# Traps in this repo that the code does not show

Checked against the tree on 2026-10-16. If one stops being true, delete the line.

## The shared tree
- Other sessions work in the same tree and commit on their own (D-057): my uncommitted edit can land inside someone else's commit. Read `git log` before saying "not committed".
- The hook `customs.py` blocks any Bash command whose TEXT contains `git commit`, even in a throwaway repo or a heredoc. To commit in a scratch repo, put the call in a .py file.
- The live `pre-merge-gate` blocks any Bash text with git merge/pull words, heredocs included: write probe inputs with the Write tool. It also blocks any `sh -c` whose text holds `git`: put the probe in a .py file.

## Running what I built
- `gitmem` on the PATH runs the plugin CACHE, not this repo's source. To test my change: `python3 unmassk-toolkit/bin/gitmem ...`.
- Editing `hooks/hooks.json` or a hook changes nothing in the live session: the session runs the cached copy.
- `git init` here creates `main` by default, so any "protect main" check fires in scratch repos.
- A hook copied out alone prints `UPGRADE: no verificable (RuntimeError)`: to compare two hook versions, copy the whole plugin dir for each side.
- `CLAUDE_PLUGIN_ROOT` does not exist in the Bash tool's shell. The Claude Code env var is `CLAUDECODE` (no underscore).
- zsh aborts the whole command on a glob with no match (`ls -d foo*`). Use `find -path`.
- zsh does not word-split `$T`: `pytest $T` with several paths in T runs "no tests ran". Write the paths out.

## Tests
- Rewriting a test file twice with same-length content inside one mtime tick can make the next subprocess run reuse a stale `__pycache__`.
- Test doubles with a fixed signature break when I add a parameter to a function they replace: new parameters stay optional with a default.
- `subprocess.run(text=True)` without `encoding=` breaks on Windows CI, and its newline translation can't be turned off: read bytes and decode.

- Local python3 is 3.14, toolkit CI runs 3.10: stdlib that is newer (e.g. `fromisoformat` reading a `Z`) passes here and breaks in CI.

## Memory system (`lib/memory/`)
- `format.parse_message` up to 1.47.0 drops a whole note on any body label it doesn't know: a new note field must still be read by the frozen cache copy (Searched rides as a first `Description: Searched:` the old reader overwrites).
- conftest's "movio HEAD del repositorio git REAL" teardown error also fires when another session commits mid-run: compare `git log` times before blaming the test.
- A copy of unmassk-toolkit run outside a git repo errors every test at setup (conftest's real-repo HEAD guard): `git init` + commit the copy first, via a .py file.
- `gitmem note`/`gitmem rule` saves need `--searched` (D-098) since #95 2c: any test or seed that saves without it bounces.
- `test_boot_launcher_install_outside_git.py` reads every `print("[memory]...")` literal in boot_launcher.py as an install notice and expects exactly 2: any new `[memory]` print there turns it red.
- test_health.py, test_boot.py and test_boot_deadline_contract.py pin the exact gh command health_plans runs: any change of call shape turns them red until Dante updates the stubs.
- A hanging fake gh no longer forces a boot overrun: fetch and gh are cut to what is left of the launcher's deadline (UNMASSK_BOOT_ENDS_AT). Force an overrun with a slow `git log` wrapper.
- A throwaway HOME logs gh out: any test reaching real gh gets an auth error, not the network answer.
- `gitmem search --file <path>` can't find notes about a source file (notes never touch it). Search by the file's name as a word.
- A reviewer's "code-only" line count may leave out blank lines: check the floor with every docstring and comment removed before promising a file can reach 300 by cutting docstrings.
- `--replaces none` stays the literal string "none" in `Note.replaces` (the overlap gate skips on non-None) and is persisted as `Replaces: none`: never normalise it to None before validation.
- Rejecting `...` as note content in validate_fields breaks old tests that seed `description="..."` (test_relaunch_command_answer_amnesia): stop holes at the relaunch, not in the validator.
- Any hooks.json entry change turns test_hooks_doc_references TestShippedPlugin red until `bin/hooks_doc_sync.py --write` regenerates skills/unmassk-memory/references/hooks.md: ask for that file in LIMITS.
- `managed_blocks.py` BLOCKS[0]: the short restore body is intended; the longer one in git history is not the right one.

## Mods (plan-pane)
- `claude plugin validate` reads a hook matcher only from a plain literal const: `requestId: PANE.id` shows as `requestId=?` though tests pass.
- `claude plugin test` refuses the `claude` shell alias: call `/Users/unmassk/.local/bin/claude`.
- `claude plugin test unmassk-toolkit` resolves the plugin from the cwd: run it from the repo root, not from inside unmassk-toolkit/.
- The skill's types can be newer than the installed engine: Text `weight` is declared (2.1.299) but 2.1.287 refuses it, and one refused prop blanks the whole pane.
- Two engines on this machine: the CLI `~/.local/bin/claude` is 2.1.287; the desktop app's is `~/Library/Application Support/Claude/claude-code/2.1.299/*/claude.app/Contents/MacOS/claude`. Run mod tests on both.
- Any `$.state` key fails `validate` unless plugin.json names a `"types"` .d.ts declaring it in PluginState.
- No tsc on this machine: a mod's type-check stays UNVERIFIED unless one is installed.
- As a subagent I have no Skill tool and the built-in `plugin-authoring` skill has no file on disk: learn the mod API from plan-pane.tsx and the tests.
- `$.ui.invalidate('ui.render')` in plan-pane's 1 s tick redraws every render hook of the plugin, the AbovePrompt band too.
- plan-agents tests pin the agent's whole first answer line in its row: a "first word only" status turns them red.
- In the test kit `$.ui.resolve(e)` on the terminal still hands back an `Svg` that draws nothing: branch on `e.surface`, never on whether Svg exists.

## chatroom/
- Bun `mock.module()` leaks across test files: assert on DB state, or use a `_setXForTesting()` setter.
- Elysia `publishToSelf` does nothing: deliver to self by hand. The WS `upgrade()` hook ignores return values.
- React StrictMode runs effects twice: a second `connect()` kills the socket that is still CONNECTING.
- health_plans can't change what the boot shows on its own: every ⚠ line in CHECKS/COUNTS is drawn by boot.py from fixed HealthReport fields, so a new kind of warning needs boot.py in scope.
- Engine 2.1.287 `$.tool.register` passes only name/description/inputSchema (isDeferred dropped before the hook chain and ignored at the bottom); a `tool.describe` answer's isDeferred is honoured. The test kit's `$.tool.describe(...)` does raise the event.
