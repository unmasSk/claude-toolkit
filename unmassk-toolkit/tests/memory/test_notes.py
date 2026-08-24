"""Contrato de lib/memory/notes.py -- PIEZAS.md Sec.8.1.

notes.py NO EXISTE TODAVIA. Estos seis tests deben fallar al importar,
por diseno -- es el ROJO del modo test-first. Uno por fila de la tabla
"Sus tests" de Sec.8.1, ni uno mas:

  1. `git show --stat` del commit contiene la nota y la linea de indice.
  2. Si el commit falla, el indice queda exactamente como estaba.
  3. Si el commit falla, el error que sale es el de git, entero.
  4. Una decision con dos alternativas produce tres commits y tres
     indices que cuadran.
  5. Un commit de trabajo con tres rutas no arrastra el resto del arbol.
  6. Dos escrituras a la vez se serializan.

El fixture `notes` importa por ruta de fichero (`import_lib_memory_module`,
ver conftest.py) para que cada test falle individualmente con la causa
real (`FileNotFoundError`: lib/memory/notes.py no existe todavia), en vez
de un unico error de coleccion para todo el fichero -- mismo patron que
test_gitcmd.py y test_validator.py. En cada test, `notes` se pide ANTES
que `model`/`config`/`indexes`/etc. en la firma, para que sea ESE fallo
(notes.py, la pieza de este contrato) el que se reporte primero, no el de
sus dependencias (todas ya en produccion).

POR QUE ESTOS SEIS SON "los mas serios de todo el proyecto" (el encargo
que acompana esta tarea, y Sec.8 del propio documento): esta es LA PIEZA
DONDE EL SISTEMA SE PUEDE CORROMPER A SI MISMO. La regla que protegen:
la nota y su linea de indice viajan en el mismo commit, o no viaja
ninguna de las dos. Si la nota se commitea y el indice no, hay una nota
que ninguna busqueda encuentra jamas -- memoria escrita e invisible. Si
el indice se actualiza y el commit falla, hay una linea que apunta a una
nota que no existe. Las dos son corrupcion silenciosa: nada revienta, y
se descubre semanas despues.

CONTRA GIT DE VERDAD, no simulado: los seis tests usan el repositorio git
temporal real del fixture `tmp_repo` de conftest.py, sin mockear
subprocess ni el modulo `git`. Los modulos de los que `notes.py` depende
(`model`, `config`, `validator`, `indexes`, `format`, `ids`, `vocabulary`,
`gitcmd`) YA ESTAN EN PRODUCCION (trabajo previo, esta misma rama) -- se
usan reales, sin mock alguno.

COMO SE PROVOCA UN FALLO REAL DE GIT PARA LAS FILAS 2 Y 3 (el encargo
pide "de la forma mas real que puedas" y que quede documentado como se
monto): se crea `.git/index.lock` A MANO, con contenido vacio, ANTES de
llamar a `notes.write()`. Ese es el fichero que el propio `git` intenta
crear (con `O_CREAT|O_EXCL`) para tomar el candado de su indice en
CUALQUIER operacion que lo modifique (`add`, `commit`, ...); si ya
existe, git se niega con un `fatal: Unable to create '<repo>/.git/
index.lock': File exists.` real, no fabricado -- no hace falta romper
permisos de fichero ni tocar la identidad git de la maquina. Se limpia
siempre en un `finally` para no dejar el repositorio temporal bloqueado.
La fila 3 ademas usa una SONDA: un `git commit` de verdad emitido por el
propio test contra el mismo repo, con el mismo candado puesto, justo
despues de que `notes.write()` intente el suyo -- así el texto contra el
que se compara `result.git_error` sale del git real de esta maquina en
esta misma ejecucion, nunca de una cadena tecleada a mano (unmassk-
standards Sec.34: nunca fabricar el resultado esperado de un round trip).

QUE NO SE PRUEBA AQUI, y es a proposito: `replace()` y `close()` -- la
tabla "Sus tests" de Sec.8.1 no las menciona, y el encargo es explicito
("esas seis, ni una mas"). Tampoco se reconstruye aqui que letra de tipo
va a que fichero de indice (D->DECISIONS.md, etc.) -- ese mapeo no esta
fijado por ningun texto que este contrato cite, asi que los tests lo
DESCUBREN leyendo los ocho ficheros reales tras cada escritura
(`_index_line_for`) en vez de asumirlo.

No se toca produccion: si `lib/memory/notes.py` no existe, estos tests
se quedan en rojo tal cual estan -- eso es lo esperado.
"""

import base64
import contextlib
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from .conftest import LIB_MEMORY_DIR, import_lib_memory_module, run_git

_BASE_NOTE_FIELDS = dict(
    type="M",
    # Placeholder deliberado: el orden de write() (Sec.8.1, "El orden de
    # write es el contrato") es "candado -> identificador -> validar ->
    # ...", es decir, el identificador REAL lo asigna write() por dentro,
    # nunca quien llama. Ninguna regla de validate_note() lee note.id (ver
    # validator.py), asi que este valor nunca se comprueba -- los tests
    # derivan siempre el id real de `WriteResult.note_id`, nunca de este
    # campo.
    id="",
    zone1="product",
    zone2="notes-test",
    headline="MARK_BASE_HEADLINE ordinary memo for lib/memory/notes.py tests",
    description="MARK_BASE_DESCRIPTION not empty, not special",
    timestamp=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
)


@pytest.fixture
def notes():
    return import_lib_memory_module("notes")


@pytest.fixture
def notes_commit():
    """El modulo donde vive `write_work()` de verdad -- `notes.write_work`
    es EL MISMO objeto funcion (import PLANO, ver docstring de
    notes_commit.py: "notes.py importa los siete nombres de aqui de forma
    PLANA"), asi que sus nombres globales (`_committed_blob_hash`,
    `_git_blob_hash_of_bytes`, `gitcmd`, ...) se resuelven en el
    `__dict__` de ESTE modulo, no en el de `notes`. `import_lib_memory_module`
    registra bajo el nombre plano en `sys.modules` (ver su propio
    docstring, "REGISTRO BAJO EL NOMBRE PLANO") y adopta la instancia que
    `notes.py` ya cargo por su cuenta si llega primero -- pedir `notes_commit`
    aqui, en vez de `notes`, siempre da el objeto que `write_work()` ve de
    verdad en tiempo de ejecucion, monkeypatchear un atributo aqui SI
    afecta a lo que la funcion ejecuta.
    """
    return import_lib_memory_module("notes_commit")


@pytest.fixture
def gitcmd_mod():
    """El modulo `gitcmd`, la MISMA instancia que `notes_commit.gitcmd`
    referencia por dentro (import PLANO entre hermanos de `lib/memory/`,
    mismo mecanismo de `sys.modules` compartido que explica el fixture
    `notes_commit` de arriba). Parchear `gitcmd_mod.run` aqui es lo que
    permite interceptar UNA llamada concreta (por sus argumentos exactos)
    dentro de `write_work()` sin tocar `lib/memory/gitcmd.py` -- tecnica
    de Cerberus, reproducida en `prove_hole4.py`.
    """
    return import_lib_memory_module("gitcmd")


@pytest.fixture
def query():
    return import_lib_memory_module("query")


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
def format_mod():
    return import_lib_memory_module("format")


@pytest.fixture
def vocabulary():
    return import_lib_memory_module("vocabulary")


@pytest.fixture
def make_note(model):
    def _make(**overrides):
        fields = dict(_BASE_NOTE_FIELDS)
        fields.update(overrides)
        return model.Note(**fields)

    return _make


@pytest.fixture
def make_context(model, config, validator):
    """Un `Context` real, con las zonas de la nota ya dadas de alta.

    `validate_zones` (validator.py) resuelve `zone1` y `zone2` cada una
    por separado contra `ctx.zones` -- las dos deben estar como clave,
    no como un par. `existing_in_zone=()` por defecto: como
    `validate_replacement` solo compara contra ESTA tupla estatica
    (nunca relee el indice), ninguna de las notas que un test escribe
    despues puede disparar un rechazo de parecido entre si -- lo que
    hace seguro reutilizar titulares parecidos entre notas de un mismo
    test sin acoplarse al umbral de similar.py (fuera del alcance de
    este contrato).
    """

    def _make(
        zone_names=("product", "notes-test"),
        existing_in_zone=(),
        known_ids=frozenset(),
        cfg=None,
    ):
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
    """Cambia el cwd del proceso a `path` durante el bloque, y lo restaura
    siempre. `gitcmd.commit()` (Sec.7.1) no declara su propio `cwd` --
    hereda el ambiental, y la Superficie de `notes.py` (Sec.8.1) tampoco
    declara un parametro de raiz para ninguna de sus cinco funciones. Sea
    cual sea la forma en que `notes.py` derive la raiz del repositorio
    (`Path.cwd()` directo, o `gitcmd.repo_root(Path.cwd())`), colocarse
    DENTRO de `tmp_repo` antes de llamar cubre las dos posibilidades: la
    raiz real del repositorio temporal Y el cwd del proceso coinciden.
    """
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _empty_repo(tmp_path, name="empty_repo_no_parent"):
    """Repo git real con CERO commits -- distinto de `tmp_repo`
    (conftest.py), que ya trae un commit `init` de fabrica. Hace falta
    para reproducir, sin depender de nada probabilistico, el caso en que
    `git reset --mixed HEAD~1` FALLA de verdad: un commit que es el
    PRIMERO del repositorio no tiene padre, y `HEAD~1` no resuelve --
    mismo patron que `_zero_commit_repo` en test_context.py, reescrito
    aqui sin importar de un fichero companero.
    """
    repo = tmp_path / name
    repo.mkdir()
    rc, _out, err = run_git(["init"], str(repo))
    assert rc == 0, f"git init fallo montando el repo sin commits: {err}"
    return repo


@contextlib.contextmanager
def _forced_git_index_lock(root):
    """Fuerza un fallo REAL de `git commit` sin tocar permisos ni
    identidad: crea `.git/index.lock` de antemano. Ver el docstring del
    modulo ("COMO SE PROVOCA...") para el porque y el detalle completo.
    Se limpia siempre, incluso si el bloque revienta.
    """
    lock_path = Path(root) / ".git" / "index.lock"
    lock_path.write_text("", encoding="utf-8")
    try:
        yield lock_path
    finally:
        lock_path.unlink(missing_ok=True)


@contextlib.contextmanager
def _forced_pre_commit_hook_rejects(root):
    """Planta un hook `pre-commit` REAL que siempre rechaza (`exit 1`) --
    a diferencia de `_forced_git_index_lock` (que bloquea el `git add`
    tambien, antes de que nada quede staged), este hook deja que
    `git add` corra con normalidad y solo hace fallar el `git commit`
    que le sigue -- el escenario donde `stage_and_commit()` ya dejo el
    indice con el contenido NUEVO staged antes de que el commit reviente
    (mismo mecanismo que `test_rule_commit_contract.py::
    _forced_pre_commit_hook_rejects`, copiado aqui porque cada fichero
    de contrato monta su propio repo semilla). Limpia el hook en un
    `finally` para no dejarlo huerfano entre tests.
    """
    hooks_dir = Path(root) / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-commit"
    hook_path.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook_path.chmod(0o755)
    try:
        yield
    finally:
        hook_path.unlink(missing_ok=True)


def _index_line_for(indexes_mod, vocabulary_mod, root, note_id):
    """Busca `note_id` en los siete indices VIGENTES (no ARCHIVED.md,
    que no es un indice de notas vivas). Devuelve `(nombre_fichero,
    IndexLine)`, o `(None, None)` si no aparece en ninguno.

    Deliberadamente NO asume que letra de tipo va a que fichero -- ese
    mapeo no esta fijado por ningun texto que Sec.8.1 cite, asi que se
    descubre leyendo los ocho ficheros reales tras cada escritura, en
    vez de hardcodearlo (ver docstring del modulo).
    """
    for name in vocabulary_mod.INDEX_FILES:
        if name == "ARCHIVED.md":
            continue
        for line in indexes_mod.read(name, root):
            if line.id == note_id:
                return name, line
    return None, None


def _read_all_index_contents(root, vocabulary_mod):
    """Contenido crudo (texto completo) de los siete indices vigentes,
    para comparar bytes exactos antes/despues de un intento de escritura
    que se espera que falle (fila 2)."""
    return {
        name: (Path(root) / name).read_text(encoding="utf-8")
        for name in vocabulary_mod.INDEX_FILES
        if name != "ARCHIVED.md"
    }


# ---------------------------------------------------------------------------
# Fila 1
# ---------------------------------------------------------------------------


def test_write_commit_contains_both_the_note_and_its_index_line(
    notes, model, config, indexes, format_mod, vocabulary, tmp_repo, make_note, make_context
):
    """Fila 1: `git show --stat` del commit contiene la nota y la linea
    de indice.

    Fallo real que previene: una nota que ninguna busqueda encuentra
    jamas -- memoria escrita e invisible.

    Tres comprobaciones independientes contra el repo real, ninguna
    fabricada: (a) `git show --stat HEAD` lista el fichero de indice que
    de verdad cambio (descubierto leyendo los ocho ficheros, no asumido);
    (b) el mensaje REAL del commit (`git log -1 --format=%B`) se vuelve a
    leer con `format.parse_message` y sale la misma nota; (c) el diff
    completo del commit contiene, anadida, la linea de indice exacta que
    `format.build_index_line` construye para esos mismos datos.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))
    note = make_note(
        headline="MARK_ROW1 headline that must ride in the same commit as its index line"
    )
    ctx = make_context()

    with _cwd(root):
        result = notes.write(note, ctx)

    assert result.ok, f"write() fallo inesperadamente: {result.git_error}"
    assert result.note_id, "write() no devolvio un identificador asignado"

    file_name, index_line = _index_line_for(indexes, vocabulary, notes.pm_root(root), result.note_id)
    assert file_name is not None, (
        f"{result.note_id!r} no aparece en ningun indice vigente tras un write() "
        "en verde -- memoria escrita e invisible, el fallo que esta pieza existe "
        "para prevenir"
    )
    assert index_line.zone1 == note.zone1
    assert index_line.zone2 == note.zone2
    assert index_line.headline == note.headline

    _rc_stat, stat_out, _err_stat = run_git(["show", "--stat", "HEAD"], tmp_repo)
    assert file_name in stat_out, (
        f"el commit no toco {file_name!r} segun `git show --stat` -- la nota y su "
        "linea de indice no viajaron en el mismo commit"
    )

    _rc_body, body, _err_body = run_git(["log", "-1", "--format=%B", "HEAD"], tmp_repo)
    parsed = format_mod.parse_message(body)
    assert parsed is not None, (
        f"el mensaje real del commit no se pudo volver a leer como Note: {body!r}"
    )
    assert parsed.id == result.note_id
    assert parsed.headline == note.headline
    assert parsed.description == note.description

    _rc_patch, patch_out, _err_patch = run_git(["show", "HEAD"], tmp_repo)
    expected_index_line_text = format_mod.build_index_line(
        model.IndexLine(
            id=result.note_id, zone1=note.zone1, zone2=note.zone2, headline=note.headline
        )
    )
    assert f"+{expected_index_line_text}" in patch_out, (
        "la linea de indice exacta no aparece anadida en el diff del commit -- "
        f"se esperaba encontrar {expected_index_line_text!r}"
    )


# ---------------------------------------------------------------------------
# Fila 2
# ---------------------------------------------------------------------------


def test_failed_commit_leaves_index_exactly_as_before(
    notes, model, config, indexes, vocabulary, tmp_repo, make_note, make_context
):
    """Fila 2: si el commit falla, el indice queda exactamente como
    estaba.

    Fallo real que previene: una linea de indice apuntando a una nota
    que no existe.

    El fallo de git es real, no simulado -- ver "COMO SE PROVOCA..." en
    el docstring del modulo. Se compara BYTE A BYTE el contenido de los
    siete indices vigentes antes y despues del intento: no solo el
    fichero que le tocaria a este tipo de nota (ese mapeo ni siquiera se
    asume aqui), sino los siete, para que un efecto secundario en
    cualquier otro tambien haga fallar el test.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))
    baseline = _read_all_index_contents(notes.pm_root(root), vocabulary)

    note = make_note(headline="MARK_ROW2 headline that must never reach the index")
    ctx = make_context()

    with _cwd(root), _forced_git_index_lock(root):
        result = notes.write(note, ctx)

    assert result.ok is False, (
        "se esperaba que write() fallara con .git/index.lock ya ocupado -- si no "
        "fallo, este test no probo nada real"
    )

    after = _read_all_index_contents(notes.pm_root(root), vocabulary)
    assert after == baseline, (
        "el contenido de al menos un indice cambio aunque el commit de git fallo -- "
        "una linea que apunta a una nota que no existe, la corrupcion silenciosa que "
        "esta pieza existe para prevenir"
    )


# ---------------------------------------------------------------------------
# Fila 3
# ---------------------------------------------------------------------------


