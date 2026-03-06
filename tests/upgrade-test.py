#!/usr/bin/env python3
"""
upgrade-test.py — Tests para git-memory-upgrade.
=================================================
Verifica detección de cambios, backup, upgrade real, JSON, y --check.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

SOURCE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL_SCRIPT = os.path.join(SOURCE, "bin", "git-memory-install.py")
UPGRADE_SCRIPT = os.path.join(SOURCE, "bin", "git-memory-upgrade.py")
DOCTOR_SCRIPT = os.path.join(SOURCE, "bin", "git-memory-doctor.py")


def make_installed_repo():
    """Crear un repo con git-memory instalado."""
    d = tempfile.mkdtemp(prefix="upgrade-test-")
    subprocess.run(["git", "init", d], capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "--allow-empty", "-m", "init"], capture_output=True)
    subprocess.run(
        [sys.executable, INSTALL_SCRIPT, "--auto"],
        capture_output=True, text=True, cwd=d, timeout=15,
    )
    return d


def run_upgrade(cwd, extra_args=None):
    """Ejecutar upgrade y devolver (exit_code, stdout, stderr)."""
    args = [sys.executable, UPGRADE_SCRIPT] + (extra_args or [])
    result = subprocess.run(args, capture_output=True, text=True, cwd=cwd, timeout=15)
    return result.returncode, result.stdout, result.stderr


def cleanup(d):
    shutil.rmtree(d, ignore_errors=True)


# ── Tests ─────────────────────────────────────────────────────────────────

passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  {name} ✓")
        passed += 1
    else:
        print(f"  {name} ✗ {detail}")
        failed += 1


print("=" * 60)
print("UPGRADE TEST — Actualización Segura")
print("=" * 60)

# ── TEST 1: Sin instalación → error ──
print("\n── TEST 1: Sin instalación → error ──")
repo = tempfile.mkdtemp(prefix="upgrade-test-")
subprocess.run(["git", "init", repo], capture_output=True)
subprocess.run(["git", "-C", repo, "commit", "--allow-empty", "-m", "init"], capture_output=True)

code, stdout, stderr = run_upgrade(repo)
test("Exit code 1", code == 1)
test("Mensaje de error claro", "install" in stderr.lower() or "install" in stdout.lower())
cleanup(repo)

# ── TEST 2: Todo actualizado → nada que hacer ──
print("\n── TEST 2: Todo actualizado → nada que hacer ──")
repo = make_installed_repo()

code, stdout, _ = run_upgrade(repo, ["--check"])
test("--check exit 0", code == 0)
test("Reporta up-to-date", "más reciente" in stdout or "reciente" in stdout)
cleanup(repo)

# ── TEST 3: Detecta archivo modificado ──
print("\n── TEST 3: Detecta archivo modificado ──")
repo = make_installed_repo()

# Modificar un hook para simular versión vieja
hook = os.path.join(repo, "hooks", "pre-validate-commit-trailers.py")
with open(hook, "a") as f:
    f.write("\n# viejo\n")

code, stdout, _ = run_upgrade(repo, ["--dry-run"])
test("--dry-run exit 0", code == 0)
test("Detecta hook modificado", "pre-validate" in stdout)
test("No aplica cambios (dry-run)", "dry-run" in stdout.lower())

# Verificar que el hook sigue "viejo"
with open(hook) as f:
    content = f.read()
test("Hook no fue modificado en dry-run", "viejo" in content)
cleanup(repo)

# ── TEST 4: Upgrade real restaura archivos ──
print("\n── TEST 4: Upgrade real restaura archivos ──")
repo = make_installed_repo()

# Modificar hook
hook = os.path.join(repo, "hooks", "pre-validate-commit-trailers.py")
with open(hook, "a") as f:
    f.write("\n# viejo\n")

code, stdout, _ = run_upgrade(repo, ["--auto"])
test("Upgrade exit 0", code == 0)
test("Reporta completado", "completado" in stdout.lower() or "upgrade" in stdout.lower())

# Verificar que el hook fue restaurado
with open(hook) as f:
    content = f.read()
test("Hook restaurado (sin 'viejo')", "viejo" not in content)

# Verificar backup
backup_dir = os.path.join(repo, ".claude", "backups")
test("Backup creado", os.path.isdir(backup_dir))
backups = os.listdir(backup_dir) if os.path.isdir(backup_dir) else []
test("Al menos 1 archivo de backup", len(backups) >= 1)
cleanup(repo)

# ── TEST 5: JSON output ──
print("\n── TEST 5: JSON output ──")
repo = make_installed_repo()

# Modificar skill
skill = os.path.join(repo, "skills", "git-memory", "SKILL.md")
with open(skill, "a") as f:
    f.write("\n# viejo\n")

code, stdout, _ = run_upgrade(repo, ["--json", "--dry-run"])
try:
    data = json.loads(stdout)
    test("JSON válido", True)
    test("Status = update_available", data.get("status") == "update_available")
    test("Versión instalada presente", "installed_version" in data)
    test("Cambios incluidos", "modified" in data.get("changes", {}))
    modified = data.get("changes", {}).get("modified", [])
    test("SKILL.md en modificados", any("SKILL.md" in f for f in modified))
except json.JSONDecodeError:
    test("JSON válido", False, f"stdout: {stdout[:100]}")
    test("Status = update_available", False)
    test("Versión instalada presente", False)
    test("Cambios incluidos", False)
    test("SKILL.md en modificados", False)
cleanup(repo)

# ── TEST 6: --check JSON ──
print("\n── TEST 6: --check JSON ──")
repo = make_installed_repo()
code, stdout, _ = run_upgrade(repo, ["--check", "--json"])
try:
    data = json.loads(stdout)
    test("JSON válido en --check", True)
    test("Status = up_to_date", data.get("status") == "up_to_date")
except json.JSONDecodeError:
    test("JSON válido en --check", False)
    test("Status = up_to_date", False)
cleanup(repo)

# ── TEST 7: Manifest actualizado después de upgrade ──
print("\n── TEST 7: Manifest actualizado después de upgrade ──")
repo = make_installed_repo()

# Modificar un archivo para forzar upgrade
hook = os.path.join(repo, "hooks", "stop-dod-check.py")
with open(hook, "a") as f:
    f.write("\n# viejo\n")

run_upgrade(repo, ["--auto"])

manifest_path = os.path.join(repo, ".claude", "git-memory-manifest.json")
with open(manifest_path) as f:
    manifest = json.load(f)

test("Manifest tiene upgraded_at", "upgraded_at" in manifest)
test("Versión actualizada en manifest", manifest.get("version") == "2.0.0")
test("Fingerprint actualizado", "sha256:" in manifest.get("install_fingerprint", ""))
cleanup(repo)


# ── Resumen ──
print("\n" + "=" * 60)
total = passed + failed
if failed == 0:
    print(f"UPGRADE TEST: ALL PASSED ✓ ({passed}/{total})")
else:
    print(f"UPGRADE TEST: {failed} FAILED ({passed}/{total} passed)")
print("=" * 60)
sys.exit(1 if failed else 0)
