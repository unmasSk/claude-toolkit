---
name: feat-boot-freshness-contract-notes
description: Boot memory freshness (multi-machine, issue #49) acceptance contract — fixture design, RED baseline, what Ultron/Cerberus/Argus/Moriarty/Yoda still owe
metadata:
  type: project
---

Plan: `docs/plan/feat-boot-freshness.md` (issue #49). Build mode: test-first.
Contract file: `unmassk-toolkit/tests/test_boot_freshness.py` (Dante, Task 1,
session 2026-07-06) — 12 pytest methods covering the plan's 8 acceptance
tests, ALL confirmed genuinely RED against the unmodified code (clean
`AssertionError`s, no fixture crashes), 0 regressions in the pre-existing
suite (863 passed, 9 pre-existing unrelated `test_release.py` failures —
same known baseline as prior rounds, see
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)).

**Why:** the boot hook (`hooks/session-start-boot.py`) already runs an
unhardened, ungated, unthrottled `git fetch --quiet` on every boot, but
`lib/boot_memory.py:extract_memory()` only ever reads local HEAD — a second
machine's newer memory commits are invisible until a manual pull, and the
existing fetch has no protection against a hanging/prompting remote.

**How to apply — fixture model, for Ultron and whoever re-touches this file:**

- Two-machine fixture is `_setup_freshness_repo(tmp_path)` (machine A: repo +
  bare remote + toolkit install, committed so the tree starts CLEAN) +
  `_clone_machine_b(bare, tmp_path)` (machine B, called separately). These
  are deliberately split — an earlier draft cloned B eagerly inside the
  setup helper and hit a real non-fast-forward push failure when a test
  added more commits to A *after* the clone point but before B pushed.
  Always clone B only after any A-only setup commits are already pushed.
- B creates commits with plain `git commit -m` using the REAL emoji +
  `type(scope): message` + trailer format (`_commit_real()` helper,
  EMOJIS dict mirrors `bin/git-memory-commit.py`'s own) — hooks never run
  in these temp repos, so there is no wrapper script to invoke for B.
- The install step leaves CLAUDE.md/.gitignore untracked on disk; if not
  committed, EVERY "clean tree" test starts dirty for the wrong reason
  (untracked install artifacts, not the test's own intentional dirty file).
  `_setup_freshness_repo()` commits+pushes them once, guarded by a `git
  status --porcelain` check (skip the commit if genuinely nothing changed).
- Fake-`git`-on-PATH technique for tests 4 (hardening env + timeout) and 5
  (fetch gate) — see
  [mock-patterns.md](mock-patterns.md) for the full pattern. POSIX-only,
  skipped on Windows.
- Rate-limit tests (6) manipulate `.git/FETCH_HEAD` mtime directly via
  `os.utime()` after seeding it with one real `git fetch` — no fake git
  needed there, real local-bare-remote fetches are fast and deterministic.
- "Fetch failed" state (test 2's third variant) uses a nonexistent local
  path as the remote URL, NOT a real dead-port network address — avoids any
  sandboxed-CI network/loopback ambiguity while still forcing a real,
  deterministic `git fetch` failure.
- Marker naming pitfall: see
  [edge-cases.md](edge-cases.md)'s "echoes back into output" entry — any
  marker text used near a `re.search(r"remot"/"behind"/...)` assertion must
  NOT itself contain that keyword, or the assertion passes vacuously before
  the feature exists. Caught and fixed twice in this file before the final
  RED run (`INCIDENT_NEXT_MARKER`, `b_remote_marker`, and the write-path
  commit message all originally embedded the keyword being searched for).

**What the RED baseline proves is still missing** (for Cerberus/Argus/
Moriarty/Yoda downstream in this same pipeline — don't re-derive, read the
test failures directly): no `MEMORIA:` freshness stamp anywhere; no fetch
gate (fetch runs even without toolkit memory installed); no rate-limit
(FETCH_HEAD mtime always advances); no env hardening on the fetch subprocess
call; `extract_memory()` is HEAD-only (never reads `origin/<branch>`, so a
behind machine can never see the other side's newer Next, and a diverged
machine only ever shows its own local side); no "first action" / "do not
pull while dirty" directive text; `bin/git-memory-commit.py` has zero
behind-check on memory writes.

See also: [boot-stdout-banner-contract-notes](boot-stdout-banner-contract-notes.md),
[skill-router-contract-notes](skill-router-contract-notes.md) (same
"test-first contract, RED baseline documented for the rest of the pipeline"
shape, same module family).

## Hardening pass (session 2026-07-06) — `test_boot_freshness_hardening.py`

After Ultron implemented (wips 98862f1, 578ffc6, 9990410), the 12-test
contract went 12/12 green untouched. Hardening pass added 68 tests (67
passed + 1 `xfail(strict=True)`) covering 15 functions directly: `fetch_
memory_ref`, `get_ahead_behind`, `_format_age_seconds`, `render_memoria_
stamp`, `_build_pull_directive_lines`, `_has_toolkit_memory`, `_fetch_head_
age_seconds` (`lib/boot_git_checks.py`); `extract_memory(ref=)`, `resolve_
boot_memory`, `_label_remote_provenance`, `_merge_diverged_memory` (`lib/
boot_memory.py`); `_resolve_origin_sha`, `_read_glossary_cache` migration
(`lib/boot_glossary_cache.py`); `run_git`'s `env=` kwarg (`lib/git_helpers.
py`); `_check_behind_warn_only` (`bin/git-memory-commit.py`). 0 regressions
in the pre-existing suite (872 passed, same baseline as before).

**Direct-call decision tree confirmed workable for this module family**
(faster than full-boot subprocess, used wherever safe): pure functions
(`_format_age_seconds`, `render_memoria_stamp`, `_build_pull_directive_
lines`, `_label_remote_provenance`, `_merge_diverged_memory`,
`_resolve_origin_sha(None)`) called in-process with no I/O; functions
taking an explicit `project_root`/`cwd` param (`fetch_memory_ref`, `_has_
toolkit_memory`, `_fetch_head_age_seconds`) called directly with a real
tmp_path repo, no chdir; functions relying on ambient process cwd (`get_
ahead_behind`) called via `monkeypatch.chdir()` (auto-restored, no
cross-test bleed). Full detail (including the `_project_root_cache` global
gotcha and the confirmed real bug) in
[mock-patterns.md](mock-patterns.md) and [edge-cases.md](edge-cases.md).

**Bug found, reported, NOT fixed (Absolute Prohibition #4):**
`lib/boot_git_checks.py:get_ahead_behind()` — the `int(parts[0]), int(parts
[1])` conversion when `git rev-list --left-right --count` returns exactly
two tokens has no try/except, so non-numeric tokens raise an uncaught
`ValueError` instead of falling through to the function's own existing
`(0, 0, upstream_ref)` safe-fallback (used one line below for the
wrong-token-COUNT case). Pinned as `test_non_numeric_rev_list_output_
should_fail_open_but_raises` with `@pytest.mark.xfail(strict=True, ...)` —
will flip to a hard failure the moment Ultron fixes it, forcing a test
update (same idiom as the fd-leak bug in mock-patterns.md's "FIXED" entry).
**Update (session 2026-07-06, regression pass):** Ultron fixed this — the
`xfail` marker was removed and the test now asserts the safe fallback
directly (confirmed green in the repair-round regression run below).

## Regression pass (session 2026-07-06) — `test_boot_freshness_regression.py`

Moriarty (T2) flagged that the repair-round fixes for issue #49 had zero
regression coverage in CI. New file (96 total across the 3 boot-freshness
files, 0 regressions), 10 methods / 11 cases, one per confirmed break:
clock-skew future-mtime gate (`fetch_memory_ref`'s `0 <= age < window`),
decoupled-stamp tracking-ref alignment (incoherent `branch.main.merge` must
never claim "remote (fetched)"), renamed-remote liveness check (`git remote
rename origin upstream` must still fetch — regression guard against a
hardcoded `"origin"` literal creeping back into the liveness check),
`REMOTE_PROVENANCE_LABEL` English-literal pin (guards against the original
Spanish wording reappearing), POSIX process-group kill-tree (fake `git`
spawns a real grandchild via `subprocess.Popen`, `run_git`'s timeout must
`os.killpg()` the whole group — see the new fake-git-with-grandchild helper
pattern below), and `_ASKPASS_FAILFAST` PATH-resolution (`subprocess.run
(["false", "x"])` must exit non-zero with no exec error). All 6 pin the
FIXED code in HEAD — no bug found in this pass.

**New reusable technique — fake `git` that spawns a real grandchild, to
test process-group kill without mocking `os.killpg` itself:** extends the
existing "fake git on PATH" pattern (see mock-patterns.md) one step
further: the fake git script itself calls `subprocess.Popen(...)` (NOT
`start_new_session=True`) to spawn a real sleeping grandchild, writes the
grandchild's pid to a file, then hangs itself. Because the fake git was
launched by `run_git` with `start_new_session=True`, it is the leader of a
fresh POSIX process group; a child it spawns normally (no `setsid` of its
own) inherits that SAME group. `run_git`'s timeout path calls
`os.killpg(getpgid(fake_git_pid), SIGKILL)` — if that call only killed the
direct child, the grandchild would survive; polling `os.kill(pid, 0)` for
up to 5s after `run_git` returns proves whether the whole tree actually
died. No `os.killpg` mock involved anywhere — this observes the REAL
kernel-level process-group signal delivery.

**Windows gap, explicitly NOT covered (documented, not a trivial-pass
substitute):** `_win32_kill_tree()` (taskkill /F /T) and the win32 value of
`_ASKPASS_FAILFAST` ("cmd /c exit 1", a full command-line string rather
than a bare executable name) have zero real Windows machine to test
against in this environment, and mocking `subprocess.run` to assert
`_win32_kill_tree` "calls taskkill with the right args" would only prove
the mock was configured correctly — logic-review only, per this project's
own "Coverage Boundaries" rule against tests whose only assertion is mock
configuration.

## Second regression pass (session 2026-07-06) — T2 repo-identity confusion

Same `test_boot_freshness_regression.py` file, extended (not a new file)
after Ultron closed a SECOND T2 finding: a misconfigured `origin` that
resolves cleanly (`@{u}` works, fetch succeeds, branch name matches) but
shares ZERO commit history with local HEAD must never have its content
rendered as this project's own memory. Fix under test:
`check_upstream_shares_history()` (`lib/boot_git_checks.py:449`, `git
merge-base -- HEAD <ref>`, fail-closed-on-trust — every non-zero exit,
including a shallow-clone false negative, collapses to "not confirmed
shared"), `render_memoria_stamp(history_related=...)` (:661, short-
circuits to a fixed "MEMORY: LOCAL — upstream unrelated..." string),
`session-start-boot.py` main()'s upstream_ref-nulling (:315-333), and
`extract_glossary(exclude_remote=...)` / `_is_safe_remote_name()` (`lib/
boot_memory.py:319,340` — `--exclude=refs/remotes/<name>/*` closes the
SECOND, unlabeled leak surface the labeled resolve_boot_memory() path
doesn't share).

**Reusable fixture — "foreign bare repo, zero shared history, same remote
NAME":** `_build_foreign_bare_with_crowned_content()` +
`_setup_foreign_upstream_scenario()`. Build the foreign content as its own
independent `git init --bare` + clone + commit lineage (real crowned
Decision via `_commit_real(..., {"Decision": marker, "Crown":
"Decision"})` + a real `Next:` context commit), THEN `git remote set-url
origin <foreign_bare>` on an otherwise-normal `_setup_freshness_repo()`
repo. Repointing the URL of the SAME remote name is deliberate — it keeps
`branch.main.remote`/`.merge` tracking config coherent (git never
re-derives tracking from a remote's URL), reproducing the exact
misconfiguration shape the guard exists to catch, without needing to hand-
craft `.git/config` directly. Verified via THREE channels in the same
test: (a) the stamp string is an exact match regardless of fetch status,
(b) both marker strings absent from combined stdout+boot-log output
(covers both leak surfaces at once), (c) an independent `git merge-base
HEAD origin/main` (run directly by the test, not through the code under
test) confirms exit 1 — proves the scenario is genuinely unrelated, not
just "the guard says so."

**`check_upstream_shares_history()` unit tests don't need a remote/clone at
all** — an orphan branch in a single throwaway repo (`git checkout
--orphan unrelated`) is a sufficient "no common ancestor" fixture, and a
plain sibling branch off the same commit is sufficient "shared history."
Both need `monkeypatch.chdir(repo)` since the function's own `run_git`
call passes no `cwd=` (relies on ambient process cwd, same as
`get_ahead_behind()`).

**Mutation-style proof for the second leak surface:** rather than only
trusting the full-boot scenario, `_extract_glossary_direct(repo,
exclude_remote=...)` calls `boot_memory.extract_glossary()` directly (out-
of-process subprocess isolation, same reasoning as
`test_boot_output.py::_extract_glossary()` — never in-process, this is a
stably-named module reused across the whole test session) with BOTH
`exclude_remote=None` (proves the leak is real — the function's own
default call shape) and `exclude_remote="origin"` (proves the guard closes
it). Confirmed empirically before writing assertions.

**New confirmed gap found, reported via `xfail(strict=True)`, NOT fixed
(Absolute Prohibition #4):** the PULL DIRECTIVE line
(`_build_pull_directive_lines()`, built from raw `ahead_n`/`behind_n` by
`render_branch_section()`) runs BEFORE
`check_upstream_shares_history()` in `main()` (:302 vs :318), and `main()`
never revisits `pull_directive_lines` after learning the upstream is
unrelated — only `upstream_ref` gets nulled (affecting the memory-read and
glossary paths, not the branch-section's own already-built lines). Verified
empirically (see the manual repro below) against real HEAD code: a
foreign, zero-shared-history upstream still prints "PULL DIRECTIVE: local
is N commit(s) behind — propose \`git pull\`..." — actively bad advice,
since pulling would try to merge in a totally unrelated commit graph.
Pinned as `TestPullDirectiveGapForUnrelatedUpstream::
test_pull_directive_never_recommends_pull_for_unrelated_upstream`.

## Third regression pass (session 2026-07-07) — Finding 8, Yoda #49 close-out

`time_ago()` (`lib/boot_git_checks.py:65`)'s `except` tuple was
`(ValueError, TypeError, OSError)`; Moriarty demonstrated live that its own
`isdigit()` branch feeds `int(...)` straight into `datetime.fromtimestamp()`,
which raises `OverflowError` (not `ValueError`) for a digit string whose
value is out of range for the platform's `time_t` — Python ints themselves
never overflow, only the C-level `fromtimestamp()` conversion does. Ultron
fixed it (commit 6fc6386) by adding `OverflowError` to the tuple. Currently
dead code in production (`git log %aI` only ever feeds ISO8601 into the
`else` branch) — pinned anyway as defense-in-depth per Yoda's verdict.
Pinned in `test_boot_freshness_regression.py`'s new `TestTimeAgoOverflow
FallsBackSafely` (Finding 8): 2 OverflowError cases (`"9"*30`, `"9"*12`) +
3 companion pre-existing-tuple cases (`not-a-date`, empty string, invalid
calendar fields) — the latter three exist because **no direct unit test of
`time_ago()`'s error path existed anywhere before this pass**; the only
prior coverage was `test_boot_output.py::TestBootTimeAgo`, which only
asserts a *valid* commit date renders a time-ago string, never touching the
except branch at all. RED confirmed via a standalone sandboxed copy of the
function with the OLD 3-member tuple (never edited the real file to check
this) — `time_ago("9"*30)` raises uncaught `OverflowError: timestamp out of
range for platform time_t` without the fix, returns `"unknown"` with it.

## FETCH_TIMEOUT_SECONDS 3s -> 10s (session 2026-07-10, decision b2a32b9)

Small test-first change, contract-then-implement in parallel (Ultron had
already landed `FETCH_TIMEOUT_SECONDS = 10` at `lib/boot_git_checks.py:442`
by the time this pass ran). **Gotcha that would have silently broken two
existing hardening/contract tests if not caught**: both
`test_boot_freshness.py::TestFetchHardening::
test_fetch_uses_hardened_env_and_bounded_timeout` and
`test_boot_freshness_hardening.py::TestFetchMemoryRefStates::
test_hung_fetch_is_bounded_by_timeout_and_returns_failed` hardcoded the fake
`git`'s `FAKE_GIT_FETCH_HANG_SECONDS` to `"8"`, tuned against the OLD 3s
timeout (8s comfortably exceeds 3s, so the timeout — not the fake sleep
finishing — is what ends the fetch). Once the real timeout rose to 10s, an
8s hang no longer exceeds it: the fake fetch would just complete on its own
(exit 0) at ~8s, so the assertion `result["status"] == "failed"` /
`elapsed < 6` would flip to false and the test would falsely appear to
prove nothing about the timeout at all — a change to production made an
*unrelated-looking* test constant silently stale. Both fixed to derive the
hang length from `FETCH_TIMEOUT_SECONDS + 20` (import the constant, never a
second hand-typed literal) and to bound `elapsed` against
`FETCH_TIMEOUT_SECONDS + 5` — self-adjusting if the constant changes again.
**Lesson: when a timeout/threshold constant changes, grep for every fixture
that races against it (hang/sleep durations, `elapsed <` assertions), not
just literal `== <old value>` assertions on the constant itself** — those
are the ones that go quietly stale instead of failing loudly.

New regression pin: `TestFetchTimeoutSecondsRaisedTo10` (Finding 9,
`test_boot_freshness_regression.py`) — two tests: (1)
`FETCH_TIMEOUT_SECONDS == 10` directly, (2) a spy on `git_helpers.run_git`
(delegates to the real function, only records the `timeout=` kwarg when
`args[0] == "fetch"`) proves `_run_hardened_fetch()` genuinely threads
`FETCH_TIMEOUT_SECONDS` itself into the real call — not a second,
independently hand-typed `10` that only coincidentally matches today. Spy
pattern mirrors the pre-existing `_fake_run_git` idiom in
`test_boot_freshness_hardening.py::TestGetAheadBehind::
test_non_numeric_rev_list_output_should_fail_open_but_raises`.

## Issue #60 — rate_limited relabel, RED contract (session 2026-07-10, decision ceef426)

Test-first Task 1. `rate_limited` (FETCH_HEAD < 300s = memory already fresh,
a GOOD state) was mislabeled `MEMORY: LOCAL — fetch skipped (rate-limit,
{age} ago)` — read as a failure. New contract: `MEMORY: remote (synced
{age_txt} ago)` (`?` for `age=None`), never containing `LOCAL` or
`skipped`. Real failure states (`failed`/`no_remote`/age-None) are
UNCHANGED — do not touch those literals when relabeling a rate-limit-shaped
bug in this module again.

Two files touched: `test_boot_freshness_hardening.py::TestRenderMemoriaStamp::
test_states_and_ages` (2 parametrize literals updated) and
`test_boot_freshness.py::TestFreshnessStampThreeStates::
test_rate_limited_state_shows_remote_synced_stamp_not_local` (renamed from
`test_rate_limited_state_shows_stamp` — old name/assertion
`re.search(r"rate.?limit|skipped", combined)` would have passed vacuously
forever since both the OLD and NEW wording contain neither "rate-limit" nor
"skipped" as a hard requirement in the old regex — the old assert was a
loose substring match over stdout+log combined, not the actual `MEMORY:`
line. Fixed to extract the real `MEMORY:` line via the file's existing
`_line_with()` helper and assert `.startswith("MEMORY: remote (synced ")` +
absence of `LOCAL`/`skipped` on that exact line — same "marker leaks into
its own assertion" family of bug as the "echoes back into output" entry in
edge-cases.md, just the inverse (loose regex, not embedded marker).

**Double-boot-rapid gap folded into the same test, not a new one:** the
original bug was SessionStart multi-firing and the LAST boot's write to
`boot-log-latest.txt` (the persisted FILE, not just that process's stdout)
carrying the bad label. Added a second block of assertions in the same test
against `log_content` specifically (the file's own contents, read via
`_read_boot_log()`), not just the `combined` stdout+log blob — this is the
real regression shape, so it belongs in the same real two-boot fixture
rather than a separate synthetic test.

RED confirmed: `python3 -m pytest unmassk-toolkit/tests/
test_boot_freshness_hardening.py unmassk-toolkit/tests/test_boot_freshness.py
unmassk-toolkit/tests/test_boot_freshness_regression.py -q` → 3 failed
(exactly the touched tests, clean `AssertionError`s comparing old text vs
new contract) + 124 passed + 2 skipped (pre-existing Windows-only guards,
same 2 as always — see the "Windows gap" note above). Exit code checked
directly (no `| tail`/`| head`), per this repo's hard rule.

## Issue #60 — hardening pass on the seam, post-GREEN (session 2026-07-10)

After Ultron's relabel landed (wip d630e14), ran EXHAUSTION on the
boot→FETCH_HEAD/boot-log→next-boot seam. Key finding: the plan's design
argument ("no pisar estado más fresco" is satisfied for free by the
relabel, no cross-boot comparison machinery needed) rests entirely on
`_fetch_gate_and_rate_limit()` short-circuiting on FETCH_HEAD's age
BEFORE ever resolving/touching the remote — that specific invariant had
zero test coverage before this pass, at either the unit or the real-
subprocess level. Closed with 4 new tests, 0 duplicated:

- `test_boot_freshness.py::TestRateLimitedStampSurvivesRemoteBreakage`
  (real subprocess boot, §34) — two tests sharing a
  `_seed_good_fetch_then_break_remote()` helper (real fetch succeeds,
  THEN `git remote set-url origin <nonexistent path>`): (1) second boot
  INSIDE the 300s window still reads `MEMORY: remote (synced ... ago)`,
  never `fetched` (proves no refetch was even attempted) — checked on
  both `combined` (stdout+log) AND `log_content` alone (the persisted
  boot-log-latest.txt FILE, issue #60's original bug shape); (2) second
  boot PAST the window (FETCH_HEAD mtime rewound via `os.utime`, same
  pattern as the pre-existing rate-limit tests) DOES attempt a real
  refetch, fails against the broken remote, and correctly falls back to
  `MEMORY: LOCAL — last fetch ... ago, unverified` (age preserved from
  the prior good sync — distinct from the "never synced" wording, which
  is reserved for a repo with no prior successful fetch at all) — same
  dual-channel (combined + log_content) check.
- `test_boot_freshness_hardening.py::TestFetchMemoryRefStates::
  test_age_just_inside_window_is_rate_limited` /
  `test_age_just_outside_window_forces_refetch` — direct `fetch_memory_ref()`
  calls pinning the EXACT `0 <= age < FETCH_RATE_LIMIT_SECONDS` boundary
  (299s → still rate-limited + stamp text asserted; 301s → real refetch,
  status flips to `fetched`). Prior boundary tests only ever used age~0s
  ("immediate") or window+60s ("comfortably stale") — never the two
  seconds straddling the literal edge. 1s margin around the boundary is
  safe in practice (`os.utime` → function call is microseconds, not a
  real race) — confirmed stable across 3 repeated runs before reporting.

**Verified NOT a gap (avoided duplicating)**: `fetch_memory_ref()`'s
"fetch OK → remote breaks → PAST window → fails, age preserved" *status
dict* shape was already pinned directly by pre-existing
`TestFetchMemoryRefStates::test_fetch_failure_returns_failed_with_prior_age`
— but only at the dict level, never through the real boot subprocess nor
against the rendered stamp TEXT nor the persisted file. The new
`test_past_window_broken_remote_reverts_to_local_unverified_with_age`
above is the seam-level complement, not a duplicate, of that dict-level
test.

pytest-cov / coverage module not installed in this environment — no
tool-reported percentage available; coverage verified by manual branch
enumeration against `_render_confirmed_fetch_stamp` (3 branches),
`render_memoria_stamp` (4 branches), `_fetch_gate_and_rate_limit` (3
branches + the boundary edge), all represented pre- and post-pass.

Full suite after this pass: `python3 -m pytest
test_boot_freshness.py test_boot_freshness_hardening.py
test_boot_freshness_regression.py -q` → 131 passed, 2 skipped
(same pre-existing Windows-only guards), exit 0. No bugs found in this
pass (pure coverage-closing, no new break).

## Issue #60 AMENDMENT v2 — own-success-stamp RED contract (session 2026-07-10, decision 90d096d)

Moriarty broke v1's relabel (still valid, untouched): the SOURCE of the
freshness signal was always `.git/FETCH_HEAD`'s mtime, which (A) a FAILED
fetch also truncates+refreshes (confirmed empirically first, via a bare
shell repro, BEFORE writing any test — a nonexistent-path remote's `git
fetch` exits 128 but still creates/truncates FETCH_HEAD to 0 bytes with a
fresh mtime, even on a repo that never had a prior successful fetch), and
(B) a successful fetch to an UNRELATED remote also touches (FETCH_HEAD is
not per-remote). v2: boot writes its OWN success stamp (location/format is
Ultron's implementation choice — every new test asserts only observable
boot BEHAVIOR: the MEMORY: line's wording, and whether a real `git fetch`
subprocess call was actually attempted, never the stamp file's own
name/shape). New class `test_boot_freshness.py::
TestOwnSuccessStampNotFetchHeadMtime` (4 tests, all real-subprocess §34,
inserted after `TestRateLimitedStampSurvivesRemoteBreakage`):

- **Vector A** (`test_vector_a_failed_fetch_never_falsely_rate_limits_next_boot`):
  origin broken from before boot #1 ever runs → boot #1 fails/LOCAL
  (sanity, passes today) → boot #2 immediate (<300s, fake-git installed
  only for boot #2 to count fetch attempts without touching boot #1's real
  behavior): must NOT say "remote (synced" and must have retried the fetch
  (fake-git log non-empty). RED today: `'MEMORY: remote (synced 0s ago)'`,
  zero fetch attempts recorded in boot #2 (the old gate short-circuits on
  FETCH_HEAD's freshly-refreshed mtime before ever calling fetch again).
- **Vector B** (`test_vector_b_unrelated_remote_fetch_never_falsely_rate_limits`):
  a real `git fetch secondary` (an unrelated second bare remote, added and
  fetched directly, bypassing the hook) touches FETCH_HEAD; boot #1 (never
  fetched origin via the hook before) must still perform + record a real
  `fetch origin` call and say "remote (fetched", never "synced". RED
  today: same false "synced 0s ago", zero fetch calls recorded.
- **Vector D** (migration, `test_vector_d_migration_external_origin_fetch_without_own_stamp_still_fetches`):
  same shape as B but the EXTERNAL fetch targets origin itself (simulates
  a pre-v2 upgrade / IDE auto-fetch) rather than a foreign remote —
  deliberately distinct from B to prove the fix keys off "does the own
  stamp exist" and not "was a different remote name involved". Explicitly
  documented as fine to collapse into the same code path as B in the real
  implementation — kept as two tests anyway since they pin the invariant
  from two angles.
- **Round-trip discriminant** (`test_round_trip_own_stamp_survives_fetch_head_deletion`):
  boot #1 real successful fetch → delete `.git/FETCH_HEAD` outright (not
  aged, gone) → boot #2 still inside the window must STILL say "remote
  (synced ..." (own stamp untouched by FETCH_HEAD's disappearance). RED
  today: deleting FETCH_HEAD forces a genuine new fetch under the old
  mtime-sourced gate, flipping the status back to "fetched" instead —
  `memory_line2 == 'MEMORY: remote (fetched 0s ago)'`, fails the
  `.startswith("MEMORY: remote (synced ")` assertion. This is the test
  that turns the "boot OK, boot again inside window → synced" round trip
  (which already passes today via the WRONG mechanism, so alone proves
  nothing) into a genuine discriminant between the two possible sources.

Empirical pre-check (via a scratch shell repro, not part of the test
suite) confirmed FETCH_HEAD's truncate+refresh-on-failure behavior BEFORE
any test was written — this is real git behavior (upload-pack round trip
never starts against a nonexistent local path, yet FETCH_HEAD still gets
touched), not a bug in this project's code, so the fix cannot "correct
git" — it must stop trusting the file at all for freshness claims.

RED confirmed exactly as predicted: `python3 -m pytest
test_boot_freshness.py test_boot_freshness_hardening.py
test_boot_freshness_regression.py -q` → 4 failed (only the 4 new tests,
clean AssertionErrors with the exact predicted wrong string) + 131 passed
+ 2 skipped (same pre-existing Windows-only guards). v1 contract (relabel
wording, rate_limited-boundary, remote-breakage-within-window) untouched
and still fully green.

**v1 tests that assume FETCH_HEAD's mtime IS the gate's source (via
`os.utime` on `.git/FETCH_HEAD` directly, or via a raw `git fetch` done
outside the hook to seed it) — flagged for Ultron to re-base onto the new
own-stamp file once v2 lands, NOT touched by this pass**:
- `test_boot_freshness.py::TestFetchRateLimit::test_fresh_fetch_head_skips_fetch`
  — seeds FETCH_HEAD via a raw `git fetch origin` (bypassing the hook) and
  asserts the boot must SKIP its own fetch. **Directly contradicted by the
  new Vector D contract** — this is the single test most likely to need a
  real behavior change (not just a re-seed), since v2 requires the OPPOSITE
  outcome for this exact setup shape.
- `test_boot_freshness.py::TestFetchRateLimit::test_stale_fetch_head_runs_fetch`
  — ages FETCH_HEAD via `os.utime` to force a refetch.
- `test_boot_freshness.py::TestRateLimitedStampSurvivesRemoteBreakage::
  test_past_window_broken_remote_reverts_to_local_unverified_with_age` —
  ages FETCH_HEAD via `os.utime` to force the post-window refetch (the
  window-entry seed itself is a real boot, fine; only the "past window"
  aging step targets the wrong file under v2).
- `test_boot_freshness_hardening.py::TestFetchMemoryRefStates::
  test_stale_fetch_head_past_window_allows_refetch` /
  `test_age_just_inside_window_is_rate_limited` /
  `test_age_just_outside_window_forces_refetch` /
  `test_fetch_failure_returns_failed_with_prior_age` — all four seed via a
  real `fetch_memory_ref()` call then directly `os.utime()` FETCH_HEAD to
  hit a specific age/boundary.
- `test_boot_freshness_regression.py::TestClockSkewFutureFetchHeadMtime::
  test_future_mtime_never_rate_limits` / `test_mtime_exactly_now_still_
  rate_limits` — clock-skew tests keyed entirely on FETCH_HEAD's mtime.

**NOT flagged (checked, still fine under v2, no dependency on WHICH file
carries the signal)**: `test_boot_freshness_hardening.py::
TestFetchMemoryRefStates::test_successful_fetch_returns_fetched_with_zero_age`
(only checks git's own FETCH_HEAD-on-fetch side effect, unrelated to gate
source) and `::test_immediate_second_call_is_rate_limited` (calls the real
function twice in-process, no direct file manipulation — structurally
agnostic to where the signal lives); `TestFetchHeadAgeSeconds` (tests the
low-level `_fetch_head_age_seconds()` helper directly — likely survives as
a utility, e.g. for the "fetched Ns ago" age report on a just-completed
real fetch, independent of the gate's own source-of-truth change).

## Issue #60 v3 — own-stamp identity RED contract (session 2026-07-10, decision 787b698)

Moriarty v2: 14/15 vectors held, broke a new one (T1). `_read_own_stamp_
age()` (`lib/boot_git_checks.py:665-722`) compared identity ONLY by alias
(`data.get("remote")`/`data.get("branch")`, e.g. `"origin"`/`"main"`) —
those are conventional names, not identity. Copying `boot-fetch-stamp.
json` from a genuinely-synced repo A into an unrelated repo B that merely
shares the alias convention (template/backup/dotfiles-sync scenario) made
B's boot claim `MEMORY: remote (synced 0s ago)` without B ever reaching
its own remote. v3 fix (Ultron's job, not yet landed at the time this
contract was written): identity must include the real remote URL (`git
remote get-url`), and an unrecognized `schema_version` must collapse to
the same "no evidence" outcome as a missing stamp.

New class `test_boot_freshness.py::TestOwnStampIdentityIncludesRemoteURL`
(2 tests, real-subprocess §34, inserted right after
`TestOwnSuccessStampNotFetchHeadMtime`):

- **PoC test** (`test_stamp_copied_between_repos_with_matching_alias_but_
  different_remote_url_is_not_trusted`): two independent `_setup_
  freshness_repo()` sites under the SAME `tmp_path` via subdirs
  (`tmp_path / "site_a"`, `tmp_path / "site_b"` — `_setup_freshness_repo()`
  only ever does `tmp_path / "repo_a"` / `"bare.git"` internally, so two
  calls under the SAME bare tmp_path would collide on those hardcoded
  names; passing a subdir Path as the `tmp_path` param sidesteps this with
  zero changes to the helper). Boot A for real (writes a real stamp) →
  copy A's raw stamp bytes verbatim into B (`shutil.copyfile`, never
  hand-typed JSON, §34) → B's own origin is pointed at a DEAD path
  (deliberately the more severe half of Moriarty's report — a repo whose
  origin may not even be reachable, not just a live-but-different one) →
  boot B inside the window must NOT say "remote (synced" and must show a
  real fetch attempt in the fake-git call log (honest failure, not silent
  trust). RED today for exactly the predicted reason: today's identity
  check matches on alias alone, so `_check_own_stamp_rate_limit` returns
  early as `rate_limited` BEFORE `_run_hardened_fetch()` is ever reached —
  confirmed empirically: the fake-git log is EMPTY (zero fetch calls) in
  the unfixed run, not just a wrong status string.
- **schema_version test** (`test_stamp_with_unknown_schema_version_is_
  treated_as_absent`): single repo, real boot writes a real stamp, then
  ONLY the `schema_version` field is mutated (read back the real JSON,
  change one field, rewrite — never hand-crafted from scratch) to `999`.
  Since today's code never even looks at `schema_version`, the mutated
  stamp is still accepted as valid (remote/branch still match, mtime still
  fresh from the rewrite) → same false "synced" line. RED today for the
  same reason.

RED confirmed exactly as predicted: `python3 -m pytest test_boot_
freshness.py test_boot_freshness_hardening.py test_boot_freshness_
regression.py -q` → 2 failed (only the 2 new tests, clean AssertionErrors
comparing `'MEMORY: remote (synced 0s ago)'` against the "must not contain
remote (synced" assertion) + 137 passed + 2 skipped (same pre-existing
Windows-only guards). v1/v2 contract (relabel wording, own-stamp Vectors
A/B/D, rate-limit boundaries) untouched and still fully green.

**Cerberus S3 (pinning, not contract) — `test_boot_freshness_hardening.
py::TestReadOwnStampAgeDirectCalls`** (4 tests, direct calls, no git repo
needed — `_read_own_stamp_age()` takes an explicit `project_root` and
never touches git): JSON-corrupt → None, wrong top-level shape (a list,
not a dict) → None, symlink planted at the stamp path → None (wrapped in
`try/except OSError: pytest.skip(...)` around the `os.symlink()` call
itself, not a blanket `skipif(WINDOWS)` — matches the project's existing
`real_symlink_capable`-style convention for "attempt the real privileged
op, skip only if the environment genuinely can't grant it" rather than
assuming POSIX==capable), hard link at the stamp path → None (same
try/except-around-`os.link()` skip pattern, `reject_hardlinks=True` is
already the read call's kwarg in production). All 4 confirmed GREEN on
first run, as expected for pinning (the underlying guards — `json.loads()`
ValueError, `isinstance(dict)`, `open_no_follow_symlink()`'s O_NOFOLLOW +
`reject_hardlinks=True` — already existed before this pass).

**Cerberus S4 fix** — `test_boot_freshness.py::TestFetchRateLimit::
test_fresh_fetch_head_skips_fetch` now asserts `os.path.isfile(stamp_path)`
immediately after the seeding boot, before installing the fake-git and
running boot #2. Without it, a regression that makes `fetch_memory_ref()`
short-circuit to `skipped_gate` (e.g. toolkit-memory detection silently
breaking) would ALSO produce zero fetch calls in boot #2 — the pre-existing
"no fetch calls observed" assertion alone can't tell a genuine rate-limit
skip apart from a differently-broken skip. Confirmed still GREEN after the
addition (the seeding boot genuinely does write the stamp today).

## Issue #60 v4 — alias-fallback URL is not identity, RED contract (session 2026-07-10, decision 174d82b)

Moriarty round 3 broke the v3 guard (`TestOwnStampIdentityIncludesRemoteURL`
above) from a different angle: `git remote set-url origin ""` leaves the
fetch refspec in place but empties `remote.origin.url`; `git remote
get-url origin` then falls back and prints the remote's own NAME
("origin") as if it were a URL, exit 0 — `_check_remote_is_live()`
(`lib/boot_git_checks.py:668`) only rejects empty/option-shaped
`get-url` output (`_looks_like_git_option`), so "origin" sails through as
"resolved identity". Decision 174d82b: a "resolved" URL identical to the
remote's own alias must collapse to the SAME "not resolved" bucket as
`git remote get-url` failing outright — no confidence, ever, no stamp
write.

**Empirical pre-check (mandatory before writing the test, done via raw
shell in scratch, not the suite) confirmed two non-obvious mechanics**,
both load-bearing for the fixture:
1. With the URL emptied, `git fetch origin -- <branch>` (the EXACT argv
   `_run_hardened_fetch()` uses, including the positional branch) only
   succeeds if a directory literally named `origin` exists in the fetch's
   `cwd` (= `project_root`) AND that directory has the target branch ref
   — git's own fallback treats the empty-URL remote's positional name as
   a relative path. An empty bare repo at `origin/` is NOT enough (`fatal:
   couldn't find remote ref main`); it must be seeded with a commit on
   that branch first.
2. **The trap directory's history must be a real continuation of the
   test repo's OWN history** (built via `git clone --bare <this repo's
   own real bare remote> origin`, not an unrelated freshly-seeded repo).
   An unrelated trap's content diverges from local HEAD, and
   `check_upstream_shares_history()` (the pre-existing #49/Moriarty-T2
   guard) then renders `"MEMORY: LOCAL — upstream unrelated (no shared
   history), not shown"` — which incidentally also doesn't say "remote
   (synced", MASKING the alias-fallback vector behind a different,
   already-fixed guard instead of exercising it. Caught by literally
   running the fixture by hand and reading the rendered line before
   writing any assertion — first attempt used an unrelated trap and the
   masking was silent (test would have been RED for the wrong reason, or
   worse, accidentally green post-fix without ever proving anything).

New helpers (`tests/test_boot_freshness.py`, module level, right before
the new class): `_degenerate_remote_url_to_alias(repo, remote_name=
"origin")` (`git remote set-url <name> ""`), `_plant_alias_named_trap
(repo, bare, alias="origin")` (bare-clones `bare` — the repo's OWN real
remote — into `repo/<alias>`).

New class `TestAliasFallbackURLIsNotResolvedIdentity` (2 tests, real
subprocess §34, inserted right after `TestOwnStampIdentityIncludesRemoteURL`):

- **PoC A→Z** (`test_stamp_written_via_alias_fallback_is_not_trusted_by_an_unrelated_repo`):
  X degenerated + alias-trap planted → real boot writes a real stamp
  (setup-sanity-asserted: `remote_url == "origin"`, proves the write-path
  bug is genuinely reproduced, not hypothetical) → stamp bytes copied
  verbatim into unrelated Z (own different bare remote, ALSO degenerated
  the same way per Moriarty's literal PoC shape, deliberately NO trap of
  its own — the more severe half) → boot Z inside the window must not
  say "remote (synced" on EITHER channel (combined stdout+log, and the
  persisted log FILE alone — same double-channel convention as every
  other test in this file family).
- **Vector B, write-side self-consistency**
  (`test_own_alias_fallback_stamp_never_rate_limits_a_second_boot_of_the_same_repo`):
  no cross-repo copy at all — X degenerated + trapped, boot #1 writes the
  bogus stamp, boot #2 of the SAME repo (still degenerate+trapped, still
  inside the window) must also not say "remote (synced" — the decision
  text explicitly frames this as "sin confianza... nunca... y sin
  escritura de stamp", i.e. the guard belongs at URL-resolution time
  (`_check_remote_is_live`), which would make it fire identically for a
  repo checking against its OWN prior stamp, not only against a foreign
  one.

**Deliberately did NOT assert on fetch-call counts (fake-git log) in
either new test**, unlike the sibling `TestOwnStampIdentityIncludesRemoteURL`
tests above. Reasoning worked through before writing: the natural fix
location (`_check_remote_is_live`, called from `_resolve_fetch_target`,
BEFORE `_check_own_stamp_rate_limit`/`_run_hardened_fetch` ever run) is
the same function that already returns an early "no_remote" result when
`git remote get-url` fails outright — extending that same early-return to
the alias-fallback case means NO fetch attempt happens at all once fixed
(fails closed at resolution time, like the dead-remote branch), not "a
fetch is attempted and merely not trusted" like the v3 cross-repo vector.
Asserting `fetch_calls` non-empty here would very likely start failing
against the CORRECT fix — asserted only the unambiguous, orchestrator-
specified observable (the MEMORY: line, both channels).

RED confirmed exactly as predicted: `python3 -m pytest tests/
test_boot_freshness.py tests/test_boot_freshness_hardening.py tests/
test_boot_freshness_regression.py -q` → 2 failed (only the 2 new tests,
clean `AssertionError`s: `'MEMORY: remote (synced 0s ago)'` present when
the assertion requires its absence) + 139 passed + 2 skipped (same
pre-existing Windows-only guards). v1/v2/v3 contract (relabel wording,
own-stamp Vectors A/B/D, rate-limit boundaries, cross-repo dead/foreign-URL
identity, schema_version) untouched and still fully green. Exit code
checked directly (no `| tail`/`| head`), per this repo's hard rule.
Production code (`lib/boot_git_checks.py`, `lib/boot_fetch_stamp.py`)
untouched by this pass — test file only.

### GREEN re-seed after Ultron's fix — one RED test's own PREMISE became impossible (same session)

Ultron implemented the guard in `_check_remote_is_live()` (`url ==
remote_name` -> treated exactly like an unresolved remote, same
"no_remote" bucket as `git remote get-url` failing outright). That closes
BOTH directions at once, because `_check_remote_is_live()` is the only
call site that ever produces `remote_url` — no fetch is attempted at all
once the alias-fallback shape is detected, so `_write_own_stamp()` is
never reached. Consequence: `test_own_alias_fallback_stamp_never_rate_
limits_a_second_boot_of_the_same_repo` went green for free (renamed to
`test_own_alias_fallback_never_writes_a_stamp_so_no_boot_claims_synced` —
its OLD `stamp_existed_after_boot1` variable was captured but never
asserted on; now explicitly `assert not os.path.isfile(stamp_path)` after
EACH boot, pinning the write-side guard directly instead of leaving it as
an unasserted side observation). But
`test_stamp_written_via_alias_fallback_is_not_trusted_by_an_unrelated_repo`
broke at its own **setup sanity** step (`assert os.path.isfile(stamp_x)`)
— its premise ("repo X's real boot writes the poisoned stamp") is now
categorically impossible by design, since the fix makes exactly that
write path a no-op. This is the correct, intended failure (Ultron's fix
IS the wanted behavior per decision 174d82b — "sin escritura de stamp") —
not a bug to route back to Ultron, but a fixture whose story needed
re-telling.

**Fix applied to the test, not the assertion under test**: re-seeded the
poisoned stamp by mutating a REAL stamp a HEALTHY, non-degenerate boot (a
third repo, W — normal `_setup_freshness_repo`, no degeneration, no
trap) wrote for real, then read-mutate-rewrite ONLY the `remote_url`
field to the literal alias `"origin"` (same pattern as the pre-existing
`test_stamp_with_unknown_schema_version_is_treated_as_absent`'s
schema_version mutation — never hand-typed JSON from scratch,
unmassk-standards §34) before placing it in target repo Z. This is
actually a STRONGER test of the read-side guard than the original: it no
longer depends on ANY one repo being able to produce the poisoned shape
itself — it proves the read side rejects the CLAIM regardless of
provenance (old plugin version predating the guard, hand-restored
backup, copy between repos), which is the real-world threat shape this
guard exists for. Renamed
`test_stamp_written_via_alias_fallback_is_not_trusted_by_an_unrelated_repo`
-> `test_stamp_claiming_alias_as_url_is_never_trusted_by_an_unrelated_repo`
to match (no longer claims anything about HOW the stamp was written).

**Lesson for next time a write-side guard changes**: any test whose
`assert os.path.isfile(stamp_path)` (or equivalent "the buggy write
happened") is itself the fixture's SEED step, not the behavior under
test, is fragile against exactly this kind of fix — the write path being
closed makes the seed impossible, not just the final assertion. When a
write-side guard is the thing being contracted, prefer seeding the
poisoned artifact by mutating a real artifact from an UNRELATED, still-
healthy write path (read-mutate-rewrite) rather than degenerating the
same repo whose write you're about to also assert never happens — keeps
the read-side test's fixture immune to the write-side guard landing
first.

Verification after the re-seed, same session: `tests/test_boot_freshness.py
tests/test_boot_freshness_hardening.py tests/test_boot_freshness_
regression.py -q` -> 141 passed, 2 skipped, exit 0. Full suite `python3
-m pytest tests -q` -> 1246 passed, 2 skipped, exit 0 (took ~4m35s — full
suite needs a longer-than-default timeout, plain `python3 -m pytest
tests -q` with no extra flags). Production code untouched by this
re-seed pass — test file only.
