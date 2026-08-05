"""Contrato de lib/memory/indexes.py -- PIEZAS.md Sec.7.3.

indexes.py NO EXISTE TODAVIA. Estos tests deben fallar al importar, por
diseno -- es el ROJO del modo test-first. Uno por fila de la tabla "Sus
tests" de Sec.7.3:

  1. `seed` dos veces no duplica ni borra nada.
  2. Las tres formas de destino del archivo se parsean: `replaced by` ·
     `closed:` · `promoted to`.
  4. Insertar en un indice inexistente falla en alto.
  5. Ida y vuelta de fichero: insertar tres lineas y releerlas con
     `read` devuelve las tres, en orden y en el indice correcto.

Retirement note (2026-08-04): la fila 3 ("los recuentos se calculan
leyendo, nunca se guardan", `test_counts_are_computed_by_reading_never_stored`)
se retiro junto con `indexes.counts()`. Medido por Ultron antes de tocar
nada: `counts()` no tenia ningun llamador en `lib/memory/`, `bin/` ni
`hooks/` -- ni siquiera dentro de su propio fichero. El desglose de notas
por tipo que hacia ya lo calcula cada sitio que lo necesita, leyendo
directamente del historial de git: el bloque COUNTS del arranque
(`boot.py`) y el informe de zona (`report.py::_by_type`). Ese test era lo
unico que mantenia viva la funcion -- un test que demuestra que funciona
algo que nadie usa. Ver el bloque de retiro mas abajo, donde vivia el
test, para el detalle.

El fixture `indexes` importa por ruta de fichero
(`import_lib_memory_module`, ver conftest.py) para que cada test falle
individualmente con la causa real (`FileNotFoundError`:
lib/memory/indexes.py no existe todavia), en vez de un unico error de
coleccion para todo el fichero -- mismo patron que test_vocabulary.py,
test_config.py y test_similar.py. Se lista antes que `model` en la
firma de cada test para que sea ESE fallo, y no el de `model.py`
(tambien podria faltar), el que se reporte primero -- pytest instancia
los fixtures independientes de un test en el orden en que aparecen
como parametros (mismo truco que test_similar.py, ver
memoria-v2 dante memory notes).

`indexes.py` es "capa 2, git, los indices, y la pieza unica" (PIEZAS.md
Sec.7): lee y escribe los ocho ficheros de indice, y "nadie mas los
toca". Recibe/devuelve `IndexLine`/`ArchiveLine` (PIEZAS.md Sec.5.3,
`model.py`) -- no strings crudos, no `Note` completas. Internamente
delega la linea de texto exacta a `format.py` (Sec.6.4:
`build_index_line`/`parse_index_line`,
`build_archive_line`/`parse_archive_line`), pero eso es un detalle de
implementacion que estos tests no fijan: se prueba la superficie
publica de `indexes.py` (Sec.7.3), no como delega internamente.

No se toca produccion: si `lib/memory/indexes.py` no existe, estos
tests se quedan en rojo tal cual estan -- eso es lo esperado.

**Por que `_assert_fields_match`/`_assert_lines_match` comparan campo a
campo y nunca con `==` directo sobre el objeto:** mismo hallazgo que
test_format.py (ver zones-contract-notes.md en la memoria de este
agente) -- dos dataclasses de `model.py` cargadas por rutas de fichero
distintas (el fixture `model` de este test frente a lo que
`indexes.py` use por dentro para construir las mismas clases al leer
un fichero) pueden acabar siendo clases Python DISTINTAS aunque el
codigo fuente sea identico, porque el `__eq__` generado por
`@dataclass` comprueba `self.__class__ is other.__class__` antes que
los campos. Comparar `==` directamente haria que las filas 1, 2 y 5
fallaran incluso con una implementacion correcta.
"""

import dataclasses
import json
import os
import subprocess
import sys
import time
from datetime import date

import pytest

from .conftest import LIB_MEMORY_DIR, import_lib_memory_module


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def model():
    return import_lib_memory_module("model")


@pytest.fixture
def index_names():
    """Los ocho nombres literales de fichero, leidos de vocabulary.py.

    No se duplican como strings sueltos en cada test: se toman de la
    unica fuente cerrada que los declara (PIEZAS.md Sec.6.1,
    `vocabulary.INDEX_FILES`). vocabulary.py ya existe y esta en verde
    (Sec.6.1 se hizo antes que esta pieza), asi que este fixture no
    aporta rojo por si mismo -- solo evita que "DECISIONS.md"/
    "MEMOS.md"/"ARCHIVED.md" se escriban a mano sin comprobar que
    siguen siendo los nombres reales.
    """
    vocabulary = import_lib_memory_module("vocabulary")
    names = vocabulary.INDEX_FILES
    assert "DECISIONS.md" in names
    assert "MEMOS.md" in names
    assert "ARCHIVED.md" in names
    return names


