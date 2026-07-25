"""
Shared constants for unmassk-toolkit hooks and CLI scripts.

Single source of truth for trailer keys, commit types, risk levels,
and memo categories. Imported everywhere.
"""

# Trailer keys (case-sensitive, matching the spec)
VALID_KEYS: set[str] = {
    "Issue", "Why", "Touched", "Decision", "Memo", "Next",
    "Blocker", "Risk", "Conflict", "Resolution",
    "Remember",  # Personality/working-style notes between sessions
    "Crown",     # Modifier: marks the canonical entry for a memory kind
    "Retract-Crown",  # Modifier: retracts a crown by commit hash (not a tombstone)
    "Resolved-Next", "Stale-Blocker",  # GC tombstone trailers
    "Resolved-Memo", "Resolved-Remember",  # Memory GC tombstone trailers
}

# Memory-relevant trailer keys for scan_trailers_memory
MEMORY_KEYS: set[str] = {
    "Decision", "Memo", "Next", "Blocker", "Remember",
    "Crown", "Retract-Crown",
    "Resolved-Next", "Stale-Blocker",
    "Resolved-Memo", "Resolved-Remember",
}

# Tombstone trailer keys — entries whose values are resolved/excluded from recall.
# Single source of truth: used by recall.py and session-start-boot.py.
TOMBSTONE_KEYS: tuple[str, ...] = (
    "Resolved-Next", "Stale-Blocker", "Resolved-Memo", "Resolved-Remember",
)

# Recall trailer keys — the memory types surfaced by the recall engine.
# Single source of truth: used by recall.py and session-start-boot.py.
RECALL_KEYS: tuple[str, ...] = ("Decision", "Memo", "Remember")

# Risk levels for Risk: trailer
RISK_VALUES: set[str] = {"low", "medium", "high"}

# Memo categories for Memo: trailer (format: "category - description")
MEMO_CATEGORIES: set[str] = {"preference", "requirement", "antipattern", "stack", "deadend"}

# Remember categories for Remember: trailer (format: "category - description")
REMEMBER_CATEGORIES: set[str] = {"user", "claude"}

# Commit types that require code trailers (Why + Touched)
CODE_TYPES: set[str] = {"feat", "fix", "refactor", "perf", "chore", "ci", "test", "docs"}

# Commit types that are memory-only (allow-empty)
MEMORY_TYPES: set[str] = {"context", "decision", "memo", "remember"}

# Default Co-Author line appended to every commit.
# Override via GIT_MEMORY_CO_AUTHOR environment variable.
DEFAULT_CO_AUTHOR: str = "Co-Authored-By: Claude, empowered by unmasSk-toolkit"
