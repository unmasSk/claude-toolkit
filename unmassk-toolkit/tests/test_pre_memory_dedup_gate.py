"""
Tests for pre-memory-dedup-gate.py — the lexical dedup gate hook.

What this hook does
-------------------
PreToolUse(Bash) hook. Intercepts Bash commands that invoke
git-memory-commit.py with type ``memo`` or ``remember``. Extracts the
trailer text from ``--trailer "Memo=..."`` or ``--trailer "Remember=..."``,
computes lexical overlap against existing entries of the SAME type in git
memory, and:

- Near-duplicate (overlap >= threshold) → allow + permissionDecisionReason
  naming the conflicting entry.
- No overlap → allow, no reason.
- Fail-open on ANY error (bad JSON, no git, etc.) → allow, no reason, exit 0.

The hook NEVER emits ``permissionDecision: "deny"``.
The hook ALWAYS exits 0.

Test surface
------------
10 behaviour contracts (acceptance granularity, test-first pass):

1. Memo identical to an existing memo → warns.
2. Memo that is a paraphrase of an existing memo (same keywords, different
   word order) → warns.
3. BOUNDARY — memo that shares MANY words with an existing memo but conveys
   a DIFFERENT, even contradictory, meaning → does NOT warn.
4. Memo completely different from all existing memos → does NOT warn.
5. Remember near-duplicate of an existing remember → warns.
6. Cross-type: memo text similar to an EXISTING REMEMBER (not a memo) →
   does NOT warn (only same-type comparison).
7. Empty corpus / repo with no memory → does NOT warn.
8. Commit type that is not memo/remember (decision, context, feat, wip) →
   passthrough, never warns. (Decision is sacred and must never be gated.)
9. Fail-open: stdin with invalid JSON → allow, no crash, exit 0.
10. Hook NEVER emits deny or exit != 0 under any condition.

I/O contract
------------
- Stdin:  JSON {"tool_name": "Bash", "tool_input": {"command": str}}
- Stdout: JSON {
              "hookSpecificOutput": {
                  "hookEventName": "PreToolUse",
                  "permissionDecision": "allow",
                  ["permissionDecisionReason": str]  ← only when near-dup found
              }
          }
- Exit 0 always.

Reference implementation (NOT to replicate, only for pattern)
---------------------------------------------------------------
See hooks/pre-task-recall.py.

Text pairs
----------
Case 2 (paraphrase — MUST warn):
  Existing:  "usar JWT para autenticar usuarios porque las sesiones no escalan en microservicios"
  Incoming:  "implementar autenticacion con JWT en microservicios ya que las sesiones no escalan"
  Rationale: after stopword removal, shared content tokens include
  {jwt, autenticar/autenticacion, sesiones, escalan, microservicios}.
  Both sentences make the same architectural claim. A correctly calibrated
  threshold will treat this as a near-duplicate.

Case 3 (boundary — must NOT warn):
  Existing:  "usar JWT para autenticacion porque las sesiones no escalan"
  Incoming:  "usar sesiones para autenticacion porque JWT no permite revocacion en tiempo real"
  Rationale: after stopword removal, shared tokens are limited to
  {jwt, autenticacion, sesiones}.  The sentences contradict each other — one
  recommends JWT, the other recommends sessions.  The overlap score is
  substantially lower than the paraphrase pair above.  A correctly calibrated
  threshold will NOT flag this as a near-duplicate.

The two cases bracket the threshold: paraphrase (case 2) above it,
contradictory-but-word-rich (case 3) below it.
"""

import json
import os
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_script, run_cmd

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

HOOK_PATH = os.path.join(HOOKS_DIR, "pre-memory-dedup-gate.py")

# ── Text pairs used in cases 2 and 3 ──────────────────────────────────────
#
# Keep these at module level so the docstring claim and the test data
# are a single source of truth.

# Case 2 — paraphrase (should warn)
_PARAPHRASE_EXISTING = (
    "usar JWT para autenticar usuarios porque las sesiones no escalan en microservicios"
)
_PARAPHRASE_INCOMING = (
    "implementar autenticacion con JWT en microservicios ya que las sesiones no escalan"
)

# Case 3 — boundary: many shared words, opposite meaning (must NOT warn)
_BOUNDARY_EXISTING = (
    "usar JWT para autenticacion porque las sesiones no escalan"
)
_BOUNDARY_INCOMING = (
    "usar sesiones para autenticacion porque JWT no permite revocacion en tiempo real"
)


