"""Contrato test-first de D-141 (#101, 8.3): el gate de casillas
(`hooks/checklist-gate.py`, evento Stop) calla mientras hay trabajo en
segundo plano en marcha.

Por que (D-141, y el ensayo a65d74c5 mapeado por Bilbo): Stop salta al
final de CADA turno, tambien cuando el orquestador lanza un agente en
segundo plano y espera su aviso. En el ensayo, los dos bloqueos del tope
por sesion se gastaron 3 s despues de lanzar a Dante y a Ultron, con los
agentes aun corriendo; el cierre real llego con el tope agotado y el gate
ya no hizo cumplir nada.

Contrato (encargo del orquestador, D-141):
- `background_tasks` del stdin de Stop con al menos una entrada -> el
  gate deja cerrar y NO cuenta ese Stop para el tope de 2 bloqueos: el
  `block_count` del registro no cambia.
- `background_tasks` vacio (`[]`) o ausente -> exactamente lo de hoy:
  bloquea con casillas abiertas, tope de 2.

Forma de `background_tasks`: la documentacion oficial
(code.claude.com/docs/en/hooks, seccion "Stop input", leida el
2026-10-19): array de `{id, type, status, description, ...}`; `command`
solo en `shell`, `agent_type` solo en `subagent`, `name` solo en
`workflow`, `server`/`tool` solo en `monitor` y `MCP task`. "Each entry
in background_tasks describes one in-flight task" y el array "is empty
when nothing is in flight" -- por eso aqui una entrada cualquiera ES
trabajo en marcha; ningun test fija que se filtre por `status`.
`session_crons` (despertares programados) NO es trabajo en marcha segun
el contrato: con `background_tasks` vacio, el gate sigue bloqueando
aunque haya crons.

Siempre por la puerta real: el hook como proceso separado con el JSON de
Stop por stdin, HOME falso (`fake_home`), registro sembrado por el inject
real o por `seed_registry()`. Los esperados salen del contrato y de
leer el registro en disco antes y despues de cada Stop, nunca del
codigo del gate.
"""

import json
import subprocess
import uuid

import pytest

from .conftest import (
    CHECKLISTS_DIR,
    GATE_HOOK,
    INJECT_HOOK,
    fake_home_env,
    make_skill_payload,
    make_stop_payload,
    registry_path,
    run_hook,
    seed_registry,
    task_board_dir,
    write_task,
)

PLUGIN = "unmassk-toolkit"


# ── helpers ─────────────────────────────────────────────────────────────

def _session():
    return f"sess-{uuid.uuid4().hex[:8]}"


def _shell_task(command="python3 -m pytest unmassk-toolkit/tests/hooks -q"):
    return {
        "id": f"task-{uuid.uuid4().hex[:6]}",
        "type": "shell",
        "status": "running",
        "description": "run the hook tests",
        "command": command,
    }


def _subagent_task(agent_type="unmassk-toolkit:unmassk-toolkit-dante"):
    return {
        "id": f"a{uuid.uuid4().hex[:16]}",
        "type": "subagent",
        "status": "running",
        "description": "Dante writes the red tests",
        "agent_type": agent_type,
    }


def _workflow_task():
    return {
        "id": f"wf-{uuid.uuid4().hex[:6]}",
        "type": "workflow",
        "status": "running",
        "description": "release workflow",
        "name": "release",
    }


def _monitor_task():
    return {
        "id": f"mon-{uuid.uuid4().hex[:6]}",
        "type": "monitor",
        "status": "running",
        "description": "watch the build",
        "server": "ci",
        "tool": "watch",
    }


def _stop(cwd, sid, background_tasks, session_crons=None):
    """Stop tal como lo manda Claude Code (forma de la documentacion):
    campos comunes + `last_assistant_message`, `background_tasks`,
    `session_crons`. `background_tasks=None` lo deja AUSENTE."""
    payload = make_stop_payload(cwd, sid)
    payload["last_assistant_message"] = "Launched the agent; waiting for its report."
    if background_tasks is not None:
        payload["background_tasks"] = background_tasks
    payload["session_crons"] = session_crons if session_crons is not None else []
    return payload


def _gate(fake_home, cwd, payload):
    rc, parsed, stdout, stderr = run_hook(
        GATE_HOOK, payload, cwd=cwd, env=fake_home_env(fake_home)
    )
    assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
    assert "Traceback" not in stderr, stderr
    return parsed, stdout, stderr


