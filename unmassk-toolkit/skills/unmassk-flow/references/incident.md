# Incidents — the scar of something that was already working

## What an incident is, and what it is not

**An incident is something that had been signed off and then broke.** Not a defect found while building it — that is ordinary work: the reviewer says it, it gets fixed, and the module carries on. A module being polished is not leaving scars behind; it is being built.

The line is the delivery. Before it, findings are work. After it, a failure is a scar, and a scar is worth recording because the next one on the same ground is not bad luck — it means something underneath is wrong.

This file is the seam between the fix and the memory. It does not restate the pipeline, the agents' lanes, or how a note is written — those are owned elsewhere and pointing at them is the point.

## The Iron Law

```
NO INCIDENT IS CLOSED WITHOUT ANSWERING WHETHER A WALL COMES OUT OF IT
```

The answer may be no. What may not happen is closing it without asking.

## 1. Investigate

Three ways in. **Start with the first**; the others are for what it cannot give:

| Route | Use it when | Ends in |
|---|---|---|
| **Describe the failure in plain words** to the diagnostician | By default | A verdict with a root cause, or an honest "I could not diagnose this" |
| **Hand over the production logs** | It cannot be reproduced here | The same verdict, on evidence from the real run |
| **Map the area first** | Nobody knows which part broke | A map handed over — **never a diagnosis** |

**The third route never concludes.** Whoever maps draws the territory — modules, callers, the walls of those zones and the scars already there — and hands it over. A map that names a culprit gets believed anyway, which is why it must not name one.

**Give the map what a diagnosis actually needs:** how the failure is reproduced, where this project writes its logs, and **what was left out** of the sweep. Without that last one the next person either redoes the reconnaissance or trusts an unknown gap.

**There is always a manual door.** A client reports it, a deploy falls over, data goes missing — an incident does not require a diagnostician to exist. It requires a cause. What it may never be is your own guess written up as a verdict.

## 2. Record the scar

**Write it the moment the verdict arrives** — not after the fix, not at session close. By then the detail is gone and what gets written is a summary of a summary.

The verdict brings what the note needs. Three things belong in the body and are lost otherwise:

- **How sure the cause is.** Confirmed, likely, or probable. A probable cause written flat reads as fact six months later.
- **Where it lives, anchored by name** — the function or the module, never a line number: the fix moves the lines minutes later.
- **How to reproduce it.** This is what turns the scar into a regression test. **When it could not be reproduced, say so in those words** and put the log evidence and the conditions in its place — otherwise whoever writes that test is chasing something that cannot be written.

**And what it cost**, if it is known: hours, data, downtime. That number is what decides the wall later, and by then nobody remembers it.

**When there is no root cause there is no incident** — half of it would be invented. Say it plainly. But if the failure **does reproduce**, the work is not lost: leave it as an open question with the steps and the paths already ruled out, so the next attempt does not burn the same three hypotheses.

## 3. Fix it

A branch and the pipeline as usual, sized by the same triage as any other work. The scar is already recorded, so from here it is ordinary work.

**It does not become a plan by itself.** If the fix is long enough to deserve one, offer it — opening it is the user's call.

## 4. Close it

Closing is one command with the answer inside:

```
gitmem remove <incident-ID> "<what was done>" --restriction no
gitmem remove <incident-ID> "<what was done>" --restriction new \
  --restriction-text "<the wall>" --why "<what it cost>"
```

It leaves the live index and lands in the archive with its reason. **Closing and the wall are one act: either both happen or neither does** — a wall that cannot be written stops the close and tells you why.

The wall's yardstick is the one memory uses everywhere. **You answer it; ask the user when what it cost is theirs to know** — you can see what broke, not what it was worth.

Then the ordinary closing of any work: squash the branch, and close the plan's issue if one was opened.

**A closed incident is history.** If the same thing breaks again it is a new incident, not a reopening — including when it means the first fix was wrong. That is information, not an error.

## Red Flags — STOP

- Recording a scar for something found while building. That is work, not an incident.
- Fixing first and recording afterwards. Record at the verdict.
- Writing the note from your own reading, with no cause established.
- A map that names a culprit.
- A note with no reproduction steps and no explicit "could not be reproduced".
- Closing without answering the wall question because "it was small".
- Anchoring the cause to a line number.
