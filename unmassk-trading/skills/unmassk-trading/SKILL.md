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

**Paths.** The scripts are invoked through `${CLAUDE_PLUGIN_ROOT}` because a skill runs
with the working directory set to the **user's** project, not to the plugin. A bare
`scripts/…` resolves against their repository and fails. The same applies to any output
directory: pass one explicitly, or the lifted scripts write their reports into whatever
repository the shell happens to be sitting in.

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
gitmem search "trading mode"
```

(The stored headline is `trading mode: <beginner|advanced>`. `gitmem search` matches
literal text, so searching `trading-mode` with a hyphen finds nothing and the fork
re-asks every session.)

- A note answers it → use that mode, say one line ("sigo en modo principiante").
- Nothing → ask the fork once:
  - **Principiante** — never traded, or barely. The skill assesses, explains at that
    level, and works on a practice account until the promotion gate is passed.
  - **Avanzado** — knows what a limit order and a stop are, wants no explanations.

Then save it, so it is asked once and never again:

```bash
gitmem zones list                      # the zones belong to the project this runs in
gitmem note M --zones <zone1> <zone2> "trading mode: <beginner|advanced>" \
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

## Advanced mode

**What it actually changes** — everything not on this list is identical in both modes:

| | Beginner | Advanced |
|---|---|---|
| The knowledge assessment | Run it | Skipped |
| Explaining a concept before using it | Every time, at their level | Only when asked |
| The affordability questionnaire | Run it | Ask for the two numbers directly: playable account, risk per trade |
| The practice account | Mandatory from minute one | Optional |
| The promotion gate | Blocks live money until passed | Does not apply |
| The five order steps, both gates, the price check | Apply | **Apply, unchanged** |

The gates are not training wheels. They are what stops a typo from becoming a loss, and
they survive the mode.

## Reading the market

A price is never stated bare. Every quote carries **its source and its age**, and before
a number gates a decision it is checked against a second venue.

**Only `price_check.py` stamps an age.** `kraken ticker` and `kraken ohlc` return no
timestamp, so the only honest age for their output is "I ran this just now". A quote from
an earlier turn is **re-fetched, never re-quoted** — there is no way to tell afterwards how
old it was.

```bash
kraken ticker BTCEUR -o json
kraken ohlc BTCEUR --interval 60 -o json
python3 ${CLAUDE_PLUGIN_ROOT}/skills/unmassk-trading/scripts/price_check.py --pair BTC/EUR    # two venues, ages, spread, verdict
```

`price_check.py` takes `--pair`; there is no positional argument. The slashless form works
(`BTCEUR`, `BTCUSDT` — both verified live against the two venues). Internally a slashless
four-letter quote splits oddly, which is invisible because the halves re-concatenate into
the same URL; **prefer the slash** (`BTC/USDT`) so the Kraken `BTC→XBT` alias resolves the
way it is meant to. **`SINGLE_SOURCE` is also the verdict when *zero* venues answered** —
read the `reason` field before repeating the label, or you will tell the user one market
replied when none did. Exit codes: `0` OK, `3` DISAGREE, `4` STALE, `5` SINGLE_SOURCE, `2`
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
python3 ${CLAUDE_PLUGIN_ROOT}/skills/unmassk-trading/scripts/position_sizer.py \
  --account-size 500 --entry 67517 --stop 63000 --risk-pct 1.0 \
  --fractional --share-precision 8
```

Real output of that exact call, run on 2026-08-27 (two report-path lines first, then):

```
Final: 0.00110692 shares @ $67517.0
Position: $74.74
Risk: $5.00 (1.0%)
```

**`--fractional` is mandatory for crypto** — without it the sizer rounds to whole units and
a sub-1-unit position collapses to zero. **Pass `--output-dir` too**: the default writes a
JSON and a Markdown report into `reports/` relative to the current directory, which means
into whatever repository the shell happens to be sitting in.

**The sizer does not check the position against the account, and it will hand you one
bigger than the account.** Verified with the exact recipe above, only the stop moved to
67010 (a 0.75% stop, ordinary in crypto): `0.00986193 shares` → **`Position: $665.85`** on
a 500 € account, exit 0, no warning. The risk is a correct 1%; the *cost* is 133% of
everything the user has. Always pass **`--max-position-pct`** (25 is a sane start), and say
the cost as a share of the account out loud.

**And the failure without `--fractional` is a plausible-looking zero, not an error:**
`Final: 0 shares` / `Position: $0.00` / `Risk: $0.00 (0.0%)`, exit 0 — verified. A report
saying the trade risks nothing is the most quotable wrong number in this plugin. A zero
there means the flag is missing, never that the position is safe.

Four lines are always said out loud, in euros: what it **costs**, what that cost is **as a
percentage of the account**, what it **loses at the stop**, and what that loss is as a
percentage. If the user has not named a stop,
that is the missing input — ask for it before sizing, not after. Methods (fixed
fractional, ATR, half-Kelly) in `references/lifted/sizing-methodologies.md`; the account
number to use, and why it is not the exchange balance, in `references/risk-and-sizing.md`.

**Two known mismatches until the adaptation pass:** the lifted scripts print `$` and
`shares`, and their calendar logic is US-market (`America/New_York`, Monday weeks). The
arithmetic is currency-neutral and correct; **restate the numbers in euros and units when
showing them to the user**, and do not rely on the day/week boundaries for a 24/7 market.

## The gates, before the order

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/unmassk-trading/scripts/check_circuit_breaker.py \
  --account-size 500 --state-dir <dir> --output-dir <dir>/reports

python3 ${CLAUDE_PLUGIN_ROOT}/skills/unmassk-trading/scripts/check_pre_trade_discipline.py \
  --answers-file <file>.json --state-dir <dir> --output-dir <dir>/reports
```

