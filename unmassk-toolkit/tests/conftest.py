"""Shared fixtures and helpers for git-memory tests.

Nota sobre importabilidad de bin.release y módulos vecinos:
esto NO lo hace pytest (pytest no añade el rootdir a sys.path por su
cuenta). Cuando test_release.py se invoca como `python3 -m pytest ...`
desde la raíz del repo, es `python -m` quien inserta el cwd en
sys.path[0] -- ese cwd resulta ser la raíz, y como bin/ no tiene
__init__.py, Python lo trata como namespace package, permitiendo
"import bin.release" / "import bin.release_helpers" sin
sys.path.insert explícito. Esto se rompe con cualquier otra forma de
invocar pytest (cwd distinto, entry point `pytest` sin `-m`) -- ver
issue #50. Por eso test_release.py inserta _REPO_ROOT en sys.path de
forma explícita en vez de depender de este efecto colateral.
"""

import json
import os
import subprocess
import sys

import pytest

SOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(SOURCE_ROOT, "bin")
LIB_DIR = os.path.join(SOURCE_ROOT, "lib")

# Make lib/ importable for unit tests of shared modules
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)
HOOKS_DIR = os.path.join(SOURCE_ROOT, "hooks")

# Hook / script paths (all in plugin source, not project root)
PRECOMPACT_SCRIPT = os.path.join(HOOKS_DIR, "precompact-snapshot.py")
PRE_HOOK = os.path.join(HOOKS_DIR, "pre-validate-commit-trailers.py")
POST_HOOK = os.path.join(HOOKS_DIR, "post-validate-commit-trailers.py")

DOCTOR = os.path.join(BIN_DIR, "git-memory-doctor.py")
INSTALL = os.path.join(BIN_DIR, "git-memory-install.py")
REPAIR = os.path.join(BIN_DIR, "git-memory-repair.py")
UNINSTALL = os.path.join(BIN_DIR, "git-memory-uninstall.py")
UPGRADE = os.path.join(BIN_DIR, "git-memory-upgrade.py")
BOOTSTRAP = os.path.join(BIN_DIR, "git-memory-bootstrap.py")


# ── Helpers ────────────────────────────────────────────────────────────


def run_cmd(args, cwd, timeout=30, env=None, input_text=None):
    """Run a command and return (returncode, stdout, stderr)."""
    merged = {**os.environ, **(env or {})}
    result = subprocess.run(
        args, capture_output=True, text=True,
        cwd=cwd, timeout=timeout, env=merged, input=input_text,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def git_cmd(args, cwd, env=None):
    """Run a git command. args can be a list or a space-separated string."""
    if isinstance(args, str):
        args = args.split()
    return run_cmd(["git"] + args, cwd, env=env)


def write_file(repo, path, content):
    """Write a file inside a repo directory."""
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)


def run_script(script_path, cwd, extra_args=None, timeout=30, env=None, input_text=None):
    """Run a Python script. Returns (returncode, stdout, stderr)."""
    args = [sys.executable, script_path] + (extra_args or [])
    return run_cmd(args, cwd, timeout=timeout, env=env, input_text=input_text)


def run_doctor_json(cwd):
    """Run doctor --json and return (parsed_dict, returncode)."""
    rc, out, _ = run_script(DOCTOR, cwd, ["--json"])
    try:
        return json.loads(out), rc
    except json.JSONDecodeError:
        return {"status": "error", "checks": []}, rc


def neutralize_needs_upgrade_check1(repo):
    """Patch CLAUDE.md's managed block so hooks/user-prompt-memory-check.py's
    needs_upgrade() Check 1 ("python3 bin/" in block or "Context Checkpoint
    Commits" not in block) is definitively False.

    Context: a freshly installed repo's CLAUDE.md managed block does not
    contain the literal string "Context Checkpoint Commits" (that text lives
    in the full skill payload, not the minimal installed snippet), so Check 1
    fires True on every real install. Any test that wants to exercise Check 2
    (manifest.version / semver, or — see BUG M — the symlink guard on the
    manifest read) must neutralize Check 1 first, or the test never reaches
    the code path it claims to cover. Originally identified in
    test_needs_upgrade_semver.py's make_semver_test_repo(); extracted here so
    other test modules (e.g. test_security_regression.py) can reuse the same
    patch instead of re-deriving it.

    No-op (returns silently) if CLAUDE.md or the managed block markers are
    missing — callers that rely on this should have already installed.
    """
    claude_md_path = os.path.join(repo, "CLAUDE.md")
    if not os.path.isfile(claude_md_path):
        return
    with open(claude_md_path) as f:
        content = f.read()

    begin = content.find("BEGIN unmassk-toolkit")
    end = content.find("END unmassk-toolkit")
    if begin == -1 or end == -1:
        return

    block = content[begin:end]
    patched_block = block

    # Ensure old-style marker is NOT present (it would trigger upgrade).
    patched_block = patched_block.replace("python3 bin/", "")

    # Ensure the required string IS present (its absence triggers upgrade).
    if "Context Checkpoint Commits" not in patched_block:
        patched_block = patched_block + "\nContext Checkpoint Commits\n"

    content = content[:begin] + patched_block + content[end:]
    with open(claude_md_path, "w") as f:
        f.write(content)


def check_hook_msg(subject, cwd, trailers=None, as_claude=False):
    """Send a commit message to the pre-hook and return the exit code."""
    command = 'git commit -m "' + subject + '"'
    if trailers:
        command = command + ' -m "' + trailers + '"'
    payload = {"tool_input": {"command": command}}
    env = {}
    if as_claude:
        env["CLAUDE_CODE"] = "1"
    rc, _, _ = run_script(PRE_HOOK, cwd, env=env, input_text=json.dumps(payload))
    return rc


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary git repo with an initial commit."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


@pytest.fixture
def real_symlink_capable(tmp_path):
    """Skip the test using this fixture if the CURRENT environment cannot
    create real filesystem symlinks.

    Confirmed live on Windows dev boxes without Developer Mode /
    SeCreateSymbolicLinkPrivilege:
        os.symlink(...) -> OSError: [WinError 1314] El cliente no dispone
        de un privilegio requerido.

    The POSIX/anti-symlink guards under test rely on real filesystem
    symlink semantics (O_NOFOLLOW, os.path.islink(), directory-symlink
    traversal) that cannot be meaningfully mocked — mocking os.path.islink()
    would only prove the mock works, not that the guard itself still
    functions. A real symlink is the only honest way to test it, so when one
    cannot be created here, this reports an explicit skip rather than faking
    the result.

    Shared by test_crossplatform_symlink_guard.py and
    test_security_regression.py — single source of truth, auto-discovered
    via conftest.py (no import needed).
    """
    probe_target = tmp_path / "_symlink_probe_target.txt"
    probe_link = tmp_path / "_symlink_probe_link.txt"
    probe_target.write_text("probe")
    try:
        os.symlink(str(probe_target), str(probe_link))
    except OSError as e:
        pytest.skip(f"cannot create real symlinks in this environment: {e}")
    else:
        os.remove(str(probe_link))


@pytest.fixture
def installed_repo(tmp_path):
    """Create a temporary git repo with git-memory installed."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    run_script(INSTALL, repo, ["--auto"])
    return repo
