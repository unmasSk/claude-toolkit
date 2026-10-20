// #98 D-160: the pane in the colours of the Checklist mod's GIF. Done: a green disc
// with a tick, the label dim and its HH:MM at the row's end; in progress: an orange
// ring with a dot, the label bold; pending: a grey empty ring. The bar: green done,
// orange in progress, grey the rest, the count dim at its right. Agents (D-159, kept):
// amber for a fix round, red for an agent that failed or was interrupted.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import {
  AMBER,
  GREEN,
  GREY,
  ISSUE_TASK,
  ORANGE,
  RED,
  TICK_STROKE,
  COUNTER,
  callPlan,
  endAgent,
  leavesOf,
  markLeafOf,
  mountPane,
  paintAt,
  progressOf,
  rowNodesOf,
  rowOf,
  shapesOf,
  spawnAgent,
  startSession,
} from './plan-kit.ts'
import type { Leaf, Paint } from './plan-kit.ts'

const [DONE, RUNNING] = ISSUE_TASK.phases[0].steps
const PENDING_STEP = ISSUE_TASK.phases[1].steps[0]!
// The terminal reference draws its done mark in the named green.
const TERMINAL_GREENS = [GREEN, 'green']
// 14:03 on the person's clock; the HH:MM the test expects is written by hand below.
const START = new Date(2026, 9, 20, 14, 3).getTime()
const MINUTE = 60_000

const isGrey = (paint: Paint | undefined) => paint !== undefined && (paint.color === GREY || (paint.color === undefined && paint.dim))

const drawn = async ($: any, paneId: string, surface: 'terminal' | 'desktop') => {
  const ui = await mountPane($, paneId, surface)
  const tree = await ui.drawn()
  await ui.unmount()
  return tree
}

// 2.1 done at 14:05, 2.2 done at 14:06 in the time test; here 2.1 done, 2.2 in progress, 3.1 pending.
const withOneOfEach = async ($: any, on: any) => {
  const session = await startSession($, on, START)
  await callPlan($, { task: ISSUE_TASK })
  await callPlan($, { step: DONE!.id, status: 'done' })
  await callPlan($, { step: RUNNING!.id, status: 'in_progress' })
  return session
}

const iconOf = (tree: any, title: string) => {
  const mark = markLeafOf(rowOf(tree, title).leaves)
  return mark?.kind === 'svg' ? mark.props : undefined
}

const textLeaves = (leaves: Leaf[]) => leaves.filter((leaf): leaf is Extract<Leaf, { kind: 'text' }> => leaf.kind === 'text')

test('should_draw_a_done_step_on_the_desktop_as_a_14px_green_disc_with_a_dark_tick', async ($, on) => {
  const { opens } = await withOneOfEach($, on)
  const tree = await drawn($, opens[0]!.id, 'desktop')
  const icon = iconOf(tree, DONE!.title)

  expect(icon, `an Svg icon leads the done row: ${JSON.stringify(rowOf(tree, DONE!.title).leaves)}`).toBeDefined()
  expect([icon?.width, icon?.height], '14 by 14').toEqual([14, 14])
  const circles = shapesOf(String(icon?.source), 'circle')
  expect(circles.filter(c => c.fill === GREEN && c.r === '6.5'), `one green disc of radius 6.5: ${icon?.source}`).toHaveLength(1)
  expect(shapesOf(String(icon?.source), 'path').filter(p => p.stroke === TICK_STROKE), 'a tick in #1f1e1d').toHaveLength(1)
})

test('should_draw_the_step_in_progress_on_the_desktop_as_an_orange_ring_with_a_dot', async ($, on) => {
  const { opens } = await withOneOfEach($, on)
  const tree = await drawn($, opens[0]!.id, 'desktop')
  const icon = iconOf(tree, RUNNING!.title)

  expect(icon, `an Svg icon leads the running row: ${JSON.stringify(rowOf(tree, RUNNING!.title).leaves)}`).toBeDefined()
  expect([icon?.width, icon?.height], '14 by 14').toEqual([14, 14])
  const circles = shapesOf(String(icon?.source), 'circle')
  const ring = circles.filter(c => c.stroke === ORANGE && c.fill === 'none' && c.r === '5.7' && c['stroke-width'] === '1.6')
  const dot = circles.filter(c => c.fill === ORANGE && c.r === '2.6')
  expect([ring.length, dot.length], `an orange ring r5.7 stroke 1.6 and an orange dot r2.6: ${icon?.source}`).toEqual([1, 1])
  expect(String(icon?.source).toLowerCase(), 'no green in it').not.toContain(GREEN)
})

