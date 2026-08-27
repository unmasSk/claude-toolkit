---
name: trading-suite-lift-tradermonty-notes
description: Lift of the tradermonty/claude-trading-skills test suites into unmassk-trading — conftest merge, the two path rewrites, the thesis_store.py blocker, and the US-Eastern/weekday calendar assumptions baked into the expectations
metadata:
  type: project
---

# Lift: tradermonty test suites → unmassk-trading (2026-08-27)

Source (read-only, MIT, `Copyright (c) 2026 TraderMonty`, LICENSE verified by reading it):
`tradermonty/claude-trading-skills`, skills `position-sizer`, `drawdown-circuit-breaker`,
`pre-trade-discipline-gate`. Destination: `unmassk-trading/skills/unmassk-trading/scripts/tests/`
(three source skills flattened into ONE skill).

## conftest collision — merged, not kept per-file

The three source `conftest.py` did the same job in two spellings (position-sizer used `os.path`
and also put the `tests/` dir on `sys.path`; the other two used `pathlib` and put only `scripts/`).
One destination directory can hold only one `conftest.py`, so it is the **union** — every suite
gets at least what it had. Per-file fixture modules were not needed: none of the three test files
imports anything from its conftest; they only rely on the `sys.path` side effect.

Source repo also ships a ROOT `conftest.py` that evicts same-named modules across 60+ skills
(`scorer`, `calculators`, `fmp_client`, `helpers`, `report_generator`) and sets
`--import-mode=importlib`. **Not needed here** and deliberately not lifted: with one skill there is
no cross-skill name collision, and the three test module basenames are unique in this repo.

## The only two edits beyond the attribution header

Both are pure location fixes, forced by the flattening:

1. `test_position_sizer.py` ×4 — `script = "skills/position-sizer/scripts/position_sizer.py"`
   → `"skills/unmassk-trading/scripts/position_sizer.py"`. The tests `cd` to
   `Path(__file__).resolve().parents[4]`, which in the new tree is the PLUGIN root
   (`unmassk-trading/`), so only the skill segment changes. Non-vacuous: two of the four assert
   `returncode == 0` **and** a stdout string, so a wrong path would fail, not pass silently.
2. `test_check_circuit_breaker.py` + `test_check_pre_trade_discipline.py` ×1 each —
   `parents[3] / "trader-memory-core" / "scripts" / "thesis_store.py"` → `parents[1] / "thesis_store.py"`.

## Blocker for Ultron: `thesis_store.py` is a fourth, unlisted production dependency

Two of the three suites load `trader-memory-core/scripts/thesis_store.py` (3479 lines) by file path
via `importlib.util.spec_from_file_location`. It is NOT one of the three scripts on the lift list,
so 6 tests fail with `FileNotFoundError` until someone lifts it into the skill's `scripts/`.
These tests are the producer↔consumer round-trip half of the suite: the real writer builds the
thesis file, the consumer under test reads it. Replacing them with a fixture would destroy exactly
the property they exist to prove — never do that.

## Expectations that are US-market / US-Eastern shaped (input to the adaptation wave)

The circuit breaker and the discipline gate compute "today", "this week" and "this month" on a
**US-Eastern day boundary with a Monday week start**. That is wrong for 24/7 crypto and must be
re-decided, never quietly re-baselined. The proof is in the assertions themselves, e.g.
`realized_pnl_wtd` excludes a Sunday 2026-06-28 event, and `active_until` lands on the next
Monday `2026-07-06T00:00:00`. The position sizer is currency-neutral arithmetic; only its field
NAMES (`dollar_risk`, `final_risk_dollars`) are USD-flavoured. No fee/commission/slippage
assumption exists anywhere in the three suites.

## Clock hygiene (checked, clean)

Both suites route through helpers that PIN `as_of` (`evaluate()` → `2026-07-03T12:00:00-04:00`,
`evaluate_state()` → `2026-07-02`). No test reads the wall clock, so none of them rot on a date
change. Do not "improve" this by removing the pins.

Two position-sizer CLI tests write to the real system `/tmp/position_sizer_test` via `--output-dir`
instead of pytest's `tmp_path`. Source behaviour, left verbatim; harmless but it is shared state.

---

# Update — wave 2 (2026-08-27): `test_thesis_store.py`

Lifted `skills/trader-memory-core/scripts/tests/test_thesis_store.py` (2294 lines, 197 tests).
**Zero changes beyond the 4-line header** — it imports `thesis_store` as a plain module and has no
path literal, no `parents[N]`, no `sys.path` line of its own, so the merged conftest already
covered it.

## The other five test files in that source directory were NOT lifted, and why

