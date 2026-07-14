# Do not over-flag — false positives and human signals

The most expensive mistake this skill can make is not missing a tell. It is
gutting real human prose because it hit a pattern from the catalog. A clean,
professional, or simply idiosyncratic writer trips many of these patterns with zero
AI involvement. Read this before rewriting, and again before you decide a text is
"AI-written".

## The core rule: clusters, not isolated hits

One tell means nothing. A single em dash, one "however", one formal word, one
clipped sentence — none of these is evidence on its own. Look for **clusters**. An em
dash *plus* a tricolon *plus* "vibrant tapestry" *plus* a "Challenges and Future
Prospects" section is a confession. Any one of them alone is just writing.

When in doubt, prefer the lighter edit. Under-correcting leaves a faint tell;
over-correcting destroys the voice you were hired to protect.

## What is NOT a reliable tell (do not flag on its own)

- **Perfect grammar and consistent style.** Many writers are professionals or have been edited. Polish is not AI.
- **Formal or academic vocabulary.** AI overuses *specific* fancy words (delve, tapestry), not all fancy words. Do not flatten "ostensibly", "constituent", "no obstante" just because they sound brainy.
- **Mixed casual and formal register.** Often a person in a technical field, a young writer, or neurodivergent prose — not a chatbot.
- **"Bland" or "robotic" prose.** AI has *specific* tells. Generic dryness without them is just dry writing.
- **One em dash.** Many editors and journalists use them. Evidence only when paired with formulaic, sales-y rhythm.
- **A common transition in isolation.** "Additionally", "moreover", "por otro lado", "además" are AI-coded only when piled up. One "however" is not a tell.
- **Curly quotes alone.** macOS, Word, Google Docs, and most CMSes auto-curl by default. Only counts when stacked.
- **One short emphatic sentence.** Humans use clipped sentences to land a point. Flag staccato drama only when several short fragments run together to inflate the tone.
- **"Honestly" or "look" mid-sentence.** Ordinary in casual writing. The tell is the standalone theatrical opener, not the word.
- **Unsourced claims.** Most of the web is unsourced. It proves nothing.
- **Correct, complex formatting.** Templates and visual editors produce clean output with no AI.
- **A letter-style opening or closing.** Salutations and sign-offs predate ChatGPT by centuries.

## Signs of real human writing — preserve these

When you see these, lean toward leaving the prose alone. Over-editing destroys
exactly what makes a piece sound human.

- **Specific, unusual, hard-to-fabricate detail.** A real address. A weird quote. "The lawyer who used to work upstairs from my dentist." LLMs round specifics off; humans hoard them.
- **Mixed feelings and unresolved tension.** "I think this is mostly good, but it bothers me and I can't say why." LLMs default to clean takes.
- **Dated, era-bound references.** Slang, memes, in-jokes that map to a specific year and subculture. Models lag by a year or more.
- **First-person editorial choices the writer can defend.** If they can explain *why* they cut a word or made a call, that is a strong human signal.
- **Real variation in sentence length.** Human writing alternates short and long. AI trends toward an even, mid-length cadence.
- **Genuine asides, parentheticals, self-corrections.** "(I keep wanting to say 'almost' here, but it really was certain.)" Models rarely interrupt themselves.
- **A defensible strong opinion.** A position argued and backed, not both-sidesed.

## The self-reference escape hatch

Never flag a watched pattern when it appears inside a quotation, a title, a proper
name, or an example where the phrase is being *discussed* rather than used. That
includes this skill's own files, teaching material about AI writing, and any
"before" example. Only flag the author's own live prose.

## When the byline has a protect list

A protect list turns some of these judgment calls into hard rules: the author's
declared signatures are never stripped, even when they match a catalog pattern. On a
protected byline, load `protect-list.md` first and let it win. See that file for the
seam.
