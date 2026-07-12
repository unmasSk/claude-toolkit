---
name: pre-task-recall-skill-injection-contract-notes
description: Test-first RED contract for domain-skill auto-injection expansion of pre-task-recall.py (BM25 skill-search.py wiring, real-subprocess fixture technique, in-process fail-open simulation)
metadata:
  type: project
---

Task: expand `pre-task-recall.py` (PreToolUse/Task hook, currently only
injects git-memory recall) to ALSO run `scripts/skill-search.py --json`
over the Task prompt and inject a Form-B domain-skill pointer block —
independent of the existing `if not memory_block: passthrough` early-return
at ~line 177 (that's the exact regression this expansion exists to prevent).
Contract tests: `unmassk-toolkit/tests/test_pre_task_recall.py` (appended,
not a new file — task required extending the existing file so the original
~51 tests stay green as a baseline). RED-verified: 8 failed / 62 passed
(19 new tests total; 8 pin genuinely-new behavior, 11 already hold true
before the feature exists and are legitimate regression nets, not filler).

**Key technique 1 — real fixture skill discovered via colocated `.skillcat`,
not env vars.** `skill-search.py`'s `find_git_root()` walks up from `os.getcwd()`
to the nearest `.git` and adds that root to its rglob search dirs. Writing a
disposable `.skillcat` + colocated `SKILL.md` directly INSIDE the temp repo
(not git-tracked — discovery is filesystem-based) makes it discoverable
regardless of whichever real skills happen to be installed on the host
machine, with zero env-var plumbing needed — as long as neither the hook nor
skill-search.py explicitly overrides `cwd` when spawning the subprocess
(reasonable default assumption, since Ultron would need to explicitly choose
to break this). A nonce trigger term repeated in the fixture's `triggers`
CSV column beats the real installed corpus's IDF easily (empirically: score
6.6 vs. real ~37-skill corpus on this machine) — never assume a "no match"
prompt is safe without checking; "BM25 recall ranking implementation" (an
old existing-test-style phrase) scored 7.1 against the REAL corpus once
domain skills are in play, so an old shared-vocabulary trick from the
memory-recall tests is NOT safe to reuse for skill-search scoring. Verified
empirically before writing assertions (real subprocess runs, not assumed):
two nonce words with zero real-English content score exactly 0.

**Key technique 2 — §34 ground truth for score/path assertions: run the
real producer directly first.** Never hand-type the expected BM25 score or
skill_md path. Call `skill-search.py "<same prompt>" --json` directly
against the same repo BEFORE running the hook, parse its JSON, and assert
the hook's injected block contains that SAME score (float-tolerant compare,
`abs(actual-expected)<0.05`, since the exact template's score formatting
precision was Ultron's call, not pinned by the task) and that SAME
`skill_md` path string.

**Key technique 3 — in-process fail-open simulation for timeout/malformed
JSON (the two failure modes the task explicitly authorized simulating,
since the real searcher can't produce them on demand without either a
genuine flaky sleep or an unreachable code path).** Load the hook via
`importlib.util.spec_from_file_location` (this repo's established pattern
for hyphenated filenames), monkeypatch the GLOBAL `subprocess.run` — not
`mod.subprocess.run` — with a SELECTIVE fake that only intercepts calls
whose command line contains `"skill-search"` and delegates everything else
(git commands inside `recall()`) to the real `subprocess.run`. This
decouples the test from assuming which module owns the skill-search call
site (hook-inline vs. a future `lib/` module) — patching the global
attribute works either way since Python resolves `subprocess.run` via
attribute lookup at call time regardless of which module imported
`subprocess`. Blindly faking ALL `subprocess.run` calls would silently break
`recall()`'s own git subprocess calls too, producing a false-pass (fail-open
via an unrelated exception, not the simulated failure) — this is a real risk
worth checking for in any similar future subprocess-simulation test.
`monkeypatch.chdir(repo)` is required alongside this (recall() calls
`run_git()` with no explicit `cwd` param — relies on process cwd, see
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)).

