"""Contrato ROJO de `bin/memory/next.py` -- PIEZAS.md Sec.10 (fila `next.py`,
renombrada desde `context.py` -- decision del propietario, 2026-08-03:
"el comando escribe el cierre de sesion, y lo que importa de el es el
Next"). Subcomando `next`.

`bin/memory/next.py` (antes `context.py`). Modo test-first, pase de
CONTRATO: aceptacion, no barrido exhaustivo.

**No confundir con `tests/memory/test_context.py`** (contrato de
`lib/memory/context.py`, que NO se renombro -- solo cambian el script y
el subcomando, PIEZAS.md Sec.10): este fichero prueba el SCRIPT
(`bin/memory/next.py`) como proceso, nunca importa
`context.write`/`context.latest` para probarlas -- solo las usa como
LECTOR REAL para verificar el efecto del script.

De donde sale cada cosa:

- PIEZAS.md Sec.10, fila `next.py`: llama a `context.write`; admite
  "titular, --keys, el contexto en prosa"; imprime "confirmacion".
- Las cuatro filas de test comunes + las dos reglas de esta tarea
  (force_utf8_streams primera sentencia; repo resuelto por cwd del
  proceso).
- `lib/memory/context.py::write(ctx: ContextNote) -> WriteResult` y
  `latest() -> ContextNote | None` -- YA en produccion, leidas antes de
  escribir este contrato: "sin candado, sin aduana, sin indice" (su
  propio docstring) -- `write()` no valida nada, es la unica escritura
  del sistema exenta a proposito. `ContextNote.headline` se guarda SIN
  el marcador `[NEXT] <emoji>` (lo añade/quita
  `format.build_context_message`/`parse_context_message` en el borde) --
  el round trip real compara contra el titular tal cual se paso por CLI,
  sin el corchete ni el emoji.

GRAMATICA DE CLI ASUMIDA -- ninguna fuente del proyecto la fija literal
para este script (a diferencia de `note.py`, TEXTOS.md no repite un
comando de relanzamiento para el cierre de sesion). Se asume, de forma
consistente con `--description` de `note.py` (un campo de texto libre
obligatorio va por flag aunque no sea opcional):

    next.py "<titular>" --context "<resumen en prosa>" [--keys k1 k2 ...]

**El cuerpo es prosa corrida, no una lista de puntos** [decision del
propietario, 2026-08-03, COLA.md Sec.5]: `--context` reemplaza al
`--point` repetible de la version anterior de este contrato --
`ContextNote.context` es una unica cadena, nunca una tupla de puntos.

Con el script inexistente, todos estos tests fallan hoy por la misma
causa real: `python3 <ruta inexistente>` -- ver docstring de
`test_note_script.py` para el detalle del mensaje.
"""

import contextlib
import os

import pytest

from .conftest import import_lib_memory_module, run_git, run_memory_script


@pytest.fixture
def context_lib():
    return import_lib_memory_module("context")


@contextlib.contextmanager
def _cwd(path):
    """Mismo helper que en `test_notes.py`/`test_remove_script.py`:
    `context.latest()` (via `query.run_git_log`) resuelve el repositorio
    por el cwd del proceso, sin declarar un parametro de raiz."""
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _git_commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


def _git_files_changed(repo):
    """Ficheros que el commit HEAD toca, via `git show --stat` de
    verdad -- para probar que el commit de contexto es GENUINAMENTE
    vacio (fila 2 de este fichero), no fabricado a partir de lo que el
    script DEBERIA hacer."""
    rc, out, err = run_git(["show", "--name-only", "--pretty=format:", "HEAD"], repo)
    assert rc == 0, f"git show fallo en el test: {err}"
    return [line for line in out.splitlines() if line.strip()]


