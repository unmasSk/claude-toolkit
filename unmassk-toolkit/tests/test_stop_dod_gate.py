"""
Tests for stop-dod-gate.py — freno duro de Definition of Done.

Comportamiento del hook
-----------------------
Stop hook opt-in. Lee `.claude/project-memory/config.json`; si tiene el campo
`test_command` (string), ejecuta ese comando al cierre de sesión.

[corregido 2026-08-06: este docstring y `_write_config()` decian
`.claude/git-memory-config.json` (sistema viejo). El hook se movio al
fichero nuevo `.claude/project-memory/config.json` el mismo dia (ver
comentario CONFIG_SUBPATH en stop-dod-gate.py) y el fichero de test no se
actualizo -- 4 de los 21 tests de entonces (TestCommandFailsBlocks
completa) llevaban corriendo en rojo silencioso porque `_write_config`
escribia en una ruta que el hook ya no lee: `_read_test_command` no
encontraba `config.json`, devolvia None, y el hook entraba siempre por
el camino "sin test_command", nunca por el de bloqueo. Confirmado
re-ejecutando la suite antes de este arreglo: 4 failed, 17 passed.]

- tests pasan (exit 0)   → DEJA cerrar (allow / exit 0 sin JSON de bloqueo).
- tests fallan (exit ≠0) → BLOQUEA: stdout JSON {"decision":"block","reason":"..."}.
- sin `test_command`     → DEJA cerrar (fail-safe, opt-in).
- error de infra         → FAIL-OPEN: deja cerrar, nunca atrapa al usuario.
- siempre devuelve JSON válido de Stop hook o sale sin output (allow implícito).

Decisión de diseño pendiente para Ultron
-----------------------------------------
La ejecución de `test_command` debe hacerse con `shell=False` usando
`shlex.split()` para tokenizar el string. Esto es obligatorio:

  1. `shell=True` es una superficie de inyección si test_command llega con
     metacaracteres (`;`, `&&`, `|`, `$(...)`, backticks). Aunque el valor
     proviene del fichero de config del proyecto (no del usuario en tiempo
     real), el principio de mínimo privilegio dicta que el hook no debe
     expandir shell.
  2. `shlex.split()` tokeniza correctamente comandos con argumentos entre
     comillas (`"python3 -m pytest unmassk-toolkit/tests -q"` → lista).
  3. Implicación para el test de metacaracteres (TestMetacharacterSafety):
     un `test_command` con `;` o `&&` como `"true ; rm -rf /"` tokenizado
     con shlex produce `["true", ";", "rm", "-rf", "/"]`, que subprocess
     ejecutará como `true` con argumentos literales `; rm -rf /`, no como
     dos comandos separados. El test verifica que NO se ejecute como shell
     (la parte después del `;` no corre como comando independiente).

  Si Ultron elige `shell=True` (con sanitización explícita), debe actualizar
  los tests de metacaracteres y documentar el por qué.

Timeout: Ultron debe definir un timeout razonable (recomendado: 60 s).
Los tests de timeout usan un comando que duerme más que el timeout configurado.

Formato I/O de Stop hook
------------------------
- Stdin:  JSON del evento Stop (puede ser `{}` o vacío — el hook no lo necesita).
- Stdout: JSON {"decision": "block", "reason": str}  → bloquea el cierre.
          Sin output (o exit 0)                       → permite el cierre.
- Exit:   0 siempre (el hook no comunica la decisión vía exit code).

Test surface: 3 responsabilidades (leer config, ejecutar comando, formatear
respuesta). El conteo de clases/tests de esta línea ha quedado desfasado
dos veces seguidas (decía "11 clases de test" cuando ya eran 9) -- para
el número real, `pytest --collect-only` en vez de confiar en esta cifra.
A fecha 2026-08-20: 24 clases / 52 tests en este fichero; junto con
`test_dod_gate_classify.py` (6 clases / 17 tests), 69 tests en verde.
[2026-08-06: +2 clases / +7 tests -- contrato "config corrupto debe avisar,
distinto de no-configurado" (RED en TestCorruptConfigMustWarn hasta que
Ultron implemente el aviso); también se corrigió la ruta de config
(`.claude/git-memory-config.json` → `.claude/project-memory/config.json`)
que había dejado 4 tests de TestCommandFailsBlocks en rojo silencioso
desde el movimiento del fichero de config el mismo día.]
[2026-08-20: +8 clases / +13 tests -- CONTRATO DE ACEPTACIÓN test-first
(RED antes de que Ultron implemente) para la clasificación de exit
5/1/2 de `test_command` cuando ES pytest de verdad, en vez de tratar
cualquier exit ≠0 como bloqueo: exit 5 (suite vacía) permite con aviso
una vez por sesión; exit 1 sigue bloqueando; exit 2 exige parsear
"No module named 'X'" de la salida real y decidir según si X vive en
disco/git (never-written permite con aviso una vez por módulo/sesión,
deleted-tracked y third-party bloquean, sin-match bloquea, mezcla
bloquea si al menos uno bloquea); y anti-goteo por firma keyeada a
session_id (firma repetida en la misma sesión = recordatorio de una
línea sin volcado; firma nueva o sesión distinta = reason completa).
Estas clases invocan pytest de verdad (`_PYTEST_COMMAND`), no un
`python -c "sys.exit(N)"` simulado -- necesario porque lo que hay que
probar es que el hook sabe leer la salida real de pytest, no solo
reaccionar al exit code. Ver TestRealPytestEmptySuiteAllows,
TestRealPytestFailureBlocks, TestCollectionErrorNoModuleMatch,
TestCollectionErrorThirdPartyModuleBlocks,
TestCollectionErrorNeverWrittenLocalModuleAllows,
TestCollectionErrorDeletedTrackedModuleBlocks,
TestCollectionErrorMixedMissingModules, TestBlockSignatureDedupBySession.]
Not tested: comportamiento del comando de test en sí mismo (eso es del usuario);
integración real con Claude Code (fuera de alcance de tests unitarios de hook);
OSError de permisos reales (chmod) -- no reproducible de forma fiable en
Windows, cubierto en su lugar por el caso "config.json es un directorio"
(mismo except OSError, repro cross-platform confirmada a mano).
[2026-08-20] la sub-rama "seg existe, el fuente concreto de X está
PRESENTE en disco pero revienta al importar" (bloquea) no tiene un
repro real construible vía pytest genuino: si el fichero de X existe y
es importable, CPython no levanta ModuleNotFoundError nombrando
exactamente ese X (se probó a mano: SyntaxError propio da
"SyntaxError", no "No module named"; un ImportError encadenado da
"cannot import name", no "No module named"; el X que SÍ aparece en un
ModuleNotFoundError real siempre resultó ser el que está ausente, nunca
el presente). Queda para la pasada de hardening (después de que Ultron
implemente) construirlo a nivel unitario contra la función de
clasificación en sí, no contra pytest real -- de momento el contrato
solo fija que las dos ramas realmente observables (ausente+trackeado
→ bloquea, ausente+no-trackeado → permite) están cubiertas.
"""

import json
import os
import sys
import textwrap

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, LIB_DIR, run_cmd, run_script, git_cmd

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from git_helpers import UNMASSK_RUNTIME_DIR  # real constant -- no ruta a mano

HOOK_PATH = os.path.join(HOOKS_DIR, "stop-dod-gate.py")

# Payload mínimo de Stop hook — el hook no usa los campos del evento
_STOP_PAYLOAD = json.dumps({"hook_event_name": "Stop"})


# ── Helpers ────────────────────────────────────────────────────────────────────

# Misma ruta que CONFIG_SUBPATH en stop-dod-gate.py -- no se importa
# directamente (el hook se invoca como subprocess, no como módulo) pero
# debe seguir siendo la MISMA cadena si el hook vuelve a moverse.
_CONFIG_SUBPATH = os.path.join(".claude", "project-memory", "config.json")


def _write_config(repo: str, config: dict) -> None:
    """Escribe .claude/project-memory/config.json en el repo temporal."""
    config_path = os.path.join(repo, _CONFIG_SUBPATH)
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f)


def _write_raw_config(repo: str, raw_content: str) -> None:
    """Escribe contenido crudo (no necesariamente JSON válido) en
    .claude/project-memory/config.json. Usado para simular un config
    corrupto/ilegible como JSON -- `_write_config` de arriba siempre
    produce JSON válido por diseño."""
    config_path = os.path.join(repo, _CONFIG_SUBPATH)
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(raw_content)


def _run_hook(cwd: str, payload: str = _STOP_PAYLOAD):
    """Invoca stop-dod-gate.py con el payload dado. Devuelve (rc, parsed, stdout, stderr)."""
    rc, stdout, stderr = run_cmd(
        [sys.executable, HOOK_PATH],
        cwd=cwd,
        input_text=payload,
        timeout=90,  # amplio para no interferir con el timeout interno del hook
    )
    try:
        parsed = json.loads(stdout) if stdout.strip() else None
    except (json.JSONDecodeError, ValueError):
        parsed = None
    return rc, parsed, stdout, stderr


def _makes_tmp_dir(tmp_path: object, name: str = "workdir") -> str:
    """Crea un directorio temporal que NO es un git repo (cwd genérico del hook)."""
    d = str(tmp_path / name)
    os.makedirs(d)
    return d


# ── Helpers -- clasificación de salida real de pytest (2026-08-20) ────────────
#
# Contrato de aceptación nuevo: el hook debe saber leer la salida REAL de
# pytest (no un `python -c "sys.exit(N)"` simulado) para distinguir suite
# vacía / fallo real / error de colección. `_PYTEST_COMMAND` invoca pytest
# de verdad; el hook hereda su cwd = workdir (confirmado leyendo
# `_run_test_command()` en stop-dod-gate.py: no pasa `cwd=` explícito a
# `subprocess.run`, así que hereda el cwd del propio proceso del hook, que
# es `workdir` porque `_run_hook()` ya lanza el hook con `cwd=workdir`).

_PYTEST_COMMAND = f"{sys.executable} -m pytest -q"


