# Plugin Audit & Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clean the plugin structure so it follows the official Claude Code plugin spec, merge unused skills, and fix the stale cache so all fixes actually run.

**Architecture:** The plugin source repo IS the plugin root. `${CLAUDE_PLUGIN_ROOT}` resolves to the cache copy at `~/.claude/plugins/cache/...`. Only CLAUDE.md and .claude/git-memory-manifest.json touch client projects. Skills merge from 4→2. Cache refresh via delete+reinstall.

**Tech Stack:** Python 3, Claude Code plugin system, git

---

## Pre-flight: Current State

```
Repo structure (CURRENT):
├── .claude-plugin/plugin.json    ✅ Correct
├── hooks/hooks.json + 7 scripts  ✅ Correct
├── skills/ (4 dirs with SKILL.md) ⚠️ 2 unused, merge needed
├── agents/gitto.md               ✅ Correct
├── bin/ (8 scripts)              ✅ Correct
├── lib/ (4 modules)              ✅ Correct
├── .claude/hooks/ (6 scripts)    ❌ DUPLICATE — delete
├── .claude/skills/ (4 dirs)      ❌ DUPLICATE — delete
└── Cache: v2.0.0                 ❌ STALE — 15 commits behind
```

```
Target structure (AFTER):
├── .claude-plugin/plugin.json    (version bumped to 3.0.0)
├── hooks/hooks.json + 6 scripts  (context-writer.py moved to bin/)
├── skills/
│   ├── git-memory/SKILL.md       (core + protocol + recovery merged)
│   └── git-memory-lifecycle/SKILL.md
├── agents/gitto.md
├── bin/ (8 scripts + context-writer.py)
├── lib/ (4 modules)
└── Cache: v3.0.0                 (fresh, all fixes active)
```

---

### Task 1: Delete duplicate .claude/hooks/ and .claude/skills/

These are leftovers from the old install model. The real hooks live at `hooks/` and skills at `skills/`. The `.claude/` versions are tracked despite `.claude/` being in `.gitignore` (force-added previously).

**Files:**
- Delete: `.claude/hooks/` (entire directory — 6 .py files)
- Delete: `.claude/skills/` (entire directory — 4 subdirs with SKILL.md)
- Keep: `.claude/settings.json`, `.claude/settings.local.json`, `.claude/git-memory-manifest.json`

**Step 1: Verify the duplicates match the originals**

```bash
# Should show no meaningful differences (or just path differences)
diff -rq hooks/ .claude/hooks/ --exclude='*.json' --exclude='context-writer.py'
diff -rq skills/ .claude/skills/
```

If they differ: the `hooks/` and `skills/` versions are canonical. `.claude/` copies are stale.

**Step 2: Delete the duplicates**

```bash
rm -rf .claude/hooks/ .claude/skills/
```

**Step 3: Also clean other .claude/ cruft**

```bash
# These are runtime files that shouldn't be in the repo
rm -f .claude/dashboard.html .claude/.context-status.json .claude/.message-counter .claude/launch.json
```

**Step 4: Verify**

```bash
ls .claude/
# Expected: settings.json, settings.local.json, git-memory-manifest.json only
```

**Step 5: Commit**

```bash
git add -f .claude/hooks/ .claude/skills/ .claude/dashboard.html .claude/.context-status.json .claude/.message-counter .claude/launch.json
git commit -m "🔧 chore(cleanup): remove duplicate .claude/hooks/ and .claude/skills/

Old-style install artifacts that duplicated hooks/ and skills/ at the
plugin root. The canonical versions live at the root, not in .claude/.

Why: .claude/ duplicates caused confusion and are not part of the plugin spec
Touched: .claude/hooks/, .claude/skills/, .claude/dashboard.html, .claude/.context-status.json"
```

---

### Task 2: Merge skills 4→2

Protocol (69 lines) and recovery (79 lines) have NEVER been used as standalone skills. Their content is reference material that Claude should know whenever it loads the core skill.

**Files:**
- Modify: `skills/git-memory/SKILL.md` — append protocol + recovery sections
- Delete: `skills/git-memory-protocol/` (entire directory)
- Delete: `skills/git-memory-recovery/` (entire directory)
- Modify: `skills/git-memory/SKILL.md` — remove "Routing" section at the bottom (lines 148-152)
- Modify: `.claude-plugin/plugin.json` — no change needed (auto-discovers `skills/`)

**Step 1: Read current content of all three skills to merge**

Read `skills/git-memory/SKILL.md`, `skills/git-memory-protocol/SKILL.md`, `skills/git-memory-recovery/SKILL.md`.

**Step 2: Edit core skill — append protocol content**

Add to `skills/git-memory/SKILL.md` after the "Memory Search" section, REPLACING the "Routing" section:

```markdown
## Protocol

### Authority Hierarchy

1. User instruction in conversation (highest)
2. Confirmed memory (decisions/memos with commit)
3. CLAUDE.md of the project
4. Other context files (.cursorrules, docs)
5. Code inferences (lowest)

If conflict between sources: acknowledge openly, defer to most recent user confirmation.

### Noise Levels

| Level | When | Action |
|-------|------|--------|
| **silent** | All OK | Zero output |
| **inline** | Warning, not blocking | Mention only if asked |
| **interrupt** | Capacity loss | Warn before working |

### Releases

- PR mandatory: `dev → staging`. Production: `staging → main` with release protocol.
- No `Next:` on main commits. `Risk:` always required on hotfixes.
- Hotfix flow: branch from main → fix → PR to main → back-merge to dev.

### Conflict Resolution

- Default: merge, not rebase. If conflict: **stop**, don't improvise.
- Resolution commits: `Conflict:` + `Resolution:` + `Why:` + `Touched:` + `Risk:`
- Force push to `main`: **FORBIDDEN**.
- Force push to `staging`: only with explicit approval + `Risk: high`.

### Undo Operations

| Operation | Risk | Confirm? |
|-----------|------|----------|
| `reset --soft HEAD~1` | low | No |
| `stash push/pop` | low | No |
| `revert <sha>` | low | No |
| `amend` (before push) | low | No |
| `amend` (after push) | **high** | YES |
| `reset --hard` | **high** | YES |
| `push --force-with-lease` | **high** | YES — feature branches only |
| `push --force` main/staging | **FORBIDDEN** | N/A |

## Recovery

### Self-Healing

On boot, compare known commit hashes with current tree.
If amnesia detected (memory commits missing): rebuild conservatively, be honest about gaps.

### Force Push / History Rewrite

- Detect history rewrite (known SHAs missing from tree)
- Don't assume "most recent = best"
- Conservative resolution — never invent missing context

### Contradiction Detection

Before creating a new decision/memo, search existing:
1. `git log --all --grep="Decision:" | grep -i "<topic>"`
2. `git log --all --grep="Memo:" | grep -i "<topic>"`
- Memo vs new Decision using that thing → warn
- Decision vs new Decision (same scope) → warn
- If confirmed → create. Most recent always wins.

### CI Rejects Trailers

Check compatibility BEFORE activating writes. If commitlint active → compatible mode.

### Emergency: Lost Commits

```bash
git reflog                    # find SHA before the reset
git reset --hard <sha>        # recover (reflog keeps ~30 days)
```

Document recovery with `Risk: high` + `Why:` trailers.
```

**Step 3: Remove the routing section from the merged skill**

Delete lines 148-152 (the "## Routing" section) since the content is now inline.

**Step 4: Delete the standalone skills**

```bash
rm -rf skills/git-memory-protocol/ skills/git-memory-recovery/
```

**Step 5: Update the lifecycle skill description**

No changes needed to `skills/git-memory-lifecycle/SKILL.md` — it's self-contained.

**Step 6: Verify skill structure**

```bash
ls skills/*/SKILL.md
# Expected: skills/git-memory/SKILL.md, skills/git-memory-lifecycle/SKILL.md
```

**Step 7: Update doctor script**

Read `bin/git-memory-doctor.py` and update the expected skill count from 4 to 2 if it checks skill count.

**Step 8: Commit**

```bash
git add skills/ bin/git-memory-doctor.py
git commit -m "♻️ refactor(skills): merge protocol + recovery into core skill

Protocol and recovery skills were never used standalone. Their content
is reference material Claude needs whenever git-memory loads. Merging
reduces from 4 skills to 2 (core + lifecycle) without losing any content.

Why: 2 of 4 skills never triggered — dead weight in skill list, confusing for users
Touched: skills/git-memory/SKILL.md, skills/git-memory-protocol/, skills/git-memory-recovery/, bin/git-memory-doctor.py"
```

---

### Task 3: Move context-writer.py out of hooks/

`context-writer.py` is NOT a hook — it's a utility script that wraps the statusline. It doesn't belong in `hooks/`.

**Files:**
- Move: `hooks/context-writer.py` → `bin/context-writer.py`
- Modify: `bin/git-memory-install.py` — update the path reference to context-writer.py

**Step 1: Move the file**

```bash
mv hooks/context-writer.py bin/context-writer.py
```

**Step 2: Update install script reference**

In `bin/git-memory-install.py`, find the line that references `hooks/context-writer.py` and change to `bin/context-writer.py`:

```python
# Line ~517: wrapper_script = os.path.join(source, "hooks", "context-writer.py")
# Change to:
wrapper_script = os.path.join(source, "bin", "context-writer.py")
```

