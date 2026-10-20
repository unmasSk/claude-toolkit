// What the plan tool and the agent events do to the plan the pane draws (D-150..D-153).
import type { TurnCompleteReason } from 'claude-code'

import type { FoldedTask, Plan, PlanPhase, PlanStatus, PlanStep, PlanTask } from './plan-pane-state'

export const EMPTY_PLAN: Plan = { current: null, finished: [] }

export type Change = { plan: Plan } | { error: string }

const STATUSES: readonly PlanStatus[] = ['in_progress', 'done']

const SECOND_MS = 1000
const MINUTE_MS = 60_000

const isStatus = (value: unknown): value is PlanStatus => STATUSES.some(one => one === value)

// Step ids are compared lowercased and without accents.
const keyOf = (id: string) =>
  id.normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toLowerCase()

const isText = (value: unknown): value is string => typeof value === 'string' && value.trim() !== ''

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null

const isIssue = (value: unknown): value is number | null =>
  value === null || (typeof value === 'number' && Number.isInteger(value))

const stepsOf = (task: PlanTask): PlanStep[] => task.phases.flatMap(phase => phase.steps)

export const pendingSteps = (plan: Plan): PlanStep[] =>
  plan.current === null ? [] : stepsOf(plan.current).filter(step => step.status !== 'done')

const readSteps = (raw: unknown, where: string): PlanStep[] | string => {
  if (!Array.isArray(raw) || raw.length === 0) return `${where} has no steps`
  const steps: PlanStep[] = []
  for (const one of raw) {
    const id = typeof one?.id === 'number' ? String(one.id) : one?.id
    if (!isText(id) || !isText(one?.title)) return `every step of ${where} needs an id and a title`
    steps.push({ id, title: one.title, status: 'pending', rounds: 0, agents: [] })
  }
  return steps
}

const readPhases = (task: Record<string, unknown>): PlanPhase[] | string => {
  if (task.phases === undefined) {
    const steps = readSteps(task.steps, 'the task')
    return typeof steps === 'string' ? steps : [{ title: null, steps }]
  }
  if (!Array.isArray(task.phases) || task.phases.length === 0) return 'phases must be a non-empty list'
  const phases: PlanPhase[] = []
  for (const phase of task.phases) {
    if (!isText(phase?.title)) return 'every phase needs a title'
    const steps = readSteps(phase.steps, `phase "${phase.title}"`)
    if (typeof steps === 'string') return steps
    phases.push({ title: phase.title, steps })
  }
  return phases
}

const foldOf = (task: PlanTask): FoldedTask | null =>
  task.finishedAt === null
    ? null
    : { title: task.title, issue: task.issue, durationMs: task.finishedAt - task.startedAt }

// A new task replaces the current one; a finished current one folds to a line (D-153).
export const applyTask = (plan: Plan, task: unknown, now: number): Change => {
  if (!isRecord(task) || !isText(task.title)) return { error: 'the task needs a title' }
  const issue = task.issue ?? null
  if (!isIssue(issue)) return { error: 'issue must be an issue number or null' }
  const phases = readPhases(task)
  if (typeof phases === 'string') return { error: phases }
  const keys = phases.flatMap(phase => phase.steps.map(step => keyOf(step.id)))
  const repeated = keys.find((key, at) => keys.indexOf(key) !== at)
  if (repeated !== undefined) return { error: `step id "${repeated}" is used twice` }
  const folded = plan.current === null ? null : foldOf(plan.current)
  const finished = folded === null ? plan.finished : [...plan.finished, folded]
  return { plan: { current: { title: task.title, issue, startedAt: now, finishedAt: null, phases }, finished } }
}

export const applyStatus = (plan: Plan, stepId: unknown, status: unknown, now: number): Change => {
  const id = typeof stepId === 'number' ? String(stepId) : stepId
  if (!isText(id)) return { error: 'step needs a step id' }
  if (!isStatus(status)) {
    return { error: `status of step "${id}" must be one of: ${STATUSES.join(', ')}` }
  }
  if (plan.current === null) return { error: `no task to change step "${id}" in: send the task first` }
  const current = structuredClone(plan.current)
  const step = stepsOf(current).find(one => keyOf(one.id) === keyOf(id))
  if (step === undefined) return { error: `the task "${current.title}" has no step "${id}"` }
  step.status = status
  // A finished step keeps its tick and rounds; its agents leave (D-151).
  if (step.status === 'done') step.agents = []
  const isFinished = stepsOf(current).every(one => one.status === 'done')
  current.finishedAt = isFinished ? (current.finishedAt ?? now) : null
  return { plan: { ...plan, current } }
}

// The step agents attach to: the first one in progress, in plan order.
const activeStep = (task: PlanTask): PlanStep | undefined =>
  stepsOf(task).find(step => step.status === 'in_progress')

// An agent launched with no step in progress is not drawn.
export const addAgent = (plan: Plan, agentId: string, type: string): Plan => {
  if (plan.current === null) return plan
  const current = structuredClone(plan.current)
  const step = activeStep(current)
  if (step === undefined) return plan
  step.agents.push({ id: agentId, type, result: null, durationMs: null })
  const launches = new Map<string, number>()
  for (const agent of step.agents) launches.set(agent.type, (launches.get(agent.type) ?? 0) + 1)
  // Rounds = the most launches of one agent type in the step.
  step.rounds = Math.max(step.rounds, ...launches.values())
  return { ...plan, current }
}

// An agent stopped before its answer shows how it ended, never a partial answer as its result.
const resultOf = (answer: string, reason: TurnCompleteReason) => {
  if (reason === 'aborted') return 'interrupted'
  if (reason !== 'answer') return 'failed'
  return answer.split('\n').find(line => line.trim() !== '')?.trim() ?? ''
}

export const endAgent = (
  plan: Plan,
  agentId: string,
  answer: string,
  durationMs: number,
  reason: TurnCompleteReason,
): Plan => {
  if (plan.current === null) return plan
  const current = structuredClone(plan.current)
  const agent = stepsOf(current).flatMap(step => step.agents).find(one => one.id === agentId)
  if (agent === undefined) return plan
  agent.result = resultOf(answer, reason)
  agent.durationMs = durationMs
  return { ...plan, current }
}

export const formatDuration = (ms: number) =>
  ms < MINUTE_MS ? `${Math.floor(ms / SECOND_MS)} s` : `${Math.round(ms / MINUTE_MS)} min`