def _assert_fields_match(parsed, expected):
    """Compara campo a campo, nunca con `==` directo sobre el objeto.

    Ver la nota del docstring del modulo. `parsed` es lo que devolvio
    `indexes.py`; `expected` es el objeto que este test construyo con
    el fixture `model`.
    """
    assert parsed is not None
    for field in dataclasses.fields(expected):
        parsed_value = getattr(parsed, field.name)
        expected_value = getattr(expected, field.name)
        assert parsed_value == expected_value, (
            f"campo {field.name!r} no coincide: "
            f"{parsed_value!r} != {expected_value!r}"
        )


def _assert_lines_match(parsed_tuple, expected_tuple):
    """Version en tupla de `_assert_fields_match`, en orden."""
    assert len(parsed_tuple) == len(expected_tuple), (
        f"se esperaban {len(expected_tuple)} lineas, llegaron "
        f"{len(parsed_tuple)}: {parsed_tuple!r}"
    )
    for parsed, expected in zip(parsed_tuple, expected_tuple):
        _assert_fields_match(parsed, expected)


def test_seed_twice_does_not_duplicate_or_erase(
    indexes, model, index_names, tmp_path
):
    """Fila 1: `seed` dos veces no duplica ni borra nada.

    Fallo real que previene: instalar en un proyecto que ya tiene notas
    y vaciarle los indices -- la segunda vez que corre `seed` (p.ej.
    una reinstalacion, o un `gitmem doctor` que la llama de nuevo) tiene
    que encontrar la nota que ya existia, no un fichero en blanco.
    """
    root = tmp_path / "project-memory"
    decisions_file = "DECISIONS.md"
    assert decisions_file in index_names

    indexes.seed(root)
    line = model.IndexLine(
        id="D-030",
        zone1="product",
        zone2="auth",
        headline="login with JWT + Google OAuth",
    )
    indexes.insert(line, decisions_file, root)

    indexes.seed(root)  # segunda instalacion: el proyecto ya tiene notas

    result = indexes.read(decisions_file, root)

    _assert_lines_match(result, (line,))


def test_three_archive_destination_forms_are_parsed(
    indexes, model, index_names, tmp_path
):
    """Fila 2: las tres formas de destino del archivo se parsean.

    Fallo real que previene: una nota retirada desaparece del informe
    sin dejar rastro de a donde fue -- si una de las tres formas
    (`replaced by` / `closed:` / `promoted to`) no se reconociera, esa
    linea de ARCHIVED.md se perderia o se leeria con el destino
    equivocado.

    Las tres lineas son literales, copiadas byte a byte de TEXTOS.md
    Sec.4 (verificado con `repr()` sobre el fichero fuente antes de
    escribir este test, no tecleadas a ojo) -- no se fabrica el
    contenido de ARCHIVED.md a mano con un formato inventado, se usa el
    mismo texto que la especificacion ya fija como ejemplo canonico.
    El fichero se escribe directamente (sin pasar por una futura
    `indexes.archive()`) porque esta fila prueba la mitad LECTORA del
    contrato -- un ARCHIVED.md real puede tener lineas mas viejas que
    la version actual del escritor, y `read_archive` tiene que seguir
    parseandolas igual.
    """
    root = tmp_path / "project-memory"
    archived_file = "ARCHIVED.md"
    assert archived_file in index_names

    indexes.seed(root)
    archived_path = next(root.rglob(archived_file))
    archived_path.write_text(
        "2026-06-02  [D-036][product][auth] \U0001F9ED session lifetime is 7 days  →  replaced by D-041\n"
        "2026-06-20  [I-014][testing][auth] \U0001F525 session fixation on the tenant switcher  →  closed: arreglado en #58 y con muro puesto (R-018)\n"
        "2026-07-30  [Q-009][ui][amianto] ❓ should the report export to XLSX too?  →  promoted to X-030\n",
        encoding="utf-8",
    )

    result = indexes.read_archive(root)

    expected = (
        model.ArchiveLine(
            date=date(2026, 6, 2),
            type="D",
            id="D-036",
            zone1="product",
            zone2="auth",
            headline="session lifetime is 7 days",
            destination="replaced",
            destination_detail="D-041",
        ),
        model.ArchiveLine(
            date=date(2026, 6, 20),
            type="I",
            id="I-014",
            zone1="testing",
            zone2="auth",
            headline="session fixation on the tenant switcher",
            destination="closed",
            destination_detail="arreglado en #58 y con muro puesto (R-018)",
        ),
        model.ArchiveLine(
            date=date(2026, 7, 30),
            type="Q",
            id="Q-009",
            zone1="ui",
            zone2="amianto",
            headline="should the report export to XLSX too?",
            destination="promoted",
            destination_detail="X-030",
        ),
    )

    _assert_lines_match(result, expected)


