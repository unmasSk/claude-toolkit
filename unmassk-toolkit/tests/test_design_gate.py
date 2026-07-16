"""Tests for bin/design_gate.py -- the skill frontmatter collision linter.

Covers: never-crash frontmatter parsing (malformed SKILL.md must warn, not
crash, and must not affect the exit code), the four collision detections
(keyword, phrase, dangling reference, mutual contradiction), the Cerberus
review regression fixes (digit-led skill names, short ALL-CAPS acronyms,
0-skills-scanned fail-loud, allowlist gating), and cross-platform handling
(utf-8 content, vendor-dir skipping, no POSIX path assumptions).

All fixtures are synthetic SKILL.md files built under tmp_path -- nothing
here depends on the real repo's skill tree or its real
design-gate-allowlist.json, so these tests are stable regardless of how
many real skills exist or what real collisions are already accepted there.
Every in-process call passes an explicit (usually empty) fixture allowlist
for the same reason.

design_gate.py is the one bin/ script with no hyphens in its filename
(every other bin/ script is hyphenated, see
unmassk-toolkit-python-test-conventions.md), so it is importable directly
via sys.path -- no importlib.util.spec_from_file_location dance needed.
"""

import json
import os
import sys

import pytest

from conftest import BIN_DIR, run_script

DESIGN_GATE = os.path.join(BIN_DIR, "design_gate.py")

if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)
import design_gate  # noqa: E402


# ── Fixture helpers ──────────────────────────────────────────────────────

def _skill_md_text(name: str, description: str) -> str:
    """Build a valid SKILL.md frontmatter block. The description is emitted
    as a JSON string -- a valid YAML flow scalar -- so embedded quotes and
    colons never need block-scalar indentation gymnastics in the fixture."""
    return (
        "---\n"
        f"name: {json.dumps(name)}\n"
        f"description: {json.dumps(description)}\n"
        "---\n\nBody text.\n"
    )


