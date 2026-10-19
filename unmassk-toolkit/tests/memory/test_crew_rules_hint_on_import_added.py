"""
The SessionStart start that ADDS the rules import to CLAUDE.md tells
Claude to read the rules now (#95, D-131 follow-up).

Why it exists: Claude Code reads CLAUDE.md BEFORE the SessionStart hooks
run. When `hooks/session-start-crew.py` is the one that writes the
`@.claude/project-memory/rules.md` import (an old toolkit block upgraded,
or a CLAUDE.md created), the import only loads at the NEXT session -- so
in this one the owner's rules would silently not bind. The hook prints a
line telling Claude to read the file now.

Contract (task 2026-10-19, written by hand here, never read from the
code under test):
  - import added by this start + rules file exists -> the output names
    `.claude/project-memory/rules.md` and tells Claude to read it now,
    exactly once;
  - import already in the CLAUDE.md Claude Code loaded (block current, or
    the line put there by hand) -> nothing extra;
  - rules file absent -> nothing extra;
  - the hint is OUTPUT only: the owner's text and the other blocks of
    CLAUDE.md are left byte-for-byte as they were.

Everything is driven through the real hook as a separate process, in
disposable git repos, with a disposable HOME. Assertions read the hook's
stdout and the file on disk only -- never the hint's internals, which are
being moved to a lib module.

NO production code is touched by this file.
"""

import os
import re
import sys

import pytest

from .conftest import (
    with_searched,
    _TOOLKIT_ROOT,
    make_session_start_payload,
    run_hook_with_payload,
    run_memory_script,
    seed_config_json,
)