# Retirement note (2026-08-04): test_counts_are_computed_by_reading_never_stored
# (fila 3, "los recuentos se calculan leyendo, nunca se guardan") se retiro
# junto con `indexes.counts()`. Medido por Ultron antes de tocar nada:
# `counts()` no tenia ningun llamador en `lib/memory/`, `bin/` ni `hooks/` --
# ni siquiera dentro de su propio fichero. El desglose de notas por tipo que
# hacia ya lo calculan, por su cuenta y leyendo directamente del historial de
# git (nunca de los ficheros indice), el bloque COUNTS del arranque
# (`boot.py`) y el informe de zona (`report.py::_by_type`). Este test era lo
# unico que mantenia viva la funcion -- un test que demuestra que funciona
# algo que el codigo no va a hacer nunca. Cobertura verificada antes de
# retirar: no probaba ninguna otra conducta de `indexes.py` (lectura de
# fichero, aislamiento entre indices, orden) que no cubra ya alguno de los
# tests restantes de este fichero -- ver fila 5 para la ida y vuelta de
# lectura/escritura, y fila 4 para el fallo en alto sobre indice ausente.
# `counts()` en si misma sigue en `lib/memory/indexes.py`; la retira Ultron
# por separado.


def test_insert_into_nonexistent_index_fails_loud(
    indexes, model, index_names, tmp_path
):
    """Fila 4: insertar en un indice inexistente falla en alto.

    Fallo real que previene: un indice que se crea solo, medio vacio, y
    parece que no hay notas -- si `insert` abriera el fichero en modo
    "crear si no existe" en vez de exigir que `seed` haya corrido
    antes, una perdida de `seed()` (bug, migracion a medias, fichero
    borrado) se disfrazaria de "cero notas" en vez de gritar que algo
    esta mal.

    `root` SI existe (se crea explicitamente) para aislar la causa: lo
    que falta es el fichero de indice, no el directorio contenedor --
    si no se aislara, un `FileNotFoundError` por directorio ausente
    pasaria este test por el motivo equivocado.
    """
    root = tmp_path / "project-memory"
    root.mkdir(parents=True)
    decisions_file = "DECISIONS.md"
    assert decisions_file in index_names
    assert not any(root.rglob(decisions_file))

    line = model.IndexLine(
        id="D-030",
        zone1="product",
        zone2="auth",
        headline="login with JWT + Google OAuth",
    )

    with pytest.raises(Exception):
        indexes.insert(line, decisions_file, root)

    assert not any(root.rglob(decisions_file)), (
        "insert() en un indice inexistente no debe crear un fichero "
        "medio vacio -- debe fallar en alto sin escribir nada"
    )


def test_insert_three_lines_round_trips_in_order_and_correct_index(
    indexes, model, index_names, tmp_path
):
    """Fila 5: ida y vuelta de fichero.

    Insertar tres lineas y releerlas con `read` devuelve las tres, en
    orden y en el indice correcto.

    Fallo real que previene: una nota que se guarda en el fichero
    equivocado, o que se pierde entre otras al reescribir -- dos
    inserciones consecutivas en DECISIONS.md no pueden pisarse entre
    si, y una insercion en MEMOS.md no puede aparecer (ni desplazar
    nada) en DECISIONS.md.
    """
    root = tmp_path / "project-memory"
    decisions_file = "DECISIONS.md"
    memos_file = "MEMOS.md"
    assert decisions_file in index_names
    assert memos_file in index_names

    indexes.seed(root)

    decision_1 = model.IndexLine(
        id="D-030",
        zone1="product",
        zone2="auth",
        headline="login with JWT + Google OAuth",
    )
    decision_2 = model.IndexLine(
        id="D-041",
        zone1="product",
        zone2="auth",
        headline="session lifetime raised to 30 days",
    )
    memo_1 = model.IndexLine(
        id="M-021",
        zone1="api",
        zone2="auth",
        headline="google returns email_verified=false for aliases",
    )

    indexes.insert(decision_1, decisions_file, root)
    indexes.insert(decision_2, decisions_file, root)
    indexes.insert(memo_1, memos_file, root)

    decisions_result = indexes.read(decisions_file, root)
    memos_result = indexes.read(memos_file, root)

    _assert_lines_match(decisions_result, (decision_1, decision_2))
    _assert_lines_match(memos_result, (memo_1,))


