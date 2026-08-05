"""
The doctor must never report green because it could not check anything.

Roadmap FASE 2.5/2.6 replaced two hand-written constants
(`EXPECTED_HOOKS`, 5 entries; `EXPECTED_SKILLS`, 3) with derivation from the
real sources — `hooks/hooks.json` and the `skills/` directory — and added a
repo-vs-cache comparison. The hand-written lists had drifted to covering 5
of 12 hooks and 3 of 10 skills while printing "5/5 ✅": a check that reports
success over things it never looked at.

Derivation removes that drift, but it introduces a worse failure mode if
handled carelessly: when `hooks.json` cannot be read, `expected_hooks()`
returns None, and a caller that treats None like an empty list prints
"0/0 ✅" — a doctor that is green *because* it is blind. That is the single
most important behaviour in this file (`TestDoctorNeverGreenWhenBlind`), and
it is asserted end-to-end through `run_doctor()`, not just on the helper's
return value, because the collapse would happen at the call site.

`check_repo_cache_sync()` is the opposite contract: fail-open. Claude Code
runs the plugin from `~/.claude/plugins/cache/...`, so an unpushed edit in
the working tree changes nothing at runtime; the check exists to say so.
But it is a developer convenience, never a correctness guarantee, so
"cannot tell" must come out as silence (None) and never as an exception or
an invented alarm.
"""

import importlib.util
import json
import os
import shutil
import sys

import pytest

from conftest import BIN_DIR, DOCTOR, LIB_DIR, git_cmd

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import cache_sync_check  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────