def _write_skill(root, rel_dir: str, name: str, description: str) -> str:
    """Write a synthetic, well-formed SKILL.md under root/rel_dir/SKILL.md."""
    skill_dir = os.path.join(root, rel_dir)
    os.makedirs(skill_dir, exist_ok=True)
    path = os.path.join(skill_dir, "SKILL.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_skill_md_text(name, description))
    return path


def _write_raw(root, rel_dir: str, content: str) -> str:
    """Write a raw (possibly malformed) SKILL.md, exactly as given."""
    skill_dir = os.path.join(root, rel_dir)
    os.makedirs(skill_dir, exist_ok=True)
    path = os.path.join(skill_dir, "SKILL.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _write_allowlist(tmp_path, keyword=None, phrase=None, dangling=None, mutual=None) -> str:
    path = os.path.join(str(tmp_path), "allowlist.json")
    data = {
        "keyword_collisions": keyword or [],
        "phrase_collisions": phrase or [],
        "dangling_references": dangling or [],
        "mutual_contradictions": mutual or [],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


def _empty_allowlist(tmp_path) -> str:
    return _write_allowlist(tmp_path)


def _run_gate_cli(root, allowlist=None, json_mode=True):
    """Run design_gate.py as a real subprocess. Returns (rc, stdout, stderr)."""
    args = ["--root", str(root)]
    if allowlist is not None:
        args += ["--allowlist", str(allowlist)]
    if json_mode:
        args += ["--json"]
    return run_script(DESIGN_GATE, str(root), args)


def _run_gate_cli_json(root, allowlist=None):
    rc, out, err = _run_gate_cli(root, allowlist=allowlist, json_mode=True)
    try:
        report = json.loads(out)
    except json.JSONDecodeError:
        report = {"_debug": f"rc={rc} stdout={out!r} stderr={err!r}"}
    return report, rc


def _by_term(collisions, key, value):
    return [c for c in collisions if c.get(key) == value]


# ══════════════════════════════════════════════════════════════════════
# 1. Never-crash frontmatter parsing
# ══════════════════════════════════════════════════════════════════════

class TestNeverCrashFrontmatterParsing:
    """Every malformed SKILL.md must produce a warning, never a crash, and
    must never affect the exit code (a companion healthy skill in the same
    root proves the gate still runs to completion and can still read CLEAN)."""

    def _root_with(self, tmp_path, raw_content):
        root = str(tmp_path / "root")
        _write_skill(root, "ok-companion", "ok-companion",
                     "Use when the user asks to \"do the companion thing\" "
                     "or mentions any of: companionuniqueterm.")
        _write_raw(root, "malformed-one", raw_content)
        return root

    def _assert_single_warning(self, tmp_path, raw_content, reason_substring):
        root = self._root_with(tmp_path, raw_content)
        allowlist = _empty_allowlist(tmp_path)
        report = design_gate.run_gate(root, allowlist_path=allowlist)
        assert report["ok"] is True
        assert report["error"] is None
        assert report["skills_scanned"] == 1
        assert len(report["warnings"]) == 1
        assert reason_substring in report["warnings"][0]["reason"]
        return report

    def test_no_frontmatter_delimiter_warns_not_crashes(self, tmp_path):
        self._assert_single_warning(
            tmp_path, "# Just a heading\nNo frontmatter here at all.\n",
            "no frontmatter delimiter",
        )

    def test_missing_closing_delimiter_warns_not_crashes(self, tmp_path):
        self._assert_single_warning(
            tmp_path, "---\nname: bad\ndescription: bad\n",
            "missing closing",
        )

    def test_empty_frontmatter_warns_not_crashes(self, tmp_path):
        self._assert_single_warning(
            tmp_path, "---\n---\n\nBody\n",
            "did not parse to a mapping",
        )

    def test_invalid_yaml_unquoted_colon_warns_not_crashes(self, tmp_path):
        self._assert_single_warning(
            tmp_path,
            "---\nname: bad-skill\ndescription: value: has an unquoted colon\n---\n\nBody\n",
            "invalid YAML frontmatter",
        )

    def test_frontmatter_parses_to_list_not_mapping(self, tmp_path):
        self._assert_single_warning(
            tmp_path, "---\n- one\n- two\n---\n\nBody\n",
            "did not parse to a mapping",
        )

    def test_missing_name_field_warns_not_crashes(self, tmp_path):
        self._assert_single_warning(
            tmp_path, '---\ndescription: "has description only"\n---\n\nBody\n',
            "missing or invalid 'name'",
        )

    def test_missing_description_field_warns_not_crashes(self, tmp_path):
        self._assert_single_warning(
            tmp_path, '---\nname: "has-name-only"\n---\n\nBody\n',
            "missing or invalid 'description'",
        )

    def test_name_field_wrong_type_warns_not_crashes(self, tmp_path):
        self._assert_single_warning(
            tmp_path, '---\nname: 123\ndescription: "has description"\n---\n\nBody\n',
            "missing or invalid 'name'",
        )

    def test_description_field_wrong_type_warns_not_crashes(self, tmp_path):
        self._assert_single_warning(
            tmp_path, '---\nname: "has-name"\ndescription: 123\n---\n\nBody\n',
            "missing or invalid 'description'",
        )

    def test_unicode_decode_error_warns_not_crashes(self, tmp_path):
        """load_skill_frontmatter's OSError/UnicodeDecodeError branch --
        exercised directly (not through the full walk) with raw invalid
        UTF-8 bytes that can never legally decode."""
        path = tmp_path / "invalid_bytes_SKILL.md"
        path.write_bytes(b"---\nname: bad\n\xff\xfe\x00 invalid utf8\ndescription: x\n---\n")
        frontmatter, warning = design_gate.load_skill_frontmatter(str(path))
        assert frontmatter is None
        assert "could not read file" in warning

    def test_yaml_none_load_skill_frontmatter_reports_missing_dependency(self, tmp_path, monkeypatch):
        """Defensive function-level guard: if pyyaml were unavailable,
        load_skill_frontmatter must report it, not raise AttributeError on
        `yaml.safe_load`."""
        path = _write_skill(str(tmp_path), "some-skill", "some-skill",
                             "Use when the user asks to \"thing\" or mentions any of: term.")
        monkeypatch.setattr(design_gate, "yaml", None)
        frontmatter, warning = design_gate.load_skill_frontmatter(path)
        assert frontmatter is None
        assert "pyyaml" in warning.lower()


# ══════════════════════════════════════════════════════════════════════
# 2. The four collision detections
# ══════════════════════════════════════════════════════════════════════

class TestFourDetections:

    def test_keyword_collision_detected(self, tmp_path):
        root = str(tmp_path / "root")
        _write_skill(root, "kw-alpha", "kw-alpha",
                     'Use when the user asks to "spin up the quantumwidget" '
                     'or mentions any of: quantumwidget, filleralpha.')
        _write_skill(root, "kw-beta", "kw-beta",
                     'Use when the user asks to "engage the quantum core" '
                     'or mentions any of: quantumwidget, fillerbeta.')
        allowlist = _empty_allowlist(tmp_path)
        report = design_gate.run_gate(root, allowlist_path=allowlist)

        assert report["ok"] is False
        matches = _by_term(report["keyword_collisions"], "term", "quantumwidget")
        assert len(matches) == 1
        assert matches[0]["skills"] == ["kw-alpha", "kw-beta"]
        assert matches[0]["allowlisted"] is False
        assert report["phrase_collisions"] == []

    def test_phrase_collision_detected(self, tmp_path):
        root = str(tmp_path / "root")
        _write_skill(root, "ph-alpha", "ph-alpha",
                     'Use when the user asks to "deploy the flux capacitor now" '
                     'or mentions any of: alphafillerterm.')
        _write_skill(root, "ph-beta", "ph-beta",
                     'Use when the user asks to "deploy the flux capacitor now" '
                     'or mentions any of: betafillerterm.')
        allowlist = _empty_allowlist(tmp_path)
        report = design_gate.run_gate(root, allowlist_path=allowlist)

        assert report["ok"] is False
        matches = _by_term(report["phrase_collisions"], "phrase", "deploy the flux capacitor now")
        assert len(matches) == 1
        assert matches[0]["skills"] == ["ph-alpha", "ph-beta"]
        assert matches[0]["allowlisted"] is False
        assert report["keyword_collisions"] == []

    def test_dangling_reference_detected(self, tmp_path):
        root = str(tmp_path / "root")
        _write_skill(root, "zeta-one", "zeta-one",
                     'Use when the user asks to "handle zeta one" '
                     'or mentions any of: zetaoneterm.')
        _write_skill(root, "zeta-two", "zeta-two",
                     'Use when the user asks to "handle zeta two" '
                     'or mentions any of: zetatwoterm.')
        _write_skill(root, "omega-ref", "omega-ref",
                     'Use when the user asks to "handle omega things" '
                     'or mentions any of: omegatermunique. '
                     'Use when NOT: covers the zeta-ghost workflow instead; '
                     'that is a different concern.')
        allowlist = _empty_allowlist(tmp_path)
        report = design_gate.run_gate(root, allowlist_path=allowlist)

        assert report["ok"] is False
        matches = [d for d in report["dangling_references"]
                   if d["skill"] == "omega-ref" and d["token"] == "zeta-ghost"]
        assert len(matches) == 1
        assert matches[0]["allowlisted"] is False
        # zeta-one / zeta-two are real skills -- must never be flagged as dangling.
        assert not [d for d in report["dangling_references"] if d["token"] in ("zeta-one", "zeta-two")]

    def test_mutual_contradiction_detected(self, tmp_path):
        root = str(tmp_path / "root")
        _write_skill(root, "mc-alpha", "mc-alpha",
                     'Use when the user asks to "handle the alpha workflow" '
                     'or mentions any of: alphaonlyterm. '
                     'Use when NOT: wobblesprocket questions; that lives elsewhere, ask mc-beta.')
        _write_skill(root, "mc-beta", "mc-beta",
                     'Use when the user asks to "handle the beta workflow" '
                     'or mentions any of: betaonlyterm. '
                     'Use when NOT: wobblesprocket topics; mc-alpha covers that domain instead.')
        allowlist = _empty_allowlist(tmp_path)
        report = design_gate.run_gate(root, allowlist_path=allowlist)

        assert report["ok"] is False
        matches = [m for m in report["mutual_contradictions"]
                   if m["skill_a"] == "mc-alpha" and m["skill_b"] == "mc-beta"]
        assert len(matches) == 1
        assert matches[0]["shared_terms"] == ["wobblesprocket"]
        assert matches[0]["allowlisted"] is False
        # mc-alpha/mc-beta reference each other's real names -- must not
        # also register as dangling references.
        assert report["dangling_references"] == []


# ══════════════════════════════════════════════════════════════════════
# 3. Cerberus review regression fixes
# ══════════════════════════════════════════════════════════════════════

class TestCerberusRegressionFixes:

    def test_digit_led_skill_name_dangling_reference_is_detected(self, tmp_path):
        """Before the fix, the family-prefix token regex required a letter
        right after the hyphen, making the whole '-3d...' shape structurally
        unreachable. A dangling reference to a digit-led fake name must now
        be caught."""
        root = str(tmp_path / "root")
        _write_skill(root, "zzzfam-3dwidget", "zzzfam-3dwidget",
                     'Use when the user asks to "render the widget" '
                     'or mentions any of: zzzfamwidgetterm.')
        _write_skill(root, "zzzfam-refskill", "zzzfam-refskill",
                     'Use when the user asks to "handle ref things" '
                     'or mentions any of: zzzfamrefterm. '
                     'Use when NOT: the zzzfam-3dghost workflow; unrelated concern.')
        allowlist = _empty_allowlist(tmp_path)
        report = design_gate.run_gate(root, allowlist_path=allowlist)

        matches = [d for d in report["dangling_references"]
                   if d["skill"] == "zzzfam-refskill" and d["token"] == "zzzfam-3dghost"]
        assert len(matches) == 1
        assert report["ok"] is False

    def test_short_uppercase_acronym_collision_is_detected(self, tmp_path):
        """Before the fix, the plain length/hyphen/dot filter dropped every
        3-letter token, hiding real short-acronym collisions. An ALL-CAPS
        acronym in the source must survive the length floor."""
        root = str(tmp_path / "root")
        _write_skill(root, "ac-alpha", "ac-alpha",
                     'Use when the user asks to "handle the alpha acronym case" '
                     'or mentions any of: XQZ, acalphafiller.')
        _write_skill(root, "ac-beta", "ac-beta",
                     'Use when the user asks to "handle the beta acronym case" '
                     'or mentions any of: XQZ, acbetafiller.')
        allowlist = _empty_allowlist(tmp_path)
        report = design_gate.run_gate(root, allowlist_path=allowlist)

        matches = _by_term(report["keyword_collisions"], "term", "xqz")
        assert len(matches) == 1
        assert matches[0]["skills"] == ["ac-alpha", "ac-beta"]
        assert report["ok"] is False

    def test_generic_and_too_short_lowercase_tokens_do_not_collide(self, tmp_path):
        """'the' (an explicit GENERIC_TERMS entry) and 'ai' (below the
        absolute length floor) must never generate a keyword collision, even
        when claimed by 2+ skills verbatim."""
        root = str(tmp_path / "root")
        _write_skill(root, "gt-alpha", "gt-alpha",
                     'Use when the user asks to "handle alpha generic case" '
                     'or mentions any of: the, ai, gtalphaunique.')
        _write_skill(root, "gt-beta", "gt-beta",
                     'Use when the user asks to "handle beta generic case" '
                     'or mentions any of: the, ai, gtbetaunique.')
        allowlist = _empty_allowlist(tmp_path)
        report = design_gate.run_gate(root, allowlist_path=allowlist)

        assert _by_term(report["keyword_collisions"], "term", "the") == []
        assert _by_term(report["keyword_collisions"], "term", "ai") == []
        assert report["ok"] is True

    def test_zero_skills_scanned_fails_loud_json(self, tmp_path):
        empty_root = str(tmp_path / "nothing_here")
        os.makedirs(empty_root)
        allowlist = _empty_allowlist(tmp_path)
        report, rc = _run_gate_cli_json(empty_root, allowlist=allowlist)

        assert rc == 1
        assert report["ok"] is False
        assert report["error"] is not None
        assert "0 skills scanned" in report["error"]

    def test_zero_skills_scanned_fails_loud_human_report(self, tmp_path):
        empty_root = str(tmp_path / "nothing_here")
        os.makedirs(empty_root)
        allowlist = _empty_allowlist(tmp_path)
        rc, stdout, stderr = _run_gate_cli(empty_root, allowlist=allowlist, json_mode=False)

        assert rc == 1
        assert "FATAL" in stdout
        assert "Result: FATAL" in stdout
        assert "Result: CLEAN" not in stdout

    def test_allowlisted_collision_does_not_fail_the_gate(self, tmp_path):
        root = str(tmp_path / "root")
        _write_skill(root, "gate-alpha", "gate-alpha",
                     'Use when the user asks to "spin up alpha" '
                     'or mentions any of: gatewidget, gatealphafiller.')
        _write_skill(root, "gate-beta", "gate-beta",
                     'Use when the user asks to "spin up beta" '
                     'or mentions any of: gatewidget, gatebetafiller.')
        allowlist = _write_allowlist(tmp_path, keyword=["gatewidget"])

        report, rc = _run_gate_cli_json(root, allowlist=allowlist)
        assert rc == 0
        assert report["ok"] is True
        matches = _by_term(report["keyword_collisions"], "term", "gatewidget")
        assert len(matches) == 1
        assert matches[0]["allowlisted"] is True

        # Human report must still SHOW the finding, tagged allowlisted, never hidden.
        rc_h, stdout, _ = _run_gate_cli(root, allowlist=allowlist, json_mode=False)
        assert rc_h == 0
        assert "[allowlisted] 'gatewidget'" in stdout
        assert "Result: CLEAN" in stdout

    def test_new_unlisted_collision_still_fails_the_gate(self, tmp_path):
        """Same fixture as above, but with an allowlist that does NOT
        contain the finding -- must fail, tagged [NEW]."""
        root = str(tmp_path / "root")
        _write_skill(root, "gate-alpha", "gate-alpha",
                     'Use when the user asks to "spin up alpha" '
                     'or mentions any of: gatewidget, gatealphafiller.')
        _write_skill(root, "gate-beta", "gate-beta",
                     'Use when the user asks to "spin up beta" '
                     'or mentions any of: gatewidget, gatebetafiller.')
        allowlist = _empty_allowlist(tmp_path)

        report, rc = _run_gate_cli_json(root, allowlist=allowlist)
        assert rc == 1
        assert report["ok"] is False
        matches = _by_term(report["keyword_collisions"], "term", "gatewidget")
        assert matches[0]["allowlisted"] is False

        rc_h, stdout, _ = _run_gate_cli(root, allowlist=allowlist, json_mode=False)
        assert rc_h == 1
        assert "[NEW] 'gatewidget'" in stdout
        assert "Result: COLLISIONS FOUND" in stdout


# ══════════════════════════════════════════════════════════════════════
# 4. Cross-platform (utf-8, vendor-dir skipping, real CLI wiring)
# ══════════════════════════════════════════════════════════════════════

class TestCrossPlatform:

    def test_unicode_description_round_trips_via_real_cli(self, tmp_path):
        """Real subprocess run (exercises force_utf8_streams() on stdout, not
        just the in-process open(encoding='utf-8') read) with a description
        containing accented Latin, CJK, and an emoji."""
        root = str(tmp_path / "root")
        _write_skill(root, "uni-alpha", "uni-alpha",
                     'Use when the user asks to "café résumé naïve façade" '
                     'or mentions any of: uniqueunicodeterm. '
                     'Covers 日本語のテスト and emoji handling \U0001F389.')
        allowlist = _empty_allowlist(tmp_path)

        report, rc = _run_gate_cli_json(root, allowlist=allowlist)
        assert rc == 0
        assert report["ok"] is True
        assert report["skills_scanned"] == 1
        assert report["warnings"] == []

    def test_vendor_directories_are_never_scanned(self, tmp_path):
        """A SKILL.md sitting under .ref-repos/ or node_modules/ must be
        completely invisible to the gate -- not just 'doesn't collide', but
        never counted at all. Proven by planting a term that WOULD collide
        with the real skill if the vendor copy were scanned."""
        root = str(tmp_path / "root")
        _write_skill(root, "sd-alpha", "sd-alpha",
                     'Use when the user asks to "handle sd alpha" '
                     'or mentions any of: vendorleakterm.')
        _write_skill(root, os.path.join(".ref-repos", "vendored-skill"), "vendored-skill",
                     'Use when the user asks to "handle vendored thing" '
                     'or mentions any of: vendorleakterm.')
        _write_skill(root, os.path.join("node_modules", "vendored-skill-2"), "vendored-skill-2",
                     'Use when the user asks to "handle vendored thing two" '
                     'or mentions any of: vendorleakterm.')
        allowlist = _empty_allowlist(tmp_path)
        report = design_gate.run_gate(root, allowlist_path=allowlist)

        assert report["skills_scanned"] == 1
        assert report["ok"] is True
        assert _by_term(report["keyword_collisions"], "term", "vendorleakterm") == []

    def test_default_root_resolves_to_git_toplevel(self, tmp_path):
        """Without --root, the gate must resolve the project root via git
        rev-parse --show-toplevel (find_project_root), not the subprocess
        cwd by coincidence."""
        from conftest import git_cmd

        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
        _write_skill(repo, "root-skill", "root-skill",
                     'Use when the user asks to "handle the root skill" '
                     'or mentions any of: rootskillterm.')
        allowlist = _empty_allowlist(tmp_path)

        rc, out, err = run_script(DESIGN_GATE, repo, ["--json", "--allowlist", allowlist])
        report = json.loads(out)
        assert rc == 0
        assert report["ok"] is True
        assert report["skills_scanned"] == 1

    def test_nonexistent_root_path_is_a_clean_cli_error(self, tmp_path):
        bogus_root = str(tmp_path / "does_not_exist_at_all")
        rc, out, err = run_script(DESIGN_GATE, str(tmp_path), ["--root", bogus_root, "--json"])
        assert rc == 1
        assert "does not exist" in err

    def test_yaml_none_main_reports_missing_dependency(self, tmp_path, monkeypatch, capsys):
        """CLI-level early exit (main()'s own guard, independent of
        load_skill_frontmatter's function-level guard exercised earlier)."""
        root = str(tmp_path / "root")
        os.makedirs(root)
        monkeypatch.setattr(design_gate, "yaml", None)
        rc = design_gate.main(["--root", root])
        captured = capsys.readouterr()
        assert rc == 1
        assert "pyyaml" in captured.err.lower()


# ══════════════════════════════════════════════════════════════════════
# 5. Pure function unit tests (no filesystem, no subprocess)
# ══════════════════════════════════════════════════════════════════════

class TestExtractMentionTerms:

    def test_basic_comma_separated_list(self):
        desc = "Use when the user asks to \"thing\" or mentions any of: alpha, beta, gamma."
        assert design_gate.extract_mention_terms(desc) == ["alpha", "beta", "gamma"]

    def test_no_clause_returns_empty(self):
        assert design_gate.extract_mention_terms("Just a plain description with no convention.") == []

    def test_quote_aware_comma_split_preserves_apostrophe(self):
        desc = 'or mentions any of: "what\'s this called", plainterm.'
        assert design_gate.extract_mention_terms(desc) == ["what's this called", "plainterm"]


class TestExtractQuotedPhrases:

    def test_scoped_to_asks_to_clause_only(self):
        """Cerberus finding #5 regression: a quoted phrase inside 'Use when
        NOT' (with no intervening 'or mentions any of:') must NOT leak into
        the asks-to trigger phrase list."""
        desc = (
            'Use when the user asks to "make it look cool" or "make it fresh". '
            'Use when NOT: a generic "make this not look like AI slop" with no '
            'specifics; that critique is out of scope.'
        )
        assert design_gate.extract_quoted_phrases(desc) == ["make it look cool", "make it fresh"]

    def test_no_asks_to_clause_returns_empty(self):
        assert design_gate.extract_quoted_phrases("mentions any of: alpha, beta.") == []


class TestExtractUseWhenNot:

    def test_present_clause_extracted(self):
        desc = "Some prose. Use when NOT: this excluded topic; that other one."
        assert design_gate.extract_use_when_not(desc) == "this excluded topic; that other one."

    def test_absent_returns_none(self):
        assert design_gate.extract_use_when_not("No exclusion clause here at all.") is None

    def test_based_on_attribution_suffix_is_stripped(self):
        desc = "Use when NOT: excluded topic here. Based on Nielsen Norman Group research."
        result = design_gate.extract_use_when_not(desc)
        assert result == "excluded topic here."
        assert "Nielsen" not in result


class TestSplitExclusionClauses:

    def test_splits_on_semicolons(self):
        assert design_gate.split_exclusion_clauses("clause one; clause two; clause three") == [
            "clause one", "clause two", "clause three",
        ]

    def test_splits_on_or_when_no_semicolon(self):
        assert design_gate.split_exclusion_clauses("clause one or clause two") == [
            "clause one", "clause two",
        ]


class TestNormalizeTerm:

    def test_collapses_whitespace_and_lowercases(self):
        assert design_gate._normalize_term("  Some   TERM \n here ") == "some term here"


class TestIsDistinctive:

    def test_generic_term_filtered(self):
        assert design_gate._is_distinctive("use", "use") is False

    def test_below_absolute_length_floor_filtered(self):
        assert design_gate._is_distinctive("ai", "AI") is False

    def test_uppercase_acronym_survives_below_length_floor(self):
        assert design_gate._is_distinctive("xqz", "XQZ") is True

    def test_hyphenated_term_survives_below_length_floor(self):
        assert design_gate._is_distinctive("a-b", "a-b") is True

    def test_plain_short_lowercase_term_without_marker_filtered(self):
        assert design_gate._is_distinctive("abc", "abc") is False

    def test_ordinary_technical_noun_passes(self):
        assert design_gate._is_distinctive("webgl", "WebGL") is True


class TestSignificantWords:

    def test_all_generic_words_filtered_to_empty(self):
        assert design_gate._significant_words("this domain covers those branches instead") == set()

    def test_non_generic_words_kept(self):
        result = design_gate._significant_words("wobblecore telemetry buffering across gizmo-sprocket")
        assert result == {"wobblecore", "telemetry", "buffering", "across", "gizmo-sprocket"}

    def test_trailing_punctuation_is_stripped_from_token(self):
        assert design_gate._significant_words("trailing note.") == {"trailing", "note"}


class TestStem:

    def test_flash_flashed_share_a_stem(self):
        assert design_gate._stem("flash") == design_gate._stem("flashed")

    def test_print_printing_share_a_stem(self):
        assert design_gate._stem("printing") == design_gate._stem("prints") == "print"

    def test_never_shortens_below_three_chars(self):
        assert design_gate._stem("bus") == "bus"


class TestExpandVariants:

    def test_hyphenated_subparts_expanded(self):
        variants = design_gate._expand_variants("prefers-reduced-motion")
        assert "prefers-reduced-motion" in variants
        assert "motion" in variants
        assert "prefer" in variants

    def test_slash_subparts_expanded_with_length_floor(self):
        variants = design_gate._expand_variants("3d/webgl")
        assert "webgl" in variants
        assert "3d/webgl" in variants
        assert "3d" not in variants  # sub-part below the 4-char floor is excluded


class TestFindingKey:

    def test_keyword_collision_key(self):
        assert design_gate._finding_key("keyword_collisions", {"term": "gdpr", "skills": []}) == "gdpr"

    def test_phrase_collision_key(self):
        assert design_gate._finding_key(
            "phrase_collisions", {"phrase": "onboarding flow", "skills": []}
        ) == "onboarding flow"

    def test_dangling_reference_key(self):
        key = design_gate._finding_key(
            "dangling_references", {"skill": "foo-bar", "token": "foo-ghost"}
        )
        assert key == "foo-bar::foo-ghost"

    def test_mutual_contradiction_key(self):
        key = design_gate._finding_key(
            "mutual_contradictions",
            {"skill_a": "a", "skill_b": "b", "shared_terms": ["x", "y"]},
        )
        assert key == "a::b::x,y"

    def test_unknown_category_raises(self):
        with pytest.raises(ValueError):
            design_gate._finding_key("not_a_real_category", {})


class TestDefaultAllowlistPath:

    def test_resolves_next_to_bin_parent(self):
        expected = os.path.join(os.path.dirname(BIN_DIR), "design-gate-allowlist.json")
        assert design_gate.default_allowlist_path() == expected


class TestLoadAllowlist:

    def test_missing_file_returns_empty_structure(self, tmp_path):
        missing = str(tmp_path / "does-not-exist.json")
        allowlist = design_gate.load_allowlist(missing)
        assert allowlist == {cat: set() for cat in design_gate._ALLOWLIST_CATEGORIES}

    def test_malformed_json_warns_and_returns_empty(self, tmp_path, capsys):
        path = tmp_path / "broken.json"
        path.write_text("{not valid json", encoding="utf-8")
        allowlist = design_gate.load_allowlist(str(path))
        assert allowlist == {cat: set() for cat in design_gate._ALLOWLIST_CATEGORIES}
        captured = capsys.readouterr()
        assert "could not read allowlist" in captured.err

    def test_non_dict_json_warns_and_returns_empty(self, tmp_path, capsys):
        path = tmp_path / "list.json"
        path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
        allowlist = design_gate.load_allowlist(str(path))
        assert allowlist == {cat: set() for cat in design_gate._ALLOWLIST_CATEGORIES}
        captured = capsys.readouterr()
        assert "did not parse to a JSON object" in captured.err

    def test_valid_file_loads_sets(self, tmp_path):
        path = _write_allowlist(tmp_path, keyword=["gdpr", "hipaa"], phrase=["onboarding flow"])
        allowlist = design_gate.load_allowlist(path)
        assert allowlist["keyword_collisions"] == {"gdpr", "hipaa"}
        assert allowlist["phrase_collisions"] == {"onboarding flow"}
        assert allowlist["dangling_references"] == set()
        assert allowlist["mutual_contradictions"] == set()


class TestAnnotateAllowlisted:

    def test_marks_allowed_and_unallowed_findings(self):
        findings = [{"term": "gdpr"}, {"term": "brandnewterm"}]
        allowlist = {"keyword_collisions": {"gdpr"}}
        result = design_gate._annotate_allowlisted(findings, "keyword_collisions", allowlist)
        assert result[0]["allowlisted"] is True
        assert result[1]["allowlisted"] is False


class TestTag:

    def test_allowlisted_tag(self):
        assert design_gate._tag({"allowlisted": True}) == "allowlisted"

    def test_new_tag(self):
        assert design_gate._tag({"allowlisted": False}) == "NEW"


class TestBuildSkillRecords:

    def test_wordbag_and_warnings_shape(self, tmp_path):
        root = str(tmp_path / "root")
        _write_skill(root, "bsr-alpha", "bsr-alpha",
                     'Use when the user asks to "handle bsr alpha" '
                     'or mentions any of: bsrwidget, prefers-reduced-motion.')
        _write_raw(root, "bsr-broken", "no frontmatter here\n")
        skill_mds = design_gate.find_skill_md_files(root)
        records, warnings = design_gate.build_skill_records(skill_mds)

        assert len(records) == 1
        assert len(warnings) == 1
        record = records[0]
        assert record["name"] == "bsr-alpha"
        assert record["mention_terms"] == ["bsrwidget", "prefers-reduced-motion"]
        assert "bsrwidget" in record["wordbag"]
        # Hyphenated compounds stay as ONE wordbag entry here -- only
        # _expand_wordset() (used later, by find_mutual_contradictions)
        # splits them into sub-parts, not _significant_words() itself.
        assert "prefers-reduced-motion" in record["wordbag"]
        assert "handle" in record["wordbag"]  # from the asks-to quoted phrase


class TestFormatHumanReport:

    def test_clean_report_shape(self, tmp_path):
        root = str(tmp_path / "root")
        _write_skill(root, "clean-skill", "clean-skill",
                     'Use when the user asks to "do the clean thing" '
                     'or mentions any of: cleanuniqueterm.')
        allowlist = _empty_allowlist(tmp_path)
        report = design_gate.run_gate(root, allowlist_path=allowlist)
        text = design_gate.format_human_report(report)

        assert "Keyword collisions: none" in text
        assert "Quoted phrase collisions: none" in text
        assert "Dangling skill references: none" in text
        assert "Mutual contradictions: none" in text
        assert "Result: CLEAN" in text

    def test_collision_report_shape(self, tmp_path):
        root = str(tmp_path / "root")
        _write_skill(root, "fh-alpha", "fh-alpha",
                     'Use when the user asks to "handle fh alpha" '
                     'or mentions any of: fhcollisionterm.')
        _write_skill(root, "fh-beta", "fh-beta",
                     'Use when the user asks to "handle fh beta" '
                     'or mentions any of: fhcollisionterm.')
        allowlist = _empty_allowlist(tmp_path)
        report = design_gate.run_gate(root, allowlist_path=allowlist)
        text = design_gate.format_human_report(report)

        assert "[NEW] 'fhcollisionterm' claimed by: fh-alpha, fh-beta" in text
        assert "Result: COLLISIONS FOUND" in text
