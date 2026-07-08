#!/usr/bin/env python3
"""PreToolUse hook: block git merge / git pull and require Cerberus + Alexandria review first.

Intercepts Bash tool calls that contain a `git merge` or `git pull` command
(excluding `git merge --abort`, `git merge --continue`, and `git pull --rebase`,
which do not create a merge commit). Also intercepts eval/bash-c/sh-c
variable-indirection patterns that reference git or merge.

When detected, blocks and instructs the orchestrator to run Cerberus and
Alexandria in parallel before retrying.
"""

import json
import os
import re
import shlex
import sys

# ── Path setup — lib/ must be importable ────────────────────────────────

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(os.path.dirname(_HOOKS_DIR), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from encoding_guard import force_utf8_streams  # noqa: E402  (import after sys.path mutation)
force_utf8_streams()

from git_helpers import run_git  # noqa: E402  (import after sys.path mutation)

_STDIN_READ_LIMIT = 1_048_576  # 1 MiB

# Matches `git merge` (with optional .exe, case-insensitive).
# Exempt check is done separately — see _GIT_MERGE_EXEMPT_RE below.
_GIT_MERGE_RE = re.compile(
    r'\bgit(\.exe)?\s+merge\b',
    re.IGNORECASE,
)

# Exempt: --abort or --continue anywhere after `git merge` in the command.
_GIT_MERGE_EXEMPT_RE = re.compile(
    r'\bgit(\.exe)?\s+merge\b.*?\s--(abort|continue)\b',
    re.IGNORECASE,
)

# Matches `git pull` without --rebase (pull triggers an implicit merge).
# Negative lookahead for --rebase so `git pull --rebase` is allowed through.
_GIT_PULL_RE = re.compile(
    r'\bgit(\.exe)?\s+pull\b(?!.*--rebase\b)',
    re.IGNORECASE,
)

# Matches variable-indirection patterns: eval / bash -c / sh -c that also
# reference 'git' or 'merge' somewhere in the command — indirect merge bypass.
_EVAL_INDIRECTION_RE = re.compile(
    r'\b(eval|bash\s+-c|sh\s+-c)\b',
    re.IGNORECASE,
)

# Control characters and null bytes to strip before matching.
_CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def _normalize(command: str) -> str:
    """Strip null bytes and control characters from command before matching."""
    return _CONTROL_CHARS_RE.sub('', command)


# ── Branch-awareness (same-branch sync exemption) ───────────────────────────
#
# The review gate exists to catch integration of a DIFFERENT branch's new
# work (e.g. `git merge feature/x`), not a plain same-branch catch-up sync
# (e.g. `git pull origin main` while sitting on `main`). Everything below is
# fail-closed: any ambiguity or subprocess error means "not exempt" — the
# existing block-and-require-review behavior always applies.

def _strip_remote_prefix(ref: str) -> str:
    """Strip a leading remote-name path segment, e.g. 'origin/main' -> 'main'."""
    if "/" in ref:
        return ref.split("/", 1)[1]
    return ref


def _extract_positional_args(normalized: str, keyword: str):
    """Return non-flag tokens following `git <keyword>` in the command,
    stopping at shell metacharacters (&&, ||, ;, |). Returns [] on any
    tokenization failure (unbalanced quotes, etc.) — caller treats that as
    "no target found", which fails closed."""
    try:
        tokens = shlex.split(normalized)
    except ValueError:
        return []

    n = len(tokens)
    for i in range(n - 1):
        if tokens[i].lower() in ("git", "git.exe") and tokens[i + 1].lower() == keyword:
            args = []
            j = i + 2
            while j < n:
                tok = tokens[j]
                if tok in ("&&", "||", ";", "|"):
                    break
                if not tok.startswith("-"):
                    args.append(tok)
                j += 1
            return args
    return []


def _current_branch(cwd):
    """Return the current branch name, or None if it cannot be determined
    (not a git repo, detached HEAD, git missing, etc.)."""
    rc, out = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    if rc != 0 or not out or out == "HEAD":
        return None
    return out


def _upstream_branch(cwd):
    """Return the current branch's upstream branch name (remote prefix
    stripped), or None if there is no tracked upstream."""
    rc, out = run_git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        cwd=cwd,
    )
    if rc != 0 or not out:
        return None
    return _strip_remote_prefix(out)


def _is_same_branch_exempt(kind: str, normalized: str, cwd: str) -> bool:
    """True only if this merge/pull command targets the SAME branch as the
    current branch (a catch-up sync, not integration of foreign work).

    Fails closed: any error, ambiguity, or unresolved target -> False.
    """
    try:
        current = _current_branch(cwd)
        if not current:
            return False

        if kind == "pull":
            args = _extract_positional_args(normalized, "pull")
            if len(args) >= 2:
                target = args[1]
            else:
                target = _upstream_branch(cwd)
        elif kind == "merge":
            args = _extract_positional_args(normalized, "merge")
            if not args:
                return False
            target = _strip_remote_prefix(args[0])
        else:
            return False

        if not target:
            return False
        return target == current
    except Exception:
        return False


