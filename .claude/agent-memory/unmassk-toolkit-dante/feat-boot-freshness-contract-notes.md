---
name: feat-boot-freshness-contract-notes
description: Boot memory freshness (multi-machine, issue #49) acceptance contract — fixture design, RED baseline, what Ultron/Cerberus/Argus/Moriarty/Yoda still owe
metadata:
  type: project
---

Plan: `docs/plan/feat-boot-freshness.md` (issue #49). Build mode: test-first.
Contract file: `unmassk-toolkit/tests/test_boot_freshness.py` (Dante, Task 1,
session 2026-07-06) — 12 pytest methods covering the plan's 8 acceptance
tests, ALL confirmed genuinely RED against the unmodified code (clean
`AssertionError`s, no fixture crashes), 0 regressions in the pre-existing
suite (863 passed, 9 pre-existing unrelated `test_release.py` failures —
same known baseline as prior rounds, see
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)).

**Why:** the boot hook (`hooks/session-start-boot.py`) already runs an
unhardened, ungated, unthrottled `git fetch --quiet` on every boot, but
`lib/boot_memory.py:extract_memory()` only ever reads local HEAD — a second
machine's newer memory commits are invisible until a manual pull, and the
existing fetch has no protection against a hanging/prompting remote.

**How to apply — fixture model, for Ultron and whoever re-touches this file:**

- Two-machine fixture is `_setup_freshness_repo(tmp_path)` (machine A: repo +
  bare remote + toolkit install, committed so the tree starts CLEAN) +
  `_clone_machine_b(bare, tmp_path)` (machine B, called separately). These
  are deliberately split — an earlier draft cloned B eagerly inside the
  setup helper and hit a real non-fast-forward push failure when a test
  added more commits to A *after* the clone point but before B pushed.
  Always clone B only after any A-only setup commits are already pushed.
- B creates commits with plain `git commit -m` using the REAL emoji +
  `type(scope): message` + trailer format (`_commit_real()` helper,
  EMOJIS dict mirrors `bin/git-memory-commit.py`'s own) — hooks never run
  in these temp repos, so there is no wrapper script to invoke for B.
- The install step leaves CLAUDE.md/.gitignore untracked on disk; if not
  committed, EVERY "clean tree" test starts dirty for the wrong reason
  (untracked install artifacts, not the test's own intentional dirty file).
  `_setup_freshness_repo()` commits+pushes them once, guarded by a `git
  status --porcelain` check (skip the commit if genuinely nothing changed).
- Fake-`git`-on-PATH technique for tests 4 (hardening env + timeout) and 5
  (fetch gate) — see
  [mock-patterns.md](mock-patterns.md) for the full pattern. POSIX-only,
  skipped on Windows.
- Rate-limit tests (6) manipulate `.git/FETCH_HEAD` mtime directly via
  `os.utime()` after seeding it with one real `git fetch` — no fake git
  needed there, real local-bare-remote fetches are fast and deterministic.
- "Fetch failed" state (test 2's third variant) uses a nonexistent local
  path as the remote URL, NOT a real dead-port network address — avoids any
  sandboxed-CI network/loopback ambiguity while still forcing a real,
  deterministic `git fetch` failure.
- Marker naming pitfall: see
  [edge-cases.md](edge-cases.md)'s "echoes back into output" entry — any
  marker text used near a `re.search(r"remot"/"behind"/...)` assertion must
  NOT itself contain that keyword, or the assertion passes vacuously before
  the feature exists. Caught and fixed twice in this file before the final
  RED run (`INCIDENT_NEXT_MARKER`, `b_remote_marker`, and the write-path
  commit message all originally embedded the keyword being searched for).

**What the RED baseline proves is still missing** (for Cerberus/Argus/
Moriarty/Yoda downstream in this same pipeline — don't re-derive, read the
test failures directly): no `MEMORIA:` freshness stamp anywhere; no fetch
gate (fetch runs even without toolkit memory installed); no rate-limit
(FETCH_HEAD mtime always advances); no env hardening on the fetch subprocess
call; `extract_memory()` is HEAD-only (never reads `origin/<branch>`, so a
behind machine can never see the other side's newer Next, and a diverged
machine only ever shows its own local side); no "first action" / "do not
pull while dirty" directive text; `bin/git-memory-commit.py` has zero
behind-check on memory writes.

See also: [boot-stdout-banner-contract-notes](boot-stdout-banner-contract-notes.md),
[skill-router-contract-notes](skill-router-contract-notes.md) (same
"test-first contract, RED baseline documented for the rest of the pipeline"
shape, same module family).
