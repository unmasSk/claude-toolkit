# Provenance

This plugin is a **fusion**, not a lift. The method and the rule catalogs were
rewritten in our own words and reorganized into one skill with a single voice, so
there is no byte-faithful, per-file correspondence to any single upstream. What was
taken is the *knowledge* — the pattern catalogs, the tier system, the three-pass
process, the protect-list seam, the modes, and the living-corpus idea — synthesized
from three MIT-licensed skills that themselves converge on Wikipedia's *Signs of AI
writing*.

The Spanish catalog (`references/patterns-es.md`) is original work: none of the
sources cover Spanish.

## Sources fused

| Source | URL | Fused-at commit | Commit date | What it contributed |
|---|---|---|---|---|
| `blader/humanizer` (MIT) | https://github.com/blader/humanizer | `1b48564898e999219882660237fde01bf4843a0f` | 2026-06-29 | The 33-pattern content catalog, the false-positives / human-signals brake, voice calibration, the draft→audit→final loop. |
| `lguz/humanize-writing` (MIT) | https://github.com/lguz/humanize-writing-skill | `4b7c37fa5148fd499e18498fcc91bb10ed801733` | 2026-03-12 | The three-pass process (structure → vocabulary → texture), the named voices, the pre-return quality checklist, LinkedIn rules. |
| `kjmagnan1s/anti-slop` (MIT) | https://github.com/kjmagnan1s/anti-slop | `115ab27443f548ec6ef61114308a854adce8b170` | 2026-06-23 | The three modes (rewrite/detect/ingest), the protect-list seam, the living corpus, transition iteration, context profiles, the 5-dimension scoring rubric. |

- Fusion date: 2026-07-14

`kjmagnan1s/anti-slop` is itself a consolidation of `avoid-ai-writing` (Conor
Bronsdon, MIT), an earlier `humanizer` lineage, and `stop-slop` (Hardik Pandya, MIT).
Those credits carry through — see `CREDITS.md`.

## Upstream lineage: Wikipedia

The pattern catalog traces to
[Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing),
maintained by WikiProject AI Cleanup. That material is licensed **CC BY-SA 4.0**. Our
examples are written fresh in our own words rather than copied; the underlying
observations originate there. See `CREDITS.md` for the share-alike note.

## Reconciling drift

When an upstream source updates, diff against a fresh clone at a newer commit and
re-fold any genuinely new patterns via the ingest flow (`references/ingestion.md`) —
do not re-lift files wholesale; this plugin does not track upstream file-for-file.
