#!/usr/bin/env python3
"""`gitmem work`: commit only the given paths; refuses on a protected main branch.

    work.py "<message>" --path <path1> [--path <path2> ...] [--issue N]
"""

import argparse
import os
import sys
from pathlib import Path

_BIN_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_BIN_MEMORY_DIR))
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import after sys.path)

force_utf8_streams()

import ci  # noqa: E402
import config  # noqa: E402
import notes  # noqa: E402
import rejection as rejection_  # noqa: E402
import repo_guard  # noqa: E402
import validator_issue  # noqa: E402


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="work.py")
    parser.add_argument("message")
    parser.add_argument("--path", action="append", required=True, dest="paths")
    parser.add_argument("--issue", type=int, default=None)
    return parser.parse_args(argv)


def _issue_rejection(message, paths, issue):
    """Build the rejection for `--issue N` when gh confirms the issue does not exist."""
    what = f"COMMIT DE TRABAJO RECHAZADO — la issue #{issue} no existe en este repo"
    options = (
        "Esta es la unica vez que se comprueba. Un numero mal tecleado aqui",
        "queda en el historial para siempre -- un commit no se reescribe.",
        "",
        "  gh issue list --limit 20          ver las abiertas",
        '  gh issue create --title "..."     crearla ahora',
    )
    path_flags = " ".join(f"--path {p}" for p in paths)
    command = (f'gitmem work "{message}" {path_flags} --issue <numero real>',)
    return rejection_.build(kind="issue_not_found", what=what, options=options, command=command)


def main(argv):
    args = _parse_args(argv)
    paths = [Path(p) for p in args.paths]

    # Read the content first, before any git call, so the commit holds what this
    # process saw. None when unreadable: write_work() then reads the file itself.
    known_content = []
    for path in paths:
        try:
            known_content.append(path.read_bytes())
        except OSError:
            known_content.append(None)

    root = notes.repo_root()
    pm = notes.pm_root(root)
    config_path = pm / "config.json"
    cfg = config.load(config_path)

    branch = repo_guard.protected_main_branch(root, cfg)
    if branch is not None:
        print(repo_guard.protected_branch_rejection(branch, config_path))
        return 1

    # Only a confirmed missing issue blocks; a gh failure only warns.
    if args.issue is not None:
        try:
            exists = validator_issue.issue_exists(args.issue)
        except RuntimeError as exc:
            print(
                f"aviso: no se pudo comprobar la issue #{args.issue} ({exc}) -- "
                "el commit de trabajo se guarda igual",
                file=sys.stderr,
            )
        else:
            if not exists:
                print(rejection_.render_terminal(_issue_rejection(args.message, paths, args.issue)))
                return 1

    # The skip-ci marker goes on its own line, so an `Issue: #N` trailer stays on its own line too.
    message_with_marker = f"{args.message}\n\n{ci.SKIP_CI_MARKER}"
    result = notes.write_work(message_with_marker, paths, args.issue, known_content=known_content)
    if not result.ok:
        print(f"git fallo al commitear: {result.git_error}", file=sys.stderr)
        return 1

    print(f"✅ commit de trabajo: {args.message}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # never a stack trace
        print(f"work.py: {exc}", file=sys.stderr)
        sys.exit(1)
