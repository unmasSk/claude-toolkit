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

## F6 hard-link reject guard (issue #53) — held under real adversarial pressure (2026-07-09)

`open_no_follow_symlink(..., reject_hardlinks=True)` and its fallback twin, both on the real
Windows branch (`_open_no_follow_symlink_windows`). 8 real PoCs, 0 breaks:

- Monkeypatch-injected TOCTOU race (attacker's `os.link()` fired exactly inside the
  `os.path.exists()` → `os.open()` window on a brand-new path) still gets caught: the
  `os.fstat(fd).st_nlink > 1` check is unconditional post-open, independent of the
  already-documented-and-accepted F5 new-file-race residual. `os.link()` to an existing file
  always yields `st_nlink >= 2`, so the nlink check catches it regardless of race timing.
- Real 500-iteration multi-threaded race (background thread hammering `os.link()` against the
  main thread's open loop, no mocking/injection) — 0 bypasses, victim content untouched.
- §34 end-to-end sabotage against all 3 real production call sites (`write_boot_log()`,
  `_write_glossary_cache()`, `_read_glossary_cache()`), independent-channel verification via
  `certutil -hashfile` (never python's own `open()`) — deferred-truncate correctly preserves the
  shared inode's content on rejection every time; no fallback-to-plain-open() anywhere in the
  `except OSError` handling at any of the 3 sites.
- 2000-iteration hammering of the rejection path — handle count verified via independent
  PowerShell `Get-Process ... HandleCount` — delta 0.
- `mode="a"` + `reject_hardlinks=True` (edge case NOT covered by the existing contract test file,
  which only parametrizes r/w) — the POSIX branch's `if mode=="a" / elif reject_hardlinks` order
  does not skip the nlink check for append mode; correctly rejected on both twins.
- `st_nlink=3` (two extra links, not just one) — `>1` threshold generalizes, twin parity holds.

Non-bug observation (not a break, logged for context): `user-prompt-memory-check.py`'s
booted_flag call site never reaches the guarded open at all when a hard link is pre-planted
before first boot (`os.path.isfile()` short-circuits `if not session_booted:` first) — safer
than reaching the guard, not weaker (confirmed via certutil: no open() call touches the
attacker's link that session).

## Issue #57 root-fix round (structural parsing, decision 0682e75) -- subject-x1f class re-attacked, holds everywhere claimed
- All 7 named sites re-attacked live with real hostile `git commit -m $'...x1f...'` payloads
  in disposable scratch repos, real production functions called directly (never mocked):
  lib/recall.py._scan_commits(), bin/git-memory-gc.py (scan_commits + find_stale_items),
  bin/git-memory-doctor.py (check_hook_execution + check_gc_status), lib/bootstrap_commits.py
  .scan_recent_commits() (dual git-log-call sha correlation), hooks/precompact-snapshot.py
  .extract_memory_from_log(), lib/boot_memory.py.extract_memory(). A stray x1f anywhere in
  the SUBJECT (a middle-positioned but now-last-in-header field, thanks to the %n
  subject/body real-newline split) no longer desyncs date/scope/author/trailers at any of
  the 7 sites -- confirmed via independent-channel `git log --pretty=format:...`/`git
  cat-file` reads matching the parsed output exactly, including a genuine 90-day-old
  Blocker correctly surfaced as stale by both gc.py and doctor.py despite carrying an x1f
  in its own commit subject.
- bootstrap_commits.py's two-git-log-call design (structured fields in call 1, `%h + author`
  in call 2, correlated by sha) also holds against an x1f embedded in %an (author name) in
  call 2 -- confirmed the sha/date/subject/scope from call 1 never desyncs from the author
  looked up via call 2's dict, live, across 4 different real commits in the same repo.
- Unicode "line-separator-equivalent" bytes in the SUBJECT -- U+2028 (LINE SEPARATOR),
  U+0085 (NEL), U+2029 (PARAGRAPH SEPARATOR), and bare CR (\r) -- were tested live (real
  commit objects confirmed via `git cat-file -p` to contain the raw bytes in the subject,
  independently confirmed via `git log --pretty=format:%s`/`%b` that git's OWN %s/%b never
  treat these as newline-equivalent). Python's `str.partition("\n")` only matches the
  literal 0x0A byte, so none of these desync the header/body boundary at any of the 4
  sites tested. Holds.
- Short-hash (%h) ambiguity/collision: forced `core.abbrev=4` and generated 1200 commits in
  a disposable repo -- git's own abbreviation algorithm self-heals by extending %h length
  dynamically whenever a fixed-length prefix would collide (confirmed via independent
  `git log --pretty=format:%h | awk '{print length}'` showing BOTH 4-char and 5-char hashes
  in the same output), so a genuine %h collision between two different commits within one
  git-log invocation is not achievable through the codebase's actual (un-flagged) %h usage,
  regardless of core.abbrev config. bootstrap_commits.py's sha-correlation between its two
  calls is not exploitable via this vector.
- scan_trailers_memory()'s per-line \x1c/\x1d/\x1e truncation: a real legit "Memo: keep this
  alive please" commit, plus a SEPARATE attacker commit gluing "Decision: real decision D" +
  x1e + "Resolved-Memo: keep this alive please" + x1e + "Blocker: FORGED BLOCKER" onto ONE
  physical line (no real newline) -- confirmed live neither the forged tombstone nor the
  forged Blocker materialize; the real Memo survives un-tombstoned, exactly as designed.
- gc.py's find_stale_items(): the previously-flagged evidence-field ANSI-leak bug (evidence
  built from sha+subject, bypassing the c["text"] sanitize choke point) is confirmed FIXED --
  a real hostile subject containing a raw ESC (x1b) byte in a keyword-overlap-matched
  "resolution" commit no longer reaches real captured stdout (byte absent, replaced by a
  space), confirmed via print_candidates()'s actual output.
- Empty-subject/empty-body/subject-only-looks-like-a-trailer edge cases: a real
  `--allow-empty-message` commit (empty subject, empty body) parses cleanly with no crash
  across gc.py and bootstrap_commits.py. A commit whose SUBJECT ALONE reads exactly like a
  trailer ("Decision: this looks like a trailer...") but has zero body produces zero memory
  entries in recall.py -- correctly matched by --grep (grep scans the whole message) but
  correctly rejected by the body-only trailer scan (no phantom entry).
- Stress: a 50,000-char subject saturated with 25,000x alternating x1f/x1e parsed in ~16ms
  with the real trailing Decision surviving; a real 600-commit repo (--all scan) completed
  in ~31ms with all 600 real Memo entries found; a single commit with a 20,000-line
  trailer-shaped body parsed in ~52ms with the real trailing Decision surviving. No hang,
  no crash, no timeout at any scale tested.
- Race: 6 real threads (3x gc.scan_commits, 3x doctor's two check functions) hammering the
  same repo concurrently, 20 iterations each -- zero errors, `git fsck --full` clean after.
  Two REAL OS processes launched simultaneously running `git-memory-gc.py --auto` against
  the same repo -- git's own index.lock naturally serialized commit creation (the losing
  process's `git commit` failed cleanly, printed the existing "Failed to create GC commit"
  error path, no crash) -- exactly 1 Stale-Blocker tombstone in the final history, no
  duplicate/corrupted state.

## lib/boot_git_checks.py get_timeline()/get_last_context_time() -- re-confirmed [GUARD], not a gap
- These 2 functions were NEVER migrated to the new -z/%n structural pattern (git blame
  confirms their last touch was issue #55's %aI->%at date-format migration, unrelated to
  #57). They still use the OLD `%h\x1fsubject\x1f%at` shape with subject in the MIDDLE and
  `\n`-based (not `-z`) record splitting.
- Re-attacked live anyway (x1f embedded in a real commit subject, including a real
  `context(...)` commit made moments earlier): confirmed `get_timeline()` and
  `get_last_context_time()` both degrade to the literal string "unknown" for the
  corrupted-date commit, exactly matching the already-existing, already-passing tests
  `test_x1f_in_subject_degrades_get_timeline_to_unknown` /
  `..._get_last_context_time_to_unknown` in tests/test_control_byte_injection.py (Sites
  7-8, documented [GUARD] not [ROJO]) -- the team's own written rationale (`str.isdigit()`
  gate + maxsplit=2 arithmetic can never produce a forged/plausible wrong timestamp, only a
  safe "unknown") holds under live re-verification with a different injected payload text
  than the existing test uses. This is a REAL residual UX degradation (a real recent commit
  can show "unknown" instead of "just now" in the live "RESUME:" boot banner via
  lib/boot_render.py's render_resume_section(), confirmed live) but it is NOT a new,
  undiscovered, or misrepresented gap -- it is exactly what the team already found, tested,
  and consciously accepted as out of scope for the #57 structural fix (the invariant
  protected is "never forge a date," not "always show the correct one").

## Issue #57 round 2d re-validation (2026-07-10) — what held
- Exact-literal snapshot header/footer spoof in precompact-snapshot.py: a Blocker/Decision
  trailer containing the EXACT string `=== END SNAPSHOT ===` or `=== GIT MEMORY SNAPSHOT
  (pre-compact) ===` is correctly neutralized to `[snapshot-frame-text-neutralized]` by
  `_neutralize_snapshot_delimiters()` — confirmed via the real `extract_memory_from_log()` +
  `format_snapshot()` against a real hostile repo; `stdout.count(delimiter) == 1` holds for
  both header and footer, real frame only.
- scan_trailers_memory()'s truncate-on-\x1c/\x1d/\x1e still works correctly: a trailer value
  with one of those three bytes is truncated at the byte (not glued, not forged) — no
  regression from this round's other changes.
- \x1c/\x1d/\x1e fence-splice via scan_trailers_memory's truncation path specifically (NOT via
  sanitize_trailer_value alone, which still leaves a decoy — see attack-patterns.md): the
  truncation happens BEFORE sanitize_trailer_value ever sees the fence tag, so nothing after
  the byte (including "SYSTEM:" text) survives at all for these three specific bytes when
  routed through scan_trailers_memory().
