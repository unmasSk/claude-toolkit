"""
Tests for recall.py — the git-memory search engine.

Covers:
- Basic matching returns relevant entries
- No false positives for unrelated queries
- Rare-term ranking: rare token outranks common token
- Deduplication: repeated entries appear once
- Tombstone exclusion
- Scope filtering via --scope flag
"""

import os
import sys

import pytest

from conftest import (
    SOURCE_ROOT, BIN_DIR,
    git_cmd, run_script, write_file,
)

# Make lib/ importable so we can call recall() directly as a unit test.
LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

RECALL_BIN = os.path.join(BIN_DIR, "git-memory-recall.py")


# ── Helpers ────────────────────────────────────────────────────────────

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


def recall_in(repo, query, limit=8, scope=None):
    """Call recall() with _repo_dir set to the test repo."""
    from recall import recall
    return recall(query, limit=limit, scope=scope, _repo_dir=repo)


def run_cli(repo, query, extra_args=None):
    """Run git-memory-recall.py CLI from test repo dir."""
    args = [query] + (extra_args or [])
    rc, stdout, stderr = run_script(RECALL_BIN, repo, args)
    return rc, stdout, stderr


# ── Tests: basic matching ───────────────────────────────────────────────

class TestBasicMatch:
    def test_returns_relevant_decision(self, tmp_path):
        """recall('memoria') returns entries from plugin/memory scope."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(plugin/memory): use file-based memory",
                "Decision: usar archivos markdown para memoria persistente")
        _commit(repo,
                "🧭 decision(plugin/recall): recall engine",
                "Decision: BM25 para ranking de memoria en recall")

        result = recall_in(repo, "memoria")
        assert result, "Expected results for 'memoria' query"
        assert "plugin/memory" in result or "plugin/recall" in result

    def test_returns_memo(self, tmp_path):
        repo = _make_repo(tmp_path)
        _commit(repo,
                "📌 memo(plugin/memory): stack note",
                "Memo: preference - mantener memoria en markdown")
        result = recall_in(repo, "memoria markdown")
        assert result
        assert "MEMOS" in result

    def test_returns_remember(self, tmp_path):
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧠 remember(user): language preference",
                "Remember: usuario prefiere respuestas en español siempre")
        result = recall_in(repo, "español preferencia usuario")
        assert result
        assert "REMEMBER" in result

    def test_multiple_types_grouped(self, tmp_path):
        """Entries from different types appear under their section headers."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(plugin/graph): graph layout",
                "Decision: usar fuerza dirigida para visualización de grafo")
        _commit(repo,
                "📌 memo(plugin/graph): graph stack",
                "Memo: stack - d3.js para visualización grafo")
        result = recall_in(repo, "grafo visualización")
        assert result
        assert "DECISIONES" in result
        assert "MEMOS" in result


# ── Tests: no false positives ──────────────────────────────────────────

class TestNoFalsePositives:
    def test_unrelated_query_returns_empty(self, tmp_path):
        """recall('github') on a repo with no github-related memory → empty."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(plugin/memory): memory format",
                "Decision: usar markdown para ficheros de memoria")
        _commit(repo,
                "📌 memo(plugin/recall): recall design",
                "Memo: preference - BM25 ranking para recall engine")
        result = recall_in(repo, "github")
        assert result == "", f"Expected empty string, got: {repr(result)}"

    def test_empty_repo_returns_empty(self, tmp_path):
        repo = _make_repo(tmp_path)
        result = recall_in(repo, "memoria")
        assert result == ""

    def test_stopwords_only_query_returns_empty(self, tmp_path):
        """Query consisting only of stopwords has no tokens — returns empty."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(auth): jwt",
                "Decision: use jwt for auth")
        # "the and for" are all stopwords — _tokenize returns empty set
        result = recall_in(repo, "the and for")
        assert result == ""


# ── Tests: ranking (rare term > common term) ───────────────────────────

class TestRanking:
    def test_rare_term_outranks_common_term(self, tmp_path):
        """
        Entry with a rare relevant token ranks above entry with only a
        common token that appears everywhere.

        Setup:
          - 10 entries all containing "commit" (common)
          - 1 entry also containing "xyzquux" (unique/rare)
        Query: "commit xyzquux"
        Expectation: the rare entry appears first in the output.
        """
        repo = _make_repo(tmp_path)

        # Flood corpus with "commit" (common token)
        for i in range(10):
            _commit(repo,
                    f"🧭 decision(plugin/scope{i}): decision {i}",
                    f"Decision: commit workflow pattern {i}")

        # One entry with both "commit" AND the rare token "xyzquux"
        _commit(repo,
                "🧭 decision(plugin/rare): rare entry",
                "Decision: commit with xyzquux special marker")

        result = recall_in(repo, "commit xyzquux", limit=12)
        assert result, "Expected results"
        lines = result.splitlines()
        # Find the line with "xyzquux" and verify it appears before a
        # line that only has "commit" (no xyzquux)
        rare_pos = next(
            (i for i, line in enumerate(lines) if "xyzquux" in line), None
        )
        common_pos = next(
            (i for i, line in enumerate(lines) if "xyzquux" not in line and "commit" in line.lower()), None
        )
        assert rare_pos is not None, "Rare entry not found in output"
        assert common_pos is not None, "Common entry not found in output"
        assert rare_pos < common_pos, (
            f"Rare entry (pos {rare_pos}) should rank before common entry (pos {common_pos})"
        )


