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
import re
import subprocess
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_script, run_cmd

# Make lib/ importable for direct recall() calls in test helpers.
LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

HOOK_PATH = os.path.join(HOOKS_DIR, "pre-task-recall.py")


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
            "Decision: usar BM25 para ranking de memoria en recall",
        )

        prompt = "implement BM25 ranking for recall"
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
        assert "BM25" in updated_prompt, "Memory block content must appear in prompt"
        # The memory block delimiters must be present
        assert "---" in updated_prompt

    def test_all_other_tool_input_fields_preserved(self, tmp_path):
        """tool_input fields other than prompt must be copied intact."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): BM25 design",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "ultron",
            "description": "implement something",
            "prompt": "implement BM25 recall ranking",
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para memoria recall",
        )

        tool_input = {
            "subagent_type": "ultron",
            "prompt": "BM25 recall ranking implementation",
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
            "prompt": "github actions workflow setup",
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
            "prompt": "BM25 recall ranking implementation",
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "unmassk-toolkit:ultron",
            "prompt": "BM25 recall ranking",
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "ultron",
            "prompt": "BM25 recall ranking",
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "ULTRON",
            "prompt": "BM25 recall ranking",
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": agent,
            "prompt": "BM25 recall ranking",
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "ultron",
            "prompt": "BM25 recall ranking implementation",
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "dante",
            "prompt": "BM25 recall ranking tests",
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        original_prompt = "BM25 recall ranking implementation"
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        prompt = "BM25 recall ranking"
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: usar BM25 para ranking de memoria recall xyzstructure",
        )
        _commit(
            repo,
            "memo(plugin/recall): recall preference",
            "Memo: preference - xyzstructure es la preferencia de ranking",
        )

        prompt = "BM25 recall ranking xyzstructure"
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para memoria recall",
        )

        tool_input = {"subagent_type": "cerberus", "prompt": "BM25 recall ranking"}

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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "unmassk-toolkit:Ultron",
            "prompt": "BM25 recall ranking",
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "  ultron  ",
            "prompt": "BM25 recall ranking",
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "Dante",
            "prompt": "BM25 recall ranking",
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
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )
        payload = json.dumps({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "ultron", "prompt": "BM25 recall ranking"},
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
        padding_unit = "implement the xqzlongprompttoken feature with full coverage "
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
# EXPANSION (test-first / contract pass): domain-skill auto-injection
# ══════════════════════════════════════════════════════════════════════════
#
# Written BEFORE Ultron implements the feature. Pins the 7 acceptance
# behaviours (a)-(g) from the task, plus a silent-failure stderr guard. Every
# test below MUST currently fail (RED) because pre-task-recall.py does not
# invoke skill-search.py at all yet -- see MEMORY.md's note on why a handful
# of the (g) invariant tests are legitimately allowed to already pass (they
# pin a property that is vacuously true before the feature exists; the
# strong-match variant is strengthened to also assert the missing block, so
# it is RED like the rest).
#
# Contract (from the task):
#   - Real subprocess: `python3 unmassk-toolkit/scripts/skill-search.py
#     "<prompt>" --json`.
#   - Strong match => inject a SEPARATE, non-nested block:
#       [DOMAIN SKILL — auto-selected for this task.]
#       Skill: <name> (score <N>)
#       Path: <skill_md>
#       ACTION: Read this SKILL.md now; it may point to scripts/references
#       you must use.
#   - Skill search is INDEPENDENT of the `if not memory_block: passthrough`
#     early-return at ~line 177 -- (skill yes / memory no) is the critical
#     regression this expansion exists to prevent.
#   - Fail-open on searcher timeout / malformed JSON: allow, no skill block,
#     no crash.
#   - Excluded agents (bilbo / gitto / unknown) -> no skill block, same
#     exclusion set as memory recall today.
#   - INVARIANT: never deny/block, ever -- across every branch above.
#   - Stderr breadcrumb on every outcome branch (T1 silent-failure guard).
#
# Real-by-default (§34.5): the match / no-match / independence cases run the
# REAL skill-search.py subprocess against a REAL, disposable fixture skill --
# a `.skillcat` + colocated `SKILL.md` written INSIDE the temp repo itself.
# skill-search.py's own find_git_root() walks up from cwd to the nearest
# `.git` and adds that root to its search dirs (rglob for `*.skillcat`), so
# placing the fixture anywhere under the temp repo makes it discoverable
# regardless of whatever real skills happen to be installed on the host
# running these tests -- verified empirically (see agent-memory) that a
# nonce trigger term repeated in the fixture's `triggers` column scores 6.6
# (fixture rank #1) against the REAL installed corpus on this machine, and
# that two unrelated nonce words with no fixture-independent English content
# score exactly 0 against that same real corpus. Every score comparison
# below is against a value read from a DIRECT, real invocation of
# skill-search.py against the SAME repo/prompt (the real producer) -- never
# hand-typed (§34).
#
# Only the two failure modes that genuinely cannot be produced on demand by
# the real searcher (subprocess timeout, malformed JSON) are simulated, and
# only there -- via an in-process import of the hook module (this repo's
# established importlib.util.spec_from_file_location pattern for hyphenated
# filenames, see unmassk-toolkit-python-test-conventions) with
# `subprocess.run` monkeypatched so ONLY a call whose command line mentions
# "skill-search" is faked; every other subprocess.run call (e.g. git, inside
# recall()) passes through to the real implementation untouched -- this
# prevents a false-pass where an unrelated exception (not the simulated
# failure) is what actually produced the fail-open result.


# ── Constants pinned by the task's exact contract text ────────────────────

# Copied verbatim from the task, including the em dash (U+2014), so a future
# formatting drift is caught precisely rather than approximately.
SKILL_BLOCK_HEADER = "[DOMAIN SKILL — auto-selected for this task.]"
SKILL_BLOCK_ACTION_LINE = (
    "ACTION: Read this SKILL.md now; it may point to scripts/references you must use."
)

_SKILL_SEARCH_SCRIPT = os.path.join(SOURCE_ROOT, "scripts", "skill-search.py")

# Import LOW_SCORE_THRESHOLD from the real module rather than hardcoding
# "1.5" (Hard Rules: No Hardcoded Values) -- hyphenated filename, so this
# repo's importlib.util.spec_from_file_location convention is used.
_skill_search_spec = importlib.util.spec_from_file_location(
    "skill_search_module_for_pre_task_recall_tests", _SKILL_SEARCH_SCRIPT
)
_skill_search_mod = importlib.util.module_from_spec(_skill_search_spec)
_skill_search_spec.loader.exec_module(_skill_search_mod)
LOW_SCORE_THRESHOLD = _skill_search_mod.LOW_SCORE_THRESHOLD

# Nonce vocabulary -- deliberately not real English words, so scores against
# the fixture / real corpus are unambiguous and verified empirically (see
# module docstring above) rather than assumed.
_NONCE_TRIGGER = "zzzqrxvnonceskilltriggerunmasskdante99182"
_FIXTURE_SKILL_NAME = "unmassk-test-nonce-domain-skill"
_NO_MATCH_PROMPT = "xyzzyplughqwerty zzznoncewordfoo"
_MEMORY_LINK_TOKEN = "qzvmemorylinktoken4471"


# ── Fixture / helper: real, disposable domain skill ───────────────────────

def _write_skill_fixture(repo, skill_name=_FIXTURE_SKILL_NAME, trigger=_NONCE_TRIGGER):
    """Write a real .skillcat + colocated SKILL.md INSIDE the temp repo.

    Discovered by the real skill-search.py via its own find_git_root() ->
    rglob("*.skillcat") over the repo root, regardless of the real skills
    installed on the host running these tests. Not git-tracked -- skill
    discovery walks the filesystem, not git state.
    """
    skill_dir = os.path.join(repo, "fixture_skills", skill_name)
    os.makedirs(skill_dir, exist_ok=True)

    skillcat_path = os.path.join(skill_dir, f"{skill_name}.skillcat")
    with open(skillcat_path, "w", encoding="utf-8", newline="") as f:
        f.write("name,plugin,triggers,domains,frameworks,tools\n")
        f.write(
            '{},{},"{} {} domain trigger fixture","{} domain",none,none\n'.format(
                skill_name, "unmassk-test-plugin", trigger, trigger, trigger
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


def _real_skill_search_json(repo, prompt):
    """Run the REAL skill-search.py as a subprocess against `repo` (so its
    own find_git_root() resolves to `repo`) and return the parsed --json
    output. Ground-truth producer for every score/path assertion below --
    never hand-typed (unmassk-standards §34)."""
    rc, stdout, stderr = run_script(
        _SKILL_SEARCH_SCRIPT, repo, extra_args=[prompt, "--json"]
    )
    assert rc == 0, f"skill-search.py must exit 0; stderr={stderr!r}"
    return json.loads(stdout)


def _memory_footer_span(prompt):
    """Return (start, end) spanning the memory footer's own '---' delimiter
    pair, or None if no '[PROJECT MEMORY' marker is present. The skill block
    template (SKILL_BLOCK_HEADER/lines above) never contains '---', so the
    LAST '---' in the whole prompt is safely the memory footer's own closing
    tail regardless of block ordering."""
    pm_idx = prompt.find("[PROJECT MEMORY")
    if pm_idx == -1:
        return None
    open_dash = prompt.rfind("---", 0, pm_idx)
    close_dash = prompt.rfind("---")
    if open_dash == -1 or close_dash == -1:
        return None
    return open_dash, close_dash + 3


def _assert_skill_block_not_nested_in_memory(prompt):
    """Implementation-agnostic 'own channel, never nested' check: the skill
    block header must not fall inside the memory footer's own '---' span."""
    footer_span = _memory_footer_span(prompt)
    skill_idx = prompt.find(SKILL_BLOCK_HEADER)
    if footer_span is None or skill_idx == -1:
        return
    start, end = footer_span
    assert not (start <= skill_idx < end), (
        f"Skill block must be its own channel, not nested inside the "
        f"[PROJECT MEMORY] footer; skill block at {skill_idx}, memory "
        f"footer spans [{start}, {end})"
    )


