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
- [boot-branches-section-contract-notes.md](boot-branches-section-contract-notes.md) — BRANCHES: origin/HEAD alias gotcha
- [boot-fetch-prune-contract-notes.md](boot-fetch-prune-contract-notes.md) — missing --prune leaves deleted branches listed
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
- [zones-contract-notes.md](zones-contract-notes.md) — zones.py §6.2: cross-module-import infra gap
- [similar-contract-notes.md](similar-contract-notes.md) — similar.py §6.5, zone2-only cross-zone design
- [config-contract-notes.md](config-contract-notes.md) — config.py §6.3 + type-guard deviation test
- [indexes-contract-and-shared-dir-incident-notes.md](indexes-contract-and-shared-dir-incident-notes.md) — indexes.py §7.3 + shared-dir incident
- [rejection-contract-notes.md](rejection-contract-notes.md) — rejection.py §7.4, ten-rejections enumeration
- [format-contract-cross-import-risk-notes.md](format-contract-cross-import-risk-notes.md) — format.py §6.4, cross-import risk
- [gitcmd-contract-notes.md](gitcmd-contract-notes.md) — gitcmd.py §7.1, SIGKILL + reentrancy gotcha
- [mutation-check-collision-incident-ids.md](mutation-check-collision-incident-ids.md) — CRITICAL: overwrote colleague's real model.py
- [import-lib-memory-module-cache-fix-and-stash-incident-notes.md](import-lib-memory-module-cache-fix-and-stash-incident-notes.md) — content-hash cache fix + stash incident
- [validator-contract-notes.md](validator-contract-notes.md) — validator.py §7.5, mandatory isolated-tmp-dir rule
- [five-regressions-format-zones-notes.md](five-regressions-format-zones-notes.md) — 5 round-trip regressions (format.py/zones.py)
- [notes-contract-real-git-failure-notes.md](notes-contract-real-git-failure-notes.md) — notes.py §8.1, index.lock real-failure technique
- [query-contract-notes.md](query-contract-notes.md) — query.py §8.2, transient-git-retry sim
- [dispatch-contract-notes.md](dispatch-contract-notes.md) — dispatch.py §9.8, office-identifier gap
- [moriarty-layer1-race-and-list-folding-regression-notes.md](moriarty-layer1-race-and-list-folding-regression-notes.md) — indexes.py real race + format.py fold gaps
- [notes-three-critical-regressions-notes.md](notes-three-critical-regressions-notes.md) — blank-paragraph round trip, restore-on-exception
- [rules-contract-notes.md](rules-contract-notes.md) — rules.py §9.7 RED, no-root-param gap
- [health-contract-notes.md](health-contract-notes.md) — health.py §9.4 coverage, gh-mocking technique
- [clusters-contract-notes.md](clusters-contract-notes.md) — clusters.py §9.1, Origin-vs-Replaces mapping
- [context-py-contract-notes.md](context-py-contract-notes.md) — context.py §9.6, HEADLINE_MAX cross-check
- [notes-stdout-only-git-error-regression-notes.md](notes-stdout-only-git-error-regression-notes.md) — git_error empty on stdout-only failure
- [rejection-gitcmd-value-presence-and-stdout-regression-notes.md](rejection-gitcmd-value-presence-and-stdout-regression-notes.md) — build() key-vs-value gap + stdout-only failure
- [deuda-6-18-upstream-guard-regression-notes.md](deuda-6-18-upstream-guard-regression-notes.md) — check_upstream_shares_history() guard regression
- [notes-replace-close-contract-notes.md](notes-replace-close-contract-notes.md) — replace()/close() RED, NotImplementedError trap
- [issue-double-registration-and-notes-path-bug-notes.md](issue-double-registration-and-notes-path-bug-notes.md) — double-registration fix + notes.py index-root bug
- [notes-cwd-leak-fix-and-guard-fixture-notes.md](notes-cwd-leak-fix-and-guard-fixture-notes.md) — fixed 5 seed-outside-_cwd leaks + HEAD-diff guard
- [boot-report-argus-four-regressions-notes.md](boot-report-argus-four-regressions-notes.md) — 4 Argus-fixed bugs pinned as regressions
- [id-reuse-regression-notes.md](id-reuse-regression-notes.md) — closed-note-id-reuse fix pinned
- [inject-hook-contract-notes.md](inject-hook-contract-notes.md) — hooks/inject.py RED, fail-open correction
- [boot-launcher-hook-contract-notes.md](boot-launcher-hook-contract-notes.md) — boot_launcher.py RED, real SessionStart payload
- [issue-deuda25-nested-repo-cwd-anchor-notes.md](issue-deuda25-nested-repo-cwd-anchor-notes.md) — DEUDA #25 RED, nested-repo cwd anchor
- [write-work-missing-lock-contract-notes.md](write-work-missing-lock-contract-notes.md) — write_work() missing file_lock RED
- [deuda24-search-by-id-contract-notes.md](deuda24-search-by-id-contract-notes.md) — search.py --id RED (#24), vocabulary gap found
- [gitmem-wip-branch-protection-notes.md](gitmem-wip-branch-protection-notes.md) — wip test fixed after 2026-08-03 checkpoint decision
- [deuda-b19-customs-autoenable-rebase-contract-notes.md](deuda-b19-customs-autoenable-rebase-contract-notes.md) — B19: customs auto-enable + rebase passthrough
- [deuda27-write-work-two-process-race-notes.md](deuda27-write-work-two-process-race-notes.md) — #27: two-real-process race, invariant, ablation-for-RED
- [wip-script-checkpoint-hardening-notes.md](wip-script-checkpoint-hardening-notes.md) — wip.py first test file, 15 green, binary round-trip
- [write-work-known-content-none-fallback-contract-notes.md](write-work-known-content-none-fallback-contract-notes.md) — known_content=None: fallback-vs-absent + IsADirectoryError
- [zones-script-english-rename-and-duplicate-bounce-notes.md](zones-script-english-rename-and-duplicate-bounce-notes.md) — Spanish→English rename + duplicate-zone bounce
- [zones-alias-collision-bounce-contract-notes.md](zones-alias-collision-bounce-contract-notes.md) — alias-collision bounce RED, names-the-owner requirement
- [deuda17-freshness-disclosure-contract-notes.md](deuda17-freshness-disclosure-contract-notes.md) — #17: PULL/BRANCHES must disclose unconfirmed remote data
- [deuda15-foreign-content-silent-discard-contract-notes.md](deuda15-foreign-content-silent-discard-contract-notes.md) — managed_blocks upsert() discards foreign content, RED
- [deuda5-cache-sync-recursive-subdirs-contract-notes.md](deuda5-cache-sync-recursive-subdirs-contract-notes.md) — cache_sync_check RED: _dir_fingerprint non-recursive
- [note-script-alias-not-resolved-regression-notes.md](note-script-alias-not-resolved-regression-notes.md) — Moriarty T1: note.py writes zone alias unresolved
- [note-script-replaces-not-archiving-regression-notes.md](note-script-replaces-not-archiving-regression-notes.md) — --replaces never calls notes.replace(); --replaces none control
- [note-script-discard-alternatives-flag-contract-notes.md](note-script-discard-alternatives-flag-contract-notes.md) — --discard RED: description-vs-why gotcha for X type
- [dante-owner-metric-over-allowlist-feedback.md](dante-owner-metric-over-allowlist-feedback.md) — owner prefers computed two-branch metric over allowlist
- [rejection-relaunch-command-ast-crosscheck-notes.md](rejection-relaunch-command-ast-crosscheck-notes.md) — relaunch vs real argparse: AST leaf-visitor, parse_args-spy
- [incident-close-question-contract-notes.md](incident-close-question-contract-notes.md) — remove.py: I- asks, M/D don't; AST-radar dodge risk
- [test-file-self-drift-correction-notes.md](test-file-self-drift-correction-notes.md) — stale prose inside test files, annotate-not-delete
- [relaunch-command-answer-amnesia-contract-notes.md](relaunch-command-answer-amnesia-contract-notes.md) — pain-question/overlap cycle never converges, drops --stops
- [incident-close-fence-atomicity-contract-notes.md](incident-close-fence-atomicity-contract-notes.md) — --restriction new RED: fence rejection must not close incident
- [promotes-flag-third-archive-destination-contract-notes.md](promotes-flag-third-archive-destination-contract-notes.md) — --promotes RED: "promoted to <ID>" had reader, no writer
- [note-archived-similarity-bypass-contract-notes.md](note-archived-similarity-bypass-contract-notes.md) — by_zone() includes archived notes, wrongly blocks new one
- [customs-corrupt-memory-file-escape-hatch-contract-notes.md](customs-corrupt-memory-file-escape-hatch-contract-notes.md) — corrupt config.json breaks rescue commands; zones.json doesn't
- [stop-dod-gate-corrupt-config-contract-notes.md](stop-dod-gate-corrupt-config-contract-notes.md) — corrupt config must warn vs not-configured silence
- [zones-list-doctor-absent-vs-empty-contract-notes.md](zones-list-doctor-absent-vs-empty-contract-notes.md) — absent-vs-empty zones.json masking, doctor unaware
- [customs-doctor-20260806-two-red-contracts-notes.md](customs-doctor-20260806-two-red-contracts-notes.md) — shlex-failure rescue + doctor type-gap; set-order pitfall
- [scaffold-py-red-contract-notes.md](scaffold-py-red-contract-notes.md) — scaffold.py 4-bug RED (TOML/JS interpolation, dead options)
- [gitmem-rule-no-commit-contract-notes.md](gitmem-rule-no-commit-contract-notes.md) — rules.py rewritten to never-commit; coherence_rules() retired
- [search-word-zones-catalog-contract-notes.md](search-word-zones-catalog-contract-notes.md) — zero-result word search shows zones catalog before footer
- [stop-dod-gate-d042-declared-identity-coverage-notes.md](stop-dod-gate-d042-declared-identity-coverage-notes.md) — D-042 coverage gap; masked UnicodeDecodeError reported
- [note-issue-field-seven-types-contract-notes.md](note-issue-field-seven-types-contract-notes.md) — --issue opens M-only to all 7 types, fake-gh-on-PATH
- [boot-open-issues-label-rename-contract-notes.md](boot-open-issues-label-rename-contract-notes.md) — boot counter relabel, Argus no-GitHub-state invariant kept
- [render-issue-zone-word-contract-notes.md](render-issue-zone-word-contract-notes.md) — report_render never showed Issue on zone/word search
- [work-issue-validation-gap-contract-notes.md](work-issue-validation-gap-contract-notes.md) — work.py --issue N never checks issue exists (Argus gap)
- [stop-dod-gate-fingerprint-cache-contract-notes.md](stop-dod-gate-fingerprint-cache-contract-notes.md) — fingerprint cache skips reruns; survives volatile addresses
- [stop-dod-gate-declared-contract-in-flight-notes.md](stop-dod-gate-declared-contract-in-flight-notes.md) — declared RED must not block Stop, stop-dod-declare.py
- [ci-fake-gh-path-fallthrough-fix-notes.md](ci-fake-gh-path-fallthrough-fix-notes.md) — CI red both platforms: EACCES-fallthrough + Windows .exe-only
- [work-staged-deletion-git-rm-contract-notes.md](work-staged-deletion-git-rm-contract-notes.md) — work fails on deletion already staged with git rm
- [rule-quote-contract-notes.md](rule-quote-contract-notes.md) — --quote RED, no-commit contradiction reported not resolved
- [rule-commit-i003-contract-notes.md](rule-commit-i003-contract-notes.md) — I-003: rule.py must commit for real, reverses 2026-08-06 decision
- [checklist-gate-inject-contract-notes.md](checklist-gate-inject-contract-notes.md) — D-052 checklist hooks: real schema, race/session_id/chmod round
- [d054-shared-textnorm-normalization-contract-notes.md](d054-shared-textnorm-normalization-contract-notes.md) — D-054 lowercase+no-accent: entry-point anchor technique
- [boot-git-object-corruption-contract-notes.md](boot-git-object-corruption-contract-notes.md) — surgical .git/objects corruption isolating one health check
- [d056-lineage-and-chain-view-contract-notes.md](d056-lineage-and-chain-view-contract-notes.md) — D-056 RED: archived marker, Replaces link, new --chain flag
- [note-exact-key-zone-duplicate-gate-contract-notes.md](note-exact-key-zone-duplicate-gate-contract-notes.md) — same-keys+same-zone exact-match gate RED; zone-pair-as-set
- [rule-retract-replace-contract-notes.md](rule-retract-replace-contract-notes.md) — --retract/--replaces RED: mandatory --kind, bare-text match
- [customs-archived-key-zone-duplicate-parity-notes.md](customs-archived-key-zone-duplicate-parity-notes.md) — customs.py missing note.py's archived-notes filter
- [chain-view-cross-zone-lineage-loss-regression-notes.md](chain-view-cross-zone-lineage-loss-regression-notes.md) — --chain drops lineage when head re-archived elsewhere
- [chain-view-superseded-labeled-closed-contract-notes.md](chain-view-superseded-labeled-closed-contract-notes.md) — --chain mislabels superseded head "cerrada" (lying)
- [dead-script-retirement-sweep-notes.md](dead-script-retirement-sweep-notes.md) — finding every test tied to a deleted script, not just named ones

## Retired (different stack or superseded, kept on disk unlinked)

`conventions.md` / `frontend-conventions.md` — 100% bun:test/Vitest chatroom/omawamapas material, not unmassk-toolkit.

`edge-cases.md` / `mock-patterns.md` — corrected 2026-08-25: **not** pure chatroom (prior claim false, checked by
full re-read). Mixed: an early chatroom section, then real unmassk-toolkit content obsolete because it targets
v1-system modules confirmed deleted (`recall.py`, `boot_memory.py`, `boot_git_checks.py`, `git-memory-*.py`) or is
attacker-model hardening CLAUDE.md now excludes. One live exception: `edge-cases.md`'s "release.py" section
targets `bin/release.py`/`bump-version.py`, confirmed still in use — worth re-extracting next time touched.

32 files unlinked 2026-08-23, +2 more 2026-08-25 (`bench-adversarial` — bench.py never built, confirmed absent;
`gitto-retirement-test-mapping` — superseded by test_boundary.py's AST orphan gate): the v2-build-phase batch
(fase0/capa4/capa5/v1-retirement/48-red-retirement/piezas-sec13/pm-root-migration/health-boot-rule-coherence/
boot-contract-root-vs-pmroot/doctor-zones-check-retirement/issue-81-audit/gitto/every other memoria-v2-* file
(precompact-retirement, conftest-collision, freshness-retirement, zonereport) — construction of a now-stable
system) and the attacker-model batch (issue-53 hardlink/issue-57 SUBJECT-vector-NEL-fence-transport-forgery/
boot-stdout-banner-v1/feat-boot-freshness/bench-adversarial — no external attacker, see CLAUDE.md).

9 issue-63 files merged 2026-08-25 into [issue-63-managed-blocks-hardening-notes.md](issue-63-managed-blocks-hardening-notes.md)
(same work split only by date, protocol point 5) — content fully preserved, nothing cut.
