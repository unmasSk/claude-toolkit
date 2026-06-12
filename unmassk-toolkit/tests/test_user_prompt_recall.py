"""
Tests for recall injection in user-prompt-memory-check.py (UserPromptSubmit hook).

This is the test-first CONTRACT written before Ultron implements the injection logic.
All tests that exercise the new recall injection path must FAIL until the hook
reads stdin JSON, calls recall_relevant(), and prepends the block to its output.

Tests that exercise existing fail-safe behaviour (the hook ignoring bad/absent stdin
without crashing) may already PASS today because the current hook does not read stdin
at all.  Those tests are labelled "INVARIANT" in their docstring: they document
behaviour that must SURVIVE the change, not behaviour still to be added.

Covered behaviours
──────────────────
1. Injection when relevant      — rare token in memory + matching prompt → block injected
2. No injection when irrelevant — unrelated prompt → no block; [memory-check] intact
3. Order                        — memory block appears BEFORE [memory-check]
4. Fail-safe (empty stdin)      — no crash, no injection, [memory-check] present
4b. Fail-safe (non-JSON stdin)  — same guarantees
4c. Fail-safe (JSON no 'prompt')— same guarantees
5. No regression                — [memory-check] always present (relevant + irrelevant)
6. Empty corpus fail-safe       — empty repo + irrelevant query → no block, hook normal

Hook invocation pattern
───────────────────────
Mirrors test_pre_task_recall.py exactly: subprocess with JSON on stdin, cwd=temp repo.
The hook is a UserPromptSubmit hook that emits PLAIN TEXT (not JSON) on stdout.
"""

import json
import os
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_cmd

# Make lib/ importable for direct recall_relevant() calls if needed.
LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

HOOK_PATH = os.path.join(HOOKS_DIR, "user-prompt-memory-check.py")

# Read the real plugin version so _make_installed_repo can write a matching
# manifest — prevents needs_upgrade() from triggering the auto-upgrade branch.
_PLUGIN_JSON = os.path.join(SOURCE_ROOT, ".claude-plugin", "plugin.json")
with open(_PLUGIN_JSON) as _f:
    _PLUGIN_VERSION = json.load(_f)["version"]


# ── Repo helpers (mirrors test_pre_task_recall.py and test_recall.py) ─────

