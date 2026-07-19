# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
Target: atomic CLAUDE.md write (docs/plan/fix-atomic-claude-md-write.md, T1 fix), diff f7945f3..HEAD,
lib/git_helpers.py::_AtomicWriteNoFollowSymlink / open_no_follow_symlink(atomic=True), the 3 real
writers (install_apply._update_claude_md, session-start-crew.py, git-memory-uninstall.py). Round-Trip Sabotage protocol applied per own mandate (this is a producer/consumer seam per the
plan's own §34 tag). Verdict: FALLA. The core no-partial/no-empty-file guarantee holds solidly
(fsync-fail, replace-fail, SIGKILL-during-write, symlink-at-destination, 8-way concurrent
processes, torn-read-during-write -- all verified live, all held). But 4 real, independently-
verified breaks match the task's own named victory conditions, none caught by the existing
14-test acceptance suite (tests/test_atomic_claude_md_write.py, itself run and confirmed 14/14
green -- its permission test only covers the chmod-succeeds happy path, never chmod-fails):
(1) silent permission downgrade -- best-effort `except OSError: pass` around the tmp-file chmod
(git_helpers.py:211-216) means ANY real chmod failure (FAT32/exFAT/restrictive-NFS mounts are the
realistic trigger) silently narrows CLAUDE.md from e.g. 0644 to mkstemp's 0600 default, zero
warning anywhere -- live PoC: mocked only os.chmod, write "succeeded", stdout/stderr both empty,
independent `stat` showed 0600. (2) lost-update race -- the read-diff-write flow has no lock;
a concurrent legitimate writer (user's editor autosave, or literally another one of the
codebase's own 3 writers) landing between the read and the commit is silently destroyed by
os.replace() with no error/merge/warning -- proven through the REAL production function
install_apply._update_claude_md() (not just the raw primitive), and trivially again via two
in-process atomic-writer instances on the same path. (3) os.replace() silently severs hardlinks
-- `ln fileA fileB` (real hardlink) then an atomic write on fileA leaves fileB frozen at stale
content forever, nlink 2->1 on both sides; the codebase's OWN docstring names "hardlink between
git worktrees sharing CLAUDE.md" as an explicitly intended-safe legitimate use case, and its
framing ("sibling unaffected by construction") is true only for content, not for the sharing
relationship itself. DECEPTION T1. (4) orphaned .tmp accumulation on real SIGKILL -- disclosed/
accepted by the implementer's own docstring as unavoidable, but grep confirms NO stale-tmp
cleanup exists anywhere in the codebase; 3 repeated real kill -9s left 3 permanently-accumulating
orphan files in the PROJECT ROOT itself (same dir as CLAUDE.md, not gitignored); 20x normal
sequential writes confirmed zero leak, so this is strictly a crash-only, unbounded artifact.
19 real attempts across 6/7 phases (EXPLOIT N/A -- no auth/injection boundary in this seam, only
integrity concerns, matching project's own system-vs-itself threat model). Full detail in
attack-patterns.md and resilience.md.

## Previous attack (issue #63 round 3, compact)
Target: issue #63 (boot simplification) round 3, branch feat/issue-63-simplificacion-boot vs
main. Round 2's 2 T1s (orphaned-END lying "up to date", needs_upgrade magic-string always-True)
are fixed and confirmed still fixed (any_block_outdated is now the shared oracle for both the
crew content gate and needs_upgrade Check 1; idempotent double-run verified byte-identical).
Re-attacked fresh, focused per instruction on the CLAUDE.md/manifest seam + content-based
upgrade detector. Verdict: FALLA. 2 new live T1s, both via real hooks, both independently
verified (plain os-level read/grep, never through the path that wrote the file):
(1) BREAK -- lib/managed_blocks.py:227-233 `upsert_managed_blocks()`'s orphaned-BEGIN
anchor-splice (the T1-A fix from round 2 itself) treats EVERYTHING between a dangling BEGIN
and the next canonical block's BEGIN as disposable "stray orphaned body" and discards it when
regenerating. Realistic corruption (one deleted END-marker HTML-comment line -- the exact
trigger the fix's own docstring names: merge-conflict resolution, editor auto-fix, accidental
line deletion) with the user's OWN content sitting in that gap (personal notes, runbook,
on-call rotation -- normal practice, nothing forbids writing free text between managed
sections) silently destroys that user content, permanently, with zero warning: the log line
says "regenerated <!-- BEGIN unmassk-toolkit... --> (orphaned END marker)", never "deleted N
bytes of unrecognized content". Confirmed via TWO independent real entry points: (a)
hooks/session-start-crew.py directly, (b) lib/upgrade_check.py's needs_upgrade()==True ->
trigger_auto_upgrade_if_needed() -> the real subprocess to bin/git-memory-install.py --auto ->
install_apply._update_claude_md() -- same shared upsert_managed_blocks(), same destructive
result, completely different call path. Scales: a 500-dangling-marker pathological file (0.068s,
no perf issue) collapsed 61KB to 5.8KB in one run -- an unbounded amount of real content can be
wiped by one small realistic corruption. 6-way concurrent crew.py processes on the same
corrupted file held structurally (valid UTF-8, no crash, no byte corruption) but reproduce the
same data loss, as expected (not a new bug, confirms concurrency doesn't add OR fix anything).
(2) DECEPTION T1 -- lib/boot_health.py:258 `check_version_mismatch()` (the STATUS-line source,
rendered into the real boot banner every session) uses raw string inequality (`installed !=
PLUGIN_VERSION`) while the actual upgrade-trigger oracle, lib/upgrade_check.py:143
`needs_upgrade()` Check 2, correctly uses semver-numeric `<` comparison on the SAME
manifest.json field. Live PoC: manifest.version="9.9.9" (newer than running PLUGIN_VERSION,
e.g. 1.19.4 -- realistic: project last installed while the plugin was on a newer release, then
the marketplace/user pinned an older one without re-running install) makes needs_upgrade()
correctly return False (no upgrade needed) while check_version_mismatch() returns "Plugin
v1.19.4 available (installed: v9.9.9). Suggest /plugin update" -- backwards and false, printed
verbatim in the real session-start-boot.py boot-log/banner output, end-to-end confirmed. Held
(6 live PoCs total): manual block reordering (user moves a whole managed section elsewhere in
the file -- valid, undetectable-as-wrong usage) causes zero content loss and no forced
re-ordering; a legacy-block-name collision (pasted old backup text using a RETIRED legacy
marker name that happens to textually contain another block's real begin-marker string) is
correctly isolated by the legacy regex's own literal END match, doesn't trip the orphan-splice
path, user content survives; idempotent double-run is byte-identical (md5 match across 3 runs);
ANSI-escape/newline injection via manifest.version into the STATUS line re-verified sanitized on
this round's code (stripped ESC, newline->space) exactly as before. The any_block_outdated()
(strip()-tolerant) vs upsert_managed_blocks() (byte-exact) whitespace-only divergence noted as
T3 (self-heals in one write, not a permanent lie) -- not blocking, logged for completeness only.

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
