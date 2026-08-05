"""
Shared constants for unmassk-toolkit hooks and CLI scripts.

Single source of truth for trailer keys and commit types.
Imported everywhere.
"""

# Trailer keys (case-sensitive, matching the spec)
VALID_KEYS: set[str] = {
    "Issue", "Why", "Decision", "Memo", "Next",
    "Blocker",
    "Remember",  # Personality/working-style notes between sessions
}

# Commit types that require code trailers (Why)
CODE_TYPES: set[str] = {"feat", "fix", "refactor", "perf", "chore", "ci", "test", "docs"}

# Commit types that are memory-only (allow-empty)
MEMORY_TYPES: set[str] = {"context", "decision", "memo", "remember"}

# Default Co-Author line appended to every commit.
# Override via GIT_MEMORY_CO_AUTHOR environment variable.
DEFAULT_CO_AUTHOR: str = "Co-Authored-By: Claude, empowered by unmasSk-toolkit"
