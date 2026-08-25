---
name: unmassk-memory-doctor
version: 1.0.0
description: Use when the user asks to "revisar la memoria", "pasar el doctor a la memoria", "audit the memory", "check the memory for rot", "is the memory healthy", "está sana la memoria", "buscar contradicciones en la memoria", "memoria que parece sana pero no lo está", or wants a read-only content review of the project's git-memory (and each agent's own memory) that lists rot suspects — contradictions, stale notes, dangling references, semantic duplicates — WITHOUT changing anything. This is a diagnostician for memory CONTENT, not the installation health check (git-memory-doctor) and not the coherence check (gitmem rezones --verify). It only looks and lists; retiring anything stays the owner's decision.
---

# The memory doctor

## What this is, and what it is not

The memory system already has two guards, and this is neither of them:

- `git-memory-doctor` checks the **installation** (plugin files, CLAUDE.md block, manifest, version). Plumbing, not content.
- `gitmem rezones --verify` checks that the **indexes match git**. Structure, not content.

Both can pass while the memory is quietly wrong. **This doctor reads the memory the way a person would and lists what smells off** — a live rule a decision already killed, two live notes that say the same thing in different words, a reference pointing at nothing, an order that can't be carried out. None of that trips a coherence check, because every index is internally consistent; the rot is in what the notes *mean*.

**It is an AI reading, not a script.** A script matches words; it can only find `"pendiente"`, never "these two notes are the same asset written twice." That is exactly the failure this exists to catch, and only understanding catches it. (This is why a mechanical `gitmem lint` was rejected — see the discarded note in memory.)

## The one hard rule

```
THE DOCTOR ONLY LOOKS AND LISTS. IT NEVER RETIRES, EDITS, OR SAVES.
```

Retiring a note, a rule, or a board item is always the owner's call, made with the note in front of him. The doctor's whole job is to **put that list in front of him** — grouped, each item citing the exact note ID or file it read, so he can decide in seconds. A suspect with no citation is a hallucination; drop it.

And it must never repeat the reader's own trap: **read the archived index first and treat archived notes as archived.** The classic trap is a reader seeing an archived note beside a live one and calling it a live contradiction. Know which is which before you judge.

## When to use

- The owner asks to review the memory, or suspects it has drifted.
- After a long stretch of sessions, as a periodic health pass on content.
- When something read out of memory turned out to be false, and you want to know what else is.

NOT for: coherence/index problems (`gitmem rezones`), install problems (`git-memory-doctor`), or writing/retiring notes (that is ordinary memory work, and the retiring is the owner's).

## The eight checks — each with the failure it catches

Run all eight. Each names a general failure mode that any project's memory can grow, not a story from one project; none is theoretical.

1. **Rules ↔ decisions contradiction.** Rules live in one file, decisions in the note indexes; **no index crosses them.** Read every live rule and every live decision and flag any pair that disagree. *Failure: a live rule a later decision already overruled keeps being read every session, because nothing crosses the two.*

2. **Each agent's memory ↔ its own index.** Every agent keeps its own memory (a `MEMORY.md` index plus detail files). For each agent, read its index and its detail files and flag where they disagree. *Failure: an agent's index marks a finding one way and its own detail file marks it the other — same agent, two files, drift nobody checks.*

3. **Semantic duplicates among live notes.** Two live notes in the same zone that mean the same thing in different words — the pair the mechanical same-keys-same-zone gate cannot catch because the words differ. Flag them as "probably one asset written twice; consider `--replaces`." *This is the check only an AI can do, and the reason the doctor is not a script.*

4. **Dangling references.** A note or a Next that points at "the pending question", "the decision above", "that note" without a resolvable target. Flag the reference and where it should have pointed. *Failure: a pointer to something the next reader cannot identify, so the thread is lost.*

5. **Inexecutable premises.** A note that orders an action that cannot be carried out — read code that has no source, hit an endpoint that no longer exists. Flag the note and why its premise is dead. *Failure: work parked on a premise that was never executable.*

6. **Time-word rot and expired horizons.** Notes leaning on words that decay — "hoy", "todavía", "pendiente", "de momento", "next release" — and notes carrying an explicit horizon that has already passed. Flag them as candidates to re-read; **do not assume they are stale** (some are legitimately about pending work). This is the one check a script could approximate, kept here so the human judgment sits next to it.

7. **Docs boards vs. reality.** Plans and boards under `docs/` that claim something is "open" when the code already resolved it. Memory lives in git, but boards in docs drift too; cross the board against the code. *Failure: a board item still "open" that the code already closed.*

8. **Reader-trap sanity.** Confirm the list views actually distinguish archived from live (the archived marker, the supersession back-link). If a view renders archived and live identically, the next reader will invent a contradiction — flag the view, not just the notes. *Failure: an ambiguous view that makes a correct memory read wrong.*

## How to run it

The orchestrator loads this skill and delegates the reading to one agent (the crew's diagnostician-style pass), injecting this protocol into the prompt. The agent works **read-only** and returns the grouped list. Steps:

1. **Gather, distinguishing live from archived.** `gitmem search` per zone for the live notes; read the archived index for what is archived and why (`→ replaced by` / `→ closed:`). Read the rules file. Read each agent's `MEMORY.md` and detail files. Read the boards under `docs/`.
2. **Run the eight checks** against what you gathered. For each suspect, keep the exact note ID or file path and one line of why.
3. **List, do not act.** Return the report below. Change nothing.

## The output

Group by check, most costly first (a live contradiction beats a time-word). Every line cites its source. End with the counts. Nothing is retired — every item is a candidate for the owner.

```
🩺 MEMORY DOCTOR — <n> suspects, 0 changes made

1 · RULES ↔ DECISIONS
   • <rule text>  ⟂  D-xxx (<one line: how they disagree>)

2 · AGENT MEMORY ↔ INDEX
   • <agent>: index says <x>, detail file says <y>  (<file path>)

3 · SEMANTIC DUPLICATES (live)
   • M-aaa  ≈  M-bbb  in <zone> — probably one asset twice; consider --replaces

… (checks 4–8) …

Nothing was changed. Retiring any of these is your call.
```

## Hard rules

- **Read-only. Writes nothing, retires nothing, saves no note.** The list is the whole deliverable.
- **Every suspect cites the note ID or file it came from.** No citation, no suspect.
- **Archived is not live.** Read the archive index before judging any contradiction.
- **This project's threat model is the system against itself** — memory lost, corrupted, contradicting itself, or read wrong. There is no external attacker here; a "suspect" about hostile input does not belong in the list.
- **The owner decides what dies.** The doctor never phrases a suspect as a done deal — always as "consider", "candidate", "worth a look".
