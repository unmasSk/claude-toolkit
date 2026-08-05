"""Contrato ROJO (pase de aceptacion, modo test-first): cerrar una
incidencia sin decir si de ella nace un muro no puede reventar con el
error crudo de argparse -- el sistema pregunta.

Encargo del propietario, decision del 2026-08-04 (guardada en memoria como
`decision(plugin/memoria-v2)`): P5, `docs/spec-sistema-memoria-v2.md` Sec.2
-- "toda pregunta del sistema es un rechazo cuyo mensaje contiene la
pregunta y las opciones; responder es relanzar el comando con la respuesta
como argumento". El molde exacto es TEXTOS.md Sec.1.10 ("Cierre de
incidencia: ¿sale muro?", ejemplo I-014).

A QUIEN AFECTA -- no es todo cierre. La pregunta es del cierre de
INCIDENCIA (`I-...`) -- spec Sec.11 punto 5. Una M o una D se cierran sin
que se les pregunte nada (TEXTOS.md Sec.1.10 solo describe este flujo para
una I).

ESTADO REAL HOY: `bin/memory/remove.py:53` declara `--restriction` con
`required=True` para TODO tipo de nota por igual. Cerrar una I sin el flag
revienta con el error crudo de argparse ("... the following arguments are
required: --restriction"), no con el rechazo del molde; y cerrar una M o
una D sin el flag revienta EXACTAMENTE IGUAL, aunque a esas dos no les
corresponde ninguna pregunta. Los tests de este fichero fallan hoy por esa
misma causa real -- ROJO por la razon correcta, nunca por una excepcion sin
relacion.

DOS COSAS ESCRITAS POR SEPARADO, COMPARADAS (regla de esta rama -- CLAUDE.md:
"un test entra solo si compara dos cosas escritas por separado"): lo que
`remove.py` IMPRIME como comando de relanzamiento contra lo que
`gitmem`/`remove.py` de verdad ACEPTAN y EJECUTAN. Los dos comandos de la
pregunta nunca se reteclean a mano en este fichero -- se EXTRAEN de la
salida real (regex sobre lineas `gitmem remove ...`) y se relanzan tal
cual, sustituyendo solo el placeholder `"..."` por texto de prueba (mismo
placeholder que ya usa `validator.py::validate_similar` para el mismo tipo
de hueco -- "esperar" un valor que el sistema no puede conocer de
antemano).

NO HAY ATACANTE EXTERNO en esta rama (CLAUDE.md): lo que se vigila es que
el sistema no se rompa a si mismo -- una incidencia que se cierra sin
querer con un `--restriction` mal puesto, un muro que nace sin que nadie
lo pidiera, un indice que queda desincronizado de ARCHIVED.md.

PARA QUIEN IMPLEMENTE (Ultron): `lib/memory/rejection.py::build()` ya
documenta este rechazo exacto en su propio docstring -- "el rechazo del
cierre de incidencia, TEXTOS Sec.1.10, ofrece dos [comandos] segun la
respuesta" -- y `tests/memory/test_rejection_relaunch_commands.py` escanea
el AST de SEIS ficheros (`validator.py`, `validator_zones.py`,
`validator_pointers.py`, `validator_issue.py`, `rejection.py`,
`hooks/customs.py`) buscando asignaciones `command = (...)` /
`relaunch = (...)` -- `bin/memory/remove.py` NO esta en esa lista. Si el
texto de este rechazo se escribe dentro de `remove.py` a mano (en vez de
construirse via una funcion de `validator.py` que devuelva un `Rejection`
con `rejection_.build(kind=..., command=(cmd_no, cmd_new))`, como ya hacen
`validate_similar`/`validate_distillation` en ese mismo fichero), los dos
comandos de relanzamiento quedan fuera del radar de ese vigilante -- lo
esquivan sin que nadie lo note. Este fichero no puede forzar donde vive el
codigo real (eso es implementacion), pero SI deja constancia del porque
importa: sitios ya escaneados vs. sitios que no.
"""

import contextlib
import os
import re
import shlex

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_gitmem_script,
    run_memory_script,
    seed_note_via_script,
    seed_zones_json,
)


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
    """Mismo helper que `test_remove_script.py`/`test_notes.py` -- ver su
    docstring para el porque exacto (varias piezas resuelven el
    repositorio por el cwd del proceso, sin un parametro de raiz)."""
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _seed_incident(
    tmp_repo,
    zone1,
    zone2,
    headline,
    description="MARK_CAUSA root cause: a stray environment variable pointed CI at production",
):
    seed_zones_json(tmp_repo, [zone1, zone2])
    rc, out, err = seed_note_via_script(
        tmp_repo, "I", zone1, zone2, headline, description=description,
    )
    assert rc == 0, (
        f"la siembra real de la incidencia fallo, no es parte de lo que "
        f"este contrato prueba: stdout={out!r} stderr={err!r}"
    )
    return extract_note_id(out)