def _write_source_file(repo: str, relpath: str, content: str) -> None:
    """Escribe un fichero fuente arbitrario (test_*.py, paquete, etc.) en
    el workdir, creando directorios intermedios si hace falta. Distinto de
    `_write_config`/`_write_raw_config`, que solo escriben config.json."""
    path = os.path.join(repo, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _stop_payload(session_id: str) -> str:
    """Payload de evento Stop con `session_id` explícito -- el evento Stop
    real de Claude Code trae este campo (hecho verificado por Bilbo, no
    reinvestigado aquí). Necesario porque el anti-goteo de esta mejora
    dedup-a por session_id: dos invocaciones con el mismo session_id deben
    poder verse como "la misma sesión" desde el test."""
    return json.dumps({"hook_event_name": "Stop", "session_id": session_id})


def _init_git_repo_with_commit(workdir: str) -> None:
    """git init + primer commit (vacío) en el workdir. Mismo patrón que el
    fixture `tmp_repo` de conftest.py, pero sobre un workdir con nombre
    propio en lugar de `tmp_path / "repo"` -- estos tests necesitan
    controlar el nombre del workdir para los escenarios que lo comparan
    contra uno hermano no-git."""
    rc, _, stderr = git_cmd(["init"], workdir)
    assert rc == 0, f"git init falló en el fixture: {stderr!r}"
    rc, _, stderr = git_cmd(["commit", "--allow-empty", "-m", "init"], workdir)
    assert rc == 0, f"git commit inicial falló en el fixture: {stderr!r}"


def _git_add_all_commit(workdir: str, message: str) -> None:
    """git add -A + commit en el workdir -- fixture, no una acción del
    agente sobre este repositorio; es código que pytest ejecuta al correr
    la suite, igual que el resto de fixtures git de este fichero de
    tests."""
    rc, _, stderr = git_cmd(["add", "-A"], workdir)
    assert rc == 0, f"git add falló en el fixture: {stderr!r}"
    rc, _, stderr = git_cmd(["commit", "-m", message], workdir)
    assert rc == 0, f"git commit falló en el fixture: {stderr!r}"


# ── Caso 1: test_command configurado + tests pasan → DEJA cerrar ──────────────

class TestCommandPassesAllowsClose:
    """test_command configurado; el comando sale 0 → el hook no bloquea."""

    def test_passing_command_does_not_block(self, tmp_path):
        """Comando que sale 0 → sin decision:block en stdout."""
        workdir = _makes_tmp_dir(tmp_path)
        # `python3 -c "pass"` siempre sale 0
        _write_config(workdir, {"test_command": f"{sys.executable} -c \"pass\""})

        rc, parsed, stdout, stderr = _run_hook(workdir)

        assert rc == 0, f"Hook debe salir 0; rc={rc!r}, stderr={stderr!r}"
        # Allow: o no hay JSON en stdout, o si lo hay, no es decision:block
        if parsed is not None:
            assert parsed.get("decision") != "block", (
                f"Comando que pasa no debe producir block; parsed={parsed!r}"
            )

    def test_passing_command_stdout_is_not_block_json(self, tmp_path):
        """Verificación explícita: si hay JSON en stdout, decision != 'block'."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": f"{sys.executable} -c \"import sys; sys.exit(0)\""})

        rc, parsed, stdout, _ = _run_hook(workdir)

        assert rc == 0
        if stdout.strip():
            # Si el hook emite algo, debe ser JSON válido y no block
            assert parsed is not None, f"Si hay stdout, debe ser JSON válido; stdout={stdout!r}"
            assert parsed.get("decision") != "block"


# ── Caso 2: test_command configurado + tests fallan → BLOQUEA ─────────────────

class TestCommandFailsBlocks:
    """test_command configurado; el comando sale ≠0 → decision:block."""

    def test_failing_command_produces_block_decision(self, tmp_path):
        """Comando que sale 1 → stdout JSON con decision:block."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": f"{sys.executable} -c \"import sys; sys.exit(1)\""})

        rc, parsed, stdout, stderr = _run_hook(workdir)

        assert rc == 0, f"Hook siempre sale 0; rc={rc!r}"
        assert parsed is not None, f"Debe emitir JSON en stdout; stdout={stdout!r}"
        assert parsed.get("decision") == "block", (
            f"Tests fallidos deben bloquear; parsed={parsed!r}"
        )

    def test_block_reason_is_non_empty_string(self, tmp_path):
        """El campo 'reason' del bloqueo debe ser un string no vacío."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": f"{sys.executable} -c \"raise SystemExit(2)\""})

        rc, parsed, _, _ = _run_hook(workdir)

        assert rc == 0
        assert parsed is not None
        assert parsed.get("decision") == "block"
        reason = parsed.get("reason", "")
        assert isinstance(reason, str) and len(reason) > 0, (
            f"'reason' debe ser string no vacío; reason={reason!r}"
        )

    def test_block_reason_mentions_test_failure(self, tmp_path):
        """El reason del bloqueo debe mencionar que los tests están en rojo."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": f"{sys.executable} -c \"import sys; sys.exit(1)\""})

        rc, parsed, _, _ = _run_hook(workdir)

        assert rc == 0
        assert parsed is not None
        assert parsed.get("decision") == "block"
        reason = parsed.get("reason", "").lower()
        # El mensaje debe indicar fallo de tests o que hay que arreglarlos
        assert any(keyword in reason for keyword in ["test", "fail", "rojo", "red", "fix", "arregl"]), (
            f"El reason debe mencionar el fallo de tests; reason={parsed.get('reason')!r}"
        )

    def test_block_reason_includes_hint_when_output_available(self, tmp_path):
        """Si el comando produjo output, el reason debe incluir una pista de qué falló."""
        workdir = _makes_tmp_dir(tmp_path)
        # Comando que imprime algo a stderr y falla
        fail_script = f"{sys.executable} -c \"import sys; print('FAILED: assert 1==2', file=sys.stderr); sys.exit(1)\""
        _write_config(workdir, {"test_command": fail_script})

        rc, parsed, _, _ = _run_hook(workdir)

        assert rc == 0
        assert parsed is not None
        assert parsed.get("decision") == "block"
        reason = parsed.get("reason", "")
        # El reason debe contener algún indicio del output del comando fallido
        # (puede ser el stderr, el exit code, o ambos)
        assert len(reason) > 20, (
            f"El reason con output disponible debe contener una pista útil; "
            f"reason={reason!r}"
        )


# ── Caso 3: sin test_command → DEJA cerrar ────────────────────────────────────

class TestNoCommandConfigAllowsClose:
    """Sin test_command en config (o sin config) → fail-safe opt-in, no bloquea."""

    def test_config_without_test_command_does_not_block(self, tmp_path):
        """Config existe pero sin campo test_command → no bloquea."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"repo_type": "trunk"})  # config real del proyecto

        rc, parsed, stdout, _ = _run_hook(workdir)

        assert rc == 0
        if parsed is not None:
            assert parsed.get("decision") != "block", (
                f"Sin test_command, no debe bloquear; parsed={parsed!r}"
            )

    def test_no_config_file_does_not_block(self, tmp_path):
        """Sin fichero .claude/project-memory/config.json → no bloquea."""
        workdir = _makes_tmp_dir(tmp_path)
        # No creamos ningún config

        rc, parsed, stdout, _ = _run_hook(workdir)

        assert rc == 0
        if parsed is not None:
            assert parsed.get("decision") != "block"

    def test_test_command_null_does_not_block(self, tmp_path):
        """test_command: null en config → tratado como ausente, no bloquea."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": None})

        rc, parsed, stdout, _ = _run_hook(workdir)

        assert rc == 0
        if parsed is not None:
            assert parsed.get("decision") != "block"

    def test_test_command_empty_string_does_not_block(self, tmp_path):
        """test_command: '' (cadena vacía) → tratado como ausente, no bloquea."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": ""})

        rc, parsed, stdout, _ = _run_hook(workdir)

        assert rc == 0
        if parsed is not None:
            assert parsed.get("decision") != "block"


# ── Caso 4: error de infraestructura → FAIL-OPEN ──────────────────────────────

class TestInfraErrorsFailOpen:
    """Cualquier error del hook en sí mismo → fail-open (deja cerrar).

    Contraste con pre-merge-gate que falla cerrado: aquí un bug del hook
    NO debe dejar al usuario sin poder cerrar la sesión jamás.
    """

    def test_unreadable_config_fails_open(self, tmp_path):
        """Config que no se puede leer → fail-open, no bloquea.

        (No AVISA todavía -- eso es el gap cubierto por
        TestCorruptConfigMustWarn más abajo. Este test solo fija la mitad
        "no bloquea" del contrato de fail-open.)
        """
        workdir = _makes_tmp_dir(tmp_path)
        # Crear un fichero con JSON inválido para simular config corrupta
        _write_raw_config(workdir, "{ INVALID JSON }")

        rc, parsed, stdout, _ = _run_hook(workdir)

        assert rc == 0, "Config ilegible debe resultar en fail-open (exit 0)"
        if parsed is not None:
            assert parsed.get("decision") != "block", (
                f"Config corrupta debe fail-open, no bloquear; parsed={parsed!r}"
            )

    def test_nonexistent_binary_fails_open(self, tmp_path):
        """test_command apunta a un binario inexistente → fail-open."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": "/absolutely/nonexistent/binary-xyz-12345 --run"})

        rc, parsed, stdout, _ = _run_hook(workdir)

        assert rc == 0, "Binario inexistente debe resultar en fail-open (exit 0)"
        if parsed is not None:
            assert parsed.get("decision") != "block", (
                f"FileNotFoundError debe fail-open; parsed={parsed!r}"
            )

    def test_timeout_fails_open(self, tmp_path):
        """Comando que excede el timeout del hook → fail-open.

        El hook debe tener un timeout interno. Este test usa un comando que
        duerme 120 s (mucho más que cualquier timeout razonable).
        El test tiene timeout=90 s en run_cmd: si el hook NO implementa
        timeout interno y espera los 120 s, este test fallará por timeout
        del test runner, lo que también detecta el problema.
        """
        workdir = _makes_tmp_dir(tmp_path)
        # Duerme 120 s — más que cualquier timeout razonable del hook (≤60 s)
        sleep_cmd = f"{sys.executable} -c \"import time; time.sleep(120)\""
        _write_config(workdir, {"test_command": sleep_cmd})

        rc, parsed, stdout, stderr = _run_hook(workdir)

        assert rc == 0, (
            f"Timeout del comando debe resultar en fail-open (exit 0); "
            f"rc={rc!r}, stderr={stderr!r}"
        )
        if parsed is not None:
            assert parsed.get("decision") != "block", (
                f"Timeout de comando debe fail-open, no bloquear; parsed={parsed!r}"
            )

    def test_exception_in_hook_does_not_crash(self, tmp_path):
        """El hook nunca debe salir con exit ≠0 por una excepción interna."""
        workdir = _makes_tmp_dir(tmp_path)
        # Config que provocará un error interno si el hook no lo maneja:
        # test_command es un objeto en lugar de string
        _write_config(workdir, {"test_command": {"not": "a string"}})

        rc, parsed, stdout, _ = _run_hook(workdir)

        assert rc == 0, (
            f"Excepción interna no debe causar exit ≠0; rc={rc!r}"
        )
        # No debe bloquear — fail-open
        if parsed is not None:
            assert parsed.get("decision") != "block"


