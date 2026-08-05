"""Convertir el informe de zona/palabra en texto -- contrato en
docs/memoria-v2/PIEZAS.md Sec.9.3 (ficha compartida con Sec.9.2,
report.py). `report.py` decide QUE se enseña; este modulo lo pinta.

De que salida se deriva, palabra por palabra [TEXTOS.md]: el informe de
zona con contenido (Sec.2.1), la zona vacia (Sec.2.2) y la busqueda por
palabra (Sec.2.3). Esos bloques son la salida, no un ejemplo -- las
cajas (`====`/`----`), el espaciado y los emojis de cabecera
(``emojis.SECTION_EMOJI``) se copian de ahi.

Que NO hace [Sec.9.2]: no decide nada -- recibe ``ZoneReport``/
``WordReport`` ya construidos por ``report.py`` y no lee de git ni de
``zones.json``/``ARCHIVED.md`` por su cuenta. Si un dato hace falta para
pintar algo y no esta en el objeto recibido, no se va a buscar: es una
ausencia del modelo, no de este fichero, y se documenta abajo en vez de
inventarse.

CINCO DESVIACIONES DECLARADAS frente a la letra literal de TEXTOS.md,
cada una porque el dato que haria falta no existe en ``model.py`` o
rompe una garantia que si esta pedida por un test [Sec.0.1]:

1. **El texto de `Why:`/`Description:`/preguntas no se envuelve en
   varias lineas** como en el ejemplo de TEXTOS. Envolverlo partiria el
   texto literal en trozos con su propia sangria, y
   `test_render_zone_restriction_shows_why_label_and_text_not_only_headline`
   exige que el texto del `why` sobreviva ENTERO y contiguo en el
   render -- envolver y no envolver son incompatibles, y gana el test.
2. **Las incidencias no llevan "cerrada"/"ABIERTA" ni la flecha "->
   parió R-018"**: ``model.Note`` no tiene un campo de estado abierto/
   cerrado ni una lista de "que nacio de mi" navegable desde la propia
   incidencia -- inventar esa relacion aqui seria decidir un dato que
   este modulo no tiene, lo que Sec.9.2 prohibe expresamente.
3. **Los racimos de decision no incluyen una fila "acta de plan"**
   (`#47  plan-login.md  acta  ...`): ``clusters.group`` solo agrupa
   tipos D/X (ver ``report.py::_DECISION_TYPES``), y una nota de acta no
   es ninguno de los dos en el pipeline real -- no hay forma de que un
   ``Cluster`` real traiga esa fila.
4. **La zona vacia no lleva "dada de alta el <fecha>" ni "Zonas
   parecidas que si tienen contenido"**: ``model.Zone`` no guarda fecha
   de alta, y comparar con el recuento de otras zonas exige una lista de
   zonas hermanas que ``ZoneReport`` no trae como campo -- mismo
   supuesto 2 que ya declara el docstring de
   ``tests/memory/test_report_render.py``.
5. **El pie de la busqueda por palabra usa el propio `word`, no un
   nombre de zona** ("Estado completo de una zona: gitmem search
   billing" en TEXTOS Sec.2.3): ``WordReport`` no expone que zona es "la
   mas relevante" -- elegir una seria decidir, y este modulo no decide.

Sin estas cinco, el resto del texto -- titulos de seccion, orden,
cajas, "CERO NOTAS", el marcador `>` y la etiqueta UTC -- es literal de
TEXTOS.md Sec.2.1/2.2/2.3.

Quien lo llama [Sec.9.2]. `bin/memory/search.py`. `dispatch` tambien lo
llamaba -- retirado entero [decision del propietario, 2026-08-03, B20]:
cada agente busca su propia memoria de proyecto, ya no hay un vigilante
que reparta por oficio.

`lib/memory/` no importa nada del toolkit fuera de la biblioteca estandar
de Python [PIEZAS.md Sec.13]. Import plano entre hermanos
[PIEZAS.md Sec.3.3bis].
"""

from datetime import datetime, timezone
from typing import NamedTuple