_RELAUNCH_LINE_RE = re.compile(r"^\s*(gitmem remove \S+.*)$", re.MULTILINE)


def _extract_relaunch_commands(combined, note_id):
    """Lineas `gitmem remove <note_id> ...` presentes en la salida real --
    extraidas con una expresion regular sobre lo que `remove.py` IMPRIMIO
    de verdad, nunca escritas a mano en este fichero (regla de esta
    rama: comparar dos cosas escritas por separado)."""
    return [line.strip() for line in _RELAUNCH_LINE_RE.findall(combined) if note_id in line]


def _fill_ellipsis_placeholders(command_line, replacements):
    """Sustituye cada `"..."` de `command_line`, EN ORDEN DE APARICION, por
    el texto de `replacements` -- nunca por posicion de flag a mano: para
    lo que este fichero comprueba (que el comando FUNCIONA de verdad al
    relanzarlo) el contenido de cada hueco es intercambiable, no importa
    cual placeholder cae en cual flag. Revienta si el numero de
    placeholders no coincide EXACTAMENTE con lo que se le paso, para que
    un cambio de forma en el comando impreso se vea aqui como fallo
    explicito, no como un `shlex`/`gitmem` reventando mas abajo por otra
    razon."""
    count = command_line.count('"..."')
    assert count == len(replacements), (
        f"se esperaban {len(replacements)} placeholders '\"...\"' y se "
        f"encontraron {count} en {command_line!r}"
    )
    it = iter(replacements)
    return re.sub(r'"\.\.\."', lambda _match: f'"{next(it)}"', command_line)


class TestClosingAnIncidentWithoutTheFlagAsksInsteadOfCrashing:
    """Punto 1 del encargo: sin `--restriction`, NO sale el error crudo de
    argparse -- sale el rechazo del molde [TEXTOS.md Sec.1.10], y la nota
    NO se cierra."""

    def test_no_flag_bounces_with_the_question_not_a_raw_argparse_error(
        self, tmp_repo, indexes,
    ):
        incident_id = _seed_incident(
            tmp_repo, "testing", "auth", "MARK seeds wiped the production users table",
        )
        pm = pm_path(tmp_repo)
        incidents_before = (pm / "INCIDENTS.md").read_bytes()
        archived_before = (pm / "ARCHIVED.md").read_bytes()

        rc, out, err = run_memory_script(
            "remove.py",
            [incident_id, "fixed in #58, root cause found"],
            cwd=tmp_repo,
        )

        assert rc != 0, (
            f"cerrar una incidencia sin --restriction tiene que rebotar: "
            f"stdout={out!r} stderr={err!r}"
        )
        combined = out + err
        assert "Traceback" not in combined

        assert "usage:" not in combined.lower(), (
            f"salio el error crudo de argparse en vez del rechazo del "
            f"molde con la pregunta dentro: {combined!r}"
        )
        assert "required" not in combined.lower(), (
            f"salio el mensaje generico de argparse ('the following "
            f"arguments are required') en vez del rechazo con la "
            f"pregunta: {combined!r}"
        )
        assert incident_id in combined, (
            f"el rechazo tiene que nombrar la incidencia por su id: {combined!r}"
        )
        assert "muro" in combined.lower(), (
            f"el rechazo tiene que mencionar el muro que puede nacer de "
            f"esta incidencia: {combined!r}"
        )

        commands = _extract_relaunch_commands(combined, incident_id)
        no_cmd = [c for c in commands if "--restriction no" in c]
        new_cmd = [c for c in commands if "--restriction new" in c]
        assert len(no_cmd) == 1, (
            f"deberia ofrecer exactamente un comando de relanzamiento con "
            f"'--restriction no': {combined!r}"
        )
        assert len(new_cmd) == 1, (
            f"deberia ofrecer exactamente un comando de relanzamiento con "
            f"'--restriction new': {combined!r}"
        )

        for cmd in no_cmd + new_cmd:
            tokens = shlex.split(cmd)
            assert tokens[0] == "gitmem" and tokens[1] == "remove" and tokens[2] == incident_id, (
                f"comando de relanzamiento mal formado, no tokeniza como "
                f"'gitmem remove {incident_id} ...': {cmd!r}"
            )

        new_tokens = shlex.split(new_cmd[0])
        assert "--restriction-text" in new_tokens, (
            f"el comando '--restriction new' tiene que traer "
            f"--restriction-text, que remove.py exige de verdad "
            f"(bin/memory/remove.py::_guard_restriction_new): {new_cmd[0]!r}"
        )
        assert "--why" in new_tokens, (
            f"el comando '--restriction new' deberia ofrecer --why, mismo "
            f"campo que _fence_retry_command ya usa para el muro: {new_cmd[0]!r}"
        )

        # El cierre NO ocurrio -- indice y archivo, byte a byte, igual que
        # antes de intentar el comando (round trip real, no supuesto).
        assert (pm / "INCIDENTS.md").read_bytes() == incidents_before, (
            f"{incident_id} no deberia haberse tocado en su indice todavia "
            f"-- la pregunta retiene el cierre, no lo hace a medias"
        )
        assert (pm / "ARCHIVED.md").read_bytes() == archived_before, (
            f"{incident_id} no deberia haber entrado en ARCHIVED.md todavia"
        )
        assert any(line.id == incident_id for line in indexes.read("INCIDENTS.md", pm)), (
            f"{incident_id} deberia seguir vigente en INCIDENTS.md"
        )


