"""
Contract tests for the Crown modifier — test-first pass (ALL should FAIL now).

Crown is a MODIFIER trailer, not a content key:
  - A normal memory commit carries ALSO a `Crown: <kind>` trailer
  - <kind> ∈ {Decision, Memo, Remember}
  - Meaning: this entry is the canonical (king) entry for its category
  - Crown is PURELY additive/presentational — it NEVER tombstones a Decision

Layout:
  - lib/constants.py: Crown in VALID_KEYS + MEMORY_KEYS; NOT in RECALL_KEYS/TOMBSTONE_KEYS
  - lib/parsing.py: scan_trailers_memory returns Crown value when present
  - hooks/session-start-boot.py:
      extract_memory() returns (label, text, is_crown) 3-tuples
      extract_glossary() returns (label, text, is_crown) 3-tuples
      Crowned entries appear FIRST with 👑 prefix in their section
      Crown does NOT consume the BOOT_MAX_* budget of non-crowned entries
      Crowned glossary entry beats non-crowned recent entry at same scope

GUARD TESTS (already pass, marked [GUARD]):
  - None of the 11 cases pass today — all contracts are red.

STATUS ORDER (expected after running pytest):
  test_01 FAIL — Crown not in VALID_KEYS
  test_02 FAIL — Crown not in MEMORY_KEYS
  test_03 FAIL — Crown not absent from RECALL_KEYS (it IS absent, so this one passes) [GUARD]
  test_04 FAIL — Crown not absent from TOMBSTONE_KEYS (it IS absent, so this one passes) [GUARD]
  test_05 FAIL — scan_trailers_memory does not return Crown
  test_06 FAIL — extract_memory returns 2-tuples, not 3-tuples with is_crown
  test_07 FAIL — Crown kind specificity not implemented
  test_08 FAIL — crowned decision shows 👑 and appears before non-crowned
  test_09 FAIL — Crown applies to Memo
  test_10 FAIL — Crown applies to Remember
  test_11 FAIL — Crown does not consume budget of non-crowned
  test_12 FAIL — glossary cache roundtrip with schema_version
  test_13 FAIL — crowned glossary entry beats non-crowned recent at same scope
  test_14 FAIL — crowned decision is not tombstonable [GUARD — Decisions already exempt, but
                  the specific Crown-annotated path must also be clean]
  test_15 PASS — non-crowned entries render exactly as today [GUARD]
"""

import json
import os
import re
import sys

import pytest

# ── Path bootstrap ──────────────────────────────────────────────────────────
# conftest adds lib/ to sys.path automatically (see conftest.py SOURCE_ROOT setup).
# We also need the hooks dir importable.

from conftest import (
    SOURCE_ROOT, HOOKS_DIR, INSTALL,
    run_cmd, git_cmd, write_file, run_script,
)

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

BOOT_HOOK = os.path.join(HOOKS_DIR, "session-start-boot.py")


# ── Repo helpers (mirroring test_recall.py pattern) ────────────────────────

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
    banner (STATUS/BRANCH/pointer/BOOT COMPLETE). The DECISIONS/MEMOS/
    REMEMBER sections these tests assert on live only in the boot-log file —
    use _read_boot_log(repo) after calling this to get the full content.
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


# ── helpers: import production modules with _repo_dir override ─────────────

