---
name: unmassk-toolkit-python-test-conventions
description: pytest conventions for unmassk-toolkit itself (lib/hooks/bin Python code) — separate stack from chatroom's bun:test
metadata:
  type: feedback
---

This project (unmassk-toolkit, the plugin at repo root) is tested with **pytest**,
not bun:test — do not confuse with [conventions](conventions.md) which is
chatroom/apps/backend only. Tests live in `unmassk-toolkit/tests/`, source in
`unmassk-toolkit/lib/` (importable modules) and `unmassk-toolkit/hooks/` +
`unmassk-toolkit/bin/` (hyphenated-filename scripts, e.g.
`pre-validate-commit-trailers.py`, `session-start-boot.py`).

**Why this matters:** hyphens in filenames make them non-importable via normal
`import`. The codebase's own pattern (see test_crown.py) is:
```python
import importlib.util
spec = importlib.util.spec_from_file_location("boot", BOOT_HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
```
Use this to reach functions like `validate_trailers()` or `extract_memory()`
directly, instead of only asserting on subprocess exit codes — direct import
lets you assert on the actual return value (e.g. the `errors` list), which is
far more precise than parsing stdout/stderr.

**Gotcha: `check_hook_msg(..., as_claude=True)` cannot test trailer-content
logic.** In `pre-validate-commit-trailers.py`, any literal `git commit`
command run with `CLAUDE_CODE=1` and not going through
`git-memory-commit.py`/`git-memory-log.py` is blocked UNCONDITIONALLY by a
"use the wrapper script" gate — before trailer validation ever runs. So
`check_hook_msg(subject, cwd, trailers, as_claude=True) != 0` is always true
regardless of trailer correctness; it only proves the wrapper gate exists, not
that a specific trailer is required. To test "is trailer X required," call
`validate_trailers(commit_type, trailers_dict, branch)` directly via the
importlib pattern above.

**Gotcha: `as_claude=False` (human) path always returns rc=0.** Both
pre/post-validate-commit-trailers.py warn-only for non-Claude authors — the
exit code is unconditionally 0 whether or not there are errors. A test
asserting `rc == 0` for `as_claude=False` is trivially true and proves
nothing; assert on stderr content (e.g. `"Why" in stderr`) instead, to prove
the check actually ran and produced the expected warning text.

**Repo helper conventions** (see conftest.py + test_crown.py):
- `_make_repo(tmp_path)` — bare git repo, no install, direct `git commit
  --allow-empty` via `_commit(repo, subject, trailers)` (bypasses hooks —
  used for testing boot/extraction logic, not validation).
- `_make_installed_repo(tmp_path)` — runs `git-memory-install.py --auto`
  first, for tests that need the full installed layout (e.g. glossary cache
  path under `.claude/.unmassk/`).
- `_run_boot(repo)` — runs `session-start-boot.py` as subprocess, returns
  stdout. Assert on slices like `output[output.find("DECISIONS:"):+800]` to
  scope assertions to one section instead of the whole boot text.
- `_extract_memory(repo)` / `_extract_glossary(repo)` — run a small inline
  Python snippet as a subprocess that monkeypatches `git_helpers.run_git` to
  point `GIT_DIR`/`GIT_WORK_TREE` at the temp repo, then calls
  `boot.extract_memory()`/`extract_glossary()` and prints JSON. Needed because
  these functions call `run_git` with no `cwd` param (relies on process cwd +
  env), so this is the reliable way to isolate them per-test.
- Decision/Memo/Remember entries in `extract_memory()`/`extract_glossary()`
  are `(label, text, is_crown)` 3-tuples, deduped one-per-scope. `label` is
  `"(scope)"` or `"(global)"`.

**Gotcha: `_extract_memory()`'s `json.dumps()` is a hand-picked whitelist, not
a mirror of `extract_memory()`'s real return dict.** `extract_memory()` (in
`lib/boot_memory.py`) returns `{last_context, pending, blockers, decisions,
memos, remembers, tombstones}`, but the test helper in `test_boot_output.py`
only serializes the keys it happened to need when written. A test written
later that reads `_extract_memory(repo)["pending"]` (or any other key not yet
in the whitelist) fails with `KeyError`, and it looks like a production bug —
it isn't; `git stash` on production code reproduces the identical failure
because the break is in the test helper's serialization, not the code under
test. `pending`/`blockers` are lists of plain dicts (already JSON-serializable
— do NOT run them through `_ser()`, which is only for the `(label, text,
is_crown)` tuple lists); `tombstones` is a `set` and needs `list()` if a
future test ever needs it. Rule: whenever a new test needs a top-level key
from `extract_memory()`/`extract_glossary()`, add it to the helper's
`json.dumps({...})` dict explicitly — don't assume "the helper already
returns everything the function does."

