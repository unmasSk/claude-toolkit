---
name: deuda17-freshness-disclosure-contract-notes
description: DEUDA.md #17 RED contract — PULL DIRECTIVE / BRANCHES must disclose local remote-tracking data may be stale (no git fetch in boot anymore); keyword-OR technique for wording-agnostic text assertions
metadata:
  type: project
---

Test-first contract pass (2026-08-04), `unmassk-toolkit/tests/test_boot_git_checks.py`
only — no production code touched, Ultron implements next.

**The gap (DEUDA.md point 17):** memory v2 removed the boot's own `git
fetch` entirely (`run_preboot_migrations()`'s docstring says so). But two
outputs still compute off local-only data as if nothing changed:
`_build_pull_directive_lines()` (behind-count from `get_ahead_behind()`,
pure local `rev-list`) and `render_branches_section()` (branch list from
`get_remote_branches()`, reads `refs/remotes/<remote>/*` "as they sat after
the last fetch" — its own docstring already said this before this task).
Neither function's returned text says the data might not reflect the real
remote. Not a crash — a lie by omission, which is this project's one
declared threat model ("the system against itself").

**Which functions "produce the text" (load-bearing distinction the task
asked to resolve before writing anything):** of the four functions named in
DEUDA #17, only two return rendered text (`list[str]`) —
`_build_pull_directive_lines()` and `render_branches_section()`. The other
two (`get_ahead_behind()`, `get_remote_branches()`) return raw tuples with
no text at all. The assertion belongs on the two text-producing functions,
called directly (pure/near-pure unit calls), not on the full boot log —
routing the assertion through `render_branch_section()`'s full boot output
would let one function's disclosure text leak into the other's assertion
and mask a fix that only patched one of the two.

**Wording-agnostic assertion technique** (task's own instruction: "sin
atarlo a una frase literal... no quiero un test que se ponga rojo al
reescribirlo"): a small `FRESHNESS_DISCLOSURE_KEYWORDS` OR-tuple —
`("confirm", "stale", "fresh", "verify", "verified", "outdated", "up to
date", "up-to-date")` — checked case-insensitively against the joined
returned lines via `_discloses_unconfirmed_freshness()`. Verified empirically
against the CURRENT (pre-fix) output of both functions before writing the
assertion — none of the eight keywords appear anywhere in today's text, so
the RED is for the right reason (missing disclosure), not an unrelated typo
in the keyword list. This is the same "OR of plausible-phrasing candidates"
shape this file's own `TestPullDirective`/`TestBootSuppressesPull...`
classes already use (e.g. `"dirty" in combined.lower() or "uncommitted" in
combined.lower()`), just generalized to a tuple since more than two
plausible words apply here.

**`render_branches_section()` fixture — confirmed empirically, no fetch
call needed:** `git push -u origin main` (the existing `_add_bare_remote()`
helper) already populates `refs/remotes/origin/main` locally as a side
effect of the push itself — verified live with a throwaway probe repo
before writing the test. No separate `git fetch` step needed to get a
non-empty BRANCHES section in the fixture, unlike `TestPullDirective`'s own
`_setup_behind()` (which fetches because it needs the SECOND machine's
pushed commits to be visible locally, a different reason).

**Scope decision left to the report, not decided here:** DEUDA #17's own
text offers two legitimate fixes — disclose, or retire both outputs while
there's no fetch. The task instructed writing the RED contract for
"disclose" (task's own directive: "LA CONDUCTA QUE FIJAS: esas dos salidas
dicen que el dato no está confirmado..."), so retirement was not
independently chosen here — it was pre-decided by the task, not evaluated
as an open question in this pass.

RED confirmed: `python3 -m pytest test_boot_git_checks.py -q` → 3 failed
(exactly the 3 new tests, clean AssertionError showing today's literal
output for each) + 41 passed + 1 skipped (unchanged baseline, same 41+1 as
before this pass). Exit code checked directly, no piping through
`tail`/`head` before reading pass/fail counts.

See also [boot-fetch-prune-contract-notes](boot-fetch-prune-contract-notes.md)
(same "no fetch in boot" lineage, one gap over — the fetch-side of this
same #17 family) and [boot-branches-section-contract-notes](boot-branches-section-contract-notes.md)
(the other file that already covers `render_branches_section()`'s
data-correctness contract; this pass adds the disclosure-text contract in
`test_boot_git_checks.py` instead, per this task's explicit single-file
scope).
