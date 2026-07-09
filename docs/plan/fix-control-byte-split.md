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
- [x] Cerberus — goal-backward review. Verdict: not mergeable. 1 issue (recall.py maxsplit=3 should be 2), 1 suggestion (doctor.py one-call/two-loops), 2 nitpicks
- [x] Argus — security audit. Verdict: 2 CRIT, 1 MED, 2 LOW. `-z` closes record forgery, but sanitization gaps re-open the class on LLM-facing sites
- [x] Moriarty — round-trip sabotage. Verdict: FALLA. 5/6 sites lose/corrupt real trailer data under a stray `\x1f`; `-z` boundary itself solid (real NUL-forgery + push tested)
- [ ] **Loop → Task 2b (findings consolidated below)**
- [ ] Dante hardening pass (exhaustion + coverage gate) — after 2b GREEN
- [ ] Re-verify (Argus re-audit mandatory per his rule; Cerberus/Moriarty re-check) then Yoda verdict — 110/110 required

### Task 2b: Remediation round (Dante extends contract RED → Ultron GREEN)
**Consolidated findings — same vuln class as #57 (hostile git history → parsed fields / LLM context). Decision commit `45cba61`.**

Field-alignment (T1 — the DoD "no field displacement" is not met):
- [ ] `lib/recall.py:194,209` — `maxsplit` 3→2 (3-field record)
- [ ] `bin/git-memory-gc.py:113` — `%b` not last (`%at` follows); align maxsplit / reorder so injectable field is last
- [ ] `bin/git-memory-doctor.py:198,248,288` — same, both loops
- [ ] `bin/git-memory-bootstrap`→`lib/bootstrap_commits.py:61` — same (5-field; date/author corruption)
- [ ] Pattern reference: `hooks/precompact-snapshot.py:73,84` (already correct — copy its shape)

Sanitization (CRIT/MED/LOW — LLM-facing fence + terminal/commit injection):
- [ ] `lib/recall.py:215-216` — sanitize `scope` before building `label` (mirror `boot_memory.py:231` SEC-CRIT-NEW-04) — closes `</memory-data>` fence break
- [ ] `hooks/precompact-snapshot.py:96-106` — sanitize `scope` + `subject` (mirror `boot_memory.py:224-225`)
- [ ] `bin/git-memory-gc.py:213,259,278,297` — apply `sanitize_trailer_value` to trailer text before print + before embedding in new tombstone commit
- [ ] `hooks/stop-close-session.py:57,84` + `hooks/stop-dod-check.py:112,140` — `.splitlines()` → `.split("\n")`
- [ ] `hooks/stop-dod-check.py:156-166` — sanitize `Next:` value
- [ ] `lib/parsing.py:163` `sanitize_trailer_value` — add `\x7f` (DEL) to stripped set (verify no legit use; Moriarty gap)

Order: Dante extends `test_control_byte_injection.py` with RED cases for field-displacement (real trailer after stray `\x1f` survives) + fence-break (scope with `</memory-data>` sanitized) + splitlines + `\x7f`; then Ultron GREEN; wip per sub-step.

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
