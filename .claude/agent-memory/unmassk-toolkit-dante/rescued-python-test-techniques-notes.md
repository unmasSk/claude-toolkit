---
name: rescued-python-test-techniques-notes
description: live pytest/git/Windows test techniques rescued 2026-10-16 from the retired catch-alls conventions.md, edge-cases.md, mock-patterns.md
metadata:
  type: project
---

# Rescued test techniques (still live)

Rescued 2026-10-16. The three catch-all files were marked retired as "chatroom/v1 material", but these sections are generic techniques for unmassk-toolkit/tests that still apply (helpers checked on disk: tests/_git_intercept.py, tests/conftest.py, lib/git_helpers.py run_git, hooks/pre-merge-gate.py). Copied verbatim; chatroom, omawa, v1-module (recall.py, boot_memory.py…) and attacker-model sections were left out. Some overlap with [[unmassk-toolkit-python-test-conventions]] is possible.

# From conventions.md

## Python Pytest (unmassk-toolkit/tests/)

Framework: `pytest` (standard). No bun, no Vitest.
Run: `python -m pytest unmassk-toolkit/tests/<file> -q` from git root.
CWD for subprocess calls: always a `tmp_path`-based temp git repo (NOT the project repo).

Patterns used:
- Class-per-scenario (e.g. `TestSubagentTypeAbsentOrEmpty`) with one assert per method.
- `_make_repo(tmp_path)` + `_commit(repo, subject, trailers)` for fixture setup.
- `_run_hook(repo, tool_name, tool_input_dict)` → `(rc, parsed, stdout, stderr)`.
- `_run_hook_raw(repo, payload_str)` for testing malformed inputs.
- `_hook_specific(parsed)` → `parsed["hookSpecificOutput"]`.
- Import `run_cmd` from `conftest` for raw subprocess invocations.
- No `@pytest.fixture` used in hook tests — all setup is inline per test.

Importing internal functions from hooks/bin (no main() side effects):
- Use `importlib.util.spec_from_file_location("unique_mod_name", SCRIPT_PATH)` + `spec.loader.exec_module(mod)`
- Prepend LIB_DIR to sys.path BEFORE exec_module so hook's own lib imports resolve
- Use a unique module name per test class to avoid importlib cache collisions
- Pattern validated for: session-start-boot._sanitize_trailer_value, git-memory-gc.find_stale_items

Regression test labeling convention (auditoría round 2):
- [ROJO]: test que DEBE fallar con el código actual (documenta el bug)
- [GUARDA]: test que DEBE pasar antes y después del fix (invariante de no regresión)

## Branch-aware hook testing (pre-merge-gate.py style, session 2026-07-01)

When a hook needs to shell out to git to learn current-branch / upstream
identity (not just regex over the command string), build a REAL git fixture
rather than mocking git plumbing:

- `git branch -m <name>` after the initial commit to force a deterministic
  branch name — never rely on `git init -b` / `init.defaultBranch`, it
  varies across git versions/configs.
- For upstream-tracking scenarios (`@{u}`, `refs/remotes/origin/<branch>`),
  create a real local bare repo (`git init --bare` in a sibling tmp_path
  dir) as `origin`, then `git push -u origin <branch>` from the working
  repo. Push auto-populates the local remote-tracking ref — no fetch needed,
  no network.
- Invoke the hook the same way test_security_regression.py does: subprocess
  + JSON stdin payload, `cwd=repo`. Do not import-and-call for hooks that
  shell out — the whole point is exercising the real subprocess/cwd path.

This confirmed a mixed RED/GUARD result is normal and expected within a
single contract-pass file: scenarios that require NEW logic are RED (fail
against the unmodified hook), scenarios documented as "already implemented"
are GUARD (pass now, must keep passing). Don't force all tests in a
test-first contract file to be RED — report the true split honestly (see
`test_pre_merge_gate.py`).


# From edge-cases.md

## Windows git bare repo — clone default branch mismatch

`git init --bare` on Windows defaults HEAD to `master`. If the source repo uses `main`,
cloning the bare repo produces "warning: remote HEAD refers to nonexistent ref" and the
clone has no checked-out branch — causing `git push origin main` from the clone to fail
with "src refspec main does not match any".

Fix: always pass `-b main` to `git init --bare` when the source uses `main`.

Affected: any test that creates a bare remote and then clones from it to simulate a
second contributor pushing ahead (e.g. the "local behind remote" preflight scenario).

## "Not truncated" assertions — longest-contiguous-run technique

When a contract requires proving a long payload was copied verbatim (not cut
short) into some larger blob of text, don't hand-type the expected full
string and compare equality (fragile — any unrelated formatting change
breaks it) and don't just do a substring `in` check on the whole marker
(works, but doesn't measure length precisely at the boundary). Instead:
seed the payload with a repeated single character not otherwise common in
the output (e.g. `"Q" * 2200`, `"Z" * 2100` — pick a different char per
field so multiple long fields in the same blob can't be confused with each
other), then scan the output for the longest contiguous run of that
character and assert `run_length == len(payload)`. Natural text (headers,
words, punctuation) essentially never repeats one character thousands of
times in a row, so this is robust to any other content differences and
precisely catches partial truncation (run shorter than expected) without
requiring exact string reproduction.

Used in `unmassk-toolkit/tests/test_boot_output.py` (`_longest_char_run`)
for the session-start-boot.py stdout-truncation-fix contract: a synthetic
context() commit with 2000+ char subject and Next/Decision/Memo/Remember
trailers (each a distinct repeated character) must appear fully intact in
the new fixed-path boot-log file, never in truncated form.

## unmassk-toolkit runtime files — fixed-path convention

Any new generated/runtime file for the plugin belongs under
`.claude/.unmassk/` (see `git_helpers._GENERATED_JSONS` — the whole
directory is already gitignored via `ensure_gitignore()`, so a new file
placed there needs no new `.gitignore` entry). Confirmed for the
boot-log-latest.txt fixed-path file added in the stdout-truncation-fix
contract (session 2026-07-04).

## Importing a hyphenated bin/ script to read its own constants (not just call it)

When a test needs to build an input that exactly matches a script's own
internal format string (e.g. a commit subject assembled as
`f"{EMOJIS[type_]} {type_}({scope}): {message}"` in
`bin/git-memory-commit.py`), don't hardcode the emoji or prefix as a string
literal in the test — that duplicates a source of truth Ultron could change
independently. Instead use the same `importlib.util.spec_from_file_location`
pattern already documented in
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)
to import the hyphenated script as a module and read its real dict/constant
(e.g. `EMOJIS = _mod.EMOJIS`) directly, then use it to compute boundary-case
lengths. Confirmed safe: `git-memory-commit.py`'s module-level code (EMOJIS
dict, CO_AUTHOR resolution) has no side effects outside `if __name__ ==
"__main__": main()`, so exec_module() is safe to call from a test.

