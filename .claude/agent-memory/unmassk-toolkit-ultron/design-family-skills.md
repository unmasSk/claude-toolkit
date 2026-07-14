---
name: design-family-skills
description: Pattern for building unmassk-design "family" skills (design-scroll, design-motion, etc.) that synthesize multiple community sub-skills into one condensed, attributed skill
metadata:
  type: implementation-patterns
---

Structure used for `unmassk-design/skills/design-scroll/` (multi-branch
design plugin, one branch per family): `SKILL.md` at skill root with a
**decision table** ("the ask" -> library -> why -> reference file) instead
of prose, plus `references/<library>.md` per source library, each condensed
independently and rewritten in our voice (not pasted verbatim from the
source skill). Frontmatter follows `unmassk-design/skills/unmassk-design/SKILL.md`'s
convention: `description: >` block starting with `Use when the user asks to
"..."`, ending with an explicit `Use when NOT` clause plus an attribution
sentence naming the source repo/author/license.

**Condensing rule that worked**: for each source reference file (which can
run 500-1200 lines of exhaustive API docs), keep only: setup/install, the
2-3 concepts that actually change behavior, 4-6 patterns worth remembering
(with minimal snippets, not the full copy-paste block), one integration
section (how this library pairs with siblings in the same family), and a
"pitfalls that actually bite" list distilled from the source's much longer
pitfalls section. Cut anything that's just an API reference table restating
option names/defaults — that's what the official library docs are for; this
skill is about judgment (which one, when to escalate) not API completeness.

**Verification gate for this pattern**: YAML frontmatter must parse
(`python -c "import yaml,re; ..."` against the `---...---` block) and every
reference path named in the SKILL.md routing/decision table must exist on
disk. Both are cheap and catch the two failure modes that actually occur
(malformed frontmatter block, typo'd reference filename).

**Parallel-agent constraint**: when multiple agents build sibling family
skills at once (design-scroll, design-motion, design-3d, ...), each works
only inside its own `unmassk-design/skills/design-<family>/` directory —
new directory per agent, never touching `skills/unmassk-design/` (the core)
or another agent's family directory. See the toolkit-wide antipattern memo
on git stash/reset during parallel work — the same "stay in your own
pathspec" discipline applies to file scope here even without git.
