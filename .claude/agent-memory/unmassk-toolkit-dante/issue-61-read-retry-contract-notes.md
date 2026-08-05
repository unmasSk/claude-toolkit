---
name: issue-61-read-retry-contract-notes
description: issue #61 test-first RED contract (docs/plan/fix-silent-memory-loss-61.md) for missing retry in the 4 production read-path git callers — WARN already shipped in a prior round, only retry is the real gap
metadata:
  type: project
---

## Surprising finding: verify claims against real code, not against the task brief

The task brief (and the plan doc) said BOTH "no retry" and "no warn" were
missing in production for the 4 read sites (`recall.py::_scan_commits()`,
`boot_memory.py::extract_glossary()`, `boot_git_checks.py::get_timeline()`,
`git_helpers.py::commits_since_last_consolidation()`). Grepping the actual
code first (before writing a single test) showed the WARN half was **already
shipped** in an earlier #61 round (`log_stderr_on_failure=True` kwarg /
manual `print` — see [issue-61-ci-flake-hardening-notes](issue-61-ci-flake-hardening-notes.md)'s
"Cerberus follow-up" entry and `tests/test_issue61_breadcrumbs.py`, 16 tests,
all green). Wrote the "persistent failure emits WARN" test anyway (kept as
an explicit regression lock, not deleted) and ran it for real: **4/4 passed
today**, confirming the WARN gap is closed, only the **retry** gap is real.
Empirical run of the full 12-test contract: exactly 4 RED (the 4
retry-recovery tests, one per site) + 8 GREEN (4 already-shipped-WARN locks
+ 4 anti-false-positive controls) — never trust a task brief's "X is
missing" claim over grepping the actual production file first.

## Patch target depends on import shape, confirmed per site (4-way split)

- `recall.py` binds `run_git` at MODULE level (`from git_helpers import
  run_git` at file top) → monkeypatch `recall.run_git`, not
  `git_helpers.run_git` (a later patch to the latter would never reach
  `_scan_commits()`, which already captured its own reference at import
  time).
- `boot_git_checks.py::get_timeline()`, `boot_memory.py::extract_glossary()`
  both do `from git_helpers import run_git` **inside the function body**
  (deferred, re-resolved every call) → monkeypatch `git_helpers.run_git`.
- `git_helpers.py::commits_since_last_consolidation()` calls `run_git`
  defined in the SAME module → also monkeypatch `git_helpers.run_git`
  (module-level name lookup at call time reaches the patched attribute).

Same rule already documented generically in
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)'s
"patch the module that OWNS the function's `__globals__`" entry — this is
a fresh concrete 4-way confirmation of it, useful as a lookup table next
time these exact 4 functions come up again (e.g. Ultron's GREEN pass, or a
future hardening round).

## Selective-double technique reused, generalized into a shared `match=` param

`commits_since_last_consolidation()` makes TWO `run_git` calls per
invocation (`log --grep=...` then `rev-list --count`, only reached if the
first found a commit) — same shape Cerberus's `test_issue61_breadcrumbs.py`
already handles per-site with a bespoke `if args[0] == "rev-list":` double.
Generalized this file's shared helpers
(`_make_flaky_run_git`/`_make_always_failing_run_git`) with an optional
`match(args) -> bool` predicate (default: match everything) so ONE helper
covers both "single call site" functions (match=None) and "isolate call N
of 2" functions (`match=lambda args: args[0] == "log"`) without duplicating
the double's body per site. `fail_times=1` + `match=<log-only>` cleanly
retries ONLY the first call while leaving the second (rev-list) untouched
whenever it's reached for real.

## Gotcha: `extract_glossary()`'s "genuine empty" shape differs from `_scan_commits()`'s

