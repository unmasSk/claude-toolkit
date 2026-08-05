"""Contrato de lib/memory/query.py -- PIEZAS.md Sec.8.2.

query.py NO EXISTE TODAVIA. Estos cuatro tests deben fallar al importar,
por diseno -- es el RED del modo test-first. Uno por fila de la tabla
"Sus tests" de Sec.8.2, ni uno mas:

  1. Sembrar tres notas y recuperarlas por identificador, por zona, por
     palabra y por fichero.
  2. Un identificador inexistente devuelve None, no una excepcion.
  3. Una lectura de git que falla de forma transitoria se reintenta
     antes de rendirse.
  4. `by_word` devuelve las lineas que casaron, no solo las notas.

query.py es "el unico lector del historial" (Sec.8.2, "Para que"): en el
v1 esto estaba implementado TRES veces, 562 lineas en tres ficheros
sincronizadas a mano, y ya habia fallado tres veces con el mismo patron
[medido -- TESTIGO Sec.3, citado en PIEZAS.md]. Aqui hay uno.

El fixture `query` se pide PRIMERO en cada firma (mismo patron que
test_zones.py/test_format.py/test_similar.py): pytest instancia los
fixtures en el orden en que aparecen, asi que si `query.py` no existe el
fallo se reporta ahi -- nunca por `model.py`/`format.py`/`gitcmd.py`,
que ya existen y estan en verde.

**Sembrado real, no `notes.py`.** `lib/memory/notes.py` (la transaccion
validar->indice->commit, Sec.8.1) NO existe todavia y no es esta pieza
-- un companero en paralelo escribe su propio contrato. Sembrar aqui con
`notes.py` inventariaria esa logica antes de que exista, lo que la
restriccion D del plan prohibe. En su lugar, cada test siembra
commiteando de verdad contra el repo temporal (`tmp_repo`, ver
conftest.py) usando SOLO piezas ya reales y en verde: `format.build_message`
para el texto del commit y `gitcmd.commit` para escribirlo. Es memoria
real, escrita con las mismas piezas que usara la produccion, aunque el
orquestador de la transaccion (`notes.py`) todavia no exista.

**Supuestos declarados, sin fuente literal en Sec.8.2 (mismo tipo de
hueco que en format-contract-notes.md/similar-contract-notes.md):**

1. **Las cuatro funciones de la superficie no declaran parametro de
   `root`/`cwd`** (`by_id(note_id: str) -> Note | None`, etc.) -- se
   asume que, igual que `gitcmd.commit()` ("hereda el cwd ambiental del
   proceso, igual que ... quien la llama ya esta corriendo dentro del
   repo"), leen contra el cwd del proceso. Por eso cada test hace
   `monkeypatch.chdir(tmp_repo)` antes de llamar a `query.*` -- nunca se
   inventa un parametro que la superficie declarada no tiene.
2. **El mecanismo de lectura para la fila 3 (reintento transitorio) se
   simula en el limite real de subprocess (`subprocess.run`)**, no
   dentro de `gitcmd.run()` (que Sec.7.1 declara SIN reintento propio --
   "no lanza nunca por un fallo DE GIT... un returncode != 0 es un
   resultado normal"). El reintento es responsabilidad de `query.py`, no
   de `gitcmd.py` -- asi que la unica forma de probarlo sin adivinar la
   implementacion interna es fingir el fallo en el proceso `git` real
   que cualquier camino interno acabaria invocando.
3. **La falla simulada apunta a la PRIMERA invocacion de `git log`**
   (nunca a `git rev-parse`/otras llamadas de preparacion que
   `query.py` pudiera hacer antes), porque Sec.8.2 dice literalmente que
   la lectura por fichero "la da `git log -- <ruta>` directamente" --
   el subcomando comun mas probable para las cuatro funciones de esta
   pieza. Si la implementacion real usa otro subcomando, este supuesto
   es una linea a corregir, no un rediseno del test.
4. **`Note.timestamp` se excluye de toda comparacion**, mismo criterio
   que `test_format.py` (ver su docstring, hueco 2): su fuente de verdad
   es la fecha de autor de git, no un valor que este test pueda fijar de
   antemano y esperar de vuelta byte a byte.

**Por que `_assert_fields_match` compara campo a campo y nunca `==`
directo:** el `model` que este fichero carga via `import_lib_memory_module`
y el `model` que `query.py` importa por dentro (`from model import Note`,
convencion plana de PIEZAS Sec.3.3bis) pueden acabar siendo clases Python
DISTINTAS aunque el codigo fuente sea identico -- mismo hallazgo que
zones-contract-notes.md/format-contract-notes.md, mismo remedio.

No se toca produccion: si `lib/memory/query.py` no existe, estos tests se
quedan en rojo tal cual estan -- eso es lo esperado. No se toca ningun
fichero de un companero (`conftest.py`, `test_notes.py`, etc.).
"""