def test_failed_commit_propagates_the_real_git_error(
    notes, model, config, tmp_repo, make_note, make_context
):
    """Fila 3: si el commit falla, el error que sale es el de git,
    entero.

    Fallo real que previene: un fallo sin causa, imposible de
    diagnosticar.

    El texto contra el que se compara `result.git_error` no se teclea a
    mano (unmassk-standards Sec.34: nunca fabricar el resultado esperado
    de un round trip): se obtiene de una SONDA -- un `git commit` real
    emitido por el propio test contra el MISMO repositorio con el MISMO
    candado (`.git/index.lock`) todavia puesto, justo despues del intento
    de `notes.write()`. Los dos fallan por la misma causa exacta, asi que
    la primera linea de la sonda tiene que aparecer, literal, dentro del
    error que devuelve `write()`.
    """
    root = Path(tmp_repo)
    note = make_note(headline="MARK_ROW3 headline for the real-git-error test")
    ctx = make_context()

    with _cwd(root), _forced_git_index_lock(root):
        result = notes.write(note, ctx)
        _rc_probe, _out_probe, probe_stderr = run_git(
            ["commit", "--allow-empty", "-m", "sonda: mismo candado, mismo fallo"],
            tmp_repo,
        )

    assert result.ok is False
    assert result.git_error is not None, (
        "git_error es None ante un fallo real de git -- el usuario se queda sin "
        "diagnostico"
    )
    assert result.git_error.strip() != "", (
        "git_error vacio ante un fallo real de git -- convierte un fallo con causa "
        "en un fallo sin causa"
    )
    assert probe_stderr.strip() != "", (
        "la sonda no reprodujo un fallo real de git -- este test no prueba nada"
    )
    probe_first_line = probe_stderr.strip().splitlines()[0]
    assert probe_first_line in result.git_error, (
        "el error devuelto no es el mensaje real de git para este fallo -- "
        f"se esperaba que contuviera {probe_first_line!r}, resultado real: "
        f"{result.git_error!r}"
    )


# ---------------------------------------------------------------------------
# Regresion (auditoria de mutaciones, hallazgo real, relayado por el
# coordinador): el guardian compartido de `stage_and_commit()`
# (`notes_commit.py`, lineas ~292-307 -- "un `git add` que si entro pero
# el commit que le sigue falla deja el indice con el contenido NUEVO
# staged, mismo `git status` en 'MM' que el escenario ya cerrado para
# `rules.py`") solo lo pinaba UN test de toda la suite, y via `rules.py`
# -- nunca a traves de uno de los otros tres llamadores reales de
# `stage_and_commit()` (`notes.write()`/`replace()`/`close()`). Si ese
# unico test de `rules.py` se retirase o se renombrase algun dia, estos
# tres llamadores se quedarian sin red sin que nadie lo notase. Este
# test cierra el hueco para `notes.write()` -- mismo patron de repo
# semilla que `test_rule_commit_contract.py::
# TestFailedCommitLeavesNoStagedLeftovers` (una escritura real primero,
# sin hook, para dejar el indice comiteado; el hook se planta solo para
# la SEGUNDA escritura, la que este test quiere ver rechazada).
# ---------------------------------------------------------------------------


def test_commit_rejected_by_pre_commit_hook_leaves_a_fully_clean_tree(
    notes, model, config, indexes, vocabulary, tmp_repo, make_note, make_context
):
    root = Path(tmp_repo)

    seed_note = make_note(headline="MARK_HOOK_SEED nota base comiteada antes del hook")
    seed_ctx = make_context()
    with _cwd(root):
        seed_result = notes.write(seed_note, seed_ctx)
    assert seed_result.ok, f"la siembra tiene que comitear limpia: {seed_result.git_error!r}"

    index_name, _seed_line = _index_line_for(
        indexes, vocabulary, notes.pm_root(root), seed_result.note_id
    )
    assert index_name is not None, (
        "precondicion del test: la nota semilla tiene que aparecer en algun indice"
    )
    index_relpath = os.path.join(".claude", "project-memory", index_name)
    baseline_content = (notes.pm_root(root) / index_name).read_text(encoding="utf-8")

    note = make_note(headline="MARK_HOOK nota que el hook de pre-commit va a rechazar")
    ctx = make_context()

    with _forced_pre_commit_hook_rejects(root):
        with _cwd(root):
            result = notes.write(note, ctx)

    assert result.ok is False, (
        f"un commit rechazado por el hook de pre-commit tiene que devolver "
        f"ok=False: {result!r}"
    )
    assert result.git_error, (
        f"el error real de git (el rechazo del hook) tiene que quedar visible "
        f"en git_error, no un ok=False mudo: {result!r}"
    )

    after_content = (notes.pm_root(root) / index_name).read_text(encoding="utf-8")
    assert after_content == baseline_content, (
        f"el contenido de {index_name} cambio aunque el commit fallo -- la "
        f"corrupcion silenciosa que esta pieza existe para prevenir: "
        f"antes={baseline_content!r} despues={after_content!r}"
    )

    rc_status, status_out, err_status = run_git(
        ["status", "--porcelain", "--", index_relpath], str(root)
    )
    assert rc_status == 0, f"git status fallo en el test: {err_status}"
    assert status_out.strip() == "", (
        f"tras un commit rechazado por el hook, {index_relpath} tiene que quedar "
        "COMPLETAMENTE limpio -- ni el indice (contenido rechazado ya staged por "
        "el `git add` que SI corrio antes del hook) ni el arbol de trabajo (ya "
        f"restaurado) pueden diferir de HEAD: git status --porcelain = "
        f"{status_out!r} (se espera cadena vacia, nunca 'MM')"
    )


# ---------------------------------------------------------------------------
# Fila 4
# ---------------------------------------------------------------------------


def test_discard_alternatives_produces_three_matching_commits(
    notes, model, config, indexes, vocabulary, tmp_repo, make_note, make_context
):
    """Fila 4: una decision con dos alternativas produce tres commits y
    tres indices que cuadran.

    Fallo real que previene: descartes que se pierden y una alternativa
    ya rechazada que se vuelve a proponer en seis meses.

    "Un acto, un commit" aplica a nota+indice, no al acto completo
    (PIEZAS.md Sec.8.1): una decision con DOS alternativas produce TRES
    commits en total (la decision + cada alternativa), no dos.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))
    _rc0, log_before, _err0 = run_git(["log", "--oneline"], tmp_repo)
    baseline_commit_count = len(log_before.splitlines())

    decision = make_note(
        type="D",
        headline="MARK_ROW4_DECISION choose JWT over session cookies",
        description="MARK_ROW4 decision description",
        why="MARK_ROW4 why -- obligatorio en el tipo D",
    )
    alt1 = make_note(
        type="X",
        headline="MARK_ROW4_ALT1 session cookies with sticky routing",
        description="MARK_ROW4 alt1 description",
    )
    alt2 = make_note(
        type="X",
        headline="MARK_ROW4_ALT2 opaque server-side tokens in Redis",
        description="MARK_ROW4 alt2 description",
    )
    ctx = make_context()

    with _cwd(root):
        results = notes.discard_alternatives(decision, (alt1, alt2), ctx)

    assert len(results) == 3, (
        "una decision con dos alternativas debe producir tres resultados (uno por "
        f"commit); llegaron {len(results)}"
    )
    assert all(r.ok for r in results), (
        f"algun commit del descarte fallo: {[r.git_error for r in results if not r.ok]}"
    )

    ids = [r.note_id for r in results]
    assert len(set(ids)) == 3, (
        f"los tres commits deberian llevar identificadores distintos, salieron: {ids}"
    )

    _rc1, log_after, _err1 = run_git(["log", "--oneline"], tmp_repo)
    new_commit_count = len(log_after.splitlines()) - baseline_commit_count
    assert new_commit_count == 3, (
        f"se esperaban exactamente 3 commits nuevos (uno por nota), hubo {new_commit_count}"
    )

    for note_id in ids:
        file_name, _line = _index_line_for(indexes, vocabulary, notes.pm_root(root), note_id)
        assert file_name is not None, (
            f"{note_id!r} no aparece en ningun indice vigente -- descarte perdido, "
            "puede volver a proponerse sin que nadie recuerde que ya se estudio"
        )


# ---------------------------------------------------------------------------
# Fila 5
# ---------------------------------------------------------------------------


def test_write_work_with_explicit_paths_does_not_drag_rest_of_tree(notes, tmp_repo):
    """Fila 5: un commit de trabajo con tres rutas no arrastra el resto
    del arbol.

    Fallo real que previene: la publicacion del toolkit se lleva por
    delante trabajo a medias.

    Se preparan cuatro ficheros trackeados. Tres (a/b/c) son "el trabajo
    que si se quiere commitear"; el cuarto (d) es "trabajo a medias en el
    mismo arbol de trabajo", staged igual que los otros tres -- para que
    la unica diferencia relevante sea que `write_work` no lo nombra en
    `paths`. Tras la llamada: d.txt NO debe aparecer en el diff del
    commit nuevo, HEAD:d.txt debe seguir siendo el contenido de ANTES, y
    el cambio a medias de d.txt debe seguir vivo (staged) en el arbol de
    trabajo -- ni arrastrado, ni perdido.
    """
    root = Path(tmp_repo)
    file_a = root / "a.txt"
    file_b = root / "b.txt"
    file_c = root / "c.txt"
    file_d = root / "d.txt"

    for handle, content in (
        (file_a, "a"),
        (file_b, "b"),
        (file_c, "c"),
        (file_d, "d-original"),
    ):
        handle.write_text(content, encoding="utf-8")
    run_git(["add", "a.txt", "b.txt", "c.txt", "d.txt"], tmp_repo)
    rc_seed, _out_seed, err_seed = run_git(
        ["commit", "-m", "seed de ficheros base del test"], tmp_repo
    )
    assert rc_seed == 0, f"no se pudo sembrar los ficheros base del test: {err_seed}"

    # Trabajo real que si se quiere commitear.
    file_a.write_text("a2", encoding="utf-8")
    file_b.write_text("b2", encoding="utf-8")
    file_c.write_text("c2", encoding="utf-8")
    # Trabajo a medias, en el mismo arbol, staged igual que a/b/c pero
    # deliberadamente fuera de la lista de rutas que se le pasa a write_work.
    file_d.write_text("d-modificado-a-medias", encoding="utf-8")
    run_git(["add", "a.txt", "b.txt", "c.txt", "d.txt"], tmp_repo)

    with _cwd(root):
        result = notes.write_work(
            "MARK_ROW5 commit de publicacion con tres rutas concretas",
            [file_a, file_b, file_c],
            issue=None,
        )

    assert result.ok, f"write_work() fallo inesperadamente: {result.git_error}"

    _rc_stat, stat_out, _err_stat = run_git(["show", "--stat", "HEAD"], tmp_repo)
    assert "a.txt" in stat_out
    assert "b.txt" in stat_out
    assert "c.txt" in stat_out
    assert "d.txt" not in stat_out, (
        "write_work() arrastro d.txt, que no era una de las tres rutas explicitas -- "
        "la publicacion se llevaria por delante trabajo a medias"
    )

    _rc_show_d, head_d_content, _err_show_d = run_git(["show", "HEAD:d.txt"], tmp_repo)
    assert head_d_content == "d-original", (
        "HEAD:d.txt ya no es el contenido de antes -- su cambio a medias se colo "
        "en el commit de publicacion"
    )

    _rc_status, status_out, _err_status = run_git(["status", "--porcelain"], tmp_repo)
    assert "d.txt" in status_out, (
        "el cambio a medias de d.txt desaparecio del arbol de trabajo -- se perdio, "
        "en vez de quedarse tal como estaba fuera de este commit"
    )


# ---------------------------------------------------------------------------
# Fila 6
# ---------------------------------------------------------------------------


def test_concurrent_writes_to_same_index_serialize(
    notes, model, config, indexes, vocabulary, tmp_repo, make_note, make_context
):
    """Fila 6: dos escrituras a la vez se serializan.

    Fallo real que previene: las dos leen el indice, cada una anade lo
    suyo, y la ultima borra el cambio de la otra sin avisar.

    Varios hilos reales (mismo patron que
    test_gitcmd.py::test_concurrent_writers_to_same_index_serialize_via_file_lock)
    llaman a `notes.write()` a la vez, todos con notas del MISMO tipo (para
    que compitan por el MISMO fichero de indice). Si `write()` serializa
    de verdad: N escritores producen N identificadores distintos, las N
    lineas aparecen todas en el indice (ninguna se pierde) y hay
    exactamente N commits nuevos -- ni uno de menos.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))
    ctx = make_context()

    n_writers = 6
    results = [None] * n_writers
    errors = []

    def _do_write(i):
        try:
            note = make_note(
                headline=f"MARK_ROW6_{i} concurrent memo number {i} about topic {i}",
                description=f"MARK_ROW6_{i} description for writer {i}",
            )
            results[i] = notes.write(note, ctx)
        except Exception as exc:  # se reporta, no se traga
            errors.append(exc)

    with _cwd(root):
        threads = [
            threading.Thread(target=_do_write, args=(i,), daemon=True)
            for i in range(n_writers)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

    still_alive = [t for t in threads if t.is_alive()]
    assert not still_alive, (
        f"{len(still_alive)} hilo(s) no terminaron dentro del plazo -- write() "
        "parece haberse colgado bajo escritura concurrente"
    )
    assert not errors, f"write() lanzo bajo escritura concurrente: {errors}"
    assert all(r is not None for r in results), "algun hilo nunca produjo resultado"

    failed = [r for r in results if not r.ok]
    assert not failed, (
        f"{len(failed)} escritura(s) concurrentes fallaron: "
        f"{[r.git_error for r in failed]}"
    )

    ids = [r.note_id for r in results]
    assert len(set(ids)) == n_writers, (
        f"se esperaban {n_writers} identificadores distintos (uno por escritor), "
        f"salieron: {ids} -- una carrera piso la asignacion de id de otra"
    )

    missing = [
        note_id
        for note_id in ids
        if _index_line_for(indexes, vocabulary, notes.pm_root(root), note_id)[0] is None
    ]
    assert not missing, (
        f"estos identificadores nunca llegaron a ningun indice: {missing} -- la "
        "actualizacion perdida que la serializacion existe para prevenir"
    )

    _rc_log, log_out, _err_log = run_git(["log", "--oneline"], tmp_repo)
    assert len(log_out.splitlines()) == 1 + n_writers, (
        "el numero de commits no coincide con 1 (init) + un commit por escritor -- "
        "algun commit se perdio o se piso bajo concurrencia"
    )


# ---------------------------------------------------------------------------
# Filas 7-11 (anadidas el 2026-08-02): `replace()` y `close()`, la mitad del
# ciclo de vida de una nota que las seis filas de arriba no cubrian.
# PIEZAS.md Sec.8.1 ya declaraba sus firmas en la Superficie, pero la tabla
# "Sus tests" original y el docstring de este fichero eran explicitos: "esas
# seis, ni una mas" -- por eso `notes.py` las deja declaradas lanzando
# `NotImplementedError` (ver los puntos 5 de su docstring de modulo). El
# punto 10 de DEUDA.md las daba por huecos abiertos ("su comportamiento
# real no lo fija ningun texto") -- ESO YA NO ES CIERTO: spec Sec.5 describe
# los dos caminos de retirada ("la mata su reemplazo" / "se cruza y
# chirria"), TEXTOS.md Sec.4 fija las tres formas literales del destino de
# archivo (`replaced by <ID>` / `closed: <motivo>` / `promoted to <ID>`), y
# la propia Superficie de Sec.8.1 dice que cada una es "un solo commit".
# Estas cinco pruebas son EXACTAMENTE las cinco filas nuevas anadidas a la
# tabla "Sus tests" de PIEZAS.md Sec.8.1 -- una fila, un test, ni una mas,
# mismo criterio que las filas 1-6 de arriba.
#
# Hoy `replace()`/`close()` lanzan `NotImplementedError` sin condicion:
# los cinco tests de abajo fallan TODOS por esa misma causa real -- es el
# ROJO del modo test-first para esta ampliacion del contrato.
#
# DECISIONES TOMADAS PARA CERRAR HUECOS QUE NINGUN TEXTO FIJA LETRA POR
# LETRA (documentadas aqui, no rellenadas en silencio -- PIEZAS.md Sec.0.2):
#
# 1. El tercer destino literal, "promoted to <ID>" (TEXTOS Sec.4), NO se
#    prueba en ninguna de las cinco filas: ni la Superficie ni la tabla
#    "Sus tests" de Sec.8.1 mencionan una tercera funcion o un tercer
#    camino que lo produzca -- "promote" no existe en la Superficie de
#    notes.py. Se deja fuera; no se inventa una funcion para probarlo.
# 2. Fila 11 (identificador inexistente) lee "rebota" como "lanza una
#    excepcion" (`pytest.raises(Exception)`, generico, nunca un tipo
#    concreto), NO como `WriteResult(ok=False, ...)`. Motivo: `indexes.py`
#    (Sec.7.3, ya en produccion) ya lanza `ValueError` para el caso analogo
#    mas cercano -- retirar un id que no esta en su indice (`remove()`,
#    verificado leyendo su codigo fuente antes de escribir este test). La
#    letra del tipo ya viaja en el propio identificador ("M-999999" ->
#    MEMOS.md), asi que si `replace()`/`close()` reutilizan `indexes.remove()`
#    para localizar la linea a retirar (en vez de reinventar esa busqueda),
#    la excepcion que ya existe se propaga sola, sin necesitar una nueva. Si
#    esta lectura resulta equivocada, es un cambio de una linea en este
#    test, no un rediseno.
# 3. Filas 7/8 (replace en verde) dan de alta `new.replaces = old_id` y
#    meten `old_id` en `ctx.known_ids` -- `validator.validate_pointers` (ya
#    en produccion) rechaza cualquier `note.replaces` que no este en
#    `known_ids`, y spec Sec.5 describe el puntero como parte del uso real
#    ("la nueva con su puntero"). Sin este `known_ids`, el test no probaria
#    `replace()` de verdad: probaria el rechazo del puntero.
# ---------------------------------------------------------------------------


def _read_all_eight_files(root, vocabulary_mod):
    """Contenido crudo (texto completo) de los OCHO ficheros de indice,
    ARCHIVED.md incluido -- a diferencia de `_read_all_index_contents`
    (filas 1-6 arriba), que lo excluye a proposito porque `write()` nunca
    lo toca. `replace()`/`close()` SI escriben en ARCHIVED.md, asi que la
    comprobacion "nada cambio" de las filas 10 y 11 tiene que cubrirlo
    tambien.
    """
    return {
        name: (Path(root) / name).read_text(encoding="utf-8")
        for name in vocabulary_mod.INDEX_FILES
    }


def _archive_line_for(indexes_mod, root, note_id):
    """La `ArchiveLine` de `note_id` en ARCHIVED.md, o `None` si no
    aparece. Usa el lector real (`indexes.read_archive` ->
    `format.parse_archive_line`), nunca una comparacion de texto tecleada
    a mano -- `parse_archive_line` solo reconoce las tres formas literales
    de destino que TEXTOS.md Sec.4 fija, asi que una coincidencia aqui ya
    prueba que el texto escrito fue una de esas tres.
    """
    for line in indexes_mod.read_archive(root):
        if line.id == note_id:
            return line
    return None


# ---------------------------------------------------------------------------
# Fila 7
# ---------------------------------------------------------------------------


def test_replace_single_commit_carries_new_note_new_index_line_old_removed_and_archived(
    notes, model, config, indexes, format_mod, vocabulary, tmp_repo, make_note, make_context
):
    """Fila 7: `replace` -- un solo commit lleva la nota nueva, su linea de
    indice, la vieja fuera del indice y su linea en el archivo.

    Fallo real que previene: que la sustitucion quede a medias -- dos
    notas vigentes diciendo lo contrario, y nadie sabe cual manda.

    Cuatro comprobaciones contra el repo real, en el MISMO commit: (a) el
    mensaje real del commit se vuelve a leer como la nota NUEVA; (b) la
    linea de indice de la nota nueva aparece en un indice vigente; (c) la
    linea de indice de la nota vieja YA NO aparece en ningun indice
    vigente; (d) la nota vieja aparece en ARCHIVED.md. Y una quinta: el
    numero de commits nuevos es exactamente uno, no dos.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))

    old_note = make_note(
        headline="MARK_ROW7_OLD headline that replace() must retire in one commit"
    )
    with _cwd(root):
        result_old = notes.write(old_note, make_context())
    assert result_old.ok, f"seed write() del test fallo: {result_old.git_error}"
    old_id = result_old.note_id

    _rc0, log_before, _err0 = run_git(["log", "--oneline"], tmp_repo)
    baseline_commit_count = len(log_before.splitlines())

    new_note = make_note(
        headline="MARK_ROW7_NEW headline that must land alongside the retirement",
        replaces=old_id,
    )
    ctx = make_context(known_ids=frozenset({old_id}))

    with _cwd(root):
        result = notes.replace(new_note, old_id, ctx)

    assert result.ok, f"replace() fallo inesperadamente: {result.git_error}"
    new_id = result.note_id
    assert new_id and new_id != old_id, (
        f"replace() no devolvio un identificador nuevo y distinto del viejo: {new_id!r}"
    )

    _rc1, log_after, _err1 = run_git(["log", "--oneline"], tmp_repo)
    new_commit_count = len(log_after.splitlines()) - baseline_commit_count
    assert new_commit_count == 1, (
        f"replace() debe producir exactamente UN commit, produjo {new_commit_count} -- "
        "una sustitucion partida en dos actos es la corrupcion que esta fila existe "
        "para prevenir"
    )

    _rc_body, body, _err_body = run_git(["log", "-1", "--format=%B", "HEAD"], tmp_repo)
    parsed = format_mod.parse_message(body)
    assert parsed is not None, f"el mensaje del commit de replace() no se pudo releer: {body!r}"
    assert parsed.id == new_id
    assert parsed.headline == new_note.headline
    assert parsed.description == new_note.description

    new_file, new_line = _index_line_for(indexes, vocabulary, notes.pm_root(root), new_id)
    assert new_file is not None, (
        f"{new_id!r} (la nota nueva) no aparece en ningun indice vigente tras replace()"
    )
    assert new_line.headline == new_note.headline

    old_file, _old_line = _index_line_for(indexes, vocabulary, notes.pm_root(root), old_id)
    assert old_file is None, (
        f"{old_id!r} (la nota vieja) sigue en un indice vigente tras replace() -- dos "
        "notas vigentes diciendo lo contrario, nadie sabe cual manda"
    )

    archived = _archive_line_for(indexes, notes.pm_root(root), old_id)
    assert archived is not None, (
        f"{old_id!r} no aparece en ARCHIVED.md tras replace() -- desaparece sin rastro"
    )

    _rc_stat, stat_out, _err_stat = run_git(["show", "--stat", "HEAD"], tmp_repo)
    assert new_file in stat_out, (
        f"el commit no toco {new_file!r} (indice de la nota nueva) segun git show --stat"
    )
    assert "ARCHIVED.md" in stat_out, (
        "el commit no toco ARCHIVED.md segun git show --stat -- el archivado de la "
        "vieja no viajo en el mismo commit que la nota nueva"
    )


# ---------------------------------------------------------------------------
# Fila 8
# ---------------------------------------------------------------------------


def test_replace_archived_line_says_replaced_by_new_id_and_round_trips(
    notes, model, config, indexes, tmp_repo, make_note, make_context
):
    """Fila 8: `replace` -- la linea archivada dice `-> replaced by <ID
    nuevo>`, y se puede volver a leer.

    Fallo real que previene: una nota retirada que desaparece sin rastro
    de a donde fue.

    La comprobacion pasa por el lector real (`indexes.read_archive` ->
    `format.parse_archive_line`), nunca por una cadena tecleada a mano:
    `destination == "replaced"` ya prueba que el texto escrito fue una de
    las tres formas literales de TEXTOS.md Sec.4, y `destination_detail ==
    new_id` compara dos valores producidos por caminos distintos -- el ID
    que `replace()` devolvio en `WriteResult.note_id` contra el ID que
    `format.parse_archive_line` extrajo de vuelta del texto en disco.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))

    old_note = make_note(headline="MARK_ROW8_OLD headline whose retirement must round-trip")
    with _cwd(root):
        result_old = notes.write(old_note, make_context())
    assert result_old.ok, f"seed write() del test fallo: {result_old.git_error}"
    old_id = result_old.note_id

    new_note = make_note(
        headline="MARK_ROW8_NEW headline that becomes the replacement pointer",
        replaces=old_id,
    )
    ctx = make_context(known_ids=frozenset({old_id}))

    with _cwd(root):
        result = notes.replace(new_note, old_id, ctx)

    assert result.ok, f"replace() fallo inesperadamente: {result.git_error}"
    new_id = result.note_id

    archived = _archive_line_for(indexes, notes.pm_root(root), old_id)
    assert archived is not None, (
        f"{old_id!r} no aparece en ARCHIVED.md tras replace() -- desaparece sin rastro "
        "de a donde fue"
    )
    assert archived.destination == "replaced", (
        f"la linea archivada de {old_id!r} no es de la forma 'replaced by' -- salio "
        f"como {archived.destination!r}"
    )
    assert archived.destination_detail == new_id, (
        f"la linea archivada de {old_id!r} apunta a {archived.destination_detail!r}, "
        f"no al ID real de la sustituta ({new_id!r})"
    )


