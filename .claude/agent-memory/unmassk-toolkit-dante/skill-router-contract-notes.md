---
name: skill-router-contract-notes
description: Contract notes for the per-message protocol-skill router feature in user-prompt-memory-check.py (test-first, written before Ultron implemented anything)
metadata:
  type: project
---

An 11-agent council (2026-07) found the toolkit's 7 non-forced protocol skills
(unmassk-flow, unmassk-grill, unmassk-council, unmassk-project-lifecycle,
unmassk-audit, unmassk-close-session, unmassk-flow-stack) get selected
unreliably — pure natural-language judgement, zero mechanical backing.
Accepted fix: extend `unmassk-toolkit/hooks/user-prompt-memory-check.py` (the
`UserPromptSubmit` hook) to run a lightweight keyword/trigger-phrase check
against all 9 protocol skills (including unmassk-core/unmassk-gitmemory) on
EVERY message, not just the first, and append an informational nudge line —
never a blocking mechanism (exit code must always be 0). Deliberately NOT a
BM25 rebuild, NOT a hard PreToolUse gate (a similar hard gate was already
tried and rejected elsewhere in this codebase for token cost).

Contract tests (test-first pass, written before Ultron implemented anything):
`unmassk-toolkit/tests/test_user_prompt_skill_router.py`.

**Why this matters:** the exact nudge wording was left to Ultron by the task,
but the marker convention was NOT left open — Dante locked it to
`"[skill-router]"` as the bracket-label, matching this hook's existing
convention (`[git-memory-boot]`, `[git-memory]`, `[memoria relevante...]`,
`[memory-check]`). Tests assert marker presence + skill name in the same
labeled block, not full sentence wording. If Ultron implements a different
marker string, either update the tests's `SKILL_ROUTER_MARKER` constant (one
line) after confirming the new name still matches the bracket-label
convention, or push back — don't let the marker silently drift to something
inconsistent with the rest of the hook's output.

**How to apply (hardening pass, after Ultron implements):** run the full
EXHAUSTION PROTOCOL against the real matching implementation this time —
map every skill's actual keyword/regex list from the code (not from the
description text used to seed the acceptance prompts), and add edge cases
the acceptance pass deliberately skipped: case sensitivity, partial-word
false positives (e.g. does "planet" false-trigger on "plan"?), Unicode/accent
handling for Spanish-language prompts (this user writes in Spanish per
CLAUDE.md), and prompts that match all 9 skills at once (dense-collision
case) — the acceptance pass only covers a 2-skill collision
(`unmassk-flow` + `unmassk-council`). Also worth adding then: a test that the
matching implementation is genuinely cheap (e.g. a rough runtime ceiling),
since the council explicitly rejected a heavy BM25 rebuild for this — the
acceptance pass intentionally does NOT test performance directly per the
task's own instruction.

**unmassk-core has no quoted trigger phrases in its description** (it's
"Loaded on session boot", not phrase-triggered) — its 3 acceptance prompts
were built from distinctive nouns/verbs instead ("agents", "delegate",
"invoke workflows", "domain plugins", "standards"). Worth flagging to
Ultron/Yoda: this may mean unmassk-core's trigger list needs deliberate
design (not literal-extraction) more than the other 8 skills — a design
call, not a testing one.

## Drift-guard hardening (2026-07) — frontmatter edited after Ultron built the dict

The orchestrator later edited 4 SKILL.md frontmatter `description` fields
directly (grill, council, flow, flow-stack) to resolve real trigger-phrase
collisions an 11-agent council found (2 skills claiming the same phrase).
This silently staled 4 entries in `SKILL_TRIGGER_PHRASES`
(`unmassk-toolkit/hooks/user-prompt-memory-check.py`): "stress-test this
plan" (grill), "let's brainstorm" (council), "create something new" (flow),
"create new project" (flow-stack) — none of these appear in the live
descriptions anymore.

**Why this matters:** a hand-built trigger dict sourced from frontmatter text
at one point in time has no mechanism to notice later frontmatter edits.
Added a permanent (not contract-pass, stays forever) parametrized test class
`TestSkillTriggerPhrasesMatchLiveDescriptions` in
`test_user_prompt_skill_router.py` that imports the hook's *live*
`SKILL_TRIGGER_PHRASES` dict (via `importlib.util.spec_from_file_location`,
per this repo's hyphenated-hook-import convention) and asserts every phrase
is a substring of its own skill's *live* SKILL.md description (parsed with
`yaml.safe_load` on the frontmatter block — handles both plain single-line
and folded `>` multi-line descriptions identically). Confirmed RED for
exactly those 4 pairs, GREEN for the other ~44 — this is the reusable
pattern for catching frontmatter/hook drift generically, not just this once.

