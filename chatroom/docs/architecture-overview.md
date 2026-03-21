# Architecture Overview

## What This Is

A real-time multi-agent chatroom backend. Human users connect over WebSocket. Claude Code agents are invoked as `claude -p` subprocesses when @mentioned. All messages persist in SQLite. Agents can @mention each other, forming autonomous conversation chains.

## Runtime

| Component      | Technology           |
|----------------|----------------------|
| Runtime        | Bun 1.x              |
| HTTP + WS      | Elysia 1.4.28        |
| Database       | bun:sqlite (WAL)     |
| Logging        | pino (structured)    |
| Validation     | Elysia typebox (HTTP), Zod (WS) |

## Request Flow

```
Browser / WS client
      |
      |  POST /api/auth/token    → get one-time token
      |  POST /api/rooms/:id/invite  → register agents in room
      |
      v
  WS /ws/:roomId?token=<uuid>
      |
      |  open()  — origin check, rate limit, token consume, room_state delivery
      |
      v
  message()  — parse, rate limit, route by msg.type
      |
      |  send_message → insertMessage → broadcastSync → extractMentions → invokeAgents
      |  invoke_agent → insertMessage → broadcastSync → invokeAgent
      |  load_history → getMessagesBefore → history_page
      |
      v
  agent-invoker (async, fire-and-forget)
      |
      |  scheduleInvocation → queue / semaphore
      |
      v
  Bun.spawn(['claude', '-p', prompt, ...])
      |
      |  stdout NDJSON → stream-parser → text / tool_use / result events
      |
      v
  insertMessage (agent reply) → broadcast via message-bus → all WS clients
      |
      v
  agent reply may contain @mentions → extractMentions → invokeAgents (chained)
```

## Module Map

```
src/
  index.ts              — server bootstrap, graceful shutdown
  config.ts             — all env vars, validated at startup
  logger.ts             — pino factory
  utils.ts              — ID generation, timestamp, DB row mappers, safeMessage
  types.ts              — DB row shapes (snake_case)

  routes/
    api.ts              — REST endpoints (rooms, agents, auth, invite)
    ws.ts               — WebSocket handler (open/message/close)

  services/
    agent-invoker.ts    — subprocess spawn, queue, semaphore, prompt builders
    agent-registry.ts   — loads .md frontmatter, builds AgentConfig map
    auth-tokens.ts      — one-time token store, brute-force detection
    message-bus.ts      — broadcast helper (async + sync variants)
    mention-parser.ts   — extracts @mentions from message content
    rate-limiter.ts     — token-bucket factory
    stream-parser.ts    — parses NDJSON from claude subprocess stdout

  db/
    connection.ts       — SQLite singleton, WAL/busy_timeout pragmas
    schema.ts           — CREATE TABLE + seed default room
    queries.ts          — all SQL query functions
```

## Concurrency Model

The server is single-process. Agents run as external subprocesses (`Bun.spawn`). The concurrency controls inside `agent-invoker.ts` are all in-process:

- `activeInvocations` — Map tracking running subprocesses by `agentName:roomId`
- `inFlight` — Set preventing duplicate simultaneous invocations per agent per room
- `pendingQueue` — Array for overflow (max 10 entries)
- `MAX_CONCURRENT_AGENTS` — global cap (default 3; tune via env)

The semaphore pattern: when a slot opens, `drainQueue()` fires automatically.

## Security Perimeter

All security measures applied at the boundary before any business logic:

1. Origin header checked in `open()` — rejects if not in `WS_ALLOWED_ORIGINS`
2. WS upgrade rate limit — 50/second global
3. Auth token consumed on first WS upgrade (one-time-use)
4. Per-connection message rate limit — 5 messages per 10 seconds
5. Per-room connection cap — 20 connections maximum
6. All user content sanitized via `sanitizePromptContent()` before entering a prompt
7. Agent `sessionId` stripped before any broadcast (`safeMessage`, `stripSessionId`)
8. Banned tools (`Bash`, `computer`) never passed to `claude` subprocess

See `security.md` for the full threat model.
