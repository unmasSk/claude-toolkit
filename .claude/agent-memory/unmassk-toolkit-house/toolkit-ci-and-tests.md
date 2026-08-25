---
name: toolkit-ci-and-tests
description: Diagnosing a red CI or a red suite in unmassk-toolkit — which reds are the harness and which are the product, the three CI env variables, the encoding/Windows/git-fixture families, and the static gates
metadata:
  type: reference
---

Every entry states what was CONFIRMED, and — where the fix has since landed — where it landed,
so nobody re-diagnoses a closed round. Re-verified against the tree on **2026-08-25**.

**Standing caveat for this whole file:** memory-v1 (`lib/recall.py`, `lib/boot_memory.py`,
`lib/boot_render.py`, `lib/boot_git_checks.py`, `hooks/session-start-boot.py`,
`bin/git-memory-commit.py`, and the whole `tests/test_boot_*` family) was **deleted from the
repository**; v2 lives in `lib/memory/` + `bin/memory/` + `tests/memory/`. Entries below that
name a v1 file keep it as the *place the mechanism was proven*, never as a place to go look.

## Read the SHAPE of the red before forming a hypothesis — it names the family for free

The four shapes, and what each one is always caused by in this suite. This replaces four
corollaries that used to sit scattered at the end of four different entries.

| Shape of the failure | Family | Never |
|---|---|---|
| Identical on Ubuntu **and** Windows | interpreter or data (py3.10, TZ, a poisoned fixture) | platform, encoding |
| Windows only, `_readerthread` / `charmap` / `cp1252` in the frame | a text-mode `subprocess`/`open`/`write_text` missing `encoding=` | product |
| Windows only, uniform `assert []` on a call-observation list, and every product assert BEFORE it passes | the observing instrument is POSIX-only; the product ran fine | product |
| Ubuntu only, intermittent, green on retry, `git` exit 128 | environmental resource pressure on the runner | fixture logic |

Then check the free controls: sibling tests in the same file that pass are the discriminator.
In the 2026-08-08 `cd` round, six passing siblings against seven failures pinned the cause with
zero instrumentation.

## The three CI environment variables — change one at a time, before reading any code

CI pins **Python 3.10** (`.github/workflows/toolkit-ci.yml:39`, matrix `[ubuntu-latest,
windows-latest]` at `:33`; `plugin-tests.yml:37` likewise), runners are **TZ=UTC**, the Windows
runner encodes **cp1252**. Dev boxes here are 3.14 / +01:00-+02:00 / UTF-8 — every axis differs.

```
TZ=UTC uv run --no-project --python 3.10 --with pytest==9.1.1 python -m pytest <file> -q
```

In the 2026-08-08 round all three failure groups fell out of this matrix alone, with no
instrumentation: py3.10×TZ=UTC explained the both-OS reds, cp1252 the Windows-only ones.
To reproduce a **Windows cp1252 decode** from macOS do NOT fight the locale (`LC_ALL=C` +
`PYTHONCOERCECLOCALE=0` still yields UTF-8 on macOS/py3.14 — tried, no reproduction): capture
the child's raw **bytes** and `.decode("cp1252")`, which is literally what `_readerthread` does.

## Ask git for epoch seconds, never for a date as text — CLOSED, and the closure is the rule

CONFIRMED 2026-08-08: `%(committerdate:iso8601-strict)` and `%aI` render the timezone stored in
the *commit*, not the reader's. Offset 0 renders a bare `Z`; `datetime.fromisoformat` accepts
`Z` only from **3.11**, so on the pinned 3.10 one commit made in UTC poisoned the read. Isolated
with three controls: py3.10+Madrid green, py3.14+UTC green, py3.11+UTC green, **py3.10+UTC red**.
Blast radius was by call site and the two modes were opposite: a `except ValueError: continue`
wrapper returned `None` (silent, reads as "no activity"); a naked parse killed the whole read, so
one poisoned commit lost every other note too.

**Substitute, in the tree now:** `lib/memory/timefmt.py:74 from_git_seconds()` — the single
reader, called by the four `lib/memory/` sites plus the close-session transcript. Its docstring
(`:32-45`) states the rule better than the original diagnosis did: *the fix is not to normalise
the `Z`, it is to stop asking for text* — an epoch number has no format a Python version can read
differently. It also records that v1 had decided this once and lost it on the rewrite.
This supersedes a separate 2026-07-08 entry on `get_last_context_time()`/`get_timeline()` using
fragile `%aI`+`fromisoformat` while `extract_memory()` used robust `%at`: same finding, same fix,
and both v1 functions are gone.

