# Credits

`unmassk-trading` does not reimplement what already exists and is already tested. Its
discipline layer is **lifted verbatim** from open-source work, and its execution
substrate is Kraken's own CLI. What is original here is the beginner layer and the
plumbing that ties the pieces to this toolkit's memory.

## Code lifted verbatim (MIT)

From **[tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills)**
— MIT, Copyright (c) 2026 TraderMonty — lifted on 2026-08-27:

| File here | Source in that repo | Lines |
|---|---|---|
| `skills/unmassk-trading/scripts/position_sizer.py` | `skills/position-sizer/scripts/position_sizer.py` | 535 |
| `skills/unmassk-trading/scripts/check_circuit_breaker.py` | `skills/drawdown-circuit-breaker/scripts/check_circuit_breaker.py` | 840 |
| `skills/unmassk-trading/scripts/check_pre_trade_discipline.py` | `skills/pre-trade-discipline-gate/scripts/check_pre_trade_discipline.py` | 718 |
| `skills/unmassk-trading/scripts/thesis_store.py` | `skills/trader-memory-core/scripts/thesis_store.py` | 3479 |
| `skills/unmassk-trading/schemas/thesis.schema.json` | `skills/trader-memory-core/schemas/thesis.schema.json` | — |
| `skills/unmassk-trading/scripts/tests/*` | the matching `scripts/tests/` of each skill above | ~5000 |

Each Python file carries an attribution header; the JSON schema cannot carry a comment,
which is why its provenance is recorded here. **The bodies are byte-identical to source**,
verified by stripping the header and diffing.

**The one line of logic changed on the way in:** `check_pre_trade_discipline.py` loaded
`thesis_store.py` from `parents[2]/trader-memory-core/scripts/`, which does not exist in
this plugin's flat layout. It now loads the sibling file. The alternative — leaving it —
would have left the gate silently unable to link a thesis while every other test passed.

**`thesis_store.py` and `thesis.schema.json` are carried as a dependency, not as a
feature.** No document in this plugin routes to them: they are here because
`check_pre_trade_discipline.py` imports the store when a candidate carries a `thesis_id`,
and they are what pulls `jsonschema` into `requirements.txt`. The record this plugin
actually keeps lives in the toolkit's git-memory. Replacing that import with git-memory
notes, and dropping both files, is phase 3.

Nothing else from that repository was taken. `thesis_review.py`, `thesis_ingest.py`, the
FMP price adapter and their suites were deliberately left behind: following the import
chain further buys features nobody asked for, in a store this plugin intends to replace
with the toolkit's own git-memory.

## The execution substrate

**[krakenfx/kraken-cli](https://github.com/krakenfx/kraken-cli)** — MIT, Kraken's own
single-binary CLI. This plugin drives it rather than calling REST directly, because it
already ships the four things that make conversational trading safe: a local paper
account, an order validator (`--validate`), a dead man's switch (`order cancel-after`),
and a machine-readable catalogue marking which of its commands are dangerous. Its
`kraken-autonomy-levels` skill supplied the permission ladder this plugin follows —
read-only, then paper, then human-confirmed execution — and `kraken-shared` the discipline
of probing capability instead of trusting a version string.

## Work that informed the design without being copied

- **[gauss314/skills](https://github.com/gauss314/skills)** (MIT) — per-vendor endpoint
  manuals; the standard for documenting a data source properly.
- **[EodHistoricalData/eodhd-claude-skills](https://github.com/EodHistoricalData/eodhd-claude-skills)**
  (MIT) — the shape a vendor-backed Claude Code plugin should have.
- **[agiprolabs/claude-trading-skills](https://github.com/agiprolabs/claude-trading-skills)**
  (MIT) — a crypto-flavoured survey of the same territory.

## What is original here

The **beginner mode**, because it exists nowhere: a sweep of 291 published trading skills
across six repositories found none that assesses what a beginner knows or teaches them.
The knowledge assessment, the teaching order, the first-week programme and the promotion
gate were written for this plugin.

The **two-source price check with a stamped age** is also original — nothing surveyed
cross-checks a quote against a second venue or refuses to advise on a stale one.

And the **record lives in the toolkit's git-memory**, not in a parallel journal file:
where the work above keeps trades in YAML or JSONL, this plugin has one memory to keep
honest instead of two.

## Data sources

- **Kraken** — <https://docs.kraken.com/api/> — public market data and execution.
- **Binance public market data** — <https://data-api.binance.vision> — keyless second
  opinion for the price cross-check. Market data only; nothing is executed there.

Kraken and Binance are cited for their own published documentation; neither endorses this
plugin.

## Dependencies

`PyYAML` and `jsonschema` arrive with the lifted code and are declared in
`requirements.txt`. Everything else is the standard library.
