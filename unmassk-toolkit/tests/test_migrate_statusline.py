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
     sequence _load_migrate_fn() runs here freezes lib/boot_memory.py and
     lib/boot_render.py's module-level `run_git` name to the stub forever,
     for the rest of the process.

     Issue #63 (boot simplification, point 4): lib/boot_migrations.py's own
     probe of this same regression was removed. It targeted
     _migrate_untrack_generated_jsons(), which is now retired from the boot
     path (pre-v1.0.0, no other caller, no upgrade-path duplicate) — the
     only function left in lib/boot_migrations.py
     (_migrate_stale_context_writer_statusline) never imports git_helpers
     at all, so there is no module-level `run_git` binding left in that
     module for a stub-and-restore sequence to freeze.
"""

import importlib.util
import json
import os
import sys
import types

import pytest

from conftest import git_cmd

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

    # Stub git_helpers, parsing, and version to avoid side effects during import.
    # Snapshot each name's previous value (or sentinel if absent) so the finally
    # block can fully restore sys.modules — preventing stub leakage into later tests.
    _ABSENT = object()
    saved_modules = {}
    # Dante (issue #63 audit, 2026-07-11): also snapshot the FULL set of module
    # names present before stubbing. hooks/session-start-boot.py now does
    # `from upgrade_check import trigger_auto_upgrade_if_needed` at module
    # level (issue #63, point 2) -- lib/upgrade_check.py's own module-level
    # `from version import VERSION as PLUGIN_VERSION` runs DURING this stub
    # window if upgrade_check hasn't been imported anywhere yet in the process,
    # permanently freezing upgrade_check.PLUGIN_VERSION to the stub's "test"
    # string in the REAL, stably-cached sys.modules["upgrade_check"] entry --
    # same contamination class as the git_helpers.run_git freeze this file's
    # own TestSysModulesContaminationRegression documents below, just reached
    # through a transitive-import surface that didn't exist when the explicit
    # 3-name stub list was written. Confirmed live: this broke
    # test_needs_upgrade_semver.py's real-PLUGIN_VERSION assertions whenever it
    # ran in the same pytest session after this function. Evicting every
    # module newly present in sys.modules after this call (below) closes the
    # whole class generically, not just this one instance.
    pre_existing_module_names = set(sys.modules.keys())
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
        # Evict every module that is newly present in sys.modules after this
        # call and was not one of the 3 explicit stub names above (see the
        # comment on pre_existing_module_names) -- forces a clean, real
        # re-import for anything (like upgrade_check) that got transitively
        # first-imported while a dependency of ITS OWN was stubbed.
        for _name in list(sys.modules.keys()):
            if _name not in pre_existing_module_names and _name not in saved_modules:
                sys.modules.pop(_name, None)

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


# _run_after_stub_contamination()/_last_json_line() (helpers only
# TestSysModulesContaminationRegression used) were removed along with it —
# see the retirement note directly below.
#
# RETIRADO (PLAN-CONSTRUCCION.md paso 9.3): TestSysModulesContaminationRegression
# probaba que el mismo secuestro de sys.modules que _load_migrate_fn() aplica
# en este fichero no dejaba `run_git` congelado en lib/boot_memory.py y
# lib/boot_render.py. lib/boot_memory.py ya no existe en disco (eliminado con
# el resto del sistema de memoria v1). lib/boot_render.py existe pero ya NO
# importa git_helpers/run_git a nivel de modulo -- confirmado leyendo el
# fichero completo, solo importa cache_sync_check/boot_checks/version -- asi
# que no queda ningun nombre `run_git` de modulo que este secuestro pudiera
# congelar en el. `get_timeline()`, que el segundo test llamaba como
# `boot_render.get_timeline()`, tampoco existe en ningun sitio de lib/ hoy
# (grep sin resultados) -- ni siquiera en boot_git_checks.py, pese a que su
# propio comentario y el de test_boot_git_checks.py todavia la citan como
# viva; drift de comentarios, no codigo, fuera del alcance de este pase.
#
# El patron que este test protegia (imports diferidos a nivel de funcion,
# no de modulo) SI sigue vivo hoy: cada uno de los 5 sitios de
# `from git_helpers import run_git` en lib/boot_git_checks.py esta dentro
# del cuerpo de una funcion, nunca a nivel de modulo -- exactamente la
# forma que este test class documentaba como el estado "GREEN, arreglado".
# No hay un objetivo vivo equivalente al que redirigir estos dos tests sin
# inventar cobertura nueva no pedida en esta tarea.


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
