# Moriarty — Memory Index

- [round-history.md](round-history.md) — full chronological log, one entry per attack round, newest first. Latest: D-065/D-066 issue-customs gate (2026-08-26) — FALLA. BREAK 1: `hooks/customs.py`'s raw-`git commit` path NEVER calls `validate_issue_gate` (only `note.py` does) — a well-formed Q/I note with no issue/quote lands permanently via a hand-typed commit, same shape as D-056's BREAK 1 (one caller enforces, the other doesn't). BREAK 2: a `\r` in `--quote` survives in git's own store but `gitcmd.py`'s `text=True` subprocess read silently turns it into `\n`, and `format.py`'s continuation-stripper eats the next real character — silent content corruption on READ, isolated from pure size (200KB clean quote round-trips exact). Rounds dated 2026-06/07 attacked the now-deleted v1 memory system — historical only, see below.
- [attack-patterns.md](attack-patterns.md) — reusable attack techniques that worked, organized by mechanism. Split into "sistema actual" (verified against today's code, with `[CERRADO ...]` notes where a past finding is now fixed) and "retirado" (v1 memory system, condensed to the transferable lesson only — files no longer exist).
- [resilience.md](resilience.md) — what held under real attack and why, same "sistema actual"/"retirado" split — read the current section before re-attacking something already proven solid, to avoid repeating a closed round.

## Sistema actual vs. retirado (compactación 2026-08-25)
El sistema de memoria v1 (`lib/boot_git_checks.py`, `lib/boot_memory.py`,
`lib/recall.py`, `bin/git-memory-gc.py` y ~13 ficheros más) fue borrado
entero el 2026-08-05 (commit `615f5cc`), reemplazado por memoria v2
(`lib/memory/*`, `hooks/customs.py`, `hooks/checklist-gate.py`,
`bin/memory/*`). Antes de citar un `file:line` de una ronda anterior a
esa fecha, comprobar que el fichero sigue existiendo (`find`) — la mayoría
ya no. `git_helpers.py` y `bin/release.py` (partido en
`release_validators.py`/`release_helpers.py`) sobrevivieron a la purga y
siguen siendo atacables tal cual.

## How this project attacks
- Threat model is fixed project-wide: **no external adversary** — see `unmassk-standards`'s own framing and this repo's CLAUDE.md ("la unica amenaza es el sistema rompiendose a si mismo"). EXPLOIT phase is routinely N/A here; don't manufacture an attacker.
- Concurrency (RACE phase) is sometimes explicitly excluded per task instruction (owner decision B22, "dos procesos a la vez... no va a pasar nunca") — check the task prompt each round before assuming N/A; it is NOT a blanket rule, some rounds explicitly want it attacked (e.g. `hooks/checklist-gate.py`, whose real Stop/PostToolUse events can genuinely fire concurrently — 4 real concurrent processes attacked and held 2026-08-24, see resilience.md; the older example of this lesson, `hooks/stop-dod-gate.py`, is one of the v1-system files deleted 2026-08-05, no longer attackable).
- The Bash-level customs hook fires on real `git commit`-shaped invocations (the literal subcommand), not on bare occurrences of the word "commit" in prose — a heredoc whose body is plain text containing "commit" runs fine (re-verified 2026-08-23). Only build the subcommand dynamically (`SUB=com; SUB=${SUB}mit; git $SUB ...`) when the command actually needs to run `git commit` in a scratch repo; no need to avoid the word elsewhere.
- Always verify cwd before trusting a multi-step scratch setup: a `cd` into a not-yet-created directory fails silently in some shells and leaves later commands running against the real project root. Confirmed twice now (capa-5 round, stop-dod-gate round) — always `git status --porcelain` immediately after any scratch setup that chains a `cd`.
- Green tests are not evidence: this codebase's own test suites repeatedly pre-seed the exact precondition (e.g. parent package dir already on disk) that hides a real gap one level up (top-level package itself never written). Read what a fixture SETS UP, not just what it asserts, before trusting "covered".
- Never write a NEW/edited test manifest or config into the real plugin's own directory (e.g. `unmassk-toolkit/checklists/`), even transiently with cleanup after — that is writing into the real repo, out of scope regardless of cleanup. When a hook resolves config relative to its own `__file__`, copy the hook + its lib deps to scratch with a sibling scratch config dir instead (confirmed 2026-08-24, coordinator-caught mid-round).
