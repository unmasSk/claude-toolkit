"""Contrato ROJO de `bin/memory/remove.py` -- PIEZAS.md Sec.10 (fila `remove.py`).

`bin/memory/remove.py` NO EXISTE TODAVIA. Modo test-first, pase de
CONTRATO: aceptacion, no barrido exhaustivo (ese llega despues de que
Ultron implemente, en el pase de endurecimiento).

De donde sale cada cosa:

- PIEZAS.md Sec.10, fila `remove.py`: llama a `notes.close`; admite
  "identificador, motivo, --restriction"; imprime "la linea movida al
  archivo".
- Las cuatro filas de test comunes (misma seccion) + las dos reglas de
  esta tarea (force_utf8_streams primera sentencia; repo resuelto por
  cwd del proceso).
- La firma real de `lib/memory/notes.py::close(note_id, reason, ctx)` --
  YA en produccion (leida antes de escribir este contrato): retira la
  linea de su indice vigente y la anade a `ARCHIVED.md` con destino
  `"closed: <reason>"`, en un solo commit. Si `note_id` no esta en su
  indice, `indexes.remove()` (tambien en produccion) lanza
  `ValueError(f"{note_id!r} no esta en {index_name}")` SIN tocar nada --
  esta es la unica excepcion real y documentada que `remove.py` tiene que
  atrapar para no imprimir una traza de pila.

HUECO QUE ESTE CONTRATO NO CIERRA, anotado en vez de inventado: TEXTOS.md
Sec.1.10 describe un flujo de `--restriction new --restriction-text ...
--why ...` que HARIA NACER una R nueva al cerrar una incidencia -- pero
`notes.close()` no tiene ninguna capacidad de crear una nota nueva (su
firma entera es `close(note_id, reason, ctx) -> WriteResult`, y su
docstring dice explicitamente que `ctx` "no se usa: cerrar no crea
ninguna nota nueva"). La fila de PIEZAS.md Sec.10 tampoco declara una
segunda llamada a `notes.write` para este script. Ningun test de aqui
ejercita `--restriction new`: solo `--restriction no`, que es el unico
camino que la firma real de `notes.close()` puede cumplir sin inventar
logica que no vive en ninguna pieza ya escrita.

Los tests SIEMBRAN una nota real primero, llamando a `notes.write()` EN
PROCESO (produccion ya existente, mismo patron que `test_notes.py`) DENTRO
de `_cwd(tmp_repo)` -- nunca a traves del script bajo contrato, que es
precisamente lo que se esta probando. `remove.py` se invoca siempre como
proceso aparte (`run_memory_script`), nunca importado.

Con el script inexistente, todos estos tests fallan hoy por la misma
causa real: `python3 <ruta inexistente>` -- ver docstring de
`test_note_script.py` para el detalle del mensaje.
"""

import contextlib
import os
from datetime import datetime, timezone

import pytest

from .conftest import (
    import_lib_memory_module,
    pm_path,
    run_memory_script,
)


@pytest.fixture
def notes():
    return import_lib_memory_module("notes")


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
def vocabulary():
    return import_lib_memory_module("vocabulary")


@pytest.fixture
def query():
    return import_lib_memory_module("query")


@contextlib.contextmanager
def _cwd(path):
    """Mismo helper que `test_notes.py` -- ver su docstring para el
    porque exacto (`notes.write()` resuelve el repositorio por el cwd
    del proceso, sin declarar un parametro de raiz)."""
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


@pytest.fixture
def seed_note(tmp_repo, notes, model, config, validator):
    """Da de alta una M real (via `notes.write()`, produccion ya
    existente) y devuelve su id real -- nunca fabricado, siempre el que
    `WriteResult.note_id` devuelve."""

    def _seed(headline="MARK seeded note for remove.py contract", zone1="product", zone2="closeTest"):
        zones = {
            zone1: model.Zone(name=zone1, description="MARK", aliases=()),
            zone2: model.Zone(name=zone2, description="MARK", aliases=()),
        }
        ctx = validator.Context(
            zones=zones, existing_in_zone=(), known_ids=frozenset(), config=config.Config(),
        )
        note = model.Note(
            type="M", id="", zone1=zone1, zone2=zone2, headline=headline,
            description="MARK description, not empty",
            timestamp=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
        )
        with _cwd(tmp_repo):
            result = notes.write(note, ctx)
        assert result.ok, f"la siembra real fallo, no es parte de lo que este contrato prueba: {result}"
        return result.note_id

    return _seed