# ── Tests: deduplication ───────────────────────────────────────────────

class TestDeduplication:
    def test_same_text_three_times_appears_once(self, tmp_path):
        """Three commits with identical Decision text → output has it once."""
        repo = _make_repo(tmp_path)
        text = "Decision: usar BM25 para memoria recall engine"
        for i in range(3):
            _commit(repo,
                    f"🧭 decision(plugin/recall): dedup test {i}",
                    text)

        result = recall_in(repo, "BM25 memoria recall")
        assert result
        # Count occurrences of the distinctive phrase
        count = result.count("BM25 para memoria recall engine")
        assert count == 1, f"Expected 1 occurrence, got {count}"

    def test_near_duplicate_via_normalize(self, tmp_path):
        """Texts that differ only in whitespace/case are deduplicated."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(plugin/a): first",
                "Decision: usar  BM25  para memoria")
        _commit(repo,
                "🧭 decision(plugin/b): second",
                "Decision: usar BM25 para memoria")

        result = recall_in(repo, "BM25 memoria")
        assert result
        # normalize() collapses whitespace, so both produce same norm
        count = result.count("BM25")
        assert count == 1, f"Expected 1 after dedup, got {count}"


# ── Tests: tombstone exclusion ─────────────────────────────────────────

class TestTombstones:
    def test_decisions_never_tombstoned(self, tmp_path):
        """Decisions are never excluded by tombstones (matches extract_memory behavior).

        Even when a Resolved-Remember or Resolved-Memo key has the same text,
        the Decision entry still appears. Only Memos and Remembers are tombstoned.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(plugin/auth): auth decision",
                "Decision: usar tokens JWT para autenticacion")
        # GC commit with same text as the Decision — should NOT suppress it
        _commit(repo,
                "♻️ chore(plugin/auth): gc",
                "Resolved-Memo: usar tokens JWT para autenticacion")

        result = recall_in(repo, "JWT autenticacion")
        assert result, "Decision should survive tombstone with same text"
        assert "JWT" in result

    def test_resolved_remember_tombstone_excludes_remember(self, tmp_path):
        """Remember entry with matching Resolved-Remember tombstone is excluded."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧠 remember(user): language",
                "Remember: usuario prefiere respuestas en español siempre")
        _commit(repo,
                "♻️ chore(gc): gc remember",
                "Resolved-Remember: usuario prefiere respuestas en español siempre")

        result = recall_in(repo, "español respuestas usuario")
        assert result == "", f"Tombstoned entry should not appear, got: {repr(result)}"

    def test_resolved_memo_tombstone_excludes_memo(self, tmp_path):
        """Memo entry with matching Resolved-Memo tombstone is excluded."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "📌 memo(plugin/stack): stack",
                "Memo: preference - usar TypeScript estricto siempre")
        _commit(repo,
                "♻️ chore(gc): gc memo",
                "Resolved-Memo: preference - usar TypeScript estricto siempre")

        result = recall_in(repo, "TypeScript estricto")
        assert result == "", f"Tombstoned memo should not appear, got: {repr(result)}"


# ── Tests: scope filtering ─────────────────────────────────────────────

class TestScopeFilter:
    def test_scope_filters_to_matching_entries(self, tmp_path):
        """--scope plugin/recall only returns entries from that scope prefix."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(plugin/recall): recall design",
                "Decision: BM25 para ranking de memoria")
        _commit(repo,
                "🧭 decision(plugin/graph): graph layout",
                "Decision: fuerza dirigida para grafo de memoria")

        result = recall_in(repo, "memoria", scope="plugin/recall")
        assert result
        assert "plugin/recall" in result
        assert "plugin/graph" not in result

    def test_scope_prefix_matches_child_scopes(self, tmp_path):
        """scope='plugin' matches 'plugin/recall' and 'plugin/memory'."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(plugin/recall): recall",
                "Decision: BM25 ranking para recall de memoria")
        _commit(repo,
                "🧭 decision(plugin/memory): memory",
                "Decision: markdown files para memoria persistente")
        _commit(repo,
                "🧭 decision(auth): auth",
                "Decision: JWT tokens para autenticacion")

        result = recall_in(repo, "memoria", scope="plugin")
        assert result
        assert "plugin/recall" in result or "plugin/memory" in result
        assert "auth" not in result

    def test_scope_no_match_returns_empty(self, tmp_path):
        """scope filter with no matching entries → empty string."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(plugin/recall): recall",
                "Decision: BM25 para memoria recall")

        result = recall_in(repo, "memoria", scope="plugin/graph")
        assert result == ""


# ── Tests: CLI ─────────────────────────────────────────────────────────

class TestCLI:
    def test_cli_basic_query(self, tmp_path):
        """CLI returns output and exit code 0 when matches exist."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(plugin/recall): engine",
                "Decision: BM25 para recall de memoria")

        rc, stdout, _ = run_cli(repo, "BM25 memoria")
        assert rc == 0
        assert "BM25" in stdout

    def test_cli_no_match_prints_no_matches(self, tmp_path):
        """CLI prints '(no matches)' and exits 0 when nothing found."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(plugin/recall): engine",
                "Decision: BM25 para recall de memoria")

        rc, stdout, _ = run_cli(repo, "github")
        assert rc == 0
        assert "(no matches)" in stdout

    def test_cli_scope_flag(self, tmp_path):
        """CLI --scope flag filters correctly."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "🧭 decision(plugin/recall): recall",
                "Decision: BM25 para memoria recall")
        _commit(repo,
                "🧭 decision(plugin/graph): graph",
                "Decision: grafo para memoria visual")

        rc, stdout, _ = run_cli(repo, "memoria", ["--scope", "plugin/recall"])
        assert rc == 0
        assert "plugin/recall" in stdout
        assert "plugin/graph" not in stdout

    def test_cli_limit_flag(self, tmp_path):
        """CLI --limit caps the number of results."""
        repo = _make_repo(tmp_path)
        for i in range(5):
            _commit(repo,
                    f"🧭 decision(plugin/scope{i}): decision {i}",
                    f"Decision: memoria entry {i} recall BM25 ranking")

        rc, stdout, _ = run_cli(repo, "memoria recall BM25", ["--limit", "2"])
        assert rc == 0
        # Each result line starts with "  (" — count those
        result_lines = [line for line in stdout.splitlines() if line.startswith("  (")]
        assert len(result_lines) <= 2, f"Expected at most 2 results, got {len(result_lines)}"


