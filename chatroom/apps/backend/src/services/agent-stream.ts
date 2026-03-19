/**
 * agent-stream.ts
 *
 * Stream-reading and result-handling helpers extracted from agent-runner.ts.
 *
 * Exports:
 *   - AgentStreamResult  — shaped data returned from the subprocess stdout
 *   - readAgentStream    — reads stdout line-by-line, fires tool callbacks,
 *                          returns AgentStreamResult
 *   - handleAgentResult  — post-stream logic: stale-session/rate-limit detection,
 *                          SKIP suppression, DB persist, broadcast, chain mentions
 */

import { createLogger } from '../logger.js';
import { parseStreamLine } from './stream-parser.js';
import type { ResultEvent } from './stream-parser.js';
import { broadcast } from './message-bus.js';
import {
  upsertAgentSession,
  incrementAgentCost,
  incrementAgentTurnCount,
  insertMessage,
  clearAgentSession,
} from '../db/queries.js';
import { generateId, nowIso } from '../utils.js';
import { AGENT_TIMEOUT_MS } from '../config.js';
import type { Message } from '@agent-chatroom/shared';
import { AgentState } from '@agent-chatroom/shared';
import {
  formatToolDescription,
  validateSessionId,
  sanitizePromptContent,
  CONTEXT_OVERFLOW_SIGNAL,
} from './agent-prompt.js';
import { extractMentions } from './mention-parser.js';
import { updateStatusAndBroadcast, postSystemMessage } from './agent-runner.js';
import type { InvocationContext } from './agent-scheduler.js';

const logger = createLogger('agent-stream');

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentStreamResult {
  resultText: string;
  resultSessionId: string | null;
  resultCostUsd: number;
  resultSuccess: boolean;
  resultDurationMs: number;
  resultNumTurns: number;
  resultInputTokens: number;
  resultOutputTokens: number;
  resultContextWindow: number;
  hasResult: boolean;
  stderrOutput: string;
}

// ---------------------------------------------------------------------------
// readAgentStream
// ---------------------------------------------------------------------------

/**
 * Reads the subprocess stdout and stderr concurrently, parses stream-json
 * events line by line, and broadcasts tool_use events (throttled to 500 ms).
 * Returns an AgentStreamResult with all collected data.
 */
export async function readAgentStream(
  proc: { stdout: ReadableStream<Uint8Array>; stderr: unknown; exited: Promise<number>; pid: number | undefined },
  agentName: string,
  roomId: string,
  timeoutHandle: ReturnType<typeof setTimeout>,
): Promise<AgentStreamResult> {
  const result: AgentStreamResult = {
    resultText: '', resultSessionId: null, resultCostUsd: 0, resultSuccess: false,
    resultDurationMs: 0, resultNumTurns: 0, resultInputTokens: 0, resultOutputTokens: 0,
    resultContextWindow: 0, hasResult: false, stderrOutput: '',
  };

  // Read stderr in background — never block stdout on it
  const stderrDone = readStderr(proc.stderr, result);
  let lastToolBroadcastTime = 0;
  const setTime = (t: number) => { lastToolBroadcastTime = t; };

  try {
    const reader = (proc.stdout as ReadableStream<Uint8Array>).getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) {
        if (line.trim()) await processStreamLine(line, agentName, roomId, result, lastToolBroadcastTime, setTime);
      }
    }
    if (buffer.trim()) await processStreamLine(buffer, agentName, roomId, result, lastToolBroadcastTime, setTime);
    await proc.exited;
    await stderrDone;
  } finally {
    clearTimeout(timeoutHandle);
  }
  // SEC-OPEN-012: Sanitize stderr before logging to avoid prompt injection in log pipelines
  if (result.stderrOutput.trim()) {
    logger.warn({ agentName, roomId, stderr: sanitizePromptContent(result.stderrOutput.trim()) }, 'subprocess stderr');
  }
  return result;
}

function readStderr(stderr: unknown, result: AgentStreamResult): Promise<void> {
  const stream = stderr as unknown as ReadableStream<Uint8Array>;
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  return (async () => {
    const chunks: string[] = [];
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(decoder.decode(value));
    }
    result.stderrOutput = chunks.join('');
  })();
}

// ---------------------------------------------------------------------------
// processStreamLine — private helper, ≤30 LOC
// ---------------------------------------------------------------------------

async function processStreamLine(
  line: string,
  agentName: string,
  roomId: string,
  result: AgentStreamResult,
  lastToolBroadcastTime: number,
  setLastToolBroadcastTime: (t: number) => void,
): Promise<void> {
  const events = parseStreamLine(line);
  for (const event of events) {
    if (event.type === 'tool_use') {
      logger.debug({ agentName, roomId, tool: event.name }, 'tool_use');
      const now = Date.now();
      if (now - lastToolBroadcastTime > 500) {
        setLastToolBroadcastTime(now);
        await broadcast(roomId, {
          type: 'tool_event',
          id: generateId(),
          agent: agentName,
          tool: event.name,
          description: formatToolDescription(event.name, event.input),
        });
      }
      await updateStatusAndBroadcast(agentName, roomId, AgentState.ToolUse, event.name);
    } else if (event.type === 'result') {
      applyResultEvent(event, agentName, result);
    }
  }
}

