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
