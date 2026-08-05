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
import subprocess
import sys

import pytest

from conftest import (
    HOOKS_DIR, INSTALL, DOCTOR,
    PRE_HOOK, CLAUDE_ENV_VAR,
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


def run_hook_from_cache(hook_name, commit_msg, cwd, env_extra=None):
    """Run a hook script from the plugin source (cache) and return (rc, stdout, stderr)."""
    hook_path = os.path.join(HOOKS_DIR, hook_name)
    if not os.path.isfile(hook_path):
        return 1, "", f"hook not found: {hook_path}"
    env = {CLAUDE_ENV_VAR: "1"}
    if env_extra:
        env.update(env_extra)
    return run_cmd([sys.executable, hook_path, commit_msg], cwd, env=env)


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


def test_session_with_trailers(tmp_path):
    """Pre-hook does not block a normal session commit (hook runs from plugin cache).

    NOTE (2026-07-25): this test used to also invoke
    post-validate-commit-trailers.py after the commit — that hook was
    deleted outright (its validate_trailers() was dead code in the
    wrapper's path; see test_memo_category_deadend_contract.py's retirement
    note for the full history). Trailer CONTENT validation now lives in
    bin/git-memory-commit.py itself (test_wrapper_trailer_content_validation_contract.py)
    rather than in a PostToolUse hook, so there is no live post-hook
    behavior left to redirect this test's second half toward.
    """
    repo = make_installed_repo(tmp_path)

    write_file(repo, "src/main.py", "print('hello')")
    git_cmd(["add", "-A"], repo)

    msg = "✨ feat(core): add main\n\nWhy: initial implementation\nTouched: src/main.py"
    write_file(repo, ".git/COMMIT_EDITMSG", msg)
    msg_file = os.path.join(repo, ".git", "COMMIT_EDITMSG")

    rc, _, _ = run_hook_from_cache("pre-validate-commit-trailers.py", msg_file, repo)
    assert rc == 0

    git_cmd(["commit", "-m", msg], repo)


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


def test_human_commits_not_blocked(tmp_path):
    """Human commits without trailers should not be blocked (hook from cache)."""
    repo = make_installed_repo(tmp_path)

    hook_input = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": 'git commit -m "fix: quick hotfix"'},
    })
    hook_path = os.path.join(HOOKS_DIR, "pre-validate-commit-trailers.py")

    # Without CLAUDECODE → allowed. The variable is removed explicitly, not
    # merely left unset: run_cmd/subprocess inherit the ambient environment,
    # and inside Claude Code CLAUDECODE really is exported (2026-07-29).
    env_no_claude = {k: v for k, v in os.environ.items() if k != CLAUDE_ENV_VAR}
    result = subprocess.run(
        [sys.executable, hook_path],
        input=hook_input, capture_output=True, text=True, encoding='utf-8', errors='replace',
        cwd=repo, timeout=15, env=env_no_claude,
    )
    assert result.returncode == 0, (
        f"human commit must pass. stderr={result.stderr!r}")

    # With CLAUDECODE → blocked
    result = subprocess.run(
        [sys.executable, hook_path],
        input=hook_input, capture_output=True, text=True, encoding='utf-8', errors='replace',
        cwd=repo, timeout=15, env={**env_no_claude, CLAUDE_ENV_VAR: "1"},
    )
    assert result.returncode == 2, (
        f"Claude's direct git commit must be blocked. stderr={result.stderr!r}")


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
