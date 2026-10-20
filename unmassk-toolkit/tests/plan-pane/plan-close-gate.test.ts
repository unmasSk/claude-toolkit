// #98 D-156, corrected by D-163: a Bash call that closes work (gh issue close,
// bin/release.py without --dry-run, gitmem next) is refused, naming them, while the pane's
// task has steps not done BEFORE the step in progress; that step and every one after it do
// not count. With no step in progress every step not done counts. With no task, a finished
// task or any other command it passes.
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

const [FIRST, SECOND, THIRD] = ISSUE_TASK.phases.flatMap(phase => phase.steps)

const setSteps = async ($: any, task: any, statuses: string[][]) => {
  await callPlan($, { task })
  for (const [step, status] of statuses) await callPlan($, { step, status })
}

// D-163's own case: the step before is done, the one in progress is the closing act, one after waits.
const startMidway = ($: any) =>
  setSteps($, ISSUE_TASK, [
    [FIRST.id, 'done'],
    [SECOND.id, 'in_progress'],
  ])

// A step before the one in progress was never done.
const startWithAnEarlierStepUndone = ($: any) => setSteps($, ISSUE_TASK, [[SECOND.id, 'in_progress']])

// No step in progress: every step not done counts, as before D-163.
const startWithNothingInProgress = ($: any) => setSteps($, ISSUE_TASK, [[FIRST.id, 'done']])

const finishAll = ($: any) =>
  setSteps(
    $,
    ISSUE_TASK,
    [FIRST, SECOND, THIRD].map(step => [step.id, 'done']),
  )

// A step is named by its id or its title.
const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const naming = (step: { id: string; title: string }) => new RegExp(`${escaped(step.id)}|${escaped(step.title)}`)

const expectRefused = (answer: any, fellThrough: any[]) => {
  expect(answer.deny, `refused: ${JSON.stringify(answer)}`).toEqual(expect.any(String))
  expect(answer.deny, 'it is the gate refusing, not the bottom').not.toContain('reached the bottom')
  expect(fellThrough, 'the closing command never ran').toEqual([])
}

// A command that passes reaches the bottom exactly as sent; the bottom's answer comes back.
const expectPassedUntouched = (answer: any, fellThrough: any[], command: string) => {
  expect(fellThrough.map(e => [e.tool, e.command]), 'reached the bottom unchanged, once').toEqual([['Bash', command]])
  expect(answer.deny, `the bottom's own answer: ${JSON.stringify(answer)}`).toContain('reached the bottom')
}

