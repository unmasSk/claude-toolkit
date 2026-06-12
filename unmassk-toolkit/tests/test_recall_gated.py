"""
Contract tests for recall_relevant() — written BEFORE implementation (test-first).

These tests define the "relevance gate": recall_relevant() only returns
a formatted block when entries score above the noise floor AND within the
top-fraction window. Otherwise it returns None.

All tests use the in-process pattern (_repo_dir=repo) — no subprocess, no
sys.modules stubs. Corpus control uses invented rare tokens ("zorblax",
"qwythen", etc.) so IDF ordering is unambiguous without relying on magic
score numbers.

Intended failure mode before implementation: ImportError / AttributeError
because recall_relevant does not exist yet. Fixture errors would indicate a
broken test setup — confirm that before reporting RED.
"""

import os
import sys

import pytest

from conftest import SOURCE_ROOT, git_cmd

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)


# ── Helpers (mirror test_recall.py) ────────────────────────────────────

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


def recall_relevant_in(repo, query, **kwargs):
    """Call recall_relevant() with _repo_dir set to the test repo."""
    from recall import recall_relevant
    return recall_relevant(query, _repo_dir=repo, **kwargs)


# ── Module-level constant import (verified at collection time) ─────────

def _get_constants():
    """Return (RECALL_MAX_RESULTS, RECALL_FLOOR, RECALL_TOP_FRACTION) from recall."""
    from recall import RECALL_MAX_RESULTS, RECALL_FLOOR, RECALL_TOP_FRACTION
    return RECALL_MAX_RESULTS, RECALL_FLOOR, RECALL_TOP_FRACTION


# ── Tests: constants exist ──────────────────────────────────────────────

class TestModuleConstants:
    """recall module must export the three gate constants."""

    def test_recall_max_results_exists_and_equals_3(self):
        """RECALL_MAX_RESULTS must be exported and equal 3."""
        from recall import RECALL_MAX_RESULTS
        assert RECALL_MAX_RESULTS == 3

    def test_recall_floor_exists_and_is_positive(self):
        """RECALL_FLOOR must be exported and > 0."""
        from recall import RECALL_FLOOR
        assert RECALL_FLOOR > 0

    def test_recall_top_fraction_exists_and_equals_0_5(self):
        """RECALL_TOP_FRACTION must be exported and equal 0.5."""
        from recall import RECALL_TOP_FRACTION
        assert RECALL_TOP_FRACTION == 0.5


# ── Tests: relevant → injects ──────────────────────────────────────────