`_scan_commits()` (recall.py) filters via `--grep=<memory-key-pattern>` IN
THE GIT CALL ITSELF — a repo with zero memory commits gets `rc=0,
log_output=""`, hitting the early-return fail-safe (`return []`).
`extract_glossary()` (boot_memory.py) does NOT filter at the git-log level
(scans everything, filters trailers during parsing) — the SAME "no memory
commits" repo still has `log_output` non-empty (the plain `init` commit's
line), so it runs the FULL success path and returns the 4-key dict
(`decisions/memos/remembers/tombstones`), not the 3-key fail-safe dict from
its own early-return branch. A control test that asserts
`result == {"decisions": [], "memos": [], "remembers": []}` (copying the
fail-safe literal) fails for the WRONG reason (missing `tombstones` key) on
a genuinely-successful call. Fix: assert the three list keys individually
(`result["decisions"] == [] and ...`) instead of exact dict equality —
robust to which of the two return shapes (fail-safe vs. success-with-empty-
results) the function actually took.

## Contract file

`unmassk-toolkit/tests/test_issue61_read_retry_contract.py` — 12 tests, 3
per site (retry-recovers-and-round-trips-§34 fused into one test per site
since item 1 and item 4 of the plan's contract are mechanically the same
assertion once the write side uses a real commit; persistent-failure-warns;
genuine-success-no-retry-no-warn control). Verified RED for the right
reason: real exit code 1, exactly the 4 retry tests fail with `entries=[]`/
`count=0` plus the real `rc=128 fatal: not a git repository` breadcrumb
still visible in captured stderr (proof the failure channel is real, not a
faked rc). Sanity-checked `test_issue61_breadcrumbs.py` (the prior WARN
round) is untouched: 16/16 still green after adding this file.

## Hardening round (2nd Dante entry, same file, Ultron already implemented)

Ultron shipped `git_helpers.py::run_git_read_retrying(run_git_fn, args,
**kwargs)` (3 attempts, 0.1s backoff, WARN suppressed on non-final attempts)
plus a wall-clock deadline gate for SEC-HIGH-001 (Argus): `deadline =
time.monotonic() + READ_RETRY_DEADLINE_SECONDS` (== `GIT_TIMEOUT`, 10s),
never starts a new attempt once < `READ_RETRY_MIN_ATTEMPT_SECONDS` (0.5s)
of budget remains. Wrapped 3 more sites: `boot_memory.py::extract_memory()`
(manual-print site, highest blast radius), `hooks/precompact-snapshot.py::
extract_memory_from_log()` (explicit `log_stderr_on_failure=True`, hyphenated
file → subprocess-isolated probe), `boot_git_checks.py::get_last_context_time()`
(explicit kwarg). Extended the SAME file to 28 tests total (all originally-RED
12 now green, confirming Ultron's fix; +16 new: 3×5 tests/site for the 3 new
sites + 3 for the shared helper's deadline logic directly). All 28 pass, real
exit code 0.

**Controlling the clock without a real 10s sleep.** `run_git_read_retrying()`
resolves `time.monotonic()`/`time.sleep()` via the bare name `time` in
`git_helpers.py`'s own module globals (`import time` at file top, called
inside the function body — NOT a deferred per-call import). Patch target:
`monkeypatch.setattr(git_helpers, "time", fake_time_module_instance)` — this
swaps only the NAME bound in `git_helpers`'s namespace, never touches the
real stdlib `time` module globally (unlike `monkeypatch.setattr(git_helpers.time,
"monotonic", ...)`, which WOULD mutate the real module object process-wide
since `git_helpers.time IS` the real stdlib module — confirmed this
distinction before writing the fake, per this file's own established
"patch the name, not a shared object" discipline). `_FakeTimeModule` exposes
`.monotonic()` (returns a manually-advanced counter) and `.sleep()` (records
the call, no real sleep) — the test's own fake `run_git_fn` calls
`fake_time.advance(GIT_TIMEOUT)` before returning `(1, "")`, simulating what
a real hang's internal `subprocess.communicate(timeout=...)` ceiling would
cost, with zero real wall-clock cost to the test suite.