- git_helpers.py commits_since_last_consolidation(): real `\n`-only split confirmed still in
  effect; a \x1e byte in an unrelated commit's subject does not bleed across git-log lines.
- ReDoS / pathological input: `_strip_generic_tags()` on a 10k-char malformed-tag string and
  `sanitize_trailer_value()` on 20k repeated fence-fragments both complete in <5ms. No
  catastrophic backtracking in either regex.

## Issue #59 (A2 token-fence + transport bytes-decode + ReDoS cap + LOW-17) -- what held, 2026-07-10
- CR/\r round-trip transport (SEC-CRIT-16 fix): a REAL commit with a raw \r (not \r\n) embedded
  mid-body between a real Decision: trailer and a Memo:-shaped forged fragment, independent-
  channel confirmed via git cat-file -p (raw \r present in the object) -- both
  lib/git_helpers.py:461-477 run_git()'s new stdout_bytes.decode("utf-8") (no text=True/
  universal-newlines) AND bin/git-memory-log.py:84-90's equivalent manual decode preserve the
  literal \r with zero translation to \n; scan_trailers_memory() sees ONE physical line
  ("\n"-split only), so the "Memo:" fragment glued via \r never materializes as a separate,
  forged trailer -- it stays as harmless trailing text inside the real Decision's own value.
  git-memory-log.py's own subprocess: a \r-embedded subject prints as exactly ONE commit line
  (not two), with the \r correctly space-substituted by sanitize_trailer_value().
