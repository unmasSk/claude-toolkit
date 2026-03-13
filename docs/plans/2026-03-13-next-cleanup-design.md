# Next Cleanup — Design Doc

**Date:** 2026-03-13
**Decision:** fa7481e

## Problem

Next: trailers accumulate in boot output forever. The Resolved-Next tombstone mechanism exists but nothing triggers it automatically. Boot shows stale Next items from sessions ago that are already completed.

## Design

### Component 1: Issue status check

For each Next item with `#N` reference, check if the GitHub issue is still open.

**Where:** `extract_memory()` in `hooks/session-start-boot.py`, post-scan phase.

**Flow:**
1. During commit scan, collect Next items as before
2. After scan, partition into: has_issue vs no_issue
3. For has_issue items, launch parallel `gh issue view #N --json state,title` calls via `subprocess.Popen`
4. Collect results with 5s global timeout
5. If issue CLOSED → skip the Next item
6. If issue OPEN → show normally
7. If gh unavailable or timeout → show the Next (degrade silently, never lose info)

**Cross-repo issue guard (Ataque 5):**
- Parse the issue title from gh response
- Compare keywords (3+ chars) between Next text and issue title
- If < 2 keyword overlap → treat as unrelated issue, show the Next anyway
- This prevents `Next: fix upstream bug #42` from being killed by an unrelated local issue #42

**Parallelization:**
- Launch all `gh issue view` as Popen processes simultaneously
- `poll()` in a loop with 5s total timeout
- Kill any remaining processes after timeout

### Component 2: Stale marker for Next without issue

Next items without `#N` have no external source of truth. Instead of discarding them, mark them as stale after a TTL so the user can decide.

**Where:** Same `extract_memory()` function, using commit timestamp.

**Flow:**
1. For Next items without `#N`, parse the commit date
2. If commit is > 7 days old → prefix with `[stale]` in the boot output
3. Still show the item — never discard automatically
4. User sees `[stale]` and can either: create an issue for it, resolve it, or ignore it

### Boot output examples

```
RESUME:
  Last: abc1234 context(plugin): session checkpoint | 2h ago
  Next: fa7481e: (plugin/boot) implement rate limiting #42
  Next: 1234abc: (plugin/hooks) [stale] add retry logic for webhook failures
  Blocker: waiting for API credentials from infra team
```

## What this does NOT do

- Does not auto-create Resolved-Next tombstones (that's a separate concern)
- Does not run GC (the GC script remains manual/optional)
- Does not change how Next items are created or how issues are linked

## Files to modify

- `hooks/session-start-boot.py` — `extract_memory()` + display logic

## Risks

- **Latency:** 5s timeout worst case, but gh calls typically complete in <1s. Parallel execution keeps it fast.
- **gh availability:** Degrades silently. No gh = no filtering = same behavior as today.
- **False negatives on cross-repo:** Keyword matching is imperfect but errs on the safe side (show, don't hide).
