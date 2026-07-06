# Attack Patterns — What Worked

## Mixed alphanumeric tokens silently dropped by tokenizer
- Pattern: query containing `[A-Z]{1,2}\d+` or `\d+[A-Za-z]+` tokens (BM25, v2, auth3)
- The regex `[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]{3,}` only captures pure-letter sequences of 3+
- 'BM25' produces empty token set → no matches even when corpus has BM25 entries
- Works on any codebase using this tokenizer for technical terms

## Fixed SCAN_DEPTH with no warning when corpus exceeds it
- SCAN_DEPTH=500 is hardcoded. If repo has >500 commits, old entries silently disappear.
- No error, no warning — `(no matches)` for entries that exist but are beyond horizon
- Effective attack: large/old repos with important early decisions silently invisible

## Tombstone normalization asymmetry via HTML comment chars
- Tombstone collected via `normalize(trailers[key])` — does NOT call `_sanitize()`
- Entry text stored via `_sanitize(trailers[kind])` then `normalize(text)`
- If entry text contains `<!--` or `-->`, sanitize removes them, normalize sees different string
- Tombstone norm: `'antipattern - <!-- note --> use bm25'`
- Entry norm: `'antipattern - note use bm25'` → no match → tombstone fails to suppress

## git add does not clear pre-staged index entries (release.py / --allow-dirty)
- Pattern: script uses `git add -- [specific files]` to stage only release files
- If attacker (or user) has pre-staged unrelated files before running with --allow-dirty,
  those files REMAIN in the git index and are included in the commit
- `git add -- [files]` ADDS to index; it does NOT reset existing staged changes
- Root location: `_execute_stage` in `bin/release.py:335`
- Fix pattern: `git reset HEAD` before selective `git add`, or pass explicit paths to `git commit`

## SEMVER_RE accepts leading zeros (1.04.0, 01.0.0)
- Pattern: `r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$"` matches `\d+` which allows leading zeros
- `int('04') = 4` so `_semver_tuple('1.04.0') = (1,4,0)` — semantically same as 1.4.0
- The invalid version string '1.04.0' passes validation and gets stored verbatim in JSON
- Root location: `SEMVER_RE` in `bin/release.py:37`, `_semver_tuple` in `bin/release.py:60`

## Pre-release suffix creates one-way ratchet via tuple stripping
- Pattern: `_semver_tuple` strips suffix before comparison: '1.4.0-rc1' → (1,4,0)
- Result: 1.4.0-rc1 releases successfully (accepted as > 1.3.0 → passes)
- But then 1.4.0 FINAL is blocked: (1,4,0) <= (1,4,0) → rejected as "not greater"
- A single pre-release release permanently blocks the final release of that version
- Root location: `_semver_tuple` in `bin/release.py:60`

## CHANGELOG regex operates on first match only — multiple [Unreleased] silently ignored
- Pattern: `re.search(...)` finds first `## [Unreleased]` — second occurrence is silently left
- Multiple [Unreleased] blocks: only the first one gets promoted; second stays as-is
- Root: `_promote_changelog` + `_check_unreleased_not_empty` in `bin/release.py:244,270`

## [Unreleased] with only subsection headers passes the "not empty" check
- `section_body.strip()` is non-empty when body contains `### Added\n\n### Changed`
- Subsection headers without entries count as "content" → release proceeds
- An empty-entries changelog gets promoted and committed
- Root location: `_check_unreleased_not_empty` in `bin/release.py:239`

## Malformed CHANGELOG structure not validated — [Unreleased] after version entry
- Script does not verify that [Unreleased] is the topmost version section
- If CHANGELOG has [1.3.0] before [Unreleased], the new [1.4.0] is inserted after [1.3.0]
- Result: committed changelog with version entries in wrong order
- Root: `_promote_changelog` in `bin/release.py:260` — no structural validation

## subprocess.TimeoutExpired uncaught in upgrade path (user-prompt-memory-check.py)
- Pattern: `subprocess.run(..., timeout=15)` at lines 171-174 of the hook has NO try/except
- When `needs_upgrade()` returns True AND the install script runs > 15s: `TimeoutExpired` propagates
- Hook exits with rc != 0 — breaks the session-level fail-open guarantee
- Root location: `hooks/user-prompt-memory-check.py:171-174`, `main()` function
- Trigger: old-style CLAUDE.md block + slow filesystem / network stall during install
- Severity: T1 — directly violates the stated "exit 0: Always" contract

