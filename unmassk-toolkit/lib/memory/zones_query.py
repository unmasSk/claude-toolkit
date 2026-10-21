"""Zone lookup and listing: alias resolution, closest matches and the list text."""

import difflib

from model import Zone
from zones_commit import normalize


def resolve(name: str, zones: dict[str, Zone]) -> str | None:
    """Return the key in `zones` that `name` or one of its aliases names, or None.

    Both sides are normalised before comparing; the key is returned as stored.
    """
    target = normalize(name)
    for canonical, zone in zones.items():
        if normalize(canonical) == target:
            return canonical
        if target in (normalize(a) for a in zone.aliases):
            return canonical
    return None


def candidates(name: str, zones: dict[str, Zone], limit: int = 3) -> tuple[Zone, ...]:
    """Return up to `limit` whole zones whose names are closest to normalised `name`."""
    close_names = difflib.get_close_matches(
        normalize(name), list(zones.keys()), n=limit, cutoff=0.6
    )
    return tuple(zones[n] for n in close_names)


def render_list(zones_map: dict[str, Zone]) -> str:
    """Format the zone list: a count header, then one line per zone with its aliases."""
    lines = [f"zones.json tiene {len(zones_map)} zonas:"]
    for name in sorted(zones_map):
        zone = zones_map[name]
        line = f"  {name}   {zone.description}"
        if zone.aliases:
            line += f"   (alias: {', '.join(zone.aliases)})"
        lines.append(line)
    return "\n".join(lines)