test('should_draw_a_pending_step_on_the_desktop_as_a_grey_empty_ring', async ($, on) => {
  const { opens } = await withOneOfEach($, on)
  const tree = await drawn($, opens[0]!.id, 'desktop')
  const icon = iconOf(tree, PENDING_STEP.title)

  expect(icon, `an Svg icon leads the pending row: ${JSON.stringify(rowOf(tree, PENDING_STEP.title).leaves)}`).toBeDefined()
  expect([icon?.width, icon?.height], '14 by 14').toEqual([14, 14])
  const circles = shapesOf(String(icon?.source), 'circle')
  expect(circles, `one grey ring r5.7 stroke 1.4, nothing filled: ${icon?.source}`).toEqual([
    expect.objectContaining({ stroke: GREY, fill: 'none', r: '5.7', 'stroke-width': '1.4' }),
  ])
})

for (const surface of ['terminal', 'desktop'] as const) {
  test(`should_draw_the_running_label_bold_and_the_done_label_dim_on_the_${surface}`, async ($, on) => {
    const { opens } = await withOneOfEach($, on)
    const tree = await drawn($, opens[0]!.id, surface)
    const labelOf = (title: string) => paintAt(rowOf(tree, title).leaves, title)

    expect(labelOf(RUNNING!.title), `the running label: ${JSON.stringify(rowOf(tree, RUNNING!.title).leaves)}`).toMatchObject({ bold: true, dim: false })
    expect(labelOf(DONE!.title), 'the done label').toMatchObject({ bold: false, dim: true })
    expect(labelOf(PENDING_STEP.title), 'the pending label').toMatchObject({ bold: false, dim: false })
  })

  test(`should_end_each_done_row_with_the_time_it_was_done_dim_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on, START)
    await callPlan($, { task: ISSUE_TASK })
    await clock.advance(2 * MINUTE)
    await callPlan($, { step: DONE!.id, status: 'done' })
    await clock.advance(1 * MINUTE)
    await callPlan($, { step: RUNNING!.id, status: 'done' })
    await callPlan($, { step: PENDING_STEP.id, status: 'in_progress' })
    await clock.advance(40 * MINUTE)

    const tree = await drawn($, opens[0]!.id, surface)
    const lastRun = (title: string) => textLeaves(rowOf(tree, title).leaves).filter(leaf => leaf.text.trim() !== '').at(-1)
    const first = lastRun(DONE!.title)
    const second = lastRun(RUNNING!.title)

    expect(first?.text.trim(), `2.1 done at 14:05, at the row's end: ${JSON.stringify(rowOf(tree, DONE!.title).leaves)}`).toMatch(/(^|\s)14:05$/)
    expect(second?.text.trim(), '2.2 done at 14:06, its own time, not the time drawn').toMatch(/(^|\s)14:06$/)
    expect([first?.paint.dim, second?.paint.dim], 'the times dim').toEqual([true, true])
    expect(rowOf(tree, PENDING_STEP.title).leaves.some(leaf => leaf.kind === 'text' && /\b\d{2}:\d{2}\b/.test(leaf.text)), 'no time on the step in progress').toBe(false)
  })
}

