---
name: relaunch-command-answer-amnesia-contract-notes
description: unmassk-memory (v2) test_relaunch_command_answer_amnesia.py -- RED contract proving the pain-question/overlap rejection cycle never converges because each rejection's `command` field is built independently, dropping already-answered flags (--stops/--replaces/--origin/--awaits)
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_relaunch_command_answer_amnesia.py`
(new file, RED by design, test-first contract pass, acceptance
granularity only -- not the exhaustive branch sweep). Bug: each
`validate_*` function in `lib/memory/validator.py` builds its own
`command` string from scratch (`note.type/zone1/zone2/headline` +
whatever local param it happens to receive), never re-including a flag
answered in an EARLIER rejection round. `validate_pain_question` knows
`--stops` (own param) but not `--replaces`; `validate_replacement`
knows `--replaces` (via `note.replaces`, but only fills it when
OFFERING it, doesn't echo an already-answered `--stops` since `stops`
isn't a `Note` field and never reaches this function). Result: a
2-cycle that never terminates -- `missing_pain_answer` ->
(answer `--stops`) -> `overlapping_note` (drops `--stops`) ->
(relaunch as offered, `--stops` missing again) -> `missing_pain_answer`
-> ... forever.

**Two tests, not an exhaustive sweep of all nine `validate_*`
functions** -- test-first contract pass (CLAUDE.md, "Modo test-first").
The task explicitly named `validator_pointers.py`/`validator_zones.py`
as sharing the same pattern, but that's material for the HARDENING pass
after Ultron implements, not this one.

1. `test_overlap_rejection_command_drops_the_already_answered_stops_flag`
   -- minimal, isolated: 2 real subprocess steps (`gitmem` facade
   against a real `tmp_repo`), then ONE comparison between two
   independently-produced strings: the tokens of the command that was
   ACTUALLY just executed (step 2, has `--stops yes`) vs. the tokens of
   the command the resulting rejection (`overlapping_note`) offers for
   step 3. Fails today: `--stops` is `None` in the offered command.

2. `test_pain_question_and_overlap_rejection_cycle_converges` -- full
   loop (bounded `MAX_STEPS=6`), executes literally whatever each
   rejection offers, accumulates `given_answers` from what was actually
   run, asserts every accumulated flag=value survives verbatim into the
   next offered command (this single assertion covers BOTH "must not
   drop an answer" and "must not invent a different one" -- a dropped
   answer and a fabricated different one are the same assertion
   failure, `got != value`, never split into two tests). On success
   (not reached today), does a REAL round-trip: `extract_note_id()`
   from `note.py`'s own confirmation line, then greps every `*.md`
   index file on disk under `pm_path(tmp_repo)` for that literal id --
   never assumes success from the exit code alone.

**Gotcha: naive "any line starting with `gitmem `" over-collects.**
`overlapping_note`'s `options` body ALSO contains a prose-embedded
`gitmem remove <id> "..." --restriction no` line (the "es duplicado"
alternative, `validator.py` ~line 409) that is NOT the rejection's
structured `command` field -- confirmed live: a first draft of
`_extract_relaunch_commands` using the naive rule (same rule
`test_rejection_relaunch_commands.py` uses for a DIFFERENT purpose --
finding every `gitmem` mention in source, Pass B) returned 2 commands
for a rejection whose contract says `command` is "uno o dos comandos,"
never a mix with prose. Fix: only scan lines AFTER the literal
`"Relanza:"` header that `rejection.py::_render` prints -- the exact
boundary between the structured `relaunch` field and free-text
`options` prose.

**Type choice avoids an unrelated confound.** `missing_pain_answer`
offers TWO alternatives (type M + `--stops no`, type R + `--stops
yes`). Picking the R branch (`_pick_relaunch`, prefers `--stops yes`)
is deliberate: `overlapping_note`'s command unconditionally adds `--why
"..."` regardless of note type (another instance of the same
independently-built-command bug), and `--why` is NOT in `M`'s
`allowed_fields` (`vocabulary.py TYPES["M"]`) but IS in `R`'s -- picking
M here would trigger a SECOND, unrelated `field_not_allowed` rejection
firing simultaneously, muddying the isolated repro. R sidesteps it
without hiding it (documented in the test's own `_pick_relaunch`
docstring, not silently avoided).

**Similarity fixture trick, reusable:** seed the existing "blocking"
note with `description="..."` too (not just the candidate) --
`similar.py::_tokens` uses `\w+` regex, which matches zero characters
in the literal string `"..."`. Two notes with identical headline and
`description="..."` on both sides get Jaccard similarity exactly 1.0,
regardless of what literal placeholder text any later relaunch step
happens to send for `--description` -- deterministic overlap trigger
with zero dependency on wording.

**Result:** both tests fail today for the exact predicted reason
(`assert None == 'yes'` / `assert got == value`), full transcript
included in the failure message. Full `tests/memory` suite: `378
passed` (pre-existing) + these `2` new RED = one pre-existing unrelated
failure (`test_remove_incident_close_fence_atomicity.py`, untracked
file, not touched by this task, confirmed failing in isolation before
this file existed too) is NOT caused by this change.

Reference: [rejection-relaunch-command-ast-crosscheck-notes](rejection-relaunch-command-ast-crosscheck-notes.md), [rejection-contract-notes](rejection-contract-notes.md), [validator-contract-notes](validator-contract-notes.md)
