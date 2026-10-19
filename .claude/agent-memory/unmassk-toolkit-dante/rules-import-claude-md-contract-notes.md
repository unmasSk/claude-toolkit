---
name: rules-import-claude-md-contract-notes
description: #95 2a contract -- managed-block @import of rules.md; expandability parser, rule.py round-trip, scratch satisfiability check
metadata:
  type: project
---

Contract file: unmassk-toolkit/tests/memory/test_rules_import_at_boot_contract.py (13 RED + 2 golden, 2026-10-19).

Patterns worth reusing:
- Text-in-a-managed-block contracts: drive the REAL writers (session-start-crew.py via run_hook_with_payload, git-memory-install.py --auto), parametrized, never upsert_managed_blocks() directly.
- "Claude Code will expand this @import" = own parser: stripped line is a single `@token`, outside ``` fences and multi-line <!-- --> comments (docs: imports not evaluated in code spans/blocks, resolve relative to the importing file).
- Round-trip the import path against the real producer (`rule.py ... --kind user --quote`, needs seed_config_json repo_type=trunk), not a hand-typed path.
- Cross-seam: a prefix the block tells Claude to look for must be one boot_launcher.py really prints at line start.
- Old block for upgrade tests = frozen literal snapshot (it vanishes from code once the change lands).
- Before reporting RED, satisfiability check: copy unmassk-toolkit to scratchpad, `git init` only (NO commit -- customs hook blocks `git commit`; tests/memory guard needs a git toplevel or it errors with FileNotFoundError ''), apply a candidate body, run; then wrong variants (backticks, fence, wrong path, wrong prefix) must go red.

**Why:** a wording contract can be unsatisfiable or too loose; the scratch candidate proves neither.
**How to apply:** any future test-first change to CLAUDE.md managed-block text.

Fix pass (2026-10-19, Argus SEC-MED-001 + Cerberus F2):
- The installer (`git-memory-install.py --auto`, also run by boot_launcher.py on a repo with no manifest) overwrites ~/.local/bin/gitmem. Any test reaching it needs a disposable HOME: autouse fixture with monkeypatch.setenv HOME+USERPROFILE (subprocesses inherit os.environ), plus a guard test asserting the launcher landed under the fake HOME. Detect offenders empirically: run each file with HOME=<scratch dir> and check <scratch>/.local/bin/gitmem.
- Cross-seam boot tests must check the SECOND boot_launcher run (first one installs and prints its own `[memory]` notice, which masks a broken everyday path); assert manifest exists between runs.

Rules read-now hint (2026-10-19, linear): tests/memory/test_crew_rules_hint_on_import_added.py, 10 tests through session-start-crew.py.
- Hint lives in lib/rules_hint.py (moved from the hook mid-task; tests survived the move because they read stdout only).
- Detect the hint by path + "read" + "now" words; negatives assert NO stdout line mentions rules.md at all (robust to rewording).
- Silent cases worth keeping: import already in owner's text outside the block (hint compares PRE-write content), and subfolder cwd (rules resolved from git root).
- Mutant scripts must target the file the code lives in NOW: grep before mutating -- a str.replace on a moved function silently no-ops and every mutant "survives".