## The cp1252 / UTF-8 family — one mechanism, three layers, all three now closed

**The mechanism** (CPython source, reproduced byte-for-byte): `subprocess.run(..., text=True)`
with no `encoding=`, reading a child that emits UTF-8, fails **differently per platform**.
On POSIX `_communicate` decodes in the MAIN thread → `UnicodeDecodeError` reaches the caller,
and a `except Exception: pass` wrapper swallows it whole (silent, rest of the `try` skipped).
On Windows it decodes inside `_readerthread` → the exception dies in the thread,
`threading.excepthook` dumps a Traceback the caller cannot catch, the buffer stays empty, and
`stdout = stdout[0] if stdout else None` hands back **`None`**. Audit every consumer for
`None`-tolerance: `json.loads(None)`, `None.strip()`, `x in None` turn an ugly traceback into a
real crash. `UnicodeDecodeError` subclasses `ValueError`, so a `except (…, ValueError)` guard
swallows it into a silent failure.

1. **Product (was T1, 2026-07-07).** No entry point forced UTF-8, so every emoji/arrow print
   exited rc=1 under a legacy codepage — `user-prompt-memory-check.py` failed on *every*
   invocation, `git-memory-install.py --auto` never wrote CLAUDE.md (≈72 downstream
   `FileNotFoundError`), `git-memory-commit.py` crashed *after* committing.
   **CLOSED:** `lib/encoding_guard.py::force_utf8_streams()` exists, is fail-open by contract,
   and is called by **25** entry points under `bin/` and `hooks/`. Its docstring credits this
   diagnosis (round 2, CI run 28897259775). A 2026-07-08 note claiming the guard was absent from
   all entry points was true at HEAD `72805bc` and is false today — deleted for that reason.
2. **Central harness.** `tests/conftest.py` `run_cmd` now runs `encoding="utf-8",
   errors="replace"` (`:198`, with the reasoning at `:178-190`); `tests/memory/conftest.py`
   does the same in `run_git` (`:661-664`) and its script runners.
3. **Per-file harness — the layer a central fix never reaches.** After (2) landed, the same
   defect resurfaced in `Path.write_text()` with no `encoding=` and in hand-written `_sp.run(['git'
   …])` inside `-c` probe code strings. Those files are gone with v1, but the rule is permanent:
   when fixing a cross-cutting encoding defect, grep the WHOLE test tree for `subprocess.run(` /
   `_sp.run(` without `encoding=`, and for `.write_text(` / `.read_text(` / `open(` without it.

**And do not over-correct.** A blanket `encoding='utf-8'` sweep is WRONG on a parent read of a
child that emits in the OS *locale* (git, or any script without a UTF-8 guard): strict utf-8
then raises on cp1252 bytes. Pair it with `errors='replace'`. Writes, and reads of files you
control, stay strict. Proven on `tests/test_release.py` (2026-07-08): the #51 sweep pinned two
reads to strict utf-8, `bin/release.py` prints Spanish accents with no guard, and the four tests
doing `combined = stdout + stderr` died on `TypeError: NoneType + str` — one event, two symptoms.

## PYTHONUTF8=1 masks all of the above — never trust one green Windows box

`locale.getpreferredencoding(False) == 'utf-8'` while `locale.getencoding() == 'cp1252'` is the
tell that Python UTF-8 mode is on (`sys.flags.utf8_mode == 1`). Under it, `open()` and
`subprocess(text=True)` default to UTF-8 and the bugs do not reproduce. Detect with:

```
python -c "import sys,locale;print(sys.flags.utf8_mode, locale.getpreferredencoding(False), locale.getencoding())"
```

If utf8_mode=1, encoding findings are LATENT, not absent. Report them as real.
**Same box, same session:** `hasattr(os,'O_NOFOLLOW')` is `False` on win32, so `os.open(...,
O_NOFOLLOW)` raises `AttributeError`, NOT `OSError` — an `except OSError` guard does not catch
it, and an `ImportError` fallback to a second copy of the same helper protects nothing when both
copies name the missing flag. `os.chmod(p, 0o600)` is a near-no-op on Windows (only the
read-only bit maps), so any "0o600 means no group/other access" claim in a docstring is false there.

## A git identity absent on the runner, swallowed by helpers that ignore rc — CLOSED twice

