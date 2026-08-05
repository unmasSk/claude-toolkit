"""Contrato ROJO de `bin/memory/search.py` -- PIEZAS.md Sec.10 (fila
`search.py`).

`bin/memory/search.py` NO EXISTE TODAVIA. Modo test-first, pase de
CONTRATO: aceptacion, no barrido exhaustivo.

De donde sale cada cosa:

- PIEZAS.md Sec.10, fila `search.py`: llama a `report.build_zone` ·
  `report.build_word` · `query.by_id` · `query.by_file`; admite
  "identificador, zona, palabra o fichero, `--todo`"; imprime "**siempre
  un informe, nunca una lista de commits**".
- spec-sistema-memoria-v2.md Sec.8.1, "El informe (unico producto de
  busqueda)": las CUATRO entradas literales -- "Por ID: `D-030` -> la
  nota y su racimo", "Por zona: `auth` -> estado completo de auth", "Por
  palabra: `stripe` -> estado completo de las zonas donde aparece", "Por
  fichero: `auth.service.ts` -> sus commits". Y el contrato duro: "Buscar
  devuelve el estado completo de una zona, NUNCA una lista de commits".
- TEXTOS.md Sec.2.3, dos pies de pagina reales que usan la MISMA forma
  posicional para los dos casos que difieren (zona vs palabra):
  `gitmem search billing` (zona) y `gitmem search stripe --todo`
  (palabra) -- evidencia literal, no supuesta, de que el mismo argumento
  posicional sirve para las dos entradas.

GRAMATICA DE CLI ASUMIDA para las dos entradas SIN evidencia posicional
directa (identificador, fichero) -- ningun texto del proyecto fija su
forma exacta:

    search.py <ZONA-o-PALABRA> [--todo]
    search.py --id <ID> [--todo]
    search.py --file <RUTA> [--todo]

El positional resuelve a zona si `zones.load()` lo reconoce (nombre
canonico o alias); si no, se trata como busqueda por palabra -- misma
lectura que ya hace `zones.resolve()` en produccion. `--id`/`--file`
quedan como flags explicitos, separados del positional, para no tener
que adivinar por la FORMA del texto (un identificador `D-030` podria
confundirse con una zona o palabra reales) -- marcado como ASUNCION, no
como hecho comprobado, mismo patron que ya declara `test_context_script.py`
para `--point`.

Round trip real, sin fabricar el texto esperado (unmassk-standards Sec.34):
para zona y palabra, el texto exacto que `search.py` tiene que imprimir
sale de llamar en el MISMO proceso de test a `report.build_zone`/
`report.build_word` + `report_render.render_zone`/`render_word` (las
piezas REALES, ya en produccion) con los mismos datos, normalizando la
unica parte que varia entre las dos llamadas por diseño (el `generated_at`
de cada informe, que usa `datetime.now()` por separado en cada invocacion
-- normalizado con una regex sobre la etiqueta ` UTC`, nunca comparando el
minuto exacto, para no depender de en que lado de un cruce de minuto cae
la ejecucion).

Siembra de datos real: via `note.py` como PROCESO (`seed_note_via_script`,
`conftest.py`) -- `note.py` ya existe y esta en verde, sembrar a traves de
el ejercita el camino completo (validador real incluido) en vez de
saltarselo.

Con el script inexistente, todos estos tests fallan hoy por la misma
causa real: `python3 <ruta inexistente>` -- ver docstring de
`test_note_script.py` para el detalle del mensaje.
"""

import contextlib
import os
import re

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    run_git,
    run_memory_script,
    seed_note_via_script,
    seed_zones_json,
)

_UTC_LABEL_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")


def _normalize_timestamps(text):
    return _UTC_LABEL_RE.sub("<UTC>", text)


@contextlib.contextmanager
def _cwd(path):
    """Mismo helper que en `test_notes.py`/`test_context_script.py`: las
    piezas de lectura (`report`/`query`) resuelven el repositorio por el
    cwd del proceso, sin declarar un parametro de raiz."""
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


@pytest.fixture
def report_lib():
    return import_lib_memory_module("report")


