# Memory Index — Cerberus (Code Reviewer)

- [conventions.md](conventions.md) — Project conventions: plugin structure, SKILL.md format requirements
- [false-positives.md](false-positives.md) — Patterns that looked suspicious but are intentional
- [anti-patterns.md](anti-patterns.md) — Recurring shell/Python/TS anti-patterns (ops-containers, unmassk-crew hooks, chatroom, session-start-boot.py module-split refactor 2026-07-05 rounds 1-13: security campaign genuinely CLOSED round 13 for 2nd consecutive round (10/10); round 12 found 4th unguarded OLD_SKILL_DIRS sibling — 90/110; round 13 (commit 24b98f1): elif-sibling fix verified + boot_memory.py split 524→394 + new boot_glossary_cache.py 195 LOC, DAG verified acyclic live, BUT split silently broke TestBugAOEnsureRuntimeDirFallbackBranchSymlinkedParent's monkeypatch (patches wrong namespace post-move, fallback branch now has zero live coverage despite GREEN) — 105/110, NOT MERGEABLE, closest yet; full history of rounds 1-12 in anti-patterns.md)
- [chatroom-standards.md](chatroom-standards.md) — Permanent 15-rule enterprise standards for chatroom/apps/backend/src/ + violation baseline as of 2026-03-19
- [chatroom-frontend-design.md](chatroom-frontend-design.md) — Definitive design reference audit (option-b-cursor-style.html): confirmed bugs, contrast truth table, missing states, color system structure
- [chatroom-frontend-patterns.md](chatroom-frontend-patterns.md) — Frontend React source audit 2026-03-21: intentional patterns, open violations (T2/T3), scoring baseline 68/110
