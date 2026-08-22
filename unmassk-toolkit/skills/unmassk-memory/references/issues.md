# Issues — where the work goes

**Core principle:** memory holds what you know. Work is not something you know — it is something that has to happen, and it ends. Work lives in the project's tracker; memory only points at it.

This file governs that pointer: when a note earns an issue, who decides, what the issue says, and how it is labelled.

## The Iron Law

```
AN ISSUE IS A DECISION. YOU PROPOSE IT, THE USER OPENS IT
```

You never create an issue on your own judgement. You say in one line what the work is and what priority you would give it, and you wait. How long they take to answer is their business, not a cost for you to engineer around — never batch the question to some later ceremony to save them the interruption.

**But an error you can fix is not a decision.** If it falls inside what you are already touching, fix it. "I'll note it" and "it was already there" are not answers; they are how a defect survives.

## Static or work — the reading of every note

Most notes are facts. They are saved and nothing else happens. Only some ask for something to be done, and those are the ones that can carry an issue.

| Type | Static or work | What that means |
| ---- | -------------- | --------------- |
| **M** memo | Static, always | A fact that is simply true. If it asks for work, it is not a memo |
| **R** restriction | Static, always | A wall stops work; it does not create it |
| **X** discarded | Static, forever | The point of it is that nobody reopens it |
| **D** decision | Static, almost always | A decision is a decision. It carries an issue only when *building* it is a body of work — deciding to use a technology is not the same as implementing it |
| **Q** question | **Either** | Answerable by asking the user → static. Needs measuring, testing or investigating → that is work |
| **I** incident | **Work, unless already repaired** | Confirmed means something delivered is broken. If the repair is done, the scar is the whole record. If it is pending, that repair is work |
| **B** blocker | Work, but not yours | It waits on someone outside. It carries the issue of the work it is holding up, when there is one |

**Every type accepts an issue number.** The table says what is *usual*, not what is permitted — a decision that turns out to be a body of work carries one exactly like an incident does.

## The line: scope, not severity

The question is never "how bad is it". It is **where it is**:

```
Inside the file or the task you already have open   →  FIX IT NOW.
                                                       The note records that it was fixed.

Outside it: other code, another session, or it       →  PROPOSE AN ISSUE.
needs a decision from the user                          One line. Then wait.
```

That line can be applied without judgement, which is why it does not decay. Anything else — "it's small", "it's pre-existing", "it's not what we came for" — is the excuse that turns a defect into a permanent one.

## Opening one

```
1. Say what the work is, in one line, with the priority you would give it.
2. The user says yes. Not before.
3. Search first: an issue for this may already exist.
4. Create it from the template below.
5. The note carries the number.
```

**If the number arrives after the note was saved**, do not rewrite the note — a note is a commit and a commit does not change. The issue cites the note instead: the issue is editable, the commit is not.

## Labels

**Never invent the label set.** Read what the repository already uses first. If it has none, create the set below once, say that you did, and move on — creating labels is plumbing, not a decision.

**Priority — three, never five.** With five levels nothing ends up being the most urgent:

| Label | Means |
| ----- | ----- |
| 🔴 `now` | Blocks work, or can lose data |
| 🟠 `soon` | Real, but the work continues without it |
| ⚪ `someday` | Worth doing, nobody is waiting |

**Type** — the same one that opens the title: `bug`, `feature`, `enhancement`, `refactor`, `security`, `docs`, `performance`.

**Zone** — the two zones of the note that produced the issue. The tracker then filters by the same vocabulary the memory searches by, instead of inventing a second language for the same thing.

## The template

**Title:**

```
<emoji> <type>: short description
```

🐛 bug · ✨ feature · ⚡ enhancement · 🔧 refactor · 🔒 security · 📝 docs · 🚀 performance

**Body:**

```markdown
## 🎯 Problem or objective
- What happens, or what we want. One to three bullets, specific.

## 🧭 Context
- Where it happens (module, endpoint, screen)
- Why it matters
- When it happens: always, sometimes, only under some condition

## 📦 Scope
- **Includes:** what IS part of this
- **Does NOT include:** what is out, and what should be its own issue

## 📂 Likely files
- the paths this is expected to touch

## ✅ Checklist
- [ ] a specific action
- [ ] a specific action
- [ ] tests
- [ ] quality gates

## 🏁 Definition of done
- [ ] tests pass
- [ ] no debug code left
- [ ] no cosmetic refactor smuggled in
- [ ] summary written, and how to test it

## 🔍 How to validate
1. steps to verify it
2. expected result
3. edge cases worth checking

## ⚠️ Risks
- breaking changes, performance, migrations — only if they apply
```

**"Does NOT include" is the most valuable line in the issue.** It is the only part that lives nowhere else, and it is what stops one issue from swallowing everything near it. Write it before the checklist, not after.

## While it runs

- **Every work commit carries the issue number.** That is what lets the system tell, later, that work happened.
- **Keep the checklist honest as you go** — tick what is genuinely done, when it is done. A checklist updated only at the end is a checklist that lied all week.
- **The boot warns when an issue has commits it never reflected.** That warning means the checklist is lying, not that the work is late.

## When the work changes

**Edit the issue that is open. Never close it and open another.** One thread: rewrite the scope, strike what no longer applies, leave the change visible inside. Two live issues for the same work is how two people build different things — and memory already carries the *why* of the change, as a new decision replacing the old one.

## Closing one

It closes when the work ships, not when the last box is ticked. Close it citing what shipped. **Closing is a decision too — show what you would close and wait.** Never close in bulk.

## Red Flags — STOP

- About to create an issue without being told to.
- About to answer a defect you could fix with "I'll open an issue for it".
- Writing an issue with no "does NOT include".
- Inventing labels without looking at what the repository uses.
- Ticking a box for something not verifiably done.
- Closing an issue and opening a new one because the direction changed.
