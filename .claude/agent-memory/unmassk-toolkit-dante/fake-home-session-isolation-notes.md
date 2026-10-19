---
name: fake-home-session-isolation-notes
description: tests/conftest.py session autouse fake HOME (R.2/R.5, Hito 3) -- why session scope, why mtime not checksum, how to prove it with a sentinel HOME
metadata:
  type: project
---

`tests/conftest.py::_isolated_home` sets HOME + USERPROFILE to a tmp dir for the whole session (2026-10-19, Hito 3 R.2). Covers tests/memory and tests/hooks too (root conftest).

**Why session scope:** a function-scoped autouse fixture is set up AFTER module/session fixtures, so a module fixture that installs would still write the real HOME. `test_fake_home_isolation.py::test_should_give_module_fixtures_the_throwaway_home_too` kills that mutant.

**Checksum is blind here:** the installer rewrites `~/.local/bin/gitmem` unconditionally with identical bytes (cache launcher is a pure function), so sha256 before/after stays equal even when it WAS overwritten. Compare bytes + st_mtime_ns.

**How to prove without touching the real HOME:** run pytest with `HOME=USERPROFILE=<scratchpad>/sentinel_home` holding a `cp -p` of the launcher; mutants in an rsync copy of `unmassk-toolkit/` (no .git needed for these files). `zsh` does not word-split `$FILES`: loop in a bash script.

**Not checkable on macOS:** the USERPROFILE half (Windows expanduser ignores HOME) -- only Windows CI proves it.

Fake HOME also hides `~/.gitconfig` (identity comes from conftest fallbacks, same as CI).
