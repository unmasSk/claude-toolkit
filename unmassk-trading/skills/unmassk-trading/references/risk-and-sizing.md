# Risk, sizing, and the record

The arithmetic this skill exists to do. None of it predicts anything; all of it is
checkable, which is why it is the part worth trusting.

## The account number is not what is in the exchange

Every calculation below uses **the playable account** — the number the user said they
could lose without their life changing (see `beginner-mode.md`), not the balance the
venue reports. If someone has 5.000 € sitting on the exchange but said 500 € is the
number, the account is 500 €.

Read it back from memory before sizing anything:

```bash
gitmem search "risk profile"
```

## Sizing — the only question that matters

Never "how much do I want to buy". Always **"how much am I willing to lose if the stop
hits"**, and the size falls out of that.

```
risk_amount   = account × risk_per_trade          (see the note below on 1% / 2%)
stop_distance = entry − stop                       (per unit, absolute)
size_in_units = risk_amount ÷ stop_distance
cost          = size_in_units × entry
```

Worked, with real numbers so the shape is obvious:

```
account 500 €, risk 1%          → risk_amount   = 5,00 €
entry 67.500 €, stop 63.000 €   → stop_distance = 4.500 €
size = 5,00 / 4.500             = 0,00111 BTC
cost = 0,00111 × 67.500         = 75,00 €
```

**1% and 2% are OUR convention, not the tool's.** `--risk-pct` has no default and no upper
bound in `position_sizer.py`: it validates only that the number is positive. Pass it
explicitly every time, keep it at 1% while learning, and treat 2% as the ceiling this skill
imposes — the script will happily size a 40% risk if asked, and say nothing.

**75 € bought to risk 5 €.** That relationship — the position being much larger than the
amount at risk — is the single idea a beginner has to internalise, and showing both
numbers every single time is how it lands.

**And it is not computed by hand — the script does it**, with `Decimal` and rounding down,
so a rounding error can never enlarge a position. **The arithmetic is independently
verified**: fourteen cases were computed by hand from the definition above, with exact
rational arithmetic, before the script was run — all fourteen agree, and mutating the
rounding to nearest kills seventeen tests. The one thing that number does *not* cover: the
euro amounts are formatted through binary floats, so about one result in a thousand shows a
cent that could have gone either way on an exact half-cent tie. The **size** — the only
figure acted on — is `Decimal` end to end and is never affected.

```bash
SKILL_DIR=$(find ~/.claude/plugins/cache -maxdepth 5 -type d -path '*/unmassk-trading/*/skills/unmassk-trading' 2>/dev/null | while read -r d; do [ -e "${d%/skills/*}/.orphaned_at" ] || echo "$d"; done | sort -V | tail -1)
python3 "$SKILL_DIR/scripts/position_sizer.py" \
  --account-size 500 --entry 67517 --stop 63000 --risk-pct 1.0 \
  --fractional --share-precision 8 --max-position-pct 25 --output-dir <dir>/reports
```

Real output of that call (after two report-path lines):

```
Final: 0.00110692 shares @ $67517.0
Position: $74.74
Risk: $5.00 (1.0%)
```

The same numbers as the worked example above — which is the point of checking the tool
against the arithmetic instead of trusting either alone. `--fractional`, `--output-dir`
and the `$`/`shares` labels are covered in `SKILL.md`; they are not repeated here.

Four lines are always said out loud, in euros, before any order:

- what the position **costs**,
- what that cost is **as a percentage of the account** — the sizer will hand you a position
  worth more than the whole account if the stop is tight, and it says nothing when it does
  (verified: 500 € account, entry 67517, stop 67010 — a 0.75% stop — → `Position: $665.85`,
  exit 0; the full recipe is in `SKILL.md`),
- what it **loses at the stop**,
- what **percentage of the account** that loss is.

Pass `--max-position-pct` so the tool enforces the first of those instead of leaving it to
whoever happens to be reading.

If the user has not named a stop, **that is the missing input** — ask for it before
sizing, not after. A position with no stop cannot be sized, only guessed at.

### Fees are part of the arithmetic

At 0.26% taker, a 75 € position costs about 0,20 € to enter and the same to leave.
Trivial per trade, and not trivial at ten trades a week. When the user is trading small
and often, say what the fees add up to over the week — it is usually the largest single
line in a beginner's P&L.

### The other two methods

ATR-based sizing (the stop placed a multiple of recent volatility away, so a quiet asset
gets a tight stop and a wild one gets room) and Kelly (shown **halved**, never full, and
floored at zero on negative expectancy) are both implemented in the same script —
`--atr` / `--atr-multiplier`, and `--win-rate` / `--avg-win` / `--avg-loss`.

**The method write-up is not repeated here**: it is
`references/lifted/sizing-methodologies.md`, lifted with the code. One rule about Kelly
belongs in the conversation rather than the file, though: it needs a *known* win rate and
payoff, which a beginner does not have, and a wrong input produces a confidently oversized
position. Do not introduce it before the plain version is understood.

## The circuit breaker, and the gate before the order

Both are lifted scripts, and both are run — not paraphrased:

```bash
SKILL_DIR=$(find ~/.claude/plugins/cache -maxdepth 5 -type d -path '*/unmassk-trading/*/skills/unmassk-trading' 2>/dev/null | while read -r d; do [ -e "${d%/skills/*}/.orphaned_at" ] || echo "$d"; done | sort -V | tail -1)
python3 "$SKILL_DIR/scripts/check_circuit_breaker.py" --account-size <n> --state-dir <dir>/theses --output-dir <dir>/reports
python3 "$SKILL_DIR/scripts/check_pre_trade_discipline.py" --answers-file <dir>/answers.json \
  --state-dir <dir>/theses --output-dir <dir>/reports --journal-dir <dir>/journal \
  --circuit-breaker-decision <dir>/reports/<the breaker report just produced>.json
```