# ── Caso 5: sin cambios relevantes / repo sin tests → no bloquea ──────────────

class TestNoRelevantChanges:
    """Escenarios donde no hay trabajo que testear → no bloquea."""

    def test_hook_does_not_block_on_empty_workdir(self, tmp_path):
        """Directorio de trabajo sin nada relevante → no bloquea (con test_command)."""
        workdir = _makes_tmp_dir(tmp_path)
        # test_command que sale 0 — simula suite vacía que pasa
        _write_config(workdir, {"test_command": f"{sys.executable} -c \"pass\""})

        rc, parsed, _, _ = _run_hook(workdir)

        assert rc == 0
        if parsed is not None:
            assert parsed.get("decision") != "block"


# ── Caso 6: JSON válido siempre ────────────────────────────────────────────────

class TestAlwaysValidJson:
    """El hook siempre devuelve JSON válido cuando emite algo a stdout."""

    def test_block_output_is_valid_json(self, tmp_path):
        """Cuando bloquea, el stdout es JSON parseable."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": f"{sys.executable} -c \"import sys; sys.exit(1)\""})

        rc, _, stdout_raw, _ = _run_hook(workdir)

        assert rc == 0
        if stdout_raw.strip():
            try:
                parsed = json.loads(stdout_raw)
            except json.JSONDecodeError as e:
                pytest.fail(
                    f"stdout del hook debe ser JSON válido cuando bloquea; "
                    f"error={e!r}, stdout={stdout_raw!r}"
                )
            assert "decision" in parsed, f"JSON de bloqueo debe tener campo 'decision'; got={parsed!r}"

    def test_allow_path_exits_zero(self, tmp_path):
        """Cuando no bloquea, exit code es 0."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": f"{sys.executable} -c \"pass\""})

        rc, _, _, _ = _run_hook(workdir)

        assert rc == 0

    def test_empty_stdin_does_not_crash(self, tmp_path):
        """stdin vacío (sin payload de Stop) → hook no crashea, exit 0."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": f"{sys.executable} -c \"pass\""})

        rc, parsed, stdout, stderr = _run_hook(workdir, payload="")

        assert rc == 0, f"stdin vacío no debe crashear; rc={rc!r}, stderr={stderr!r}"

    def test_malformed_stdin_does_not_crash(self, tmp_path):
        """stdin con JSON inválido → fail-open, exit 0."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": f"{sys.executable} -c \"pass\""})

        rc, _, _, stderr = _run_hook(workdir, payload="{NOT VALID JSON}")

        assert rc == 0, f"stdin inválido no debe crashear; rc={rc!r}, stderr={stderr!r}"


# ── Caso 7: config corrupto vs no configurado -- deben distinguirse ───────────
#
# Gap reportado 2026-08-06: `_read_test_command()` atrapa
# `(OSError, json.JSONDecodeError)` y devuelve None en los DOS casos, y
# `main()` trata "None" siempre igual: `if not test_command: sys.exit(0)`.
# Un config.json CORRUPTO (JSON inválido, o ilegible) y un config.json SIN
# `test_command` declarado (opt-in no configurado) producen HOY la MISMA
# salida: silencio total, exit 0, stdout vacío, stderr vacío.
#
# Confirmado a mano antes de escribir estos tests (ver informe): ambos
# casos dan rc=0, stdout='', stderr=''.
#
# Eso es fallo callado, prohibido por el modelo de amenaza de este
# proyecto ("un fallo no debe pasar callado" -- unmassk-standards §4,
# "the system against itself"). El caso "no configurado" es CORRECTO y no
# debe cambiar (TestNoCommandStaysSilent lo fija como regresión). El caso
# "corrupto" SÍ debe cambiar: el hook tiene que avisar (stderr, o
# cualquier warning visible) que el config está corrupto -- sin dejar de
# ser fail-open (nunca debe bloquear el cierre de sesión por esto; eso es
# competencia de config.py/Ultron, no de estos tests).

