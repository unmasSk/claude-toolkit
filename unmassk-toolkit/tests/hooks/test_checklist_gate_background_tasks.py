"""Contrato test-first del gate de casillas (`hooks/checklist-gate.py`,
evento Stop) con trabajo en segundo plano: D-141, sustituida por D-142
(#101, 8.3).

Por que (D-141, y el ensayo a65d74c5 mapeado por Bilbo): Stop salta al
final de CADA turno, tambien cuando el orquestador lanza un agente en
segundo plano y espera su aviso. En el ensayo, los dos bloqueos del tope
por sesion se gastaron 3 s despues de lanzar a Dante y a Ultron, con los
agentes aun corriendo; el cierre real llego con el tope agotado y el gate
ya no hizo cumplir nada.

Por que D-142 estrecha D-141 (Cerberus F1 y Argus, 2026-10-19): una shell
de larga vida (servidor de desarrollo, `tail -f`) o un monitor siguen en
`background_tasks` en el cierre real y dejarian el gate mudo, sin rastro.
X-135 descarta "cualquier entrada calla el gate".

Contrato (D-142):
- `background_tasks` con al menos una entrada de `type` `subagent` o
  `workflow` -> el gate deja cerrar y NO cuenta ese Stop para el tope de
  2 bloqueos (`block_count` del registro no cambia), y escribe UNA linea
  en stderr que nombra lo que espera.
- Entradas solo de `type` `shell` o `monitor` -> exactamente lo de hoy:
  bloquea con casillas abiertas y cuenta para el tope.
- `background_tasks` vacio (`[]`) o ausente -> lo de hoy.
- Excepcion declarada por Ultron: `background_tasks` que NO es una lista
  (string, objeto, numero, null) -> lo de hoy.

Forma de `background_tasks`: la documentacion oficial
(code.claude.com/docs/en/hooks, seccion "Stop input", leida el
2026-10-19): array de `{id, type, status, description, ...}`; `command`
solo en `shell`, `agent_type` solo en `subagent`, `name` solo en
`workflow`, `server`/`tool` solo en `monitor` y `MCP task`. Ningun test
fija que se filtre por `status`. `session_crons` (despertares
programados) NO es trabajo en marcha: con `background_tasks` vacio, el
gate sigue bloqueando aunque haya crons.

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


def _assert_one_wait_line(stderr, waited_type):
    """D-142: cada salto deja UNA linea en stderr que nombra lo que espera.
    Bug que caza: el salto mudo de D-141 (stderr vacio), o un salto que
    vuelca varias lineas o no dice a que tipo de trabajo espera."""
    lines = [ln for ln in stderr.splitlines() if ln.strip()]
    assert len(lines) == 1, f"tenia que haber exactamente una linea en stderr; stderr={stderr!r}"
    assert waited_type in lines[0], (
        f"la linea tenia que nombrar lo que espera ({waited_type!r}); linea={lines[0]!r}"
    )


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
        parsed, stdout, stderr = _gate(fake_home, root, _stop(root, sid, [_subagent_task()]))
        _assert_allows(parsed, stdout)
        _assert_one_wait_line(stderr, "subagent")
        # Espera 2: Ultron lanzado, corriendo; el Stop llega desde src/.
        parsed, stdout, stderr = _gate(
            fake_home,
            root / "src",
            _stop(root / "src", sid, [_subagent_task("unmassk-toolkit:unmassk-toolkit-ultron")]),
        )
        _assert_allows(parsed, stdout)
        _assert_one_wait_line(stderr, "subagent")
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


# ── 2. un agente en marcha -> deja cerrar, sin contar, y lo dice ───────

class TestAgentWorkInFlightAllowsUncounted:
    """D-142: solo `subagent` y `workflow` cuentan como espera.

    Bug que caza: un gate que no mira `background_tasks` (bloquea y
    cuenta mientras el agente corre), o que calla sin dejar rastro."""

    @pytest.mark.parametrize(
        "task_factory, waited_type",
        [(_subagent_task, "subagent"), (_workflow_task, "workflow")],
        ids=["subagent", "workflow"],
    )
    def test_should_allow_keep_count_and_name_the_wait_when_agent_work_is_in_flight(
        self, fake_home, project_dir, task_factory, waited_type
    ):
        sid = _session()
        boxes = ["Correr Moriarty", "Cerrar con Yoda"]
        seed_registry(project_dir, sid, f"{PLUGIN}:unmassk-flow", boxes)
        _open_board(fake_home, sid, boxes)
        before = _read_registry(project_dir, sid)

        parsed, stdout, stderr = _gate(fake_home, project_dir, _stop(project_dir, sid, [task_factory()]))

        _assert_allows(parsed, stdout)
        assert _read_registry(project_dir, sid)["block_count"] == before["block_count"]
        _assert_one_wait_line(stderr, waited_type)

    def test_should_allow_uncounted_when_a_subagent_runs_beside_a_long_lived_shell(
        self, fake_home, project_dir
    ):
        """Bug que caza: un gate que exige que TODAS las entradas sean de
        agente, o que mira solo la primera: con un servidor de desarrollo
        ya corriendo, la espera de un agente volveria a gastar el tope."""
        sid = _session()
        boxes = ["Correr Moriarty"]
        seed_registry(project_dir, sid, f"{PLUGIN}:unmassk-flow", boxes)
        _open_board(fake_home, sid, boxes)

        parsed, stdout, stderr = _gate(
            fake_home,
            project_dir,
            _stop(project_dir, sid, [_shell_task("npm run dev"), _monitor_task(), _subagent_task()]),
        )

        _assert_allows(parsed, stdout)
        assert _read_registry(project_dir, sid)["block_count"] == 0
        _assert_one_wait_line(stderr, "subagent")

    def test_should_neither_reset_nor_advance_a_count_already_spent_once(
        self, fake_home, project_dir
    ):
        """Bug que caza: un gate que, al ver un agente en marcha, reescribe
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


