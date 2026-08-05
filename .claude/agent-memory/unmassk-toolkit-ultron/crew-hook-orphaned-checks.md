---
name: crew-hook-orphaned-checks
description: Moving 3 non-memory checks (PLUGIN cache-sync, UPGRADE auto-upgrade, REPO working-tree status) from the deleted session-start-boot.py into session-start-crew.py, always-print + fail-open convention
metadata:
  type: project
---

2026-08-05: when `hooks/session-start-boot.py` (v1 boot chain) was unplugged
from `hooks/hooks.json` in favor of the memory-v2 hooks
(`boot_launcher.py`), it silently took 3 non-memory checks with it that had
no v2 equivalent — see [[v1-boot-chain-deletion]] for the deletion side of
this same day's work by a concurrent agent. Restored the 3 into
`hooks/session-start-crew.py` (the surviving toolkit SessionStart hook),
never into `lib/memory/` — that tree has a declared zero-toolkit-imports
boundary (`docs/memoria-v2/PIEZAS.md` §13).

**Pattern used for all three** (`_print_plugin_sync_check`,
`_print_upgrade_check`, `_print_repo_status_check`): import the reused
helper INSIDE the function body wrapped in its own `try/except Exception`,
so an import failure (e.g. a sibling module mid-edit by another agent) and
a runtime failure both degrade the same way — a printed `[crew] LABEL: ...`
line, never a raised exception. Matches the file's existing `except OSError`
degrade style. Every branch prints, including the "nothing to do" case
(`unmassk-standards` P6, "the zero is shown, not silenced") — `_print_upgrade_check`
had to call `needs_upgrade()` itself before `trigger_auto_upgrade_if_needed()`
for exactly this reason: the latter is silent on the no-op path by design
and only ever speaks (to stderr) on failure.

**Label convention**: English label + Spanish content
(`[crew] PLUGIN: sincronizado (0 ficheros)`), matching `boot_render.py`'s
`_render_plugin_sync_line()` mixed convention — NOT the pure-English style
of this same file's pre-existing CLAUDE.md-block lines
(`[crew] All managed blocks up to date`). Both conventions now coexist in
one file by design; don't "fix" one to match the other.

**REPO check has no reusable source** — `git status --porcelain` via
`git_helpers.run_git(cwd=..., timeout=5)` was written fresh, since no v2
equivalent exists anywhere to import.

**Verified live in the actual dirty repo (not a fixture)**: first run fired
all 3 alert paths for real (PLUGIN 10 files drifted, UPGRADE triggered a
real `--auto` install, REPO 17 files dirty) — no artificial forcing needed,
the WIP branch state already exercises them. Second run showed UPGRADE's
"al dia" idempotent path once the manifest synced. The "PLUGIN
sincronizado (0)" and "REPO working tree limpio" zero-cases were NOT
exercised — forcing them needs `claude plugin update` or a clean tree,
both out of scope for this task (read-only elsewhere, no destructive git).
`.claude/.unmassk/manifest.json` (what `--auto` install writes) is
gitignored — confirmed via `git status --porcelain --ignored` that running
the real installer left zero trace in tracked git state.

**Pre-existing, unrelated test failure found while verifying**:
`tests/test_upgrade_moved_to_sessionstart.py::test_sessionstart_hooks_perform_the_version_sync_effect`
fails because it shells out to `hooks/session-start-boot.py`, which the
concurrent boot-chain-deletion agent had already removed by the time this
check ran — not caused by this change, and that test file was out of scope
to fix (test files off-limits per task instructions).

See also [[v1-boot-chain-deletion]] and the HARD RULE at the top of
MEMORY.md — this session ran entirely read-only outside
`hooks/session-start-crew.py`, no git mutation commands used.