import ast
import dataclasses
import os
import subprocess
from pathlib import Path

import pytest

from .conftest import import_lib_memory_module, LIB_MEMORY_DIR


@pytest.fixture
def query():
    return import_lib_memory_module("query")


@pytest.fixture
def model():
    return import_lib_memory_module("model")


@pytest.fixture
def fmt():
    return import_lib_memory_module("format")


@pytest.fixture
def gitcmd():
    return import_lib_memory_module("gitcmd")


def _note(model, **overrides):
    """Factoria de Note con valores por defecto neutros -- cada test
    override solo los campos que le importan. Mismo patron que
    test_format.py::_note.
    """
    fields = dict(
        type="M",
        id="M-900",
        zone1="testing",
        zone2="query",
        headline="seeded note for query.py contract",
        description="placeholder description for the query.py round trip.",
        timestamp=None,
        why=None,
        keys=(),
        origin=(),
        replaces=None,
        awaits=None,
        issue=None,
    )
    fields.update(overrides)
    if fields["timestamp"] is None:
        from datetime import datetime, timezone

        fields["timestamp"] = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    return model.Note(**fields)


def _commit_note(repo_path, fmt, gitcmd, note, touched_rel_path):
    """Siembra `note` como un commit REAL en `repo_path`: escribe un
    fichero tocado (para que `by_file` tenga algo que filtrar) y
    commitea con el texto real de `fmt.build_message`, via `gitcmd.commit`
    (que exige `paths` explicitos -- Sec.7.1).

    Devuelve la ruta relativa tocada, lista para pasarsela a
    `query.by_file`.

    Requiere que el cwd del PROCESO ya sea `repo_path` (ver supuesto 1
    del docstring del modulo) -- `gitcmd.commit()` no acepta `cwd` como
    parametro, hereda `Path.cwd()`.
    """
    file_path = Path(repo_path) / touched_rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(fmt.build_index_line(note), encoding="utf-8")

    add_result = subprocess.run(
        ["git", "add", "--", str(file_path)],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    assert add_result.returncode == 0, (
        f"git add fallo sembrando {note.id}: {add_result.stderr}"
    )

    message = fmt.build_message(note)
    commit_result = gitcmd.commit(message, paths=[file_path], allow_empty=False)
    assert commit_result.returncode == 0, (
        f"commit fallo sembrando {note.id}: {commit_result.stderr}"
    )
    return Path(touched_rel_path)


def _assert_fields_match(parsed, expected, exclude=()):
    """Compara campo a campo, nunca con `==` directo sobre el objeto --
    ver el docstring del modulo, seccion sobre identidad de clase entre
    cargas por ruta de fichero distintas.
    """
    assert parsed is not None
    for field in dataclasses.fields(expected):
        if field.name in exclude:
            continue
        parsed_value = getattr(parsed, field.name)
        expected_value = getattr(expected, field.name)
        assert parsed_value == expected_value, (
            f"campo {field.name!r} no volvio identico via query: "
            f"{parsed_value!r} != {expected_value!r}"
        )


def test_seed_three_notes_recovered_by_id_zone_word_and_file(
    query, model, fmt, gitcmd, tmp_repo, monkeypatch
):
    """Fila 1: sembrar tres notas y recuperarlas por identificador, por
    zona, por palabra y por fichero.

    Fallo real que previene: que se escriba bien y no se pueda leer --
    que es tener una memoria que no sirve.
    """
    monkeypatch.chdir(tmp_repo)

    note_a = _note(
        model,
        id="M-101",
        zone1="testing",
        zone2="query-alpha",
        headline="round trip note alpha for the query contract",
        description="alpha note used to prove query.py can read back what it wrote.",
        why="zzqueryalphaneedle appears only in this note's why field",
    )
    note_b = _note(
        model,
        id="M-102",
        zone1="testing",
        zone2="query-beta",
        headline="round trip note beta for the query contract",
        description="beta note, same zone1 as alpha but a different zone2, no needle word here.",
    )
    note_c = _note(
        model,
        id="M-103",
        zone1="another",
        zone2="place",
        headline="round trip note charlie for the query contract",
        description="charlie note, a different zone1 entirely, no needle word here either.",
    )

    path_a = _commit_note(tmp_repo, fmt, gitcmd, note_a, "markers/note_a.txt")
    _commit_note(tmp_repo, fmt, gitcmd, note_b, "markers/note_b.txt")
    _commit_note(tmp_repo, fmt, gitcmd, note_c, "markers/note_c.txt")

    # por identificador
    by_id_result = query.by_id(note_a.id)
    _assert_fields_match(by_id_result, note_a, exclude={"timestamp"})

    # por zona
    by_zone_result = query.by_zone(note_a.zone1, note_a.zone2)
    assert {n.id for n in by_zone_result} == {note_a.id}, (
        f"by_zone({note_a.zone1!r}, {note_a.zone2!r}) devolvio "
        f"{[n.id for n in by_zone_result]!r}, se esperaba solo {note_a.id!r}"
    )

    # por palabra
    by_word_result = query.by_word("zzqueryalphaneedle")
    matched_ids = {n.id for n, _lines in by_word_result}
    assert note_a.id in matched_ids, (
        "la palabra sembrada solo en note_a no aparece entre los resultados de by_word"
    )
    assert note_b.id not in matched_ids and note_c.id not in matched_ids, (
        f"by_word devolvio notas que no contienen la palabra buscada: {matched_ids!r}"
    )

    # por fichero
    by_file_result = query.by_file(path_a)
    assert {n.id for n in by_file_result} == {note_a.id}, (
        f"by_file({path_a!r}) devolvio {[n.id for n in by_file_result]!r}, "
        f"se esperaba solo {note_a.id!r}"
    )


def test_by_id_unknown_identifier_returns_none_not_exception(
    query, model, fmt, gitcmd, tmp_repo, monkeypatch
):
    """Fila 2: un identificador inexistente devuelve None, no una
    excepcion ni una cadena vacia.

    Fallo real que previene: un fallo que se confunde con "no hay nada"
    y pasa callado.
    """
    monkeypatch.chdir(tmp_repo)

    seeded = _note(
        model,
        id="M-201",
        zone1="testing",
        zone2="unknown-id",
        headline="seeded note present while an unrelated id is queried",
        description="present so the repo has at least one real note commit to search through.",
    )
    _commit_note(tmp_repo, fmt, gitcmd, seeded, "markers/note_m201.txt")

    result = query.by_id("Z-999999")

    assert result is None, (
        f"un identificador inexistente debe devolver None, devolvio {result!r}"
    )


def test_by_id_retries_after_transient_git_failure_before_giving_up(
    query, model, fmt, gitcmd, tmp_repo, monkeypatch
):
    """Fila 3: una lectura de git que falla de forma transitoria se
    reintenta antes de rendirse.

    Fallo real que previene: un `git` que falla una vez por carga se lee
    como "este proyecto no tiene memoria", y la sesion arranca en blanco.

    Se finge el fallo transitorio en el limite real (`subprocess.run`,
    ver supuestos 2 y 3 del docstring del modulo): la primera invocacion
    de `git log` devuelve un fallo real de git (`returncode=128`, con el
    mensaje que un `index.lock` en curso produciria de verdad); cualquier
    invocacion posterior -- incluida la de reintento -- se deja pasar al
    `subprocess.run` real. Se comprueba tanto que hubo una segunda
    invocacion de `git log` (la prueba del reintento) como que el
    resultado final es la nota real, no un `None` fruto de rendirse
    demasiado pronto.
    """
    monkeypatch.chdir(tmp_repo)

    note = _note(
        model,
        id="M-401",
        zone1="testing",
        zone2="retry",
        headline="note used to prove a transient git read failure gets retried",
        description="present so by_id has something real to recover after the retry.",
    )
    _commit_note(tmp_repo, fmt, gitcmd, note, "markers/note_m401.txt")

    real_run = subprocess.run
    state = {"log_calls": 0}

    def flaky_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if "log" in cmd and state["log_calls"] == 0:
            state["log_calls"] += 1
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=128,
                stdout="",
                stderr=(
                    "fatal: Unable to create '.git/index.lock': File exists. "
                    "(simulated transient failure)"
                ),
            )
        if "log" in cmd:
            state["log_calls"] += 1
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", flaky_run)

    result = query.by_id(note.id)

    assert state["log_calls"] >= 2, (
        "query.by_id no reintento: 'git log' se invoco una sola vez tras el "
        "fallo transitorio simulado, en vez de reintentarse antes de rendirse "
        f"(invocaciones de 'git log' observadas: {state['log_calls']})"
    )
    _assert_fields_match(result, note, exclude={"timestamp"})