class TestAcceptsAllFlagsWithoutBouncing:
    def test_headline_keys_and_context_in_one_call(self, tmp_repo):
        rc, out, err = run_memory_script(
            "next.py",
            [
                "implement discussed changes to close-session skill",
                "--keys", "close-session", "checkpoint", "plan",
                "--context",
                "Revisado el diseno del checkpoint: muere el automatico. "
                "Punto de inflexion: fuera comodines.",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err


class TestProducesAGenuinelyEmptyCommitAndRoundTripsForReal:
    """Fila 4 de "Sus tests", adaptada: el camino completo probado de
    punta a punta -- el commit no toca NINGUN fichero, y `context.latest()`
    (lector real, ya en produccion) recupera exactamente lo que el script
    escribio."""

    def test_commit_is_empty_and_latest_reads_back_the_same_data(self, tmp_repo, context_lib):
        before = _git_commit_count(tmp_repo)
        prose = (
            "Revisado el diseno del checkpoint: muere el automatico. "
            "Punto de inflexion: fuera comodines."
        )
        rc, out, err = run_memory_script(
            "next.py",
            [
                "implement discussed changes to close-session skill",
                "--keys", "close-session", "checkpoint", "plan",
                "--context", prose,
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, "el cierre tiene que producir exactamente un commit nuevo"
        assert _git_files_changed(tmp_repo) == [], (
            "el commit de contexto no puede tocar ningun fichero -- 'sin candado, "
            "sin aduana, sin indice' [context.py, docstring del modulo]"
        )

        with _cwd(tmp_repo):
            latest = context_lib.latest()
        assert latest is not None, "context.latest() no encontro el cierre recien escrito"
        assert latest.headline == "implement discussed changes to close-session skill"
        assert latest.keys == ("close-session", "checkpoint", "plan")
        assert latest.context == prose


class TestFailureExitsNonzeroWithRealTextNoTraceback:
    """NOTA: no hay aqui un test de "falta el titular" (argparse). Se
    probo y se descarto a proposito: con el script inexistente, un
    argparse real y un "can't open file" de Python devuelven los DOS un
    `returncode` distinto de cero y CERO "Traceback" en la salida --
    cualquier assert que solo mire esas dos cosas pasaria en falso hoy
    mismo (verificado ejecutando), lo que rompe la garantia de este
    contrato ("ningun test puede quedarse en verde por la causa
    equivocada"). Sin ninguna aduana en `context.write()` que produzca
    un texto real y comparable [docstring del modulo: "sin candado, sin
    aduana, sin indice"], no hay ningun contenido POSITIVO que comparar
    sin inventar la redaccion exacta de argparse -- exactamente lo que
    el encargo pide no hacer. La fila "sin traceback ante entrada mala"
    queda cubierta por el test de abajo (`.git/index.lock`), que si
    produce un texto real y verificable."""

    def test_real_git_index_lock_surfaces_the_real_git_error_not_a_traceback(self, tmp_repo):
        lock_path = os.path.join(tmp_repo, ".git", "index.lock")
        with open(lock_path, "w", encoding="utf-8"):
            pass
        try:
            rc, out, err = run_memory_script(
                "next.py",
                [
                    "should not commit, index is locked",
                    "--context", "contexto de prueba para el candado de git",
                ],
                cwd=tmp_repo,
            )
        finally:
            os.remove(lock_path)

        assert rc != 0, f"con .git/index.lock puesto, el commit tiene que fallar: stdout={out!r}"
        combined = out + err
        assert "Traceback" not in combined
        assert "index.lock" in combined, (
            f"el error real de git tiene que llegar a la salida: {combined!r}"
        )


class TestForceUtf8StreamsFirstStatement:
    def test_accented_headline_and_context_survive_a_restricted_console_encoding(self, tmp_repo):
        rc, out, err = run_memory_script(
            "next.py",
            [
                "sesión cerrada con é, ñ y 🚧 en el cuerpo",
                "--context", "decisión tomada de palabra, sin código todavía",
            ],
            cwd=tmp_repo,
            env={"PYTHONIOENCODING": "cp1252", "LANG": "C", "LC_ALL": "C"},
        )
        combined = out + err
        assert "UnicodeEncodeError" not in combined
        assert "UnicodeDecodeError" not in combined
        assert "Traceback" not in combined
        assert rc == 0, f"un cierre valido con acentos no deberia fallar bajo cp1252: {combined!r}"


class TestRepoResolvedByProcessCwd:
    def test_launched_from_a_nested_subdirectory_still_writes_to_that_same_repo(
        self, tmp_repo, context_lib
    ):
        nested = os.path.join(tmp_repo, "src", "some", "nested", "place")
        os.makedirs(nested, exist_ok=True)
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "next.py",
            [
                "context written from a nested cwd",
                "--context", "escrito desde una subcarpeta anidada del mismo repo",
            ],
            cwd=nested,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, (
            "el commit no aparecio en tmp_repo aunque el script se lanzo desde "
            "una subcarpeta suya -- ¿resuelve el repositorio por una ruta fija?"
        )
        with _cwd(tmp_repo):
            latest = context_lib.latest()
        assert latest is not None and latest.headline == "context written from a nested cwd"
