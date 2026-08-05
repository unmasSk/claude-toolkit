"""
Pase de endurecimiento — tests de regresión y adversariales para los arreglos
de seguridad recientes en hooks/user-prompt-memory-check.py.

RETIRADO (PLAN-CONSTRUCCION.md paso 9.3): lib/recall.py ya no existe en
disco — eliminado junto con el resto del sistema de memoria v1. Los tests
T1-B/T1-C/T1-D (recall push→pull) y T2-B (Unicode separators en
_sanitize()) que dependian de el se retiraron completos; ver el comentario
al final de este fichero.

Arreglos cubiertos
──────────────────
T1-A [fail-open upgrade]
    El bloque needs_upgrade() + subprocess.run() está envuelto en try/except.
    Un subprocess.TimeoutExpired (script lento >15 s) o cualquier Exception
    genérica NO deben propagar: el boot debe continuar y salir con código 0.

    Issue #63 (boot simplification, point 2): este bloque vive ahora en
    lib/upgrade_check.py::trigger_auto_upgrade_if_needed(), invocado una vez
    por SessionStart desde hooks/session-start-boot.py -- ya NO en
    hooks/user-prompt-memory-check.py, cuyo main() no llama a
    needs_upgrade()/subprocess.run() en absoluto tras el refactor. Ver
    TestFailOpenUpgrade más abajo para el canal real ejercitado.

T2-A [stdin acotado — DoS por tamaño]
    Un payload JSON >600 KB no debe colgar el hook ni causar exit != 0.

Patrón de importación en-proceso
─────────────────────────────────
Para T1-A (fail-open upgrade) se usa el mismo patrón de subproceso aislado que
_run_boot_with_failing_log_write() en test_boot_output.py: el código real
(hooks/session-start-boot.py + lib/upgrade_check.py) se carga y ejecuta en un
subproceso desechable, con el punto exacto de sabotaje inyectado como texto
antes de cargar el hook — ver TestFailOpenUpgrade más abajo.

Para los tests de salida que quedan se usa el patrón de subproceso de
test_user_prompt_recall.py: _run_hook(repo, prompt).
"""

import json
import os
import subprocess
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, INSTALL, git_cmd, run_cmd, run_script

# ── Paths ──────────────────────────────────────────────────────────────────────

HOOK_FILE = os.path.join(HOOKS_DIR, "user-prompt-memory-check.py")
BOOT_HOOK = os.path.join(HOOKS_DIR, "session-start-boot.py")
LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

# Plugin version — needed to write a matching manifest so needs_upgrade() → False
_PLUGIN_JSON = os.path.join(SOURCE_ROOT, ".claude-plugin", "plugin.json")
with open(_PLUGIN_JSON, encoding="utf-8") as _f:
    _PLUGIN_VERSION = json.load(_f)["version"]


# ── Repo helpers ───────────────────────────────────────────────────────────────

