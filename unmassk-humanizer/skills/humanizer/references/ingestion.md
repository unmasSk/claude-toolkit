# Ingestion flow (curation mode)

How a piece of slop becomes a memorialized rule. This runs only when something is
flagged for capture. It is off the hot path — drafting and rewriting do not pay this
overhead.

## Trigger

- The user pastes text marked `slop:` (or "this is slop" + paste).
- You catch your own slop mid-conversation and flag it.
- The user points at a published example and says "ingest this".

## The six steps

For each flagged span, produce:

1. **Anatomy.** Quote the exact span. Name the phrasing and the grammatical move (copula avoidance, present-participle tail, tricolon, binary contrast, false agency, calco del inglés, etc.).
2. **Mechanism.** Why the model generates it. Tag to a cause — this is the differentiator; naming the mechanism is what lets us predict the next tell before it is common:
   - `reward-tuning`: hedging, sycophancy, both-sidesing, over-balancing.
   - `repetition-penalty`: synonym cycling, elegant variation.
   - `instruction-tuning`: list reflex, rule of three, header stacking, signposting.
   - `pretraining-register`: formal-corpus words (delve, tapestry, robusto, piedra angular).
   - `uncertainty-conditioning`: cutoff disclaimers, over-qualification.
   - `assistant-persona`: "let me know if", "I hope this helps", "buena pregunta".
   - `translation-artifact`: calcos, gerundios ingleses, orden de palabras del inglés (Spanish-specific).
   - `displacement`: a new tell created by a crackdown on an old one (see the anti-em-dash entry in the living corpus).
3. **Context.** Where it is actually fine versus where it is a tell. Not everything is a universal ban.
4. **Strength.** Assign a tier, never a blunt "never" unless it is a true universal (em dash, the fatal binary-contrast family):
   - Tier 1: always replace.
   - Tier 2: flag in clusters (2+ per paragraph).
   - Tier 3: flag by density.
   - context-dependent: fine in some profiles, a tell in others.
5. **Replacement.** The rewrite, plus the general rule behind it so it generalizes past this one example.
6. **Dedup + file.** Check the living corpus and the relevant patterns file (EN or ES). If already covered, merge as a variant. If new, write a fresh entry.

## The protect-list cross-check (mandatory before filing)

Run every proposed entry against `protect-list.md` (canonical: the byline's voice
spec). If the pattern collides with a protected signature — for example, the pasted
text happens to contain a phrase on the protect list — STOP. Surface the collision
and ask before filing. Do not let a slop entry accidentally ban the author's own voice.

## File-step friction (your dial)

- **Deliberate flag** (user pastes `slop:`): show the proposed entry, file on a one-word ok.
- **Self-caught** (you notice your own slop mid-conversation): auto-file and show a revertible diff, so it stays frictionless.
- A protect-list collision overrides both: always ask first.

You own this dial. Tighten or loosen it any time.

## Entry template (written into living-corpus.md)

```
### <short-name-of-tell>

- Added: YYYY-MM-DD  |  Tier: 1 | 2 | 3 | context-dependent
- Mechanism: <one of the tags above>
- Context: <where it is fine vs a tell>
- Before: "<the AI version>"
- After: "<the human version>"
- Rule: <the generalized directive>
- Source: <writer in the wild | my own output | published example URL>
```
