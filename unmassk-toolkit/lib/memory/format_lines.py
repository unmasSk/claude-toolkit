"""La linea de indice y la linea de archivo -- partido fuera de format.py
por tamano [DEUDA.md punto 12: 519 lineas, techo 500].

Este fichero NO es una segunda pareja productor<->consumidor: sigue
habiendo una sola implementacion de "construir y parsear"
[PIEZAS.md Sec.6.4]. `format.py` importa estos cuatro nombres de aqui de
forma PLANA [PIEZAS.md Sec.3.3bis] y los reexpone bajo el mismo nombre,
asi que `format.build_index_line` / `format.parse_index_line` /
`format.build_archive_line` / `format.parse_archive_line` siguen
funcionando exactamente igual para cualquiera que los llame -- ninguna
firma ni nombre cambia. Solo `indexes.py` los llama hoy, se verifico
antes de partir.

QUE ES LO QUE SE PARTIO, Y POR QUE ESTE CORTE Y NO OTRO: de las cinco
parejas build/parse de `format.py`, estas dos son las unicas que no usan
`_fold_raw`/`_fold`/`_encode_list`/`_decode_list` (el plegado de campos
largos y el escapado de listas) ni componen `build_subject`/
`parse_subject` como hace `build_message`/`parse_message`. Sacarlas no
deja ningun ayudante compartido a caballo entre dos ficheros: `format.py`
sigue teniendo TODOS los ayudantes de plegado en un solo sitio, junto a
las tres parejas que si los usan (titular, mensaje, contexto de cierre).
Import en un solo sentido -- este fichero no importa nada de `format.py`
-- para que no haya ciclo.

QUE NO HACE. No valida contenido de negocio (eso es `validator`, fase
posterior). Los parsers nunca lanzan: devuelven `None` ante una linea que
no es la suya, nunca una excepcion y nunca una adivinanza, mismo
principio que el resto de `format.py` [PIEZAS.md Sec.6.4].

**El separador `  ->  ` de la linea de archivo es inequivoco aunque el
titular lo contenga**: `parse_archive_line` no busca la PRIMERA aparicion
del separador (eso es lo que rompia con un titular como "rename
colors.py  ->  emojis.py") -- exige que lo que sigue al separador empiece
por uno de los tres destinos literales del vocabulario cerrado
(`replaced by `/`closed: `/`promoted to `, derivados de
`_ARCHIVE_DESTINATIONS`, la misma tabla que usa `build_archive_line`),
asi que una aparicion del separador dentro del propio titular (que no va
seguida de ese vocabulario) no puede confundirse con el separador real.

No importa nada fuera de la biblioteca estandar de Python y de sus
hermanos de `lib/memory/` [PIEZAS.md Sec.13], importados PLANOS
[PIEZAS.md Sec.3.3bis].
"""

import re
from datetime import datetime

import emojis
from model import ArchiveLine, IndexLine, Note

# ---------------------------------------------------------------------------
# Linea de indice: "[D-030][product][auth] headline" -- sin emoji, sin fecha
# (TEXTOS Sec.4 "Regla comun"; TEXTOS Sec.6 punto 6).
# ---------------------------------------------------------------------------

_INDEX_LINE_RE = re.compile(
    r"^\[(?P<id>[A-Z]-\d+)\]\[(?P<zone1>[^\]]+)\]\[(?P<zone2>[^\]]+)\]\s+(?P<headline>.+)$"
)


def build_index_line(note: Note) -> str:
    return f"[{note.id}][{note.zone1}][{note.zone2}] {note.headline}"


def parse_index_line(line: str) -> IndexLine | None:
    try:
        match = _INDEX_LINE_RE.match(line)
        if match is None:
            return None
        return IndexLine(
            id=match.group("id"),
            zone1=match.group("zone1"),
            zone2=match.group("zone2"),
            headline=match.group("headline"),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Linea de archivo (ARCHIVED.md, TEXTOS Sec.4):
# "date  [id][zone1][zone2] emoji headline  ->  destino"
# Los tres destinos literales, y solo esos tres: "replaced by <ID>" /
# "closed: <motivo>" / "promoted to <ID>".
# ---------------------------------------------------------------------------

_ARCHIVE_DESTINATIONS = (
    ("replaced", "replaced by "),
    ("closed", "closed: "),
    ("promoted", "promoted to "),
)

# El grupo `phrase` solo casa si, tras el separador, sigue uno de los tres
# prefijos del vocabulario cerrado -- asi una aparicion del separador
# DENTRO del propio titular (que no va seguida de ese vocabulario) nunca
# se confunde con el separador real, sin importar cuantas veces aparezca
# el titular.
_ARCHIVE_PHRASE_ALTERNATION = "|".join(re.escape(prefix) for _, prefix in _ARCHIVE_DESTINATIONS)

_ARCHIVE_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})  "
    r"\[(?P<id>[A-Z]-\d+)\]\[(?P<zone1>[^\]]+)\]\[(?P<zone2>[^\]]+)\]"
    r"\s+(?P<emoji>\S+)\s+(?P<headline>.+)  →  "
    rf"(?P<phrase>(?:{_ARCHIVE_PHRASE_ALTERNATION}).+)$"
)


def build_archive_line(note: Note, destination: str, detail: str) -> str:
    emoji = emojis.TYPE_EMOJI[note.type]
    date_str = note.timestamp.date().isoformat()
    # Vocabulario cerrado de tres destinos, la misma tabla que usa el
    # parser: un `destination` fuera de esos tres revienta con KeyError
    # en vez de componerse con un repuesto de pinta valida -- mismo
    # principio que `emojis.TYPE_EMOJI[note.type]` ya aplica arriba.
    phrase_by_destination = {dest: f"{prefix}{detail}" for dest, prefix in _ARCHIVE_DESTINATIONS}
    phrase = phrase_by_destination[destination]
    return (
        f"{date_str}  [{note.id}][{note.zone1}][{note.zone2}] {emoji} "
        f"{note.headline}  →  {phrase}"
    )


def parse_archive_line(line: str) -> ArchiveLine | None:
    try:
        match = _ARCHIVE_LINE_RE.match(line)
        if match is None:
            return None

        phrase = match.group("phrase")
        destination = None
        detail = None
        for dest, prefix in _ARCHIVE_DESTINATIONS:
            if phrase.startswith(prefix):
                destination = dest
                detail = phrase[len(prefix):]
                break
        if destination is None:
            return None

        note_id = match.group("id")
        date_value = datetime.strptime(match.group("date"), "%Y-%m-%d").date()

        return ArchiveLine(
            date=date_value,
            type=note_id.split("-", 1)[0],
            id=note_id,
            zone1=match.group("zone1"),
            zone2=match.group("zone2"),
            headline=match.group("headline"),
            destination=destination,
            destination_detail=detail,
        )
    except Exception:
        return None
