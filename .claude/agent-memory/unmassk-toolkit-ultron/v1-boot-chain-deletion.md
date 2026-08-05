---
name: v1-boot-chain-deletion
description: Deleting deprecated v1 memory-boot files in claude-toolkit — how to tell a real live caller from an installer/repair cleanup list false positive
metadata:
  type: project
---

2026-08-05: deleted the v1 boot chain (`hooks/session-start-boot.py`,
`hooks/pre-validate-commit-trailers.py`, `hooks/stop-dod-check.py`,
`bin/git-memory-commit.py`, `lib/boot_checks.py`, `lib/boot_git_checks.py`,
`lib/boot_render.py`, `lib/boot_migrations.py`) after v2 (`boot_launcher.py`)
replaced it and it was unplugged from `hooks/hooks.json`. Reduced
`lib/boot_health.py` from 333 lines to the 3 symbols `lib/cache_sync_check.py`
still imports (`CACHE_BASE_DIR`, `_latest_version_dir`, `_md5_file`); dropped
`REPO_BASE_DIR`, `_is_real_repo_source()`, `_build_repo_skill_index()`,
`check_skill_drift()`, `check_version_mismatch()`, `run_doctor()`,
`run_repair()` — zero callers left once the v1 chain was gone.

**False-positive trap when grepping for "live callers" of a deprecated
filename in this repo:** `lib/install_inspect.py`'s `OLD_HOOK_FILES` list and
`bin/git-memory-repair.py`'s `old_files` list both hardcode filenames like
`"hooks/session-start-boot.py"` as strings. These are NOT imports of the
toolkit's own source files — they're lists of v1-era leftover filenames that
the installer/repair script checks for **inside a target project's root**
(a different repo entirely) to clean up stale copies from an old-style
install. Read the surrounding docstring before treating a string-literal
filename match as a real caller; `install_inspect.py`'s own docstring says
it plainly ("These were copied by the v1 installer but should only live in
the plugin cache"). Confirmed safe to leave untouched when deleting the
files these lists name.

**Unidirectional-DAG docstrings pay off.** `boot_checks.py`'s and
`boot_health.py`'s own docstrings both stated the DAG direction explicitly
("boot_health/boot_git_checks <- boot_checks <- boot_render", "this module
must never be imported FROM either of the two modules it re-exports from")
— that's what let me delete `boot_checks.py` and its siblings without
reading every line of `boot_health.py` first to prove it was safe. Trust but
verify: still grepped repo-wide for the departing symbol names
(`check_skill_drift`, `run_doctor`, etc.) to confirm zero surviving callers
before cutting, since a docstring can go stale.

See also [[lessons.md]] for other git-safety-relevant lessons in this repo
(none of those applied here — this task involved rm only, no git commands).