class TestNoCommandStaysSilent:
    """Config SIN test_command (o config ausente) -- opt-in no
    configurado. Este es el comportamiento CORRECTO y NO debe cambiar:
    silencio total, ni una línea en stderr. Sirve de línea base directa
    para contrastar con TestCorruptConfigMustWarn de abajo -- los dos
    casos deben verse DISTINTOS y hoy no se ven."""

    def test_valid_config_without_test_command_is_fully_silent(self, tmp_path):
        """config.json válido, sin `test_command` → stdout Y stderr vacíos."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"repo_type": "gitflow"})

        rc, parsed, stdout, stderr = _run_hook(workdir)

        assert rc == 0
        assert stdout.strip() == "", f"no configurado no debe emitir stdout; stdout={stdout!r}"
        assert stderr.strip() == "", (
            f"no configurado es opt-in válido, no debe avisar nada; "
            f"stderr={stderr!r}"
        )

    def test_missing_config_file_is_fully_silent(self, tmp_path):
        """Sin fichero config.json en absoluto → stdout Y stderr vacíos."""
        workdir = _makes_tmp_dir(tmp_path)

        rc, parsed, stdout, stderr = _run_hook(workdir)

        assert rc == 0
        assert stdout.strip() == ""
        assert stderr.strip() == "", (
            f"sin config.json es el estado por defecto de un proyecto "
            f"recién iniciado, no debe avisar nada; stderr={stderr!r}"
        )


class TestCorruptConfigMustWarn:
    """Config PRESENTE pero corrupto/ilegible como JSON → debe AVISAR,
    distinto del silencio total de TestNoCommandStaysSilent. Fail-open se
    mantiene (rc=0, nunca bloquea), pero el silencio TOTAL no es
    aceptable: hoy `_read_test_command()` atrapa
    `(OSError, json.JSONDecodeError)` y devuelve None, indistinguible del
    caso "no configurado" para quien lee la salida del hook.

    RED hoy (2026-08-06, confirmado a mano antes de escribir estos tests):
    un config.json con `{ INVALID JSON }` produce rc=0, stdout='',
    stderr='' -- el mismo silencio que sin configurar."""

    def test_invalid_json_syntax_emits_visible_warning(self, tmp_path):
        """config.json con JSON inválido → el hook debe avisar (stderr no
        vacío), no tragárselo en silencio."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_raw_config(workdir, "{ INVALID JSON }")

        rc, parsed, stdout, stderr = _run_hook(workdir)

        assert rc == 0, "config corrupto sigue siendo fail-open (exit 0)"
        if parsed is not None:
            assert parsed.get("decision") != "block", (
                f"config corrupto no debe bloquear el cierre; parsed={parsed!r}"
            )
        assert stderr.strip() != "", (
            "config.json corrupto (JSON inválido) no debe pasar en silencio "
            "total -- el hook debe avisar por stderr que el config no se "
            f"pudo leer. stdout={stdout!r} stderr={stderr!r}"
        )

    def test_invalid_json_warning_mentions_config_problem(self, tmp_path):
        """El aviso, cuando exista, debe señalar hacia el problema real
        (config/JSON/parseo), no ser un mensaje genérico sin relación."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_raw_config(workdir, "{ INVALID JSON }")

        rc, parsed, stdout, stderr = _run_hook(workdir)

        assert rc == 0
        warning = stderr.lower()
        assert any(
            keyword in warning
            for keyword in [
                "config", "json", "pars", "corrupt", "inválid", "invalid",
                "malformed", "leer", "read",
            ]
        ), (
            f"el aviso de config corrupto debe mencionar el problema real "
            f"(config/JSON/parseo), no ser genérico; stderr={stderr!r}"
        )

    def test_directory_at_config_path_emits_visible_warning(self, tmp_path):
        """config.json existe como DIRECTORIO (no fichero) → open() lanza
        OSError/PermissionError, mismo camino silencioso que JSON inválido.

        Repro cross-platform confirmada a mano: en Windows produce
        PermissionError (subclase de OSError) al abrir un directorio en
        modo lectura; en POSIX típicamente IsADirectoryError (también
        subclase de OSError). Ambos caen en el mismo
        `except (OSError, json.JSONDecodeError): return None`, así que
        este es un segundo repro real del mismo gap, no una variante
        cosmética del primero."""
        workdir = _makes_tmp_dir(tmp_path)
        config_path = os.path.join(workdir, _CONFIG_SUBPATH)
        os.makedirs(config_path)  # config.json como directorio, no fichero

        rc, parsed, stdout, stderr = _run_hook(workdir)

        assert rc == 0, "config ilegible (directorio) sigue siendo fail-open"
        if parsed is not None:
            assert parsed.get("decision") != "block", (
                f"config ilegible no debe bloquear el cierre; parsed={parsed!r}"
            )
        assert stderr.strip() != "", (
            "config.json ilegible como fichero (es un directorio) no debe "
            f"pasar en silencio total; stdout={stdout!r} stderr={stderr!r}"
        )

    def test_corrupt_config_warning_differs_from_not_configured_silence(self, tmp_path):
        """Verificación directa del gap: mismo hook, dos configs
        distintos (uno corrupto, uno simplemente sin test_command) → las
        dos salidas por stderr deben DIFERIR. Hoy son idénticas (ambas
        vacías), que es exactamente el fallo callado reportado."""
        not_configured_dir = _makes_tmp_dir(tmp_path, "not_configured")
        _write_config(not_configured_dir, {"repo_type": "gitflow"})
        _, _, _, stderr_not_configured = _run_hook(not_configured_dir)

        corrupt_dir = _makes_tmp_dir(tmp_path, "corrupt")
        _write_raw_config(corrupt_dir, "{ INVALID JSON }")
        _, _, _, stderr_corrupt = _run_hook(corrupt_dir)

        assert stderr_not_configured.strip() == "", (
            "el caso 'no configurado' debe seguir en silencio total (línea base)"
        )
        assert stderr_corrupt.strip() != stderr_not_configured.strip(), (
            "un config CORRUPTO y un config SIN test_command no pueden "
            "producir la misma salida (mismo silencio) -- son fallos "
            "distintos y quien lee la salida del hook tiene que poder "
            f"distinguirlos. corrupto: stderr={stderr_corrupt!r} | "
            f"no configurado: stderr={stderr_not_configured!r}"
        )


# ── Caso 8: clasificación de la salida REAL de pytest -- exit 5/1/2 ───────────
#
# CONTRATO DE ACEPTACIÓN 2026-08-20 (test-first, RED antes de que Ultron
# implemente). Hoy el hook trata CUALQUIER exit ≠0 de test_command como
# bloqueo -- la mejora reportada por el propietario exige clasificar el
# resultado antes de decidir:
#   - exit 0                → permite (ya cubierto arriba, sin cambios).
#   - exit 5 (suite vacía, pytest "no tests ran") → permite, con un aviso
#     informativo UNA vez por sesión (no un bloqueo).
#   - exit 1 (tests corren y fallan de verdad)     → bloquea (ya cubierto
#     arriba con exit codes simulados; aquí se confirma con pytest real).
#   - exit 2 (error de colección)                  → ver Caso 9 más abajo,
#     requiere parsear "No module named 'X'".
#
# Estas clases invocan pytest DE VERDAD (`_PYTEST_COMMAND`), no un
# `python -c "sys.exit(N)"` simulado -- lo que hay que probar es que el
# hook sabe LEER y clasificar la salida real de pytest 9.0.2 / Python
# 3.14, no solo reaccionar al exit code. Exit codes confirmados a mano
# antes de escribir las aserciones (ver hechos de Bilbo en el prompt de
# esta tarea, no reinvestigados aquí).

class TestRealPytestEmptySuiteAllows:
    """exit 5 (pytest real, ningún test recogido) -- debe DEJAR cerrar,
    no bloquear. RED hoy: el hook actual bloquea ante CUALQUIER exit ≠0,
    incluido el 5."""

    def test_empty_suite_exit5_allows_close(self, tmp_path):
        """Workdir sin ningún test_*.py -- pytest real sale 5 ("no tests
        ran"). El hook no debe bloquear el cierre."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": _PYTEST_COMMAND})

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-empty-1"))

        assert rc == 0, f"Hook siempre sale 0; rc={rc!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"Suite vacía (exit 5) no debe bloquear el cierre; "
            f"parsed={parsed!r}, stdout={stdout!r}, stderr={stderr!r}"
        )

    def test_empty_suite_warning_does_not_repeat_same_session(self, tmp_path):
        """El aviso informativo de suite vacía es UNA vez por sesión: dos
        invocaciones seguidas con el MISMO session_id y la misma suite
        vacía no deben repetir el aviso en la segunda."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": _PYTEST_COMMAND})
        session = "sess-empty-repeat"

        rc1, parsed1, _, stderr1 = _run_hook(workdir, payload=_stop_payload(session))
        rc2, parsed2, _, stderr2 = _run_hook(workdir, payload=_stop_payload(session))

        assert rc1 == 0 and rc2 == 0
        assert parsed1 is None or parsed1.get("decision") != "block"
        assert parsed2 is None or parsed2.get("decision") != "block"
        assert stderr2.strip() == "", (
            "El aviso de suite vacía debe verse UNA vez por sesión -- la "
            f"segunda invocación con el mismo session_id no debe repetirlo; "
            f"stderr primera={stderr1!r}, stderr segunda={stderr2!r}"
        )


class TestRealPytestFailureBlocks:
    """exit 1 (pytest real: tests corren y fallan) -- debe seguir
    bloqueando, confirmado contra la salida real de pytest (no
    simulada)."""

    def test_real_pytest_failure_exit1_blocks(self, tmp_path):
        workdir = _makes_tmp_dir(tmp_path)
        _write_source_file(
            workdir,
            "test_real_fail.py",
            "def test_should_pass_but_fails():\n"
            "    assert 1 == 2\n",
        )
        _write_config(workdir, {"test_command": _PYTEST_COMMAND})

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-fail-1"))

        assert rc == 0
        assert parsed is not None, f"Fallo real de pytest debe bloquear; stdout={stdout!r}"
        assert parsed.get("decision") == "block", (
            f"exit 1 de pytest real debe bloquear; parsed={parsed!r}"
        )


# ── Caso 9: exit 2 -- error de colección, parseo de "No module named" ─────────
#
# Contrato (hechos de Bilbo, no reinvestigados): para cada módulo
# faltante X extraído de "No module named '(X)'" en stdout+stderr,
# seg = X.split('.')[0]:
#   - si NINGUNA coincidencia del patrón aparece (p.ej. sintaxis rota en
#     el propio fichero de test, sin relación con imports) → bloquea.
#   - si seg NO existe en disco (`<cwd>/<seg>/`, `<cwd>/<seg>.py`,
#     `<cwd>/src/<seg>/`) NI está trackeado bajo esos paths en git HEAD →
#     bloquea (dependencia de verdad ausente, típicamente third-party).
#   - si seg SÍ existe, pero el fuente concreto de X está ausente en
#     disco Y NO trackeado en git HEAD (módulo local que nunca se llegó
#     a escribir) → permite, con aviso una vez por módulo/sesión.
#   - si seg SÍ existe, pero el fuente concreto de X está ausente en
#     disco Y SÍ trackeado en git HEAD (existió y se borró) → bloquea.
#   - con varios módulos faltantes en la misma corrida: si al menos uno
#     bloquea, el resultado global bloquea; solo si TODOS caen en
#     "nunca escrito" el resultado permite.
#
# Cada fixture de abajo fue confirmada a mano contra pytest 9.0.2 /
# Python 3.14 antes de escribir la aserción (exit code + presencia real
# de "No module named" en la salida), igual que Bilbo hizo para los
# hechos que trae este prompt -- no se asume ningún mensaje de pytest sin
# haberlo visto salir de un run real.

class TestCollectionErrorNoModuleMatch:
    """Error de colección SIN "No module named" en la salida -- no hay
    módulo que clasificar, el hook no puede saber si es seguro. Debe
    bloquear."""

    def test_syntax_error_in_own_test_file_blocks(self, tmp_path):
        """Sintaxis rota en el propio fichero de test -- pytest sale 2 con
        un SyntaxError, no un ModuleNotFoundError. Confirmado a mano:
        stdout+stderr no contienen "No module named" en absoluto."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_source_file(workdir, "test_broken_syntax.py", "def test_foo(:\n    pass\n")
        _write_config(workdir, {"test_command": _PYTEST_COMMAND})

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-syntax-1"))

        assert rc == 0
        assert parsed is not None, f"Error de colección sin match debe bloquear; stdout={stdout!r}"
        assert parsed.get("decision") == "block", (
            f"Sin coincidencia de 'No module named', debe bloquear (no se "
            f"puede clasificar); parsed={parsed!r}"
        )


class TestCollectionErrorThirdPartyModuleBlocks:
    """Módulo faltante cuyo `seg` (primer segmento) no existe ni en disco
    ni en git HEAD -- dependencia de verdad ausente (típicamente
    third-party). Debe bloquear."""

    def test_missing_thirdparty_single_segment_blocks(self, tmp_path):
        """Import de un paquete inventado de un solo segmento -- pytest
        sale 2 con "No module named 'totally_fake_thirdparty_pkg_xyz'".
        Ese `seg` no existe en disco ni en git en ningún sitio del
        workdir."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_source_file(
            workdir,
            "test_import_thirdparty.py",
            "import totally_fake_thirdparty_pkg_xyz\n\n"
            "def test_foo():\n    pass\n",
        )
        _write_config(workdir, {"test_command": _PYTEST_COMMAND})

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-thirdparty-1"))

        assert rc == 0
        assert parsed is not None, f"Dependencia third-party ausente debe bloquear; stdout={stdout!r}"
        assert parsed.get("decision") == "block", (
            f"seg ausente en disco y en git debe bloquear; parsed={parsed!r}"
        )


class TestCollectionErrorNeverWrittenLocalModuleAllows:
    """`seg` existe (paquete local real en el workdir), pero el submódulo
    concreto importado nunca se llegó a escribir (ausente en disco Y no
    trackeado en git) -- caso benigno de referencia adelantada. Debe
    permitir, con aviso una vez por módulo/sesión."""

    def _build_never_written_fixture(self, workdir: str) -> None:
        _write_source_file(workdir, "moria/__init__.py", "")
        _write_source_file(
            workdir,
            "test_import_never_written.py",
            "import moria.never_written_submodule\n\n"
            "def test_foo():\n    pass\n",
        )
        _write_config(workdir, {"test_command": _PYTEST_COMMAND})

    def test_never_written_submodule_allows_close(self, tmp_path):
        workdir = _makes_tmp_dir(tmp_path)
        self._build_never_written_fixture(workdir)

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-neverwritten-1"))

        assert rc == 0
        assert parsed is None or parsed.get("decision") != "block", (
            f"Submódulo local nunca escrito (no trackeado) no debe "
            f"bloquear el cierre; parsed={parsed!r}, stdout={stdout!r}, "
            f"stderr={stderr!r}"
        )

    def test_never_written_submodule_warns_with_module_name(self, tmp_path):
        """El aviso (cuando exista) debe señalar el módulo concreto que
        falta, no ser genérico -- quien lee el aviso necesita saber qué
        fichero crear."""
        workdir = _makes_tmp_dir(tmp_path)
        self._build_never_written_fixture(workdir)

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-neverwritten-2"))

        assert rc == 0
        assert stderr.strip() != "", (
            "Un módulo local nunca escrito debe avisar (no silencio "
            f"total) aunque no bloquee; stdout={stdout!r}"
        )
        assert "moria" in stderr, (
            f"El aviso debe mencionar el módulo concreto ('moria...'), "
            f"no ser genérico; stderr={stderr!r}"
        )

    def test_never_written_submodule_warning_does_not_repeat_same_session(self, tmp_path):
        """Aviso una vez por módulo/sesión -- misma sesión, mismo módulo
        faltante dos veces seguidas: la segunda no debe repetir el
        aviso."""
        workdir = _makes_tmp_dir(tmp_path)
        self._build_never_written_fixture(workdir)
        session = "sess-neverwritten-repeat"

        _, _, _, stderr1 = _run_hook(workdir, payload=_stop_payload(session))
        rc2, parsed2, _, stderr2 = _run_hook(workdir, payload=_stop_payload(session))

        assert rc2 == 0
        assert parsed2 is None or parsed2.get("decision") != "block"
        assert stderr2.strip() == "", (
            "El aviso de módulo local nunca escrito debe verse UNA vez "
            f"por módulo/sesión; primera={stderr1!r}, segunda={stderr2!r}"
        )


class TestCollectionErrorDeletedTrackedModuleBlocks:
    """`seg` existe, pero el fuente concreto del submódulo importado está
    ausente en disco Y SÍ trackeado en git HEAD (existió, se commiteó, se
    borró del árbol de trabajo). Debe bloquear -- a diferencia del caso
    "nunca escrito", aquí SÍ hubo código real que dejó de estar."""

    def test_deleted_but_git_tracked_submodule_blocks(self, tmp_path):
        workdir = _makes_tmp_dir(tmp_path)
        _init_git_repo_with_commit(workdir)
        _write_source_file(workdir, "moria/__init__.py", "")
        _write_source_file(workdir, "moria/foo.py", "X = 1\n")
        _write_source_file(
            workdir,
            "test_import_deleted.py",
            "import moria.foo\n\ndef test_foo():\n    pass\n",
        )
        _git_add_all_commit(workdir, "add moria.foo -- fixture del test")
        _write_config(workdir, {"test_command": _PYTEST_COMMAND})

        # Ahora se borra del árbol de trabajo, pero sigue en HEAD.
        os.remove(os.path.join(workdir, "moria", "foo.py"))

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-deleted-1"))

        assert rc == 0
        assert parsed is not None, (
            f"Submódulo borrado pero trackeado en git HEAD debe bloquear; "
            f"stdout={stdout!r}, stderr={stderr!r}"
        )
        assert parsed.get("decision") == "block", (
            f"seg existe, submódulo ausente en disco pero trackeado en "
            f"HEAD (borrado) debe bloquear; parsed={parsed!r}"
        )


class TestCollectionErrorMixedMissingModules:
    """Varios módulos faltantes en la misma corrida (pytest SÍ acumula
    "ERROR collecting ..." de varios ficheros independientes en la misma
    corrida -- confirmado a mano con dos ficheros de test rotos por
    razones distintas): si al menos uno bloquea, el resultado global
    bloquea; solo si TODOS caen en "nunca escrito" permite."""

    def test_mixed_thirdparty_and_never_written_blocks(self, tmp_path):
        """Un fichero importa un third-party inexistente (bloquea) y otro
        importa un submódulo local nunca escrito (permitiría solo). El
        resultado global debe bloquear -- basta con que uno bloquee."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_source_file(
            workdir,
            "test_a_thirdparty.py",
            "import totally_fake_thirdparty_pkg_mixed_aaa\n\n"
            "def test_a():\n    pass\n",
        )
        _write_source_file(workdir, "moria/__init__.py", "")
        _write_source_file(
            workdir,
            "test_b_never_written.py",
            "import moria.never_written_mixed_bbb\n\n"
            "def test_b():\n    pass\n",
        )
        _write_config(workdir, {"test_command": _PYTEST_COMMAND})

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-mixed-block-1"))

        assert rc == 0
        assert parsed is not None, (
            f"Mezcla con al menos un módulo que bloquea debe bloquear "
            f"globalmente; stdout={stdout!r}"
        )
        assert parsed.get("decision") == "block", (
            f"Un third-party ausente entre varios módulos faltantes basta "
            f"para bloquear el resultado global; parsed={parsed!r}"
        )

    def test_mixed_all_never_written_allows(self, tmp_path):
        """Dos ficheros, cada uno con un submódulo local distinto nunca
        escrito (ninguno trackeado, ninguno third-party). TODOS caen en
        "nunca escrito" -- el resultado global debe permitir."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_source_file(workdir, "moria/__init__.py", "")
        _write_source_file(
            workdir,
            "test_a_never_written.py",
            "import moria.never_written_aaa\n\ndef test_a():\n    pass\n",
        )
        _write_source_file(
            workdir,
            "test_b_never_written.py",
            "import moria.never_written_bbb\n\ndef test_b():\n    pass\n",
        )
        _write_config(workdir, {"test_command": _PYTEST_COMMAND})

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-mixed-allow-1"))

        assert rc == 0
        assert parsed is None or parsed.get("decision") != "block", (
            f"Todos los módulos faltantes son 'nunca escritos' -- el "
            f"resultado global no debe bloquear; parsed={parsed!r}, "
            f"stdout={stdout!r}, stderr={stderr!r}"
        )


# ── Caso 10: anti-goteo -- firma del bloqueo, dedup por session_id ────────────
#
# Contrato: al BLOQUEAR, firma = sha256 del conjunto ordenado de líneas
# FAILED…/ERROR…/E … + exit_code, keyeada por session_id. Firma repetida
# en la misma sesión → la 'reason' es un recordatorio de UNA línea (NO
# contiene el volcado de salida). Firma nueva (sesión nueva, o contenido
# de fallo distinto) → 'reason' completa (con el snippet de salida, como
# hoy). Estos tests no verifican el algoritmo de firma en sí (eso es
# implementación de Ultron) -- verifican el CONTRATO observable: mismo
# fallo + misma sesión = recordatorio corto sin volcado; fallo distinto o
# sesión distinta = reason completa con el detalle de siempre.
#
# Los ficheros de test usan un marcador único en el mensaje de assert
# para poder comprobar, sin ambigüedad, si el volcado de pytest está o no
# presente en el 'reason'.

_MARKER_A = "ZZZMARKERDEADBEEF1234"
_MARKER_B = "ZZZMARKERCAFEBABE5678"


def _write_failing_test_with_marker(workdir: str, marker: str) -> None:
    _write_source_file(
        workdir,
        "test_marked_fail.py",
        "def test_should_pass_but_fails():\n"
        f"    assert False, {marker!r}\n",
    )
    _write_config(workdir, {"test_command": _PYTEST_COMMAND})


class TestBlockSignatureDedupBySession:
    """Anti-goteo: firma repetida en la misma sesión → reason corta, sin
    volcado. Firma nueva (sesión distinta, o contenido distinto) →
    reason completa, como hoy."""

    def test_repeated_signature_same_session_gets_oneliner_without_dump(self, tmp_path):
        """Misma sesión, mismo fallo dos veces seguidas -- la primera
        reason trae el volcado (contiene el marcador), la segunda es un
        recordatorio de una línea que NO lo repite."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_failing_test_with_marker(workdir, _MARKER_A)
        session = "sess-dedup-repeat-1"

        rc1, parsed1, _, _ = _run_hook(workdir, payload=_stop_payload(session))
        rc2, parsed2, _, _ = _run_hook(workdir, payload=_stop_payload(session))

        assert rc1 == 0 and rc2 == 0
        assert parsed1 is not None and parsed1.get("decision") == "block"
        assert parsed2 is not None and parsed2.get("decision") == "block"

        reason1 = parsed1.get("reason", "")
        reason2 = parsed2.get("reason", "")

        assert _MARKER_A in reason1, (
            f"Primera vez que se ve esta firma en la sesión -- la reason "
            f"debe traer el volcado completo (con el marcador); "
            f"reason={reason1!r}"
        )
        assert _MARKER_A not in reason2, (
            "Firma repetida en la misma sesión -- la segunda reason NO "
            f"debe repetir el volcado de salida; reason={reason2!r}"
        )
        assert "\n" not in reason2.strip(), (
            "Firma repetida en la misma sesión -- la reason debe ser un "
            f"recordatorio de UNA sola línea; reason={reason2!r}"
        )
        assert len(reason2) < len(reason1), (
            "El recordatorio de firma repetida debe ser sensiblemente más "
            f"corto que la reason completa; reason1={reason1!r} "
            f"({len(reason1)} chars), reason2={reason2!r} ({len(reason2)} chars)"
        )

    def test_new_failure_content_same_session_gets_full_reason_again(self, tmp_path):
        """Misma sesión, pero el SEGUNDO fallo tiene contenido distinto
        (firma nueva) -- debe traer la reason completa de nuevo, no un
        recordatorio corto."""
        workdir = _makes_tmp_dir(tmp_path)
        session = "sess-dedup-newcontent-1"

        _write_failing_test_with_marker(workdir, _MARKER_A)
        rc1, parsed1, _, _ = _run_hook(workdir, payload=_stop_payload(session))

        _write_failing_test_with_marker(workdir, _MARKER_B)
        rc2, parsed2, _, _ = _run_hook(workdir, payload=_stop_payload(session))

        assert rc1 == 0 and rc2 == 0
        assert parsed1 is not None and parsed1.get("decision") == "block"
        assert parsed2 is not None and parsed2.get("decision") == "block"

        reason2 = parsed2.get("reason", "")
        assert _MARKER_B in reason2, (
            "Contenido de fallo distinto (firma nueva) en la misma sesión "
            f"debe traer la reason completa, no un recordatorio corto; "
            f"reason={reason2!r}"
        )

    def test_same_signature_different_session_gets_full_reason_each(self, tmp_path):
        """Mismo fallo exacto, pero en sesiones DISTINTAS -- el dedup es
        per-session_id, así que cada sesión debe ver la reason completa
        (no se contamina de una sesión a otra)."""
        workdir_a = _makes_tmp_dir(tmp_path, "workdir_a")
        workdir_b = _makes_tmp_dir(tmp_path, "workdir_b")
        _write_failing_test_with_marker(workdir_a, _MARKER_A)
        _write_failing_test_with_marker(workdir_b, _MARKER_A)

        rc_a, parsed_a, _, _ = _run_hook(workdir_a, payload=_stop_payload("sess-diff-a"))
        rc_b, parsed_b, _, _ = _run_hook(workdir_b, payload=_stop_payload("sess-diff-b"))

        assert rc_a == 0 and rc_b == 0
        assert parsed_a is not None and parsed_a.get("decision") == "block"
        assert parsed_b is not None and parsed_b.get("decision") == "block"

        reason_a = parsed_a.get("reason", "")
        reason_b = parsed_b.get("reason", "")
        assert _MARKER_A in reason_a, f"sesión A debe traer reason completa; reason={reason_a!r}"
        assert _MARKER_A in reason_b, (
            f"sesión B (session_id distinto) debe traer su PROPIA reason "
            f"completa, no un recordatorio heredado de la sesión A; "
            f"reason={reason_b!r}"
        )


