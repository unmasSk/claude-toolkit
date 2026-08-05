"""Contrato en ROJO -- una nota CERRADA no puede bloquear un alta parecida.

EL FALLO, encontrado ejecutandolo y confirmado leyendo el codigo real
(no supuesto): `lib/memory/query.py::by_zone()` (linea 236-245) devuelve
lo que sale de `_all_notes()` -- TODO el historial de git, notas vivas
Y notas ya cerradas/sustituidas/ascendidas por igual, sin mirar si el id
sigue en su indice vigente o ya se movio a `ARCHIVED.md`. `bin/memory/
note.py::_build_context()` (linea 133) pasa ese resultado tal cual como
`existing_in_zone` al `Context` del validador, y
`validator.py::validate_replacement()` (linea 371-426) lo usa entero
para decidir si algo "pisa a algo que ya esta escrito" -- una nota
cerrada hace meses sigue contando como si estuviera viva.

CASO REAL que dispara esto (encargo del orquestador, marzo/octubre): se
anota una incidencia, se arregla y se CIERRA -- sale de `INCIDENTS.md`,
queda en `ARCHIVED.md` con `closed: <motivo>`. Meses despues la misma
clase de fallo vuelve a pasar; al anotar la incidencia NUEVA, el sistema
la para diciendo que pisa a la vieja -- que esta cerrada -- y ofrece
`--replaces <id>` como una de las tres salidas. Para el tipo `I`,
`--replaces` NI SIQUIERA es un campo permitido
(`vocabulary.TYPES["I"].allowed_fields == frozenset({"description",
"why", "keys"})`, verificado leyendo `vocabulary.py` antes de escribir
esto) -- el rechazo ofrece una salida que el propio sistema rechazaria
si se intentara.

LA REGLA [decision del propietario, 2026-08-05]: "si sale una nueva
incidencia, es una nueva incidencia; la otra ya se cerro, aunque sea
sobre lo mismo". Lo archivado es historia y no bloquea nada. Lo que SI
debe seguir bloqueando es que la anterior siga ABIERTA -- ahi si es un
duplicado de verdad.

Ejecutado con `bin/gitmem` (la fachada), contra un `tmp_repo` temporal
-- nunca importando `notes.py`/`validator.py` en proceso, y nunca este
repositorio (`conftest.py::_guard_against_writing_to_the_real_repo` lo
impediria de todas formas). `gitmem note`/`gitmem remove` despachan por
ruta a `bin/memory/note.py`/`bin/memory/remove.py` sin anadir logica
propia [docstring de `bin/gitmem`], asi que ejercitar la fachada es
ejercitar el camino real de un usuario.

**Similitud garantizada sin depender de la formula exacta de
`similar.py`:** cada pareja "vieja"/"nueva" de este fichero comparte
headline y description LITERALMENTE IDENTICOS -- Jaccard = 1.0, muy por
encima de `vocabulary.SIMILARITY_THRESHOLD` (0.5). Ningun test de aqui
depende de contar palabras a mano.

**Por que `--stops no` en las M y nada en las I:**
`validator.validate_pain_question` solo aplica a M/R
(`note.type not in ("M", "R"): return None`), verificado en
`validator.py`. Las I no la necesitan.

**Por que la nota B de la fila 4 nace con `--replaces none`:** hoy
(antes del arreglo) `existing_in_zone` YA incluye a la nota archivada
del mismo texto -- si B no llevara `--replaces none`, su propia
alta rebotaria contra la archivada, y el test nunca llegaria a probar
lo que quiere probar (que una nota VIVA, no la archivada, es la que
tiene que seguir bloqueando). `--replaces none` es el centinela real
["conviven las dos, a proposito" -- `validator.py::
validate_replacement`, docstring] que hace que `validate_replacement`
se salte sin mirar candidatos (`if note.replaces is not None: return
None`) -- no un atajo del test, es el mismo mecanismo que
`note-script-replaces-not-archiving-regression-notes` ya documenta.

Cada test lee el resultado de fuentes escritas por separado: la
salida real de `gitmem` (¿rebota o no?) contra los indices/archivo
REALES leidos con el lector real (`indexes.read`/`indexes.read_archive`)
-- nunca un texto de rechazo tecleado a mano ni un id inventado.
"""

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_gitmem_script,
    seed_zones_json,
)

import pytest


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


_SHARED_HEADLINE = "csv export crashes once a report exceeds 5000 rows"
_SHARED_DESCRIPTION = (
    "the nightly export job throws a timeout in production whenever a "
    "report contains more than 5000 rows, and finance cannot download it"
)


