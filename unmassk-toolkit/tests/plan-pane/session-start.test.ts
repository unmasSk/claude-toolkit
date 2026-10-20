// #98 phase 1: the plan-pane hooks module registers and opens its pane on session.start.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'

const PLUGIN = 'unmassk-toolkit'
const START = { cwd: '/work/project', surface: 'desktop', isInteractive: true } as const
const PANE_ID = /^[A-Za-z0-9_-]{1,64}$/

type Open = { id: string; title?: string; focus?: true; closeOnEscape?: true; holdToasts?: true }

const paneProps = (title: string) => ({
  title,
  isFocused: false,
  bodyColumns: 40,
  placement: 'dock' as const,
  scroll: { offset: 0, bodyRows: 20 },
  view: {},
})

// The test's hooks sit beneath the plugin: they record what the module asks of the engine.
const startSession = async ($: any, on: any) => {
  const opens: Open[] = []
  const handedOn: unknown[] = []
  on('ui.open', async (_$: unknown, e: Open) => {
    opens.push(e)
    return { value: { isPlaced: true } }
  })
  on('session.start', async (_$: unknown, e: { cwd: string }) => {
    handedOn.push(e)
    return { cwd: e.cwd }
  })
  const result = await $.session.start(START)
  return { opens, handedOn, result }
}

test('should_open_exactly_one_pane_when_the_session_starts', async ($, on) => {
  const { opens } = await startSession($, on)

  expect(opens.length, 'panes opened on session.start').toBe(1)
  expect(opens[0]?.id).toMatch(PANE_ID)
})

test('should_draw_the_pane_it_opened_on_desktop_and_terminal', async ($, on) => {
  const { opens } = await startSession($, on)
  const opened = opens[0]
  expect(opened, 'a pane opened on session.start').toBeDefined()

  for (const surface of ['desktop', 'terminal'] as const) {
    const ui = await $.ui.mount({
      plugin: PLUGIN,
      surface,
      component: 'Pane',
      requestId: opened!.id,
      props: paneProps(opened!.title ?? opened!.id),
    })
    expect((await ui.findAll({})).length, `elements drawn on ${surface}`).toBeGreaterThan(0)
    await ui.unmount()
  }
})

test('should_open_a_pane_that_stays_not_a_dialog', async ($, on) => {
  const { opens } = await startSession($, on)
  const opened = opens[0]
  expect(opened, 'a pane opened on session.start').toBeDefined()

  // D-149/D-153: the plan stays in view; Escape must not close it and it must not hold every toast.
  expect(opened!.closeOnEscape).toBeUndefined()
  expect(opened!.holdToasts).toBeUndefined()
})

test('should_hand_session_start_on_to_the_rest_of_the_chain', async ($, on) => {
  const { handedOn, result } = await startSession($, on)

  expect(handedOn).toEqual([START])
  expect(result).toEqual({ cwd: START.cwd })
})
