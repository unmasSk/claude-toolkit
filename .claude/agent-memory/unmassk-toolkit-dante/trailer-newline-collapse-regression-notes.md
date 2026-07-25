---
name: trailer-newline-collapse-regression-notes
description: T1 regression test for build_commit_message() CR/LF-in-trailer-value collapse (bin/git-memory-commit.py) — one test, four assertion groups, GREEN
metadata:
  type: project
---

Task (2026-07-25): one regression test locking in Ultron's T1 fix —
`build_commit_message()` (`unmassk-toolkit/bin/git-memory-commit.py`) now
runs `sanitize_trailer_value()` + a double-space collapse on every
`--trailer` value before emitting it, so a real embedded `\n`/`\r\n`
can no longer split a trailer across multiple physical lines and get
silently truncated by `scan_trailers_memory()` (`lib/parsing.py`, the
recall/boot read path — splits body on literal `"\n"` only).

**File:** `unmassk-toolkit/tests/test_trailer_newline_regression.py`
**Class/test:** `TestTrailerNewlineNoSilentLoss::test_trailer_value_with_embedded_newline_survives_build_and_scan_intact`
— ONE test function, four assertion groups (LF single-physical-line +
scan_trailers_memory full recovery / anti-vacuity length check / CRLF +
multi-newline collapse, no double spaces). Consolidated into one test
because the task explicitly asked for "UN test... UNA fase", mirroring
`test_deadend_memo_round_trip.py`'s "one test, one behavior, multiple
assertion groups" shape rather than splitting into several test methods.

**Result: GREEN**, `1 passed`.

**Import pattern reused:** same as
`test_git_memory_commit_subject_length.py` —
`importlib.util.spec_from_file_location` + `exec_module` on the hyphenated
`bin/git-memory-commit.py` to reach the real `build_commit_message()`
(not importable via normal `import`, filename has hyphens). `conftest.SOURCE_ROOT`/`BIN_DIR` give the paths; `lib/` is added to
`sys.path` manually for `from parsing import scan_trailers_memory`.

**Anti-vacuity technique used (outside pytest, no prod code touched):**
built a standalone script that reproduces the PRE-FIX shape by hand
(writes `f"Memo: {raw_value}"` verbatim, skipping
`sanitize_trailer_value()`) and fed it through the REAL
`scan_trailers_memory()`. Confirmed it truncates to
`'deadend - linea1 IMPORTANTE'` and silently drops `linea2
NO_DEBE_PERDERSE` — proves the in-suite length/substring assertions
aren't trivially true regardless of the fix. This is a good general
pattern for T1 regression tests where touching prod code even
temporarily is off-limits: replicate the buggy INPUT shape by hand, not
the buggy CODE.

See also [deadend-memo-round-trip-contract-notes](deadend-memo-round-trip-contract-notes.md)
for the sibling round-trip test this one complements (deadend value
survives parse_trailers()+recall() when it has NO embedded newline; this
one covers the case where it DOES).