# ── Repo helpers ───────────────────────────────────────────────────────────

def _make_repo(tmp_path, name="repo"):
    """Create a minimal git repo with user config."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _commit(repo, subject, trailers=""):
    """Add a memory commit with optional trailer block."""
    msg = subject if not trailers else subject + "\n\n" + trailers
    git_cmd(["commit", "--allow-empty", "-m", msg], repo)


def _seed_memo(repo, text):
    """Commit an existing Memo entry."""
    _commit(repo, "memo(test): seed entry", f"Memo: preference - {text}")


def _seed_remember(repo, text):
    """Commit an existing Remember entry."""
    _commit(repo, "remember(test): seed entry", f"Remember: {text}")


# ── Hook invocation helpers ────────────────────────────────────────────────

def _bash_command_for(commit_type, text):
    """Build a realistic git-memory-commit.py Bash command string.

    The hook intercepts commands of this shape:
        python3 .../git-memory-commit.py memo --trailer "Memo=<text>"
    or
        python3 .../git-memory-commit.py remember --trailer "Remember=<text>"
    """
    key = commit_type.capitalize()
    return (
        f"python3 /path/to/git-memory-commit.py {commit_type} "
        f'--trailer "{key}={text}"'
    )


def _run_hook(repo, command):
    """Invoke pre-memory-dedup-gate.py with a Bash tool_input payload.

    Returns (returncode, parsed_output_dict_or_None, raw_stdout, stderr).
    """
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    rc, stdout, stderr = run_script(HOOK_PATH, repo, input_text=payload)
    try:
        parsed = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        parsed = None
    return rc, parsed, stdout, stderr


def _run_hook_raw(repo, payload_str):
    """Invoke hook with a raw stdin string (for fail-open / malformed paths)."""
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
    """Return the hookSpecificOutput sub-dict, or {} if absent."""
    if parsed is None:
        return {}
    return parsed.get("hookSpecificOutput", {})


def _has_warning(parsed):
    """True if the hook emitted a permissionDecisionReason (the near-dup warning)."""
    hso = _hook_specific(parsed)
    return bool(hso.get("permissionDecisionReason", ""))


# ── Case 1: identical memo → warns ────────────────────────────────────────

class TestIdenticalMemoWarns:
    def test_identical_text_triggers_warning(self, tmp_path):
        """A memo whose text is character-for-character identical to an existing
        memo must produce a non-empty permissionDecisionReason.
        """
        repo = _make_repo(tmp_path)
        text = "preferir bun sobre node para el backend del proyecto"
        _seed_memo(repo, text)

        cmd = _bash_command_for("memo", text)
        rc, parsed, stdout, stderr = _run_hook(repo, cmd)

        assert rc == 0, f"Hook must exit 0; rc={rc}, stderr={stderr!r}"
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow", (
            "Hook must always allow — never deny"
        )
        assert _has_warning(parsed), (
            "Identical memo must trigger a warning in permissionDecisionReason"
        )

    def test_warning_reason_names_existing_entry(self, tmp_path):
        """The permissionDecisionReason for a near-duplicate must contain
        recognisable text from the existing entry (so the agent knows what
        it duplicates).
        """
        repo = _make_repo(tmp_path)
        text = "preferir bun sobre node para el backend del proyecto"
        _seed_memo(repo, text)

        cmd = _bash_command_for("memo", text)
        rc, parsed, _, _ = _run_hook(repo, cmd)

        assert rc == 0
        reason = _hook_specific(parsed).get("permissionDecisionReason", "")
        # At least one significant word from the existing entry must appear
        # in the warning — the agent needs a clue to find the duplicate.
        assert any(
            word in reason.lower()
            for word in ["bun", "node", "backend", "preferir"]
        ), f"Reason must name the existing entry; got: {reason!r}"


# ── Case 2: paraphrase → warns ────────────────────────────────────────────

class TestParaphraseWarns:
    """Memo that is a rewrite of an existing memo must trigger a warning.

    Pair used:
      Existing: _PARAPHRASE_EXISTING
      Incoming: _PARAPHRASE_INCOMING
    """

    def test_paraphrase_triggers_warning(self, tmp_path):
        """Same architectural claim, different word order → warns."""
        repo = _make_repo(tmp_path)
        _seed_memo(repo, _PARAPHRASE_EXISTING)

        cmd = _bash_command_for("memo", _PARAPHRASE_INCOMING)
        rc, parsed, _, stderr = _run_hook(repo, cmd)

        assert rc == 0, f"Hook must exit 0; stderr={stderr!r}"
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert _has_warning(parsed), (
            "Paraphrase (same meaning, reordered) must trigger a near-dup warning.\n"
            f"  existing : {_PARAPHRASE_EXISTING!r}\n"
            f"  incoming : {_PARAPHRASE_INCOMING!r}"
        )

    def test_paraphrase_warning_is_not_empty(self, tmp_path):
        """The warning reason string for a paraphrase is non-empty."""
        repo = _make_repo(tmp_path)
        _seed_memo(repo, _PARAPHRASE_EXISTING)

        cmd = _bash_command_for("memo", _PARAPHRASE_INCOMING)
        rc, parsed, _, _ = _run_hook(repo, cmd)

        assert rc == 0
        reason = _hook_specific(parsed).get("permissionDecisionReason", "")
        assert len(reason) > 0, "permissionDecisionReason must not be an empty string"


# ── Case 3: BOUNDARY — many shared words, opposite meaning → NO warning ───

class TestBoundaryNoFalsePositive:
    """THE MOST IMPORTANT TEST.

    Two memos share a cluster of content words (jwt, autenticacion, sesiones)
    but assert OPPOSITE architectural recommendations.  The gate MUST NOT
    flag this as a near-duplicate.

    Pair used:
      Existing: _BOUNDARY_EXISTING
      Incoming: _BOUNDARY_INCOMING

    If this test fails (i.e. the hook warns), the threshold is too aggressive
    and real new information would be silently suppressed.
    """

    def test_boundary_pair_does_not_warn(self, tmp_path):
        """Contradictory memo (high word overlap, opposite meaning) → no warning."""
        repo = _make_repo(tmp_path)
        _seed_memo(repo, _BOUNDARY_EXISTING)

        cmd = _bash_command_for("memo", _BOUNDARY_INCOMING)
        rc, parsed, _, stderr = _run_hook(repo, cmd)

        assert rc == 0, f"Hook must exit 0; stderr={stderr!r}"
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert not _has_warning(parsed), (
            "Contradictory memo (opposite recommendation, high surface word overlap) "
            "MUST NOT trigger a warning — this is the false-positive the gate must avoid.\n"
            f"  existing : {_BOUNDARY_EXISTING!r}\n"
            f"  incoming : {_BOUNDARY_INCOMING!r}"
        )

    def test_boundary_pair_is_a_genuine_boundary(self, tmp_path):
        """Confirms the paraphrase pair warns AND the boundary pair does not,
        in the same repo.  This is the calibration proof: both pairs exist
        simultaneously — the hook must differentiate them.
        """
        repo = _make_repo(tmp_path)
        _seed_memo(repo, _PARAPHRASE_EXISTING)
        _seed_memo(repo, _BOUNDARY_EXISTING)

        # Paraphrase → must warn
        cmd_para = _bash_command_for("memo", _PARAPHRASE_INCOMING)
        rc1, parsed1, _, _ = _run_hook(repo, cmd_para)
        assert rc1 == 0
        assert _has_warning(parsed1), (
            "Paraphrase must warn even when boundary entry coexists in corpus"
        )

        # Boundary → must NOT warn
        cmd_boundary = _bash_command_for("memo", _BOUNDARY_INCOMING)
        rc2, parsed2, _, _ = _run_hook(repo, cmd_boundary)
        assert rc2 == 0
        assert not _has_warning(parsed2), (
            "Boundary pair must not warn even when paraphrase entry coexists in corpus"
        )


# ── Case 4: completely different memo → no warning ────────────────────────

class TestDifferentMemoNoWarning:
    def test_unrelated_memo_passes_clean(self, tmp_path):
        """A memo about a completely unrelated topic must not trigger a warning."""
        repo = _make_repo(tmp_path)
        _seed_memo(repo, "preferir bun sobre node para el backend del proyecto")

        # Totally unrelated topic
        cmd = _bash_command_for(
            "memo",
            "usar postgres con indices gin para busqueda fulltext en documentos",
        )
        rc, parsed, _, _ = _run_hook(repo, cmd)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert not _has_warning(parsed), (
            "Unrelated memo must produce a clean allow with no warning"
        )

    def test_completely_disjoint_vocabulary_no_warning(self, tmp_path):
        """When new and existing memo share no content tokens at all → no warning."""
        repo = _make_repo(tmp_path)
        _seed_memo(repo, "cachear respuestas de la api con redis y ttl de 300 segundos")

        cmd = _bash_command_for(
            "memo",
            "preferir migraciones incrementales en la base de datos relacional",
        )
        rc, parsed, _, _ = _run_hook(repo, cmd)

        assert rc == 0
        assert not _has_warning(parsed)


# ── Case 5: remember near-dup → warns ─────────────────────────────────────

class TestRememberNearDupWarns:
    def test_similar_remember_triggers_warning(self, tmp_path):
        """A remember that closely matches an existing remember must warn."""
        repo = _make_repo(tmp_path)
        existing = "usuario prefiere respuestas concisas sin resumen al final"
        _seed_remember(repo, existing)

        # Paraphrase of the same preference
        incoming = "el usuario quiere respuestas concisas sin resumen al final de cada mensaje"
        cmd = _bash_command_for("remember", incoming)
        rc, parsed, _, stderr = _run_hook(repo, cmd)

        assert rc == 0, f"Hook must exit 0; stderr={stderr!r}"
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert _has_warning(parsed), (
            "Near-duplicate remember must trigger a warning"
        )

    def test_identical_remember_triggers_warning(self, tmp_path):
        """Identical remember text must warn."""
        repo = _make_repo(tmp_path)
        text = "responder siempre en español con ortografia completa"
        _seed_remember(repo, text)

        cmd = _bash_command_for("remember", text)
        rc, parsed, _, _ = _run_hook(repo, cmd)

        assert rc == 0
        assert _has_warning(parsed)


# ── Case 6: cross-type → no warning ───────────────────────────────────────

class TestCrossTypeNoWarning:
    def test_memo_similar_to_remember_does_not_warn(self, tmp_path):
        """A memo similar to an EXISTING REMEMBER must NOT warn — only same-type
        comparison is performed.  memo↔remember cross-comparison is forbidden.
        """
        repo = _make_repo(tmp_path)
        # Plant the similar text as a remember, not a memo
        _seed_remember(repo, _PARAPHRASE_EXISTING)

        # Incoming is a MEMO — should not match against the remember above
        cmd = _bash_command_for("memo", _PARAPHRASE_INCOMING)
        rc, parsed, _, _ = _run_hook(repo, cmd)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert not _has_warning(parsed), (
            "memo must not be compared against existing remember entries — "
            "cross-type comparison must not happen"
        )

    def test_remember_similar_to_memo_does_not_warn(self, tmp_path):
        """Symmetric: a remember similar to an existing MEMO must NOT warn."""
        repo = _make_repo(tmp_path)
        # Plant similar text as a memo
        _seed_memo(repo, _PARAPHRASE_EXISTING)

        # Incoming is a REMEMBER — should not match against the memo above
        cmd = _bash_command_for("remember", _PARAPHRASE_INCOMING)
        rc, parsed, _, _ = _run_hook(repo, cmd)

        assert rc == 0
        assert not _has_warning(parsed), (
            "remember must not be compared against existing memo entries"
        )


# ── Case 7: empty corpus → no warning ─────────────────────────────────────

class TestEmptyCorpusNoWarning:
    def test_empty_repo_no_warning(self, tmp_path):
        """Repo with no memory commits → no warning, clean allow."""
        repo = _make_repo(tmp_path)

        cmd = _bash_command_for("memo", "preferir bun sobre node para el backend")
        rc, parsed, _, _ = _run_hook(repo, cmd)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert not _has_warning(parsed)

    def test_repo_with_only_decision_commits_no_warning(self, tmp_path):
        """Repo with only Decision commits (no memo/remember) → no warning."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(auth): usar JWT",
            "Decision: usar JWT para autenticacion porque las sesiones no escalan",
        )

        cmd = _bash_command_for("memo", "usar JWT para autenticacion")
        rc, parsed, _, _ = _run_hook(repo, cmd)

        assert rc == 0
        # No memos exist → no same-type match → no warning
        assert not _has_warning(parsed)


