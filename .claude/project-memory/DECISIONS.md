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
[D-017][skills][architecture] BM25 skill routing replaced the static CLAUDE.md skill-map
[D-018][release][architecture] this marketplace repo works directly on main
[D-019][memory][architecture] the memory system stays a hooks-based plugin, not an MCP
[D-020][memory][hooks] subagent recall needs a PreToolUse/Task hook rewriting the prompt
[D-021][testing][skills] two build modes: test-first for clear contracts, linear Flow for the rest
[D-022][testing][skills] two build modes: test-first for clear contracts, linear Flow for the rest
