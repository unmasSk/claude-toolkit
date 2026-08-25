"""Contrato en ROJO -- la aduana (`hooks/customs.py`) bloquea un commit
legitimo citando una nota YA ARCHIVADA como si siguiera viva.

EL FALLO, confirmado leyendo el codigo real (no supuesto) y reproducido
en vivo antes de escribir este fichero: hay DOS caminos por los que una
nota entra al sistema -- `bin/memory/note.py` (CLI) y `hooks/customs.py`
(la aduana, cuando un agente escribe un `git commit` cuyo mensaje parsea
como `Note`). `bin/memory/note.py::_build_context()`
(`bin/memory/note.py:154-156`) filtra `query.by_zone()` contra
`indexes.archived_ids(pm)` antes de pasarlo como `existing_in_zone` --
"si sale una nueva incidencia, es una nueva incidencia; la otra ya se
cerro" [decision del propietario, 2026-08-05, ver
note-archived-similarity-bypass-contract-notes]. `hooks/customs.py::
_decide_note()` (`hooks/customs.py:666`) NO tiene ese filtro:

    existing_in_zone = query.by_zone(note.zone1, note.zone2)

sin filtrar contra `indexes.archived_ids()` -- pasa TODO el historial
de esa pareja de zonas (vivo Y archivado) al `Context` del validador.
`validator.validate_replacement()` usa `similar.find_overlapping()`, que
desde el gate de coincidencia EXACTA de claves+zona
(`similar.py::_find_exact_key_match`) bloquea sin depender del parecido
de titular/descripcion -- por eso este fichero fija las keys y varia el
texto, para aislar la puerta de claves+zona de la de Jaccard.

Modelo de amenaza: el sistema contra si mismo -- un `git commit`
legitimo que la aduana rechaza en falso citando una nota que ya no esta
viva, nunca un atacante externo [CLAUDE.md, "que security y tests
significan en este proyecto"].

Cada test compara dos cosas escritas por separado: la decision REAL de
`_decide()` (via el proceso `hooks/customs.py`, nunca importado) contra
el estado REAL del repositorio (`bin/memory/note.py`/`remove.py` como
proceso, `indexes.read`/`read_archive` como lector) -- nunca un texto de
rechazo tecleado a mano ni un id inventado. El mensaje de commit que
dispara el hook se construye con `format.build_message()` sobre un
`model.Note` real, nunca como una cadena literal -- mismo mecanismo
productor/consumidor que `test_customs_hook.py::_expected_block_text`
ya usa para los rechazos del contrato original.

Mapeado 1:1 a los 4 puntos del encargo del orquestador (mismo patron
mixto RED/GREEN que
`test_note_archived_similarity_bypass.py`/
`test_note_exact_key_zone_duplicate_gate.py`):

1. RED -- nota archivada, mismas keys+zona, via el HOOK -> tiene que
   aprobar. Hoy bloquea citando la archivada.
2. GREEN (control de paridad) -- mismo fixture, via `note.py` (CLI) ->
   ya aprueba hoy; confirma que hay algo real que preservar, no una
   asercion que pasa por casualidad.
3. GREEN (control, no debe desactivar la puerta entera) -- misma pareja
   de keys+zona, pero la vieja sigue VIVA (no archivada), via el HOOK ->
   tiene que seguir bloqueando.
4. GREEN (guarda de sobrecorreccion) -- vieja archivada A + viva B, las
   dos con las mismas keys, via el HOOK -> tiene que bloquear citando a
   B, nunca a A.
"""

import os
import subprocess
import sys
from datetime import datetime, timezone

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_memory_script,
    seed_config_json,
    seed_zones_json,
)

_TESTS_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_TESTS_MEMORY_DIR))
HOOK_PATH = os.path.join(_TOOLKIT_ROOT, "hooks", "customs.py")

_SHARED_KEYS = ("socket", "leak")


# ── Piezas reales de produccion, cargadas una vez por modulo de test ───────


@pytest.fixture
def model_mod():
    return import_lib_memory_module("model")


@pytest.fixture
def format_mod():
    return import_lib_memory_module("format")


@pytest.fixture
def indexes_mod():
    return import_lib_memory_module("indexes")


# ── Helpers ──────────────────────────────────────────────────────────────


def run_customs_hook(cwd, command):
    """Invoca `hooks/customs.py` como proceso real, JSON de payload de
    `Bash` `tool_input` por stdin -- misma convencion medida que
    `test_customs_hook.py::run_customs_hook`. Devuelve
    `(rc, parsed_json_or_None, stdout, stderr)`.
    """
    import json

    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    result = subprocess.run(
        [sys.executable, HOOK_PATH],
        cwd=cwd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        env=dict(os.environ),
    )
    rc, stdout, stderr = result.returncode, result.stdout, result.stderr
    try:
        parsed = json.loads(stdout) if stdout.strip() else None
    except (json.JSONDecodeError, ValueError):
        parsed = None
    return rc, parsed, stdout, stderr


