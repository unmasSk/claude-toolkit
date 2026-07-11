# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
Target: issue #63 (boot simplification) round 2, branch feat/issue-63-simplificacion-boot vs main
(the version-gate this file's round-1 FALLA broke was already deleted -- redesigned to a content
gate, decision 2d56444: crew.py ALWAYS reads+diffs CLAUDE.md, only skips the WRITE when
new_content==content). Re-attacked the whole seam fresh. Verdict: FALLA. 2 new T1s, both live,
both via the real hooks/installer, never through the vulnerable path itself for verification:
(1) BREAK+DECEPTION -- lib/managed_blocks.py:190 `upsert_managed_blocks()` checks only `begin in
content`, never that `end` is ALSO present. Deleting one block's END marker (realistic: merge-
conflict resolution, editor auto-fix, accidental line deletion) leaves a dangling BEGIN with no
matching END; the begin...end regex can't match, `pattern.sub` no-ops, and the code logs
`"up-to-date {begin}"` -- a lie, confirmed false via independent `grep -c END` (0). Permanent:
2 consecutive real `session-start-crew.py` runs both still say "All managed blocks up to date"
while the file stays corrupted forever (the write only fires on a diff, and there never is one).
Defeats decision 2d56444's own stated goal ("veneno -> regenera") for exactly the malformed case.
(2) DECEPTION -- lib/upgrade_check.py:102 `needs_upgrade()` Check 1 requires literal string
"Context Checkpoint Commits" inside the block to consider it current; that string has NEVER
existed in the real managed block content (`git log --all -S` = zero hits in managed_blocks.py/
git-memory-install.py) -- only test fixtures fake it (one commit message literally admits
"neutraliza Check 1... en vez de arreglarlo"). Live-confirmed on a from-scratch real install
(manifest.version==PLUGIN_VERSION, CLAUDE.md 100% canonical): `needs_upgrade()` still returns
True. End-to-end: running the real `session-start-boot.py` twice on an already-current install
re-stamps manifest.json's installed_at BOTH times -- the nested full-reinstall subprocess fires
on literally every boot, forever, contradicting #63's own docstring claim ("subprocess... once the
manifest fell behind"). Pre-existing bug (byte-identical on main, previously fired every message
instead of every session -- #63 improved frequency but never fixed the root cause, and its new
prose asserts a conditional guarantee that isn't real). STATUS line itself unaffected (separate,
correct function). Held (11 live PoCs total): the exact chmod-444-CLAUDE.md producer-sabotage that
broke round 1 -- lib/install_apply.py's `apply_plan()` now correctly withholds `_create_manifest()`
when `errors` is non-empty, `trigger_auto_upgrade_if_needed()` now surfaces the non-zero returncode
as a stderr breadcrumb (was previously discarded), self-heals correctly once the real permission
issue is fixed; crew.py fail-open (no crash/hang) against a locked+diverged file (mislabeled error
text, T3 cosmetic only); needs_upgrade's Check-2 symlinked-.claude-parent guard (SEC-T1-002,
isolated by artificially bypassing Check 1) correctly rejects a poisoned manifest; ANSI/newline
injection via manifest.version into the STATUS line (already sanitized, pre-existing); 8-way and
6-way real concurrent processes (crew.py + full nested installer, the realistic multi-terminal
scenario the always-True bug makes routine, not rare) -- CLAUDE.md/manifest.json stayed valid
UTF-8/JSON, byte-identical to idempotent regen, no corruption; 6MB pathological CLAUDE.md with 300
fake legacy blocks -- 0.05s, correct strip, no regex blowup. See attack-patterns.md's newest 2
entries for the reusable patterns.

## Previous attack (issue #63 round 1, compact)
- FALLA, T1 Round-Trip Sabotage on the OLD manifest-version gate (`_manifest_version_matches()`, since deleted -- replaced by round 2's content gate, decision 2d56444). Producer sabotage (chmod 444 CLAUDE.md) let `_create_manifest()` stamp VERSION anyway despite the write failing; zero-failure trust-forgery via pre-committed manifest.json; CLAUDE.md deleted while manifest survives never got recreated. Full detail in attack-patterns.md and round 2's summary above (round 2 re-verified all 3 PoCs now hold).

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
