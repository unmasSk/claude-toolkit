#!/usr/bin/env python3
"""bin/memory/remove.py -- retira una nota (retira su linea del indice
vigente, la anade a ARCHIVED.md) y, si se pide, hace nacer el muro que
sale de una incidencia.

Contrato: docs/memoria-v2/PIEZAS.md Sec.10 (fila `remove.py`) y Sec.10.1,
punto 2. Grammar de CLI [TEXTOS.md Sec.1.10, literal]:

    remove.py <ID> "<motivo>" --restriction no
    remove.py <ID> "<motivo>" --restriction new \\
        --restriction-text "..." --why "..."

`--restriction new` es DOS actos, DOS commits [Sec.10.1, punto 2, mismo
patron que `notes.discard_alternatives`: "un acto, un commit" aplica a
nota+indice, no al acto completo]: primero el cierre de `<ID>`
(`notes.close`), despues -- solo si el cierre salio bien -- el muro
nuevo (`notes.write`, tipo R, con `Origin:` apuntando a `<ID>`, en la
MISMA pareja de zonas que la incidencia que la origina). Si el cierre
falla, el muro no se intenta: no hay nada de que "salir".

Solo aplica a incidencias (`I-...`): es el unico tipo que TEXTOS.md
Sec.1.10 describe naciendo muro al cerrarse.
"""

import argparse
import dataclasses
import os
import shlex
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
import notes_duplicate  # noqa: E402
import query  # noqa: E402
import rejection as rejection_  # noqa: E402
import similar  # noqa: E402
import validator  # noqa: E402
import zones as zones_lib  # noqa: E402
from model import Note  # noqa: E402
from vocabulary import SIMILARITY_THRESHOLD, TYPE_INDEX_FILES  # noqa: E402


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="remove.py")
    parser.add_argument("id")
    parser.add_argument("reason")
    # Corregido 2026-08-04: antes required=True para TODO tipo de nota --
    # falso, incumplia P5: cerrar una I sin el flag revienta con el error
    # crudo de argparse en vez de la pregunta del molde [TEXTOS.md
    # Sec.1.10, decision del propietario]. Ahora opcional; main() decide
    # segun el tipo via validator.validate_incident_close_question.
    parser.add_argument("--restriction", choices=("no", "new"), default=None)
    parser.add_argument("--restriction-text", default=None)
    parser.add_argument("--why", default=None)
    parser.add_argument("--commit", default=None)  # elige una nota de un id repetido (D-145)
    parser.add_argument("--replaces", default=None)  # el muro nuevo sustituye a este
    return parser.parse_args(argv)


def _empty_context():
    """`notes.close()` recibe `ctx` por simetria de Superficie con
    `write()`/`replace()` pero no lo usa -- cerrar no crea ninguna nota
    nueva [notes.py, docstring de `close()`]. Ninguna de las cuatro ramas
    de un `Context` real se lee nunca para esta llamada.
    """
    return validator.Context(
        zones={}, existing_in_zone=(), known_ids=frozenset(), config=config.Config(),
    )


def _build_fence_context(pm, zone1, zone2):
    """2026-08-05: `existing_in_zone` se filtra contra
    `indexes.archived_ids(pm)` -- mismo arreglo y mismo porque que
    `bin/memory/note.py::_build_context()` (ver su docstring): el muro
    que nace aqui pasa por `validator.validate_note()`
    (`_guard_restriction_new`) y por `notes.write()`
    (`_create_fence`), las dos vias que llegan a
    `validate_replacement()` -- sin este filtro, un muro archivado hace
    meses seguia bloqueando uno nuevo parecido. `known_ids` se deja sin
    filtrar: el propio muro cita con `--origin {args.id}` la incidencia
    que el cierre de mas arriba en este mismo flujo acaba de archivar, y
    ese puntero tiene que seguir resolviendo como conocido.
    """
    zones_map = zones_lib.load(pm / "zones.json")
    archived = indexes.archived_ids(pm)
    existing_in_zone = tuple(
        n for n in query.by_zone(zone1, zone2) if n.id not in archived
    )
    known_ids = frozenset(n.id for n in query.by_zone(None, None))
    cfg = config.load(pm / "config.json")
    return validator.Context(
        zones=zones_map,
        existing_in_zone=existing_in_zone,
        known_ids=known_ids,
        config=cfg,
    )


def _build_fence_candidate(args, incident):
    """La `Note` candidata del muro que nace de `incident` -- construccion
    compartida entre el pre-chequeo de `_guard_restriction_new()` y el alta
    real de `_create_fence()`, para no escribirla dos veces [encargo del
    propietario, 2026-08-05: "si quiere apuntar un muro, tiene que
    apuntarse ese muro"].
    """
    return Note(
        type="R",
        id="",
        zone1=incident.zone1,
        zone2=incident.zone2,
        headline=args.restriction_text,
        description=args.restriction_text,
        timestamp=datetime.now(timezone.utc),
        why=args.why,
        origin=(args.id,),
        replaces=args.replaces,
    )


