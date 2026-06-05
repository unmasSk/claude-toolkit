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

## The interview

Interview the user relentlessly about every aspect of the plan until you reach shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one by one.

Rules:

- **One question at a time.** Never bundle.
- **Provide a recommended answer with every question.** Defaulting to "what do you think?" is lazy.
- **If a question can be answered by exploring the codebase, explore it instead.** Don't ask what grep or Read resolves.
- Wait for the answer before the next question.

## Output

As each branch resolves, the decisions that emerge are real decisions — capture each as a `decision()` in git-memory with its `Why:`. This is the integration with the toolkit that Pocock's original doesn't have: the grill doesn't just align understanding, it produces durable, auditable decisions.

## Boundary

- Persistence → git-memory only. Never CONTEXT.md or ADR files.
- This skill aligns and decides. It does not implement.
