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
