# Module Reference

## index.ts

Server entry point.

**Startup sequence (order matters):**
1. `initializeSchema()` — creates tables, seeds default room
2. `loadAgentRegistry()` — reads agent `.md` files from disk
3. `new Elysia()` — mounts CORS, error handler, API routes, WS routes, health check
4. `app.listen()` — binds to `HOST:PORT`

**Shutdown** (SIGTERM or SIGINT):
1. `app.server?.stop()` — closes all WS connections
2. `drainActiveInvocations()` — waits for in-progress agent subprocesses
3. WAL checkpoint — `PRAGMA wal_checkpoint(TRUNCATE)`
4. `db.close()`
5. Forced exit after 5s timeout

**Exports:** `app` (Elysia singleton), `App` (type)

The app singleton export is consumed by `message-bus.ts` to call `app.server!.publish()` for broadcast.

**Swagger** — mounted only in `NODE_ENV=development` at `/docs`. Never in production or test.

**Static files** — served only in `NODE_ENV=production` from `../frontend/dist`.

---

## config.ts

Single source of truth for all configuration. Never read `process.env` directly anywhere else.

**Exported constants:**

| Export                  | Env var              | Default                        | Notes                                      |
|-------------------------|----------------------|--------------------------------|--------------------------------------------|
| `PORT`                  | `PORT`               | `3000`                         | Integer, 1–65535                           |
| `HOST`                  | `HOST`               | `127.0.0.1`                    | Loopback by default                        |
| `DB_PATH`               | `DB_PATH`            | `<src>/../data/chatroom.db`    | Path to SQLite file                        |
| `NODE_ENV`              | `NODE_ENV`           | `development`                  | `development \| production \| test`        |
| `AGENT_DIR`             | `AGENT_DIR`          | Auto-resolved from `~/.claude` | Directory with agent `.md` files           |
| `MAX_CONCURRENT_AGENTS` | `MAX_CONCURRENT_AGENTS` | `3`                         | Integer, 1–20                              |
| `AGENT_TIMEOUT_MS`      | —                    | `300000` (5 min)               | Subprocess kill timeout                    |
| `AGENT_HISTORY_LIMIT`   | —                    | `20`                           | Messages injected into each agent prompt   |
| `ROOM_STATE_MESSAGE_LIMIT` | —               | `50`                           | Messages in initial `room_state`           |
| `WS_ALLOWED_ORIGINS`    | `WS_ALLOWED_ORIGINS` | `http://localhost:4201,...`    | Comma-separated, validated as URLs         |
| `AGENT_VOICE`           | —                    | Hardcoded map                  | Per-agent persona injected into system prompt |

**Validation:** Invalid env vars call `process.exit(1)` at startup. There are no silent defaults for bad values.

**`AGENT_DIR` resolution order:**
1. `AGENT_DIR` env var (validated to exist, symlinks resolved)
2. `~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-toolkit/*/agents` (highest version wins)
3. Relative fallback for development

**`WS_ALLOWED_ORIGINS` in dev/test:** An empty string `''` is appended to allow `wscat` and `curl` connections with no Origin header. Never in production.

---

## logger.ts

**Usage in every module:**
```ts
import { createLogger } from './logger.js';
const logger = createLogger('module-name');
logger.info({ key: value }, 'message');
```

Never use `console.log`. The `module` binding appears in every log line.

**Behavior by env:**
- `development` / `test`: pino-pretty to stderr (colored, human-readable)
- `production`: NDJSON to stderr (parseable by log aggregators)

**`LOG_LEVEL` env var:** `fatal | error | warn | info | debug | trace`. Defaults to `debug`. Invalid values cause `process.exit(1)` before the logger is created (writes raw JSON to stderr).

---

## utils.ts

Pure utility functions. No side effects.

| Function             | Purpose                                                            |
|----------------------|--------------------------------------------------------------------|
| `generateId()`       | 12 random bytes → base64url string (~16 chars). 96 bits, collision-safe for millions of messages. |
| `nowIso()`           | Current time as ISO 8601 string                                    |
| `mapMessageRow(row)` | `MessageRow` (snake_case) → `Message` (camelCase protocol type). Parses `metadata` JSON. |
| `mapAgentSessionRow(row)` | `AgentSessionRow` → `AgentStatus`                           |
| `mapRoomRow(row)`    | `RoomRow` → `Room`                                                 |
| `safeMessage(msg)`   | Strips `sessionId` from `msg.metadata`. Applied before any client broadcast. |

---

## types.ts