# ---------------------------------------------------------------------------
# Regresion permanente, encontrada por Moriarty (rompio la capa 1) y
# arreglada el 2026-08-02 -- "es el mas grave de toda la obra": dos
# procesos reales concurrentes sobre el MISMO indice, uno insertando una
# nota, otro retirando otra distinta, perdian la nota recien insertada sin
# un solo error: 25 de 40 intentos contra el codigo viejo. Los dos
# procesos terminaban con exito.
#
# "insertar contra insertar SI aguantaba" (el modo anadir del sistema
# operativo es atomico por si solo) -- lo que rompia era mezclar insertar
# con una reescritura (remove() lee el fichero entero y lo rescribe). Por
# eso este test es especificamente insert() contra remove(), nunca
# insert() contra insert(): un test que solo lanzara inserciones pasaria
# siempre y no probaria nada.
#
# CONTRA PROCESOS REALES, no hilos: un hilo Python de este mismo interprete
# no reproduce el modelo historico del bug (insert() sin `file_lock()` en
# absoluto, un `open(path, "a")` crudo del sistema operativo -- confirmado
# en el mutation-check de abajo).
#
# En vez de repetir 40 intentos y contar fallos (estadistico, y a veces no
# fuerza la ventana real), este test fuerza la ventana EXACTA que el
# encargo describe -- "un insert() que cae justo entre la lectura y la
# escritura de un remove() concurrente" -- parcheando
# `pathlib.Path.read_text` SOLO dentro del subproceso de `remove()` (nunca
# en el fichero de produccion, en disco): tras la lectura real, el
# subproceso de remove() escribe un marcador y se PAUSA hasta que el test
# suelta un segundo marcador. El proceso padre lanza el subproceso de
# insert() (real, tal cual, sin parchear) justo durante esa pausa, le da
# un respiro para correr, y solo entonces suelta a remove() para que
# termine con lo que sea que leyo. Determinista por construccion, no
# depende de que el scheduler del SO decida solapar dos lanzamientos.
#
# Confirmado en vivo, en ambas direcciones, antes de escribir este test
# (scratchpad de esta sesion,
# `dante_bug_regressions_20260802/race_probe_v2.py` +
# `dante_bug_regressions_20260802/indexes_bug/indexes.py`):
#   - Contra el codigo real (este mismo, sin tocar): 5/5 intentos
#     correctos -- D-099 presente, D-005 ausente, ambos procesos rc=0.
#     Insert(), al reintentar el candado tras el bloqueo, vuelve a leer el
#     fichero YA actualizado por remove() -- nunca escribe con datos
#     caducos.
#   - Contra una copia de indexes.py con insert() vuelto a un
#     `path.open("a").write(...)` crudo sin `file_lock()` (el modelo
#     historico exacto que este encargo describe): 5/5 intentos
#     reproducen el fallo narrado al detalle -- D-099 NUNCA aparece en el
#     indice final, D-005 si se retira, y ambos procesos terminan con
#     rc=0 en los dos casos (sin una sola excepcion ni codigo de error),
#     exactamente "los dos procesos terminaban con exito, sin un solo
#     error".
# ---------------------------------------------------------------------------


_REMOVE_WITH_FORCED_READ_WRITE_GAP_SCRIPT = """
import importlib.util, os, sys, pathlib, time
sys.path.insert(0, {lib_memory_dir!r})

def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join({lib_memory_dir!r}, name + ".py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

indexes = _load("indexes")

_target = str(pathlib.Path({root!r}) / {decisions_file!r})
_real_read_text = pathlib.Path.read_text
_state = {{"paused": False}}

def _patched_read_text(self, *a, **kw):
    result = _real_read_text(self, *a, **kw)
    if not _state["paused"] and str(self) == _target:
        _state["paused"] = True
        with open({marker_read_done!r}, "w", encoding="utf-8") as f:
            f.write("go")
        deadline = time.time() + 15
        while not os.path.exists({marker_release!r}):
            if time.time() > deadline:
                raise RuntimeError("timeout esperando marker_release")
            time.sleep(0.001)
    return result

pathlib.Path.read_text = _patched_read_text

indexes.remove({removed_id!r}, {decisions_file!r}, {root!r})
"""

