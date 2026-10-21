// The usage bars under the plan in the side pane (D-165, D-166): two bars, this session's context and the week (7 d), percent only (D-168).
// Cut down from MoonZhe/usage-band (hooks/register.tsx and pills.ts), Copyright (c) 2026 MoonZhe, MIT;
// see NOTICE beside this file.
import { update } from 'claude-code'
import type { Register } from 'claude-code'

import type { UsageReading, UsageWindow } from './plan-pane-state'


type Rate = { kind: string; percentUsed: number; resetsAt?: string }


const CELLS = 10

const pickLimit = (list: readonly Rate[], kind: string): UsageWindow | null => {
  const r = list.find(x => x.kind === kind)
  return r ? { percentUsed: r.percentUsed, resetsAt: r.resetsAt ?? null } : null
}

type Context = { tokens?: number; window?: number; percent?: number }

// How full this session's context is, in percent; unknown until the engine says.
const contextPercent = (c: Context | undefined): number | null => {
  if (c === undefined) return null
  if (typeof c.percent === 'number') return c.percent
  return typeof c.tokens === 'number' && typeof c.window === 'number' && c.window > 0 ? (100 * c.tokens) / c.window : null
}

// This session's context and the weekly limit; a reading with neither is no reading.
const toReading = (context: Context | undefined, list: readonly Rate[]): UsageReading | null => {
  const sessionPercent = contextPercent(context)
  const sevenDay = pickLimit(list ?? [], 'seven_day')
  const tokens = typeof context?.tokens === 'number' && typeof context.window === 'number' ? { used: context.tokens, window: context.window } : null
  return sessionPercent !== null || sevenDay ? { context: sessionPercent, tokens, sevenDay } : null
}

// A window whose reset time has passed starts over, whatever the last reading said.
const percentOf = (w: UsageWindow, now: number) =>
  w.resetsAt !== null && Date.parse(w.resetsAt) <= now ? 0 : Math.max(0, Math.min(100, w.percentUsed))


const fmtPercent = (percent: number) => `${Math.round(percent)}%`

const barCells = (percent: number) => {
  const filled = Math.round((percent / 100) * CELLS)
  return '█'.repeat(filled) + '░'.repeat(CELLS - filled)
}

export const register: Register = on => {
  on('session.measure', async ($, e, next) => {
    const reading = toReading(e.context, e.rateLimits)
    if (reading !== null) {
      // The band redraws from state first: a refused store write only costs the next session's first draw.
      await update($, { plugin: 'unmassk-toolkit', key: 'usage' }, () => reading)
      // Only the week is kept for the next session: its context starts empty.
      await $.store.set('usage-bars', { context: null, tokens: null, sevenDay: reading.sevenDay }).catch(() => undefined)
      $.ui.invalidate('ui.render')
    }

    return next(e)
  })
}

type Ui = { Box: any; Text: any; Svg?: any }

// An instrument of fine marks, in the plan pane's own colours (D-169): green while there is room, orange from 90 %.
const GREEN = '#5a9e6f'
const ORANGE = '#d98b6a'
const GREY = '#5c5b56'
const MARKS = 30

const fmtTokens = (n: number) =>
  n >= 1_000_000 ? `${+(n / 1_000_000).toFixed(1)}M` : n >= 1_000 ? `${Math.round(n / 1_000)}k` : String(n)

// Each mark is its own small drawing, spread with space-between: the row always spans the card exactly.
const MARK_W = 6
const MARK_H = 7
const markSvg = (fill: string, opacity: number) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${MARK_W}" height="${MARK_H}" viewBox="0 0 ${MARK_W} ${MARK_H}"><rect width="${MARK_W}" height="${MARK_H}" rx="1" fill="${fill}" fill-opacity="${opacity}"/></svg>`

const Marks = ({ Box, Svg }: Ui, percent: number) => {
  const on = Math.round((percent / 100) * MARKS)
  const lit = markSvg(percent >= 90 ? ORANGE : GREEN, 1)
  const off = markSvg(GREY, 0.45)
  return (
    <Box flexDirection="row" justifyContent="space-between">
      {Array.from({ length: MARKS }, (_, i) => (
        <Svg key={i} source={i < on ? lit : off} alt="" width={MARK_W} height={MARK_H} />
      ))}
    </Box>
  )
}

// Drawn by the plan pane under the plan; nothing until the first reading.
export const drawUsage = (ui: Ui, reading: UsageReading | null, now: number) => {
  if (reading === null) return null
  const { Box, Text, Svg } = ui
  // The owner's order and labels: never the engine's list order.
  const shown = [
    ...(reading.context !== null
      ? [{
          label: 'Sesión',
          percent: Math.max(0, Math.min(100, reading.context)),
          detail: reading.tokens ? `${fmtTokens(reading.tokens.used)}/${fmtTokens(reading.tokens.window)}` : '',
        }]
      : []),
    ...(reading.sevenDay ? [{ label: 'Semana', percent: percentOf(reading.sevenDay, now), detail: '' }] : []),
  ]
  return (
    <Box flexDirection="column" borderStyle="round" borderColor={GREY} paddingX={1}>
      {shown.map(({ label, percent, detail }) =>
        Svg === undefined ? (
          <Text key={label}>
            {`${label} `}
            <Text color={percent >= 90 ? ORANGE : GREEN}>{barCells(percent)}</Text>
            <Text bold>{` ${fmtPercent(percent)}`}</Text>
          </Text>
        ) : (
          <Box key={label} flexDirection="column">
            <Box flexDirection="row">
              <Box flexGrow={1}>
                <Text dimColor>{label}</Text>
              </Box>
              <Text color={percent >= 90 ? ORANGE : undefined}>{`${Math.round(percent)}`}</Text>
              <Text dimColor>{detail !== '' ? `%  ${detail}` : '%'}</Text>
            </Box>
            {Marks(ui, percent)}
          </Box>
        ),
      )}
    </Box>
  )
}
