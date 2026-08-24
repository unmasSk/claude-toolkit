# Memory Index — Cerberus (Code Reviewer)

- [conventions.md](conventions.md) — Project conventions: plugin structure, SKILL.md format requirements
- [false-positives.md](false-positives.md) — Patterns that looked suspicious but are intentional
- [anti-patterns.md](anti-patterns.md) — Recurring shell/Python/TS/agent-sheet-prose anti-patterns across boot/git-memory/hooks/CI-flake/self-review rounds; latest: `checklist-gate.py` (2026-08-24) — a safety-counter persist call's return value discarded, no warning, while the sibling hook of the same feature already handles the identical failure
- [review-history.md](review-history.md) — Full dated log of past commit-reviews/audits with verdicts, evidence, test counts (2026-07-08 → present). Most recent: 2026-08-24 "casillas por programa" (checklist-gate/skill-checklist-inject), NOT MERGEABLE — T1 unchecked block-counter persist defeats the max-2-blocks bound
- [chatroom-standards.md](chatroom-standards.md) — Permanent 15-rule enterprise standards for chatroom/apps/backend/src/ + violation baseline as of 2026-03-19
- [chatroom-frontend-design.md](chatroom-frontend-design.md) — Definitive design reference audit (option-b-cursor-style.html): confirmed bugs, contrast truth table, missing states, color system structure
- [chatroom-frontend-patterns.md](chatroom-frontend-patterns.md) — Frontend React source audit 2026-03-21: intentional patterns, open violations (T2/T3), scoring baseline 68/110
- [cicd-workflows.md](cicd-workflows.md) — GitHub Actions audit 2026-08-06: chatroom-ci gives false green (no frontend coverage), missing permissions/timeouts/pinning across all 3 workflows
