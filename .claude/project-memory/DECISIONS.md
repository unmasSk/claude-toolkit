# DECISIONS — índice. Lo escribe el script. No editar. Si diverge, manda git.

[D-001][memory][hooks] delete the v1 memory system instead of keeping it dormant on disk
[D-002][install][memory] the boot installs the project by itself when no manifest is present
[D-003][memory][skills] the CLI stays 'gitmem rule'; the user's door is the slash command /remember
[D-004][standards][testing] unmassk-standards gained Producer-Consumer round-trip integrity (§34)
[D-005][memory][hooks] the near-dup write-path gate stays lexical, not semantic
[D-006][memory][release] code commits: local WIPs per sub-step, single squash and push at close
[D-007][boot][memory] boot hook output is always a minimal banner, content lives only in the file
[D-008][boot][memory] boot fetches async before reading memory, never blocks or force-pulls