- Invalid-UTF-8 decode-failure path: code-inspection confirmed except UnicodeDecodeError as e:
  (lib/git_helpers.py:520) is unchanged and still catches bytes.decode("utf-8")'s strict-mode
  failure identically to the old text=True, encoding="utf-8" path -- isolated .decode('utf-8')
  on a genuinely invalid byte sequence confirmed to still raise as expected. (Live full-commit
  reproduction of a truly-invalid-UTF-8 commit MESSAGE was not achievable on this Windows/msys-
  git box specifically: git commit -F <file> silently re-encodes lone high bytes like \x80\x81
  into valid UTF-8 \xc2\x80\xc2\x81 before storing the object -- a git-for-windows message-
  encoding behavior unrelated to this codebase, not a gap in the #59 fix itself.)
- ReDoS/DoS: lib/bootstrap_commits.py's _GENERIC_TAG_MAX_INPUT_LEN = 4096 cap genuinely bounds
  _strip_generic_tags() regardless of input size -- a 4,000,000-char pathological "<a"*N string
  completes in 8ms (truncated to 4096 chars before the regex ever runs); the 4096-char worst
  case itself (AT the cap) also completes in ~9ms. lib/parsing.py's new _UNCLOSED_FENCE_TAIL_RE
  (LOW-17, [^>]*$) on a 5,000,000-char string: 5ms. Canonical sanitize_trailer_value() on a
  4.5M-char string of repeated fence-fragments: 0.21s. scan_trailers_memory() on a single
  6M-char pathological line: 13ms; on 48M chars across 2000 pathological lines: 0.17s. No
  catastrophic/quadratic backtracking found in any regex touched by this round's fix.
- LOW-17 (_UNCLOSED_FENCE_TAIL_RE, lib/parsing.py:107): re-attacked directly through the real
  scan_trailers_memory() (not just the isolated regex) for its EXACT designed scenario --
  </memory-data\x1c> / \x1d / \x1e all correctly truncate-then-strip to a clean "real decision
  text" with zero unclosed-tag remnant surviving. A double-fragment line
  (<memory-data>middle</memory-data\x1e>) correctly leaves the well-formed FIRST tag
  (<memory-data>) for the LATER sanitize_trailer_value() stage to close (by design, two-stage
  split) -- confirmed that stage does close it. An invisible ZWSP placed immediately BEFORE the
  truncation byte (</memory-data + U+200B + \x1e>) is still correctly swept by [^>]*$ (unlike
  the CLOSED-tag ZWSP exploit in attack-patterns.md, which is a structurally different,
  unrelated code path -- LOW-17 only ever fires on genuinely UNCLOSED remnants).
- Concurrency: 10 real concurrent hooks/user-prompt-memory-check.py subprocess invocations
  against unchanged repo state -- all rc=0, all correctly inject the real recall content, all
  show stdout.count("</memory-data>") == 1, all 10 fence-nonce: values are distinct
  (secrets.token_hex(8) is safe under real OS-level process concurrency).

## Issue #60 v2 own-fetch-success-stamp hardening (2026-07-10, real repos + real hook subprocess)
- Vector A re-run (failed fetch to dead/unreachable remote URL) → stamp never written, next boot within window still retries honestly (`fetched`/`LOCAL — unverified`, never `synced`). Held.
- Vector B/D re-run (real successful fetch of an unrelated remote name, or of the SAME remote externally before the hook's own stamp exists) → own stamp untouched (write only happens inside `_run_hardened_fetch` after ITS OWN fetch), boot still performs its own real fetch. Held (matches shipped `test_vector_b_*`/`test_vector_d_*`).
- Stamp content attacks: garbage JSON, empty file, valid JSON with wrong remote/branch strings, 20MB malformed JSON — all fall through to honest fetch, no crash, fast (`json.loads` on 20MB still sub-second).
- Stamp as symlink to an external file (even with byte-identical correct-looking content) → rejected by `open_no_follow_symlink` on read (falls to honest fetch); on write, `verify_path_within_project` raises `UnsafePathError` on the resolved (through-symlink) destination → write silently no-ops, external target file confirmed untouched (no write-through-symlink).
- Stamp as a hard link to an otherwise-correct stamp file → rejected via `reject_hardlinks=True` on read (st_nlink>1 check on the open fd). Falls to honest fetch.
- `.claude/.unmassk` directory itself replaced with a symlink pointing outside the project root, with a real, reachable, tracked upstream (fetch WOULD succeed) → `verify_path_within_project` refuses both the stamp write and the boot-log write (`UnsafePathError`, caught, fail-open); nothing landed in the external target directory; boot still completes with the correct `fetched` status, exit 0, one stderr breadcrumb.
- Future-mtime clock skew on the stamp (`touch -t 2030...`) → negative age computed, correctly NOT treated as fresh (falls through to a real fetch), matching the pre-existing FETCH_HEAD-skew contract.
- 8 fully concurrent real boot subprocesses racing the SAME empty-stamp repo → all 8 completed, final stamp file is valid single JSON (no interleaving/truncation), zero leftover `mkstemp` temp files. atomic `mkstemp`+`os.replace` held under real concurrency.
- Reordered `fetch_memory_ref()` (identity resolved before rate-limit) re-tested against detached HEAD, a branch with no upstream at all, a remote entirely removed (`git remote remove origin`), and a remote whose URL is unreachable — all correctly report `LOCAL — unverified`, exit 0, no crash, no stamp written, no false "remote" claim.
- Stamp deleted between two boots (mid-window) → next boot degrades cleanly to a real fetch (`fetched`), not a crash or a stale cached claim.
- Happy path (real fetch OK, second boot <300s) → `MEMORY: remote (synced Ns ago)`, confirmed via two independent channels (stdout banner + persisted `boot-log-latest.txt`). Not broken by the v2 change.
