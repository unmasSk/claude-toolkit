"""Contrato de `hooks/checklist-gate.py` -- pieza 3 de
docs/plan/casillas-por-programa.md (D-052), evento `Stop`.

Modo test-first, pase de CONTRATO: una fila del contrato B del encargo (8
protecciones), un test cada una -- no el barrido exhaustivo de ramas (ese
llega en el endurecimiento, sobre el codigo real).

NOTA (2026-08-24): igual que `test_skill_checklist_inject.py`, Ultron
implemento este hook EN PARALELO mientras se escribia este contrato. La
subseccion 6 (fichero de tarea corrupto) se reescribio tras leer
`hooks/checklist-gate.py` real: el diseno original ("si por eso no puede
decidir, deja pasar avisando") se interpreto aqui como dos subcasos
posibles antes de ver el codigo; el codigo real resuelve la ambiguedad de
una sola forma, verificada, no adivinada -- ver el punto 5 de "ESQUEMA
REAL" en `conftest.py` y la clase `TestCorruptTaskFileIsTreatedAsMissing`
mas abajo para el detalle.

Este fichero NO depende de que `skill-checklist-inject.py` exista ni
funcione: siembra el registro por-sesion directamente con
`seed_registry()` (ver `conftest.py`, "ESQUEMA REAL" punto 3) -- el
contrato de cada hook se verifica por separado, mismo patron que
`test_customs_hook.py` prueba `validator.py`/`rejection.py` sin pasar por
la aduana.

Salida esperada, forma REAL verificada leyendo `hooks/checklist-gate.py`:
`{"decision": "block", "reason": "..."}` para bloquear; para "pasa" el
diseno dice literalmente "exit 0 mudo" (sin bloquear).

Cobertura de las 8 protecciones del encargo (contrato B):
  1. casillas ausentes/pending/in_progress -> block con lista
  2. todas completed -> mudo
  3. sin registro de sesion -> mudo (con tablero incompleto Y con tablero
     vacio)
  4. `stop_hook_active=true` -> NUNCA bloquea
  5. tercer intento de bloqueo en la sesion -> deja pasar avisando
  6. UN json de tarea corrupto -> se ignora, los demas cuentan; la
     casilla cuya unica fuente era ese fichero se trata como AUSENTE
     (bloquea si por eso falta algo, avisando por stderr que hubo
     ficheros rotos) -- nunca revienta, nunca bloquea EN SILENCIO (el
     aviso por stderr siempre esta), pero tampoco es un fail-open "no
     puedo decidir" (ese fail-open esta reservado a fallos de sistema,
     ver protocolos 3/7 y el edge case de registro corrupto)
  7. directorio de tareas inexistente -> deja pasar avisando
  8. el gate no lanza NINGUN proceso -- barrido estatico del fichero

Edge case anadido (fuera de la lista pero mismo principio de fail-open del
diseno, "ante error, JSON corrupto o tablero ilegible: DEJA PASAR"): el
registro de sesion EN SI mismo corrupto, y stdin totalmente malformado --
estos SI son fallos de sistema (el gate no puede ni empezar a evaluar) y
por tanto SI dejan pasar sin bloquear.
"""

import uuid

import pytest

from .conftest import (
    GATE_HOOK,
    HOOKS_DIR,
    fake_home_env,
    make_stop_payload,
    run_hook,
    run_hook_raw,
    seed_corrupt_registry,
    seed_registry,
    task_board_dir,
    write_corrupt_task,
    write_task,
)

# `fake_home`, `project_dir` son fixtures de `conftest.py` (pytest las
# descubre solas por nombre de parametro).


def _new_session():
    return f"sess-{uuid.uuid4().hex[:8]}"