def _seed_i(repo, zone1, zone2, headline_suffix, *, keys=_SHARED_KEYS):
    """I real via `note.py` -- headline/description DISTINTOS cada vez
    (Jaccard bajo a proposito, ver docstring del modulo) pero las MISMAS
    keys, para que el unico gate que se dispare sea el de coincidencia
    exacta de claves+zona (`similar.py::_find_exact_key_match`), nunca
    el de parecido de texto. `I` no pasa por `validate_pain_question`
    (solo M/R), asi que no necesita `--stops`.
    """
    return run_memory_script(
        "note.py",
        [
            "I", "--zones", zone1, zone2,
            f"incident report about {headline_suffix}",
            "--description", f"a real, distinct incident description for {headline_suffix}",
            "--keys", *keys,
        ],
        cwd=repo,
    )


def _archive(repo, note_id, reason):
    """Cierra una I real via `remove.py` -- `--restriction no|new` es
    obligatorio siempre (`bin/memory/remove.py`, `required=True`), no
    solo para I."""
    return run_memory_script(
        "remove.py", [note_id, reason, "--restriction", "no"], cwd=repo,
    )


def _commit_message_for_new_note(model_mod, format_mod, note_id, zone1, zone2, headline_suffix, *, keys=_SHARED_KEYS):
    """El texto EXACTO de commit para una `Note` nueva, derivado de
    `format.build_message()` sobre un `model.Note` real -- nunca una
    cadena escrita a mano (asi el emoji/formato del titular siempre
    coincide con lo que `format.parse_message()` espera, sin duplicar
    esa tabla aqui).
    """
    note = model_mod.Note(
        type="I",
        id=note_id,
        zone1=zone1,
        zone2=zone2,
        headline=f"a fresh incident also about {headline_suffix}",
        description=f"a fresh, distinct incident description about {headline_suffix}",
        timestamp=datetime.now(timezone.utc),
        keys=keys,
    )
    message = format_mod.build_message(note)
    assert "'" not in message, "el mensaje de prueba no puede llevar comilla simple"
    return message


def _commit_command(message):
    return f"git commit --allow-empty -m '{message}'"


# ═══════════════════════════════════════════════════════════════════════
# Punto 1 -- RED: nota archivada, mismas keys+zona, via el HOOK.
# ═══════════════════════════════════════════════════════════════════════


class TestCustomsHookDoesNotBlockAgainstAnArchivedKeyZoneDuplicate:
    """Fallo real que este test fija en rojo: una nota archivada (cerrada
    meses atras) sigue contando como candidata viva SOLO en el camino de
    la aduana -- `note.py` ya la ignora [ver la fila 2, control de
    paridad]."""

    def test_git_commit_with_same_keys_as_an_archived_incident_is_approved(
        self, tmp_repo, model_mod, format_mod,
    ):
        seed_zones_json(tmp_repo, ["infra", "deploy"])
        seed_config_json(tmp_repo, customs_enabled=True)

        rc_old, out_old, err_old = _seed_i(tmp_repo, "infra", "deploy", "a file descriptor leak")
        assert rc_old == 0, f"siembra fallo: stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)

        rc_close, out_close, err_close = _archive(
            tmp_repo, old_id, "fixed by closing the socket in the finally block",
        )
        assert rc_close == 0, f"cierre fallo: stdout={out_close!r} stderr={err_close!r}"

        message = _commit_message_for_new_note(
            model_mod, format_mod, "I-777", "infra", "deploy", "a file descriptor leak",
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, _commit_command(message))

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"una nota nueva con las MISMAS keys+zona que una nota YA "
            f"ARCHIVADA ({old_id}) tiene que aprobar via el hook -- "
            f"paridad con note.py, que ya la ignora. Llego {parsed!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Punto 2 -- GREEN (control de paridad): mismo fixture, via `note.py`.
# ═══════════════════════════════════════════════════════════════════════


