# Distilling memory from a previous or different system

**This runs once per project, deliberately, and never on its own.** It is not maintenance and not a migration: the earlier history is **read and never touched**, and what comes out is new notes that cite where they came from.

**Who does it:** the explorer agent — Bilbo — round by round. **Who approves the zones:** the user. **Who never does it:** a script, in one pass, unattended.

## The Iron Law

```
NOTHING IS REWRITTEN. EVERY DISTILLED NOTE CITES ITS SOURCES
```

A distilled note with no origin is not a distillation — it is an assertion, and nobody can check it or trace it back.

## Round 0 — harvest the zones

Before anything is distilled, sweep the **whole** history and pull out the candidate zones: the recurring subjects of this project, how often each appears, and one example. Present them and let the user approve.

**Why this comes first and covers everything at once:** if each round proposed its own zones, the later ones would invent new words for what the first already named, and the same subject would end up split across three zones that never meet.

**Zones are what makes distilling possible at all.** A note whose zone does not exist is rejected, so with no approved list every round would die at the first note.

## The rounds — oldest to newest, never in parallel

```
round 1 → the oldest block                        → produces N notes
round 2 → READS those N notes + its own block     → produces M notes
round 3 → READS the N+M + its own block           → ...
```

**Why in cascade, and this is the whole design:** rounds blind to each other distil contradictions as if all of them were true — a decision made in March and replaced in June comes out twice, both stated as current, and the round that saw March never learns it died. Reading the notes already produced — the notes themselves, with their reasoning, not a list of identifiers — is what lets a later round **replace with a pointer** instead of piling up.

**A round is about 400 commits.** That number is set by whoever hands out the round, not worked out inside it — an agent cannot see what it is spending. Measured on real histories, a hundred is far too small: it wastes most of the window and multiplies the rounds for nothing, and most of the cost of that first pass was the one-off zone harvest, not the distilling.

**Cut at a natural seam, not exactly on the number.** A history divides itself into working sessions, and its own closing commits mark them: aim for the size and stop at the nearest one, so a round never splits one piece of work in half.

**And cut at a natural seam, not at a round number.** A history divides itself into working sessions — its own closing commits mark them. Aim for the size above and then cut at the nearest seam, so a round never splits one piece of work down the middle.

**Every round starts by reading the real zone list.** Empty or missing means the harvest was never approved: stop there. And with the list in hand, anything that does not fit is visible at that moment rather than after the fact.

**A round may create a zone that is genuinely missing** — same as anywhere else in this system, in the open, without asking. The harvest catches the bulk; it does not catch everything. **Each round declares in its report which zones it created**, so they get reviewed together instead of being discovered months later.

## What a later round owes the earlier ones

Reading what came before is not for context. **It is to close it.** A round that only adds notes produces a portrait of the past; the point is to end with the present state.

So every round, before writing anything of its own, asks what its block resolves:

- **An open question that these commits answer** → it is not left open. The note carrying the answer promotes it in the same act: up to a fact if the answer is yes, down to discarded if the answer is no. The archive then says what it became.
- **A decision these commits overrode** → the new one is written pointing at the one it replaces. Two live decisions contradicting each other is the failure this whole design exists to prevent.
- **A restriction that stopped being true** → retired, with the reason.
- **An option that was tried later and rejected** → recorded as discarded, so nobody re-proposes it in a year.
- **A failure the history shows was fixed** → recorded as an incident **and closed**, at the point where the history says it was resolved. Left open, it shows up as a live incident at every boot for something settled years ago — and if a wall came out of it, that wall is the part worth keeping.
- **Something that was waiting on someone and eventually arrived** → the same: recorded and cleared, not left hanging.

**Nothing is distilled into an open state that the history already closed.** The end result is the project as it stands, not a photograph of every moment it passed through.

**And this is checked, not assumed.** Distilling is slow — once per project, and the slowness is the point: every link is verified against the history that produced it, not inferred. A pointer that says a decision was replaced is worth exactly as much as the commit that proves it.

**The last round is the one that has to leave the memory usable.** What is still open when it finishes is genuinely open — and that is information, not an oversight.

## What comes out

**A block of old commits is not a block of notes.** Several commits about one thing become one note; plenty of the old material does not deserve to survive at all. **Saying what was dropped, and why, is part of the result** — otherwise nobody can tell the difference between "there was nothing there" and "it was missed".

Each note goes to its natural type: a choice with its reasoning is a decision · a stable fact is a memo · something that can break work is a restriction · something unresolved is an open question · something studied and rejected is a discard.

**What is not project memory does not become a note.** Working preferences — how the user wants to be spoken to, what annoys them — belong to the rules channel.

**And so does everything else about how the work gets done**, which is the trap: a review protocol, an agent's instructions, the order of a checkpoint, a coding convention. Those read exactly like decisions about the product — "we decided the audit runs in eight steps" is grammatically identical to "we decided on Postgres" — and they are not. **The test: would this still be true if a different team built the project?** If yes, it is the project's memory. If it would only be true for whoever happens to be building it, it is a rule, whatever shape it is written in.

In an early history this is most of what you will find: the first weeks of a project are usually about setting up how it will be worked on, not about the product itself.

**Rules do not carry their sources, and do not need to.** A rule is worth what it says, not where it came from. What they do need is the same order as everything else: distilled oldest to newest, so a later one overrides an earlier one that says something different. The law about citing sources is for the project's own notes.

## Red Flags — STOP

- Distilling before the zones are approved.
- Running rounds in parallel, or newest first.
- A round that never reads what the previous ones produced.
- A note with no sources cited.
- Rewriting, amending or deleting anything in the old history.
- Dropping material silently: what was dropped is part of the report.
