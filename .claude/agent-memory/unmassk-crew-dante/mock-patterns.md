---
name: mock-patterns
description: Working mock patterns for Bun test suites (bun:test, ESM, SQLite, WebSocket)
type: project
---

## Database Mock (Bun ESM-safe, chatroom/backend)

Pattern: mock `connection.js` BEFORE imports. Use a persistent in-memory DB for the entire file.

```ts
import { mock } from 'bun:test';
import { Database } from 'bun:sqlite';

const _testDb = new Database(':memory:');
_testDb.exec(`CREATE TABLE IF NOT EXISTS rooms (...); INSERT OR IGNORE INTO rooms ...`);

// MUST be before any import that transitively loads queries.ts
mock.module('./connection.js', () => ({
  getDb: () => _testDb,
}));

// Then import the real query functions
import { insertMessage, getRecentMessages } from './queries.js';
```

Rotate DB per test: use `let currentDb: Database` and replace it in `beforeEach(() => { currentDb = makeDb(); })`. The closure in the mock factory references `currentDb` lazily.

## App Singleton Mock (message-bus.ts broadcast)

`broadcast()` dynamically imports `../index.js` to get the Elysia app. Mock the deep dependency:

```ts
mock.module('../index.js', () => ({
  app: {
    server: {
      publish(topic: string, data: string) { /* capture or no-op */ },
    },
  },
}));
```

DO NOT mock `./message-bus.js` if another test file imports the real `broadcast` function — that will contaminate it.

## Node:fs Mock (agent-registry.ts file-reading path)

```ts
mock.module('node:fs', () => {
  const realFs = require('node:fs');
  return {
    ...realFs,
    existsSync(p: string) { return p === FAKE_DIR ? true : realFs.existsSync(p); },
    readdirSync(p: string) { return p === FAKE_DIR ? fakeFileList : realFs.readdirSync(p); },
    readFileSync(p: string, enc?: string) {
      if (p.startsWith(FAKE_DIR)) return fakeFiles[basename(p)];
      return realFs.readFileSync(p, enc);
    },
  };
});
```

## Config Mock (override env-evaluated constants)

For constants evaluated at import time (like AGENT_DIR), mock the config module or set env before import:

```ts
// Option A: env var before import (works if module reads process.env lazily)
process.env.DB_PATH = '/tmp/test.db';
const { getDb } = await import('./connection.js');

// Option B: mock.module
mock.module('../config.js', () => ({
  ...require('../config.js'),
  AGENT_DIR: '/fake/agents',
}));
```

## Cross-File Mock Contamination Rule

Bun `mock.module()` persists across test files in the same run. Two rules:
1. If file A mocks `./foo.js`, file B's import of `./foo.js` gets the mock.
2. To avoid contamination: mock the DEEPEST dependency (index.js, not message-bus.js).

## WebSocket Testing (Elysia + bun:test)

```ts
// Spin up real server on port 0
const app = new Elysia().ws('/ws/:roomId', { ... });
await app.listen(0);
const url = `ws://localhost:${app.server!.port}/ws/default`;

// Wait for room_state before doing anything
function openWsReady(url: string, timeoutMs = 2000): Promise<WebSocket> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    const t = setTimeout(() => reject(new Error('timeout')), timeoutMs);
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'room_state') { clearTimeout(t); resolve(ws); }
    };
    ws.onerror = (err) => { clearTimeout(t); reject(err); };
  });
}

// Rate limit key: use ws.id (Bun built-in), NOT upgrade() return data
// upgrade() return value ({ data: { connId } }) does NOT merge into ws.data
```

## Bun spawn subprocess testing

`Bun.spawn` in agent-invoker.ts spawns real `claude -p` processes. These lines (267-479) are NOT unit-testable. Accept the coverage gap — mark in report as "requires real claude binary".
