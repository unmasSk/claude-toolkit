# MEMORY.md — Dante (Test Engineering Agent)

## Topic Files

- [unmassk-toolkit-python-test-conventions.md](unmassk-toolkit-python-test-conventions.md) — pytest conventions: importlib for hyphenated hooks, sys.path fix
- [crown-retraction-design-notes.md](crown-retraction-design-notes.md) — multi-crown edge case: per-commit patch resurfaces superseded crowns
- [skill-router-contract-notes.md](skill-router-contract-notes.md) — per-message skill-router marker contract
- [encoding-contract-notes.md](encoding-contract-notes.md) — #52 cp1252 + #54 surrogate-escape gotchas
- [issue-55-date-parsing-contract-notes.md](issue-55-date-parsing-contract-notes.md) — %aI/fromisoformat fragile-date contract
- [issue-61-ci-flake-hardening-notes.md](issue-61-ci-flake-hardening-notes.md) — CI flake fix: rc-verification vs anti-vacuity retry
- [issue-63-boot-simplification-contract-notes.md](issue-63-boot-simplification-contract-notes.md) — boot-simplification RED contract
- [issue-63-t1-manifest-read-hardening-notes.md](issue-63-t1-manifest-read-hardening-notes.md) — RecursionError + dir-symlink bypass, 3 sites
- [issue-63-p1-v2-content-gate-contract-notes.md](issue-63-p1-v2-content-gate-contract-notes.md) — v2 content-based gate, sabotage test
- [issue-63-p1-v1-retirement-notes.md](issue-63-p1-v1-retirement-notes.md) — v1-gate retirement, cross-file cascade
- [issue-63-producer-hardening-contract-notes.md](issue-63-producer-hardening-contract-notes.md) — apply_plan manifest-stamp gate
- [issue-63-t1-end-marker-magic-string-contract-notes.md](issue-63-t1-end-marker-magic-string-contract-notes.md) — orphaned-END lie, magic-string RED
- [issue-63-magic-string-reconciliation-notes.md](issue-63-magic-string-reconciliation-notes.md) — GREEN reconciliation via managed_blocks.upsert
- [issue-63-t1a-orphaned-end-userdata-loss-contract-notes.md](issue-63-t1a-orphaned-end-userdata-loss-contract-notes.md) — orphaned-END regen deletes user text
- [issue-63-orphaned-end-hardening-round-trip-notes.md](issue-63-orphaned-end-hardening-round-trip-notes.md) — last-block/note-above edges, §34 mtime round-trip
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
- [vocabulary-contract-notes.md](vocabulary-contract-notes.md) — vocabulary.py §6.1 contract, 3-state reader rule
- [zones-contract-notes.md](zones-contract-notes.md) — zones.py §6.2: cross-module-import infra gap
- [similar-contract-notes.md](similar-contract-notes.md) — similar.py §6.5 contract, zone2-only cross-zone design
- [config-contract-notes.md](config-contract-notes.md) — config.py §6.3 contract + type-guard deviation test
- [indexes-contract-and-shared-dir-incident-notes.md](indexes-contract-and-shared-dir-incident-notes.md) — indexes.py §7.3 contract + shared-dir incident
- [rejection-contract-notes.md](rejection-contract-notes.md) — rejection.py §7.4 contract, ten-rejections enumeration
- [format-contract-cross-import-risk-notes.md](format-contract-cross-import-risk-notes.md) — format.py §6.4 contract, cross-import risk
- [gitcmd-contract-notes.md](gitcmd-contract-notes.md) — gitcmd.py §7.1 contract, SIGKILL + reentrancy gotcha
- [mutation-check-collision-incident-ids.md](mutation-check-collision-incident-ids.md) — CRITICAL: overwrote colleague's real model.py
- [import-lib-memory-module-cache-fix-and-stash-incident-notes.md](import-lib-memory-module-cache-fix-and-stash-incident-notes.md) — content-hash cache fix + stash incident
- [validator-contract-notes.md](validator-contract-notes.md) — validator.py §7.5 contract, mandatory isolated-tmp-dir rule
- [five-regressions-format-zones-notes.md](five-regressions-format-zones-notes.md) — 5 round-trip regressions (format.py/zones.py)
- [notes-contract-real-git-failure-notes.md](notes-contract-real-git-failure-notes.md) — notes.py §8.1 RED: index.lock real-failure technique
- [query-contract-notes.md](query-contract-notes.md) — query.py §8.2 contract, transient-git-retry sim
- [dispatch-contract-notes.md](dispatch-contract-notes.md) — dispatch.py §9.8 contract, office-identifier gap
- [moriarty-layer1-race-and-list-folding-regression-notes.md](moriarty-layer1-race-and-list-folding-regression-notes.md) — indexes.py real race + format.py fold gaps
- [notes-three-critical-regressions-notes.md](notes-three-critical-regressions-notes.md) — 3 fixes: blank-paragraph round trip, restore-on-exception
- [rules-contract-notes.md](rules-contract-notes.md) — rules.py §9.7 RED, no-root-param gap
- [health-contract-notes.md](health-contract-notes.md) — health.py Sec.9.4 coverage, gh-mocking technique
- [clusters-contract-notes.md](clusters-contract-notes.md) — clusters.py Sec.9.1 RED, Origin-vs-Replaces mapping
- [context-py-contract-notes.md](context-py-contract-notes.md) — context.py Sec.9.6 RED, HEADLINE_MAX cross-check
- [notes-stdout-only-git-error-regression-notes.md](notes-stdout-only-git-error-regression-notes.md) — git_error empty on stdout-only failure
- [rejection-gitcmd-value-presence-and-stdout-regression-notes.md](rejection-gitcmd-value-presence-and-stdout-regression-notes.md) — build() key-vs-value gap + stdout-only failure
- [deuda-6-18-upstream-guard-regression-notes.md](deuda-6-18-upstream-guard-regression-notes.md) — check_upstream_shares_history() guard regression
- [notes-replace-close-contract-notes.md](notes-replace-close-contract-notes.md) — notes.py replace()/close() RED, NotImplementedError trap
- [issue-double-registration-and-notes-path-bug-notes.md](issue-double-registration-and-notes-path-bug-notes.md) — double-registration fix + notes.py index-root bug
- [notes-cwd-leak-fix-and-guard-fixture-notes.md](notes-cwd-leak-fix-and-guard-fixture-notes.md) — fixed 5 seed-outside-_cwd leaks + HEAD-diff guard
- [boot-report-argus-four-regressions-notes.md](boot-report-argus-four-regressions-notes.md) — 4 Argus-fixed bugs pinned as regression tests
- [id-reuse-regression-notes.md](id-reuse-regression-notes.md) — closed-note-id-reuse fix pinned
- [inject-hook-contract-notes.md](inject-hook-contract-notes.md) — hooks/inject.py RED, fail-open empirical correction
- [boot-launcher-hook-contract-notes.md](boot-launcher-hook-contract-notes.md) — hooks/boot_launcher.py RED, real SessionStart payload
- [issue-deuda25-nested-repo-cwd-anchor-notes.md](issue-deuda25-nested-repo-cwd-anchor-notes.md) — DEUDA #25 RED, nested-repo cwd anchor
- [write-work-missing-lock-contract-notes.md](write-work-missing-lock-contract-notes.md) — write_work() missing file_lock RED contract
- [deuda24-search-by-id-contract-notes.md](deuda24-search-by-id-contract-notes.md) — search.py --id RED (DEUDA #24), vocabulary gap found
- [gitmem-wip-branch-protection-notes.md](gitmem-wip-branch-protection-notes.md) — wip test fixed after 2026-08-03 checkpoint decision
- [deuda-b19-customs-autoenable-rebase-contract-notes.md](deuda-b19-customs-autoenable-rebase-contract-notes.md) — DEUDA B19: customs auto-enable + rebase passthrough hardening
- [deuda27-write-work-two-process-race-notes.md](deuda27-write-work-two-process-race-notes.md) — write_work() DEUDA #27: two-real-process race test, invariant assertion, ablation-for-RED technique
- [wip-script-checkpoint-hardening-notes.md](wip-script-checkpoint-hardening-notes.md) — wip.py first dedicated test file, 15 green, binary round-trip, two-controls-not-one lesson
- [write-work-known-content-none-fallback-contract-notes.md](write-work-known-content-none-fallback-contract-notes.md) — write_work() known_content=None RED: fallback-vs-expect-absent contract + uncaught IsADirectoryError sibling
- [zones-script-english-rename-and-duplicate-bounce-notes.md](zones-script-english-rename-and-duplicate-bounce-notes.md) — zones.py Spanish→English rename + duplicate-zone bounce, chained-RED technique
- [zones-alias-collision-bounce-contract-notes.md](zones-alias-collision-bounce-contract-notes.md) — zones.py alias-collision bounce RED: names-the-owner requirement, resolve()-after invariant
- [deuda17-freshness-disclosure-contract-notes.md](deuda17-freshness-disclosure-contract-notes.md) — DEUDA #17 RED: PULL DIRECTIVE/BRANCHES must disclose unconfirmed remote data, keyword-OR wording-agnostic technique
- [deuda15-foreign-content-silent-discard-contract-notes.md](deuda15-foreign-content-silent-discard-contract-notes.md) — managed_blocks.py upsert() silently discards foreign content inside BEGIN/END, RED contract
- [deuda5-cache-sync-recursive-subdirs-contract-notes.md](deuda5-cache-sync-recursive-subdirs-contract-notes.md) — cache_sync_check.py RED: _dir_fingerprint() non-recursive, empty-cache-dir TypeError fixture gotcha
- [note-script-alias-not-resolved-regression-notes.md](note-script-alias-not-resolved-regression-notes.md) — Moriarty T1: note.py writes zone alias unresolved, note vanishes from index/search
- [note-script-replaces-not-archiving-regression-notes.md](note-script-replaces-not-archiving-regression-notes.md) — note.py --replaces never calls notes.replace(), old note stays live forever; --replaces none control
- [note-script-discard-alternatives-flag-contract-notes.md](note-script-discard-alternatives-flag-contract-notes.md) — note.py --discard flag RED: description-vs-why gotcha for X type, no origin flag needed
- [dante-owner-metric-over-allowlist-feedback.md](dante-owner-metric-over-allowlist-feedback.md) — owner reverses allowlists mid-task; prefer a computed two-branch metric + threshold over a named exception table
- [rejection-relaunch-command-ast-crosscheck-notes.md](rejection-relaunch-command-ast-crosscheck-notes.md) — relaunch commands vs real argparse: AST leaf-visitor gotcha, parse_args-spy technique
- [incident-close-question-contract-notes.md](incident-close-question-contract-notes.md) — remove.py incident-close question: I- asks, M/D don't; AST-radar dodge risk for Ultron
- [test-file-self-drift-correction-notes.md](test-file-self-drift-correction-notes.md) — stale close→remove/required-flag/ablation-result inside test prose itself, annotate-not-delete on test data
- [relaunch-command-answer-amnesia-contract-notes.md](relaunch-command-answer-amnesia-contract-notes.md) — pain-question/overlap rejection cycle never converges, drops --stops across rounds, RED contract
- [incident-close-fence-atomicity-contract-notes.md](incident-close-fence-atomicity-contract-notes.md) — remove.py --restriction new RED: fence rejection must NOT leave incident closed, validate_note pre-check
- [promotes-flag-third-archive-destination-contract-notes.md](promotes-flag-third-archive-destination-contract-notes.md) — --promotes RED via bin/gitmem: third archive destination "promoted to <ID>" had a reader but no writer
- [note-archived-similarity-bypass-contract-notes.md](note-archived-similarity-bypass-contract-notes.md) — query.by_zone() includes archived notes, a closed note wrongly blocks a similar new one; --replaces none guard
- [customs-corrupt-memory-file-escape-hatch-contract-notes.md](customs-corrupt-memory-file-escape-hatch-contract-notes.md) — customs.py RED: corrupt config.json breaks 4 rescue commands; corrupt zones.json doesn't (verified, not assumed)
- [stop-dod-gate-corrupt-config-contract-notes.md](stop-dod-gate-corrupt-config-contract-notes.md) — stop-dod-gate.py RED: corrupt config must warn vs not-configured silence; same-day test-drift fixed
- [zones-list-doctor-absent-vs-empty-contract-notes.md](zones-list-doctor-absent-vs-empty-contract-notes.md) — zones.py list + doctor RED: absent-vs-empty zones.json masking, doctor has zero zones awareness
- [customs-doctor-20260806-two-red-contracts-notes.md](customs-doctor-20260806-two-red-contracts-notes.md) — shlex-failure rescue passthrough + doctor config type-gap; set-iteration-order nondeterminism pitfall
- [scaffold-py-red-contract-notes.md](scaffold-py-red-contract-notes.md) — scaffold.py 4-bug RED contract (TOML/JS interpolation, dead ORM/CSS options, escape); dispatch-table mapping reused
- [gitmem-rule-no-commit-contract-notes.md](gitmem-rule-no-commit-contract-notes.md) — rules.py/rule.py rewritten to never-commit contract, coherence_rules() retired from boot.py CHECKS
- [search-word-zones-catalog-contract-notes.md](search-word-zones-catalog-contract-notes.md) — search.py zero-result word search shows zones catalog before footer; absent-vs-empty parity
- [stop-dod-gate-d042-declared-identity-coverage-notes.md](stop-dod-gate-d042-declared-identity-coverage-notes.md) — D-042 identity coverage gap closed; module-vs-function import gotcha; masked UnicodeDecodeError reported, not fixed
- [note-issue-field-seven-types-contract-notes.md](note-issue-field-seven-types-contract-notes.md) — --issue opens from M-only to all 7 types: two production gates, fake-gh-on-PATH technique
- [boot-open-issues-label-rename-contract-notes.md](boot-open-issues-label-rename-contract-notes.md) — boot counter relabel "plans with a record" to "issues with a live note", keeping Argus's no-GitHub-state invariant
- [render-issue-zone-word-contract-notes.md](render-issue-zone-word-contract-notes.md) — report_render.py never showed Issue on zone/word search: D/I/R contract, issue-0 + cluster hardening
- [work-issue-validation-gap-contract-notes.md](work-issue-validation-gap-contract-notes.md) — work.py --issue N never checks the issue exists at all (Argus gap): reject-if-missing, degrade-with-warning if gh cannot answer
- [stop-dod-gate-fingerprint-cache-contract-notes.md](stop-dod-gate-fingerprint-cache-contract-notes.md) — working-tree fingerprint cache skips reruns when nothing changed; signature survives volatile memory addresses
- [stop-dod-gate-declared-contract-in-flight-notes.md](stop-dod-gate-declared-contract-in-flight-notes.md) — declared test-first RED must not block Stop, new bin/stop-dod-declare.py, per-session, auto-clears on green
- [ci-fake-gh-path-fallthrough-fix-notes.md](ci-fake-gh-path-fallthrough-fix-notes.md) — CI red both platforms: POSIX EACCES-fallthrough + Windows CreateProcess .exe-only, path_without_real_gh() fix, win32 skip
- [work-staged-deletion-git-rm-contract-notes.md](work-staged-deletion-git-rm-contract-notes.md) — gitmem work fails on a deletion already staged with git rm; stage_and_commit() git-add-then-commit gap, RED contract
- [rule-quote-contract-notes.md](rule-quote-contract-notes.md) — gitmem rule --quote RED contract, no-commit contradiction reported not resolved, vacuous-green argparse pitfall
- [rule-commit-i003-contract-notes.md](rule-commit-i003-contract-notes.md) — I-003 RED contract: rule.py must commit for real or not say "guardada", reverses 2026-08-06 no-commit decision (evidenced, not invented)
- [checklist-gate-inject-contract-notes.md](checklist-gate-inject-contract-notes.md) — D-052 checklist hooks: real schema vs guessed, tests/hooks/ collision fix, race/session_id/chmod hardening round
- [d054-shared-textnorm-normalization-contract-notes.md](d054-shared-textnorm-normalization-contract-notes.md) — D-054 lowercase+no-accent everywhere: anchor-at-entry-point technique around a live boundary test, real non-string contradiction left RED
- [boot-git-object-corruption-contract-notes.md](boot-git-object-corruption-contract-notes.md) — surgical .git/objects corruption isolating ONE health check; live cd-safety incident + fix; concurrent-agent RED→GREEN mid-session

## Retired (different stack, no longer this project's shape)

`conventions.md` / `mock-patterns.md` / `edge-cases.md` / `frontend-conventions.md` — bun:test/Vitest/RTL/SQLite/Zod
material from a prior chatroom/omawamapas codebase, not unmassk-toolkit (pure Python). Files kept on disk, unlinked
from this index — irrelevant to this project's recall.

32 more topic files unlinked 2026-08-23 (index over its size ceiling), kept on disk: the v2-build-phase batch
(fase0/capa4/capa5/v1-retirement/48-red-retirement/piezas-sec13/pm-root-migration/health-boot-rule-coherence/
boot-contract-root-vs-pmroot/doctor-zones-check-retirement/issue-81-audit — construction of a now-stable system)
and the attacker-model batch (issue-53 hardlink, issue-57 SUBJECT-vector/NEL-fence/transport-forgery, boot-stdout-
banner v1, feat-boot-freshness) — obsolete per CLAUDE.md: no external attacker in this project, adversarial-input
hardening is dead weight here.