DB row shapes returned from `bun:sqlite` queries. Use snake_case column names. Services map these to camelCase protocol types via `utils.ts` mappers.

| Type               | Columns                                                                  |
|--------------------|--------------------------------------------------------------------------|
| `RoomRow`          | `id, name, topic, created_at`                                            |
| `MessageRow`       | `id, room_id, author, author_type, content, msg_type, parent_id, metadata (JSON string), created_at` |
| `AgentSessionRow`  | `agent_name, room_id, session_id, model, status, last_active, total_cost, turn_count` |

---

## db/connection.ts

Singleton SQLite connection.

```ts
import { getDb } from './db/connection.js';
const db = getDb(); // creates once, returns same instance thereafter
```

**Pragmas applied on first access:**
- `journal_mode = WAL` — allows concurrent reads while agents write
- `busy_timeout = 5000` — waits 5 seconds before throwing `SQLITE_BUSY`
- `synchronous = NORMAL` — safe with WAL, faster than FULL

The data directory is created automatically (`mkdirSync` with `recursive: true`).

---

## db/schema.ts

Creates tables and indexes if they don't exist. Seeds the `default` room.

Called once at startup from `index.ts`. Can also be run directly: `bun run src/db/schema.ts`.

See `database-schema.md` for full schema documentation.

---

## db/queries.ts

All SQL in one place. No SQL outside this file.

**Rooms:**
- `getRoomById(id)` → `RoomRow | null`
- `listRooms()` → `RoomRow[]` ordered by `created_at ASC`

**Messages:**
- `insertMessage(row)` — inserts one message
- `getRecentMessages(roomId, limit)` — latest N messages, returned in chronological order (double-ORDER trick)
- `getMessagesBefore(roomId, beforeId, limit)` — cursor-based pagination, returns DESC (callers must reverse)
- `getMessageCreatedAt(id)` → `string | null` — used by pagination to find the pivot timestamp
- `hasMoreMessagesBefore(roomId, beforeCreatedAt)` → `boolean` — infinite scroll indicator

**Agent sessions:**
- `getAgentSession(agentName, roomId)` → `AgentSessionRow | null`
- `listAgentSessions(roomId)` → `AgentSessionRow[]`
- `upsertAgentSession(row)` — INSERT OR UPDATE (updates `last_active` on conflict)
- `updateAgentStatus(agentName, roomId, status)` — sets status + `last_active`
- `incrementAgentCost(agentName, roomId, delta)` — atomic `total_cost = total_cost + delta`
- `incrementAgentTurnCount(agentName, roomId)` — atomic increment
- `clearAgentSession(agentName, roomId)` — sets `session_id = NULL` on stale session detection

---

## services/rate-limiter.ts

Token-bucket factory. One call creates one independent bucket map.

```ts
const check = createTokenBucket(max, windowMs);
if (!check('per-connection-key')) return 429;
```

**Algorithm:** On first request for a key, consume one token from `max`. On subsequent requests, refill proportionally to elapsed time. Returns `false` when bucket is empty.

Each limiter instance is isolated — the auth, invite, and WS buckets never interfere.

**Deployments in the codebase:**

| Location  | Bucket name       | Limit           | Scope                         |
|-----------|-------------------|-----------------|-------------------------------|
| `api.ts`  | `'auth-token'`    | 20 / 60s        | Global (intentional — spoofed IPs) |
| `api.ts`  | `'invite'`        | 20 / 60s        | Global                        |
| `ws.ts`   | per `connId`      | 5 / 10s         | Per connection                |
| `ws.ts`   | `'global'`        | 50 / 1s         | WS upgrade global             |

---

## services/auth-tokens.ts

In-memory token store for WS authentication. Tokens expire after 30 minutes.

**API:**

| Function            | Purpose                                                            |
|---------------------|--------------------------------------------------------------------|
| `validateName(raw)` | Returns cleaned name or `null` if invalid, empty, or reserved     |
| `issueToken(name)`  | Returns `{ token, expiresAt }` or `null` if store at 10,000 cap   |
| `peekToken(token)`  | Validates without consuming. Used by `POST /invite` to check auth  |
| `validateToken(token)` | Validates AND consumes (one-time-use). Used by WS `open()`.   |
| `getReservedAgentNames()` | Set of names that cannot be issued — agent names + `claude` + `system` |

**Reserved names:** All known agent names from the shared registry, plus `claude` and `system`. The name `user` is explicitly NOT reserved — it is the default frontend identity.

