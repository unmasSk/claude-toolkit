#!/usr/bin/env python3
"""
git-memory-commit — Pretty commit wrapper for git-memory.

Creates a git commit with proper emoji, type, scope, trailers,
and prints a single pretty line for the user.

Usage:
  git-memory-commit.py <type> <scope> <message> [--body TEXT] [--trailer KEY=VALUE]...
  git-memory-commit.py decision auth "usar JWT"
  git-memory-commit.py memo api "preference - siempre async/await" --trailer "Why=equipo lo prefiere"
  git-memory-commit.py feat forms "add date picker" --body "Full body text" --trailer "Why=users need dates"
  git-memory-commit.py context forms "validación completada" --trailer "Next=wire to API"
  git-memory-commit.py wip forms "half-done date picker"

Exit codes:
  0: Commit created
  1: Error
"""

import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from constants import MEMORY_TYPES, DEFAULT_CO_AUTHOR
from git_helpers import run_git, open_no_follow_symlink
from parsing import suggest_scope_from_paths, sanitize_trailer_value

# ── Config ───────────────────────────────────────────────────────────────

# Co-author line: configurable via env var, falls back to constant.
# Sanitise: strip everything from the first newline (CR or LF) onwards so
# a malicious value cannot inject extra trailers into the commit message.
def _sanitize_co_author(value: str) -> str:
    """Return the first line of value, stripped.

    If the result is empty or does not look like a valid Co-Authored-By
    trailer, fall back to DEFAULT_CO_AUTHOR.
    """
    # Keep only the text before the first CR or LF
    first_line = re.split(r"[\r\n]", value)[0].strip()
    # A valid trailer must match "Co-Authored-By: Name <email>" loosely
    if not re.match(r"(?i)co-authored-by:\s*\S", first_line):
        return DEFAULT_CO_AUTHOR
    return first_line

CO_AUTHOR = _sanitize_co_author(os.environ.get("GIT_MEMORY_CO_AUTHOR", DEFAULT_CO_AUTHOR))

EMOJIS = {
    "feat": "✨", "fix": "🐛", "refactor": "♻️", "perf": "⚡",
    "test": "🧪", "docs": "📝", "chore": "🔧", "ci": "👷",
    "wip": "🚧", "context": "💾", "decision": "🧭", "memo": "📌",
    "remember": "🧠",
}

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RED = "\033[91m"

CYAN = "\033[36m"

TYPE_COLORS = {
    "decision": YELLOW, "memo": BLUE, "context": GREEN,
    "remember": CYAN,
    "feat": MAGENTA, "fix": MAGENTA, "refactor": MAGENTA,
    "perf": MAGENTA, "test": MAGENTA, "docs": MAGENTA,
    "chore": MAGENTA, "ci": MAGENTA, "wip": DIM,
}


def _load_scope_map() -> dict[str, str]:
    """Load scope map from .claude/git-memory-scopes.json or agent-memory, flatten to {dir_prefix: scope_name}."""
    try:
        _, toplevel = run_git(["rev-parse", "--show-toplevel"])
        if not toplevel:
            return {}
        # Check primary location first, then agent-memory fallback
        scopes_file = os.path.join(toplevel, ".claude", "git-memory-scopes.json")
        if not os.path.isfile(scopes_file):
            # Search in agent-memory directories
            agent_mem = os.path.join(toplevel, ".claude", "agent-memory")
            if os.path.isdir(agent_mem):
                for agent_dir in os.listdir(agent_mem):
                    candidate = os.path.join(agent_mem, agent_dir, "scopes.json")
                    if os.path.isfile(candidate):
                        scopes_file = candidate
                        break
        if not os.path.isfile(scopes_file):
            return {}
        # SEC-MED-NEW-12: never follow a symlink planted at
        # git-memory-scopes.json.
        with open_no_follow_symlink(scopes_file, "r") as f:
            data = json.load(f)
        result: dict[str, str] = {}
        for scope_name, scope_info in data.get("scopes", {}).items():
            result[scope_name] = scope_name
        return result
    except (OSError, ValueError):
        return {}


def _suggest_scope(given_scope: str) -> None:
    """Print a hint if staged files suggest a more specific scope than what was given."""
    scope_map = _load_scope_map()
    if not scope_map:
        return
    code, output = run_git(["diff", "--cached", "--name-only"])
    if code != 0 or not output:
        return
    changed = [f for f in output.strip().splitlines() if f]
    if not changed:
        return
    suggested = suggest_scope_from_paths(changed, scope_map)
    if not suggested:
        return
    scope_base = given_scope.split("/")[0]
    if suggested != scope_base and suggested != given_scope:
        print(f"  {DIM}hint: files are in {suggested}/, consider scope '{suggested}' or '{suggested}/...'{RESET}",
              file=sys.stderr)


