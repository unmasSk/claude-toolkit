---
name: notes-three-critical-regressions-notes
description: unmassk-memory (v2) 3 critical fixes locked into test_notes.py (2026-08-02) -- blank-paragraph-lost-forever cross-seam round trip (notes.write real git + query.by_id), restore-on-exception, restore-shadowing-real-diagnostic; module-attribute monkeypatch technique for phantom-loaded siblings
metadata:
  type: project
---

Context: three critical bugs, already fixed and hand-verified by the
owner (not by any test), had zero test coverage locking them in. Task:
add them as permanent regressions. All three landed in
`unmassk-toolkit/tests/memory/test_notes.py` (baseline 69 green -> 72
green, zero regressions), not in three separate files -- two of the
three live in `notes.py`'s `write()`, and the file already had every
fixture (`make_note`/`make_context`/`_cwd`/`_forced_git_index_lock`/
`_read_all_index_contents`) the tests needed. Added one `query` fixture
for the third.

**The worst bug in the whole system, and the one whose test had to
cross a seam no existing test crossed:** `format._fold_raw` (Sec.6.4)
encodes a blank line inside a folded field as a continuation line
containing EXACTLY one space. Git's DEFAULT cleanup mode
(`--cleanup=strip`) strips trailing whitespace per line on commit -- that
line goes empty. On reread, `_parse_body_fields` doesn't recognize an
empty line as either a field start or a continuation, returns `None`;
`parse_message` propagates it; `query._parse_records` silently drops any
commit that doesn't parse. **Why no existing test saw it:**
`test_format.py`'s round trips are all IN-MEMORY (`build_message` ->
`parse_message` directly, no git involved); `test_query.py` commits for
real but none of its seeded notes has a two-paragraph field. The bug
lived in the seam between what the system writes and what git actually
stores, and nothing tested that seam. **The regression test crosses it
for real:** `notes.write()` against a real temp git repo, then
`query.by_id()`/`by_zone()`/`by_word()` -- never `format.parse_message`
directly. The fix is `gitcmd.commit()` adding `--cleanup=verbatim`.

**Reusable technique: get the EXACT module instance a production module
uses internally, to monkeypatch it correctly, when the test harness
loads siblings by file path (`import_lib_memory_module`, see
[memoria-v2-fase0-conftest-notes](memoria-v2-fase0-conftest-notes.md)
and the cross-import-identity risk in
[format-contract-cross-import-risk-notes](format-contract-cross-import-risk-notes.md)).**
`notes.py` does plain `import format`/`import gitcmd`/`import ids`/
`import indexes` (PIEZAS Sec.3.3bis flat-import convention) -- these
bind as MODULE-LEVEL ATTRIBUTES on the `notes` module object itself.
So instead of guessing whether the `format`/`gitcmd`/`indexes` fixture
(each loaded separately via `import_lib_memory_module`, a DIFFERENT
phantom instance per the cross-import-identity finding) is the same
object `notes.write()` actually calls into, just reach through the
already-loaded `notes` fixture: `monkeypatch.setattr(notes.gitcmd,
"commit", fake)` / `monkeypatch.setattr(notes.indexes, "remove", fake)`.
This is guaranteed to be the exact instance `notes.py`'s own code path
uses, no identity guessing needed, and `monkeypatch` still auto-reverts
it after each test even though the underlying module object is cached
process-wide via `import_lib_memory_module`'s content-hash cache.

**Fix 2 (restore only covered `returncode != 0`, not a real exception mid-commit):**
forced `notes.gitcmd.commit` to raise `RuntimeError` (simulating a
Ctrl-C) right after `indexes.insert()` already wrote the index line for
real. Asserted the exception still propagates (`pytest.raises`) AND the
seven live index files are byte-identical to the pre-write baseline
(reused `_read_all_index_contents` from row 2's existing test). The fix
is a `try/except BaseException: restore; raise` wrapping the
build-message+commit call in `notes.write()`.

**Fix 3 (restoration's own failure shadowed the real git diagnostic):**
combined a REAL git failure (`.git/index.lock` pre-created, same
technique as rows 2/3 -- see
[notes-contract-real-git-failure-notes](notes-contract-real-git-failure-notes.md))
with `notes.indexes.remove` also raising during the restoration that
follows. Asserted `write()` does NOT raise the secondary exception, and
`result.git_error` is the REAL git message (verified via a live probe --
a second real `git commit` against the same locked repo, first stderr
line must appear in `result.git_error`, same anti-fabrication technique
as the existing row-3 test, unmassk-standards Sec.34), never containing
the restoration's own marker text. The fix is `_restore_index_best_effort`
wrapping `indexes.remove()` in `try/except Exception: pass`.

**Mutation-check methodology (all three, confirmed live before writing
the pytest versions):** copied all of `lib/memory/*.py` into three
scratchpad dirs (`mutcheck/lib_memory_broken1|2|3/`, never
`lib/memory/` itself), undid exactly one bug's mechanism per copy
(removed `--cleanup=verbatim` / removed the `try/except BaseException`
wrap / removed the `try/except Exception` guard), and ran three
standalone probe scripts (`probe1_blank_paragraph.py`,
`probe2_restore_on_exception.py`, `probe3_restore_shadow.py` -- plain
asserts, no pytest, run via `python3 probe.py <lib_dir>` against both
the broken copy and the real `lib/memory/`) that reproduce the exact
pytest scenario. All three: FAIL against the broken copy (note lost /
index not restored / secondary exception propagates), PASS against the
real fixed code -- confirmed before a single pytest line was written.
Same generator/probe pattern as
[five-regressions-format-zones-notes](five-regressions-format-zones-notes.md),
extended here to exercise real git subprocess calls (temp repo per
probe, cleaned up in `finally`), not just in-memory round trips.

Verification: `python3 -m pytest unmassk-toolkit/tests/memory -q` ->
72 passed (baseline 69 + 3), run 4x for flake-check, stable every time.
`--collect-only` -> 72 tests, zero collection errors. Only file touched:
`unmassk-toolkit/tests/memory/test_notes.py` (added one `query` fixture
+ three regression tests at the bottom, same "REGRESION" heading
convention as test_format.py's bottom section). No production code
touched at any point -- confirmed via `git status --porcelain` showing
no `lib/memory/*.py` changes.

See also: [notes-contract-real-git-failure-notes](notes-contract-real-git-failure-notes.md)
(the `.git/index.lock`-forcing and git-probe techniques this session's
fix-3 test reuses), [format-contract-cross-import-risk-notes](format-contract-cross-import-risk-notes.md)
(the cross-import-identity finding that motivated reaching through
`notes.gitcmd`/`notes.indexes` instead of a separately-loaded fixture),
[five-regressions-format-zones-notes](five-regressions-format-zones-notes.md)
(the scratchpad generator/probe mutation-check pattern this session
extended to real git subprocess calls).
