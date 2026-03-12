# Design: Alexandria Changelog Automation

## Problem

After merging a feature branch to dev, there's no automatic changelog update. The information exists in commit trailers (Why:, Touched:) but nobody synthesizes it into CHANGELOG.md.

## Solution

A PostToolUse hook detects merges to dev, generates changelog data from trailers, and instructs Claude to launch Alexandria — who updates CHANGELOG.md and checks CLAUDE.md freshness.

## Components

### 1. `bin/git-memory-changelog.py` (new script)

**Input**: merge commit range (auto-detected or explicit)

**Process**:
- Read commits from the merged branch (`git log dev..MERGE_HEAD` or merge range)
- Filter OUT: wip, context, decision, memo, remember commits
- Filter OUT: agent infrastructure scopes (agents, agent-memory)
- Group remaining by type: feat→Added, fix→Fixed, refactor/perf→Changed, docs→Changed, chore/ci→skip unless notable
- Extract `Why:` trailer as description (fallback: commit subject)
- Extract `Touched:` trailers → deduplicate into affected folders list

**Output**: markdown block + affected folders list. If no actionable commits → output "NO_ACTIONABLE_CHANGES" and exit 0.

**Idempotency**: include commit SHAs in output so Alexandria can check if already present in CHANGELOG.

### 2. PostToolUse hook addition (in `post-validate-commit-trailers.py`)

**Trigger**: detects `git merge` command where target branch is `dev`.

**Action**:
1. Execute `git-memory-changelog.py`
2. If output is "NO_ACTIONABLE_CHANGES" → print nothing, exit 0
3. Otherwise → print `[alexandria-trigger]` message with:
   - Changelog markdown block
   - Affected folders list
   - Merge source/target branch names
   - Instruction: "Launch alexandria agent in background with this data"

### 3. `agents/alexandria.md` (new plugin agent)

**Identity**: Documentation agent. Keeps CHANGELOG.md and CLAUDE.md synchronized with codebase reality.

**On trigger** (receives `[alexandria-trigger]` data):
1. Open CHANGELOG.md (create with Keep a Changelog template if missing)
2. Check idempotency: search for commit SHAs already present → skip duplicates
3. Insert new entries under `[Unreleased]` in correct sections
4. Check CLAUDE.md freshness for affected folders (staleness detection via git log)
5. Commit with wrapper: `docs(changelog): update from merge <branch> → dev`

**Format**: Keep a Changelog 1.1.0 strict. Entries are human-readable descriptions, not raw commit messages.

**Autonomous responsibilities** (on every launch, not just triggers):
- CLAUDE.md staleness detection
- CHANGELOG freshness check
- Contradiction detection between root and folder CLAUDE.md files

### 4. Rule in git-memory skill

Add to Auto-Git Triggers table:
```
| Merge to dev detected | [alexandria-trigger] → launch Alexandria in background |
```

Add to Routing section:
```
- [alexandria-trigger] in hook output → launch alexandria agent with trigger data
```

## Flow

```
git merge feat/xxx → dev
       ↓
PostToolUse hook detects merge to dev
       ↓
Hook runs git-memory-changelog.py
       ↓
Script returns: changelog markdown + affected folders
(or NO_ACTIONABLE_CHANGES → stop here)
       ↓
Hook outputs [alexandria-trigger] message
       ↓
Claude reads output → launches Alexandria in background
       ↓
Alexandria:
  1. Opens CHANGELOG.md (creates if missing)
  2. Checks idempotency (SHA dedup)
  3. Inserts under [Unreleased]
  4. Checks CLAUDE.md of affected folders
  5. Commits: docs(changelog): update from merge feat/xxx → dev
```

## Filters

### Commit type filter
| Include | Exclude |
|---------|---------|
| feat, fix, refactor, perf, docs | wip, context, decision, memo, remember |
| chore (only if notable) | chore (routine) |

### Scope filter
| Include | Exclude |
|---------|---------|
| All domain scopes | agents, agent-memory |

### Fallback
If after filtering there are zero actionable commits → no trigger, no Alexandria launch, no empty changelog block.

## Idempotency

The changelog script includes short SHAs in a comment or metadata per entry. Alexandria checks existing CHANGELOG.md for those SHAs before inserting. If all SHAs already present → skip silently.

## Decisions

- Only merges to `dev` trigger the hook — staging/main are ceremonial
- Alexandria commits the CHANGELOG herself with wrapper script
- Separate commit after merge, never amend
- `Why:` trailer as entry description, subject as fallback
- Keep a Changelog 1.1.0 format strict
- Agent/infrastructure commits filtered from changelog
- No action on empty results (fallback silencioso)