def _make_repo(tmp_path, name="repo"):
    """Create a minimal git repo."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _make_installed_repo(tmp_path, name="repo"):
    """Create a repo that appears fully installed (skips needs_install and needs_upgrade).

    Writes:
      1. CLAUDE.md with managed block markers + 'Context Checkpoint Commits'.
      2. .claude/.unmassk/manifest.json with version == PLUGIN_VERSION.
      3. .session-booted flag so the hook uses the already-booted path.
    """
    repo = _make_repo(tmp_path, name)

    claude_md_path = os.path.join(repo, "CLAUDE.md")
    with open(claude_md_path, "w", encoding="utf-8") as f:
        f.write(
            "<!-- BEGIN unmassk-toolkit -->\n"
            "Context Checkpoint Commits\n"
            "<!-- END unmassk-toolkit -->\n"
        )

    unmassk_dir = os.path.join(repo, ".claude", ".unmassk")
    os.makedirs(unmassk_dir, exist_ok=True)

    manifest_path = os.path.join(unmassk_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"version": _PLUGIN_VERSION}, f)

    booted_flag = os.path.join(unmassk_dir, ".session-booted")
    open(booted_flag, "w", encoding="utf-8").close()

    return repo


def _commit(repo, subject, trailers=""):
    """Add a memory commit with optional trailer block."""
    msg = subject if not trailers else subject + "\n\n" + trailers
    git_cmd(["commit", "--allow-empty", "-m", msg], repo)


# ── Subprocess hook invocation helper ─────────────────────────────────────────

def _run_hook(repo, prompt, *, input_text=None):
    """Invoke the hook via subprocess with JSON on stdin.

    If input_text is provided it is used verbatim (for edge-case payloads).
    Returns (returncode, stdout_str, stderr_str). stdout is stripped.
    """
    if input_text is None:
        input_text = json.dumps({"prompt": prompt})
    return run_cmd(
        [sys.executable, HOOK_FILE],
        cwd=repo,
        input_text=input_text,
    )


# ══════════════════════════════════════════════════════════════════════════════
# T1-A: fail-open upgrade — subprocess.TimeoutExpired y Exception genérico
# ══════════════════════════════════════════════════════════════════════════════

class TestFailOpenUpgrade:
    """El bloque de upgrade vive en lib/upgrade_check.py::trigger_auto_upgrade_if_needed(),
    invocado una vez por SessionStart desde hooks/session-start-boot.py::main() (issue #63,
    boot simplification, point 2).

    Deuda reportada por Ultron (wip 8245c99) y confirmada aquí: la versión anterior de esta
    clase parcheaba subprocess.run global y llamaba a hook.main() de
    hooks/user-prompt-memory-check.py -- pasaba en verde, pero por la razón equivocada.
    Tras el refactor, ese main() ya NO llama a needs_upgrade()/subprocess.run() en absoluto
    (ver su propio comentario "Case 1.5 ... removed"), así que el parche nunca se ejercitaba
    y el try/except real (ahora en lib/upgrade_check.py) nunca se probaba.

    Reescrita para ejercitar el canal real de punta a punta:
    hooks/session-start-boot.py::main() -> lib/upgrade_check.py::trigger_auto_upgrade_if_needed()
    -> subprocess.run(). Cada test corre boot.main() de verdad en un subproceso aislado (mismo
    patrón que _run_boot_with_failing_log_write() en test_boot_output.py: boot.main() llama
    sys.exit(0) al final igual que al ejecutar el fichero directamente, así que rc/stdout/stderr
    tienen exactamente la misma forma que run_boot()) contra un repo real e instalado cuyo
    manifest.json queda deliberadamente por debajo de PLUGIN_VERSION -- dispara
    needs_upgrade()==True por la vía semver (check 2), sin depender de markers antiguos.

    Anti-vacuidad (verificado manualmente antes de fijar esta versión, no repetido en CI):
    con el try/except de trigger_auto_upgrade_if_needed() retirado (y check=True añadido al
    subprocess.run interno para hacer que el caso 3 -- exit≠0 sin excepción por diseño hoy --
    también dependa de la protección), las 3 pruebas de abajo pasan a ROJO: boot.main() propaga
    la excepción sin capturar y el subproceso sale con rc=1 en vez de 0. Confirma que estas
    pruebas dependen genuinamente del try/except, no de que nada dispare la ruta de sabotaje.
    """

    def _make_repo_needing_upgrade_via_semver(self, tmp_path):
        """Repo real, completamente instalado (git-memory-install.py --auto), cuyo
        manifest.json queda deliberadamente por debajo de PLUGIN_VERSION. Tras una
        instalación real, el bloque gestionado de CLAUDE.md ya no lleva markers
        antiguos, así que el único camino que dispara needs_upgrade()==True aquí
        es el chequeo semver (check 2 de needs_upgrade()), no el check 1."""
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["config", "user.email", "test@test.com"], repo)
        git_cmd(["config", "user.name", "Test"], repo)
        git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
        run_script(INSTALL, repo, ["--auto"])

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["version"] = "0.0.1"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        return repo

    def _run_boot_with_sabotaged_installer(self, repo, sabotage_code):
        """Corre hooks/session-start-boot.py::main() de verdad, en un subproceso
        aislado, con el subprocess.run que trigger_auto_upgrade_if_needed() invoca
        saboteado según `sabotage_code` (fragmento Python inyectado justo antes de
        cargar el hook, después de confirmar needs_upgrade()==True como sanity
        check). upgrade_check es un módulo real y estable (import bin/session-start-boot.py
        lo reutiliza vía sys.modules), así que todo esto corre en un subproceso
        desechable para no contaminar sys.modules del resto de la sesión de pytest
        -- misma disciplina documentada en unmassk-toolkit-python-test-conventions.md.
        """
        code = f"""
