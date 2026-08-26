"""
Tests for user-prompt-memory-check.py (UserPromptSubmit hook).

hooks/user-prompt-memory-check.py is STILL LIVE (confirmed: exists on disk,
runs on every user message) -- this whole file is NOT the same situation as
its sibling test_hardening_recall.py (RETIRADO: that one tested lib/recall.py
directly, which no longer exists).

Recall push→pull (git-memory decision 1e94975, issue #69): the automatic
per-message recall injection ("[memoria relevante...]" / <memory-data> block)
and the old "[memory-check]" reminder text were both retired from this hook's
per-message output — replaced by a single static banner (see _BANNER in the
hook).

CORRECCION 2026-08-26 (Bilbo finding): `recall_relevant()` / `lib/recall.py`
do NOT exist anymore -- deleted with the rest of the v1 memory system
(confirmed: no such file on disk). This comment used to claim they were
"still callable on demand"; that stopped being true when v1 was retired.
The LIB_DIR sys.path insert below is now dead weight from that era (nothing
in this file imports from lib/ directly) -- left in place, harmless, not
removed here since this pass is a comment realignment, not a cleanup.

The tests below that asserted the removed injection block or the removed
"[memory-check]" text were deleted (dead assertions against a feature that no
longer exists) — see git-memory decision for issue #72 (cut useless tests).
What remains here documents behaviour that SURVIVES the change, exercised
via REAL subprocess calls to the real, still-live hook: fail-safe stdin
handling (no crash on empty/garbage/oversized/no-prompt stdin, real rc==0
checked against the real process), the absence of the retired injection
label, and the hook always emitting a non-empty banner. This is real,
current regression coverage for a hook that still runs on every message --
not a candidate for the same retirement as test_hardening_recall.py.

Hook invocation pattern
───────────────────────
Subprocess with JSON on stdin, cwd=temp repo (test_pre_task_recall.py, which
this used to mirror, no longer exists on disk either -- see CORRECCION
above; the pattern itself survives independently in this file's own
_run_hook() helper).
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
with open(_PLUGIN_JSON, encoding="utf-8") as _f:
    _PLUGIN_VERSION = json.load(_f)["version"]


# ── Repo helpers (test_pre_task_recall.py/test_recall.py no longer exist; kept for its own sake) ─────

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
    with open(claude_md_path, "w", encoding="utf-8") as f:
        f.write(
            "<!-- BEGIN unmassk-toolkit -->\n"
            "Context Checkpoint Commits\n"
            "<!-- END unmassk-toolkit -->\n"
        )

    # 2. Manifest with current version so needs_upgrade() → False
    unmassk_dir = os.path.join(repo, ".claude", ".unmassk")
    os.makedirs(unmassk_dir, exist_ok=True)
    manifest_path = os.path.join(unmassk_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"version": _PLUGIN_VERSION}, f)

    # 3. Create the session-booted flag so the hook emits [git-memory] root
    #    (already-booted path) rather than the verbose first-boot block.
    booted_flag = os.path.join(unmassk_dir, ".session-booted")
    open(booted_flag, "w", encoding="utf-8").close()

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


# ── Tests: no regression of core output (Case 5) ─────────────────────────

class TestNoRegression:
    """Hook always emits a non-empty banner regardless of prompt content."""

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

    def test_exit_0_empty_repo(self, tmp_path):
        """Hook exits 0 with empty corpus.

        INVARIANT — already passes today; must not regress.
        """
        repo = _make_installed_repo(tmp_path)

        rc, _stdout, _stderr = _run_hook(repo, "zorblax recall")

        assert rc == 0, f"Expected exit 0 with empty corpus; got rc={rc}"