# ── Case 8: non-memo/remember commit types → passthrough, no warning ──────

class TestNonMemoRememberPassthrough:
    """Commits of type decision, context, feat, wip, fix, etc. must never be
    intercepted or warned.  Decision is sacred — never gated.
    """

    @pytest.mark.parametrize("commit_type,trailer_key", [
        ("decision", "Decision"),
        ("context", "Context"),
        ("feat", "Feat"),
        ("wip", "Wip"),
        ("fix", "Fix"),
        ("refactor", "Refactor"),
    ])
    def test_non_memo_remember_type_passes_clean(self, commit_type, trailer_key, tmp_path):
        """Commit type '{commit_type}' must pass through without any warning."""
        repo = _make_repo(tmp_path)
        # Seed existing memos so the corpus is non-empty
        _seed_memo(repo, "usar JWT para autenticacion en microservicios")
        _seed_remember(repo, "usuario prefiere respuestas en español")

        # Build a command for the non-memo/remember type
        text = "usar JWT para autenticacion en microservicios porque las sesiones no escalan"
        cmd = (
            f"python3 /path/to/git-memory-commit.py {commit_type} "
            f'--trailer "{trailer_key}={text}"'
        )
        rc, parsed, _, _ = _run_hook(repo, cmd)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert not _has_warning(parsed), (
            f"Commit type '{commit_type}' must not trigger dedup gate"
        )

    def test_decision_specifically_never_warned(self, tmp_path):
        """Decision is the most sacred type — must NEVER be intercepted.
        Even if the decision text is identical to an existing decision, the hook
        must not warn (decisions are never gated).
        """
        repo = _make_repo(tmp_path)
        decision_text = "usar JWT para autenticacion porque las sesiones no escalan"
        _commit(
            repo,
            "decision(auth): usar JWT",
            f"Decision: {decision_text}",
        )

        # Attempt to commit the exact same decision text — must not warn
        cmd = (
            f"python3 /path/to/git-memory-commit.py decision "
            f'--trailer "Decision={decision_text}"'
        )
        rc, parsed, _, _ = _run_hook(repo, cmd)

        assert rc == 0
        assert not _has_warning(parsed), (
            "Decision commits must NEVER be intercepted or warned, ever"
        )

    def test_bash_command_not_invoking_git_memory_commit_passes(self, tmp_path):
        """Any Bash command that does NOT invoke git-memory-commit.py must pass
        through without inspection.
        """
        repo = _make_repo(tmp_path)
        _seed_memo(repo, "preferir bun sobre node para el backend")

        rc, parsed, _, _ = _run_hook(repo, "git log --oneline -10")

        assert rc == 0
        assert not _has_warning(parsed)

    def test_non_bash_tool_passes_through(self, tmp_path):
        """tool_name other than Bash must be ignored (passthrough)."""
        repo = _make_repo(tmp_path)
        _seed_memo(repo, "preferir bun sobre node para el backend")

        payload = json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/x.txt", "content": "hello"},
        })
        rc, parsed, _, _ = _run_hook_raw(repo, payload)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert not _has_warning(parsed)