import sys, os
sys.path.insert(0, {repr(LIB_DIR)})
sys.path.insert(0, {repr(HOOKS_DIR)})
os.chdir({repr(repo)})

import upgrade_check
assert upgrade_check.needs_upgrade({repr(repo)}) is True, "sanity: needs_upgrade debe ser True antes de sabotear"

{sabotage_code}

import importlib.util
spec = importlib.util.spec_from_file_location('boot', {repr(BOOT_HOOK)})
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)
boot.main()
"""
        return run_cmd([sys.executable, "-c", code], repo, timeout=30)

    def test_timeout_expired_does_not_break_boot(self, tmp_path):
        """subprocess.TimeoutExpired real (installer que tarda >15s) dentro de
        trigger_auto_upgrade_if_needed() -> boot.main() debe salir 0 con el
        banner presente, nunca propagar la excepción.

        El sabotaje sólo intercepta la llamada cuyo cmd contiene
        'git-memory-install.py'; cualquier otra llamada a subprocess.run dentro
        del boot (p. ej. doctor/repair) sigue siendo real, para no confundir un
        efecto colateral no relacionado con la propiedad bajo prueba.
        """
        repo = self._make_repo_needing_upgrade_via_semver(tmp_path)

        sabotage = """
import subprocess as _subprocess
_real_run = _subprocess.run
def _fake_run(cmd, *a, **kw):
    if isinstance(cmd, list) and any('git-memory-install.py' in str(c) for c in cmd):
        raise _subprocess.TimeoutExpired(cmd=cmd, timeout=15)
    return _real_run(cmd, *a, **kw)
_subprocess.run = _fake_run
"""
        rc, stdout, stderr = self._run_boot_with_sabotaged_installer(repo, sabotage)

        assert rc == 0, (
            f"boot.main() debe salir 0 pese a un TimeoutExpired real en el "
            f"installer; rc={rc}\nstdout: {stdout!r}\nstderr: {stderr!r}"
        )
        assert "STATUS:" in stdout, (
            f"el banner de boot debe seguir presente; stdout={stdout!r}"
        )
        assert "upgrade fail-open" in stderr, (
            "se esperaba la traza fail-open de trigger_auto_upgrade_if_needed() "
            f"en stderr, confirmando que el try/except realmente actuó; stderr={stderr!r}"
        )

    def test_generic_exception_does_not_break_boot(self, tmp_path):
        """Excepción genérica (OSError -- instalador ausente/sin permisos) dentro
        de trigger_auto_upgrade_if_needed() -> boot.main() debe salir 0, nunca
        propagar."""
        repo = self._make_repo_needing_upgrade_via_semver(tmp_path)

        sabotage = """
import subprocess as _subprocess
_real_run = _subprocess.run
def _fake_run(cmd, *a, **kw):
    if isinstance(cmd, list) and any('git-memory-install.py' in str(c) for c in cmd):
        raise OSError('script de instalacion no encontrado')
    return _real_run(cmd, *a, **kw)
