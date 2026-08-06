---
description: Deliver every working rule, or save a new one
argument-hint: [the new rule — or nothing, to read them all]
allowed-tools: Bash(gitmem:*)
disable-model-invocation: true
---

The user invoked `/remember`. Arguments given: `$ARGUMENTS`

## If there are NO arguments — deliver the rules

Run `gitmem rule` (no arguments) and read the **entire** output.

Those lines are the user's standing instructions for how you work on this
project. Treat them as binding from this point in the session, exactly as if
the user had just typed each one. They outrank any habit, any default and any
document.

Then tell the user, in their language, how many rules are now loaded and — in
one short line each — which ones change what you were about to do. Do not
paste the list back verbatim: they wrote it, they know it. If a rule
contradicts something you already said or did earlier in this session, say so
in one line and correct course.

## If there ARE arguments — save a new rule

Run:

```
gitmem rule "$ARGUMENTS"
```

Add `--kind claude` only when the rule is about your own internal behaviour
rather than about how the user wants to be worked with.

Then confirm in one line what was saved, and apply it immediately.

## Guardrails

- The rules file is **outside** the note system: it carries no zones, never
  passes the zone customs, never appears in any search or report, and no agent
  reads it. Do not save a rule as a note, and do not save a note as a rule.
- **Never hand-edit `rules.md`.** The script writes it. If the file and git
  disagree, git wins.
- If `gitmem` is not found, say exactly that — the command could not be run —
  and offer to install the toolkit in this project. **Never report "there are
  no rules"** when what actually happened is that you could not ask. Those are
  opposite claims.
- If `gitmem` runs but returns an empty list, that is a real answer: this
  project has no rules yet. Say so, and offer to save the first one.
