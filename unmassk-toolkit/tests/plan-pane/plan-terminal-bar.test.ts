// #98 terminal bar (Cerberus F2, F5): capped at the first 12 steps like the desktop's pills,
// so a long plan never wraps the count off its row; one space before the count.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import { COUNTER, ORANGE, callPlan, leavesOf, mountPane, progressOf, rowNodesOf, rowsOf, startSession } from './plan-kit.ts'

const terminalTree = async ($: any, on: any, count: number, statuses: Record<string, 'in_progress' | 'done'>) => {
  const { opens } = await startSession($, on)
  const steps = Array.from({ length: count }, (_, i) => ({ id: String(i + 1), title: `Paso ${i + 1}` }))
  await callPlan($, { task: { title: 'Muchos pasos', issue: null, steps } })
  for (const [step, status] of Object.entries(statuses)) await callPlan($, { step, status })
  const ui = await mountPane($, opens[0]!.id, 'terminal')
  const tree = await ui.drawn()
  await ui.unmount()
  return tree
}

test('should_draw_only_the_first_12_steps_in_the_terminal_bar_past_12_with_the_count_on_its_row', async ($, on) => {
  // 20 steps: 1 done, 2 in progress, 13 done (beyond the 12 drawn), the rest to do.
  const tree = await terminalTree($, on, 20, { '1': 'done', '2': 'in_progress', '13': 'done' })
  const progress = progressOf(tree)
  const rows = rowsOf(tree)
  const bar = rowNodesOf(tree)[progress.at]
  const paints = (bar === undefined ? [] : leavesOf(bar)).flatMap(leaf =>
    leaf.kind === 'text' ? [...leaf.text.replace(/\d+\/\d+/g, '').replace(/\s/g, '')].map(() => leaf.paint.color) : [],
  )

  expect(progress.segments, `12 segments, not 20: ${JSON.stringify(rows)}`).toHaveLength(12)
  expect(paints[1], 'the second segment is step 2, in progress: the first 12, not the last').toBe(ORANGE)
  expect(COUNTER.test(rows[progress.at] ?? ''), 'the count on the bar row').toBe(true)
  expect([progress.done, progress.total], 'the count keeps all 20 steps').toEqual([3, 20])
})

test('should_keep_one_segment_per_step_in_the_terminal_bar_at_exactly_12_steps', async ($, on) => {
  const tree = await terminalTree($, on, 12, { '12': 'done' })

  expect(progressOf(tree).segments, '12 steps, 12 segments').toHaveLength(12)
})

test('should_put_a_single_space_before_the_terminal_count', async ($, on) => {
  const tree = await terminalTree($, on, 3, { '1': 'done' })
  const progress = progressOf(tree)
  const row = rowsOf(tree)[progress.at] ?? ''

  expect(row, `one space between the last segment and 1/3: ${JSON.stringify(row)}`).toMatch(/\S \d+\/\d+\s*$/)
})
