---
description: Deliver every working rule into your context
allowed-tools: Bash(gitmem:*)
disable-model-invocation: true
---

Run `gitmem rule` and read the **entire** output.

Those lines are the user's standing instructions for how you work on this
project. From this point in the session they are binding, exactly as if the
user had just typed each one. They outrank any habit, any default and any
document.

Then tell the user, in their language, how many rules are now loaded and — one
short line each — which ones change what you were about to do. Do not paste the
list back verbatim: they wrote it, they know it. If a rule contradicts
something you already said or did earlier in this session, say so in one line
and correct course.

## Guardrails

- **This command only reads.** It never saves a rule and takes no arguments.
  Saving is yours: when the user tells you how they want to be worked with,
  you run `gitmem rule "<what they said>"` there and then, in the conversation.
  Waiting for them to type a command to save their own correction is how the
  correction gets lost.
- The rules file is **outside** the note system: no zones, never through the
  zone customs, never in any search or report, never read by an agent. Do not
  save a rule as a note, and do not save a note as a rule.
- **Never hand-edit `rules.md`.** The script writes it. If the file and git
  disagree, git wins.
- If `gitmem` is not found, say exactly that — the command could not be run —
  and offer to install the toolkit in this project. **Never report "there are
  no rules"** when what happened is that you could not ask. Those are opposite
  claims.
- If `gitmem` runs and returns an empty list, that is a real answer: this
  project has no rules yet. Say so.