def _extract_skill_block_score(prompt, skill_name):
    match = re.search(
        r"Skill:\s*{}\s*\(score\s*([\d.]+)\)".format(re.escape(skill_name)),
        prompt,
    )
    assert match, f"Expected 'Skill: {skill_name} (score N)' line; prompt={prompt!r}"
    return float(match.group(1))


# ── Helper: in-process fail-open simulation (timeout / malformed JSON) ────

def _fake_timeout(cmd, kwargs):
    raise subprocess.TimeoutExpired(cmd=cmd, timeout=6)


def _fake_malformed_json(cmd, kwargs):
    return subprocess.CompletedProcess(
        args=cmd, returncode=0, stdout="NOT VALID JSON {{{", stderr=""
    )


def _run_hook_inprocess_with_faked_searcher(monkeypatch, repo, tool_input, fake_run):
    """Load pre-task-recall.py fresh, in-process, with subprocess.run
    monkeypatched so ONLY a call whose command line mentions "skill-search"
    is faked -- any other subprocess.run call (e.g. git, inside recall())
    passes through to the real implementation untouched, so a false-pass
    from an unrelated exception cannot masquerade as the simulated failure.

    monkeypatch.chdir(repo) makes recall()'s cwd-relative run_git() calls
    (it takes no explicit cwd param -- see unmassk-toolkit-python-test-
    conventions) resolve against the disposable temp repo, not this
    process's real cwd.

    Returns (stdout_text, stderr_text) -- the hook emits JSON on stdout.
    """
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


