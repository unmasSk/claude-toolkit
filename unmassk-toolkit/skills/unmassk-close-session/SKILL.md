---
name: unmassk-close-session
version: 2.1.0
description: Use when the user says "let's wrap up", "close the session", "we're done for today", "hand off", "save where we are", or otherwise signals that a working session is ending and wants it closed properly
---

# Close Session

Write down what this session knew before the window shuts. The commits are kept; the conversation is not.

> **Paths.** Every path below is relative to this skill's own directory — the absolute path printed as `Base directory for this skill:` when the skill loads. `${CLAUDE_PLUGIN_ROOT}` is empty in the Bash tool; never paste it into a command.

## When it runs

Only when the user asks. Not on compaction, not at the end of a turn, not because the session looks finished. Offer it in one line; do not start it.

## 1. Clean up

Scratch files, temporary files, caches, build leftovers, folders with no owner. State the result in one line: what was removed, or "nothing found" — a clean-up with no listed outcome did not happen.

Never touch source. For anything that looks orphaned, say what it is and why before removing it; if you cannot say, leave it.

## 2. Branches and issues

Write the answer into the conversation — step 4 sends an agent to read it.

- **The branch the work is on**, by name, and whether it is merged or still open.
- Issues opened, advanced or finished, by number.
- What merged, and what is waiting to.
- Anything still uncommitted, by name. It appears in no commit list and no boot.

Closing an issue or deleting a branch: act only on what you can mechanically verify as done or merged, show the exact list first, and wait for the user. Never bulk-close, never force a delete git refused. On doubt, leave it and write it down.

**The issue sweep is a fixed step of every close — never skipped, never merged into another.** Search the live notes and put in front of the user, one line each with the priority you would give it: every **Q or I saved with `--work no`** (did any mature into real work?), every note that passed with **`--issue none`** (does the refusal still stand?), and every **D that defers future building** without an issue behind it (the long-term checklist the customs cannot detect). Let the user decide each one. **You never open one on your own judgement — but with his yes, you create it (`gh issue create`) and link the note's work to it.** The protocol, the labels and the template are in the memory skill's `references/issues.md`.

## 3. Alexandria, in `close` mode

`subagent_type: unmassk-toolkit-alexandria`. Her profile holds the protocol; give her only what she cannot read from the repository — one line per thing the session shipped that is new or changed.

Expect back: what she corrected, where a document and the code contradict each other, and anything shipped with no home in the documentation. If the project has no documentation set she says so and stops — building one is her `foundation` mode, which the user asks for by name.

## 4. The close itself

**After Alexandria, never alongside her.** She commits; the close lists every commit of the session, and a list taken while she is still working is a list missing her work.

A `general-purpose` agent, handed the prompt at `references/close-agent-prompt.md` (relative to this skill's own directory) verbatim, with its placeholders resolved to absolute paths. It reads the session and writes one commit: the Next as the headline, the context as the body, and every commit since the last close underneath.

Then read the result out of git, not out of the agent's report: `git log -1` — the subject starts with `[NEXT]`, the body carries the prose, and it ends with the commit list. Each close replaces the previous one.

## Not part of a close

| | Where it belongs |
|---|---|
| Saving a decision the session never saved | When it was made |
| Registering work blocked on someone | When it stopped |
| Retiring a rule that stopped being true | When it stopped being true |
| Consolidating memory | Its own pass |
| Updating the CHANGELOG | Alexandria, in Flow's Document step — never the orchestrator, and never at close |
| A handoff document | The Next is the handoff |
| Releasing a version | The user's call, in the project's own instructions |

## Red flags

- Starting a close nobody asked for.
- Writing the close yourself instead of sending the agent.
- Sending the close agent while Alexandria is still running.
- A body that lists what was built instead of what was said.
- Deleting or closing something you cannot prove.
- Finishing without naming the branch.