# ── Tests: empty corpus ────────────────────────────────────────────────

class TestEmptyCorpus:
    def test_repo_with_no_memory_commits_returns_empty(self, tmp_path):
        """A repo that has commits but zero memory trailers returns empty string.

        This is distinct from test_empty_repo_returns_empty (which has only
        the init commit). Here we add non-memory commits to confirm the corpus
        has entries in git log but _scan_commits returns [].
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "feat(auth): add login endpoint")
        _commit(repo, "fix(auth): handle null token")
        _commit(repo, "docs(readme): update installation steps")

        result = recall_in(repo, "autenticacion login")
        assert result == "", f"Expected empty string with no memory commits, got: {repr(result)}"

    def test_repo_only_tombstone_commits_returns_empty(self, tmp_path):
        """A repo whose only memory-like commits are tombstone GC commits returns empty.

        There are no Decision/Memo/Remember entries — only Resolved-* trailers.
        recall() must return '' because there is nothing to surface.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "chore(gc): remove stale remember",
                "Resolved-Remember: usuario prefiere respuestas en español siempre")

        result = recall_in(repo, "español respuestas usuario")
        assert result == "", f"Expected empty string, got: {repr(result)}"


# ── Tests: malformed trailers ──────────────────────────────────────────

class TestMalformedTrailers:
    def test_trailer_without_colon_is_ignored(self, tmp_path):
        """A line that looks like a trailer but lacks ': ' is not parsed.

        'Decision usar markdown para memoria' has no colon-space — it must not
        produce a match even when the query contains matching tokens.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/memory): memory format",
                "Decision usar markdown para memoria persistente")

        result = recall_in(repo, "memoria markdown persistente")
        assert result == "", f"Malformed trailer should yield no entry, got: {repr(result)}"

    def test_trailer_with_lowercase_key_is_ignored(self, tmp_path):
        """Trailer keys are case-sensitive. 'decision: ...' (lowercase) is not parsed.

        scan_trailers_memory regex requires [A-Z][a-z]+ pattern — a fully
        lowercase key must be silently skipped.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/memory): memory format",
                "decision: usar markdown para memoria persistente")

        result = recall_in(repo, "memoria markdown persistente")
        assert result == "", f"Lowercase trailer key should be ignored, got: {repr(result)}"

    def test_trailer_with_injection_chars_sanitized(self, tmp_path):
        """_sanitize() strips newline and HTML-comment injection from trailer values.

        The entry must still appear in results (text is sanitized, not dropped),
        but the output must not contain the raw injection characters.
        """
        repo = _make_repo(tmp_path)
        # Use a real trailer key but embed injection chars in the value.
        # _sanitize() is called on the raw trailer value before storing.
        _commit(repo,
                "remember(user): inject test",
                "Remember: usuario prefiere markdown<!--injected-->para notas")

        result = recall_in(repo, "usuario prefiere markdown notas")
        # The entry must appear (trailer is valid)
        assert result, "Expected entry to appear after sanitization"
        # The raw injection markers must be stripped
        assert "<!--" not in result, "HTML comment opener must be stripped by _sanitize"
        assert "-->" not in result, "HTML comment closer must be stripped by _sanitize"

    def test_trailer_with_newline_escape_sanitized(self, tmp_path):
        r"""_sanitize() replaces \n and \r with spaces in trailer values.

        This test exercises the path where scan_trailers_memory returns a value
        containing literal backslash-n (from parsing) — the sanitized output
        must have a space instead.
        """
        # We can test _sanitize() directly as a unit test since it is module-level.
        from recall import _sanitize
        raw = "use BM25\nfor recall\r\nengine"
        sanitized = _sanitize(raw)
        assert "\n" not in sanitized, "Newline must be stripped"
        assert "\r" not in sanitized, "Carriage return must be stripped"
        # Content is preserved (as spaces)
        assert "BM25" in sanitized
        assert "recall" in sanitized

    def test_body_with_no_trailer_block_returns_empty(self, tmp_path):
        """A commit body that is pure prose with no trailer lines produces no entries."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "docs(readme): update usage section",
                "This commit updates the readme with usage examples for recall.\n"
                "No trailer lines here at all.")

        result = recall_in(repo, "readme usage examples recall")
        assert result == "", f"Expected empty without trailers, got: {repr(result)}"


# ── Tests: unicode / non-ASCII scopes ─────────────────────────────────

class TestUnicodeScopes:
    def test_unicode_scope_is_parsed_and_matched(self, tmp_path):
        """Scope containing accented characters is correctly parsed by parse_scope.

        'feat(área/técnico): ...' has a scope 'área/técnico'. The entry must
        appear in results and its label must reflect the unicode scope.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(área/técnico): soporte unicode",
                "Decision: usar codificacion UTF-8 para soporte unicode completo")

        result = recall_in(repo, "UTF-8 unicode codificacion")
        assert result, "Expected result for entry with unicode scope"
        assert "UTF-8" in result or "unicode" in result or "área" in result

    def test_unicode_tokens_in_text_are_matched(self, tmp_path):
        """_tokenize() includes accented word tokens (regex [a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]{3,}).

        A query containing accented terms must match an entry whose trailer
        value also contains those accented terms.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "remember(user): idioma",
                "Remember: usuario prefiere comunicación en español siempre")

        result = recall_in(repo, "comunicación español")
        assert result, "Expected match on accented tokens"
        assert "REMEMBER" in result

    def test_scope_filter_case_insensitive(self, tmp_path):
        """Scope filter comparison is case-insensitive.

        An entry with scope 'Plugin/Recall' must be returned when filtering
        with scope='plugin/recall' (lowercase).
        """
        repo = _make_repo(tmp_path)
        # parse_scope extracts whatever is in the parens literally.
        # The filter does .lower() on both sides, so case should not matter.
        _commit(repo,
                "decision(Plugin/Recall): recall design",
                "Decision: BM25 para ranking de memoria recall")
        _commit(repo,
                "decision(auth): auth design",
                "Decision: JWT para autenticacion")

        result = recall_in(repo, "memoria BM25 recall", scope="plugin/recall")
        assert result, "Expected match with case-insensitive scope filter"
        assert "BM25" in result
        assert "JWT" not in result

    def test_scope_filter_non_ascii_prefix(self, tmp_path):
        """Scope filter works when the prefix itself contains non-ASCII characters."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(área/técnico): soporte",
                "Decision: soporte técnico completo para usuarios internacionales")
        _commit(repo,
                "decision(auth): auth",
                "Decision: JWT para autenticacion")

        result = recall_in(repo, "soporte técnico usuarios", scope="área")
        assert result, "Expected match with non-ASCII scope prefix"
        assert "técnico" in result or "soporte" in result
        assert "JWT" not in result