for (const closing of CLOSING) {
  test(`should_refuse_${closing.name}_naming_only_the_earlier_step_when_a_step_before_the_one_in_progress_is_not_done`, async ($, on) => {
    const { fellThrough } = await startSession($, on)
    await startWithAnEarlierStepUndone($)

    const answer = await bash($, closing.command)

    expectRefused(answer, fellThrough)
    expect(answer.deny, 'names the earlier step not done').toMatch(naming(FIRST))
    expect(answer.deny, 'does not name the step in progress').not.toContain(SECOND.title)
    expect(answer.deny, 'does not name the step after it').not.toContain(THIRD.title)
  })

  test(`should_refuse_${closing.name}_naming_every_step_not_done_when_no_step_is_in_progress`, async ($, on) => {
    const { fellThrough } = await startSession($, on)
    await startWithNothingInProgress($)

    const answer = await bash($, closing.command)

    expectRefused(answer, fellThrough)
    expect(answer.deny, 'names the second step').toMatch(naming(SECOND))
    expect(answer.deny, 'names the third step').toMatch(naming(THIRD))
    expect(answer.deny, 'does not name the step already done').not.toContain(FIRST.title)
  })

  test(`should_pass_${closing.name}_untouched_when_every_step_before_the_one_in_progress_is_done`, async ($, on) => {
    const { fellThrough } = await startSession($, on)
    await startMidway($)

    const answer = await bash($, closing.command)

    expectPassedUntouched(answer, fellThrough, closing.command)
  })

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

// Non-closing commands pass even in the state where a closing one is refused.
for (const passing of PASSING) {
  test(`should_pass_${passing.name}_untouched_when_a_step_before_the_one_in_progress_is_not_done`, async ($, on) => {
    const { fellThrough } = await startSession($, on)
    await startWithAnEarlierStepUndone($)

    const answer = await bash($, passing.command)

    expectPassedUntouched(answer, fellThrough, passing.command)
  })
}

// A release run as a plan: publishing is itself a step; CI and the install come after it.
const RELEASE_TASK = {
  title: 'Release',
  issue: null,
  steps: [
    { id: 'r1', title: 'Bump the version' },
    { id: 'r2', title: 'Publicar' },
    { id: 'r3', title: 'Watch CI' },
    { id: 'r4', title: 'Install the new version' },
  ],
}
const [BUMP, PUBLISH, CI, INSTALL] = RELEASE_TASK.steps
const RELEASE = 'python3 bin/release.py unmassk-toolkit 1.54.0'

test('should_pass_the_release_while_publishing_is_in_progress_and_ci_and_install_wait', async ($, on) => {
  const { fellThrough } = await startSession($, on)
  await setSteps($, RELEASE_TASK, [
    [BUMP.id, 'done'],
    [PUBLISH.id, 'in_progress'],
  ])

  const answer = await bash($, RELEASE)

  expectPassedUntouched(answer, fellThrough, RELEASE)
})

test('should_refuse_the_release_naming_step_1_when_it_is_not_done_and_publishing_is_in_progress', async ($, on) => {
  const { fellThrough } = await startSession($, on)
  await setSteps($, RELEASE_TASK, [[PUBLISH.id, 'in_progress']])

  const answer = await bash($, RELEASE)

  expectRefused(answer, fellThrough)
  expect(answer.deny, 'names step 1').toMatch(naming(BUMP))
  expect(answer.deny, 'does not name the step in progress').not.toContain(PUBLISH.title)
  expect(answer.deny, 'does not name CI').not.toContain(CI.title)
  expect(answer.deny, 'does not name the install').not.toContain(INSTALL.title)
})

test('should_refuse_the_release_naming_every_earlier_step_not_done_not_only_the_one_just_before', async ($, on) => {
  const { fellThrough } = await startSession($, on)
  await setSteps($, RELEASE_TASK, [[CI.id, 'in_progress']])

  const answer = await bash($, RELEASE)

  expectRefused(answer, fellThrough)
  expect(answer.deny, 'names step 1').toMatch(naming(BUMP))
  expect(answer.deny, 'names step 2').toMatch(naming(PUBLISH))
  expect(answer.deny, 'does not name the step in progress').not.toContain(CI.title)
  expect(answer.deny, 'does not name the step after it').not.toContain(INSTALL.title)
})

test('should_pass_the_release_when_the_first_step_is_in_progress_and_every_other_waits', async ($, on) => {
  const { fellThrough } = await startSession($, on)
  await setSteps($, RELEASE_TASK, [[BUMP.id, 'in_progress']])

  const answer = await bash($, RELEASE)

  expectPassedUntouched(answer, fellThrough, RELEASE)
})

// "Before" runs in plan order across phases: an earlier phase's step not done still counts.
test('should_refuse_a_closing_command_naming_an_earlier_phase_step_when_the_step_in_progress_opens_the_next_phase', async ($, on) => {
  const { fellThrough } = await startSession($, on)
  await setSteps($, ISSUE_TASK, [
    [FIRST.id, 'done'],
    [THIRD.id, 'in_progress'],
  ])

  const answer = await bash($, 'gh issue close 98')

  expectRefused(answer, fellThrough)
  expect(answer.deny, 'names the earlier phase step').toMatch(naming(SECOND))
  expect(answer.deny, 'does not name the step in progress').not.toContain(THIRD.title)
  expect(answer.deny, 'does not name the step already done').not.toContain(FIRST.title)
})

test('should_pass_a_closing_command_when_the_last_step_is_in_progress_and_every_earlier_one_is_done', async ($, on) => {
  const { fellThrough } = await startSession($, on)
  await setSteps($, ISSUE_TASK, [
    [FIRST.id, 'done'],
    [SECOND.id, 'done'],
    [THIRD.id, 'in_progress'],
  ])

  const answer = await bash($, 'gh issue close 98')

  expectPassedUntouched(answer, fellThrough, 'gh issue close 98')
})

test('should_refuse_closing_again_once_a_new_task_replaces_a_finished_one', async ($, on) => {
  const { fellThrough } = await startSession($, on)
  await finishAll($)
  const next = { title: 'Next task', issue: null, steps: [{ id: 'n1', title: 'Fresh pending step' }] }
  await callPlan($, { task: next })

  const answer = await bash($, 'gh issue close 99')

  expectRefused(answer, fellThrough)
  expect(answer.deny, 'names the new task pending step').toMatch(naming(next.steps[0]))
})

// The plan cannot be read: a closing command is refused, never run unjudged; any other passes.
const startWithBrokenPlanRead = async ($: any, on: any) => {
  const store = { isBroken: false }
  on('state.get', PLAN_STATE, async (_$: unknown, e: any, next: any) =>
    store.isBroken ? { deny: 'disk unreadable' } : next(e),
  )
  const { fellThrough } = await startSession($, on)
  await startWithAnEarlierStepUndone($)
  store.isBroken = true
  return { fellThrough }
}

test('should_refuse_a_closing_command_saying_the_check_failed_when_the_plan_cannot_be_read', async ($, on) => {
  const { fellThrough } = await startWithBrokenPlanRead($, on)

  const answer = await bash($, 'gh issue close 98')

  expectRefused(answer, fellThrough)
  expect(answer.deny, 'says the check failed').toMatch(/fail/i)
  expect(answer.deny, 'does not claim steps it could not read').not.toContain(FIRST.title)
})

test('should_pass_a_non_closing_command_untouched_when_the_plan_cannot_be_read', async ($, on) => {
  const { fellThrough } = await startWithBrokenPlanRead($, on)

  const answer = await bash($, 'git status --short')

  expectPassedUntouched(answer, fellThrough, 'git status --short')
})
