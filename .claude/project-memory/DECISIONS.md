# DECISIONS — índice. Lo escribe el script. No editar. Si diverge, manda git.

[D-001][memory][hooks] delete the v1 memory system instead of keeping it dormant on disk
[D-002][install][memory] the boot installs the project by itself when no manifest is present
[D-003][memory][skills] the CLI stays 'gitmem rule'; the user's door is the slash command /remember
[D-004][standards][testing] unmassk-standards gained Producer-Consumer round-trip integrity (§34)
[D-005][memory][hooks] the near-dup write-path gate stays lexical, not semantic
[D-007][boot][memory] boot hook output is always a minimal banner, content lives only in the file
[D-008][boot][memory] boot fetches async before reading memory, never blocks or force-pulls
[D-009][standards][install] Windows/macOS/Linux support became a hard requirement
[D-010][standards][memory] context-injection features cap Security below 10/10 by design
[D-011][skills][architecture] unmassk-grill absorbs the Spec Kit investigation instead of a new skill
[D-012][docs][release] one root CHANGELOG.md for every plugin, not one per plugin
[D-013][hooks][memory] hostile-commit forgery defense uses an unpredictable nonce fence, not a denylist
[D-014][docs][architecture] important content is documented by hand in three audiences at once
[D-015][release][install] plugin marketplace distribution replaces manual git-clone install
[D-016][memory][install] no confirmation before saving memos and decisions
[D-018][release][architecture] this marketplace repo works directly on main
[D-019][memory][architecture] the memory system stays a hooks-based plugin, not an MCP
[D-021][testing][skills] two build modes: test-first for clear contracts, linear Flow for the rest
[D-023][docs][architecture] public repo content: English code and UI, Spanish conversation
[D-024][memory][architecture] vector search deferred as non-foundational, unlike the git decision graph
[D-025][standards][testing] the toolkit's threat model is the system against itself, not an attacker
[D-026][standards][architecture] unmassk-standards rewritten generic, axis: the system against itself
[D-027][testing][standards] tests default to real dependencies, mock only what cannot run
[D-028][skills][architecture] domain skills route by orchestrator judgment from loaded front matter
[D-029][boot][memory] freshness stamp: own success-stamp only, real remote+branch identity
[D-030][boot][memory] boot fetches every branch and shows a global summary, never switches locally
[D-031][skills][architecture] START stays a prose checklist, deliberately without a mechanical gate
[D-033][memory][boot] CLAUDE.md managed-block writes became atomic
[D-034][memory][testing] memory readers retry and warn loud instead of returning empty
[D-035][install][architecture] MCPs install on-demand per skill, at user scope, none wired by default
[D-036][memory][architecture] objective-profile is a documented convention over git-memory, not new machinery
[D-037][memory][architecture] memory v1 stored everything but surfaced almost nothing, so v2 was born
[D-038][memory][architecture] remember() leaves the project-memory system entirely
[D-039][memory][architecture] two mandatory zones, decided by whether a word can modify another
[D-040][memory][architecture] commit headline format: brackets first, emoji after, no ANSI color
[D-041][memory][skills] a zero-result search must name the candidate zones, instead of nine agent cards
[D-042][hooks][testing] the DoD gate recognises first-party modules by declared project identity
[D-044][memory][architecture] the issue is opened the moment the work appears, with the user present
[D-045][memory][architecture] issue labels: three priorities, the type, and the note's own memory zones
[D-046][hooks][testing] Stop-time test gate retired: test_command never runs on its own
[D-047][skills][hooks] Dante and Ultron lose Task; the router speaks the owner's Spanish
[D-048][skills][architecture] a user's question is never a go; the message IS the question
[D-049][skills][architecture] modo automatico: unattended work protocol with a fixed closing report
[D-050][memory][skills] gitmem rule requires the owner's literal words, or an explicit --quote none
[D-051][skills][architecture] fixes target the toolkit itself, never this repo's local rules or CLAUDE.md
[D-052][skills][architecture] compliance plan approved: blocks 3 4 5 6 8 9b 9c and program-set checkboxes
[D-053][skills][architecture] point 7 approved: split wizard and frameworks refs, keep best-practices whole
[D-054][skills][architecture] checklist box matching strips accents too, not only casefold/dash/whitespace
[D-055][memory][architecture] two concurrent work-writes to one file are not both required to succeed
[D-056][memory][architecture] memory legibility and integrity batch scoped and ordered from Moria review
[D-059][skills][architecture] repetition-scout skill: Protocolo Dia de la Marmota, file unmassk-groundhog
[D-060][boot][memory] walls leave the opening menu: Claude-only seatbelt, pretty table on demand
[D-064][boot][memory] opening table: eight fixed sections, branch, issues and health always visible
[D-066][memory][architecture] issue-gate refusal records the owner's exact phrase, like rules do with --quote
[D-067][docs][release] changelog adopts Zen-style: Fixed first, issue links, Known section, dates kept
[D-068][docs][release] changelog entries: 1-2 sentences with the why, pointer to memory, no story
[D-069][boot][architecture] session timing telemetry, automatic, shown in next boot
[D-070][ci][release] work/wip commits carry [skip ci]; only the release commit triggers CI
[D-071][skills][trading] trading skill is for a beginner: live data, plain talk, advice he executes
[D-072][skills][trading] the trading skill starts on crypto, stocks and the rest come later
[D-073][architecture][trading] the skill sends the order when he says so, dry-run first, never on its own
[D-075][skills][trading] the trading skill has two modes and asks which one at the start
[D-076][architecture][trading] kraken-cli is the substrate; live means fresh-on-ask, no daemon of ours
[D-077][architecture][trading] council: connect the brake to the paper account, do not delete it; wrapper now
[D-078][architecture][trading] no order-intercepting hook: it would sit in every call of every project
[D-079][skills][trading] phase 2 is not built yet: learn on the practice account first
[D-080][architecture][skills] harness review uses the Claude desktop app as baseline, not the terminal
[D-081][skills][docs] reviews of prompts and CLAUDE.md count only the last one or two months
[D-082][skills][docs] every SKILL.md moves to one common template, later
[D-084][install][release] end-to-end install test runs in a clean VM provided by Blackbox
[D-085][architecture][skills] long term: make the toolkit more agnostic, usable beyond Claude
[D-086][docs][architecture] toolkit docs and code move to English together with the agnostic work
[D-087][boot][memory] boot loads the owner's rules whole each session, after a review of them
[D-088][skills][memory] each agent repairs its own notebook in every project, after the toolkit redesign
[D-089][skills][standards] Yoda: 110 is perfection; any lower score owes the path to 110, or why not
[D-090][boot][hooks] live panel mod for agent and session timings, apart from #84
[D-091][skills][architecture] council gains an ideation round when no options exist yet, adhd-style
[D-092][hooks][skills] a hook blocks git stash, reset, checkout and restore, not just R-017's text
[D-094][boot][skills] boot slimming: nothing leaves without a pointer to its full version
[D-095][skills][boot] boot slimming is verified by inventory, blind check, branch and a fresh session
[D-100][skills][install] project cleanup skill (CLAUDE.md, plugins, memory), once per project
[D-102][hooks][install] owner cue: Morse three times, 0.3 s apart, only when he is needed
[D-106][skills][architecture] flow order in both modes, every fix once, Yoda last with path to 110
[D-108][skills][architecture] work hierarchy: milestone, task (= issue), phase, step
[D-112][skills][architecture] flow procedures: Trivial, Short (Corto), Full (Completo)
[D-113][skills][architecture] fixes always go to a fresh agent unless Bex names the same one
[D-114][testing][skills] each agent running tests gets its own test database, as the sector does
[D-116][memory][architecture] memory moves to its own git refs with hash-based note IDs
[D-117][release][memory] a task's branch lives until the task ends; merged to dev, it is deleted at once
[D-118][memory][release] commit protocol: orchestrator saves a WIP per agent, one commit per step
[D-119][hooks][release] merge gate: nothing on merges into dev; the heavy gate only from dev to staging
[D-120][hooks][release] staging gate: Cerberus+Argus on the whole batch, Alexandria, Bex's yes
[D-121][skills][hooks] flow checklist by procedure: Trivial none, Short its own boxes, Full all
[D-122][skills][standards] audit runs one pass: every reviewer once, every fix once, no loops
[D-124][memory][hooks] per-message checklist gains a 4th check: a result given is ticked in its plan
[D-126][skills][testing] test-first: Ultron adds code beyond the tests only as a declared exception
[D-127][skills][testing] wrong contract test goes to a fresh Dante at once; Short follows the build mode
[D-128][skills][docs] flow written to a standard now: titled sections, reading order, no filler
[D-129][hooks][skills] council on publishing today's changes: fix four things first, then release
[D-130][boot][hooks] boot asks GitHub once for all issues, under a total deadline that fails loud
[D-131][boot][memory] owner's rules reach every session through a CLAUDE.md import, not hook output
[D-132][hooks][install] Morse cue fires on Claude Code's Notification event: permission or idle prompt
[D-133][memory][boot] searched text rides in a leading Description so 1.47.0 reads new notes
[D-135][skills][docs] flow's eight parts go by their own names, no number and no generic word
[D-137][skills][docs] flow v2: open points of the draft decided by sector, one left for Bex
[D-138][skills][docs] a Short task may ask Bilbo one pointed question when size can't be told
[D-139][skills][docs] an agent that stopped before working gets one fresh run with what it lacked
[D-140][skills][docs] flow v2 goes in on a local branch, tried via --plugin-dir before release
[D-142][hooks][skills] checklist gate waits only on in-flight subagents and workflows, and says so
[D-143][memory][skills] a redo close covers the whole session: skip this session's own earlier close
[D-144][memory][skills] close extractor reads every transcript since the last close, not only newest
