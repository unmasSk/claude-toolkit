"""Contrato ROJO de `bin/memory/rezones.py` -- PIEZAS.md Sec.10 (fila
`rezones.py`).

`bin/memory/rezones.py` NO EXISTE TODAVIA. Modo test-first, pase de
CONTRATO: aceptacion, no barrido exhaustivo.

De donde sale cada cosa:

- PIEZAS.md Sec.10, fila `rezones.py`: llama a `indexes` + `health`;
  admite `--verify` (solo diagnostica); imprime "que diverge, o que se
  reconstruyo".
- PIEZAS.md Sec.9.4, "Quien lo llama": `bin/memory/rezones.py --verify`
  llama a `health.coherence(root)` -- ya en produccion. "Sus tests", fila
  1: "Borrar una linea de un indice a mano se reporta como «falta en
  indice»" -- exactamente el escenario de esta tarea.
- Encargo explicito de esta tarea: "corrompe un indice, comprueba que el
  modo de diagnostico lo dice SIN TOCAR NADA, que la reconstruccion lo
  ARREGLA, y que el resultado es IDENTICO al que habia -- esa igualdad es
  la prueba de que reconstruir no inventa".

Round trip real, sin fabricar el texto esperado (unmassk-standards Sec.34):
el texto que `rezones.py --verify` tiene que mencionar (que nota diverge)
sale de llamar en el MISMO proceso de test a `health.coherence(root)` --
la pieza REAL, ya en produccion -- contra el mismo repositorio corrompido,
nunca de un texto tecleado a mano.

**Convencion asumida sobre el codigo de retorno de `--verify`** -- ningun
texto del proyecto la fija: `--verify` con una divergencia real devuelve
codigo de retorno distinto de cero (mismo idioma que un linter -- "algo
esta mal, dilo con el retorno tambien, no solo con el texto"), y cero si
todo esta coherente. Marcado como ASUNCION, mismo patron que ya declaran
`test_context_script.py`/`test_note_script.py` para huecos sin texto
fijo.

Siembra de datos real: via `note.py` como PROCESO (`seed_note_via_script`,
`conftest.py`) -- ya existe y esta en verde.

Con el script inexistente, todos estos tests fallan hoy por la misma
causa real: `python3 <ruta inexistente>` -- ver docstring de
`test_note_script.py` para el detalle del mensaje.
"""

import contextlib
import os
from pathlib import Path

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_memory_script,
    seed_note_via_script,
    seed_zones_json,
)


@pytest.fixture
def health_lib():
    return import_lib_memory_module("health")


@pytest.fixture
def indexes_lib():
    return import_lib_memory_module("indexes")


@pytest.fixture
def notes_lib():
    return import_lib_memory_module("notes")


@pytest.fixture
def model_lib():
    return import_lib_memory_module("model")


@pytest.fixture
def vocabulary_lib():
    return import_lib_memory_module("vocabulary")


@contextlib.contextmanager
def _cwd(path):
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _decisions_path(repo):
    return pm_path(repo) / "DECISIONS.md"


def _remove_note_line(repo, note_id):
    """Corrompe DECISIONS.md a mano, quitando SOLO la linea de `note_id`
    -- el escenario exacto de la fila 1 de `health.py` "Sus tests":
    "Borrar una linea de un indice a mano se reporta como «falta en
    indice»". Devuelve el contenido ORIGINAL (antes de corromper), para
    que el test pueda comprobar despues que reconstruir lo devuelve
    IDENTICO, byte a byte.
    """
    path = _decisions_path(repo)
    original = path.read_text(encoding="utf-8")
    kept_lines = [
        line for line in original.splitlines(keepends=True) if f"[{note_id}]" not in line
    ]
    path.write_text("".join(kept_lines), encoding="utf-8")
    return original


class TestAcceptsFlagsWithoutBouncingOnAHealthyRepo:
    def test_verify_on_a_clean_repo_exits_zero(self, tmp_repo):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "auth", "product", "auth0 was never used here",
            description="MARK description", stops="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        rc, out, err = run_memory_script("rezones.py", ["--verify"], cwd=tmp_repo)
        assert rc == 0, f"un repo coherente no puede rebotar: stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err


