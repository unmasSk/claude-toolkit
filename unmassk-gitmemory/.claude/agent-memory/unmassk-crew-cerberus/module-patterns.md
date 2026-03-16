---
name: unmassk-gitmemory plugin conventions
description: Key architectural conventions for this plugin's runtime file layout and path conventions
type: project
---

## Runtime directory layout

All generated/runtime JSON files live under `.claude/.unmassk/` (single gitignore entry).
Manifest is the exception: `.claude/.unmassk/manifest.json` is tracked (per-project state).
Scopes file lives in `.claude/agent-memory/*/scopes.json` (tracked, per-project).

## Scopes fallback chain (correct pattern)

Both `git-memory-commit.py` and `session-start-boot.py` check:
1. `.claude/git-memory-scopes.json` (backward-compat legacy location, checked first)
2. `.claude/agent-memory/*/scopes.json` (new primary location, glob search)

Searching old location FIRST is intentional for backward compat — do not flag as wrong order.

## ensure_runtime_dir pattern

All scripts that write to `.claude/.unmassk/` must call `ensure_runtime_dir(root)` or
`os.makedirs(..., exist_ok=True)` before writing. This is consistently done in the codebase.

## session-booted flag

`.claude/.unmassk/.session-booted` is:
- Created automatically by `session-start-boot.py` at end of successful boot
- Deleted at START of boot (fresh session clears the flag)
- `user-prompt-memory-check.py` still instructs Claude to `touch` it as a fallback
  (this covers the case where boot ran but the script path failed to create it)
