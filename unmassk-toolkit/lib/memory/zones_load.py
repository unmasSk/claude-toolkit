"""Read `zones.json`; `zones.py` re-exports `load()`."""

import json
from pathlib import Path

from model import Zone
from zones_commit import normalize


def load(path: Path) -> dict[str, Zone]:
    """Zones keyed by normalized name; a missing file means no zones yet.

    Invalid JSON or a wrong shape raises (`ValueError` naming file and zone):
    returning {} would let `add()` overwrite every zone. Names and aliases are
    normalized on read; the description is kept as is.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        return {}

    if not isinstance(raw, dict):
        raise ValueError(
            f"zones.py: {path.name} esta corrupto -- se esperaba un objeto "
            f"JSON (diccionario) y llego {type(raw).__name__}"
        )

    zones: dict[str, Zone] = {}
    for name, fields in raw.items():
        if not isinstance(fields, dict):
            raise ValueError(
                f"zones.py: {path.name} esta corrupto -- la zona {name!r} "
                f"debe ser un objeto JSON y llego {type(fields).__name__}"
            )

        description = fields.get("description", "")
        if not isinstance(description, str):
            raise ValueError(
                f"zones.py: {path.name} esta corrupto -- 'description' de "
                f"la zona {name!r} debe ser texto y llego "
                f"{type(description).__name__}"
            )

        aliases = fields.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            raise ValueError(
                f"zones.py: {path.name} esta corrupto -- 'aliases' de la "
                f"zona {name!r} debe ser una lista de texto y llego "
                f"{aliases!r}"
            )

        canonical_name = normalize(name)
        canonical_aliases = tuple(normalize(a) for a in aliases)
        zones[canonical_name] = Zone(
            name=canonical_name, description=description, aliases=canonical_aliases
        )
    return zones
