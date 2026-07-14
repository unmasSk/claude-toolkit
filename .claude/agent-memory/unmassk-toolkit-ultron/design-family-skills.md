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

**Wiring source-repo scripts into a family skill**: when a family skill's
source material (e.g. claudedesignskills) ships `scripts/` + `assets/` per
sub-library, organize the copy by library under `scripts/<library>/` and
`assets/<library>/` (matching the family skill's own `references/<library>.md`
naming), then add a `## Scripts` section to the family `SKILL.md` — same
table shape already used by `design-flutter/SKILL.md` and the core
`unmassk-design/SKILL.md`: `| Script | Qué hace | Uso |`, with `Uso` always
`python3 ${CLAUDE_PLUGIN_ROOT}/skills/<family-skill>/scripts/<library>/<script>.py ...`.
Adapt every `Usage:` docstring line inside each copied script from the
source's `./script.py` convention to that same `${CLAUDE_PLUGIN_ROOT}` form.
Verify with `ast.parse()` on every copied file AND an actual functional
run of each script (interactive-mode scripts need a CLI-flag path to avoid
blocking on `input()`) — `ast.parse()` alone does not catch a broken
`.format()` template; see [[lessons]]'s claudedesignskills entry for a
real case this caught.

**Wiring scripts+assets from `.ref-repos/claudedesignskills` sources** (done
for `design-scroll`): organize `scripts/<library>/` and `assets/<library>/`
one subfolder per source skill (not flattened), so the relationship to the
source skill stays traceable. The source repo's per-skill `assets/README.md`
often documents `../scripts/x.py` style relative paths and sometimes
already-broken links (e.g. `../references/api_reference.md` pointing one
level short of the real `references/` sibling at skill root) -- when
copying these companion docs into the new nested-by-library layout, fix
the relative paths to the new depth (typically `../../scripts/<library>/x.py`
from `assets/<library>/README.md`, or `../../../references/<library>.md`
from a doubly-nested `assets/<library>/<subdir>/README.md`) rather than
carrying the breakage forward. Not every source skill actually has assets:
its SKILL.md may claim `assets/starter_x/` and `assets/examples/` exist
when only a `README.md` stub is really on disk (verify with `find`, don't
trust the source's own doc listing) -- these community skills use stdlib
Python only, so no dependency work is needed, but path-correctness has to
be checked file by file, not assumed.

**Scripts section wiring (design-motion precedent)**: when a family skill
copies generator/validator scripts from source repos into
`scripts/<tool>/`, mirror the core's `## Scripts` table format (script |
purpose | usage, `${CLAUDE_PLUGIN_ROOT}` in the usage column) plus an
"Assets" subsection for anything under `scripts/<tool>/assets/` (not loaded
into context, copied/referenced on demand). **Nesting-depth gotcha**: if a
source script resolves a sibling resource via
`Path(__file__).parent.parent / "schema"` (i.e. script lives directly in
`scripts/`), and the destination organizes scripts one level deeper by tool
(`scripts/<tool>/script.py`), the `.parent` chain needs one more `.parent`
to still land on the skill root — verify by running the script end-to-end
against a real input after copying, not just by re-deriving the path
arithmetic on paper (a schema-not-found bug here would be silent until
someone runs it). Same applies to any `requirements.txt`-worthy external
dependency the copied script pulls in (e.g. `jsonschema`) — document it in
scripts/requirements.txt and in the Scripts table's usage column, don't
just leave it in the script's docstring.

**Scripts wiring pattern** (used for `design-flutter/scripts/flutter_ui_audit.py`,
copied verbatim from a stdlib-only, self-contained source script): mirror
the core's `## Scripts` section (`unmassk-design/SKILL.md` — table of
script | qué hace | uso, with `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/<file>.py`
as the invocation path). Place the section right before the skill's
"Out of scope" section. No separate attribution edit needed if the
skill-level Attribution section already names the same source repo the
script came from. Verification gate for a copied script: `ast.parse()`
on the file plus a `--help` smoke run (catches missing shebang issues or
copy corruption; the file was stdlib-only so no dependency install step
was needed).
