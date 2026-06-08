---
name: unmassk-project-lifecycle
description: >
  Detects the project situation and runs the right lifecycle protocol: starting a
  new project, continuing an existing one, or scanning an unfamiliar/external repo
  to seed memory. Use this skill at the start of any work on a project — when the
  user says "new project", "let's start", "continue", "where were we", "pick up
  the project", "scan this repo", "I inherited this codebase", or whenever it's
  unclear what state the project is in. Always reach for this before writing code
  on a project that hasn't been situated yet.
---

# Project Lifecycle

One skill, three situations. First **detect** which situation applies, then run that branch.

## Detection (run first, always)

Check two facts:

1. **Is there toolkit git-memory?** (decision/memo trailers in the commit history)
2. **Is there existing code?** (source files, package manifests, config)

Route:

| git-memory | code | Situation | Branch |
|------------|------|-----------|--------|
| yes | yes | Continuing our own project | → CONTINUE |
| no  | yes | External repo, never used the toolkit | → SCAN |
| no  | no  | Brand new project | → START |
| yes | no  | Rare/inconsistent state | flag it, ask the user |

State the detected situation to the user in one line before proceeding.

---

## START — new project

Goal: don't let implementation begin until the base decision tree is seeded.

1. Cascade the requirements from the project type. A SaaS implies: cloud server, cloud DB, possibly Redis, auth, OAuth provider, and so on. Walk the chain so the known-in-advance requirements surface as nodes.
2. For each major choice (stack, framework, DB, auth), capture a `decision()` with its `Why:`.
3. Hand off to the scaffolding wizard (`unmassk-flow-stack`) for the actual structure.
4. **Critical:** ensure the choices made in scaffolding are written to git-memory as decisions. The richest moment in decisions is the start — do not let it evaporate.

Do not write feature code until the base tree exists.

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
4. **Seed:** many memory commits (one per decision, each with Why + reference), a single push. Zero changes to the existing history or code.

This takes time. That's expected — it's a once-per-project setup. Make it explicit to the user ("I'm going to scan this project, it'll take a while"), not silent.

---

## Boundary

- This skill **situates and seeds**. It does not enforce process — that's for gates/hooks.
- All persistence goes to **git-memory**, never to `.md` files.