import timefmt
from emojis import SECTION_EMOJI
from model import Cluster, Note, WordChunk, WordReport, ZoneReport

_BOX_WIDTH = 72
_DIVIDER = "═" * _BOX_WIDTH  # ====
_THIN_DIVIDER = "─" * _BOX_WIDTH  # ----
# Copiado literal de TEXTOS.md Sec.2.2 -- no tecleado de memoria.
_CERO_NOTAS = "⚠  C E R O   N O T A S"

_RESTRICTION_TYPES = frozenset({"R"})
_BLOCKER_TYPES = frozenset({"B"})
_DECISION_TYPES = frozenset({"D", "X"})
_MEMO_TYPES = frozenset({"M"})
_INCIDENT_TYPES = frozenset({"I"})
_QUESTION_TYPES = frozenset({"Q"})

_MARK = "› "  # el marcador "> " de TEXTOS Sec.2.3
_NO_MARK = "  "


def _header_line(left: str, right: str) -> str:
    gap = _BOX_WIDTH - len(left) - len(right)
    if gap < 1:
        gap = 1
    return f"{left}{' ' * gap}{right}"


# Alias publicos -- reutilizados por report_render_note.py (informe de una
# nota por su id, TEXTOS.md Sec.2.4) sin duplicar ninguna de las cuatro
# piezas de arriba. Mismo principio que ``vocabulary.TYPE_INDEX_FILES`` se
# hizo publica para reuso entre hermanos: una sola copia, nunca dos.
# report_render_note.py se separo de este fichero (no una funcion mas
# aqui) por el mismo techo de 500 lineas que ya partio format.py/
# validator.py [DEUDA.md puntos 12/14].
DIVIDER = _DIVIDER
THIN_DIVIDER = _THIN_DIVIDER
header_line = _header_line
# La etiqueta UTC vive en `timefmt.py` desde 2026-08-05: estaba escrita
# aqui y otra vez en `boot.py`, y las dos copias ya habian empezado a
# separarse -- una convertia la zona horaria y la otra no. Se reexporta
# para no tocar a `report_render_note.py`, que la usa por este nombre.
utc_label = timefmt.utc_label


def _restriction_block(note: Note, marker: str) -> list[str]:
    lines = [f"{marker}{note.id}  [{note.zone1}][{note.zone2}]  {note.headline}"]
    if note.why:
        lines.append(f"         Why: {note.why}")
    if note.origin:
        lines.append(f"         Origin: {', '.join(note.origin)}")
    if note.keys:
        lines.append(f"         Keys: {', '.join(note.keys)}")
    return lines


def _blocker_block(note: Note, marker: str) -> list[str]:
    lines = [f"{marker}{note.id}  [{note.zone1}][{note.zone2}]  {note.headline}"]
    if note.awaits:
        lines.append(f"         awaits: {note.awaits}")
    lines.append(f"         Description: {note.description}")
    return lines


def _decision_block(note: Note, marker: str) -> list[str]:
    """Nota D/X suelta, sin racimo -- usada solo por ``render_word``, que
    recibe ``WordChunk.notes`` en bruto y no un ``Cluster`` (ver
    desviacion 3 del docstring del modulo)."""
    lines = [f"{marker}{note.id}  {note.headline}"]
    if note.why:
        lines.append(f"         Why: {note.why}")
    if note.origin:
        lines.append(f"         Origin: {', '.join(note.origin)}")
    return lines


def _memo_block(note: Note, marker: str) -> list[str]:
    return [f"{marker}{note.id}  {note.headline}"]


def _incident_block(note: Note, marker: str) -> list[str]:
    return [f"{marker}{note.id}  {note.headline}"]


def _question_block(note: Note, marker: str) -> list[str]:
    lines = [f"{marker}{note.id}  {note.headline}"]
    if note.description:
        lines.append(f"         {note.description}")
    return lines


