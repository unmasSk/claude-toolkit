---
name: False positives — patterns that are intentional
description: Patterns that look suspicious but are correct in this codebase
type: project
---

## scripts/README.md is not an orphaned file

In any `scripts/` directory inside a skill, a `README.md` is expected documentation. Do not flag it as an orphaned file when auditing routing table coverage against disk contents.

## SKILL.md has two routing tables

unmassk-marketing SKILL.md has BOTH a "Request Routing" table (lines 59-73) AND a "Reference Files" table (lines 189-205). Both reference the same 14 files. This is intentional redundancy (one for quick routing, one for load-when context). Do not flag as duplication.

## finalize_exit + exit $? two-step in cluster_health.sh and network_debug.sh

```bash
finalize_exit
exit $?
```

This is intentional. Calling `exit` directly in `finalize_exit()` would exit the shell if the function were ever sourced. The two-step preserves the exit code from the function's `return` statement and then exits the script. Do not flag as redundant.

## BM25 IDF variant (+1 outside log) in skill-search.py

`skill-search.py` uses `log((N - freq + 0.5) / (freq + 0.5) + 1)` (Robertson-Sparck-Jones variant). The `+1` is outside the log, not inside. This keeps IDF always positive for common terms in small corpora (N=36). It is intentional and correct for this use case. Do NOT flag as incorrect BM25 formula.

## BM25 ZeroDivisionError when avgdl=0 is latent but safe

`BM25.score()` divides by `self.avgdl` (via `doc_len / self.avgdl`). If all documents tokenize to empty strings, `avgdl=0`. However, in that case `self.idf` is also empty, so the inner loop `if token in self.idf:` never executes and the division is never reached. This is safe in practice. Do NOT flag as an active bug; it is a latent fragility.

## Dedup order (cache wins over dev-tree) in skill-search.py

`skill-search.py` deduplicates skills by name keeping the first occurrence. Search dirs are ordered: home cache first, then git-root last. This means cached plugin versions win over dev-tree versions. The comment `# keep first seen — cache version wins over dev` documents this as intentional. Do NOT flag as incorrect dedup ordering.

## sed -i.bak pattern in generate_* scripts

```bash
sed -i.bak "s/PLACEHOLDER/value/g" "$FILE"
rm -f "${FILE}.bak"
```

This is the cross-platform form of `sed -i` (GNU requires `-i ''`, macOS requires `-i .bak`). The `.bak` suffix approach is intentional for macOS compatibility. The `.bak` cleanup with `rm -f` is correct. Do not flag as unnecessary.

## configureRateLimitLogging registered AFTER applyRateLimit in app.middleware.ts

In `app.middleware.ts` lines 87-88, `applyRateLimit(app)` is called before `configureRateLimitLogging(app)`. This looks like it could be a registration order issue, but both register on `/api/v1`. The logging monitor patches `res.setHeader` and therefore intercepts the headers that `express-rate-limit` sets during request processing — not during registration. The order of Express middleware registration matters for *request processing*, and since `configureRateLimitLogging` is registered immediately after `applyRateLimit` (both during startup, not per-request), the `setHeader` wrapper WILL be present on the response object when the rate limiter fires on the *same request*. Do NOT flag as an ordering bug.

## `as any` in Bun.spawn call for cross-platform spawning

`agent-invoker.ts` line 498 uses `} as any` for the Bun.spawn options. This is intentional: Bun's TypeScript types for `spawn` don't correctly narrow the return type when `detached` is conditionally included (platform check). The `as any` is a genuine Bun type-system limitation, not sloppy typing. Do not flag.

## GC setInterval in auth-tokens.ts does not unref()

The 10-minute `setInterval` for token cleanup does not call `.unref()`. This is intentional — the interval must keep the process alive to purge expired tokens during long-running server sessions. In a CLI tool it would be a problem; in a server it is correct behavior.

## `activeInvocations` Map is declared but effectively unused for tracking