# ── Tests: ranking ties ────────────────────────────────────────────────

class TestRankingTies:
    def test_tied_entries_both_appear_in_output(self, tmp_path):
        """Two entries with identical IDF scores both appear in the output.

        Setup: two entries each containing the same unique token once.
        Their scores are equal (both rare, both appear in 1 of 2 entries).
        Both must be present in the output — ties must not drop either entry.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/alpha): alpha decision",
                "Decision: usar xyzalpha para configuracion especial")
        _commit(repo,
                "decision(plugin/beta): beta decision",
                "Decision: usar xyzbeta para configuracion especial")

        # Query includes a shared token ("configuracion") and each entry's
        # unique token — but the unique tokens are not in the other entry,
        # so IDF scores for "configuracion" (df=2, appears in both) are equal.
        result = recall_in(repo, "configuracion especial", limit=8)
        assert result, "Expected results for common token query"
        # Both entries must appear — ties preserve all entries up to limit
        assert "xyzalpha" in result, "First tied entry must appear"
        assert "xyzbeta" in result, "Second tied entry must appear"

    def test_limit_applied_after_tie_sort(self, tmp_path):
        """When limit=1 and all entries are tied, exactly 1 entry is returned.

        Confirms the cap-to-limit logic applies correctly on a fully tied set.
        """
        repo = _make_repo(tmp_path)
        for i in range(4):
            _commit(repo,
                    f"decision(plugin/s{i}): decision {i}",
                    f"Decision: configuracion especial para modulo {i}")

        result = recall_in(repo, "configuracion especial modulo", limit=1)
        assert result, "Expected at least one result"
        result_lines = [l for l in result.splitlines() if l.startswith("  (")]
        assert len(result_lines) == 1, (
            f"limit=1 must return exactly 1 entry, got {len(result_lines)}"
        )


# ── Tests: tombstone two-pass non-obvious ordering ─────────────────────

class TestTombstoneTwoPassOrdering:
    def test_gc_commit_before_target_in_log_still_tombstones(self, tmp_path):
        """GC commit appears FIRST in git log (newest commit) — target appears SECOND.

        git log is newest-first. The GC commit is committed AFTER the memory
        entry, so it appears at log position 0 while the original entry is at
        position 1. Without the two-pass approach, a single-pass scan would
        process the original entry BEFORE seeing the tombstone, and would include
        it erroneously.

        The two-pass implementation in _scan_commits() collects ALL tombstone
        keys in the first pass, then filters entries in the second pass. This
        test confirms that ordering in the log does not affect correctness.
        """
        repo = _make_repo(tmp_path)
        # Commit 1 (older, appears LATER in git log): the memory entry
        _commit(repo,
                "remember(user): language pref",
                "Remember: usuario prefiere respuestas en español siempre")
        # Commit 2 (newer, appears FIRST in git log): the GC tombstone
        _commit(repo,
                "chore(gc): resolve remember",
                "Resolved-Remember: usuario prefiere respuestas en español siempre")

        result = recall_in(repo, "español respuestas usuario")
        assert result == "", (
            "GC tombstone (log pos 0) must suppress original entry (log pos 1); "
            f"got: {repr(result)}"
        )

    def test_stale_blocker_tombstone_key(self, tmp_path):
        """Stale-Blocker is a valid tombstone key that suppresses Memo entries.

        Stale-Blocker is in _TOMBSTONE_KEYS. A Memo whose normalized text
        matches a Stale-Blocker trailer value must be excluded from results.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "memo(plugin/deploy): blocker note",
                "Memo: stack - deployment pipeline bloqueado por certificado expirado")
        _commit(repo,
                "chore(gc): resolve blocker",
                "Stale-Blocker: stack - deployment pipeline bloqueado por certificado expirado")

        result = recall_in(repo, "deployment pipeline certificado bloqueado")
        assert result == "", (
            "Stale-Blocker tombstone must suppress matching Memo; "
            f"got: {repr(result)}"
        )

    def test_resolved_next_tombstone_does_not_suppress_decision(self, tmp_path):
        """Resolved-Next is in _TOMBSTONE_KEYS but Decisions are never tombstoned.

        Even when a Resolved-Next trailer has the same text as a Decision entry,
        the Decision must still appear. Only Memo and Remember are suppressible.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/deploy): deploy strategy",
                "Decision: usar blue-green deployment para zero downtime")
        _commit(repo,
                "chore(gc): resolve next",
                "Resolved-Next: usar blue-green deployment para zero downtime")

        result = recall_in(repo, "blue-green deployment downtime")
        assert result, "Decision must not be suppressed by Resolved-Next tombstone"
        assert "blue-green" in result or "deployment" in result

    def test_multiple_tombstones_collected_in_one_pass(self, tmp_path):
        """A single GC commit can carry multiple tombstone trailers.

        Both Resolved-Memo and Resolved-Remember in the same commit body
        must both be collected in the first pass, suppressing their respective
        entries in the second pass.
        """
        repo = _make_repo(tmp_path)
        _commit(repo,
                "remember(user): language",
                "Remember: usuario prefiere respuestas en español siempre")
        _commit(repo,
                "memo(plugin/stack): stack",
                "Memo: preference - usar TypeScript estricto siempre")
        # Single GC commit resolves both
        _commit(repo,
                "chore(gc): batch gc",
                "Resolved-Remember: usuario prefiere respuestas en español siempre\n"
                "Resolved-Memo: preference - usar TypeScript estricto siempre")

        result_remember = recall_in(repo, "español respuestas usuario")
        assert result_remember == "", (
            "Remember suppressed by batch GC commit; "
            f"got: {repr(result_remember)}"
        )
        result_memo = recall_in(repo, "TypeScript estricto")
        assert result_memo == "", (
            "Memo suppressed by batch GC commit; "
            f"got: {repr(result_memo)}"
        )


# ── Tests: scope-only vs text-only match ──────────────────────────────

class TestScopeVsTextMatch:
    def test_scope_only_match_scores_nonzero(self, tmp_path):
        """An entry whose text has no query tokens but scope does still scores > 0.

        Query token appears in the scope but NOT in the trailer text body.
        The entry must appear in results because _idf_score() checks both
        entry_tokens and scope_tokens.
        """
        repo = _make_repo(tmp_path)
        # Scope contains "recall"; text contains completely unrelated words
        _commit(repo,
                "decision(plugin/recall): design decision",
                "Decision: arquitectura modular para separacion responsabilidades")

        # Query: "recall" — only in scope, not in text
        result = recall_in(repo, "recall")
        assert result, (
            "Entry whose scope contains the query token must appear in results; "
            f"scope-only match returned empty"
        )

    def test_text_only_match_scores_nonzero(self, tmp_path):
        """An entry whose scope has no query tokens but text does still scores > 0.

        Query token appears in the trailer text but NOT in the scope string.
        """
        repo = _make_repo(tmp_path)
        # Scope is generic "config"; text contains "xyzrare"
        _commit(repo,
                "decision(config): some decision",
                "Decision: usar xyzrare pattern para manejo configuracion")

        # Query: "xyzrare" — only in text, not in scope
        result = recall_in(repo, "xyzrare")
        assert result, (
            "Entry whose text contains the query token must appear in results; "
            f"text-only match returned empty"
        )

    def test_scope_match_outranks_text_only_match(self, tmp_path):
        """Scope match (1.5x multiplier) outranks text-only match for same rare token.

        Setup: two entries both containing unique token "xyzsignal".
        Entry A: token appears in scope.
        Entry B: token appears only in text.
        Entry A must rank first because scope gets a 1.5x multiplier.
        """
        repo = _make_repo(tmp_path)
        # Entry B: token in text only (committed first = older, lower in log)
        _commit(repo,
                "decision(plugin/generic): generic",
                "Decision: xyzsignal aparece solo en texto para prueba ranking")
        # Entry A: token in scope (committed second = newer, higher in log)
        _commit(repo,
                "decision(plugin/xyzsignal): scope match",
                "Decision: arquitectura para separacion responsabilidades modulo")

        result = recall_in(repo, "xyzsignal", limit=8)
        assert result, "Expected results"
        lines = result.splitlines()
        scope_pos = next(
            (i for i, l in enumerate(lines) if "xyzsignal" in l and "scope match" in l.lower()),
            None,
        )
        text_pos = next(
            (i for i, l in enumerate(lines) if "xyzsignal" in l and "texto" in l.lower()),
            None,
        )
        # If both appear, scope entry must come first
        if scope_pos is not None and text_pos is not None:
            assert scope_pos < text_pos, (
                f"Scope match (pos {scope_pos}) must outrank text-only match "
                f"(pos {text_pos}) due to 1.5x multiplier"
            )


# ── Tests: limit boundary ──────────────────────────────────────────────

class TestLimitBoundary:
    def test_limit_one_returns_exactly_one_entry(self, tmp_path):
        """limit=1 returns exactly one result even when many entries match."""
        repo = _make_repo(tmp_path)
        for i in range(6):
            _commit(repo,
                    f"decision(plugin/s{i}): decision {i}",
                    f"Decision: memoria recall BM25 entry {i} importante")

        result = recall_in(repo, "memoria recall BM25 importante", limit=1)
        assert result, "Expected one result"
        result_lines = [l for l in result.splitlines() if l.startswith("  (")]
        assert len(result_lines) == 1, (
            f"limit=1 must return exactly 1 entry, got {len(result_lines)}"
        )

    def test_limit_below_one_clamped_to_one(self, tmp_path):
        """recall() with limit=0 or limit=-1 is clamped to 1 by the guard.

        Source: `if limit < 1: limit = 1` at the top of recall().
        """
        repo = _make_repo(tmp_path)
        for i in range(4):
            _commit(repo,
                    f"decision(plugin/s{i}): decision {i}",
                    f"Decision: memoria recall BM25 entry {i}")

        result_zero = recall_in(repo, "memoria recall BM25", limit=0)
        result_neg = recall_in(repo, "memoria recall BM25", limit=-5)

        for label, result in [("limit=0", result_zero), ("limit=-5", result_neg)]:
            assert result, f"{label}: expected at least one result after clamp"
            result_lines = [l for l in result.splitlines() if l.startswith("  (")]
            assert len(result_lines) == 1, (
                f"{label} clamped to 1 — expected 1 result line, got {len(result_lines)}"
            )

    def test_limit_larger_than_corpus(self, tmp_path):
        """limit > corpus size returns all matching entries (no crash, no padding)."""
        repo = _make_repo(tmp_path)
        for i in range(3):
            _commit(repo,
                    f"decision(plugin/s{i}): decision {i}",
                    f"Decision: memoria recall BM25 entry {i}")

        result = recall_in(repo, "memoria recall BM25", limit=100)
        assert result, "Expected results"
        result_lines = [l for l in result.splitlines() if l.startswith("  (")]
        assert len(result_lines) == 3, (
            f"Expected all 3 entries, got {len(result_lines)}"
        )


# ── Tests: deduplication (3+ copies) ──────────────────────────────────

class TestDeduplicationExtended:
    def test_five_identical_copies_appear_once(self, tmp_path):
        """Five commits with identical Decision text produce exactly one output line."""
        repo = _make_repo(tmp_path)
        text = "Decision: usar BM25 ranking para memoria recall engine exacto"
        for i in range(5):
            _commit(repo,
                    f"decision(plugin/recall): dedup {i}",
                    text)

        result = recall_in(repo, "BM25 ranking memoria recall exacto")
        assert result
        count = result.count("BM25 ranking para memoria recall engine exacto")
        assert count == 1, f"Expected 1 occurrence after dedup, got {count}"

    def test_dedup_per_kind_not_across_kinds(self, tmp_path):
        """Same normalized text in both Decision and Remember creates two entries.

        Deduplication is scoped per kind (seen_norms is keyed by kind).
        The same text appearing as both a Decision and a Remember must produce
        two separate output lines, one under DECISIONES and one under REMEMBER.
        """
        repo = _make_repo(tmp_path)
        shared_text = "usar markdown para memoria persistente xyzunique"
        _commit(repo,
                "decision(plugin/memory): memory",
                f"Decision: {shared_text}")
        _commit(repo,
                "remember(user): memory note",
                f"Remember: {shared_text}")

        result = recall_in(repo, "markdown memoria persistente xyzunique")
        assert result, "Expected entries from both kinds"
        assert "DECISIONES" in result, "Expected Decision section"
        assert "REMEMBER" in result, "Expected Remember section"
        # Both entries must be present (dedup does not cross kind boundaries)
        count = result.count("xyzunique")
        assert count == 2, (
            f"Same text in two different kinds must appear twice, got {count}"
        )


# ── Tests: alphanumeric tokenizer (Moriarty #1) ────────────────────────

class TestAlphanumericTokenizer:
    """_tokenize must handle tokens that contain digits: BM25, v2, RS256, auth3."""

    def test_query_bm25_finds_entry(self, tmp_path):
        """Query 'BM25' returns an entry whose trailer contains 'BM25'."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/recall): ranking algorithm",
                "Decision: usar BM25 para ranking de memoria en recall")

        result = recall_in(repo, "BM25")
        assert result, "Expected result for query 'BM25'"
        assert "BM25" in result

    def test_query_v2_finds_entry(self, tmp_path):
        """Query 'v2' returns an entry whose trailer contains 'v2'."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/api): version",
                "Decision: migrar a API v2 para nueva interfaz")

        result = recall_in(repo, "v2")
        assert result, "Expected result for query 'v2'"
        assert "v2" in result

    def test_query_rs256_finds_entry(self, tmp_path):
        """Query 'RS256' returns an entry whose trailer contains 'RS256'."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(auth): jwt algorithm",
                "Decision: usar RS256 para firma de tokens JWT")

        result = recall_in(repo, "RS256")
        assert result, "Expected result for query 'RS256'"
        assert "RS256" in result

    def test_pure_digits_not_tokenized(self, tmp_path):
        """Pure digit sequences like '123' are not valid tokens (no letter)."""
        from recall import _tokenize
        tokens = _tokenize("error 123 found")
        assert "123" not in tokens, "Pure digit sequences must not be tokenized"
        assert "error" in tokens

    def test_alphanumeric_mixed_token_preserved(self, tmp_path):
        """Mixed alphanumeric tokens like 'auth3' and 'p256' are tokenized."""
        from recall import _tokenize
        tokens = _tokenize("auth3 algorithm p256 curve")
        assert "auth3" in tokens, "auth3 must be tokenized (has a letter)"
        assert "p256" in tokens, "p256 must be tokenized (has a letter)"


