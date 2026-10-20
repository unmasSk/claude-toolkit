#!/usr/bin/env python3
"""bin/memory/remove.py -- retira una nota (sale de su indice vigente y
entra en ARCHIVED.md) y, si se pide, hace nacer el muro que sale de una
incidencia.

    remove.py <ID> "<motivo>" --restriction no
    remove.py <ID> "<motivo>" --restriction new \\
        --restriction-text "..." --why "..."

`--restriction new` (solo incidencias) son dos commits: primero el cierre
de `<ID>`, despues -- solo si salio bien -- el muro R en la misma pareja de
zonas, con `Origin:` apuntando a `<ID>`.
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
    # Opcional: main() pregunta por el muro si una I llega sin el flag.
    parser.add_argument("--restriction", choices=("no", "new"), default=None)
    parser.add_argument("--restriction-text", default=None)
    parser.add_argument("--why", default=None)
    parser.add_argument("--commit", default=None)  # elige una nota de un id repetido (D-145)
    parser.add_argument("--replaces", default=None)  # el muro nuevo sustituye a este
    return parser.parse_args(argv)


def _empty_context():
    """Un `Context` vacio: `notes.close()` lo recibe pero no lo usa."""
    return validator.Context(
        zones={}, existing_in_zone=(), known_ids=frozenset(), config=config.Config(),
    )


def _build_fence_context(pm, zone1, zone2):
    """El `Context` del muro: las notas vivas de su zona, sin las archivadas.
    `known_ids` incluye las archivadas, porque el muro cita la incidencia que
    se acaba de cerrar.
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
    """La `Note` candidata del muro que nace de `incident`."""
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

    Devuelve la `Note` de la incidencia, o `None` si ya se imprimio el
    rechazo. El muro candidato pasa por `validator.validate_note()` aqui, para
    que la incidencia no quede cerrada sin su muro: o nacen las dos, o ninguna.
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
    # Se lee antes de cerrar: la zona del muro sale de la incidencia tal como estaba.
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
    target_problem = _replaces_target_problem(args.replaces, args.id, pm)
    if target_problem is not None:
        print(target_problem, file=sys.stderr)
        return None

    return incident


def _incident_note(args):
    """La nota de `args.id`; con `--commit`, la de ese commit (un id
    repetido puede tener cada nota en otras zonas). Sin `--commit`, la de
    la unica linea vigente, no la de una gemela ya archivada. `None` si no
    hay una sola.
    """
    if args.commit is None:
        return _live_incident_note(args.id) or query.by_id(args.id)
    found = [
        note for sha, note in query.commits_by_id(args.id)
        if notes_duplicate.sha_matches(sha, args.commit)
    ]
    return found[0] if len(found) == 1 else None


def _live_incident_note(note_id):
    """La nota del commit de la unica linea vigente de `note_id`, o `None`."""
    pm = notes.pm_root(notes.repo_root())
    index_name = TYPE_INDEX_FILES.get(note_id.split("-", 1)[0])
    live = [line for line in indexes.read(index_name, pm) if line.id == note_id] if index_name else []
    if len(live) != 1:
        return None
    return next(
        (note for _sha, note in query.commits_by_id(note_id) if notes_duplicate.same_note(note, live[0])),
        None,
    )


def _incident_label(args):
    if args.commit is None:
        return repr(args.id)
    return f"{args.id!r} con --commit {args.commit}"


def _replaces_target_problem(replaces, incident_id, pm):
    """El motivo por el que `--replaces` no apunta a una sola nota vigente
    distinta de la incidencia que se cierra, o `None` si si -- se mira
    antes de cerrar nada, para no dejar la incidencia cerrada y el muro sin
    nacer.
    """
    if replaces is None or replaces == "none":
        return None
    if replaces.lower() == incident_id.lower():
        return (
            f"remove.py: --replaces {replaces!r} es la incidencia que se cierra -- el muro "
            "nace de ella (Origin:), no la sustituye; no se ha tocado nada"
        )
    index_name = TYPE_INDEX_FILES.get(replaces.split("-", 1)[0])
    lines = indexes.read(index_name, pm) if index_name else ()
    line, duplicate = notes_duplicate.pick(
        replaces, lines, None, notes_duplicate.remove_relaunch(replaces)
    )
    if duplicate is not None:
        return rejection_.render_terminal(duplicate)
    if line is None:
        return f"remove.py: --replaces {replaces!r} no es una nota vigente -- no hay nada que sustituir"
    return None


def _headline_rejection_for_remove(args, rejection):
    """El rechazo del titular largo, con el Relanza cambiado a `gitmem remove`
    con todos los flags que se dieron: el `gitmem note` del validador
    escribiria un muro suelto sin cerrar la incidencia.
    """
    placeholder = f"<titular de hasta {validator.HEADLINE_MAX} caracteres>"
    return dataclasses.replace(rejection, relaunch=(_remove_command(args, text=placeholder),))


def _overlap_rejection_for_remove(args, rejection, candidate, ctx):
    """El rechazo del muro parecido, con el Relanza cambiado a `gitmem
    remove ... --replaces <el parecido>`: el `gitmem note R` del validador
    escribe un muro suelto y deja la incidencia abierta. La incidencia que
    se cierra nunca es el parecido (el muro nace de ella), ni otra I, X, Q o
    B; si no queda ninguno, el Relanza lleva `--replaces none`.
    """
    overlapping = similar.find_overlapping(candidate, ctx.existing_in_zone, threshold=SIMILARITY_THRESHOLD)
    others = [n.id for n in overlapping if n.id.lower() != args.id.lower() and validator.can_be_replaced(n)]
    replaces = others[0] if others else "none"
    return dataclasses.replace(rejection, relaunch=(_remove_command(args, replaces=replaces),))


def _remove_command(args, replaces=None, commit=None, text=None):
    """`gitmem remove` con todos los flags que se dieron, listo para pegar."""
    words = ["gitmem", "remove", args.id, args.reason]
    for flag, value in (
        ("--restriction", args.restriction),
        ("--restriction-text", text or args.restriction_text),
        ("--why", args.why),
        ("--replaces", replaces or args.replaces),
        ("--commit", commit or args.commit),
    ):
        if value is not None:
            words += [flag, value]
    return shlex.join(words)


def _fence_retry_command(args, incident):
    """El comando exacto, ejecutable tal cual, para relanzar SOLO el muro
    cuando el cierre ya quedo hecho. Toda R contesta `--stops yes`.
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
    """La R que sale de `incident`, en su misma pareja de zonas, con `Origin:`
    apuntando a la incidencia. Devuelve el codigo de salida.

    Si el muro no nace, el aviso dice primero que el cierre ya es permanente y
    da el comando para relanzar solo el muro.
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
    """Imprime por que fallo el cierre y devuelve 1."""
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
