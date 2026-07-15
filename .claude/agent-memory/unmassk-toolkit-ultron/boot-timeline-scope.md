---
name: boot-timeline-scope
description: unmassk-toolkit boot TIMELINE section wiring — where the git log call and count limit actually live, and the exclude_remote guard needed when switching a section from HEAD to --all
metadata:
  type: project
---

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

Related: [[implementation-patterns]]
