---
name: issue-57-root-fix-subject-vector-contract-notes
description: Issue #57 root-fix round (decision 0682e75) — SUBJECT-vector class attack, scan_trailers_memory forge/erase, fence evasion via interleaved control bytes, bootstrap/gc leftover leaks
metadata:
  type: feedback
---

Extends [issue-57-field-displacement-contract-notes](issue-57-field-displacement-contract-notes.md).
That round fixed BODY-originated field displacement (moved `%b` last in
every format string). Moriarty then showed the SUBJECT (`%s`) is equally
attacker-controlled and, at every site, still sits BEFORE at least one
other structured field — this round's contract (added to the SAME file,
`tests/test_control_byte_injection.py`, now ~2500 lines) attacks that as
a class, not per-site instances. Written test-first, RED confirmed before
Ultron implements (decision commit 0682e75: structured-fields-first +
`%n`-separated `%s`/`%b` last, since git guarantees `%s` never contains a
literal newline).

## SUBJECT-vector mechanism (bullet A) — one root cause, six+ symptoms

A single stray `\x1f` embedded in the SUBJECT alone (no `\x1e`, no forged
record) consumes a maxsplit slot the parser never budgeted for, shifting
every field parsed after it by one position. Confirmed live with ONE
exact payload (`"feat(scope): subj" + "\x1f" + "junk"`, Moriarty's literal
PoC) reused unmodified across every site — the symptom differs per site
based on what comes after `%s` in that site's format string, but the root
cause and the PoC are identical:
- `recall.py` (%s before %b, body last): total loss — `_scan_commits()`
  returns `[]`, the real Decision is gone entirely (the truncated subject
  tail glues onto body's front, breaking the trailer regex).
- `gc.py`/`doctor.py` (%s before %at, before %b): `scope` survives intact
  in THIS exact payload (paren already closed before the stray byte), but
  `date` corrupts to `None` and the real trailer disappears from
  `trailers` — a DIFFERENT pair of casualties than recall's, same root
  cause.
- `doctor.py check_gc_status` specifically: a real 100-day-old `Blocker:`
  becomes invisible to the stale scan — same shape as the body-vector bug
  Task 2b fixed, just reached via the subject this time.
- `bootstrap_commits.py` (%s before %aI before %an before %b): `date`
  becomes the literal string `'junk'` and `author` becomes the real ISO
  timestamp — BOTH trailing fields corrupt, no phantom 3rd entry (only
  data corruption, not duplication).
- `precompact-snapshot.py`: same total-loss shape as recall (identical
  format/maxsplit shape).
- `boot_memory.py:extract_memory()` — NOT in the user's originally-named
  6 sites, but explicitly named in decision 0682e75 as needing the same
  alignment (`%b` not last there either, `%at` trails it) — added as a
  7th bonus test class since it's demonstrably broken by the identical
  mechanism and in-scope for the same fix.

**Gotcha**: the exact byte POSITION within the subject barely matters —
whether placed inside the scope parens or after the colon, the net effect
(one consumed maxsplit slot, everything after shifted) is the same. Don't
over-engineer payload placement chasing "which field gets corrupted worst"
— pick the placement that matches the literal reported PoC (traceability)
and let empirical repro tell you which assertion actually fails today.

## `scan_trailers_memory()` phantom-line forge/erase (bullet C, Argus SEC-CRIT-14)

Independent bug from the maxsplit/field-alignment class above — no git
record/field parsing involved at all. `lib/parsing.py:113` does
`body.splitlines()`, which treats `\x1c`/`\x1d`/`\x1e` (plus `\r\n\v\f`,
NOT `\x1f`) as line boundaries. A real trailer line immediately followed
by one of these bytes (no real `\n`) masquerades as a second, independent
line within the SAME real commit body:
- **Forge**: if the phantom "line" happens to match `^Key: value$` for a
  DIFFERENT key than the one already seen, it's added as a genuine second
  trailer — confirmed for recall.py, precompact-snapshot.py, and
  boot_memory.py (all 3 real consumers named in the contract).
- **Erase (worse)**: a phantom `Resolved-Memo: <text>` line where `<text>`
  matches a REAL, active Memo from an EARLIER, unrelated commit silently
  tombstones it — the real memo vanishes from output entirely with no
  trace. Confirmed live at all 3 consumers.
- **Same-key forge attempt is a false negative to watch for**: if the
  phantom line reuses the SAME key as the trailer already found
  (`scan_trailers_memory`'s `found: dict` dedups first-occurrence-per-key),
  nothing forges — this looks like a guard but is actually just "the
  wrong test payload", not evidence of a fix. Use a DIFFERENT key for the
  forge PoC (`Decision:` real + phantom `Memo:`), not the same key twice.

## Fence evasion via interleaved control bytes (bullet D)

`sanitize_trailer_value()` removes an EXACT `</memory-data>` substring
(case-insensitive) but never strips `\x1c`/`\x1d`/`\x1e`. A control byte
interleaved INSIDE the marker (`</memory-data\x1e>`) breaks the exact
match, so the whole string — byte included — survives untouched. Test as
a general invariant via regex (`</memory-data[\x1c\x1d\x1e]?>`), not a
literal string compare, so the assertion states the CLASS ("no variant of
this fence marker, with or without an interleaved control byte, survives")
rather than one specific byte.

## `--json` vs human-mode is a real, deliberate asymmetry — don't test both as RED

Two sites (bootstrap `%an` in human mode SEC-MED-15, described in bullet
E) print raw attacker-controlled text directly to a terminal string in
non-JSON mode, while `--json` mode already escapes the same byte via
`json.dumps()` (`\x1b` → the 6-char literal ``). Confirmed live
before writing any assertion — don't write a RED test against `--json`
output for these; it's already safe and was never broken. Only human-mode
(`format_human()`) is the actual gap.

## `find_stale_items()`'s per-field sanitize call is not automatically total

`bin/git-memory-gc.py`'s SEC-MED-09 fix (Task 2b, PART E) sanitizes
`c["text"]` in one shared loop right before `find_stale_items()` returns —
but `evidence` (built earlier, from `c["sha"] + " " + c["subject"]` for
H1's keyword-overlap matches) is a SEPARATE field on the same candidate
dict, never touched by that loop. A single "we already sanitize this
candidate" mental model misses sibling fields built at a different point
in the same function — always grep every field written into the same
dict literal, not just the one already known to be fixed, when auditing
whether a downstream `print_candidates()`/`create_gc_commit()` call site
is actually safe.

## Verification discipline this round

Every one of the 46 new tests (21 RED + 25 GUARD, exact split verified via
`pytest --collect-only` + failure list) was empirically reproduced live in
a scratch script (real tmp git repos, real function/subprocess calls)
BEFORE being written into the test file — including confirming which
GUARD assertions (e.g. `\x1c`/`\x1d` record-forgery inertness at
gc/doctor/bootstrap, which use `parse_trailers_full()`'s plain `\n`-split
and are therefore NOT vulnerable to the splitlines() byte family) were
already safe, so as not to write a false-RED. Full file: 86 tests total
(40 pre-existing + 46 new), `65 passed, 21 failed` confirmed matching
exactly (7 SUBJECT-vector RED + 9 scan_trailers_memory forge/erase RED +
3 fence-evasion RED + 1 bootstrap-human-mode RED + 1 gc-evidence RED = 21),
zero regressions in the 40 pre-existing tests.
