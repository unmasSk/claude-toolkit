"""
Regresion permanente para 2 fixes T1 (Argus, issue #63) aplicados en
wip 5c9d012 sobre lecturas de manifest.json.

RETIRADO EN ESTE FICHERO (fase #63 P1 v2, decision 2d56444, ver tambien
test_crew_manifest_version_gate.py): las 2 clases que probaban el sitio
`hooks/session-start-crew.py :: _manifest_version_matches(git_root)`
(TestSecT1_001CrewManifestVersionMatchesFailSafe y
TestSecT1_002CrewManifestVersionMatchesFailSafe) se retiran -- no por un
cambio de contrato semantico, sino porque la funcion misma DEJA DE EXISTIR
en el gate v2: `git diff -- hooks/session-start-crew.py` (WIP de Ultron en
curso al momento de este retiro) borra integramente
`_manifest_version_matches` junto con sus imports (`json`, `git_helpers.
verify_path_within_project`, `version.VERSION`) -- el hook v2 nunca vuelve
a leer manifest.json para decidir si reescribe CLAUDE.md (ver docstring de
test_crew_content_gate_v2.py y test_crew_manifest_version_gate.py). Sin
lectura de manifest en ese sitio no hay superficie de ataque SEC-T1-001/002
que endurecer alli: dejarlas habria producido AttributeError contra el
modulo (funcion inexistente), no un fallo de aserto -- confirmado leyendo
el diff en curso, no una suposicion.

Quedan 2 de los 3 puntos de lectura originales, sin cambios de Ultron en
este WIP y por tanto con contrato intacto:

  - lib/boot_health.py          :: check_version_mismatch()
  - lib/upgrade_check.py        :: needs_upgrade(root)

[corregido 2026-08-05: check_version_mismatch() se retiro de
lib/boot_health.py junto con el resto del sistema de memoria v1 -- solo
sobreviven CACHE_BASE_DIR, _md5_file() y _latest_version_dir() en ese
fichero. Su clase de test (TestSecT1_001BootHealthCheckVersionMismatchFailSafe)
se retiro; ver nota en su antiguo sitio. Solo
lib/upgrade_check.py::needs_upgrade() sigue cubierto aqui.]

SEC-T1-001 (RecursionError -> crash): un manifest.json con anidamiento
JSON extremo hace que json.load lance RecursionError, que no es ni
OSError ni json.JSONDecodeError -- escapaba del except estrecho y
crasheaba el hook/funcion que lo llamaba. Fix: el except se amplio a
`except Exception:` en estos sitios (upgrade_check.py ya lo tenia amplio
de antes -- ver nota en la clase de ese sitio).

SEC-T1-002 (symlink de directorio bypassa el guard): open_no_follow_symlink()
solo protege el COMPONENTE FINAL de la ruta (manifest.json). Si `.claude`
(o `.claude/.unmassk`) es en si mismo un symlink de DIRECTORIO apuntando
a un sitio con un manifest.json REAL (no symlink), open_no_follow_symlink()
no tiene nada que objetar -- el ultimo componente genuinamente no es un
symlink. Fix: verify_path_within_project(manifest_path, root) antes del
open, en estos sitios -- resuelve cada componente intermedio via realpath()
y rechaza cualquier ruta que escape del git root.

Canal: llamada directa a las 2 funciones (nunca al hook completo via
--json ni parseo de stdout), cada una en un subprocess aislado (evita
contaminar sys.modules del proceso de test con modulos reales y
establemente cacheados como upgrade_check/boot_health -- ver
unmassk-toolkit-python-test-conventions.md). Ambas toman `root`/cwd
explicitos o dependen del cwd del proceso (documentado por funcion), asi
que cada helper de invocacion fija el canal correcto.

Build mode: linear (fix ya aplicado por Ultron en wip 5c9d012; el retiro
del sitio crew es limpieza de suite en la misma fase que
test_crew_manifest_version_gate.py). Solo tests -- ningun cambio de
produccion en este fichero.
"""

import json
import os
import subprocess
import sys

import pytest

from conftest import SOURCE_ROOT, INSTALL, git_cmd, run_script

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

# SEC-T1-001 payload: anidamiento JSON valido (array vacio anidado N veces)
# que agota la pila de recursion de json.load bien por debajo del limite de
# recursion por defecto de Python (1000) -- confirmado localmente: con
# N=150000, json.loads() lanza RecursionError, nunca JSONDecodeError ni
# OSError. Construido con multiplicacion de string (O(N), sin recursion en
# el propio test).
_MALICIOUS_NESTING_DEPTH = 150000


def _malicious_deep_json_payload(n=_MALICIOUS_NESTING_DEPTH):
    return "[" * n + "]" * n


