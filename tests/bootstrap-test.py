#!/usr/bin/env python3
"""
bootstrap-test.py — Tests para git-memory-bootstrap (scout conservador).
=========================================================================
Verifica detección de stack, monorepos, proyectos vacíos, commitlint,
y memoria existente.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "git-memory-bootstrap.py")
INSTALL_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "git-memory-install.py")


def make_temp_repo():
    """Crear un repo git temporal."""
    d = tempfile.mkdtemp(prefix="bootstrap-test-")
    subprocess.run(["git", "init", d], capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "--allow-empty", "-m", "init"], capture_output=True)
    return d


def run_bootstrap(cwd, extra_args=None):
    """Ejecutar bootstrap y devolver (exit_code, stdout, parsed_json)."""
    args = [sys.executable, SCRIPT, "--json"] + (extra_args or [])
    result = subprocess.run(args, capture_output=True, text=True, cwd=cwd, timeout=15)
    parsed = None
    if result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
    return result.returncode, result.stdout, parsed


def write_file(repo, path, content):
    """Escribir un archivo en el repo."""
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)


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
print("BOOTSTRAP TEST — Scout Conservador")
print("=" * 60)

# ── TEST 1: Proyecto vacío ──
print("\n── TEST 1: Proyecto vacío ──")
repo = make_temp_repo()
code, _, data = run_bootstrap(repo)

# Proyecto vacío debería sugerir minimal_bootstrap
suggestions = [s["action"] for s in data.get("suggestions", [])] if data else []
findings_categories = [f["category"] for f in data.get("findings", [])] if data else []

test("Produce output JSON válido", data is not None)
test("No detecta stack", "stack" not in findings_categories)
test("Sugiere minimal_bootstrap", "minimal_bootstrap" in suggestions)
cleanup(repo)

# ── TEST 2: Proyecto Node.js/TypeScript ──
print("\n── TEST 2: Proyecto Node.js/TypeScript ──")
repo = make_temp_repo()
write_file(repo, "package.json", json.dumps({
    "name": "test-app",
    "dependencies": {"react": "^18.0.0", "next": "^14.0.0"},
    "devDependencies": {"typescript": "^5.3.0"},
}))
write_file(repo, "tsconfig.json", '{"compilerOptions":{}}')
write_file(repo, "tailwind.config.js", "module.exports = {}")
subprocess.run(["git", "-C", repo, "add", "-A"], capture_output=True)
subprocess.run(["git", "-C", repo, "commit", "-m", "setup"], capture_output=True)

code, _, data = run_bootstrap(repo)
findings_text = [f["text"] for f in data.get("findings", [])] if data else []

test("Detecta React", any("React" in t for t in findings_text))
test("Detecta Next.js", any("Next.js" in t for t in findings_text))
test("Detecta TypeScript", any("TypeScript" in t for t in findings_text))
test("Detecta Tailwind", any("Tailwind" in t for t in findings_text))
test("Sugiere bootstrap_commit", "bootstrap_commit" in [s["action"] for s in data.get("suggestions", [])])
cleanup(repo)

# ── TEST 3: Proyecto Python ──
print("\n── TEST 3: Proyecto Python ──")
repo = make_temp_repo()
write_file(repo, "pyproject.toml", """
[project]
name = "my-api"
requires-python = ">=3.11"

[build-system]
build-backend = "hatchling.core"

