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
const MARKS = 40
const MARK_H = 8

const fmtTokens = (n: number) =>
  n >= 1_000_000 ? `${+(n / 1_000_000).toFixed(1)}M` : n >= 1_000 ? `${Math.round(n / 1_000)}k` : String(n)

const marksSvg = (percent: number, width: number) => {
  const step = width / MARKS
  const on = Math.round((percent / 100) * MARKS)
  const colour = percent >= 90 ? ORANGE : GREEN
  const marks = Array.from({ length: MARKS }, (_, i) => {
    const lit = i < on
    return `<rect x="${(i * step + 0.6).toFixed(1)}" y="0" width="${(step - 1.6).toFixed(1)}" height="${MARK_H}" rx="1" fill="${lit ? colour : GREY}" fill-opacity="${lit ? 1 : 0.45}"/>`
  })
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${MARK_H}" viewBox="0 0 ${width} ${MARK_H}">${marks.join('')}</svg>`
}

// Drawn by the plan pane under the plan; nothing until the first reading.
export const drawUsage = (ui: Ui, reading: UsageReading | null, now: number, columns: number) => {
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
  // A pane column is about 7 px wide on the desktop.
  const width = Math.max(120, columns * 7)
  return (
    <Box flexDirection="column" marginTop={1} rowGap={1}>
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
            <Svg source={marksSvg(percent, width)} alt={`${label} ${fmtPercent(percent)}`} width={width} height={MARK_H} />
          </Box>
        ),
      )}
    </Box>
  )
}
