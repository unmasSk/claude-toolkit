# MEMORY.md — Dante (Test Engineering Agent)

## Topic Files

- [conventions.md](conventions.md) — Test conventions for chatroom/apps/backend (bun:test, ESM, SQLite, WebSocket)
- [mock-patterns.md](mock-patterns.md) — Mock patterns that work (bun:test, SQLite in-memory, ESM module mocking, WS)
- [edge-cases.md](edge-cases.md) — Recurring edge cases (LIKE injection, RBAC, parameterized queries)
- [frontend-conventions.md](frontend-conventions.md) — Vitest + @testing-library/react conventions for chatroom/apps/frontend (jsdom, Zustand isolation, FakeWebSocket class pattern, CSS mocking)
- [unmassk-toolkit-python-test-conventions.md](unmassk-toolkit-python-test-conventions.md) — pytest conventions for unmassk-toolkit itself (importlib for hyphenated hook files, as_claude gotchas, repo/boot helpers, sys.path cwd-independence for git-root bin/ imports, symlink-skip-guard exhaustive count method)
- [crown-retraction-design-notes.md](crown-retraction-design-notes.md) — Crown-retraction multi-crown edge case gotcha (naive per-commit patch resurfaces superseded crowns)
- [skill-router-contract-notes.md](skill-router-contract-notes.md) — Per-message skill-router contract ("[skill-router]" marker), what the hardening pass still owes
- [boot-stdout-banner-contract-notes.md](boot-stdout-banner-contract-notes.md) — session-start-boot.py unconditional stdout banner + 5 rounds of audit-hardening findings across bin/git-memory-*.py (symlink read/write, control-byte injection, manifest.json, path traversal, ANSI injection)
- [feat-boot-freshness-contract-notes.md](feat-boot-freshness-contract-notes.md) — boot memory freshness (multi-machine, issue #49) acceptance contract: fixture design, RED baseline, marker-naming pitfall
- [encoding-contract-notes.md](encoding-contract-notes.md) — issue #52 cp1252 contract: parent-decode gotcha (child RC=0 can still be RED), `--runxfail` verification pattern, AST-based open()-encoding sweep
- [issue-55-date-parsing-contract-notes.md](issue-55-date-parsing-contract-notes.md) — issue #55 %aI/fromisoformat fragile-date contract; bootstrap_commits.py reconciled back to %aI (presentation-only field, never parsed)