CONFIRMED 2026-07-07: runners have no `user.name`/`user.email`, git's auto-detect yields
`runner@…(none)` which git rejects, `git commit` exits 128 — and helpers returning `(rc, out, err)`
whose callers ignore `rc` turned that fatal into an unborn HEAD and a wall of *content-absent*
assertion failures with no error anywhere. macOS does not reproduce it (git auto-detects
`user@host.local`); nullifying `GIT_CONFIG_GLOBAL`/`SYSTEM` is not enough either. Faithful local
reproduction:

```
printf '[user]\n\tuseConfigOnly = true\n' > /tmp/fakegitconfig
GIT_CONFIG_GLOBAL=/tmp/fakegitconfig GIT_CONFIG_SYSTEM=/dev/null python3 -m pytest <files> -q
```

Correct layer was the shared test env, not the workflow: fixing the runner env would have masked
the real defect (helpers ignoring rc). **CLOSED in both suites, with the same literal name/email
on purpose** so that importing both conftests into one pytest process cannot have one overwrite
the other: `tests/conftest.py:88-91` (`_DEFAULT_GIT_IDENTITY_ENV`, merged per call) and
`tests/memory/conftest.py:640-643` (written straight into `os.environ`, inherited by every
child). Env vars always beat any config file, which is why touching `run_git` alone suffices.

**The lesson that outlived the bug.** The v2 rewrite re-derived this from scratch and shipped a
`run_git` docstring arguing a git-identity fallback would be "anticipating infrastructure without
having seen the real failure" — the failure had been seen, written down and fixed thirteen months
of sessions earlier. Rewrites do not inherit scars. When a fixture or helper docstring explicitly
declines a hardening step, it is a countdown: grep agent memory for that failure class before
accepting the argument. (That docstring is gone; the current one at `tests/memory/conftest.py:646`
explains the fallback instead.)

## A fixture that fails loud in masse MASKS the bigger bug behind it

CONFIRMED 2026-08-08. "284 `ERROR at setup` from one fixture plus only 2 real failures" reads
like a small tail. The 284 tests never executed, and the three homes of the real product bug
were all inside them: satisfying the precondition and re-running turned 2 failures into **17**.
An error count is not a damage estimate; it is a blindfold. Procedure: (1) `grep -l <fixture>`
to list which suites were suppressed, (2) satisfy the precondition and re-run exactly those under
the CI's Python and TZ, (3) report the post-fix number. Sequencing matters — fixing the fixture
first would have turned a red CI into a redder one and looked like a regression caused by the fix.

## Ubuntu-only `git` exit 128 on big fixtures — CLOSED at the fixture, still open in principle

Three rounds (2026-07-11, 07-18, 07-22) on one family: fixtures build hundreds of empty commits,
then `git log --all` reads them; a different test fails each Ubuntu run, green on retry, never on
macOS or Windows. Exit 128 disambiguates: this suite's `run_git` returns rc 1 on timeout and rc 0
on zero results, so 128 is a genuine git `die()`.

**Do not re-run these dead ends — all rejected with evidence:** the 10 s git timeout (a timeout
prints its own breadcrumb; none in any failing log) · a stale or corrupt commit-graph (a stale one
degrades silently, a corrupt one prints `commit-graph …` lines and still returns rc=0; CI stderr
had zero such lines) · an auto-gc object-count race (510 `--allow-empty` commits share one tree ≈
513 loose objects, far below `gc.auto=6700`) · same-second timestamps (linear chains walk by
parent pointer) · deterministic env leak (intermittency contradicts it).

**What the evidence did support.** The exact stderr pair `error: Could not read <parentSHA>` +
`fatal: Failed to traverse parents of commit <childSHA>` is the revision-walker signature for a
**reachable parent object genuinely absent** — reproduced exactly by deleting one middle commit's
loose object; `git fsck --connectivity-only` then prints `broken link` and exits non-zero, which
makes it an ideal fixture-integrity probe. Why Ubuntu only: `git commit` and `git fetch`
auto-invoke `git gc --auto`, Linux detaches it via fork (`gc.autoDetach`) and can race the
object DB under heavy parallel CI I/O; Windows cannot fork so gc is serialized; macOS/APFS never
repacked mid-loop even at `gc.auto=50`. The gc-as-cause link stays high-confidence inference,
never spontaneously reproduced locally (a 10-core/16 GB box is too capable).

