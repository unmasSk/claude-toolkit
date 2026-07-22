---
name: diagnostic-patterns
description: Recurring root cause patterns found during investigations in unmassk-toolkit and related projects
type: reference
---

## Pattern: "Failed to traverse parents of commit" on CI = MISSING reachable object in the fixture object-store, NOT a stale/corrupt commit-graph

**Project:** unmassk-toolkit (#61 reopened, Ubuntu-CI-only) · **Seen:** 2026-07-22 · confirmed by exact reproduction + real CI log (run 29702760223)

Symptom: `git log --all` readers (`lib/recall.py::_scan_commits`, `lib/git_helpers.py::commits_since_last_consolidation`) exit rc=128 with the exact pair:
`error: Could not read <parentSHA>` + `fatal: Failed to traverse parents of commit <childSHA>`. Deterministic — fails identically all 3 retries, so the #61 retry wrapper can NEVER recover it (retry re-runs the same doomed read against the same damaged on-disk repo). Readers fail-safe to []/0 → "CONSOLIDATE:" absent / entry-510 not found.

**Discriminator that REJECTS the commit-graph hypothesis:** a stale commit-graph degrades silently; a corrupt one prints `commit-graph ...` lines (e.g. "commit-graph fanout values out of order") and STILL returns rc=0. CI stderr had ZERO commit-graph lines. The `Could not read` + `Failed to traverse parents` pair is the revision-walker / object-DB signature = a **reachable parent commit object is genuinely absent**. Reproduced exactly by deleting one middle commit's loose object then running either reader (scratchpad repoD). `git fsck --connectivity-only` on that state prints `broken link ... missing commit <sha>`, non-zero exit — ideal fixture-integrity probe.

**Why only Ubuntu-CI:** append-only fixture loses a reachable object only via auto-gc/repack/prune. `git commit` (and boot's `git fetch`) auto-invoke `git gc --auto`; Linux detaches via fork (`gc.autoDetach`) and can race the object-DB under ext4 + heavy parallel CI I/O. Windows can't fork → gc foreground/serialized. macOS-local Apple-git did NOT repack mid-loop even at `gc.auto=50` (512 loose / 0 packs) → local never corrupts. Could NOT spontaneously reproduce the object loss on APFS; missing-object→failure link is confirmed, gc-as-cause is high-confidence inference.

**Fix lever (test-only):** neutralize implicit maintenance in EVERY fixture repo via conftest `run_cmd` merged env (same precedent as `_DEFAULT_GIT_IDENTITY_ENV`) using `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` → `gc.auto=0`, `gc.autoDetach=false`, `maintenance.auto=false`. `gc.auto=0` alone kills the trigger for both `git commit` and `git fetch`. Add fail-loud post-build probe (`git fsck --connectivity-only` assert rc==0).

## Pattern: Suite-red after a refactor is often stale-test + config-drift, NOT a product regression — separate "mechanism removed" from "assertion drifted" from "coupled config not updated"

**Project:** unmassk-toolkit (user-prompt hook, #69 push→pull + #76 description rewrite) · **Seen:** 2026-07-14 · confirmed from source + test run + git log

Three co-occurring red clusters from `user-prompt-memory-check.py`, three DIFFERENT verdicts — do not lump them:

1. **Fully-obsolete tests (mechanism deleted).** #69 (`3f65c72`) turned the per-message recall channel from PUSH (`[memoria relevante...]` + `<memory-data>` fence-nonce injected into hook stdout) into PULL (a static `_BANNER`; recall.py still exists but is on-demand only). 6 end-to-end tests in `test_control_byte_injection.py` (Fence/Nonce classes ~L2496/3210/3802) all die at their SETUP/GUARD line (`assert "[memoria relevante" in stdout` / `assert "zorblax decision text" in out`) — they never reach their real security invariant because the push surface is gone. Doubly dead: CLAUDE.md explicitly RETIRES the control-byte/injection threat model ("dead weight… retire whatever exists"). Verdict OBSOLETE → Dante deletes. These are survivors of the "16 tests obsoletos" #69 cleanup that was incomplete.

2. **Valid test, one drifted assertion.** `test_encoding_contract.py::TestUserPromptMemoryCheckCp1252` has TWO asserts: (a) `rc==0` under cp1252 = the REAL regression (hook must not `UnicodeEncodeError` on its `→` char) — still PASSES, and the hook DELIBERATELY keeps a non-ASCII char in `_BANNER` to keep guarding it (hook comment says so). (b) `"[memory-check]" in out` = a stale MARKER — #69 folded that literal reminder into `_BANNER` and dropped the token. Only (b) fails. Verdict NOT obsolete → Dante updates the one marker assertion (assert on a surviving marker, e.g. the recall pointer), keeps the rc==0 guard. NOT a product bug.

3. **Coupled config not updated by the refactor (real coherence defect).** `test_user_prompt_skill_router.py::TestSkillTriggerPhrasesMatchLiveDescriptions` is a live DRIFT-GUARD: it reads `SKILL_TRIGGER_PHRASES` (lib/skill_router.py) dynamically and asserts each phrase is a substring of its skill's CURRENT folded frontmatter description. #76 (`84b9a26`) rewrote grill + project-lifecycle descriptions but did NOT update the coupled trigger dict → 2 phrases orphaned (`'the request is ambiguous'`→ desc now says `'help me define this'`; `'pick up the project'`→ desc now says `'pick up where we left off'`). Verdict test is CORRECT and caught an INCOMPLETE #76 → fix is to reconcile the dict (product/config, orchestrator lane completing #76), NOT touch the test. (The test's own docstring "EXPECTED STATE TODAY" paragraph is itself stale — names 4 old pairs already reconciled — but that's cosmetic; the parametrization is dynamic.)

**Lesson:** when a refactor (push→pull, rename, description rewrite) leaves the suite red, triage each red into: mechanism-removed (delete test), assertion-marker-drifted (update one assert, keep the real contract), or coupled-config-not-updated (fix product/config, the test is doing its job). A drift-guard test failing is usually the guard WORKING. Read git log on the PRODUCT file vs the TEST/CONFIG file: if the product refactor commit post-dates the test/config, the test/config is the lagging side.

## Pattern: Boot MEMORY stamp shows "rate-limit/skip" because multiple SessionStart boots overwrite the single per-repo boot-log (last-writer-wins), not because fetch is broken

**Project:** unmassk-toolkit (git-memory boot) · **Seen:** 2026-07-10 · confirmed from session transcripts

Symptom: user reports "the boot fetch never works — every project shows `MEMORY: LOCAL — fetch skipped (rate-limit, Ns ago)`". The fetch actually WORKS.

Root cause is an interaction of three facts, none of them a fetch bug:
1. `hooks/hooks.json` registers `SessionStart` with NO `matcher`, so the boot hook (`session-start-boot.py`) fires on EVERY session-start source: `startup`, `resume`, `clear`, `compact`. Each invocation runs the full boot.
2. Every boot unconditionally overwrites the single per-repo file `.claude/.unmassk/boot-log-latest.txt` (`write_boot_log`) and prints its own banner. There is NO dedupe — the boot hook deliberately does NOT create/read `.session-booted` (that flag is UserPromptSubmit's).
3. The fetch is rate-limited to `FETCH_RATE_LIMIT_SECONDS = 300` keyed on `.git/FETCH_HEAD` mtime (`_fetch_gate_and_rate_limit` / `_fetch_head_age_seconds`, `lib/boot_git_checks.py`). The FIRST boot in a 5-min window fetches successfully (writes FETCH_HEAD → banner `MEMORY: remote (fetched 0s ago)`); every SUBSEQUENT boot within 5 min sees fresh FETCH_HEAD → `rate_limited` → banner `LOCAL — fetch skipped`.

Because users open/resume/clear the same repo several times within a few minutes, the LAST boot to write boot-log-latest.txt is almost always a rate-limited one, and that stale last-writer banner is what the user sees. Proof in transcripts: a single session jsonl (`7a658028`, claude-toolkit) contains TWO real boots with DIFFERENT stamps (`2min ago` @13:32Z, `24s ago` @13:54Z) → SessionStart re-fires within one session. Across three antonio-alsara opens in 4 min: `failed(15h)`@15:27 → `rate-limit 1min`@15:28 → `rate-limit 24s`@15:31, FETCH_HEAD advancing the whole time = fetches ARE happening.

Verified NON-causes (rejected hypotheses): (a) a single boot CANNOT fetch-then-relabel-skip — `render_memoria_stamp` uses the same `fetch_state` dict returned once by `fetch_memory_ref`, never re-reads age (main() lines 304→369); rate-limit is an early return BEFORE the fetch. (b) The 15:37/15:40 "sessions that didn't regenerate boot-log" were NOT new boots — jsonl mtime is last-message time, not a boot event; no SessionStart fired then, so nothing was expected to regenerate.

Secondary: FETCH_HEAD mtime is shared, non-authoritative state (documented residual Argus SEC-LOW-001) — a user/IDE `git pull` also resets the rate-limit clock, so boots can be gated by non-boot git activity (seen in omawaMapas where boots never show "fetched" yet FETCH_HEAD advances).

Fix direction (WHAT, not implemented): make the banner/boot-log reflect the freshest KNOWN state instead of last-writer-wins. Options for Ultron/Yoda to choose: (a) don't overwrite a "fetched" boot-log with a later "rate-limited" one within the window (compare-and-keep-fresher); (b) render the stamp from FETCH_HEAD age alone (a fresh FETCH_HEAD IS fresh memory — "rate-limit skip" is not a degraded state, it means "already fresh"); (c) reword `rate_limited` so it reads as "memory is fresh (synced Ns ago)" rather than "skipped", which users read as failure. This is a UX/labeling + last-writer bug, not a fetch bug.

## Pattern: Barrido `encoding='utf-8'` OVER-CORRECTED — Pinning PARENT Read to utf-8 While CHILD Writes Locale Encoding Breaks Only on Non-utf8 CI Runner (run 28933635507)

**Project:** unmassk-toolkit (git-memory) · **Seen:** 2026-07-08 · confirmed 1:1 locally on real Windows

The #51 barrido added `encoding='utf-8'` to 140 subprocess/read/write sites. In `tests/test_release.py` that was WRONG for the sites that READ a child process which itself emits in the OS **locale** encoding. Two culprit sites: `_run_release` (reads `bin/release.py` stdout/stderr, line ~192) and `_git` (reads git output, line ~82). `bin/release.py` prints Spanish-accented text (`vía`, `falló`, `versión`, `Múltiples`, `malformado`, `sección`) and has NO utf-8 stream guard, so on a cp1252 runner it emits á=0xe1/ó=0xf3/í=0xed/ú=0xfa. The test parent, now pinned to `encoding='utf-8'` STRICT, decodes those cp1252 bytes → `UnicodeDecodeError` inside `subprocess.py:_readerthread` (visible symptom #1) → the reader thread dies → `stdout` comes back **None** → `combined = stdout + stderr` → `TypeError: unsupported operand +: NoneType and str` (symptom #2). BOTH symptoms are ONE event. The 4 failing tests are exactly the ones doing `combined = stdout + stderr` on accented release output (`test_dry_run_prints_plan`, `test_push_failure...`, `test_multiple_unreleased_aborts`, `test_unreleased_not_first_version_aborts`); siblings that only use stdout in f-strings tolerate None and pass.

**Why green on dev's Windows but red on CI:** dev box has `PYTHONUTF8=1` (utf8_mode=1) → the child `release.py` inherits utf-8 mode → emits utf-8 → matches the parent's forced utf-8 read → pass. CI runner has NO PYTHONUTF8 → child emits cp1252 → mismatch → crash. Same `PYTHONUTF8=1 masks cp1252` trap. Pre-barrido (`text=True`, no explicit encoding) the parent decoded with the SAME locale as the child → always matched (mojibake but no crash; asserts are ASCII substrings) → passed everywhere.

**Reproduced 1:1:** child `sys.stdout.reconfigure(encoding='cp1252'); print('...falló...versión...')` read by parent `subprocess.run(..., text=True, encoding='utf-8')` → `UnicodeDecodeError byte 0xf3 pos 26 in _readerthread` + `stdout=None` + `TypeError NoneType + str`. Exact CI bytes.

**Owner = Dante (TEST).** Fix: the two parent reads that consume localizable child output must decode tolerantly — keep `encoding='utf-8'` but add `errors='replace'` (or read bytes) at `_run_release` and `_git`. This never crashes, stdout never None, ASCII asserts still pass, and it covers BOTH release.py AND git output. NOT a product bug: `release.py` emits only cp1252-SAFE accents at runtime (its only non-cp1252 char, `─` U+2500, is comment-only, never printed) so a real cp1252 user sees correct output, no crash. NOTE: contrary to an earlier memory, `force_utf8_streams()` is ABSENT from ALL bin/hooks entry points at HEAD 72805bc (grep-verified) — there is no repo-wide utf-8-guard convention to be "consistent" with, so do NOT assign product work; `errors='replace'` in `run_git`-style child reads cannot be replaced by a product-side guard anyway (git output is out of product's control).

**Lesson:** a blanket `encoding='utf-8'` barrido is not safe on subprocess READS whose child emits in the OS locale encoding (git, or any product script lacking a utf-8 stream guard). For parent reads of possibly-non-utf8 child output, pair `encoding='utf-8'` with `errors='replace'`. WRITES and reads of files YOU control can stay strict utf-8.

## Pattern: cp1252 Write-Path Recurs in NEW Test-Harness Spots After conftest.run_cmd Was Fixed (CI run 28922061708)

**Project:** unmassk-toolkit (git-memory) · **Seen:** 2026-07-08 · confirmed from real CI log

After #52/#54 fixed conftest.run_cmd (added `encoding="utf-8"`) and added `force_utf8_streams()` to all 25 entry points, the SAME cp1252 write-path defect resurfaced in TWO test-harness spots the fix never touched. Both windows-latest / Python 3.10.11 only.

1. **`pathlib.Path.write_text()` without `encoding=`** — `tests/test_security_regression.py:1622` and `:2017` (`victim.write_text(valid_content)`). `valid_content` is a REAL installed CLAUDE.md (UTF-8 skill text containing `→` U+2192 at offset 1144). `Path.write_text(data)` with no encoding uses the locale codepage → cp1252/strict on the runner → `UnicodeEncodeError: '→' position 1144` inside `encodings/cp1252.py`. Traceback root frame is `pathlib.py:1155 write_text -> f.write(data)`, NOT product code, NOT pytest rendering, NOT the subprocess child. Sibling TestBugP tests pass because they write the plain-ASCII `_FAKE_INSTALLED_MARKER_CLAUDE_MD` constant. TEST bug (Dante), not product — product write paths are guarded. Fix: `victim.write_text(content, encoding="utf-8")` (and every peer `.write_text` of UTF-8 content in that file).

2. **Inline monkeypatched `run_git` in `-c` probe helpers** — `tests/test_crown_retraction.py:227` (and the twin `_extract_memory`/`_extract_glossary` in `test_boot_output.py:203,250`). These `_sp.run(['git']+args, capture_output=True, text=True, cwd=..., env=...)` with NO `encoding="utf-8"` — the exact bug conftest.run_cmd already had, re-introduced by hand in the probe code string. On cp1252 the emoji subjects (🧭 = `F0 9F A7 AD`; byte `0x9F` is undefined in cp1252) fail to decode in the subprocess `_readerthread` (visible as `PytestUnhandledThreadExceptionWarning ... _readerthread` at `subprocess.py:1515`); the thread dies, stdout returns EMPTY, `extract_memory()` hits `if code!=0 or not output: return {}`, decisions come back `[]`, and crown-dedup asserts fail `0 == 1` (`Expected one deduped entry for (auth): []`). Note the monkeypatched run_git also lacks the real `git_helpers.run_git`'s UnicodeDecodeError guard. TEST bug (Dante). Fix: add `encoding="utf-8"` to those inline `_sp.run(...)` calls.

**Lesson:** when fixing a cross-cutting encoding defect, grep the WHOLE test tree for `subprocess.run(`/`_sp.run(` without `encoding=` AND for `.write_text(`/`.read_text(`/`open(` without `encoding=` — the central-helper fix does not reach per-test-file helpers or `-c` code strings.

## Pattern: get_last_context_time()/get_timeline() Use Fragile %aI+fromisoformat vs extract_memory()'s Robust %at (boot time_ago absent on runner git ~2.43)

**Project:** unmassk-toolkit · **Seen:** 2026-07-08 · confirmed mechanism, exact git trigger not locally reproducible

`test_boot_output.py::test_last_commit_has_time_ago` (`assert re.search(r"\d+[mhdw] ago|just now", content)` → `assert None`) and `test_regression_memory_correctness.py::test_consistent_detection_both_paths_agree` (`assert has_time` → None) fail on BOTH ubuntu AND windows (so NOT encoding, NOT OS). CI trace shows the `Last:` line HAS the subject (so `extract_memory()` found the context commit) but NO time — i.e. `get_last_context_time()` returned empty AND the TIMELINE section (also `time_ago`-based) had no time strings either. The two code paths diverge in `lib/boot_git_checks.py`: `get_last_context_time()`/`get_timeline()` use `git log ... --pretty=%h\x1f%s\x1f%aI` (no `-z`, no explicit `HEAD`, no `--`) + `datetime.fromisoformat()`, while `extract_memory()` (lib/boot_memory.py:154) uses the robust `git log HEAD -z ... %at --` (unix epoch, parsed via time_ago's `.isdigit()` branch). Verified NOT Python 3.10 (fromisoformat parses strict `%aI` `+00:00` fine on 3.10.18) and NOT reproducible with local git 2.49 (boot renders `just now` under py3.10+git2.49). Sole remaining variable is the runner's older git (~2.43) on the `%aI` reading path — same conclusion as the prior round. FIX (product robustness, Ultron): unify `get_last_context_time()`/`get_timeline()` onto `%at` (+ explicit `HEAD` + `--`) exactly like `extract_memory()`, removing the `%aI`/`fromisoformat` fragility and making the two "paths agree" by construction. Observability gap that hides the real cause: boot subprocess reads discard stderr — surface it before the next round.

## Pattern: CI Runner Has No Git Identity → Test Helpers Silently Swallow `git commit` Failure

**Project:** unmassk-toolkit (git-memory)
**First seen:** 2026-07-07

Mass boot/memory test failures on GitHub Actions (ubuntu + windows, Python 3.10) with symptoms of "memory content never reaches the boot log": REMEMBER/DECISIONS/TIMELINE sections missing, glossary-cache.json never created (FileNotFoundError), 2200-char giant-commit payload absent, branch-scoped items missing, sanitization tests failing — all *content-absent*, no crashes.

**Root cause:** CI runners have NO git identity (no global/system `user.name`/`user.email`) and git's auto-detect yields `runner@...(none)`, which git rejects → `git commit` exits 128 with "Author identity unknown / unable to auto-detect email address". Test helpers call commits via a `git_cmd`/`run_cmd` wrapper that RETURNS `(rc, out, err)` but callers ignore rc. So the fatal commit is swallowed, the repo ends up with an unborn HEAD (zero commits), and boot (read-only) produces empty output → every content assertion fails with a confusing "missing" symptom instead of a clear git error.

**Why it doesn't reproduce on macOS:** macOS git auto-detects a hostname-based identity (`user@host.local`) and commits succeed (rc=0). Nullifying `GIT_CONFIG_GLOBAL`/`SYSTEM` alone does NOT reproduce — macOS still auto-detects.

**Faithful local reproduction of the CI condition:**
```
printf '[user]\n\tuseConfigOnly = true\n' > /tmp/fakegitconfig
GIT_CONFIG_GLOBAL=/tmp/fakegitconfig GIT_CONFIG_SYSTEM=/dev/null python3 -m pytest tests/test_boot_output.py -q
```
`useConfigOnly=true` with no identity forces git to refuse auto-detection → `git commit` fatal, exactly like the runner. Confirming the fix direction: add `GIT_AUTHOR_NAME/EMAIL` + `GIT_COMMITTER_NAME/EMAIL` env vars → suite goes green under the same fatal config.

**Test-only vs production:** This is a TEST defect, not a production bug. Production commit path (`bin/git-memory-commit.py::_do_commit`) also sets no identity, BUT it checks `returncode != 0` and exits 1 with a loud error — a real user without git identity fails visibly, not silently. Fixing the runner ENV (adding `git config --global user.email` in the workflow) would mask the real defect (helpers ignoring git rc) and is the wrong layer.

**Correct fix layer:** centralize a deterministic git identity for tests — set `GIT_AUTHOR_*`/`GIT_COMMITTER_*` in the shared `run_cmd` merged env in `conftest.py` (applies to every git subprocess regardless of cwd, makes tests hermetic vs the runner's global config). `_make_repo_no_install` already did per-repo `git config user.email/name` (its tests passed); the many helpers that forgot (`make_repo_with_giant_commit`, `make_repo_with_memory`, conftest `tmp_repo`/`installed_repo`, and ~5 other test files) are the blast radius — hence centralize rather than patch each helper.

## Pattern: cp1252 Default stdout on Windows CI Runner Crashes Every UTF-8-Emitting Entry Point (masked on dev's own Windows box)

**Project:** unmassk-toolkit (git-memory)
**First seen:** 2026-07-07

GitHub `windows-latest` runner ran the suite with the Python child-process stdout defaulting to **cp1252** (not UTF-8 mode). Every production entry point in `bin/*.py` and `hooks/*.py` prints emoji (🧭📌🧠💾✨🔧), arrows (`→` U+2192, `↑` U+2191) and box-drawing chars to stdout/stderr with NO UTF-8 guard (no `sys.stdout.reconfigure(encoding="utf-8")` anywhere in the codebase). Result on cp1252: `print()` raises `UnicodeEncodeError: 'charmap' codec can't encode character` → script exits rc=1. Reproduced locally 1:1 with `PYTHONIOENCODING=cp1252 python3 <script>`:
- `git-memory-install.py --auto` → rc=1, CLAUDE.md + manifest.json NEVER written → cascades into ~72 `FileNotFoundError` + many AssertionError downstream.
- `hooks/user-prompt-memory-check.py` → rc=1 on EVERY invocation (even empty/garbage stdin) because its own static output contains `→`. Claude Code runs this per prompt ⇒ memory injection fully broken for Windows cp1252 users. **T1.**
- `git-memory-commit.py` → commit is made (line 447) then crashes at the emoji result print (line 381/455) ⇒ rc=1 after a successful commit.

**Why it was green on the dev's real Windows box:** that box was almost certainly in Python UTF-8 mode (`PYTHONUTF8=1`) or a UTF-8 console (`chcp 65001` / Windows Terminal). Same latent-defect-masked-by-UTF-8-mode trap as the sibling pattern below. Do NOT trust a single green Windows run.

**Two compounding TEST-harness bugs (separate from the production T1):**
1. `tests/conftest.py::run_cmd` calls `subprocess.run(..., text=True)` with **no `encoding="utf-8"`** → on Windows the PARENT decodes the child's UTF-8 output as cp1252 → `UnicodeDecodeError` in `subprocess._readerthread` (byte 0x8f/0x90). Central harness ⇒ wide blast radius.
2. `tests/test_user_prompt_skill_router.py::_read_skill_description` (and peers) `open()` SKILL.md with no `encoding="utf-8"` → decode byte 0x90 pos 15660 under cp1252.

**Fix layers (WHAT):** (a) Production: force UTF-8 on every entry point's stdout/stderr (e.g. `sys.stdout.reconfigure(encoding="utf-8", errors="...")` at startup, or emit a UTF-8 wrapper) — this is the T1. (b) Tests: add `encoding="utf-8"` to conftest `run_cmd`'s subprocess and to every `open()` of a UTF-8 file. Fixing only the runner env (PYTHONUTF8=1 in the workflow) would mask the production T1 for real cp1252 Windows users — WRONG layer, same trap as the git-identity round.

**Ubuntu sibling cluster (same run, NOT encoding):** 7 ubuntu failures (drift snapshot/post-hook empty, boot time_ago absent, recall-beyond-500, regression context detection) did NOT reproduce locally on macOS across Python 3.10 (real, via uv) OR 3.14, in isolation OR full suite (984 passed). Ruled out: git identity (fix holds), Python version, test ordering/shared-state, and locale-read (`lib/git_helpers.run_git` forces `encoding="utf-8"`). Sole remaining variable: runner git version (~2.43 vs local 2.50) on Linux — not reproducible without that git. Observability gap that hid it: the failing tests route through production subprocesses (`precompact-snapshot.py`, post-hook) via `run_cmd`/`run_snapshot` that **discard stderr** (`rc, out, _ = ...`) — recommend surfacing that stderr so the runner reveals the actual crash before re-diagnosing.

## Pattern: PYTHONUTF8=1 Masks Windows cp1252 Encoding Defects ("works on my Windows box")

**Project:** unmassk-toolkit (git-memory)
**First seen:** 2026-07-06

When auditing Windows portability, a machine can report `locale.getpreferredencoding(False) == 'utf-8'` while `locale.getencoding() == 'cp1252'`. That split is the tell that **Python UTF-8 mode is active** (`sys.flags.utf8_mode == 1`, driven by `PYTHONUTF8=1` in the environment). Under UTF-8 mode, `open()` without `encoding=` and `subprocess(..., text=True)` without `encoding=` both default to UTF-8 — so encoding bugs do NOT reproduce on that machine. On a DEFAULT Windows install (no PYTHONUTF8), the same calls default to cp1252 and break: git/gh UTF-8 output (accents, commit emojis) becomes mojibake, and undecodable multi-byte sequences raise `UnicodeDecodeError` — a subclass of `ValueError`, so a wrapper catching `(SubprocessError, OSError, ValueError)` swallows it into a silent failure.

**Detection:** `python -c "import sys,locale;print(sys.flags.utf8_mode, locale.getpreferredencoding(False), locale.getencoding())"`. If utf8_mode=1 with preferred=utf-8 but getencoding=cp1252 → encoding findings are LATENT, not absent. Report them as real defects masked by env config, and do NOT conclude "encoding is fine on Windows" from a single UTF-8-mode box.

**Also confirmed here:** `os.O_NOFOLLOW` — `hasattr(os,'O_NOFOLLOW')` is `False` on win32 (Python 3.11), so any `os.open(..., O_NOFOLLOW)` raises `AttributeError` (NOT `OSError`, so `except OSError` guards do not catch it). An `ImportError`-based fallback to a second copy of the same helper gives zero protection when both copies reference the missing flag. `os.chmod(p,0o600)` / `os.open(p,flags,0o600)` are near-no-ops on Windows (only the read-only bit maps) — any "0o600 = no group/other access regardless of umask" guarantee in the code is FALSE on Windows.

## Pattern: pytest sys.modules Stub Leak Across Test Files (Bare ModuleType Poisons Real Import)

**Project:** unmassk-toolkit (git-memory)
**First seen:** 2026-06-09

A test that stubs a shared module by inserting a bare `types.ModuleType` into `sys.modules` — and only restores `sys.path` in its `finally` (not `sys.modules`) — leaves the stub registered for the entire pytest process. pytest runs all files in one process with a shared `sys.modules`, so a later test that does a real `from <module> import <symbol>` resolves to the stub.

**Concrete instance:** `test_migrate_statusline.py` `_load_migrate_fn()` did:
```python
for stub_name in ("git_helpers", "parsing", "version"):
    if stub_name not in sys.modules:   # guard: only stub if absent
        stub = types.ModuleType(stub_name)
        stub.run_git = ...             # but NOT GIT_TIMEOUT
        sys.modules[stub_name] = stub
try: spec.loader.exec_module(mod)
finally: sys.path[:] = saved          # restores sys.path, NOT sys.modules
```
The stub `git_helpers` survives. Later `test_recall.py` → `from recall import recall` → `recall.py` line 33 `from git_helpers import run_git, GIT_TIMEOUT` resolves to the stub, which lacks `GIT_TIMEOUT`.

**Signature error:** `ImportError: cannot import name 'GIT_TIMEOUT' from 'git_helpers' (unknown location)`. The "(unknown location)" is the tell: a synthetic `ModuleType` has no `__file__`/`__spec__`, so Python reports its origin as unknown — proof the import resolved to a hand-built stub, not the real `lib/git_helpers.py`.

**Detection:**
1. Test passes in isolation, fails in full suite (classic shared-global-state signature).
2. Bisect: `pytest <earlier_file> <failing_file>` for each alphabetically-earlier file until the pair reproduces.
3. The error names a module "from (unknown location)" → look for a test that builds that module via `types.ModuleType(...)` and assigns into `sys.modules`.
4. Check the stub's `finally`: does it restore `sys.modules` or only `sys.path`?
5. The `if stub_name not in sys.modules` guard means the stub is also non-deterministic — whether it leaks depends on whether the real module was imported first by an earlier test.

**Fix pattern (test isolation, not production code):**
- The polluting test must restore `sys.modules` for every name it stubbed. Snapshot the prior entry (or absence) and restore in `finally`, OR use `monkeypatch.setitem(sys.modules, name, stub)` (auto-reverts), OR an autouse fixture that snapshots/restores `sys.modules` + `sys.path` around each test.
- Do NOT "fix" this by making recall.py tolerate a missing GIT_TIMEOUT — that masks the leak and weakens the real import contract.

## Pattern: Verifying PreToolUse `updatedInput` prompt injection reaches a subagent — the transcript records PRE-hook input, so injection is INVISIBLE there

**Project:** unmassk-toolkit (pre-task-recall.py memory footer) · **Seen:** 2026-07-12 · confirmed live, first-party

Question class: "does hook X's `hookSpecificOutput.updatedInput.prompt` actually reach the spawned subagent, or is it a silent no-op?" (People suspect no-op because of upstream bug #15897 re: skill injection.)

Key structural facts about Claude Code transcripts (`~/.claude/projects/<proj>/<session>.jsonl`):
1. **Subagent conversations are NOT in the .jsonl** — `isSidechain=true` count is 0 in current versions. Subagent I/O goes to separate `/private/tmp/claude-501/.../<session>/tasks/<task-id>.output` files. So you cannot read the subagent's received prompt from the parent .jsonl.
2. **The recorded `tool_use.input(Agent/Task).prompt` is the MODEL's ORIGINAL prompt (PRE-hook).** The hook's `updatedInput` is applied AFTER and is NOT written back into the transcript. Proof: across 58 Agent spawns in one session, the real footer signature appeared in the recorded sent-prompt **0 times**, even for whitelisted agents that demonstrably received it. This is exactly why the injection looks like a no-op from the orchestrator side and why nobody could confirm it.
3. **Beware loose grep matches.** Matching `"PROJECT MEMORY"` caught false positives where the orchestrator QUOTED the block format as literal task-description text (building the feature). Use the exact distinctive footer phrase (e.g. `auto-recalled, relevant to your task`) as the signature. Also: `json.dumps` escapes em-dash `—` to `—` — use `ensure_ascii=False` or match on the raw line.

**The airtight verification (what actually resolves it):** compare the orchestrator's RECORDED spawn prompt (pre-hook, footer absent) against what the subagent ACTUALLY received. First-party is cleanest: when House itself is the whitelisted subagent, its own live prompt ends with the exact `_FOOTER_HEADER` + real recall block, while the parent transcript's `tool_use.input` for that same `subagent_type:house` spawn shows `footer=False`. The delta (footer, added between tool_use emission and receipt) can only be the PreToolUse hook's `updatedInput` → **injection DOES propagate; not a no-op.** Secondary corroboration: subagents echo the footer back in their `toolUseResult` returns (but filter out sessions where the footer is the investigation topic — self-contamination).

**Lesson:** `updatedInput` propagation cannot be confirmed OR denied from the parent transcript alone (it records pre-hook). Confirm via first-party subagent receipt or the `tasks/*.output` files. A green test that asserts the hook's emitted JSON contains `updatedInput.prompt` proves only WHAT THE HOOK EMITS, never that Claude Code delivers it — that is an end-to-end gap no subprocess-level unit test closes.

## Pattern: Schema-Code Divergence (Phantom Tables)

**Project:** omawamapas
**First seen:** 2026-03-15

Code references tables that do not exist in schema.sql or any migration file. Root cause: code was written against an aspirational/planned schema that was never migrated into the database. The schema.sql is a pg_dump of the ACTUAL database; the code was authored (likely by AI agents during audit rounds) assuming tables that would exist in a future state.

**Detection:** grep for FROM/JOIN/INTO + table name, then verify against schema.sql CREATE TABLE statements.

**Affected tables (as of 2026-03-15):**
- `usuarios` (code uses plural; DB has singular `usuario`)
- `layer_permissions` (no CREATE TABLE anywhere)
- `spatial_layers` (no CREATE TABLE anywhere)
- `supervisor_municipio` (no CREATE TABLE anywhere)
- `operador_municipio` (no CREATE TABLE anywhere)
- `inventario` (code uses short form; DB has `inventario_amianto`)
- `capa` (no CREATE TABLE anywhere)
- `eventos` (no CREATE TABLE anywhere)

**Key insight:** The initial Knex migration (`20250507162238_initial_schema_setup.ts`) is a no-op stub (empty up/down). All schema was created via raw SQL (supabase_migration.sql or direct pg_dump). Code modules were built by audit agents without verifying against actual DB state.

## Pattern: ws.publish vs server.publish in Elysia/Bun (Self-Delivery)

**Project:** agent-chatroom
**First seen:** 2026-03-18

`ws.publish(topic, data)` in Bun/uWebSockets sends to all topic subscribers EXCEPT the calling socket. `server.publish(topic, data)` sends to ALL subscribers including the sender. Elysia's `publishToSelf: true` in `.ws()` config does NOT work in v1.4.28 — the option is inherited from Bun types but not implemented by Elysia.

**Root cause:** `broadcastSync()` received `ws` (individual connection) as its `server` parameter, calling `ws.publish()` which by uWebSockets design excludes the sender. The sender never receives their own message back.

**Detection:** When "messages not received" in WS system, check whether publish originates from individual socket or server instance. Test with 2 connections — if other subscriber receives but sender does not, this is the pattern.

## Pattern: Windows CMD Flash from Child-of-Child Process Spawning

**Project:** agent-chatroom
**First seen:** 2026-03-18

`windowsHide: true` in Bun.spawn v1.3.11 is **inversely implemented** on Windows. Instead of suppressing console windows, it CREATES them. Tested empirically:

| Executable | windowsHide: true | No flags | conhost.exe? |
|---|---|---|---|
| node.exe | conhost CREATED | No conhost | BUG |
| claude.exe | conhost CREATED | No conhost | BUG |
| cmd.exe | No conhost | No conhost | No diff |

**Root cause:** When `windowsHide: true` is passed, Bun's libuv integration on Windows passes incorrect `CreateProcessW` flags (likely `DETACHED_PROCESS` instead of `CREATE_NO_WINDOW`), causing console subsystem executables to allocate a new console via `conhost.exe`. Without the flag, piped stdio naturally suppresses console allocation.

**Also found:** `process.kill(-pid, 'SIGTERM')` (negative PID for process group kill) does NOT work on Windows in Bun 1.3.11 (ESRCH error). The FIX 16 orphan cleanup pattern is broken on Windows.

**Secondary factor:** `claude.exe` internally spawns `cmd.exe /d /s /c "npx ..."` for MCP servers. Even if `windowsHide` worked correctly, these grandchild processes would not inherit the flag.

**Detection:** Use `Get-CimInstance Win32_Process | Where ParentProcessId -eq $PID` to check for `conhost.exe` children.

**Fix:** Remove `windowsHide: true` (it does the opposite of what's intended). Remove `detached: true` (process group kill is broken on Windows anyway). Replace orphan cleanup with `proc.kill()` direct call with timeout. The piped stdio (`stdout: 'pipe', stderr: 'pipe'`) already prevents console window creation without any additional flags.

## Pattern: Missing `position: relative` on Dropdown Anchor (CSS Clipping)

**Project:** agent-chatroom
**First seen:** 2026-03-21

Absolutely-positioned dropdown (`.mention-dropdown`) renders inside a container (`.chat-input`) that lacks `position: relative`. The dropdown's containing block falls through to a distant ancestor (`.chat`) that has `position: relative; overflow: hidden`. The dropdown positions itself relative to `.chat` and ends up outside its clipping bounds -- invisible to the user.

**Detection:** When a dropdown "should render but doesn't appear," check:
1. The dropdown's `position: absolute` CSS
2. Whether its immediate parent has `position: relative`
3. Whether any ancestor between parent and containing block has `overflow: hidden`

**Key insight:** The React state and DOM are correct (the element exists in the DOM tree). The issue is purely CSS positioning. DevTools element inspector will show the element exists but is positioned outside visible bounds. This pattern is especially common when refactoring from `<input>` to `<textarea>` or reorganizing component hierarchy -- the CSS containment context changes but the dropdown positioning CSS is not updated.

## Pattern: HMR Cascade Amplification of React-Managed Side Effects

**Project:** agent-chatroom
**First seen:** 2026-03-21

When a side effect (WebSocket, fetch, timer) is managed inside a React `useEffect`, Vite HMR cascades can create unbounded amplification loops. The trigger: backend dies -> Vite proxy loses upstream -> HMR update fires -> React remounts component tree -> `useEffect` restarts the side effect -> side effect fails (backend still down) -> triggers Zustand state updates -> React re-renders -> HMR detects changes -> loop repeats.

**Key factors:**
1. Side effect initiated in `useEffect` (coupled to React lifecycle)
2. Vite dev proxy forwarding to the backend (proxy errors trigger HMR)
3. Each attempt creates Zustand state transitions that trigger re-renders
4. Debounce/backoff guards bypassed during reconnect cycles
5. StrictMode cleanup delays (100ms) designed for double-mount, not rapid HMR

**Detection:** When an Electron host (Cursor, VS Code) shows extreme RAM/CPU after a backend process stops, check whether the frontend has React-lifecycle-managed connections to that backend. Look for `useEffect` + `connect()` patterns in root-level components.

**Fix pattern:** Decouple connection lifecycle from React. Run connect/reconnect as a module-level singleton. React hooks should be passive subscribers (read status), not active controllers (trigger connections). Add circuit breakers on repeated failures.

## Pattern: Concurrently Piped Output -> Electron Terminal OOM

**Project:** agent-chatroom
**First seen:** 2026-03-21

When `concurrently` runs multiple dev processes (backend, frontend, bridge) WITHOUT `--kill-others-on-fail`, killing one process leaves others alive. Surviving processes that have reconnect logic to the dead process produce sustained stderr/stdout floods. Concurrently pipes all child stdio (`['pipe', 'pipe', 'pipe']` in spawn.js). The output flows into Cursor/VS Code's Electron terminal (xterm.js), which retains ALL scrollback in V8 renderer memory without bounds. On machines with <= 16GB RAM this triggers OOM.

**Causal chain:**
1. Backend killed -> concurrently keeps bridge + frontend alive (no --kill-others)
2. Bridge: 20 reconnect attempts, each logging to console.error
3. Frontend: 10 reconnect attempts through Vite proxy (5s timeout per attempt)
4. Vite proxy: logs its own errors for each failed upstream connection
5. Health check loop (10s interval) continues producing proxy errors indefinitely
6. pino-pretty ANSI colorization inflates per-line memory footprint
7. xterm.js scrollback buffer retains everything in Electron renderer heap

**Detection:** When an Electron IDE (Cursor, VS Code) shows extreme RAM after killing a child process in a `concurrently` managed terminal, check: (a) does the concurrently script use --kill-others? (b) do surviving processes have reconnect loops to the dead process? (c) how many console.error/warn calls per reconnect cycle?

**Fix pattern:** Add `--kill-others-on-fail` to the concurrently dev script. Reduce reconnect attempt counts for dev environments. Cap or silence intermediate reconnect log output.

## Pattern: Status Overwrite After Async Subprocess Completion

**Project:** agent-chatroom
**First seen:** 2026-03-21
**Updated:** 2026-03-21 (runtime verification)

SIGSTOP DOES freeze the `claude` process (confirmed: `ps` shows state `T` on PID). However, SIGSTOP does NOT propagate to child processes (MCP servers). And the completion path unconditionally overwrites Paused status.

**Three compounding failures:**
1. **SIGSTOP only stops the parent** — `process.kill(pid, 'SIGSTOP')` targets only the `claude` process. Its children (MCP servers spawned via `npm exec`) remain in state `S` (running). To stop the entire process group: `process.kill(-pid, 'SIGSTOP')` (negative PID = process group signal). This works because `detached: true` gives `claude` its own process group.
2. **Timeout ignores pause** — `makeTimeoutHandle` runs on wall-clock time (5 min). If the agent is paused for 4 minutes, only 1 minute of actual work time remains before the timeout kills it. No mechanism pauses or extends the timeout during SIGSTOP.
3. **Completion path overwrites status** — `handleAgentResult`, `handleFailedResult`, `handleEmptyResult` in `agent-result.ts` and `agent-stream.ts` unconditionally set status to Done/Error without checking `isAgentPaused()`. When the subprocess eventually completes (after SIGCONT, or after timeout kill), status flips from Paused to Done.

**Detection:** When a control button "doesn't work" but the system message confirms the handler ran, check: (a) `ps -o state` on the process — is it actually `T`? (b) are child processes also stopped? (c) does the timeout fire while paused? (d) does the completion path check pause state?

**Key insight:** The SIGSTOP mechanism fundamentally works (confirmed by runtime test). The real bugs are: missing process-group signal, no timeout suspension during pause, and unconditional status overwrite on completion.

## Pattern: bun:test mock.module() Global Leak Across Test Files

**Project:** agent-chatroom
**First seen:** 2026-03-24

`mock.module()` in bun 1.3.11 affects the **global module registry**, not just the declaring test file. When file A mocks `../../src/services/agent-runner.js` with a stub, file B (which imports the real `agent-runner.js` and has its own mock.module for different modules) gets file A's stub instead of the real implementation.

**Root cause:** bun test runs all test files in the same thread with a shared module cache. `mock.module()` replaces entries in this shared cache. Once replaced, ALL subsequent imports of that module path resolve to the mock, regardless of which test file does the importing.

**Symptoms:**
- Mock capture arrays (`_publishCalls`, `_broadcasts`) stay empty
- DB queries return 0 rows despite functions that insert data
- Tests pass in isolation but fail in full suite
- One specific test file causes ALL other mock-dependent tests to fail

**Detection:**
1. Run failing test file in isolation -- if it passes, this is the pattern
2. Binary search: `bun test fileA.test.ts fileB.test.ts` to find the poisoning file
3. Check if the poisoning file mocks a module that OTHER test files import directly (not just transitively)
4. The poisoning file's mock.module replaces the real implementation; downstream files get the stub

**Key test:** `bun test $(ls tests/**/*.test.ts | grep -v <poisoning-file>)` -- if 0 failures, confirmed.

**Fix pattern:** The poisoning test file must NOT use `mock.module()` on modules that other test files import for real behavior. Options:
1. Mock at a higher level (mock the functions, not the module)
2. Use dependency injection so the test can pass stubs without `mock.module`
3. Restructure so the poisoning test uses `jest.fn()`/`mock()` on individual functions rather than replacing entire modules

## Pattern: Bun.spawn stdin:Uint8Array EOF Not Signaled on Windows (Lost Result Event)

**Project:** agent-chatroom
**First seen:** 2026-03-25

When `Bun.spawn` is called with `stdin: Uint8Array` on Windows, the write end of the stdin pipe may not be properly closed after all bytes are written. The subprocess (`claude`) receives the prompt data but never gets an EOF signal on stdin. Combined with the lack of `detached: true` on Windows (disabled due to Bun 1.3.11 bugs), this creates a cascading failure:

1. `claude` CLI reads the prompt from stdin (agent starts working, tool_use events flow)
2. Agent completes tool use and prepares its response
3. The result event is the LAST stdout write before process exit
4. On Windows, forced process termination (timeout kill via `proc.kill()`) or abnormal exit may discard unflushed stdout pipe data
5. The stdout reader sees `done: true` without the result event
6. `handleEmptyResult` fires, posting "Agent X returned no response."

**Key distinction from Unix:** On Unix, pipe semantics guarantee all written data is readable by the parent even after process exit. On Windows, this guarantee does not hold for forced termination. Additionally, on Unix `detached: true` + process group kill (`process.kill(-pid, 'SIGTERM')`) allows graceful shutdown; on Windows, only `proc.kill()` is available.

**Detection:**
1. Agent tool_use events arrive (visible in chat as ToolLine items) but no agent message follows
2. System message "Agent X returned no response." appears
3. Only reproducible on Windows, not Mac/Linux
4. Check pino logs for the `handleEmptyResult` path being hit with `hasResult: false`
5. Check whether the subprocess was killed by timeout vs exited normally

**Compounding factors:**
- `windowsHide: true` bug (already documented above) — shows Bun 1.3.x has systemic Windows CreateProcessW issues
- `process.kill(-pid)` ESRCH on Windows — shows process group management is broken
- These are all in the same Bun libuv/Windows-API integration layer

**Fix approach:** Use `-p` flag with a stdin-fallback pattern: pass a short marker via `-p` and the full prompt via stdin, OR pipe through a shell wrapper that explicitly closes stdin after writing, OR detect the empty-result-after-tool-use condition and retry with `-p` arg directly (truncated to Windows limits).

## Pattern: Windows-only CI red = extensionless fake-git shim on PATH is silently bypassed (missing @skipif(WINDOWS) guard), NOT a product bug

**Project:** unmassk-toolkit (git-memory boot) · **Seen:** 2026-07-10 · confirmed from CI run 29110579481 (sha 174d82b) + source + git history

Symptom shape: N Windows-latest test failures, ALL identical `assert fetch_calls` -> `assert []` (empty), while every product-behavior assert BEFORE that line PASSES on Windows (e.g. vector B's `assert memory_line.startswith("MEMORY: remote (fetched ")` passes -> product DID fetch for real). macOS/Linux all green.

Root cause: `tests/test_boot_freshness.py::_make_fake_git` (~L261) writes an extensionless, chmod-755 file literally named `git` (POSIX shebang script) into a dir prepended to PATH, to observe whether boot attempted a fetch (it logs every invocation to a jsonl). The boot's `run_git` does `subprocess.Popen(["git"] + args)` (lib/git_helpers.py:456) — bare name. On POSIX, PATH lookup finds `fake_bin/git` first (executable). On Windows, `Popen(["git"])` resolves the bare name via PATHEXT and does NOT treat an extensionless file as executable, so the REAL `git.exe` further down PATH runs -> the fake jsonl stays empty -> `fetch_calls == []` -> assert fails. The product ran real git and behaved correctly the whole time; only the TEST's observation instrument is Windows-blind.

The class already DOCUMENTS this (comment ~L234-236 "POSIX only — Windows does not resolve a bare extensionless `git`...") and the repo-wide convention is `@pytest.mark.skipif(WINDOWS, reason="fake-git PATH-shadowing needs a POSIX-executable named exactly 'git'")` — present on sibling tests at test_boot_freshness.py:1305/1379, test_boot_freshness_hardening.py:348, test_date_parsing_epoch_contract.py:374/429. The failing tests are simply NEW and forgot the guard. `WINDOWS = sys.platform == "win32"` at L68.

Latent secondary (not a red, worth flagging): `assert not fetch_calls` tests (test_boot_freshness.py ~L1401/1468) RUN on Windows and pass vacuously there (empty log makes `not fetch_calls` trivially true, for the wrong reason) — they stay honest only because the author also pins stamp-file evidence (self-noted ~L1458). A Windows-portable shim would fix that blindness too.

Fix (Dante, TEST-ONLY — NO product change): (A) cheap/matches precedent: add `@skipif(WINDOWS, ...)` to the failing tests -> instant green but ZERO Windows coverage of fetch-gate logic. (B) better: make `_make_fake_git` Windows-portable — on win32 write `fake_bin/git.cmd` (or .bat) = `@"<sys.executable>" "<fake_git.py>" %*`; bare `["git"]`+PATHEXT then finds it before git.exe -> ALL fake-git tests (incl. the currently-skipif'd ones) run on Windows, closing the gap. Precedent for B exists: test_boot_freshness_regression.py:455 already has a "Windows counterpart" shim helper. Use sys.executable, never bare `python`.

**Lesson:** for this suite, Windows-only red with a uniform `assert []` on a fetch/call-observation list = the extensionless fake-git PATH-shadow instrument, not product. Before diagnosing product, check: (1) do the pre-assert product-behavior asserts PASS on Windows? (2) is `@skipif(WINDOWS)` present like on the sibling fake-git tests? Grep `_make_fake_git` + `skipif(WINDOWS)` to find un-guarded new tests.

## Pattern: Windows-only CI test failures from POSIX-assuming test scaffolding (expanduser HOME + text-mode CRLF), never a production bug

**Project:** unmassk-toolkit (Windows CI matrix, toolkit-ci.yml) · **Seen:** 2026-07-11 · confirmed by code trace of PR #65

Two independent Windows-only test-red patterns, both TEST-ONLY (production code is correct on Windows):

1. **`os.path.expanduser("~")` ignores `HOME` on Windows.** Tests that sandbox the plugin cache by launching a subprocess with `env={"HOME": tmp}` work on POSIX (posixpath.expanduser reads HOME) but NOT on Windows: `ntpath.expanduser` uses `USERPROFILE` first, then `HOMEDRIVE`+`HOMEPATH` — HOME is never consulted (verified via `inspect.getsource(ntpath.expanduser)`). GitHub Actions Windows runners always set USERPROFILE, so a module-level `CACHE_BASE_DIR = expanduser("~")/...` resolves to the REAL runner home, not the fixture → planted-drift/planted-state under the fixture HOME is never scanned → "expected warning absent" assertions fail. Fix (test): also set `USERPROFILE` (and for robustness HOMEDRIVE/HOMEPATH) in the subprocess env, not just HOME. Production is fine: on a real Windows box expanduser resolves the real profile where the cache actually lives.

2. **Python text-mode write translates `\n`→`\r\n` on Windows.** Producers that read CLAUDE.md via `os.fdopen(fd, "r", ...)` (default newline=None → universal-newlines normalizes to `\n`) and write via `os.fdopen(fd, "w", ...)` (default newline=None → `\n`→os.linesep) legitimately produce a UNIFORM-CRLF file on Windows (NOT mixed EOLs — read normalizes everything to LF first, write converts everything to CRLF). Tests that read the produced file with `open(..., "rb")` (raw, preserves CRLF) and then assert an LF-rendered expected string is a substring (`expected in content_after`) or call semantic checks (`any_block_outdated`) fail on Windows. Fix (test): normalize `content.replace("\r\n","\n")` before string/semantic comparisons; byte-level marker/note checks with no internal newline are unaffected. Uniform CRLF in a user's CLAUDE.md is cosmetic/normal on Windows — not a production defect.

**Common tell:** Ubuntu green + Windows red + local macOS green. Both patterns are POSIX-vs-Windows platform divergence in the TEST harness, invisible on POSIX dev machines. Always separate "producer wrote platform-native EOL / expanduser resolved real home" (correct) from "test hard-coded LF / assumed HOME override" (the actual defect).

## Pattern: Ubuntu-CI-only flake that self-heals on retry + `git exit 128` = environmental resource-pressure transient, NOT a fixture logic bug — and the production `git log` swallows rc!=0 into empty (silent memory loss)

**Project:** unmassk-toolkit (#61, git-memory recall/drift/consolidation) · **Seen:** 2026-07-18 · confirmed by code trace + could-not-reproduce on macOS under aggressive stress

Family flakes ONLY on ubuntu-latest CI (2 vCPU/7GB), never macOS/Windows-local. Symptom: `git log --all --grep=...` exits 128 (git's `die()` code) on fixtures of hundreds (or even ~50) sequential commits. Disambiguation of exit 128: run_git returns **rc 1** on timeout (git_helpers.py 3 sites) and **rc 0** on zero-results, so 128 is neither timeout nor empty — it is a genuine transient git die under load. Self-heals on retry ⇒ environmental, not a logic bug.

Ruled OUT with evidence: (a) fixture logic — commits built sequentially THEN scanned, no concurrent write during the scan; (b) background auto-gc/pack-refs race — 510 empty commits = 513 loose objects, far below gc.auto default 6700, so auto-gc is a no-op; could not reproduce on macOS/APFS even forcing gc.auto=1+autoDetach, nor under 2583 reads during concurrent commit+pack-refs+gc-prune churn (0/2583 failures). Class that survives: transient fork/mmap/alloc or slow-fs ref-read failure under Ubuntu-CI contention. The EXACT stderr `fatal:` line (captured by the v1.19.4 breadcrumb, log_stderr_on_failure=True) is the missing piece that pins fork/OOM vs bad-ref — it lives in CI logs, not in the code.

**Load-bearing tell (the real bug behind the flake):** production `_scan_commits()` (lib/recall.py) does `if code != 0 or not log_output: return []` — a transient exit 128 collapses to "no memory found", indistinguishable from genuinely-empty, feeding the UserPromptSubmit/PreToolUse injection with EMPTY memory. Same silent-empty shape at boot_memory.py extract_glossary() and boot_git_checks.py get_timeline(); consolidation counter returns 0. Breadcrumbs make it VISIBLE on stderr but do NOT change the return value — the user still silently loses the read (signed threat model: system-against-itself, silent memory loss). The test-side `_recall_with_retry`/`_run_boot_with_retry` wrappers are symptom-side band-aids: they green the CI but production has NO retry, so a real user still loses memory on the same transient. Do not "fix the flake" by deleting the integrity guard — the guard is the smoke detector; the fire is the un-retried silent-empty return in prod.