def _build_subject(type_: str, scope: str, message: str) -> str:
    """Build the commit subject line: '{emoji} {type}({scope}): {message}'."""
    emoji = EMOJIS.get(type_, "")
    return f"{emoji} {type_}({scope}): {message}"


# Trailer keys whose VALUE content is checked for an empty description
# before the commit is made. Both use the "category - description" shape;
# there is no importable category enum left to validate against (retired
# in 578177a, DEUDA.md #16), so only the description-emptiness half is
# restored here -- never re-add a hardcoded category list.
_TRAILER_CONTENT_KEYS: set[str] = {"Memo", "Remember"}


def _validate_trailer_content(key: str, value: str) -> str | None:
    """Validate the CONTENT of a Memo:/Remember: trailer value.

    Returns None if valid (or if `key` isn't one we content-validate), or a
    human-readable error string if the description is empty. Does NOT
    validate a category enum -- none exists in this codebase anymore (see
    DEUDA.md #16). Nothing else validates Memo:/Remember: content before
    this wrapper builds the commit (the PreToolUse hook only intercepts raw
    `git commit` Bash commands, never this wrapper's own in-process
    trailers).

    Validates the SANITIZED value, not the raw one -- build_commit_message()
    always runs sanitize_trailer_value() on every trailer value before it is
    written to the commit, so a description that looks non-empty in the raw
    string (e.g. a bare trailing dash, or a stray embedded newline plus
    spaces) but collapses to "" once sanitized must be rejected the same as
    an outright empty one.
    """
    if key not in _TRAILER_CONTENT_KEYS:
        return None

    sanitized = sanitize_trailer_value(value)
    _, sep, description = sanitized.partition(" - ")
    if not sep or not description.strip():
        return (
            f"empty {key} description: {sanitized!r}. "
            "Must be: 'category - description' with a non-empty description"
        )
    return None


def _check_trailer_content(trailers: list[str]) -> None:
    """Fail closed before the commit is built if any Memo:/Remember:
    trailer's description is empty (once sanitized).

    Runs BEFORE build_commit_message()/_do_commit() so an invalid trailer
    never reaches git: exit 2, clear stderr message naming the trailer and
    what's wrong with it, no commit created.
    """
    for t in trailers:
        key, _, value = t.partition("=")
        error = _validate_trailer_content(key, value)
        if error:
            print(f"{RED}{BOLD}Error{RESET}: {error}", file=sys.stderr)
            sys.exit(2)


def build_commit_message(type_: str, scope: str, message: str,
                         body: str | None, trailers: list[str]) -> str:
    """Build the full commit message with emoji, subject, body, trailers."""
    subject = _build_subject(type_, scope, message)

    parts = [subject]

    if body or trailers:
        parts.append("")  # blank line after subject

    if body:
        parts.append(body)

    if trailers:
        if body:
            parts.append("")  # blank line between body and trailers
        for t in trailers:
            key, _, value = t.partition("=")
            # BUG T1 fix: a raw CR/LF inside `value` (e.g. free text an
            # agent wrote with a real newline) would split this trailer
            # across multiple PHYSICAL lines, so only the first physical
            # line would ever be recognized as this trailer's value --
            # everything after the embedded newline is silently lost on
            # every future line-based read. sanitize_trailer_value()
            # (canonical, already used at read time) collapses any
            # embedded CR/LF/control byte to a single space instead of
            # truncating, so the full value always survives on ONE
            # physical line.
            # Collapse any resulting run of spaces (e.g. from a CRLF
            # pair producing two substitutions) so the value stays tidy.
            clean_value = re.sub(r" {2,}", " ", sanitize_trailer_value(value))
            parts.append(f"{key}: {clean_value}")

    # Co-author
    parts.append("")
    parts.append(CO_AUTHOR)

    return "\n".join(parts)


def _validate_path_args(paths: list[str], repo_real: str | None) -> None:
    """Valida que todos los --path queden dentro del repo root.

    Rechaza rutas con '..' explícito o que apunten fuera del root resuelto.
    Llama a sys.exit(1) si alguna ruta es inválida.
    """
    for p in paths:
        if ".." in p.replace("\\", "/").split("/"):
            print(f"{RED}{BOLD}Error{RESET}: path rechazado (contiene '..'): {p!r}", file=sys.stderr)
            sys.exit(1)
        if repo_real:
            abs_p = os.path.realpath(os.path.join(os.getcwd(), p))
            if not abs_p.startswith(repo_real + os.sep) and abs_p != repo_real:
                print(f"{RED}{BOLD}Error{RESET}: path fuera del repo: {p!r}", file=sys.stderr)
                sys.exit(1)


