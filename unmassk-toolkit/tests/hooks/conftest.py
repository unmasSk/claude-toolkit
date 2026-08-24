"""Fixtures y helpers compartidos para `tests/hooks/` -- las casillas por
programa (docs/plan/casillas-por-programa.md, D-052).

Escrito desde cero para este directorio nuevo (no reutiliza literalmente
`tests/conftest.py` ni `tests/memory/conftest.py` -- ninguno de los dos
cubre PostToolUse/Stop ni el tablero de tareas real de `~/.claude/tasks/`),
pero SIGUE el patron ya medido en ambos: hook invocado como PROCESO
SEPARADO con JSON real por stdin, nunca importando sus funciones.

NOTA IMPORTANTE (2026-08-24, escrita a mitad de este pase): Ultron
implemento los dos hooks EN PARALELO mientras se escribia este contrato
(el encargo lo decia explicitamente: "que Ultron implementa en
paralelo"). Cuando la primera version de este fichero se ejecuto contra
el codigo real, las asunciones de firma de mas abajo (marcadas
"DISCLOSED") resultaron tener un esquema DISTINTO al que aqui se habia
adivinado -- verificado leyendo `hooks/skill-checklist-inject.py`,
`hooks/checklist-gate.py` y `lib/checklist_state.py` directamente, nunca
de memoria. Este fichero quedo REESCRITO para seguir el esquema REAL, no
el adivinado -- exactamente la regla de este agente para actualizar un
test tras un cambio de codigo intencional: se confirma el cambio, se
alinea la aserche, se preserva la intencion original del test. Las
"ASUNCIONES DISCLOSED" de abajo documentan ahora el esquema VERIFICADO
(no una apuesta previa a que existiera codigo), y siguen anotandose como
tales porque ningun documento de diseno los fijaba por adelantado --
solo el codigo, una vez escrito, los fija.

ESQUEMA REAL (verificado leyendo el codigo, no adivinado):

1. **Ruta y nombre de los manifiestos.** `checklists/<basename>.json`,
   sibling de `hooks/`, resuelto por `skill-checklist-inject.py` via
   `os.path.dirname(_HOOKS_DIR)` (su propio `__file__`) -- nunca via
   `$CLAUDE_PLUGIN_ROOT` en la implementacion real, aunque se sigue
   fijando esa env var por si un hook futuro la lee. `<basename>` quita
   el prefijo `unmassk-` si el nombre de skill lo lleva (`checklists/
   flow.json`, no `checklists/unmassk-flow.json`); un nombre sin ese
   prefijo se usa tal cual. Los fixtures de este fichero usan SIEMPRE
   nombres de skill SIN el prefijo `unmassk-` (via `unique_skill_name()`)
   para no tener que replicar esa logica de recorte en cada test.

2. **Esquema del manifiesto.** `{"skill": "<nombre-completo>", "boxes":
   ["texto 1", "texto 2", ...]}` -- la clave real es `boxes`, no
   `checklist`. `skill-checklist-inject.py` solo lee `data["boxes"]`
   (debe ser una lista de strings); un manifiesto sin esa clave, o con
   JSON invalido, cae por el mismo camino de error (aviso por stderr,
   `exit 0`, sin escritura de registro).

3. **Esquema del registro por-sesion** (`lib/checklist_state.py`,
   `<project_root>/.claude/.unmassk/session-checklists/<session_id>.json`):
   ```json
   {"session_id": "...", "skills": [{"skill": "...", "boxes": [...]}],
    "block_count": 0}
   ```
   Un registro que NO tenga `skills` como lista se trata como corrupto
   (`load_registry` devuelve el registro vacio por defecto + `corrupt=
   True`) -- por eso `seed_registry()`/`seed_corrupt_registry()` escriben
   esta forma exacta, y no la que este fichero asumia en su primera
   version (`{"skill":..., "checklist":[...]}, sin envoltorio "skills"`).
   Los tests de `checklist-gate.py` siguen sin depender de que
   `skill-checklist-inject.py` exista o funcione: siembran este registro
   DIRECTAMENTE, para verificar el contrato de cada hook por separado
   (igual que `test_customs_hook.py` prueba `validator.py`/`rejection.py`
   sin pasar por la aduana) -- eso no cambio, solo el esquema sembrado.

4. **Como empareja `checklist-gate.py` una casilla esperada con una tarea
   real del tablero.** Comparacion EXACTA de texto (con `.strip()` en
   ambos lados) entre cada entrada de `boxes` y el campo `subject` de un
   fichero de tarea (`~/.claude/tasks/<clave>/<N>.json`, esquema
   verificado en vivo en esta maquina). "Ausente" = ninguna tarea con ese
   `subject` existe entre las tareas LEGIBLES; "pending"/"in_progress" =
   existe pero su `status` no es `"completed"`.

5. **Un fichero de tarea corrupto NO activa un "no puedo decidir, dejo
   pasar".** Se ignora igual que cualquier fichero ausente: la casilla
   cuya unica fuente de informacion era ese fichero se cuenta como
   "ausente" (bloquea, con la lista de rotos avisada aparte por stderr).
   El fail-open de "no puede decidir" esta reservado para fallos a nivel
   de SISTEMA (registro corrupto, stdin corrupto, directorio de tareas
   ausente, excepcion no prevista) -- nunca para un fichero de tarea
   individual, que siempre se trata como informacion perdida = casilla
   sin cubrir. Verificado leyendo `_read_board_tasks`/`_violations` en
   `hooks/checklist-gate.py`: un nombre en `broken` nunca aparece en el
   dict `tasks`, y `_violations` no distingue "ausente por corrupcion" de
   "ausente porque nunca se creo".

6. **Clave del directorio de tareas.** `$CLAUDE_CODE_TASK_LIST_ID` si
   existe, si no el `session_id` del payload de Stop -- el protocolo 7
   (directorio ausente) cubre el caso en que ninguna de las dos resuelve
   a un directorio real.

HOME/CLAUDE_CONFIG_DIR SIEMPRE FALSOS: ningun test de este directorio
toca `~/.claude` real. `fake_home()` crea un HOME temporal y fija
`HOME`/`CLAUDE_CONFIG_DIR`/`CLAUDE_PLUGIN_ROOT` en el entorno del hijo --
las dos primeras al MISMO valor (`<fake_home>/.claude`) para que el
resultado no dependa de cual de las dos lea el gate para encontrar
`tasks/`.
"""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _THIS_DIR.parent
TOOLKIT_ROOT = _TESTS_DIR.parent

