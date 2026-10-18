"""Simulacro previo a publicar (Moriarty, 2026-10-18): tres fallos que
dejan las casillas por programa muertas en el uso real.

Contrato test-first (Dante, 2026-10-18), siempre por los hooks reales como
proceso separado:

1. Prefijo de plugin. Claude Code manda las skills de plugin con prefijo:
   `"skill": "unmassk-toolkit:unmassk-flow"` (16 de 17 cargas reales de
   flow en los transcripts del propietario). El inject tiene que cargar el
   MISMO manifiesto que con el nombre pelado, y el gate hacerlo cumplir.
   El nombre pelado sigue funcionando.
2. Tablero barrido. Claude Code borra todos los `N.json` unos 5 s despues
   de completar la ultima tarea y deja solo `.lock` y `.highwatermark`
   (verificado en `~/.claude/tasks/*` de esta maquina: `.lock` vacio,
   `.highwatermark` con el numero de tareas, p.ej. "19"). Un tablero con
   `.highwatermark` y sin ningun fichero de tarea = todo se completo -> el
   gate no bloquea. Un tablero que existe sin tareas y sin
   `.highwatermark` sigue como hoy: casillas ausentes -> bloquea.
3. Deriva de cwd. El registro vive bajo el top-level git del cwd del
   payload, no bajo el cwd: Skill cargada desde la raiz y Stop desde
   `src/` ven el mismo registro; cargar desde `src/` no crea
   `src/.claude/.unmassk/`. Un cwd fuera de git sigue usando el cwd (lo
   cubren todos los tests existentes, cuyo `project_dir` no es repo).

Valores esperados: del encargo y de este fichero (rutas construidas a
mano, registros comparados entre dos ejecuciones separadas), nunca leidos
del codigo de los hooks. Los manifiestos reales `checklists/*.json` solo
se LEEN como entrada (para construir el tablero), nunca como esperado de
la logica que se prueba.
"""

import json
import subprocess
import uuid
from pathlib import Path

from .conftest import (
    CHECKLISTS_DIR,
    GATE_HOOK,
    INJECT_HOOK,
    fake_home_env,
    make_skill_payload,
    make_stop_payload,
    registry_path,
    run_hook,
    task_board_dir,
    write_task,
)

SEL_TRIVIAL = "Procedimiento: Trivial"
SEL_CORTO = "Procedimiento: Corto"

# La lista Corto (encargo D-121, textos escritos a mano).
FLOW_CORTO_BOXES = [
    "Gate: sin feature de Flow abierto antes de arrancar uno nuevo",
    "Triaje: procedimiento decidido (Trivial/Corto/Completo) y seam declarada",
    "Brainstorm: gray areas resueltas y modo de build (test-first/linear) decidido",
    "Corto — Ultron hizo el cambio",
    "Corto — Dante entregó el test del cambio (si el proyecto tiene tests)",
    "Corto — Cerberus revisó el código y el test",
    "Corto — se corrigió una sola vez lo que señaló (código, Ultron; tests, Dante)",
    "Close — las pruebas de lo tocado en verde",
    "Corto — commit y push hechos, rama fusionada y borrada si la hubo, issue cerrada si la hay, y se preguntó si seguir",
]

PLUGIN = "unmassk-toolkit"


# ── helpers ─────────────────────────────────────────────────────────────

def _session():
    return f"sess-{uuid.uuid4().hex[:8]}"


def _prefixed(bare):
    return f"{PLUGIN}:{bare}"


def _manifest_boxes(basename):
    """Entrada (no esperado): las casillas de un manifiesto real, para
    poder construir un tablero que las complete."""
    data = json.loads((CHECKLISTS_DIR / f"{basename}.json").read_text(encoding="utf-8"))
    return list(data["boxes"])


def _inject(fake_home, cwd, sid, skill):
    rc, parsed, stdout, stderr = run_hook(
        INJECT_HOOK,
        make_skill_payload(cwd, sid, skill),
        cwd=cwd,
        env=fake_home_env(fake_home),
    )
    assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
    assert "Traceback" not in stderr, stderr
    return parsed, stdout, stderr