[project.dependencies]
fastapi = ">=0.110"
sqlalchemy = ">=2.0"
pydantic = ">=2.0"
""")
write_file(repo, "requirements.txt", "fastapi\nsqlalchemy\n")
subprocess.run(["git", "-C", repo, "add", "-A"], capture_output=True)
subprocess.run(["git", "-C", repo, "commit", "-m", "setup"], capture_output=True)

code, _, data = run_bootstrap(repo)
findings_text = [f["text"] for f in data.get("findings", [])] if data else []

test("Detecta Python", any("Python" in t for t in findings_text))
test("Detecta FastAPI", any("FastAPI" in t for t in findings_text))
test("Detecta SQLAlchemy", any("SQLAlchemy" in t for t in findings_text))
test("Detecta Pydantic", any("Pydantic" in t for t in findings_text))
cleanup(repo)

# ── TEST 4: Monorepo ──
print("\n── TEST 4: Monorepo ──")
repo = make_temp_repo()
write_file(repo, "package.json", json.dumps({
    "name": "monorepo",
    "workspaces": ["packages/*"],
}))
write_file(repo, "turbo.json", "{}")
write_file(repo, "packages/web/package.json", '{"name": "@app/web"}')
write_file(repo, "packages/api/package.json", '{"name": "@app/api"}')
write_file(repo, "packages/shared/package.json", '{"name": "@app/shared"}')
subprocess.run(["git", "-C", repo, "add", "-A"], capture_output=True)
subprocess.run(["git", "-C", repo, "commit", "-m", "setup"], capture_output=True)

code, _, data = run_bootstrap(repo)
findings = data.get("findings", []) if data else []
hypotheses = [f for f in findings if f["level"] == "hypothesis"]
suggestions = [s["action"] for s in data.get("suggestions", [])] if data else []

test("Detecta monorepo como hypothesis", any("Monorepo" in f["text"] for f in hypotheses))
test("Sugiere ask_scope", "ask_scope" in suggestions)
test("Monorepo signals incluyen sub-projects", len(data.get("monorepo_signals", [])) > 0)
cleanup(repo)

# ── TEST 5: commitlint detectado ──
print("\n── TEST 5: commitlint detectado ──")
repo = make_temp_repo()
write_file(repo, "commitlint.config.js", "module.exports = { extends: ['@commitlint/config-conventional'] };")
write_file(repo, "package.json", '{"name": "test"}')
os.makedirs(os.path.join(repo, ".husky"), exist_ok=True)
write_file(repo, ".husky/commit-msg", '#!/bin/sh\nnpx --no -- commitlint --edit "$1"')
subprocess.run(["git", "-C", repo, "add", "-A"], capture_output=True)
subprocess.run(["git", "-C", repo, "commit", "-m", "setup"], capture_output=True)

code, _, data = run_bootstrap(repo)
findings = data.get("findings", []) if data else []
suggestions = [s["action"] for s in data.get("suggestions", [])] if data else []

test("Detecta commitlint como hypothesis", any("commitlint" in f.get("text", "").lower() for f in findings if f["level"] == "hypothesis"))
test("Sugiere compatible mode", "consider_compatible_mode" in suggestions)
cleanup(repo)

# ── TEST 6: Memoria ya instalada ──
print("\n── TEST 6: Memoria ya instalada ──")
repo = make_temp_repo()
claude_dir = os.path.join(repo, ".claude")
os.makedirs(claude_dir, exist_ok=True)
with open(os.path.join(claude_dir, "git-memory-manifest.json"), "w") as f:
    json.dump({"version": "2.0.0", "runtime_mode": "normal"}, f)
subprocess.run(["git", "-C", repo, "add", "-A"], capture_output=True)
subprocess.run(["git", "-C", repo, "commit", "-m", "installed"], capture_output=True)

code, _, data = run_bootstrap(repo)
suggestions = [s["action"] for s in data.get("suggestions", [])] if data else []
findings = data.get("findings", []) if data else []

test("Detecta memoria instalada", any("already installed" in f.get("text", "") for f in findings))
test("Sugiere skip_bootstrap", "skip_bootstrap" in suggestions)
cleanup(repo)

# ── TEST 7: Múltiples ecosistemas ──
print("\n── TEST 7: Múltiples ecosistemas ──")
repo = make_temp_repo()
write_file(repo, "Dockerfile", "FROM python:3.11")
write_file(repo, "Makefile", "build:\n\tdocker build .")
os.makedirs(os.path.join(repo, ".github", "workflows"), exist_ok=True)
write_file(repo, ".github/workflows/ci.yml", "name: CI")
write_file(repo, "go.mod", "module myapp\ngo 1.22")
subprocess.run(["git", "-C", repo, "add", "-A"], capture_output=True)
subprocess.run(["git", "-C", repo, "commit", "-m", "setup"], capture_output=True)

code, _, data = run_bootstrap(repo)
findings_text = [f["text"] for f in data.get("findings", [])] if data else []
ecosystems = set(f["ecosystem"] for f in data.get("findings", []) if "ecosystem" in f)

test("Detecta Docker", any("Docker" in t for t in findings_text))
test("Detecta Go", any("Go" in t for t in findings_text))
test("Detecta GitHub Actions", any("GitHub Actions" in t for t in findings_text))
test("Detecta Make", any("Make" in t for t in findings_text))
cleanup(repo)

# ── TEST 8: --silent exit code ──
print("\n── TEST 8: --silent exit code ──")
repo = make_temp_repo()
# Vacío → exit 1
result_empty = subprocess.run(
    [sys.executable, SCRIPT, "--silent"], capture_output=True, text=True, cwd=repo, timeout=15
)
# Con archivos → exit 0
write_file(repo, "package.json", '{"name": "test"}')
subprocess.run(["git", "-C", repo, "add", "-A"], capture_output=True)
subprocess.run(["git", "-C", repo, "commit", "-m", "add"], capture_output=True)
result_full = subprocess.run(
    [sys.executable, SCRIPT, "--silent"], capture_output=True, text=True, cwd=repo, timeout=15
)

test("Vacío → exit 1", result_empty.returncode == 1)
test("Con stack → exit 0", result_full.returncode == 0)
test("--silent no produce output", result_empty.stdout.strip() == "" and result_full.stdout.strip() == "")
cleanup(repo)


# ── Resumen ──
print("\n" + "=" * 60)
total = passed + failed
if failed == 0:
    print(f"BOOTSTRAP TEST: ALL PASSED ✓ ({passed}/{total})")
else:
    print(f"BOOTSTRAP TEST: {failed} FAILED ({passed}/{total} passed)")
print("=" * 60)
sys.exit(1 if failed else 0)
