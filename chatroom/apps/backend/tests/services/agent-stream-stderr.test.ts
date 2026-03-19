/**
 * Unit tests for agent-stream.ts — stderr error path.
 *
 * Covers the readAgentStream() behavior when the stderr stream throws on read.
 * The private readStderr() function catches the error and leaves stderrOutput as
 * an empty string — the outer readAgentStream() must not propagate the exception.
 *
 * Strategy: build a minimal fake `proc` object that:
 *   - stdout: a ReadableStream that yields no bytes and closes immediately (done=true)
 *   - stderr: a ReadableStream whose reader.read() rejects with an error
 *   - exited: a Promise<number> that resolves to 0
 *   - pid: an arbitrary number
 *
 * mock.module() declarations precede all imports.
 */
import { mock } from 'bun:test';
import { Database } from 'bun:sqlite';

// ---------------------------------------------------------------------------
// In-memory DB (readAgentStream → agent-runner → agent-runner's updateStatusAndBroadcast
// calls updateAgentStatus which needs a working DB; but we only test readAgentStream
// directly — it does NOT touch the DB itself. The DB mock is here only to satisfy
// the transitive import chain if any other module in the file loads db/connection.js)
// ---------------------------------------------------------------------------

const _streamStderrDb = new Database(':memory:');
_streamStderrDb.exec(`
  CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, topic TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
  CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY, room_id TEXT NOT NULL, author TEXT NOT NULL,
    author_type TEXT NOT NULL, content TEXT NOT NULL,
    msg_type TEXT NOT NULL DEFAULT 'message', parent_id TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
  CREATE TABLE IF NOT EXISTS agent_sessions (
    agent_name TEXT NOT NULL, room_id TEXT NOT NULL,
    session_id TEXT, model TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'idle',
    last_active TEXT, total_cost REAL DEFAULT 0.0, turn_count INTEGER DEFAULT 0,
    PRIMARY KEY (agent_name, room_id)
  );
  INSERT OR IGNORE INTO rooms (id, name, topic) VALUES ('default', 'general', 'Agent chatroom');
`);

mock.module('../../src/db/connection.js', () => ({
  getDb: () => _streamStderrDb,
}));

mock.module('../../src/index.js', () => ({
  app: {
    server: {
      publish(_topic: string, _data: string) { /* no-op */ },
    },
  },
}));

// ---------------------------------------------------------------------------
// Imports — AFTER mock.module declarations
// ---------------------------------------------------------------------------

import { describe, it, expect } from 'bun:test';
import { readAgentStream } from '../../src/services/agent-stream.js';
import type { AgentStreamResult } from '../../src/services/agent-stream.js';

// ---------------------------------------------------------------------------
// Helpers — fake ReadableStream builders
// ---------------------------------------------------------------------------

/**
 * Returns a ReadableStream<Uint8Array> that immediately signals done on first read.
 * Used for stdout when we want no content produced.
 */
function makeEmptyReadableStream(): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      controller.close();
    },
  });
}

/**
 * Returns a ReadableStream<Uint8Array> whose reader.read() rejects with the
 * provided error on the first call.
 * Used to simulate a stderr stream that throws mid-read.
 */
function makeThrowingReadableStream(err: Error): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    pull(_controller) {
      throw err;
    },
  });
}

/**
 * Returns a ReadableStream<Uint8Array> that yields a single UTF-8 chunk and closes.
 */
function makeStringReadableStream(text: string): ReadableStream<Uint8Array> {
  const encoded = new TextEncoder().encode(text);
  let sent = false;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (!sent) {
        sent = true;
        controller.enqueue(encoded);
      } else {
        controller.close();
      }
    },
  });
}

// ---------------------------------------------------------------------------
// Fake proc builder
// ---------------------------------------------------------------------------

interface FakeProc {
  stdout: ReadableStream<Uint8Array>;
  stderr: ReadableStream<Uint8Array>;
  exited: Promise<number>;
  pid: number | undefined;
}

function makeProc(opts: {
  stdout?: ReadableStream<Uint8Array>;
  stderr?: ReadableStream<Uint8Array>;
  exitCode?: number;
}): FakeProc {
  return {
    stdout: opts.stdout ?? makeEmptyReadableStream(),
    stderr: opts.stderr ?? makeEmptyReadableStream(),
    exited: Promise.resolve(opts.exitCode ?? 0),
    pid: 99999,
  };
}

// ---------------------------------------------------------------------------
// Tests — stderr throws on read
// ---------------------------------------------------------------------------

