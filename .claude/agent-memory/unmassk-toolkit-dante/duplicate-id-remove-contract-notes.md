---
name: duplicate-id-remove-contract-notes
description: #105 1.1 D-145 RED: making a real duplicated id (clone + union merge), worktree gotcha, count-in-output regex
metadata:
  type: project
---

Files: `unmassk-toolkit/tests/memory/test_remove_duplicate_id_contract.py`,
`test_remove_restriction_replaces_contract.py` (2026-10-19, test-first, 9 RED).

**Make a duplicate id the way it really happens**, never by hand-editing an index:
seed a base note (so the index file is tracked), `git clone` the tmp repo, write the
next id with `gitmem note` in both, write `*.md merge=union` into `.git/info/attributes`,
`git fetch <clone> HEAD` + `git merge --no-edit FETCH_HEAD`. Both index lines survive;
each note has its own commit sha (`git rev-parse HEAD` right after the seed).

**Gotcha:** use a clone, not `git worktree add`: every gitmem write fails in a
worktree (`notes_commit.lock_resource` builds `<root>/.git/memory-notes`, `.git` is a
file there -> Errno 20). Reported as a bug, not fixed.

**Count in output without inventing a format:** regex `(?<![\w-])1(?![\w-])` on stdout
-- skips digits of ids (`M-001`) and dates; keep reason/headlines digit-free.

**Red for the right reason when today's failure is argparse:** assert `rc == 1` (the
rejection code) and `"unrecognized arguments" not in output`; argparse exits 2.

Fake HOME per call: `env={"HOME": tmp, "USERPROFILE": tmp}` on `run_gitmem_script`.