`activeInvocations` holds promises keyed by `${agentName}:${roomId}` but nothing awaits them or reads them outside `runInvocation`. Its purpose is to count concurrent invocations (`activeInvocations.size >= MAX_CONCURRENT_AGENTS`). The Map of promises is intentional (reachable in future if tracking/cancellation is added). Do not flag as dead code.

## chatroom mockup: dual hex + OKLCH color token sets are intentional (unreconciled but both present)

In `option-b-cursor-style.html`, agent colors are defined twice: as WoW-palette hex values (lines 43-52: `--color-ultron: #0070DD`) and as OKLCH values (lines 65-75: `--c-ultron: oklch(65% 0.18 250)`). The HTML uses the hex set. The OKLCH set appears unused in the mockup file itself. This is NOT intentional good design — it is a W1 structural warning — but do not treat the OKLCH set as "dead code" requiring deletion. It is the intended production token system and should replace the hex set, not be removed.

## chatroom mockup: `overflow: hidden` on `.agent-list` is a bug, not intentional

Line 287: `.agent-list { overflow: hidden; }`. The scrollbar CSS at lines 290-292 is defined but inactive because the parent suppresses scroll. This is a confirmed bug (S7). Do not treat the scrollbar CSS as dead code — the fix is changing `hidden` to `auto`.

## BunSpawnOptionsWithDetached stdin generic mismatch is benign

`agent-runner.ts` defines `BunSpawnOptionsWithDetached = Bun.Spawn.SpawnOptions<"ignore", "pipe", "pipe"> & { detached?: boolean }`. The `"ignore"` stdin generic does not match the actual runtime behavior (stdin is not set in `spawnOpts`, so Bun uses its default). This is a type-annotation imprecision only — stdin is never read in this codebase. Do NOT flag as a functional bug.

## connection.test.ts singleton test hits real DB singleton — intentional

After the 2026-03-23 rewrite, the `getDb()` singleton-identity tests in `connection.test.ts` import the cached module without redirecting `DB_PATH`. They test the singleton contract (same ref returned), not the path. The SQL/WAL execution tests use their own `new Database(tempPath)`. This split is intentional design. Do not flag the singleton tests as "testing the wrong database."

## IGNORECASE=1 replaced by tolower() in dockerfile-validate.sh awk

In `dockerfile-validate.sh` around line 415, the comment explains that BSD awk (macOS) does not honour `IGNORECASE=1` for the `~` dynamic regex operator, only for literal `/patterns/`. Using `tolower()` before the `~` comparison is the correct workaround. Do not flag as inconsistent style.

## agent-result-kill-guard.test.ts: broadcast contract is intentionally untested (bun mock constraint)

The test `'persists message to DB when agent is killed (broadcast path reached via insertion ordering)'` does NOT directly verify that `message-bus.broadcast()` was called. The original assertion (`broadcastCalls.length > 0`) was removed because `mock.module('../../src/services/message-bus.js', ...)` leaks into bun 1.3.11's global module registry and breaks 32 other tests.

The replacement assertion (`countAgentMessages(ROOM, AGENT) > 0`) only verifies message persistence, not broadcast. This is a documented, acknowledged coverage gap — not a mistake. The comment in the test explains the constraint and the proxy reasoning.

Do NOT flag this as a missing assertion bug. The correct long-term fix is DI for the broadcast function so mock.module is not needed — but that is a future Dante task, not a present bug.

## pre-memory-dedup-gate.py: `entry["text"]` in warning reason is already sanitized

In `pre-memory-dedup-gate.py` line 301, `best_entry['text']!r` is embedded in the `permissionDecisionReason` without an explicit `_sanitize()` call. This looks like a missing sanitization step, but it is safe: `entry["text"]` comes from `_scan_commits()` in recall.py, which calls `_sanitize()` at line 174 before storing the value. The text is clean before it ever reaches the hook. Do not flag as unsanitized injection.