## Reproducing a write-failure (permissions/disk-full) fallback bug — chmod ordering matters

When a hook's "write a file, fall back on failure" logic has the bug that
the fallback-trigger variable is set to a truthy path *before* the
try/except confirms the write succeeded (so the except branch still leaves
a "we wrote it" signal even though nothing was written), reproduce with:
`os.chmod(parent_dir, 0o500)` (read+execute, no write) applied to the parent
directory **before** the target subdirectory exists — this makes
`os.makedirs(target_subdir, exist_ok=True)` itself raise `PermissionError`
(a subclass of `OSError`), which is what the hook's `except OSError: pass`
catches. Do NOT chmod a directory that already has the target subdirectory
created inside it (e.g. by an installer that already ran) — if the child
directory already exists and is itself still writable, a read-only parent
does not block writes into that already-existing child (Unix write
permission is per-directory, not inherited from ancestors). Always restore
permissions (`os.chmod(dir, 0o700)`) in a `try/finally` around the
subprocess call, before any `tmp_path` teardown tries to remove the tree.
Confirmed in `unmassk-toolkit/tests/test_boot_output.py`
(`TestBootLogWriteFailureFallback`, session 2026-07-04) — needed a
`_no_install` variant of the giant-commit repo builder specifically so
`.claude/.unmassk` did not pre-exist.

## Git branch name length limits — per-component ceiling from the `.lock` file, not NAME_MAX

A single-path-component branch name (no `/`) fails `git checkout -b` once
it exceeds roughly 250 bytes on APFS (NAME_MAX=255), because git briefly
creates a `<name>.lock` file in `.git/refs/heads/` during the ref update —
the lock suffix (`.lock`, 5 bytes) counts against the same 255-byte
filesystem limit, so the real usable ceiling for a single segment is
`NAME_MAX - 5`, not `NAME_MAX`. To construct a long branch name well beyond
what "usually short" code assumes (for testing byte-budget assumptions),
use a two-segment name with a `/` separator, e.g. `("a"*245) + "/" +
("b"*245)` — each segment stays under the per-component ceiling so
`checkout -b` succeeds, while the total branch name (~491 chars here) is
long enough to expose any code path that embeds the branch name into a
size-bounded string without capping it. Confirmed in
`test_boot_output.py::TestBannerByteBudgetWithLongBranchName` (session
2026-07-04): this pushed a banner from a baseline ~666 bytes to ~1207 bytes,
comfortably proving the >1000-byte budget isn't guaranteed by construction.

## Reproducing sys.modules stub contamination across stably-named lib/ modules

When a test file stubs `sys.modules["git_helpers"]`/`["parsing"]`/`["version"]`
before `exec_module()`-ing a hyphenated hook (the pattern in
`test_migrate_statusline.py::_load_migrate_fn`) and restores them in a
`finally`, that restore does NOT protect any *other* stably-named module
(e.g. `lib/boot_memory.py`, `lib/boot_render.py`, `lib/boot_migrations.py`)
that does a MODULE-LEVEL `from git_helpers import run_git` and gets
first-ever-imported while the stub is installed — Python caches that module
in `sys.modules['boot_memory']` with `run_git` bound to the stub's function
object forever; rebinding `sys.modules['git_helpers']` afterwards doesn't
touch names already bound in `boot_memory`'s own namespace.

Reproduce by running the *existing* stub-and-restore helper (don't reinvent
it) in a **fresh subprocess** — process isolation matters here because the
bug only bites on a module's first-ever import in a process, so the result
must not depend on whether some other test file in the same pytest session
already did a real `import boot_memory` first. Pattern: build a `python3 -c`
snippet that (1) adds `LIB_DIR` and the test file's own directory to
`sys.path`, (2) loads the test file itself via
`importlib.util.spec_from_file_location` under a throwaway name (so its own
`_load_migrate_fn` helper is reachable), (3) calls that helper and the
returned migration function (triggers the contamination), (4) `os.chdir()`
into a real temp repo, (5) does a plain `import boot_memory` (already
cached from step 3) and calls a REAL function that depends on `run_git`
(e.g. `extract_memory()`, `boot_render.get_timeline()`,
`boot_migrations._migrate_untrack_generated_jsons()`).

**Assert on BEHAVIOR, never on `module.run_git is real_run_git` identity.**
The eventual fix (deferring the import into each function body, mirroring
the `parsing` pattern documented at the top of `boot_memory.py`) may remove
`run_git` as a module-level attribute entirely rather than merely rebind
it — an identity-based assertion would then error (AttributeError) instead
of transitioning to green. Test the observable output instead: seed a real
commit with a unique marker (Decision trailer text, commit subject, or a
tracked file matching `git_helpers._GENERATED_JSONS`), then assert the
real function reports that marker. Contaminated (stub `run_git` always
returns `(1, "")`) → the function sees "no commits"/"not tracked" and the
marker never appears; real `run_git` → marker appears (or, for
`_migrate_untrack_generated_jsons()`, the previously-tracked fixture file
becomes untracked — check this ONE assertion back in the *outer*,
uncontaminated test process via a plain `git ls-files`, not inside the
probe subprocess). Confirmed in
`test_migrate_statusline.py::TestSysModulesContaminationRegression`
(session 2026-07-05) — RED against the current (unfixed) module-level
imports, 0 regressions in the file's 5 pre-existing tests.

