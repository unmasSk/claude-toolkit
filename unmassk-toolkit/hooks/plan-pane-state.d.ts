export type PlanStatus = 'pending' | 'in_progress' | 'done'

export type PlanAgent = { id: string; type: string; result: string | null; durationMs: number | null }

// startedAt: when its current span in progress began (ms), null outside one.
// spentMs: the sum of its closed spans, null until the first one closes.
export type PlanStep = {
  id: string
  title: string
  status: PlanStatus
  rounds: number
  startedAt: number | null
  spentMs: number | null
  agents: PlanAgent[]
}

// A plain task (D-152) has one phase whose title is null.
export type PlanPhase = { title: string | null; steps: PlanStep[] }

export type PlanTask = {
  title: string
  issue: number | null
  startedAt: number
  finishedAt: number | null
  phases: PlanPhase[]
}

export type FoldedTask = { title: string; issue: number | null; durationMs: number }

export type Plan = { current: PlanTask | null; finished: FoldedTask[] }

declare module 'claude-code' {
  interface PluginState {
    'unmassk-toolkit': { plan: Plan }
  }
}