**Step 3: Verify no other references**

```bash
grep -r "context-writer" --include="*.py" --include="*.json" --include="*.md" .
```

Update any other references found.

**Step 4: Commit**

```bash
git add hooks/context-writer.py bin/context-writer.py bin/git-memory-install.py
git commit -m "🔧 chore: move context-writer.py from hooks/ to bin/

context-writer.py is a statusline utility, not a hook. It doesn't belong
in the hooks/ directory alongside actual hook scripts.

Why: hooks/ should only contain hook scripts referenced by hooks.json
Touched: hooks/context-writer.py, bin/context-writer.py, bin/git-memory-install.py"
```

---

### Task 4: Version bump to 3.0.0

Breaking change (skills reduced from 4→2), warrants major version bump.

**Files:**
- Modify: `.claude-plugin/plugin.json` — version "3.0.0"
- Modify: `bin/git-memory-install.py` — VERSION constant

**Step 1: Update plugin.json**

```json
{
  "name": "claude-git-memory",
  "version": "3.0.0",
  ...
}
```

**Step 2: Update install script VERSION**

In `bin/git-memory-install.py` line 38:
```python
VERSION = "3.0.0"
```

**Step 3: Commit**

```bash
git add .claude-plugin/plugin.json bin/git-memory-install.py
git commit -m "🔖 release: bump version to 3.0.0 — skills consolidation + cleanup

Breaking: skills reduced from 4 to 2 (protocol+recovery merged into core).
Duplicate .claude/ artifacts removed. context-writer moved to bin/.

Why: major restructure — skills count changed, directory layout cleaned
Touched: .claude-plugin/plugin.json, bin/git-memory-install.py"
```

---

### Task 5: Force refresh the plugin cache

The cache at `~/.claude/plugins/cache/unmassk-claude-git-memory/claude-git-memory/2.0.0/` is stale. It must be replaced with the current repo state.

**Step 1: Push changes to main**

```bash
git push origin main
```

**Step 2: Delete stale cache**

```bash
rm -rf ~/.claude/plugins/cache/unmassk-claude-git-memory/
```

**Step 3: Reinstall plugin**

The user must run `/plugin install` from Claude Code to re-fetch from GitHub and populate the cache with v3.0.0.

Alternatively, if Claude Code supports it:
```
/plugin update claude-git-memory
```

**Step 4: Verify new cache**

```bash
ls ~/.claude/plugins/cache/unmassk-claude-git-memory/
# Expected: claude-git-memory/3.0.0/ (or similar structure)
cat ~/.claude/plugins/cache/unmassk-claude-git-memory/claude-git-memory/*/. claude-plugin/plugin.json
# Expected: version "3.0.0"
```

**Step 5: Verify hooks.json in cache**

```bash
cat ~/.claude/plugins/cache/unmassk-claude-git-memory/claude-git-memory/*/hooks/hooks.json | python3 -m json.tool
```

**Step 6: Verify skills in cache**

```bash
ls ~/.claude/plugins/cache/unmassk-claude-git-memory/claude-git-memory/*/skills/
# Expected: git-memory/, git-memory-lifecycle/ (only 2)
```

---

### Task 6: End-to-end verification

**Step 1: Start a new Claude Code session in this repo**

After cache refresh, start a fresh session and verify:
- [ ] SessionStart hook fires
- [ ] UserPromptSubmit hook fires (boot reminder)
- [ ] Skills `git-memory` and `git-memory-lifecycle` load via Skill tool
- [ ] Stop hook does NOT block (exit 0, auto-wip message)
- [ ] Doctor reports 2/2 skills (not 4/4)

**Step 2: Verify stop hook is non-blocking**

Make a trivial change, then let Claude stop. The stop hook should print an auto-wip instruction, NOT block with exit code 2.

**Step 3: Verify in a DIFFERENT repo**

Install the plugin in a separate test repo and verify:
- [ ] Only CLAUDE.md and .claude/git-memory-manifest.json created
- [ ] No bin/, hooks/, skills/, lib/ at project root
- [ ] Doctor runs successfully
- [ ] Skills load

---

## Execution Order

| Task | Depends on | Risk |
|------|-----------|------|
| 1. Delete duplicates | None | Low — removing unused copies |
| 2. Merge skills | None | Medium — content merge, must preserve all info |
| 3. Move context-writer | None | Low — path update in 1 file |
| 4. Version bump | Tasks 1-3 | Low |
| 5. Cache refresh | Task 4 + push | Medium — requires plugin reinstall |
| 6. E2E verification | Task 5 | None — read-only |

Tasks 1, 2, 3 are independent and can run in parallel.
