# kraken-cli — the substrate

`krakenfx/kraken-cli` is Kraken's own single-binary CLI (MIT, open source). This skill
is built on it rather than on raw REST calls, because it already ships the four things
that would otherwise have to be written and maintained here: a local paper account, an
order validator, a dead man's switch, and a machine-readable list of which commands are
dangerous.

Everything below was verified against the CLI's own shipped skills on 2026-08-27. When
the CLI and this file disagree, **the CLI is right** — probe the tool, do not trust this
page. `kraken --help` and `kraken <command> --help` are the authority.

## Install

```bash
curl --proto '=https' --tlsv1.2 -LsSf https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh
kraken status && kraken ticker BTCEUR      # verify
```

Single binary, no runtime dependencies. macOS (Apple Silicon and Intel) and Linux
(x86_64, ARM64). Windows goes through WSL. `cargo install --git https://github.com/krakenfx/kraken-cli`
also works.

**If `kraken` is not found, do not fall back to raw REST calls.** That silently gives up
paper mode, `--validate` and `cancel-after` — the three things that make this safe.
Install it, or say plainly that it is missing.

## Keys — the permission rule

From Kraken's own guidance, and it is the hard wall of this skill:

- **Never enable `Withdraw Funds`.** Without it, even a compromised host or an injected
  instruction cannot move assets off the exchange.
- **Start read-only:** `Query Funds`, `Query Open Orders & Trades`,
  `Query Closed Orders & Trades`.
- **Add trading only when live trading begins:** `Create & Modify Orders`,
  `Cancel/Close Orders`. Nothing else is needed for spot.
- **IP-allowlist the key** when the machine has a stable address.
- **Rotate on host change.**

Keys are managed at <https://www.kraken.com/u/security/api>. The CLI resolves credentials
from flags, then `KRAKEN_API_KEY` / `KRAKEN_API_SECRET`, then its own config file
(`kraken auth set` / `show` / `reset`). Verify which key is live with `kraken auth test`
and `kraken balance`.

**Paper mode needs no key at all.** That is the point of starting there.

## Workspaces and paper mode

A workspace carries its own mode, and it persists between sessions:

**`export` does not survive between commands** — each one runs in its own shell — so the
workspace is selected **per command**, inline. Create it once; then prefix every paper
command with it:

```bash
kraken workspace create practica --capital 1000 --mode paper --currency EUR --slippage-rate 0.001
KRAKEN_WORKSPACE=practica kraken workspace status -o json

KRAKEN_WORKSPACE=practica kraken paper buy BTCEUR 0.001
KRAKEN_WORKSPACE=practica kraken paper sell BTCEUR 0.001
KRAKEN_WORKSPACE=practica kraken paper balance -o json
KRAKEN_WORKSPACE=practica kraken paper orders -o json
KRAKEN_WORKSPACE=practica kraken paper history -o json
kraken workspace status -o json
# DESTRUCTIVE — wipes the practice account, and with it the promotion gate's evidence:
# every closed position and every timestamped stop. Ask before running it, always.
KRAKEN_WORKSPACE=practica kraken workspace reset --yes
```

**Add `--allow-pairs` when creating a practice workspace** (comma-separated, or repeat the
flag): it restricts trading to the pairs named, and a beginner working on one pair has no
reason to be able to touch ninety others. One flag, free defence in depth.

Paper runs **locally against live market prices**. Kraken has no server-side spot
sandbox — the only Kraken demo environment is futures-only
(`demo-futures.kraken.com`), which is not what this skill uses.

### What the paper simulator does NOT simulate — say this out loud when showing results

- **Orders always fill in full, immediately.** Live orders partially fill, queue, or get
  rejected. This is the biggest lie the simulator tells.
- **Fees are a flat assumption.** Default 0.26% taker (Kraken Starter tier), set with
  `--fee-rate` at workspace creation and **fixed for that account's life**. Real fees drop
  with volume, and maker fees are lower (0.16%).
- **Slippage is a flat rate, default 0.0.** Always create the workspace with a non-zero
  `--slippage-rate`; a simulator that fills at the quoted price teaches the wrong habit.
  Market buys fill at `ask × (1 + rate)`, sells at `bid × (1 − rate)`.
- **No order-book depth, no rejections, no queue position.**

`kraken workspace promote <workspace>` exists as a graded evaluation, and as of the read
above it **returns exit 1 rather than flipping anything** — the grading is the value, not
the switch. Use the gate in `beginner-mode.md` and change modes deliberately.

## Live orders — the five steps

```bash
# 1. dead man's switch, once per session
kraken order cancel-after 300 -o json

# 2. validate: real endpoint, real key, real payload, trades nothing
kraken order buy BTCEUR 0.001 --type limit --price 60000 --validate -o json

# 3. show the validated order to the user and WAIT for an explicit yes

# 4. execute (same command, no --validate)
kraken order buy BTCEUR 0.001 --type limit --price 60000 -o json

# 5. read back — never report a fill from step 4's own output
kraken open-orders -o json
kraken balance -o json
```

`--validate` is the single highest-value command here. It catches what the paper
simulator structurally cannot: a wrong pair name, an amount under the venue minimum, an
insufficient balance, and a key missing the permission the order needs.

Other order commands: `kraken order sell`, `kraken order cancel <id>`,
`kraken order cancel-all`, `kraken order cancel-batch`, `kraken order batch <file>`.
Order types and their flags: `kraken order --help`.

