---
name: issue-57-fence-a2-close-contract-notes
description: Issue #57 close-out round (decisions feed852/79fdf9a, plan docs/plan/fix-fence-a2-close-57.md) — \r transport forgery, ReDoS in _strip_generic_tags, LOW-17 unclosed-fence truncation, A2 nonce infalsifiability. All 4 areas RED, test-first, zero prior coverage.
metadata:
  type: feedback
---

Extends [issue-57-round2e-fence-invariant-contract-notes](issue-57-round2e-fence-invariant-contract-notes.md).
That round closed the sanitizer's own denylist class structurally. This
round is 4 unrelated areas Bilbo mapped as having ZERO existing coverage
in `tests/test_control_byte_injection.py` (PART S added, ~430 new lines,
13 new tests: 8 RED + 5 GUARD). Confirmed via scoped `pytest -k` run:
exactly 8 failed / 5 passed on the new classes, full-file run 167 items
(154 pre-existing + 13 new): 8 failed, 159 passed — 0 regressions.

## (a) `\r`→`\n` subprocess transport forgery — must use a REAL subprocess round-trip, never in-memory strings

`lib/git_helpers.py:run_git()` and `bin/git-memory-log.py`'s own inline
`subprocess.run(...)` both use `text=True` with NO `newline=` kwarg —
Python's universal-newlines decoding silently converts every `\r` in the
child's stdout bytes to `\n` **before any Python code sees the string**.
Confirmed empirically (2026-07-10, real repo, real `git commit`, real
`run_git()` call — no hand-built string ever stood in for git's output,
per §34): a body `"Decision: real text\rMemo: FORGED"` round-tripped
through `run_git(["log","-1","--pretty=format:%b"])` comes back as
`"Decision: real text\nMemo: FORGED"` — `scan_trailers_memory()` then
parses BOTH as genuine trailers. Verified the corruption is NOT in git's
own storage: `git cat-file -p HEAD` (subprocess with `text=False`, raw
bytes, zero decoding) shows the literal `0x0D` intact and no real `0x0A`
before "Memo:" — the bug is strictly in the Python-side subprocess decode
boundary. This is why an in-memory string test (build the "post-transport"
string by hand in Python and feed it to `scan_trailers_memory()`) would
NEVER have caught this: the bug lives exactly at the seam between the
child process's raw bytes and Python's decoded string, invisible to any
test that starts from an already-decoded Python literal.

Second, independent site: `bin/git-memory-log.py:65-68` has its own
separate `subprocess.run(..., text=True)` call (does not go through
`run_git()` at all) that reads `git log --pretty=format:"%h %s"`. A raw
`\r` mid-subject splits ONE real "sha subject" line into two once
translated to `\n` — the second fragment has no real sha prefix, so
`sha = line[:7]` manufactures a phantom sha from attacker text and
`git-memory-log.py` renders a fabricated extra commit entry
indistinguishable in format from a real one. Confirmed live: subject
`"feat(x): real message part1\rZZFAKESHA phantom forged part2"` renders
as TWO lines, the second `"[ZZFAKES] A phantom forged part2"`.

**Test design for a fabricated-phantom-entry assertion**: don't try to
count "total rendered lines" (fragile — every code path wraps `[sha]` in
ANSI codes at different line positions depending on which branch fires).
Instead pick a payload whose fragment-2 prefix is a KNOWN, distinctive
literal (`"ZZFAKESHA..."` so `fragment[:7] == "ZZFAKES"`), and assert the
literal bracketed marker `"[ZZFAKES]"` is absent from stdout — precise
regardless of ANSI wrapping, since `f"[{sha}]"` puts the brackets directly
adjacent to the literal sha string in every branch.

## Windows `subprocess.run([..., "-c", huge_literal])` hits the ~32K command-line length limit

An early draft embedded a 120,000-char hostile payload directly as a
Python literal inside a `-c` script string passed to `subprocess.run()`.
On Windows, `CreateProcess`'s command-line length ceiling (~32,767 chars)
is blown by any payload approaching that size embedded in argv. Fix: write
the payload to a `tmp_path` file first, have the `-c` script `open()` and
`read()` it — keeps the actual subprocess argv short regardless of payload
size. Relevant for any future large-payload subprocess test on Windows.

## (b) `_strip_generic_tags` is genuinely O(n²), not classic exponential ReDoS — verify empirically before assuming "no catastrophic backtracking = safe"

