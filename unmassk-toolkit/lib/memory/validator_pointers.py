"""Los punteros (Replaces/Origin) apuntan a notas que existen, y un
muro (R) no nace sin decir de que incidencia sale -- partido fuera de
`validator.py` por tamano [mismo techo, mismo motivo que
`validator_zones.py`/`validator_issue.py`: DEUDA.md punto 14, "552
lineas, techo 500"; con esta pieza dentro, `validator.py` habria pasado
el mismo techo una tercera vez, esta con el banco adversarial,
PIEZAS.md Sec.14].

Este fichero NO es una segunda pieza ni una segunda puerta de
validacion: sigue habiendo una sola implementacion de "esto es valido"
[PIEZAS.md Sec.7.5]. `validator.py` importa `validate_pointers` de aqui
de forma PLANA [PIEZAS.md Sec.3.3bis] y lo reexpone bajo el mismo
nombre, asi que `validator.validate_pointers` sigue funcionando
exactamente igual para cualquiera que lo llame.

QUE ES LO QUE SE PARTIO, Y POR QUE ESTE CORTE Y NO OTRO: las dos formas
en que un puntero rebota -- cita un identificador que no existe, o es
una R que nace sin ninguna incidencia detras -- son un mismo asunto (la
legalidad del PUNTERO), y no comparten datos con el resto de
`validator.py` mas alla de la propia `Note` y el conjunto de
identificadores conocidos.

**``existing_in_zone`` [anadido 2026-08-02, banco adversarial,
PIEZAS.md Sec.14 fila 2 -- ASUNCION DE FIRMA, disclosed en el docstring
de `validator.py`]:** la tabla del banco dice que la fila 2 la caza
`validate_pointers`, pero la firma de produccion original
(`validate_pointers(note, known_ids)`) no podia "listar todas las
incidencias candidatas de la zona" -- `known_ids` es un
`frozenset[str]` sin contenido descriptivo. Se resuelve con un tercer
parametro, `existing_in_zone: tuple[Note, ...] = ()` (mismo nombre que
ya usa `validate_replacement`, mismo dato que ya trae `Context`): si
`note` es una R con `origin` vacio y hay al menos una incidencia (`I`)
candidata en `existing_in_zone`, rebota listandolas TODAS -- "la aduana
presenta todas las incidencias candidatas de la zona, nunca una sola
preseleccionada" [spec-sistema-memoria-v2.md Sec.4]. `--origin none`
(mismo sentinela literal que `--replaces none` ya usa) sigue sin
rebotar: `note.origin` deja de estar vacio. Una zona sin ninguna
incidencia candidata tampoco rebota -- no hay nada que citar, y forzar
la pregunta ahi no protegeria nada. `validator.validate_note` pasa
`ctx.existing_in_zone` como tercer argumento -- unico cambio de
comportamiento en produccion que trae esta partida.

QUE NO HACE. No decide el tipo de nota, las zonas, los campos, la
sustitucion, la pregunta del dolor, la destilacion ni la issue -- todo
eso sigue en `validator.py`/`validator_zones.py`/`validator_issue.py`.
No abre ficheros ni llama a git [PIEZAS.md Sec.7.5, misma restriccion
que el resto de la pieza].

No importa nada fuera de la biblioteca estandar de Python y de sus
hermanos de `lib/memory/` [PIEZAS.md Sec.13], importados PLANOS
[PIEZAS.md Sec.3.3bis].
"""

import re

from model import Note, Rejection
import rejection as rejection_

# La FORMA de un identificador de nota real: LETRA-NUMERO (ej. "D-030"),
# nunca un hash de commit v1 (ej. "4f2a1bc") citado en `origin` para una
# destilacion [TEXTOS.md Sec.1.7] -- un hash de git no tiene guion y por
# tanto nunca casa esta forma. La deteccion de forma es insensible a
# mayusculas/minusculas y a espacios de sobra (se aplica sobre
# `pointer.strip()` en modo IGNORECASE): un identificador real escrito
# casi bien -- "d-030", "D-030 ", " D-030" -- tiene forma de identificador
# igual que "D-030". Casar la FORMA no significa pasar la comprobacion:
# el puntero que case se sigue verificando contra `known_ids` con su
# valor SIN normalizar, asi que solo el texto exacto se acepta y
# cualquier variante de mayuscula o espacio rebota como colgante.
_NOTE_ID_PATTERN = re.compile(r"^[DMRQXIB]-\d+$", re.IGNORECASE)


