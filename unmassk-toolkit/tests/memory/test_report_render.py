"""Contrato de lib/memory/report_render.py -- PIEZAS.md Sec.9.3 (ficha
compartida con Sec.9.2, report.py).

report_render.py NO EXISTE TODAVIA. Estos tests deben fallar al
resolver la fixture `report_render` (FileNotFoundError via
`import_lib_memory_module`, ver conftest) -- es el ROJO del modo
test-first. `report.py` (Sec.9.2) SI existe y esta en verde; se usa tal
cual, real, para construir la entrada (`ZoneReport`/`WordReport`) que
`render_zone`/`render_word` tienen que convertir en texto.

REPARTO DE LA TABLA "SUS TESTS" ENTRE LAS DOS PIEZAS DE LA FICHA --
segun el propio docstring de `test_report.py` (ya escrito, ya en
verde), de las cinco filas SOLO LA 1 ("el orden se cumple:
restricciones primero... preguntas al final") es de `report_render.py`;
las otras cuatro se probaron ahi a nivel de DATOS (el campo `why`
sobrevive, los recuentos salen en cero, etc.), no de texto.

El encargo de esta tarea, sin embargo, es literal en pedir CINCO
comprobaciones sobre el TEXTO que produce esta pieza -- y no hay
contradiccion real: son la MISMA lista de preocupaciones que
`test_report.py`, pero miradas desde el lado que le toca a
`report_render.py` (la letra, no el dato):

  1. El orden se cumple de principio a fin, EN TEXTO -- unico dueno,
     nadie mas lo prueba (fila 1 de la tabla).
  2. Las restricciones llevan su "Why:" ESCRITO en el texto, no solo el
     dato `why` intacto en memoria (eso ya lo prueba `test_report.py`,
     fila 4) -- `vocabulary.FIELDS["why"].reader ==
     "report_render.render"`, literal: el LECTOR de ese campo es esta
     pieza, no `report.py`.
  3. Una zona vacia dice CERO NOTAS con la forma espaciada exacta de
     TEXTOS Sec.2.2 -- `test_report.py` fila 3 solo prueba que las seis
     tuplas salen vacias, nunca la letra grande.
  4. La busqueda por palabra marca la linea con `>` en el TEXTO --
     `test_report.py` fila 5 solo prueba que `matched_ids` tiene el id
     correcto, nunca el simbolo.
  5. Las horas llevan su etiqueta UTC [spec Sec.2, P11] -- no citada en
     la tabla de PIEZAS.md Sec.9.2/9.3, pero si en la especificacion
     cerrada, que manda sobre cualquier otro documento
     [PIEZAS.md "0.1 Cada afirmacion lleva su fuente"].

TEXTOS.md ES LA SALIDA, NO UN EJEMPLO -- se copian sus fragmentos
literales (titulos de seccion, la letra "CERO NOTAS", el disclaimer
"Es un dato, no un fallo.") tal cual estan en el fichero, nunca
tecleados de memoria, y se comparan contra el texto que produce la
pieza real (`report.build_zone`/`build_word`, ya en verde) mas la
pieza bajo prueba -- el que construye la entrada y el que fija el texto
esperado son DOS cosas escritas por separado (unmassk-standards Sec.34).
No se compara el bloque ENTERO de TEXTOS.md contra la salida: los datos
sembrados aqui no son los de los ejemplos (zonas/ids distintos), asi
que una igualdad total seria fabricar candidatos que no van a coincidir
nunca por texto libre (headline/descripcion de este fichero). Se
comparan fragmentos ESTABLES -- titulos de seccion, la letra CERO
NOTAS, el marcador `>`, la etiqueta UTC -- contra posiciones relativas
en el texto generado con datos propios de cada test.

COMO SE SIEMBRA, igual que `test_report.py` (misma convencion, mismo
motivo: `notes.write()` YA ES la transaccion real validar->indice->
commit, sembrar a mano seria repetir logica que ya existe y esta en
verde): cada nota entra por `notes.write(note, ctx)` contra un
`tmp_repo` real, nunca construida a mano. El `ZoneReport`/`WordReport`
de entrada sale de `report.build_zone`/`report.build_word`, tambien
reales -- ninguno de los dos se fabrica en este fichero.

UN AVISO DEL ENCARGO, RESPETADO TAL CUAL: `report.build_zone` escribe
hoy los ocho indices/zones.json contra
`<root>/.claude/project-memory/` (ver el docstring de `report.py`,
seccion "UN HECHO REAL, MEDIDO EN VIVO"), mientras que
`notes.write()`/`indexes.seed()` dejan los SIETE INDICES VIGENTES en la
RAIZ del repo -- desajuste ajeno a esta pieza, con arreglo encolado
[DEUDA.md]. Este fichero siembra exactamente como `test_report.py`:
`indexes.seed(_pm_root(root))` para `zones.json`/`ARCHIVED.md`, y
`notes.write()` sin tocar la ruta de los siete indices vigentes -- no
se arregla ni se esquiva aqui.

SUPUESTOS DECLARADOS, sin fuente literal en Sec.9.2/9.3 (mismo tipo de
hueco que `test_report.py`, "supuestos declarados"):

1. **El formato exacto de la hora** ("2026-08-01 09:12 UTC") es un
   EJEMPLO de TEXTOS Sec.2.1, no una gramatica formal declarada en
   ningun otro sitio -- P11 (spec Sec.2) solo exige la etiqueta "UTC"
   explicita, no un `strftime` concreto. Este fichero comprueba
   precision de DIA (`%Y-%m-%d`) junto a la etiqueta "UTC" en la misma
   linea -- suficiente para probar el round-trip real (la hora que
   `report.build_zone`/`build_word` puso de verdad, con `datetime.now
   (timezone.utc)`, aparece marcada) sin fijar un formato de minuto que
   Sec.9.2/9.3 no cierra.
2. **"Zonas parecidas que si tienen contenido"** (TEXTOS Sec.2.2,
   ultimo bloque del informe de zona vacia) NO SE PRUEBA aqui: exige
   comparar el recuento de notas de OTRAS zonas, un dato que
   `model.ZoneReport` no trae como campo (no hay lista de zonas
   hermanas en la superficie declarada, Sec.9.2). Probarlo aqui
   obligaria a inventar de donde sale ese dato -- exactamente lo que
   "no se fabrica, se pregunta" prohibe. Fuera de esta pasada, para
   quien la audite despues.
3. **Si un `WordChunk` cuyas UNICAS notas son de tipo Q imprime su
   propia cabecera de separador de zona** (`──── [zone][zone] ...`) no
   esta fijado por ningun texto -- los tres ejemplos de TEXTOS Sec.2.3
   siempre tienen al menos otra categoria ademas de Q en cada chunk. El
   test de agregacion global de preguntas (mas abajo) no depende de la
   respuesta: solo comprueba CUANTAS veces aparece el titulo "LO QUE
   ESPERA DE TI" (una, nunca una por chunk) y que aparece DESPUES del
   contenido del ultimo chunk, sea cual sea la respuesta a este punto.
4. **Los nombres de zona de este fichero se siembran con
   `zone1 == zone2 == zone`** (mismo supuesto 3 de `test_report.py`,
   sobre que eje casa `build_zone`/`build_word` con `WordChunk.zone1`/
   `zone2`) -- evita depender de la respuesta, no la resuelve.

No se toca produccion: si `lib/memory/report_render.py` no existe,
estos tests se quedan en rojo tal cual estan -- eso es lo esperado. No
se toca `report.py` ni ningun otro fichero de un companero (hay
agentes trabajando en `notes.py` y otros ficheros de `tests/`, fuera
de esta tarea).
"""