**Brute-force detection:** Auth failures are tracked by the first 8 characters of the presented token. After 10 failures in 60 seconds from the same prefix, a `logger.error` fires (alerting hook). The map is capped at 5,000 entries to prevent memory exhaustion.

**GC:** Expired tokens and stale failure windows are cleaned every 10 minutes (timer has `.unref()` so it does not keep the process alive).

---

## services/agent-registry.ts

Loads and merges agent configuration from two sources:
1. Static `AGENT_BY_NAME` map from `@agent-chatroom/shared` (base definitions)
2. YAML frontmatter in `.md` files under `AGENT_DIR` (model, color, tools)

**`AgentConfig`** extends `AgentDefinition` with:
- `allowedTools: string[]` — from frontmatter, banned tools already removed
- `invokable: boolean` — true only if agent has at least one allowed tool AND the static definition marks it invokable

**Banned tools** (never allowed regardless of frontmatter): `Bash`, `computer`. Enforced here and again in `agent-invoker.ts` (belt-and-suspenders).

**API:**
- `loadAgentRegistry()` — builds and caches the registry. Call once at startup.
- `getAgentConfig(name)` — case-insensitive lookup. Returns `null` if unknown.
- `getAllAgents()` — full registry as array.

The registry is loaded lazily if accessed before `loadAgentRegistry()` is called (for test isolation).

---

## services/mention-parser.ts

Extracts `@name` mentions from message content.

```ts
const mentions = extractMentions(content); // returns Set<string>
```

**Rules:**
- Lowercases all names
- Deduplicates automatically (returns `Set`)
- Ignores email-like patterns: `user@bilbo.com` does not trigger `@bilbo`
- Never returns `user`, `system`, `claude`, `everyone`
- Only returns names that exist in the agent registry
- Does not enforce turn limits (that is `agent-invoker.ts`)

---

## services/stream-parser.ts

Parses NDJSON lines from `claude -p --output-format stream-json --verbose`.

```ts
const events = parseStreamLine(line); // returns StreamEvent[]
```

**Event types returned:**

| Type          | When                                              |
|---------------|---------------------------------------------------|
| `TextEvent`   | `assistant` event with `text` content block       |
| `ToolUseEvent`| `assistant` event with `tool_use` content block   |
| `ResultEvent` | `result` event — final output with all metrics    |

**Whitelist:** Only `assistant` and `result` events are processed. Everything else (`progress`, `hook_started`, `hook_response`, `system`) is discarded silently.

**`ResultEvent` fields:** `result, sessionId, costUsd, success, durationMs, numTurns, inputTokens, outputTokens, cacheReadTokens, contextWindow, permissionDenials`.

`success` is derived from `subtype === 'success'`. Context window is inferred from model name when the CLI reports 0.

---

## services/message-bus.ts

Broadcasts server messages to all WebSocket clients in a room.

**Two variants:**

| Function            | When to use                                                      |
|---------------------|------------------------------------------------------------------|
| `broadcast(roomId, event)` | From async contexts (agent-invoker). Lazy-imports app singleton. |
| `broadcastSync(roomId, event, server)` | From WS handlers where server is already in scope. |

Both strip `sessionId` from message metadata before sending (`stripSessionId`).

The lazy import in `broadcast` avoids circular imports at module load time — `agent-invoker.ts` → `message-bus.ts` → `index.ts` (app) would cycle if imported at the module level.

---

## services/agent-invoker.ts

The core invocation engine. See `agent-invocation-pipeline.md` for full flow documentation.

**Exported functions:**

| Function                    | Purpose                                               |
|-----------------------------|-------------------------------------------------------|
| `invokeAgents(roomId, names, trigger, turns, priority)` | Invoke multiple agents (from @everyone or multiple @mentions). Staggers by 600ms. |
| `invokeAgent(roomId, name, prompt)` | Invoke single agent (from `invoke_agent` WS message) |
| `drainActiveInvocations()`  | Wait for all in-flight subprocesses. Used by graceful shutdown. |
| `pauseInvocations(roomId)`  | Halt scheduling for a room (`@everyone stop`)         |
| `resumeInvocations(roomId)` | Resume scheduling for a room                          |
| `isPaused(roomId)`          | Check pause state for a room                          |
| `clearQueue(roomId)`        | Remove all pending queue entries for a room           |
| `sanitizePromptContent(s)`  | Strip injection markers + normalize Unicode           |
| `buildPrompt(roomId, trigger, historyLimit?)` | Builds the full structured prompt     |
| `validateSessionId(id)`     | Returns UUID string or null (format validation)        |