class TestRelevantReturnsBlock:
    """When a query shares a distinctive token with a memory entry, the
    gate must return a non-None string containing that entry's text."""

    def test_rare_token_match_returns_string(self, tmp_path):
        """Query sharing rare token 'zorblax' with a Decision → returns block (not None)."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): rare token entry",
            "Decision: usar zorblax para configuracion especial del motor",
        )
        result = recall_relevant_in(repo, "zorblax")
        assert result is not None, "Expected a string block, got None"
        assert isinstance(result, str), f"Expected str, got {type(result)}"

    def test_result_contains_matched_entry_text(self, tmp_path):
        """The returned block must contain the text of the matched entry."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): zorblax design",
            "Decision: zorblax es el algoritmo elegido para ranking memoria",
        )
        result = recall_relevant_in(repo, "zorblax")
        assert result is not None
        assert "zorblax" in result, (
            f"Block must contain the matched entry text; got: {repr(result)}"
        )

    def test_result_shares_format_headers_with_recall(self, tmp_path):
        """Block format must match recall() section headers (DECISIONES / MEMOS / REMEMBER)."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): qwythen design",
            "Decision: qwythen token para ranking especial",
        )
        result = recall_relevant_in(repo, "qwythen")
        assert result is not None
        # recall() uses [DECISIONES] header for Decision entries
        assert "DECISIONES" in result, (
            f"Block must use [DECISIONES] header (same as recall()); got: {repr(result)}"
        )

    def test_memo_match_returns_memos_section(self, tmp_path):
        """A Memo entry match must produce a block with [MEMOS] header."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "memo(plugin/stack): zorblax memo",
            "Memo: zorblax es la preferencia para configuracion avanzada",
        )
        result = recall_relevant_in(repo, "zorblax")
        assert result is not None
        assert "MEMOS" in result

    def test_remember_match_returns_remember_section(self, tmp_path):
        """A Remember entry match must produce a block with [REMEMBER] header."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "remember(user): zorblax pref",
            "Remember: usuario prefiere zorblax para todas las operaciones",
        )
        result = recall_relevant_in(repo, "zorblax")
        assert result is not None
        assert "REMEMBER" in result


# ── Tests: irrelevant → None ────────────────────────────────────────────

class TestIrrelevantReturnsNone:
    """When the query has no real token overlap with the corpus, the gate
    must return None (not an empty string, not a block)."""

    def test_no_overlap_returns_none(self, tmp_path):
        """Query 'frobnicator' on a corpus with no such token → None."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/memory): memory format",
            "Decision: usar zorblax para ficheros de memoria persistente",
        )
        result = recall_relevant_in(repo, "frobnicator")
        assert result is None, (
            f"Query with zero overlap must return None, got: {repr(result)}"
        )

    def test_empty_corpus_returns_none(self, tmp_path):
        """Empty corpus → None (no entries to match against)."""
        repo = _make_repo(tmp_path)
        result = recall_relevant_in(repo, "zorblax")
        assert result is None, (
            f"Empty corpus must return None, got: {repr(result)}"
        )

    def test_stopwords_only_query_returns_none(self, tmp_path):
        """Query consisting only of stopwords tokenizes to empty set → None."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): zorblax",
            "Decision: usar zorblax para configuracion",
        )
        # "the and for" are EN stopwords — tokenize returns empty set
        result = recall_relevant_in(repo, "the and for")
        assert result is None, (
            f"Stopword-only query must return None, got: {repr(result)}"
        )


# ── Tests: top_fraction gate — weak match excluded ──────────────────────

class TestTopFractionGate:
    """Entry B with score < top_fraction * score(A) must be excluded from the
    block even when B has positive score.

    Uses a two-entry corpus:
      A — contains rare token 'zorblax' (high IDF, df=1)
      B — contains only common token 'config' (low IDF, df=N-1 where N>>1)
    Query: 'zorblax config'
    With top_fraction=0.5, B's score must fall below 0.5 * A's score.
    """

    def _build_two_entry_corpus(self, tmp_path):
        repo = _make_repo(tmp_path)
        # Flood corpus with 'config' so it becomes very common (low IDF)
        for i in range(8):
            _commit(
                repo,
                f"decision(plugin/scope{i}): generic {i}",
                f"Decision: configuracion del modulo {i} con config habitual",
            )
        # Entry A: has both zorblax (rare) AND config
        _commit(
            repo,
            "decision(plugin/rare): entry A",
            "Decision: zorblax config algoritmo especial para memoria",
        )
        # Entry B: has ONLY config (common) — NOT zorblax
        # (This is already covered by the flood commits above.)
        return repo

    def test_entry_a_included_entry_b_excluded_default_fraction(self, tmp_path):
        """With default top_fraction=0.5: entry A (zorblax) in block, flood entries out."""
        repo = self._build_two_entry_corpus(tmp_path)
        result = recall_relevant_in(repo, "zorblax config")
        assert result is not None, (
            "Entry A (zorblax) should clear the gate — result must not be None"
        )
        assert "zorblax" in result, "Entry A must be in the block"
        # Flood entries only have 'config' (low IDF) — they score << A
        # Count how many flood entries leaked through
        flood_lines = [
            line for line in result.splitlines()
            if "zorblax" not in line and "config" in line.lower() and line.startswith("  (")
        ]
        assert len(flood_lines) == 0, (
            f"Flood entries (config-only) must be excluded by top_fraction gate; "
            f"leaked lines: {flood_lines}"
        )

    def test_top_fraction_zero_admits_weak_entries(self, tmp_path):
        """top_fraction=0.0 disables the fraction gate — config-only entries admitted."""
        repo = self._build_two_entry_corpus(tmp_path)
        # With fraction=0.0 the threshold is 0 * max_score = 0, so all scored > 0
        # entries are admitted (up to max_results cap)
        result = recall_relevant_in(
            repo, "zorblax config", top_fraction=0.0, max_results=20
        )
        assert result is not None, "With top_fraction=0.0 at least one entry must match"
        # At least one config-only flood entry must now appear
        flood_lines = [
            line for line in result.splitlines()
            if "zorblax" not in line and "config" in line.lower() and line.startswith("  (")
        ]
        assert len(flood_lines) > 0, (
            "top_fraction=0.0 must admit config-only entries that were excluded at 0.5"
        )


# ── Tests: max_results cap ──────────────────────────────────────────────

class TestMaxResultsCap:
    """Even when many entries are strongly relevant, the block must contain
    at most RECALL_MAX_RESULTS entries."""

    def test_cap_at_max_results(self, tmp_path):
        """With 5 strongly relevant entries (all share rare token), block has ≤ 3."""
        repo = _make_repo(tmp_path)
        # Build 5 entries that ALL share the same rare token 'zorblax'
        for i in range(5):
            _commit(
                repo,
                f"decision(plugin/scope{i}): zorblax entry {i}",
                f"Decision: zorblax algoritmo especial modulo {i} memoria avanzada",
            )
        result = recall_relevant_in(repo, "zorblax")
        assert result is not None, "Expected at least one match"
        result_lines = [l for l in result.splitlines() if l.startswith("  (")]
        max_r, _, _ = _get_constants()
        assert len(result_lines) <= max_r, (
            f"Block must contain at most RECALL_MAX_RESULTS ({max_r}) entries, "
            f"got {len(result_lines)}"
        )

    def test_custom_max_results_overrides_default(self, tmp_path):
        """max_results=1 returns at most 1 entry even when many match."""
        repo = _make_repo(tmp_path)
        for i in range(4):
            _commit(
                repo,
                f"decision(plugin/s{i}): zorblax entry {i}",
                f"Decision: zorblax raro para modulo {i}",
            )
        result = recall_relevant_in(repo, "zorblax", max_results=1)
        assert result is not None
        result_lines = [l for l in result.splitlines() if l.startswith("  (")]
        assert len(result_lines) == 1, (
            f"max_results=1 must return exactly 1 entry, got {len(result_lines)}"
        )


# ── Tests: language-agnostic (numeric gate, not keyword gate) ──────────

class TestLanguageAgnostic:
    """The gate operates on IDF scores, not on keyword language detection.
    A query in English sharing a rare token with a Spanish memory must fire."""

    def test_english_query_matches_spanish_memory(self, tmp_path):
        """English query 'zorblax' matches memory entry written in Spanish."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): zorblax design",
            "Decision: zorblax es el algoritmo elegido para optimizacion memoria",
        )
        # Query is in English context but shares the rare token
        result = recall_relevant_in(repo, "using zorblax for memory optimization")
        assert result is not None, (
            "English query sharing a rare token with a Spanish memory must return a block"
        )
        assert "zorblax" in result

    def test_mixed_language_query_triggers_on_shared_rare_token(self, tmp_path):
        """Query mixing EN+ES with a rare token triggers the gate."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): qwythen algorithm",
            "Decision: qwythen seleccionado para el motor de busqueda memoria",
        )
        result = recall_relevant_in(repo, "qwythen algorithm selected motor")
        assert result is not None
        assert "qwythen" in result


# ── Tests: parameter semantics ──────────────────────────────────────────

class TestParameterSemantics:
    """Parameters must dominate behavior independent of corpus content."""

    def test_high_floor_returns_none_despite_overlap(self, tmp_path):
        """floor=999 is above any realistic IDF score → returns None even with overlap."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): zorblax",
            "Decision: zorblax algoritmo especial para memoria persistente",
        )
        result = recall_relevant_in(repo, "zorblax", floor=999.0)
        assert result is None, (
            f"floor=999 must suppress all entries (no realistic score that high); "
            f"got: {repr(result)}"
        )

    def test_floor_zero_and_fraction_zero_admits_any_positive_score(self, tmp_path):
        """floor=0 and top_fraction=0.0 — any positive-scoring entry is admitted."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): zorblax entry",
            "Decision: zorblax para configuracion del modulo de memoria",
        )
        result = recall_relevant_in(repo, "zorblax", floor=0.0, top_fraction=0.0)
        assert result is not None, (
            "floor=0 and top_fraction=0.0 must admit any positive-scoring entry"
        )

    def test_scope_parameter_still_filters(self, tmp_path):
        """scope= parameter filters entries as in recall() — gate still applies."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): zorblax recall",
            "Decision: zorblax para ranking en plugin recall",
        )
        _commit(
            repo,
            "decision(plugin/graph): zorblax graph",
            "Decision: zorblax para visualizacion en plugin graph",
        )
        result = recall_relevant_in(repo, "zorblax", scope="plugin/recall")
        assert result is not None
        assert "plugin/recall" in result
        assert "plugin/graph" not in result

    def test_scope_no_match_returns_none(self, tmp_path):
        """scope= that matches nothing → None (not empty string)."""
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "decision(plugin/recall): zorblax",
            "Decision: zorblax para memoria recall",
        )
        result = recall_relevant_in(repo, "zorblax", scope="plugin/nonexistent")
        assert result is None, (
            f"scope with no match must return None, got: {repr(result)}"
        )
