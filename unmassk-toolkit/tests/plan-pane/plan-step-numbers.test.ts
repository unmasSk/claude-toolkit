// #98 D-161: every step row shows the step's number before its title («1.1 Tests del
// contrato»), the id the plan tool received; Bex names all work by number («#105, 1.2»).
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import { ISSUE_TASK, SURFACES, callPlan, drawnRows, isDoneStep, mountPane, rowIndex, startSession } from './plan-kit.ts'

const STEPS = ISSUE_TASK.phases.flatMap(phase => phase.steps)
const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
// The number, then only blank space, then the title.
const numbered = (id: string, title: string) => new RegExp(`(^|\\s)${escaped(id)}\\s+${escaped(title)}`)

for (const surface of SURFACES) {
  test(`should_show_each_step_number_before_its_title_done_running_and_pending_on_the_${surface}`, async ($, on) => {
    const { opens } = await startSession($, on)
    await callPlan($, { task: ISSUE_TASK })
    await callPlan($, { step: STEPS[0]!.id, status: 'done' })
    await callPlan($, { step: STEPS[1]!.id, status: 'in_progress' })

    const rows = await drawnRows(await mountPane($, opens[0]!.id, surface))
    const rowOfStep = (title: string) => rows[rowIndex(rows, title)] ?? ''

    expect(
      STEPS.filter(step => !numbered(step.id, step.title).test(rowOfStep(step.title))).map(step => rowOfStep(step.title)),
      `rows missing "<id> <title>": ${JSON.stringify(rows)}`,
    ).toEqual([])
    expect(isDoneStep(rowOfStep(STEPS[0]!.title)), `the circle still leads the done row: ${rowOfStep(STEPS[0]!.title)}`).toBe(true)
  })

  test(`should_show_a_number_id_the_tool_received_as_a_number_before_the_title_on_the_${surface}`, async ($, on) => {
    const { opens } = await startSession($, on)
    const task = { title: 'Investigar el arranque', issue: null, steps: [{ id: 1, title: 'Leer el informe' }, { id: 2, title: 'Reproducir el fallo' }] }
    await callPlan($, { task })

    const rows = await drawnRows(await mountPane($, opens[0]!.id, surface))

    expect(rows[rowIndex(rows, 'Leer el informe')], `1 before its title: ${JSON.stringify(rows)}`).toMatch(numbered('1', 'Leer el informe'))
    expect(rows[rowIndex(rows, 'Reproducir el fallo')], '2 before its title').toMatch(numbered('2', 'Reproducir el fallo'))
  })
}
