"""
Tests for the per-message protocol-skill router in user-prompt-memory-check.py
(UserPromptSubmit hook).

BUILD MODE: test-first / contract pass. These are ACCEPTANCE-level tests
written BEFORE Ultron implements the skill-router logic — they define "done",
not the exhaustive branch/unit suite (that hardening pass happens later,
after Ultron's real implementation exists to measure).

Background (council decision this contract encodes)
─────────────────────────────────────────────────────
An 11-agent council found that 7 of the toolkit's 9 protocol skills
(unmassk-flow, unmassk-grill, unmassk-council, unmassk-project-lifecycle,
unmassk-audit, unmassk-close-session, unmassk-flow-stack) get selected
unreliably because they have zero mechanical backing — only Claude's own
judgement matching a natural-language description to the user's message.
unmassk-core and unmassk-gitmemory already get FORCED on the first message of
a session (see the existing `session_booted` block in the hook), but nothing
nudges Claude toward the right skill on messages 2, 3, 4... for ANY of the 9.

Accepted fix (deliberately NOT a heavy BM25 rebuild, and explicitly NOT a
hard PreToolUse gate — a similar hard gate was already tried and rejected
elsewhere in this codebase for token cost): a lightweight keyword /
trigger-phrase check against all 9 protocol skills, run on EVERY message,
that appends a short, purely informational nudge line to stdout when a match
is found. Never blocks. Never denies. Exit code is always 0.

Contract decision (Dante, pre-implementation) — the marker convention
───────────────────────────────────────────────────────────────────────
The task description's own example uses "[skill-router]" as the nudge
marker. This hook already has an established bracket-label convention for
every line it prints: [git-memory-bootstrap], [git-memory-boot],
[git-memory], [memoria relevante...], [memory-check]. Locking the new nudge
to the same "[skill-router]" bracket marker is not inventing wording — it is
the one convention already used by every other line this hook emits, so
Ultron has an unambiguous target to implement against. Tests below assert
marker PRESENCE plus skill-name proximity to that marker, never exact
sentence wording (the task explicitly says exact wording is Ultron's call).

Trigger-phrase source data
──────────────────────────
Every prompt below is built from phrases and words that appear LITERALLY in
each skill's own SKILL.md frontmatter `description` field (the same text
Claude reads today to decide, unreliably, whether to load the skill) — see
SKILL_TRIGGER_PROMPTS for the source phrase cited per skill. Exception:
unmassk-core's description has no quoted example user phrases (it is
"Loaded on session boot", not phrase-triggered) — its 3 prompts are built
from its own distinctive nouns/verbs instead ("agents", "delegate", "invoke
workflows", "domain plugins", "standards"), which is the best-effort
equivalent for that one skill.

Covered behaviours
──────────────────
1. Match          — 9 skills x 3 realistic prompts each -> nudge names the skill
2. Multiple match — prompt hits 2 skills' triggers -> nudge lists BOTH, not just one
3. No match       — neutral prompt -> no nudge line at all (no per-message noise)
4. Exit code      — ALWAYS 0, matched or not (never blocking)
5. No regression  — first-message-only core/gitmemory forcing text is untouched
                     by this per-message check, and both can coexist on message 1

Performance refactor (2026-07)
───────────────────────────────
Cases 1-3 originally ran through the full `_make_installed_repo()` (real
`git init` + config writes) + `_run_hook()` (fresh `python3` subprocess)
round-trip for every single case -- ~40 subprocess-spawning tests just to
check pure string matching, which is what made this file take 4+ minutes to
run and was causing real hangs/timeouts for the user. The actual matching
logic lives in `lib/skill_router.py` as an importable, pure function
(`match_skills(prompt_text) -> list[str]`) with ZERO dependency on git, the
hook script, or subprocess. Cases 1-3 below now call `match_skills()`
directly, in-process, with no fixture at all -- same prompts, same expected
skill names, same assertions in substance, just against the fastest correct
target for what is actually being verified (a pure function's output, not a
subprocess's stdout).

What's still a real subprocess/hook test (deliberately kept, not a fixture
optimization target): whether the HOOK ITSELF wires `match_skills()` into
its stdout correctly (marker line, exit code) -- see
`TestSkillRouterHookIntegration` below, kept small (3 tests) since that's
end-to-end wiring, not phrase-matching correctness. `TestFirstMessageForcingTextUnaffected`
also stays subprocess-based, since it tests hook-level session-state
behaviour (`.session-booted` flag interaction) that cannot be exercised via
`match_skills()` alone. The drift-guard class
(`TestSkillTriggerPhrasesMatchLiveDescriptions`) was never part of the
problem -- it already reads SKILL.md files directly in-process, no
subprocess, and stays untouched.

Hook invocation pattern (subprocess with JSON on stdin, cwd=temp repo; the
hook emits PLAIN TEXT, not JSON, on stdout) mirrors test_user_prompt_recall.py
and now applies ONLY to the small number of true hook-level tests noted
above -- not to the phrase-matching correctness tests, which call
`match_skills()` directly.
"""