# ---------------------------------------------------------------------------
# Fila 9
# ---------------------------------------------------------------------------


def test_close_removes_from_index_and_archives_with_closed_reason(
    notes, model, config, indexes, vocabulary, tmp_repo, make_note, make_context
):
    """Fila 9: `close` -- la linea sale del indice y entra en el archivo
    con `-> closed: <motivo>`.

    Fallo real que previene: una nota cerrada que sigue saliendo en los
    informes como si fuera verdad.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))

    note = make_note(headline="MARK_ROW9 headline for a note that gets closed, not replaced")
    with _cwd(root):
        result_write = notes.write(note, make_context())
    assert result_write.ok, f"seed write() del test fallo: {result_write.git_error}"
    note_id = result_write.note_id

    _rc0, log_before, _err0 = run_git(["log", "--oneline"], tmp_repo)
    baseline_commit_count = len(log_before.splitlines())

    reason = "MARK_ROW9_REASON arreglado en un incidente que ya no aplica"

    with _cwd(root):
        result = notes.close(note_id, reason, make_context())

    assert result.ok, f"close() fallo inesperadamente: {result.git_error}"

    _rc1, log_after, _err1 = run_git(["log", "--oneline"], tmp_repo)
    new_commit_count = len(log_after.splitlines()) - baseline_commit_count
    assert new_commit_count == 1, (
        f"close() debe producir exactamente UN commit, produjo {new_commit_count}"
    )

    live_file, _live_line = _index_line_for(indexes, vocabulary, notes.pm_root(root), note_id)
    assert live_file is None, (
        f"{note_id!r} sigue en un indice vigente tras close() -- seguiria saliendo en "
        "los informes como si fuera verdad"
    )

    archived = _archive_line_for(indexes, notes.pm_root(root), note_id)
    assert archived is not None, f"{note_id!r} no aparece en ARCHIVED.md tras close()"
    assert archived.destination == "closed", (
        f"la linea archivada de {note_id!r} no es de la forma 'closed:' -- salio como "
        f"{archived.destination!r}"
    )
    assert archived.destination_detail == reason, (
        f"el motivo archivado ({archived.destination_detail!r}) no coincide con el "
        f"motivo real pasado a close() ({reason!r})"
    )


# ---------------------------------------------------------------------------
# Fila 10
# ---------------------------------------------------------------------------


def test_failed_commit_leaves_indexes_exactly_as_before_for_replace_and_close(
    notes, model, config, indexes, vocabulary, tmp_repo, make_note, make_context
):
    """Fila 10: si el commit falla, en las dos (`replace` y `close`), los
    indices quedan exactamente como estaban.

    Fallo real que previene: un indice que apunta a una nota que no existe.

    El fallo de git es real (mismo mecanismo `.git/index.lock` de las
    filas 2/3 de arriba), no simulado. Se compara BYTE A BYTE el contenido
    de los OCHO ficheros (los siete indices vigentes MAS ARCHIVED.md --
    `replace`/`close` escriben ahi, a diferencia de `write()`) antes y
    despues de cada intento fallido.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))

    # -- Parte "replace" --
    old_note = make_note(
        headline="MARK_ROW10_REPLACE_OLD headline that must survive a failed replace"
    )
    with _cwd(root):
        result_old = notes.write(old_note, make_context())
    assert result_old.ok, f"seed write() del test fallo: {result_old.git_error}"
    old_id = result_old.note_id

    baseline_replace = _read_all_eight_files(notes.pm_root(root), vocabulary)

    new_note = make_note(
        headline="MARK_ROW10_REPLACE_NEW headline that must never reach any index",
        replaces=old_id,
    )
    ctx_replace = make_context(known_ids=frozenset({old_id}))

    with _cwd(root), _forced_git_index_lock(root):
        result_replace = notes.replace(new_note, old_id, ctx_replace)

    assert result_replace.ok is False, (
        "se esperaba que replace() fallara con .git/index.lock ya ocupado -- si no "
        "fallo, esta parte del test no probo nada real"
    )
    after_replace = _read_all_eight_files(notes.pm_root(root), vocabulary)
    assert after_replace == baseline_replace, (
        "el contenido de al menos un fichero de indice (incluido ARCHIVED.md) cambio "
        "aunque el commit de replace() fallo -- la corrupcion silenciosa que esta fila "
        "existe para prevenir"
    )

    # -- Parte "close" --
    other_note = make_note(headline="MARK_ROW10_CLOSE headline that must survive a failed close")
    with _cwd(root):
        result_other = notes.write(other_note, make_context())
    assert result_other.ok, f"seed write() del test fallo: {result_other.git_error}"
    other_id = result_other.note_id

    baseline_close = _read_all_eight_files(notes.pm_root(root), vocabulary)

    with _cwd(root), _forced_git_index_lock(root):
        result_close = notes.close(
            other_id, "MARK_ROW10_CLOSE_REASON motivo del cierre fallido", make_context()
        )

    assert result_close.ok is False, (
        "se esperaba que close() fallara con .git/index.lock ya ocupado -- si no "
        "fallo, esta parte del test no probo nada real"
    )
    after_close = _read_all_eight_files(notes.pm_root(root), vocabulary)
    assert after_close == baseline_close, (
        "el contenido de al menos un fichero de indice (incluido ARCHIVED.md) cambio "
        "aunque el commit de close() fallo -- un indice apuntando a una nota que no "
        "existe, la corrupcion silenciosa que esta fila existe para prevenir"
    )


# ---------------------------------------------------------------------------
# Fila 11
# ---------------------------------------------------------------------------


