---
name: unmassk-trading
version: 1.0.0
description: >
  Use when the user asks to "compra bitcoin", "vende ETH", "cuánto vale el bitcoin",
  "cómo va el mercado", "buy bitcoin", "sell", "what is BTC at", "check my portfolio",
  "quiero empezar a invertir", "enséñame a invertir", "teach me trading",
  "paper trading", "modo simulacro", "practicar sin dinero", "cuánto pongo",
  "how much should I buy", "position size", "cuánto puedo perder", "dónde pongo el stop",
  "abre una cuenta de práctica", "cómo va mi cartera", "qué he ganado", "he perdido",
  or wants to look at a live market price, practise trading with fake money, size a
  position, place an order on Kraken, or be taught how any of this works starting from
  zero. Two modes, asked once and remembered: BEGINNER (assess what the user knows, teach
  at that level, paper account first) and ADVANCED (straight to execution). The user gives
  every order — this skill never trades on its own, and never holds a key that can
  withdraw. NOT for backtesting research or tax accounting.
---

# unmassk-trading

Conversational trading on Kraken. The user speaks, the skill quotes, sizes, validates and
— only on an explicit order — executes.

**Read `references/honest-advice.md` before giving any opinion.** It is the shortest file
here and the one that decides whether this skill is useful or dangerous.

## The three rules that never bend

1. **The user decides direction. The skill never does.** No buy call, no price target, no
   sentiment score. What this produces is arithmetic and facts: what a position costs,
   what it loses at the stop, where the day's high and low are, and what the user's own
   record says about this kind of trade.
2. **Nothing executes without an explicit order from the user, in that turn.** "Vale",
   "ok", "lo que veas" are not orders. An order names the pair, the side and the amount;
   if one of the three is missing, ask for that one thing.
3. **The key never has withdrawal permission.** Not temporarily, not for convenience. If
   the active key can withdraw, stop and say so before anything else.

## Step 0 — which mode

Check memory first, do not re-ask:

```bash
gitmem search trading-mode
```

- A note answers it → use that mode, say one line ("sigo en modo principiante").
- Nothing → ask the fork once:
  - **Principiante** — never traded, or barely. The skill assesses, explains at that
    level, and works on a practice account until the promotion gate is passed.
  - **Avanzado** — knows what a limit order and a stop are, wants no explanations.

Then save it, so it is asked once and never again:

```bash
gitmem note M --zones skills trading "trading mode: <beginner|advanced>" \
  --description "<what the user said, or what the assessment showed>" --stops no
```

A beginner who asks for something advanced gets it — the mode governs how much is
explained and whether real money is reachable, never what may be asked.

## Beginner mode

Procedure in `references/beginner-mode.md`. The shape: **assess** (what they know, and
separately what they can afford to lose), **teach only what the next step needs**,
**practice account from minute one**, and **a measurable promotion gate** before a euro
moves. The affordability half runs on the lifted instrument in
`references/lifted/risk-profile-questionnaire.md` — capacity, tolerance and requirement
scored separately, with the rule that matters most: *never exceed emotional risk
tolerance*.

## Reading the market

A price is never stated bare. Every quote carries **its source and its age**, and before
a number gates a decision it is checked against a second venue:

```bash
kraken ticker BTCEUR -o json
kraken ohlc BTCEUR --interval 60 -o json
python3 scripts/price_check.py --pair BTC/EUR    # two venues, ages, spread, verdict
```

`price_check.py` takes `--pair` (the slashless form `BTCEUR` also works); there is no
positional argument. Exit codes: `0` OK, `3` DISAGREE, `4` STALE, `5` SINGLE_SOURCE, `2`
argparse usage error. **A caller that only checks the exit code is still protected** —
that is the point of them being distinct. Two disagreeing prices are reported, never
averaged.

**Read the JSON, then speak plainly.** `spread_bps` is emitted at full precision on
purpose (rounding it would hide a real difference between two prices that a float would
flatten to zero). Never read that number out. Say "los dos mercados coinciden" — or, when
they do not, "difieren un 0,4%, así que este precio no vale para decidir". The
machine-readable field stays exact; what reaches the user is one sentence.

Full command surface, the paper simulator's honest limits, and the MCP wiring:
`references/kraken-cli.md`.

## Sizing — before any order, always

Never quote a position in euros without saying what it loses if the stop is hit.

```bash
python3 scripts/position_sizer.py \
  --account-size 500 --entry 67517 --stop 63000 --risk-pct 1.0 \
  --fractional --share-precision 8
```