@pytest.fixture
def report_render_lib():
    return import_lib_memory_module("report_render")


@pytest.fixture
def format_lib():
    return import_lib_memory_module("format")


def _commit_sha_for_note(repo, note_id):
    """El commit que DECLARA `note_id` en su titular -- localizado con
    `git log --grep` anclado al principio del mensaje (`-E
    --grep=^[ID]`), para no casar un commit que solo CITA el id (p.ej. un
    hijo con `Origin: D-030` en el cuerpo). Camino de lectura
    completamente aparte de `query.by_id`/`report.build_zone`, que es lo
    que `search.py` usa por dentro."""
    rc, out, err = run_git(
        ["log", "--all", "-E", f"--grep=^\\[{note_id}\\]", "--format=%H"], repo,
    )
    assert rc == 0 and out.strip(), (
        f"no se encontro por git el commit de {note_id}: rc={rc} out={out!r} err={err!r}"
    )
    return out.splitlines()[0]


def _read_note_independently(repo, note_id, format_lib):
    """Lee `note_id` completo desde git por un camino DISTINTO del que usa
    `search.py` (`query.py`/`report.py`): sha localizado a mano
    (`_commit_sha_for_note`), cuerpo real via `git log --format=%B` y
    fecha de autor real via `git log --format=%aI`, parseados con
    `format.parse_message` -- el parser REAL de produccion, nunca una
    regex propia de este test [unmassk-standards Sec.34: lo que el
    informe imprime se compara contra algo escrito por separado, no
    contra si mismo]. `format.parse_message` no rellena `Note.timestamp`
    con la fecha real (usa un marcador `datetime.now()` -- ver el
    docstring de `query.py`), por eso la fecha de autor se lee y se
    devuelve aparte, tal y como hace `query.py` con `dataclasses.replace`.
    """
    sha = _commit_sha_for_note(repo, note_id)
    _, body, _ = run_git(["log", "-1", "--format=%B", sha], repo)
    _, author_date, _ = run_git(["log", "-1", "--format=%aI", sha], repo)
    note = format_lib.parse_message(body)
    assert note is not None, (
        f"format.parse_message no reconocio el commit de {note_id}: {body!r}"
    )
    return note, author_date


class TestAcceptsAllInputsWithoutBouncing:
    def test_zone_query_with_todo_flag_in_one_call(self, tmp_repo):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "auth", "product", "search contract seed memo",
            description="MARK description", stops="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        rc, out, err = run_memory_script("search.py", ["auth", "--todo"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err


