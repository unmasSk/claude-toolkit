// #98 D-161: the right column shows how long a thing took, right-aligned: a done step its
// duration (start to tick), an agent under the step in progress its own. A long step title
// is cut, never the right column nor the ↻N round mark. Durations are written by hand.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import {
  ISSUE_TASK,
  SURFACES,
  callPlan,
  endAgent,
  leavesOf,
  mountPane,
  rounds,
  rowOf,
  rowsOf,
  spawnAgent,
  startSession,
} from './plan-kit.ts'

const [FIRST, SECOND] = ISSUE_TASK.phases[0].steps
const MINUTE = 60_000
const ULTRON = 'unmassk-toolkit:ultron'
const CERBERUS = 'unmassk-toolkit:cerberus'
const BODY_COLUMNS = 60
const CUT_WRAPS = ['truncate', 'truncate-end', 'end']
const DURATION = /\b\d+ (s|min)\b/g
const LONG = 'Comprobar que todo el panel se ve bien en el escritorio y en la terminal sin que nada se corte'

type Surface = (typeof SURFACES)[number]

const drawn = async ($: any, paneId: string, surface: Surface) => {
  const ui = await mountPane($, paneId, surface)
  const tree = await ui.drawn()
  await ui.unmount()
  return tree
}

const kidsOf = (node: any): any[] =>
  (Array.isArray(node?.children) ? node.children : [node?.children]).filter(
    (kid: any) => kid !== null && kid !== undefined && kid !== false && kid !== '',
  )

const textIn = (node: any) =>
  leavesOf(node)
    .map(leaf => (leaf.kind === 'text' ? leaf.text : ''))
    .join('')
    .trim()

// The row's last element when the layout pushes it to the right edge (a growing sibling
// before it, a space-between/flex-end row, or marginLeft auto); undefined otherwise.
const rightColumnOf = (row: any) => {
  let box = row
  while (box?.type === 'Box' && kidsOf(box).length === 1 && kidsOf(box)[0]?.type === 'Box') box = kidsOf(box)[0]
  if (box?.type !== 'Box' || String(box.props?.flexDirection ?? 'row').startsWith('column')) return undefined
  const kids = kidsOf(box)
  const last = kids.at(-1)
  if (typeof last !== 'object') return undefined
  const pushed =
    ['space-between', 'flex-end'].includes(box.props?.justifyContent) ||
    last.props?.marginLeft === 'auto' ||
    kids.slice(0, -1).some(kid => typeof kid === 'object' && Number(kid.props?.flexGrow) > 0)
  if (!pushed) return undefined
  const texts = leavesOf(last).filter(leaf => leaf.kind === 'text' && leaf.text.trim() !== '')
  return { text: textIn(last), dim: texts.length > 0 && texts.every(leaf => leaf.kind === 'text' && leaf.paint.dim) }
}

const durationsIn = (row: any) => (rowsOf(row)[0] ?? '').match(DURATION) ?? []

// 2.1 runs 16 min with ultron (2 min) under it until 2.2 starts, which then has cerberus (12 s).
const withStepDoneAndAgentsRunning = async ($: any, on: any) => {
  const session = await startSession($, on, new Date(2026, 9, 20, 14, 3).getTime())
  await callPlan($, { task: ISSUE_TASK })
  await callPlan($, { step: FIRST!.id, status: 'in_progress' })
  await session.clock.advance(16 * MINUTE)
  await callPlan($, { step: FIRST!.id, status: 'done' })
  await callPlan($, { step: SECOND!.id, status: 'in_progress' })
  await spawnAgent($, 'a1', ULTRON)
  await endAgent($, 'a1', 'GREEN — 12/12 tests pass', 2 * MINUTE)
  await spawnAgent($, 'a2', CERBERUS)
  await endAgent($, 'a2', 'CLEAN — merge', 12_000)
  await spawnAgent($, 'a3', 'unmassk-toolkit:argus')
  await session.clock.advance(5 * MINUTE)
  return session
}

