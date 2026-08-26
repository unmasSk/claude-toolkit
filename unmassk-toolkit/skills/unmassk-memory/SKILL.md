---
name: unmassk-memory
version: 2.1.0
description: Use at the start and at the close of every session in a project with git memory; whenever a decision is made, a correction is given, something breaks, or work stops waiting on someone; when the user says "save this", "remember this", "note this down", "from now on", "always", "never", "what did we decide", "what is pending", "why did we do it this way", "we already discussed this"; before proposing an option or building on anything that may already be decided; and when committing code or checkpointing work in progress
---

# Project Memory

## Overview

**Core principle:** you start every session blank. What is not saved did not happen, and what is not read gets decided twice.

This is not a log and not an archive. It is what you know: the decisions, the walls, the scars and the open questions of this project. It lives in git, so **nothing is ever deleted** — a decision is never edited, a new one replaces it and points back at it.

**Violating the letter of this skill is violating the spirit of it.**

## The Iron Law

```
NOTHING THAT MATTERS NEXT SESSION LIVES ONLY IN THIS CONVERSATION
```

If a correction, a decision or a wall reaches the end of the session unsaved, it is gone — and the same mistake gets made again.

## The Read Gate

```
BEFORE proposing an option, building on existing ground,
or saying "there is nothing about that":

1. SEARCH   the zone, or the word, or the note ID
2. READ     the walls first — they are what stops the work
3. STATE    what memory says, with its note ID and date
4. ONLY THEN propose, build, or claim absence

Skipping this is deciding something for the second time
```

**What comes at boot is a sample, not the memory.** Absence from it proves nothing. And **reading is not applying**: a restriction that shows up at boot and doesn't change what you do is the same as one that was never written.

**When two sources disagree, this is the order** — highest first:

```
1. what the user is telling you now
2. confirmed memory (a note, with its ID)
3. the project's own instructions file
4. other context files
5. what you infer from the code
```

Never resolve a conflict silently. Name the two sources, say which one wins and why, and if the memory is the one losing, retire it — **by asking, never on your own judgement**.

## The Write Gate

```
THE MOMENT a signal appears — a correction, a decision,
a wall, something that broke, something waiting on someone:

1. STOP    before continuing the work
2. TEST    does it matter next session? is it derivable from
           the code or the history? would it change what I do
           if the same context repeats?
3. SAVE    one command, every field filled in
4. SAY     one line: what was saved, and its ID

"Later" is where memory goes to die
```

**Announcing is not saving.** Saying "I'll save that as a memo" and not running the command leaves the user believing it is stored when it is not — worse than never saving it, because now nobody will save it again. Run the command, then say what was saved.

**If what you are saving expires, put the horizon inside it.** "The provider changes this in the next release" is a useful memo while it's true and garbage afterwards; written without its horizon, nobody can tell which one it is today.

## What goes where

| The signal | Type | Dies when |
|---|---|---|
| A choice was made between options | **D** decision | Another D replaces it |
| A stable fact about the project | **M** memo | Replaced, or removed |
| Something that can stop or break work | **R** restriction | It stops being true |
| An open question, unconfirmed | **Q** question | It becomes an M or an X |
| Studied and rejected | **X** discarded | Never — that is the point |
| Something **already signed off** broke: what, why, what was done | **I** incident | Closed by its protocol — and a closed one is history |
| Pending on someone outside | **B** blocker | It is resolved |
| **How the user wants to be worked with** | **not a note** — a rule | Replaced by a clearer one |

**If it doesn't fit cleanly, don't force it.** The system rejects and asks. "I can't classify this" is information; a bucket is how memory rots.

**The wall yardstick, and it is the only one:** *can this cost data, hours, or production downtime?* Yes → restriction. No → memo.

**The blocker yardstick:** it comes from **outside** *and* makes a project claim false or an action impossible. Something pending on you is not a blocker.

## Static, or asking for work

Every note is one of two things, and the type does not decide it — the note does.

**Static:** a fact that just needs keeping. It changes only by being replaced. Most notes are this, and nothing else happens to them.

**Asking for work:** it says something has to be done. That work does not live in memory — memory only points at where it lives, with an issue number. **Every type accepts one.**

