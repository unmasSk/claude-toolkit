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
NORMALIZED before hashing, plus exit_code -- is kept per session_id in
`.claude/.unmassk/stop-dod-gate-state.json`. [2026-08-22] A real report
measured 704 orphaned processes from a red suite re-running on every
Stop because the signature never repeated: pytest's own "E   " lines can
carry volatile content (a generator/object memory address, a temp path,
a UUID, a timing figure) that changes on every real run of the exact
same failure. The fix is normalization, not exclusion: `0x[0-9a-f]+`
addresses, paths under the system temp dir, UUIDs, and `in N.NNs`-style
timing figures are replaced with stable placeholders before hashing (see
`_normalize_volatile()`). E lines stay IN the signature on purpose --
pytest's own FAILED summary line is truncated to a fixed width, so two
genuinely different failures (different assertion content, same test
name) can share an identical FAILED line; dropping E lines wholesale was
tried and reverted after it collapsed exactly that case (see
`_is_signature_line()`'s docstring for the concrete repro). The SAME
signature repeated within the SAME session collapses the block reason to
a one-line reminder (no output dump); a new signature (new failure
content, or a different/missing session_id) always gets the full reason.
State I/O is best-effort: any failure to read or write it only degrades
dedup back to "always full reason" -- it can never change block vs.
allow.

Tree-fingerprint cache [2026-08-22]: test_command runs on EVERY Stop
event, and it is NOT guaranteed idempotent or free of side effects (the
real report above: a project's test_command played real audio on every
invocation, and a red suite means Stop fires repeatedly in one session --
that alone produced the 704 orphaned processes, independent of the
dedup gap above). test_command MUST be safe to run repeatedly and MUST
NOT have side effects beyond what running a test suite implies (no audio,
no system notifications, no writes outside temp locations, no network
calls) -- the gate multiplies whatever it does. To cut the real damage
(re-running at all when nothing changed), a fingerprint of the working
tree (`git rev-parse HEAD` + `git status --porcelain`, hashed) is kept
alongside the anti-drip state, per session_id. On the next Stop, if the
fingerprint is IDENTICAL to the one saved, the previous decision (block
or allow, with its exact reason) is reused WITHOUT re-running
test_command. A change to the tree (even uncommitted -- this is the
working tree, not HEAD alone), or a fingerprint that cannot be computed
at all (not a git repo, or git itself fails) ALWAYS forces a real run --
never skip the check on doubt (D2). Reusing a decision can never turn a
block into an allow or vice versa: it replays the exact decision that was
saved, nothing else.

Declared in-flight contracts (Caso 17) [2026-08-22]: the toolkit's own
build method is test-first -- Dante writes the contract in red, Ultron
implements until green -- and without this, a red written ON PURPOSE
blocks Stop exactly like a real regression, on every Stop while the
implementation is in flight. `bin/stop-dod-declare.py declare
<test_node_id...> --session <ID>` lets the orchestrator name, explicitly
(never inferred), which currently-failing pytest node ids are a known
in-flight contract for this session. When exit_code == 1 (pytest ran and
some tests genuinely failed): if EVERY currently-failing node id is
declared, allow with a visible stderr notice (never silent); if even one
failing id is undeclared, block as before (D2) -- a declaration for OTHER
tests never shields an undeclared failure, and a mix always blocks.

[2026-08-22, live-project follow-up] exit_code == 1 alone missed the
MOST common test-first shape: a test importing a function that doesn't
exist yet is a pytest COLLECTION error (exit_code == 2), not a failed
assertion -- and a collection error never produces a node id at all (the
file didn't finish collecting), only a file path. So exit_code == 2 is
ALSO checked against the declaration, at FILE granularity instead of
node-id granularity: an errored file is shielded when any declared node
id names that file. This SUMS to the pre-existing never-written-module
classification for exit_code == 2 (see classify_collection_error()), it
does not replace it -- either one allowing is enough. Same requisitos as
exit_code == 1: a mix of declared and undeclared errored files always
blocks, naming the undeclared one(s).

Real pytest limitation, not a hole in this hook [2026-08-22, honesty
finding from a live project's own manual replay]: a collection error
ABORTS collection entirely by default ("Interrupted: N errors during
collection") -- every OTHER test in that run, declared or not, simply
never executes at all, and produces no result for this hook (or anything
else) to see. So when the shield allows a Stop because every errored
file is declared, that "allow" can NOT mean "the rest of the suite is
green" -- it may mean the rest of the suite never ran. Blocking here
would defeat the whole point of the declaration (it would mean no
test-first contract could ever import a not-yet-written name without
manually running with a flag pytest doesn't use by default), so allowing
is still correct -- but doing it in silence would be misleading. The
stderr notice for this exact path (`_warn_declared_contract_shields(...,
collection_interrupted=True)`) says so explicitly: "Collection was
interrupted, so the rest of the suite did NOT run: this is not a green."
This is a WORDING fix only, not a decision-logic change.

If `test_command` instead runs with `--continue-on-collection-errors`
(or any other flag that makes pytest keep going after a collection
error), OTHER tests in the same run DO produce real results -- pytest
then reports both `FAILED <node_id>` and `ERROR <path>` lines together,
typically with exit_code == 1 rather than 2. That case already has real
results to check, so it goes through the ORDINARY exit_code == 1 path
above (matched by node id, via `_extract_failed_node_ids()`) -- an
undeclared FAILED test there still blocks and is still named, exactly as
without any collection error in the mix; a file that only shows an ERROR
line (no FAILED entry for it) is not currently matched by the exit_code
== 1 path at all, since that path only looks at FAILED lines -- a known,
narrower scope than the exit_code == 2 path, left as-is because
`--continue-on-collection-errors` is not this project's own default and
was out of scope for this round's fix.

Each real run drops any declared id that is no longer failing (auto-clears
the moment its red turns green, nobody retracts it by hand). The
declaration lives in the SAME per-session state file as the anti-drip/
fingerprint data (`.claude/.unmassk/stop-dod-gate-state.json`, see
lib/dod_gate_state.py) and does not survive a different session_id --
with no declaration in effect, behavior is byte-for-byte unchanged from
before this feature.

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
import re
import shlex
import subprocess
import sys
import tempfile
import traceback

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from git_helpers import open_no_follow_symlink, run_git, UNMASSK_RUNTIME_DIR
from dod_gate_classify import classify_collection_error
from dod_gate_state import (
    state_path as _state_path,
    default_state as _default_state,
    load_state as _load_state,
    save_state as _save_state,
)

TIMEOUT_SECONDS = 60
# STATE_FILENAME lives in lib/dod_gate_state.py now (single source of
# truth, shared with bin/stop-dod-declare.py) -- no local copy here.
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


# ── Working-tree fingerprint (skip a rerun when nothing changed) ───────────
#
# See the module docstring, "Tree-fingerprint cache", for the full report
# and contract. Uses lib/git_helpers.py:run_git() -- never a raw
# subprocess call -- same discipline as every other git read in this repo.

_RUNTIME_DIR_POSIX = UNMASSK_RUNTIME_DIR.replace(os.sep, "/")
_RUNTIME_DIR_PREFIX = _RUNTIME_DIR_POSIX + "/"


def _unquote_git_path(raw: str) -> str:
    """Strip git's C-style quoting wrapper (used for paths with spaces or
    non-ASCII bytes) -- only the wrapping quotes, not a full escape
    decode. Good enough here: this string is only ever used to build a
    stable per-path identity for the fingerprint, never displayed or
    used to open a file with attacker-relevant precision beyond what
    os.path.join+os.stat already tolerates."""
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        raw = raw[1:-1]
    return raw


def _porcelain_line_paths(rest: str) -> list[str]:
    """Extract the path(s) named by one `git status --porcelain` line's
    tail (everything after the "XY " status prefix). A rename/copy line
    carries two paths joined by " -> "; every other line carries one."""
    if " -> " in rest:
        old_path, new_path = rest.split(" -> ", 1)
        return [_unquote_git_path(old_path), _unquote_git_path(new_path)]
    return [_unquote_git_path(rest)]


def _is_runtime_path(path: str) -> bool:
    """True for anything under the toolkit's own runtime directory
    (`.claude/.unmassk/`, UNMASSK_RUNTIME_DIR) -- what the gate itself
    writes (this same state file) must never count as "the project
    changed" when computing the fingerprint, or the gate re-triggers a
    real run purely because it wrote its own bookkeeping."""
    normalized = path.replace("\\", "/")
    return normalized == _RUNTIME_DIR_POSIX or normalized.startswith(_RUNTIME_DIR_PREFIX)


def _content_mark(cwd: str, rel_path: str) -> str:
    """`<path>:<mtime_ns>:<size>`, or `<path>:MISSING` when the path can't
    be stat'd (deleted, permission error, race) -- a missing/unreadable
    file still contributes its OWN stable mark rather than raising, so
    one bad path never breaks the whole fingerprint computation."""
    full_path = os.path.join(cwd, rel_path)
    try:
        st = os.stat(full_path)
        return f"{rel_path}:{st.st_mtime_ns}:{st.st_size}"
    except OSError:
        return f"{rel_path}:MISSING"


def _compute_tree_fingerprint(cwd: str) -> str | None:
    """sha256 of `HEAD` + a content-aware digest of `git status
    --porcelain`, or None when it cannot be computed at all (not a git
    repo, or git itself fails for any reason). Callers MUST treat None as
    "always run test_command" -- never skip the run on doubt (D2),
    mirroring the same `rev-parse --is-inside-work-tree` pre-check
    pattern already used by git_tracked_status() in lib/git_helpers.py.

    [2026-08-22, live-project report] `git status --porcelain` alone
    reports each path's STATE (modified / untracked / etc.), not its
    CONTENT -- editing an already-modified (or already-untracked) file
    produces the exact same porcelain line, so the fingerprint never
    changed and a stale cached decision (including a stale BLOCK) kept
    getting replayed forever, even after the real fix landed. Fix: for
    every path named in the porcelain output, fold in its mtime_ns and
    size (`_content_mark()`) -- cheap and sufficient per the report's own
    fix, without hashing file contents outright. Paths under this gate's
    OWN runtime directory (`.claude/.unmassk/`) are excluded entirely
    (`_is_runtime_path()`) -- the state file this function's own caller
    writes must never count as "the project changed" (measured in the
    same report: 4 no-op Stops produced 2 real reruns instead of 1,
    because writing the state file itself moved the porcelain output)."""
    repo_code, _ = run_git(["rev-parse", "--is-inside-work-tree"], cwd=cwd)
    if repo_code != 0:
        return None
    head_code, head = run_git(["rev-parse", "HEAD"], cwd=cwd)
    if head_code != 0:
        return None
    # -uall: expand untracked directories into their individual files
    # instead of one collapsed "?? dir/" line -- otherwise, the moment
    # ANY part of an untracked ".claude/" is untracked (no .gitignore
    # for it, the common case), git collapses the ENTIRE tree -- state
    # file included -- into a single line, and that line's directory
    # mtime changes the instant _save_state() writes under it, so the
    # _is_runtime_path() path-prefix filter below never gets a chance
    # to see (and exclude) the individual runtime-dir path at all.
    status_code, status = run_git(["status", "--porcelain", "-uall"], cwd=cwd)
    if status_code != 0:
        return None

    relevant_lines = []
    content_marks = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        rest = line[3:]
        paths = _porcelain_line_paths(rest)
        if any(_is_runtime_path(p) for p in paths):
            continue
        relevant_lines.append(line)
        for p in paths:
            content_marks.append(_content_mark(cwd, p))

    material = f"{head}\n" + "\n".join(relevant_lines) + "\n" + "\n".join(content_marks)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


# ── Anti-drip state (dedup by session_id) ───────────────────────────────────
#
# `.claude/.unmassk/stop-dod-gate-state.json` -- best-effort persistence.
# Any read/write failure here degrades dedup back to "always warn / always
# full reason"; it must never change a block-vs-allow decision (D2).
#
# The actual load/save/default-shape logic lives in lib/dod_gate_state.py
# [2026-08-22, Caso 17 extraction] -- re-imported above under these same
# private names so every call site below is unchanged. Shared with
# bin/stop-dod-declare.py, which reads and writes the exact same file.


def _save_decision(cwd: str, session_id: str, fingerprint: str | None, decision: dict) -> None:
    """Persist the tree fingerprint alongside the decision just reached
    (`{"decision": "allow"}` or `{"decision": "block", "reason": ...}`),
    so the next Stop with an unchanged tree can reuse it without
    re-running test_command.

    Re-loads state FRESH right before writing -- rather than reusing an
    in-memory copy captured earlier in this same invocation -- because
    other helpers already called in this same run (_warn_empty_suite_once,
    _warn_never_written_module_once, _build_block_reason_deduped) each do
    their own load-modify-save round trip against the same state file; a
    stale in-memory copy here would silently clobber whatever they just
    wrote. Best-effort like the rest of this state file: a failure here
    only degrades the cache back to "always rerun", it can never change
    a decision (D2)."""
    state = _load_state(cwd, session_id)
    state["tree_fingerprint"] = fingerprint
    state["cached_decision"] = decision
    _save_state(cwd, state)


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


# ── declared in-flight contracts (Caso 17, 2026-08-22) ─────────────────────
#
# The toolkit's own build method is test-first: Dante writes the contract
# in red, Ultron implements until green. Without this section, a red
# written ON PURPOSE blocks Stop exactly like a real regression, every
# single Stop while the implementation is in flight. `bin/stop-dod-
# declare.py declare <node_id...> --session <ID>` lets the orchestrator
# say, explicitly, which currently-failing pytest node ids are a known
# in-flight contract -- never inferred from the output itself. Declaring
# a test that isn't ACTUALLY failing has no effect either way (it simply
# never shows up in the currently-failing set below).

def _extract_failed_node_ids(output: str) -> set[str]:
    """pytest node ids (`<file>::<test>`) parsed from the real "FAILED "
    summary lines already trusted by the anti-drip signature
    (`_is_signature_line`). Used to compare a real run's currently-failing
    tests against this session's declared contracts. Never raises -- a
    line that doesn't parse simply contributes nothing."""
    ids: set[str] = set()
    for line in output.splitlines():
        if line.startswith("FAILED "):
            rest = line[len("FAILED "):].strip()
            node_id = rest.split(" - ", 1)[0].strip()
            if node_id:
                ids.add(node_id)
    return ids


def _declared_ids(cwd: str, session_id: str) -> set[str]:
    return set(_load_state(cwd, session_id).get("declared_tests", []))


def _classify_declared_reds(
    cwd: str, session_id: str, failing_ids: set[str], errored_files: set[str]
) -> tuple[bool, set[str]]:
    """Compare a real run's currently-red items against this session's
    declared contracts, for exit_code == 1 runs -- which can carry BOTH
    real FAILED node ids and collection ERROR file entries at once (e.g.
    `test_command` run with `--continue-on-collection-errors`: pytest
    then reports `FAILED <node_id>` and `ERROR <path>` lines together,
    usually with exit_code == 1 instead of 2).

    [2026-08-22, live-project report, second finding] checking ONLY
    `failing_ids` (FAILED lines) here missed a declared node id whose
    file still has a collection ERROR in the same run -- that file never
    shows up as FAILED (pytest never got far enough to run its tests), so
    it looked resolved/undeclared to a node-id-only check even though
    the underlying red never actually turned green. Fixed by ALSO
    matching declared node ids against errored files, at file
    granularity, same as `_classify_declared_collection_errors()` does
    for exit_code == 2 -- `undeclared` here can mix node ids (real
    failures) and bare file paths (collection errors), whichever the red
    item actually is. `all_declared` is True only when there's at least
    one red item overall AND every one of them (by either match) is
    declared (requisitos 1/2/3: a declaration for OTHER tests/files never
    shields an undeclared one, and a mix always blocks)."""
    declared_ids = _declared_ids(cwd, session_id)
    declared_files = {node_id.partition("::")[0] for node_id in declared_ids}
    undeclared_node_ids = failing_ids - declared_ids
    undeclared_files = errored_files - declared_files
    undeclared = undeclared_node_ids | undeclared_files
    any_red = bool(failing_ids) or bool(errored_files)
    return (any_red and not undeclared), undeclared


def _clear_resolved_declarations(
    cwd: str,
    session_id: str,
    currently_failing: set[str],
    currently_errored_files: "set[str] | frozenset[str]" = frozenset(),
) -> None:
    """Drop any declared node id that is no longer red -- the declaration
    clears itself the moment its red turns green, nobody has to retract
    it by hand. Called once per REAL run (never on a cached-decision
    reuse, which has no fresh failing set to compare against).

    A declared node id is kept when it EITHER still appears in
    `currently_failing` (a real FAILED node id) OR its file still appears
    in `currently_errored_files` (a collection ERROR, which never
    produces a node id at all -- see `_extract_collection_error_files()`)
    [2026-08-22, live-project report, second finding]: without the
    second check, a declared collection-error file whose import is STILL
    broken got silently dropped from the declared set the instant a
    DIFFERENT, unrelated FAILED test also happened to be in the same run
    (exit_code == 1 with `--continue-on-collection-errors`) -- the file's
    own red never turned green, but the node-id-only check couldn't see
    it was still red at all. Best-effort like the rest of this state
    file: a save failure here only leaves a stale entry lingering, it can
    never change a decision (D2)."""
    state = _load_state(cwd, session_id)
    declared = state.get("declared_tests", [])
    remaining = [
        node_id
        for node_id in declared
        if node_id in currently_failing or node_id.partition("::")[0] in currently_errored_files
    ]
    if remaining != declared:
        state["declared_tests"] = remaining
        _save_state(cwd, state)


def _warn_declared_contract_shields(
    cwd: str, session_id: str, shielded: set[str], collection_interrupted: bool = False
) -> None:
    """Visible (never silent) notice that every currently-failing test is
    covered by an in-flight contract declared for this session.

    `collection_interrupted` (2026-08-22, live-project honesty finding):
    when the shield fires for a COLLECTION error (exit_code == 2), pytest
    itself never ran the rest of the suite at all -- it aborts collection
    entirely the moment any file fails to import ("Interrupted: N errors
    during collection"), so no other test in the run produced a result,
    declared or not. Allowing here is still the right call (blocking would
    kill the feature this exists for), but staying silent about WHY would
    let whoever reads the notice believe the rest of the suite is green
    when it simply never ran. This is a WORDING-ONLY distinction: the
    allow/block decision itself is unaffected either way."""
    try:
        names = ", ".join(sorted(shielded))
        message = (
            "stop-dod-gate: declared test-first contract in flight -- "
            f"{len(shielded)} failing test(s) covered ({names}); allowing "
            "session close."
        )
        if collection_interrupted:
            message += (
                " Collection was interrupted, so the rest of the suite "
                "did NOT run: this is not a green."
            )
        sys.stderr.write(message + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def _extract_collection_error_files(output: str) -> set[str]:
    """Repo-relative file paths parsed from pytest's own short-summary
    "ERROR <path>" lines (exit_code == 2, collection failure) -- the
    file-level analogue of `_extract_failed_node_ids()`.

    [2026-08-22, live-project report] the most common test-first shape is
    NOT an assertion that fails -- it's a test file importing a function
    that doesn't exist yet, which pytest reports as a COLLECTION error
    (exit 2), not a test failure (exit 1). A collection error never
    produces a pytest node id at all (the file didn't finish collecting
    far enough to name one) -- only a file path -- so declared-contract
    matching for this exit code has to happen at FILE granularity, never
    node-id granularity."""
    files: set[str] = set()
    for line in output.splitlines():
        if line.startswith("ERROR "):
            rest = line[len("ERROR "):].strip()
            file_path = rest.split(" - ", 1)[0].strip()
            if file_path:
                files.add(file_path)
    return files


def _declared_files(cwd: str, session_id: str) -> set[str]:
    """Files named by this session's declared node ids -- the part before
    `::`, or the whole string when a declared id has no `::` at all (a
    file-level declaration would already look like this)."""
    return {node_id.partition("::")[0] for node_id in _declared_ids(cwd, session_id)}


def _classify_declared_collection_errors(
    cwd: str, session_id: str, errored_files: set[str]
) -> tuple[bool, set[str]]:
    """File-granularity analogue of `_classify_declared_failures()`, for
    exit_code == 2. An errored file is shielded when ANY declared node id
    names that same file -- a node id declares a specific test inside a
    file, but the file itself hasn't even collected yet, so this is the
    coarsest match that's actually possible here. Same requisitos 1/2/3
    as the exit_code == 1 case: a declaration for another file never
    shields this one, and a mix always blocks."""
    declared = _declared_files(cwd, session_id)
    undeclared = errored_files - declared
    return (bool(errored_files) and not undeclared), undeclared


# ── non-zero exit classification (exit 5 / 1 / 2 / other) ──────────────────

def _handle_nonzero_exit(
    cwd: str, session_id: str, exit_code: int, output: str, failing_ids: set[str] | None = None
) -> bool:
    """Classify a non-zero test_command exit. Returns True to ALLOW close,
    False to BLOCK. May emit deduped stderr warnings as a side effect --
    warning/state I/O never changes the returned decision (D2)."""
    if exit_code == 5:
        _warn_empty_suite_once(cwd, session_id)
        return True

    if exit_code == 1:
        failing = failing_ids if failing_ids is not None else _extract_failed_node_ids(output)
        errored_files = _extract_collection_error_files(output)
        all_declared, undeclared = _classify_declared_reds(cwd, session_id, failing, errored_files)
        if all_declared:
            # Every currently-red item (FAILED node id, or a collection
            # ERROR file that ran alongside real results -- see
            # `_classify_declared_reds()`) is a declared in-flight
            # contract (Caso 17, requisitos 1/2/3) -- allow, but say so
            # out loud, never in silence.
            _warn_declared_contract_shields(cwd, session_id, failing | errored_files)
            return True
        return False

    if exit_code == 2:
        allow, never_written = classify_collection_error(cwd, output)
        if allow:
            for module in never_written:
                _warn_never_written_module_once(cwd, session_id, module)
            return True

        # Declared in-flight contracts also shield a collection error
        # (Caso 17 follow-up, 2026-08-22 live-project report) -- this
        # SUMS to the never-written classification above, it does not
        # replace it: that check already ran first and already returned
        # True on its own terms when every missing module was
        # never-written. This is a SEPARATE path that can still allow
        # even when the module classification alone says block, as long
        # as every file that errored is declared.
        errored_files = _extract_collection_error_files(output)
        all_declared, _undeclared_files = _classify_declared_collection_errors(
            cwd, session_id, errored_files
        )
        if all_declared:
            _warn_declared_contract_shields(
                cwd, session_id, errored_files, collection_interrupted=True
            )
            return True
        return False

    # Any other non-zero exit code — unchanged fallback: block.
    return False


# ── block-reason anti-drip (signature dedup by session_id) ─────────────────

def _is_signature_line(line: str) -> bool:
    """FAILED/ERROR lines carry a file and a test name -- the core signal
    of "which failure is this". "E   " (E + 3 spaces) traceback-body
    lines are KEPT too [2026-08-22, see below for why], because pytest's
    own FAILED summary line is truncated to a fixed width (confirmed:
    `FAILED test_x.py::test_y - AssertionError: ZZZM...`) -- two
    genuinely different assertion messages sharing a long-enough common
    prefix produce an IDENTICAL FAILED line, so FAILED/ERROR alone is not
    always enough to tell two different failures apart; the untruncated
    detail lives in the E lines. What actually varies between two REAL
    runs of the exact SAME failure (a memory address, a temp path, a
    UUID, a timing figure) is handled by `_normalize_volatile()` below,
    not by dropping E lines wholesale -- dropping them was tried first
    and reverted after it collapsed two different real pytest failures
    (different assertion marker, same truncated FAILED line) into one
    signature, breaking TestBlockSignatureDedupBySession
    .test_new_failure_content_same_session_gets_full_reason_again
    (pre-existing, verified failing 2026-08-22 with the drop-E-lines
    approach; passes with normalize-in-place)."""
    return line.startswith("FAILED") or line.startswith("ERROR") or line.startswith("E   ")


_HEX_ADDR_RE = re.compile(r"0x[0-9a-fA-F]+")
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_TIMING_RE = re.compile(r"\bin \d+(?:\.\d+)?s\b")
_TEMP_DIR_RE = re.compile(re.escape(tempfile.gettempdir()) + r"[^\s'\")]*")


def _normalize_volatile(line: str) -> str:
    """Strip content that varies between runs of the SAME failure --
    memory addresses, temp-dir paths, UUIDs, and `in N.NNs` timing
    figures -- so the signature is stable even though E lines stay in
    the candidate set. This is what actually closes the real report (a
    generator object's `0x...` address changing every run defeated
    dedup); dropping E lines outright was not the fix, see
    `_is_signature_line()`'s docstring."""
    line = _HEX_ADDR_RE.sub("0xADDR", line)
    line = _UUID_RE.sub("UUID", line)
    line = _TIMING_RE.sub("in Ns", line)
    line = _TEMP_DIR_RE.sub("TEMPPATH", line)
    return line


def _compute_block_signature(exit_code: int, output: str) -> str:
    """sha256 of the sorted set of normalized FAILED/ERROR/E-prefixed
    lines, plus exit_code. A rerun of the exact same failure -- even one
    whose output carries a volatile memory address, temp path, UUID, or
    timing figure -- produces the same signature; a genuinely different
    failure (different test, or different assertion content) still
    produces a different one."""
    lines = {
        _normalize_volatile(line)
        for line in output.splitlines()
        if _is_signature_line(line)
    }
    material = f"{exit_code}\n" + "\n".join(sorted(lines))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _build_block_reason_deduped(
    cwd: str,
    session_id: str,
    test_command: str,
    exit_code: int,
    output: str,
    undeclared_ids: set[str] | None = None,
) -> str:
    """Full block reason on a new signature; a one-line reminder (no output
    dump) when the SAME signature already blocked this session.

    `undeclared_ids` (Caso 17, requisito 3): when a mix of declared and
    undeclared failures blocks, the generic reason's truncated 500-char
    output snippet is NOT guaranteed to still contain the undeclared
    test's name (confirmed: with two tiny fixtures the declared one's
    file, listed first by pytest's alphabetical collection order, can
    consume the whole snippet on its own) -- so the undeclared id(s) are
    named in an explicit line prepended to whichever reason follows,
    first-block or deduped reminder alike."""
    signature = _compute_block_signature(exit_code, output)
    state = _load_state(cwd, session_id)
    if state["last_block_signature"] == signature:
        reason = "Tests still failing (same failure as last check) -- see the previous block reason for details."
    else:
        state["last_block_signature"] = signature
        _save_state(cwd, state)
        reason = _build_block_reason(test_command, exit_code, output)
    if undeclared_ids:
        names = ", ".join(sorted(undeclared_ids))
        reason = (
            f"Undeclared failing test(s) (not covered by any in-flight "
            f"contract declared for this session): {names}\n\n{reason}"
        )
    return reason


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

        # Tree-fingerprint cache: if the working tree is IDENTICAL to the
        # last time this session checked, reuse that exact decision
        # without running test_command again. fingerprint is None when it
        # cannot be computed at all (not a git repo, git failure) -- that
        # case can never match a stored (also-None-guarded) fingerprint,
        # so it always falls through to a real run below (D2: never skip
        # the check on doubt). See _compute_tree_fingerprint().
        fingerprint = _compute_tree_fingerprint(cwd)
        state = _load_state(cwd, session_id)
        cached_decision = state.get("cached_decision")
        if (
            fingerprint is not None
            and state.get("tree_fingerprint") == fingerprint
            and isinstance(cached_decision, dict)
            and cached_decision.get("decision") in ("allow", "block")
        ):
            if cached_decision["decision"] == "block":
                json.dump(
                    {"decision": "block", "reason": cached_decision.get("reason", "")},
                    sys.stdout,
                )
                sys.stdout.flush()
            sys.exit(0)

        # TRUST ASSUMPTION: test_command is executed as a subprocess with the
        # privileges of the current process. The file .claude/project-memory/config.json
        # must only contain commands from trusted sources (repo authors). It is NOT
        # sandboxed — do not place commands from untrusted or user-supplied input here.
        passed, exit_code, output = _run_test_command(test_command)

        # Declared in-flight contracts (Caso 17): a real run just told us
        # exactly which node ids are currently failing (empty set when
        # exit_code == 0, since nothing failed) -- any previously declared
        # id no longer in that set has turned green, drop it. Only on a
        # REAL run (never on the cached-decision-reuse path above, which
        # never reaches here at all).
        if exit_code == 0:
            _clear_resolved_declarations(cwd, session_id, set())
            failing_ids: set[str] | None = set()
        elif exit_code == 1:
            failing_ids = _extract_failed_node_ids(output)
            # A declared collection-ERROR file (see _classify_declared_reds()
            # docstring) can appear in the SAME exit_code == 1 run
            # alongside real FAILED node ids -- its file must also be
            # checked, or a still-red declared file gets wrongly cleared
            # the moment an unrelated FAILED test shares the run.
            _clear_resolved_declarations(
                cwd, session_id, failing_ids, _extract_collection_error_files(output)
            )
        else:
            failing_ids = None

        if passed:
            # Allow — no output needed (implicit allow).
            _save_decision(cwd, session_id, fingerprint, {"decision": "allow"})
            sys.exit(0)

        if _handle_nonzero_exit(cwd, session_id, exit_code, output, failing_ids):
            # Classified as safe to allow (empty suite, or every missing
            # module is "never written") — no block, warnings already emitted.
            _save_decision(cwd, session_id, fingerprint, {"decision": "allow"})
            sys.exit(0)

        # Block. When exit_code == 1 (or 2) AND there's an active
        # declaration for this session, name any undeclared red(s)
        # explicitly (Caso 17, requisito 3) -- a mix of declared and
        # undeclared always blocks, and the reason must not rely on the
        # generic 500-char output snippet happening to still contain it.
        # With NO declaration at all (requisito 5: nothing changes),
        # leave this None -- every current red is trivially "undeclared"
        # in that case, and prepending a note over that would be new
        # noise on the pre-existing, unrelated baseline block path.
        undeclared_ids = None
        if exit_code == 1 and failing_ids is not None:
            declared_ids = _declared_ids(cwd, session_id)
            if declared_ids:
                # Same combined match _classify_declared_reds() uses --
                # a mix of real FAILED node ids and collection ERROR
                # files can both be present in one exit_code == 1 run.
                errored_files_for_reason = _extract_collection_error_files(output)
                declared_files = {nid.partition("::")[0] for nid in declared_ids}
                undeclared_ids = (failing_ids - declared_ids) | (
                    errored_files_for_reason - declared_files
                )
        elif exit_code == 2:
            errored_files = _extract_collection_error_files(output)
            if errored_files:
                declared_files = _declared_files(cwd, session_id)
                if declared_files:
                    undeclared_ids = errored_files - declared_files
        reason = _build_block_reason_deduped(
            cwd, session_id, test_command, exit_code, output, undeclared_ids
        )
        _save_decision(cwd, session_id, fingerprint, {"decision": "block", "reason": reason})
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