import os
import re
import contextlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from .conftest import import_lib_memory_module

_BASE_NOTE_FIELDS = dict(
    type="M",
    id="",
    zone1="product",
    zone2="report-render-test",
    headline="MARK_BASE_HEADLINE ordinary memo for report_render.py tests",
    description="MARK_BASE_DESCRIPTION not empty, not special",
    timestamp=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
)


@pytest.fixture
def report():
    return import_lib_memory_module("report")


@pytest.fixture
def report_render():
    return import_lib_memory_module("report_render")


@pytest.fixture
def model():
    return import_lib_memory_module("model")


@pytest.fixture
def config():
    return import_lib_memory_module("config")


@pytest.fixture
def validator():
    return import_lib_memory_module("validator")


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def notes():
    return import_lib_memory_module("notes")


@pytest.fixture
def zones_mod():
    return import_lib_memory_module("zones")


@pytest.fixture
def make_note(model):
    def _make(**overrides):
        fields = dict(_BASE_NOTE_FIELDS)
        fields.update(overrides)
        return model.Note(**fields)

    return _make


@pytest.fixture
def make_context(model, config, validator):
    """Un `Context` real, con las zonas de la nota ya dadas de alta EN
    MEMORIA -- mismo patron que `test_notes.py::make_context` y
    `test_report.py::make_context`. No toca `zones.json`: eso es
    `_register_zone` (abajo).
    """

    def _make(zone_names=(), existing_in_zone=(), known_ids=frozenset(), cfg=None):
        zones = {
            name: model.Zone(name=name, description=f"MARK zone {name}", aliases=())
            for name in zone_names
        }
        return validator.Context(
            zones=zones,
            existing_in_zone=existing_in_zone,
            known_ids=known_ids,
            config=cfg if cfg is not None else config.Config(),
        )

    return _make


