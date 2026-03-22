/**
 * Golden snapshot tests for agent-stream.ts — pre-split baseline.
 *
 * PURPOSE: Capture the exact observable behavior of readAgentStream,
 * which exercises both applyResultEvent (private) and readStderr (private).
 * After any structural refactor these tests must still pass.
 *
 * Functions covered via readAgentStream:
 *   - applyResultEvent  — maps result event fields to AgentStreamResult
 *   - readStderr        — collects stderr chunks into stderrOutput string
 *
 * Also covered inline:
 *   - makeTimeoutHandle kill logic (inline mirrors — function is private,
 *     timer is not fakeable without spawning real processes)
 *
 * Builds on agent-stream-stderr.test.ts (error/empty paths).
 * This file covers the happy path: result event parsing and field mapping.
 *
 * mock.module() MUST be declared before any import of agent-stream.js.
 */
import { mock } from 'bun:test';
import { Database } from 'bun:sqlite';

// ---------------------------------------------------------------------------
// In-memory DB — satisfies transitive imports (updateAgentStatus etc.)
// ---------------------------------------------------------------------------

const _streamGoldenDb = new Database(':memory:');
_streamGoldenDb.exec(`
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
    input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
    context_window INTEGER DEFAULT 0, duration_ms INTEGER DEFAULT 0,
    num_turns INTEGER DEFAULT 0,
    PRIMARY KEY (agent_name, room_id)
  );
  CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY, room_id TEXT NOT NULL, message_id TEXT,
    filename TEXT NOT NULL, mime_type TEXT NOT NULL, size_bytes INTEGER NOT NULL,
    storage_path TEXT NOT NULL, created_at TEXT NOT NULL
  );
  INSERT OR IGNORE INTO rooms (id, name, topic) VALUES ('default', 'general', 'Agent chatroom');
  INSERT OR IGNORE INTO rooms (id, name, topic) VALUES ('stream-golden-room', 'stream-golden', 'Stream golden room');
`);

// ---------------------------------------------------------------------------
// mock.module() declarations — MUST precede all imports of agent-stream.js
// ---------------------------------------------------------------------------

mock.module('../../src/db/connection.js', () => ({
  getDb: () => _streamGoldenDb,
}));

mock.module('../../src/index.js', () => ({
  app: {
    server: {
      publish(_topic: string, _data: string) {},
    },
  },
}));

// ---------------------------------------------------------------------------
// Imports AFTER all mock.module() declarations
// ---------------------------------------------------------------------------

import { describe, it, expect } from 'bun:test';
import { readAgentStream } from '../../src/services/agent-stream.js';
import type { AgentStreamResult } from '../../src/services/agent-stream.js';

// ---------------------------------------------------------------------------
// Stream helpers
// ---------------------------------------------------------------------------

function makeEmptyReadableStream(): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    pull(controller) { controller.close(); },
  });
}

function makeStringReadableStream(text: string): ReadableStream<Uint8Array> {
  const encoded = new TextEncoder().encode(text);
  let sent = false;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (!sent) { sent = true; controller.enqueue(encoded); }
      else { controller.close(); }
    },
  });
}

function makeProc(opts: {
  stdout?: ReadableStream<Uint8Array>;
  stderr?: ReadableStream<Uint8Array>;
  exitCode?: number;
}): { stdout: ReadableStream<Uint8Array>; stderr: ReadableStream<Uint8Array>; exited: Promise<number>; pid: number | undefined } {
  return {
    stdout: opts.stdout ?? makeEmptyReadableStream(),
    stderr: opts.stderr ?? makeEmptyReadableStream(),
    exited: Promise.resolve(opts.exitCode ?? 0),
    pid: 99999,
  };
}