# ── Caso 11 (hardening/Verify 2026-08-20) -- proceso matado por señal ─────────
#
# Argus finding: un test_command cuyo proceso muere por señal (returncode
# negativo, p.ej. SIGHUP) NO es un error de infraestructura del hook --
# es un rojo real (algo mató el proceso de tests) y debe bloquear, no
# fail-open. `_run_test_command()` distingue esto por construcción:
# exit_code=None SOLO quiere decir "no se pudo ni arrancar" (binario
# inexistente, timeout, etc); un returncode negativo real de
# subprocess.run() (matado por señal) es un int válido que cae en la
# rama "cualquier otro exit ≠0 -> bloquea" de _handle_nonzero_exit().
#
# SIGHUP no existe en Windows (module `signal` no expone SIGHUP fuera de
# POSIX) -- skip explícito, no una condición silenciosa.

class TestSignalKilledProcessBlocks:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="signal.SIGHUP no existe en Windows -- no hay repro real posible ahí",
    )
    def test_process_killed_by_sighup_blocks(self, tmp_path):
        """test_command se suicida con SIGHUP -- returncode negativo real
        (no None, no un sentinel de infra-fallo). Debe bloquear."""
        workdir = _makes_tmp_dir(tmp_path)
        kill_cmd = (
            f"{sys.executable} -c "
            "\"import os, signal; os.kill(os.getpid(), signal.SIGHUP)\""
        )
        _write_config(workdir, {"test_command": kill_cmd})

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-sighup-1"))

        assert rc == 0, f"El hook siempre sale 0 aunque bloquee; rc={rc!r}"
        assert parsed is not None, (
            "Un test_command matado por SIGHUP (returncode negativo real) "
            f"no es un fallo de infraestructura -- debe bloquear, no "
            f"fail-open en silencio; stdout={stdout!r}, stderr={stderr!r}"
        )
        assert parsed.get("decision") == "block", (
            f"returncode negativo real (señal) debe clasificarse como un "
            f"rojo genuino, no colapsar con el sentinel de fail-open; "
            f"parsed={parsed!r}"
        )


