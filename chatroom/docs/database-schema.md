# Database Schema

## Engine

SQLite via `bun:sqlite`. WAL journal mode, `busy_timeout = 5000`, `synchronous = NORMAL`.

The database file is at `DB_PATH` (default: `<backend>/data/chatroom.db`). The data directory is created automatically on first access.

Tests use in-memory databases (`:memory:`) — never the file on disk.

## Tables

### rooms

```sql
CREATE TABLE IF NOT EXISTS rooms (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  topic       TEXT DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

| Column       | Type | Notes                              |
|--------------|------|------------------------------------|
| `id`         | TEXT | Application-assigned (e.g., `default`) |
| `name`       | TEXT | Display name                       |
| `topic`      | TEXT | Optional description               |
| `created_at` | TEXT | ISO 8601 via SQLite `datetime('now')` |

The `default` room is seeded at startup: `INSERT OR IGNORE INTO rooms VALUES ('default', 'general', 'Agent chatroom')`.

### messages

```sql
CREATE TABLE IF NOT EXISTS messages (
  id          TEXT PRIMARY KEY,
  room_id     TEXT NOT NULL REFERENCES rooms(id),
  author      TEXT NOT NULL,
  author_type TEXT NOT NULL CHECK(author_type IN ('agent', 'human', 'system')),
  content     TEXT NOT NULL,
  msg_type    TEXT NOT NULL DEFAULT 'message'
              CHECK(msg_type IN ('message', 'tool_use', 'system')),
  parent_id   TEXT REFERENCES messages(id),
  metadata    TEXT DEFAULT '{}',
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

| Column        | Type | Notes                                           |
|---------------|------|-------------------------------------------------|
| `id`          | TEXT | base64url random ID from `generateId()`         |
| `room_id`     | TEXT | FK → `rooms.id`                                 |
| `author`      | TEXT | Agent name, human name, or `'system'`           |
| `author_type` | TEXT | `agent`, `human`, or `system`                   |
| `content`     | TEXT | Message body                                    |
| `msg_type`    | TEXT | `message`, `tool_use`, or `system`              |
| `parent_id`   | TEXT | Self-referencing FK for threading (nullable)    |
| `metadata`    | TEXT | JSON string. Agent messages include `sessionId`, `costUsd`, `model`, `durationMs`, `numTurns`, `inputTokens`, `outputTokens`, `contextWindow`. Stripped of `sessionId` before broadcast. |
| `created_at`  | TEXT | ISO 8601 string                                 |

**Indexes:**
- `idx_messages_room` on `(room_id, created_at)` — used by `getRecentMessages` and pagination queries
- `idx_messages_parent` on `(parent_id)` — used for threading lookups

### agent_sessions

```sql
CREATE TABLE IF NOT EXISTS agent_sessions (
  agent_name  TEXT NOT NULL,
  room_id     TEXT NOT NULL REFERENCES rooms(id),
  session_id  TEXT,
  model       TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'idle'
              CHECK(status IN ('idle', 'thinking', 'tool-use', 'done', 'out', 'error')),
  last_active TEXT,
  total_cost  REAL DEFAULT 0.0,
  turn_count  INTEGER DEFAULT 0,
  PRIMARY KEY (agent_name, room_id)
);
```

| Column       | Type    | Notes                                                     |
|--------------|---------|-----------------------------------------------------------|
| `agent_name` | TEXT    | Lowercase agent name                                      |
| `room_id`    | TEXT    | FK → `rooms.id`                                           |
| `session_id` | TEXT    | Claude session ID for `--resume`. Nullable. Validated as UUID before use. Set to NULL on stale session detection. |
| `model`      | TEXT    | Model ID (e.g., `claude-opus-4-5`)                        |
| `status`     | TEXT    | `idle | thinking | tool-use | done | out | error`         |
| `last_active`| TEXT    | ISO 8601, updated on every status change and cost update  |
| `total_cost` | REAL    | Cumulative cost in USD. Updated atomically via `total_cost + delta`. |
| `turn_count` | INTEGER | Number of completed invocations for this agent in this room |

**Primary key:** `(agent_name, room_id)`. One session per agent per room.

## Pagination Pattern

Cursor-based. The cursor is a message ID, not an offset.

```sql
-- getMessagesBefore: returns DESC (caller must reverse)
SELECT * FROM messages
WHERE room_id = ?
  AND created_at < (SELECT created_at FROM messages WHERE id = ?)
ORDER BY created_at DESC
LIMIT ?

-- hasMoreMessagesBefore
SELECT COUNT(*) as count FROM messages
WHERE room_id = ? AND created_at < ?
```

The `before` cursor ID is resolved to a `created_at` timestamp via `getMessageCreatedAt()`. The pagination queries use the timestamp, not the ID, as the boundary condition.

`getRecentMessages` uses a double-ORDER trick to return the latest N messages in chronological order:

```sql
SELECT * FROM (
  SELECT * FROM messages
  WHERE room_id = ?
  ORDER BY created_at DESC
  LIMIT ?
) ORDER BY created_at ASC
```

## Concurrency Notes

SQLite WAL mode allows concurrent reads while a write is in progress. `busy_timeout = 5000` prevents `SQLITE_BUSY` errors when multiple agents write messages simultaneously. Cost updates use `total_cost = total_cost + delta` (not `SET total_cost = $value`) to avoid lost update races.
