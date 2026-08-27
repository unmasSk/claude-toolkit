---
name: unmassk-trading
description: >
  Use when the user asks to "compra bitcoin", "vende mis ETH", "cuánto vale el bitcoin",
  "cómo va el mercado", "cómo va mi cartera", "cuánto he ganado", "he perdido dinero",
  "cierra la posición", "buy bitcoin", "sell my ETH", "what is BTC at", "check my
  portfolio", "quiero empezar a invertir", "enséñame a invertir", "teach me trading",
  "paper trading", "modo simulacro", "practicar sin dinero", "cuánto pongo en esta
  operación", "how much should I buy", "position size", "cuánto puedo perder", "dónde
  pongo el stop", "stop loss", "orden límite", "abre una cuenta de práctica", or mentions
  Kraken, cripto/crypto, or an exchange order. Also use when the user asks the skill to
  trade for them — "invierte por mí", "opera mientras duermo", "trade for me
  automatically", "hazlo tú solo" — so the refusal is given with its reasons rather than
  improvised. Two modes, asked once and remembered: BEGINNER (assess what the user knows,
  teach at that level, paper account first) and ADVANCED (straight to execution). The user
  gives every order — this skill never trades on its own, and never holds a key that can
  withdraw. Crypto spot on Kraken only. NOT for stocks or other brokers, NOT for
  backtesting research, NOT for tax accounting.
version: 1.0.2
---

# unmassk-trading

Conversational trading on Kraken. The user speaks, the skill quotes, sizes, validates and
— only on an explicit order — executes.

**Read `references/honest-advice.md` before giving any opinion.** It is the shortest file
here and the one that decides whether this skill is useful or dangerous.

**Paths.** A skill runs with the working directory set to the **user's** project, not to
the plugin, so a bare `scripts/…` resolves against their repository and fails. **And
`${CLAUDE_PLUGIN_ROOT}` is empty in the shell** — verified: it is substituted in
`hooks.json` entries, never exported to the Bash tool. What does arrive is the line
`Base directory for this skill: <absolute path>`, printed when this skill loads. Use that.
Set it once per session and use it everywhere below:

```bash
SKILL_DIR="<the Base directory this skill printed when it loaded>"
# if that line is not to hand, discover it:
SKILL_DIR=$(ls -d ~/.claude/plugins/cache/*/unmassk-trading/*/skills/unmassk-trading 2>/dev/null | sort -V | tail -1)
ls "$SKILL_DIR/scripts/price_check.py"      # prove it before using it
```

Output directories are always passed explicitly, for the same reason — see *The working
directory* below.

## The sequence

Every step below has its own section. The value of this skill is not skipping one.

0. **Tooling** — check `kraken` is installed, and install it if not. Nothing else works
   without it, and in a project opened for the first time it will not be there.
1. **Mode** — read it from memory, ask only if absent.
2. **Working directory** — read it from memory, agree it only once.
3. **Read the record** — the risk profile, and prior trades on this pair.
4. **Quote** — cross-checked against a second venue, with its age.
5. **Stop** — the user names it *before* the size is computed.
6. **Size** — from the script, never by hand; read `binding_constraint`.
7. **Write the answers file** — the gate's input, built from steps 5 and 6.
8. **Circuit breaker** — run it, keep its JSON report.
9. **Discipline gate** — run it *with* the breaker's report piped in.
10. **Validate** — `--validate` against the real venue; nothing is sent.
11. **Confirm** — show the validated order and wait for an explicit yes.
12. **Execute, read back, record** — never report a fill from the send's own output.

Steps 10-11 (`--validate` and the confirmation) belong to live orders only — there is
nothing to validate on a simulated fill. **Steps 8-9, the two gates, apply to the practice
account too**, and that is the point: the habit of refusing your own trade is what
transfers, and rehearsing it costs nothing while the money is fake. The first week in
`references/beginner-mode.md` introduces them once a stop and a size exist (day 4 onward),
not on day one.

## Step 0 — is the tooling there

**Run this first, in any project where this skill has not been used before.**

```bash
command -v kraken >/dev/null && kraken status -o json || echo "kraken NOT installed"
```

**What needs the binary and what does not** — this matters, because it decides whether a
session can start at all:

| Works without `kraken` | Needs `kraken` |
|---|---|
| `price_check.py` (it calls the public endpoints itself), the position sizer, both gates | Quotes through `kraken ticker`/`ohlc`, the practice account, `--validate`, the dead man's switch, every order |

So a user with no binary can still be taught, quoted and sized — say that rather than
stopping. What they cannot do is practise or order, and **`price_check.py` is the only
sanctioned direct call**: never hand-roll another REST call to replace a `kraken` command,
because that is how the practice account, `--validate` and the dead man's switch get
quietly skipped.

If it is missing, say what it is in one line — Kraken's own free command-line program, open
source, no account needed for prices or the practice mode — and install it:

```bash
curl --proto '=https' --tlsv1.2 -LsSf https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh
source "$HOME/.cargo/env" 2>/dev/null || true      # the installer puts it in ~/.cargo/bin
kraken status && kraken ticker BTCEUR
```

macOS and Linux; on Windows it goes through WSL. Full detail: `references/kraken-cli.md`.

**The Python side needs `PyYAML` for the gates**, and a bare `pip` is not a safe bet: on
many machines it does not exist, and `pip3` refuses with `externally-managed-environment`.
Use a virtual environment inside the working directory, once:

```bash
python3 -m venv <dir>/venv
<dir>/venv/bin/pip install -q -r "$SKILL_DIR/../../requirements.txt"
```

**Then run every script in this skill with `<dir>/venv/bin/python`, not `python3`.** Every
command below writes `python3` for readability; if you built the venv, that is the
interpreter it means. Say what was installed and move on — do not turn it into a ceremony.

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

## Step 1 — which mode

```bash
gitmem search "trading mode"
```

The stored headline is `trading mode: <beginner|advanced>`. `gitmem search` matches literal
text, so searching `trading-mode` with a hyphen finds nothing and the fork re-asks every
session.

- A note answers it → use that mode, say one line ("sigo en modo principiante").
- Nothing → ask the fork once: **principiante** (never traded, or barely) or **avanzado**
  (knows what a limit order and a stop are, wants no explanations). Then save it:

```bash
gitmem zones list                      # the zones belong to the project this runs in
gitmem note M --zones <zone1> <zone2> "trading mode: <beginner|advanced>" \
  --description "<what the user said, or what the assessment showed>" --stops no
```

**Never hardcode the zone pair.** This skill travels to whatever project it is run in, and
a note whose zone does not exist there is rejected — the note goes unwritten and the
failure reads as "the command is broken".

**If `gitmem` is not found**, say so once, plainly: the mode will be asked again next
session, and **the trade record has nowhere to go**. The second half matters more, and the
user deserves it before trading rather than after. `gitmem` ships with the
`unmassk-toolkit` plugin; without it this skill still quotes, sizes and gates — it just
forgets.

## The working directory

The scripts read and write state: the thesis store the circuit breaker looks at, the
reports, the gate's journal, the answers file. **They must all live in one directory that
survives sessions**, or the breaker reads an empty store forever and answers
`TRADING_ALLOWED` over nothing.

Agree it once and store it:

```bash
gitmem search "trading workspace"
gitmem note M --zones <zone1> <zone2> "trading workspace: <absolute path>" \
  --description "State, reports and journal for the trading skill live here." --stops no
```

Propose `~/trading/` — outside any repository, because these scripts default to writing
into the current working directory. Everywhere below, `<dir>` is that path.

## Beginner mode

Procedure in `references/beginner-mode.md`: **assess** (what they know, and separately what
they can afford to lose), **teach only what the next step needs**, **practice account from
minute one**, and **a measurable promotion gate** before a euro moves. The affordability
half runs on the lifted instrument in `references/lifted/risk-profile-questionnaire.md`.

## Advanced mode

**What it changes** — everything not on this list is identical in both modes:

| | Beginner | Advanced |
|---|---|---|
| The knowledge assessment | Run it | Skipped |
| Explaining a concept before using it | Every time, at their level | Only when asked |
| The affordability questionnaire | Run it | Ask for the two numbers directly: playable account, risk per trade |
| The practice account | Mandatory from minute one | Optional |
| The promotion gate | Blocks live money until passed | Does not apply |
| The sequence, both gates, the price check | Apply | **Apply, unchanged** |

