#!/usr/bin/env python3
"""
Stop hook -- Definition of Done gate.

Opt-in hard brake on session close. Reads `.claude/project-memory/config.json`
from cwd; if the field `test_command` (non-empty string) is present, runs
that command before allowing the session to end.

- tests pass (exit 0)  → allow close (no output, or {"decision":"allow"})
- no test_command      → allow (opt-in, fail-safe)
- any infra error      → FAIL-OPEN: allow close, never trap the user

A non-zero exit is no longer a blanket block -- it is CLASSIFIED first
[2026-08-20], so that the intentional red of test-first work is not
confused with a real failure:

- exit 5  (pytest: suite empty, no tests collected)     → ALLOW, with an
  informational stderr warning shown once per session_id.
- exit 1  (pytest: tests ran and genuinely failed)      → BLOCK, unchanged.
- exit 2  (pytest: collection error) → every "No module named 'X'" match
  in stdout+stderr is classified on its own:
    - no match at all (e.g. a SyntaxError in the test file itself) → BLOCK
      (nothing to classify, D2 applies: block on any doubt).
    - X's first dotted segment doesn't exist locally (disk or git HEAD)
      → BLOCK (a real, typically third-party, dependency is missing).
    - X's concrete source file exists on disk but still failed to import
      → BLOCK (defensive branch; existing-but-broken is a real failure).
    - X's concrete source is absent on disk AND absent from git HEAD
      (a local module that was simply never written yet, test-first in
      flight) → ALLOW, with a stderr warning shown once per module per
      session_id.
    - X's concrete source is absent on disk but IS tracked in git HEAD
      (it existed, got committed, then got removed from the worktree)
      → BLOCK (real code went missing, not "not written yet").
    A run with several missing modules only allows when EVERY one of them
    classifies as "never written" -- a single one that blocks makes the
    whole result block.
  See lib/dod_gate_classify.py and lib/git_helpers.py:git_tracked_status()
  for the git-HEAD half of this classification (tri-state -- "tracked" /
  "untracked" / "unknown", never collapses a git failure into "safe to
  allow").
- any other non-zero exit                               → BLOCK (unchanged
  fallback -- D2, the golden rule: any exit code this tree doesn't name
  explicitly is treated as a real failure, never fail-open on a
  classification the code can't explain).

Anti-drip (dedup on BLOCK only): a signature -- sha256 of the sorted set of
output lines starting with "FAILED", "ERROR", or "E   " (E + 3 spaces),
plus exit_code -- is kept per session_id in
`.claude/.unmassk/stop-dod-gate-state.json`. The SAME signature repeated
within the SAME session collapses the block reason to a one-line reminder
(no output dump); a new signature (new failure content, or a different/
missing session_id) always gets the full reason. State I/O is best-effort:
any failure to read or write it only degrades dedup back to "always full
reason" -- it can never change block vs. allow.

Security: test_command is always executed with shell=False via shlex.split().
This prevents metacharacter injection (;, &&, |, $(...)) even if the config
value contains them. (T1 requirement — see test_stop_dod_gate.py.)

Timeout: subprocess is capped at 60 s (TIMEOUT_SECONDS). A command that
exceeds this results in fail-open (TimeoutExpired is caught).

I/O contract (Stop hook):
  stdin:  JSON Stop event -- session_id (str) is read for dedup/warn-once
          keying; every other field is ignored.
  stdout: {"decision":"block","reason":"..."} when blocking; empty when allowing
  exit:   always 0
"""

import hashlib
import json
import os
import shlex
import subprocess
import sys
import traceback

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from git_helpers import open_no_follow_symlink, ensure_runtime_dir, UNMASSK_RUNTIME_DIR
from dod_gate_classify import classify_collection_error

