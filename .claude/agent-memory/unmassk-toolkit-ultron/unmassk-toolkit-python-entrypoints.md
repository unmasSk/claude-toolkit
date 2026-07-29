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

## hooks/pre-task-recall.py issue #68 history: updatedInput propagation bug,
## the deny-gate redo, and its later removal (2026-07-12)

First attempt at #68 (silent skill injection, mirroring how the existing
git-memory `_allow_with_injection()` rewrites `tool_input.prompt`) was
implemented, tested green, then fully reverted (`git show 7497f61`) because
Claude Code does not actually propagate `hookSpecificOutput.updatedInput`
into a spawned subagent's prompt (upstream bug #15897) -- confirmed
independently of this repo, not a bug in the hook itself.

The redo used a DENY gate instead: when a domain skill scored high enough
against the prompt and the prompt didn't already contain the `_SKILL_MARKER`
sentinel (`"[DOMAIN SKILL —"`), the hook returned `permissionDecision:
"deny"` with instructions to paste the skill block and reinvoke. Also
corrected in that pass: the hook's `tool_name` check was `!= "Task"` and
silently never fired, because the real PreToolUse payload for a subagent
spawn uses `tool_name == "Agent"` -- the check became `not in ("Agent",
"Task")`. That fix is still current (it applies to the whole hook, not just
the now-removed gate).

