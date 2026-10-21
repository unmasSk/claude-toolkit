#!/usr/bin/env python3
"""Memory search by zone, word, note id or file; always prints a report, never a commit list.

Usage: search.py <ZONE-or-WORD> [--todo | --chain] | --id <ID> | --file <PATH> [--todo]
"""

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

import notes  # noqa: E402
import query  # noqa: E402
import report  # noqa: E402
import report_render  # noqa: E402
import report_render_chain  # noqa: E402
import report_render_note  # noqa: E402
import zones as zones_lib  # noqa: E402


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="search.py")
    parser.add_argument("query", nargs="?", default=None, help="zona o palabra")
    parser.add_argument("--id", default=None)
    parser.add_argument("--file", default=None)
    parser.add_argument("--todo", action="store_true")
    # Chain view: each live note with its replaced predecessors below it.
    parser.add_argument("--chain", action="store_true")
    return parser.parse_args(argv)


def _render_by_id(note_id):
    note_report = report.build_note(note_id)
    if note_report is None:
        print(f"search.py: no existe la nota {note_id}", file=sys.stderr)
        return None
    return report_render_note.render_note(note_report)


def _render_by_file(path, include_archived):
    touched = query.by_file(path)
    if not touched:
        return (
            f"search.py: ninguna nota toco {path} -- limitacion conocida de "
            "--file: busca commits que tocan esa ruta exacta, y el commit de "
            "una nota nunca toca el fichero de codigo del que habla (toca "
            "solo los indices de memoria). Para preguntar por un fichero, "
            "usa la busqueda por palabra: search.py <basename o modulo>"
        )
    zones_touched = sorted({n.zone1 for n in touched})
    reports = [
        report_render.render_zone(report.build_zone(z, include_archived))
        for z in zones_touched
    ]
    return "\n\n".join(reports)


def _render_zones_catalog(zones_map):
    """Render the project's zone list, shown when a word search finds no note."""
    if not zones_map:
        return "Este proyecto todavía no tiene ninguna zona dada de alta."
    return zones_lib.render_list(zones_map)


def _insert_before_footer(rendered, block):
    """Insert `block` before the word report's footer (its last THIN_DIVIDER)."""
    marker = "\n" + report_render.THIN_DIVIDER
    head, sep, tail = rendered.rpartition(marker)
    if not sep:
        # No footer: append rather than drop the block.
        return rendered + "\n\n" + block
    return f"{head}\n\n{block}{sep}{tail}"


def _render_chain(text):
    """Render the ``--chain`` view for `text` (resolved against the cwd's repo)."""
    return report_render_chain.render_chain(report.build_chain(text))


def _render_by_query(text, include_archived, pm):
    zones_map = zones_lib.load(pm / "zones.json")
    resolved = zones_lib.resolve(text, zones_map)
    if resolved is not None:
        return report_render.render_zone(report.build_zone(resolved, include_archived))

    word_report = report.build_word(text, include_archived)
    rendered = report_render.render_word(word_report)
    if word_report.zone_count == 0:
        rendered = _insert_before_footer(rendered, _render_zones_catalog(zones_map))
    return rendered


def main(argv):
    args = _parse_args(argv)

    if args.id is not None:
        text = _render_by_id(args.id)
        if text is None:
            return 1
        print(text)
        return 0

    root = notes.repo_root()
    pm = notes.pm_root(root)

    if args.file is not None:
        print(_render_by_file(args.file, args.todo))
        return 0

    if args.query is None:
        print("search.py: se necesita una zona, una palabra, --id o --file", file=sys.stderr)
        return 1

    if args.chain:
        print(_render_chain(args.query))
        return 0

    print(_render_by_query(args.query, args.todo, pm))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # never a stack trace
        print(f"search.py: {exc}", file=sys.stderr)
        sys.exit(1)
