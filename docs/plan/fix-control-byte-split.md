# Control-Byte Field-Split Hardening — Implementation Plan

**Issue:** #57
**Branch:** main (trunk repo — no feature branch)
**Triage:** Standard + security → Argus/Moriarty/Yoda mandatory in Verify
**Build mode:** test-first (ATDD: Dante contract → Ultron GREEN → Dante hardening in Verify)
**Seam:** YES — git subprocess (producer) → field parsers (consumer). Round-trip repro with a REAL hostile commit, owned by Dante. §34 applies.
**Created:** 2026-07-09

## Goal

A commit with literal `\x1f`/`\x1e` bytes in subject/body can no longer forge records or shift parsed fields in any consumer of `git log` output.

## Decisions

- Decision commit `80c7f7b`: mirror the hardened `git log -z` pattern from `lib/boot_memory.py:154-161/361-371` (fix SEC-CRIT-NEW-01, 2026-07-05) at the 6 full-forgery sites; lightweight last-field validation (no `-z`) at the 2 cosmetic sites in `lib/boot_git_checks.py`. Malformed records are skipped silently (existing pattern: `len(parts) < N → continue`).
- Prior art tests: `tests/test_boot_output.py:1428-1560` `TestControlByteRecordInjection` — reuse its payload/fixture/subprocess-isolation shape.

## Sites (from Bilbo's inventory)

Full forgery (fix = `-z` + `\x00` record split + `\x1f` maxsplit + skip-if-short):
1. `bin/git-memory-gc.py:79-92` `scan_commits`
2. `bin/git-memory-doctor.py:174-197` `check_hook_execution`
3. `bin/git-memory-doctor.py:214-292` `check_gc_status` — ONE git call parsed in TWO loops (227-263, 267-280): fix the call once, update both loops consistently
4. `lib/recall.py:157-226` `_scan_commits` — highest blast radius (feeds UserPromptSubmit/PreToolUse hooks → LLM context)
5. `lib/bootstrap_commits.py:26-80` `scan_recent_commits`
6. `hooks/precompact-snapshot.py:28-142` `extract_memory_from_log` — also LLM-facing

Cosmetic (fix = validate/rescue the trailing `%at` field, e.g. rsplit or digit-check; NO `-z`):
7. `lib/boot_git_checks.py:120-162` `get_timeline`
8. `lib/boot_git_checks.py:165-192` `get_last_context_time`

## Tasks

### Task 1: Contract tests (Dante) — RED
**Files:** new/extended test files mirroring `TestControlByteRecordInjection`
**Steps:**
- [ ] Acceptance-level repro per site (6 forgery + 2 cosmetic): real hostile commit via `--allow-empty`, assert forged scope/text absent from each function's return structure; `\x1f`-alone-is-inert guard tests
- [ ] Verify tests FAIL against current code (RED) — except any site accidentally safe
- [ ] wip commit

### Task 2: Implementation (Ultron) — GREEN
**Depends on:** Task 1
**Files:** the 8 sites above
**Steps:**
- [ ] Apply `-z` pattern (sites 1-6), lightweight validation (sites 7-8)
- [ ] Contract tests GREEN + full suite green (`pytest unmassk-toolkit/tests`)
- [ ] wip commit

### Task 3: Verify (Cerberus ∥ Argus ∥ Moriarty, then Dante hardening, then Yoda)
**Depends on:** Task 2
- [ ] Cerberus: goal-backward review; no hand-typed expected literals in round-trip tests; doctor.py one-call/two-loops consistency
- [ ] Argus: security audit incl. severity call on the LLM-facing sites (recall.py, precompact-snapshot.py) + sanitize-layer check
- [ ] Moriarty: round-trip sabotage against real git (hostile payload variants: nested separators, NUL attempts, huge records, subject-only `\x1f`)
- [ ] Dante hardening pass (exhaustion + coverage gate)
- [ ] Loop to Task 2 on T1/T2 findings; then Yoda verdict — 110/110 required
- [ ] wip commits per sub-step

### Task 4: Document (Alexandria)
**Depends on:** Task 3
- [ ] CHANGELOG [Unreleased] Security entry; three audiences check (SKILL.md gitmemory Filesystem/parsing notes if warranted, README no-op expected)

### Task 5: Close (orchestrator + Gitto)
**Depends on:** Task 4
- [ ] Squash pipeline wips → single commit with trailers → push (trunk: direct on main)
- [ ] CI green both runners; release bump (`bin/release.py`, next version) — bump is mandatory at task close
- [ ] `gh issue close 57`; strike from ROADMAP backlog line; plan marked COMPLETED; context commit

## Wave Map
Sequential: 1 → 2 → 3 → 4 → 5. Within Task 3: Cerberus/Argus/Moriarty in parallel, Dante after fixes stabilize, Yoda last.