**Key technique 4 — "not nested" invariant without assuming block order.**
The skill block template (from the task, verbatim) never contains `"---"`.
The memory footer always does (`_FOOTER_HEADER`/`_FOOTER_TAIL`). So the
memory footer's own span can be found as `[last "---" before "[PROJECT
MEMORY", last "---" in the whole prompt]` regardless of whether the skill
block appears before or after the memory footer — then assert the skill
block header index falls outside that span. Implementation-agnostic, no
assumption about block ordering baked in.

**Not deduplicated on purpose per task structure:** the task's own (b) and
(c)'s "skill no / memory yes" are the identical scenario; implemented once
in `TestNoSkillMatchMemoryStillFlows`, cross-referenced (not re-implemented)
from `TestSkillMemoryIndependenceRegression`'s docstring.

**(g) invariant tests are NOT all RED, by design, and that's correct.**
"Never deny" is vacuously already true for branches that don't exist yet
(there's no way to deny on a code path that isn't there). Only
`test_invariant_strong_skill_match` was strengthened with an extra
assertion (skill block must ALSO be present) to make it RED like the rest;
the other 4 genuinely already pass today and remain valid regression nets
once Ultron implements — don't force-fail invariant/regression-net tests
that are legitimately already true just to hit a RED quota.

## Contract REVERTED then reshipped as a DENY-based gate (2026-07-12)

The append-block design documented above (inject a separate `[DOMAIN
SKILL — auto-selected for this task.]` block, never deny) was reverted
wholesale (`chore` commit 7497f61: "no funciona"). Root cause diagnosed in
decision `cd42912`: the hook checked `tool_name == "Task"` but the real
payload for a subagent spawn is `tool_name == "Agent"` — the whole feature
was a silent no-op from day one, injection AND gate alike. Root-cause fix
(`tool_name in ("Agent", "Task")`) also revived memory injection, which had
been broken the same way the entire time. The feature was then reshipped
under a DIFFERENT, incompatible contract: instead of appending a block, the
hook now **DENIES** the spawn (`permissionDecision: "deny"`) when a strong
match is found and the marker isn't already in the prompt, with the deny
reason instructing the orchestrator to paste the block at the top of the
prompt and retry (anti-loop: marker presence skips the search entirely).
Verified live: a PreToolUse `deny` genuinely blocks the Task tool call and
the reason reaches the orchestrator.

**Lesson: before reconciling a test file, check whether the git history
between "last known contract" and "now" contains a revert + a different
reimplementation, not just incremental changes.** `git log --oneline -- <test
file>` surfaced this immediately — the file's own history had the revert
commit that the 5-commit general `git log` shown in a fresh session's status
summary did not include (HEAD had moved since). The old append-block
assertions (`SKILL_BLOCK_HEADER`, non-nested-block checks, etc.) are NOT
reusable for the new contract; only the *techniques* (fixture `.skillcat`,
real-producer ground truth, selective subprocess.run monkeypatch) carried
over. New tests for the deny-based contract:
`TestSkillGateDomainMatchDenies`, `TestSkillGateMarkerAntiLoop`,
`TestSkillGateLowScoreAllowsMemory`, `TestSkillGateSearcherFailsOpen`,
`TestSkillGateExcludedAgentPassthrough`, `TestSkillGateInvariant`.

