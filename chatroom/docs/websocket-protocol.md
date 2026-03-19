# WebSocket Protocol

## Connection

```
WS /ws/:roomId?token=<uuid>
```

- `roomId` — must match an existing room ID (e.g., `default`)
- `token` — one-time auth token from `POST /api/auth/token`
- Max payload: 64KB per frame (enforced by uWebSockets before the handler runs)

## Connection Lifecycle

**On open:**
1. Server validates origin, rate limit, room cap, token
2. Server sends `user_list_update` to all room subscribers
3. Server sends `room_state` to the new connection

**On close:**
1. Server removes connection from `connStates` and `roomConns`
2. Server broadcasts updated `user_list_update` to remaining subscribers
3. Server unsubscribes connection from room topic

## Client → Server Messages

All messages must be valid JSON matching `ClientMessageSchema` (Zod, from `@agent-chatroom/shared`). Invalid JSON or schema violations return an `error` message.

### send_message

```json
{
  "type": "send_message",
  "content": "Hello @bilbo, what do you see?"
}
```

- `content` — the message text. Author is set server-side (never accepted from client).
- If content contains `@agentName`, the mentioned agent(s) are invoked.
- If content contains `@everyone`, all agents in the room are invoked. See below.

### invoke_agent

```json
{
  "type": "invoke_agent",
  "agent": "bilbo",
  "prompt": "Describe the latest diff."
}
```

- `agent` — must be a known, invokable agent name.
- `prompt` — the prompt text. Sanitized before use.
- The prompt is persisted as a human message, then the agent is invoked.

### load_history

```json
{
  "type": "load_history",
  "before": "<message-id>",
  "limit": 50
}
```

- `before` — cursor message ID. Returns messages older than this ID.
- `limit` — capped at 100 server-side.
- Returns a `history_page` response.

## Server → Client Messages

All messages are JSON. The `type` field identifies the payload shape.

### room_state

Sent once on connection, contains full initial state.

```json
{
  "type": "room_state",
  "room": { "id": "default", "name": "general", "topic": "...", "createdAt": "..." },
  "messages": [ /* recent messages */ ],
  "agents": [ /* AgentStatus objects, sessionId always null */ ],
  "connectedUsers": [ { "name": "alice", "connectedAt": "..." } ]
}
```

### new_message

Broadcast to all subscribers when any message is inserted.

```json
{
  "type": "new_message",
  "message": {
    "id": "...",
    "roomId": "default",
    "author": "bilbo",
    "authorType": "agent",
    "content": "...",
    "msgType": "message",
    "parentId": null,
    "metadata": { "costUsd": 0.0012, "model": "claude-opus-4-5", "durationMs": 3200, "numTurns": 2, "inputTokens": 1500, "outputTokens": 200, "contextWindow": 200000 },
    "createdAt": "2026-03-19T12:00:00.000Z"
  }
}
```

`metadata.sessionId` is **always stripped** before broadcast. It is stored in the DB for `--resume` but never sent to clients.

**`authorType` values:** `human | agent | system`
**`msgType` values:** `message | tool_use | system`

### tool_event

Emitted while an agent is running, throttled to one broadcast per 500ms per agent.

```json
{
  "type": "tool_event",
  "id": "...",
  "agent": "bilbo",
  "tool": "Read",
  "description": "Reading file.ts"
}
```

### agent_status

Broadcast when an agent's status changes.

```json
{
  "type": "agent_status",
  "agentName": "bilbo",
  "roomId": "default",
  "status": "thinking",
  "model": "claude-opus-4-5",
  "sessionId": null,
  "lastActive": "2026-03-19T12:00:00.000Z",
  "totalCost": 0.0024,
  "turnCount": 3
}
```

**`status` values:** `idle | thinking | tool-use | done | out | error`

### user_list_update

Broadcast when any connection opens or closes.

```json
{
  "type": "user_list_update",
  "connectedUsers": [
    { "name": "alice", "connectedAt": "2026-03-19T11:55:00.000Z" }
  ]
}
```

Duplicate names (same browser tab double-connecting in React StrictMode) are deduplicated by name.

### history_page

Response to `load_history`.

```json
{
  "type": "history_page",
  "messages": [ /* older messages, chronological order */ ],
  "hasMore": true
}
```

### error

Sent for validation failures, auth errors, rate limits, and other non-fatal errors. Connection stays open unless the error type requires closing.

```json
{
  "type": "error",
  "message": "Rate limit exceeded. Max 5 messages per 10 seconds.",
  "code": "RATE_LIMIT"
}
```

**`code` values:** `UNAUTHORIZED | ROOM_NOT_FOUND | ROOM_FULL | UPGRADE_RATE_LIMIT | RATE_LIMIT | PARSE_ERROR | VALIDATION_ERROR | UNKNOWN_AGENT | DB_ERROR`

## @everyone Directives

A message starting with `@everyone` triggers special handling:

| Directive pattern                                  | Effect                                          |
|----------------------------------------------------|-------------------------------------------------|
| `@everyone <any text>`                             | All room agents invoked with the directive text |
| `@everyone stop` (or `para`, `callaos`, `silence`, `quiet`) | Queue cleared, invocations paused for room |

After a stop directive, the room remains paused until a human sends any non-`@everyone` message. Individual `@mentions` in the same message as `@everyone` are ignored.

## Pub/Sub Topics

Each room uses the pub/sub topic `room:{roomId}`. Subscriptions are managed automatically:
- `ws.subscribe(topic)` in `open()`
- `ws.unsubscribe(topic)` in `close()`
- `ws.publish(topic, data)` broadcasts to all subscribers except the sender

Due to Elysia 1.4.28 not implementing `publishToSelf`, `ws.send()` is also called directly for self-delivery in critical paths (message delivery on send, room_state on connect).
