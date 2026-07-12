# START — New Project Director

> Reference for the START branch of `unmassk-project-lifecycle`. The **director** — the master file that orchestrates a brand-new project from an idea to a project prepared *perfectly* before a single line of business code.
> Read top to bottom. Run the phases in order. Two phases hand off to their own reference (B → `walkthroughs.md`, D → `foundations.md`); everything else runs inline here.
> This is prose you follow like a checklist. It is not enforced by a gate — it is enforced by reading it and doing the steps. Each phase states **Done when** so you know when to move on, and where to stop for the user.

## The principle

Nothing is improvised, trimmed, or "improved" on the fly. The whole point of START is that the decision tree is fully seeded — requirements, behavior, visuals, engineering foundations — *before* implementation begins. Each phase closes with its decisions persisted to git-memory; the richest moment for decisions is the start, and none of it is allowed to evaporate.

All persistence goes to **git-memory** (`decision()` / `memo()` / `context()`), never to loose `.md` files. At the close of every phase write a `context()` bookmark naming the phase just finished — that bookmark is what lets a later session resume START at the right phase instead of restarting.

## Phase 0 — Triage (calibrate before anything)

START is **not one rail for everything.** Classify the project first, the same way Flow triages a task, and run only the phases that fit:

| Size | What it is | Phases to run |
|---|---|---|
| **Trivial** | A throwaway script, a one-off, a spike. Correctness self-evident, nobody else maintains it. | Skip A–D. Scaffold minimally (E) and go. No PRD, no walkthroughs, no catalog. |
| **Small** | A single-surface tool or a small app with no real domain complexity. | A (light) → C (only if it has UI) → E. Skip walkthroughs (B) and the full foundations catalog; offer only the Mandatory foundations. |
| **Standard / Big** | A real product with domain logic, multiple roles/surfaces, data that matters. | All six phases, full. |

State the detected size to the user in one line and confirm it before proceeding. When in doubt, size up — but never drag a script through the whole rail.

---

## Phase A — Define

Interrogate until the project is actually understood.

1. **Interrogate by thematic blocks.** Walk the domain block by block (payments, auth, roles, catalog, stock, orders, notifications, whatever the project has). Use the Skill tool with `skill="unmassk-grill"` (TOOL CALL) for the interrogation discipline. Ask one question at a time, each with a recommendation.
2. **Persist each answer immediately** as its own `decision()` / `memo()` — never batch them for a summary at the end. A deferred decision is a lost decision.
3. **Write the PRD as a living document derived from git-memory.** Git is the source of truth; the PRD reflects what memory already holds and is re-synced after each round of decisions — never the reverse.

**Done when:** every thematic block has been walked and its open questions are either answered (as decisions) or explicitly logged as still-open; the PRD reflects them. Close with a `context(start): phase A done` bookmark. **Stop and confirm** the PRD's scope with the user before starting B.

---

## Phase B — Design the behavior *(Standard/Big only)*

1. **High-level flow diagrams first.** Draw the flows (areas × steps) before dropping to detail — drawing detects gaps conversation alone never surfaces. Track every gap in a list and close them one by one.
2. **Three-layer walkthroughs.** Apply the protocol in **`references/walkthroughs.md`**: each action in three layers (sees / does / DB) across four viewpoints, every exit including errors, decided in conversation, artifact carries only the decided flow, each action **approved by the user before the next**.
3. **Cross-check the data model against every walkthrough** — at least two passes; stop when a full pass finds no new discrepancy. The model must serve every screen; reconcile any discrepancy before the model is called done.

**Done when:** every action on the agenda has an approved walkthrough artifact and the data model survives a clean cross-check pass. Close with `context(start): phase B done`.

---

## Phase C — Design the visuals

For every visual surface, follow the cycle and **use the Skill tool with `skill="unmassk-design"` (TOOL CALL)**:

- **Research** real references and current trends (with sources) → **brief** (a binding brief, not a suggestion) → **build** → **render and review it with your own eyes before showing it** (open it, screenshot it). Never hand over a visual artifact sighted-unseen — that rule was learned from artifacts rejected for being shipped blind.

**Relationship to phase B (no duplication):** the wireframes from B are the *behavior contract* — schematic, they capture every option and every error branch. Phase C mockups are the *visual direction* — the real look and feel, built on top of the approved wireframes for the key surfaces (not every screen). B says what the screen must do; C says how it looks. C starts from B's approved wireframes; it never re-decides behavior.

**Done when:** the key surfaces have approved mockups and they don't contradict the walkthroughs. Close with `context(start): phase C done`. **Stop and get the user's approval** on each mockup before moving on.

---

## Phase D — Foundations: decide

1. **Write `ARCHITECTURE` and `STANDARDS` as two separate, binding documents**, each with a table of the alternatives considered and *why* they were rejected — not just the final choice.
2. **Offer the enterprise foundations catalog** in **`references/foundations.md`** — following its "How to run this in phase D" (don't ask 60 questions one by one: auto-accept the Mandatory set with a single "anything to drop?", prune the Conditionals that don't apply to this project's stack/shape, and ask one-by-one only the genuinely doubtful ones). Record every accepted and declined foundation as `decision()`/`memo()` so a "no" is a recorded choice, not a silent gap. List by name — the concrete tool per stack is chosen at build time, not here.

**Done when:** ARCHITECTURE and STANDARDS are written, and every catalog foundation is marked accepted or declined in memory. Close with `context(start): phase D done`. **Stop and confirm** the accepted foundation set with the user before building.

---

## Phase E — Build the base

1. **Scaffold** the project — use the Skill tool with `skill="unmassk-scaffolding"` (TOOL CALL).
2. **Wire the accepted foundations in code** — the ones accepted in phase D (validation, logging, dates, money, errors, security headers, and the rest), each with its lint rule where one applies so it's enforced by CI, not by goodwill.
3. **Translate every standard into a verifiable Phase-1 plan** — a checklist of concrete steps per task with an explicit wave map, not prose.
4. **Build mode is the orchestrator's call, not baked in here.** Per `unmassk-flow`'s Build mode: test-first for business logic with clear rules, linear for prototypes/exploration. Whichever mode, tests run with **no infrastructure mocks** — real dependency by default — and a **blocking CI/CD pipeline stands from the first commit**, not deferred.

Record the resolved test command in `.claude/git-memory-config.json` under `test_command` so the `stop-dod-gate` hook runs it automatically. A missing quality floor is captured as a `decision()` ("deferred: no test runner yet"), never left silent.

**Done when:** the project builds and runs, the accepted foundations are wired, the Phase-1 plan exists, and CI is green. Close with `context(start): phase E done — base stands`.

---

## Phase F — Close

Close with a `context()` bookmark that declares what was done and the exact next step — never end a session without a written resume point.

---

## Recommendations (not obligations — judge per project)

- **Council at checkpoints.** Use the Skill tool with `skill="unmassk-council"` (TOOL CALL) to audit at control points — useful, but the verdict is *filtered*, not adopted whole.
- **Extensive design research brief** — applies if there's brand-facing UI; pointless for a pure backend or an internal tool.
- **Exhaustive up-front component design system** — a call for a multi-surface product; overkill for a single-surface project.
- **Concrete stack choices** (framework, host, DB, ORM) are per project — what generalizes is the *process* of justifying with a table of rejected alternatives, not the choice itself.

---

## Boundary

- START **situates, decides, and prepares**. It does not enforce process with a gate — it is a checklist you follow. The phase bookmarks in git-memory are what make it resumable.
- Do not write business code until phases A–D (as the triage requires them) are seeded and the base (phase E) stands.
- All persistence goes to git-memory, never to loose `.md` files.