def _extract_memory(repo):
    """Call extract_memory() from session-start-boot with the test repo as CWD."""
    # We run the function by importing the hook module with cwd set to the test repo.
    # To avoid polluting sys.modules across tests we import fresh each time.
    import importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_boot_mod", BOOT_HOOK,
    )
    mod = importlib.util.load_from_spec(spec) if hasattr(importlib.util, "load_from_spec") else None
    # Simpler approach: run as subprocess and parse output is fragile.
    # Better: monkeypatch run_git inside the module.
    # We use subprocess to run a small Python snippet that patches cwd.
    code = f"""
import sys, os
sys.path.insert(0, {repr(LIB_DIR)})
sys.path.insert(0, {repr(HOOKS_DIR)})
os.chdir({repr(repo)})

# Patch run_git to operate in {repr(repo)}
import subprocess as _sp
import git_helpers as _gh

_orig_run_git = _gh.run_git
def _patched_run_git(args, cwd=None):
    env = dict(os.environ)
    env['GIT_DIR'] = os.path.join({repr(repo)}, '.git')
    env['GIT_WORK_TREE'] = {repr(repo)}
    result = _sp.run(
        ['git'] + args,
        capture_output=True, text=True, cwd={repr(repo)}, env=env,
    )
    return result.returncode, result.stdout.strip()
_gh.run_git = _patched_run_git

import importlib, importlib.util
spec = importlib.util.spec_from_file_location('boot', {repr(BOOT_HOOK)})
boot = importlib.util.module_from_spec(spec)
# patch run_git in boot too after load
spec.loader.exec_module(boot)
boot.run_git = _patched_run_git  # type: ignore

import json
result = boot.extract_memory()
# Serialize: decisions/memos/remembers may be 2- or 3-tuples
def _ser(lst):
    out = []
    for item in lst:
        out.append(list(item))
    return out

print(json.dumps({{
    'decisions': _ser(result.get('decisions', [])),
    'memos':     _ser(result.get('memos', [])),
    'remembers': _ser(result.get('remembers', [])),
}}))
"""
    rc, stdout, stderr = run_cmd(
        [sys.executable, "-c", code], repo, timeout=30,
    )
    if rc != 0:
        raise RuntimeError(f"_extract_memory failed (rc={rc}): {stderr}")
    return json.loads(stdout)


def _extract_glossary(repo):
    """Call extract_glossary() from session-start-boot with the test repo."""
    code = f"""
import sys, os
sys.path.insert(0, {repr(LIB_DIR)})
sys.path.insert(0, {repr(HOOKS_DIR)})
os.chdir({repr(repo)})

import subprocess as _sp
import git_helpers as _gh

_orig_run_git = _gh.run_git
def _patched_run_git(args, cwd=None):
    env = dict(os.environ)
    env['GIT_DIR'] = os.path.join({repr(repo)}, '.git')
    env['GIT_WORK_TREE'] = {repr(repo)}
    result = _sp.run(
        ['git'] + args,
        capture_output=True, text=True, cwd={repr(repo)}, env=env,
    )
    return result.returncode, result.stdout.strip()
_gh.run_git = _patched_run_git

import importlib, importlib.util
spec = importlib.util.spec_from_file_location('boot', {repr(BOOT_HOOK)})
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)
boot.run_git = _patched_run_git  # type: ignore

import json
result = boot.extract_glossary()

def _ser(lst):
    return [list(item) for item in lst]

print(json.dumps({{
    'decisions': _ser(result.get('decisions', [])),
    'memos':     _ser(result.get('memos', [])),
    'remembers': _ser(result.get('remembers', [])),
}}))
"""
    rc, stdout, stderr = run_cmd(
        [sys.executable, "-c", code], repo, timeout=30,
    )
    if rc != 0:
        raise RuntimeError(f"_extract_glossary failed (rc={rc}): {stderr}")
    return json.loads(stdout)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — constants.py contracts
# ══════════════════════════════════════════════════════════════════════════════

