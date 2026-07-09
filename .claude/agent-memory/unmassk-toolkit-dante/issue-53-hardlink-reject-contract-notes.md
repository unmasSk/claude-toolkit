---
name: issue-53-hardlink-reject-contract-notes
description: Contract notes for the F6 hard-link bypass closure (reject_hardlinks opt-in param, issue #53, design owned by Argus decision 51a3c44) — test-first, written before Ultron implemented anything
metadata:
  type: project
---

Issue #53 closes F6, a residual documented (and, until now, deliberately
accepted per decision 51a3c44) in both `open_no_follow_symlink()` twins
(`lib/git_helpers.py` / `lib/_symlink_safe_open.py`): a hard link planted at
a guarded path is indistinguishable from an ordinary file to
`os.path.islink()` and to POSIX `O_NOFOLLOW`. Argus's design: add an
OPT-IN `reject_hardlinks: bool = False` param to both twins; when True,
raise `OSError` if `os.fstat(fd).st_nlink > 1` (checked on the ALREADY-OPEN
fd, never the path — TOCTOU discipline). Default False keeps every
existing call site (none pass this param today) byte-identical, since
Argus found the naive always-on version breaks legitimate hard links
between git worktrees pointing at the same user file (CLAUDE.md,
settings.json, package.json, .gitignore, scopes).

Contract file: `unmassk-toolkit/tests/test_hardlink_reject_guard.py`
(new file, sibling of `test_crossplatform_symlink_guard.py`, reuses its
`TWIN_FUNCS` dict via import rather than redefining it — same pattern the
hardening file for that contract already used).

**Platform-coverage decision, different from the symlink guard's Windows
tests:** `os.link()` needs NO special privilege on Windows (unlike
`os.symlink()`, which needs Developer Mode/SeCreateSymbolicLinkPrivilege —
that's why `real_symlink_capable` exists). So these tests do NOT
monkeypatch `sys.platform` — they run the REAL, unmocked branch for
whichever host OS pytest is actually on (confirmed live on this Windows
dev box: `os.link()` works, exercises the real Windows hybrid branch for
real). Added a parallel `real_hardlink_capable` fixture to `conftest.py`
(same skip-not-silently-assume pattern as `real_symlink_capable`) for CI
runners/filesystems that might reject hard-link creation (network mounts,
some overlay/tmpfs configs) even though it works everywhere tested so far.

**Independent-channel rejection verification, adapted from the plan's
instruction:** the codebase already documents `errno.ELOOP` as
deliberately REUSED across two semantically different Windows symlink
rejections (see `git_helpers.py`'s own docstring) — so a bare errno match
would NOT by itself prove a hard-link rejection fired for the hard-link
reason rather than some other coincidental OSError. Used a **differential
control** instead: `TestRejectHardlinksTrueRejectsMultilinkFile` (must
raise) is paired with `TestRejectHardlinksExplicitFalseAllowsMultilinkFile`
(must NOT raise) on the exact same fixture shape (real hard link via
`os.link()`, `st_nlink` read back via `os.stat()` — never hardcoded to
literal `2`, per §34) — only the `reject_hardlinks` flag differs between
the two tests, isolating it as the actual cause. Paired with a softer
second signal: the raised `OSError`'s message must contain hard-link
vocabulary (`"hard" in msg and "link" in msg`, case-insensitive) — flexible
enough not to dictate Ultron's exact wording.

**RED baseline confirmed 2026-07-09:** all 14 tests that pass
`reject_hardlinks=True` or `reject_hardlinks=False` explicitly fail with
`TypeError: ...unexpected keyword argument 'reject_hardlinks'` on BOTH
twins — the correct RED-for-the-right-reason (grepped every failure
line, zero divergent failure reasons). The 4 GUARD tests
(`TestRejectHardlinksParamOmittedPreservesCurrentBehavior` — call the
twins with NO `reject_hardlinks` arg at all, on a real multi-link file)
pass GREEN now, proving the new contract is purely additive. Full existing
`test_crossplatform_symlink_guard*.py` suite (46 passed, 4 skipped) stayed
green after the `conftest.py` fixture addition — no collateral damage.

See also: [unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)
for the general repo pytest conventions (TWIN_FUNCS pattern,
`real_symlink_capable`/skip-guard discipline this file's
`real_hardlink_capable` mirrors).

**Post-implementation ripple, fixed 2026-07-09:** once Ultron wired
`write_boot_log()` to actually pass `reject_hardlinks=True` at its real
call site, two UNRELATED tests in `test_boot_output.py`
(`TestBootLogWriteFailureFallback`,
`TestBootLogWriteFailureLogsWarning`) broke — not because the new param's
behavior was wrong, but because their fixed-arity monkeypatch stub
`_raise_permission_error(path, mode="w", encoding="utf-8")` (helper
`_run_boot_with_failing_log_write()`, ~line 845) doesn't accept unknown
kwargs, so the call raised `TypeError` instead of the `PermissionError`
the test simulates. Fix: widen the stub to `**kwargs` — do NOT touch the
assertions, since the fallback/warning contract itself never changed.
**General lesson:** any test double that stands in for
`open_no_follow_symlink()` (or any twin function likely to gain future
opt-in params) should accept `**kwargs` from the start, not just fixed
positional/keyword args — otherwise every unrelated feature that adds a
new opt-in param to the real function silently breaks doubles elsewhere
in the suite that were never touched by that feature's own test file.
