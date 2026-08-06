---
name: stop-dod-gate-corrupt-config-contract-notes
description: stop-dod-gate.py RED contract (2026-08-06) -- corrupt config.json must warn, distinct from not-configured silence; plus a same-day config-path drift found and fixed in the pre-existing test file
metadata:
  type: project
---

Task: write-only RED contract for `hooks/stop-dod-gate.py`
(`_read_test_command()`), owner-reported gap. `except (OSError,
json.JSONDecodeError): return None` makes a CORRUPT `config.json`
(invalid JSON, or unreadable e.g. a directory at that path) produce the
exact same silent exit-0 as a config.json that simply never declared
`test_command` (valid opt-out). Per this project's threat model ("the
system against itself", not an attacker) that's the forbidden shape: a
failure passing with zero signal. The opt-out case is correct and must
stay silent -- only the corrupt case must start warning (stderr or any
visible channel), while staying fail-open (never blocks close).

**Found and fixed in the same pass: the test file itself had gone
stale.** `tests/test_stop_dod_gate.py`'s `_write_config()` wrote to
`.claude/git-memory-config.json` (old system). The hook's own
`CONFIG_SUBPATH` comment says it moved to
`.claude/project-memory/config.json` *the same day* (2026-08-06) as the
last live consumer of the old file. Result: 4 of the file's 21 tests
(all of `TestCommandFailsBlocks`) had been silently red-for-the-wrong-reason
-- the fixture wrote a config the hook never reads, so the hook always
took the "no test_command" branch and never exercised the block path at
all. Confirmed by running the suite before touching anything: `4 failed,
17 passed`. Fixed the path in `_write_config()` (new helper
`_write_raw_config()` added alongside it for non-JSON content) + the
docstring, with a dated `[corregido 2026-08-06: ...]` annotation
explaining what was wrong and why, per
[[test-file-self-drift-correction-notes]]. After the fix: `21 passed`.
Then added the new contract on top of a now-correct baseline.

**Empirical repro before writing assertions (own convention, followed
here):** ran the hook by hand via subprocess against a temp dir with
`.claude/project-memory/config.json` containing `{ INVALID JSON }` --
confirmed `rc=0, stdout='', stderr=''`. Same empirical check for the
"not configured" baseline (valid JSON, no `test_command` key) -- also
`rc=0, stdout='', stderr=''`, proving the two cases are indistinguishable
today. Also confirmed cross-platform validity of a *second* repro for
the corrupt case (`config.json` as a directory instead of a file):
on Windows `open(dir_path, "r")` raises `PermissionError`, a subclass of
`OSError` -- same swallow path as `json.JSONDecodeError`, so it is a real
second instance of the same gap, not a cosmetic variant.

**Final RED state:** `tests/test_stop_dod_gate.py` -- 27 tests total, 23
green / 4 red. New classes: `TestNoCommandStaysSilent` (2 tests, green --
pins the correct silent baseline explicitly, including stdout/stderr
emptiness which no prior test in the file asserted) and
`TestCorruptConfigMustWarn` (4 tests, red for the right reason -- all
fail on `assert stderr.strip() != ""` or the direct
stderr-corrupt-vs-stderr-not-configured differs assertion). Did not touch
`hooks/stop-dod-gate.py` or `lib/memory/config.py` -- Ultron's task is to
make `_read_test_command()` distinguish the two cases (e.g. re-raise or
log on `json.JSONDecodeError`/`OSError` specifically instead of
swallowing both into `None`), keeping fail-open (rc always 0, never
blocks) intact.

Reference: [[test-file-self-drift-correction-notes]] (same drift shape:
prose/fixture referencing a path/name the production code moved away
from, caught only by re-running against current code, not by trusting
the file's own green history).