TIMEOUT_SECONDS = 60
STATE_FILENAME = "stop-dod-gate-state.json"
# Sentinel exit_code for the UnicodeDecodeError defense-in-depth branch in
# _run_test_command() -- never a real subprocess.run() returncode (those
# are always >= 0, or negative-as-signal on POSIX with a real signum
# magnitude). Deliberately distinct from -1 (already meaningful: a real
# SIGHUP-killed child) so the two block causes stay distinguishable if
# ever inspected. Its only job is to miss every named branch in
# _handle_nonzero_exit() (5, 1, 2) and fall into the "any other non-zero
# exit -> BLOCK" fallback -- the exact value carries no other meaning.
_DECODE_ERROR_EXIT_CODE = -9999
# El fichero de configuracion del proyecto es el del sistema nuevo
# [movido 2026-08-06]. Hasta hoy este hook leia
# `.claude/git-memory-config.json`, el del sistema anterior, y era el
# ULTIMO consumidor vivo que le quedaba.
#
# No era solo un nombre viejo: ese fichero llevaba dentro su propio
# `repo_type`, que NADIE lee -- este hook solo saca `test_command` de ahi --
# y que **contradecia al del sistema nuevo**. Medido en este mismo
# repositorio: el viejo decia `trunk` y el vivo dice `gitflow`. Dos
# ficheros de configuracion diciendo lo contrario sobre si la rama
# principal esta protegida es exactamente el fallo callado que este
# proyecto declara como su unica amenaza: el que lea el equivocado
# concluye lo contrario y no hay nada que le avise.
#
# Las tres claves del sistema nuevo (`customs_enabled`, `repo_type`,
# `test_command`) viven juntas en un solo sitio, que es lo que ya
# declaraba `lib/memory/config.py`.
CONFIG_SUBPATH = os.path.join(".claude", "project-memory", "config.json")


def _tokenize(cmd: str) -> list[str]:
    """Tokenize a shell command string into a list of arguments.

    Uses shlex.split(posix=False) so that Windows paths (backslash separators)
    are not interpreted as POSIX escape sequences.  After splitting, outer
    quote characters added by the shell convention are stripped from each
    token so that Python receives the bare string value.

    This keeps shell=False (T1 requirement) while correctly handling both
    POSIX and Windows path styles in the test_command config value.

    Example:
        'python -c "import sys; sys.exit(1)"'
        → ['python', '-c', 'import sys; sys.exit(1)']
    """
    tokens = shlex.split(cmd, posix=False)
    result = []
    for token in tokens:
        if (
            len(token) >= 2
            and (
                (token[0] == '"' and token[-1] == '"')
                or (token[0] == "'" and token[-1] == "'")
            )
        ):
            result.append(token[1:-1])
        else:
            result.append(token)
    return result


def _warn_corrupt_config(config_file: str, error: BaseException) -> None:
    """Emit a visible stderr warning that config.json exists but could not
    be read/parsed. Never raises — a failure to write the warning itself
    must not escape (stderr is best-effort, same discipline as the rest of
    this hook's fail-open contract).

    Distinct on purpose from the "no test_command configured" case, which
    stays fully silent (see TestNoCommandStaysSilent /
    TestCorruptConfigMustWarn in test_stop_dod_gate.py) — this path only
    fires when config.json is PRESENT but unreadable/invalid, never when
    it is simply absent or doesn't declare test_command.
    """
    try:
        sys.stderr.write(
            f"stop-dod-gate: {config_file} exists but could not be read as "
            f"valid JSON ({error.__class__.__name__}: {error}). "
            "test_command gate skipped (fail-open) -- fix or remove the "
            "config file.\n"
        )
        sys.stderr.flush()
    except Exception:
        pass


