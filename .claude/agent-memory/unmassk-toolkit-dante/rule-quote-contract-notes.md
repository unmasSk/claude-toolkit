---
name: rule-quote-contract-notes
description: gitmem rule --quote RED contract (2026-08-23) -- mandatory literal quote for [user] rules, contradiction found vs no-commit design
metadata:
  type: project
---

Contract file: `unmassk-toolkit/tests/memory/test_rule_quote.py` (8 tests, all RED as of
2026-08-23 for the right reason). Feature: `gitmem rule "<texto>"` now requires
`--quote "<palabras literales de Bex>"` for `--kind user` (default); optional for
`--kind claude`. Motivation: Claude saved a `[user]` rule 2026-08-20 that the owner never
said. Related: [[rules-contract-notes]], [[gitmem-rule-no-commit-contract-notes]].

**Contradiction found and reported, not silently resolved:** the task instructions asked
scenario 2 (quote given) to assert "exactly one new commit whose message carries the
rule." Current production (`rules.py::add()`, 2026-08-06 decision, docstring + enforced by
`test_rule_script.py::TestRuleEndsUpInTheFileNotInAnOwnCommit`) never commits -- one step,
atomic file write only. Wrote the test asserting what the code actually guarantees (HEAD
unmoved, file left as uncommitted change) instead of the requested commit, with the
discrepancy documented in the test file's module docstring. **How to apply:** when a task
prompt asks for behavior that contradicts a recent, deliberately-tested production
decision, don't silently pick a side -- write the coherent part matching current code,
flag the conflict explicitly in the report, and let the orchestrator decide. Don't guess.

**Vacuous-green pitfall with a not-yet-existing flag:** a rejection test for `--quote ""`
initially passed today for the WRONG reason -- argparse's own `unrecognized arguments:
--quote` (flag doesn't exist yet) already yields `rc != 0`, satisfying a naive "rc != 0"
assertion without ever exercising real blank-quote validation. Fix: assert
`"unrecognized arguments" not in combined` (forces true RED today) plus the same
`"Relanza:"` shape check used for the missing-quote rejection, so the test only goes GREEN
once a real business rejection (via `rejection.build()`/`render_terminal()`) exists.
**How to apply:** whenever a RED test's failure-mode assertion is just "exit code
nonzero", check whether an unrelated failure (missing CLI flag, import error) could
already satisfy it today -- if so, add an assertion that names the specific mechanism
expected (e.g. absence of the generic argparse error string) so RED is RED for the right
reason, per Dante's own protocol.

Format landed on for the quote line (fixed by the task, asserted exactly):
`[remember][user] <emoji> <texto> — «<cita>»`, verified via
`rules.iter_rule_texts()` returning `"<texto> — «<cita>»"` as one text (the reader is
never told a quote exists as a separate field -- Ultron's contract is just to produce that
exact line shape). Near-duplicate detection (`similar_existing()`, Jaccard on text only)
must keep ignoring the quote -- scenario 7 seeds two near-identical texts with two
*different* quotes and expects the existing rejection to still fire, guarding against
Ultron accidentally folding the quote into the text passed to the dedup check.

**Amended 2026-08-23 (owner hardened the contract mid-flight, Ultron already implementing
in parallel):** `--quote` became mandatory for BOTH kinds, not just `[user]`. Escape hatch
is the literal `--quote none` (accepted for `[claude]` and, explicitly, for `[user]` too)
-> saved with no quote part. Updated the same test file in place: scenario 3 flipped from
"claude no-quote succeeds" to "claude no-quote rejected", added two `--quote none` tests
(claude, user). Re-running against Ultron's in-progress implementation surfaced a real bug
in my OWN test, not in production: `assert candidate_text not in content` false-failed
because the candidate text ("...integration test") is a literal prefix substring of the
already-seeded text ("...integration tests") -- a whole-file substring check is unsafe
whenever two fixture strings differ only by a trailing suffix. Fixed by comparing against
`iter_rule_texts()` entries with exact equality / exact quote-suffix match instead of
`in content`. **How to apply:** never assert `X not in <whole file content>` when X could
be a true substring of a DIFFERENT, legitimately-present entry -- compare against
production's own parsed/tokenized view (here `iter_rule_texts()`), never raw string
containment, whenever two test fixtures share a prefix/suffix relationship.

**Closed out 2026-08-23:** Ultron's implementation made the new contract file
(`test_rule_quote.py`) 11/11 green, which broke 9 pre-existing seed calls in
`test_rule_script.py` (they added rules via the CLI with no `--quote`, now mandatory).
Updated only the `rule.py` invocations inside those 9 tests -- both the literal "seed"
calls AND, inside `TestSimilarExistingRuleIsWarnedBeforeAdding`, the "candidate" calls
too, since those also add a rule via the CLI and would otherwise hit the new
missing-quote rejection before ever reaching the near-duplicate check the test exists to
verify. Picked `--quote none` vs. a real literal quote per assertion shape, not per
`kind`: `test_rule_ends_up_in_the_file_and_creates_no_commit` asserts `text in
file_texts` where `file_texts` is a tuple of EXACT parsed strings (equality, not
substring) -- a real quote appends `" — «...»"` to the persisted text and breaks that
equality, so `--quote none` was mandatory there regardless of `kind=user`. Everywhere
else the assertion was substring-on-a-blob (`text in show_out`/`text in out`), where
either choice was safe -- used `--quote none` for `kind=claude` self-rules (matches the
scenario's own spirit) and a real literal quote for `kind=user`. Final:
`test_rule_script.py` + `test_rules.py` + `test_rule_quote.py` = 35/35 green, 0
production code touched. **How to apply:** when a mandatory-field change breaks a batch
of pre-existing tests, check what EACH assertion actually compares (tuple equality vs.
substring) before picking a filler value -- the safe filler differs by assertion shape,
not by which branch of the code path you happen to be testing.
