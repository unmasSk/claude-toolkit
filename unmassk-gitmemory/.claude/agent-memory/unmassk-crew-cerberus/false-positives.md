---
name: false positives for unmassk-gitmemory reviews
description: Patterns that look like bugs but are intentional design choices
type: project
---

## test_context_writer.py references old paths (e.g. `.context-status.json`)

Lines 54, 82, 116, 132 reference `.claude/.context-status.json` (without `.unmassk/` subdir).
This IS a real test bug — the test was NOT updated to match the new `.claude/.unmassk/context-status.json` path.
Do NOT mark as false positive — this is a real failing test.

## test_bootstrap.py uses `git-memory-manifest.json` at `.claude/` root (line 162)

This test creates `.claude/git-memory-manifest.json` (old path) to simulate "already installed".
The bootstrap scanner `check_existing_memory()` checks `.claude/.unmassk/manifest.json` (new path).
The test would NOT detect the installation. This is a real bug in the test.

## user-prompt-memory-check.py tells Claude to `touch` the booted flag manually

Line 110: `f'After booting, run: touch "{booted_flag}"'`
This is intentional defense-in-depth: if `session-start-boot.py` ran but failed to create
the file (e.g. import error, partial boot), Claude's manual touch is the fallback.
NOT a bug — the redundancy is deliberate.

## git-memory-scopes.json checked first in fallback chain

Both commit.py and boot.py check the old `.claude/git-memory-scopes.json` location BEFORE
agent-memory. This is intentional backward compat, not a wrong order.
