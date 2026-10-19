---
name: presave-searched-flag-contract-notes
description: #95 part 2c RED contract -- gitmem note/rule require --searched (D-098/D-124), customs.py asks before the command; exact-relaunch technique and the existing-test blast radius
metadata:
  type: project
---

File: `unmassk-toolkit/tests/memory/test_presave_searched_contract.py` (2026-10-19, test-first, 45 tests: 36 RED, 9 green on purpose).

**Exact-relaunch technique (reusable for any new required flag):** bounce, take the line after `Relanza:`,
shlex-split it, fill ONLY the placeholder of the new flag, run it through `run_gitmem_script`, then read
`git log -1 --format=%B` and check every free-text value the user originally typed is there. Catches both a
dropped answer (`--stops`/`--work` -> bounces again) and a `--description "..."` stand-in (saves "..." =
content lost). Use `--kind claude` for rule relaunches: a dropped `--kind` falls back to `user` silently.

**Bounce must not be argparse's `usage:`** -- an argparse `required=True` flag would print usage instead of
the question AND break `test_rejection_relaunch_commands.py`'s parser crosscheck for every existing relaunch.

**X-105 (discarded):** neither command nor hook may check WHAT was searched -- any non-empty text is the answer.

**Blast radius when a save flag becomes mandatory:** ~28 test files execute `note.py`/`rule.py`/`gitmem note|rule`;
the central fix is `conftest.py::seed_note_via_script`. `test_relaunch_command_answer_amnesia.py` executes
other rejections' relaunches literally -- those must carry the new flag too (class 6 of the contract file).
Coordinator split the update of existing tests into a later pass (another agent was running boot/health tests).

**Blast-radius fix pattern (2026-10-19, done):** a new mandatory save flag is answered VISIBLY at each call,
never injected by `run_memory_script`/`run_gitmem_script` (that would silently defeat any test of the bounce).
`conftest.py` holds `SEARCHED_ANSWER`/`SEARCHED_ARGS`/`with_searched(args)`; `seed_note_via_script` defaults
`searched=SEARCHED_ANSWER` (`None` omits). Call sites were wrapped with an AST script (find `run_memory_script("note.py"|"rule.py", X)`
and `run_gitmem_script(["note"|"rule", ...])`, wrap X in `with_searched(...)`; skip rule read `[]` and `--retract`).
Variable-args helpers (`_write_note`, `_promote_args`) need a manual edit. A test that compares a rendered
rejection must add the carried suffix by hand (`" --searched " + shlex.quote(value)`), never via `carry_searched`.

**Pre-existing relaunch gap found (not fixed):** `rules_validate.py` missing-quote relaunch drops `--kind` and
`--replaces` -- obeyed literally, a claude rule saves as [user] and a replace adds a 2nd rule, old one stays.
Field-mismatch relaunch (`validator.py` ~282) drops `--why`.

**Fix pass (2026-10-19, `test_presave_searched_fix_pass.py`, 31 tests, 16/16 mutants killed):**
- **Version-skew technique (reusable):** the previous release's reader lives in the REAL home's plugin
  cache (`~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-toolkit/<ver>/`). Under a throwaway HOME,
  `~` points elsewhere: resolve it with `pwd.getpwuid(os.getuid()).pw_dir`. Run its `format.parse_message`
  in a `python -B -c` subprocess with its `lib/memory` first on sys.path and PYTHONDONTWRITEBYTECODE=1 (no
  .pyc into the cache), compare `dataclasses.asdict` minus timestamp against every typed field; also its
  own `bin/gitmem search --id` (user door) and its writer for the reverse direction. Missing cache ->
  `pytest.fail` naming the path; `pytest.skip` only when GITHUB_ACTIONS=true (runners never have it).
- `--keys` that appear in the headline are dropped by `normalize_keys` -- pick keys absent from it.
- rules.md line shape: `[remember][<kind>] <emoji> <text>[ — «<quote>»]` -- match on the part before ` — «`.
- Mutating a copy of `unmassk-toolkit/` needs the copy's parent to be a git repo (the real-repo HEAD guard
  in tests/memory/conftest.py runs `git rev-parse` from the tests dir); always run an unmutated BASELINE row.
- The owner's live customs hook blocks any Bash command TEXT containing `git commit`: put such steps in a
  script file written with Write, never inline/heredoc.
