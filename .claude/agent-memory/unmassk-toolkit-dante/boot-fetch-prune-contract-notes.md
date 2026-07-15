---
name: boot-fetch-prune-contract-notes
description: Boot fetch missing --prune RED contract (Finding 10, test_boot_freshness_regression.py) — deleted remote branch survives forever in refs/remotes/*; direct fetch_memory_ref() call reuses the stale-own-stamp technique
metadata:
  type: project
---

Review bug (2026-07-15, self-lie-of-state class, not a security finding —
matches this project's CLAUDE.md threat model: "the system against
itself"): `_run_hardened_fetch()`'s refspec (`lib/boot_git_checks.py`,
`["fetch", remote_name, "--no-tags", "--", f"+refs/heads/*:refs/remotes/
{remote_name}/*"]`) has no `--prune`. A branch deleted on the remote is
never removed from `refs/remotes/<remote>/*` on this machine — it survives
forever, and `get_remote_branches()`/`render_branches_section()`
(`tests/test_boot_branches_section.py`) keep listing it even though the
fetch itself reports `"status": "fetched"` (success).

**Contract pinned in `tests/test_boot_freshness_regression.py::
TestFetchDoesNotPruneDeletedRemoteBranches`** (Finding 10, session
2026-07-15), 2 tests: (1) RED — push `feature/x` to a real bare remote →
first real `fetch_memory_ref(repo)` call brings it in → delete it for real
(`git push origin --delete feature/x` from an independent clone) → force a
genuine SECOND real fetch past the rate-limit window → `get_remote_
branches("origin")` must no longer list it. Confirmed RED for exactly the
predicted reason: `branches_after == ['feature/x', 'main']`. (2) GUARD,
green today and must stay green after the fix — a branch that still
exists on the remote survives a real (eventually `--prune`d) fetch.

**Driven through the REAL production fetch path, never a hand-run `git
fetch`** — `boot_git_checks.fetch_memory_ref(repo)` directly (in-process,
explicit `project_root` param, no chdir needed — same "functions taking an
explicit path param" pattern as `mock-patterns.md`'s hardening-pass
direct-call section) → `_run_hardened_fetch()`. This matters because
`test_boot_branches_section.py`'s own fixtures use a **manual**
`_sync_remote_tracking()` helper (a hand-run `git fetch` mirroring the
production refspec by hand) — sufficient for THAT file's contract (get_
remote_branches' read-side shape), but NOT sufficient here: the bug is in
the boot's own WRITE-side fetch call, so the test must exercise that exact
call, not a parallel hand-typed one that could silently drift from
production and mask a fix (or a regression) either way.

**Forcing the second real fetch — same technique as every other test in
this file**: the rate-limit gate now reads `.claude/.unmassk/boot-fetch-
stamp.json`'s own mtime (issue #60 v2/v3, NOT `.git/FETCH_HEAD` anymore —
see [feat-boot-freshness-contract-notes](feat-boot-freshness-contract-notes.md)).
`os.utime(stamp_path, (stale_time, stale_time))` with `stale_time =
time.time() - (FETCH_RATE_LIMIT_SECONDS + 60)`, reused verbatim from
`test_boot_freshness_hardening.py::TestFetchMemoryRefStates::
test_stale_fetch_head_past_window_allows_refetch`. Both new tests assert
`second["status"] == "fetched"` as a setup-sanity check BEFORE asserting on
branch presence/absence — without it, a differently-broken rate-limit gate
(e.g. always skipping) would make the branch-absence assertion pass
vacuously for the wrong reason.

**Fixture reuse, no new helpers needed**: `_make_gated_repo(tmp_path)` +
`_add_bare_remote(repo, tmp_path)` (imported from
`test_boot_freshness_hardening.py`, already re-exported into this file) —
lighter than `_setup_freshness_repo()` since these tests never render a
full boot, only call `fetch_memory_ref()`/`get_remote_branches()` directly.
The second branch is pushed from an independent clone of the same bare
remote (mirrors `_clone_machine_b()`'s "machine B" shape used elsewhere in
this file family) — `_add_bare_remote()` already returns the bare path, so
no new bare-repo helper was needed.

RED confirmed: `python3 -m pytest test_boot_freshness.py test_boot_
freshness_hardening.py test_boot_freshness_regression.py test_boot_
branches_section.py -q` → 1 failed (only the new RED test, clean
AssertionError with the predicted `['feature/x', 'main']`) + 158 passed +
2 skipped (same pre-existing Windows-only guards as always). Exit code
checked directly (no `| tail`/`| head`), per this repo's hard rule.
Production code (`lib/`, `hooks/`, `bin/`) untouched — test file only.
