<![CDATA[<p align="center">
  <img src="claude_git_memory_logo_concept_2_1772753619440.png" alt="claude-git-memory" width="180">
</p>

<h1 align="center">claude-git-memory</h1>

<p align="center">
  Cross-machine persistent memory system for <a href="https://docs.anthropic.com/en/docs/claude-code">Claude Code</a>.<br>
  Uses git commits as the single source of truth — no external docs, no extra files.<br>
  Everything lives in the commit history.
</p>

---

## The problem

Every time Claude starts a new session, it forgets everything. Who decided to use dayjs? Why did we reject raw SQL? What was the user's preference for arrow functions? Lost. You end up repeating yourself, re-explaining decisions, and watching Claude reinvent wheels.

## The solution

**Git = Memory.** Every commit carries structured trailers (`Why:`, `Decision:`, `Memo:`, `Next:`, `Blocker:`) that Claude reads on session start. Switch machines, close the terminal, compress context — the memory survives because it's in git.

```
✨ feat(forms): add date range validation

Issue: CU-042
Why: users submit impossible date ranges crashing the report engine
Touched: src/forms/DateFilter.vue, tests/forms/dateFilter.test.ts
Decision: use dayjs over moment — moment is deprecated and 10x heavier
Next: wire validation into the API layer
```

## How it works

```
┌─────────────────────────────────────────────────────────────┐
│                     Claude Session Start                     │
│                                                             │
│  AUTO-BOOT: git log -n 30 → extract trailers → show resume │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Branch: feat/CU-042-filters                           │ │
│  │ Last session: "pause forms refactor" (2h ago)         │ │
│  │ Pending: wire validation into API layer               │ │
│  │ Decision: (forms) use dayjs over moment               │ │
│  │ Memo: (api) never use sync fs operations              │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  Claude knows exactly where you left off. No questions.     │
└─────────────────────────────────────────────────────────────┘
```

### Four hooks protect the system

| Hook | Event | What it does |
|------|-------|-------------|
| **Belt** (pre-validate) | `PreToolUse` | Blocks `git commit` if required trailers are missing |
| **Suspenders** (post-validate) | `PostToolUse` | Safety net — if a bad commit slips through, resets it safely |
| **DoD** (stop-check) | `Stop` | Blocks session exit if uncommitted changes or pending work exist |
| **Hipocampo** (precompact) | `PreCompact` | Before context compression, saves critical memory as a compact snapshot |

Both validation hooks handle Git-native messages transparently:

- **`fixup!`, `squash!`, `amend!`** prefixes are stripped before parsing the commit type, so interactive rebase workflows work without friction.
- **Merge, Revert, Cherry-pick** commits are whitelisted as `internal` and skip trailer validation entirely.
- **Trailer values > 200 chars** are truncated with `...` in the snapshot to protect the line budget.
- **Shallow clones** are detected (`git rev-parse --is-shallow-repository`) and flagged with a warning in both the snapshot and `git memory boot`.

### Five commit types

| Emoji | Type | Purpose | Required trailers |
|-------|------|---------|-------------------|
| `✨🐛♻️⚡🔧👷🧪📝` | Code (`feat`, `fix`, `refactor`, etc.) | Regular development | `Why:` + `Touched:` + `Issue:` (if branch has one) |
| `🚧` | `wip` | Temporary checkpoint | None (feature branches only) |
| `💾` | `context()` | Session bookmark | `Why:` + `Next:` |
| `🧭` | `decision()` | Design/architecture decision | `Why:` + `Decision:` |
| `📌` | `memo()` | Soft knowledge | `Memo: category - description` |

### Eleven trailers

| Trailer | Format | When |
|---------|--------|------|
| `Issue:` | `CU-xxx` or `#xxx` | Auto-extracted from branch name |
| `Why:` | Free text (1 line) | Every non-wip commit |
| `Touched:` | `path1, path2` or `glob/* (N files)` | Code commits |
| `Decision:` | Free text | `decision()` commits |
| `Memo:` | `preference\|requirement\|antipattern - text` | `memo()` commits |
| `Next:` | Free text | Pending work |
| `Blocker:` | Free text | What blocks progress |
| `Risk:` | `low\|medium\|high` | Dangerous operations, hotfixes |
| `Conflict:` | Free text | Merge conflict resolutions |
| `Resolution:` | Free text | How conflict was resolved |
| `Refs:` | URLs, doc links | External references |

## Dashboard

A self-contained static HTML dashboard that visualizes the entire memory system at a glance. Built with GitHub Primer dark theme — no server, no dependencies.

```bash
git memory dashboard    # Generate + open in browser
```

The dashboard renders 7 sections from real git data:

| Section | What it shows |
|---------|---------------|
| **Status bar** | Pending, blockers, decisions, memos counts |
| **Blockers** | Active blockers with TTL progress bars |
| **Pending** | `Next:` items sorted by age |
| **Decisions** | Latest decision per scope |
| **Memos** | Latest memo per scope with category labels |
| **Health** | Compliance percentage + missing trailer breakdown |
| **GC Status** | Tombstone count, candidates, days since last GC |
| **Timeline** | Last 20 commits with type-colored badges |

**Auto-refresh**: The dashboard auto-reloads every 10 seconds. After every valid commit, the post-hook regenerates it in the background. Open it once and forget — it stays current.

**State preservation**: Search queries, scroll position, and collapsed sections persist across reloads via `localStorage`.

## Garbage Collector

Stale `Next:` and `Blocker:` items accumulate over time. The GC cleans them automatically using three heuristics:

| Heuristic | What it detects |
|-----------|----------------|
| **H1** (keyword overlap) | `Next:` items where subsequent commits in the same scope share ≥2 keywords |
| **H2** (TTL expiry) | `Blocker:` items older than N days with no recent mentions |
| **H3** (explicit resolution) | Items referenced by a `Resolution:` trailer |

```bash
git memory gc              # Interactive — shows candidates, asks before commit
git memory gc --dry-run    # Just show what would be cleaned
git memory gc --auto       # Auto-commit without asking
git memory gc --days 60    # Custom TTL for blockers (default 30)
```

The GC creates a compensation commit with tombstone trailers (`Resolved-Next:`, `Stale-Blocker:`) that suppress cleaned items from future snapshots and dashboard views. Fully reversible with `git revert`.

## Installation

### 1. Copy hooks and skills into your project

```bash
cp -r .claude/ /path/to/your-project/.claude/
cp CLAUDE.md /path/to/your-project/
```

### 2. Register hooks in Claude Code settings

Copy the contents of `settings-snippet.json` into your project's `.claude/settings.json` (or your user-level `~/.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/pre-validate-commit-trailers.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/post-validate-commit-trailers.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/stop-dod-check.py"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/precompact-snapshot.py"
          }
        ]
      }
    ]
  }
}
```

### 3. Install the CLI

```bash
# From your project root:
export PATH="$PWD/bin:$PATH"

