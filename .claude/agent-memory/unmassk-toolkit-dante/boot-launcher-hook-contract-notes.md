---
name: boot-launcher-hook-contract-notes
description: hooks/boot_launcher.py (SessionStart) RED contract, first hook of Capa 6 -- real-payload technique via official plugin-dev schema doc, "cwd==payload.cwd" trick to avoid asserting internal hook logic
metadata:
  type: project
---

`unmassk-toolkit/tests/memory/test_boot_launcher.py` (12 tests) is the
test-first contract for `hooks/boot_launcher.py`, the first of the 3
Capa-6 hooks in `docs/memoria-v2/PIEZAS.md` Sec.11. Its whole contract is
one line: "~20 lineas sin logica: llama a `bin/memory/boot.py`". No fila
of Sec.11 is assigned to it individually (that table covers all 3 hooks
together), so the contract was derived, not copied from a row.

**Real SessionStart payload shape — none of this codebase's existing
hooks could serve as ground truth.** `hooks/session-start-boot.py` and
`hooks/session-start-crew.py` (both real, live SessionStart hooks in this
repo) do NOT read stdin at all — they resolve everything via `git` against
the process's inherited cwd. This proves a toolkit hook can legitimately
need zero payload fields, but it meant the task's instruction to check
`session-start-boot.py` "for the exact payload shape" was a dead end.
Found the real shape instead in the **officially installed `plugin-dev`
marketplace skill**:
`~/.claude/plugins/marketplaces/plugin-dev-marketplace/plugins/plugin-dev/skills/hook-development/references/hook-input-schemas.md`
— common fields for every hook (`session_id`, `transcript_path`, `cwd`,
`permission_mode`, `hook_event_name`) + `SessionStart`-specific
(`source`: startup/resume/clear/compact, `model`, optional `agent_type`).
Built `make_session_start_payload()` in `conftest.py` from this, cited in
its own docstring. **Reusable for the other 2 Capa-6 hooks**
(`customs.py`/PreToolUse-Bash, `inject.py`/PreToolUse-Agent) — check the
same reference doc's PreToolUse/SubagentStart rows before inventing a
payload shape for those.

**Key technique: `cwd == payload["cwd"]`, always, in every test.** No
document says whether the hook resolves the target repo via
`payload["cwd"]` or via its own inherited process cwd (both are plausible
— `hooks/pre-merge-gate.py` already does the former: "prefer an explicit
cwd in the hook payload... fall back to the hook process's own working
directory"). Asserting one specific mechanism would be "asserting a
decision made inside the launcher" — exactly what this project's
CLAUDE.md/PIEZAS.md forbid a contract test from doing for a piece whose
whole point is having *no* internal logic. Fix: every test sets the
**outer subprocess's own cwd** (`run_hook_with_payload(..., cwd=X)`) and
`payload["cwd"]` to the identical value `X`. The result is then
independent of which one the eventual implementation reads — round-trip
still verifiable, no internal-logic assumption baked into the test.
Added `run_hook_with_payload()` / `run_hook_raw_stdin()` /
`make_session_start_payload()` to the SHARED `conftest.py` (legitimate —
test infra, not `lib/memory/`, and other hook contracts will reuse it),
alongside the pre-existing `run_memory_script()`/`run_gitmem_script()`.

**Real (not simulated) boot.py failure used for the "never blocks
session" contract item.** Ran `bin/memory/boot.py` by hand outside a git
repo before writing the test: it fails for real (`git rev-parse
--show-toplevel` errors), caught by its own top-level try/except, prints
`boot.py: git rev-parse --show-toplevel fallo en ...` to stderr, no
traceback, exits 1. That genuine failure (not a monkeypatch, not a fake
broken script) is what `TestBootFailureNeverBlocksSession` wraps —
`test_launcher_exits_zero_when_boot_py_fails_outside_a_git_repo` even
includes a "control" sub-assertion that re-runs `boot.py` directly first
and asserts it still fails today, so the test doesn't silently go vacuous
if someone later hardens `boot.py` to succeed outside a repo.

**Stdin/encoding robustness tests are deliberately framed as internal
robustness, not attacker-input tests** — this project's threat model
(CLAUDE.md) explicitly excludes an external attacker; malformed
stdin/restricted console encoding are framed as "the harness/host OS
doing something the hook must survive," matching the `§5 platform
robustness` / "system against itself" framing this repo's `unmassk-standards`
already uses, not an injection/exploit angle.

**Result:** 12/12 RED, all failing for the identical, correct reason
(`can't open file '.../hooks/boot_launcher.py': No such file or
directory`, Python's own file-not-found exit code 2) — never an import
error or broken fixture. Full `tests/memory` suite unaffected:
239 passed with `--ignore=test_boot_launcher.py`, 251 collected total.

**Open gap flagged to Ultron/Yoda, not resolved here:** whether the hook
needs to read stdin/JSON at all (both other live SessionStart hooks in
this repo don't), and if it does, which single field it actually uses to
resolve the target repo. Per this task's own instruction ("si un test
tuyo necesita afirmar una decision tomada dentro del lanzador... fijalo
como hueco"), this was deliberately left undecided rather than guessed.

See also: [boot-stdout-banner-contract-notes](boot-stdout-banner-contract-notes.md) (sibling SessionStart hook, same "fail-open, exit 0 always" contract, same UTC-label-normalization round-trip technique borrowed from `test_boot_script.py`).
