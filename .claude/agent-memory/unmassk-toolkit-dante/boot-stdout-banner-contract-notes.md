---
name: boot-stdout-banner-contract-notes
description: session-start-boot.py stdout-truncation contract, corrected mid-pipeline from conditional (byte threshold) to unconditional banner — test_boot_output.py
metadata:
  type: project
---

`unmassk-toolkit/hooks/session-start-boot.py` had a real bug (House diagnosis):
a giant context() commit subject could exhaust the Claude Code harness's
~2KB stdout preview window before the `Next:` line was reached. First fix
attempt (Dante's first contract pass) was CONDITIONAL:
`STDOUT_FULL_INLINE_BUDGET_BYTES = 6000` — print everything inline if the
full briefing measured under that, else switch to a short banner + full
content written to `.claude/.unmassk/boot-log-latest.txt`.

**Why this got corrected:** Yoda found the threshold measured the wrong
thing. A repo with 25 ordinary scopes (nothing extreme) totalled only 3193
bytes (under 6000, so still printed fully inline) — yet its `Next:` line
landed at byte 2491, already past the harness's real ~2KB truncation point.
Total-size thresholds don't guarantee where the important line falls. Bex's
ruling: remove the conditional. The banner is now UNCONDITIONAL — every
boot, any repo size, prints the short banner (STATUS, BRANCH, pointer
message, BOOT COMPLETE terminator) and writes the full untruncated briefing
to the fixed-path file. With no threshold to cross, this class of bug is
impossible by construction. The one exception, unchanged: if the file write
itself fails (permissions, disk full), fall back to printing `full_text`
inline — that's about write success, not size, and was never part of the
threshold logic.

**How to apply — pattern for correcting a test-first contract mid-pipeline:**
1. Every test that asserted heavy sections (RESUME/REMEMBER/DECISIONS/
   MEMOS/TIMELINE/SCOPES) or their content directly against **stdout** for a
   *small/normal* repo was testing the OLD contract and needed conversion to
   read the **boot-log file** instead (same helper, `_read_boot_log(repo)` /
   `_boot_log_path(repo)`, already existed in the test file — no new helper
   needed). Do this before deleting anything; only delete a test if nothing
   in it survives the new contract (none did here — every old assertion had
   a valid new home).
2. Tests that constructed a "giant commit" *purely to force the banner
   branch* (`make_repo_with_giant_commit`) no longer need to, once the
   banner is unconditional — an ordinary small repo (`make_repo_with_memory`)
   now reaches the same code path. Simplify those to the plain fixture
   (`TestBannerByteBudgetWithLongBranchName` was the concrete case: dropped
   the giant-commit setup, kept only the long-branch-name edge case, and it
   still exercises the banner path).
3. Where a giant-payload fixture still earns its keep — proving no
   regression on an extreme case, or giving an unambiguous character-run
   marker as proof of non-truncation — keep it alongside a new normal-repo
   variant of the same test, not instead of it. Both class of proof matter:
   "works for everyday repos" and "still works at the extreme."
4. Add ONE direct regression test built from the exact reported incident
   numbers (here: 25 scopes, ~3193 bytes) rather than only asserting the new
   rule abstractly — it's the most concrete evidence that the specific
   confirmed bug can't recur, and it's cheap insurance if anyone
   reintroduces a size-based threshold later.
5. Factor the repeated magic number (here, the `<1000`-byte stdout budget)
   into ONE module-level constant instead of duplicating it across every
   test class — it had drifted into 3 separate literals before consolidation.

Result: 39 → 45 tests in `unmassk-toolkit/tests/test_boot_output.py`. Ran
RED against the current hook (still has the conditional): 6 failed / 39
passed, all 6 failures being exactly the tests that encode "banner must be
unconditional" — coherent RED, ready for Ultron to remove
`STDOUT_FULL_INLINE_BUDGET_BYTES` and the branch that reads it.

See also: [unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md), [skill-router-contract-notes](skill-router-contract-notes.md) (same "test-first contract, corrected mid-pipeline" shape).

**Round 3 (session 2026-07-05) — re-audit findings, 4th pass on this same
file/module.** Argus + Cerberus found 4 more issues on the already-hardened
boot hook + adjacent bin/ scripts: control-byte record injection in
`extract_memory()`/`extract_glossary()` (SEC-CRIT-NEW-01), asymmetric
symlink guard on `_read_glossary_cache()` (write side already fixed via
SEC-CRIT-001, read side still plain `open()`) (SEC-MED-NEW-02),
`manifest.json` written unguarded by `bin/git-memory-install.py` and
`bin/git-memory-upgrade.py` (SEC-HIGH-NEW-03, NOT in session-start-boot.py —
different files, same class of bug), and `write_boot_log()`'s bare `except
OSError: return None` leaving zero stderr trace (CRB T2-2). All 4 written as
failing contract tests before Ultron touches anything — see
[edge-cases.md](edge-cases.md) for the exact reproduction patterns (control-byte
injection, and the install/upgrade manifest symlink gotchas). Confirms this
file/module has now gone through 3 full audit-then-harden cycles in the same
session — a sign the "hardening pass" after test-first fixes keeps surfacing
genuinely new findings each round rather than converging, worth flagging to
Yoda if a 4th round starts finding the same class of bug again.

**Round 2 — Ultron implemented the unconditional banner; 5 OTHER test files broke
(23 tests), not just `test_boot_output.py`.** Any test file that runs
`session-start-boot.py` as a subprocess and asserts directly against its
stdout for heavy content (RESUME/REMEMBER/DECISIONS/MEMOS/CONSOLIDATE/TIMELINE)
breaks the same way, regardless of what feature that file is actually testing
(tombstones, crown, crown retraction, consolidation trigger, unrelated
regression bugs). Fixed in `test_boot_tombstones.py`, `test_consolidation_trigger.py`,
`test_crown.py`, `test_crown_retraction.py`, `test_regression_memory_correctness.py`.

**How to apply:**
1. Don't just fix the tests pytest reports as FAILED. A stdout→file contract
   change can leave some assertions **vacuously passing** for the wrong reason
   (e.g. `assert "xyz" not in output` trivially true now because NOTHING heavy
   is ever in stdout anymore, not because the feature under test actually
   suppressed it). Grep every file for the heavy-section markers
   (`DECISIONS:`, `MEMOS:`, `REMEMBER:`, `RESUME:`, `CONSOLIDATE:`, `TIMELINE`)
   used against a stdout variable and migrate ALL of them to the boot-log
   file, not only the ones currently red. In this round, 23 pytest-reported
   failures + ~6 additional vacuous-pass assertions across the 5 files all
   needed the same fix.
2. Each file already had its own local `run_boot`/`_run_boot` helper
   (different name per file) that returns stdout only — don't change its
   return signature (other assertions in the same file may legitimately
   check stdout, e.g. `BOOT COMPLETE`, `Traceback` in stderr, rc). Instead,
   add the same three-symbol helper trio locally to each file:
   `BOOT_LOG_REL_PARTS`, `_boot_log_path(repo)`, `_read_boot_log(repo)`
   (copy verbatim from `test_boot_output.py` — do not invent a new shape).
   Call the existing run-boot helper for its side effect (writes the log
   file), then separately call `_read_boot_log(repo)` to get content to
   assert against.
3. Where a file calls the pattern `_some_block(_run_boot(repo))` (a
   block-extraction helper fed directly the boot call), the block-extraction
   helper itself doesn't care about the source of the string — only the
   call site changes, e.g. `_decisions_block(_run_boot(repo))` →
   `_decisions_block(_boot_log_content(repo))` where `_boot_log_content`
   is a tiny local wrapper (`_run_boot(repo); return _read_boot_log(repo)`)
   added once per file to avoid repeating the two-call sequence at every
   site.
4. A test asserting BOTH banner-only content (`BOOT COMPLETE`, `STATUS:`,
   `BRANCH:`) AND heavy content in the same body (e.g. a "regression: normal
   boot still works" catch-all test) needs to split into two variables —
   `output = run_boot(repo)` for the banner assertions, `content =
   _read_boot_log(repo)` for everything else — not migrate the whole test
   to the file, since the banner assertions would then trivially pass by
   checking the wrong source.
5. Confirm scope precisely before touching anything cross-cutting: a
   sibling script (`precompact-snapshot.py` in this repo) that does NOT use
   `BOOT_LOG_REL_PARTS`/the banner mechanism at all is untouched by this
   contract change — grep the target hook file for the banner constant name
   before assuming every "boot-adjacent" script needs migrating.