import importlib.util
import json
import os
import sys

import pytest
import yaml

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_cmd
from skill_router import match_skills

HOOK_PATH = os.path.join(HOOKS_DIR, "user-prompt-memory-check.py")
SKILLS_DIR = os.path.join(SOURCE_ROOT, "skills")

# Read the real plugin version so _make_installed_repo can write a matching
# manifest -- prevents needs_upgrade() from triggering the auto-upgrade branch.
_PLUGIN_JSON = os.path.join(SOURCE_ROOT, ".claude-plugin", "plugin.json")
with open(_PLUGIN_JSON, encoding="utf-8") as _f:
    _PLUGIN_VERSION = json.load(_f)["version"]

# The bracket-label marker this contract locks the nudge line to (see module
# docstring "Contract decision" above).
SKILL_ROUTER_MARKER = "[skill-router]"


# ── Repo helpers (mirrors test_user_prompt_recall.py) ─────────────────────

def _make_repo(tmp_path, name="repo"):
    """Create a minimal git repo (no git-memory installation)."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _make_installed_repo(tmp_path, name="repo", booted=True):
    """Create a minimal git repo that appears to have git-memory installed.

    Writes the minimum artefacts that make the hook skip needs_install() and
    needs_upgrade() and proceed to the normal per-message output path.

    booted=True (default): also creates the .session-booted flag, so the
    hook takes the "already booted" branch -- this is what almost every test
    in this file wants, since we're testing the NEW per-message router, not
    the existing first-message-only forcing text.

    booted=False: leaves the flag absent, so the hook takes the "first
    message" branch and emits the MANDATORY forcing block. Used only by
    TestFirstMessageForcingTextUnaffected below.
    """
    repo = _make_repo(tmp_path, name)

    claude_md_path = os.path.join(repo, "CLAUDE.md")
    with open(claude_md_path, "w", encoding="utf-8") as f:
        f.write(
            "<!-- BEGIN unmassk-toolkit -->\n"
            "Context Checkpoint Commits\n"
            "<!-- END unmassk-toolkit -->\n"
        )

    unmassk_dir = os.path.join(repo, ".claude", ".unmassk")
    os.makedirs(unmassk_dir, exist_ok=True)
    manifest_path = os.path.join(unmassk_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"version": _PLUGIN_VERSION}, f)

    if booted:
        booted_flag = os.path.join(unmassk_dir, ".session-booted")
        open(booted_flag, "w", encoding="utf-8").close()

    return repo


# ── Hook invocation helper ─────────────────────────────────────────────────

def _run_hook(repo, prompt):
    """Invoke user-prompt-memory-check.py with JSON stdin from repo directory.

    Returns (returncode, stdout_str, stderr_str). The hook emits PLAIN TEXT,
    not JSON.
    """
    input_text = json.dumps({"prompt": prompt})
    return run_cmd(
        [sys.executable, HOOK_PATH],
        cwd=repo,
        input_text=input_text,
    )


def _skill_router_block(stdout):
    """Return the concatenated text of every line containing the
    '[skill-router]' marker, or '' if the marker never appears.

    Concatenating (rather than taking a single line) tolerates either a
    single-line "[skill-router] unmassk-flow, unmassk-grill" implementation
    or a multi-line "[skill-router] unmassk-flow\\n[skill-router] unmassk-grill"
    implementation -- the contract does not mandate one over the other.
    """
    return "\n".join(line for line in stdout.splitlines() if SKILL_ROUTER_MARKER in line)


# ── Trigger-phrase source data ─────────────────────────────────────────────
# Each prompt cites, in the comment, the literal phrase/words from the
# skill's own SKILL.md `description` field that it is built from.

SKILL_TRIGGER_PROMPTS = {
    # description has no quoted user phrases (it's "Loaded on session boot",
    # not phrase-triggered) -- built from its own distinctive nouns/verbs.
    "unmassk-core": [
        "what agents do you have available to delegate this work to",  # "agents", "how to delegate"
        "how do you decide when to invoke workflows for a task",  # "when to invoke workflows"
        "what domain plugins and standards do you use",  # "domain plugins", "standards"
    ],
    # "memory, resume, context, decision, memo, remember" + quoted
    # "what did we decide", "what's pending"
    "unmassk-gitmemory": [
        "what did we decide about the api design last time",  # quoted: "what did we decide"
        "what's pending from the last session",  # quoted: "what's pending"
        "remember that we chose postgres over mysql",  # "remember"
    ],
    # quoted: "build a feature", "implement", "add functionality",
    # "fix a non-trivial bug", "refactor"
    "unmassk-flow": [
        "let's build a feature for user authentication",  # quoted: "build a feature"
        "I need to implement this and add functionality for search",  # quoted: "implement", "add functionality"
        "can we refactor this non-trivial bug fix",  # quoted: "refactor", "non-trivial bug"
    ],
    # quoted: "grill me", "let's think this through". "stress-test this plan"
    # was REMOVED from unmassk-grill's live description in a 2026-07 frontmatter
    # edit (council found it collided with unmassk-council's "pressure-test
    # this decision") -- replaced below with a literal substring of the
    # current description ("the request is ambiguous") instead of the removed
    # quoted phrase.
    "unmassk-grill": [
        "grill me on this before we start building",  # quoted: "grill me"
        "I know the request is ambiguous, help me nail down what I actually mean",  # substring: "the request is ambiguous" (replaces removed "stress-test this plan")
        "let's think this through before deciding",  # quoted: "let's think this through"
    ],
    # quoted: "should I X or Y", "which option", "I'm torn", "help me decide",
    # "council this", "prototype this". "let's brainstorm" was REMOVED from
    # unmassk-council's live description in a 2026-07 frontmatter edit (council
    # found it collided with unmassk-flow's brainstorm/discuss/plan wording) --
    # replaced below with "council this", which IS still quoted in the
    # current description.
    "unmassk-council": [
        "should I use redis or postgres for this, which option is better",  # quoted: "should I X or Y", "which option"
        "I'm torn between two approaches, help me decide",  # quoted: "I'm torn", "help me decide"
        "let's council this and prototype this idea before we commit",  # quoted: "council this", "prototype this" (replaces removed "let's brainstorm")
    ],
    # quoted: "new project", "let's start", "continue", "where were we",
    # "pick up the project", "scan this repo", "I inherited this codebase"
    "unmassk-project-lifecycle": [
        "let's start a new project from scratch",  # quoted: "let's start", "new project"
        "where were we, let's continue from last time",  # quoted: "where were we", "continue"
        "I inherited this codebase, can you scan this repo",  # quoted: "I inherited this codebase", "scan this repo"
    ],
    # quoted: "audit a module", "enterprise review", "launch audit"
    "unmassk-audit": [
        "can you audit a module for me",  # quoted: "audit a module"
        "let's do an enterprise review of this service",  # quoted: "enterprise review"
        "please launch audit on the payments module",  # quoted: "launch audit"
    ],
    # quoted: "let's wrap up", "close the session", "we're done for today", "hand off"
    "unmassk-close-session": [
        "let's wrap up for today",  # quoted: "let's wrap up"
        "please close the session now",  # quoted: "close the session"
        "we're done for today, hand off to the next session",  # quoted: "we're done for today", "hand off"
    ],
    # quoted: "scaffold project", "which stack", "tech stack", "what framework".
    # "create new project" was REMOVED from unmassk-flow-stack's live description
    # in a 2026-07 frontmatter edit (council found it collided with
    # unmassk-project-lifecycle's "new project") -- replaced below with
    # "which stack", which IS still quoted in the current description.
    "unmassk-flow-stack": [
        "scaffold project for a new react app",  # quoted: "scaffold project"
        "what framework and tech stack should I use",  # quoted: "what framework", "tech stack"
        "which stack should I pick for this backend, fastapi or something else",  # quoted: "which stack" (replaces removed "create new project")
    ],
}

# Flattened (skill, prompt) pairs for parametrization, with readable ids.
_PARAM_CASES = [
    pytest.param(skill, prompt, id=f"{skill}__{i}")
    for skill, prompts in SKILL_TRIGGER_PROMPTS.items()
    for i, prompt in enumerate(prompts)
]

# Sanity check on the fixture data itself: 9 skills x 3 prompts = 27 cases.
assert len(SKILL_TRIGGER_PROMPTS) == 9
assert len(_PARAM_CASES) == 27


# ── Tests: match (Case 1) ──────────────────────────────────────────────────

class TestSkillRouterMatchesRealTriggerPhrases:
    """9 skills x 3 realistic prompts (from each skill's own description)
    -> match_skills() returns that skill.

    In-process: calls match_skills() directly, no repo fixture, no
    subprocess. This is pure string-matching correctness, not hook wiring --
    see TestSkillRouterHookIntegration for the small number of tests that
    verify the hook actually surfaces match_skills()'s result on stdout.
    """

    @pytest.mark.parametrize("skill, prompt", _PARAM_CASES)
    def test_prompt_triggers_matching_skill(self, skill, prompt):
        matches = match_skills(prompt)

        assert skill in matches, (
            f"Expected {skill!r} in match_skills({prompt!r}); got {matches!r}"
        )


# ── Tests: multiple match (Case 2) ────────────────────────────────────────

class TestSkillRouterListsAllMatches:
    """A prompt that hits more than one skill's triggers -> match_skills()
    returns ALL matches, not just the first one found.

    In-process: calls match_skills() directly, no repo fixture, no
    subprocess.
    """

    def test_prompt_matching_two_skills_lists_both(self):
        # Hits unmassk-flow ("refactor") AND unmassk-council
        # ("should I", "help me decide", "which option").
        prompt = "should I refactor this now or wait, help me decide which option"

        matches = match_skills(prompt)

        assert "unmassk-flow" in matches, (
            f"Expected unmassk-flow among the matches; got {matches!r}"
        )
        assert "unmassk-council" in matches, (
            f"Expected unmassk-council among the matches; got {matches!r}"
        )


# ── Tests: no match (Case 3) ──────────────────────────────────────────────

class TestSkillRouterNoNudgeWhenNoTrigger:
    """Neutral prompts unrelated to any of the 9 skills -> match_skills()
    returns an empty list (no false-positive noise on every message).

    In-process: calls match_skills() directly, no repo fixture, no
    subprocess. These prompts must genuinely not hit any skill's trigger
    words.
    """

    @pytest.mark.parametrize(
        "prompt",
        [
            "can you tell me a joke about cats",
            "what's the capital city of france",
            "print the fibonacci sequence up to ten numbers",
        ],
    )
    def test_neutral_prompt_produces_no_matches(self, prompt):
        matches = match_skills(prompt)

        assert matches == [], (
            f"Expected no matches for neutral prompt {prompt!r}; got {matches!r}"
        )


# ── Tests: hook-level wiring (Cases 1/3/4, end-to-end) ────────────────────

class TestSkillRouterHookIntegration:
    """Small set of true end-to-end tests: does the HOOK ITSELF (not just
    match_skills()) wire the matching function into its stdout correctly.
    Phrase-matching correctness is already covered in-process above; these
    three tests only verify the wiring (marker line, exit code) through a
    real subprocess -- deliberately kept small (not one per prompt) since
    subprocess spawns are the expensive part of this file.
    """

    def test_matching_prompt_produces_skill_router_line_naming_the_skill(self, tmp_path):
        repo = _make_installed_repo(tmp_path)
        rc, stdout, _stderr = _run_hook(repo, "grill me on this before we start")

        assert rc == 0
        block = _skill_router_block(stdout)
        assert block, f"Expected a '[skill-router]' line; got stdout: {stdout!r}"
        assert "unmassk-grill" in block, (
            f"Expected unmassk-grill named in the skill-router block; got: {block!r}"
        )

    def test_non_matching_prompt_produces_no_skill_router_line(self, tmp_path):
        repo = _make_installed_repo(tmp_path)
        rc, stdout, _stderr = _run_hook(repo, "what's the capital city of france")

        assert rc == 0
        assert SKILL_ROUTER_MARKER not in stdout, (
            f"Expected no '[skill-router]' marker for neutral prompt; "
            f"got stdout: {stdout!r}"
        )

    def test_exit_code_always_zero_through_real_hook_matched_case(self, tmp_path):
        repo = _make_installed_repo(tmp_path)
        # Deliberately dense with trigger words across several skills, to
        # also prove rc==0 holds even when many matches are found at once.
        prompt = (
            "let's start a new project, grill me on the plan, then help me decide "
            "which option, and audit a module before we wrap up for today"
        )

        rc, _stdout, _stderr = _run_hook(repo, prompt)

        assert rc == 0, f"Hook must exit 0 even with many matches; got rc={rc}"


# ── Tests: no regression of first-message forcing text (Case 5) ──────────

class TestFirstMessageForcingTextUnaffected:
    """The existing first-message-only core/gitmemory MANDATORY forcing
    block must survive this change untouched, and must coexist with the new
    per-message router when both conditions apply on message 1.
    """

    def test_first_message_forcing_text_present_regardless_of_prompt(self, tmp_path):
        """MANDATORY forcing block still appears on an unbooted repo's first
        message, independent of prompt content.

        INVARIANT -- already passes today (the forcing block does not
        depend on prompt content at all). Must not regress.
        """
        repo = _make_installed_repo(tmp_path, booted=False)

        rc, stdout, _stderr = _run_hook(repo, "grill me on this before we start")

        assert rc == 0
        assert "MANDATORY" in stdout, (
            f"Expected the MANDATORY first-message forcing block; got: {stdout!r}"
        )
        assert 'skill="unmassk-core"' in stdout, (
            f"Expected the unmassk-core forcing step; got: {stdout!r}"
        )
        assert 'skill="unmassk-gitmemory"' in stdout, (
            f"Expected the unmassk-gitmemory forcing step; got: {stdout!r}"
        )
        assert "CALIBRATION.md" in stdout, (
            f"Expected the CALIBRATION.md forcing step; got: {stdout!r}"
        )

    def test_first_message_forcing_text_and_router_nudge_coexist(self, tmp_path):
        """On message 1, when the prompt ALSO matches a skill trigger, BOTH
        the MANDATORY forcing block AND the new '[skill-router]' nudge
        appear -- the new check must not replace or short-circuit the old
        one.

        RED: today there is no '[skill-router]' marker at all -> FAIL on
        that half of the assertion, even though the forcing-block half
        already passes.
        """
        repo = _make_installed_repo(tmp_path, booted=False)

        rc, stdout, _stderr = _run_hook(repo, "grill me on this before we start")

        assert rc == 0
        assert "MANDATORY" in stdout, (
            f"First-message forcing block must still be present; got: {stdout!r}"
        )
        block = _skill_router_block(stdout)
        assert block, (
            f"Expected a '[skill-router]' line to coexist with the first-message "
            f"forcing block; got stdout: {stdout!r}"
        )
        assert "unmassk-grill" in block, (
            f"Expected unmassk-grill named in the skill-router block; got: {block!r}"
        )

    def test_first_message_forcing_text_no_router_match_still_present(self, tmp_path):
        """On message 1 with a neutral prompt (no skill trigger), the
        MANDATORY forcing block is still present and no router marker
        appears.

        INVARIANT for the forcing-block half; already trivially true for the
        no-marker half (hook never emits it today). Must hold after
        implementation too.
        """
        repo = _make_installed_repo(tmp_path, booted=False)

        rc, stdout, _stderr = _run_hook(repo, "what's the capital city of france")

        assert rc == 0
        assert "MANDATORY" in stdout, (
            f"First-message forcing block must still be present; got: {stdout!r}"
        )
        assert SKILL_ROUTER_MARKER not in stdout, (
            f"Expected no '[skill-router]' marker for a neutral first message; "
            f"got: {stdout!r}"
        )


# ── Drift guard: SKILL_TRIGGER_PHRASES vs. live SKILL.md frontmatter ──────
#
# NOT part of the acceptance contract above (that pass is frozen at the
# granularity the task defined "done" for). This is a PERMANENT regression
# guard added after the fact: an orchestrator editing 4 SKILL.md frontmatter
# `description` fields directly (2026-07, fixing real trigger-phrase
# collisions found by an 11-agent council review) silently made 4 entries in
# SKILL_TRIGGER_PHRASES stale -- "stress-test this plan" (grill), "let's
# brainstorm" (council), "create something new" (flow), "create new project"
# (flow-stack). Nothing caught that drift because the dict was hand-built
# from the description text at one point in time and never re-checked
# against it. This test reads both sides FRESH at test time (the hook's own
# dict via import, each skill's description via its live SKILL.md) so it
# fails the moment they diverge again in the future, for any skill, not just
# the 4 that happen to be stale today.


def _load_hook_module_for_drift_guard():
    """Import user-prompt-memory-check.py to read its LIVE SKILL_TRIGGER_PHRASES
    dict directly -- never copy/hardcode that dict into this test file, or the
    drift guard would just be checking itself instead of the real hook.

    Uses importlib.util.spec_from_file_location per this repo's convention for
    importing hyphenated hook filenames (see conventions.md /
    unmassk-toolkit-python-test-conventions). No main()-time side effects:
    the hook only executes work inside `if __name__ == "__main__"`.
    """
    lib_dir = os.path.join(SOURCE_ROOT, "lib")
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    spec = importlib.util.spec_from_file_location(
        "user_prompt_memory_check_driftguard", HOOK_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_skill_description(skill_name):
    """Read the live `description` field from a skill's SKILL.md frontmatter,
    lowercased for case-insensitive substring checks (mirrors the hook's own
    case-insensitive `_match_skills` matching).

    Parses the YAML frontmatter block (text between the first two `---`
    delimiters) with a real YAML parser so both plain single-line
    descriptions (unmassk-flow, unmassk-audit, unmassk-core,
    unmassk-gitmemory) and folded `>` block-scalar descriptions
    (unmassk-grill, unmassk-council, unmassk-project-lifecycle,
    unmassk-close-session, unmassk-flow-stack) are read identically --
    a naive string-search would treat the folded newlines differently
    than yaml.safe_load's real folding rules.
    """
    skill_md_path = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
    with open(skill_md_path, encoding="utf-8") as f:
        content = f.read()
    _, frontmatter_text, _ = content.split("---", 2)
    frontmatter = yaml.safe_load(frontmatter_text)
    return frontmatter["description"].lower()


_HOOK_MODULE_FOR_DRIFT_GUARD = _load_hook_module_for_drift_guard()

# One (skill, phrase) pair per entry in the REAL dict -- not a hardcoded
# count. If Ultron adds/removes phrases later, this parametrization picks it
# up automatically without editing this test file.
_DRIFT_GUARD_CASES = [
    pytest.param(skill, phrase, id=f"{skill}__{phrase!r}")
    for skill, phrases in _HOOK_MODULE_FOR_DRIFT_GUARD.SKILL_TRIGGER_PHRASES.items()
    for phrase in phrases
]


class TestSkillTriggerPhrasesMatchLiveDescriptions:
    """Every phrase in SKILL_TRIGGER_PHRASES must be a real substring of its
    OWN skill's CURRENT SKILL.md description -- read fresh at test time, not
    a snapshot hardcoded here.

    EXPECTED STATE TODAY (before Ultron reconciles the dict): FAILS for
    exactly 4 of the ~48 (skill, phrase) pairs --
    ("unmassk-grill", "stress-test this plan"),
    ("unmassk-council", "let's brainstorm"),
    ("unmassk-flow", "create something new"),
    ("unmassk-flow-stack", "create new project") --
    proving SKILL_TRIGGER_PHRASES is stale relative to the frontmatter edits.
    All other pairs (unmassk-core, unmassk-gitmemory, unmassk-project-lifecycle,
    unmassk-audit, unmassk-close-session, and the non-removed phrases of the
    4 edited skills) already pass today and must keep passing.
    """

    @pytest.mark.parametrize("skill, phrase", _DRIFT_GUARD_CASES)
    def test_phrase_is_substring_of_own_skill_live_description(self, skill, phrase):
        description = _read_skill_description(skill)

        assert phrase.lower() in description, (
            f"SKILL_TRIGGER_PHRASES[{skill!r}] contains {phrase!r}, but that "
            f"phrase no longer appears in skills/{skill}/SKILL.md's live "
            f"description -- the hook's trigger dict has drifted from the "
            f"frontmatter. Update SKILL_TRIGGER_PHRASES in "
            f"user-prompt-memory-check.py to match the current description."
        )
