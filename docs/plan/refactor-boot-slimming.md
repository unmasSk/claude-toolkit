# Boot slimming Plan (task = issue #89)

**Issue:** #89
**Branch:** refactor/boot-slimming
**Procedure:** Full
**Build mode:** test-first (code); text moves checked by rule inventory
**Base:** f5121876
**Created:** 2026-10-19

## Goal
Everything Claude reads at session start gets shorter without losing a single rule: what leaves a boot-read file goes to memory, an issue, a skill reference loaded on demand, or a path rule, never to another boot-read file, and every short version says where the long one is.

## Decisions
- Owner, 2026-10-18 (#89 comments): the four points of https://claude.ai/artifact/PiGXihJwCxvVCzNZK97Bx5, the verification plan (rule inventory first, blind check, separate branch, fresh-session test) and the order (release skill → CLAUDE.md → boot report → core and memory).
- D-094: nothing leaves without a pointer to its full version.
- D-131: the owner's rules arrive by the `@rules.md` import; the managed block keeps it.
- Core rule 14 (owner, 2026-10-18): until #87 ships, a step's WIPs are pushed as they are; `CLAUDE.md:92` (D-118 squash wording) is aligned to it.
- Core rule 38: one source of truth per fact in what Claude reads; the progress-line rule stays only in core.
- Rebase of the proposal against today's files: .claude/informes/alexandria-2026-10-19-124553-89-boot-slimming-check-c333.md.

## Out of scope
- The project-cleanup skill and its boot check line (D-100): not built; its own issue waits on the owner.
- M-140 is not a sizing argument (owner: never design around compaction).
- Other projects' CLAUDE.md files.

## Phases

### Phase 0: inventory
- [x] 0.1 Bilbo (316 rules: .claude/informes/bilbo-2026-10-19-104858-boot-rule-inventory-63c6.md): numbered list of every rule in core, memory, the managed block and this repo's CLAUDE.md, before anything is touched.

### Phase 1: release skill
**Files:** create `.claude/skills/release/SKILL.md`
- [x] 1.1 Orchestrator: the release procedure moves from CLAUDE.md to a project skill of this repo.

### Phase 2: this repo's CLAUDE.md
**Files:** `CLAUDE.md` (own part)
- [x] 2.1 Orchestrator: rewrite the own part from `.claude/informes/CLAUDE.propuesto.md`, rebased on today (status paragraphs to memory/issues, broncas only where rules.md or core do not already say them, `lib/memory/` ban to `.claude/rules/`), in English.

### Phase 3: managed block
**Files:** `unmassk-toolkit/lib/managed_blocks.py`, `unmassk-toolkit/tests/test_managed_blocks.py`
- [x] 3.1 Dante: red tests for the shorter block (keeps the rules import and the file-based report step; protocols menu short; communication without the progress rule; build-mode block retired as legacy).
- [x] 3.2 Ultron: make 3.1 green.

### Phase 4: boot report
**Files:** `unmassk-toolkit/bin/memory/boot.py` and its tests; `unmassk-close-session` prompt and SKILL (orchestrator)
- [x] 4.1 Dante: red tests — restrictions headline-only with one pointer line; issues one line per OPEN issue with live work notes, through the boot's single bounded GitHub call (R-025); discards and closed issues out.
- [x] 4.2 Ultron: make 4.1 green.
- [x] 4.3 Orchestrator: close prompt — Next about 25 lines, no commit tail, and a corrections block with the owner's literal words.

### Phase 5: core and memory
**Files:** `unmassk-toolkit/skills/unmassk-core/` and `unmassk-memory/` (orchestrator); `unmassk-toolkit/lib/skill_router.py`, `unmassk-toolkit/lib/hooks_doc.py`, `bin/hooks_doc_sync.py` and tests (Dante, Ultron)
- [x] 5.1 Orchestrator: move to references the sections the proposal names (automatic mode, documentation discipline, protocol table, Red Flags; Rationalizations, issue customs, zones, four cases, hooks table), each with its pointer.
- [x] 5.2 Dante: red tests — the automatic-mode reminder points to the new reference; the hooks table is generated into `references/hooks.md`.
- [x] 5.3 Ultron: make 5.2 green.

### Phase 6: verification
- [x] 6.1 Moriarty (3 weakened CLAUDE.md rules restored; R-008 holds the write rule), blind: every rule of the 0.1 inventory is still in a boot-read file or in a reference a pointer names.
- [x] 6.2 Fresh session (4 headless cases on a copy: automatic mode, Q note customs, release, write permission — each answered from the right file; CLAUDE.md not reverted) on the branch (`--plugin-dir`): case questions from the inventory; it answers right and opens the right reference.
- [x] 6.3 Measured: CLAUDE.md 22,681 → 8,440 B; core 36,662 → 32,170 B; memory 28,068 → 22,762 B; boot report 18,488 → 10,934 B (the Next shrinks further from the next close).

## Wave map
- Wave 1: Phase 0
- Wave 2: Phases 1, 3, 4, 5.2-5.3 (independent files)
- Wave 3: Phases 2, 4.3, 5.1 (text, after the inventory)
- Wave 4: Phase 6
