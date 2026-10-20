import { update } from 'claude-code'
import type { Register, StateDollar } from 'claude-code'

import { EMPTY_PLAN, addAgent, applyStatus, applyTask, endAgent, formatDuration, pendingSteps, stepsOf } from './plan-pane-model.ts'
import type { Change } from './plan-pane-model.ts'
import type { Plan, PlanAgent, PlanStep, PlanTask } from './plan-pane-state'

// The plan stays in view (D-149, D-153): opened without focus, closeOnEscape or holdToasts.
const PANE = 'plan'
const PLAN = { plugin: 'unmassk-toolkit', key: 'plan' } as const

// The look of the Checklist mod (D-158): a circle per step, a segmented bar with its count.
const TICK = '✓'
const MARK = { pending: '○', in_progress: '◐', done: '●' } as const
const SEGMENT = { done: '━', pending: '─' } as const
const ELLIPSIS = '…'
const AGENT_INDENT = 2

const PLAN_TOOL_SPEC = {
  name: 'plan',
  description:
    'Shows the current task in the plan pane and ticks its steps. Send the whole task once before starting ' +
    '({ task: { title, issue, phases: [{ title, steps: [{ id, title }] }] } }; a task with no issue sends ' +
    'issue: null, and one with no phases sends steps in place of phases). Then send { step, status } as each ' +
    'step starts (in_progress) and ends (done). A new task replaces the current one; a finished one folds to one line.',
  inputSchema: {
    type: 'object',
    properties: {
      task: { type: 'object', description: 'The whole task: title, issue (number or null), phases or steps.' },
      step: { type: 'string', description: 'The id of the step whose status changes.' },
      status: { type: 'string', enum: ['in_progress', 'done'] },
    },
  },
  isDeferred: false,
} as const

// Applies one change to the plan; answers the change's error, or null once written.
const change = async ($: StateDollar, apply: (plan: Plan) => Change): Promise<string | null> => {
  let error: string | null = null
  await update($, PLAN, value => {
    const out = apply(value ?? EMPTY_PLAN)
    error = 'error' in out ? out.error : null
    return 'error' in out ? (value ?? EMPTY_PLAN) : out.plan
  })
  return error
}

