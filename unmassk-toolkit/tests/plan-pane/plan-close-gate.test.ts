// #98 D-156: while the pane's task has steps not done, a Bash call that closes work
// (gh issue close, bin/release.py without --dry-run, gitmem next) is refused naming
// the pending steps; with no task, a finished task or any other command it passes.
// Run: claude plugin test unmassk-toolkit
import { test, expect } from 'claude-code/testing'
import { ISSUE_TASK, PLAN_STATE, callPlan, startSession } from './plan-kit.ts'

const bash = ($: any, command: string) => $.tool.call({ tool: 'Bash', command })

// The commands as the orchestrator types them in a session.
const CLOSING = [
  { name: 'gh_issue_close', command: 'gh issue close 98 --comment "done"' },
  { name: 'a_release', command: 'python3 bin/release.py unmassk-toolkit 1.53.0' },
  { name: 'gitmem_next', command: 'gitmem next "#98 phase 5: the close gate"' },
  { name: 'gh_issue_close_chained_after_a_push', command: 'git push && gh issue close 98' },
  { name: 'gh_issue_close_after_a_semicolon', command: 'git status --short; gh issue close 98' },
  { name: 'gitmem_next_after_a_cd', command: 'cd unmassk-toolkit && gitmem next "#98 phase 5: the close gate"' },
  {
    name: 'a_release_after_a_cd',
    command: 'cd /Users/unmassk/Workspace/claude-toolkit && python3 bin/release.py unmassk-toolkit 1.53.0',
  },
]

const PASSING = [
  { name: 'a_release_dry_run', command: 'python3 bin/release.py unmassk-toolkit 1.53.0 --dry-run' },
  { name: 'gh_issue_view', command: 'gh issue view 98' },
  { name: 'git_status', command: 'git status --short' },
  // Commands that only mention a closing command close nothing (Cerberus F1).
  { name: 'git_add_of_the_release_script', command: 'git add bin/release.py' },
  { name: 'git_diff_of_the_release_script', command: 'git diff bin/release.py' },
  { name: 'a_grep_for_gitmem_next', command: 'grep -rn "gitmem next" unmassk-toolkit/skills' },
  { name: 'a_commit_naming_gitmem_next', command: 'git commit -m "docs: explain gitmem next"' },
  { name: 'a_memory_search_quoting_gh_issue_close', command: 'gitmem search "gh issue close"' },
]

const [DONE, STARTED, UNTOUCHED] = ISSUE_TASK.phases.flatMap(phase => phase.steps)

// One step done, one in progress, one never started.
const startHalfDone = async ($: any) => {
  await callPlan($, { task: ISSUE_TASK })
  await callPlan($, { step: DONE.id, status: 'done' })
  await callPlan($, { step: STARTED.id, status: 'in_progress' })
}

const finishAll = async ($: any) => {
  await callPlan($, { task: ISSUE_TASK })
  for (const step of [DONE, STARTED, UNTOUCHED]) await callPlan($, { step: step.id, status: 'done' })
}

// A step is named by its id or its title.
const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const naming = (step: { id: string; title: string }) => new RegExp(`${escaped(step.id)}|${escaped(step.title)}`)

for (const closing of CLOSING) {
  test(`should_refuse_${closing.name}_naming_the_pending_steps_when_the_task_has_steps_not_done`, async ($, on) => {
    const { fellThrough } = await startSession($, on)
    await startHalfDone($)

    const answer = await bash($, closing.command)

    expect(answer.deny, `refused: ${JSON.stringify(answer)}`).toEqual(expect.any(String))
    expect(answer.deny, 'it is the gate refusing, not the bottom').not.toContain('reached the bottom')
    expect(fellThrough, 'the closing command never ran').toEqual([])
    expect(answer.deny, 'names the step in progress').toMatch(naming(STARTED))
    expect(answer.deny, 'names the step never started').toMatch(naming(UNTOUCHED))
    expect(answer.deny, 'does not name the step already done').not.toContain(DONE.title)
  })
}

// A command that passes reaches the bottom exactly as sent; the bottom's answer comes back.
const expectPassedUntouched = (answer: any, fellThrough: any[], command: string) => {
  expect(fellThrough.map(e => [e.tool, e.command]), 'reached the bottom unchanged, once').toEqual([['Bash', command]])
  expect(answer.deny, `the bottom's own answer: ${JSON.stringify(answer)}`).toContain('reached the bottom')
}

for (const passing of PASSING) {
  test(`should_pass_${passing.name}_untouched_when_the_task_has_steps_not_done`, async ($, on) => {
    const { fellThrough } = await startSession($, on)
    await startHalfDone($)

    const answer = await bash($, passing.command)

    expectPassedUntouched(answer, fellThrough, passing.command)
  })
}

for (const closing of CLOSING) {
  test(`should_pass_${closing.name}_untouched_when_there_is_no_task`, async ($, on) => {
    const { fellThrough } = await startSession($, on)

    const answer = await bash($, closing.command)

    expectPassedUntouched(answer, fellThrough, closing.command)
  })

  test(`should_pass_${closing.name}_untouched_when_every_step_is_done`, async ($, on) => {
    const { fellThrough } = await startSession($, on)
    await finishAll($)

    const answer = await bash($, closing.command)

    expectPassedUntouched(answer, fellThrough, closing.command)
  })
}

test('should_refuse_closing_again_once_a_new_task_replaces_a_finished_one', async ($, on) => {
  const { fellThrough } = await startSession($, on)
  await finishAll($)
  const next = { title: 'Next task', issue: null, steps: [{ id: 'n1', title: 'Fresh pending step' }] }
  await callPlan($, { task: next })

  const answer = await bash($, 'gh issue close 99')

  expect(answer.deny, `refused: ${JSON.stringify(answer)}`).toEqual(expect.any(String))
  expect(answer.deny, 'names the new task pending step').toMatch(naming(next.steps[0]))
  expect(fellThrough, 'the closing command never ran').toEqual([])
})

// The plan cannot be read: a closing command is refused, never run unjudged; any other passes.
const startWithBrokenPlanRead = async ($: any, on: any) => {
  const store = { isBroken: false }
  on('state.get', PLAN_STATE, async (_$: unknown, e: any, next: any) =>
    store.isBroken ? { deny: 'disk unreadable' } : next(e),
  )
  const { fellThrough } = await startSession($, on)
  await startHalfDone($)
  store.isBroken = true
  return { fellThrough }
}

test('should_refuse_a_closing_command_saying_the_check_failed_when_the_plan_cannot_be_read', async ($, on) => {
  const { fellThrough } = await startWithBrokenPlanRead($, on)

  const answer = await bash($, 'gh issue close 98')

  expect(answer.deny, `refused: ${JSON.stringify(answer)}`).toEqual(expect.any(String))
  expect(answer.deny, 'it is the gate refusing, not the bottom').not.toContain('reached the bottom')
  expect(fellThrough, 'the closing command never ran').toEqual([])
  expect(answer.deny, 'says the check failed').toMatch(/fail/i)
  expect(answer.deny, 'does not claim steps it could not read').not.toMatch(naming(STARTED))
})

test('should_pass_a_non_closing_command_untouched_when_the_plan_cannot_be_read', async ($, on) => {
  const { fellThrough } = await startWithBrokenPlanRead($, on)

  const answer = await bash($, 'git status --short')

  expectPassedUntouched(answer, fellThrough, 'git status --short')
})
