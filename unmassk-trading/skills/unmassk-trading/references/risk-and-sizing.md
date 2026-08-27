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
risk_amount   = account × risk_per_trade          (1% default, 2% ceiling)
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

**75 € bought to risk 5 €.** That relationship — the position being much larger than the
amount at risk — is the single idea a beginner has to internalise, and showing both
numbers every single time is how it lands.

**And it is not computed by hand — the script does it**, with `Decimal` and rounding down,
so a rounding error can never enlarge a position:

```bash
python3 scripts/position_sizer.py \
  --account-size 500 --entry 67517 --stop 63000 --risk-pct 1.0 \
  --fractional --share-precision 8
```

Measured output for exactly that call: `0.00110692 units @ 67517 · position 74.74 ·
risk 5.00 (1.0%)` — the same numbers as the worked example above, which is the point of
checking it against the arithmetic rather than trusting either alone.

**`--fractional` is mandatory here.** Without it the sizer rounds to whole units, and any
position under one bitcoin collapses to zero. And the script prints `$` and `shares`: the
arithmetic is currency-neutral and correct, the labels are not ours — restate them in
euros and units when showing anything to the user.

Three lines are always said out loud, in euros, before any order:

- what the position **costs**,
- what it **loses at the stop**,
- what **percentage of the account** that is.

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
python3 scripts/check_circuit_breaker.py --state-dir <dir>
python3 scripts/check_pre_trade_discipline.py --state-dir <dir>
```

The circuit breaker halts after a bad day, a bad week, a bad month, or two losses in a
row; the strictest rule wins and **every** triggered rule is reported, not only the one
that decided. The gate blocks an order with no written reason, no stop decided before
entry, a size that does not match the rule, a risk above what was planned, a trade inside
the revenge-window cooldown, or a breaker that is halted.

**The thresholds and the seven checks live where the code that enforces them lives** —
`references/lifted/circuit-breaker-framework.md` and
`references/lifted/discipline-gate-framework.md`. Copying the numbers into this file would
guarantee they drift apart, and the copy would be the one someone reads.

What matters here, in the conversation:

- **Missing data is never a pass.** An unparseable number, an absent artifact or an
  unanswerable check produces `REVIEW_REQUIRED`. Report that as what it is — the gate did
  not pass — never as "all clear".
- **A halt is stated with its number and its reason**, and it is not lifted because the
  user asks again in the same session. The clock lifts it, or the user deliberately changes
  their own rule — which is saved as a rule change, not as an exception.
- **Both calendars are US-market** (`America/New_York`, Monday weeks), lifted as-is. Crypto
  trades 24/7, so do not lean on their day and week boundaries until the adaptation pass
  lands; the loss arithmetic itself is sound.
- **They need `PyYAML` and `jsonschema`** (`requirements.txt`). If an import fails, say so:
  a gate that could not run has not passed.

## The record — in memory, never in a second file

Every closed position and every meaningful decision becomes a `gitmem` note. There is no
trade journal file anywhere in this skill, deliberately: a parallel store is a second
memory to keep in sync, and this project already has one that survives sessions and
machines.

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
gitmem note M --zones product trading "BTCEUR buy 0,00111 @ 67.500 (papel)" \
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
