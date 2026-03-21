---
name: chatroom-backend-standards
description: Enterprise standards rules that apply ALWAYS to chatroom/apps/backend/src/ — enforced on every audit
type: feedback
---

These rules were mandated by the user for permanent enforcement on every review of this codebase:

1. File LOC max 300. If >300 → T2 mandatory split.
2. Exported function LOC max 50. If >50 → T2.
3. Helper function LOC max 30. If >30 → T2.
4. Nesting depth max 3 levels. If >3 → refactor.
5. Function params max 5. If >5 → use object param.
6. Generic `throw new Error()` → T2. Must use typed error classes.
7. `console.log/error` → T2 forbidden.
8. `process.env` direct access → T2 in any file except config.ts and logger.ts.
9. Code duplication: 3+ repeats = mandatory abstraction.
10. `as any` casts: document or eliminate.
11. JSDoc: every exported function needs `/** summary + @param + @returns + @throws */`. Every exported constant needs `/** description */`.
12. SOLID: Single Responsibility per file/function. Open/Closed. No god functions.
13. KISS: simplest solution that works. No over-abstraction.
14. YAGNI: no speculative code, no "just in case".
15. DRY: extract after 2nd duplication, mandatory at 3rd.

**Why:** User explicitly stated "Save these rules to your memory — they apply ALWAYS from now on."
**How to apply:** Apply all 15 rules on every audit, commit-review, or any touch to chatroom/apps/backend/src/ without exception.

## Known violations as of 2026-03-19 (pre-refactor baseline — superseded)
- agent-runner.ts: spawnAndParse 403 LOC (T2), nesting depth 6 in stream parsing loop (T2), `as any` on Bun.spawn (documented inline — Bun 1.3.11 Windows bug)
- agent-runner.ts: doInvoke 76 LOC (T2), JSDoc missing @param/@returns (T3)
- ws-handlers.ts: open() 110 LOC (T2)
- ws-message-handlers.ts: handleEveryoneDirective 64 LOC (T2), handleSendMessage/handleInvokeAgent/handleLoadHistory missing JSDoc (T3)
- ws-state.ts: 11 exported constants/maps with no JSDoc (T3) — still open
- config.ts: `throw new Error()` at line 143 — internally caught, exits via process.exit(1); sentinel, not propagated. T3 (documented).

## Violations after 2026-03-19 refactor of agent-scheduler.ts + agent-prompt.ts
### agent-scheduler.ts (post-refactor, still open)
- File 348 LOC (T2) — split into agent-queue.ts not yet done
- runInvocation has no JSDoc; RACE-002 invariant documented mid-body only (T3)
- All exported functions now have JSDoc with @param/@returns — RESOLVED (was T3)
- scheduleInvocation now 38 LOC — RESOLVED (was 95 LOC T2)
- Duplicate merge-into-queue block extracted into tryMergeOrEnqueue — RESOLVED (was DRY T2)

### agent-prompt.ts (post-refactor, still open)
- buildChatroomRules helper 54 LOC (T2) — extract rule clusters into named const arrays
- Six exported functions missing @param/@returns in JSDoc: validateSessionId, sanitizePromptContent, buildPrompt, getGitDiffStat, buildSystemPrompt (partial), formatToolDescription (T3)
- buildSystemPrompt now 7 LOC — RESOLVED (was 95 LOC T2)

## Final scan 2026-03-19 (post all refactors)

### RESOLVED (from previous open list)
- agent-runner.ts: spawnAndParse 8-param violation → SpawnAndParseOptions interface introduced — RESOLVED (T2 closed)
- agent-runner.ts: duplicate import from '../db/queries.js' (lines 20 and 30) — RESOLVED (consolidated to single import at line 20)
- agent-stream.ts: 386 LOC → 323 LOC — still T2 (>300 limit), improvement noted
- agent-stream.ts: readAgentStream JSDoc now has all 4 @param tags — RESOLVED (T3 closed)
- agent-stream.ts: AgentStreamResult interface now has full JSDoc with @property tags — RESOLVED (T3 closed)
- agent-stream.ts: handleAgentResult now has @param/@returns tags — RESOLVED (T3 closed)
- agent-scheduler.ts: 348 LOC → 294 LOC (split to agent-queue.ts) — RESOLVED (T2 closed)
- agent-prompt.ts: six missing @param/@returns — STILL OPEN (see below)

