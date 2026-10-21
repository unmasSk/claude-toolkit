#!/usr/bin/env python3
"""PreToolUse/Bash commit gate ("customs"): checks commits with validator.py and blocks with the rejection text.

On once the project has a note, unless config.json sets customs_enabled. wip and session-close
commits pass; a note commit is validated; any other plain commit is sent to `gitmem work`;
`commit --amend` and a starting `rebase` are refused; merge, cherry-pick and rebase
--abort/--continue/--skip always pass. Answers JSON on stdout with exit code 0; any
unexpected error blocks.
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

# Make lib/ and lib/memory/ importable.

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(_HOOKS_DIR)
_LIB_DIR = os.path.join(_TOOLKIT_ROOT, "lib")
_LIB_MEMORY_DIR = os.path.join(_LIB_DIR, "memory")
for _dir in (_LIB_DIR, _LIB_MEMORY_DIR):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)

from utf8 import force_utf8_streams  # noqa: E402

force_utf8_streams()

import config  # noqa: E402
import format  # noqa: E402
import gitcmd  # noqa: E402
import indexes  # noqa: E402
import query  # noqa: E402
import rejection as rejection_  # noqa: E402
import save_command  # noqa: E402
import validator  # noqa: E402
import vocabulary  # noqa: E402
import zones as zones_lib  # noqa: E402
from git_bash_path import native_path  # noqa: E402

_STDIN_READ_LIMIT = 1_048_576  # 1 MiB

# Detection of commands that create a commit, by shell-token shape.

_GIT_PROGRAM_TOKEN_RE = re.compile(r"(?:^|/)git(?:\.exe)?$", re.IGNORECASE)
_GIT_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
_SHELL_STATEMENT_SEPARATORS = ("&&", "||", ";", "|")
_COMMIT_CREATING_SUBCOMMANDS = {"commit", "merge", "rebase", "cherry-pick"}

# Flags that continue or leave a rebase already started: they pass.
_REBASE_PASSTHROUGH_FLAGS = frozenset({"--abort", "--continue", "--skip"})

# The same flags on the raw string, for when shlex cannot tokenize; `\b` would not bound a `-`.
_RESCUE_FLAG_RE = re.compile(
    r"(?<![\w-])(?:"
    + "|".join(re.escape(f) for f in sorted(_REBASE_PASSTHROUGH_FLAGS))
    + r")(?![\w-])"
)


def _split_statements(tokens):
    """Split tokens into statements at shell separators."""
    statements = []
    current = []
    for tok in tokens:
        if tok in _SHELL_STATEMENT_SEPARATORS:
            statements.append(current)
            current = []
        else:
            current.append(tok)
    statements.append(current)
    return statements


def _shell_statements(command):
    """Tokenize `command` into statements; None when its quotes are unbalanced.

    punctuation_chars=True keeps `;`, `&&`, `||` and `|` separate even when glued to a word.
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = "#"
        tokens = list(lexer)
    except ValueError:
        return None
    return _split_statements(tokens)


def _find_commit_creating_statement(command):
    """`(subcommand, tokens_after_it, stmt_index)` for the first statement running git
    commit/merge/rebase/cherry-pick, or None.

    If `command` does not tokenize, a raw regex search is used instead: stmt_index is None,
    rescue flags (--abort/--continue/--skip) come back as the tokens, and when present
    rebase/merge/cherry-pick are tried first.
    """
    statements = _shell_statements(command)
    if statements is None:
        rescue_tokens = _RESCUE_FLAG_RE.findall(command)
        order = _COMMIT_CREATING_SUBCOMMANDS
        if rescue_tokens:
            order = ("rebase", "merge", "cherry-pick") + tuple(
                sub for sub in _COMMIT_CREATING_SUBCOMMANDS
                if sub not in ("rebase", "merge", "cherry-pick")
            )
        for sub in order:
            if re.search(rf"\bgit\b.*\b{re.escape(sub)}\b", command):
                return sub, rescue_tokens, None
        return None

    for stmt_index, statement in enumerate(statements):
        n = len(statement)
        for i, tok in enumerate(statement):
            if not _GIT_PROGRAM_TOKEN_RE.search(tok):
                continue
            j = i + 1
            while j < n and statement[j].startswith("-"):
                flag = statement[j]
                j += 1
                if flag in _GIT_VALUE_FLAGS and "=" not in flag and j < n:
                    j += 1
            if j >= n:
                continue
            sub = statement[j].lower()
            if sub not in _COMMIT_CREATING_SUBCOMMANDS:
                continue
            return sub, statement[j + 1:], stmt_index
    return None


