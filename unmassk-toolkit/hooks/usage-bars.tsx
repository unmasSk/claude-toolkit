// The usage bars under the plan in the side pane (D-165, D-166): two bars, the session (5 h) and the week (7 d), percent only.
// Cut down from MoonZhe/usage-band (hooks/register.tsx and pills.ts), Copyright (c) 2026 MoonZhe, MIT;
// see NOTICE beside this file.
import { update } from 'claude-code'
import type { Register } from 'claude-code'

import type { UsageReading, UsageWindow } from './plan-pane-state'


type Rate = { kind: string; percentUsed: number; resetsAt?: string }

// The owner's order and labels: never the engine's list order.
const WINDOWS = [
  { label: 'Sesión', pick: (r: UsageReading) => r.fiveHour },
  { label: 'Semana', pick: (r: UsageReading) => r.sevenDay },
] as const

const CELLS = 10
const BAR_W = 60
const BAR_H = 6
const LEVEL_TERMINAL = { ok: 'green', warn: 'yellow', high: 'red' } as const
const LEVEL_SVG = { ok: '#2f9e63', warn: '#d39b12', high: '#d64040' } as const
const TRACK = '#8a8a8a'

const pickLimit = (list: readonly Rate[], kind: string): UsageWindow | null => {
  const r = list.find(x => x.kind === kind)
  return r ? { percentUsed: r.percentUsed, resetsAt: r.resetsAt ?? null } : null
}

// Only the two windows; a reading with neither is no reading.
const toReading = (list: readonly Rate[]): UsageReading | null => {
  const fiveHour = pickLimit(list, 'five_hour')
  const sevenDay = pickLimit(list, 'seven_day')
  return fiveHour || sevenDay ? { fiveHour, sevenDay } : null
}

// A window whose reset time has passed starts over, whatever the last reading said.
const percentOf = (w: UsageWindow, now: number) =>
  w.resetsAt !== null && Date.parse(w.resetsAt) <= now ? 0 : Math.max(0, Math.min(100, w.percentUsed))

const level = (percent: number) => (percent >= 90 ? 'high' : percent >= 70 ? 'warn' : 'ok')

const fmtPercent = (percent: number) => `${Math.round(percent)}%`

const barSvg = (percent: number) => {
  const track = `<rect x="0" y="0" width="${BAR_W}" height="${BAR_H}" rx="${BAR_H / 2}" fill="${TRACK}" fill-opacity="0.3"/>`
  const fill =
    percent > 0
      ? `<rect x="0" y="0" width="${((BAR_W * percent) / 100).toFixed(1)}" height="${BAR_H}" rx="${BAR_H / 2}" fill="${LEVEL_SVG[level(percent)]}"/>`
      : ''
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${BAR_W}" height="${BAR_H}" viewBox="0 0 ${BAR_W} ${BAR_H}">${track}${fill}</svg>`
}

const barCells = (percent: number) => {
  const filled = Math.round((percent / 100) * CELLS)
  return '█'.repeat(filled) + '░'.repeat(CELLS - filled)
}

export const register: Register = on => {
  on('session.measure', async ($, e, next) => {
    const reading = toReading(e.rateLimits)
    if (reading !== null) {
      // The band redraws from state first: a refused store write only costs the next session's first draw.
      await update($, { plugin: 'unmassk-toolkit', key: 'usage' }, () => reading)
      // Kept for the next session until its first reading arrives.
      await $.store.set('usage-bars', reading).catch(() => undefined)
      $.ui.invalidate('ui.render')
    }

    return next(e)
  })
}

type Ui = { Box: any; Text: any; Svg?: any }

// Drawn by the plan pane under the plan; nothing until the first reading.
export const drawUsage = (ui: Ui, reading: UsageReading | null, now: number) => {
  if (reading === null) return null
  const { Box, Text, Svg } = ui
  const shown = WINDOWS.flatMap(({ label, pick }) => {
    const w = pick(reading)
    return w ? [{ label, percent: percentOf(w, now) }] : []
  })
  return (
    <Box flexDirection="column" marginTop={1}>
      {shown.map(({ label, percent }) =>
        Svg === undefined ? (
          <Text key={label}>
            {`${label} `}
            <Text color={LEVEL_TERMINAL[level(percent)]}>{barCells(percent)}</Text>
            <Text bold>{` ${fmtPercent(percent)}`}</Text>
          </Text>
        ) : (
          <Box key={label} flexDirection="row" columnGap={1} alignItems="center">
            <Text>{label}</Text>
            <Svg source={barSvg(percent)} alt={`${label} ${fmtPercent(percent)}`} width={BAR_W} height={BAR_H} />
            <Text bold>{fmtPercent(percent)}</Text>
          </Box>
        ),
      )}
    </Box>
  )
}
