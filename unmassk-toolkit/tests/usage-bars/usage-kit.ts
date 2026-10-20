// D-165/D-166: shared bottom hooks and readers for the usage-bars tests (the band above the prompt).
import { mock } from 'claude-code/testing'
import { leavesOf, shapesOf } from '../plan-pane/plan-kit.ts'

export const PLUGIN = 'unmassk-toolkit'
export const SURFACES = ['terminal', 'desktop'] as const
export type Surface = (typeof SURFACES)[number]

// The owner's labels (D-165): the 5-hour window is the session, the 7-day one the week.
export const SESSION = 'Sesión'
export const WEEK = 'Semana'
export const LABELS = [SESSION, WEEK] as const

// 10:00 on the person's clock.
export const START = new Date(2026, 9, 20, 10, 0).getTime()
export const MINUTE = 60_000
export const HOUR = 60 * MINUTE

export type Limit = { kind: string; percentUsed: number; resetsAt?: string }

export const iso = (ms: number) => new Date(ms).toISOString()
// A window as the engine reports it; resetsAt in the future unless given.
export const fiveHour = (percentUsed: number, resetsAt = START + 3 * HOUR): Limit => ({ kind: 'five_hour', percentUsed, resetsAt: iso(resetsAt) })
export const sevenDay = (percentUsed: number, resetsAt = START + 4 * 24 * HOUR): Limit => ({ kind: 'seven_day', percentUsed, resetsAt: iso(resetsAt) })

export const BAND = {
  hasSurvey: false,
  isWorking: false,
  maxRows: 12,
  bodyColumns: 60,
  scroll: { offset: 0, bodyRows: 11 },
  view: {},
}

export type World = {
  clock: ReturnType<typeof mock.clock>
  // What $.store holds, as the mod left it: written only by the mod, never by a test.
  store: Map<string, unknown>
  storeWrites: string[]
  // Every write the mod tried outside $.store: files and host commands.
  outside: string[]
  usage: { startedAt: number; context: { window: number; tokens?: number; percent?: number }; rateLimits: Limit[]; cost?: { usd: number } }
  isStoreRefusing: boolean
  isFreshSession: boolean
}

