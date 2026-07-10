---
name: issue-61-ci-flake-hardening-notes
description: issue #61 test-side anti-flake hardening (test_drift/test_recall/test_consolidation_trigger) — opaque-rc-swallowing pattern, anti-vacuity retry, mock-signature-drift gotcha, mid-session git-reset incident
metadata:
  type: project
---

## Root cause (House, confirmed)

Ubuntu CI runners (2-core/7GB) building 200-510 commit fixtures via
subprocess fork storms occasionally hit a transient git subprocess
failure. The bug is never in scan logic — it's tests treating partial/
absent stdout as authoritative without checking rc. Windows/macOS never
reproduce (no fork pressure). Same class as issue #52's `run_snapshot()`
fix (rc discarded → opaque downstream count assert).

## Two distinct fix shapes, pick by whether the failure is swallowed

1. **rc verification** (test_drift.py `_git_log_or_fail`): use when the
   caller controls the subprocess directly and a failure SHOULD raise
   rc != 0. Turns `assert 4 >= 12` into `git log exited N: <stderr>`.
2. **Bounded retry with breadcrumb + anti-vacuity** (test_recall.py
   `_recall_with_retry`, test_consolidation_trigger.py
   `_run_boot_with_retry` / `_commits_since_consolidation_with_retry`):
   use when the failure is swallowed BY DESIGN (fail-safe production
   code, e.g. `recall.py::_scan_commits()` returns `[]` on `rc != 0`;
   `git_helpers.py::commits_since_last_consolidation()` returns `0`/
   sentinel on any git error) — rc alone can never surface this class,
   since the wrapping function always "succeeds" with a wrong-looking
   value. Retry must require the FULL expected result (exact needle
   in output, exact count, not just "non-empty") — a genuinely broken
   scan must keep failing after every attempt is exhausted. Pattern:
   `for attempt in range(1, attempts+1): ...; print breadcrumb; if ok:
   return`. On final failure, add a diagnostic (not a substitute
   assertion): re-run the SAME underlying git query directly (reconstructed
   from the module's own constants, e.g. `recall._TOMBSTONE_KEYS` /
   `_MEMORY_KEYS` — never hardcode the grep pattern as a literal) to say
   whether git itself failed vs. the entry genuinely isn't findable.

## Gotcha: local test-double signature drift breaks when production adds a kwarg

`test_consolidation_trigger.py` had 6 copy-pasted local `run_git`
monkeypatch doubles (`_rg`/`_patched_run_git`, cases 02/03/06/09/09b),
each with a FIXED signature `(args, timeout=10, cwd=None)`. When
Ultron's parallel #61 production fix added `log_stderr_on_failure=True`
to the real `run_git()` calls inside `commits_since_last_consolidation()`,
every one of those 6 sites raised a `TypeError` INSIDE the function's own
try/except — silently swallowed by its fail-safe design (`except
(ValueError, TypeError): return 0`), collapsing all 5 affected tests to
"count == 0" with ZERO trace back to the real cause (looked like a
consolidation-counting bug, was actually a mock/production signature
mismatch). Confirmed live both ways: reproduces with Ultron's kwarg
present, silently not-a-bug without it. **Fix**: DRY the 6 duplicates
into one `_load_git_helpers_bound_to_repo(repo, mod_name)` helper whose
patched `run_git` accepts `**kwargs` — a test double wrapping a real
function should always tolerate future keyword-only params on that
function, not hardcode today's exact signature. This is a
test-mock-drift fix (owned by Dante), not a production behavior change.

## Incident: mid-session `git reset` wiped uncommitted work (both agents)

Mid-task, `git reflog` showed `HEAD@{0}: reset: moving to HEAD` — some
parallel process (Ultron's own workflow reset, not confirmed malicious)
wiped ALL uncommitted changes in the shared working tree, including
Dante's just-written test edits AND Ultron's in-progress
`log_stderr_on_failure` production edits. Files silently reverted to
pristine HEAD state — `git status --porcelain` went from several `M`
lines to completely empty. Caught only because a system-reminder showed
stale (pre-edit) file content after a supposedly-successful edit, which
prompted re-reading the files directly rather than trusting the earlier
Edit tool confirmations. **Lesson**: in a shared/parallel-agent working
tree, do not assume an Edit tool's "successfully updated" result is
durable — if there's any signal of external interference (a
system-reminder showing reverted content, an unexpected clean `git
status`), re-read the target files before the final verification pass
and re-apply if needed. Re-ran full ×5 loops per file AND the full
suite again after re-applying, before reporting done.

## Cerberus follow-up (2026-07-11): call-site coverage for the 9 breadcrumbs, not just run_git's own kwarg