## os.path.islink() calls os.lstat() internally on Windows — spy on the right layer

When spying on `os.lstat`/`os.fstat` to prove `_open_no_follow_symlink_windows()`
(`lib/git_helpers.py`, twin `lib/_symlink_safe_open.py`) skips the identity
check for a brand-new path (no `os.path.exists()` match, the F5/O_CREAT
case), a naive spy that patches `os.lstat` and then calls the real
`os.path.islink(path)` will see ONE spurious call — confirmed empirically
(Windows, Python 3.11): `ntpath.islink()`'s own implementation calls
`os.lstat()` under the hood. A strict `assert lstat_calls == []` fails for
the wrong reason (it's islink's internal plumbing, not the guard's own
explicit `if os.path.exists(path): prior_identity = os.lstat(path)` line).
Fix: `monkeypatch.setattr(os.path, "islink", lambda p: False)` FIRST, so the
spy only ever observes the guard's own call. A loose truthy check
(`assert lstat_calls`, no exact-emptiness assertion) doesn't need this fix
since one extra call doesn't change truthiness — only exact-count/exact-empty
assertions are exposed to this gotcha. Confirmed in
`test_crossplatform_symlink_guard_hardening.py::TestNewFileOCreatSkipsIdentityCheck`
(hardening pass, session 2026-07-06).

## Moriarty T1 theater fix: in-process round-trip tests of `run_git()`'s `encoding="utf-8"` kwarg are false-green under ambient PYTHONUTF8=1 — force PYTHONUTF8=0 in a child process

`test_run_git_round_trips_utf8_accents_and_emoji_through_real_git`
(`test_crossplatform_symlink_guard_hardening.py`) originally ran `git
commit` + `git_helpers.run_git(["log", ...])` in-process and compared to
the literal `subject` used to create the commit — a genuine round-trip
(§34-compliant, no fixture), but Moriarty proved it doesn't actually pin
`run_git()`'s explicit `encoding="utf-8"` kwarg: this dev machine's ambient
`PYTHONUTF8=1` silently forces UTF-8 decoding process-wide, so the test
stayed green even with the kwarg deleted from `subprocess.run(...)`. Same
root cause already documented for `open_no_follow_symlink()` in
`TestEncodingIndependentOfPythonUtf8Env`
(`test_crossplatform_symlink_guard.py:422`) — same fix applies to
`run_git()`.

**Fix:** run the real round-trip (real `git commit`, real `git log` via
`run_git()`) inside a **child subprocess** with `PYTHONUTF8=0` forced and
`PYTHONLEGACYWINDOWSFSENCODING` popped from env, so a missing `encoding=`
kwarg falls back to the locale's ANSI codepage (cp1252) instead of being
masked. The child imports the REAL `lib/git_helpers.py` (via
`sys.path.insert(0, LIB_DIR)`), calls `run_git()`, and prints the result as
`json.dumps({...})` with the default `ensure_ascii=True` — this keeps the
parent↔child pipe pure ASCII (all non-ASCII \uXXXX-escaped) so a mangled
*console* codepage in the test harness itself can never masquerade as a
mangled *file*-decode round-trip. Keep the accented/emoji `subject` OUT of
the child's `-c` argv entirely (only ASCII paths like `tmp_repo`/`LIB_DIR`
are embedded) — it stays in the parent process and is only compared
against the child's decoded-back JSON at the end.

**Verified as Moriarty would**: built a scratch copy of `git_helpers.py`
with the `encoding="utf-8"` kwarg deleted, pointed a throwaway duplicate
script's child subprocess at that scratch copy — confirmed RED with the
exact mojibake Moriarty predicted
(`'ðŸ”§ ... corazÃ³n, seÃ±al, aÃ±o ...'`). With the real, unmodified
`lib/git_helpers.py` (kwarg present): GREEN. Scratch copy discarded after
verification, never committed.

## Test-input text that echoes back into output can make a keyword assertion pass vacuously — audit marker names against every regex they're near

When a test writes a commit message / file / marker string that a script
under test PRINTS BACK VERBATIM (confirmation lines like
`bin/git-memory-commit.py`'s `_print_commit_result()` echo the commit
`message` argument), and the same test then does `re.search(r"<keyword>",
combined_output)` to prove some NEW feature added that keyword to the
output, the assertion can pass today — before the feature exists — purely
because the test's OWN input text happened to contain the keyword. Caught
live in `test_boot_freshness.py`'s write-path warn-only test (Task 1 test
8): the commit message was `"proceed despite being behind"`, and the
regex checking for a new "behind" warning matched the echoed message
itself, making a RED-should-be test pass GREEN for the wrong reason before
any warning logic existed. Same root cause hit a second time in the same
file: `INCIDENT_NEXT_MARKER = "INCIDENT-REMOTE-NEXT-..."` and
`b_remote_marker = "B-REMOTE-NEXT-MARKER"` both contained the substring
"REMOTE", which a `re.search(r"remot", line, re.IGNORECASE)` check (meant
to prove a NEW remote-provenance LABEL was added next to the marker) would
match on the marker's own name alone, regardless of whether the label
existed.

**Fix / prevention**: before writing an assertion `re.search(r"<kw>",
text)`, grep every string LITERAL the test itself writes into that same
commit/file/env (commit messages, trailer values, marker constants,
filenames) for that keyword (case-insensitive) and rename any collision.
Prefer marker names built from a scope name + a short random-looking
suffix (e.g. `"B-NEXT-MARKER-77c2"`) that avoids every word the test's own
regexes search for. This is a variant of the codebase's existing "make the
PoC real" / anti-fixture-fabrication family of gotchas — the bug isn't in
what's asserted, it's in the test's own input data secretly satisfying the
assertion. Always run the new test once against UNMODIFIED (pre-fix)
production code and confirm every physical test method is genuinely RED,
not just the file as a whole — running with `-x` can hide a vacuously
green test sitting after a real failure.