for (const surface of SURFACES) {
  test(`should_right_align_each_agent_duration_like_a_done_step_duration_on_the_${surface}`, async ($, on) => {
    const { opens } = await withStepDoneAndAgentsRunning($, on)
    const tree = await drawn($, opens[0]!.id, surface)
    const ultron = rowOf(tree, /ultron/i).node
    const cerberus = rowOf(tree, /cerberus/i).node
    const step = rowOf(tree, FIRST!.title).node

    expect(rightColumnOf(step), `control: the done step's 16 min sits right-aligned, dim: ${JSON.stringify(step)}`).toEqual({ text: '16 min', dim: true })
    expect(rightColumnOf(ultron), `ultron's 2 min right-aligned, dim, alone: ${JSON.stringify(ultron)}`).toEqual({ text: '2 min', dim: true })
    expect(rightColumnOf(cerberus), `cerberus's 12 s right-aligned, dim, alone: ${JSON.stringify(cerberus)}`).toEqual({ text: '12 s', dim: true })
    expect([durationsIn(ultron), durationsIn(cerberus)], 'each duration drawn once, not also inline').toEqual([['2 min'], ['12 s']])
  })

  test(`should_show_no_duration_on_an_agent_still_running_on_the_${surface}`, async ($, on) => {
    const { opens } = await withStepDoneAndAgentsRunning($, on)
    const tree = await drawn($, opens[0]!.id, surface)
    const argus = rowOf(tree, /argus/i).node

    expect(rowsOf(argus)[0], `argus says running: ${JSON.stringify(argus)}`).toMatch(/running/)
    expect(durationsIn(argus), 'no duration while it runs').toEqual([])
  })

  test(`should_keep_the_round_mark_and_the_duration_whole_when_a_long_done_title_is_cut_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on)
    await callPlan($, { task: { title: 'Revisar el panel', issue: null, steps: [{ id: '1', title: LONG }, { id: '2', title: 'Corto' }] } })
    await callPlan($, { step: '1', status: 'in_progress' })
    for (const [id, type] of [['a1', ULTRON], ['a2', CERBERUS], ['a3', ULTRON]] as const) {
      await spawnAgent($, id, type)
      await endAgent($, id, 'GREEN — ok', MINUTE)
    }
    await clock.advance(16 * MINUTE)
    await callPlan($, { step: '1', status: 'done' })

    const tree = await drawn($, opens[0]!.id, surface)
    const row = rowOf(tree, LONG.slice(0, 20)).node
    const line = rowsOf(row)[0] ?? ''
    // Text runs outside any Text that the engine cuts at the edge.
    const uncut: string[] = []
    const walk = (node: any, isCut: boolean) => {
      if (typeof node === 'string' || typeof node === 'number') return void (isCut ? null : uncut.push(String(node)))
      if (node === null || typeof node !== 'object') return
      if (Array.isArray(node)) return node.forEach(kid => walk(kid, isCut))
      walk(node.children, isCut || (node.type === 'Text' && CUT_WRAPS.includes(String(node.props?.wrap))))
    }
    walk(row, false)
    const tail = uncut.join(' ')
    const keptByLayout = rounds(2).test(tail) && /\b16 min\b/.test(tail)
    const keptByOwnCut = [...line].length <= BODY_COLUMNS && rounds(2).test(line) && /\b16 min\b/.test(line)

    expect(keptByLayout || keptByOwnCut, `↻2 and 16 min stay visible on a long title: ${JSON.stringify({ line, tail })}`).toBe(true)
  })

  test(`should_keep_the_first_duration_when_a_done_step_is_ticked_again_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    await callPlan($, { step: FIRST!.id, status: 'in_progress' })
    await clock.advance(16 * MINUTE)
    await callPlan($, { step: FIRST!.id, status: 'done' })
    await clock.advance(9 * MINUTE)
    await callPlan($, { step: FIRST!.id, status: 'done' })

    const tree = await drawn($, opens[0]!.id, surface)
    expect(durationsIn(rowOf(tree, FIRST!.title).node), 'still 16 min, not 25').toEqual(['16 min'])
  })

  test(`should_drop_the_duration_of_a_reopened_step_and_show_a_new_one_when_ticked_again_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    await callPlan($, { step: FIRST!.id, status: 'in_progress' })
    await clock.advance(16 * MINUTE)
    await callPlan($, { step: FIRST!.id, status: 'done' })
    await clock.advance(5 * MINUTE)
    await callPlan($, { step: FIRST!.id, status: 'in_progress' })

    const reopened = durationsIn(rowOf(await drawn($, opens[0]!.id, surface), FIRST!.title).node)
    await clock.advance(3 * MINUTE)
    await callPlan($, { step: FIRST!.id, status: 'done' })
    const ticked = durationsIn(rowOf(await drawn($, opens[0]!.id, surface), FIRST!.title).node)

    expect(reopened, 'no duration while it is reopened').toEqual([])
    expect(ticked, 'one duration once ticked again').toHaveLength(1)
    expect(ticked, 'never the stale 16 min of the first tick').not.toEqual(['16 min'])
  })
}