@contextlib.contextmanager
def _cwd(path):
    """Cambia el cwd del proceso a `path` durante el bloque, y lo
    restaura siempre -- mismo helper que `test_notes.py::_cwd` /
    `test_report.py::_cwd`.
    """
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _pm_root(root) -> Path:
    """Raiz de los ocho indices y zones.json -- ver supuesto del
    docstring del modulo y el de `report.py`."""
    return Path(root) / ".claude" / "project-memory"


def _zones_json_path(root) -> Path:
    return _pm_root(root) / "zones.json"


def _register_zone(zones_mod, model, root, name, description=None):
    """Da de alta `name` en el `zones.json` REAL de `root` -- la
    representacion en disco que `report.build_zone` lee."""
    zones_mod.add(
        model.Zone(
            name=name,
            description=description or f"MARK zone {name} for report_render.py contract",
            aliases=(),
        ),
        _zones_json_path(root),
    )


def _write(notes, root, note, ctx):
    with _cwd(root):
        result = notes.write(note, ctx)
    assert result.ok, f"seed fallo: {result.git_error or result.rejections}"
    return result


# ---------------------------------------------------------------------------
# Fila 1 -- el orden se cumple: restricciones y literales, bloqueantes,
# racimos de decisiones, memos e incidencias, preguntas al final
# ---------------------------------------------------------------------------


def test_render_zone_section_order_restrictions_to_questions_last(
    report,
    report_render,
    model,
    config,
    validator,
    indexes,
    notes,
    zones_mod,
    tmp_repo,
    make_note,
    make_context,
):
    """Fila 1 (unica de report_render en la tabla de Sec.9.2/9.3): el
    orden se cumple, EN TEXTO -- restricciones arriba, bloqueantes,
    racimos de decisiones, memos e incidencias, y las preguntas al
    final bajo "OPEN QUESTIONS" [PIEZAS Sec.9.2, TEXTOS Sec.2.1].

    Fallo real que previene: un muro enterrado bajo veinte memos, que
    es no tener muro.
    """
    root = Path(tmp_repo)
    zone = "renderorderzone"
    indexes.seed(_pm_root(root))
    _register_zone(zones_mod, model, root, zone)
    ctx = make_context(zone_names=(zone,))

    restriction = make_note(
        type="R",
        zone1=zone,
        zone2=zone,
        headline="MARK_R_HEADLINE never skip the order check in this test",
        description="MARK_R_DESCRIPTION restriction for the order test.",
    )
    blocker = make_note(
        type="B",
        zone1=zone,
        zone2=zone,
        headline="MARK_B_HEADLINE waiting on an external answer",
        description="MARK_B_DESCRIPTION blocker for the order test.",
        awaits="MARK_AWAITS someone external",
    )
    decision = make_note(
        type="D",
        zone1=zone,
        zone2=zone,
        headline="MARK_D_HEADLINE chose an option for the order test",
        description="MARK_D_DESCRIPTION decision for the order test.",
        why="MARK_D_WHY because this test needs one decision cluster",
    )
    memo = make_note(
        type="M",
        zone1=zone,
        zone2=zone,
        headline="MARK_M_HEADLINE a stable fact for the order test",
        description="MARK_M_DESCRIPTION memo for the order test.",
    )
    incident = make_note(
        type="I",
        zone1=zone,
        zone2=zone,
        headline="MARK_I_HEADLINE something broke for the order test",
        description="MARK_I_DESCRIPTION incident for the order test.",
    )
    question = make_note(
        type="Q",
        zone1=zone,
        zone2=zone,
        headline="MARK_Q_HEADLINE is this order really guaranteed",
        description="MARK_Q_DESCRIPTION question for the order test.",
    )

    for note in (restriction, blocker, decision, memo, incident, question):
        _write(notes, root, note, ctx)

    with _cwd(root):
        zone_report = report.build_zone(zone, False)
        rendered = report_render.render_zone(zone_report)

    assert isinstance(rendered, str), f"render_zone no devolvio str: {type(rendered)!r}"

    section_titles = (
        "RESTRICTIONS",
        "BLOCKERS",
        "DECISIONS",
        "MEMOS",
        "INCIDENTS",
        "OPEN QUESTIONS",
    )
    positions = {}
    for title in section_titles:
        assert title in rendered, (
            f"el titulo de seccion {title!r} [TEXTOS Sec.2.1] no aparece en el "
            f"informe renderizado:\n{rendered}"
        )
        positions[title] = rendered.index(title)

    ordered = sorted(positions, key=positions.get)
    assert ordered == list(section_titles), (
        f"el orden real de las secciones es {ordered!r}, deberia ser "
        f"{list(section_titles)!r} [PIEZAS Sec.9.2: 'restricciones arriba y "
        f"literales, luego bloqueantes, luego los racimos de decisiones, "
        f"luego memos e incidencias, y las preguntas al final']"
    )