## Windows fake-`git` process-tree kill test — CreateProcess ignores Popen's `env=` for executable SEARCH; must mutate the real process PATH instead

Closing the two Windows-only gaps in `test_boot_freshness_regression.py`
(`_win32_kill_tree`/taskkill, and `_ASKPASS_FAILFAST == "cmd /c exit 1"`)
that were previously documented as "no Windows machine available" —
session 2026-07-07, first real Windows box for this suite.

**Platform quirk confirmed empirically (not in any doc, easy to get
wrong)**: on POSIX, `execvpe`/`subprocess.Popen(["cmd"], env={"PATH":
fake_dir, ...})` resolves the executable using the `env` dict passed in —
this is exactly what the existing POSIX fake-git-on-PATH pattern relies
on. On Windows, `CreateProcess` (which is what `Popen(["git"]+args,
shell=False)` compiles down to when no `executable=` is given) resolves
the bare command name using the CALLING process's OWN live PATH
environment block — the `env=` kwarg only populates the CHILD's
environment AFTER the executable has already been found and started. So
`git_helpers.run_git(["fetch"], env={"PATH": fake_bin + ...})` is a
silent no-op for redirecting which "git" runs on Windows: the real
system git still executes, and a naive test assuming POSIX semantics
gets a fast, wrong-looking pass/fail (confirmed: got `rc=128` "unable to
access... getaddrinfo() thread failed to start" from the REAL git,
looking like a plausible network failure, not "wrong git ran").

**Fix for Windows tests that need a fake `git` on PATH**: use
`monkeypatch.setenv("PATH", fake_bin + os.pathsep + os.environ.get("PATH",
""))` (or plain `os.environ["PATH"] = ...` with manual restore) on the
TEST process itself before calling the function under test — this
mutates the real live env block `CreateProcess`'s search consults. The
`env=` kwarg passed to `run_git`/`Popen` is still useful (and still
production-faithful) for populating the CHILD's own environment (e.g.
`PYTHONPATH` below), just not for the executable search itself.

**Second problem, specific to needing a fake "git" that does real work
on Windows**: `CreateProcess`'s implicit search only auto-appends `.exe`
— it does NOT consider `.bat`/`.cmd` the way `cmd.exe`'s own PATHEXT
-driven resolution does. A `git.bat` dropped on the prepended PATH dir is
silently skipped in favor of the real `git.exe` found later in the
search — confirmed by direct experiment (a `git.bat` printing a sentinel
and exiting 7 was never invoked; real git ran instead). So the fake must
be a genuine PE executable, not a script with a shebang-like batch file.

**Working technique**: copy a REAL python interpreter binary to
`fake_dir/git.exe` — but NOT `sys.executable` directly if the test
process might be running under a venv/poetry env (its `python.exe` is
often a small launcher stub that locates the real interpreter via a
`pyvenv.cfg` file relative to ITS OWN path; copied elsewhere with no
`pyvenv.cfg` alongside it, the stub fails to start). Use
`os.path.join(sys.base_exec_prefix, "python.exe")` instead — always the
base, non-venv install regardless of what venv is active, safe to copy
and relocate. Then set `PYTHONPATH` (via the real `env=` kwarg, which DOES
work for child-env population) to a directory containing a
`sitecustomize.py` that does the real fake-git logic (spawn a real
grandchild via `subprocess.Popen([sys.executable, "-S", "-c", "import
time; time.sleep(60)"])`, write its pid to a file, `time.sleep(60)`
itself). This works because Python's `site` module imports
`sitecustomize.py` during interpreter STARTUP — before it ever attempts
to open `argv[1]` ("fetch", the git subcommand) as a script file — so
the hijack fires unconditionally, with no valid python script needing to
exist on disk at all. The `-S` flag on the grandchild's own invocation is
required to stop it from ALSO importing the same `sitecustomize.py` and
recursively spawning further "grandchildren."

**Third gotcha — `tasklist` output encoding**: `subprocess.run(["tasklist",
"/FI", f"PID eq {pid}"], text=True)` with the DEFAULT (UTF-8) encoding
raises `UnicodeDecodeError` on a non-English Windows locale (confirmed:
Spanish Windows, byte `0xe0`) — `tasklist`'s console output uses the
OEM/ANSI codepage, not UTF-8. Fix: `encoding="oem", errors="replace"` on
the `subprocess.run` call. This is a liveness probe, not a content
assertion, so `errors="replace"` is safe — never let an unrelated
locale-encoding mismatch fail a process-liveness check.

Verified end-to-end manually (outside pytest) before writing the actual
test: fake git.exe hangs, `run_git(timeout=1)` returns `(1, "")` in
~1.2s, grandchild pid written, and dies (confirmed via `tasklist`) within
the 5s polling deadline after `run_git` returns — proving
`_win32_kill_tree()`'s real `taskkill /F /T /PID` genuinely kills the
whole tree, not just the direct "git.exe" child. Classes:
`TestWin32ProcessTreeKillOnTimeout`,
`TestWin32AskpassFailfastResolvesAndExitsNonzero` (the latter needed no
new technique — just `subprocess.run(_ASKPASS_FAILFAST + " " + prompt,
shell=True)`, faithfully reproducing how git invokes a multi-token
GIT_ASKPASS command line on Windows).


# From mock-patterns.md

## Python Pytest — Hook Subprocess Testing Pattern

Hooks under `unmassk-toolkit/hooks/` are tested as subprocesses via `conftest.run_cmd`.
Conftest is in `unmassk-toolkit/tests/conftest.py`. Key helpers:

```python
# Run hook with JSON stdin (mirrors Claude Code's invocation contract):
rc, stdout, stderr = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=json_str)
parsed = json.loads(stdout)
hso = parsed.get("hookSpecificOutput", {})

# Or use the _run_hook() helper defined in the test file (wraps run_cmd):
rc, parsed, raw_stdout, stderr = _run_hook(repo, "Task", tool_input_dict)
```

`SOURCE_ROOT` = `unmassk-toolkit/` dir. `HOOKS_DIR` = `unmassk-toolkit/hooks/`. `LIB_DIR` = `unmassk-toolkit/lib/`.

For `recall()` calls in helper functions, pass `_repo_dir=repo` — do NOT use the default (which resolves git root of the real project repo).

### Fail-open invariant pattern (deny/block test)
```python
output_str = json.dumps(json.loads(stdout))
assert "deny" not in output_str.lower()
assert "block" not in output_str.lower()
```

## Python Hook — importlib Direct Import Pattern (not subprocess)

When testing a single function inside a hook file (not the full hook via subprocess),
import with `importlib.util.spec_from_file_location` — avoids the sys.modules collision
risk of `importlib.import_module` and the global pollution of `exec()`.

```python
import importlib.util

HOOKS_DIR = os.path.join(SOURCE_ROOT, "hooks")

def _import_hook(monkeypatch):
    monkeypatch.syspath_prepend(HOOKS_DIR)
    monkeypatch.syspath_prepend(os.path.join(SOURCE_ROOT, "lib"))
    spec = importlib.util.spec_from_file_location("hook_module_name", HOOK_FILE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
```

Then patch module-level constants AFTER loading:
```python
hook = _import_hook(monkeypatch)
monkeypatch.setattr(hook, "PLUGIN_VERSION", "1.10.0", raising=False)
```

`raising=False` is required when the attribute does not yet exist (pre-implementation, RED tests).

## SessionStart hook — subprocess invocation (no stdin)

`session-start-crew.py` takes no stdin — it is a pure SessionStart hook that
reads `CLAUDE.md` from the git root. Invoke via `run_script(HOOK_PATH, repo)`
with NO `input_text`. The `cwd` IS the repo root (hooks call
`git rev-parse --show-toplevel` to find CLAUDE.md).

```python
def _run_hook(repo):
    return run_script(HOOK_PATH, repo)
```

## PostToolUse hook — exit_code must be cast with try/except

`post-validate-commit-trailers.py` receives `tool_output.exit_code` which can be
a non-int (string word, list) from exotic tool outputs. The correct pattern is:

```python
try:
    if exit_code is not None and int(exit_code) != 0:
        sys.exit(0)
except (ValueError, TypeError):
    pass  # treat as success / fail-open
```

Always wrap `int(exit_code)` in try/except in PostToolUse hooks — fail-open on
uncastable values.

## Simulating a not-yet-written Windows code branch from any host OS (no real Windows, no symlink privilege needed)

To contract-test a future `if sys.platform == "win32":` branch before it
exists (test-first pass), patch the GLOBAL singleton attributes the branch
will read — `monkeypatch.setattr(sys, "platform", "win32")`,
`monkeypatch.setattr(os.path, "islink", lambda p: True)`,
`monkeypatch.setattr(os, "lstat", ...)` / `monkeypatch.setattr(os, "fstat",
...)`. Because every module does a plain `import os` / `import sys`, they
all share the same module objects — patching the global attribute once
affects every importer, including modules not yet written. This works
identically whether the test process is real Windows or POSIX CI, and needs
zero real symlink privilege. For `os.lstat`/`os.fstat`, a duck-typed stub
class exposing only `.st_dev`/`.st_ino` is enough — no need to construct a
real `os.stat_result`.

To verify a rejected-path guard "closes the fd, never leaks it" once that
logic exists: wrap `os.open`/`os.close` with spy functions that record every
real fd before delegating to the real implementation, call the target inside
`pytest.raises(OSError)`, then assert `closed_fds == opened_fds` afterward.
Confirmed in `unmassk-toolkit/tests/test_crossplatform_symlink_guard.py`
(Windows/macOS/Linux compat fix, Task 1, session 2026-07-06): `os.O_NOFOLLOW`
does not exist on Windows, so ALL of these tests are RED today via an
unhandled `AttributeError` from the twin functions' unconditional reference
to it — `pytest.raises(OSError)` does not catch `AttributeError`, so it
propagates as the (correct) failure signal without any extra assertion
needed.

For the one thing that genuinely CANNOT be mocked (real kernel-level
O_NOFOLLOW enforcement on a real symlink): use a `real_symlink_capable`
fixture that attempts a real `os.symlink()` in `tmp_path` and calls
`pytest.skip(...)` if it raises `OSError` (confirmed: `[WinError 1314]` on a
Windows box without Developer Mode / SeCreateSymbolicLinkPrivilege) — never
fake kernel symlink-following behavior with a mock and call it equivalent.

## Fake `git` that spawns a real grandchild — testing process-group kill without mocking os.killpg

