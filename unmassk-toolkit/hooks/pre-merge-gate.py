#!/usr/bin/env python3
"""PreToolUse hook: gate git merge / git pull by the branch that RECEIVES it.

Intercepts Bash tool calls that contain `git merge` or `git pull` (also
`git -C <path> ...`). `git merge --abort`, `git merge --continue` and
`git pull --rebase` are left alone: they create no merge commit. EVERY other
merge/pull in the command is judged on its own, and the command is blocked if
any of them is. The target of each one is the branch the command switched to
before it (`git switch dev && git merge ...`), or else the current branch.

  - target is `dev`                       -> approve, no gate (D-119: flow
                                             already reviewed that work).
  - target syncs its own remote copy      -> approve (`git pull origin main`
                                             on main, `git merge origin/main`;
                                             only a configured remote counts).
  - target above dev (staging, main,
    master, production)                   -> block with the staging gate
                                             (D-120): Cerberus + Argus on the
                                             whole incoming diff, Alexandria on
                                             CHANGELOG + version, Bex's yes;
                                             the full suite is left to CI.
  - any other target (feature branches)   -> block, Cerberus + Alexandria.
  - target unknown (no repo, detached
    HEAD, unreadable switch, `cd` or
    `git -C` to another repo or worktree,
    hook failure)                         -> block with the staging gate: it
                                             may be staging (fail closed).

A `cd` / `git -C` that resolves to the session repo's own top-level (any
literal spelling — absolute, relative, trailing slash — or a subfolder of it)
is read as if it were not there (D-129). `~`, `$VAR`, backticks and globs
stay unknown by design: the hook does not expand what the shell would.

`# merge-reviewed` in the command approves after the reviews ran. eval /
bash -c / sh -c wrapping git or merge is always blocked: the target cannot be
read through the wrapper.
"""

import json
import os
import re
import sys

