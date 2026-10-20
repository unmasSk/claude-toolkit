// #98 D-161: the right column shows how long a thing took, right-aligned: a done step its
// duration (start to tick), an agent under the step in progress its own. A long step title
// is cut, never the right column nor the ↻N round mark. Durations are written by hand.
// D-162: the step in progress and every running agent show, right-aligned, the time so far,
// ticking each second on the mod's clock with the pane left mounted; on ending it freezes.
// Format, running and frozen alike: under a minute `45s`, under an hour `12m 05s`, from an hour `1h 12m`.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import {
  DURATION,
  ISSUE_TASK,
  SURFACES,
  callPlan,
  drawn,
  endAgent,
  mountPane,
  rightColumnOf,
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
const LONG = 'Comprobar que todo el panel se ve bien en el escritorio y en la terminal sin que nada se corte'

const aligned = (row: any) => {
  const right = rightColumnOf(row)
  return right === undefined ? undefined : { text: right.text, dim: right.dim }
}

const durationsIn = (row: any) => (rowsOf(row)[0] ?? '').match(DURATION) ?? []

// The right column of the row holding `text` in a pane that stays mounted: a value that
// changes between two reads proves the pane redrew on its own, with no state change.
const rightTextOf = async (ui: any, text: string | RegExp) => {
  const row = rowOf(await ui.drawn(), text).node
  return { right: rightColumnOf(row)?.text, row: JSON.stringify(row) }
}

