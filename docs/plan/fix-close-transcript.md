# Close transcript extractor Plan

**Status: COMPLETED** (2026-10-19)
**Procedure:** Full
**Build mode:** test-first
**Base:** f6419f58
**Created:** 2026-10-19

## Goal
The session-close extractor (`unmassk-toolkit/skills/unmassk-close-session/scripts/session_transcript.py`) hands the close agent every word the owner typed in the session, and never comes out empty or partial without saying so.

## Decisions
- D-143: a redo close covers the whole session (skip this session's own earlier `[NEXT]`); `--since` bounds the commit range too; zero commits is said.
- M-155: dead-ends (not the transcript choice, not `isMeta`, not git parsing).
- Seam: yes. The script reads the `.jsonl` Claude Code writes and its output becomes the `[NEXT]` memory commit.

## Out of scope
- Rewriting the close-session skill or its agent prompt beyond documenting `--since` and the redo.
- Other record types (tool results, thinking, subagent sidechains) stay dropped.
- Peer-session messages and task notifications that arrive as `queued_command`: only `origin.kind == "human"` is the owner.

## Phases

### Phase 1: owner's words and boundaries
**Files:** modify `unmassk-toolkit/skills/unmassk-close-session/scripts/session_transcript.py`; create its tests under `unmassk-toolkit/tests/`
**Steps:**
- [x] 1.1 Dante: red tests (19: 13 red, 6 guards green) through the script's command line, on real-shaped `.jsonl` fixtures and a disposable git repo: (a) a mid-turn owner message (`attachment` / `queued_command`, `origin.kind=human`) comes out, a peer message or task notification in the same shape does not; (b) the text inside `<command-args>` of a slash command comes out; (c) `--since` bounds the commits as well as the turns; (d) zero commits in the window prints a warning; (e) a second close in the same transcript takes the previous `[NEXT]` as boundary and returns the whole session.
- [x] 1.2 Ultron: make 1.1 green (19 green; real transcript copy: both mid-turn messages come out).
- [x] 1.3 Dante: round-trip check (3 tests on 10 real-shaped records, anonymised; 4/4 mutants killed) on this session's real transcript (copy): both mid-turn messages of 2026-10-19 come out.
- [x] 1.4 Verify (22 passed): `python3 -m pytest unmassk-toolkit/tests -q -k transcript` green.

## Review
- Cerberus + Argus: 2 T2 + 1 T1 (list-shaped prompts, zero-commit warning stopped the close) fixed once.
- Moriarty: a session ended without a close lost its owner's words (D-144); fixed once with 3 surviving mutants killed.
- Yoda: REJECTED 67/110 (own close matched a sha `gitmem next` never prints; 3 breaks untested; test file too big); every point fixed once. 84 scoped tests green on Python 3.14 and 3.10.

## Wave map
- Wave 1: Phase 1
