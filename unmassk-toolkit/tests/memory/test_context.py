"""Contrato de lib/memory/context.py -- PIEZAS.md Sec.9.6.

context.py NO EXISTE TODAVIA. Estos tres tests deben fallar al importar,
por diseno -- es el RED del modo test-first. Uno por fila de la tabla
"Sus tests" de Sec.9.6, ni uno mas:

  1. Se escribe y se lee de vuelta identico, con sus puntos de contexto.
  2. El segundo cierre pisa al primero y el arranque enseña solo el
     ultimo.
  3. La aduana no le hace ni una pregunta.

context.py es "leer y escribir el (arrow) del cierre de sesion" (Sec.9.6,
"Para que"): perder el hilo entre sesiones es el unico fallo que esta
pieza existe para prevenir -- el arranque siguiente enseña un Next que ya
no es el vigente, o dos Next compitiendo, y nadie sabe cual seguir.

El fixture `context` se pide PRIMERO en cada firma (mismo patron que
test_query.py/test_zones.py/test_format.py): pytest instancia los
fixtures en el orden en que aparecen, asi que si `context.py` no existe
el fallo se reporta ahi -- nunca por `model.py`/`validator.py`/
`vocabulary.py`, que ya existen y estan en verde.

**Superficie usada, literal de Sec.9.6** (nunca se inventa un parametro
que no este ahi):

    def write(ctx: ContextNote) -> WriteResult
    def latest() -> ContextNote | None

**Supuestos declarados, sin fuente literal en Sec.9.6 (mismo tipo de
hueco que en query-contract-notes.md/format-contract-notes.md):**

1. **Ninguna de las dos funciones declara parametro de `root`/`cwd`** --
   se asume que, igual que el resto de la Capa 2/3 ya escrita
   (`gitcmd.commit()`, `notes.write()`), heredan el cwd ambiental del
   proceso. Por eso cada test hace `monkeypatch.chdir(tmp_repo)` antes de
   llamar a `context.*` -- nunca se inventa un parametro que la
   superficie declarada no tiene.
2. **`ContextNote.timestamp` se excluye de toda comparacion**, mismo
   criterio que `test_format.py`/`test_query.py`: `format.py`
   (`parse_context_message`, ya en verde) fija esa fecha en el momento
   del PARSEO, no la deriva del commit -- no es un valor que este test
   pueda fijar de antemano y esperar de vuelta byte a byte. Round-trip
   real de los campos que SI son la memoria (headline, context,
   keys), no del reloj.
3. **El fichero real que toca el commit de contexto no se supone.**
   Sec.9.6 dice "sin indice y sin lapida" pero `gitcmd.commit()` (Sec.7.1,
   ya en verde) exige `paths` no vacio -- como resuelve `write()` esa
   tension (un `git commit --allow-empty` sin pathspec via `gitcmd.run()`
   directo, o algun fichero propio que no es indice ni archivo) no esta
   escrito en ningun sitio y no se inventa aqui. Los tres tests de este
   fichero solo llaman a la Superficie declarada (`context.write`,
   `context.latest`) y comprueban lo que devuelven contra un repo git
   real -- nunca aserciones sobre que ruta se toco por dentro.
4. **La fila 3 ("la aduana no le hace ni una pregunta") se prueba con un
   titular real que SI dispara la aduana para una `Note` normal** --
   mas largo que `vocabulary.HEADLINE_MAX`, el mismo umbral que
   `validator.validate_headline` usa (Sec.6.1, ya en verde). Se
   comprueba primero, contra el validador real (no una suposicion), que
   ese titular concreto SI produce un `Rejection` para una nota
   corriente -- asi el test no es un hombre de paja: prueba que el input
   es genuinamente provocador antes de comprobar que `context.write` lo
   deja pasar de todas formas.

No se toca produccion: si `lib/memory/context.py` no existe, estos tests
se quedan en rojo tal cual estan -- eso es lo esperado. No se toca ningun
fichero de un companero (`conftest.py`, `test_notes.py`, etc.).
"""

