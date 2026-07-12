# Three-Layer Walkthroughs

> Reference for START **phase B**. The method for pinning down every action of the system, screen by screen, *before* the data model is frozen and long before any code exists.
> This is the step that turns a PRD into a buildable contract. It is dense and it is reused once per action — that is why it lives in its own reference.

## What a walkthrough is

Every action the system can perform, told in **three layers at once**, step by step:

- 👁 **SEES** — the screen the person is on, with *all* of its outputs (not just the happy path).
- ⚙️ **DOES** — what the system executes.
- 🗄️ **DB** — which row is born or changed, and what it links to.

Each action is walked from **four points of view**: the customer, the employee, the admin/owner, and the database. Drawing the screen of each step and enumerating *every* exit — including the error branches — is what surfaces the decisions and the gaps that plain conversation never reveals.

## The method (one action at a time)

For each action on the agenda:

1. **Trace it in the three layers**, from the four viewpoints, drawing the screen of each step and listing **all** its exits — happy path and every error branch.
2. **Surface the decisions to pin** (where each one lands) and the **loose ends** (screens or cases not yet traced).
3. **Resolve them one by one in conversation**, each with a recommendation, and persist each as a `decision()` in git-memory. Only the *already-decided* flow goes into the visual artifact — never the discussion.
4. **Build the visual artifact**: an HTML wireframe of every screen, its options, and its error branches. Render it and review it before showing it (see phase C's rule — the same discipline applies to any visual artifact).
5. **Get the user's approval on this action before opening the next one.** One action closed before the next is opened.

## Hard rules (learned the expensive way)

- **Design each screen by its edge cases before drawing it.** The corner cases decide the layout; discover them first.
- **A wireframe must show ALL options**, not a trimmed subset, and is **verified complete against the data model** before it is shown.
- **Before calling anything a gap, search git-memory first** — the docs lag behind the decisions, so a "still open" question may already be closed in memory.
- **The artifact carries only the decided flow.** The alternatives considered and the reasoning stay in git-memory, not in the wireframe.

## Cross-check against the data model

Walkthroughs and the data model are verified against **each other**, in more than one pass, before either is called done. The walkthroughs are what the data model must serve; if a screen needs a field the model doesn't have, one of the two is wrong — reconcile before proceeding. In practice this catches dozens of discrepancies that a single pass misses.

## Output

- One approved HTML wireframe per action, kept as the binding visual contract alongside the PRD and the data model.
- Every decision that emerged persisted as `decision()` with its Why.
- Nothing in a `.md` "discussion log" — the reasoning lives in git-memory; the artifact shows only the decided result.

## Boundary

This reference defines the *method*. Which actions exist comes from the PRD (phase A). The walkthrough wireframe is a **schematic behavior contract** — it captures every option and every error branch, not the final look. The **visual direction** (real look and feel) is phase C's mockups, built on top of these approved wireframes for the key surfaces — never a second, contradictory visual track. Render-before-showing (open it, screenshot it) applies to any visual artifact, this one included.