# ---------------------------------------------------------------------------
# Fila 4 -- las restricciones llevan su porque, ESCRITO en el texto
# ---------------------------------------------------------------------------


def test_render_zone_restriction_shows_why_label_and_text_not_only_headline(
    report,
    report_render,
    model,
    config,
    validator,
    indexes,
    notes,
    zones_mod,
    tmp_repo,
    make_note,
    make_context,
):
    """Fila 4: las restricciones llevan su porque -- no solo el
    titular [PIEZAS Sec.9.2: "un titular en ingles a secas no cambia
    la conducta de nadie a las tres de la manana"].

    `vocabulary.FIELDS["why"].reader == "report_render.render"`: el
    LECTOR real del campo `why` es esta pieza -- `test_report.py` fila
    4 ya prueba que el DATO sobrevive el viaje por git; este test
    prueba que el TEXTO ("Why:" mas el contenido) sale de verdad, y
    despues del titular, nunca solo.
    """
    root = Path(tmp_repo)
    zone = "renderwhyzone"
    indexes.seed(_pm_root(root))
    _register_zone(zones_mod, model, root, zone)
    ctx = make_context(zone_names=(zone,))

    needle_why = (
        "MARK_WHY_NEEDLE this exact sentence must survive git and come "
        "back rendered with its label"
    )
    restriction = make_note(
        type="R",
        zone1=zone,
        zone2=zone,
        headline="MARK_RESTRICTION_HEADLINE never do the thing this test forbids",
        description="MARK_RESTRICTION_DESCRIPTION separate from the why field.",
        why=needle_why,
    )
    _write(notes, root, restriction, ctx)

    with _cwd(root):
        zone_report = report.build_zone(zone, False)
        rendered = report_render.render_zone(zone_report)

    assert restriction.headline in rendered, (
        f"el titular de la restriccion no aparece en el texto:\n{rendered}"
    )
    assert "Why:" in rendered, (
        f"la etiqueta 'Why:' [TEXTOS Sec.2.1] no aparece en el texto:\n{rendered}"
    )
    assert needle_why in rendered, (
        f"el texto real del porque no aparece, palabra por palabra, en el "
        f"informe renderizado:\n{rendered}"
    )
    headline_index = rendered.index(restriction.headline)
    why_label_index = rendered.index("Why:")
    why_text_index = rendered.index(needle_why)
    assert headline_index < why_label_index < why_text_index, (
        f"el orden esperado es titular -> 'Why:' -> texto del porque, salio "
        f"{headline_index}, {why_label_index}, {why_text_index}"
    )


# ---------------------------------------------------------------------------
# Fila 3 -- una zona vacia dice CERO NOTAS en alto, imposible de confundir
# con un error
# ---------------------------------------------------------------------------


