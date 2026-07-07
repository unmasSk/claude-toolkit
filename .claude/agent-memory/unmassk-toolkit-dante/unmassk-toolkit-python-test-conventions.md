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

See also: [crown-retraction-design-notes](crown-retraction-design-notes.md).
