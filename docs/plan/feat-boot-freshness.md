# Boot Memory Freshness (Multi-Machine) Implementation Plan

**Issue:** #49
**Branch:** main (trunk repo — no feature branch)
**Triage:** Big (boot hook recently audited + new network surface)
**Build mode:** test-first
**Seam:** YES — fetch writes remote-tracking refs that the boot then reads; bare-remote round-trip mandatory (unmassk-standards §34)
**Created:** 2026-07-06
**Decisions:** 3d2f377 (council verdict), d958659 (Bex: pull proposed at boot, not at close)

## Goal

The boot always shows memory that is fresh against the remote: hardened rate-limited fetch, visible provenance/freshness stamp, explicit behind signal with a pull proposal as the session's first action, memory read from `origin/<branch>` when it is strictly ahead, and a warn-only guard before committing memory on a stale base.

## Key research facts (Bilbo)

- A fetch ALREADY runs on every boot: `session-start-boot.py:246` — `git fetch --quiet`, sync, timeout 5s (`BOOT_FETCH_TIMEOUT`, :114), inside `run_preboot_migrations()`, BEFORE `render_branch_section()`. It is ungated (any git repo), unhardened (no `GIT_TERMINAL_PROMPT/GIT_ASKPASS/SSH_ASKPASS/BatchMode`), and unthrottled.
- Ahead/behind: `lib/boot_git_checks.py:render_branch_section()` (:142-190), `rev-list --left-right --count HEAD...@{u}` (:170); "PULL RECOMMENDED" at :187.
- `lib/boot_memory.py:extract_memory()` (:88-257) is HEAD-only (`log -z -n30`, no ref param). `extract_glossary()` uses `--all` (incidentally includes origin refs, unlabeled). Sanitization: `-z`/NUL records + `sanitize_trailer_value()` — reuse as-is, only the ref changes.
- Glossary cache keys freshness on local HEAD sha only (`boot_glossary_cache.py:117-122`).
- `run_git()` (`git_helpers.py:279-326`) has NO `env` kwarg — needs additive one.
- Write path `bin/git-memory-commit.py` has zero behind-check; warn-only variant of `release_helpers._preflight_check_not_behind()` (:278-298) is the model.
- Toolkit-repo gate: `needs_install()`-style CLAUDE.md marker check (`user-prompt-memory-check.py:51-62`) or `.claude/.unmassk/manifest.json` presence (already read by `boot_health.check_version_mismatch`). `git-memory-config.json:repo_type` is the WRONG gate (deploy-risk axis).
- Test fixture model: `tests/test_release.py:_setup_release_repo()` (:108-156) + `TestPreflightBehindRemote` (bare remote + second clone pushes → first is behind).
- Hook invocation in tests: `tests/conftest.py:run_script()`; session-start-boot.py reads no stdin.

## Architecture decision locked

Keep the fetch SYNCHRONOUS in the boot script (Bex d958659: the boot script itself detects and signals behind). The council's "never block" concern is satisfied by: timeout 3s, rate-limit (skip if `.git/FETCH_HEAD` mtime < 5 min), toolkit-repo gate, and hardened env that guarantees no interactive hang. Worst case ≈ 3s on the first boot of the day; typical repeat boots pay zero network.

## Tasks

### Task 1: Acceptance contract (Dante — FIRST, test-first mode)
**Files:** create `unmassk-toolkit/tests/test_boot_freshness.py`
**Steps:**
- [ ] Fixture: bare remote + two clones (model: `test_release.py::_setup_release_repo`); machine B pushes memory commits (decision/context with Next:) so machine A is N commits strictly behind — expected values derive from what B actually wrote (§34: no hand-typed literals)
- [ ] RED test 1 (incident reproduction — the fix criterion): clone A 12 behind → boot output signals behind AND the RESUME/Next shown comes from origin's newest context commit, labeled with remote provenance
- [ ] RED test 2: freshness stamp present in header in all three states (fresh-fetch / rate-limited / fetch-failed→"LOCAL, sin verificar")
- [ ] RED test 3: behind + clean tree → boot emits the pull-proposal directive; behind + dirty tree → directive says dirty, do not touch
- [ ] RED test 4: fetch hardening — remote URL pointing at a dead port → boot completes < timeout+margin, fail-open; env asserts `GIT_TERMINAL_PROMPT=0`, askpass overrides, BatchMode
- [ ] RED test 5: gate — repo WITHOUT toolkit memory → no fetch attempted (assert via fake remote that would fail loudly)
- [ ] RED test 6: rate-limit — fresh FETCH_HEAD mtime → fetch skipped; stale → fetch runs
- [ ] RED test 7: divergence (A ahead 1 AND behind 2) → both sides labeled, no auto-merge, no crash
- [ ] RED test 8: write path — memory commit while strictly behind → warning emitted, commit still succeeds (warn-only)
- [ ] Verify: suite runs, new tests FAIL (red), existing suite still green
- [ ] wip commit