**Host-corpus vocabulary collision broke 27 pre-existing tests the moment
the gate shipped.** The file's own long-standing shared test vocabulary,
`"BM25 recall ranking"` (used in ~20+ tests as the go-to "memory match"
prompt since before any skill gate existed), scores 7.1 against the real
installed `db-vector-rag` skill — both "BM25" and "recall" independently
score 3.5 against it (their own vocabulary overlaps "retrieval augmented
generation" domain terms). Once the gate went live, every one of those
tests started getting DENIED instead of reaching the memory-allow path they
were written to exercise. Fix: introduced `_MEM_NONCE = "zqxvbnkplfth
wjrqztkvnmg"` (pure invented vocabulary, verified score 0 against the real
corpus via direct subprocess) as shared vocabulary between seeded commit
trailers and prompts — recall()'s BM25 index is a SEPARATE corpus (git
commit messages) from skill-search's, so nonce token overlap there still
produces a deterministic memory match. A second nonce, `_NO_MATCH_NONCE`,
covers "genuinely no match at all" tests. **General lesson for this
project: any time a hook gains an additional BM25/keyword-matching gate
over the same prompt field an existing test suite already uses as free-text
vocabulary, audit EVERY existing prompt string in that suite against the
new corpus — plain English test phrases reused for years can silently start
tripping a brand-new gate.**

**Repeated-English padding is NOT a safe way to pad a prompt past a length
threshold once a scoring gate exists.** `TestLongPromptQueryTruncation`'s
existing 12 000-char prompt padded with real English
(`"implement the ... feature with full coverage "` × 200) scored 494.7
against `frontend-react` (BM25 term-frequency amplification from blunt
repetition) — always denies once the gate exists. Fixed by padding with
repeated nonce vocabulary instead (`f"xqzlongprompttoken {_MEM_NONCE}
qzxdfklmnpwrtjhbg "` × 200, still > 10 000 chars) — verified score 0 even at
that repetition count.

**Fixture `.skillcat` technique is REUSED verbatim for the new deny tests**
(same discovery mechanism, unchanged in `scripts/skill-search.py`), but
generalized past a single accepted case: it also grounds the marker
anti-loop test (embed the real producer's own score/path into a retried
prompt) and the excluded-agent test (prove score is irrelevant once
exclusion applies). `_SKILL_MARKER` / `_SKILL_SCORE_THRESHOLD` are read from
the hook module in-process (`importlib.util.spec_from_file_location`) rather
than hand-typed, so a future rename doesn't silently desync the tests.

**Breadcrumb invariant has a real exception, not a test gap.** The task
asked for "every branch leaves a stderr breadcrumb", but the excluded-agent
passthrough (bilbo/gitto) exits via the pre-existing whitelist check
*before* the skill-gate's own try/except block — verified empirically: zero
stderr output for that branch, consistent with how this file already tested
non-whitelisted-agent passthrough before the gate ever existed. Not a
regression from #68; asserted as "no deny" only for that branch, not
"breadcrumb present" — forcing that assertion would make a correct
implementation fail for the wrong reason.

