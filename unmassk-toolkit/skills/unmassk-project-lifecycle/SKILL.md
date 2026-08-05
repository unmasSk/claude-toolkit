---
name: unmassk-project-lifecycle
description: >
  Use when the user asks to "start a new project", "let's start", "scaffold",
  "continue", "pick up where we left off", "where were we", "scan this repo",
  "I inherited this codebase", "set up this project". Also invoke AUTOMATICALLY,
  as the FIRST step, whenever the user opens work — build, create, implement, or
  continue anything — on a project you have not situated yet this session; do not
  wait to be asked, and situate first even when the state seems obvious. Runs the
  matching protocol: START (new project), CONTINUE (a project that already
  carries our memory), or SCAN (unfamiliar/external repo, seed memory). Naming a stack
  ("a React app") does not skip the earlier definition phases — the stack is one
  decision among many, seeded after requirements and foundations. Do not write
  code on a project you have not situated.
---

# Project Lifecycle

One skill, three situations. First **detect** which situation applies, then run that branch.

## Detection (run first, always)

Check two facts, by looking — not by assuming:

1. **Does this project carry our memory?** `gitmem search <any word>` answers
   something, or `.claude/project-memory/` exists with notes in it.
2. **Is there existing code?** Source files, package manifests, config.

Route:

| memory | code | Situation | Branch |
|------------|------|-----------|--------|
| yes | yes | Continuing our own project | → CONTINUE |
| no  | yes | External repo, never used the toolkit | → SCAN |
| no  | no  | Brand new project | → START |
| yes | no  | Project mid-preparation — START ran partway (decisions saved, no code yet) | → resume START at its last completed phase; the last close says which one |

State the detected situation to the user in one line before proceeding.

---

## START — new project

Goal: an idea turned into a project prepared *perfectly* before a single line of business code — requirements, behavior, visuals and engineering foundations all seeded first.

**First, calibrate.** START is not one rail for everything. A throwaway script or a one-screen tool does NOT walk all six phases — see the triage at the top of `references/start.md`. The full protocol below is for a real product; trivial work skips the heavy phases the same way Flow's triage skips its pipeline.

**Run the full protocol in [`references/start.md`](references/start.md)** (the "director" — the master file that orchestrates the phases). Read it top to bottom. In summary, six phases:

- **A · Define** — interrogate by thematic blocks (via `unmassk-grill`), and **each answer is saved the moment it is given** — never batched at the end. The PRD is derived from those decisions, not kept in parallel with them.
- **B · Design the behavior** — high-level flow diagrams, then three-layer walkthroughs (see [`references/walkthroughs.md`](references/walkthroughs.md)); cross-check the data model against every walkthrough.
- **C · Design the visuals** — mockups via `unmassk-design`, following research → brief → build → render-before-show.
- **D · Foundations, decide** — `ARCHITECTURE` + `STANDARDS` as separate binding docs; offer the full enterprise foundations catalog (see [`references/foundations.md`](references/foundations.md)), Mandatory vs Conditional, opt-out.
- **E · Build the base** — scaffold (`unmassk-scaffolding`) → wire the accepted foundations in code → Phase-1 plan as a verifiable checklist → test-first, no infra mocks, blocking CI/CD from the first commit. Record the project's test command in `.claude/project-memory/config.json` under `test_command`, so a machine reads it instead of somebody remembering it.
- **F · Close** — run `unmassk-close-session`; its Next is the bookmark that says exactly where this picks up again.

Do not write business code until phases A–D are seeded and the base (phase E) stands.

---

## CONTINUE — our project, new session

Goal: reconstruct state, orient, confirm direction.

1. Read what the boot already injected (decisions, memos, status, next steps).
2. Summarize in plain language: what's done, what's in progress, what's pending, what's next.
3. Confirm the direction with the user before implementing.

This is mostly "boot + spoken orientation". Keep it short; the data is already there.

---

## SCAN — external repo, no toolkit memory

Goal: seed memory retroactively, **without touching any prior commit or any code**.

Order matters — code is the reliable source, git is the complement:

1. **Scan code + config first.** `package.json` → stack. Folder structure → architecture. `.env.example` → services. Tests → what's validated. These yield **EXTRACTED** decisions (real, verifiable).
2. **Each decision must reference its proof** — `file:line`. Not "uses Next.js" but "uses Next.js — package.json:14". This is what separates the scan from a mass hallucination.
3. **Cross with commits** for dates, authors, context. What can't be verified from code → mark **INFERRED**.
4. **Seed:** one note per decision, each with its why and its `file:line`. Zero changes to the existing history or code.

This takes time. That's expected — it's a once-per-project setup. Make it explicit to the user ("I'm going to scan this project, it'll take a while"), not silent.

---

## Boundary

- This skill **situates and seeds**. It does not enforce process — that's for gates/hooks.
- Everything is saved to the project's memory, never to a loose `.md` file.