def _gate(fake_home, cwd, sid):
    rc, parsed, stdout, stderr = run_hook(
        GATE_HOOK,
        make_stop_payload(cwd, sid),
        cwd=cwd,
        env=fake_home_env(fake_home),
    )
    assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
    assert "Traceback" not in stderr, stderr
    return parsed, stdout, stderr


def _read_registry(project_root, sid):
    path = registry_path(project_root, sid)
    assert path.exists(), f"no hay registro en {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _entries_without_skill_name(registry):
    """Las entradas tal cual, salvo el campo `skill` (que puede guardar el
    nombre con o sin prefijo: el contrato no lo fija)."""
    return [{k: v for k, v in e.items() if k != "skill"} for e in registry["skills"]]


def _assert_silent(stdout):
    assert stdout.strip() == "", f"el gate tenia que dejar cerrar en silencio; stdout={stdout!r}"


def _assert_blocks(parsed, stdout):
    assert parsed is not None and parsed.get("decision") == "block", (
        f"el gate tenia que bloquear; stdout={stdout!r}"
    )
    return parsed.get("reason", "")


def _empty_board(fake_home, sid):
    """Directorio de tablero que existe, sin tareas y sin `.highwatermark`
    (Claude Code todavia no creo ninguna tarea)."""
    return task_board_dir(fake_home, sid)


def _wiped_board(fake_home, sid, created=19):
    """El tablero tal como lo deja Claude Code tras barrer: solo `.lock`
    (vacio) y `.highwatermark` (numero de tareas creadas), forma copiada
    de `~/.claude/tasks/83bfcf1f-.../` de esta maquina."""
    board = task_board_dir(fake_home, sid)
    (board / ".lock").write_text("", encoding="utf-8")
    (board / ".highwatermark").write_text(str(created), encoding="utf-8")
    return board


def _write_board(board, tasks):
    for i, (subject, status) in enumerate(tasks, start=1):
        write_task(board, i, subject, status)


def _done(subjects):
    return [(s, "completed") for s in subjects]


def _git_repo(tmp_path):
    """Repo git real y desechable, con una subcarpeta `src/`."""
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    return root.resolve()


# ── 1. prefijo de plugin ────────────────────────────────────────────────