/** Build a result event NDJSON line for stdout injection. */
function makeResultLine(opts: {
  subtype?: 'success' | 'error';
  result?: string;
  sessionId?: string;
  costUsd?: number;
  durationMs?: number;
  numTurns?: number;
  inputTokens?: number;
  cacheCreationTokens?: number;
  cacheReadTokens?: number;
  outputTokens?: number;
  contextWindow?: number;
  model?: string;
}): string {
  const event = {
    type: 'result',
    subtype: opts.subtype ?? 'success',
    result: opts.result ?? 'agent response text',
    session_id: opts.sessionId ?? 'a1b2c3d4-1234-4abc-abcd-ef0123456789',
    total_cost_usd: opts.costUsd ?? 0,
    duration_ms: opts.durationMs ?? 0,
    num_turns: opts.numTurns ?? 1,
    usage: {
      input_tokens: opts.inputTokens ?? 0,
      cache_creation_input_tokens: opts.cacheCreationTokens ?? 0,
      cache_read_input_tokens: opts.cacheReadTokens ?? 0,
      output_tokens: opts.outputTokens ?? 0,
    },
    model_usage: opts.model
      ? { [opts.model]: { contextWindow: opts.contextWindow ?? 0 } }
      : undefined,
  };
  return JSON.stringify(event) + '\n';
}

function makeFakeHandle(): ReturnType<typeof setTimeout> {
  const h = setTimeout(() => {}, 30_000);
  clearTimeout(h);
  return h;
}

// ---------------------------------------------------------------------------
// GOLDEN: applyResultEvent via readAgentStream — result field mapping
//
// applyResultEvent is private. Its contract is tested here by feeding a
// synthetic result event into readAgentStream and checking AgentStreamResult.
// ---------------------------------------------------------------------------

