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
