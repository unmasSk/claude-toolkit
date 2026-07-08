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

**Adversarial round (Argus + Moriarty) follow-up, same session — 5 more
bugs on the %at-migrated code, test-first.** Added to the same file
(`test_date_parsing_epoch_contract.py`), 6 new classes / 11 new test
functions, 6 confirmed genuinely RED (clean `AssertionError`s or a clean
uncaught `AttributeError` for the right reason), 1 class (5+1 tests)
honestly GREEN and documented as such rather than faked red:
- **BUG-1** (`AttributeError` on non-string `parse_date()` input —
  `None`/`int`/`list`): the except tuple
  (`ValueError, TypeError, OSError, OverflowError`) never included
  `AttributeError`, so `date_str.isdigit()` crashes instead of degrading
  to `None` per the docstring. RED via uncaught `AttributeError` at
  `lib/date_parsing.py:27`, not a mere `AssertionError` — right-reason
  confirmed by reading the actual traceback, not assumed.
- **BUG-2** (no explicit length guard before `int()`): verified live
  (not assumed) that on this runtime (CPython 3.14, default
  `sys.get_int_max_str_digits()==4300`) an oversized digit string ALREADY
  returns `None` today via two accidental, stacking safety nets —
  CPython's own int-string-conversion limit (`ValueError` above 4300
  digits) and, independently (confirmed by temporarily calling
  `sys.set_int_max_str_digits(0)`), `datetime.fromtimestamp()`'s
  `OverflowError` for any epoch outside its representable range. Wrote
  the test as the CONTRACT (`len>20 → None`) anyway per the task's
  explicit instruction to be honest rather than fake red — it is GREEN
  today, documented in the class docstring as testing "accidental
  behavior already matching the intended explicit contract," not a
  currently-proven bug. Stays green unchanged once Ultron adds a real
  upfront guard; gains real teeth if either accidental safety net is ever
  weakened.
- **BUG-3** (`bootstrap_commits.py`'s `--json` "date" field is a raw
  epoch digit string, not presentable): expected value derived from
  `git log -1 --pretty=format:%at` on the real fixture repo (§34 — never
  hand-typed), asserted equal to the actual `--json` field first (setup
  sanity proving it's the same commit) THEN asserted `not
  got_date.isdigit()` — the real, minimal, non-speculative assertion of
  "not presentable," since the eventual readable format Ultron picks is
  unknown and shouldn't be pre-guessed/hand-typed.
- **BUG-4 & BUG-5** (`bin/git-memory-doctor.py::check_gc_status()`,
  overflow-future / negative-days): both reproduced LIVE via bash before
  writing the test (not assumed from reading code) — a real,
  `git fsck --full` rc=0-clean commit with
  `GIT_AUTHOR_DATE="@253402300800 +0000"` (one second past
  `datetime.max`) produces `parse_date()==None` (caught `ValueError:
  year must be in 1..9999, not 10000`), and doctor.py's `--json` GC check
  message is then BYTE-FOR-BYTE `"never run"` — identical to a repo with
  genuinely zero GC commits. Test proves the contract violation by
  comparing against a same-shape zero-commits baseline (asserted as
  setup sanity to actually say "never run" — proving what "never run"
  is SUPPOSED to mean) rather than hand-guessing what Ultron's fix
  message should say. BUG-5: a real fsck-clean commit dated exactly
  `now + 365 days` (still within `datetime`'s representable range, so
  `parse_date()` returns a real, valid, future datetime — no exception
  path involved at all) makes line ~266's unclamped
  `(now - last_gc).days` go negative; live repro showed the exact string
  `"last run -365 days ago"`. Assertion is a regex
  (`-\d+\s*days?\s*ago` must NOT match) rather than a hand-typed exact
  message, since Ultron's clamp-vs-distinct-message choice isn't fixed
  yet — same "define the contract, don't pre-guess the wording"
  discipline as BUG-4.
- All 6 new RED tests reproduced live via raw bash/python BEFORE being
  encoded as pytest assertions (both the `sys.set_int_max_str_digits`
  probe for BUG-2 and the two `git commit --allow-empty` + `git fsck
  --full` + `doctor.py --json` repros for BUG-4/BUG-5) — never assumed
  from reading the source alone. Confirmed deterministic by running the
  new/edited file twice: identical 6 failed / 16 passed both times, same
  test IDs.

See also: [feat-boot-freshness-contract-notes](feat-boot-freshness-contract-notes.md),
[encoding-contract-notes](encoding-contract-notes.md) (same session family,
same %at/robust-parsing lineage).

**Cerberus follow-up, same session (1 suggestion, micro-encargo, review
mode not test-first): the ISO-8601 fallback branch inside both
`parse_date()`s had no direct coverage.** After Ultron's parallel fix
widened the except tuple to `(ValueError, TypeError, OSError,
OverflowError)`, the fallback branch itself (`fromisoformat()` +
`if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)`) is
unreachable from any in-repo caller (all now emit `%at`) but kept for
external/legacy callers — a silent regression risk if someone deletes the
`.replace(tzinfo=...)` line later (naive/aware mixing). Added
`test_parse_date_iso_fallback_stays_tz_aware` (parametrized, 2 cases: naive
ISO → asserts `result.tzinfo == timezone.utc`; ISO-with-offset → asserts
equality against `datetime.fromisoformat()` of the same string, preserving
the original offset) to both `TestGcParseDateEpochContract` and
`TestDoctorParseDateEpochContract`. Expected values built via
`datetime.fromisoformat()` in the test file itself, never hand-typed
(§34) — the only manual step is `.replace(tzinfo=timezone.utc)` for the
naive case, which mirrors production's own naive-defaults-to-UTC semantic
rather than re-deriving parse_date()'s actual logic. Suite now 10/10 green
(6 pre-existing + 4 new). No conditional logic needed in the test body:
both cases share one assertion shape by passing `expected` and
`expected_tzinfo` as separate parametrize columns instead of branching
inside the test.
