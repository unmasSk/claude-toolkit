# DECISIONS — índice. Lo escribe el script. No editar. Si diverge, manda git.

[D-001][memory][hooks] delete the v1 memory system instead of keeping it dormant on disk
[D-002][install][memory] the boot installs the project by itself when no manifest is present
[D-003][memory][skills] the CLI stays 'gitmem rule'; the user's door is the slash command /remember
[D-004][standards][testing] unmassk-standards gained Producer-Consumer round-trip integrity (§34)
[D-005][memory][hooks] the near-dup write-path gate stays lexical, not semantic
[D-006][memory][release] code commits: local WIPs per sub-step, single squash and push at close
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
[D-020][memory][hooks] subagent recall needs a PreToolUse/Task hook rewriting the prompt
[D-021][testing][skills] two build modes: test-first for clear contracts, linear Flow for the rest
[D-022][testing][skills] two build modes: test-first for clear contracts, linear Flow for the rest
[D-023][docs][architecture] public repo content: English code and UI, Spanish conversation
[D-024][memory][architecture] vector search deferred as non-foundational, unlike the git decision graph
[D-025][standards][testing] the toolkit's threat model is the system against itself, not an attacker
[D-026][standards][architecture] unmassk-standards rewritten generic, axis: the system against itself
[D-027][testing][standards] tests default to real dependencies, mock only what cannot run
[D-028][skills][architecture] domain skills route by orchestrator judgment from loaded front matter
[D-029][boot][memory] freshness stamp: own success-stamp only, real remote+branch identity
[D-030][boot][memory] boot fetches every branch and shows a global summary, never switches locally
[D-031][skills][architecture] START stays a prose checklist, deliberately without a mechanical gate
[D-032][skills][architecture] Flow's agent sequence is fixed to a canonical, loop-free order
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