## The danger list — read it, never copy it

The CLI ships `agents/tool-catalog.json`, a machine-readable catalogue of its commands
with a `dangerous: true` field (41 of 174 at the time of writing: order placement,
amendment, cancel-all, withdraw…). **Check that field before executing**, and never
maintain a hand-written copy of it in this skill — a copy drifts the day the CLI adds a
command, and drifts silently.

## Reading the market

```bash
kraken ticker BTCEUR -o json
kraken ohlc BTCEUR --interval 60 -o json
kraken orderbook BTCEUR -o json
kraken status -o json                 # venue status; a closed or degraded market is a fact worth saying
```

**`ticker` answers under Kraken's INTERNAL pair name, not the one you asked for.** Ask for
`BTCEUR` and the response is keyed `XXBTZEUR`. Reach the fields with `.[]` or `to_entries`
— a hardcoded key works on the pair you tested and fails on the next one, which is the
worst kind of bug because it looks like a data problem.

### Live streaming, when polling is not enough

```bash
kraken ws ticker BTC/EUR -o json      # NDJSON, one object per line
kraken ws trades BTC/EUR -o json
kraken ws book BTC/EUR -o json
```

There is also a `streamd` daemon and a playground that **records a live tape** to
`sessions/s<n>/tape.*` (duckdb or jsonl) and replays it (`--from tape:<name> --speed 10`).
That is what makes "watch this for 30 seconds and tell me what happened" possible without
this skill holding a socket open across turns — a skill cannot do that, a recorded tape
can.

### The free second opinion

No key, no account, and it is the cheapest integrity check available. Two independent
venues on the same pair:

```bash
curl -s "https://data-api.binance.vision/api/v3/ticker/24hr?symbol=BTCEUR"
curl -s "https://api.kraken.com/0/public/Ticker?pair=XBTEUR"
```

That comparison is what `scripts/price_check.py` automates, and its two thresholds are the
only numbers in this plugin a user is likely to want to tune:

| Flag | Default | Meaning |
|---|---|---|
| `--max-spread-bps` | `50` (0.5%) | Above this, the two venues `DISAGREE` and the quote gates nothing |
| `--max-age-seconds` | `60` | Older than this on either side and the verdict is `STALE` |

Both are strict comparisons: exactly 50 bps and exactly 60 s still read `OK`. **50 bps is
calibrated for a liquid pair** — measured live on BTC/EUR on 2026-08-27, Kraken and Binance
sat between 1 and 4 bps apart across the day. Treat that as an order of magnitude, not a
constant: it moves with volatility and with the hour. A thin pair can legitimately differ by more than that, so a `DISAGREE` on an
illiquid market is information about liquidity, not necessarily about a broken feed. Say
which it looks like rather than treating every alarm as a fault.

A disagreement is **reported, never averaged**. Two prices 2% apart mean one source is
wrong, and that is the finding.

## Pairs and naming

Kraken's REST layer uses its own asset codes (`XXBTZEUR` for BTC/EUR) while the CLI
accepts the friendly form (`BTCEUR`, `BTC/EUR`). Never hand-translate a pair name — pass
what the user said to the CLI and let `--validate` reject it if it is wrong. A silently
mistranslated pair is an order on the wrong asset.

## When a command fails — route by category, do not retry blindly

The CLI reports an error category. Each one has exactly one correct response, and getting
this wrong is how a failed order becomes two orders:

| Category | What to do |
|---|---|
| `auth` | Re-authenticate. **Never retry** — the same key will fail the same way. |
| `rate_limit` | Read the `suggestion` field and wait. Do not tighten the loop. |
| `network` | Back off exponentially — **and if it happened during an order, check `open-orders` and `trades-history` before resubmitting anything.** |
| `validation` | Fix the input. Retrying the identical payload is guaranteed to fail again. |
| `api` | Inspect the message; it is the venue telling you something specific. |

## Rate limits

The CLI ships a `kraken-rate-limits` skill; Kraken's public market-data endpoints are
generous and the private ones are not. Back off on error rather than retrying in a loop,
and never poll a private endpoint in a tight loop to "watch" something — that is what the
websocket and the tape are for.

## Wiring it as an MCP server (opt-in, after the CLI is installed)

The CLI ships its own MCP server over stdio, so the tools can be called natively instead
of through shell commands. **This plugin's `.mcp.json` is deliberately empty**: declaring
a server whose binary is not installed fails on every session start, loudly and
uselessly. Wire it only once `kraken status` works, by adding this to the plugin's
`.mcp.json`:

```json
{
  "mcpServers": {
    "kraken": {
      "command": "kraken",
      "args": ["mcp", "-s", "market,paper,workspace,account"]
    }
  }
}
```

**Those four service groups are the safe set** — public market data, the paper account,
workspaces, and read-only account queries. None of them can place a live order.

Two caveats worth knowing before wiring it: the CLI's own default is
`market,paper,feedback`, and **`account` requires a key**, so during the keyless paper
phase it adds nothing but a failing group. Start with `market,paper,workspace` and add
`account` when a read-only key exists.

`trade` (live orders) and `funding` (withdrawals) are **not** in that list on purpose.
Adding `trade` is a deliberate decision taken with the user when live trading begins;
`funding` is never added, for the same reason the API key never has withdrawal
permission. Kraken's own warning applies: any agent connected to this server uses the
same account and the same key permissions, so it stays local and least-privilege.
