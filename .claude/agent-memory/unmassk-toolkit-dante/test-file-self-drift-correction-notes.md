---
name: test-file-self-drift-correction-notes
description: 2026-08-04 correction pass on test_rejection.py + test_rejection_relaunch_commands.py -- stale command name/count/ablation-result inside test prose itself, annotate-don't-delete pattern applied to test data and docstrings
metadata:
  type: project
---

Owner instruction: two test files that describe the `gitmem` relaunch
contract had gone stale -- the code moved (`close`->`remove`,
`remove.py --restriction` `required=True`->`default=None`,
`validator.py::validate_incident_close_question` added 2 new commands)
and nobody had updated the prose describing that code. Ironic because
`test_rejection_relaunch_commands.py` is the exact apparatus built to
stop this divergence -- but the drift was inside the TEST's own written
description of a command it constructs by hand (`test_rejection.py`),
not inside anything that file's own AST-crosscheck touches.

**Confirms the file's own documented limitation, in production:**
`test_rejection.py`'s incident-close-question fixture row hand-types
`gitmem close I-014 ...` inside a parametrize tuple, passes it through
`rejection_.build()`, and only asserts it renders in the two output
formats -- never executes it or checks it against real `SUBCOMMANDS`.
That's exactly why a dead subcommand name survived there after
`close`->`remove` while `test_rejection_relaunch_commands.py` (which
DOES cross-check against real argparse via `_real_parser_for_subcommand`)
was green the whole time -- different files, different jobs, and the
first one's job (layout only) doesn't overlap the second's (executability).

**A "confirmed via ablation" claim can go stale too, not just names/counts.**
`test_rejection_relaunch_commands.py`'s retirement comment block (~line
554) documented, with a concrete before/after ablation run, that
stripping `--restriction` from the real command still tripped
`_check_tokens_against_real_parser`'s missing-required-flag check. Re-ran
that exact ablation today (`_check_tokens_against_real_parser` against
`remove`'s real parser with `--restriction` tokens removed) and got `[]`,
not the missing-flag message quoted in the comment -- because
`remove.py:53`'s `--restriction` moved from `required=True` to
`default=None` AFTER that comment was written (business-rule enforcement
moved to `validate_incident_close_question`, not argparse). Lesson:
re-run any "verified via X" claim in a doc/comment against the CURRENT
code before trusting it, even when it already has a timestamp and looks
authoritative -- it can go stale in the same session it was written in.

**Recount technique, not eyeballing:** got the real per-file command
counts (`Counter(relpath for relpath, _, _ in ALL_COMMANDS)`) by
importing the test module itself
(`sys.path.insert(0, ".../unmassk-toolkit")`, `from tests.memory import
test_rejection_relaunch_commands as m`) and grouping `m.ALL_COMMANDS` --
never hand-counted `grep -c "gitmem "`, which would double-count
compound/prose mentions the module's own AST extractor already
filters out.

**Annotate, never delete, applies to test DATA too, not just prose.**
Owner's explicit instruction for `test_rejection.py`: correct the two
`gitmem close`->`gitmem remove` strings (they must reflect real
production text since this row is *supposed* to mirror
`validate_incident_close_question`'s literal output) but leave a dated
`[corregido 2026-08-04: ...]` comment stating what it said, why it was
wrong, and which OTHER file actually verifies executability
(`test_rejection_relaunch_commands.py`) -- so a future reader doesn't
mistake this file's green run for proof the command works.

Reference: [incident-close-question-contract-notes](incident-close-question-contract-notes.md), [rejection-relaunch-command-ast-crosscheck-notes](rejection-relaunch-command-ast-crosscheck-notes.md)
