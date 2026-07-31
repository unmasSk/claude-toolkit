---
name: generated-doc-blocks
description: How the toolkit generates documentation from code truth — hooks_doc.py's marker-block pattern, why managed_blocks.upsert is NOT reused, and the two traps (escaped pipes, .py names in prose)
metadata:
  type: project
---

## The pattern: derived facts in a marker block, judgment in prose beside it

`unmassk-toolkit/lib/hooks_doc.py` generates the "Active Hooks" table of
`skills/unmassk-gitmemory/SKILL.md` from `hooks/hooks.json` + the files on
disk. Writer: `bin/hooks_doc_sync.py` (`--write` regenerates, no flag
verifies, exit 1 on drift). Reader: `bin/git-memory-doctor.py`'s "Hooks doc"
check, via `compare_hooks_doc()`.

The split that makes it work, and that should be copied for any other
generated doc section: **only what is mechanically derivable goes inside the
markers** (event, matcher, timeout, file presence). Everything that is human
judgment — "this hook is known-dead", "this one will get in your way" — stays
hand-written *below* the block. Both live in the same section so a reader sees
them together; neither can overwrite the other.

Severity contract of the doctor check (asymmetric on purpose):

- doc names a hook `hooks.json` no longer declares → **error** (exit 1). This
  is the direction that makes Claude assert a falsehood to the user every
  session.
- declared hook missing from the doc → **warn**. Under-informing, not
  misinforming; also the normal transient state right after adding a hook.
- same hooks, drifted event/matcher/timeout → **warn**.
- `hooks.json` underivable or SKILL.md absent → **no line at all** (the Hooks
  / Skills checks already own those facts; two lines for one fact is noise).

## Why `managed_blocks.upsert_managed_blocks()` was NOT reused

It looks like the same problem and is not. Its `BLOCKS` are fixed literal
bodies for CLAUDE.md, and its one expensive behaviour — the orphaned-END
repair pinned by issue #63's T1 tests — is the *opposite* of what a generated
block wants. With a marker missing there is no reliable signal of where the
block ends, and the hand-written prose sits immediately below it: guessing a
boundary would eat it. `hooks_doc.replace_block()` therefore **refuses**
(returns None) unless exactly one well-ordered BEGIN/END pair exists, and the
caller reports the refusal. Reuse the *pattern* (marker pair + idempotent
replace); do not generalise `upsert_managed_blocks` — it is imported by
`session-start-crew.py` on the boot path and by `install_apply.py`.

## Two traps when parsing your own generated markdown table

1. **`line.split("|")` is wrong.** A cell can legally carry an escaped pipe —
   the real matcher `Write|Edit` renders as `Write\|Edit` — and splitting on
   it shifts every later column, so the hook filename silently disappears from
   that row. Found live: `validate-memory-path.py` was reported "not
   documented" while sitting in the table. Split with `(?<!\\)\|`.
2. **Never scan the whole block for `*.py`.** The block's own prose names
   `bin/hooks_doc_sync.py`; a naive scan reports it as a documented hook and
   then as a phantom one. Read the hook name only from the table rows' hook
   column.

## Verifying a drift check actually bites

Mutate the real `hooks.json` / `SKILL.md`, run the real doctor, restore in a
`finally`, then assert the restored bytes are identical to the originals —
`tests/`-free, ~90 lines of throwaway script, and it exercises the same call
path the health report uses. Six scenarios worth running: hook removed from
hooks.json, invented row added to the doc, new hook declared but undocumented,
timeout drift, block deleted, hooks.json corrupt (must stay silent).
[[unmassk-toolkit-python-entrypoints]]
