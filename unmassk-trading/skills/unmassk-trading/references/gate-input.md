# Feeding the pre-trade gate

`check_pre_trade_discipline.py` has one required input and it is not optional:
`--answers-file`. Without it the script exits 2 with an argparse error and nothing is
checked. **A gate that could not run has not passed** — say that plainly rather than
carrying on.

## The file

JSON or YAML, one entry per candidate order. The five fields that decide the verdict are
`entry_in_written_plan`, `stop_predefined`, `size_within_plan`, `planned_risk_*` and
`actual_risk_*`.

```json
{
  "candidates": [
    {
      "symbol": "BTCEUR",
      "order_intent": "ENTRY_READY",
      "entry_in_written_plan": true,
      "stop_predefined": true,
      "size_within_plan": true,
      "planned_risk_dollars": 5.00,
      "actual_risk_dollars": 5.00,
      "notes": "Tamaño calculado por position_sizer.py, stop en 63.000."
    }
  ]
}
```

**The field names say `dollars`. They are the lifted schema's names and the arithmetic is
currency-neutral** — put euros in them and read euros out. Renaming them would mean
editing lifted code; restating the currency when speaking to the user costs nothing and
breaks nothing.

Only actionable intents are gated: `ENTRY_READY`, `ACTIONABLE`, `ACTIONABLE_DAY1`,
`MANUAL_ORDER`. Anything else (`WATCHLIST`, `IGNORE`, `REJECTED`…) is journaled as
`NO_ACTIONABLE_ORDERS` — recorded, but it grants no permission to place an order.

## Where the values come from — none of them are invented

| Field | Source |
|---|---|
| `entry_in_written_plan` | Did the user say why, before being asked to confirm? One sentence counts. |
| `stop_predefined` | The stop the user named **before** entry. If it was decided after seeing the price move, this is `false`. |
| `size_within_plan` | Whether the size matches what `position_sizer.py` returned, unedited by hand. |
| `planned_risk_*` | The sizer's `risk` figure. |
| `actual_risk_*` | What the order about to be sent really risks. If it differs from planned, the gate blocks — and it is right to. |

**Never fill a field to make the gate pass.** A missing value, a boolean where a number
belongs, a non-numeric string, `NaN`, an infinity or a negative all produce
`REVIEW_REQUIRED` by design. That is the gate working, not the gate being awkward.

## Running it

```bash
python3 scripts/check_pre_trade_discipline.py \
  --answers-file <file>.json \
  --state-dir <dir> \
  --output-dir <dir>/reports \
  --journal-dir <dir>/journal \
  --circuit-breaker-decision <dir>/reports/<breaker report>.json \
  --fail-on-non-go
```

**`--fail-on-non-go` or the exit code lies.** Without it, a `NO_GO` exits 0 — verified.
With it, anything other than `GO` exits 2.

**`--circuit-breaker-decision` is how the breaker's verdict reaches this gate.** Run the
breaker first, then hand it **the report you just made**. Without the pipe, a `HALTED`
account cannot block a single order here — verified.

And check the report before passing it: the gate reads only its `recommendation` and never
looks at `generated_at` or `data_quality`. **A stale report, or one that says
`EMPTY_STATE`, is accepted as a clean bill of health.** Give every run its own
`--output-dir`; the filenames are second-granular and two runs in the same second
overwrite each other, leaving one file whose verdict may not be the one you think.

**Always pass the output directories.** The defaults are relative to the current working
directory (`reports/`, `state/journal/…`), so running from a repository root writes report
files into it. Point them at the user's own trading directory, never at wherever the shell
happens to be.

## The verdicts

`GO` < `NO_ACTIONABLE_ORDERS` < `REVIEW_REQUIRED` < `NO_GO`, and the strongest wins, so an
explicit rule violation stays visible even when another candidate merely needs review.
`GO` decisions are journaled too, not only refusals — a record that only holds failures
cannot show that the good trades also followed the rules.

**`GO` is unreachable as this plugin ships, and that is not a bug in your answers.** The
gate also expects `--market-regime-decision`, an artifact produced by a skill that was not
lifted, and a missing upstream artifact is `REVIEW_REQUIRED` by design.

**Read the reasons one by one before saying anything. They are not interchangeable:**

| Reason | What it means |
|---|---|
| `market_regime artifact not provided` | The input nobody produces here. No rule was broken by this. |
| `circuit_breaker artifact not provided` | **You forgot the pipe.** The account may be halted right now and this gate cannot see it. Never report this as "nothing wrong" — go and run the breaker. |
| anything else | A real finding. That one is a refusal. |

Only when `market_regime` is the **sole** reason may you say the gate found no rule
violation — and even then, say that the breaker was checked separately and what it said.
The reasons are written to the JSON report and are **not** printed on stdout, so read the
file; the `Decision:` line alone does not tell you which of the three rows you are in.

The seven blocking rules themselves: `references/lifted/discipline-gate-framework.md`.

---

*The JSON shape and the field semantics above are taken from tradermonty/claude-trading-skills
(MIT) — see `CREDITS.md`.*
