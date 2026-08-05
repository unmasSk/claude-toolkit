"""Contrato ROJO de `bin/memory/boot.py` -- PIEZAS.md Sec.10 (fila
`boot.py`).

`bin/memory/boot.py` NO EXISTE TODAVIA. Modo test-first, pase de
CONTRATO: aceptacion, no barrido exhaustivo.

**No confundir con `tests/memory/test_boot.py`** (contrato de
`lib/memory/boot.py::build`/`render`, ya en produccion): este fichero
prueba el SCRIPT como proceso -- nunca importa `boot.build`/`boot.render`
para probarlas, solo las usa como PRODUCTOR REAL con el que comparar la
salida del proceso (round trip, unmassk-standards Sec.34).

De donde sale cada cosa:

- PIEZAS.md Sec.10, fila `boot.py`: llama a `boot.build` + `boot.render`;
  no admite argumentos; imprime "el menu del dia".
- Encargo explicito de esta tarea: **"en un proyecto recien instalado
  tiene que funcionar -- hoy ya se han cazado dos formas distintas de
  que reventara ahi, asi que fijalo desde el principio"**. Las dos formas
  ya reparadas del lado de produccion, verificadas leyendo el codigo
  antes de escribir este contrato:
  1. `indexes.archived_ids()`/`_current_index_lines()` tratan un indice o
     `ARCHIVED.md` ausentes como CERO, nunca como `FileNotFoundError`
     [indexes.py, health.py, docstrings "Revision 2026-08-02"].
  2. `query.run_git_log()`/`is_unborn_branch()` tratan una rama SIN NINGUN
     commit todavia como estado valido (cadena vacia), nunca como el
     fallo real de la rama de abajo [query.py, "hallazgo 2 de Moriarty,
     ronda 2"].
  Los dos se prueban aqui contra el SCRIPT (no contra la libreria, que ya
  los prueba en su propio contrato) -- fila 1 con un repo con un solo
  commit inicial y nada de `.claude/project-memory/` (la fixture
  `tmp_repo` normal), fila 2 con un repo `git init` SIN NINGUN commit,
  el caso mas extremo de "recien instalado".

Round trip real, sin fabricar el texto esperado (unmassk-standards Sec.34):
el texto exacto que `boot.py` tiene que imprimir sale de llamar en el
MISMO proceso de test a `boot.build()` + `boot.render()` (las piezas
REALES, ya en produccion) contra el mismo repositorio, normalizando la
unica parte que varia entre las dos llamadas por diseno (las etiquetas
` UTC`, cada llamada usa `datetime.now()` por separado).

Siembra de datos real: via `note.py`/`context.py` como PROCESO
(`seed_note_via_script`, `conftest.py`) -- los dos ya existen y estan en
verde.

Con el script inexistente, todos estos tests fallan hoy por la misma
causa real: `python3 <ruta inexistente>` -- ver docstring de
`test_note_script.py` para el detalle del mensaje.
"""

import contextlib
import os
import re
from datetime import date

import pytest

from .conftest import (
    import_lib_memory_module,
    run_git,
    run_memory_script,
    seed_note_via_script,
    seed_zones_json,
)

_UTC_LABEL_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")


def _normalize_timestamps(text):
    return _UTC_LABEL_RE.sub("<UTC>", text)


@pytest.fixture
def boot_lib():
    return import_lib_memory_module("boot")


@contextlib.contextmanager
def _cwd(path):
    """Mismo helper que en `test_notes.py`/`test_context_script.py`."""
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _build_expected(repo, boot_lib):
    with _cwd(repo):
        return boot_lib.render(boot_lib.build())


def _report_of(repo):
    """El informe REAL que dejo `boot.py`: desde 2026-08-05 el arranque
    escribe un fichero y por pantalla solo deja donde esta [decision del
    propietario: "no se le puede inyectar, se tiene que crear el archivo
    y el lo lee"]. Comparar contra su stdout compararia contra el
    puntero, no contra el informe."""
    from pathlib import Path

    return Path(repo, ".claude", ".unmassk", "boot-latest.txt").read_text(
        encoding="utf-8"
    )


