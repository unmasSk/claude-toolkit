# Configuration

All configuration is in `src/config.ts`. Never read `process.env` directly in application code.

Invalid env var values call `process.exit(1)` at startup with a structured error log. There are no silent coercions for out-of-range or unrecognized values.

## Environment Variables

| Variable                | Default                                | Required | Description                              |
|-------------------------|----------------------------------------|----------|------------------------------------------|
| `PORT`                  | `3000`                                 | No       | HTTP/WS listen port (1–65535)            |
| `HOST`                  | `127.0.0.1`                            | No       | Bind address. Use `0.0.0.0` for Docker/LAN. |
| `NODE_ENV`              | `development`                          | No       | `development \| production \| test`      |
| `DB_PATH`               | `<src>/../data/chatroom.db`            | No       | SQLite file path. Created if missing.    |
| `AGENT_DIR`             | Auto-resolved (see below)              | No       | Directory containing agent `.md` files   |
| `MAX_CONCURRENT_AGENTS` | `3`                                    | No       | Max simultaneous agent subprocesses (1–20). Raise to 5+ only on machines with >16GB RAM. |
| `WS_ALLOWED_ORIGINS`    | `http://localhost:4201,http://127.0.0.1:4201` | No | Comma-separated list of allowed WebSocket origins. Each must be a valid `http://` or `https://` URL. |
| `LOG_LEVEL`             | `debug`                                | No       | `fatal \| error \| warn \| info \| debug \| trace` |

## AGENT_DIR Resolution

If `AGENT_DIR` is not set, the server resolves it in this order:

1. `~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-toolkit/*/agents` — glob, highest version wins
2. `../../../../../../agents` relative to `src/` (development monorepo layout)
3. `../agents` relative to `src/`

If the explicit `AGENT_DIR` env var points to a non-existent directory, the server exits with an error.

## WS_ALLOWED_ORIGINS in Development

In `development` and `test` environments, an empty string `''` is appended to `WS_ALLOWED_ORIGINS`. This allows `wscat`, `curl`, and test harnesses that send no `Origin` header to connect. A warning is logged:

```
WS upgrade accepts connections with no Origin header — set NODE_ENV=production to enforce origin checking
```

In `production`, this bypass is disabled regardless of what `WS_ALLOWED_ORIGINS` contains.

## Fixed Constants (not env-configurable)

| Constant                   | Value          | Location        |
|----------------------------|----------------|-----------------|
| `AGENT_TIMEOUT_MS`         | 300,000 (5min) | `config.ts`     |
| `AGENT_HISTORY_LIMIT`      | 20 messages    | `config.ts`     |
| `ROOM_STATE_MESSAGE_LIMIT` | 50 messages    | `config.ts`     |
| Token TTL                  | 30 minutes     | `auth-tokens.ts`|
| Token store cap            | 10,000 tokens  | `auth-tokens.ts`|
| Max pending queue          | 10 entries     | `agent-invoker.ts` |
| Max connections per room   | 20             | `ws.ts`         |
| Max agent response size    | 256KB          | `agent-invoker.ts` |
| Max trigger content        | 16,000 bytes   | `agent-invoker.ts` |
| WS max payload             | 64KB           | `ws.ts`         |
| Rate limit: /auth/token    | 20 / 60s       | `api.ts`        |
| Rate limit: /invite        | 20 / 60s       | `api.ts`        |
| Rate limit: WS messages    | 5 / 10s        | `ws.ts`         |
| Rate limit: WS upgrades    | 50 / 1s        | `ws.ts`         |
| Agent chain turn limit     | 5 turns/agent  | `agent-invoker.ts` |
| Tool broadcast throttle    | 500ms          | `agent-invoker.ts` |
| Rate limit retry delay     | 12 seconds     | `agent-invoker.ts` |

## Running with Custom Config

```bash
# Development with custom port
PORT=3001 bun run dev

# Production
NODE_ENV=production PORT=3000 HOST=0.0.0.0 \
  DB_PATH=/data/chatroom.db \
  WS_ALLOWED_ORIGINS=https://app.example.com \
  bun run start

# Test with explicit agent directory
NODE_ENV=test AGENT_DIR=/path/to/agents bun test
```