// ---------------------------------------------------------------------------
// applyResultEvent — private helper, ≤30 LOC
// ---------------------------------------------------------------------------

function applyResultEvent(event: ResultEvent, agentName: string, result: AgentStreamResult): void {
  result.hasResult = true;
  result.resultText = event.result;
  result.resultSessionId = validateSessionId(event.sessionId);
  result.resultCostUsd = event.costUsd;
  result.resultSuccess = event.success;
  result.resultDurationMs = event.durationMs;
  result.resultNumTurns = event.numTurns;
  result.resultInputTokens = event.inputTokens;
  result.resultOutputTokens = event.outputTokens;
  result.resultContextWindow = event.contextWindow;

  const durationSec = (event.durationMs / 1000).toFixed(1);
  const totalTokens = event.inputTokens + event.outputTokens;
  const denialCount = event.permissionDenials.length;
  const logCtx = {
    agentName, success: result.resultSuccess, costUsd: result.resultCostUsd,
    durationMs: event.durationMs, numTurns: event.numTurns,
    inputTokens: event.inputTokens, outputTokens: event.outputTokens,
    cacheReadTokens: event.cacheReadTokens,
    permissionDenials: denialCount > 0 ? event.permissionDenials : undefined,
  };
  const mark = result.resultSuccess ? '✓' : '✗';
  logger.info(logCtx, `${agentName} ${mark} ${durationSec}s | ${event.numTurns} turns | ${totalTokens.toLocaleString()} tokens | $${result.resultCostUsd.toFixed(4)}${denialCount ? ` | ${denialCount} denied` : ''}`);
}

// ---------------------------------------------------------------------------
// handleAgentResult
// ---------------------------------------------------------------------------

const MAX_AGENT_RESPONSE_BYTES = 256_000;

/**
 * Post-stream result handler. Covers:
 *   - stale-session / context-overflow detection → schedules retry, returns true
 *   - rate-limit detection → releases lock, schedules delayed retry, returns false
 *   - empty result → posts system message, returns false
 *   - SKIP suppression → returns false
 *   - happy path: truncate, persist, broadcast, chain mentions, update session/cost
 */
export async function handleAgentResult(
  sr: AgentStreamResult,
  roomId: string,
  agentName: string,
  model: string,
  context: InvocationContext,
): Promise<boolean> {
  if (sr.hasResult && !sr.resultSuccess) {
    return handleFailedResult(sr, roomId, agentName, context);
  }

  if (!sr.hasResult || !sr.resultText.trim()) {
    return handleEmptyResult(sr, roomId, agentName, context);
  }

  // SKIP mechanism: agent explicitly opted out
  if (/^skip\.?$/i.test(sr.resultText.trim())) {
    logger.debug({ agentName, roomId }, 'SKIP received — suppressing message');
    await updateStatusAndBroadcast(agentName, roomId, AgentState.Done);
    return false;
  }

  await persistAndBroadcast(sr, roomId, agentName, model, context);
  return false;
}

// ---------------------------------------------------------------------------
// handleFailedResult — private, ≤30 LOC
// ---------------------------------------------------------------------------

async function handleFailedResult(
  sr: AgentStreamResult,
  roomId: string,
  agentName: string,
  context: InvocationContext,
): Promise<boolean> {
  const lo = (s: string) => s.toLowerCase();
  const isContextOverflow = lo(sr.resultText).includes(CONTEXT_OVERFLOW_SIGNAL) || lo(sr.stderrOutput).includes(CONTEXT_OVERFLOW_SIGNAL);
  const isStaleSession = isContextOverflow || sr.resultText.includes('No conversation found') || sr.resultText.includes('conversation not found');
  if (isStaleSession) {
    clearAgentSession(agentName, roomId);
    const staleReason = isContextOverflow ? 'context too long' : 'stale session';
    logger.warn({ agentName, roomId, staleReason }, 'stale session detected — scheduling retry');
    if (isContextOverflow) {
      const display = agentName.charAt(0).toUpperCase() + agentName.slice(1);
      await postSystemMessage(roomId, `🔄 ${display} reinvocado (contexto agotado, nueva sesión)`);
    } else {
      await postSystemMessage(roomId, `Agent ${agentName}: ${staleReason} detected, retrying fresh...`);
    }
    context.isRespawn = isContextOverflow;
    const { scheduleInvocation } = await import('./agent-scheduler.js');
    scheduleInvocation(roomId, agentName, context, true, true);
    return true;
  }

  const errorMsg = sr.resultText || 'Agent returned an error result';
  await updateStatusAndBroadcast(agentName, roomId, AgentState.Error, errorMsg);
  await postSystemMessage(roomId, `Agent ${agentName} failed: ${errorMsg}`);
  return false;
}

// ---------------------------------------------------------------------------
// handleEmptyResult — private, ≤30 LOC
// ---------------------------------------------------------------------------

