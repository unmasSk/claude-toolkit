# Honest advice

The shortest file here, and the one that decides whether this skill is worth having.

**A language model has no informational edge on where a price goes next.** None. An
indicator adds arithmetic to the past, not information about the future. Every serious
trading toolkit published says this in its own disclaimer, and then most of them go on to
ship a bullishness score anyway. This one does not.

## What can be said with a straight face

**1. Arithmetic on live numbers and on the user's own account.**
Position size, worst-case loss in euros, what percentage of the account is at risk, total
exposure across open positions, what the fee costs, what the position is worth now versus
entry. This is the highest-value output in the whole skill and it needs no prediction at
all. It is also the part a beginner cannot do in their head and gets wrong every time.

**2. Levels that are facts.**
The day's high and low. The distance from here to the stop, expressed in euros and in
percent. The 24h range and where the current price sits inside it. Realised volatility
over the last N days. How far price is from a moving average, expressed in ATRs so the
number means something. These are measurements, not opinions — they can be checked, and
the skill can be caught being wrong about them, which is exactly what makes them safe.

**3. Contradictions against the user's own record.**
*"Your rule says one open position at a time; this would be the second."*
*"The last four times you bought after a 10% drop, three went further down."*
*"You said you would exit at −8%; it is at −11%."*
This is the one category where the machine has a genuine, unfakeable edge, because the
input is the user's own history and nobody else has it. The record lives in `gitmem`
notes — see `risk-and-sizing.md` for the fields.

**4. Calendar and events as facts.**
"There is a scheduled unlock on Thursday." "The exchange has announced maintenance."
Reporting what a source says, with the source named, is fine. Deriving a direction from
it is not.

**5. Data-quality alarms — always, loudly.**
"This quote is 4 minutes old." "Kraken and Binance disagree by 40 basis points." "The
paper simulator filled this instantly; a live order would not have." Under this project's
threat model — the system harming itself, silence being the worst failure — a stale or
disagreeing number that is presented as clean is the most likely way this skill lies to
its user. It never looks wrong.

## What is a guess wearing a decimal point

**Direction calls.** "Buy", "sell", "this looks bullish", "target 75.000". Nothing in the
input supports the confidence in the output.

**Sentiment scores.** Summarising an announcement is fine. Turning headlines into a
0-100 bullishness number and letting it gate a decision is fabrication with a format.

**Self-scored backtests.** A rule tuned on the same data it is measured against will look
excellent and mean nothing. Without out-of-sample testing and realistic fees and
slippage, a backtest result is a story. If one is produced anyway, it is labelled as
in-sample and the fee and slippage assumptions are stated next to it.

**Intraday advice on delayed or ageless data.** If the quote's age cannot be established,
the advice is wrong by construction and nothing in the output shows it.

**Averaging away a disagreement.** Two sources 2% apart do not average to a price. They
mean one of them is wrong, and that is the finding.

## How to phrase it

When the user asks the question this file exists for — *"¿compro o no?"* — the answer is
not a refusal lecture. It is the facts they need to decide, in one breath:

> No sé si va a subir. Lo que sí sé: ahora está en 67.500 €, hoy ha estado entre 66.600
> y 67.900. Si pones 50 € y pones el stop en 63.000, arriesgas 3,30 €. Eso es un 0,3% de
> tu cuenta. La decisión de si te compensa es tuya.

That answer is useful, honest, and takes the same number of words as a fake signal.

## The test

Before sending an opinion, ask: **could this be checked, and could I be caught being
wrong?** If yes, it is a fact and it can be said. If no — if it is unfalsifiable until
the future arrives — it is a guess, and the user is better served by the numbers that
sit underneath it.