```
Is it inside the file or the task you already have open?
    YES → FIX IT NOW. The note records that it was fixed.
    NO  → it is outside, or it needs the user's decision:
          propose an issue in one line, with the priority you'd give it,
          and wait. You never open one on your own judgement.
```

"I'll note it" is not an answer to something you could fix, and "it was already there" is not an exemption. But an issue **is** a decision, so it is proposed and never assumed — and how long the user takes to answer is their business, never a reason to save the question for later.

Usually static: memo, restriction, discarded, and a decision (deciding something is not building it). Usually work: a question that needs measuring instead of answering, and an incident whose repair is still pending — a repair already done leaves only the scar.

**The full reading, the labels, and the issue template are in `references/issues.md`.** Read it before opening or closing one.

## Fields, by type

Sending a field a type doesn't accept is rejected exactly like omitting a required one.

| | Required | Also accepted |
|---|---|---|
| **D** | `--description` `--why` | `--keys` `--replaces` `--origin` `--discard` `--issue` |
| **M** | `--description` `--stops yes\|no` | `--keys` `--replaces` `--origin` `--issue` |
| **R** | `--description` `--stops yes` | `--why` `--keys` `--replaces` `--origin` `--issue` |
| **Q** | `--description`, and `--work no` **or** `--issue` | `--keys` · `--quote` (only with `--issue none`) |
| **X** | `--description` | `--why` `--keys` `--origin` `--issue` |
| **I** | `--description`, and `--work no` **or** `--issue` | `--why` `--keys` · `--quote` (only with `--issue none`) |
| **B** | `--description` `--awaits` | `--keys` `--issue` |

**`--issue` is accepted by all seven** — a note that points at work can be of any type. The number must belong to an issue that already exists; the system checks it once, when the note is saved, and rejects the note if it doesn't. If the issue is opened *after* the note was saved, the note is not rewritten: the issue cites the note instead.

**Q and I pass through the issue customs — the gate asks THE work question.** Saving either without `--issue` and without `--work` is rejected, with the yardstick in the rejection: *does closing this note require sitting down to work (code, measuring, building) — or just an answer or a decision in conversation?* The relaunch paths, and each is a recorded answer:

- **Just an answer** → `--work no`. The note passes with no issue; the session close puts these in front of the owner in case one matured into work.
- **Work, and the owner said yes** → you STOP and propose the issue to the owner in one line first; with his yes YOU create it (`gh issue create`) and relaunch with `--issue N`.
- **Work, and the owner said no** → `--issue none --quote "<his exact words>"`. The refusal only passes with the owner's literal phrase — same mechanic as rules; there is no `--quote none` here, because the no is always his.

A **D that defers future building** (a feature decided for later) also carries an issue — it is the owner's long-term checklist. The gate cannot detect that mechanically, so it is on you at save time, and the session-close sweep is the net that catches it.

**Headline and keys in English; the body in the user's language.** The headline is ≤80 characters and says what happened, not what was fixed. Keys are up to five search words **not already in the headline** — without them a correct note is unfindable.

**A decision buries its alternatives in the same act:** one `--discard` per option that lost, with why it lost — every one of them, not just the runner-up.

**A restriction carries the scar it was born from:** `--origin <incident-ID>`, or `--origin none` if it was born of nothing. It is only demanded once that zone pair already holds an incident, and then it is demanded hard — a wall whose scar is one zone away and unlinked is a wall nobody can date. **`--stops` is asked of memos and restrictions only;** on any other type it changes nothing.

**The test for a why, and it is the whole difference between memory and noise:** could someone reading only this note, six months from now, understand why *this* was chosen over the closest alternative? If not, rewrite it before saving. "Because it's better" fails. "Because sessions don't survive multi-tenant" passes.

## Which of the three situations you are in

Check this once, at the start, before writing anything. The three look alike from the outside and behave very differently.

