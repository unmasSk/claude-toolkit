---
name: ci-fake-gh-path-fallthrough-fix-notes
description: CI red (ubuntu-latest + windows-latest) on the fake-gh-on-PATH technique; POSIX execvp EACCES-fallthrough proven, Windows CreateProcess .exe-only proven; conftest.path_without_real_gh() fix + explicit win32 skip
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