class TestClosingANonIncidentWithoutTheFlagJustClosesNoQuestionAsked:
    """Punto 4 del encargo: a una M o una D no se les pregunta nada -- se
    cierran directamente, sin `--restriction`, sin mencion de ningun
    muro."""

    @pytest.mark.parametrize(
        "note_type, index_file, headline, extra_seed_kwargs",
        [
            (
                "M", "MEMOS.md", "MARK a plain memo, not an incident",
                # Toda M contesta la pregunta del dolor [TEXTOS.md Sec.1.6]
                # antes de entrar -- "no" para que quede como M, no como R.
                {"stops": "no"},
            ),
            (
                "D", "DECISIONS.md", "MARK a decision, not an incident",
                # Toda D exige `why` [vocabulary.py, campos obligatorios
                # por tipo] -- ajeno a este contrato, solo hace falta para
                # que la siembra en si no rebote.
                {"why": "MARK_WHY not empty, required by the vocabulary for type D"},
            ),
        ],
    )
    def test_closes_directly_without_any_restriction_question(
        self, tmp_repo, indexes, note_type, index_file, headline, extra_seed_kwargs,
    ):
        zone1, zone2 = "product", "billing"
        seed_zones_json(tmp_repo, [zone1, zone2])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, note_type, zone1, zone2, headline,
            description="MARK_DESC not empty, required by the vocabulary",
            **extra_seed_kwargs,
        )
        assert rc_seed == 0, f"la siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)
        pm = pm_path(tmp_repo)
        assert any(line.id == note_id for line in indexes.read(index_file, pm))

        rc, out, err = run_memory_script(
            "remove.py",
            [note_id, "closed without any fence question"],
            cwd=tmp_repo,
        )

        assert rc == 0, (
            f"una {note_type} no deberia preguntar nada al cerrarse, ni "
            f"exigir --restriction: stdout={out!r} stderr={err!r}"
        )
        combined = out + err
        assert "Traceback" not in combined
        assert "muro" not in combined.lower(), (
            f"a una {note_type} no le corresponde la pregunta del muro: {combined!r}"
        )

        assert not any(line.id == note_id for line in indexes.read(index_file, pm)), (
            f"{note_id} deberia haber salido de {index_file}"
        )
        archived = [a for a in indexes.read_archive(pm) if a.id == note_id]
        assert len(archived) == 1, f"deberia haber exactamente una linea de archivo para {note_id}"
        assert archived[0].destination == "closed"
        assert archived[0].destination_detail == "closed without any fence question"


