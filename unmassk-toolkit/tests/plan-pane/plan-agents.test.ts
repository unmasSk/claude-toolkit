// #98 step 3.1: agents launched while a step is in progress show under it, with
// result, time and fix rounds, and leave when the step ends (D-150, D-151).
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import {
  ISSUE_TASK,
  callPlan,
  drawnRows,
  isDoneStep,
  endAgent,
  minutes,
  mountPane,
  rounds,
  rowIndex,
  spawnAgent,
  startSession,
} from './plan-kit.ts'

const FIRST = ISSUE_TASK.phases[0].steps[0]
const SECOND = ISSUE_TASK.phases[0].steps[1]
const ULTRON = 'unmassk-toolkit:ultron'
const CERBERUS = 'unmassk-toolkit:cerberus'

const withFirstStepRunning = async ($: any, on: any) => {
  const session = await startSession($, on)
  await callPlan($, { task: ISSUE_TASK })
  await callPlan($, { step: FIRST.id, status: 'in_progress' })
  return session
}

// The rows strictly between a step's row and the next step's row.
const rowsUnder = (rows: string[], step: string, nextStep: string) =>
  rows.slice(rowIndex(rows, step) + 1, rowIndex(rows, nextStep))

test('should_show_an_agent_under_the_step_in_progress_while_it_runs', async ($, on) => {
  const { opens } = await withFirstStepRunning($, on)

  await spawnAgent($, 'a1', ULTRON)

  const rows = await drawnRows(await mountPane($, opens[0]!.id, 'desktop'))
  const under = rowsUnder(rows, FIRST.title, SECOND.title)
  expect(under.filter(row => /ultron/i.test(row)), `ultron under ${FIRST.id}: ${JSON.stringify(rows)}`).toHaveLength(1)
})

test('should_show_the_agent_result_and_time_when_it_ends', async ($, on) => {
  const { opens } = await withFirstStepRunning($, on)
  await spawnAgent($, 'a1', ULTRON)

  await endAgent($, 'a1', 'GREEN — 12/12 tests pass\nnone\nreport: /tmp/r.md', 120_000)

  const rows = await drawnRows(await mountPane($, opens[0]!.id, 'desktop'))
  const agentRows = rowsUnder(rows, FIRST.title, SECOND.title).join('\n')
  expect(agentRows, `the answer's first line: ${JSON.stringify(rows)}`).toContain('GREEN — 12/12 tests pass')
  expect(agentRows, 'the rest of the answer stays out').not.toContain('report:')
  expect(agentRows, 'the time it took').toMatch(minutes(2))
})

test('should_count_a_fix_round_when_an_agent_type_runs_again_in_the_step', async ($, on) => {
  const { opens } = await withFirstStepRunning($, on)
  await spawnAgent($, 'a1', ULTRON)
  await endAgent($, 'a1', 'GREEN — built', 60_000)
  await spawnAgent($, 'a2', CERBERUS)
  await endAgent($, 'a2', 'CHANGES — one finding', 60_000)

  await spawnAgent($, 'a3', ULTRON)

  const rows = await drawnRows(await mountPane($, opens[0]!.id, 'desktop'))
  const stepAndAgents = [rows[rowIndex(rows, FIRST.title)], ...rowsUnder(rows, FIRST.title, SECOND.title)]
  expect(stepAndAgents.join('\n'), `round 2 shown in the step: ${JSON.stringify(rows)}`).toMatch(rounds(2))
})

test('should_drop_the_agents_and_keep_the_tick_and_rounds_when_the_step_ends', async ($, on) => {
  const { opens } = await withFirstStepRunning($, on)
  for (const [id, type] of [['a1', ULTRON], ['a2', CERBERUS], ['a3', ULTRON]] as const) {
    await spawnAgent($, id, type)
    await endAgent($, id, 'GREEN — ok', 60_000)
  }

  await callPlan($, { step: FIRST.id, status: 'done' })

  const rows = await drawnRows(await mountPane($, opens[0]!.id, 'desktop'))
  const stepRow = rows[rowIndex(rows, FIRST.title)]
  expect(rowsUnder(rows, FIRST.title, SECOND.title), `no agent left under ${FIRST.id}`).toEqual([])
  expect(rows.filter(row => /ultron|cerberus/i.test(row)), 'no agent anywhere').toEqual([])
  expect(isDoneStep(stepRow), `the step is ticked: ${stepRow}`).toBe(true)
  expect(stepRow, 'with its rounds').toMatch(rounds(2))
})

test('should_show_agents_under_the_next_step_once_it_starts', async ($, on) => {
  const { opens } = await withFirstStepRunning($, on)
  await callPlan($, { step: FIRST.id, status: 'done' })
  await callPlan($, { step: SECOND.id, status: 'in_progress' })

  await spawnAgent($, 'a1', ULTRON)

  const rows = await drawnRows(await mountPane($, opens[0]!.id, 'desktop'))
  const nextPhase = ISSUE_TASK.phases[1].title
  expect(rowsUnder(rows, FIRST.title, SECOND.title), `nothing under the finished ${FIRST.id}`).toEqual([])
  expect(rowsUnder(rows, SECOND.title, nextPhase).filter(row => /ultron/i.test(row)), `ultron under ${SECOND.id}: ${JSON.stringify(rows)}`).toHaveLength(1)
})

test('should_show_seconds_when_an_agent_took_under_a_minute', async ($, on) => {
  const { opens } = await withFirstStepRunning($, on)
  await spawnAgent($, 'a1', ULTRON)
  await spawnAgent($, 'a2', CERBERUS)

  await endAgent($, 'a1', 'GREEN — quick', 12_000)
  await endAgent($, 'a2', 'CLEAN — one minute', 60_000)

  const rows = await drawnRows(await mountPane($, opens[0]!.id, 'desktop'))
  const quick = rows.find(row => row.includes('GREEN — quick'))
  const minute = rows.find(row => row.includes('CLEAN — one minute'))
  expect(quick, `12 s, never 0 min: ${JSON.stringify(rows)}`).toMatch(/\b12 s\b/)
  expect(quick, 'not rounded to minutes').not.toMatch(/min\b/)
  expect(minute, 'a full minute in minutes').toMatch(minutes(1))
})

const INTERRUPTED_ENDS = [
  { name: 'interrupted', reason: 'aborted', isAborted: true, answer: 'GREEN — half of the tests written', says: /interrupted/i },
  { name: 'failed', reason: 'error', isAborted: false, answer: '', says: /failed/i },
] as const

for (const end of INTERRUPTED_ENDS) {
  test(`should_show_the_agent_as_${end.name}_never_as_finished_when_its_turn_ends_${end.reason}`, async ($, on) => {
    const { opens } = await withFirstStepRunning($, on)
    await spawnAgent($, 'a1', ULTRON)

    await $.turn.complete({ agentId: 'a1', answer: end.answer, durationMs: 12_000, isAborted: end.isAborted, turnId: 't-a1', reason: end.reason })

    const rows = await drawnRows(await mountPane($, opens[0]!.id, 'desktop'))
    const agentRows = rowsUnder(rows, FIRST.title, SECOND.title).filter(row => /ultron/i.test(row))
    expect(agentRows, `one ultron row: ${JSON.stringify(rows)}`).toHaveLength(1)
    expect(agentRows[0], `the row says it was ${end.name}`).toMatch(end.says)
    expect(agentRows[0], 'a partial answer is not shown as its result').not.toContain('GREEN')
    expect(agentRows[0], 'it is no longer running').not.toContain('running')
  })
}
