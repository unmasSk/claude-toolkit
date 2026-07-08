# Resilience — Attacks That Held

## recall.py / git-memory-recall.py (2026-06-05)

- Empty string query → returns '(no matches)' cleanly. No crash.
- 10,000-char query → handled in 130ms. No crash. No timeout.
- All-stopword query → returns '(no matches)'. No crash.
- Regex metacharacters as query (`.*`, `[`, `(`) → tokenizer strips them. No re.error.
- Backslash-only query → empty token set, clean '(no matches)'.
- Emoji-only query → empty token set, clean '(no matches)'.
- Unicode non-Latin queries (Arabic, Chinese, Cyrillic) → empty token set, clean result.
- `--flags` passed as query → argparse handles correctly; unrecognized flags = error exit 2.
- limit=0 and limit=-1 via CLI → correctly rejected with error message.
- limit=-5 via API → clamped to 1 by `if limit < 1: limit = 1`. Returns 1 result.
- limit=999999999 → returns all results (Python slice handles it cleanly).
- scope='nonexistent/scope' → returns '(no matches)' cleanly.
- scope='.*' → treated as literal string, no regex execution, no crash.
- scope='' (empty) → treated as falsy, no filter applied (same as scope=None).
- scope case-insensitive matching → works correctly (both sides lowercased).
- Git injection via query string → query never passed to git subprocess. Safe.
- Tombstoned entries do NOT leak into IDF df weights (filtered before _build_df).
- Decisions are never tombstoned — by design and verified in practice.
- Tie-breaking sort → Python's stable sort preserves insertion order deterministically.
- Race conditions → recall() is fully stateless. No shared mutable state.
- Regex ReDoS in _tokenize → character class with no backtracking. Safe.

## release.py / bin/bump-version.py (2026-06-09)

- Path traversal `../evil` → rejected by PLUGIN_NAME_RE before any filesystem access.
- Uppercase plugin name → rejected by PLUGIN_NAME_RE.
- Empty plugin name → rejected by PLUGIN_NAME_RE.
- `UNMASSK_REPO_ROOT` env set to external repo → release.py overrides it with the correct root; victim repo not mutated.
- 1.9.0 → 1.10.0 semver comparison → _semver_tuple uses int(); (1,9,0) < (1,10,0) correctly.
- 2.0.0 > 1.99.99 comparison → (2,0,0) > (1,99,99) correctly.
- 1.4.0-rc1 vs 1.4.0 (same core) → rejected as "not greater" (correct behavior).
- Working tree check without --allow-dirty → correctly aborts.
- No upstream configured → correctly aborts.
- CHANGELOG absent → correctly aborts with FileNotFoundError message.
- CHANGELOG with whitespace-only [Unreleased] body → correctly aborts.
- Push failure → exits code 2 (VERIFY_FAIL), not 0; local commit preserved; ADVERTENCIA printed.
- Second release same version → rejected as "not greater".
- git fetch fails, push also fails → exits code 2 (not silent); files are mutated locally but that is documented behavior.
- Detached HEAD → correctly aborts (no upstream).
- CRLF CHANGELOG → handled correctly; output is clean; no double-blank-line corruption.
- 10,000-line CHANGELOG → processed in <1s, no timeout.
- Huge version 99999.99999.99999 → accepted as valid (correct: valid semver).
- Concurrent releases (same version, two threads) → one wins (rc=0), other fails at git add (index lock); final state consistent.

## user-prompt-memory-check.py recall injection (2026-06-12)