# ── (a) Strong skill match -> block injected, real searcher end-to-end ────

class TestStrongSkillMatchInjectsBlock:
    """(a) Domain task with a STRONG skill match (real searcher, real
    fixture, top score >= LOW_SCORE_THRESHOLD) -> the skill block is
    injected with its own header, name, real skill_md path, ACTION line."""

    def test_strong_match_injects_skill_block_end_to_end(self, tmp_path):
        repo = _make_repo(tmp_path)
        _write_skill_fixture(repo)

        prompt = f"implement the {_NONCE_TRIGGER} feature end to end"

        expected = _real_skill_search_json(repo, prompt)
        assert expected["results"], "Fixture must produce at least one result"
        top = expected["results"][0]
        assert top["name"] == _FIXTURE_SKILL_NAME
        assert top["score"] >= LOW_SCORE_THRESHOLD, (
            f"Test precondition: fixture must score >= {LOW_SCORE_THRESHOLD}; "
            f"got {top['score']}"
        )

        tool_input = {"subagent_type": "ultron", "prompt": prompt}
        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" in hso, "Expected skill injection to trigger updatedInput"

        updated_prompt = hso["updatedInput"]["prompt"]
        assert SKILL_BLOCK_HEADER in updated_prompt
        assert f"Skill: {_FIXTURE_SKILL_NAME}" in updated_prompt
        assert f"Path: {top['skill_md']}" in updated_prompt, (
            "Injected path must be the REAL skill_md path the searcher produced"
        )
        assert SKILL_BLOCK_ACTION_LINE in updated_prompt

        actual_score = _extract_skill_block_score(updated_prompt, _FIXTURE_SKILL_NAME)
        assert abs(actual_score - top["score"]) < 0.05, (
            f"Injected score {actual_score} must match the real searcher's "
            f"score {top['score']} (§34: never hand-typed, always derived "
            f"from the real producer)"
        )


