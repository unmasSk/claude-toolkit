"""Contrato de lib/memory/report.py -- PIEZAS.md Sec.9.2 (compartida con
Sec.9.3, report_render.py).

report.py NO EXISTE TODAVIA. Estos tests deben fallar al importar, por
diseno -- es el ROJO del modo test-first.

REPARTO DE LA TABLA "SUS TESTS" ENTRE LAS DOS PIEZAS DE LA FICHA, Y POR
QUE AQUI SOLO HAY CUATRO (no cinco) -- decision explicita, no un hueco:
Sec.9.2 fija la tabla para "report.py y report_render.py" juntos porque
comparten ficha, pero el propio encargo es literal: "tu solo escribes
los tests de report, el que decide QUE se enseña y en que orden -- no
el que lo convierte en texto". De las cinco filas:

  2. La historia solo aparece con la opcion explicita         -> report.py
  3. Una zona vacia dice CERO NOTAS en alto, sin confundirse
     con un error                                              -> report.py
  4. Las restricciones llevan su porque                        -> report.py
  5. La busqueda por palabra marca la linea que caso            -> report.py
  1. El orden se cumple: restricciones primero, preguntas
     al final                                                  -> report_render.py

La fila 1 se DEFIERE a la pasada de Dante sobre report_render.py, no se
omite por descuido. Motivo: "restricciones arriba... preguntas al
final" es el orden en que report_render ITERA los campos de
`ZoneReport` para producir texto -- ese orden ya esta fijado, cerrado y
en verde en `model.py` (Sec.5.3: `ZoneReport` es un dataclass con
`restrictions`/`blockers`/`decisions`/`memos`/`incidents`/`questions`
como campos NOMBRADOS, no una lista donde alguien decida en que
posicion va cada cosa). `build_zone`/`build_word` no tienen ninguna
decision de orden que tomar mas alla de rellenar el campo que le
corresponde a cada nota por su tipo -- inventar aqui una asercion sobre
"orden" seria repetir el contrato de `model.py` (ya cubierto y en
verde) disfrazado de test de `report.py`. Cuando llegue la pasada de
`report_render.py` (tanda 4b, en fila, "solo cuando report este"), esa
fila 1 se prueba de verdad sobre `render_zone`/`render_word`, que son
quienes de verdad iteran los campos en ese orden para producir texto.

Las otras cuatro filas SI tienen decision real que tomar a nivel de
datos, y se adaptan aqui a la superficie declarada
(`build_zone(zone: str, include_archived: bool) -> ZoneReport`,
`build_word(word: str, include_archived: bool) -> WordReport`) en vez
de al texto renderizado: donde TEXTOS.md dice "CERO NOTAS" en letras
grandes o "Why:" en una linea, el test de aqui comprueba el dato del
que esa letra grande o esa linea saldria (recuentos en cero, tuplas
vacias, el campo `why` intacto) -- la letra en si es cosa de
`report_render.py`.

COMO SE SIEMBRA: NUNCA a mano ni con `format`/`gitcmd` sueltos como hace
`test_query.py` -- `lib/memory/notes.py` (Sec.8.1, la transaccion
validar->indice->commit) YA EXISTE Y ESTA EN VERDE en esta rama, y
usarla es exactamente "las piezas reales del sistema... nunca sembrar a
mano" que pide el encargo. Cada test llama a `notes.write(note, ctx)`
de verdad contra el `tmp_repo`, y deriva el identificador real de
`WriteResult.note_id` -- nunca lo inventa (mismo patron que
`test_notes.py::make_note`/`make_context`, replicado aqui porque cada
fichero de test trae su propia copia, convencion ya establecida en
`test_query.py`/`test_clusters.py`).

QUE HACE FALTA PARA SIMULAR UNA NOTA ARCHIVADA (fila 2), Y POR QUE A
MANO: `notes.replace()`/`notes.close()` estan declaradas en la
Superficie de Sec.8.1 pero DESCOPADAS A PROPOSITO de esa tarea anterior
-- lanzan `NotImplementedError` (ver su docstring: "esas seis [filas],
ni una mas"). No existe todavia ninguna transaccion real que mueva una
nota de un indice vigente a `ARCHIVED.md`. El test de la fila 2
reproduce, a mano, los DOS pasos que esa transaccion haria (ya
verificados uno a uno, y en verde, cada uno en su propio contrato):
`indexes.remove(old_id, "MEMOS.md", root)` seguido de
`indexes.archive(ArchiveLine(...), root)`. Esto NO reimplementa nada de
`report.py` (la pieza bajo prueba) -- son dos piezas hermanas ya
construidas, usadas tal cual.

SUPUESTOS DECLARADOS, sin fuente literal en Sec.9.2 (mismo tipo de
hueco que en query-contract-notes.md/clusters-contract-notes.md):

1. **Ni `build_zone` ni `build_word` declaran `root`/`cwd`** -- mismo
   patron que `query.py` (Sec.8.2) y `notes.py` (Sec.8.1): se asume que
   leen contra el cwd del proceso, derivando la raiz del repo con
   `gitcmd.repo_root(Path.cwd())` (mismo helper que `notes.py::
   _repo_root()`/`rules.py::_repo_root()` ya usan). Cada test hace
   `_cwd(tmp_repo)` (mismo helper que `test_notes.py`) alrededor de
   CUALQUIER llamada a `report.*`/`notes.write`, nunca le pasa una raiz
   explicita que la superficie declarada no tiene.
2. **Los ocho indices y `zones.json` viven en `<root>/.claude/
   project-memory/`** -- ruta ya fijada y usada por `rules.py::
   _rules_file_path()` y por `notes.py` (Sec.7.3/Sec.9.7), no una
   invencion de este fichero.
3. **Que eje (`zone1` o `zone2`) casa el parametro `zone: str` de
   `build_zone`/con que campo casan `WordChunk.zone1`/`zone2` de
   `build_word`, Sec.9.2 no lo dice.** Se evita por diseno, no se
   adivina: CADA nota de este fichero se siembra con `zone1 == zone2 ==
   <la misma zona>`, asi que el resultado es identico sea cual sea el
   eje real que `report.py` use -- ningun test de aqui depende de
   adivinar la respuesta. Queda anotado como pregunta real para quien
   implemente: con `zone1 != zone2`, una zona pasada a `build_zone` que
   solo aparece como `zone1` en algunas notas y como `zone2` en otras
   -- ¿las trae todas, o solo las que casan por un eje? Sin texto que lo
   fije, no se inventa aqui.
4. **Como se marca una nota archivada DENTRO de una tupla plana
   (`memos`, `restrictions`, etc.) cuando `include_archived=True` no
   esta declarado.** `model.ZoneReport` no trae un campo aparte de
   "cuales son archivadas" para memos/restricciones/incidencias/
   preguntas/bloqueantes -- eso SI existe para `decisions`
   (`Cluster.archived_ids`, Sec.5.3) pero no para el resto. El test de
   la fila 2 comprueba unicamente PRESENCIA/AUSENCIA en la tupla segun
   el flag -- nunca inventa una aserquia sobre COMO se distingue una
   nota archivada de una vigente una vez las dos estan en la misma
   tupla, porque Sec.9.2 no lo fija (mismo criterio que
   clusters-contract-notes.md, supuesto 3: no fabricar contrato no
   escrito).
5. **Un `Zone` real, dado de alta en `zones.json` via `zones.add()`, es
   condicion previa para que `build_zone` funcione.** Se infiere de que
   `model.ZoneReport.zone: Zone` es un objeto con `description` propia
   (no derivable de las notas) y de que TEXTOS.md Sec.2.2 dice
   literalmente "la zona existe en zones.json" como parte del contrato
   de la zona vacia. El caso de una zona NUNCA registrada en
   `zones.json` (a diferencia de "registrada pero sin notas", que si es
   la fila 3) no se prueba aqui -- pertenece a un flujo de rechazo
   distinto (TEXTOS Sec.1.1) que no es parte de esta tabla.
6. **`ctx.zones` (el diccionario en memoria que `notes.write()`
   consulta para validar) y `zones.json` en disco (lo que `report.py`
   leeria) son DOS representaciones separadas de la misma zona, y este
   fichero las mantiene coherentes a mano en cada test** -- exactamente
   igual que `test_notes.py::make_context` construye `ctx.zones` sin
   tocar disco en absoluto. `report.py` no participa en absoluto de la
   escritura; solo lee lo que `zones.add()` dejo en `zones.json`.

No se toca produccion: si `lib/memory/report.py` no existe, estos tests
se quedan en rojo tal cual estan -- eso es lo esperado. No se toca
ningun fichero de un companero (`vocabulary.py`, `validator.py`,
`rules.py`, `health.py` estan fuera de esta tarea, y no se han tocado).
"""

