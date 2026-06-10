#!/usr/bin/env python3
"""PreToolUse hook: lexical dedup gate for git-memory memo/remember commits.

Purpose
-------
Intercepts Bash commands that invoke git-memory-commit.py with type ``memo``
or ``remember``.  Extracts the trailer text, computes Jaccard overlap against
existing entries of the SAME type in git memory, and:

- Near-duplicate (Jaccard >= DEDUP_THRESHOLD) → allow + permissionDecisionReason
  naming the matching existing entry.
- No near-duplicate → allow, no reason.
- Any error / non-memo-remember command → fail-open, allow, no reason.

The hook NEVER emits permissionDecision: "deny".
The hook ALWAYS exits 0.

Metric choice: Jaccard (intersection / union)
---------------------------------------------
We use Jaccard rather than the overlap coefficient (intersection / min(|A|, |B|))
because the boundary case (Case 3 in the test suite) involves memos with
substantially different lengths.  With the overlap coefficient, a short entry
that is a semantic subset of a longer one scores high even when they mean
opposite things.  Jaccard penalizes both entries for tokens the other does NOT
have, making it more robust against asymmetric-length pairs.

Stopword strategy for Jaccard dedup
-------------------------------------
recall.py's _tokenize() is calibrated for BM25 ranking: it only removes
high-frequency function words that carry no topic signal for IDF scoring.
For Jaccard dedup we need a stricter filter: words like "usar", "no",
"porque", "en" appear in nearly every memo regardless of topic.  When left
in, they inflate the intersection between memos that discuss different topics
in a similar syntactic frame (e.g. "usar X porque Y no escala" vs
"usar Y porque X no permite Z").

This hook defines its own _dedup_tokenize() that adds these high-frequency
content-neutral words to the stopword list.  The recall.py stoplist is NOT
modified — its calibration for BM25 is independent of our needs here.

Threshold calibration: DEDUP_THRESHOLD = 0.40
----------------------------------------------
Scores computed on tokens after _dedup_tokenize() (including the "preference - "
category prefix that git-memory-commit.py prepends to Memo entries):

  - Paraphrase pair (Case 2): Jaccard ≈ 0.44  → warns  (above 0.40) ✓
  - Boundary pair   (Case 3): Jaccard ≈ 0.33  → silent (below 0.40) ✓

Gap between the two cases is ~0.11, giving comfortable margin on both sides.
NOTE: calibrated on a small synthetic corpus; if the real-world corpus shifts
the distribution, re-evaluate the threshold — the tests are the contract, not
this constant.

Fail-open posture (CRITICAL)
-----------------------------
Any failure — JSON parse error, missing git, recall scan exception, regex error,
or any other exception — is swallowed and results in an unconditional allow with
no reason.  A broken dedup gate must NEVER paralyse the orchestrator.

I/O contract (Claude Code PreToolUse hook)
------------------------------------------
- Stdin:  JSON {"tool_name": str, "tool_input": {"command": str}}
- Stdout: JSON {"hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    ["permissionDecisionReason": str]  ← only when near-dup found
                }}
- Exit 0 always.
"""

import json
import os
import re
import sys
import traceback

# ── Path setup — lib/ must be importable ────────────────────────────────

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(os.path.dirname(_HOOKS_DIR), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from recall import _scan_commits  # noqa: E402  (import after sys.path mutation)

# ── Threshold ────────────────────────────────────────────────────────────

# Jaccard similarity threshold for near-duplicate detection.
# See module docstring for calibration rationale.
DEDUP_THRESHOLD: float = 0.40

# ── Dedup-specific tokenization ──────────────────────────────────────────
#
# Extended stopword list for Jaccard dedup.  Words below are syntactic
# fillers that appear in most memos regardless of topic.  Removing them
# prevents high intersection scores between memos with the same sentence
# *structure* but opposite *recommendations*.
#
# recall.py's _tokenize() intentionally keeps these words for BM25 IDF
# weighting (they carry signal for ranking by topic).  We diverge here
# intentionally — the use-cases are different.

_DEDUP_STOPWORDS: frozenset[str] = frozenset({
    # ── recall.py baseline (ES) ──────────────────────────────────────
    "para", "con", "por", "que", "los", "las", "del", "una", "sin",
    "son", "ser", "sus", "hay", "mas", "pero", "como", "todo",
    "cuando", "donde", "entre", "sobre", "cada", "esto", "esta", "ese", "esa",
    # ── recall.py baseline (EN) ──────────────────────────────────────
    "the", "and", "for", "from", "with", "that", "this", "not", "are", "was",
    "have", "has", "had", "its", "can", "will", "all", "but", "been", "use",
    "used", "via", "into", "over", "also", "each", "per", "any", "our", "you",
    "add", "new", "set", "run", "get", "put", "out", "off", "now", "one",
    # ── dedup-specific extras (ES verbs / particles) ─────────────────
    # These appear in most memos syntactically but carry no topic signal
    # for dedup purposes.  Their inclusion caused false positives on the
    # boundary pair (Case 3): "usar X porque Y no..." shares usar/porque/no
    # with "usar Y porque X no..." even though both memos recommend
    # completely different architectures.
    "usar", "no", "porque", "en", "ya", "al", "el", "lo", "le",
    "se", "su", "mi", "si", "ni", "oh",
    # ── dedup-specific extras (EN particles/auxiliaries) ─────────────
    "is", "it", "in", "at", "be", "do", "on", "an", "of", "to",
    "we", "so", "as", "by",
})


def _dedup_tokenize(text: str) -> set[str]:
    """Tokenize for Jaccard dedup: lowercase alphanumeric tokens >=2 chars
    with at least one letter, excluding the extended dedup stopword list.

    Uses the same regex as recall._tokenize() for consistency — only the
    stopword set differs.
    """
    return {
        w.lower()
        for w in re.findall(
            r"(?=[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9]*[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ])"
            r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9]{2,}",
            text,
        )
        if w.lower() not in _DEDUP_STOPWORDS
    }