HOOKS_DIR = TOOLKIT_ROOT / "hooks"
CHECKLISTS_DIR = TOOLKIT_ROOT / "checklists"
LIB_DIR = TOOLKIT_ROOT / "lib"

INJECT_HOOK = "skill-checklist-inject.py"
GATE_HOOK = "checklist-gate.py"


# ── Ejecucion del hook, siempre como proceso separado ──────────────────

def run_cmd(args, cwd, env=None, input_text=None, timeout=20):
    """Corre un comando y devuelve (returncode, stdout, stderr).

    `env` se AÑADE al entorno heredado (nunca lo sustituye entero); un
    valor `None` BORRA esa variable del hijo -- mismo contrato que
    `tests/conftest.py::run_cmd`, aqui reducido a lo que estos hooks
    necesitan (sin inyeccion de identidad git: ninguno de los dos toca
    git).
    """
    merged = dict(os.environ)
    for key, value in (env or {}).items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    result = subprocess.run(
        args,
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=merged,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def run_hook_raw(hook_name, raw_stdin, cwd, env=None):
    """Invoca `hooks/<hook_name>` con `raw_stdin` literal por entrada
    estandar. Con el hook inexistente, falla con el `returncode` que
    Python da a "no se pudo abrir el fichero" -- el ROJO real de este
    contrato, nunca un error de import enmascarado (ningun test de este
    directorio importa las funciones del hook).
    """
    hook_path = str(HOOKS_DIR / hook_name)
    return run_cmd([sys.executable, hook_path], cwd=cwd, env=env, input_text=raw_stdin)


def run_hook(hook_name, payload, cwd, env=None):
    """Igual que `run_hook_raw`, serializando `payload` (dict) con
    `json.dumps`. Devuelve tambien el JSON parseado de stdout (`None` si
    stdout esta vacio o no es JSON valido) para que cada test no repita
    el parseo defensivo.
    """
    rc, stdout, stderr = run_hook_raw(hook_name, json.dumps(payload), cwd, env=env)
    parsed = None
    if stdout.strip():
        try:
            parsed = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            parsed = None
    return rc, parsed, stdout, stderr


# ── HOME/CLAUDE_CONFIG_DIR falsos -- nunca el ~/.claude real ────────────

@pytest.fixture
def fake_home(tmp_path):
    """Directorio HOME temporal con `.claude/tasks/` ya creado debajo.
    Devuelve el `Path` del HOME (no el de `.claude/`) -- usar
    `fake_home_env()` para el dict de entorno que apunta ambas variables
    (`HOME`, `CLAUDE_CONFIG_DIR`) al MISMO `.claude/` real bajo este HOME.
    """
    home = tmp_path / "fake-home"
    (home / ".claude" / "tasks").mkdir(parents=True)
    return home


def fake_home_env(fake_home_path):
    """Entorno a pasarle al hijo para que jamas toque `~/.claude` real.

    `HOME` y `CLAUDE_CONFIG_DIR` fijados al MISMO `.claude/` -- ver
    ASUNCION 1 del docstring de modulo: si el gate resuelve el tablero de
    tareas por `Path.home()/".claude"/"tasks"` o por
    `$CLAUDE_CONFIG_DIR/tasks`, las dos rutas coinciden aqui.
    `CLAUDE_PLUGIN_ROOT` tambien fijado (real env var de Claude Code,
    documentada en `hook-development/SKILL.md`) por si el inject resuelve
    `checklists/` por ahi en vez de por su propio `__file__`.
    """
    claude_dir = str(fake_home_path / ".claude")
    return {
        "HOME": str(fake_home_path),
        "CLAUDE_CONFIG_DIR": claude_dir,
        "CLAUDE_PLUGIN_ROOT": str(TOOLKIT_ROOT),
    }


def task_board_dir(fake_home_path, key):
    """`<fake_home>/.claude/tasks/<key>/` -- lo crea si no existe."""
    d = fake_home_path / ".claude" / "tasks" / key
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_task(board_dir, task_id, subject, status, description=""):
    """Escribe `<board_dir>/<task_id>.json` con el esquema REAL verificado
    en vivo en esta maquina (`id`, `subject`, `description`, `status`,
    `blocks`, `blockedBy`)."""
    path = Path(board_dir) / f"{task_id}.json"
    path.write_text(
        json.dumps(
            {
                "id": str(task_id),
                "subject": subject,
                "description": description,
                "status": status,
                "blocks": [],
                "blockedBy": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def write_corrupt_task(board_dir, task_id):
    """Un fichero de tarea con JSON invalido -- protocolo 6 del gate."""
    path = Path(board_dir) / f"{task_id}.json"
    path.write_text("{not json at all", encoding="utf-8")
    return path


# ── Manifiestos (`checklists/<skill>.json`) -- ver ASUNCION 1 y 2 ───────

@pytest.fixture
def make_manifest():
    """Factory fixture: `make_manifest(skill_name, items)` escribe
    `checklists/<skill_name>.json` (la ruta REAL, sibling de `hooks/` --
    el hook no admite parametrizarla, ver ASUNCION 1) y lo borra al
    terminar el test, pase lo que pase. Usar SIEMPRE un `skill_name` unico
    por test (uuid) para no chocar con manifiestos reales que Ultron cree
    mas tarde en la misma carpeta.
    """
    created = []
    pre_existing_dir = CHECKLISTS_DIR.exists()

    def _make(skill_name, boxes):
        """`skill_name` debe ir SIN el prefijo `unmassk-` (ver ESQUEMA
        REAL punto 1) para que el nombre de fichero coincida tal cual."""
        CHECKLISTS_DIR.mkdir(parents=True, exist_ok=True)
        path = CHECKLISTS_DIR / f"{skill_name}.json"
        path.write_text(
            json.dumps({"skill": skill_name, "boxes": list(boxes)}, ensure_ascii=False),
            encoding="utf-8",
        )
        created.append(path)
        return path

    yield _make

    for p in created:
        p.unlink(missing_ok=True)
    if not pre_existing_dir and CHECKLISTS_DIR.exists():
        try:
            next(CHECKLISTS_DIR.iterdir())
        except StopIteration:
            CHECKLISTS_DIR.rmdir()


@pytest.fixture
def make_corrupt_manifest():
    """Factory fixture gemela de `make_manifest`, pero escribe texto que
    NO es JSON valido -- protocolo 4 del inject (manifiesto corrupto)."""
    created = []
    pre_existing_dir = CHECKLISTS_DIR.exists()

    def _make(skill_name, raw_text="{not json at all"):
        CHECKLISTS_DIR.mkdir(parents=True, exist_ok=True)
        path = CHECKLISTS_DIR / f"{skill_name}.json"
        path.write_text(raw_text, encoding="utf-8")
        created.append(path)
        return path

    yield _make

    for p in created:
        p.unlink(missing_ok=True)
    if not pre_existing_dir and CHECKLISTS_DIR.exists():
        try:
            next(CHECKLISTS_DIR.iterdir())
        except StopIteration:
            CHECKLISTS_DIR.rmdir()


def unique_skill_name(prefix="dante-test-skill"):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ── Proyecto (cwd del hook) y su registro por-sesion ────────────────────

@pytest.fixture
def project_dir(tmp_path):
    """Directorio de proyecto (cwd del hook) -- NO es un repo git: ninguno
    de los dos hooks necesita git para nada de su contrato."""
    d = tmp_path / "project"
    d.mkdir()
    return d


def registry_path(project_dir_path, session_id):
    return Path(project_dir_path) / ".claude" / ".unmassk" / "session-checklists" / f"{session_id}.json"


def seed_registry(project_dir_path, session_id, skill, boxes, block_count=0, extra=None):
    """Siembra el registro por-sesion DIRECTAMENTE (sin pasar por
    `skill-checklist-inject.py`) con el esquema REAL de
    `lib/checklist_state.py` (ver ESQUEMA REAL punto 3): los tests de
    `checklist-gate.py` verifican su contrato de forma independiente del
    inject."""
    path = registry_path(project_dir_path, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "session_id": session_id,
        "skills": [{"skill": skill, "boxes": list(boxes)}],
        "block_count": block_count,
    }
    if extra:
        body.update(extra)
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return path


def seed_corrupt_registry(project_dir_path, session_id, raw_text="{not json at all"):
    path = registry_path(project_dir_path, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw_text, encoding="utf-8")
    return path


# ── Payloads reales (esquema de hook-input-schemas.md, skill plugin-dev) ─

def make_skill_payload(cwd, session_id, skill, tool_input_extra=None, tool_result="ok"):
    """PostToolUse sobre la herramienta `Skill`. Campos comunes +
    `tool_name`/`tool_input` segun `hook-input-schemas.md` Sec.
    "PreToolUse / PostToolUse / ..." y la fila `Skill` de "Tool Input
    Schemas" (`skill`, `args` opcional).

    `cwd` del payload y `cwd` del proceso hijo se fijan al MISMO valor a
    proposito (mismo motivo que `test_boot_launcher.py`): ningun documento
    dice cual de los dos usa el hook para resolver donde escribir el
    registro, y afirmar uno concreto seria fijar una decision interna.
    """
    tool_input = {"skill": skill}
    if tool_input_extra:
        tool_input.update(tool_input_extra)
    return {
        "session_id": session_id,
        "transcript_path": str(Path(cwd) / "transcript.jsonl"),
        "cwd": str(cwd),
        "permission_mode": "default",
        "hook_event_name": "PostToolUse",
        "tool_name": "Skill",
        "tool_input": tool_input,
        "tool_result": tool_result,
        "tool_use_id": f"tooluse_{uuid.uuid4().hex[:8]}",
    }


def make_non_skill_payload(cwd, session_id, tool_name="Bash"):
    return {
        "session_id": session_id,
        "transcript_path": str(Path(cwd) / "transcript.jsonl"),
        "cwd": str(cwd),
        "permission_mode": "default",
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"command": "echo hi"} if tool_name == "Bash" else {},
        "tool_result": "hi",
        "tool_use_id": f"tooluse_{uuid.uuid4().hex[:8]}",
    }


def make_stop_payload(cwd, session_id, stop_hook_active=False):
    """Evento `Stop` -- campos comunes + `stop_hook_active`
    (`hook-input-schemas.md` Sec. "Stop / SubagentStop")."""
    return {
        "session_id": session_id,
        "transcript_path": str(Path(cwd) / "transcript.jsonl"),
        "cwd": str(cwd),
        "permission_mode": "default",
        "hook_event_name": "Stop",
        "stop_hook_active": stop_hook_active,
    }
