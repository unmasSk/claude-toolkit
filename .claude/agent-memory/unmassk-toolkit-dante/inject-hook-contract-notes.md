---
name: inject-hook-contract-notes
description: hooks/inject.py (memoria-v2 Capa 6, PreToolUse/Agent) RED contract -- payload real spec Sec.269, fail-open empirical correction, R-note stops=yes gotcha
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_inject_hook.py` (8 tests, RED
by design -- `hooks/inject.py` does not exist yet). Covers the two
`inject.py`-specific rows of PIEZAS.md Sec.11's test table ("una excepcion
en cualquier punto... deja pasar el encargo sin tocarlo" /
"el contrato... se prueba contra el payload real, medido") plus three
explicit orchestrator asks: exact per-office repartition, an
agent-not-in-the-map passes through untouched, an explicit `Zone:` line
beats word-matching through the whole hook (not just at `dispatch.py`
level, already covered by [dispatch-contract-notes](dispatch-contract-notes.md)).

**Empirical correction on the orchestrator's own suggested fail-open
scenarios -- verify before writing, don't trust the prompt's examples
blindly.** The task text suggested inducing failure via "zones.json
missing" and "repo with zero commits". Live-tested both against the
already-hardened production code (throwaway script, scratchpad only,
never `lib/memory/`) before writing any test:

- `zones.load(missing_path)` -> `{}`, no raise (module's own docstring:
  "fichero ausente = todavia no hay ninguna zona").
- `query.by_zone(...)` in a repo with `git init` but zero commits ->
  `()`, no raise ("Revision 2026-08-02, hallazgo 2 de Moriarty" in
  `query.py`: unborn branch is a VALID state, not a failure).

Both are already gracefully degraded by prior hardening rounds -- using
them as fail-open exception tests would be vacuous (the `try/except`
never engages). Substituted with two that DO reproduce a real exception
today: **malformed `zones.json`** (real `JSONDecodeError` at load time,
before `dispatch` is even reached) and **a directory with no `.git` at
all** (real `RuntimeError` from `query.by_zone()` after 3 retries,
~0.1s -- this one genuinely fires INSIDE `dispatch.content_for()`, so
it's the closer match to the task's "que dispatch reviente"). Each test
proves the induced failure is real via a direct control call (same
pattern as `test_boot_launcher.py::TestBootFailureNeverBlocksSession`)
before asserting the hook survives it.

**R-type notes require `--stops yes`, not `--stops no` (M requires
`no`).** `validate_pain_question()` (validator.py): answering "no" to
the pain question means "es un hecho, entra como M" -- an R note seeded
with `stops="no"` is REJECTED with "contestaste no... entonces es un(a)
hecho, entra como M, no R", which looks like a seeding bug but is
actually the validator doing its job. Cost 3 failed test runs before
catching it (all 6 R-type `seed_note_via_script` calls in this file
needed `stops="yes"`; M-type calls correctly use `stops="no"`). Same
gotcha likely bites any future contract seeding R notes via the real
CLI path -- `notes.write()` called directly (bypassing the CLI's
`validate_pain_question` check, as `test_dispatch.py`'s in-process
`_seed_note` does) does NOT enforce this, only the `note.py` script path
does.

**`HEADLINE_MAX = 80`** (vocabulary.py) -- not 95/96 as the bench
adversarial doc's attack #4 example (`"titular de 96 caracteres"`)
might suggest as the boundary; 96 is just an example value comfortably
over the real 80 cap. `SIMILARITY_THRESHOLD = 0.5` (Jaccard) --
multiple notes seeded in the same test must be about clearly different
subjects (payment lock / EU payout provider / search reindex crash /
leaked token / standup schedule), never variations of one filler
phrase, or `validate_replacement` rejects the later one as "esto pisa a
algo ya escrito" (documented independently in `test_note_script.py`'s
seven-types table, confirmed again here).

**Agent-codename-to-office mapping, DERIVED not invented, same class of
gap as `dispatch.py`'s own flagged assumption.** Neither PIEZAS.md
Sec.11 nor ARQUITECTURA.md Sec.3 name which literal `subagent_type`
string maps to which of the seven Spanish office labels
(`Implementador`/`Tests`/.../`Explorador`) that `dispatch.content_for()`
actually accepts. Derived from `spec-sistema-memoria-v2.md` Sec.8.2,
which lists the SAME seven real agent names (Ultron, Dante, House,
Argus/Cerberus, Moriarty, Yoda, Bilbo) with the identical per-office
content description as ARQUITECTURA.md Sec.3 -- content-matched, not
guessed. `alexandria` and `gitto` are deliberately absent from both
Sec.8.2's list and this mapping -- used `alexandria` as the real,
non-invented "agent outside the office map" test subject (a currently
whitelisted crew agent in the retired v1 hook's own worker list, so
it's a realistic case, not a strawman name chosen to fail).

**Shared `conftest.py` hook-invocation helpers already existed when this
task started** (`run_hook_with_payload`, `run_hook_raw_stdin`,
`HOOKS_DIR`, `make_session_start_payload`) -- added by a concurrent
sibling task (`test_boot_launcher.py`, the `SessionStart` hook of the
same Capa 6). Reused them as-is (generic, hook-name-agnostic). Did NOT
add a `make_agent_payload()` equivalent to the shared `conftest.py` --
kept it LOCAL to `test_inject_hook.py` on purpose: `PreToolUse`/`Agent`
is specific to this one hook, and `conftest.py` is being concurrently
edited by other agents this session (the third hook, `customs.py`, also
landed its own `test_customs_hook.py` mid-session) -- same
"shared-directory concurrent-write" caution as the `lib/memory/`
incident, applied preventively to a shared test-infra file instead.

**Baseline verification technique when sibling RED contracts appear
mid-session.** An initial `pytest tests/memory -q` at the very start of
the task showed 239 passed, 0 failures. By the time this task's own
file was ready, two NEW sibling files (`test_boot_launcher.py`,
`test_customs_hook.py`) had landed in the working tree (untracked, same
as everything else on this branch -- nothing is committed) with their
own RED failures (20 total) for the OTHER two hooks of Capa 6, being
built in parallel. Confirmed these were not caused by this task's work:
`git status --porcelain` on `conftest.py` showed +510 insertions only
(the siblings' additions, never touched by this task), and re-running
with all three new hook-contract files excluded via `--ignore` still
showed exactly 239 passed -- the real, pre-existing baseline this task
must not regress was untouched.

Reference: [dispatch-contract-notes](dispatch-contract-notes.md) (the
office-string/content_for contract this hook wraps),
[capa5-scripts-red-contract-notes](capa5-scripts-red-contract-notes.md)
(same `run_memory_script`/subprocess-testing family, one layer down).
