// #98 step 4.1: plan tool input -> the mod's state -> the drawn tree, and a finished
// task folding to one line when the next starts (D-153).
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import {
  ISSUE_TASK,
  SURFACES,
  FOLDED_MARKS,
  callPlan,
  doneSteps,
  drawnRows,
  isDoneStep,
  markOf,
  took,
  mountPane,
  rowIndex,
  startSession,
} from './plan-kit.ts'

const STEP_IDS = ISSUE_TASK.phases.flatMap(phase => phase.steps.map(step => step.id))
const STEP_TITLES = ISSUE_TASK.phases.flatMap(phase => phase.steps.map(step => step.title))

// What the state must hold for the task this test sent: every field it wrote.
const sentAsState = (status: (id: string) => string) => ({
  title: ISSUE_TASK.title,
  issue: ISSUE_TASK.issue,
  phases: ISSUE_TASK.phases.map(phase => ({
    title: phase.title,
    steps: phase.steps.map(step => ({ id: step.id, title: step.title, status: status(step.id) })),
  })),
})

const finishTask = async ($: any) => {
  for (const id of STEP_IDS) {
    await callPlan($, { step: id, status: 'in_progress' })
    await callPlan($, { step: id, status: 'done' })
  }
}

test('should_keep_every_field_the_model_sent_and_draw_it_back', async ($, on) => {
  const { opens, planReads } = await startSession($, on)

  await callPlan($, { task: ISSUE_TASK })
  await callPlan($, { step: '2.1', status: 'done' })
  await (await mountPane($, opens[0]!.id, 'terminal')).unmount()

  // The value the pane's drawing read from the module's state, not a copy of the input.
  const value: any = planReads[planReads.length - 1]
  expect(value?.current, `state the drawing read: ${JSON.stringify(planReads)}`).toMatchObject(
    sentAsState(id => (id === '2.1' ? 'done' : 'pending')),
  )
  const kept = value.current
  const keptTitles = [kept.title, ...kept.phases.flatMap((p: any) => [p.title, ...p.steps.map((s: any) => s.title)])]
  for (const surface of SURFACES) {
    const ui = await mountPane($, opens[0]!.id, surface)
    const rows = await drawnRows(ui)
    await ui.unmount()
    expect(keptTitles.filter(title => rowIndex(rows, title) < 0), `kept titles not drawn on ${surface}`).toEqual([])
    expect(rows[rowIndex(rows, kept.title)], `kept issue drawn on ${surface}`).toContain(`#${kept.issue}`)
    expect(doneSteps(rows).length, `kept done steps ticked on ${surface}`).toBe(
      kept.phases.flatMap((p: any) => p.steps).filter((s: any) => s.status === 'done').length,
    )
  }
})

test('should_keep_a_finished_task_whole_with_its_total_time_until_the_next_starts', async ($, on) => {
  const { opens, clock } = await startSession($, on)
  await callPlan($, { task: ISSUE_TASK })
  await clock.advance(25 * 60_000)

  await finishTask($)

  const rows = await drawnRows(await mountPane($, opens[0]!.id, 'desktop'))
  expect(STEP_TITLES.filter(title => !isDoneStep(rows[rowIndex(rows, title)])), `unticked: ${JSON.stringify(rows)}`).toEqual([])
  expect(rows[rowIndex(rows, ISSUE_TASK.title)], 'the task row carries its total time').toMatch(took('25m 00s'))
})

test('should_fold_the_finished_tasks_into_one_count_line_when_the_next_starts', async ($, on) => {
  const { opens, clock } = await startSession($, on)
  await callPlan($, { task: ISSUE_TASK })
  await clock.advance(25 * 60_000)
  await finishTask($)
  const next = { title: 'Publicar 1.51.1', issue: null, steps: [{ id: '1', title: 'Subir la version' }] }

  await callPlan($, { task: next })

  const rows = await drawnRows(await mountPane($, opens[0]!.id, 'desktop'))
  // D-170: finished tasks fold into one «› N terminadas» line, never one line each.
  expect(rows.filter(row => row.includes(ISSUE_TASK.title)), `no line per finished task: ${JSON.stringify(rows)}`).toEqual([])
  expect(rows.some(row => row.includes('› 1 terminada')), `one count line: ${JSON.stringify(rows)}`).toBe(true)
  expect(STEP_TITLES.filter(title => rowIndex(rows, title) >= 0), 'its steps are no longer drawn').toEqual([])
  expect(rowIndex(rows, next.title), 'the new task heads the pane').toBe(0)
  expect(rowIndex(rows, next.steps[0].title)).toBeGreaterThan(0)
})
