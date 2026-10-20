// #98 phases 2-4: shared bottom hooks and readers for the plan-pane tests.
import { mock } from 'claude-code/testing'

export const PLUGIN = 'unmassk-toolkit'
export const PLAN_TOOL = `mcp__${PLUGIN}__plan`
export const PLAN_STATE = { plugin: PLUGIN, key: 'plan' } as const
export const SURFACES = ['terminal', 'desktop'] as const

// Marks the pane draws (D-158, D-160): an empty circle for a pending step, a filled or
// ticked circle for a done one; one place to change them. The in-progress ring (◉) is neither.
export const PENDING = '○'
export const DONE_MARKS: readonly string[] = ['●', '✓', '✔']
// A finished task folded to one line (D-153) may keep its tick.
export const FOLDED_MARKS: readonly string[] = DONE_MARKS
export const rounds = (n: number) => new RegExp(`↻\\s?${n}\\b`)
// Durations (owner's format, running and frozen alike): under a minute `45s`, under an
// hour `12m 05s`, from an hour `1h 12m`. `took('12m 05s')` matches that text as a whole.
export const took = (text: string) => new RegExp(`\\b${text}\\b`)

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
  if (node.type === 'Svg') return svgGlyphs(String(node.props?.source ?? ''), String(node.props?.alt ?? ''))
  const own = node.children === undefined ? [] : node.children
  const kids = textOf(own)
  return kids === '' && typeof node.props?.label === 'string' ? node.props.label : kids
}

// D-160 colours, read from the Checklist mod Bex sent: the drawing's own hex, not theme keys.
export const GREEN = '#5a9e6f'
export const ORANGE = '#d98b6a'
export const GREY = '#5c5b56'
export const TICK_STROKE = '#1f1e1d'
// D-159's agent colours, kept by D-160: the app's theme keys (ThemeKey, types 2.1.299).
export const AMBER = 'warning'
export const RED = 'error'

