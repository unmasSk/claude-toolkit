---
name: managed-block-slimming-89-contract-notes
description: #89 3.1 managed CLAUDE.md block slimming RED contract — property tests, wrapped-phrase gotcha, satisfiability check
metadata:
  type: project
---

#89 step 3.1 (2026-10-19): shorter managed block, tests in `tests/test_managed_blocks.py` (classes TestShortToolkitBlock, TestShortProtocolsMenu, TestShortCommunicationBlock, TestBuildModeRetired).

- Pin properties, not the block text: each menu skill exactly once (regex on backticked `unmassk-*`), one skill per bullet, line ceiling = skills + heading + footer, anchors per rule that must survive.
- Gotcha: block bodies are hard-wrapped ("the boot\n   failed") — normalise with `" ".join(body.split())` before phrase checks.
- Retiring a block: old fixture must be hand-written with the real markers (source loses them); test through the crew hook (every-start door) plus idempotent second run.
- Old tests that pinned the retired thing (count 4, BLOCKS[3], "NOT YAPPING" label) are updated in the RED pass, otherwise Ultron cannot reach green.
- Legacy-block removal (fix pass): pin that owner text with 3+ newline runs elsewhere survives byte for byte, and owner edits inside a retired block reach the log / hook stdout verbatim. Fixture = current rendered BLOCKS + old block, so only the legacy path acts.
- A pointer to a shipped file must be named by skill + in-skill path, never `unmassk-toolkit/skills/...` (exists only in this repo); assert the repo prefix is absent.
- Satisfiability check: apply a sample implementation on a scratch copy and run the file there — proves the contract is reachable. Sibling suites erroring with FileNotFoundError('') in a scratch copy is environmental, not a signal.
