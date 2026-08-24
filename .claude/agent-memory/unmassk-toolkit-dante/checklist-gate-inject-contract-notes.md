---
name: checklist-gate-inject-contract-notes
description: casillas-por-programa D-052 hooks (skill-checklist-inject.py/checklist-gate.py) contract, real schema vs guessed schema, tests/hooks/ new directory conventions
metadata:
  type: feedback
---

Test-first contract for `hooks/skill-checklist-inject.py` (PostToolUse on
`Skill`) and `hooks/checklist-gate.py` (Stop), docs/plan/casillas-por-programa.md
(D-052). Ultron implemented both **in parallel** while the contract was
being written (the task said so explicitly) — by the time I finished the
first draft, the real hooks already existed with a schema I had guessed
differently. Rewrote to match the verified code, per the "confirm the
change is intentional, align the assertion, preserve original intent"
rule.

**Real schema (verified by reading code, not guessed):**
- Manifest: `checklists/<basename>.json` (basename drops `unmassk-`
  prefix), `{"skill": "...", "boxes": [...]}` — key is `boxes`, not
  `checklist`.
- Session registry (`lib/checklist_state.py`,
  `<project_root>/.claude/.unmassk/session-checklists/<session_id>.json`):
  `{"session_id": "...", "skills": [{"skill": "...", "boxes": [...]}],
  "block_count": N}` — a LIST of skills (a session can load more than
  one process skill), not a single flat `{"skill", "checklist"}`.
- Board dir: `(CLAUDE_CONFIG_DIR or ~/.claude)/tasks/
  (CLAUDE_CODE_TASK_LIST_ID or session_id)/`.
- additionalContext lives under `hookSpecificOutput.additionalContext`
  (not root-level) for PostToolUse.

**A corrupt task file is NOT a "can't decide, fail open" case.** I first
assumed (before reading the code) that a corrupt task file covering the
only info about an expected box would make the gate pass with a warning
("can't be sure, so don't block"). The real code treats it exactly like
an absent file: the box counts as **missing**, which blocks normally
(with a stderr note listing which files were unreadable). The fail-open
("never block") path is reserved for SYSTEM-level failures only: corrupt
registry, corrupt stdin, absent board directory, uncaught exception — not
per-file task corruption. Verified by reading `_read_board_tasks`/
`_violations` directly: a broken filename never enters the `tasks` dict,
and `_violations` has no separate "uncertain" state.

**Static source-scan false positive**: a naive `"subprocess" in source`
substring check to verify "this hook launches no subprocess" (protection
8) false-positives on the hook's OWN docstring/comment ("no subprocess, no
git call") — the file mentions the forbidden word to declare it doesn't
do it. Fixed with regex patterns anchored to actual call/import syntax
(`\bsubprocess\.\w+\(`, `\bimport\s+subprocess\b`, `\bPopen\(`, etc.),
never the bare word.

**New `tests/hooks/` directory — module collision with root `tests/conftest.py`.**
Both `tests/conftest.py` and `tests/hooks/conftest.py` register as
`sys.modules['conftest']` when neither the new dir nor its files are a
proper package — breaks the ENTIRE suite (32 collection errors on
unrelated files importing from the root conftest). Fix: give the new
subdirectory an `__init__.py` (same pattern `tests/memory/` already
uses) and use relative imports (`from .conftest import ...`) inside its
test files instead of flat `from conftest import ...`. Always check for
this before adding ANY new test subdirectory with its own conftest.py —
run the FULL suite (`python3 -m pytest unmassk-toolkit/tests -q`, no
`--ignore`), not just the new directory, before calling a test-first
contract pass done.

**Manifest fixtures written into the REAL `checklists/` dir at test time.**
The hook resolves manifests relative to its own `__file__` (sibling of
`hooks/`), not a parametrizable path — no way to redirect it to a tmp dir
without dictating an internal decision. Fixtures create/delete files
there per-test with a uuid-suffixed skill name (never a real production
name like `unmassk-flow`) and guaranteed cleanup (`yield` + `finally`),
verified afterward that `git status` shows the dir empty of stray files.

