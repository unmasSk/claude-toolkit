---
name: d070-skip-ci-marker-contract-notes
description: D-070 skip-ci RED contract (gitmem work/wip add [skip ci], release never does) -- line-anchor regression risk, 3/6 points RED, 2 were already-true controls
metadata:
  type: project
---

Task (2026-08-28): pin, in RED, D-070 (`gitmem search --id D-070`) --
`work.py`/`wip.py` must append `[skip ci]` on its OWN line;
`bin/release.py` must NEVER carry it (its commit is the only one that
triggers CI, verifying everything since the last release). File:
`unmassk-toolkit/tests/memory/test_ci_skip_marker.py` (new), plus one
updated test in `test_wip_script.py`, plus one new test in
`test_release.py`.

**The real risk this whole contract exists to prevent:**
`health_plans.py::_ISSUE_TRAILER_RE = re.compile(r"^Issue: #(\d+)$",
re.MULTILINE)` is anchored to a WHOLE line. If the skip-ci marker ever
landed on the SAME line as the `Issue: #N` trailer, that regex would
silently stop matching -- the boot safety net ("N commits sin reflejar")
would undercount with zero error. Point 2's test calls the REAL regex
via `import_lib_memory_module("health_plans")`, never a copy, so a
future rewrite of that regex changes this test's meaning with it instead
of leaving it lying.

**Verified split before writing a line, exactly like
[[work-issue-validation-gap-contract-notes]] warns to do -- ran the
file, didn't infer red/green from reading:** 3 of 6 points are RED for
the right reason (1: plain work commit has no marker at all; 2: --issue
commit has no marker either, `Issue: #4242` trailer alone confirms this;
4: wip commit has no marker). 3 are GREEN, and correctly so:
- Point 3 (boot safety net still counts a marked `work --issue N`
  commit) is GREEN TODAY BY COINCIDENCE -- nothing has broken the
  line-anchor yet because no marker exists yet. It's a regression guard
  that stays inert until Ultron's implementation exists, then starts
  protecting for real. Verified via the SAME `_patch_gh`-style in-process
  `subprocess.run` monkeypatch technique as `test_health.py` (health_plans
  runs in-process, unlike work.py/wip.py which run as subprocess) --
  `import_lib_memory_module("health_plans")`, call `plans_unreflected()`
  under `os.chdir(tmp_repo)`, patch only `cmd[0] == "gh"` calls, let real
  `git log` through untouched.
- Point 5 (release commit never carries the marker) is GREEN TODAY --
  `bin/release.py` already commits via `notes.write_work()` directly with
  no marker anywhere in today's code. Left as an explicit guardian
  (`TestReleaseCommitNeverCarriesTheSkipCiMarker` in `test_release.py`):
  if the marker ever migrated into the SHARED `notes_commit.py::
  write_work()` assembly point (line 507, `f"{message}\n\nIssue: #{issue}"`)
  instead of staying in the two scripts that must add it, release would
  inherit it silently and stop triggering CI on publish -- an unverified
  release landing in silence. Regex: `re.search(r"\[?skip[- ]ci\]?", msg,
  re.IGNORECASE)`, deliberately looser than the positive-side check (see
  below) to catch ANY variant, not just the exact literal.
- Point 6 (`test_wip_script.py`'s stdout-echo assertion) was flagged by
  the task as genuinely AMBIGUOUS -- pinned it to "stdout equals the
  FULL committed message" (round-trip against real `git log`, never a
  hand-rebuilt string), not "just the marked subject" (the old
  assertion). This is also GREEN today by coincidence (no issue trailer,
  no marker yet, so subject == full message already) but becomes a real
  guardian once Ultron adds the marker: if he appends it to the commit
  body but forgets to also change what prints (or vice versa), this
  test catches the mismatch.

**Surprising, and worth restating for whoever reads this next:** the
task prompt warned that `test_work_script.py`/`test_work_issue_field.py`
"already assert on committed message text and will legitimately need
updating." Read every assertion in both files before touching anything
-- ALL of them use `.startswith(...)` or `"Issue: #N" in message`
(substring/prefix checks), never exact full-message equality. A
substring check can't be broken by appending unrelated lines elsewhere
in the message, so **neither file actually needed a single edit** --
confirmed by running both green, unchanged, in the same suite as the 3
new reds. Only `test_wip_script.py` had a real
`out.strip() == f"[WIP] {marker} <msg>"` full-equality assertion, and
that's the one point 6 correctly targeted. Lesson: a prompt's "these
will need updating" is a hypothesis to verify by reading every
assertion, not a checklist to execute blindly -- verified 90/93 tests in
the three "moving" files needed zero changes.

**Positive-marker regex, deliberately exact, not the loose guard-side
one:** `_SKIP_CI_OWN_LINE_RE = re.compile(r"^\s*\[skip ci\]\s*$",
re.IGNORECASE | re.MULTILINE)` -- checks the literal `[skip ci]` D-070
itself cites (`gitmem search --id D-070`), case-insensitive only for
capitalization, never inventing an unrequested variant like `skip-ci`
without brackets for the POSITIVE assertions (points 1/2/4). The
guard-side test (point 5, "never on the release commit") uses the wider
`\[?skip[- ]ci\]?` on purpose -- a negative guard should catch more
shapes than the positive contract requires, since ANY variant leaking
into release is the failure being defended against.

Fake-gh technique for `--issue N` (points 2/3): trimmed-down local copy
of `test_work_issue_field.py::_fake_gh_dir` (`mode="exists"` only, no
`missing`/`unrelated_error` -- those infra-failure branches are already
covered there, out of scope for this file) + `path_without_real_gh()`
from `conftest.py`, same `_skip_on_windows` reason (Windows
`subprocess.run(["gh"])` without `shell=True` never resolves an
extensionless file via CreateProcess).

Full suite verification: `python3 -m pytest unmassk-toolkit/tests -q`
(run in background, ~180s) -> `3 failed, 1287 passed, 2 skipped` --
exactly the 3 new RED, zero collateral damage anywhere else in the
1287+2 baseline.

See also: [[work-issue-validation-gap-contract-notes]] (the fake-gh
technique this borrows from, and the "run before inferring red/green"
lesson this repeats one level up -- per-point, not just per-test),
[[note-issue-gate-work-quote-contract-notes]] (the fake-gh-on-PATH
pattern's origin and the CI PATH-filtering incident this reuses via
`conftest.py::path_without_real_gh`).