def _load_doctor(name):
    """Load bin/git-memory-doctor.py (hyphenated, not importable normally).

    Same pattern as test_date_parsing_epoch_contract.py — the script has no
    side effects outside `if __name__ == "__main__"`.
    """
    spec = importlib.util.spec_from_file_location(name, DOCTOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


REAL_PLUGIN_ROOT = os.path.dirname(BIN_DIR)


def _fake_plugin_root(tmp_path, hooks_json_content="__real__", with_skills=True):
    """Build a minimal plugin root: hooks/ + skills/ only.

    `hooks_json_content`:
        "__real__" -> copy the shipped hooks.json verbatim
        None       -> do not create hooks.json at all
        str        -> write that exact text
    """
    root = tmp_path / "plugin_root"
    hooks_dir = root / "hooks"
    hooks_dir.mkdir(parents=True)

    if hooks_json_content == "__real__":
        shutil.copy(
            os.path.join(REAL_PLUGIN_ROOT, "hooks", "hooks.json"),
            str(hooks_dir / "hooks.json"),
        )
    elif hooks_json_content is not None:
        (hooks_dir / "hooks.json").write_text(hooks_json_content, encoding="utf-8")

    if with_skills:
        skills_dir = root / "skills" / "some-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("# skill\n", encoding="utf-8")

    return str(root)


def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _run_doctor_json(doctor_mod, repo, plugin_root, monkeypatch, capsys):
    """Run the real run_doctor() against a chosen plugin root."""
    monkeypatch.setattr(doctor_mod, "find_plugin_root", lambda: plugin_root)
    monkeypatch.chdir(repo)
    rc = doctor_mod.run_doctor(as_json=True)
    out = capsys.readouterr().out
    return json.loads(out), rc


def _find_check(parsed, component):
    for check in parsed.get("checks", []):
        if check.get("component") == component:
            return check
    return None


# ── expected_hooks(): derived from hooks.json ────────────────────────────

class TestExpectedHooksDerivation:

    def test_matches_the_hook_files_actually_shipped(self):
        """hooks.json and the files on disk must describe the same set.

        The expected value is not hand-typed: it is read off the filesystem,
        an independent source from hooks.json. This is the drift the hand-
        written EXPECTED_HOOKS list could not detect — it named 5 of 12 and
        called it 5/5.
        """
        doctor = _load_doctor("doctor_expected_hooks_real")

        derived = doctor.expected_hooks(REAL_PLUGIN_ROOT)

        # Los tres hooks del sistema viejo que el cambio de guardia del
        # 2026-08-05 desenchufo siguen en disco a proposito: si el arranque
        # nuevo falla en una sesion real, volver es cambiar hooks.json y
        # nada mas. Se declaran aqui, con su motivo, para que este
        # vigilante siga cazando una divergencia de VERDAD en vez de estar
        # rojo todos los dias por un hueco ya decidido -- un test rojo que
        # nadie explica es un test que se acaba ignorando.
        DELIBERATELY_UNWIRED = {
            # RETIRADOS el 2026-08-05 en el cambio de guardia: siguen en
            # disco a proposito hasta que se borren con sus tests, que
            # tocan siete ficheros y dos de ellos compartidos. Borrarlos
            # es una pasada propia, no una linea al final de otra cosa.
            "pre-validate-commit-trailers.py",
            "stop-dod-check.py",
            "session-start-boot.py",
        }

        on_disk = {
            name for name in os.listdir(os.path.join(REAL_PLUGIN_ROOT, "hooks"))
            if name.endswith(".py")
        } - doctor.TRANSIENT_HOOKS - DELIBERATELY_UNWIRED

        assert derived is not None, "the shipped hooks.json must be readable"
        assert set(derived) == on_disk, (
            "hooks.json and hooks/ disagree.\n"
            f"  declared but not shipped: {sorted(set(derived) - on_disk)}\n"
            f"  shipped but not declared: {sorted(on_disk - set(derived))}\n"
            "  (los hooks del sistema viejo desenchufados el 2026-08-05 estan "
            "exentos a proposito hasta que se borren con sus tests)"
        )

    def test_unreadable_and_malformed_inputs_all_return_none(self, tmp_path):
        """Every way hooks.json can fail must land on None, never [].

        [] and None are both falsy, but they mean opposite things to the
        caller: "this install declares no hooks" vs "I could not look".
        Collapsing them is how a blind check reports success.
        """
        doctor = _load_doctor("doctor_hooks_json_failure_modes")

        cases = {
            "absent": None,
            "not json": "{ this is not json",
            "json but a list": "[]",
            "json but a string": '"hooks"',
            "no hooks key": '{"description": "x"}',
            "hooks key is a list": '{"hooks": []}',
            "hooks key is a string": '{"hooks": "everything"}',
        }
        for label, content in cases.items():
            root = _fake_plugin_root(tmp_path / label.replace(" ", "_"),
                                     hooks_json_content=content)

            result = doctor.expected_hooks(root)

            assert result is None, (
                f"hooks.json case {label!r} must return None (cannot verify), "
                f"got {result!r}. An empty list here becomes '0/0 ✅'."
            )

    def test_directory_where_hooks_json_should_be_returns_none(self, tmp_path):
        """A directory named hooks.json is an OSError on open, not a crash."""
        doctor = _load_doctor("doctor_hooks_json_is_a_dir")
        root = _fake_plugin_root(tmp_path, hooks_json_content=None)
        os.makedirs(os.path.join(root, "hooks", "hooks.json"))

        assert doctor.expected_hooks(root) is None

    def test_malformed_entries_are_skipped_without_losing_the_good_ones(self, tmp_path):
        """One broken entry must not void the whole list, nor crash.

        Half a hooks.json is still worth checking; the alternative is either
        a traceback at boot or a silent None over hooks that ARE declared.
        """
        doctor = _load_doctor("doctor_hooks_json_partial")
        content = json.dumps({
            "hooks": {
                "SessionStart": [
                    "not-a-dict",
                    {"hooks": "not-a-list"},
                    {"hooks": ["not-a-dict", {"command": "python3 ${X}/hooks/good-one.py"}]},
                ],
                "Stop": "not-a-list",
                "PreToolUse": [{"hooks": [{"command": "echo no hook path here"}]}],
            }
        })
        root = _fake_plugin_root(tmp_path, hooks_json_content=content)

        assert doctor.expected_hooks(root) == ["good-one.py"]

    def test_result_is_sorted_and_deduplicated(self, tmp_path):
        """The same hook declared on three events counts once."""
        doctor = _load_doctor("doctor_hooks_json_dedup")
        cmd = "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/zeta.py"
        content = json.dumps({
            "hooks": {
                "SessionStart": [{"hooks": [{"command": cmd}]}],
                "Stop": [{"hooks": [{"command": cmd}]}],
                "PreToolUse": [{"hooks": [
                    {"command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/alpha.py"}]}],
            }
        })
        root = _fake_plugin_root(tmp_path, hooks_json_content=content)

        assert doctor.expected_hooks(root) == ["alpha.py", "zeta.py"]


# ── expected_skills(): derived from skills/ ──────────────────────────────

class TestExpectedSkillsDerivation:

    def test_matches_the_skill_directories_actually_shipped(self):
        """Every shipped skill directory must be expected — all 10, not 3."""
        doctor = _load_doctor("doctor_expected_skills_real")
        skills_dir = os.path.join(REAL_PLUGIN_ROOT, "skills")

        derived = doctor.expected_skills(REAL_PLUGIN_ROOT)

        on_disk = {
            name for name in os.listdir(skills_dir)
            if os.path.isdir(os.path.join(skills_dir, name))
            and not name.startswith((".", "_"))
        }
        assert derived is not None
        assert set(derived) == on_disk, (
            f"expected_skills() returned {sorted(derived)}, skills/ holds "
            f"{sorted(on_disk)}"
        )
        assert derived == sorted(derived), "result must be sorted"

    def test_missing_skills_dir_returns_none_not_empty(self, tmp_path):
        """None = cannot verify. [] would print '0/0' over a broken install."""
        doctor = _load_doctor("doctor_skills_missing")
        root = _fake_plugin_root(tmp_path, with_skills=False)

        assert doctor.expected_skills(root) is None

    def test_files_and_hidden_or_underscored_dirs_are_not_skills(self, tmp_path):
        """Only real, visible directories count."""
        doctor = _load_doctor("doctor_skills_filtering")
        root = _fake_plugin_root(tmp_path)
        skills = os.path.join(root, "skills")
        os.makedirs(os.path.join(skills, ".hidden-skill"))
        os.makedirs(os.path.join(skills, "_scratch"))
        with open(os.path.join(skills, "README.md"), "w", encoding="utf-8") as f:
            f.write("not a skill\n")

        assert doctor.expected_skills(root) == ["some-skill"]

    def test_empty_skills_dir_returns_empty_list_not_none(self, tmp_path):
        """Readable but empty is a different fact from unreadable.

        The caller distinguishes the two in its error message ("skills/ is
        empty" vs "skills/ unreadable"), which is only possible if the
        helper keeps them apart.
        """
        doctor = _load_doctor("doctor_skills_empty")
        root = _fake_plugin_root(tmp_path, with_skills=False)
        os.makedirs(os.path.join(root, "skills"))

        assert doctor.expected_skills(root) == []


# ── The one that matters: no green report over an unchecked surface ──────

class TestDoctorNeverGreenWhenBlind:
    """End-to-end through run_doctor(), because the collapse to "0/0 ✅"
    would happen at the call site, not inside the helper."""

    @pytest.mark.parametrize(
        "label, hooks_json",
        [
            ("absent", None),
            ("corrupt", "{ not json at all"),
            ("declares nothing", '{"hooks": {}}'),
        ],
    )
    def test_unverifiable_hooks_are_reported_as_an_error(
        self, tmp_path, monkeypatch, capsys, label, hooks_json
    ):
        doctor = _load_doctor(f"doctor_blind_hooks_{label.replace(' ', '_')}")
        repo = _make_repo(tmp_path)
        plugin_root = _fake_plugin_root(tmp_path, hooks_json_content=hooks_json)

        parsed, rc = _run_doctor_json(doctor, repo, plugin_root, monkeypatch, capsys)
        check = _find_check(parsed, "Hooks")

        assert check is not None, f"no Hooks check in the report: {parsed}"
        assert check["level"] == "error", (
            f"hooks.json {label}: the doctor cannot verify a single hook and "
            f"must say so as an error. Got level={check['level']!r}, "
            f"message={check['message']!r}"
        )
        assert "cannot verify" in check["message"], (
            "the message must state that nothing was verified, not just that "
            f"something is off. Got {check['message']!r}"
        )
        assert "0/0" not in check["message"], (
            "'0/0' is the exact shape of the silent green this check "
            f"replaced. Got {check['message']!r}"
        )
        assert parsed["status"] == "error", (
            f"overall status must be error, got {parsed['status']!r}")
        assert rc == 1, f"exit code must be 1 when the doctor is blind, got {rc}"

    def test_unverifiable_skills_are_reported_as_an_error(
        self, tmp_path, monkeypatch, capsys
    ):
        doctor = _load_doctor("doctor_blind_skills")
        repo = _make_repo(tmp_path)
        plugin_root = _fake_plugin_root(tmp_path, with_skills=False)

        parsed, rc = _run_doctor_json(doctor, repo, plugin_root, monkeypatch, capsys)
        check = _find_check(parsed, "Skills")

        assert check is not None, f"no Skills check in the report: {parsed}"
        assert check["level"] == "error", (
            "skills/ is unreadable — the doctor must not stay quiet. Got "
            f"{check!r}"
        )
        assert "cannot verify" in check["message"]
        assert "0/0" not in check["message"]
        assert rc == 1

    def test_a_healthy_plugin_root_still_reports_the_real_totals(
        self, tmp_path, monkeypatch, capsys
    ):
        """Anti-vacuity control for the whole class.

        Against the REAL plugin root the Hooks and Skills checks must be
        green and must name the real counts — otherwise the tests above
        would pass just as well on a doctor that reports "error" for
        everything, always.
        """
        doctor = _load_doctor("doctor_healthy_root")
        repo = _make_repo(tmp_path)

        parsed, _ = _run_doctor_json(
            doctor, repo, REAL_PLUGIN_ROOT, monkeypatch, capsys)

        hooks = _find_check(parsed, "Hooks")
        skills = _find_check(parsed, "Skills")
        n_hooks = len(doctor.expected_hooks(REAL_PLUGIN_ROOT))
        n_skills = len(doctor.expected_skills(REAL_PLUGIN_ROOT))

        assert hooks["level"] == "ok", f"real plugin root: {hooks!r}"
        assert f"{n_hooks}/{n_hooks}" in hooks["message"], (
            f"expected the real derived count {n_hooks} in {hooks['message']!r}")
        assert skills["level"] == "ok", f"real plugin root: {skills!r}"
        assert f"{n_skills}/{n_skills}" in skills["message"], (
            f"expected the real derived count {n_skills} in {skills['message']!r}")

    def test_a_hook_declared_but_not_shipped_is_named_in_the_report(
        self, tmp_path, monkeypatch, capsys
    ):
        """The point of derivation: a hook that hooks.json promises and the
        install does not carry must be named, not averaged away."""
        doctor = _load_doctor("doctor_missing_hook_file")
        repo = _make_repo(tmp_path)
        content = json.dumps({"hooks": {"SessionStart": [{"hooks": [
            {"command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/ghost-hook.py"}]}]}})
        plugin_root = _fake_plugin_root(tmp_path, hooks_json_content=content)

        parsed, rc = _run_doctor_json(doctor, repo, plugin_root, monkeypatch, capsys)
        check = _find_check(parsed, "Hooks")

        assert check["level"] == "error"
        assert "ghost-hook.py" in check["message"], (
            f"the missing hook must be named. Got {check['message']!r}")
        assert rc == 1


# ── check_repo_cache_sync(): fail-open, never louder than the facts ──────

class TestRepoCacheSyncFailsOpen:

    def test_project_without_a_toolkit_tree_says_nothing(self, tmp_path):
        """Any project that is not the toolkit repo has no source to compare."""
        project = tmp_path / "some-other-project"
        (project / "src").mkdir(parents=True)

        assert cache_sync_check.check_repo_cache_sync(str(project)) is None

    def test_no_cache_at_all_says_nothing(self, tmp_path, monkeypatch):
        """A missing plugin cache is not an alarm — it is nothing to say."""
        project = tmp_path / "toolkit-repo"
        (project / cache_sync_check.PLUGIN_DIR_NAME / "lib").mkdir(parents=True)
        monkeypatch.setattr(
            cache_sync_check, "CACHE_BASE_DIR", str(tmp_path / "no-such-cache"))

        assert cache_sync_check.check_repo_cache_sync(str(project)) is None

    def test_cache_dir_present_but_holds_no_version_says_nothing(
        self, tmp_path, monkeypatch
    ):
        project = tmp_path / "toolkit-repo"
        (project / cache_sync_check.PLUGIN_DIR_NAME / "lib").mkdir(parents=True)
        cache = tmp_path / "cache"
        (cache / cache_sync_check.PLUGIN_DIR_NAME).mkdir(parents=True)
        monkeypatch.setattr(cache_sync_check, "CACHE_BASE_DIR", str(cache))

        assert cache_sync_check.check_repo_cache_sync(str(project)) is None

    def test_cache_pointing_at_the_source_tree_says_nothing(
        self, tmp_path, monkeypatch, real_symlink_capable
    ):
        """Running against the working tree itself — comparing it to itself
        would always be 'in sync', which is true but noise."""
        project = tmp_path / "toolkit-repo"
        source = project / cache_sync_check.PLUGIN_DIR_NAME
        (source / "lib").mkdir(parents=True)
        cache = tmp_path / "cache"
        (cache / cache_sync_check.PLUGIN_DIR_NAME).mkdir(parents=True)
        os.symlink(str(source), str(cache / cache_sync_check.PLUGIN_DIR_NAME / "9.9.9"))
        monkeypatch.setattr(cache_sync_check, "CACHE_BASE_DIR", str(cache))

        assert cache_sync_check.check_repo_cache_sync(str(project)) is None


class TestRepoCacheSyncDetectsDrift:
    """The one thing it must actually catch: an edit that is not running."""

    @staticmethod
    def _build(tmp_path, monkeypatch, repo_files, cache_files, version="1.0.0"):
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

    def test_identical_trees_report_no_drift(self, tmp_path, monkeypatch):
        files = {
            "hooks/a.py": "print(1)\n",
            "lib/b.py": "x = 1\n",
            "bin/c.py": "y = 2\n",
        }
        project = self._build(tmp_path, monkeypatch, files, dict(files))

        assert cache_sync_check.check_repo_cache_sync(project) == []

    def test_an_edited_file_is_named(self, tmp_path, monkeypatch):
        """The exact failure the check exists for: the edit is in the repo,
        the cache still runs the old byte."""
        project = self._build(
            tmp_path, monkeypatch,
            {"hooks/pre-validate-commit-trailers.py": 'CLAUDECODE\n'},
            {"hooks/pre-validate-commit-trailers.py": 'CLAUDE_CODE\n'},
        )

        drift = cache_sync_check.check_repo_cache_sync(project)

        assert drift, "an edited hook must be reported as drift"
        assert any("pre-validate-commit-trailers.py" in line for line in drift), (
            f"the drifting file must be named. Got {drift}")

    def test_a_file_only_in_the_repo_counts_as_drift(self, tmp_path, monkeypatch):
        project = self._build(
            tmp_path, monkeypatch,
            {"lib/new_module.py": "x = 1\n"},
            {"lib/other.py": "y = 1\n"},
        )

        drift = cache_sync_check.check_repo_cache_sync(project)

        assert any("new_module.py" in line for line in drift), drift

    def test_a_subdir_absent_from_the_cache_is_reported_as_such(
        self, tmp_path, monkeypatch
    ):
        project = self._build(
            tmp_path, monkeypatch,
            {"bin/tool.py": "x = 1\n"},
            {"lib/other.py": "y = 1\n"},
        )

        drift = cache_sync_check.check_repo_cache_sync(project)

        assert any("bin/: absent from the cache" in line for line in drift), drift

    def test_a_subdir_absent_from_the_repo_is_not_an_alarm(self, tmp_path, monkeypatch):
        """No source side to compare = fail open, per the module contract."""
        project = self._build(
            tmp_path, monkeypatch,
            {"lib/same.py": "x = 1\n"},
            {"lib/same.py": "x = 1\n", "bin/extra.py": "z = 1\n"},
        )

        assert cache_sync_check.check_repo_cache_sync(project) == []

    def test_pycache_is_ignored(self, tmp_path, monkeypatch):
        """__pycache__ is regenerated locally and always differs — counting
        it would make the check cry wolf on every single run."""
        project = self._build(
            tmp_path, monkeypatch,
            {"lib/same.py": "x = 1\n", "lib/__pycache__/same.cpython-99.pyc": "AAA"},
            {"lib/same.py": "x = 1\n"},
        )

        assert cache_sync_check.check_repo_cache_sync(project) == []

    def test_many_differing_files_are_summarised_not_dumped(self, tmp_path, monkeypatch):
        """Bounded output: three names then a count."""
        repo_files = {f"lib/mod{i}.py": f"v = {i}\n" for i in range(7)}
        cache_files = {f"lib/mod{i}.py": f"v = {i}00\n" for i in range(7)}
        project = self._build(tmp_path, monkeypatch, repo_files, cache_files)

        drift = cache_sync_check.check_repo_cache_sync(project)

        assert len(drift) == 1, drift
        line = drift[0]
        named = [n for n in repo_files if os.path.basename(n) in line]
        assert len(named) == cache_sync_check._MAX_NAMED_FILES, (
            f"expected {cache_sync_check._MAX_NAMED_FILES} names in {line!r}")
        assert f"+{7 - cache_sync_check._MAX_NAMED_FILES} more" in line, line

    def test_picks_the_highest_semver_cache_version(self, tmp_path, monkeypatch):
        """Comparing against a stale older version directory would report
        drift that no longer exists — a false alarm, and the check's whole
        value is that its silence can be trusted."""
        project = self._build(
            tmp_path, monkeypatch,
            {"lib/a.py": "new\n"}, {"lib/a.py": "old\n"}, version="1.9.0")
        newer = (tmp_path / "cache" / cache_sync_check.PLUGIN_DIR_NAME
                 / "1.10.0" / "lib")
        newer.mkdir(parents=True)
        (newer / "a.py").write_text("new\n", encoding="utf-8")

        assert cache_sync_check.check_repo_cache_sync(project) == [], (
            "1.10.0 is newer than 1.9.0 by semver; comparing against 1.9.0 "
            "would report drift that is already fixed"
        )


# ── count_repo_cache_drift(): the real file count, not the grouped-line
# count ─────────────────────────────────────────────────────────────────
#
# check_repo_cache_sync() already has full coverage above for the fail-open
# contract and the description text; that contract did not change and is
# not repeated here. count_repo_cache_drift() shares the exact same
# _compute_drift() core, so this class only tests the ONE thing that is new
# and different: the raw integer count, and specifically that it survives
# _describe()'s "+N more" summarisation instead of being derived from the
# bounded description strings.

def _build_drift_fixture(tmp_path, monkeypatch, repo_files, cache_files, version="1.0.0"):
    """Same fixture shape as TestRepoCacheSyncDetectsDrift._build() above —
    duplicated rather than shared across classes so this class stays
    readable on its own and neither ever depends on the other's setup."""
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


class TestCountRepoCacheDrift:

    def test_not_applicable_returns_none_same_as_check_repo_cache_sync(self, tmp_path):
        """One representative fail-open case, proving count_repo_cache_drift()
        preserves the "None means cannot verify" contract of its sibling —
        not the full fail-open matrix, which is already covered above."""
        project = tmp_path / "some-other-project"
        (project / "src").mkdir(parents=True)

        assert cache_sync_check.count_repo_cache_drift(str(project)) is None

    def test_identical_trees_return_zero_count_and_empty_descriptions(
        self, tmp_path, monkeypatch
    ):
        files = {
            "hooks/a.py": "print(1)\n",
            "lib/b.py": "x = 1\n",
            "bin/c.py": "y = 2\n",
        }
        project = _build_drift_fixture(tmp_path, monkeypatch, files, dict(files))

        count, descriptions = cache_sync_check.count_repo_cache_drift(project)

        assert count == 0, "identical trees must report the explicit zero, not a truthy count"
        assert descriptions == []

    def test_count_is_the_real_file_count_not_the_grouped_description_count(
        self, tmp_path, monkeypatch
    ):
        """This is the exact reason the function exists: with more than
        _MAX_NAMED_FILES differing files in one subdir, check_repo_cache_sync()
        bundles them behind "+N more" into ONE description line — but the
        PLUGIN: banner needs the real number of differing files, 7, not 1."""
        repo_files = {f"lib/mod{i}.py": f"v = {i}\n" for i in range(7)}
        cache_files = {f"lib/mod{i}.py": f"v = {i}00\n" for i in range(7)}
        project = _build_drift_fixture(tmp_path, monkeypatch, repo_files, cache_files)

        count, descriptions = cache_sync_check.count_repo_cache_drift(project)

        assert count == 7, (
            f"7 files actually differ; a caller reading the description "
            f"count instead would see {len(descriptions)}"
        )
        assert len(descriptions) == 1, (
            "sanity check on the fixture: this must be the exact grouped-"
            "into-one-line shape count_repo_cache_drift() has to see through"
        )

    def test_count_sums_across_multiple_subdirs(self, tmp_path, monkeypatch):
        repo_files = {
            "lib/a.py": "new_a\n", "lib/b.py": "new_b\n",
            "bin/c.py": "new_c\n", "bin/d.py": "new_d\n", "bin/e.py": "new_e\n",
        }
        cache_files = {
            "lib/a.py": "old_a\n", "lib/b.py": "old_b\n",
            "bin/c.py": "old_c\n", "bin/d.py": "old_d\n", "bin/e.py": "old_e\n",
        }
        project = _build_drift_fixture(tmp_path, monkeypatch, repo_files, cache_files)

        count, descriptions = cache_sync_check.count_repo_cache_drift(project)

        assert count == 5, f"2 lib/ + 3 bin/ files differ = 5 total, got {count}"
        assert len(descriptions) == 2, (
            f"one description line per drifted subdir (lib/, bin/), got {descriptions}"
        )

    def test_subdir_absent_from_cache_counts_every_repo_file_in_it(
        self, tmp_path, monkeypatch
    ):
        """_compute_drift()'s fail-open branch for a whole missing subdir
        counts every repo-side file as unaccounted for -- count_repo_cache_drift()
        must report that same real number, not just note the subdir is absent."""
        repo_files = {"bin/tool.py": "x = 1\n", "bin/other.py": "y = 1\n"}
        cache_files = {"lib/only.py": "z = 1\n"}
        project = _build_drift_fixture(tmp_path, monkeypatch, repo_files, cache_files)

        count, descriptions = cache_sync_check.count_repo_cache_drift(project)

        assert count == 2, f"both bin/ files are unaccounted for in the cache, got {count}"
        assert any("bin/: absent from the cache" in line for line in descriptions), descriptions

    def test_descriptions_match_check_repo_cache_sync_exactly(self, tmp_path, monkeypatch):
        """Both public functions share _compute_drift() -- their description
        halves must never disagree, only count_repo_cache_drift() adds the
        extra integer."""
        repo_files = {"lib/a.py": "new\n", "hooks/h.py": "same\n"}
        cache_files = {"lib/a.py": "old\n", "hooks/h.py": "same\n"}
        project = _build_drift_fixture(tmp_path, monkeypatch, repo_files, cache_files)

        _count, descriptions = cache_sync_check.count_repo_cache_drift(project)
        sync_descriptions = cache_sync_check.check_repo_cache_sync(project)

        assert descriptions == sync_descriptions
