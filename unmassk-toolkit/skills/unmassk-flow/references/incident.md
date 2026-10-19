# Incidents — the scar of something that was working

Open this when something that was signed off breaks. An incident is a failure *after* delivery: a scar worth recording, because a second failure on the same ground means something underneath is wrong. A defect found while building is ordinary work: the reviewer says it, it is fixed, the build carries on (House handles a stuck step, `SKILL.md` Build).

An incident repair is not blocked by the one-task-in-flight check; park the open task first.

```
NO INCIDENT IS CLOSED WITHOUT ANSWERING WHETHER A WALL COMES OUT OF IT
```

The answer may be no. Asking is mandatory.

## 1. Investigate

Start with the first route; use the others for what it cannot give. Tell House it is an incident (already delivered, then broke) so his report carries the incident note, and tell him in the first prompt where the project writes its logs.

| Route | Use when | Ends in |
|---|---|---|
| Describe the failure in plain words to **House** | Default | A verdict with a root cause, or an honest «I could not diagnose this». |
| Hand a fresh House the **production logs** | His first run could not reproduce it (`NO DIAGNOSIS`) | The same verdict, on evidence from the real run. |
| Send **Bilbo** to map the area first | Nobody knows which part broke | A map: modules, callers, and the walls and scars of those zones. Never a diagnosis. |

A map names no culprit: a named culprit gets believed. Give the mapper what a diagnosis needs: how the failure reproduces, where the project writes its logs, and what was left out of the sweep.

An incident needs a cause, not a diagnostician. A client report, a failed deploy or missing data starts one manually. Never write your own guess up as a verdict.

## 2. Record the scar

Write it the moment the verdict arrives, before the fix and not at session close. The scar is House's Proposed incident note, committed as written: its zones and keys are what make it findable later. Its body holds:
- **How sure the cause is:** confirmed, likely or probable.
- **Where it lives**, anchored by function or module name, never a line number.
- **How to reproduce it.** This becomes the regression test. If it could not be reproduced, write those words and put the log evidence and conditions in their place.
- **What it cost**, if known: hours, data, downtime. That number later decides the wall.

With no root cause there is no incident; say so plainly. If the failure does reproduce, leave an open question with the steps and the paths already ruled out.

## 3. Fix it

Use a branch and the procedure Triage picks; an incident repair is never Trivial. House's severity and affected files feed that triage, and a T1 or a data or memory path goes to Full. The scar is already recorded, so this is ordinary work. Whatever the build mode, Dante first turns House's Reproduction into a failing test; then the fixer House's Fix to route names makes it pass. In Full, Plan writes the plan file without asking; if the repair will span sessions, offer its issue and record (`references/plan.md`).

## 4. Close it

Closing is one command with the answer inside:

```
gitmem remove <incident-ID> "<what was done>" --restriction no
gitmem remove <incident-ID> "<what was done>" --restriction new \
  --restriction-text "<the wall>" --why "<what it cost>"
```

The incident leaves the live index and lands in the archive with its reason. Closing and the wall are one act: a wall that cannot be written stops the close and says why. The wall's criterion is the one memory uses everywhere (`unmassk-memory`). Answer the wall question yourself; ask the owner when what it cost is his to know.

Then close as any work does (`SKILL.md` Close): merge, delete the branch, close the plan's issue if one was opened. Alexandria's CHANGELOG entry for the fix cites the incident id.

A closed incident is history. If the same thing breaks again it is a new incident, including when the first fix was wrong.

## Stop signs

- Recording a scar for something found while building.
- Fixing first and recording afterwards.
- Writing the note from your own reading, with no cause established.
- A note with neither reproduction steps nor an explicit «could not be reproduced».
- Closing without answering the wall question.
- Anchoring the cause to a line number.