# ── Tests: full history horizon (Moriarty #2) ──────────────────────────

class TestFullHistoryHorizon:
    """_scan_commits scans all history — no silent truncation at a fixed depth."""

    def test_entry_beyond_500_commits_is_found(self, tmp_path):
        """An entry committed 510 commits ago must still be found (no SCAN_DEPTH cap)."""
        repo = _make_repo(tmp_path)

        # Add the memory entry first (will be deep in history after padding)
        _commit(repo,
                "decision(plugin/horizon): deep memory",
                "Decision: usar xyzdeephorizon para memoria profunda")

        # Pad with 510 non-memory commits to push the memory entry beyond any 500-cap
        for i in range(510):
            _commit(repo, f"feat(pad): padding commit {i}")

        result = recall_in(repo, "xyzdeephorizon")
        assert result, (
            "Entry committed 510 commits ago must be found — "
            "recall must scan full history, not just last 500"
        )
        assert "xyzdeephorizon" in result


# ── Tests: tombstone with HTML comment in value (Moriarty #3) ─────────

class TestTombstoneWithHTMLComment:
    """Tombstone must match even when value contains '<!--' characters."""

    def test_tombstone_with_html_comment_suppresses_entry(self, tmp_path):
        """A Remember entry containing '<!--' is tombstoned when Resolved-Remember
        has the same raw value (sanitize applied consistently on both paths).
        """
        repo = _make_repo(tmp_path)
        # Entry with injection chars in the value
        raw_value = "usuario prefiere<!--injected-->markdown para notas"
        _commit(repo,
                "remember(user): inject test",
                f"Remember: {raw_value}")
        # Tombstone uses the same raw value
        _commit(repo,
                "chore(gc): resolve remember",
                f"Resolved-Remember: {raw_value}")

        result = recall_in(repo, "usuario prefiere markdown notas")
        assert result == "", (
            "Remember with '<!--' in value must be tombstoned when Resolved-Remember "
            f"has the same text; got: {repr(result)}"
        )


