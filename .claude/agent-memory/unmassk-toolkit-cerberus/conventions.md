---
name: project-conventions
description: unmassk-toolkit project conventions for commit types, branch patterns, and empty commits
type: project
---

# Project Conventions

## Empty commits are intentional
Commits with types `context`, `decision`, `memo`, `remember` are intentionally --allow-empty.
They carry git trailer metadata (Remember:, Memo:, Decision:, Next:) consumed by session-start-boot.py.
Do NOT flag them as "empty commits" — that is the design.

## GC tombstone commits
Commits prefixed `context(claude): GC: tombstone` are --allow-empty and carry `Resolved-Remember:` or `Resolved-Memo:` trailers.
They suppress old entries from appearing in the boot output. Intentional.

## Branch topology
main is the integration branch. Feature sessions happen in worktrees on branches like `claude/silly-cori`.
These branches diverge from main and are merged back. The `git diff main...branch` three-dot syntax shows
only what's on the branch and not in main.

## CLAUDE.md header line
The `# CLAUDE.md — unmassk-toolkit` title line may be present or absent — the managed block is what matters.
Its presence/absence is not a bug.
