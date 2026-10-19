"""Reading a Bash command for hooks/pre-merge-gate.py: its git calls, where
each one runs, and which branches a merge/pull receives and brings in.

This module only reads; the verdict (approve / light / heavy gate) stays in
the hook. Everything here is fail-closed: any ambiguity or subprocess error
leaves the answer unknown (None, or "runs elsewhere"), and the hook gives an
unknown target the staging gate.
"""

import functools
import os
import re
import shlex

from git_bash_path import native_path
from git_helpers import run_git

_SHELL_PUNCTUATION = "();<>|&\n"

# `cd` / `pushd` / `popd` before a merge: it may run in another repository or
# worktree, whose branch the hook does not read — unless it resolves to the
# session repo's own top-level (D-129).
_DIR_CHANGERS = frozenset({"cd", "pushd", "popd"})

# git global options that point the call at another repository, and the ones
# that take a separate value; both appear between `git` and the subcommand.
_GIT_REPO_OPTIONS = ("-C", "--git-dir", "--work-tree")
_GIT_VALUE_OPTIONS = _GIT_REPO_OPTIONS + ("-c", "--namespace", "--config-env")


# ── Tokenizing ──────────────────────────────────────────────────────────────

def _is_separator(tok: str) -> bool:
    return bool(tok) and all(ch in _SHELL_PUNCTUATION for ch in tok)


def _clean_separator(tok: str) -> str:
    """An unquoted newline ends a command like `;`. Glued to another operator
    (`&&` at the end of a line) it is only the line break: keep the operator."""
    if "\n" in tok and _is_separator(tok):
        return tok.replace("\n", "") or "\n"
    return tok


def tokenize(normalized: str):
    """Split the command into shell words, with `&&`, `;`, `|`, newline... as
    their own tokens even when glued to a word (`dev&&git`). Redirections
    (`2>&1`, `>/dev/null`, `<<'EOF'`) are dropped with their target: they
    belong to the command they follow, they do not end it. Returns None on
    any tokenization failure (unbalanced quotes, etc.) — callers fail closed."""
    try:
        text = _FD_BEFORE_REDIRECT_RE.sub(r"\1", normalized)
        lexer = shlex.shlex(text, posix=True, punctuation_chars=_SHELL_PUNCTUATION)
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        lexer.commenters = ""
        return _drop_redirections([_clean_separator(tok) for tok in lexer])
    except ValueError:
        return None


# A file-descriptor number glued in front of a redirection (`2>`, `2>&1`).
_FD_BEFORE_REDIRECT_RE = re.compile(r"(^|[\s;&|()])\d+(?=[<>])")

# Redirection operators as the lexer groups them; each takes the next word as
# its target (a file, an fd, a heredoc delimiter, a here-string).
_REDIRECTIONS = frozenset({">", ">>", ">|", ">&", "&>", "&>>", "<", "<>", "<&", "<<", "<<<"})


def _drop_redirections(tokens):
    """tokens without redirection operators and their targets. An operator
    glued to `;`, `&&`, `(`... is not in the set and stays a separator."""
    kept, skip_target = [], False
    for tok in tokens:
        if skip_target:
            skip_target = False
            if not _is_separator(tok):
                continue
        if tok in _REDIRECTIONS:
            skip_target = True
            continue
        kept.append(tok)
    return kept


# ── Heredocs ────────────────────────────────────────────────────────────────

# `<<EOF`, `<<'EOF'`, `<<"EOF"`, `<<\EOF`, `<<-EOF`; not the here-string `<<<`.
_HEREDOC_RE = re.compile(
    r"(?<!<)<<(?!<)(-?)[ \t]*(?:'([^'\n]*)'|\"([^\"\n]*)\"|\\?([\w.\-]+))"
)


def _heredoc_end(lines, start, delimiter, strip_tabs):
    """Index of the line that closes the heredoc body starting at start, or
    None when no line closes it."""
    for j in range(start, len(lines)):
        line = lines[j].rstrip("\r")
        if (line.lstrip("\t") if strip_tabs else line) == delimiter:
            return j
    return None


def strip_heredoc_bodies(text: str) -> str:
    """text without the body and closing line of every heredoc: the body is
    data, never a command. The line that opens it stays. When a delimiter is
    never closed, text is returned unchanged (fail closed: nothing hidden)."""
    lines = text.split("\n")
    kept, i = [], 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        i += 1
        for match in _HEREDOC_RE.finditer(line):
            delimiter = next(g for g in match.group(2, 3, 4) if g is not None)
            end = _heredoc_end(lines, i, delimiter, bool(match.group(1)))
            if end is None:
                return text
            i = end + 1
    return "\n".join(kept)