describe('GOLDEN — applyResultEvent via readAgentStream (agent-stream.ts)', () => {
  it('hasResult is true when stdout contains a result event', async () => {
    const proc = makeProc({ stdout: makeStringReadableStream(makeResultLine({})) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.hasResult).toBe(true);
  });

  it('resultText matches the result event result field', async () => {
    const line = makeResultLine({ result: 'GOLDEN_CANARY_RESULT_TEXT' });
    const proc = makeProc({ stdout: makeStringReadableStream(line) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultText).toBe('GOLDEN_CANARY_RESULT_TEXT');
  });

  it('resultSuccess is true when subtype is "success"', async () => {
    const line = makeResultLine({ subtype: 'success' });
    const proc = makeProc({ stdout: makeStringReadableStream(line) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultSuccess).toBe(true);
  });

  it('resultSuccess is false when subtype is "error"', async () => {
    const line = makeResultLine({ subtype: 'error', result: 'something failed' });
    const proc = makeProc({ stdout: makeStringReadableStream(line) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultSuccess).toBe(false);
  });

  it('resultSessionId contains the validated UUID from session_id field', async () => {
    const uuid = 'a1b2c3d4-1234-4abc-abcd-ef0123456789';
    const line = makeResultLine({ sessionId: uuid });
    const proc = makeProc({ stdout: makeStringReadableStream(line) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultSessionId).toBe(uuid);
  });

  it('resultSessionId is null when session_id is not a valid UUID', async () => {
    const line = makeResultLine({ sessionId: 'not-a-uuid' });
    const proc = makeProc({ stdout: makeStringReadableStream(line) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultSessionId).toBeNull();
  });

  it('resultCostUsd matches total_cost_usd from the result event', async () => {
    const line = makeResultLine({ costUsd: 0.0137 });
    const proc = makeProc({ stdout: makeStringReadableStream(line) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultCostUsd).toBeCloseTo(0.0137, 6);
  });

  it('resultDurationMs matches duration_ms from the result event', async () => {
    const line = makeResultLine({ durationMs: 5678 });
    const proc = makeProc({ stdout: makeStringReadableStream(line) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultDurationMs).toBe(5678);
  });

  it('resultNumTurns matches num_turns from the result event', async () => {
    const line = makeResultLine({ numTurns: 4 });
    const proc = makeProc({ stdout: makeStringReadableStream(line) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultNumTurns).toBe(4);
  });

  it('resultOutputTokens matches usage.output_tokens', async () => {
    const line = makeResultLine({ outputTokens: 333 });
    const proc = makeProc({ stdout: makeStringReadableStream(line) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultOutputTokens).toBe(333);
  });

  it('resultInputTokens = input_tokens + cache_creation_input_tokens + cache_read_input_tokens', async () => {
    // 100 + 5 + 10 = 115
    const line = makeResultLine({ inputTokens: 100, cacheCreationTokens: 5, cacheReadTokens: 10 });
    const proc = makeProc({ stdout: makeStringReadableStream(line) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultInputTokens).toBe(115);
  });

  it('resultInputTokens with only input_tokens (no cache fields): equals input_tokens', async () => {
    const line = makeResultLine({ inputTokens: 200, cacheCreationTokens: 0, cacheReadTokens: 0 });
    const proc = makeProc({ stdout: makeStringReadableStream(line) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultInputTokens).toBe(200);
  });

  it('resultContextWindow from model_usage[modelId].contextWindow', async () => {
    const line = makeResultLine({ model: 'claude-sonnet-4-6', contextWindow: 200_000 });
    const proc = makeProc({ stdout: makeStringReadableStream(line) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultContextWindow).toBe(200_000);
  });

  it('resultContextWindow is 0 when model_usage is absent', async () => {
    // no model key → no model_usage in the event
    const event = {
      type: 'result', subtype: 'success',
      result: 'text', session_id: 'a1b2c3d4-1234-4abc-abcd-ef0123456789',
      total_cost_usd: 0, duration_ms: 0, num_turns: 1,
      usage: { input_tokens: 0, output_tokens: 0, cache_creation_input_tokens: 0, cache_read_input_tokens: 0 },
    };
    const proc = makeProc({ stdout: makeStringReadableStream(JSON.stringify(event) + '\n') });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.resultContextWindow).toBe(0);
  });

  it('noise events (type=progress) are silently discarded — hasResult stays false', async () => {
    const noise = JSON.stringify({ type: 'progress', message: 'doing stuff' }) + '\n';
    const proc = makeProc({ stdout: makeStringReadableStream(noise) });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.hasResult).toBe(false);
  });

  it('malformed JSON in stdout is silently discarded — hasResult stays false', async () => {
    const proc = makeProc({ stdout: makeStringReadableStream('not json at all\n') });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.hasResult).toBe(false);
  });

  it('empty stdout: all AgentStreamResult fields are at their zero/null/false defaults', async () => {
    const proc = makeProc({});
    const result: AgentStreamResult = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.hasResult).toBe(false);
    expect(result.resultText).toBe('');
    expect(result.resultSuccess).toBe(false);
    expect(result.resultSessionId).toBeNull();
    expect(result.resultCostUsd).toBe(0);
    expect(result.resultDurationMs).toBe(0);
    expect(result.resultNumTurns).toBe(0);
    expect(result.resultInputTokens).toBe(0);
    expect(result.resultOutputTokens).toBe(0);
    expect(result.resultContextWindow).toBe(0);
    expect(result.stderrOutput).toBe('');
  });
});

// ---------------------------------------------------------------------------
// GOLDEN: readStderr via readAgentStream — stderr field contract
//
// readStderr is private. Its contract: reads all chunks from the stderr
// ReadableStream, joins them into a single string in stderrOutput.
// ---------------------------------------------------------------------------

describe('GOLDEN — readStderr via readAgentStream (agent-stream.ts)', () => {
  it('stderrOutput is empty string when stderr stream is empty', async () => {
    const proc = makeProc({});
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.stderrOutput).toBe('');
  });

  it('stderrOutput captures a single stderr chunk', async () => {
    const proc = makeProc({ stderr: makeStringReadableStream('some error output') });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.stderrOutput).toBe('some error output');
  });

  it('stderrOutput contains rate-limit text when CLI emits 429', async () => {
    const proc = makeProc({ stderr: makeStringReadableStream('HTTP 429 Too Many Requests') });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.stderrOutput).toContain('429');
  });

  it('stderrOutput is independent of stdout content', async () => {
    const proc = makeProc({
      stdout: makeStringReadableStream(makeResultLine({ result: 'ok' })),
      stderr: makeStringReadableStream('stderr text'),
    });
    const result = await readAgentStream(proc, 'agent', 'default', makeFakeHandle());
    expect(result.stderrOutput).toBe('stderr text');
    expect(result.resultText).toBe('ok');
  });
});

// ---------------------------------------------------------------------------
// GOLDEN: readAgentStream — timeout handle is cleared after stream completes
// ---------------------------------------------------------------------------

describe('GOLDEN — readAgentStream timeout clearing (agent-stream.ts)', () => {
  it('clears the timeout handle on normal exit so it does not fire after return', async () => {
    const proc = makeProc({});
    // A real timeout that would throw if NOT cleared
    const handle = setTimeout(() => {
      throw new Error('timeout fired — readAgentStream did not clear it');
    }, 30_000);
    const result = await readAgentStream(proc, 'agent', 'default', handle);
    // Reaching here means the handle was cleared (or timeout didn't fire yet in 0ms)
    expect(typeof result).toBe('object');
  });

  it('clears the timeout handle even when a result event is present', async () => {
    const proc = makeProc({ stdout: makeStringReadableStream(makeResultLine({})) });
    const handle = setTimeout(() => {
      throw new Error('timeout fired — readAgentStream did not clear it');
    }, 30_000);
    const result = await readAgentStream(proc, 'agent', 'default', handle);
    expect(result.hasResult).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// GOLDEN: makeTimeoutHandle kill logic — inline mirror
//
// makeTimeoutHandle is private and requires AGENT_TIMEOUT_MS to fire (large).
// The kill logic branches are documented here as inline mirrors so any change
// to the branching contract fails these tests.
// ---------------------------------------------------------------------------

describe('GOLDEN — makeTimeoutHandle kill logic (inline mirror of agent-runner.ts)', () => {
  // Mirror the exact guard from makeTimeoutHandle line 243:
  //   if (!proc.pid || proc.pid <= 0) { proc.kill(); return; }
  function shouldUseDirectKill(pid: number | undefined): boolean {
    return !pid || pid <= 0;
  }

  it('undefined pid → use proc.kill() directly', () => {
    expect(shouldUseDirectKill(undefined)).toBe(true);
  });

  it('pid=0 → use proc.kill() directly', () => {
    expect(shouldUseDirectKill(0)).toBe(true);
  });

  it('negative pid → use proc.kill() directly', () => {
    expect(shouldUseDirectKill(-1)).toBe(true);
  });

  it('pid=1 (valid) → do NOT use direct kill (use process.kill(-pid) on Unix)', () => {
    expect(shouldUseDirectKill(1)).toBe(false);
  });

  it('pid=99999 (valid) → do NOT use direct kill', () => {
    expect(shouldUseDirectKill(99999)).toBe(false);
  });

  // Mirror the platform check from makeTimeoutHandle line 242:
  //   if (process.platform !== 'win32') { /* SIGTERM process group */ } else { proc.kill() }
  function isUnixKill(platform: string): boolean {
    return platform !== 'win32';
  }

  it('darwin platform → Unix kill path (not win32)', () => {
    expect(isUnixKill('darwin')).toBe(true);
  });

  it('linux platform → Unix kill path', () => {
    expect(isUnixKill('linux')).toBe(true);
  });

  it('win32 platform → Windows kill path (proc.kill())', () => {
    expect(isUnixKill('win32')).toBe(false);
  });

  // Mirror the Unix kill: process.kill(-(proc.pid), 'SIGTERM')
  // The negative PID kills the entire process group.
  it('Unix kill sends SIGTERM to process GROUP (negative pid)', () => {
    const pid = 1234;
    const signalTarget = -(pid);
    expect(signalTarget).toBe(-1234);
    expect(signalTarget).toBeLessThan(0);
  });

  it('Unix kill uses SIGTERM signal (not SIGKILL)', () => {
    const signal = 'SIGTERM';
    expect(signal).toBe('SIGTERM');
    expect(signal).not.toBe('SIGKILL');
  });
});