# ── (b) No skill match -> memory recall unaffected ─────────────────────────

class TestNoSkillMatchMemoryStillFlows:
    """(b) No skill match (score < LOW_SCORE_THRESHOLD) -> no skill block
    injected, but the EXISTING memory-recall behaviour is unaffected. Also
    the (skill no / memory yes) combination named in (c)'s 4-combo matrix --
    not duplicated in TestSkillMemoryIndependenceRegression, see that
    class's docstring."""

    def test_low_score_skill_no_block_memory_injection_unchanged(self, tmp_path):
        repo = _make_repo(tmp_path)
        _write_skill_fixture(repo)
        _commit(
            repo,
            "decision(plugin/recall): unrelated preference",
            "Decision: preferencia xyzzyplughqwerty zzznoncewordfoo del proyecto",
        )
        prompt = _NO_MATCH_PROMPT

        expected = _real_skill_search_json(repo, prompt)
        top = expected["results"][0]
        assert top["score"] < LOW_SCORE_THRESHOLD, (
            f"Test precondition: prompt must NOT strongly match any skill "
            f"(fixture or real corpus); got score {top['score']} for {top['name']!r}"
        )

        tool_input = {"subagent_type": "ultron", "prompt": prompt}
        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert "updatedInput" in hso, "Memory match must still inject as before"
        updated_prompt = hso["updatedInput"]["prompt"]
        assert "PROJECT MEMORY" in updated_prompt
        assert SKILL_BLOCK_HEADER not in updated_prompt, (
            "Low-confidence skill score must not produce a skill block"
        )


# ── (c) CRITICAL regression: skill search independent of memory ───────────

class TestSkillMemoryIndependenceRegression:
    """(c) CRITICAL regression: skill search must be INDEPENDENT of the
    existing `if not memory_block: passthrough` early-return at ~line 177.
    Covers 3 of the task's 4 named combinations; the 4th (skill no / memory
    yes) is TestNoSkillMatchMemoryStillFlows above -- same scenario, not
    duplicated here.
    """

    def test_skill_yes_memory_no_still_injects_skill_block(self, tmp_path):
        """THE regression this task exists to prevent: today's
        `if not memory_block: _allow_passthrough(); return` would kill
        skill injection entirely whenever there is no memory match. Skill
        search must run and inject independently of that early-return."""
        repo = _make_repo(tmp_path)  # no memory commits at all
        _write_skill_fixture(repo)
        prompt = f"implement the {_NONCE_TRIGGER} feature end to end"

        expected = _real_skill_search_json(repo, prompt)
        top = expected["results"][0]
        assert top["score"] >= LOW_SCORE_THRESHOLD

        tool_input = {"subagent_type": "ultron", "prompt": prompt}
        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert "updatedInput" in hso, (
            "Skill match must inject even when memory_block is empty -- this "
            "is exactly the regression the early-return at ~line 177 would "
            "otherwise cause"
        )
        updated_prompt = hso["updatedInput"]["prompt"]
        assert SKILL_BLOCK_HEADER in updated_prompt
        assert "PROJECT MEMORY" not in updated_prompt, (
            "No memory match was seeded -- only the skill block should appear"
        )

    def test_both_match_inject_both_blocks_not_nested(self, tmp_path):
        repo = _make_repo(tmp_path)
        _write_skill_fixture(repo)
        _commit(
            repo,
            "decision(plugin/recall): fixture combo",
            f"Decision: usar {_MEMORY_LINK_TOKEN} para el enfoque de {_NONCE_TRIGGER}",
        )
        prompt = f"implement the {_NONCE_TRIGGER} feature using {_MEMORY_LINK_TOKEN} approach"

        tool_input = {"subagent_type": "ultron", "prompt": prompt}
        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert "updatedInput" in hso
        updated_prompt = hso["updatedInput"]["prompt"]

        assert "PROJECT MEMORY" in updated_prompt, "Memory block must still be present"
        assert SKILL_BLOCK_HEADER in updated_prompt, "Skill block must also be present"
        _assert_skill_block_not_nested_in_memory(updated_prompt)

    def test_neither_match_clean_passthrough(self, tmp_path):
        repo = _make_repo(tmp_path)  # no memory commits
        _write_skill_fixture(repo)
        prompt = _NO_MATCH_PROMPT  # score 0 vs both the fixture and real corpus

        tool_input = {"subagent_type": "ultron", "prompt": prompt}
        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso, (
            "Neither signal matched -- must be a clean passthrough"
        )