The gates are not training wheels. They are what stops a typo from becoming a loss, and
they survive the mode.

## Reading the market

A price is never stated bare. Every quote carries **its source and its age**, and before a
number gates a decision it is checked against a second venue:

```bash
kraken ticker BTCEUR -o json
kraken ohlc BTCEUR --interval 60 -o json
python3 "$SKILL_DIR/scripts/price_check.py" --pair BTC/EUR
```

**Only `price_check.py` stamps an age.** `kraken ticker` and `kraken ohlc` return no
timestamp, so the only honest age for their output is "I ran this just now". A quote from
an earlier turn is **re-fetched, never re-quoted**.

Exit codes: `0` OK, `3` DISAGREE, `4` STALE, `5` SINGLE_SOURCE, `2` argparse usage error. A
caller that only checks the exit code is still protected — that is why they are distinct.

**`SINGLE_SOURCE` is also the verdict when *zero* venues answered.** Read the `reason`
field before repeating the label, or you will tell the user one market replied when none
did.

`--pair` takes `BTC/EUR` and `BTCEUR` alike; prefer the slash, so Kraken's `BTC→XBT` alias
resolves as intended. Two disagreeing prices are **reported, never averaged**, and
`spread_bps` is emitted at full precision on purpose — never read it out. Say "los dos
mercados coinciden", or "difieren un 0,4%, así que este precio no vale para decidir".

## Reading the account

The question the user actually asks — *"¿cómo voy?"* — and per `references/honest-advice.md`
the highest-value thing this skill produces, because it is arithmetic on their own numbers
rather than a guess about the future.

```bash
kraken paper balance -o json     # practice account
kraken balance -o json           # real account
```

**Say which account it is, every single time.** A practice result read later as a real one
is the most damaging thing this skill could do.

Then compute against the record, not from memory:

```bash
gitmem search <pair>             # the entries, with their stops and their theses
```

Per open position, in euros: what was paid, what it is worth now (at a quote checked as
above), the difference, **and whether that difference is realised or not** — down 20% is
not a loss until sold, and that distinction is the most valuable thing a beginner can
learn. Then the fees paid, and the total across positions as a percentage of the playable
account. **Never report a P&L figure from a quote whose age you cannot state.**

## Sizing — before any order, always

**Read the record first.** The account to size against is what the user said they could
lose, not the exchange balance:

```bash
gitmem search "risk profile"     # the playable amount, and the ceiling per position
gitmem search <pair>             # what happened the last times, if anything
```

If the record contradicts what the user is about to do, say so and quote the note. That is
the one edge this skill genuinely has.

**The user names the stop before the size is computed.** If they have not, that is the
missing input — ask for that one thing.

```bash
python3 "$SKILL_DIR/scripts/position_sizer.py" \
  --account-size 500 --entry 67517 --stop 63000 --risk-pct 1.0 \
  --fractional --share-precision 8 --max-position-pct 25 --output-dir <dir>/reports
```

Real output of that call without the cap (two report-path lines first, then):

```
Final: 0.00110692 shares @ $67517.0
Position: $74.74
Risk: $5.00 (1.0%)
```

Four things this tool does quietly, all verified:

- **Without `--fractional` it returns a plausible zero**: `Final: 0 shares`,
  `Risk: $0.00 (0.0%)`, exit 0. A zero there means the flag is missing, never that the
  position is safe.
- **Without `--max-position-pct` it hands you a position bigger than the account.** The
  same recipe with the stop at 67010 (0.75%, ordinary in crypto) returns
  `Position: $665.85` on a 500 € account, exit 0, no warning.
- **With the cap, the cap binds silently.** Verified: the same 0.75%-stop recipe with
  `--max-position-pct 25` on a 500 € account returns `Position: $125.00` and
  `Risk: $0.94 (0.19%)` — the user asked to risk 1% and is shown 0.19%, with nothing on
  stdout saying why. The field that explains it is **`binding_constraint`, in the JSON
  report only** (here: `max_position_pct`). Read it, and say it out loud: the stop is too
  tight for this account, so the position was capped.