`lib/bootstrap_commits.py:_GENERIC_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")`
uses a negated character class (`[^>]*`), which has NO catastrophic
(exponential) backtracking risk — a naive "is this ReDoS-vulnerable"
static read would conclude "safe." Empirically wrong: measured directly
(2026-07-10, this machine) — `"<a" * 200000` (400,000 chars, all
unmatched `<a` openers, zero `>` anywhere) took **~41 seconds**; `"<a" *
60000` (120,000 chars) took **~4.2s / ~3.4s** (variance across runs).
Root cause: for EVERY one of the ~200,000 `<letter` start positions in
the string, the regex engine must scan `[^>]*` all the way to the end of
the remaining string before concluding there's no closing `>` to match —
O(n) work repeated from O(n) start positions = O(n²), not O(n). A
git commit subject has no length cap anywhere in this codebase, making
this a real, reachable DoS via `git memory bootstrap --json` against a
large hostile subject. Lesson: don't skip empirical timing verification
for a regex just because its pattern shape isn't the textbook
`(a+)+`-style catastrophic-backtracking case — negated-class scans can
still be quadratic and just as exploitable in practice.

**Test technique**: the regex engine holds the GIL for the whole scan —
an in-process call with `signal.alarm` or `threading.Timer` CANNOT
interrupt a hung/slow `re.sub()` call. Must isolate in a real subprocess
with `subprocess.run(..., timeout=N)` so `subprocess.TimeoutExpired` gives
a clean, prompt test failure instead of hanging pytest itself for the
full multi-second (or worse) blowup. Picked payload size (60,000 reps,
120,000 chars, ~3-4s today) deliberately smaller than the demonstrably
even-worse 400K-char/41s case, to keep the RED test's own runtime
reasonable while still clearing the 2.0s bound comfortably. Timing
assertions here are NOT the "tight Date.now margins" flakiness the Hard
Rules warn about — a generous multi-second-vs-milliseconds gap for a
genuine algorithmic-complexity bug is a standard, non-flaky technique,
distinct from asserting on race-condition-prone tight windows.

## (c) LOW-17 — a truncation fix and a fence-regex fix can each be individually correct and still combine into a gap

`lib/parsing.py:scan_trailers_memory()` truncates each line at the FIRST
`\x1c`/`\x1d`/`\x1e` found (root-fix round's closing of the phantom-line
forgery class — see
[issue-57-root-fix-subject-vector-contract-notes](issue-57-root-fix-subject-vector-contract-notes.md)).
`sanitize_trailer_value()`'s fence regex (round 2e's
`<\s*/?\s*memory-data\s*>`) REQUIRES a literal closing `>` to match (see
[issue-57-round2e-fence-invariant-contract-notes](issue-57-round2e-fence-invariant-contract-notes.md)).
Individually both are correct fixes for what they targeted. But if the
control byte sits INSIDE `</memory-data...>` immediately before the `>`,
truncation discards the byte AND the `>` together — the returned trailer
value ends in an unclosed `</memory-data` prefix that the fence regex
(needing that `>`) structurally cannot catch, no matter how
whitespace-tolerant it is. Confirmed empirically for all three bytes
(`\x1c`/`\x1d`/`\x1e`) at the unit level (`scan_trailers_memory()` ->
`sanitize_trailer_value()`) and end-to-end via `recall_relevant()`.

**New regex needed, not reuse of `_FENCE_SHAPE_RE`**: existing
`_FENCE_SHAPE_RE`/`_FENCE_CLOSE_ONLY_RE` (already in this file, round 2e)
both require the closing `>` and therefore cannot detect this unclosed
variant either — added `_FENCE_PREFIX_RE = re.compile(r"<\s*/\s*memory-data\b",
re.IGNORECASE)` (no `>` required at all) specifically for LOW-17. Paired
with a GUARD proving the assertion mechanism isn't vacuously tripped by
ordinary (non-fence-adjacent) control-byte truncation — same discipline
as every other round in this file.

## (d) A2 nonce infalsifiability — the only implementation-agnostic test is cross-invocation byte-diff over unchanged state

Decision `feed852` (Bex, "lo mas enterprise"): fix is a per-invocation
UNPREDICTABLE token woven into `hooks/user-prompt-memory-check.py`'s
`<memory-data>` fence, closing the class at the root rather than
continuing the denylist-patching Bex explicitly told the team to stop
(`f888056`). At acceptance-contract time (before Ultron picks exact
nonce shape/placement — attribute? suffix? open tag only? both tags?),
the ONLY assertion guaranteed to hold post-fix regardless of that choice
is: **two real hook invocations, over IDENTICAL repo state and an
IDENTICAL prompt, must stop producing byte-identical stdout.** Confirmed
empirically (2026-07-10) this is currently FALSE — two consecutive real
subprocess invocations of the hook produce 100% byte-identical stdout
today (recall content is itself deterministic given fixed git state, so
nothing else in the hook's output varies run-to-run either — verified
this holds before relying on it).

