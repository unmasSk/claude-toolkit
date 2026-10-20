// #98: the task's title row ends, right-aligned, with the task's total time so far: from the
// task's start, live while the task runs (each second, like the running step, between steps
// too), frozen once every step is done at the same total the folded line shows (D-153).
// Bex, 2026-10-20: «a la derecha debería de haber el sumatorio de todo». Times written by hand.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import { DURATION, ISSUE_TASK, SURFACES, callPlan, drawn, mountPane, rightColumnOf, rowOf, rowsOf, startSession } from './plan-kit.ts'

const STEP_IDS = ISSUE_TASK.phases.flatMap(phase => phase.steps.map(step => step.id))
const [FIRST, SECOND] = ISSUE_TASK.phases[0].steps
const MINUTE = 60_000
const CUT_WRAPS = ['truncate', 'truncate-end', 'end']

const titleRowOf = (tree: any) => rowOf(tree, ISSUE_TASK.title).node

const totalOf = (tree: any) => rightColumnOf(titleRowOf(tree))?.text

// Whether a Text that the engine cuts at the edge holds the node.
const isCut = (node: any, inCut = false): boolean => {
  if (node === null || typeof node !== 'object') return inCut
  if (Array.isArray(node)) return node.some(kid => isCut(kid, inCut))
  const cuts = inCut || (node.type === 'Text' && CUT_WRAPS.includes(String(node.props?.wrap)))
  const kids = Array.isArray(node.children) ? node.children : [node.children]
  return kids.some((kid: any) => (typeof kid === 'string' || typeof kid === 'number' ? cuts : isCut(kid, cuts)))
}

const finishTask = async ($: any) => {
  for (const id of STEP_IDS) {
    await callPlan($, { step: id, status: 'in_progress' })
    await callPlan($, { step: id, status: 'done' })
  }
}

for (const surface of SURFACES) {
  test(`should_end_the_title_row_with_the_task_total_since_its_start_right_aligned_and_uncut_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    await clock.advance(2 * MINUTE)
    await callPlan($, { step: FIRST!.id, status: 'in_progress' })
    await clock.advance(3 * MINUTE)

    const tree = await drawn($, opens[0]!.id, surface)
    const title = titleRowOf(tree)
    const right = rightColumnOf(title)

    // The task started 5m 00s ago; its running step only 3m 00s ago.
    expect(right?.text, `the title row's right column: ${JSON.stringify(title)}`).toBe('5m 00s')
    expect(rightColumnOf(rowOf(tree, FIRST!.title).node)?.text, 'control: the step counts from its own start').toBe('3m 00s')
    expect(isCut(right?.node), 'the total sits outside the Text that cuts the title').toBe(false)
    expect((rowsOf(title)[0] ?? '').match(DURATION), 'the total drawn once on the title row').toEqual(['5m 00s'])
  })

  test(`should_tick_the_task_total_each_second_and_redraw_the_mounted_pane_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    await clock.advance(2 * MINUTE)
    await callPlan($, { step: FIRST!.id, status: 'in_progress' })
    await clock.advance(3 * MINUTE)
    const ui = await mountPane($, opens[0]!.id, surface)
    const seen: (string | undefined)[] = []
    let last = ''
    try {
      for (const ms of [1_000, 1_000, 1_000]) {
        await clock.advance(ms)
        const tree = await ui.drawn()
        seen.push(totalOf(tree))
        last = JSON.stringify(titleRowOf(tree))
      }
    } finally {
      await ui.unmount()
    }

    expect(seen, `one more second each tick, with no call in between: ${last}`).toEqual(['5m 01s', '5m 02s', '5m 03s'])
  })

  // The task still runs with no step in progress: one ticked, the next not yet started.
  test(`should_keep_counting_the_task_total_between_steps_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    await callPlan($, { step: FIRST!.id, status: 'in_progress' })
    await clock.advance(4 * MINUTE)
    await callPlan($, { step: FIRST!.id, status: 'done' })
    await clock.advance(2 * MINUTE)
    const ui = await mountPane($, opens[0]!.id, surface)
    const seen: (string | undefined)[] = []
    let last = ''
    try {
      for (const ms of [0, 1_000]) {
        await clock.advance(ms)
        const tree = await ui.drawn()
        seen.push(totalOf(tree))
        last = JSON.stringify(titleRowOf(tree))
      }
    } finally {
      await ui.unmount()
    }

    expect(seen, `6m 00s since the task started, still ticking: ${last}`).toEqual(['6m 00s', '6m 01s'])
  })

  test(`should_freeze_the_task_total_once_every_step_is_done_at_the_total_the_folded_line_shows_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    await clock.advance(25 * MINUTE)
    await finishTask($)
    await clock.advance(10 * MINUTE)

    const finished = await drawn($, opens[0]!.id, surface)
    const title = titleRowOf(finished)
    await callPlan($, { task: { title: 'Publicar 1.51.1', issue: null, steps: [{ id: '1', title: 'Subir la version' }] } })
    const folded = rowOf(await drawn($, opens[0]!.id, surface), ISSUE_TASK.title).node

    expect(rightColumnOf(title)?.text, `25m 00s, not the 35m 00s since the start: ${JSON.stringify(title)}`).toBe('25m 00s')
    expect((rowsOf(title)[0] ?? '').match(DURATION), 'drawn once, not also inline').toEqual(['25m 00s'])
    expect((rowsOf(folded)[0] ?? '').match(DURATION), 'the folded line shows the same total').toEqual(['25m 00s'])
  })

  test(`should_count_the_task_total_again_from_the_task_start_when_a_finished_task_reopens_a_step_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    await clock.advance(25 * MINUTE)
    await finishTask($)
    await clock.advance(5 * MINUTE)
    await callPlan($, { step: SECOND!.id, status: 'in_progress' })

    const tree = await drawn($, opens[0]!.id, surface)
    expect(totalOf(tree), `live again: 30m 00s since the task started, not the frozen 25m 00s: ${JSON.stringify(titleRowOf(tree))}`).toBe('30m 00s')
  })
}