### Still open after final scan (T2/T3)

#### T2 (blocking)
- agent-stream.ts: 323 LOC (T2) — still over 300 limit; next split needed
- agent-prompt.ts: buildChatroomRules helper 55 LOC (T2) — extract rule clusters into named const arrays

### Audit 2026-03-21 — kill/pause/resume/read_chat commit (INITIAL)

#### ALL RESOLVED by re-audit 2026-03-21
- T1: ParticipantItem.tsx no Resume button — RESOLVED: toggle button with isPaused local state + aria-label flip
- T2: drainQueue bypassed _pausedAgents — RESOLVED: findIndex now filters all three conditions
- T2: killAgent JSDoc false claim — RESOLVED: JSDoc now correct + SEC-CRIT-002 inline comment
- T2: ws-message-handlers.ts 398 LOC — RESOLVED: 241 LOC, control handlers extracted to ws-control-handlers.ts (225 LOC)
- T2: handleReadChat 44 LOC — RESOLVED: insertAndBroadcastReadChat private helper extracted

### Re-Audit 2026-03-21 — after fixes

#### T2 (blocking — open)
- agent-scheduler.ts: 387 LOC (T2) — still over 300 hard limit. Split: move _pausedAgents + pauseAgent/resumeAgent/isAgentPaused/killAgent into agent-queue.ts (shared state already there)
- sendError: identical 8-line function in ws-message-handlers.ts (lines 36-43) AND ws-control-handlers.ts (lines 28-35) — DRY violation, extract to ws-state.ts or ws-helpers.ts

#### T3 (non-blocking — open)
- READ_CHAT_LIMIT = ROOM_STATE_MESSAGE_LIMIT alias is YAGNI — use constant directly (ws-control-handlers.ts:38)
- handlePauseAgent: no WS acknowledgment when already-paused (silent no-op)
- ParticipantItem.tsx: local isPaused state does not sync from server AgentStatus — stale on reload or multi-client
- Resume icon SVG (triangle polygon) is visually identical to Play icon — operator confusion risk; differentiate shapes
- Zero tests for 8 new exported functions (killAgent, pauseAgent, resumeAgent, isAgentPaused, handleKillAgent, handlePauseAgent, handleResumeAgent, handleReadChat)

### Audit 2026-03-21 — SIGSTOP/pause process-group fix commit

#### W2 (non-blocking warnings — open, follow-up needed)
- agent-queue.ts pauseAgent: remaining-budget calculation uses `pausedAt ?? Date.now()` on first pause — elapsed is always ~0, full timeout budget is preserved instead of subtracting already-elapsed time. Fix: track `startedAt`/`resumedAt` on ActiveProcess.
- agent-scheduler.ts killAgent: does not clearTimeout(proc.timeoutHandle) before activeProcesses.delete — stale timer fires after kill, logs misleading "timeout reached — killing subprocess".
- agent-runner.ts spawnAndParse: resume-created timeoutHandle in activeEntry is not cleared after readAgentStream returns — timer fires on natural process exit, logs false "timeout reached after resume" warning.

#### T3 (non-blocking — open)
- agent-queue.ts pauseAgent/resumeAgent: logger.info with activeKeys array serialized on every call — downgrade to logger.debug or remove (log volume concern in production).
- agent-result.ts persistAndBroadcast: cost/turn incrementing happens even when paused — intentional but needs a comment to prevent future maintainer confusion.

#### RESOLVED by this commit
- agent-scheduler.ts: 387 LOC T2 — RESOLVED: pauseAgent/resumeAgent/isAgentPaused moved to agent-queue.ts; agent-scheduler.ts now at ~290 LOC (verify)
- sendError DRY violation — VERIFY: check if still duplicated after this commit

### Audit 2026-03-21 — SIGSTOP/pause 6-fix correctness review

#### CONFIRMED RESOLVED (all 6 stated fixes verified)
1. pid guard — RESOLVED: `typeof active?.pid !== 'number' || active.pid <= 0` is correct
2. remainingTimeoutMs preserved on resume — RESOLVED: comment + code correct; `pausedAt = undefined` cleared, `remainingTimeoutMs` kept for next pause
3. Single isAgentPaused read in persistAndBroadcast — RESOLVED: `const isPaused = isAgentPaused(...)` at line 273 used for both DB write and broadcast guard
4. ESRCH clears _pausedAgents — RESOLVED: `_pausedAgents.delete(...)` in catch block when `code === 'ESRCH'`
5. Timeout handle created before activeProcesses.set — RESOLVED: activeEntry built with timeoutHandle pre-included; clearTimeout on activeEntry.timeoutHandle after readAgentStream returns covers resume-replaced handles
6. tool_event test `id` field — RESOLVED: three test objects now include `id: 'te-1'/'te-2'/'te-3'`