- Binary stdin (NUL bytes, 0xff, 0x80) → _read_prompt_text() returns None, hook exits 0 cleanly
- latin-1 / Windows-1252 encoded stdin (invalid UTF-8) → swallowed by except Exception
- Lone surrogate \ud800 in JSON → json.loads fails, swallowed, hook exits 0
- BOM prefix on valid JSON → json.loads fails, swallowed, hook exits 0
- JSON with trailing garbage → json.loads fails, swallowed, hook exits 0
- prompt=number/list/object/null/bool → isinstance guard rejects, hook exits 0
- Deeply nested JSON (depth 500, 990) → json.loads handles or fails silently, hook exits 0
- 10MB stdin → _read_prompt_text() truncated at 2000 chars by recall.py, hook exits 0 in <210ms
- Stopwords-only query → _tokenize returns empty set → recall_relevant returns None, no injection
- Punctuation-only query → same as above
- Digits-only query → tokenizer requires at least one letter, no injection
- All-equal-score corpus (6 entries) → top_fraction gate admits all, capped at max_results=3 correctly
- Determinism: tied scores produce identical output across 10 in-process calls AND 5 subprocess calls (stable sort by insertion index)
- 300 commits hook latency: avg 140ms (well under 300ms target)
- Manifest > plugin version: needs_upgrade returns False (no spurious upgrade trigger)
- All manifest edge cases (null, missing, corrupt JSON, non-semver): fail-safe returns False, hook exits 0
- Concurrent first-boot (5 processes, no .session-booted): all exit 0, all emit [memory-check], flag write is idempotent
- Concurrent git commits during hook reads: all hook invocations exit 0, no corruption

## hooks/bin — adversarial inputs (2026-06-12)

- stop-dod-gate: test_command as list/null/int/empty → all fail-open (exit 0, allow close)
- stop-dod-gate: test_command with shell metacharacters (`; exit 1`) → shell=False prevents execution
- stop-dod-gate: test_command with unmatched quotes → ValueError caught in _run_test_command → fail-open
- stop-dod-gate: test_command with embedded NUL → fail-open
- pre-validate-commit-trailers: malformed JSON / empty stdin → exit 0 (no exception)
- pre-task-recall: prompt=int/list/null, subagent_type=int → exceptions caught, decision=allow, exit 0
- validate-memory-path: ../traversal through agent-memory → normpath resolves it out, no trigger
- validate-memory-path: file_path in another root's agent-memory → correctly blocked
- session-start-boot: empty repo (no commits) → exit 0 cleanly
- precompact-snapshot: detached HEAD → exit 0, no crash
- stop-dod-check / stop-close-session / precompact-snapshot: run outside git repo → exit 0
- git-memory-commit: Unicode RTL/ZWJ in scope/message → commits accepted, parsed correctly by scanner
- git-memory-gc: --days=-1 / --days=0 → runs without crash, no mass-tombstone (interactive asks)
- session-start-crew: running in empty repo → exit 0 cleanly

## git_helpers.open_no_follow_symlink Windows guard (2026-07-06)

- Real Windows box, real git-checkout-style symlink threat (islink() mocked True): both twins raise OSError
  BEFORE os.open() is ever called -- 0 open_calls observed, file content untouched. Matches the stated
  SEC-CRIT-001/SEC-MED-NEW-02 threat model exactly.
- TOCTOU lstat/fstat identity mismatch (mocked st_ino divergence): OSError raised, fd opened then closed
  before returning -- no leaked fd, no fd handed to caller.
- Twin parity: git_helpers._open_no_follow_symlink_windows and _symlink_safe_open's copy are byte-identical
  in logic (only docstring wording differs) -- no divergence found despite deliberate attempt to diff them.
- POSIX branch: git diff confirms the O_NOFOLLOW/O_CREAT/O_TRUNC/O_APPEND lines are 100% untouched by this
  patch (no regression possible from this change on POSIX -- diff-verified, not just asserted).
- Directory planted at the target path (not a symlink, not a hardlink): Windows os.open() on a directory in
  read mode raises PermissionError (OSError subclass) -- fails closed, no crash, no silent success.
- Nonexistent path in read mode: FileNotFoundError (OSError subclass) -- expected, no AttributeError.
- run_git(): mocked subprocess.run raising UnicodeDecodeError -> caught by except (..., ValueError) ->
  returns (1, "") as documented, no crash escapes.
- ensure_gitignore() idempotency: called twice on a fresh .gitignore -- entry appears exactly once, no
  duplication, no corruption.