**CLOSED at the fixture layer:** `tests/conftest.py:121-129` (`_GC_DISABLE_ENV`) now merges
`GIT_CONFIG_COUNT`/`KEY_n`/`VALUE_n` → `gc.auto=0`, `gc.autoDetach=false`,
`maintenance.auto=false` into every git subprocess. `gc.auto=0` alone kills the trigger for both
`commit` and `fetch`.

**Still true in principle, and the real finding:** the product code that HID the transient.
`_scan_commits()` did `if code != 0 or not log_output: return []` — a transient 128 collapsed to
"no memory found", indistinguishable from genuinely empty, and fed the injection with EMPTY
memory. Same silent-empty shape in three sibling readers. Test-side retry wrappers were
symptom-side band-aids: they greened CI while a real user still lost the read. When a CI-only
intermittent cannot be reproduced on capable local hardware, **the actionable root cause is the
code that hides the transient, not the transient**. Fix = fail loud (assert rc==0 with stderr) on
every read path. The v1 readers are deleted, so verify the v2 ones in `lib/memory/gitcmd.py`
before assuming this shape is absent.

## POSIX assumptions baked into the harness — the instrument is blind, the product is fine

All test-only, all invisible on a POSIX dev box. Tell: Ubuntu green + Windows red + macOS green.

- **`subprocess.Popen(["git"], shell=False)` cannot be intercepted by a PATH shim on Windows.**
  CreateProcess, given an extensionless module name, appends **only `.exe`** and searches PATH —
  it does NOT consult PATHEXT. PATHEXT is a cmd.exe / `where` / `shutil.which` concept, and
  subprocess with `shell=False` never calls `which`. So an extensionless `git` shim is invisible
  AND so is a `git.cmd` wrapper — a doctrine that cost a whole extra CI round (runs 29110579481
  then 29122808531, same empty-log signature both times). **Substitute in the tree:**
  `tests/_git_intercept.py` patches `subprocess.Popen` itself, cross-platform, with a
  `sitecustomize.py` vehicle for subprocess-launched hooks. Caveat: its only consumer
  (`test_boot_freshness.py`) died with v1, so the module is currently an **orphan** — read it
  before re-deriving any of this, do not rewrite it.
- **`core.autocrlf` makes `git add` read the blob of files it is NOT adding.** CONFIRMED
  2026-08-26 by controlled matrix on macOS (run 32904954108, `test_boot.py::test_boot_survives_a_real_corrupted_git_object...`).
  With autocrlf `true`/`input` (the Git-for-Windows default; unset on the ubuntu/macOS
  runners) git cannot trust a **racy stat** — an index entry whose mtime is in the same
  second as the index write, which every fast fixture produces — so it re-converts that
  path through `convert_to_git()`, and the CRLF_AUTO branch consults the CONTENT of the
  blob the index records for it (`convert.c::has_crlf_in_index` -> `read_blob_data_from_index`).
  Corrupt that blob and an unrelated `git add`/`git commit -- <other paths>` dies
  `fatal: loose object <sha> ... is corrupt`. Pathspec scope, `--all` and `core.safecrlf`
  are all irrelevant; only three things stop it: autocrlf off, the path marked `-text`
  (binary short-circuits before the index read), or an mtime older than one second.
  **Rule:** "corrupting object X does not touch code path Y" is a POSIX-only claim.
  Under autocrlf, EVERY tracked text blob in the repo is on the path of EVERY `git add`.
  A fixture that sabotages an object must exempt that path via `.git/info/attributes`
  (repo-local, untracked, leaves autocrlf live everywhere else) — never by switching
  autocrlf off repo-wide, which would mask R-014's whole class.
- **A vacuous inverse assert.** `assert not fetch_calls` on a shim-fed list passes on Windows for
  the wrong reason — the log is empty either way. A blind instrument makes both polarities lie.
- **`ntpath.expanduser` never reads `HOME`** (CPython source): it reads `USERPROFILE`, then
  `HOMEDRIVE`+`HOMEPATH`. Sandboxing a subprocess with `env={"HOME": tmp}` is a no-op on Windows.
  **CLOSED** where it bit: `tests/memory/test_customs_hook.py:1522` now sets both.
- **Text-mode write translates `\n`→`\r\n`.** A producer reading with `newline=None` and writing
  with `newline=None` legitimately emits a **uniform-CRLF** file on Windows (not mixed EOLs).
  A test that reads it `"rb"` and asserts an LF-rendered substring fails. Fix is in the test
  (`content.replace("\r\n","\n")` before comparing); uniform CRLF in a user's CLAUDE.md is normal.
