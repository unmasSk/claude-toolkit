"""
Contract (RED, test-first) for #89 step 5.2: the generated hooks table moves
out of the boot-read `skills/unmassk-memory/SKILL.md` into
`skills/unmassk-memory/references/hooks.md`, loaded on demand.

Every test drives the real door, `bin/hooks_doc_sync.py`, against a
disposable plugin root in tmp_path (`--plugin-root`), never the shipped one,
except the last class, which checks the shipped plugin as it is.

The expected table rows come from parsing hooks/hooks.json here, in the test
(the file Claude Code reads), never from lib/hooks_doc.py.
"""

import json
import os
import re
import shutil
import sys

import pytest

from conftest import SOURCE_ROOT, BIN_DIR, run_cmd

SYNC_SCRIPT = os.path.join(BIN_DIR, "hooks_doc_sync.py")
REAL_HOOKS_DIR = os.path.join(SOURCE_ROOT, "hooks")
SKILL_DIR_REL = os.path.join("skills", "unmassk-memory")
REFERENCE_REL = os.path.join(SKILL_DIR_REL, "references", "hooks.md")
SKILL_REL = os.path.join(SKILL_DIR_REL, "SKILL.md")

# Written by hand from the contract (the markers are the file format).
BEGIN = "<!-- BEGIN unmassk-active-hooks (generated from hooks/hooks.json — do not edit by hand) -->"
END = "<!-- END unmassk-active-hooks -->"

SKILL_WITHOUT_TABLE = (
    "# unmassk-memory\n\n## The hooks that are live\n\n"
    "Full table: `references/hooks.md`.\n\n## After\n\nhand-written prose\n"
)
REFERENCE_PROSE_BELOW = "\nHand-written judgment below the table.\n"


