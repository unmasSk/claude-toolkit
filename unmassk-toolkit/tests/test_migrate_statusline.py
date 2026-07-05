"""
Tests for _migrate_stale_context_writer_statusline() in session-start-boot.

Covers:
  1. context-writer statusLine + backup present → restores original command
  2. context-writer statusLine + no backup → removes statusLine key entirely
  3. Unrelated statusLine (not context-writer) → settings unchanged
  4. Missing settings.json → no exception (idempotent)
  5. Backup file deleted after restore (idempotent second run)
  6. Cerberus-confirmed sys.modules contamination regression (see
     TestSysModulesContaminationRegression below): the exact stub-and-restore
     sequence _load_migrate_fn() runs here freezes lib/boot_memory.py,
     lib/boot_render.py, and lib/boot_migrations.py's module-level `run_git`
     name to the stub forever, for the rest of the process.
"""

import importlib.util
import json
import os
import subprocess
import sys
import types

import pytest

from conftest import git_cmd

HOOKS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
THIS_FILE = os.path.abspath(__file__)


def _load_migrate_fn(fake_home: str):
    """Load _migrate_stale_context_writer_statusline with a patched expanduser.

    Returns the function bound to fake_home without touching the real
    ~/.claude/settings.json.
    """
    # We import the module fresh each time to pick up a new expanduser.
    # Because the module name contains hyphens we load it via spec.
    spec = importlib.util.spec_from_file_location(
        "session_start_boot",
        os.path.join(HOOKS_DIR, "session-start-boot.py"),
    )
    mod = importlib.util.module_from_spec(spec)

    # Patch sys.path so the module can find its lib/ dependencies
    saved = sys.path[:]
    if LIB_DIR not in sys.path:
        sys.path.insert(0, LIB_DIR)

    # Stub git_helpers, parsing, and version to avoid side effects during import.
    # Snapshot each name's previous value (or sentinel if absent) so the finally
    # block can fully restore sys.modules — preventing stub leakage into later tests.
    _ABSENT = object()
    saved_modules = {}
    for stub_name in ("git_helpers", "parsing", "version"):
        saved_modules[stub_name] = sys.modules.get(stub_name, _ABSENT)
        stub = types.ModuleType(stub_name)
        if stub_name == "git_helpers":
            stub.ensure_gitignore = lambda *a, **kw: None
            stub._GENERATED_JSONS = []
            stub.run_git = lambda *a, **kw: (1, "")
            stub.is_git_repo = lambda: False
            stub.GIT_TIMEOUT = 10
            stub.commits_since_last_consolidation = lambda *a, **kw: 0
        elif stub_name == "parsing":
            stub.scan_trailers_memory = lambda *a, **kw: {}
            stub.normalize = lambda s: s.lower().strip()
            stub.parse_scope = lambda *a, **kw: None
            stub.suggest_scope_from_paths = lambda *a, **kw: None
            stub.sanitize_trailer_value = lambda s: s
        elif stub_name == "version":
            stub.VERSION = "test"
        sys.modules[stub_name] = stub

    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = saved
        # Restore sys.modules to its pre-stub state for every name we touched.
        for stub_name, prev in saved_modules.items():
            if prev is _ABSENT:
                sys.modules.pop(stub_name, None)
            else:
                sys.modules[stub_name] = prev

    # Patch expanduser on the module's copy of os.path
    real_expanduser = mod.os.path.expanduser
    mod.os.path.expanduser = lambda p: fake_home if p == "~" else real_expanduser(p)

    return mod._migrate_stale_context_writer_statusline


# ── Helpers ───────────────────────────────────────────────────────────