# ── Case 9: fail-open — invalid JSON → allow, no crash ────────────────────

class TestFailOpenInvalidJson:
    def test_malformed_json_returns_allow_exit0(self, tmp_path):
        """Completely invalid JSON → fail-open: allow, exit 0, valid JSON stdout."""
        repo = _make_repo(tmp_path)
        rc, parsed, stdout, _ = _run_hook_raw(repo, "NOT JSON AT ALL {{{")

        assert rc == 0, f"Malformed JSON must not cause non-zero exit; rc={rc}"
        assert parsed is not None, (
            f"Hook must emit valid JSON even on malformed input; stdout={stdout!r}"
        )
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"
        assert not _has_warning(parsed)

    def test_empty_stdin_returns_allow_exit0(self, tmp_path):
        """Empty stdin → fail-open: allow, exit 0."""
        repo = _make_repo(tmp_path)
        rc, parsed, stdout, _ = _run_hook_raw(repo, "")

        assert rc == 0
        assert parsed is not None, (
            f"Hook must emit valid JSON on empty stdin; stdout={stdout!r}"
        )
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"

    def test_json_without_tool_input_fail_open(self, tmp_path):
        """JSON missing tool_input key → fail-open: allow."""
        repo = _make_repo(tmp_path)
        payload = json.dumps({"tool_name": "Bash"})
        rc, parsed, _, _ = _run_hook_raw(repo, payload)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"

    def test_json_null_tool_input_fail_open(self, tmp_path):
        """tool_input: null → fail-open: allow."""
        repo = _make_repo(tmp_path)
        payload = json.dumps({"tool_name": "Bash", "tool_input": None})
        rc, parsed, _, _ = _run_hook_raw(repo, payload)

        assert rc == 0
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"

    def test_json_array_stdin_fail_open(self, tmp_path):
        """JSON array instead of object → fail-open: allow."""
        repo = _make_repo(tmp_path)
        rc, parsed, stdout, _ = _run_hook_raw(repo, '["Bash", "memo"]')

        assert rc == 0
        assert parsed is not None, f"Must emit valid JSON; stdout={stdout!r}"
        hso = _hook_specific(parsed)
        assert hso.get("permissionDecision") == "allow"


