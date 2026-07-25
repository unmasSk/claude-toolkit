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
   - **A discard is not done while its front still has live memos/`Next:`.** When the session *decides against* a candidate (a "don't build X" decision), tombstone the memos and resolve the `Next:` entries of that same front in the same close — otherwise they resurface at the next boot and lead a future session to re-offer something already decided. Before proposing to resume any candidate, cross-check it against the DECISIONS, not just against Next/memos.

3. **Write the resume point.** A short handoff so the next session knows where it stopped: what's done, what's in progress, what's next, which skills the next session should use.

4. **Don't duplicate.** Reference decisions/commits/issues by their git reference instead of re-summarizing their content. The handoff points; it doesn't copy.

## Project housekeeping (adaptive — only what the project actually has)

Before the resume point, inspect the project and run what applies. Adaptive: check, don't assume.

5. **Versioning** — if the project has a version (`plugin.json`/`package.json`/etc.) and the session shipped changes worth a release → run the version bump. For THIS toolkit marketplace, the release is one command: `python3 bin/release.py <plugin> <new-version>` (dry-run first) — it bumps, promotes the changelog, commits, pushes, and verifies. See the `unmassk-gitmemory` skill's "Releases" section. No versioning → skip. **The release is part of finishing, not an optional follow-up:** when the session's work justifies a release, run it now as part of the close — don't defer it or ask permission to publish.
6. **Changelog** — if there's a `CHANGELOG` → hand to **Alexandria** to update the `[Unreleased]` section. Do this BEFORE the release command (it aborts on an empty `[Unreleased]`). No changelog → skip.
7. **Cleanup** — remove temporary/scratch files the session created (drafts, tmp, scratch). Never touch real source.
8. **Tracker & branch hygiene** — inspect what the session actually finished. This step deletes branches and closes issues: both are outward-facing and hard to undo, so it is **fail-safe by default** — act only on what you can *mechanically verify* as done/merged; on any doubt, do nothing and record it in the resume point instead of deleting or closing. Before any destructive or outward-facing action (remote branch delete, issue close), list exactly what will be closed/deleted and get the user's confirmation — never batch-delete or bulk-close silently. (a) If the work completed one or more GitHub issues that are still open → after confirmation, close them (`gh issue close <n>` with a one-line reason). (b) If the work lived on a branch that is now merged and no longer needed → after confirmation, delete it, local **and** remote (`git branch -d <b>`; `git push origin --delete <b>`). Adaptive and **repo_type-aware**: a **trunk** repo works on `main` — usually there's no branch to delete; a **gitflow** repo deletes the merged `feat/*`/`fix/*` branch after the merge. Never delete an unmerged branch or one with open work, and never close an issue whose work isn't actually done. Nothing closed/merged this session → skip.
   - **(c) Reconcile the WHOLE open backlog, not just this session's work.** The recurring leak is issues resolved in a *previous* session that were never closed: a fix commit references `#N` but no `Resolved-Next:` trailer fired (the work didn't come from a `Next:`), so GitHub stayed open and the tracker drifts out of sync with reality. At close, list every open issue (`gh issue list --state open`) and cross-reference each number against the commit history (`git log --all --grep="#<n>"`) and git-memory. Any open issue with a commit that *demonstrably* resolves it → surface it with the evidence commit and, after confirmation, close it citing that commit (`gh issue close <n> --comment "Resuelto: <fix> (<hash>)"`). Same fail-safe rules as (a): evidence-or-nothing, list don't bulk-close, confirm first, and on any doubt leave it open and note it in the resume point. This sweep is what stops the backlog from silently accumulating done-but-open issues across sessions.
   - **Remote delete has no merge guard.** Only run the remote delete once the local `git branch -d` succeeded (that's what confirms the branch is merged). If the platform already removed the remote branch (GitHub "auto-delete head branches" after a PR merge), treat the failing remote delete as success, not an error — just drop the stale local ref. Never fall back to `-D` to force a local delete that `-d` refused.
   - **Gitflow hotfix isn't done at `main`.** A hotfix merged to `main` but not yet back-merged to `dev` still satisfies "merged", but deleting it there loses the only signal that the back-merge is missing (the bug returns next time `dev` promotes). In gitflow, confirm the back-merge to `dev` before deleting a hotfix branch — a merge to `main` alone is not "finished".
9. **Three-audience doc check** — for anything new the session shipped (feature, script, flag, convention), confirm it is documented for ALL three audiences (humans → `README`/`docs`, us → roadmap/git-memory, Claude → `SKILL.md`/`CLAUDE.md`). See `unmassk-core` "Documentation discipline". A capability documented in only one surface is unfinished — hand the sync to **Alexandria**.

## Output

The resume point and the flushed decisions all live in **git-memory** (commits), not in a file. The next session's boot reads them back.

## Boundary

- Persistence → git-memory only. No `handoff-*.md`, no CONTEXT.md.
- This skill writes memory and nothing else. Never touches code.