def test_render_zone_empty_zone_shows_cero_notas_loudly_not_as_an_error(
    report, report_render, model, zones_mod, indexes, tmp_repo
):
    """Fila 3: una zona vacia dice CERO NOTAS en alto, y es imposible
    confundirlo con un error [TEXTOS Sec.2.2, literal].

    `test_report.py` fila 3 ya prueba que las seis tuplas de
    `ZoneReport` salen vacias de forma explicita a nivel de dato; este
    test prueba la LETRA -- el fragmento espaciado exacto de TEXTOS
    Sec.2.2, copiado tal cual del fichero, nunca tecleado de memoria --
    y que la palabra "error" no aparece en ningun sitio del texto.

    Fallo real que previene: el silencio del v1, donde algo deja de
    funcionar y nadie se entera.
    """
    root = Path(tmp_repo)
    zone = "renderemptyzone"
    indexes.seed(_pm_root(root))
    _register_zone(zones_mod, model, root, zone)

    with _cwd(root):
        zone_report = report.build_zone(zone, False)
        rendered = report_render.render_zone(zone_report)

    assert isinstance(rendered, str), f"render_zone no devolvio str: {type(rendered)!r}"

    # Fragmento copiado LITERAL de docs/memoria-v2/TEXTOS.md Sec.2.2, linea
    # "              (warning) C E R O   N O T A S" -- no tecleado de memoria.
    cero_notas_literal = "⚠  C E R O   N O T A S"
    assert cero_notas_literal in rendered, (
        f"la letra grande de CERO NOTAS [TEXTOS Sec.2.2] no aparece tal cual "
        f"en el informe de una zona vacia:\n{rendered}"
    )

    disclaimer_literal = "Es un dato, no un fallo."
    assert disclaimer_literal in rendered, (
        f"el disclaimer literal de TEXTOS Sec.2.2 no aparece: {rendered!r}"
    )

    assert re.search(r"error", rendered, re.IGNORECASE) is None, (
        f"la palabra 'error' aparece en el informe de una zona vacia -- "
        f"TEXTOS Sec.2.2 exige que CERO NOTAS sea 'imposible de confundir "
        f"con un error':\n{rendered}"
    )


# ---------------------------------------------------------------------------
# Fila 5 -- la busqueda por palabra marca la linea que caso con `>`
# ---------------------------------------------------------------------------


def test_render_word_marks_matched_line_not_unmatched_line(
    report,
    report_render,
    model,
    config,
    validator,
    indexes,
    notes,
    zones_mod,
    tmp_repo,
    make_note,
    make_context,
):
    """Fila 5: la busqueda por palabra marca la linea que caso, con
    `>` [TEXTOS Sec.2.3, cabecera: "marca la linea que caso"].

    `test_report.py` fila 5 ya prueba que `WordChunk.matched_ids` trae
    el id correcto a nivel de dato; este test prueba que ESE id se
    traduce en el simbolo `>` delante de su linea, y que la nota que
    NO caso -- presente igual, para dar contexto -- no lo lleva.
    """
    root = Path(tmp_repo)
    zone = "renderwordzone"
    indexes.seed(_pm_root(root))
    _register_zone(zones_mod, model, root, zone)
    ctx = make_context(zone_names=(zone,))

    needle = "zzrenderwordneedle"
    matching_note = make_note(
        type="M",
        zone1=zone,
        zone2=zone,
        headline="MARK_MATCH_HEADLINE memo that mentions the needle below",
        description=f"MARK_MATCH_DESCRIPTION containing the needle {needle} once.",
    )
    other_note = make_note(
        type="M",
        zone1=zone,
        zone2=zone,
        headline="MARK_NOMATCH_HEADLINE memo without the needle anywhere",
        description="MARK_NOMATCH_DESCRIPTION, no needle here at all.",
    )
    _write(notes, root, matching_note, ctx)
    _write(notes, root, other_note, ctx)

    with _cwd(root):
        word_report = report.build_word(needle, False)
        rendered = report_render.render_word(word_report)

    assert isinstance(rendered, str), f"render_word no devolvio str: {type(rendered)!r}"
    assert matching_note.headline in rendered, (
        f"la nota que de verdad caso no aparece en el texto:\n{rendered}"
    )
    assert other_note.headline in rendered, (
        f"la nota que no caso deberia aparecer igual, para dar contexto "
        f"[TEXTOS Sec.2.3, M-055 sin marcar]:\n{rendered}"
    )

    lines = rendered.splitlines()
    matching_lines = [line for line in lines if matching_note.headline in line]
    other_lines = [line for line in lines if other_note.headline in line]
    assert len(matching_lines) == 1, matching_lines
    assert len(other_lines) == 1, other_lines

    assert matching_lines[0].lstrip().startswith("›"), (
        f"la linea de la nota que caso no empieza con el marcador '>' "
        f"[TEXTOS Sec.2.3]: {matching_lines[0]!r}"
    )
    assert not other_lines[0].lstrip().startswith("›"), (
        f"la linea de la nota que NO caso lleva el marcador '>' de todas "
        f"formas: {other_lines[0]!r}"
    )