## post-validate-commit-trailers.py: int() crash on non-numeric exit_code
- Pattern: `int(exit_code)` at line 183 raises ValueError/TypeError on non-numeric values
- `exit_code='zero'` → `ValueError: invalid literal for int()`
- `exit_code=[0]` → `TypeError: int() argument must be a string, a bytes-like object...`
- Hook exits with rc=1 (crash) instead of rc=0 (fail-open)
- Root: `post-validate-commit-trailers.py:183`

## pre-validate-commit-trailers.py: overly broad regex blocks legitimate commands
- Pattern: `re.search(r'\bgit\b.*\blog\b', command)` matches any command with 'git' AND 'log' tokens
- `echo git log` → blocked with exit=2 (false positive)
- `cat git.log` → blocked with exit=2 (false positive — git.log is a filename)
- `git log-remote` → blocked with exit=2 (false positive — different subcommand)
- Only applies when CLAUDE_CODE=1 env is set (Claude agents)
- Root: `pre-validate-commit-trailers.py:150-157`

## session-start-crew.py: UnicodeDecodeError on non-UTF-8 CLAUDE.md
- Pattern: `claude_md.read_text(encoding='utf-8')` with no try/except
- CLAUDE.md with bytes like 0xff or 0xfe → `UnicodeDecodeError` → exit=1
- SessionStart hook crash: managed blocks NOT updated
- Root: `session-start-crew.py:41`

## pre-memory-dedup-gate.py: single-quoted trailer bypasses dedup check
- Pattern: `_TRAILER_PATTERN` only matches `--trailer "Memo=..."` (double quotes)
- Single-quoted or unquoted trailer: `--trailer 'Memo=...'` or `--trailer Memo=...` → gate skips entirely
- Exact duplicate memos can be committed silently without dedup warning
- Root: `pre-memory-dedup-gate.py:158-161` (_TRAILER_PATTERN)

## pre-merge-gate.py: # merge-reviewed string bypasses gate unconditionally
- Pattern: `if '# merge-reviewed' in command:` at line 94 — no verification that reviews ran
- Any command containing `# merge-reviewed` (as a comment, in a string, etc.) bypasses
- `git pull origin main # merge-reviewed` → approved without reviews
- `git merge evil-branch # merge-reviewed -- skip gate` → approved
- Root: `pre-merge-gate.py:94`

## Hard link defeats "anti-symlink" guards on both Windows and POSIX (git_helpers.open_no_follow_symlink)
- Pattern: os.path.islink() (Windows) and O_NOFOLLOW (POSIX) only detect symbolic links -- a hard link
  (os.link(target, victim_path)) is indistinguishable from an ordinary file to both mechanisms, since it
  is not a reparse point and shares the same inode/file-record as the target.
- Demonstrated live (real filesystem, no mocking) on Windows: os.link(sensitive, 'boot-log-latest.txt')
  then git_helpers.open_no_follow_symlink(path, 'w') succeeds with NO OSError, and the write lands on the
  hard-linked sensitive file's shared data -- confirmed content overwritten.
- Read-side (SEC-MED-NEW-02) equally bypassed: hard-linking glossary-cache.json to attacker-controlled
  JSON, open_no_follow_symlink(path, 'r') returns the attacker's content with no rejection.
- Reached through a REAL production entry point, not just the raw primitive: ensure_gitignore() in
  git_helpers.py:208 -- hard-linking .gitignore to an outside file and calling ensure_gitignore()
  appends the generated block onto the outside file's shared content.
- Threat-model caveat (do not overclaim): git checkout cannot materialize a hard link (only blob content or
  a symlink-target string), so this bypass is NOT reachable via "clone a malicious repo, do nothing else" --
  the specific attack SEC-CRIT-001 targets. It requires the attacker to already have local write access to
  the runtime dir before the guarded write runs (e.g. a separate/earlier local exploit, malicious
  pre-install hook, or another lower-trust local process) -- a different, adjacent threat model. Also true of
  the original pre-Windows-fix POSIX O_NOFOLLOW code -- not a regression introduced by this patch.
- Root: lib/git_helpers.py:167 (_open_no_follow_symlink_windows) and its twin
  lib/_symlink_safe_open.py:50 -- neither os.path.islink() nor the lstat/fstat (st_dev, st_ino)
  TOCTOU comparison can ever flag a hard link, because a hard link's identity IS the target's identity by
  design -- there is no way to distinguish a pre-existing hard link from a legitimately separate file using
  device+inode alone.

