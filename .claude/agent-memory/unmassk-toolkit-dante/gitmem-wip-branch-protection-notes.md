---
name: gitmem-wip-branch-protection-notes
description: test_gitmem_facade.py wip test fixed after 2026-08-03 decision (checkpoint protects main); same seed_config_json technique as test_work_script.py, plus new rejection regression
metadata:
  type: project
---

Fixed the one red test in `unmassk-toolkit/tests/memory/test_gitmem_facade.py`
(`TestDispatchesToTheRealSubcommandScript::test_gitmem_wip_produces_a_real_commit_that_validator_is_wip_recognizes`).
Root cause was not a code bug: the owner decided on 2026-08-03 that the `wip`
checkpoint protects the main branch exactly like `work.py` does (fail-closed:
no `config.json` -> `repo_type="gitflow"` -> bounces on `main`). The test
predates that decision and seeded no config, so it now legitimately bounces.

Fix: seeded `config.json` with `repo_type="trunk"` via the existing
`seed_config_json()` fixture helper (`tests/memory/conftest.py:511`) before
invoking `gitmem wip` — the exact same technique `test_work_script.py`
already uses to unblock its main-branch commits. No production code touched.

Also added the missing regression: `TestWipRejectsDirectCommitToProtectedMainBranch`
in the same file — no config seeded (default fail-closed), asserts `wip`
bounces on `main` with rc != 0, non-empty message, no traceback, AND (the
part that matters most) HEAD's SHA and commit count are unchanged before vs.
after — a rejection that already wrote is not a rejection. Mirrors
`test_work_script.py::TestProtectedRepoRejectsDirectCommitToMainBranch`
exactly (same repo_guard.py mechanism shared by work.py and wip.py).

Mutation-check performed and reverted: temporarily changed
`if cfg.repo_type == repo_guard.PROTECTED_REPO_TYPE:` to
`if False and cfg.repo_type == ...` in `bin/memory/wip.py`, confirmed the new
rejection test goes red for the right reason (checkpoint commits anyway,
rc==0) while the fixed dispatch test stays green, then restored the file and
diffed byte-identical against a scratchpad backup before reporting.

**Why:** DEUDA.md PARTE 1 (owner decisions, 2026-08-03) is the source of
truth for this branch — a red test caused by a same-day requirement change is
not evidence of a code bug; check DEUDA.md PARTE 1 before assuming Ultron's
code is wrong.

**How to apply:** when a test in this branch goes red and DEUDA.md PARTE 1 has
a same-day entry touching that behavior, read the decision first. Reuse
`seed_config_json()` — never hand-roll a second way to write `config.json`.
See also [config-contract-notes](config-contract-notes.md) and
[capa5-work-branch-protection-and-similarity-fix-notes](capa5-work-branch-protection-and-similarity-fix-notes.md)
for the original `repo_type` fail-closed contract on `work.py`.
