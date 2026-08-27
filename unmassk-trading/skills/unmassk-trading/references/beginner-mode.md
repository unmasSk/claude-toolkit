# Beginner mode

For a user who has never traded, or has traded a little and knows they do not know much.
The goal is not to make them a trader. It is to get them to the point where they can
decide for themselves, having lost nothing while learning.

**Nothing in this file places a live order.** Live money is unreachable in beginner mode
until the promotion gate at the bottom is passed.

**The two gates apply on the practice account too**, from day 5 of the first week. They
cost nothing there and the habit is the whole point: someone who has never had a trade
refused will not accept the first refusal that matters.

**And the rehearsal has one rule, or it teaches the opposite.** `GO` is unreachable as this
plugin ships, so every practice run answers `REVIEW_REQUIRED`. The expected reason —
`market_regime artifact not provided` — is the input nobody produces here, and the trade
proceeds. **Any other reason in that list stops the practice trade exactly as it would stop
a real one.** A rehearsal whose answer is always overridden trains the beginner to override
the answer.

## 1. Assess — two different questions, both asked

Ask them **one at a time**, in the user's language, conversationally. Never as a form.
Stop asking the moment the picture is clear; twelve questions is a ceiling, not a quota.

### What they know (six)

Each answer is scored *known / half / unknown*. The point is not to grade the user — it
is to know which explanations to skip so the teaching is not insulting.

1. If something costs 100 and you buy it, and it goes to 90 — have you lost 10, or have
   you lost nothing yet? *(Tests: realised vs unrealised loss. The single most important
   idea and the one that ruins people.)*
2. What happens if you say "buy 50 €" and the price moves while the order travels?
   *(Tests: market vs limit order.)*
3. Have you heard the word "stop"? What do you think it does?
4. If you put 100 € in and it becomes 50 €, how much does it have to rise, in percent, to
   get back to 100? *(Answer: 100%. Tests whether losses and gains feel symmetric — they
   are not.)*
5. Who is on the other side when you buy? *(Tests whether they think price is a fact or
   an agreement between two people.)*
6. Where does the money actually sit — in the app, in a bank, somewhere else?

### What they can afford — run the lifted instrument, do not improvise it

**The affordability half is not written here.** It is
`references/lifted/risk-profile-questionnaire.md`, lifted verbatim with the code (MIT,
see `CREDITS.md`), and it is a properly built instrument rather than a handful of
questions: it scores **capacity** (financial and objective — horizon, income stability,
what share of net worth, emergency fund, debt), **tolerance** (emotional — including the
sleep test and *what the person actually did* in the last crash, which it weights higher
than what they say they would do) and **requirement** (what the goal needs), then resolves
the conflicts between the three. Its own hard rule is the one to carry out of it:
**never exceed emotional risk tolerance**.

Two things about running it with a beginner:

- **Run it as a conversation, not as a form.** Take the axes in order, one question at a
  time, and stop as soon as the picture is clear. A 608-line questionnaire read aloud
  verbatim is how someone quits on day one.
- **Its output is an allocation between stocks and bonds. Ours is not.** What is taken
  from it is the euro number that may be put at risk and the ceiling per position — the
  asset-mix half does not apply to a single crypto pair and is ignored.

The five questions worth asking in plain words even when the instrument is skipped, because
each one alone can stop the whole thing:

1. Money you could put in and genuinely not need for a year — a number, not a feeling.
2. If that number halved in a week, what changes in your life? *(If the answer is anything
   real, the number is too big. Say so.)*
3. Debt with interest above about 5%? *(If yes: paying it is a guaranteed return, and this
   is not. Say it once, do not moralise.)*
4. Emergency savings covering a few months? *(If no, that comes first.)*
5. What is this for — learning, a long-term stake, or excitement? *(All three are valid.
   The third one needs the loss limits said out loud.)*

Save the conclusion, not the transcript:

```bash
gitmem zones list        # the zones belong to the project this runs in, not to this skill
gitmem note M --zones <zone1> <zone2> "risk profile: <amount> playable, <what they did last drop>" \
  --description "<the answers that shaped it, and the ceiling per position that follows>" --stops no
```

**The ceiling that comes out of this is a wall, not a suggestion.** If they said 500 € is
the number, no position is ever sized against a larger account than 500 €, whatever is
actually in the exchange.

## 2. Teach in the order the work needs it

Not a course. Each idea is explained at the moment it is about to matter, in one or two
sentences, with a number from their own screen. In this order:

1. **A price is what two people just agreed on.** It is not a value.
2. **Buying and selling, and the fee.** Show the fee in euros on their actual size — a
   0.26% taker fee on 50 € is 13 céntimos, and saying so kills the fear of hidden costs.
3. **Market vs limit.** "Now, at whatever price" vs "at this price or better, maybe never".
4. **The stop, and why it is decided before entering.** The one rule: the number is
   chosen with a cold head, not while watching it fall.
5. **Size.** Never "how much do I want to buy" — always "how much am I willing to lose if
   the stop hits". See `risk-and-sizing.md`.
6. **Unrealised vs realised.** Down 20% is not a loss until sold, and that is *why*
   selling in panic is where the money actually goes.
7. **Volatility.** Show them their own asset's 24h range. "This thing moves 3% on a quiet
   day" is more useful than any definition.
8. **Only after all of the above:** what a candle chart shows, if they ask. Not before.

Anything the assessment scored *known* is skipped, and skipping it is said out loud
("esto ya lo sabes, sigo").

## 3. The paper account, from minute one

```bash
kraken workspace create practica --capital 1000 --mode paper --currency EUR --slippage-rate 0.001
KRAKEN_WORKSPACE=practica kraken workspace status -o json   # selección POR COMANDO:
# un `export` no sobrevive de una llamada a la siguiente, así que cada comando de
# práctica lleva el prefijo delante o irá al espacio por defecto (otro capital, otro
# deslizamiento) y la evidencia de la puerta de promoción acabará donde nadie la lee.
```

**No API key exists in this mode.** A bug in this skill cannot spend the user's money,
because there is no money reachable. That property is the reason paper comes first, and
it is worth telling the user.

Set the slippage rate to something non-zero (0.001 above). The default is 0, and a
simulator that always fills at the quoted price teaches a false lesson. Say what the
simulator does not do — full list in `kraken-cli.md`, and at minimum, out loud, every
time results are shown: **paper orders always fill in full and instantly; live ones do
not.**

### A first week that produces something checkable each day

One action per day, each leaving evidence. Do not run several days in one sitting — the
waiting is part of what is being taught.

1. **Day 1** — create the account, quote one pair, place one paper buy of 50 €. Read the
   position back. Nothing else.
2. **Day 2** — read the same position without touching it. Say whether it is up or down,
   in euros, and whether that is realised. *(This is the lesson.)*
3. **Day 3** — place a limit buy below the market and watch it not fill. Cancel it.
4. **Day 4** — decide the stop and write it down, **before** looking at the price again.
   **The practice account has no stop orders**: verified in the CLI's own source, paper
   accepts only `market` and `limit`. So the stop is a number the user commits to and this
   skill holds them to, not an order the exchange holds. Save it with the position note.
   The exercise is the commitment, and it is the one that transfers to real money.
5. **Day 5** — sell half. Show the realised result and the fee, in euros. Then **rehearse
   the gates for the first time**: write the answers file for that trade after the fact
   (`references/gate-input.md`), run the breaker and the gate as `SKILL.md` prescribes, and
   read the verdict together. Nothing is at stake — that is exactly why it is the right day
   to learn what a refusal looks like. From here on, every practice entry goes through them
   before it is placed.
6. **Day 6** — read the week: what was bought, what it cost, what it is worth, what the
   fees ate.
7. **Day 7** — write the rules the user wants to hold themselves to, in their own words,
   and save them with `gitmem rule`. These become the contradictions the skill will raise
   later.

## 4. The promotion gate

Live money becomes reachable only when **all** of these are true, and the evidence is
shown, not asserted:

- [ ] At least **two full weeks** of paper activity, with at least **ten** closed paper
      positions. Fewer than ten and there is nothing to learn from.
- [ ] Every one of those positions had a **stop written down before entry**, in the
      position note, with a timestamp that precedes the entry. On the practice account the
      exchange cannot hold a stop, so the note is the evidence — and a note written after
      the entry does not count. One missing resets the count.
- [ ] The user's own written rules exist (day 7) and were **not broken** in the last week.
- [ ] The user can answer, unprompted: what they are risking per position, what their
      stop is, and what would tell them they were wrong.
- [ ] The user has stated the real-money amount, and it is **at or below** the number
      from the affordability assessment.

Then, and only then:

- the first live size is **the smallest the venue allows**, not the sized position — the
  first real order exists to prove the plumbing works, not to make money;
- keys are created **without withdrawal permission** (`kraken-cli.md`);
- the mode note is updated, citing which gate items were met.

**Refusals name what is missing.** "Todavía no" is not an answer; "todavía no: llevas 6
operaciones cerradas de 10, y dos entraron sin stop" is.
