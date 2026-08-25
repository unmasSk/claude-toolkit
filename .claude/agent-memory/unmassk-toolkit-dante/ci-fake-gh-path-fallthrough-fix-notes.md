---
name: ci-fake-gh-path-fallthrough-fix-notes
description: CI red (ubuntu-latest + windows-latest) on the fake-gh-on-PATH technique; POSIX execvp EACCES-fallthrough proven, Windows CreateProcess .exe-only proven; conftest.path_without_real_gh() fix + explicit win32 skip. Round 2 (2026-08-25): same function's directory-level filter took git down with gh on ubuntu-latest (git+gh share /usr/bin) -- fixed to filter by file via a symlinked scratch dir
metadata:
  type: project
---

2026-08-22, urgent: CI red on both matrix legs (ubuntu-latest,
windows-latest) for `test_note_issue_field.py`, `test_work_issue_field.py`,
`test_report_render_issue_field.py` -- all three used the same
`_fake_gh_dir()` + `_env_with_fake_gh()` pattern (`PATH = fake_dir +
os.pathsep + os.environ["PATH"]`), which passed locally (17/17, gh
authenticated) but failed on CI runners where a REAL `gh` is installed
but unauthenticated. CI stderr was literally gh's own auth-wall message
-- proof the REAL binary executed, not the fake.

**Root cause, measured by reproduction, not assumed** (see
[[note-issue-field-seven-types-contract-notes]] for the original
technique this bug was in):

- POSIX (ubuntu-latest/macOS): `execvp`/`posix_spawnp` does NOT raise on
  `EACCES` for the first PATH candidate -- it silently continues to the
  next PATH entry. Proven live: `chmod(0o644)` on the fake `gh` (instead
  of `0o755`) made `subprocess.run(["gh", ...])` execute the REAL `gh`
  on this machine, producing the exact class of error CI showed. Simply
  prepending the fake dir to PATH is not enough -- a real `gh` sitting
  anywhere later in PATH is a silent fallback the moment the fake can't
  execute for ANY reason.
- Windows: `subprocess.run(["gh", ...])` with `shell=False` (production's
  own call in `validator_issue.py`, never touched) resolves via Win32
  `CreateProcess`, which auto-appends ONLY `.exe` when no extension is
  given -- never `.cmd`/`.bat`/extensionless (well-documented Python/
  Windows subprocess gotcha, same reason `.bat`/`.cmd` need
  `shell=True`). An extensionless `gh` fake file can **never** be found
  by production's exact invocation, structurally, on any Windows
  machine -- not a CI-specific flake.

