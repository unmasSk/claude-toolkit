"""
DEUDA.md punto 5 (abierto desde 2026-08-02): el vigilante repo-vs-cache no
entra en subcarpetas.

`cache_sync_check._dir_fingerprint()` solo mira las entradas que son
ficheros directos de `hooks/`, `lib/`, `bin/` y `agents/` -- cualquier
entrada que sea un directorio se descarta con
`if not os.path.isfile(full): continue`, sin recursar en ella.

Eso era un limite conocido y sin consecuencia mientras esas cuatro carpetas
eran planas. Con el sistema de memoria v2 deja de serlo: sus modulos viven
enteros bajo `lib/memory/` (varios ficheros) y sus scripts bajo
`bin/memory/`. Tal como esta el codigo hoy, un edit en cualquiera de esos
dos arboles cambia el contenido real pero el vigilante sigue diciendo "en
sincronia", porque nunca llega a mirar dentro de `memory/`.

Este fichero prueba EXCLUSIVAMENTE ese efecto observable -- que un fichero
dentro de una subcarpeta de una de las cuatro carpetas vigiladas SI se nota
cuando difiere entre repo y cache -- via la superficie publica
(`check_repo_cache_sync()` / `count_repo_cache_drift()`), nunca contra
`_dir_fingerprint()` por dentro: esa es una funcion privada que Ultron
puede reescribir (por ejemplo con `os.walk`) sin que el contrato observable
cambie.

El contrato base de `check_repo_cache_sync()` / `count_repo_cache_drift()`
(fail-open, resumen "+N mas", empate de version por semver, etc.) ya esta
cubierto por completo en test_doctor_derived_expectations.py -- no se
repite aqui.
"""

import os
import sys

from conftest import LIB_DIR

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import cache_sync_check  # noqa: E402


def _build(tmp_path, monkeypatch, repo_files, cache_files, version="1.0.0"):
    """Same fixture shape as TestRepoCacheSyncDetectsDrift._build() in
    test_doctor_derived_expectations.py -- duplicated on purpose so this
    file reads standalone, exactly like that file's own note on
    `_build_drift_fixture()` duplicating rather than sharing across
    classes."""
    project = tmp_path / "toolkit-repo"
    cache = tmp_path / "cache"
    repo_plugin = project / cache_sync_check.PLUGIN_DIR_NAME
    cache_plugin = cache / cache_sync_check.PLUGIN_DIR_NAME / version
    for base, files in ((repo_plugin, repo_files), (cache_plugin, cache_files)):
        for rel, text in files.items():
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(cache_sync_check, "CACHE_BASE_DIR", str(cache))
    return str(project)


class TestNestedSubdirDriftIsDetected:
    """The exact case DEUDA #5 is written against: a v2 module edited
    inside lib/memory/ or a v2 script edited inside bin/memory/."""

    def test_edited_file_inside_lib_memory_is_detected_as_drift(
        self, tmp_path, monkeypatch
    ):
        project = _build(
            tmp_path, monkeypatch,
            {"lib/memory/vocabulary.py": "VERSION = 2\n"},
            {"lib/memory/vocabulary.py": "VERSION = 1\n"},
        )

        drift = cache_sync_check.check_repo_cache_sync(project)

        assert drift, (
            "an edit inside lib/memory/ must be reported as drift -- "
            f"got {drift!r} (empty means the watcher never looked inside "
            "the subdirectory)"
        )
        assert any("vocabulary.py" in line for line in drift), drift

    def test_edited_file_inside_bin_memory_is_detected_as_drift(
        self, tmp_path, monkeypatch
    ):
        project = _build(
            tmp_path, monkeypatch,
            {"bin/memory/note.py": "print('new')\n"},
            {"bin/memory/note.py": "print('old')\n"},
        )

        drift = cache_sync_check.check_repo_cache_sync(project)

        assert drift, (
            "an edit inside bin/memory/ must be reported as drift, "
            f"got {drift!r}"
        )
        assert any("note.py" in line for line in drift), drift

    def test_new_file_only_in_repo_inside_nested_subdir_counts_as_drift(
        self, tmp_path, monkeypatch
    ):
        """Mirrors the flat-directory case already proven at top level
        (test_a_file_only_in_the_repo_counts_as_drift) -- a brand new
        module added under lib/memory/ and never installed must count
        too, not just an edited one."""
        project = _build(
            tmp_path, monkeypatch,
            {"lib/memory/new_module.py": "x = 1\n"},
            {"lib/memory/other.py": "y = 1\n"},
        )

        drift = cache_sync_check.check_repo_cache_sync(project)

        assert drift is not None, (
            "cache_plugin exists (lib/memory/other.py was written on the "
            "cache side) -- the check must apply, not fail open"
        )
        assert any("new_module.py" in line for line in drift), drift

    def test_nested_subdir_is_the_only_content_of_its_parent(
        self, tmp_path, monkeypatch
    ):
        """The parent (lib/) has NO flat files of its own -- every real
        source file lives one level down, under memory/. This is the
        actual v2 shape (lib/memory/ holds 31 files, bin/memory/ holds 10
        scripts) and it must not silently collapse to an empty, "nothing
        to compare" fingerprint just because the parent directory itself
        has nothing directly inside it."""
        project = _build(
            tmp_path, monkeypatch,
            {"lib/memory/vocabulary.py": "new\n"},
            {"lib/memory/vocabulary.py": "old\n"},
        )

        count, drift = cache_sync_check.count_repo_cache_drift(project)

        assert count >= 1, (
            "DEUDA #5's own verification: touch a file under lib/memory/ "
            f"and the boot count must rise. Got count={count}, drift={drift!r}"
        )

    def test_count_repo_cache_drift_count_rises_for_nested_edit(
        self, tmp_path, monkeypatch
    ):
        """DEUDA #5's literal verification command: "tocar un fichero de
        lib/memory/ y comprobar que el conteo del arranque sube". This
        checks the actual integer the boot banner reads, not just the
        description list."""
        identical = {"lib/top_level.py": "same\n"}
        project = _build(
            tmp_path, monkeypatch,
            {**identical, "lib/memory/vocabulary.py": "new\n"},
            {**identical, "lib/memory/vocabulary.py": "old\n"},
        )

        count, _drift = cache_sync_check.count_repo_cache_drift(project)

        assert count >= 1, (
            f"a nested edit must move the count above zero, got {count}"
        )


class TestNestedSubdirEdgeCases:
    """Edge cases around the same gap: no false alarms once recursion
    exists, and __pycache__ stays excluded at any depth."""

    def test_identical_nested_trees_report_no_drift(self, tmp_path, monkeypatch):
        """Control case: two byte-identical nested trees must never be
        reported as drift, however the fix recurses."""
        files = {"lib/memory/vocabulary.py": "same\n"}
        project = _build(tmp_path, monkeypatch, files, dict(files))

        assert cache_sync_check.check_repo_cache_sync(project) == []

    def test_pycache_inside_nested_subdir_is_still_ignored(
        self, tmp_path, monkeypatch
    ):
        """__pycache__ is excluded at the top level already
        (test_pycache_is_ignored); once the watcher recurses, a
        __pycache__ born inside lib/memory/ must be excluded the same
        way, or every run would cry wolf over a regenerated .pyc that
        was never a source edit."""
        project = _build(
            tmp_path, monkeypatch,
            {
                "lib/memory/same.py": "x = 1\n",
                "lib/memory/__pycache__/same.cpython-99.pyc": "AAA",
            },
            {"lib/memory/same.py": "x = 1\n"},
        )

        assert cache_sync_check.check_repo_cache_sync(project) == []
