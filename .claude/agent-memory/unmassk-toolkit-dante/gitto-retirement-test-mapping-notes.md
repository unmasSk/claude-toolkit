---
name: gitto-retirement-test-mapping-notes
description: Read-only mapping of tests depending on retired Gitto agent / v1 memory system (crown, consolidation trigger, agent-count assumptions)
metadata:
  type: project
---

Mapping pass (no edits) after `agents/gitto.md` moved to `deprecated/gitto.md` and crew went 10→9. Task: find tests depending on gitto.md content, agent-count assumptions, or the crown/consolidation-trigger mechanism (executed by Gitto, dies with v1 memory).

**Baseline drift:** measured 780 collected / 7 collection errors, vs a prior reference of 770/7. Error count matched, collected count did not — not investigated further, out of scope.

**Family 1 (gitto.md references):** only 2 files cite the path (`test_pre_validate_commit_trailers_git_log.py`, `test_crown_retraction.py`), both in comment/assertion-message text only — never `open()`/`read_text()` against it. `test_pre_validate_commit_trailers_git_log.py` (8/8 pass) is fully alive: the gitto.md citation is historical rationale for a still-live hook exemption (`BLOCK_DIRECT_GIT_LOG` in pre-validate-commit-trailers.py), not a dependency.

**Family 2 (agent count / roster):** zero hits anywhere in `tests/*.py`. Grepped all 9 crew names + "gitto" + "agents" — every hit is an attribution comment ("Moriarty found X"), never a glob/listdir over `agents/` or an asserted list length. **Don't assume this exists — verified absent.**

**Family 3 (crown / consolidation trigger / retraction):** 3 files, 45 tests, 43 already failing pre-cleanup:
- `test_consolidation_trigger.py` (11 tests, 0 pass) — contract for `CONSOLIDATE:`/`commits_since_last_consolidation()`, never reached GREEN. `hooks/session-start-boot.py:9-13` docstring explicitly confirms this section "was removed with the rest of the v1 memory system."
- `test_crown.py` (21 tests, 1 pass) and `test_crown_retraction.py` (13 tests, 1 pass) — `lib/boot_render.py:12-18` docstring explicitly confirms crown rendering helpers were removed in the v1 cleanup. The lone passing test in each file only checks `"Crown"`/`"Retract-Crown"` membership in `lib/constants.py::VALID_KEYS` — a leftover constant with zero live consumers, not a survivor of real behavior. Worth flagging to whoever decides deletion: that constant is itself dead weight now.

**Gotcha for future passes:** a filename containing "consolidation" is not proof of family membership — `test_parsing_consolidation.py` (one of the 7 collection errors) is about parsing/normalization refactor consolidation, unrelated to Gitto's memory-consolidation trigger. Read the docstring before classifying by name.

**Technique:** to confirm "does removed-looking test X still protect live code", grep the *docstring* of the module the test imports from — this codebase leaves explicit "removed with v1 memory system, see docs/memoria-v2/PLAN-CONSTRUCCION.md §5.3" breadcrumbs in `boot_render.py` and `session-start-boot.py` rather than silently deleting. Faster and more reliable than tracing call graphs by hand.
