---
name: install-protected-branch-d157-contract-notes
description: D-157 RED contract -- installer makes no commit on gitflow main; two doors (boot_launcher first install, crew upgrade), and why the upgrade setup needs a stale manifest
metadata:
  type: project
---

File: unmassk-toolkit/tests/memory/test_install_protected_branch_no_commit.py (2026-10-20, test-first Short).

- Gitflow without hand-seeding config.json: `git init -b main` + `git branch develop` -> installer deduces repo_type gitflow itself (install_inspect._deduce_repo_type). Single branch -> trunk.
- Customs blocks `git commit` typed in the Bash tool: probe scripts must commit from Python subprocess.
- Upgrade door trap: session-start-crew.py's content gate rewrites an outdated CLAUDE.md block ITSELF, without the installer -> no commit even today. To reach the installer's commit, ALSO stamp manifest.json version old (gitignored, tree stays clean). Committed older block + stale manifest = the fe040683 shape.
- Crew runs AFTER boot_launcher writes the report: an upgrade's leftovers can only show in the NEXT boot's report.
- Report line pinned wording-free: one line with "instal" + (commit|confirm|git), accent/case-normalized.
- "Not staged" test is green today only because the commit consumes the index: green-by-design guard.

**How to apply:** any later D-157 fix pass or a change to where the installer commits.

Fix pass (2026-10-20, Ultron's «Beyond the tests»):
- Marker removal is only observable as a FALSE warning: protected install -> work branch -> `git-memory-install.py --auto` (apply_plan commits every run) -> owner edits .gitignore -> boot must carry no install line.
- `git status` failing while the boot still runs: overwrite `.git/index` with garbage; status fails, log answers, boot completes.