def test_by_word_returns_the_matched_lines_not_only_the_notes(
    query, model, fmt, gitcmd, tmp_repo, monkeypatch
):
    """Fila 4: `by_word` devuelve las lineas que casaron, no solo las
    notas.

    Fallo real que previene: el informe no puede marcar cual fue la
    linea que caso, y hay que ir a buscarla por otra puerta.
    """
    monkeypatch.chdir(tmp_repo)

    matching_note = _note(
        model,
        id="M-301",
        zone1="testing",
        zone2="word-match",
        headline="note that mentions the search needle in its why field",
        description="description without the needle word.",
        why="the ledger zzwordneedle job double-counted refunds last week",
    )
    other_note = _note(
        model,
        id="M-302",
        zone1="testing",
        zone2="word-nomatch",
        headline="note without the needle anywhere in its text",
        description="this description does not contain the search term at all.",
    )
    _commit_note(tmp_repo, fmt, gitcmd, matching_note, "markers/note_m301.txt")
    _commit_note(tmp_repo, fmt, gitcmd, other_note, "markers/note_m302.txt")

    result = query.by_word("zzwordneedle")

    matched = {n.id: lines for n, lines in result}
    assert matching_note.id in matched, (
        "by_word no encontro la nota que realmente contiene la palabra buscada"
    )
    assert other_note.id not in matched, (
        "by_word devolvio una nota que no contiene la palabra buscada"
    )

    matched_lines = matched[matching_note.id]
    assert matched_lines, (
        "by_word encontro la nota pero no devolvio ninguna linea que caso -- "
        "el informe no podria marcar cual fue"
    )
    assert any("zzwordneedle" in line for line in matched_lines), (
        f"ninguna de las lineas devueltas contiene la palabra buscada: {matched_lines!r}"
    )


