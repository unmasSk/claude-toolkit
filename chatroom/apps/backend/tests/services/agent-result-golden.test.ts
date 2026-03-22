/**
 * Golden snapshot tests for agent-result.ts — pre-split baseline.
 *
 * PURPOSE: Capture the exact observable behavior of every exported function
 * BEFORE any refactor. After restructuring, all these tests must still pass.
 * Any deviation means the refactor introduced a behavioral regression.
 *
 * Exports covered:
 *   - buildAgentMessage — constructs Message + meta from AgentStreamResult
 *   - maybeTruncate     — byte cap enforcement with truncation suffix
 *
 * mock.module() MUST be declared before any import of agent-result.ts or
 * any module that transitively loads it.
 */
import { mock } from 'bun:test';
import { Database } from 'bun:sqlite';

// ---------------------------------------------------------------------------
// In-memory DB — satisfies transitive imports of db/connection.js
// ---------------------------------------------------------------------------

const _resultDb = new Database(':memory:');
_resultDb.exec(`
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
  INSERT OR IGNORE INTO rooms (id, name, topic) VALUES ('result-golden-room', 'result-golden', 'Result golden room');
`);

// ---------------------------------------------------------------------------
// mock.module() declarations — MUST precede all imports of agent-result.js
// ---------------------------------------------------------------------------

