---
name: issue-55-date-parsing-contract-notes
description: Issue #55 (%aI + fromisoformat fragile date parsing) test-first contract — sites tested, dead-field exclusion, and a "verify before trusting a stale verdict" finding on the Yoda docstring fleco
metadata:
  type: project
---

**Issue #55, test-first mode (session 2026-07-08).** Six sites share the
`git log --pretty=format:...%aI...` + `datetime.fromisoformat()` +
`except (ValueError, IndexError): return None` shape: `bin/git-memory-gc.py`
(`parse_date()` :70, git log call :88), `bin/git-memory-doctor.py`
(`parse_date()` :84, git log calls :187 and :220), `lib/bootstrap_commits.py`
(git log call :28, no parse_date() at all — raw ISO string stored unparsed).
Contract: migrate all to `%at` (unix epoch) + robust digit parsing, mirroring
`lib/boot_git_checks.py:time_ago()`'s `isdigit()` branch (already the
project's own canonical reference for this exact fix, see
[feat-boot-freshness-contract-notes](feat-boot-freshness-contract-notes.md)'s
"Third regression pass" section). Contract tests:
`unmassk-toolkit/tests/test_date_parsing_epoch_contract.py`, 6 tests, all
confirmed genuinely RED (clean `AssertionError`s, no fixture crashes) against
unmodified HEAD.

**Not tested, with reason: `bin/git-memory-doctor.py:187`
(`check_hook_execution()`'s %aI call).** Read directly before deciding: the
function fetches the 4th `\x1f`-separated field (the date) but never parses
or otherwise consumes it — only `body = parts[2]` is used downstream. No
observable behavior differs whether this field is ISO or epoch today, so no
behavioral RED test can be written for it (would have to assert on the git
log *format string itself*, an implementation detail — forbidden by
Dante's Coverage Boundaries rule). Flagged in the report for Ultron to
migrate anyway, for consistency with the other five sites, not because a
test proves a break there.

**Two test shapes used, both real (no fabricated fixtures):**

1. **`parse_date()` epoch-contract (unit, both gc.py and doctor.py):** build
   a real tmp repo, read the REAL `%at` epoch via
   `git log -1 --pretty=format:%at` (never hand-typed — §34), call the
   duplicated `parse_date()` (loaded via the standard hyphenated-script
   importlib pattern) with that real epoch string, assert it equals
   `datetime.fromtimestamp(int(real_epoch), tz=timezone.utc)` — the exact
   shape `time_ago()` already uses, since the task explicitly named that
   function as the canonical reference ("igual que extract_memory()/
   boot_git_checks.py"). RED today because current `parse_date()` only
   tries `fromisoformat()`, which raises `ValueError` on a bare digit
   string and is swallowed to `None`.
2. **End-to-end degradation via a NEW fake-git technique — "mangle %aI to
   inert literal text":** extends the existing fake-git-on-PATH pattern
   (see [mock-patterns.md](mock-patterns.md)'s "Fake `git` executable on
   PATH" entry) one step further for a *parsing*-failure simulation rather
   than an env/timeout one. The fake script rewrites any `"%aI"` substring
   found inside a `--pretty=format:` arg to inert literal text
   (`"OLDGIT-UNSUPPORTED-DATE-TOKEN"`) BEFORE delegating to the real git
   binary — since that text no longer contains a `%` placeholder, real git
   emits it verbatim, exactly reproducing what an old git release that
   doesn't recognize `%aI` would do (unrecognized directives are emitted
   literally, never expanded). Crucially, `%at` is never touched by this
   rewrite — so once a site migrates to `%at`, the exact same "hostile"
   PATH becomes provably harmless to it, which is what proves the fix
   works, not just that today's code is broken. Used to reproduce two
   real, observable degradations: `bin/git-memory-gc.py`'s H2 heuristic
   (`if not commit["date"]: continue` — a genuinely-stale `Blocker:`,
   backdated via `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` env on a real
   commit, silently stops being flagged) and `bin/git-memory-doctor.py`'s
   `check_gc_status()` (same guard, both its stale-blocker COUNT and its
   "days since last GC" figure collapse to "none"/"never run" instead of
   the real values). Each end-to-end test runs the SAME fixture through
   real git first (setup-sanity assertion, proves the fixture itself is
   valid) before switching PATH to the fake old-git and asserting the
   contract (must still show the real value — RED today).

**Finding, verified but NOT acted on (worth remembering for future "fleco"
tasks): a Yoda verdict citing a stale target can already be resolved by the
time you're handed the task — always re-read the actual file before
editing.** The orchestrator's task described a docstring in
`test_boot_freshness_regression.py` (~line 1021,
`TestTimeAgoOverflowFallsBackSafely`) as still claiming the `isdigit()`
branch in `time_ago()` is dead code. Read the file directly first: the
docstring ALREADY correctly states the branch is now the PRIMARY production
path (not dead code) — confirmed via `git log -p` that this exact wording
landed in commit `72805bc` (same commit that shipped the `%at` migration in
`lib/boot_git_checks.py`'s `get_timeline()`/`get_last_context_time()`),
*before* this session started. A repo-wide grep for `"dead code"` /
`"isdigit() branch"` across `tests/` confirmed no other stale copy exists
anywhere else. No edit was made — editing an already-correct docstring
"because a verdict said so" would have been busywork, not a fix. Always
verify a named target's current content before touching it, especially for
"fleco" (loose-end) tasks handed down from an earlier scoring round — the
codebase may have moved since the verdict was written.

See also: [feat-boot-freshness-contract-notes](feat-boot-freshness-contract-notes.md),
[encoding-contract-notes](encoding-contract-notes.md) (same session family,
same %at/robust-parsing lineage).