def _read_test_command(cwd: str) -> str | None:
    """Return test_command from .claude/project-memory/config.json, or None.

    Returns None on any error (missing file, parse error, wrong type,
    empty/null value) — all of which are treated as opt-out (fail-open).

    A MISSING config file is the normal "opt-in not configured" state and
    stays fully silent -- this is a real reader of config.py's contract,
    same as customs.py, but unlike customs.py (which fails loud/high on a
    corrupt config) this hook is fail-open by design: it must never block
    session close over its own infra problems. A PRESENT but corrupt/
    unreadable config file (invalid JSON, or the path is a directory) is a
    DIFFERENT case and emits a visible stderr warning via
    _warn_corrupt_config() before returning None, so it is never
    indistinguishable from "not configured" to whoever reads the hook's
    output.
    """
    config_file = os.path.join(cwd, CONFIG_SUBPATH)
    try:
        # barrido finding: never follow a symlink planted at
        # config.json — an attacker-controlled test_command must
        # never be read from (and thus executed via) an external file.
        with open_no_follow_symlink(config_file, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        # No config file at all — normal opt-in-not-configured state.
        # Stays fully silent (TestNoCommandStaysSilent).
        return None
    except (OSError, json.JSONDecodeError) as e:
        # config.json exists but is unreadable/invalid — distinct failure,
        # must not pass in total silence (TestCorruptConfigMustWarn).
        _warn_corrupt_config(config_file, e)
        return None

    cmd = config.get("test_command")
    if not cmd or not isinstance(cmd, str):
        return None
    return cmd


def _run_test_command(test_command: str) -> tuple[bool, int | None, str]:
    """Execute test_command with shell=False.

    Returns (passed, exit_code, combined_output).
    passed is True when exit_code == 0 (tests genuinely passed) OR when
    exit_code is None (test_command could not be run to completion at
    all -- fail-open). exit_code is a real int in every OTHER case,
    including a negative one -- a real subprocess.run() returncode is
    negative when the child was killed by a signal (POSIX:
    returncode == -signum), which is a genuine red, not an infra problem,
    and must reach the exit-code classifier as any other non-zero exit
    (falls through to the "any other non-zero exit -> BLOCK" branch).

    exit_code=None ONLY on a genuine "could not run the command at all"
    failure -- caught BEFORE the child ever produced a return code
    (FileNotFoundError, TimeoutExpired, OSError, ValueError).

    [2026-08-20, Argus LOW finding, Verify pass]: this used to signal
    "infra failure" with the SENTINEL VALUE -1 instead of None -- but -1
    is also EXACTLY the real `returncode` POSIX reports for a child
    killed by SIGHUP (`-signum`, signum=1). A test run that dies to
    SIGHUP is a real red (something killed the test process), not an
    infra problem with running test_command itself -- the old sentinel
    made the two indistinguishable, so `main()`'s `if passed: sys.exit(0)`
    would fail-open and allow session close over a genuinely-killed test
    run. `None` can never come from `result.returncode` (always an int),
    so there is no collision by construction -- "could not run" and "ran,
    got a real (possibly negative) code" are now structurally distinct.

    PYTHONDONTWRITEBYTECODE=1 is forced on the child's env (additive over
    the inherited environment, never mutates this process's own os.environ)
    [2026-08-20, found while implementing the exit-5/1/2 classification
    above]: reproduced directly against real pytest -- two source writes to
    the SAME path, of the SAME byte length, close enough together to share
    one filesystem mtime tick, leave `__pycache__` holding a stale .pyc.
    Python's import cache validates on (mtime, size) by default, both of
    which matched, so the SECOND run silently re-executed the FIRST run's
    compiled AssertionError message while showing the NEW source line in
    its traceback -- a real, reproducible silent-failure class this
    project's threat model explicitly forbids ("a failure must not pass
    silently"), not specific to the block-signature dedup feature above:
    any repo where a fix and a rerun land in the same mtime tick would hit
    it. Forcing PYTHONDONTWRITEBYTECODE=1 stops `__pycache__` from ever
    being written for this subprocess tree, so there is never a stale .pyc
    to read from a later run.
    """
    try:
        args = _tokenize(test_command)
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
            env=env,
        )
        combined = (result.stdout + result.stderr).strip()
        return result.returncode == 0, result.returncode, combined
    except subprocess.TimeoutExpired:
        return True, None, ""  # fail-open: could not run to completion
    except UnicodeDecodeError:
        # [2026-08-20, Yoda finding] errors="replace" above means decoding
        # itself can no longer raise -- this is defense-in-depth so that
        # IF it ever did, this ValueError subclass can't fall into the
        # broader except below and silently fail-open over a real red.
        # Must stay listed before that broader tuple (first-match wins).
        return False, _DECODE_ERROR_EXIT_CODE, ""
    except (FileNotFoundError, OSError, ValueError):
        return True, None, ""  # fail-open: could not run at all