type Attrs = Record<string, string>
const attrsOf = (tag: string): Attrs =>
  Object.fromEntries([...tag.matchAll(/([\w-]+)="([^"]*)"/g)].map(([, k, v]) => [k!, v!.toLowerCase()]))
export const shapesOf = (source: string, shape: 'rect' | 'circle' | 'path'): Attrs[] =>
  [...source.matchAll(new RegExp(`<${shape}\\b[^>]*>`, 'g'))].map(([tag]) => attrsOf(tag))

// An Svg icon or bar read as the glyphs the terminal would show: a done disc, a ring in
// progress, an empty ring; one glyph per bar segment. Unknown drawings read as their alt.
const svgGlyphs = (source: string, alt: string): string => {
  const rects = shapesOf(source, 'rect')
  if (rects.length > 0) return rects.map(r => (r.fill === GREEN ? '■' : r.fill === ORANGE ? '▣' : '□')).join('')
  const circles = shapesOf(source, 'circle')
  if (circles.some(c => c.fill === GREEN)) return '●'
  if (circles.some(c => c.stroke === ORANGE)) return '◐'
  if (circles.some(c => c.stroke === GREY)) return PENDING
  return alt
}

const isRowBox = (node: any): boolean => {
  if (node?.type !== 'Box' || String(node.props?.flexDirection ?? 'row').startsWith('column')) return false
  const nested = (kids: any): boolean =>
    (Array.isArray(kids) ? kids : [kids]).some(
      (kid: any) =>
        kid !== null &&
        typeof kid === 'object' &&
        (kid.type === 'Markdown' || (kid.type === 'Box' && String(kid.props?.flexDirection ?? 'row').startsWith('column')) || nested(kid.children)),
    )
  return !nested(node.children)
}

const rowTextOf = (node: any): string =>
  node.type === 'Box'
    ? (node.children ?? []).map((kid: any) => (typeof kid === 'object' && kid?.type === 'Box' ? rowTextOf(kid) : textOf(kid))).filter((t: string) => t !== '').join(' ')
    : textOf(node)

// The drawn pane as the person reads it: one row per outermost Text or Button, per row
// Box (an icon, its label and its time side by side), or per Markdown line, in document order.
export const rowNodesOf = (tree: any): any[] => {
  const nodes: any[] = []
  const walk = (node: any) => {
    if (node === null || node === undefined || typeof node !== 'object') return
    if (Array.isArray(node)) return node.forEach(walk)
    if (node.type === 'Markdown') return void String(node.props?.text ?? '').split('\n').forEach(line => nodes.push({ type: 'Line', text: line }))
    if (node.type === 'Text' || node.type === 'Button' || node.type === 'Svg' || isRowBox(node)) return void nodes.push(node)
    walk(node.children)
  }
  walk(tree)
  return nodes
}

const lineOf = (node: any) => (node.type === 'Line' ? node.text : rowTextOf(node))

export const rowsOf = (tree: any): string[] => rowNodesOf(tree).map(lineOf)

// weight: the Text prop as written (inherited), never derived from `bold`: `bold: true` alone draws semibold.
export type Paint = { color: string | undefined; bold: boolean; weight: string | undefined; dim: boolean }
export type Leaf = { kind: 'text'; text: string; paint: Paint } | { kind: 'svg'; props: Record<string, any> }

// What a row is made of, in order: each run of text with the paint it inherits, and each Svg.
export const leavesOf = (node: any, paint: Paint = { color: undefined, bold: false, weight: undefined, dim: false }): Leaf[] => {
  if (node === null || node === undefined || node === false) return []
  if (typeof node === 'string' || typeof node === 'number') return [{ kind: 'text', text: String(node), paint }]
  if (Array.isArray(node)) return node.flatMap(kid => leavesOf(kid, paint))
  if (node.type === 'Svg') return [{ kind: 'svg', props: node.props ?? {} }]
  const props = node.props ?? {}
  const own: Paint =
    node.type === 'Text' || node.type === 'Button'
      ? {
          color: typeof props.color === 'string' ? props.color : paint.color,
          bold: props.bold === true || ['bold', 'semibold'].includes(props.weight) || (props.bold === undefined && paint.bold),
          weight: typeof props.weight === 'string' ? props.weight : paint.weight,
          dim: props.dimColor === true || (props.dimColor === undefined && paint.dim),
        }
      : paint
  const kids = leavesOf(node.children ?? [], own)
  return kids.length === 0 && typeof props.label === 'string' ? [{ kind: 'text', text: props.label, paint: own }] : kids
}

// The row holding the text (first in document order) and what it is made of.
export const rowOf = (tree: any, text: string | RegExp) => {
  const node = rowNodesOf(tree).find(one => {
    const line = lineOf(one)
    return typeof text === 'string' ? line.includes(text) : text.test(line)
  })
  return { node, leaves: node === undefined ? [] : leavesOf(node) }
}

// The paint of the text run holding `text` in those leaves; undefined when none holds it.
export const paintAt = (leaves: Leaf[], text: string | RegExp): Paint | undefined =>
  leaves.find(
    (leaf): leaf is Extract<Leaf, { kind: 'text' }> =>
      leaf.kind === 'text' && (typeof text === 'string' ? leaf.text.includes(text) : text.test(leaf.text)),
  )?.paint

// The step's circle: its Svg on a surface that draws one, else the first text run that shows a glyph.
export const markLeafOf = (leaves: Leaf[]): Leaf | undefined =>
  leaves.find(leaf => leaf.kind === 'svg' || leaf.text.trim() !== '')

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

// The progress bar's count, `done/total`, closes its row (D-158).
export const COUNTER = /(\d+)\/(\d+)\s*$/

// The first glyph a row shows: a step's circle.
export const markOf = (row: string | undefined) => [...(row ?? '').trimStart()][0] ?? ''

export const isDoneStep = (row: string | undefined) => !COUNTER.test(row ?? '') && DONE_MARKS.includes(markOf(row))

export const doneSteps = (rows: string[]) => rows.filter(isDoneStep)

// The bar as drawn: one segment per step, each told apart by glyph and paint (a bar
// Svg reads one segment per rect, by fill); the count on the bar's row or the row after.
export const progressOf = (tree: any) => {
  const nodes = rowNodesOf(tree)
  const rows = nodes.map(lineOf)
  const at = rows.findIndex(row => COUNTER.test(row))
  const [, done, total] = rows[at]?.match(COUNTER) ?? []
  const segmentsOf = (node: any): string[] =>
    node === undefined
      ? []
      : leavesOf(node).flatMap(leaf =>
          leaf.kind === 'svg'
            ? shapesOf(String(leaf.props.source ?? ''), 'rect').map(r => `rect ${r.fill}`)
            : [...leaf.text.replace(/\d+\/\d+/g, '').replace(/\s/g, '')].map(
                glyph => `${glyph} ${leaf.paint.color ?? ''} ${leaf.paint.dim ? 'dim' : ''}`,
              ),
        )
  const own = segmentsOf(nodes[at])
  const barAt = own.length > 0 ? at : at - 1
  return {
    at: barAt,
    counters: rows.filter(row => COUNTER.test(row)).length,
    done: Number(done),
    total: Number(total),
    segments: barAt === at ? own : segmentsOf(nodes[barAt]),
  }
}
