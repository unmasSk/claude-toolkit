---
name: wip-script-checkpoint-hardening-notes
description: bin/memory/wip.py first dedicated test file (2026-08-04) -- 15 tests, all green, no RED (piece pre-existed unreviewed)
metadata:
  type: project
---

**2026-08-04, memoria-v2.** `bin/memory/wip.py` (born 2026-08-03) was the
only one of ten `bin/memory/` scripts without its own `test_*_script.py`
-- only two `test_gitmem_facade.py` tests touched it, both through the
`gitmem` dispatcher, never the script alone. Wrote
`unmassk-toolkit/tests/memory/test_wip_script.py` (15 tests, all green,
no RED -- the piece already existed and worked; this was its first pass
through a reviewer, not a test-first contract).

**Technique: derive the marker from the real producer, verify with the
real consumer, never hand-type `"🚧"`.** `emojis.CHANNEL_EMOJI["wip"]`
(producer, what `wip.py` prepends) and `validator.is_wip()` (consumer,
what a real caller checks) both load via `import_lib_memory_module` and
get compared against the actual `git log -1 --format=%s` of the commit
`wip.py` just made. Same round-trip pattern as
[[capa5-scripts-red-contract-notes]].

**Binary/non-UTF8 content round trip caught a real gap in test coverage
(not a bug -- confirmed correct behavior).** `wip.py`'s own comment says
it reads each `--path` with `path.read_bytes()` as the very first
action, before touching git. Wrote raw non-UTF8 bytes
(`b"...\xe9\xff\x00..."`) to a file, checkpointed it, and compared
`git show HEAD:<path>` in raw `subprocess.run` (capture_output, no
`text=True` -- `run_git()` in conftest forces UTF-8 text mode and would
have silently corrupted the comparison) against the exact bytes written
before invocation. Passed clean -- proves `read_bytes()` really is
binary-safe end to end, not just by docstring claim.

**DEUDA.md B22 (2026-08-04, owner decision) closed the concurrency
axis for `known_content` -- do not reopen it.** The real race coverage
(two live OS processes, `write_work()`'s `known_content` parameter)
already lives in exhaustive form in
`test_notes.py::test_regression_two_real_processes_writing_same_file_
never_commit_crossed_content_under_ok_true`. For `wip.py` specifically,
only the WIRING matters (does it read first, does it pass the bytes,
does it fall back to `None` on `OSError` for an unreadable/nonexistent
path) -- not the race safety itself, which is `write_work()`'s contract,
already proven elsewhere. Wrote a nonexistent-path test for the `None`
fallback branch instead of attempting any concurrency scenario.

**Two distinct controls, one file, easy to conflate -- the task
explicitly warned about this and it's worth restating for future
scripts with a customs exemption.** `wip` is exempt from ALL customs
questions (`validator.is_wip()`, tested in `test_customs_hook.py`) but
IS still subject to branch protection (`repo_guard.py`, same mechanism
as `work.py`, decision 2026-08-03: "el checkpoint protege la rama
principal"). `test_wip_script.py` only tests branch protection; zero
tests here touch `hooks/customs.py`. A test that asserted both in one
place would blur which control actually fired.

**Error-path enumeration for wip.py's two functions (`_parse_args`,
`main`):** branch-protection reject (2 rows: explicit `gitflow` config
+ missing-config fail-closed default) · `--issue` rejected by argparse
(explicit grammar difference from `work.py`, stated in `wip.py`'s own
docstring) · nonexistent path -> real git pathspec error via
`stage_and_commit` · `.git/index.lock` -> `write_work()`'s own
`git fallo al commitear:` branch (a DIFFERENT failure branch than the
pathspec one -- add succeeds, commit itself fails) · corrupt
`config.json` (`repo_type` non-string) -> the top-level generic
`except Exception` handler, `"wip.py: <msg>"` prefix, still no
traceback. All five error branches got dedicated tests instead of only
testing the happy path.

Full suite after adding the file: `python3 -m pytest
unmassk-toolkit/tests/memory -q` -> 282 passed (was 261 at last
CLAUDE.md snapshot; net effect of parallel work by other agents plus
these 15 new tests). Confirmed zero collision with `test_validator.py`
(a different Dante's file, explicitly off-limits this task) and zero
new files besides `test_wip_script.py`.
