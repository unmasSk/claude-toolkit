---
name: issue-63-producer-hardening-contract-notes
description: issue #63 wip f0313d8 PRODUCER-hardening regression contract (install_apply.apply_plan manifest-stamp gate + upgrade_check.trigger_auto_upgrade_if_needed returncode breadcrumb) — the front test_crew_content_gate_v2.py explicitly deferred out of scope
metadata:
  type: project
---

New file: `unmassk-toolkit/tests/test_issue63_producer_hardening.py` (6
tests). Covers the PRODUCER-side front that
[issue-63-p1-v2-content-gate-contract-notes](issue-63-p1-v2-content-gate-contract-notes.md)
explicitly called out as out of scope ("hardening the PRODUCER itself...
a second contract for that front was explicitly deferred to a separate
task") — now fixed by Ultron in wip f0313d8 and locked in here.

**Behavior A — `lib/install_apply.py::apply_plan()`'s `create_manifest`
branch now gated `if not errors`.** Reused the exact sabotage technique
`test_crew_content_gate_v2.py::_run_sabotaged_producer()` already
established (monkeypatch `install_apply.open_no_follow_symlink` to raise
`PermissionError` ONLY for `mode=="w"` + `basename==CLAUDE.md`, real
subprocess, real `apply_plan()` call) — 3 tests: fresh target (manifest
must stay absent), target with a REAL prior install whose manifest
version was downgraded to `0.0.1` on disk (manifest must stay
byte-identical to its pre-sabotage-run content — expected value is what
was read from disk moments earlier, never hand-typed, per §34), and the
happy-path control (no sabotage → manifest stamped with `VERSION`).

**Behavior B — `lib/upgrade_check.py::trigger_auto_upgrade_if_needed()`
now prints a stderr breadcrumb (`"[git-memory] upgrade fail-open: install
--auto exited N: ..."`) on `returncode != 0`.** Built a NEW helper,
`_run_trigger_upgrade()`, distinct from `test_hardening_recall.py`'s
`TestFailOpenUpgrade._run_boot_with_sabotaged_installer()` — that file
drives the FULL `hooks/session-start-boot.py::main()` channel and its
`test_installer_nonzero_exit_does_not_break_boot` (written before this
fix) only asserts `rc==0`/`STATUS:` present, never the breadcrumb text —
a real coverage gap this file closes by calling
`upgrade_check.trigger_auto_upgrade_if_needed()` directly (unit-level,
narrower and faster) against a REAL fake installer script (`sys.exit(1)`
writing to its own stderr) rather than monkeypatching `subprocess.run`
itself. 3 tests: non-zero exit → breadcrumb present, names the returncode,
embeds the installer's own stderr text, never says "success"; zero exit →
no breadcrumb (control); genuine `subprocess.run()` exception (OSError,
via the same monkeypatch shape `test_hardening_recall.py` uses) → still
fails open, still breadcrumbs via the pre-existing (unchanged) except
branch. A `"TRIGGER_DONE"` stdout marker distinguishes "function returned
normally" from "rc==0 but the wrapper script crashed before reaching that
line" — rc alone doesn't prove the function under test actually
completed.

**Both mutation-checks done manually this session** (Edit → run only the
affected test(s) → confirm RED for the right reason → Edit back →
`git diff --quiet` confirmed clean), per the project's established
discipline (not self-mutating pytest code):
- A: reverted `if not errors:` → `if True:` — both the fresh-target and
  prior-install tests went RED (manifest genuinely got re-stamped to
  current `VERSION` despite the sabotaged failure).
- B: reverted `if result.returncode != 0:` → `if False:` — the
  non-zero-returncode test went RED (`stderr == ''`, no breadcrumb).

**Verification**: new file alone ×5 loops, 6/6 every run, no flakiness.
Full suite `python3 -m pytest unmassk-toolkit/tests -q` run BOTH ways
(foreground with 480s timeout AND background as a cross-check, same
discipline as
[issue-63-t1-manifest-read-hardening-notes](issue-63-t1-manifest-read-hardening-notes.md)) —
both **1278 passed, 2 skipped (Windows-only baseline), exit 0**, ~306s
runtime (needs a >2min bash timeout — the default 120s times out
mid-run and looks like a hang, not a failure; user explicitly asked not
to end the turn only waiting on the background job, so the foreground run
is the one whose numbers are authoritative here). `git diff --quiet` on
`lib/install_apply.py` and `lib/upgrade_check.py` confirmed clean after
every mutation-check round — no residual diff in production code, only
the new test file is untracked.

See also: [issue-63-p1-v2-content-gate-contract-notes](issue-63-p1-v2-content-gate-contract-notes.md)
(the consumer-gate contract this producer fix was deferred out of),
[issue-61-ci-flake-hardening-notes](issue-61-ci-flake-hardening-notes.md)
(foreground-vs-background full-suite verification pattern this reuses).