class TestAcceptsAllFlagsWithoutBouncingAndMovesTheLineForReal:
    """Filas 1 y 4 de "Sus tests" [PIEZAS.md Sec.10]: un comando, cero
    rechazos; y el efecto real -- la linea sale de su indice vigente y
    entra en ARCHIVED.md con destino "closed: <motivo>"."""

    def test_close_no_restriction_moves_line_from_index_to_archive(
        self, tmp_repo, seed_note, indexes, vocabulary
    ):
        note_id = seed_note()
        pm = pm_path(tmp_repo)
        # Antes de cerrar: la linea esta en su indice vigente.
        assert any(line.id == note_id for line in indexes.read("MEMOS.md", pm))

        rc, out, err = run_memory_script(
            "remove.py",
            [note_id, "fixed in #58, no fence needed", "--restriction", "no"],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        # Efecto real, leido con el lector real -- no supuesto.
        assert not any(line.id == note_id for line in indexes.read("MEMOS.md", pm)), (
            "la linea deberia haber salido de MEMOS.md tras el cierre"
        )
        archived = [a for a in indexes.read_archive(pm) if a.id == note_id]
        assert len(archived) == 1, f"deberia haber exactamente una linea de archivo para {note_id}"
        assert archived[0].destination == "closed"
        assert archived[0].destination_detail == "fixed in #58, no fence needed"


class TestFailureExitsNonzeroWithRealTextNoTraceback:
    """Filas 2 y 3 de "Sus tests": codigo de retorno distinto de cero, y
    la salida es el error real (nunca una traza de pila)."""

    def test_unknown_id_fails_with_the_real_indexes_error_not_a_traceback(self, tmp_repo):
        rc, out, err = run_memory_script(
            "remove.py",
            ["M-999999", "does not exist", "--restriction", "no"],
            cwd=tmp_repo,
        )
        assert rc != 0, f"un id que no existe tiene que fallar: stdout={out!r}"
        combined = out + err
        assert "Traceback" not in combined
        # Texto real de `indexes.remove()` (ya en produccion):
        # ValueError(f"{note_id!r} no esta en {index_name}") -- el id y
        # su fichero de indice real (M -> MEMOS.md, tabla ya en
        # produccion en notes.py) tienen que aparecer, no una traza.
        assert "M-999999" in combined
        assert "MEMOS.md" in combined

    def test_real_git_index_lock_surfaces_the_real_git_error_not_a_traceback(
        self, tmp_repo, seed_note
    ):
        note_id = seed_note()
        # Mismo mecanismo que test_notes.py: `.git/index.lock` a mano
        # provoca un fallo REAL de `git commit` (`fatal: Unable to
        # create '.../index.lock': File exists.`), no fabricado.
        lock_path = os.path.join(tmp_repo, ".git", "index.lock")
        with open(lock_path, "w", encoding="utf-8"):
            pass
        try:
            rc, out, err = run_memory_script(
                "remove.py",
                [note_id, "should not commit, index is locked", "--restriction", "no"],
                cwd=tmp_repo,
            )
        finally:
            os.remove(lock_path)

        assert rc != 0, f"con .git/index.lock puesto, el commit tiene que fallar: stdout={out!r}"
        combined = out + err
        assert "Traceback" not in combined
        assert "index.lock" in combined, (
            f"el error real de git (menciona index.lock) tiene que llegar a la salida: {combined!r}"
        )


class TestForceUtf8StreamsFirstStatement:
    def test_real_error_survives_a_restricted_console_encoding(self, tmp_repo):
        rc, out, err = run_memory_script(
            "remove.py",
            ["M-999999", "does not exist", "--restriction", "no"],
            cwd=tmp_repo,
            env={"PYTHONIOENCODING": "cp1252", "LANG": "C", "LC_ALL": "C"},
        )
        assert rc != 0
        combined = out + err
        assert "UnicodeEncodeError" not in combined
        assert "UnicodeDecodeError" not in combined
        assert "Traceback" not in combined
        assert "M-999999" in combined


class TestRepoResolvedByProcessCwd:
    """El script resuelve el repositorio por el directorio donde se
    ejecuta -- lanzado desde una subcarpeta de `tmp_repo`, el cierre
    tiene que aparecer en ESE MISMO repo, no en otro sitio."""

    def test_launched_from_a_nested_subdirectory_still_closes_in_that_same_repo(
        self, tmp_repo, seed_note, indexes
    ):
        note_id = seed_note(headline="MARK seeded note, closed from nested cwd")
        nested = os.path.join(tmp_repo, "src", "some", "nested", "place")
        os.makedirs(nested, exist_ok=True)

        rc, out, err = run_memory_script(
            "remove.py",
            [note_id, "closed from a nested cwd", "--restriction", "no"],
            cwd=nested,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        pm = pm_path(tmp_repo)
        assert not any(line.id == note_id for line in indexes.read("MEMOS.md", pm)), (
            "el cierre no se reflejo en tmp_repo aunque el script se lanzo desde "
            "una subcarpeta suya -- ¿resuelve el repositorio por una ruta fija?"
        )
        archived = [a for a in indexes.read_archive(pm) if a.id == note_id]
        assert len(archived) == 1


# ---------------------------------------------------------------------------
# Endurecimiento (paso 5, PIEZAS.md Sec.12bis) -- hallazgo real de
# `_create_fence()`: `--restriction new` es DOS commits (cierre, luego
# muro). Si el muro nace rechazado, el cierre YA se hizo -- es
# PERMANENTE, no hay vuelta atras. Antes de este arreglo, el script salia
# con codigo 1 sin decir que el cierre ya habia quedado guardado; quien
# mirase solo el codigo de retorno reintentaria el comando ENTERO, que
# fallaria de otra forma porque el ID ya no esta en su indice vigente.
# Ahora el aviso dice el estado real primero, y da el comando EXACTO para
# relanzar SOLO el muro.
# ---------------------------------------------------------------------------


# RETIRADA 2026-08-05 [encargo del propietario]: esta clase se llamaba
# `TestRestrictionNewWarnsThePermanentCloseAndGivesAWorkingRetryCommand` y
# afirmaba, para un titular de muro de 96 caracteres, que el cierre de la
# incidencia YA era permanente ("archivada" + "permanente" en la salida,
# indice vigente vacio, ARCHIVED.md con la linea) y que el reintento
# consistia en relanzar SOLO el muro suelto con un comando impreso por
# `_fence_retry_command()`. Esa conducta era el bug, no el contrato: el
# propietario decidio el mismo dia "si quiere apuntar un muro, tiene que
# apuntarse ese muro" -- o pasan las dos cosas (cierre + muro), o no pasa
# ninguna. `_guard_restriction_new()` (`bin/memory/remove.py`) ahora pasa
# la R candidata por `validator.validate_note()` ANTES de tocar nada, asi
# que un titular de 96 caracteres rebota el comando ENTERO sin cerrar la
# incidencia -- exactamente lo contrario de lo que esta clase daba por
# bueno.
#
# El escenario (titular de muro que supera `vocabulary.HEADLINE_MAX` con
# `--restriction new`, antes de tocar nada) ya esta cubierto por
# `test_remove_incident_close_fence_atomicity.py::TestFenceThatCannotBeBornClosesNothing`
# -- mismo titular de mas de 80 caracteres, mismos lectores reales
# (`indexes.read`/`indexes.read_archive`), mas la comparacion byte a byte
# de `INCIDENTS.md`/`ARCHIVED.md`/`RESTRICTIONS.md` que esta clase no
# hacia. No se duplica aqui: se retira la clase entera y queda esta nota
# en su lugar en vez de borrarla en silencio.
#
# El unico trozo que esta clase cubria y que el fichero nuevo NO cubre es
# `_fence_retry_command()` / el flujo de "relanza solo el muro" -- ese
# codigo sigue vivo en `_create_fence()` para el caso en que el
# PRE-CHEQUEO pasa pero la escritura real del muro falla despues (p.ej. un
# error de git), no para un titular demasiado largo (que ahora ni siquiera
# llega ahi). Ese camino queda sin test dedicado tras esta retirada; no es
# parte de este encargo, se anota como hueco, no se inventa.


# ---------------------------------------------------------------------------
# Regresion (2026-08-04, hallazgo de Moriarty, reparado el mismo dia en
# `notes.py::_reject_close_reason_multiline`): un motivo de cierre con un
# salto de linea propio partia `ARCHIVED.md` en dos lineas fisicas y el
# comando salia con "✅ archivada" y codigo 0 -- corrupcion silenciosa mas
# un visto bueno falso. Este fallo ya salio dos veces en dias anteriores
# [aviso del propietario]. `close()` lo rechaza ahora ANTES de tocar nada
# -- se comprueba aqui contra el SCRIPT real, comparando lo que el comando
# dice que hizo contra lo que queda escrito en disco.
# ---------------------------------------------------------------------------


class TestCloseReasonWithNewlineIsRejectedBeforeTouchingAnything:
    def test_multiline_reason_is_rejected_with_retry_command_and_leaves_archive_and_index_untouched(
        self, tmp_repo, seed_note
    ):
        note_id = seed_note()
        pm = pm_path(tmp_repo)
        index_path = pm / "MEMOS.md"
        archive_path = pm / "ARCHIVED.md"
        index_before = index_path.read_bytes()
        archive_before = archive_path.read_bytes()

        rc, out, err = run_memory_script(
            "remove.py",
            [note_id, "motivo\nsegunda linea", "--restriction", "no"],
            cwd=tmp_repo,
        )

        assert rc == 1, f"un motivo con salto de linea tiene que rebotar con codigo 1: stdout={out!r} stderr={err!r}"
        combined = out + err
        assert "Traceback" not in combined
        assert "✅" not in combined, (
            f"no puede haber confirmado el cierre si lo rechazo: {combined!r}"
        )
        assert "salto de linea" in combined, (
            f"el rechazo tiene que nombrar el motivo real (salto de linea propio): {combined!r}"
        )
        # El comando de reintento real, letra por letra -- mismo texto que
        # `notes.py::_reject_close_reason_multiline` construye en produccion.
        assert f'gitmem remove {note_id} "<motivo sin saltos de linea>"' in combined, (
            f"falta el comando exacto de reintento: {combined!r}"
        )

        # Lo que el comando DICE que hizo (nada) contra lo que queda
        # escrito en disco -- byte a byte, sin tocar ni un caracter.
        assert index_path.read_bytes() == index_before, (
            "MEMOS.md no deberia haber cambiado ni un byte tras un cierre rechazado"
        )
        assert archive_path.read_bytes() == archive_before, (
            "ARCHIVED.md no deberia haber cambiado ni un byte tras un cierre rechazado"
        )