class TestContractPluginPrefixedSkillName:
    """Bug: el inject recorta `unmassk-` de `unmassk-toolkit:unmassk-flow`,
    busca `checklists/toolkit:unmassk-flow.json`, no lo encuentra y calla:
    ni registro ni orden, y el gate no tiene nada que hacer cumplir."""

    def test_should_record_same_flow_entry_for_prefixed_and_bare_name(
        self, fake_home, project_dir
    ):
        sid_bare, sid_pref = _session(), _session()
        _inject(fake_home, project_dir, sid_bare, "unmassk-flow")
        _inject(fake_home, project_dir, sid_pref, _prefixed("unmassk-flow"))

        bare = _read_registry(project_dir, sid_bare)
        pref = _read_registry(project_dir, sid_pref)
        assert len(pref["skills"]) == 1, pref
        assert _entries_without_skill_name(pref) == _entries_without_skill_name(bare)
        assert "procedures" in pref["skills"][0], pref

    def test_should_emit_the_checklist_order_for_prefixed_flow(self, fake_home, project_dir):
        parsed, stdout, _ = _inject(fake_home, project_dir, _session(), _prefixed("unmassk-flow"))

        assert parsed is not None, f"sin orden de casillas; stdout={stdout!r}"
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert SEL_CORTO in ctx and FLOW_CORTO_BOXES[3] in ctx, ctx

    def test_should_record_same_entry_for_prefixed_close_session(self, fake_home, project_dir):
        sid_bare, sid_pref = _session(), _session()
        _inject(fake_home, project_dir, sid_bare, "unmassk-close-session")
        _inject(fake_home, project_dir, sid_pref, _prefixed("unmassk-close-session"))

        bare = _read_registry(project_dir, sid_bare)
        pref = _read_registry(project_dir, sid_pref)
        assert len(pref["skills"]) == 1, pref
        assert _entries_without_skill_name(pref) == _entries_without_skill_name(bare)

    def test_should_record_same_entry_for_prefixed_audit(self, fake_home, project_dir):
        sid_bare, sid_pref = _session(), _session()
        _inject(fake_home, project_dir, sid_bare, "unmassk-audit")
        _inject(fake_home, project_dir, sid_pref, _prefixed("unmassk-audit"))

        bare = _read_registry(project_dir, sid_bare)
        pref = _read_registry(project_dir, sid_pref)
        assert len(pref["skills"]) == 1, pref
        assert _entries_without_skill_name(pref) == _entries_without_skill_name(bare)

    def test_should_block_close_when_prefixed_close_session_boxes_are_missing(
        self, fake_home, project_dir
    ):
        sid = _session()
        _inject(fake_home, project_dir, sid, _prefixed("unmassk-close-session"))
        _empty_board(fake_home, sid)

        parsed, stdout, _ = _gate(fake_home, project_dir, sid)
        reason = _assert_blocks(parsed, stdout)
        assert "Agente de cierre — commit [NEXT] verificado con git log -1" in reason, reason

    def test_should_pass_when_prefixed_close_session_boxes_are_completed(
        self, fake_home, project_dir
    ):
        sid = _session()
        _inject(fake_home, project_dir, sid, _prefixed("unmassk-close-session"))
        _write_board(_empty_board(fake_home, sid), _done(_manifest_boxes("close-session")))

        # El registro tiene que existir: sin el, este silencio seria el
        # del bug (nada registrado), no el de las casillas cumplidas.
        assert len(_read_registry(project_dir, sid)["skills"]) == 1
        _assert_silent(_gate(fake_home, project_dir, sid)[1])

    def test_should_block_corto_box_left_open_under_prefixed_flow(self, fake_home, project_dir):
        sid = _session()
        _inject(fake_home, project_dir, sid, _prefixed("unmassk-flow"))
        open_box = FLOW_CORTO_BOXES[5]
        tasks = _done([SEL_CORTO] + [b for b in FLOW_CORTO_BOXES if b != open_box])
        _write_board(_empty_board(fake_home, sid), tasks + [(open_box, "pending")])

        parsed, stdout, _ = _gate(fake_home, project_dir, sid)
        reason = _assert_blocks(parsed, stdout)
        assert open_box in reason, reason

    def test_should_still_register_bare_flow_name(self, fake_home, project_dir):
        sid = _session()
        _inject(fake_home, project_dir, sid, "unmassk-flow")
        assert len(_read_registry(project_dir, sid)["skills"]) == 1


# ── 2. tablero barrido por Claude Code ──────────────────────────────────

