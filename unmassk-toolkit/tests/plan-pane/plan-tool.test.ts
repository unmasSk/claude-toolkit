// #98 step 2.1: the plan tool the model calls, and the pane's drawn tree (D-151, D-152).
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import {
  ISSUE_TASK,
  PLAN_TOOL,
  SURFACES,
  TICK,
  callPlan,
  drawnRows,
  mountPane,
  rowIndex,
  startSession,
} from './plan-kit.ts'

test('should_register_the_plan_tool_when_the_session_starts', async ($, on) => {
  const { registered } = await startSession($, on)

  expect(registered.map(spec => spec.name), 'tools registered on session.start').toContain('plan')
})

test('should_register_the_plan_tool_with_the_arguments_the_model_sends', async ($, on) => {
  const { registered } = await startSession($, on)

  const plan = registered.find(spec => spec.name === 'plan')

  expect(Object.keys(plan?.inputSchema?.properties ?? {}).sort(), 'the arguments the model may send').toEqual(['status', 'step', 'task'])
  expect(plan?.inputSchema?.properties?.status?.enum, 'the two statuses a step can take').toEqual(['in_progress', 'done'])
})

test('should_offer_the_plan_tool_from_the_start_not_behind_tool_search', async ($, on) => {
  // The bottom places tools as the engine does for an MCP tool: behind ToolSearch.
  const described: string[] = []
  on('tool.describe', async (_$: unknown, e: any) => {
    described.push(e.tool)
    return { description: `engine text for ${e.tool}`, isDeferred: true }
  })
  await startSession($, on)
  const asked = (tool: string) =>
    $.tool.describe({ tool, description: 'd', isDeferred: true, provider: { plugin: 'engine', tier: 'core' } } as any)

  // tool.describe is what the engine reads to place a tool (2.1.287 drops isDeferred at tool.register).
  const plan = await asked(PLAN_TOOL)
  const other = await asked('mcp__other-server__tool')

  // Deferred, the model would have to search for the tool before it could send the task (phase 5).
  expect(plan.isDeferred, 'the model sees the plan tool from the start').toBe(false)
  expect(plan.description, "the engine's description kept").toBe(`engine text for ${PLAN_TOOL}`)
  expect(other.isDeferred, 'only the plan tool is pinned in front').toBe(true)
  expect(described, 'both asks reached the engine beneath').toEqual([PLAN_TOOL, 'mcp__other-server__tool'])
})

test('should_draw_title_issue_phases_and_steps_in_order_when_the_model_sends_the_whole_task', async ($, on) => {
  const { opens } = await startSession($, on)

  const sent = await callPlan($, { task: ISSUE_TASK })
  expect(sent.deny, 'the plan tool answered the call').toBeUndefined()

  for (const surface of SURFACES) {
    const ui = await mountPane($, opens[0]!.id, surface)
    const rows = await drawnRows(ui)
    const order = [
      rowIndex(rows, ISSUE_TASK.title),
      rowIndex(rows, ISSUE_TASK.phases[0].title),
      rowIndex(rows, ISSUE_TASK.phases[0].steps[0].title),
      rowIndex(rows, ISSUE_TASK.phases[0].steps[1].title),
      rowIndex(rows, ISSUE_TASK.phases[1].title),
      rowIndex(rows, ISSUE_TASK.phases[1].steps[0].title),
    ]
    expect(order.every(at => at >= 0), `every title drawn on ${surface}: ${JSON.stringify(rows)}`).toBe(true)
    expect([...order].sort((a, b) => a - b), `task, phases and steps in order on ${surface}`).toEqual(order)
    expect(rows[order[0]], `issue on the task row on ${surface}`).toContain('#98')
    expect(rows.filter(row => row.includes(TICK)), `nothing ticked yet on ${surface}`).toEqual([])
    await ui.unmount()
  }
})

test('should_draw_a_plain_task_titled_by_the_request_when_there_is_no_issue', async ($, on) => {
  const { opens } = await startSession($, on)
  const plain = {
    title: 'Investigar el fallo del arranque',
    issue: null,
    steps: [
      { id: '1', title: 'Leer el informe de arranque' },
      { id: '2', title: 'Reproducir con un repo desechable' },
    ],
  }

  const sent = await callPlan($, { task: plain })
  expect(sent.deny, 'the plan tool answered the call').toBeUndefined()

  const ui = await mountPane($, opens[0]!.id, 'desktop')
  const rows = await drawnRows(ui)
  const titleAt = rowIndex(rows, plain.title)
  expect(titleAt, `the request heads the pane: ${JSON.stringify(rows)}`).toBe(0)
  expect(rows[titleAt], 'no issue number on a plain task').not.toContain('#')
  expect(rowIndex(rows, plain.steps[0].title)).toBeGreaterThan(titleAt)
  expect(rowIndex(rows, plain.steps[1].title)).toBeGreaterThan(rowIndex(rows, plain.steps[0].title))
})

test('should_mark_the_step_in_progress_and_then_tick_it_when_the_model_changes_its_status', async ($, on) => {
  const { opens } = await startSession($, on)
  await callPlan($, { task: ISSUE_TASK })
  const ui = await mountPane($, opens[0]!.id, 'desktop')
  const step = ISSUE_TASK.phases[0].steps[0]
  const pendingRow = (await drawnRows(ui))[rowIndex(await drawnRows(ui), step.title)]

  const started = await callPlan($, { step: step.id, status: 'in_progress' })
  const runningRows = await drawnRows(ui)
  const runningRow = runningRows[rowIndex(runningRows, step.title)]

  const ended = await callPlan($, { step: step.id, status: 'done' })
  const doneRows = await drawnRows(ui)

  expect([started.deny, ended.deny], 'both status changes answered').toEqual([undefined, undefined])
  expect(runningRow, 'the step in progress is drawn apart from a pending one').not.toEqual(pendingRow)
  expect(runningRow, 'a step in progress is not ticked').not.toContain(TICK)
  expect(doneRows[rowIndex(doneRows, step.title)], 'the finished step is ticked').toContain(TICK)
  expect(doneRows.filter(row => row.includes(TICK)), 'only that step is ticked').toHaveLength(1)
})

test('should_refuse_a_status_change_for_a_step_the_task_does_not_have', async ($, on) => {
  const { opens } = await startSession($, on)
  await callPlan($, { task: ISSUE_TASK })

  const answer = await callPlan($, { step: '9.9', status: 'done' })

  // A change that lands nowhere must reach the model as a failure, never as a silent ok.
  expect(answer.deny !== undefined || answer.isError === true, `refused: ${JSON.stringify(answer)}`).toBe(true)
  expect(JSON.stringify(answer), 'the refusal names the step').toContain('9.9')
  const rows = await drawnRows(await mountPane($, opens[0]!.id, 'desktop'))
  expect(rowIndex(rows, ISSUE_TASK.title), 'the task is still drawn').toBeGreaterThanOrEqual(0)
  expect(rows.filter(row => row.includes(TICK)), 'nothing ticked').toEqual([])
})

test('should_refuse_a_status_change_when_no_task_was_sent', async ($, on) => {
  await startSession($, on)

  const answer = await callPlan($, { step: '1', status: 'in_progress' })

  expect(answer.deny !== undefined || answer.isError === true, `refused: ${JSON.stringify(answer)}`).toBe(true)
  expect(JSON.stringify(answer), 'it is the plan tool refusing, not the bottom').not.toContain('reached the bottom')
})
