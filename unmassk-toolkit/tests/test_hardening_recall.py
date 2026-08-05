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
T1-A [fail-open upgrade] -- RETIRADO 2026-08-05, ver nota abajo.

T2-A [stdin acotado — DoS por tamaño]
    Un payload JSON >600 KB no debe colgar el hook ni causar exit != 0.

[corregido 2026-08-05: T1-A (TestFailOpenUpgrade) cargaba
hooks/session-start-boot.py::main() de verdad en un subproceso -- ese
fichero ya no existe en disco (borrado junto con el resto del sistema de
memoria v1). La clase se retiró; ver el comentario en su antiguo sitio,
donde vivía, para el detalle. Solo T2-A (TestFailSafeLargeStdin) sigue
viva hoy, y usa el patrón de subproceso de test_user_prompt_recall.py:
_run_hook(repo, prompt).]
"""

import json
import os
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_cmd

# ── Paths ──────────────────────────────────────────────────────────────────────

HOOK_FILE = os.path.join(HOOKS_DIR, "user-prompt-memory-check.py")

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


# RETIRADO (memoria v2, 2026-08-05): TestFailOpenUpgrade cargaba y ejecutaba
# hooks/session-start-boot.py::main() de verdad en un subproceso -- ese
# fichero ya no existe en disco (borrado junto con el resto del sistema de
# memoria v1). 3/3 tests fallaban (confirmado ejecutando el fichero antes de
# este retiro: FileNotFoundError al cargar BOOT_HOOK). El contrato fail-open
# que protegía (lib/upgrade_check.py::trigger_auto_upgrade_if_needed() no
# debe propagar TimeoutExpired/OSError/exit!=0 del instalador) sigue siendo
# código real y sin test de fail-open propio hoy -- ahora se invoca desde
# hooks/session-start-crew.py::_print_upgrade_check() en vez de
# session-start-boot.py (confirmado por grep), pero redirigir esta cobertura
# ahí es una decisión de qué probar, no una retirada mecánica -- fuera del
# alcance de este pase, reportado aparte.

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