- **It prints `$` and `shares`, and its calendar logic is US-market.** The arithmetic is
  currency-neutral and independently verified — fourteen cases computed by hand from the
  definition, all fourteen agree — but restate the numbers in euros and units.

Four lines are always said out loud, in euros: what it **costs**, what that cost is **as a
percentage of the account**, what it **loses at the stop**, and what percentage that loss
is. Methods: `references/lifted/sizing-methodologies.md`. The account number and the
arithmetic: `references/risk-and-sizing.md`.

## The gates

```bash
python3 "$SKILL_DIR/scripts/check_circuit_breaker.py" \
  --account-size 500 --state-dir <dir>/theses --output-dir <dir>/reports

python3 "$SKILL_DIR/scripts/check_pre_trade_discipline.py" \
  --answers-file <dir>/answers.json --state-dir <dir>/theses \
  --output-dir <dir>/reports --journal-dir <dir>/journal \
  --circuit-breaker-decision <dir>/reports/<the report just produced>.json
```

**`<dir>/theses` is the state directory everywhere**, in both gates and in every file: two
different values means the breaker and the gate read different stores, both answering
"empty", silently.

**Two runs in the same second overwrite each other.** All three scripts name their reports
`…_%Y-%m-%d_%H%M%S` and truncate: two sizings back to back leave one file, holding the
second. Give a run its own `--output-dir` when the previous report still matters — and note
the sizer stamps its filename in **local** time while the gates use UTC, so the names of
files written seconds apart can be hours apart.

**Both required flags are required** — `--account-size` and `--answers-file`. Omit either
and the script exits 2 having checked nothing. How to build the answers file, what each
reason means, and why the pipe is not optional: **`references/gate-input.md`**. Read it
before running the gate — it is what decides whether the answer means anything.

**The verdict is never in the exit code, and the two gates fail differently:**

- **The breaker prints its verdict to stdout** — `Recommendation:` and `Data quality:` —
  and exits 0 whatever it says, `HALTED` included.
- **The gate prints only `Decision:` and a generic rationale; the reasons live in the JSON
  report, at `candidate_results[].reasons`** — one list per candidate, and that exact path
  is verified. Open the report and read that field; nothing on stdout distinguishes a
  refusal from a missing input. `--fail-on-non-go` makes a non-`GO` exit 2 — but `GO` is
  unreachable while `--market-regime-decision` has no producer here, so that flag currently
  means "always 2" and carries no information. **Use it only once `GO` is reachable**;
  until then the JSON is the only channel that separates a refusal from a missing input.

**Two limits of the breaker that a 24/7 market makes real, both verified:**

- **Its day boundary is New York.** A loss closed between midnight UTC and the New York
  midnight — the early hours in Madrid — books to *yesterday*: `realized_pnl_today` comes
  back `0.0`, verdict `TRADING_ALLOWED`, `data_quality: OK`, no warning.
- **It reads a thesis store this plugin's workflow never writes.** Unless the user keeps
  that store deliberately, the breaker answers `TRADING_ALLOWED` over zero data forever.
  `data_quality: EMPTY_STATE` and `theses_scanned: 0` are the tell, and they are the
  difference between a brake and an ornament. Say which one you are looking at.

A `HALTED` or `COOLDOWN` is stated with its number and its reason, and it is not lifted
because the user asks again in the same session.

These scripts need `PyYAML`; `jsonschema` is imported lazily and only matters for the test
suite and for candidates carrying a `thesis_id`. If an import fails:

```bash
<dir>/venv/bin/pip install -q -r "$SKILL_DIR/../../requirements.txt"
```

**A gate that could not run has not passed** — say that, never "all clear".

## Placing an order

### Paper orders — what beginner mode uses

The workspace must exist first (`kraken workspace create …`, then
`export KRAKEN_WORKSPACE=…` — `references/kraken-cli.md`). In advanced mode nobody has
necessarily done it.

```bash
kraken paper buy BTCEUR 0.001
kraken paper sell BTCEUR 0.001
kraken paper balance -o json
```

**Paper accepts only `market` and `limit`** — verified in the CLI's own source. There are
no stop orders on the practice account: the stop is a number the user commits to and this
skill holds them to.

### Live orders — everything below is REAL money

