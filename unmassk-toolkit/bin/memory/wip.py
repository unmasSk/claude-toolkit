#!/usr/bin/env python3
"""gitmem wip: commit work in progress with the [WIP] 🚧 marker so the commit gate asks no questions.

Usage: wip.py "<message>" --path <file> [--path <file> ...]. Refuses on a protected main branch.
"""

import argparse
import os
import shlex
import sys
from pathlib import Path

_BIN_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_BIN_MEMORY_DIR))
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402

force_utf8_streams()

import ci  # noqa: E402
import config  # noqa: E402
import emojis  # noqa: E402
import gitcmd  # noqa: E402
import notes  # noqa: E402
import repo_guard  # noqa: E402

_WIP_MARKER = emojis.CHANNEL_EMOJI["wip"]

# Read back by `validator.is_wip()`.
_WIP_PREFIX = "[WIP]"


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="wip.py")
    parser.add_argument("message")
    parser.add_argument("--path", action="append", required=True, dest="paths")
    return parser.parse_args(argv)


def _changed_files_under(directory, root, cwd):
    """Changed files (tracked or new) under `directory`, as posix paths relative to `cwd`."""
    result = gitcmd.run(
        ["status", "--porcelain", "-z", "--untracked-files=all", "--", str(directory)],
        cwd=cwd,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git status fallo: {result.stderr.strip()}")
    fields = result.stdout.split("\0")
    changed = []
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        # With -z, a rename or copy is followed by its source path.
        if entry[0] in "RC":
            i += 1
        changed.append(Path(os.path.relpath(root / entry[3:], cwd)).as_posix())
    return sorted(changed)


def _directory_rejection(message, paths, root):
    """Rejection text when a `--path` is a folder: its changed files and the exact relaunch command."""
    cwd = Path.cwd().resolve()
    root = Path(root).resolve()
    files = []
    lines = []
    for path in paths:
        if not path.is_dir():
            files.append(path.as_posix())
            continue
        under = _changed_files_under(path, root, cwd)
        lines.append(f"\n«{path.as_posix()}» es una carpeta, y --path solo admite ficheros.")
        if under:
            lines.append("Ficheros cambiados dentro:")
            lines.extend(f"  {name}" for name in under)
        else:
            lines.append("Dentro no hay ningun fichero cambiado.")
        files.extend(under)
    lines.insert(0, "No se ha guardado nada.")
    if files:
        unique = dict.fromkeys(files)
        relaunch = " ".join(f"--path {shlex.quote(f)}" for f in unique)
        lines.append("\nPara guardarlos, relanza con un --path por fichero:")
        lines.append(f"  gitmem wip {shlex.quote(message)} {relaunch}")
    return "\n".join(lines)


def main(argv):
    args = _parse_args(argv)
    paths = [Path(p) for p in args.paths]

    if any(path.is_dir() for path in paths):
        print(_directory_rejection(args.message, paths, notes.repo_root()), file=sys.stderr)
        return 1

    # Read the bytes before any git call; None makes write_work() read the file itself.
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

    marked_message = f"{_WIP_PREFIX} {_WIP_MARKER} {args.message}"
    # The skip-ci marker goes on its own line after a blank line.
    full_message = f"{marked_message}\n\n{ci.SKIP_CI_MARKER}"
    result = notes.write_work(full_message, paths, None, known_content=known_content)
    if not result.ok:
        print(f"git fallo al commitear: {result.git_error}", file=sys.stderr)
        return 1

    print(full_message)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # never a stack trace
        print(f"wip.py: {exc}", file=sys.stderr)
        sys.exit(1)
