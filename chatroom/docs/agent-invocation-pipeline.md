# Agent Invocation Pipeline

## Trigger Points

Agents are invoked from three places:

| Trigger                  | Source                     | Handler                                  |
|--------------------------|----------------------------|------------------------------------------|
| `@agentName` in message  | WS `send_message`          | `extractMentions` → `invokeAgents`       |
| `@everyone` in message   | WS `send_message`          | `listAgentSessions` → `invokeAgents`     |
| `invoke_agent` message   | WS `invoke_agent`          | `invokeAgent`                            |
| Agent reply with @mention| `spawnAndParse` completion | `extractMentions` → `invokeAgents`       |

## Scheduling Flow

```
invokeAgents(roomId, names, trigger, turns, priority)
  → for each name: setTimeout(scheduleInvocation, delay * 600ms)
  → staggered to avoid API rate limit spikes

scheduleInvocation(roomId, name, context, isRetry, priority)
  → if room is paused (@everyone stop): drop silently
  → if agent:room key is in inFlight:
      → try to merge into existing pending queue entry for same agent+room
      → if no existing entry and queue < 10: enqueue
      → else: post system message "cannot queue"
  → if activeInvocations.size >= MAX_CONCURRENT_AGENTS:
      → try to merge into existing pending queue entry
      → if no existing entry and queue < 10: enqueue
      → else: post system message "cannot queue"
  → else: runInvocation(...)

runInvocation(roomId, name, context, isRetry)
  → inFlight.add("agent:room")
  → activeInvocations.set("agent:room", doInvoke(...))
  → on completion: inFlight.delete, activeInvocations.delete, drainQueue()
```

Priority entries (`priority=true`, human-originated) go to the front of `pendingQueue`. Agent-chain entries go to the back.

## Invocation Execution (doInvoke)

```
doInvoke(roomId, agentName, context, isRetry)
  → getAgentConfig(agentName)       -- fail-closed if unknown or not invokable
  → filter allowedTools by BANNED_TOOLS   -- belt-and-suspenders
  → getAgentSession(agentName, roomId)    -- find existing --resume session
  → validateSessionId(session_id)         -- UUID format check
  → if isRetry: sessionId = null          -- no --resume on retries
  → updateStatusAndBroadcast(thinking)
  → buildPrompt(roomId, trigger, historyLimit?)
  → buildSystemPrompt(agentName, role, isRespawn?)
  → spawnAndParse(...)
```

## Subprocess Spawn

```
Bun.spawn([
  'claude',
  '-p', prompt,
  '--model', model,
  '--append-system-prompt', systemPrompt,
  '--output-format', 'stream-json',
  '--verbose',
  '--allowedTools', 'Tool1,Tool2,...',
  '--permission-mode', 'auto',
  '--resume', sessionId,   // only if valid session exists
])
```

Shell string concatenation is never used. Args are always an array.

On Unix, `detached: true` creates a process group so the timeout kill (`process.kill(-pid, 'SIGTERM')`) reaches all child processes. On Windows, `detached` is not set (it breaks in Bun 1.3.11).

**Timeout:** 5 minutes (`AGENT_TIMEOUT_MS`). After timeout, the process or process group is killed.

## Stream Parsing

`stdout` is read line-by-line as NDJSON. `stderr` is drained in a background task and inspected after completion. Only `assistant` and `result` event types are processed; all others are discarded.

For each `result` event, the invoker captures:
- `result` — the agent's text response
- `sessionId` — for `--resume` on the next invocation
- `costUsd`, `durationMs`, `numTurns`, `inputTokens`, `outputTokens`, `contextWindow`, `permissionDenials`

## Post-Invocation Paths

After `spawnAndParse` completes:

**Success (has result, non-empty text, not "skip"):**
1. Truncate response if > 256KB
2. `insertMessage` with agent's response and full metrics in metadata
3. `broadcast` to all room subscribers (`sessionId` stripped by message-bus)
4. `extractMentions` from response — up to 5 chained turns per agent per chain
5. `upsertAgentSession` with new `sessionId` and `status=done`
6. `incrementAgentCost` (atomic), `incrementAgentTurnCount`

**SKIP response:** Agent returned exactly `"skip"` → suppress message, set `status=done`.

**No result / empty response:**
- Check stderr for `429` / `rate limit` / `overloaded` → retry once after 12 seconds
- Otherwise: post system message "returned no response"

**Error result (success=false):**
- Check for stale session signals: `"No conversation found"`, `"conversation not found"`, `"prompt is too long"`
- Stale/overflow: `clearAgentSession`, schedule one retry with `isRetry=true`
- Context overflow: post visible respawn announcement, set `isRespawn=true` on context (causes next invocation to fetch 2000 history messages for orientation)
- Other error: post system message with error text

## Turn Limits (Agent Chains)

Each invocation chain tracks `agentTurns: Map<string, number>`. When an agent's response mentions another agent, the turn count for the mentioned agent is incremented. Agents with 5 or more turns are blocked from further chained invocations. A system message announces which agents were blocked.

Self-mentions are silently ignored.

## Pause / Resume

`@everyone stop` (and variants: `para`, `callaos`, `silence`, `quiet`) triggers:
1. `clearQueue(roomId)` — removes all pending entries for the room
2. `pauseInvocations(roomId)` — adds roomId to `_pausedRooms`

Any subsequent non-`@everyone` human message calls `resumeInvocations(roomId)`.

Pause state is per-room. An `@everyone stop` in room A does not affect room B.

## @everyone Behavior

When `@everyone` is present in a message:
1. The directive text (everything after `@everyone`) is sanitized and stored as a system message with the prefix `[DIRECTIVE FROM USER — ALL AGENTS MUST OBEY]`
2. All agents with sessions in the room are invoked via `invokeAgents`
3. Individual `@mentions` in the same message are **skipped** (already handled by the broadcast)
4. If `@everyone stop`, no invocations occur — only queue clear and pause
