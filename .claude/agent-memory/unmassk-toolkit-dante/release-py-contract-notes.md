---
name: release-py-contract-notes
description: bin/release.py / release_helpers.py / bump-version.py edge cases — semver ordering, CHANGELOG promotion format, date-rollover technique, dry-run guarantees, bump-version retrocompat
metadata:
  type: feedback
---

Rescued 2026-08-25 (memory compaction pass) from `edge-cases.md` — that file
is otherwise obsolete (v1-system + attacker-model content, see this agent's
MEMORY.md Retired section) but this one section targets `bin/release.py`,
`bin/release_helpers.py`, `bin/release_validators.py`, `bin/bump-version.py`
— all four confirmed still on disk and in active use (`CLAUDE.md` itself
cites `python3 bin/release.py <plugin> <versión>` as this repo's own
release-promote step). Content below is unedited from the original
"release.py — Edge Cases (hardening pass, 2026-06-09)" section — nothing
cut, only relocated to a linkable home.

## Semver numeric ordering

`_semver_tuple` converts to `(int, int, int)` — never string-compare versions.
Test: `1.10.0 > 1.9.0` (accepted), `1.9.0 < 1.10.0` (rejected), `2.0.0 > 1.99.99` (accepted).

## CHANGELOG format precision

After promotion: exactly `"\n\n"` between `## [Unreleased]` and `## [<ver>] - <date>`.
Assert `changelog[idx_unreleased + len("## [Unreleased]"):idx_new_ver] == "\n\n"`.
Previous content must appear verbatim under the new heading. Heading date = `date.today().isoformat()`.

## Date-at-import vs date-at-subprocess-invocation rollover (issue #62, fixed 2026-07-11)

A module-level `TODAY = date.today().isoformat()` computed once at test-file
import time WILL diverge from a subprocess-under-test that computes "today"
at its own invocation time, whenever the two moments straddle a (UTC)
midnight — confirmed twice (Yoda locally, CI Windows run 29131458089).
Never hardcode/precompute a date constant for comparison against a live
subprocess write. Fix pattern (no clock mocking needed — less machinery):
capture `date.today().isoformat()` immediately BEFORE and immediately AFTER
the subprocess call, then assert the value written by the subprocess is one
of those 2 candidates — stays strict (exact date, exact heading format), not
relaxed to a substring check. See `_extract_changelog_version_heading()` in
`test_release.py` for the shared regex-based extraction helper used across
all 4 affected tests. General rule: any test asserting a date/timestamp a
subprocess computes independently needs this before/after window, not a
constant computed anywhere earlier in the test process.

## Missing / malformed files

CHANGELOG absent → `_read_file` → `_die` → exit 1, no traceback.
marketplace.json malformed JSON → `_load_json` → `_die` → exit 1, no traceback.
plugin.json absent → `_preflight` check → `_die` → exit 1.
Assert `"Traceback" not in (stdout + stderr)` for all three.

## --dry-run guarantees beyond "no file mutations"

Also assert: `git diff --cached --name-only` is empty (index untouched).
Also assert: local HEAD unchanged (no git object created).
Pre-flight still runs with --dry-run: invalid semver → exit != 0 even with --dry-run.

## bump-version.py retrocompat

Without `UNMASSK_REPO_ROOT`: resolves via `_FILE_ROOT` (`__file__`-relative). Test with `--list` from a tmp CWD that has no marketplace.json — must succeed and show real PLUGIN_NAME.
With `UNMASSK_REPO_ROOT`: uses override root. Test with fake marketplace in tmp_path — must show fake plugin, NOT real plugin.