class TestNotePyStillDoesNotBlockAgainstTheSameArchivedKeyZoneDuplicate:
    """Confirma que hay algo real que preservar: el mismo escenario
    (misma nota archivada, mismas keys+zona) YA aprueba hoy por el
    camino de `note.py` -- sin este control, el punto 1 podria estar
    fijando en rojo un comportamiento que en realidad nunca funciono en
    ningun camino."""

    def test_note_py_still_approves_the_same_scenario(self, tmp_repo):
        seed_zones_json(tmp_repo, ["infra", "deploy"])

        rc_old, out_old, err_old = _seed_i(tmp_repo, "infra", "deploy", "a file descriptor leak")
        assert rc_old == 0, f"siembra fallo: stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)

        rc_close, out_close, err_close = _archive(
            tmp_repo, old_id, "fixed by closing the socket in the finally block",
        )
        assert rc_close == 0, f"cierre fallo: stdout={out_close!r} stderr={err_close!r}"

        rc_new, out_new, err_new = _seed_i(tmp_repo, "infra", "deploy", "a file descriptor leak")
        assert rc_new == 0, (
            f"note.py ya tiene que aprobar esto hoy (filtra archivadas, "
            f"bin/memory/note.py:154-156) -- si esto tambien fallara, el "
            f"punto 1 estaria en rojo por otra razon: "
            f"stdout={out_new!r} stderr={err_new!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Punto 3 -- GREEN (control, la puerta sigue viva): la vieja SIGUE
# viva -- el hook tiene que seguir bloqueando.
# ═══════════════════════════════════════════════════════════════════════


class TestCustomsHookStillBlocksAgainstALiveKeyZoneDuplicate:
    """El arreglo del punto 1 no puede desactivar la puerta entera: sin
    archivar la vieja, el hook tiene que seguir bloqueando un commit con
    las mismas keys+zona -- mismo mecanismo que
    `TestArchivedNoteIsIgnoredButALiveDuplicateStillBlocks` en
    `test_note_archived_similarity_bypass.py`."""

    def test_git_commit_with_same_keys_as_a_live_incident_is_blocked(
        self, tmp_repo, model_mod, format_mod,
    ):
        seed_zones_json(tmp_repo, ["infra", "deploy"])
        seed_config_json(tmp_repo, customs_enabled=True)

        rc_old, out_old, err_old = _seed_i(tmp_repo, "infra", "deploy", "a file descriptor leak")
        assert rc_old == 0, f"siembra fallo: stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)
        # Nunca archivada -- sigue vigente en INCIDENTS.md.

        message = _commit_message_for_new_note(
            model_mod, format_mod, "I-777", "infra", "deploy", "a file descriptor leak",
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, _commit_command(message))

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"una nota VIVA con las mismas keys+zona tiene que seguir "
            f"bloqueando via el hook; llego {parsed!r}"
        )
        reason = parsed.get("reason", "")
        assert old_id in reason, (
            f"el rechazo tiene que nombrar la candidata VIVA real ({old_id}): "
            f"{reason!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Punto 4 -- GREEN (guarda de sobrecorreccion): archivada A + viva B ->
# bloquea citando B, nunca A.
# ═══════════════════════════════════════════════════════════════════════


class TestCustomsHookOvercorrectionGuardNamesTheLiveCandidateNotTheArchivedOne:
    """Lo que no puede pasar: que arreglar el punto 1 cuele un duplicado
    de algo VIVO porque el filtro de archivadas se aplico de mas (p.ej.
    ignorando TODAS las candidatas en vez de solo las archivadas). Siembra
    A (cerrada) y B (viva, `--replaces none` para no chocar con A
    archivada bajo el fallo de hoy) con las mismas keys+zona; el commit
    nuevo tiene que bloquear citando a B, nunca a A."""

    def test_new_commit_still_bounces_against_the_live_candidate_not_the_archived_one(
        self, tmp_repo, model_mod, format_mod,
    ):
        seed_zones_json(tmp_repo, ["infra", "deploy"])
        seed_config_json(tmp_repo, customs_enabled=True)

        rc_a, out_a, err_a = _seed_i(tmp_repo, "infra", "deploy", "a file descriptor leak")
        assert rc_a == 0, f"stdout={out_a!r} stderr={err_a!r}"
        old_a_id = extract_note_id(out_a)

        rc_close, out_close, err_close = _archive(
            tmp_repo, old_a_id, "fixed by closing the socket in the finally block",
        )
        assert rc_close == 0, f"stdout={out_close!r} stderr={err_close!r}"

        # Sin `--replaces` -- `I` no lo tiene entre sus campos permitidos
        # (`vocabulary.TYPES["I"].allowed_fields ==
        # {"description", "why", "keys", "issue"}`, verificado leyendo
        # `vocabulary.py`). Da de alta limpio precisamente PORQUE
        # `note.py` ya filtra `A` (archivada) de `existing_in_zone`
        # [ver la fila 2, control de paridad] -- si ese filtro no
        # existiera, esta alta chocaria contra `A` y el fixture nunca
        # llegaria a construirse.
        rc_b, out_b, err_b = _seed_i(
            tmp_repo, "infra", "deploy", "a live incident also about a file descriptor leak",
        )
        assert rc_b == 0, f"stdout={out_b!r} stderr={err_b!r}"
        live_b_id = extract_note_id(out_b)

        message = _commit_message_for_new_note(
            model_mod, format_mod, "I-777", "infra", "deploy", "a file descriptor leak",
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, _commit_command(message))

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"la nota VIVA (B) tiene que seguir bloqueando el commit nuevo, "
            f"aunque haya una archivada (A) con las mismas keys al lado; "
            f"llego {parsed!r}"
        )
        reason = parsed.get("reason", "")
        assert live_b_id in reason, (
            f"el rechazo tiene que nombrar a la candidata VIVA (B, {live_b_id}): "
            f"{reason!r}"
        )
        assert old_a_id not in reason, (
            f"el rechazo NO puede nombrar a la candidata ARCHIVADA (A, "
            f"{old_a_id}) -- esta cerrada, no es una candidata real: {reason!r}"
        )