# ── Caso 12 (hardening/Verify 2026-08-20) -- anti-goteo también en exit 2 ─────
#
# Los tests de firma de TestBlockSignatureDedupBySession solo cubrían
# exit 1 (fallo real de un test). El anti-goteo (sha256 de líneas
# FAILED/ERROR/E + exit_code, keyeado por session_id) se computa igual
# para CUALQUIER bloqueo, incluido un exit 2 (error de colección) que no
# se clasificó como "todo nunca-escrito". Estos tests fijan el mismo
# contrato para ese camino.

class TestCollectionErrorSignatureDedup:
    # `_build_block_reason()` trunca el volcado a 500 chars -- el nombre
    # del módulo third-party vive al FINAL de un traceback real (detrás
    # de una ruta absoluta de tmp_path larga) y queda fuera de esa
    # ventana (confirmado a mano: un primer intento buscando el nombre
    # del módulo en `reason` falló con `AssertionError` porque el propio
    # `reason` venía truncado antes de llegar a esa línea). El nombre del
    # fichero de test SÍ cae dentro de la ventana -- aparece pegado a la
    # cabecera "ERROR collecting <fichero>", que es de las primeras
    # líneas del volcado -- así que se usa como marcador de firma en su
    # lugar, un fichero por escenario para que la firma cambie de verdad
    # entre "mismo error" y "error distinto". "Output:" es el marcador de
    # "es la reason completa" -- solo aparece cuando `_build_block_reason`
    # incluyó el volcado; el recordatorio corto de
    # `_build_block_reason_deduped` es la frase fija que nunca lo trae.
    def _write_thirdparty_import(self, workdir: str, fake_module: str, test_filename: str) -> None:
        _write_source_file(
            workdir,
            test_filename,
            f"import {fake_module}\n\ndef test_foo():\n    pass\n",
        )
        _write_config(workdir, {"test_command": _PYTEST_COMMAND})

    def test_repeated_collection_error_same_session_gets_oneliner(self, tmp_path):
        """Mismo error de colección (mismo third-party ausente) dos veces
        seguidas, misma sesión -- la primera reason trae el volcado real
        de pytest, la segunda es un recordatorio corto que no lo repite."""
        workdir = _makes_tmp_dir(tmp_path)
        fake_module = "totally_fake_thirdparty_pkg_dedup_exit2_aaa"
        test_filename = "test_collection_dedup_aaa.py"
        self._write_thirdparty_import(workdir, fake_module, test_filename)
        session = "sess-dedup-exit2-repeat"

        rc1, parsed1, _, _ = _run_hook(workdir, payload=_stop_payload(session))
        rc2, parsed2, _, _ = _run_hook(workdir, payload=_stop_payload(session))

        assert rc1 == 0 and rc2 == 0
        assert parsed1 is not None and parsed1.get("decision") == "block"
        assert parsed2 is not None and parsed2.get("decision") == "block"

        reason1 = parsed1.get("reason", "")
        reason2 = parsed2.get("reason", "")
        assert test_filename in reason1 and "Output:" in reason1, (
            f"Primera vez que se ve esta firma -- reason completa con el "
            f"volcado real de pytest; reason={reason1!r}"
        )
        assert "Output:" not in reason2, (
            "Firma repetida en la misma sesión (mismo error de colección) "
            f"-- la segunda reason no debe traer el volcado; "
            f"reason={reason2!r}"
        )
        assert "\n" not in reason2.strip(), (
            f"Recordatorio de firma repetida debe ser una sola línea; "
            f"reason={reason2!r}"
        )

    def test_new_collection_error_content_same_session_gets_full_reason_again(self, tmp_path):
        """Misma sesión, pero el segundo error de colección es sobre un
        módulo third-party DISTINTO (firma nueva) -- debe traer la reason
        completa otra vez."""
        workdir = _makes_tmp_dir(tmp_path)
        session = "sess-dedup-exit2-newcontent"

        module_a = "totally_fake_thirdparty_pkg_dedup_exit2_bbb"
        self._write_thirdparty_import(workdir, module_a, "test_collection_dedup_bbb.py")
        rc1, parsed1, _, _ = _run_hook(workdir, payload=_stop_payload(session))

        module_b = "totally_fake_thirdparty_pkg_dedup_exit2_ccc"
        test_filename_b = "test_collection_dedup_ccc.py"
        self._write_thirdparty_import(workdir, module_b, test_filename_b)
        # El fichero del escenario A queda en el workdir -- borrarlo para
        # que pytest solo vea el escenario B en la segunda corrida (si no,
        # ambos ficheros colisionan en la colección y contaminan la firma).
        os.remove(os.path.join(workdir, "test_collection_dedup_bbb.py"))
        rc2, parsed2, _, _ = _run_hook(workdir, payload=_stop_payload(session))

        assert rc1 == 0 and rc2 == 0
        assert parsed1 is not None and parsed1.get("decision") == "block"
        assert parsed2 is not None and parsed2.get("decision") == "block"

        reason2 = parsed2.get("reason", "")
        assert test_filename_b in reason2 and "Output:" in reason2, (
            "Error de colección con contenido distinto (firma nueva) en "
            f"la misma sesión debe traer la reason completa de nuevo (con "
            f"volcado), no un recordatorio corto; reason={reason2!r}"
        )


# ── Caso 13 (hardening/Verify 2026-08-20) -- round-trip real del estado ───────
#
# §34 (unmassk-standards): la firma esperada en la segunda invocación
# nunca se escribe a mano -- se lee del propio fichero real que la
# primera invocación acaba de escribir. Esto es lo que
# TestBlockSignatureDedupBySession / TestCollectionErrorSignatureDedup
# NO comprueban directamente: verifican el comportamiento observable
# (reason corta vs completa) pero nunca abren
# `.claude/.unmassk/stop-dod-gate-state.json` en sí. Este test sí lo
# abre, en las dos puntas del round-trip.

