---
name: rejection-relaunch-command-ast-crosscheck-notes
description: unmassk-memory (v2) test_rejection_relaunch_commands.py -- AST-extracted gitmem relaunch commands (validator.py/validator_zones.py/validator_pointers.py/validator_issue.py/rejection.py/hooks/customs.py) cross-checked against real argparse via parse_args-spy introspection; validator.py:409 dead "close" subcommand confirmed as the only break among 21
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_rejection_relaunch_commands.py`
(new file, RED by design -- 3 of 44 tests fail, all naming the same real
bug). Task: prove `validator.py:409`'s `gitmem close <id> "..."` is dead
(subcommand renamed `close`->`remove` days ago, per `bin/gitmem`'s
`SUBCOMMANDS`), and find out whether it's the only broken relaunch
command among everything the six rejection-producing files offer.

**Two independently-written things, never hand-copied:** producer =
every `gitmem ...` string the six files actually contain, extracted from
their real AST (never regex-over-text, never retyped); consumer = the
real `argparse.ArgumentParser` each `bin/memory/<sub>.py` builds,
obtained by running its own `_parse_args([])` function with
`ArgumentParser.parse_args` monkeypatched to return `self` instead of
parsing -- gets the production parser object with zero risk of
triggering real validation/side effects, and zero hand-copied flag
lists.

**Extraction needed TWO passes over the same AST, not one:** Pass A
walks `command = (...)` / `relaunch = (...)` assignments (the ONLY names
every `rejection_.build(..., command=X)` call site in these six files
uses -- confirmed by grep before writing, 9x `command=command` + 2x
`command=relaunch`, zero inline literals). Pass B walks EVERY string
literal in the file and keeps ones whose `.strip()` starts literally
with `"gitmem "`. Pass B was the one that actually caught the target
bug: `validator.py:409`'s `gitmem close <id> "..."` lives inside
`options` (the explanatory prose shown alongside the structured
`command` field), not inside `command` itself -- Pass A alone would have
missed it entirely. Same pattern at `validator_zones.py:93`
(`gitmem rule "..."`, a second valid relaunch path offered in prose next
to the `command` field's `gitmem note M ...`). The `.strip().startswith("gitmem ")`
rule is what separates a real actionable command line from a backtick
prose mention (`"usa \`gitmem note\`. Si es..."` doesn't start with
`"gitmem "` -- prose precedes it) without a hand-maintained exclusion
list.

**AST walk gotcha: a naive `ast.walk` over the whole file double-counts
f-string fragments.** `ast.walk` recurses into a `JoinedStr`'s own
`.values` (its constituent `Constant`/`FormattedValue` pieces), so a
generic "find every Constant str anywhere" pass also matches each
fragment of a multi-part f-string as a SEPARATE partial string (e.g. one
match for `'gitmem note <TIPO> --zones <zona1> <zona2> "<titular de
hasta'`, truncated mid-word right where the `{HEADLINE_MAX}`
interpolation starts). Fix: a custom `ast.NodeVisitor` whose
`visit_JoinedStr` appends the node WITHOUT calling `generic_visit` --
treats the whole f-string as one leaf, never descends into it. Constant
nodes need no such guard (they have no children). Same technique is
reusable for any future AST-based text-extraction test in this repo.

