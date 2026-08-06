---
name: scaffold-py-red-contract-notes
description: scaffold.py (unmassk-scaffolding, zero prior tests) 4-bug RED contract, 2026-08-06 -- golden-test scope was cancelled mid-task in favor of self-harm-only regression contracts
metadata:
  type: project
---

**File**: `unmassk-toolkit/skills/unmassk-scaffolding/scripts/scaffold.py` (3541
lines, no `.py` production changes made -- test-only task).
**Tests**: `unmassk-toolkit/tests/test_scaffold_bug_contracts.py` (14 tests: 8
RED contracts for 4 Cerberus-confirmed bugs, 6 GREEN baseline-sanity tests).
Run scoped to this one file only, per instruction -- never ran the full
`unmassk-toolkit/tests` suite in this session.

**Scope reversal mid-task, orchestrator-driven (2026-08-06):** task started as
"19 golden master tests" (full-file snapshot, tree+content, pre-refactor
safety net for later splitting scaffold.py into smaller files) -- Cerberus's
own design, 17 dispatch-table entries + `_create_python_cli` direct +
all-off. Before any golden fixture was written to disk, the owner reversed
the whole plan in-flight: **no split is happening, so no refactor net is
needed.** Replaced with 4 RED contract tests (Cerberus read the whole file
and found real self-harm bugs) + a small non-red validity net. Lesson: even
after fully reverse-engineering a dispatch table / config surface for one
test strategy (see the branch-mapping notes below, still valid and reused),
be ready to pivot the *test type* entirely without re-deriving the mapping
work -- the file-structure investigation (dispatch table, `main()`'s
language-forcing list, per-creator `config.*` branch grep) was 100% reused
for the new RED tests.

**The 4 bugs, each with the file:line Cerberus named and the real-parser
proof used:**
1. **Raw string interpolation breaks hand-written TOML/JS, silently.**
   `_fastapi_pyproject` (~2294), `_python_pyproject` (~2727),
   `_python_cli_pyproject` (~2789) f-string `config.description` straight
   into a TOML `description = "..."` line with no escaping -- a `"` in the
   description breaks the TOML syntax, script still prints "Created", exits
   0. `_nextjs_layout` (~1925) has the same bug in a single-quoted JS string
   (`description: '...'`) -- an apostrophe breaks it.
   Proof used: real `tomllib.loads()` on the actual written file (stdlib,
   the same parser pip/uv/build use) for the 3 TOML sites: raises
   `tomllib.TOMLDecodeError: Expected newline or end of document after a
   statement (at line 4, column 25)`. For the JS site: real Node
   (`shutil.which("node")`, skip if absent) on the extracted
   `metadata = {...}` object-literal substring only (the surrounding
   `layout.tsx` is TSX/JSX, unparseable by plain Node regardless of this
   bug, so extraction isolates exactly the site under test) -- Node raises
   `SyntaxError: Unexpected identifier 's'` on `Handles the user's edge
   cases`. **Extraction technique**: the template is fixed-shape
   (`export const metadata: Metadata = {` ... `title: '...'` ...
   `description: '...',` ... `};`) and the description never contains a
   literal newline, so `raw.index("export const metadata...")` +
   `raw.index("{", ...)` + `raw.index("};", brace_start)` reliably finds the
   same boundary even when the quote inside already broke JS syntax --
   confirmed empirically, not assumed.
2. **CLI-advertised options are silent no-ops.** `--orm` accepts `drizzle`
   (choices at ~3473) but no creator ever branches on `ORM.DRIZZLE`
   anywhere in the file (grepped `config.orm ==` -- only PRISMA/TYPEORM/
   SEQUELIZE/SQLALCHEMY/SQLMODEL appear). Same for `CSSFramework.CSS_MODULES
   /STYLED_COMPONENTS/EMOTION/SCSS` (only `== CSSFramework.TAILWIND` and
   `!= CSSFramework.NONE` ever checked). Proof: two REAL runs of the script
   (express+DRIZZLE vs express+NONE; react+CSS_MODULES vs react+NONE),
   **same project name, different `base_path`** so `package.json`'s `name`
   field doesn't contaminate the diff -- confirmed byte-identical tree+content
   today. Cerberus's own wording deferred the *fix* shape to Ultron ("puede
   ser implementarlo o rechazarlo") but the *test* wording was literal
   comparison-only (no branching) -- kept the assertion as a plain `!=`, no
   if/else, per this agent's own "no conditional logic in tests" rule.