class TestVerifyReportsRealDivergenceWithoutTouchingTheFile:
    def test_a_corrupted_index_is_reported_by_id_and_the_file_stays_untouched(
        self, tmp_repo, health_lib
    ):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "D", "auth", "product", "login with JWT and Google OAuth",
            why="sessions do not scale multi-tenant", description="MARK description",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        _original_content = _remove_note_line(tmp_repo, note_id)
        corrupted_content = _decisions_path(tmp_repo).read_text(encoding="utf-8")
        assert f"[{note_id}]" not in corrupted_content, "la corrupcion de prueba no quito la linea"

        with _cwd(tmp_repo):
            _lines, _notes, expected_discrepancies = health_lib.coherence(Path(tmp_repo))
        assert any(note_id in d for d in expected_discrepancies), (
            f"la corrupcion de prueba no produjo una divergencia real de health.coherence(): "
            f"{expected_discrepancies!r}"
        )

        rc, out, err = run_memory_script("rezones.py", ["--verify"], cwd=tmp_repo)
        assert "Traceback" not in out and "Traceback" not in err
        assert rc != 0, f"--verify con una divergencia real tiene que rebotar: stdout={out!r}"
        combined = out + err
        assert note_id in combined, (
            f"el diagnostico tiene que nombrar la nota que diverge (real, de "
            f"health.coherence(), no inventada): {combined!r}"
        )

        after_verify = _decisions_path(tmp_repo).read_text(encoding="utf-8")
        assert after_verify == corrupted_content, (
            "--verify SOLO diagnostica -- no puede haber tocado el fichero corrompido"
        )


class TestRebuildFixesAndReproducesTheOriginalExactly:
    def test_rebuild_restores_the_missing_line_and_matches_the_original_byte_for_byte(
        self, tmp_repo
    ):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "D", "auth", "product", "login with JWT and Google OAuth",
            why="sessions do not scale multi-tenant", description="MARK description",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        original_content = _remove_note_line(tmp_repo, note_id)

        rc, out, err = run_memory_script("rezones.py", [], cwd=tmp_repo)
        assert rc == 0, f"la reconstruccion no deberia fallar: stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        rebuilt_content = _decisions_path(tmp_repo).read_text(encoding="utf-8")
        assert rebuilt_content == original_content, (
            "reconstruir tiene que devolver EXACTAMENTE lo que habia antes de "
            "corromper -- esa igualdad es la prueba de que reconstruir no inventa "
            "[encargo de esta tarea]"
        )


class TestForceUtf8StreamsFirstStatement:
    def test_verify_survives_a_restricted_console_encoding(self, tmp_repo):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "auth", "product", "decision con acentos: sesión, código",
            description="MARK description", stops="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        rc, out, err = run_memory_script(
            "rezones.py", ["--verify"], cwd=tmp_repo,
            env={"PYTHONIOENCODING": "cp1252", "LANG": "C", "LC_ALL": "C"},
        )
        combined = out + err
        assert "UnicodeEncodeError" not in combined
        assert "UnicodeDecodeError" not in combined
        assert "Traceback" not in combined
        assert rc == 0, f"un repo coherente bajo cp1252 no deberia fallar: {combined!r}"


# ---------------------------------------------------------------------------
# Endurecimiento (paso 5, PIEZAS.md Sec.12bis) -- hallazgo real: `_rebuild()`
# reimplementaba treinta lineas del mismo cruce que ahora vive en
# `health.rebuild_plan()` [PIEZAS.md Sec.10, regla comun a los once
# scripts: "si un script crece, es que se le esta colando logica que
# pertenece a un modulo"]. Compara dos cosas escritas por separado: lo que
# el SCRIPT REAL deja en disco (subprocess, sobre el repo real) contra el
# plan de `health.rebuild_plan()` aplicado A MANO por este test, sobre una
# COPIA de los indices -- nunca la misma llamada reciclada dos veces.
# ---------------------------------------------------------------------------


