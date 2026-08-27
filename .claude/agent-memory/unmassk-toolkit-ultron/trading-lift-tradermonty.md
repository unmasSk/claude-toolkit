---
name: trading-lift-tradermonty
description: Verbatim lift of 3 tradermonty/claude-trading-skills scripts into unmassk-trading; the header-insert recipe, the byte-identity proof, and the dangling trader-memory-core dependency the lift carries
metadata:
  type: project
---

# Lifting proven third-party scripts verbatim (unmassk-trading, 2026-08-27)

The owner asked for a LIFT, not a rewrite: copy MIT code that already works
rather than write new code. Wave 1 brought `position_sizer.py`,
`check_circuit_breaker.py` and `check_pre_trade_discipline.py` from
`tradermonty/claude-trading-skills` into
`unmassk-trading/skills/unmassk-trading/scripts/`.

**Why:** the owner does not trade and wants live-data + plain-talk advice he
executes by hand (D-071/D-072/M-131 in zone `trading`). Proven discipline
logic is worth more than freshly written logic; the EUR / 24-7-crypto
adaptation is a *separate, later* wave and deliberately did NOT happen in the
lift commit.

**How to apply — the mechanics that made "verbatim" provable:**

- Insert the attribution header *below* an existing shebang, *above* the
  module docstring. Two of the three had `#!/usr/bin/env python3`;
  `position_sizer.py` starts straight at its docstring.
- Prove verbatim-ness by stripping exactly the header lines back out and
  diffing against the source: `sed '1,5d' dst | diff - src` (no shebang) or
  `sed '2,6d' dst | diff - src` (shebang). "IDENTICAL" is the evidence; a
  line-count delta equal to the header size is not, on its own.
- Do the copy from a small Python script in the scratchpad, not by hand —
  it keeps the body untouched and prints before/after line counts in one go.

**The dependency the lift carries (the finding that matters):**
`check_pre_trade_discipline.py` dynamically loads a sibling skill's module via
`Path(__file__).resolve().parents[2] / "trader-memory-core" / "scripts" /
"thesis_store.py"` (importlib, inside `_load_thesis_store_module`). That skill
was not lifted, so the path never resolves here. It fails *loud*, not silent:
the exception is caught, becomes a warning, and every actionable candidate is
forced to REVIEW_REQUIRED. So the gate is safe but its "link report to thesis"
half is permanently dead until someone either lifts `trader-memory-core` or
cuts the call — a decision for the adaptation wave, not for the lift.

The lifted *tests* want the same module at a **different** place:
`scripts/thesis_store.py` (six of them load it directly and fail
FileNotFoundError). So dropping the file where the tests want it still leaves
production looking one directory tree away. Whoever closes this has to pick
one location and make both sides agree — that mismatch is invisible from
either side alone.

Also carried: a hard `import yaml` in two of the three (PyYAML, not stdlib —
same precedent as [[design-gate-linter]]), `ZoneInfo("America/New_York")` and
US-market-hours logic throughout, and CWD-relative default output/state paths
(`state/theses`, `reports/`, `state/journal/...`) that write wherever the
skill happens to be invoked from.

Related: [[implementation-patterns]], [[lessons]].

## Wave 2 (same day): thesis_store.py lifted, loader pointed at the sibling

The orchestrator chose to lift `trader-memory-core/scripts/thesis_store.py`
rather than cut the gate's thesis-link half, and authorised exactly one logic
line: the gate's loader now reads
`Path(__file__).resolve().parent / "thesis_store.py"` instead of
`parents[2] / "trader-memory-core" / "scripts" / ...`. Everything else stayed
byte-identical. Production and the tests now resolve to the same absolute
path — proved by loading the gate module and printing `mod.__file__`, not by
reading both call sites.

**Lifting one file dragged in two things nobody costed:** a third-party
`jsonschema` import (module-level, so it kills test *collection*, not just a
test), and a data file the module reaches for at
`Path(__file__).resolve().parent.parent / "schemas" / "thesis.schema.json"` —
i.e. a `schemas/` directory that is a *sibling of* `scripts/`, outside the
write scope of a scripts-only task. 191 tests fail on that one missing JSON
file. **Before agreeing a lift, grep the candidate for `__file__`-relative
data paths and non-stdlib imports** — a 3.5k-line module is not self-contained
just because it has no sibling `import`.

**Measuring "what happens once the missing file lands", without writing
outside scope:** `cp -R` the scripts dir into a scratchpad skill-shaped layout
(`fake_skill/scripts/` + `fake_skill/schemas/`), drop the data file in, run
pytest there. Copying a tests dir wholesale is not "opening a test file". Two
CLI tests will fail in that copy because they invoke the script by its real
repo path — that is the copy's artifact, not a finding; confirm it against the
same tests in the real location before reporting it as one.

## Wave 3: the schema file, and the number that closed it

`schemas/thesis.schema.json` copied verbatim with `cp` (identical sha256, no
header — a JSON data file cannot carry one, so its provenance lives only in
CREDITS.md). Suite in the real location, scratchpad venv: **371 passed, 0
failed**, matching the scratchpad-layout projection exactly, including the two
sizer CLI tests that could only ever fail in the copy.

**The lift needed four files and one line, not three files:** three scripts,
then `thesis_store.py`, then a JSON schema, then one loader path. Each step
was only visible after the previous one ran. `py_compile` was green at every
one of those steps and told us nothing — the module-level `import jsonschema`
and the `__file__`-relative schema path are both invisible to it. Only
executing the suite moved the failure one layer deeper each time.
