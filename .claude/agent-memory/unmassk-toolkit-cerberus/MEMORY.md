# Memory Index — Cerberus (Code Reviewer)

- [conventions.md](conventions.md) — Project conventions: plugin structure, SKILL.md format requirements
- [false-positives.md](false-positives.md) — Patterns that looked suspicious but are intentional
- [anti-patterns.md](anti-patterns.md) — Recurring shell/Python/TS anti-patterns across boot/git-memory/hooks/CI-flake rounds; latest: trailer content validated pre-sanitize instead of post-sanitize (2026-07-25)
- [review-history.md](review-history.md) — Full dated log of past commit-reviews/audits with verdicts, evidence, test counts (2026-07-08 → present). Most recent: 2026-07-25 trailer-content-validation wrapper round, NOT MERGEABLE (1 issue: raw vs sanitized value gap), 2 suggestions
- [chatroom-standards.md](chatroom-standards.md) — Permanent 15-rule enterprise standards for chatroom/apps/backend/src/ + violation baseline as of 2026-03-19
- [chatroom-frontend-design.md](chatroom-frontend-design.md) — Definitive design reference audit (option-b-cursor-style.html): confirmed bugs, contrast truth table, missing states, color system structure
- [chatroom-frontend-patterns.md](chatroom-frontend-patterns.md) — Frontend React source audit 2026-03-21: intentional patterns, open violations (T2/T3), scoring baseline 68/110