**Mutation-checked, not just written**: neutralized each of the module's TWO
independent deadline checks one at a time (a top-of-loop `attempt > 1 and
...` guard AND a post-failure `... this attempt alone ate the budget` guard —
belt-and-suspenders, either one alone already stops a hang at 1 attempt) —
the hang tests stayed green both times (correctly, since the other check
still covers it), then removed BOTH simultaneously: `test_hanging_first_
attempt_never_starts_a_second_attempt` and `test_hanging_read_bounded_to_
one_attempt_at_site_level` both failed for the right reason (`3 == 1`,
i.e. all `READ_RETRY_ATTEMPTS` ran), while the anti-vacuity companion
(`test_anti_vacuity_fast_failures_still_get_full_retry_budget`) stayed green
throughout (correctly — it tests the OTHER side, unaffected by removing the
gate). Restored the production file from a `/tmp` backup immediately after,
verified `git status --porcelain` clean before reporting — this is the
one-time manual mutation-check discipline already established elsewhere in
this memory file, applied here because SEC-HIGH-001 was flagged as "the
most important part of this pass" by the coordinator and a vacuous pass
would have been the worst possible failure mode to miss.

**WARN-only-after-exhausting, tested on both mechanisms.** Two dedicated
assertions per relevant site (not just "warn appears on persistent
failure", already covered by the completeness pass): (a) a transient that
RECOVERS on attempt 2 leaves stderr completely empty (not even attempt 1's
own failure trace — a real regression here would print a false alarm for a
self-healed flake), (b) a persistent failure prints the WARN text EXACTLY
once (`captured.err.count(needle) == 1`), never once per failed attempt.
Covered on `extract_memory()` (manual `print`, boot_memory.py) and
`get_last_context_time()` (explicit `log_stderr_on_failure=True`,
boot_git_checks.py) — the two mechanisms already documented in
`test_issue61_breadcrumbs.py`'s own module docstring, per the coordinator's
explicit ask to cover one of each rather than all 3 new sites.

## Repair pass (3rd Dante entry) — per-attempt timeout cap broke fixed-signature test doubles

Moriarty found a real hole in the deadline gate: "1st attempt slow-but-real
(consumes ~9.3s of the 10s budget, fails) + 2nd attempt that WOULD hang" —
the old gate only checked "is there enough budget to START a new attempt"
(≥0.5s), so a 2nd attempt starting with 0.7s left could still hang for a
FULL `GIT_TIMEOUT` (no per-attempt cap existed), costing ~2x total. Ultron's
fix: `run_git_read_retrying()` now injects `timeout=max(0.1, min(remaining,
base_timeout))` into EVERY attempt's kwargs unconditionally (not just when
the caller passed `timeout=`) — this broke every `run_git` test double with
a FIXED signature lacking `**kwargs` (`TypeError: unexpected keyword
argument 'timeout'`).

