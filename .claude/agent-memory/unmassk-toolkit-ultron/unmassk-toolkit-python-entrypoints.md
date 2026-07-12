---
name: unmassk-toolkit-python-entrypoints
description: unmassk-toolkit/bin and hooks Python entry points -- sys.path/lib import variants and the encoding guard pattern (issue #52)
metadata:
  type: project
---

## Three sys.path-to-lib variants across bin/*.py and hooks/*.py

When touching every entry point in `unmassk-toolkit/bin/*.py` and
`unmassk-toolkit/hooks/*.py` (23 files total, no more no less -- confirmed
by `find unmassk-toolkit/bin unmassk-toolkit/hooks -name '*.py'`), expect
three different header shapes, not one:

1. **Direct insert** (most common):
   `sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))`
   immediately followed by `from X import Y` lines, no guard.
2. **Guarded `_LIB_DIR` insert** (pre-merge-gate.py, pre-task-recall.py,
   session-start-crew.py, pre-memory-dedup-gate.py):
   ```python
   _HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
   _LIB_DIR = os.path.join(os.path.dirname(_HOOKS_DIR), "lib")
   if _LIB_DIR not in sys.path:
       sys.path.insert(0, _LIB_DIR)
   ```
3. **No lib import at all** (`hooks/validate-memory-path.py` only) --
   fully self-contained script, subprocess-only git access. Any change that
   must apply to "every entry point" (not just the ones already importing
   lib/) needs its own `sys.path.insert` added here, not just a bare
   `from lib_module import X`.

`bin/git-memory-bootstrap.py` and `bin/git-memory-install.py` use variant 1
but with multiple `from X import Y` blocks split across paragraphs (their
own lib submodules bootstrap_tree/bootstrap_deps/... and
install_inspect/install_apply); the shared-lib import block is the FIRST
one, before those.

## Encoding guard (issue #52, T1) -- fail-open UTF-8 stream reconfigure

`lib/encoding_guard.py` exports `force_utf8_streams()`: reconfigures
stdout/stderr to UTF-8 with `errors="replace"`, wrapped in
`try/except (AttributeError, ValueError, OSError)` so the guard itself can
never crash (fail-open contract every hook in this project already
follows). Call it as the FIRST statement after the sys.path-to-lib
mutation, before any other `from lib_module import ...` -- in all three
header variants above. [[lessons]]

Root cause was House's finding: no entry point forced UTF-8, so any
print() of an emoji/arrow crashes with UnicodeEncodeError under a Windows
legacy codepage (reproducible anywhere via `PYTHONIOENCODING=cp1252`).
`tests/conftest.py`'s `run_cmd()` already does the parent-side symmetric
fix (`subprocess.run(..., encoding="utf-8")`) -- don't re-fix that, it's a
test file (Dante's territory).

## date_parsing.py extraction: parse_date() centralized, time_ago() deliberately left alone

`bin/git-memory-gc.py` and `bin/git-memory-doctor.py` each had a
byte-identical `parse_date()` (the `%at`-epoch-first, ISO-8601-fallback
shape from the issue #55 migration, see [[lessons]]). Centralized into
`lib/date_parsing.py` (new tiny module, same precedent as
`_symlink_safe_open.py`), imported with a plain module-level
`from date_parsing import parse_date` in both bins -- variant 1 header,
no defensive fallback needed (grepped `tests/` for a `date_parsing` stub:
none exists, unlike `git_helpers`/`parsing`/`version`). Tests that load
these hyphenated bins via `spec_from_file_location` + `exec_module` and
call `mod.parse_date(...)` (`tests/test_date_parsing_epoch_contract.py`)
keep working unchanged since the import binds `parse_date` into each
bin's own module namespace -- no re-export shim needed, unlike the
`session-start-boot.py` split cases in [[lessons]].

Evaluated folding `lib/boot_git_checks.py::time_ago()` on top of the
same `parse_date()` -- did NOT do it. `time_ago()`'s ISO-8601 branch is
`datetime.fromisoformat(iso_or_unix)` with no `"Z"` -> `"+00:00"`
replace, while `parse_date()`'s ISO branch does that replace. On Python
3.10 (this repo's declared `[tool.mypy] python_version`), `fromisoformat()`
doesn't accept a trailing `Z` -- so swapping `time_ago()` to call
`parse_date()` would silently start accepting `Z`-suffixed input it
currently rejects (returns `"unknown"` today). No test pins this either
way, but it's a real behavior change bundled into what should be a
pure dedup refactor, not something to force through unilaterally
(`unmassk-standards`'s "no hidden feature changes" rule for
Refactoring Mode). Reported instead of merged; `time_ago()` still has
its own independent, duplicated-in-spirit ISO/epoch parsing.

`lib/_symlink_safe_open.py` exists because `tests/test_migrate_statusline.py`
stubs `sys.modules["git_helpers"]`/`["parsing"]`/`["version"]` with minimal
fake modules for one test file, and call sites need a defensive
`try: from git_helpers import X / except ImportError: from
_symlink_safe_open import X_fallback` fallback. Before adding a similar
fallback for any NEW lib/ module, grep `tests/` for
`sys.modules[stub_name]` or `types.ModuleType` to see exactly which module
names get stubbed -- only add a fallback if your new module's name (or a
module it needs) is in that stub set. `encoding_guard.py` is not, so a
direct unconditional `from encoding_guard import force_utf8_streams` is
correct with no defensive fallback.

## hooks/pre-task-recall.py issue #68: injecting into a Task/Agent prompt via
## updatedInput does NOT propagate (Claude Code bug #15897) -- redo as a deny gate

First attempt at #68 (silent skill injection, mirroring how the existing
git-memory `_allow_with_injection()` rewrites `tool_input.prompt`) was
implemented, tested green, then fully reverted (`git show 7497f61`) because
Claude Code does not actually propagate `hookSpecificOutput.updatedInput`
into a spawned subagent's prompt (upstream bug #15897) -- confirmed
independently of this repo, not a bug in the hook itself. `_allow_with_injection`
still exists and is still used for the git-memory recall footer -- **do not
assume it's dead code just because the skill-injection use case was reverted**;
it may itself be silently non-functional for the same underlying reason and
worth flagging if that's ever confirmed.

The redo (this session) uses a DENY gate instead: when a domain skill scores
>= `_SKILL_SCORE_THRESHOLD` (1.5, same as `scripts/skill-search.py`'s own
`LOW_SCORE_THRESHOLD`) against the prompt and the prompt doesn't already
contain the `_SKILL_MARKER` sentinel (`"[DOMAIN SKILL —"`), the hook returns
`permissionDecision: "deny"` with `permissionDecisionReason` containing the
exact block to paste + reinvoke instructions. Denying (unlike updatedInput)
DOES reach the orchestrator today -- verified live before implementing, per
the task's own "CONTEXTO VERIFICADO EN VIVO" brief. Also corrected in the
same pass: the hook's own `tool_name` check was `!= "Task"` and silently
never fired, because the real PreToolUse payload for a subagent spawn uses
`tool_name == "Agent"` (verified live) -- the check is now `not in
("Agent", "Task")`. This second bug is likely why some earlier assumptions
about this hook's behavior never actually exercised its logic at all.

Fail-open contract for the gate itself: `_find_top_skill()` returns
`(None, error_str)` on ANY failure (missing `scripts/skill-search.py`,
non-zero exit, timeout, malformed JSON, missing `score`/`name` keys) and the
caller only denies on `(top, None)` with `top["score"] >= threshold` --
every other combination falls through to the pre-existing memory-recall
allow flow. Verified manually (not just by reading the code): moved
`scripts/skill-search.py` aside and re-ran the hook -- fell through to allow
with a `skill gate: fail-open script not found: ...` stderr breadcrumb, and
memory injection still ran normally afterward.

Applying this gate to real prompts breaks ~27 of the ~51 tests in
`tests/test_pre_task_recall.py` (they assert `permissionDecision == "allow"`
for prompts that legitimately score high against the REAL `~/.claude/plugins/cache`
skill corpus, e.g. `"implement BM25 ranking for recall"` scores high against a
"ranking algorithm"/search-domain skill). This is expected, not a regression --
the prior (reverted) attempt at #68 hit the identical situation ("8 contrato
verdes; 2 tests viejos obsoletos" in `bfe9d9f`) -- test reconciliation for the
gate semantics is Dante's follow-up, not something to patch unilaterally while
implementing the hook itself.