test('should_draw_the_bar_on_the_desktop_as_one_14x4_rounded_rect_per_step_green_orange_grey', async ($, on) => {
  const { opens } = await withOneOfEach($, on)
  const tree = await drawn($, opens[0]!.id, 'desktop')
  const nodes = rowNodesOf(tree)
  const bar = nodes[progressOf(tree).at]
  const leaves = bar === undefined ? [] : leavesOf(bar)
  const svg = leaves.find(leaf => leaf.kind === 'svg')
  const rects = shapesOf(String(svg?.kind === 'svg' ? svg.props.source : ''), 'rect')

  expect(rects.map(r => r.fill), `green, orange, grey: ${JSON.stringify(leaves)}`).toEqual([GREEN, ORANGE, GREY])
  expect(rects.map(r => [r.width, r.height, r.rx]), '14 wide, 4 high, rounded 2').toEqual([['14', '4', '2'], ['14', '4', '2'], ['14', '4', '2']])
  expect(rects.map(r => Number(r.x)), 'a gap of 4 between segments').toEqual([0, 18, 36])
  const counter = leaves.findIndex(leaf => leaf.kind === 'text' && COUNTER.test(leaf.text))
  expect(counter, 'the count right of the bar').toBeGreaterThan(leaves.indexOf(svg!))
  expect(paintAt(leaves, COUNTER)?.dim, 'the count dim').toBe(true)
})

const desktopBar = async ($: any, on: any, count: number, statuses: Record<string, 'in_progress' | 'done'>) => {
  const { opens } = await startSession($, on, START)
  const steps = Array.from({ length: count }, (_, i) => ({ id: String(i + 1), title: `Paso ${i + 1}` }))
  await callPlan($, { task: { title: 'Muchos pasos', issue: null, steps } })
  for (const [step, status] of Object.entries(statuses)) await callPlan($, { step, status })
  const tree = await drawn($, opens[0]!.id, 'desktop')
  const progress = progressOf(tree)
  const bar = rowNodesOf(tree)[progress.at]
  const svg = (bar === undefined ? [] : leavesOf(bar)).find(leaf => leaf.kind === 'svg')
  const props = svg?.kind === 'svg' ? svg.props : {}
  return { progress, svg: props, rects: shapesOf(String(props.source ?? ''), 'rect') }
}

// The reference pills(): past 12 steps, 12 segments 8 wide for the first 12 steps; the count keeps every step.
test('should_draw_12_segments_8_wide_for_the_first_12_steps_past_12_steps', async ($, on) => {
  // 14 steps: 1 done, 2 in progress, 13 done (beyond the 12 drawn), the rest to do.
  const { progress, svg, rects } = await desktopBar($, on, 14, { '1': 'done', '2': 'in_progress', '13': 'done' })

  expect(rects.map(r => r.fill), `12 segments, the first 12 steps: ${JSON.stringify(svg)}`).toEqual([GREEN, ORANGE, ...Array(10).fill(GREY)])
  expect([...new Set(rects.map(r => r.width))], 'every segment 8 wide').toEqual(['8'])
  expect(rects.map(r => Number(r.x)), 'a gap of 4: x = 12 per segment').toEqual(Array.from({ length: 12 }, (_, i) => i * 12))
  // 12 * 8 + 11 * 4 = 140, by hand.
  expect(Number(svg.width), 'the bar 140 wide').toBe(140)
  expect([progress.done, progress.total], 'the count of all 14 steps: 2 done, one running').toEqual([3, 14])
})

test('should_keep_one_14_wide_segment_per_step_at_exactly_12_steps', async ($, on) => {
  const { svg, rects } = await desktopBar($, on, 12, { '12': 'done' })

  expect(rects.map(r => r.fill), `12 segments, the last done: ${JSON.stringify(svg)}`).toEqual([...Array(11).fill(GREY), GREEN])
  expect([...new Set(rects.map(r => r.width))], 'every segment 14 wide').toEqual(['14'])
  // 12 * 14 + 11 * 4 = 212, by hand.
  expect(Number(svg.width), 'the bar 212 wide').toBe(212)
})

