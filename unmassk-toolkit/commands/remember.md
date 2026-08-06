---
description: Deliver this project's working rules, whole, and flag any divergence
allowed-tools: Read, Bash(git log:*)
disable-model-invocation: true
---

Read `.claude/project-memory/rules.md` — this project's rules file — and
deliver it **entire**. Not a summary, not a selection: every line. The path is
project-relative on purpose, so one project's rules are never shown in another.

Then cross-check it against git, because a rule lives in **two** places and is
only trustworthy when both agree:

```
git log --format=%s --grep='^\[remember\]'
```

Compare the two sides **in both directions** — a line in the file with no
commit behind it, and a rule commit whose line is missing from the file.

## What to put on screen

1. **Every rule, whole.** Print the list. The user wrote these, but they came
   to read them, so they get read out — abridging the delivery is the one thing
   this command must never do.
2. **The divergence, if there is any**, named line by line and on which side it
   is missing. A rule present in git but absent from the file is a rule that
   silently stopped applying; a line in the file with no commit behind it never
   survived. Both are this project's actual threat model — the system losing
   its own memory with nothing on screen to say so.
3. **What changes right now.** One short line per rule that contradicts
   something you already said or did earlier in this session, and the correction
   you are making because of it.

From this point in the session every rule is binding, exactly as if the user
had just typed it. They outrank any habit, any default and any document.

## Guardrails

- **This command only reads.** It takes no arguments and never saves. Saving is
  yours: when the user says how they want to be worked with, you run
  `gitmem rule "<what they said>"` there and then, in the conversation. A user
  who must invoke a command to store their own correction is a user whose
  correction gets lost.
- **Never hand-edit `rules.md`.** The script writes it, file first and commit
  second. If the two disagree, git is the one that survived.
- Rules sit **outside** the note system: no zones, never through the zone
  customs, never in a search or a report, never read by an agent. Do not save a
  rule as a note, or a note as a rule.
- If the file does not exist, say the toolkit is not installed in this project
  and offer to install it. **Never report "there are no rules"** when what
  happened is that you could not look. Those are opposite claims.
- A file that exists and is empty is a real answer: this project has no rules
  yet. Say that.
