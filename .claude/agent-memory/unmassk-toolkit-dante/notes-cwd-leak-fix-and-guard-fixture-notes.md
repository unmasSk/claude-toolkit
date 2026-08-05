---
name: notes-cwd-leak-fix-and-guard-fixture-notes
description: Fixed the 5 notes.write() seed calls outside _cwd() in test_notes.py (rows 7-10, real-repo pollution incident); added conftest.py autouse HEAD-diff guard; monkeypatch-fixture-teardown-order gotcha when mutation-checking an autouse fixture
metadata:
  type: project
---

2026-08-02, urgent fix requested by the owner (already diagnosed and
verified by him). Same root cause Ultron had already logged in his own
memory (`memoria-v2-notes-cwd-incident` in the ultron agent's
MEMORY.md): `unmassk-toolkit/tests/memory/test_notes.py` seeded old
notes via `notes.write(old_note, make_context())` *outside* the
`with _cwd(root):` wrapper the rest of the file uses correctly.
`notes.write()` resolves its target repo from `Path.cwd()` — with no
`_cwd(root)` active, that's the real claude-toolkit checkout, not
`tmp_repo`. Measured damage: 70 real commits on `feat/memoria-v2` plus
8 stray index files (`MEMOS.md`, `ARCHIVED.md`, `DECISIONS.md`, ...) at
the project root, growing by ~5 more every time the file ran.

**Correction to Ultron's count:** his memo says "four seed calls" (rows
7/8/9/10). It's actually **five** — row 10 seeds *twice* in the same
test (once for the `replace()` half, once for the `close()` half), both
outside `_cwd`. Exact lines fixed (all now wrapped in their own
`with _cwd(root):`): row 7 (~759), row 8 (~849), row 9 (~898), row 10
part A (~962) and row 10 part B (~990).

**Swept every other file in `tests/memory/` for the same shape** before
declaring done — required by the owner ("`_cwd` es un ayudante local...
otros ficheros pueden tener el mismo agujero sin saberlo"). Method: grep
every file for its write-capable call (`notes.write/replace/close/
write_work`, `gitcmd.commit`) and cross-check the line number sits
inside a `with _cwd(...)`/after a `monkeypatch.chdir(tmp_repo)` that
precedes it in the same test body, not just present somewhere in the
file. Clean: `test_health.py`, `test_report.py`, `test_report_render.py`,
`test_context.py`, `test_dispatch.py` (its `_seed_note()` helper isn't
self-wrapped, but the one caller does `monkeypatch.chdir(tmp_repo)`
*before* any `_seed_note()` call — order matters, both need auditing
independently), `test_query.py`, `test_gitcmd.py`, `test_rules.py`.
Files like `test_indexes.py`/`test_ids.py`/`test_format.py` never touch
`Path.cwd()` at all (their modules take an explicit `root` param) — no
risk class there.

**Added a real safety net, not another wrapper to remember** —
`conftest.py::_guard_against_writing_to_the_real_repo`, autouse,
function-scoped. Captures `git rev-parse HEAD` of the REAL repo (root
resolved once via `git rev-parse --show-toplevel` run with
`cwd=_TESTS_MEMORY_DIR`, a path that never moves) before and after
every test in `tests/memory/`; if HEAD differs, `pytest.fail()` names
the nodeid and the likely missing wrapper. Compares the SHA, not
`rev-list --count`, so it also catches `--amend` or a branch switch, not
just a new commit at the tip.

**Mutation-check gotcha worth remembering for any future autouse-guard
verification:** first attempt used pytest's `monkeypatch` fixture inside
a throwaway test to fake `subprocess.run`'s return for the HEAD check —
it silently never triggered the guard. Cause: fixture teardown is LIFO.
The autouse guard is set up before `monkeypatch` (autouse fixtures
resolve first), so at teardown `monkeypatch` restores `subprocess.run`
to the real one *before* the guard's post-`yield` code runs — the guard
ends up reading the real (unchanged) HEAD every time, a false "it
works". Fix: patch `subprocess.run` with a raw direct assignment (no
`monkeypatch`, no restore) inside the throwaway test — since the whole
one-off `pytest` invocation gets thrown away right after, there's
nothing to restore. That version correctly produced a teardown `ERROR`
naming the test's nodeid. General lesson: **never use `monkeypatch` to
mutation-check something that lives in an autouse fixture's teardown
code** — its own teardown races against exactly the code you're trying
to prove fires.

**Verification the owner asked for:** commit count/HEAD sha of the real
repo before and after running `pytest tests/memory/test_notes.py`
(only that file, per instruction — did not run the full `tests/memory`
suite). Before: `010ced6`, 1805 commits. After: `010ced6`, 1805 commits,
15/15 passed. No new files appeared anywhere outside
`tests/memory/{conftest.py,test_notes.py}` in `git status`.

**Did NOT do** (explicitly forbidden by the owner): no `git reset`/
`rebase`/`checkout`/`restore`/`stash`, did not delete the 8 stray root
files (queued for a separate fix), did not run the full `tests/memory`
suite, did not touch anything in `lib/memory/` or other agents' test
files beyond the audit-read.