**Deliberately did NOT write** a companion test asserting a specific
hardcoded literal (e.g. today's exact `"<memory-data>\n"` substring)
disappears from stdout post-fix — that would silently assume the nonce
lands inside/adjacent to the OPEN tag specifically. A valid fix that only
nonces the CLOSE tag (`</memory-data-<nonce>>`) would leave that
hardcoded open-side literal fully intact and pass, while the actual
per-invocation-uniqueness property the decision requires would still be
satisfied by the close-tag nonce alone — a hardcoded-substring test would
then be a false negative masquerading as a stricter check. This is the
same "assert the invariant, not the byte/format" lesson from round 2e,
applied to fence PLACEMENT instead of fence BYTES — reread that round's
notes before writing any new fence-shaped assertion.

## Follow-up (issue #59, 2026-07-10) — the (a) `\r` forgery fix landed; 8 stale-contract tests needed mock/assertion updates, not behavior changes

Ultron's fix for (a) above: `lib/git_helpers.py:run_git()` (~L455-488)
dropped `text=True`/`encoding="utf-8"` from the `subprocess.Popen(...)`
call entirely — `proc.communicate()` now returns raw BYTES, decoded
manually via `stdout_bytes.decode("utf-8")` / `stderr_bytes.decode("utf-8")`,
which (unlike `text=True`'s universal-newlines mode) performs NO newline
translation, so a real `\r` survives untouched. This broke 8 tests that
mocked the OLD contract, not because the fix was wrong:

- `test_boot_freshness_hardening.py::TestRunGitLogStderrOnFailure` (7
  tests) — its `_FakeProc.communicate()` returned `self._stdout`/
  `self._stderr` as `str`; `run_git`'s new `.decode("utf-8")` call then
  raised `AttributeError: 'str' object has no attribute 'decode'`. Fix:
  the fake now returns `self._stdout.encode("utf-8")` /
  `self._stderr.encode("utf-8")` — mimicking what a real `Popen` without
  `text=True` actually returns. Zero change to what each of the 7 tests
  asserts (stderr breadcrumb only on genuine failure, truncated to 300,
  silent on success/empty/whitespace/flag-false).
- `test_crossplatform_symlink_guard_hardening.py::TestRunGitEncodingUtf8::test_run_git_passes_encoding_utf8_and_text_true_to_subprocess`
  — asserted `calls[0].get("encoding") == "utf-8"` and
  `calls[0].get("text") is True`, both now permanently false by design.
  Renamed to `test_run_git_captures_bytes_and_decodes_utf8_without_newline_translation`
  and rewrote to assert the NEW contract: `"text" not in calls[0]` and
  `"encoding" not in calls[0]` (Popen called without either kwarg), plus
  a round-trip payload (`"línea-uno\rlínea-dos\n"`, encoded to bytes for
  the fake `communicate()`) proving BOTH the accented-UTF-8 decode still
  works AND the literal `\r` survives untranslated in the returned
  string (`out == payload.strip()`, `"\r" in out`) — this is the actual
  regression guard for the (a) `\r`-forgery bug this whole entry is
  about, now living as a fast in-memory mock test instead of only the
  slower real-subprocess round-trip test already in this same class
  (`test_run_git_round_trips_utf8_accents_and_emoji_through_real_git`).

**Lesson reinforced**: when a production fix intentionally changes a
`Popen`/`subprocess.run` kwarg contract, grep the WHOLE test tree for
mocks/assertions pinned to the OLD kwargs before declaring the fix
done — `git_helpers.run_git` had exactly 2 test files mocking
`subprocess.Popen` directly (not `run_git` itself), and both needed
touching even though only one was the "obvious" round-trip test file.
Confirmed no other `subprocess.Popen`/`subprocess.run` mock in the tree
asserted `text=True`/`encoding=` against `run_git` specifically (checked
via grep for `"text") is True` and `.get("encoding")` across
`unmassk-toolkit/tests/`) — these were the only 2 files, matching the
task's exact 8-test scope. Full suite re-run after: unchanged pass count
outside the 8 fixed (no other collateral breakage from the Popen
contract change).

## Verification discipline this round

Every RED (all 4 areas, 8 test functions/parametrizations) was
empirically reproduced live in a scratch script against the REAL,
unmodified current code BEFORE being written into the test file — the
`\r` transport bug via a real tmp git repo + real `run_git()` +
`git cat-file -p HEAD` ground-truth check; the ReDoS via direct timing
measurements at 3 payload sizes; LOW-17 via direct
`scan_trailers_memory()`/`sanitize_trailer_value()` calls; the nonce gap
via two real consecutive hook subprocess invocations diffed byte-for-byte.
Confirmed via scoped `pytest -k` (13/167 collected, 8 failed/5 passed
exactly as predicted from the scratch repros) and a full-file run (167
items: 8 failed, 159 passed, 0 regressions in the 154 pre-existing
tests).