**How to apply:** when any SKILL.md description changes in the future, this
test class catches it automatically — no test-file edit needed, since it
reads the dict and the description fresh every run. Only fails if a human
(Ultron) needs to reconcile `SKILL_TRIGGER_PHRASES` itself; that reconciliation
is implementation, not testing — stays out of Dante's scope.

Also updated 3 of the original 27 acceptance prompts in
`SKILL_TRIGGER_PROMPTS` that were built on the now-removed quoted phrasing:
grill's middle prompt (was "stress-test this plan" → now built on the literal
substring "the request is ambiguous"), council's third prompt (was "let's
brainstorm" → now "council this", still quoted in the live description), and
flow-stack's third prompt (was "create new project" → now "which stack",
still quoted in the live description). 2 of these 3 replacements went RED
too (grill's and flow-stack's — their new phrases aren't in the stale dict
yet either), which is correct: they assert the desired end state, not today's
buggy behavior. flow's own 3 acceptance prompts never referenced "create
something new" literally, so none needed changing there — only the hook's
dict (not any test) is stale for flow.

**Known adjacent staleness NOT fixed here (out of this task's scope):**
`unmassk-toolkit/tests/test_managed_blocks.py` (lines ~110-156) also hardcodes
comments/trigger_phrases tuples citing "create something new" and "create new
project" as SKILL.md source-of-truth text. Its actual assertions use looser
substrings ("non-trivial", "new project" as prefix-of-"new projects") that
still happen to pass today, but the comments are stale and worth a pass if
that file is touched next.

## Performance refactor (2026-07-04) — subprocess spawn was the actual cost

`test_user_prompt_skill_router.py` had grown to 85 tests taking 4+ minutes,
causing Bex real hangs (manual background/kill of test runs). Root cause was
NOT the drift-guard class (already fast, in-process) — it was ~31 of the
original 85 tests (27 acceptance-phrase + 1 multi-match + 3 no-match) calling
`_make_installed_repo(tmp_path)` (real `git init`) + `_run_hook()` (fresh
`python3` subprocess) just to check pure string matching, when the matching
logic (`lib/skill_router.py::match_skills()`) has zero dependency on git or
the hook process. Fix: those 31 tests now call `match_skills()` directly,
in-process, no fixture at all — same prompts/expected skills, same
assertions in substance. Kept only 6 true subprocess tests total: 3 in a new
`TestSkillRouterHookIntegration` (verifies the HOOK wires `match_skills()`
into stdout: marker+skill-name present on match, marker absent on no-match,
rc==0 even with a dense multi-skill match) + the pre-existing 3 in
`TestFirstMessageForcingTextUnaffected` (untouched — tests `.session-booted`
flag interaction, genuinely needs the real hook process). Result: same 85
tests, same coverage, runtime dropped from 4+ min to ~0.7s. Full suite
(`unmassk-toolkit/tests`) still 697 passed in ~5:18 afterward — no
regression elsewhere.

**Reusable pattern:** when a test file is slow, check whether tests calling
a subprocess/fixture-heavy hook are actually testing pure logic that already
lives in an importable module one layer down. If so, test the pure function
directly and reserve subprocess/fixture tests for the small number of cases
that genuinely test wiring (does the hook call the function and surface its
result correctly) or process-level state (flag files, env, exit codes tied
to real script execution) that the pure function can't exercise on its own.
Don't conflate "we need N tests for N acceptance prompts" with "each of
those N tests needs the expensive fixture" — the fixture only needs to be
exercised enough times to prove the wiring holds, not once per prompt.

## Skill rename `unmassk-flow-stack` → `unmassk-scaffolding` (2026-07-12)

Ultron renamed the skill (code + `lib/skill_router.py` dict key + `lib/managed_blocks.py`
generator) in an earlier commit; this session's task was only the two test
files following that rename (no code changes, no git-memory ops). Updated:
`test_managed_blocks.py` (`test_protocols_block_includes_flow_stack_skill` →
`..._scaffolding_skill`, assert string) and `test_user_prompt_skill_router.py`
(dict key in `SKILL_TRIGGER_PROMPTS`, module docstring's 7-skill list, the
drift-guard docstring's "EXPECTED STATE TODAY" narrative, and the
`_read_skill_description` docstring's folded-scalar skill list) — all
occurrences of the literal string `unmassk-flow-stack` are gone from both
files (`git grep` confirmed empty). This also resolves the "Known adjacent
staleness NOT fixed here" note above for `test_managed_blocks.py` — that file
was touched as part of this rename, so its stale flow-stack comment no longer
exists (it's the renamed `test_protocols_block_includes_scaffolding_skill`
now). If any other reference to `unmassk-flow-stack` surfaces later (e.g. in
`references/`, other skill docs, or agent-memory files outside Dante's own),
treat it as a leftover from this rename, not a new skill.

## Skill retirement `unmassk-gitmemory` (2026-08-02) — remove-with-breadcrumb, not three-state

`docs/memoria-v2/PLAN-CONSTRUCCION.md` §5.1 retired `skills/unmassk-gitmemory/`
entirely (deliberate, owner-approved — v1 memory system rebuilt from zero,
verified before touching anything). Same-day production changes (not mine —
already done when this task arrived): `lib/skill_router.py::SKILL_TRIGGER_PHRASES`
dropped to 8 keys (no `unmassk-gitmemory`), and `hooks/user-prompt-memory-check.py`'s
first-message MANDATORY block no longer forces `skill="unmassk-gitmemory"` or
mentions `CALIBRATION.md` — only `skill="unmassk-core"` remains. This left 4
tests red in `test_user_prompt_skill_router.py`: 3 parametrized cases
(`unmassk-gitmemory__0/1/2` in `TestSkillRouterMatchesRealTriggerPhrases`, from
a hand-written `SKILL_TRIGGER_PROMPTS["unmassk-gitmemory"]` entry never sourced
from production) + `test_first_message_forcing_text_present_regardless_of_prompt`
(asserted `skill="unmassk-gitmemory"` and `CALIBRATION.md` literally in stdout).

**Chose remove + docstring breadcrumb over PIEZAS.md §6.1's three-state
(verified/pending/roto) pattern.** The three-state pattern fits an
in-progress *construction* sequence: a test iterating a declared structure
(FIELDS→readers) where "module not written yet" is expected and counted
toward a same-build acceptance gate that reaches zero as steps complete. This
is the opposite shape — a *retirement* whose replacement is a separate,
not-yet-authorized future plan step (7.12) with no defined date, and
`match_skills()` is a flat dict/substring matcher with no "does this skill
exist" reader abstraction to hook a pending-state check into (inventing one
would be production-code scope, which this task forbade). Removal +
breadcrumb also directly matches what the task instructions described as the
primary path; three-state was offered as "if it fits better," and it didn't.
Reusable takeaway: three-state fits when a test tracks incremental completion
toward a gate the same build owns; plain removal + a docstring breadcrumb
naming the exact return step fits when the return is an external, dateless,
separately-authorized future decision.

**Mechanics used:** removed the `"unmassk-gitmemory"` key from
`SKILL_TRIGGER_PROMPTS` (not the whole test method — the other 8 skills'
`TestSkillRouterMatchesRealTriggerPhrases` cases are untouched), updated the
`len(...) == 9/27` sanity asserts to `8/24`, removed only the 2
gitmemory-specific assertions from `test_first_message_forcing_text_present_regardless_of_prompt`
(kept `MANDATORY` + `skill="unmassk-core"` assertions — those are still real
today), and left a "Retirement note" block in the module docstring plus
per-site comments citing `PLAN-CONSTRUCCION.md §5.1` (what was removed and
why) and `§7.12` (where it returns, same name, per the plan's own text: "el
nombre `unmassk-gitmemory` queda libre y la skill nueva lo hereda"). Verified
via `--collect-only -q | grep -i gitmemory` that zero references survive in
collection (not just "passing" — genuinely gone). 74 tests pass (was ~85
before this session; delta is the 3 removed parametrized cases + prior file
growth, not a coverage loss — every other skill's 3 cases per skill,
multi-match, no-match, hook-integration, and the full drift-guard class are
all untouched).

See also: [unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md).
