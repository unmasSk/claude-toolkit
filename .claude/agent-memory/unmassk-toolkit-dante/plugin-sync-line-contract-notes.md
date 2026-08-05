---
name: plugin-sync-line-contract-notes
description: PLUGIN sync-line contract (commit fbc2ac5) — count_repo_cache_drift vs grouped-description gotcha, real HOME-redirect subprocess pattern for cache-vs-repo end-to-end, exception-fail-open mutation check
metadata:
  type: project
---

Commit fbc2ac5 added a boot STATUS line reporting repo-vs-plugin-cache
drift (`lib/cache_sync_check.py:count_repo_cache_drift()`,
`lib/boot_render.py:_render_plugin_sync_line()`,
`hooks/session-start-boot.py:350`). Test file:
`unmassk-toolkit/tests/test_plugin_sync_boot_line.py` (unit + end-to-end)
plus `TestCountRepoCacheDrift` appended to
`test_doctor_derived_expectations.py` (where the sibling
`check_repo_cache_sync()` tests already lived).

**The actual bug class this function exists for**: `check_repo_cache_sync()`
bundles >3 differing files behind `"+N more"` into ONE description string
per subdir — a caller counting `len(descriptions)` gets 1, not the real
number of drifted files. The single test that proves the new function
earns its existence is building exactly that fixture (7 differing files in
one subdir) and asserting `count == 7` while `len(descriptions) == 1`. See
[[boot-fetch-prune-contract-notes]] for a similar "the count and the
description-list length are NOT the same number" trap in a different boot
subsystem.

**Real end-to-end pattern for repo-vs-cache comparisons**: `CACHE_BASE_DIR`
is computed from `os.path.expanduser("~")` at import time but read at call
time, so a real subprocess run of the hook can be redirected by overriding
`HOME` (+ `USERPROFILE`/`HOMEDRIVE`/`HOMEPATH` for Windows parity) in
`run_script(..., env=...)`. Plant a real `<project>/unmassk-toolkit/{hooks,lib,bin}`
tree and a real `<fake-home>/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-toolkit/<version>/{hooks,lib,bin}`
tree with real files, run the actual hook, and read the assertion off the
boot-log file (`.claude/.unmassk/boot-log-latest.txt`) — the PLUGIN: line
lands only there, never in the short stdout banner (confirmed by reading
`render_boot_banner_lines()`'s call site in `session-start-boot.py`: the
banner only reuses `status`/`status_detail`, not the full `status_lines`
list). Same `HOME`-redirect pattern already established in
`test_skill_drift_repo_source_detection.py` for the same reason (avoid
resolving into the real developer machine's plugin cache).

**Fail-open + visible-reason contract, no real exception reachable**: the
comparator's own error handling already fail-opens internally
(`_dir_fingerprint` catches `OSError`, `_latest_version_dir` catches
`OSError`/`ValueError`) — there is no real filesystem state left that makes
`count_repo_cache_drift()` raise. The renderer's own `try/except Exception`
guard is defensive code for an unreachable-today failure mode, so
monkeypatching `cache_sync_check.count_repo_cache_drift` to raise is the
correct (not lazy) choice here — proved it by calling the REAL
`boot_render.render_status_section()` (the actual boot-critical-path
function, not just the private helper) and asserting it returns normally
with the exception's type name still visible in the STATUS lines.

**Mutation-checked live** (not just "wrote it, assumed it works"): broke
the zero-line string in `boot_render.py` → both the unit test and the
end-to-end test failed for the right reason; broke `count_repo_cache_drift`
to return `len(drifted)` instead of the real count → the exact 3 tests
built to catch that (grouped-count, multi-subdir-sum, absent-subdir) failed
and the rest stayed green. Both reverted before commit.