### Task 2: Hardened, gated, rate-limited fetch (Ultron)
**Depends on:** Task 1
**Files:** modify `unmassk-toolkit/hooks/session-start-boot.py`, `unmassk-toolkit/lib/git_helpers.py`
**Steps:**
- [ ] `run_git()` gains optional `env` kwarg (additive; merged over `os.environ` copy)
- [ ] New `fetch_memory_ref(project_root)` (in `lib/boot_git_checks.py`): gate (toolkit memory present: manifest.json or CLAUDE.md marker) → rate-limit (FETCH_HEAD mtime < 300s → skip, report age) → `git fetch origin <current-branch> --no-tags` with env `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS=/bin/false`-equivalent, `SSH_ASKPASS` neutralized, `GIT_SSH_COMMAND="ssh -oBatchMode=yes"`, timeout 3s; returns fetch status (`fetched` | `rate_limited` | `skipped_gate` | `no_remote` | `failed`) + age of last successful fetch
- [ ] Replace the bare `run_git(["fetch","--quiet"])` at session-start-boot.py:246 with this call; remove `BOOT_FETCH_TIMEOUT=5` in favor of the new constant
- [ ] Fail-open on every branch; never raise
- [ ] Verify: Task 1 tests 4-6 GREEN
- [ ] wip commit

### Task 3: Provenance stamp + behind signal + pull directive (Ultron)
**Depends on:** Task 2
**Files:** modify `unmassk-toolkit/lib/boot_git_checks.py`, `unmassk-toolkit/lib/boot_render.py`, `unmassk-toolkit/hooks/session-start-boot.py`
**Steps:**
- [ ] Header stamp (banner + boot-log first lines): `MEMORIA: remoto (fetch hace Xs)` / `MEMORIA: LOCAL — último fetch hace Nh, sin verificar` / `MEMORIA: LOCAL — fetch omitido (rate-limit, hace Xmin)` — provenance in the content header, not a side note
- [ ] Behind > 0 in `render_branch_section`: escalate from "PULL RECOMMENDED" to an explicit directive block in BOTH stdout banner and boot-log: local N behind; if working tree clean → "propose `git pull` to the user as the FIRST action of this session"; if dirty → "tree has uncommitted work — inform the user, do NOT pull"
- [ ] Verify: Task 1 tests 2-3 GREEN
- [ ] wip commit

### Task 4: Read memory from origin when strictly ahead (Ultron)
**Depends on:** Task 2
**Files:** modify `unmassk-toolkit/lib/boot_memory.py`, `unmassk-toolkit/lib/boot_glossary_cache.py`, `unmassk-toolkit/hooks/session-start-boot.py`
**Steps:**
- [ ] `extract_memory(ref=None)` — parametrize the log ref (default HEAD, same `-z`/NUL pipeline, same sanitization; ONLY the ref argument changes)
- [ ] Boot logic: strictly behind (behind>0, ahead==0) → extract from `origin/<branch>`, label RESUME/entries `[origen: remoto]`; diverged (both >0) → extract both, render both labeled, never merge; otherwise → HEAD as today
- [ ] Glossary cache freshness key: include `origin/<branch>` sha alongside local HEAD sha
- [ ] Verify: Task 1 tests 1 and 7 GREEN
- [ ] wip commit

### Task 5: Warn-only behind check on memory writes (Ultron)
**Depends on:** Task 2 (constants/helpers), independent of 3-4
**Files:** modify `unmassk-toolkit/bin/git-memory-commit.py`
**Steps:**
- [ ] Before `_do_commit()` for memory types (decision/memo/remember/context): `rev-list --count HEAD..@{u}` against existing tracking refs (NO network call here — boot's fetch keeps refs fresh); if behind>0 → print visible warning ("local N behind remoto — considera pull antes de seguir; el commit se hace igualmente"); never block, fail-open on any error
- [ ] Verify: Task 1 test 8 GREEN
- [ ] wip commit

### Task 6: Docs — three audiences (Alexandria, Step 6)
**Files:** README.md, CHANGELOG.md [Unreleased], `unmassk-toolkit/skills/unmassk-gitmemory/SKILL.md` (Boot Protocol + Active Hooks sections), docs/plan status
**Steps:**
- [ ] SKILL.md: document stamp semantics, behind directive, origin-read behavior, write-path warning
- [ ] README/docs: multi-machine freshness behavior in plain language
- [ ] CHANGELOG [Unreleased]
- [ ] wip commit

## Wave Map

- Wave 1: Task 1 (Dante — contract)
- Wave 2: Task 2 (Ultron)
- Wave 3: Task 3, Task 4, Task 5 (parallel — no file overlap: 3=render/git_checks, 4=memory/glossary, 5=bin) — NOTE: 3 and 4 both touch session-start-boot.py → run 3 and 4 sequentially or assign both to ONE Ultron; 5 parallel safely
- Wave 4: Verify (Cerberus + Argus + Moriarty + Yoda — Big + seam: Dante owns round-trip, Moriarty sabotages the real bare-remote dependency, Yoda mechanical round-trip evidence rule)
- Wave 5: Task 6 (Alexandria) → Close (Gitto squash on main + push)

## Plan Checker

- Decision 3d2f377 items → Tasks: hardened gated rate-limited fetch (T2), provenance stamp (T3), origin read + divergence labeling (T4), write-path guard (T5). Decision d958659 → pull directive at boot (T3). Fix criterion (12-behind reproduction) → T1 test 1. ✔
- Every task has verify steps tied to the red tests. ✔
- Dependencies explicit; file-overlap noted in wave map. ✔