| | How you tell | What it means |
|---|---|---|
| **New project** | No memory yet: nothing to read at boot, and no zone list | Nothing to recover. The first note creates the memory. **Zones do not exist yet**: the first ones get created as they are needed |
| **Project already running** | Memory reads back, zones are there | Ordinary work: read before building, save when the signal fires |
| **Project carrying memory from a previous or different system** | The history holds memory, but none of it reads back through these commands | **Nothing is lost and nothing is migrated.** That memory is distilled once, additively — the earlier commits are never touched. Until that pass runs, the past is only reachable by reading the raw history |

**Each agent's own memory is a fourth thing entirely** — what it learned about this codebase, kept apart from the project's. Nobody checks whether it is still true, and it rots the same way: `references/agent-memory-compaction.md` is the pass that fixes it, one agent at a time, each compacting only its own.

**The third one is not ordinary work and does not happen on its own.** It is a deliberate pass: harvest the zones first and get them approved, then distil oldest to newest, each round reading what the previous ones produced. The protocol is in `references/distill.md` — read it when that pass is what you are doing, not before.

**Never mix them up.** Treating the third as if it were the first leaves years of decisions unreachable while the memory looks perfectly healthy — the worst of the three, because nothing warns you.

## The two zones

Every note carries two, both real, no catch-alls.

**A zone is a judgment call, never a script's default.** Naming the zones a project speaks about means reading its history and distilling what it is really about — which is why an installer leaves the zone list empty on purpose and never guesses one for you. You create the first zone after reading the commits; in a project carrying old memory, that is the *harvest* step of the distill pass (the third situation above).

- **Zone 1 — the kind of work you speak from:** `product`, `testing`, `codeaudit`, `docs`, `deploy`, `database`, `api`, `ui`, `auth`. Not pre-installed: a fresh project has none.
- **Zone 2 — the part of the product you speak about:** different in every project.

**The two-second rule:** if the word can modify another one — "the *testing* OF X" — it's zone 1. If it can only be the object, it's zone 2.

**Zones are always lowercase** — on creation, on lookup, and on a note's own zone fields. `Billing` and `billing` are the same zone; write them however, the system normalizes them. `gitmem search` is case-insensitive the same way, and echoes the searched word back in lowercase.

**List before guessing, search before creating.** Adding one that already exists, or that is another's alias, bounces and touches nothing.

| Word a note may never use | Why it is banned |
|---|---|
| `claude`, `user`, `session`, `project`, `workflow` | They describe how you work — that is a rule, not memory |
| `audit` | Ambiguous: the kind of work and a module name collide |

The zone command will create all six anyway: the guard is at the note, so creating one buys a zone nothing can use. **And needing one of them is the signal, not the obstacle:** if a note keeps reaching for `workflow` or `project` to get a second zone, the note is not missing a word — it is a rule trying to come in through the wrong door.

## The signals

**Loud** — the words themselves are the trigger, in whatever language they're spoken:

- *"we'll go with X"*, *"decided"*, *"that's the approach"* → a decision.
- *"always"*, *"never"*, *"from now on"* → a rule if it's about how you work, a restriction if it can break something.
- *"the client requires"*, *"it must"*, *"it's mandatory"* → an imposed fact.
- *"that broke because…"*, *"don't ever do that again"* → **if it broke in something already delivered**, an incident, and probably a wall. A defect found while the thing is still being built is ordinary work: it gets fixed, and nothing is recorded.
- *"we're waiting on…"* → a blocker.

**Quiet** — these get lost, and they're the ones that cost:

- They stop arguing and start acting as if it's settled. That is the decision.
- The decision is already inside something they did, undiscussed.
- The same thing comes up a third time — a pattern, not a coincidence.
- They correct you and you fix it in the moment. **The most expensive one to lose:** applied today, forgotten tomorrow, made again.

**And the one that isn't a signal at all: your own proposal.** What you suggested is not a decision until they confirm it — explicitly, or by acting on it. Saving your own idea as the project's decision is how memory starts lying.

### Four calls, worked

