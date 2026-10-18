#!/usr/bin/env python3
"""PreToolUse hook: gate git merge / git pull by the branch that RECEIVES it.

Intercepts Bash tool calls that contain a `git merge` or `git pull` command
(excluding `git merge --abort`, `git merge --continue`, and `git pull --rebase`,
which do not create a merge commit). The target is the current branch, or the
branch the same command switches to first (`git switch dev && git merge ...`,
`git checkout staging && git merge ...`).

  - target is `dev`                       -> approve, no gate (D-119: flow
                                             already reviewed that work).
  - target syncs its own remote copy      -> approve (`git pull origin main`
                                             on main, `git merge origin/main`).
  - target above dev (staging, main,
    master, production)                   -> block with the staging gate
                                             (D-120): Cerberus + Argus on the
                                             whole incoming diff, Alexandria on
                                             CHANGELOG + version, Bex's yes;
                                             the full suite is left to CI.
  - any other target (feature branches)   -> block, Cerberus + Alexandria.
  - target unknown (no repo, detached
    HEAD, unreadable switch)              -> block (fail closed).

`# merge-reviewed` in the command approves after the reviews ran. eval /
bash -c / sh -c wrapping git or merge is always blocked: the target cannot be
read through the wrapper.
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


_SHELL_PUNCTUATION = set("();<>|&")


def _tokenize(normalized: str):
    """Split the command into shell words, with `&&`, `;`, `|`... as their own
    tokens even when glued to a word (`dev&&git`). Returns None on any
    tokenization failure (unbalanced quotes, etc.) — callers fail closed."""
    try:
        lexer = shlex.shlex(normalized, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return None


def _is_separator(tok: str) -> bool:
    return bool(tok) and all(ch in _SHELL_PUNCTUATION for ch in tok)


def _find_git_subcommands(tokens, keywords):
    """Indexes i where tokens[i] is `git` and tokens[i + 1] is in keywords."""
    return [
        i for i in range(len(tokens) - 1)
        if tokens[i].lower() in ("git", "git.exe") and tokens[i + 1].lower() in keywords
    ]


def _args_after(tokens, i):
    """All tokens after `git <sub>` at index i, up to the next separator."""
    args = []
    for tok in tokens[i + 2:]:
        if _is_separator(tok):
            break
        args.append(tok)
    return args


def _extract_positional_args(normalized: str, keyword: str):
    """Return non-flag tokens following the first `git <keyword>` in the
    command, stopping at shell separators. Returns [] on any tokenization
    failure — caller treats that as "no target found", which fails closed."""
    tokens = _tokenize(normalized)
    if not tokens:
        return []
    found = _find_git_subcommands(tokens, (keyword,))
    if not found:
        return []
    return [tok for tok in _args_after(tokens, found[0]) if not tok.startswith("-")]


def _current_branch(cwd):
    """Return the current branch name, or None if it cannot be determined
    (not a git repo, detached HEAD, git missing, etc.)."""
    rc, out = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    if rc != 0 or not out or out == "HEAD":
        return None
    return out


def _upstream_branch(cwd, branch=""):
    """Return the upstream branch name of `branch` (the current branch when
    empty), remote prefix stripped, or None if there is no tracked upstream."""
    rc, out = run_git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", f"{branch}@{{u}}"],
        cwd=cwd,
    )
    if rc != 0 or not out:
        return None
    return _strip_remote_prefix(out)


# Branches that receive work only after it has passed through dev (D-120).
_DEV_BRANCH = "dev"
_ABOVE_DEV_BRANCHES = frozenset({"staging", "main", "master", "production"})


def _switch_destination(args):
    """The branch a `git switch` / `git checkout` lands on, or None when it
    cannot be read with certainty (detach, path checkout, `-`, start point)."""
    if any(a in ("--", "--detach", "-d") for a in args):
        return None
    positional = [a for a in args if not a.startswith("-")]
    return positional[0] if len(positional) == 1 else None


def _target_branch(kind: str, normalized: str, cwd: str):
    """The branch that RECEIVES this merge/pull: the branch the command
    switches to before it, or else the current branch. None when unknown.

    A switch counts only when every separator between it and the merge is
    `&&` — with `;` or `||` the merge may run on the original HEAD."""
    tokens = _tokenize(normalized)
    if not tokens:
        return None
    ops = _find_git_subcommands(tokens, (kind,))
    if not ops:
        return None
    op = ops[0]
    switches = [i for i in _find_git_subcommands(tokens, ("switch", "checkout")) if i < op]
    if not switches:
        return _current_branch(cwd)
    sw = switches[-1]
    if any(_is_separator(t) and t != "&&" for t in tokens[sw:op]):
        return None
    return _switch_destination(_args_after(tokens, sw))


def _incoming_branch(kind: str, normalized: str, cwd: str, target: str):
    """The branch being merged in, or None when it cannot be read."""
    if kind == "pull":
        args = _extract_positional_args(normalized, "pull")
        if len(args) >= 2:
            return args[1]
        return _upstream_branch(cwd, target)
    args = _extract_positional_args(normalized, "merge")
    if not args:
        return None
    return _strip_remote_prefix(args[0])


def _gate_decision(kind: str, normalized: str, cwd: str, command: str):
    """(decision, reason) for a merge/pull. Fails closed: any error or
    unknown target -> block with the review message."""
    try:
        target = _target_branch(kind, normalized, cwd)
        if not target:
            return "block", MERGE_GATE_MESSAGE.format(cmd=command)
        if _incoming_branch(kind, normalized, cwd, target) == target:
            return "approve", None
        if target == _DEV_BRANCH:
            return "approve", None
        if target in _ABOVE_DEV_BRANCHES:
            return "block", STAGING_GATE_MESSAGE.format(cmd=command, target=target)
    except Exception:
        pass
    return "block", MERGE_GATE_MESSAGE.format(cmd=command)


STAGING_GATE_MESSAGE = (
    "MERGE GATE (blocked command: {cmd!r}): this lands on '{target}', above dev. "
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

        # git merge (exempt: --abort / --continue anywhere in the command) and
        # git pull without --rebase (implicit merge): decided by the target.
        kind = None
        if _GIT_MERGE_RE.search(normalized) and not _GIT_MERGE_EXEMPT_RE.search(normalized):
            kind = "merge"
        elif _GIT_PULL_RE.search(normalized):
            kind = "pull"
        if kind:
            decision, reason = _gate_decision(kind, normalized, cwd, command)
            result = {"decision": decision}
            if reason:
                result["reason"] = reason
            json.dump(result, sys.stdout)
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