def _cluster_block(cluster: Cluster) -> list[str]:
    """El racimo completo -- raiz mas hijos, con su estado
    (descartada/vigente/archivada) y el puntero que los conecta
    [TEXTOS Sec.2.1]. Solo lo usa ``render_zone``: es el unico que
    recibe ``Cluster`` ya armados por ``clusters.group`` (con
    ``archived_ids``); ``render_word`` no tiene ese dato (desviacion 3).
    """
    root = cluster.root
    lines = [_header_line(f"  {root.id}  {root.headline}", root.timestamp.strftime("%Y-%m-%d"))]
    if root.why:
        lines.append(f"         Why: {root.why}")

    children = cluster.children
    for index, child in enumerate(children):
        branch = "└─" if index == len(children) - 1 else "├─"
        if child.type == "X":
            status = "descartada"
        elif child.id in cluster.archived_ids:
            status = "archivada"
        else:
            status = "vigente"

        if root.replaces == child.id:
            pointer = f"replaced by {root.id}"
        elif child.origin:
            pointer = f"Origin {', '.join(child.origin)}"
        elif child.replaces:
            pointer = f"replaces {child.replaces}"
        else:
            pointer = ""

        tail = f"{status} · {pointer}" if pointer else status
        lines.append(f"    {branch} {child.id}  {child.headline}  {tail}")

    return lines


def _empty_zone_lines() -> list[str]:
    """El bloque CERO NOTAS -- literal de TEXTOS.md Sec.2.2 salvo la
    fecha de alta y "zonas parecidas" (desviacion 4 del docstring del
    modulo: ``model.Zone``/``model.ZoneReport`` no traen esos datos)."""
    return [
        " " * 14 + _CERO_NOTAS,
        "",
        "  La zona existe en zones.json y no tiene ni una: ninguna",
        "  decisión, ningún muro, ningún hecho, ninguna incidencia,",
        "  ninguna pregunta.",
        "",
        "  Es un dato, no un fallo. O el trabajo no ha empezado, o se ha",
        "  hecho sin escribir nada de lo que se decidió.",
    ]


def _no_marker(_note: Note) -> str:
    return _NO_MARK


def _section(
    lines: list[str],
    title: str,
    notes: list[Note],
    block_fn,
    marker_fn,
    compact: bool = False,
) -> None:
    """Aniade una seccion (titulo + un bloque por nota) a ``lines`` si
    ``notes`` no esta vacio -- una zona/trozo sin ninguna nota de ese
    tipo no imprime una seccion vacia. ``compact`` deja una sola linea
    en blanco al final en vez de una por nota (los memos, de una linea
    cada uno [TEXTOS Sec.2.1]).
    """
    if not notes:
        return
    lines.append(title)
    lines.append("")
    for note in notes:
        lines.extend(block_fn(note, marker_fn(note)))
        if not compact:
            lines.append("")
    if compact:
        lines.append("")


def _cluster_section(lines: list[str], title: str, clusters: tuple[Cluster, ...]) -> None:
    if not clusters:
        return
    lines.append(title)
    lines.append("")
    for cluster in clusters:
        lines.extend(_cluster_block(cluster))
        lines.append("")


def _render_zone_sections(r: ZoneReport) -> list[str]:
    """Las seis secciones del cuerpo, en el orden fijado por contrato
    [PIEZAS Sec.9.2, spec Sec.8] -- separado de ``render_zone`` para que
    ninguna de las dos pase de 50 lineas."""
    lines: list[str] = []
    before_decisions = (
        (
            f"{SECTION_EMOJI['restricciones']} RESTRICTIONS ({len(r.restrictions)}) "
            f"— literales",
            r.restrictions,
            _restriction_block,
            False,
        ),
        (f"{SECTION_EMOJI['bloqueantes']} BLOCKERS ({len(r.blockers)})", r.blockers, _blocker_block, False),
    )
    for title, notes, block_fn, compact in before_decisions:
        _section(lines, title, notes, block_fn, _no_marker, compact)

    _cluster_section(
        lines, f"{SECTION_EMOJI['decisiones']} DECISIONS ({len(r.decisions)} racimos)", r.decisions
    )

    after_decisions = (
        (f"{SECTION_EMOJI['memos']} MEMOS ({len(r.memos)})", r.memos, _memo_block, True),
        (f"{SECTION_EMOJI['incidencias']} INCIDENTS ({len(r.incidents)})", r.incidents, _incident_block, False),
        (
            f"{SECTION_EMOJI['preguntas']} OPEN QUESTIONS ({len(r.questions)})",
            r.questions,
            _question_block,
            False,
        ),
    )
    for title, notes, block_fn, compact in after_decisions:
        _section(lines, title, notes, block_fn, _no_marker, compact)
    return lines