**Full sweep, not just the reported list.** Ultron flagged 6 sites; a broad
grep (`grep -rnE "^\s*def _[A-Za-z_]*run_git[A-Za-z_]*\(" tests/` cross-
checked against every `monkeypatch.setattr(..., "run_git", ...)` site)
found 3 MORE not in the original list:
`test_boot_freshness_hardening.py:541` (`_fake_run_git`, already had an
explicit `timeout=10` param but no `**kwargs` — would break on a future
`log_stderr_on_failure=` too), `test_boot_freshness_regression.py:777`
(`_patched_run_git`) and `:1209` (`_spy_run_git`, spies on `fetch`'s
`timeout` kwarg specifically). Fixed all 9 sites total (6 reported + 3
found) with the SAME minimal pattern: add `**kwargs` to the signature,
change NOTHING else (body/return unchanged) — for the 6
`_patched_run_git(args, cwd=None):` sites (`test_crown.py:158/211`,
`test_crown_retraction.py:223`, `test_boot_output.py:199/246/1011`, all
byte-identical literal text, safe for a `replace_all` Edit each) this
became `(args, cwd=None, **kwargs)`; for the 3 explicit-param doubles that
already delegate to the real `run_git` (`_fake_run_git`/`_spy_run_git`/
`test_boot_freshness_regression.py`'s `_patched_run_git`) the added
`**kwargs` is accepted-and-ignored (never forwarded into the delegate call)
per the coordinator's explicit "don't change the double's logic or return"
constraint — swallowing an extra kwarg silently is correct here since none
of these doubles' own test assertions depend on it reaching the real
`run_git`. Re-verified with a fresh grep after editing: zero remaining
fixed-signature `run_git` doubles anywhere in `tests/` (the 3 hits that
still show up on a naive grep — `_make_flaky_run_git`/
`_make_always_failing_run_git`/`_make_counting_run_git` in this same file —
are FACTORY functions whose returned inner closures already accept
`**kwargs`, not doubles themselves; false positives, confirmed by reading).

**New test: `test_slow_then_would_be_hanging_second_attempt_gets_capped_
timeout`** (same `TestRunGitReadRetryingDeadline` class, `_FakeTimeModule`
reused unchanged) — reproduces Moriarty's exact scenario. The fake
`run_git_fn` RECORDS the `timeout` kwarg it received each call (the central
assertion) and, in the simulated response, advances the fake clock by
EXACTLY that received timeout (modeling what a real hang capped by
`subprocess.communicate(timeout=...)` would cost) — attempt 1 instead
deliberately advances by a fixed 9.3s (a slow-but-real failure, not a hang,
matching Moriarty's reported sequence exactly). Assertions: exactly 2
attempts happen (3rd blocked by the existing "not enough budget to start"
gate); attempt 1 received ≈`GIT_TIMEOUT` (full budget, nothing consumed
yet); attempt 2 received a value `< GIT_TIMEOUT * 0.9` (the actual
regression-locking assertion — proves the CAP, not just the start-gate);
total simulated elapsed stays `≤ GIT_TIMEOUT * 1.1` (proves no 2x blowup).
**Mutation-killed**: replaced `call_kwargs["timeout"] = max(0.1,
min(remaining, base_timeout))` with `call_kwargs["timeout"] = base_timeout`
(the per-attempt cap silently removed, everything else intact) — test
failed for exactly the right reason (`received_timeouts[1] == 10`, not
`< 9`), proving it isn't vacuous. Restored from a `/tmp` backup immediately
after, `git status --porcelain` on the production file confirmed clean
before reporting.

## Completeness close-out (4th Dante entry) — bootstrap_commits.py::scan_recent_commits()

Last of the 9 read-path sites: Ultron wrapped BOTH of `scan_recent_commits()`'s
internal `run_git` calls with `run_git_read_retrying()` (same mechanism
already hardened at the shared-helper level — no need to re-test deadline/
WARN here, only that the retry actually WIRES both calls at this site).
Added `TestScanRecentCommitsReadRetryContract` (3 tests) to
`test_issue61_read_retry_contract.py` — this module imports `run_git` at
MODULE level (`from git_helpers import run_git, run_git_read_retrying`,
same shape as `recall.py`), so the patch target is
`bootstrap_commits.run_git`, never `git_helpers.run_git`.

**Distinguishing the 2 calls that share `args[0] == "log"`**: reused the
exact `--pretty=format:` \x1f-count technique `test_issue61_breadcrumbs.py`'s
`TestScanRecentCommitsBreadcrumb` already established for these same 2 call
sites (2 separators = 1st call, `%h\x1f%aI\x1f%s`; 1 separator = 2nd call,
`%h\x1f%an`) — extracted into 2 tiny top-level `_match_scan_recent_call1`/
`_match_scan_recent_call2` predicates, passed straight into the existing
`match=` param on `_make_flaky_run_git`, no new double-factory needed.

**Self-inflicted test bug caught by running, not assumed**: the 2nd-call
round-trip test initially asserted `all(c["author"] == "Issue61ScanRecent
Author" for c in result["recent"])` — failed because `_make_repo()` already
seeds an "init" commit under a DIFFERENT author ("Test", configured before
this test's own `git config user.name` call), so the repo legitimately has
2 different real authors. Fixed by asserting only the specific "alpha"
commit's author instead of "all recent commits" — same class of gotcha as
the earlier `extract_glossary()` empty-shape fix in this file: don't assume
a fixture repo is author-homogeneous just because one test cares about one
author.

**"Genuine empty" control reframed as "genuine success = 1 call"**, same
convention as `get_timeline()`/`commits_since_last_consolidation()` earlier
in this file: `scan_recent_commits()` always sees at least the `init`
commit (no grep-filtering like `_scan_commits()`), so a truly empty result
is unreachable — the control test instead counts calls per-call-shape
(`calls["call1"]`/`calls["call2"]`, keyed by the same \x1f-count predicates)
and asserts both stay at 1 on a genuine `rc=0` success.

Verified: `TestScanRecentCommitsReadRetryContract` 3/3, full contract file
+ `test_bootstrap.py` 44/44, `test_issue61_breadcrumbs.py` (untouched
sanity check) 16/16 — all real exit code 0. Only the test file changed,
`git status --porcelain` confirms no production code touched.

## Retirement (5th Dante entry) — get_timeline()/get_last_context_time() deleted from production (DEUDA.md #7)

Memory v2's five-block boot (spec §8.3) has no timeline block, so
`boot_git_checks.py::get_timeline()`/`get_last_context_time()` (112 lines,
zero production callers) were deleted from production the same day, along
with their re-export in `boot_checks.py`'s `from boot_git_checks import
(...)` / `__all__` (deleting only the functions without also cutting the
re-export would have cascaded an `ImportError` through
`boot_checks.py` → `boot_health.py`/`boot_render.py` →
`session-start-boot.py` — the whole boot, not just a test). Retired the two
now-dead classes (`TestGetTimelineReadRetryContract`,
`TestGetLastContextTimeReadRetryContract`, 8 tests) from
`unmassk-toolkit/tests/test_read_retry_contract.py` per §9.3 ("borrar los
tests de cada pieza retirada, a la vez que la pieza") — tests only, zero
production lines touched.

**Coverage-loss check done BEFORE deleting, not after.** The read-retry
contract those two classes proved has 3 parts: (a) transient failure
recovers via retry, round-trips real data; (b) persistent failure emits a
visible WARN, never silent; (c) genuine success = exactly 1 call, no retry,
clean stderr. Read the whole file first and confirmed all 3 are still
proved by LIVE code, independently: `TestScanRecentCommitsReadRetryContract`
+ `TestScanRecentCommitsBreadcrumb` (same 3 assertions, at
`bootstrap_commits.py::scan_recent_commits()`) and
`TestRunGitReadRetryingDeadline` (the shared `run_git_read_retrying()`
helper directly — the SAME function every read site, including
`scan_recent_commits()`, calls into; its deadline/budget logic was never
site-specific). Ran the suite BEFORE touching anything: exactly 8 red (the
2 dead classes, `AttributeError: module 'boot_git_checks' has no attribute
...`) + 9 green (everything that survives) — matched the task's claim
exactly, so no coverage was silently lost by this retirement. This is the
generalizable move for any "delete tests for a retired piece" task: don't
just delete on the requester's word that it's safe — reread the file,
name what covers the same contract now, and verify empirically (red count
before == expected dead-test count) before cutting.

Also swept for stray references before finishing: `bootstrap_commits.py`,
`test_boot_git_checks.py`, `test_regression_memory_correctness.py` only
*mention* `get_last_context_time()` in prose/docstrings (dead comments now,
out of scope — no production code, not my file to touch);
`test_migrate_statusline.py` calls `boot_render.get_timeline(10)` inside a
subprocess probe but that whole test was already broken independently (it
also imports `boot_memory`, which memory v2 deleted entirely per this same
file's own docstring) — unrelated pre-existing breakage, not caused by
today's retirement, left untouched (out of the assigned scope).

**Subprocess probe for the hyphenated hook, extended with a `MODE` selector.**
`_PRECOMPACT_EXTRACT_MEMORY_PROBE` (new template, same shape as
`test_issue61_breadcrumbs.py`'s `_PRECOMPACT_BRANCH_FAILURE_PROBE`) patches
`git_helpers.run_git` BEFORE loading `precompact-snapshot.py` via
`importlib.util.spec_from_file_location`, then calls
`mod.extract_memory_from_log()` directly (not `mod.main()` — cleaner return
value than parsing stdout snapshot text) and prints
`json.dumps({"result": ..., "calls": ...})`. `MODE` (`"flaky1"` / `"always"`
/ `"counting"`) parameterizes the SAME double shape used everywhere else in
this file, run inside the isolated subprocess so the monkeypatch never
leaks into the main test process — `extract_memory_from_log()`'s return
dict (`decisions`/`memos`/`pending`/`blockers` — plain dicts/lists, no
tuple-based `(label, text, is_crown)` shape like boot_memory.py) is directly
JSON-serializable, no `_ser()`-style whitelist gotcha here.
