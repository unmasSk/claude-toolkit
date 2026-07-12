"""
Tests for pre-task-recall.py — the git-memory recall injection hook.

Covers:
- Task with whitelisted agent (ultron) + memory match → prompt is injected,
  all other tool_input fields are preserved.
- Task with non-whitelisted agent (bilbo) → passthrough, no updatedInput.
- tool_name other than Task → passthrough.
- recall returns no matches → passthrough.
- Malformed JSON on stdin → fail-open (allow, exit 0).
- subagent_type with namespace prefix ('unmassk-toolkit:ultron') → recognised.
- subagent_type without prefix ('ultron') → recognised.
- Prompt field absent or empty → passthrough.

The hook is invoked as a subprocess with JSON passed via stdin, mirroring
the pattern used by run_script() in conftest.
"""

import importlib.util
import io
import json
import os
import subprocess
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_script

# Make lib/ importable for direct recall() calls in test helpers.
LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

HOOK_PATH = os.path.join(HOOKS_DIR, "pre-task-recall.py")
SKILL_SEARCH_SCRIPT = os.path.join(SOURCE_ROOT, "scripts", "skill-search.py")

# ── Skill-gate-safe nonce vocabulary ──────────────────────────────────────
# Issue #68: the hook now runs skill-search.py over every crew-agent prompt
# BEFORE falling through to memory recall (see TestSkillGate* below). Plain
# English test phrases like "BM25 recall ranking" score >= _SKILL_SCORE_
# THRESHOLD (1.5) against the REAL, host-installed skill corpus — "BM25" and
# "recall" each independently overlap unmassk-db's db-vector-rag skill
# vocabulary (verified via a direct real subprocess call to
# skill-search.py: score 7.1 for "BM25 recall", 3.5 for either word alone).
# That now makes the gate DENY instead of falling through to the memory path
# these tests exist to exercise.
#
# _MEM_NONCE is pure invented vocabulary (no real English/Spanish words) —
# verified via a real subprocess call to skill-search.py to score exactly 0
# against this machine's real corpus, so it can never accidentally collide
# with an installed domain skill regardless of which skills happen to be
# present. Tests whose intent is the MEMORY path use it as shared
# vocabulary between the seeded commit trailer and the prompt: recall()'s
# own BM25 index is a separate corpus (git commit messages, not skill
# descriptions), so token overlap there still produces a deterministic
# memory match. See agent memory:
# pre-task-recall-skill-injection-contract-notes.md.
_MEM_NONCE = "zqxvbnkplfth wjrqztkvnmg"

# For tests whose intent is "no memory match at all" — a nonce disjoint from
# _MEM_NONCE so it never accidentally overlaps a commit seeded elsewhere in
# the same test. Also verified score 0 against the real skill corpus.
_NO_MATCH_NONCE = "qzxdfklmnpwrtjhbg zvkxbmqlnwrtfhcds"


# ── Repo helpers (mirrors test_recall.py) ────────────────────────────────

