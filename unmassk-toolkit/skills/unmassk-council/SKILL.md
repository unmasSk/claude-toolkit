---
name: unmassk-council
description: >
  Run a high-stakes decision through a council of 5 advisors with opposing thinking
  lenses who analyze independently, peer-review anonymously, and synthesize a verdict.
  Also covers open-ended idea generation and throwaway prototyping — comparing
  candidate APPROACHES to an already-understood goal, where the goal itself is
  known and only the path there is open. Use when the OPTIONS are already known
  and the user must pick
  between them — "should I X or Y", "which option", "council this", "pressure-test
  this decision", "I'm torn", "help me decide", "prototype this". NOT for cases where
  the goal or requirements THEMSELVES are still undefined — that's `unmassk-grill`.
  Do NOT use for trivial choices with one right answer. Reach for this when being
  wrong would be expensive.
---

# Council

Adapted from Karpathy's LLM Council methodology. The verdict is saved as a decision in the project's memory, never as an HTML or `.md` report.

Three modes, pick by the kind of uncertainty:

- **Genuine decision with stakes** → run the full council (below).
- **Open exploration, no options yet** → brainstorm: generate ideas, then converge by forcing a single choice. Don't leave it expansive.
- **"Does this idea actually work?"** → prototype: throwaway code that answers one question. Delete or absorb when done. Save only the *answer*, with the question it answered, as a decision.

## Full council

### 1. Frame (with context)

Search the project's memory for prior decisions on this question, so the advisors decide *with* the project's context instead of blind — and so nothing already discarded gets proposed again. Then reframe the user's question as one neutral prompt all advisors receive: core decision, key context, project context from memory, what's at stake. Don't steer it. If too vague, ask exactly one clarifying question.

### 2. Convene — 5 advisors in parallel

Spawn 5 sub-agents simultaneously, each a thinking lens (not a persona):

1. **Contrarian** — hunts the fatal flaw, the questions you're avoiding.
2. **First Principles** — strips assumptions, asks if you're solving the right problem.
3. **Expansionist** — finds the upside everyone's missing.
4. **Outsider** — zero context; catches the curse of knowledge.
5. **Executor** — only cares what you do Monday morning.

Each: 150-300 words, no hedging, lean fully into the angle.

### 3. Peer review — 5 in parallel

Anonymize responses as A-E (randomize). Each reviewer answers: strongest response and why; biggest blind spot; what ALL responses missed. Under 200 words.

### 4. Chairman synthesis

One agent gets the question, de-anonymized responses, and all reviews. Produces:

- **Where the council agrees** (high-confidence signals)
- **Where the council clashes** (don't smooth over; present both sides)
- **Blind spots the council caught** (emerged in peer review)
- **The recommendation** (a real answer, not "it depends"; may side with a strong dissenter over the majority)
- **The one thing to do first** (single concrete step)

### 5. Present + persist

Present the verdict in chat (markdown, scannable). Then save it:

```
gitmem note D --zones <zone1> <zone2> "<the recommendation, in English>" \
  --why "<why it beat the closest alternative>" \
  --description "<where the council agreed, where it clashed>" \
  --discard "<each option that lost>" "<why it lost>"
```

The verdict already has the shape of a decision: the recommendation is the headline, the clash is the why, and every option the council rejected is a discard — one per option, not just the runner-up. Losing those is how the same idea comes back in six months.

## Cost warning

5 advisors + 5 reviewers + chairman = 11 sub-agent calls. The most expensive skill in the set. Gate it mentally: **if being wrong wouldn't hurt, don't convene the council.**

## Boundary

The verdict is saved as a decision and nothing else. No HTML report, no transcript `.md`, unless the user asks for one.