- **`shlex(posix=True)` eats the backslashes of a native Windows path.**
  `shlex.shlex(cmd, posix=True, punctuation_chars=True)` (still live at `hooks/customs.py:236`)
  turns `cd C:\Users\x\proj` into `C:UsersxProj`; `ntpath.isabs` then says False, the mangled
  string is joined onto the base cwd, `isdir` fails, and the `cd` is **silently ignored** — the
  commit gate decides about the wrong repository. Any test interpolating `str(Path)` into a
  command string is POSIX-only by construction. **CLOSED in the harness** with `Path.as_posix()`
  (`tests/memory/test_customs_hook.py:1313-1323` and eight peers).
  What actually works on Windows: relative ✅ · forward-slash absolute ✅ · quoted backslash ✅ ·
  unquoted backslash ❌ (bash eats them too, so the product agrees with reality) · Git-Bash
  `/c/Users/x` — this one was a genuine **product** hole, since `ntpath.isabs("/c/…")` is True
  yet the path resolves nowhere. **CLOSED in the product:**
  `hooks/customs.py:405-450 _translate_git_bash_drive_path()`, Windows-only, single drive letter.

## A red suite after a refactor is three different verdicts — never lump them

CONFIRMED 2026-07-14. Triage each red into one of three, and read `git log` on the PRODUCT file
against the TEST/CONFIG file: the newer side is the outlier.

1. **Mechanism deleted → the test is obsolete, delete it.** Tests dying at their own setup line
   because the surface they exercise no longer exists. (The 2026-07-14 instance was the
   push→pull change on the per-message recall channel; those files, and the control-byte threat
   model behind them, are both retired now — CLAUDE.md calls that material dead weight.)
2. **Marker assertion drifted → update the one assert, keep the real contract.** In the same
   round, an encoding-contract test had two asserts: `rc==0` under cp1252 (the real regression,
   still passing, and the hook deliberately keeps a non-ASCII char to keep guarding it) and a
   stale literal marker. Only the marker had moved. Not a product bug.
   (`[memory-check]` is back in `hooks/user-prompt-memory-check.py:267` today.)
3. **Coupled config the refactor forgot → fix the config, the test is doing its job.**
   `tests/test_user_prompt_skill_router.py` reads `SKILL_TRIGGER_PHRASES`
   (`lib/skill_router.py:59`, plus `_ES` at `:92`) dynamically and asserts each phrase is a
   substring of its skill's CURRENT description. A description rewrite orphaned two phrases.
   **A drift-guard failing is the guard WORKING.**

## The static gates in tests/memory — diagnosable by reading, never by instrumentation

CONFIRMED 2026-08-06 by AST trace. When one goes red after new work, the gate is almost always
right and the new code is the outlier. All three still exist; each has a non-obvious contract.

1. **`test_no_file_outside_the_allowed_zone_imports_lib_memory`** (`test_boundary.py:190`).
   Allowed zone: `lib/memory/`, `bin/memory/`, `bin/gitmem`, `hooks/customs.py`,
   `hooks/boot_launcher.py`, `tests/memory/`. Purpose: v2 must stay deletable without breaking
   boot or the installer. Trap: a NEW file in `lib/` that legitimately reuses a memory function
   collides head-on. That is a **policy collision** (deliberate reuse vs the deletability
   invariant), not a bug — route to the owner: decouple, or widen the zone (weakens
   deletability, owner-approval only). A planted-violation self-test sits at `:214`.
2. **`test_no_public_symbol_has_zero_production_and_zero_tests`** (`test_boundary.py:881`).
   Two-branch AST scan; the production branch deliberately excludes same-file callers, because it
   wants a CROSS-FILE consumer. Trap: a public function whose only caller is a same-file sibling
   counts as production 0. That is not dead code and not a scanner blind spot — it means the
   symbol never needed to be public. Fix = privatize with `_`, or give it a direct test. The
   tests branch resolves fixture aliases, module-level import vars and methods inside `class
   Test…`, so a reported "0 tests" is trustworthy.
3. **`test_relaunch_command_flags_and_required_args_match_real_argparse`**
   (`test_rejection_relaunch_commands.py:489`). Its harness monkeypatches `parse_args` to return
   a bare `Namespace()` and calls `module._parse_args([])` to capture the real parser without
   parsing — which assumes every `bin/memory/<sub>.py::_parse_args` is a thin
   `return parser.parse_args(argv)`. **CLOSED:** `rule.py` was the one sibling in ten that
   post-processed inside `_parse_args`; the normalization now lives in `main`
   (`bin/memory/rule.py:88-95` thin, `:230-240` the logic) — the 10:1 convention, restored.