**Technique: forcing a defensive-import fallback branch (`X = None` on
ImportError) without stubbing the whole module.** Several hot-path functions
(`hooks/session-start-boot.py:write_boot_log()`,
`lib/boot_glossary_cache.py:_write_glossary_cache()`) do `try: from
git_helpers import ensure_runtime_dir; except ImportError:
ensure_runtime_dir = None` at module level, then branch on that name at call
time. To exercise the `else` fallback branch in a test, do NOT stub
`sys.modules["git_helpers"]` (that risks breaking sibling module-level
imports and needs careful restore/whitelist bookkeeping, see the
`_extract_memory()` gotcha above) — instead load the target module normally
via the importlib spec_from_file_location pattern (real git_helpers, real
import succeeds), then simply overwrite the already-bound name on the loaded
module object: `mod.ensure_runtime_dir = None`. This forces the fallback
branch on the next call while every other dependency
(boot_memory/boot_migrations/boot_render/version) keeps using the real
git_helpers. Always do this inside a subprocess (`import sys, os, json,
importlib.util; ...; print(json.dumps(...))`, same pattern as every other
importlib probe in test_security_regression.py), not in-process, since these
are real stably-named modules and an in-process load risks sys.modules
contamination across test files in the same pytest session (see Round 4 in
[boot-stdout-banner-contract-notes](boot-stdout-banner-contract-notes.md)).