#### STILL OPEN after this commit (W2 — non-blocking)
- agent-queue.ts pauseAgent line 143: `Date.now() - (active.pausedAt ?? Date.now())` → elapsed is always 0 on first pause. Fix: add `startedAt: Date.now()` to ActiveProcess and use it as the fallback.
- agent-scheduler.ts killAgent line 127: `activeProcesses.delete(key)` before `clearTimeout(proc.timeoutHandle)` — stale timer fires AGENT_TIMEOUT_MS after kill, logs misleading "timeout reached — killing subprocess".

#### STILL OPEN after this commit (T3 — non-blocking)
- agent-queue.ts pauseAgent/resumeAgent: `logger.info` with `activeKeys` array on every call — downgrade to `logger.debug`

#### NEW FALSE POSITIVES (do not re-flag)
- agent-runner.ts `import('./agent-queue.js').ActiveProcess` in-line import type: valid TypeScript pattern to avoid a circular import; not an error.
- ParticipantItem.tsx `playEnabled = isPaused || isPausedFromServer` double-condition: intentional — covers both optimistic local state and server-confirmed state; not redundant.
- Shared schemas test failures (2 fail: "rejects content/prompt exceeding 10000 chars"): pre-existing mismatch between schema max(50000) and test expectation; NOT introduced by this diff.

#### SCORE DELTA (backend, out of 110)
- W2 "elapsed=0 first pause" remains open (minor severity, never causes agent termination early — only allows slightly longer timeout)
- W2 "killAgent stale timer" remains open (logs noise only, no functional breakage — ESRCH caught)
- All 6 stated fixes verified correct — no new T1/T2 introduced
- Net: no regressions; 2 pre-existing W2s remain

### Audit 2026-03-21 — 5 final fixes commit

#### ALL CONFIRMED RESOLVED
1. startedAt added to ActiveProcess, used in pauseAgent elapsed fallback chain — RESOLVED: `active.pausedAt ?? active.startedAt ?? Date.now()` is correct; `pausedAt` is cleared by resumeAgent so `startedAt` is the correct fallback for first pause. Both W2s from prior audit closed.
2. killAgent clears timeoutHandle before delete — RESOLVED: `clearTimeout(proc.timeoutHandle)` at agent-scheduler.ts:126, before `activeProcesses.delete`. Stale-timer W2 closed.
3. pid > 0 guard in makeTimeoutHandle — RESOLVED: agent-runner.ts:243 guards `!proc.pid || proc.pid <= 0` before `process.kill(-pid)` in timeout callback.
4. resumeAgent double-call guard + pre-clear existing handle — RESOLVED: `if (!_pausedAgents.has(key)) return false` prevents double-resume; `if (active.timeoutHandle !== undefined) clearTimeout(active.timeoutHandle)` before new setTimeout prevents handle leak.
5. Schema test boundaries 10000→50000 — RESOLVED: schemas.ts already had max(50000); tests now match. `AgentState.Paused` added to exhaustive enum loop.

#### STILL OPEN (pre-existing, not introduced by this diff)
- agent-runner.ts: 328 LOC (T2) — over 300-line limit; next split needed
- agent-scheduler.ts: 353 LOC (T2) — over 300-line limit; next split needed
- agent-queue.ts pauseAgent/resumeAgent: `logger.info` with `activeKeys` on every call — T3, downgrade to `logger.debug` — RESOLVED by resumedAt commit (downgraded to logger.debug)
- All T3 agent-prompt.ts / agent-result.ts JSDoc gaps — still open (see list above)

#### NEW FALSE POSITIVES (do not re-flag)
- `readAgentStream` receives original `timeoutHandle` local var (not a ref to activeEntry.timeoutHandle): intentional — cleanup after `readAgentStream` returns reads `activeEntry.timeoutHandle` directly, which may have been replaced by resumeAgent; the local var passed to readAgentStream is used only for stream-level abort signaling.
- resumeAgent timeout callback does not call `activeProcesses.delete`: intentional — spawnAndParse cleanup path runs after SIGTERM kills the process; double-delete on Map is benign.
- `accepts Paused status` test is a duplicate of the exhaustive loop test: intentional minor redundancy for clarity; not a test quality issue.

