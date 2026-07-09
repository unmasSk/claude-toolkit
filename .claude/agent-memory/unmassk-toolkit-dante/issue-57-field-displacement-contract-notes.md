---
name: issue-57-field-displacement-contract-notes
description: Issue #57 Task 2b remediation-round contract (field displacement, fence-break, splitlines phantom-commit, \x7f) — str.strip() control-byte gotcha and per-site test design
metadata:
  type: feedback
---

Extends [boot-stdout-banner-contract-notes](boot-stdout-banner-contract-notes.md)'s
control-byte record-injection contract. That first pass (`-z` NUL record
boundaries) closed RECORD forgery; three independent auditors (Cerberus,
Argus, Moriarty) then found the real DoD wasn't met — a completely
different mechanism, no `\x1e` involved at all. Written test-first as a
sibling section inside the SAME file
(`tests/test_control_byte_injection.py`, not a new file — the fix targets
the same 8 sites, so one contract file stays the single source of truth).

## Critical gotcha: Python's `str.strip()` treats `\x1c`/`\x1d`/`\x1e`/`\x1f` as whitespace

`'a\x1f'.strip() == 'a'` — confirmed empirically. This is NOT documented
anywhere obvious and silently invalidates two kinds of test design:

1. **Never place an injected control byte at the very start/end of a
   string you're about to `.strip()`.** Every parsing site in this
   codebase calls `.strip()` on the whole record AND on individual parsed
   fields. A stray `\x1f`/`\x1e` at a string edge gets silently eaten
   before your assertion ever sees it — the test then measures the wrong
   thing. Fix: always embed the injected byte MID-STRING (e.g.
   `"noise before stray sep" + FIELD_SEP + "\nDecision: ..."`), never as
   the first or last character of the payload.
2. **A commit with an EMPTY body plus a trailing format-string separator
   can silently drop below a `len(parts) < N` threshold and get skipped
   entirely** — discovered while building the precompact-snapshot.py ANSI
   test: a `context(...)` commit with NO body produces a raw record
   `"sha\x1fsubject\x1f"` (trailing separator, empty 3rd field). `.strip()`
   eats that trailing `\x1f`, collapsing the record to only 2 parts after
   `split("\x1f", 2)` — `extract_memory_from_log()`'s `if len(parts) < 3:
   continue` then skips the commit outright, and `last_context` never gets
   set. This is a REAL, separate, pre-existing quirk (not the bug under
   test) — it only bites when the body is genuinely empty. Fix: give any
   test commit that exercises subject/last_context sanitization a
   non-empty body (any filler text), so the record always has a real
   non-whitespace character after the final separator and `.strip()`
   cannot eat it.

## Field-displacement (Task 2b PART A) — root cause per site, one sentence each

The bug is never "the maxsplit count is wrong in general" — it's "the
field carrying fully attacker-controlled text (the body) is not
positioned LAST in the `--pretty=format` string, so a stray `\x1f` inside
it bleeds into whatever real field comes after." Confirmed per site
(2026-07-09, live repro, not reasoned about):

- `lib/recall.py` (`%h\x1f%s\x1f%b`, maxsplit=3 for a 3-field/2-separator
  record): stray sep before a real trailer → `body` truncated → trailer
  discarded → `_scan_commits()` returns `[]`.
- `bin/git-memory-gc.py` / `bin/git-memory-doctor.py` (`check_hook_execution`,
  `check_gc_status`) (`%h\x1f%s\x1f%b\x1f%at`, %b NOT last): stray sep →
  `body` truncated (trailer lost) AND `date`/`with_trailers` corrupted —
  `parse_date()` on the leftover (trailer text + real sep + real epoch)
  returns `None`. For `check_gc_status` specifically: a REAL, genuinely
  100-day-old `Blocker:` becomes fully invisible to the stale scan
  (Moriarty's exact finding — `stale_blockers == []`).
- `lib/bootstrap_commits.py` (`%h\x1f%s\x1f%b\x1f%aI\x1f%an`, %b NOT last):
  stray sep shifts BOTH trailing fields — `date` ends up literally holding
  the discarded trailer text (fails an ISO-8601 regex outright), `author`
  ends up holding `"<real-ISO-date>\x1f<real-author>"` glued together via
  the one remaining unconsumed separator.
- `hooks/precompact-snapshot.py` (`%h\x1f%s\x1f%b`, maxsplit=2, %b LAST
  field): already correct by construction — a stray sep anywhere inside
  body has nowhere left to bleed into, it just stays embedded harmlessly.
  This is the ONE site written as `[GUARD]` not `[ROJO]` for this bug
  class, and is the reference shape Ultron's fix replicates at the other
  4 (move the injectable/body field to the end of the format string, or
  equivalently ensure it's the one field with no maxsplit cap after it).

**Test pattern per site**: build the hostile commit with `body = "noise
before stray sep" + FIELD_SEP + "\nDecision: real decision must survive"`
(or `Blocker:` for the doctor `check_gc_status` case, backdated via
`GIT_AUTHOR_DATE` to also prove the staleness detection specifically), run
the real function, assert the real trailer/date/author survives — NOT
that a forged value is absent (that's the earlier record-forgery
contract; field-displacement is about REAL data loss/corruption, a
different assertion shape). Pair every `[ROJO]` with a `[GUARD]`: the
identical trailer with NO stray separator, proving the eventual fix
(reordering the format string / adjusting maxsplit) cannot regress the
already-working happy path.

