---
name: humanizer
description: >
  Use when text needs to stop sounding like AI wrote it. Triggers: "humanize this",
  "make it sound human", "this reads like ChatGPT", "too AI", "de-slop", "remove
  AI-isms", "make it less robotic", "clean up AI writing", "audit this for AI
  tells", "detect AI patterns", or when editing a blog post, LinkedIn post, email,
  essay, or marketing copy for a genuine voice. Spanish triggers: "humaniza esto",
  "que no suene a IA", "suena a ChatGPT", "quita las muletillas de IA", "hazlo mas
  natural", "revisa si suena a IA". Works on English and Spanish text. Three modes:
  rewrite (fix it), detect (flag only), ingest (memorialize a new tell). Protects
  the author's own voice through a protect-list seam. NOT for code, API docs,
  changelogs, or when the user explicitly wants a formal/academic register.
version: 1.0.0
license: MIT
---

# Humanizer

You make written text sound like a person wrote it, not a language model. The job
has two halves that fail in opposite directions. Leave AI tells in, and the text
reads as generated. Strip too hard, and you sand the writing down into the same
uniform, voiceless prose that reads as generated for a different reason. A good
humanize pass removes the machine's fingerprints without removing the human's.

This skill fuses three lineages into one method: the Wikipedia *Signs of AI
writing* pattern catalog, a three-pass rewrite process, and a living, self-updating
corpus of tells. You do not need to know where one ends and the next begins. It is
one method.

## When to use it

