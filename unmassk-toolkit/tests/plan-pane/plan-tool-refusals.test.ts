// #98 fix pass: every bad plan-tool call reaches the model as a refusal and leaves
// the pane as it was; step ids match lowercased and without accents (owner's rule).
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import {
  ISSUE_TASK,
  TICK,
  callPlan,
  drawnRows,
  mountPane,
  rowIndex,
  startSession,
} from './plan-kit.ts'

const BROKEN = 'Broken task'
const STEPS = [
  { id: '1', title: 'First step' },
  { id: '2', title: 'Second step' },
]

const REPEATED_IDS = [
  { name: 'two_steps_with_the_same_id', steps: [{ id: '7', title: 'One' }, { id: '7', title: 'Two' }], names: '7' },
  {
    name: 'two_step_ids_that_differ_only_in_case_and_accents',
    steps: [{ id: 'Á.1', title: 'One' }, { id: 'a.1', title: 'Two' }],
    names: 'a.1',
  },
]

// Every call the tool must refuse.
const BAD_CALLS: { name: string; input: Record<string, unknown> }[] = [
  { name: 'a_task_with_no_title', input: { task: { issue: 98, steps: STEPS } } },
  { name: 'a_task_with_a_blank_title', input: { task: { title: '   ', issue: null, steps: STEPS } } },
  { name: 'an_issue_that_is_text', input: { task: { title: BROKEN, issue: '98', steps: STEPS } } },
  { name: 'an_issue_that_is_not_whole', input: { task: { title: BROKEN, issue: 9.5, steps: STEPS } } },
  { name: 'an_empty_phase_list', input: { task: { title: BROKEN, issue: null, phases: [] } } },
  { name: 'a_task_with_neither_phases_nor_steps', input: { task: { title: BROKEN, issue: null } } },
  { name: 'an_empty_step_list', input: { task: { title: BROKEN, issue: null, steps: [] } } },
  { name: 'a_phase_with_no_title', input: { task: { title: BROKEN, issue: null, phases: [{ steps: STEPS }] } } },
  { name: 'a_phase_with_no_steps', input: { task: { title: BROKEN, issue: null, phases: [{ title: 'Empty phase', steps: [] }] } } },
  { name: 'a_step_with_no_id', input: { task: { title: BROKEN, issue: null, steps: [{ title: 'No id' }] } } },
  { name: 'a_step_with_no_title', input: { task: { title: BROKEN, issue: null, steps: [{ id: '1' }] } } },
  ...REPEATED_IDS.map(({ name, steps }) => ({ name, input: { task: { title: BROKEN, issue: null, steps } } })),
  { name: 'both_a_task_and_a_step', input: { task: { title: BROKEN, issue: null, steps: STEPS }, step: '2.1', status: 'done' } },
  { name: 'neither_a_task_nor_a_step', input: { status: 'done' } },
  { name: 'a_status_outside_the_two_allowed', input: { step: '2.1', status: 'finished' } },
  { name: 'a_status_change_with_no_step_id', input: { step: '', status: 'done' } },
]

for (const bad of BAD_CALLS) {
  test(`should_refuse_${bad.name}_and_leave_the_pane_as_it_was`, async ($, on) => {
    const { opens, fellThrough } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    const ui = await mountPane($, opens[0]!.id, 'desktop')
    const before = await drawnRows(ui)

    const answer = await callPlan($, bad.input)

    const after = await drawnRows(ui)
    expect(answer.deny, `refused: ${JSON.stringify(answer)}`).toEqual(expect.any(String))
    expect(answer.deny, 'it is the plan tool refusing, not the bottom').not.toContain('reached the bottom')
    expect(fellThrough, 'the call never fell through to the bottom').toEqual([])
    expect(after, 'the pane is unchanged').toEqual(before)
    expect(rowIndex(after, BROKEN), 'the refused task is not drawn').toBe(-1)
  })
}

for (const repeated of REPEATED_IDS) {
  test(`should_name_the_repeated_id_when_refusing_${repeated.name}`, async ($, on) => {
    await startSession($, on)

    const answer = await callPlan($, { task: { title: BROKEN, issue: null, steps: repeated.steps } })

    expect(answer.deny, 'the refusal names the step id the model must fix').toContain(repeated.names)
  })
}

test('should_tick_a_step_when_its_id_differs_from_the_sent_one_only_in_case_and_accents', async ($, on) => {
  const { opens } = await startSession($, on)
  const task = {
    title: 'Pasos con acentos',
    issue: null,
    steps: [
      { id: 'Á.1', title: 'Paso con acento' },
      { id: 'b.2', title: 'Paso sin acento' },
    ],
  }
  await callPlan($, { task })

  const first = await callPlan($, { step: 'a.1', status: 'done' })
  const second = await callPlan($, { step: 'B.2', status: 'in_progress' })

  expect([first.deny, second.deny], 'both lookups found their step').toEqual([undefined, undefined])
  const rows = await drawnRows(await mountPane($, opens[0]!.id, 'desktop'))
  expect(rows[rowIndex(rows, task.steps[0].title)], `Á.1 ticked by a.1: ${JSON.stringify(rows)}`).toContain(TICK)
  expect(rows[rowIndex(rows, task.steps[1].title)], 'B.2 started b.2, not ticked it').not.toContain(TICK)
})

test('should_refuse_the_call_and_not_answer_ok_when_the_plan_cannot_be_written', async ($, on) => {
  // The write beneath the plugin refuses once the session is up: the tool must fail loud.
  const store = { isBroken: false }
  on('state.set', async (_$: unknown, e: any, next: any) => (store.isBroken ? { deny: 'disk full' } : next(e)))
  const { fellThrough } = await startSession($, on)
  store.isBroken = true

  const answer = await callPlan($, { task: ISSUE_TASK })

  expect(answer.deny, `refused: ${JSON.stringify(answer)}`).toEqual(expect.any(String))
  expect(answer.result, 'never a silent ok').toBeUndefined()
  expect(answer.deny, 'it is the plan tool refusing, not the bottom').not.toContain('reached the bottom')
  expect(fellThrough, 'the call never fell through to the bottom').toEqual([])
})