# ── (d) Searcher timeout -> fail-open ──────────────────────────────────────

class TestSearcherTimeoutFailOpen:
    """(d) Searcher subprocess TIMEOUT (~5-6s budget inside the hook's 10s)
    -> fail-open: Task allowed unchanged, no skill block, hook does not
    crash. Simulated in-process (see helper docstring above) -- a real
    multi-second sleep is not an option (Hard Rules: no timing-dependent
    tests)."""

    def test_timeout_allows_task_no_skill_block_no_crash(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)  # no memory commits -> deterministic bare passthrough
        prompt = f"implement the {_NONCE_TRIGGER} feature"
        tool_input = {"subagent_type": "ultron", "prompt": prompt}

        stdout_text, _stderr_text = _run_hook_inprocess_with_faked_searcher(
            monkeypatch, repo, tool_input, _fake_timeout
        )

        parsed = json.loads(stdout_text)
        hso = parsed.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "allow"
        assert SKILL_BLOCK_HEADER not in stdout_text
        assert "updatedInput" not in hso, (
            "No memory match was seeded -- searcher timeout must fail open "
            "to a clean passthrough, not crash or deny"
        )


# ── (e) Searcher malformed JSON -> fail-open ───────────────────────────────

class TestSearcherMalformedJsonFailOpen:
    """(e) Searcher returns MALFORMED JSON -> fail-open: Task allowed, no
    skill block, no crash. Simulated in-process -- skill-search.py always
    emits valid JSON on success, so this cannot be produced on demand by
    the real script."""

    def test_malformed_json_allows_task_no_skill_block_no_crash(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        prompt = f"implement the {_NONCE_TRIGGER} feature"
        tool_input = {"subagent_type": "ultron", "prompt": prompt}

        stdout_text, _stderr_text = _run_hook_inprocess_with_faked_searcher(
            monkeypatch, repo, tool_input, _fake_malformed_json
        )

        parsed = json.loads(stdout_text)
        hso = parsed.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "allow"
        assert SKILL_BLOCK_HEADER not in stdout_text
        assert "updatedInput" not in hso


# ── (f) Excluded agents -> no skill block, even with a strong match ───────

class TestExcludedAgentsSkipSkillInjection:
    """(f) bilbo / gitto / any unknown agent -> passthrough untouched, even
    when the prompt would strongly match BOTH the fixture skill AND memory.
    Same exclusion set as recall's existing whitelist (ultron, dante,
    cerberus, argus, moriarty, house, yoda, alexandria)."""

    @pytest.mark.parametrize("agent", ["bilbo", "gitto", "unknown-agent-xyz"])
    def test_excluded_agent_gets_no_skill_block_even_with_strong_match(self, agent, tmp_path):
        repo = _make_repo(tmp_path)
        _write_skill_fixture(repo)
        _commit(
            repo,
            "decision(plugin/recall): fixture combo",
            f"Decision: usar {_MEMORY_LINK_TOKEN} para el enfoque de {_NONCE_TRIGGER}",
        )
        prompt = f"implement the {_NONCE_TRIGGER} feature using {_MEMORY_LINK_TOKEN} approach"
        tool_input = {"subagent_type": agent, "prompt": prompt}

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso, (
            f"Excluded agent {agent!r} must receive neither skill nor memory injection"
        )


# ── (g) INVARIANT: never deny/block, across every branch above ────────────

class TestNeverDeniesInvariantWithSkillSearch:
    """(g) INVARIANT — the hook NEVER returns a deny/block for a Task in ANY
    case; every path is an allow. Asserted across every branch the skill-
    search expansion adds. The strong-match variant additionally asserts the
    skill block is present, so it is RED like the rest of this file today;
    the other variants pin a property that is legitimately already true
    before the branch exists (there is no way to fail open on a branch that
    doesn't exist yet) and remain valid regression nets once it does."""

    def _assert_never_deny(self, stdout_text):
        parsed = json.loads(stdout_text)
        decision = parsed.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision not in ("deny", "block"), (
            f"permissionDecision must never be 'deny'/'block'; got {decision!r}"
        )
        assert decision == "allow"

    def test_invariant_strong_skill_match(self, tmp_path):
        repo = _make_repo(tmp_path)
        _write_skill_fixture(repo)
        prompt = f"implement the {_NONCE_TRIGGER} feature end to end"
        payload = json.dumps({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "ultron", "prompt": prompt},
        })
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=payload)
        assert rc == 0
        self._assert_never_deny(stdout)
        assert SKILL_BLOCK_HEADER in stdout, (
            "Strong match branch must both inject AND never deny"
        )

    def test_invariant_low_score_skill(self, tmp_path):
        repo = _make_repo(tmp_path)
        _write_skill_fixture(repo)
        payload = json.dumps({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "ultron", "prompt": _NO_MATCH_PROMPT},
        })
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=payload)
        assert rc == 0
        self._assert_never_deny(stdout)

    def test_invariant_excluded_agent_with_strong_match(self, tmp_path):
        repo = _make_repo(tmp_path)
        _write_skill_fixture(repo)
        prompt = f"implement the {_NONCE_TRIGGER} feature end to end"
        payload = json.dumps({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "bilbo", "prompt": prompt},
        })
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=payload)
        assert rc == 0
        self._assert_never_deny(stdout)

    def test_invariant_searcher_timeout(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        tool_input = {"subagent_type": "ultron", "prompt": "implement something"}
        stdout_text, _ = _run_hook_inprocess_with_faked_searcher(
            monkeypatch, repo, tool_input, _fake_timeout
        )
        self._assert_never_deny(stdout_text)

    def test_invariant_searcher_malformed_json(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        tool_input = {"subagent_type": "ultron", "prompt": "implement something"}
        stdout_text, _ = _run_hook_inprocess_with_faked_searcher(
            monkeypatch, repo, tool_input, _fake_malformed_json
        )
        self._assert_never_deny(stdout_text)


# ── Silent-failure guard (T1, unmassk-standards): stderr breadcrumb ───────

class TestSilentFailureStderrBreadcrumb:
    """Every outcome branch this expansion adds must write SOME diagnostic
    to stderr, so a future failure in the skill-search wiring is never
    invisible. None of these branches write anything today -- RED."""

    def test_stderr_breadcrumb_when_skill_injected(self, tmp_path):
        repo = _make_repo(tmp_path)
        _write_skill_fixture(repo)
        prompt = f"implement the {_NONCE_TRIGGER} feature end to end"
        tool_input = {"subagent_type": "ultron", "prompt": prompt}

        _rc, _parsed, _stdout, stderr = _run_hook(repo, "Task", tool_input)

        assert stderr.strip() != "", (
            "Expected a stderr breadcrumb on the 'skill injected' branch"
        )

    def test_stderr_breadcrumb_when_low_score_skipped(self, tmp_path):
        repo = _make_repo(tmp_path)
        _write_skill_fixture(repo)
        tool_input = {"subagent_type": "ultron", "prompt": _NO_MATCH_PROMPT}

        _rc, _parsed, _stdout, stderr = _run_hook(repo, "Task", tool_input)

        assert stderr.strip() != "", (
            "Expected a stderr breadcrumb on the 'low-score-skipped' branch"
        )

    def test_stderr_breadcrumb_when_searcher_times_out(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        tool_input = {"subagent_type": "ultron", "prompt": "implement something"}

        _stdout_text, stderr_text = _run_hook_inprocess_with_faked_searcher(
            monkeypatch, repo, tool_input, _fake_timeout
        )

        assert stderr_text.strip() != "", (
            "Expected a stderr breadcrumb on the 'searcher-failed' (timeout) branch"
        )

    def test_stderr_breadcrumb_when_searcher_returns_malformed_json(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        tool_input = {"subagent_type": "ultron", "prompt": "implement something"}

        _stdout_text, stderr_text = _run_hook_inprocess_with_faked_searcher(
            monkeypatch, repo, tool_input, _fake_malformed_json
        )

        assert stderr_text.strip() != "", (
            "Expected a stderr breadcrumb on the 'searcher-failed' "
            "(malformed JSON) branch"
        )
