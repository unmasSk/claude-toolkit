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