**Gotcha: patch the module that OWNS the function's `__globals__`, not
whatever module object you happened to load it through.** `_write_glossary_cache()`
used to live in `lib/boot_memory.py`; Ultron later split it out into
`lib/boot_glossary_cache.py` (boot_memory.py's theme stayed "commit-history
parsing"; the new module's theme is "glossary cache I/O"). `boot_memory.py`
still re-exports the name at its own file tail
(`from boot_glossary_cache import (..., _write_glossary_cache, ...)`) purely
so a test that loads `lib/boot_memory.py` via
`spec_from_file_location(throwaway_name, ...)` can still resolve
`mod._write_glossary_cache`. But that re-exported name is just a reference
to the SAME function object — its `__globals__` still points at
`boot_glossary_cache`'s module dict, not at the throwaway `mod` you loaded.
Cerberus caught this exact bug in `test_security_regression.py`'s
`_call_write_glossary_cache_fallback()`: it did `mod.ensure_runtime_dir =
None` after loading `boot_memory.py` under a throwaway name — that patches
an unrelated attribute on an unrelated module while the real lookup at call
time still resolves to the real, non-None `ensure_runtime_dir` in
`boot_glossary_cache`'s globals. The test stayed green, but for the wrong
reason: it silently exercised the normal `if ensure_runtime_dir is not
None` branch instead of the `else` fallback branch it claimed to cover — a
real regression path (`lib/boot_glossary_cache.py`'s fallback
`verify_path_within_project()` guard) went uncovered. **Fix pattern:** `import
boot_glossary_cache` as a REAL (non-throwaway-name) import first — so it
lands in `sys.modules` under its real name — patch
`boot_glossary_cache.ensure_runtime_dir = None` on that real module object,
THEN load `boot_memory.py` via `spec_from_file_location`. Its `from
boot_glossary_cache import (...)` statement reuses the already-patched
`sys.modules["boot_glossary_cache"]` entry, so `mod._write_glossary_cache`
now genuinely sees `ensure_runtime_dir is None` at call time. **Verify with a
mutation check whenever you can't be 100% sure the assertion is exercising
the branch it claims:** temporarily strip the guard from the target `else`
branch, confirm the test NOW fails, then restore the file — a same-result
green test before AND after a guard is deleted is proof the test isn't
covering that guard at all, whatever its docstring says. General rule after
any Ultron file-split: when a test's monkeypatch target is `mod.<name>` on a
module loaded via `spec_from_file_location`, re-verify which module's
`__globals__` the patched function's implementation actually lives in post-split
— re-exports preserve the call site, not the namespace the function reads
from.

**Recurring test shape: "symlinked-parent-directory" (BUG Y class,
11 rounds and counting).** A large, recurring family of security regression
tests in `test_security_regression.py` (BUG Y through AO at last count)
follows one shape: plant a REAL, ordinary intermediate directory
(`.claude`, or a deeper one like `.claude/.unmassk`/`.claude/agent-memory`/
`skills`/`bin`/`lib`) as a symlink to an external, pre-existing directory,
optionally with a real file/dir inside it matching whatever the code under
test looks for, then call the write/delete/migrate path and assert nothing
in the external directory was touched. The project's `verify_path_within_project()` /
`ensure_runtime_dir()` chokepoint (`lib/git_helpers.py`) is the fix for the
whole class — when reviewing where Ultron applied it, check whether the
guard covers ONLY the immediate parent (e.g. `.claude`) or also every
independently-symlinkable sub-path reached along the way (`.unmassk`,
`agent-memory`, etc.) — each of those has needed ITS OWN separate
`verify_path_within_project()` call in this codebase (BUG AC's `claude_dir`
check, BUG AM's `unmassk_dir` check, and BUG AN's `agent_dir`/`target_dir`
check are three independent guards in the SAME function, not one guard
covering all three shapes).

**Windows test-hygiene fix (2026-07-07): `real_symlink_capable` fixture
promoted to `conftest.py`, shared by both symlink test files.** All of the
BUG-Y-class tests above (and BUG D/E/F/I/J/K/L/M/N/O/P/Q/R/S/T/U/V/W/X — 60
test functions total, confirmed via a real `pytest --collect-only` +
failure-list diff, not guessed) plant a REAL `os.symlink()` in their own
setup. On a Windows box without Developer Mode /
SeCreateSymbolicLinkPrivilege, `os.symlink()` raises `OSError: [WinError
1314]` — the test never reaches the guard it's supposed to exercise, so it
FAILED at setup instead of skipping. Fix: the `real_symlink_capable` fixture
(originally local to `test_crossplatform_symlink_guard.py`) now lives in
`tests/conftest.py` as the single source of truth (auto-discovered, no
import needed); the local copy was deleted. Gating pattern used based on
whether EVERY test in a class plants a symlink or only some do (checked
per-class with a `pytest --collect-only` vs failure-list diff before
editing, not assumed from reading test bodies) — do this check again before
adding new tests to this pattern:
- Whole class always symlinks → `@pytest.mark.usefixtures("real_symlink_capable")`
  on the class (34 classes gated this way).
- Class has a mix (e.g. `TestBugFDoctorManifestSymlinkReadWrite` has one
  test that checks the REAL manifest still gets its healthcheck timestamp
  updated — that one must NOT skip) → add `real_symlink_capable` as a
  plain parameter to only the affected test function(s), never a class
  marker (3 classes needed this: BugF, BugI, BugJ, 4 functions total).
Adding the class-level marker to a mixed class would wrongly skip the
non-symlink test and silently lose its coverage.

**Follow-up (same session): the "69 failures" bug report undercounted by
scope, not by number.** The original diagnosis said "69 failures, all in
test_security_regression.py" — actual measurement showed only 60 there.
Always verify a bug report's failure count by actually running the named
file before trusting it; don't silently accept "~N" figures. The other 9
were genuinely elsewhere: `grep -rl "os.symlink(" tests/` across the WHOLE
tests dir (not just the one file named in the report) found 4 more
untouched cases in `test_boot_output.py` (`TestSymlinkWriteProtection` x2,
`TestGlossaryCacheReadSymlinkProtection` x1) and
`test_boot_freshness_hardening.py` (`TestHasToolkitMemory::test_symlinked_claude_md_is_treated_as_absent`
x1) — same WinError 1314 root cause, gated with the same fixture. The
remaining 5 were a DIFFERENT bug class entirely (Windows portability, not
symlink-creation-privilege): POSIX `0o600` mode-bit assertions (NTFS
doesn't deny group/other the same way — already documented as an accepted
decision in `lib/git_helpers.py`'s `open_no_follow_symlink()` docstring, so
that one stays a genuine `@pytest.mark.skipif(sys.platform=="win32", ...)`
rather than a rewrite), `os.chmod(dir, 0o500)`-based write-failure
simulation (doesn't block the owner's own writes on Windows), and
`git checkout -b` with a branch name that's either too long (Windows
MAX_PATH) or contains NTFS-reserved characters (`<`/`>`). Lesson: when a
"failed count" and a "gated count" don't reconcile, grep the WHOLE
directory for the same root-cause pattern before assuming the gap is noise
— it wasn't guesswork, it was 4 more of the same bug the report missed by
scoping to one file.

