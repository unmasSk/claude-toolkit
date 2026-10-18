"""
Contract (test-first, RED) -- issue #95, phase 2a, decisions D-087 + D-131.

The owner's rules reach every session through a CLAUDE.md import, not
through hook output (D-131: hook output above 10,000 characters is cut by
Claude Code, and dies with the hook timeout; a CLAUDE.md `@path` import is
loaded whole at launch by Claude Code itself).

What the unmassk-toolkit managed block must carry, once written into a
project's CLAUDE.md by the REAL writers (never by calling
`upsert_managed_blocks()` from the test):
  - an import of `.claude/project-memory/rules.md` that Claude Code will
    expand: an `@` path on its own line, outside any code fence, code span
    or HTML comment;
  - a sentence, next to that import, saying those rules bind from the
    first message;
  - a step 1 that no longer claims the briefing is "already in your
    context": it sends Claude to the boot report whose path the `[memory]`
    lines of the session start give, and says that if no such line or no
    report arrived the boot failed and the user is told first.
Existing projects get it on their next session start: the old block is
upgraded in place, the user's own text around it untouched.

Writers exercised (the doors a real project goes through):
  - `hooks/session-start-crew.py`, the SessionStart hook that writes the
    managed blocks every session;
  - `bin/git-memory-install.py --auto`, the installer, which shares
    `lib/managed_blocks.py` (lib/install_apply.py imports it).

Expected values come from the contract (plan
docs/plan/feat-95-rules-at-boot.md 2a, D-131) and from independent real
producers: the path `gitmem rule` actually writes to, and the line prefix
the real boot actually prints -- never from `managed_blocks.BLOCKS`.

How Claude Code expands an import (code.claude.com/docs/en/memory, read for
D-131 on 2026-10-19): `@path` imports are not evaluated inside markdown
code spans or code blocks; relative paths resolve against the file that
holds the import. `_expandable_imports()` below is that rule, written
separately from the code under test.

Every test here runs with a disposable HOME (autouse fixture below): the
installer, run directly or by boot_launcher.py on an uninstalled project,
overwrites ~/.local/bin/gitmem, and must never touch the owner's.

NO production code is touched by this file.
"""

import os
import re
import subprocess
import sys

import pytest

from .conftest import (
    _TOOLKIT_ROOT,
    make_session_start_payload,
    run_hook_with_payload,
    run_memory_script,
    seed_config_json,
)

