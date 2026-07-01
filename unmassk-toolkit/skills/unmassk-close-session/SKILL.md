---
name: unmassk-close-session
description: >
  Close a working session cleanly so nothing decided is lost and the next session
  can pick up where this one left off. Use when the user says "let's wrap up",
  "close the session", "we're done for today", "hand off", or when a session is
  ending. Also the natural anchor for end-of-session consolidation. Reach for this
  before ending any substantive session — an unsaved session is the failure this
  whole system exists to prevent.
---

# Close Session

Adapted from Matt Pocock's handoff (MIT). Persistence changed: the handoff goes to git-memory, not to a `handoff-*.md` file.

> Note: closing a session is **process that should always happen**. The reliable enforcement of it belongs to a hook on `Stop`/`PreCompact`, not to this voluntary skill. This skill is the *content* of the close; the hook is what guarantees it fires. Keep both.

## What the close does

1. **Flush uncommitted decisions.** Any decision/memo from this session not yet in git-memory → commit it now, with its Why. Live-write, immediately — a deferred commit is a lost commit.

2. **Run the curator** (when it exists) to consolidate: merge duplicates, promote maturity, resolve contradictions. Memory only, never code.

3. **Write the resume point.** A short handoff so the next session knows where it stopped: what's done, what's in progress, what's next, which skills the next session should use.

4. **Don't duplicate.** Reference decisions/commits/issues by their git reference instead of re-summarizing their content. The handoff points; it doesn't copy.

## Project housekeeping (adaptive — only what the project actually has)

Before the resume point, inspect the project and run what applies. Adaptive: check, don't assume.

5. **Versioning** — if the project has a version (`plugin.json`/`package.json`/etc.) and the session shipped changes worth a release → run the version bump. For THIS toolkit marketplace, the release is one command: `python3 bin/release.py <plugin> <new-version>` (dry-run first) — it bumps, promotes the changelog, commits, pushes, and verifies. See the `unmassk-gitmemory` skill's "Releases" section. No versioning → skip.
6. **Changelog** — if there's a `CHANGELOG` → hand to **Alexandria** to update the `[Unreleased]` section. Do this BEFORE the release command (it aborts on an empty `[Unreleased]`). No changelog → skip.
7. **Cleanup** — remove temporary/scratch files the session created (drafts, tmp, scratch). Never touch real source.
8. **Three-audience doc check** — for anything new the session shipped (feature, script, flag, convention), confirm it is documented for ALL three audiences (humans → `README`/`docs`, us → roadmap/git-memory, Claude → `SKILL.md`/`CLAUDE.md`). See `unmassk-core` "Documentation discipline". A capability documented in only one surface is unfinished — hand the sync to **Alexandria**.

## Output

The resume point and the flushed decisions all live in **git-memory** (commits), not in a file. The next session's boot reads them back.

## Boundary

- Persistence → git-memory only. No `handoff-*.md`, no CONTEXT.md.
- This skill writes memory and nothing else. Never touches code.