class TestIncompleteBoardBlocksWithReason:
    """Protocolo 1: casillas ausentes/pending/in_progress -> bloquea con
    una lista que menciona lo que falta."""

    def test_pending_and_absent_items_are_named_in_the_reason(
        self, fake_home, project_dir
    ):
        session_id = _new_session()
        items = ["Confirmar modo de build", "Correr Moriarty", "Cerrar con Yoda"]
        seed_registry(project_dir, session_id, "unmassk-flow", items)

        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, items[0], "completed")
        write_task(board, 2, items[1], "pending")
        # items[2] ("Cerrar con Yoda") no tiene ningun fichero -> ausente

        payload = make_stop_payload(project_dir, session_id)
        rc, parsed, stdout, stderr = run_hook(
            GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", f"parsed={parsed!r}"
        reason = parsed.get("reason", "")
        assert items[1] in reason, f"la pending no aparece en reason: {reason!r}"
        assert items[2] in reason, f"la ausente no aparece en reason: {reason!r}"


class TestAllCompletedIsMute:
    """Protocolo 2: todas completed -> exit 0 mudo (sin salida)."""

    def test_no_output_when_everything_is_done(self, fake_home, project_dir):
        session_id = _new_session()
        items = ["Paso unico"]
        seed_registry(project_dir, session_id, "unmassk-close-session", items)

        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, items[0], "completed")

        payload = make_stop_payload(project_dir, session_id)
        rc, parsed, stdout, stderr = run_hook(
            GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert stdout.strip() == "", f"esperaba mudo, salio: {stdout!r}"


class TestNoSessionRegistryIsMute:
    """Protocolo 3: sin registro de sesion -> mudo, tanto con tablero
    incompleto como con tablero vacio."""

    def test_incomplete_board_without_registry_is_mute(self, fake_home, project_dir):
        session_id = _new_session()
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, "Una tarea cualquiera", "pending")

        payload = make_stop_payload(project_dir, session_id)
        rc, parsed, stdout, stderr = run_hook(
            GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert stdout.strip() == "", f"esperaba mudo, salio: {stdout!r}"

    def test_empty_board_without_registry_is_mute(self, fake_home, project_dir):
        session_id = _new_session()
        task_board_dir(fake_home, session_id)  # directorio creado, vacio

        payload = make_stop_payload(project_dir, session_id)
        rc, parsed, stdout, stderr = run_hook(
            GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert stdout.strip() == "", f"esperaba mudo, salio: {stdout!r}"


class TestStopHookActiveNeverBlocks:
    """Protocolo 4: `stop_hook_active=true` -> NUNCA bloquea, aunque el
    tablero este incompleto y el registro lo justifique."""

    def test_stop_hook_active_overrides_incomplete_board(self, fake_home, project_dir):
        session_id = _new_session()
        items = ["Item pendiente"]
        seed_registry(project_dir, session_id, "unmassk-flow", items)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, items[0], "pending")

        payload = make_stop_payload(project_dir, session_id, stop_hook_active=True)
        rc, parsed, stdout, stderr = run_hook(
            GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"stop_hook_active=true nunca debe bloquear; parsed={parsed!r}"
        )


class TestThirdBlockAttemptPassesWithWarning:
    """Protocolo 5: maximo 2 bloqueos por sesion; al tercer intento, deja
    pasar avisando (contador vive en el registro, mismo fichero a traves
    de las tres llamadas secuenciales)."""

    def test_third_call_in_a_row_stops_blocking(self, fake_home, project_dir):
        session_id = _new_session()
        items = ["Item que nunca se completa"]
        seed_registry(project_dir, session_id, "unmassk-flow", items)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, items[0], "pending")

        payload = make_stop_payload(project_dir, session_id, stop_hook_active=False)
        env = fake_home_env(fake_home)

        rc1, parsed1, out1, err1 = run_hook(GATE_HOOK, payload, cwd=project_dir, env=env)
        rc2, parsed2, out2, err2 = run_hook(GATE_HOOK, payload, cwd=project_dir, env=env)
        rc3, parsed3, out3, err3 = run_hook(GATE_HOOK, payload, cwd=project_dir, env=env)

        assert rc1 == 0 and parsed1 is not None and parsed1.get("decision") == "block", (
            f"1er intento deberia bloquear: parsed={parsed1!r} stderr={err1!r}"
        )
        assert rc2 == 0 and parsed2 is not None and parsed2.get("decision") == "block", (
            f"2o intento deberia bloquear: parsed={parsed2!r} stderr={err2!r}"
        )
        assert rc3 == 0, f"rc={rc3} stdout={out3!r} stderr={err3!r}"
        assert parsed3 is None or parsed3.get("decision") != "block", (
            f"3er intento tiene que dejar pasar avisando, no bloquear: "
            f"parsed={parsed3!r}"
        )
        assert err3.strip() != "", "el 3er intento tiene que avisar por stderr"


