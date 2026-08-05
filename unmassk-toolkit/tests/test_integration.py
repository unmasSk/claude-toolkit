"""
End-to-end integration tests.

Covers real-world scenarios: install over existing config, sessions,
compaction, and branch-aware context.

NOTE: The plugin runs from the cache. Install only creates CLAUDE.md +
manifest at the project root. Hooks/skills/bin are never copied to the
project.

Retirement note (2026-08-02): test_bootstrap_with_commits,
test_bootstrap_detects_installed (bin/git-memory-bootstrap.py),
test_gc_real (bin/git-memory-gc.py), test_uninstall_reinstall_data_intact
(bin/git-memory-uninstall.py), and test_upgrade_creates_backup
(bin/git-memory-upgrade.py) were removed -- all four scripts no longer
exist on disk (docs/memoria-v2/PLAN-CONSTRUCCION.md §5.4, "ya estaban
muertos"). Retired per §9.3. SOURCE_ROOT/UNINSTALL/UPGRADE/BOOTSTRAP/
run_doctor_json were dropped from the import block below since nothing
else in this file used them.
"""

import json
import os
import sys

import pytest

from conftest import (
    HOOKS_DIR, INSTALL, DOCTOR,
    run_cmd, git_cmd, write_file, run_script,
)
from version import VERSION


# ── Helpers ────────────────────────────────────────────────────────────

def make_installed_repo(tmp_path, name="repo"):
    """Create a temp repo with git-memory installed."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    run_script(INSTALL, repo, ["--auto"])
    return repo


# ── Tests ──────────────────────────────────────────────────────────────


def test_install_over_existing(tmp_path):
    """Install over existing .claude/ preserves user content."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)

    # Create existing user content
    write_file(repo, ".claude/my-settings.json", '{"custom": true}')
    write_file(repo, "CLAUDE.md", "# Mi Proyecto\n\nInstrucciones personalizadas aquí.\n")
    git_cmd(["add", "-A"], repo)
    git_cmd(["commit", "-m", "mi config"], repo)

    rc, _, _ = run_script(INSTALL, repo, ["--auto"])
    assert rc == 0
    assert os.path.isfile(os.path.join(repo, ".claude", "my-settings.json"))

    with open(os.path.join(repo, "CLAUDE.md"), encoding="utf-8") as f:
        claude_md = f.read()
    assert "Instrucciones personalizadas" in claude_md
    assert "BEGIN unmassk-toolkit" in claude_md


def test_install_only_creates_claude_md_and_manifest(tmp_path):
    """Install should only create CLAUDE.md and manifest — no hooks/skills/bin at project root."""
    repo = make_installed_repo(tmp_path)

    # CLAUDE.md exists
    with open(os.path.join(repo, "CLAUDE.md"), encoding="utf-8") as f:
        assert "BEGIN unmassk-toolkit" in f.read()

    # Manifest exists
    with open(os.path.join(repo, ".claude", ".unmassk", "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
        assert manifest["version"] == VERSION

    # Nothing else copied to project root
    assert not os.path.isdir(os.path.join(repo, "hooks"))
    assert not os.path.isdir(os.path.join(repo, "skills"))
    assert not os.path.isdir(os.path.join(repo, "bin"))
    assert not os.path.isdir(os.path.join(repo, "lib"))
    assert not os.path.isdir(os.path.join(repo, ".claude-plugin"))


# RETIRADO (memoria v2, 2026-08-05): test_session_with_trailers invocaba
# hooks/pre-validate-commit-trailers.py via run_hook_from_cache() -- ese
# hook se borro entero junto con el resto del sistema de memoria v1
# (confirmado: rc=1 "hook not found" al ejecutarlo antes de este retiro).
# Su sucesor real es hooks/customs.py (aduana), ya cubierto de punta a
# punta en tests/memory/test_customs_hook.py -- no hay comportamiento vivo
# que redirigir aqui especificamente para "un commit de sesion normal no
# bloquea", ese caso ya lo cubre TestCustomsDisabledNeverBlocks /
# TestCustomsEnabledBlocksWithExactRejectionText::test_enabled_valid_note_never_blocks
# en ese fichero.


def test_compaction_snapshot(tmp_path):
    """PreCompact snapshot stays within 18 lines."""
    repo = make_installed_repo(tmp_path)

    trailers_sets = [
        "Decision: usar TypeScript strict\nWhy: mejor tipado",
        "Memo: preference - siempre async/await\nWhy: consistencia",
        "Next: implementar auth\nBlocker: falta API key",
        "Decision: usar Prisma para ORM\nWhy: mejor DX",
        "Memo: stack - React 18, Next.js 14\nWhy: bootstrap",
    ]
    for i, trailers in enumerate(trailers_sets):
        git_cmd(["commit", "--allow-empty", "-m",
                 f"🧭 decision(core): choice {i}\n\n{trailers}"], repo)

    hook_path = os.path.join(HOOKS_DIR, "precompact-snapshot.py")
    if os.path.isfile(hook_path):
        rc, stdout, _ = run_cmd([sys.executable, hook_path], repo)
        if stdout:
            lines = stdout.strip().split("\n")
            assert len(lines) <= 18, f"Snapshot has {len(lines)} lines"


# RETIRADO (memoria v2, 2026-08-05): test_human_commits_not_blocked
# invocaba hooks/pre-validate-commit-trailers.py directamente por
# subprocess -- ese hook ya no existe en disco (confirmado: FileNotFoundError
# antes de este retiro). Su sucesor, hooks/customs.py, no distingue
# humano/Claude en absoluto -- vigila por si el proyecto tiene aduana
# encendida (config.json o primera nota real), no por quien firma el
# commit -- asi que este contrato concreto (humano vs Claude) no tiene
# equivalente 1:1 en el hook nuevo; no se inventa cobertura que no pidio
# nadie. La aduana en si ya esta cubierta de punta a punta en
# tests/memory/test_customs_hook.py.


def test_branch_context(tmp_path):
    """Branch change produces branch-aware context."""
    repo = make_installed_repo(tmp_path)

    # Remember the default branch name (may be "main" or "master")
    _, default_branch, _ = git_cmd(["branch", "--show-current"], repo)

    git_cmd(["commit", "--allow-empty", "-m",
             "🧭 decision(main): arch principal\n\nDecision: usar monolito\nWhy: simplicidad"], repo)

    git_cmd(["checkout", "-b", "feat/microservices"], repo)
    git_cmd(["commit", "--allow-empty", "-m",
             "🧭 decision(arch): cambiar arq\n\nDecision: usar microservicios\nWhy: escalabilidad"], repo)

    _, log_output, _ = git_cmd(["log", "-n", "5", "--pretty=format:%s%n%b"], repo)
    assert "microservicios" in log_output

    git_cmd(["checkout", default_branch], repo)
    _, log_output, _ = git_cmd(["log", "-n", "5", "--pretty=format:%s%n%b"], repo)
    assert "monolito" in log_output
    assert "microservicios" not in log_output


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
