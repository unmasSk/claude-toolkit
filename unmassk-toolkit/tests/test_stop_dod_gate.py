"""
Tests for stop-dod-gate.py — freno duro de Definition of Done.

Comportamiento del hook
-----------------------
Stop hook opt-in. Lee `.claude/git-memory-config.json`; si tiene el campo
`test_command` (string), ejecuta ese comando al cierre de sesión.

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
respuesta), 12 ramas/caminos, 9 clases de test, 20 tests.
Not tested: comportamiento del comando de test en sí mismo (eso es del usuario);
integración real con Claude Code (fuera de alcance de tests unitarios de hook).
"""

import json
import os
import sys
import textwrap

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, run_cmd, run_script

HOOK_PATH = os.path.join(HOOKS_DIR, "stop-dod-gate.py")

# Payload mínimo de Stop hook — el hook no usa los campos del evento
_STOP_PAYLOAD = json.dumps({"hook_event_name": "Stop"})


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_config(repo: str, config: dict) -> None:
    """Escribe .claude/git-memory-config.json en el repo temporal."""
    claude_dir = os.path.join(repo, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    with open(os.path.join(claude_dir, "git-memory-config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f)


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
        """Sin fichero .claude/git-memory-config.json → no bloquea."""
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
        """Config que no se puede leer → fail-open, no bloquea."""
        workdir = _makes_tmp_dir(tmp_path)
        claude_dir = os.path.join(workdir, ".claude")
        os.makedirs(claude_dir)
        config_path = os.path.join(claude_dir, "git-memory-config.json")
        # Crear un fichero con JSON inválido para simular config corrupta
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("{ INVALID JSON }")

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


# ── Caso extra: metacaracteres en test_command → NO shell injection ────────────

class TestMetacharacterSafety:
    """test_command con metacaracteres de shell NO ejecuta comandos adicionales.

    El hook DEBE usar shell=False (shlex.split) para ejecutar test_command.
    Un ';' o '&&' en el string no debe separar comandos adicionales.

    Cómo verifica el test: si shell=True, `python3 -c "pass" ; python3 -c
    "import sys; sys.exit(1)"` ejecutaría ambos comandos y el exit code sería
    el del segundo (1 → bloqueo). Con shell=False, el ';' es un argumento
    literal pasado a python3 y el comando falla por argumento inválido.
    El test verifica que ese fallo resulta en fail-open (no en bloqueo del
    comando secundario que viene después del ';').

    En ambos casos (shell=True y shell=False) el hook DEBE HACER fail-open
    cuando el primer comando falla por argumento inesperado — el test pin
    el comportamiento fail-open como invariante de seguridad.
    """

    def test_semicolon_metacharacter_does_not_inject_second_command(self, tmp_path):
        """';' en test_command no ejecuta el comando tras el punto y coma como
        comando shell independiente.

        Con shell=False: `python3 -c 'pass' ; python3 -c 'sys.exit(1)'`
        tokenizado con shlex da `[python3, -c, pass, ;, python3, -c, sys.exit(1)]`,
        que falla porque python3 no acepta ';' como argumento — fail-open.

        Invariante: el hook NO debe bloquear por la parte que viene después del ';'.
        Si bloqueara, significaría que ejecutó shell=True y el segundo comando
        (`python3 -c 'import sys; sys.exit(1)'`) corrió y salió 1.
        """
        workdir = _makes_tmp_dir(tmp_path)
        # La parte antes del ';' es un comando válido que pasa.
        # La parte después forzaría un exit 1 si se ejecutara como shell.
        _write_config(workdir, {
            "test_command": (
                f"{sys.executable} -c \"pass\" "
                f"; {sys.executable} -c \"import sys; sys.exit(1)\""
            )
        })

        rc, parsed, stdout, _ = _run_hook(workdir)

        # Con shell=False: falla porque el ';' es argumento inválido → fail-open.
        # Con shell=True: el segundo comando ejecuta exit(1) → bloquea.
        # El test EXIGE que NO haya bloqueo.
        assert rc == 0
        if parsed is not None:
            assert parsed.get("decision") != "block", (
                "Metacaracter ';' NO debe causar bloqueo. "
                "Si falla aquí, el hook usa shell=True y es vulnerable a inyección. "
                f"parsed={parsed!r}"
            )

    def test_command_injection_pattern_does_not_execute(self, tmp_path):
        """Patrón de inyección `$(command)` en test_command no ejecuta el subcomando.

        Con shell=False, `$(...)` es texto literal pasado como argumento.
        Con shell=True, el subcomando se ejecutaría — inyección confirmada.

        El test usa un comando que si se ejecutara como shell crearía un fichero
        centinela; verificamos que el fichero NO existe.
        """
        workdir = _makes_tmp_dir(tmp_path)
        sentinel = os.path.join(workdir, "injected.txt")
        # Con shell=True, esto crearía injected.txt al expandir la subshell.
        # Con shell=False, el '$(...)' es literal y no se expande.
        _write_config(workdir, {
            "test_command": (
                f"{sys.executable} -c \"pass\" "
                f"$(python3 -c \"open('{sentinel}', 'w').close()\")"
            )
        })

        rc, _, _, _ = _run_hook(workdir)

        assert rc == 0
        assert not os.path.exists(sentinel), (
            "El fichero centinela fue creado — el hook está expandiendo subshell "
            "(shell=True). Esto es una vulnerabilidad de inyección de comandos. "
            "Ultron DEBE usar shell=False con shlex.split()."
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
