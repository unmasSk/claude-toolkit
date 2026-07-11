---
name: issue-63-t1a-orphaned-end-userdata-loss-contract-notes
description: issue #63 Moriarty round 3 (T1-1) data-loss regression contract — T1-A's own orphaned-END fix in lib/managed_blocks.py deletes user content sitting below the corrupted block; RED test file, fixture design, verified-live boundary mechanics
metadata:
  type: project
---

Contract file: `unmassk-toolkit/tests/test_issue63_orphaned_end_preserves_user_content.py`
(2 tests, both RED). Follows straight from
[issue-63-t1-end-marker-magic-string-contract-notes](issue-63-t1-end-marker-magic-string-contract-notes.md)'s
T1-A: that fix (`lib/managed_blocks.py:212-242`, orphaned-BEGIN branch)
correctly regenerates a block whose END marker was deleted, but its
mechanism over-reaches — when a later block's BEGIN is found as a
boundary, it deletes EVERYTHING between the orphaned BEGIN and that
boundary (`content = content[:start] + rendered + "\n\n" + content[boundary:]`),
including any non-managed user text sitting in that gap (a completely
ordinary place for a user to write notes below a managed block).

**Verified live before writing the test** (unmassk-standards §34 discipline
— confirm the mechanism with a real call before asserting): built the exact
corruption in a throwaway REPL against the real `upsert_managed_blocks()`
— inserted `"USER-NOTE: never touch payments"` right after BLOCKS[0]'s END,
deleted only the END line, called `upsert_managed_blocks()`. Result:
`NOTE survives: False`, `end count: 1`, `begin count: 1`, log line
`"regenerated ... (orphaned END marker)"`. Confirms the split precisely:
T1-A's own contract (END/BEGIN recovery) already holds and is NOT what's
RED here — only the user-content-preservation assertion is.

**Fixture design (both tests combine 3 assertion groups in one test, not
split into separate cases):** real `--auto` install → insert a recognizable
literal note (`USER-NOTE: never touch payments`, deliberately specific per
the task's own anti-vacuity requirement, never a generic placeholder)
directly after BLOCKS[0]'s END marker → delete ONLY that END marker line
(same technique as T1-A's own RED test: `[ln for ln in lines if
ln.rstrip("\n") != end_marker]`) → run the real channel → assert (a) END
count == 1 and BEGIN count == 1 (T1-A's contract must still hold — a "fix"
that reverts to the pre-T1-A silent-corruption bug to avoid deleting user
text would fail here instead) AND (b) the note's raw UTF-8 bytes are still
present (the new contract). Block 0 was deliberately chosen because it is
NOT the last block in BLOCKS — `assert b0 is not BLOCKS[-1]` documents this
in the test itself, since the buggy branch's `next_positions`/boundary
logic only fires when a later block's BEGIN exists; the last-block case
takes the OTHER branch (append-only, doesn't delete anything) and would
prove nothing about this bug.

**Two channels, one shared root, per the task's own explicit permission to
avoid duplicating a heavy chain:**
1. `hooks/session-start-crew.py` — real subprocess, `installed_repo`-shape
   fixture, independent-channel verification via raw `open(path, "rb")`
   read (never through `managed_blocks.py` internals — that's the code
   under test, not the oracle).
2. `lib/install_apply.py::_update_claude_md()` — direct call in an isolated
   `python3 -c` subprocess (`sys.path.insert(LIB_DIR)`, `import
   install_apply`, `install_apply._update_claude_md(repo)`), same pattern
   `test_crew_content_gate_v2.py::_run_sabotaged_producer()` already uses
   for this exact function. Chosen over driving the full
   `needs_upgrade()` → `trigger_auto_upgrade_if_needed()` →
   `bin/git-memory-install.py --auto` chain because both channels call the
   IDENTICAL `managed_blocks.upsert_managed_blocks()` (see that module's own
   docstring: "Both session-start-crew.py ... and git-memory-install.py ...
   import this module so the 5 blocks never diverge") — a second,
   differently-shaped call into the same shared function is representative
   without the extra weight, and that heavier chain's own manifest-stamp
   gating is already covered elsewhere
   ([issue-63-producer-hardening-contract-notes](issue-63-producer-hardening-contract-notes.md)).

Verification: both tests RED for the right reason (confirmed via failure
message — `end_count_after`/`begin_count_after` assertions pass silently,
only the final `USER_NOTE.encode("utf-8") in raw_after` assertion fails,
showing the full regenerated content with the note genuinely absent). Full
suite run in background per
[issue-61-ci-flake-hardening-notes](issue-61-ci-flake-hardening-notes.md)'s
convention (>2 min runtime) — 0 production files touched, only the new test
file is untracked.
