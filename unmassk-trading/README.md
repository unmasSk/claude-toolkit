# unmassk-trading

**Conversational trading on Kraken, for someone who is still learning.** You say what
you want in plain words; the skill quotes the live market, does the arithmetic you would
get wrong in your head, validates the order against the real exchange, shows it to you,
and executes only after you say yes.

It never trades on its own, and it never holds a key that can move money off the
exchange.

## Two modes, asked once

**Beginner.** For someone who has never traded. The skill finds out what you actually
know — and, separately, what you can actually afford to lose — then explains each idea at
the moment it matters, not as a course up front. Everything happens on a **local practice
account with fake money and no API key at all**, so a bug cannot spend a euro. Real money
becomes reachable only after a measurable gate: two weeks, ten closed positions, a stop
set before every entry, and your own written rules unbroken.

**Advanced.** No explanations, same gates. `--validate` before every order, an explicit
confirmation, a read-back afterwards, and a dead man's switch per session are not
training wheels — they are what stops a typo from becoming a loss.

The answer is stored in the project's memory, so the question is asked once and never
again.

## The three rules that never bend

1. **You decide direction. The skill never does.** No buy calls, no price targets, no
   sentiment scores. What it produces is arithmetic and facts: what a position costs,
   what it loses at your stop, where today's high and low are, and what your own record
   says about this kind of trade.
2. **Nothing executes without an explicit order from you, in that turn.** "Sounds good"
   is not an order.
3. **The API key never has withdrawal permission.** Not temporarily, not for convenience.

## What it actually does

- **Live prices, with their age stamped on them**, and a free second opinion from an
  independent venue when a number is about to gate a decision. A disagreement is
  reported, never averaged away.
- **Position sizing from risk, not from appetite** — you say what you are willing to lose
  if the stop hits, and the size falls out of that. Cost, loss-at-stop and percentage of
  account are stated in euros, every time.
- **A circuit breaker** that halts trading after a bad day, a bad week, or two losses in
  a row, and says which threshold you hit.
- **A record in git-memory, not in a second journal file** — so next session can be asked
  what you decided and why, and so the skill can tell you when you are about to break
  your own rule.

## What it refuses

To place an order you did not give. To run unattended or on a schedule. To use a
withdrawal-capable key. To give a direction call. To advise on a quote whose age it
cannot establish. To promote a beginner to real money before the gate. Every refusal
names what is missing.

## Install

```
/plugin install unmassk-trading@unmassk-claude-toolkit
```

It drives [`krakenfx/kraken-cli`](https://github.com/krakenfx/kraken-cli), Kraken's own
open-source CLI:

```bash
curl --proto '=https' --tlsv1.2 -LsSf https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh
kraken status && kraken ticker BTCEUR
```

Paper mode needs no account and no key. Set up keys only when you go live, and create
them without `Withdraw Funds`.

## What is shipping, and what is not

**Phase 1 ships**: live prices, the teaching layer, the practice account, and the sizing
arithmetic. **Live order execution is written down but has never been run** — that is
phase 2, and it is gated.

**The loss limit does not protect you yet, and this is deliberate rather than hidden.**
The circuit breaker reads a record this plugin does not write, so it answers "you may
trade" over no data at all; and its day boundary is New York, so a loss closed in the small
hours books to the previous day. Both are documented inside the skill, and connecting the
practice account to it is the gate that opens phase 2. While there is no money reachable,
this costs nothing. It would cost everything afterwards.

**What IS verified**: the sizing arithmetic — the only number you would act on — was
computed by hand in fourteen cases from the definition, independently of the code, and all
fourteen agree. Over 680 tests pass, two of which call the real Kraken and Binance on every
run so that a change at either venue cannot pass unnoticed.

## Honest limits

- **Nobody knows where a price goes next, this skill included.** Everything it says is
  either a measurement or arithmetic, and it is designed so you can catch it being wrong.
- **The practice account lies in one specific way:** orders always fill in full and
  instantly. Real ones partially fill, queue, and get rejected. The skill says so every
  time it shows practice results.
- **Crypto first.** It is the only asset class where live, EUR-denominated prices are
  free and unlimited. Stocks are a later phase and cost real money for real-time data.
- **This is not financial advice**, and the skill will not pretend otherwise.

See `CREDITS.md` for the open-source work this stands on.