// The test's hooks are the bottom: they answer every $ call the plugin makes.
export const startSession = async ($: any, on: any, now = START): Promise<World> => {
  const world: World = {
    clock: mock.clock(on, { now }),
    store: new Map(),
    storeWrites: [],
    outside: [],
    usage: { startedAt: now, context: { window: 200_000 }, rateLimits: [] },
    isStoreRefusing: false,
    isFreshSession: false,
  }
  on('store.get', async (_$: unknown, e: { key: string }) => ({ value: world.store.get(e.key) }))
  on('store.set', async (_$: unknown, e: { key: string; value: unknown }) => {
    if (world.isStoreRefusing) return { deny: 'the store refused the write' }
    world.storeWrites.push(e.key)
    world.store.set(e.key, JSON.parse(JSON.stringify(e.value)))
    return { value: undefined }
  })
  on('store.delete', async (_$: unknown, e: { key: string }) => {
    world.store.delete(e.key)
    return { value: undefined }
  })
  on('store.keys', async () => ({ value: [...world.store.keys()] }))
  on('fs.write', async (_$: unknown, e: { path: string }) => {
    world.outside.push(`fs.write ${e.path}`)
    return { deny: 'reached the bottom: no file is written outside $.store' }
  })
  on('process.run', async (_$: unknown, e: { argv: readonly string[] }) => {
    world.outside.push(`process.run ${e.argv.join(' ')}`)
    return { deny: 'reached the bottom: no host command runs' }
  })
  on('session.usage', async () => ({ value: world.usage }))
  on('session.measure', async (_$: unknown, e: { changed: string[] }) => ({ changed: e.changed }))
  // What the engine draws in the band when no plugin draws: nothing.
  on('ui.render', { component: 'AbovePrompt' }, async () => ({ type: 'Box', props: {}, children: [] }))
  // The plan pane shares the plugin: its own start needs these.
  on('ui.open', async () => ({ value: { isPlaced: true } }))
  on('tool.register', async (_$: unknown, e: any) => ({ value: { tool: `mcp__${PLUGIN}__${e.name}` } }))
  on('session.start', async (_$: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  // A new session: the host's state reads empty until the new session writes its own; $.store is kept.
  on('state.get', { plugin: PLUGIN }, async (_$: unknown, e: any, next: any) =>
    world.isFreshSession ? { value: { value: undefined, version: 0 } } : next(e),
  )
  on('state.set', { plugin: PLUGIN }, async (_$: unknown, e: any, next: any) => {
    world.isFreshSession = false
    return next(e)
  })
  await $.session.start({ cwd: '/work/project', surface: 'desktop', isInteractive: true })
  return world
}

// A reading arrives: the engine's figures change, then it raises session.measure with them.
export const measure = async ($: any, world: World, rateLimits: Limit[], extra: Partial<World['usage']> = {}) => {
  world.usage = { ...world.usage, ...extra, rateLimits }
  const changed = rateLimits.length > 0 ? ['context', 'rateLimits'] : ['context']
  const { startedAt: _startedAt, ...figures } = world.usage
  return $.session.measure({ ...figures, changed })
}

// The next session on this machine: nothing in this session's state, no reading yet.
export const nextSession = (world: World, options: { isStoreKept: boolean }) => {
  world.isFreshSession = true
  world.usage = { ...world.usage, rateLimits: [] }
  if (!options.isStoreKept) world.store.clear()
}

export const mountBand = ($: any, surface: Surface) =>
  $.ui.mount({ plugin: PLUGIN, surface, component: 'AbovePrompt', requestId: 'above-prompt', props: BAND })

// The band drawn once on a surface: mount, read, unmount.
export const drawnBand = async ($: any, surface: Surface) => {
  const ui = await mountBand($, surface)
  const tree = await ui.drawn()
  await ui.unmount()
  return tree
}

type Cell = { ch: string; key: string } | { svg: Record<string, any> }

// The band as a stream in document order: one cell per character with its paint, one per Svg.
const streamOf = (tree: any): Cell[] =>
  leavesOf(tree).flatMap(leaf =>
    leaf.kind === 'svg'
      ? [{ svg: leaf.props }]
      : [...leaf.text].map(ch => ({ ch, key: `${ch} ${leaf.paint.color ?? ''} ${leaf.paint.dim ? 'dim' : ''}` })),
  )

const svgTextOf = (props: Record<string, any>) =>
  [...String(props.source ?? '').matchAll(/<text\b[^>]*>([^<]*)<\/text>/g)].map(([, text]) => text).join(' ')

const charOf = (cell: Cell) => ('svg' in cell ? ` ${svgTextOf(cell.svg)} ` : cell.ch)

// Everything the band says: its texts and any text inside its Svg drawings.
export const bandText = (tree: any) => streamOf(tree).map(charOf).join('')

export const svgCount = (tree: any) => streamOf(tree).filter(cell => 'svg' in cell).length

// A character that draws a cell of a terminal bar: not a letter, digit, space, % or a frame mark.
const isBarGlyph = (ch: string) => !/[\p{L}\p{N}\s%[\]|()]/u.test(ch)

const widthOf = (attrs: Record<string, string>, of: number) => {
  const raw = attrs.width ?? ''
  return raw.endsWith('%') ? (Number(raw.slice(0, -1)) / 100) * of : Number(raw)
}

// How full a desktop bar is, from its rects: a track and a fill over it, or one rect per cell.
const svgFill = (props: Record<string, any>): number => {
  const rects = shapesOf(String(props.source ?? ''), 'rect')
  if (rects.length === 0) return Number.NaN
  const track = Math.max(...rects.map(r => widthOf(r, Number(props.width ?? 100))))
  const widths = rects.map(r => widthOf(r, track))
  const isCells = rects.length >= 5 && widths.every(w => w === widths[0])
  if (isCells) return rects.filter(r => r.fill === rects[0]!.fill).length / rects.length
  const fills = widths.filter(w => w < track)
  return fills.length === 0 ? (rects.length > 1 ? 1 : 0) : Math.max(...fills) / track
}

export type Window = {
  // How many times the label is drawn.
  labels: number
  // The first percent drawn after the label, before the next label.
  percent: number | undefined
  // How full the bar is, 0 to 1: filled cells over all cells, or the fill over the track.
  fill: number
  // Cells of a terminal bar, each as glyph and paint; empty on the desktop.
  cells: string[]
  svgs: number
}

// What the band draws for one label: from the label to the next label, in document order.
export const windowOf = (tree: any, label: string): Window => {
  const stream = streamOf(tree)
  const text = stream.map(cell => ('svg' in cell ? '\u0000' : cell.ch)).join('')
  const starts = LABELS.map(one => text.indexOf(one)).filter(at => at >= 0)
  const at = text.indexOf(label)
  const labels = text.split(label).length - 1
  if (at < 0) return { labels, percent: undefined, fill: Number.NaN, cells: [], svgs: 0 }
  const end = Math.min(...starts.filter(one => one > at), stream.length)
  const block = stream.slice(at + label.length, end)
  const blockText = block.map(charOf).join('')
  const found = blockText.match(/(\d+(?:[.,]\d+)?)\s?%/)
  const svgs = block.filter((cell): cell is { svg: Record<string, any> } => 'svg' in cell)
  const cells = block.flatMap(cell => ('svg' in cell || !isBarGlyph(cell.ch) ? [] : [cell.key]))
  const fill =
    svgs.length > 0 ? svgFill(svgs[0]!.svg) : cells.length === 0 ? Number.NaN : cells.filter(key => key === cells[0]).length / cells.length
  return { labels, percent: found === null ? undefined : Number(found[1]!.replace(',', '.')), fill, cells, svgs: svgs.length }
}

// The cells before the first label: a bar drawn with no label of its own.
export const strayCells = (tree: any) => {
  const stream = streamOf(tree)
  const text = stream.map(cell => ('svg' in cell ? '\u0000' : cell.ch)).join('')
  const first = Math.min(...LABELS.map(one => text.indexOf(one)).filter(at => at >= 0), stream.length)
  return stream.slice(0, first).filter(cell => 'svg' in cell || isBarGlyph(cell.ch)).length
}
