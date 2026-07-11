# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
Target: issue #63 (boot simplification) branch feat/issue-63-simplificacion-boot, Cerberus+Argus
already fixed their 2 T1. Verdict: FALLA, T1 Round-Trip Sabotage on the NEW manifest-trust seam
(hooks/session-start-boot.py writes .claude/.unmassk/manifest.json's version -> hooks/
session-start-crew.py:86 `_manifest_version_matches()` trusts it to skip CLAUDE.md diff+rewrite
entirely). 3 independent live PoCs, all confirmed via plain `cat`/`md5`/`grep` (never through the
vulnerable gate itself): (1) sabotaged the REAL producer -- chmod 444 on a real CLAUDE.md with
old-style markers, ran the real hook chain (session-start-boot.py -> bin/git-memory-install.py
--auto) -- `_update_claude_md()`'s write raises, but lib/install_apply.py's `apply_plan()` does
NOT stop on a per-action exception (just appends to `errors[]`, loop continues) so
`_create_manifest()` still runs right after and writes manifest.version==VERSION anyway; the
subprocess call in lib/upgrade_check.py::trigger_auto_upgrade_if_needed discards
returncode/stdout/stderr entirely (bare `subprocess.run(...)`, unassigned) -- CLAUDE.md left with
the stale block + missing 4/5 managed blocks, both hooks print success, exit 0. (2) zero-failure
variant: a repo can just pre-commit manifest.json with the current (public) VERSION string next
to a poisoned CLAUDE.md managed block -- first-ever SessionStart on the clone trusts it forever,
no diff ever runs (pure trust-forgery, no adversary capability needed beyond `git commit`).
(3) ABUSE: gate at session-start-crew.py:86 runs BEFORE line 91's `claude_md.exists()` check -- a
user who deletes CLAUDE.md while a matching manifest.json survives on disk gets it silently never
recreated. DECEPTION: the existing test (test_crew_manifest_version_gate.py) only proves the
happy-path invariant via a synthetic always-succeeds `_install()` fixture -- it never sabotages
the real producer, so it never catches (1)-(3). Held: boot_health.py's `_is_real_repo_source` +
scoped skill-drift index (self-check against the real dev repo, correct drift list, no crash);
RecursionError->broad-Exception fix in both boot_health.check_version_mismatch and crew.py's gate
(100k-deep nested manifest.json, no crash, safe fail-open); 2 concurrent session-start-boot.py
processes on the same repo (no truncated/corrupted CLAUDE.md or manifest.json); removed pre-v1.0.0
migrations (_migrate_runtime_to_unmassk/_migrate_untrack_generated_jsons) confirmed as documented
accepted-loss, still reachable via explicit `git memory upgrade`, not silently broken. See
attack-patterns.md's newest entry for the reusable pattern.

## Previous attack (issue #60, compact — all rounds)
- v4 round 4 (FINAL) -- AGUANTA, re-attacked the `url == remote_name` guard (lib/boot_git_checks.py:725) that closed round 3's break; 0 breaks, 4/4 regression + 8-way concurrency held.
- v3 round 3 (decision 787b698) -- FALLA, T1: `git remote get-url` falls back to the literal remote NAME when the URL is unset (`git remote set-url origin ""`, one ordinary command) -- forged `MEMORY: remote (synced)` across unrelated repos sharing a common alias. Root: lib/boot_git_checks.py:704-709. Led to round 4's guard (now holding).
- v2 round (decision 90d096d) -- FALLA, T1: own-fetch-success-stamp bound identity by LOCAL ALIAS STRINGS only, no URL signal -- a `cp`'d stamp forged sync status. Led to v3.
- v1 (decision ceef426) -- FALLA, T1 Round-Trip Sabotage: bare FETCH_HEAD-mtime rendered false "synced" from either the boot's own failed fetch or an unrelated remote's real fetch touching the same file.

## Previous attack (older rounds, compact)
- Issue #59 (A2 token-fence infalsifiability, decision feed852) -- FALLA, 2 live T1 EXPLOITs (Unicode Cf invisible-format-char fence bypass) + 1 T1 structural DECEPTION (nonce outside the trust boundary).
- Issue #57 (log-parsing/field-displacement, several rounds) -- FALLA then DEBIL then AGUANTA across rounds; \x1f/\x1c/\x1d/\x1e/NEL fence-splice gaps found and closed progressively.
- F6 hard-link bypass rejection (issue #53) -- AGUANTA, 8 real PoCs, 0 breaks.
- Issue #55 date-parsing migration -- DEBIL, 3 real breaks (year-10000+ overflow, negative "days ago", silent --json date-format change).
- Boot memory freshness multi-machine (issue #49, 3 rounds) -- round1 DEBIL (2 breaks) → round2 AGUANTA → round3 AGUANTA (1 new T2 via Round-Trip Sabotage).
- git_helpers.py encoding seam Round-Trip Sabotage and any rounds older than the above: see attack-patterns.md / resilience.md (not reproduced here).