3. **`_create_python_cli` unreachable from the real CLI.** `_create_cli`
   (~1161) branches on `config.language`, and the Python generator (~1168)
   works fine when reached directly. But `main()` (~3492) only forces
   `language = PYTHON` for `["python","fastapi","django","flask"]` --
   `"cli"` excluded -- and there is **no `--language` flag at all** in
   today's argparse. Proof: real subprocess `scaffold.py cli lang-check
   --language python` → argparse itself rejects it, `rc=2`, stderr
   `unrecognized arguments: --language python`, nothing created. This is the
   literal contract Cerberus asked for ("--type cli --language python...
   debe producir un CLI de Python") even though `--language` doesn't exist
   yet -- the RED is argparse's own rejection, not a semantic mismatch.
4. **Absolute `config.name` escapes `base_path`.** `create_project()` line
   ~125: `self.base_path / config.name` -- pathlib discards `base_path`
   entirely when `config.name` is absolute (documented pathlib behavior).
   Proof: real `ProjectScaffolder(base_path=<intended tmp dir>)
   .create_project(ProjectConfig(name=<absolute path under a SIBLING tmp
   dir>, ...))` today raises nothing and genuinely writes files at the
   absolute path -- `pytest.raises(Exception)` fails with "DID NOT RAISE",
   confirmed by also asserting the sibling dir doesn't exist beforehand.
   Used bare `Exception` (not a specific subclass) deliberately -- the
   contract is "reject with a clear error", type unspecified, and pinning a
   specific exception class would have constrained Ultron's implementation
   choice more than Cerberus's finding warranted.

**Baseline (non-RED) validity net, deliberately not exhaustive across all 17
dispatch entries:** `package.json` is always built via a plain Python dict +
real `json.dump` (`_create_package_json`/`_write_json`, ~1329/1335) -- that
code path structurally cannot emit invalid JSON regardless of which creator
calls it, so one creator per JSON-producing *shape* (react=frontend,
express=backend, typescript=lib) is enough to prove the writer itself is
sound; the interesting bug (raw f-string interpolation) simply doesn't apply
to this path. `pyproject.toml` is the opposite (hand-written f-string, see
bug 1) -- covering exactly the 3 sites bug 1 touches, with a SAFE (no-quote)
description this time, confirms the happy path is otherwise sound and
isolates "the bug is the quoting, not the TOML shape in general." 6 tests
total, all GREEN today.

**Config-surface mapping (reusable if a future task returns to golden/
snapshot testing of this file):** dispatch table is exactly 17 entries at
`create_project()` line ~131 (html, react, nextjs, vue, nuxt, svelte,
angular, express, nestjs, fastapi, django, flask, python, typescript, cli,
electron, monorepo) -- NOT the 70 the skill description advertises.
`ProjectConfig` dataclass defaults are already "mostly on"
(`typescript_strict/eslint/prettier/testing/ruff/mypy/pytest` all default
`True`, `css_framework` defaults `TAILWIND`) -- only `docker`/
`github_actions` default `False` and `language` defaults `TYPESCRIPT`.
`main()`'s CLI parser has a real bug of its own (out of today's 4, not
tested): `--eslint/--prettier/--testing/--ruff/--mypy/--pytest` are all
`action="store_true", default=True"` -- meaning the flag can never turn
these OFF via the CLI, only building `ProjectConfig` directly in Python can.
`--drf` for Django is not a CLI flag either -- DRF only activates via
`"drf" in config.features` (~1010), a comma-separated `--features` string.
`_create_common_files` (~1434) is the single choke point for `github_actions`
(~1635) and `docker` (~1639, **and only when `not python`** -- Python
creators never get a Dockerfile from this path even with `docker=True`).

See also: [unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md).