def _resolve_effective_cwd(command, base_cwd, limit_index=None):
    """Directory the commit statement runs in: each `cd` before it, applied in order to `base_cwd`.

    Only statements before `limit_index` count. A `cd` to a non-directory is ignored, a bare `cd`
    goes to HOME, and on Windows a Git Bash path is converted to its native form.
    """
    statements = _shell_statements(command)
    if statements is None:
        return base_cwd
    if limit_index is not None:
        statements = statements[:limit_index]

    cwd = base_cwd
    for statement in statements:
        if not statement or statement[0] != "cd":
            continue
        raw_target = statement[1] if len(statement) > 1 else "~"
        target = os.path.expanduser(raw_target)
        target = native_path(target)
        candidate = target if os.path.isabs(target) else os.path.join(cwd, target)
        if os.path.isdir(candidate):
            cwd = os.path.normpath(candidate)
    return cwd


def _extract_dash_m_message(tokens):
    """Value of the first -m/--message, or None (heredoc, -F, or no message)."""
    for i, tok in enumerate(tokens):
        if tok in ("-m", "--message"):
            return tokens[i + 1] if i + 1 < len(tokens) else None
        if tok.startswith("--message="):
            return tok[len("--message="):]
    return None


# Rejections built here: they have no shared template.


def _non_note_commit_rejection():
    """Rejection for a plain `git commit` that is not wip, session close or a note."""
    what = (
        "esto crea un commit fuera de gitmem: un `git commit` cuyo "
        "mensaje no es una nota de memoria reconocible (ni una nota "
        "D/M/R/Q/X/I/B, ni wip, ni el cierre ⏩)"
    )
    options = (
        "La memoria es el registro de cada cosa que hacemos: con la aduana",
        "encendida, todo commit que use git directamente tiene que quedar",
        "registrado -- que se toco y a que issue iba",
        "[decision del propietario, 2026-08-03, PIEZAS.md Sec.11.1].",
        "",
        "Si esto es una nota de memoria (una decision, un memo, una",
        "restriccion...) usa `gitmem note`. Si es trabajo de codigo, usa",
        "`gitmem work`.",
    )
    command = (
        'gitmem work "<mensaje>" --path <ruta1> [--path <ruta2> ...] [--issue N]',
    )
    return rejection_.build(
        kind="non_note_commit", what=what, options=options, command=command
    )


def _history_rewrite_rejection(subcommand):
    """Rejection for `commit --amend` or a starting `rebase`: both rewrite history."""
    if subcommand == "commit":
        what = "esto reescribe un commit ya existente: `git commit --amend`"
        relaunch = (
            'gitmem note <TIPO> --zones <zona1> <zona2> "..." --replaces <ID>'
            + validator.searched_suffix(validator.SEARCHED_PLACEHOLDER)
            + "  # si es una nota que hay que corregir",
            'gitmem work "<mensaje>" --path <ruta1> [--path <ruta2> ...]'
            "  # si es codigo: arreglalo en un commit nuevo",
        )
    else:
        what = "esto reescribe historia en lote: `git rebase`"
        relaunch = (
            "git merge --no-ff <rama>"
            "  # al terminar la tarea",
        )

    options = (
        "P1: nada se borra ni se reescribe jamas. Toda correccion es un",
        "commit nuevo (sustitucion, cierre, alta) -- nunca una reescritura",
        "de lo que ya esta en la historia.",
        "",
        "Si el motivo es limpiar la rama antes de mostrarla, no hace falta:",
        "deja los commits como estan. Al terminar la tarea la rama se fusiona",
        "con `git merge --no-ff <rama>`, que conserva el commit de cada paso.",
    )
    return rejection_.build(
        kind="history_rewrite", what=what, options=options, command=relaunch
    )


