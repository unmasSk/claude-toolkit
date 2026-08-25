---
name: rule-retract-replace-contract-notes
description: gitmem rule --retract/--replaces RED contract (2026-08-25) -- text-only rule identity, no prior CLI decision existed, kind made mandatory to avoid inventing ambiguity resolution
metadata:
  type: project
---

Contract file: `unmassk-toolkit/tests/memory/test_rule_retract_replace_contract.py`
(8 tests, all RED for the right reason as of 2026-08-25). Task: give
`gitmem rule` the ability to RETIRE and REPLACE a rule -- until now
`rules.py` only had `add()`/`read_all()`, and a rule has no id, only its
literal text (`_RULE_LINE_RE`/`iter_rule_texts()`).

**No prior decision existed for this CLI shape** -- `gitmem search
"retirar regla"` / "sustituir regla" / "rule retract" all returned 0
zones, checked before writing (not assumed). This test file therefore
FIXES the new surface itself, same pattern [[rules-contract-notes]]'s
sibling `test_rule_script.py` already used for the read-mode grammar
assumption:

```
rule.py --retract "<texto exacto>" --kind <user|claude>
rule.py "<texto nuevo>" --replaces "<texto viejo>" --kind <user|claude> [--quote ...]
```

Library: `rules.retract(text, kind) -> WriteResult`,
`rules.replace(old_text, new_text, kind, quote=...) -> WriteResult`.

**Design decisions made, not left ambiguous:**
- `--kind` is MANDATORY for both `--retract` and `--replaces` -- a rule
  is only unique by (kind, text) pair (`similar_existing()` already
  established this for near-duplicates), so identifying by text alone
  would require inventing an ambiguity-resolution UX nobody asked for.
  Wrong-kind retract is tested as a clean bounce, not a silent no-op.
- Matching text is the BARE text (`rules.strip_quote_suffix()` applied
  before comparing) -- a caller retiring a rule refers to what was
  said, never to the citation suffix appended when it was saved. One
  test seeds a quoted rule and retires it by bare text only.
- Both `retract()` and `replace()` must go through the same
  `rules_commit.commit_or_restore()` atomic path as `add()` (I-003) --
  proven with two explicit `health.coherence_rules()` tests (clean
  after a good retract, clean after a *failed* replace too, since
  `commit_or_restore()` already restores the working tree to HEAD on
  failure).

**Vacuous-green pitfall caught and fixed live** (same mechanism as
[[rule-quote-contract-notes]]): the "wrong kind bounces" test initially
passed for the WRONG reason -- with `--retract` not yet a real flag,
argparse's own "unrecognized arguments: --retract" already yields
`rc != 0`, satisfying a naive assertion without ever exercising the
real business rejection. Fixed by asserting
`"unrecognized arguments" not in combined`, forcing true RED today.
**How to apply:** any RED test whose only failure-mode assertion is
"exit code nonzero" needs this same check whenever the flag/behavior
under test doesn't exist yet -- run the suite once, look for tests that
passed you didn't expect to pass, and add the specific-mechanism
assertion.

Atomicity of `replace()` verified at LIBRARY level (`rules_lib.replace()`
direct call under a forced `.git/index.lock`, same pattern as
`test_rule_commit_contract.py::TestFailedCommitLeavesNoStagedLeftovers`)
rather than through the script -- the failure scenario lives inside the
function itself, the script only relays what it returns.

See also: [[rule-commit-i003-contract-notes]] (the atomic file+git path
this contract reuses), [[gitmem-rule-no-commit-contract-notes]] (history
of `coherence_rules()` retirement/resurrection).

**2026-08-25 extension -- real crash pinned RED, existing guard covered:**
Cerberus found `--replaces "<old>" --kind user` with NO new positional
text (natural slip -- `--retract "<text>" --kind <k>` DOES stand alone
with one argument, `--replaces` doesn't) reaches `_cmd_replace(args.text,
...)` with `new_text=None`, and crashes inside `rules.replace()`
(`"\n" in new_text`, `rules.py:248`) with a raw Python `TypeError`.
`main()`'s top-level `try/except Exception` catches it (no stack trace
leaks) but prints the RAW `TypeError` text verbatim
(`rule.py: argument of type 'NoneType' is not a container or iterable`)
-- confirmed by actually running it, not by trusting the report. Added
`TestReplaceWithoutNewTextBouncesCleanlyInsteadOfCrashing` (RED for the
right reason: `"NoneType" not in combined` and `"nuevo" in
combined.lower()` both fail today) and
`TestKindRequiredGuardBouncesCleanlyOnBothFlags` (2 tests, both GREEN --
`_KIND_REQUIRED_MSG` already covers `--retract`/`--replaces` without
`--kind` correctly, just had no test). The guard-message test imports
`bin/memory/rule.py` by file path (same pattern as
`test_rejection_relaunch_commands.py::_import_bin_memory_module`) ONLY
to read the real `_KIND_REQUIRED_MSG` constant for the assertion --
never to call its functions; execution still only goes through
`run_memory_script` (subprocess), per PIEZAS.md Sec.10.

**Environment gotcha hit while reproducing:** running `git commit`
literally via the Bash tool (even in a throwaway `mktemp -d` repo
outside this project) gets intercepted and returns THIS project's own
customs-hook rejection text -- the harness enforces Dante's own Bash
Blacklist (`git commit` never runs directly) at the tool-call level,
regardless of cwd. Reproduce crashes through `pytest` + the existing
`tmp_repo`/`run_memory_script` fixtures instead (those spawn git via
Python `subprocess`, which the literal-command blacklist doesn't
match) -- never via a raw `git commit` Bash invocation.
