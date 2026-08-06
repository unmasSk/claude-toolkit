---
name: customs-doctor-20260806-two-red-contracts-notes
description: Two test-first RED contracts closed same day - customs.py shlex-failure rescue passthrough (Moriarty PoC), doctor check_project_config type validation. Set-iteration-order pitfall discovered.
metadata:
  type: project
---

2026-08-06, orchestrator dispatched two contracts test-first (tests only, Ultron
fixed in parallel — both landed green same session, no red survived to close-out):

1. `hooks/customs.py::_find_commit_creating_statement()` — its `except ValueError`
   fallback (shlex fails on an unescaped apostrophe earlier in the bash line) used
   to `return sub, []`, discarding all tokens, so `--abort`/`--continue`/`--skip`
   became invisible to `_decide_rescue_passthrough()`. Fixed by scanning the raw
   text for the three rescue flags via `_RESCUE_FLAG_RE` and prioritizing
   `rebase`/`merge`/`cherry-pick` in the subcommand-detection order when a rescue
   flag is present in the text.
2. `bin/git-memory-doctor.py::check_project_config()` only checked that `repo_type`
   existed, never validated the TYPE of `customs_enabled`/`repo_type`/`test_command`
   — a mistyped config.json (e.g. `"customs_enabled": "true"` as a string) made
   `config.py::load()` raise (blocking every commit via the customs hook) while the
   doctor reported "ok". Fixed by replicating `config.py::load()`'s per-field type
   contract locally (same no-import-lib/memory pattern `check_project_zones()`
   already used for zones.json).

**Reusable finding — non-determinism from `for x in a_set:` early-return fallbacks.**
`_COMMIT_CREATING_SUBCOMMANDS` is a plain `set`. With `PYTHONHASHSEED` unset (this
repo's default), the iteration order of a set of short ASCII strings varies **per
process** — confirmed live, 5 separate `python3 -c` invocations gave 2 different
orderings. Any code that does `for x in some_set: ... return` on a decision path
carries this same silent nondeterminism unless the set is ordered (tuple) or the
loop is order-independent. Worth grepping for this shape (`for .+ in .+_SET` /
`for .+ in \{`) if a similar "sometimes green, sometimes red" report surfaces
elsewhere in the toolkit — it looks like test flakiness but is actually a real
bug in the code under test, not the test.

See [[dante-owner-metric-over-allowlist-feedback]] for a related owner-preference
note (computed metrics over hand-written allowlists) — same "derive, don't
hardcode" instinct applies to fixing subcommand-priority order too (Ultron's fix
derives priority from the presence of rescue flags in the raw text, not a
hand-picked constant order).