import dataclasses
from pathlib import Path

import pytest

from .conftest import import_lib_memory_module, run_git


@pytest.fixture
def context():
    return import_lib_memory_module("context")


@pytest.fixture
def model():
    return import_lib_memory_module("model")


@pytest.fixture
def validator():
    return import_lib_memory_module("validator")


@pytest.fixture
def vocabulary():
    return import_lib_memory_module("vocabulary")


def _context_note(model, **overrides):
    """Factoria de ContextNote con valores por defecto neutros -- cada
    test override solo los campos que le importan. Mismo patron que
    `_note` en test_query.py/test_format.py.
    """
    from datetime import datetime, timezone

    fields = dict(
        headline="implement discussed changes to close-session skill",
        context=(
            "Revisado el diseno del checkpoint: muere el automatico, lo hace "
            "close-session. Decidido de palabra: los planes viven en docs/ "
            "como plan-*.md."
        ),
        keys=("close-session", "checkpoint"),
        timestamp=datetime(2026, 8, 1, 19, 44, tzinfo=timezone.utc),
    )
    fields.update(overrides)
    return model.ContextNote(**fields)


def _zero_commit_repo(tmp_path, name="zero_commit_repo"):
    """Un repo git genuinamente SIN NINGUN commit -- distinto de
    `tmp_repo` (conftest.py), que ya trae un commit 'init' de fabrica.
    `git log` sobre este repo devuelve el mensaje real de rama sin nacer
    ('does not have any commits yet'), no un fallo simulado.
    """
    repo = tmp_path / name
    repo.mkdir()
    rc, _out, err = run_git(["init"], str(repo))
    assert rc == 0, f"git init fallo montando el repo sin commits: {err}"
    return repo


def _assert_context_fields_match(parsed, expected, exclude=("timestamp",)):
    """Compara campo a campo, nunca con `==` directo sobre el objeto --
    el `model` que este fichero carga via `import_lib_memory_module` y el
    `model` que `context.py` importa por dentro (`from model import
    ContextNote`, convencion plana de PIEZAS Sec.3.3bis) pueden acabar
    siendo clases Python DISTINTAS aunque el codigo fuente sea identico
    -- mismo hallazgo que test_query.py::_assert_fields_match.
    """
    assert parsed is not None
    for field in dataclasses.fields(expected):
        if field.name in exclude:
            continue
        parsed_value = getattr(parsed, field.name)
        expected_value = getattr(expected, field.name)
        assert parsed_value == expected_value, (
            f"campo {field.name!r} no volvio identico via context.latest(): "
            f"{parsed_value!r} != {expected_value!r}"
        )


def test_write_then_latest_returns_the_same_context_note_with_its_points(
    context, model, tmp_repo, monkeypatch
):
    """Fila 1: se escribe y se lee de vuelta identico, con sus puntos de
    contexto.

    Fallo real que previene: perder el hilo entre sesiones, que es para
    lo unico que existe esta pieza.
    """
    monkeypatch.chdir(tmp_repo)

    written = _context_note(
        model,
        headline="ship the context.py round trip contract",
        context=(
            "escrito el contrato de context.py en modo test-first. pendiente: "
            "que Ultron lo implemente hasta que los tests pasen"
        ),
        keys=("context", "close-session"),
    )

    write_result = context.write(written)
    assert write_result.ok, (
        f"context.write() no dio ok=True sobre un repo real: {write_result!r}"
    )

    read_back = context.latest()

    _assert_context_fields_match(read_back, written)