**Both required flags are required** — `--account-size` and `--answers-file`. Omit either
and the script exits 2 having checked nothing. How to build the answers file, and where
every field comes from: `references/gate-input.md`.

**Read the verdict from stdout, NEVER from the exit code.** Verified: a `NO_GO` from the
discipline gate and a `HALTED` from the circuit breaker both exit **0**. This is the
opposite of `price_check.py`, and getting it wrong means reading a refusal as a pass.

- `check_pre_trade_discipline.py` accepts **`--fail-on-non-go`**, which makes anything
  other than `GO` exit 2. **Always pass it.**
- `check_circuit_breaker.py` has no equivalent. Its verdict is the `Recommendation:` line,
  full stop.

**The pipe is not optional.** Run the breaker first and hand its JSON report to the gate
as `--circuit-breaker-decision`. Without it a `HALTED` account blocks nothing — verified:
breaker `HALTED`, gate `REVIEW_REQUIRED`, and the only reasons are the two missing
artifacts. Reporting that as "nothing wrong with this trade" while the account is halted is
the single worst failure this plugin can produce.

**Before passing a breaker report, check the report itself:** the gate reads only its
`recommendation` field and never looks at when it was made or whether it checked anything.
A report from yesterday, or one whose `data_quality` says `EMPTY_STATE`, is accepted as a
clean bill of health. Pass the run you just made, not `ls | head -1`, and give each run its
own `--output-dir` — the filenames are second-granular and two runs in the same second
overwrite each other.

**`--market-regime-decision` has no producer here**, so `GO` is unreachable as shipped.
When reporting a `REVIEW_REQUIRED`, name which reasons are present: `market_regime` alone
means "no rule was broken and one input we do not produce is missing"; anything else in
that list is a real finding, and `circuit_breaker artifact not provided` means **you forgot
the pipe**, not that the account is fine.

**The two gates do not fail the same way, and the difference matters:**

- **The discipline gate fails loud.** A missing value, an unparseable number, an absent
  upstream artifact → `REVIEW_REQUIRED`. It never turns absence into a pass.
- **The circuit breaker does not use that vocabulary at all.** Its verdicts are
  `TRADING_ALLOWED` / `COOLDOWN` / `HALTED`, and data quality is a **separate field**
  (`OK` / `PARTIAL` / `EMPTY_STATE`). Run against an empty state directory it returns
  `TRADING_ALLOWED` with `EMPTY_STATE` beside it — verified. **Read the data-quality field
  before believing the verdict**, and when it says `EMPTY_STATE`, say so: there is no
  history, so nothing was actually checked.

**Two limits of the breaker that a 24/7 market makes real, both verified:**

- **Its day boundary is New York, not UTC.** A loss closed in the window between midnight
  UTC and the New York midnight — 04:00 UTC in summer, 05:00 in winter, i.e. the early
  hours in Madrid either way — is booked to *yesterday*: `realized_pnl_today` comes
  back `0.0`, verdict `TRADING_ALLOWED`, `data_quality: OK`, no warning. The daily loss
  limit has a nightly blind window, and crypto trades through it. Until the calendar is
  adapted, do the day's arithmetic yourself before trusting a `TRADING_ALLOWED` at night.
- **It reads a thesis store this plugin never writes.** The trade record kept here goes to
  git-memory notes; nothing in the documented workflow creates `state/theses/`. So unless
  the user maintains that store deliberately, the breaker answers `TRADING_ALLOWED` over
  zero data, forever. `data_quality: EMPTY_STATE` is the tell, and it is the difference
  between a brake and an ornament.