# ── Repo helpers ──────────────────────────────────────────────────────────


def _make_installed_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    rc, out, err = run_script(INSTALL, repo, ["--auto"])
    assert rc == 0, f"install --auto failed: {out}\n{err}"
    return repo


def _make_installed_repo_for_needs_upgrade(tmp_path, name="repo"):
    """needs_upgrade()'s Check 1 (stale CLAUDE.md markers) must be
    neutralized first, or Check 2 (the manifest read under test) is never
    reached -- same precondition test_needs_upgrade_semver.py's
    make_semver_test_repo() establishes, reused here via conftest's shared
    helper instead of re-deriving the patch."""
    from conftest import neutralize_needs_upgrade_check1

    repo = _make_installed_repo(tmp_path, name)
    neutralize_needs_upgrade_check1(repo)
    return repo


def _manifest_path(repo):
    return os.path.join(repo, ".claude", ".unmassk", "manifest.json")


def _write_malicious_deep_manifest(repo):
    with open(_manifest_path(repo), "w", encoding="utf-8") as f:
        f.write(_malicious_deep_json_payload())


# ── Direct-call probes, one isolated subprocess per invocation ────────────
# (never in-process: upgrade_check/boot_health are real, stably-named
# modules -- an in-process import would leak into sys.modules and could
# contaminate other test files running in the same pytest session, see
# unmassk-toolkit-python-test-conventions.md)


def _call_needs_upgrade(repo):
    code = f"""
import sys, json
sys.path.insert(0, {LIB_DIR!r})
import upgrade_check
result = upgrade_check.needs_upgrade({repo!r})
print(json.dumps({{"result": result}}))
"""
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", timeout=30
    )


def _result_or_fail(proc, label):
    assert proc.returncode == 0, (
        f"{label} probe must not crash (fail-safe contract). "
        f"rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    last_line = proc.stdout.strip().splitlines()[-1]
    return json.loads(last_line)["result"]


# ── Sanity: the payload itself is genuinely malicious ──────────────────────


class TestMaliciousPayloadSanity:
    def test_deep_nested_payload_raises_recursion_error_directly(self):
        """Precondition proof (not a production-code test): the fixture used
        by every SEC-T1-001 test below must actually trigger RecursionError
        when parsed by the stdlib json module directly -- not
        JSONDecodeError, not some other error. If this ever stops being
        true (e.g. a future CPython changes the nesting guard), every
        SEC-T1-001 test below would silently stop proving anything."""
        with pytest.raises(RecursionError):
            json.loads(_malicious_deep_json_payload())


# ══════════════════════════════════════════════════════════════════════════
# SEC-T1-001 -- RecursionError from a maliciously deep-nested manifest.json
# must never crash the caller; each site must return its documented
# fail-safe value.
# ══════════════════════════════════════════════════════════════════════════


# RETIRADO (memoria v2, 2026-08-05): TestSecT1_001BootHealthCheckVersionMismatchFailSafe
# (y su helper _call_check_version_mismatch()) probaba
# lib/boot_health.py::check_version_mismatch() -- esa funcion se retiro de
# boot_health.py junto con el resto del sistema de memoria v1 (solo
# sobreviven CACHE_BASE_DIR, _md5_file() y _latest_version_dir() en ese
# fichero, confirmado leyendolo). 1/1 test fallaba con AttributeError:
# module 'boot_health' has no attribute 'check_version_mismatch'. El otro
# sitio que este fichero cubria (lib/upgrade_check.py::needs_upgrade(),
# clase de abajo) es independiente y sigue vivo.


class TestSecT1_001UpgradeCheckNeedsUpgradeFailSafe:
    """lib/upgrade_check.py::needs_upgrade() -- fail-safe is False (no
    spurious auto-upgrade subprocess triggered by an unparseable manifest).

    Note: this site's `except Exception:` was already broad BEFORE issue
    #63's SEC-T1-001 fix (the commit only added verify_path_within_project()
    here, for SEC-T1-002) -- this test is a regression guard against a
    FUTURE narrowing of that except, not a fix this commit introduced for
    this specific site. Still one of the 2 read points this file covers.
    """

    def test_deep_nested_manifest_returns_false_without_crashing(self, tmp_path):
        repo = _make_installed_repo_for_needs_upgrade(tmp_path)
        _write_malicious_deep_manifest(repo)

        proc = _call_needs_upgrade(repo)
        result = _result_or_fail(proc, "needs_upgrade")

        assert result is False, (
            "SEC-T1-001: a deeply-nested manifest.json must fail-safe to "
            f"False, not crash or trigger an upgrade. stdout={proc.stdout!r}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