# ── Path setup — lib/ must be importable ────────────────────────────────

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(os.path.dirname(_HOOKS_DIR), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from encoding_guard import force_utf8_streams  # noqa: E402  (import after sys.path mutation)
force_utf8_streams()

from merge_gate_target import (  # noqa: E402  (import after sys.path mutation)
    args_after, git_calls, incoming_branch, remotes, runs_elsewhere,
    strip_heredoc_bodies, target_branch, tokenize, toplevel,
)

_STDIN_READ_LIMIT = 1_048_576  # 1 MiB

# Backstop only, for a command the tokenizer cannot parse (unbalanced quotes):
# its merge/pull words block with the light gate. A command that parses and
# holds no merge/pull call is approved, whatever its text mentions.
_GIT_MERGE_RE = re.compile(
    r'\bgit(\.exe)?\s+merge\b',
    re.IGNORECASE,
)

_GIT_MERGE_EXEMPT_RE = re.compile(
    r'\bgit(\.exe)?\s+merge\b.*?\s--(abort|continue)\b',
    re.IGNORECASE,
)

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


# ── Judging each merge/pull ────────────────────────────────────────────────
#
# Reading the command (git calls, where each runs, target and incoming
# branch) lives in lib/merge_gate_target.py; the verdict is decided here.
# Everything is fail-closed: an unknown target gets the staging gate.


def _is_exempt(sub: str, args) -> bool:
    """`git merge --abort/--continue` and `git pull --rebase` make no merge."""
    if sub == "merge":
        return any(a in ("--abort", "--continue") for a in args)
    return any(
        a == "--rebase" or (a.startswith("--rebase=") and a != "--rebase=false")
        for a in args
    )


# Branches that receive work only after it has passed through dev (D-120).
_DEV_BRANCH = "dev"
_ABOVE_DEV_BRANCHES = frozenset({"staging", "main", "master", "production"})


def _judge(tokens, calls, call, cwd, remote_names):
    """('approve' | 'light' | 'heavy', target) for one merge/pull call."""
    op, sub, other_repo = call
    target = None if other_repo else target_branch(tokens, calls, op, cwd)
    if not target:
        return "heavy", None
    args = [a for a in args_after(tokens, op) if not a.startswith("-")]
    if incoming_branch(sub, args, cwd, target, remote_names) == target:
        return "approve", target
    if target == _DEV_BRANCH:
        return "approve", target
    if target in _ABOVE_DEV_BRANCHES:
        return "heavy", target
    return "light", target


_RANK = {"approve": 0, "light": 1, "heavy": 2}
_UNKNOWN_TARGET = (
    "its target branch could not be read (another directory or repository, "
    "an unreadable switch, or no branch checked out), so it may be above dev"
)


def _heavy_reason(command: str, target):
    where = f"this lands on '{target}', above dev" if target else _UNKNOWN_TARGET
    return STAGING_GATE_MESSAGE.format(cmd=command, where=where)


def _gate_decision(normalized: str, cwd: str, command: str):
    """(decision, reason) for the whole command: every merge/pull in it is
    judged, and the strictest verdict wins. Fails closed: any error or unknown
    target -> block with the staging gate."""
    try:
        tokens = tokenize(normalized)
        if tokens is None:
            backstop = (_GIT_MERGE_RE.search(normalized)
                        and not _GIT_MERGE_EXEMPT_RE.search(normalized)) \
                or _GIT_PULL_RE.search(normalized)
            return ("block", MERGE_GATE_MESSAGE.format(cmd=command)) if backstop \
                else ("approve", None)
        raw_calls = git_calls(tokens)
        if not any(c[1] in ("merge", "pull") for c in raw_calls):
            return "approve", None
        session_top = toplevel(cwd)
        calls = [(sub, name, runs_elsewhere(tokens, sub, paths, cwd, session_top))
                 for sub, name, paths in raw_calls]
        ops = [c for c in calls if c[1] in ("merge", "pull")]
        remote_names = remotes(cwd)
        worst, worst_target = "approve", None
        for call in ops:
            if _is_exempt(call[1], args_after(tokens, call[0])):
                continue
            verdict, target = _judge(tokens, calls, call, cwd, remote_names)
            if _RANK[verdict] > _RANK[worst]:
                worst, worst_target = verdict, target
    except Exception as exc:
        return "block", (
            f"pre-merge-gate failed internally ({type(exc).__name__}: {exc}); "
            "the target is treated as unknown. " + _heavy_reason(command, None)
        )
    if worst == "heavy":
        return "block", _heavy_reason(command, worst_target)
    if worst == "light":
        return "block", MERGE_GATE_MESSAGE.format(cmd=command)
    return "approve", None


STAGING_GATE_MESSAGE = (
    "MERGE GATE (blocked command: {cmd!r}): {where}. "
    "Before merging, launch in parallel: "
    "(1) Cerberus and (2) Argus on the whole incoming diff, "
    "(3) Alexandria in merge mode checking CHANGELOG and version against that diff. "
    "Show the results to Bex and wait for the owner's yes. "
    "The full test suite is left to CI on push. "
    "After that, retry the merge with `# merge-reviewed` appended to the command."
)

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

        # A heredoc body is data: it is never read for git calls or wrappers.
        normalized = strip_heredoc_bodies(_normalize(command))

        # POLICY CONTROL (not a security guarantee): '# merge-reviewed' is a
        # convention token that the orchestrator appends after the reviews the
        # block message asked for (Cerberus + Alexandria; above dev also Argus
        # and the owner's yes). It is intentionally forgeable — its purpose is
        # to enforce workflow discipline, not to prove that review occurred.
        # A mistaken actor can bypass it by adding the token manually; that
        # risk is accepted by design.
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

        # Every git merge / git pull in the command, judged by its target.
        decision, reason = _gate_decision(normalized, cwd, command)
        result = {"decision": decision}
        if reason:
            result["reason"] = reason
        json.dump(result, sys.stdout)
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