class TestRelaunchCommandsExtractedFromTheQuestionActuallyWork:
    """Puntos 2, 3 y 5 del encargo -- y el hueco anotado en DEUDA.md #6.4
    ("falta la prueba de que crear el muro con exito funciona"). Los
    comandos no se retiplean a mano: se extraen de la salida REAL de la
    pregunta y se relanzan tal cual, con solo el placeholder rellenado."""

    def test_the_no_relaunch_command_closes_the_incident_for_real(
        self, tmp_repo, indexes,
    ):
        incident_id = _seed_incident(
            tmp_repo, "testing", "seedbug", "MARK a first seeds incident, --restriction no path",
        )
        rc, out, err = run_memory_script(
            "remove.py",
            [incident_id, "placeholder reason, ignored -- the question retains the close"],
            cwd=tmp_repo,
        )
        assert rc != 0
        combined = out + err
        no_cmd = [c for c in _extract_relaunch_commands(combined, incident_id) if "--restriction no" in c]
        assert len(no_cmd) == 1, f"no se encontro el comando '--restriction no' en la salida: {combined!r}"

        reason_text = "MARK_REASON root cause was a stray env var, fixed in #58"
        filled = _fill_ellipsis_placeholders(no_cmd[0], [reason_text])
        tokens = shlex.split(filled)
        assert tokens[0] == "gitmem"

        rc_retry, out_retry, err_retry = run_gitmem_script(tokens[1:], cwd=tmp_repo)
        assert rc_retry == 0, (
            f"el comando extraido de la pregunta no funciono al relanzarlo "
            f"tal cual: stdout={out_retry!r} stderr={err_retry!r}"
        )

        pm = pm_path(tmp_repo)
        assert not any(line.id == incident_id for line in indexes.read("INCIDENTS.md", pm)), (
            f"{incident_id} deberia haber salido de INCIDENTS.md"
        )
        archived = [a for a in indexes.read_archive(pm) if a.id == incident_id]
        assert len(archived) == 1
        assert archived[0].destination == "closed"
        assert archived[0].destination_detail == reason_text

    def test_the_new_relaunch_command_closes_the_incident_and_births_the_fence_for_real(
        self, tmp_repo, indexes, vocabulary, query,
    ):
        zone1, zone2 = "testing", "fencebug"
        incident_id = _seed_incident(
            tmp_repo, zone1, zone2, "MARK a second seeds incident, --restriction new path",
        )
        rc, out, err = run_memory_script(
            "remove.py",
            [incident_id, "placeholder reason, ignored -- the question retains the close"],
            cwd=tmp_repo,
        )
        assert rc != 0
        combined = out + err
        new_cmd = [c for c in _extract_relaunch_commands(combined, incident_id) if "--restriction new" in c]
        assert len(new_cmd) == 1, f"no se encontro el comando '--restriction new' en la salida: {combined!r}"

        reason_text = "MARK_REASON root cause was a stray env var, fixed in #58"
        restriction_text = "MARK_FENCE seeds must never read the DB url from the environment"
        why_text = "MARK_WHY it already bit us once, worth a permanent fence"
        assert len(restriction_text) <= vocabulary.HEADLINE_MAX, (
            "fixture de test roto: el titular del muro tiene que caber "
            "bajo el tope real de vocabulary.py"
        )
        filled = _fill_ellipsis_placeholders(
            new_cmd[0], [reason_text, restriction_text, why_text],
        )
        tokens = shlex.split(filled)
        assert tokens[0] == "gitmem"

        rc_retry, out_retry, err_retry = run_gitmem_script(tokens[1:], cwd=tmp_repo)
        assert rc_retry == 0, (
            f"el comando extraido de la pregunta no funciono al relanzarlo "
            f"tal cual: stdout={out_retry!r} stderr={err_retry!r}"
        )

        pm = pm_path(tmp_repo)
        assert not any(line.id == incident_id for line in indexes.read("INCIDENTS.md", pm)), (
            f"{incident_id} deberia haber salido de INCIDENTS.md"
        )
        archived = [a for a in indexes.read_archive(pm) if a.id == incident_id]
        assert len(archived) == 1

        # El muro nacido -- extraido de la salida real, nunca inventado
        # (mismo patron que `extract_note_id`, pero el emoji que
        # `_create_fence` usa es "⚠️", no "✅").
        fence_match = re.search(r"[✅⚠️]\s*([A-Z]-\d+)\s+guardada", out_retry)
        assert fence_match is not None, (
            f"no se encontro el id del muro nacido en la salida: {out_retry!r}"
        )
        fence_id = fence_match.group(1)
        assert any(line.id == fence_id for line in indexes.read("RESTRICTIONS.md", pm)), (
            f"el muro {fence_id} deberia estar en RESTRICTIONS.md"
        )

        with _cwd(tmp_repo):
            fence_note = query.by_id(fence_id)
        assert fence_note is not None, f"{fence_id} no se encuentra en el historial real de git"
        assert fence_note.origin == (incident_id,), (
            f"el muro deberia apuntar a la incidencia original con Origin: "
            f"salio origin={fence_note.origin!r}"
        )
        assert fence_note.zone1 == zone1 and fence_note.zone2 == zone2, (
            f"el muro deberia nacer en la MISMA pareja de zonas que la "
            f"incidencia: salio ({fence_note.zone1}, {fence_note.zone2})"
        )
