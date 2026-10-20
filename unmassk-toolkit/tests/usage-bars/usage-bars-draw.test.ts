// D-165/D-166: above the prompt, exactly two bars, "Sesión" (five_hour) and "Semana" (seven_day),
// each with its percent used, on the desktop (Svg) and in the terminal; nothing else.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import { SESSION, SURFACES, WEEK, bandText, drawnBand, fiveHour, measure, sevenDay, startSession, strayCells, svgCount, windowOf } from './usage-kit.ts'

test('should_draw_sesion_then_semana_each_with_the_percent_of_its_own_window', async ($, on) => {
  const world = await startSession($, on)
  // The week listed first: the order drawn is the owner's, never the engine's list.
  await measure($, world, [sevenDay(62), fiveHour(37)])

  for (const surface of SURFACES) {
    const tree = await drawnBand($, surface)
    const text = bandText(tree)
    const session = windowOf(tree, SESSION)
    const week = windowOf(tree, WEEK)

    expect([session.labels, week.labels], `each label once on ${surface}: ${JSON.stringify(text)}`).toEqual([1, 1])
    expect(text.indexOf(SESSION) < text.indexOf(WEEK), `Sesión above or before Semana on ${surface}`).toBe(true)
    expect([session.percent, week.percent], `five_hour is the session, seven_day the week, on ${surface}`).toEqual([37, 62])
  }
})

test('should_fill_each_terminal_bar_as_far_as_its_percent', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [fiveHour(30), sevenDay(80)])
  const tree = await drawnBand($, 'terminal')

  for (const [label, percent] of [[SESSION, 30], [WEEK, 80]] as const) {
    const bar = windowOf(tree, label)
    expect(bar.cells.length, `${label}: a bar of cells in the terminal`).toBeGreaterThanOrEqual(5)
    // One cell either way for rounding, never more.
    expect(Math.abs(bar.fill - percent / 100), `${label} at ${percent} %: ${bar.cells.join(' | ')}`).toBeLessThanOrEqual(1 / bar.cells.length + 0.001)
  }
})

test('should_draw_each_desktop_bar_as_an_svg_filled_as_far_as_its_percent', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [fiveHour(30), sevenDay(80)])
  const tree = await drawnBand($, 'desktop')

  for (const [label, percent] of [[SESSION, 30], [WEEK, 80]] as const) {
    const bar = windowOf(tree, label)
    expect(bar.svgs, `${label}: its own Svg bar on the desktop`).toBe(1)
    expect(Math.abs(bar.fill - percent / 100), `${label} at ${percent} %: fill ${bar.fill}`).toBeLessThanOrEqual(0.05)
  }
})

test('should_draw_no_third_bar_for_a_gateway_spend_limit', async ($, on) => {
  const world = await startSession($, on)
  await measure($, world, [fiveHour(37), { kind: 'spend_limit', percentUsed: 91 }, sevenDay(62)])

  for (const surface of SURFACES) {
    const tree = await drawnBand($, surface)
    const text = bandText(tree)

    expect(text, `the spend limit is not drawn on ${surface}`).not.toMatch(/91/)
    expect(strayCells(tree), `no bar before Sesión on ${surface}`).toBe(0)
  }
  expect(svgCount(await drawnBand($, 'desktop')), 'two Svg bars on the desktop, no third').toBe(2)
})

test('should_draw_no_context_cost_tokens_countdown_or_pace_mark', async ($, on) => {
  const world = await startSession($, on)
  // Every figure the upstream mod drew besides the two percents (the session resets in 3 h:
  // a countdown would draw a digit), each one a number no percent here is.
  await measure($, world, [fiveHour(37), sevenDay(62)], {
    context: { window: 200_000, tokens: 154_000, percent: 77 },
    cost: { usd: 12.34 },
  })

  for (const surface of SURFACES) {
    const text = bandText(await drawnBand($, surface))
    const words = (text.match(/\p{L}+/gu) ?? []).filter(word => word !== SESSION && word !== WEEK)

    expect(text.match(/\d+(?:[.,]\d+)?/g), `only the two percents on ${surface}: ${JSON.stringify(text)}`).toEqual(['37', '62'])
    expect(words, `no word but the two labels on ${surface}`).toEqual([])
  }
})