test('should_paint_the_terminal_circles_green_done_orange_in_progress_grey_pending', async ($, on) => {
  const { opens } = await withOneOfEach($, on)
  const tree = await drawn($, opens[0]!.id, 'terminal')
  const markPaint = (title: string) => {
    const mark = markLeafOf(rowOf(tree, title).leaves)
    return mark?.kind === 'text' ? mark.paint : undefined
  }

  expect(TERMINAL_GREENS, `the done mark green: ${JSON.stringify(rowOf(tree, DONE!.title).leaves)}`).toContain(markPaint(DONE!.title)?.color)
  expect(markPaint(RUNNING!.title)?.color, 'the running mark orange').toBe(ORANGE)
  expect(isGrey(markPaint(PENDING_STEP.title)), `the pending mark grey: ${JSON.stringify(markPaint(PENDING_STEP.title))}`).toBe(true)
})

test('should_paint_the_terminal_bar_green_done_orange_in_progress_grey_pending', async ($, on) => {
  const { opens } = await withOneOfEach($, on)
  const tree = await drawn($, opens[0]!.id, 'terminal')
  const bar = rowNodesOf(tree)[progressOf(tree).at]
  const glyphPaints = textLeaves(bar === undefined ? [] : leavesOf(bar)).flatMap(leaf =>
    [...leaf.text.replace(/\d+\/\d+/g, '').replace(/\s/g, '')].map(() => leaf.paint),
  )

  expect(glyphPaints, `three segments: ${JSON.stringify(leavesOf(bar))}`).toHaveLength(3)
  expect(TERMINAL_GREENS, 'the done segment green').toContain(glyphPaints[0]?.color)
  expect(glyphPaints[1]?.color, 'the running segment orange').toBe(ORANGE)
  expect(isGrey(glyphPaints[2]), 'the pending segment grey').toBe(true)
})

const STOPPED = [
  { id: 'a2', name: 'cerberus', end: { reason: 'aborted', isAborted: true }, says: 'interrupted' },
  { id: 'a3', name: 'argus', end: { reason: 'error', isAborted: false }, says: 'failed' },
] as const

for (const surface of ['terminal', 'desktop'] as const) {
  test(`should_paint_a_fix_round_amber_on_the_${surface}`, async ($, on) => {
    const { opens } = await startSession($, on, START)
    await callPlan($, { task: ISSUE_TASK })
    await callPlan($, { step: DONE!.id, status: 'in_progress' })
    await spawnAgent($, 'a1', 'unmassk-toolkit:ultron')
    await endAgent($, 'a1', 'GREEN — built', MINUTE)
    await spawnAgent($, 'a2', 'unmassk-toolkit:ultron')

    const tree = await drawn($, opens[0]!.id, surface)
    const rounds = /↻\s?2/
    const holder = rowNodesOf(tree).map(node => leavesOf(node)).find(leaves => paintAt(leaves, rounds) !== undefined)

    expect(paintAt(holder ?? [], rounds)?.color, `the round mark amber: ${JSON.stringify(holder)}`).toBe(AMBER)
  })

  test(`should_paint_an_interrupted_or_failed_agent_red_and_a_clean_one_neither_red_nor_amber_on_the_${surface}`, async ($, on) => {
    const { opens } = await startSession($, on, START)
    await callPlan($, { task: ISSUE_TASK })
    await callPlan($, { step: DONE!.id, status: 'in_progress' })
    await spawnAgent($, 'a1', 'unmassk-toolkit:ultron')
    for (const agent of STOPPED) await spawnAgent($, agent.id, `unmassk-toolkit:${agent.name}`)
    await endAgent($, 'a1', 'GREEN — built', MINUTE)
    for (const agent of STOPPED) {
      await $.turn.complete({ agentId: agent.id, answer: 'partial', durationMs: 12_000, turnId: `t-${agent.id}`, ...agent.end })
    }

    const tree = await drawn($, opens[0]!.id, surface)
    const resultPaint = (name: string, says: string) => paintAt(rowOf(tree, name).leaves, says)

    expect(
      STOPPED.map(agent => resultPaint(agent.name, agent.says)?.color),
      `interrupted and failed in red: ${JSON.stringify(STOPPED.map(agent => rowOf(tree, agent.name).leaves))}`,
    ).toEqual([RED, RED])
    expect([AMBER, RED], 'the clean answer neither').not.toContain(resultPaint('ultron', 'GREEN — built')?.color)
  })
}
