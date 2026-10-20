// #98 phases 2-4: shared bottom hooks and readers for the plan-pane tests.
import { mock } from 'claude-code/testing'

export const PLUGIN = 'unmassk-toolkit'
export const PLAN_TOOL = `mcp__${PLUGIN}__plan`
export const PLAN_STATE = { plugin: PLUGIN, key: 'plan' } as const
export const SURFACES = ['terminal', 'desktop'] as const

// Marks the pane draws (proposal; one place to change them).
export const TICK = '✓'
export const rounds = (n: number) => new RegExp(`↻\\s?${n}\\b`)
export const minutes = (n: number) => new RegExp(`\\b${n} min\\b`)

const START = { cwd: '/work/project', surface: 'desktop', isInteractive: true } as const

type Open = { id: string; title?: string }

// The test's hooks are the bottom: they answer every $ call the module makes.
export const startSession = async ($: any, on: any, now = 1_000_000) => {
  const clock = mock.clock(on, { now })
  const opens: Open[] = []
  const registered: any[] = []
  const fellThrough: any[] = []
  on('ui.open', async (_$: unknown, e: Open) => {
    opens.push(e)
    return { value: { isPlaced: true } }
  })
  on('tool.register', async (_$: unknown, e: any) => {
    registered.push(e)
    return { value: { tool: `mcp__${PLUGIN}__${e.name}` } }
  })
  on('tool.call', async (_$: unknown, e: any) => {
    fellThrough.push(e)
    return { deny: `reached the bottom: no plugin hook answered ${e.tool}` }
  })
  on('agent.spawn', async (_$: unknown, e: any) => ({ model: 'opus', agentId: e.name }))
  on('turn.complete', async (_$: unknown, e: any) => ({ text: e.answer }))
  on('session.start', async (_$: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  // The test's $ has no state noun: it reads the plan as the module itself read it
  // (the op's answer wraps the StateRead: { value: { value, version } }).
  const planReads: unknown[] = []
  on('state.get', async (_$: unknown, e: any, next: any) => {
    const read = await next(e)
    if (e.plugin === PLAN_STATE.plugin && e.key === PLAN_STATE.key) planReads.push(read?.value?.value)
    return read
  })
  await $.session.start(START)
  return { clock, opens, registered, fellThrough, planReads }
}

export const callPlan = ($: any, input: Record<string, unknown>) =>
  $.tool.call({ tool: PLAN_TOOL, ...input })

// An agent the orchestrator launches; the bottom hands back `name` as its agentId.
export const spawnAgent = ($: any, agentId: string, subagentType: string) =>
  $.agent.spawn({ prompt: 'work', description: 'work', subagentType, name: agentId })

export const endAgent = ($: any, agentId: string, answer: string, durationMs: number) =>
  $.turn.complete({ agentId, answer, durationMs, isAborted: false, turnId: `t-${agentId}`, reason: 'answer' })

export const mountPane = async ($: any, paneId: string, surface: (typeof SURFACES)[number]) =>
  $.ui.mount({
    plugin: PLUGIN,
    surface,
    component: 'Pane',
    requestId: paneId,
    props: {
      title: 'Plan',
      isFocused: false,
      bodyColumns: 60,
      placement: 'dock',
      scroll: { offset: 0, bodyRows: 40 },
      view: {},
    },
  })

const textOf = (node: any): string => {
  if (node === null || node === undefined || node === false) return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  const own = node.children === undefined ? [] : node.children
  const kids = textOf(own)
  return kids === '' && typeof node.props?.label === 'string' ? node.props.label : kids
}

// The drawn pane as the person reads it: one row per outermost Text, Button or
// Markdown line, in document order, whatever Boxes hold them.
export const rowsOf = (tree: any): string[] => {
  const rows: string[] = []
  const walk = (node: any) => {
    if (node === null || node === undefined || typeof node !== 'object') return
    if (Array.isArray(node)) return node.forEach(walk)
    if (node.type === 'Text' || node.type === 'Button') return void rows.push(textOf(node))
    if (node.type === 'Markdown') return void rows.push(...String(node.props?.text ?? '').split('\n'))
    walk(node.children)
  }
  walk(tree)
  return rows
}

export const drawnRows = async (ui: any) => rowsOf(await ui.drawn())

// Index of the first row holding the text; -1 when none.
export const rowIndex = (rows: string[], text: string | RegExp) =>
  rows.findIndex(row => (typeof text === 'string' ? row.includes(text) : text.test(row)))

export const ISSUE_TASK = {
  title: 'Plan pane',
  issue: 98,
  phases: [
    {
      title: 'The plan tool and the pane',
      steps: [
        { id: '2.1', title: 'Write the pane tests' },
        { id: '2.2', title: 'Build the tool' },
      ],
    },
    {
      title: 'Agents in the step in progress',
      steps: [{ id: '3.1', title: 'Write the agent tests' }],
    },
  ],
}
