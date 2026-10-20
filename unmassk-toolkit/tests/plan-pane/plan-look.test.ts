// #98 D-158: the pane's look, copied from the Checklist mod Bex sent: a bar of one
// segment per step with the done/total count beside it, a circle per step (empty
// pending, marked done), a long step cut with an ellipsis. D-151's layout stays.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import {
  DONE_MARKS,
  ISSUE_TASK,
  PENDING,
  SURFACES,
  callPlan,
  drawnRows,
  markOf,
  mountPane,
  progressOf,
  rowsOf,
  rowIndex,
  startSession,
} from './plan-kit.ts'

const STEPS = ISSUE_TASK.phases.flatMap(phase => phase.steps)
const PLAIN = {
  title: 'Investigar el fallo del arranque',
  issue: null,
  steps: [
    { id: '1', title: 'Leer el informe de arranque' },
    { id: '2', title: 'Reproducir con un repo desechable' },
  ],
}
// mountPane draws into 60 columns.
const BODY_COLUMNS = 60
const LONG = 'Comprobar que todo el panel se ve bien en el escritorio y en la terminal sin que nada se corte'
const CUT_WRAPS = ['truncate', 'truncate-end', 'end']

const barNow = async ($: any, paneId: string, surface: (typeof SURFACES)[number]) => {
  const ui = await mountPane($, paneId, surface)
  const tree = await ui.drawn()
  await ui.unmount()
  return { rows: rowsOf(tree), bar: progressOf(tree) }
}

test('should_draw_a_bar_of_one_segment_per_step_with_the_count_beside_it_under_the_task', async ($, on) => {
  const { opens } = await startSession($, on)
  await callPlan($, { task: ISSUE_TASK })

  for (const surface of SURFACES) {
    const { rows, bar } = await barNow($, opens[0]!.id, surface)

    expect([bar.done, bar.total], `0 of 3 steps done on ${surface}: ${JSON.stringify(rows)}`).toEqual([0, 3])
    expect(bar.segments, `one segment per step on ${surface}`).toHaveLength(3)
    expect(new Set(bar.segments).size, `every segment pending alike on ${surface}`).toBe(1)
    expect(bar.at, `the bar under the task row on ${surface}`).toBeGreaterThan(rowIndex(rows, ISSUE_TASK.title))
    expect(bar.at, `the bar above the first phase on ${surface}`).toBeLessThan(rowIndex(rows, ISSUE_TASK.phases[0].title))
    expect(bar.counters, `one count in the pane on ${surface}`).toBe(1)
  }
})

// D-160 marks the step in progress's segment apart (orange) from both pending and done.
// The count is the reference mod's position: done, plus one while a step runs (the GIF's 3/7).
test('should_fill_one_segment_per_done_step_and_count_the_step_in_progress_as_its_position', async ($, on) => {
  const { opens } = await startSession($, on)
  await callPlan($, { task: ISSUE_TASK })
  const fresh = (await barNow($, opens[0]!.id, 'desktop')).bar
  const pendingGlyph = fresh.segments[0]

  await callPlan($, { step: STEPS[0]!.id, status: 'in_progress' })
  const running = (await barNow($, opens[0]!.id, 'desktop')).bar
  await callPlan($, { step: STEPS[0]!.id, status: 'done' })
  const one = await barNow($, opens[0]!.id, 'desktop')
  for (const step of STEPS.slice(1)) await callPlan($, { step: step.id, status: 'done' })
  const all = (await barNow($, opens[0]!.id, 'desktop')).bar

  expect([running.done, running.total], 'the step in progress is the position: 1 of 3').toEqual([1, 3])
  expect(running.segments.slice(1), 'the rest stay pending').toEqual(fresh.segments.slice(1))
  expect([one.bar.done, one.bar.total], `1 of 3 after one step: ${JSON.stringify(one.rows)}`).toEqual([1, 3])
  expect(one.bar.segments[0], 'the done step fills its segment').not.toEqual(pendingGlyph)
  expect(one.bar.segments.slice(1), 'the other two stay pending').toEqual([pendingGlyph, pendingGlyph])
  expect([pendingGlyph, one.bar.segments[0]], 'the step in progress is marked as neither pending nor done').not.toContain(running.segments[0])
  expect([all.done, all.total], '3 of 3 when every step is done').toEqual([3, 3])
  expect(all.segments, 'every segment filled').toEqual([one.bar.segments[0], one.bar.segments[0], one.bar.segments[0]])
})

// The GIF frame: 2 done, 1 in progress, 4 to do reads 3/7 on both surfaces.
test('should_show_3_of_7_with_two_steps_done_and_one_in_progress_as_the_gif', async ($, on) => {
  const { opens } = await startSession($, on)
  const steps = Array.from({ length: 7 }, (_, i) => ({ id: String(i + 1), title: `Paso ${i + 1}` }))
  await callPlan($, { task: { title: 'Siete pasos', issue: null, steps } })
  await callPlan($, { step: '1', status: 'done' })
  await callPlan($, { step: '2', status: 'done' })
  await callPlan($, { step: '3', status: 'in_progress' })

  for (const surface of SURFACES) {
    const { rows, bar } = await barNow($, opens[0]!.id, surface)
    expect([bar.done, bar.total], `3/7 on ${surface}: ${JSON.stringify(rows)}`).toEqual([3, 7])
  }
})