def _write_m(repo, zone1, zone2, *, replaces=None):
    """Da de alta una M con el texto compartido (headline+description
    identicos entre llamadas -- Jaccard=1.0 contra cualquier otra M
    escrita con este mismo helper). Devuelve (rc, out, err)."""
    args = [
        "note", "M",
        "--zones", zone1, zone2,
        _SHARED_HEADLINE,
        "--description", _SHARED_DESCRIPTION,
        "--stops", "no",
    ]
    if replaces is not None:
        args += ["--replaces", replaces]
    return run_gitmem_script(args, cwd=repo)


def _write_i(repo, zone1, zone2):
    """Da de alta una I con el texto compartido. `I` no pasa por
    `validate_pain_question` (solo M/R) -- ver docstring del modulo."""
    args = [
        "note", "I",
        "--zones", zone1, zone2,
        _SHARED_HEADLINE,
        "--description", _SHARED_DESCRIPTION,
    ]
    return run_gitmem_script(args, cwd=repo)


class TestClosedNoteDoesNotBlockASimilarNewNote:
    """Fila 1 del contrato: escribe una nota, ciérrala, y escribe otra muy
    parecida en la misma pareja de zonas -- tiene que entrar SIN rechazo.
    Comprobado con los indices reales, no con la salida del comando."""

    def test_note_closed_via_gitmem_remove_no_longer_blocks_a_similar_alta(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "exports"])

        rc_old, out_old, err_old = _write_m(tmp_repo, "product", "exports")
        assert rc_old == 0, f"stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)

        rc_close, out_close, err_close = run_gitmem_script(
            ["remove", old_id, "fixed by paginating the export query"],
            cwd=tmp_repo,
        )
        assert rc_close == 0, f"el cierre tiene que salir bien: stdout={out_close!r} stderr={err_close!r}"

        pm = pm_path(tmp_repo)
        archived_before = indexes.read_archive(pm)
        assert any(line.id == old_id for line in archived_before), (
            f"precondicion del test: {old_id} tiene que estar ya en ARCHIVED.md "
            f"antes de intentar la nota nueva -- {archived_before!r}"
        )

        rc_new, out_new, err_new = _write_m(tmp_repo, "product", "exports")
        assert rc_new == 0, (
            "una nota CERRADA no puede bloquear el alta de una parecida -- "
            f"tiene que entrar sin rechazo. stdout={out_new!r} stderr={err_new!r}"
        )
        new_id = extract_note_id(out_new)

        live_ids = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert new_id in live_ids, f"la nueva tiene que quedar vigente: {sorted(live_ids)!r}"
        assert old_id not in live_ids, (
            f"la vieja sigue cerrada, no puede reaparecer en el indice vigente: "
            f"{sorted(live_ids)!r}"
        )


class TestLiveNoteStillBlocksASimilarNewNote:
    """Fila 2 (control): el mismo caso SIN cerrar la primera -- tiene que
    rebotar, y el rechazo tiene que ensenar la candidata real. Este es el
    comportamiento que YA funciona hoy; el arreglo de la fila 1 no puede
    romperlo."""

    def test_note_left_open_still_bounces_a_similar_alta_naming_the_candidate(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "exports"])

        rc_old, out_old, err_old = _write_m(tmp_repo, "product", "exports")
        assert rc_old == 0, f"stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)
        # Nunca cerrada -- sigue vigente en MEMOS.md.

        rc_new, out_new, err_new = _write_m(tmp_repo, "product", "exports")
        assert rc_new != 0, (
            "una nota VIVA parecida tiene que seguir bloqueando el alta: "
            f"stdout={out_new!r} stderr={err_new!r}"
        )
        combined = out_new + err_new
        assert "Traceback" not in combined
        assert old_id in combined, (
            f"el rechazo tiene que ensenar la candidata real ({old_id}), "
            f"no un aviso generico: {combined!r}"
        )

        pm = pm_path(tmp_repo)
        live_ids = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert live_ids == {old_id}, (
            f"la nota rechazada no puede haber entrado en el indice: {sorted(live_ids)!r}"
        )