class TestContractWipedBoardMeansAllCompleted:
    """Bug: Claude Code barre los `N.json` al completar la ultima tarea, el
    gate ve cero tareas y bloquea por "ausentes" lo que ya se completo."""

    def test_should_not_block_a_trivial_run_whose_board_was_wiped(self, fake_home, project_dir):
        sid = _session()
        _inject(fake_home, project_dir, sid, "unmassk-flow")
        assert len(_read_registry(project_dir, sid)["skills"]) == 1
        _wiped_board(fake_home, sid, created=1)

        _assert_silent(_gate(fake_home, project_dir, sid)[1])

    def test_should_not_block_a_corto_run_whose_board_was_wiped(self, fake_home, project_dir):
        sid = _session()
        _inject(fake_home, project_dir, sid, "unmassk-flow")
        assert len(_read_registry(project_dir, sid)["skills"]) == 1
        _wiped_board(fake_home, sid, created=1 + len(FLOW_CORTO_BOXES))

        _assert_silent(_gate(fake_home, project_dir, sid)[1])

    def test_should_not_block_a_wiped_board_with_flow_and_close_session(
        self, fake_home, project_dir
    ):
        """Extremo a extremo por la puerta real: nombres con prefijo, como
        los manda Claude Code, y tablero barrido al final."""
        sid = _session()
        _inject(fake_home, project_dir, sid, _prefixed("unmassk-flow"))
        _inject(fake_home, project_dir, sid, _prefixed("unmassk-close-session"))
        assert len(_read_registry(project_dir, sid)["skills"]) == 2
        _wiped_board(fake_home, sid)

        _assert_silent(_gate(fake_home, project_dir, sid)[1])

    def test_should_still_block_when_board_exists_without_tasks_or_highwatermark(
        self, fake_home, project_dir
    ):
        sid = _session()
        _inject(fake_home, project_dir, sid, "unmassk-close-session")
        board = _empty_board(fake_home, sid)
        (board / ".lock").write_text("", encoding="utf-8")

        parsed, stdout, _ = _gate(fake_home, project_dir, sid)
        reason = _assert_blocks(parsed, stdout)
        assert "Agente de cierre — commit [NEXT] verificado con git log -1" in reason, reason

    def test_should_still_check_tasks_when_highwatermark_and_task_files_coexist(
        self, fake_home, project_dir
    ):
        """El atajo "barrido = todo hecho" solo vale con CERO tareas: con
        una tarea pendiente todavia en disco, el tablero no se barrio."""
        sid = _session()
        _inject(fake_home, project_dir, sid, "unmassk-close-session")
        board = _wiped_board(fake_home, sid, created=4)
        boxes = _manifest_boxes("close-session")
        _write_board(board, _done(boxes[:-1]) + [(boxes[-1], "pending")])

        parsed, stdout, _ = _gate(fake_home, project_dir, sid)
        reason = _assert_blocks(parsed, stdout)
        assert boxes[-1] in reason, reason


# ── 3. deriva de cwd ────────────────────────────────────────────────────

class TestContractRegistryLivesAtGitTopLevel:
    """Bug: el registro se escribe bajo el cwd del payload; un Stop desde
    `src/` no ve lo cargado desde la raiz (y cierra sin mirar nada), y una
    carga desde `src/` siembra `src/.claude/.unmassk/`."""

    def test_should_block_stop_from_subfolder_on_skill_loaded_from_root(
        self, fake_home, tmp_path
    ):
        root = _git_repo(tmp_path)
        sid = _session()
        _inject(fake_home, root, sid, "unmassk-close-session")
        _empty_board(fake_home, sid)

        parsed, stdout, _ = _gate(fake_home, root / "src", sid)
        reason = _assert_blocks(parsed, stdout)
        assert "Agente de cierre — commit [NEXT] verificado con git log -1" in reason, reason

    def test_should_write_registry_at_top_level_when_loaded_from_subfolder(
        self, fake_home, tmp_path
    ):
        root = _git_repo(tmp_path)
        sid = _session()
        _inject(fake_home, root / "src", sid, "unmassk-close-session")

        expected = root / ".claude" / ".unmassk" / "session-checklists" / f"{sid}.json"
        assert expected.exists(), f"el registro no esta en la raiz del repo: {expected}"
        assert not (root / "src" / ".claude").exists(), (
            "cargar desde src/ creo src/.claude/ -- el registro no va ahi"
        )

    def test_should_block_stop_from_root_on_skill_loaded_from_subfolder(
        self, fake_home, tmp_path
    ):
        root = _git_repo(tmp_path)
        sid = _session()
        _inject(fake_home, root / "src", sid, "unmassk-close-session")
        _empty_board(fake_home, sid)

        parsed, stdout, _ = _gate(fake_home, root, sid)
        _assert_blocks(parsed, stdout)

    def test_should_count_blocks_in_one_registry_across_folders(self, fake_home, tmp_path):
        """El tope de 2 bloqueos por sesion es uno solo: un Stop desde la
        raiz y otro desde `src/` gastan los dos -> el tercero, desde la
        raiz, ya no bloquea."""
        root = _git_repo(tmp_path)
        sid = _session()
        _inject(fake_home, root, sid, "unmassk-close-session")
        _empty_board(fake_home, sid)

        _assert_blocks(*_gate(fake_home, root, sid)[:2])
        _assert_blocks(*_gate(fake_home, root / "src", sid)[:2])
        _assert_silent(_gate(fake_home, root, sid)[1])