def _inject(fake_home, cwd, sid, skill):
    rc, _parsed, stdout, stderr = run_hook(
        INJECT_HOOK, make_skill_payload(cwd, sid, skill), cwd=cwd, env=fake_home_env(fake_home)
    )
    assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
    assert "Traceback" not in stderr, stderr


def _read_registry(project_root, sid):
    path = registry_path(project_root, sid)
    assert path.exists(), f"no hay registro en {path} -- un silencio aqui no probaria nada"
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_allows(parsed, stdout):
    assert parsed is None or parsed.get("decision") != "block", (
        f"con trabajo en marcha el gate tenia que dejar cerrar; stdout={stdout!r}"
    )


def _assert_blocks(parsed, stdout):
    assert parsed is not None and parsed.get("decision") == "block", (
        f"el gate tenia que bloquear; stdout={stdout!r}"
    )
    return parsed.get("reason", "")


def _git_repo(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    return root.resolve()


def _open_board(fake_home, sid, boxes, done=0):
    """Tablero con las `done` primeras casillas completadas y el resto
    pendientes -- siempre queda al menos una abierta."""
    board = task_board_dir(fake_home, sid)
    for i, box in enumerate(boxes, start=1):
        write_task(board, i, box, "completed" if i <= done else "pending")
    return board


# ── 1. el ensayo real, de punta a punta ─────────────────────────────────

class TestTrialSequenceWaitsDoNotSpendTheCap:
    """La secuencia del ensayo a65d74c5: Flow cargado con prefijo de
    plugin, casillas abiertas, el orquestador lanza un subagente y su
    turno acaba (Stop con el subagente corriendo) -- dos veces. Despues,
    el cierre real con las mismas casillas abiertas y nada corriendo.

    Bug que caza: hoy los dos Stops de espera bloquean y gastan el tope;
    el cierre real pasa con casillas abiertas sin bloquear nunca."""

    def test_should_allow_waits_uncounted_then_enforce_both_blocks_at_real_close(
        self, fake_home, tmp_path
    ):
        root = _git_repo(tmp_path)
        sid = _session()
        _inject(fake_home, root, sid, f"{PLUGIN}:unmassk-flow")
        boxes = json.loads((CHECKLISTS_DIR / "flow.json").read_text(encoding="utf-8"))["boxes"]
        _open_board(fake_home, sid, boxes, done=len(boxes) - 6)  # 6 abiertas, como en el ensayo
        before = _read_registry(root, sid)

        # Espera 1: Dante lanzado en segundo plano, todavia corriendo.
        _assert_allows(*_gate(fake_home, root, _stop(root, sid, [_subagent_task()]))[:2])
        # Espera 2: Ultron lanzado, corriendo; el Stop llega desde src/.
        _assert_allows(
            *_gate(
                fake_home,
                root / "src",
                _stop(root / "src", sid, [_subagent_task("unmassk-toolkit:unmassk-toolkit-ultron")]),
            )[:2]
        )
        after_waits = _read_registry(root, sid)
        assert after_waits == before, (
            "un Stop de espera toco el registro (block_count incluido): "
            f"antes={before!r} despues={after_waits!r}"
        )

        # Cierre real: mismas casillas, nada corriendo -> los dos bloqueos
        # del tope siguen enteros, y el tercero deja pasar avisando.
        _assert_blocks(*_gate(fake_home, root, _stop(root, sid, []))[:2])
        _assert_blocks(*_gate(fake_home, root, _stop(root, sid, []))[:2])
        parsed, stdout, stderr = _gate(fake_home, root, _stop(root, sid, []))
        _assert_allows(parsed, stdout)
        assert stderr.strip() != "", "el tercer intento tiene que avisar por stderr"


# ── 2. trabajo en marcha -> deja cerrar, sin contar ─────────────────────

class TestInFlightBackgroundTaskAllowsUncounted:
    """Cualquier tipo documentado de tarea en segundo plano cuenta como
    trabajo en marcha -- no solo `subagent`.

    Bug que caza: un gate que solo mira `type == "subagent"` (o que no
    mira `background_tasks` en absoluto, como hoy) bloquea y cuenta."""

    @pytest.mark.parametrize(
        "task_factory",
        [_shell_task, _subagent_task, _workflow_task, _monitor_task],
        ids=["shell", "subagent", "workflow", "monitor"],
    )
    def test_should_allow_and_keep_block_count_when_one_task_is_in_flight(
        self, fake_home, project_dir, task_factory
    ):
        sid = _session()
        boxes = ["Correr Moriarty", "Cerrar con Yoda"]
        seed_registry(project_dir, sid, f"{PLUGIN}:unmassk-flow", boxes)
        _open_board(fake_home, sid, boxes)
        before = _read_registry(project_dir, sid)

        parsed, stdout, _ = _gate(fake_home, project_dir, _stop(project_dir, sid, [task_factory()]))

        _assert_allows(parsed, stdout)
        assert _read_registry(project_dir, sid)["block_count"] == before["block_count"]

    def test_should_allow_uncounted_with_several_tasks_in_flight(self, fake_home, project_dir):
        sid = _session()
        boxes = ["Correr Moriarty"]
        seed_registry(project_dir, sid, f"{PLUGIN}:unmassk-flow", boxes)
        _open_board(fake_home, sid, boxes)

        parsed, stdout, _ = _gate(
            fake_home,
            project_dir,
            _stop(project_dir, sid, [_subagent_task(), _shell_task(), _subagent_task()]),
        )

        _assert_allows(parsed, stdout)
        assert _read_registry(project_dir, sid)["block_count"] == 0

    def test_should_neither_reset_nor_advance_a_count_already_spent_once(
        self, fake_home, project_dir
    ):
        """Bug que caza: un gate que, al ver trabajo en marcha, reescribe
        el contador a 0 (regala un bloqueo de mas) o lo sube (lo gasta).
        Con un bloqueo ya gastado: espera -> sigue en 1; cierre real ->
        bloquea y pasa a 2; el siguiente ya deja pasar."""
        sid = _session()
        boxes = ["Correr Moriarty"]
        seed_registry(project_dir, sid, f"{PLUGIN}:unmassk-flow", boxes, block_count=1)
        _open_board(fake_home, sid, boxes)

        _assert_allows(*_gate(fake_home, project_dir, _stop(project_dir, sid, [_subagent_task()]))[:2])
        assert _read_registry(project_dir, sid)["block_count"] == 1

        _assert_blocks(*_gate(fake_home, project_dir, _stop(project_dir, sid, []))[:2])
        assert _read_registry(project_dir, sid)["block_count"] == 2
        _assert_allows(*_gate(fake_home, project_dir, _stop(project_dir, sid, []))[:2])


# ── 3. nada en marcha -> exactamente lo de hoy ──────────────────────────

class TestNothingInFlightKeepsTodaysGate:
    """Verdes a proposito (red de seguridad del cambio): con
    `background_tasks` vacio o ausente, el gate bloquea y cuenta como
    hoy. Bug que cazan: un arreglo que deja pasar por la mera PRESENCIA
    de la clave (`"background_tasks" in payload`) en vez de por su
    contenido -- Claude Code la manda SIEMPRE, vacia si no hay nada."""

    def test_should_block_and_count_when_background_tasks_is_empty(self, fake_home, project_dir):
        sid = _session()
        boxes = ["Correr Moriarty", "Cerrar con Yoda"]
        seed_registry(project_dir, sid, f"{PLUGIN}:unmassk-flow", boxes)
        _open_board(fake_home, sid, boxes, done=1)

        reason = _assert_blocks(*_gate(fake_home, project_dir, _stop(project_dir, sid, []))[:2])

        assert "Cerrar con Yoda" in reason, reason
        assert _read_registry(project_dir, sid)["block_count"] == 1

    def test_should_block_and_count_when_background_tasks_is_absent(self, fake_home, project_dir):
        sid = _session()
        boxes = ["Correr Moriarty"]
        seed_registry(project_dir, sid, f"{PLUGIN}:unmassk-flow", boxes)
        _open_board(fake_home, sid, boxes)

        _assert_blocks(*_gate(fake_home, project_dir, _stop(project_dir, sid, None))[:2])
        assert _read_registry(project_dir, sid)["block_count"] == 1

    def test_should_block_when_only_a_session_cron_is_scheduled(self, fake_home, project_dir):
        """Un cron programado no es trabajo en marcha (el contrato solo
        habla de `background_tasks`). Bug que caza: un gate que calla
        tambien por `session_crons` -- un `/loop` recurrente lo dejaria
        mudo la sesion entera."""
        sid = _session()
        boxes = ["Correr Moriarty"]
        seed_registry(project_dir, sid, f"{PLUGIN}:unmassk-flow", boxes)
        _open_board(fake_home, sid, boxes)
        cron = {"id": "cron-001", "schedule": "0 9 * * 1-5", "recurring": True, "prompt": "check the build"}

        _assert_blocks(*_gate(fake_home, project_dir, _stop(project_dir, sid, [], [cron]))[:2])
        assert _read_registry(project_dir, sid)["block_count"] == 1