def validate_pointers(
    note: Note,
    known_ids: frozenset[str],
    existing_in_zone: tuple[Note, ...] = (),
) -> Rejection | None:
    """Los identificadores citados (Replaces/Origin) existen de verdad, y
    un muro (R) no nace sin decir de que incidencia sale.

    Solo se comprueban los punteros que tienen forma de identificador de
    nota (``LETRA-NUMERO``, sin importar mayusculas ni espacios de sobra)
    -- ver `_NOTE_ID_PATTERN` arriba. La comprobacion en si es siempre
    contra el valor SIN normalizar: un puntero con esa forma pero mal
    escrito (mayuscula distinta, espacio de mas) no esta tal cual en
    `known_ids` y rebota como colgante -- no se corrige solo.
    """
    missing = []
    if (
        note.replaces is not None
        and note.replaces != "none"
        and note.replaces not in known_ids
    ):
        missing.append(note.replaces)
    for pointer in note.origin:
        if _NOTE_ID_PATTERN.match(pointer.strip()) and pointer not in known_ids:
            missing.append(pointer)

    if missing:
        noun = "un identificador" if len(missing) == 1 else "identificadores"
        what = f"cita {noun} que no existe: {', '.join(missing)}"
        options = (
            "Los punteros (Replaces/Origin) tienen que apuntar a notas que existen de verdad.",
        )
        command = (
            f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
            f'"{note.headline}" --description "..."',
        )
        return rejection_.build(
            kind="dangling_pointer", what=what, options=options, command=command
        )

    if note.type == "R" and not note.origin:
        candidates = tuple(n for n in existing_in_zone if n.type == "I")
        if candidates:
            return _reject_restriction_without_incident(note, candidates)

    return None


def _reject_restriction_without_incident(
    note: Note, candidates: tuple[Note, ...]
) -> Rejection:
    """[PIEZAS.md Sec.14 fila 2, "variante de origen" de TEXTOS.md
    Sec.1.6] Un muro que nace sin decir de que incidencia sale, con al
    menos una candidata real en la zona.
    """
    what = f"este muro nace sin decir de que incidencia sale, en [{note.zone1}][{note.zone2}]"
    options = [
        f"Al nacer un muro, la aduana presenta todas las incidencias candidatas de "
        f"[{note.zone1}][{note.zone2}] -- decide con calma cual, si alguna, la origina:",
        "",
    ]
    for candidate in candidates:
        options.append(
            f"  {candidate.id}   {candidate.timestamp.date().isoformat()}   "
            f"{candidate.headline}"
        )
    options.append("")
    options.extend(
        [
            "Dos salidas:",
            "",
            "  cita una o varias   --origin <id1> <id2> ...   el muro queda enlazado",
            "  ninguna encaja      --origin none               el muro nace sin incidencia",
        ]
    )
    first_id = candidates[0].id
    command = (
        f'gitmem note R --zones {note.zone1} {note.zone2} '
        f'"{note.headline}" --description "..." --origin {first_id}',
    )
    return rejection_.build(
        kind="restriction_without_incident", what=what, options=tuple(options), command=command
    )


# 2026-08-05, encargo del propietario: el ciclo intento -> rechazo ->
# relanzamiento no convergia -- cada rechazo construia su `command` mirando
# solo lo que EL necesitaba y perdia las respuestas que un rechazo anterior
# ya habia arrancado (`--stops`, `--origin`, `--replaces`, `--awaits`).
# Vive aqui, no en `validator.py` (en su techo de 500 lineas): `--origin`/
# `--replaces` son exactamente los dos punteros que este fichero ya valida,
# y comparten el mismo problema con los otros dos flags de respuesta.
# Reexportado PLANO como el resto de esta pieza [PIEZAS.md Sec.3.3bis]. No
# decide nada (no produce `Rejection`, no es "esto es valido") -- solo
# vuelve a imprimir, sin inventar, lo que `note` YA trae.
def carry_answer_flags(note: Note, *, skip: frozenset[str] = frozenset()) -> str:
    """Los flags ``--stops``/``--origin``/``--replaces``/``--awaits`` que
    ``note`` YA trae, listos para pegar en un comando de relanzamiento --
    nunca fabrica un valor que el usuario no dio. ``--stops`` no es un
    campo de ``Note``; se deriva del tipo (R -> "yes", M -> "no"), que solo
    llega a ser R/M si la pregunta del dolor ya se contesto de forma
    consistente [`validate_pain_question`]. ``skip`` excluye el flag que el
    propio rechazo que llama ya construye a mano (p.ej. ``overlapping_note``
    ya pone su propio ``--replaces``).
    """
    parts = []
    if "--stops" not in skip and note.type in ("M", "R"):
        parts.append(f' --stops {"yes" if note.type == "R" else "no"}')
    if "--origin" not in skip and note.origin:
        parts.append(f' --origin {" ".join(note.origin)}')
    if "--replaces" not in skip and note.replaces is not None:
        parts.append(f' --replaces {note.replaces}')
    if "--awaits" not in skip and note.awaits is not None and note.awaits.strip():
        parts.append(f' --awaits "{note.awaits}"')
    return "".join(parts)
