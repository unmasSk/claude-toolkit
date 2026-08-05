"""
Scope-mapping tests for suggest_scope_from_paths().

Retirement note (2026-08-02): every test in this file that ran
bin/git-memory-bootstrap.py (test_empty_project, test_nodejs_typescript,
test_python_project, test_monorepo, test_commitlint_detected,
test_memory_already_installed, test_multiple_ecosystems,
test_silent_exit_code) was removed. That script no longer exists on disk
-- docs/memoria-v2/PLAN-CONSTRUCCION.md §5.4 lists it among the five
scripts that "ya estaban muertos" ("only reachable via a shell alias that
is never installed -- no need to plan its retirement"). Retired per §9.3
("borrar los tests de cada pieza retirada, a la vez que la pieza").

What survives here (test_suggest_scope_*) tests suggest_scope_from_paths()
in lib/parsing.py directly -- a real, still-live function with no
dependency on the retired script.
"""

import sys

import pytest


# ── Scope mapping (unit tests, no git needed) ───────────────────────────

def test_suggest_scope_single_match():
    """All files in one scope → returns that scope."""
    from parsing import suggest_scope_from_paths

    scope_map = {"apps/web": "web", "apps/api": "api", "packages/ui": "ui"}
    files = ["apps/web/src/index.ts", "apps/web/src/app.tsx"]
    assert suggest_scope_from_paths(files, scope_map) == "web"


def test_suggest_scope_ambiguous():
    """Files across multiple scopes → returns None."""
    from parsing import suggest_scope_from_paths

    scope_map = {"apps/web": "web", "apps/api": "api"}
    files = ["apps/web/src/index.ts", "apps/api/src/server.ts"]
    assert suggest_scope_from_paths(files, scope_map) is None


def test_suggest_scope_root_files_ignored():
    """Root-level files (outside any scope) are ignored."""
    from parsing import suggest_scope_from_paths

    scope_map = {"apps/web": "web", "packages/ui": "ui"}
    files = ["apps/web/src/index.ts", "README.md", ".gitignore"]
    assert suggest_scope_from_paths(files, scope_map) == "web"


def test_suggest_scope_empty():
    """Empty inputs → None."""
    from parsing import suggest_scope_from_paths

    assert suggest_scope_from_paths([], {"a": "b"}) is None
    assert suggest_scope_from_paths(["x/y"], {}) is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
