"""
Contract (RED) for hooks/reviewer-prompt-gate.py -- PreToolUse gate on the
tool that launches subagents ("Agent" today, "Task" in older builds).

Owner's rule: "si le dices 'encuentra', siempre van a encontrar". A reviewing
lane (cerberus / argus / yoda) must get the BLIND review template from
skills/unmassk-core/SKILL.md ("Review prompts are blind"): it needs the
`ASK:` line and must not ask for findings.

Two-sources rule: every expectation about the template (the ASK wording, the
two banned example phrases, the "valid answer" sentence) is EXTRACTED from
SKILL.md at run time, and the registration is read from hooks.json -- nothing
hand-copied from either. The hook is driven as Claude Code drives it: a
process, JSON on stdin, assertions on stdout / exit code.

Pinned decisions (not stated by the task):
  * Allow = empty stdout, exit 0.
  * Deny  = exit 0, stdout one JSON object:
      {"hookSpecificOutput": {"hookEventName": "PreToolUse",
        "permissionDecision": "deny", "permissionDecisionReason": "<1-2 lines>"}}
    (documented PreToolUse shape, code.claude.com/docs/en/hooks. The older
    top-level {"decision": "block"} used by the other hooks here is NOT used.)
  * `ASK:` must start a line ("TASK:" does not count).
  * A banned phrase inside quotation marks (' " or typographic) is a
    mention, not a request, and is ignored; unquoted it is denied.
  * Matching is case-insensitive and accent-insensitive.
  * Reviewer launch with no/non-string prompt -> allow (missing field).
"""

import json
import os
import re
import subprocess
import sys

import pytest

from conftest import HOOKS_DIR, SOURCE_ROOT

HOOK = os.path.join(HOOKS_DIR, "reviewer-prompt-gate.py")
SKILL = os.path.join(SOURCE_ROOT, "skills", "unmassk-core", "SKILL.md")
HOOKS_JSON = os.path.join(HOOKS_DIR, "hooks.json")


@pytest.fixture(autouse=True)
def _hook_exists():
    # Without this, the fail-open tests would pass vacuously on a missing file.
    assert os.path.isfile(HOOK), f"hook does not exist yet: {HOOK}"


# ── Template, extracted from the skill ──────────────────────────────────────

def _skill_text():
    with open(SKILL, encoding="utf-8") as f:
        return f.read()


def _template_block():
    m = re.search(r"```\n(\[REVIEW — blind\]\n.*?)\n```", _skill_text(), re.S)
    assert m, "blind template block not found in SKILL.md"
    return m.group(1)


def _valid_prompt():
    """The template with its placeholders filled in -- ASK line verbatim."""
    out = []
    for line in _template_block().splitlines():
        key = line.split(":", 1)[0]
        if key in ("ARTIFACT", "CONTRACT", "SCOPE"):
            out.append(f"{key}: the diff of commit abc123 in lib/x.py")
        else:
            out.append(line)
    return "\n".join(out)


def _ask_line():
    return next(l for l in _template_block().splitlines() if l.startswith("ASK:"))


def _banned_examples():
    """The phrases SKILL.md itself says never to send: '... never "find the issues"
    or "report your findings"'."""
    m = re.search(r"never \"([^\"]+)\" or \"([^\"]+)\"", _skill_text())
    assert m, "banned-phrase sentence not found in SKILL.md"
    return [m.group(1), m.group(2)]


def _valid_sentence():
    m = re.search(r"(Finding nothing is a valid answer)", _ask_line())
    assert m
    return m.group(1)


# ── Driver ──────────────────────────────────────────────────────────────────

def _run_raw(stdin_text):
    p = subprocess.run([sys.executable, HOOK], input=stdin_text,
                       capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout, p.stderr


def _launch(subagent_type, prompt, tool_name="Agent"):
    return json.dumps({
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": {"subagent_type": subagent_type, "prompt": prompt,
                       "description": "review"},
    })


def _assert_allowed(stdin_text):
    rc, out, err = _run_raw(stdin_text)
    assert rc == 0, err
    assert out.strip() == "", out


def _assert_denied(stdin_text):
    rc, out, err = _run_raw(stdin_text)
    assert rc == 0, err
    body = json.loads(out)
    assert set(body) == {"hookSpecificOutput"}
    hso = body["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"].strip()
    return hso["permissionDecisionReason"]


REVIEWERS = ["cerberus", "argus", "yoda",
             "unmassk-toolkit:cerberus", "unmassk-toolkit:argus",
             "unmassk-toolkit:yoda"]
NON_REVIEWERS = ["ultron", "dante", "bilbo", "house", "alexandria", "moriarty",
                 "general-purpose", "Explore", "unmassk-toolkit:ultron",
                 "unmassk-toolkit:moriarty"]
BIASING = [
    "find the issues", "find bugs", "find problems", "report your findings",
    "report the issues", "look for bugs", "encuentra los fallos",
    "busca errores", "encuentra problemas",
    "FIND THE ISSUES", "Encuentra los Fallos", "ENCUÉNTRA los fallos",
    "búsca errores",
]