class TestIncidentClosedThenReopenedEndToEnd:
    """Fila 3 -- el caso de la incidencia, entero y de punta a punta:
    incidencia -> cerrada -> incidencia nueva parecida -> entra, y las dos
    quedan donde tienen que estar: la vieja en el archivo con su motivo,
    la nueva viva en su indice."""

    def test_incident_reopened_months_later_enters_clean_while_old_stays_archived(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "exports"])

        rc_march, out_march, err_march = _write_i(tmp_repo, "product", "exports")
        assert rc_march == 0, f"stdout={out_march!r} stderr={err_march!r}"
        march_id = extract_note_id(out_march)

        rc_close, out_close, err_close = run_gitmem_script(
            ["remove", march_id, "paginated the export query", "--restriction", "no"],
            cwd=tmp_repo,
        )
        assert rc_close == 0, (
            f"cerrar la incidencia de marzo tiene que salir bien: "
            f"stdout={out_close!r} stderr={err_close!r}"
        )

        rc_october, out_october, err_october = _write_i(tmp_repo, "product", "exports")
        assert rc_october == 0, (
            "la incidencia nueva (misma clase de fallo, meses despues) tiene que "
            f"entrar SIN rechazo -- la de marzo ya esta cerrada: "
            f"stdout={out_october!r} stderr={err_october!r}"
        )
        october_id = extract_note_id(out_october)
        assert october_id != march_id

        pm = pm_path(tmp_repo)
        live_ids = {line.id for line in indexes.read("INCIDENTS.md", pm)}
        assert live_ids == {october_id}, (
            f"solo la de octubre tiene que quedar vigente en INCIDENTS.md: "
            f"{sorted(live_ids)!r}"
        )

        archived = indexes.read_archive(pm)
        archived_by_id = {line.id: line for line in archived}
        assert march_id in archived_by_id, (
            f"la de marzo tiene que seguir en ARCHIVED.md: {sorted(archived_by_id)!r}"
        )
        march_line = archived_by_id[march_id]
        assert march_line.destination == "closed", (
            f"destino real de la de marzo: {march_line.destination!r}"
        )
        assert march_line.destination_detail == "paginated the export query", (
            f"motivo real archivado: {march_line.destination_detail!r}"
        )
        assert october_id not in archived_by_id, (
            "la de octubre, recien creada y vigente, no puede aparecer en "
            f"ARCHIVED.md: {sorted(archived_by_id)!r}"
        )


class TestArchivedNoteIsIgnoredButALiveDuplicateStillBlocks:
    """Fila 4 -- lo que no puede pasar: que al dejar de mirar lo archivado
    se cuele un duplicado de algo VIVO. Siembra una vieja (cerrada) y una
    B (viva, mismo texto, dada de alta con `--replaces none` para no
    chocar con la vieja archivada) en la misma pareja de zonas; la nota
    nueva tiene que seguir rebotando -- por B, nunca "porque ya no hay
    nada archivado que mirar"."""

    def test_new_similar_note_still_bounces_against_the_live_one_not_the_archived_one(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "exports"])

        rc_a, out_a, err_a = _write_m(tmp_repo, "product", "exports")
        assert rc_a == 0, f"stdout={out_a!r} stderr={err_a!r}"
        old_a_id = extract_note_id(out_a)

        rc_close, out_close, err_close = run_gitmem_script(
            ["remove", old_a_id, "fixed by paginating the export query"],
            cwd=tmp_repo,
        )
        assert rc_close == 0, f"stdout={out_close!r} stderr={err_close!r}"

        # `--replaces none`: centinela real, "conviven a proposito" -- sin
        # esto, dar de alta B chocaria hoy contra A (todavia archivada,
        # todavia visible para el validador con el fallo sin arreglar).
        rc_b, out_b, err_b = _write_m(tmp_repo, "product", "exports", replaces="none")
        assert rc_b == 0, f"stdout={out_b!r} stderr={err_b!r}"
        live_b_id = extract_note_id(out_b)

        pm = pm_path(tmp_repo)
        live_ids_before = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert live_ids_before == {live_b_id}, (
            f"precondicion del test: solo B tiene que estar vigente antes del "
            f"tercer alta: {sorted(live_ids_before)!r}"
        )

        rc_new, out_new, err_new = _write_m(tmp_repo, "product", "exports")
        assert rc_new != 0, (
            "una nota VIVA (B) parecida tiene que seguir bloqueando el alta, "
            f"aunque haya una archivada con el mismo texto al lado: "
            f"stdout={out_new!r} stderr={err_new!r}"
        )
        combined = out_new + err_new
        assert "Traceback" not in combined
        assert live_b_id in combined, (
            f"el rechazo tiene que nombrar a la candidata VIVA (B, {live_b_id}): "
            f"{combined!r}"
        )
        assert old_a_id not in combined, (
            f"el rechazo NO puede nombrar a la candidata ARCHIVADA (A, {old_a_id}) "
            f"-- esta cerrada, no es una candidata real: {combined!r}"
        )

        live_ids_after = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert live_ids_after == {live_b_id}, (
            f"la nota rechazada no puede haber entrado en el indice: "
            f"{sorted(live_ids_after)!r}"
        )