_subprocess.run = _fake_run
"""
        rc, stdout, stderr = self._run_boot_with_sabotaged_installer(repo, sabotage)

        assert rc == 0, (
            f"boot.main() debe salir 0 pese a un OSError real en el installer; "
            f"rc={rc}\nstdout: {stdout!r}\nstderr: {stderr!r}"
        )
        assert "STATUS:" in stdout, (
            f"el banner de boot debe seguir presente; stdout={stdout!r}"
        )
        assert "upgrade fail-open" in stderr, (
            f"se esperaba la traza fail-open en stderr; stderr={stderr!r}"
        )

    def test_installer_nonzero_exit_does_not_break_boot(self, tmp_path):
        """El instalador sale con returncode != 0 (subproceso GENUINO, no
        mockeado -- un script Python real que hace sys.exit(3), apuntado vía
        upgrade_check._PLUGIN_ROOT) -> boot.main() debe salir 0 igualmente.

        subprocess.run() en trigger_auto_upgrade_if_needed() no usa check=True
        hoy, así que este caso concreto ni siquiera llega al except -- ya falla
        abierto por diseño (subprocess.run no lanza en returncode!=0 sin
        check=True). El mutation-check de esta clase (ver docstring de
        TestFailOpenUpgrade) cubre precisamente esto: con check=True añadido Y
        el try/except retirado, este test pasa a ROJO, probando que sigue
        dependiendo genuinamente de la protección y no de que el sabotaje nunca
        dispare nada.
        """
        repo = self._make_repo_needing_upgrade_via_semver(tmp_path)

        fake_root = tmp_path / "fake_plugin_root"
        (fake_root / "bin").mkdir(parents=True)
        (fake_root / "bin" / "git-memory-install.py").write_text(
            "import sys\nsys.exit(3)\n", encoding="utf-8"
        )

        sabotage = f"upgrade_check._PLUGIN_ROOT = {repr(str(fake_root))}"
        rc, stdout, stderr = self._run_boot_with_sabotaged_installer(repo, sabotage)

        assert rc == 0, (
            f"boot.main() debe salir 0 aunque el instalador real salga con "
            f"returncode=3; rc={rc}\nstdout: {stdout!r}\nstderr: {stderr!r}"
        )
        assert "STATUS:" in stdout, (
            f"el banner de boot debe seguir presente; stdout={stdout!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# T2-A: stdin acotado — DoS por tamaño
# ══════════════════════════════════════════════════════════════════════════════

class TestFailSafeLargeStdin:
    """Un payload JSON enorme (>600 KB) no debe colgar el hook ni causar exit != 0.

    El límite _STDIN_READ_LIMIT = 512_000 bytes trunca la lectura antes de parsear JSON.
    El hook debe manejar el JSON truncado (inválido) con el mismo camino fail-safe
    que cualquier otra entrada mal formada: sin crash, exit 0.
    """

    def test_large_stdin_exits_zero(self, tmp_path):
        """Payload de >600 KB → exit 0 (no crash, no timeout)."""
        repo = _make_installed_repo(tmp_path)

        # Construir un payload enorme: valor de 'prompt' de 600 KB de ruido
        big_value = "X" * 600_000
        big_payload = json.dumps({"prompt": big_value})

        rc, stdout, _stderr = _run_hook(repo, prompt=None, input_text=big_payload)

        assert rc == 0, (
            f"Hook debe salir con código 0 con payload de >600 KB; rc={rc}"
        )

    def test_large_stdin_no_crash_raw_bytes(self, tmp_path):
        """600 KB de basura binaria como stdin → exit 0, no crash.

        (La aserción original también comprobaba '[memory-check]' presente;
        ese texto fue retirado del hook — decision 1e94975, issue #69 — y la
        aserción se eliminó por dead-assertion, issue #72. El chequeo de
        exit 0 sigue siendo real y se conserva.)
        """
        repo = _make_installed_repo(tmp_path)

        # Basura que no es JSON válido (también >512 KB)
        garbage = "A" * 650_000

        rc, stdout, _stderr = _run_hook(repo, prompt=None, input_text=garbage)

        assert rc == 0, (
            f"Hook debe salir con código 0 con stdin de basura grande; rc={rc}"
        )

# RETIRADO (PLAN-CONSTRUCCION.md paso 9.3): TestSanitizeUnicodeSeparators
# (T2-B, U+2028/U+2029 en _sanitize()) y TestRecallRelevantEdgeCases
# (bordes de recall_relevant()/_sanitize()) importaban `recall` directamente
# (`import recall`, `from recall import recall_relevant, _sanitize`) —
# lib/recall.py ya no existe en disco, eliminado junto con el resto del
# sistema de memoria v1 (ver memoria-v2-boot-memory-precompact-retirement-
# notes.md en la memoria de este agente). El docstring del modulo (arriba)
# menciona T2-B y afirma que "_sanitize() sigue siendo real y usada por
# recall.py bajo demanda" -- ya no es asi, esa parte quedo desactualizada.