def _corrupt_file_rejection(filename, exc):
    """Rejection for an unreadable config.json or zones.json, saying how to repair it."""
    what = (
        f"`.claude/project-memory/{filename}` no se puede leer o no es "
        f"valido ({exc})"
    )
    options = (
        "Revisa el fichero a mano -- la causa mas probable es un merge o",
        "un rebase que se dejo a medias con marcadores de conflicto sin",
        "resolver dentro (`<<<<<<<` / `=======` / `>>>>>>>`). Corrige o",
        "edita el contenido hasta que vuelva a ser JSON valido y",
        "reintenta el commit.",
    )
    command = (
        f"# edita .claude/project-memory/{filename} a mano y valida que sea JSON",
    )
    return rejection_.build(
        kind="corrupt_memory_file", what=what, options=options, command=command
    )


# Customs switch.


def _project_has_notes(pm):
    """True once the project has a live or archived note."""
    if not pm.exists():
        return False

    for name in vocabulary.TYPE_INDEX_FILES.values():
        try:
            if indexes.read(name, pm):
                return True
        except FileNotFoundError:
            continue

    try:
        if indexes.read_archive(pm):
            return True
    except FileNotFoundError:
        pass

    return False


def _customs_active(cfg, pm):
    """Effective switch: an explicit config value wins, otherwise on once the project has notes."""
    if cfg.customs_enabled is not None:
        return cfg.customs_enabled
    return _project_has_notes(pm)


def _decide_rescue_passthrough(subcommand, rest_tokens):
    """Approve merge, cherry-pick and rebase rescue flags before reading any file; None otherwise.

    Runs first so a corrupt config.json never blocks the way out of a conflicted merge or rebase.
    """
    if subcommand in ("merge", "cherry-pick"):
        return {"decision": "approve"}
    if subcommand == "rebase" and _REBASE_PASSTHROUGH_FLAGS.intersection(rest_tokens):
        return {"decision": "approve"}
    return None


# Decision.


def _existing_in_zone_pair(zone1, zone2, archived):
    """Live notes of the zone pair in either order, deduplicated by id."""
    seen: set[str] = set()
    matches = []
    for n in (*query.by_zone(zone1, zone2), *query.by_zone(zone2, zone1)):
        if n.id in seen:
            continue
        seen.add(n.id)
        if n.id not in archived:
            matches.append(n)
    return tuple(matches)


def _decide_note(note, pm, cfg):
    """Validate a note commit against the repository's real Context, issue gate included."""
    try:
        zones_map = zones_lib.load(pm / "zones.json")
    except Exception as exc:
        reason = rejection_.render_hook_block(_corrupt_file_rejection("zones.json", exc))
        return {"decision": "block", "reason": reason}
    archived = indexes.archived_ids(pm)
    existing_in_zone = _existing_in_zone_pair(note.zone1, note.zone2, archived)
    known_ids = frozenset(n.id for n in query.by_zone(None, None))
    ctx = validator.Context(
        zones=zones_map,
        existing_in_zone=existing_in_zone,
        known_ids=known_ids,
        config=cfg,
    )
    rejections = list(validator.validate_note(note, ctx))
    gate_rejection = validator.validate_issue_gate(note, note.issue, None)
    if gate_rejection is not None:
        rejections.append(gate_rejection)
    if not rejections:
        return {"decision": "approve"}
    reason = "\n\n".join(rejection_.render_hook_block(r) for r in rejections)
    return {"decision": "block", "reason": reason}