# ---------------------------------------------------------------------------
# Endurecimiento (2026-08-02) -- estructural, no una fila de la tabla. El
# sistema volvio a tener TRES lectores del historial de git
# (`_rule_commit_texts()`/`_issue_commit_dates()` en health.py,
# `context.latest()`): el mismo patron de tres implementaciones
# sincronizadas a mano que este modulo existe para impedir (Sec.8.2, "Por
# que es uno solo"), medido en el sistema anterior como 562 lineas en tres
# ficheros que ya habian fallado tres veces [TESTIGO Sec.3]. Se demostro en
# vivo: arreglar "rama sin commits" en un sitio y el arranque seguia
# reventando tres veces mas, porque los otros dos lectores lo tenian por su
# cuenta. Ya esta consolidado -- los tres pasan ahora por
# `query.run_git_log()` (ver su docstring, "se hizo publica el
# 2026-08-02") -- este test es la red que impide que vuelva a partirse.
# ---------------------------------------------------------------------------


def _git_history_call_sites(py_path):
    """Sitios REALES (nodos del arbol de sintaxis, nunca texto) que
    invocan un lector de historial de git -- `algo.run(...)`/
    `subprocess.run(...)`/`subprocess.Popen(...)`/
    `subprocess.check_output(...)`/`subprocess.check_call(...)` cuyo
    PRIMER argumento es una lista/tupla LITERAL que contiene "log",
    "show" o "rev-list" como elemento -- en `py_path`.

    Deliberadamente AST, nunca `grep`/texto crudo: varios ficheros de
    este contrato CITAN la forma vieja en prosa, dentro de su propio
    docstring, para explicar el arreglo (p.ej. health.py: "antes tenia su
    propia gitcmd.run(["log", ...]) a mano"; confirmado con
    `grep -c 'gitcmd.run(\\["log"' lib/memory/health.py` -> 1, dentro del
    docstring, cero llamadas reales). Un `grep` a lo bruto cazaria esa
    prosa como si fuera codigo real y daria un rojo falso -- el arbol de
    sintaxis nunca ve un comentario ni el contenido de un docstring como
    una llamada, asi que esta funcion no puede caer en esa trampa.

    Tambien queda a salvo por construccion la invocacion generica que
    `gitcmd.py` SI hace de verdad (`subprocess.run(["git"] + args, ...)`)
    -- su primer argumento es un `BinOp` (concatenacion de listas, `args`
    es una variable), nunca una lista LITERAL, asi que no es un nodo
    `ast.List`/`ast.Tuple` y esta funcion lo ignora sin necesidad de
    ninguna excepcion especial para `gitcmd.py`.
    """
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    sites = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        else:
            continue
        if name not in ("run", "Popen", "check_output", "check_call"):
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if not isinstance(first_arg, (ast.List, ast.Tuple)):
            continue
        literals = {
            elt.value
            for elt in first_arg.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        }
        if literals & {"log", "show", "rev-list"}:
            sites.append(node.lineno)
    return sites