| The situation | Saved? | Why |
|---|---|---|
| Three options compared, one picked without drama; from then on the user talks about it as settled | **Yes — a decision**, with its why and the losers discarded | Quiet agreement is agreement; drama is not a requirement |
| You lay out three approaches, argue for one; the user says "let me think about it" | **No** | A proposal you like is not a decision; filing it as one puts words in their mouth that come back as fact months later |
| You notice which port the service listens on, or where a module lives | **No** | The next session reads it off the code in seconds; that noise buries the notes that matter |
| The user corrects you mid-task, you fix it and keep going | **Yes — and it is the one that gets lost** | Applied today, forgotten tomorrow, made again. About how the project is → memo or restriction; about how you must work → rule |

## Red Flags — STOP

- About to propose an option without checking whether it was already discarded.
- About to say "there's nothing decided about that" from the boot alone.
- Saving a wall because it feels important, without answering the cost question.
- Filing how the user wants to be treated as a project memo.
- Retiring a wall because it seems stale — that is the user's call, never yours.
- Hand-editing an index or the zone list because the command bounced.
- "I'll save it after this block."

## Rationalizations

| Excuse | Reality |
|---|---|
| "I'll save it when I finish this" | The signal is gone by then. Save now. |
| "I told them I'd save it, that's the same" | It is not saved until the command ran. |
| "I proposed it and nobody objected" | Silence is not confirmation. Yours is a proposal. |
| "It's in the conversation, we both know it" | The conversation ends tonight. |
| "The boot didn't mention it, so it doesn't exist" | The boot is a sample. Search. |
| "No zone fits, I'll invent a general one" | A note with no zone is a misfiled note. |
| "The user contradicts a wall, so the wall must be stale" | Show them the wall and let them decide. |
| "It's a small correction" | Small corrections repeated are what costs hours. |
| "I'll write it into a file so it's visible" | If it isn't a commit, nothing reaches next session. |
| "This option is obviously right, searching would just confirm it" | The search takes ten seconds; skipping it is how a discarded option gets proposed again. |
| "I already know this project well enough" | Confidence is not memory. Search anyway — that is exactly the moment a discarded option resurfaces. |
| "It's just a suggestion, not a final decision" | The Read Gate applies to proposing, not just deciding. A suggestion built on unsearched ground is how memory starts lying. |

## When you get rejected

A rejection is the system asking, with the options and the exact relaunch inside. Read it whole — if it shows candidate notes, look at them — then answer as an argument.

| The rejection says | You answer |
|---|---|
| This overlaps something already written | `--replaces <ID>`, or `--replaces none` if both stand |
| The cost question is unanswered | `--stops yes` or `--stops no` |
| This rule is nearly the one already saved | Keep one. Don't reword and re-save |
| A wall with incidents in its zone | `--origin <incident-ID>`, or `--origin none` |
| That zone does not exist | Search for an equivalent; create it; relaunch |
| Working on the protected branch | Branch off, or declare the project's type as the rejection shows. **The test for declaring it:** does a commit to the main branch, by itself, publish to users? Yes → protected. Unsure → protected |

## Opening and closing

**At the start** the state arrives: the last Next with its context, **every** blocker, **every** wall, the counts and the coherence checks. Read it whole, then give the user the day's map as a **fixed two-column table** — always these eight labeled sections, in this order, written in the user's language, with a dash (—) in any section that is empty:

| | |
|---|---|
| 🧭 **Today** | the Next — one line per task it names |
| 📦 **Last session** | what the session that wrote the Next left done — one line per thing |
| ⛔ **Blockers** | one per line, each with who it waits on |
| ❓ **Questions** | one per line, the ones that block work under way, by name — never a bare number |
| 🔥 **Incidents** | one per line: open incidents, and plans with commits they never reflected |
| 🌿 **Branch** | the branch you are on; an extra line if it differs from the last worked one, another if there are unpushed commits |
| 📋 **Issues** | the issues carrying a live note, one per line |
| ⚙️ **Health** | the boot coherence checks: one line saying all green, or each failure on its own line — failures never softened, always first |

**Every section is always present** — a dash (—) when empty, never omitted. **One item per line, always.** A cell never packs two things with "+" or "·": when a section holds several items, each gets its own continuation row with the label cell left empty. Close with one line offering where to start. **The user picks the direction**; the boot lays out the map.