class TestCrownInConstants:
    """Crown trailer key must be registered in the right sets."""

    def test_01_crown_in_valid_keys(self):
        """Crown must be in VALID_KEYS so validation hooks accept it.

        STATUS: RED — Crown is not yet in VALID_KEYS.
        """
        from constants import VALID_KEYS
        assert "Crown" in VALID_KEYS, (
            "Crown must be in VALID_KEYS so the pre-validate hook does not "
            "reject commits that carry a Crown: trailer"
        )

    def test_02_crown_in_memory_keys(self):
        """Crown must be in MEMORY_KEYS so scan_trailers_memory returns it.

        STATUS: RED — Crown is not yet in MEMORY_KEYS.
        """
        from constants import MEMORY_KEYS
        assert "Crown" in MEMORY_KEYS, (
            "Crown must be in MEMORY_KEYS so scan_trailers_memory() includes "
            "it in the returned dict (required by extract_memory and extract_glossary)"
        )

    def test_03_crown_not_in_recall_keys(self):
        """Crown must NOT be in RECALL_KEYS — it is a modifier, not a recall category.

        STATUS: GREEN [GUARD] — Crown is already absent; this must stay passing.
        """
        from constants import RECALL_KEYS
        assert "Crown" not in RECALL_KEYS, (
            "Crown is a modifier, not a recall category. "
            "It must never appear in RECALL_KEYS."
        )

    def test_04_crown_not_in_tombstone_keys(self):
        """Crown must NOT be in TOMBSTONE_KEYS — crowning is additive, never a GC marker.

        STATUS: GREEN [GUARD] — Crown is already absent; this must stay passing.
        """
        from constants import TOMBSTONE_KEYS
        assert "Crown" not in TOMBSTONE_KEYS, (
            "Crown must never be a tombstone key. "
            "The INVARIANTE DE ORO: a crowned Decision is never tombstoned."
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — parsing.py contracts
# ══════════════════════════════════════════════════════════════════════════════

class TestCrownInParsing:
    """scan_trailers_memory must surface the Crown key when present."""

    def test_05_scan_trailers_memory_returns_crown(self):
        """scan_trailers_memory returns {'Crown': 'Decision', ...} when Crown: Decision is in body.

        STATUS: RED — Crown is not in MEMORY_KEYS so the key is filtered out.
        """
        from parsing import scan_trailers_memory
        body = "Decision: use JWT for auth\nCrown: Decision"
        result = scan_trailers_memory(body)
        assert "Crown" in result, (
            f"scan_trailers_memory must return Crown key. Got: {result}"
        )
        assert result["Crown"] == "Decision", (
            f"Crown value must be 'Decision'. Got: {result.get('Crown')!r}"
        )

    def test_05b_scan_trailers_memory_returns_crown_memo(self):
        """scan_trailers_memory returns Crown: Memo when that trailer is present.

        STATUS: RED — same root cause as test_05.
        """
        from parsing import scan_trailers_memory
        body = "Memo: preference - async everywhere\nCrown: Memo"
        result = scan_trailers_memory(body)
        assert "Crown" in result
        assert result["Crown"] == "Memo"

    def test_05c_scan_trailers_memory_returns_crown_remember(self):
        """scan_trailers_memory returns Crown: Remember when that trailer is present.

        STATUS: RED — same root cause as test_05.
        """
        from parsing import scan_trailers_memory
        body = "Remember: user - prefers Spanish\nCrown: Remember"
        result = scan_trailers_memory(body)
        assert "Crown" in result
        assert result["Crown"] == "Remember"

    def test_05d_scan_trailers_memory_no_crown_when_absent(self):
        """scan_trailers_memory does not inject Crown when the trailer is absent.

        STATUS: GREEN [GUARD] — already correct; must remain passing after change.
        """
        from parsing import scan_trailers_memory
        body = "Decision: use JWT for auth"
        result = scan_trailers_memory(body)
        assert "Crown" not in result, (
            "Crown must not appear when the trailer is missing"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — extract_memory() 3-tuple contract
# ══════════════════════════════════════════════════════════════════════════════

class TestExtractMemoryCrownTuple:
    """extract_memory() must return (label, text, is_crown) 3-tuples."""

    def test_06_extract_memory_crowned_decision_is_crown_true(self, tmp_path):
        """A decision commit with Crown: Decision yields is_crown=True in the tuple.

        STATUS: RED — extract_memory returns 2-tuples (label, text) today.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(auth): use JWT",
                "Decision: JWT over sessions\nCrown: Decision")

        result = _extract_memory(repo)
        decisions = result["decisions"]
        assert decisions, "Expected at least one decision"

        # Each entry must be a 3-element list: [label, text, is_crown]
        first = decisions[0]
        assert len(first) == 3, (
            f"extract_memory decisions must be 3-tuples [label, text, is_crown]. "
            f"Got {len(first)}-element tuple: {first}"
        )
        label, text, is_crown = first
        assert is_crown is True, (
            f"is_crown must be True for commit with Crown: Decision. "
            f"Got is_crown={is_crown!r}, label={label!r}, text={text!r}"
        )

    def test_06b_extract_memory_non_crowned_decision_is_crown_false(self, tmp_path):
        """A decision commit WITHOUT Crown: Decision yields is_crown=False.

        STATUS: RED — extract_memory returns 2-tuples today.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(auth): use JWT",
                "Decision: JWT over sessions")

        result = _extract_memory(repo)
        decisions = result["decisions"]
        assert decisions, "Expected at least one decision"

        first = decisions[0]
        assert len(first) == 3, (
            f"extract_memory decisions must be 3-tuples. Got {len(first)}-tuple: {first}"
        )
        _, _, is_crown = first
        assert is_crown is False, (
            f"is_crown must be False when Crown trailer is absent. Got: {is_crown!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Crown kind-specificity contract
# ══════════════════════════════════════════════════════════════════════════════

class TestCrownKindSpecificity:
    """Crown: Decision does not crown a Memo of the same scope, and vice versa."""

    def test_07_crown_decision_does_not_crown_memo(self, tmp_path):
        """Crown: Decision on a decision commit must NOT set is_crown on a memo of the same scope.

        Setup: decision(api) with Crown: Decision + memo(api) without Crown.
        Expected: decision is_crown=True, memo is_crown=False.

        STATUS: RED — extract_memory returns 2-tuples; is_crown field absent.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(api): use REST",
                "Decision: REST over GraphQL\nCrown: Decision")
        _commit(repo,
                "📌 memo(api): async preference",
                "Memo: preference - async/await everywhere")

        result = _extract_memory(repo)

        # Decision must be crowned
        decisions = result["decisions"]
        assert decisions, "Expected at least one decision"
        dec = decisions[0]
        assert len(dec) == 3, f"Expected 3-tuple, got: {dec}"
        assert dec[2] is True, f"Decision must be crowned. Got: {dec}"

        # Memo must NOT be crowned
        memos = result["memos"]
        assert memos, "Expected at least one memo"
        memo = memos[0]
        assert len(memo) == 3, f"Expected 3-tuple, got: {memo}"
        assert memo[2] is False, (
            f"Crown: Decision must NOT crown a Memo of the same scope. "
            f"Memo is_crown={memo[2]!r}"
        )

    def test_07b_crown_memo_does_not_crown_decision(self, tmp_path):
        """Crown: Memo on a memo commit must NOT set is_crown on the decision of the same scope.

        STATUS: RED — same root cause.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(api): use REST",
                "Decision: REST over GraphQL")
        _commit(repo,
                "📌 memo(api): async preference",
                "Memo: preference - async/await everywhere\nCrown: Memo")

        result = _extract_memory(repo)

        # Memo must be crowned
        memos = result["memos"]
        assert memos, "Expected at least one memo"
        memo = memos[0]
        assert len(memo) == 3, f"Expected 3-tuple: {memo}"
        assert memo[2] is True, f"Memo must be crowned. Got: {memo}"

        # Decision must NOT be crowned
        decisions = result["decisions"]
        assert decisions, "Expected at least one decision"
        dec = decisions[0]
        assert len(dec) == 3, f"Expected 3-tuple: {dec}"
        assert dec[2] is False, (
            f"Crown: Memo must NOT crown the decision. "
            f"Decision is_crown={dec[2]!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Boot display contracts
# ══════════════════════════════════════════════════════════════════════════════

class TestCrownBootDisplay:
    """Crowned entries appear FIRST with 👑 prefix in the DECISIONS section."""

    def test_08_crowned_decision_shows_crown_emoji_and_appears_first(self, tmp_path):
        """A crowned decision appears before non-crowned decisions with 👑 prefix.

        Setup:
          - decision(db): use postgres       ← no Crown
          - decision(auth): use JWT          ← Crown: Decision  (crowned)

        Expected in DECISIONS output:
          - 👑 line for (auth) appears at a smaller position than (db) line
          - Line contains '👑'

        STATUS: RED — boot renders all decisions the same way today.
        """
        repo = _make_installed_repo(tmp_path)

        # Older commit (will be lower in git log)
        _commit(repo,
                "🧭 decision(db): use postgres",
                "Decision: postgres over mysql")
        # Newer commit, crowned
        _commit(repo,
                "🧭 decision(auth): use JWT",
                "Decision: JWT over sessions\nCrown: Decision")

        _run_boot(repo)
        content = _read_boot_log(repo)

        assert "DECISIONS:" in content, "DECISIONS section must be present"

        decisions_start = content.find("DECISIONS:")
        decisions_block = content[decisions_start:]

        # 👑 must appear in the decisions block
        assert "👑" in decisions_block, (
            "Crowned decision must display with 👑 prefix in DECISIONS section. "
            f"DECISIONS block:\n{decisions_block[:400]}"
        )

        # 👑 line must come before the non-crowned line
        crown_pos = decisions_block.find("👑")
        postgres_pos = decisions_block.find("postgres")
        assert crown_pos < postgres_pos, (
            f"Crowned entry (pos {crown_pos}) must appear before non-crowned "
            f"entry (pos {postgres_pos}) in DECISIONS block"
        )

    def test_09_crowned_memo_shows_crown_emoji_and_appears_first(self, tmp_path):
        """Crown: Memo renders 👑 prefix and appears first in MEMOS section.

        STATUS: RED — boot renders all memos the same way today.
        """
        repo = _make_installed_repo(tmp_path)

        _commit(repo,
                "📌 memo(db): use indexes",
                "Memo: preference - always add indexes on foreign keys")
        _commit(repo,
                "📌 memo(api): async preference",
                "Memo: preference - async/await everywhere\nCrown: Memo")

        _run_boot(repo)
        content = _read_boot_log(repo)

        assert "MEMOS:" in content, "MEMOS section must be present"

        memos_start = content.find("MEMOS:")
        memos_block = content[memos_start:]

        assert "👑" in memos_block, (
            "Crowned memo must display with 👑 prefix in MEMOS section. "
            f"MEMOS block:\n{memos_block[:400]}"
        )

        crown_pos = memos_block.find("👑")
        indexes_pos = memos_block.find("indexes")
        assert crown_pos < indexes_pos, (
            f"Crowned memo (pos {crown_pos}) must appear before non-crowned "
            f"memo (pos {indexes_pos}) in MEMOS block"
        )

    def test_10_crowned_remember_shows_crown_emoji_and_appears_first(self, tmp_path):
        """Crown: Remember renders 👑 prefix and appears first in REMEMBER section.

        STATUS: RED — boot renders all remembers the same way today.
        """
        repo = _make_installed_repo(tmp_path)

        _commit(repo,
                "🧠 remember(user): uses dark mode",
                "Remember: user - prefers dark mode always")
        _commit(repo,
                "🧠 remember(user): prefers Spanish",
                "Remember: user - prefiere respuestas en español\nCrown: Remember")

        _run_boot(repo)
        content = _read_boot_log(repo)

        assert "REMEMBER:" in content, "REMEMBER section must be present"

        remember_start = content.find("REMEMBER:")
        remember_block = content[remember_start:]

        assert "👑" in remember_block, (
            "Crowned remember must display with 👑 prefix in REMEMBER section. "
            f"REMEMBER block:\n{remember_block[:400]}"
        )

        crown_pos = remember_block.find("👑")
        dark_pos = remember_block.find("dark mode")
        assert crown_pos < dark_pos, (
            f"Crowned remember (pos {crown_pos}) must appear before non-crowned "
            f"remember (pos {dark_pos}) in REMEMBER block"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Crown does not consume the normal budget
# ══════════════════════════════════════════════════════════════════════════════

class TestCrownDoesNotConsumeBudget:
    """Crowned entries are displayed in ADDITION to the BOOT_MAX_* normal entries."""

    def test_11_crowned_decision_visible_even_when_budget_full(self, tmp_path):
        """With BOOT_MAX_DECISIONS non-crowned decisions + 1 crowned, the crowned one is visible.

        The crown entry must appear BEYOND the normal cap, not instead of one.

        Setup:
          - 20 non-crowned decisions (fills BOOT_MAX_DECISIONS = 20)
          - 1 crowned decision

        Expected: the crowned decision STILL appears in the DECISIONS section
        output, even though the budget of 20 is already full.

        STATUS: RED — Crown is not implemented; budget logic does not exist yet.
        """
        repo = _make_installed_repo(tmp_path)

        # Fill the normal budget (BOOT_MAX_DECISIONS = 20 from the hook)
        # We commit the crowned one FIRST (oldest), so without Crown-override
        # it would be pushed out by the newer non-crowned ones.
        _commit(repo,
                "🧭 decision(crown/target): crowned canonical",
                "Decision: this is the crowned canonical entry\nCrown: Decision")

        # Now flood with 20 non-crowned decisions (newer = higher priority in log)
        for i in range(20):
            _commit(repo,
                    f"🧭 decision(scope{i:02d}): filler {i}",
                    f"Decision: filler decision number {i} for budget test")

        _run_boot(repo)
        content = _read_boot_log(repo)

        assert "DECISIONS:" in content, "DECISIONS section must be present"
        assert "crowned canonical" in content, (
            "Crowned decision must appear even when normal budget (20) is full. "
            "The crown entry must not be displaced by non-crowned entries. "
            f"DECISIONS block (first 600 chars):\n"
            f"{content[content.find('DECISIONS:'):content.find('DECISIONS:')+600]}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — Glossary cache roundtrip with schema_version
# ══════════════════════════════════════════════════════════════════════════════

class TestGlossaryCacheWithCrown:
    """Crowned entries survive cache write+read; old 2-tuple cache triggers regeneration."""

    def test_12_crowned_entry_survives_cache_roundtrip(self, tmp_path):
        """A crowned decision written to the glossary cache is read back with is_crown=True.

        Requires:
          - _write_glossary_cache stores the is_crown field
          - _read_glossary_cache restores it
          - Cache JSON has a 'schema_version' key so old caches can be detected

        STATUS: RED — cache writes 2-tuples today; no schema_version field.
        """
        repo = _make_installed_repo(tmp_path)

        # Commit a crowned decision (goes into glossary)
        _commit(repo,
                "🧭 decision(arch): use microservices",
                "Decision: microservices over monolith\nCrown: Decision")

        # Boot once to populate the cache
        _run_boot(repo)

        # Read the cache file directly
        cache_path = os.path.join(repo, ".claude", ".unmassk", "glossary-cache.json")
        assert os.path.isfile(cache_path), "Glossary cache must be created by boot"

        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)

        # schema_version must be present
        assert "schema_version" in cache, (
            "Glossary cache must contain 'schema_version' key for format evolution. "
            f"Cache keys found: {list(cache.keys())}"
        )

        # decisions in cache must be 3-element lists [label, text, is_crown]
        decisions_in_cache = cache.get("decisions", [])
        assert decisions_in_cache, "Expected at least one decision in cache"
        first = decisions_in_cache[0]
        assert len(first) == 3, (
            f"Cache decisions must be 3-element lists [label, text, is_crown]. "
            f"Got {len(first)}-element: {first}"
        )
        _, _, is_crown = first
        assert is_crown is True, (
            f"Crowned decision must survive cache roundtrip with is_crown=True. "
            f"Got is_crown={is_crown!r}"
        )

    def test_12b_old_two_tuple_cache_triggers_regeneration(self, tmp_path):
        """A cache file with 2-tuple decisions (no schema_version) is discarded and regenerated.

        The regenerated cache must have schema_version and 3-tuples.

        STATUS: RED — no schema_version check exists today.
        """
        repo = _make_installed_repo(tmp_path)
        _commit(repo,
                "🧭 decision(db): use postgres",
                "Decision: postgres over mysql\nCrown: Decision")

        # First boot to create the cache
        _run_boot(repo)

        cache_path = os.path.join(repo, ".claude", ".unmassk", "glossary-cache.json")
        assert os.path.isfile(cache_path)

        # Simulate old 2-tuple cache (no schema_version)
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)

        # Downgrade: remove schema_version and convert decisions to 2-tuples
        cache.pop("schema_version", None)
        cache["decisions"] = [[d[0], d[1]] for d in cache.get("decisions", [])]
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f)

        # Boot again: must detect stale format and regenerate
        _run_boot(repo)

        with open(cache_path, encoding="utf-8") as f:
            refreshed = json.load(f)

        assert "schema_version" in refreshed, (
            "Regenerated cache must have schema_version. "
            "Old 2-tuple cache must have been discarded and rewritten."
        )

        decisions = refreshed.get("decisions", [])
        assert decisions, "Expected decisions in refreshed cache"
        first = decisions[0]
        assert len(first) == 3, (
            f"Refreshed cache decisions must be 3-tuples. Got {len(first)}-tuple: {first}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — Glossary crown beats recent non-crowned at same scope
# ══════════════════════════════════════════════════════════════════════════════

class TestCrownGlossaryWinsOverRecent:
    """A crowned glossary entry wins over a non-crowned recent entry at the same scope."""

    def test_13_crowned_glossary_entry_shown_over_non_crowned_recent(self, tmp_path):
        """When a crowned entry is outside the recent window and a non-crowned entry
        exists for the same scope within the recent window, the crowned entry wins.

        Setup:
          1. Commit a crowned decision(auth) deep in history (outside SCAN_DEPTH=30)
          2. Pad with 35 non-memory commits to push it outside the recent window
          3. Commit a non-crowned decision(auth) — this is NOW in the recent window

        Expected:
          - The boot output shows 👑 (the crowned one), not the non-crowned one
          - Crowned entry wins the scope deduplication even when it is older

        STATUS: RED — scope deduplication today is first-seen-wins (most recent);
                 no Crown-aware deduplication exists.
        """
        repo = _make_installed_repo(tmp_path)

        # 1. The crowned entry — must be outside the recent window
        _commit(repo,
                "🧭 decision(auth): use JWT canonical",
                "Decision: JWT is the canonical auth method\nCrown: Decision")

        # 2. Pad with 35 commits to push the crowned one outside SCAN_DEPTH=30
        for i in range(35):
            _commit(repo, f"feat(pad): padding commit {i:03d}")

        # 3. Non-crowned recent entry for the same scope
        _commit(repo,
                "🧭 decision(auth): experiment with sessions",
                "Decision: experiment with session-based auth")

        _run_boot(repo)
        content = _read_boot_log(repo)

        assert "DECISIONS:" in content, "DECISIONS section must be present"

        decisions_start = content.find("DECISIONS:")
        decisions_block = content[decisions_start:decisions_start + 800]

        # The crowned entry must appear (either directly or via glossary merge)
        assert "👑" in decisions_block, (
            "Crowned glossary entry must win over non-crowned recent entry at same scope. "
            f"DECISIONS block:\n{decisions_block}"
        )

        assert "canonical" in decisions_block, (
            "The crowned decision text ('canonical') must appear in output, "
            "not the non-crowned 'experiment' entry. "
            f"DECISIONS block:\n{decisions_block}"
        )

        assert "experiment" not in decisions_block, (
            "The non-crowned recent entry ('experiment') must NOT appear when "
            "a crowned entry exists for the same scope. "
            f"DECISIONS block:\n{decisions_block}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — Invariante de Oro: crowned Decision is never tombstoned
# ══════════════════════════════════════════════════════════════════════════════

class TestCrownGoldenInvariant:
    """A crowned Decision must not be suppressed by any tombstone trailer."""

    def test_14_crowned_decision_not_tombstoned_by_resolved_memo(self, tmp_path):
        """A crowned Decision with matching text in Resolved-Memo must still appear.

        This is the INVARIANTE DE ORO applied to crowned entries specifically.
        Decisions are already exempt from tombstoning in the existing code;
        this test confirms that the Crown path does not accidentally re-enable it.

        STATUS: GREEN [GUARD] for the no-tombstone rule (already in place for
                all decisions). RED for the Crown display (👑 not rendered yet).
        """
        repo = _make_installed_repo(tmp_path)

        _commit(repo,
                "🧭 decision(auth): use JWT",
                "Decision: JWT over sessions is the canonical choice\nCrown: Decision")

        # GC commit: try to tombstone the same text via Resolved-Memo
        _commit(repo,
                "♻️ chore(gc): gc old memo",
                "Resolved-Memo: JWT over sessions is the canonical choice")

        _run_boot(repo)
        content = _read_boot_log(repo)

        assert "DECISIONS:" in content
        decisions_start = content.find("DECISIONS:")
        decisions_block = content[decisions_start:decisions_start + 600]

        # The decision must still appear (tombstone does not apply to decisions)
        assert "JWT" in decisions_block, (
            "Crowned Decision must survive Resolved-Memo tombstone attempt. "
            "Decisions are NEVER tombstoned. "
            f"DECISIONS block:\n{decisions_block}"
        )

        # And it must be crowned (this is the RED part)
        assert "👑" in decisions_block, (
            "Crowned Decision that survived tombstone must display with 👑. "
            f"DECISIONS block:\n{decisions_block}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — Regression: non-crowned entries unaffected
# ══════════════════════════════════════════════════════════════════════════════

class TestCrownRegressionNonCrowned:
    """Non-crowned entries render exactly as today — Crown introduction must not break them."""

    def test_15_non_crowned_entries_render_as_before(self, tmp_path):
        """A repo with no Crown trailers produces DECISIONS/MEMOS/REMEMBER as before.

        This test mirrors test_boot_output.py::TestBootSections to ensure we
        have not broken normal boot output.

        STATUS: GREEN [GUARD] — must stay passing throughout implementation.
        """
        repo = _make_installed_repo(tmp_path)

        output = _run_boot(repo)
        content = _read_boot_log(repo)

        # Core sections present: STATUS/BRANCH/BOOT COMPLETE stay on the
        # short stdout banner; RESUME/REMEMBER/DECISIONS are heavy content
        # and live only in the boot-log file (contract correction, Bex
        # 2026-07-04: the banner is unconditional for any repo size).
        assert "STATUS:" in output
        assert "BRANCH:" in output
        assert "BOOT COMPLETE" in output
        assert "RESUME:" in content
        assert "REMEMBER:" in content
        assert "DECISIONS:" in content

        # No spurious 👑 in the log file (no crowned entries exist)
        # Check only the memory sections to avoid false positives from other content
        decisions_start = content.find("DECISIONS:")
        remember_start = content.find("REMEMBER:")

        for section_name, start in [
            ("DECISIONS", decisions_start),
            ("REMEMBER", remember_start),
        ]:
            if start != -1:
                # Find the next section boundary
                section_block = content[start:start + 300]
                assert "👑" not in section_block, (
                    f"👑 must not appear in {section_name} section when no Crown "
                    f"trailer is present. Section block:\n{section_block}"
                )

        # Existing content is rendered (in the boot-log file, where the memory
        # sections live)
        assert "JWT" in content or "async/await" in content or "español" in content, (
            "At least one memory entry from the installed repo must appear in the boot log file"
        )

        # Section order is preserved in the log file (it carries every section,
        # unlike the short stdout banner)
        positions = []
        for marker in ["STATUS:", "BRANCH:", "RESUME:", "REMEMBER:", "DECISIONS:", "BOOT COMPLETE"]:
            pos = content.find(marker)
            if pos != -1:
                positions.append(pos)
        assert positions == sorted(positions), (
            f"Section order must be preserved. Positions: {positions}"
        )
