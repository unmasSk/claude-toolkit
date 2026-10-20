// The pane's drawing (D-158, D-160, D-161): colours, icons and bar copied from
// nix-checklist-sidebar (hooks/register.tsx), Copyright (c) 2026 nikscz, MIT; see NOTICE beside this file.
import type { Elements } from 'claude-code'

import { formatDuration, isStopped, stepsOf } from './plan-pane-model.ts'
import type { Plan, PlanAgent, PlanStatus, PlanStep, PlanTask } from './plan-pane-state'

// What every surface draws with; Svg is absent on the terminal only.
type Ui = Pick<Elements['terminal'], 'Box' | 'Text'> & { Svg?: Elements['mobile']['Svg'] }

// Drawing, in the colours of Claude's dark theme.
const GREEN = '#5a9e6f'
const ORANGE = '#d98b6a'
const GREY = '#5c5b56'
// Agents: the app's theme keys (D-159, kept by D-160).
const AMBER = 'warning'
const RED = 'error'
const ICON_SIZE = 14
const PILL_W = 14
const PILL_W_NARROW = 8
const PILL_CAP = 12
const PILL_GAP = 4
const PILL_H = 4
const svg = (body: string) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${ICON_SIZE}" height="${ICON_SIZE}" viewBox="0 0 14 14">${body}</svg>`
const CHECK = '<path d="M4.2 7.3l1.9 1.9 3.8-4.2" fill="none" stroke="#1f1e1d" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
const ICON: Record<PlanStatus, string> = {
  done: svg(`<circle cx="7" cy="7" r="6.5" fill="${GREEN}"/>${CHECK}`),
  in_progress: svg(`<circle cx="7" cy="7" r="5.7" fill="none" stroke="${ORANGE}" stroke-width="1.6"/><circle cx="7" cy="7" r="2.6" fill="${ORANGE}"/>`),
  pending: svg(`<circle cx="7" cy="7" r="5.7" fill="none" stroke="${GREY}" stroke-width="1.4"/>`),
}
const ALT: Record<PlanStatus, string> = { done: 'done', in_progress: 'in progress', pending: 'to do' }
const FILL: Record<PlanStatus, string> = { done: GREEN, in_progress: ORANGE, pending: GREY }

// The terminal draws the same in characters.
const MARK: Record<PlanStatus, string> = { done: '✓', in_progress: '◉', pending: '○' }
const TERMINAL_PAINT: Record<PlanStatus, { color?: string; dimColor?: boolean }> = {
  done: { color: 'green' },
  in_progress: { color: ORANGE },
  pending: { dimColor: true },
}
const SEGMENT: Record<PlanStatus, string> = { done: '━', in_progress: '━', pending: '─' }

const TICK = '✓'
const ELLIPSIS = '…'
const AGENT_INDENT = 2

// One rounded segment per step, the first 12: green done, orange now, grey still to do.
const pills = (steps: readonly PlanStep[]) => {
  const n = Math.min(steps.length, PILL_CAP)
  const w = steps.length > PILL_CAP ? PILL_W_NARROW : PILL_W
  const width = n * w + (n - 1) * PILL_GAP
  const body = steps.slice(0, n).map(
    (step, i) => `<rect x="${i * (w + PILL_GAP)}" y="0" width="${w}" height="${PILL_H}" rx="2" fill="${FILL[step.status]}"/>`,
  )
  return {
    width,
    source: `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${PILL_H}" viewBox="0 0 ${width} ${PILL_H}">${body.join('')}</svg>`,
  }
}

// How long a done step took; none for a step never in progress or saved before spentMs existed.
const tookOf = (step: PlanStep) =>
  step.status === 'done' && typeof step.spentMs === 'number' ? formatDuration(step.spentMs) : null

const issueOf = (issue: number | null) => (issue === null ? '' : ` #${issue}`)

const taskRow = (task: PlanTask) =>
  `${task.title}${issueOf(task.issue)}` +
  (task.finishedAt === null ? '' : ` · ${formatDuration(task.finishedAt - task.startedAt)}`)

// Like "3/7": the step being worked on, or how many are done once none is.
const counterOf = (steps: PlanStep[]) => {
  const done = steps.filter(step => step.status === 'done').length
  const position = steps.some(step => step.status === 'in_progress') ? done + 1 : done
  return `${position}/${steps.length}`
}