## Two traps on a large in-flight refactor

CONFIRMED 2026-08-02 by direct import of HEAD blobs and a full-vs-subset pytest comparison.

1. **HEAD may already be broken, so the diff under review can be the REPAIR, not the damage.**
   A module was deleted while an importer kept its module-level `from … import`, so SessionStart
   had been dying on every session for five commits. Cheap probe with no worktree:
   `git show HEAD:<path>` each module into a tmpdir, then import it. **Order matters** — insert
   the tmpdir LAST on `sys.path` so it wins; backwards, you silently import the working tree and
   get a false "HEAD OK".
2. **A partial pytest run in this suite is not evidence.** A test file that stubs a module into
   `sys.modules` during its own import window freezes stably-named modules for whoever collects
   after it — 5 failures in a subset, 5 passes alone. Only the full-suite run is authoritative,
   and it needs `--continue-on-collection-errors`: one module-level ImportError makes pytest
   abort with "Interrupted: N errors during collection" and run **zero** tests. A mid-refactor
   suite is then not red, it is *absent*, which reads exactly like "nobody verified this".
3. **`git diff --stat` counts insertions+deletions, not deletions.** "657 lines lost" was 598
   deleted + 59 added. Re-derive with `--numstat` before calling a size gap over-cutting.
4. **A guard written for a removed subsystem may also protect surfaces that survive.** An
   upstream-history check born for the memory fetch was also suppressing the pull directive and
   the branch listing; removing the fetch removed the guard and both survivors started lying.
   Grep every removed function for call sites in the code that STAYS.

## `sys.modules` stub leak across test files

CONFIRMED 2026-06-09. A test that inserts a bare `types.ModuleType` into `sys.modules` and
restores only `sys.path` in its `finally` leaves the stub registered for the whole pytest
process; a later real `from <module> import <symbol>` resolves to it.
**Signature:** `ImportError: cannot import name 'X' from 'mod' (unknown location)` — the
"(unknown location)" is the tell, since a synthetic module has no `__file__`/`__spec__`.
**Detection:** passes alone, fails in the full suite → bisect `pytest <earlier_file>
<failing_file>` over alphabetically-earlier files → check whether the polluter's `finally`
restores `sys.modules` or only `sys.path`. A `if name not in sys.modules` guard makes the leak
non-deterministic, depending on whether the real module was imported first.
**Fix (test isolation, never production):** `monkeypatch.setitem(sys.modules, name, stub)`, or
snapshot-and-restore in `finally`. Do NOT make the importing module tolerate the missing symbol —
that masks the leak and weakens a real import contract.
The 2026-06-09 instance (`test_migrate_statusline.py`) is deleted, but four files still write
into `sys.modules` today (`tests/test_file_lock.py`, `tests/test_file_lock_regressions.py`,
`tests/memory/conftest.py`, `tests/memory/test_rejection_relaunch_commands.py`), so the class
is live — and it is also the mechanism behind trap 2 above.

## Superseded, kept because nothing replaced it: the boot-stamp last-writer-wins design

**Stopped being actionable when memory-v1 was deleted** (`hooks/session-start-boot.py` and
`lib/boot_git_checks.py` no longer exist); kept because the *design* mistake has no substitute
written anywhere and v2 boot can repeat it. CONFIRMED 2026-07-10 from session transcripts.

`SessionStart` was registered with no matcher, so boot fired on `startup`, `resume`, `clear` and
`compact` alike; every boot overwrote the single per-repo boot-log with no dedupe; the fetch was
rate-limited to 300 s keyed on `.git/FETCH_HEAD` mtime. The first boot in a window fetched and
the rest reported "fetch skipped" — so the LAST writer was almost always a rate-limited one, and
users read a working system as broken. Rejected with evidence: a single boot cannot fetch then
relabel itself skipped (one `fetch_state` dict, rate-limit is an early return before the fetch);
a session-file mtime is a last-message time, not a boot event.
**Three durable points:** (a) a stamp rendered last-writer-wins lies whenever the writer fires
more than once per window — render the freshest KNOWN state, or keep the fresher of the two;
(b) "rate-limit skip" is not a degraded state, it means *already fresh*, and wording it as
"skipped" is what users report as a bug; (c) `FETCH_HEAD` mtime is shared non-authoritative
state — a user's own `git pull` resets the clock, so the gate can be driven by non-boot activity.
