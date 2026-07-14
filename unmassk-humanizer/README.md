# unmassk-humanizer

Make written text stop reading as AI — in **English and Spanish** — without
flattening the author's own voice.

One skill, three modes, a bilingual pattern catalog, and a living corpus that keeps
it current as the tells change.

## What it does

Give it any prose and it removes the machine's fingerprints: the metronome rhythm
where every sentence is the same length, the "not X, but Y" reversals, the em
dashes, the forced groups of three, the `delve`/`tapestry`/`vibrant` vocabulary,
the "let's dive in" runways, the tidy bow on every paragraph. What it does **not**
do is sand the writing down into a new kind of uniform, voiceless prose — that reads
as AI for a different reason.

## Three modes

- **rewrite** (default) — returns a clean version plus a short summary of what changed.
- **detect** — flags only, grouped by severity (P0/P1/P2). No rewriting. For auditing published or third-party text.
- **ingest** — memorializes a new tell into a dated, mechanism-tagged corpus, so the skill doesn't go stale as models change.

## What makes it different

- **It's bilingual from v1.** The Spanish catalog is original work: muletillas,
  calcos del inglés, and machine-translation tells that do not map one-to-one from
  English. No source skill covers Spanish. This is the core reason the plugin exists.
- **It doesn't over-flag.** A false-positives guard keeps it from gutting good human
  prose over one formal word or a single em dash. It looks for *clusters* of tells,
  not isolated signals.
- **It can protect your own voice.** You can list your real writing quirks (your
  tics, your deliberate fragments, your closers) in a "protect list" so the de-slop
  pass never strips them, and log new AI tells over time in a "living corpus" so the
  skill doesn't go stale. Both ship **empty on purpose** — they are yours to fill as
  you use it, not pre-seeded with invented content. Until you fill them, the skill
  applies its general rules at full strength.

## How to use it

Just ask, in either language:

- "Humanize this blog post." / "Humaniza este post."
- "Does this sound like AI? Flag what's wrong." / "¿Suena a IA? Márcame qué falla."
- "Rewrite this in a sharp, opinionated voice."
- "Here's a sample of my writing — match my voice."
- Paste text marked `slop:` to teach it a new tell.

## When NOT to use it

Code, API docs, READMEs, commit messages, changelogs, or any text where a formal,
neutral register is the correct human voice. There, plain *is* human.

## Structure

```
unmassk-humanizer/
  skills/humanizer/
    SKILL.md                         the fused method
    references/
      patterns.md                    English rule library
      patterns-es.md                 Spanish rule library (original)
      false-positives.md             what NOT to flag + human signals
      voices.md                      named voices + mirror profile
      protect-list.md                the voice-protection seam (template)
      living-corpus.md               dated tells, tagged by mechanism
      ingestion.md                   the curation flow
```

## Credits

Fused from three MIT-licensed skills — [blader/humanizer](https://github.com/blader/humanizer),
[lguz/humanize-writing](https://github.com/lguz/humanize-writing-skill), and
[kjmagnan1s/anti-slop](https://github.com/kjmagnan1s/anti-slop) — whose pattern
lineage traces to [Wikipedia's Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
(CC BY-SA 4.0). Full attribution in [CREDITS.md](CREDITS.md) and [PROVENANCE.md](PROVENANCE.md).

MIT licensed. Part of the [unmassk toolkit](https://github.com/unmasSk/claude-toolkit).