// Cuts a text to `room` characters, the last one an ellipsis.
const fit = (text: string, room: number) => {
  const chars = [...text]
  return chars.length <= room ? text : `${chars.slice(0, Math.max(room - 1, 0)).join('')}${ELLIPSIS}`
}

const Bar = ({ Box, Text, Svg }: Ui, steps: PlanStep[]) => {
  const counter = counterOf(steps)
  if (Svg === undefined) {
    return (
      <Text>
        {steps.slice(0, PILL_CAP).map(step => (
          <Text {...TERMINAL_PAINT[step.status]}>{`${SEGMENT[step.status]} `}</Text>
        ))}
        <Text dimColor>{counter}</Text>
      </Text>
    )
  }
  const bar = pills(steps)
  return (
    <Box flexDirection="row" alignItems="center" gap={1}>
      <Svg source={bar.source} alt={counter} width={bar.width} height={PILL_H} />
      <Text dimColor>{counter}</Text>
    </Box>
  )
}

const Rounds = ({ Box, Text }: Ui, rounds: number) =>
  rounds > 1 ? (
    <Box flexShrink={0}>
      <Text color={AMBER}>{`↻${rounds}`}</Text>
    </Box>
  ) : null

// What a row took, pushed to its right edge by the growing part before it.
const Took = ({ Box, Text }: Ui, took: string | null) =>
  took === null ? null : (
    <Box flexShrink={0}>
      <Text dimColor>{took}</Text>
    </Box>
  )

// Only the numbered title is cut: the round mark and the duration always show.
const StepRow = (ui: Ui, step: PlanStep) => {
  const { Box, Text, Svg } = ui
  const label = { bold: step.status === 'in_progress', dimColor: step.status === 'done' }
  const mark =
    Svg === undefined ? (
      <Text {...TERMINAL_PAINT[step.status]}>{MARK[step.status]}</Text>
    ) : (
      <Svg source={ICON[step.status]} alt={ALT[step.status]} width={ICON_SIZE} height={ICON_SIZE} />
    )
  return (
    <Box flexDirection="row" alignItems="center" gap={1}>
      {mark}
      <Box flexDirection="row" flexGrow={1} flexShrink={1} minWidth={0} gap={1}>
        <Box flexShrink={1} minWidth={0}>
          <Text wrap="truncate-end" {...label}>{`${step.id} ${step.title}`}</Text>
        </Box>
        {Rounds(ui, step.rounds)}
      </Box>
      {Took(ui, tookOf(step))}
    </Box>
  )
}

// One line per agent: the status is cut so the name and the duration always show.
const AgentRow = (ui: Ui, agent: PlanAgent, columns: number) => {
  const { Box, Text } = ui
  const head = `${agent.type.split(':').pop()} · `
  const took = agent.durationMs === null ? null : formatDuration(agent.durationMs)
  const room = columns - AGENT_INDENT - [...head].length - (took === null ? 0 : [...took].length + 1)
  return (
    <Box flexDirection="row" paddingLeft={AGENT_INDENT} gap={1}>
      <Box flexGrow={1} flexShrink={1} minWidth={0}>
        <Text dimColor wrap="truncate-end">
          {head}
          <Text color={isStopped(agent) ? RED : undefined}>{fit(agent.result ?? 'running', Math.max(room, 1))}</Text>
        </Text>
      </Box>
      {Took(ui, took)}
    </Box>
  )
}

export const drawPane = (ui: Ui, plan: Plan, columns: number) => {
  const { Box, Text } = ui
  const task = plan.current
  return (
    <Box flexDirection="column">
      {task === null && <Text dimColor>No plan yet.</Text>}
      {task !== null && (
        <Box flexDirection="column" marginBottom={1}>
          <Text bold wrap="truncate-end">{taskRow(task)}</Text>
          {Bar(ui, stepsOf(task))}
        </Box>
      )}
      {task?.phases.map(phase => (
        <Box flexDirection="column" marginBottom={1}>
          {phase.title !== null && <Text dimColor wrap="truncate-end">{phase.title}</Text>}
          {phase.steps.map(step => (
            <Box flexDirection="column">
              {StepRow(ui, step)}
              {step.agents.map(agent => AgentRow(ui, agent, columns))}
            </Box>
          ))}
        </Box>
      ))}
      {plan.finished.map(folded => (
        <Text dimColor wrap="truncate-end">
          {`${TICK} ${folded.title}${issueOf(folded.issue)} · ${formatDuration(folded.durationMs)}`}
        </Text>
      ))}
    </Box>
  )
}
