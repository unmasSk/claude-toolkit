"""Construir y parsear -- la pareja productor<->consumidor del sistema de
memoria v2. Contrato en docs/memoria-v2/PIEZAS.md Sec.6.4.

Cada `build_*` tiene su `parse_*`. No hay ninguno suelto -- esa simetria
es el contrato. Los textos literales que este modulo produce y consume
estan en docs/memoria-v2/TEXTOS.md Sec.4 (lineas de indice y de archivo)
y Sec.5 (los siete commits y el contexto de cierre).

**La pareja de la linea de indice y la de la linea de archivo viven en
`format_lines.py`** -- partido por tamano [DEUDA.md punto 12], ver el
docstring de ese fichero para el porque de ese corte y no otro. Se
importan de forma PLANA y se reexponen aqui bajo el mismo nombre
[PIEZAS.md Sec.3.3bis], asi que `format.build_index_line`,
`format.parse_index_line`, `format.build_archive_line` y
`format.parse_archive_line` siguen alcanzables desde este modulo sin que
cambie una firma.

**No valida contenido de negocio** (longitud de titular, zonas
conocidas, etc.) -- quien lo rechaza es `validator` (que no existe
todavia -- fase posterior). Eso es lo que permite leer notas viejas sin
que las reglas de hoy lo impidan. **Si valida forma**: un tipo de nota o
un destino de archivo fuera del vocabulario cerrado (siete tipos,
tres destinos) revienta en alto -- mismo principio que
`emojis.TYPE_EMOJI[note.type]` ya aplicaba de partida: un valor fuera
del vocabulario no se sustituye por un repuesto con pinta de valido.

**Los parsers nunca lanzan.** Ante una linea que no es de las suyas
devuelven `None`, nunca una excepcion y nunca una adivinanza -- un
`ARCHIVED.md` con una linea escrita a mano no puede tumbar el arranque
entero. Cada `parse_*` envuelve su cuerpo entero en un `try/except
Exception` como red de seguridad (p.ej. un `strptime` sobre una fecha
sintacticamente valida pero imposible como "2026-13-99" fallaria con
`ValueError` si el resto de la linea llegara a encajar) -- la regla
"nunca lanza" pesa mas que la economia de no envolver.

**Formato del titular** (TEXTOS Sec.5, TEXTOS Sec.6 punto 8 -- correccion
expresa del propietario, 2026-08-02): el emoji va DESPUES de los
corchetes de cierre, nunca antes:

    [D-030][product][auth] (emoji) login with JWT + Google OAuth

**`_SubjectParts`** es el tipo de retorno de `parse_subject`. No aparece
entre las trece clases de `model.py` (PIEZAS Sec.5.3) ni se describe en
ningun otro sitio del contrato -- vive aqui, en el modulo que lo produce
y consume, porque es un detalle interno de como `parse_message` separa
el titular del cuerpo, no una forma que otra pieza del sistema necesite
nombrar. Marcada interna con guion bajo (2026-08-04): el detector de
codigo muerto de `test_boundary.py` la daba con 0 usos externos al
fichero y 0 tests que la nombren directamente -- no estaba muerta (la
construye `parse_subject` en este mismo modulo), solo de cara al
publico sin que nadie de fuera la usara. El renombrado no cambia
comportamiento, solo deja de pedir un nombre publico que nadie necesita
fuera de este fichero.

**`Note.timestamp` no viaja en el texto** (ninguna plantilla de TEXTOS
Sec.5 lo declara como campo -- PIEZAS Sec.5.3 dice que su fuente de
verdad es la fecha de autor de git, no el cuerpo del commit). Por eso
`build_message`/`build_context_message` no lo escriben en ningun sitio
del texto, y `parse_message`/`parse_context_message` no tienen forma de
recuperarlo de un texto que nunca lo llevo -- devuelven
`datetime.now(timezone.utc)` como marcador de posicion. Quien necesite
el timestamp real (la fecha de autor del commit git) lo obtiene aparte,
de git, y reconstruye la `Note` con ese valor si hace falta; esa
composicion es responsabilidad de quien llama (`notes`/`query`), no de
esta pieza, que solo conoce el texto.

**El orden de los campos del cuerpo** vive en UNA sola constante,
`_BODY_FIELD_ORDER`: de ahi sale tanto el regex que reconoce cada campo
al parsear como el orden real en que `build_message` los escribe
(`_body_field_line` es el unico sitio que sabe como se codifica cada
uno). Antes habia una tercera copia muda del mismo orden, sin lector --
se elimino en vez de dejarla como una verdad que nadie comprobaba contra
las otras dos. Un campo ausente (`None`, o tupla vacia en `keys`/
`origin`) no escribe su linea -- no hay "Origin: " vacio en ningun
ejemplo de TEXTOS.md.

**Continuacion de campos largos, y el mismo mecanismo para el titular y
los puntos de contexto**: si el valor de un campo de texto libre
(`Why`/`Description`/`Awaits`), el titular de una nota, o un punto del
contexto de cierre trae saltos de linea propios, cada linea despues de
la primera se escribe precedida de un unico espacio de continuacion (el
mismo estilo visual de TEXTOS Sec.5). `_fold_raw` es el unico sitio que
sabe construir esto; `parse_message`/`parse_subject`/
`parse_context_message` lo deshacen exactamente: cualquier linea que
empiece por ese espacio y no sea el arranque de un campo/punto conocido
se pega, sin ese espacio, al valor anterior con un salto de linea -- por
construccion (siempre exactamente un espacio) esto es una vuelta exacta,
sin perdida, cualquiera que sea el contenido. Esto es lo que permite que
un titular o un punto de contexto con un `\\n` embebido sobreviva el
round trip en vez de partir el mensaje en una linea huerfana que tumba
el parseo entero.

**Listas (`Keys`/`Origin`) escapan su separador**: se codifican con
`_encode_list`/`_decode_list`, que escapan `\\` y `,` caracter a
caracter en vez de un `", ".join()`/`.split(", ")` sin escapar -- un
item que trae literalmente `", "` dentro (p.ej. una key `"a, b"`) ya no
se parte en entradas de mas.

**La linea de indice, la de archivo y el separador `  ->  ` inequivoco
del archivo** se documentan en `format_lines.py` -- ver ese fichero.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import emojis
from format_lines import build_archive_line, build_index_line, parse_archive_line, parse_index_line
from model import ContextNote, Note

# ---------------------------------------------------------------------------
# Helpers de plegado (folding) y de listas escapadas -- compartidos por
# titular, cuerpo y contexto de cierre. Ver docstring del modulo.
# ---------------------------------------------------------------------------


def _fold_raw(prefix: str, value: str) -> str:
    """Antepone `prefix` a la primera linea de `value`; cada salto interno
    se escribe en su propia linea, precedida de un unico espacio de
    continuacion. Reversible sin perdida cualquiera que sea el contenido
    de `value` (nunca cero espacios, nunca mas de uno, por construccion).
    """
    parts = value.split("\n")
    out = [f"{prefix}{parts[0]}"]
    out.extend(f" {cont}" for cont in parts[1:])
    return "\n".join(out)


def _fold(label: str, value: str) -> str:
    """`Label: primera linea` + continuacion -- ver `_fold_raw`."""
    return _fold_raw(f"{label}: ", value)


def _escape_list_item(item: str) -> str:
    """Escapa `\\` y `,` para que `item` sobreviva el join/split de listas
    (Keys/Origin) contenga lo que contenga -- el backslash se escapa
    primero para que la inversa (`_decode_list`) pueda leer de izquierda
    a derecha sin ambiguedad.
    """
    return item.replace("\\", "\\\\").replace(",", "\\,")


def _encode_list(items: tuple[str, ...]) -> str:
    return ", ".join(_escape_list_item(item) for item in items)


def _decode_list(text: str) -> tuple[str, ...]:
    """Inversa exacta de `_encode_list`: recorre `text` caracter a caracter
    -- nunca con un regex de separador -- para que una `,` escapada
    dentro de un item nunca se confunda con el separador real `", "`
    entre items.
    """
    items: list[str] = []
    current: list[str] = []
    escaped = False
    i = 0
    while i < len(text):
        ch = text[i]
        if escaped:
            current.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\":
            escaped = True
            i += 1
            continue
        if text[i:i + 2] == ", ":
            items.append("".join(current))
            current = []
            i += 2
            continue
        current.append(ch)
        i += 1
    items.append("".join(current))
    return tuple(items)


# ---------------------------------------------------------------------------
# _SubjectParts -- ver docstring del modulo.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SubjectParts:
    """Lo que trae la primera linea de un commit de nota, ya separado."""

    type: str
    id: str
    zone1: str
    zone2: str
    headline: str


# ---------------------------------------------------------------------------
# Subject: "[D-030][product][auth] (emoji) headline". El titular puede
# venir plegado en varias lineas fisicas (ver `_fold_raw`) si trae saltos
# de linea propios -- `parse_subject` deshace el plegado antes de casar
# el regex.
# ---------------------------------------------------------------------------

_SUBJECT_RE = re.compile(
    r"^\[(?P<id>[A-Z]-\d+)\]\[(?P<zone1>[^\]]+)\]\[(?P<zone2>[^\]]+)\]"
    r"\s+(?P<emoji>\S+)\s+(?P<headline>.+)$",
    re.DOTALL,
)


def build_subject(note: Note) -> str:
    emoji = emojis.TYPE_EMOJI[note.type]
    prefix = f"[{note.id}][{note.zone1}][{note.zone2}] {emoji} "
    return _fold_raw(prefix, note.headline)


def parse_subject(text: str) -> _SubjectParts | None:
    try:
        lines = text.split("\n")
        unfolded_parts = [lines[0]]
        for line in lines[1:]:
            if not line.startswith(" "):
                return None
            unfolded_parts.append(line[1:])
        unfolded = "\n".join(unfolded_parts)

        match = _SUBJECT_RE.match(unfolded)
        if match is None:
            return None
        note_id = match.group("id")
        return _SubjectParts(
            type=note_id.split("-", 1)[0],
            id=note_id,
            zone1=match.group("zone1"),
            zone2=match.group("zone2"),
            headline=match.group("headline"),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Message: subject + linea en blanco + campos del cuerpo (TEXTOS Sec.5)
# ---------------------------------------------------------------------------

_BODY_FIELD_ORDER = ("Why", "Awaits", "Keys", "Description", "Replaces", "Origin", "Issue", "Quote")
_BODY_FIELD_RE = re.compile(
    r"^(" + "|".join(_BODY_FIELD_ORDER) + r"):[ ]?(.*)$"
)


def _body_field_line(label: str, note: Note) -> str | None:
    """La linea de cuerpo para `label`, o `None` si el campo esta ausente
    en `note`. Unico sitio que sabe como se codifica cada campo -- junto
    con `_BODY_FIELD_ORDER`, la unica fuente del orden real de escritura
    (`build_message` no repite esa decision en una segunda cadena de
    `if` propia).
    """
    if label == "Why":
        return _fold("Why", note.why) if note.why is not None else None
    if label == "Awaits":
        return _fold("Awaits", note.awaits) if note.awaits is not None else None
    if label == "Keys":
        return _fold("Keys", _encode_list(note.keys)) if note.keys else None
    if label == "Description":
        return _fold("Description", note.description)
    if label == "Replaces":
        return _fold("Replaces", note.replaces) if note.replaces is not None else None
    if label == "Origin":
        return _fold("Origin", _encode_list(note.origin)) if note.origin else None
    if label == "Issue":
        return f"Issue: #{note.issue}" if note.issue is not None else None
    if label == "Quote":
        return _fold("Quote", note.quote) if note.quote is not None else None
    raise ValueError(f"format.py: campo de cuerpo desconocido {label!r}")  # pragma: no cover


def _parse_fields(body_lines: list[str], field_re: re.Pattern) -> dict[str, str] | None:
    """Agrupa las lineas del cuerpo en `{Label: valor}`, reconstruyendo los
    valores multilinea. `None` si alguna linea no es ni el arranque de un
    campo conocido de `field_re` ni una continuacion (empieza por un
    espacio) de uno. Generica sobre el vocabulario de campos: la comparten
    `parse_message` (via `_parse_body_fields`, `_BODY_FIELD_RE`) y
    `parse_context_message` (`_CONTEXT_BODY_FIELD_RE`) para no duplicar la
    misma logica de plegado con dos alfabetos de campo distintos.
    """
    fields: dict[str, str] = {}
    current_label: str | None = None
    current_parts: list[str] = []

    for line in body_lines:
        match = field_re.match(line)
        if match is not None:
            if current_label is not None:
                fields[current_label] = "\n".join(current_parts)
            current_label = match.group(1)
            current_parts = [match.group(2)]
        elif line.startswith(" ") and current_label is not None:
            current_parts.append(line[1:])
        else:
            return None

    if current_label is not None:
        fields[current_label] = "\n".join(current_parts)

    if not fields:
        return None
    return fields


def _parse_body_fields(body_lines: list[str]) -> dict[str, str] | None:
    return _parse_fields(body_lines, _BODY_FIELD_RE)


def build_message(note: Note) -> str:
    subject = build_subject(note)
    body_lines: list[str] = []
    for label in _BODY_FIELD_ORDER:
        line = _body_field_line(label, note)
        if line is not None:
            body_lines.append(line)

    return subject + "\n\n" + "\n".join(body_lines)


def parse_message(text: str) -> Note | None:
    try:
        lines = text.split("\n")

        # El titular ocupa la primera linea mas cualquier continuacion
        # plegada (ver `_fold_raw`) -- se recoge hasta la linea en blanco
        # que separa titular de cuerpo.
        idx = 1
        while idx < len(lines) and lines[idx].startswith(" "):
            idx += 1
        if idx >= len(lines) or lines[idx] != "":
            return None

        subject = parse_subject("\n".join(lines[:idx]))
        if subject is None:
            return None

        fields = _parse_body_fields(lines[idx + 1:])
        if fields is None or "Description" not in fields:
            return None

        keys = _decode_list(fields["Keys"]) if "Keys" in fields else ()
        origin = _decode_list(fields["Origin"]) if "Origin" in fields else ()
        issue = int(fields["Issue"].strip().lstrip("#")) if "Issue" in fields else None

        return Note(
            type=subject.type,
            id=subject.id,
            zone1=subject.zone1,
            zone2=subject.zone2,
            headline=subject.headline,
            description=fields["Description"],
            timestamp=datetime.now(timezone.utc),
            why=fields.get("Why"),
            keys=keys,
            origin=origin,
            replaces=fields.get("Replaces"),
            awaits=fields.get("Awaits"),
            issue=issue,
            quote=fields.get("Quote"),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Linea de indice y linea de archivo: `build_index_line`/`parse_index_line`,
# `build_archive_line`/`parse_archive_line`. Importadas de `format_lines.py`
# y reexpuestas arriba -- ver el docstring de este modulo y el de
# `format_lines.py` para el porque de ese corte.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Contexto de cierre -- el [NEXT] del cierre de sesion, sin zonas, sin
# indice (TEXTOS Sec.5 "Contexto de cierre").
#
# Formato fijado por el propietario, 2026-08-03 (COLA.md Sec.5), en
# sustitucion del anterior ("(arrow) titular" + "Context:" con una linea
# "- punto" por punto): el corchete "[NEXT]" es literal, seguido del
# emoji del canal y el titular; el cuerpo es un UNICO campo "Context:" en
# prosa corrida, nunca una lista de guiones -- "el resumen de toda la
# sesion... no es un acta de lo construido". `ContextNote.context` es una
# unica cadena (posiblemente multilinea via `_fold_raw`, igual que
# Why/Description de una nota), no una tupla de puntos.
# ---------------------------------------------------------------------------

_CONTEXT_MARKER = emojis.CHANNEL_EMOJI["next"]
_NEXT_PREFIX = f"[NEXT] {_CONTEXT_MARKER} "

_CONTEXT_BODY_FIELD_ORDER = ("Keys", "Context")
_CONTEXT_BODY_FIELD_RE = re.compile(
    r"^(" + "|".join(_CONTEXT_BODY_FIELD_ORDER) + r"):[ ]?(.*)$"
)


def build_context_message(ctx: ContextNote) -> str:
    lines = [_fold_raw(_NEXT_PREFIX, ctx.headline), ""]
    if ctx.keys:
        lines.append(_fold("Keys", _encode_list(ctx.keys)))
    lines.append(_fold("Context", ctx.context))
    return "\n".join(lines)


def parse_context_message(text: str) -> ContextNote | None:
    """`None` significa exactamente una cosa: `text` no es un cierre de
    sesion. Mismo patron que `parse_message`: el titular ocupa la primera
    linea mas cualquier continuacion plegada, hasta la linea en blanco que
    separa titular de cuerpo; el cuerpo se agrupa por campo con
    `_parse_fields` sobre `_CONTEXT_BODY_FIELD_RE`. `Context` es
    obligatorio -- un cierre sin ese campo no es un cierre valido.
    """
    try:
        lines = text.split("\n")
        if not lines or not lines[0].startswith(_NEXT_PREFIX):
            return None

        idx = 1
        while idx < len(lines) and lines[idx].startswith(" "):
            idx += 1
        if idx >= len(lines) or lines[idx] != "":
            return None

        headline_lines = [lines[0][len(_NEXT_PREFIX):]]
        headline_lines.extend(line[1:] for line in lines[1:idx])
        headline = "\n".join(headline_lines)

        fields = _parse_fields(lines[idx + 1:], _CONTEXT_BODY_FIELD_RE)
        if fields is None or "Context" not in fields:
            return None

        keys = _decode_list(fields["Keys"]) if "Keys" in fields else ()

        return ContextNote(
            headline=headline,
            context=fields["Context"],
            keys=keys,
            timestamp=datetime.now(timezone.utc),
        )
    except Exception:
        return None
