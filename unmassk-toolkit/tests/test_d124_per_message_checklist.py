"""
#95 part 2b -- the D-124 per-message checklist in the UserPromptSubmit hook.

BUILD MODE: test-first. Written before the code; every contract test below is
RED until hooks/user-prompt-memory-check.py prints the checklist.

The contract (D-124, Bex 2026-10-18; restates D-098 and adds item 3)
--------------------------------------------------------------------
On EVERY user message the hook output carries:
  (1) do I keep every rule loaded at start, one by one, in this message?
  (2) do I know what we are doing without assuming -- if not, search memory
      first;
  (3) if I just gave a result or got a decision, have I ticked or written it
      in its plan or checklist?
  and, only when proposing options or deciding: did I start from what the
  sector does?
D-124's "only when saving" item is part 2c (customs/note/rule), not here.

Why: on 2026-10-18 five decisions reached Bex and memory but not the session
plan until he asked; M-152 (Bilbo) found the hook carried none of these.

How the expected values are written (never read from the hook)
---------------------------------------------------------------
The wording is Ultron's. Each question is pinned by the concept words of
D-124 itself, in English or Spanish (the hook already speaks both: its
[orden] lines are Spanish), accent- and case-insensitive, and all the words
of one question must sit on ONE line of the output -- a question is a
sentence; words scattered across unrelated lines are not the question.

"Every message" is exercised as Claude Code delivers it: the command line
read from hooks/hooks.json, run through the shell with CLAUDE_PLUGIN_ROOT
set, the real UserPromptSubmit JSON payload on stdin, inside an installed
repo; first message (no .session-booted flag), later messages of the same
session, a message that matches a skill route, one that matches nothing,
and automatic mode (both the owner's phrase "modo automatico" and Claude
Code's permission_mode "auto"/"bypassPermissions").

Size: Claude Code cuts hook output at 10,000 characters. "Far under" is
read as at most half the cap on the worst case this hook can produce today
(first message + four skill routes + all four [orden] reminders, ~1.2k
characters measured 2026-10-19 before the change).
"""

import json
import os
import subprocess
import sys
import unicodedata

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd

HOOKS_JSON = os.path.join(HOOKS_DIR, "hooks.json")
HOOK_FILE = "user-prompt-memory-check.py"

CLAUDE_CODE_OUTPUT_CAP = 10_000          # Claude Code's hook output cap
FAR_UNDER_LIMIT = CLAUDE_CODE_OUTPUT_CAP // 2

# Prompts. NEUTRAL matches no skill route and no [orden] reminder.
NEUTRAL = "what is the weather like in the cluster logs today"
ROUTED = "let's build a feature for user authentication"   # -> unmassk-flow
AUTO_PHRASE = "ponte en automatico hasta que vuelva"         # -> [orden] automatico
WORST_CASE = (
    "modo automatico, si o no, investiga, no sigas: build a feature, grill me, "
    "help me decide, audit this module, wrap up the session, scaffold a new "
    "project, refactor"
)


# ── Concept anchors (from D-124's text, EN or ES) ─────────────────────────
# Each question = list of groups; every group needs one alternative on the
# same line.

Q1_RULES_ONE_BY_ONE = [
    ("rule", "regla"),
    ("one by one", "una a una", "una por una", "uno a uno", "uno por uno"),
    ("start", "boot", "arranque", "inicio", "loaded", "cargad"),
]
Q2_NO_ASSUMING_SEARCH_MEMORY = [
    ("assum", "supon", "suponer", "presupon"),
    ("search", "busc"),
    ("memor",),
]
Q3_TICK_IN_PLAN = [
    ("result", "resultado"),
    ("decision",),
    ("plan",),
    ("tick", "marc", "tach", "written", "escrit", "apunt"),
]
Q4_SECTOR_FIRST = [
    ("sector",),
    ("option", "opcion", "propon", "propos"),
]
# The sector question is conditional ("only when proposing options").
Q4_CONDITIONAL = [
    ("sector",),
    ("only when", "solo cuando", "solo si", "solo al", "unicamente cuando", "when proposing", "al proponer"),
]


def _norm(text):
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _line_with(stdout, groups):
    """First output line carrying one alternative of every group, or None."""
    for line in stdout.splitlines():
        n = _norm(line)
        if all(any(alt in n for alt in group) for group in groups):
            return line
    return None


# ── Fixtures: an installed repo, the hook run as Claude Code runs it ──────