## `extract_glossary` (uncached) re-exported into session-start-boot.py but never called there

After the CRB-04 split, `hooks/session-start-boot.py` imports `extract_glossary` from `lib/boot_memory.py` alongside `extract_glossary_cached`, but only calls `extract_glossary_cached()` inside `main()`. `extract_glossary` itself looks like a dead/unused import at first read. It is NOT dead: `tests/test_crown.py:229` loads the hook module directly (`spec_from_file_location`) and calls `boot.extract_glossary()` on it — the re-export exists specifically so tests that reach into the hook module by name keep working unchanged after the split (documented in `lib/boot_memory.py`'s module docstring). Do not flag as an unused import without first grepping `tests/` for `boot.extract_glossary(` or similar attribute access on the loaded hook module.

## `_sanitize_trailer_value` re-exported into session-start-boot.py but never called there

After the CRB-04/T2-1 splits, `hooks/session-start-boot.py` imports `_sanitize_trailer_value` from `lib/boot_memory.py` (line 49) but never calls it anywhere else in the file — looks like a dead/unused import at first read, same shape as the already-documented `extract_glossary` false positive above. It is NOT dead: `tests/test_regression_audit_round2.py::_load_boot_sanitize()` loads the hook module directly via `spec_from_file_location` + `exec_module` and reads `mod._sanitize_trailer_value` as an attribute (`TestBootSanitize` parity tests). The re-export exists specifically so that test keeps working unchanged after the split. Do not flag as an unused import without first grepping `tests/` for `._sanitize_trailer_value` / `.extract_glossary(` attribute access on a module loaded from the hook file. Confirmed 2026-07-05 round 6.

## afterAll scheduler cleanup in kill-guard test is order-dependent by design

`afterAll(() => { activeInvocations.clear(); inFlight.clear(); })` at the bottom of `agent-result-kill-guard.test.ts` deliberately clears global state left by `agent-invoker-schedule.test.ts`. This looks like a test that is cleaning up after a different test file, which would normally be a flaky pattern. It IS that — but it is intentional, documented, and the alternative (running each file in isolation) is not supported by the current bun test runner. Do not flag as a shared-state anti-pattern without reading the comment block first.

## Fake `_patched_run_git(args, cwd=None)` test helpers with narrow signatures are not broken by a new opt-in kwarg on the real `run_git()`

`git_helpers.run_git()` gained an opt-in `log_stderr_on_failure: bool = False` param (2026-07-08, issue #52 CI-fix round, run 28922061708). Several test files (`test_crown.py`, `test_crown_retraction.py`, `test_boot_output.py`) monkeypatch `git_helpers.run_git`/`boot.run_git` with a local `_patched_run_git(args, cwd=None)` — a narrow signature with no `**kwargs`. This looks like it would raise `TypeError: unexpected keyword argument` the moment any patched call path passes the new kwarg. It does NOT: those specific test helpers are only ever reached via `extract_memory()`/`extract_glossary()`/`render_status_section()` etc., none of which pass `log_stderr_on_failure`. Only `get_timeline()`/`get_last_context_time()` (`lib/boot_git_checks.py`) pass it, and no test in this codebase monkeypatches `run_git` with a narrow signature on a path that reaches those two functions specifically. Before flagging a narrow-signature test fake as broken by a new kwarg on the real function, trace which actual call sites the patched fake is reached through — do not assume every kwarg addition is a blanket break.

## test_lifecycle.py::test_doctor_after_install fails under `-k` filtering, passes when the file runs whole — pre-existing, unrelated to date-parsing diffs

Running `pytest tests/ -k "gc or doctor or bootstrap_commits"` (or any other cross-file `-k` selection that pulls in `test_doctor_after_install` without its `test_lifecycle.py` siblings running in their normal order) fails with `assert result.get("status") != "error"` / `'CLAUDE.md not found'`. Running `tests/test_lifecycle.py` alone (whole file, normal order) passes 10/10. Confirmed via `git worktree add` against the pre-diff commit `0ff8bfe` (issue #55 date-parsing round, 2026-07-08): identical failure reproduces on the base commit with the same `-k` filter, so it is a test-isolation/order-dependent flake in the existing suite, not a regression from any date-parsing/`%at` change. Do not flag this failure against a diff unless the diff touches `test_lifecycle.py`, `git-memory-install.py`, or `git-memory-doctor.py`'s CLAUDE.md-detection path — always reproduce it against the pre-diff commit via `git worktree add <path> <base-sha>` before attributing it to the change under review.

## CLI `--before/--after nan` degrading to `commanded_unverified` instead of `invalid_input` is intentional (sensor_gate.py)

Confirmed 2026-07-15, unmassk-electronics sensor_gate.py commit-review. In `sensor_gate.py`'s CLI layer, `run_cli()` runs every `--before`/`--after` value list through `_median_of_readings()` (which drops NaN/Infinity/None) BEFORE calling `evaluate_gate()`. A user passing `--before nan` therefore never reaches `evaluate_gate`'s own NaN-rejection branch (`status="invalid_input"`); the value collapses to `before=None` and the CLI reports `status="commanded_unverified"` instead — both are `ok:false`/exit 1, but the reason text differs ("no sensor reading available" vs "before must be a finite number"). This is documented in the module docstring, explicitly pinned by a real subprocess test (`test_all_nan_before_degrades_to_commanded_unverified_via_median_filter`), and was independently accepted by Bex after Dante flagged it. Do not re-flag this as a correctness bug in this or sibling scripts that reuse the same median-then-evaluate CLI shape — it is an acceptable minor diagnostics-clarity trade-off (still honest, still non-zero exit, never silent success), not a data-corruption or silent-failure issue under this project's threat model.

## unmassk-toolkit bin/hooks "variant 1" sys.path imports never noqa their post-path from-imports

Files using the direct `sys.path.insert(...)` header shape (not the guarded `_LIB_DIR` shape) — e.g. `post-validate-commit-trailers.py`, `pre-validate-commit-trailers.py`, `precompact-snapshot.py`, `session-start-boot.py`, `stop-close-session.py`, `stop-dod-check.py`, `user-prompt-memory-check.py` — never had `# noqa: E402` on their post-sys.path `from X import Y` lines, even before the 2026-07-07 `encoding_guard.py` addition (confirmed by checking `from constants import ...` / `from git_helpers import ...` in the same files). The `_LIB_DIR`-guarded files (`pre-merge-gate.py`, `pre-task-recall.py`, `session-start-crew.py`, `pre-memory-dedup-gate.py`, `stop-dod-gate.py`, `validate-memory-path.py`) DO use `# noqa: E402` consistently. This is a pre-existing two-way convention split, not an inconsistency introduced by any single commit — do not flag `from encoding_guard import force_utf8_streams` (or any future import) for "missing noqa" in a variant-1 file without first checking whether that file's *other* post-path imports already have noqa either.

## memoria-v2 lib/memory/: zones.py and gitcmd.py each implement their own private file-lock + atomic-write — this is disclosed, required by the layering rule, not a duplication bug

Confirmed 2026-08-02, capa-1 review. `zones.py::_exclusive_lock`/`_write_atomic` and `gitcmd.py::file_lock`/`atomic_write` are two independent implementations of the same lock+atomic-write mechanism. This looks exactly like the "tres implementaciones de lo mismo" pattern the whole v2 redesign exists to avoid. It is NOT a violation: `zones.py` is CAPA 1 (may only import CAPA 0 — model.py — per PIEZAS.md §0/§13 layering) and `gitcmd.py` is CAPA 2, so `zones.py` architecturally cannot import `gitcmd.py` without breaking the layer order. Both files explicitly disclose this in their own docstrings (`gitcmd.py`: "Mismo espiritu que ya aplico `zones.py` para su propio candado privado, aqui como la pieza canonica de la capa git"; `zones.py`: "Ambos mecanismos estan reescritos de cero en este modulo, sin importar nada del resto del toolkit"), and `zones.py`'s own concurrent-add test (`test_two_concurrent_adds_do_not_clobber_each_other`) requires SOME locking mechanism to exist at capa 1. Do not flag this pairing as unauthorized duplication; if it recurs a third time in a future capa-1 module needing the same primitive, that would be the point to reconsider (e.g., promote the lock/atomic-write pair to capa 0).

## `config.py`'s per-field `isinstance` type validation exceeds the Superficie's one-line `def load(path) -> Config` declaration — self-disclosed and tested, not a violation

Confirmed 2026-08-02, capa-1 review. PIEZAS.md §6.3's declared Superficie for `config.py` is just `def load(path: Path) -> Config`; the shipped implementation additionally type-checks each of the three fields (`customs_enabled` must be `bool`, not just JSON-valid) and raises with the filename named. This reads like unrequested scope creep at first glance (priority-4 "código que el contrato no pedía" check), but it is explicitly declared as a deviation in the module's own docstring (lines 25-30) AND backed by a dedicated test (`test_wrong_type_but_valid_json_fails_loud_and_names_file` in `test_config.py`, itself labeled "desviacion declarada por Ultron, verificada en vivo"). The real-world failure it prevents is concrete: `{"customs_enabled": "false"}` (string, not bool) is valid JSON that would otherwise silently evaluate truthy in any `if config.customs_enabled:` consumer, turning the aduana on without anyone deciding it. Do not flag this as an out-of-contract addition — it passes the project's own bar ("se justifica con un test o se quita").

## unmassk-close-session round 2 (2026-08-05): a recalled project-memory `[DECISIONES]` entry about the close protocol was stale, superseded by later same-day owner decisions

Confirmed 2026-08-05, second review of the rewritten `unmassk-close-session` skill. Auto-recalled project memory carried a `[DECISIONES] (plugin/close-session)` entry saying the close protocol should ADAPTIVELY run a version bump, send Alexandria to update the CHANGELOG, clean temp files, and flush decisions/write a resume point. The current `SKILL.md`/`close-agent-prompt.md`/`agents/alexandria.md` do none of the version-bump/CHANGELOG/decision-flush things — at first glance this looks like a regression against a recorded decision. It is not: `DEUDA.md` documents two later, same-branch owner decisions (**B34**, 2026-08-04, and especially **B42**, 2026-08-05 — the same day as this review) that establish the final, current model: the close is *only* a conversation-summary `[NEXT]` commit with the full commit list appended, and B42's own text says explicitly the filter must extract "solo la conversación... nada de nada" with no signals collected. The commit-review task's own "Deliberate design decisions" list independently confirms this ("the close collects no signals... those are saved when they happen, not at the end of the day"). Do NOT flag the absence of version-bump/changelog/decision-flush/wall-pruning/blocker-registration in this skill as a regression against the older recalled memory — that memory predates B34/B42 and is superseded. Check pattern: when a recalled `[DECISIONES]` memory contradicts the current state of a fast-moving in-progress branch, check the branch's own most-recent status doc (here `DEUDA.md`) for a same-day or later revocation before treating the memory as still authoritative.

## pytest teardown "HEAD moved during test" watchdog firing is not automatically test-caused corruption

Confirmed 2026-08-05, feat/memoria-v2 pre-merge gate round. `tests/memory/test_boot_launcher.py::TestLauncherReproducesRealBootOutput::test_launcher_adds_no_wrapper_text_beyond_boot_py_output` failed at teardown with "movio HEAD del repositorio git REAL" (a fixture that snapshots the real repo's HEAD before a test and asserts it hasn't moved after, guarding against a write call escaping its `tmp_repo` sandbox). Before attributing this to a sandboxing bug in the test/production code: ran `git show <new-head>` — real author (`bextia`), a coherent unrelated commit message ("Alexandria en modo fusion... CHANGELOG.md"), real CHANGELOG.md content, landed at a timestamp inside the pytest run window. This is a concurrent legitimate git operation from another process/session racing the test run, not evidence the test itself wrote outside its sandbox. Re-ran the same suite immediately after: 411/411 clean, zero HEAD movement. Do not flag a single non-reproducible HEAD-move alarm as a production bug without first diffing the commit that actually landed — if its content/author is unrelated to the test under suspicion, it's a race with an external process, not a sandboxing escape.

## `checklist-gate.py`: a corrupt individual task-board file is treated as a "missing" box (blocks, warns) rather than a fail-open "let pass" — this is the CORRECT reading of protection 4, not a violation

Confirmed 2026-08-24, "casillas por programa" (D-052) commit-review. The design doc's protection 4 says "ante error, JSON corrupto o tablero ilegible: DEJA PASAR y lo dice" (on error/corrupt JSON/unreadable board: let pass, and say so) — read too literally, this could mean ANY corrupt task JSON should let the session close. The shipped `hooks/checklist-gate.py::_read_board_tasks()` does something narrower: a corrupt task file is skipped (never crashes, always named in a stderr warning) but the checklist box whose only evidence was that file is counted as "missing" — which CAN trigger a block (bounded by the separate max-2-blocks protection). Before flagging this as a protection-4 violation: the design doc's own "Riesgo tecnico" section (House, verified in execution) clarifies protection 4 at the file level as isolation ("el fail-open... se aplica POR FICHERO: un JSON ilegible no invalida los otros" — an unreadable JSON does not invalidate the OTHERS), not as "an unreadable file counts as done." Treating an unreadable task as automatically-satisfied would open exactly the silent-success hole this project's whole threat model exists to close (a corrupted/truncated task file at the wrong moment silently waving through a genuinely-incomplete box). The max-2-blocks cap already bounds the cost of the stricter reading to at most 2 extra nags before the session can close regardless. Do not flag this design choice as a bug without first checking whether the alternative (corrupt-file-as-silently-satisfied) would itself be the worse failure mode under this project's own "system against itself" model.

## TOCTOU identity-mismatch fd-leak coverage: removing a parametrized attacker-framed test class does not necessarily remove the underlying invariant's coverage

Confirmed 2026-07-18, issue #72 adelgazamiento round. `test_crossplatform_symlink_guard.py::TestWindowsToctouIdentityMismatch` and `test_crossplatform_symlink_guard_hardening.py::TestToctouMismatchAllModes` (both parametrized fd-open/fd-close spies across `r`/`w`/`a` modes and both open() twins) were deleted as attacker-race-framed. Before flagging this as a lost integrity gap (fd leak = resource exhaustion, a legitimate self-harm concern independent of attacker intent), I checked the surviving `TestDeferredTruncateOnIdentityMismatch.test_mismatch_raises_before_ftruncate_and_content_survives` (`test_crossplatform_symlink_guard_hardening.py:329-382`) — it independently asserts `closed_fds == opened_fds` for the exact same lstat/fstat identity-mismatch scenario in mode `"w"` (the mode that matters, since read mode doesn't call ftruncate), PLUS proves `os.ftruncate()` is never called and file content survives. `TestTwinParity.test_toctou_scenario_same_outcome_on_both_twins` (`test_crossplatform_symlink_guard.py:253-280`, surviving) also confirms `OSError` is raised by both twins for the mismatch. Net: the removed classes' `r`/`a`-mode parametrization is gone, but the critical `w`-mode fd-leak + content-integrity invariant is still pinned, arguably more thoroughly than before. Do not flag "attacker-framed class deleted" as an automatic integrity-coverage-loss finding — always check whether a differently-named surviving class already covers the same code path before reporting a gap.
