#!/usr/bin/env python3
"""
Stop hook -- Definition of Done gate.

Opt-in hard brake on session close. Reads `.claude/git-memory-config.json`
from cwd; if the field `test_command` (non-empty string) is present, runs
that command before allowing the session to end.

- tests pass (exit 0)  → allow close (no output, or {"decision":"allow"})
- tests fail (exit ≠0) → BLOCK: stdout JSON {"decision":"block","reason":"..."}
- no test_command      → allow (opt-in, fail-safe)
- any infra error      → FAIL-OPEN: allow close, never trap the user

Security: test_command is always executed with shell=False via shlex.split().
This prevents metacharacter injection (;, &&, |, $(...)) even if the config
value contains them. (T1 requirement — see test_stop_dod_gate.py.)

Timeout: subprocess is capped at 60 s (TIMEOUT_SECONDS). A command that
exceeds this results in fail-open (TimeoutExpired is caught).

I/O contract (Stop hook):
  stdin:  JSON Stop event (ignored — we don't need any field from it)
  stdout: {"decision":"block","reason":"..."} when blocking; empty when allowing
  exit:   always 0
"""

import json
import os
import shlex
import subprocess
import sys
import traceback

TIMEOUT_SECONDS = 60
CONFIG_SUBPATH = os.path.join(".claude", "git-memory-config.json")


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


def _read_test_command(cwd: str) -> str | None:
    """Return test_command from .claude/git-memory-config.json, or None.

    Returns None on any error (missing file, parse error, wrong type,
    empty/null value) — all of which are treated as opt-out.
    """
    config_file = os.path.join(cwd, CONFIG_SUBPATH)
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    cmd = config.get("test_command")
    if not cmd or not isinstance(cmd, str):
        return None
    return cmd


def _run_test_command(test_command: str) -> tuple[bool, int, str]:
    """Execute test_command with shell=False.

    Returns (passed, exit_code, combined_output).
    passed is True only when exit code is exactly 0.
    On any infra error (FileNotFoundError, TimeoutExpired, OSError, etc.)
    returns (True, -1, "") so the caller treats it as fail-open.
    """
    try:
        args = _tokenize(test_command)
        result = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        combined = (result.stdout + result.stderr).strip()
        return result.returncode == 0, result.returncode, combined
    except subprocess.TimeoutExpired:
        return True, -1, ""  # fail-open
    except (FileNotFoundError, OSError, ValueError):
        return True, -1, ""  # fail-open


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


def main() -> None:
    """Entry point. Always exits 0. Blocks via stdout JSON, not exit code."""
    # Read stdin — we don't use it, but must not crash on bad input.
    try:
        sys.stdin.read()
    except Exception:
        pass

    cwd = os.getcwd()

    try:
        test_command = _read_test_command(cwd)
        if not test_command:
            # Opt-in not configured — allow silently.
            sys.exit(0)

        passed, exit_code, output = _run_test_command(test_command)

        if passed:
            # Allow — no output needed (implicit allow).
            sys.exit(0)

        # Block.
        reason = _build_block_reason(test_command, exit_code, output)
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