- Concurrent writers (8 threads, same brand-new path, no prior identity to protect): all 8 succeed, final
  file content is one writer's full payload with zero interleaving/corruption -- Windows-level file writes
  for these buffer sizes are atomic enough that no torn writes were observed in 1 run.
- Encoding round-trip (accents + commit emojis via git log vocabulary): payload written once, reread
  compared against the SAME variable (not a hand-retyped literal) -- genuine round-trip, not fabricated. On
  disk the bytes are CRLF-translated (not literally "byte for byte" as the test docstring claims), but the
  str-level round-trip the code actually needs to guarantee holds correctly.
- 5.8M-character payload (accents + emoji repeated) round-trips correctly in 0.06s -- no stress ceiling hit.
- PYTHONUTF8=0 subprocess round-trip: both twins still round-trip correctly -- guarantee genuinely comes
  from the explicit encoding="utf-8" parameter, not from the ambient env var.

## git_helpers.run_git() encoding="utf-8" kwarg -- formal Round-Trip Sabotage (2026-07-06)

- Real commit with accents+emoji subject, ground truth confirmed via an INDEPENDENT channel (raw bytes
  captured with subprocess.run(capture_output=True) WITHOUT text=/encoding=, manually .decode('utf-8')) --
  git's own stdout bytes are valid, well-formed UTF-8; the failure mode lives entirely in Python's decode
  step, never in git itself.
- Sabotaged the REAL dependency the way a real bug corrupts it (silent decode corruption, not a killed
  connection): scratch replica of run_git with encoding="utf-8" removed, run in a fresh child process with
  PYTHONUTF8=0 forced (locale.getpreferredencoding(False) confirmed 'cp1252' in that child) -> produced
  silent mojibake ('ðŸ"§'-style garbage), returncode 0, NO exception raised. This is the dangerous case: no
  crash, no warning, just wrong bytes accepted as success.
- REAL production git_helpers.run_git (lib/git_helpers.py:279, the actual file, not a copy) under the
  IDENTICAL forced PYTHONUTF8=0 conditions (verified same cp1252/utf8_mode_flag=0 in that child) round-trips
  the commit subject correctly byte-for-byte. The guarantee genuinely comes from the explicit
  encoding="utf-8" kwarg at git_helpers.py:298, not from the ambient PYTHONUTF8 env var this dev machine
  happens to have set.
- Confirmed via an INDEPENDENT channel throughout: results read back from a side-channel JSON file written
  with its own explicit encoding="utf-8" + ensure_ascii=True, never through the same in-process stdout the
  code under test itself produces.
- SEAM VERDICT: run_git()'s encoding="utf-8" kwarg itself AGUANTA the sabotage -- it is real, load-bearing,
  and does exactly what it claims under the exact adversarial condition (PYTHONUTF8=0 / no ambient UTF-8
  mode) it was added to defend against.