# ── Tests: Unicode line terminators in _sanitize (Argus #4) ───────────

class TestUnicodeLineTerminators:
    """_sanitize must strip U+2028 and U+2029 (Unicode line/paragraph separators)."""

    def test_sanitize_strips_unicode_line_separator(self, tmp_path):
        """_sanitize replaces U+2028 (LINE SEPARATOR) with a space."""
        from recall import _sanitize
        raw = "use BM25 for recall engine"
        sanitized = _sanitize(raw)
        assert " " not in sanitized, "U+2028 must be stripped by _sanitize"
        assert "BM25" in sanitized
        assert "recall" in sanitized

    def test_sanitize_strips_unicode_paragraph_separator(self, tmp_path):
        """_sanitize replaces U+2029 (PARAGRAPH SEPARATOR) with a space."""
        from recall import _sanitize
        raw = "use BM25 for recall engine"
        sanitized = _sanitize(raw)
        assert " " not in sanitized, "U+2029 must be stripped by _sanitize"

    def test_sanitize_strips_vertical_tab(self, tmp_path):
        """_sanitize replaces \\x0b (vertical tab) with a space."""
        from recall import _sanitize
        raw = "use BM25\x0bfor recall"
        sanitized = _sanitize(raw)
        assert "\x0b" not in sanitized, "\\x0b must be stripped by _sanitize"

    def test_sanitize_strips_form_feed(self, tmp_path):
        """_sanitize replaces \\x0c (form feed) with a space."""
        from recall import _sanitize
        raw = "use BM25\x0cfor recall"
        sanitized = _sanitize(raw)
        assert "\x0c" not in sanitized, "\\x0c must be stripped by _sanitize"


