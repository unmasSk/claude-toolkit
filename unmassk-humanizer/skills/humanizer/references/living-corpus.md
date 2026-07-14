# Living corpus

Dated AI tells caught in the wild, each tagged with the mechanism that produces it.
This is the part of the skill that compounds — the rule tables are commodity, but a
corpus of fresh, dated, mechanism-tagged tells is the moat. Grow it with the ingest
flow (`ingestion.md`); that file defines the entry format.

Tells age. The delve/tapestry era is already burning out; new ones appear whenever a
crackdown on an old tell pushes the same rhythm somewhere else. Note the date so we
can watch how fast a tell rises and falls, and re-tier or retire entries as the
models change.

Entries below are seeds. Both are second-order tells — worth logging because they
survive the obvious first-pass rules.

---

### anti-em-dash displacement

- Added: 2026-07-14  |  Tier: context-dependent
- Mechanism: displacement
- Context: A second-order tell. Now that every slop skill flags em dashes, models shunt the same "punchy aside" rhythm into colons and comma-spliced appositives. The punctuation changed; the metronome did not. Flag when the colon-or-appositive rhythm repeats across several sentences, not on a single clean use.
- Before: "The fix is simple: stop. It works, a clean little loop, every time."
- After: "The fix is simple. Stop. It runs as a clean loop every time."
- Rule: Removing em dashes is not enough. Check whether the same interruptive rhythm moved into colons or paired commas. Vary the sentence shape, not only the punctuation mark.
- Source: my own output (Claude, Opus-class)

---

### concession reflex

- Added: 2026-07-14  |  Tier: 2
- Mechanism: reward-tuning
- Context: "To be fair, X. That said, Y." dropped in to simulate balance when there is no real counterpoint. The tell is the reflex to both-sides even trivial points. Fine once when there is a genuine tradeoff; a tell when reflexive. Spanish equivalent: "Todo hay que decirlo, X. Dicho esto, Y."
- Before: "To be fair, the tool has limits. That said, it's still useful."
- After: "The tool is useful for X and weak at Y."
- Rule: Do not manufacture balance. If there is a real counterpoint, name it specifically. If not, drop the concession and make the claim.
- Source: my own output (Claude, Opus-class)