def test_replace_or_close_unknown_id_bounces_without_touching_anything(
    notes, model, config, indexes, vocabulary, tmp_repo, make_note, make_context
):
    """Fila 11: cerrar o sustituir un identificador que no existe rebota,
    sin tocar nada.

    Fallo real que previene: un archivo que se llena de lineas que no
    corresponden a ninguna nota.

    "Rebota" se lee aqui como "lanza una excepcion" (`pytest.raises`,
    generico, no un tipo concreto) -- ver punto 2 de las decisiones en el
    comentario de cabecera de este bloque de filas 7-11 para el porque.

    Cada `pytest.raises(Exception)` va acompanado de una comprobacion
    explicita de que la excepcion NO es `NotImplementedError`: sin ella,
    este test pasaria en VERDE hoy mismo (antes de que Ultron implemente
    nada) por pura coincidencia -- `NotImplementedError` tambien es una
    `Exception`, y el hueco declarado a proposito en `notes.py` la lanza
    sin condicion. Esa coincidencia enmascararia el rojo real que este
    contrato exige: las cinco filas nuevas deben fallar HOY por la causa
    real (no implementado), nunca pasar por casualidad.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))

    _rc0, log_before, _err0 = run_git(["log", "--oneline"], tmp_repo)
    baseline_commit_count = len(log_before.splitlines())
    baseline_files = _read_all_eight_files(notes.pm_root(root), vocabulary)

    # -- Parte "replace" con un old_id que nunca existio --
    nonexistent_old_id = "M-999999"
    new_note = make_note(headline="MARK_ROW11_REPLACE headline pointed at a ghost id")
    ctx = make_context()

    with _cwd(root):
        with pytest.raises(Exception) as exc_info_replace:
            notes.replace(new_note, nonexistent_old_id, ctx)
    assert not isinstance(exc_info_replace.value, NotImplementedError), (
        "replace() sigue sin implementar (NotImplementedError) -- este test debe "
        "fallar hoy por esa causa real, no confundirse en verde con la excepcion de "
        "la fila 11 (identificador inexistente)"
    )

    after_replace_attempt = _read_all_eight_files(notes.pm_root(root), vocabulary)
    assert after_replace_attempt == baseline_files, (
        f"replace() con {nonexistent_old_id!r} (que nunca existio) modifico algun "
        "fichero de indice -- un archivo lleno de lineas que no corresponden a "
        "ninguna nota, el fallo que esta fila existe para prevenir"
    )

    # -- Parte "close" con un note_id que nunca existio --
    nonexistent_note_id = "I-999999"

    with _cwd(root):
        with pytest.raises(Exception) as exc_info_close:
            notes.close(nonexistent_note_id, "MARK_ROW11_CLOSE motivo irrelevante", ctx)
    assert not isinstance(exc_info_close.value, NotImplementedError), (
        "close() sigue sin implementar (NotImplementedError) -- este test debe fallar "
        "hoy por esa causa real, no confundirse en verde con la excepcion de la fila "
        "11 (identificador inexistente)"
    )

    after_close_attempt = _read_all_eight_files(notes.pm_root(root), vocabulary)
    assert after_close_attempt == baseline_files, (
        f"close() con {nonexistent_note_id!r} (que nunca existio) modifico algun "
        "fichero de indice"
    )

    _rc1, log_after, _err1 = run_git(["log", "--oneline"], tmp_repo)
    assert len(log_after.splitlines()) == baseline_commit_count, (
        "se creo al menos un commit nuevo pese a que ambos intentos debian rebotar sin "
        "tocar nada"
    )


# ---------------------------------------------------------------------------
# Regresion permanente de tres fallos arreglados el 2026-08-02, encontrados
# y verificados a mano por el propietario (no por un test de esta tarea).
# Cada uno nombra en su docstring que hacia el sistema ANTES del arreglo.
# Mismo criterio que el bloque REGRESION al final de test_format.py: cada
# uno se confirmo ROJO SIN su arreglo concreto antes de escribirse aqui --
# copia de lib/memory/ al scratchpad de esta sesion
# (mutcheck/lib_memory_broken1|2|3/), deshecho ahi el mecanismo puntual de
# cada bug (nunca lib/memory/ real), y una version minima sin pytest
# (probe1/2/3_*.py) que reproduce exactamente el escenario del test de
# abajo. Los tres devolvieron el sintoma descrito contra la copia rota, y
# el resultado correcto contra el codigo real.
# ---------------------------------------------------------------------------


def test_regression_blank_line_in_folded_field_survives_real_git_commit_and_query(
    notes, query, model, config, indexes, vocabulary, tmp_repo, make_note, make_context
):
    """REGRESION (arreglado 2026-08-02, el fallo mas grave de toda la
    obra): una nota con un campo de dos parrafos (una linea en blanco en
    medio de `description`) se escribia sin error pero desaparecia PARA
    SIEMPRE al releerla -- ni por identificador, ni por zona, ni por
    palabra volvia a aparecer nunca.

    Mecanismo exacto: `format._fold_raw` (Sec.6.4) codifica una linea en
    blanco dentro de un campo plegado como una linea de continuacion que
    contiene EXACTAMENTE un espacio. Git, con su modo de limpieza POR
    DEFECTO (`--cleanup=strip`), recorta el espacio final de cada linea
    del mensaje al comitear -- esa linea de continuacion se queda vacia.
    Al releer, `format._parse_body_fields` no reconoce una linea vacia ni
    como arranque de campo ni como continuacion y devuelve `None`;
    `parse_message` propaga ese `None`, y `query._parse_records` descarta
    en silencio cualquier commit que no parsea. El arreglo es
    `gitcmd.commit()`: pasa `--cleanup=verbatim` a git, que conserva el
    espacio final tal cual `format.build_message` lo escribio.

    Por que ningun test existente lo vio: los round trips de
    test_format.py son EN MEMORIA (`build_message` -> `parse_message`
    directo, sin pasar por git nunca) y los de test_query.py commitean de
    verdad pero ninguna de sus notas trae un campo con dos parrafos. El
    fallo vivia en la COSTURA entre lo que el sistema escribe y lo que
    git de verdad guarda -- ningun test cruzaba esa costura. Este si:
    escribe con `notes.write()` de verdad, contra un commit git real, y
    recupera con `query.by_id()`/`by_zone()`/`by_word()`, nunca contra
    `format.parse_message` en memoria.

    Confirmado en vivo contra una copia con `--cleanup=verbatim` quitado
    de `gitcmd.commit()` (scratchpad de esta sesion,
    `mutcheck/lib_memory_broken1/`, sondado con `mutcheck/
    probe1_blank_paragraph.py`): `query.by_id()` devolvia `None` -- la
    nota desaparecia -- con ese arreglo desecho; con el codigo real,
    vuelve identica por las tres puertas.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))
    two_paragraph_description = (
        "MARK_BLANKLINE parrafo uno de la descripcion, antes del hueco.\n"
        "\n"
        "MARK_BLANKLINE parrafo dos, que sin el arreglo desaparecia sin dejar rastro."
    )
    note = make_note(
        headline="MARK_BLANKLINE_REGRESSION note with a two-paragraph description",
        description=two_paragraph_description,
    )
    ctx = make_context()

    with _cwd(root):
        result = notes.write(note, ctx)
        assert result.ok, f"write() fallo inesperadamente: {result.git_error}"

        found = query.by_id(result.note_id)
        by_zone_result = query.by_zone(note.zone1, note.zone2)
        by_word_result = query.by_word("MARK_BLANKLINE_REGRESSION")

    assert found is not None, (
        "la nota con descripcion de dos parrafos desaparecio al releerla via "
        "query.by_id() -- exactamente el fallo silencioso que este test existe para "
        "prevenir"
    )
    assert found.description == two_paragraph_description, (
        "la descripcion volvio truncada o alterada: "
        f"{found.description!r} != {two_paragraph_description!r}"
    )
    assert result.note_id in {n.id for n in by_zone_result}, (
        "la nota con parrafo en blanco no aparece via query.by_zone()"
    )
    assert result.note_id in {n.id for n, _lines in by_word_result}, (
        "la nota con parrafo en blanco no aparece via query.by_word()"
    )


def test_regression_index_restored_when_exception_interrupts_commit_not_only_on_git_failure(
    notes, model, config, indexes, vocabulary, tmp_repo, make_note, make_context, monkeypatch
):
    """REGRESION (arreglado 2026-08-02): la restauracion del indice solo
    cubria el caso "git respondio con `returncode != 0`" -- entre escribir
    la linea de indice y comprobar ese resultado no habia ningun
    `try`/`finally`. Una excepcion real a mitad (un Ctrl-C durante un
    commit lento, por ejemplo) se saltaba la restauracion entera y dejaba
    el indice apuntando a un commit que nunca se hizo, huerfano para
    siempre. El arreglo envuelve ese tramo en `try/except BaseException`:
    restaura el indice y vuelve a lanzar la excepcion original.

    Se fuerza la excepcion en el punto exacto que describe el bug: la
    linea de indice ya esta escrita en disco (`indexes.insert()` ya
    corrio), y `gitcmd.commit()` -- el propio objeto modulo que
    `notes.py` usa por dentro, via el atributo `notes.gitcmd` (nunca un
    mock generico desconectado del modulo real) -- revienta simulando la
    interrupcion.

    Confirmado en vivo contra una copia con el `try/except BaseException`
    quitado (scratchpad de esta sesion, `mutcheck/lib_memory_broken2/`,
    sondado con `mutcheck/probe2_restore_on_exception.py`): la excepcion
    se propagaba igual, pero el indice NO se restauraba, con ese arreglo
    desecho; con el codigo real, se propaga Y se restaura.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))
    baseline = _read_all_index_contents(notes.pm_root(root), vocabulary)

    def _boom(*args, **kwargs):
        raise RuntimeError("MARK_SIMULATED_CTRLC mid-commit interruption")

    monkeypatch.setattr(notes.gitcmd, "commit", _boom)

    note = make_note(headline="MARK_ROW_EXC headline that must never reach a broken commit")
    ctx = make_context()

    with _cwd(root):
        with pytest.raises(RuntimeError, match="MARK_SIMULATED_CTRLC"):
            notes.write(note, ctx)

    after = _read_all_index_contents(notes.pm_root(root), vocabulary)
    assert after == baseline, (
        "una excepcion a mitad del commit (no un returncode != 0 ordenado de git) dejo "
        "el indice modificado -- la linea huerfana que este arreglo existe para prevenir"
    )


def test_regression_restore_failure_never_shadows_the_real_git_diagnostic(
    notes, model, config, indexes, vocabulary, tmp_repo, make_note, make_context, monkeypatch
):
    """REGRESION (arreglado 2026-08-02): `_restore_index_best_effort()`
    (que llama a `indexes.remove()` para revertir la linea de indice tras
    un commit que no llego a completarse) no estaba protegida contra su
    PROPIO fallo. Si `indexes.remove()` reventaba durante la
    restauracion, su excepcion SUSTITUIA el mensaje real de git: el
    usuario perdia el unico diagnostico que tenia para arreglar el
    problema, y ademas el indice se quedaba huerfano igual (la
    restauracion nunca llegaba a completarse). El arreglo envuelve la
    llamada a `indexes.remove()` en `try/except Exception: pass` --
    mejor esfuerzo, nunca sustituye el diagnostico real por el suyo
    propio.

    Se fuerza un fallo REAL de git (mismo mecanismo `.git/index.lock` que
    las filas 2/3 de este fichero) Y, a la vez, se hace reventar
    `indexes.remove()` -- el propio modulo que `notes.py` usa por dentro,
    via `notes.indexes` -- para que la restauracion tambien falle. El
    texto contra el que se compara `result.git_error` sale de una SONDA
    real (mismo patron que la fila 3), nunca tecleado a mano
    (unmassk-standards Sec.34).

    Confirmado en vivo contra una copia con el `try/except Exception`
    quitado de `_restore_index_best_effort()` (scratchpad de esta sesion,
    `mutcheck/lib_memory_broken3/`, sondado con
    `mutcheck/probe3_restore_shadow.py`): `notes.write()` lanzaba la
    excepcion de `indexes.remove()` hacia afuera -- el diagnostico real
    de git se perdia por completo -- con ese arreglo desecho; con el
    codigo real, `write()` no lanza y `git_error` es el mensaje real de
    git.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))

    def _boom_remove(*args, **kwargs):
        raise RuntimeError("MARK_RESTORE_OWN_FAILURE indexes.remove blew up too")

    monkeypatch.setattr(notes.indexes, "remove", _boom_remove)

    note = make_note(headline="MARK_ROW_SHADOW headline for the restore-swallow test")
    ctx = make_context()

    with _cwd(root), _forced_git_index_lock(root):
        result = notes.write(note, ctx)  # no debe lanzar la excepcion de indexes.remove
        _rc_probe, _out_probe, probe_stderr = run_git(
            ["commit", "--allow-empty", "-m", "sonda: mismo candado, mismo fallo (shadow test)"],
            tmp_repo,
        )

    assert result.ok is False
    assert result.git_error is not None, (
        "git_error es None -- el fallo real de git se perdio por completo"
    )
    assert "MARK_RESTORE_OWN_FAILURE" not in result.git_error, (
        "el error de la restauracion (indexes.remove) sustituyo al diagnostico real de "
        "git -- justo el fallo que este arreglo existe para prevenir"
    )
    assert probe_stderr.strip() != "", "la sonda no reprodujo un fallo real de git"
    probe_first_line = probe_stderr.strip().splitlines()[0]
    assert probe_first_line in result.git_error, (
        "el error devuelto no es el mensaje real de git para este fallo -- se esperaba "
        f"que contuviera {probe_first_line!r}, resultado real: {result.git_error!r}"
    )


# ---------------------------------------------------------------------------
# Regresion adicional (2026-08-02, EN ROJO -- sin arreglar todavia): el
# mismo defecto que la fila 3 protege (`git_error` vacio ante un fallo real
# de git), pero por una via que la fila 3 no cubre: `git commit` falla
# porque no hay nada que comitear, y git escribe el motivo en STDOUT, no en
# STDERR (que sale vacio). Confirmado ejecutando git de verdad en esta
# maquina antes de escribir el test, no supuesto. A diferencia del bloque
# de arriba, este NO se confirmo verde contra ninguna copia arreglada -- el
# arreglo lo hace Ultron despues de este test.
# ---------------------------------------------------------------------------


def test_regression_git_error_not_empty_when_git_failure_writes_only_stdout(
    notes, model, config, indexes, vocabulary, tmp_repo, make_note, make_context, monkeypatch
):
    """REGRESION EN ROJO: cuando `git commit` falla porque no hay nada que
    comitear, git escribe el motivo en STDOUT ('On branch main\\nnothing to
    commit, working tree clean\\n') y deja STDERR VACIO -- confirmado
    contra el git real de esta maquina, no supuesto. `notes.py` devuelve
    `git_error=git_result.stderr` tanto en `write()` (linea 264) como en
    `write_work()` (linea 317): ante ESTE fallo real (a diferencia de las
    filas 2/3, que usan `.git/index.lock` y SI llenan stderr),
    `WriteResult.git_error` sale como cadena vacia -- ni `None` ni el
    mensaje real, un fallo con causa que llega al usuario como un fallo SIN
    causa.

    Es exactamente el defecto que docs/spec-sistema-memoria-v2.md Sec.6,
    validacion 9, nombra del sistema viejo: "el generador nuevo propaga el
    error real de git; jamas lo silencia (defecto reproducido en el wrapper
    v1: 'Error: git commit failed:' vacio)". Y el contrato de
    `gitcmd.GitResult` en PIEZAS.md Sec.7.1: "el mensaje real, entero,
    nunca vacio ni recortado". El sistema nuevo reprodujo el fallo que
    existia para evitar.

    Cubre las DOS superficies que comparten la misma linea rota:

    - `write()`: se comitea primero un baseline real de los ocho indices
      sembrados (para que el arbol de trabajo y HEAD coincidan byte a
      byte), y se neutraliza `indexes.insert()` (via `notes.indexes`, el
      atributo real que `write()` usa por dentro -- mismo patron ya usado
      arriba en este fichero) para que el fichero de indice NUNCA cambie.
      `git add` no tiene nada nuevo que anadir y el `git commit` real que
      sigue despues falla, de verdad, con "nothing to commit".
    - `write_work()`: un fichero ya comiteado se pasa SIN modificar --
      ningun mock necesario, el mismo fallo real ocurre sin ayuda.

    El texto contra el que se compara cada `git_error` sale de una SONDA
    real -- un `git commit` de verdad emitido por el propio test contra el
    mismo repo, en el mismo estado (arbol de trabajo limpio), justo despues
    del intento -- nunca tecleado a mano (unmassk-standards Sec.34).
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))

    rc_add, _out_add, err_add = run_git(["add", "-A"], tmp_repo)
    assert rc_add == 0, f"no se pudo stagear el baseline sembrado: {err_add}"
    rc_seed_commit, _out_seed_commit, err_seed_commit = run_git(
        ["commit", "-m", "seed baseline de los ocho indices"], tmp_repo
    )
    assert rc_seed_commit == 0, f"no se pudo comitear el baseline sembrado: {err_seed_commit}"

    def _noop_insert(*args, **kwargs):
        return None

    monkeypatch.setattr(notes.indexes, "insert", _noop_insert)

    note = make_note(
        headline="MARK_ROW_STDOUT_ONLY headline for the write() nothing-to-commit test"
    )
    ctx = make_context()

    with _cwd(root):
        result = notes.write(note, ctx)
        _rc_probe, probe_stdout, _err_probe = run_git(
            ["commit", "-m", "sonda: nothing to commit (write)"], tmp_repo
        )

    assert result.ok is False, (
        "se esperaba que write() fallara con el indice neutralizado (nada nuevo que "
        "comitear) -- si no fallo, este test no probo nada real"
    )
    assert probe_stdout.strip() != "", (
        "la sonda no reprodujo un fallo real de git -- este test no prueba nada"
    )
    probe_first_line = probe_stdout.strip().splitlines()[0]
    assert result.git_error is not None, (
        "git_error es None ante un fallo real de git que solo escribe en stdout -- el "
        "usuario se queda sin diagnostico"
    )
    assert result.git_error.strip() != "", (
        "git_error vacio ante un fallo real de git que solo escribe en stdout -- "
        "convierte un fallo con causa (git lo dijo, por stdout) en un fallo sin causa"
    )
    assert probe_first_line in result.git_error, (
        "el error devuelto por write() no es el mensaje real de git para este fallo -- "
        f"se esperaba que contuviera {probe_first_line!r}, resultado real: "
        f"{result.git_error!r}"
    )

    file_x = root / "unchanged.txt"
    file_x.write_text("MARK_UNCHANGED contenido que nunca cambia", encoding="utf-8")
    rc_add_x, _out_add_x, err_add_x = run_git(["add", "unchanged.txt"], tmp_repo)
    assert rc_add_x == 0, f"no se pudo stagear unchanged.txt: {err_add_x}"
    rc_commit_x, _out_commit_x, err_commit_x = run_git(
        ["commit", "-m", "seed de unchanged.txt para write_work()"], tmp_repo
    )
    assert rc_commit_x == 0, f"no se pudo comitear unchanged.txt: {err_commit_x}"

    with _cwd(root):
        result_work = notes.write_work(
            "MARK_ROW_STDOUT_ONLY_WORK mensaje que no debe llegar a comitear nada",
            [file_x],
            issue=None,
        )
        _rc_probe_work, probe_stdout_work, _err_probe_work = run_git(
            ["commit", "-m", "sonda: nothing to commit (write_work)"], tmp_repo
        )

    assert result_work.ok is False, (
        "se esperaba que write_work() fallara al pasarle una ruta sin cambios -- si no "
        "fallo, este test no probo nada real"
    )
    assert probe_stdout_work.strip() != "", (
        "la sonda de write_work() no reprodujo un fallo real de git -- este test no "
        "prueba nada"
    )
    probe_first_line_work = probe_stdout_work.strip().splitlines()[0]
    assert result_work.git_error is not None, (
        "git_error es None en write_work() ante un fallo real de git que solo escribe "
        "en stdout -- el usuario se queda sin diagnostico"
    )
    assert result_work.git_error.strip() != "", (
        "git_error vacio en write_work() ante un fallo real de git que solo escribe en "
        "stdout -- convierte un fallo con causa en un fallo sin causa"
    )
    assert probe_first_line_work in result_work.git_error, (
        "el error devuelto por write_work() no es el mensaje real de git para este "
        f"fallo -- se esperaba que contuviera {probe_first_line_work!r}, resultado "
        f"real: {result_work.git_error!r}"
    )


# ---------------------------------------------------------------------------
# Regresion (2026-08-03, cierre de PIEZAS.md Sec.12bis para la capa 5 -- el
# fallo mas grave detectado en toda la obra hasta ahora, segun el encargo):
# `ids.next_id()` recibia solo el indice VIVO en `write()` y en `replace()`
# -- al archivar una nota (`close()`, o el lado "vieja" de un `replace()`),
# su numero desaparecia de esa vista y quedaba libre para la siguiente alta
# del mismo tipo. Reproducido en un repo real antes del arreglo: alta ->
# cierre -> alta devolvia el MISMO identificador dos veces, dos notas
# distintas etiquetadas igual en git PARA SIEMPRE. Arreglo real:
# `notes.py::_index_with_archived()` (punto 5 del docstring del modulo),
# que funde el indice vivo con `indexes.archived_ids()` antes de cada
# llamada a `ids.next_id()` -- `ids.py` en si NO cambio, su firma sigue
# siendo `next_id(type_, index)` letra por letra.
#
# Confirmado ROJO contra una copia de `lib/memory/` en el scratchpad de
# esta sesion (`dante_mutcheck_idreuse/lib_memory_reverted/`), con el
# mecanismo puntual deshecho (las dos llamadas de `notes.py` vueltas a
# `ids.next_id(tipo, current_index)` a secas, sin `_index_with_archived()`
# -- el reemplazo exacto y opuesto al que aplico Ultron) -- nunca en
# `lib/memory/` real ni siquiera de forma temporal. Dos scripts standalone
# (`repro.py`, `repro_replace.py`, mismo scratchpad) reprodujeron cada
# escenario contra un repo git real y desechable: los dos devolvieron el
# id reutilizado contra la copia deshecha, y el id correcto contra el
# codigo real. Copias descartadas tras la verificacion, nunca commiteadas.
# ---------------------------------------------------------------------------


def test_regression_closing_a_note_never_frees_its_id_for_the_next_write_of_the_same_type(
    notes, model, config, indexes, format_mod, vocabulary, tmp_repo, make_note, make_context
):
    """REGRESION -- el hallazgo real: alta -> cierre -> alta del mismo tipo
    tiene que dar dos identificadores DISTINTOS, nunca el mismo dos veces.

    Fallo real que este test fija: antes del arreglo, cerrar la primera
    incidencia liberaba su numero para la segunda -- `search.py --id
    I-001` enseñaba solo la vieja, la nueva no aparecia por ese id nunca.

    Compara dos cosas escritas por separado, no solo lo que la funcion
    bajo prueba dice de si misma: el id que `WriteResult.note_id`
    devolvio (la decision tomada EN PROCESO por `write()`) contra el id
    que se lee de vuelta de cada COMMIT REAL con `format.parse_message`
    -- el mismo lector independiente que usa `query.py`, nunca una
    lectura fabricada a mano.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))

    first_incident = make_note(type="I", headline="MARK_IDREUSE_1 an incident to close")
    with _cwd(root):
        result_first = notes.write(first_incident, make_context())
        _rc_sha1, first_sha, _err_sha1 = run_git(["rev-parse", "HEAD"], tmp_repo)
    assert result_first.ok, f"seed write() del test fallo: {result_first.git_error}"
    first_id = result_first.note_id

    with _cwd(root):
        result_close = notes.close(
            first_id, "MARK_IDREUSE_1 closing reason", make_context()
        )
    assert result_close.ok, f"close() del test fallo: {result_close.git_error}"

    second_incident = make_note(
        type="I", headline="MARK_IDREUSE_2 second incident, distinct from the first"
    )
    with _cwd(root):
        result_second = notes.write(second_incident, make_context())
        _rc_sha2, second_sha, _err_sha2 = run_git(["rev-parse", "HEAD"], tmp_repo)
    assert result_second.ok, f"segunda escritura del test fallo: {result_second.git_error}"
    second_id = result_second.note_id

    assert second_id != first_id, (
        f"el segundo alta reutilizo el identificador de la primera nota, ya cerrada: "
        f"{first_id!r} == {second_id!r} -- dos notas distintas con el mismo id para siempre"
    )
    assert (first_id, second_id) == ("I-001", "I-002"), (
        "se esperaba la secuencia exacta del hallazgo real (I-001 la primera vez, "
        f"I-002 la segunda), salio {(first_id, second_id)!r}"
    )

    # Los DOS COMMITS REALES llevan identificadores distintos -- releidos con
    # el lector real de la pareja productor<->consumidor, no supuestos.
    _rc_a, body_first, _err_a = run_git(["log", "-1", "--format=%B", first_sha], tmp_repo)
    _rc_b, body_second, _err_b = run_git(["log", "-1", "--format=%B", second_sha], tmp_repo)
    parsed_first = format_mod.parse_message(body_first)
    parsed_second = format_mod.parse_message(body_second)
    assert parsed_first is not None and parsed_second is not None, (
        "los dos commits de alta tienen que releerse como notas validas con el "
        "parser real"
    )
    assert parsed_first.id == first_id
    assert parsed_second.id == second_id
    assert parsed_first.id != parsed_second.id, (
        f"los DOS COMMITS REALES de git llevan el mismo identificador: "
        f"{parsed_first.id!r} == {parsed_second.id!r}"
    )


