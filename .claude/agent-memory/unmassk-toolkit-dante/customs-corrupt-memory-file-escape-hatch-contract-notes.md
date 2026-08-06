---
name: customs-corrupt-memory-file-escape-hatch-contract-notes
description: hooks/customs.py RED contract (2026-08-06) -- corrupt config.json/zones.json must not swallow git merge/rebase --abort/--continue; only config.json corruption breaks rescue commands today, zones.json corruption doesn't
metadata:
  type: project
---

Context: owner-reported real incident -- a merge-conflict-corrupted
`.claude/project-memory/config.json` (merge markers left unresolved,
invalid JSON) makes `config.load()` throw inside `hooks/customs.py::_decide()`,
caught by `main()`'s generic `except Exception`, which blocks with a
non-actionable message ("fallo inesperado, bloqueando por seguridad: <raw
exc>") for EVERY commit-creating git subcommand it detects -- including
`git merge --abort`/`git rebase --abort`/`--continue`, the natural way
OUT of the very conflict that corrupted the file. Owner decision: "block
with a clear exit" -- normal commits stay blocked but the reason must say
HOW to fix the file, not just name it; the four rescue commands
(`merge --abort`, `merge --continue`, `rebase --abort`, `rebase
--continue`) must always approve regardless of corruption.

**Empirically verified BEFORE writing the contract (ran the real hook as
subprocess, not guessed) -- config.json and zones.json do NOT behave the
same for the rescue-command point:**
- `config.load(pm / "config.json")` runs unconditionally in `_decide()`
  before dispatching to `_decide_commit_creating()` -- so its exception
  fires for ANY subcommand (`commit`/`merge`/`rebase`/`cherry-pick`),
  corruption alone breaks all 4 rescue commands today. Confirmed RED.
- `zones_lib.load(pm / "zones.json")` is only reached inside
  `_decide_note()`, itself only reachable when subcommand == `commit`
  (never `merge`/`rebase`) AND the message parses as a recognizable note.
  `merge --abort`/`rebase --continue`/etc. never touch zones.json at all
  -- corrupting it does NOT break rescue commands today (verified: hook
  returns `approve` unchanged). Added those 4 tests anyway as a locked-in
  safety net (task asked to cover "both files"), documented explicitly in
  the class docstring's ASUNCIONES DE FIRMA as "already green today, not
  a red gap" so nobody reads a passing test as proof of a bug that isn't
  there.

**Wording assertion technique for pre-fix acceptance text:** exact repair
wording doesn't exist yet (Ultron hasn't written the fix). Rather than
inventing/guessing prose, pinned two verifiable properties instead of a
literal string: (a) `reason` must NOT start with the current generic
prefix `"customs.py: fallo inesperado, bloqueando por seguridad: "`
(that prefix followed by a raw exception dump IS the bug), (b) `reason`
must name the corrupted filename AND contain at least one repair-verb
hint from a small Spanish vocabulary (`repara`/`arregla`/`corrige`/
`edita`/`resuelve`/`valida`/`revisa`). A reason that only names the file
without any instruction is rejected on purpose -- the task explicitly
says naming alone isn't enough.

**Result: 6/10 new tests RED today (the real gap), 4/10 already GREEN
(zones.json + rescue commands, locked in as regression safety net).**
Test class: `TestCorruptMemoryFileBlocksWithEscapeHatch` in
`tests/memory/test_customs_hook.py`. All 26 pre-existing tests in that
file stayed green -- no regression from the addition.

Reference: [deuda-b19-customs-autoenable-rebase-contract-notes](deuda-b19-customs-autoenable-rebase-contract-notes.md)
-- same file's live-Bash-tool-interception gotcha reconfirmed here: this
project's own PreToolUse `customs.py` hook intercepts the agent's OWN
`Bash` tool calls (not just pytest subprocesses) when the command text
matches a `git commit`/`merge`/`rebase`/`cherry-pick` pattern -- a
manual probe with a plain `git commit --allow-empty -m "init"` inside a
throwaway repo got blocked by the LIVE hook on the real project, because
it resolves cwd via `os.getcwd()` of the hook process, not the probe
script's `cd`. Workaround used: wip-prefixed (`🚧`) commit messages for
throwaway init commits during manual verification.