def _guard_restriction_new(args):
    """Comprobaciones previas de `--restriction new`, antes de tocar nada.

    Devuelve la `Note` real de la incidencia si todo esta en orden, o
    `None` si ya se imprimio el motivo del rechazo -- el llamador sale
    con 1 en ese caso, sin intentar cerrar nada.

    2026-08-05, encargo del propietario: ademas de las tres comprobaciones
    de forma de siempre, la `Note` candidata del muro se pasa por
    `validator.validate_note()` -- la MISMA funcion pura que `notes.write()`
    ya llama antes de comprometer nada -- para que un muro que la aduana va
    a rechazar (p.ej. titular de mas de 80 caracteres) no deje la
    incidencia cerrada sin su leccion al lado: o las dos cosas nacen, o
    ninguna.
    """
    if not args.id.startswith("I-"):
        print(
            f"remove.py: --restriction new solo aplica al cierre de una "
            f"incidencia (I-...); {args.id!r} no lo es",
            file=sys.stderr,
        )
        return None
    if not args.restriction_text:
        print(
            'remove.py: --restriction new exige --restriction-text "..."',
            file=sys.stderr,
        )
        return None
    # Se lee ANTES de cerrar -- el commit de la incidencia sigue en el
    # historial de git para siempre (cerrar solo retira la linea de
    # indice), pero leerlo aqui deja claro que la zona del muro sale de
    # la incidencia tal como estaba, no de un estado a medio cerrar.
    incident = _incident_note(args)
    if incident is None:
        print(
            f"remove.py: no se encontro {_incident_label(args)} en el historial de git "
            "-- no se puede saber en que zona nace el muro",
            file=sys.stderr,
        )
        return None

    root = notes.repo_root()
    pm = notes.pm_root(root)
    ctx = _build_fence_context(pm, incident.zone1, incident.zone2)
    candidate = _build_fence_candidate(args, incident)
    rejections = validator.validate_note(candidate, ctx)
    if rejections:
        headline = validator.validate_headline(candidate.headline)
        overlap = validator.validate_replacement(candidate, ctx.existing_in_zone)
        for one_rejection in rejections:
            if one_rejection == headline:
                one_rejection = _headline_rejection_for_remove(args, one_rejection)
            elif one_rejection == overlap:
                one_rejection = _overlap_rejection_for_remove(args, one_rejection, candidate, ctx)
            print(rejection_.render_terminal(one_rejection), file=sys.stderr)
        return None
    target_problem = _replaces_target_problem(args.replaces, pm)
    if target_problem is not None:
        print(target_problem, file=sys.stderr)
        return None

    return incident


def _incident_note(args):
    """La nota de `args.id`; con `--commit`, la de ese commit (un id
    repetido puede tener cada nota en otras zonas). `None` si no hay una sola.
    """
    if args.commit is None:
        return query.by_id(args.id)
    found = [
        note for sha, note in query.commits_by_id(args.id)
        if notes_duplicate.sha_matches(sha, args.commit)
    ]
    return found[0] if len(found) == 1 else None


def _incident_label(args):
    if args.commit is None:
        return repr(args.id)
    return f"{args.id!r} con --commit {args.commit}"


def _replaces_target_problem(replaces, pm):
    """El motivo por el que `--replaces` no apunta a una sola nota vigente,
    o `None` si si -- se mira antes de cerrar nada, para no dejar la
    incidencia cerrada y el muro sin nacer.
    """
    if replaces is None or replaces == "none":
        return None
    index_name = TYPE_INDEX_FILES.get(replaces.split("-", 1)[0])
    lines = indexes.read(index_name, pm) if index_name else ()
    line, duplicate = notes_duplicate.pick(
        replaces, lines, None,
        lambda sha: f'gitmem remove {replaces} "<motivo>" --commit {sha}',
    )
    if duplicate is not None:
        return rejection_.render_terminal(duplicate)
    if line is None:
        return f"remove.py: --replaces {replaces!r} no es una nota vigente -- no hay nada que sustituir"
    return None


