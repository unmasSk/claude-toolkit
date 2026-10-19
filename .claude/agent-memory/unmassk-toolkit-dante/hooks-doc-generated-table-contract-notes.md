---
name: hooks-doc-generated-table-contract-notes
description: hooks_doc.py / bin/hooks_doc_sync.py — first test file; table moves to unmassk-memory/references/hooks.md (#89)
metadata:
  type: project
---

Before 2026-10-19 no test referenced hooks_doc at all. `tests/test_hooks_doc_references.py`
drives `bin/hooks_doc_sync.py --plugin-root <tmp>` (real door, disposable root:
copytree of real hooks/ + hand-written SKILL.md and references/hooks.md).
Expected rows parsed from hooks.json in the test (regex `hooks/(\S+\.py)`),
never from the lib.

**Why:** the doctor's "Hooks doc" check and the sync script share
`compare_hooks_doc`; a check reading SKILL.md while --write targets hooks.md
would say ok over a missing table.

**How to apply:** to make a check-reads-wrong-file test red on the right
assertion, seed the OLD location with an in-sync block built by
`render_hooks_block` (setup input from the lib is fine) so today's code says
`ok:`. The marker-missing refusal guard is green by design.

**Four columns, not two (#89 Moriarty):** compare all of event/matcher/file/timeout (unescape `\|` in cells). The shipped-table test catches hooks.json drift; a render mutant (matcher constant) is caught only by a write-then-edit-hooks.json drift test through the sync script. Mutating hooks.json in the copy makes the drift test a no-op — mutate the lib instead.