**Walls are NOT a row of that table.** They are Claude's seatbelt, not the user's reading: read every one and apply them, but never list them in the opening menu. Mention a wall only if it directly blocks what the user is about to do — one line, in plain words, at the moment it bites. When the user asks to SEE the walls ("show me the walls", an audit of them), present them properly: a clean table in plain language — what each one protects and what it forbids — never a raw dump of ids and zone tags.

**At the end**, write the Next. Its headline is the order for the next session; its context is prose — what was discussed, decided, broken, left half-done, and what made the user angry and why. Not a list of what was built: the commits already say that.

## Code, and the state of the indexes

**Code is committed through the memory too** — `work` for finished work, `wip` for a checkpoint, never a bare commit. `work` carries the files it touched and the plan it belongs to; `wip` is asked nothing, so there is never a reason not to save one. Both need a file that **actually changed**, and both **refuse to run on the main branch** unless the project has declared itself one that commits there directly.

**When the boot reports the indexes and git disagreeing, rebuild them.** Verifying says whether they match; rebuilding takes git as the truth and rewrites them from it.

## The commands — the only place they are written

Copy the shape, swap the values: every required argument is already there. **In a project whose zones aren't set up yet, the zone commands come first** — a note with an unknown zone is rejected, and a fresh project has no zones at all.

```
# zones — list and find before adding; nothing can be saved without them
gitmem zones list
gitmem zones find billing
gitmem zones add billing --description "payments and subscriptions" --aliases invoicing

# read — by zone, by word, by ID; --todo adds the archived
gitmem search auth
gitmem search stripe --todo      # archived notes are marked "archivada"; a note that replaced another shows (↺ M-xxx)
gitmem search --id D-030         # the --id view of a replacement note also shows "sustituye a M-xxx"
gitmem search auth --chain       # each live note with its superseded ancestors struck through below it (a moved head reads "sustituida por M-xxx", a real end "cerrada")

# a file's history, and what this branch touches
git log -- src/auth/login.py
git diff --name-only main

# note — type and headline are positional
gitmem note D --zones product auth "login with JWT + Google OAuth" \
  --why "server sessions don't scale multi-tenant" \
  --description "Sessions, a home-grown login and JWT were weighed." \
  --keys token oauth sso --discard "server-side sessions" "don't survive multi-tenant"

gitmem note M --zones api billing "Stripe sends webhooks in UTC" \
  --description "Confirmed against their dashboard while debugging a 2h offset." --stops no

# a note that points at work carries its issue number — any of the seven types.
# The issue must already exist: the user opens it, you never do. See references/issues.md
gitmem note Q --zones api billing "unknown whether the export holds at 1000 users" \
  --description "Nobody has measured it. Investigating means a load run, not an answer." \
  --keys load capacity export --issue 91

gitmem note R --zones testing database "never point the test suite at production" \
  --description "A seed run wiped the users table." --stops yes --origin I-014

gitmem note B --zones deploy billing "staging domain not purchased yet" \
  --description "Blocks the staging deploy." --awaits "the client"

# work / wip — message positional, one --path per file
gitmem work "add rate limiting to the login endpoint" \
  --path src/auth/login.py --path tests/test_login.py --issue 47
gitmem wip "half-way through the rate limiter" --path src/auth/login.py

# remove — id and reason positional
gitmem remove M-041 "the provider dropped that limit"
gitmem remove I-014 "seeds fixed" --restriction new \
  --restriction-text "never point the test suite at production" \
  --why "a seed run wiped the users table"

# next — close the session
gitmem next "finish the rate limiter and wire it to the login endpoint" \
  --context "<the whole session in prose, in the user's language>"

# rezones — verify the indexes against git, or rebuild them
gitmem rezones --verify
gitmem rezones

# rule — how to work, not what the project is. Defaults to the user's;
# --kind claude marks a rule about your own behaviour. No argument: prints them all
gitmem rule "be brief: never repeat back what I just said" --quote "be brief, don't repeat back what I just said"
gitmem rule "always read the existing patterns first" --kind claude --quote none
gitmem rule --retract "<exact text>" --kind <user|claude>            # retire a rule that stopped holding
gitmem rule "<new text>" --replaces "<old text>" --kind <user|claude> --quote "<literal>"  # replace one rule with another, atomically
gitmem rule
```