def _declared_hooks(hooks_json_path):
    """(event, hook filename) per declared command, in file order."""
    with open(hooks_json_path, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for event, groups in data["hooks"].items():
        for group in groups:
            for entry in group["hooks"]:
                m = re.search(r"hooks/([^/\s]+\.py)", entry["command"])
                if m:
                    out.append((event, m.group(1)))
    return out


def _table_rows(text):
    """(event, hook filename) per table row between the markers."""
    body = text[text.index(BEGIN) + len(BEGIN):text.index(END)]
    rows = []
    for line in body.splitlines():
        cells = [c.strip().strip("`") for c in re.split(r"(?<!\\)\|", line)]
        if len(cells) >= 5 and cells[3].endswith(".py"):
            rows.append((cells[1], cells[3].split("`")[0].strip()))
    return rows


def _declared_hooks_full(hooks_json_path):
    """(event, matcher, hook filename, timeout) per declared command, from
    hooks.json as Claude Code reads it. A missing matcher or timeout is "—"."""
    with open(hooks_json_path, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for event, groups in data["hooks"].items():
        for group in groups:
            for entry in group["hooks"]:
                m = re.search(r"hooks/([^/\s]+\.py)", entry["command"])
                if m:
                    timeout = entry.get("timeout")
                    out.append((
                        event,
                        group.get("matcher") or "—",
                        m.group(1),
                        f"{timeout}s" if timeout is not None else "—",
                    ))
    return out


def _table_rows_full(text):
    """All four columns per table row; an escaped pipe in a cell is a pipe."""
    body = text[text.index(BEGIN) + len(BEGIN):text.index(END)]
    rows = []
    for line in body.splitlines():
        cells = [c.strip().strip("`").replace("\\|", "|")
                 for c in re.split(r"(?<!\\)\|", line)]
        if len(cells) >= 6 and cells[3].endswith(".py"):
            rows.append((cells[1], cells[2], cells[3], cells[4]))
    return rows


def _make_plugin_root(tmp_path, reference_text, skill_text=SKILL_WITHOUT_TABLE):
    """Disposable plugin root: a copy of the real hooks/ plus the two docs.
    reference_text None means references/hooks.md is absent."""
    root = tmp_path / "plugin"
    shutil.copytree(REAL_HOOKS_DIR, root / "hooks",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (root / SKILL_DIR_REL / "references").mkdir(parents=True)
    (root / SKILL_REL).write_text(skill_text, encoding="utf-8")
    if reference_text is not None:
        (root / REFERENCE_REL).write_text(reference_text, encoding="utf-8")
    return root


def _empty_reference():
    return f"# Live hooks\n\n{BEGIN}\nstale\n{END}\n{REFERENCE_PROSE_BELOW}"


def _sync(root, *extra):
    return run_cmd([sys.executable, SYNC_SCRIPT, "--plugin-root", str(root), *extra],
                   cwd=str(root))


class TestWriteTargetsReferencesHooks:
    def test_should_write_every_declared_hook_into_references_hooks_md(self, tmp_path):
        # Bug caught: --write still aimed at SKILL.md (or misses a hook).
        root = _make_plugin_root(tmp_path, _empty_reference())
        rc, out, err = _sync(root, "--write")
        assert rc == 0, (rc, out, err)
        written = (root / REFERENCE_REL).read_text(encoding="utf-8")
        assert _table_rows(written) == _declared_hooks(root / "hooks" / "hooks.json")

    def test_should_keep_hand_written_prose_of_references_hooks_md(self, tmp_path):
        # Bug caught: the rewrite eats the judgment written below the markers.
        root = _make_plugin_root(tmp_path, _empty_reference())
        rc, out, err = _sync(root, "--write")
        assert rc == 0, (rc, out, err)
        written = (root / REFERENCE_REL).read_text(encoding="utf-8")
        assert written.startswith("# Live hooks\n\n" + BEGIN), written
        assert written.endswith(END + "\n" + REFERENCE_PROSE_BELOW), written

    def test_should_leave_skill_md_byte_identical_when_writing(self, tmp_path):
        # Bug caught: the old target keeps being written. The SKILL.md here
        # still carries an old block, so a writer aimed at it would change it.
        old_skill = f"# unmassk-memory\n\n{BEGIN}\nold table\n{END}\n"
        root = _make_plugin_root(tmp_path, _empty_reference(), skill_text=old_skill)
        rc, out, err = _sync(root, "--write")
        assert rc == 0, (rc, out, err)
        assert (root / SKILL_REL).read_text(encoding="utf-8") == old_skill


class TestCheckReadsReferencesHooks:
    def test_should_report_in_sync_after_write_round_trip(self, tmp_path):
        # Bug caught: check and --write look at different files.
        root = _make_plugin_root(tmp_path, _empty_reference())
        rc_w, out_w, err_w = _sync(root, "--write")
        assert rc_w == 0, (rc_w, out_w, err_w)
        rc, out, err = _sync(root)
        assert rc == 0, (rc, out, err)
        assert out.startswith("ok:"), out

    def test_should_fail_check_when_hooks_json_drops_a_documented_hook(self, tmp_path):
        # Bug caught: a hook removed from hooks.json still documented, unseen.
        root = _make_plugin_root(tmp_path, _empty_reference())
        rc_w, out_w, err_w = _sync(root, "--write")
        assert rc_w == 0, (rc_w, out_w, err_w)
        hooks_json = root / "hooks" / "hooks.json"
        before = {name for _, name in _declared_hooks(str(hooks_json))}
        data = json.loads(hooks_json.read_text(encoding="utf-8"))
        del data["hooks"]["Notification"]
        hooks_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
        # Expected names come from this run's own edit, never typed by hand.
        dropped = before - {name for _, name in _declared_hooks(str(hooks_json))}
        assert dropped, "the deleted group must drop at least one hook file"
        rc, out, err = _sync(root)
        assert rc == 1, (rc, out, err)
        assert out.startswith("error:"), out
        for name in dropped:
            assert name in out, (name, out)

    def test_should_not_report_ok_when_references_hooks_md_is_absent(self, tmp_path):
        # Bug caught: a missing table reported as a clean bill. SKILL.md here
        # holds a block that IS in sync, so a check still reading SKILL.md
        # would say ok over the missing reference.
        # Setup input built by the library (not an expected value).
        from hooks_doc import parse_hook_declarations, render_hooks_block
        root = _make_plugin_root(tmp_path, None)
        body = render_hooks_block(str(root), parse_hook_declarations(str(root)))
        (root / SKILL_REL).write_text(f"# m\n\n{BEGIN}\n{body}\n{END}\n", encoding="utf-8")
        rc, out, err = _sync(root)
        assert rc == 1, (rc, out, err)
        assert not out.startswith("ok:"), out


class TestCheckSeesMatcherAndTimeout:
    def _drift(self, tmp_path, field, value):
        root = _make_plugin_root(tmp_path, _empty_reference())
        rc_w, out_w, err_w = _sync(root, "--write")
        assert rc_w == 0, (rc_w, out_w, err_w)
        hooks_json = root / "hooks" / "hooks.json"
        data = json.loads(hooks_json.read_text(encoding="utf-8"))
        group = data["hooks"]["PreToolUse"][0]
        if field == "matcher":
            group["matcher"] = value
        else:
            group["hooks"][0]["timeout"] = value
        hooks_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return _sync(root)

    def test_should_fail_check_when_a_hook_matcher_changes(self, tmp_path):
        # Bug caught: the check compares event and file only, so a matcher
        # edited in hooks.json leaves the table wrong and still "ok".
        rc, out, err = self._drift(tmp_path, "matcher", "Bash|Write")
        assert rc == 1, (rc, out, err)
        assert not out.startswith("ok:"), out

    def test_should_fail_check_when_a_hook_timeout_changes(self, tmp_path):
        # Bug caught: same, for the timeout column.
        rc, out, err = self._drift(tmp_path, "timeout", 61)
        assert rc == 1, (rc, out, err)
        assert not out.startswith("ok:"), out


class TestRefusalAtNewLocation:
    def test_should_refuse_and_change_nothing_when_reference_markers_missing(self, tmp_path):
        # Guard (green by design today): no markers -> refuse, never guess.
        text = "# Live hooks\n\nno markers here\n"
        root = _make_plugin_root(tmp_path, text)
        rc, out, err = _sync(root, "--write")
        assert rc == 1, (rc, out, err)
        assert out.startswith("failed:"), out
        assert (root / REFERENCE_REL).read_text(encoding="utf-8") == text
        assert (root / SKILL_REL).read_text(encoding="utf-8") == SKILL_WITHOUT_TABLE


class TestShippedPlugin:
    def test_shipped_references_hooks_md_is_in_sync_with_hooks_json(self):
        # Bug caught: the move shipped without the generated table.
        path = os.path.join(SOURCE_ROOT, REFERENCE_REL)
        assert os.path.isfile(path), path
        with open(path, encoding="utf-8") as f:
            rows = _table_rows(f.read())
        assert rows == _declared_hooks(os.path.join(REAL_HOOKS_DIR, "hooks.json"))

    def test_shipped_table_matches_every_column_of_hooks_json(self):
        # Bug caught (Moriarty, deception): the in-sync test above reads
        # event and file only; a matcher or timeout changed in hooks.json
        # without regenerating the table stays green.
        with open(os.path.join(SOURCE_ROOT, REFERENCE_REL), encoding="utf-8") as f:
            rows = _table_rows_full(f.read())
        assert rows == _declared_hooks_full(os.path.join(REAL_HOOKS_DIR, "hooks.json"))

    def test_shipped_skill_md_has_no_table_and_points_to_reference(self):
        # Bug caught: two copies of the table in what Claude reads, or the
        # boot-read skill loses the pointer to the full version (D-094).
        with open(os.path.join(SOURCE_ROOT, SKILL_REL), encoding="utf-8") as f:
            skill = f.read()
        assert BEGIN not in skill and END not in skill
        assert "references/hooks.md" in skill