def _plugin_version():
    with open(os.path.join(SOURCE_ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
        return json.load(f)["version"]


def _make_installed_repo(tmp_path, booted):
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    with open(os.path.join(repo, "CLAUDE.md"), "w", encoding="utf-8") as f:
        f.write("<!-- BEGIN unmassk-toolkit -->\nx\n<!-- END unmassk-toolkit -->\n")
    unmassk = os.path.join(repo, ".claude", ".unmassk")
    os.makedirs(unmassk)
    with open(os.path.join(unmassk, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"version": _plugin_version()}, f)
    if booted:
        open(os.path.join(unmassk, ".session-booted"), "w", encoding="utf-8").close()
    return repo


def _hook_command():
    """The UserPromptSubmit command line Claude Code reads from hooks.json."""
    with open(HOOKS_JSON, encoding="utf-8") as f:
        hooks = json.load(f)["hooks"]
    commands = [
        h["command"]
        for entry in hooks["UserPromptSubmit"]
        for h in entry["hooks"]
        if HOOK_FILE in h.get("command", "")
    ]
    assert len(commands) == 1, f"expected one UserPromptSubmit entry for {HOOK_FILE}: {commands}"
    return commands[0]


def _payload(repo, prompt, permission_mode="default"):
    """The real UserPromptSubmit payload shape Claude Code sends."""
    return json.dumps({
        "session_id": "d124-test-session",
        "transcript_path": os.path.join(repo, "transcript.jsonl"),
        "cwd": repo,
        "permission_mode": permission_mode,
        "hook_event_name": "UserPromptSubmit",
        "prompt": prompt,
    })


def _run(repo, home, prompt, permission_mode="default"):
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = SOURCE_ROOT
    env["HOME"] = home
    proc = subprocess.run(
        _hook_command(),
        shell=True,
        cwd=repo,
        env=env,
        input=_payload(repo, prompt, permission_mode),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


@pytest.fixture
def booted_repo(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return _make_installed_repo(tmp_path, booted=True), str(home)


@pytest.fixture
def fresh_repo(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return _make_installed_repo(tmp_path, booted=False), str(home)


def _assert_full_checklist(stdout, where):
    for name, groups in (
        ("(1) every boot rule kept, one by one", Q1_RULES_ONE_BY_ONE),
        ("(2) know what we do without assuming, else search memory", Q2_NO_ASSUMING_SEARCH_MEMORY),
        ("(3) result/decision ticked or written in its plan", Q3_TICK_IN_PLAN),
        ("(4) sector first, when proposing options", Q4_SECTOR_FIRST),
    ):
        assert _line_with(stdout, groups) is not None, (
            f"{where}: D-124 question {name} missing from the hook output.\n"
            f"Needed on one line, one of each: {groups}\n--- stdout ---\n{stdout}"
        )


# ── Contract: the checklist rides on every kind of message ────────────────

class TestChecklistOnEveryMessage:

    def test_should_carry_checklist_when_first_message_of_session(self, fresh_repo):
        # Bug caught: checklist only added in the "already booted" branch.
        repo, home = fresh_repo
        rc, out, err = _run(repo, home, NEUTRAL)
        assert rc == 0, err
        assert "[git-memory-boot]" in out, out   # really the first-message branch
        _assert_full_checklist(out, "first message")

    def test_should_carry_checklist_when_later_message_no_route(self, booted_repo):
        # Bug caught: checklist printed only as a first-message boot item.
        repo, home = booted_repo
        rc, out, err = _run(repo, home, NEUTRAL)
        assert rc == 0, err
        _assert_full_checklist(out, "later message, no route")

    def test_should_carry_checklist_when_message_matches_skill_route(self, booted_repo):
        # Bug caught: checklist only in the no-match fallback (the old
        # `if not lines` slot), so it vanishes whenever a skill matches.
        repo, home = booted_repo
        rc, out, err = _run(repo, home, ROUTED)
        assert rc == 0, err
        assert "unmassk-flow" in out, out
        _assert_full_checklist(out, "message matching a skill route")

    def test_should_carry_checklist_when_owner_says_modo_automatico(self, booted_repo):
        # Bug caught: checklist suppressed in automatic mode, or only in the
        # fallback that an [orden] line fills.
        repo, home = booted_repo
        rc, out, err = _run(repo, home, AUTO_PHRASE)
        assert rc == 0, err
        assert "[orden]" in out, out
        _assert_full_checklist(out, "owner's automatic mode phrase")

    @pytest.mark.parametrize("mode", ["auto", "bypassPermissions", "acceptEdits", "plan"])
    def test_should_carry_checklist_when_claude_code_permission_mode_is(self, booted_repo, mode):
        # Bug caught: checklist gated on permission_mode == "default".
        repo, home = booted_repo
        rc, out, err = _run(repo, home, NEUTRAL, permission_mode=mode)
        assert rc == 0, err
        _assert_full_checklist(out, f"permission_mode={mode}")

    def test_should_carry_checklist_on_each_of_three_messages_in_one_session(self, fresh_repo):
        # Bug caught: a "once per session" flag that silences the checklist
        # after its first appearance. Same repo, three messages in a row.
        repo, home = fresh_repo
        for i, prompt in enumerate((NEUTRAL, ROUTED, NEUTRAL), start=1):
            rc, out, err = _run(repo, home, prompt)
            assert rc == 0, err
            _assert_full_checklist(out, f"message {i} of the session")

    def test_should_mark_sector_question_as_only_when_proposing_options(self, booted_repo):
        # Bug caught: the sector check written as an unconditional every-
        # message duty, which D-124 explicitly scopes to proposing options.
        repo, home = booted_repo
        rc, out, err = _run(repo, home, NEUTRAL)
        assert rc == 0, err
        assert _line_with(out, Q4_CONDITIONAL) is not None, (
            f"the sector line must say it applies only when proposing options/deciding:\n{out}"
        )

    def test_should_print_each_question_once_when_message_matches_everything(self, fresh_repo):
        # Bug caught: checklist appended once per matched route/reminder.
        repo, home = fresh_repo
        rc, out, err = _run(repo, home, WORST_CASE)
        assert rc == 0, err
        for groups in (Q1_RULES_ONE_BY_ONE, Q2_NO_ASSUMING_SEARCH_MEMORY, Q3_TICK_IN_PLAN, Q4_SECTOR_FIRST):
            hits = [l for l in out.splitlines()
                    if all(any(a in _norm(l) for a in g) for g in groups)]
            assert len(hits) == 1, f"expected exactly one line for {groups}, got {hits}"


# ── Size: far under Claude Code's cap, on the worst case ──────────────────

class TestOutputSize:

    def test_should_stay_far_under_cap_when_worst_case_message(self, fresh_repo):
        # Green today (~1.2k); turns red if the checklist (or anything added
        # with it) pushes the worst case past half the 10,000-char cap.
        repo, home = fresh_repo
        rc, out, err = _run(repo, home, WORST_CASE)
        assert rc == 0, err
        assert len(out) <= FAR_UNDER_LIMIT, f"{len(out)} chars > {FAR_UNDER_LIMIT}"

    def test_should_stay_far_under_cap_with_checklist_present(self, fresh_repo):
        # The size bound only means something once the checklist is in.
        repo, home = fresh_repo
        rc, out, err = _run(repo, home, WORST_CASE)
        assert rc == 0, err
        _assert_full_checklist(out, "worst case")
        assert len(out) <= FAR_UNDER_LIMIT, f"{len(out)} chars > {FAR_UNDER_LIMIT}"


# ── The lines that already existed keep working (green on purpose) ────────

class TestExistingLinesKeepWorking:

    def test_should_keep_skill_router_line_when_route_matches(self, booted_repo):
        repo, home = booted_repo
        rc, out, err = _run(repo, home, ROUTED)
        assert rc == 0, err
        router = [l for l in out.splitlines() if "[skill-router]" in l]
        assert router and "unmassk-flow" in router[0], out

    def test_should_keep_orden_line_when_owner_order_matches(self, booted_repo):
        repo, home = booted_repo
        rc, out, err = _run(repo, home, AUTO_PHRASE)
        assert rc == 0, err
        orden = [l for l in out.splitlines() if l.startswith("[orden]")]
        assert orden and "modo automatico" in _norm(orden[0]), out

    def test_should_keep_memory_check_line_when_nothing_matches(self, booted_repo):
        # Bug caught: the checklist fills `lines`, so the old `if not lines`
        # fallback never fires and the [memory-check] line silently dies.
        repo, home = booted_repo
        rc, out, err = _run(repo, home, NEUTRAL)
        assert rc == 0, err
        assert "[skill-router]" not in out and "[orden]" not in out, out
        assert any(l.startswith("[memory-check]") for l in out.splitlines()), out

    def test_should_keep_first_message_boot_block(self, fresh_repo):
        repo, home = fresh_repo
        rc, out, err = _run(repo, home, NEUTRAL)
        assert rc == 0, err
        assert 'skill="unmassk-core"' in out and 'skill="unmassk-memory"' in out, out