def _write_settings(claude_dir: str, data: dict) -> str:
    path = os.path.join(claude_dir, "settings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def _read_settings(claude_dir: str) -> dict:
    path = os.path.join(claude_dir, "settings.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_backup(claude_dir: str, content: str) -> str:
    path = os.path.join(claude_dir, ".git-memory-original-statusline")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ── Tests ──────────────────────────────────────────────────────────────


def test_restores_from_backup(tmp_path):
    """context-writer statusLine + backup file → full statusLine structure restored from backup."""
    home = str(tmp_path / "home")
    claude_dir = os.path.join(home, ".claude")
    os.makedirs(claude_dir)

    _write_settings(claude_dir, {
        "statusLine": {"command": "/path/to/context-writer.py"},
        "other": "value",
    })
    _write_backup(claude_dir, "/usr/local/bin/my-statusline.sh")

    migrate = _load_migrate_fn(home)
    migrate()

    settings = _read_settings(claude_dir)
    restored = settings["statusLine"]
    assert restored["command"] == "/usr/local/bin/my-statusline.sh"
    assert restored["type"] == "command"
    assert restored["padding"] == 0
    assert settings["other"] == "value"
    assert not os.path.exists(os.path.join(claude_dir, ".git-memory-original-statusline"))


def test_removes_key_without_backup(tmp_path):
    """context-writer statusLine + no backup file → statusLine key is removed."""
    home = str(tmp_path / "home")
    claude_dir = os.path.join(home, ".claude")
    os.makedirs(claude_dir)

    _write_settings(claude_dir, {
        "statusLine": {"command": "/path/to/context-writer.py"},
        "other": "value",
    })
    # No backup file

    migrate = _load_migrate_fn(home)
    migrate()

    settings = _read_settings(claude_dir)
    assert "statusLine" not in settings
    assert settings["other"] == "value"


def test_unrelated_statusline_untouched(tmp_path):
    """statusLine not referencing context-writer → settings are not modified."""
    home = str(tmp_path / "home")
    claude_dir = os.path.join(home, ".claude")
    os.makedirs(claude_dir)

    original = {
        "statusLine": {"command": "/usr/local/bin/my-own-statusline.sh"},
        "other": "value",
    }
    _write_settings(claude_dir, original)

    migrate = _load_migrate_fn(home)
    migrate()

    assert _read_settings(claude_dir) == original


def test_idempotent_no_settings_file(tmp_path):
    """Missing settings.json → no exception, no file created."""
    home = str(tmp_path / "home")
    claude_dir = os.path.join(home, ".claude")
    os.makedirs(claude_dir)
    # No settings.json

    migrate = _load_migrate_fn(home)
    migrate()  # Must not raise

    assert not os.path.exists(os.path.join(claude_dir, "settings.json"))


def test_backup_deleted_after_restore(tmp_path):
    """After restore, backup file is deleted; second run is a no-op."""
    home = str(tmp_path / "home")
    claude_dir = os.path.join(home, ".claude")
    os.makedirs(claude_dir)

    _write_settings(claude_dir, {
        "statusLine": {"command": "/path/to/context-writer.py"},
    })
    backup_path = _write_backup(claude_dir, "/usr/local/bin/my-statusline.sh")

    migrate = _load_migrate_fn(home)
    migrate()

    assert not os.path.exists(backup_path)

    # Second run: statusLine now holds the restored value, not context-writer → no-op
    migrate()
    settings = _read_settings(claude_dir)
    assert settings["statusLine"]["command"] == "/usr/local/bin/my-statusline.sh"


# ── sys.modules contamination regression (Cerberus, session 2026-07-05) ──
#
# lib/boot_memory.py, lib/boot_render.py, and lib/boot_migrations.py all do
# `from git_helpers import ...` at MODULE level. The `parsing` imports right
# next to them in boot_memory.py are deliberately deferred into each
# function body instead, specifically because this same test file replaces
# sys.modules["parsing"]/["git_helpers"]/["version"] with stubs and restores
# them in a `finally` block — a module-level binding captured while the stub
# is installed survives the restore, because rebinding sys.modules doesn't
# touch names already bound in another module's namespace.
#
# `_load_migrate_fn()` above triggers exactly this: it stubs git_helpers,
# then execs hooks/session-start-boot.py, whose module-level
# `from boot_memory import (...)` causes the FIRST-EVER `import boot_memory`
# in the process (also pulling in boot_migrations and boot_render the same
# way). Each of those three modules' own `from git_helpers import ...`
# line then binds `run_git` to the STUB's `lambda *a, **kw: (1, "")` —
# permanently, for the rest of the process — even after the `finally` block
# restores sys.modules["git_helpers"] to the real module.
#
# Each probe below runs the exact stub-and-restore sequence in a FRESH
# subprocess (so the result never depends on whether some other test file
# already did a real `import boot_memory` earlier in the same pytest
# session — the bug only bites on the very first import), then exercises a
# real function through its public behavior (not by asserting on the
# `run_git` attribute directly, since the eventual fix — deferred imports,
# mirroring the `parsing` pattern — may remove that module-level name
# entirely rather than merely rebind it).


def _run_after_stub_contamination(fake_home: str, repo: str, action_code: str) -> subprocess.CompletedProcess:
    """Reproduce _load_migrate_fn()'s stub-and-restore sequence, then run
    `action_code` (a Python source string) in the SAME fresh subprocess,
    with CWD set to `repo` and `boot_memory`/`boot_render`/`boot_migrations`
    already import-cached (contaminated or not) from that sequence.
    """
    code = f"""
import sys, os, json, importlib.util

sys.path.insert(0, {repr(LIB_DIR)})
sys.path.insert(0, {repr(os.path.dirname(THIS_FILE))})

spec = importlib.util.spec_from_file_location("tms_probe", {repr(THIS_FILE)})
tms_probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tms_probe)

migrate = tms_probe._load_migrate_fn({repr(fake_home)})
migrate()

os.chdir({repr(repo)})

{action_code}
"""
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=30,
    )


def _last_json_line(stdout: str) -> dict:
    return json.loads(stdout.strip().splitlines()[-1])


class TestSysModulesContaminationRegression:
    """RED today: run_git is frozen to the stub in all three modules, so
    every real function below silently reports "nothing here" regardless of
    the actual repository state. GREEN after the fix (deferred imports):
    each function reflects the real repository state again.
    """

    def test_boot_memory_extract_memory_not_frozen_after_stub_contamination(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["config", "user.email", "test@test.com"], repo)
        git_cmd(["config", "user.name", "Test"], repo)
        git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
        marker = "CONTAMINATION-DECISION-MARKER-58213"
        git_cmd(["commit", "--allow-empty", "-m",
                 f"\U0001F9ED decision(contamtest): probe\n\nDecision: {marker}"], repo)

        home = str(tmp_path / "home")
        os.makedirs(os.path.join(home, ".claude"))

        action = f"""
import boot_memory
result = boot_memory.extract_memory()
decisions = result.get("decisions", [])
found = any({marker!r} in text for _, text, _ in decisions)
print(json.dumps({{"found": found, "decisions": decisions}}))
"""
        result = _run_after_stub_contamination(home, repo, action)
        assert result.returncode == 0, (
            f"probe subprocess crashed: rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        payload = _last_json_line(result.stdout)
        assert payload["found"], (
            "boot_memory.extract_memory() did not see the real commit after "
            "the sys.modules stub-and-restore sequence ran once in this "
            "process — run_git is frozen to the stub's (1, \"\"), proving "
            f"module-level contamination. decisions={payload['decisions']!r}"
        )

    def test_boot_render_get_timeline_not_frozen_after_stub_contamination(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["config", "user.email", "test@test.com"], repo)
        git_cmd(["config", "user.name", "Test"], repo)
        git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
        marker = "CONTAMINATION-TIMELINE-MARKER-77123"
        git_cmd(["commit", "--allow-empty", "-m",
                 f"✨ feat(contamtest): {marker}"], repo)

        home = str(tmp_path / "home")
        os.makedirs(os.path.join(home, ".claude"))

        action = f"""
import boot_render
timeline = boot_render.get_timeline(10)
found = any({marker!r} in line for line in timeline)
print(json.dumps({{"found": found, "timeline": timeline}}))
"""
        result = _run_after_stub_contamination(home, repo, action)
        assert result.returncode == 0, (
            f"probe subprocess crashed: rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        payload = _last_json_line(result.stdout)
        assert payload["found"], (
            "boot_render.get_timeline() did not see the real commit after "
            "the sys.modules stub-and-restore sequence ran once in this "
            "process — run_git is frozen to the stub's (1, \"\"), proving "
            f"module-level contamination. timeline={payload['timeline']!r}"
        )

    def test_boot_migrations_untrack_generated_jsons_not_frozen_after_stub_contamination(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["config", "user.email", "test@test.com"], repo)
        git_cmd(["config", "user.name", "Test"], repo)
        git_cmd(["commit", "--allow-empty", "-m", "init"], repo)

        generated_dir = os.path.join(repo, ".claude", ".unmassk")
        os.makedirs(generated_dir)
        with open(os.path.join(generated_dir, "foo.json"), "w") as f:
            f.write("{}")
        git_cmd(["add", ".claude/.unmassk/foo.json"], repo)
        git_cmd(["commit", "-m", "add generated json (legacy tracked install)"], repo)

        # Sanity check: the file really is tracked before the probe runs.
        rc, _, _ = git_cmd(["ls-files", "--error-unmatch", ".claude/.unmassk/foo.json"], repo)
        assert rc == 0, "sanity check failed: fixture file must be tracked before the migration runs"

        home = str(tmp_path / "home")
        os.makedirs(os.path.join(home, ".claude"))

        action = f"""
import boot_migrations
boot_migrations._migrate_untrack_generated_jsons({repr(repo)})
print(json.dumps({{"done": True}}))
"""
        result = _run_after_stub_contamination(home, repo, action)
        assert result.returncode == 0, (
            f"probe subprocess crashed: rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        # Assertion happens back in THIS (uncontaminated) process/repo state,
        # via a plain git call — independent of whatever run_git was bound
        # to inside the probe subprocess.
        rc, _, _ = git_cmd(["ls-files", "--error-unmatch", ".claude/.unmassk/foo.json"], repo)
        assert rc != 0, (
            "the tracked generated-JSON file was NOT untracked by "
            "_migrate_untrack_generated_jsons() — proving "
            "boot_migrations.run_git was frozen to the sys.modules stub's "
            "(1, \"\") and the real `git ls-files`/`git rm --cached` calls "
            "never actually ran against the repository"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
