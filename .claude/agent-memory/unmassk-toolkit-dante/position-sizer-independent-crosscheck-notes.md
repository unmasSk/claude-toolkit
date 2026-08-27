---
name: position-sizer-independent-crosscheck-notes
description: Independent hand-computed cross-check of unmassk-trading's position_sizer.py sizing arithmetic (14 cases, all agreed) — the Fraction-first technique, the two-mutant non-vacuity proof, and the one real finding (size is Decimal, the money display is float, so exact half-cent ties flip)
metadata:
  type: project
---

# Cross-check: `position_sizer.py` arithmetic (unmassk-trading, 2026-08-27)

File written: `unmassk-trading/skills/unmassk-trading/scripts/tests/test_position_sizer_crosscheck.py`,
44 tests. The lifted `test_position_sizer.py` was NOT touched.

## Why a second file next to 100% branch coverage — the argument, reusable

Coverage lifted from the same repository as the code proves the formula was *implemented*, never
that it is *correct*: every expected value in it was produced by the thing under test. That is the
exact shape this project's rule ("a test enters only if it compares two things written separately")
exists to catch, and coverage percentage is no defence against it. When a suite arrives with the
code, assume the whole suite is one-sided until an independent computation says otherwise.

## The technique: exact rationals FIRST, implementation SECOND

1. Read only the DEFINITION (`references/risk-and-sizing.md`), never the implementation's arithmetic.
2. Compute every case in a scratchpad script with `fractions.Fraction` — exact, no float noise, and
   a genuinely separate arithmetic path from the code's `Decimal`. Print, for each case, both the
   floor result and the round-to-nearest result: the cases where they DIFFER are the only ones that
   can prove a rounding direction, and picking them by eye afterwards is how that test ends up vacuous.
3. Only then read the code — for the flag names and the output format, which are contract, not
   arithmetic. Write the literals from step 2, never from a first run of the script.

The hand figures went in before any run, and all 14 agreed with the code first try. Both examples
this plugin's documentation quotes (`0.00110692` / `74.74` / `5.00`, and `0.00986193` / `665.85`)
reproduce from the definition alone, so the docs are pinned by arithmetic now, not by the code's
own output.

## Non-vacuity proof: two mutants, in a scratchpad COPY of the script

Per the standing ban (see [mutation-check-collision-incident-ids](mutation-check-collision-incident-ids.md)),
the production file is never edited: `cp` the script and the test into the session scratchpad, mutate
the copy, run pytest against the copy.

| mutant (in the copy) | killed |
|---|---|
| `ROUND_FLOOR` → `ROUND_HALF_UP` (both the fractional and the whole-unit path) | 17 / 44 |
| risk budget `/ Decimal(100)` → `/ Decimal(99)` (a 1% error) | 26 / 44 |

A green cross-check is worth nothing without this: "all my hand figures matched" and "my test file
asserts nothing" look identical from the outside.

## Finding, reported not tested: size is Decimal, the money display is float

`calculate_position()` computes the size in `Decimal` (exact) but then does
`round(final_shares * params.entry_price, 2)` and `final_shares * (entry - stop)` in binary float.
On an exact half-cent tie the displayed cent therefore depends on the binary representation and can
land either side. Verified through the real CLI:

    --account-size 247554.93 --entry 84894.5 --stop 53353.18 --risk-pct 2.0 --fractional --share-precision 2
    → Position: $12,734.17     while 0.15 × 84894.5 = 12734.175 exactly

~0.1% of 200k randomised plausible inputs differ by one cent, in both directions. **Deliberately not
pinned by a test:** a test there would freeze arbitrary tie-breaking behaviour as if it were the
contract. The size — the number the user acts on — is never affected.

## Two things about this script worth knowing before testing it again

- `--share-precision` is silently ignored without `--fractional` (the whole-unit path is `int()`),
  and `--share-precision` outside 0–8 is a `ValueError` → exit 1.
- The lifted CLI tests write to the shared system `/tmp/position_sizer_test`. The cross-check does
  not: it invokes the script by absolute path with `cwd=tmp_path` and `--output-dir` under
  `tmp_path`, so the plugin suite can run from any cwd and nothing lands in the repo. Use that shape
  for any new CLI test here.