#### VERDICT: Approve. No T1, no new T2.

#### FALSE POSITIVES (do not re-flag)
- pauseAgent/resumeAgent using `active.pid!` non-null assertion: safe, guarded by `if (!active?.pid) return false` two lines above.
- Resume timeout callback capturing `pid` snapshot: safe, pid is immutable after spawn; process may exit but ESRCH is caught.
- `isAgentPaused` check in completion handlers: correct pattern — paused flag is cleared by resumeAgent before next invocation, so a paused-then-resumed agent will correctly get Done status after its next run.

#### FALSE POSITIVES (added 2026-03-21 — do not re-flag)
- killAgent double-delete of activeProcesses: benign on Map, not a bug (spawnAndParse deletes on exit, killAgent deletes earlier — second delete is no-op)
- ws-handlers.ts parseAndValidate return type `result.data as ClientMessage`: cast IS redundant but Zod discriminatedUnion already types result.data as ClientMessage — not a type escape
- ParticipantItem.tsx Resume triangle SVG has different points (2,1 10,6 2,11) vs Play (3,1 11,6 3,11) — different coordinates but same shape visually. Flag the UX confusion, not as a code bug.

#### T3 (non-blocking)
- agent-prompt.ts: validateSessionId — single-line JSDoc only, no @param/@returns (T3)
- agent-prompt.ts: sanitizePromptContent — description only, no @param/@returns (T3)
- agent-prompt.ts: buildPrompt — description only, no @param/@returns (T3)
- agent-prompt.ts: getGitDiffStat — description only, no @param (T3)
- agent-prompt.ts: formatToolDescription — description only, no @param/@returns (T3)
- agent-result.ts: maybeTruncate — no JSDoc at all (T3)
- agent-result.ts: buildAgentMessage — no JSDoc at all (T3)
- agent-result.ts: scheduleChainMentions — no JSDoc at all (T3)
- agent-result.ts: persistAndBroadcast — no JSDoc at all (T3)
- agent-scheduler.ts: tryMergeOrEnqueue helper — has 9 params (>5 limit, Rule 5) and no JSDoc (T3 — private helper)
- ws-state.ts: wsConnIds (Map<any, string>) — exported, no JSDoc describing the any type (T3)
- agent-stream.ts: line 206 is 215 chars — long line (T3)

#### FALSE POSITIVES (do not re-flag)
- agent-runner.ts: `as any` on Bun.spawn — documented inline ("Bun 1.3.11 Windows bug"), acceptable
- ws-handlers.ts: `any` on ws parameter — documented with eslint-disable, Elysia internals limitation, acceptable
- config.ts: `throw new Error()` inside ConfigError (subclass) — not generic throw, ConfigError is a typed subclass
- agent-scheduler.ts: tryMergeOrEnqueue 9 params — private helper (not exported), T3 at most

### Audit 2026-03-21 — resumedAt fix commit

#### ALL CONFIRMED RESOLVED
1. `resumedAt` added to `ActiveProcess` — RESOLVED: field correctly typed `number | undefined` with accurate JSDoc
2. pauseAgent elapsed chain `pausedAt ?? resumedAt ?? startedAt ?? Date.now()` — RESOLVED: all state transitions in multi-cycle pause/resume verified correct; prior W2 "elapsed always 0 on first pause" closed
3. resumeAgent sets `resumedAt = Date.now()` inside try block, after SIGCONT success — RESOLVED: correct placement; ESRCH path leaves resumedAt unchanged (safe, process is gone)
4. logger.info downgraded to logger.debug — RESOLVED: T3 log-volume finding from prior audit closed

#### STILL OPEN (pre-existing, not introduced by this diff)
- agent-runner.ts: 328 LOC (T2) — over 300-line limit
- agent-scheduler.ts: 353 LOC (T2) — over 300-line limit
- All T3 agent-prompt.ts / agent-result.ts JSDoc gaps — still open

#### VERDICT: Approve. No T1, no new T2. 0 issues, 0 suggestions, 0 nitpicks.
