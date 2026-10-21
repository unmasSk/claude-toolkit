---
name: subagent-walls-hook-contract-notes
description: D-171/D-174 SubagentStart walls hook RED contract -- real gitmem note R args, customs blocks scratch git commit, throwaway-impl satisfiability check
metadata:
  type: project
---

Test file: `tests/hooks/test_subagent_walls_contract.py` (2026-10-21, issue #91, Short procedure).

- **Real `gitmem note R` in a throwaway repo** needs `zones.json` seeded plus `--why`, `--description`, `--stops yes`, `--searched <text>`; without `--stops` it bounces with "falta una respuesta". Pass git identity env explicitly: `tests/hooks/conftest.run_cmd` injects none.
- **The customs hook blocks `git commit` typed in Bash even inside the scratchpad.** Put scratch git setup in a Python script file and run that.
- **Test-first satisfiability check:** in an rsync copy in the scratchpad, write a 20-line throwaway implementation + registration and confirm the RED suite can go fully GREEN, then mutate it. This caught nothing here, but it proves no test is unsatisfiable before Ultron sees it.
- Pinned choices: payload `cwd` over process cwd, nearest project wins, stderr line names RESTRICTIONS.md.
