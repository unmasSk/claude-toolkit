"""
Acceptance-level contract tests for Crown RETRACTION — test-first pass
(ALL contract tests below should FAIL against the unmodified codebase).

Context: gitto.md Mode C already documents retraction, but there is ZERO
code support for it (`grep -rn "Retract-Crown" lib/ hooks/ tests/` → no
results before this file). Crown itself (the 👑 highlight) already works
and is covered by test_crown.py — this file covers ONLY the new
retraction mechanism layered on top of it.

The mechanism (per unmassk-toolkit/agents/gitto.md, Mode C — Consolidator):
  - A crown is a normal memory commit (`decision`/`memo`/`remember`) carrying
    `Crown: <kind>`. It is rendered 👑 at boot (already implemented).
  - To retract a crown, someone writes a NEW, separate normal memory commit
    (`memo`/`decision`, matching the crowned scope) carrying:
        Retract-Crown: <hash of the bad crown commit>
        Why: <what was wrong>
    This is purely additive — it never touches/edits/deletes the old crown
    commit. It only tells the boot renderer to stop treating that specific
    commit's Crown as active.
  - After retraction, the scope goes back to being rendered as if it had no
    crown at all (plain recency-based dedup, no 👑) — it must NOT fall back
    to an older, already-superseded crown for the same scope.
  - The retraction commit itself is a normal memory entry in its own right:
    it shows up in its own type's section like any other entry. It is not
    itself treated as a crown just because it carries Retract-Crown.
  - A Retract-Crown value that doesn't match any real crown commit (typo,
    wrong hash, or a hash that never carried Crown:) is a no-op — no crash,
    nothing retracted, and it does NOT itself become a crown.

Layout of the required implementation (inferred from the existing Crown
implementation this mirrors):
  - lib/constants.py: "Retract-Crown" added to VALID_KEYS + MEMORY_KEYS;
    kept OUT of RECALL_KEYS/TOMBSTONE_KEYS (it matches by commit HASH, not
    by normalized text, so it cannot reuse the tombstone-by-text mechanism).
  - lib/parsing.py: scan_trailers_memory must surface "Retract-Crown" when
    present (a direct consequence of adding it to MEMORY_KEYS).
  - hooks/session-start-boot.py: extract_memory()/extract_glossary() must
    collect retracted crown hashes from the same commit range they already
    scan, and treat a crowned commit's `is_crown` as False when its own
    hash is in the retracted set — WITHOUT letting an older, previously
    superseded crown for the same scope resurface.
  - hooks/pre-validate-commit-trailers.py / post-validate-commit-trailers.py:
    a commit carrying Retract-Crown must also carry Why: (mirrors the
    existing block-for-Claude / warn-for-human pattern already used for
    every other required trailer in this codebase — see
    validate_trailers() in both hook files).

STATUS ORDER (expected the first time this file is run, before Ultron
implements anything):
  ALL tests in this file FAIL red, except where marked [GUARD] (already
  true today, must stay true throughout implementation).
"""

import importlib.util
import json
import os
import sys

import pytest

from conftest import (
    SOURCE_ROOT, HOOKS_DIR, INSTALL,
    run_cmd, git_cmd, run_script,
)

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

BOOT_HOOK = os.path.join(HOOKS_DIR, "session-start-boot.py")
PRE_HOOK_PATH = os.path.join(HOOKS_DIR, "pre-validate-commit-trailers.py")
POST_HOOK_PATH = os.path.join(HOOKS_DIR, "post-validate-commit-trailers.py")


# ── Repo helpers (mirroring test_crown.py's helpers) ───────────────────────

def _make_repo(tmp_path, name="repo"):
    """Create a minimal git repo (no install required)."""
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


def _short_sha(repo):
    """Return the abbreviated hash (%h) of the last commit — same format
    extract_memory()/extract_glossary() use when they scan `git log`."""
    _, out, _ = git_cmd(["log", "-1", "--pretty=format:%h"], repo)
    return out.strip()