- Caveat (see attack-patterns.md): the TEST that is supposed to prove this ("real round-trip through real
  git") never forces PYTHONUTF8=0 itself, so it is a false green on any PYTHONUTF8=1 environment -- the
  kwarg holds, but the round-trip test that claims to prove it does not actually exercise the risk
  condition. Regression protection for a literal kwarg deletion still exists today via the sibling mock
  test (test_run_git_passes_encoding_utf8_and_text_true_to_subprocess), which is env-independent by
  construction.

## Boot freshness (issue #49) -- hardened fetch + multi-machine memory read (2026-07-06)

- Real hung TCP remote (nc accepting, never responding) over HTTP AND an unroutable ssh:// host
  (192.0.2.1, TEST-NET-1) -- both bounded at ~3.3s wall clock, boot exits 0, stderr shows
  "[git_helpers] git 'fetch' timed out after 3s". Fail-open confirmed under a REAL hang, not a
  mocked/fake-git wrapper.
- 501-commit-behind real remote (bare + clone triangle, ground truth confirmed via `git ls-remote`)
  -- boot completes in 0.34s, correctly shows "[0/501 vs upstream]", PULL DIRECTIVE, and the
  remote-only Next item labeled "[origen: remoto]" in the RESUME section.
- Genuine shallow clone (`git clone --depth 1 --no-local file://...`, `git rev-parse
  --is-shallow-repository` confirmed true) -- both at-parity and 1-behind-after-clone states
  produce correct ahead/behind numbers and correct RESUME content; no crash, no shallow-graft
  weirdness surfaced in `rev-list --left-right --count`.
- Detached HEAD -- correctly shows "BRANCH: (detached HEAD)", no fetch attempted (branch name
  empty), MEMORIA correctly says "sin verificar (nunca se ha sincronizado)" -- accurate, not
  falsely claiming fresh.
- True divergence (3 ahead / 5 behind, CONTRADICTORY Decision: trailers on each side, built via a
  real bare-remote + two-clone triangle) -- both sides shown side by side in DECISIONS and RESUME,
  remote side correctly labeled "[origen: remoto]", local side unlabeled, NEVER merged/deduped/
  dropped -- matches the plan's explicit "never auto-merge" requirement exactly, verified end to
  end with real git history, not a mock.
- Corrupt SHA planted directly in `.git/refs/remotes/origin/main` (independent-channel confirmed
  via `git cat-file -t <sha>` failing) -- `get_ahead_behind()`'s `rev-list` call fails silently,
  falls back to (0,0,upstream_ref); `resolve_boot_memory()` then reads local HEAD (safe default,
  no crash) -- though the DISPLAYED "[0/0 vs upstream]" is misleading in this specific case (see
  attack-patterns.md note on the ghost-branch finding for the more severe sibling of this gap).
- 6 concurrent real boots on the same repo (parallel `git fetch` against the same `.git`) -- no
  crash, no lock-error propagation to the user, `git fsck` clean afterward, no repo corruption.
- Real 3MB single-trailer commit (no embedded newline, one giant `Next:` value) fetched from a real
  remote -- boot completes in 0.4s, full boot-log correctly grows to ~3MB (by design, unshortened),
  stdout banner stays short as documented -- no truncation bug, no timeout.
- Old-format (pre-#49) glossary-cache.json missing the `origin_sha` key, WITH a real upstream
  configured -- correctly treated as stale and regenerated (cache.get("origin_sha") is None !=
  the real resolved origin sha) rather than served stale. Backward-compat path is safe-by-default
  (invalidates rather than risks serving pre-#49-shaped stale data).
- Write-path warn-only (`bin/git-memory-commit.py` while 5 commits behind, real repo) -- prints the
  yellow warning to stderr and still creates the commit (verified via `git log -1`) -- never blocks.
- Newline injection into a spoofed "[origen: remoto]"/"MEMORIA:"/"PULL DIRECTIVE:" provenance label
  via a trailer value is blocked (`sanitize_trailer_value` strips \r\n/U+2028/U+2029/vtab/formfeed
  before the label is ever appended) -- an attacker with push access to origin can make text
  WITHIN a `Next:`/`Decision:` line visually blend with the genuine provenance label (same string,
  glued with no delimiter), but cannot forge a new top-level boot line (no `STATUS:`/`MEMORIA:`
  banner-header spoof) because no attacker-controlled value can ever contain a real newline by the
  time it reaches rendering. Low-severity cosmetic confusion only (T3), not a bypass.
- Planting a hanging `post-merge`/`reference-transaction` git hook does not intercept `git fetch`
  at all (neither hook fires on a plain client-side fetch in stock git) -- confirmed N/A, not a
  real vector against this feature.

## Boot freshness round-2 repair (issue #49, commit 2fb3663) -- both originally-reported breaks confirmed FIXED under live re-attack (2026-07-06)
- Clock-skew (Moriarty #1): `fetch_memory_ref()`'s `0 <= age < FETCH_RATE_LIMIT_SECONDS` gate
  (lib/boot_git_checks.py:490) correctly forces a real fetch across every boundary tested live:
  future by 1s, future by 30 days (original repro, real bare+2-clone, marker commit fetched and
  independently confirmed via `git log origin/main`), future by 10 years, FETCH_HEAD absent, and
  mtime exactly at "now" (correctly still rate-limits, as intended). FETCH_HEAD's own mtime
  (independent `stat -f %m` channel) changes exactly when a real fetch happens, never when it
  should be suppressed.
- Decoupled stamp (Moriarty #2): `fetch_memory_ref()` now resolves `@{u}` itself and fetches
  `remote_name`/`remote_branch` from THAT (not the bare branch name) -- reproduced the exact
  original incident (real bare+2-clone, `branch.main.merge` corrupted to a nonexistent ref, a real
  marker commit pushed from "machine B") and confirmed the stamp now correctly says
  "MEMORY: LOCAL -- unverified (never synced with origin)" instead of falsely claiming "remote".
  No fetch was attempted (independent channel: FETCH_HEAD absent) since there was no coherent
  upstream to align with -- correct, honest fail path.
- Real hung remote + Popen/killpg process-tree kill (SEC-MED-001): built a real Python socket
  server that accepts a TCP connection and never responds (not a mock/fake-git), pointed origin at
  it -- observed via `ps` DURING the hang a real 3-level-deep process tree (`git fetch` ->
  `git remote-http` -> `git-remote-http`), all sharing the new session's pgid. After
  fetch_memory_ref()'s FETCH_TIMEOUT_SECONDS elapsed, `ps` (independent channel, not the
  function's own claim) showed ZERO leftover processes from that tree -- the whole group was
  genuinely killed, not just the direct child.
- Leading-dash / git-option-injection defense (SEC-CRIT-001): hand-crafted `.git/config` with
  `branch.main.remote = -evilremote` (git DOES allow creating a remote named with a leading dash
  via `git remote add -- -evilremote <url>`) and a matching `refs/remotes/-evilremote/main` --
  `_looks_like_git_option()` correctly caught it and returned `{"status": "failed"}` WITHOUT ever
  invoking `git fetch -evilremote ...` (independent channel: FETCH_HEAD never created).
- Opportunistic tracking-ref update for the NEW fetch call shape: confirmed via independent
  `git rev-parse refs/remotes/origin/main` (before/after) cross-checked against the bare repo's
  own ground-truth ref that `git fetch origin --no-tags -- main` (the exact positional-arg shape
  `fetch_memory_ref()` now uses) DOES update the local tracking ref opportunistically, even without
  an explicit refspec colon-mapping -- so a successful fetch genuinely makes `get_ahead_behind()`/
  `resolve_boot_memory()`'s subsequent read see the new content, not stale data.
- Real true divergence with BOTH sides crowning the SAME scope with different text (real bare+2-
  clone, `Crown=Decision` trailer on each side) -- both entries shown side by side in DECISIONS,
  correctly labeled (remote side carries the provenance suffix), never silently merged or dropped
  -- matches the explicit "never auto-merge" design contract.
- Concurrency: 6 real concurrent boot invocations on a fresh clone (no prior FETCH_HEAD) -- no
  crash, `git fsck` clean, all 6 show the correct "MEMORY: remote" stamp. A genuine real `git
  fetch` (separate process) racing against `fetch_memory_ref()` at the same instant -- no crash,
  `git fsck` clean, correctly resolves to `rate_limited` (the user's parallel fetch won the race).
  50 rapid-fire in-process `fetch_memory_ref()` calls complete in 0.06s with the expected
  1-fetched-then-49-rate-limited pattern, no FD/resource leak observed.
- 10,000-char branch name: rejected by git itself at the ref-lock/filesystem layer (`fatal: cannot
  lock ref`) before ever reaching this module's code -- N/A, not a vector against this feature.
- Manual/out-of-band `git fetch` run by the user immediately before boot, and CLAUDE.md +
  manifest.json deleted mid-session (gate flap) -- both handled correctly (`rate_limited` and
  `skipped_gate` respectively), no crash.

## Boot freshness round-3/FINAL repair (issue #49, fix d409805 + regression tests 45ecfd6) -- all 4 prior findings confirmed closed, both original breaks re-confirmed fixed, new injection variants held (2026-07-06)
- English label/stamp: real divergence and real strictly-behind reproductions (bare+multi-clone) both
  show " [source: remote]" and "MEMORY: remote (fetched Ns ago)" -- zero Spanish literals found via
  grep across the feature's code path.
- Renamed remote now fetches: simple `remote rename origin upstream` (tracking preserved), a
  two-remote setup where "origin" is a broken/unreachable decoy and the real tracked remote has a
  different name, and a remote literally named `2nd.origin_weird-name` (dots/underscore/hyphen) --
  all three fetch successfully and correctly surface the new remote content, confirmed via
  independent `refs/remotes/<name>/main` reads and direct bare-repo ground truth, never through the
  hook's own claims.
- Leading-dash injection still blocked at the NEW `remote get-url --` call site: a hand-crafted
  `-evilremote` remote+matching ref (real `.git/config` edit, git itself allows creating this via
  `remote add --`) is still caught by `_looks_like_git_option` before reaching the new call --
  confirmed via independent channel (no FETCH_HEAD created). Also confirmed for the remote_BRANCH
  half specifically (hand-crafted `refs/remotes/origin/--evil-branch` + matching config so `@{u}`
  resolves it) -- also blocked, no FETCH_HEAD created.
- Shell-metacharacter remote names (`evil;touch_CANARY`, `` evil`touch_CANARY2` ``,
  `evil$(touch_CANARY3)`) all created successfully by real git (no rejection at creation time), then
  tracked and fetched successfully via the new argv-list `remote get-url --`/`fetch` calls with ZERO
  canary file created anywhere -- confirms no shell=True anywhere in this path, genuinely argv-safe.
- Both ORIGINAL round-1 breaks re-verified fixed under this round's exact code: future-dated
  FETCH_HEAD mtime (clock skew) still forces a real fetch (FETCH_HEAD mtime independently confirmed
  to move to "now", not stay skewed); a hand-corrupted `branch.main.merge` ghost ref still correctly
  returns `no_remote`/"MEMORY: LOCAL -- unverified" while an independent `fetch`+`log origin/main`
  confirms the real remote DOES have new content the stamp correctly refuses to claim.
- POSIX killpg process-tree kill re-confirmed under the refactored Windows/POSIX `popen_kwargs` split:
  a real hung TCP listener (not a mock) + real `git fetch` against it -- after the 3s timeout, `ps`
  independently confirms zero leftover `git`/`git-remote-http` processes.
- `false`-by-PATH askpass: confirmed the old `/bin/false` literally does not exist on this real macOS
  box (`ls /bin/false` -> No such file or directory) so the portability claim is true, but also
  confirmed via a REAL `git ls-remote` against an auth-required https URL that GIT_TERMINAL_PROMPT=0
  alone already fully prevented any hang/interactive-prompt leak even with the OLD broken
  `/bin/false` -- the fix is a genuine portability correction with no prior live hang to its name, not
  overclaimed as fixing a security gap it doesn't.
- Concurrency on the renamed-remote code path specifically: 6 real concurrent `fetch_memory_ref()`
  calls (fresh FETCH_HEAD) all correctly report "fetched", `fsck` clean after; a REAL concurrent
  out-of-band `git fetch upstream` racing the function at the same instant resolves cleanly to
  `rate_limited` with no crash and `fsck` clean; 50 rapid-fire in-process calls reproduce the exact
  expected 1-fetched/49-rate-limited pattern in 0.05s with the renamed-remote resolution path.
- Stress: a renamed-remote clone 600 commits behind resolves ahead/behind and reads/caps `pending` at
  MAX_PENDING correctly in ~0.1s -- no slowdown from the new dynamic remote-name resolution.
- _crown_replace's multi-match branch confirmed to introduce NO observable divergence-handling bug:
  a real true-divergence (both sides crowning the SAME scope, real bare+2-clone) still shows BOTH
  crowned entries side by side, correctly labeled, never deduped/dropped/merged.

## fetch_memory_ref()'s narrowed except + broad except fallback pattern (polish round, 2026-07-07)
- Pattern checked: git_helpers.py's `_win32_kill_tree` and `commits_since_last_consolidation`
  had bare `except Exception` narrowed to specific tuples this round. `fetch_memory_ref()`
  (lib/boot_git_checks.py:699-716) looks narrowed the same way but actually KEPT a second,
  broader `except Exception as e:` fallback right after the narrow one — both branches
  return the identical fail-open value ({"status": "failed", "age_seconds": None}), only the
  logged message differs. Confirmed by direct code reading: this specific narrowing is
  cosmetic (better diagnostics), NOT a real reduction of the fail-open safety net. Do not
  re-flag this site as a narrowing risk without re-checking for the same dual-except pattern.
- `commits_since_last_consolidation()`'s new `except (ValueError, TypeError)` (git_helpers.py:478)
  genuinely has no broad fallback, but empirically tried an invalid-UTF-8 commit message
  through the real function (real repo, real git commit, real call) — result: fails open to 0
  via run_git's own internal UnicodeDecodeError handling (returns (1,"") upstream), never
  reaches an exception in this function's own try block. Held under this specific attack.
- git-memory-commit.py's realpath `except OSError` narrowing (was bare Exception): reasoned
  that `os.path.realpath(None)`/non-str args raise TypeError (not OSError, would escape) but
  NOT reachable via the real call site — `toplevel` always comes from run_git()'s guaranteed
  str return, `.strip()` always succeeds, so realpath always receives a str. Confirmed via
  isolated os.path.realpath() testing (None/int -> TypeError uncaught) but no live path feeds
  a non-str here. Logged as latent-not-reachable, not a live break.

## issue #55 date-parsing migration (%aI→%at) — held under real adversarial dates
- Negative epoch: git's own CLI date validator rejects it outright (`fatal: invalid date format`)
  for every format tried (`@-N`, ISO with `-`, raw negative). Only reachable via
  `hash-object --literally` (bypasses fsck's `badDate` check) — a deliberate raw-object-surgery
  scenario, not something a normal commit can produce. When forced, real git's own `%at` renders
  as an EMPTY string for the malformed date (not a crash, not garbage digits) — `parse_date("")`
  correctly returns `None` via the ISO fallback's `ValueError`.
- Year-10000+ overflow (`OverflowError` inside `datetime.fromtimestamp`) is caught cleanly by
  `parse_date()`'s broad except clause — no traceback, no crash, in both `git-memory-gc.py` and
  `git-memory-doctor.py` end-to-end real runs (see attack-patterns.md for the visibility-loss
  finding this causes downstream, which IS real).
- `\x1f`/`\x1e` field-separator injection into subject/body can never produce a wrong-but-valid
  DATE (mathematically proven + empirically confirmed) — always safely collapses to `None`.
- Huge digit strings (2,000,000 digits) for the `int(date_str)` path: Python 3.11+'s built-in
  `sys.int_max_str_digits` guard (default 4300) rejects it via `ValueError` in ~1ms — no CVE-2020-
  10735-style quadratic DoS reachable. Same for a 5,000,000-char garbage string through the ISO
  `fromisoformat` fallback (fast rejection, no backtracking).
- Concurrency: two real parallel `git memory gc --auto` processes on the same repo, and 5 parallel
  `doctor.py --json` reads racing a `gc.py --auto` write — no corruption, `git fsck --full` clean,
  single consistent history in both cases. No NEW race introduced by the %aI→%at date migration
  itself (git's own commit-ref-move race between two writers is pre-existing/orthogonal, unrelated
  to date parsing).
- Tombstone (`Stale-Blocker:`/`Resolved-*`) suppression is date-independent by design (`normalize()`
  text matching only, no `commit["date"]` check in that path) — confirmed by code read, holds
  regardless of a target blocker's own date parseability.
- `parse_date()`'s ISO fallback ALWAYS returns a tz-AWARE datetime (never naive) — confirmed no
  input produces a naive return value, which is what makes the fix's `datetime.now(timezone.utc)`
  comparison genuinely crash-proof (see attack-patterns.md for the confirmed OLD-code crash this
  replaces).
