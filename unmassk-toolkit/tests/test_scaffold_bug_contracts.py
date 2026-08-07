"""RED contract tests for scaffold.py (unmassk-scaffolding).

Cerberus read `skills/unmassk-scaffolding/scripts/scaffold.py` (3541 lines,
zero prior tests -- confirmed via `gitmem search scaffold.py`, zero zones)
end to end on 2026-08-06 and found four ways the scaffolder can break
*itself*: write output a real downstream parser rejects, silently ignore an
option it advertised as valid, make a real generator branch unreachable from
its own CLI, and let a bad project name escape the destination directory it
was told to use. This project has no external-attacker threat model (see
CLAUDE.md) -- these are all "the system corrupting or losing its own output",
which is exactly what is in scope here.

Every assertion below compares two independently produced things: the real
script's real output against a real, official parser (`tomllib`, `json`,
Node itself for the JS site), or two real runs of the same script against
each other. None of it is a hand-typed expected value (unmassk-standards
S34). These tests are written test-first: they are expected to FAIL today for
the reason documented in each docstring, and Ultron implements until they
pass. Do not weaken an assertion to make it pass without the underlying
script changing.
"""
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from conftest import SOURCE_ROOT, run_cmd

try:
    import tomllib  # stdlib only from Python 3.11 (PEP 680).
except ModuleNotFoundError:
    tomllib = None

# toolkit-ci.yml pins Python 3.10 on both matrix legs (Ubuntu and Windows) --
# `tomllib` does not exist there, and this project adds no third-party TOML
# parser to keep tests dependency-free (CLAUDE.md: "no vamos a empezar
# ahora"). The two tests below that need a REAL TOML parser (not a
# hand-rolled string check -- that would stop comparing two independently
# produced things and become worthless, unmassk-standards S34) skip on
# Python < 3.11 with this reason, so the pyproject.toml-quoting contract is
# NOT verified on CI until CI's Python is bumped past 3.11 -- everything
# else in this file still collects and runs on 3.10 (the package.json/ORM/
# CSS/CLI-language/absolute-path/Node tests need no TOML parser at all).
_TOMLLIB_UNAVAILABLE_REASON = (
    "tomllib is stdlib only from Python 3.11+; this project adds no "
    "third-party TOML parser, and CI (toolkit-ci.yml) pins Python 3.10 -- "
    "this contract is not verified on CI"
)

SCAFFOLD_PATH = os.path.join(
    SOURCE_ROOT, "skills", "unmassk-scaffolding", "scripts", "scaffold.py"
)


