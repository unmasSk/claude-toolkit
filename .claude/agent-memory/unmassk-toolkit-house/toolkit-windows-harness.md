---
name: toolkit-windows-harness
description: Windows-only reds in unmassk-toolkit where the test harness is POSIX-only and the product is fine — PATH stubs, shlex backslashes, shell=True, HOME, CRLF, autocrlf
metadata:
  type: reference
---

Split out of toolkit-ci-and-tests.md on 2026-10-19 (that file passed 300 lines).
Tell for the whole file: Ubuntu green + Windows red + macOS green.

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
  **Same class, second home (2026-10-19, run 39167842007, I-006):** `lib/merge_gate_target.py::tokenize`
  (shlex posix) — `tests/test_pre_merge_gate.py` interpolated `str(tmp_path)` unquoted, 12 Windows
  reds, all "target could not be read". Rewrites do not inherit scars: the as_posix rule was not
  applied to the new test file. Faithful Mac end-to-end repro with the REAL hook: put the session
  repo under a directory literally named `a\b`; unquoted path → heavy/unknown, quoted → approve,
  and `bash` itself fails the same `cd`. The merge gate's `_join_path` also lacks the `/c/` translation.
- **`subprocess.run(<hooks.json command>, shell=True)` is POSIX-only.** On Windows `shell=True` is
  `cmd.exe /c`, which never expands `${CLAUDE_PLUGIN_ROOT}` → python gets a literal path, rc=2.
  Any test that "runs the hook as Claude Code runs it, from hooks.json" needs the win32 skip
  (`boot_hook_harness.POSIX_ONLY` and `test_owner_cue_contract` have it; `test_d124_*` did not).
- **Extensionless fake `gh` + `path_without_real_gh()` without the win32 skip** turns the product's
  "gh exists / does not" path into "gh not installed" on Windows — no `Relanza:` block. Mac
  simulation: run the scenario with `PATH=path_without_real_gh()` and no stub dir.
- **CLAUDE.md written by `open_no_follow_symlink(..., atomic=True)` is uniform CRLF on Windows**
  (`os.fdopen` text mode, no `newline=`). A test reading it back with `newline=""` and asserting
  LF literals (`startswith`, `endswith`, `count(block)`) is POSIX-only; older crew tests normalize.

