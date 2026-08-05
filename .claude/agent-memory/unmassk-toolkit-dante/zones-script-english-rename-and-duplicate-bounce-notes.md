---
name: zones-script-english-rename-and-duplicate-bounce-notes
description: test_zones_script.py 2026-08-04 update -- CLI rename alta/listar/buscar to add/list/find, duplicate-zone-registration bounce contract, B22 concurrency-out-of-scope note, chained-RED technique for a two-decision same-file task
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_zones_script.py`, already existed
GREEN (4 tests) from a prior session against a REAL, already-implemented
`bin/memory/zones.py` (not the usual "script doesn't exist yet" RED). This
task landed two owner decisions (2026-08-04) on the SAME script at once:
subcommands `alta`/`listar`/`buscar` -> `add`/`list`/`find` (no alias, no
grace period), and re-registering an existing zone name must bounce instead
of silently overwriting (real regression reproduced live by the
orchestrator that same session: second `alta` on `billing` wiped the first
one's alias/description, both printed the identical "✅ dada de alta").

**Technique: chained-RED for two decisions landing in one file at once.**
Testing decision 2 (duplicate bounce) requires a *first* successful
registration to bounce against -- but decision 1 (rename) isn't implemented
yet, so seeding through the new `add` verb fails today for a DIFFERENT
reason than the one under test. Resolved by asserting the first call's
`rc == 0` explicitly, with a message naming it as the seed step -- this
makes the test fail today at the seed assertion (real reason: `add` not
recognized), and will only pass once BOTH decisions are real: rename done
AND dedup implemented. No vacuous-pass risk verified two ways: (a) ran the
suite and confirmed every one of the 10 new/changed tests fails for a
distinct, correct reason (`pytest -v`, read every traceback); (b) mentally
walked "rename done, dedup still missing" -- second `add` would then
succeed (rc==0) and overwrite, so `rc_second != 0` and the byte-compare
would both catch it independently. Two independent invariants (rc AND
byte-identity) that don't share a common trivial-pass cause is the pattern
to reach for whenever one RED test has to prove a chain of two behaviors.

**Old-subcommand-retirement test needs a positive check beyond `rc != 0`,
for `alta` specifically (the write path).** `rc != 0` alone can't tell
"argparse rejected an unknown token" from "the write silently half-failed
for some other reason" -- confirmed the real discriminator is whether the
zone shows up via `zones.load()` afterward. For the two read-only old verbs
(`listar`/`buscar`) there's nothing to seed-and-check-absence against, so
the positive signal used instead is argparse's OWN literal echo of the
offending token (`invalid choice: 'listar'`) -- verified live this is
Python's own contract (`argparse` always echoes the bad choice verbatim),
not fabricated project prose, so it's fair game under the "no invented
rejection text" rule even though no project document names this case.

**No TEXTOS.md text exists for "zone already exists"** -- verified by
grep across the whole file for "ya existe"/"duplicad"/"already" combined
with zone-related terms. Sec.1.1 is the *opposite* rejection ("zona que NO
existe"). Contract enforces behavior only (bounces, `rc != 0`, file
byte-identical via `Path.read_bytes()` before/after PLUS
`zones.load()` field-by-field) plus one non-fabricated positive datum (the
real zone name must appear in the combined output) -- never a hand-typed
rejection sentence. Documented explicitly in the file's module docstring
so Ultron doesn't have to re-derive this by searching again.

**Alias-collision case left OUT on purpose.** `zones.resolve()` already
applies aliases when resolving a name to its canonical zone, but no
document and no existing function decides whether registering a NEW name
that collides with another zone's *alias* (not its canonical name) should
also bounce. Flagged in both the test file's docstring and the task report
instead of guessed at -- matches the project's explicit rule (`CLAUDE.md`):
"un hueco puede ser deliberado", fill nothing from personal judgment.

**B22 (2026-08-04) retired concurrency as an in-scope test concern for this
whole project** -- *"dos escrituras a la vez sobre el mismo fichero: no se
dan... trabaja en una sola ventana"*. The task's own instructions echoed
this as a hard boundary ("dos procesos a la vez está descartado. Nada de
eso") for what I should ADD. Left the pre-existing
`TestTwoConcurrentRegistrationsDoNotClobberEachOther` class untouched in
shape (only updated its subcommand string for the rename) rather than
deleting it unilaterally -- it predates B22, is currently exercising real
locking code that's still in production, and deleting an unrelated
passing test outside the two decisions I was scoped to touch is exactly
the kind of unauthorized scope creep this project's CLAUDE.md warns
against ("nada se rellena con criterio propio"). Flagged as a retirement
candidate in the report instead.

Verification command: `python3 -m pytest unmassk-toolkit/tests/memory/test_zones_script.py -v`
-> 10 failed, each for a distinct real reason (read every traceback, no
generic "script not found" catch-all since the script already exists).
`--collect-only` on the whole `tests/memory` dir confirms no other file
touched (292 tests collected, only this file's own tests changed shape).