Verified output for that call: `0.00110692 units @ 67517 · position 74.74 · risk 5.00
(1.0%)`. **`--fractional` is mandatory for crypto** — without it the sizer rounds to whole
units and a sub-1-unit position collapses to zero.

Three lines are always said out loud, in euros: what it **costs**, what it **loses at the
stop**, and what **percentage of the account** that is. If the user has not named a stop,
that is the missing input — ask for it before sizing, not after. Methods (fixed
fractional, ATR, half-Kelly) in `references/lifted/sizing-methodologies.md`; the account
number to use, and why it is not the exchange balance, in `references/risk-and-sizing.md`.

**Two known mismatches until the adaptation pass:** the lifted scripts print `$` and
`shares`, and their calendar logic is US-market (`America/New_York`, Monday weeks). The
arithmetic is currency-neutral and correct; **restate the numbers in euros and units when
showing them to the user**, and do not rely on the day/week boundaries for a 24/7 market.

## The gates, before the order

```bash
python3 scripts/check_circuit_breaker.py --state-dir <dir>          # halted after a bad day/week/month?
python3 scripts/check_pre_trade_discipline.py --state-dir <dir>     # plan, stop, size, cooldown
```

Both **fail loud**: a missing value, an unparseable number or an absent upstream artifact
produces `REVIEW_REQUIRED`, never a silent pass. A `HALTED` or `COOLDOWN` verdict is
stated with its number and its reason, and it is not lifted because the user asks again in
the same session. Thresholds: `references/lifted/circuit-breaker-framework.md`. The seven
blocking checks: `references/lifted/discipline-gate-framework.md`.

These scripts need `PyYAML` and `jsonschema` (`requirements.txt`). If an import fails, say
so plainly — a gate that cannot run has not passed.

## Placing an order

Five steps, both modes, every time. Detail in `references/kraken-cli.md`.

1. **Dead man's switch, once per session** — `kraken order cancel-after 300 -o json`
2. **Validate** — `kraken order buy BTCEUR 0.001 --type limit --price 60000 --validate -o json`
   (real endpoint, real key, real payload, trades nothing)
3. **Show the validated order and wait** for an explicit yes
4. **Execute** — the same command without `--validate`
5. **Read it back** — `kraken open-orders -o json` and `kraken balance -o json`. Never
   report a fill from step 4's own output; if the read-back disagrees, say so immediately
   and do nothing else until it is resolved.

Before executing, check the command against the CLI's own `agents/tool-catalog.json`
`dangerous` field. Never keep a hand-written copy of that list here — it would drift.

## After a trade

The record goes in the project's memory, never in a second journal file:

```bash
gitmem note M --zones product trading "<pair> <side> <amount> @ <price> (<paper|real>)" \
  --description "Tesis en una frase. Stop, riesgo en euros, y qué lo invalidaría." --stops no
```

The fields worth carrying — thesis, kill criteria, stop, what would prove it wrong — are
in `references/lifted/thesis-lifecycle.md`. **The mode (paper or real) is never omitted:**
a practice result read later as a real one is the most damaging thing this record could do.

## What this skill refuses

- To place an order the user did not explicitly give in that turn.
- To run unattended, on a schedule, or "while you sleep".
- To use or request a key with withdrawal permission.
- To give a direction call, a price target, or a sentiment score.
- To advise on a quote whose age it cannot establish.
- To promote a beginner to live money before the gate in `references/beginner-mode.md`.

Each refusal names what is missing. "No puedo" without the reason is a bug in the answer.

## Reference files

Original to this plugin:

- **`references/beginner-mode.md`** — assessment, teaching order, first week, promotion gate.
- **`references/kraken-cli.md`** — install, paper mode, `--validate`, `cancel-after`, key
  permissions, streaming, MCP wiring, and what the simulator does not simulate.
- **`references/risk-and-sizing.md`** — the account number to use, the euro arithmetic,
  and what a trade note carries.
- **`references/honest-advice.md`** — what can be said, and what is a guess with a decimal
  point.

Lifted verbatim with the code they document (MIT — see `CREDITS.md`):

- **`references/lifted/sizing-methodologies.md`** — fixed fractional, ATR, Kelly.
- **`references/lifted/circuit-breaker-framework.md`** — the halt thresholds.
- **`references/lifted/discipline-gate-framework.md`** — the seven blocking checks.
- **`references/lifted/thesis-lifecycle.md`** — thesis fields and their state machine.
- **`references/lifted/risk-profile-questionnaire.md`** — the affordability instrument.