def _do_commit(type_: str, msg: str, paths: list[str]) -> subprocess.CompletedProcess:
    """Construye y ejecuta el comando git commit. Aborta con exit 1 ante fallos."""
    git_args = ["commit"]
    if type_ in MEMORY_TYPES:
        git_args.append("--allow-empty")
    git_args += ["-m", msg]
    # Pathspec explícito: cuando se pasan --path, el commit incluye SOLO esas rutas.
    # Sin --path: comportamiento original (commitea el índice completo).
    if paths:
        git_args += ["--"] + paths
    try:
        result = subprocess.run(
            ["git"] + git_args,
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as e:
        print(f"{RED}{BOLD}Error{RESET}: git commit failed: {e}", file=sys.stderr)
        sys.exit(1)
    if result.returncode != 0:
        print(f"{RED}{BOLD}Error{RESET}: git commit failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result


def _do_push() -> None:
    """Ejecuta git push. Aborta con exit 1 si falla."""
    try:
        push_result = subprocess.run(
            ["git", "push"],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as e:
        print(f"  {RED}push failed: {e}{RESET}", file=sys.stderr)
        sys.exit(1)
    if push_result.returncode == 0:
        print(f"  {DIM}↑ pushed{RESET}")
    else:
        print(f"  {RED}push failed: {push_result.stderr.strip()}{RESET}", file=sys.stderr)
        sys.exit(1)


def _print_commit_result(type_: str, scope: str, message: str,
                         result: subprocess.CompletedProcess) -> None:
    """Imprime la línea de confirmación del commit."""
    sha = "?"
    sha_match = re.search(r"\[\S+\s+([a-f0-9]+)\]", result.stdout)
    if sha_match:
        sha = sha_match.group(1)[:7]

    emoji = EMOJIS.get(type_, "")
    color = TYPE_COLORS.get(type_, RESET)
    print(f"  {emoji} {color}{BOLD}{type_}{RESET}{DIM}({scope}){RESET}: {message} {DIM}[{sha}]{RESET}")


def _build_arg_parser() -> argparse.ArgumentParser:
    """Construye y devuelve el parser de argumentos de la CLI."""
    parser = argparse.ArgumentParser(description="Pretty git commit for git-memory")
    parser.add_argument("type", help="Commit type (feat, fix, decision, memo, context, wip, ...)")
    parser.add_argument("scope", help="Scope (auth, api, forms, ...)")
    parser.add_argument("message", help="Commit message (subject line)")
    parser.add_argument("--body", default=None, help="Commit body text")
    parser.add_argument("--trailer", action="append", default=[], dest="trailers",
                        help="Trailer in KEY=VALUE format (repeatable)")
    parser.add_argument("--push", action="store_true", help="Push after commit")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        dest="paths",
        metavar="PATH",
        help="Explicit pathspec for the commit (repeatable). "
             "If paths are passed, only those enter the commit. "
             "Must stay inside the repo (no .. that escapes the root).",
    )
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()

    type_ = args.type
    if type_ not in EMOJIS:
        print(f"{RED}{BOLD}Error{RESET}: unknown type '{type_}'. Valid: {', '.join(sorted(EMOJIS))}", file=sys.stderr)
        sys.exit(1)

    # Validación de --path: deben quedar dentro del repo root
    if args.paths:
        try:
            _, toplevel = run_git(["rev-parse", "--show-toplevel"])
            repo_real = os.path.realpath(toplevel.strip()) if toplevel else None
        except OSError:
            # Expected failure mode only: os.path.realpath() can raise OSError
            # on some platforms/filesystem edge cases. run_git() itself never
            # raises (already collapses subprocess/OSError to (1, "")). A
            # different exception here (e.g. AttributeError from a future
            # refactor) would be a real bug and should surface, not be
            # silently treated as "no repo root available".
            repo_real = None
        _validate_path_args(args.paths, repo_real)

    # Scope suggestion from staged files (non-blocking hint)
    if type_ not in MEMORY_TYPES:
        _suggest_scope(args.scope)

    _check_trailer_content(args.trailers)

    msg = build_commit_message(type_, args.scope, args.message, args.body, args.trailers)
    result = _do_commit(type_, msg, args.paths)

    _print_commit_result(type_, args.scope, args.message, result)

    if args.push:
        _do_push()


if __name__ == "__main__":
    main()