// The reference adds one for any step in progress, never one per step in progress.
test('should_add_only_one_to_the_count_when_two_steps_are_in_progress', async ($, on) => {
  const { opens } = await startSession($, on)
  await callPlan($, { task: ISSUE_TASK })
  await callPlan($, { step: STEPS[0]!.id, status: 'done' })
  await callPlan($, { step: STEPS[1]!.id, status: 'in_progress' })
  await callPlan($, { step: STEPS[2]!.id, status: 'in_progress' })

  for (const surface of SURFACES) {
    const { rows, bar } = await barNow($, opens[0]!.id, surface)
    expect([bar.done, bar.total], `2/3, not 3/3, on ${surface}: ${JSON.stringify(rows)}`).toEqual([2, 3])
  }
})

test('should_count_the_steps_of_a_plain_task_with_no_phases', async ($, on) => {
  const { opens } = await startSession($, on)
  await callPlan($, { task: PLAIN })
  await callPlan($, { step: PLAIN.steps[0]!.id, status: 'done' })

  const { rows, bar } = await barNow($, opens[0]!.id, 'terminal')

  expect([bar.done, bar.total, bar.segments.length], `1 of 2: ${JSON.stringify(rows)}`).toEqual([1, 2, 2])
  expect(bar.at, 'under the request that heads the pane').toBeGreaterThan(rowIndex(rows, PLAIN.title))
  expect(bar.at, 'above the first step').toBeLessThan(rowIndex(rows, PLAIN.steps[0]!.title))
})

test('should_count_only_the_new_task_when_the_finished_one_folds', async ($, on) => {
  const { opens } = await startSession($, on)
  await callPlan($, { task: ISSUE_TASK })
  for (const step of STEPS) await callPlan($, { step: step.id, status: 'done' })

  await callPlan($, { task: { title: 'Publicar 1.51.1', issue: null, steps: [{ id: '1', title: 'Subir la version' }] } })

  const { rows, bar } = await barNow($, opens[0]!.id, 'desktop')
  expect([bar.done, bar.total, bar.segments.length], `the new task's 0 of 1: ${JSON.stringify(rows)}`).toEqual([0, 1, 1])
  expect(bar.counters, 'the folded task carries no bar').toBe(1)
})

test('should_draw_an_empty_circle_for_a_pending_step_and_a_marked_one_for_a_done_step', async ($, on) => {
  const { opens } = await startSession($, on)
  await callPlan($, { task: ISSUE_TASK })
  await callPlan($, { step: STEPS[0]!.id, status: 'done' })
  await callPlan($, { step: STEPS[1]!.id, status: 'in_progress' })

  for (const surface of SURFACES) {
    const { rows } = await barNow($, opens[0]!.id, surface)
    const markOfStep = (title: string) => markOf(rows[rowIndex(rows, title)])

    expect(DONE_MARKS, `the done step's circle on ${surface}: ${JSON.stringify(rows)}`).toContain(markOfStep(STEPS[0]!.title))
    expect(markOfStep(STEPS[2]!.title), `the pending step's empty circle on ${surface}`).toBe(PENDING)
    expect([PENDING, ...DONE_MARKS], `the step in progress is neither on ${surface}`).not.toContain(markOfStep(STEPS[1]!.title))
  }
})

test('should_cut_a_long_step_with_an_ellipsis_and_leave_a_short_one_whole', async ($, on) => {
  const { opens } = await startSession($, on)
  const task = { title: 'Revisar el panel', issue: null, steps: [{ id: '1', title: LONG }, { id: '2', title: 'Corto' }] }
  await callPlan($, { task })

  for (const surface of SURFACES) {
    const ui = await mountPane($, opens[0]!.id, surface)
    const rows = await drawnRows(ui)
    const holders = await ui.findAll({ type: 'Text', text: LONG.slice(0, 30) })
    await ui.unmount()
    const longRow = rows[rowIndex(rows, LONG.slice(0, 30))] ?? ''
    // The engine cuts a truncating Text at the pane's edge; a row the mod cuts itself fits and ends in one.
    const engineCuts = holders.some((held: any) => CUT_WRAPS.includes(String(held.props?.wrap)))
    const modCuts = longRow.endsWith('…') && [...longRow].length <= BODY_COLUMNS

    expect(engineCuts || modCuts, `the long step is cut with an ellipsis on ${surface}: ${JSON.stringify({ longRow, holders })}`).toBe(true)
    expect(rows[rowIndex(rows, 'Corto')], `the short step whole on ${surface}`).not.toMatch(/…$/)
  }
})