def test_second_close_overwrites_the_first_and_latest_shows_only_the_newest(
    context, model, tmp_repo, monkeypatch
):
    """Fila 2: el segundo cierre pisa al primero y el arranque enseña
    solo el ultimo.

    Fallo real que previene: dos "siguiente paso" a la vez, sin saber
    cual esta vivo.
    """
    monkeypatch.chdir(tmp_repo)

    first_close = _context_note(
        model,
        headline="first next: this one must stop being visible after the second close",
        context="primer cierre de la sesion de prueba",
        keys=("first-close",),
    )
    second_close = _context_note(
        model,
        headline="second next: this is the only one latest() should show",
        context="segundo cierre, pisa por completo al primero",
        keys=(),
    )

    first_write = context.write(first_close)
    assert first_write.ok, f"el primer context.write() no dio ok=True: {first_write!r}"

    second_write = context.write(second_close)
    assert second_write.ok, f"el segundo context.write() no dio ok=True: {second_write!r}"

    read_back = context.latest()

    _assert_context_fields_match(read_back, second_close)
    assert read_back.headline != first_close.headline, (
        "context.latest() devolvio el titular del primer cierre; el segundo "
        "debe pisarlo por completo, no convivir con el"
    )
    assert read_back.context != first_close.context, (
        "context.latest() devolvio el contexto del primer cierre; el segundo "
        "debe pisarlo por completo, no convivir con el"
    )


def test_write_asks_the_customs_no_question_not_even_for_an_over_length_headline(
    context, model, validator, vocabulary, tmp_repo, monkeypatch
):
    """Fila 3: la aduana no le hace ni una pregunta.

    Fallo real que previene: friccion justo al cerrar, que es cuando
    menos se tolera.

    El titular usado es mas largo que `vocabulary.HEADLINE_MAX` -- se
    comprueba primero, contra `validator.validate_headline` real, que
    ese titular concreto SI dispara un rechazo para una nota corriente,
    para que el test no sea un hombre de paja.
    """
    monkeypatch.chdir(tmp_repo)

    over_length_headline = "x" * (vocabulary.HEADLINE_MAX + 1)

    would_reject_a_normal_note = validator.validate_headline(over_length_headline)
    assert would_reject_a_normal_note is not None, (
        "el titular de prueba no dispara validate_headline para una nota "
        "corriente -- el test no probaria nada sobre la exencion de la aduana"
    )

    provocative_close = _context_note(
        model,
        headline=over_length_headline,
        context="cierre con un titular deliberadamente demasiado largo",
        keys=(),
    )

    write_result = context.write(provocative_close)

    assert write_result.ok, (
        f"context.write() rechazo un titular largo -- la aduana le hizo una "
        f"pregunta que Sec.9.6 dice que no debe hacerle: {write_result!r}"
    )
    assert write_result.rejections == (), (
        f"context.write() devolvio rechazos de la aduana: "
        f"{write_result.rejections!r} -- Sec.9.6 dice 'exento de la aduana'"
    )
    assert write_result.git_error is None, (
        f"context.write() fallo por un error real de git, no por la aduana: "
        f"{write_result.git_error!r}"
    )


# ---------------------------------------------------------------------------
# Ronda 2 (Moriarty) -- dos arreglos mas, ya hechos, sin ninguna red que los
# proteja. Los dos se demostraron ejecutando (docstring de context.py,
# "hallazgo 2"/"hallazgo 3 de Moriarty, ronda 2"). Ninguno toca produccion.
# ---------------------------------------------------------------------------


def test_latest_on_a_repo_with_zero_commits_returns_none_not_an_exception(
    context, tmp_path, monkeypatch
):
    """Hallazgo 2 de Moriarty, ronda 2 -- un repo recien creado, sin un
    solo commit todavia, reventaba `context.latest()` (que la llamaba
    `boot.build()` sin capturar nada): `git log` sobre una rama sin nacer
    devuelve `returncode=128` con "does not have any commits yet", y
    antes de la consolidacion via `query.run_git_log()` eso no se
    distinguia de un fallo real transitorio.

    Un proyecto sin un solo commit no tiene ningun cierre de sesion que
    enseñar -- es exactamente el caso que esta funcion ya declara como
    `None` para "nunca se cerro ninguna sesion", nunca un `RuntimeError`.
    """
    root = _zero_commit_repo(tmp_path)
    monkeypatch.chdir(root)

    result = context.latest()  # NO debe lanzar

    assert result is None, (
        f"un repo sin ningun commit deberia devolver None (nunca se cerro "
        f"ninguna sesion), devolvio {result!r}"
    )


