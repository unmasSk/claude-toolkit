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
`lib/boot_memory.py:_write_glossary_cache()`) do `try: from git_helpers
import ensure_runtime_dir; except ImportError: ensure_runtime_dir = None`
at module level, then branch on that name at call time. To exercise the
`else` fallback branch in a test, do NOT stub `sys.modules["git_helpers"]`
(that risks breaking sibling module-level imports and needs careful
restore/whitelist bookkeeping, see the `_extract_memory()` gotcha above) —
instead load the target module normally via the importlib
spec_from_file_location pattern (real git_helpers, real import succeeds),
then simply overwrite the already-bound name on the loaded module object:
`mod.ensure_runtime_dir = None`. This forces the fallback branch on the next
call while every other dependency (boot_memory/boot_migrations/boot_render/
version) keeps using the real git_helpers. Always do this inside a
subprocess (`import sys, os, json, importlib.util; ...; print(json.dumps(...))`,
same pattern as every other importlib probe in test_security_regression.py),
not in-process, since these are real stably-named modules and an in-process
load risks sys.modules contamination across test files in the same pytest
session (see Round 4 in
[boot-stdout-banner-contract-notes](boot-stdout-banner-contract-notes.md)).

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

See also: [crown-retraction-design-notes](crown-retraction-design-notes.md).