def args_after(tokens, sub):
    """All tokens after the subcommand at index sub, up to the next separator."""
    args = []
    for tok in tokens[sub + 1:]:
        if _is_separator(tok):
            break
        args.append(tok)
    return args


# ── Git calls ───────────────────────────────────────────────────────────────

def _is_git(tok: str) -> bool:
    name = tok.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name in ("git", "git.exe")


def _scan_global_options(tokens, j):
    """Walk git's global options starting at index j. Returns (index of the
    first token after them, paths): paths is the tuple of `-C` values in
    order, or None once `--git-dir` / `--work-tree` or an unreadable `-C`
    (`-C=x`, or a `-C` after one of those) point the call elsewhere."""
    paths = []
    while j < len(tokens) and tokens[j].startswith("-") and not _is_separator(tokens[j]):
        option = tokens[j].split("=", 1)[0]
        takes_next = option in _GIT_VALUE_OPTIONS and "=" not in tokens[j]
        if option == "-C" and takes_next and j + 1 < len(tokens) and paths is not None:
            paths.append(tokens[j + 1])
        elif option in _GIT_REPO_OPTIONS:
            paths = None
        j += 2 if takes_next else 1
    return j, None if paths is None else tuple(paths)


def git_calls(tokens):
    """(subcommand index, subcommand, paths) for every git call. paths is the
    tuple of its `-C` values in order (empty when it has none), or None when
    `--git-dir` / `--work-tree` or an unreadable `-C` point it elsewhere."""
    calls = []
    for i, tok in enumerate(tokens):
        if not _is_git(tok):
            continue
        j, paths = _scan_global_options(tokens, i + 1)
        if j < len(tokens) and not _is_separator(tokens[j]):
            calls.append((j, tokens[j].lower(), paths))
    return calls


# ── Where a call runs (D-129) ───────────────────────────────────────────────

@functools.lru_cache(maxsize=None)
def toplevel(path):
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
    return os.path.join(base, native_path(path))


def _shell_dir(tokens, index, cwd, session_top):
    """The directory the shell is in at token index, after every `cd` /
    `pushd` before it. None when one of them is unreadable (`popd`, no or
    several arguments) or lands outside the session repo's top-level."""
    here = cwd
    for i, tok in enumerate(tokens[:index]):
        if tok not in _DIR_CHANGERS:
            continue
        args = args_after(tokens, i)
        if tok == "popd" or len(args) != 1:
            return None
        here = _join_path(here, args[0])
        if here is None or toplevel(here) != session_top:
            return None
    return here


def runs_elsewhere(tokens, sub, paths, cwd, session_top):
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
    return bool(paths) and toplevel(here) != session_top


# ── Branches: the one that receives, the one that comes in ──────────────────

def _current_branch(cwd):
    """Return the current branch name, or None if it cannot be determined
    (not a git repo, detached HEAD, git missing, etc.)."""
    rc, out = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    if rc != 0 or not out or out == "HEAD":
        return None
    return out


def remotes(cwd):
    """Names of the configured remotes; empty when they cannot be read."""
    rc, out = run_git(["remote"], cwd=cwd)
    if rc != 0:
        return frozenset()
    return frozenset(line.strip() for line in out.splitlines() if line.strip())


def _strip_remote_prefix(ref: str, remote_names) -> str:
    """'origin/main' -> 'main' when `origin` is a configured remote. A local
    branch with a slash (`feat/main`) is left whole."""
    for remote in sorted(remote_names, key=len, reverse=True):
        if ref.startswith(remote + "/"):
            return ref[len(remote) + 1:]
    return ref


def _upstream_branch(cwd, branch, remote_names):
    """Return the upstream branch name of `branch` (the current branch when
    empty), remote prefix stripped, or None if there is no tracked upstream."""
    rc, out = run_git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", f"{branch}@{{u}}"],
        cwd=cwd,
    )
    if rc != 0 or not out:
        return None
    return _strip_remote_prefix(out, remote_names)


def _switch_destination(args):
    """The branch a `git switch` / `git checkout` lands on, or None when it
    cannot be read with certainty (detach, path checkout, `-`, start point,
    `--track origin/x`, which names the remote ref, not the local branch)."""
    if any(a in ("--", "--detach", "-d", "-t") or a.startswith("--track") for a in args):
        return None
    positional = [a for a in args if not a.startswith("-")]
    return positional[0] if len(positional) == 1 else None


def target_branch(tokens, calls, op, cwd):
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
    return _switch_destination(args_after(tokens, sw))


def incoming_branch(sub, args, cwd, target, remote_names):
    """The branch being merged in, or None when it cannot be read."""
    if sub == "pull":
        if len(args) >= 2:
            return args[1]
        return _upstream_branch(cwd, target, remote_names)
    if not args:
        return None
    return _strip_remote_prefix(args[0], remote_names)