def test_regression_replace_also_never_reuses_an_id_archived_in_an_earlier_commit(
    notes, model, config, indexes, format_mod, vocabulary, tmp_repo, make_note, make_context
):
    """REGRESION -- la otra via que comparte el mismo defecto: `replace()`
    llama a `ids.next_id()` igual que `write()`, y hasta el arreglo tenia
    la MISMA ventana. El punto 4(a) del docstring del modulo ya protegia
    el caso de un solo commit (el numero que el propio `replace()` esta a
    punto de liberar no se reutiliza para la nota que ese mismo
    `replace()` crea) -- pero eso NO cubre un identificador archivado en
    un commit ANTERIOR, que es el hallazgo real.

    Orden realista, sin ningun cruce de tipos (`replace()` exige que el
    tipo nuevo admita `replaces` -- I no lo admite, M si): dos memos
    vivos, se cierra el MAS NUEVO (queda archivado), y mas tarde se
    sustituye el MAS VIEJO, que sigue vivo. Antes del arreglo, en ese
    instante el indice vivo de memos solo contenia la nota que se esta
    sustituyendo (la mas nueva ya no esta, esta archivada), asi que el
    siguiente numero se calculaba SOLO a partir de ella y colisionaba con
    el que el cierre ya habia archivado.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))

    older_memo = make_note(
        headline="MARK_IDREUSE_R1 older memo, stays live then gets replaced"
    )
    with _cwd(root):
        result_older = notes.write(older_memo, make_context())
    assert result_older.ok, f"seed write() del test fallo: {result_older.git_error}"
    older_id = result_older.note_id

    newer_memo = make_note(headline="MARK_IDREUSE_R2 newer memo, closed soon after")
    with _cwd(root):
        result_newer = notes.write(newer_memo, make_context())
    assert result_newer.ok, f"segunda siembra del test fallo: {result_newer.git_error}"
    newer_id = result_newer.note_id

    with _cwd(root):
        result_close = notes.close(
            newer_id,
            "MARK_IDREUSE_R closed while the older memo is still open",
            make_context(),
        )
    assert result_close.ok, f"close() del test fallo: {result_close.git_error}"

    replacement = make_note(
        headline="MARK_IDREUSE_R3 older memo superseded by a better description",
        replaces=older_id,
    )
    ctx = make_context(known_ids=frozenset({older_id}))
    with _cwd(root):
        result_replace = notes.replace(replacement, older_id, ctx)
        _rc_sha, replace_sha, _err_sha = run_git(["rev-parse", "HEAD"], tmp_repo)
    assert result_replace.ok, f"replace() fallo inesperadamente: {result_replace.git_error}"
    replaced_id = result_replace.note_id

    assert replaced_id != newer_id, (
        f"replace() reutilizo el identificador de una nota archivada en un commit "
        f"ANTERIOR: {replaced_id!r} == {newer_id!r} (ya archivada por close())"
    )
    assert (older_id, newer_id, replaced_id) == ("M-001", "M-002", "M-003"), (
        "se esperaba la secuencia exacta (M-001 la primera, M-002 la segunda -- "
        f"cerrada despues --, M-003 la de replace()), salio "
        f"{(older_id, newer_id, replaced_id)!r}"
    )

    # Mismo criterio que la fila de arriba: releido del COMMIT REAL, no
    # supuesto de lo que `WriteResult` dice de si mismo.
    _rc, body, _err = run_git(["log", "-1", "--format=%B", replace_sha], tmp_repo)
    parsed = format_mod.parse_message(body)
    assert parsed is not None, "el commit de replace() tiene que releerse como una nota valida"
    assert parsed.id == replaced_id == "M-003"


def test_regression_counter_stays_per_type_when_an_archived_note_of_another_type_exists(
    notes, model, config, indexes, format_mod, vocabulary, tmp_repo, make_note, make_context
):
    """El contador es POR TIPO -- `ids.py` Sec.7.2 ya lo prueba SIN
    archivados de por medio (fila 2 de sus tests). Lo que faltaba, y es
    exactamente el hueco de esta tarea, es la misma regla CON una nota
    archivada de OTRO tipo mezclada: `_index_with_archived()` funde en la
    MISMA tupla los ids archivados de TODOS los tipos -- no filtra por
    tipo antes de pasarla a `ids.next_id()` -- y es el filtrado por
    prefijo que ya vive dentro de `ids.next_id()` (Sec.7.2, "cuenta solo
    las lineas cuyo id empieza por type_-") el unico que evita que cerrar
    una decision mueva el contador de las incidencias.

    Cierra una D y comprueba, en el mismo repo, que una I nueva sigue
    empezando en I-001 -- y que la siguiente D (tras el cierre) continua
    en D-002, sin reutilizar D-001.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))

    decision = make_note(
        type="D",
        why="MARK_IDREUSE_D why this decision existed",
        headline="MARK_IDREUSE_D first decision, soon closed",
    )
    with _cwd(root):
        result_decision = notes.write(decision, make_context())
    assert result_decision.ok, f"seed write() del test fallo: {result_decision.git_error}"
    decision_id = result_decision.note_id
    assert decision_id == "D-001"

    with _cwd(root):
        result_close = notes.close(
            decision_id, "MARK_IDREUSE_D closed, superseded elsewhere", make_context()
        )
    assert result_close.ok, f"close() del test fallo: {result_close.git_error}"

    incident = make_note(
        type="I", headline="MARK_IDREUSE_D2 incident unrelated to the closed decision"
    )
    with _cwd(root):
        result_incident = notes.write(incident, make_context())
    assert result_incident.ok, f"escritura de la incidencia fallo: {result_incident.git_error}"
    assert result_incident.note_id == "I-001", (
        f"cerrar una decision no debe mover el contador de las incidencias -- salio "
        f"{result_incident.note_id!r}"
    )

    second_decision = make_note(
        type="D",
        why="MARK_IDREUSE_D2 why this second decision exists",
        headline="MARK_IDREUSE_D second decision, written after the first was closed",
    )
    with _cwd(root):
        result_second_decision = notes.write(second_decision, make_context())
    assert result_second_decision.ok, (
        f"segunda decision fallo: {result_second_decision.git_error}"
    )
    assert result_second_decision.note_id == "D-002", (
        f"el contador de decisiones tiene que seguir despues de D-001 (archivada), no "
        f"reiniciarse -- salio {result_second_decision.note_id!r}"
    )


# ---------------------------------------------------------------------------
# Regresion (2026-08-03, PIEZAS.md Sec.12bis paso 7 -- "Ultron y Dante
# reparan lo que Moriarty rompio", capa 3): `write_work()`
# (`lib/memory/notes_commit.py:242`) comitea SIN el candado global que sus
# tres hermanas de este mismo fichero (`write`/`replace`/`close`, lineas
# 199/314/401) SI toman -- `with gitcmd.file_lock(lock_resource(root)):`.
#
# La consecuencia, reproducida por el encargo antes de pedir estos tests y
# confirmada aqui otra vez en vivo antes de escribirlos: un commit
# PERMANENTE cuyo titulo dice una cosa y cuyo contenido es el de otro
# escritor, con el sistema respondiendo `ok=True` -- corrupcion silenciosa,
# no un error que se note. El mecanismo exacto: `stage_and_commit()` hace
# `git commit --cleanup=verbatim -m msg -- <rutas>` (`gitcmd.commit()`,
# forma con pathspec) -- esta forma de `git commit` NO usa lo que un
# `git add` anterior dejo preparado, vuelve a leer el ARBOL DE TRABAJO para
# esas rutas en el instante mismo del commit. Si el fichero fue pisado por
# otro escritor entre que se preparo y que se comiteo, el commit se lleva
# SU contenido bajo el mensaje de quien lo llamo. Confirmado contra el git
# real de esta maquina, no supuesto (misma tecnica de verificacion previa
# que ya usa `capa4-hardening-session-notes.md` para
# `gitcmd.commit_empty()`).
#
# Tres cosas se fijan aqui, ni una mas [encargo explicito de esta tarea]:
# la reproduccion determinista del fallo, que la serializacion real
# funcione igual que en las tres hermanas, y que el caso corriente (una
# ruta, varias rutas, nadie mas en medio) no se rompa con el arreglo.
# ---------------------------------------------------------------------------


def test_regression_write_work_without_lock_can_commit_another_writers_content_under_its_own_message(
    notes, tmp_repo
):
    """Reproduccion DETERMINISTA del fallo -- 100% de las veces, sin
    depender de ningun timing de hilos ni de la suerte.

    La secuencia (identica a la que reprodujo el encargo antes de pedir
    este test):
      1. Un primer escritor escribe `content-A` en `shared.txt` y hace
         `git add` -- su propia preparacion, ya en curso.
      2. Un segundo escritor pisa el MISMO fichero con `content-B` y
         tambien hace `git add`.
      3. El primero llama a `notes.write_work("msgA", [shared], None)`.

    Hoy: `result.ok` sale `True`, y `git show HEAD:shared.txt` -- la
    fuente de la verdad, nunca lo que devuelve la funcion, tal como pide
    el encargo -- sale `content-B` bajo un commit titulado `msgA`. El
    sistema reporta exito sobre un commit que miente acerca de lo que
    guardo.

    La aserción no fija de antemano COMO se arregla -- ningun texto de
    esta rama dice si el arreglo tiene que impedir el pisotón entero o
    detectarlo y fallar con causa en vez de mentir (el candado que hace
    falta es sobre la ESCRITURA DEL SISTEMA, no sobre `.git/index.lock`
    de git -- ver el encargo). Lo que no puede seguir pasando, bajo
    NINGUNA forma del arreglo, es `ok=True` a la vez que el contenido real
    diverge de lo que este escritor preparo: eso es exactamente la
    corrupcion silenciosa que esta pieza existe para prevenir.
    """
    root = Path(tmp_repo)
    shared = root / "shared.txt"

    shared.write_text("content-A\n", encoding="utf-8")
    run_git(["add", "shared.txt"], tmp_repo)

    shared.write_text("content-B\n", encoding="utf-8")
    run_git(["add", "shared.txt"], tmp_repo)

    with _cwd(root):
        result = notes.write_work("msgA", [shared], issue=None)

    _rc_show, head_content, _err_show = run_git(["show", "HEAD:shared.txt"], tmp_repo)
    _rc_msg, head_message, _err_msg = run_git(["log", "-1", "--format=%s"], tmp_repo)

    assert not (result.ok and head_content != "content-A\n"), (
        f"write_work() dijo ok=True pero el commit titulado {head_message!r} "
        f"comiteo {head_content!r} en vez del contenido que este escritor "
        "preparo (content-A) -- un commit permanente que miente sobre lo que "
        "guardo, y el sistema lo reporta como exito"
    )


