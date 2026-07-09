---
name: issue-57-output-saneo-round2d-contract-notes
description: Issue #57 round 2d (decision 0cef65c) — closing the OUTPUT-sanitization class (NEL fence-evasion, plain-text delimiter spoofing, raw trailer/subject reflection across 4 sites, splitlines inflation) — all RED, test-first
metadata:
  type: feedback
---

Extends [issue-57-root-fix-subject-vector-contract-notes](issue-57-root-fix-subject-vector-contract-notes.md).
That round closed *parsing* corruption (control bytes breaking field/record
boundaries). This round is a DIFFERENT class: fields already parse
correctly, but the SANITIZER has a gap, or a downstream site never calls it,
or uses a spoofable plain-text delimiter instead of a fenced marker. Added
to the SAME file (`tests/test_control_byte_injection.py`, now ~2900 lines),
PART L through Q. All 12 new RED + 11 new GUARD confirmed live before
writing a single assertion (2026-07-10) — none of this was reasoned about
from reading source alone.

## Bullet A — NEL (U+0085) evades `sanitize_trailer_value()`'s fence regex

`re.sub(r"[\r\n \x0b\x0c\x1b\x1c\x1d\x1e\x7f]", " ", text)` covers
\x1c/\x1d/\x1e (root-fix round) but not \x85 (NEL, Unicode "Next Line").
`</memory-data\x85>` survives byte-for-byte. Confirmed at THREE levels
(all RED): the sanitizer directly, a real `recall_relevant(query,
scope="i", _repo_dir=repo)` call (Moriarty's exact repro shape — scope
filter "i" just needs to prefix-match a real scope, doesn't need to be
special), and the real `hooks/user-prompt-memory-check.py` end-to-end
(stdout ends up with 2 regex matches for
`</memory-data[\x1c\x1d\x1e\x85]?>` instead of 1 — the genuine wrapper
close plus the forged one). Fix will just be adding `\x85` to the
character class; the 3-level test pyramid stays valid across the fix.

## Bullet B — precompact snapshot's delimiter is plain text, spoofable with ZERO control bytes (the most subtle one)

`format_snapshot()`'s header (`=== GIT MEMORY SNAPSHOT (pre-compact) ===`)
and footer (`=== END SNAPSHOT ===`) are ordinary printable strings.
`sanitize_trailer_value()` has no reason to touch them (no control bytes
involved at all), so a Decision trailer containing the literal footer text
reproduces it byte-for-byte inside the snapshot body — indistinguishable
from the real one. Confirmed live: the footer string appears TWICE in real
stdout from one hostile commit. **This is not a byte-sanitization fix** —
the eventual fix must neutralize the DELIMITER STRING wherever it appears
in trailer/subject content (same class of fix as the `</memory-data>`
substring-removal, applied to a different string). Test asserts
`stdout.count(delimiter) == 1`, which holds regardless of *how* Ultron
neutralizes it (escape, strip, replace) — don't assert on the neutralized
form itself, since that's an implementation choice Ultron hasn't made yet.

This directly satisfies bullet G's "test_drift.py's containment checks
give false confidence, should be uniqueness" concern — PART M's assertion
IS a uniqueness check (`.count() == 1`) against real hostile input, so
test_drift.py's own (weaker) checks don't need a separate edit in this
round; noted but deliberately not touched (Bex: not necessarily a
production test to fix here).

## Bullet C — pre/post-validate-commit-trailers.py reflect raw trailer/subject to stderr

Both hooks interpolate an invalid trailer's raw value into an f-string
(`Invalid Memo format: '{trailers['Memo']}'...` / `Memo: (invalid format
'{trailers['Memo']}')`) with **no** `sanitize_trailer_value()` call
anywhere in either file (confirmed via import list — neither hook imports
`parsing.sanitize_trailer_value` at all). pre-hook additionally reflects
the raw SUBJECT for a non-conventional-format commit
(`Subject: {subject}`).

**Gotcha reused from [unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md):**
`as_claude=True` never reaches trailer-format validation at all (blocked
earlier by the "use git-memory-commit.py" wrapper gate on a literal `git
commit` command) — every test here uses `as_claude=False` (human path).
That path always returns rc=0 regardless of errors, but it DOES print the
warning to stderr — that's the assertion surface, not rc.

Precise assertion pattern used (don't just assert "no \x1b anywhere" —
colors.py's OWN legitimate RED/YELLOW/RESET codes are also \x1b and would
make that assertion vacuously true-for-the-wrong-reason): assert the
literal fence substring `</memory-data>` is absent (colors.py never emits
that text), and separately assert the attacker's OWN distinctive ANSI
sequence (`\x1b[31m`, code 31 = red foreground) is absent — colors.py only
ever emits 91/93/0, so `\x1b[31m` surviving is an unambiguous fingerprint
of the attacker payload leaking raw, not a false positive from the hook's
own coloring.

