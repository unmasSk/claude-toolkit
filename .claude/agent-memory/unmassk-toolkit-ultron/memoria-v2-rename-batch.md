---
name: memoria-v2-rename-batch
description: Command renames (remove/next/rezones/wip), NEXT format change, English arranque labels, bash-hook text-match gotcha for demos, gitcmd file_lock TOCTOU race, B20 dispatch/inject retirement doc-sweep checklist
metadata:
  type: project
---

Session 2026-08-03: renamed `close→remove`, `context→next`, `reindex→rezones`
(only the `bin/memory/*.py` SCRIPT + `gitmem` subcommand names change — the
underlying `lib/memory/context.py` MODULE keeps its name, since only
`context.py`'s bin-script twin was renamed). Deleted `bench` entirely
(script+lib+HealthReport fields `bench_caught/bench_total/bench_failures`+
its boot.py render line+its 2 test files) and removed `boot` from `gitmem`'s
subcommand list (arranque no longer manual — `bin/memory/boot.py` itself is
untouched, still called directly by `hooks/boot_launcher.py`). Added `wip`
(`bin/memory/wip.py`, subcommand `gitmem wip`) reusing `notes.write_work()`
verbatim — deliberately does NOT repeat `work.py`'s main-branch protection
(not asked, flagged instead of added unilaterally per Deviation Rules).

**ContextNote model changed shape**: `context_points: tuple[str,...]`
(bullet list) → `context: str` (single prose string). New commit format:
`[NEXT] {emoji} {headline}\n\nKeys: ...\nContext: {prose, foldable like
Why/Description}` replacing the old `⏩ {headline}\n\nContext:\n- point\n-
point`. The NEXT emoji itself changed `⏩`→`🧭` (owner decision, confirmed by
cross-checking COLA.md — a decision-log doc — showing the same literal
`[NEXT] 🧭 ...` example twice independently before I touched anything; if a
literal contradicts an established TEXTOS.md glossary entry, check COLA.md
first, it's the authoritative "what the owner actually said today" log).
`CHANNEL_EMOJI` in `emojis.py` is the single source for all three
(`next`/`rule`/`wip`) — never hardcode the glyph a second place
(`validator._WIP_MARKER = emojis.CHANNEL_EMOJI["wip"]`, not a literal).

**HealthReport gained `archived_notes: int`** so boot's coherence line can
show `"{live} live + {archived} archived / {total} notes"` instead of a
bare `"{lines} lines / {notes} notes"` that silently didn't add up when
notes were archived (archived notes are removed from the live index but
still count in `git_notes`). Computed via
`len(indexes.archived_ids(notes.pm_root(root)))` in `health.build()` — same
source `coherence()` already reads internally, just also returned as a count.

**English label batch** (owner decision, structural tags only, prose stays
Spanish): RECUENTOS→COUNTS, AVISOS→CHECKS, RESTRICCIONES→RESTRICTIONS,
BLOQUEANTES→BLOCKERS, DECISIONES→DECISIONS, INCIDENCIAS→INCIDENTS, LO QUE
ESPERA DE TI→OPEN QUESTIONS, MEMORIA→MEMORY, "IDs sin duplicados"→"no
duplicate IDs", "índices/reglas coherentes con git"→"indexes/rules match
git". **`espera:`→`awaits:` applies ONLY to the arranque (boot.py)** — the
zone-report render (`report_render.py`'s blocker block) keeps Spanish
`espera:` deliberately, per an existing dedicated TEXTOS.md §6 point-4
decision that the human-facing zone report stays Spanish while the arranque
went English. Don't blanket-replace `espera:` everywhere — check which
surface it's on first.

See [lessons.md](lessons.md) for: the bash-hook text-match gotcha when
building demo commands, the flock+unlink TOCTOU race in `gitcmd.file_lock()`
(not fixed — flagged), and the concurrent-agent HEAD-move false-positive in
`test_boot_script.py`'s teardown fixture.

**Session 2026-08-03, B20: retired `lib/memory/dispatch.py` +
`hooks/inject.py`** (per-office memory injection replaced by "each agent
greps its own file's git history" — 3 steps in each agent's own prompt,
out of scope for Ultron). Checklist for cleanly retiring a piece in this
project, reusable for the next one:

1. `grep -rn "import <module>\|from <module>"` across `lib/`, `bin/`,
   `hooks/` FIRST — distinguishes a real code dependency (blocks/pauses the
   removal, must ask the owner) from a doc-only mention (safe to sweep).
   Here only the retired hook itself imported the retired module; two
   sibling modules (`report.py`, `report_render.py`) only *mentioned* it in
   a "Quien lo llama" docstring line — that's not a dependency, just a
   stale doc line to fix in the same pass.
2. Stale-count sweep, not just the named sections: piece counts appear in
   MULTIPLE places beyond the piece's own contract entry — a document-wide
   summary line (`ARQUITECTURA.md`'s "N módulos, N scripts, N hooks"
   opener), a "who calls me" list on a sibling piece, an ASCII dependency
   graph (delete the node's line AND re-thread the tree connectors, e.g.
   `├──`→`└──` when the node that used to be last is now gone), and a
   status/checklist table far from the piece's own section (`PIEZAS.md`
   §12 "lo que falta para empezar", §13 boundary-test row). `grep -n
   "dispatch\|inject"` across the WHOLE doc caught all of these; searching
   only the two named sections would have missed most of them.
3. A stale historical test-count claim (`CALENDARIO.md`'s "→ 28 passed"
   pinned to a specific pytest command) can already be wrong BEFORE your
   change — measured `29 passed` for the two surviving hook test files
   alone, which doesn't reconcile with the old "28 passed for three files"
   claim at all. Don't propagate an unverified number forward — rerun the
   command and write what you actually measured.
4. Final verification grep (`grep -rn "dispatch\|inject" lib bin hooks`)
   WILL hit unrelated same-word noise — generic uses of "inject(ion)" as a
   security term (control-byte/trailer injection, unrelated v1 code), and
   an unrelated local `_dispatch()` command-dispatch function in
   `bin/gitmem`. Confirm each hit is noise or a retirement comment, not a
   real call, rather than trying to make the grep return zero.

**Session 2026-08-04: six-symbol privatize batch** (`test_boundary.py`'s
"produccion==0 Y tests==0" gate, §13 Puerta 3) — 5 agents in parallel, one
symbol each, all confined to their own `lib/memory/*.py` file per the
owner's no-shared-file rule. `query.is_unborn_branch`→`_is_unborn_branch`
was the ONLY one of the six with a real history of having been public on
purpose (made public 2026-08-02 when `context.py`/`health.py` each ran
their own `git log`; both were consolidated onto `query.run_git_log()`
that same day, which removed the second caller and left it with zero
reason to stay public). Wrote that history INTO the function's own
docstring, dated, so a future re-promotion reads as legitimate rather than
"this is sacred, don't touch." Grep before renaming: hits in
`test_boot_script.py`/`test_boot_launcher.py` docstrings/prose that NAME a
function are not the same as a real call — read the surrounding lines
before concluding a mention means a live dependency. Confirmed via full
suite: ran red mid-batch (142 failed) purely from the other 4 agents'
files being mid-edit at that instant — reran minutes later, 320 passed,
0 regressions, nothing to chase on my file alone.