`trader-memory-core` ships six test files, ~6062 lines. Only one tests `thesis_store` alone:

| file | imports | verdict |
|---|---|---|
| `test_thesis_store.py` | `thesis_store` | LIFTED |
| `test_thesis_store_futures.py` (2278 lines) | `thesis_store` **and** `thesis_review` | held back — see below |
| `test_thesis_ingest.py` | `thesis_ingest` | script not lifted |
| `test_thesis_review.py` | `thesis_review` | script not lifted |
| `test_fmp_price_adapter.py` | `fmp_price_adapter` | script not lifted (paid FMP API) |
| `test_trader_memory_cli.py` | launcher by absolute path | script not lifted |

`test_thesis_store_futures.py` is the near-miss worth revisiting: 2278 lines of futures
LONG/SHORT round-trip P&L and silent-wrong prevention against `thesis_store`, blocked by exactly
**two lines** calling `thesis_review.generate_postmortem`. Lifting `thesis_review.py` buys that
whole file. Not my call, but the price is known.

## `thesis_store.py` needs two things that are not Python source

1. **`jsonschema`** (declared in the source `pyproject.toml` as `jsonschema>=4.25.1`) — absent from
   this machine's system python. Without it the module will not even import.
2. **`schemas/thesis.schema.json`** — an ASSET, not a script. `thesis_store._SCHEMA_PATH` resolves
   it as `<skill>/schemas/thesis.schema.json`. It lives at
   `skills/trader-memory-core/schemas/thesis.schema.json` in the source.

Every one of the 191 failures in the whole tree traced to #2, one single missing file. When a lift
list says "three scripts", the real unit is the script PLUS the data files it opens at runtime —
check for `open(` on a path built from `__file__` before declaring a lift complete.

## Verification technique that paid off here

To get the target green number without waiting on the repo, run the ORIGINAL suite inside its own
source repo in a scratchpad venv, with `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider` so
the read-only source tree stays byte-clean: **197 passed**. My copy collects exactly 197 too, so
collection parity is proven even while the schema asset is still missing. Never claim a lift is
faithful on a suite that has not collected.

## Market/currency scan of the new suite (clean, unlike wave 1)

No US-Eastern boundary, no NYSE/weekday/holiday logic. 81 timestamps are `+00:00` and 2 are
`+09:00` (the two `test_cross_timezone_*` tests, which PROVE offset handling rather than assume a
zone). `holding_days` is plain calendar-day arithmetic (`2026-03-01`→`2026-04-01` = 31), which
suits 24/7 crypto as-is. Currency appears only in field names (`pnl_dollars`, `risk_dollars`); the
arithmetic is `(exit - entry) * shares`, currency-neutral. No fee/commission/slippage anywhere.

Filesystem hygiene: all 575 path expressions derive from `tmp_path`. Nothing writes to a shared
system path — better than the two position-sizer CLI tests noted above.

---

# Close-out — the lift is green (2026-08-27)

**371 passed, 0 failed, 0 errors**, three consecutive runs, in a scratchpad venv holding exactly
what `unmassk-trading/requirements.txt` declares (`PyYAML>=6.0`, `jsonschema>=4.25.1`). Per file:
sizer 41, circuit breaker 74, pre-trade gate 59, thesis_store 197. Each number equals its source
baseline, so nothing was lost in transit and nothing passes for a new reason.

The single missing `schemas/thesis.schema.json` was indeed the whole of the 191 failures — one
asset, 191 red tests. Landed byte-identical (md5 `7de830dd...` on both sides).

## The scope line, recorded so nobody re-opens it

Final lift = `position_sizer.py`, `check_circuit_breaker.py`, `check_pre_trade_discipline.py`,
`thesis_store.py`, `schemas/thesis.schema.json`, and their tests. **Nothing else from that repo.**
`thesis_review.py` and its 2278-line `test_thesis_store_futures.py` were refused on purpose: the
plugin came for the discipline layer, `thesis_store` is in only because the gate opens it, and this
project intends to replace that store with its own git-memory anyway. Chasing an import chain one
more hop is how a lift quietly doubles. I raised the question; the answer was no; it stays no.

## Cold/warm proof technique for a test that writes outside tmp_path

The two position-sizer CLI tests write to the shared `/tmp/position_sizer_test` (wave-1 finding,
left alone). To show they are not secretly depending on state left by an earlier run, I MOVED the
directory aside — never deleted it — re-ran cold (41 passed, the script recreates the dir), then
moved the 36 files back. Moving aside and restoring gives the same evidence as deleting and costs
nothing if the guess about who owns the directory is wrong.
