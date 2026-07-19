# Memory Index — unmassk-toolkit-ultron

- [chatroom-frontend.md](chatroom-frontend.md) — Agent Chatroom frontend patterns, scroll behavior, icon mapping, build commands
- [implementation-patterns.md](implementation-patterns.md) — Elysia WS upgrade hook context shape (headers access, rejection pattern); opt-in `atomic` param pattern on open_no_follow_symlink()
- [chatroom-bridge.md](chatroom-bridge.md) — claude-bridge.ts patterns: singleton guard, WS reconnect, ring buffer, inline types, HTTP auth
- [chatroom-backend-hardening.md](chatroom-backend-hardening.md) — Graceful shutdown, onError hook, env validation patterns in config.ts/index.ts
- [lessons.md](lessons.md) — Mistakes and fixes: Bun mock.module() leaks, scheduler state cleanup, DB-state assertions, Elysia WS patterns
- [unmassk-toolkit-python-entrypoints.md](unmassk-toolkit-python-entrypoints.md) — bin/hooks sys.path variants (3 shapes), encoding_guard.py fail-open UTF-8 pattern (issue #52)
- [design-family-skills.md](design-family-skills.md) — pattern for unmassk-design family skills: decision table + condensed references/ + attribution, verification gate, parallel-agent file scope
- [electronics-scripts.md](electronics-scripts.md) — unmassk-electronics scripts/*.py: pure-decision-function split, setup_cad_env.py reuse, ssh self-verify scope, sensor_gate.py tolerance-band gate
- [boot-timeline-scope.md](boot-timeline-scope.md) — boot TIMELINE's real git-log call lives in boot_git_checks.py (not boot_render.py); --all needs the same exclude_remote guard as extract_glossary()
- [design-gate-linter.md](design-gate-linter.md) — design_gate.py SKILL.md corpus shape, pyyaml precedent, 3 false-positive traps (trailing punctuation, inverted contradiction logic, homonym/stemming) found by real-repo verification