## UnicodeEncodeError (non-OSError) escapes open_no_follow_symlink and truncates pre-existing content first
- Pattern: write mode opens with O_TRUNC at os.open() time (truncation happens immediately, before any
  write() call). If the payload contains a lone UTF-16 surrogate code point (invalid for strict UTF-8
  encoding), f.write(payload) raises UnicodeEncodeError -- a ValueError subclass, NOT OSError.
- Confirmed live: pre-existing file content is destroyed (0 bytes on disk) by the time the exception
  propagates, since truncation already happened at open().
- Callers throughout the codebase wrap these calls in except OSError expecting ALL guard failures to
  surface that way (the docstring's own contract: "Raises OSError... Callers must let that propagate").
  UnicodeEncodeError violates that contract and would surface as an unhandled crash at any call site that
  only catches OSError.
- Caveat: no current caller in this codebase feeds attacker-controlled content likely to contain lone
  surrogates (most content is json.dumps(..., ensure_ascii=True) output or hardcoded strings) -- not
  demonstrated as reachable from an external input in THIS codebase today. Also pre-existing on POSIX and in
  the pre-fix code (same truncate-then-write structure) -- not introduced by the Windows crossplatform patch.

## run_git()'s "real round-trip" test is a false green on this machine (and per its own docstring, most CI) -- TestEncodingIndependentOfPythonUtf8Env does not cover run_git
- Formal Round-Trip Sabotage (unmassk-standards §34) executed against lib/git_helpers.py:279 run_git()'s
  encoding="utf-8" kwarg (added 2026-07-06, fix-windows-crossplatform):
  1. Independent channel confirms ground truth: real `git commit` with subject containing accents+emoji,
     read via subprocess WITHOUT text=/encoding= (raw bytes), decoded manually as UTF-8 -- git's own output
     is valid, well-formed UTF-8 on the wire (hex-verified). Bug is 100% in the Python decode step, not git.
  2. Scratch replica of run_git with encoding="utf-8" REMOVED, forced PYTHONUTF8=0 in a fresh child
     process (locale.getpreferredencoding(False) confirmed == 'cp1252' in that child) -> SILENT mojibake,
     returncode 0 (no exception): '🔧 chore...' became 'ðŸ”§ chore...corazÃ³n, seÃ±al...'. Not a crash --
     exactly the silent-corruption failure mode the sabotage protocol requires, not a dead connection.
  3. REAL production git_helpers.run_git under the IDENTICAL forced PYTHONUTF8=0 conditions (same
     preferredencoding='cp1252', same utf8_mode_flag=0 confirmed in the child) round-trips correctly.
  4. Checked tests/test_crossplatform_symlink_guard.py:422 TestEncodingIndependentOfPythonUtf8Env (the ONLY
     test in the suite that forces PYTHONUTF8=0) -- its @pytest.mark.parametrize ONLY covers
     ("git_helpers","open_no_follow_symlink") and ("_symlink_safe_open","open_no_follow_symlink_fallback").
     run_git is NOT parametrized into it.
  5. The dedicated real-git round-trip test for run_git,
     tests/test_crossplatform_symlink_guard_hardening.py:534
     TestRunGitEncodingUtf8.test_run_git_round_trips_utf8_accents_and_emoji_through_real_git, never forces
     PYTHONUTF8=0 -- runs only in the ambient interpreter env.
  6. Demonstrated concretely: built a scratch copy of the REAL production git_helpers.py with ONLY the
     encoding="utf-8" kwarg deleted from the run_git() call (diff-confirmed, one line), replayed that
     test's exact logic (same subject variable, real `git commit --allow-empty`, real `git log`) against
     the broken copy under this machine's AMBIENT env (PYTHONUTF8=1) -> test assertion PASSES (TEST_WOULD_PASS
     == True) even though the guarding kwarg is gone. Same broken copy under forced PYTHONUTF8=0 ->
     assertion correctly FAILS (mojibake). Same broken copy replayed against the SIBLING mock test
     test_run_git_passes_encoding_utf8_and_text_true_to_subprocess (asserts calls[0]['encoding']=='utf-8'
     directly on the mocked subprocess.run kwargs) -> that one correctly fails regardless of env, since it
     inspects the call arguments rather than relying on ambient decode behavior.
  - Net finding: the "real round-trip through real git" claim specifically (the one unmassk-standards §34
    requires as authoritative proof, since it is the only non-mocked check) is theater on any environment
    where PYTHONUTF8=1 is ambient (this dev box; per the sibling test's own docstring, "most CI" too) --
    it provides ZERO incremental regression protection beyond the mock kwarg-check test, because it never
    enters the one condition (cp1252 default) that the encoding="utf-8" kwarg exists to guard against.
    The regression itself IS still caught today, but only by the mock test, not by the round-trip test that
    is supposed to prove real behavior. If someone later relies on "the real round-trip test is green" as
    proof of correctness on Windows without PYTHONUTF8=1 forced, that proof is false.
  - Root: tests/test_crossplatform_symlink_guard_hardening.py:534 (missing env forcing);
    tests/test_crossplatform_symlink_guard.py:442-448 (parametrize list excludes run_git).

## Boot freshness (issue #49): FETCH_HEAD age computed with unclamped time.time() delta -- future mtime (clock skew) suppresses fetch indefinitely
- Pattern: `_fetch_head_age_seconds()` (lib/boot_git_checks.py:377) returns `time.time() - mtime`
  with NO clamp to >=0. `fetch_memory_ref()`'s rate-limit gate (`if age is not None and age <
  FETCH_RATE_LIMIT_SECONDS`) treats any negative age as "younger than 300s" -> skips the fetch.
- Demonstrated live: real bare-remote + clone triangle, `touch -t` FETCH_HEAD's mtime 30 days into
  the future (simulates a second machine's desynced clock, or this machine's own clock drifting/
  being corrected backward) -> boot shows "MEMORIA: LOCAL — fetch omitido (rate-limit, hace 0s)"
  (age clamped to 0 for DISPLAY by `_format_age_seconds`'s `max(0, int(seconds))`, hiding that the
  real number was negative) and FETCH_HEAD's own mtime is UNCHANGED after the boot run (independent
  verification via `stat -f %m`) -- confirmed no fetch was attempted. This suppresses the entire
  multi-machine freshness feature for as long as the clock-skew delta lasts (hours to weeks,
  whatever the skew is) with a message that reads as fresh/healthy ("hace 0s").
- Root: lib/boot_git_checks.py:377 (`_fetch_head_age_seconds`), :406 (rate-limit comparison),
  :434 (`_format_age_seconds` clamps for display, masking the negative value that drove the
  decision).

## Boot freshness (issue #49): MEMORIA: remoto stamp is decoupled from which ref resolve_boot_memory() actually reads -- broken/stale upstream tracking silently reverts to pre-#49 local-only behavior while claiming remote-verified freshness
- Two independent git ref-resolution paths exist and can disagree:
  1. `fetch_memory_ref()` (lib/boot_git_checks.py:386) fetches by BRANCH NAME
     (`git fetch origin <branch> --no-tags`, branch from `git branch --show-current`) -- does NOT
     depend on the branch's configured upstream (`branch.<name>.merge`/`.remote`).
  2. `get_ahead_behind()` (lib/boot_git_checks.py:143) resolves `upstream_ref` via
     `git rev-parse --abbrev-ref @{u}` -- DOES depend on that same tracking config.
  `resolve_boot_memory()` (lib/boot_memory.py) only ever reads from `upstream_ref` (path 2). If
  path 2's config is broken (e.g. `branch.main.merge` points at a deleted/renamed/never-existed
  ref -- realistic after a branch rename or manual git-config mistake) while path 1 still succeeds
  (the literal branch name "main" exists on origin), the fetch reports "fetched" (status shown as
  "MEMORIA: remoto (fetch hace 0s)") but the actual memory content displayed is 100% local HEAD --
  new content genuinely pushed by another machine to origin/main is invisible.
- Demonstrated live: real bare-remote + clone triangle. Corrupted `branch.main.merge` to
  `refs/heads/ghost-branch-never-existed` via `git config`. Pushed a real commit with a unique
  `Next:` marker from a second clone (machine B). Ran the real boot hook: `git fetch origin main`
  succeeded (independently confirmed via `git log origin/main` showing the new commit), MEMORIA
  stamp said "remoto"/fresh, but the marker was completely absent from the boot-log RESUME section
  -- confirmed via direct `grep` on the boot-log file, not via the hook's own claims.
  This is the exact incident issue #49 was filed to fix (a second machine's memory silently
  invisible), reproduced through a config path the fetch-hardening work did not close, with a
  freshness stamp that actively asserts the opposite of what happened.
- Root: lib/boot_git_checks.py:159 (`@{u}` resolution feeding `upstream_ref`) vs :420 (`fetch`
  by branch name, independent of `upstream_ref`); lib/boot_memory.py `resolve_boot_memory()`
  (only path that reads origin) is 100% gated on `upstream_ref` being non-None.

## Boot freshness round-2 repair (issue #49, commit 2fb3663): both originally-reported breaks confirmed FIXED live, but the "origin"-hardcoded gate silently disables the whole feature for renamed remotes
- fetch_memory_ref() (lib/boot_git_checks.py:493) gates on `git remote get-url origin` -- a
  LITERAL, hardcoded remote name, unrelated to what the branch's `@{u}` tracking config actually
  resolves to (which correctly uses the real remote name dynamically at :529 for the fetch itself).
  A repo where "origin" was renamed (e.g. fork workflow: origin=canonical upstream, personal remote
  named something else and set as the tracking remote) has a 100% coherent, working upstream that
  get_ahead_behind() resolves and reads fine -- but fetch_memory_ref() returns "no_remote" before
  ever checking `@{u}`, so NO fetch is ever attempted and the MEMORY stamp permanently reads
  "unverified", silently reverting the entire issue #49 feature to pre-fix behavior. Not a lie (it
  correctly avoids claiming "remote"), so lower severity than the original 2 findings, but the
  freshness feature itself is dead for this (common) remote-naming pattern.
- Demonstrated live: real bare+clone, `git remote rename origin upstream`, upstream/main tracking
  fully coherent (get_ahead_behind() correctly resolves "upstream/main" and shows "[0/0 vs
  upstream]") -- fetch_memory_ref() still returns {"status": "no_remote"} and never creates
  FETCH_HEAD (independent-channel confirmed: file absent).
- Root: lib/boot_git_checks.py:493 (hardcoded "origin" liveness gate), pre-existing since Task 2
  (98862f1), NOT introduced by the round-2 repair -- but never closed by it either.

## Boot freshness round-2: MEMORY stamp docstring claims full English banner unification -- REMOTE_PROVENANCE_LABEL is still Spanish, verified live
- render_memoria_stamp()'s docstring (lib/boot_git_checks.py:577) explicitly claims: "the whole
  boot banner (STATUS/BRANCH/RESUME/REMEMBER/DECISIONS/PULL DIRECTIVE) is English -- this stamp
  used to be the one Spanish outlier." This is FALSE and directly falsifiable: `REMOTE_PROVENANCE_LABEL
  = " [origen: remoto]"` (lib/boot_memory.py:425) is still Spanish, verbatim, and gets appended to
  every remote-labeled Decision/Memo/Remember/Next/Blocker line.
- Demonstrated live: real bare+2-clone true divergence, BOTH sides commit a `Crown=Decision` for
  the SAME scope with different text -> real boot hook's DECISIONS section shows
  `👑 (crowntest) REMOTE crowned choice for crowntest [origen: remoto]` -- Spanish label, in a
  banner whose own code comment claims is now fully English.
- Low severity (T2, cosmetic mixed-language inconsistency, not a functional/security bug) but a
  concretely disprovable claim, not merely "unproven" -- Deception Phase 5 finding.
- Root: lib/boot_memory.py:425 (REMOTE_PROVENANCE_LABEL never touched by the language-unification pass).

## _crown_replace multi-match dedup "fix" is unreachable dead code relative to its own stated justification
- The docstring/commit for the round-2 _crown_replace() change (lib/boot_memory.py:60) justifies
  the new while-loop dedup logic by pointing at `_merge_diverged_memory()`'s concatenated
  local+remote-labeled lists as the scenario that can "legitimately share a scope" and needs
  dedup -- but `_merge_diverged_memory()` (lib/boot_memory.py:455) NEVER calls `_crown_replace()`
  on its result; it just concatenates lists directly. `_crown_replace()`'s only 4 call sites (all
  inside extract_memory()/extract_glossary()) operate on a single side's own per-call walk, where
  decision_scopes/memo_scopes membership-gating already guarantees at most one entry per scope
  BEFORE `_crown_replace` ever runs -- exactly what the docstring itself admits ("this was always
  equivalent to there is only one match"). The new multi-match branch is therefore never exercised
  by any real production call path today.
- Confirmed empirically: the actual scenario the docstring describes (both sides crowning the same
  scope, real divergence) was reproduced live and correctly shows BOTH crowned entries side by
  side, un-deduped -- which is the CORRECT, DESIGNED behavior per `_merge_diverged_memory()`'s own
  "never auto-merge, show both sides" contract, not a bug the new dedup logic needed to fix.
- Tier: T3 (dead-code branch; the function still behaves correctly if it were ever called with a
  genuinely duplicated list, and its unit tests -- TestCrownReplaceMultiMatch -- call it directly
  with hand-built lists, never through the real merge pipeline, so no test masks a bug here either).

## Boot freshness round-2: zero regression-test coverage for either of the 2 fixes this round claims to have made
- Grepped the full test suite (tests/test_boot_freshness.py + tests/test_boot_freshness_hardening.py,
  85 tests total, all passing): no test exercises a negative/future FETCH_HEAD mtime (clock-skew
  fix), and no test exercises a mismatched-upstream/ghost-branch fetch-by-branch-name-vs-read-by-
  `@{u}` scenario (decoupled-stamp fix). TestRenderMemoriaStamp only parametrizes render_memoria_stamp()
  with static fetch_state dicts -- it never exercises fetch_memory_ref()'s own age/rate-limit
  computation at all.
- Both fixes are REAL and hold under live adversarial reproduction (see resilience.md) -- this is
  not a currently-live bug -- but nothing in CI would catch either fix regressing in the future.
  T2: real fix today, missing regression protection for exactly the 2 findings this repair round
  was supposed to close.

## Boot freshness round-3/FINAL (issue #49, fix d409805 + regression tests 45ecfd6) -- repo-identity confusion via a fully coherent but UNRELATED tracked ref (formal Round-Trip Sabotage, not a regression of this round)
- The whole issue #49 stack (fetch_memory_ref/get_ahead_behind/resolve_boot_memory) validates that
  `@{u}` resolves to a coherent, fetchable branch-shaped ref -- it never validates that the resolved
  remote is actually a fork/continuation of THIS project's own history. `@{u}` has no concept of
  "same project"; a branch.<name>.remote/.merge pair pointing at a completely different, disjoint
  codebase is indistinguishable from a legitimate one purely by ref-resolution machinery.
- Demonstrated live: real bare "remote.git" (this project's own history) + a second, completely
  UNRELATED bare repo seeded with its own unrelated commit (`decision(payments): use Stripe not
  PayPal`, `Crown=Decision`). Pointed a real clone's `branch.main.remote`/`.merge` at the unrelated
  repo (a real `remote add` + real `fetch` + real `--set-upstream-to`, not a mock). Zero shared
  history confirmed via an INDEPENDENT channel (`merge-base` between HEAD and the tracked ref exits
  1 -- no common ancestor -- plus a direct read of the unrelated bare repo's own log, never through
  the path under test).
- fetch_memory_ref() reports `{"status": "fetched", "age_seconds": 0.0}` (a REAL, successful fetch --
  not a lie about that specific fact), render_memoria_stamp() renders the confident, healthy
  "MEMORY: remote (fetched 0s ago)" line, and resolve_boot_memory() serves the unrelated repo's
  crowned Decision labeled "[source: remote]" -- confirmed end-to-end through the REAL boot hook
  (not just the library functions in isolation): the boot log's DECISIONS section shows
  "(payments) Use Stripe, final [source: remote]" sitting right next to this project's own real
  crowned decision, with zero distinguishing signal that anything is wrong. `BRANCH: main [7/1 vs
  upstream]` and a real `PULL DIRECTIVE` line were also computed and rendered against the unrelated
  repo's ahead/behind counts.
- Severity bounded to T2, not T1: (a) pre-existing since the very first issue #49 Task 4 design, not
  introduced or reopened by this repair round; (b) requires LOCAL git-config-level tracking
  misconfiguration to trigger -- not remotely exploitable by a content-pushing attacker with only
  push access to the real, correctly-tracked remote; (c) the worst-case escalation (blindly acting on
  the false PULL DIRECTIVE) is independently blocked by git's own default refusal to combine
  histories with no common ancestor (confirmed live: a real pull attempt against this exact state
  fails with "refusing to merge unrelated histories" before anything destructive happens) -- so the
  actual live impact is confidently-mislabeled, misleading DISPLAYED content, not data loss or a
  destructive merge.
- Root: lib/boot_git_checks.py get_ahead_behind()/fetch_memory_ref() (`@{u}` resolution, no
  same-project identity check) and lib/boot_memory.py resolve_boot_memory() (unconditionally trusts
  whatever ref get_ahead_behind() resolved).
