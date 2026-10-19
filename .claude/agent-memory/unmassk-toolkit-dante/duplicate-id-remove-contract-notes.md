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

## Round trip 4.1 (2026-10-19): search/rezones read back remove and discard

File: `test_hito3_round_trip.py`. Expected side = `indexes.read`/`read_archive` keyed by
(id, headline), plus note-commit count from `git log --format=%s`; readers = `gitmem search --id`,
`search <zone>` (+ `--todo`), `rezones --verify` counts, and `rezones` leaving index bytes unchanged.

- **Found:** after a duplicated-id `remove --commit`, search keys archive state by id only
  (`report.py` build_zone ~166-172, NoteReport archived ~304): the kept live note vanishes from the
  zone and `search --id` shows it as archivada. Which note `--id` shows flips run to run (same-second
  commits), so assert both "card state matches" AND "no live (id, headline) hidden".
- Scratch mutant copies need `git init` in the copy root: conftest resolves the real repo root via
  `git rev-parse --show-toplevel` and crashes on '' otherwise.
- Bash `git commit` is blocked by the customs hook even in scratchpad; explore with a python script.

## Fix pass after Moriarty (2026-10-19): twins on every reader

Files: `hito3_twins_support.py` (make_twins), `test_hito3_fixpass_{remove,boot,search}_twins.py`,
`test_hito3_fixpass_discard_combos.py` (26 RED, 8 green guards).

- **Deterministic twin order:** pass `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` in the env of each seed
  (run_gitmem_script adds env; gitcmd inherits it). Parametrize "archived twin newer/older": an
  id-only bug then dies in one case every run (m08 killed 3/3), never by git-log tie luck.
- **Twin bugs hide in every sibling reader:** boot (R, I and Q all), word marker, --chain,
  clusters (D twins collapse), search --id with two live twins. Check each reader, not just one.
- **Overlap rejection needs a real overlap:** `normalize_keys` drops keys that appear in the
  headline, so use keys outside it (exact-key gate) to trigger it reliably.
- **"One consistent state or refused" without branching:** assert `old_live != claimed_replaced`
  and `(rc == 0) == written` -- both legal outcomes pass, the half state fails.

## Step 5.1 reshape to D-147 (2026-10-19): boot alerts, readers not adapted

Owner's D-147: a duplicated id is an error the boot reports, not a state readers support.
Twin-reader tests (search word/--chain/clusters/--id two live, boot lists) were dropped; the boot
file now asserts the CHECKS duplicate line across live + ARCHIVED.md, one line per note with
sha[:7], both zones and headline (match rows by sha prefix, not headline: headlines also appear in
other boot blocks). Cut the CHECKS block from "CHECKS" to the next blank line.

- Today `health.duplicates` reads only live indexes (`_current_index_lines`), so one-live-one-archived
  and both-archived twins show "✓ no duplicate IDs"; `archived_notes` counts distinct ids
  ("1 archived" with two archived lines).
- Guard for the fix: normal `remove` + `--replaces` must stay ✓ (archive line is not a second copy).
## Step 5.2 "Beyond the tests" pass (2026-10-19)

Files: `test_hito3_fixpass_promotes_relaunch.py` (new), plus additions to `test_ids.py`,
`test_hito3_fixpass_{boot,remove}_twins.py`.

- A relaunch with an unquoted placeholder (`--promotes <ID de una Q real>`) is a shell redirect:
  replace the placeholder in the command string before `pasted_words`, as a person would.
- `--work` on a D: the `field_not_allowed` relaunch (validator_issue.py ~184) drops `--why` and
  never calls `carry_answer_flags`; pasted as printed it bounces again. Append `--why` in tests.
- A "rezoned" index line has no producer command: build it with `indexes.remove(only=)` +
  `indexes.insert`, then `git commit -am` in the tmp repo.
- Probe file star-importing a test module re-collects its tests; import only helpers.

- Probe a setup without adding a kept test: a temp `test_zz_*_tmp.py` importing the test file's
  helpers, run with -s, deleted after.
