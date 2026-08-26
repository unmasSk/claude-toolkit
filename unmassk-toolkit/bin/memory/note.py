#!/usr/bin/env python3
"""bin/memory/note.py -- guarda una nota de memoria (D/M/R/Q/X/I/B).

Contrato: docs/memoria-v2/PIEZAS.md Sec.10 (fila `note.py`) y Sec.10.1,
punto 1 (la comprobacion de `--issue`). Recibe argumentos, arma el
`Context` real (zonas del proyecto, notas de la misma zona, identificadores
conocidos, configuracion), llama a la funcion de la libreria que toca segun
`--replaces` (`notes.write` si esta ausente o es el centinela `"none"`,
`notes.replace` si es un ID real) e imprime lo que devuelve -- toda la
logica de "esto es valido" vive en `validator.py`/`notes.py`, nunca aqui
[PIEZAS.md Sec.10, regla comun a los once scripts: "si un script crece, es
que se le esta colando logica que pertenece a un modulo"; PIEZAS.md
Sec.10, fila `note.py`: "llama a notes.write · notes.replace ·
notes.discard_alternatives" -- `discard_alternatives` se enganchó vía
`--discard` [decision del propietario, 2026-08-04: "hay que engancharlo,
por supuesto"; forma del flag fijada en el contrato en rojo,
test_note_script.py::TestDiscardFlagWiresIntoNotesDiscardAlternatives].
`notes.promote` se engancha via `--promotes` [2026-08-05, pendiente de
que esa fila de PIEZAS.md se ponga al dia con esta cuarta funcion].

Grammar de CLI [derivada de los comandos de relanzamiento LITERALES que
TEXTOS.md repite en Sec.1.1/1.5/1.6/1.7/1.9/1.11, todos con la misma
forma -- ver el docstring de test_note_script.py, que fija esta misma
gramatica antes de que este fichero existiera]:

    note.py <TIPO> --zones <zona1> <zona2> "<titular>" \\
        [--why "..."] [--description "..."] [--keys k1 k2 ...] \\
        [--stops yes|no] [--origin <id1> <id2> ...] \\
        [--replaces <ID>|none] [--awaits "..."] [--issue N|none] \\
        [--work no] [--quote "..."] \\
        [--discard "<titular alternativa>" "<porque>" ...] \\
        [--promotes <ID de una Q>]

`--work`/`--quote` [D-065/D-066, 2026-08-26]: la aduana de issues,
exclusiva de Q/I -- sin `--issue` ni `--work`, rebota pidiendo que se
conteste "¿cerrar esta nota exige trabajo... o solo una
respuesta/decision?" (`validator.validate_issue_gate`). `--work no`
deja pasar la nota sin issue; `--issue none` deja pasar el "no" del
dueño, pero exige `--quote "<sus palabras>"` (sin escape `--quote none`,
a diferencia de `gitmem rule`: D-066, "el no siempre es del dueño y
siempre lleva cita"). `--work` no es campo de `Note` -- viaja aparte
igual que `--stops`; `--quote` SI lo es (`Note.quote`, solo Q/I).

`--promotes <ID>` [2026-08-05, encargo del propietario]: la nota nueva
asciende la pregunta (Q) `<ID>` -- sube a memo si la respuesta es un
hecho, cae a descarte si es que no [spec Sec.4]. Llama a
`notes.promote()` (reexportada de `notes_promote.py`, ver su docstring)
en vez de `notes.write()`/`notes.replace()`; no se combina con
`--replaces` en ningun test de esta tarea, y no se le exige a este
script decidir nada sobre esa combinacion -- toda decision de "esto es
valido" sigue en `validator.py`/`notes_promote.py`.

`--discard` es repetible (una vez por alternativa) -- ningun test de
esta tarea lo combina con `--replaces <ID>`. El SEGUNDO valor de cada
pareja llena `Note.description` de la alternativa (tipo `X`), NUNCA
`Note.why` [`vocabulary.TYPES["X"].required_fields == {"description"}`,
`why` es opcional para X]. `origin` lo pone `discard_alternatives()` por
su cuenta -- este script no pasa ningun puntero de origen.

`--stops` (solo aplica a M/R) y `--issue` NO son campos de `Note`: viajan
aparte hasta `validator.validate_pain_question`/`validate_issue`, las
DOS unicas funciones del validador que se llaman fuera de
`validate_note()` [ver "ASUNCIONES DE FIRMA" en validator.py]. Las dos
se comprueban ANTES de escribir nada -- ninguna abre un commit por su
cuenta, y las dos usan el rechazo REAL de `validator.py`/`rejection.py`,
nunca un texto propio de este script.

`--keys` pasa por `validator.normalize_keys` antes de guardarse: el
generador (esta pieza) es quien aplica la correccion y la enseña al
guardar -- nunca un rechazo [TEXTOS.md Sec.1.8, "no es rechazo, es aviso
al guardar"].
"""