The circuit breaker halts after a bad day, a bad week, a bad month, or two losses in a
row; the strictest rule wins and **every** triggered rule is reported, not only the one
that decided. The gate blocks an order with no written reason, no stop decided before
entry, a size that does not match the rule, a risk above what was planned, a trade inside
the revenge-window cooldown, or a breaker that is halted.

**Four of those six can fire today. Two cannot, and pretending otherwise is the lie this
file is not going to tell:** the revenge-window cooldown and every drawdown rule read the
thesis store, and nothing in the documented workflow puts a trade there — the piece that
creates a thesis was not lifted (see `SKILL.md` and issue #86). Verified in both
directions: with a hand-written thesis carrying a loss two hours old the gate answers
`NO_GO` with `recent losing exit/trim within 24h`; with the store as this skill leaves it,
`theses_scanned` is `0` and that rule can never fire.

**So check `metrics.theses_scanned` on the gate as well as on the breaker.** A zero there
means the only things that were actually checked are the five answers written into the
answers file minutes earlier — which is the assistant checking its own homework, and worth
saying out loud rather than reporting as a clean gate.

**The thresholds and the seven checks live where the code that enforces them lives** —
`references/lifted/circuit-breaker-framework.md` and
`references/lifted/discipline-gate-framework.md`. Copying the numbers into this file would
guarantee they drift apart, and the copy would be the one someone reads.

What matters here, in the conversation:

- **Missing data is never a pass — for the discipline gate.** An unparseable number, an
  absent artifact or an unanswerable check produces `REVIEW_REQUIRED`. Report that as what
  it is — the gate did not pass — never as "all clear".
- **The circuit breaker is the exception, and it is the dangerous one.** A `--state-dir`
  that does not exist, or a typo in the path, returns `TRADING_ALLOWED` with `EMPTY_STATE`
  beside it — verified. It answers "you may trade" over zero data. Name the state directory
  once, save it to memory, and check `theses_scanned`: zero after ten paper trades means
  the path is wrong, not that the account is clean.
- **The discipline gate has a quieter version of the same hole:** with an unreachable
  `--state-dir` its revenge-window check silently evaluates against no history and reports
  nothing — `warnings` comes back empty. Treat `--state-dir` as required, not optional.
- **A halt is stated with its number and its reason**, and it is not lifted because the
  user asks again in the same session. The clock lifts it, or the user deliberately changes
  their own rule — which is saved as a rule change, not as an exception.
- **Both calendars are US-market** (`America/New_York`, Monday weeks), lifted as-is and staying that way — the lift is byte-identical on purpose (`CREDITS.md`). Crypto trades 24/7, so do not lean on their day and week boundaries: the day boundary is one of the two things issue **#86** has to settle before real money moves. The loss arithmetic itself is sound.
- **They need `PyYAML`.** `jsonschema` is also declared (`requirements.txt`) but reaches
  these two only through the thesis store, and only when a candidate carries a `thesis_id`
  — verified: both gates run and return their normal verdicts without it. If an import does
  fail, say so: a gate that could not run has not passed.
- **Both carry a required flag** — `--account-size` for the breaker, `--answers-file` for
  the gate — and the invocations, plus the difference in how each one fails, are in
  `SKILL.md`. The answers file itself: `references/gate-input.md`.

## The record — in memory, never in a second file

Every closed position and every meaningful decision becomes a `gitmem` note. **The record
this plugin keeps is the memory, not a file** — a parallel store is a second memory to keep
in sync, and this project already has one that survives sessions and machines.

Two file-based stores exist anyway, and claiming otherwise was a lie this document told
until it was caught:

- **The discipline gate appends a journal** of every decision (`--journal-dir`, default
  `state/journal/…` relative to the working directory). It is the gate's own audit trail;
  point it somewhere deliberate.
- **The circuit breaker reads a thesis store** (`--state-dir`) that nothing here fills in
  yet. `thesis_store.py` does ship the lifecycle commands (`open-position`, `trim`,
  `close`, `terminate`) and the breaker reads what they write; what was not lifted is the
  piece that *creates* a thesis, so there is no path from a trade to that store. Until
  issue #86 closes it, the breaker answers `TRADING_ALLOWED` over zero data — see
  `SKILL.md`.

Fields worth carrying in the note body:

- **thesis** — why this trade, in one sentence.
- **kill criteria** — what would prove it wrong, written *before* entry. This is the
  field that makes the record useful later; without it, every loss gets re-explained
  after the fact.
- **entry, stop, size, cost, risk in euros.**
- **mode** — paper or live. Never let a paper result be read later as a real one.
- **outcome, when closed** — exit, result in euros, and whether the plan was followed.
  "Followed the plan and lost" and "broke the plan and won" are both worth recording,
  and the second is the more dangerous one.

```bash
gitmem zones list        # first, always: the zones are the project's, not this skill's
gitmem note M --zones <zone1> <zone2> "BTCEUR buy 0,00111 @ 67.500 (papel)" \
  --description "Tesis: <una frase>. Stop 63.000, riesgo 5,00 € (1%). Lo invalidaría: <qué>. Modo: papel." --stops no
```

## What the record is for

Not nostalgia. It is the input for the one genuinely valuable thing this skill can say:

> *"Las últimas cuatro veces que compraste después de una caída del 10%, tres siguieron
> bajando."*
> *"Tu regla dice una posición abierta; ésta sería la segunda."*
> *"Dijiste que salías en −8% y va por −11%."*

Search it before sizing anything, and quote the note when it contradicts what the user is
about to do.