# ---------------------------------------------------------------------------
# Agregacion global de preguntas en la busqueda por palabra -- parte del
# "orden se cumple" (fila 1) aplicado a render_word: una sola seccion "LO
# QUE ESPERA DE TI", nunca una por chunk [TEXTOS Sec.2.3: Q-019 nace de
# D-044, del primer bloque [api][billing], y aun asi aparece una sola vez,
# al final de TODO el informe, no justo despues de ese bloque]
# ---------------------------------------------------------------------------


def test_render_word_questions_appear_once_after_all_chunks(
    report,
    report_render,
    model,
    config,
    validator,
    indexes,
    notes,
    zones_mod,
    tmp_repo,
    make_note,
    make_context,
):
    """Fila 1 aplicada a `render_word`: las preguntas van al final del
    informe COMPLETO, una sola vez -- no repetidas por cada pareja de
    zonas de las que provienen [TEXTOS Sec.2.3].

    Se siembra una pregunta en la zona que ordena PRIMERO
    (`report.build_word` ordena los chunks por `(zone1, zone2)`,
    ver `report.py::build_word`) y un memo en la zona que ordena
    ULTIMO -- si `render_word` imprimiera "OPEN QUESTIONS" chunk a
    chunk, saldria ANTES del memo del segundo chunk; si la agrega de
    verdad al final del informe completo (lo que pide TEXTOS Sec.2.3),
    sale DESPUES.
    """
    root = Path(tmp_repo)
    zone_first = "aaarenderwordorder"
    zone_last = "zzzrenderwordorder"
    indexes.seed(_pm_root(root))
    _register_zone(zones_mod, model, root, zone_first)
    _register_zone(zones_mod, model, root, zone_last)
    ctx = make_context(zone_names=(zone_first, zone_last))

    needle = "zzrenderwordorderneedle"
    question = make_note(
        type="Q",
        zone1=zone_first,
        zone2=zone_first,
        headline="MARK_ORDERQ_HEADLINE does this question really land last",
        description=f"MARK_ORDERQ_DESCRIPTION with the needle {needle} once.",
    )
    memo = make_note(
        type="M",
        zone1=zone_last,
        zone2=zone_last,
        headline="MARK_ORDERM_HEADLINE a memo in the zone that sorts last",
        description=f"MARK_ORDERM_DESCRIPTION with the needle {needle} once.",
    )
    _write(notes, root, question, ctx)
    _write(notes, root, memo, ctx)

    with _cwd(root):
        word_report = report.build_word(needle, False)
        rendered = report_render.render_word(word_report)

    zone_pairs = [(c.zone1, c.zone2) for c in word_report.chunks]
    assert zone_pairs == sorted(zone_pairs), (
        f"la entrada de este test asume chunks ordenados por (zone1, zone2) "
        f"[report.py::build_word] -- salio {zone_pairs!r}"
    )
    assert (zone_first, zone_first) == zone_pairs[0], zone_pairs
    assert (zone_last, zone_last) == zone_pairs[-1], zone_pairs

    occurrences = rendered.count("OPEN QUESTIONS")
    assert occurrences == 1, (
        f"'OPEN QUESTIONS' deberia aparecer UNA sola vez para todo el "
        f"informe, salio {occurrences} veces:\n{rendered}"
    )
    assert rendered.count(question.headline) == 1, (
        f"la pregunta deberia aparecer una sola vez en todo el informe: "
        f"{rendered.count(question.headline)} veces:\n{rendered}"
    )

    memo_index = rendered.index(memo.headline)
    question_section_index = rendered.index("OPEN QUESTIONS")
    assert question_section_index > memo_index, (
        f"'OPEN QUESTIONS' (indice {question_section_index}) deberia "
        f"salir DESPUES del contenido del ultimo chunk (memo en indice "
        f"{memo_index}) -- si sale antes, las preguntas se estan imprimiendo "
        f"chunk a chunk en vez de agregadas al final del informe completo"
    )


