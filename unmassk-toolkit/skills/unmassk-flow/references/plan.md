# The plan — document, issue and record

Open this to propose, open, change or close a plan that spans sessions. A decision says *what* and *why* and stays in memory. A plan says *how* and *in what order* and ends when the work ships. A decision does not create a plan: a plan exists when the work spans sessions, whatever started it (a decision, a question, an incident, or the owner's wish). Never write a plan's record as if a decision demanded it.

This file covers a plan that spans sessions. Issue labels, the issue template, the line between fixing and opening, how an issue is kept up to date, edited and closed: `unmassk-memory/references/issues.md`. The document is the same file as the execution plan of the Full task (phases, steps, wave map, format in Plan in `SKILL.md`): there is one plan file, never two.

## Rule: you propose, the owner opens

A plan that spans sessions carries a document, an issue and a record. In Full the document is the plan file that Plan in `SKILL.md` already wrote without asking. What is offered is the issue and the record: that ceremony is the owner's call. Offer them in one line when the work stretches past a session or spans several zones, then stop. Open them only with his yes.

## The three pieces

| Piece | Where | Holds | Written by |
|---|---|---|---|
| **Document** | the plan directory (`SKILL.md` Plan) | What is built, in what order, and **what is out of scope**. | You, with the owner. |
| **Issue** | the project's tracker | A link to the document and the tickable checklist. | You, by hand, with the tracker's own command, in front of the owner. Never from a script or in bulk. |
| **Record** | a note in memory | The decision the plan came from, and the issue number. | You, in the same act. |

The document is the thinking and also carries its own checkboxes; the issue is the state seen from outside. Tick a step in both when it is genuinely done, with a one-line summary of where it stands. Keep the reasoning in the document. Write the "Out of scope" section before the phases: it is the only part that lives nowhere else.

## Open one

1. Propose the issue and the record in one line; wait for the yes.
2. The document is the Full plan file (Plan in `SKILL.md`). Add its `**Issue:**` line; write nothing twice.
3. Create the issue by hand, linking the document.
4. Save the record: the decision it comes from and the issue number.

## Close one

The plan closes when the work is merged to the integration branch (`dev`, or `main` in trunk). Then:
1. Close the issue, citing what shipped (Close in `SKILL.md` does it).
2. Add `**Status: COMPLETED**` to the document's header. Keep the document: it is the record of how the work was built. The one-task-in-flight check in `SKILL.md` looks for this exact marker.

## Stop signs

- Opening an issue because the work "feels big": offer it and wait.
- Creating an issue from a script, in bulk, or unseen by the owner.
- Writing the document without an "Out of scope" section.