**2026-07-12 -- the entire BM25 skill-gate was retired (not tuned, removed).**
Deleted from `hooks/pre-task-recall.py`: all `_SKILL_*` constants, `_deny()`,
`_find_gate_skills()`, `_build_skill_gate_message()`, and the gate block in
`main()` between the whitelist check and the memory-recall query -- memory
injection (section B, `_allow_with_injection` / `recall()`) now runs
unconditionally right after the whitelist check, with nothing gating it.
`scripts/skill-search.py` (the gate's only consumer) and all 36 `.skillcat`
files across the plugin repos were deleted outright (recoverable via the
`bm25-skill-gate-1.19.9` tag if ever needed again). `tests/test_pre_task_recall.py`'s
~10 `TestSkillGate*` classes are now dead and are Dante's follow-up, not
touched during the removal. Do not resurrect any `_SKILL_*` reference, or
the precision-calibration numbers this file used to carry (trigger 8.0,
confident floor 5.0, relative margin 0.35), as if the gate still exists --
it does not. If it's ever rebuilt, re-derive thresholds from fresh evidence.

## Reuse an existing semver comparator, don't add a second parser (issues #58/#64)

Two semver comparators already live in this codebase, each solving a
different problem -- don't conflate them or invent a third:

- `bin/release_validators.py::_semver_key()` -- full semver 2.0.0 ordering
  key (major.minor.patch + pre-release identifier comparison), used by
  `bin/release_helpers.py` for release ordering. Its pre-release identifier
  loop must guard with `ident.isascii() and ident.isdigit()`, not bare
  `isdigit()` -- `str.isdigit()` accepts non-ASCII Unicode digit chars that
  `int()` also parses, silently misclassifying them into the numeric
  comparison branch instead of the alphanumeric one (issue #58).
- `unmassk-toolkit/lib/upgrade_check.py::_parse_semver()` -- simple
  `(major, minor, patch)` int-tuple parser (no pre-release support, returns
  `None` on anything else), the oracle `needs_upgrade()`'s Check 2 already
  trusts for `manifest_tuple < code_tuple`. `unmassk-toolkit/lib/boot_health.py::check_version_mismatch()`
  used to compare with raw string inequality (`installed != PLUGIN_VERSION`),
  which suggested "update" even when the installed version was numerically
  NEWER than the code (issue #64, PoC: manifest "9.9.9" vs code "1.19.4").
  Fixed by importing `_parse_semver` into `check_version_mismatch()` and
  gating the warning on `installed_tuple < code_tuple` -- same function,
  imported, not re-derived.

**Addendum (issue #58 T3, 2026-07-14):** `bin/release_validators.py:_semver_key()`'s
`isascii() and isdigit()` guard was already committed in `0fab68eb` (2026-07-12,
same commit as the #64 fix above) — re-checking it later found nothing left to
change; `git blame` + a clean `git status` on the file confirmed it. Don't
re-apply a fix without first blaming the exact line — the task description
handed to an agent may lag the actual repo state.

Also checked (same pass): `lib/boot_health.py`'s OWN local `_semver_key()`
(nested inside `_latest_version_dir()`, sorting `os.listdir()` entries of a
locally-installed plugin cache dir — never adversarial/external input) does
**not** call `isdigit()` at all — it does `tuple(int(x) for x in
v.split("."))` wrapped in a blanket `try/except ValueError: return (0, 0,
0)`. Since Python's `int()` already accepts Unicode decimal digits (the same
class `isdigit()` accepts), a non-ASCII-digit directory name parses to the
same tuple either the `isdigit()`-gated or ungated way — there's no
mixed-type-tuple misclassification risk here (unlike the pre-release
identifier case in `release_validators.py`, which produces `(0, int)` vs
`(1, str)` tuples that must NOT cross-contaminate). Worst case for a
malformed dir name is the coarse `(0, 0, 0)` fallback, not a crash or a
silently-wrong ordering relative to real semver dirs. Verdict: leave as-is,
no `isascii()` guard needed — confirmed via
`unmassk-toolkit/tests/test_issue64_boot_health_semver_comparison.py` (all
cases pass unchanged).

Import discipline for reusing `_parse_semver` from `boot_health.py`: kept
**deferred inside the function body**, next to the existing deferred
`from git_helpers import ...` line, for the same reason stated in
`boot_health.py`'s own module docstring -- `boot_health` is a real,
stably-named module, and a module-level `from upgrade_check import
_parse_semver` risks running during a test's stub window (`upgrade_check.py`
has its own module-level `from version import VERSION as PLUGIN_VERSION`
that would freeze to a stub's fake `"test"` version forever in that
scenario). This is a broader instance of the "check what tests stub before
adding a module-level import" rule already documented above for
`_symlink_safe_open.py` fallbacks -- applies even when there's no
`ImportError` fallback involved, just an import-order/caching hazard.

**`_allow_with_injection` is CONFIRMED working, not a suspected no-op.**
A prior version of this note flagged it as "may itself be silently
non-functional" by analogy to the reverted skill-injection case (bug
#15897). House (2026-07-12, see its `diagnostic-patterns.md`) confirmed
live that the memory footer DOES reach the whitelisted subagent -- the
parent transcript only ever records the PRE-hook prompt, so injection is
invisible from there, but first-party subagent receipt shows the real
`_FOOTER_HEADER` + recall block. Smoke-tested again in this same session
(`echo '{"tool_name":"Agent",...}' | python3 hooks/pre-task-recall.py`)
and the emitted `updatedInput.prompt` carries the footer correctly. Do not
re-flag this as a suspected no-op without new evidence.

## Editing hooks/hooks.json does NOT change what runs in the live session

Verified 2026-07-29: `~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-toolkit/<version>/`
is an independent **copy**, not a symlink into the repo working tree
(`ls -l` on `hooks/hooks.json` there shows a regular file with its own
mtime and its own byte size). Claude Code executes the CACHE copy.

Consequences, both of which have real cost if forgotten:

- Adding/editing a hook in `unmassk-toolkit/hooks/` and declaring it in
  `unmassk-toolkit/hooks/hooks.json` changes NOTHING at runtime until the
  plugin is reinstalled/synced into the cache. A plan that says "declare
  the hook, then read its results next turn" has a missing step between
  those two.
- `bin/git-memory-doctor.py`'s "Hooks: N/N in plugin cache" line reports on
  the CACHE, not the repo — it stays green while the repo has hooks the
  cache has never seen. It is not a check that your edit took effect.

Check both sides explicitly before claiming a hook is live:
`grep -c <hookname> <cache>/hooks/hooks.json` and
`ls <cache>/hooks/<hookname>.py`. [[lessons]]

**Since 2026-07-29 `bin/git-memory-doctor.py` checks this itself** — a
`Repo vs cache` line (warn, never error) built on `lib/cache_sync_check.py`,
which MD5-compares `hooks/`, `lib/` and `bin/` between the working tree and
`_latest_version_dir(CACHE_BASE_DIR/unmassk-toolkit)`. It is silent unless the
current project actually contains a `unmassk-toolkit/` directory, and
fail-open everywhere else. Skills are deliberately NOT compared there —
`lib/boot_health.py::check_skill_drift()` already does it at boot.

## The env var is `CLAUDECODE`, never `CLAUDE_CODE`

Claude Code exports `CLAUDECODE=1` (no underscore), alongside
`CLAUDE_CODE_ENTRYPOINT`, `CLAUDE_CODE_SESSION_ID`, etc. — the underscore
variants all have a suffix; the bare "am I running under Claude" flag does
not. `hooks/pre-validate-commit-trailers.py` read `CLAUDE_CODE` and was
therefore inert from v1.0.0 to 2026-07-29 (~4 months), while its tests passed
the whole time because `tests/conftest.py`'s `check_hook_msg(as_claude=True)`
fabricated `CLAUDE_CODE=1`. Before writing ANY env-based "is this Claude?"
guard, check `env | grep -i claude` on a real session instead of copying the
name from an existing hook.

Second-order trap once the name is fixed: `conftest.run_cmd()` merges
`**os.environ` into every subprocess env, so running the suite from inside a
Claude Code session leaks the real `CLAUDECODE=1` into every hook under test.
Tests that mean "run as a human" (`as_claude=False`, or an env dict filtering
only `CLAUDE_CODE`) then fail in a CC terminal and pass in a plain one. Always
run the suite BOTH ways — plain, and `env -u CLAUDECODE python3 -m pytest ...`
— before attributing a failure to your own change.

## git-memory-doctor.py: expected hooks/skills are derived, not listed

`EXPECTED_HOOKS`/`EXPECTED_SKILLS` used to be hand-written literals and had
drifted to 5 hooks (vs 12 declared in `hooks/hooks.json`) and 3 skills (vs 10
on disk) — reporting "5/5 ✅" over 7 unchecked hooks. Now derived at runtime:
`expected_hooks()` parses `hooks/hooks.json` and regexes `hooks/(\S+\.py)` out
of each `command`; `expected_skills()` lists `skills/*/`. Both return
`None` on "cannot read", which the caller reports as an explicit
`cannot verify — <reason>` **error** — never collapse an underivable list into
an empty one, or the check silently passes as "0/0". `TRANSIENT_HOOKS` is the
one escape hatch (currently `_probe_canal.py`): short-lived instrumentation
declared in hooks.json must not become a permanent requirement.