class TestFreshlyInstalledProjectWorks:
    """Encargo explicito: "en un proyecto recien instalado tiene que
    funcionar". Repo con UN commit inicial (fixture `tmp_repo`), sin
    `.claude/project-memory/` en absoluto -- ni `zones.json`, ni
    `config.json`, ni un solo indice, ni `ARCHIVED.md`."""

    def test_boot_on_a_project_with_one_commit_and_no_memory_yet(self, tmp_repo, boot_lib):
        rc, out, err = run_memory_script("boot.py", [], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        expected = _build_expected(tmp_repo, boot_lib)
        assert _normalize_timestamps(_report_of(tmp_repo).rstrip("\n")) == _normalize_timestamps(expected), (
            "boot.py no reproduce byte a byte lo que construyen boot.build()+"
            "boot.render() reales -- ¿reimplementa su propio pintado?"
        )


class TestUnbornBranchProjectWorks:
    """El caso MAS extremo de "recien instalado": `git init` sin un solo
    commit todavia -- ni siquiera el inicial que trae `tmp_repo`. Prueba
    directa de la segunda de las "dos formas" que el encargo pide fijar
    (`is_unborn_branch`, `query.py`)."""

    def test_boot_on_a_repo_with_zero_commits(self, tmp_path, boot_lib):
        repo = tmp_path / "unborn"
        repo.mkdir()
        rc_init, _out_init, err_init = run_git(["init"], str(repo))
        assert rc_init == 0, f"git init fallo en el test: {err_init}"

        rc, out, err = run_memory_script("boot.py", [], cwd=str(repo))
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        expected = _build_expected(str(repo), boot_lib)
        assert _normalize_timestamps(_report_of(str(repo)).rstrip("\n")) == _normalize_timestamps(expected)


class TestRealContentMatchesTheRealProducerRoundTrip:
    """Con contenido real (bloqueantes, restricciones, un cierre de
    sesion) -- el mismo round trip que arriba, contra un proyecto que ya
    no esta vacio. Prueba tambien la fila "restricciones/bloqueantes sin
    tope" indirectamente: si `boot.py` recortara algo, dejaria de
    coincidir con `boot.render(boot.build())`, que no recorta nada."""

    def test_blockers_restrictions_and_context_all_present_in_the_real_render(
        self, tmp_repo, boot_lib
    ):
        seed_zones_json(tmp_repo, ["auth", "product", "deploy", "infra"])
        rc_b, out_b, err_b = seed_note_via_script(
            tmp_repo, "B", "product", "auth",
            "google workspace admin consent still pending",
            description="MARK description", awaits="el cliente (Marta, IT)",
        )
        assert rc_b == 0, f"siembra fallo: stdout={out_b!r} stderr={err_b!r}"

        rc_r, out_r, err_r = seed_note_via_script(
            tmp_repo, "R", "deploy", "infra",
            "no auth deploy on Friday without a tested rollback",
            why="viernes sin vuelta atras ensayada", description="MARK description",
            stops="yes",
        )
        assert rc_r == 0, f"siembra fallo: stdout={out_r!r} stderr={err_r!r}"

        rc_ctx, out_ctx, err_ctx = run_memory_script(
            "next.py",
            [
                "implement discussed changes to close-session skill",
                "--context", "Revisado el diseno del checkpoint",
            ],
            cwd=tmp_repo,
        )
        assert rc_ctx == 0, f"cierre de contexto fallo: stdout={out_ctx!r} stderr={err_ctx!r}"

        rc, out, err = run_memory_script("boot.py", [], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        expected = _build_expected(tmp_repo, boot_lib)
        assert _normalize_timestamps(_report_of(tmp_repo).rstrip("\n")) == _normalize_timestamps(expected)


class TestForceUtf8StreamsFirstStatement:
    def test_boot_survives_a_restricted_console_encoding(self, tmp_repo):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "auth", "product", "decision con acentos: sesión, código",
            description="MARK description", stops="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        rc, out, err = run_memory_script(
            "boot.py", [], cwd=tmp_repo,
            env={"PYTHONIOENCODING": "cp1252", "LANG": "C", "LC_ALL": "C"},
        )
        combined = out + err
        assert "UnicodeEncodeError" not in combined
        assert "UnicodeDecodeError" not in combined
        assert "Traceback" not in combined
        assert rc == 0, f"el arranque no deberia fallar bajo cp1252: {combined!r}"


class TestRepoResolvedByProcessCwd:
    def test_launched_from_a_nested_subdirectory_reads_that_same_repo(self, tmp_repo, boot_lib):
        nested = os.path.join(tmp_repo, "src", "some", "nested", "place")
        os.makedirs(nested, exist_ok=True)

        rc, out, err = run_memory_script("boot.py", [], cwd=nested)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        expected = _build_expected(tmp_repo, boot_lib)
        assert _normalize_timestamps(_report_of(tmp_repo).rstrip("\n")) == _normalize_timestamps(expected), (
            "el arranque no coincide con el del repo -- ¿resuelve por una ruta fija?"
        )


# ---------------------------------------------------------------------------
# Regresion (2026-08-04, hallazgo de Moriarty, reparado el mismo dia en
# `health.py::coherence()`): un id archivado que no existe en ningun commit
# real de git no se cruzaba contra git -- solo se usaba para DESCONTAR de
# "falta en el indice". El arranque pintaba "✓ indexes match git" con
# numeros que ni siquiera sumaban. Se prueba aqui contra el SCRIPT real,
# metiendo una entrada fantasma DIRECTAMENTE en ARCHIVED.md (con el
# escritor real, `indexes.archive()`, nunca fabricando texto a mano) sin
# que ninguna nota con ese id haya existido jamas en git.
# ---------------------------------------------------------------------------


@pytest.fixture
def indexes_lib():
    return import_lib_memory_module("indexes")


@pytest.fixture
def model_lib():
    return import_lib_memory_module("model")


@pytest.fixture
def notes_lib():
    return import_lib_memory_module("notes")


class TestArchivedPhantomEntryIsShownAsAWarningNotAFalseGreen:
    def test_a_ghost_archived_id_unknown_to_git_makes_boot_warn_and_name_it(
        self, tmp_repo, boot_lib, indexes_lib, model_lib, notes_lib
    ):
        pm = notes_lib.pm_root(tmp_repo)
        indexes_lib.seed(pm)

        phantom_id = "I-999"
        indexes_lib.archive(
            model_lib.ArchiveLine(
                date=date(2026, 8, 4),
                type="I",
                id=phantom_id,
                zone1="product",
                zone2="bootTest",
                headline="MARK_PHANTOM entrada que nunca existio en git",
                destination="closed",
                destination_detail="MARK_PHANTOM_DETAIL nunca hubo commit real",
            ),
            pm,
        )

        rc, out, err = run_memory_script("boot.py", [], cwd=tmp_repo)
        assert rc == 0, f"un indice corrupto no puede tumbar el arranque: stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        out = _report_of(tmp_repo)
        assert "✓  indexes match git" not in out, (
            f"con un archivado fantasma, el arranque no puede salir con un visto "
            f"bueno falso: {out!r}"
        )
        assert "⚠️  indexes do not match git" in out, (
            f"el arranque tiene que avisar, no callar, con un archivado fantasma: {out!r}"
        )
        assert f"{phantom_id}: archivado pero no existe en git" in out, (
            f"el aviso tiene que NOMBRAR el identificador fantasma, no solo los "
            f"numeros: {out!r}"
        )

        expected = _build_expected(tmp_repo, boot_lib)
        assert _normalize_timestamps(_report_of(tmp_repo).rstrip("\n")) == _normalize_timestamps(expected), (
            "boot.py no reproduce byte a byte lo que construyen boot.build()+"
            "boot.render() reales"
        )