import contextlib
import dataclasses
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from .conftest import import_lib_memory_module

_BASE_NOTE_FIELDS = dict(
    type="M",
    id="",
    zone1="product",
    zone2="report-test",
    headline="MARK_BASE_HEADLINE ordinary memo for lib/memory/report.py tests",
    description="MARK_BASE_DESCRIPTION not empty, not special",
    timestamp=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
)


@pytest.fixture
def report():
    return import_lib_memory_module("report")


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
    MEMORIA -- mismo patron que `test_notes.py::make_context`. No toca
    `zones.json`: eso es responsabilidad de `_register_zone` (abajo),
    la representacion en DISCO que `report.py` de verdad lee (ver
    supuesto 6 del docstring del modulo).
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
    restaura siempre -- mismo helper que `test_notes.py::_cwd`, ver
    supuesto 1 del docstring del modulo.
    """
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _pm_root(root) -> Path:
    """Raiz de los ocho indices y zones.json -- ver supuesto 2 del
    docstring del modulo."""
    return Path(root) / ".claude" / "project-memory"


def _zones_json_path(root) -> Path:
    return _pm_root(root) / "zones.json"


def _register_zone(zones_mod, model, root, name, description=None):
    """Da de alta `name` en el `zones.json` REAL de `root` -- la
    representacion en disco que `report.py` lee (supuestos 5 y 6)."""
    zones_mod.add(
        model.Zone(
            name=name,
            description=description or f"MARK zone {name} for report.py contract",
            aliases=(),
        ),
        _zones_json_path(root),
    )


# ---------------------------------------------------------------------------
# Fila 2 -- la historia solo aparece con la opcion explicita
# ---------------------------------------------------------------------------


def test_history_only_appears_with_include_archived_true(
    report,
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
    """Fila 2: la historia solo aparece con la opcion explicita.

    Fallo real que previene: un informe de cien lineas donde lo vigente
    se pierde entre lo retirado.
    """
    root = Path(tmp_repo)
    zone = "reporthistzone"
    indexes.seed(_pm_root(root))
    _register_zone(zones_mod, model, root, zone)
    ctx = make_context(zone_names=(zone,))

    old_note = make_note(
        type="M",
        zone1=zone,
        zone2=zone,
        headline="MARK_OLD memo later superseded by a newer one in this test",
        description="MARK_OLD description, superseded within this test.",
    )
    with _cwd(root):
        old_result = notes.write(old_note, ctx)
    assert old_result.ok, (
        f"seed de old_note fallo: {old_result.git_error or old_result.rejections}"
    )

    extended_ctx = dataclasses.replace(
        ctx, known_ids=ctx.known_ids | {old_result.note_id}
    )
    new_note = make_note(
        type="M",
        zone1=zone,
        zone2=zone,
        headline="MARK_NEW memo that supersedes the old one seeded above",
        description="MARK_NEW description, the live replacement.",
        replaces=old_result.note_id,
    )
    with _cwd(root):
        new_result = notes.write(new_note, extended_ctx)
    assert new_result.ok, (
        f"seed de new_note fallo: {new_result.git_error or new_result.rejections}"
    )

    # Camino 1 de la retirada [spec Sec.5]: la nota vieja sale del
    # indice vigente y entra en ARCHIVED.md. `notes.replace()` no existe
    # todavia (NotImplementedError, ver docstring del modulo) -- se
    # reproducen a mano los dos pasos reales, con piezas ya en verde.
    pm_root = _pm_root(root)
    indexes.remove(old_result.note_id, "MEMOS.md", pm_root)
    indexes.archive(
        model.ArchiveLine(
            date=old_note.timestamp.date(),
            type="M",
            id=old_result.note_id,
            zone1=zone,
            zone2=zone,
            headline=old_note.headline,
            destination="replaced",
            destination_detail=new_result.note_id,
        ),
        pm_root,
    )

    with _cwd(root):
        vigente_only = report.build_zone(zone, False)
        with_history = report.build_zone(zone, True)

    vigente_ids = {n.id for n in vigente_only.memos}
    assert old_result.note_id not in vigente_ids, (
        f"la nota archivada {old_result.note_id!r} aparecio sin pedir el historial -- "
        f"memos vigentes: {vigente_ids!r}"
    )
    assert new_result.note_id in vigente_ids, (
        f"la nota vigente {new_result.note_id!r} no aparecio en el informe por defecto"
    )

    history_ids = {n.id for n in with_history.memos}
    assert old_result.note_id in history_ids, (
        f"con include_archived=True la nota retirada {old_result.note_id!r} sigue sin "
        f"aparecer -- memos: {history_ids!r}"
    )

    assert vigente_only.live_count == 1 and vigente_only.archived_count == 1, (
        "los recuentos deben reflejar la realidad siempre, se pida o no el historial: "
        f"live={vigente_only.live_count!r} archived={vigente_only.archived_count!r}"
    )
    assert with_history.live_count == 1 and with_history.archived_count == 1, (
        "los recuentos no deben cambiar segun include_archived, solo que se INCLUYA "
        f"el contenido: live={with_history.live_count!r} "
        f"archived={with_history.archived_count!r}"
    )


# ---------------------------------------------------------------------------
# Fila 3 -- una zona vacia dice CERO NOTAS en alto, sin confundirse con un error
# ---------------------------------------------------------------------------


def test_zone_with_zero_notes_reports_zero_loudly_not_as_an_error(
    report, model, zones_mod, indexes, tmp_repo
):
    """Fila 3: una zona vacia dice CERO NOTAS en alto, y es imposible
    confundirlo con un error.

    Fallo real que previene: el silencio del v1 -- algo deja de
    funcionar y nadie se entera.

    A nivel de datos (report_render decide la letra grande, no esta
    pieza -- ver docstring del modulo): que `build_zone` no lance, no
    devuelva `None`, y que los recuentos y las seis tuplas de categoria
    salgan en cero de forma EXPLICITA -- nunca ausentes.
    """
    root = Path(tmp_repo)
    zone = "reportemptyzone"
    indexes.seed(_pm_root(root))
    _register_zone(zones_mod, model, root, zone)

    with _cwd(root):
        result = report.build_zone(zone, False)

    assert result is not None, (
        "build_zone() de una zona registrada y sin notas devolvio None -- "
        "un silencio indistinguible de un fallo"
    )
    assert isinstance(result, model.ZoneReport), (
        f"build_zone() no devolvio un ZoneReport, devolvio {type(result)!r}"
    )
    assert result.zone.name == zone, (
        f"el informe no identifica la zona real registrada: {result.zone!r}"
    )
    assert result.live_count == 0, f"live_count deberia ser 0, salio {result.live_count!r}"
    assert result.archived_count == 0, (
        f"archived_count deberia ser 0, salio {result.archived_count!r}"
    )
    assert result.restrictions == (), result.restrictions
    assert result.blockers == (), result.blockers
    assert result.decisions == (), result.decisions
    assert result.memos == (), result.memos
    assert result.incidents == (), result.incidents
    assert result.questions == (), result.questions


# ---------------------------------------------------------------------------
# Fila 4 -- las restricciones llevan su porque
# ---------------------------------------------------------------------------


def test_restriction_why_field_survives_the_round_trip(
    report,
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
    """Fila 4: las restricciones llevan su porque.

    Fallo real que previene: un titular que nadie obedece porque no
    dice que pasa si se lo salta.

    El texto de `Why:` en el informe renderizado es cosa de
    `report_render.py` (`vocabulary.FIELDS["why"].reader` apunta ahi,
    literal) -- lo que `build_zone` tiene que garantizar es que el
    campo `why` de una R sobrevive intacto el viaje real: escrito con
    `notes.write()` contra git de verdad, releido por `report.build_zone`.
    El valor esperado es el que este mismo test escribio, nunca uno
    tecleado aparte como "resultado" (unmassk-standards Sec.34).
    """
    root = Path(tmp_repo)
    zone = "reportwhyzone"
    indexes.seed(_pm_root(root))
    _register_zone(zones_mod, model, root, zone)
    ctx = make_context(zone_names=(zone,))

    needle_why = (
        "MARK_WHY_NEEDLE this exact sentence must survive git and come back unchanged"
    )
    restriction = make_note(
        type="R",
        zone1=zone,
        zone2=zone,
        headline="MARK_RESTRICTION never do the thing this test forbids",
        description="MARK_RESTRICTION description, separate from the why field.",
        why=needle_why,
    )
    with _cwd(root):
        result = notes.write(restriction, ctx)
    assert result.ok, (
        f"seed de la restriccion fallo: {result.git_error or result.rejections}"
    )

    with _cwd(root):
        zone_report = report.build_zone(zone, False)

    matching = [n for n in zone_report.restrictions if n.id == result.note_id]
    assert matching, (
        f"la restriccion {result.note_id!r} no aparece en zone_report.restrictions -- "
        f"restricciones presentes: {[n.id for n in zone_report.restrictions]!r}"
    )
    assert matching[0].why == needle_why, (
        f"el campo why no volvio identico via build_zone: {matching[0].why!r} != "
        f"{needle_why!r}"
    )


# ---------------------------------------------------------------------------
# Fila 5 -- la busqueda por palabra marca la linea que caso
# ---------------------------------------------------------------------------


def test_word_search_marks_which_notes_actually_matched(
    report,
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
    """Fila 5: la busqueda por palabra marca la linea que caso.

    Fallo real que previene: saber que una nota caso pero no por que, y
    tener que leerla entera para averiguarlo.

    A nivel de datos (el simbolo `>` es cosa de `report_render.py`):
    `WordChunk.notes` trae el estado completo de la zona (incluida una
    nota que NO caso, para dar contexto -- TEXTOS.md Sec.2.3 muestra
    M-055 sin marcar dentro de un chunk con otras SI marcadas) y
    `WordChunk.matched_ids` distingue cual de ellas caso de verdad.
    """
    root = Path(tmp_repo)
    zone = "reportwordzone"
    indexes.seed(_pm_root(root))
    _register_zone(zones_mod, model, root, zone)
    ctx = make_context(zone_names=(zone,))

    needle = "zzreportwordneedle"
    matching_note = make_note(
        type="M",
        zone1=zone,
        zone2=zone,
        headline="MARK_MATCH memo that mentions the search needle below",
        description=f"MARK_MATCH description containing the needle word {needle} once.",
    )
    other_note = make_note(
        type="M",
        zone1=zone,
        zone2=zone,
        headline="MARK_NOMATCH memo without the needle anywhere in its text",
        description="MARK_NOMATCH description, no needle here at all.",
    )
    with _cwd(root):
        matching_result = notes.write(matching_note, ctx)
        other_result = notes.write(other_note, ctx)
    assert matching_result.ok, (
        f"seed de matching_note fallo: "
        f"{matching_result.git_error or matching_result.rejections}"
    )
    assert other_result.ok, (
        f"seed de other_note fallo: {other_result.git_error or other_result.rejections}"
    )

    with _cwd(root):
        word_report = report.build_word(needle, False)

    target_chunks = [
        chunk
        for chunk in word_report.chunks
        if chunk.zone1 == zone and chunk.zone2 == zone
    ]
    assert target_chunks, (
        f"ningun WordChunk corresponde a la zona sembrada {zone!r} -- zonas "
        f"devueltas: {[(c.zone1, c.zone2) for c in word_report.chunks]!r}"
    )
    chunk = target_chunks[0]
    chunk_ids = {n.id for n in chunk.notes}
    assert matching_result.note_id in chunk_ids, (
        f"la nota que de verdad contiene la palabra no aparece en el chunk: "
        f"{chunk_ids!r}"
    )
    assert other_result.note_id in chunk_ids, (
        "el chunk deberia mostrar el estado completo de la zona (TEXTOS Sec.2.3, "
        f"notas sin marcar incluidas), no solo lo que caso: {chunk_ids!r}"
    )
    assert matching_result.note_id in chunk.matched_ids, (
        f"la nota que de verdad contiene la palabra no esta marcada en matched_ids: "
        f"{chunk.matched_ids!r}"
    )
    assert other_result.note_id not in chunk.matched_ids, (
        f"una nota que no contiene la palabra aparece marcada como si hubiera "
        f"casado: {chunk.matched_ids!r}"
    )


# ---------------------------------------------------------------------------
# Regresion de Argus (2026-08-02) -- bug 1 de test_boot.py ("el arranque
# reventaba en un proyecto recien instalado") tenia el mismo agujero aqui:
# `indexes.archived_ids()` leia `ARCHIVED.md` sin comprobar que existiera.
# Arreglado en la misma pieza (`indexes.archived_ids`, un ausente cuenta como
# cero), asi que estos dos tests solo fijan la regresion -- no tocan
# produccion.
# ---------------------------------------------------------------------------


def test_build_zone_on_a_repo_where_indexes_seed_never_ran_does_not_crash(
    report, model, zones_mod, tmp_repo
):
    """El mismo agujero que `test_boot.py::
    test_a_repo_where_indexes_seed_never_ran_boots_without_crashing`,
    para `build_zone`. Zona registrada en `zones.json` (paso real
    previo, `gitmem zone add`) pero `indexes.seed()` JAMAS corrio --
    ninguno de los ocho ficheros de indice existe todavia, ni
    `ARCHIVED.md`. Se crea solo el directorio `.claude/project-memory/`
    a mano (lo necesita `zones.add()` para escribir su fichero
    temporal), nunca los ficheros de indice.
    """
    root = Path(tmp_repo)
    zone = "reportfreshzone"
    pm = _pm_root(root)
    pm.mkdir(parents=True)
    _register_zone(zones_mod, model, root, zone)

    assert not (pm / "ARCHIVED.md").exists(), (
        f"comprobacion previa: {pm / 'ARCHIVED.md'} ya existe -- el "
        "escenario no es genuinamente fresco"
    )
    assert not (pm / "RESTRICTIONS.md").exists(), (
        f"comprobacion previa: {pm / 'RESTRICTIONS.md'} ya existe -- el "
        "escenario no es genuinamente fresco"
    )

    with _cwd(root):
        result = report.build_zone(zone, False)  # NO debe lanzar

    assert result is not None, (
        "build_zone() de una zona registrada, sin ningun indice sembrado "
        "todavia, devolvio None -- un silencio indistinguible de un fallo"
    )
    assert isinstance(result, model.ZoneReport), (
        f"build_zone() no devolvio un ZoneReport, devolvio {type(result)!r}"
    )
    assert result.zone.name == zone
    assert result.live_count == 0 and result.archived_count == 0, (
        f"sin ninguna nota ni ARCHIVED.md, los dos recuentos deberian ser "
        f"cero: live_count={result.live_count!r}, archived_count={result.archived_count!r}"
    )
    assert result.restrictions == () and result.memos == (), (
        f"sin notas, las tuplas de categoria deberian salir vacias, no "
        f"reventar: restrictions={result.restrictions!r}, memos={result.memos!r}"
    )


def test_build_word_on_a_repo_with_no_project_memory_directory_at_all_does_not_crash(
    report, model, tmp_repo
):
    """Mismo agujero, para `build_word` -- sin ninguna zona que registrar
    (`build_word` no llama a `_load_zone`), el escenario mas fresco
    posible es que `.claude/project-memory/` no exista en absoluto
    todavia, ni siquiera como directorio vacio.
    """
    root = Path(tmp_repo)
    pm = _pm_root(root)
    assert not pm.exists(), (
        f"comprobacion previa: {pm} ya existe -- el escenario no es "
        "genuinamente fresco"
    )

    with _cwd(root):
        result = report.build_word("MARK_NONEXISTENT_WORD_FRESHPROJECT", False)  # NO debe lanzar

    assert result is not None, (
        "build_word() en un repo sin project-memory/ devolvio None -- un "
        "silencio indistinguible de un fallo"
    )
    assert isinstance(result, model.WordReport), (
        f"build_word() no devolvio un WordReport, devolvio {type(result)!r}"
    )
    assert result.zone_count == 0 and result.live_count == 0, (
        f"sin ninguna nota, los recuentos deberian ser cero: "
        f"zone_count={result.zone_count!r}, live_count={result.live_count!r}"
    )
    assert result.chunks == (), f"sin notas no deberia haber ningun chunk: {result.chunks!r}"