def _make_repo(tmp_path, name="repo"):
    """Create a minimal git repo (no git-memory installation)."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _make_installed_repo(tmp_path, name="repo"):
    """Create a minimal git repo that appears to have git-memory installed.

    Writes the minimum artefacts that make the hook skip needs_install() and
    needs_upgrade() and proceed to the normal [memory-check] output:

      1. CLAUDE.md with the required 'BEGIN unmassk-toolkit' marker and
         'Context Checkpoint Commits' text (so needs_upgrade check 1 is False).
      2. .claude/.unmassk/manifest.json with version == PLUGIN_VERSION (so the
         semver comparison returns False — manifest is not older than code).

    This lets the hook reach the [memory-check] / recall-injection path even
    in a bare temporary repo that has never run git-memory-install.py.
    """
    repo = _make_repo(tmp_path, name)

    # 1. Minimal CLAUDE.md managed block
    claude_md_path = os.path.join(repo, "CLAUDE.md")
    with open(claude_md_path, "w") as f:
        f.write(
            "<!-- BEGIN unmassk-toolkit -->\n"
            "Context Checkpoint Commits\n"
            "<!-- END unmassk-toolkit -->\n"
        )

    # 2. Manifest with current version so needs_upgrade() → False
    unmassk_dir = os.path.join(repo, ".claude", ".unmassk")
    os.makedirs(unmassk_dir, exist_ok=True)
    manifest_path = os.path.join(unmassk_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump({"version": _PLUGIN_VERSION}, f)

    # 3. Create the session-booted flag so the hook emits [git-memory] root
    #    (already-booted path) rather than the verbose first-boot block.
    booted_flag = os.path.join(unmassk_dir, ".session-booted")
    open(booted_flag, "w").close()

    return repo


def _commit(repo, subject, trailers=""):
    """Add a memory commit with optional trailer block."""
    msg = subject if not trailers else subject + "\n\n" + trailers
    git_cmd(["commit", "--allow-empty", "-m", msg], repo)


# ── Hook invocation helpers ────────────────────────────────────────────────

def _run_hook(repo, prompt, *, input_text=None):
    """Invoke user-prompt-memory-check.py with JSON stdin from repo directory.

    If input_text is provided, it is used verbatim (for fail-safe edge cases).
    Otherwise a well-formed payload {"prompt": prompt} is built automatically.

    Returns (returncode, stdout_str, stderr_str).
    The hook emits PLAIN TEXT, not JSON.
    """
    if input_text is None:
        input_text = json.dumps({"prompt": prompt})
    return run_cmd(
        [sys.executable, HOOK_PATH],
        cwd=repo,
        input_text=input_text,
    )


# ── Tests: injection when relevant (Case 1) ───────────────────────────────

class TestInjectsWhenRelevant:
    """Rare token in memory + matching prompt → recall block injected in stdout."""

    def test_injected_label_present_when_relevant(self, tmp_path):
        """Hook injects a '[memoria relevante...' label when recall matches.

        RED: today the hook does not read stdin → no injection → FAIL.
        """
        repo = _make_installed_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/zorblax): zorblax strategy",
            "Decision: usar zorblax para configuracion especial del sistema",
        )

        rc, stdout, _stderr = _run_hook(repo, "algo sobre zorblax")

        assert rc == 0
        assert "[memoria relevante" in stdout, (
            "Expected '[memoria relevante...' label in stdout when recall matches; "
            f"got: {stdout!r}"
        )

    def test_injected_block_contains_memory_text(self, tmp_path):
        """The injected block contains the actual memory entry text.

        RED: today the hook does not read stdin → no injection → FAIL.
        """
        repo = _make_installed_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/zorblax): zorblax design",
            "Decision: usar zorblax para el pipeline de configuracion",
        )

        rc, stdout, _stderr = _run_hook(repo, "algo sobre zorblax")

        assert rc == 0
        assert "zorblax" in stdout, (
            "Expected memory content ('zorblax') in stdout after injection; "
            f"got: {stdout!r}"
        )


# ── Tests: no injection when irrelevant (Case 2) ──────────────────────────

class TestNoInjectionWhenIrrelevant:
    """Unrelated prompt → no recall block; [memory-check] still present."""

    def test_no_label_for_irrelevant_prompt(self, tmp_path):
        """No '[memoria relevante' label when query is unrelated to memory.

        The token 'qwzzz' does not appear in any memory commit.

        This may already PASS today (hook ignores stdin → never injects).
        Once Ultron implements, it must continue to pass.
        """
        repo = _make_installed_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/zorblax): zorblax design",
            "Decision: usar zorblax para configuracion especial",
        )

        rc, stdout, _stderr = _run_hook(repo, "mensaje sin relacion ninguna qwzzz")

        assert rc == 0
        assert "[memoria relevante" not in stdout, (
            "Must NOT inject '[memoria relevante' for an irrelevant prompt; "
            f"got: {stdout!r}"
        )

    def test_memory_check_present_when_no_injection(self, tmp_path):
        """[memory-check] block still appears even when recall returns nothing.

        INVARIANT: this must hold before AND after the implementation.
        """
        repo = _make_installed_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/zorblax): zorblax design",
            "Decision: usar zorblax para configuracion especial",
        )

        rc, stdout, _stderr = _run_hook(repo, "mensaje sin relacion ninguna qwzzz")

        assert rc == 0
        assert "[memory-check]" in stdout, (
            "Expected '[memory-check]' in stdout even when no injection occurs; "
            f"got: {stdout!r}"
        )


# ── Tests: order (Case 3) ─────────────────────────────────────────────────

class TestInjectionOrder:
    """When recall block is injected, it must appear BEFORE [memory-check]."""

    def test_memory_block_before_memory_check(self, tmp_path):
        """[memoria relevante...] appears before [memory-check] in stdout.

        RED: today the hook does not read stdin → no injection → FAIL.
        """
        repo = _make_installed_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/zorblax): zorblax strategy",
            "Decision: usar zorblax para configuracion especial del pipeline",
        )

        rc, stdout, _stderr = _run_hook(repo, "algo sobre zorblax")

        assert rc == 0
        assert "[memoria relevante" in stdout, (
            "Expected '[memoria relevante...' label; hook may not have read stdin yet"
        )
        assert "[memory-check]" in stdout, "Expected '[memory-check]' block in stdout"

        pos_recall = stdout.find("[memoria relevante")
        pos_check = stdout.find("[memory-check]")
        assert pos_recall < pos_check, (
            f"Memory recall block (pos {pos_recall}) must precede "
            f"[memory-check] block (pos {pos_check})"
        )


# ── Tests: fail-safe — empty stdin (Case 4) ──────────────────────────────

class TestFailSafeEmptyStdin:
    """INVARIANT: empty stdin → no crash (exit 0), no injection, [memory-check] present.

    The current hook does not read stdin at all, so these pass today.
    They must continue to pass after Ultron adds stdin reading.
    """

    def test_exit_0_with_empty_stdin(self, tmp_path):
        """Empty stdin must not cause a non-zero exit.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)
        rc, stdout, _stderr = _run_hook(repo, prompt=None, input_text="")

        assert rc == 0, (
            f"Hook must exit 0 on empty stdin; got rc={rc}"
        )

    def test_no_injection_with_empty_stdin(self, tmp_path):
        """Empty stdin must not produce a recall injection.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/zorblax): zorblax design",
            "Decision: usar zorblax para configuracion especial",
        )
        rc, stdout, _stderr = _run_hook(repo, prompt=None, input_text="")

        assert rc == 0
        assert "[memoria relevante" not in stdout, (
            "Empty stdin must not trigger recall injection; "
            f"got: {stdout!r}"
        )

    def test_memory_check_present_with_empty_stdin(self, tmp_path):
        """[memory-check] block still present on empty stdin.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)
        rc, stdout, _stderr = _run_hook(repo, prompt=None, input_text="")

        assert rc == 0
        assert "[memory-check]" in stdout, (
            "Expected '[memory-check]' even with empty stdin; "
            f"got: {stdout!r}"
        )


