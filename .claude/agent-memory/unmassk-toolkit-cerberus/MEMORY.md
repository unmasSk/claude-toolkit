# Memory Index — Cerberus (Code Reviewer)

- [conventions.md](conventions.md) — Project conventions: plugin structure, SKILL.md format requirements
- [false-positives.md](false-positives.md) — Patterns that looked suspicious but are intentional
- [anti-patterns.md](anti-patterns.md) — Recurring shell/Python/TS anti-patterns (ops-containers, unmassk-crew hooks, chatroom, session-start-boot.py refactor rounds 1-14 CLOSED 109/110; boot-freshness #49 LGTM; 2026-07-07 encoding_guard #52: MEMORY.md-points-to-uncommitted-file pattern added)
- 2026-07-08 CI-fix round (issue #52/#54, run 28922061708) LGTM: `%at` unification (boot_git_checks.py) + opt-in `log_stderr_on_failure` (git_helpers.py) + 140-site test encoding='utf-8' sweep. See [false-positives.md](false-positives.md) narrow-signature-run_git-fake entry.
- 2026-07-08 issue #55 `%at` unification round 2 (gc.py + doctor.py `parse_date()` + bootstrap_commits.py) LGTM 2 nitpicks, 0 blockers, 6/6 contract tests green. See [false-positives.md](false-positives.md) test_doctor_after_install `-k`-filter flake entry (pre-existing, not caused by this diff).
- 2026-07-08 issue #55 adversarial-fix round (Argus SEC-LOW-001/002 + Moriarty BUG-4/5/3, diff 0dd396d..HEAD) LGTM 0 issues, 1 suggestion, 2 nitpicks. `lib/date_parsing.py` extracted (centralizes the 2 duplicates, closes prior Yoda Architecture gap). `check_gc_status()` 3-tuple→4-tuple, single call site (`run_doctor`), unpacking correct. 22/22 new contract tests green + 84/84 combined suite green.
- 2026-07-08 issue #55 closing round (diff 7fe8f9f..HEAD): 3/3 prior findings RESOLVED (isascii guard, comment cleanup, docstring). LGTM 1 suggestion (time_ago length-guard asymmetry), 0 nitpicks. See [anti-patterns.md](anti-patterns.md) "mirror functions drift" entry.
- [chatroom-standards.md](chatroom-standards.md) — Permanent 15-rule enterprise standards for chatroom/apps/backend/src/ + violation baseline as of 2026-03-19
- [chatroom-frontend-design.md](chatroom-frontend-design.md) — Definitive design reference audit (option-b-cursor-style.html): confirmed bugs, contrast truth table, missing states, color system structure
- [chatroom-frontend-patterns.md](chatroom-frontend-patterns.md) — Frontend React source audit 2026-03-21: intentional patterns, open violations (T2/T3), scoring baseline 68/110
