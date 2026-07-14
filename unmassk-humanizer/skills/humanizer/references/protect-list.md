# Protect-list seam (template)

The floor (this skill) strips generic AI tells. The overlay (your voice spec)
defines what must survive on a given byline. This file is the seam between them.

It ships as a **template**. The categories below are the ones that most often
collide with a real writer's voice. Fill each from your own writing, or let a mirror
profile (see `voices.md`) generate it. Delete the placeholders once replaced — an
unfilled template protects nothing.

## The mechanism

The skill is reusable across contexts; each context supplies its own protect list:

- **Your byline** → your personal voice spec is canonical. The list below is the operational mirror for when that spec is not loaded.
- **A specific project** → that project's in-repo voice doc or CLAUDE.md.
- **No named context** → no protect list; apply the floor at full strength.

Rule: before flagging or filing on a byline that has a protect list, load it first.
Never strip a protected signature. If a floor flag collides with a protected item,
surface the collision and do not auto-edit.

## How to fill it in

For each category, quote the exact words, phrases, or moves that are genuinely
*yours* and that a generic de-slop pass would wrongly flatten. Be concrete — quote
the phrase. Anything you cannot point to in your own samples is not a signature yet;
leave it out. Keep it short and real. A bloated protect list defeats the floor.

## Operational mirror (canonical: your voice spec)

Fill every `<...>` from your own writing.

- **Reveal verb / framing tic** — the phrase you habitually reach for right before stating a finding. A generic pass cuts these as throat-clearing; keep yours.
  - `<your lead-in phrase>`
- **Intensifier verdict** — your go-to moderate judgment phrase. The floor kills the adverb inside it. Keep yours.
  - `<your verdict phrase>`
- **Hedge-then-commit words** — softeners that set up a hard claim. Keep them when they front a firm claim.
  - `<your hedge words>`
- **Closers** — your end-of-piece move (a question that hands the reader the ball, a directive, a sign-off). The floor restructures question openers; protect these as closers.
  - `<your closers>`
- **Fragment beats** — deliberate fragments and short/long stacking you use for rhythm. The floor flags dramatic fragmentation; keep the deliberate ones.
  - `<your fragment-beat examples>`
- **Conjunction openers** — `And` / `But` / `So` / `Y` / `Pero` at sentence or paragraph start, if on purpose. Keep.
- **Comma splices for rhythm** (occasional, deliberate) — keep if part of your cadence.
- **First-person density** — if you write heavily in first person on purpose, record your baseline ("I"s per 1,000 words) so the floor doesn't strip it for a "professional" tone.
  - `<your first-person baseline, if any>`
- **Word repetition over synonym-cycling** — if you deliberately repeat the right word, keep it.
- **Signature phrases** — recurring idioms, coined terms, pet metaphors that are distinctly yours.
  - `<your signature phrases>`

## Calibration gap (stricter-than-floor rules)

Where your voice spec is stricter than the floor, the spec wins. Common example: the
floor allows "max one" binary contrast per piece, but a voice spec may ban it at zero
(FATAL). Enforce the stricter setting. List any such gaps here so the floor does not
silently relax them.

- `<your stricter-than-floor rules, e.g. "binary contrast: zero, not max one">`
