// D-166: the band follows session.measure: each reading redraws the band already on screen;
// a measure with no rate-limit reading (before the first response) never wipes what it shows.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import { SESSION, SURFACES, WEEK, bandText, drawnBand, fiveHour, measure, mountBand, sevenDay, startSession, windowOf } from './usage-kit.ts'

const percents = (tree: any) => [windowOf(tree, SESSION).percent, windowOf(tree, WEEK).percent]

test('should_redraw_the_band_on_screen_with_the_new_percents_after_a_measure', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [fiveHour(20), sevenDay(40)])

  for (const surface of SURFACES) {
    const ui = await mountBand($, surface)
    expect(percents(await ui.drawn()), `the first reading on ${surface}`).toEqual([20, 40])

    await measure($, world, [fiveHour(55), sevenDay(41)])

    // The same band, never mounted again: the measure alone must bring the new figures.
    expect(percents(await ui.drawn()), `after the measure on ${surface}`).toEqual([55, 41])
    await ui.unmount()
    await measure($, world, [fiveHour(20), sevenDay(40)])
  }
})

test('should_keep_the_last_percents_when_a_measure_carries_no_rate_limits', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [fiveHour(33), sevenDay(66)])
  await measure($, world, [])

  for (const surface of SURFACES) {
    expect(percents(await drawnBand($, surface)), `an empty reading changes nothing on ${surface}`).toEqual([33, 66])
  }
})

test('should_draw_nothing_before_any_reading_with_nothing_stored_then_draw_the_first_reading', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [])

  for (const surface of SURFACES) {
    expect(bandText(await drawnBand($, surface)).trim(), `an empty band on ${surface}`).toBe('')
  }

  await measure($, world, [fiveHour(12), sevenDay(48)])

  for (const surface of SURFACES) {
    expect(percents(await drawnBand($, surface)), `the first reading drawn on ${surface}`).toEqual([12, 48])
  }
})

test('should_still_update_the_band_when_the_store_refuses_the_write', async ($, on) => {
  const world = await startSession($, on)
  world.isStoreRefusing = true
  await measure($, world, [fiveHour(27), sevenDay(54)])

  for (const surface of SURFACES) {
    expect(percents(await drawnBand($, surface)), `the live reading on ${surface}, stored or not`).toEqual([27, 54])
  }
})

test('should_hand_session_measure_on_to_the_rest_of_the_chain', async ($, on) => {
  const world = await startSession($, on)

  // The bottom echoes `changed`: a hook answering for itself would hide every other plugin.
  expect(await measure($, world, [fiveHour(10), sevenDay(20)])).toEqual({ changed: ['context', 'rateLimits'] })
})