class TestCorruptTaskFileIsTreatedAsMissing:
    """Protocolo 6: un JSON de tarea corrupto se ignora -- los demas
    ficheros cuentan; la casilla que dependia de ese fichero se cuenta
    como AUSENTE (nunca bloquea a ciegas EN SILENCIO -- siempre avisa por
    stderr -- ni revienta), no como un fail-open de "no puedo decidir"
    (ver nota de modulo, "ESQUEMA REAL" punto 5 de `conftest.py`)."""

    def test_corrupt_extra_file_does_not_block_a_fully_completed_board(
        self, fake_home, project_dir
    ):
        """El corrupto es un fichero DE MAS (no corresponde a ninguna
        casilla esperada) -- los ficheros validos ya completan las dos
        casillas esperadas, asi que el resultado tiene que seguir siendo
        `mudo`, exactamente igual que si el corrupto no existiera."""
        session_id = _new_session()
        items = ["Casilla A", "Casilla B"]
        seed_registry(project_dir, session_id, "unmassk-flow", items)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, items[0], "completed")
        write_task(board, 2, items[1], "completed")
        write_corrupt_task(board, 3)

        payload = make_stop_payload(project_dir, session_id)
        rc, parsed, stdout, stderr = run_hook(
            GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert stdout.strip() == "", (
            f"un corrupto DE MAS no debe impedir el mudo cuando lo valido ya "
            f"completa todo: stdout={stdout!r}"
        )

    def test_corrupt_file_covering_the_missing_item_still_blocks_as_absent(
        self, fake_home, project_dir
    ):
        """Aqui el corrupto es el UNICO otro fichero ademas del que cubre
        la primera casilla. Verificado leyendo `_read_board_tasks`/
        `_violations` en el codigo real: un fichero roto nunca entra en
        el dict de tareas legibles, asi que "Casilla B" se cuenta como
        AUSENTE -- exactamente igual que si ese fichero no existiera --
        y el gate bloquea (avisando por stderr que hubo un fichero
        roto), no deja pasar en silencio ni por incertidumbre."""
        session_id = _new_session()
        items = ["Casilla A", "Casilla B"]
        seed_registry(project_dir, session_id, "unmassk-flow", items)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, items[0], "completed")
        write_corrupt_task(board, 2)

        payload = make_stop_payload(project_dir, session_id)
        rc, parsed, stdout, stderr = run_hook(
            GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is not None and parsed.get("decision") == "block", (
            f"'Casilla B' se queda sin fuente legible cuando su unico "
            f"fichero esta corrupto -- eso es 'ausente', y ausente "
            f"bloquea (protocolo 1): parsed={parsed!r} stderr={stderr!r}"
        )
        assert items[1] in parsed.get("reason", ""), (
            f"la casilla sin cubrir tiene que aparecer en la razon: "
            f"{parsed.get('reason')!r}"
        )
        assert stderr.strip() != "", (
            "tiene que avisar por stderr que hubo un fichero de tarea roto"
        )


class TestMissingTaskBoardDirectoryFailsOpen:
    """Protocolo 7: la clave del directorio de tareas no es el
    `session_id` (equipo, `CLAUDE_CODE_TASK_LIST_ID`...) y el directorio
    no existe en absoluto -> deja pasar avisando, nunca bloquea."""

    def test_absent_board_directory_never_blocks(self, fake_home, project_dir):
        session_id = _new_session()
        items = ["Casilla que nunca se puede verificar"]
        seed_registry(project_dir, session_id, "unmassk-flow", items)
        # Deliberadamente NO se crea `task_board_dir(fake_home, session_id)`.

        payload = make_stop_payload(project_dir, session_id)
        rc, parsed, stdout, stderr = run_hook(
            GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"directorio de tareas ausente nunca debe bloquear: parsed={parsed!r}"
        )
        assert stderr.strip() != "", "tiene que avisar por stderr al dejar pasar"


class TestGateNeverLaunchesAProcess:
    """Protocolo 8: el gate SOLO LEE -- ni tests, ni git, ni ningun otro
    proceso (R-009: 704 procesos huerfanos; D-046: medio millon de
    contexto). Barrido ESTATICO del fichero -- deliberadamente no una
    asercion de tiempo (<1s): un umbral de reloj es exactamente el tipo de
    asercion fragil que las reglas de este agente prohiben; la alternativa
    que el propio diseno ofrece (inspeccionar el codigo) no lo es.
    """

    # Patrones de USO real (llamada/import), no la palabra suelta -- el
    # propio fuente de `checklist-gate.py` menciona "subprocess" en su
    # docstring y en un comentario ("no subprocess, no network, no git
    # call"; "no git/subprocess helpers") precisamente para DECLARAR que
    # no lo usa. Un scan por substring ingenuo confundiria esa frase con
    # el propio uso -- de ahi los patrones anclados a sintaxis real
    # (`import subprocess`, `subprocess.algo(`, `Popen(`, ...) via regex.
    _FORBIDDEN_PATTERNS = (
        r"\bimport\s+subprocess\b",
        r"\bfrom\s+subprocess\b",
        r"\bsubprocess\.\w+\(",
        r"\bos\.system\(",
        r"\bos\.popen\(",
        r"\bos\.spawn\w*\(",
        r"\bos\.exec\w*\(",
        r"\bPopen\(",
        r"\bcheck_call\(",
        r"\bcheck_output\(",
    )

    def test_source_never_imports_or_calls_a_process_launcher(self):
        import re

        hook_path = HOOKS_DIR / "checklist-gate.py"
        assert hook_path.exists(), (
            f"{hook_path} no existe todavia -- ROJO esperado en este pase "
            "de contrato (test-first, antes de Ultron)"
        )
        source = hook_path.read_text(encoding="utf-8")
        found = [
            pattern
            for pattern in self._FORBIDDEN_PATTERNS
            if re.search(pattern, source)
        ]
        assert not found, (
            f"checklist-gate.py no debe lanzar procesos (protocolo 8): "
            f"encontrado {found!r} en el fuente"
        )


class TestCorruptSessionRegistryFailsOpen:
    """Edge case (misma regla general de fail-open del diseno: 'ante
    error, JSON corrupto o tablero ilegible: DEJA PASAR y lo dice') -- el
    registro de sesion en si mismo, no un fichero de tarea, es el que
    esta corrupto."""

    def test_corrupt_registry_json_never_blocks(self, fake_home, project_dir):
        session_id = _new_session()
        seed_corrupt_registry(project_dir, session_id)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, "Cualquier cosa", "pending")

        payload = make_stop_payload(project_dir, session_id)
        rc, parsed, stdout, stderr = run_hook(
            GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"registro corrupto nunca debe bloquear: parsed={parsed!r}"
        )
        assert "Traceback" not in stdout and "Traceback" not in stderr


class TestMalformedStdinFailsOpen:
    """Edge case: entrada estandar que ni siquiera es JSON -- el gate
    tampoco debe reventar ni bloquear."""

    def test_non_json_stdin_never_blocks(self, fake_home, project_dir):
        rc, stdout, stderr = run_hook_raw(
            GATE_HOOK,
            "esto tampoco es json {{{",
            cwd=project_dir,
            env=fake_home_env(fake_home),
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        parsed = None
        if stdout.strip():
            try:
                import json as _json

                parsed = _json.loads(stdout)
            except ValueError:
                parsed = None
        assert parsed is None or parsed.get("decision") != "block", (
            f"stdin malformado nunca debe bloquear: parsed={parsed!r}"
        )
        assert "Traceback" not in stdout and "Traceback" not in stderr