# ── 3. solo shells y monitores -> exactamente lo de hoy ─────────────────

class TestLongLivedShellOrMonitorKeepsTodaysGate:
    """D-142 / X-135: un servidor de desarrollo, un `tail -f` o un
    monitor siguen en `background_tasks` en el cierre real. Bug que
    cazan: el gate de D-141, que callaba con cualquier entrada y dejaba
    cerrar con casillas abiertas sin decir nada."""

    @pytest.mark.parametrize(
        "tasks",
        [
            [_shell_task("npm run dev")],
            [_shell_task("tail -f /var/log/app.log")],
            [_monitor_task()],
            [_shell_task("npm run dev"), _monitor_task()],
        ],
        ids=["dev-server", "tail-f", "monitor", "shell-and-monitor"],
    )
    def test_should_block_and_count_when_only_shells_or_monitors_are_in_flight(
        self, fake_home, project_dir, tasks
    ):
        sid = _session()
        boxes = ["Correr Moriarty", "Cerrar con Yoda"]
        seed_registry(project_dir, sid, f"{PLUGIN}:unmassk-flow", boxes)
        _open_board(fake_home, sid, boxes, done=1)

        reason = _assert_blocks(*_gate(fake_home, project_dir, _stop(project_dir, sid, tasks))[:2])

        assert "Cerrar con Yoda" in reason, reason
        assert _read_registry(project_dir, sid)["block_count"] == 1

    def test_should_spend_the_cap_at_real_close_with_a_dev_server_still_running(
        self, fake_home, project_dir
    ):
        """El cierre real con el servidor de desarrollo vivo: bloquea dos
        veces (tope entero) y el tercer intento deja pasar avisando, igual
        que sin nada en marcha."""
        sid = _session()
        boxes = ["Correr Moriarty"]
        seed_registry(project_dir, sid, f"{PLUGIN}:unmassk-flow", boxes)
        _open_board(fake_home, sid, boxes)
        running = [_shell_task("npm run dev")]

        _assert_blocks(*_gate(fake_home, project_dir, _stop(project_dir, sid, running))[:2])
        _assert_blocks(*_gate(fake_home, project_dir, _stop(project_dir, sid, running))[:2])
        assert _read_registry(project_dir, sid)["block_count"] == 2
        parsed, stdout, stderr = _gate(fake_home, project_dir, _stop(project_dir, sid, running))
        _assert_allows(parsed, stdout)
        assert stderr.strip() != "", "el tercer intento tiene que avisar por stderr"


# ── 4. nada en marcha -> exactamente lo de hoy ──────────────────────────

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


# ── 5. excepcion declarada por Ultron: no es una lista -> lo de hoy ─────

class TestNonListBackgroundTasksKeepsTodaysGate:
    """Excepcion que Ultron declaro: un `background_tasks` que no es una
    lista no es trabajo en marcha. Verdes a proposito hoy (la guarda de
    D-141 ya exige lista); quedan como red para la reescritura de D-142.

    Bug que cazan: un filtro nuevo que recorre lo que llegue sin mirar el
    tipo -- un objeto `{"type": "subagent"}` o el string "subagent" dejarian
    cerrar con casillas abiertas (o romperian el hook con un Traceback,
    que `_gate` tambien caza)."""

    @pytest.mark.parametrize(
        "value",
        [
            {"id": "a1", "type": "subagent", "status": "running", "description": "x"},
            "subagent",
            "workflow",
            0,
            1,
        ],
        ids=["object-shaped-like-a-subagent", "string-subagent", "string-workflow", "zero", "one"],
    )
    def test_should_block_and_count_when_background_tasks_is_not_a_list(
        self, fake_home, project_dir, value
    ):
        sid = _session()
        boxes = ["Correr Moriarty"]
        seed_registry(project_dir, sid, f"{PLUGIN}:unmassk-flow", boxes)
        _open_board(fake_home, sid, boxes)
        payload = _stop(project_dir, sid, [])
        payload["background_tasks"] = value

        _assert_blocks(*_gate(fake_home, project_dir, payload)[:2])
        assert _read_registry(project_dir, sid)["block_count"] == 1

    def test_should_block_and_count_when_background_tasks_is_json_null(self, fake_home, project_dir):
        """`null` explicito, distinto de clave ausente: `.get()` devuelve
        None en los dos, pero un `"background_tasks" in payload` no."""
        sid = _session()
        boxes = ["Correr Moriarty"]
        seed_registry(project_dir, sid, f"{PLUGIN}:unmassk-flow", boxes)
        _open_board(fake_home, sid, boxes)
        payload = _stop(project_dir, sid, [])
        payload["background_tasks"] = None

        _assert_blocks(*_gate(fake_home, project_dir, payload)[:2])
        assert _read_registry(project_dir, sid)["block_count"] == 1