# ── Registration (read from hooks.json) ─────────────────────────────────────

class TestRegistration:
    def _entries(self):
        with open(HOOKS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        return [e for e in data["hooks"]["PreToolUse"]
                if any("reviewer-prompt-gate.py" in h.get("command", "")
                       for h in e["hooks"])]

    def test_should_register_exactly_one_pretooluse_entry(self):
        assert len(self._entries()) == 1

    @pytest.mark.parametrize("tool", ["Agent", "Task"])
    def test_should_match_subagent_launching_tool(self, tool):
        matcher = self._entries()[0]["matcher"]
        assert re.fullmatch(matcher, tool)

    @pytest.mark.parametrize("tool", ["Bash", "Write", "Edit"])
    def test_should_not_match_other_tools(self, tool):
        assert not re.fullmatch(self._entries()[0]["matcher"], tool)

    def test_should_point_command_at_an_existing_file(self):
        cmd = self._entries()[0]["hooks"][0]["command"]
        rel = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/(\S+)", cmd).group(1)
        assert os.path.isfile(os.path.join(SOURCE_ROOT, rel))


# ── Allow paths ─────────────────────────────────────────────────────────────

class TestAllow:
    @pytest.mark.parametrize("who", REVIEWERS)
    @pytest.mark.parametrize("tool", ["Agent", "Task"])
    def test_should_allow_template_prompt_for_every_reviewer(self, who, tool):
        _assert_allowed(_launch(who, _valid_prompt(), tool))

    @pytest.mark.parametrize("who", NON_REVIEWERS)
    @pytest.mark.parametrize("phrase", ["find the issues", "no ASK line at all"])
    def test_should_pass_every_other_subagent_untouched(self, who, phrase):
        _assert_allowed(_launch(who, f"please {phrase}"))

    @pytest.mark.parametrize("phrase", _banned_examples() if os.path.isfile(SKILL) else [])
    def test_should_ignore_banned_phrase_quoted_in_ask_wording(self, phrase):
        prompt = _valid_prompt() + f" (never \"{phrase}\")"
        _assert_allowed(_launch("cerberus", prompt))

    def test_should_ignore_single_quoted_banned_phrase(self):
        prompt = _valid_prompt() + " (never 'find the issues')"
        _assert_allowed(_launch("argus", prompt))


# ── Deny paths ──────────────────────────────────────────────────────────────

class TestDeny:
    @pytest.mark.parametrize("who", REVIEWERS)
    @pytest.mark.parametrize("phrase", BIASING)
    def test_should_deny_biasing_phrase_even_with_ask_line(self, who, phrase):
        prompt = _valid_prompt() + f"\nAlso, {phrase} in it."
        _assert_denied(_launch(who, prompt))

    @pytest.mark.parametrize("phrase", _banned_examples() if os.path.isfile(SKILL) else [])
    def test_should_deny_the_skills_own_banned_phrases_unquoted(self, phrase):
        _assert_denied(_launch("yoda", _valid_prompt() + f"\nPlease {phrase}."))

    @pytest.mark.parametrize("tool", ["Agent", "Task"])
    def test_should_deny_prompt_without_ask_line(self, tool):
        prompt = "ARTIFACT: lib/x.py\nCONTRACT: must not crash\nSCOPE: all"
        _assert_denied(_launch("cerberus", prompt, tool))

    def test_should_not_count_TASK_colon_as_ask_line(self):
        prompt = "TASK: review lib/x.py\nARTIFACT: lib/x.py"
        _assert_denied(_launch("argus", prompt))

    def test_should_deny_empty_prompt_string_for_reviewer(self):
        _assert_denied(_launch("cerberus", ""))

    def test_should_say_what_to_rewrite_in_one_or_two_lines(self):
        reason = _assert_denied(_launch("cerberus", "find the issues in lib/x.py"))
        lines = [l for l in reason.splitlines() if l.strip()]
        assert 1 <= len(lines) <= 2
        assert "ASK:" in reason
        assert _valid_sentence() in reason


# ── Fail-open ───────────────────────────────────────────────────────────────

class TestFailOpen:
    @pytest.mark.parametrize("raw", [
        "", "   ", "not json", "{", "[]", "null", "42", '"str"',
        json.dumps({}),
        json.dumps({"tool_name": "Agent"}),
        json.dumps({"tool_name": "Agent", "tool_input": None}),
        json.dumps({"tool_name": "Agent", "tool_input": "cerberus"}),
        json.dumps({"tool_name": "Agent", "tool_input": {}}),
        json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": None}}),
        json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": 7, "prompt": "find bugs"}}),
        json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": "cerberus"}}),
        json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": "cerberus", "prompt": None}}),
        json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": "cerberus", "prompt": ["find bugs"]}}),
    ])
    def test_should_allow_silently_on_malformed_or_missing_fields(self, raw):
        _assert_allowed(raw)

    def test_should_allow_on_invalid_utf8_stdin(self):
        p = subprocess.run([sys.executable, HOOK], input=b"\xff\xfe{\x80",
                           capture_output=True, timeout=30)
        assert p.returncode == 0
        assert p.stdout.strip() == b""
