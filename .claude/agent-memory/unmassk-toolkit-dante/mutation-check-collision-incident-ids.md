---
name: mutation-check-collision-incident-ids
description: CRITICAL incident (2026-08-02) -- overwrote a colleague's real in-progress lib/memory/model.py with a mutation-check throwaway stub, unrecoverable. SUPERSEDED by an absolute ban (same day) -- mutation-checks now run in a scratchpad/tmp_path dir, never inside lib/memory/ at all, not even gated by an existence check.
metadata:
  type: feedback
---

**SUPERSEDED, same day, by the orchestrator, in direct response to this
incident:** the "corrected procedure" below (existence check before
write) is no longer sufficient and is NOT the current rule. The current
rule is an absolute ban: **never write any file, not even a gated/checked
throwaway, inside `unmassk-toolkit/lib/memory/` (or any shared
production path with parallel agents active).** Run every mutation-check
in an isolated scratch directory instead (the session scratchpad, or
pytest's own `tmp_path`) -- build the throwaway module(s) there, insert
THAT directory into `sys.path`, and verify the mechanism generically. If
the thing being verified is specifically "does `import_lib_memory_module`
resolve a flat sibling import," write a standalone probe that replicates
the same technique (`sys.path.insert` + `spec_from_file_location` +
`exec_module`) parameterized by an arbitrary directory, instead of
calling the real fixture pointed at the real shared path. Proven
equivalent in
[zones-py-full-contract-notes](zones-py-full-contract-notes.md)'s second round: a probe
against a scratchpad directory caught the same two conditions
(`FileNotFoundError` preserved for a missing module; a real flat
`from model import Zone` resolves) without ever touching `lib/memory/`.
**Read the rest of this file for the incident context, but treat the
"corrected procedure" section as historical -- it was the first fix,
not the final one.**

**What happened:** writing `unmassk-toolkit/tests/memory/test_ids.py`
(PIEZAS.md Sec.7.2, RED contract, test-first). Prior sessions in this
same doc series ([vocabulary-contract-notes](vocabulary-contract-notes.md),
[config-contract-notes](config-contract-notes.md),
[zones-py-full-contract-notes](zones-py-full-contract-notes.md)) established a
mutation-check pattern: write a throwaway satisfiable fake for the
not-yet-existing module + its not-yet-existing dependency (`model.py`),
confirm the tests pass against it, delete both, confirm RED returns.
That pattern is only safe when the dependency genuinely does not exist
yet. This time it did: the task explicitly said "hay compañeros en
paralelo en otros ficheros de `tests/memory/`" -- Ultron was concurrently
building `lib/memory/model.py` (and `format.py`) for real, uncommitted,
untracked, in the SAME session. I ran `ls "$LIB"` and `cat > model.py
<<EOF ...` in the **same bash block**, so I never actually gated the
overwrite on the `ls` result -- I saw the directory already had
`model.py` only in the tool output returned AFTER the destructive write
had already run. The real `model.py` was clobbered with a 4-line
`IndexLine`-only stub.

**Why it's unrecoverable:** the file was untracked (`git status` showed
`??`, confirmed via `git diff` = empty and `git log -- model.py` = no
history) -- nothing was ever staged, so git has no object for it, no
reflog, no stash. Checked `tmutil listlocalsnapshots /`: only OS-update
snapshots exist on this machine, no scheduled user-data local snapshot
covering the loss window. `__pycache__/model.cpython-314.pyc` was
useless too -- the .pyc cache key is the source file's own path/mtime,
so by the time I could check it, it had already been recompiled from MY
stub during the mutation-check pytest run, not the original.

**Recovery action taken:** did not attempt to reconstruct `model.py`
myself (writing production code is an absolute prohibition, and a guess
-- even one grounded in PIEZAS.md Sec.5.3's literal dataclass listing --
risks being silently wrong and mistaken for Ultron's real work). Deleted
the clobbered stub entirely instead of leaving it in place: an
unambiguous "file does not exist" (clean RED for every dependent test)
is less harmful than a plausible-looking partial stub that could be
mistaken for legitimate progress. `format.py` also disappeared between
two `ls` calls in this same session, cause unconfirmed -- most likely a
concurrent colleague's own action (not mine), flagged separately, not
touched further.

**Corrected procedure -- mandatory before ANY mutation-check write
under `lib/memory/` (or any shared production path) in a session with
parallel agents:**
1. Run `ls`/`find` on the target path as its own step and READ the
   result BEFORE deciding whether to write anything -- never chain a
   `ls && cat > file` (or equivalent) in one command where the write
   isn't conditional on what the read showed.
2. If the file already exists, STOP -- do not treat it as "not yet
   existing" by default just because a prior session's notes describe
   that module that way. Prior-session memory describes a point in
   time, not the current state (this is the general "verify before
   recommending from memory" rule, doubly true for concurrent sessions).
   Either skip the mutation-check for that dependency (test against the
   real file instead, read-only) or explicitly ask before overwriting
   anything real.
3. In an explicitly parallel/concurrent task (task prompt says other
   agents are touching sibling files right now), treat every file under
   the shared directory as potentially real and in-flight, not
   throwaway, until proven otherwise by a fresh existence check.

**General rule going forward:** the mutation-check technique itself
(documented in [vocabulary-contract-notes](vocabulary-contract-notes.md),
[config-contract-notes](config-contract-notes.md),
[zones-py-full-contract-notes](zones-py-full-contract-notes.md)) is still correct and
still required for RED-phase verification -- what changed is the
precondition. Never skip the existence check, and never combine
"check if it exists" and "write to it" in a single unreviewed command
again.

Reference: [vocabulary-contract-notes](vocabulary-contract-notes.md), [config-contract-notes](config-contract-notes.md), [zones-py-full-contract-notes](zones-py-full-contract-notes.md)