def _headline_rejection_for_remove(args, rejection):
    """El rechazo del titular largo, con el Relanza cambiado a `gitmem
    remove` -- corregido 2026-10-19, hallazgo real: el de
    `validator.validate_headline()` propone `gitmem note <TIPO> ...`, que
    pegado tal cual escribe un muro suelto, sin `Origin:` y sin cerrar la
    incidencia: justo lo que `_guard_restriction_new()` existe para evitar.
    Se rehace solo el comando aqui, no en el validador: el camino de
    `gitmem note` tiene que seguir proponiendo su propio comando.

    El motivo y el porque van con `shlex.quote` -- corregido 2026-10-19,
    hallazgo real (Cerberus F1): entre comillas dobles crudas, un acento
    grave, un `$` o una `"` del texto los altera el shell al pegar el
    comando, y la nota guarda otra cosa de lo que se escribio.
    """
    command = (
        f"gitmem remove {args.id} {shlex.quote(args.reason)} --restriction new "
        f'--restriction-text "<titular de hasta {validator.HEADLINE_MAX} caracteres>"'
    )
    if args.why:
        command += f" --why {shlex.quote(args.why)}"
    return dataclasses.replace(rejection, relaunch=(command,))


def _overlap_rejection_for_remove(args, rejection, candidate, ctx):
    """El rechazo del muro parecido, con el Relanza cambiado a `gitmem
    remove ... --replaces <el parecido>`: el `gitmem note R` del validador
    escribe un muro suelto y deja la incidencia abierta.
    """
    first = similar.find_overlapping(candidate, ctx.existing_in_zone, threshold=SIMILARITY_THRESHOLD)[0]
    return dataclasses.replace(rejection, relaunch=(_remove_command(args, replaces=first.id),))


def _remove_command(args, replaces=None, commit=None):
    """`gitmem remove` con todos los flags que se dieron, listo para pegar."""
    words = ["gitmem", "remove", args.id, args.reason]
    for flag, value in (
        ("--restriction", args.restriction),
        ("--restriction-text", args.restriction_text),
        ("--why", args.why),
        ("--replaces", replaces or args.replaces),
        ("--commit", commit or args.commit),
    ):
        if value is not None:
            words += [flag, value]
    return shlex.join(words)


def _fence_retry_command(args, incident):
    """El comando exacto para volver a intentar SOLO el muro suelto --
    sin repetir el cierre, que ya es permanente -- misma gramatica de
    `note.py` [Sec.10, fila `note.py`]. Usado por `_create_fence()` si el
    muro no nace: ver su docstring para el porque.

    Ejecutable TAL CUAL, sin editar -- corregido 2026-08-03, hallazgo
    real: la version anterior omitia dos flags que `note.py` exige de
    verdad para un tipo R y el comando rebotaba dos veces si se pegaba
    literal (primero por la pregunta del dolor sin responder, despues por
    el campo obligatorio que falta). `--stops yes` responde la pregunta
    del dolor [`validator.validate_pain_question`]: no hace falta
    preguntarla, porque `_create_fence()` (mas abajo en este fichero)
    siempre construye una `Note(type="R", ...)`, y toda R contesta "si".
    `--description` es obligatorio para el tipo R
    [`vocabulary.TYPES["R"].required_fields`] -- lleva el MISMO texto que
    `_create_fence()` usa de verdad al escribir el muro
    (`description=args.restriction_text`), asi que no hay ningun hueco
    que rellenar: el dato ya esta disponible aqui. `--searched` lleva el
    hueco a rellenar, como el resto de relanzamientos [D-098].

    El texto del muro y el porque van con `shlex.quote` -- corregido
    2026-10-19, hallazgo real (gemelo de Cerberus F1): entre comillas
    dobles crudas, un acento grave, un `$` o una `"` los altera el shell
    al pegar, y el comando dejaba de ser ejecutable tal cual.
    """
    text = shlex.quote(args.restriction_text)
    command = f"gitmem note R --zones {incident.zone1} {incident.zone2} {text}"
    if args.why:
        command += f" --why {shlex.quote(args.why)}"
    command += f" --description {text} --stops yes"
    command += f" --origin {args.id}"
    if args.replaces is not None:
        command += f" --replaces {args.replaces}"
    command += validator.searched_suffix(validator.SEARCHED_PLACEHOLDER)
    return command