def test_regression_write_work_serializes_like_its_three_siblings_under_real_concurrent_writers(
    notes, tmp_repo
):
    """Que el commit de trabajo se serializa igual que `write()` (fila 6
    de arriba) y que `test_gitcmd.py::
    test_concurrent_writers_to_same_index_serialize_via_file_lock`, mismo
    patron: varios escritores reales, cada uno con su PROPIA ruta, llaman
    a `write_work()` a la vez -- sin forzar ningun orden.

    Calibrado en vivo antes de escribir este test: sin candado, 10 hilos
    concurrentes contra el codigo de hoy chocan de verdad contra
    `.git/index.lock` -- git no reintiene por su cuenta -- entre 7 y 8 de
    cada 10 en las cinco repeticiones que se probaron (`fatal: Unable to
    create '.../.git/index.lock': File exists`). Con el candado que ya
    usan sus tres hermanas, los N escritores tienen que terminar los N,
    sin que ninguno choque contra el indice de git sin reintento, y sin
    que el contenido de uno aparezca bajo el commit de otro (cada
    escritor tiene su propia ruta -- ninguno debe perder ni heredar el
    contenido ajeno).
    """
    root = Path(tmp_repo)
    n_writers = 10
    results = [None] * n_writers
    errors = []

    def _do_write(i):
        try:
            path = root / f"work_file_{i}.txt"
            path.write_text(f"content writer {i}\n", encoding="utf-8")
            results[i] = notes.write_work(
                f"MARK_ROW_WORK_LOCK commit de trabajo concurrente {i}", [path], issue=None
            )
        except Exception as exc:  # se reporta, no se traga
            errors.append(exc)

    with _cwd(root):
        threads = [
            threading.Thread(target=_do_write, args=(i,), daemon=True)
            for i in range(n_writers)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

    still_alive = [t for t in threads if t.is_alive()]
    assert not still_alive, (
        f"{len(still_alive)} hilo(s) no terminaron dentro del plazo -- write_work() "
        "parece haberse colgado bajo escritura concurrente"
    )
    assert not errors, f"write_work() lanzo bajo escritura concurrente: {errors}"
    assert all(r is not None for r in results), "algun hilo nunca produjo resultado"

    lock_collisions = [
        r.git_error
        for r in results
        if not r.ok and r.git_error and "index.lock" in r.git_error
    ]
    assert not lock_collisions, (
        f"{len(lock_collisions)} escritor(es) chocaron contra .git/index.lock sin "
        f"reintento -- exactamente lo que el candado tiene que evitar: {lock_collisions}"
    )

    failed = [r for r in results if not r.ok]
    assert not failed, (
        f"{len(failed)} commit(s) de trabajo concurrentes fallaron: "
        f"{[r.git_error for r in failed]}"
    )

    mismatched = []
    for i in range(n_writers):
        _rc, content, _err = run_git(["show", f"HEAD:work_file_{i}.txt"], tmp_repo)
        if content != f"content writer {i}":
            mismatched.append((i, content))
    assert not mismatched, (
        f"estos ficheros en HEAD no llevan el contenido de su propio escritor -- se "
        f"llevaron el de otro: {mismatched}"
    )

    _rc_log, log_out, _err_log = run_git(["log", "--oneline"], tmp_repo)
    assert len(log_out.splitlines()) == 1 + n_writers, (
        "el numero de commits no coincide con 1 (init) + un commit por escritor -- "
        "algun commit se perdio bajo concurrencia"
    )


def test_write_work_ordinary_commit_with_a_single_path_still_works(notes, tmp_repo):
    """Regresion (la tercera cosa que pide esta tarea): el caso corriente
    con UNA sola ruta, sin nadie mas en medio, tiene que seguir
    funcionando exactamente igual una vez que `write_work()` tome el
    candado -- si el arreglo rompe esto, es peor que el fallo que vino a
    arreglar.
    """
    root = Path(tmp_repo)
    file_a = root / "solo.txt"
    file_a.write_text("solo content", encoding="utf-8")

    _rc_before, before_count, _err_before = run_git(["rev-list", "--count", "HEAD"], tmp_repo)

    with _cwd(root):
        result = notes.write_work(
            "MARK_ROW_WORK_SINGLE commit de trabajo con una sola ruta", [file_a], issue=None
        )

    assert result.ok, (
        f"write_work() con una sola ruta, sin nadie mas en medio, fallo inesperadamente: "
        f"{result.git_error}"
    )

    _rc_after, after_count, _err_after = run_git(["rev-list", "--count", "HEAD"], tmp_repo)
    assert int(after_count) == int(before_count) + 1, (
        "no se creo exactamente un commit nuevo para el commit de trabajo de una sola ruta"
    )

    _rc_show, content, _err_show = run_git(["show", "HEAD:solo.txt"], tmp_repo)
    assert content == "solo content"

    _rc_msg, message, _err_msg = run_git(["log", "-1", "--format=%B", "HEAD"], tmp_repo)
    assert message.strip().splitlines()[0] == "MARK_ROW_WORK_SINGLE commit de trabajo con una sola ruta"


def test_write_work_ordinary_commit_with_several_paths_still_works(notes, tmp_repo):
    """Regresion (la tercera cosa que pide esta tarea): el caso corriente
    con VARIAS rutas, sin nadie mas en medio, tiene que seguir
    funcionando exactamente igual una vez que `write_work()` tome el
    candado. Complementa la fila 5 de arriba (que verifica que NO arrastra
    ficheros ajenos a `paths`) con el caso mas simple: varias rutas
    propias, todas comiteadas, cada una con su contenido correcto.
    """
    root = Path(tmp_repo)
    file_a = root / "multi_a.txt"
    file_b = root / "multi_b.txt"
    file_c = root / "multi_c.txt"
    for handle, content in ((file_a, "a content"), (file_b, "b content"), (file_c, "c content")):
        handle.write_text(content, encoding="utf-8")

    _rc_before, before_count, _err_before = run_git(["rev-list", "--count", "HEAD"], tmp_repo)

    with _cwd(root):
        result = notes.write_work(
            "MARK_ROW_WORK_MULTI commit de trabajo con varias rutas",
            [file_a, file_b, file_c],
            issue=None,
        )

    assert result.ok, (
        f"write_work() con varias rutas, sin nadie mas en medio, fallo inesperadamente: "
        f"{result.git_error}"
    )

    _rc_after, after_count, _err_after = run_git(["rev-list", "--count", "HEAD"], tmp_repo)
    assert int(after_count) == int(before_count) + 1, (
        "no se creo exactamente un commit nuevo para el commit de trabajo de varias rutas"
    )

    mismatched = []
    for path, expected in (
        (file_a, "a content"), (file_b, "b content"), (file_c, "c content")
    ):
        _rc_show, content, _err_show = run_git(["show", f"HEAD:{path.name}"], tmp_repo)
        if content != expected:
            mismatched.append((path.name, content, expected))
    assert not mismatched, (
        f"alguna de las rutas no quedo con su contenido esperado en HEAD: {mismatched}"
    )


# ---------------------------------------------------------------------------
# Encargo aparte (2026-08-03): fijar con un test el caso real que mantuvo
# vivo el punto 27 de DEUDA.md durante tres rondas -- dado por cerrado dos
# veces sin estarlo. Los dos tests de arriba que ya cubren `write_work()` sin
# candado NO cubren este caso:
#   - `test_regression_write_work_without_lock_can_commit_another_writers_
#     content_under_its_own_message` simula un `git add` EXTERNO a mano --
#     un proceso intruso que nunca llama a `write_work()`.
#   - `test_regression_write_work_serializes_like_its_three_siblings_under_
#     real_concurrent_writers` lanza diez HILOS, cada uno con su PROPIA
#     ruta -- nunca chocan por el mismo fichero.
#
# El caso real es distinto de los dos: DOS PROCESOS normales (nunca hilos --
# el propio arreglo se verifico asi, ver el punto 7 del docstring de
# `write_work()` en notes_commit.py: "verificado en vivo, dos procesos de SO
# reales, no hilos"), cada uno escribe su PROPIO contenido en el MISMO
# fichero por su cuenta y cada uno llama a `notes.write_work()`. Sin ningun
# `git add` externo. Sin proceso intruso.
#
# Medido por el propio equipo antes del arreglo del punto 7: 11 de 20
# intentos (55%) salian con `ok=True` y el commit permanente llevaba el
# mensaje de un escritor sobre el contenido del otro. Despues: 0 de 60.
# ---------------------------------------------------------------------------


def test_regression_two_real_processes_writing_same_file_never_commit_crossed_content_under_ok_true(
    tmp_repo, tmp_path
):
    """Reproduccion del caso real que mantuvo vivo el punto 27: dos
    PROCESOS DE VERDAD (`subprocess.Popen`, nunca hilos), cada uno escribe
    su propio contenido en `shared.txt` y llama a `notes.write_work()` --
    sin ningun `git add` externo, sin proceso intruso.

    20 rondas -- antes del arreglo fallaba mas de la mitad de las veces, asi
    que basta para ser concluyente.

    La aserción, contra `git show` EN CRUDO -- nunca contra lo que la
    funcion DICE que hizo -- es la misma en las dos direcciones: si
    `write_work()` responde `ok=True`, el commit que lleva su mensaje tiene
    que llevar EXACTAMENTE su propio contenido. Si no puede garantizarlo,
    la salida correcta es `ok=False` con causa en `git_error` -- eso no se
    penaliza aqui, es el comportamiento que el punto 27 pide.

    El script que cada proceso ejecuta vive en `tmp_path` (nunca en
    `lib/memory/`, regla de esta obra tras el incidente de
    `mutation-check-collision-incident-ids.md`): escribe sus propios bytes
    en `shared.txt` y se los pasa a `write_work()` como `known_content` --
    el mismo contrato que usan de verdad `bin/memory/work.py` y
    `bin/memory/wip.py` (leer el fichero como primerisima accion, antes de
    cualquier otra cosa, y pasar esos bytes sin releerlos del disco).
    """
    root = Path(tmp_repo)
    shared = root / "shared.txt"

    script_lines = [
        "import base64",
        "import json",
        "import sys",
        "from pathlib import Path",
        "",
        f"sys.path.insert(0, {LIB_MEMORY_DIR!r})",
        "import notes  # noqa: E402",
        "",
        "path_str, content_b64, message, pass_known = sys.argv[1:5]",
        "own_bytes = base64.b64decode(content_b64)",
        "",
        "with open(path_str, 'wb') as fh:",
        "    fh.write(own_bytes)",
        "",
        "known_content = [own_bytes] if pass_known == '1' else None",
        "result = notes.write_work(",
        "    message, [Path(path_str)], issue=None, known_content=known_content",
        ")",
        "print(json.dumps({'ok': result.ok, 'git_error': result.git_error}))",
    ]
    script_path = tmp_path / "concurrent_writer.py"
    script_path.write_text("\n".join(script_lines), encoding="utf-8")

    n_rounds = 20
    for round_idx in range(n_rounds):
        content_a = f"round-{round_idx}-content-A".encode("utf-8")
        content_b = f"round-{round_idx}-content-B".encode("utf-8")
        message_a = f"MARK_ROW_TWOPROC_A_{round_idx} proceso A"
        message_b = f"MARK_ROW_TWOPROC_B_{round_idx} proceso B"

        proc_a = subprocess.Popen(
            [
                sys.executable, str(script_path), str(shared),
                base64.b64encode(content_a).decode("ascii"), message_a, "1",
            ],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        proc_b = subprocess.Popen(
            [
                sys.executable, str(script_path), str(shared),
                base64.b64encode(content_b).decode("ascii"), message_b, "1",
            ],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        out_a, err_a = proc_a.communicate(timeout=30)
        out_b, err_b = proc_b.communicate(timeout=30)

        assert proc_a.returncode == 0, (
            f"ronda {round_idx}: el proceso A revento (returncode "
            f"{proc_a.returncode}): {err_a}"
        )
        assert proc_b.returncode == 0, (
            f"ronda {round_idx}: el proceso B revento (returncode "
            f"{proc_b.returncode}): {err_b}"
        )

        result_a = json.loads(out_a)
        result_b = json.loads(out_b)

        for result, message, content, label in (
            (result_a, message_a, content_a, "A"),
            (result_b, message_b, content_b, "B"),
        ):
            if not result["ok"]:
                assert result["git_error"], (
                    f"ronda {round_idx}, escritor {label}: write_work() devolvio "
                    "ok=False sin causa en git_error -- fallar con causa es una "
                    "salida correcta, fallar en silencio no"
                )
                continue

            _rc_log, commit_hash, _err_log = run_git(
                ["log", "--fixed-strings", f"--grep={message}", "-1", "--format=%H"],
                str(root),
            )
            assert commit_hash, (
                f"ronda {round_idx}, escritor {label}: write_work() dijo ok=True "
                f"pero no existe ningun commit con el mensaje {message!r}"
            )

            _rc_show, real_content, _err_show = run_git(
                ["show", f"{commit_hash}:shared.txt"], str(root)
            )
            assert real_content == content.decode("utf-8"), (
                f"ronda {round_idx}, escritor {label}: write_work() dijo ok=True "
                f"bajo el mensaje {message!r}, pero el commit real ({commit_hash}) "
                f"lleva {real_content!r} en vez de {content.decode('utf-8')!r} -- "
                "contenido de otro escritor bajo el mensaje de este, exactamente "
                "el fallo mas grave de la obra (DEUDA.md punto 27)"
            )


# ---------------------------------------------------------------------------
# Encargo aparte (2026-08-04): `known_content` con `None` para una ruta --
# contrato escrito, palabra por palabra, en los DOS unicos llamadores reales
# (`bin/memory/work.py` lineas 73-76 y `bin/memory/wip.py` lineas 85-88):
# "`None` si la ruta no se puede leer ahora mismo (no existe, permiso) --
# write_work() cae entonces a su propia lectura de disco para esa ruta,
# mismo comportamiento que antes de este arreglo, no una regresion." El
# codigo real de `write_work()` (notes_commit.py) hace otra cosa: cuando
# `known_content` trae `None` para una ruta, la huella de ENTRADA para esa
# ruta se fija a `None` -- no "cae a leer el disco", fija un valor fijo --
# y la comparacion posterior (que SI lee el disco) casi nunca vuelve a dar
# `None` para un fichero que existe, asi que la ruta cae en
# `changed_since_entry` y el commit se rechaza con un diagnostico que dice
# que "otro proceso" toco el fichero, cuando en un solo proceso, sin nadie
# mas, eso nunca paso.
#
# Verificado antes de escribir estos dos tests que NINGUN llamador real del
# repo (grep de `known_content` fuera de tests: solo `work.py` y `wip.py`)
# usa `None` con el significado "esta ruta debe estar ausente" -- las dos
# unicas fuentes del contrato dicen "no se pudo leer, cae a leer tu", nunca
# "se espera ausente". No se encontro ningun otro significado legitimo de
# `None` en `known_content` en ningun documento de docs/memoria-v2/ ni en
# ningun otro llamador de produccion.
# ---------------------------------------------------------------------------


def test_write_work_with_known_content_none_for_untouched_existing_path_falls_back_to_disk_and_succeeds(
    notes, tmp_repo
):
    """Contrato de `work.py`/`wip.py` (lineas citadas arriba) contra la
    implementacion real de `write_work()`: si `known_content` trae `None`
    para una ruta que EXISTE y que NADIE MAS ha tocado, `write_work()` debe
    caer a su propia lectura de disco para esa ruta -- mismo comportamiento
    que sin `known_content` -- y el commit debe salir bien. Reproduce, con
    el repositorio git real del fixture, el repro exacto que trae el
    encargo: un solo proceso, sin ningun otro tocando nada, `ok: False` con
    un mensaje que culpa a un proceso que no existio.

    Nada mockeado: `write_work()` real, repo git real, lectura de disco
    real. El unico hecho fabricado es el contenido inicial del fichero, que
    el propio test escribe y nunca vuelve a tocar.
    """
    root = Path(tmp_repo)
    file_path = root / "known_content_none_existing.txt"
    file_path.write_text("MARK_KNOWN_NONE_EXISTING contenido que nadie mas toca", encoding="utf-8")

    _rc_before, before_count, _err_before = run_git(["rev-list", "--count", "HEAD"], tmp_repo)

    with _cwd(root):
        result = notes.write_work(
            "MARK_ROW_KNOWN_NONE un commit de trabajo normal",
            [file_path],
            None,
            known_content=[None],
        )

    assert result.ok, (
        "write_work() con known_content=[None] para una ruta que existe y no ha "
        "cambiado tiene que caer a su propia lectura de disco y comitear bien -- "
        "lo dicen, palabra por palabra, work.py (lineas 73-76) y wip.py (lineas "
        f"85-88). Resultado real: ok=False, git_error={result.git_error!r} -- "
        "un diagnostico que culpa a 'otro proceso' cuando en esta llamada, de un "
        "solo proceso, no hubo ningun otro"
    )

    _rc_after, after_count, _err_after = run_git(["rev-list", "--count", "HEAD"], tmp_repo)
    assert int(after_count) == int(before_count) + 1, (
        "write_work() dijo ok=True pero no se creo exactamente un commit nuevo"
    )

    _rc_show, content, _err_show = run_git(
        ["show", f"HEAD:{file_path.name}"], tmp_repo
    )
    assert content == "MARK_KNOWN_NONE_EXISTING contenido que nadie mas toca", (
        "el commit que write_work() dijo haber hecho no lleva el contenido real "
        f"del fichero -- HEAD:{file_path.name} es {content!r}"
    )


def test_write_work_with_directory_path_and_known_content_none_fails_clean_not_a_raw_traceback(
    notes, tmp_repo
):
    """Segunda mitad del mismo encargo: una ruta que es un DIRECTORIO (por
    ejemplo, `-- src/` en vez de un fichero, una errata facil) y que por
    tanto no se pudo leer como bytes (`path.read_bytes()` revienta con
    `IsADirectoryError`, capturado por el `except OSError` de work.py/
    wip.py, que anade `None` a `known_content` -- exactamente el mismo
    camino que el test de arriba). `_content_fingerprint()`
    (notes_commit.py lineas ~296-300) solo captura `FileNotFoundError`, asi
    que al comparar la huella de esa ruta contra el disco, `open(dir, 'rb')`
    lanza `IsADirectoryError` que NADIE captura dentro de `write_work()` --
    revienta hacia arriba en vez de volver un `WriteResult(ok=False, ...)`
    con causa.

    El contrato comun de los diez scripts (PIEZAS.md Sec.10) dice que
    ninguno imprime jamas una traza de pila; a nivel de esta funcion de
    biblioteca eso significa que `write_work()` no debe dejar escapar una
    excepcion sin capturar -- debe volver un fallo limpio, con su causa
    real, igual que hace ante cualquier otro fallo real de git en este
    mismo fichero de tests. El texto exacto de la causa no esta fijado por
    ningun documento citado en el encargo -- este test exige la CONDUCTA
    (fallo limpio, sin excepcion sin capturar), no un texto concreto.
    """
    root = Path(tmp_repo)
    dir_path = root / "known_content_none_directory"
    dir_path.mkdir()
    (dir_path / "inner.txt").write_text("contenido irrelevante", encoding="utf-8")

    try:
        with _cwd(root):
            result = notes.write_work(
                "MARK_ROW_KNOWN_NONE_DIR commit de trabajo con una ruta que es un directorio",
                [dir_path],
                None,
                known_content=[None],
            )
    except Exception as exc:  # noqa: BLE001 -- justo lo que este test prueba que NO debe pasar
        pytest.fail(
            f"write_work() dejo escapar {type(exc).__name__}: {exc} -- una ruta que "
            "es un directorio debe producir un fallo limpio (WriteResult con "
            "ok=False y una causa real), nunca una excepcion sin capturar que se "
            "convierte en traza de pila (PIEZAS.md Sec.10: ningun script de este "
            "sistema imprime jamas una traza de pila)"
        )

    assert result.ok is False, (
        "una ruta que es un directorio no puede comitearse como contenido de "
        "fichero -- se esperaba ok=False con causa, no un commit satisfactorio"
    )
    assert result.git_error, (
        "write_work() devolvio ok=False para la ruta-directorio pero sin causa en "
        "git_error -- fallar en silencio es el mismo defecto que el resto de este "
        "fichero de tests existe para prevenir"
    )


# ---------------------------------------------------------------------------
# Contrato en ROJO, tercera vuelta sobre el mismo punto (Cerberus, 2026-08-08):
# el punto 8 de `write_work()` (notes_commit.py ~489-527) detecta un commit
# que se llevo el contenido de otro escritor y lo deshace con
# `git reset --mixed HEAD~1` -- pero el propio arreglo tiene DOS agujeros que
# `hooks/customs.py` NO se toca aqui, y `lib/memory/` TAMPOCO -- Ultron
# arregla, esto solo fija el contrato:
#
#   1. El resultado del reset (linea ~602) se descarta entero -- si el
#      reset falla (repo sin HEAD~1, primer commit; o el indice ocupado por
#      otro proceso), el commit corrupto se queda como HEAD y la funcion
#      devuelve igual el texto fijo "Se deshizo el commit..." -- miente.
#   2. `HEAD~1` se resuelve EN EL MOMENTO del reset, no se fija al padre del
#      commit propio en cuanto ese commit se crea. El docstring lo justifica
#      con el candado global -- pero eso solo cubre a quien USA ese candado,
#      y `bin/release.py` no lo usa. Si otro proceso comitea de verdad entre
#      nuestro commit y esta verificacion, `HEAD~1` deja de ser nuestro
#      padre: pasa a ser nuestro PROPIO commit, y el reset borra el commit
#      legitimo del otro proceso.
#
# Los cuatro tests de aqui abajo comparan el HISTORIAL DE GIT REAL (nunca lo
# que `WriteResult`/`git_error` afirman) contra lo que estos deberian hacer.
# El desajuste de hash que dispara la rama del reset se fuerza sustituyendo
# `notes_commit._committed_blob_hash` -- tecnica de Cerberus, deterministica
# al 100%, nunca una carrera real de la que dependa el color del test.
# ---------------------------------------------------------------------------


def test_reset_failure_leaves_the_corrupt_commit_alive_and_names_it(
    notes, notes_commit, tmp_path, monkeypatch
):
    """Agujero 1: si el reset FALLA (repo sin padre -- el commit que
    `write_work()` acaba de crear es el PRIMERO del repositorio, no existe
    `HEAD~1`), el commit corrupto sigue siendo HEAD de verdad. La respuesta
    tiene que decirlo -- nombrar su identificador para poder arreglarlo a
    mano -- y NUNCA afirmar que se deshizo, porque no es verdad."""
    root = _empty_repo(tmp_path)
    target = root / "work.txt"
    content = b"MARK_RESET_FAILS contenido real que este escritor prepara\n"
    target.write_bytes(content)

    # Desajuste forzado, determinista -- nunca coincide con nada real.
    monkeypatch.setattr(
        notes_commit, "_committed_blob_hash", lambda path, root: "0" * 40
    )

    with _cwd(root):
        result = notes.write_work(
            "MARK_RESET_FAILS commit cuyo contenido no puede verificarse",
            [target],
            None,
            known_content=[content],
        )

    assert result.ok is False, "un desajuste de hash tiene que negarse a reportar exito"

    rc_head, corrupt_sha, err_head = run_git(["rev-parse", "HEAD"], str(root))
    assert rc_head == 0, f"git rev-parse HEAD fallo verificando el montaje: {err_head}"

    # El montaje es invalido si este commit SI tiene padre -- comprobado
    # con OTRO comando de solo lectura, nunca asumido: sin padre, ni
    # siquiera resuelve HEAD~1, que es exactamente lo que hace que el
    # 'git reset --mixed HEAD~1' interno de write_work() falle de verdad.
    rc_parent_probe, _out, err_parent_probe = run_git(["rev-parse", "HEAD~1"], str(root))
    assert rc_parent_probe != 0, (
        f"el montaje de la prueba es invalido: HEAD~1 SI resolvio en este "
        f"repo (deberia ser el primer commit, sin padre) -- {err_parent_probe!r}"
    )

    # La fuente de verdad es git, no lo que la funcion afirma.
    rc_head_final, head_final, _err = run_git(["rev-parse", "HEAD"], str(root))
    assert head_final == corrupt_sha, (
        f"el reset no puede haber funcionado (sin HEAD~1) -- HEAD tiene que "
        f"seguir siendo el commit corrupto {corrupt_sha!r}, salio {head_final!r}"
    )

    assert "se deshizo" not in (result.git_error or "").lower(), (
        f"el reset FALLA en un repo sin padre -- decir que 'se deshizo el "
        f"commit' cuando el reset fallo es mentira; git_error={result.git_error!r}"
    )
    assert corrupt_sha in (result.git_error or ""), (
        f"el reset fallo y el commit corrupto {corrupt_sha!r} sigue siendo "
        f"HEAD -- la respuesta tiene que nombrar su identificador para "
        f"poder arreglarlo a mano; git_error={result.git_error!r}"
    )


def test_reset_success_actually_removes_the_corrupt_commit_from_history(
    notes, notes_commit, tmp_repo, monkeypatch
):
    """Camino feliz del FALLO: cuando el reset SI puede funcionar (hay un
    padre real -- `tmp_repo` ya trae el commit `init`), el commit corrupto
    tiene que desaparecer de verdad del historial. Comprobado mirando el
    log real, no lo que `WriteResult` dice."""
    root = Path(tmp_repo)
    target = root / "work.txt"
    content = b"MARK_RESET_SUCCEEDS contenido real que este escritor prepara\n"
    target.write_bytes(content)

    rc_before, sha_before, err_before = run_git(["rev-parse", "HEAD"], str(root))
    assert rc_before == 0, f"git rev-parse HEAD fallo montando la prueba: {err_before}"

    monkeypatch.setattr(
        notes_commit, "_committed_blob_hash", lambda path, root: "0" * 40
    )

    with _cwd(root):
        result = notes.write_work(
            "MARK_RESET_SUCCEEDS commit cuyo contenido no puede verificarse",
            [target],
            None,
            known_content=[content],
        )

    assert result.ok is False, "un desajuste de hash tiene que negarse a reportar exito"

    rc_after, sha_after, err_after = run_git(["rev-parse", "HEAD"], str(root))
    assert rc_after == 0, f"git rev-parse HEAD fallo verificando: {err_after}"
    assert sha_after == sha_before, (
        f"HEAD~1 existia de verdad (el padre de antes de esta llamada, "
        f"{sha_before!r}) -- el reset tenia que funcionar y devolver HEAD "
        f"ahi, salio {sha_after!r}"
    )

    rc_log, log_out, err_log = run_git(["log", "--oneline", "--all"], str(root))
    assert rc_log == 0, f"git log fallo verificando: {err_log}"
    assert "MARK_RESET_SUCCEEDS" not in log_out, (
        f"el commit corrupto sigue apareciendo en el historial real tras un "
        f"reset que deberia haberlo quitado de verdad: {log_out!r}"
    )


def test_head_moved_by_another_process_leaves_history_untouched(
    notes, notes_commit, tmp_repo, monkeypatch
):
    """Agujero 2, el que puede destruir trabajo AJENO: si HEAD se mueve
    entre nuestro commit y esta verificacion (un `bin/release.py` real, que
    no toma el candado de `write_work()`, comitea de verdad justo ahi),
    `HEAD~1` en el momento del reset deja de ser el padre de NUESTRO
    commit -- pasa a ser nuestro propio commit, y el reset borraria el
    commit legitimo del otro proceso. La respuesta correcta: no tocar el
    historial en absoluto, y fallar con una causa que no diga que se
    deshizo nada (porque no se deshace nada).

    El commit ajeno se inyecta DETERMINISTICAMENTE desde dentro de
    `_committed_blob_hash` (la funcion que write_work() llama justo
    despues de comitear lo suyo, para verificar) -- nunca dos hilos ni
    ningun timing real del que dependa el color de este test.
    """
    root = Path(tmp_repo)
    target = root / "work.txt"
    content = b"MARK_HEAD_MOVED contenido real que este escritor prepara\n"
    target.write_bytes(content)

    foreign_sha_holder = {}

    def _fake_committed_blob_hash(path, repo_root):
        if "sha" not in foreign_sha_holder:
            rc_foreign, _out, err_foreign = run_git(
                ["commit", "--allow-empty", "-m", "MARK_FOREIGN_RELEASE_COMMIT"],
                str(repo_root),
            )
            assert rc_foreign == 0, f"commit ajeno de montaje fallo: {err_foreign}"
            rc_sha, sha, err_sha = run_git(["rev-parse", "HEAD"], str(repo_root))
            assert rc_sha == 0, f"git rev-parse HEAD fallo montando el commit ajeno: {err_sha}"
            foreign_sha_holder["sha"] = sha
        # Fuerza el desajuste igualmente -- sin esto no se entra ni en la
        # rama que intenta el reset.
        return "0" * 40

    monkeypatch.setattr(notes_commit, "_committed_blob_hash", _fake_committed_blob_hash)

    with _cwd(root):
        result = notes.write_work(
            "MARK_HEAD_MOVED commit cuyo padre deja de ser el nuestro a mitad de la verificacion",
            [target],
            None,
            known_content=[content],
        )

    assert result.ok is False, "un desajuste de hash tiene que negarse a reportar exito"

    foreign_sha = foreign_sha_holder.get("sha")
    assert foreign_sha, "el montaje de la prueba es invalido: el commit ajeno nunca se creo"

    rc_head, head_after, err_head = run_git(["rev-parse", "HEAD"], str(root))
    assert rc_head == 0, f"git rev-parse HEAD fallo verificando: {err_head}"
    assert head_after == foreign_sha, (
        f"HEAD se movio por otro proceso ANTES de esta verificacion -- el "
        f"reset no puede tocar el historial en ese caso: el commit legitimo "
        f"del otro proceso ({foreign_sha!r}) tiene que seguir siendo HEAD, "
        f"salio {head_after!r} -- si es distinto, el reset se comio el "
        f"commit ajeno"
    )

    rc_log, log_out, err_log = run_git(["log", "--oneline", "--all"], str(root))
    assert rc_log == 0, f"git log fallo verificando: {err_log}"
    assert "MARK_FOREIGN_RELEASE_COMMIT" in log_out, (
        f"el commit ajeno desaparecio del historial -- exactamente el fallo "
        f"que este contrato existe para impedir: {log_out!r}"
    )

    assert "se deshizo" not in (result.git_error or "").lower(), (
        f"con el historial sin tocar, la respuesta no puede afirmar que se "
        f"deshizo un commit -- nada se deshizo; git_error={result.git_error!r}"
    )
    assert result.git_error, (
        "un fallo tan serio como este (pudo haber borrado trabajo ajeno) "
        f"tiene que devolver una causa, no quedarse callado: {result!r}"
    )


def test_matching_content_undoes_nothing(notes, notes_commit, tmp_repo):
    """El camino feliz de los cuatro: cuando el contenido comiteado SI
    coincide con el que este escritor tenia en la mano, no hay ningun
    desajuste que verificar -- no se toca el reset en absoluto, y el
    commit se queda tal cual. Sin ningun monkeypatch: `_committed_blob_hash`
    real, `_git_blob_hash_of_bytes` real, los dos calculando el MISMO hash
    para el MISMO contenido."""
    root = Path(tmp_repo)
    target = root / "work.txt"
    content = b"MARK_HAPPY_PATH contenido real que este escritor prepara\n"
    target.write_bytes(content)

    rc_before, count_before, err_before = run_git(["rev-list", "--count", "HEAD"], str(root))
    assert rc_before == 0, f"git rev-list fallo montando la prueba: {err_before}"

    with _cwd(root):
        result = notes.write_work(
            "MARK_HAPPY_PATH commit cuyo contenido SI coincide",
            [target],
            None,
            known_content=[content],
        )

    assert result.ok is True, f"contenido coincidente tiene que dar ok=True: {result.git_error}"

    rc_after, count_after, err_after = run_git(["rev-list", "--count", "HEAD"], str(root))
    assert rc_after == 0, f"git rev-list fallo verificando: {err_after}"
    assert int(count_after) == int(count_before) + 1, (
        f"se esperaba exactamente un commit nuevo, nada deshecho: antes "
        f"{count_before!r} commits, despues {count_after!r}"
    )

    rc_log, log_out, err_log = run_git(["log", "--oneline", "-1"], str(root))
    assert rc_log == 0, f"git log fallo verificando: {err_log}"
    assert "MARK_HAPPY_PATH" in log_out, (
        f"el commit del camino feliz tiene que seguir siendo HEAD, nada se "
        f"deshizo: {log_out!r}"
    )


# ---------------------------------------------------------------------------
# Contrato, CUARTA vuelta sobre el mismo punto (Cerberus, 2026-08-08,
# reproducido en vivo con `prove_hole4.py` -- ver
# /private/tmp/claude-501/-Users-unmassk-Workspace-claude-toolkit/
# 14757cf4-3930-4b7a-a25b-7688c36efc7a/scratchpad/prove_hole4.py, usado
# como punto de partida de la tecnica de aqui abajo). El punto 9 de
# `write_work()` (notes_commit.py ~702-750, version original) ya cerraba
# el agujero de la vuelta anterior comprobando `HEAD` ANTES de intentar el
# reset -- pero quedaban dos huecos MAS ESTRECHOS en el mismo patron
# (check-then-act, nunca del todo atomico), y un tercero de calidad del
# mensaje. Los tres se documentaron aqui como agujeros 4/5/6.
#
# QUINTA vuelta (Ultron, 2026-08-08, MISMO DIA): reescribio el mecanismo
# entero -- ya no es "comprobar y luego actuar" en ningun punto:
#
#   - `own_commit_sha` ya NO se lee con un `git rev-parse HEAD` en un
#     subproceso posterior (lo que el agujero 5 explotaba) -- se lee de la
#     PRIMERA LINEA de la salida del propio `git commit`
#     (`_own_commit_sha_from_commit_output()`), la MISMA llamada que crea
#     el commit, sin ningun subproceso adicional de por medio. El sha
#     corto de esa linea se expande a 40 caracteres con
#     `git rev-parse <corto>^{commit}` -- busqueda por CONTENIDO (el
#     objeto ya existe bajo ese hash), nunca por REFERENCIA -- un commit
#     ajeno que aterrice justo ahi no cambia a que apunta un hash de
#     contenido que ya existe.
#   - El padre se resuelve con `git rev-parse <own_commit_sha>~1` --
#     tambien por CONTENIDO, no por `HEAD~1` (referencia viva).
#   - Deshacer es una UNICA llamada atomica:
#     `git update-ref -m <razon> HEAD <padre> <own_commit_sha>` --
#     comparar-y-cambiar bajo el candado de referencias del propio git:
#     mueve `HEAD` a `<padre>` SOLO SI su valor actual es, exactamente,
#     `own_commit_sha`. Mirar y actuar son el MISMO acto, sin hueco entre
#     medias en el que un proceso ajeno pueda colarse.
#
# Consecuencia para los tests de aqui abajo, verificada ejecutandolos
# contra el codigo nuevo ANTES de tocar nada (regla de esta tarea:
# "averiguarlo antes de tocar nada"): los ganchos de los agujeros 4 y 5
# filtraban por la forma EXACTA de comandos que ya no existen
# (`["reset", "--mixed", "HEAD~1"]` y `["rev-parse", "HEAD"]` a secas) --
# no intervienen nunca, y la propia asercion de montaje de cada test
# ("el commit ajeno nunca se creo") es la que fallaba, no el mecanismo de
# `write_work()`. El test del agujero 6 (el mensaje nombra el commit
# corrupto) SI paso limpio sin tocarlo -- el mismo commit que reescribio el
# mecanismo ya incluye `own_commit_sha` en el mensaje de la rama de
# comparar-y-cambiar fallido.
#
# Reapuntados, no reescritos desde cero -- misma propiedad bajo prueba en
# los dos, misma tecnica de Cerberus (inyectar un commit ajeno real
# interceptando `gitcmd.run`), solo cambia DONDE se engancha el gancho:
#
#   4 (REAPUNTADO). El instante peligroso equivalente ya no es un reset
#      que resuelve una referencia viva -- es la propia llamada a
#      `update-ref`. El test intercepta esa llamada por su SUBCOMANDO
#      (`args[0] == "update-ref"`), nunca por sus argumentos completos
#      (que incluyen SHAs impredecibles y un texto de mensaje que puede
#      cambiar) -- exactamente la leccion de esta vuelta: atarse a la
#      forma exacta del comando es lo que acaba de romperse. Las
#      aserciones siguen siendo sobre la PROPIEDAD (el commit ajeno sigue
#      en el log, HEAD sigue siendo el suyo, el mensaje no miente) -- ni
#      una sola asercion sobre que argumentos exactos llevo el comando.
#      Ahora pasa limpio: es la prueba viva de que el CAS atomico protege
#      donde el check-then-act anterior no podia.
#
#   5 (RETIRADO). El hueco que probaba -- un commit ajeno envenenando
#      `own_commit_sha` ANTES de que se lea -- ya no puede existir: la
#      lectura ya no es un subproceso separado que pueda perder una
#      carrera, es la salida del PROPIO `git commit` (ya en memoria, sin
#      ningun subproceso de por medio que un commit ajeno pudiera ganar) y
#      una expansion corta->completa que busca por CONTENIDO, no por
#      referencia -- un commit ajeno no puede cambiar a que apunta un hash
#      ya existente. Intentar reapuntar este test habria significado
#      interceptar la llamada de expansion (`rev-parse <corto>^{commit}`)
#      e inyectar un commit ajeno ahi -- probado mentalmente (y coincide
#      con el propio razonamiento del docstring de
#      `_own_commit_sha_from_commit_output`): el resultado de esa consulta
#      no cambia pase lo que pase, porque no depende de ninguna referencia
#      que se pueda mover, solo de que el objeto exista. Un test asi
#      pasaria SIEMPRE, no por construccion correcta sino porque no hay
#      forma real de hacerlo fallar -- verde que no protege nada. Se
#      retira en vez de dejarlo así; su nombre y motivo quedan aqui por si
#      la mecanica vuelve a cambiar y hace falta reabrirlo.
#
#   6 (SIN CAMBIOS, sigue verde). No se toca -- ya prueba lo que tiene que
#      probar contra el codigo nuevo sin ningun ajuste.
#
# NUEVO (respuesta a la pregunta explicita de esta vuelta -- "¿y si HEAD no
# es una rama sino un estado suelto?"): `git update-ref HEAD <viejo>
# <nuevo>` resuelve `HEAD` de forma transparente tanto si es una referencia
# simbolica a una rama (caso normal) como si es un estado suelto (un SHA
# directo, sin rama) -- no es una suposicion de este fichero, es
# comportamiento documentado de `update-ref`. Verificado en vivo, no solo
# leido: `test_foreign_commit_landing_right_before_the_update_ref_call_
# survives_in_detached_head_too` monta un repo en HEAD SUELTO (`git
# checkout --detach`) y repite el mismo ataque -- si esta suposicion fuera
# falsa, este test fallaria exactamente igual que el agujero 4 original.
# Pasa limpio: la proteccion generaliza.
#
# La otra pregunta explicita ("¿y si el commit ajeno aterriza entre el
# 'git commit' y la lectura de su salida?") no tiene test dedicado: esa
# lectura no es un subproceso, es una cadena Python ya en memoria
# (`git_result.stdout`, capturada por el MISMO `subprocess.run` que crea
# el commit) -- no hay ningun subproceso adicional ahi en el que un commit
# ajeno pudiera intercalarse. No se fabrica un test para una ventana que
# no existe (mismo criterio que el agujero 5, arriba).
# ---------------------------------------------------------------------------


def test_foreign_commit_landing_right_before_the_update_ref_call_does_not_lose_it(
    notes, notes_commit, gitcmd_mod, tmp_repo, monkeypatch
):
    """Agujero 4, REAPUNTADO (2026-08-08, misma vuelta): el instante
    peligroso equivalente ya no es un reset que resuelve 'HEAD~1' como
    referencia viva -- es la propia llamada de comparar-y-cambiar
    (`git update-ref HEAD <padre> <own_commit_sha>`). Prueba la PROPIEDAD,
    no el comando: un commit ajeno real que aterriza en el peor instante
    posible (justo antes de esa llamada) no se pierde, y lo que
    `write_work()` devuelve dice la verdad. El gancho intercepta por
    SUBCOMANDO (`update-ref`), nunca por la lista completa de argumentos
    -- esos llevan SHAs y un texto que pueden cambiar sin que la propiedad
    bajo prueba cambie."""
    root = Path(tmp_repo)
    target = root / "work.txt"
    content = b"MARK_HOLE4 contenido real que este escritor prepara\n"
    target.write_bytes(content)

    monkeypatch.setattr(
        notes_commit, "_committed_blob_hash", lambda path, root: "0" * 40
    )

    real_run = gitcmd_mod.run
    foreign_sha_holder = {}

    def _patched_run(args, cwd, timeout, env=None):
        if args and args[0] == "update-ref":
            # El peor caso posible: el proceso ajeno aterriza justo antes
            # de que el propio comparar-y-cambiar se ejecute.
            rc, _out, err = run_git(
                ["commit", "--allow-empty", "-m", "MARK_FOREIGN_RELEASE_COMMIT_HOLE4"],
                str(cwd),
            )
            assert rc == 0, f"commit ajeno de montaje fallo: {err}"
            rc2, sha, err2 = run_git(["rev-parse", "HEAD"], str(cwd))
            assert rc2 == 0, err2
            foreign_sha_holder["sha"] = sha
        return real_run(args, cwd, timeout, env)

    monkeypatch.setattr(gitcmd_mod, "run", _patched_run)

    with _cwd(root):
        result = notes.write_work(
            "MARK_HOLE4 commit cuyo padre puede dejar de ser el nuestro justo antes del update-ref",
            [target],
            None,
            known_content=[content],
        )

    assert result.ok is False, "un desajuste de hash tiene que negarse a reportar exito"

    foreign_sha = foreign_sha_holder.get("sha")
    assert foreign_sha, "el montaje de la prueba es invalido: el commit ajeno nunca se creo"

    rc_head, head_after, err_head = run_git(["rev-parse", "HEAD"], str(root))
    assert rc_head == 0, f"git rev-parse HEAD fallo verificando: {err_head}"
    assert head_after == foreign_sha, (
        f"el commit ajeno aterrizo justo antes de la llamada real de "
        f"comparar-y-cambiar -- el historial ajeno no se puede tocar: "
        f"HEAD tiene que seguir siendo {foreign_sha!r}, salio {head_after!r}"
    )

    rc_log, log_out, err_log = run_git(["log", "--oneline", "--all"], str(root))
    assert rc_log == 0, f"git log fallo verificando: {err_log}"
    assert "MARK_FOREIGN_RELEASE_COMMIT_HOLE4" in log_out, (
        f"el commit ajeno desaparecio del historial -- exactamente el "
        f"fallo que este contrato existe para impedir: {log_out!r}"
    )

    assert "se deshizo" not in (result.git_error or "").lower(), (
        f"si el comparar-y-cambiar se hubiera comido el commit ajeno, la "
        f"respuesta no podria afirmar sin mas que 'se deshizo el commit' "
        f"como si todo hubiera ido segun lo esperado; "
        f"git_error={result.git_error!r}"
    )


def test_foreign_commit_landing_right_before_the_update_ref_call_survives_in_detached_head_too(
    notes, notes_commit, gitcmd_mod, tmp_repo, monkeypatch
):
    """Respuesta EMPIRICA a la segunda pregunta explicita de esta vuelta:
    '¿y si HEAD no es una rama sino un estado suelto?'. Mismo ataque que
    el test de arriba, mismo gancho, unica diferencia: el repo se pone en
    HEAD SUELTO (`git checkout --detach`) antes de escribir nada. Si
    `git update-ref HEAD <padre> <own_commit_sha>` no resolviera HEAD
    igual de bien en este estado, el commit ajeno se perderia exactamente
    igual que en el agujero 4 original -- este test fallaria con la misma
    forma. No es una suposicion leida del docstring: es la misma prueba
    de fuego, en el otro estado posible de HEAD."""
    root = Path(tmp_repo)

    rc_detach, _out, err_detach = run_git(["checkout", "--detach", "HEAD"], str(root))
    assert rc_detach == 0, f"el montaje es invalido: no se pudo soltar HEAD: {err_detach}"
    rc_symbolic, symbolic_out, _err = run_git(["symbolic-ref", "-q", "HEAD"], str(root))
    assert rc_symbolic != 0 and not symbolic_out, (
        f"el montaje es invalido: HEAD sigue siendo una referencia "
        f"simbolica tras el checkout --detach -- symbolic-ref devolvio "
        f"rc={rc_symbolic!r} out={symbolic_out!r}"
    )

    target = root / "work.txt"
    content = b"MARK_HOLE4_DETACHED contenido real que este escritor prepara\n"
    target.write_bytes(content)

    monkeypatch.setattr(
        notes_commit, "_committed_blob_hash", lambda path, root: "0" * 40
    )

    real_run = gitcmd_mod.run
    foreign_sha_holder = {}

    def _patched_run(args, cwd, timeout, env=None):
        if args and args[0] == "update-ref":
            rc, _out, err = run_git(
                ["commit", "--allow-empty", "-m", "MARK_FOREIGN_RELEASE_COMMIT_HOLE4_DETACHED"],
                str(cwd),
            )
            assert rc == 0, f"commit ajeno de montaje fallo: {err}"
            rc2, sha, err2 = run_git(["rev-parse", "HEAD"], str(cwd))
            assert rc2 == 0, err2
            foreign_sha_holder["sha"] = sha
        return real_run(args, cwd, timeout, env)

    monkeypatch.setattr(gitcmd_mod, "run", _patched_run)

    with _cwd(root):
        result = notes.write_work(
            "MARK_HOLE4_DETACHED commit cuyo padre puede dejar de ser el nuestro en HEAD suelto",
            [target],
            None,
            known_content=[content],
        )

    assert result.ok is False, "un desajuste de hash tiene que negarse a reportar exito"

    foreign_sha = foreign_sha_holder.get("sha")
    assert foreign_sha, "el montaje de la prueba es invalido: el commit ajeno nunca se creo"

    rc_head, head_after, err_head = run_git(["rev-parse", "HEAD"], str(root))
    assert rc_head == 0, f"git rev-parse HEAD fallo verificando: {err_head}"
    assert head_after == foreign_sha, (
        f"con HEAD suelto, el commit ajeno aterrizo justo antes del "
        f"comparar-y-cambiar -- el historial ajeno no se puede tocar: "
        f"HEAD tiene que seguir siendo {foreign_sha!r}, salio {head_after!r}"
    )

    rc_log, log_out, err_log = run_git(["log", "--oneline", "--all"], str(root))
    assert rc_log == 0, f"git log fallo verificando: {err_log}"
    assert "MARK_FOREIGN_RELEASE_COMMIT_HOLE4_DETACHED" in log_out, (
        f"el commit ajeno desaparecio del historial con HEAD suelto -- "
        f"exactamente el fallo que este contrato existe para impedir: "
        f"{log_out!r}"
    )


# ---------------------------------------------------------------------------
# RETIRADO (agujero 5), 2026-08-08 -- ver el bloque de comentarios grande
# de mas arriba para el razonamiento completo. Nombre que tenia este test:
# `test_foreign_commit_landing_before_own_commit_sha_capture_does_not_
# produce_a_false_all_clear`. Probaba que un commit ajeno aterrizando
# ANTES de que `own_commit_sha` se leyera podia envenenar esa lectura
# desde el origen -- valido contra el codigo de la vuelta anterior, donde
# esa lectura era un `git rev-parse HEAD` en un subproceso separado (una
# referencia VIVA, que un commit ajeno si podia mover antes de que el
# subproceso arrancara).
#
# La reescritura de Ultron (misma vuelta, mismo dia) elimina esa lectura
# por completo: `own_commit_sha` sale ahora de la PRIMERA LINEA de la
# salida del propio `git commit` (`_own_commit_sha_from_commit_output()`,
# notes_commit.py) -- ya en memoria, sin ningun subproceso adicional en el
# que un commit ajeno pudiera ganar la carrera -- y el sha corto de esa
# linea se expande a 40 caracteres con `git rev-parse <corto>^{commit}`,
# una busqueda por CONTENIDO: el objeto ya existe bajo ese hash, y ningun
# commit ajeno que aterrice despues cambia a que apunta un hash que ya
# existe.
#
# Reapuntar este test habria significado interceptar esa llamada de
# expansion e inyectar ahi un commit ajeno -- pero su resultado no puede
# cambiar por eso: no depende de ninguna referencia movible, solo de que
# el objeto ya exista en la base de datos de git. Un test asi pasaria
# SIEMPRE, no porque el mecanismo lo proteja sino porque no hay forma real
# de hacerlo fallar -- verde por construccion, que es exactamente lo que
# esta obra pide no dejar pasar ("un test que no puede fallar no protege
# nada"). Se retira con el motivo escrito en vez de forzar un montaje
# artificial.


def test_head_moved_message_names_the_corrupt_commit_identifier(
    notes, notes_commit, tmp_repo, monkeypatch
):
    """Agujero 6, de calidad del mensaje, no de historial: cuando el punto
    9 SI detecta que el historial se movio y se niega a tocar nada (rama
    de notes_commit.py ~712-724), esa rama nunca nombra el identificador
    del commit corrupto (`own_commit_sha`) -- a diferencia de su rama
    hermana, "el reset fallo" (~727-739), que si lo hace. Sin el
    identificador, el commit corrupto queda vivo en el historial sin
    ninguna pista de cual es -- justo la rama donde mas falta hace, porque
    aqui el commit corrupto SIGUE siendo HEAD (nada se deshizo)."""
    root = Path(tmp_repo)
    target = root / "work.txt"
    content = b"MARK_HOLE6 contenido real que este escritor prepara\n"
    target.write_bytes(content)

    captured = {}

    def _fake_committed_blob_hash(path, repo_root):
        if "own_sha" not in captured:
            rc_own, own_sha, err_own = run_git(["rev-parse", "HEAD"], str(repo_root))
            assert rc_own == 0, f"rev-parse de montaje fallo: {err_own}"
            captured["own_sha"] = own_sha
            rc_foreign, _out, err_foreign = run_git(
                ["commit", "--allow-empty", "-m", "MARK_FOREIGN_RELEASE_COMMIT_HOLE6"],
                str(repo_root),
            )
            assert rc_foreign == 0, f"commit ajeno de montaje fallo: {err_foreign}"
        return "0" * 40

    monkeypatch.setattr(notes_commit, "_committed_blob_hash", _fake_committed_blob_hash)

    with _cwd(root):
        result = notes.write_work(
            "MARK_HOLE6 commit corrupto cuyo identificador tiene que quedar nombrado",
            [target],
            None,
            known_content=[content],
        )

    assert result.ok is False, "un desajuste de hash tiene que negarse a reportar exito"

    own_sha = captured.get("own_sha")
    assert own_sha, "el montaje de la prueba es invalido: own_sha nunca se capturo"

    assert own_sha in (result.git_error or ""), (
        f"con el historial movido y nada deshecho, el commit corrupto "
        f"{own_sha!r} SIGUE siendo HEAD -- la respuesta tiene que nombrar "
        f"su identificador para poder arreglarlo a mano, igual que ya "
        f"hace la rama hermana del reset fallido; git_error={result.git_error!r}"
    )
