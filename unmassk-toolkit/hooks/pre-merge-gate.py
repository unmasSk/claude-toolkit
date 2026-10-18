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
spelling, or a subfolder of it) is read as if it were not there (D-129).

`# merge-reviewed` in the command approves after the reviews ran. eval /
bash -c / sh -c wrapping git or merge is always blocked: the target cannot be
read through the wrapper.
"""

import functools
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

# Backstop only: merge/pull words the tokenizer could not place as a git call
# (unbalanced quotes, `git merge` inside a quoted string) still block.
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


# ── Reading the command: git calls, switches, targets ───────────────────────
#
# Everything below is fail-closed: any ambiguity or subprocess error leaves
# the target unknown, and an unknown target gets the staging gate.

_SHELL_PUNCTUATION = "();<>|&\n"

# `cd` / `pushd` / `popd` before a merge: it may run in another repository or
# worktree, whose branch this hook does not read — unless it resolves to the
# session repo's own top-level (D-129).
_DIR_CHANGERS = frozenset({"cd", "pushd", "popd"})

# git global options that point the call at another repository, and the ones
# that take a separate value; both appear between `git` and the subcommand.
_GIT_REPO_OPTIONS = ("-C", "--git-dir", "--work-tree")
_GIT_VALUE_OPTIONS = _GIT_REPO_OPTIONS + ("-c", "--namespace", "--config-env")


def _is_separator(tok: str) -> bool:
    return bool(tok) and all(ch in _SHELL_PUNCTUATION for ch in tok)


def _clean_separator(tok: str) -> str:
    """An unquoted newline ends a command like `;`. Glued to another operator
    (`&&` at the end of a line) it is only the line break: keep the operator."""
    if "\n" in tok and _is_separator(tok):
        return tok.replace("\n", "") or "\n"
    return tok


def _tokenize(normalized: str):
    """Split the command into shell words, with `&&`, `;`, `|`, newline... as
    their own tokens even when glued to a word (`dev&&git`). Returns None on
    any tokenization failure (unbalanced quotes, etc.) — callers fail closed."""
    try:
        lexer = shlex.shlex(normalized, posix=True, punctuation_chars=_SHELL_PUNCTUATION)
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        lexer.commenters = ""
        return [_clean_separator(tok) for tok in lexer]
    except ValueError:
        return None


def _is_git(tok: str) -> bool:
    name = tok.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name in ("git", "git.exe")


def _git_calls(tokens):
    """(subcommand index, subcommand, paths) for every git call. paths is the
    tuple of its `-C` values in order (empty when it has none), or None when
    `--git-dir` / `--work-tree` or an unreadable `-C` point it elsewhere."""
    calls = []
    for i, tok in enumerate(tokens):
        if not _is_git(tok):
            continue
        j, paths = i + 1, []
        while j < len(tokens) and tokens[j].startswith("-") and not _is_separator(tokens[j]):
            option = tokens[j].split("=", 1)[0]
            takes_next = option in _GIT_VALUE_OPTIONS and "=" not in tokens[j]
            if option == "-C" and takes_next and j + 1 < len(tokens) and paths is not None:
                paths.append(tokens[j + 1])
            elif option in _GIT_REPO_OPTIONS:
                paths = None
            j += 2 if takes_next else 1
        if j < len(tokens) and not _is_separator(tokens[j]):
            calls.append((j, tokens[j].lower(), None if paths is None else tuple(paths)))
    return calls


@functools.lru_cache(maxsize=None)
def _toplevel(path):
    """Resolved top-level directory of the repository or worktree at path, or
    None when it cannot be read (not a repo, missing directory, git error)."""
    rc, out = run_git(["rev-parse", "--show-toplevel"], cwd=path)
    if rc != 0 or not out:
        return None
    return os.path.normcase(os.path.realpath(out))


def _join_path(base, path):
    """base joined with a literal path, or None when it cannot be read: no
    base, an option (`cd -`, `cd -P`), or anything the shell would rewrite
    (`~`, `$VAR`, backticks, globs)."""
    if base is None or not path or path.startswith("-") or any(c in path for c in "~$`*?["):
        return None
    return os.path.join(base, path)


def _shell_dir(tokens, index, cwd, session_top):
    """The directory the shell is in at token index, after every `cd` /
    `pushd` before it. None when one of them is unreadable (`popd`, no or
    several arguments) or lands outside the session repo's top-level."""
    here = cwd
    for i, tok in enumerate(tokens[:index]):
        if tok not in _DIR_CHANGERS:
            continue
        args = _args_after(tokens, i)
        if tok == "popd" or len(args) != 1:
            return None
        here = _join_path(here, args[0])
        if here is None or _toplevel(here) != session_top:
            return None
    return here


def _runs_elsewhere(tokens, sub, paths, cwd, session_top):
    """True unless the git call whose subcommand is at index sub runs in the
    session repo's own top-level (D-129): every `cd` before it and its `-C`
    paths resolve there. Another repo, another worktree of the same repo, or
    anything unreadable counts as elsewhere (fail closed)."""
    if paths is None or session_top is None:
        return True
    here = _shell_dir(tokens, sub, cwd, session_top)
    for path in paths:
        here = _join_path(here, path)
    if here is None:
        return True
    return bool(paths) and _toplevel(here) != session_top