import argparse
import os
import sys
from datetime import datetime, timezone

_BIN_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_BIN_MEMORY_DIR))
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import tras sys.path)

force_utf8_streams()

import config  # noqa: E402
import indexes  # noqa: E402
import notes  # noqa: E402
import query  # noqa: E402
import rejection as rejection_  # noqa: E402
import validator  # noqa: E402
import zones as zones_lib  # noqa: E402
from emojis import TYPE_EMOJI  # noqa: E402
from model import Note  # noqa: E402
from vocabulary import MARKER_KEYS  # noqa: E402


def _issue_arg(value):
    """`--issue` acepta un numero real o el centinela literal `"none"`
    [D-065/D-066, la aduana de issues] -- mismo patron que `--replaces`
    (cadena libre, distinguida de un id real por quien la usa), pero con
    forma comprobada aqui: cualquier otra cadena revienta en argparse con
    un mensaje claro, en vez de propagarse como un `ValueError` sin
    explicar mas abajo. Devuelve `int` para un numero real, o el string
    `"none"` tal cual para el centinela -- `main()` resuelve cual de los
    dos es antes de construir la `Note` candidata.
    """
    if value == "none":
        return value
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--issue: {value!r} no es ni un numero ni el centinela 'none'"
        )


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="note.py")
    parser.add_argument("type", help="D M R Q X I B")
    parser.add_argument("--zones", nargs=2, metavar=("ZONE1", "ZONE2"), required=True)
    parser.add_argument("headline")
    parser.add_argument("--why", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--keys", nargs="+", default=())
    parser.add_argument("--stops", choices=("yes", "no"), default=None)
    parser.add_argument("--origin", nargs="+", default=())
    parser.add_argument("--replaces", default=None)
    parser.add_argument("--awaits", default=None)
    parser.add_argument("--issue", type=_issue_arg, default=None)
    # `--work`/`--quote` [D-065/D-066, 2026-08-26]: la aduana de issues de
    # Q/I. `--work` solo acepta "no" -- D-065 no define un "--work yes"
    # propio, esa respuesta se contesta dando `--issue` directamente.
    parser.add_argument("--work", choices=("no",), default=None)
    parser.add_argument("--quote", default=None)
    parser.add_argument("--promotes", default=None)  # 2026-08-05: asciende una Q
    parser.add_argument(
        "--discard", action="append", nargs=2, metavar=("HEADLINE", "WHY"), default=None
    )
    return parser.parse_args(argv)


def _existing_in_zone_pair(zone1, zone2, archived):
    """Notas VIVAS de la pareja de zonas ``(zone1, zone2)``, EN CUALQUIER
    ORDEN [Moriarty BREAK 2, 2026-08-25, mismo helper duplicado a proposito
    en `hooks/customs.py::_decide_note` -- los dos caminos de entrada
    tienen que tratar la pareja de zonas igual, sin acoplar los dos
    scripts entre si ni tocar `query.py`].

    Une ``query.by_zone(zone1, zone2)`` y ``query.by_zone(zone2, zone1)``,
    dedup por ``id`` (conserva el primer orden en que aparece), y filtra
    contra ``archived`` -- mismo filtro que ya vivia aqui antes de este
    arreglo, ahora aplicado a la union de las dos consultas en vez de a
    una sola.
    """
    seen: set[str] = set()
    matches = []
    for note in (*query.by_zone(zone1, zone2), *query.by_zone(zone2, zone1)):
        if note.id in seen:
            continue
        seen.add(note.id)
        if note.id not in archived:
            matches.append(note)
    return tuple(matches)


def _build_context(pm, zone1, zone2):
    """El `Context` real que `validator.validate_note` necesita -- cada
    campo, leido de la fuente real que ya existe en produccion, nunca
    fabricado: `zones.load` (zonas del proyecto), `query.by_zone` (las
    notas ya escritas en esa pareja de zonas, para `validate_replacement`,
    y el historial completo para `known_ids`, que `validate_pointers`
    necesita), `config.load` (fail-closed si no hay fichero).

    `zone1`/`zone2` se resuelven a su nombre CANONICO con `zones.resolve()`
    contra el mismo mapa que se acaba de cargar, antes de usarlos para
    nada mas -- `validator_zones._validate_zone_name()` ya acepta un
    alias como zona valida, pero nadie lo traducia entre "esto es valido"
    y "esto es lo que se guarda"; una nota dada de alta con un alias
    quedaba invisible para siempre en la navegacion por zona [hallazgo
    real de Moriarty, 2026-08-04]. Si `resolve()` no encuentra nada (zona
    de verdad inexistente) se conserva el nombre tal cual se tecleo, para
    que `validate_zones` pueda rechazarlo con su texto real. Devuelve el
    `Context` junto con el `zone1`/`zone2` ya resueltos, para que quien
    llama construya la nota candidata con el nombre que de verdad se va a
    guardar -- el mismo que se usa aqui para `existing_in_zone`.

    `existing_in_zone` se filtra contra `indexes.archived_ids(pm)` antes
    de entrar en `Context` [2026-08-05, encargo del propietario: "si sale
    una nueva incidencia, es una nueva incidencia; la otra ya se cerro,
    aunque sea sobre lo mismo"]. `query.by_zone()` no distingue vivo de
    archivado -- devuelve TODO el historial de esa pareja de zonas a
    proposito, porque el informe de zona y otras lecturas si necesitan
    ver lo archivado (Sec.8.2). El filtro va aqui, no dentro de
    `query.by_zone()` ni dentro de `validate_replacement()`: lo primero
    rompería al informe de zona y a `health`/`boot`, que leen el
    historial completo por diseño; lo segundo exigiría que el validador
    abriera `ARCHIVED.md` por su cuenta, y el contrato de `validator.py`
    prohibe que ese modulo abra ficheros o llame a git -- todo lo que
    necesita saber del mundo lo recibe ya resuelto en `Context`. `known_ids`
    se deja sin filtrar a proposito: un `--replaces`/`--origin` valido
    puede apuntar a una nota ya archivada (p.ej. el muro de `remove.py`
    cita con `--origin` la incidencia que el propio cierre acaba de
    archivar), y `validate_pointers` solo comprueba que el identificador
    exista alguna vez, no que siga vigente.

    `existing_in_zone` recorre la pareja de zonas en los DOS ordenes
    (``_existing_in_zone_pair``) [Moriarty BREAK 2, 2026-08-25]: la
    puerta de duplicados de `similar.py` ya compara `zone1`/`zone2` como
    CONJUNTO, pero de nada sirve si la nota con las zonas al reves nunca
    llega a `existing_in_zone` -- `query.by_zone(zone1, zone2)` por si
    sola es una coincidencia posicional exacta y la deja fuera. No toca
    `query.by_zone()` ni como se resuelven las zonas en ningun otro
    camino: solo une sus dos llamadas aqui, en el mismo sitio donde ya
    vive el filtro de archivadas.
    """
    zones_map = zones_lib.load(pm / "zones.json")
    zone1 = zones_lib.resolve(zone1, zones_map) or zone1
    zone2 = zones_lib.resolve(zone2, zones_map) or zone2
    archived = indexes.archived_ids(pm)
    existing_in_zone = _existing_in_zone_pair(zone1, zone2, archived)
    known_ids = frozenset(n.id for n in query.by_zone(None, None))
    cfg = config.load(pm / "config.json")
    ctx = validator.Context(
        zones=zones_map,
        existing_in_zone=existing_in_zone,
        known_ids=known_ids,
        config=cfg,
    )
    return ctx, zone1, zone2


def _corrected_key_pairs(raw_keys, normalized_keys):
    """Las parejas (forma escrita, forma canonica) donde una key marcadora
    [vocabulary.MARKER_KEYS] se corrigio DE VERDAD -- para el aviso de
    TEXTOS.md Sec.1.8 ("con una key corregida"). No incluye keys que
    desaparecieron por duplicado o por estar ya en el titular: esas no
    tienen una forma corregida que enseñar, simplemente no entraron.
    """
    normalized_set = set(normalized_keys)
    pairs = []
    for raw in raw_keys:
        canonical = MARKER_KEYS.get(raw.lower(), raw.lower())
        if canonical != raw.lower() and canonical in normalized_set:
            pairs.append((raw, canonical))
    return pairs


def _build_candidate(args, normalized_keys, zone1, zone2):
    # `args.issue` es `int | "none" | None` [`_issue_arg`] -- `Note.issue`
    # solo conoce `int | None` (el centinela "none" significa "sin
    # issue", igual que ausente, para todo lo que lee el campo aguas
    # abajo: `format.py`, `report_render_note.py`, `health.py`). La
    # distincion entre "ausente" y "none explicito" solo la necesita la
    # aduana de issues (`validator.validate_issue_gate`), que recibe
    # `args.issue` sin resolver por separado -- ver `main()`.
    issue = args.issue if isinstance(args.issue, int) else None
    return Note(
        type=args.type,
        id="",
        zone1=zone1,
        zone2=zone2,
        headline=args.headline,
        description=args.description or "",
        timestamp=datetime.now(timezone.utc),
        why=args.why,
        keys=normalized_keys,
        origin=tuple(args.origin),
        replaces=args.replaces,
        awaits=args.awaits,
        issue=issue,
        quote=args.quote,
    )


def _build_discard_candidates(discard_pairs, zone1, zone2):
    """Una nota `X` por pareja `(titular, porque)` de `--discard`, en la
    MISMA zona que la decision que las origina. `origin` se deja vacio a
    proposito -- ver cabecera del modulo."""
    return tuple(
        Note(
            type="X",
            id="",
            zone1=zone1,
            zone2=zone2,
            headline=headline,
            description=why,
            timestamp=datetime.now(timezone.utc),
        )
        for headline, why in discard_pairs
    )


def _print_success(result, args, normalized_keys):
    lines = [f"✅ {result.note_id} guardada"]
    corrected = _corrected_key_pairs(args.keys, normalized_keys)
    if corrected:
        plural = "s" if len(corrected) > 1 else ""
        lines[0] += f" — con {len(corrected)} key{plural} corregida{plural}"
        lines.append("")
        for raw, canonical in corrected:
            lines.append(f"  {raw}  →  {canonical}")
    print("\n".join(lines))


def _print_success_with_discards(decision_result, alternatives, discard_results, args, normalized_keys):
    """Sin molde en TEXTOS.md para esta salida -- forma corta, mismo tono
    que `_print_success`, reusando `TYPE_EMOJI["X"]` en vez de un literal
    nuevo. Reportada al propietario para aprobar o cambiar."""
    lines = [f"✅ {decision_result.note_id} guardada"]
    corrected = _corrected_key_pairs(args.keys, normalized_keys)
    suffixes = []
    if corrected:
        plural_k = "s" if len(corrected) > 1 else ""
        suffixes.append(f"con {len(corrected)} key{plural_k} corregida{plural_k}")
    plural_x = "s" if len(discard_results) != 1 else ""
    suffixes.append(f"con {len(discard_results)} alternativa{plural_x} descartada{plural_x}")
    lines[0] += " — " + ", ".join(suffixes)
    if corrected:
        lines.append("")
        for raw, canonical in corrected:
            lines.append(f"  {raw}  →  {canonical}")
    lines.append("")
    for alternative, result in zip(alternatives, discard_results):
        lines.append(f"  {TYPE_EMOJI['X']} {result.note_id}  {alternative.headline}")
    print("\n".join(lines))


def _handle_discard(candidate, args, normalized_keys, ctx, zone1, zone2):
    """Rama `--discard`: `notes.discard_alternatives()` escribe la
    decision y cada alternativa, cada una en su propio commit [PIEZAS.md
    Sec.8.1]. Si la decision falla, devuelve solo ese resultado. Si una
    alternativa rebota tras la decision, el resto sigue intentandose --
    este script solo reporta cada rechazo real, nunca inventa uno propio.
    """
    alternatives = _build_discard_candidates(args.discard, zone1, zone2)
    results = notes.discard_alternatives(candidate, alternatives, ctx)
    decision_result = results[0]

    if not decision_result.ok:
        if decision_result.rejections:
            for one_rejection in decision_result.rejections:
                print(rejection_.render_terminal(one_rejection))
            return 1
        print(f"git fallo al guardar la nota: {decision_result.git_error}", file=sys.stderr)
        return 1

    discard_results = results[1:]
    failed = [result for result in discard_results if not result.ok]
    if failed:
        for result in failed:
            if result.rejections:
                for one_rejection in result.rejections:
                    print(rejection_.render_terminal(one_rejection))
            else:
                print(f"git fallo al guardar un descarte: {result.git_error}", file=sys.stderr)
        return 1

    _print_success_with_discards(decision_result, alternatives, discard_results, args, normalized_keys)
    return 0


def _handle_write_or_replace(candidate, args, normalized_keys, ctx):
    """Rama sin `--discard`: `--promotes` [2026-08-05] tiene prioridad --
    si se dio, `notes.promote()` es la unica que se llama (asciende la Q
    citada, ver el docstring del modulo). Si no, `--replaces` distingue
    tres casos [TEXTOS.md Sec.1.6] -- ausente (nada se sustituye), el
    centinela literal "none" ("conviven las dos, a proposito" --
    `validator.validate_replacement`), o un ID real ("la sustituye" -- la
    vieja tiene que archivarse). Solo el tercero usa `notes.replace()`,
    la unica funcion que archiva la vieja en el mismo commit [PIEZAS.md
    Sec.8.1]; los otros dos siguen en `notes.write()` exactamente igual
    que antes -- `Note.replaces` viaja tal cual (`None` o `"none"`) hasta
    el commit, sin que `note.py` decida nada mas.
    """
    if args.promotes is not None:
        result = notes.promote(candidate, args.promotes, ctx)
    else:
        replaces_real_id = args.replaces is not None and args.replaces != "none"
        if replaces_real_id:
            result = notes.replace(candidate, args.replaces, ctx)
        else:
            result = notes.write(candidate, ctx)

    if not result.ok:
        if result.rejections:
            for one_rejection in result.rejections:
                print(rejection_.render_terminal(one_rejection))
            return 1
        print(f"git fallo al guardar la nota: {result.git_error}", file=sys.stderr)
        return 1

    _print_success(result, args, normalized_keys)
    return 0


def main(argv):
    args = _parse_args(argv)

    root = notes.repo_root()
    pm = notes.pm_root(root)
    ctx, zone1, zone2 = _build_context(pm, args.zones[0], args.zones[1])

    normalized_keys = validator.normalize_keys(tuple(args.keys), args.headline)
    candidate = _build_candidate(args, normalized_keys, zone1, zone2)

    pain_rejection = validator.validate_pain_question(candidate, args.stops)
    if pain_rejection is not None:
        print(rejection_.render_terminal(pain_rejection))
        return 1

    # La aduana de issues [D-065/D-066, 2026-08-26]: la vara de medir
    # antes de `validate_issue()` -- recibe `args.issue` SIN resolver
    # (`int | "none" | None`), la unica forma de distinguir "ausente" de
    # "none explicito" [ver docstring de `_build_candidate`].
    gate_rejection = validator.validate_issue_gate(candidate, args.issue, args.work)
    if gate_rejection is not None:
        print(rejection_.render_terminal(gate_rejection))
        return 1

    try:
        issue_rejection = validator.validate_issue(candidate, candidate.issue)
    except RuntimeError as exc:
        print(f"no se pudo comprobar la issue #{candidate.issue}: {exc}", file=sys.stderr)
        return 1
    if issue_rejection is not None:
        print(rejection_.render_terminal(issue_rejection))
        return 1

    # `--discard` es su propio flujo: la nota se escribe via
    # `notes.discard_alternatives()`, nunca via `write()`/`replace()`.
    if args.discard:
        return _handle_discard(candidate, args, normalized_keys, ctx, zone1, zone2)

    return _handle_write_or_replace(candidate, args, normalized_keys, ctx)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # nunca una traza de pila -- PIEZAS.md Sec.10
        print(f"note.py: {exc}", file=sys.stderr)
        sys.exit(1)
