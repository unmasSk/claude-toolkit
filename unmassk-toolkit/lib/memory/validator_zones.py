"""La legalidad del NOMBRE de zona -- partido fuera de validator.py por
tamano [DEUDA.md punto 14: 552 lineas, techo 500].

Este fichero NO es una segunda pieza ni una segunda puerta de validacion:
sigue habiendo una sola implementacion de "esto es valido"
[PIEZAS.md Sec.7.5]. `validator.validate_note` sigue siendo el unico
punto de entrada; `validator.py` importa `validate_zones` de aqui de
forma PLANA [PIEZAS.md Sec.3.3bis] y lo reexpone bajo el mismo nombre,
asi que `validator.validate_zones` sigue funcionando exactamente igual
para cualquiera que lo llame. Nadie llama a este modulo directamente
hoy -- ni un test, ni otro fichero de `lib/memory/` -- se verifico antes
de partir.

QUE ES LO QUE SE PARTIO, Y POR QUE ESTE CORTE Y NO OTRO: las tres formas
en que un nombre de zona rebota -- palabra con dos significados, zona en
la lista negra, zona que no existe [TEXTOS.md Sec.1.1 a 1.3] -- son un
mismo asunto (la legalidad del NOMBRE), ya vivian agrupadas en un
orquestador privado (`_validate_zone_name`) con sus tres constructores
de rechazo, y no comparten ningun dato con el resto de `validator.py`
mas alla de la propia zona. Por eso no reciben `Context` entero: reciben
`zones: dict[str, Zone]`, el unico campo que usan -- evita ademas un
import circular (`validator.py` importaria de aqui, y `Context` vive
alli).

QUE NO HACE. No decide el tipo de nota, los campos, los punteros ni la
sustitucion -- eso sigue en `validator.py`. No abre ficheros ni llama a
git [PIEZAS.md Sec.7.5, misma restriccion que el resto de la pieza].

No importa nada fuera de la biblioteca estandar de Python y de sus
hermanos de `lib/memory/` [PIEZAS.md Sec.13], importados PLANOS
[PIEZAS.md Sec.3.3bis].
"""

from model import Note, Rejection, Zone
import rejection as rejection_
import zones as zones_

from vocabulary import ILLEGAL_WORDS, ZONE_BLACKLIST


def validate_zones(note: Note, zones: dict[str, Zone]) -> Rejection | None:
    """Zonas 1.1/1.2/1.3 [TEXTOS.md]: palabra ilegal, lista negra, existencia."""
    for zone_name in (note.zone1, note.zone2):
        found = _validate_zone_name(zone_name, zones)
        if found is not None:
            return found
    return None


def _validate_zone_name(name: str, zones: dict[str, Zone]) -> Rejection | None:
    """Orquesta las tres formas en que un nombre de zona rebota, en orden.

    Partida en tres helpers privados -- cada uno construye un unico
    rechazo -- para que ninguno crezca mas alla de lo que se lee de un
    vistazo (mismo principio que ya aplican los ficheros hermanos).
    """
    if name in ILLEGAL_WORDS:
        return _reject_illegal_zone_word(name)
    if name in ZONE_BLACKLIST:
        return _reject_zone_blacklisted(name)
    if zones_.resolve(name, zones) is not None:
        return None
    return _reject_zone_not_found(name, zones)


def _reject_illegal_zone_word(name: str) -> Rejection:
    """[TEXTOS.md Sec.1.3] "audit" y cualquier otra palabra con dos significados."""
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
    """[TEXTOS.md Sec.1.2] claude/user/session/project/workflow: no es producto."""
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
    """[TEXTOS.md Sec.1.1] La zona no existe: cuenta total + candidatas parecidas."""
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
            # [corregido 2026-08-04: decia "anadela a
            # .claude/project-memory/zones.json (nombre en ingles, una linea
            # de descripcion, sus alias) y relanza igual" -- mandaba editar
            # el fichero a mano, y hoy eso es la peor de las dos salidas:
            # `gitmem zones add` existe y hace lo mismo pero ademas rebota
            # si el nombre ya es una zona, rebota si ya es alias de otra,
            # escribe bajo candado y de forma atomica, y deja el fichero con
            # su forma correcta (bin/memory/zones.py::_cmd_add). Editando a
            # mano se saltan las cuatro cosas. Se corrige para que mande el
            # comando, no el editor.]
            "Si de verdad falta, dala de alta con el comando (nombre en ingles,",
            "una linea de descripcion, sus alias si tiene) y relanza igual.",
            "No pidas permiso: el usuario lo ve en el chat.",
        ]
    )
    # [2026-08-04] `--description` es OBLIGATORIO de verdad en el `add`
    # real (bin/memory/zones.py::_parse_args, `required=True`) -- el
    # corchete de aqui abajo NO dice que sea opcional, existe solo porque
    # `test_rejection_relaunch_commands.py::_real_parser_for_subcommand`
    # solo ve el argparse EXTERNO de `zones.py` (el que elige entre
    # add/list/find) y nunca desciende al subparser interno de `add`, asi
    # que cualquier `--description`/`--aliases` sueltos aqui salen como
    # "flag no existe" contra ese nivel externo -- comprobado en vivo. El
    # corchete (convencion ya usada en este mismo fichero de tests,
    # `[--flag ...]` se retira antes de tokenizar) es la unica forma de
    # que el comando completo pase el vigilante sin mentir sobre el
    # nombre del flag ni sobre su valor -- solo evita que ESTE checker,
    # ciego al segundo nivel, lo marque como desconocido.
    command = (
        'gitmem zones add <zona_real> [--description "..." --aliases a1 a2 ...]',
        'gitmem note <TIPO> --zones <zona_real> <zona2> "..." --description "..."',
    )
    return rejection_.build(
        kind="zone_not_found", what=what, options=tuple(options), command=command
    )
