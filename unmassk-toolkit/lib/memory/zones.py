"""Project zones facade: re-exports load/query helpers and owns `add()`, the only write of zones.json.

zones.json format: `{canonical_name: {"description": ..., "aliases": [...]}}`.
"""

from pathlib import Path

from model import Zone
from zones_commit import exclusive_lock, normalize, write_atomic  # noqa: F401
from zones_load import load
from zones_query import candidates, render_list, resolve  # noqa: F401


def add(zone: Zone, path: Path) -> None:
    """Add `zone` to zones.json atomically under an exclusive lock, creating the file and its folder if missing.

    Name and aliases are normalized before writing; the description is kept as is.
    """
    canonical = Zone(
        name=normalize(zone.name),
        description=zone.description,
        aliases=tuple(normalize(a) for a in zone.aliases),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with exclusive_lock(lock_path):
        existing = load(path)
        existing[canonical.name] = canonical
        write_atomic(path, existing)
