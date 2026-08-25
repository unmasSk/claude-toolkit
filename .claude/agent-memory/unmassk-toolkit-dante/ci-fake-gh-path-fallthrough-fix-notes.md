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