class TestStateFileRoundTrip:
    # Mismo nombre de fichero que STATE_FILENAME en stop-dod-gate.py -- no
    # se importa directamente (el hook es un fichero con guion, se invoca
    # como subprocess, no como módulo; mismo motivo que _CONFIG_SUBPATH
    # arriba), pero UNMASSK_RUNTIME_DIR sí es un módulo normal importable.
    _STATE_FILENAME = "stop-dod-gate-state.json"

    def _state_path(self, workdir: str) -> str:
        return os.path.join(workdir, UNMASSK_RUNTIME_DIR, self._STATE_FILENAME)

    def test_block_signature_round_trips_through_real_state_file(self, tmp_path):
        """La firma que la primera invocación escribe en el fichero de
        estado real es la MISMA que la segunda invocación relee (round
        trip contra el fichero real, sin ningún literal de firma escrito
        a mano por el test)."""
        workdir = _makes_tmp_dir(tmp_path)
        _write_failing_test_with_marker(workdir, _MARKER_A)
        session = "sess-roundtrip-state-1"

        rc1, parsed1, _, _ = _run_hook(workdir, payload=_stop_payload(session))
        assert rc1 == 0
        assert parsed1 is not None and parsed1.get("decision") == "block"

        state_path = self._state_path(workdir)
        assert os.path.isfile(state_path), (
            f"El hook debe persistir el estado real en {state_path!r} "
            f"tras un bloqueo"
        )
        with open(state_path, "r", encoding="utf-8") as f:
            state_after_first = json.load(f)

        signature_after_first = state_after_first.get("last_block_signature")
        assert isinstance(signature_after_first, str) and signature_after_first, (
            f"La firma persistida debe ser un string real no vacío -- "
            f"nunca la escribimos a mano en el test, la leemos del propio "
            f"fichero que el hook acaba de escribir; state={state_after_first!r}"
        )
        assert state_after_first.get("session_id") == session

        # Segunda invocación, MISMO fallo -- debe releer esa firma real
        # (no recomputar a ciegas sin comparar) y el fichero, tras la
        # segunda pasada, debe seguir teniendo la MISMA firma que
        # escribió la primera.
        rc2, parsed2, _, _ = _run_hook(workdir, payload=_stop_payload(session))
        assert rc2 == 0
        assert parsed2 is not None and parsed2.get("decision") == "block"

        with open(state_path, "r", encoding="utf-8") as f:
            state_after_second = json.load(f)
        signature_after_second = state_after_second.get("last_block_signature")

        assert signature_after_second == signature_after_first, (
            "La firma releída tras la segunda invocación debe coincidir "
            f"byte a byte con la que la primera escribió en el fichero "
            f"real (ida y vuelta genuina, sin literal de firma escrito a "
            f"mano); primera={signature_after_first!r}, "
            f"segunda={signature_after_second!r}"
        )

        # Y el comportamiento observable derivado de ese round-trip:
        # reason corta en la segunda, sin el marcador del volcado.
        reason2 = parsed2.get("reason", "")
        assert _MARKER_A not in reason2, (
            f"Si el round-trip de la firma funcionó de verdad, la segunda "
            f"reason debe ser el recordatorio corto, no repetir el "
            f"volcado; reason={reason2!r}"
        )


# ── Caso 14 (hardening/Verify 2026-08-20) -- D-042, identidad declarada ───────
#
# Ultron implementó D-042 (lib/dod_gate_classify.py: "primera parte" ahora
# mira primero la identidad declarada del proyecto -- pyproject.toml
# [project].name / [tool.poetry].name / [tool.setuptools] packages,
# setup.cfg [metadata] name -- antes de caer al chequeo de disco/git) sin
# un solo test end-to-end. La cobertura unitaria directa contra
# lib/dod_gate_classify.py vive en test_dod_gate_classify.py
# (TestDeclaredFirstPartyIdentity / TestDeclaredIdentityFailsSafe /
# TestNoDeclaredIdentityStillBlocksNewTopLevel) -- estas dos de aquí son
# el regreso end-to-end real: hook + pytest real + git real, exactamente
# la forma que rompió Moriarty.
#
# OJO (encontrado escribiendo esta cobertura, no antes): el import tiene
# que ser a NIVEL DE MÓDULO (arriba del fichero), no dentro del cuerpo de
# una función de test -- un `import moria` dentro de `def test_foo():`
# hace que pytest RECOJA el test con éxito (el ImportError ocurre en
# tiempo de EJECUCIÓN del test, no de colección) y el test simplemente
# falla con exit 1, sin pasar nunca por classify_collection_error(). Ese
# es el falso negativo exacto que Ultron se comió -- confirmado a mano
# antes de escribir estas aserciones (import a nivel de módulo -> exit 2
# real con "No module named 'moria'" en la salida).

class TestDeclaredIdentityD042EndToEnd:
    def _write_pyproject_declaring_moria(self, workdir: str) -> None:
        _write_source_file(workdir, "pyproject.toml", '[project]\nname = "moria"\nversion = "0.1.0"\n')

    def test_declared_identity_allows_never_written_toplevel_module(self, tmp_path):
        """El caso que rompió Moriarty: proyecto con pyproject.toml
        [project].name = "moria", `import moria` a NIVEL DE MÓDULO en un
        test, 'moria' nunca escrito ni trackeado en ningún sitio. Antes
        de D-042 esto bloqueaba SIEMPRE (seg_exists() no tenía forma de
        saber que 'moria' era el propio proyecto). Debe permitir."""
        workdir = _makes_tmp_dir(tmp_path)
        self._write_pyproject_declaring_moria(workdir)
        _write_source_file(
            workdir,
            "test_moria_toplevel.py",
            "import moria\n\ndef test_foo():\n    pass\n",
        )
        _write_config(workdir, {"test_command": _PYTEST_COMMAND})

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-d042-allow-1"))

        assert rc == 0
        assert parsed is None or parsed.get("decision") != "block", (
            "Identidad declarada (pyproject.toml [project].name = 'moria') "
            f"+ 'moria' nunca escrito -- debe permitir el cierre, no "
            f"bloquear como third-party; parsed={parsed!r}, "
            f"stdout={stdout!r}, stderr={stderr!r}"
        )

    def test_undeclared_thirdparty_still_blocks_in_same_project(self, tmp_path):
        """Invariante que no se puede perder: en ESE MISMO proyecto (con
        identidad declarada para 'moria'), un import de un third-party
        que NO está declarado y NO existe en ningún sitio sigue
        bloqueando -- la identidad declarada no es un permiso general."""
        workdir = _makes_tmp_dir(tmp_path)
        self._write_pyproject_declaring_moria(workdir)
        _write_source_file(
            workdir,
            "test_undeclared_thirdparty.py",
            "import totally_fake_thirdparty_xyz\n\ndef test_foo():\n    pass\n",
        )
        _write_config(workdir, {"test_command": _PYTEST_COMMAND})

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-d042-block-1"))

        assert rc == 0
        assert parsed is not None, (
            f"Third-party no declarado y ausente debe bloquear incluso en "
            f"un proyecto con identidad propia declarada; stdout={stdout!r}"
        )
        assert parsed.get("decision") == "block", (
            f"La identidad declarada para 'moria' no debe filtrarse a "
            f"'totally_fake_thirdparty_xyz' -- ese import sigue sin "
            f"declarar ni existir; parsed={parsed!r}"
        )


# ── Caso 15 (hardening/Verify 2026-08-20) -- Yoda finding: fallo callado ──────
# ante bytes invalidos en la salida de un fallo REAL ────────────────────────
#
# Yoda: un test que fallaba DE VERDAD (exit 1) pero cuya salida traia un
# byte invalido en UTF-8 lanzaba UnicodeDecodeError dentro de
# subprocess.run() -- ese ValueError caia en el `except (..., ValueError)`
# de fail-open y PERMITIA cerrar en silencio sobre un rojo real. Ultron
# arreglo esto con `errors="replace"` en subprocess.run() (la decodificacion
# ya no puede lanzar -- el byte invalido se sustituye por el caracter de
# reemplazo U+FFFD) mas un `except UnicodeDecodeError:` propio, anterior al
# `except (..., ValueError)` mas ancho, que devuelve un exit code centinela
# nuevo (_DECODE_ERROR_EXIT_CODE = -9999) por si la excepcion llegara a
# lanzarse de todos modos -- defensa en profundidad.
#
# `errors="replace"` hace que, en la practica, decodificar YA NO PUEDA
# lanzar -- confirmado a mano: un byte 0xFF crudo en stdout, capturado con
# `text=True, encoding="utf-8", errors="replace"`, se decodifica sin
# excepcion a "...ZZZBADBYTE � end\n" (rc=1 real, nunca -9999). El
# camino del centinela -9999 es defensivo por diseno y no tiene un repro
# real alcanzable a traves de un subprocess.run() normal -- lo que SI se
# puede fijar de extremo a extremo es el contrato que -9999 explota
# (cualquier exit no-cero no nombrado explicitamente cae en BLOQUEAR), con
# un exit code real y arbitrario que tampoco es 0/1/2/5/negativo-por-senal.

def _write_invalid_byte_failing_script(workdir: str, filename: str = "emit_invalid_byte_fail.py") -> str:
    """Escribe un script que imprime una linea FAILED... con un byte
    invalido en UTF-8 (0xFF crudo, via stdout.buffer) y sale con exit 1 --
    el repro exacto de Yoda. Determinista: mismo byte, mismo texto, mismo
    exit code en cada ejecucion (confirmado a mano antes de escribir estos
    tests)."""
    _write_source_file(
        workdir,
        filename,
        "import sys\n"
        "sys.stdout.write(\"FAILED test_x.py::test_should_fail - AssertionError: ZZZBADBYTE \")\n"
        "sys.stdout.flush()\n"
        "sys.stdout.buffer.write(bytes([0xFF]))\n"
        "sys.stdout.buffer.write(b\" end\\n\")\n"
        "sys.exit(1)\n",
    )
    return f"{sys.executable} {filename}"


