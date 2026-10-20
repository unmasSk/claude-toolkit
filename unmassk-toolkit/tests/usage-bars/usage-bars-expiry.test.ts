// D-166 (expire): a window whose resetsAt has passed is drawn at 0 %; one still running keeps its percent.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import { HOUR, MINUTE, SESSION, START, SURFACES, WEEK, drawnBand, fiveHour, measure, sevenDay, startSession, windowOf } from './usage-kit.ts'

test('should_draw_a_window_whose_reset_has_passed_at_zero_and_keep_the_other', async ($, on) => {
  const world = await startSession($, on)
  // The reading came at 10:00; the session window reset at 9:30 and the engine has not measured since.
  await measure($, world, [fiveHour(88, START - 30 * MINUTE), sevenDay(62)])

  for (const surface of SURFACES) {
    const tree = await drawnBand($, surface)
    expect([windowOf(tree, SESSION).percent, windowOf(tree, WEEK).percent], `on ${surface}`).toEqual([0, 62])
  }
})

test('should_draw_zero_once_the_clock_passes_the_reset_of_a_reading_taken_before_it', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [fiveHour(88, START + HOUR), sevenDay(62, START + 2 * 24 * HOUR)])

  for (const surface of SURFACES) {
    expect(windowOf(await drawnBand($, surface), SESSION).percent, `before the reset on ${surface}`).toBe(88)
  }

  // Past the session's reset, before the week's; the person drew no new reading.
  await world.clock.advance(HOUR + MINUTE)

  for (const surface of SURFACES) {
    const tree = await drawnBand($, surface)
    expect([windowOf(tree, SESSION).percent, windowOf(tree, WEEK).percent], `after the reset on ${surface}`).toEqual([0, 62])
  }
})

test('should_empty_the_terminal_bar_of_a_window_whose_reset_has_passed', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [fiveHour(88, START - MINUTE), sevenDay(40)])
  const tree = await drawnBand($, 'terminal')
  const session = windowOf(tree, SESSION)
  const week = windowOf(tree, WEEK)
  // The week at 40 %: its last cell is an empty one; every cell of the expired session must look like it.
  const empty = week.cells.at(-1)

  expect(session.cells.length, 'the session keeps its bar').toBeGreaterThanOrEqual(5)
  expect(session.cells.filter(cell => cell !== empty), `no filled cell: ${session.cells.join(' | ')}`).toEqual([])
})

test('should_empty_the_desktop_bar_of_a_window_whose_reset_has_passed', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [fiveHour(88, START - MINUTE), sevenDay(40)])
  const session = windowOf(await drawnBand($, 'desktop'), SESSION)

  expect(session.svgs, 'the session keeps its Svg bar').toBe(1)
  expect(session.fill, 'an empty bar').toBeLessThanOrEqual(0.01)
})