**Pattern for rewriting a chmod/git-ref-based Windows-incompatible test
into a cross-platform one that still drives real production code (Bex's
"enterprise = no lazy skips" directive, same session):** rule used — skip
ONLY when the property under test is a documented, accepted OS-specific
decision (the 0o600 case above); otherwise monkeypatch at the real IO
boundary and keep exercising the same production function on every
platform. Two concrete techniques, both landed in `test_boot_output.py`:
1. **Write-failure simulation**: replaced `os.chmod(claude_dir, 0o500)`
   with a subprocess helper (`_run_boot_with_failing_log_write()`) that
   loads `hooks/session-start-boot.py` via
   `importlib.util.spec_from_file_location` (module name `'boot'`) and
   overwrites `boot.open_no_follow_symlink` with a function that raises
   `PermissionError` — because `write_boot_log()` imports that name at
   MODULE level (`from git_helpers import open_no_follow_symlink` inside a
   try/except at the top of the file), not as a deferred per-call lookup
   like `run_git`, so the name to patch is on the LOADED HOOK MODULE
   itself, not on `git_helpers`. Then calls `boot.main()` for real — same
   `sys.exit(0)` shape as running the file directly, so
   rc/stdout/stderr match `run_boot()`'s existing shape exactly.
2. **Branch-name edge cases without creating a real ref**: replaced
   `git_cmd(["checkout", "-b", <problem name>], repo)` (fails on Windows
   for both "too long" and "contains `<`/`>`" payloads — MAX_PATH and NTFS
   reserved chars respectively) with `_render_banner_with_branch()`, which
   monkeypatches ONLY the single `git_helpers.run_git(["branch",
   "--show-current"])` call (a passthrough wrapper — every other git
   command still hits the real repo) so `boot_git_checks.render_branch_section()`'s
   real `_resolve_sanitized_branch()` -> `parsing.sanitize_trailer_value()`
   chain runs on the fake string, then feeds the result into the hook's
   real `render_boot_banner_lines()`. This is safe because
   `render_branch_section()`'s implementation does `from git_helpers import
   run_git` as a LOCAL import inside the function body (executed fresh
   every call) — patching the attribute on the real, already-imported
   `git_helpers` module object (`import git_helpers as _gh; _gh.run_git =
   ...`) is picked up regardless of which module re-exports
   `render_branch_section`'s name (boot_render re-exports from
   boot_git_checks; the hook re-exports from boot_render) — the deferred
   import always resolves against the live module in `sys.modules`, not a
   snapshot. Rule of thumb going forward: check whether the name to patch
   is a **module-level bound name on the file defining the function under
   test** (patch that module's own attribute after loading it) vs. a
   **name looked up fresh via a local `from X import Y` inside the
   function body at call time** (patch it on the real `X` module instead,
   regardless of re-export chains) — using the wrong one of these two
   silently exercises the untouched original code path while the test
   stays green, exactly the false-negative already documented above for
   `_write_glossary_cache()`.

**Issue #50 (2026-07-07) — `import bin.X` in test_release.py only worked by
accident of invocation shape; fixed to be cwd-independent.** `test_release.py`
does `import bin.release_helpers` / `import bin.release` inline inside 9 test
methods (T25, T26, T27, and all 6 in `TestPromoteChangelogUnit` via its
shared `_promote()` helper) to reach the git-root `bin/release*.py` modules
(a DIFFERENT `bin/` than `unmassk-toolkit/bin/`'s hyphenated hook scripts —
git-root `bin/` has no hyphens and is a plain namespace package, no
`__init__.py`). This worked when invoked as `python3 -m pytest
unmassk-toolkit/tests -q` from the git root only because `python -m X`
inserts the CURRENT WORKING DIRECTORY into `sys.path[0]` — a side effect of
`-m` invocation, unrelated to pytest's own rootdir logic (the conftest.py
docstring's claim that "pytest añade el rootdir a sys.path" is not actually
what makes this work). Reproduced the failure locally simply by running
pytest from inside `unmassk-toolkit/tests/` instead of the git root:
`ModuleNotFoundError: No module named 'bin'`. This is exactly what breaks on
a CI runner or a bare `pytest` entry point (no `-m`) invoked from any cwd
other than the git root — confirmed as the root cause of the reported
Windows `bin.release_helpers` failures. **Fix**: explicit
`if _REPO_ROOT not in sys.path: sys.path.insert(0, _REPO_ROOT)` right after
`_REPO_ROOT` is computed at the top of `test_release.py`, making the import
correct by construction regardless of invocation cwd/shape. Verified by
re-running the same 9 tests from inside `tests/` (previously failing) — all
pass after the fix, with no change needed to `conftest.py` itself (its
`BIN_DIR` constant only ever pointed at `unmassk-toolkit/bin/`, unrelated to
this git-root `bin/`).

**Issue #50 (2026-07-07) — symlink-setup Windows-skip guard: the "~68 tests"
estimate was exactly right once parametrization is counted.** Before
touching anything, did an exhaustive line-by-line sweep (every
`os.symlink(` and every `_plant_symlink(` call site — the latter is
`test_security_regression.py`'s own local helper that wraps `os.symlink`,
so a call site through it also needs the guard, not just literal
`os.symlink(` lines) across the WHOLE `tests/` directory, mapped each to
its enclosing class/function, and checked whether `real_symlink_capable`
already covered it (class-level `@pytest.mark.usefixtures` or a direct
function parameter). Result: **zero unguarded call sites found** — this
exact fix (fixture promoted to `conftest.py`, applied file-by-file) had
already landed in a PRIOR session the same day (see the "Windows
test-hygiene fix (2026-07-07)" entry above this one) via commits
`543b57b`/`108c6a3`, before issue #50 was handed to me as a fresh task.
Counting actual pytest-collected test items (not just `def test_` lines —
`test_crossplatform_symlink_guard.py`'s two guarded functions are each
`@pytest.mark.parametrize`'d over `TWIN_FUNCS` with 2 entries, so they
collect as 4 items, not 2): 60 (`test_security_regression.py`) + 3
(`test_boot_output.py`, `TestSymlinkWriteProtection` x2 +
`TestGlossaryCacheReadSymlinkProtection` x1) + 1
(`test_boot_freshness_hardening.py`) + 4 (`test_crossplatform_symlink_guard.py`,
parametrized) = **68 exactly**, matching the reported "~68" estimate on the
nose rather than differing from it. Lesson: when a memo/report cites a
prior-session count, verify it's still current by re-deriving it from the
live tree (grep + line-based class/function mapping, cheap and exact)
before assuming either "still needs doing" or "already done" — here it
turned out fully done, and the number itself needed re-deriving with
parametrize multiplication to actually reconcile with the estimate.
(Aside: a naive pytest plugin using `item.fixturenames` to count fixture
usage across the whole suite returned obviously-wrong results — showed
`real_symlink_capable` on totally unrelated tests like
`test_boot_freshness.py` that never reference it. Don't trust
`item.fixturenames` for "does this test use fixture X" without further
verification; static grep + class/function line mapping was the reliable
method here.)

**Issue #50/#51 (2026-07-07) — hermetic-runner git identity: env vars ALWAYS
beat `git config user.name/email`, so a centralized fallback needs repo
tracking to coexist with the dozens of tests that set identity on
purpose.** House root-caused CI failures (35 in `test_boot_output.py` +
more in tombstones/lifecycle/integration/drift) to `git commit` exiting 128
on runners with no git identity anywhere (repro:
`GIT_CONFIG_GLOBAL=/tmp/fakegitconfig GIT_CONFIG_SYSTEM=/dev/null` +
`useConfigOnly = true` in that fake global config) combined with
`run_cmd`/`git_cmd` callers routinely discarding the returned rc — repo
silently ends up with zero commits. Fix landed centrally in
`conftest.py::run_cmd()`: merge a `_DEFAULT_GIT_IDENTITY_ENV` dict
(`GIT_AUTHOR_NAME/EMAIL`, `GIT_COMMITTER_NAME/EMAIL`) as the LOWEST-precedence
layer (`{**identity_defaults, **os.environ, **(env or {})}`), so real
ambient env or an explicit `env=` kwarg (e.g. `test_drift.py`'s
`GIT_AUTHOR_DATE` overrides) still win. **Verified live before writing the
fix** (not assumed): `GIT_AUTHOR_NAME` env always overrides `git config
user.name` regardless of Python dict merge order — confirmed with a throwaway
repo (`git config user.name RepoLocalName` + `GIT_AUTHOR_NAME=EnvName git
commit` → commit author is `EnvName`, config value never used). This means
unconditionally injecting the fallback would have silently overridden every
existing test that deliberately sets its own identity via
`git_cmd(["config", "user.name"/"user.email", ...], repo)` — a pattern used
in DOZENS of call sites across the whole suite (test_boot_output.py's
`_make_repo_no_install`, test_crown.py, test_hardening_recall.py,
test_managed_blocks.py, test_migrate_statusline.py, and more), not just the
one file House named. **Coexistence mechanism**: a module-level
`_REPOS_WITH_EXPLICIT_GIT_IDENTITY` set in conftest.py, populated whenever
`run_cmd` sees an incoming `args == ["git", "config", "user.name"|"user.email",
<value>]` (git_cmd always prepends `"git"`, so this shape is reliable for
every git_cmd caller); once a repo path (`os.path.realpath(cwd)`) is in that
set, the fallback identity is skipped for all later commands in that same
repo, letting the test's own `git config` win exactly as before. Files with
their OWN local `_git()` helper that bypasses conftest's `run_cmd`/`git_cmd`
entirely (`test_boot_freshness.py`, `test_release.py` — both already set
identity explicitly via their own `_git(["config", ...])` calls) are
untouched by this change and were correctly out of scope — grep for `from
conftest import (...)` vs a locally-defined `_git`/`git_cmd` before assuming
a conftest-level fix reaches every test file uniformly. Verified 3 ways:
(1) House's exact repro on `test_boot_output.py` alone: 35 failed → 71
passed; (2) same hermetic env vars on the FULL suite: 984 passed, 2 skipped
(same as baseline, no hermetic-only failures anywhere else); (3) normal
(non-hermetic) full suite unchanged: 984 passed, 2 skipped, 0 failed — no
regression from the new tracking logic.

**Issue #65 (2026-07-11) — Windows-only CI, two more test-hygiene bugs, both
diagnosed by House and fixed test-only (production confirmed correct):**

1. **`open(path, "rb")` raw bytes compared against an in-memory string built
   with bare `"\n"` fails on Windows for a purely cosmetic EOL reason.**
   `hooks/session-start-crew.py`'s text-mode writes translate every `"\n"` it
   emits to `os.linesep` UNIFORMLY on Windows (a genuine, correct CRLF file,
   not a mixed-EOL corruption). A test that reads the result via
   `open(path, "rb")` (to keep a byte-exact channel for marker-count and
   `note.encode("utf-8") in raw_bytes` assertions, which correctly do NOT
   depend on EOL since markers never embed a newline) but then also compares
   that SAME raw string against something LF-built (`_render_block()`'s
   output, or a `prefix` sliced from a `_read()`-based string, which is
   always LF because text-mode reads are universal-newline) fails on Windows
   only. Fix: keep the raw/byte assertions on the raw-decoded string, but
   build a SEPARATE `content_after_text = content_after.replace("\r\n",
   "\n").replace("\r", "\n")` for every STRING/semantic comparison
   (`expected_rendered in ...`, `any_block_outdated(...)`,
   `content_after.startswith(prefix)`, and any later `_read()`-based
   idempotency comparison — same class, easy to miss since it's a second,
   later assertion in the same test). `tests/test_issue63_orphaned_end_preserves_user_content.py`
   was the only file in the suite with this exact shape (grepped every
   `open(..., "rb")` site — the other 4 in the same file and 4 more in
   `test_upgrade_moved_to_sessionstart.py` only do byte-vs-byte equality or
   marker-count/containment checks with no embedded newline, so they were
   correctly left untouched).
2. **`env={"HOME": ...}` alone does not redirect `os.path.expanduser("~")`
   on Windows.** CPython's `ntpath.expanduser()` prefers `USERPROFILE` over
   `HOME` entirely (falls back to `HOMEDRIVE`+`HOMEPATH` only if
   `USERPROFILE` is absent) — a test fixture that only sets `HOME` in the
   subprocess `env=` to redirect a plugin cache lookup (`CACHE_BASE_DIR`
   derived from `expanduser("~")`) silently resolves to the REAL runner
   home on Windows, so the fixture's planted cache tree is never scanned.
   Fix: always set `USERPROFILE` (and `HOMEDRIVE`/`HOMEPATH` for extra
   robustness) alongside `HOME` in any `env=` dict meant to redirect
   `expanduser("~")`. Repo-wide grep for `"HOME"` in `env=` dicts
   (`grep -rn '"HOME"' tests/*.py`) found exactly 2 call sites, both in
   `tests/test_skill_drift_repo_source_detection.py` — both fixed the same
   way. One of the two tests in that file (`TestPureCacheLayoutWithout...`)
   was already passing on non-Windows for the WRONG reason (its
   `CACHE_BASE_DIR` also didn't point at the fixture pre-fix, so it happened
   to see zero drift regardless) — re-verified green post-fix for the
   RIGHT reason by confirming the fixture's planted cache tree is what's
   actually being scanned, not by trusting the pre-fix green as proof.

General grep recipe for this class of Windows-only CI failure, before
assuming a report is exhaustive: `grep -rn 'open(.*"rb")' tests/*.py` (EOL
mismatch) and `grep -rn '"HOME"' tests/*.py` (expanduser redirect gap) —
both are cheap, whole-directory sweeps that catch every instance of the
pattern, not just the one(s) named in the bug report.

**Issues #64/#58 (2026-07-12) — patching a module-level global read at call
time (not a deferred local import) needs only `module.NAME = x` after
import, before calling; and the "derive-the-expected, don't hand-type-it"
rule for a pure ordering function is best satisfied by flipping the
comparison, not by hardcoding the internal tuple shape.**
1. `lib/boot_health.py::check_version_mismatch()` reads `PLUGIN_VERSION`
   as a bare name resolved from its OWN module's globals at call time
   (`from version import VERSION as PLUGIN_VERSION` at the top of
   `boot_health.py`, not a deferred `from version import VERSION` inside
   the function body like `git_helpers`/`upgrade_check` get in this same
   function -- see the module docstring's caching-hazard rationale for why
   those two ARE deferred). To exercise a code-side-unparseable-version
   edge case without touching production code: `import boot_health` for
   real in the isolated subprocess, then `boot_health.PLUGIN_VERSION =
   "not-a-version"` BEFORE calling `boot_health.check_version_mismatch()`
   -- the function's global lookup at call time picks up the patched
   value. (Contrast with the `_write_glossary_cache()` gotcha earlier in
   this file, where the name-to-patch distinction the OTHER way around --
   deferred local imports -- mattered; check which shape applies before
   picking a patch target.)
2. For `bin/release_validators.py::_semver_key()`'s issue #58 fix
   (`ident.isascii() and ident.isdigit()` gating the numeric pre-release
   branch), the useful regression assertion is not "assert the returned
   tuple equals `(1, 0, 0, 0, (1, '１２３'))`" (hand-typing the internal
   branch-tag shape just re-describes the implementation) but "assert
   `_semver_key('1.0.0-１２３') > _semver_key('1.0.0-200')`" -- a full-width
   identifier with a NUMERICALLY SMALLER digit value (123) must still
   outrank an ASCII-numeric identifier with a LARGER value (200), because
   alphanumeric always outranks numeric per semver SS11.4.3 regardless of
   value. This is the exact comparison that flips between the buggy and
   fixed implementation (verified live by simulating the old
   `ident.isdigit()`-only branch inline before writing the test: pre-fix
   `fullwidth > ascii_200` is False, post-fix True) -- a same-value or
   same-direction comparison would pass on both buggy and fixed code and
   prove nothing. General rule for regression-testing a branch-selection
   bug in a pure ordering/comparator function: find (or construct, via a
   throwaway inline simulation of the old logic) the SPECIFIC pair of
   inputs whose relative order is different under old vs. new logic, and
   assert only that relation -- never the internal representation.

**Issue #68 follow-up (2026-07-12) — reconciling a test file after Ultron
retires a whole feature (the skill-search gate) from a hook: the dead test
infra was one CONTIGUOUS block, not scattered.** `test_pre_task_recall.py`
failed to collect (`AttributeError: module 'pre-task-recall' has no
attribute '_SKILL_MARKER'`) because 10 `TestSkillGate*` classes plus their
shared fixtures (in-process hook import via
`importlib.util.spec_from_file_location`, constants read off the hook
module, `_domain_prompt`/`_real_skill_search_top`/etc.) all lived after the
last surviving (memory-injection) class, under one banner comment ("NEW
COVERAGE: skill gate"), straight through EOF — confirmed by grepping every
identifier Bilbo listed and finding zero hits outside that range. When a
feature is fully retired (not just changed), check whether its test
coverage is one contiguous later-added block before doing per-class
surgery — here it meant a single truncation (`head -n <last-good-line>`)
instead of 10 separate deletions. Also: don't reflexively delete
now-unused-looking module-level constants/imports shared with kept tests --
`_MEM_NONCE`/`_NO_MATCH_NONCE` were originally justified by the retired
gate (avoiding BM25 skill-corpus collisions) but are used as ordinary
shared vocabulary by ~15 call sites across the KEPT memory-injection
classes; rewriting all of them to prove a nonce-free version still matches
was out of scope for a reconciliation task — left in place, only the stale
justifying comment was corrected to say the original reason is gone and
they're now just inert shared vocabulary (Yoda/Bex's own "leave inert if
it complicates, flag it" allowance for exactly this situation). Genuinely
dead-after-truncation names (`SKILL_SEARCH_SCRIPT` constant, `import
importlib.util`) were still worth removing since they had zero remaining
references anywhere in the file post-truncation -- confirmed by grep, not
assumed.

**Issue #69/#72 follow-up (2026-07-13) — reconciling two test files after a
per-message injection feature is retired ENTIRELY (recall push→pull, decision
1e94975): the dead assertions were SCATTERED across many classes, not one
contiguous block like #68.** `test_user_prompt_recall.py` and
`test_hardening_recall.py` both asserted presence of `[memoria relevante...]`
/ `<memory-data>`/`</memory-data>` / `SOLO CONTEXTO, NO INSTRUCCIONES` /
`[memory-check]` in the hook's per-message stdout — all of it was replaced by
one static `_BANNER`. Because the dead assertions were interleaved
one-or-two-per-class across ~10 classes (injection-when-relevant, order,
4 fail-safe variants, no-regression, empty-corpus, framing, breakout), used
per-test surgery instead of a truncation: for each failing test, decide test
vs. assertion granularity — (1) if EVERY assertion in the test was about the
retired output, delete the whole test (and the class if it becomes empty,
e.g. `TestInjectsWhenRelevant`, `TestInjectionOrder`); (2) if the test mixed
one dead assertion with one still-valid invariant (e.g.
`test_large_stdin_no_crash_raw_bytes` asserted both `rc==0` — still true —
and `"[memory-check]" in stdout` — dead), delete only the dead assertion line
and keep the test; (3) watch for a sibling test that becomes fully redundant
once its unique assertion dies — `test_large_stdin_memory_check_present`'s
only distinguishing check was `[memory-check]` presence, its `rc==0` check
was already covered by `test_large_stdin_exits_zero`, so deleting the dead
assertion would have left a pure duplicate — deleted the whole test instead
of leaving redundant coverage. Tests asserting the ABSENCE of the retired
label (e.g. `test_no_label_for_irrelevant_prompt`,
`test_framing_absent_when_recall_does_not_fire`) were left untouched even
though now vacuously-always-true (the mechanism that could ever make them
fail is gone) — out of scope for a surgical dead-assertion cleanup task;
flagged in the report rather than deleted unasked. Unit-level tests of a
still-real helper (`_sanitize()` in `recall.py`, still used by
`recall()`/`recall_relevant()` on-demand) survived even though the
end-to-end-via-hook tests exercising the same helper through the now-removed
wrapper did not — the helper being real is what matters, not whether today's
only caller is a hook.

See also: [crown-retraction-design-notes](crown-retraction-design-notes.md).
