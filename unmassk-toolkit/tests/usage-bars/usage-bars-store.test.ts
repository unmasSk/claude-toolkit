// D-166: the last reading is kept in $.store and drawn in the next session until its first reading;
// nothing stored, nothing drawn; no file is written outside $.store.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import { HOUR, SESSION, START, SURFACES, WEEK, bandText, drawnBand, fiveHour, measure, nextSession, sevenDay, startSession, windowOf } from './usage-kit.ts'

const percents = (tree: any) => [windowOf(tree, SESSION).percent, windowOf(tree, WEEK).percent]

test('should_draw_the_last_stored_percents_in_the_next_session_before_its_first_reading', async ($, on) => {
  const world = await startSession($, on)
  // Written by the mod itself in this session: the store the next session reads is never hand-made.
  await measure($, world, [fiveHour(44), sevenDay(71)])
  nextSession(world, { isStoreKept: true })
  await measure($, world, [])

  for (const surface of SURFACES) {
    expect(percents(await drawnBand($, surface)), `the stored reading on ${surface}`).toEqual([44, 71])
  }
})

test('should_draw_nothing_in_the_next_session_when_nothing_is_stored', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [fiveHour(44), sevenDay(71)])
  // The control: this session draws its reading.
  expect(percents(await drawnBand($, 'terminal')), 'drawn in its own session').toEqual([44, 71])

  nextSession(world, { isStoreKept: false })
  await measure($, world, [])

  for (const surface of SURFACES) {
    expect(bandText(await drawnBand($, surface)).trim(), `nothing kept outside $.store and $.state, on ${surface}`).toBe('')
  }
})

test('should_draw_the_next_session_s_first_reading_over_the_stored_one', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [fiveHour(44), sevenDay(71)])
  nextSession(world, { isStoreKept: true })
  await measure($, world, [fiveHour(5), sevenDay(72)])

  for (const surface of SURFACES) {
    expect(percents(await drawnBand($, surface)), `the new reading on ${surface}`).toEqual([5, 72])
  }
})

test('should_draw_zero_for_a_stored_window_whose_reset_passed_before_the_next_session', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [fiveHour(90, START + HOUR), sevenDay(71, START + 3 * 24 * HOUR)])
  nextSession(world, { isStoreKept: true })
  // Two hours later: the session window has reset, the week has not.
  await world.clock.advance(2 * HOUR)

  for (const surface of SURFACES) {
    expect(percents(await drawnBand($, surface)), `the reset session window drawn at 0 on ${surface}`).toEqual([0, 71])
  }
})

test('should_keep_the_reading_in_the_store_and_write_no_file_outside_it', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [fiveHour(44), sevenDay(71)])
  for (const surface of SURFACES) await drawnBand($, surface)
  await measure($, world, [fiveHour(45), sevenDay(71)])
  await measure($, world, [])

  expect(world.storeWrites.length, 'the reading went to $.store').toBeGreaterThan(0)
  expect(world.outside, 'no file and no host command').toEqual([])
})
