import { update } from 'claude-code'
import type { Register, StateDollar } from 'claude-code'

import { drawPane } from './plan-pane-look.tsx'
import { EMPTY_PLAN, addAgent, applyStatus, applyTask, endAgent, isTicking, pendingSteps } from './plan-pane-model.ts'
import type { Change } from './plan-pane-model.ts'
import type { Plan, PlanStep, PlanTask, UsageReading } from './plan-pane-state'
import { drawUsage, register as registerUsageBars } from './usage-bars.tsx'

// The plan stays in view (D-149, D-153): opened without focus, closeOnEscape or holdToasts.
const PANE = 'plan'
const PLAN = { plugin: 'unmassk-toolkit', key: 'plan' } as const
// Running times tick on screen once a second (D-162).
const TICK_MS = 1000

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

export const register: Register = on => {
  // hooks.json takes one module per plugin: the usage band (D-166) registers from here.
  registerUsageBars(on)

  on('session.start', async ($, e, next) => {
    // The pane opens before the tool registers: a failed register must not leave it closed.
    await $.ui.open({ id: PANE, title: 'Plan' })
    $.clock.every(TICK_MS, () => $.ui.invalidate('ui.render'))
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
    if (agentId !== undefined) {
      const now = await $.clock.now()
      await change($, plan => ({ plan: addAgent(plan, agentId, e.subagentType, now) }))
    }

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
    const { value: plan = EMPTY_PLAN } = await $.state.get(PLAN)
    // The clock is read only when a live time is drawn; with nothing running `now` is unused.
    const now = isTicking(plan) ? await $.clock.now() : 0

    const ui = $.ui.resolve(e)
    // Only these surfaces draw an Svg; elsewhere resolve may still hand one back that draws nothing.
    const hasSvg = e.surface === 'desktop' || e.surface === 'vscode' || e.surface === 'mobile'

    const surface = hasSvg ? ui : { Box: ui.Box, Text: ui.Text }
    // This session's reading (D-166), else the one the last session stored.
    const { value: measured } = await $.state.get({ plugin: 'unmassk-toolkit', key: 'usage' })
    // A store that cannot be read only leaves the bars out until the first reading.
    const stored = measured ? undefined : await $.store.get('usage-bars').catch(() => undefined)
    const usage = measured ?? (stored as UsageReading | undefined) ?? null
    const usageNow = usage === null ? 0 : now || (await $.clock.now())

    return (
      // The plan on top; the usage card pinned to the bottom of the pane (D-170).
      <ui.Box flexDirection="column" height={e.props.scroll.bodyRows}>
        <ui.Box flexDirection="column" flexGrow={1}>
          {drawPane(surface, plan, e.props.bodyColumns, now)}
        </ui.Box>
        {drawUsage(surface, usage, usageNow)}
      </ui.Box>
    )
  })
}