class TestZoneQueryMatchesTheRealProducerRoundTrip:
    """`search.py auth` tiene que imprimir EXACTAMENTE lo que la pieza real
    (`report.build_zone` + `report_render.render_zone`) construye para los
    mismos datos -- nunca un texto reimplementado a mano en el script."""

    def test_zone_report_equals_report_render_render_zone_for_real(
        self, tmp_repo, report_lib, report_render_lib
    ):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "R", "auth", "product", "never log refresh tokens",
            why="a leaked token replays forever", description="MARK description",
            stops="yes",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        rc, out, err = run_memory_script("search.py", ["auth"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        with _cwd(tmp_repo):
            expected = report_render_lib.render_zone(report_lib.build_zone("auth", False))

        assert _normalize_timestamps(out.rstrip("\n")) == _normalize_timestamps(expected), (
            "search.py no reproduce byte a byte lo que construye la pieza real "
            "de informe -- ¿reimplementa su propio render?"
        )


class TestWordQueryMatchesTheRealProducerRoundTrip:
    def test_word_report_equals_report_render_render_word_for_real(
        self, tmp_repo, report_lib, report_render_lib
    ):
        seed_zones_json(tmp_repo, ["billing", "api"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "billing", "api",
            "the stripe webhook secret rotates per environment",
            description="MARK description", stops="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        rc, out, err = run_memory_script("search.py", ["stripe"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        with _cwd(tmp_repo):
            expected = report_render_lib.render_word(report_lib.build_word("stripe", False))

        assert _normalize_timestamps(out.rstrip("\n")) == _normalize_timestamps(expected), (
            "search.py no reproduce byte a byte lo que construye la pieza real "
            "de busqueda por palabra -- ¿reimplementa su propio render?"
        )


class TestTodoFlagChangesRealResultsByIncludingArchived:
    """`--todo` tiene que cambiar el resultado real -- no un flag que se
    acepta y no hace nada [PIEZAS.md Sec.10, "Sus tests" comun a los once:
    "un fallo sale por codigo de retorno distinto de cero" no aplica aqui,
    pero el mismo espiritu de "no aceptar y tirar" si]."""

    def test_archived_note_is_hidden_by_default_and_shown_with_todo(self, tmp_repo):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "auth", "product", "auth0 was never used here",
            description="MARK description", stops="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        rc_close, out_close, err_close = run_memory_script(
            "remove.py", [note_id, "superseded, kept for history", "--restriction", "no"],
            cwd=tmp_repo,
        )
        assert rc_close == 0, f"cierre fallo: stdout={out_close!r} stderr={err_close!r}"

        rc_default, out_default, err_default = run_memory_script(
            "search.py", ["auth"], cwd=tmp_repo
        )
        assert rc_default == 0, f"stdout={out_default!r} stderr={err_default!r}"
        assert note_id not in out_default, (
            f"una nota archivada NO puede aparecer sin --todo: {out_default!r}"
        )

        rc_todo, out_todo, err_todo = run_memory_script(
            "search.py", ["auth", "--todo"], cwd=tmp_repo
        )
        assert rc_todo == 0, f"stdout={out_todo!r} stderr={err_todo!r}"
        assert note_id in out_todo, (
            f"con --todo, una nota archivada tiene que aparecer: {out_todo!r}"
        )


class TestByIdNeverPrintsABareCommitList:
    """spec Sec.8.1, contrato duro: "Buscar devuelve el estado completo de
    una zona, NUNCA una lista de commits". Probado con una entrada por ID
    -- si el test acabara comparando contra una lista de hashes de commit,
    estaria mal planteado [encargo de esta tarea]."""

    def test_lookup_by_id_renders_through_the_real_report_box_not_a_commit_dump(
        self, tmp_repo, report_render_lib
    ):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "D", "auth", "product", "login with JWT and Google OAuth",
            why="sessions do not scale multi-tenant", description="MARK description",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        rc, out, err = run_memory_script("search.py", ["--id", note_id], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        # La caja real del informe (report_render._DIVIDER, constante de
        # produccion) tiene que aparecer -- prueba de que pasa por el
        # renderizador real de informes, no por un volcado de commits.
        assert report_render_lib._DIVIDER in out, (
            f"la salida de --id no pasa por report_render -- parece una lista "
            f"de commits, no un informe: {out!r}"
        )
        assert note_id in out
        assert "login with JWT and Google OAuth" in out


class TestFailureExitsNonzeroWithRealTextNoTraceback:
    def test_unknown_id_fails_without_a_traceback(self, tmp_repo):
        # `combined` tiene que NOMBRAR el identificador que fallo, no solo
        # "algo" -- con el script ausente, "no se pudo abrir el fichero"
        # tambien da rc!=0 y cero Traceback (el mismo pitfall que ya cazo
        # `test_context_script.py` sobre argparse); exigir el ID real como
        # contenido POSITIVO es lo que hace que este test siga en rojo hoy.
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc, out, err = run_memory_script("search.py", ["--id", "D-999"], cwd=tmp_repo)
        assert rc != 0, f"un identificador inexistente tiene que fallar: stdout={out!r}"
        combined = out + err
        assert "Traceback" not in combined
        assert "D-999" in combined, (
            f"el fallo tiene que nombrar el identificador que no existe: {combined!r}"
        )


class TestForceUtf8StreamsFirstStatement:
    def test_accented_zone_report_survives_a_restricted_console_encoding(self, tmp_repo):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "auth", "product", "decision tomada de palabra, sin codigo",
            description="con acentos: sesión, código, mañana", stops="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        rc, out, err = run_memory_script(
            "search.py", ["auth"], cwd=tmp_repo,
            env={"PYTHONIOENCODING": "cp1252", "LANG": "C", "LC_ALL": "C"},
        )
        combined = out + err
        assert "UnicodeEncodeError" not in combined
        assert "UnicodeDecodeError" not in combined
        assert "Traceback" not in combined
        assert rc == 0, f"una busqueda valida no deberia fallar bajo cp1252: {combined!r}"


# ---------------------------------------------------------------------------
# DEUDA.md #24 -- `search.py --id` devolvia el inventario de la ZONA entera
# (report_render.render_zone(report.build_zone(note.zone1, True))), no la
# nota pedida: ignoraba zone2, forzaba el archivado a True sin marca, y el
# pie seguia ofreciendo `--todo` que ya estaba arriba. El molde que fija el
# contrato acaba de escribirse [TEXTOS.md Sec.2.4, dictado por el
# propietario 2026-08-03] -- antes no existia ningun texto de referencia,
# que es la razon por la que este fallo llevaba desde el primer dia sin
# reparar [DEUDA.md #24]. Sus CINCO reglas, una clase de test por regla
# (mas la reproduccion literal del fallo, que es la segunda mitad de la
# regla 1):
#
#   1. Cabecera = LA NOTA (id + tipo en castellano + estado), no la zona.
#   2. Todos los campos del commit, con su nombre, alineados; uno vacio no
#      se imprime.
#   3. Las dos zonas juntas, con la fecha de escritura de la nota (no la
#      hora del informe).
#   4. El racimo por punteros Origin/Replaces debajo; sin nada que cuelgue,
#      el bloque entero no se imprime.
#   5. El pie ofrece la zona, nunca --todo (aqui lo archivado ya sale
#      marcado en el racimo).
#
# Con `bin/memory/search.py::_render_by_id` sin arreglar, todos los tests
# de aqui abajo fallan HOY por la causa real: la salida es el inventario
# completo de la zona (cabecera "ZONA auth ...", sin el id pedido en la
# cabecera, con --todo en el pie), no el informe de la nota que el molde
# fija. No fallan por un import roto ni por un fixture mal escrito.
# ---------------------------------------------------------------------------


class TestByIdRule1HeaderIsTheNoteWithTypeAndStatusNotTheZone:
    """Regla 1 [TEXTOS Sec.2.4]: la cabecera es la nota -- id, tipo en
    castellano, estado -- nunca el inventario de una zona."""

    def test_a_live_decision_shows_id_type_and_vigente_in_the_header(
        self, tmp_repo, format_lib
    ):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "D", "auth", "product", "login with JWT and Google OAuth",
            why="sessions do not scale multi-tenant", description="MARK description",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        rc, out, err = run_memory_script("search.py", ["--id", note_id], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        note, _author_date = _read_note_independently(tmp_repo, note_id, format_lib)
        assert note.type == "D"

        assert f"{note_id} · decisión · vigente" in out, (
            f"la cabecera tiene que llevar id + tipo en castellano + estado "
            f"[TEXTOS Sec.2.4, regla 1]: {out!r}"
        )
        assert "ZONA" not in out, (
            f"la cabecera NO puede ser la de una zona -- DEUDA.md #24: {out!r}"
        )

    def test_a_closed_incident_shows_archivada_and_never_its_live_sibling(
        self, tmp_repo
    ):
        """Reproduccion literal de DEUDA.md #24: `I-001` cerrada, `I-002`
        viva -- `search.py --id I-001` respondia `ZONA core · 1 vigentes
        · 1 archivadas` y listaba las DOS bajo INCIDENCIAS. Aqui tiene que
        enseñar SOLO la nota pedida, marcada `archivada`, sin ni rastro de
        la hermana viva."""
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc1, out1, err1 = seed_note_via_script(
            tmp_repo, "I", "auth", "product", "seeds wiped the users table",
            description="MARK description",
        )
        assert rc1 == 0, f"siembra 1 fallo: stdout={out1!r} stderr={err1!r}"
        first_id = extract_note_id(out1)

        rc_close, out_close, err_close = run_memory_script(
            "remove.py", [first_id, "fixed and documented", "--restriction", "no"],
            cwd=tmp_repo,
        )
        assert rc_close == 0, f"cierre fallo: stdout={out_close!r} stderr={err_close!r}"

        rc2, out2, err2 = seed_note_via_script(
            tmp_repo, "I", "auth", "product", "login loop on safari after cookie change",
            description="MARK description",
        )
        assert rc2 == 0, f"siembra 2 fallo: stdout={out2!r} stderr={err2!r}"
        second_id = extract_note_id(out2)

        rc, out, err = run_memory_script("search.py", ["--id", first_id], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        assert f"{first_id} · incidencia · archivada" in out, (
            f"una nota cerrada tiene que leerse como archivada en su propia "
            f"cabecera: {out!r}"
        )
        assert "vigente" not in out, (
            f"una nota archivada no puede decir vigente en ningun sitio: {out!r}"
        )
        assert second_id not in out, (
            f"pedir {first_id} no puede enseñar la nota viva hermana "
            f"{second_id} -- ese era exactamente el fallo de DEUDA.md #24 "
            f"(la zona entera mezclada, no la nota): {out!r}"
        )
        assert "ZONA" not in out


class TestByIdRule2AllCommitFieldsNamedAlignedAndNeverEmpty:
    """Regla 2 [TEXTOS Sec.2.4]: todos los campos del commit, con su
    nombre y alineados; un campo vacio no se imprime."""

    def test_present_fields_match_the_real_commit_and_are_aligned(
        self, tmp_repo, format_lib
    ):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "D", "auth", "product", "login with JWT and Google OAuth",
            why="sessions do not scale multi-tenant across companies",
            description="MARK description with real content to compare",
            keys=["token", "oauth"],
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        rc, out, err = run_memory_script("search.py", ["--id", note_id], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        note, _author_date = _read_note_independently(tmp_repo, note_id, format_lib)
        assert note.why in out
        assert note.description in out
        for key in note.keys:
            assert key in out, f"la key real {key!r} tiene que aparecer: {out!r}"

        label_lines = [
            line for line in out.splitlines()
            if re.match(r"^\s*(Why|Description|Keys)\s+\S", line)
        ]
        assert len(label_lines) == 3, (
            f"esperaba Why/Description/Keys, cada uno una vez: {label_lines!r} "
            f"en {out!r}"
        )
        value_columns = {
            len(re.match(r"^(\s*\S+\s+)\S", line).group(1)) for line in label_lines
        }
        assert len(value_columns) == 1, (
            f"Why/Description/Keys tienen que empezar su valor en la MISMA "
            f"columna -- 'alineados' [TEXTOS Sec.2.4, regla 2] -- columnas "
            f"distintas encontradas {value_columns}: {out!r}"
        )

    def test_an_absent_field_prints_no_label_at_all(self, tmp_repo):
        seed_zones_json(tmp_repo, ["infra", "deploy"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "B", "infra", "deploy", "the staging domain is not bought yet",
            description="MARK description", awaits="the user",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        rc, out, err = run_memory_script("search.py", ["--id", note_id], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        # Cabecera de la NOTA, no de la zona -- sin esto, un B suelto en
        # una zona con una sola nota pasaria en falso contra el `search.py`
        # de HOY (el dump de zona ya imprime "awaits:"/nunca "Why" para un
        # unico bloqueante, y este test estaria en verde por casualidad,
        # no porque el fallo de DEUDA.md #24 este arreglado).
        assert f"{note_id} · bloqueante · vigente" in out, (
            f"la cabecera tiene que ser la de la NOTA, no el inventario de "
            f"la zona [TEXTOS Sec.2.4, regla 1]: {out!r}"
        )
        # REVISADO [DEUDA.md B19 punto 4, 2026-08-03]: "awaits:" en todas
        # partes, tambien en el informe de nota -- ya no hay excepcion en
        # castellano para esta superficie (report_render_note.py linea 95).
        assert "awaits: the user" in out, (
            f"el campo real del bloqueante ('awaits:') tiene que salir: {out!r}"
        )
        assert "Why" not in out, (
            f"B no admite Why -- su etiqueta no puede aparecer nunca: {out!r}"
        )
        assert "Keys" not in out, (
            f"sin --keys, la etiqueta Keys es un campo vacio -- no se imprime "
            f"[TEXTOS Sec.2.4, regla 2]: {out!r}"
        )


class TestByIdRule3BothZonesWithTheNotesOwnWriteDate:
    """Regla 3 [TEXTOS Sec.2.4]: las dos zonas juntas, en su linea, con la
    fecha real en que se escribio la nota -- distinta de la hora del
    informe que va en la cabecera."""

    def test_both_zones_and_the_real_write_date_share_one_line(
        self, tmp_repo, format_lib
    ):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "auth", "product", "auth0 was never used here",
            description="MARK description", stops="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        rc, out, err = run_memory_script("search.py", ["--id", note_id], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        _note, author_date_iso = _read_note_independently(tmp_repo, note_id, format_lib)
        # `author_date_iso` es un ISO completo (`%aI`, leido de git, jamas
        # del informe); el molde solo promete la fecha corta ("escrita
        # 2026-04-11" -- YYYY-MM-DD), asi que se compara por ese prefijo.
        write_date = author_date_iso[:10]

        zones_lines = [line for line in out.splitlines() if "[auth] [product]" in line]
        assert len(zones_lines) == 1, (
            f"las DOS zonas tienen que aparecer juntas en UNA sola linea "
            f"[TEXTOS Sec.2.4, regla 3]: {out!r}"
        )
        assert write_date in zones_lines[0], (
            f"la fecha REAL de escritura de la nota (leida de git, no del "
            f"informe) tiene que estar en la MISMA linea que las zonas: "
            f"{write_date!r} no esta en {zones_lines[0]!r}"
        )


class TestByIdRule4ClusterByPointersOnlyWhenSomethingHangsFromIt:
    """Regla 4 [TEXTOS Sec.2.4]: el racimo por punteros Origin/Replaces
    debajo de la nota; si no cuelga nada, el bloque entero no se
    imprime."""

    def test_two_discards_and_a_child_restriction_all_hang_from_the_root(
        self, tmp_repo
    ):
        """Tres hijos por `Origin`, como el propio racimo de ejemplo de
        TEXTOS Sec.2.4 (X-012/X-013/R-018, los tres `nace de D-030`).

        NO se usa una segunda `D` como tercer hijo -- se probo primero, y
        `vocabulary.TYPES["D"].allowed_fields` (ya en produccion) NO
        incluye `origin` (solo `replaces`): el validador real rechaza
        `note.py D ... --origin <id>` con "Estos campos no existen para
        el tipo D: origin", verificado en vivo. El propio molde de
        TEXTOS Sec.2.1/2.4 SI muestra una D (`D-041`) colgando de otra D
        por `Origin` -- es una pieza que falta (el vocabulario cerrado y
        el molde no estan de acuerdo), reportada aparte, no inventada
        aqui con un rodeo. Este test usa el otro hijo que el MISMO
        racimo de ejemplo trae y que si es construible hoy: `R-018`."""
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_root, out_root, err_root = seed_note_via_script(
            tmp_repo, "D", "auth", "product", "login with JWT and Google OAuth",
            why="sessions do not scale multi-tenant", description="MARK description",
        )
        assert rc_root == 0, f"siembra raiz fallo: stdout={out_root!r} stderr={err_root!r}"
        root_id = extract_note_id(out_root)

        rc_x1, out_x1, err_x1 = seed_note_via_script(
            tmp_repo, "X", "auth", "product", "server-side sessions",
            description="MARK description", origin=[root_id],
        )
        assert rc_x1 == 0, f"siembra descarte 1 fallo: stdout={out_x1!r} stderr={err_x1!r}"
        x1_id = extract_note_id(out_x1)

        rc_x2, out_x2, err_x2 = seed_note_via_script(
            tmp_repo, "X", "auth", "product", "own password login",
            description="MARK description", origin=[root_id],
        )
        assert rc_x2 == 0, f"siembra descarte 2 fallo: stdout={out_x2!r} stderr={err_x2!r}"
        x2_id = extract_note_id(out_x2)

        rc_child, out_child, err_child = seed_note_via_script(
            tmp_repo, "R", "auth", "product",
            "no auth deploy on Friday without a tested rollback",
            why="MARK why", description="MARK description", stops="yes",
            origin=[root_id],
        )
        assert rc_child == 0, (
            f"siembra restriccion hija fallo: stdout={out_child!r} stderr={err_child!r}"
        )
        child_id = extract_note_id(out_child)

        rc, out, err = run_memory_script("search.py", ["--id", root_id], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        assert "LO QUE CUELGA DE ELLA" in out, (
            f"con tres notas colgando de la raiz, el bloque tiene que "
            f"imprimirse [TEXTOS Sec.2.4, regla 4]: {out!r}"
        )
        assert f"nace de {root_id}" in out, (
            f"el racimo se arma por punteros, con la leyenda literal del "
            f"molde: {out!r}"
        )

        lines_by_id = {}
        for line in out.splitlines():
            for candidate in (x1_id, x2_id, child_id):
                if candidate in line:
                    lines_by_id[candidate] = line

        assert x1_id in lines_by_id and "descartada" in lines_by_id[x1_id], (
            f"el descarte 1 tiene que salir marcado descartada: {out!r}"
        )
        assert x2_id in lines_by_id and "descartada" in lines_by_id[x2_id], (
            f"el descarte 2 tiene que salir marcado descartada: {out!r}"
        )
        assert child_id in lines_by_id and "vigente" in lines_by_id[child_id], (
            f"la restriccion hija (no archivada) tiene que salir marcada "
            f"vigente: {out!r}"
        )

    def test_an_orphan_note_prints_no_cluster_block_at_all(self, tmp_repo):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "auth", "product", "the JWT carries tenant_id",
            description="MARK description", stops="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        rc, out, err = run_memory_script("search.py", ["--id", note_id], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        # La ausencia sola no basta como señal de rojo real -- HOY el
        # titulo tampoco existe en NINGUN lado del sistema, asi que la
        # sola ausencia pasaria en falso incluso sin el arreglo. Se ata a
        # la cabecera de la nota (que SI cambia con el arreglo) para que
        # este test falle por la causa real -- DEUDA.md #24 -- y no por
        # casualidad.
        assert f"{note_id} · memo · vigente" in out, (
            f"la cabecera tiene que ser la de la NOTA, no el inventario de "
            f"la zona [TEXTOS Sec.2.4, regla 1]: {out!r}"
        )
        assert "LO QUE CUELGA DE ELLA" not in out, (
            f"una nota huerfana no puede imprimir el bloque del racimo -- "
            f"un titular vacio es ruido [TEXTOS Sec.2.4, regla 4]: {out!r}"
        )


class TestByIdRule5FooterOffersTheZoneNeverTodo:
    """Regla 5 [TEXTOS Sec.2.4]: el pie ofrece la zona, nunca --todo --
    aqui lo archivado ya sale marcado en el racimo, asi que ofrecer 'ver
    lo archivado' mentiria, que es exactamente el defecto que este molde
    viene a corregir."""

    def test_footer_points_to_the_zone_and_never_mentions_todo(self, tmp_repo):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "auth", "product", "auth0 was never used here",
            description="MARK description", stops="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        rc, out, err = run_memory_script("search.py", ["--id", note_id], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        assert "gitmem search auth" in out, (
            f"el pie tiene que ofrecer la ZONA de la nota: {out!r}"
        )
        assert "--todo" not in out, (
            f"ofrecer --todo aqui mentiria: lo archivado ya sale marcado en "
            f"el racimo [TEXTOS Sec.2.4, regla 5, y DEUDA.md #24 punto 3]: "
            f"{out!r}"
        )