def _build_block_reason(test_command: str, exit_code: int, output: str) -> str:
    """Produce a human-readable block reason."""
    base = (
        f"Tests failed (exit {exit_code}). "
        f"Fix the failing tests before closing the session. "
        f"Command: {test_command!r}"
    )
    if output:
        # Include at most 500 chars of output to stay useful without flooding
        snippet = output[:500]
        if len(output) > 500:
            snippet += f"\n... ({len(output) - 500} chars truncated)"
        return f"{base}\n\nOutput:\n{snippet}"
    return base


# ── stdin session_id extraction ─────────────────────────────────────────────

def _extract_session_id(raw_stdin: str) -> str:
    """Best-effort session_id from the Stop event JSON payload on stdin.

    Returns "" (a stable, falsy-but-usable sentinel) when the payload is
    empty, not valid JSON, or has no string `session_id` field. "" is a
    perfectly valid dedup key like any other -- it just means every
    invocation that omits session_id shares one bucket instead of being
    treated as a brand-new session each time. Never raises.
    """
    try:
        payload = json.loads(raw_stdin) if raw_stdin.strip() else {}
        sid = payload.get("session_id")
        return sid if isinstance(sid, str) else ""
    except Exception:
        return ""


# ── Anti-drip state (dedup by session_id) ───────────────────────────────────
#
# `.claude/.unmassk/stop-dod-gate-state.json` -- best-effort persistence.
# Any read/write failure here degrades dedup back to "always warn / always
# full reason"; it must never change a block-vs-allow decision (D2).

def _state_path(cwd: str) -> str:
    return os.path.join(cwd, UNMASSK_RUNTIME_DIR, STATE_FILENAME)


def _default_state(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "last_block_signature": None,
        "warned_empty_suite": False,
        "warned_modules": [],
    }


def _load_state(cwd: str, session_id: str) -> dict:
    """Return this session's dedup state, or a fresh one when the stored
    session_id doesn't match (new session) or the file is missing/corrupt.
    Never raises.
    """
    default = _default_state(session_id)
    try:
        with open_no_follow_symlink(_state_path(cwd), "r") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("session_id") != session_id:
            return default
        warned_modules = data.get("warned_modules")
        return {
            "session_id": session_id,
            "last_block_signature": data.get("last_block_signature"),
            "warned_empty_suite": bool(data.get("warned_empty_suite", False)),
            "warned_modules": list(warned_modules) if isinstance(warned_modules, list) else [],
        }
    except Exception:
        return default


def _save_state(cwd: str, state: dict) -> None:
    """Best-effort persist. Failure here must never surface -- it only
    means the next call re-warns / re-dumps instead of deduping."""
    try:
        runtime_dir = ensure_runtime_dir(cwd)
        path = os.path.join(runtime_dir, STATE_FILENAME)
        with open_no_follow_symlink(path, "w", atomic=True) as f:
            json.dump(state, f)
    except Exception:
        pass


def _warn_empty_suite_once(cwd: str, session_id: str) -> None:
    state = _load_state(cwd, session_id)
    if state["warned_empty_suite"]:
        return
    try:
        sys.stderr.write(
            "stop-dod-gate: test_command reported an empty test suite "
            "(exit 5, no tests collected) -- allowing session close, but "
            "check this is intentional.\n"
        )
        sys.stderr.flush()
    except Exception:
        pass
    state["warned_empty_suite"] = True
    _save_state(cwd, state)


def _warn_never_written_module_once(cwd: str, session_id: str, module: str) -> None:
    state = _load_state(cwd, session_id)
    if module in state["warned_modules"]:
        return
    try:
        sys.stderr.write(
            f"stop-dod-gate: local module '{module}' is imported but was "
            "never written (absent on disk, not tracked in git) -- "
            "allowing session close (test-first in flight). Create the "
            "file before the next real run.\n"
        )
        sys.stderr.flush()
    except Exception:
        pass
    state["warned_modules"].append(module)
    _save_state(cwd, state)