To regression-test that a subprocess wrapper's timeout path (`git_helpers.
run_git`'s `os.killpg(getpgid(pid), SIGKILL)`) kills the WHOLE process
group, not just the direct child, write a fake `git` script (same PATH-
shadowing technique as above) whose body itself calls `subprocess.Popen
(...)` — with NO `start_new_session=True` of its own — to spawn a real
sleeping grandchild (`sys.executable -c "import time; time.sleep(60)"`),
writes the grandchild's pid to a file, then hangs. Because the fake git
was launched by the wrapper under test with `start_new_session=True`, it
already leads a fresh POSIX process group; a child it spawns normally
inherits that SAME group (no explicit setsid needed on either side). Call
the real wrapper with a short `timeout=1`, then poll `os.kill(grandchild_
pid, 0)` for up to ~5s after it returns (`ProcessLookupError` = dead;
`PermissionError` counts as still-alive) to prove the whole tree died —
this observes REAL kernel process-group signal delivery, no `os.killpg`
mock anywhere. Confirmed in
`unmassk-toolkit/tests/test_boot_freshness_regression.py::
TestPosixProcessTreeKillOnTimeout` (session 2026-07-06). POSIX only — the
Windows counterpart (`taskkill /F /T`) has no real-machine way to verify
here; don't substitute a `subprocess.run` mock and call it equivalent (see
[feat-boot-freshness-contract-notes](feat-boot-freshness-contract-notes.md)
for the full rationale on why that would be a vacuous test).

## Hardening-pass direct-call testing — when subprocess isolation is NOT needed

Not every real, stably-named `lib/` module function needs the full
subprocess-isolation dance (`_extract_memory()`'s `python3 -c` snippet
pattern above). Three cheaper patterns, all confirmed safe in
`test_boot_freshness_hardening.py` (session 2026-07-06):

1. **Pure functions** (no I/O, no git, no module-level mutable state) —
   import the real module directly at the top of the test file (`import
   boot_git_checks`, `import boot_memory`) and call the function in-process.
   Safe even though these are the same stably-named modules the
   sys.modules-stub-contamination warning above targets, BECAUSE the
   contamination risk only bites module-level `from x import y` bindings
   evaluated once at first import — a pure function with no such imports in
   its own call chain has nothing to go stale.
2. **Functions taking an explicit path param** (e.g. `fetch_memory_ref
   (project_root)`, `_has_toolkit_memory(project_root)`) — call directly
   with a real `tmp_path` repo, no chdir needed at all; the function's own
   `run_git(..., cwd=project_root)` calls already scope everything.
3. **Functions relying on ambient process cwd** (no `cwd=` passed to their
   own `run_git` calls, e.g. `get_ahead_behind(branch)`) — use pytest's
   `monkeypatch.chdir(repo)` fixture, which auto-restores the real cwd after
   the test; safe against cross-test bleed within the same session.

**Gotcha — process-global cache defeats direct calls for one specific
function family:** `lib/boot_glossary_cache.py` has a **module-level
mutable cache**, `_project_root_cache: str | None = None`, set once by
`_get_project_root()` and never invalidated. Any test that calls
`_read_glossary_cache()` / `_write_glossary_cache()` / `extract_glossary_
cached()` directly against a SECOND (different) `tmp_path` repo in the same
pytest process will silently resolve to the FIRST repo's cached root unless
you explicitly reset the global first: `boot_glossary_cache._project_root_
cache = None` before `monkeypatch.chdir(new_repo)` + the call. This is a
lighter fix than `test_security_regression.py`'s full subprocess-per-call
pattern (`_call_write_glossary_cache_fallback`) — reach for the subprocess
version only when the test ALSO needs to patch a defensive-import fallback
(`ensure_runtime_dir = None`) or otherwise needs true process isolation;
for a plain "different repo, different cache file" test, resetting the
global in-process is sufficient and much faster (confirmed: `_resolve_
origin_sha`/`_read_glossary_cache` migration tests, session 2026-07-06).

## Injecting malformed git output to test a fail-open branch (not just non-zero exit)

To exercise a specific parsing branch inside a `lib/` function that calls
`run_git()` MULTIPLE times for different subcommands (so you can't just
monkeypatch the whole function), monkeypatch the single shared
`git_helpers.run_git` attribute with a wrapper that intercepts only the
target subcommand shape (`if args and args[0] == "rev-list" and
"--left-right" in args: return 0, "abc def"`) and delegates everything else
to the REAL `run_git` (saved as `real_run_git = git_helpers.run_git` before
patching). Because the target function does a deferred, function-body
`from git_helpers import run_git`, this takes effect immediately with no
module-reload needed — `monkeypatch.setattr(git_helpers, "run_git", ...)`
auto-restores after the test. This is what found a genuine bug (documented
in [edge-cases.md](edge-cases.md) and
[feat-boot-freshness-contract-notes](feat-boot-freshness-contract-notes.md)):
`get_ahead_behind()`'s `int()` conversion on `rev-list --left-right --count`
output has no try/except, unlike the sibling "wrong token count" fallback
one line below it.

## Forcing a controlled (returncode, stdout, stderr) out of `run_git()` without a real git failure

`lib/git_helpers.py:run_git()` calls `subprocess.Popen(["git"] + args, ...)`
then `proc.communicate(timeout=...)` then reads `proc.returncode`. To test a
branch that only fires on a SPECIFIC exit code + stderr combination (e.g. the
`log_stderr_on_failure` diagnostic-breadcrumb kwarg, issue-driven Cerberus
follow-up, session 2026-07-08) — don't try to make a real git command fail
with a specific stderr string; monkeypatch `subprocess.Popen` itself with a
duck-typed fake:

```python
class _FakeProc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.pid = 424242
        self._stdout, self._stderr = stdout, stderr
    def communicate(self, timeout=None):
        return self._stdout, self._stderr

monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: _FakeProc(1, stderr="fatal: x"))
code, out = git_helpers.run_git(["status"], log_stderr_on_failure=True)
```

Patch the `subprocess` module the TEST FILE already imported (`import
subprocess` at file top) — it is the same object in `sys.modules` that
`git_helpers.py`'s own `import subprocess` resolved to, so no need to reach
into `git_helpers.subprocess` specifically. This is the same "patch the
module that owns the callee's globals" principle as the `_write_glossary_
cache()` gotcha in unmassk-toolkit-python-test-conventions.md, just applied
to a stdlib module instead of a project one. Since `run_git()`'s print is
gated by a 4-operand conditional (`log_stderr_on_failure and returncode != 0
and stderr and stderr.strip()`), enumerate all the ways it can flip: flag
True/False/omitted, returncode 0 vs non-zero, stderr empty/whitespace-only/
real text, and the `[:300]` truncation boundary (`"X"*300 in captured.err`
+ `"X"*301 not in captured.err` proves the exact cutoff, not just "some
truncation happened"). Confirmed in
`unmassk-toolkit/tests/test_boot_freshness_hardening.py::
TestRunGitLogStderrOnFailure` (7 tests, all via `capsys` since the print
happens in-process — no subprocess wrapper needed for THIS assertion,
unlike the fake-git-on-PATH pattern above which is for asserting the
*subprocess's own* env/argv).

## Fake `git` that mangles a specific `%`-token to inert literal text — simulating "old git can't expand this directive" without a real ancient git binary

Extends the fake-git-on-PATH pattern above one step further: to reproduce
what happens when an old git release doesn't recognize a specific
pretty-format directive (e.g. `%aI`, ISO-8601 date), rewrite that literal
substring to plain non-`%` text INSIDE any `--pretty=format:` arg before
delegating to the real git binary — since the rewritten text no longer
contains a `%` placeholder, real git emits it verbatim, exactly matching
how an old git emits an unrecognized directive (literally, unexpanded).
This needs no fake-command-logging/hanging machinery, just a 3-line rewrite
loop over `sys.argv[1:]`. Crucially, any OTHER `%` token in the same format
string (e.g. `%at`, unix epoch — much older and universally supported) is
left untouched, so this technique proves a migration fix works: run the
SAME "hostile" PATH against code that has already switched from the
mangled token to the untouched one, and it must produce correct output.
Confirmed in `unmassk-toolkit/tests/test_date_parsing_epoch_contract.py`
(issue #55, session 2026-07-08) reproducing two real degradations end-to-
end: `bin/git-memory-gc.py`'s H2 stale-blocker heuristic
(`if not commit["date"]: continue`) and `bin/git-memory-doctor.py`'s
`check_gc_status()` (both its stale-blocker count and "days since last GC"
figure) silently stop firing when `%aI` can't be expanded, because the
project's own `parse_date()` swallows the resulting `ValueError` to `None`.
Each test runs the real-git control pass FIRST (setup-sanity assertion — a
real backdated commit, via `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` env, must
already trigger the heuristic with unmodified git) before switching PATH to
the mangling fake and asserting the contract still holds.

## Discriminant test to prove a signal moved from file/source X to file/source Y — delete X, assert Y is untouched

When a fix's whole point is "the freshness/state signal must stop coming
from source X (e.g. a file git itself writes as a side effect) and must
come from a new, application-owned source Y instead," a plain "do the
happy-path round trip" test (write via the new mechanism, read it back
immediately) is NOT a real discriminant — it typically already passes
today via the OLD (wrong) mechanism too, since X and Y are both freshly
written at the same moment in the common case. Prove it moved by making
the two sources diverge: after the producing action, **delete or corrupt
X outright** (not age it — genuinely remove it), then re-run the read path
and assert the SAME correct output still comes back. If the code still
secretly depends on X, deleting it flips the observable output (forces a
real recompute / falls back to a different, distinguishable state); if the
signal genuinely lives in Y now, X's disappearance has zero effect.
Confirmed in `test_boot_freshness.py::TestOwnSuccessStampNotFetchHeadMtime::
test_round_trip_own_stamp_survives_fetch_head_deletion` (issue #60
AMENDMENT v2, session 2026-07-10): deleting `.git/FETCH_HEAD` after a real
successful fetch, then re-booting inside the rate-limit window, must still
render "remote (synced ...)" from the new own-stamp source — confirmed RED
against the unfixed code (which forces a real refetch instead, flipping
the status to "fetched"), for exactly the predicted reason.

Companion technique for the SAME family of bug — proving X gets falsely
credited by two independent categories of "ambient touch" the fix must
reject: (a) a FAILED write/side-effect to X (e.g. a failed `git fetch`
still truncates+refreshes `FETCH_HEAD`'s mtime — verified with a bare
shell repro against a nonexistent-path remote BEFORE writing any test,
confirmed real git behavior, not a bug to "fix" in git itself), and (b) a
successful write to X caused by something UNRELATED to the feature (e.g. a
fetch of a totally different, foreign remote, which touches the same
non-per-remote `FETCH_HEAD` file). Both need their own test — a fix that
closes (a) doesn't automatically close (b) and vice versa. See the "Vector
A" / "Vector B" tests in the same class.

## Patching `subprocess.Popen` directly, cross-platform, instead of PATH-shimming "git" — `tests/_git_intercept.py` (issue #60 close-out round 2, session 2026-07-10)

Supersedes the PATH-shim entry above for `lib/git_helpers.py:run_git()`'s
exact call shape (`subprocess.Popen(["git"] + args, shell=False)`; see
that entry for why PATH-shimming can never work here on Windows). Shared
module `unmassk-toolkit/tests/_git_intercept.py` exports
`make_intercepted_popen(real_popen, log_path)`: a Popen-shaped wrapper
that (1) logs every git invocation's `args` (excluding the leading "git"
token — same JSONL shape the old fake-git-on-PATH shim produced, so every
pre-existing `r["args"][0] == "fetch"` assertion needed zero changes) and
`env` actually received, (2) delegates UNCHANGED to the real `Popen` for
everything except one case, (3) for a `git fetch` whose env carries
`FAKE_GIT_FETCH_HANG_SECONDS`, swaps the argv for a REAL
`[sys.executable, "-c", "import time; time.sleep(N)"]` child before
delegating — so `run_git()`'s own `communicate(timeout=...)` and
`os.killpg()`/`_win32_kill_tree()` process-group-kill paths are exercised
against a genuinely hung real process, never synthesized. All other
kwargs (`cwd`, `env`, `stdout`, `stderr`, `creationflags`/
`start_new_session`) pass through untouched, so the killed child is still
the leader of its own process group exactly as before.

Two install vehicles share this one implementation:
1. **Subprocess** (a real boot launched via `tests/conftest.py`'s
   `run_script()`, i.e. `[sys.executable, script]` with no `-S`/`-I`):
   `test_boot_freshness.py::_make_fake_git(tmp_path, log_path)` now
   writes a `sitecustomize.py` (not a `git`/`git.cmd` executable) into a
   scratch dir, self-contained (bakes the absolute `tests/` dir path into
   its own source so it can `import _git_intercept` without any extra
   `sys.path`/`PYTHONPATH` entry beyond itself). The CALLER prepends that
   dir to the child's **`PYTHONPATH`** (never `PATH` — nothing is being
   shadowed anymore) via `_fake_git_env(fake_bin, log_path, extra=None)`,
   which also sets `GIT_INTERCEPT_LOG_PATH` in the child's env. `site`
   imports `sitecustomize.py` automatically at interpreter startup
   (because `run_script()`'s invocation has no `-S`/`-I`), which calls
   `_git_intercept.install_via_env()` — reads `GIT_INTERCEPT_LOG_PATH`
   from `os.environ` and patches `subprocess.Popen` inside the CHILD
   process before `session-start-boot.py`'s own code ever runs.
2. **In-process** (a test calling a `lib/` function directly, e.g.
   `boot_git_checks.fetch_memory_ref()` — no subprocess at all):
   `monkeypatch.setattr(subprocess, "Popen", make_intercepted_popen(subprocess.Popen, log_path))`
   — patches the REAL `subprocess` module's own `Popen` attribute (not
   `git_helpers.subprocess`, not any re-exported reference); works
   regardless of how `git_helpers.py` imported `subprocess` because
   `import subprocess` binds the SAME module object from `sys.modules`,
   and `run_git()`'s `subprocess.Popen(...)` call looks up `.Popen` fresh
   at call time. `pytest`'s `monkeypatch` auto-restores it — no
   `install()`/`uninstall()` bookkeeping needed for this vehicle.
   Confirmed in `test_boot_freshness_hardening.py::TestFetchMemoryRefStates::
   test_hung_fetch_is_bounded_by_timeout_and_returns_failed` (migrated off
   `monkeypatch.setenv("PATH", ...)` this round).

**Populated-log guard for `assert not fetch_calls` tests** — a negative
assertion on the fake-git call log (`assert not fetch_calls`) passes
VACUOUSLY if the interceptor never engaged at all (exactly the blind spot
that caused this whole migration), indistinguishable from a genuine
"correctly skipped" result. Pair every `assert not fetch_calls` with
`assert records` (the log is non-empty overall — the boot always runs
OTHER real git commands regardless of whether it fetches) BEFORE the
narrower fetch-specific check. Verified as a real discriminant, not
decorative, via a live mutation-kill: monkeypatching `_looks_like_git()`
to always return `False` (simulating "interceptor silently never
engages") made all three `assert records`/`assert fetch_calls` guards
fail for exactly the predicted reason (empty log), confirmed byte-for-byte
file restoration afterward via `diff` before re-running the real suite.

**Cross-platform BY CONSTRUCTION, not by a POSIX/Windows branch** — unlike
the old `_make_fake_git()` (which forked into a POSIX shim vs a
`git.cmd`/`fake_git.py` pair based on a `WINDOWS` module constant), the
new `_make_fake_git()` has no platform branch at all: the exact same
`sitecustomize.py`-on-`PYTHONPATH` mechanism, exercised identically on
macOS/Linux/Windows, since `subprocess.Popen` patching never touches OS
executable-resolution machinery. Verification limit (documented, not
silently assumed): local verification here (macOS) exercises this IDENTICAL
code path Windows CI will run — there is no separate Windows branch left
to verify locally. What's still Windows-CI-only: whether `site` truly
imports `sitecustomize.py` from a `PYTHONPATH` entry the same way on a
real Windows Python install (expected per CPython's own `site` module
contract, not previously exercised on a real Windows runner for this
project).

## HARD RULE — never write a mutation-check throwaway file into a shared production dir (`unmassk-toolkit/lib/memory/` and equivalents)

**Rule, effective 2026-08-02, coordinator-issued mid-session stop:**
mutation-check throwaway modules (the "write a fake implementation, run
the suite against it to prove assertions aren't vacuous, then delete
it" technique used across
[vocabulary-contract-notes](vocabulary-contract-notes.md),
[zones-py-full-contract-notes](zones-py-full-contract-notes.md),
[rejection-contract-notes](rejection-contract-notes.md)) must NEVER be
written into a directory other agents write to concurrently — not even
for one bash command, not even if deleted immediately after.

**Why:** during the memoria-v2 build (`feat/memoria-v2`), multiple
Dante/Ultron instances write into `unmassk-toolkit/lib/memory/` in
parallel across different files. A `rejection.py` mutation-check there
nearly clobbered a colleague's real in-progress file, and even after
deleting the `.py` source, a stray `__pycache__/rejection.cpython-
314.pyc` was left behind — `importlib.util.spec_from_file_location` +
`exec_module()` writes bytecode cache as a side effect, and `rm`-ing
the `.py` does NOT remove it. Caught only because the coordinator
audited the directory after the fact; the fix cost a second round-trip
that a correctly-scoped check would never have needed.

**How to do it instead — always:**
1. Inside a pytest test: use `tmp_path` (pytest fixture, auto-cleaned,
   never touches the real dir) and point
   `importlib.util.spec_from_file_location` at a file under it.
2. Outside pytest (ad-hoc Bash verification before writing the final
   test): use the session scratchpad
   (`/private/tmp/claude-*/.../scratchpad/`) or a private `/tmp` dir —
   never the project's `lib/memory/` (or any dir a teammate is
   concurrently writing to).
3. If neither is possible for what needs verifying: don't do the
   check. Report to the coordinator what verification is missing and
   let them decide — an unverified test is recoverable; a clobbered
   teammate file (or its cache-artifact aftermath) may not be.

**How to apply:** every time before running a mutation-check, ask "is
this directory owned solely by me for this task, or shared with
parallel agents right now?" If shared (memoria-v2's `lib/memory/` is
the current live example, but the rule is general), redirect the fake
file to an isolated path FIRST — never write-then-delete in place.