# ── Passthrough regex — cheap pre-filter ─────────────────────────────────
#
# The hook fires on EVERY Bash command.  We skip git entirely unless the
# command looks like a git-memory-commit.py invocation for memo or remember.
# This keeps latency well under 10 ms for the 99% of commands that are not
# memory commits.

_COMMIT_PATTERN = re.compile(
    r"git-memory-commit\.py\s+(memo|remember)\b",
    re.IGNORECASE,
)

# Extracts the trailer value from  --trailer "Memo=..." or --trailer "Remember=..."
_TRAILER_PATTERN = re.compile(
    r'--trailer\s+"(?:Memo|Remember)=([^"]*)"',
    re.IGNORECASE,
)


# ── Output helpers ───────────────────────────────────────────────────────

def _allow_passthrough() -> None:
    """Emit a bare allow and exit 0."""
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        },
        sys.stdout,
    )
    sys.stdout.flush()


def _allow_with_warning(reason: str) -> None:
    """Emit allow + permissionDecisionReason (near-dup warning)."""
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.stdout.flush()


# ── Similarity ───────────────────────────────────────────────────────────

def _jaccard(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Jaccard similarity: |A ∩ B| / |A ∪ B|.  Returns 0.0 if both are empty."""
    if not tokens_a and not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        raw = sys.stdin.read()

        # --- Parse stdin ------------------------------------------------
        try:
            hook_input = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            _allow_passthrough()
            return

        # Require a dict (not list, not None, etc.)
        if not isinstance(hook_input, dict):
            _allow_passthrough()
            return

        # --- Tool filter ------------------------------------------------
        tool_name = hook_input.get("tool_name", "")
        if tool_name != "Bash":
            _allow_passthrough()
            return

        # --- Extract command --------------------------------------------
        tool_input = hook_input.get("tool_input")
        if not isinstance(tool_input, dict):
            _allow_passthrough()
            return

        command = tool_input.get("command", "") or ""
        if not isinstance(command, str) or not command.strip():
            _allow_passthrough()
            return

        # --- Cheap pre-filter (regex, no git) ---------------------------
        match = _COMMIT_PATTERN.search(command)
        if not match:
            _allow_passthrough()
            return

        commit_type = match.group(1).lower()  # "memo" or "remember"

        # --- Extract trailer text ---------------------------------------
        trailer_match = _TRAILER_PATTERN.search(command)
        if not trailer_match:
            _allow_passthrough()
            return

        incoming_text = trailer_match.group(1).strip()
        if not incoming_text:
            _allow_passthrough()
            return

        # --- Scan existing memory (same type only) ----------------------
        # _scan_commits() uses cwd when repo_dir=None, which is what we want
        # when running in a real project.  Tests override via chdir.
        try:
            all_entries = _scan_commits(repo_dir=None)
        except Exception:
            try:
                sys.stderr.write(traceback.format_exc())
            except Exception:
                pass
            _allow_passthrough()
            return

        # The kind field in entries uses title-case ("Memo", "Remember").
        target_kind = commit_type.capitalize()
        existing = [e for e in all_entries if e["kind"] == target_kind]

        if not existing:
            _allow_passthrough()
            return

        # --- Jaccard comparison ─────────────────────────────────────────
        incoming_tokens = _dedup_tokenize(incoming_text)
        if not incoming_tokens:
            _allow_passthrough()
            return

        best_score = 0.0
        best_entry = None

        for entry in existing:
            entry_tokens = _dedup_tokenize(entry["text"])
            score = _jaccard(incoming_tokens, entry_tokens)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score >= DEDUP_THRESHOLD and best_entry is not None:
            reason = (
                f"Near-duplicate detected (Jaccard={best_score:.2f} >= {DEDUP_THRESHOLD}). "
                f"Existing {target_kind}: {best_entry['text']!r}"
            )
            _allow_with_warning(reason)
            return

        _allow_passthrough()

    except Exception:
        # Fail-open: any unhandled error must not block execution.
        try:
            sys.stderr.write(traceback.format_exc())
        except Exception:
            pass
        try:
            _allow_passthrough()
        except Exception:
            pass


if __name__ == "__main__":
    main()