class TestRebuildDelegatesToHealthRebuildPlan:
    def test_reindex_disk_state_matches_hand_applied_health_rebuild_plan(
        self, tmp_repo, health_lib, indexes_lib, notes_lib, model_lib, vocabulary_lib, tmp_path
    ):
        seed_zones_json(tmp_repo, ["ops", "checkout"])

        # Una nota real que se va a quedar SIN linea de indice (to_insert).
        rc1, out1, err1 = seed_note_via_script(
            tmp_repo, "D", "ops", "checkout", "MARK_REBUILD1 missing from its own index",
            why="MARK_REBUILD1_WHY", description="MARK description 1",
        )
        assert rc1 == 0, f"siembra 1 fallo: stdout={out1!r} stderr={err1!r}"
        missing_id = extract_note_id(out1)

        pm = pm_path(tmp_repo)
        decisions_path = pm / "DECISIONS.md"
        original = decisions_path.read_text(encoding="utf-8")
        without_missing = "".join(
            line for line in original.splitlines(keepends=True)
            if f"[{missing_id}]" not in line
        )
        decisions_path.write_text(without_missing, encoding="utf-8")
        assert f"[{missing_id}]" not in decisions_path.read_text(encoding="utf-8"), (
            "la corrupcion de prueba no quito la linea"
        )

        # Y una linea de indice SIN ninguna nota real detras (to_remove).
        with _cwd(tmp_repo):
            indexes_lib.insert(
                model_lib.IndexLine(
                    id="M-999999", zone1="ops", zone2="checkout",
                    headline="MARK_REBUILD_ORPHAN, no nota real detras",
                ),
                "MEMOS.md",
                pm,
            )
        assert any(
            line.id == "M-999999" for line in indexes_lib.read("MEMOS.md", pm)
        ), "la linea huerfana de prueba no quedo escrita"

        # Plan REAL, calculado ANTES de que el script real toque nada.
        with _cwd(tmp_repo):
            expected_to_insert, expected_to_remove = health_lib.rebuild_plan(Path(tmp_repo))
        assert any(note.id == missing_id for note, _target in expected_to_insert), (
            f"la nota corrompida ({missing_id}) deberia salir en to_insert: {expected_to_insert!r}"
        )
        assert any(note_id == "M-999999" for note_id, _name in expected_to_remove), (
            f"la linea huerfana deberia salir en to_remove: {expected_to_remove!r}"
        )

        # Snapshot de los OCHO indices, y el plan aplicado A MANO sobre esa
        # copia -- codigo distinto del que corre dentro de rezones.py.
        scratch_pm = tmp_path / "pm_snapshot"
        scratch_pm.mkdir()
        for name in vocabulary_lib.INDEX_FILES:
            (scratch_pm / name).write_text(
                (pm / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        for note, target in expected_to_insert:
            indexes_lib.insert(
                model_lib.IndexLine(
                    id=note.id, zone1=note.zone1, zone2=note.zone2, headline=note.headline,
                ),
                target,
                scratch_pm,
            )
        for note_id, name in expected_to_remove:
            indexes_lib.remove(note_id, name, scratch_pm)

        # El SCRIPT REAL, como proceso, sobre el repo real.
        rc, out, err = run_memory_script("rezones.py", [], cwd=tmp_repo)
        assert rc == 0, f"la reconstruccion no deberia fallar: stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        for name in vocabulary_lib.INDEX_FILES:
            real_content = (pm / name).read_text(encoding="utf-8")
            hand_applied_content = (scratch_pm / name).read_text(encoding="utf-8")
            assert real_content == hand_applied_content, (
                f"{name}: el resultado REAL de rezones.py no coincide con el "
                "plan de health.rebuild_plan() aplicado a mano de forma "
                "independiente -- rezones.py dejo de usar la misma pieza "
                f"compartida.\nreal={real_content!r}\nesperado={hand_applied_content!r}"
            )