def _args_after(tokens, sub):
    """All tokens after the subcommand at index sub, up to the next separator."""
    args = []
    for tok in tokens[sub + 1:]:
        if _is_separator(tok):
            break
        args.append(tok)
    return args


def _is_exempt(sub: str, args) -> bool:
    """`git merge --abort/--continue` and `git pull --rebase` make no merge."""
    if sub == "merge":
        return any(a in ("--abort", "--continue") for a in args)
    return any(
        a == "--rebase" or (a.startswith("--rebase=") and a != "--rebase=false")
        for a in args
    )


def _current_branch(cwd):
    """Return the current branch name, or None if it cannot be determined
    (not a git repo, detached HEAD, git missing, etc.)."""
    rc, out = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    if rc != 0 or not out or out == "HEAD":
        return None
    return out


def _remotes(cwd):
    """Names of the configured remotes; empty when they cannot be read."""
    rc, out = run_git(["remote"], cwd=cwd)
    if rc != 0:
        return frozenset()
    return frozenset(line.strip() for line in out.splitlines() if line.strip())


def _strip_remote_prefix(ref: str, remotes) -> str:
    """'origin/main' -> 'main' when `origin` is a configured remote. A local
    branch with a slash (`feat/main`) is left whole."""
    for remote in sorted(remotes, key=len, reverse=True):
        if ref.startswith(remote + "/"):
            return ref[len(remote) + 1:]
    return ref


def _upstream_branch(cwd, branch, remotes):
    """Return the upstream branch name of `branch` (the current branch when
    empty), remote prefix stripped, or None if there is no tracked upstream."""
    rc, out = run_git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", f"{branch}@{{u}}"],
        cwd=cwd,
    )
    if rc != 0 or not out:
        return None
    return _strip_remote_prefix(out, remotes)


# Branches that receive work only after it has passed through dev (D-120).
_DEV_BRANCH = "dev"
_ABOVE_DEV_BRANCHES = frozenset({"staging", "main", "master", "production"})


def _switch_destination(args):
    """The branch a `git switch` / `git checkout` lands on, or None when it
    cannot be read with certainty (detach, path checkout, `-`, start point,
    `--track origin/x`, which names the remote ref, not the local branch)."""
    if any(a in ("--", "--detach", "-d", "-t") or a.startswith("--track") for a in args):
        return None
    positional = [a for a in args if not a.startswith("-")]
    return positional[0] if len(positional) == 1 else None


def _target_branch(tokens, calls, op, cwd):
    """The branch that RECEIVES the merge/pull whose subcommand is at index
    op: the branch the command last switched to before it, or else the
    current branch. None when unknown.

    A switch counts only when every separator between it and the merge is
    `&&` — with `;`, `||` or a newline the merge may run on the original HEAD.
    A switch or merge run outside the session repo (other_repo) is unknown."""
    switches = [c for c in calls if c[0] < op and c[1] in ("switch", "checkout")]
    if not switches:
        return _current_branch(cwd)
    sw, _, other_repo = switches[-1]
    if other_repo or any(_is_separator(t) and t != "&&" for t in tokens[sw:op]):
        return None
    return _switch_destination(_args_after(tokens, sw))


def _incoming_branch(sub, args, cwd, target, remotes):
    """The branch being merged in, or None when it cannot be read."""
    if sub == "pull":
        if len(args) >= 2:
            return args[1]
        return _upstream_branch(cwd, target, remotes)
    if not args:
        return None
    return _strip_remote_prefix(args[0], remotes)


def _judge(tokens, calls, call, cwd, remotes):
    """('approve' | 'light' | 'heavy', target) for one merge/pull call."""
    op, sub, other_repo = call
    target = None if other_repo else _target_branch(tokens, calls, op, cwd)
    if not target:
        return "heavy", None
    args = [a for a in _args_after(tokens, op) if not a.startswith("-")]
    if _incoming_branch(sub, args, cwd, target, remotes) == target:
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
        tokens = _tokenize(normalized)
        raw_calls = _git_calls(tokens) if tokens else []
        ops = [c for c in raw_calls if c[1] in ("merge", "pull")]
        if not ops:
            backstop = (_GIT_MERGE_RE.search(normalized)
                        and not _GIT_MERGE_EXEMPT_RE.search(normalized)) \
                or _GIT_PULL_RE.search(normalized)
            return ("block", _heavy_reason(command, None)) if backstop else ("approve", None)
        session_top = _toplevel(cwd)
        calls = [(sub, name, _runs_elsewhere(tokens, sub, paths, cwd, session_top))
                 for sub, name, paths in raw_calls]
        ops = [c for c in calls if c[1] in ("merge", "pull")]
        remotes = _remotes(cwd)
        worst, worst_target = "approve", None
        for call in ops:
            if _is_exempt(call[1], _args_after(tokens, call[0])):
                continue
            verdict, target = _judge(tokens, calls, call, cwd, remotes)
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

        normalized = _normalize(command)

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
