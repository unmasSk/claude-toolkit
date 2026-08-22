# The plan — document, issue, record

**Core principle:** deciding and planning are two different acts. The decision says *what* and *why* and stays in memory forever. The plan says *how* and *in what order* and dies when the work ships.

**A decision does not create a plan.** Deciding to use a technology is a decision and nothing else; *building* with it may or may not be a body of work. A plan is born when work is big enough to span sessions — and that work can come from a decision, from a question that needs investigating, from an incident whose repair is long, or from nothing at all except the user wanting it built. Never write a plan's record as if some decision demanded it.

**A plan is the heavy end of the same thing `references/issues.md` governs** (in the memory skill): one issue is a unit of work, a plan is a body of work with a document behind it. The labels, the issue template and the line between fixing and opening live there — read it first.

This file governs the plan that **spans sessions** — the one with an issue and a checklist the user follows. The execution plan of a single feature (tasks and wave map) stays in `SKILL.md` Step 3.

## The Iron Law

```
A PLAN IS OPENED BY THE USER, NEVER BY YOU
```

Offer it in one line when work stretches past a session or spans several zones. Then stop. A plan carries a document, an issue and a record — that is ceremony, and the ceremony is the owner's call.

## The three pieces

| Piece | Where | What it holds | Who writes it |
|---|---|---|---|
| **Document** | the project's plan directory | What is being built, in what order, and **what is out of scope** | You, with the user |
| **Issue** | the project's tracker | The link to the document, and the **tickable checklist** | You, by hand — never a script |
| **Record** | a note in memory | The decision this came from, and the issue number | You, in the same act |

**The document is the thinking; the issue is the state.** Don't duplicate the checklist into the document, and don't paste the reasoning into the issue. Each has one job.

**What is out of scope is the most valuable line in the document.** It is the only part that lives nowhere else, and it is what stops a plan from swallowing everything nearby. Write it before the task list, not after.

## Opening one

```
1. The user says to open it. Not before.
2. Write the document: goal, order of work, and what is NOT included.
3. Create the issue by hand, linking the document. The checklist lives here.
4. Save the record: the decision it comes from, and the issue number.
```

The issue is created with the tracker's own command, by you, in front of the user. Never from a script and never in bulk — an issue nobody read into existence is one nobody will maintain.

## While it runs

- **Every work commit carries the issue number.** That is what lets the system tell, later, that work happened.
- **At session close the issue gets caught up:** tick what is genuinely done and leave a one-line summary of where it stands. This is what keeps the boot quiet for the right reason.
- **The boot warns when an issue has commits it never reflected.** That warning means the checklist is lying, not that the work is late — fix the checklist.

## When the decision changes

**Edit the issue that is open. Never close it and open another.**

One plan, one thread: rewrite the scope, strike what no longer applies, and leave the change visible inside. Two live issues for the same work is how two people end up building different things — and memory already carries the *why* of the change, as a new decision replacing the old one.

## Closing one

A plan closes when the work ships, not when the last box is ticked. Close the issue citing what shipped, and mark the document as done rather than deleting it — it is the record of how something was built, and it costs nothing to keep.

## Red Flags — STOP

- About to open a plan because the work "feels big". Ask, don't open.
- About to create an issue from a script, in bulk, or without the user seeing it.
- Writing the plan document without a "what is out of scope" section.
- Closing an issue and opening a new one because the direction changed.
- Ticking a checklist box for something that isn't verifiably done.
- A session ending with an issue that has commits nobody reflected.

## Rationalizations

| Excuse | Reality |
|---|---|
| "This is clearly big enough to need a plan" | Offer it. The decision is the user's. |
| "I'll create the issue and tell them after" | An issue they didn't ask for is one they won't maintain. |
| "The scope changed, cleaner to start fresh" | One plan, one thread. Edit it. |
| "I'll tick the boxes at the end" | Then the boot warns, and the warning is right. |
| "The document says what's included, that's enough" | What's excluded is what stops the plan growing. |
