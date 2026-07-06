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
