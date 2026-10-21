#!/usr/bin/env python3
"""Repair the memory indexes from git: `--verify` only diagnoses; without it,
rebuild the indexes and commit the repair. Exit 1 on divergence or failed save."""

import argparse
import os
import sys

_BIN_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_BIN_MEMORY_DIR))
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import after sys.path)

force_utf8_streams()

import health  # noqa: E402
import indexes  # noqa: E402
import notes  # noqa: E402
import rezones_commit  # noqa: E402


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="rezones.py")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args(argv)


def _verify(root):
    lines, notes_count, discrepancies = health.coherence(root)
    if not discrepancies:
        return [f"✓ índices coherentes con git ({lines} líneas / {notes_count} notas)"], 0
    out = [f"⚠️ índices no coherentes con git ({lines} líneas / {notes_count} notas)"]
    out.extend(f"  - {text}" for text in discrepancies)
    return out, 1


def _rebuild(root, pm):
    indexes.seed(pm)
    # Planned outside the lock on purpose: concurrent repairs are not supported.
    to_insert, to_remove = health.rebuild_plan(root)

    if not to_insert and not to_remove:
        return ["✓ nada que reconstruir -- los índices ya coinciden con git"], 0

    result = rezones_commit.apply_rebuild_plan(to_insert, to_remove, pm, root)
    if not result.ok:
        # apply_rebuild_plan() already restored the files; print git's real error.
        return [f"⚠️ la reparación no se pudo guardar -- índices restaurados: {result.git_error}"], 1

    changes = [f"+ {note.id} reinsertada en {target}" for note, target in to_insert]
    changes += [f"- {note_id} retirada de {name} (no existe en git)" for note_id, name in to_remove]
    return changes, 0


def main(argv):
    args = _parse_args(argv)
    root = notes.repo_root()
    pm = notes.pm_root(root)

    if args.verify:
        lines, rc = _verify(root)
        print("\n".join(lines))
        return rc

    lines, rc = _rebuild(root, pm)
    print("\n".join(lines))
    return rc


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # never a stack trace
        print(f"rezones.py: {exc}", file=sys.stderr)
        sys.exit(1)
