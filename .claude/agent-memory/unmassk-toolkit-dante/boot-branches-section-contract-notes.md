---
name: boot-branches-section-contract-notes
description: BRANCHES boot section (get_remote_branches/render_branches_section, lib/boot_git_checks.py) gap-fill test contract — origin/HEAD alias fixture gotcha, mutation-check on the cap
metadata:
  type: project
---

Linear-mode gap-fill (2026-07-15): Ultron shipped `get_remote_branches()` /
`render_branches_section()` in `unmassk-toolkit/lib/boot_git_checks.py`
(BRANCHES boot section, `BOOT_MAX_REMOTE_BRANCHES = 20`) without a dedicated
test file. Filled in `unmassk-toolkit/tests/test_boot_branches_section.py`
(16 tests, all real-git, no fabricated fixtures). No production code
touched — code was already correct, no bug found.

**origin/HEAD alias gotcha (load-bearing for the exclude-HEAD test)**:
`git clone` only auto-creates the symbolic `refs/remotes/<remote>/HEAD`
alias when the bare remote **already had a branch before being cloned**.
An empty-bare-then-push-after-clone sequence (the shape most existing
fixtures in this suite use, e.g. `test_boot_freshness.py::_setup_freshness_repo`)
never creates that alias — verified live with two probes. Any fixture that
needs to exercise the HEAD-exclusion path must seed the bare repo with a
commit *first*, then clone it (`_seed_bare()` in this file does exactly
that) — the freshness-repo pattern will silently make that assertion
vacuous.

**Real git's HEAD short-name shape**: `%(refname:short)` for
`refs/remotes/<remote>/HEAD` renders as the bare remote alias
(`"origin"`), NOT `"origin/HEAD"`, on the git version tested here. The
production code's `ref_short == f"{remote_name}/HEAD"` equality branch is
therefore never the branch that actually fires the exclusion in practice
— the `not ref_short.startswith(prefix)` check catches it first, since
`"origin".startswith("origin/")` is False. Confirmed via live probe
before writing the test; not something to "fix", just a note for whoever
next touches that function — the equality check may be defensive for an
older/different git version's rendering, kept as dead-in-practice-here
code, not asserted against directly (would require mocking `git_helpers.run_git`
to fake a line git itself never produces — rejected per §34: don't test
your own mock).

**Cap test performance**: pushing exactly `BOOT_MAX_REMOTE_BRANCHES` (20)
new branches (plus the pre-existing `main` = 21 total, `remaining=1`) is
the minimum fixture that proves capping — no need to overshoot to 23+ for
"safety margin"; 16 tests including the cap-with-20-branches one run in
~4.7s total.

**Mutation-check performed** (manual, one-time, not committed as a test):
monkeypatched `boot_git_checks.BOOT_MAX_REMOTE_BRANCHES = 999999` at
runtime against a real 25-branch repo and re-ran `render_branches_section()`
— confirmed the cap test's `len(shown_branch_lines) == BOOT_MAX_REMOTE_BRANCHES`
assertion flips from pass to fail (20 -> 26 shown), proving the assertion is
load-bearing, not vacuous.

**Scope waiver applied**: `_is_safe_remote_name()`'s allowlist guard
(rejects a glob/shell-metacharacter remote name) was deliberately NOT
tested here — per this project's CLAUDE.md, attacker-model tests are
surplus (single-owner toolkit, no hostile-input threat model). Noted
explicitly in the "Not tested" list rather than silently skipped.

See also [pending-next-cutoff-contract-notes](pending-next-cutoff-contract-notes.md)
for the underlying in-process `monkeypatch.chdir()` + direct-import call
pattern this file reuses (no subprocess/fake-git needed for pure
data/render functions — `git_helpers.run_git`'s `cwd=None` inherits the
real process cwd).
