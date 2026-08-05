---
name: unmassk-grill
description: >
  Use when the user asks to "grill me", "let's think this through", "help me
  define this", or describes something to build without pinning down what it must
  do. Also invoke AUTOMATICALLY, before starting any build, whenever WHAT to build
  is under-defined; do not wait to be asked. Concrete trigger test: before
  building, try to state in one sentence exactly what you are about to build — if
  you cannot without guessing, or if two materially different things would both
  satisfy the request, STOP and run this skill. Interrogates the user to resolve
  every branch of the decision tree before a line of code is written. NOT for
  picking between options that are already scoped and understood — only when what
  to build itself is undefined. Guessing what the user meant builds the wrong
  thing.
---

# Grill

Adapted from Matt Pocock's grill-me (MIT). The interview discipline is preserved; what changes is where it lands — every decision is saved to the project's memory, never to a `.md` file.

## When this fires

Something significant is on the table. **Search the memory first** (`gitmem search <term>`):

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

When `unmassk-project-lifecycle` or `unmassk-flow` invokes this skill automatically (not a direct user request), cap the interview at **5 questions**. State the cap isn't reached by bundling ("is X and Y both fine?" counts as one question toward the cap, don't game it by merging). If 5 questions aren't enough to resolve the tree, save what is resolved, write down the branches still open as an explicit list, and let the calling skill proceed — don't stall an automated pipeline step indefinitely.

When the user invokes this directly ("grill me"), stay unbounded as before — a human actively driving the session can go as deep as the decision warrants.

## Output

Every branch that resolves is a real decision, and it is saved the moment it resolves — not batched at the end, where half of them get lost:

```
gitmem note D --zones <zone1> <zone2> "<what was decided, in English>" \
  --why "<why this and not the closest alternative>" \
  --description "<what was on the table>" \
  --discard "<the option that lost>" "<why it lost>"
```

**A branch that stays open after the interview is a question, not a gap** — save it as one, so the next session knows it is still owed an answer:

```
gitmem note Q --zones <zone1> <zone2> "<what is still undecided>" \
  --description "<what it blocks, and what has to happen to close it>"
```

## Boundary

- Everything is saved to the memory. Never a `CONTEXT.md`, never an ADR file.
- This skill aligns and decides. It does not implement.