**Fix (test-only, `conftest.py::path_without_real_gh()`)**: build the
child's PATH as `fake_dir + os.pathsep + <inherited PATH minus every
directory that contains a real gh/gh.exe/gh.cmd/gh.bat>`. This
generalizes a pattern that already existed, narrowly, in
`test_work_issue_field.py::_path_without_gh` (only used for its "gh not
installed" case) to all three files. Effect: if the fake ever fails to
execute for any reason, there's nothing left to fall through to --
`validator_issue.issue_exists()`'s own `except OSError` converts it into
a loud, clearly diagnosable `RuntimeError` ("no se pudo ejecutar 'gh'"),
never a silent real-`gh` masquerade. Verified live: with the fake
non-executable AND `path_without_real_gh()` applied, the failure changed
from the auth-wall message to the clean `RuntimeError` text.

**Windows: skipped explicitly, not faked green.** Added
`_skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason=
"...")` to every class/test that depends on the fake winning PATH
resolution (not the ones testing "gh entirely absent", which don't need
the fake to win at all). Making Windows genuinely green would require
either a real, verifiable `.exe` stub (couldn't fabricate/verify one
without a Windows machine) or a production change (e.g. `shutil.which()`
-based resolution in `validator_issue.py`, PATHEXT-aware) -- explicitly
out of scope, reported rather than guessed at. Full local suite
(darwin, so the skip doesn't trigger): 513 passed, 1 skipped
(pre-existing), 84s.

**Lesson**: "prepend fake dir to PATH" is not sufficient by itself for a
test double meant to intercept a bare-name `subprocess.run([name, ...])`
call -- always ALSO strip any real candidate from the rest of PATH, so
an execution failure fails loud instead of silently falling back to the
real dependency.

## Round 2 (2026-08-25): the 2026-08-22 fix itself broke `git` on ubuntu-latest

CI run 32895458657, commit d9cec70, Yoda's system pass (M-126): 37 tests
red on ubuntu-latest with "git no encontrado" -- never reproduced locally.
Root cause: `path_without_real_gh()` filtered by DIRECTORY (dropped every
PATH entry containing a real `gh`), correct only while `gh` and `git` live
in different directories (true on this macOS dev machine, Homebrew `gh` vs
Xcode CLT `git`). On `ubuntu-latest`, both binaries live together in
`/usr/bin` -- dropping the directory took `git` down with it. Same shape
as Round 1's lesson, one level deeper: filtering too coarse a unit (a
whole directory) hides a real dependency that happens to share ground
with the fake target.

**Fix**: filter by FILE, not by directory. When a PATH entry contains a
real `gh`, don't drop the entry -- rebuild it in a scratch dir with a
symlink to every OTHER entry (falls back to `shutil.copy2` per-entry only
if symlinks aren't supported), and swap that scratch dir in instead.
`git` (or anything else sharing the directory) stays reachable; only `gh`
disappears. Cached per real directory (`_SANITIZED_GH_FREE_DIRS`), cleaned
via `atexit`, never inside the test (the returned PATH can still be live
inside a running subprocess when the test function returns).

**Verification technique for "can't reproduce locally" CI-only bugs**:
built a synthetic single-directory PATH (`git` + `gh` both written into
one fresh `tempfile.mkdtemp()`, mimicking `/usr/bin`) rather than trusting
the dev machine's real PATH -- the real PATH already keeps `git`/`gh`
apart, so testing against it silently masks the exact bug being fixed.
Confirmed the OLD filter logic (re-implemented inline, not imported) lost
`git` entirely (`shutil.which("git")` -> `None`) on that synthetic PATH,
and the NEW filter kept it (`shutil.which("git")` -> path inside the
sanitized scratch dir, `gh` absent from its listing). Proving the old code
COULD reproduce the failure is what makes the new code's pass meaningful
-- a demonstration that never breaks under the pre-fix code proves
nothing.

**Scope note**: this round's task limited edits to `conftest.py` only.
Pytest's `python_files = ["test_*.py"]` config (`pyproject.toml`) means a
`def test_...` inside `conftest.py` is never collected -- so the
CI-scenario demonstration above was run ad hoc (not committed as a
permanent regression test), reported EXECUTED. A permanent automated
version of this demonstration would need a new `test_*.py` file, which
is outside this round's declared limits -- flagged, not silently added.

## Round 3 (2026-08-26): the flagged follow-up approved, made permanent

New file `tests/memory/test_conftest_path_without_real_gh.py` (7 tests,
0 skips, no Windows gate needed -- unlike Round 1's tests, these never
actually invoke `git`/`gh` as subprocesses, only check filesystem
presence/content through the returned `PATH`, so the whole file is
cross-platform by construction). Each test builds its OWN synthetic
"`/usr/bin`-like" directory (`git` + `gh`, sometimes a third binary,
written by the test itself) via `monkeypatch.setenv("PATH", ...)` --
never the dev machine's real PATH, which already keeps `git`/`gh` apart
and would mask the exact bug. Covers: git survives when sharing a
directory with a real gh, the shared directory itself gets replaced (not
emptied), a third binary in that directory also survives, no directory
in the result contains a real `gh`/`gh.exe`/`gh.cmd`/`gh.bat`, the
sanitized copy is cached per real directory (two calls return the same
string), and the symlink-unsupported fallback (`os.symlink` forced to
raise via `monkeypatch.setattr`) still produces a working real-copy
entry, content-compared against the original.

**RED-with-old-logic proof, done right**: reimplementing the OLD
directory-drop logic INSIDE the permanent test file would duplicate
production code inside a test (banned) and the file itself can't hold
two competing versions of the SUT. Instead: a throwaway script
(scratchpad, never committed) imported the real test module, replaced
its imported `path_without_real_gh` name with the pre-fix
implementation via `pytest.MonkeyPatch()`, and called each test method
directly (own `tmp_path`/`monkeypatch` built manually, `mp.undo()` in a
`finally`). Result: the 3 tests that assert "git stays locatable" all
went RED with the exact CI symptom message ("git ya no es localizable
tras filtrar -- PATH resultante: ''"); 2 tests stayed green even under
the old logic, correctly -- one checks gh-absence (old logic also
achieves that, crudely, by nuking the whole directory) and one checks
call-to-call cache stability (trivially true when both calls return the
same empty string). Not every test in a suite needs to fail against the
old bug; only the ones asserting the specific invariant that broke
should, and confirming that split (which fail, which don't, and why) is
what makes the RED proof meaningful rather than decorative.

Verified: new file green ×3 runs (7/7 each), together with
`test_conftest_smoke.py` + the 3 Round 1/2 files (50/50), no leaked
`path-without-gh-*` scratch dirs in the OS temp dir after any run
(autouse fixture pops `_SANITIZED_GH_FREE_DIRS` keys created during each
test and `shutil.rmtree`s them, same pattern as the module's own
`atexit` cleanup, at test scope instead of process scope).

## Round 4 (2026-08-26): Round 3's own permanent test file broke on windows-latest

CI run 32904954108: 3 of the 7 tests in `test_conftest_path_without_real_gh.py`
red on windows-latest, green on ubuntu-latest with the exact same code
(`test_git_stays_locatable_after_filtering_a_shared_directory`,
`test_a_third_binary_sharing_the_directory_also_survives`,
`test_symlink_unsupported_falls_back_to_a_real_copy_of_just_that_entry`
-- all three via `shutil.which()`). Root cause confirmed by reading
`shutil.which()`'s actual source (`inspect.getsource`), not assumed: on
`win32`, `which()` only inserts the bare queried name into its candidate
list when that name ALREADY ends with a `PATHEXT` extension; a bare name
like `"git"` is only ever checked as `"git" + ext` for each `PATHEXT`
entry (`.COM`, `.EXE`, `.BAT`, ...), never as the literal `"git"` itself
(with the default `mode` including `X_OK`). The synthetic binaries in
Round 3 were written with bare POSIX-style names on all three platforms
-- invisible to `shutil.which()` on Windows even though the file genuinely
existed in the returned `PATH`.

**Fix**: `_binary_name(base)` = `base + (".exe" if sys.platform == "win32"
else "")`, used for BOTH writing the synthetic binary's filename and for
the `shutil.which()` query -- never just one side. `sys.platform`, not
`os.name`, to match this suite's own convention everywhere else
(`test_work_issue_field.py`/`test_note_issue_field.py`/
`test_report_render_issue_field.py`/`gitcmd.py` all use
`sys.platform == "win32"`). No Windows skip anywhere -- the three tests
run for real on every platform, just against the name each platform's
own resolver expects. `test_windows_style_gh_names_are_also_filtered`
(pre-existing, not touched) was never broken -- it already used literal
`.exe` names, which is exactly why it was absent from the Windows
failure list; that's what pointed at the extension, not the filter
logic, as the real cause.

**Verifying a Windows-only code path without a Windows machine**: full
`shutil.which()` can't even be called with `sys.platform` monkeypatched
to `"win32"` on macOS/Linux -- it dereferences `_winapi` internally,
which is `None` off real Windows (`AttributeError: 'NoneType' object has
no attribute 'NeedCurrentDirectoryForExePath'`, confirmed by trying).
Worked around by isolating just the candidate-list construction (the
`if sys.platform == "win32":` branch's `pathext`/`files` lines, copied
VERBATIM from the source already read via `inspect.getsource`, not
retyped from memory) into a standalone ad hoc function and running that
in isolation, with Windows's own `;`-separated `PATHEXT` format hardcoded
(this machine's `os.pathsep` is `:`, which would silently corrupt the
`PATHEXT.split()` if reused) -- confirmed `"git"` never appears as a
candidate, `"git.exe"` always appears first. This is real executed
evidence for the MECHANISM, not the full Windows runtime -- the actual
CI result is still declared UNVERIFIED-en-Windows until the next run
confirms it end to end (filesystem case-folding, real `PATHEXT` content
on the runner, etc. remain genuinely unexercised here).

Verified locally (POSIX, `_EXE_SUFFIX == ""`, so this is also a
no-regression check for the already-green platforms): new file green ×3
(7/7 each), together with `test_conftest_smoke.py` +
`test_work_issue_field.py`/`test_note_issue_field.py`/
`test_report_render_issue_field.py` (50/50). `conftest.py` untouched
(`git status` empty throughout) -- the whole fix lives in the test file,
per this round's declared limits.