// 2.1 runs 16m 00s with ultron (2m 00s) under it until 2.2 starts, which then has cerberus (12s).
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

    // The done step's time takes its label's grey (plan-colours); an agent's stays dim like its line.
    expect(rightColumnOf(step)?.text, `control: the done step's 16m 00s sits right-aligned: ${JSON.stringify(step)}`).toBe('16m 00s')
    expect(aligned(ultron), `ultron's 2m 00s right-aligned, dim, alone: ${JSON.stringify(ultron)}`).toEqual({ text: '2m 00s', dim: true })
    expect(aligned(cerberus), `cerberus's 12s right-aligned, dim, alone: ${JSON.stringify(cerberus)}`).toEqual({ text: '12s', dim: true })
    expect([durationsIn(ultron), durationsIn(cerberus)], 'each duration drawn once, not also inline').toEqual([['2m 00s'], ['12s']])
  })

  test(`should_show_the_running_agent_time_so_far_right_aligned_on_the_${surface}`, async ($, on) => {
    const { opens } = await withStepDoneAndAgentsRunning($, on)
    const tree = await drawn($, opens[0]!.id, surface)
    const argus = rowOf(tree, /argus/i).node

    // argus was spawned, then 5m 00s passed on the mod's clock.
    expect(rowsOf(argus)[0], `argus says running: ${JSON.stringify(argus)}`).toMatch(/running/)
    expect(rightColumnOf(argus)?.text, `argus's 5m 00s so far, right-aligned: ${JSON.stringify(argus)}`).toBe('5m 00s')
    expect(durationsIn(argus), 'drawn once, not also inline').toEqual(['5m 00s'])
  })

  test(`should_tick_the_step_in_progress_each_second_and_redraw_the_mounted_pane_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    await callPlan($, { step: FIRST!.id, status: 'in_progress' })
    const ui = await mountPane($, opens[0]!.id, surface)
    const seen: (string | undefined)[] = []
    let last = ''
    try {
      for (const ms of [5_000, 1_000, 1_000, 1_000]) {
        await clock.advance(ms)
        const { right, row } = await rightTextOf(ui, FIRST!.title)
        seen.push(right)
        last = row
      }
    } finally {
      await ui.unmount()
    }

    expect(seen, `5s, then one more each second, with no call in between: ${last}`).toEqual(['5s', '6s', '7s', '8s'])
  })

  test(`should_tick_a_running_agent_each_second_and_redraw_the_mounted_pane_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    await callPlan($, { step: FIRST!.id, status: 'in_progress' })
    await clock.advance(30_000)
    await spawnAgent($, 'a1', ULTRON)
    const ui = await mountPane($, opens[0]!.id, surface)
    const seen: (string | undefined)[] = []
    let last = ''
    try {
      for (const ms of [7_000, 1_000, 1_000]) {
        await clock.advance(ms)
        const { right, row } = await rightTextOf(ui, /ultron/i)
        seen.push(right)
        last = row
      }
    } finally {
      await ui.unmount()
    }

    expect(seen, `from its own spawn, not the step's start: 7s, 8s, 9s: ${last}`).toEqual(['7s', '8s', '9s'])
  })

  test(`should_freeze_the_time_of_a_step_and_an_agent_once_they_end_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    await callPlan($, { step: FIRST!.id, status: 'in_progress' })
    await spawnAgent($, 'a1', ULTRON)
    const ui = await mountPane($, opens[0]!.id, surface)
    const right = async (text: string | RegExp) => (await rightTextOf(ui, text)).right
    const seen: Record<string, string | undefined> = {}
    try {
      await clock.advance(3_000)
      await endAgent($, 'a1', 'GREEN — ok', 3_000)
      seen.agentEnded = await right(/ultron/i)
      await clock.advance(3_000)
      // Read while the step still runs: agents leave the pane once their step is done.
      seen.agentLater = await right(/ultron/i)
      await callPlan($, { step: FIRST!.id, status: 'done' })
      seen.stepEnded = await right(FIRST!.title)
      await clock.advance(4_000)
      seen.stepLater = await right(FIRST!.title)
    } finally {
      await ui.unmount()
    }

    expect(seen, 'the agent stays at the 3s it took, the step at its 6s').toEqual({ agentEnded: '3s', agentLater: '3s', stepEnded: '6s', stepLater: '6s' })
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
    const keptByLayout = rounds(2).test(tail) && /\b16m 00s\b/.test(tail)
    const keptByOwnCut = [...line].length <= BODY_COLUMNS && rounds(2).test(line) && /\b16m 00s\b/.test(line)

    expect(keptByLayout || keptByOwnCut, `↻2 and 16m 00s stay visible on a long title: ${JSON.stringify({ line, tail })}`).toBe(true)
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
    expect(durationsIn(rowOf(tree, FIRST!.title).node), 'still 16m 00s, not 25m 00s').toEqual(['16m 00s'])
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

    expect(reopened, 'one live time while it is reopened (D-162)').toHaveLength(1)
    expect(ticked, 'one duration once ticked again').toHaveLength(1)
    expect(ticked, 'never the stale 16m 00s of the first tick').not.toEqual(['16m 00s'])
  })

  test(`should_tick_the_seconds_above_one_minute_on_the_${surface}`, async ($, on) => {
    const { opens, clock } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    await callPlan($, { step: FIRST!.id, status: 'in_progress' })
    const ui = await mountPane($, opens[0]!.id, surface)
    const seen: (string | undefined)[] = []
    let last = ''
    try {
      for (const ms of [65_000, 1_000, 1_000]) {
        await clock.advance(ms)
        const { right, row } = await rightTextOf(ui, FIRST!.title)
        seen.push(right)
        last = row
      }
    } finally {
      await ui.unmount()
    }

    expect(seen, `past a minute the seconds still tick, two digits: ${last}`).toEqual(['1m 05s', '1m 06s', '1m 07s'])
  })

  // One per band: the same text while the step runs and once it is ticked done.
  for (const band of [
    { name: 'seconds_under_a_minute', ms: 45_000, text: '45s' },
    { name: 'minutes_and_two_digit_seconds_under_an_hour', ms: 12 * MINUTE + 5_000, text: '12m 05s' },
    { name: 'hours_and_minutes_from_an_hour', ms: 72 * MINUTE, text: '1h 12m' },
  ]) {
    test(`should_show_${band.name}_the_same_running_and_frozen_on_the_${surface}`, async ($, on) => {
      const { opens, clock } = await startSession($, on)
      await callPlan($, { task: ISSUE_TASK })
      await callPlan($, { step: FIRST!.id, status: 'in_progress' })
      const ui = await mountPane($, opens[0]!.id, surface)
      const seen: Record<string, string | undefined> = {}
      let last = ''
      try {
        await clock.advance(band.ms)
        seen.running = (await rightTextOf(ui, FIRST!.title)).right
        await callPlan($, { step: FIRST!.id, status: 'done' })
        const frozen = await rightTextOf(ui, FIRST!.title)
        seen.frozen = frozen.right
        last = frozen.row
      } finally {
        await ui.unmount()
      }

      expect(seen, `${band.text} while running and once done: ${last}`).toEqual({ running: band.text, frozen: band.text })
    })
  }
}
