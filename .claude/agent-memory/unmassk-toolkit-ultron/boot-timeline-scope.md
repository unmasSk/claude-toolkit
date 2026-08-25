---
name: boot-timeline-scope
description: RETIRED SUBJECT (confirmed 2026-08-25) — lib/boot_render.py, lib/boot_git_checks.py, lib/boot_memory.py were deleted 2026-08-05 ([[v1-boot-chain-deletion]]). Kept for the TIMELINE/exclude_remote/PLUGIN-line design reasoning, which generalizes; the PLUGIN repo-vs-cache check itself now lives in bin/git-memory-doctor.py instead (still current).
metadata:
  type: project
---

**RETIRED SUBJECT, kept for the reasoning.** Every file this entry names
(`lib/boot_render.py`, `lib/boot_git_checks.py`, `lib/boot_memory.py`,
`hooks/session-start-boot.py`) was deleted 2026-08-05 — see
[[v1-boot-chain-deletion]] and [[lessons]]'s top banner. The `PLUGIN:`
repo-vs-cache drift check this entry documents is NOT gone: it moved to
`bin/git-memory-doctor.py` (confirmed still present 2026-08-25) — see
`unmassk-toolkit-python-entrypoints.md`'s "Since 2026-07-29
`bin/git-memory-doctor.py` checks this itself" section for the current
version. What's below is the ORIGINAL design reasoning (why a
`--exclude=refs/remotes/<name>/*` guard is needed on any `--all`-scanning
git-log call, why the PLUGIN line needed to exist at all) — still useful
if the same class of check gets added to whatever reads git history next,
just not a pointer to live code anymore.

## Where the boot TIMELINE's git log call and count limit actually live

Not in `boot_render.py` despite that file owning `render_timeline_section()` and the
`BOOT_MAX_TIMELINE` constant. The real `git log` invocation is in
`lib/boot_git_checks.py:get_timeline()` — `boot_render.py` only imports it (via
`lib/boot_checks.py`'s re-export shim, `boot_checks <- boot_git_checks`). Grepping
`boot_render.py`/`boot_memory.py` alone for "git log"/"HEAD" will miss it.

## `--all` on a per-section git log call needs the SAME exclude_remote guard extract_glossary() already has

`extract_glossary()` (`lib/boot_memory.py`) already solved "a confirmed-unrelated
upstream's refs must never leak into an unlabeled boot section" (Moriarty T2, issue
#49): `exclude_remote` param + `_is_safe_remote_name()` allowlist + `--exclude=refs/remotes/<name>/* ` placed *before* `--all`. `tests/test_boot_freshness_regression.py::TestForeignUpstreamBootSuppressesUnrelatedHistory` pins this end-to-end for the whole boot output, not just extract_glossary()'s own unit tests — it caught a real regression when `get_timeline()` was switched from `git log HEAD -n{n}` to `git log --all -n{n}` (2026-07-15, TIMELINE 10→20-commits-all-branches task) without threading the same guard through.

**Pattern when adding a new `--all`-scanning git log call to the boot, or widening an
existing one from HEAD to `--all`:** add an `exclude_remote: str | None = None` param,
reuse `_is_safe_remote_name` from `boot_memory` (already exported, import it — don't
duplicate the regex), and thread the SAME `unrelated_remote_name` value
`hooks/session-start-boot.py`'s `main()` already computes once (from
`check_upstream_shares_history(upstream_ref)`) down through the render function to the
git-log-calling function. Confirm by re-running
`TestForeignUpstreamBootSuppressesUnrelatedHistory` — it is the one test that actually
exercises the end-to-end leak, unit tests on the individual function won't catch it.

## The boot's PLUGIN: repo-vs-cache line (2026-08-01)

`lib/boot_render.py::render_status_section(project_root: str | None = None)` now
renders an always-present `PLUGIN: ...` line (via private helper
`_render_plugin_sync_line()`), backed by `lib/cache_sync_check.py::count_repo_cache_drift()`
— a new function added alongside the pre-existing `check_repo_cache_sync()` (same
shared core, `_compute_drift()`), because the existing function's return
(`list[str]` of bundled `"lib/: a.py, b.py, +N more"` descriptions) cannot answer
"how many files, exactly" once past `_MAX_NAMED_FILES`. `count_repo_cache_drift()`
returns `(total_file_count, descriptions) | None` instead.

Why this line exists at all: `render_status_section()`'s own aggregate `status`
var only escalates above `"ok"` when the doctor's JSON `status == "error"` — a
`status == "warn"` finding (which is exactly what `check_repo_cache_sync` drift
produces inside the doctor) never flips it, so a stale plugin cache was
rendering `STATUS: ok` with zero visible trace. This is the same incident
documented in project memory `(plugin/hooks) requirement` / `(plugin/release)
stack` — 3 days of stale hooks with nothing at boot pointing at it.

`render_status_section()`'s only real caller (`hooks/session-start-boot.py`)
now passes `project_root` (already resolved there via `_get_project_root()`)
explicitly; the default `None` exists only so the one test that calls it with
no args (`tests/test_boot_output.py`) keeps working — `None` renders as
`"PLUGIN: no verificable (project root no disponible)"`, never silence and
never a false "ok".

## DEUDA.md #17 — PULL DIRECTIVE / BRANCHES freshness disclosure (2026-08-04)

`_build_pull_directive_lines()` and `render_branches_section()`
(`lib/boot_git_checks.py`) both compute off `refs/remotes/<remote>/*` as
they sat after the last fetch — the boot itself doesn't fetch anymore
(memory v2). Fix: both now say so in plain text ("not confirmed against a
fresh remote check"), no new git calls added. Test contract
(`tests/test_boot_git_checks.py`'s `FRESHNESS_DISCLOSURE_KEYWORDS`)
deliberately doesn't pin exact wording — any of confirm/stale/fresh/
verify(ied)/outdated/up(-) to date counts, case-insensitive. Constraint
that shaped the fix: `_build_pull_directive_lines()`'s existing tests pin
`len(lines) == 1` for both branches, so the disclosure had to go INSIDE
the existing single line, not as a second list item.

For `render_branches_section()`: added the disclosure as its own line
right after the `BRANCHES ({remote}):` header — NOT inside the header
line itself, and NOT starting with two-space-indent-plus-colon, because
`test_boot_branches_section.py`'s cap test (`TestRenderBranchesSectionCap`)
filters "branch lines" via `l.startswith("  ") and ":" in l` — any new
line matching both would silently inflate that count.

Related: [[implementation-patterns]]