def _load_scaffold():
    """Load the real scaffold.py fresh (no sys.modules caching -- each test
    gets its own module object, so nothing leaks between tests). This is the
    codebase's established pattern for reaching a script entry point's
    internals directly instead of only asserting on subprocess exit codes
    (see unmassk-toolkit-python-test-conventions.md)."""
    spec = importlib.util.spec_from_file_location("scaffold_under_test", SCAFFOLD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _snapshot(root: Path):
    """Real filesystem walk of a real scaffold run: sorted relative paths +
    UTF-8 text content. Used to compare two real runs of the script against
    each other."""
    tree = []
    contents = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            tree.append(rel)
            contents[rel] = p.read_text(encoding="utf-8")
    return tree, contents


# ── Bug 1 -- user strings interpolated raw into hand-written TOML/JS ───────
# `_fastapi_pyproject` (~2294), `_python_pyproject` (~2727),
# `_python_cli_pyproject` (~2789) and `_nextjs_layout` (~1925) f-string the
# description straight into a TOML/JS string literal with no escaping. A
# quote in the description breaks the emitted file -- the script still
# prints "Created" and exits 0, and nobody finds out until they try to build
# that project.

@pytest.mark.skipif(tomllib is None, reason=_TOMLLIB_UNAVAILABLE_REASON)
class TestDescriptionQuoteBreaksPyproject:
    """Contract: whatever the script writes to pyproject.toml must be
    accepted by `tomllib` -- the real, official parser pip/build/uv actually
    use. Today, a `"` in the description breaks the TOML syntax at the
    `description = "..."` line, so `tomllib.loads()` raises
    `tomllib.TOMLDecodeError` -- that uncaught exception is the RED."""

    _QUOTED_DESCRIPTION = 'Handles "edge cases" in input'

    @pytest.mark.parametrize("project_type", ["python", "fastapi", "cli"])
    def test_pyproject_toml_parses_with_quoted_description(self, tmp_path, project_type):
        scaffold = _load_scaffold()
        config = scaffold.ProjectConfig(
            name="quote-check",
            project_type=project_type,
            language=scaffold.Language.PYTHON,
            description=self._QUOTED_DESCRIPTION,
            author="Golden Author",
        )
        scaffolder = scaffold.ProjectScaffolder(base_path=tmp_path)
        project_path = scaffolder.create_project(config)

        pyproject = project_path / "pyproject.toml"
        assert pyproject.exists()
        raw = pyproject.read_text(encoding="utf-8")

        data = tomllib.loads(raw)  # RED today: tomllib.TOMLDecodeError

        assert data["project"]["description"] == self._QUOTED_DESCRIPTION


class TestDescriptionApostropheBreaksNextjsLayout:
    """Same bug class as above, different file: `_nextjs_layout` (~1925)
    single-quotes the description into a JS object literal
    (`description: '{...}'`). Verified with Node itself -- the real JS
    engine, not a hand-rolled lexer -- on the exact `metadata = {...}`
    object-literal substring the script wrote (the template around it is
    TSX/JSX, which a plain JS engine can't parse regardless of this bug, so
    this isolates exactly the site under test)."""

    _QUOTED_DESCRIPTION = "Handles the user's edge cases"  # real apostrophe

    def test_nextjs_layout_metadata_is_valid_js_with_apostrophe_in_description(self, tmp_path):
        node = shutil.which("node")
        if node is None:
            pytest.skip("node not available in this environment")

        scaffold = _load_scaffold()
        config = scaffold.ProjectConfig(
            name="nextjs-quote-check",
            project_type="nextjs",
            language=scaffold.Language.TYPESCRIPT,
            description=self._QUOTED_DESCRIPTION,
            author="Golden Author",
        )
        project_path = scaffold.ProjectScaffolder(base_path=tmp_path).create_project(config)
        layout = project_path / "src" / "app" / "layout.tsx"
        assert layout.exists()
        raw = layout.read_text(encoding="utf-8")

        start = raw.index("export const metadata: Metadata = {")
        brace_start = raw.index("{", start)
        # +2, not +1: `str.index("};", ...)` returns the position of the
        # "}" character, and the slice below is exclusive of its end index
        # -- +1 lands exactly ON the ";" and excludes it from the slice,
        # leaving `object_literal_src` ending in "}" with no terminator.
        # Concatenated below with only a space (no newline/semicolon)
        # before `process.stdout.write(...)`, that missing ";" is exactly
        # what made Node reject valid output: automatic semicolon
        # insertion does not kick in there, so `node -e` saw one broken
        # statement regardless of what scaffold.py emitted. +2 includes
        # both "}" and ";".
        brace_end = raw.index("};", brace_start) + 2
        object_literal_src = raw[brace_start:brace_end]

        node_script = (
            f"const metadata = {object_literal_src} "
            "process.stdout.write(JSON.stringify(metadata));"
        )
        rc, stdout, stderr = run_cmd([node, "-e", node_script], cwd=str(tmp_path))

        # GREEN today (fixed by Ultron, verified 2026-08-06): scaffold.py
        # now emits a double-quoted, escaped literal for this field, so
        # Node accepts it. Kept as a regression guard, not a RED contract
        # anymore -- would fail again if a future change reintroduces raw
        # interpolation here.
        assert rc == 0, f"node rejected the emitted metadata object -- stderr={stderr!r}"
        parsed = json.loads(stdout)
        assert parsed["description"] == self._QUOTED_DESCRIPTION


# ── Bug 2 -- options the CLI advertises as valid are silently no-ops ───────
# `--orm` accepts "drizzle" (line ~3473) but no creator branches on
# `ORM.DRIZZLE` anywhere -- requesting it produces byte-identical output to
# requesting no ORM at all, with no warning.

class TestOrmChoiceSilentlyIgnored:
    """Contract: requesting `ORM.DRIZZLE` (a CLI-advertised, valid choice)
    must produce output that differs from requesting `ORM.NONE` -- either
    real Drizzle support, or a clear rejection. Two independently produced
    real runs are compared; today they are identical, which is the RED."""

    def test_express_drizzle_orm_changes_output_vs_no_orm(self, tmp_path):
        scaffold = _load_scaffold()
        none_base = tmp_path / "none_run"
        drizzle_base = tmp_path / "drizzle_run"
        none_base.mkdir()
        drizzle_base.mkdir()

        common = dict(
            name="orm-project",
            project_type="express",
            language=scaffold.Language.TYPESCRIPT,
            database=scaffold.Database.POSTGRESQL,
            description="Same config except for orm",
            author="Golden Author",
        )
        none_config = scaffold.ProjectConfig(orm=scaffold.ORM.NONE, **common)
        drizzle_config = scaffold.ProjectConfig(orm=scaffold.ORM.DRIZZLE, **common)

        none_path = scaffold.ProjectScaffolder(base_path=none_base).create_project(none_config)
        drizzle_path = scaffold.ProjectScaffolder(base_path=drizzle_base).create_project(drizzle_config)

        none_tree, none_contents = _snapshot(none_path)
        drizzle_tree, drizzle_contents = _snapshot(drizzle_path)

        assert (none_tree, none_contents) != (drizzle_tree, drizzle_contents)


class TestCssFrameworkChoiceSilentlyIgnored:
    """Same bug class, the CSS-framework side of the same finding:
    `--css-framework`-equivalent `CSSFramework.CSS_MODULES` is a valid enum
    member but only `CSSFramework.TAILWIND` is ever checked -- requesting
    CSS Modules produces the exact same output as requesting no CSS
    framework at all."""

    def test_react_css_modules_changes_output_vs_none(self, tmp_path):
        scaffold = _load_scaffold()
        none_base = tmp_path / "none_run"
        modules_base = tmp_path / "modules_run"
        none_base.mkdir()
        modules_base.mkdir()

        common = dict(
            name="css-project",
            project_type="react",
            language=scaffold.Language.TYPESCRIPT,
            description="Same config except for css_framework",
            author="Golden Author",
        )
        none_config = scaffold.ProjectConfig(css_framework=scaffold.CSSFramework.NONE, **common)
        modules_config = scaffold.ProjectConfig(css_framework=scaffold.CSSFramework.CSS_MODULES, **common)

        none_path = scaffold.ProjectScaffolder(base_path=none_base).create_project(none_config)
        modules_path = scaffold.ProjectScaffolder(base_path=modules_base).create_project(modules_config)

        none_tree, none_contents = _snapshot(none_path)
        modules_tree, modules_contents = _snapshot(modules_path)

        assert (none_tree, none_contents) != (modules_tree, modules_contents)


# ── Bug 3 -- the Python CLI generator is unreachable from the real CLI ─────
# `_create_cli` (line ~1161) branches on `config.language`, and
# `_create_python_cli` (line ~1168) is a real, working generator. But
# `main()` (~3492) only forces `language = PYTHON` for
# `["python", "fastapi", "django", "flask"]` -- "cli" is excluded, and there
# is no `--language` flag at all today, so no combination of real
# command-line flags can ever reach `_create_python_cli`.

class TestCliLanguagePythonUnreachableFromRealCommandLine:
    """Contract: `scaffold.py cli <name> --language python`, run as a real
    subprocess through the real `argparse` parser, must produce the Python
    CLI generator's output (pyproject.toml + requirements.txt), never the
    Node one. Today there is no `--language` flag, so argparse rejects it
    outright (rc=2, nothing created) -- that is the RED."""

    def test_cli_language_python_flag_produces_python_cli(self, tmp_path):
        rc, stdout, stderr = run_cmd(
            [sys.executable, SCAFFOLD_PATH, "cli", "lang-check", "--language", "python"],
            cwd=str(tmp_path),
        )
        project_path = tmp_path / "lang-check"

        assert rc == 0, f"stdout={stdout!r} stderr={stderr!r}"
        assert (project_path / "pyproject.toml").exists()
        assert not (project_path / "package.json").exists()


# ── Bug 4 -- an absolute project name escapes the destination directory ────
# `create_project()` (line ~125) does `self.base_path / config.name`.
# pathlib's own semantics: if `config.name` is an absolute path, the whole
# expression evaluates to `config.name` alone -- `base_path` is silently
# discarded. There is no validation that `name` is a plain directory name,
# and the script still prints "Created" on success.

class TestAbsoluteProjectNameDoesNotEscapeBasePath:
    """Contract: a `config.name` that is an absolute path must be rejected
    with a clear error, and must never cause `create_project()` to write
    outside the given `base_path`. Today it raises nothing and writes the
    whole project tree at the absolute path instead -- `pytest.raises`
    failing with "DID NOT RAISE" is the RED."""

    def test_absolute_name_is_rejected_not_written_outside_base(self, tmp_path):
        scaffold = _load_scaffold()
        base = tmp_path / "intended_base"
        base.mkdir()
        outside = tmp_path / "outside"
        escape_name = str(outside / "pwned-project")

        config = scaffold.ProjectConfig(name=escape_name, project_type="html")
        scaffolder = scaffold.ProjectScaffolder(base_path=base)

        with pytest.raises(Exception):
            scaffolder.create_project(config)

        assert not outside.exists()


# ── Baseline sanity net -- not a bug contract, a regression guard ─────────
# With a SAFE description (no quotes, sidesteps Bug 1 above on purpose so
# this class isolates "does the happy path actually produce a parseable
# artifact" from the known quote bug), every package.json the scaffolder
# writes must be valid JSON (what npm/pnpm/yarn actually parse), and every
# pyproject.toml must be valid TOML (what pip/uv/build actually parse).
#
# Not all 17 dispatch entries: package.json is always built from a plain
# Python dict via `json.dump` (`_create_package_json`/`_write_json`, line
# ~1329) -- that path can't produce invalid JSON regardless of which creator
# calls it, so one creator per JSON-producing shape (frontend/backend/lib)
# is enough to prove the writer itself is sound. pyproject.toml is the
# opposite case (hand-written f-string, see Bug 1) -- covering exactly the
# three sites Bug 1 touches confirms they're sound on the happy path, i.e.
# the bug is specifically the quoting, not the TOML shape in general.

class TestGeneratedManifestsParseWithRealParsers:
    _SAFE_DESCRIPTION = "A safe description without quotes"

    @pytest.mark.parametrize("project_type", ["react", "express", "typescript"])
    def test_package_json_is_valid_json(self, tmp_path, project_type):
        scaffold = _load_scaffold()
        config = scaffold.ProjectConfig(
            name="validity-check",
            project_type=project_type,
            language=scaffold.Language.TYPESCRIPT,
            description=self._SAFE_DESCRIPTION,
            author="Golden Author",
        )
        project_path = scaffold.ProjectScaffolder(base_path=tmp_path).create_project(config)
        package_json = project_path / "package.json"
        assert package_json.exists()
        data = json.loads(package_json.read_text(encoding="utf-8"))
        assert data["name"] == "validity-check"

    @pytest.mark.skipif(tomllib is None, reason=_TOMLLIB_UNAVAILABLE_REASON)
    @pytest.mark.parametrize("project_type", ["python", "fastapi", "cli"])
    def test_pyproject_toml_is_valid_toml(self, tmp_path, project_type):
        scaffold = _load_scaffold()
        config = scaffold.ProjectConfig(
            name="validity-check",
            project_type=project_type,
            language=scaffold.Language.PYTHON,
            description=self._SAFE_DESCRIPTION,
            author="Golden Author",
        )
        project_path = scaffold.ProjectScaffolder(base_path=tmp_path).create_project(config)
        pyproject = project_path / "pyproject.toml"
        assert pyproject.exists()
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        assert data["project"]["name"] == "validity-check"
