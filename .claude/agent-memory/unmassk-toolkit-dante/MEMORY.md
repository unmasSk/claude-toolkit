# MEMORY.md — Dante (Test Engineering Agent)

## Topic Files

- [unmassk-toolkit-python-test-conventions.md](unmassk-toolkit-python-test-conventions.md) — pytest conventions: importlib for hyphenated hooks, sys.path fix
- [crown-retraction-design-notes.md](crown-retraction-design-notes.md) — multi-crown edge case: retraction resurfaces superseded crowns
- [skill-router-contract-notes.md](skill-router-contract-notes.md) — per-message skill-router marker contract
- [encoding-contract-notes.md](encoding-contract-notes.md) — #52 cp1252 + #54 surrogate-escape gotchas
- [issue-55-date-parsing-contract-notes.md](issue-55-date-parsing-contract-notes.md) — %aI/fromisoformat fragile-date contract
- [issue-61-ci-flake-hardening-notes.md](issue-61-ci-flake-hardening-notes.md) — CI flake fix: rc-verification vs anti-vacuity retry
- [issue-63-managed-blocks-hardening-notes.md](issue-63-managed-blocks-hardening-notes.md) — issue #63 full arc (9 rounds merged): manifest-read, orphaned-END, v1→v2 gate, producer hardening
- [pre-task-recall-skill-injection-contract-notes.md](pre-task-recall-skill-injection-contract-notes.md) — #68 append-block→DENY-gate, BM25 reconciliation
- [cad-trimesh-validate-mesh-contract-notes.md](cad-trimesh-validate-mesh-contract-notes.md) — validate_mesh.py: trimesh process=True gotcha
- [run-cadquery-stale-output-contract-notes.md](run-cadquery-stale-output-contract-notes.md) — stale-STL silent-failure regression
- [serial-verify-contract-notes.md](serial-verify-contract-notes.md) — serial_verify.py pure-decision separation
- [sensor-gate-contract-notes.md](sensor-gate-contract-notes.md) — sensor_gate.py hardening (69 tests)
- [pending-next-cutoff-contract-notes.md](pending-next-cutoff-contract-notes.md) — pending-Next cutoff RED contract
- [design-gate-contract-notes.md](design-gate-contract-notes.md) — design_gate.py full contract (68 tests)
- [issue-61-read-retry-contract-notes.md](issue-61-read-retry-contract-notes.md) — read-path retry: RED→hardening→repair→close-out
- [issue-61-gc-race-fixture-corruption-notes.md](issue-61-gc-race-fixture-corruption-notes.md) — git gc --auto fork race corrupts fixtures
- [deadend-memo-round-trip-contract-notes.md](deadend-memo-round-trip-contract-notes.md) — Memo:deadend round-trip fidelity
- [trailer-newline-collapse-regression-notes.md](trailer-newline-collapse-regression-notes.md) — build_commit_message() CR/LF collapse fix
- [file-lock-lost-update-contract-notes.md](file-lock-lost-update-contract-notes.md) — file_lock() T1 contract + 3 Moriarty regressions
- [env-var-leak-and-dead-gate-detection-notes.md](env-var-leak-and-dead-gate-detection-notes.md) — run_cmd None-sentinel env removal
- [wrapper-trailer-content-validation-contract-notes.md](wrapper-trailer-content-validation-contract-notes.md) — Memo/Remember validation RED + retirement
- [plugin-sync-line-contract-notes.md](plugin-sync-line-contract-notes.md) — PLUGIN sync-line count-vs-grouped gotcha
- [vocabulary-contract-notes.md](vocabulary-contract-notes.md) — vocabulary.py §6.1, 3-state reader rule
- [zones-py-full-contract-notes.md](zones-py-full-contract-notes.md) — lib/memory/zones.py + zones.py full campaign (5 rounds merged): §6.2 contract + cross-import fix, English rename + duplicate bounce, alias-collision bounce, doctor's check_project_zones() added, absent-vs-empty doctor gap
- [similar-contract-notes.md](similar-contract-notes.md) — similar.py §6.5, zone2-only cross-zone design
- [config-contract-notes.md](config-contract-notes.md) — config.py §6.3 + type-guard deviation test
- [indexes-contract-and-shared-dir-incident-notes.md](indexes-contract-and-shared-dir-incident-notes.md) — indexes.py §7.3 + shared-dir incident
- [rejection-contract-notes.md](rejection-contract-notes.md) — rejection.py §7.4, ten-rejections enumeration
- [format-py-full-contract-notes.md](format-py-full-contract-notes.md) — lib/memory/format.py full campaign (2 rounds merged): §6.4 original contract + cross-import-identity incident, 5 round-trip regressions (4 format.py, 1 zones.json)
- [gitcmd-contract-notes.md](gitcmd-contract-notes.md) — gitcmd.py §7.1, SIGKILL + reentrancy gotcha
- [mutation-check-collision-incident-ids.md](mutation-check-collision-incident-ids.md) — CRITICAL: overwrote colleague's real model.py
- [import-lib-memory-module-cache-fix-and-stash-incident-notes.md](import-lib-memory-module-cache-fix-and-stash-incident-notes.md) — content-hash cache fix + stash incident
- [validator-contract-notes.md](validator-contract-notes.md) — validator.py §7.5, mandatory isolated-tmp-dir rule
- [notes-py-full-contract-notes.md](notes-py-full-contract-notes.md) — lib/memory/notes.py + notes_commit.py full campaign (9 rounds merged): §8.1 contract, replace/close, 3 critical regressions, cwd-leak fix, write_work() hardening, id-reuse (worst bug of the build), staged-deletion gap
- [query-contract-notes.md](query-contract-notes.md) — query.py §8.2, transient-git-retry sim
- [dispatch-contract-notes.md](dispatch-contract-notes.md) — dispatch.py §9.8, office-identifier gap
- [moriarty-layer1-race-and-list-folding-regression-notes.md](moriarty-layer1-race-and-list-folding-regression-notes.md) — indexes.py real race + format.py fold gaps
- [rule-py-full-contract-notes.md](rule-py-full-contract-notes.md) — lib/memory/rules.py + rule.py full campaign (5 rounds merged): original §9.7 contract, never-commit rewrite, --quote, I-003 commit-for-real reversal, --retract/--replaces
- [health-contract-notes.md](health-contract-notes.md) — health.py §9.4 coverage, gh-mocking technique
- [clusters-contract-notes.md](clusters-contract-notes.md) — clusters.py §9.1, Origin-vs-Replaces mapping
- [context-py-contract-notes.md](context-py-contract-notes.md) — context.py §9.6, HEADLINE_MAX cross-check
- [notes-stdout-only-git-error-regression-notes.md](notes-stdout-only-git-error-regression-notes.md) — git_error empty on stdout-only failure
- [rejection-gitcmd-value-presence-and-stdout-regression-notes.md](rejection-gitcmd-value-presence-and-stdout-regression-notes.md) — build() key-vs-value gap + stdout-only failure
- [issue-double-registration-and-notes-path-bug-notes.md](issue-double-registration-and-notes-path-bug-notes.md) — double-registration fix + notes.py index-root bug
- [boot-py-v2-full-contract-notes.md](boot-py-v2-full-contract-notes.md) — memoria-v2 boot.py rendering + health.py coherence (6 rounds merged): coherence_rules() wiring, 4 Argus regressions, COUNTS label rename, corrupted-git-object isolation, BootSummary.issues field, autocrlf-reread fixture fix
- [inject-hook-contract-notes.md](inject-hook-contract-notes.md) — hooks/inject.py RED, fail-open correction
- [boot-launcher-hook-contract-notes.md](boot-launcher-hook-contract-notes.md) — boot_launcher.py RED, real SessionStart payload
- [issue-deuda25-nested-repo-cwd-anchor-notes.md](issue-deuda25-nested-repo-cwd-anchor-notes.md) — DEUDA #25 RED, nested-repo cwd anchor
- [deuda24-search-by-id-contract-notes.md](deuda24-search-by-id-contract-notes.md) — search.py --id RED (#24), vocabulary gap found
- [gitmem-wip-branch-protection-notes.md](gitmem-wip-branch-protection-notes.md) — wip test fixed after 2026-08-03 checkpoint decision
- [customs-py-full-contract-notes.md](customs-py-full-contract-notes.md) — hooks/customs.py full campaign (3 rounds merged): auto-enable + rebase passthrough, corrupt-memory-file escape hatch, archived-key-zone parity with note.py
- [wip-script-checkpoint-hardening-notes.md](wip-script-checkpoint-hardening-notes.md) — wip.py first test file, 15 green, binary round-trip
- [deuda15-foreign-content-silent-discard-contract-notes.md](deuda15-foreign-content-silent-discard-contract-notes.md) — managed_blocks upsert() discards foreign content, RED
- [deuda5-cache-sync-recursive-subdirs-contract-notes.md](deuda5-cache-sync-recursive-subdirs-contract-notes.md) — cache_sync_check RED: _dir_fingerprint non-recursive
- [note-py-script-full-contract-notes.md](note-py-script-full-contract-notes.md) — bin/memory/note.py full campaign (7 rounds merged): alias regression, --replaces archiving, --discard, archived-similarity bypass, exact-key-zone gate, --promotes, --issue seven-types
- [dante-owner-metric-over-allowlist-feedback.md](dante-owner-metric-over-allowlist-feedback.md) — owner prefers computed two-branch metric over allowlist
- [relaunch-command-mechanism-notes.md](relaunch-command-mechanism-notes.md) — gitmem relaunch-command mechanism (2 rounds merged): AST-extracted argparse crosscheck (dead 'close' subcommand found), answer-amnesia cycle bug
- [remove-py-incident-close-full-contract-notes.md](remove-py-incident-close-full-contract-notes.md) — remove.py incident-close feature (2 rounds merged): missing-flag question contract, fence-rejection atomicity fix
- [test-file-self-drift-correction-notes.md](test-file-self-drift-correction-notes.md) — stale prose inside test files, annotate-not-delete
- [stop-dod-gate-py-full-contract-notes.md](stop-dod-gate-py-full-contract-notes.md) — hooks/stop-dod-gate.py full campaign (4 rounds merged): corrupt-config warn, D-042 identity coverage, fingerprint cache, declared-contract-in-flight
- [customs-doctor-20260806-two-red-contracts-notes.md](customs-doctor-20260806-two-red-contracts-notes.md) — shlex-failure rescue + doctor type-gap; set-order pitfall
- [scaffold-py-red-contract-notes.md](scaffold-py-red-contract-notes.md) — scaffold.py 4-bug RED (TOML/JS interpolation, dead options)
- [search-word-zones-catalog-contract-notes.md](search-word-zones-catalog-contract-notes.md) — zero-result word search shows zones catalog before footer
- [render-issue-zone-word-contract-notes.md](render-issue-zone-word-contract-notes.md) — report_render never showed Issue on zone/word search
- [work-issue-validation-gap-contract-notes.md](work-issue-validation-gap-contract-notes.md) — work.py --issue N never checks issue exists (Argus gap)
- [ci-fake-gh-path-fallthrough-fix-notes.md](ci-fake-gh-path-fallthrough-fix-notes.md) — CI red both platforms: EACCES-fallthrough + Windows .exe-only; round 2: dir-vs-file PATH filter; round 4: shutil.which() needs PATHEXT-suffixed names on win32
- [checklist-gate-inject-contract-notes.md](checklist-gate-inject-contract-notes.md) — D-052 checklist hooks: real schema, race/session_id/chmod round
- [d054-shared-textnorm-normalization-contract-notes.md](d054-shared-textnorm-normalization-contract-notes.md) — D-054 lowercase+no-accent: entry-point anchor technique
- [chain-view-full-contract-notes.md](chain-view-full-contract-notes.md) — search.py --chain full campaign (3 rounds merged): D-056 RED contract, cross-zone lineage-loss regression, superseded-labeled-closed regression
- [piezas-sec13-boundary-tests-notes.md](piezas-sec13-boundary-tests-notes.md) — re-linked 2026-08-25: test_boundary.py AST import-graph gate, still live and enforced
- [memoria-v2-zonereport-shared-section-notes.md](memoria-v2-zonereport-shared-section-notes.md) — re-linked 2026-08-25: report.py §9.2 build_zone/build_word original contract, still live, sole source
- [dead-script-retirement-sweep-notes.md](dead-script-retirement-sweep-notes.md) — finding every test tied to a deleted script, not just named ones
- [release-py-contract-notes.md](release-py-contract-notes.md) — rescued from edge-cases.md: bin/release.py/bump-version.py semver, CHANGELOG format, date-rollover technique
- [note-issue-gate-work-quote-contract-notes.md](note-issue-gate-work-quote-contract-notes.md) — D-065/D-066 note.py Q/I issue-gate RED contract (4 rounds merged): 2 CLI gaps, 19-test harness repair, Moriarty's 4-point break (customs-hook bypass, \r-in-quote round-trip loss, --issue none regression, --issue+--work no contradiction)
- [trading-suite-lift-tradermonty-notes.md](trading-suite-lift-tradermonty-notes.md) — tradermonty test-suite lift: conftest merge, thesis_store blocker, US-Eastern calendar list
- [price-check-red-contract-notes.md](price-check-red-contract-notes.md) — price_check.py contract + hardening: real venue shapes, checked_at-after-fetch flaw, entry-point coverage gap
- [position-sizer-independent-crosscheck-notes.md](position-sizer-independent-crosscheck-notes.md) — position_sizer.py hand-computed cross-check: Fraction-first, two-mutant proof, float money display

## Retired (different stack or superseded, kept on disk unlinked)

`conventions.md` / `frontend-conventions.md` — 100% bun:test/Vitest chatroom/omawamapas material, not unmassk-toolkit.

`edge-cases.md` / `mock-patterns.md` — mixed: an early chatroom section, then real unmassk-toolkit content
obsolete because it targets v1-system modules confirmed deleted (`recall.py`, `boot_memory.py`,
`boot_git_checks.py`, `git-memory-*.py`) or is attacker-model hardening CLAUDE.md now excludes. Their one live
section (`edge-cases.md`'s "release.py") was rescued 2026-08-25 into
[release-py-contract-notes.md](release-py-contract-notes.md), replaced in `edge-cases.md` by a pointer, not a gap.

`capa4-hardening-session-notes.md` — re-checked 2026-08-25 (phase 3): its content was almost entirely
duplicated elsewhere (write-order/restore regression already in `rule-py-full-contract-notes.md`'s Round 1
Update; `coherence_rules()` hardening already in `health-contract-notes.md`'s own Update; `DeclaredZoneNotFound`
hardening already in `dispatch-contract-notes.md`'s own Update — all confirmed present by grep). Its one
non-duplicated piece (`gitcmd.commit_empty()`'s verbatim-cleanup technique) was rescued into
[gitcmd-contract-notes.md](gitcmd-contract-notes.md)'s own Update section, replaced here by a pointer.

32 files unlinked 2026-08-23. Named explicitly below by real filename (2026-08-26: a real link-traversal
found 17 had drifted to keyword-only coverage — a batch label is not the filename):

- Attacker-model, obsolete per CLAUDE.md (no external attacker in this project):
  `issue-53-hardlink-reject-contract-notes.md`, `issue-57-fence-a2-close-contract-notes.md`,
  `issue-57-field-displacement-contract-notes.md`, `issue-57-output-saneo-round2d-contract-notes.md`,
  `issue-57-root-fix-subject-vector-contract-notes.md`, `issue-57-round2e-fence-invariant-contract-notes.md`,
  `boot-stdout-banner-contract-notes.md`, `feat-boot-freshness-contract-notes.md`,
  `bench-adversarial-contract-notes.md` (`lib/memory/bench.py` never built, confirmed absent).
- Target module `lib/boot_git_checks.py` confirmed deleted (2026-08-05 commit `615f5cc`, `ls` checked directly):
  `boot-branches-section-contract-notes.md`, `boot-fetch-prune-contract-notes.md`,
  `deuda17-freshness-disclosure-contract-notes.md`, `deuda-6-18-upstream-guard-regression-notes.md`.
- v2-build-phase construction history, superseded by the now-stable shipped system (each already-shipped
  piece's CURRENT contract lives in its own still-linked or merged file, not here):
  `memoria-v2-fase0-conftest-notes.md`, `memoria-v2-fase0-emojis-utf8-contract-notes.md`,
  `memoria-v2-conftest-package-collision-notes.md`, `memoria-v2-48-red-retirement-notes.md`,
  `memoria-v2-boot-memory-precompact-retirement-notes.md`, `memoria-v2-freshness-retirement-notes.md`,
  `capa4-moriarty-round2-five-bugs-plus-single-reader-notes.md`, `capa5-read-scripts-and-facade-contract-notes.md`,
  `capa5-scripts-red-contract-notes.md`, `capa5-six-regressions-notes_commit-close-health-bench-reindex-notes.md`,
  `capa5-work-branch-protection-and-similarity-fix-notes.md`, `pm-root-migration-test-alignment-notes.md`,
  `boot-contract-root-vs-pmroot-notes.md`, `issue-81-suite-audit-reconfirmation-notes.md`,
  `gitto-retirement-test-mapping-notes.md` (superseded by test_boundary.py's AST orphan gate, itself re-linked
  phase 3 via [piezas-sec13-boundary-tests-notes.md](piezas-sec13-boundary-tests-notes.md)).
- v1→v2 migration bookkeeping itself, now historical: `v1-guard-changeover-2026-08-05-notes.md`,
  `v1-retirement-batch-notes.md`.

**Phase 3 (2026-08-25) — re-linked, NOT retired** (target confirmed still on disk, same technique that
caught the 4 `boot_git_checks.py` files): [piezas-sec13-boundary-tests-notes.md](piezas-sec13-boundary-tests-notes.md)
(`test_boundary.py` still live) and [memoria-v2-zonereport-shared-section-notes.md](memoria-v2-zonereport-shared-section-notes.md)
(`report.py::build_zone`/`build_word` still live). Two more of the same kind had a live merge partner instead
of a standalone re-link: `doctor-zones-check-retirement-notes.md` → [zones-py-full-contract-notes.md](zones-py-full-contract-notes.md)
Round 4; `health-boot-rule-coherence-wiring-notes.md` → [boot-py-v2-full-contract-notes.md](boot-py-v2-full-contract-notes.md)
Round 1.

9 issue-63 files merged 2026-08-25 (phase 1) into [issue-63-managed-blocks-hardening-notes.md](issue-63-managed-blocks-hardening-notes.md).
39 files merged 2026-08-25 (phase 2) into 9 same-theme campaign files:
[rule-py-full-contract-notes.md](rule-py-full-contract-notes.md) (5),
[zones-py-full-contract-notes.md](zones-py-full-contract-notes.md) (4→5, phase 3),
[stop-dod-gate-py-full-contract-notes.md](stop-dod-gate-py-full-contract-notes.md) (4),
[note-py-script-full-contract-notes.md](note-py-script-full-contract-notes.md) (7),
[customs-py-full-contract-notes.md](customs-py-full-contract-notes.md) (3),
[chain-view-full-contract-notes.md](chain-view-full-contract-notes.md) (3),
[relaunch-command-mechanism-notes.md](relaunch-command-mechanism-notes.md) (2),
[remove-py-incident-close-full-contract-notes.md](remove-py-incident-close-full-contract-notes.md) (2),
[notes-py-full-contract-notes.md](notes-py-full-contract-notes.md) (9).
2 more files merged 2026-08-25 (phase 3) into [format-py-full-contract-notes.md](format-py-full-contract-notes.md)
(format.py §6.4 contract + the 5-regression batch), plus 2 files folded as extra rounds into the phase-2
campaigns above (`doctor-zones-check-retirement-notes.md` → zones cluster, `health-boot-rule-coherence-wiring-notes.md`
→ boot-py-v2 cluster). Every episode kept under its own dated heading, nothing cut.

Files deliberately left un-merged (weaker thematic fit, reasons in each declining file's own
preamble) are all directly linked above in Topic Files already — no separate list needed here.
