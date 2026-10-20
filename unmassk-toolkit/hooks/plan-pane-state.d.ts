export type PlanStatus = 'pending' | 'in_progress' | 'done'

// startedAt: when it was spawned (ms); plans saved before may lack it.
export type PlanAgent = {
  id: string
  type: string
  result: string | null
  durationMs: number | null
  startedAt?: number
}

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

// A plan limit window as last read (D-166); resetsAt is an ISO time, null when the engine gave none.
export type UsageWindow = { percentUsed: number; resetsAt: string | null }

// context: this session's context used, in percent (D-168).
export type UsageReading = {
  context: number | null
  tokens?: { used: number; window: number } | null
  sevenDay: UsageWindow | null
}

declare module 'claude-code' {
  interface PluginState {
    'unmassk-toolkit': { plan: Plan; usage: UsageReading }
  }
}
