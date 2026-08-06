---
name: scaffold-py-scaffolding-bugs
description: unmassk-scaffolding/scripts/scaffold.py fixes (2026-08-06) -- TOML/JS escaping, silent-noop ORM/CSS enum values, CLI --language reachability, absolute-name path escape, and a test-file off-by-one found while implementing
metadata:
  type: project
---

Fixed 4 bug classes in `unmassk-toolkit/skills/unmassk-scaffolding/scripts/scaffold.py`
(3541 lines, zero prior gitmem zones) against Dante's red contract
`unmassk-toolkit/tests/test_scaffold_bug_contracts.py`. 13/14 green; 1 stayed
red for a reason that is NOT scaffold.py's fault (see below) -- reported to
orchestrator per Ultron's "never touch a test" rule, not fixed.

**Escaping (Bug 1):** added two module-level helpers right after the
`encoding_guard` import block (before `class Language`): `_toml_escape(s)`
(hand-rolled -- backslash/quote/control-char escaping per the TOML basic-
string spec, deliberately NOT reusing `json.dumps` because Python's
`ensure_ascii=True` default encodes astral characters as UTF-16 surrogate
PAIRS of `\uXXXX`, and TOML's `\uXXXX` must be one full Unicode scalar value
-- a valid JS/JSON surrogate pair is an INVALID TOML escape) and
`_js_string_literal(s)` (`return json.dumps(s)` -- this direction IS safe to
reuse because JS strings are UTF-16-based, so JSON's surrogate-pair encoding
of astral chars is exactly correct JS). Applied at all 4 named sites
(`_fastapi_pyproject`, `_python_pyproject`, `_python_cli_pyproject` incl. the
`[project.scripts]` bare key which needed quoting too since it's the same
`config.name`, `_nextjs_layout`'s title+description). Left `config.version`/
`python_version` unescaped (not string-literal-quoted in those templates,
not named in the finding). [[implementation-patterns]]

**Silent no-op ORM/CSS enum values (Bug 2):** the contract test forces real
differentiated output (not rejection) for `ORM.DRIZZLE` on `express` and
`CSSFramework.CSS_MODULES` on `react` -- rejecting would raise inside
`create_project()` where the test expects success. Decision: implement
real (if minimal) support rather than reject, and extend consistently to
the other enum values named in the bug text so no orphaned value remains:
`ORM.DRIZZLE`+`ORM.MONGOOSE` in `_create_express` (real deps: drizzle-orm/
drizzle-kit, mongoose), `ORM.TORTOISE` in `_create_fastapi` (tortoise-orm
requirement), and `CSSFramework.SCSS`/`STYLED_COMPONENTS`/`EMOTION` in
`_create_react` via real deps, `CSS_MODULES` via a genuinely new artifact
(`src/components/ui/Example.module.css`, new `_css_module_example()`
template) since CSS Modules needs no dependency under Vite -- without an
artifact its output would stay byte-identical to `NONE`. Scope was
deliberately bounded to what the finding named ("en react" for CSS) --
other frameworks (vue/svelte/nuxt/html) still only check `== TAILWIND` and
were left untouched, out of the stated finding.

**CLI --language reachability (Bug 3):** `main()`'s python-forcing list
(`["python","fastapi","django","flask"]`) never included `"cli"`, and there
was no `--language` flag at all, so `_create_python_cli` (a real, working
generator `_create_cli` already branches to) was unreachable from any real
argv. Added `--language {typescript,javascript,python}` and made it take
priority over `--typescript`/`--javascript` in the language-resolution
block, BEFORE the existing forced-python-for-4-types override (preserved
verbatim so fastapi/django/flask/python's forced behavior is untouched).

**Absolute/traversal project name (Bug 4):** `Path(base) / name` silently
discards `base` when `name` is absolute (pathlib semantics, not a bug in
pathlib). Fix rejects `name` containing `/` or `\` or equal to `.`/`..`
before constructing `project_path` -- covers the tested absolute case AND
the same-class relative-traversal case (`../x`) in one check, since a
project name should never be anything but a single leaf directory-name
component. Not framed as attacker defense (CLAUDE.md: no external-attacker
threat model here) -- framed as upstream template/caller error the
scaffolder must not let through silently.

**Test-file bug found, NOT fixed (reported instead):**
`TestDescriptionApostropheBreaksNextjsLayout` (bug-1's second contract)
still failed after the real fix, for an unrelated reason: its own
extraction slice `raw.index("};", brace_start) + 1` computes the index of
the `;` character but then Python's slice-end-exclusive semantics drop
that same `;` from `object_literal_src` -- verified by hand with the real
generated file (`repr()` of the slice ends in `...}` with the `;` gone).
The test then concatenates `f"{object_literal_src} process.stdout..."` with
only a single space (no newline, no semicolon) between them, which Node
correctly rejects via ASI rules (ASI only fires on a genuine line-terminator
boundary or at a `}` token, neither of which applies to a same-line space
before an identifier) -- confirmed this fails regardless of what valid
`layout.tsx` scaffold.py emits, i.e. it is not fixable from the
production-file side. This is `[[lessons]]`-worthy as a pattern: when a
red test survives an otherwise-complete fix, hand-verify the test's own
extraction/assertion logic against the REAL generated artifact before
assuming the production code is still wrong. Confirmed by the orchestrator
independently (generated a project with an apostrophe AND double quotes
together, `node --check` accepted it) -- test bug confirmed, routed to
Dante.

**Follow-up (same session): reintroduced bug 3's class on the new ORM code.**
Implementing `ORM.MONGOOSE`/`ORM.TORTOISE` fixed the "no creator ever
branches on it" half of bug 2, but `--orm`'s argparse `choices` list was
never updated to include them -- new working code, unreachable from any
real argv, exactly bug 3's shape. Also found (correcting the orchestrator's
message, which assumed it needed a decision): `ORM.SEQUELIZE` was already
implemented in `_create_express` (pre-existing, line ~842, not new code) --
it just wasn't in `choices` either. Fix: added `"sequelize"`, `"tortoise"`,
`"mongoose"` to `--orm`'s choices (no decision needed for SEQUELIZE, since
"implement or drop" doesn't apply to something already implemented).
Verified end-to-end via real subprocess CLI calls (`--orm mongoose` on
express, `--orm tortoise` on fastapi, `--orm sequelize` on express) --
rc=0, real dependency present in the generated manifest for all three.
**Lesson: after wiring a new enum value into a creator, always re-check the
CLI's `choices=[...]` list for that same flag in the same pass -- the two
are easy to drift apart, and the drift is invisible to any test that only
constructs `ProjectConfig` directly (bypassing argparse), which is exactly
what this contract test suite does.** `--css-framework` as a CLI flag still
does not exist at all (only boolean `--tailwind`) -- confirmed via grep, not
added (out of the explicit ask, which was investigate-and-report for CSS,
fix-only for ORM). See MEMORY.md/session report for the full reachability
table across ORM/CSSFramework/Database.

**Follow-up 2: `--css-framework` flag added, with fail-loud validation --
NOT in `create_project()`.** The orchestrator decided to add the flag and
reject (with a clear message) any `--css-framework` value the chosen
project type doesn't implement. Critical placement lesson: I first
considered validating inside `ProjectScaffolder.create_project()` (the
same central place bug 4's name-check lives) since that's where every
caller funnels through -- but `ProjectConfig.css_framework` DEFAULTS to
`CSSFramework.TAILWIND` at the dataclass level (line ~140), for every
project type including backend/library ones that never look at it. Contract
tests construct `ProjectConfig(project_type="express"/"fastapi"/"cli"/...)`
WITHOUT specifying css_framework in ~5 of the 14 tests, relying on that
default. Validating in `create_project()` would have raised on every one of
them -- silently turning 5 currently-green tests red without touching the
test file, which is exactly what "no toques ningún test" is meant to
prevent even indirectly. Moved the validation into `main()` instead, gated
on the CLI args (`args.css_framework`/`args.tailwind`) rather than the
config's resolved value -- fires only when a human explicitly asked via a
flag, never for a default leaking through a direct `ProjectConfig(...)`
call. **Lesson: before adding validation at a "central" dispatch point,
check what every existing caller relies on that point NOT enforcing --
a shared default value is a classic hazard.**

Also corrected the orchestrator's stated premise ("tailwind lo entienden
todos") with evidence before implementing: `_create_angular` never reads
`config.css_framework` at all (confirmed by reading the full function body),
and neither does any backend/library creator (express, fastapi, django,
flask, python, typescript, cli, electron, monorepo). Built
`_CSS_FRAMEWORK_SUPPORTED_TYPES` (new module-level constant, right before
`main()`) from the real per-creator grep, not the assumption -- so
`angular --css-framework tailwind` now correctly errors too, verified live
via subprocess (`rc=1`, message lists the 6 real types: html, nextjs, nuxt,
react, svelte, vue). Also verified the legacy `--tailwind` boolean routes
through the same validation (`fastapi --tailwind` now errors instead of
silently no-op'ing) since both flags resolve to the same `css_framework`
variable before the check.