mock.module('../../src/db/connection.js', () => ({
  getDb: () => _resultDb,
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
import { buildAgentMessage, maybeTruncate } from '../../src/services/agent-result.js';
import type { AgentStreamResult } from '../../src/services/agent-stream.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSr(overrides: Partial<AgentStreamResult> = {}): AgentStreamResult {
  return {
    resultText: 'hello world',
    resultSessionId: 'a1b2c3d4-1234-4abc-abcd-ef0123456789',
    resultCostUsd: 0.0042,
    resultSuccess: true,
    resultDurationMs: 1234,
    resultNumTurns: 3,
    resultInputTokens: 100,
    resultOutputTokens: 50,
    resultContextWindow: 200_000,
    hasResult: true,
    stderrOutput: '',
    ...overrides,
  };
}

const ROOM = 'result-golden-room';
const AGENT = 'result-golden-agent';
const MODEL = 'claude-sonnet-4-6';
const TEXT = 'Hello, this is the agent response.';

// ---------------------------------------------------------------------------
// GOLDEN: buildAgentMessage — return shape
// ---------------------------------------------------------------------------

describe('GOLDEN — buildAgentMessage return shape (agent-result.ts)', () => {
  it('returns an object with both "message" and "meta" keys', () => {
    const result = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, MODEL);
    expect(typeof result).toBe('object');
    expect('message' in result).toBe(true);
    expect('meta' in result).toBe(true);
  });

  it('does not throw for a fully populated AgentStreamResult', () => {
    expect(() => buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, MODEL)).not.toThrow();
  });

  it('does not throw when resultSessionId is null', () => {
    expect(() => buildAgentMessage(makeSr({ resultSessionId: null }), TEXT, ROOM, AGENT, MODEL)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// GOLDEN: buildAgentMessage — message fields
// ---------------------------------------------------------------------------

describe('GOLDEN — buildAgentMessage message fields (agent-result.ts)', () => {
  it('message.id is a non-empty string', () => {
    const { message } = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, MODEL);
    expect(typeof message.id).toBe('string');
    expect(message.id.length).toBeGreaterThan(0);
  });

  it('message.id is unique across two calls (generateId is random)', () => {
    const sr = makeSr();
    const { message: m1 } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    const { message: m2 } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect(m1.id).not.toBe(m2.id);
  });

  it('message.roomId matches the supplied roomId', () => {
    const { message } = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, MODEL);
    expect(message.roomId).toBe(ROOM);
  });

  it('message.author matches the supplied agentName', () => {
    const { message } = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, MODEL);
    expect(message.author).toBe(AGENT);
  });

  it('message.authorType is "agent" (always, regardless of input)', () => {
    const { message } = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, MODEL);
    expect(message.authorType).toBe('agent');
  });

  it('message.content matches the supplied resultText', () => {
    const { message } = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, MODEL);
    expect(message.content).toBe(TEXT);
  });

  it('message.content with empty resultText: content is empty string', () => {
    const { message } = buildAgentMessage(makeSr(), '', ROOM, AGENT, MODEL);
    expect(message.content).toBe('');
  });

  it('message.msgType is "message"', () => {
    const { message } = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, MODEL);
    expect(message.msgType).toBe('message');
  });

  it('message.parentId is null', () => {
    const { message } = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, MODEL);
    expect(message.parentId).toBeNull();
  });

  it('message.createdAt is a non-empty string', () => {
    const { message } = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, MODEL);
    expect(typeof message.createdAt).toBe('string');
    expect(message.createdAt.length).toBeGreaterThan(0);
  });

  it('message.createdAt is a valid ISO date', () => {
    const { message } = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, MODEL);
    expect(!isNaN(new Date(message.createdAt).getTime())).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// GOLDEN: buildAgentMessage — message.metadata fields
// ---------------------------------------------------------------------------

describe('GOLDEN — buildAgentMessage message.metadata fields (agent-result.ts)', () => {
  it('metadata.costUsd matches sr.resultCostUsd', () => {
    const sr = makeSr({ resultCostUsd: 0.1337 });
    const { message } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect((message.metadata as Record<string, unknown>).costUsd).toBe(0.1337);
  });

  it('metadata.model matches the supplied model string', () => {
    const { message } = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, 'claude-opus-4-6');
    expect((message.metadata as Record<string, unknown>).model).toBe('claude-opus-4-6');
  });

  it('metadata.durationMs matches sr.resultDurationMs', () => {
    const sr = makeSr({ resultDurationMs: 9876 });
    const { message } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect((message.metadata as Record<string, unknown>).durationMs).toBe(9876);
  });

  it('metadata.numTurns matches sr.resultNumTurns', () => {
    const sr = makeSr({ resultNumTurns: 7 });
    const { message } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect((message.metadata as Record<string, unknown>).numTurns).toBe(7);
  });

  it('metadata.inputTokens matches sr.resultInputTokens', () => {
    const sr = makeSr({ resultInputTokens: 4321 });
    const { message } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect((message.metadata as Record<string, unknown>).inputTokens).toBe(4321);
  });

  it('metadata.outputTokens matches sr.resultOutputTokens', () => {
    const sr = makeSr({ resultOutputTokens: 999 });
    const { message } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect((message.metadata as Record<string, unknown>).outputTokens).toBe(999);
  });

  it('metadata.contextWindow matches sr.resultContextWindow', () => {
    const sr = makeSr({ resultContextWindow: 1_000_000 });
    const { message } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect((message.metadata as Record<string, unknown>).contextWindow).toBe(1_000_000);
  });

  it('metadata.sessionId matches sr.resultSessionId when non-null', () => {
    const sessionId = 'a1b2c3d4-1234-4abc-abcd-ef0123456789';
    const sr = makeSr({ resultSessionId: sessionId });
    const { message } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect((message.metadata as Record<string, unknown>).sessionId).toBe(sessionId);
  });

  it('metadata.sessionId is undefined when sr.resultSessionId is null (null ?? undefined coercion)', () => {
    const sr = makeSr({ resultSessionId: null });
    const { message } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    // message.metadata uses `sr.resultSessionId ?? undefined` — null becomes undefined
    expect((message.metadata as Record<string, unknown>).sessionId).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// GOLDEN: buildAgentMessage — meta record fields
// ---------------------------------------------------------------------------

describe('GOLDEN — buildAgentMessage meta record fields (agent-result.ts)', () => {
  it('meta.sessionId retains the raw sr.resultSessionId value (including null — no coercion)', () => {
    const sr = makeSr({ resultSessionId: null });
    const { meta } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect(meta.sessionId).toBeNull();
  });

  it('meta.sessionId is the UUID string when non-null', () => {
    const sessionId = 'a1b2c3d4-1234-4abc-abcd-ef0123456789';
    const sr = makeSr({ resultSessionId: sessionId });
    const { meta } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect(meta.sessionId).toBe(sessionId);
  });

  it('meta.costUsd matches sr.resultCostUsd', () => {
    const sr = makeSr({ resultCostUsd: 0.0001 });
    const { meta } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect(meta.costUsd).toBe(0.0001);
  });

  it('meta.costUsd is 0 when sr.resultCostUsd is 0', () => {
    const sr = makeSr({ resultCostUsd: 0 });
    const { meta } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect(meta.costUsd).toBe(0);
  });

  it('meta.model is the model string supplied to the function (not from sr)', () => {
    const { meta } = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, 'claude-haiku-4-5');
    expect(meta.model).toBe('claude-haiku-4-5');
  });

  it('meta.durationMs matches sr.resultDurationMs', () => {
    const sr = makeSr({ resultDurationMs: 0 });
    const { meta } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect(meta.durationMs).toBe(0);
  });

  it('meta.numTurns matches sr.resultNumTurns', () => {
    const sr = makeSr({ resultNumTurns: 1 });
    const { meta } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect(meta.numTurns).toBe(1);
  });

  it('meta.inputTokens matches sr.resultInputTokens', () => {
    const sr = makeSr({ resultInputTokens: 50_000 });
    const { meta } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect(meta.inputTokens).toBe(50_000);
  });

  it('meta.outputTokens matches sr.resultOutputTokens', () => {
    const sr = makeSr({ resultOutputTokens: 8192 });
    const { meta } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect(meta.outputTokens).toBe(8192);
  });

  it('meta.contextWindow matches sr.resultContextWindow', () => {
    const sr = makeSr({ resultContextWindow: 200_000 });
    const { meta } = buildAgentMessage(sr, TEXT, ROOM, AGENT, MODEL);
    expect(meta.contextWindow).toBe(200_000);
  });

  it('meta has exactly 8 keys: sessionId, costUsd, model, durationMs, numTurns, inputTokens, outputTokens, contextWindow', () => {
    const { meta } = buildAgentMessage(makeSr(), TEXT, ROOM, AGENT, MODEL);
    const keys = Object.keys(meta).sort();
    expect(keys).toEqual(['contextWindow', 'costUsd', 'durationMs', 'inputTokens', 'model', 'numTurns', 'outputTokens', 'sessionId']);
  });
});

// ---------------------------------------------------------------------------
// GOLDEN: maybeTruncate — byte cap enforcement
// ---------------------------------------------------------------------------

describe('GOLDEN — maybeTruncate byte cap (agent-result.ts)', () => {
  const MAX = 256_000;

  it('text within cap is returned unchanged', () => {
    const text = 'hello world';
    expect(maybeTruncate(text, AGENT, ROOM)).toBe(text);
  });

  it('empty string is returned unchanged', () => {
    expect(maybeTruncate('', AGENT, ROOM)).toBe('');
  });

  it('text at exact cap (256000 bytes) is NOT truncated', () => {
    const text = 'x'.repeat(MAX);
    expect(maybeTruncate(text, AGENT, ROOM)).toBe(text);
  });

  it('text at 255999 bytes is NOT truncated', () => {
    const text = 'x'.repeat(255_999);
    expect(maybeTruncate(text, AGENT, ROOM)).toBe(text);
  });

  it('text at 256001 bytes IS truncated', () => {
    const text = 'x'.repeat(256_001);
    const result = maybeTruncate(text, AGENT, ROOM);
    expect(result).not.toBe(text);
  });

  it('truncated result ends with the exact suffix "\\n[...truncated]"', () => {
    const text = 'x'.repeat(MAX + 1);
    const result = maybeTruncate(text, AGENT, ROOM);
    expect(result.endsWith('\n[...truncated]')).toBe(true);
  });

  it('truncated result starts with the first bytes of the original text', () => {
    const text = 'CANARY_START' + 'x'.repeat(MAX);
    const result = maybeTruncate(text, AGENT, ROOM);
    expect(result.startsWith('CANARY_START')).toBe(true);
  });

  it('truncated result total byte length is within a small margin above the cap', () => {
    const text = 'x'.repeat(MAX + 1_000);
    const result = maybeTruncate(text, AGENT, ROOM);
    // cap bytes + "\\n[...truncated]" (15 bytes) = at most MAX + 15
    expect(Buffer.byteLength(result, 'utf8')).toBeLessThanOrEqual(MAX + 20);
  });

  it('multi-byte UTF-8 text within cap is returned unchanged', () => {
    // '€' is 3 bytes — 10 euros = 30 bytes, well within cap
    const text = '€'.repeat(10);
    expect(maybeTruncate(text, AGENT, ROOM)).toBe(text);
  });

  it('does not throw for very large text', () => {
    const text = 'x'.repeat(MAX * 2);
    expect(() => maybeTruncate(text, AGENT, ROOM)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// GOLDEN: maybeTruncate truncation suffix — exact string (inline mirror)
//
// The suffix '\n[...truncated]' must remain exactly this string after any
// refactor. Changing it would break clients that detect truncated responses.
// ---------------------------------------------------------------------------

describe('GOLDEN — maybeTruncate truncation suffix (inline mirror)', () => {
  const TRUNCATION_SUFFIX = '\n[...truncated]';

  it('suffix starts with a newline character', () => {
    expect(TRUNCATION_SUFFIX.startsWith('\n')).toBe(true);
  });

  it('suffix contains "[...truncated]" marker', () => {
    expect(TRUNCATION_SUFFIX).toContain('[...truncated]');
  });

  it('suffix exact value: "\\n[...truncated]"', () => {
    expect(TRUNCATION_SUFFIX).toBe('\n[...truncated]');
  });

  it('suffix is 15 characters long', () => {
    expect(TRUNCATION_SUFFIX.length).toBe(15);
  });
});
