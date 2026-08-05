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
from model import Note  # noqa: E402


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
    incident = query.by_id(args.id)
    if incident is None:
        print(
            f"remove.py: no se encontro {args.id!r} en el historial de git "
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
        for one_rejection in rejections:
            print(rejection_.render_terminal(one_rejection), file=sys.stderr)
        return None

    return incident


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
    que rellenar: el dato ya esta disponible aqui.
    """
    command = (
        f'gitmem note R --zones {incident.zone1} {incident.zone2} '
        f'"{args.restriction_text}"'
    )
    if args.why:
        command += f' --why "{args.why}"'
    command += f' --description "{args.restriction_text}" --stops yes'
    command += f" --origin {args.id}"
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


def main(argv):
    args = _parse_args(argv)

    incident = None
    if args.restriction == "new":
        incident = _guard_restriction_new(args)
        if incident is None:
            return 1
    elif args.restriction is None and args.id.startswith("I-"):
        # Anadido 2026-08-04: antes esta rama no existia -- una I sin
        # --restriction no llegaba aqui nunca (el flag era required=True,
        # argparse reventaba antes de que main() corriera). Ahora se
        # pregunta con el molde real [TEXTOS.md Sec.1.10] antes de cerrar.
        incident = query.by_id(args.id)
        if incident is None:
            # Corregido 2026-08-04, hallazgo de Cerberus (T1, fallo
            # callado): si el indice esta desincronizado del historial de
            # git (p.ej. tras un rebase o una edicion a mano) esta rama
            # caia directo a notes.close() sin preguntar jamas si de la
            # incidencia nace un muro -- que es todo el proposito de este
            # camino [TEXTOS.md Sec.1.10]. Salia "✅ ... archivada" con
            # codigo 0 sin haber hecho la pregunta ni una vez. Mismo caso
            # que _guard_restriction_new() (mas arriba en este fichero) ya
            # cubre con fallo en alto; esta rama nueva no lo habia reusado.
            print(
                f"remove.py: no se encontro {args.id!r} en el historial de "
                "git -- no se puede saber si de esta incidencia nace un "
                "muro",
                file=sys.stderr,
            )
            return 1
        question = validator.validate_incident_close_question(
            incident, args.restriction
        )
        if question is not None:
            print(rejection_.render_terminal(question), file=sys.stderr)
            return 1

    close_result = notes.close(args.id, args.reason, _empty_context())
    if not close_result.ok:
        return _report_close_failure(close_result, args.id)

    print(f"✅ {args.id} archivada — closed: {args.reason}")

    if args.restriction != "new":
        return 0

    return _create_fence(args, incident)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # nunca una traza de pila -- PIEZAS.md Sec.10
        print(f"remove.py: {exc}", file=sys.stderr)
        sys.exit(1)