# ── Tests: fail-safe — non-JSON stdin (Case 4b) ───────────────────────────

class TestFailSafeNonJsonStdin:
    """INVARIANT: garbage/non-JSON stdin → no crash, no injection, [memory-check] present."""

    def test_exit_0_with_garbage_stdin(self, tmp_path):
        """Garbage non-JSON stdin must not cause a non-zero exit.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)
        rc, stdout, _stderr = _run_hook(repo, prompt=None, input_text="THIS IS NOT JSON {{{")

        assert rc == 0, (
            f"Hook must exit 0 on non-JSON stdin; got rc={rc}"
        )

    def test_no_injection_with_garbage_stdin(self, tmp_path):
        """Garbage stdin must not trigger recall injection.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/zorblax): zorblax design",
            "Decision: usar zorblax para configuracion especial",
        )
        rc, stdout, _stderr = _run_hook(repo, prompt=None, input_text="THIS IS NOT JSON {{{")

        assert rc == 0
        assert "[memoria relevante" not in stdout, (
            "Non-JSON stdin must not trigger injection; got: {stdout!r}"
        )

    def test_memory_check_present_with_garbage_stdin(self, tmp_path):
        """[memory-check] block still present on non-JSON stdin.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)
        rc, stdout, _stderr = _run_hook(repo, prompt=None, input_text="THIS IS NOT JSON {{{")

        assert rc == 0
        assert "[memory-check]" in stdout, (
            f"Expected '[memory-check]' even with garbage stdin; got: {stdout!r}"
        )


# ── Tests: fail-safe — JSON without 'prompt' key (Case 4c) ───────────────

class TestFailSafeJsonNoPrompt:
    """INVARIANT: valid JSON but no 'prompt' key → no crash, no injection, hook normal."""

    def test_exit_0_with_json_no_prompt(self, tmp_path):
        """JSON without 'prompt' key must not cause a non-zero exit.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)
        payload = json.dumps({"other_field": "value", "something": 42})
        rc, stdout, _stderr = _run_hook(repo, prompt=None, input_text=payload)

        assert rc == 0, (
            f"Hook must exit 0 when JSON has no 'prompt' key; got rc={rc}"
        )

    def test_no_injection_with_json_no_prompt(self, tmp_path):
        """JSON without 'prompt' key must not trigger injection.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/zorblax): zorblax design",
            "Decision: usar zorblax para configuracion especial",
        )
        payload = json.dumps({"other_field": "value"})
        rc, stdout, _stderr = _run_hook(repo, prompt=None, input_text=payload)

        assert rc == 0
        assert "[memoria relevante" not in stdout, (
            "JSON without 'prompt' must not trigger injection; "
            f"got: {stdout!r}"
        )

    def test_memory_check_present_with_json_no_prompt(self, tmp_path):
        """[memory-check] block still present when JSON has no 'prompt' key.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)
        payload = json.dumps({"other_field": "value"})
        rc, stdout, _stderr = _run_hook(repo, prompt=None, input_text=payload)

        assert rc == 0
        assert "[memory-check]" in stdout, (
            f"Expected '[memory-check]' when JSON has no 'prompt'; got: {stdout!r}"
        )