A `HALTED` or `COOLDOWN` is stated with its number and its reason, and it is not lifted
because the user asks again in the same session. Thresholds:
`references/lifted/circuit-breaker-framework.md`. The seven blocking checks:
`references/lifted/discipline-gate-framework.md`.

These scripts need `PyYAML`. They also declare `jsonschema` (`requirements.txt`), but that
one is imported lazily and only when a candidate carries a `thesis_id` — verified: both
gates run and return their normal verdicts on an interpreter without it. What genuinely
breaks without `jsonschema` is the **test suite**, which cannot even be collected.

If an import does fail, say so: **a gate that could not run has not passed** — never
"all clear".

## Placing an order

### Paper orders — this is what beginner mode uses

```bash
kraken paper buy BTCEUR 0.001        # practice account, no key, no money
kraken paper sell BTCEUR 0.001
kraken paper balance -o json
```

**Paper accepts only `market` and `limit` order types** — verified in the CLI's own
source. There are no stop orders on the practice account.

### Live orders — everything below is REAL money

**Status: written, not yet exercised against a live account.** This plugin ships phase 1 —
read, practise, size. Every command in this section touches the real exchange; none of them
is the paper procedure. Before any live order the promotion gate in
`references/beginner-mode.md` applies, and the key is created without withdrawal
permission.

Five steps, every time. Detail in `references/kraken-cli.md`.

1. **Dead man's switch, once per session** — `kraken order cancel-after 300 -o json`
2. **Validate** — `kraken order buy BTCEUR 0.001 --type limit --price 60000 --validate -o json`
   (real endpoint, real key, real payload, trades nothing)
3. **Show the validated order and wait** for an explicit yes
4. **Execute** — the same command without `--validate`
5. **Read it back** — `kraken open-orders -o json` and `kraken balance -o json`. Never
   report a fill from step 4's own output; if the read-back disagrees, say so immediately
   and do nothing else until it is resolved.

**If step 4 errors, the order may or may not have reached the exchange. Never retry it
blind** — that is how one order becomes two:

```bash
kraken open-orders -o json      # is it sitting there?
kraken trades-history -o json   # did it already fill?
```

Resubmit only if it is absent from **both**. Tag orders with `--cl-ord-id <id>` so the
question has a cheap answer: query by the tag instead of guessing from timestamps.

Before executing, check the command against the CLI's own `agents/tool-catalog.json`
`dangerous` field (it ships inside the `kraken` installation; locate it rather than
guessing, and **if it cannot be read, treat the command as dangerous** — an unresolvable
check must never resolve to "proceed"). Never keep a hand-written copy of that list here:
it would drift.

**`paper_safe` is NOT a "does not spend money" flag.** Verified against the shipped
catalogue: only four commands carry it — `order-buy`, `order-sell`, `order-cancel`,
`order-cancel-all` — and it means only that the danger gate relaxes **while the workspace
is in paper mode**. Reading `order-buy: paper_safe: true` as "this does not spend" is
exactly backwards on the live path.

One caveat that stands on its own: `order-cancel-after` is marked dangerous and it is step
1 here. Setting the dead man's switch cancels orders, it never places one, so do not stop
to ask permission for it. **What the plugin does not know is its expiry semantics** — which
resting orders it reaches, and whether it must be refreshed. Until that is verified against
the real CLI, do not leave a protective stop resting behind an unrefreshed timer, and say
so when a user asks.

## After a trade

The record goes in the project's memory, never in a second journal file:

```bash
gitmem zones list                      # ALWAYS first — the zones differ per project
gitmem note M --zones <zone1> <zone2> "<pair> <side> <amount> @ <price> (<paper|real>)" \
  --description "Tesis en una frase. Stop, riesgo en euros, y qué lo invalidaría." --stops no
```

**Never hardcode the zone pair.** This skill travels to whatever project the user runs it
in, and a note whose zone does not exist there is rejected — the trade goes unrecorded and
the failure reads as "the command is broken". List the zones, pick two that exist, and
create one (`gitmem zones add trading --description "..."`) only if nothing fits.

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
- **`references/gate-input.md`** — the answers file the discipline gate requires, field by
  field, and where each value comes from.

Lifted verbatim with the code they document (MIT — see `CREDITS.md`):

- **`references/lifted/sizing-methodologies.md`** — fixed fractional, ATR, Kelly.
- **`references/lifted/circuit-breaker-framework.md`** — the halt thresholds.
- **`references/lifted/discipline-gate-framework.md`** — the seven blocking checks.
- **`references/lifted/thesis-lifecycle.md`** — thesis fields and their state machine.
- **`references/lifted/risk-profile-questionnaire.md`** — the affordability instrument.
