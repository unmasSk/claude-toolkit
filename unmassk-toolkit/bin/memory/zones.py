#!/usr/bin/env python3
"""List, find and add the project's zones.

    zones.py add <name> --description "..." [--aliases a1 a2 ...]
    zones.py list
    zones.py find <name>

`add` refuses a name that is already a zone or another zone's alias, leaving zones.json untouched.
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

import health  # noqa: E402
import notes  # noqa: E402
import zones as zones_lib  # noqa: E402
from model import Zone  # noqa: E402


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="zones.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("name")
    add_parser.add_argument("--description", required=True)
    add_parser.add_argument("--aliases", nargs="+", default=())

    subparsers.add_parser("list")

    find_parser = subparsers.add_parser("find")
    find_parser.add_argument("name")

    return parser.parse_args(argv)


def _zones_path():
    root = notes.repo_root()
    pm = notes.pm_root(root)
    return pm / "zones.json"


def _cmd_add(args, path):
    # Name and aliases are lowercased before the duplicate check; the description is not.
    name = zones_lib.normalize(args.name)
    aliases = tuple(zones_lib.normalize(a) for a in args.aliases)

    existing = zones_lib.load(path)
    if name in existing:
        print(
            f"❌ \"{name}\" ya es una zona -- no se ha tocado zones.json. "
            "Si quieres cambiar su descripcion o sus alias, edita el fichero "
            "a mano (todavia no hay comando de edicion)."
        )
        return 1

    # A name that is another zone's alias is refused too, naming its owner.
    owner = zones_lib.resolve(name, existing)
    if owner is not None:
        print(
            f"❌ \"{name}\" ya es alias de la zona \"{owner}\" -- no se ha "
            "tocado zones.json. Si quieres cambiar sus alias, edita el "
            "fichero a mano (todavia no hay comando de edicion)."
        )
        return 1

    zone = Zone(name=name, description=args.description, aliases=aliases)
    zones_lib.add(zone, path)
    total = len(zones_lib.load(path))
    unit = "zona" if total == 1 else "zonas"

    # Tell the user what normalisation changed.
    changed = []
    if name != args.name:
        changed.append(f"\"{args.name}\" → \"{name}\"")
    for raw, normalized in zip(args.aliases, aliases):
        if raw != normalized:
            changed.append(f"alias \"{raw}\" → \"{normalized}\"")
    notice = f" (normalizado a minuscula: {', '.join(changed)})" if changed else ""

    # No commit here: zones.json stays modified in the working tree for the next commit.
    print(f"✅ {name} añadida — zones.json tiene {total} {unit}{notice}")
    return 0


def _cmd_list(path):
    # A missing zones.json is reported apart from an empty one.
    state, _ = health.zones_state(path)
    if state == "absent":
        print("zones.json (no existe) -- todavia no se ha dado de alta ninguna zona.")
        return 0

    zones_map = zones_lib.load(path)
    print(zones_lib.render_list(zones_map))
    return 0


def _cmd_find(args, path):
    zones_map = zones_lib.load(path)
    matches = zones_lib.candidates(args.name, zones_map)
    if not matches:
        print(f"ninguna zona parecida a «{args.name}» (zones.json tiene {len(zones_map)} zonas)")
        return 0
    print(f"zonas parecidas a «{args.name}»:")
    for zone in matches:
        print(f"  {zone.name}   {zone.description}")
    return 0


def main(argv):
    args = _parse_args(argv)
    path = _zones_path()

    if args.command == "add":
        return _cmd_add(args, path)
    if args.command == "list":
        return _cmd_list(path)
    return _cmd_find(args, path)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # never a stack trace
        print(f"zones.py: {exc}", file=sys.stderr)
        sys.exit(1)