_INSERT_DURING_THE_GAP_SCRIPT = """
import importlib.util, os, sys
sys.path.insert(0, {lib_memory_dir!r})

def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join({lib_memory_dir!r}, name + ".py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

indexes = _load("indexes")
model = _load("model")

line = model.IndexLine(
    id={inserted_id!r}, zone1="product", zone2="auth",
    headline="new note inserted during the race",
)
indexes.insert(line, {decisions_file!r}, {root!r})
"""


def test_regression_insert_survives_a_concurrent_remove_racing_its_read_write_gap(
    indexes, model, index_names, tmp_path
):
    """REGRESION (arreglado 2026-08-02, Moriarty rompio la capa 1): dos
    procesos reales, uno insertando una nota y otro retirando otra
    distinta del MISMO indice, perdian la nota recien insertada sin un
    solo error -- 25 de 40 intentos contra el codigo viejo, con los dos
    procesos terminando con exito. Ver el docstring del bloque de arriba
    para el detalle completo del mecanismo y de como se confirmo en
    ambas direcciones antes de escribir este test.
    """
    root = tmp_path / "project-memory"
    decisions_file = "DECISIONS.md"
    assert decisions_file in index_names

    indexes.seed(root)
    baseline = model.IndexLine(
        id="D-005", zone1="product", zone2="billing",
        headline="baseline note, to be removed",
    )
    indexes.insert(baseline, decisions_file, root)

    marker_read_done = tmp_path / "remove_read_done.marker"
    marker_release = tmp_path / "release.marker"

    remove_script = _REMOVE_WITH_FORCED_READ_WRITE_GAP_SCRIPT.format(
        lib_memory_dir=LIB_MEMORY_DIR,
        root=str(root),
        decisions_file=decisions_file,
        removed_id="D-005",
        marker_read_done=str(marker_read_done),
        marker_release=str(marker_release),
    )
    insert_script = _INSERT_DURING_THE_GAP_SCRIPT.format(
        lib_memory_dir=LIB_MEMORY_DIR,
        root=str(root),
        decisions_file=decisions_file,
        inserted_id="D-099",
    )

    proc_remove = subprocess.Popen([sys.executable, "-c", remove_script])
    try:
        deadline = time.time() + 10
        while not marker_read_done.exists():
            if time.time() > deadline:
                raise AssertionError(
                    "remove() nunca escribio el marcador de lectura -- este "
                    "test no llego a montar la carrera que dice probar"
                )
            if proc_remove.poll() is not None:
                raise AssertionError(
                    "remove() termino antes de pausarse tras su lectura, "
                    f"rc={proc_remove.returncode} -- no hubo ventana que forzar"
                )
            time.sleep(0.001)

        proc_insert = subprocess.Popen([sys.executable, "-c", insert_script])
        try:
            # Respiro real para que insert() (sin parchear, tal cual el
            # codigo de produccion) corra durante la ventana -- contra el
            # codigo actual esto lo pasa bloqueado en file_lock(), contra
            # el modelo historico roto esto le basta para terminar entero.
            time.sleep(0.3)

            marker_release.write_text("go", encoding="utf-8")

            rc_remove = proc_remove.wait(timeout=15)
            rc_insert = proc_insert.wait(timeout=15)
        finally:
            if proc_insert.poll() is None:
                proc_insert.kill()
                proc_insert.wait(timeout=10)
    finally:
        if proc_remove.poll() is None:
            proc_remove.kill()
            proc_remove.wait(timeout=10)

    assert rc_remove == 0, f"remove() termino con error bajo la carrera: rc={rc_remove}"
    assert rc_insert == 0, f"insert() termino con error bajo la carrera: rc={rc_insert}"

    result = indexes.read(decisions_file, root)
    ids = tuple(line.id for line in result)

    assert "D-099" in ids, (
        "la nota recien insertada desaparecio bajo la carrera con un "
        f"remove() concurrente -- indice final: {ids!r}"
    )
    assert "D-005" not in ids, (
        f"la nota retirada seguia presente tras remove() -- indice final: {ids!r}"
    )
    assert ids.count("D-099") == 1, f"D-099 aparece duplicado: {ids!r}"