**Status: written, not yet exercised against a live account.** This plugin ships phase 1.
Before any live order the promotion gate in `references/beginner-mode.md` applies, and the
key is created without withdrawal permission.

```bash
kraken order cancel-after 300 -o json                                          # 1. dead man's switch
kraken order buy BTCEUR 0.001 --type limit --price 60000 --validate -o json    # 2. validate
#                                                                              # 3. show it, wait for a yes
kraken order buy BTCEUR 0.001 --type limit --price 60000 -o json               # 4. execute
kraken open-orders -o json && kraken balance -o json                           # 5. read it back
```

Never report a fill from step 4's own output. If the read-back disagrees, say so
immediately and do nothing else until it is resolved.

**If step 4 errors, the order may or may not have reached the exchange. Never retry
blind** — check `kraken open-orders` and `kraken trades-history`, and resubmit only if it
is absent from both. Tag orders with `--cl-ord-id <id>` so the question has a cheap answer.

**The danger list is not on disk after a normal install.** `agents/tool-catalog.json` ships
in the CLI's source repository, not in the release tarball — checked inside the published
archive. So there is nothing to look up, and any `find` for it either fails or, worse,
matches an unrelated file in another project and answers `dangerous: false` right before a
real order. **Do not go looking for it.** The rule that replaces it, taken from that
catalogue while it could be read:

> **Every `kraken order …` command is dangerous and needs the user's explicit yes** —
> `order buy`, `order sell`, `order cancel`, `order cancel-all`. The one exception is
> `order cancel-after`, which only ever *cancels* and is step 1 here: run it without
> asking.

`paper_safe` is **not** a "does not spend money" flag: only four commands carry it, and it
means the danger gate relaxes *while the workspace is in paper mode*. And
`order cancel-after`'s expiry semantics are unverified, so never leave a protective order
resting behind an unrefreshed timer.

The first live order is the smallest the venue allows — and `--validate` is how that
minimum is discovered: it rejects an undersized order by name, at no cost.

## After a trade

The record goes in the project's memory, never in a second journal file:

```bash
gitmem zones list
gitmem note M --zones <zone1> <zone2> "<pair> <side> <amount> @ <price> (<paper|real>)" \
  --description "Tesis en una frase. Stop, riesgo en euros, y qué lo invalidaría." --stops no
```

**The mode — paper or real — is never omitted.** The fields worth carrying:
`references/risk-and-sizing.md`.

## What this skill refuses

- To place an order the user did not explicitly give in that turn.
- To run unattended, on a schedule, or "while you sleep".
- To use or request a key with withdrawal permission.
- To give a direction call, a price target, or a sentiment score.
- To advise on a quote whose age it cannot establish.
- To promote a beginner to live money before the gate in `references/beginner-mode.md`.
- Anything outside Kraken spot crypto: no stocks, no other broker, no futures, no leverage.

Each refusal names what is missing. "No puedo" without the reason is a bug in the answer.

## Reference files

Written for this plugin:

- **`references/honest-advice.md`** — what can be said, and what is a guess with a decimal
  point. Read first.
- **`references/beginner-mode.md`** — assessment, teaching order, first week, promotion gate.
- **`references/gate-input.md`** — the answers file, the reason table, the pipe.
- **`references/kraken-cli.md`** — install, keys, paper mode, `--validate`, `cancel-after`,
  streaming, MCP wiring, and what the simulator does not simulate.
- **`references/risk-and-sizing.md`** — the account number, the euro arithmetic, the record.

Under `references/lifted/` — **five documents kept byte-identical to their upstream source
(MIT, see `CREDITS.md`). They describe the upstream toolkit, not this plugin: read them for
the reasoning and the thresholds, never as this plugin's command surface.** That warning
applies hardest to `references/lifted/thesis-lifecycle.md`, which documents subcommands
that do not exist here — take the thesis fields from `references/risk-and-sizing.md`, which
states them in this plugin's own terms. The other four:
`references/lifted/sizing-methodologies.md` (the three sizing methods),
`references/lifted/circuit-breaker-framework.md` (the halt thresholds),
`references/lifted/discipline-gate-framework.md` (the seven blocking rules), and
`references/lifted/risk-profile-questionnaire.md` (the affordability instrument).