def render_zone(r: ZoneReport) -> str:
    """El informe de una zona, llena o vacia [TEXTOS Sec.2.1/2.2].

    El orden es contrato, no gusto [PIEZAS Sec.9.2, spec Sec.8]:
    restricciones arriba y literales, bloqueantes, racimos de
    decisiones, memos, incidencias y las preguntas al final bajo
    "OPEN QUESTIONS". Una zona sin ninguna nota (``live_count`` y
    ``archived_count`` los dos a cero) dice CERO NOTAS en vez de listar
    seis secciones vacias -- Sec.9.2, "Sus tests", fila 3.
    """
    lines = [_DIVIDER]
    total = r.live_count + r.archived_count

    if total == 0:
        lines.append(_header_line(f"  ZONA {r.zone.name}", timefmt.utc_label(r.generated_at)))
        lines.append(_DIVIDER)
        lines.append("")
        lines.extend(_empty_zone_lines())
        lines.append(_DIVIDER)
        return "\n".join(lines)

    lines.append(
        _header_line(
            f"  ZONA {r.zone.name} · {r.live_count} vigentes · "
            f"{r.archived_count} archivadas",
            timefmt.utc_label(r.generated_at),
        )
    )
    lines.append(_DIVIDER)
    lines.append("")
    lines.extend(_render_zone_sections(r))
    lines.append(_THIN_DIVIDER)
    lines.append(f"  Historia completa, con lo archivado:   gitmem search {r.zone.name} --todo")
    return "\n".join(lines)


class _TypeSplit(NamedTuple):
    """Las notas de un ``WordChunk`` separadas por tipo -- detalle
    privado de este modulo, no una forma del sistema (Sec.5.3 reserva
    eso a ``model.py``). ``WordChunk`` no trae los recuentos ya
    separados como ``ZoneReport`` (``report.py`` no los construye para
    la busqueda por palabra), asi que es este modulo quien los separa
    para pintarlos -- clasificar por un campo que ya existe en la nota
    (``note.type``) es parte de "convertir en texto", no una decision
    nueva."""

    restrictions: list[Note]
    blockers: list[Note]
    decisions: list[Note]
    memos: list[Note]
    incidents: list[Note]
    questions: list[Note]


def _split_by_type(notes: tuple[Note, ...]) -> _TypeSplit:
    return _TypeSplit(
        restrictions=[n for n in notes if n.type in _RESTRICTION_TYPES],
        blockers=[n for n in notes if n.type in _BLOCKER_TYPES],
        decisions=[n for n in notes if n.type in _DECISION_TYPES],
        memos=[n for n in notes if n.type in _MEMO_TYPES],
        incidents=[n for n in notes if n.type in _INCIDENT_TYPES],
        questions=[n for n in notes if n.type in _QUESTION_TYPES],
    )


def _chunk_header(chunk: WordChunk) -> str:
    header = f"──── [{chunk.zone1}][{chunk.zone2}] · {len(chunk.notes)} notas "
    if len(header) < _BOX_WIDTH:
        header = header + "─" * (_BOX_WIDTH - len(header))
    return header