# ── exit-2 collection-error classification ──────────────────────────────────
#
# The actual classification (extract_missing_modules / seg_exists /
# module_source_candidates / classify_missing_module /
# classify_collection_error) lives in lib/dod_gate_classify.py [2026-08-20,
# size/testability extraction, Cerberus/Argus Verify pass] -- pure
# functions, no hook-only concerns, directly importable for unit tests.


# ── non-zero exit classification (exit 5 / 1 / 2 / other) ──────────────────

def _handle_nonzero_exit(cwd: str, session_id: str, exit_code: int, output: str) -> bool:
    """Classify a non-zero test_command exit. Returns True to ALLOW close,
    False to BLOCK. May emit deduped stderr warnings as a side effect --
    warning/state I/O never changes the returned decision (D2)."""
    if exit_code == 5:
        _warn_empty_suite_once(cwd, session_id)
        return True

    if exit_code == 1:
        return False

    if exit_code == 2:
        allow, never_written = classify_collection_error(cwd, output)
        if allow:
            for module in never_written:
                _warn_never_written_module_once(cwd, session_id, module)
            return True
        return False

    # Any other non-zero exit code — unchanged fallback: block.
    return False


# ── block-reason anti-drip (signature dedup by session_id) ─────────────────

def _is_signature_line(line: str) -> bool:
    return line.startswith("FAILED") or line.startswith("ERROR") or line.startswith("E   ")


def _compute_block_signature(exit_code: int, output: str) -> str:
    """sha256 of the sorted set of FAILED/ERROR/E-prefixed lines, plus
    exit_code. Deliberately excludes timing lines ("in 0.04s") so a rerun
    of the exact same failure produces the same signature."""
    lines = {line for line in output.splitlines() if _is_signature_line(line)}
    material = f"{exit_code}\n" + "\n".join(sorted(lines))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _build_block_reason_deduped(
    cwd: str, session_id: str, test_command: str, exit_code: int, output: str
) -> str:
    """Full block reason on a new signature; a one-line reminder (no output
    dump) when the SAME signature already blocked this session."""
    signature = _compute_block_signature(exit_code, output)
    state = _load_state(cwd, session_id)
    if state["last_block_signature"] == signature:
        return "Tests still failing (same failure as last check) -- see the previous block reason for details."
    state["last_block_signature"] = signature
    _save_state(cwd, state)
    return _build_block_reason(test_command, exit_code, output)


def main() -> None:
    """Entry point. Always exits 0. Blocks via stdout JSON, not exit code."""
    # Read stdin — used only for session_id (dedup key); must not crash on
    # bad/empty input.
    raw_stdin = ""
    try:
        raw_stdin = sys.stdin.read()
    except Exception:
        pass

    session_id = _extract_session_id(raw_stdin)
    cwd = os.getcwd()

    try:
        test_command = _read_test_command(cwd)
        if not test_command:
            # Opt-in not configured — allow silently.
            sys.exit(0)

        # TRUST ASSUMPTION: test_command is executed as a subprocess with the
        # privileges of the current process. The file .claude/project-memory/config.json
        # must only contain commands from trusted sources (repo authors). It is NOT
        # sandboxed — do not place commands from untrusted or user-supplied input here.
        passed, exit_code, output = _run_test_command(test_command)

        if passed:
            # Allow — no output needed (implicit allow).
            sys.exit(0)

        if _handle_nonzero_exit(cwd, session_id, exit_code, output):
            # Classified as safe to allow (empty suite, or every missing
            # module is "never written") — no block, warnings already emitted.
            sys.exit(0)

        # Block.
        reason = _build_block_reason_deduped(cwd, session_id, test_command, exit_code, output)
        json.dump({"decision": "block", "reason": reason}, sys.stdout)
        sys.stdout.flush()

    except Exception:
        # Any unexpected error → fail-open.
        # Write diagnostic to stderr (best-effort; a write failure must not
        # propagate — stderr is never the decision channel).
        try:
            sys.stderr.write(traceback.format_exc())
        except Exception:
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