## Fence-break (Task 2b PART B) — `scope` is the one field that regularly skips sanitization

`parse_scope(subject)` reads directly from the fully attacker-controlled
commit subject, yet several sites build `label = f"({scope})"` (or embed
`scope`/raw `subject` in an LLM-facing string) with NO call to
`sanitize_trailer_value()` — even though the SAME site already sanitizes
every trailer VALUE (Decision/Memo/Next/Blocker text). Mirror pattern
already fixed once in `lib/boot_memory.py` (SEC-CRIT-NEW-04): `scope =
sanitize_trailer_value(parse_scope(subject) or "")` before building the
label. `recall.py`'s `_scan_commits()` and `precompact-snapshot.py`'s
`extract_memory_from_log()` both lack this call on `scope`;
`precompact-snapshot.py` additionally stores `last_context['subject']`
completely raw (reaches stdout verbatim via `f"Last session: {sha}
{subject}"`).

**Payload that proves it without fighting `splitlines()`**: subject =
`"feat(</memory-data> INJECTED): forged commit subject"` — same
`</memory-data>` zone-delimiter trick already documented as the reliable
non-line-boundary marker (see
[edge-cases](edge-cases.md)'s "Testing `_sanitize_trailer_value()`
coverage" note). For the raw-subject/ANSI variant, embed `\x1b` (ANSI ESC)
mid-subject and assert `"\x1b" not in stdout` — remember the empty-body
`.strip()` gotcha above; give the commit a real filler body.

## `.splitlines()` phantom-commit (Task 2b PART C) — a DIFFERENT control-byte family than `\x1f`

`hooks/stop-close-session.py` and `hooks/stop-dod-check.py` read `git log
--pretty=format:%s` WITHOUT `-z` and iterate with `.splitlines()`. Python's
`.splitlines()` boundary set is `\r \n \v \f \x1c \x1d \x1e \x85 U+2028
U+2029` — note `\x1e` (Record Separator) IS in this set, `\x1f` (Unit
Separator, the field-separator byte used everywhere else in this contract)
is NOT. A single commit subject embedding a raw `\x1e` therefore
masquerades as TWO iterated "lines"/"commits" to any counting function —
confirmed for all 4 functions checked (`_commits_since_last_context`,
`_has_substantive_commits` in stop-close-session.py;
`count_consecutive_wips`, `has_recent_memory_commits` in
stop-dod-check.py). Depending on the function, the symptom is either
OVER-counting (a phantom line satisfies a "found it" condition that
shouldn't exist) or UNDER-counting (a phantom non-matching line
prematurely breaks a "count consecutive matches" loop that should have
kept going into REAL older commits behind it — `count_consecutive_wips`
is this shape: poison the MIDDLE of 3 genuinely-consecutive real wip
commits to prove the corruption reaches past the poisoned commit itself).
Call the hyphenated hook's internal functions directly via the
`importlib.util.spec_from_file_location` pattern (both files have zero
side effects outside `if __name__ == "__main__": main()`) — no subprocess
needed, these are plain functions.

`hooks/stop-dod-check.py:get_last_commit_next()` (lines 156-166) already
uses `.split("\n")`, not `.splitlines()` — NOT part of this bug class,
don't write a test for it under this contract.

## `\x7f` (DEL) gap in `sanitize_trailer_value()` (Task 2b PART D)

`lib/parsing.py:sanitize_trailer_value()` strips `\x1b` (ANSI ESC,
SEC-MED-NEW-08) via `re.sub(r"[\r\n \x0b\x0c\x1b]", " ", text)` but the
character class doesn't include `\x7f` — confirmed live, `\x7f` survives
verbatim. Simplest test in the whole contract: no git involved, straight
unit test on the function, `sanitize_trailer_value("abc\x7fdef")` must not
contain `"\x7f"` (plus a positive control that `"abc"`/`"def"` survive —
proves stripping, not blanking).

## Verification discipline for this round

Every one of the 13 new RED tests + 8 new GUARD tests in this round was
empirically reproduced live (real tmp git repos, real function calls) in
the scratchpad BEFORE being written into the test file — not reasoned
about from reading the source. Full-suite confirmation after writing:
`1086 passed, 2 skipped, 13 failed` (the 13 new RED cases, exact expected
count, zero unexpected regressions in the other 1086).
