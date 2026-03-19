# Testing Guide

## Running Tests

```bash
cd chatroom/apps/backend
bun test
```

535+ tests. All must pass before merging. There is no watch mode flag — rerun the command manually.

To run a specific test file:
```bash
bun test src/services/auth-tokens.test.ts
```

To run tests matching a name pattern:
```bash
bun test --test-name-pattern "validateName"
```

## Framework

`bun:test` — Jest-compatible API. No external test runner.

## Database Strategy

Tests use in-memory SQLite (`:memory:`), never the file on disk.

**Standard pattern:**
```ts
import { Database } from 'bun:sqlite';

const db = new Database(':memory:');
db.exec(`CREATE TABLE IF NOT EXISTS rooms (...); INSERT OR IGNORE INTO rooms ...`);
```

For modules that call `getDb()` internally, mock the connection module **before importing** the module under test:

```ts
import { mock } from 'bun:test';
import { Database } from 'bun:sqlite';

const testDb = new Database(':memory:');
testDb.exec(/* schema */);

// Must be declared BEFORE importing the module that calls getDb()
mock.module('../db/connection.js', () => ({
  getDb: () => testDb,
}));

// Now import the module under test
import { buildPrompt } from './agent-invoker.js';
```

Do NOT close the in-memory DB between tests within a file — keep it alive for the entire file. The `bun:test` isolates test files but not individual tests within a file.

## Test File Structure

| File                                         | What it tests                               |
|----------------------------------------------|---------------------------------------------|
| `smoke.test.ts`                              | Server starts, health endpoint responds     |
| `config.test.ts`                             | Env var parsing and validation              |
| `config-validation.test.ts`                  | Invalid env var rejection                   |
| `logger.test.ts`                             | Logger creation, child bindings             |
| `utils.test.ts`                              | `generateId`, `nowIso`, row mappers, `safeMessage` |
| `db/connection.test.ts`                      | DB singleton, pragma application            |
| `db/queries.test.ts`                         | All query functions (in-memory DB)          |
| `db/queries-real.test.ts`                    | Queries against a temp file DB              |
| `routes/api.test.ts`                         | HTTP routes: rooms, agents, auth, invite    |
| `routes/api-invite.test.ts`                  | Invite endpoint auth and rate limit         |
| `routes/ws.test.ts`                          | WebSocket connect, send_message, load_history, rate limit, origin check |
| `services/agent-invoker.test.ts`             | `validateSessionId`, `buildPrompt`, `sanitizePromptContent`, `buildSystemPrompt` |
| `services/agent-invoker-schedule.test.ts`    | Queue scheduling, pause/resume, `@everyone` |
| `services/agent-registry.test.ts`            | Registry build, `getAgentConfig`, banned tool filtering |
| `services/agent-registry-fs.test.ts`         | Frontmatter parsing from real `.md` files   |
| `services/agent-registry-frontmatter.test.ts`| Frontmatter edge cases                      |
| `services/auth-tokens.test.ts`               | `validateName`, `issueToken`, `validateToken`, `peekToken` |
| `services/auth-tokens-brute-force.test.ts`   | Brute-force detection threshold             |
| `services/mention-parser.test.ts`            | `extractMentions` edge cases                |
| `services/message-bus.test.ts`               | `stripSessionId` for broadcasts             |
| `services/message-bus-broadcast.test.ts`     | `broadcastSync` integration                 |
| `services/rate-limiter.test.ts`              | Token bucket behavior                       |
| `services/stream-parser.test.ts`             | NDJSON parsing, event whitelisting          |

## Patterns

### Arrange / Act / Assert

```ts
it('rejects reserved agent name', () => {
  // Arrange: name that matches a known agent
  const name = 'bilbo';

  // Act
  const result = validateName(name);

  // Assert
  expect(result).toBeNull();
});
```

### Cleanup with try/finally

When a test modifies shared state or creates resources:
```ts
it('thing', async () => {
  const resource = createResource();
  try {
    // assertions
    expect(resource.foo).toBe('bar');
  } finally {
    resource.cleanup();
  }
});
```

### Testing WS Handlers

`ws.test.ts` spins up a minimal Elysia server with an in-memory DB that mirrors production behavior. The Bun WebSocket client is used for connections. Tests connect, send messages, and assert on received events.

The production origin check is skipped in the test server because Bun's built-in WS client does not send an `Origin` header. Origin logic is unit-tested separately as a pure function.

### Testing Async Fire-and-Forget (agent-invoker)

Functions like `invokeAgents` are fire-and-forget. Tests that need to observe outcomes after invocation use `await new Promise(resolve => setTimeout(resolve, <ms>))` to yield the event loop. Schedule tests (`agent-invoker-schedule.test.ts`) mock the underlying DB and inspect queue/inFlight state directly.

## What is NOT Tested

- End-to-end subprocess spawn: calling the real `claude` binary is not done in unit tests (no API key required to run the test suite)
- Frontend integration: tests cover backend only
- Production static file serving