**Post-GREEN reconciliation (hardening pass): pre-existing tests can go
stale the moment the new signal ships, not just newly-written ones.**
`TestNoMemoryMatch::test_no_match_no_injection` and `::test_empty_repo_no_injection`
(the ORIGINAL pre-feature tests, written before skill-search existed) both
started failing once Ultron shipped the feature: their prompts ("github
actions workflow setup", "BM25 recall ranking implementation") are ordinary
English that happens to score above `LOW_SCORE_THRESHOLD` against whatever
domain skills are actually installed on the host (ops-cicd ~11.5,
db-vector-rag ~7.1) — this is exactly the host-corpus non-determinism this
contract's `_NO_MATCH_PROMPT` nonce constant already exists to avoid. Fix:
swap both prompts to the shared `_NO_MATCH_PROMPT` constant (already
verified score-0 against the real corpus, see above) — no new nonce needed,
reuse the one that's already ground-truthed. Judged NOT a duplicate of
`test_neither_match_clean_passthrough` despite same final property (neither
signal → passthrough): that test always uses an empty repo + a REAL planted
skill fixture (proves *present-but-unmatched* skill signal still passes
through); these two vary the *memory* side instead (unrelated-but-real
commit vs. genuinely empty repo, no fixture planted at all) — different
producer state, same invariant, kept as separate regression nets rather
than consolidated away. General lesson: when a hook grows a second
independent injection signal, audit EVERY pre-existing "no injection"
assertion in the file for the same host-corpus leak, not just the tests
written for the new signal.

## Multi-skill selection reconciliation (2026-07-12)

The gate expanded again: `_find_gate_skills()` now selects ALL results
`score >= _SKILL_CONFIDENT` (5.0), falls back to the single top result only
if none clear that bar (`score >= _SKILL_SCORE_THRESHOLD`, 1.5), sorts
desc, caps to `_SKILL_MAX` (3); `_build_skill_gate_message()` switches to a
plural Spanish header/footer ("los siguientes bloques" / "estos bloques
delante") whenever more than one block is selected. All 59 pre-existing
tests stayed GREEN unmodified against the new hook — every one of them only
ever planted a single confident fixture, which is still exactly "1 block,
singular header" under the new selection logic, so nothing broke. Added 3
new acceptance tests (62 total) plus strengthened the one pre-existing
single-fixture deny test with explicit block-count/header assertions it
previously lacked.

**Controlling BM25 score deterministically via document length, not just
term frequency — used to hit the [1.5, 5.0) fallback band.** Raising a
fixture's score is easy (repeat the trigger word in the `triggers` column —
`reps` param added to `_write_gate_skill_fixture`, verified empirically:
reps 1/2/3/4 on 4 co-planted fixtures queried together gave real, strictly
distinct scores 6.3/6.8/7.0/7.2). LOWERING a fixture below `_SKILL_CONFIDENT`
while staying above `_SKILL_SCORE_THRESHOLD` needed the opposite BM25 lever:
padding the SAME document with ~60 unrelated filler tokens
(`fillerword0..59`) in the `triggers` column. BM25's own length
normalisation (`doc_len/avgdl` term in the denominator) then pulls the
score down for the same single trigger occurrence — verified empirically:
one mention scored 5.2 (already confident) undiluted, 2.6 (comfortably in
the fallback band) once diluted. New helper:
`_write_diluted_gate_skill_fixture()`. This is a real BM25 property, not a
fabricated number — the score is still read from a live subprocess call
per Key technique 2, never hand-typed.

**Distinct real scores made ordering assertions provable without ties.**
For the 2-skill and cap-to-3 tests, deliberately giving each fixture a
different `reps` (hence a different real score) avoids relying on BM25's
tie-breaking behavior (stable sort on equal float scores, which follows
filesystem rglob discovery order — untested and not worth depending on).
Every "must appear before" assertion in the new tests compares `reason.find()`
indices between two GENUINELY different real scores, not equal ones.

**Cap-to-3 test derives "excluded" from the real result set, not from
which fixtures were planted.** `excluded = ranked[SKILL_MAX:]` where
`ranked` is sorted from the REAL subprocess response (host corpus skills
included) — if the host's own corpus ever contributed a 5th confident
result ranking above one of the 4 planted fixtures, the test would still
correctly assert against whichever 3 the real hook actually kept, rather
than hard-asserting "the 4 planted fixtures, 3 of them." Test prerequisite
assertions (`len(confident) >= 4`, `expected_names <= confident_names`)
fail loud with the full real result list if the host corpus doesn't behave
as expected — same fail-loud-not-silent pattern as the rest of this file.

**Mutation-checked all 3 new tests against the hook directly (not just read
the code).** Three temporary `sed` edits to `pre-task-recall.py`
(`_SKILL_CONFIDENT=999`, `_SKILL_MAX=1`, `plural=False`), each re-run only
against the affected test classes, each correctly failed the new tests for
the right reason (prerequisite assertion or plural-header assertion), then
reverted via a pre-edit `cp` backup and verified with `diff` before
finishing — confirms none of the 3 new tests are vacuously green. Did NOT
touch the hook file in the final state (task explicitly forbade it); the
hook's underlying multi-skill implementation was already present
uncommitted in the working tree at session start (part of decision
863bd54's work), not something this session wrote.
