# Rules and checklist at boot Plan (task = issue #95, step 2)

**Issue:** #95
**Branch:** main (trunk)
**Procedure:** Full
**Build mode:** test-first
**Created:** 2026-10-19

## Goal
Every session starts with the memory briefing and the owner's rules already in Claude's context, without anyone reading them by hand.

## Decisions
- I-005: the boot hook is killed at 30 s; `health_plans.plans_unreflected` asks GitHub once per cited issue, serially.
- D-130: one batched GitHub query under a total deadline; `boot_launcher` keeps its own deadline and fails loud.
- D-087 (rules whole at boot), D-124 (per-message checklist), D-102 (Morse): phase 2, after its gray areas are settled with Bex.
- Seam: yes — the boot reads files other commands write (`rules.md`, `boot-latest.txt`).

## Phases

### Phase 1: Boot finishes inside the hook timeout
**Files:** modify `unmassk-toolkit/lib/memory/health_plans.py`, `unmassk-toolkit/hooks/boot_launcher.py`; tests in `unmassk-toolkit/tests/`
**Steps:**
- [ ] 1.1: Dante — complete test set, red, run through the hook itself (slow `gh` stub, ~40 cited issues; loud notice on overrun; error line instead of an invented result)
- [ ] 1.2: Ultron — code until green
- [ ] 1.3: verify — `python3 -m pytest` on the new tests + the boot/health tests; real boot from the repo root under 30 s
- [ ] 1.4: Cerberus + Argus, blind; one fix pass
- [ ] 1.5: WIP

### Phase 2: Rules, checklist and sound
Gray areas decided by sector rule in auto mode (Bex asleep, 2026-10-19): D-131 (rules via CLAUDE.md import), D-132 (Morse on Notification). D-124/D-098 already fix the checklist and the pre-save field.

**2a · Rules whole at launch (D-087, D-131)** — `lib/managed_blocks.py`
- The unmassk-toolkit block imports `@.claude/project-memory/rules.md`, saying they bind from the first message.
- Its step 1 stops claiming the briefing is "already in your context": it names the `[memory]` lines of the session start, and says that if none arrived the boot failed and the user is told in the first line.

**2b · Per-message checklist (D-124)** — `hooks/user-prompt-memory-check.py`
- Every message carries the three D-124 questions, plus the sector-first question for when options are proposed.

**2c · Pre-save search (D-098, D-124)** — `hooks/customs.py`, `bin/memory/note.py`, `bin/memory/rule.py`, `lib/memory/validator.py`
- `gitmem note` and `gitmem rule` require `--searched "<what I searched>: <what I found>"`, stored in the commit; without it they bounce with the question.
- customs.py, before a `gitmem note`/`gitmem rule` without `--searched`, blocks with the D-098 question.

**2d · Morse cue (D-102, D-132)** — `hooks/hooks.json`, new `hooks/owner-cue.py`
- Notification hook, matcher `permission_prompt|idle_prompt`: Morse three times 0.3 s apart; never blocks; no-op without afplay. Tests never play sound.

**Steps (each part):** Dante red tests → Ultron green → Cerberus + Argus → one fix pass → WIP.
**Then, once for the whole issue step:** Moriarty → fix → Yoda → fix → Alexandria (CHANGELOG, memory skill fields, three audiences) → scoped tests → push. Publishing waits for Bex.

## Wave Map
- Wave 1: Phase 1 (Ultron) ‖ 2a, 2b, 2c, 2d (Dante) — no shared files
- Wave 2: 2a, 2b, 2c, 2d (Ultron), after their tests
- Wave 3: reviewers per part, then Moriarty, Yoda, Alexandria
