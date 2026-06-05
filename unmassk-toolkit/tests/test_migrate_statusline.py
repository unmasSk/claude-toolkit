"""
Tests for _migrate_stale_context_writer_statusline() in session-start-boot.

Covers:
  1. context-writer statusLine + backup present → restores original command
  2. context-writer statusLine + no backup → removes statusLine key entirely
  3. Unrelated statusLine (not context-writer) → settings unchanged
  4. Missing settings.json → no exception (idempotent)
  5. Backup file deleted after restore (idempotent second run)
"""

import importlib.util
import json
import os
import sys
import types

import pytest

HOOKS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")


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

    # Stub git_helpers and parsing to avoid side effects during import
    for stub_name in ("git_helpers", "parsing", "version"):
        if stub_name not in sys.modules:
            stub = types.ModuleType(stub_name)
            if stub_name == "git_helpers":
                stub.ensure_gitignore = lambda *a, **kw: None
                stub._GENERATED_JSONS = []
                stub.run_git = lambda *a, **kw: (1, "")
                stub.is_git_repo = lambda: False
            elif stub_name == "parsing":
                stub.scan_trailers_memory = lambda *a, **kw: {}
                stub.normalize = lambda s: s.lower().strip()
                stub.parse_scope = lambda *a, **kw: None
                stub.suggest_scope_from_paths = lambda *a, **kw: None
            elif stub_name == "version":
                stub.VERSION = "test"
            sys.modules[stub_name] = stub

    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = saved

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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