def _make_repo(tmp_path, name="repo"):
    """Create a minimal git repo."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _commit(repo, subject, trailers=""):
    """Add a memory commit with optional trailer block."""
    msg = subject
    if trailers:
        msg = subject + "\n\n" + trailers
    git_cmd(["commit", "--allow-empty", "-m", msg], repo)


# ── Hook invocation helper ────────────────────────────────────────────────

def _run_hook(repo, tool_name, tool_input):
    """Invoke pre-task-recall.py with JSON stdin from the given repo directory.

    Returns (returncode, parsed_output_dict, raw_stdout, stderr).
    parsed_output_dict is None if stdout is not valid JSON.
    """
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    rc, stdout, stderr = run_script(HOOK_PATH, repo, input_text=payload)
    try:
        parsed = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        parsed = None
    return rc, parsed, stdout, stderr


def _run_hook_raw(repo, payload_str):
    """Invoke the hook with a raw stdin string (may be invalid JSON).

    Unlike _run_hook, this does not build the payload — the caller passes the
    exact bytes to feed to stdin, so fail-open paths can be exercised directly.
    Returns (returncode, parsed_output_dict_or_None, raw_stdout, stderr).
    """
    from conftest import run_cmd
    rc, stdout, stderr = run_cmd(
        [sys.executable, HOOK_PATH],
        cwd=repo,
        input_text=payload_str,
    )
    try:
        parsed = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        parsed = None
    return rc, parsed, stdout, stderr


def _hook_specific(parsed):
    """Shortcut: return the hookSpecificOutput sub-dict."""
    if parsed is None:
        return {}
    return parsed.get("hookSpecificOutput", {})


# ── Tests: whitelisted agent with memory match ────────────────────────────

class TestWhitelistedAgentWithMatch:
    def test_prompt_injected_for_ultron(self, tmp_path):
        """Task(ultron) + memory match → hookSpecificOutput.updatedInput.prompt
        contains the original prompt AND the memory block footer."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): ranking algorithm",
            f"Decision: usar {_MEM_NONCE} como estrategia interna de memoria",
        )

        prompt = _MEM_NONCE
        tool_input = {
            "subagent_type": "ultron",
            "description": "some task",
            "prompt": prompt,
            "extra_field": "preserved",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" in hso, "Expected updatedInput when memory matches"

        updated_prompt = hso["updatedInput"]["prompt"]
        assert prompt in updated_prompt, "Original prompt must be preserved verbatim"
        assert "PROJECT MEMORY" in updated_prompt, "Footer header must be present"
        assert _MEM_NONCE in updated_prompt, "Memory block content must appear in prompt"
        # The memory block delimiters must be present
        assert "---" in updated_prompt

    def test_all_other_tool_input_fields_preserved(self, tmp_path):
        """tool_input fields other than prompt must be copied intact."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce design",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": "ultron",
            "description": "implement something",
            "prompt": _MEM_NONCE,
            "extra_field": "preserved_value",
            "another": 42,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert "updatedInput" in hso

        updated = hso["updatedInput"]
        assert updated.get("subagent_type") == "ultron"
        assert updated.get("description") == "implement something"
        assert updated.get("extra_field") == "preserved_value"
        assert updated.get("another") == 42

    def test_permission_decision_reason_set(self, tmp_path):
        """When injecting, permissionDecisionReason must be set."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": "ultron",
            "prompt": _MEM_NONCE,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecisionReason") == "git-memory recall injected"


# ── Tests: non-whitelisted agent → passthrough ────────────────────────────

class TestNonWhitelistedAgent:
    def test_bilbo_not_injected(self, tmp_path):
        """bilbo is excluded from the whitelist → no updatedInput."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): BM25 design",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "bilbo",
            "prompt": "BM25 recall ranking",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso, "bilbo must not receive memory injection"

    def test_gitto_not_injected(self, tmp_path):
        """gitto is excluded from the whitelist → no updatedInput."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): BM25 design",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "gitto",
            "prompt": "BM25 recall ranking",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso

    def test_unknown_agent_not_injected(self, tmp_path):
        """An unknown agent name not in the whitelist → no updatedInput."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): BM25 design",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "unknown-agent-xyz",
            "prompt": "BM25 recall ranking",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso


# ── Tests: non-Task tool_name → passthrough ──────────────────────────────

class TestNonTaskTool:
    def test_bash_passes_through(self, tmp_path):
        """tool_name=Bash → hook does not intercept."""
        repo = _make_repo(tmp_path)
        tool_input = {"command": "echo hello"}

        rc, parsed, _, _ = _run_hook(repo, "Bash", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso

    def test_write_passes_through(self, tmp_path):
        """tool_name=Write → hook does not intercept."""
        repo = _make_repo(tmp_path)
        tool_input = {"file_path": "/tmp/x.txt", "content": "hello"}

        rc, parsed, _, _ = _run_hook(repo, "Write", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso


# ── Tests: no memory match → passthrough ─────────────────────────────────

class TestNoMemoryMatch:
    def test_no_match_no_injection(self, tmp_path):
        """When recall() returns empty string → no updatedInput emitted."""
        repo = _make_repo(tmp_path)
        # Commit memory that is completely unrelated to the prompt
        _commit(
            repo,
            "decision(plugin/graph): graph layout",
            "Decision: usar fuerza dirigida para grafo de visualizacion",
        )

        tool_input = {
            "subagent_type": "ultron",
            "prompt": _NO_MATCH_NONCE,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso, "No match → must not inject"

    def test_empty_repo_no_injection(self, tmp_path):
        """Empty repo (no memory commits) → no updatedInput."""
        repo = _make_repo(tmp_path)

        tool_input = {
            "subagent_type": "ultron",
            "prompt": _NO_MATCH_NONCE,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso


# ── Tests: malformed input → fail-open ───────────────────────────────────

class TestFailOpen:
    def test_malformed_json_returns_allow_exit0(self, tmp_path):
        """Invalid JSON on stdin → fail-open: allow, exit 0, no exception."""
        repo = _make_repo(tmp_path)
        from conftest import run_cmd
        rc, stdout, stderr = run_cmd(
            [sys.executable, HOOK_PATH],
            cwd=repo,
            input_text="THIS IS NOT JSON {{{",
        )

        assert rc == 0, f"Malformed JSON must not cause non-zero exit; got rc={rc}"
        # Must still emit valid allow JSON
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Hook must emit valid JSON even on malformed input; got: {stdout!r}")

        hso = parsed.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso

    def test_empty_stdin_returns_allow_exit0(self, tmp_path):
        """Empty stdin → fail-open."""
        repo = _make_repo(tmp_path)
        from conftest import run_cmd
        rc, stdout, stderr = run_cmd(
            [sys.executable, HOOK_PATH],
            cwd=repo,
            input_text="",
        )

        assert rc == 0
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Must emit valid JSON on empty stdin; got: {stdout!r}")

        hso = parsed.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "allow"

    def test_deny_never_emitted(self, tmp_path):
        """Hook must never emit permissionDecision: 'deny' under any condition."""
        repo = _make_repo(tmp_path)

        # Test with several problematic inputs
        bad_payloads = [
            "not json",
            "{}",
            json.dumps({"tool_name": "Task", "tool_input": None}),
            json.dumps({"tool_name": "Task", "tool_input": {}}),
        ]

        from conftest import run_cmd
        for payload in bad_payloads:
            rc, stdout, stderr = run_cmd(
                [sys.executable, HOOK_PATH],
                cwd=repo,
                input_text=payload,
            )
            assert rc == 0, f"Hook must exit 0 for payload {payload!r}; got rc={rc}"
            parsed = json.loads(stdout)
            hso = parsed.get("hookSpecificOutput", {})
            decision = hso.get("permissionDecision", "")
            assert decision != "deny", (
                f"Hook must never emit 'deny'; got {decision!r} for payload {payload!r}"
            )


class TestFailOpenMissingToolInput:
    def test_missing_tool_input_returns_allow(self, tmp_path):
        """JSON without tool_input field → fail-open: allow, no updatedInput."""
        repo = _make_repo(tmp_path)
        payload = json.dumps({"tool_name": "Task"})
        rc, parsed, stdout, _ = _run_hook_raw(repo, payload)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso


# ── Tests: subagent_type normalisation ────────────────────────────────────

class TestSubagentTypeNormalisation:
    def test_namespaced_form_recognised(self, tmp_path):
        """'unmassk-toolkit:ultron' is recognised (segment after last ':')."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": "unmassk-toolkit:ultron",
            "prompt": _MEM_NONCE,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" in hso, (
            "'unmassk-toolkit:ultron' must be normalised to 'ultron' and whitelisted"
        )

    def test_bare_form_recognised(self, tmp_path):
        """'ultron' (no namespace prefix) is also recognised."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": "ultron",
            "prompt": _MEM_NONCE,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" in hso, "'ultron' (bare) must be whitelisted"

    def test_namespaced_bilbo_still_excluded(self, tmp_path):
        """'unmassk-toolkit:bilbo' → bilbo is still excluded after normalisation."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "unmassk-toolkit:bilbo",
            "prompt": "BM25 recall ranking",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso, "bilbo must be excluded even with namespace prefix"

    def test_uppercase_normalised_to_lower(self, tmp_path):
        """'ULTRON' (uppercase) is normalised to 'ultron' and whitelisted."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": "ULTRON",
            "prompt": _MEM_NONCE,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        # Uppercase should be normalised to lowercase and matched
        assert "updatedInput" in hso, "ULTRON must normalise to ultron and be whitelisted"


# ── Tests: empty / absent prompt → passthrough ────────────────────────────

class TestEmptyPrompt:
    def test_absent_prompt_passthrough(self, tmp_path):
        """tool_input without 'prompt' key → passthrough, no injection."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "ultron",
            "description": "a task without prompt",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso

    def test_empty_string_prompt_passthrough(self, tmp_path):
        """prompt='' → passthrough."""
        repo = _make_repo(tmp_path)
        tool_input = {
            "subagent_type": "ultron",
            "prompt": "",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso

    def test_whitespace_only_prompt_passthrough(self, tmp_path):
        """prompt='   ' (whitespace only) → passthrough."""
        repo = _make_repo(tmp_path)
        tool_input = {
            "subagent_type": "ultron",
            "prompt": "   \t\n",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso


# ── Tests: all whitelisted agents ────────────────────────────────────────

class TestAllWhitelistedAgents:
    """Each member of the whitelist receives injection when memory matches."""

    @pytest.mark.parametrize("agent", [
        "ultron", "dante", "cerberus", "argus",
        "moriarty", "house", "yoda", "alexandria",
    ])
    def test_whitelisted_agent_receives_injection(self, agent, tmp_path):
        """Agent '{agent}' is in the whitelist and receives memory injection."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": agent,
            "prompt": _MEM_NONCE,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" in hso, f"Agent '{agent}' must receive injection"


# ── Tests: subagent_type absent or empty → passthrough ───────────────────

class TestSubagentTypeAbsentOrEmpty:
    def test_subagent_type_key_absent_passthrough(self, tmp_path):
        """tool_input has no 'subagent_type' key → passthrough, no injection.

        _normalize_agent(subagent_type) receives '' (the .get() default),
        which strips+lowers to '' — not in the whitelist → passthrough.
        """
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "prompt": "BM25 recall ranking",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso, (
            "Missing subagent_type must not inject memory"
        )

    def test_subagent_type_empty_string_passthrough(self, tmp_path):
        """tool_input has subagent_type='' → passthrough, no injection.

        Empty string normalises to '' which is not in the whitelist.
        """
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "",
            "prompt": "BM25 recall ranking",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso, (
            "Empty subagent_type must not inject memory"
        )


# ── Tests: updatedInput preserves extra tool_input fields ────────────────

class TestUpdatedInputPreservesFields:
    def test_model_field_preserved_in_updated_input(self, tmp_path):
        """'model' field in tool_input must survive in updatedInput unchanged."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": "ultron",
            "prompt": _MEM_NONCE,
            "description": "implement ranking",
            "model": "claude-opus-4-5",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert "updatedInput" in hso, "Expected memory injection to occur"
        updated = hso["updatedInput"]
        assert updated.get("model") == "claude-opus-4-5", (
            "'model' field must be preserved verbatim in updatedInput"
        )
        assert updated.get("description") == "implement ranking", (
            "'description' field must also be preserved"
        )

    def test_arbitrary_extra_fields_all_preserved(self, tmp_path):
        """All extra fields in tool_input (description, model, and custom) are preserved.

        _allow_with_injection does dict(tool_input) then overwrites only 'prompt'.
        Every other key must survive with its original value and type.
        """
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": "dante",
            "prompt": _MEM_NONCE,
            "description": "write tests",
            "model": "claude-sonnet-4-6",
            "max_turns": 10,
            "custom_flag": True,
            "nested": {"key": "value"},
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert "updatedInput" in hso
        updated = hso["updatedInput"]

        assert updated.get("subagent_type") == "dante"
        assert updated.get("description") == "write tests"
        assert updated.get("model") == "claude-sonnet-4-6"
        assert updated.get("max_turns") == 10
        assert updated.get("custom_flag") is True
        assert updated.get("nested") == {"key": "value"}

    def test_only_prompt_field_is_modified(self, tmp_path):
        """After injection, only the 'prompt' value changes; all other keys are untouched."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        original_prompt = _MEM_NONCE
        tool_input = {
            "subagent_type": "ultron",
            "prompt": original_prompt,
            "description": "some description",
            "model": "claude-haiku-3-5",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert "updatedInput" in hso
        updated = hso["updatedInput"]

        # prompt is changed — extended with footer
        assert updated["prompt"] != original_prompt, "prompt must be rewritten"
        assert original_prompt in updated["prompt"], "original prompt must be preserved"
        # every other field is identical
        assert updated["subagent_type"] == tool_input["subagent_type"]
        assert updated["description"] == tool_input["description"]
        assert updated["model"] == tool_input["model"]


# ── Tests: memory block structure in injected prompt ─────────────────────

class TestMemoryBlockStructure:
    def test_footer_delimiters_present_in_injected_prompt(self, tmp_path):
        """Injected prompt contains two '---' delimiter lines (header + tail)."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        prompt = _MEM_NONCE
        tool_input = {"subagent_type": "ultron", "prompt": prompt}

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        updated_prompt = _hook_specific(parsed)["updatedInput"]["prompt"]

        # The footer header starts with '\n\n---\n' and the tail ends with '\n---'
        # Both must be present as separate occurrences.
        assert updated_prompt.count("---") >= 2, (
            "Injected prompt must contain at least two '---' delimiter lines"
        )

    def test_memory_block_between_delimiters_is_intact(self, tmp_path):
        """Multi-line memory block content sits between the --- delimiters."""
        repo = _make_repo(tmp_path)
        # Two commits so the memory block likely contains multiple lines.
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: usar {_MEM_NONCE} para estrategia interna xyzstructure",
        )
        _commit(
            repo,
            "memo(plugin/recall): recall preference",
            "Memo: preference - xyzstructure es la preferencia de ranking",
        )

        prompt = f"{_MEM_NONCE} xyzstructure"
        tool_input = {"subagent_type": "ultron", "prompt": prompt}

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert "updatedInput" in hso, "Expected injection for matching prompt"

        updated_prompt = hso["updatedInput"]["prompt"]

        # Original prompt appears before the footer header.
        first_delimiter_pos = updated_prompt.find("---")
        assert first_delimiter_pos > updated_prompt.find(prompt), (
            "Original prompt must appear before the first '---' delimiter"
        )

        # Memory content (xyzstructure) must appear after the first delimiter.
        memory_section_start = first_delimiter_pos
        assert "xyzstructure" in updated_prompt[memory_section_start:], (
            "Memory block content must appear after the opening '---'"
        )

        # The prompt must end with '\n---' (the footer tail).
        assert updated_prompt.endswith("\n---"), (
            "Injected prompt must end with '\\n---'"
        )

    def test_footer_header_label_present(self, tmp_path):
        """The footer contains the 'PROJECT MEMORY' section label."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {"subagent_type": "cerberus", "prompt": _MEM_NONCE}

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        updated_prompt = _hook_specific(parsed)["updatedInput"]["prompt"]
        assert "PROJECT MEMORY" in updated_prompt, (
            "Footer label 'PROJECT MEMORY' must be present in injected prompt"
        )


# ── Tests: subagent_type casing and namespace variations ─────────────────

class TestSubagentTypeCasingAndNamespace:
    def test_mixed_case_namespace_and_name(self, tmp_path):
        """'unmassk-toolkit:Ultron' — namespace bare, name mixed case → whitelisted.

        _normalize_agent takes the last ':' segment and lowercases it.
        'unmassk-toolkit:Ultron' → rsplit gives 'Ultron' → .lower() → 'ultron'.
        """
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": "unmassk-toolkit:Ultron",
            "prompt": _MEM_NONCE,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" in hso, (
            "'unmassk-toolkit:Ultron' must normalise to 'ultron' and be whitelisted"
        )

    def test_subagent_type_with_leading_trailing_spaces(self, tmp_path):
        """'  ultron  ' (padded with spaces) → .strip().lower() → 'ultron' → whitelisted.

        _normalize_agent calls .strip().lower() after rsplit.
        """
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": "  ultron  ",
            "prompt": _MEM_NONCE,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" in hso, (
            "'  ultron  ' with spaces must be stripped and whitelisted"
        )

    def test_mixed_case_bare_name_whitelisted(self, tmp_path):
        """'Dante' (title case, no namespace) → lowercases to 'dante' → whitelisted."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": "Dante",
            "prompt": _MEM_NONCE,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" in hso, "'Dante' must normalise to 'dante' and be whitelisted"

    def test_namespaced_mixed_case_excluded_agent_stays_excluded(self, tmp_path):
        """'TOOLKIT:Bilbo' normalises to 'bilbo' which is still not in the whitelist."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "TOOLKIT:Bilbo",
            "prompt": "BM25 recall ranking",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso, (
            "'TOOLKIT:Bilbo' → 'bilbo' must still be excluded"
        )


# ── Tests: fail-open invariant (deny/block never emitted) ────────────────

class TestFailOpenInvariant:
    """Comprehensive invariant: 'deny' and 'block' must NEVER appear in output."""

    def _assert_no_deny_or_block(self, raw_stdout: str, context: str) -> None:
        """Assert that hookSpecificOutput.permissionDecision is never 'deny' or 'block'.

        Checks the field value directly rather than substring-searching the full
        serialised JSON, which would give false positives if memory content
        happened to contain the words 'deny' or 'block'.
        """
        assert raw_stdout, (
            f"Hook must always emit output; got empty stdout; context={context!r}"
        )
        try:
            parsed = json.loads(raw_stdout)
        except json.JSONDecodeError:
            pytest.fail(
                f"Hook must always emit valid JSON; context={context!r}, "
                f"stdout={raw_stdout!r}"
            )
        decision = parsed.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision not in ("deny", "block"), (
            f"permissionDecision must never be 'deny' or 'block'; "
            f"got {decision!r}; context={context!r}"
        )

    def test_invariant_whitelisted_agent_with_match(self, tmp_path):
        """Normal injection path must not emit deny or block."""
        from conftest import run_cmd
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )
        payload = json.dumps({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "ultron", "prompt": _MEM_NONCE},
        })
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=payload)
        assert rc == 0
        self._assert_no_deny_or_block(stdout, "whitelisted agent with match")

    def test_invariant_non_whitelisted_agent(self, tmp_path):
        """Passthrough for excluded agent must not emit deny or block."""
        from conftest import run_cmd
        repo = _make_repo(tmp_path)
        payload = json.dumps({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "bilbo", "prompt": "BM25 recall ranking"},
        })
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=payload)
        assert rc == 0
        self._assert_no_deny_or_block(stdout, "non-whitelisted agent bilbo")

    def test_invariant_malformed_json(self, tmp_path):
        """Fail-open for malformed JSON must not emit deny or block."""
        from conftest import run_cmd
        repo = _make_repo(tmp_path)
        rc, stdout, _ = run_cmd(
            [sys.executable, HOOK_PATH], cwd=repo, input_text="{{{not json"
        )
        assert rc == 0
        self._assert_no_deny_or_block(stdout, "malformed json")

    def test_invariant_null_tool_input(self, tmp_path):
        """tool_input: null → fail-open, no deny."""
        from conftest import run_cmd
        repo = _make_repo(tmp_path)
        payload = json.dumps({"tool_name": "Task", "tool_input": None})
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=payload)
        assert rc == 0
        self._assert_no_deny_or_block(stdout, "null tool_input")

    def test_invariant_empty_stdin(self, tmp_path):
        """Empty stdin must not emit deny or block."""
        from conftest import run_cmd
        repo = _make_repo(tmp_path)
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text="")
        assert rc == 0
        self._assert_no_deny_or_block(stdout, "empty stdin")

    def test_invariant_non_task_tool(self, tmp_path):
        """Non-Task tool must not emit deny or block."""
        from conftest import run_cmd
        repo = _make_repo(tmp_path)
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=payload)
        assert rc == 0
        self._assert_no_deny_or_block(stdout, "non-Task tool")


# ── Tests: stdin edge cases ───────────────────────────────────────────────

class TestStdinEdgeCases:
    def test_non_json_utf8_text_fail_open(self, tmp_path):
        """Plain UTF-8 text (not JSON) on stdin → fail-open: allow, exit 0.

        The hook writes a diagnostic traceback to stderr for malformed input
        (best-effort signal); stdout remains a valid allow JSON and rc==0.
        """
        from conftest import run_cmd
        repo = _make_repo(tmp_path)
        rc, stdout, stderr = run_cmd(
            [sys.executable, HOOK_PATH],
            cwd=repo,
            input_text="just some plain text that is not json at all",
        )
        assert rc == 0, f"Non-JSON UTF-8 text must not cause non-zero exit; rc={rc}"
        assert "Traceback" in stderr, f"Diagnostic traceback must appear in stderr; stderr={stderr!r}"
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Must emit valid JSON on non-JSON stdin; got: {stdout!r}")
        hso = parsed.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "allow"

    def test_json_array_instead_of_object_fail_open(self, tmp_path):
        """JSON array on stdin (not an object) → fail-open: allow, exit 0.

        The hook writes a diagnostic traceback to stderr for malformed input
        (best-effort signal); stdout remains a valid allow JSON and rc==0.
        """
        from conftest import run_cmd
        repo = _make_repo(tmp_path)
        rc, stdout, stderr = run_cmd(
            [sys.executable, HOOK_PATH],
            cwd=repo,
            input_text='["tool_name", "Task"]',
        )
        assert rc == 0, f"JSON array must not cause non-zero exit; rc={rc}"
        assert "Traceback" in stderr, f"Diagnostic traceback must appear in stderr; stderr={stderr!r}"
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Must emit valid JSON for array-shaped input; got: {stdout!r}")
        hso = parsed.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "allow"

    def test_json_null_stdin_fail_open(self, tmp_path):
        """JSON literal 'null' on stdin → fail-open: allow, exit 0.

        The hook writes a diagnostic traceback to stderr for malformed input
        (best-effort signal); stdout remains a valid allow JSON and rc==0.
        """
        from conftest import run_cmd
        repo = _make_repo(tmp_path)
        rc, stdout, stderr = run_cmd(
            [sys.executable, HOOK_PATH],
            cwd=repo,
            input_text="null",
        )
        assert rc == 0, f"JSON null must not cause non-zero exit; rc={rc}"
        assert "Traceback" in stderr, f"Diagnostic traceback must appear in stderr; stderr={stderr!r}"
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Must emit valid JSON for null input; got: {stdout!r}")
        hso = parsed.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "allow"


# ── Tests: very long prompt — query truncation does not truncate prompt ───

class TestLongPromptQueryTruncation:
    def test_original_prompt_intact_when_query_exceeds_max_query_len(self, tmp_path):
        """recall() truncates its internal query to MAX_QUERY_LEN (2000 chars) when
        the prompt is very long, but the hook must preserve the FULL original prompt
        in updatedInput.prompt — the footer is appended to the complete original, not
        to the truncated search string.

        Design contract (intentional behaviour):
          - recall(prompt) caps 'query = query[:2000]' for BM25 search only.
          - _build_prompt(original_prompt, memory_block) receives the ORIGINAL prompt
            unmodified; the 2000-char cap is an internal search guard, not a prompt cap.
          - updatedInput.prompt = original_prompt + footer (original_prompt is 10 000+ chars).

        The seeded token 'xqzlongprompttoken' appears within the first 2000 chars so
        that truncation does not suppress it, guaranteeing a recall hit and injection.

        Padding is built from nonce vocabulary only (no real English words like
        "implement"/"feature"/"coverage") — repeating ordinary English 200x makes
        the skill gate's BM25 score climb into the hundreds (verified empirically:
        494.7 against 'frontend-react' with the original English padding), which
        would DENY this prompt instead of exercising the memory-allow path this
        test targets. Repeated nonce vocabulary is verified to still score 0.
        """
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): xqzlongprompttoken strategy",
            "Decision: xqzlongprompttoken es la estrategia de inyeccion para prompts largos",
        )

        # Build a deterministic 10 000+ char prompt.
        # The distinguishing token appears at the start (well within the 2000-char
        # search window), followed by padding that pushes the total past 10 000 chars.
        seed_token = "xqzlongprompttoken"
        padding_unit = f"xqzlongprompttoken {_MEM_NONCE} qzxdfklmnpwrtjhbg "
        prompt = seed_token + " " + (padding_unit * 200)  # ≈ 12 000 chars
        assert len(prompt) > 10_000, "Test prerequisite: prompt must exceed 10 000 chars"
        assert len(prompt) > 2000, "Test prerequisite: prompt must exceed MAX_QUERY_LEN"

        tool_input = {
            "subagent_type": "ultron",
            "prompt": prompt,
        }

        rc, parsed, _, stderr = _run_hook(repo, "Task", tool_input)

        assert rc == 0, f"Hook must exit 0; rc={rc}, stderr={stderr!r}"
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"

        # Injection must have fired (recall found the seeded token).
        assert "updatedInput" in hso, (
            "Expected recall hit on seeded token — updatedInput must be present"
        )

        updated_prompt = hso["updatedInput"]["prompt"]

        # 1. The FULL original prompt (all 10 000+ chars) must be present verbatim.
        assert updated_prompt.startswith(prompt), (
            f"updatedInput.prompt must start with the complete original prompt "
            f"({len(prompt)} chars); got length {len(updated_prompt)}"
        )

        # 2. The prompt length in updatedInput must be strictly greater than the
        #    original (footer was appended, not a truncated substitute).
        assert len(updated_prompt) > len(prompt), (
            "updatedInput.prompt must be longer than the original — footer was appended"
        )

        # 3. The memory footer must be present.
        assert "PROJECT MEMORY" in updated_prompt, (
            "Footer label 'PROJECT MEMORY' must appear in the injected prompt"
        )

        # 4. The seeded memory content must appear in the footer section.
        assert seed_token in updated_prompt, (
            f"Seeded token '{seed_token}' from the memory commit must appear in the output"
        )

        # 5. The prompt must end with the footer tail '\n---'.
        assert updated_prompt.endswith("\n---"), (
            "Injected prompt must end with '\\n---'"
        )


# ══════════════════════════════════════════════════════════════════════════
# NEW COVERAGE: skill gate (issue #68 — current, deny-based contract)
# ══════════════════════════════════════════════════════════════════════════
#
# Verified live (see decision cd42912): for a crew agent's prompt, the hook
# runs skill-search.py --json BEFORE memory recall. If the top result scores
# >= _SKILL_SCORE_THRESHOLD and the prompt doesn't already carry the
# "[DOMAIN SKILL —" marker, the spawn is DENIED with the skill block pasted
# into the reason (anti-loop: re-invoking with the block already in the
# prompt allows). Any failure of the skill search itself (missing script,
# non-zero exit, timeout, malformed JSON, unexpected shape) is fail-open —
# falls through to memory recall, never a deny. Excluded agents
# (bilbo/gitto/unknown) never reach the gate at all.
#
# Real-by-default (§34.5): every branch except the two failure-mode
# simulations (timeout, malformed JSON — genuinely unreproducible on demand
# from the real searcher) runs the REAL skill-search.py subprocess against a
# REAL, disposable fixture skill written INSIDE the temp repo (a `.skillcat`
# + colocated `SKILL.md`). skill-search.py's own find_git_root() walks up
# from cwd to the nearest `.git` and adds that root to its rglob search dirs
# (see collect_search_dirs() in scripts/skill-search.py), so the fixture is
# discoverable regardless of whatever real skills happen to be installed on
# the host running these tests — verified empirically: the fixture's own
# nonce trigger term ranks #1 (score 6.1) even against the real ~36-skill
# corpus. Every score/path assertion below is read from a DIRECT real
# invocation of skill-search.py against the same repo/prompt (the real
# producer) — never hand-typed (§34).
#
# The two failure-mode simulations reuse this repo's established in-process
# importlib.util.spec_from_file_location pattern for hyphenated filenames
# (see unmassk-toolkit-python-test-conventions), with subprocess.run
# monkeypatched SELECTIVELY: only a call whose command line mentions
# "skill-search" is faked; every other subprocess.run call (git, inside
# recall()) passes through to the real implementation — this prevents a
# false-pass where an unrelated exception (not the simulated failure) is
# what actually produced the fail-open result.
#
# _SKILL_MARKER / _SKILL_SCORE_THRESHOLD are read from the hook module
# itself (imported in-process) rather than hand-typed, per Hard Rules (No
# Hardcoded Values) — if Ultron ever renames either constant, these tests
# stay correct without a text-search-and-replace.

_skill_gate_hook_spec = importlib.util.spec_from_file_location(
    "pre_task_recall_module_for_skill_gate_tests", HOOK_PATH
)
_skill_gate_hook_mod = importlib.util.module_from_spec(_skill_gate_hook_spec)
_skill_gate_hook_spec.loader.exec_module(_skill_gate_hook_mod)

SKILL_MARKER = _skill_gate_hook_mod._SKILL_MARKER
SKILL_SCORE_THRESHOLD = _skill_gate_hook_mod._SKILL_SCORE_THRESHOLD
SKILL_CONFIDENT = _skill_gate_hook_mod._SKILL_CONFIDENT
SKILL_MAX = _skill_gate_hook_mod._SKILL_MAX

# Nonce vocabulary for the fixture skill — deliberately not real English, so
# it can only ever match via the fixture itself, never by accidental overlap
# with real skill descriptions.
_GATE_TRIGGER = "zzzqrxgatefixturetrigger882"
_GATE_FIXTURE_SKILL_NAME = "unmassk-test-gate-skill"

# Fallback-band fixture (score in [SKILL_SCORE_THRESHOLD, SKILL_CONFIDENT)) —
# see _write_diluted_gate_skill_fixture.
_FALLBACK_TRIGGER = "zzzqrxfallbacktrigger339"
_FALLBACK_FIXTURE_SKILL_NAME = "unmassk-test-fallback-skill"


def _write_gate_skill_fixture(repo, skill_name=_GATE_FIXTURE_SKILL_NAME, trigger=_GATE_TRIGGER, reps=1):
    """Write a real .skillcat + colocated SKILL.md INSIDE the temp repo.

    Discovered by the real skill-search.py via its own find_git_root() ->
    rglob("*.skillcat") over the repo root — deterministic regardless of
    whatever real skills happen to be installed on the host running these
    tests. Not git-tracked; skill discovery is filesystem-based, not git
    state.

    `reps` repeats the trigger term in the `triggers` column (BM25 term
    frequency knob) — used by the multi-skill tests to force distinct,
    strictly-ordered scores across several confident fixtures planted in the
    same repo. `reps=1` (the default) reproduces the exact byte output every
    pre-existing single-fixture test already relies on.
    """
    skill_dir = os.path.join(repo, "fixture_skills", skill_name)
    os.makedirs(skill_dir, exist_ok=True)

    trig_field = " ".join([trigger] * reps) + " domain trigger fixture"

    skillcat_path = os.path.join(skill_dir, f"{skill_name}.skillcat")
    with open(skillcat_path, "w", encoding="utf-8", newline="") as f:
        f.write("name,plugin,triggers,domains,frameworks,tools\n")
        f.write(
            '{},{},"{}","{} domain",none,none\n'.format(
                skill_name, "unmassk-test-plugin", trig_field, trigger
            )
        )

    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    with open(skill_md_path, "w", encoding="utf-8") as f:
        f.write(
            "---\n"
            f"name: {skill_name}\n"
            f"description: Fixture domain skill for {trigger} testing.\n"
            "---\n\n"
            "# Fixture skill\n\nUsed only by pre-task-recall.py's test suite.\n"
        )

    return skill_dir, skillcat_path, skill_md_path


def _write_diluted_gate_skill_fixture(repo, skill_name=None, trigger=None, filler_count=60):
    """Write a fixture skill whose trigger term is diluted by filler
    vocabulary in its `triggers` column, so its real BM25 score lands in the
    fallback band [_SKILL_SCORE_THRESHOLD, _SKILL_CONFIDENT) instead of
    clearing the confident bar outright — the same length-normalisation
    effect BM25 always applies (a longer document scores lower for the same
    term frequency), not a fabricated number. Used to exercise the "nothing
    reaches _SKILL_CONFIDENT, but the top clears _SKILL_SCORE_THRESHOLD"
    fallback branch of _find_gate_skills(). Every score assertion using this
    fixture still re-derives the actual number from a live skill-search.py
    subprocess call (§34) — the dilution only shapes which band the real
    score falls in, it never substitutes for measuring it.
    """
    skill_name = skill_name or _FALLBACK_FIXTURE_SKILL_NAME
    trigger = trigger or _FALLBACK_TRIGGER
    skill_dir = os.path.join(repo, "fixture_skills", skill_name)
    os.makedirs(skill_dir, exist_ok=True)

    filler = " ".join(f"fillerword{i}" for i in range(filler_count))
    skillcat_path = os.path.join(skill_dir, f"{skill_name}.skillcat")
    with open(skillcat_path, "w", encoding="utf-8", newline="") as f:
        f.write("name,plugin,triggers,domains,frameworks,tools\n")
        f.write(
            '{},{},"{} {}","none",none,none\n'.format(
                skill_name, "unmassk-test-plugin", trigger, filler
            )
        )

    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    with open(skill_md_path, "w", encoding="utf-8") as f:
        f.write(
            "---\n"
            f"name: {skill_name}\n"
            f"description: Diluted fixture domain skill for {trigger} testing.\n"
            "---\n\n"
            "# Diluted fixture skill\n\nUsed only by pre-task-recall.py's test suite.\n"
        )

    return skill_dir, skillcat_path, skill_md_path


def _real_skill_search_top(repo, prompt):
    """Run the REAL skill-search.py as a subprocess against `repo` (so its
    own find_git_root() resolves to `repo`) and return the top parsed JSON
    result, or None if there are no results at all. Ground-truth producer
    for every score/path assertion below — never hand-typed (§34)."""
    results = _real_skill_search_results(repo, prompt)
    return results[0] if results else None


def _real_skill_search_results(repo, prompt):
    """Run the REAL skill-search.py as a subprocess against `repo` and return
    the FULL parsed results list (not just the top). Ground-truth producer
    for the multi-skill selection/ordering/cap assertions below — never
    hand-typed (§34)."""
    rc, stdout, stderr = run_script(
        SKILL_SEARCH_SCRIPT, repo, extra_args=[prompt, "--json"]
    )
    assert rc == 0, f"skill-search.py must exit 0; stderr={stderr!r}"
    data = json.loads(stdout)
    return data.get("results") or []


# ── In-process fail-open simulation (timeout / malformed JSON only) ───────

def _fake_timeout(cmd, kwargs):
    raise subprocess.TimeoutExpired(cmd=cmd, timeout=6)


def _fake_malformed_json(cmd, kwargs):
    return subprocess.CompletedProcess(
        args=cmd, returncode=0, stdout="NOT VALID JSON {{{", stderr=""
    )


def _run_hook_inprocess_with_faked_searcher(monkeypatch, repo, tool_input, fake_run):
    """Load pre-task-recall.py fresh, in-process, with subprocess.run
    monkeypatched so ONLY a call whose command line mentions "skill-search"
    is faked. Returns (stdout_text, stderr_text)."""
    real_run = subprocess.run

    def _selective_fake_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args")
        cmd_text = " ".join(str(c) for c in cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
        if "skill-search" in cmd_text:
            return fake_run(cmd, kwargs)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _selective_fake_run)
    monkeypatch.chdir(repo)

    spec = importlib.util.spec_from_file_location("pre_task_recall_failsim", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    stdin = io.StringIO(json.dumps({"tool_name": "Task", "tool_input": tool_input}))
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    mod.main()

    return stdout.getvalue(), stderr.getvalue()


# ── (1) Strong domain match + crew agent + no marker → deny ───────────────

class TestSkillGateDomainMatchDenies:
    def test_strong_match_denies_with_real_skill_block(self, tmp_path):
        """Strong domain match, real subprocess end-to-end (§34.5 — no
        mocked skill-search): deny, with the real skill name/score/path
        pasted into the reason."""
        repo = _make_repo(tmp_path)
        _write_gate_skill_fixture(repo)
        prompt = f"implement the {_GATE_TRIGGER} feature end to end"

        top = _real_skill_search_top(repo, prompt)
        assert top is not None and top["name"] == _GATE_FIXTURE_SKILL_NAME, (
            f"Test prerequisite: fixture skill must be the top real result; got {top}"
        )
        assert top["score"] >= SKILL_SCORE_THRESHOLD, (
            f"Test prerequisite: fixture must clear the gate threshold; got {top['score']}"
        )

        tool_input = {"subagent_type": "ultron", "prompt": prompt}
        rc, parsed, _, stderr = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "deny"
        assert "updatedInput" not in hso, "A deny must never carry updatedInput"

        reason = hso.get("permissionDecisionReason", "")
        assert SKILL_MARKER in reason, "Deny reason must carry the domain-skill marker"
        assert f"Skill: {top['name']} (score {top['score']:.1f})" in reason, (
            "Injected name/score must match the REAL searcher's output verbatim (§34)"
        )
        assert f"Path: {top['skill_md']}" in reason, (
            "Injected path must be the REAL skill_md path the searcher produced"
        )
        assert "skill gate: deny" in stderr, "Deny branch must leave a stderr breadcrumb"

        # Multi-skill contract (issue #68 expansion): a single confident
        # match must still produce exactly ONE block and the SINGULAR
        # header — this is the "still correct" case the expanded selection
        # logic must not regress.
        assert reason.count(SKILL_MARKER) == 1, (
            "A single confident match must produce exactly one skill block"
        )
        assert "el siguiente bloque" in reason, "Single-block deny must use the singular header"
        assert "los siguientes bloques" not in reason, (
            "Single-block deny must NOT use the plural header"
        )


# ── (2) Marker already present → anti-loop, no re-deny ────────────────────

class TestSkillGateMarkerAntiLoop:
    def test_marker_present_prevents_redeny(self, tmp_path):
        """Same strong-match prompt, but the marker is ALREADY present (the
        orchestrator's retry) → the gate must not re-trigger."""
        repo = _make_repo(tmp_path)
        _write_gate_skill_fixture(repo)
        domain_prompt = f"implement the {_GATE_TRIGGER} feature end to end"

        top = _real_skill_search_top(repo, domain_prompt)
        assert top is not None and top["score"] >= SKILL_SCORE_THRESHOLD

        # Sanity: the SAME prompt without the marker denies — proves the
        # allow below is due to the marker, not an unrelated non-match.
        _, parsed0, _, _ = _run_hook(
            repo, "Task", {"subagent_type": "ultron", "prompt": domain_prompt}
        )
        assert _hook_specific(parsed0).get("permissionDecision") == "deny", (
            "Test prerequisite: the bare domain prompt must deny"
        )

        retried_prompt = (
            f"{SKILL_MARKER} auto-selected for this task]\n"
            f"Skill: {top['name']} (score {top['score']:.1f})\n"
            f"Path: {top['skill_md']}\n\n"
            + domain_prompt
        )
        tool_input = {"subagent_type": "ultron", "prompt": retried_prompt}
        rc, parsed, _, stderr = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow", "Marker presence must prevent re-deny"
        assert "skill gate: allow (marcador presente)" in stderr


# ── (3) Score below threshold → gate doesn't fire, memory untouched ───────

class TestSkillGateLowScoreAllowsMemory:
    def test_low_score_nonce_allows_and_memory_still_injects(self, tmp_path):
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        top = _real_skill_search_top(repo, _MEM_NONCE)
        assert top is None or top["score"] < SKILL_SCORE_THRESHOLD, (
            f"Test prerequisite: nonce must not clear the gate threshold; got {top}"
        )

        tool_input = {"subagent_type": "ultron", "prompt": _MEM_NONCE}
        rc, parsed, _, stderr = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" in hso, "Memory match must still inject when the gate doesn't fire"
        assert _MEM_NONCE in hso["updatedInput"]["prompt"]
        assert "skill gate: allow (no match)" in stderr


# ── (4) Searcher fails (timeout / malformed JSON) → fail-open, never deny ─

class TestSkillGateSearcherFailsOpen:
    def test_timeout_fails_open_never_denies(self, tmp_path, monkeypatch):
        """A prompt that WOULD deny if the real searcher ran (fixture
        planted, verified separately in TestSkillGateDomainMatchDenies) must
        still allow when the searcher itself times out."""
        repo = _make_repo(tmp_path)
        _write_gate_skill_fixture(repo)
        prompt = f"implement the {_GATE_TRIGGER} feature end to end"

        stdout_text, stderr_text = _run_hook_inprocess_with_faked_searcher(
            monkeypatch, repo, {"subagent_type": "ultron", "prompt": prompt}, _fake_timeout
        )
        parsed = json.loads(stdout_text)
        hso = parsed.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "allow"
        assert "skill gate: fail-open" in stderr_text
        assert "timeout" in stderr_text

    def test_malformed_json_fails_open_never_denies(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        _write_gate_skill_fixture(repo)
        prompt = f"implement the {_GATE_TRIGGER} feature end to end"

        stdout_text, stderr_text = _run_hook_inprocess_with_faked_searcher(
            monkeypatch, repo, {"subagent_type": "ultron", "prompt": prompt}, _fake_malformed_json
        )
        parsed = json.loads(stdout_text)
        hso = parsed.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "allow"
        assert "skill gate: fail-open" in stderr_text
        assert "malformed JSON" in stderr_text


# ── (5) Excluded agent + strong domain match → passthrough, never deny ────

class TestSkillGateExcludedAgentPassthrough:
    @pytest.mark.parametrize("agent", ["bilbo", "gitto"])
    def test_excluded_agent_strong_match_passthrough(self, agent, tmp_path):
        """Exclusion happens before the gate is ever reached (same
        whitelist check as memory recall) — score is irrelevant."""
        repo = _make_repo(tmp_path)
        _write_gate_skill_fixture(repo)
        prompt = f"implement the {_GATE_TRIGGER} feature end to end"

        top = _real_skill_search_top(repo, prompt)
        assert top is not None and top["score"] >= SKILL_SCORE_THRESHOLD

        tool_input = {"subagent_type": agent, "prompt": prompt}
        rc, parsed, _, stderr = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso
        assert "skill gate: deny" not in stderr


# ── (6) Invariant: exactly ONE branch ever denies ──────────────────────────

class TestSkillGateInvariant:
    def test_exactly_one_branch_denies(self, tmp_path):
        """Across the strong-match/marker/low-score/excluded-agent branches,
        the clean strong-match-no-marker case is the ONLY one that denies."""
        results = {}

        repo = _make_repo(tmp_path / "shared")
        _write_gate_skill_fixture(repo)
        domain_prompt = f"implement the {_GATE_TRIGGER} feature end to end"
        top = _real_skill_search_top(repo, domain_prompt)
        assert top is not None and top["score"] >= SKILL_SCORE_THRESHOLD

        _, parsed_a, _, _ = _run_hook(
            repo, "Task", {"subagent_type": "ultron", "prompt": domain_prompt}
        )
        results["strong_match_no_marker"] = _hook_specific(parsed_a).get("permissionDecision")

        retried_prompt = (
            f"{SKILL_MARKER} auto-selected]\n"
            f"Skill: {top['name']} (score {top['score']:.1f})\n"
            f"Path: {top['skill_md']}\n\n" + domain_prompt
        )
        _, parsed_b, _, _ = _run_hook(
            repo, "Task", {"subagent_type": "ultron", "prompt": retried_prompt}
        )
        results["marker_present"] = _hook_specific(parsed_b).get("permissionDecision")

        repo_low = _make_repo(tmp_path / "low")
        _, parsed_c, _, _ = _run_hook(
            repo_low, "Task", {"subagent_type": "ultron", "prompt": _MEM_NONCE}
        )
        results["low_score"] = _hook_specific(parsed_c).get("permissionDecision")

        _, parsed_d, _, _ = _run_hook(
            repo, "Task", {"subagent_type": "bilbo", "prompt": domain_prompt}
        )
        results["excluded_agent"] = _hook_specific(parsed_d).get("permissionDecision")

        deny_branches = [name for name, decision in results.items() if decision == "deny"]
        assert deny_branches == ["strong_match_no_marker"], (
            f"Exactly one branch must deny; got deny from: {deny_branches}; "
            f"full results={results}"
        )
        for name, decision in results.items():
            if name != "strong_match_no_marker":
                assert decision == "allow", f"Branch {name!r} must be allow; got {decision!r}"


# ══════════════════════════════════════════════════════════════════════════
# NEW COVERAGE: multi-skill selection contract
# ══════════════════════════════════════════════════════════════════════════
#
# The gate no longer injects only the single top result. _find_gate_skills()
# now selects ALL results scoring >= _SKILL_CONFIDENT; if none clear that
# bar, it falls back to the single top result if its score >=
# _SKILL_SCORE_THRESHOLD; the resulting set is sorted by score descending
# and capped to _SKILL_MAX. _build_skill_gate_message() switches the deny
# header to plural whenever more than one block is selected. Every case
# below runs the REAL skill-search.py subprocess against real,
# filesystem-discovered fixture skills (§34.5 — no mocked searcher); no
# score/name/path is hand-typed anywhere — every assertion re-derives its
# expected value from a direct real invocation of the same producer
# (_real_skill_search_top / _real_skill_search_results). Anti-loop (marker
# present → allow) and fail-open (searcher broken → allow, never deny) are
# NOT re-tested here: the marker check and the failure branches both run
# BEFORE selection, so they are single, shared code paths already covered
# by TestSkillGateMarkerAntiLoop and TestSkillGateSearcherFailsOpen above,
# regardless of how many skills would otherwise have been selected —
# re-testing them per skill-count would just re-exercise the same branch.

# ── (7) Two independently-confident matches → 2 blocks, plural header ─────

class TestSkillGateMultiSkillConfidentDenies:
    def test_two_confident_matches_deny_with_two_blocks_plural_header(self, tmp_path):
        """Two domain skills that BOTH independently clear _SKILL_CONFIDENT
        for the same prompt → deny with one [DOMAIN SKILL — block per skill,
        highest score first, and the PLURAL header/footer wording."""
        repo = _make_repo(tmp_path)
        trigger_a, trigger_b = "zzzqrxAAA111multiskill", "zzzqrxBBB222multiskill"
        name_a, name_b = "unmassk-test-multi-skill-a", "unmassk-test-multi-skill-b"
        _write_gate_skill_fixture(repo, skill_name=name_a, trigger=trigger_a, reps=1)
        _write_gate_skill_fixture(repo, skill_name=name_b, trigger=trigger_b, reps=2)
        prompt = f"implement the {trigger_a} {trigger_b} feature end to end"

        results = _real_skill_search_results(repo, prompt)
        confident = [r for r in results if r["score"] >= SKILL_CONFIDENT]
        confident_names = {r["name"] for r in confident}
        assert {name_a, name_b} <= confident_names, (
            f"Test prerequisite: both fixtures must clear _SKILL_CONFIDENT; got {results}"
        )
        assert len(confident) == 2, (
            f"Test prerequisite: exactly these two fixtures must be confident for this "
            f"prompt (no accidental host-corpus overlap); got confident={confident}"
        )
        by_name = {r["name"]: r for r in results}
        expected_order = sorted(
            [by_name[name_a], by_name[name_b]], key=lambda r: r["score"], reverse=True
        )

        tool_input = {"subagent_type": "ultron", "prompt": prompt}
        rc, parsed, _, stderr = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "deny"
        assert "updatedInput" not in hso, "A deny must never carry updatedInput"

        reason = hso.get("permissionDecisionReason", "")
        assert reason.count(SKILL_MARKER) == 2, "Two confident skills must produce exactly two blocks"
        assert "los siguientes bloques" in reason, "Two blocks must use the PLURAL header"
        assert "estos bloques delante" in reason, "Two blocks must use the PLURAL footer wording"
        assert "el siguiente bloque" not in reason, "Plural deny must NOT contain the singular header"

        for r in expected_order:
            assert f"Skill: {r['name']} (score {r['score']:.1f})" in reason, (
                "Injected name/score must match the REAL searcher's output verbatim (§34)"
            )
            assert f"Path: {r['skill_md']}" in reason

        first_idx = reason.find(f"Skill: {expected_order[0]['name']}")
        second_idx = reason.find(f"Skill: {expected_order[1]['name']}")
        assert first_idx != -1 and second_idx != -1 and first_idx < second_idx, (
            "Blocks must be ordered highest score first"
        )

        assert "skill gate: deny 2 skills" in stderr, "Deny branch must leave a stderr breadcrumb"


# ── (8) No skill reaches _SKILL_CONFIDENT, top clears the low bar → 1 block ─

class TestSkillGateFallbackTopOnlyOneBlock:
    def test_no_confident_match_but_top_clears_threshold_denies_one_block(self, tmp_path):
        """No result clears _SKILL_CONFIDENT, but the top result clears
        _SKILL_SCORE_THRESHOLD → the fallback-to-top-only branch fires:
        exactly ONE block, singular header. This is the genuinely different
        code path from TestSkillGateDomainMatchDenies (that test's fixture
        already clears _SKILL_CONFIDENT outright — the `confident` branch,
        not this `else: top` fallback)."""
        repo = _make_repo(tmp_path)
        _write_diluted_gate_skill_fixture(repo)
        prompt = _FALLBACK_TRIGGER

        results = _real_skill_search_results(repo, prompt)
        assert results, f"Test prerequisite: at least one result expected; got {results}"
        top = results[0]
        assert top["name"] == _FALLBACK_FIXTURE_SKILL_NAME, (
            f"Test prerequisite: fixture must be the top real result; got {top}"
        )
        assert SKILL_SCORE_THRESHOLD <= top["score"] < SKILL_CONFIDENT, (
            f"Test prerequisite: top score must sit in the fallback band "
            f"[{SKILL_SCORE_THRESHOLD}, {SKILL_CONFIDENT}); got {top['score']}"
        )
        assert all(r["score"] < SKILL_CONFIDENT for r in results), (
            f"Test prerequisite: NO result may clear _SKILL_CONFIDENT for this prompt "
            f"(the fallback branch only fires when the confident set is empty); got {results}"
        )

        tool_input = {"subagent_type": "ultron", "prompt": prompt}
        rc, parsed, _, stderr = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "deny"

        reason = hso.get("permissionDecisionReason", "")
        assert reason.count(SKILL_MARKER) == 1, "Fallback branch must select exactly the top result"
        assert "el siguiente bloque" in reason, "Single-block fallback deny must use the singular header"
        assert "los siguientes bloques" not in reason
        assert f"Skill: {top['name']} (score {top['score']:.1f})" in reason, (
            "Injected name/score must match the REAL searcher's output verbatim (§34)"
        )
        assert f"Path: {top['skill_md']}" in reason

        assert "skill gate: deny 1 skills" in stderr, "Deny branch must leave a stderr breadcrumb"


# ── (9) More than _SKILL_MAX confident matches → capped to the top _SKILL_MAX ─

class TestSkillGateCapAtThree:
    def test_four_confident_matches_caps_to_highest_scoring_max(self, tmp_path):
        """Four independently-confident domain skills for the same prompt →
        the deny must list only _SKILL_MAX (3) blocks: the highest-scoring
        ones. The lowest-scoring confident skill must be excluded entirely,
        not just re-ordered."""
        repo = _make_repo(tmp_path)
        specs = [
            ("unmassk-test-cap-a", "zzzqrxCAPAAA111", 1),
            ("unmassk-test-cap-b", "zzzqrxCAPBBB222", 2),
            ("unmassk-test-cap-c", "zzzqrxCAPCCC333", 3),
            ("unmassk-test-cap-d", "zzzqrxCAPDDD444", 4),
        ]
        for name, trigger, reps in specs:
            _write_gate_skill_fixture(repo, skill_name=name, trigger=trigger, reps=reps)
        prompt = "implement the " + " ".join(t for _, t, _ in specs) + " feature end to end"

        results = _real_skill_search_results(repo, prompt)
        confident = [r for r in results if r["score"] >= SKILL_CONFIDENT]
        confident_names = {r["name"] for r in confident}
        expected_names = {name for name, _, _ in specs}
        assert expected_names <= confident_names, (
            f"Test prerequisite: all four fixtures must clear _SKILL_CONFIDENT; got {results}"
        )
        assert len(confident) >= 4, (
            f"Test prerequisite: at least 4 confident results are needed to exercise the "
            f"cap; got confident={confident}"
        )
        ranked = sorted(confident, key=lambda r: r["score"], reverse=True)
        top_max = ranked[:SKILL_MAX]
        excluded = ranked[SKILL_MAX:]

        tool_input = {"subagent_type": "ultron", "prompt": prompt}
        rc, parsed, _, stderr = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "deny"

        reason = hso.get("permissionDecisionReason", "")
        assert reason.count(SKILL_MARKER) == SKILL_MAX, (
            f"Must cap to exactly _SKILL_MAX ({SKILL_MAX}) blocks even with "
            f"{len(confident)} confident matches"
        )
        assert "los siguientes bloques" in reason, "A capped multi-block deny must use the PLURAL header"

        for r in top_max:
            assert f"Skill: {r['name']} (score {r['score']:.1f})" in reason, (
                "Every retained top-scoring skill must appear verbatim (§34)"
            )
        for r in excluded:
            assert f"Skill: {r['name']} (score {r['score']:.1f})" not in reason, (
                f"Excluded lower-scoring skill {r['name']!r} must NOT appear in a capped deny"
            )

        indices = [reason.find(f"Skill: {r['name']}") for r in top_max]
        assert all(i != -1 for i in indices), "Every retained skill must be found in the reason"
        assert indices == sorted(indices), "Capped blocks must be ordered highest score first"

        assert f"skill gate: deny {SKILL_MAX} skills" in stderr, (
            "Deny branch must leave a stderr breadcrumb naming the actual selected count"
        )