def test_no_second_reader_of_git_history_outside_query_py():
    """Estructural: solo `query.py` puede pedir el historial de git
    (`log`/`show`/`rev-list`) -- Sec.8.2, "es el unico lector del
    historial". Ningun otro modulo de `lib/memory/` puede invocarlo por
    su cuenta -- si aparece uno, es exactamente el fallo ya medido tres
    veces en el sistema anterior (562 lineas en tres ficheros
    sincronizadas a mano, TESTIGO Sec.3) volviendo a nacer.

    Verificado en vivo antes de confiar en este detector (nunca supuesto
    por lectura de codigo): contra el `lib/memory/` real, sin tocarlo,
    esta funcion no encuentra ninguna violacion. Sobre una COPIA
    descartable de `health.py` (nunca el fichero real -- regla del
    encargo, "no toques produccion") con una llamada real
    `gitcmd.run(["log", "--pretty=format:%B"], ...)` reintroducida a
    mano, el mismo detector SI la encuentra -- confirma que no es un
    chequeo de adorno.
    """
    violations = {}
    for name in sorted(os.listdir(LIB_MEMORY_DIR)):
        if not name.endswith(".py") or name == "query.py":
            continue
        path = Path(LIB_MEMORY_DIR) / name
        sites = _git_history_call_sites(path)
        if sites:
            violations[name] = sites

    assert not violations, (
        "modulo(s) de lib/memory/, ademas de query.py, invocando un lector "
        "de historial de git (log/show/rev-list) por su cuenta -- Sec.8.2 "
        f"dice 'es el UNICO lector del historial': {violations!r}"
    )