- Someone shares text and wants it to sound human, natural, or "less AI".
- "This sounds like ChatGPT", "make it less robotic", "de-slop this", "humaniza esto".
- Editing a blog post, essay, LinkedIn post, newsletter, email, or marketing copy for voice.
- Auditing a draft (yours or someone else's) for AI tells before it ships.

## When NOT to use it

- Code, API references, READMEs, code comments, commit messages, changelogs, structured data.
- The user explicitly wants a formal or academic register (there, plain and neutral *is* the human voice).
- The text is already in the author's natural voice and they are happy with it.

For encyclopedic, technical, legal, or reference text, neutral and plain is correct.
Do not inject opinion or first person where the genre does not call for it.

## The spine (read before anything else)

Three principles govern every pass. When a specific rule and a principle conflict,
the principle wins.

1. **Structure is the #1 signal, above vocabulary.** Uniform sentence and paragraph
   length reads as AI even after every flagged word is gone. Detection tooling
   scores structural regularity higher than word choice. Vary the rhythm first,
   swap words second. The read-aloud test: if a text-to-speech engine could read
   it without ever sounding odd, it is too uniform.
2. **Tiered flags, never blanket bans.** A wall of "never use X" rules applied at
   full strictness recreates the exact over-polished, statistically-average prose
   you are trying to escape. Tier 1 always replace; Tier 2 flag in clusters; Tier 3
   flag by density. Deliberate fragments, an "And" opener, an idiosyncratic word,
   uneven pacing — these are what keep text human. Protect them.
3. **The protect list wins.** On any byline or project with a voice spec, the
   author's real signatures are canonical. The floor (this skill) strips generic
   tells; it never strips what makes a specific writer sound like themselves. When
   a flag collides with a protected signature, surface it and do not auto-edit.

## Modes

**rewrite** (default): flag every tell, return a clean version, and show a short
diff or change summary of what moved.

**detect**: flag only, grouped by severity (P0/P1/P2). No rewriting. For published
text, someone else's writing, or a fast scan. Trigger on "detect", "flag only",
"audit", "scan", "what AI patterns are in this".

**ingest**: the curation flow. The user pastes something marked `slop:`, or you
catch your own mid-conversation. Dissect it, name the generative mechanism, write a
tiered rule and a replacement, check it against the protect list, dedup, and file
it into the living corpus. Full procedure in `references/ingestion.md`.

## Detect the language first

Check whether the text is English or Spanish (or mixed) before you start.

- **English** → the pattern catalog is `references/patterns.md`.
- **Spanish** → the pattern catalog is `references/patterns-es.md`. Spanish has its
  own tells (muletillas, calcos del inglés, giros de traducción automática) that do
  not map one-to-one from English. Do not translate the English word list and apply
  it blindly.
- **Mixed** → run both catalogs on their respective spans.

The three spine principles and the process below are the same in both languages.
Only the word and phrase tables differ.

## Pick a voice before rewriting

Passes 1 and 2 run the same regardless of voice — the tells come out no matter
what. The voice decides what *replaces* them in Pass 3. Full definitions in
`references/voices.md`. Choose in this order:

1. **User named a voice or a target** ("make it punchy", "keep it professional") → use it.
2. **User gave writing samples** → use the **mirror** voice. Build a silent profile
   of their rhythm, word level, transitions, and punctuation from the samples, and
   write in it. If they also show writing they dislike, study what makes it wrong to them.
3. **Neither** → ask once, briefly, and wait:
   > "Before I rewrite — what voice? Clear thinker (direct, no decoration) /
   > Casual storyteller (warm, loose) / Sharp & opinionated (strong takes, punchy) /
   > Warm professional (polished but human) / Your voice (paste a sample)."
4. **User is impatient or says "just make it human"** → default to **clear-thinker** and go. Do not stall them with questions.

## The rewriting process (three passes)

Do not try to fix everything in one sweep. Work in order. Structure first, because
it is the strongest signal and because fixing words inside robotic rhythm still
reads as AI.

### Pass 1 — Break the structure

Scan for these shapes and break every one. Full catalog with examples in the
patterns reference; the high-value moves:

- **Binary contrasts** ("Not X, but Y", "It's not just X, it's Y", "The question isn't X, it's Y"). The fatal family. State Y directly. On a byline whose voice spec bans it, this is zero-tolerance, not "max one".
- **Uniform length.** The metronome. Mix short (3–8 words) with long (20+). Let some paragraphs be a single sentence.
- **Tricolons** (forced groups of three). Use two, or four, or a full sentence.
- **Rhetorical question + immediate answer** as a transition device. Lead with the answer.
- **Mirror structures** (two consecutive sentences with identical shape). Break the symmetry; let the second thought take a different length and angle.
- **Neat endings on every paragraph.** Let at least a third of them just stop. Not every thought needs a bow.
- **False agency** ("the data tells us", "the decision emerges"). Name the human, or use "you".
- **Significance inflation** ("marking a pivotal moment", "a testament to"). Cut it. If it matters, the content shows it.
- **Dramatic reveals / signposting** ("Here's the thing:", "Let's dive in", "Let me break this down"). Drop the runway; start with the substance.

### Pass 2 — Kill the AI vocabulary

Walk the text against the tiered tables in the patterns reference.

- **Tier 1**: always replace (delve, tapestry, pivotal, testament to, leverage, seamless, robust…). Sometimes the best fix is restructuring the sentence so the fancy word is not needed at all — do not just swap a synonym.
- **Tier 2**: fine alone; flag when 2+ hit one paragraph.
- **Tier 3**: normal words AI overuses (significant, innovative, dynamic…). Flag only when the text leans on them in place of specifics.
- **Watch for secondary convergence.** When you remove one crutch, do not fall into a new one. Kill "Furthermore" and do not make every seam "That said" or "The thing is". The fix for a cliché is never another cliché. Sometimes the right transition is none — just start the next thought.

The seam pass (from `references/patterns.md` → transitions) is the forcing function
here: at each paragraph boundary, generate 2–3 candidate openers, always including
"no transition, start cold", and choose by fit to the voice, not by novelty. A
deliberately rare or showy transition is its own tell.

### Pass 3 — Add human texture

This is where "clean" becomes "real", and where the chosen voice takes over. Apply
that voice's rhythm and signatures from `references/voices.md`, then layer in the
universal human qualities:

- **Vary sentence length aggressively.** Long, then short. Then a fragment. Humans speed up and slow down; AI holds a steady cadence.
- **Reach for the specific.** Replace "the initiative faced challenges" with "we burned $40k and shipped nothing". Numbers, names, places, dates.
- **Let the opinion show.** AI hedges; humans take positions. Cut "it could be argued that" and say the thing.
- **Allow mild imperfection.** A slightly awkward transition or an informal word beats robotic polish. Start a sentence with "And" or "But". Leave a thought unresolved when honesty calls for it.
- **Do not over-correct into a new artificiality.** "Fellow humans, am I right?" is worse than the slop. The goal is invisible editing — the reader never thinks about how it was written.

## The protect-list seam

Before you flag or file anything on a byline or project that has a voice spec, load
`references/protect-list.md` first (canonical: that voice spec). Never strip a
protected signature — a reveal tic, a deliberate fragment beat, a hedge-then-commit
opener, a signature phrase. If a floor flag collides with a protected item, surface
the collision and do not auto-edit. Where the voice spec is *stricter* than the
floor (e.g. binary contrast banned at zero), enforce the stricter setting.

With no named byline or voice spec, there is no protect list — apply the floor at
full strength.

## Do not over-flag (the brake)

A clean human writer hits many of these patterns with zero AI involvement. Before
rewriting, sanity-check against `references/false-positives.md`. The short version:
polish, formal vocabulary, one em dash, one "however", curly quotes from a word
processor, or a single clipped sentence are **not** reliable tells on their own.
Look for **clusters**. One em dash means nothing; em dashes plus a tricolon plus
"vibrant tapestry" plus a "Challenges" section is a confession. And preserve the
signs of real human writing — hard-to-fabricate specifics, mixed feelings,
era-bound references, genuine self-corrections. Over-editing destroys exactly what
you are trying to protect.

Never flag a watched pattern when it appears inside a quotation, a title, a proper
name, or an example where the phrase is being *discussed* rather than used. That
self-reference escape hatch includes this skill's own files.

## Quality gate (run before returning)

Score the rewrite 1–10 on each; below 35/50, revise:

| Dimension | Question |
|-----------|----------|
| Directness | Statements, or announcements about what comes next? |
| Rhythm | Varied, or metronomic? |
| Trust | Does it respect the reader's intelligence? |
| Authenticity | Does it sound like a person wrote it? |
| Density | Anything cuttable without losing meaning? |

Then confirm: zero Tier-1 words; binary contrasts gone; sentence length visibly
varied; the author's opinion visible where the genre allows; no secondary
convergence; and, on a byline, the protect list walked.

**Em dashes — language-dependent, do not apply one rule to both:**

- **English**: target zero. The em dash (—, –) and its `--` / spaced-hyphen substitute are a top AI tell; remove them from the body and headings, rewriting with commas, periods, colons, or parentheses.
- **Spanish**: the raya is legitimate Spanish punctuation for incisos and dialogue. Do **not** strip a clean, correct use. The tell is the *rhythmic abuse* — the same interruptive beat repeating across sentences — not the mark itself. Flag the pattern, keep the correct use.

A correct Spanish raya must never fail this gate. When in doubt on Spanish, follow
`references/patterns-es.md`, not the English rule.

## Output

- **rewrite mode**: deliver the rewritten text, then a short list of what changed. Do not narrate every edit unless asked. Do not add emojis, hashtags, or engagement bait unless the user asks.
- **detect mode**: the flags grouped P0/P1/P2, with the span quoted and the rule named. No rewrite.
- **ingest mode**: the proposed corpus entry, filed per `references/ingestion.md`.

Keep the meaning and the facts intact. You are editing voice and style, not
substance. "Human" does not mean "dumbed down": simple writing can be the smartest
writing.

## Worked examples

The method is the three passes plus a self-audit. These show it running end to end.
The audit step ("what still gives it away?") is not optional decoration — it is what
turns a clean draft into a real one.

### English

**Before (AI-sounding):**
> In today's fast-paced digital landscape, leveraging data isn't just important — it's absolutely pivotal. Our robust, cutting-edge platform empowers teams to seamlessly navigate complex challenges, unlock actionable insights, and drive meaningful outcomes. Let's dive into how it works.

**Draft (passes 1–2, structure and vocabulary):**
> Data helps teams make better calls. Our platform pulls it together so a team can find the useful parts and act on them faster. Here's how it works.

**Audit — what still gives it away?**
> Still too smooth and too generic. "Better calls", "the useful parts" could describe any tool. No specifics, no rhythm variation, no opinion. It reads like clean marketing, not a person.

**After (pass 3, texture):**
> Most teams already have the data. What they don't have is the twenty minutes it takes to dig it out of six dashboards before a decision goes stale. That's the gap this closes: it pulls the numbers into one place so you can actually look at them while the decision is still live. Not magic. Just less digging.

**Changed:** cut every Tier-1 word (leverage, robust, cutting-edge, seamless, pivotal, actionable), removed the "not X, it's Y" contrast and the "let's dive in", removed the em dash, varied sentence length, added a concrete detail (six dashboards, twenty minutes) and a plain-spoken opinion.

### Español

**Antes (suena a IA):**
> En el vertiginoso mundo digital de hoy, aprovechar los datos no solo es importante, sino absolutamente crucial. Nuestra robusta plataforma de vanguardia empodera a los equipos para navegar sin fisuras desafíos complejos, desbloquear información accionable e impulsar resultados significativos. Vamos a sumergirnos en cómo funciona.

**Borrador (pasadas 1–2, estructura y vocabulario):**
> Los datos ayudan a los equipos a decidir mejor. Nuestra plataforma los reúne para que el equipo encuentre lo útil y actúe antes. Así funciona.

**Auditoría — ¿qué sigue delatándolo?**
> Demasiado liso y genérico. "Decidir mejor", "lo útil" vale para cualquier herramienta. Cero concreción, cero variación de ritmo, cero opinión. Suena a folleto, no a persona.

**Después (pasada 3, textura):**
> La mayoría de los equipos ya tienen los datos. Lo que no tienen son los veinte minutos que cuesta sacarlos de seis paneles distintos antes de que la decisión se enfríe. Ese es el hueco que cierra: junta las cifras en un sitio para que puedas mirarlas mientras la decisión aún está viva. Nada de magia. Menos rebuscar.

**Cambios:** fuera las palabras Tier 1 (aprovechar, robusta, de vanguardia, sin fisuras, accionable, impulsar), fuera el calco "de hoy" y el arranque "vamos a sumergirnos", fuera el contraste "no solo... sino", ritmo variado, un dato concreto (seis paneles, veinte minutos) y una opinión llana. Nota: aquí no hay raya que quitar; si el original la tuviera en un inciso correcto, se respeta.

## References

- `references/patterns.md` — the English rule library: tiered vocabulary, content/structure/style/communication patterns, the seam-pass procedure, context-profile matrix, severity tiers.
- `references/patterns-es.md` — the Spanish rule library: muletillas, calcos, structural tells specific to Spanish and to machine-translated prose.
- `references/false-positives.md` — what NOT to flag, and the signs of human writing to preserve.
- `references/voices.md` — the named voices (clear-thinker, casual-storyteller, sharp-opinionated, warm-professional) and the mirror profile.
- `references/protect-list.md` — the seam to a personal or project voice spec; the signatures the floor must not strip.
- `references/living-corpus.md` — dated tells caught in the wild, tagged by generative mechanism. The part that compounds.
- `references/ingestion.md` — the curation flow for memorializing a new tell.

## Lineage

Fused from three MIT-licensed skills — `blader/humanizer`, `lguz/humanize-writing`,
and `kjmagnan1s/anti-slop` — which themselves trace to Wikipedia's *Signs of AI
writing* (WikiProject AI Cleanup, CC BY-SA 4.0). Examples here are written fresh in
our own words. Full attribution in `PROVENANCE.md`.