# ── Case 10: NEVER deny, NEVER exit != 0 ──────────────────────────────────

class TestNeverDenyNeverNonZeroExit:
    """Comprehensive invariant: deny and non-zero exit are absolutely forbidden."""

    def _assert_allow_and_exit0(self, rc, parsed, raw_stdout, context):
        assert rc == 0, (
            f"Hook must ALWAYS exit 0; got rc={rc}; context={context!r}"
        )
        assert raw_stdout, (
            f"Hook must always emit output; context={context!r}"
        )
        try:
            p = json.loads(raw_stdout)
        except json.JSONDecodeError:
            pytest.fail(
                f"Hook must always emit valid JSON; context={context!r}, "
                f"stdout={raw_stdout!r}"
            )
        decision = p.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision not in ("deny", "block"), (
            f"permissionDecision must never be 'deny' or 'block'; "
            f"got {decision!r}; context={context!r}"
        )
        assert decision == "allow", (
            f"permissionDecision must be 'allow'; got {decision!r}; context={context!r}"
        )

    def test_invariant_normal_near_dup_path(self, tmp_path):
        """Warning path must not emit deny."""
        repo = _make_repo(tmp_path)
        text = "preferir bun sobre node para el backend del proyecto"
        _seed_memo(repo, text)
        cmd = _bash_command_for("memo", text)
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=payload)
        parsed = json.loads(stdout)
        self._assert_allow_and_exit0(rc, parsed, stdout, "normal near-dup warning path")

    def test_invariant_clean_path(self, tmp_path):
        """Clean (no near-dup) path must not emit deny."""
        repo = _make_repo(tmp_path)
        _seed_memo(repo, "preferir bun sobre node para el backend del proyecto")
        cmd = _bash_command_for("memo", "usar postgres con gin para busqueda fulltext")
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=payload)
        parsed = json.loads(stdout)
        self._assert_allow_and_exit0(rc, parsed, stdout, "clean no-dup path")

    def test_invariant_malformed_json(self, tmp_path):
        """Malformed JSON must not emit deny."""
        repo = _make_repo(tmp_path)
        rc, stdout, _ = run_cmd(
            [sys.executable, HOOK_PATH], cwd=repo, input_text="{{{not json"
        )
        self._assert_allow_and_exit0(rc, None, stdout, "malformed json")

    def test_invariant_empty_stdin(self, tmp_path):
        """Empty stdin must not emit deny."""
        repo = _make_repo(tmp_path)
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text="")
        self._assert_allow_and_exit0(rc, None, stdout, "empty stdin")

    def test_invariant_decision_type(self, tmp_path):
        """Decision type must not emit deny."""
        repo = _make_repo(tmp_path)
        cmd = (
            'python3 /path/to/git-memory-commit.py decision '
            '--trailer "Decision=usar JWT para autenticacion"'
        )
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=payload)
        self._assert_allow_and_exit0(rc, None, stdout, "decision type passthrough")

    def test_invariant_non_bash_tool(self, tmp_path):
        """Non-Bash tool must not emit deny."""
        repo = _make_repo(tmp_path)
        payload = json.dumps({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "ultron", "prompt": "do something"},
        })
        rc, stdout, _ = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=payload)
        self._assert_allow_and_exit0(rc, None, stdout, "non-Bash tool Task")

    @pytest.mark.parametrize("bad_payload", [
        "not json",
        "{}",
        json.dumps({"tool_name": "Bash", "tool_input": None}),
        json.dumps({"tool_name": "Bash", "tool_input": {}}),
        json.dumps({"tool_name": "Bash", "tool_input": {"command": ""}}),
        json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo hello"}}),
    ])
    def test_invariant_various_edge_inputs(self, bad_payload, tmp_path):
        """Assorted edge-case inputs must all exit 0 and never deny."""
        repo = _make_repo(tmp_path)
        rc, stdout, _ = run_cmd(
            [sys.executable, HOOK_PATH], cwd=repo, input_text=bad_payload
        )
        self._assert_allow_and_exit0(rc, None, stdout, f"edge input: {bad_payload!r}")