// Commands that call the work done (D-156), caught only where a command starts: a mention closes nothing,
// and neither does a release dry run.
const SEPARATOR = /[;&|(\n]/
const CLOSE_COMMAND = /^\s*(?:gh\s+issue\s+close|gitmem\s+next)\b/
const RELEASE = /^\s*(?:python3?\s+)?(?:\S*\/)?bin\/release\.py\b/

const isClosing = (command: string) =>
  command
    .split(SEPARATOR)
    .some(part => CLOSE_COMMAND.test(part) || (RELEASE.test(part) && !/--dry-run\b/.test(part)))

const stepLabel = (step: PlanStep) => `${step.id} ${step.title}`

const closeRefusal = (task: PlanTask, pending: PlanStep[]) =>
  `the task "${task.title}" still has steps not done in the plan pane: ` +
  `${pending.map(stepLabel).join('; ')}. Finish them and tick them with the plan tool first.`

const issueOf = (issue: number | null) => (issue === null ? '' : ` #${issue}`)

const taskRow = (task: PlanTask) =>
  `${task.title}${issueOf(task.issue)}` +
  (task.finishedAt === null ? '' : ` · ${formatDuration(task.finishedAt - task.startedAt)}`)

const roundsOf = (rounds: number) => (rounds > 1 ? ` ↻${rounds}` : '')

const stepRow = (step: PlanStep) => `${MARK[step.status]} ${step.title}${roundsOf(step.rounds)}`

// Cuts a text to `room` characters, the last one an ellipsis.
const fit = (text: string, room: number) => {
  const chars = [...text]
  return chars.length <= room ? text : `${chars.slice(0, Math.max(room - 1, 0)).join('')}${ELLIPSIS}`
}

// One line per agent: the status is cut so the name and the time always show.
const agentRow = (agent: PlanAgent, columns: number) => {
  const head = `${agent.type.split(':').pop()} · `
  const time = agent.durationMs === null ? '' : ` · ${formatDuration(agent.durationMs)}`
  const room = columns - AGENT_INDENT - [...head].length - [...time].length
  return `${head}${fit(agent.result ?? 'running', Math.max(room, 1))}${time}`
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    // The pane opens before the tool registers: a failed register must not leave it closed.
    await $.ui.open({ id: PANE, title: 'Plan' })
    await $.tool.register(PLAN_TOOL_SPEC)

    return next(e)
  })

  on('tool.call', { tool: 'mcp__unmassk-toolkit__plan' }, async ($, e) => {
    // An MCP tool's arguments ride loose beside `tool` on the call's input.
    const input = e as unknown as Record<string, unknown>
    const isTask = input.task !== undefined
    if (isTask === (input.step !== undefined)) return { deny: 'send either { task } or { step, status }' }
    const now = await $.clock.now()
    const error = await change($, plan =>
      isTask ? applyTask(plan, input.task, now) : applyStatus(plan, input.step, input.status, now),
    )
    if (error !== null) return { deny: error }

    return { result: isTask ? 'The task is in the plan pane.' : `Step ${String(input.step)} is ${String(input.status)}.` }
  }).catch(() => ({ deny: 'the plan tool failed: the pane was not updated' }))

  // A failed check never lets a closing command through unjudged; any other command passes.
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    if (!isClosing(e.command)) return next(e)
    const { value: plan = EMPTY_PLAN } = await $.state.get(PLAN)
    const pending = pendingSteps(plan)
    if (plan.current !== null && pending.length > 0) return { deny: closeRefusal(plan.current, pending) }

    return next(e)
  }).catch((_$, e, next) =>
    next.called || !isClosing(e.command) ? next(e) : { deny: 'the close gate failed: the plan pane could not be read' },
  )

  // The engine may drop the spec's isDeferred; this answer is read ahead of it.
  on('tool.describe', { tool: 'mcp__unmassk-toolkit__plan' }, async ($, e, next) => ({
    ...(await next(e)),
    isDeferred: false,
  }))

  on('agent.spawn', async ($, e, next) => {
    const started = await next(e)
    const agentId = started.deny === undefined ? started.agentId : undefined
    if (agentId !== undefined) await change($, plan => ({ plan: addAgent(plan, agentId, e.subagentType) }))

    return started
  })

  on('turn.complete', async ($, e, next) => {
    const ended = await next(e)
    const agentId = e.agentId
    if (agentId !== undefined) {
      await change($, plan => ({ plan: endAgent(plan, agentId, e.answer, e.durationMs, e.reason) }))
    }

    return ended
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const { value: plan = EMPTY_PLAN } = await $.state.get(PLAN)
    const task = plan.current
    const steps = task === null ? [] : stepsOf(task)
    const done = steps.filter(step => step.status === 'done').length
    const columns = e.props.bodyColumns

    return (
      <Box flexDirection="column">
        {task === null && <Text dimColor>No plan yet.</Text>}
        {task !== null && (
          <Box flexDirection="column" marginBottom={1}>
            <Text bold wrap="truncate-end">{taskRow(task)}</Text>
            <Text>
              {steps.map(step => (
                <Text dimColor={step.status !== 'done'}>{`${SEGMENT[step.status === 'done' ? 'done' : 'pending']} `}</Text>
              ))}
              <Text dimColor>{` ${done}/${steps.length}`}</Text>
            </Text>
          </Box>
        )}
        {task?.phases.map(phase => (
          <Box flexDirection="column" marginBottom={1}>
            {phase.title !== null && <Text dimColor wrap="truncate-end">{phase.title}</Text>}
            {phase.steps.map(step => (
              <Box flexDirection="column">
                <Text dimColor={step.status === 'done'} wrap="truncate-end">{stepRow(step)}</Text>
                {step.agents.map(agent => (
                  <Box paddingLeft={AGENT_INDENT}>
                    <Text dimColor wrap="truncate-end">{agentRow(agent, columns)}</Text>
                  </Box>
                ))}
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
  })
}