def _make_installed_repo(tmp_path, name="repo"):
    """Create a repo with install + baseline memory commits."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    run_script(INSTALL, repo, ["--auto"])

    _commit(repo,
            "🧭 decision(auth): use JWT",
            "Decision: JWT over sessions\nWhy: stateless API")
    _commit(repo,
            "📌 memo(api): async preference",
            "Memo: preference - async/await everywhere")
    _commit(repo,
            "🧠 remember(user): prefers Spanish",
            "Remember: user - prefiere respuestas en español")
    return repo


def _run_boot(repo):
    """Run the session-start-boot hook and return stdout.

    NOTE (contract correction, Bex 2026-07-04): stdout is now always a short
    banner (STATUS/BRANCH/pointer/BOOT COMPLETE). The DECISIONS/MEMOS
    content these tests assert on lives only in the boot-log file — use
    _boot_log_content(repo) (below) to run boot and get that content.
    """
    rc, stdout, stderr = run_cmd([sys.executable, BOOT_HOOK], repo)
    return stdout


# ── Boot-log file helpers (same pattern as test_boot_output.py) ───────────

BOOT_LOG_REL_PARTS = (".claude", ".unmassk", "boot-log-latest.txt")


def _boot_log_path(repo):
    return os.path.join(repo, *BOOT_LOG_REL_PARTS)


def _read_boot_log(repo):
    with open(_boot_log_path(repo), encoding="utf-8") as f:
        return f.read()


def _boot_log_content(repo):
    """Run boot (writes the boot-log file) and return its full content.

    DECISIONS:/MEMOS: sections live only here now — never in stdout.
    """
    _run_boot(repo)
    return _read_boot_log(repo)


def _decisions_block(output, span=800):
    start = output.find("DECISIONS:")
    return output[start:start + span] if start != -1 else ""


def _memos_block(output, span=800):
    start = output.find("MEMOS:")
    return output[start:start + span] if start != -1 else ""


# ── validate_trailers() helpers (direct import, no subprocess) ─────────────
#
# We import the hooks' own validate_trailers() function directly rather than
# going through the full hook via subprocess, because for Claude authors the
# hook has an UNRELATED, unconditional "use the wrapper script" gate that
# blocks any direct `git commit` regardless of trailer content — that gate
# would mask whether Why: is actually being required by validate_trailers().

def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pre_hook_errors(commit_type, trailers, branch=""):
    mod = _load_module(PRE_HOOK_PATH, "_pre_hook_under_test")
    return mod.validate_trailers(commit_type, trailers, branch)


def _post_hook_errors(commit_type, trailers, branch=""):
    mod = _load_module(POST_HOOK_PATH, "_post_hook_under_test")
    return mod.validate_trailers(commit_type, trailers, branch)


def _run_pre_hook_full(repo, subject, trailers, as_claude=False):
    """Run the real pre-hook end-to-end with a literal `git commit` command,
    as a human (as_claude=False) so the unrelated "use the wrapper script"
    gate never fires and the real trailer-validation path executes.

    Returns (rc, stdout, stderr).
    """
    command = f'git commit -m "{subject}"'
    if trailers:
        command += f' -m "{trailers}"'
    payload = {"tool_input": {"command": command}}
    env = {"CLAUDE_CODE": "1"} if as_claude else {}
    return run_script(PRE_HOOK_PATH, repo, env=env, input_text=json.dumps(payload))


# ── extract_memory() helper (subprocess isolation, mirrors test_crown.py) ──

def _extract_memory(repo):
    """Call extract_memory() from session-start-boot with the test repo as CWD."""
    import json
    code = f"""
import sys, os
sys.path.insert(0, {repr(LIB_DIR)})
sys.path.insert(0, {repr(HOOKS_DIR)})
os.chdir({repr(repo)})

import subprocess as _sp
import git_helpers as _gh

def _patched_run_git(args, cwd=None):
    env = dict(os.environ)
    env['GIT_DIR'] = os.path.join({repr(repo)}, '.git')
    env['GIT_WORK_TREE'] = {repr(repo)}
    result = _sp.run(
        ['git'] + args,
        capture_output=True, text=True, encoding='utf-8', cwd={repr(repo)}, env=env,
    )
    return result.returncode, result.stdout.strip()
_gh.run_git = _patched_run_git

import importlib, importlib.util
spec = importlib.util.spec_from_file_location('boot', {repr(BOOT_HOOK)})
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)
boot.run_git = _patched_run_git  # type: ignore

import json
result = boot.extract_memory()

def _ser(lst):
    return [list(item) for item in lst]