# Now you can run:
git memory decisions
git memory search "dayjs"
git memory boot
git memory dashboard
git memory gc --dry-run
```

## CLI: `git memory`

A portable script (`bin/git-memory`) for querying memory without Claude:

```bash
git memory              # All memory trailers
git memory decisions    # Only Decision: entries
git memory memos        # Only Memo: entries
git memory pending      # Only Next: entries
git memory blockers     # Only Blocker: entries
git memory search term  # Search across decisions + memos + pending
git memory boot         # Compact boot summary
git memory dashboard    # Static HTML dashboard (opens in browser)
git memory gc           # Garbage collect stale items
```

## Project structure

```
.claude/
├── hooks/
│   ├── pre-validate-commit-trailers.py   # Belt — blocks bad commits
│   ├── post-validate-commit-trailers.py  # Suspenders — safety net + dashboard regen
│   ├── precompact-snapshot.py            # Saves memory before compression
│   └── stop-dod-check.py                # Blocks exit with pending work
└── skills/
    └── git-memory/
        ├── SKILL.md        # Router: AUTO-BOOT, search protocol, triggers
        ├── WORKFLOW.md     # Day-to-day: branches, commits, trailers
        ├── RELEASE.md      # Promotions: dev→staging→main, hotfixes
        ├── CONFLICTS.md    # Conflict resolution with audit trail
        └── UNDO.md         # Recovery with risk tagging
