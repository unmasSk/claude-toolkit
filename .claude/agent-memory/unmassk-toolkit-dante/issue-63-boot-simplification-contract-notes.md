---
name: issue-63-boot-simplification-contract-notes
description: issue #63 boot-simplification acceptance contract (test-first, before Ultron) — P1 manifest-version gate, P2 upgrade moved to SessionStart, P3 skill-drift repo-source detection; HOME-env cache-fixture technique, decoy-plugin determinism trick
metadata:
  type: project
---

Plan: `docs/plan/refactor-boot-simplification.md` (issue #63, branch
`feat/issue-63-simplificacion-boot`). Bilbo's map:
`.claude/agent-memory/unmassk-toolkit-bilbo/boot-simplification-63-map.md`.
Build mode: test-first ligero, acceptance granularity only (no EXHAUSTION —
that's the post-Ultron hardening pass). 3 new files, all RED confirmed for
the right reason, 0 regressions (1266 passed / 2 skipped baseline unchanged):
`test_crew_manifest_version_gate.py`, `test_upgrade_moved_to_sessionstart.py`,
`test_skill_drift_repo_source_detection.py`.

**P1 (session-start-crew.py manifest gate)** — only
`TestManifestVersionMatchSkipsRewrite` is genuinely new (today's hook has
zero manifest-awareness, always diffs+rewrites). The two "regenerate"
classes (version-mismatch, missing/corrupt manifest) already pass today —
kept anyway as part of the same acceptance contract and as a regression
guard the new gate must not break. **mtime assertion needs a real
`time.sleep(1.1)`** between capturing `mtime_before` and running the hook —
some filesystems have ~1s mtime resolution, so a same-second rewrite could
otherwise pass the mtime check vacuously even if content changed (content
equality is the primary signal; mtime is the secondary confirmation the
plan text explicitly asked for — "contenido y mtime intactos").

**P2 (upgrade moved to SessionStart)** — asserted purely on OBSERVABLE
EFFECT (manifest.version ends up synced), never on which of the two
SessionStart hooks or which function performs it — the orchestrator
explicitly left that wiring choice to Ultron. Ran the real
`session-start-boot.py` then `session-start-crew.py` in the exact order
`hooks/hooks.json` declares them. Reused conftest's
`neutralize_needs_upgrade_check1()` to isolate the semver-only trigger
(same helper `test_needs_upgrade_semver.py` already established).

**P3 (skill-drift repo-source detection, `lib/boot_health.py:52`)** — the
hardest of the three. `REPO_BASE_DIR = dirname³(__file__)` and
`CACHE_BASE_DIR = ~/.claude/plugins/cache/unmassk-claude-toolkit` are both
computed from real filesystem state (module's own location, real HOME) —
no monkeypatching internals is possible while staying "canal real,
subprocess" per the task brief. Two techniques made this tractable:

1. **HOME env override for CACHE_BASE_DIR, without ever touching the
   real user cache.** `run_script(hook_path, repo, env={"HOME": str(home)})`
   — conftest's `run_cmd` merges `{**identity_defaults, **os.environ,
   **(env or {})}`, so only HOME is redirected, everything else (PATH,
   git behavior) stays real. To reproduce the buggy REPO_BASE_DIR shape
   at all (a cache-version-listing directory, not a real repo root), the
   test must **execute a full `shutil.copytree()` of the plugin source**
   from inside `<HOME>/.claude/plugins/cache/unmassk-claude-toolkit/
   unmassk-toolkit/<version>/` — REPO_BASE_DIR is derived from the
   RUNNING module's own `__file__`, so there is no way to fake it without
   physically running the hook from that path. `shutil.ignore_patterns
   ("tests", "__pycache__", ".git")` keeps the copy small/fast (~2.2MB of
   hooks+lib+bin+skills+.claude-plugin, no test suite needed inside the
   copy).

2. **Cross-plugin decoy avoids a real dict-overwrite race that IS part of
   the reported bug.** The straightforward repro (two `unmassk-toolkit`
   version dirs with genuinely different SKILL.md content) is NOT
   deterministic: `_build_repo_skill_index()` iterates
   `os.listdir(REPO_BASE_DIR)` and last-writer-wins into a dict, and
   because REPO_BASE_DIR and the cache's own "latest version" folder are
   the SAME physical directory in this bug shape, whichever entry is
   processed last can be either the "self" (matches, no drift) or the
   "stale" one (mismatches, drift) — filesystem-dependent, not portable
   across hosts/CI. **Fix: plant the mismatched content under a SEPARATE
   cached plugin name** (`decoy-plugin/1.0.0/skills/<real-skill-name>/
   SKILL.md`) reusing a skill_name that's real in `unmassk-toolkit`'s own
   (single, or content-identical multi-version) skills tree.
   `repo_index.get(skill_name)` is not scoped to a plugin_name at all —
   this is the SAME root cause (REPO_BASE_DIR miscalculation) manifesting
   through a path with zero listdir-order dependency: unmassk-toolkit's
   own entry always self-compares (deterministic no-drift from that
   plugin), decoy-plugin's entry always mismatches against the real repo
   content pulled in via repo_index (deterministic drift). Verified live
   before finalizing: this fires 100% reproducibly, confirmed by running
   the fixture and reading the actual drift line
   (`⚠️ drift: decoy-plugin/unmassk-core cache differs from repo source`).
   A second, content-IDENTICAL `unmassk-toolkit` version dir was still
   included in the fixture (0.9.0 alongside 1.0.0) purely to keep the
   task brief's literal ">=2 cached versions" shape — its content being
   identical means it can't introduce the race back in, regardless of
   which one `_build_repo_skill_index()` picks last.

**Gotcha caught before finalizing (own mistake, fixed same pass): a bare
`"⚠" not in combined` assertion is too broad and would have failed for
the WRONG reason.** `lib/boot_git_checks.py` and `lib/boot_render.py`
use the same `⚠️` emoji for unrelated warnings (consolidation-threshold
nudge, memory-accumulation nudge, doctor auto-repair status) that fire
independently of drift on a fresh/uninstalled throwaway repo (confirmed:
"STATUS: warn — auto-repaired issues" and "⚠️ 9999 commits since last
consolidation" both appear in the real fixture output, neither is
drift-related). Grepped `grep -rn "⚠" lib/*.py hooks/*.py` before
narrowing the assertion to `"drift" not in combined.lower()` — confirmed
by the same grep that the literal word "drift" as user-facing text
appears ONLY inside `check_skill_drift()`'s own warning string, so this
narrower check is precise, not just narrower. Same family of pitfall as
[edge-cases.md](edge-cases.md)'s "echoes back into output" / marker
pitfall, just discovered via a live test run instead of upfront review —
worth checking early next time a shared emoji/prefix is used for the
assertion.

RED confirmed via full-suite run (`python3 -m pytest unmassk-toolkit/tests
-q`, exit code read directly from the printed summary line, never through
a pipe): 4 failed (exactly the 4 new-behavior tests) + 1266 passed + 2
skipped (pre-existing Windows-only guards, same baseline as every prior
session). The other 5 tests across these 3 new files pass today already
(regression/control tests for already-correct behavior) — expected and
reported honestly as such, not hidden.

See also: [unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)
(HOME/env-override pattern is new; the rest follows established repo/boot
helper conventions), [feat-boot-freshness-contract-notes](feat-boot-freshness-contract-notes.md)
(same "test-first contract, RED baseline for the rest of the pipeline" shape).

## GREEN-pass audit (2026-07-11): Ultron's 4 test re-bases + TestFailOpenUpgrade rewrite

Ultron implemented P1-P4+P6 (wip 8245c99) and, under a revoked authorization,
re-based 4 test files himself. Audited `git diff 0966668..8245c99 --
unmassk-toolkit/tests/`: **all 4 ADOPTED**, one (`test_migrate_statusline.py`)
needed a genuine fix on top (see below), found only by running the full
combination, not by reading the diff alone.

- `test_boot_output.py`: removed `test_untrack_previously_committed_jsons`
  (probed the retired `_migrate_untrack_generated_jsons`); kept
  `test_gitignore_entries_added`, verified it still exercises REAL code
  (`boot_glossary_cache.py`/`boot_fetch_stamp.py`'s own unconditional
  `ensure_gitignore()` calls, unrelated to the retired migration).
- `test_migrate_statusline.py`: removed the boot_migrations sys.modules
  probe. Confirmed `lib/boot_migrations.py` now has zero `git_helpers`
  imports (only `json`/`os`/`sys`) — nothing left to freeze there.
- `test_needs_upgrade_semver.py`: patch moved to
  `hook.needs_upgrade.__globals__` (real function-identity re-export,
  `hooks/user-prompt-memory-check.py:35` does `from upgrade_check import
  needs_upgrade`). **Mutation-verified**: temporarily changed
  `lib/upgrade_check.py`'s `return manifest_tuple < code_tuple` to a
  lexicographic `str(manifest_version) < str(PLUGIN_VERSION)` — exactly the
  2 rebased tests (`test_semver_not_lexicographic_*`) went RED, 13 others
  stayed green (precise, not over-broad); restored, `git diff` empty,
  15/15 green again.
- `test_security_regression.py`: removed 3 `_boot_migrations` variants
  (function deleted), kept the 3 `_upgrade` variants (BUG AC/AM/AN) —
  confirmed against `bin/git-memory-upgrade.py`'s
  `_migrate_runtime_to_unmassk()` that all 3 independent
  `verify_path_within_project()` guards (claude_dir, unmassk_dir,
  agent_dir/target_dir) are each still covered by exactly one kept test.

**Real bug found while running the audited files TOGETHER (not visible
running any single file alone): `test_migrate_statusline.py`'s
`_load_migrate_fn()` leaked a NEW sys.modules contamination class.**
`hooks/session-start-boot.py` now does (issue #63, point 2) `from
upgrade_check import trigger_auto_upgrade_if_needed` at module level.
`_load_migrate_fn()` stubs `sys.modules["version"]` to `VERSION = "test"`
while loading `session-start-boot.py` — if `lib/upgrade_check.py` hasn't
been imported anywhere yet in the process, this transitive import runs
DURING the stub window, so `upgrade_check.py`'s own `from version import
VERSION as PLUGIN_VERSION` permanently freezes
`sys.modules["upgrade_check"].PLUGIN_VERSION` to `"test"` — a REAL,
stably-cached module, never restored (it wasn't in the explicit 3-name
stub/restore list, since that surface didn't exist before P2). Effect:
`_parse_semver("test")` → `None` → `needs_upgrade()`'s semver check always
returns `False`, silently breaking `test_needs_upgrade_semver.py`'s
`test_manifest_older_than_code_returns_true` whenever it ran in the same
pytest session AFTER `test_migrate_statusline.py` (confirmed deterministic
by isolating to just those 2 files: `pytest test_migrate_statusline.py
test_needs_upgrade_semver.py` fails every time; either file alone is
green). Reproduced directly in-process:
`sys.modules["upgrade_check"].PLUGIN_VERSION == "test"` after calling
`_load_migrate_fn()` once. **Fix (test-only, `_load_migrate_fn()`)**:
snapshot `set(sys.modules.keys())` BEFORE the 3-name stub loop, and in the
`finally` block, after restoring the 3 explicit stubs, evict every OTHER
module name that is newly present and wasn't one of the 3 explicit stubs —
generic fix for the whole class (any future new transitive import during
this stub window), not just this one instance. Verified: `upgrade_check"
in sys.modules` is `False` after `_load_migrate_fn()` post-fix, and a fresh
`import upgrade_check` afterward reads the REAL `PLUGIN_VERSION` (matched
`.claude-plugin/plugin.json`'s real version).

**`TestFailOpenUpgrade` rewrite** (`test_hardening_recall.py`): the old
version patched `subprocess.run` globally and called
`hook.main()` on `hooks/user-prompt-memory-check.py` — passed green for the
wrong reason, since that hook's `main()` no longer calls
`needs_upgrade()`/`subprocess.run()` at all post-#63 (moved to
`lib/upgrade_check.py::trigger_auto_upgrade_if_needed()`, invoked once from
`hooks/session-start-boot.py::main()`, itself NOT wrapped in its own
try/except — relies entirely on `trigger_auto_upgrade_if_needed()`'s own
internal try/except). Rewrote to run `boot.main()` for real in an isolated
subprocess (same pattern as `test_boot_output.py`'s
`_run_boot_with_failing_log_write()`), against a real, fully-installed repo
(`run_script(INSTALL, repo, ["--auto"])`) with `manifest.json` tampered to
`"0.0.1"` so `needs_upgrade()` triggers via the semver check (check 2) —
CLAUDE.md from a real install already satisfies check 1, so this isolates
the semver path cleanly. 3 real-channel scenarios:
1. TimeoutExpired — selective sabotage (only the `git-memory-install.py`
   subprocess.run call raises; every other real subprocess.run call, e.g.
   doctor/repair, passes through to the REAL function) so `STATUS:` stays
   `ok` and only the upgrade path is under test, not incidental doctor
   noise.
2. Generic OSError — same selective-sabotage shape.
3. Installer returncode != 0 — genuine subprocess spawn (a real throwaway
   `sys.exit(3)` script), reached via `upgrade_check._PLUGIN_ROOT`
   override, no subprocess.run mocking at all.
Mutation-verified as a combined check (anti-vacuity, since scenario 3
doesn't naturally hit the except today — `subprocess.run()` has no
`check=True`): removed the try/except AND added `check=True` in
`lib/upgrade_check.py::trigger_auto_upgrade_if_needed()` — all 3 tests went
RED (`rc=1`, uncaught traceback propagated through `boot.main()`);
restored, `git diff` empty, 3/3 green again. Full combined run
(`test_boot_output.py test_migrate_statusline.py
test_needs_upgrade_semver.py test_security_regression.py
test_hardening_recall.py`): 198 passed. Full suite
(`unmassk-toolkit/tests`): 1265 passed, 2 skipped, 0 failed, exit 0.