def _create_fence(args, incident):
    """La R que sale de `incident`, en su misma pareja de zonas, con
    `Origin:` apuntando a la incidencia -- decision del propietario
    [PIEZAS.md Sec.10.1, punto 2]. Devuelve el codigo de salida.

    **Si el muro no nace, el aviso deja claro que el cierre YA es
    permanente** -- corregido 2026-08-02, hallazgo real: `main()` ya
    imprimio "✅ <ID> archivada" (el cierre se comiteo de verdad, no hay
    vuelta atras) antes de llegar aqui; un fallo aqui abajo (p.ej. un
    titular de mas de 80 caracteres) salia con codigo 1 sin decir que el
    cierre ya quedo guardado -- quien mirase solo el codigo de salida
    reintentaria el comando ENTERO, y el segundo intento fallaria de otra
    forma porque `<ID>` ya no esta en su indice [demostrado ejecutando].
    Por eso el aviso nombra el estado real primero, y da el comando EXACTO
    para relanzar solo el muro, sin repetir un cierre que ya no hace falta.
    """
    root = notes.repo_root()
    pm = notes.pm_root(root)
    ctx = _build_fence_context(pm, incident.zone1, incident.zone2)

    fence = _build_fence_candidate(args, incident)
    if args.replaces not in (None, "none"):
        fence_result = notes.replace(fence, args.replaces, ctx)
    else:
        fence_result = notes.write(fence, ctx)
    if not fence_result.ok:
        print(
            f"⚠️ {args.id} ya quedó cerrada de forma permanente -- el muro "
            "nuevo NO nació:",
            file=sys.stderr,
        )
        if fence_result.rejections:
            for one_rejection in fence_result.rejections:
                print(rejection_.render_terminal(one_rejection))
        else:
            print(f"git fallo al crear el muro: {fence_result.git_error}", file=sys.stderr)
        print(f"Relanza solo el muro con: {_fence_retry_command(args, incident)}", file=sys.stderr)
        return 1

    print(f"⚠️ {fence_result.note_id} guardada — muro nacido de {args.id}")
    return 0


def _report_close_failure(close_result, note_id):
    """Imprime por que fallo el cierre y devuelve 1 -- extraida de
    `main()` el 2026-08-04 para mantenerla bajo 50 LOC al anadir el
    manejo de `close_result.rejections` (antes `close()` nunca devolvia
    un rechazo real, asi que esta rama solo miraba `git_error`; un
    rechazo real -- motivo con salto de linea, ver
    `notes.py::_reject_close_reason_multiline` -- habria impreso "None").
    """
    if close_result.rejections:
        for one_rejection in close_result.rejections:
            print(rejection_.render_terminal(one_rejection), file=sys.stderr)
        return 1
    print(f"git fallo al cerrar {note_id}: {close_result.git_error}", file=sys.stderr)
    return 1


def _archived_count(note_id):
    """Cuantas lineas de `note_id` tiene ARCHIVED.md ahora -- leido del
    fichero, no supuesto, para contar lo que el cierre archivo de verdad.
    """
    pm = notes.pm_root(notes.repo_root())
    if not (pm / "ARCHIVED.md").exists():
        return 0
    return sum(1 for line in indexes.read_archive(pm) if line.id == note_id)


def _refuse_unanswered_incident(args):
    """Una I cerrada sin `--restriction`: imprime la pregunta del molde
    [TEXTOS.md Sec.1.10], o el fallo si la incidencia no esta en el
    historial (nunca se cierra sin preguntar). `True` si se nego.
    """
    incident = _incident_note(args)
    if incident is None:
        print(
            f"remove.py: no se encontro {_incident_label(args)} en el "
            "historial de git -- no se puede saber si de esta incidencia "
            "nace un muro",
            file=sys.stderr,
        )
        return True
    question = validator.validate_incident_close_question(incident, args.restriction)
    if question is None:
        return False
    if args.commit is not None:
        suffix = f" --commit {shlex.quote(args.commit)}"
        question = dataclasses.replace(question, relaunch=tuple(c + suffix for c in question.relaunch))
    print(rejection_.render_terminal(question), file=sys.stderr)
    return True


def main(argv):
    args = _parse_args(argv)

    if args.replaces is not None and args.restriction != "new":
        print(
            "remove.py: --replaces solo vale con --restriction new (sin muro nuevo "
            "no hay nada que sustituya a otra nota) -- no se ha tocado nada",
            file=sys.stderr,
        )
        return 1
    incident = None
    if args.restriction == "new":
        incident = _guard_restriction_new(args)
        if incident is None:
            return 1
    elif args.restriction is None and args.id.startswith("I-") and _refuse_unanswered_incident(args):
        return 1

    archived_before = _archived_count(args.id)
    close_result = notes.close(
        args.id, args.reason, _empty_context(), commit=args.commit,
        relaunch_for=lambda sha: _remove_command(args, commit=sha),
    )
    if not close_result.ok:
        return _report_close_failure(close_result, args.id)

    archived = _archived_count(args.id) - archived_before
    print(f"✅ {args.id} archivada — closed: {args.reason} · notas archivadas: {archived}")

    if args.restriction != "new":
        return 0

    return _create_fence(args, incident)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # nunca una traza de pila -- PIEZAS.md Sec.10
        print(f"remove.py: {exc}", file=sys.stderr)
        sys.exit(1)