**The memory doctor — the CONTENT check, not the structure one.** `gitmem rezones --verify` proves the indexes match git; it says nothing about whether the notes still make sense. To review the content for rot — a live note a decision already killed, two notes saying the same thing in different words, a reference pointing at nothing, a board that lies about the code — invoke the **`unmassk-memory-doctor`** skill: an AI reads the memory (and each agent's own memory) and lists candidates, read-only. Retiring any of them stays the owner's call. Not to be confused with `git-memory-doctor`, which only checks the install.

**Every rule is saved with the literal words of whoever said it, via `--quote` — without them it bounces, for either `--kind`.** Claude's own paraphrase is not a substitute; that gap is how a rule the owner never said got saved on 2026-08-20, and how a real owner correction was later saved as `--kind claude` just to dodge the quote. The only way to save without a real quote is the explicit `--quote none` — Claude leaving itself a note, the owner said nothing.

**A word search that finds nothing shows the project's zone catalog, not a blank header.** `gitmem search <word>` is literal-text matching: zero results means that string isn't written anywhere, not that there's no memory of it. When a word search comes back empty, the output now lists the project's zones with their description and aliases — the words this project actually uses — so retry with one of those before concluding there's nothing. This only fires for a plain word search with zero matches; `--id`, `--file`, and a search that resolves to a zone name are unaffected. A project with no zones yet says so instead of showing an empty list.

**The user's own door into the rules is `/remember`** — the one slash command this toolkit ships, and it **only reads**: it delivers the whole rules file into your context, and you treat every line as binding from that moment. It takes no arguments and never saves. **Saving a rule is yours, always** — the moment the user says how they want to be worked with, you run `gitmem rule` there and then. A user who has to invoke a command to store their own correction is a user whose correction gets lost.

**`gitmem` is on the PATH — type it bare.** The installer puts a launcher at `~/.local/bin/gitmem` that resolves the newest installed version on every run, so it keeps working across upgrades. Write `gitmem note ...`, never a long path into the plugin cache: a pasted cache path carries a version number in it and goes stale the day the toolkit updates.

**If the bare command is not found, that is not a reason to reach for a long path — it is the signal that this project was never set up.** Run the installer once, `python3 ${CLAUDE_PLUGIN_ROOT}/bin/git-memory-install.py --auto`, and then use `gitmem`. It puts the launcher on the PATH and, in the same pass, seeds the eight indexes and writes the project's config — the things whose absence makes the first note bounce.

Reaching for the cache path instead leaves the project half-set-up forever: the command appears to work, so nobody notices there is no config and no indexes, and the next session pays for it again.

**And never report "no memory" when what happened is that the command wasn't found.** Those are opposite claims: one says the project has nothing saved, the other says you couldn't ask.

**And never ask the user to run any of them. You run them.**

## The hooks that are live

Generated from `hooks/hooks.json`, never by hand: a hook documented here but not registered is this skill telling the user something untrue.

<!-- BEGIN unmassk-active-hooks (generated from hooks/hooks.json — do not edit by hand) -->
**8 hook invocations declared** in `hooks/hooks.json`. Event, matcher and timeout are read from that file; file presence is checked on disk; transient measurement probes are excluded. This table is generated — regenerate with `bin/hooks_doc_sync.py --write`, never by editing it here.

| Event | Matcher | Hook file | Timeout |
|---|---|---|---|
| `SessionStart` | — | `boot_launcher.py` | 30s |
| `SessionStart` | — | `session-start-crew.py` | 10s |
| `PreToolUse` | `Bash` | `customs.py` | 15s |
| `PreToolUse` | `Write\|Edit` | `validate-memory-path.py` | 5s |
| `PreToolUse` | `Bash` | `pre-merge-gate.py` | 10s |
| `UserPromptSubmit` | — | `user-prompt-memory-check.py` | 10s |
| `PostToolUse` | `Skill` | `skill-checklist-inject.py` | 5s |
| `Stop` | — | `checklist-gate.py` | 5s |
<!-- END unmassk-active-hooks -->