def _decide_commit_creating(subcommand, rest_tokens, pm, cfg):
    """Decide a commit-creating statement with customs on.

    merge/cherry-pick pass, history rewrites block; a plain commit passes as wip or session close,
    is validated as a note, or is sent to `gitmem work`.
    """
    if subcommand in ("merge", "cherry-pick"):
        return {"decision": "approve"}

    if subcommand == "rebase":
        if _REBASE_PASSTHROUGH_FLAGS.intersection(rest_tokens):
            return {"decision": "approve"}
        reason = rejection_.render_hook_block(_history_rewrite_rejection("rebase"))
        return {"decision": "block", "reason": reason}

    # subcommand == "commit"
    if "--amend" in rest_tokens:
        reason = rejection_.render_hook_block(_history_rewrite_rejection("commit"))
        return {"decision": "block", "reason": reason}

    message = _extract_dash_m_message(rest_tokens)
    if message is not None:
        if validator.is_wip(message):
            return {"decision": "approve"}
        if format.parse_context_message(message) is not None:
            return {"decision": "approve"}
        note = format.parse_message(message)
        if note is not None:
            return _decide_note(note, pm, cfg)

    reason = rejection_.render_hook_block(_non_note_commit_rejection())
    return {"decision": "block", "reason": reason}


def _decide(hook_input):
    """Decision dict for a parsed hook payload."""
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input") or {}
    if tool_name != "Bash":
        return {"decision": "approve"}

    command = tool_input.get("command", "")
    if not command:
        return {"decision": "approve"}

    blocked = _decide_gitmem_save(command, hook_input)
    if blocked is not None:
        return blocked

    found = _find_commit_creating_statement(command)
    if found is None:
        return {"decision": "approve"}
    subcommand, rest_tokens, stmt_index = found

    passthrough = _decide_rescue_passthrough(subcommand, rest_tokens)
    if passthrough is not None:
        return passthrough

    # Judge against the directory the commit runs in, after any earlier `cd`.
    pm, cfg, early = _active_customs(command, hook_input, stmt_index)
    if early is not None:
        return early

    return _decide_commit_creating(subcommand, rest_tokens, pm, cfg)


def _active_customs(command, hook_input, stmt_index):
    """`(pm, cfg, None)` when customs is on where statement `stmt_index` runs,
    else `(None, None, decision)`: approve without a repo or with customs off, block on a corrupt config.json."""
    session_cwd = hook_input.get("cwd") or os.getcwd()
    cwd = _resolve_effective_cwd(command, session_cwd, limit_index=stmt_index)

    try:
        root = gitcmd.repo_root(Path(cwd))
    except RuntimeError:
        # Not a git repository: git itself will refuse the command.
        return None, None, {"decision": "approve"}

    pm = root / ".claude" / "project-memory"
    try:
        cfg = config.load(pm / "config.json")
    except Exception as exc:
        reason = rejection_.render_hook_block(_corrupt_file_rejection("config.json", exc))
        return None, None, {"decision": "block", "reason": reason}

    if not _customs_active(cfg, pm):
        return None, None, {"decision": "approve"}
    return pm, cfg, None


def _decide_gitmem_save(command, hook_input):
    """Block a `gitmem note`/`gitmem rule` save without `--searched` when customs is on; None otherwise."""
    found = save_command.find_unanswered_save(_shell_statements(command))
    if found is None:
        return None
    stmt_index, tokens = found
    _, _, early = _active_customs(command, hook_input, stmt_index)
    if early is not None:
        return early if early["decision"] == "block" else None
    reason = rejection_.render_hook_block(validator.validate_searched(None, tokens))
    return {"decision": "block", "reason": reason}


def main():
    try:
        raw = sys.stdin.read(_STDIN_READ_LIMIT)
        try:
            hook_input = json.loads(raw) if raw.strip() else {}
        except ValueError:
            hook_input = {}
        result = _decide(hook_input)
    except Exception as exc:
        result = {
            "decision": "block",
            "reason": f"customs.py: fallo inesperado, bloqueando por seguridad: {exc}",
        }

    try:
        json.dump(result, sys.stdout)
        sys.stdout.flush()
    except Exception:
        pass


if __name__ == "__main__":
    main()
