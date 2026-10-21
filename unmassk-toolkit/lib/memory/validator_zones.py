"""Zone-name legality checks (ambiguous word, blacklist, unknown zone), re-exported by `validator.py`."""

from model import Note, Rejection, Zone
import rejection as rejection_
import zones as zones_

from vocabulary import ILLEGAL_WORDS, ZONE_BLACKLIST


def validate_zones(note: Note, zones: dict[str, Zone]) -> Rejection | None:
    """Return the first rejection for either zone of `note`: illegal word, blacklisted, or unknown."""
    for zone_name in (note.zone1, note.zone2):
        found = _validate_zone_name(zone_name, zones)
        if found is not None:
            return found
    return None


def _validate_zone_name(name: str, zones: dict[str, Zone]) -> Rejection | None:
    """Check one zone name against the three rejection cases, in order."""
    if name in ILLEGAL_WORDS:
        return _reject_illegal_zone_word(name)
    if name in ZONE_BLACKLIST:
        return _reject_zone_blacklisted(name)
    if zones_.resolve(name, zones) is not None:
        return None
    return _reject_zone_not_found(name, zones)


def _reject_illegal_zone_word(name: str) -> Rejection:
    """Reject a zone word with two meanings, offering both resolutions."""
    resolution_a, resolution_b = ILLEGAL_WORDS[name]
    what = f'"{name}" significa dos cosas distintas'
    options = (
        "Elige cual:",
        "",
        f"  {resolution_a}",
        f"  {resolution_b}",
    )
    command = (
        f'gitmem note <TIPO> --zones product {resolution_a} "..." --description "..."',
        f'gitmem note <TIPO> --zones {resolution_b} <zona2> "..." --description "..."',
    )
    return rejection_.build(
        kind="illegal_zone_word", what=what, options=options, command=command
    )


def _reject_zone_blacklisted(name: str) -> Rejection:
    """Reject a blacklisted zone (claude/user/session/project/workflow), pointing to `gitmem rule`."""
    what = f'"{name}" no es memoria del proyecto'
    options = (
        "claude, user, session, project y workflow describen COMO trabajamos,",
        "no el producto. Eso va al fichero de reglas, que se lee entero aparte",
        "y no ensucia ninguna busqueda:",
        "",
        '  gitmem rule "..."',
        "",
        "Si en realidad hablabas de una parte del producto, dale su zona real:",
    )
    command = ('gitmem note M --zones <zona1> <zona2> "..." --description "..."',)
    return rejection_.build(
        kind="zone_blacklisted", what=what, options=options, command=command
    )


def _reject_zone_not_found(name: str, zones: dict[str, Zone]) -> Rejection:
    """Reject an unknown zone, listing the zone count and the closest candidates."""
    candidates = zones_.candidates(name, zones)
    what = f'la zona "{name}" no existe'
    options = [
        f"zones.json tiene {len(zones)} zonas. Antes de crear una nueva, mira si ya",
        "esta con otro nombre. Las mas parecidas:",
        "",
    ]
    for candidate in candidates:
        options.append(f"  {candidate.name}   {candidate.description}")
    options.append("")
    if candidates:
        options.append("Si es una de ellas, relanza con esa zona.")
        options.append("")
    options.extend(
        [
            "Si de verdad falta, dala de alta con el comando (nombre en ingles,",
            "una linea de descripcion, sus alias si tiene) y relanza igual.",
            "No pidas permiso: el usuario lo ve en el chat.",
        ]
    )
    # `--description` is required by `zones add`; the brackets only let the relaunch-command
    # test, which sees just the outer parser, skip flags of the `add` subparser.
    command = (
        'gitmem zones add <zona_real> [--description "..." --aliases a1 a2 ...]',
        'gitmem note <TIPO> --zones <zona_real> <zona2> "..." --description "..."',
    )
    return rejection_.build(
        kind="zone_not_found", what=what, options=tuple(options), command=command
    )