MERGE_GATE_MESSAGE = (
    "MERGE GATE (blocked command: {cmd!r}): Before merging, launch in parallel: "
    "(1) Cerberus in commit-review mode on the merge diff, "
    "(2) Alexandria in merge mode for changelog + CLAUDE.md check. "
    "If Cerberus has 0 blocking issues, retry the merge. "
    "If there are issues, show them to the user. "
    "After reviews pass with 0 blocking issues, retry the merge with "
    "`# merge-reviewed` appended to the command."
)

INDIRECTION_GATE_MESSAGE = (
    "MERGE GATE (blocked command: {cmd!r}): Command uses eval/bash-c/sh-c with "
    "'git' or 'merge' present — possible variable-indirection bypass. "
    "Run the git merge directly (not via eval/sh) so the hook can inspect it. "
    "If this is a false positive, remove the eval wrapper and retry."
)


def main():
    try:
        raw = sys.stdin.read(_STDIN_READ_LIMIT)
        hook_input = json.loads(raw)
        tool_name = hook_input.get("tool_name", "")
        tool_input = hook_input.get("tool_input") or {}

        # Only act on Bash calls.
        if tool_name != "Bash":
            json.dump({"decision": "approve"}, sys.stdout)
            sys.stdout.flush()
            return

        command = tool_input.get("command", "")
        if not command:
            json.dump({"decision": "approve"}, sys.stdout)
            sys.stdout.flush()
            return

        # cwd for git subprocess calls: prefer an explicit `cwd` in the hook
        # payload (not provided by Claude Code today, but checked defensively
        # in case a future version adds it); fall back to the hook process's
        # own working directory otherwise.
        cwd = hook_input.get("cwd") or os.getcwd()

        normalized = _normalize(command)

        # POLICY CONTROL (not a security guarantee): '# merge-reviewed' is a
        # convention token that the orchestrator appends after running Cerberus
        # and Alexandria. It is intentionally forgeable — its purpose is to
        # enforce workflow discipline, not to provide a cryptographic proof that
        # review occurred. A malicious or mistaken actor can bypass it by adding
        # the token manually; that risk is accepted by design.
        # Bypass: orchestrator has already run reviews and signals approval.
        if '# merge-reviewed' in command:
            json.dump({
                "decision": "approve",
                "reason": "merge-reviewed bypass acknowledged"
            }, sys.stdout)
            sys.stdout.flush()
            return

        # Check for variable-indirection bypass first.
        if _EVAL_INDIRECTION_RE.search(normalized):
            lower = normalized.lower()
            if 'git' in lower or 'merge' in lower:
                json.dump({
                    "decision": "block",
                    "reason": INDIRECTION_GATE_MESSAGE.format(cmd=command)
                }, sys.stdout)
                sys.stdout.flush()
                return

        # Check git merge (exempt: --abort / --continue anywhere in command,
        # or merging your own same-named branch / remote-tracking counterpart).
        if _GIT_MERGE_RE.search(normalized) and not _GIT_MERGE_EXEMPT_RE.search(normalized):
            if _is_same_branch_exempt("merge", normalized, cwd):
                json.dump({"decision": "approve"}, sys.stdout)
                sys.stdout.flush()
                return
            json.dump({
                "decision": "block",
                "reason": MERGE_GATE_MESSAGE.format(cmd=command)
            }, sys.stdout)
            sys.stdout.flush()
            return

        # Check git pull without --rebase (implicit merge), exempt when the
        # pull target resolves to the same branch we're already on.
        if _GIT_PULL_RE.search(normalized):
            if _is_same_branch_exempt("pull", normalized, cwd):
                json.dump({"decision": "approve"}, sys.stdout)
                sys.stdout.flush()
                return
            json.dump({
                "decision": "block",
                "reason": MERGE_GATE_MESSAGE.format(cmd=command)
            }, sys.stdout)
            sys.stdout.flush()
            return

        json.dump({"decision": "approve"}, sys.stdout)
        sys.stdout.flush()

    except Exception as exc:
        # Fail closed on any unhandled error — never let a broken hook approve silently.
        try:
            json.dump({
                "decision": "block",
                "reason": (
                    f"BLOCKED: pre-merge-gate hook raised an unhandled error: {exc}. "
                    "Fix the hook or investigate the input before retrying."
                )
            }, sys.stdout)
            sys.stdout.flush()
        except Exception:
            pass


if __name__ == "__main__":
    main()