def test_second_close_with_empty_context_still_wins_over_the_first(
    context, model, tmp_repo, monkeypatch
):
    """Hallazgo 3 de Moriarty, ronda 2 -- el Next mas reciente se perdia
    cuando su contexto venia vacio (un valor VALIDO). Distinto de
    `test_second_close_overwrites_the_first_and_latest_shows_only_the_
    newest` de arriba (los dos cierres de ESE test llevan contexto no
    vacio): aqui el SEGUNDO cierre -- el que `latest()` debe devolver --
    tiene el campo `Context` VACIO a proposito.

    Antes del arreglo (ver docstring de `format.parse_context_message`,
    "hallazgo 3 de Moriarty"), un cierre real sin contenido se confundia
    con "esto no es un cierre" y `latest()` seguia buscando hacia atras --
    devolvia el cierre MAS ANTIGUO que si tenia contenido, perdiendo
    exactamente el hilo entre sesiones que esta pieza existe para no
    perder.
    """
    monkeypatch.chdir(tmp_repo)

    first_close = _context_note(
        model,
        headline="first next: has context, must stop being visible after the second",
        context="primer cierre, con contexto real",
        keys=("first-close",),
    )
    second_close = _context_note(
        model,
        headline="second next: empty context, this is still the one latest() must show",
        context="",
        keys=(),
    )

    first_write = context.write(first_close)
    assert first_write.ok, f"el primer context.write() no dio ok=True: {first_write!r}"

    second_write = context.write(second_close)
    assert second_write.ok, f"el segundo context.write() no dio ok=True: {second_write!r}"

    read_back = context.latest()

    assert read_back is not None, (
        "context.latest() devolvio None -- un cierre real con contexto vacio "
        "se esta confundiendo con 'esto no es un cierre'"
    )
    _assert_context_fields_match(read_back, second_close)
    assert read_back.headline != first_close.headline, (
        "context.latest() devolvio el titular del PRIMER cierre -- un "
        "segundo cierre con contexto vacio no puede perderse frente a "
        "uno mas antiguo que si lo tenia"
    )
    assert read_back.context == "", (
        f"context.latest() deberia devolver el segundo cierre con su "
        f"contexto VACIO real, no el del primero: {read_back.context!r}"
    )


def test_close_session_from_a_plain_subfolder_of_the_same_repo_still_works(
    context, model, tmp_repo, monkeypatch
):
    """[GUARD] -- sigue funcionando igual que hoy desde una subcarpeta
    NORMAL del mismo repositorio (ningun repositorio anidado dentro, solo
    directorios corrientes). Es la fila 3 del encargo (DEUDA.md punto 25:
    "evita que el arreglo rompa el caso corriente"): no depende de ningun
    arreglo -- git ya resuelve `git commit` correctamente desde cualquier
    subcarpeta de un unico repositorio -- asi que este test debe seguir en
    VERDE antes y despues del arreglo de `commit_empty()`.
    """
    project_root = Path(tmp_repo)
    subfolder = project_root / "src" / "some" / "module"
    subfolder.mkdir(parents=True)

    note = _context_note(
        model,
        headline="MARK_SUBFOLDER_CONTEXT cierre lanzado desde una subcarpeta normal",
        context="cierre de sesion ejecutado desde src/some/module",
        keys=(),
    )

    monkeypatch.chdir(subfolder)
    write_result = context.write(note)

    assert write_result.ok, (
        f"context.write() no dio ok=True desde una subcarpeta normal del "
        f"mismo repositorio: {write_result!r}"
    )

    _rc, subject, _err = run_git(["log", "-1", "--format=%s"], str(project_root))
    assert "MARK_SUBFOLDER_CONTEXT" in subject, (
        "el cierre de sesion lanzado desde una subcarpeta normal del mismo "
        f"repositorio no aparece en su git log: {subject!r}"
    )