# ── Tests: query length cap (Argus #5) ────────────────────────────────

class TestQueryLengthCap:
    """recall() must cap query at MAX_QUERY_LEN before processing."""

    def test_oversized_query_does_not_crash(self, tmp_path):
        """A query longer than MAX_QUERY_LEN must not raise an exception."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/recall): ranking",
                "Decision: usar BM25 para memoria recall")

        from recall import MAX_QUERY_LEN
        huge_query = "BM25 " * (MAX_QUERY_LEN // 4)
        assert len(huge_query) > MAX_QUERY_LEN

        # Must not raise; result can be empty or non-empty
        try:
            result = recall_in(repo, huge_query)
        except Exception as exc:
            pytest.fail(f"Oversized query raised exception: {exc}")

    def test_query_exactly_at_max_len_is_accepted(self, tmp_path):
        """A query of exactly MAX_QUERY_LEN characters must be processed normally."""
        from recall import MAX_QUERY_LEN
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/recall): ranking",
                "Decision: usar BM25 para memoria recall")

        # Build a query of exactly MAX_QUERY_LEN that contains "BM25"
        filler = "memoria " * (MAX_QUERY_LEN // 8)
        query = ("BM25 " + filler)[:MAX_QUERY_LEN]
        result = recall_in(repo, query)
        assert result, "Query at MAX_QUERY_LEN must still find matching entries"


# ── Tests: empty query guard (Cerberus #9) ────────────────────────────

class TestEmptyQueryGuard:
    """recall() returns '' immediately for blank/whitespace-only queries."""

    def test_empty_string_returns_empty(self, tmp_path):
        """recall('') returns empty string without hitting git."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/recall): ranking",
                "Decision: usar BM25 para memoria recall")
        result = recall_in(repo, "")
        assert result == "", f"Empty query must return '', got: {repr(result)}"

    def test_whitespace_only_returns_empty(self, tmp_path):
        """recall('   ') (spaces only) returns empty string."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/recall): ranking",
                "Decision: usar BM25 para memoria recall")
        result = recall_in(repo, "   ")
        assert result == "", f"Whitespace query must return '', got: {repr(result)}"

    def test_tab_newline_only_returns_empty(self, tmp_path):
        """recall('\\t\\n') returns empty string."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/recall): ranking",
                "Decision: usar BM25 para memoria recall")
        result = recall_in(repo, "\t\n")
        assert result == "", f"Whitespace-only query must return '', got: {repr(result)}"


