import { update } from 'claude-code'
import type { Register, StateDollar } from 'claude-code'

import { EMPTY_PLAN, addAgent, applyStatus, applyTask, endAgent, formatDuration, pendingSteps } from './plan-pane-model.ts'
import type { Change } from './plan-pane-model.ts'
import type { Plan, PlanAgent, PlanStep, PlanTask } from './plan-pane-state'

// The plan stays in view (D-149, D-153): opened without focus, closeOnEscape or holdToasts.
const PANE = 'plan'
const PLAN = { plugin: 'unmassk-toolkit', key: 'plan' } as const

const TICK = '✓'
const MARK = { pending: '○', in_progress: '▶', done: TICK } as const

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

// Commands that call the work done (D-156); a release dry run closes nothing.
const isClosing = (command: string) =>
  /\bgh\s+issue\s+close\b/.test(command) ||
  /\bgitmem\s+next\b/.test(command) ||
  (/\bbin\/release\.py\b/.test(command) && !/--dry-run\b/.test(command))

const closeRefusal = (task: PlanTask, pending: PlanStep[]) =>
  `the task "${task.title}" still has steps not done in the plan pane: ` +
  `${pending.map(step => `${step.id} ${step.title}`).join('; ')}. Finish them and tick them with the plan tool first.`

const issueOf = (issue: number | null) => (issue === null ? '' : ` #${issue}`)

const taskRow = (task: PlanTask) =>
  `${task.title}${issueOf(task.issue)}` +
  (task.finishedAt === null ? '' : ` · ${formatDuration(task.finishedAt - task.startedAt)}`)

const roundsOf = (rounds: number) => (rounds > 1 ? ` ↻${rounds}` : '')

const stepRow = (step: PlanStep) => `  ${MARK[step.status]} ${step.title}${roundsOf(step.rounds)}`

const agentRow = (agent: PlanAgent) =>
  `      ${agent.type.split(':').pop()} · ${agent.result ?? 'running'}` +
  (agent.durationMs === null ? '' : ` · ${formatDuration(agent.durationMs)}`)

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
  }).catch(($, e, next) =>
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

    return (
      <Box flexDirection="column">
        {task === null && <Text dimColor>No plan yet.</Text>}
        {task !== null && <Text bold>{taskRow(task)}</Text>}
        {task?.phases.map(phase => (
          <Box flexDirection="column">
            {phase.title !== null && <Text bold>{phase.title}</Text>}
            {phase.steps.map(step => (
              <Box flexDirection="column">
                <Text dimColor={step.status === 'done'}>{stepRow(step)}</Text>
                {step.agents.map(agent => (
                  <Text dimColor>{agentRow(agent)}</Text>
                ))}
              </Box>
            ))}
          </Box>
        ))}
        {plan.finished.map(done => (
          <Text dimColor>{`${TICK} ${done.title}${issueOf(done.issue)} · ${formatDuration(done.durationMs)}`}</Text>
        ))}
      </Box>
    )
  })
}
