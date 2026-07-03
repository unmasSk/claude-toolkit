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

See also: [crown-retraction-design-notes](crown-retraction-design-notes.md).