def _chunk_sections(chunk: WordChunk, by_type: _TypeSplit) -> list[str]:
    """Las cinco secciones del cuerpo de un trozo (todo menos preguntas,
    que ``render_word`` agrega una sola vez al final) -- separado de
    ``_chunk_body`` para que ninguna de las dos pase de 50 lineas."""
    lines: list[str] = []

    def marker_for(note: Note) -> str:
        return _MARK if note.id in chunk.matched_ids else _NO_MARK

    specs = (
        (
            f"{SECTION_EMOJI['restricciones']} RESTRICTIONS ({len(by_type.restrictions)})",
            by_type.restrictions,
            _restriction_block,
            False,
        ),
        (
            f"{SECTION_EMOJI['bloqueantes']} BLOCKERS ({len(by_type.blockers)})",
            by_type.blockers,
            _blocker_block,
            False,
        ),
        (
            f"{SECTION_EMOJI['decisiones']} DECISIONS ({len(by_type.decisions)})",
            by_type.decisions,
            _decision_block,
            False,
        ),
        (f"{SECTION_EMOJI['memos']} MEMOS ({len(by_type.memos)})", by_type.memos, _memo_block, True),
        (
            f"{SECTION_EMOJI['incidencias']} INCIDENTS ({len(by_type.incidents)})",
            by_type.incidents,
            _incident_block,
            False,
        ),
    )
    for title, notes, block_fn, compact in specs:
        _section(lines, title, notes, block_fn, marker_for, compact)
    return lines


def _chunk_body(chunk: WordChunk, pending_questions: list[tuple[Note, bool]]) -> list[str]:
    """El cuerpo de un trozo de la busqueda por palabra -- todo menos
    las preguntas, que ``render_word`` agrega una sola vez al final
    [TEXTOS Sec.2.3]."""
    lines = [_chunk_header(chunk), ""]
    by_type = _split_by_type(chunk.notes)
    lines.extend(_chunk_sections(chunk, by_type))
    for note in by_type.questions:
        pending_questions.append((note, note.id in chunk.matched_ids))
    return lines


def render_word(r: WordReport) -> str:
    """La busqueda por palabra suelta, a traves de varias zonas
    [TEXTOS Sec.2.3]. Las preguntas de TODOS los trozos se agregan bajo
    un unico "OPEN QUESTIONS" al final del informe completo, nunca
    una vez por trozo [Sec.9.2, fila 1 de "Sus tests" aplicada aqui].
    """
    lines = [_DIVIDER]
    lines.append(
        _header_line(
            f"  PALABRA «{r.word}» · {r.zone_count} zonas · {r.live_count} vigentes",
            timefmt.utc_label(r.generated_at),
        )
    )
    lines.append(f"  {_MARK} marca la línea que casó")
    lines.append(_DIVIDER)

    pending_questions: list[tuple[Note, bool]] = []
    for chunk in r.chunks:
        lines.append("")
        lines.extend(_chunk_body(chunk, pending_questions))

    if pending_questions:
        lines.append("")
        lines.append(f"{SECTION_EMOJI['preguntas']} OPEN QUESTIONS ({len(pending_questions)})")
        lines.append("")
        for note, matched in pending_questions:
            marker = _MARK if matched else _NO_MARK
            lines.extend(_question_block(note, marker))
            lines.append("")

    lines.append(_THIN_DIVIDER)
    lines.append(f"  Historia completa, con lo archivado:   gitmem search «{r.word}» --todo")
    return "\n".join(lines)


# `render()` -- BORRADA 2026-08-04 [correccion, decision del orquestador,
# revocable]. Era un alias que despachaba por tipo, creado SOLO para que
# `vocabulary.FIELDS["why"]`/`["description"]` declarasen un lector con
# ese nombre exacto y la vacuna reflexiva de `test_vocabulary.py`
# encontrara un simbolo que resolviera -- nadie la llamaba de verdad, ni
# fuera del modulo ni dentro: `bin/memory/search.py` siempre llamo
# directamente a `render_zone`/`render_word`. Un lector de mentira puesto
# para engañar al mismo chequeo que existe para impedir justo eso
# [mismo fallo que `Sources:` en el sistema v1, docstring de
# `vocabulary.py`]. `vocabulary.FIELDS["why"]`/`["description"]` ya
# declaran `"report_render.render_zone"` como lector real.