# ---------------------------------------------------------------------------
# Regresion, confirmada por Moriarty (PoC en el scratchpad de su sesion,
# `moriarty_indexes/poc_wrong_target.py`, ejecutado antes de escribir este
# test): `insert(line, name, root)` acepta CUALQUIER nombre de fichero y
# escribe en el -- no comprueba `name` contra `vocabulary.INDEX_FILES` antes
# de tocar el disco. `zones.json` vive en el MISMO directorio `root` que los
# ocho indices reales (el propio texto de rechazo de validator.py lo situa
# ahi: ".claude/project-memory/zones.json"). Un caller que pase el nombre
# equivocado por error (typo, constante mal referenciada, un bucle que itera
# `root.iterdir()` en vez de `vocabulary.INDEX_FILES`) le pega una linea de
# indice detras del JSON: el fichero deja de parsear (`json.load` revienta
# con "Extra data"), e `insert()` NO LANZA NADA -- corrupcion silenciosa con
# el resto de la suite en verde.
#
# El contrato de Sec.7.3 ya lo pedia y nadie lo comprobaba hasta ahora: "Leer
# y escribir los ocho ficheros [...] Nadie mas los toca" -- la frase esta en
# el docstring del modulo (Sec.7.3, primera linea) y en el "Para que" de
# PIEZAS.md, no es una lectura libre de este test.
#
# Dos exigencias, no una -- lanzar DESPUES de haber escrito sigue siendo
# corrupcion: (1) `insert()` debe fallar en alto cuando `name` no esta en
# `vocabulary.INDEX_FILES`, (2) el fichero ajeno debe quedar byte a byte
# igual que antes de la llamada, sin escritura parcial.
# ---------------------------------------------------------------------------


def test_insert_into_target_outside_index_files_fails_loud_and_leaves_file_untouched(
    indexes, model, index_names, tmp_path
):
    """Regresion (Moriarty): `insert()` no valida `name` contra la lista
    cerrada de `vocabulary.INDEX_FILES` antes de escribir -- acepta un
    fichero ajeno del mismo directorio (`zones.json`) y le apenda una linea
    de indice, corrompiendolo en silencio. Ver el bloque de arriba para el
    detalle completo y la referencia al PoC que lo confirmo en vivo.
    """
    root = tmp_path / "project-memory"
    indexes.seed(root)

    foreign_name = "zones.json"
    assert foreign_name not in index_names, (
        "este test exige un nombre que NO sea uno de los ocho indices -- "
        "si vocabulary.INDEX_FILES llega a incluir 'zones.json' algun dia, "
        "el test deja de probar lo que dice probar"
    )

    # Formato real de zones.py (mismo shape que su propio docstring declara:
    # {name: {"description":..., "aliases":[...]}}), no un JSON inventado
    # sin relacion con lo que produccion escribe de verdad ahi.
    foreign_path = root / foreign_name
    original_content = json.dumps(
        {
            "auth": {
                "description": "authentication and sessions",
                "aliases": ["login", "oauth"],
            },
            "billing": {
                "description": "billing and invoicing",
                "aliases": ["stripe"],
            },
        },
        indent=2,
        ensure_ascii=False,
    )
    foreign_path.write_text(original_content, encoding="utf-8")

    line = model.IndexLine(
        id="D-999",
        zone1="product",
        zone2="auth",
        headline="caller bug: wrong index name reused zones.json by mistake",
    )

    with pytest.raises(Exception):
        indexes.insert(line, foreign_name, root)

    after_content = foreign_path.read_text(encoding="utf-8")
    assert after_content == original_content, (
        "insert() en un destino fuera de INDEX_FILES no debe escribir nada "
        "en el, ni siquiera parcialmente -- el fichero ajeno cambio de "
        f"{original_content!r} a {after_content!r}"
    )

    # No solo "sigue siendo JSON valido" (una escritura que dejara el JSON
    # tecnicamente parseable pero con datos añadidos pasaria esta aseveracion
    # mas floja sin ser correcta) -- byte a byte igual, ya cubierto arriba;
    # esta segunda comprobacion es una lectura semantica adicional del mismo
    # hecho, para que el fallo sea legible sin tener que diffear reprs a
    # mano si algun dia el assert de arriba revienta.
    assert json.loads(after_content) == json.loads(original_content)