# ── Tests: CLI --limit 0 (Nitpick #14) ───────────────────────────────

class TestCLILimitZero:
    """CLI rejects --limit 0; library clamps it to 1.

    The divergence is intentional and documented in the CLI docstring:
    - CLI: strict (user-facing), rejects < 1 with exit code 1.
    - recall(): lenient (programmatic), clamps < 1 to 1.
    """

    def test_cli_limit_zero_exits_error(self, tmp_path):
        """CLI --limit 0 exits with code 1 and prints error to stderr."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/recall): ranking",
                "Decision: usar BM25 para memoria recall")

        rc, stdout, stderr = run_cli(repo, "BM25 memoria", ["--limit", "0"])
        assert rc == 1, f"Expected exit code 1 for --limit 0, got {rc}"
        assert "limit" in stderr.lower() or "error" in stderr.lower(), (
            f"Expected error message in stderr, got: {repr(stderr)}"
        )

    def test_cli_limit_negative_exits_error(self, tmp_path):
        """CLI --limit -1 exits with code 1."""
        repo = _make_repo(tmp_path)
        _commit(repo,
                "decision(plugin/recall): ranking",
                "Decision: usar BM25 para memoria recall")

        rc, stdout, stderr = run_cli(repo, "BM25 memoria", ["--limit", "-1"])
        assert rc == 1, f"Expected exit code 1 for --limit -1, got {rc}"

    def test_lib_limit_zero_clamped_to_one(self, tmp_path):
        """recall(limit=0) is clamped to 1 — returns exactly one result."""
        repo = _make_repo(tmp_path)
        for i in range(3):
            _commit(repo,
                    f"decision(plugin/s{i}): decision {i}",
                    f"Decision: BM25 memoria recall entry {i}")

        result = recall_in(repo, "BM25 memoria recall", limit=0)
        assert result, "limit=0 clamped to 1 must return one result"
        result_lines = [line for line in result.splitlines() if line.startswith("  (")]
        assert len(result_lines) == 1, (
            f"limit=0 clamped to 1 must return exactly 1 entry, got {len(result_lines)}"
        )