async function handleEmptyResult(
  sr: AgentStreamResult,
  roomId: string,
  agentName: string,
  context: InvocationContext,
): Promise<boolean> {
  const isRateLimit =
    sr.stderrOutput.includes('429') ||
    sr.stderrOutput.toLowerCase().includes('rate limit') ||
    sr.stderrOutput.toLowerCase().includes('overloaded') ||
    sr.stderrOutput.toLowerCase().includes('too many requests');

  if (isRateLimit && !context.rateLimitRetry) {
    logger.warn({ agentName, roomId }, 'rate limit detected — releasing lock and retrying in 12s');
    await postSystemMessage(roomId, `Agent ${agentName}: rate limited, retrying in 12s...`);
    context.rateLimitRetry = true;
    const key = `${agentName}:${roomId}`;
    const sched = await import('./agent-scheduler.js');
    sched.inFlight.delete(key);
    sched.activeInvocations.delete(key);
    sched.drainQueue();
    setTimeout(() => { sched.scheduleInvocation(roomId, agentName, context, false); }, 12_000);
    return false;
  }

  await postSystemMessage(roomId, `Agent ${agentName} returned no response.`);
  await updateStatusAndBroadcast(agentName, roomId, AgentState.Done);
  return false;
}

// ---------------------------------------------------------------------------
// persistAndBroadcast — private, ≤30 LOC
// ---------------------------------------------------------------------------

async function persistAndBroadcast(
  sr: AgentStreamResult,
  roomId: string,
  agentName: string,
  model: string,
  context: InvocationContext,
): Promise<void> {
  const resultText = maybeTruncate(sr.resultText, agentName, roomId);
  const { message, meta } = buildAgentMessage(sr, resultText, roomId, agentName, model);

  // SEC-FIX 5: Store sessionId in DB; message-bus.ts strips it before broadcast
  insertMessage({ id: message.id, roomId, author: agentName, authorType: 'agent',
    content: resultText, msgType: 'message', parentId: null, metadata: JSON.stringify(meta) });

  await broadcast(roomId, { type: 'new_message', message });
  await scheduleChainMentions(resultText, agentName, roomId, context);

  upsertAgentSession({ agentName, roomId, sessionId: sr.resultSessionId, model, status: 'done' });
  if (sr.resultCostUsd > 0) incrementAgentCost(agentName, roomId, sr.resultCostUsd);
  incrementAgentTurnCount(agentName, roomId);
  await updateStatusAndBroadcast(agentName, roomId, AgentState.Done);
}

function maybeTruncate(text: string, agentName: string, roomId: string): string {
  const byteLength = Buffer.byteLength(text, 'utf8');
  if (byteLength <= MAX_AGENT_RESPONSE_BYTES) return text;
  logger.warn({ agentName, roomId, byteLength, cap: MAX_AGENT_RESPONSE_BYTES },
    'agent response exceeds size cap — truncating before DB insert');
  return text.slice(0, MAX_AGENT_RESPONSE_BYTES) + '\n[...truncated]';
}

function buildAgentMessage(
  sr: AgentStreamResult,
  resultText: string,
  roomId: string,
  agentName: string,
  model: string,
): { message: Message; meta: Record<string, unknown> } {
  const msgId = generateId();
  const createdAt = nowIso();
  const meta = {
    sessionId: sr.resultSessionId, costUsd: sr.resultCostUsd, model,
    durationMs: sr.resultDurationMs, numTurns: sr.resultNumTurns,
    inputTokens: sr.resultInputTokens, outputTokens: sr.resultOutputTokens,
    contextWindow: sr.resultContextWindow,
  };
  const message: Message = {
    id: msgId, roomId, author: agentName, authorType: 'agent',
    content: resultText, msgType: 'message', parentId: null,
    metadata: { ...meta, sessionId: sr.resultSessionId ?? undefined },
    createdAt,
  };
  return { message, meta };
}

// ---------------------------------------------------------------------------
// scheduleChainMentions — private, ≤30 LOC
// ---------------------------------------------------------------------------

async function scheduleChainMentions(resultText: string, agentName: string, roomId: string, context: InvocationContext): Promise<void> {
  const updatedTurns = new Map(context.agentTurns);
  updatedTurns.set(agentName, (updatedTurns.get(agentName) ?? 0) + 1);

  const rawMentions = extractMentions(resultText);
  const chainedMentions = new Set<string>();
  const blockedAgents: string[] = [];
  for (const name of rawMentions) {
    if (name === agentName) continue;
    if ((updatedTurns.get(name) ?? 0) >= 5) blockedAgents.push(name);
    else chainedMentions.add(name);
  }

  logger.debug({ agentName, roomId, turns: Object.fromEntries(updatedTurns), allowed: [...chainedMentions], blocked: blockedAgents }, 'chain mentions');

  if (blockedAgents.length > 0) {
    await postSystemMessage(roomId, `Agent(s) ${blockedAgents.join(', ')} reached max turns (5). Mentions not invoked.`);
  }
  if (chainedMentions.size > 0) {
    const { invokeAgents } = await import('./agent-scheduler.js');
    const { sanitizePromptContent } = await import('./agent-prompt.js');
    invokeAgents(roomId, chainedMentions, sanitizePromptContent(resultText), updatedTurns);
  }
}
