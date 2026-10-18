---
name: checklist-by-procedure-d121-contract-notes
description: D-121 flow checklist by procedure (Trivial/Corto/Completo) RED contract — schema I fixed, which guards are green-by-design
metadata:
  type: project
---

D-121 (#101 A3) contract in tests/hooks/test_checklist_by_procedure.py (2026-10-18).

- The orchestrator gave the mechanism but NOT the JSON shape of `procedures`; the test file fixes it in its docstring:
  `{"Trivial": {"selector", "boxes": []}, "Corto": {"selector", "boxes": [...]}, "Completo": {"selector"}}` — Completo has no `boxes`, uses top-level. If Ultron picks another shape, the contract file is the arbiter; tell the orchestrator.
- Completo-selected and "Corto+Completo both on board" tests are GREEN today by design (the current gate always expects the full list) — they guard against Corto winning after the change, not RED contract. Declare them as such, don't report them as missing RED.
- Gate tests seed multi-entry registries directly (own `_seed_entries` helper; conftest's `seed_registry` only writes one entry without extra keys).
- Inject tests with `procedures`: call `make_manifest()` (for cleanup tracking), then overwrite the returned path with the full dict.

**Why:** the shape choice is mine, so a later round must check it against what Ultron built before "fixing" tests.
**How to apply:** in the hardening pass, re-read the hooks first; mutation targets: selector lookup, Trivial → empty, bigger-list tie-break, per-entry filtering (audit untouched).

**Fix pass after Cerberus (2026-10-18):** an e2e "gate stays silent" test is vacuous unless it first proves the inject wrote the registry — a silent gate is also what you get with NO registry. Helper `_inject_real_flow` asserts rc, file exists, entry has `procedures`. Mutant "inject never saves" was only killed after this. Also added: blank selector -> no registry + stderr + rc 0; open Trivial selector never blocks (only test killing "Trivial demands its selector"); Trivial+Corto -> Corto.
