// #98 Cerberus F2: each agent of the step in progress shows how its own turn ended:
// an answer shows its first line, aborted shows interrupted, error and refusal show failed.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import { ISSUE_TASK, callPlan, drawnRows, mountPane, rowIndex, spawnAgent, startSession } from './plan-kit.ts'

const FIRST = ISSUE_TASK.phases[0].steps[0]
const SECOND = ISSUE_TASK.phases[0].steps[1]

// Stopped turns carry a partial answer, so a leaked answer shows in the row.
const STOPPED = [
  { id: 'a2', name: 'cerberus', end: { reason: 'aborted', isAborted: true }, answer: 'CLEAN — half read', says: 'interrupted' },
  { id: 'a3', name: 'argus', end: { reason: 'error', isAborted: false }, answer: 'SECURE — partial', says: 'failed' },
  {
    id: 'a4',
    name: 'moriarty',
    end: { reason: 'refusal', isAborted: false, refusal: { category: null, explanation: null } },
    answer: 'BROKEN — refused midway',
    says: 'failed',
  },
] as const
const ANSWERED = { id: 'a1', name: 'ultron', end: { reason: 'answer', isAborted: false }, answer: 'GREEN — built', says: 'GREEN — built' } as const
const ALL = [ANSWERED, ...STOPPED]

test('should_show_each_agent_as_its_own_turn_ended_answer_interrupted_or_failed', async ($, on) => {
  const { opens } = await startSession($, on)
  await callPlan($, { task: ISSUE_TASK })
  await callPlan($, { step: FIRST.id, status: 'in_progress' })
  for (const agent of ALL) await spawnAgent($, agent.id, `unmassk-toolkit:${agent.name}`)

  for (const agent of ALL) {
    await $.turn.complete({ agentId: agent.id, answer: agent.answer, durationMs: 12_000, turnId: `t-${agent.id}`, ...agent.end })
  }

  const rows = await drawnRows(await mountPane($, opens[0]!.id, 'desktop'))
  const under = rows.slice(rowIndex(rows, FIRST.title) + 1, rowIndex(rows, SECOND.title))
  const rowOf = (name: string) => under.filter(row => row.includes(name))
  expect(ALL.map(agent => rowOf(agent.name).length), `one row per agent: ${JSON.stringify(rows)}`).toEqual([1, 1, 1, 1])
  expect(
    ALL.map(agent => rowOf(agent.name)[0]!.includes(agent.says)),
    `answer / interrupted / failed / failed, each on its own agent: ${JSON.stringify(under)}`,
  ).toEqual([true, true, true, true])
  expect(STOPPED.map(agent => rowOf(agent.name)[0]!.includes(agent.answer)), 'a stopped turn never shows its answer').toEqual([false, false, false])
  expect(ALL.map(agent => rowOf(agent.name)[0]!.includes('running')), 'none still running').toEqual([false, false, false, false])
})