# ── Tests: no regression of core output (Case 5) ─────────────────────────

class TestNoRegression:
    """[memory-check] always present regardless of injection outcome."""

    def test_memory_check_present_when_injecting(self, tmp_path):
        """[memory-check] still present in stdout when recall injects a block.

        RED: today the hook does not read stdin → no injection → still passes
        for the [memory-check] assertion, but fails on the [memoria relevante] check.
        After Ultron implements, both assertions must hold.
        """
        repo = _make_installed_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/zorblax): zorblax strategy",
            "Decision: usar zorblax para configuracion especial del sistema",
        )

        rc, stdout, _stderr = _run_hook(repo, "algo sobre zorblax")

        assert rc == 0
        assert "[memoria relevante" in stdout, (
            "Injection must occur for the relevant prompt"
        )
        assert "[memory-check]" in stdout, (
            "Expected '[memory-check]' even when recall block is injected; "
            f"got: {stdout!r}"
        )

    def test_base_output_not_empty(self, tmp_path):
        """Hook always emits non-empty stdout.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)
        rc, stdout, _stderr = _run_hook(repo, "cualquier mensaje de usuario")

        assert rc == 0
        assert stdout.strip(), "Hook must always emit non-empty stdout"


# ── Tests: empty corpus fail-safe (Case 6) ────────────────────────────────

class TestEmptyCorpusFailSafe:
    """Empty repo (no memory commits) → no injection, hook normal output.

    INVARIANT for the no-injection and [memory-check] assertions (pass today).
    RED for [memoria relevante] being absent — already passes today trivially,
    but confirms the isolation: empty corpus must never inject.
    """

    def test_no_injection_empty_repo(self, tmp_path):
        """Empty corpus → no '[memoria relevante' label.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)

        rc, stdout, _stderr = _run_hook(repo, "algo sobre zorblax recall importante")

        assert rc == 0
        assert "[memoria relevante" not in stdout, (
            "Empty corpus must never inject a recall block; "
            f"got: {stdout!r}"
        )

    def test_memory_check_present_empty_repo(self, tmp_path):
        """[memory-check] block present even with empty corpus.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)

        rc, stdout, _stderr = _run_hook(repo, "algo sobre zorblax recall importante")

        assert rc == 0
        assert "[memory-check]" in stdout, (
            f"Expected '[memory-check]' with empty corpus; got: {stdout!r}"
        )

    def test_exit_0_empty_repo(self, tmp_path):
        """Hook exits 0 with empty corpus.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)

        rc, _stdout, _stderr = _run_hook(repo, "zorblax recall")

        assert rc == 0, f"Expected exit 0 with empty corpus; got rc={rc}"
