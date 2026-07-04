---
name: unmassk-grill
description: >
  Before anything significant, interrogate the user relentlessly to resolve every
  branch of the decision tree before writing a line of code. Use when a decision
  has stakes, the request is ambiguous, there are two valid interpretations, or
  the user says "grill me", "stress-test this plan", "let's think this through",
  or describes something big without having decided the details. Reach for this
  instead of guessing what the user meant — guessing builds the wrong thing.
---

# Grill

Adapted from Matt Pocock's grill-me (MIT). The interview discipline is preserved; the persistence is changed: decisions go to git-memory, not to `.md` files.

## When this fires

Something significant is on the table. First, **search git-memory** for prior decisions on this topic:

- **Found a relevant decision** → surface it. Don't re-litigate what's settled.
- **Nothing found** → ask the user: do we start a brainstorming pass, or do you already know what you want? Route accordingly (council/brainstorm vs. straight grill).

This skill is invoked two ways — **direct** (the user explicitly asks: "grill me", "stress-test this", or a decision with obvious stakes comes up in conversation) and **pipeline-invoked** (called automatically by `unmassk-project-lifecycle`'s START branch, or `unmassk-flow`'s Triage for a Standard/Big feature). The mode changes one thing — see "Bounded mode" below — nothing else.

## Vagueness preamble (run before the interview starts)

Before asking anything, scan the request's own wording for the kind of vagueness that produces the wrong build regardless of how many decisions get resolved later. Look for:

- **Unquantified qualifiers** — "fast", "simple", "scalable", "robust" with no number or concrete bar attached.
- **Missing actors** — "the user can..." without saying which user/role, when more than one exists.
- **Missing error states** — a happy path described with no mention of what happens when it fails.
- **Ambiguous scope boundary** — a request that reads as one feature but is actually 2-3 bundled together (see "Independently testable slice" below).

Anything caught here becomes the first questions in the interview — don't run this as a separate pass, fold it into the same one-at-a-time loop.

## The interview

Interview the user relentlessly about every aspect of the plan until you reach shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one by one.

Rules:

- **One question at a time.** Never bundle.
- **Provide a recommended answer with every question.** Defaulting to "what do you think?" is lazy.
- **If a question can be answered by exploring the codebase, explore it instead.** Don't ask what grep or Read resolves.
- Wait for the answer before the next question.
- **Independently testable slice.** When resolving feature scope, ask: "if we build only this part, is it useful/verifiable on its own?" If the answer is no, the request is bundling multiple features — split it before proceeding, don't plan a single monolith that can't be tested or judged as pass/fail until everything is done.

### Bounded mode (pipeline-invoked only)

When `unmassk-project-lifecycle` or `unmassk-flow` invokes this skill automatically (not a direct user request), cap the interview at **5 questions**. State the cap isn't reached by bundling ("is X and Y both fine?" counts as one question toward the cap, don't game it by merging). If 5 questions aren't enough to resolve the tree, capture what's resolved as `decision()`s, log the remaining open branches as an explicit list, and let the calling skill proceed — don't stall an automated pipeline step indefinitely.

When the user invokes this directly ("grill me"), stay unbounded as before — a human actively driving the session can go as deep as the decision warrants.

## Output

As each branch resolves, the decisions that emerge are real decisions — capture each as a `decision()` in git-memory with its `Why:`. This is the integration with the toolkit that Pocock's original doesn't have: the grill doesn't just align understanding, it produces durable, auditable decisions.

## Boundary

- Persistence → git-memory only. Never CONTEXT.md or ADR files.
- This skill aligns and decides. It does not implement.
