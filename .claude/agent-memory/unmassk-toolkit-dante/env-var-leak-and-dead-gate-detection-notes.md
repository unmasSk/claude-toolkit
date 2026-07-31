---
name: env-var-leak-and-dead-gate-detection-notes
description: Roadmap FASE 2 (2026-07-29) — conftest.run_cmd None-sentinel env removal channel, how to test "does this hook ever actually fire", and the feature-flag-forced-on driver for keeping a dormant regex regression non-vacuous
metadata:
  type: feedback
---

Roadmap `docs/plan/ROADMAP-memoria-v2.md` FASE 2, unmassk-toolkit.

## 1. `conftest.run_cmd()` env removal channel (the root cause, not the 4 reds)

`run_cmd` merges `**os.environ` into every subprocess, so a dict-based `env=`
overlay can only ADD/OVERRIDE, never DELETE. Any variable in the developer's
shell leaks into the whole suite. Measured before the fix: **5 failed** run
from inside Claude Code (`CLAUDECODE=1` really exported) vs **4 failed** under
`env -u CLAUDECODE`. Neither was "the" result.

Mechanism added (test infra, Dante's to own): a value of `None` in `env=` means
**remove that key from the merged environment**, applied *after* the merge so
it also strips what came from `os.environ`. Plus `conftest.claude_env(bool)`
which always returns a decision (`{"CLAUDECODE": "1"}` or
`{"CLAUDECODE": None}`) — never "just omit it".

**General rule (confirmed useful, keep applying):** a test whose outcome
depends on an env var must SET it or REMOVE it. Omitting it is not a third
option — it means "whatever the shell says", and that is how a hook that never
fired for 4 months kept a green suite.

Gotcha when mutation-checking conftest: `git checkout -- <conftest>` reverts
**your own uncommitted edits too**, not just the mutation. On an
uncommitted/WIP test file, revert the mutation with a targeted Edit (exact
original text), never with `git checkout`.

## 2. Testing "does this gate ever actually fire?" without fabricating input

The 4-month-dead `pre-validate-commit-trailers.py` read `CLAUDE_CODE` while
Claude Code exports `CLAUDECODE`; `conftest.check_hook_msg()` fabricated the
same wrong name, so hook and fixture agreed with each other and disagreed with
reality. Seven test files stayed green.

Two complementary shapes, neither sufficient alone
(`tests/test_pre_validate_hook_actually_fires.py`):

- **Real-producer test**: pass `dict(os.environ)` through unmodified and
  assert the gate fires. `pytest.skip()` with an explicit "real producer
  unreachable here" message when the marker is absent (CI). This is the §34
  "report not-verified, never substitute a fixture" rule applied to an
  environment variable — the producer is the shell, and it only exists inside
  Claude Code.
- **Dead-name negative test** (runs everywhere, CI included): set ONLY the
  retired name, assert NOT blocked; twin test sets only the live name, assert
  blocked. Same repo, same command, the sole difference being the variable
  name. This is the CI-visible half and it caught the reverted-name mutation
  on a clean shell.

Also worth pinning: `MARKER=""` must read as absent (the hook uses
`bool(os.environ.get(...))`), since the removal channel and any future
`env -u` plumbing both depend on empty-vs-missing being equivalent.

## 3. Keeping a regression test non-vacuous when its feature flag is OFF

`BLOCK_DIRECT_GIT_LOG = False` in the hook — `git log` is deliberately exempt
(bin/git-memory-log.py silently caps at 100 commits with `--all`, and
agents/gitto.md:239 tells agents to use `git log` directly). With the flag off,
the three BUG C false-positive tests (`cat git.log`, `echo 'git log info'`,
`git log-remote origin` must NOT be blocked) pass because *nothing* is ever
blocked — they prove nothing about the regex.

Fix: a small subprocess **driver** that loads the shipped hook via
`importlib.util.spec_from_file_location`, asserts the constant is still False
(so the driver itself fails loudly if the flag ever ships True), sets
`mod.BLOCK_DIRECT_GIT_LOG = True`, and calls `mod.main()` translating
`SystemExit` into an exit code. `exec_module()` runs module level only
(`main()` is `__name__`-guarded) and `force_utf8_streams()` never touches
stdin, so the hook still reads its payload normally. Mutation-checked: putting
the old `\bgit\b.*\blog\b` regex back turns all three red.

Always pair it with an anti-vacuity control in the same class ("with the flag
forced on, a REAL `git log` IS blocked") — otherwise three exit-0 results only
prove the driver failed to turn the feature on.

## 4. Doctor: proving "never green because it could not check"

`bin/git-memory-doctor.py::expected_hooks/expected_skills` return `None` for
"cannot verify" and `[]` for "genuinely empty" — falsy twins that mean opposite
things. The regression that matters is at the CALL SITE, not in the helper, so
test it end-to-end through `run_doctor(as_json=True)`:
`monkeypatch.setattr(doctor_mod, "find_plugin_root", lambda: fake_root)` +
`monkeypatch.chdir(repo)` + `capsys` → parse the JSON. Assert level `error`,
message contains "cannot verify", **and `"0/0" not in message`** — "0/0 ✅" is
the literal shape of the silent green being killed.

Mutation-checked live: rewriting the call site to
`expected_hooks(...) or []` + `if False:` produced exactly
`level='ok', message='0/0 in plugin cache'` and turned 3 tests red.

Anti-vacuity control for the whole class: run the same `run_doctor()` against
the REAL plugin root and assert `ok` with the real derived counts — otherwise
the blind-doctor tests would pass on a doctor that errors on everything.

For the derivation itself, don't hand-type the hook list: compare
`expected_hooks(REAL_PLUGIN_ROOT)` against `os.listdir(hooks/)` minus
`TRANSIENT_HOOKS` — the filesystem is an independent source from hooks.json,
and disagreement between them is exactly the drift the check exists for.
The transient-probe exclusion test needs its own anti-vacuity guard (assert the
probe IS still declared in hooks.json raw text first), or it passes trivially
the day the probe is retired.

See also:
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md).
