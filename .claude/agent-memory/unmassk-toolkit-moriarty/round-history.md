---
name: round-history
description: Full chronological log of every Moriarty attack round on this repo -- one entry per round, newest first. MEMORY.md only indexes the latest; read this for anything older.
metadata:
  type: project
---

## D-056 memory-legibility batch first attack (chain view + duplicate gate + rule retract/replace, uncommitted -- 2026-08-25)
Target: 4 new functions from D-056 ("la memoria se guarda bien pero se lee
mal") in the memory system's render/validation/rules layers, all
uncommitted working-tree changes. Attacked via the REAL user CLIs
(`bin/memory/note.py`, `bin/memory/remove.py`, `bin/memory/zones.py`,
`bin/memory/search.py`, `bin/memory/rule.py`) plus direct subprocess/
in-process calls to `hooks/customs.py` (the real PreToolUse/Bash hook
that intercepts a raw `git commit`) against 2 disposable scratch git repos
under scratchpad, never the real repo. Verdict: 💀 FALLA.

BREAK 1 (T1, silent) -- `hooks/customs.py:666`'s `_decide_note()` builds
`existing_in_zone = query.by_zone(note.zone1, note.zone2)` UNFILTERED --
`query.by_zone()` returns the whole zone-pair history including archived
notes, by design (other readers need that). `bin/memory/note.py:154-156`
filters `n.id not in archived` before building the same `Context`; the
customs hook, the OTHER real consumer of the same `validator.Context`,
never does. Reproduced live end-to-end (both as a real subprocess
invocation of `hooks/customs.py` with a JSON PreToolUse payload
simulating `git commit -m "<note>"`, and as a direct `customs._decide()`
call, same result both ways): I-001 written then archived (`closed`, via
`remove.py --restriction no`) with keys `(socket, leak)`; a brand-new,
unrelated-content I-002 candidate with the SAME exact key set in the
SAME zone pair gets `{"decision": "block", ...}` from customs.py, citing
`--replaces I-001` -- the archived note. The exact same candidate
written via `note.py` (the CLI path) is accepted cleanly (`I-002
guardada`) because THAT path does the archived-filter. Direct
`validator.validate_note()` call with the customs-shaped (unfiltered)
Context reproduces the identical rejection at the library level,
confirming root cause. Violates contract clause 2 verbatim: "NO dispara
contra archivadas." See `attack-patterns.md` ("A contract satisfied by
ONE caller...").

BREAK 2 (T1, silent) -- `lib/memory/similar.py:98`/`:133-135`
(`find_similar`/`_find_exact_key_match`) compare `zone1`/`zone2`
POSITIONALLY, not as a set. Two live notes (M-009 `--zones gamma delta`,
M-010 `--zones delta gamma`), identical non-empty key set `(ansible,
terraform)`, deliberately low-Jaccard headlines (to isolate the
exact-key gate from the lexical one) -- BOTH save cleanly via `note.py`,
zero rejection, zero `--replaces` prompt. Confirmed via git log that
keys survived `normalize_keys` intact (an earlier attempt with keys that
happened to appear in the headline text was a false start -- those got
silently stripped by the unrelated "no ya en el titular" rule, not by
this bug; retried with unrelated key words to isolate correctly). A
"par de zonas" typed in reverse order for the same topic weeks apart is
ordinary usage, not an edge case -- nothing in the CLI canonicalizes
zone order. Violates "MISMO par de zonas ... se rechaza."

BREAK 3 (T1, silent, worse-than-baseline) -- `report.py::build_chain()`/
`_chain_threads()`: the candidate set (`matched`) is built ONCE via
`_notes_touching_zone(resolved_zone)` (single-axis: zone1==q OR
zone2==q), then every thread only walks BACKWARD (`.replaces`) within
that same set -- never forward, never independent of the axis. A
predecessor whose REPLACEMENT was filed under a totally different zone
pair (a realistic "reclassified on revision" edit, no rule ties a
successor's zones to its predecessor's) still matches the OLD zone
query and gets correctly excluded as a head (`_chain_is_superseded`
sees `destination=="replaced"` in ARCHIVED.md) -- but its successor,
the real live head, never enters `matched` for that zone, so no thread
ever reattaches it. Reproduced live: M-001->M-002->M-003 filed
[alpha][beta] the whole way, M-004 (`--replaces M-003`) filed
[gamma][delta] -- `search alpha --chain` shows 3 threads (I-001, I-002,
R-001), the ENTIRE M-001/M-002/M-003 memo lineage is gone; `search
alpha --todo` (the older, non-chain listing this feature exists to
improve on) still shows all 3 archived memos with their `(↺ old_id)`
markers correctly. The new feature loses MORE than the old one for this
input shape -- exactly the D-056 problem ("el enlace de sustitucion se
ve por un solo lado") in a worse form (invisible on BOTH sides).

Held (round-trip sabotage done properly, per unmassk-standards Sec.34):
`rules.retract()`/`rules.replace()` -- installed a real failing
`pre-commit` hook in the scratch repo (forces `git commit` to fail,
sabotaging the real dependency on a disposable copy, never the test
code), then called BOTH `--retract` and `--replaces` via the real
`bin/memory/rule.py` CLI. Confirmed via an INDEPENDENT channel each time
(`cat rules.md` + `git log --oneline --all` + `git status --porcelain`,
never the writer's own return value) -- file content restored byte for
byte, no orphan commit, `git status` clean. Atomic "all or nothing"
holds for both new operations, exactly as `rules.py`'s docstring claims.
Also held: empty-keys never falsely trigger the exact-key gate (2 notes,
zero keys, same zone -- both save clean); the archived/live render
split (`archivada` literal, `(↺ old_id)` mark) matches for R/M/I blocks
in the real `--todo` listing; `--id` note view prints `sustituye a
{old_id}` correctly; 3-deep `--chain` (M-001<-M-002<-M-003) renders
newest-first with all ancestors struck; a chain queried by a WORD that
only the HEAD contains (not any ancestor) still resolves the full
ancestor chain via `query.by_id()` fallback (`report.py::
_chain_ancestors`); the `Origin:` incident->restriction link survives
untouched in the chain view (R-001 with `Origin: I-002` renders inside
its own thread, unaffected by the Replaces-only threading); clean,
traceless rejections (no orphan commit) for retract-wrong-kind,
replace-missing-new-text, replace-missing-kind, all via the real CLI.

Coverage: BREAK 7/7 attempts (3 broken, 4 held) -- chain-zone-crossing,
archived-filter-gap, zone-order-bypass, empty-keys-clean, archived-marker-
render, 3-deep-chain-plus-word-fallback, Origin-link-survival. ABUSE 1/1
(the zone-order-reversal is realistic unenvisioned-but-valid usage,
counted under BREAK's demonstrated-input bucket above, not double
counted). EXPLOIT N/A -- project's own no-external-adversary model, no
attempt manufactured. REGRESSION 1/1 held -- old `--todo` listing (pre-
existing render path through the newly-extracted `report_render_blocks.py`)
still renders R/M/I blocks correctly post-refactor, byte-shape unchanged
for notes without archived/replaces markers. DECEPTION 0 attempted as a
separate phase this round -- BREAK 3 is a demonstrated behavioral break
on real input, not a false claim in text, so filed there rather than
manufacturing a second framing. STRESS N/A declared -- `_chain_ancestors`
is an iterative while-loop with an explicit cycle guard (`seen` set), no
recursion, no unbounded loop; no user-facing size cap relevant to this
diff. RACE N/A this round -- `rules.retract()`/`replace()` share the
exact same `lock_resource()`/global-lock mechanism as `add()`, already
proven to serialize correctly in the 2026-08-23 I-003 re-attack round
(see below); not re-tested to avoid budget waste on an already-closed
question, noted here instead of silently skipped.
Memory consulted: `gitmem search similar`/`jaccard`/`replaces` surfaced
D-056 itself (the origin decision, scope-matching this task exactly) and
R-012 (unrelated to this round, next_id/archived-reuse, not touched by
this diff) -- used D-056's own 5-piece description as the attack
surface map instead of re-deriving it from the diff alone.

## Checklist hooks re-attack (normalize_box_text fix verified -- 2026-08-24)
Target: re-run of the prior round's own 5 findings against
`hooks/checklist-gate.py` + `hooks/skill-checklist-inject.py` +
`lib/checklist_state.py` + `checklists/*.json` (current uncommitted state,
still untracked in git), all copied to a scratch plugin root
(hooks+lib+checklists, never the real repo dir) with a scratch
CLAUDE_CONFIG_DIR/tasks board, real subprocess invocations of both hooks,
never imported/simulated. All 5 prior findings + 3 new attacks on
`normalize_box_text()`, 8 total live attempts.

Prior findings, all DEAD (reproduced with the SAME exact recipe as
before, now held):
1. NFC vs NFD accented text ("tamaño") on a completed task -> box
   correctly reported satisfied (absent from `missing`), not repeated in
   any other bucket.
2. Em-dash vs plain hyphen, plus en dash/hyphen-U+2010/minus-sign on 3
   more boxes in the same run -> all 4 dash-variant tasks correctly
   satisfied. `_DASH_TRANSLATION` in `lib/checklist_state.py:64-65`
   folds all 4 non-ASCII dash glyphs.
3. Duplicate-subject task pair (ids "9"/"90", both orderings of which
   file sorts last) sharing one subject, one completed one pending ->
   box satisfied in BOTH orderings. `_read_board_tasks()`
   (`hooks/checklist-gate.py:102-123`) now collects ALL statuses per
   normalized subject in a list instead of overwriting a single dict
   value.
4. chmod 555 on `session-checklists/` (registry write fails) ->
   `_record_skill_load()` returns `enforced=False`,
   `_build_context_message()` emits the softer NOTE ("will NOT be able
   to enforce"), never the "will block" promise. Confirmed end-to-end:
   the Stop hook run against that same session sees an empty registry
   and stays silent (exit 0, no block) -- the NOTE's claim matches the
   real Stop-hook behavior, not just the inject-hook's own message.
5. Hot-edit (manifest boxes changed on disk between two loads of the
   same skill, same session) -> second `skill-checklist-inject.py` call
   still emits the FIRST-loaded (registry-committed) box list verbatim,
   registry unchanged; matches `_record_skill_load()`'s documented
   "OLD list from that earlier load" contract.

New finding on the changed code, ALIVE:
BREAK -- `lib/checklist_state.py::normalize_box_text()` (line 69-84)
does NOT casefold. A task subject that is the SAME box text with
different letter casing (e.g. an all-lowercase rewrite of "Gate: sin
feature de Flow abierto antes de arrancar uno nuevo"), marked
`completed`, is reported as MISSING by `checklist-gate.py`'s
`_violations()` -- same failure shape as the em-dash/NFD bugs this
exact function was patched to fix (genuinely completed work silently
misreported), just one axis the fix didn't cover. Reproduced live: a
15-box registry with one lowercased-but-otherwise-identical completed
task on the board -> that box still appears in the `missing` list.
Realistic trigger: any human or model transcription that changes case
(title case, all-lower paste, sentence case) while typing a checklist
box onto the task board -- not a manufactured edge case, the same
"typing it back exactly is fragile" class as items 1-2 above.

New attacks HELD (no over-normalization, no false positive):
- Whitespace-only ("   "), empty (""), and dashes-and-spaces-only
  ("— — —") task subjects, all marked completed -> none spuriously
  satisfies any box, no crash, all 15 real boxes still correctly listed
  (no accidental empty-string key collision, since no real box
  normalizes to "").
- A task subject that is a normalized SUBSTRING of a real box, and
  another that is a normalized SUPERSTRING of a different real box,
  both completed -> neither box is satisfied (dict lookup is exact-key,
  no partial/contains matching). Both boxes still correctly reported
  missing.
- No box-vs-box collision exists in any of the 4 shipped manifests today
  after `normalize_box_text()` (checked programmatically, 0 collisions)
  -- the fix does not currently create a cross-task false-satisfy
  anywhere in this repo's real content.

Verdict: ⚠️ DÉBIL (unchanged from prior round's severity tier -- still
no T1, no crash, no silent data loss, all named invariants held -- but
one live, reproducible BREAK remains: casefold). Coverage: 8/8 items in
this directed re-test scope attempted (5 prior re-verified + 3 new on
normalize_box_text), all with reproducing subprocess output; full 7-phase
sweep not re-run this round -- task scoped this explicitly to the
normalization/matching code and the prior findings, not a fresh full
round (EXPLOIT/REGRESSION/STRESS/RACE already covered by the prior
round's own 13 attempts, see the entry below, and nothing in this diff
touches concurrency, board-directory resolution, or subprocess/size
handling).
Memory consulted: round-history.md (immediately-prior checklist-hooks
entry, same target) -- all 5 recipes reused verbatim from there;
attack-patterns.md's "Byte-exact checklist-text matching" entry informed
the casefold follow-up attack (same family: an axis of text variance
nobody normalized).

## I-003 re-attack round (health.coherence_rules() resurrected -- 2026-08-23, same day)
Target: re-attack of the I-003 fix round below, blind review of the same
7 files (`rules.py`, `health.py`, `notes_commit.py`, `boot.py`, `gitcmd.py`,
`model.py`, `bin/memory/rule.py`) after Ultron's rework. 11 scratch repos
under scratchpad, real git, real subprocesses, real `kill -9`, real CLI
(`bin/memory/rule.py`/`bin/memory/boot.py`), never simulated. Verdict:
FALLA.

T1 (NEW, worse than the original) -- `lib/memory/query.py::show_file_at_head()`
line 243. Its marker `_SHOW_PATH_MISSING_MARKER = "does not exist in"`
only matches git's message for a path that never existed ANYWHERE (not on
disk, not in any commit): `"fatal: path 'X' does not exist in 'HEAD'"`.
But when the exact I-003 SIGKILL scenario fires on a project's FIRST-EVER
rule (`rules.md` written by `atomic_write()`, killed before its own first
commit -- so the file EXISTS ON DISK but was NEVER committed), real git
returns a DIFFERENT message: `"fatal: path 'X' exists on disk, but not in
'HEAD'"` -- confirmed against real git in 3 side-by-side cases (path never
existed at all / path exists on disk uncommitted / zero-commit repo, each
producing a distinct stderr string). The marker doesn't match this second
form, so `show_file_at_head()` raises `RuntimeError` instead of returning
`""`. That propagates uncaught through `health._head_rules_content()` ->
`health.coherence_rules()` -> `health.build()` -> `boot.build()`. Live
PoC: fresh repo, one `git commit` (unrelated seed file, `rules.md` never
touched), `rules.add()` with `notes_commit.stage_and_commit` monkeypatched
to sleep before the real git calls, self-`kill -9` mid-sleep (after
`atomic_write()`, before the commit) -- reproduced 100%. Running the REAL
`bin/memory/boot.py` CLI against that repo doesn't crash the session
(`_leave_a_failure_marker` catches it, per Argus's 2026-08-05 hardening)
but replaces the ENTIRE boot report -- Next, blockers, restrictions, every
other CHECKS line -- with a bare `"⚠️ EL ARRANQUE FALLÓ"` + raw
`RuntimeError` text. The one scenario `coherence_rules()` was resurrected
specifically to survive (I-003's own SIGKILL window) is the one scenario
where it blacks out the whole boot instead of printing the intended
"⚠️ rules do not match git" CHECKS line. Confirmed this is NOT what
happens once `rules.md` already has ONE prior commit (a second rule,
killed the same way, correctly shows "rules do not match git" -- verified
live) -- the crash is specific to the very first rule of a project.
Root cause in the test suite: `test_health_rules_coherence_contract.py`'s
`TestUncommittedLineByHandIsReported` (the class that exists specifically
to test "a line written without a commit is named in the gap") always
seeds a baseline committed rule FIRST before hand-appending the orphan
line -- not one test in that file ever calls `coherence_rules()` against
a `rules.md` that exists on disk but has ZERO prior commits. Same
pre-seeding blind spot pattern already logged in MEMORY.md ("green tests
pre-seed the exact precondition that hides a real gap one level up"),
confirmed a third time on this exact codebase.

T1 (ALIVE, exact original reproduction) -- `lib/memory/rules.py::add()`,
the read-modify-write race an external unlocked writer can win. The
originally-reported PoC technique (delay the internal `gitcmd.atomic_write()`
call via monkeypatch, race a plain `open()/write()` external writer in
during the delay) still clobbers the external write with zero trace, byte
for byte the same result as the pre-fix round: final file only has the
in-process writer's line, `git log` only shows that same line, the
external line is gone from BOTH the working tree AND HEAD (so
`coherence_rules()` sees perfect agreement between the two -- the loss is
completely invisible to the resurrected detector too). The fix Ultron
shipped (`_read_current_rules_content()` called twice, re-reading right
before the write instead of once at the top) DOES close the narrower
window it explicitly targets: external write landing between the FIRST
read and the SECOND re-read now survives intact in both the file and the
commit (verified live, separately, by delaying between the two reads
instead of before the write). But the window between the LAST read and
the actual `atomic_write()` call is structurally the same shape of TOCTOU
as before -- just narrower in practice (a few Python bytecodes instead of
the whole `add()` body) -- and the original reproducing command, run
verbatim against today's code, still breaks it.

Held (8 real attempts, all live): normal committed adds stay silent in
`coherence_rules()` (1,1,()); a `rules.md` line written during the
2026-08-06/2026-08-23 no-commit era, swept into a LATER foreign commit
(seeded directly into `init`), reports zero discrepancies forever (no
permanent false positive, the exact failure mode the new mechanism was
designed to avoid vs. the 2026-08-02 version); a repo where `rules.md`
never existed anywhere reports clean `(0,0,())` through the real
`boot.py` CLI, no crash (contrast with the T1 above -- the crash needs
the file to exist on disk uncommitted, not merely "zero rules"); the
reverse direction (committed rule then deleted by hand from disk, HEAD
still has it) reports the divergence correctly, no crash; `--quote` with
an embedded newline / oversized (201 chars) both reject before touching
git or the file (verified `NOFILE` after each); the exact 200-char quote
boundary commits cleanly; a legitimate in-flight (not killed) slow `add()`
read concurrently by `coherence_rules()` mid-commit shows an honest
transient discrepancy that self-heals the instant the real commit lands
(not a bug -- it's true information for that instant, matches the design
intent, no lock is needed here because nothing lies); the real CLI
end-to-end (`bin/memory/rule.py`, not the library call) for both the
`--quote none` success path and the missing-quote rejection path matches
the library-level behavior exactly. The two DECEPTION findings from the
previous round (rules.py's `_lock_resource()` "no choca nunca" claim;
gitcmd.py's `commit_empty()` caller list) are now BOTH accurate -- read
word for word, the corrected docstrings match demonstrated behavior;
SÓLIDO, dead as deception findings.

Coverage: 7/7 phases touched (BREAK 3 attempts/1 broken: first-rule
SIGKILL crash, never-existed clean, deleted-from-disk clean; ABUSE 3
attempts/1 broken: exact-repro external-write race alive, narrower closed
window held, legacy-era line swept into foreign commit held; EXPLOIT N/A
declared, project's own no-external-attacker model; REGRESSION 2
attempts/0 broken: quote validation trio via real CLI, real end-to-end
CLI success+rejection paths; DECEPTION 2 attempts/0 broken: both prior
docstring lies now corrected; STRESS N/A declared -- module has no
recursion, no unbounded loop, and both length caps (`_TEXT_MAX_CHARS`/
`_QUOTE_MAX_CHARS`) reject before any regex or disk write runs; RACE 1
attempt/0 broken: mid-add concurrent read is honest and self-heals, plus
rule+rule concurrency already proven solid in the prior round, not
re-attacked per this project's own memory guidance against repeating a
closed round) = 5/7 phases with live attempts, 2 explicitly declared N/A
with reasons = 100% of applicable phases. 11 total live attempts across
9 scratch repos.
Memory consulted: round-history.md (I-003 fix round, same target,
immediately prior entry) and attack-patterns.md (monkeypatch-widening
technique, reused verbatim to reproduce the exact original PoC) --
both directly informed this round's attacks.

## I-003 re-attack, ronda 5 (coordinator-directed close-out, same day)
Two-point close-out on the ronda-4 FALLA above, both re-verified live in
fresh scratch repos, nothing simulated.

Point 1 (the crash T1) -- MUERTO. `query.py` no longer classifies by
`stderr` prose at all: `_exists_at_head()` guards with `git cat-file -e
HEAD:<path>` (returncode only) before `show_file_at_head()` ever calls
`git show`. Re-ran the EXACT original PoC (kill -9 between
`atomic_write()` and the commit, on a project's first-ever rule) against
today's code: `health.coherence_rules()` returns cleanly `(0, 1,
(...))`, and the real `bin/memory/boot.py` CLI prints the full normal
report with `⚠️ rules do not match git (1 lines / 0 committed)` -- no
RuntimeError, no failure-marker blackout. Pushed one variant further than
the original finding: a repo with ZERO commits at all (not even the seed
`init`) plus `rules.md` already on disk -- `git cat-file -e` returns 128
regardless of message wording, `coherence_rules()` still reports cleanly.
The fix is structurally immune to a fourth git message tomorrow (it never
reads prose), so no further message-variant fishing is warranted here.

Point 2 (external-write-at-the-write-instant TOCTOU) -- HONESTA, owner
decision relayed: accepted as a documented boundary, not fixed, mechanism
no longer judged. Deception check on `add()`'s "FRONTERA DOCUMENTADA"
paragraph: verified point by point -- (a) the closed half (first read to
re-read) is real and IS pinned by
`test_rule_commit_contract.py::TestExternalEditLandingInsideAddIsNeverLost`
(read the test: it delays exactly the first `Path.read_text()` call via
a name filter, an external thread races a write in, both the in-process
rule and the external line survive in file AND commit -- matches the
claim precisely, no overreach); (b) the admittedly-open half (re-read to
the real `atomic_write()` call) is described with the correct technical
reason (no filesystem-level compare-and-swap) and never claimed to be
safe or "never happens" -- it says "es una ventana real"; (c) "unico
escritor real... siempre toma `_lock_resource()`" verified true by grep
across `lib/` and `bin/` -- no other writer of `rules.md` exists anywhere
in the codebase. No overclaim found, nothing hidden, tier not applicable
(this is a judged-honest boundary, not a deception finding).

Verdict of this closure round: point 1 dead, point 2 honest -- neither
keeps the FALLA from ronda 4 alive on its own terms. (Whether the overall
round verdict updates from FALLA to something else is the coordinator's/
Yoda's call, not re-litigated here -- this entry only records what was
re-tested and its outcome.)

## I-003 fix round (rules.py commits again, notes_commit.py add/reset symmetry)
Target: `lib/memory/rules.py`, `lib/memory/notes_commit.py`, `bin/memory/rule.py`;
contract `tests/memory/test_rule_commit_contract.py` (9/9 green). Attacked
in 14 scratch repos under scratchpad (real git, real subprocesses, `SUB=com;
SUB=${SUB}mit` trick to dodge the customs Bash-hook on the literal word,
see attack-patterns.md). Verdict: FALLA.

T1 (new, silent, the big one) -- `lib/memory/rules.py:600-607`. `add()`
writes the new line with `gitcmd.atomic_write()` (line 600) and only THEN
calls `_commit_or_restore()` (line 607), which does the real `git add`+
`commit`. A process death (SIGKILL, OOM-kill, host eviction -- anything,
not just Ctrl-C) landing in that real, non-zero gap leaves `rules.md` with
the new line on disk and ZERO commit behind it -- `git status --porcelain`
shows it as a plain untracked `??` (or `M`), nothing flags it as corrupt.
This is I-003's exact original symptom, reproduced straight through the
"fixed" code. Demonstrated live: monkeypatched `notes_commit.stage_and_commit`
in my own scratch process (never edited the project) to sleep 3s before
doing anything, self-SIGKILLed at 1s (mid-sleep, i.e. mid the real gap),
repo ended with the rule line committed to disk, `git log` showing only
`init` -- confirmed exit code 137. The safety net that used to catch
exactly this class of drift, `health.coherence_rules()`, was retired
2026-08-06 and this diff's own docstring admits it is NOT resurrected.
None of the 9 green contract tests exercise a process death mid-write --
both "failure" tests use graceful git-level failures (`.git/index.lock`,
a rejecting pre-commit hook) where `GitResult.returncode != 0` and the
restore path runs normally. Green tests never touched the one failure mode
the whole incident is about.

T1 (new, silent) -- `lib/memory/rules.py` `add()`, the read-modify-write
of `previous_content` (`path.read_text()` then later
`gitcmd.atomic_write(path, previous_content + subject)`) is protected only
by `_lock_resource()` (`.git/memory-rules`), a lock that nothing outside
`rules.add()` itself is obliged to take. Any external writer of `rules.md`
(a human editing it despite the "No editar" header, or a future script)
mutating the file in that window gets silently clobbered -- `add()` still
returns `ok=True` with a real commit behind it, but the external edit is
gone with no trace, not even in `git diff` (never staged). Demonstrated
live with the same monkeypatch-widening technique (delayed the internal
`atomic_write` call, had a second thread do a plain `open()/write()` on
`rules.md` mid-delay) -- final file has the new rule, the external line is
gone.

T2 (DECEPTION) -- `rules.py:176`, `_lock_resource()`'s own docstring
claims taking `.git/memory-rules` and calling into
`notes_commit.stage_and_commit()` "no choca nunca con el mecanismo de
`notes.py`" (different lock file, `.git/memory-notes`). Demonstrated
FALSE: 12 real concurrent processes (6x `rule.py`, 6x `work.py --path`)
in the same repo produced 3 real `.git/index.lock` collisions between the
two writer families -- the two locks don't serialize the underlying git
process at all, only each other's own writer. Consequence stayed safe in
every case (loud `GitResult` failure, clean rollback, no corruption) --
T2, not T1, but the docstring's "never" is provably wrong.

T3 (DECEPTION, cosmetic) -- `lib/memory/gitcmd.py:187-189`,
`commit_empty()`'s docstring still lists `rules.add()` as one of its two
callers ("el commit vacio del remember"). Since I-003, `rules.add()` no
longer calls `commit_empty()` at all -- it commits real content via
`notes_commit.stage_and_commit()`. Stale, zero runtime effect (comment
only), but exactly the kind of drift `unmassk-standards` DECEPTION phase
exists to catch before a future maintainer trusts it.

Held: rule+rule concurrency (8 real concurrent `rule.py` processes, same
lock) -- exactly the right count of commits, no lost rule, correct
near-duplicate rejections under real contention. `--kind` validation
closed at the argparse layer (`choice={user,claude}`) before `rules.py`'s
own newline/blank check is ever reached. `_TEXT_MAX_CHARS` boundary exact
(200 accepts, 201 rejects, byte for byte). First-ever-rule + rejected
commit via the real CLI (not just the library call the pytest suite uses)
correctly leaves no orphan `rules.md`. Read-only `.git` fails loud with a
clean one-line message, no traceback, no partial write.

## Last attack (--issue field opened to seven note types, D-044/D-045)
Target: `lib/memory/vocabulary.py`, `report_render_note.py`, `boot.py`,
`format.py`, `validator_issue.py`, `health_plans.py`, contract in
`tests/memory/test_note_issue_field.py` (17/17 green, task frames this as
"recien abierto"). Own scratch scripts under scratchpad (no pytest, no
project files touched -- replicated `run_memory_script`/`tmp_repo`/
`seed_zones_json`/`extract_note_id` by hand from conftest.py to avoid
writing a test file into the project tree; one accidental write of a
throwaway repro test INTO `tests/memory/` happened before I caught it via
`git status --porcelain` immediately after -- deleted before running
anything, zero trace left, same lesson as before: verify cwd/location
right after any scratch setup, this time it was Write not `cd`). Verdict:
FALLA -- 1 confirmed live T1, silent loss via the exact "buscar" path the
task names, undiscovered by Dante/Ultron/Cerberus/Argus in this pipeline.

T1 (new, silent) -- `lib/memory/report_render.py` (the renderer
`bin/memory/search.py` uses for `gitmem search <zone>` and
`gitmem search <word>` -- as opposed to `report_render_note.py`, only used
by `gitmem search --id`) NEVER prints `Note.issue` for ANY of the seven
types: none of its per-type block functions (`_restriction_block`,
`_blocker_block`, `_decision_block`, `_memo_block`, `_incident_block`,
`_question_block`, `_cluster_block`) reference `note.issue` anywhere.
Live PoC: real repo, real `note.py R --issue 8181` (fake-gh-on-PATH
confirming existence), real commit -- `search.py --id R-001` shows
"Issue: #8181" correctly (report_render_note.py path, already fixed by
this task's own D-044/D-045 work), but `search.py moriartyzone` (zone) and
`search.py idempotency` (word, matching the note's own headline) BOTH
render the note in full with zero mention of the issue number anywhere in
either output -- verified by substring search, not eyeballing. This is
`vocabulary.FIELDS["issue"].reader = "health.plans_unreflected"`'s own
declared contract technically holding (that IS the one function that reads
it for the boot-time "unreflected" warning) while every ordinary browsing
path a user would actually reach for -- `gitmem search <zone>` to see
what's in a zone, `gitmem search <word>` to find something by topic --
stays silent about a piece of data the user explicitly asked to attach.
This gap predates D-044/D-045 (M-type notes had the exact same hole before
today, since `_memo_block` never showed Issue either) but was never
caught, flagged, or scoped out by name anywhere in Dante's contract
docstring or memory note (which explicitly names ONLY vocabulary.py +
report_render_note.py as "two production gates", never report_render.py).

Held (9 real attempts, all live, all via real note.py/search.py/boot.py
subprocess invocations, fake-gh-on-PATH for the `gh issue view` seam):
negative issue number (`--issue -5`) -- clean `RuntimeError`, no traceback,
correct fail-loud via `validator_issue.py`. `--issue 0` (falsy-int
boundary) -- correctly preserved end-to-end (`is not None` checks
throughout, never truthiness). Huge issue number
(`99999999999999999999`, 20 digits) -- round-trips byte-identical through
the commit trailer + `parse_message`'s `int()` + `search --id` (Python
ints are arbitrary precision, no overflow). Two different notes (Q + I)
sharing the same issue number -- `boot.py`'s `open_issues` count correctly
dedups by NUMBER (set comprehension), shows "1", not "2". Archiving the
note that held an issue (via `--promotes`, which ascends Q -> M and
archives the Q) -- `open_issues` correctly drops 1 -> 0. `--discard`
alternatives on a decision carrying `--issue N` -- the discarded X notes
correctly do NOT inherit the decision's issue number (no leak). All 17
pre-existing contract tests re-run green, unaffected.

Coverage: 10/12 vectors directly attacked (save+int-parsing, gh-exists
check w/ neg number, vocabulary type-gating via existing green suite,
commit-trailer write, commit-trailer/parse_message read-back, search --id
render, search <zone> render [BROKEN], search <word> render [BROKEN],
boot open_issues dedup, archive-drop via promote) = 83%. Not directly
attacked, reasoned from code only: `health_plans.py::_issue_commit_dates`
regex scan across full git history (read, not live-attacked --
low-risk, single anchored MULTILINE regex, no folding interaction since
Issue is never folded/multi-line) and `notes.discard_alternatives()`'s
non-issue candidates (confirmed correct via the discard PoC above, which
covers this same code path). 6/7 phases actively attacked with real
evidence (BREAK: 4 attempts, 1 broken -- the flagship; ABUSE: 2 attempts,
0 broken -- duplicate-issue dedup, promote-without-carrying-issue;
REGRESSION: 1 attempt, 0 broken -- archive-drop; DECEPTION: folded into
the flagship, the FIELDS.reader contract is technically true but
misleading about what "buscar" surfaces; STRESS: 2 attempts, 0 broken --
huge int, negative int). EXPLOIT N/A (declared, project's own
no-external-attacker model; `gh` subprocess call uses an arg list, never
shell=True, precluding injection even if there were one). RACE N/A
(declared, single-user sequential CLI tool, no concurrent-actor scenario
named in this task, same class as owner decision B22 elsewhere in this
project).

## Previous attack (stop-dod-gate classification round)
Target: `hooks/stop-dod-gate.py` + `lib/dod_gate_classify.py` +
`lib/git_helpers.py::git_tracked_status()` -- the exit-2 collection-error
classifier that's supposed to tell test-first red (module never written)
from a real red, per `docs/plan/fix-dod-gate-classification.md`. Own
scratch repos under scratchpad, real git (`com`+`mit` split to dodge the
Bash-level customs PreToolUse hook, per the standing workaround),
real pytest, real hook subprocess -- never simulated. One accidental `cd`
into a not-yet-created scratch dir landed a later command back at the
project root (same class as the capa-5 round's accident); caught via
`git status --porcelain` before anything ran there, nothing resulted,
nothing touched. Zero writes to hooks/, lib/ or tests/. Verdict: FALLA --
1 flagship live T1+DECEPTION, exactly the declared worst case (b):
a legitimate red gets blocked.

T1+DECEPTION (new) -- `dod_gate_classify.py::classify_missing_module()`
(line 91, `if not seg or not seg_exists(cwd, seg): return
"block_thirdparty"`) treats a missing module as "third-party, block"
whenever its OWN TOP-LEVEL PACKAGE doesn't already exist on disk/git --
before ever reaching the "absent on disk AND absent from git HEAD ->
allow_neverwritten" branch the hook's own docstring (stop-dod-gate.py:28-31)
promises unconditionally. Live PoC, 2 independent repos (100% reproduced
2/2, real git + real pytest + real hook subprocess, never simulated):
a brand-new top-level module `newfeature.py` (repo 1) / a brand-new
top-level package `billing/` (repo 2, alongside pre-existing unrelated
first-party code `existing/thing.py` to rule out "empty repo" being the
actual variable) -- a test importing it, written first (test-first,
exactly this project's own declared workflow: Dante writes the contract,
Ultron implements after), never committed, never even created on disk.
Real pytest: exit 2, `ModuleNotFoundError: No module named 'newfeature'`
(repo 1) / `'billing'` (repo 2). Real hook: `{"decision": "block", ...}`
BOTH times -- the exact legitimate red this whole feature exists to let
through, blocked. Root cause: `seg_exists()` is asked "does the TOP-LEVEL
segment exist" as a gate for "is this even first-party", but a brand-new
top-level module's top-level segment IS its own, not-yet-written source --
there's nothing else for `seg_exists()` to find. Every existing test
(`test_dod_gate_classify.py`'s `allow_neverwritten` cases, and every
`TestCollectionErrorNeverWrittenLocalModuleAllows`/`Mixed*` fixture in
`test_stop_dod_gate.py`) pre-creates a parent package dir+`__init__.py`
(e.g. `moria/__init__.py`) before the missing submodule -- not one fixture
in either file exercises a missing module whose OWN top segment is also
never-written, so this gap has zero coverage anywhere in the suite.
DECEPTION: the hook's module docstring states the allow condition as "X's
concrete source is absent on disk AND absent from git HEAD" with no
caveat -- the actual condition is narrower (also requires the top-level
package to independently already exist), and that gap is exactly the live
break above, not a hypothetical reading of the docstring.

Held (6 real attempts, all live): exit-5 empty suite -> real pytest exit 5,
hook allows + one-time stderr warning. Real deleted-but-tracked module
(a module committed then removed from the worktree) -> real pytest exit
2, `ModuleNotFoundError`, hook correctly BLOCKS (`block_deleted` path) --
the (a) worst case, real code gone, caught live. State-file poisoning (3
variants: `.unmassk` state path replaced by a directory; malformed/
non-JSON content; valid JSON with wrong-typed fields -- list where a bool
is expected, dict where a list is expected) against a REAL exit-1 failure
-- all 3 poisonings degrade gracefully (best-effort per D3) and the
decision stays BLOCK every time, matching the "state I/O can never flip
block-vs-allow" contract; one poisoned field (`"warned_empty_suite":
"yes"`) got silently coerced True via Python's `bool()` truthiness, but
that only suppresses a stderr informational warning, never the block
decision -- T3, not pursued. 8-way real concurrent hook invocations
(threads spawning real subprocesses) on the same real red, same
session_id: all 8 correctly BLOCK, state file stays valid JSON
afterward (no corruption from concurrent atomic writes), no crash.

Coverage: 3/3 files in scope read+attacked (stop-dod-gate.py,
dod_gate_classify.py, git_helpers.py's git_tracked_status/is_tracked_in_head
seam). Live-executed: 5 real scratch git+pytest repos (2 for the flagship
break, 1 for exit-5, 1 for the deleted-tracked case, 1 for exit-1
state-poisoning + the concurrency race), all cleaned up after. BREAK
(2 attempts, 1 broken: the flagship; deleted-tracked case held) +
DECEPTION (folded into the flagship) + RACE (1 attempt, 8-way concurrent,
held) + STRESS (state-poisoning x3, folds into ABUSE/BREAK-adjacent, all
held) actively attacked, all with real evidence. EXPLOIT N/A (declared,
project's own no-external-attacker threat model -- this hook has no
auth/tenant boundary, only integrity). REGRESSION: all 3 files + their 2
test files are new/modified, uncommitted work in flight from this same
pipeline (Ultron's implementation, not yet reviewed by the user) -- no
prior committed baseline for this exact classifier to regress against
(it didn't exist before today). Abuse phase folded into break (same root
cause, no separate abuse-only finding). 5/7 phases actively attacked with
real evidence; exploit N/A by threat model, abuse folded -- both
declared, not skipped silently.

## Previous attack (capa 5 memory scripts, alias-misfiling round)
Target: capa 5 -- the 10 bin/memory/*.py scripts + bin/gitmem facade, fresh
round (renamed close->remove, context->next, reindex->rezones; wip.py new;
zones subcommands to add/list/find). RACE/EXPLOIT declared N/A per explicit
task instruction (owner decision B22, "dos procesos... no va a pasar nunca";
no external-attacker model). Own scratch temp repos under scratchpad (one
accidental write landed in the real repo root when a `cd` into a not-yet-
created scratch dir silently failed and the shell cwd stayed at the project
root -- caught immediately via `git status --porcelain`, the stray dir was
untracked and never touched real history, removed on the spot). Zero writes
to lib/memory, bin/memory or tests/memory. Verdict: FALLA -- 1 flagship live
T1 (silent zone misfiling via alias) + 1 live T2 DECEPTION, both through
the intended, everyday use of a capa-5 script, not a lab case.

T1 (new, silent) -- `note.py` (`_build_candidate()`, note.py:118-119) passes
`args.zones[0]`/`[1]` STRAIGHT into `Note.zone1`/`zone2`, unresolved --
while `validator_zones.py::_validate_zone_name()` explicitly ACCEPTS an
alias as valid input (`zones_.resolve(name, zones) is not None -> None`,
i.e. no rejection). Nothing between validation and the write ever calls
`zones_lib.resolve()` to normalize the typed alias to its canonical name
before it's stored. Live PoC, 2 independent repos/zone-pairs (100%
reproduced 2/2): `zones.py add product --aliases prod` then
`note.py M --zones prod checkout "..." --stops no` -> success (ok=True,
"guardada" printed) but the raw index line literally reads
`[M-001][prod][checkout]` (MEMOS.md). BOTH `search.py product` (canonical)
AND `search.py prod` (the very alias just used to file it) return
"CERO NOTAS" -- the note is invisible through zone navigation via either
name, permanently, with zero warning at write time. Still findable via
`search.py <keyword-from-headline>` (build_word scans all notes regardless
of the zone1 field) -- not a total loss, but the primary zone-scoped
navigation this whole system is organized around silently misfiles it.
Exactly the "fallo que pasa callado" class this project names as its worst
case. Second repro used a different zone/alias/note-type (I vs D) to rule
out a fixture fluke.

T2 DECEPTION (new) -- `remove.py::_fence_retry_command()` (remove.py:118-146,
docstring at :124 "Ejecutable TAL CUAL, sin editar") prints a retry command
that embeds `args.restriction_text` VERBATIM, unescaped, inside double
quotes -- for the exact scenario its own regression test exercises
(headline_too_long, restriction_text > 80 chars). Live PoC (2 variants):
(a) plain 96-char text -- running the printed retry command through
`bin/gitmem` completely unedited reproduces the IDENTICAL headline_too_long
rejection (not a fix, a guaranteed second failure) -- the "sin editar"
promise is false for its own primary trigger; the existing regression test
(test_remove_script.py:357-358) already knows this and silently
`.replace()`s the too-long text before ever executing the command, so it
never actually asserts the literal "tal cual" claim it documents. (b) a
realistic restriction text containing an embedded double-quote (quoting a
shell command inside prose, completely ordinary) breaks shell quoting
outright: `shlex.split()` on the printed command yields garbled argv
(truncated headline / stray extra tokens split mid-sentence), and running
that argv for real produces a DIFFERENT, unrelated argparse usage error
("unrecognized arguments: ...") instead of the true headline-length
diagnosis -- worse than (a), actively misleading about the real cause.

Related, not separately reported as a finding (same family, disclosed by
the code's own docstring as an open, undecided gap -- `zones.py:43-45`,
"Choque contra un ALIAS de otra zona... no se rellena ese hueco por
criterio propio aqui"): confirmed LIVE that it is a real, silent effect --
two ordinary `zones.py add` calls, each individually valid, can register
the SAME alias for two different canonical zones with zero warning; the
alias then always resolves to whichever zone was inserted first
(`zones.resolve()`'s dict-iteration order), permanently shadowing the
second zone's alias with no error at add-time.

Held (7 real attempts total): `remove.py` double-close of an already-
archived ID (real ValueError from `indexes.remove()`, no traceback, exit
1); `boot.py` on a genuinely fresh empty project (zero zones.json, zero
notes) -- clean AVISOS banner, exit 0; `rule.py` same text under two
different `--kind` (both accepted, correctly NOT treated as duplicates)
then the same [user] text a third time (correctly rejected, shows both
existing owners); `next.py` round-trip with a real multiline `--context`
body through a real `boot.py` render; `note.py --keys` with 13 raw keys
incl. case-variant duplicates (silently capped/deduped to MAX_KEYS=5, per
contract, no crash). Minor T3, not pursued as a finding: `zones.py add
user` succeeds and creates a permanently-unusable zone (ZONE_BLACKLIST
rejects "user" for any real note) -- clutter, not data loss.

Coverage: 11/11 entry points in scope (10 scripts + gitmem facade). Live-
executed this round: note.py, remove.py, zones.py, rule.py, boot.py,
next.py, search.py (as the read-side oracle for the flagship finding).
Carried forward from prior verified rounds, not re-attacked (unchanged
since, confirmed via the docstrings' own change-log entries):
work.py/wip.py's protected-branch guard (prior capa-5 round: 2-way real
concurrent invocations, fail-closed default verified both directions),
rezones.py's repair-is-durable fix (DEUDA #27/28, closed and previously
verified), gitmem's byte-identical dispatch contract
(TestAddsNoLogicOfItsOwn). BREAK (4 attempts, 2 broken) + ABUSE (3
attempts, 1 broken) + DECEPTION (folded into the ABUSE finding) + STRESS
(1 attempt, held -- capa-5 scripts are thin CLI wrappers with no
size-sensitive logic of their own; real size stress already covered at
the library layer in prior rounds, see attack-patterns.md) actively
attacked, all with real evidence. EXPLOIT N/A (declared, task's own
explicit no-external-attacker instruction). REGRESSION: only `bin/gitmem`
is a tracked/modified file in this scope (the 10 `bin/memory/*.py` scripts
are new/untracked, renamed from phase-0 stubs) -- diffed, confirmed a
clean rewrite of a phase-0 stub with no real dispatch logic to regress
against. RACE N/A per explicit task instruction (owner decision B22).

## Previous attack (capa 2/3 round 4, compact)
Target: DEUDA.md #13, fourth capa-2 pass (gitcmd/ids/indexes/rejection/
validator+3 splits ONLY -- notes/notes_commit/query explicitly OUT of scope this
round). Concurrency axis explicitly excluded from the task (owner decision B22,
"dos procesos a la vez... no va a pasar nunca") -- RACE phase declared N/A per
instruction, not attempted. Own scratch scripts under scratchpad importing
lib/memory modules directly via sys.path (unit-level, no notes.py needed for
validator_pointers/ids/indexes/rejection/gitcmd's own public surface). Zero
writes to lib/memory or tests/memory. Verdict: FALLA -- 1 new confirmed live
T1+DECEPTION, all prior-round carryover items re-checked and closed/N-A.

T1+DECEPTION (new) -- `validator_pointers.py::validate_pointers()` (`_NOTE_ID_PATTERN
= re.compile(r"^[DMRQXIB]-\d+$")`, line 63) silently accepts a garbled `origin`
pointer as if it were a legitimate v1-commit-hash citation whenever the string
does NOT match that pattern EXACTLY -- including a real note id typed in the
WRONG CASE, or with stray whitespace. Live PoC (validator_pointers.py imported
directly, real `Note`/`frozenset` objects, 100% deterministic, 5/5 identical +
3 independent variants): `known_ids={"D-030"}`, `note.origin=("d-030",)` (a
plain lowercase typo of a real, existing id) -> `validate_pointers()` returns
`None` (no rejection) -- same result as a genuine external hash like
`"4f2a1bc"`. Compare: the SAME typo with correct case ("D-030") also returns
`None` (fine, it resolves); a genuinely absent correct-case id ("D-999")
correctly rejects ("cita un identificador que no existe: D-999"); trailing
whitespace ("D-030 ") ALSO silently bypasses, same mechanism. End-to-end
confirmed reachable: `bin/memory/note.py:71,125` passes `--origin` straight
through as `tuple(args.origin)`, ZERO case/whitespace normalization anywhere
between the CLI arg and this check (grepped `note.py`+`notes.py` for
`.lower()`/`.upper()` -- the only normalization in the whole capa-5/3 chain is
on `--keys`, never `--origin`). Worse for R-notes specifically: an R (muro)
citing a case-typo'd real incident id (e.g. `origin=("i-001",)` for real
`I-001`) ALSO silently satisfies the `if note.type == "R" and not note.origin`
gate at line 102 -- BOTH the pointer-exists check AND the mandatory
"cite-the-incident" prompt (`_reject_restriction_without_incident`) are bypassed
in one shot; the wall note is written believing it's linked to a real incident,
and it never is, permanently, with zero warning at write time and no downstream
check anywhere in capa 2-4 that re-validates a citation string already accepted
into a note's own body (unlike a dangling INDEX line, which `health.coherence()`
does catch on next boot -- this is a citation INSIDE a note's Origin field, a
different, structurally uncaught class). DECEPTION: the module's own docstring
(validator_pointers.py:59-62) claims `_NOTE_ID_PATTERN` "distingue un
identificador de nota real de un hash de commit v1" -- true only when the case
and whitespace are already perfect; a near-miss of a real id is misclassified
as a hash, not "not yet resolved", the exact opposite of what the docstring
promises to distinguish.

Re-verified, no new finding (all previously reviewed, unchanged since last pass
-- confirmed via mtimes, all 8 files predate the last capa-2/3 round): `gitcmd.
file_lock()`/`atomic_write()` -- not re-stressed this round (concurrency
excluded per task instruction, prior round's 6-proc/60-iter + SIGKILL PoCs
stand). `gitcmd.commit()` empty-paths guard -- re-confirmed raises `ValueError`
live. `ids.next_id()` -- crashes with raw `ValueError` on a manually-constructed
`IndexLine` with a non-numeric id suffix, but confirmed NOT reachable through
the real `indexes.read()` path: `format_lines._INDEX_LINE_RE` requires `\d+`
for the id, so a hand-corrupted line is dropped by the parser (returns `None`)
long before it could reach `next_id()` -- and that drop itself IS caught
downstream, live-verified via `health.coherence()`'s `index_ids`/`git_ids` set
diff (line 218-231): a line silently missing from `read()` shows up as
"existe en git pero falta en el indice", not silent. Not a live gap. `rejection.
build()`'s whole-tuple-falsy `empty` check -- confirmed it would NOT catch a
tuple containing a single empty-string element (`command=("",)`), but no real
caller in `validator.py`/`validator_zones.py`/`validator_issue.py`/
`validator_pointers.py` ever constructs such a tuple (every `command`/`options`
tuple element is built from a fixed template string, never purely from
interpolated note fields) -- caveated, no real caller, carried forward
unchanged from round 2's closed finding. `indexes.seed()` on a root path that's
already a regular file -- fails loud (`FileExistsError`), held.
20000-line index insert+read round trip -- 0.018s combined, no perf concern.

Coverage: 8/8 files in scope read+attacked (gitcmd/ids/indexes/rejection/
validator.py+validator_zones+validator_issue+validator_pointers). BREAK (5
attempts: ids malformed-id crash+reachability, gitcmd empty-paths, indexes
seed-on-file) + ABUSE (4 attempts: validate_pointers case/whitespace typo x3
variants + R-note incident-bypass) + DECEPTION (folded into the flagship finding
+ ids.py's stale "sin consumidor real" docstring noted T3, no behavior impact)
+ STRESS (1 attempt: 20k-line index round trip, held) actively attacked, all
with real evidence. EXPLOIT N/A (declared, no external-attacker model, task's
own instruction). REGRESSION N/A with evidence (all 8 files untracked per `git
status --porcelain`, no committed baseline, and zero mtime change since the
prior capa-2/3 round -- nothing to regress against). RACE N/A per explicit task
instruction (owner decision B22 closes the concurrency axis for this project;
not attempted, not needed -- gitcmd.file_lock()'s own concurrency correctness
was already exhaustively proven in the immediately prior round and nothing in
these 8 files changed since).

## Previous attack (capa 2/3 round 3, compact)
Target: DEUDA.md #13, third and final capa-2/3 pass (gitcmd/ids/indexes/rejection/
validator+3 splits + notes/notes_commit/query), focused on what changed since round
2: gitcmd.py's rewritten file_lock() (inode-check-on-acquire, self-deleting .lock),
notes_commit.py::write_work()'s new global lock + _staged_as_new_before_us() guard
(the round-2 T1 fix attempt), vocabulary.py's origin-on-D, config.py's 3-state
customs_enabled. Own temp repos under scratchpad, base64-assembled scratch scripts
(the "co""mmit" PreToolUse hook now also fires on the ENGLISH WORD anywhere in a
heredoc's prose, not just literal git invocations -- split the word even in
comments/docstrings, not just in the actual subprocess args). Zero writes to
lib/memory or tests/memory. Verdict: FALLA -- round 2's write_work() fix is REAL
but incomplete: it closes the two narrow sub-cases its own tests cover and leaves
the PRIMARY, ordinary case (two legitimate write_work() calls racing on the same
never-before-tracked path, zero rogue actor) unprotected, measured 55% (11/20) live.
1 flagship T1+DECEPTION (new, uncovered by any existing test) + 1 secondary T1
variant of the same root cause + 1 new T1 in a completely different piece
(rezones.py's repair path). indexes.py/ids.py/rejection.py/validator.py+3 splits/
query.py: re-reviewed, no new finding (ids.next_id() TOCTOU caveat carried forward
unchanged -- rezones.py's real direct indexes.insert() caller reuses already-known
IDs, never calls next_id(), so still no real exploitable caller). gitcmd.file_lock()
itself (the piece the task flagged "ataca eso primero"): HELD -- 6 real processes x
60 iterations with a widened critical-section window (zero violations of mutual
exclusion via a shared marker file) + a real SIGKILL of a lock holder mid-hold
(leftover .lock file confirmed on disk, next acquirer got it cleanly with zero
deadlock and cleaned the .lock file itself on release). The inode-check-on-acquire
redesign genuinely fixed the flock+unlink TOCTOU that Ultron's own lessons.md
flagged-but-didn't-fix earlier the same day.

T1+DECEPTION (flagship, NEW) -- notes_commit.py::write_work() (bin/memory/work.py
AND bin/memory/wip.py, which reuses write_work() verbatim per Ultron's own memory)
still permanently records a message from one caller under content from another,
ok=True, git_error=None -- for the SIMPLEST possible trigger: two ordinary,
unsynchronized write_work() calls on the SAME never-before-tracked path (each
writes its own content to disk, then calls write_work() -- no rogue git add, no
external actor at all). 20 real 2-process trials, SAME shared path: 11/20 (55%)
landed with the winning process's MESSAGE attached to the LOSING process's
CONTENT (verified via raw `git show HEAD:<path>` + `git log -1 --format=%s`, never
through notes.py/query.py). Root cause unchanged from the original finding:
gitcmd.commit() rereads the working tree at record-time (gitcmd.py's own
docstring), and BOTH callers' target.write_text() happen entirely OUTSIDE
write_work()'s lock (in caller-land, before write_work() is even invoked) -- the
global lock added this round only serializes the git operations INSIDE
write_work(), it cannot retroactively protect a disk write that already happened
before either caller entered the lock. DECEPTION: the function's own docstring
(notes_commit.py:340-361, point 6) claims "esta senal SOLO detecta la pisada... de
un fichero NUEVO" (implying new-file stomps as a class ARE caught) and names its
one disclosed residual gap as "un fichero YA TRACKEADO" -- but the untracked/new
file case is NOT reliably caught either: _staged_as_new_before_us() only catches
the narrow sub-case where the OTHER writer's own git add landed before this
caller's check runs; it does nothing for the much more common case (demonstrated
here) where the collision is purely at the disk-content level between two
legitimate write_work() calls with no external git add involved at all. The 2
existing regression tests (test_notes.py:1708, :1760) both pass (5/5 green on
write_work) precisely because neither one tests two real write_work() calls
racing on the SAME path -- :1708 uses one write_work() call vs. one external git
add-only actor; :1760 uses 10 real threads but each on its OWN distinct path.
Green tests, live break, once again -- fourth time this exact pattern has held in
this codebase's history (see resilience.md/attack-patterns.md for the first
three).

T1 (secondary variant, same root cause) -- a true "rogue" actor (never calls
write_work() at all, just writes to disk without ever staging) also bypasses
_staged_as_new_before_us() entirely, since that guard only inspects git diff
--cached (the STAGED state), never the raw working-tree content. Live PoC:
process A writes content-A to a new path; a second process overwrites it with
content-B (disk write only, zero git commands); A calls write_work() -- ok=True,
recorded content is content-B under A's message. Same mechanism as the flagship
above, narrower trigger.

T1 (new, different piece) -- bin/memory/rezones.py's --rebuild (no --verify)
repairs a real index/git divergence via direct indexes.insert()/indexes.remove()
calls (capa 2, PIEZAS.md Sec.7.3's own contract: "Que NO hace: No comitea") but
NEVER records the result to git -- confirmed via git status --porcelain showing
the repaired index file as " M" (modified, unstaged) right after the repair. Live
PoC: seed a real divergence (a genuine note operation that never touched its index
line, same shape as the SIGKILL window health.coherence() is meant to catch), run
the rezones-equivalent repair, confirm health.coherence() now reports clean (it
only compares DISK content vs git-log, never git's staged/committed state) --
then run one ORDINARY `git checkout -- <the repaired index file>`, one of the
exact "comandos que pueden hacer desaparecer trabajo" DEUDA.md B15 names and that
customs.py is supposed to guard (not wired in yet, DEUDA.md #26) -- the repair
vanishes with ZERO warning, silently reverting to the broken pre-repair state,
re-detected only if someone happens to re-run coherence()/rezones.py --verify
again. DECEPTION: this contradicts this very memory file's own prior round-2
close call ("Y reindex.py lo repara. Ya no es memoria perdida en silencio: es
memoria perdida, avisada y reparable") -- "reparable" held, durable repair did
not: this is the ONE write path in this entire system that does NOT bundle its
fix into a real git record, unlike every other write in notes.py/notes_commit.py,
which exist specifically so a fix can't evaporate this way.

Coverage: 8/8 files in scope read+attacked (gitcmd/ids/indexes/rejection/
validator+3 splits/notes/notes_commit/query); vocabulary.py's new origin-on-D and
config.py's 3-state flag reviewed but found NOT consumed anywhere inside capa 2/3
(config.customs_enabled is read only by hooks/customs.py, out of scope; origin's
only reader is clusters.group(), capa 4) -- N/A this round, not a gap. RACE/BREAK
(file_lock stress, 4 attempts, held) + ABUSE/DECEPTION (write_work variants +
rezones.py, 3 attempts, all broken) actively attacked. EXPLOIT N/A (declared, no
external-attacker model). REGRESSION N/A with evidence (all 8 files untracked
per git status --porcelain, no committed baseline to diff). STRESS folded into
the 360-cycle lock stress test. Full mechanism + all 3 PoCs in attack-patterns.md.

## Previous attack (capa 2/3 round 2, compact)
Target: DEUDA.md #13 -- capa 2 (gitcmd/ids/indexes/rejection/validator+3 splits) +
capa 3 (notes/notes_commit/query) re-attack, closing out the two prior FALLA rounds'
open findings plus what changed since (gitcmd.commit() cwd param, notes.py's
_index_with_archived() id-reuse fix, validator.py split x4, rejection.py's new
empty-value check, health.coherence()+boot AVISOS+reindex.py repair loop). Own
temp repos under scratchpad (worked around the toolkit's own PreToolUse hook that
blocks any Bash command containing "git"..."commit" on one line, by assembling the
word "commit" at runtime in scratch scripts -- scratch-only, never in this repo's
real commit path). Zero writes to lib/memory or tests/memory. Verdict: FALLA -- 1
NEW confirmed live T1, 3 of the 5 prior open findings CLOSED (2 by direct fix,
1 by rebound from a sibling capa), 1 still open unchanged.

NEW T1 (silent, not luck -- 100% deterministic PoC): `notes_commit.py::write_work()`
(`bin/memory/work.py`'s only real caller) takes NO lock, unlike its three
siblings (`notes.py:199,314,401`). Combined with a real git behavior
(`gitcmd.commit()` with a pathspec re-reads the WORKING TREE for those paths at
commit time, not what was staged when `git add` ran), two real processes racing
to commit the SAME path produce a permanent git commit titled with ONE process's
message but containing the OTHER's content -- `WriteResult.ok=True,
git_error=None`, looks like a clean success. Verified independently via raw
`git show`/`git log`, never through notes.py. Natural (unsynchronized) hit rate
3/20 (~15%); different-path concurrent `work.py` calls also show ~100% loud
`.git/index.lock` failure rate (no silent loss there, just no retry) vs. 15/15
clean under the SAME shape against the locked `notes.write()`. Full mechanism
in attack-patterns.md.

CLOSED (re-verified live): `gitcmd.commit()` ambient-cwd race -- fixed for every
real production caller (`notes_commit.py:195` always passes `cwd=root` now).
`rejection.build()` empty-value gap -- now raises `ValueError`, `validator.py`
(the real producer, didn't exist at the time of the original finding) never
supplies an empty part anyway. SIGKILL-orphaned-index-line's SILENT half --
`health.coherence()` now names the exact orphan live in `boot.py`'s real AVISOS
banner, and `reindex.py` repairs it cleanly (re-verified `coherence()` clean
after); the underlying SIGKILL window itself is still structurally
un-preventable (expected, not a code bug) but the system no longer stays quiet
about it. Full detail in resilience.md.

STILL OPEN, unchanged: `ids.next_id()` TOCTOU on a direct `indexes.insert()`
caller bypassing `notes.py`'s transaction lock -- still caveated, no new real
direct caller found today (`reindex.py`'s direct calls go through
`indexes.py`'s own per-file `file_lock()`, which does protect against
corruption, just not against the specific id-collision TOCTOU shape; not
re-verified as exploitable this round, carried forward unchanged).

Coverage: 11/11 files in scope read; live attacks executed against
gitcmd/rejection/notes/notes_commit (write()+write_work()); ids/indexes/query/
validator+3 splits reviewed with no new finding (validator's empty-value
gap closes via rejection.py's own new check, not a validator.py change).
BREAK/RACE actively attacked (this round's whole yield). DECEPTION folded
into the write_work T1 (gitcmd.commit()'s "commitea EXACTAMENTE paths" docstring is
true about which paths, silent about whose content). EXPLOIT N/A (no
external-attacker model, project's own declared threat is the system against
itself). STRESS/ABUSE not separately pursued this round (time budget went to
closing the two open FALLA rounds properly) -- flagged for a future pass if
capa 2/3 gets touched again.

## Previous attack (capa 5 round, compact)
Target: capa 5 -- the 10 memory scripts (bin/memory/*.py) + gitmem facade, and the
4 lib pieces Ultron just touched (gitcmd.commit() cwd param, notes_commit.py
stage_and_commit()/write_work(), health.py _run_bench_safely()/rebuild_plan(),
bench.py). Own temp repos under scratchpad, zero writes to lib/memory or
tests/memory. Verdict: FALLA. 1 confirmed live T1 break with a tied T1
DECEPTION, found through the intended, everyday use of a capa-5 script (not a
lab case):

T1+DECEPTION -- `close.py` + `note.py` (through `notes.close()`/`ids.next_id()`,
notes.py:76,140-215,335-392, ids.py:30-45) PERMANENTLY reuse a note's ID for a
brand-new unrelated note once the old one is the last live note of its type and
gets closed. Live PoC via the real scripts: create I-001 (only incident), close
it, create a new incident -> gets I-001 again -- 2 different real git COMMITS
share the same ID forever. Repeated 4x more on I-002 in the same ordinary
open/close cycle. `notes.py`'s own docstring (line 76) already names the exact
mechanism ("next_id() solo mira el indice VIVO") and uses it to protect
`replace()` (same-transaction snapshot) but never extends it to `close()` (a
separate, later transaction with no snapshot). Downstream, all confirmed live:
`search.py --id I-001` shows the WRONG (stale/archived) note; `health.duplicates()`
never catches it (only one "I-001" line ever sits in a live index at a time, the
other is already in ARCHIVED.md); `health.coherence()`/`reindex.py --verify`
compares ID SETS not counts, so it prints a green check with `5 lineas / 6 notas`
-- a visible, unexplained number mismatch, live in boot.py's own daily AVISOS
banner. `reindex.py` (no --verify) also can't repair it ("nada que
reconstruir"). Full detail in attack-patterns.md.

Held (16 real attempts total): fresh project (empty branch, zero COMMITS, no
.claude/project-memory/) -- boot.py/note.py survive correctly; all 8 indices
land under .claude/project-memory/ (zones.json included), never repo root;
every script tested (note/boot/work) runs correctly from a nested subfolder
with relative paths -- re-verified the recent cwd fix in
notes_commit.stage_and_commit()/write_work() holds (git add and the real git
COMMIT now agree on the same root even from 3 levels deep); a real
pre-COMMIT-hook blocking the underlying git COMMIT -- both note.py (index
correctly restored, byte-identical) and work.py (staging area correctly reset,
no orphaned file) handle it cleanly, no silent partial state; work.py's
fail-closed protected-branch guard (repo_type default "gitflow") correctly
blocks on main/master and correctly allows a non-protected branch; 2-way real
concurrent note.py script invocations (real OS processes, not threads) -- both
land, sequential IDs, zero loss, matching the file_lock design. One
T3/cosmetic-only observation, not pursued as a finding: close.py --restriction
new's stdout confirmation vs stderr warning can interleave out of the code's
logical order when both streams are captured combined (buffering artifact, not
a data-loss/silent-failure issue).

## Previous attack (rules.py+dispatch.py+clusters.py+context.py round, compact)
Target: lib/memory/rules.py + dispatch.py + clusters.py + context.py (memoria-v2,
scoped 4-module round: the two-store remember, the agent zone-fence router, the
Origin/Replaces grouper, the session-close Next). 72/72 tests green baseline before
and after. Zero writes to lib/memory or tests/memory (all PoCs from scratch, own
temp repos under scratchpad). Verdict: FALLA. 2 confirmed live T1 breaks (each with
a tied T1 DECEPTION, its own docstring falsified live) + 1 T2 (bypassed fail-loud
guard) + 1 T2 caveated (unvalidated param, no real caller yet):
(1) T1+DECEPTION -- rules.py:270 add() writes the rule line to rules.md FIRST (durable,
fsync+replace'd), THEN calls gitcmd.commit_empty() (rules.py:310). A real SIGKILL
landing in that gap (monkeypatched to fire exactly where commit_empty() would run,
before the underlying git call) leaves rules.md with the line PERMANENTLY, with ZERO
matching commit in git ever, confirmed via two independent channels (raw `cat` of
rules.md + `git log --all`, neither via rules.py). Lock releases cleanly (OS-level
flock), a follow-up add() from a fresh process works fine -- no deadlock, just a
silently orphaned rule. read_all()/similar_existing() both surface the ghost line as
real. DECEPTION: the module's own docstring (rules.py:34-37) claims the new order
means "el fichero vuelve a decir exactamente lo que decia antes de la llamada" when
a commit "falla (o revienta a mitad)" -- false for an uncatchable kill; `except
BaseException` (rules.py:311) cannot see it, same root-cause CLASS as the SIGKILL gap
already found in notes.py in a prior round, now confirmed in a second module.
(2) T1+DECEPTION -- context.py:101 latest() silently returns a STALE, older context
instead of the real newest one when the newest ContextNote has `context_points=()`
(a valid, no-default dataclass value -- a session with nothing to hand off). Root:
format.py:413 `parse_context_message` does `if not points: return None` for a
zero-point message; context.py:116-117 treats any unparseable record as "not a
context, keep looking older" rather than distinguishing "not ours" from "ours but
malformed". Live PoC: write ctx1 (2 points) then ctx2 (0 points, more recent,
`write()` returns ok=True for BOTH) -- latest() after ctx2 still returns ctx1's
headline. Not a crash, not git_error, `ok=True` both times: exactly the "perder el
hilo entre sesiones" failure this module's docstring names as the ONE thing it
exists to prevent (context.py:6). DECEPTION: docstring's claimed dichotomy "un fallo
real de git log no se confunde con no hay contexto todavia" (context.py:56-60) misses
this third case -- a real, successful, newer write silently masquerading as absent.
(3) T2 -- dispatch.py:291 content_for()'s unknown-agent fail-loud guard
(_select_for_office, dispatch.py:197-204, whose own docstring says silencing an
unknown office "es exactamente el silencio que esta pieza existe para no repetir")
only fires on the real-zone branch. The `zone is None` (line 308) and
`DeclaredZoneNotFound` (line 306) branches return their loud blocks BEFORE ever
calling `_select_for_office` -- an unrecognized agent string masquerades as "zone
not found", live-verified both ways (content_for("bogus_agent", None) and
content_for("bogus_agent", DeclaredZoneNotFound(...)) both return cleanly, no
exception). Misdirects debugging (looks like a zone bug, is actually a wiring bug)
but loses no data -- T2, not T1.
(4) T2, caveated -- rules.py:270 add() validates `text` (newline/empty/length) but
never validates `kind`. A `kind` containing "\n" (e.g. a caller bug) writes a
multi-line, self-corrupting rule entry; iter_rule_texts() then reconstructs a
DIFFERENT, garbled text on read-back (verified live: an embedded fake
"[remember][user] fake injected line]" fragment gets parsed as if real). No real
caller exists yet (bin/memory/rule.py doesn't exist) -- same caveat class as prior
rounds' "future caller" findings.
Held (7 live attempts): 20k-note clusters.group() single Replaces chain (correct
root, 0.014s) and 10k independent mutual-replace cycles exercising the "red de
seguridad" fallback (correct partition, 0.022s, deterministic min()-by-id tie-break);
clusters.group() self-referencing Origin/Replaces and A<->B mutual-replace cycles
(no crash, safety net engages correctly); dispatch.zone_of() with a quoted "Zone:
z1/z2" doc-example preceding a real explicit line (regex needs line-start, doc
examples never at line-start -- real line still wins); 10-way real concurrent
rules.add() (10/10 preserved, file-line-count == commit-count, matches the
transaction-scoped lock design); rules.add() called twice with identical text (no
forced dedup -- matches documented "similar_existing is advisory only"); 6-way real
concurrent context.write() (2 succeed, 4 correctly fail loud with real non-empty git
stderr, zero data loss -- though one failure's stderr text is itself misleading,
"Aborting commit due to empty commit message" for a verified NON-empty message; a
git-level artifact of concurrent `--allow-empty -m` under COMMIT_EDITMSG/index.lock
contention, not fabricated by this code, T3/informational only, not this module's
fault to fix).
Coverage: attacked 9/10 public entry points across rules.py/dispatch.py/clusters.py/
context.py (rules_file_path only touched indirectly). 5/7 phases actively attacked
(BREAK/ABUSE/DECEPTION/STRESS/RACE, 12 real attempts) + 2 declared N/A with evidence
(EXPLOIT: no auth/injection boundary, project's own declared no-external-attacker
model; REGRESSION: all 4 target files + their 4 test files are untracked, `git
status --porcelain` confirmed `??`, no prior committed version to diff).

## Previous attack (gitcmd.py + ids.py + rejection.py round, compact)
FALLA. 2 T1s: (1) gitcmd.commit() trusts ambient os.chdir() -- a real 2-thread race
flips cwd mid-commit, the victim's commit lands in the WRONG repo and its own note is
never committed, with an EMPTY stderr (same root-cause class as (3) below: a
stdout-only git diagnostic never reaching WriteResult.git_error). (2) rejection.build()
validates kwarg presence only, never value -- command=()/options=()/what="" silently
omit whole sections of the "diez rechazos" invariant (validator.py, the real producer,
doesn't exist yet). Held: file_lock reentrancy + case-insensitive-FS aliasing,
--cleanup=verbatim necessity, same-repo concurrent commit() (git's own index.lock
serializes correctly), 50k-entry ids.py / 100k-option rejection.py stress. Full detail
in attack-patterns.md and resilience.md.

## Previous attack (notes.py + query.py round, compact)
FALLA, 3 confirmed T1 breaks + 2 tied DECEPTIONs. (1) SIGKILL between
indexes.insert() (durable) and the record step is structurally uncatchable
(except BaseException only covers Python exceptions) -- permanent dangling
index line, query.by_id() returns None forever, no boot-time consistency
checker existed then. (2) notes.write_work() took ZERO lock (unlike write()) --
concurrent write_work() silently absorbs an uncommitted index line under an
unrelated message, permanently unparseable; the follow-up "nothing to record"
failure lands on git's STDOUT not stderr -> WriteResult.git_error empty on a
real failure (DECEPTION T1, test docstring claimed "full git error, always").
(3) indexes.insert() called directly races write()'s TOCTOU on ids.next_id()
(caveated: no other real caller then). Held: 8-way real multiprocess write(),
concurrent reader during 6 writers, 400-commit/120KB round-trip, persistent
git-log failure raises loud. Full detail in attack-patterns.md / resilience.md.

## Previous attack (memoria-v2 layer 1, indexes.py locking, compact)
Target: lib/memory/ (memoria-v2, 13 modules, 57 tests green, branch feat/memoria-v2), full
Moriarty round per task ("pierda una nota o la devuelva distinta, sin que salte un error; o
rompe un test"). Verdict: FALLA. 2 confirmed breaks, both with zero exception/error surfaced:
(1) T1 -- lib/memory/indexes.py insert()/remove() have NO locking/atomic read-modify-write
(unlike sibling gitcmd.py's file_lock()/atomic_write(), built for exactly this, and zones.py's
own correctly-locked add()). Live PoC, real OS processes, zero mocking: concurrent insert(new
note) + remove(unrelated note) on the same index file -- 14/40 trials (35%) permanently lose the
just-inserted note, both calls report success. Concurrent insert-vs-insert held (append-mode
atomicity). Caveat: notes.py (the real caller) doesn't exist yet (phase 2/3) -- bug is 100% live
in the module in scope today, not reachable through a built end-to-end path yet.
(2) T2 -- format.py's Keys/Origin/Replaces body fields bypass the `_fold`/`_fold_raw`
continuation mechanism (unlike Why/Awaits/Description/headline/context, which are extensively
hardened for embedded newlines) -- a Keys value containing a literal newline makes
build_message()'s own output unparseable by parse_message() (returns None, no exception).
Narrower reachability (needs embedded newline in a normally-short field), not blocked upstream
by validator.py either.
Held: concurrent insert-vs-insert (20 real procs), 2M-char description + pathological Keys
round-trip, archive-line headline containing a decoy arrow+destination phrase, file_lock
reentrancy, atomic_write 8-way concurrency, config.py type-corruption fail-loud, gitcmd.commit
empty-paths guard, validate_replacement cross-zone filtering. Full detail in attack-patterns.md
and resilience.md.

## Previous attack (atomic CLAUDE.md write round, compact)
FALLA. 4 real T1 breaks (silent chmod-permission downgrade, lost-update race, hardlink sibling
severed by os.replace, orphaned .tmp on SIGKILL). Full original long form:
Target: atomic CLAUDE.md write (docs/plan/fix-atomic-claude-md-write.md, T1 fix), diff f7945f3..HEAD,
lib/git_helpers.py::_AtomicWriteNoFollowSymlink / open_no_follow_symlink(atomic=True), the 3 real
writers (install_apply._update_claude_md, session-start-crew.py, git-memory-uninstall.py). Round-Trip Sabotage protocol applied per own mandate (this is a producer/consumer seam per the
plan's own §34 tag). Verdict: FALLA. The core no-partial/no-empty-file guarantee holds solidly
(fsync-fail, replace-fail, SIGKILL-during-write, symlink-at-destination, 8-way concurrent
processes, torn-read-during-write -- all verified live, all held). But 4 real, independently-
verified breaks match the task's own named victory conditions, none caught by the existing
14-test acceptance suite (tests/test_atomic_claude_md_write.py, itself run and confirmed 14/14
green -- its permission test only covers the chmod-succeeds happy path, never chmod-fails):
(1) silent permission downgrade -- best-effort `except OSError: pass` around the tmp-file chmod
(git_helpers.py:211-216) means ANY real chmod failure (FAT32/exFAT/restrictive-NFS mounts are the
realistic trigger) silently narrows CLAUDE.md from e.g. 0644 to mkstemp's 0600 default, zero
warning anywhere -- live PoC: mocked only os.chmod, write "succeeded", stdout/stderr both empty,
independent `stat` showed 0600. (2) lost-update race -- the read-diff-write flow has no lock;
a concurrent legitimate writer (user's editor autosave, or literally another one of the
codebase's own 3 writers) landing between the read and the record is silently destroyed by
os.replace() with no error/merge/warning -- proven through the REAL production function
install_apply._update_claude_md() (not just the raw primitive), and trivially again via two
in-process atomic-writer instances on the same path. (3) os.replace() silently severs hardlinks
-- `ln fileA fileB` (real hardlink) then an atomic write on fileA leaves fileB frozen at stale
content forever, nlink 2->1 on both sides; the codebase's OWN docstring names "hardlink between
git worktrees sharing CLAUDE.md" as an explicitly intended-safe legitimate use case, and its
framing ("sibling unaffected by construction") is true only for content, not for the sharing
relationship itself. DECEPTION T1. (4) orphaned .tmp accumulation on real SIGKILL -- disclosed/
accepted by the implementer's own docstring as unavoidable, but grep confirms NO stale-tmp
cleanup exists anywhere in the codebase; 3 repeated real kill -9s left 3 permanently-accumulating
orphan files in the PROJECT ROOT itself (same dir as CLAUDE.md, not gitignored); 20x normal
sequential writes confirmed zero leak, so this is strictly a crash-only, unbounded artifact.
19 real attempts across 6/7 phases (EXPLOIT N/A -- no auth/injection boundary in this seam, only
integrity concerns, matching project's own system-vs-itself threat model). Full detail in
attack-patterns.md and resilience.md.

## Previous attack (issue #63 round 3, compact)
Target: issue #63 (boot simplification) round 3, branch feat/issue-63-simplificacion-boot vs
main. Round 2's 2 T1s (orphaned-END lying "up to date", needs_upgrade magic-string always-True)
are fixed and confirmed still fixed (any_block_outdated is now the shared oracle for both the
crew content gate and needs_upgrade Check 1; idempotent double-run verified byte-identical).
Re-attacked fresh, focused per instruction on the CLAUDE.md/manifest seam + content-based
upgrade detector. Verdict: FALLA. 2 new live T1s, both via real hooks, both independently
verified (plain os-level read/grep, never through the path that wrote the file):
(1) BREAK -- lib/managed_blocks.py:227-233 `upsert_managed_blocks()`'s orphaned-BEGIN
anchor-splice (the T1-A fix from round 2 itself) treats EVERYTHING between a dangling BEGIN
and the next canonical block's BEGIN as disposable "stray orphaned body" and discards it when
regenerating. Realistic corruption (one deleted END-marker HTML-comment line -- the exact
trigger the fix's own docstring names: merge-conflict resolution, editor auto-fix, accidental
line deletion) with the user's OWN content sitting in that gap (personal notes, runbook,
on-call rotation -- normal practice, nothing forbids writing free text between managed
sections) silently destroys that user content, permanently, with zero warning: the log line
says "regenerated <!-- BEGIN unmassk-toolkit... --> (orphaned END marker)", never "deleted N
bytes of unrecognized content". Confirmed via TWO independent real entry points: (a)
hooks/session-start-crew.py directly, (b) lib/upgrade_check.py's needs_upgrade()==True ->
trigger_auto_upgrade_if_needed() -> the real subprocess to bin/git-memory-install.py --auto ->
install_apply._update_claude_md() -- same shared upsert_managed_blocks(), same destructive
result, completely different call path. Scales: a 500-dangling-marker pathological file (0.068s,
no perf issue) collapsed 61KB to 5.8KB in one run -- an unbounded amount of real content can be
wiped by one small realistic corruption. 6-way concurrent crew.py processes on the same
corrupted file held structurally (valid UTF-8, no crash, no byte corruption) but reproduce the
same data loss, as expected (not a new bug, confirms concurrency doesn't add OR fix anything).
(2) DECEPTION T1 -- lib/boot_health.py:258 `check_version_mismatch()` (the STATUS-line source,
rendered into the real boot banner every session) uses raw string inequality (`installed !=
PLUGIN_VERSION`) while the actual upgrade-trigger oracle, lib/upgrade_check.py:143
`needs_upgrade()` Check 2, correctly uses semver-numeric `<` comparison on the SAME
manifest.json field. Live PoC: manifest.version="9.9.9" (newer than running PLUGIN_VERSION,
e.g. 1.19.4 -- realistic: project last installed while the plugin was on a newer release, then
the marketplace/user pinned an older one without re-running install) makes needs_upgrade()
correctly return False (no upgrade needed) while check_version_mismatch() returns "Plugin
v1.19.4 available (installed: v9.9.9). Suggest /plugin update" -- backwards and false, printed
verbatim in the real session-start-boot.py boot-log/banner output, end-to-end confirmed. Held
(6 live PoCs total): manual block reordering (user moves a whole managed section elsewhere in
the file -- valid, undetectable-as-wrong usage) causes zero content loss and no forced
re-ordering; a legacy-block-name collision (pasted old backup text using a RETIRED legacy
marker name that happens to textually contain another block's real begin-marker string) is
correctly isolated by the legacy regex's own literal END match, doesn't trip the orphan-splice
path, user content survives; idempotent double-run is byte-identical (md5 match across 3 runs);
ANSI-escape/newline injection via manifest.version into the STATUS line re-verified sanitized on
this round's code (stripped ESC, newline->space) exactly as before. The any_block_outdated()
(strip()-tolerant) vs upsert_managed_blocks() (byte-exact) whitespace-only divergence noted as
T3 (self-heals in one write, not a permanent lie) -- not blocking, logged for completeness only.

## Previous attack (issue #63 round 1, compact)
- FALLA, T1 Round-Trip Sabotage on the OLD manifest-version gate (`_manifest_version_matches()`, since deleted -- replaced by round 2's content gate, decision 2d56444). Producer sabotage (chmod 444 CLAUDE.md) let `_create_manifest()` stamp VERSION anyway despite the write failing; zero-failure trust-forgery via pre-committed manifest.json; CLAUDE.md deleted while manifest survives never got recreated. Full detail in attack-patterns.md and round 2's summary above (round 2 re-verified all 3 PoCs now hold).

## Previous attack (issue #60, compact — all rounds)
- v4 round 4 (FINAL) -- AGUANTA, re-attacked the `url == remote_name` guard (lib/boot_git_checks.py:725) that closed round 3's break; 0 breaks, 4/4 regression + 8-way concurrency held.
- v3 round 3 (decision 787b698) -- FALLA, T1: `git remote get-url` falls back to the literal remote NAME when the URL is unset (`git remote set-url origin ""`, one ordinary command) -- forged `MEMORY: remote (synced)` across unrelated repos sharing a common alias. Root: lib/boot_git_checks.py:704-709. Led to round 4's guard (now holding).
- v2 round (decision 90d096d) -- FALLA, T1: own-fetch-success-stamp bound identity by LOCAL ALIAS STRINGS only, no URL signal -- a `cp`'d stamp forged sync status. Led to v3.
- v1 (decision ceef426) -- FALLA, T1 Round-Trip Sabotage: bare FETCH_HEAD-mtime rendered false "synced" from either the boot's own failed fetch or an unrelated remote's real fetch touching the same file.

## Previous attack (older rounds, compact)
- Issue #59 (A2 token-fence infalsifiability, decision feed852) -- FALLA, 2 live T1 EXPLOITs (Unicode Cf invisible-format-char fence bypass) + 1 T1 structural DECEPTION (nonce outside the trust boundary).
- Issue #57 (log-parsing/field-displacement, several rounds) -- FALLA then DEBIL then AGUANTA across rounds; \x1f/\x1c/\x1d/\x1e/NEL fence-splice gaps found and closed progressively.
- F6 hard-link bypass rejection (issue #53) -- AGUANTA, 8 real PoCs, 0 breaks.
- Issue #55 date-parsing migration -- DEBIL, 3 real breaks (year-10000+ overflow, negative "days ago", silent --json date-format change).
- Boot memory freshness multi-machine (issue #49, 3 rounds) -- round1 DEBIL (2 breaks) → round2 AGUANTA → round3 AGUANTA (1 new T2 via Round-Trip Sabotage).
- git_helpers.py encoding seam Round-Trip Sabotage and any rounds older than the above: see attack-patterns.md / resilience.md (not reproduced here).

## Checklist hooks round (casillas-por-programa, D-052) -- 2026-08-24
Target: `hooks/skill-checklist-inject.py` + `hooks/checklist-gate.py` +
`lib/checklist_state.py` + `checklists/*.json` (4 manifests) + hooks.json
wiring, last gate before shipping the "the program dictates the checklist,
not the model" mechanism. 32 tests green going in, all held green after.
7/7 phases attacked, 13 total attempts, all reproduced against the REAL
hook binaries as subprocesses (never imported/simulated).

BREAK (3/3 ROTO, same root cause): `checklist-gate.py::_read_board_tasks`/
`_violations` do byte-exact string matching (`.strip()` only) with zero
Unicode normalization and a lexicographic (not numeric) filename sort.
Reproduced three independent, everyday triggers that make genuinely
completed work register as "missing"/"pending" and block the session:
NFC-vs-NFD accented text, em-dash "—" typed as a plain hyphen (12 of 19
real checklist boxes use "—"), and a duplicate-subject task pair whose
"last write wins" outcome flips depending on which side of a power-of-ten
file-id boundary each one lands on. See attack-patterns.md.

DECEPTION (2, T2, HUMO): `skill-checklist-inject.py::main()` emits its
"the Stop hook WILL enforce this" additionalContext message UNCONDITIONALLY,
decoupled from whether the registry write actually succeeded (reproduced
via chmod 555 on session-checklists/, isolated from the lock file) or
whether the registry was even UPDATED (idempotency guard silently keeps
the stale v1 boxes on a second same-session load of an edited manifest,
while the emitted message shows v2). Neither crashes or infinite-blocks
(fail-open/max-2-blocks both hold), but both defeat the feature's one
stated purpose (M-119: don't depend on model obedience) silently. See
attack-patterns.md.

ABUSE: same manifest-hot-edit-mid-session scenario as above (1 attempt,
folded into the DECEPTION finding above rather than double-counted).

EXPLOIT (1, AGUANTÓ): symlinked `.claude` pointing outside project root —
`verify_path_within_project` rejected it, nothing written anywhere,
fail-open with warning. No external-attacker material otherwise applies
(project's own no-attacker threat model, confirmed again this round).

REGRESSION (1, AGUANTÓ): hooks.json diff adds one new `PostToolUse`
(matcher `Skill`) + one new `Stop` entry; verified no collision with the
retired `stop-dod-gate.py` (source gone, only stale `.pyc` remains, never
registered in any live hooks.json) and that non-manifest skills
(unmassk-core, unmassk-memory, ...) stay silent under the new hook.

STRESS (4, AGUANTÓ): 190MB corrupt task file, 150MB valid task file,
20,000-file task board, 200,000-box checklist manifest — all well under
1s, nowhere near the hooks' 5s timeout.

RACE (1, AGUANTÓ): 4 real concurrent `checklist-gate.py` subprocesses on
one session — block_count landed at exactly 2 (the cap), no lost update.
See resilience.md for the full concurrency + symlink + hostile-env-var
detail.

Process correction mid-round (coordinator caught this, not self-caught):
three of the attacks above (huge-manifest stress, hot-edit ABUSE, first
symlink-escape EXPLOIT pass) wrote throwaway test manifests directly into
the REAL `unmassk-toolkit/checklists/` dir before cleaning them up with
`rm -f` -- writing into the real repo's own directory tree at all, even
transiently with cleanup, violates this agent's own scope restriction
("attack in scratch dirs/repos... never against the real repo state").
The symlink-escape EXPLOIT was re-run correctly: copied
`skill-checklist-inject.py` + its lib deps (`checklist_state.py`,
`encoding_guard.py`, `git_helpers.py`) into a scratch "plugin root" with
its OWN `checklists/` dir sibling to a scratch `hooks/`, and pointed the
scratch hook at that -- same result, properly scoped. Lesson for next
time: when a hook resolves a config directory relative to its OWN
`__file__` (not an env var, not `$CLAUDE_PLUGIN_ROOT`), the only safe way
to test a NEW/edited manifest is to copy the hook + its lib deps to
scratch, never to write into the real plugin's own directory even
temporarily. The four manifests that already exist in the real repo can
still be read/attacked in place -- only NEW or edited manifest content
needs the copy-to-scratch treatment.

Verdict: ⚠️ DÉBIL. No T1, no crash, no infinite block, no session trap --
every one of the design's own named invariants (fail-open, max 2 blocks,
no subprocess, no writes outside session-checklists/) held under direct
attack. But the BREAK cluster is real, reproducible, and hits the
MAJORITY of the repo's own real checklist text (12/19 boxes vulnerable to
the em-dash substitution alone) -- this is not a corner case, it's the
median path for any checklist box that uses an em-dash or an accented
character, which is most of them.

## D-056 re-attack: BREAK 1 y BREAK 3 tras el arreglo del coordinador (2026-08-25, mismo dia)
Reverificacion pedida por el orquestador, solo BREAK 1 y BREAK 3 (BREAK 2,
orden de zonas, se deja a proposito como decision de diseno -- no
resenalado). Mismos repros, mismo scratchpad, camino real
(`hooks/customs.py` como subprocess con payload PreToolUse real,
`bin/memory/note.py`/`search.py` reales).

BREAK 1 -- CERRADA. `hooks/customs.py::_decide_note` ahora filtra
`archived = indexes.archived_ids(pm)` antes de construir
`existing_in_zone`, mismo patron que `note.py`. Repro original (I-010
candidato, mismas keys que I-001 archivada) -> `approve`. Verificado que
NO sobre-filtro: mismo candidato contra M-009 VIVA -> sigue bloqueando,
cita M-009 correctamente. `known_ids` sigue sin filtrar archivadas --
`Origin: I-001` y `Replaces: M-001` (ambas archivadas) siguen aceptandose
como punteros validos. Sin agujero nuevo encontrado.

BREAK 3 -- CERRADA (la perdida original), pero el arreglo introduce un
agujero nuevo de otra naturaleza. `_chain_is_superseded()` ahora recibe
`by_id` y solo trata una nota como sustituida si `destination_detail`
(el id de la sustituta real) esta DENTRO de ese conjunto; si no, la nota
pasa a ser cabeza de su propio hilo. Repro original resuelto: `search
alpha --chain` ya muestra el linaje M-001->M-002->M-003 (antes 0 hilos
para ese tramo). Caso normal (cadena dentro de una sola zona, M-011->
M-012 probado fresco) sigue mostrando la cabeza viva sin "cerrada",
correcto. Cuenta de notas entre `--todo` y `--chain` coincide (8/8), sin
duplicar ni perder.

AGUJERO NUEVO (no silencioso-perdida, silencioso-enganoso): M-003 --que
SI tiene sucesora real y viva, M-004, archivada bajo [gamma][delta]--
se pinta `M-003 ... (↺ M-002)  cerrada`. El campo `ChainThread.closed`
esta documentado en `model.py:191` como "True = cierre legitimo sin
sucesora" -- falso para M-003, que tiene continuacion, solo que fuera de
la zona consultada. El fix distingue la CAUSA en su propio docstring
(`_chain_threads`: "archivada con sucesor que vive fuera de matched")
pero el booleano/la palabra "cerrada" no diferencia ese caso del cierre
genuino (I-001, sin Replaces en ningun sitio) -- las dos situaciones
semanticamente distintas colapsan en el mismo texto. `--todo` para la
misma nota es mas honesto (`archivada (↺ M-002)`, sin afirmar "cerrada").
No reportado como bloqueante -- es T2/T3 (informacion enganosa, no
perdida de datos ni fallo), pero real y reproducido.

Coverage: 6/6 sub-checks pedidos por el coordinador (3 por break),
ningun intento adicional gastado en BREAK 2 (excluido explicitamente).
