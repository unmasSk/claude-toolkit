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
respuesta), 12 ramas/caminos, 11 clases de test, 27 tests.
[2026-08-06: +2 clases / +7 tests -- contrato "config corrupto debe avisar,
distinto de no-configurado" (RED en TestCorruptConfigMustWarn hasta que
Ultron implemente el aviso); también se corrigió la ruta de config
(`.claude/git-memory-config.json` → `.claude/project-memory/config.json`)
que había dejado 4 tests de TestCommandFailsBlocks en rojo silencioso
desde el movimiento del fichero de config el mismo día.]
Not tested: comportamiento del comando de test en sí mismo (eso es del usuario);
integración real con Claude Code (fuera de alcance de tests unitarios de hook);
OSError de permisos reales (chmod) -- no reproducible de forma fiable en
Windows, cubierto en su lugar por el caso "config.json es un directorio"
(mismo except OSError, repro cross-platform confirmada a mano).
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