LIB_DIR = os.path.join(_TOOLKIT_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

# Input only: builds the three untouched blocks of an existing project's
# CLAUDE.md. No expected value is read from it.
from managed_blocks import BLOCKS  # noqa: E402

# From the contract, by hand.
RULES_RELPATH = ".claude/project-memory/rules.md"
RULES_IMPORT_LINE = "@" + RULES_RELPATH
TOOLKIT_BEGIN = "<!-- BEGIN unmassk-toolkit (managed block — do not edit) -->"
TOOLKIT_END = "<!-- END unmassk-toolkit -->"

# Frozen snapshot of the toolkit block every pre-2a project carries on
# disk (no rules import). It no longer exists in the code.
OLD_TOOLKIT_BODY = """\
## unmassk-toolkit Active

This project uses the **unmassk toolkit**. Its memory lives in git, and it is
what you know about this project -- not a log you may consult.

**On every session start**, you MUST:
1. Read the session-start briefing already in your context: the last Next,
   every blocker, every restriction, the counts and the checks
2. Use the Skill tool with `skill="unmassk-core"` (TOOL CALL, not bash)
3. Use the Skill tool with `skill="unmassk-memory"` (TOOL CALL, not bash)
4. Tell the user the menu of the day, then respond

**Four rules that hold even when no skill is loaded:**
- Memory is a commit. Never write it into a file.
- The indexes and the zone list are written by the commands. Never by hand.
- A restriction is retired by asking the user, never on your own judgement — unless you have checked that the piece it describes no longer exists anywhere (not just moved or renamed): then it is retired in the same act, and said.
- Never ask the user to run a command -- you run it."""

USER_HEAD = "# My project\n\nOwner notes written by hand, above the blocks.\n\n"
USER_TAIL = "\n\n## My own section\n\nkeep me exactly as I am, byte for byte.\n"
RULES_BODY = "# Rules\n\n- [user] answer in the owner's language\n"


@pytest.fixture(autouse=True)
def _disposable_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return str(home)


# ── Builders and readers ─────────────────────────────────────────────────


def _other_blocks():
    return [f"{b['begin']}\n{b['body']}\n{b['end']}" for b in BLOCKS[1:]]


def _old_project_claude_md(extra_head=""):
    blocks = [f"{TOOLKIT_BEGIN}\n{OLD_TOOLKIT_BODY}\n{TOOLKIT_END}"] + _other_blocks()
    return USER_HEAD + extra_head + "\n\n".join(blocks) + USER_TAIL


def _write(repo, rel, text):
    path = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _read(repo, rel):
    with open(os.path.join(repo, rel), encoding="utf-8", newline="") as f:
        return f.read()


def _start(repo, cwd=None):
    rc, out, err = run_hook_with_payload(
        "session-start-crew.py", make_session_start_payload(cwd or repo), cwd=cwd or repo
    )
    assert rc == 0, f"session-start-crew.py rc={rc}\nstdout={out}\nstderr={err}"
    return out


def _hint_lines(out):
    """Lines of the hook output that send Claude to the rules file now."""
    return [l for l in out.splitlines()
            if RULES_RELPATH in l and re.search(r"\bread\b", l, re.I)
            and re.search(r"\bnow\b", l, re.I)]


def _rules_mentions(out):
    return [l for l in out.splitlines() if "rules.md" in l]


def _assert_import_written(repo):
    lines = [l.strip() for l in _read(repo, "CLAUDE.md").splitlines()]
    assert RULES_IMPORT_LINE in lines, (
        "precondition: this start did not write the rules import into CLAUDE.md"
    )


# ── The hint fires on the start that adds the import ─────────────────────


def test_should_tell_claude_to_read_the_rules_now_once_when_an_old_block_is_upgraded(tmp_repo):
    """Bug caught: the start that upgrades the old block stays silent, so
    the owner's rules do not bind for the whole first session after the
    upgrade (the import only loads next session)."""
    _write(tmp_repo, "CLAUDE.md", _old_project_claude_md())
    _write(tmp_repo, RULES_RELPATH, RULES_BODY)

    out = _start(tmp_repo)

    _assert_import_written(tmp_repo)
    assert len(_hint_lines(out)) == 1, (
        f"expected exactly one line telling Claude to read {RULES_RELPATH} now:\n{out}"
    )


def test_should_tell_claude_to_read_the_rules_now_when_the_start_creates_claude_md(tmp_repo):
    """Bug caught: the 'Created CLAUDE.md' path forgets the hint."""
    _write(tmp_repo, RULES_RELPATH, RULES_BODY)
    assert not os.path.exists(os.path.join(tmp_repo, "CLAUDE.md"))

    out = _start(tmp_repo)

    _assert_import_written(tmp_repo)
    assert len(_hint_lines(out)) == 1, f"no single read-now hint on CLAUDE.md creation:\n{out}"


def test_should_tell_claude_to_read_the_rules_now_when_an_owner_claude_md_had_no_blocks(tmp_repo):
    """A project whose CLAUDE.md is the owner's text only (blocks appended
    by this start). Bug caught: the hint only fires when an existing toolkit
    block is replaced, not when the blocks are added for the first time."""
    _write(tmp_repo, "CLAUDE.md", USER_HEAD + "Just my notes.\n")
    _write(tmp_repo, RULES_RELPATH, RULES_BODY)

    out = _start(tmp_repo)

    _assert_import_written(tmp_repo)
    assert len(_hint_lines(out)) == 1, f"no single read-now hint when blocks were added:\n{out}"


def test_should_resolve_the_hint_against_the_repo_root_when_the_session_starts_in_a_subfolder(
    tmp_repo,
):
    """Claude Code often starts in a subfolder. Bug caught: the rules file
    is looked up relative to the current folder, so the hint never fires
    for a project opened below its root."""
    _write(tmp_repo, "CLAUDE.md", _old_project_claude_md())
    _write(tmp_repo, RULES_RELPATH, RULES_BODY)
    sub = os.path.join(tmp_repo, "src", "deep")
    os.makedirs(sub)

    out = _start(tmp_repo, cwd=sub)

    _assert_import_written(tmp_repo)
    assert len(_hint_lines(out)) == 1, f"no hint when started from a subfolder:\n{out}"


def test_should_name_the_file_gitmem_rule_wrote_when_the_hint_fires(tmp_repo):
    """Round-trip through the real producer of rules.md. Bug caught: the
    hint names a path the rule command never writes, so Claude opens the
    wrong file (or none) and the rules still do not bind."""
    seed_config_json(tmp_repo, repo_type="trunk")
    rule_text = "answer in the owner's language, every single message"
    rc, out, err = run_memory_script(
        "rule.py", with_searched([rule_text, "--kind", "user", "--quote", "habla en mi idioma"]),
        cwd=tmp_repo,
    )
    assert rc == 0, f"gitmem rule failed: stdout={out!r} stderr={err!r}"
    _write(tmp_repo, "CLAUDE.md", _old_project_claude_md())

    hint = _hint_lines(_start(tmp_repo))
    assert len(hint) == 1, f"expected one read-now hint, got {hint}"
    named = [t.rstrip(".,;:") for t in hint[0].split() if t.rstrip(".,;:").endswith("rules.md")]
    assert named, f"the hint names no rules.md path: {hint[0]!r}"
    resolved = os.path.join(tmp_repo, named[0])
    assert os.path.isfile(resolved), f"hint path does not exist from the repo root: {resolved}"
    with open(resolved, encoding="utf-8") as f:
        assert rule_text in f.read(), f"{resolved} does not hold the rule gitmem rule saved"


# ── Silent when Claude Code already loaded the import, or no rules ───────


def test_should_say_nothing_about_the_rules_when_the_block_was_already_current(tmp_repo):
    """Second start after the upgrade: Claude Code loaded the import at
    launch. Bug caught: the hint fires on every start, nagging Claude to
    re-read rules that are already in context."""
    _write(tmp_repo, "CLAUDE.md", _old_project_claude_md())
    _write(tmp_repo, RULES_RELPATH, RULES_BODY)
    first = _start(tmp_repo)
    assert _hint_lines(first), f"precondition: the first start gave no hint:\n{first}"
    before = _read(tmp_repo, "CLAUDE.md")

    out = _start(tmp_repo)

    assert "All managed blocks up to date" in out, f"second start was not a no-op:\n{out}"
    assert _read(tmp_repo, "CLAUDE.md") == before
    assert not _rules_mentions(out), f"rules mentioned on a start that added nothing:\n{out}"


def test_should_say_nothing_about_the_rules_when_the_owner_had_the_import_outside_the_block(
    tmp_repo,
):
    """The import line already sat in the owner's own text, so Claude Code
    loaded it at launch even though this start upgrades the old block.
    Bug caught: the hint looks only at the toolkit block (or only at the
    new content) and tells Claude to re-read what is already loaded."""
    _write(tmp_repo, "CLAUDE.md", _old_project_claude_md(extra_head=RULES_IMPORT_LINE + "\n\n"))
    _write(tmp_repo, RULES_RELPATH, RULES_BODY)

    out = _start(tmp_repo)

    block = _read(tmp_repo, "CLAUDE.md").split(TOOLKIT_BEGIN, 1)[1].split(TOOLKIT_END, 1)[0]
    assert RULES_IMPORT_LINE in block, "precondition: the old block was not upgraded"
    assert not _rules_mentions(out), f"rules hint although the import was already loaded:\n{out}"


@pytest.mark.parametrize("claude_md", ["old-block", "absent"])
def test_should_say_nothing_about_the_rules_when_the_rules_file_does_not_exist(
    tmp_repo, claude_md
):
    """Bug caught: Claude is sent to read a file that is not there, on
    every project that has no rules yet."""
    if claude_md == "old-block":
        _write(tmp_repo, "CLAUDE.md", _old_project_claude_md())

    out = _start(tmp_repo)

    _assert_import_written(tmp_repo)
    assert not _rules_mentions(out), f"rules hint with no rules file:\n{out}"


# ── The hint is output only: CLAUDE.md keeps the rest untouched ──────────


def test_should_leave_the_owner_text_and_other_blocks_untouched_when_the_hint_fires(tmp_repo):
    """Bug caught: the hint is written into CLAUDE.md (it would fire
    forever and pollute the owner's file), or the upgrade that triggers it
    eats the owner's text or rewrites the other three blocks."""
    original = _old_project_claude_md()
    _write(tmp_repo, "CLAUDE.md", original)
    _write(tmp_repo, RULES_RELPATH, RULES_BODY)

    out = _start(tmp_repo)
    hint = _hint_lines(out)
    assert hint, f"precondition: no hint fired:\n{out}"
    # On Windows the hook rewrites CLAUDE.md in text mode, so every line ends
    # in CRLF -- a uniform, correct Windows file. The LF literals below are
    # about the owner's words, not line endings: normalize before comparing,
    # as test_issue63_orphaned_end_preserves_user_content.py does (I-007).
    text = _read(tmp_repo, "CLAUDE.md").replace("\r\n", "\n")

    assert text.startswith(USER_HEAD), f"text above the blocks changed:\n{text[:300]}"
    assert text.endswith(USER_TAIL), f"text below the blocks changed:\n{text[-300:]}"
    for block in _other_blocks():
        assert text.count(block) == 1, f"another managed block changed:\n{block[:120]}"
    assert hint[0].strip() not in text, "the hint line leaked into CLAUDE.md"
    assert _read(tmp_repo, RULES_RELPATH) == RULES_BODY, "the rules file was modified"