# ---------------------------------------------------------------------------
# Quinta comprobacion -- las horas llevan su etiqueta UTC [spec Sec.2, P11]
# ---------------------------------------------------------------------------


def test_render_zone_generated_at_carries_utc_label(
    report, report_render, model, zones_mod, indexes, tmp_repo
):
    """P11 (spec-sistema-memoria-v2.md Sec.2): "Todo timestamp en UTC,
    y toda hora mostrada al usuario lleva la etiqueta 'UTC' explicita."

    El valor comparado es el que `report.build_zone` puso DE VERDAD
    (`datetime.now(timezone.utc)`, en el momento real de la llamada),
    nunca una fecha tecleada aparte -- se comprueba precision de dia,
    no de minuto (ver supuesto 1 del docstring del modulo: el formato
    de minuto de TEXTOS Sec.2.1 es un ejemplo, no una gramatica
    cerrada).
    """
    root = Path(tmp_repo)
    zone = "renderutczone"
    indexes.seed(_pm_root(root))
    _register_zone(zones_mod, model, root, zone)

    with _cwd(root):
        zone_report = report.build_zone(zone, False)
        rendered = report_render.render_zone(zone_report)

    date_prefix = zone_report.generated_at.strftime("%Y-%m-%d")
    lines_with_date = [line for line in rendered.splitlines() if date_prefix in line]
    assert lines_with_date, (
        f"ninguna linea del informe lleva la fecha real de "
        f"generated_at ({date_prefix!r}):\n{rendered}"
    )
    assert any("UTC" in line for line in lines_with_date), (
        f"la fecha real de generated_at aparece sin la etiqueta 'UTC' "
        f"[spec Sec.2, P11]: {lines_with_date!r}"
    )


def test_render_word_generated_at_carries_utc_label(
    report, report_render, model, zones_mod, indexes, tmp_repo
):
    """P11 aplicado a `render_word` -- mismo criterio que la version de
    zona de arriba, sobre `WordReport.generated_at`.
    """
    root = Path(tmp_repo)
    indexes.seed(_pm_root(root))

    with _cwd(root):
        word_report = report.build_word("norendermatcheshere", False)
        rendered = report_render.render_word(word_report)

    date_prefix = word_report.generated_at.strftime("%Y-%m-%d")
    lines_with_date = [line for line in rendered.splitlines() if date_prefix in line]
    assert lines_with_date, (
        f"ninguna linea del informe por palabra lleva la fecha real de "
        f"generated_at ({date_prefix!r}):\n{rendered}"
    )
    assert any("UTC" in line for line in lines_with_date), (
        f"la fecha real de generated_at aparece sin la etiqueta 'UTC' "
        f"[spec Sec.2, P11]: {lines_with_date!r}"
    )


# ---------------------------------------------------------------------------
# render() -- RETIRADO 2026-08-04. Los tres tests que probaban su reparto
# (a render_zone/render_word y su TypeError para tipos desconocidos) se
# quitaron de aqui. `render()` no la llama nadie en produccion -- ni
# bin/memory/search.py ni ningun otro modulo, que usan `render_zone`/
# `render_word` directamente -- y su propio docstring lo admitia: existia
# SOLO para que el chequeo reflexivo de `vocabulary.FIELDS` encontrara un
# simbolo con ese nombre, porque `why`/`description` la declaraban como su
# lector. `vocabulary.py` ya se corrigio para declarar el lector real,
# `report_render.render_zone`. No se pierde cobertura real: `render_zone`
# tiene sus propios tests directos arriba (order/why-label/cero-notas/UTC,
# lineas 260-696) y `render_word` tambien (matched-line/questions-once/UTC,
# lineas 494-721) -- lo unico que probaban los tres tests retirados era el
# despachador de mentira, no el texto que producen las piezas reales.
# `render()` sigue existiendo en el fichero (la retira Ultron aparte); si
# alguien la repone dentro de seis meses pensando que se perdio por
# descuido, no fue asi: fue una retirada deliberada, vease DEUDA.md.
# ---------------------------------------------------------------------------