Cerberus flagged that `TestRunGitLogStderrOnFailure` (test_boot_freshness_hardening.py,
Popen-mocked) only proves `run_git()`'s `log_stderr_on_failure` kwarg works in
the abstract — it never proves any of the 9 real production call sites
(`recall._scan_commits`, `git_helpers.commits_since_last_consolidation` x2,
`bootstrap_commits.scan_recent_commits` x2, `boot_memory.extract_memory`/
`extract_glossary` — manual print, no kwarg, because those 2 call sites can't
safely pass a new kwarg through the fixed-signature test doubles used
elsewhere — `precompact-snapshot.py` `extract_memory_from_log`/
`format_snapshot` x2) actually wire it up or that a real failure there prints
anything. Closed in `tests/test_issue61_breadcrumbs.py` (16 tests, 9
failure-path + 7 anti-vacuity/success-path, one per production function).

**Reusable pattern: "selective delegate" double for a function with two
internal `run_git()` calls where only the SECOND must fail.** Needed at 3 of
the 9 sites (`commits_since_last_consolidation`'s rev-list call,
`scan_recent_commits`'s author-only call, `format_snapshot`'s branch call —
each only reachable once an earlier call in the same function already
succeeded for real). Shape:
```python
real_run_git = <module>.run_git
def _selective_fail(args, **kwargs):
    if <condition identifying the call to break>:
        kwargs["cwd"] = broken_dir  # real dir, no .git anywhere upward
    return real_run_git(args, **kwargs)
monkeypatch.setattr(<module>, "run_git", _selective_fail)
```
Always delegate to the REAL `run_git` (never reimplement the print) so the
breadcrumb text asserted on is production code actually executing, not a
test-authored stand-in. Always accept `**kwargs` (see the mock-signature-drift
gotcha above in this same file) — never a fixed positional/keyword signature.
`kwargs["cwd"] = broken_dir` reliably reproduces a real `rc=128 fatal: not a
git repository` from a real git subprocess; no faked returncode ever needed.
Distinguishing which of two same-named calls to break: `git_helpers.py` by
`args[0]` (`"log"` vs `"rev-list"`), `bootstrap_commits.py` by counting `\x1f`
in the literal `--pretty=format:` string (2 separators = first call's
`%h\x1f%aI\x1f%s%n%b`, 1 = second call's `%h\x1f%an`), `precompact-snapshot.py`
by `args[0] == "branch"`.

**Gotcha: `precompact-snapshot.py`'s `format_snapshot()` branch call is only
reachable when memory is non-empty.** `main()` does
`if not memory: sys.exit(0)` right after `extract_memory_from_log()` — a
repo-level failure (no commits, broken `.git`) never reaches
`format_snapshot()`'s own `run_git(["branch", ...])` call at all. To exercise
that specific breadcrumb you need a repo with a REAL commit (so
`extract_memory_from_log()` succeeds and `has_content` is true), with only the
`branch` subcommand redirected to a broken cwd via the selective-delegate
double above — loaded through `importlib.util.spec_from_file_location` inside
an isolated `subprocess.run([sys.executable, "-c", script], ...)` (never
in-process) so the `git_helpers.run_git` monkeypatch can't leak into the main
test process's `sys.modules` between test functions.

**Which sites need a real broken-repo dir vs. `monkeypatch.chdir()`:**
functions with an explicit `repo_dir`/`cwd` parameter (`_scan_commits`,
`commits_since_last_consolidation`) take a real non-git directory as an
argument directly — no chdir needed. Functions with NO cwd param
(`scan_recent_commits`, `extract_memory`, `extract_glossary`) rely on ambient
process cwd — use `monkeypatch.chdir()` (auto-restored, matches the
established pattern already documented in
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)).

**Verified 2026-07-11**: new file ×5 loops (16/16 every run), new file +
`test_boot_freshness_hardening.py` + `test_consolidation_trigger.py` together
(111/111), full suite `python3 -m pytest unmassk-toolkit/tests -q` run in
background (same >2min timeout caveat as below) — all real exit codes
checked individually, never piped to `tail`/`head`.

## Verification numbers (2026-07-11)

`test_drift.py` ×5, `test_recall.py` ×5, `test_consolidation_trigger.py`
×5 — all green, real exit codes checked individually (never piped to
tail/head). Full suite `python3 -m pytest unmassk-toolkit/tests -q`:
1246 passed, 2 skipped (Windows-only), 0 failed, exit code 0
(289s runtime — needs a >2min bash timeout, the default 120s times out
mid-run and looks like a hang, not a failure).
