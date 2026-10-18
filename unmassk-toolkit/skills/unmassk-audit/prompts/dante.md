# Prompt Templates — Dante (Audit)

> Templates for the orchestrator. Fill in the fields in brackets. Audit tasks need no build mode.

---

## Template 1: Golden Tests (Step 3)

```markdown
## Task: Golden tests for [FILE] — 97%+ coverage

TASK: write characterization tests that capture the current behaviour of `[MODULE_PATH]/[FILE]` (issue #[N]), at 97%+ coverage with real assertions.
KNOWN:
- Existing tests: [TEST_FILE or "none"]
- Exports to cover (from the step 1 scan): `exportA()`, `exportB()`
- Imports from: `[module1]`, `[module2]`. Consumed by: `[module3]`.
- Style and structure model, tests approved by Yoda: `[REFERENCE_MODULE_PATH]/[reference_test]` (test directory per project convention)
CROSS-CHECK: this KNOWN block is a starting point, not a substitute. If the task touches anything present in your memory index or in the project's memory, verify it in pairs before acting: your own memory, the real code, and `gitmem search` — even if KNOWN already tells you the answer.
LIMITS: touch only your test file(s): [EXACT LIST]. Never edit source code. No commits; no git stash/reset/checkout/restore.
VERIFY:
1. `[TEST_CMD]` scoped to `[MODULE_PATH]/[TEST_FILE]`, with coverage.
2. If under 97%: list the uncovered branches.
3. `[TEST_CMD]` scoped to `[MODULE_PATH]`.
4. Run TWICE.
Tag claims EXECUTED/READ/UNVERIFIED.

Write your report file. Answer in three lines: status, what to act on, report path.

Do the task yourself or report back — never spawn agents of your own. Never end your turn waiting on background work — read the result and deliver the report. If the task grows past its point, finish the coherent part, report, and wait.
```

---

## Template 2: Adversarial Tests (Step 9)

```markdown
## Task: Adversarial tests for [MODULE] from Moriarty's report

TASK: write a regression test for every confirmed break and a confirmation test for every attack the module withstood, in `[MODULE_PATH]`, issue #[N].
KNOWN:
- Moriarty's report: [MORIARTY_REPORT_PATH] — read its confirmed breaks, the attacks that held, and `Surviving mutants`.
- If it lists surviving mutants: re-apply each on a scratchpad copy and show each new test red. Report "survivors re-applied: K/K killed".
CROSS-CHECK: this KNOWN block is a starting point, not a substitute. If the task touches anything present in your memory index or in the project's memory, verify it in pairs before acting: your own memory, the real code, and `gitmem search` — even if KNOWN already tells you the answer.
LIMITS: touch only `[MODULE_PATH]/[test dir]/[MODULE].adversarial.test` (extension and test-dir convention per project). Never edit source code. No commits; no git stash/reset/checkout/restore.
VERIFY:
1. `[TEST_CMD]` scoped to the new adversarial test file.
2. `[TEST_CMD]` scoped to `[MODULE_PATH]`.
3. Run TWICE.
Tag claims EXECUTED/READ/UNVERIFIED.

Write your report file. Answer in three lines: status, what to act on, report path.

Do the task yourself or report back — never spawn agents of your own. Never end your turn waiting on background work — read the result and deliver the report. If the task grows past its point, finish the coherent part, report, and wait.
```

---

## Template 3: Broken Tests (Step 2)

```markdown
## Task: Fix the broken tests of module [MODULE]

TASK: make the broken tests Bilbo reported pass again, in `[MODULE_PATH]`, issue #[N]. A test that fails because the source is wrong stays failing: report it as a source blocker for Ultron.
KNOWN:
- Bilbo's report: [BILBO_REPORT_PATH] — the broken tests and their error output are under `Confirmed findings`.
CROSS-CHECK: this KNOWN block is a starting point, not a substitute. If the task touches anything present in your memory index or in the project's memory, verify it in pairs before acting: your own memory, the real code, and `gitmem search` — even if KNOWN already tells you the answer.
LIMITS: touch only these test files: [EXACT LIST]. Never edit source code. No commits; no git stash/reset/checkout/restore.
VERIFY: `[TEST_CMD]` scoped to `[MODULE_PATH]`, run TWICE. Tag claims EXECUTED/READ/UNVERIFIED.

Write your report file. Answer in three lines: status, what to act on, report path.

Do the task yourself or report back — never spawn agents of your own. Never end your turn waiting on background work — read the result and deliver the report. If the task grows past its point, finish the coherent part, report, and wait.
```