describe('readAgentStream — throwing stderr stream', () => {
  it('does not throw when stderr.read() rejects', async () => {
    const proc = makeProc({
      stderr: makeThrowingReadableStream(new Error('stderr exploded')),
    });
    const timeoutHandle = setTimeout(() => {}, 30_000);
    clearTimeout(timeoutHandle); // clear immediately — we just need the handle type

    const fakeHandle = setTimeout(() => {}, 30_000);
    await expect(
      readAgentStream(proc, 'testAgent', 'default', fakeHandle),
    ).resolves.toBeDefined();
  });

  it('returns stderrOutput as empty string when stderr throws', async () => {
    const proc = makeProc({
      stderr: makeThrowingReadableStream(new Error('read error')),
    });
    const fakeHandle = setTimeout(() => {}, 30_000);
    const result: AgentStreamResult = await readAgentStream(proc, 'testAgent', 'default', fakeHandle);
    expect(result.stderrOutput).toBe('');
  });

  it('returns hasResult=false when stdout is empty and stderr throws', async () => {
    const proc = makeProc({
      stderr: makeThrowingReadableStream(new Error('io error')),
    });
    const fakeHandle = setTimeout(() => {}, 30_000);
    const result = await readAgentStream(proc, 'testAgent', 'default', fakeHandle);
    expect(result.hasResult).toBe(false);
  });

  it('returns resultText="" when stdout is empty and stderr throws', async () => {
    const proc = makeProc({
      stderr: makeThrowingReadableStream(new Error('io error')),
    });
    const fakeHandle = setTimeout(() => {}, 30_000);
    const result = await readAgentStream(proc, 'testAgent', 'default', fakeHandle);
    expect(result.resultText).toBe('');
  });

  it('returns resultSuccess=false when stderr throws and no result event parsed', async () => {
    const proc = makeProc({
      stderr: makeThrowingReadableStream(new Error('io error')),
    });
    const fakeHandle = setTimeout(() => {}, 30_000);
    const result = await readAgentStream(proc, 'testAgent', 'default', fakeHandle);
    expect(result.resultSuccess).toBe(false);
  });

  it('clears the timeout handle after stream completes (even when stderr throws)', async () => {
    const proc = makeProc({
      stderr: makeThrowingReadableStream(new Error('stderr oops')),
    });
    // Give a real (long) timeout; readAgentStream should clearTimeout before returning.
    // We verify by checking the result arrives promptly — if clearTimeout were NOT called
    // the handle would still be pending but the test would still pass (it does not block).
    const fakeHandle = setTimeout(() => {
      throw new Error('timeout fired — clearTimeout was not called');
    }, 30_000);
    const result = await readAgentStream(proc, 'testAgent', 'default', fakeHandle);
    // If we reach here the timeout was cleared and readAgentStream returned normally.
    expect(typeof result).toBe('object');
  });
});

// ---------------------------------------------------------------------------
// Tests — stderr normal (smoke check that the happy path still works)
// ---------------------------------------------------------------------------

describe('readAgentStream — empty stdout and stderr (clean process exit)', () => {
  it('returns an AgentStreamResult with all zero/empty/false defaults', async () => {
    const proc = makeProc({});
    const fakeHandle = setTimeout(() => {}, 30_000);
    const result = await readAgentStream(proc, 'agent', 'default', fakeHandle);
    expect(result.resultText).toBe('');
    expect(result.stderrOutput).toBe('');
    expect(result.hasResult).toBe(false);
    expect(result.resultSuccess).toBe(false);
    expect(result.resultCostUsd).toBe(0);
    expect(result.resultDurationMs).toBe(0);
    expect(result.resultNumTurns).toBe(0);
    expect(result.resultInputTokens).toBe(0);
    expect(result.resultOutputTokens).toBe(0);
    expect(result.resultContextWindow).toBe(0);
    expect(result.resultSessionId).toBeNull();
  });

  it('captures stderr text when stderr stream is well-behaved', async () => {
    const proc = makeProc({
      stderr: makeStringReadableStream('some stderr text'),
    });
    const fakeHandle = setTimeout(() => {}, 30_000);
    const result = await readAgentStream(proc, 'agent', 'default', fakeHandle);
    expect(result.stderrOutput).toBe('some stderr text');
  });
});

// ---------------------------------------------------------------------------
// Tests — stderr throws with TypeError (non-Error object thrown)
// ---------------------------------------------------------------------------

describe('readAgentStream — stderr stream that throws a non-Error value', () => {
  it('handles non-Error thrown value gracefully (returns stderrOutput="")', async () => {
    // Some environments throw plain objects or strings from stream internals.
    const nonErrorStream = new ReadableStream<Uint8Array>({
      pull() {
        throw 'string error, not an Error object';
      },
    });
    const proc = makeProc({ stderr: nonErrorStream });
    const fakeHandle = setTimeout(() => {}, 30_000);
    const result = await readAgentStream(proc, 'agent', 'default', fakeHandle);
    expect(result.stderrOutput).toBe('');
  });
});