post-hook needs a REAL prior commit (it reads `git log -1` for the last
commit's message, not a simulated command string) — the hostile Memo
trailer must be committed for real first, then post-hook invoked with a
`tool_output.exit_code: 0` payload so it doesn't short-circuit on the
"commit failed" fast path.

## Bullet D — `bin/git-memory-log.py` (the MANDATORY substitute for `git log`) has ZERO sanitization

Confirmed via import list: this script never imports `sanitize_trailer_value`
at all. Two independent print branches, BOTH vulnerable, needing separate
tests: (1) `SUBJECT_RE` matches (subject has an emoji prefix +
`type(scope): msg` shape) → prints `msg` raw (line ~98); (2) `SUBJECT_RE`
doesn't match (no emoji prefix, or any other shape) → prints the WHOLE
raw `subject` (line ~100, the fallback `else` branch). A hostile subject
needs a DIFFERENT construction to hit each branch — with vs. without a
leading emoji token — don't assume one test covers both.

## Bullet E — bootstrap `--json` reflects raw tag-like substrings (a DIFFERENT gap than the already-covered %an human-mode leak)

`lib/bootstrap_commits.py:scan_recent_commits()` stores subject/scope raw
in `"recent"` (confirmed: zero `sanitize_trailer_value` calls in that
function). `git-memory-bootstrap.py --json` does `json.dumps(output, ...)`
— this escapes control bytes (already confirmed safe for `\x1b` in the
prior round's "json vs human asymmetry" note, don't re-test that) but
`json.dumps()` has NO reason to touch `<`/`>` — a literal `</memory-data>`
or `<system>` substring in a commit subject survives byte-for-byte and is
fully reconstructable by anything reading the JSON text (not just a
JSON-aware consumer). This is genuinely independent from the already-fixed
%an-in-human-mode gap (different field, different output mode).

## Bullet F — `git_helpers.commits_since_last_consolidation()`'s `.splitlines()` — genuinely RED, not inert (don't assume "count-only = low impact = safe")

Initial hypothesis (matching a plain-text-only construction, e.g. same
literal subject text with/without `\x1e`, forging via `--grep` keyword
match alone) turned out to be a dead end — confirmed empirically that
result stays `0` either way in that shape (unrelated to control bytes; a
separate "any commit whose subject merely CONTAINS the keyword anywhere
gets treated as if it were the real checkpoint" issue, out of scope for
this control-byte-specific contract). The REAL, byte-specific mechanism:
place `\x1e` **before** the `context(consolidation)` keyword in the
subject of the ONLY matching commit in history. `--grep` still finds the
commit (operates on real message bytes, unaffected). But `.splitlines()`
on the `%H %s` OUTPUT LINE for that commit splits it into two fragments at
the `\x1e` boundary — fragment 1 keeps the sha but loses the keyword,
fragment 2 keeps (part of) the keyword but loses the sha prefix (`parts =
line.split(" ", 1)` then treats a keyword-shard as if it were a sha).
Neither fragment satisfies the loop's match condition, so the real
checkpoint becomes entirely invisible → the function falls through to
`_CONSOLIDATION_SENTINEL` (9999) instead of the correct small count.
Confirmed live: correct count 2 → corrupted result 9999 with ONLY the
`\x1e` byte changed (identical construction with plain text gives 2,
proving the byte alone causes the jump). This is the class's worst-case
outcome (inflation to the sentinel, not a silent no-op) — write it as
RED, not GUARD, and don't shortcut to "count-only function = low-impact =
probably already fine" without the live repro.

## Verification discipline (2026-07-10)

Every RED/GUARD pair here was reproduced live in a scratch script (real
tmp git repos, real function/subprocess calls, real hook invocations)
BEFORE being written into the test file, including one dead-end hypothesis
for bullet F that was discarded once its repro came back unchanged
between hostile and clean input — don't skip the "does the byte alone
change anything" differential check even when a construction "looks"
exploitable on paper. Full file after this round: 109 tests total (86
pre-existing + 23 new: 12 RED + 11 GUARD), confirmed via
`pytest --collect-only -k <new-class-names>` (23/109, exact split
matching 12 failed / 11 passed on a scoped run). Full project suite:
`1160 passed, 2 skipped, 12 failed` — the 12 failures are exactly the new
RED set, zero regressions anywhere else in the ~1174-test suite.