print(json.dumps({{
    'decisions': _ser(result.get('decisions', [])),
    'memos':     _ser(result.get('memos', [])),
    'remembers': _ser(result.get('remembers', [])),
}}))
"""
    rc, stdout, stderr = run_cmd([sys.executable, "-c", code], repo, timeout=30)
    if rc != 0:
        raise RuntimeError(f"_extract_memory failed (rc={rc}): {stderr}")
    return json.loads(stdout)


# ══════════════════════════════════════════════════════════════════════════
# SECTION 1 — constants.py contracts for Retract-Crown
# ══════════════════════════════════════════════════════════════════════════

class TestRetractCrownInConstants:
    """Retract-Crown trailer key must be registered in the right sets."""

    def test_01_retract_crown_in_valid_keys(self):
        """Retract-Crown must be in VALID_KEYS so pre-validate does not
        silently strip it (parse_trailers only keeps keys in VALID_KEYS).

        STATUS: RED — Retract-Crown is not yet in VALID_KEYS.
        """
        from constants import VALID_KEYS
        assert "Retract-Crown" in VALID_KEYS, (
            "Retract-Crown must be in VALID_KEYS or commits carrying it "
            "will have the trailer silently dropped by parse_trailers()"
        )

    def test_02_retract_crown_in_memory_keys(self):
        """Retract-Crown must be in MEMORY_KEYS so scan_trailers_memory
        (full-body scan used by extract_memory/extract_glossary) returns it.

        STATUS: RED — Retract-Crown is not yet in MEMORY_KEYS.
        """
        from constants import MEMORY_KEYS
        assert "Retract-Crown" in MEMORY_KEYS, (
            "Retract-Crown must be in MEMORY_KEYS or the boot scanner will "
            "never see the retraction and will keep rendering the bad crown"
        )

    def test_03_retract_crown_not_in_recall_keys(self):
        """Retract-Crown is a modifier, not a recall category.

        STATUS: GREEN [GUARD] — already absent; must stay passing.
        """
        from constants import RECALL_KEYS
        assert "Retract-Crown" not in RECALL_KEYS

    def test_04_retract_crown_not_in_tombstone_keys(self):
        """Retract-Crown matches by commit HASH, not by normalized text —
        it must never be treated as a text-matching tombstone trailer
        (that would only work by coincidence and never on purpose).

        STATUS: GREEN [GUARD] — already absent; must stay passing.
        """
        from constants import TOMBSTONE_KEYS
        assert "Retract-Crown" not in TOMBSTONE_KEYS


# ══════════════════════════════════════════════════════════════════════════
# SECTION 2 — parsing.py contracts
# ══════════════════════════════════════════════════════════════════════════

class TestRetractCrownInParsing:
    """scan_trailers_memory must surface Retract-Crown when present."""

    def test_05_scan_trailers_memory_returns_retract_crown(self):
        """scan_trailers_memory returns {'Retract-Crown': '<hash>', ...}.

        STATUS: RED — Retract-Crown is not in MEMORY_KEYS so it's filtered out.
        """
        from parsing import scan_trailers_memory
        body = "Decision: no consensus, reverted\nRetract-Crown: abc1234\nWhy: it was wrong"
        result = scan_trailers_memory(body)
        assert "Retract-Crown" in result, f"Got: {result}"
        assert result["Retract-Crown"] == "abc1234", f"Got: {result.get('Retract-Crown')!r}"

    def test_05b_scan_trailers_memory_no_retract_crown_when_absent(self):
        """scan_trailers_memory does not inject Retract-Crown when absent.

        STATUS: GREEN [GUARD] — already correct; must remain passing.
        """
        from parsing import scan_trailers_memory
        body = "Decision: use JWT for auth"
        result = scan_trailers_memory(body)
        assert "Retract-Crown" not in result


# ══════════════════════════════════════════════════════════════════════════
# SECTION 3 — a matching Retract-Crown stops the crown from rendering (item 1)
# ══════════════════════════════════════════════════════════════════════════

class TestRetractedCrownStopsRendering:
    """A crown with a matching Retract-Crown commit renders as if it had
    no crown at all — no 👑, plain recency-based entry instead."""

    def test_06_retracted_crown_no_longer_shows_crown_emoji(self, tmp_path):
        """Crown a decision, confirm it renders 👑, retract it, confirm the
        👑 and the crowned synthesis text disappear from DECISIONS.

        STATUS: RED — no retraction handling exists; the crown stays 👑 forever.
        """
        repo = _make_installed_repo(tmp_path)

        _commit(repo,
                "🧭 decision(auth): JWT is canonical",
                "Decision: JWT over sessions is the canonical choice\n"
                "Crown: Decision\nWhy: consolidation pass")
        crown_sha = _short_sha(repo)

        # Sanity: crown is active before retraction.
        before = _decisions_block(_boot_log_content(repo))
        assert "👑" in before, f"Crown must be active before retraction. Block:\n{before}"
        assert "canonical choice" in before

        _commit(repo,
                "🧭 decision(auth): reopen auth method",
                f"Decision: no consensus, reopened for review\n"
                f"Retract-Crown: {crown_sha}\nWhy: canonical text was outdated after the auth rewrite")

        after = _decisions_block(_boot_log_content(repo))
        assert "👑" not in after, (
            f"Retracted crown must not render with 👑 anymore. Block:\n{after}"
        )
        assert "canonical choice" not in after, (
            f"The retracted crown's synthesis text must no longer be shown as the "
            f"scope's canonical entry. Block:\n{after}"
        )
        assert "reopened for review" in after, (
            f"The scope must fall back to plain (non-crowned) rendering — the "
            f"retraction commit's own text should be the current entry. Block:\n{after}"
        )


# ══════════════════════════════════════════════════════════════════════════
# SECTION 4 — regression: crown with no retraction still renders (item 2)
# ══════════════════════════════════════════════════════════════════════════

class TestCrownWithoutRetractionRegression:
    """A crown with NO matching Retract-Crown anywhere renders normally.

    Included directly alongside the retraction tests for context, even
    though test_crown.py::test_08 already covers this — this guards that
    introducing retraction support does not accidentally require a
    Retract-Crown to be present for a crown to render.
    """

    def test_07_crown_without_any_retraction_renders_normally(self, tmp_path):
        """STATUS: GREEN [GUARD] — must remain passing throughout implementation."""
        repo = _make_installed_repo(tmp_path)

        _commit(repo,
                "🧭 decision(payments): use Stripe",
                "Decision: Stripe over Adyen\nCrown: Decision\nWhy: consolidation")

        block = _decisions_block(_boot_log_content(repo))
        assert "👑" in block, f"Crown with no retraction must render 👑. Block:\n{block}"
        assert "Stripe over Adyen" in block


# ══════════════════════════════════════════════════════════════════════════
# SECTION 5 — Retract-Crown referencing a hash that isn't a real crown (item 3)
# ══════════════════════════════════════════════════════════════════════════

class TestRetractCrownNoOp:
    """A Retract-Crown value that does not match a real crown commit must
    be a no-op: no crash, nothing retracted, and it never itself becomes a
    crown just by carrying the trailer."""

    def test_08_retract_crown_referencing_non_crown_commit_is_noop(self, tmp_path):
        """The referenced hash IS a real commit, but it never carried Crown:.

        STATUS: RED — retraction isn't implemented, but this documents the
        no-op requirement once it is (a wrong/irrelevant hash must not
        accidentally retract the real crown just because it's the only
        retraction machinery in play).
        """
        repo = _make_installed_repo(tmp_path)

        _commit(repo,
                "📌 memo(search): note on tokenizer",
                "Memo: stack - using the standard tokenizer for now")
        non_crown_sha = _short_sha(repo)

        _commit(repo,
                "🧭 decision(search): use elastic",
                "Decision: elastic over solr\nCrown: Decision\nWhy: consolidation")

        _commit(repo,
                "🧭 decision(search): retraction attempt on wrong target",
                f"Decision: no change\nRetract-Crown: {non_crown_sha}\n"
                f"Why: testing a hash that never carried Crown:")

        block = _decisions_block(_boot_log_content(repo))
        assert "👑" in block, (
            f"Retract-Crown referencing a real commit that never carried Crown: "
            f"must be a no-op — the actual crown must remain active. Block:\n{block}"
        )
        assert "elastic" in block

    def test_09_retract_crown_with_garbage_hash_does_not_crash_boot(self, tmp_path):
        """The referenced hash matches NO commit at all (typo / made up).

        STATUS: RED for the crown-persists assertion; this also guards
        that boot must never crash on a malformed Retract-Crown value.
        """
        repo = _make_installed_repo(tmp_path)

        _commit(repo,
                "🧭 decision(search): use elastic",
                "Decision: elastic over solr\nCrown: Decision\nWhy: consolidation")

        _commit(repo,
                "🧭 decision(search): retraction attempt with typo hash",
                "Decision: no change\nRetract-Crown: zzzznothash\n"
                "Why: testing a malformed/typo hash")

        output = _run_boot(repo)
        assert "BOOT COMPLETE" in output, (
            f"Boot must not crash on a Retract-Crown hash matching no commit. "
            f"Output:\n{output[:600]}"
        )
        content = _read_boot_log(repo)
        block = _decisions_block(content)
        assert "👑" in block, "A garbage Retract-Crown hash must not retract the real crown"
        assert "elastic" in block


# ══════════════════════════════════════════════════════════════════════════
# SECTION 6 — multiple crowns over time (re-consolidation) (item 4)
# ══════════════════════════════════════════════════════════════════════════

class TestRetractCrownMultipleCrownsOverTime:
    """Retracting an older, already-superseded crown must not affect a
    newer, still-valid crown. Retracting the newest (active) crown must
    fall back to un-crowned — never to the older superseded crown."""

    def test_10_retracting_older_crown_leaves_newer_crown_active(self, tmp_path):
        """STATUS: RED — no retraction handling; also RED today because
        without retraction there's nothing to distinguish, but the
        assertion on is_crown=True for the newer entry documents the
        exact expected shape of extract_memory()'s output.
        """
        repo = _make_repo(tmp_path)

        _commit(repo,
                "🧭 decision(auth): older canonical",
                "Decision: older canonical choice\nCrown: Decision")
        older_sha = _short_sha(repo)

        _commit(repo,
                "🧭 decision(auth): newer canonical",
                "Decision: newer canonical choice\nCrown: Decision")

        _commit(repo,
                "🧭 decision(auth): retract older canonical",
                f"Decision: cleanup, superseded record\nRetract-Crown: {older_sha}\n"
                f"Why: older canonical was already superseded, cleaning up the record")

        result = _extract_memory(repo)
        auth_entries = [d for d in result["decisions"] if d[0] == "(auth)"]
        assert len(auth_entries) == 1, f"Expected one deduped entry for (auth): {auth_entries}"

        label, text, is_crown = auth_entries[0]
        assert is_crown is True, (
            f"Retracting the OLDER crown must not affect the newer, still-valid "
            f"crown. Got: {auth_entries[0]}"
        )
        assert "newer canonical" in text, f"Got: {text!r}"

    def test_11_retracting_newest_crown_falls_back_to_uncrowned_not_older_crown(self, tmp_path):
        """STATUS: RED — retraction isn't implemented, and even a naive
        per-commit 'is_crown AND not retracted' implementation would fail
        this test by letting the older crown resurface. This is the crux
        of the retraction contract.
        """
        repo = _make_repo(tmp_path)

        _commit(repo,
                "🧭 decision(auth): older canonical",
                "Decision: older canonical choice\nCrown: Decision")

        _commit(repo,
                "🧭 decision(auth): newer canonical",
                "Decision: newer canonical choice\nCrown: Decision")
        newer_sha = _short_sha(repo)

        _commit(repo,
                "🧭 decision(auth): retract newer canonical",
                f"Decision: no consensus, reverted after retraction\nRetract-Crown: {newer_sha}\n"
                f"Why: newer canonical text was factually wrong")

        result = _extract_memory(repo)
        auth_entries = [d for d in result["decisions"] if d[0] == "(auth)"]
        assert len(auth_entries) == 1, f"Expected one deduped entry for (auth): {auth_entries}"

        label, text, is_crown = auth_entries[0]
        assert is_crown is False, (
            f"Retracting the NEWEST (active) crown must leave the scope "
            f"uncrowned. Got: {auth_entries[0]}"
        )
        assert "older canonical" not in text, (
            f"Must NOT fall back to the older, already-superseded crown. Got: {text!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# SECTION 7 — the retraction commit is a normal entry in its own right (item 5)
# ══════════════════════════════════════════════════════════════════════════

class TestRetractionCommitIsNormalEntry:
    """The retraction commit itself (memo/decision carrying Retract-Crown)
    must show up in its own type's section like any other entry — it is
    not itself rendered as a crown, and it does not get hidden."""

    def test_12_retraction_commit_appears_as_normal_memo_entry(self, tmp_path):
        """STATUS: RED — Retract-Crown is not scanned at all today, so the
        retraction commit's own Memo: text renders exactly as any other
        non-crowned memo, and the crown it targets stays 👑 forever.
        """
        repo = _make_installed_repo(tmp_path)

        _commit(repo,
                "📌 memo(billing): use quarterly caps",
                "Memo: requirement - enforce quarterly usage caps\n"
                "Crown: Memo\nWhy: consolidation")
        crown_sha = _short_sha(repo)

        _commit(repo,
                "📌 memo(billing): retract quarterly caps crown",
                f"Memo: requirement - quarterly caps crown was wrong, revisit per-plan caps\n"
                f"Retract-Crown: {crown_sha}\n"
                f"Why: quarterly caps didn't account for enterprise plans")

        block = _memos_block(_boot_log_content(repo))
        assert "👑" not in block, (
            f"Retraction must remove the crown from MEMOS. Block:\n{block}"
        )
        assert "revisit per-plan caps" in block, (
            f"The retraction commit's own Memo: text must appear as a normal "
            f"entry in the MEMOS section — it must not be hidden. Block:\n{block}"
        )


# ══════════════════════════════════════════════════════════════════════════
# SECTION 8 — missing Why: on a Retract-Crown commit (item 6)
# ══════════════════════════════════════════════════════════════════════════

class TestRetractCrownRequiresWhy:
    """Missing-required-trailer handling for Retract-Crown must follow the
    SAME pattern already used everywhere else in validate_trailers() (see
    pre-validate-commit-trailers.py / post-validate-commit-trailers.py):
    a missing required trailer is appended to the errors list, which then
    drives block-for-Claude / warn-for-human upstream in main(). No new
    enforcement style is invented here.

    We exercise this on a `memo` commit specifically, because memo commits
    do not otherwise require Why: (validate_trailers only requires Memo:
    for that type) — so this isolates the NEW behavior Retract-Crown adds,
    rather than the pre-existing Why: requirement `decision` already has.
    """

    def test_13_pre_hook_flags_missing_why_on_memo_with_retract_crown(self):
        """validate_trailers("memo", ...) must flag a missing Why: when
        Retract-Crown is present, using the same "Why" wording already used
        for every other required-trailer error in this function.

        STATUS: RED — Retract-Crown carries no Why: requirement today; a
        memo with only Memo: passes validate_trailers() unconditionally.
        """
        trailers = {"Memo": "requirement - JWT crown was wrong", "Retract-Crown": "abc1234"}
        errors = _pre_hook_errors("memo", trailers)
        assert any("Why" in e for e in errors), (
            f"A Retract-Crown-carrying memo commit without Why: must be flagged, "
            f"same as any other missing-required-trailer case. Got errors: {errors}"
        )

    def test_13b_post_hook_flags_missing_why_on_memo_with_retract_crown(self):
        """Same contract, mirrored in the post-hook's own validate_trailers()
        copy — both hooks must agree (belt and suspenders).

        STATUS: RED — same root cause as test_13.
        """
        trailers = {"Memo": "requirement - JWT crown was wrong", "Retract-Crown": "abc1234"}
        errors = _post_hook_errors("memo", trailers)
        assert any("Why" in e for e in errors), f"Got errors: {errors}"

    def test_14_retract_crown_with_why_produces_no_errors(self):
        """CONTROL: once Why: is present, validate_trailers() must return no
        errors for an otherwise well-formed memo.

        STATUS: GREEN [GUARD] once implemented — must not regress.
        """
        trailers = {
            "Memo": "requirement - JWT crown was wrong",
            "Retract-Crown": "abc1234",
            "Why": "crown text was factually wrong after the auth rewrite",
        }
        errors = _pre_hook_errors("memo", trailers)
        assert errors == [], f"Well-formed Retract-Crown commit must pass. Got: {errors}"

    def test_15_human_commit_missing_why_on_retract_crown_warns_with_why_mentioned(self, tmp_path):
        """Integration: a human (non-Claude) commit is never blocked (matches
        every other trailer check in this codebase — see
        test_drift.py::test_hook_robustness's as_claude=False expectation),
        but the warning printed to stderr must mention Why: once Retract-Crown
        requires it — proving the check actually ran, not just that human
        commits are unconditionally exit 0 regardless of content.

        STATUS: RED — today this produces no warning at all (memo type
        currently only requires Memo:, which is already present).
        """
        repo = _make_repo(tmp_path)
        subject = "📌 memo(auth): retract stale crown"
        trailers = "Memo: requirement - JWT crown was wrong\nRetract-Crown: abc1234"

        rc, _, stderr = _run_pre_hook_full(repo, subject, trailers, as_claude=False)

        assert rc == 0, "Human commits are never blocked, only warned."
        assert "Why" in stderr, (
            f"Missing Why: on a Retract-Crown commit must be surfaced in the "
            f"warning, proving the new requirement is actually enforced. stderr={stderr!r}"
        )
