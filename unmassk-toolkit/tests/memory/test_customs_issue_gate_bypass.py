"""Contrato en ROJO -- Moriarty T1 (2026-08-26, reproducido en vivo por
el orquestador antes de asignar esta tarea): el camino de `hooks/
customs.py` esquiva la aduana de issues por completo.

EL FALLO, confirmado leyendo el codigo real: `hooks/customs.py::
_decide_note()` (linea ~683) construye la `Note` de un `git commit -m`
crudo y solo llama a `validator.validate_note(note, ctx)` -- nunca a
`validator.validate_issue_gate()` (unico llamador real hoy:
`bin/memory/note.py:419`). `validate_note()` documenta explicitamente
por que -- ver su propio docstring, "ASUNCIONES DE FIRMA": no incluye
ninguna comprobacion que necesite un dato fuera de `note`/`ctx`
(`validate_pain_question`, `validate_issue`, y desde D-065/D-066 tambien
`validate_issue_gate`, todas quedan fuera a proposito). El hook nunca
llamo a esas comprobaciones extra para NINGUNA de ellas -- la aduana de
issues, nacida el mismo dia que este contrato, hereda el mismo hueco sin
que nadie lo cerrara para ella todavia.

Reproducido en vivo antes de escribir esto (mismo criterio que el resto
de esta rama, "se prueba ejecutando, no leyendo"): un `git commit -m
"<mensaje bien formado de una I>"` sin `Issue:` ni `Quote:` en el
cuerpo, vertido a `hooks/customs.py` por stdin como haria Claude Code
real, sale `{"decision": "approve"}` -- la nota queda viva y buscable
sin haber contestado nunca la vara de medir.

Contrato (D-065/D-066, unmassk-standards Sec.34 -- "el sistema contra si
mismo", nunca un atacante externo [CLAUDE.md]): el hook de customs
rechaza un commit crudo que cree una Q/I sin contestar la vara -- MISMO
criterio, MISMO texto de rechazo (`validator_issue.py::
validate_issue_gate`, ya en produccion desde el pase anterior de este
mismo contrato) que `note.py` ya aplica hoy.

Patron de test tomado de `test_customs_archived_key_zone_duplicate_parity.py`
(explicito en el encargo) -- mismo `run_customs_hook`/`HOOK_PATH`
locales, mismo `_commit_command`, mismo `model_mod`/`format_mod` para
construir el mensaje de commit EXACTO via `format.build_message()` sobre
un `model.Note` real, nunca una cadena tecleada a mano. Mapeado 1:1 al
mismo patron mixto RED/GREEN que ese fichero y
`test_note_archived_similarity_bypass.py`/`test_note_exact_key_zone_duplicate_gate.py`
ya usan:

1. RED -- commit crudo, `I`, sin `issue`/`quote` -> el hook APRUEBA hoy;
   tiene que BLOQUEAR con la vara de medir + las tres opciones literales
   de D-065/D-066.
2. RED -- mismo fallo, tipo `Q` (D-065/D-066 no distingue entre los dos).
3. GREEN (control de paridad) -- mismo fixture, via `note.py` (CLI) ->
   YA rechaza hoy (`validate_issue_gate` esta enganchada ahi desde el
   pase anterior) -- confirma que hay algo real que preservar, no una
   asercion que pasa por casualidad.
4. GREEN (control, la puerta no se generaliza de mas) -- commit crudo
   creando una `D` (tipo no gateado) sin `issue`/`quote`/`work` -> el
   hook tiene que seguir aprobando exactamente igual que hoy.
5. GREEN (control, la puerta no bloquea de mas) -- commit crudo, `I`,
   CON `Issue: #N` real en el cuerpo (la vara YA contestada) -> el hook
   tiene que seguir aprobando. `validate_issue_gate` es pura (no llama a
   `gh`, ver su propio docstring) -- no hace falta un `gh` falso aqui.

Nada de esto se arregla en este fichero -- Ultron corrige
`hooks/customs.py::_decide_note()` despues (limite explicito del
encargo: no tocar `lib/`, `bin/` ni `hooks/`).
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    run_memory_script,
    seed_config_json,
    seed_zones_json,
)

_TESTS_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_TESTS_MEMORY_DIR))
HOOK_PATH = os.path.join(_TOOLKIT_ROOT, "hooks", "customs.py")

_ZONE1 = "issuegatehookzone"
_ZONE2 = "issuegatehookzonetwo"

# La vara de medir literal y las tres opciones de relanzamiento --
# identicas a `validator_issue.py::_MEASURING_STICK`/
# `_reject_missing_measuring_stick_answer` (ya en produccion) y al
# contrato original de `test_note_issue_gate.py`. Constantes en vez de
# repetidas, mismo motivo que alli: un typo salta en el propio test, no
# en produccion.
_VARA_DE_MEDIR = (
    "¿cerrar esta nota exige trabajo — código, medir, construir — o "
    "solo una respuesta/decisión?"
)
_RELANZA_WORK_NO = "--work no"
_RELANZA_ISSUE_N = "--issue N"
_RELANZA_ISSUE_NONE_QUOTE = '--issue none --quote "<frase exacta del dueño>"'


@pytest.fixture
def model_mod():
    return import_lib_memory_module("model")


@pytest.fixture
def format_mod():
    return import_lib_memory_module("format")


def run_customs_hook(cwd, command):
    """Invoca `hooks/customs.py` como proceso real, JSON de payload de
    `Bash` `tool_input` por stdin -- misma convencion medida que
    `test_customs_hook.py::run_customs_hook` /
    `test_customs_archived_key_zone_duplicate_parity.py::run_customs_hook`.
    Devuelve `(rc, parsed_json_or_None, stdout, stderr)`.
    """
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


def _commit_command(message):
    return f"git commit --allow-empty -m '{message}'"


def _commit_message(model_mod, format_mod, note_type, note_id, zone1, zone2, headline, description, **extra):
    """El texto EXACTO de commit para una `Note` nueva, derivado de
    `format.build_message()` sobre un `model.Note` real -- nunca una
    cadena escrita a mano (mismo tecnica que
    `test_customs_archived_key_zone_duplicate_parity.py::
    _commit_message_for_new_note`), para que el emoji/formato del
    titular siempre coincida con lo que `format.parse_message()` espera.
    `**extra` pasa campos reales de `Note` cuando el test los necesita
    (p.ej. `issue=4242` para el control 5) -- nunca `work`, que no es un
    campo de `Note` [ver docstring de `validate_issue_gate`].
    """
    note = model_mod.Note(
        type=note_type,
        id=note_id,
        zone1=zone1,
        zone2=zone2,
        headline=headline,
        description=description,
        timestamp=datetime.now(timezone.utc),
        **extra,
    )
    message = format_mod.build_message(note)
    assert "'" not in message, "el mensaje de prueba no puede llevar comilla simple"
    return message


class TestCustomsHookBlocksARawCommitCreatingAnIncidentWithoutTheGate:
    """Punto 1 -- RED: commit crudo, `I`, sin `issue` ni `quote` -> el
    hook tiene que bloquear con la vara de medir completa."""

    def test_raw_commit_creating_an_incident_with_no_issue_answer_is_blocked(
        self, tmp_repo, model_mod, format_mod,
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        seed_config_json(tmp_repo, customs_enabled=True)

        message = _commit_message(
            model_mod, format_mod, "I", "I-901", _ZONE1, _ZONE2,
            "checkout gateway silently retried a charge twice",
            "a stray retry loop double-charged a real customer during the "
            "outage last night",
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, _commit_command(message))

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"un commit crudo que crea una I SIN issue ni quote tiene que "
            f"bloquear via el hook -- llego {parsed!r} (aprobado, la nota "
            f"quedaria viva y buscable sin haber contestado la vara)"
        )
        reason = parsed.get("reason", "")
        assert _VARA_DE_MEDIR in reason, (
            f"el bloqueo tiene que traer la vara de medir literal -- "
            f"razon real: {reason!r}"
        )
        assert _RELANZA_WORK_NO in reason and _RELANZA_ISSUE_N in reason and \
            _RELANZA_ISSUE_NONE_QUOTE in reason, (
            f"el bloqueo tiene que ofrecer las tres opciones de "
            f"relanzamiento de D-065/D-066 -- razon real: {reason!r}"
        )


class TestCustomsHookBlocksARawCommitCreatingAQuestionWithoutTheGate:
    """Punto 2 -- RED, mismo fallo para `Q` (D-065/D-066 no distingue
    entre los dos tipos gateados)."""

    def test_raw_commit_creating_a_question_with_no_issue_answer_is_blocked(
        self, tmp_repo, model_mod, format_mod,
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        seed_config_json(tmp_repo, customs_enabled=True)

        message = _commit_message(
            model_mod, format_mod, "Q", "Q-901", _ZONE1, _ZONE2,
            "does a refunded order still count toward the loyalty tier",
            "support keeps asking whether a refunded order should be "
            "subtracted from the customer loyalty point total",
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, _commit_command(message))

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"un commit crudo que crea una Q SIN issue ni quote tiene que "
            f"bloquear via el hook -- llego {parsed!r}"
        )
        reason = parsed.get("reason", "")
        assert _VARA_DE_MEDIR in reason, (
            f"el bloqueo tiene que traer la vara de medir literal -- "
            f"razon real: {reason!r}"
        )
        assert _RELANZA_WORK_NO in reason and _RELANZA_ISSUE_N in reason and \
            _RELANZA_ISSUE_NONE_QUOTE in reason, (
            f"el bloqueo tiene que ofrecer las tres opciones de "
            f"relanzamiento de D-065/D-066 -- razon real: {reason!r}"
        )


class TestNotePyParityControlAlreadyBlocksTheSameScenario:
    """Punto 3 -- GREEN (control de paridad): el mismo escenario (misma
    I, sin issue/quote/work) YA rechaza hoy por el camino de `note.py`
    -- confirma que hay algo real que preservar, no que el punto 1/2
    esten en rojo por una razon distinta (p.ej. un `Context` mal
    construido en el test)."""

    def test_note_py_already_rejects_the_same_incident_without_the_gate_answer(
        self, tmp_repo,
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])

        rc, out, err = run_memory_script(
            "note.py",
            [
                "I", "--zones", _ZONE1, _ZONE2,
                "checkout gateway silently retried a charge twice",
                "--description", "a stray retry loop double-charged a real "
                                  "customer during the outage last night",
            ],
            cwd=tmp_repo,
        )
        assert rc != 0, (
            f"note.py ya tiene que rechazar esto hoy (validate_issue_gate "
            f"esta enganchada ahi desde el pase anterior) -- si esto "
            f"tambien pasara, los puntos 1/2 estarian en rojo por otra "
            f"razon: stdout={out!r} stderr={err!r}"
        )
        assert _VARA_DE_MEDIR in out, (
            f"note.py ya tiene que traer la vara de medir literal hoy -- "
            f"salida real: {out!r}"
        )


class TestCustomsHookStillApprovesARawCommitCreatingANonGatedType:
    """Punto 4 -- GREEN (control, la puerta no se generaliza de mas): un
    commit crudo que crea una `D` (tipo no gateado, D-065/D-066 es
    exclusiva de Q/I) SIN issue/quote tiene que seguir aprobando
    exactamente igual que hoy."""

    def test_raw_commit_creating_a_decision_with_no_issue_field_still_approves(
        self, tmp_repo, model_mod, format_mod,
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        seed_config_json(tmp_repo, customs_enabled=True)

        message = _commit_message(
            model_mod, format_mod, "D", "D-901", _ZONE1, _ZONE2,
            "retire the legacy CSV export in favor of the bulk API",
            "the CSV export has not been touched in two years and the bulk "
            "API already covers every field it exposed",
            why="one export path is cheaper to maintain than two",
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, _commit_command(message))

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"una D sin issue/quote/work no pasa por la aduana de issues "
            f"(exclusiva de Q/I) -- tiene que seguir aprobando igual que "
            f"hoy. Llego {parsed!r}"
        )


class TestCustomsHookStillApprovesARawCommitThatAlreadyAnsweredTheGate:
    """Punto 5 -- GREEN (control, la puerta no bloquea de mas): un
    commit crudo que crea una `I` CON `Issue: #N` real en el cuerpo (la
    vara YA contestada) tiene que seguir aprobando -- `validate_issue_gate`
    es pura, no hace falta un `gh` falso para este control."""

    def test_raw_commit_creating_an_incident_with_a_real_issue_number_still_approves(
        self, tmp_repo, model_mod, format_mod,
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        seed_config_json(tmp_repo, customs_enabled=True)

        message = _commit_message(
            model_mod, format_mod, "I", "I-902", _ZONE1, _ZONE2,
            "the retry queue kept redelivering the same webhook for hours",
            "a missing acknowledgment step let the retry worker redeliver "
            "the same webhook payload every five minutes",
            issue=4242,
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, _commit_command(message))

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"una I con Issue: #4242 real ya contesto la vara de medir -- "
            f"tiene que aprobar. Llego {parsed!r}"
        )
