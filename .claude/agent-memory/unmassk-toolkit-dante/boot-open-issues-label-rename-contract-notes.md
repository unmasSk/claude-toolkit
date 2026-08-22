---
name: boot-open-issues-label-rename-contract-notes
description: boot.py COUNTS label rename ("plans with a record" -> "issues with a live note") after D-044/D-045 opened --issue to all seven note types — RED-only edit, Argus invariant preserved untouched
metadata:
  type: project
---

Task: bounded contract change, tests-only. `--issue` was just opened from
M-only to all seven note types (D-044/D-045). Consequence: `boot.py`'s
COUNTS block label "plans with a record" (`boot.py:381`, `open_issues`
computed at `boot.py:215` as distinct issue numbers across live/unarchived
notes) no longer describes what the number measures — an incident (I) or
a discard (X) with `--issue` now also counts, not just a memo (M) acta.

**What changed**: renamed
`test_boot.py::test_recuentos_label_says_planes_con_acta_not_issues_abiertas`
to `test_recuentos_label_says_issues_with_a_live_note_not_issues_abiertas`.
Swapped the two positive assertions from `"plans with a record" in
rendered` to `"issues with a live note" in rendered` (before AND after
archiving). Updated docstring and failure messages to explain the new
reason.

**What did NOT change, on purpose**: the negative assertion `"issues
abiertas" not in rendered` — this is Argus's 2026-08-02 invariant (the
number never asks GitHub, can lie "0" with a real open issue or "1" with
one closed months ago) and stays untouched in both before/after blocks.
Also untouched: the archive-then-recount-to-0 mechanic itself (still
`indexes.remove()` + `indexes.archive()`, still checks `open_issues == 0`
locally without touching GitHub) — this test still seeds only an M-type
note with `issue=47`, since the seven-type opening (`--issue` on other
types) is a SEPARATE contract (`test_note_issue_field.py`, see
[[note-issue-field-seven-types-contract-notes]]) not yet implemented in
production. Confirmed RED for the right reason: production still prints
`plans with a record`, assertion fails on the new label string, not on
`open_issues` count or the "issues abiertas" guard.

Verified: `unmassk-toolkit/tests/memory` — 488 passed, 1 skipped, 1 failed
(this test, RED as intended). No production file touched.

**Reminder to self**: nearly overwrote an unrelated existing memory file
(`pending-next-cutoff-contract-notes.md`) with a Write() typo/placeholder
mid-task — caught immediately via `git diff --stat`, restored with `git
checkout HEAD -- <path>` (safe: file was clean/tracked, no uncommitted
work lost) before writing this note under its own correct filename.
Always `git status`/`git diff` an agent-memory file right after any Write
to it, before moving on.