**Hardening round (2026-08-24, same day) — Cerberus/Argus findings, 6 scenarios, all found GREEN.**
Coordinator asked for 6 more tests after Cerberus/Argus review; by the
time each was written Ultron had already fixed all of it in parallel
(verified reading the live files immediately before each test, not from
memory): `checklist_state.locked()` (new, wraps `file_lock()`) closes the
inject-race (two skills registering concurrently used to lose one
entry); `is_safe_path_component()` (new) rejects a `session_id`
containing `/`, `\`, or `..` before it becomes a path component (a
`"foo/../../bar"` session_id used to silently write
`.claude/.unmassk/bar.json`, one level OUTSIDE `session-checklists/`,
because `verify_path_within_project()` only guards against escaping the
project root, not the specific intended subdirectory); `checklist-gate.py`
now checks `isinstance(hook_input, dict)` (valid-but-non-dict stdin —
`null`/`[1,2,3]`/`42` — used to crash with AttributeError, exit 1) and
checks `save_registry()`'s return value before ever emitting a block (a
read-only registry dir used to make the counter stay at 0 forever while
still blocking — Argus's "infinite block" repro).

**Race-test technique for a shared-state module (not a hook wrapper):**
reused `tests/test_file_lock.py`'s own established pattern (asymmetric
injected delay via a `python -c` harness synchronized with a ready/go
marker-file barrier, real `Popen` subprocesses) but pointed at
`lib/checklist_state.py`'s `locked()/load_registry()/save_registry()`
directly instead of reimplementing the hook's stdin-parsing wrapper — the
delay goes INSIDE the locked critical section, which both widens the race
window AND proves mutual exclusion is real (if it weren't, the sleeping
writer's peer would run concurrently and clobber it).

**chmod-based permission test, restored in `finally`:** to force a real
`save_registry()` failure (read-only dir), touch the `.lock` file with
normal perms FIRST, then `chmod 555` only the specific
`session-checklists/` dir (never tmp_path root) — opening an EXISTING
file for locking doesn't need dir-write, only CREATING a new one does, so
this isolates the write failure to the registry itself, not lock
acquisition. Skip on non-POSIX and when running as root (permission bits
don't apply).

**Third round (2026-08-24, same day) — Moriarty broke the box↔task matching, all 4 found GREEN.**
Coordinator asked for 4 more tests after Moriarty's adversarial pass; all
4 were already fixed by Ultron in parallel by the time each test was
written (re-verified by reading the live files immediately before, not
trusting the read from the previous round). `checklist_state.normalize_box_text()`
(new: casefold + NFC + whitespace collapse) makes an em-dash/ASCII-hyphen,
NFC/NFD, or irregular-whitespace spelling of the same box match; a
negative-control test (a genuinely DIFFERENT box) confirms the
normalization isn't loose enough to swallow real mismatches.
`_read_board_tasks()` now keys on `normalize_box_text(subject) -> list of
ALL statuses seen` instead of a dict overwrite, so a completed duplicate
task is never shadowed by a same-subject pending one that happens to sort
later alphabetically (`"9.json" < "90.json"`, id 9 completed, id 90
pending — id 90's status used to silently win). `_record_skill_load()` now
returns `(enforced, effective_boxes)`: `enforced=False` (persistence
failed) drops the "will block closing this session" sentence from the
emitted message in favor of a softer notice, and a repeat load after a
manifest hot-edit re-emits the REGISTRY's already-committed box text, not
the edited manifest's — tested via the same round-trip technique as
always (read the registry file independently, compare against what
stdout said).

**Verification discipline under this fast-parallel Ultron pace**: by the
third round in the same day, re-reading the live hook/lib files
immediately before writing EACH test (not once at the start of the whole
batch) was what caught that items 1+2 were already fixed mid-file-write —
a single "read once, write four tests" pass would have produced RED
assertions against code that had already changed underneath, and reported
a false RED to the coordinator.

**Fourth round (2026-08-24, same day) — case-folding gap I myself mis-reported as already fixed.**
Third round's memory note claimed `normalize_box_text()` already
casefolded, read from the docstring/intent rather than from a test that
actually varied case — none of round 3's dash/NFD/whitespace variants
ever put the manifest box and the task subject in DIFFERENT letter
cases (all built via `.replace()`/`unicodedata.normalize()`, neither of
which touches case), so a missing `.casefold()` had no test that could
have caught it. Coordinator confirmed by hand it wasn't folding, Ultron
fixed it in parallel again. **Verified this round's tests were meaningful,
not vacuous**: temporarily stripped `.casefold()` from the real function,
reran — 4/5 red (the negative control correctly stayed green, since it
doesn't depend on case-folding), restored the file byte-for-byte
(`diff` confirmed) before rerunning green. Added a bonus test with German
`ß` vs `SS` (`"ß".casefold() == "ss"` but `"ß".lower() == "ß"` unchanged)
specifically because the coordinator's own requested example (`Ó`/`ó`)
folds identically under both `.casefold()` and `.lower()` in Python and
so can't actually tell a casefold-based fix apart from a lower()-based
one — only ß/SS can.

**Lesson**: when writing a memory note about "what the code now does"
from reading a docstring/comment describing intent, downgrade the
confidence unless a test in the SAME round actually forced that
behavior to matter (varied the exact axis the docstring claims to
handle). A docstring's promise and the code's actual behavior can drift
apart mid-implementation, especially under this pace of parallel fixes.

**Fifth round (2026-08-24, same day) — diacritics, a deliberate contract not a bug.**
Coordinator decision: `normalize_box_text()` also strips diacritics
(NFKD-decompose + drop combining marks, e.g. `unicodedata.combining(c)`),
not just NFC-compose them. RED confirmed against the pre-fix code (same
revert-and-restore verification as round 4: temporarily swapped the real
function back to the NFC-compose-only version, reran — 2/3 red, the
negative control correctly stayed green — restored byte-for-byte via
`diff`). Ultron's fix was already live by the time the tests were first
run against the current file.

**"ñ" vs "n" is an intentional, accepted collision — pin it as a
contract, not a regression test.** The coordinator explicitly named this
pairing as the deliberate effect of stripping diacritics (Spanish "ñ" is
"n" + combining tilde under NFKD, same mechanism as any other accent).
Wrote it as its own test class with a docstring warning: if this test
ever starts failing, that means the diacritics-stripping decision was
reverted, not that a real mismatch-prevention bug reappeared — don't
"fix" it by tightening the matcher without going back to the coordinator
first. General lesson for any test pinning a deliberate business
decision that happens to look like a false positive: say so loudly in
the test's own docstring, at the point of failure, not just in agent
memory.

**Full-suite HEAD-moved false-positive, unrelated to this work**: one
`python3 -m pytest unmassk-toolkit/tests -q` run mid-round failed
`test_customs_hook.py`'s `_guard_against_writing_to_the_real_repo`
autouse fixture (HEAD moved during the run) — caused by the memory system
itself (gitmem) committing real notes (`D-054`, the same decision this
round tests) to this repo WHILE the full suite was running, not by any
test file. Confirmed via `git reflog` (two legitimate memory commits
landed mid-run) and by re-running `test_customs_hook.py` alone
immediately after (100% green). A full-suite run that fails ONLY this
guard, with commits visible in `git log`/`reflog` matching the exact
window of the run, is this specific false-positive class — rerun once
before treating it as a real regression.