LIB_DIR = os.path.join(_TOOLKIT_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

# Input only: used to BUILD the three untouched blocks of an existing
# project's CLAUDE.md. No assertion reads its expected value from here.
from managed_blocks import BLOCKS  # noqa: E402

INSTALLER = os.path.join(_TOOLKIT_ROOT, "bin", "git-memory-install.py")

# From the contract (plan 2a, D-131), written by hand.
RULES_RELPATH = ".claude/project-memory/rules.md"
TOOLKIT_BEGIN = "<!-- BEGIN unmassk-toolkit (managed block — do not edit) -->"
TOOLKIT_END = "<!-- END unmassk-toolkit -->"
OLD_CLAIM = "already in your context"

# What every existing project carries on disk today (toolkit 1.47.x, the
# body this repository's own CLAUDE.md still has). A frozen snapshot on
# purpose: once 2a lands this text exists nowhere in the code, only in the
# CLAUDE.md files of projects that have not had a session start since.
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
USER_TAIL = "\n\n## My own section\n\nkeep me exactly as I am -- `@not/an/import.md`\n"


@pytest.fixture(autouse=True)
def _disposable_home(tmp_path, monkeypatch):
    """Every subprocess of this file inherits a throwaway HOME: the
    installer writes the gitmem launcher under ~/.local/bin, and a test
    must never rewrite the owner's real one (Argus SEC-MED-001)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return str(home)


# ── Writers (the real doors) ─────────────────────────────────────────────


def _run_session_start_crew(repo):
    rc, out, err = run_hook_with_payload(
        "session-start-crew.py", make_session_start_payload(repo), cwd=repo
    )
    assert rc == 0, f"session-start-crew.py rc={rc}\nstdout={out}\nstderr={err}"
    return out


def _run_installer(repo):
    result = subprocess.run(
        [sys.executable, INSTALLER, "--auto"],
        cwd=repo, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120,
    )
    assert result.returncode == 0, (
        f"installer rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    return result.stdout


WRITERS = {
    "session-start-crew": _run_session_start_crew,
    "installer": _run_installer,
}


def _claude_md(repo):
    with open(os.path.join(repo, "CLAUDE.md"), encoding="utf-8") as f:
        return f.read()


def _written_claude_md(repo, writer):
    WRITERS[writer](repo)
    return _claude_md(repo)


def test_should_write_the_gitmem_launcher_under_the_disposable_home_when_the_installer_runs(
    tmp_repo, _disposable_home
):
    """Guard of this file's own isolation. Bug caught: the HOME override
    is dropped or bypassed, so the installer run by these tests rewrites
    the owner's real ~/.local/bin/gitmem (it happened, SEC-MED-001)."""
    _run_installer(tmp_repo)
    launcher = os.path.join(_disposable_home, ".local", "bin", "gitmem")
    assert os.path.isfile(launcher), (
        f"the installer did not write its launcher under the disposable HOME "
        f"({launcher}); it went somewhere else -- maybe the real one"
    )


# ── Independent readers ──────────────────────────────────────────────────


def _expandable_imports(text):
    """[(line_index, path)] for every `@path` line Claude Code would expand:
    the line, stripped, is a single `@token`, and it sits outside a fenced
    code block and outside an HTML comment. A line starting with a backtick
    (code span) never starts with `@`, so it is excluded by construction.
    """
    found = []
    in_fence = False
    in_comment = False
    for i, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped.startswith("<!--") and "-->" not in stripped:
            in_comment = True
            continue
        if re.fullmatch(r"@\S+", stripped):
            found.append((i, stripped[1:]))
    return found


def _toolkit_block_line_range(text):
    lines = text.splitlines()
    begin = [i for i, l in enumerate(lines) if l.strip() == TOOLKIT_BEGIN]
    end = [i for i, l in enumerate(lines) if l.strip() == TOOLKIT_END]
    assert len(begin) == 1 and len(end) == 1, (
        f"expected exactly one unmassk-toolkit block, got BEGIN at {begin}, END at {end}"
    )
    assert begin[0] < end[0], "unmassk-toolkit BEGIN after its END"
    return begin[0], end[0]


def _toolkit_block_text(text):
    b, e = _toolkit_block_line_range(text)
    return "\n".join(text.splitlines()[b + 1:e])


def _rules_import_lines(text):
    """Line indexes, inside the unmassk-toolkit block, of an expandable
    import of exactly the contract's rules path."""
    b, e = _toolkit_block_line_range(text)
    return [i for i, path in _expandable_imports(text)
            if b < i < e and path == RULES_RELPATH]


def _step_one(block_text):
    """The text of step 1 of 'On every session start': from the line
    starting `1.` up to (not including) the line starting `2.`."""
    lines = block_text.splitlines()
    start = [i for i, l in enumerate(lines) if l.lstrip().startswith("1.")]
    assert start, f"no step 1 in the unmassk-toolkit block:\n{block_text}"
    out = []
    for l in lines[start[0]:]:
        if out and l.lstrip().startswith("2."):
            break
        out.append(l)
    return "\n".join(out)


# ── 1. The import exists and Claude Code will expand it ──────────────────


@pytest.mark.parametrize("writer", sorted(WRITERS))
def test_should_carry_an_expandable_rules_import_inside_the_toolkit_block_when_written(
    tmp_repo, writer
):
    """Bug caught: no import at all, an import of another path, an import
    wrapped in backticks or a code fence (Claude Code leaves it as text),
    or one placed outside the unmassk-toolkit block."""
    text = _written_claude_md(tmp_repo, writer)
    assert len(_rules_import_lines(text)) == 1, (
        f"{writer}: the unmassk-toolkit block must hold exactly one line "
        f"'@{RULES_RELPATH}' on its own, outside code fences/spans/comments. "
        f"Expandable imports found in the whole file: {_expandable_imports(text)}\n"
        f"Block:\n{_toolkit_block_text(text)}"
    )


def test_should_resolve_the_import_to_the_file_gitmem_rule_writes_when_a_rule_is_saved(
    tmp_repo,
):
    """Round-trip through the real producer of rules.md: `gitmem rule`
    writes a rule; the import in the CLAUDE.md the session start wrote,
    resolved the way Claude Code resolves it (relative to CLAUDE.md's own
    folder), must land on that very file and see that rule.
    Bug caught: the block imports a path the rule command never writes
    (typo, wrong folder, absolute path, path relative to something else)."""
    seed_config_json(tmp_repo, repo_type="trunk")
    rule_text = "answer in the owner's language, every single message"
    rc, out, err = run_memory_script(
        "rule.py", [rule_text, "--kind", "user", "--quote", "habla en mi idioma"],
        cwd=tmp_repo,
    )
    assert rc == 0, f"gitmem rule failed: stdout={out!r} stderr={err!r}"

    text = _written_claude_md(tmp_repo, "session-start-crew")
    imports = _rules_import_lines(text)
    assert imports, (
        f"no expandable rules import in the toolkit block:\n{_toolkit_block_text(text)}"
    )
    resolved = os.path.normpath(os.path.join(tmp_repo, RULES_RELPATH))
    assert os.path.isfile(resolved), f"import resolves to a missing file: {resolved}"
    with open(resolved, encoding="utf-8") as f:
        assert rule_text in f.read(), (
            f"the imported file {resolved} does not hold the rule gitmem rule just saved"
        )


# ── 2. It says the rules bind from the first message ─────────────────────


@pytest.mark.parametrize("writer", sorted(WRITERS))
def test_should_say_the_imported_rules_bind_from_the_first_message_when_written(
    tmp_repo, writer
):
    """Bug caught: the import lands with no instruction, so the rules sit
    in context as reference material instead of binding from message one."""
    text = _written_claude_md(tmp_repo, writer)
    imports = _rules_import_lines(text)
    assert imports, (
        f"{writer}: no expandable rules import in the toolkit block:\n"
        f"{_toolkit_block_text(text)}"
    )
    lines = text.splitlines()
    i = imports[0]
    around = "\n".join(lines[max(0, i - 3):i + 4]).lower()
    assert "first message" in around, (
        f"{writer}: within three lines of the import, the block must say the "
        f"rules bind from the first message. Got:\n{around}"
    )


# ── 3. Step 1 tells the truth about the briefing ─────────────────────────


@pytest.mark.parametrize("writer", sorted(WRITERS))
def test_should_drop_the_already_in_your_context_claim_from_step_one_when_written(
    tmp_repo, writer
):
    """Bug caught: step 1 keeps asserting the briefing is in context, so a
    boot killed by its timeout (I-005) goes unnoticed: Claude believes a
    briefing it never received."""
    block = _toolkit_block_text(_written_claude_md(tmp_repo, writer))
    assert OLD_CLAIM not in block.lower(), (
        f"{writer}: the block still claims '{OLD_CLAIM}':\n{block}"
    )


@pytest.mark.parametrize("writer", sorted(WRITERS))
def test_should_name_the_memory_lines_and_the_failed_boot_rule_in_step_one_when_written(
    tmp_repo, writer
):
    """Bug caught: step 1 does not tell Claude what to look for, nor what
    to do when it is missing -- so a dead boot is met with silence instead
    of the user being told first. Also caught: step 1 says the `[memory]`
    lines themselves carry the Next and blockers (they only point to the
    boot report, bin/memory/boot.py), so Claude reads a pointer as the
    briefing and never opens the report (Argus SEC-LOW-001)."""
    step1 = _step_one(_toolkit_block_text(_written_claude_md(tmp_repo, writer)))
    low = step1.lower()
    missing = [w for w in ("[memory]", "boot report", "path", "fail", "first", "user")
               if w not in low]
    assert not missing, (
        f"{writer}: step 1 must send Claude to the boot report whose path the "
        f"`[memory]` lines give, and say that if none arrived the boot failed "
        f"and the user is told first. Missing {missing} in:\n{step1}"
    )


def test_should_name_in_step_one_the_prefix_of_the_line_that_carries_the_boot_report_path(
    tmp_repo,
):
    """Cross-seam, on the everyday path: an INSTALLED project's session
    start. The prefix step 1 tells Claude to look for must open a line,
    printed by the real SessionStart boot (hooks/boot_launcher.py), that
    carries the path of a boot report that really exists on disk.
    The first boot_launcher run installs the project; only the second run
    is checked, so the installer's own `[memory] ... installed` notice
    cannot satisfy the test (Cerberus F2).
    Bug caught: the block names a prefix the boot never puts on the report
    line (or the boot stops printing it), so on every session after the
    first Claude finds no report and tells the owner the boot failed."""
    payload = make_session_start_payload(tmp_repo)
    rc, _first, err = run_hook_with_payload("boot_launcher.py", payload, cwd=tmp_repo)
    assert rc == 0, f"first boot_launcher rc={rc} stderr={err}"
    manifest = os.path.join(tmp_repo, ".claude", ".unmassk", "manifest.json")
    assert os.path.isfile(manifest), (
        "the first session start did not install the project, so the second "
        "run would not be the everyday path of an installed project"
    )
    _run_session_start_crew(tmp_repo)

    rc, boot_out, err = run_hook_with_payload("boot_launcher.py", payload, cwd=tmp_repo)
    assert rc == 0, f"second boot_launcher rc={rc} stderr={err}"

    step1 = _step_one(_toolkit_block_text(_claude_md(tmp_repo)))
    named = set(re.findall(r"\[[a-z]+\]", step1))
    assert named, f"step 1 names no `[prefix]` of the session start:\n{step1}"

    def _existing_paths(line):
        return [t for t in line.split() if os.path.isabs(t) and os.path.isfile(t)]

    report_lines = [l for l in boot_out.splitlines()
                    if any(l.startswith(p) for p in named) and _existing_paths(l)]
    assert report_lines, (
        f"step 1 names {sorted(named)}, but no line of an installed project's "
        f"boot starts with it and carries the path of an existing boot report. "
        f"Boot output:\n{boot_out}"
    )


# ── 4. Existing projects are upgraded on their next session start ────────


def _existing_project_claude_md():
    """An existing project's CLAUDE.md: the owner's own text, the OLD
    toolkit block, the three other blocks as they are today, more owner
    text after."""
    blocks = [f"{TOOLKIT_BEGIN}\n{OLD_TOOLKIT_BODY}\n{TOOLKIT_END}"]
    blocks += [f"{b['begin']}\n{b['body']}\n{b['end']}" for b in BLOCKS[1:]]
    return USER_HEAD + "\n\n".join(blocks) + USER_TAIL


@pytest.mark.parametrize("writer", sorted(WRITERS))
def test_should_upgrade_an_old_toolkit_block_and_keep_user_text_when_the_project_starts_again(
    tmp_repo, writer
):
    """Bug caught: projects already on the old block never get the import
    (the change only reaches new installs), or the upgrade eats the owner's
    hand-written text around the blocks."""
    with open(os.path.join(tmp_repo, "CLAUDE.md"), "w", encoding="utf-8") as f:
        f.write(_existing_project_claude_md())

    text = _written_claude_md(tmp_repo, writer)

    assert text.startswith(USER_HEAD), f"{writer}: text above the blocks changed:\n{text[:300]}"
    assert text.rstrip("\n").endswith(USER_TAIL.rstrip("\n")), (
        f"{writer}: text below the blocks changed:\n{text[-300:]}"
    )
    block = _toolkit_block_text(text)
    assert len(_rules_import_lines(text)) == 1 and OLD_CLAIM not in block.lower(), (
        f"{writer}: the old toolkit block was not upgraded to the new one:\n{block}"
    )


def test_should_settle_after_one_upgrade_when_the_session_starts_twice(tmp_repo):
    """Bug caught: a new block the upsert never recognises as current (for
    example an import line whose spacing the writer normalises), so every
    session start rewrites CLAUDE.md and reports changes forever."""
    with open(os.path.join(tmp_repo, "CLAUDE.md"), "w", encoding="utf-8") as f:
        f.write(_existing_project_claude_md())

    _run_session_start_crew(tmp_repo)
    first = _claude_md(tmp_repo)
    assert _rules_import_lines(first), (
        f"first session start did not upgrade the block:\n{_toolkit_block_text(first)}"
    )
    out2 = _run_session_start_crew(tmp_repo)
    assert _claude_md(tmp_repo) == first, "second session start rewrote CLAUDE.md again"
    assert "All managed blocks up to date" in out2, (
        f"second session start did not report the blocks as current:\n{out2}"
    )


# ── 5. Golden: what 2a must NOT lose from the block ──────────────────────


@pytest.mark.parametrize("writer", sorted(WRITERS))
def test_should_keep_steps_two_to_four_and_the_four_rules_when_step_one_is_rewritten(
    tmp_repo, writer
):
    """GREEN on purpose (golden). Bug caught: rewriting step 1 and adding
    the import drops the skill-loading steps or the four standing rules."""
    block = _toolkit_block_text(_written_claude_md(tmp_repo, writer))
    kept = [
        '`skill="unmassk-core"`',
        '`skill="unmassk-memory"`',
        "menu of the day",
        "Memory is a commit. Never write it into a file.",
        "The indexes and the zone list are written by the commands. Never by hand.",
        "A restriction is retired by asking the user",
        "Never ask the user to run a command -- you run it.",
    ]
    missing = [k for k in kept if k not in block]
    assert not missing, f"{writer}: block lost {missing}:\n{block}"
