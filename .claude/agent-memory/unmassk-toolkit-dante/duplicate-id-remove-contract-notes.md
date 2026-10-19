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

## Fix pass (2026-10-19): duplicated I-, relaunch paste, --replaces guard, discard refusal

Files: `test_remove_duplicate_incident_contract.py`, `test_remove_replaces_guard_contract.py`,
`test_note_discard_refusal_contract.py` (8 RED, 11 green guards).

- **Ambiguous sha prefix, built for real:** rewrite the clone's HEAD commit (same tree and message,
  committer time + k) until `sha1(b"commit %d\0" % len(body) + body)` shares 4 hex chars with the other
  note's sha; write it with `git hash-object -t commit -w --stdin`, `git update-ref HEAD <sha>`, then merge.
  ~65k sha1 tries, under a second. Never rely on luck for a prefix collision.
- **Different zones per clone** make "the wall is born in the picked incident's zones" checkable.
- **Seeding an R in a zone that already holds an incident** needs `--origin none` (or the incident id),
  otherwise the origin question bounces the seed.
- **Run every relaunch you assert on:** extract the `Relanza:` block, split through a real shell
  (`printf '%s\0'`), run `words[1:]` through `run_gitmem_script`, read the state back. A `"..."` word is the
  one gap to fill; the fence retry's `--searched` placeholder too.
- **Partial-act git failure:** a pre-commit hook refusing only commits that stage `DISCARDED.md` lets the
  decision land and fails every X -- same trick as the RESTRICTIONS.md hook for the fence.
