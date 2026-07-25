"""
Tests for pre-task-recall.py — the git-memory recall injection hook.

Covers:
- Task with whitelisted agent (ultron) + memory match → prompt is injected,
  all other tool_input fields are preserved.
- Task with non-whitelisted agent (gitto, unknown) → passthrough, no updatedInput.
- tool_name other than Task → passthrough.
- recall returns no matches → passthrough.
- Malformed JSON on stdin → fail-open (allow, exit 0).
- subagent_type with namespace prefix ('unmassk-toolkit:ultron') → recognised.
- subagent_type without prefix ('ultron') → recognised.
- Prompt field absent or empty → passthrough.

The hook is invoked as a subprocess with JSON passed via stdin, mirroring
the pattern used by run_script() in conftest.

--- TEST-FIRST contract (dead-end memory loop, RED before Ultron) ---
Bilbo joins the memory-injection whitelist (was previously excluded, same
category as gitto). gitto stays excluded — this is a scoped addition, not a
whitelist-model change. Every test below that previously asserted "bilbo is
excluded" was rewritten to assert "bilbo is whitelisted" (see
TestBilboWhitelistedForInjection, TestSubagentTypeCasingAndNamespace) so the
whole file stays internally consistent with the new contract — the old
assertions would otherwise start failing the moment _WORKER_WHITELIST
changes, for a reason unrelated to whatever a future test author is working
on. gitto-exclusion coverage was preserved (moved into the mixed-case/
namespace test that used to use bilbo for that purpose) rather than deleted.

RED contract (must fail today — bilbo still excluded in _WORKER_WHITELIST):
    - TestBilboWhitelistedForInjection::test_bilbo_receives_injection
    - TestSubagentTypeCasingAndNamespace::test_namespaced_bilbo_now_whitelisted
    - TestAllWhitelistedAgents::test_whitelisted_agent_receives_injection[bilbo]

GREEN control (must pass before AND after — gitto stays excluded):
    - TestNonWhitelistedAgent::test_gitto_not_injected
    - TestSubagentTypeCasingAndNamespace::test_namespaced_mixed_case_gitto_stays_excluded
"""

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

# ── Nonce vocabulary (now vestigial, kept inert) ──────────────────────────
# Originally chosen (issue #68) so plain English test phrases like "BM25
# recall ranking" would not score above the skill-search gate's threshold
# against the real domain-skill corpus and wrongly DENY instead of falling
# through to the memory path these tests exercise. That skill gate has since
# been removed from pre-task-recall.py entirely (see the retired
# TestSkillGate* classes this file used to carry) — the collision these
# nonces guarded against can no longer happen. Left in place as ordinary
# shared vocabulary between seeded commit trailers and prompts (recall()'s
# own BM25 index over git commit messages still needs token overlap to
# produce a match, which nonce text satisfies exactly as well as real
# words would) rather than rewritten across the ~15 call sites that use
# them, per Yoda/Bex's explicit "leave inert, flag it" allowance.
_MEM_NONCE = "zqxvbnkplfth wjrqztkvnmg"

# For tests whose intent is "no memory match at all" — a nonce disjoint from
# _MEM_NONCE so it never accidentally overlaps a commit seeded elsewhere in
# the same test.
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


# ── Tests: bilbo is now whitelisted for injection ─────────────────────────

class TestBilboWhitelistedForInjection:
    """bilbo joins the memory-injection whitelist (dead-end memory loop feature).

    RED today: bilbo is still in the excluded set (_WORKER_WHITELIST does not
    contain 'bilbo' yet), so this currently produces passthrough (no
    updatedInput) instead of injection.
    """

    def test_bilbo_receives_injection(self, tmp_path):
        """Task(bilbo) + memory match → hookSpecificOutput.updatedInput.prompt
        contains the original prompt AND the memory block footer, exactly like
        any other whitelisted worker."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): ranking algorithm",
            f"Decision: usar {_MEM_NONCE} como estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": "bilbo",
            "prompt": _MEM_NONCE,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" in hso, "bilbo must now receive memory injection"

        updated_prompt = hso["updatedInput"]["prompt"]
        assert _MEM_NONCE in updated_prompt, "Memory block content must appear in prompt"
        assert "PROJECT MEMORY" in updated_prompt, "Footer header must be present"


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

    def test_namespaced_bilbo_now_whitelisted(self, tmp_path):
        """'unmassk-toolkit:bilbo' → bilbo is whitelisted after normalisation.

        RED today: bilbo is not yet in _WORKER_WHITELIST (dead-end memory
        loop feature, TEST-FIRST contract) — this currently produces
        passthrough instead of injection.
        """
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): nonce ranking",
            f"Decision: {_MEM_NONCE} para estrategia interna de memoria",
        )

        tool_input = {
            "subagent_type": "unmassk-toolkit:bilbo",
            "prompt": _MEM_NONCE,
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" in hso, (
            "'unmassk-toolkit:bilbo' must normalise to 'bilbo' and be whitelisted"
        )

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
        "moriarty", "house", "yoda", "alexandria", "bilbo",
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

    def test_namespaced_mixed_case_gitto_stays_excluded(self, tmp_path):
        """'TOOLKIT:Gitto' normalises to 'gitto' which is still not in the whitelist.

        Previously this test used 'TOOLKIT:Bilbo' to exercise "mixed-case +
        namespace + excluded agent" — bilbo is no longer excluded (dead-end
        memory loop feature), so this switched to gitto (still excluded,
        untouched by this change) to keep covering the same normalisation +
        exclusion combo without losing coverage.
        """
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): BM25 ranking",
            "Decision: BM25 ranking para recall de memoria",
        )

        tool_input = {
            "subagent_type": "TOOLKIT:Gitto",
            "prompt": "BM25 recall ranking",
        }

        rc, parsed, _, _ = _run_hook(repo, "Task", tool_input)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert "updatedInput" not in hso, (
            "'TOOLKIT:Gitto' → 'gitto' must still be excluded"
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
        """Passthrough for excluded agent must not emit deny or block.

        Uses gitto (still excluded, untouched by the bilbo-whitelisting
        change) rather than bilbo, which is now whitelisted.
        """
        from conftest import run_cmd
        repo = _make_repo(tmp_path)
        payload = json.dumps({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "gitto", "prompt": "BM25 recall ranking"},
        })
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=payload)
        assert rc == 0
        self._assert_no_deny_or_block(stdout, "non-whitelisted agent gitto")

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