**Placeholder-vs-runtime-value distinction, and why type/choices checks
were dropped from the checker:** the task's own instruction ("lo que se
comprueba es la FORMA del comando, no su contenido") meant the checker
must NOT call the real `parser.parse_args()` -- doing so validates
`type=int` and `choices=` too, which produced two FALSE positives during
development: `--stops {stops}` (an f-string interpolation of an
ALREADY-validated real value, replaced by the extractor with a synthetic
`PLACEHOLDERn` token that isn't literally `"yes"`/`"no"`) and `--issue
<numero real>` (a literal doc placeholder, not `int`-parseable as
written). Both are legitimate under "form, not content" -- the fix was
to stop calling `parse_args()` and instead hand-roll a token-consumption
walk driven by each real `Action.nargs` (`None`->1, int->that many,
`"+"`->greedy until the next `--flag`-looking token), checking only (a)
flag existence in `parser._option_string_actions` and (b) required-arg
coverage (`Action.required`, both optionals and positionals) -- exactly
the three checks the task asked for, nothing about value typing.

**Documentation-notation normalization needed before tokenizing, or
false positives from meta-syntax:** `hooks/customs.py` writes relaunch
examples with `[--flag ...]` bracket notation to mean "optional,
repeatable" (man-page style) -- `shlex.split` treats `[--path` as a
literal (unrecognized) token if not stripped first, a pure test-harness
artifact unrelated to any real bug. Fix: `re.sub(r"\[[^\[\]]*\]", "",
isolated)` before tokenizing. Separately, exactly one placeholder among
all 21 commands has an internal space (`validator_issue.py:124`'s
`--issue <numero real>`) -- `re.sub(r"<[^<>]*>", ...replace(" ",
"_")...)` collapses any `<...>` marker's internal whitespace to one
shell token before `shlex.split`, treating the marker AS the single
value it represents (task's explicit instruction) rather than letting a
test-harness tokenization quirk manufacture a spurious failure.

**Two form-level oddities found and deliberately NOT turned into
failing rows (disclosed in the module docstring instead):** (1)
`validator_issue.py:124`'s `--issue <numero real>` is the only
two-word, unquoted placeholder among 21 -- if a user copy-pasted it
literally before substituting, shell tokenization already breaks it in
two; every sibling placeholder is a single token. (2) `--origin
<hash1>,<hash2>,...` (validator.py:439, validator_pointers.py) is written
as ONE comma-joined shell token, but `note.py --origin` is `nargs="+"`
(space-separated multiple tokens) -- shape mismatch between the doc
example and how the flag actually consumes values. Both are real but
minor; out of scope per the task's explicit form/content boundary
(neither is a missing flag nor a missing required arg), so no test
asserts on them -- they're just named in the docstring for whoever wants
to pick them up next.

**Result: RED confirms `close` is the ONLY broken relaunch command among
21.** `test_relaunch_command_flags_and_required_args_match_real_argparse`
(20 cases, `close` excluded via a filtered parametrize list computed at
collection time, not a runtime branch) is 100% green -- every other
extracted command's flags exist and its required args are present. Three
failures, all naming `validator.py:409`/`close` explicitly: (1) the
generic subcommand-membership row: `close not in SUBCOMMANDS`; (2) a
real subprocess end-to-end proof via `run_gitmem_script` (the actual
`bin/gitmem` facade, real stderr: `"subcomando desconocido: 'close'"`);
(3) a characterization test proving the MINIMAL fix (rename
`close`->`remove`, touch nothing else) still isn't enough --
`remove.py`'s `--restriction` (`required=True`) is missing from the
offered command too. `44 total (1 sanity + 21 + 20 + 1 + 1), 3 failed,
41 passed`. Full memory suite re-run after adding the file:
`361 passed` (pre-existing) `+ 3` (new, expected RED) `= 364`, zero
regressions.

**Follow-up 2026-08-04 -- retired the third test after Ultron's real fix,
kept the two general ones:** once `validator.py:409` offered
`gitmem remove <id> "..." --restriction no` for real (Ultron, verified
live against a test repo, returncode 0), the third test
(`test_close_command_renamed_to_remove_is_still_missing_required_restriction_flag`)
started failing on its OWN setup assertion (`tokens[1] == "close"`) --
not because anything was broken, but because it had hand-fixed the
expectation that the subcommand would still be the dead one. Owner's
framing: "un test que fija por su nombre un fallo ya reparado es
exactamente el test academico que no se quiere al cerrar." Retired
rather than patched, per owner instruction: **verified via ablation
before deleting**, not assumed -- imported the test module directly
(`from tests.memory import test_rejection_relaunch_commands as m`,
`sys.path.insert(0, ".../unmassk-toolkit")`, works because `tests/memory/`
has `__init__.py` but `tests/` itself does not, so the package root for
this import is `unmassk-toolkit/`) and ran
`m._check_tokens_against_real_parser` twice: once on today's real
tokens (`[]`, clean) and once with `--restriction no` stripped by hand
to simulate a future regression (`["falta el flag obligatorio
['--restriction'] en remove.py"]`) -- proving
`test_relaunch_command_flags_and_required_args_match_real_argparse`
alone still catches that exact class of regression, no coverage hole
left behind. The retirement note was left IN the file (owner's rule:
"aqui lo equivocado se anota, no se borra en silencio") as a dated
comment block where the test used to live, not in a changelog or in
memory alone. Full suite after retirement: `364 passed`, zero red.

Reference: [rejection-contract-notes](rejection-contract-notes.md), [validator-contract-notes](validator-contract-notes.md)
