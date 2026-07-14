# Patterns — English rule library (the floor)

The deduped rule library for English. Order of operations: **structure first** (the
#1 detection signal), then vocabulary, then formatting. Fixing words while leaving
robotic rhythm still reads as AI.

On a byline with a protect list, the protect list wins over any rule here. Apply
tiers, not blanket bans — see the over-polishing warning at the end.

---

## Tier system (vocabulary)

- **Tier 1 — always replace.** Appears 5–20x more in AI text than human text.
- **Tier 2 — flag in clusters.** Fine alone; 2+ in one paragraph is a strong tell.
- **Tier 3 — flag by density.** Normal words AI overuses. Flag only when they hit ~3%+ of the text in place of specifics.

### Tier 1 — always replace

| Replace | With |
|---|---|
| delve / delve into | explore, dig into, look at |
| deep dive / dive into | look at, examine |
| unpack / unpacking | explain, break down, walk through |
| tapestry | (describe the actual complexity) |
| landscape (metaphor) | field, space, industry, world |
| realm | area, field, domain |
| paradigm | model, approach, framework |
| embark | start, begin |
| nestled | is in, sits in |
| testament to | shows, proves |
| pivotal | important, key, critical |
| underscores | highlights, shows |
| meticulous / meticulously | careful, precise |
| seamless / seamlessly | smooth, easy |
| robust | strong, reliable, solid |
| comprehensive | thorough, complete, full |
| cutting-edge | latest, newest, advanced |
| leverage (verb) / utilize | use |
| game-changer / game-changing | say what changed and why |
| watershed moment | turning point, shift |
| vibrant | (describe what makes it active, or cut) |
| thriving / bustling | growing, busy (or cite a number) |
| showcasing | showing, demonstrating (or cut) |
| intricate / intricacies | complex, detailed (name the complexity) |
| ever-evolving | changing, growing |
| enduring | lasting, long-running (or cite how long) |
| holistic / holistically | complete, whole |
| actionable | practical, useful, concrete |
| impactful | effective, significant (or describe the impact) |
| learnings | lessons, findings |
| thought leader / thought leadership | expert, authority (or describe the contribution) |
| best practices | what works, proven methods |
| at its core | (cut, state the thing) |
| synergy / synergies | (describe the combined effect) |
| interplay | relationship, connection |
| in order to | to |
| due to the fact that | because |
| serves as | is |
| boasts / features (verb) | has, includes |
| commence | start, begin |
| symphony (metaphor) | (describe the actual coordination) |
| embrace (metaphor) | adopt, accept, switch to |

### Tier 2 — flag when 2+ appear in one paragraph

harness, navigate / navigating, foster, elevate, unleash, streamline, empower,
bolster, spearhead, resonate / resonates with, revolutionize, facilitate,
underpin, nuanced, crucial, multifaceted, ecosystem (metaphor), myriad / plethora,
encompass, catalyze, reimagine, galvanize, augment, cultivate, illuminate,
elucidate, juxtapose, transformative, cornerstone, paramount, poised (to),
burgeoning, nascent, quintessential, overarching.

Replace with the plain verb or noun. If two or more land in one paragraph, that
paragraph reads as generated.

### Tier 3 — flag only at high density

significant / significantly, innovative / innovation, effective / effectively,
dynamic, scalable, compelling, unprecedented, exceptional, remarkable,
sophisticated, instrumental, world-class / state-of-the-art / best-in-class.

Normal words. Flag only when the text leans on them instead of numbers,
comparisons, or examples.

### Template / slot-fill phrases

If a phrase has a blank where any noun or adjective would fit and still sound the
same, it was generated, not written.

- "a [adjective] step toward [adjective] X" → name the specific capability or outcome.
- "Whether you're [X] or [Y]" → false breadth. Pick the real audience, or cut.
- "I recently had the pleasure of [verb]-ing" → just say what happened.

---

## Structure patterns (the #1 signal — weight these highest)

### Binary contrasts (the fatal family)

Telegraphed reversals. State the positive claim directly. Variants to catch:

- "Not because X. Because Y."
- "It's not just X, it's Y."
- "X isn't the problem. Y is."
- "The answer isn't X. It's Y."
- "It feels like X. It's actually Y."
- "more than just X" / "goes beyond X"
- "Less X, more Y."

FATAL on a byline whose voice spec bans it: zero, not "max one". Drop the negation;
assert Y.

### False agency (inanimate things doing human verbs)

AI uses this to avoid naming the actor. Name the human, or use "you".

| Before | Reality |
|---|---|
| "the complaint becomes a fix" | someone fixed it |
| "the decision emerges" | someone decides |
| "the culture shifts" | people change behavior |
| "the data tells us" | someone read it and concluded |
| "the market rewards" | buyers pay for things |

### Other structure tells

- **Uniform length (the metronome).** Mix short (3–8 words) with long (20+). Some one-sentence paragraphs. If a TTS engine could read it without sounding odd, it is too uniform.
- **Tricolon (rule of three).** Forced triads to sound comprehensive. Use two, four, or a full sentence.
- **Mirror structure.** Two consecutive sentences with identical shape. Break the symmetry.
- **Rhetorical question + immediate answer** as a transition. Lead with the answer.
- **Neat endings on every paragraph.** Let a third of them stop without a bow.
- **Negative listing.** "Not a X... Not a Y... A Z." State Z; skip the runway.
- **Dramatic fragmentation.** "Noun. That's it. That's the thing." Complete sentences instead (unless a protected fragment beat).
- **Rhetorical setups.** "What if...?", "Here's what I mean:", "Think about it:". Make the point.
- **Passive / subjectless fragments.** "Mistakes were made." "No config needed." Find the actor; move them to the front.
- **Synonym cycling (elegant variation).** "developers... engineers... practitioners..." in one paragraph. Repeat the clearest word.

---

## Content patterns

1. **Significance / legacy inflation.** Routine facts dressed as history. "Founded in 1989, a pivotal moment in regional governance" → "Founded in 1989 to publish regional statistics."
2. **Notability name-dropping.** Stacked prestige citations without context. Name the specific claim from the specific source instead.
3. **Superficial -ing analyses.** Present-participle tails faking depth ("...symbolizing renewal, reflecting community pride"). State the actual reason, or cut.
4. **Promotional / brochure prose.** "Nestled in the breathtaking foothills, a vibrant hub of culture" → "A town in the Gonder region with a weekly market."
5. **Vague attributions / weasel words.** "Experts believe", "studies show" with nobody named. Cite the source or drop the claim.
6. **Formulaic challenges sections.** "Despite challenges, it continues to thrive." Name the real challenge and response, or cut.
7. **Copula avoidance.** "serves as", "boasts". Default to is / has.
8. **Novelty inflation.** Treating an established idea as a discovery. Describe what the person did with it.
9. **Emotional flatline.** Claiming the feeling instead of earning it ("what surprised me most"). If it is surprising, the content shows it.
10. **False ranges.** "from the Big Bang to dark matter." List the actual topics, or pick the one that matters.

---

## Communication / filler patterns

- **Chatbot artifacts.** "I hope this helps", "Certainly!", "Great question", "Feel free to reach out." Strip entirely.
- **Cutoff disclaimers.** "As of my last update", "while specific details are limited." Find the fact or remove the hedge.
- **Sycophancy.** "You're absolutely right!", "That's a really insightful observation." Remove.
- **Acknowledgment loops.** Restating the prompt before answering. Just answer.
- **Confidence-calibration adverbs.** "Notably", "Interestingly", "Importantly", "Surprisingly." Flag by density.
- **Filler phrases.** "It is important to note that" → state it. "At this point in time" → "now". "The system has the ability to" → "the system can".
- **Excessive hedging.** "It could potentially possibly be argued that it might" → "It may."
- **Generic positive conclusions.** "The future looks bright", "exciting times ahead." Cut, or make it specific.
- **Signposting / "let's" openers.** "Let's dive in", "Here's what you need to know", "without further ado." Start with the point.
- **Persuasive authority tropes.** "The real question is", "at its core", "what really matters." Usually ceremony around an ordinary point. State the point.
- **Aphorism formulas.** "X is the Y of Z", "X is not a tool but a mirror." Replace with the concrete claim.
- **Conversational rhetorical openers.** "Honestly?", "Look,", "Here's the thing" as standalone hooks. A person being honest usually just says the thing.

---

## Style / formatting patterns

- **Em dashes.** Target zero. Catch the Unicode glyph (—, –) and the `--` / spaced `-` substitute, headings included. Rewrite with commas, periods, colons, or parentheses.
- **Boldface overuse.** One bolded phrase per major section at most. If it matters enough to bold, lead the sentence with it.
- **Inline-header vertical lists.** Bullets that open with a bold header restating themselves. Strip the header or make it a paragraph.
- **Title case in headings.** Sentence case for subheadings. Title case only for the top title, if at all.
- **Emoji in headers.** Remove. Social posts may use one or two end-of-line.
- **Curly quotes.** Use straight quotes (only a tell when stacked with others; word processors auto-curl).
- **Excessive bullet lists.** Convert bullet-heavy prose to paragraphs. Bullets only for genuinely list-like content.
- **Fragmented headers.** A heading followed by a one-line restatement of itself. Cut the warm-up line.

---

## Transition iteration (rewrite mode)

Slop shows most at the seams — how paragraphs and thoughts connect. Banning specific
transitions backfires: kill "Moreover" and the model collapses to a different small
set, or drops connective tissue entirely, and you get a new uniformity. Iterate
transitions; do not ban them. The target is variety plus voice-fit, not rarity — a
showy rare transition is its own tell.

**The procedure (every rewrite):**

1. **Draft pass.** Rewrite normally.
2. **Seam pass.** At each paragraph boundary and major thought-shift, generate 2–3 candidate openers and always include "no transition, start the thought cold". Choose by fit to voice and argument. Emitting the candidates is the forcing function that stops this collapsing to one pass. Format (internal scaffolding, not shipped in rewrite mode; surfaced in detect mode):

   ```
   [seam after "...last words of prior paragraph"]
     a) <candidate opener>
     b) <structurally different candidate>
     c) no transition: <how the next line reads cold>
     -> chose (x): <one-word reason: fit / rhythm / voice / cut>
   ```

3. **Monotony pass.** Read end to end for transition repetition. If two boundaries lean on the same move (two "and then"s, two Wh-openers), break one. Vary the *shape* of the connection, not just the word.

**Guards:** do not manufacture a transition where the thought connects on its own;
do not reach for rare transitions to seem human; on a protected byline, bias toward
that voice's natural transitions.

**Optional fresh-eyes pass:** for flagship pieces, run a separate transition review
with an agent that did not write the draft. It catches seam-monotony the author is
blind to. Not worth it on a tweet.

---

## Context-profile matrix

Adjusts strictness per surface. Rules not listed apply at full strength everywhere.

| Rule | linkedin | blog | technical-blog | investor-email | docs | casual |
|------|----------|------|----------------|----------------|------|--------|
| Em dashes | 2/post OK | strict | strict | strict | relaxed | skip |
| Bold overuse | hooks OK | strict | strict | strict | relaxed | skip |
| Emoji in headers | 1–2 end-of-line | strict | strict | strict | skip | skip |
| Excessive bullets | skip | strict | relaxed | strict | skip | skip |
| Hedging | strict | strict | relaxed | strict | relaxed | skip |
| Promotional | relaxed | strict | strict | extra strict | strict | skip |
| Copula avoidance | skip | strict | relaxed | strict | skip | skip |
| Generic conclusions | skip | strict | strict | extra strict | skip | skip |

**Technical-blog word exceptions** (legit technical meaning): robust, comprehensive,
seamless, ecosystem, leverage (platform/API), facilitate, underpin, streamline.
Still flag: delve, tapestry, embark, testament to, game-changer, harness.

**Auto-detect** when no profile is passed: <300 words + hashtags → linkedin; code
blocks → technical-blog; salutation + fundraising → investor-email; step-by-step +
params → docs; else blog.

**LinkedIn extra rules** (AI writing gets punished fastest there): lead with the
hook, not a setup; sentences under ~20 words; liberal line breaks; no "thought
leadership" framing; end with something real and unresolved, not a neat lesson.

---

## Severity tiers (for detect-mode triage)

- **P0 — credibility killers:** cutoff disclaimers, chatbot artifacts, vague attributions, significance inflation on routine events.
- **P1 — obvious AI smell:** Tier 1 word hits, template phrases, "let's" openers, synonym cycling, formulaic openings, bold overuse, em-dash frequency, the binary-contrast family.
- **P2 — stylistic polish:** generic conclusions, rule of three, uniform paragraph length, copula avoidance, transition phrases.

Quick passes cover P0+P1. Full audit covers all three.

---

## Over-polishing warning

Applying every rule at maximum strictness sands writing back toward the uniform
statistical profile that reads as AI in the first place. Deliberate fragments, the
occasional "And" opener, idiosyncratic word choice, and uneven pacing are what keep
text human. The goal is to sound like a person, not like clean prose. When in doubt
on a byline, defer to the protect list. When in doubt with no byline, prefer the
lighter edit.