bin/
├── git-memory              # CLI query tool
├── git-memory-gc.py        # Garbage collector
└── git-memory-dashboard.py # Dashboard generator
dashboard-preview.html      # HTML template (GitHub Primer dark theme)
tests/
└── drift-test.py           # 6-month simulation (200 commits, 6 scopes)
CLAUDE.md                   # Entry point for Claude sessions
settings-snippet.json       # Hook registration config
```

## Snapshot budget

The PreCompact snapshot and AUTO-BOOT summary share a strict line budget to avoid consuming context window:

| Section | Max lines |
|---------|-----------|
| Header + Branch + Last context | 3 |
| Pending (Next:) + overflow | 4 |
| Blockers | 3 |
| Decisions (1 per scope) | 4 |
| Memos (1 per scope) | 3 |
| Footer | 1 |
| **Total worst case** | **18** |

## Memory search protocol

Before asking the user anything Claude could find in history:

1. `git fetch --all --prune` — ensure refs are fresh
2. `git log --all --grep="Decision:"` — search decisions
3. `git log --all --grep="Memo:"` — search memos
4. Check `CLAUDE.md` and `~/.claude/MEMORY.md` for global preferences
5. **Only if no match** — ask the user

### Contradiction detection

Before creating a new `decision()` or `memo()`, Claude searches for existing entries on the same scope/topic. If a contradiction is found, it warns the user before overriding.

## Conversational memory capture

Claude detects intent from natural language and creates commits automatically:

| User says | Claude does |
|-----------|-------------|
| "let's go with X" / "decidido X" | `decision()` commit |
| "always X" / "never Y" | `memo()` with `preference` |
| "the client wants X" | `memo()` with `requirement` |
| "don't ever use X" | `memo()` with `antipattern` |
| ambiguous | Asks: "register as decision or memo?" |

## Drift test

`tests/drift-test.py` generates 200 commits across 6 months and 6 scopes, then validates:

1. **Deep search** — finds all decisions/memos across the full history
2. **Dedup** — preserves entries from different scopes (doesn't collapse)
3. **Snapshot budget** — stays at 18 lines even under stress (all sections maxed)
4. **Truncation** — long trailer values (>200 chars) are truncated with `...`
5. **Hook robustness** — `fixup!`, `squash!`, `amend!`, Merge, Revert all pass validation correctly
6. **Post-hook exit_code safety** — failed commits (exit_code=1) don't trigger destructive resets
7. **Delimiter collision** — pipes in commit messages don't break the snapshot parser
8. **Nested prefixes** — `squash! fixup! feat:` and triple-nested variants parse correctly
9. **GC tombstones** — `Resolved-Next:` and `Stale-Blocker:` suppress items from snapshot

```bash
python3 tests/drift-test.py
```

## Adding new commit types

If you need a new type (e.g., `policy()`), follow the checklist in `SKILL.md > Forward Compatibility`:

1. Add emoji + type to WORKFLOW.md
2. Add to SKILL.md (AUTO-BOOT, triggers, routing)
3. Add to both validation hooks (VALID_KEYS, MEMORY_TYPES, validation block)
4. Add extraction + display to precompact-snapshot.py (respect budget)
5. Apply parsing hardening (emoji strip, dedup, overflow rule)
6. Add to drift test
7. Include in contradiction detection

## Requirements

- Python 3.10+
- Git
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) with hooks support

## License

MIT
]]>