class TestInvalidUtf8ByteInRealFailureBlocks:
    """El repro exacto de Yoda: exit 1 real, salida con un byte invalido.
    Debe bloquear, y la reason debe traer la salida con el caracter de
    reemplazo, no quedarse vacia ni caer en fail-open."""

    def test_invalid_byte_in_failing_output_blocks_with_replacement_char(self, tmp_path):
        workdir = _makes_tmp_dir(tmp_path)
        cmd = _write_invalid_byte_failing_script(workdir)
        _write_config(workdir, {"test_command": cmd})

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-invalidbyte-1"))

        assert rc == 0, f"El hook siempre sale 0 aunque bloquee; rc={rc!r}"
        assert parsed is not None, (
            "Un fallo real (exit 1) con un byte invalido en la salida NO "
            f"es un fallo de infraestructura -- debe bloquear, nunca "
            f"fail-open en silencio; stdout={stdout!r}, stderr={stderr!r}"
        )
        assert parsed.get("decision") == "block", (
            f"exit 1 real con byte invalido en la salida debe bloquear, "
            f"igual que cualquier otro fallo real; parsed={parsed!r}"
        )
        reason = parsed.get("reason", "")
        assert reason != "", (
            "La reason no puede quedar vacia -- el fallo callado exacto "
            "que reporto Yoda era precisamente esto: bloqueo con "
            "contenido vacio/perdido, o peor, ni siquiera bloqueo"
        )
        assert "ZZZBADBYTE" in reason, (
            f"La reason debe traer la salida real del fallo (con el texto "
            f"anterior al byte invalido intacto); reason={reason!r}"
        )
        assert "\ufffd" in reason, (
            f"El byte invalido debe aparecer sustituido por el caracter de "
            f"reemplazo U+FFFD ('\ufffd'), no provocar una excepcion ni "
            f"desaparecer en silencio; reason={reason!r}"
        )


class TestInvalidUtf8ByteDedupStability:
    """La dedup (firma sha256 de lineas FAILED/ERROR/E + exit_code) sigue
    siendo estable cuando el contenido trae un byte invalido sustituido --
    el caracter de reemplazo es parte del texto que se hashea, y debe
    producir el mismo comportamiento de dedup que cualquier otro fallo."""

    def test_repeated_invalid_byte_failure_same_session_gets_oneliner(self, tmp_path):
        workdir = _makes_tmp_dir(tmp_path)
        cmd = _write_invalid_byte_failing_script(workdir)
        _write_config(workdir, {"test_command": cmd})
        session = "sess-invalidbyte-dedup-repeat"

        rc1, parsed1, _, _ = _run_hook(workdir, payload=_stop_payload(session))
        rc2, parsed2, _, _ = _run_hook(workdir, payload=_stop_payload(session))

        assert rc1 == 0 and rc2 == 0
        assert parsed1 is not None and parsed1.get("decision") == "block"
        assert parsed2 is not None and parsed2.get("decision") == "block"

        reason1 = parsed1.get("reason", "")
        reason2 = parsed2.get("reason", "")
        assert "Output:" in reason1 and "ZZZBADBYTE" in reason1, (
            f"Primera vez que se ve esta firma -- reason completa con el "
            f"volcado real (incluido el caracter de reemplazo); "
            f"reason={reason1!r}"
        )
        assert "Output:" not in reason2, (
            "Firma repetida en la misma sesion (mismo fallo con byte "
            f"invalido) -- la segunda reason no debe traer el volcado; "
            f"reason={reason2!r}"
        )
        assert "\n" not in reason2.strip(), (
            f"Recordatorio de firma repetida debe ser una sola linea; "
            f"reason={reason2!r}"
        )

    def test_invalid_byte_failure_different_session_gets_full_reason_with_deterministic_signature(self, tmp_path):
        """Sesion distinta, mismo fallo con byte invalido -- reason
        completa en ambas (dedup es per-session), y la firma persistida en
        el fichero de estado real de cada workdir debe ser IDENTICA byte a
        byte (misma firma determinista para el mismo contenido, sin
        literal de firma escrito a mano -- se lee del propio fichero que
        cada invocacion acaba de escribir, mismo patron que
        TestStateFileRoundTrip)."""
        workdir_a = _makes_tmp_dir(tmp_path, "workdir_a")
        workdir_b = _makes_tmp_dir(tmp_path, "workdir_b")
        cmd_a = _write_invalid_byte_failing_script(workdir_a)
        cmd_b = _write_invalid_byte_failing_script(workdir_b)
        _write_config(workdir_a, {"test_command": cmd_a})
        _write_config(workdir_b, {"test_command": cmd_b})

        rc_a, parsed_a, _, _ = _run_hook(workdir_a, payload=_stop_payload("sess-invalidbyte-diff-a"))
        rc_b, parsed_b, _, _ = _run_hook(workdir_b, payload=_stop_payload("sess-invalidbyte-diff-b"))

        assert rc_a == 0 and rc_b == 0
        assert parsed_a is not None and parsed_a.get("decision") == "block"
        assert parsed_b is not None and parsed_b.get("decision") == "block"

        reason_a = parsed_a.get("reason", "")
        reason_b = parsed_b.get("reason", "")
        assert "ZZZBADBYTE" in reason_a and "Output:" in reason_a, (
            f"sesion A debe traer reason completa; reason={reason_a!r}"
        )
        assert "ZZZBADBYTE" in reason_b and "Output:" in reason_b, (
            f"sesion B (session_id distinto) debe traer su PROPIA reason "
            f"completa, no un recordatorio heredado; reason={reason_b!r}"
        )

        state_path_a = os.path.join(workdir_a, UNMASSK_RUNTIME_DIR, "stop-dod-gate-state.json")
        state_path_b = os.path.join(workdir_b, UNMASSK_RUNTIME_DIR, "stop-dod-gate-state.json")
        with open(state_path_a, "r", encoding="utf-8") as f:
            signature_a = json.load(f).get("last_block_signature")
        with open(state_path_b, "r", encoding="utf-8") as f:
            signature_b = json.load(f).get("last_block_signature")

        assert isinstance(signature_a, str) and signature_a, (
            f"firma real persistida en el workdir A, nunca escrita a "
            f"mano; got={signature_a!r}"
        )
        assert signature_a == signature_b, (
            "La firma debe ser determinista: mismo contenido de fallo "
            f"(mismo byte invalido, mismo texto, mismo exit code) en dos "
            f"sesiones distintas debe producir la MISMA firma persistida; "
            f"a={signature_a!r}, b={signature_b!r}"
        )


class TestUnknownNonzeroExitCodeAlwaysBlocks:
    """El centinela _DECODE_ERROR_EXIT_CODE (-9999) no tiene un repro real
    alcanzable via subprocess.run() (errors="replace" ya impide que la
    decodificacion lance) -- pero el contrato que protege SI es alcanzable
    de extremo a extremo: _handle_nonzero_exit() no nombra explicitamente
    ningun exit code fuera de {5, 1, 2} y cae siempre a BLOQUEAR para
    cualquier otro, sea cual sea su valor. Un exit code real, arbitrario,
    que no es 0/1/2/5 ni un negativo-por-senal fija ese contrato general
    -- el mismo que -9999 explota si el camino defensivo se llegara a
    activar alguna vez."""

    def test_arbitrary_unnamed_nonzero_exit_code_blocks(self, tmp_path):
        workdir = _makes_tmp_dir(tmp_path)
        _write_config(workdir, {"test_command": f"{sys.executable} -c \"import sys; sys.exit(77)\""})

        rc, parsed, stdout, stderr = _run_hook(workdir, payload=_stop_payload("sess-unknown-exit-1"))

        assert rc == 0
        assert parsed is not None, (
            f"Un exit code no nombrado explicitamente (77) debe bloquear "
            f"por el fallback generico, nunca fail-open; stdout={stdout!r}"
        )
        assert parsed.get("decision") == "block", (
            f"El fallback \"cualquier otro exit no-cero -> bloquea\" es "
            f"lo unico que protege contra un centinela futuro que llegue "
            f"a dispararse; parsed={parsed!r}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="signal.SIGHUP no existe en Windows -- no hay repro real posible ahí",
    )
    def test_arbitrary_exit_code_stays_distinct_from_real_sighup(self, tmp_path):
        """Verificacion cruzada explicita: un exit code positivo arbitrario
        (77) y el returncode negativo real de SIGHUP (-1) son casos
        DISTINTOS por construccion (uno cae directo al fallback generico,
        el otro pasa primero por la distincion None-vs-int-negativo de
        _run_test_command) pero ambos deben terminar bloqueando -- ninguno
        de los dos puede colapsar en fail-open."""
        workdir_arbitrary = _makes_tmp_dir(tmp_path, "workdir_arbitrary")
        workdir_sighup = _makes_tmp_dir(tmp_path, "workdir_sighup")
        _write_config(workdir_arbitrary, {"test_command": f"{sys.executable} -c \"import sys; sys.exit(77)\""})
        _write_config(
            workdir_sighup,
            {"test_command": f"{sys.executable} -c \"import os, signal; os.kill(os.getpid(), signal.SIGHUP)\""},
        )

        rc_arb, parsed_arb, _, _ = _run_hook(workdir_arbitrary, payload=_stop_payload("sess-cross-arbitrary"))
        rc_sig, parsed_sig, _, _ = _run_hook(workdir_sighup, payload=_stop_payload("sess-cross-sighup"))

        assert rc_arb == 0 and rc_sig == 0
        assert parsed_arb is not None and parsed_arb.get("decision") == "block", (
            f"exit code arbitrario (77) debe bloquear; parsed={parsed_arb!r}"
        )
        assert parsed_sig is not None and parsed_sig.get("decision") == "block", (
            f"SIGHUP (returncode negativo real) debe bloquear; "
            f"parsed={parsed_sig!r}"
        )


# ── Import / syntax sanity ──────────────────────────────────────────────────────

class TestImportSanity:
    def test_hook_compiles_without_error(self, tmp_path):
        """El módulo compila sin errores de sintaxis ni de importación."""
        rc, stdout, stderr = run_cmd(
            [sys.executable, "-m", "py_compile", HOOK_PATH],
            cwd=str(tmp_path),
        )
        assert rc == 0, f"Error de compilación en el hook: stderr={stderr!r}"

    def test_hook_exits_zero_in_non_git_dir(self, tmp_path):
        """El hook sale 0 incluso fuera de un repo git y sin config."""
        non_git = str(tmp_path / "not-a-repo")
        os.makedirs(non_git)

        rc, parsed, stdout, stderr = _run_hook(non_git)

        assert rc == 0, f"Fuera de repo git debe exit 0; stderr={stderr!r}"
        if parsed is not None:
            assert parsed.get("decision") != "block"
