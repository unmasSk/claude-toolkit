---
name: Anti-patterns found in ops scripts, hooks, and chatroom bridge plans
description: Recurring shell, Python, and TypeScript/Bun anti-patterns found in ops-containers, ops-scripting/ops-observability skills, unmassk-crew hooks (2026-03-14, 2026-03-16), chatroom bridge plan (2026-03-18), and chatroom @mention depth feature (2026-03-18)
type: project
---

## Commit touches an agent-memory MEMORY.md index without the topic file it points to

Confirmed 2026-07-07 in commit 38f5728 (encoding_guard.py fix, issue #52): the commit added a line to `.claude/agent-memory/unmassk-toolkit-ultron/MEMORY.md` pointing to `unmassk-toolkit-python-entrypoints.md`, but that topic file itself was never `git add`-ed — it existed only as an untracked file on the author's disk (`git show <sha>:<path>` failed with "exists on disk, but not in <sha>"). Anyone who clones/checks out that commit alone gets a dangling memory link. This is Issue-tier, not a nitpick — it breaks the memory system's own integrity contract.

Check pattern for future commit reviews: whenever a diff touches any `agent-memory/*/MEMORY.md`, extract every new `[Title](file.md)` line added, then run `git show <sha>:<path-to-file.md>` for each — if it fails, the commit is incomplete.

## "Mirror" functions drift out of sync on defense-in-depth guards (parse_date / time_ago)

Confirmed 2026-07-08, issue #55 final round (`lib/date_parsing.py::parse_date()` vs `lib/boot_git_checks.py::time_ago()`). Both functions share the same docstring cross-reference ("mirrors the other's ... shape") and got the same `isinstance(str)` + `isascii()` guards added in lockstep across two review rounds. But `parse_date()` also has an explicit `if len(date_str) > 20: return None` length guard (defense-in-depth ahead of `int()`, added for SEC-LOW-002) that was never mirrored onto `time_ago()`. Not a live bug — CPython's own `sys.get_int_max_str_digits()` limit and `datetime.fromtimestamp()`'s `OverflowError` both land inside `time_ago()`'s existing except tuple, so it fails safe by accident, same as `parse_date()` did before its own explicit guard existed (see `TestParseDateLengthGuardContract`'s honesty note in `test_date_parsing_epoch_contract.py`).

Lesson: when two functions are documented as mirroring each other and a guard is added to one under an explicit "defense-in-depth, not dependent on interpreter limits" rationale, check whether the twin function needs the identical guard — don't just check that both got the same `isinstance`/`isascii()` treatment. Grep for the guard's own justification comment; if it says "not dependent on X", the other function inherits the same argument.

## set -e without -u or -o pipefail

Scripts in ops-containers/scripts/ use mixed `set -e` (generate_chart_structure.sh, generate_standard_helpers.sh, k8s-detect-crd-wrapper.sh, k8s-setup-tools.sh) while most others use `set -euo pipefail`. The correct baseline for all scripts in this project is:

```bash
set -euo pipefail
```

Flag any script that uses `set -e` without `-u` and/or without `-o pipefail`.

## source activate inside non-interactive scripts

`k8s-detect-crd-wrapper.sh` uses `source "$TEMP_VENV/bin/activate"` then bare `pip install`. This is wrong: it pollutes the caller's environment and may resolve to the wrong pip. The correct pattern (used in `helm-detect-crd-wrapper.sh`) is:

```bash
python3 -m venv "$TEMP_VENV" >/dev/null 2>&1
"$TEMP_VENV/bin/python3" -m pip install --quiet --disable-pip-version-check pyyaml
"$TEMP_VENV/bin/python3" "$PYTHON_SCRIPT" "${FILES[@]}"
```

## Unquoted variable in trap

`trap "rm -rf $TEMP_VENV" EXIT` expands the variable at definition time. If it contains spaces this silently deletes the wrong directory. Always use single quotes for trap bodies:

```bash
trap 'rm -rf "$TEMP_VENV"' EXIT
```

## #!/bin/bash shebang for scripts requiring bash 4+

Scripts using arrays, `[[`, `BASH_REMATCH`, or `((...))` must use `#!/usr/bin/env bash` because macOS ships `/bin/bash` 3.2. Four scripts in this directory have the wrong shebang.

## set -- "${POSITIONAL_ARGS[@]}" when array may be empty

Under `set -u`, an empty array expansion with `"${arr[@]}"` produces a single empty string argument on some bash versions. Guard with:

```bash
if [ ${#POSITIONAL_ARGS[@]} -gt 0 ]; then
    set -- "${POSITIONAL_ARGS[@]}"
else
    set --
fi
```

## ((...)) arithmetic increment under set -e

`((var++))` exits with code 1 when var is 0 (the result of the expression is 0 = falsy). Under `set -e` this terminates the script. Use `var=$((var + 1))` instead.

Confirmed in ops-cicd Jenkins scripts: `jenkins-best-practices.sh:40,47,54,60`, `jenkins-validate-declarative.sh:37,44,51`, `jenkins-validate-scripted.sh:37,44,51`. All use `((ERRORS++))` / `((WARNINGS++))` etc. as counters starting at 0. The first found issue kills the script silently.

Reference implementation: `jenkins-validate-shared-library.sh` uses `ERRORS=$((ERRORS + 1))` — use this as the correct model.

Note: `jenkins-common-validation.sh` has the same `((var++))` but uses `set -uo pipefail` (no `-e`, intentional) — this is a false positive. Do NOT flag it.

## Wrong sys.path subdirectory in Python generators

`jenkins-generate-declarative.py` and `jenkins-generate-scripted.py` use:

```python
sys.path.insert(0, str(Path(__file__).parent / 'lib'))
```

But the actual module directory is `jenkins-lib/`, not `lib/`. This produces `ModuleNotFoundError` on cold-start. Always verify the actual directory name before flagging — check `ls scripts/` to confirm.

Also found in `jenkins-test-declarative.py:12`. The test scripts that use `SCRIPT_DIR` directly without a subdirectory (e.g., `jenkins-test-shared-library.py`) are correct.

## bash -n with multiple file arguments

`bash -n file1 file2 file3` only checks file1 syntax; file2 and file3 are positional arguments to that check, not independent checks. Correct:

```bash
bash -n file1
bash -n file2
bash -n file3
```

## Python `or`-based defaults replace falsy caller values

`kwargs.get("key") or default` silently replaces 0, empty string, and False with the default even when the caller explicitly passed those values. Use `is not None` instead:

```python
# WRONG
value = kwargs.get("ingestion_rate_mb") or 10

# CORRECT
value = kwargs["ingestion_rate_mb"] if kwargs.get("ingestion_rate_mb") is not None else 10
```

Found in: `loki-generate-config.py` `_generate_monolithic`, `_generate_simple_scalable`, `_generate_microservices`. The fluentbit generator explicitly tests and documents the fix (`TestFalsyDefaults`).

## `exit $?` after a command under `set -e` is unreachable on failure

```bash
some_command "$@"
exit $?   # only reached when some_command succeeds (exit 0)
```

Under `set -e`, if `some_command` exits non-zero, the script is already terminated before `exit $?` runs. Save the exit code explicitly:

```bash
local rc=0
some_command "$@" || rc=$?
exit "$rc"
```

Found in: `shellcheck_wrapper.sh:49` `check_system_shellcheck()`.

## ASCII box line[:85] + '|' truncation pattern

In `skill-search.py` `format_ascii()`, the corpus line is constructed as:
```python
lines.append(f'|  Corpus: {total_skills} skills indexed ...|'[:85] + '|')
```
The intent is to pad to 85 chars. The pattern is fragile: if the raw string is exactly 85 chars, slice returns all 85 then '|' is appended making it 86 chars (one over the box). For skill counts >= 100, the raw string is already 86+ chars and the slice-then-append makes it 86, misaligning the closing border.

Correct pattern: use an f-string with explicit ljust or format spec to 83 inner chars, then wrap in '| ... |'.

## Unused wrapper function (thin forwarding)

`get_plugin_json_path()` in `bump-version.py` is a one-line wrapper that just calls `safe_plugin_path()`. It is never called internally (all callers use `safe_plugin_path()` directly or `load_plugin_json()`). Dead code.

## --all error path saves partial state without rollback

In `bump-version.py` `main()`, the `--all` path calls `bump_plugin()` in a loop and then `save_marketplace()` regardless of per-plugin failures. If one plugin's marketplace entry fails to update (plugin not found), `save_marketplace()` still persists the partial changes. No dry-run or rollback mechanism.

## Windows drive-letter case mismatch in path startswith checks

`git rev-parse --show-toplevel` on Windows Git Bash returns lowercase drive letters (e.g., `c:/Users/...`). `os.path.abspath()` returns OS-cased paths (e.g., `C:\Users\...`). After `.replace("\\", "/")` you get `C:/Users/...`. A `str.startswith()` comparison between `c:/Users/...` and `C:/Users/...` is case-sensitive and fails silently.

Correct pattern — always normalize case before comparison on Windows-hosting code:

```python
if resolved.lower().startswith(valid_prefix.lower()):
```

Or use `os.path.normcase()` on both sides before the comparison (platform-aware).

Found in: `unmassk-crew/hooks/validate-memory-path.py:63` (2026-03-16).

## os.path.abspath() anchored to cwd, not to project root

`os.path.abspath(relative_path)` resolves against `os.getcwd()`, which in a subprocess hook context is NOT guaranteed to be the git root. An agent writing a relative path like `backend/.claude/agent-memory/...` will resolve it against whatever cwd the hook process was spawned with.

Correct pattern — anchor relative paths explicitly:

```python
if os.path.isabs(file_path):
    resolved = os.path.normpath(file_path)
else:
    resolved = os.path.normpath(os.path.join(git_root, file_path))
resolved = resolved.replace("\\", "/")
```

Found in: `unmassk-crew/hooks/validate-memory-path.py:61` (2026-03-16).

## Dead negative lookahead for `git mergetool` exclusion

In `pre-merge-gate.py`, the regex includes `(?!\s*tool\b)` intended to exclude `git mergetool`. This is dead code: `\bgit\s+merge\b` never matches `git mergetool` because the word boundary `\b` after `merge` requires a non-word character — but in `mergetool`, the character after `merge` is `t` (word character). The lookahead never fires and creates false documentation confidence.

Correct regex (remove the dead lookahead):
```python
_GIT_MERGE_RE = re.compile(
    r'\bgit\s+merge\b(?!\s*--abort\b)(?!\s*--continue\b)'
)
```

When reviewing hook regexes that claim to exclude subcommands: verify whether the base pattern would even match the subcommand before adding a lookahead for it.

Found in: `unmassk-crew/hooks/pre-merge-gate.py:17-19` (2026-03-16).

## Dual severity framework conflict in agent mode definitions

Agent mode instructions that define two independent severity/category axes (e.g., category: Issue/Suggestion/Nitpick AND severity: Critical/Major/Minor/Trivial) produce incoherent combinations (e.g., "Nitpick Critical"). If both dimensions are needed, add an explicit constraint table showing valid combinations. Otherwise collapse to one axis.

Found in: `unmassk-crew/agents/cerberus.md` commit-review mode (2026-03-16).

## Mode-scoped "do NOT" instructions conflicting with unconditional MANDATORY sections

When an agent has multiple modes and one mode prohibits an action (e.g., "do NOT touch memory in merge mode"), any MANDATORY section below it that covers the same action without a mode guard creates a direct instruction conflict. Always add an explicit mode conditional to MANDATORY sections, or move them above the mode definitions.

Found in: `unmassk-crew/agents/alexandria.md` — merge mode says "do NOT touch memory", Shutdown section says MANDATORY save (2026-03-16).

## IPC via /tmp files in a security-hardened WS codebase

Using `/tmp` flat files as IPC for a bridge component that connects to a hardened WebSocket server creates a perimeter mismatch: all the server-side guards (origin check, rate limit, Zod validation, author enforcement) are bypassed because the bridge holds a trusted long-lived connection and forwards anything placed in the file. This pattern appeared in the chatroom claude-bridge plan (2026-03-18).

Correct pattern: keep the IPC file under `$XDG_RUNTIME_DIR` (user-private), `chmod 600` immediately, validate owning UID before reading, enforce per-send rate limit and message length cap in the bridge itself before forwarding to WS.

## Polling a file with setInterval when Bun.watch() is available

Using a 500ms `setInterval` to poll an outbox file for new content is a patch when the runtime already provides `Bun.watch()` for zero-latency change detection. Pattern seen in claude-bridge plan (2026-03-18). Always use `Bun.watch()` first; fall back to polling only on platforms where it is unavailable (document explicitly).

## Reserved name set with explicit exclusions that create identity collision

A `RESERVED_AGENT_NAMES` Set that filters OUT certain names (e.g., `!== 'claude'`) to allow them as WS client names creates an identity collision when a bridge script connects with that exact name. If the server sets `authorType='human'` for all WS client messages, the excluded name appears as a human in the DB and triggers @mention agent invocations. Found in chatroom ws.ts + bridge plan (2026-03-18) and confirmed again in claude-bridge.ts implementation audit (2026-03-18). Either: (a) do not exclude names from the reserved set without a corresponding authorType distinction, or (b) introduce a dedicated `authorType='orchestrator'` that bypasses mention parsing.

## Dead parameter in multi-argument guard function (TypeScript)

A function that accepts a parameter (e.g. `authorType: AuthorType`) and uses it in neither the guard condition nor the body creates a false contract. Callers believe the function is author-aware; tests pass for the wrong reason. Found in `mention-parser.ts:extractMentions` (2026-03-18): `authorType` was accepted but unused — the depth guard fired unconditionally for all author types.

Pattern to watch for: functions with a discriminant parameter (`authorType`, `role`, `mode`) whose body contains only one branch. Verify the parameter is read somewhere in the body before approving.

## Bridge singleton check defeated by auth on health endpoint

When a bridge process checks for an existing instance by probing `GET /health` unauthenticated, applying an auth guard to ALL routes (including `/health`) causes the probe to receive `401` instead of `200`. The singleton check only treats `200` as "already running", so `401` is silently interpreted as "no bridge present". Two instances start up. Found in `claude-bridge.ts:checkSingleton + handleRequest` (2026-03-18).

Rule: health/liveness endpoints MUST be exempt from auth if they are used for singleton detection or readiness probing.

## Inline log wrapper anti-pattern: coercing objects to strings manually

In `agent-invoker.ts`, `ws.ts`, and `mention-parser.ts`, a custom `log()` wrapper is defined:
```typescript
function log(...args: unknown[]) {
  logger.info(args.map(a => typeof a === 'object' && a !== null ? JSON.stringify(a) : String(a)).join(' '));
}
```
This defeats pino's structured logging — objects are serialized as opaque strings, losing field-level searchability. The project convention (`createLogger` → `logger.info({ field }, 'message')`) must be used directly. The `log` wrapper is a workaround for a missing import pattern and should be removed in favor of consistent `logger.info({ ... }, 'message')` calls.

## Duplicated rate-limit bucket implementation across api.ts and test files

`checkApiRateLimit` in `api.ts` and `checkInviteRateLimit` in `invite.test.ts` (and `checkRateLimit` in `ws.ts`) contain identical token-bucket logic (3 copies). The bucket algorithm is non-trivial (refill formula, cap logic). If the formula has a bug, it must be fixed in 3 places. Extract to a shared `createBucket(max, windowMs)` factory. This hits the 3+ duplication threshold for mandatory abstraction.

## `inFlight` lock keyed by agent name only (not agent:room)

Using a `Set<string>` keyed by agent name alone for a per-agent in-flight lock blocks the agent across ALL rooms when the desired scope is per-agent-per-room. The `activeInvocations` map uses `${agentName}:${roomId}` — the `inFlight` lock must use the same compound key for consistency. Found in `agent-invoker.ts:inFlight` (2026-03-18). Check that all concurrency primitives in the same module use the same key scope.

NOTE (2026-03-18 follow-up): This was already fixed — `agent-invoker.ts:144` uses `${agentName}:${roomId}` as the compound key. Do not re-flag.

## Unbounded in-memory token Map with public unauthenticated endpoint

An in-memory `Map<string, TokenEntry>` for WS auth tokens with no size cap, combined with a `POST /api/auth/token` endpoint that is unauthenticated and has no rate limit, creates a memory-exhaustion vector. The GC interval only removes expired entries; it does not cap total size. Found in `auth-tokens.ts` (2026-03-18).

Rule: any in-memory store fed by a public endpoint must have an upper-bound (`TOKEN_MAX`) checked in the issuer function before inserting.

## Async reconnect path that omits retry on token fetch failure

When a WS connect function is wrapped in an async IIFE to fetch an auth token first, the catch block for token fetch failure must schedule a reconnect the same way `ws.onclose` does — otherwise token fetch errors leave the UI silently stuck in `disconnected` while WS-level errors correctly retry. Found in `ws-store.ts` (2026-03-18).

Asymmetry pattern: `ws.onclose` → retry; token fetch error → no retry. Always mirror the reconnect logic across all error paths in the same connect flow.

## Token in WS query string without documenting the access-log risk

Passing a short-lived auth token as `?token=<uuid>` in the WS upgrade URL is the only standard option when the `Authorization` header cannot be set (browser WebSocket). However, the token appears in server access logs if logging is enabled. This is acceptable for localhost dev tools, but the trade-off must be documented in a code comment. Found in `claude-bridge.ts:247` and `ws-store.ts` (2026-03-18).

## Dead function after render-path migration (React)

When a React component is migrated from a manual render path (e.g., splitting text with a helper function) to a declarative renderer (e.g., ReactMarkdown), the helper function is often left defined but not wired into the new renderer. The component compiles and renders without errors, but the feature silently stops working.

Pattern to detect: a named function that returns `React.ReactNode[]` or similar, defined in the same file as a component, but never called in the JSX. Always verify that helper functions from the old render path are either deleted or re-wired into the new one.

Found in: `MessageLine.tsx:splitMentions` (2026-03-18) — function defined, ReactMarkdown migration did not wire it in, @mention CSS highlighting silently broken.

## Fenced code block `isBlock` heuristic via `className` presence

In ReactMarkdown, the `code` component prop receives `className="language-xyz"` for fenced code blocks with a language specifier, and `className={undefined}` for both inline code AND fenced code blocks with no language tag. The pattern `const isBlock = !!className` incorrectly renders unlabeled fenced blocks as inline code.

Correct pattern — use the `node` AST prop (available in react-markdown v9+) to check whether the parent is a `pre` element, or check `node.position.start.line !== node.position.end.line` as a multiline heuristic.

Found in: `MessageLine.tsx:65` (2026-03-18).

## NODE_ENV bypass comment says "dev" but applies to all non-production environments

A guard `process.env.NODE_ENV !== 'production'` activates in staging, test, and undefined environments — not just "dev". Documenting it as "In dev, ..." misleads operators who run staging without NODE_ENV=production and believe they are protected.

Always say "non-production environments (NODE_ENV !== 'production')" and add an explicit NOTE that staging operators must set NODE_ENV=production.

Found in: `config.ts:78` (chatroom WS_ALLOWED_ORIGINS dev bypass, 2026-03-18).

## Duplicate function declaration in same module (TypeScript)

When a module is refactored to export a shared function (e.g. `getReservedAgentNames()`), the old local version is sometimes left in place under a slightly different return type (`Set<string>` vs `ReadonlySet<string>`). TypeScript will reject duplicate `export function` declarations with the same name at compile time — but in some editors or loose tsconfig setups the error is surfaced as a type conflict rather than a clear duplicate. The fix is to delete one of the two declarations, keeping only the one with the correct return type.

Found in: `auth-tokens.ts:49-65` (2026-03-19) — two `export function getReservedAgentNames()` declarations, return types `Set<string>` and `ReadonlySet<string>` respectively.

## Dead `if not top` guard after already-proven non-empty slice

When a list is guaranteed non-empty by a prior guard AND the slice index is clamped to >= 1, the `if not top: return None` after the slice is unreachable dead code. It compiles but misleads readers into thinking the empty case is possible.

Pattern: `if not within_window: return None` (guard) → `within_window.sort(...)` → `top = within_window[:max_results]` → `if not top: return None` (dead).

Found in: `unmassk-toolkit/lib/recall.py:440` in `recall_relevant()` (2026-06-12).

## pre-memory-dedup-gate: _TRAILER_PATTERN only matches double-quoted --trailer values

`pre-memory-dedup-gate.py` intercepts `python3 git-memory-commit.py memo ...` commands and looks for `--trailer "Memo=..."` (double-quoted). If Claude writes `--trailer 'Memo=value'` (single quotes) or `--trailer Memo=value` (unquoted), `_TRAILER_PATTERN` returns `None` → `_allow_passthrough()` fires → dedup check is silently skipped.

The COMMIT_PATTERN fires on both forms, so the hook correctly identifies memo/remember commits. Only the TRAILER value extraction is fragile.

Found in: `unmassk-toolkit/hooks/pre-memory-dedup-gate.py:158` (2026-06-12).

## post-validate-commit-trailers.py missing 'remember' commit type

`pre-validate-commit-trailers.py` validates `remember` commits (checks `Remember:` trailer present + valid category). `post-validate-commit-trailers.py` does NOT have a corresponding `elif commit_type == 'remember':` branch — the type falls through to only Memo/Risk/Issue format checks. Belt-and-suspenders are asymmetric for remember commits.

Found in: `unmassk-toolkit/hooks/post-validate-commit-trailers.py` validate_trailers() (2026-06-12).

## Session-start-boot tombstone window: glossary memos bypass retired tombstones

`session-start-boot.py` populates `tombstones` from the `-n30` scan in `extract_memory()`. `extract_glossary_cached()` scans `--all -n500`. If a `Resolved-Memo` tombstone is between commits 31–500 (pushed out of the -n30 window by new work) and the glossary returns the tombstoned memo (no tombstone logic in `extract_glossary()`), the merge step's `normalize(text) not in tombstones` check passes because `tombstones` does NOT contain the now-out-of-window tombstone. The retired memo reappears in the boot output.

Trigger: active project, >30 commits since a Resolved-Memo or Resolved-Remember was written.

Found in: `unmassk-toolkit/hooks/session-start-boot.py` main() MEMOS/REMEMBER merge block (2026-06-12).

**UPDATE (2026-07-04 full-file audit):** The window-gap version of this bug is RESOLVED — `extract_glossary()` now collects and returns its own `tombstones` (from the full `--all -n500` scan), and `main()` unions them with the recent-window tombstones before filtering (`tombstones = memory.get("tombstones", set()) | glossary.get("tombstones", set())`). Do not re-flag the original window-gap scenario.

However, a narrower **still-open variant** exists: the crown-override REPLACE branch for Memo entries never re-checks tombstones, only the initial-insert branch does. In both `extract_glossary()`'s own internal crown resolution (`memos[i] = (label, trailers["Memo"], True)` around line 611-615) and in `main()`'s MEMOS glossary-merge (`all_memos[i] = (gscope, gtext, True)` around line 1216-1220), the pattern is:
```python
if scope not in X and normalize(text) not in tombstones:   # tombstone checked here
    ...
elif is_crown:                                               # NOT checked here
    for i, ...:
        if match: X[i] = (..., True); break                  # replay of tombstoned text possible
```
Repro: an old crowned Memo commit (pushed beyond SCAN_DEPTH into glossary-only territory) whose text is later tombstoned via `Resolved-Memo`, combined with a newer non-crowned Memo commit for the SAME scope that is within SCAN_DEPTH. The crowned-but-retired text overwrites the live entry because the REPLACE path skips the tombstone check that the ADD path has. `test_boot_tombstones.py` only covers the simpler "new scope, glossary insert" tombstone path (`TestTombstonedMemoDoesNotReappearViaGlossary`) — it does not cover "crown replaces an already-populated scope". T2 finding, still open as of 2026-07-04 audit.

**RESOLVED (2026-07-05 re-audit, CRB-01):** Ultron extracted a single shared `_crown_replace(entries, key, text, tombstones=None)` helper (now in `lib/boot_memory.py`) that all 6 former call sites use (2x in `extract_memory()`, 2x in `extract_glossary()`, 2x in `session-start-boot.py`'s glossary-merge for Decisions/Memos). The REPLACE branch now takes an explicit `tombstones` parameter and no-ops if the crowned text is tombstoned — verified by direct code read at `lib/boot_memory.py:74-99,231-232,341-344` and `hooks/session-start-boot.py:818`. Decisions correctly omit `tombstones` (no tombstone concept for that memory kind, documented in the function's own docstring). This also fixed the pre-existing 6x duplication (formerly CRB-03). Do not re-flag this specific variant; the shared-function extraction closes it structurally (a future call site cannot reintroduce the bug without also skipping the shared helper).

## has_recent_memory_commits() misses scopeless memory commits

`stop-dod-check.py has_recent_memory_commits()` checks `cleaned.startswith('decision(')` etc. (open-paren form). Commits with no scope — `memo: prefer X` or `decision: chose JWT` — do NOT match. The reminder fires even when memory was legitimately captured without a scope, incorrectly pushing Claude to write a redundant commit.

Found in: `unmassk-toolkit/hooks/stop-dod-check.py:142` (2026-06-12).

## Shared sanitizer that does not cover its own delimiters

A sanitizer function that strips all known trust-boundary markers from user content will be incomplete if the system later adds a new delimiter (e.g. box-drawing chars for a RESPAWN notice) without adding a corresponding strip pattern to the sanitizer. The gap means stored messages containing the new delimiter pass through unsanitized.

Pattern to detect: when a new structural delimiter is introduced (constant like `RESPAWN_DELIMITER_BEGIN`), check whether `sanitizePromptContent` (or equivalent) has a matching `.replace()` for it. If not, flag the omission.

Correct fix: add a pattern to the sanitizer that strips any sequence matching the delimiter format, e.g.:
```typescript
.replace(/\u2550{2,}[^\n\u2550]*\u2550{2,}/g, '[DELIMITER-SANITIZED]')
```

Found in: `agent-invoker.ts:sanitizePromptContent` (2026-03-19) — RESPAWN delimiters (U+2550) not covered after box-drawing delimiter hardening.

## Fallback path-existence flag not reset when the write it guards fails

When a function writes a file inside a `try/except OSError: pass` (silent-fail, correct on its own — the caller must not crash) but sets the "path exists / is available" variable *before* the try block instead of only on successful write, any downstream branch that checks `if path_var: use path_var` cannot distinguish "wrote successfully" from "write failed, pass'd silently." If that downstream branch is a size/budget check that decides between "print everything inline" vs "print a short pointer to the file," a failed write reproduces the exact bug the pointer-file design was meant to fix: the short banner claims the full content is in the file, but the file was never written (first run) or is stale (later runs) — the real content, e.g. the harness-truncation-preventing "Next:" line, is silently lost.

Reproduced live (not just static reading) in `session-start-boot.py:1291-1301`: `boot_log_path` is set right after `if project_root:`, before the `try/except OSError`. `os.chmod(claude_dir, 0o500)` (read-only, simulating disk-full/permission-denied/read-only-fs, e.g. sandboxed CI) + a giant `context()` commit that exceeds `STDOUT_FULL_INLINE_BUDGET_BYTES` (6000) → hook exits 0, prints the "minimal banner" telling Claude to read `boot-log-latest.txt`, but the file does not exist (`os.path.isfile() == False`). No test in `test_boot_output.py` covers this path (grep for OSError/chmod/PermissionError in that file returns nothing) — the entire 42-test contract was RED/GREEN only for the happy path.

Correct fix: only treat the log path as "available" after the `open()`+`write()` inside the try succeeds — e.g. set `boot_log_path = None` initially and only assign the real path on success, or use a separate `log_write_ok: bool` flag; then in the branch condition, treat write failure the same as "no project root" → fall through to printing `full_text` inline unconditionally (safer than pointing at a promise that isn't there), regardless of size.

General rule when reviewing "write full content to file, print short pointer on stdout" fallback designs: always check whether the "pointer is safe to print" condition is coupled to write *success*, not just to whether a path *could theoretically* be computed. Test the OSError branch explicitly (chmod a parent dir read-only, or monkeypatch `open`) — a happy-path-only contract will pass 100% green while reintroducing the original bug under any permission/disk-full condition.

## Module-split refactors: verify the split didn't leave behind orphaned duplicates/dead values

Found during the 2026-07-05 re-audit of `session-start-boot.py`'s CRB-04 split into `lib/boot_memory.py` + `lib/boot_migrations.py`:

1. **Duplicated fallback function across the split.** `open_no_follow_symlink`'s defensive fallback (used when `git_helpers` is stubbed by a test) is defined byte-identically in both `hooks/session-start-boot.py:42-46` and `lib/boot_memory.py:32-36`. Before the split it existed once. Nothing enforces the two copies stay in sync if the real `git_helpers.open_no_follow_symlink` implementation ever changes (e.g. different flags/permission bits) — a security-relevant helper (SEC-CRIT-001 symlink guard) silently drifting between two copies is a real risk. When a module is split and a defensive-import fallback is needed in more than one of the resulting files, either factor the fallback into a tiny shared helper, or add a cross-reference comment + a test asserting both copies are identical.

2. **CRB-05 (stderr breadcrumb for previously-silent excepts) applied inconsistently.** Only 3 of ~13 `except OSError`/`except Exception` blocks across the three files got the one-line stderr breadcrumb (`run_doctor`, `run_repair`, `_migrate_stale_context_writer_statusline`). The single highest-value one — `write_boot_log`'s `except OSError: return None` at `hooks/session-start-boot.py:966`, which is the exact trigger for the "print full text inline" safety fallback that Cerberus/House/Yoda spent the most design effort on — has NO breadcrumb. If it ever fires in production there is zero signal that the boot log write failed; the only symptom is a silently different (larger) stdout output. When applying a "add a breadcrumb to silent excepts" fix, grep for ALL matching except blocks in the touched files, not just the ones near the original finding's report.

3. **Dead unpacked return value after extraction.** When a monolithic function is split into `render_*_section()` helpers that each return a tuple, check whether every element of the tuple is actually read again by the caller. `render_branch_section()` returns `behind_n` (its docstring claims "all reused downstream") but `main()` never reads it again after unpacking — the pull-recommendation line that needed it already ran *inside* `render_branch_section()` before returning. Only 5 of the 6 returned values are actually reused downstream. A return-tuple docstring that says "all reused downstream" should be re-verified against the actual caller, not assumed from the pre-split code's structure.

**RESOLVED (2026-07-05 re-audit round 2):** `behind_n` is no longer returned at all — `render_branch_section()` (`lib/boot_render.py:487-526`) now computes the "PULL RECOMMENDED" line itself before returning, and the docstring was corrected to say so explicitly ("not part of the return value ... it used to be returned but was never actually consumed"). Do not re-flag.

## Module-split re-introduces the exact hard-limit violation it was meant to fix, one file over

When Ultron splits an oversized file (`session-start-boot.py`, 1110 LOC, T2 — over the project's 500-LOC HARD LIMIT per unmassk-standards §22 Structure) into smaller modules to close the finding, ALWAYS re-measure every NEW file the split produced — do not just confirm the original file shrank. Found in the 2026-07-05 CRB T2-1 re-audit: `hooks/session-start-boot.py` correctly dropped to 298 LOC, but the extracted `lib/boot_render.py` is 875 LOC — still 75% over the same HARD LIMIT the fix was supposed to close. The violation didn't disappear, it moved.

Compounding issue: `boot_render.py`'s own module docstring claims its functions are "cohesive... pure 'given inputs, produce these briefing lines' functions" — but roughly a third of the file (`check_skill_drift`, `check_version_mismatch`, `run_doctor`, `run_repair`, `check_issue_status`, plus their private helpers `_md5_file`, `_latest_version_dir`, `_build_repo_skill_index`) does real I/O (subprocess, filesystem walk, `gh` CLI network calls) and has nothing to do with "rendering briefing lines" — it's health/version/issue-status probing. The `render_*_section()` functions that DO belong under a "renderer" umbrella call into this I/O layer, so even they aren't pure. The correct fix is a second split: extract the I/O/health-check layer into its own module (e.g. `lib/boot_checks.py`), leaving `boot_render.py` with only the text-formatting/section-assembly functions. Verify the LOC count of both resulting files against the hard limit before accepting the split as closed.

## Split introduces a NEW named-module sys.modules pollution vector when a stub test doesn't clean up transitive imports

`tests/test_migrate_statusline.py` stubs `sys.modules["git_helpers"]` (and `parsing`, `version`) with a fake module, then loads `hooks/session-start-boot.py` in-process via `spec_from_file_location` + `exec_module`, and restores the three stubbed names in a `finally` block. Before the CRB-04/T2-1 split, this was safe: the hook file's own top-level `from git_helpers import run_git, ...` bound to a THROWAWAY module object each call (module name changes or isn't reused across tests), so nothing lingered in `sys.modules` under a stable key.

After the split, `session-start-boot.py`'s `from boot_memory import (...)` / `from boot_render import (...)` / `from boot_migrations import (...)` cause Python's import machinery to cache these THREE new modules under their real, stable names in the GLOBAL `sys.modules` — and each of them does `from git_helpers import ensure_gitignore, run_git` (boot_memory.py, boot_migrations.py) or `from git_helpers import run_git, commits_since_last_consolidation` (boot_render.py) at module level, binding to whatever `git_helpers.run_git`/`ensure_gitignore` IS at that exact moment. If this test's stubbed exec_module happens to be the first time any of these three modules gets imported in the pytest process, they get PERMANENTLY cached with `run_git` frozen to the stub's `lambda *a, **kw: (1, "")` — for the rest of the pytest process, regardless of the test's own stub-restore `finally` block (which only restores `git_helpers`/`parsing`/`version`, not `boot_memory`/`boot_render`/`boot_migrations`).

Reproduced live (2026-07-05): running the stub-and-restore sequence once, then a plain `import boot_memory; boot_memory.run_git(...)` afterward in the same process returns the stubbed `(1, "STUBBED")` sentinel, not a real git result.

**RESOLVED (2026-07-05 re-audit round 3, CRB-final):** `git_helpers` imports (`run_git`, `ensure_gitignore`, `commits_since_last_consolidation`) are now deferred into function bodies in all of `lib/boot_memory.py`, `lib/boot_checks.py` (new), `lib/boot_render.py`, and `lib/boot_migrations.py` — verified by grepping every module-level `from git_helpers import` line in the 4 files and confirming each is indented inside a function. `tests/test_migrate_statusline.py::TestSysModulesContaminationRegression` (3 tests, written specifically to prove this, not just claim it) now PASSES — ran it live, 8/8 green. Do not re-flag this specific vector. Note: `open_no_follow_symlink`'s `try/except ImportError` fallback import IS still at module level in `boot_memory.py`/`boot_checks.py`/the hook file — this is safe by design (not a re-introduction of the bug): the fallback always resolves to the real, never-stubbed `lib/_symlink_safe_open.py` implementation regardless of whether `git_helpers` is stubbed, so there is no "freeze to a wrong stub" risk the way there was for `run_git`.

Currently DORMANT (does not manifest as a live test failure) only because no other test in the current suite does a plain in-process `import boot_memory`/`import boot_render`/`import boot_migrations` — every other consumer either goes through a fresh subprocess (`python3 -c "..."` in test_crown.py/test_crown_retraction.py/test_boot_output.py) or doesn't touch these modules at all. This is fragile: any future test (e.g. a faster in-process unit test of `extract_memory()`) that runs alphabetically after `test_migrate_statusline.py` in the same pytest invocation would silently get a poisoned `run_git`.

The module's own docstring in `lib/boot_memory.py` already reasons about exactly this class of bug for `parsing` (and defers those 4 imports into function bodies for that reason) but does NOT apply the same treatment to the `git_helpers`-derived names (`ensure_gitignore`, `run_git`, `commits_since_last_consolidation`), which stay bound at module level in all three split files. Correct fix: either (a) defer the `git_helpers` imports the same way `parsing` imports already are, or (b) have `test_migrate_statusline.py`'s stub `finally` block also pop `boot_memory`/`boot_render`/`boot_migrations` (and any other real modules the hook transitively imports) from `sys.modules`, forcing a fresh re-import next time. Found in `lib/boot_memory.py`, `lib/boot_render.py`, `lib/boot_migrations.py` + `tests/test_migrate_statusline.py` (2026-07-05).

## "No further split possible without circular import" claims must be checked against the actual import graph, not assumed

Round-4 fix split `lib/boot_render.py` (875 LOC) into itself (661 LOC) + new `lib/boot_checks.py` (306 LOC) to separate I/O from rendering. Ultron declined to split further, citing "would create an import circular with boot_checks.py." Re-audit round 5: this claim is FALSE. `grep "^from\|^import" lib/boot_checks.py` shows it imports only `boot_memory`, `version`, and stdlib — zero import of `boot_render`. The dependency graph is a one-directional DAG: `boot_memory ← boot_checks ← boot_render`. Since `boot_checks.py` never imports `boot_render.py`, it can safely absorb MORE functions from `boot_render.py` with no cycle risk.

Concretely, `boot_render.py`'s own module docstring claims "All subprocess/filesystem/network I/O ... has been extracted to lib/boot_checks.py" — also false. Five functions still do real I/O directly in `boot_render.py`: `get_timeline()` (28 lines, `run_git`), `get_last_context_time()` (19 lines, `run_git`), `render_branch_section()` (49 lines, 3x `run_git` calls), `render_scopes_section()` (49 lines, `open()`/`json.load()`/`os.listdir()`), `render_consolidation_section()` (24 lines, `commits_since_last_consolidation()`) — ~169 lines of direct I/O, not "pure formatting." A real second-level split (extract each function's raw-fetch step into `boot_checks.py`, leaving only the formatting/sanitization/parsing behind in `boot_render.py`) is achievable with the confirmed-safe DAG direction. Additionally, `render_remember_section()`/`render_decisions_section()`/`render_memos_section()` (39/45/43 lines) share near-identical crown-split + cap + partition-and-format logic — a 3x duplication a shared helper could collapse further.

Rule: when an agent declines an LOC-limit fix by citing "circular import," always verify the claim yourself by grepping the actual import lines of the target module before accepting the exception — do not take the stated risk at face value. Found in `lib/boot_render.py` (661 LOC, still over the 500 hard limit) — 2026-07-05 re-audit round 5, scored 100/110, still not mergeable against Bex's 109 floor.

**RESOLVED (2026-07-05 re-audit round 6, CRB T2-1 finally closed for boot_render.py):** `lib/boot_render.py` dropped to 458 LOC (under the 500 hard limit) — verified by direct `wc -l`. All 5 I/O functions named in round 5 (`get_timeline`, `get_last_context_time`, `render_branch_section`, `render_scopes_section`, `render_consolidation_section`, plus their only-callers `parse_branch_keywords`/`time_ago`) moved to `lib/boot_checks.py`, confirmed by reading both files in full — `boot_render.py` no longer contains any `run_git`/`open()`/`os.listdir()` call directly, only calls into the re-imported `boot_checks` functions. The module docstring was corrected: it no longer claims "all I/O extracted" as an absolute; it explicitly names the 5 functions moved and says round-5-remaining I/O now lives in `boot_checks.py`. The 3x duplication in `render_remember_section`/`render_decisions_section`/`render_memos_section` was collapsed into a shared `_render_crowned_capped_section()` helper (`boot_render.py:245-303`) — verified the DIFFERING merge logic per section was preserved correctly, not lost in the dedup: Remembers still dedup by normalized TEXT with no crown-replace (no `elif gis_crown` branch in `render_remember_section`'s own merge loop, only in the shared helper's docstring explaining why); Decisions still dedup by SCOPE with `_crown_replace(all_decisions, gscope, gtext)` (no tombstones arg, matching Decisions' documented no-tombstone-concept); Memos still dedup by SCOPE with `_crown_replace(all_memos, gscope, gtext, tombstones)` (WITH tombstones, preserving the CRB-01 fix). Ran the full targeted test suite (`test_boot_output.py`, `test_crown.py`, `test_crown_retraction.py`, `test_migrate_statusline.py`, `test_boot_tombstones.py`, `test_security_regression.py`, `test_regression_audit_round2.py` — 161 tests) live: 100% pass. Do not re-flag boot_render.py's LOC or docstring; both are now honest and correct.

**NEW T2 (round 6, same rule reapplied): `lib/boot_checks.py` grew to 561 LOC (over the same 500 hard limit) by absorbing the 5 functions moved out of boot_render.py.** This is the "violation moved one file over" pattern recurring for a third time. Verified further split is achievable, same as round 5's debunk: `grep "^from\|^import" lib/boot_checks.py` shows only `boot_memory`, `version`, stdlib — zero import of `boot_render` — so the DAG (`boot_memory ← boot_checks ← boot_render`) stays intact even if boot_checks.py itself is split into two children, since neither would need to import the other's sibling or boot_render. Concrete split: (a) `boot_health.py` — `_md5_file`, `_latest_version_dir`, `_build_repo_skill_index`, `check_skill_drift`, `check_version_mismatch`, `run_doctor`, `run_repair`, `check_issue_status`, `_issue_matches_next` (~330 LOC, "is the installed plugin/repo state OK" theme); (b) `boot_git_checks.py` — `parse_branch_keywords`, `time_ago`, `get_timeline`, `get_last_context_time`, `render_branch_section`, `render_scopes_section`, `render_consolidation_section` (~230 LOC, "read git/repo state for this boot" theme). Both only need `boot_memory`/`version`/stdlib. Unlike round 4/5's boot_render.py (which mixed *pure rendering* with *I/O*, a real concern-mixing bug), boot_checks.py is already single-concern (all I/O) — but "single concern" does not exempt a file from the hard LOC limit; the two sub-themes above are distinct enough to split cleanly. Scored T2 in the 2026-07-05 round-6 audit (100/110 again, still short of Bex's 109 floor) specifically because this is the third consecutive round where "we split it, narrowly missed the limit" repeats — the fix must be verified LOC-under-500 on ALL resulting files, every round, not just the file named in the previous finding.

**RESOLVED (2026-07-05 round 7, final): both new files land under the limit — `lib/boot_health.py` 303 LOC, `lib/boot_git_checks.py` 269 LOC, `lib/boot_checks.py` reduced to a 74-line pure re-export shim (verified: only `from boot_health import (...)` / `from boot_git_checks import (...)` + `__all__`, zero reimplementation). DAG confirmed unidirectional (`boot_memory ← boot_health/boot_git_checks ← boot_checks ← boot_render`), no circular import, `git_helpers` imports still correctly deferred into function bodies in both new files (module-level only for the `open_no_follow_symlink` try/except ImportError fallback, which is safe by the already-documented reasoning). Full test suite: 777 passed, 9 failed — all 9 in `tests/test_release.py` (`ModuleNotFoundError: No module named 'bin.release_helpers'`, a file that doesn't exist anywhere in the repo) — confirmed pre-existing and unrelated to any of the 17 files in this round (release.py/release_helpers.py untouched by the boot-split or the security sweep). Do not re-flag the module-split LOC issue; it is closed.

## Symlink-guard fix applied to one function but not its sibling reading the same fixed path (asymmetric sweep gap)

Found in the 2026-07-05 round-7 audit of the 14-file security sweep (Argus's symlink-follow-on-read/write hardening, tracked as BUG A-S in `tests/test_security_regression.py`). The sweep was thorough (14+ call sites fixed, ~20 dedicated regression tests, `TestBugPClaudeMdReadSymlink` explicitly documents the "asymmetric read/write" bug shape and fixed 5 CLAUDE.md-read call sites) but missed 2 more call sites of the *exact same* bug shape, in files that already contain a correctly-guarded sibling function reading the identical path:

1. `bin/git-memory-install.py:390` — `_update_claude_md()` reads CLAUDE.md via plain `open(claude_md)`, while `inspect()` in the SAME file (line 132) already uses `open_no_follow_symlink()` for the identical path, three lines above `_update_claude_md`'s own (correctly guarded) WRITE at line 401.
2. `hooks/user-prompt-memory-check.py:101` — `needs_upgrade()` reads CLAUDE.md via plain `open(claude_md)`, while `needs_install()` in the SAME file (line 59, ~40 lines above) already uses `open_no_follow_symlink()` for the identical path.

Exploitability is currently bounded (not zero) — in both cases the corresponding WRITE is already guarded, so a planted symlink can't be used to overwrite an arbitrary file via this exact path (the guarded write raises `OSError` and the caller fails safe). But the READ still follows the symlink and loads the victim file's content into memory (a confidentiality gap the codebase's own `git_helpers.open_no_follow_symlink()` docstring calls out as "symmetrically" as important as the write side) — and, more importantly as a process signal, it is the identical bug shape the team already swept for and fixed 5 times over in this same round. Neither site has a regression test (confirmed: grepped `tests/` for `_update_claude_md` and `needs_upgrade` — no test exercises either function's own CLAUDE.md read path; the existing `TestBugMNeedsUpgradeManifestSymlinkRead` only covers `needs_upgrade()`'s manifest.json read, a different check inside the same function).

Rule: when a security sweep fixes read+write pairs for a fixed/predictable path, grep EVERY function in the same file (not just the one named in the finding) that touches that same path — a sibling function performing the "twin" read/write is the highest-probability place the sweep misses, because pattern-matching on the reported call site doesn't catch a structurally identical one two functions away. Scored T2 in the round-7 (2026-07-05) audit — final score 98/110, below Bex's 109 floor, NOT MERGEABLE pending this fix + matching regression tests.

## Round-9 chokepoint fix (verify_path_within_project) shipped well but two live twins of the exact bug it targets were missed

`lib/git_helpers.py`'s new `verify_path_within_project()` (realpath + `os.sep`-anchored prefix check, `UnsafePathError(OSError)` subclass so existing `except OSError`/`except Exception` catch it for free) is correctly implemented and correctly wired into 6 real call sites (`ensure_runtime_dir`, `git-memory-install.py`'s `_cleanup_stale_settings_hooks`/`_create_manifest` x2, `git-memory-upgrade.py`'s `create_backup`/`apply_upgrade`'s manifest block). Round-8/9 re-audit (2026-07-05) confirmed by direct grep that its return value is never consumed at any of the 6 call sites (every caller re-derives the original, unresolved path for the actual `os.makedirs()`/`open()` call) — not a live bug on its own (check-then-use with the same input is safe absent a race), but it forfeits the extra TOCTOU-hardening the resolved return value could offer.

**Live-reproduced T1 miss**: `_migrate_runtime_to_unmassk()` exists TWICE — `lib/boot_migrations.py` (called unconditionally, with zero try/except wrapper, from `run_preboot_migrations()` on EVERY SessionStart boot — the highest-frequency, zero-click surface in the whole plugin) and `bin/git-memory-upgrade.py` (called from `apply_upgrade()`). Neither copy calls `verify_path_within_project()` before its `os.makedirs(unmassk_dir, exist_ok=True)` / `os.makedirs(agent_dir, exist_ok=True)` + `os.rename()` calls — this is the exact BUG Y (parent-directory symlink escape) class the whole round exists to close. Reproduced live: symlink `.claude` → an external directory, place a legacy `git-memory-manifest.json` inside that external directory (simulating a v3.7 install), run `boot_migrations._migrate_runtime_to_unmassk(project_root)` directly → `.unmassk/manifest.json` is created INSIDE the external directory, confirmed with a direct filesystem check, not just static reading. The existing `TestBugYClaudeDirSymlinkBypassesAllGuards` E2E test for `session-start-boot.py` does NOT catch this because `_make_repo()` builds a fresh repo with no legacy pre-migration files present — the migration's `if os.path.isfile(old_path):` guard short-circuits before ever reaching the vulnerable `os.makedirs()` in that test's specific fixture, giving false confidence from a 100%-green suite.

Design nuance for the eventual fix: `run_preboot_migrations()` calls `_migrate_runtime_to_unmassk()` with NO surrounding try/except at all — naively adding a raising `verify_path_within_project()` call inside it would crash `main()` and violate the hook's own documented "Exit codes: 0: Always (never blocks session start)" contract. The fix must wrap the guard so a rejected/unsafe path skips the migration and lets boot continue, not just add the check.

Secondary, lower-severity findings from the same sweep: `create_backup()` (`git-memory-upgrade.py:190`) writes the actual backup file with plain `open()` instead of `open_no_follow_symlink()` — inconsistent with the codebase's otherwise-universal convention, though exploitability is low (requires guessing a second-precision timestamped filename in advance). `git-memory-uninstall.py`'s `.claude/hooks`/`.claude/skills` cleanup never imports or calls `verify_path_within_project` either — tested live: its existing "only rmtree if ALL entries are symlinks" guard limits real damage (deletes the directory entry + symlink pointers, not symlink targets) when `.claude` is redirected, so this is a real but narrower gap than the migration-function one.

Rule confirmed again: when a security sweep targets one specific bug shape, grep the ENTIRE repo for the vulnerable primitive (`os.makedirs` under a `.claude`-derived path, `os.rename` into one) yourself — do not scope the search to only the files the implementing agent says it touched. A second, byte-identical copy of a vulnerable function in a sibling module (post module-split) is exactly the kind of place a scoped read misses.

## Round 10 (2026-07-05): T1 migration-duplication fix verified closed, but 3 MORE live-reproduced siblings of the same "parent-.claude-symlink" bug class found

Re-audit of the round-9 T1 fix (`_migrate_runtime_to_unmassk()` twins) plus its "5 hermanos" (rmtree destructivo, glossary-cache, session-booted creation, doctor timestamp, `create_backup()`). All 6 verified CLOSED by direct code read + the dedicated `TestBugAC.../TestBugAD...` regression tests (63/63 green in `test_security_regression.py`, 797/806 green overall — the 9 failures are the pre-existing unrelated `bin.release_helpers` `ModuleNotFoundError` in `test_release.py`, confirmed untouched by this round's 7 files).

However, live-reproducing the exploit against every OTHER function in the same 7 changed files that touches a `.claude`-relative fixed path turned up 3 NEW, previously-undetected siblings of the identical bug shape — none had a code comment acknowledging the gap (unlike the accepted narrow exceptions elsewhere in this codebase, e.g. `create_backup()`'s deliberate no-try/except):

1. **`bin/git-memory-uninstall.py:152-155` `remove_manifest()`** — plain `safe_remove()` → `os.unlink(path)` on `.claude/.unmassk/manifest.json`, with ZERO `verify_path_within_project()` call, in the SAME FILE where `remove_old_install_files()`'s hooks/skills rmtree (~50 lines below) already got the guard added this exact round. Live-reproduced: symlink `.claude` → external dir containing a real `.unmassk/manifest.json` → `git memory uninstall` deletes that external file. Triggered by a normal, explicit user command (`git memory uninstall`), not just a zero-click boot path.

2. **`bin/git-memory-doctor.py:278-296` `check_manifest()`** — uses `open_no_follow_symlink()` (protects the final component) but has no `verify_path_within_project()` for the parent-`.claude`-symlink case, while `run_doctor()`'s OWN healthcheck-timestamp block ~180 lines below (in the SAME FILE, fixed THIS round) does. Live-reproduced: `git-memory-doctor.py --json` leaks the externally-resolved manifest's `"version"` field into the JSON report (`"message": "v0.0.1-VICTIM-LEAK-CHECK-MANIFEST"`). Confidentiality-only (no write), but the read-path/write-path asymmetry is the exact repeating pattern documented earlier in this file for BUG P/CLAUDE.md.

3. **`hooks/session-start-boot.py:196-202` `run_preboot_migrations()`'s "Clean session-booted flag" step** — plain `os.remove(booted_flag)` on `.claude/.unmassk/.session-booted`, zero guard, runs UNCONDITIONALLY on every SessionStart (same reach as the just-fixed T1). Live-reproduced: symlinked `.claude` → external dir with a file literally named `.session-booted` → deleted on next boot. Lower blast radius than the fixed T1 (deletes one fixed-name flag file, doesn't write attacker-reachable content or create directories) but same zero-click trigger frequency.

Rule reinforced yet again: a security sweep that fixes N call sites of a bug shape in a set of files must grep EVERY function in those SAME files for the identical primitive (`os.remove`/`os.unlink` on a `.claude`-relative fixed path; `open()`/`open_no_follow_symlink()` read on a `.claude`-relative fixed path with no `verify_path_within_project()` before it) — not just the sites named in the fixing commit's own message. Three consecutive rounds (7, 9, 10) have each found 2-3 more siblings this way. Scored 72/110 in the round-10 re-audit (Security 5/10 — 3 new live-reproduced instances of the round's own target bug class; Structure 4/10 — `bootstrap.py` still 953 LOC/untouched, `install.py` grew 591→600 LOC this round alone, both un-split; Testing 7/10 — the round's own 5 fixes are well tested, but these 3 new gaps have zero regression coverage; Error Handling 9/10; Maintainability 8/10 — dead `plan["skipped"]` loop in `git-memory-install.py:546` still never populated, confirmed by grep). NOT MERGEABLE against Bex's 109 floor.

## Round 11 (2026-07-05): 3 targeted fixes verified closed + bootstrap.py/install.py split audited clean, but split brought a NEW live sibling of the campaign's own target bug into scope

Re-audit of round 10's 3 named T2s (`remove_manifest`, `check_manifest` version leak, session-booted `os.remove`) — all 3 verified CLOSED via dedicated red→green tests (`TestBugAEUninstallRemoveManifestClaudeDirSymlink`, `TestBugAFDoctorCheckManifestVersionLeakClaudeDirSymlink`, `TestBugAGBootPrebootMigrationsBootedFlagDeletionClaudeDirSymlink`), full suite 800 passed / 9 pre-existing-unrelated (`bin.release_helpers` `ModuleNotFoundError` in `test_release.py`, confirmed untouched). The dead `plan["skipped"]` loop is now genuinely populated (self-install cleanup-skip case) and printed. `verify_path_within_project()`'s Windows branch correctly added (`sys.platform == "win32"` gate + `os.path.normcase()` on both sides, mirrors `validate-memory-path.py`'s existing pattern).

`bootstrap.py` (953→143 LOC) and `install.py` (609→252 LOC) splits are both clean: one-way dependency graphs (`bootstrap_tree`/`bootstrap_deps`/`bootstrap_commits`/`bootstrap_report` never import each other or the entrypoint; `install_apply` imports `install_inspect`, never the reverse — verified by grepping every `^from\|^import` line), all new files well under the 500 LOC hard limit (72–302 LOC), docstrings independently verified accurate against actual code (e.g. `bootstrap_report.py`'s "never touches the filesystem or git directly" claim confirmed true by reading the whole file). Re-export claims for `git-memory-upgrade.py`/`git-memory-repair.py` (`install_mod.OLD_BIN_FILES`, `mod._update_claude_md`, etc.) verified LIVE by loading `git-memory-install.py` via `importlib.util.spec_from_file_location` and confirming every named attribute resolves.

**NEW T2 found by the split itself**: `lib/bootstrap_deps.py:check_existing_memory()` (moved here from the monolithic `bootstrap.py`, which was NEVER in scope for any of the 10 prior symlink-sweep rounds) reads `.claude/.unmassk/manifest.json` via `open_no_follow_symlink()` (protects the final component) but has ZERO `verify_path_within_project()` call for the parent-`.claude`-symlink escape — the exact bug shape as `doctor.py`'s `check_manifest()` (BUG AF), fixed in THIS SAME ROUND, three files away. Live-reproduced: symlinked `.claude` → external dir containing a planted `manifest.json` with `{"version": "VICTIM-LEAK..."}`  → `check_existing_memory()` returns the external file's version string, which flows into `git memory bootstrap --json`'s `existing_memory.installed_version` field and the human-readable `"git-memory already installed (v...)"` line. `tests/test_bootstrap.py` has ZERO symlink/security tests (12 tests total, all purely functional) — confirmed by grep, no regression coverage exists for this gap.

Rule reinforced for an 11th time: a module split that moves code INTO the scope of an ongoing security-sweep campaign must itself be swept for the campaign's own target bug shape before being declared done — "the file didn't change its logic, only its location" is not a valid reason to skip the check, because the location change is exactly what brings previously-out-of-scope code under the same obligation.

**Structure judgment call**: `bin/git-memory-doctor.py` sits at 518 LOC (over the project's own repeatedly-enforced 500-LOC hard limit — the same limit `boot_render.py`/`boot_checks.py`/`session-start-boot.py` were each split down to satisfy, even when only marginally over). Ultron left it unsplit, documenting the decision only in the commit message ("out of scope of this session, ya estaba así antes") rather than getting it sanctioned by Bex. Judged NOT acceptable as a silent grandfather exception: the project's own precedent (3 prior rounds treating "violation moved one file over" as blocking) means an 18-line overage on a file that was already over the limit before this round's 8-line fix should be split or explicitly escalated to Bex for a documented waiver — not unilaterally closed by the implementing agent.

Scored 87/110 in the round-11 audit (Security 6/10 — one new live-reproduced sibling, narrower than round 10's three, but same target-bug-class miss; Error Handling 10/10 — no findings; Structure 8/10 — doctor.py hard-limit residual, self-granted exception not accepted at face value; Testing 7/10 — the round's own 3 fixes are excellently tested, but bootstrap_deps.py's entire symlink surface has zero coverage; Maintainability 9/10 — clean, honest docstrings, only pre-existing minor CLAUDE.md-check duplication between bootstrap_deps.py/install_inspect.py, not new this round). NOT MERGEABLE against Bex's 109 floor, but the closest this campaign has been to closing — only 1 concrete new fix + 1 judgment call remain.

## Round 12 (2026-07-05): 5 targeted fixes verified closed + doctor.py 518 LOC formally waived by Bex, but a 4th unguarded sibling of the round's own OLD_SKILL_DIRS pattern was live-reproduced in the SAME functions

Re-audit of round 11's 1 new T2 (`bootstrap_deps.py check_existing_memory()`) plus 3 more sites Argus found in parallel this round: `_cleanup_old_install()`'s/`remove_old_install_files()`'s `OLD_BIN_FILES+OLD_HOOK_FILES+OLD_LIB_FILES` unlink loop (BUG AH), the `__pycache__` rmtree loop (BUG AI), and `remove_generated_files()` (BUG AJ). All 5 fixes verified present and correctly wired: `lib/bootstrap_deps.py:299` (`verify_path_within_project(manifest, root)`), `lib/install_apply.py:84,134` + `bin/git-memory-uninstall.py:206,182`. Each has a dedicated regression test class (`TestBugAHCleanupOldInstallFixedNameFileParentSymlink`, `TestBugAIPycacheRmtreeParentSymlink`, `TestBugAJGeneratedFilesRemovalClaudeDirSymlink`, `TestBugAKBootstrapCheckExistingMemoryManifestParentSymlink` in `tests/test_security_regression.py`) — ran `test_security_regression.py` (71/71) and `test_bootstrap.py` (12/12) live, both green.

Bex explicitly waived `bin/git-memory-doctor.py`'s 518 LOC (over the project's 500-LOC hard limit) as an accepted, documented exception — do not re-flag this as a pending Structure finding in future audits of this file, UNLESS the file grows further or a future round touches it directly. Note: as of this round the waiver exists only in conversation/commit-message form, not as an in-repo code comment — recommend a one-line docstring note in `git-memory-doctor.py` itself (e.g. "518 LOC — Bex-approved exception to the 500-LOC hard limit, YYYY-MM-DD") so a future Cerberus without this memory doesn't re-open it as unresolved.

**NEW T1/T2 live-reproduced**: `lib/install_apply.py:91-98` (`_cleanup_old_install()`) and `bin/git-memory-uninstall.py:212-220` (`remove_old_install_files()`) both loop over `OLD_SKILL_DIRS` (`skills/git-memory`, `skills/git-memory-protocol`, etc.) with:
```python
if os.path.isdir(path) and not os.path.islink(path):
    shutil.rmtree(path)
```
This has NO `verify_path_within_project()` guard — the exact bug class (parent-directory symlink escape, i.e. `target/skills` itself is a symlink to an external directory, and the external directory happens to contain a REAL, non-symlinked subdirectory matching one of the fixed `OLD_SKILL_DIRS` names) that this SAME round fixed 15 lines above (`OLD_BIN_FILES`/`OLD_HOOK_FILES`/`OLD_LIB_FILES` loop, BUG AH) in the SAME two functions. `shutil.rmtree()` only refuses when its own argument is literally a symlink — it does not care whether an ancestor directory is a symlink, which is exactly the escape mechanism here (`os.path.islink(path)` checks the final component, not `target/skills`).

Live-reproduced (not just static read) against both files: symlinked `target/skills` → an external directory containing a real subdirectory named `git-memory` (or `git-memory-protocol`) with a victim file inside → calling `install_apply._cleanup_old_install()` / `uninstall.remove_old_install_files()` directly deletes the external subdirectory and its contents (`shutil.rmtree`), confirmed by checking `os.path.isfile(victim)` before/after. Zero regression test covers this branch — grepped `tests/` for `OLD_SKILL_DIRS` and found no test exercising the "isdir and not islink" rmtree branch under a symlinked `skills/` parent.

Rule reinforced for a 12th time: a security sweep that adds a guard to one loop in a function must check every OTHER loop/branch in that SAME function for the identical primitive (`shutil.rmtree`/`os.unlink` under a fixed, predictable subpath) before declaring the function's symlink-escape surface closed — `_cleanup_old_install()`/`remove_old_install_files()` have 4 separate removal loops each; 3 of 4 got the guard this round (BUG AH's bin/hook/lib loop, the pycache loop, the `.claude/hooks`+`.claude/skills` loop from an earlier round) but the `OLD_SKILL_DIRS` loop (arguably the most obvious one to check, since it's textually adjacent to BUG AH's now-fixed loop) was missed.

Scored 90/110 in the round-12 audit (Security 5/10 — one new destructive, live-reproduced sibling gap in the round's own target bug class, worse than round 11's read-only version-leak because it's an unrecoverable external directory delete; Error Handling 10/10; Structure 10/10 — doctor.py waiver now accepted, no longer blocking; Testing 8/10 — the round's own 5 fixes are excellently tested, but the new OLD_SKILL_DIRS gap has zero coverage; Maintainability 9/10 — clean, honest docstrings, only the pre-existing accepted `OLD_BIN_FILES`/etc. duplication). NOT MERGEABLE against Bex's 109 floor.

## Round 13 (2026-07-05): security campaign genuinely CLOSED (10/10, 2nd consecutive round); LOC-split of boot_memory.py verified clean; but the split's own test-compat shim silently broke a security regression test's monkeypatch technique

Commit `24b98f1`. Two changes this round: (1) the round-12 "elif hermano sin guard" fix — `lib/install_apply.py:104-113` (`elif os.path.islink(path):` inside the OLD_SKILL_DIRS loop) and `bin/git-memory-uninstall.py:226-235` (identical shape) both now call `verify_path_within_project(path, target)` before `os.unlink(path)`, mirroring the `if` branch immediately above (SEC-LOW-001). Verified correct in both files, symmetric. (2) `lib/boot_memory.py` (524 LOC, the one remaining Structure finding from the prior round) split into itself (394 LOC) + new `lib/boot_glossary_cache.py` (195 LOC) — both now under the 500-LOC hard limit, confirmed by `wc -l`.

**Full re-sweep of both changed security files found no new gap.** Checked every removal loop in `install_apply.py`/`git-memory-uninstall.py` for the OLD_SKILL_DIRS/OLD_BIN_FILES/pycache/generated-files/`.claude/hooks`+`.claude/skills` bug class this campaign has hunted for 12 rounds — all correctly guarded. One candidate that looks unguarded but is a genuine false positive (do not re-flag): `bin/git-memory-uninstall.py`'s `# Remove .claude-plugin/` block (`if os.path.isdir(plugin_dir): shutil.rmtree(plugin_dir)`, no `verify_path_within_project()` call) — safe because `.claude-plugin` is a DIRECT single-level child of `target` with no intermediate symlinkable path component; `shutil.rmtree()`'s own built-in `os.path.islink(path)` check on its exact argument already refuses if `.claude-plugin` itself is a symlink. The guard is only needed when an INTERMEDIATE component (`.claude`, `bin`, `skills`, etc.) can be a symlink while the final component is a real subdirectory inside it — not applicable here. Security: 10/10, campaign holds for a second consecutive round.

**DAG genuinely verified acyclic (not just re-stated) by live import test both directions**: `python3 -c "import boot_memory"` and `python3 -c "import boot_glossary_cache"` both succeed standalone, confirming `boot_memory.py`'s bottom-of-file `from boot_glossary_cache import (...)` (test-compat re-export, `# noqa: E402`) and `boot_glossary_cache.py`'s function-body-deferred `from boot_memory import extract_glossary` (inside `extract_glossary_cached()` only) never enter a load-time cycle regardless of which module a caller imports first. `session-start-boot.py` imports `boot_memory` (line 47) before `boot_glossary_cache` (line 55) at its own module level, and only calls `extract_glossary_cached()` later at runtime (line 281) — so by the time the deferred import fires, both modules are already fully loaded in the normal execution path too. Structure: 10/10, the split closes cleanly with no "violation moved one file over" repeat.

**NEW T2, live-reproduced: the split silently broke `TestBugAOEnsureRuntimeDirFallbackBranchSymlinkedParent::test_write_glossary_cache_does_not_write_outside_repo_via_fallback_branch`'s monkeypatch technique, leaving the fallback branch it exists to protect with ZERO live coverage — yet the test still shows GREEN.** The documented technique (see `unmassk-toolkit-python-test-conventions.md` lines 83-103, itself now stale) is: load the target module via `spec_from_file_location` under a throwaway name (`mod`), then `mod.ensure_runtime_dir = None` to force the module's own `else:` fallback branch. This worked before the split because `_write_glossary_cache()` was DEFINED in `boot_memory.py` — `mod` WAS that module, so `mod.ensure_runtime_dir = None` patched exactly the global the function's body reads. After the split, `_write_glossary_cache()` moved to `lib/boot_glossary_cache.py`; `boot_memory.py`'s `mod._write_glossary_cache` is now merely a re-exported reference to the SAME function object, whose `__globals__` is fixed at definition time to `boot_glossary_cache.__dict__` — a completely separate namespace from `mod.__dict__`. Live-verified: `mod._write_glossary_cache.__globals__ is boot_glossary_cache.__dict__` → `True`; after `mod.ensure_runtime_dir = None`, `boot_glossary_cache.ensure_runtime_dir` (the name the function's body actually resolves) is untouched, still the real function. The test therefore now silently exercises the NORMAL branch (`ensure_runtime_dir` available, calling the real `ensure_runtime_dir()` which has its own internal `verify_path_within_project()`) instead of the hand-rolled `else:` fallback branch (`boot_glossary_cache.py:156-168`) it names and documents. It stays green only because the OTHER branch also blocks the symlink escape — not because the branch under test ran at all. If a future edit silently dropped the fallback's own `verify_path_within_project(cache_dir, root)` call, this test would not catch it. The sibling test in the same class, `test_write_boot_log_does_not_write_outside_repo_via_fallback_branch`, is unaffected — `write_boot_log()` was never moved, so `mod.ensure_runtime_dir = None` still patches the correct namespace for that one.

Rule for a 13th consecutive round: whenever a module split moves a function that a test forces into a specific branch via `mod.<module-level-name> = X` monkeypatching, re-verify that `mod` (the throwaway-loaded module the test patches) is still the SAME module where the moved function is actually DEFINED — not just re-exported. A re-export preserves the function's *identity* (same object, same callable) but not its *namespace* (`__globals__`), and a test that patches the wrong one stays green for a false reason. Grep every `mod.<name> = ` / `<module>.<name> = ` monkeypatch line touching any function moved by the split, not just the ones the split's own commit message mentions.

Also flagged (Alexandria, non-blocking, doc drift): `.claude/agent-memory/unmassk-toolkit-dante/unmassk-toolkit-python-test-conventions.md:86-87` still describes this monkeypatch technique as targeting "`lib/boot_memory.py:_write_glossary_cache()`" — stale since the split, and arguably why the break went unnoticed (the doc reinforced the wrong assumption). Needs a one-line update to `lib/boot_glossary_cache.py:_write_glossary_cache()`.

Full suite: 813 passed, 9 failed — all 9 pre-existing/unrelated (`bin.release_helpers` `ModuleNotFoundError` in `tests/test_release.py`, confirmed untouched by this round's 5 files, same baseline every round since round 7).

Scored 105/110 in the round-13 audit (Security 30/30 — genuinely closed, 2nd consecutive round; Error Handling 30/30 — no findings; Structure 20/20 — split clean, both files under the 500-LOC hard limit, DAG verified acyclic; Testing 16/20 — one live-reproduced false-confidence test on a security-critical fallback branch; Maintainability 9/10 — shim design well-justified and documented, minor point off for the resulting cross-module coupling + the stale test-conventions doc). NOT MERGEABLE against Bex's 109 floor, but the closest this campaign has been — only 1 fix (re-target the monkeypatch to the real module + update the stale doc line) remains.

## Round 14 (2026-07-05, CAMPAIGN CLOSED): monkeypatch re-target verified by live mutation test, doc drift fixed, full suite green — 109/110, MERGEABLE

Dante's fix for round 13's sole remaining T2 verified independently, not by re-reading the diff: `_call_write_glossary_cache_fallback()` (`tests/test_security_regression.py:3880-3915`) now imports `boot_glossary_cache` directly and patches `boot_glossary_cache.ensure_runtime_dir = None` BEFORE loading `boot_memory.py` via `spec_from_file_location` (whose `from boot_glossary_cache import (...)` re-export then reuses the same, already-patched `sys.modules` entry) — correctly targets the namespace `_write_glossary_cache.__globals__` actually resolves (`boot_glossary_cache.__dict__`), not the throwaway `boot_memory` module object the old version patched.

Confirmed live via mutation, not static read: commented out the `verify_path_within_project(cache_dir, root)` call inside `lib/boot_glossary_cache.py:_write_glossary_cache()`'s fallback `else` branch, ran `TestBugAOEnsureRuntimeDirFallbackBranchSymlinkedParent` — `test_write_glossary_cache_does_not_write_outside_repo_via_fallback_branch` FAILED exactly as expected (`glossary-cache.json` leaked into the external symlink target, assertion message correctly named BUG AO), sibling `test_write_boot_log_...` still passed (unaffected, different function). Restored the guard, re-ran — both green again, `git diff` on the file empty (no residual mutation left in the tree). This proves the test now genuinely exercises the fallback branch's guard, closing the round-13 false-confidence gap for real.

Doc drift also fixed: `.claude/agent-memory/unmassk-toolkit-dante/unmassk-toolkit-python-test-conventions.md` now correctly references `lib/boot_glossary_cache.py:_write_glossary_cache()` (was previously `lib/boot_memory.py:_write_glossary_cache()`).

Full suite re-run: 813 passed, 9 failed — identical baseline to every round since round 7 (`bin.release_helpers` `ModuleNotFoundError` in `tests/test_release.py`, confirmed pre-existing/unrelated, untouched by this round's 1-file test change). `test_security_regression.py` alone: 79/79 green. LOC re-verified unchanged from round 13 (`boot_memory.py` 394, `boot_glossary_cache.py` 195, `boot_render.py` 458, `boot_checks.py` 74 shim, `boot_health.py` 303, `boot_git_checks.py` 269, `doctor.py` 518 — Bex-waived).

No other finding from rounds 1-13 reopened; nothing new found in this narrowly-scoped 1-file change. Scored 109/110 (Security 30/30, Error Handling 30/30, Structure 20/20, Testing 20/20 — the round-13 gap is closed and mutation-verified, Maintainability 9/10 — same minor point held over from round 13, the cross-module coupling from the shim design is an accepted tradeoff of the split, not a fresh deduction). MEETS Bex's 109 floor. VERDICT: LGTM — this closes the 14-round security/structure audit of the unmassk-toolkit boot/install/uninstall surface. Do not re-open rounds 1-13's resolved items without a new code change touching those specific files; if a future change touches any of the split boot_*/install_*/bootstrap_* modules, re-verify LOC limits and re-grep for the "fixed one call site, missed the sibling" pattern that recurred in rounds 7/9/10/11/12/13 before considering it automatically clean.

## Byte-identical config lists duplicated across install.py and uninstall.py

`OLD_BIN_FILES`, `OLD_HOOK_FILES`, `OLD_LIB_FILES`, `OLD_SKILL_DIRS` are declared identically (differ only in a trailing comment) in both `bin/git-memory-install.py` and `bin/git-memory-uninstall.py`. Pre-existing (not introduced by the 2026-07-05 security sweep), first flagged in the round-7 full-file audit. Non-blocking (T3) — these two scripts are deliberately self-contained (no shared `lib/` module for install-specific constants), so some duplication is an accepted tradeoff of the "runs entirely from cache, no project-root copies" architecture. If a third script ever needs the same lists, extract to a shared module rather than copying a third time.

## Boot freshness feature (issue #49, 2026-07-06): cross-machine memory merge invariant violation + language-consistency drift

Commit-review of the 4 wip commits (63573e1/98862f1/578ffc6/9990410) implementing multi-machine boot freshness (fetch hardening, MEMORIA stamp, pull directive, origin-side memory read, warn-only write guard). Correctly scoped diff was `bc888be..HEAD` (the feature's own base), NOT `ca1f6a2..HEAD` as originally requested — that wider range accidentally included ~15 unrelated prior commits (the already-closed 14-round security campaign + a separate Windows cross-platform fix), which would have produced false "regressions" if reviewed as if they were new. Always verify a requested diff base against `git log --oneline <base>..HEAD` before trusting it — a stale/wrong base silently pulls in already-reviewed work.

Overall verdict: LGTM, 0 blocking issues, all 12 contract tests pass live, full suite unaffected (875 passed / 9 pre-existing-unrelated `bin.release_helpers` failures, same baseline as every round since round 7). Sanitization symmetry confirmed: `extract_memory(ref=...)` reuses the exact same `-z`/NUL + `_sanitize_trailer_value` pipeline for `origin/<branch>` as for HEAD — only the ref argument changes, no parallel/divergent code path was written.

Findings (all non-blocking, Suggestion-tier):

1. **Cross-machine merge re-introduces a same-scope-collision invariant that a single-source `extract_memory()` call always prevents internally.** `extract_memory()` deduplicates Decisions/Memos by scope WITHIN one call (`decision_scopes`/`memo_scopes` sets). `_merge_diverged_memory()` (`lib/boot_memory.py:420`) concatenates local's list + labeled-remote's list with no cross-list scope dedup. Live-reproduced: two independently-deduped single-scope lists, concatenated, can carry the same scope twice. This is NOT a display bug — the plan explicitly wants "both sides shown, never silently merged" (decision 3d2f377), so showing both is correct. The narrower gap: `_render_crowned_capped_section`'s `_crown_replace` (used by `render_decisions_section`/`render_memos_section` in `lib/boot_render.py`) only replaces the FIRST scope match in the list when a glossary entry is crowned — so a crowned override would apply only to whichever side happens to come first (always local, since `_merge_diverged_memory` concatenates local-then-remote), leaving the other side's duplicate-scope entry un-crowned. Three conditions must coincide (divergence + same scope on both sides + a glossary crown for that scope) — narrow blast radius, zero test coverage (Test 7's divergence fixture only exercises Next/pending items, never Decision/Memo scope collisions).

2. **POSIX-only hardened-fetch env in a project with an explicit cross-platform mandate.** `lib/boot_git_checks.py:344-349` (`_FETCH_HARDENED_ENV`) hardcodes `GIT_ASKPASS`/`SSH_ASKPASS` to `/bin/false`, with no `sys.platform == "win32"` branch — inconsistent with this same codebase's own recently-established hybrid-guard convention (`open_no_follow_symlink`'s POSIX/Windows split, decisions 013b064/75fdb2f). Functionally still fail-open on Windows (a nonexistent askpass path makes git fail to authenticate rather than hang), but the two hardening tests (`TestFetchHardening`, `TestFetchGateSkipsWithoutToolkitMemory`) are POSIX-only (`skipif(WINDOWS)`, needed for fake-git PATH-shadowing) — so there is zero automated proof the fail-open behavior actually holds on Windows.

3. **Silent bare `except Exception` with no stderr breadcrumb, in the same feature that just added one elsewhere.** `fetch_memory_ref()`'s outer `except Exception: return {"status": "failed", ...}` (`lib/boot_git_checks.py:429`) swallows any unexpected exception with zero diagnostic trace — while `git_helpers.run_git()`'s new `UnicodeDecodeError` branch (added in this SAME diff) explicitly prints a stderr breadcrumb for exactly this reason. Repeats the project's own documented anti-pattern (see "Fallback path-existence flag..." and CRB-05 entries above in this file) of a genuinely-unexpected-exception path staying invisible forever.

4. **New language-mixing inconsistency introduced within a single task, in a document whose only job is to be parsed every boot.** `render_memoria_stamp()` (`lib/boot_git_checks.py:446-476`) is entirely Spanish ("remoto", "fetch hace Xs", "sin verificar"), while `_build_pull_directive_lines()` (`lib/boot_git_checks.py:172-188`, same Task 3, same commit) is entirely English ("PULL DIRECTIVE... FIRST action"). Verified live: zero non-ASCII/Spanish text existed anywhere in `boot_render.py`/`boot_git_checks.py`/`session-start-boot.py` before this feature — this is the first Spanish text ever introduced into the boot banner/log pipeline, and it's inconsistent even against the OTHER new line added in the same task. Not a functional bug (tests pass, Claude parses either language fine) — flag for normalization or an explicit documented exception.

5. **`render_branch_section()`'s return tuple grew again, 5 -> 9 positions**, unpacked positionally in `main()`. All 9 values ARE consumed this round (verified, unlike the round-5/6 "dead behind_n" finding earlier in this file) — but a tuple that keeps growing across features, unpacked by position, is a live footgun for a future silent argument-order swap. Recommend a small dataclass/NamedTuple before a 10th field gets added.

**Polish round (2026-07-07): all 5 findings above resolved. LGTM, 0 blocking, 0 new T1/T2.** Verified each fix live, not just by reading diffs:
- Finding 2 (POSIX-only askpass) closed: `_ASKPASS_FAILFAST` now branches on `sys.platform == "win32"` (`"cmd /c exit 1"` vs `"false"`), with a new real (non-mocked) Windows test (`TestWin32AskpassFailfastResolvesAndExitsNonzero`) — confirmed it actually runs (not skipped) on this Windows dev box and passes.
- Finding 3 (silent catch-all) closed: `fetch_memory_ref()` now has BOTH a narrowed `except (subprocess.SubprocessError, OSError, ValueError, TypeError)` (with a stderr breadcrumb) AND a distinctly-tagged `except Exception` catch-all ("UNEXPECTED (likely a bug...)") that still returns `{"status": "failed", ...}` — fail-open preserved. Confirmed live via `TestFetchHeadAgeSeconds`... no — via `test_unexpected_exception_is_caught_and_returns_failed` (poisons `git_helpers.run_git` with `RuntimeError`, asserts `fetch_memory_ref()` still returns the failed dict, not a traceback).
- Finding 4 (language mix) closed: `render_memoria_stamp()` rewritten to English ("MEMORY: remote (fetched Xs ago)" etc.) — zero Spanish left in the boot banner/log pipeline.
- Finding 5 (growing positional tuple) closed: `BranchSectionResult(NamedTuple)` introduced with 9 named fields — `render_branch_section()` still returns a plain tuple (unpacking call sites unaffected) but every field is now attribute-accessible/self-documenting.
- Finding 1 (crown-replace multi-match reachability) was NOT a bug to fix — Ultron correctly left `_crown_replace`'s multi-match behavior in place and instead corrected its docstring, which previously claimed the multi-match branch was dead. Verified live: `render_decisions_section()`/`render_memos_section()` (`lib/boot_render.py:348,377`) DO call `_crown_replace`, fed by `_merge_diverged_memory()`'s local+remote concatenation — the multi-match path is genuinely reachable during a diverged-memory boot with same-scope entries on both sides. Do not re-flag this as dead code or ask for it to be simplified to single-match.

Also this round: 3 broad `except Exception:` handlers narrowed (`_win32_kill_tree` -> `(OSError, subprocess.SubprocessError)`, `commits_since_last_consolidation` -> `(ValueError, TypeError)`, `git-memory-commit.py`'s realpath try -> `OSError`). All 3 verified safe by tracing every statement inside each try block against the narrowed exception set — no plausible runtime exception is left uncaught in any of them. Minor T3 (not blocking): `_win32_kill_tree`'s own try/except is the ONLY safety net for its `subprocess.run(["taskkill", ...])` call — unlike the sibling POSIX branch in `run_git()`, which wraps `os.killpg()` in ITS OWN local try/except at the call site in `run_git` itself. If `_win32_kill_tree`'s internal catch is ever incomplete, nothing in `run_git()` catches the overflow, which would violate `run_git()`'s own documented "never raises" contract. Not a live bug (traced every realistic failure mode of `subprocess.run` with these exact args — all are OSError/SubprocessError subclasses) — flag only if `_win32_kill_tree` is ever modified to do more than a single `subprocess.run` call.

New test techniques worth reusing: (a) `_run_boot_with_failing_log_write()` (`tests/test_boot_output.py`) replaces `os.chmod(claude_dir, 0o500)` (POSIX-only — does not block the owner's own writes on Windows) with a direct monkeypatch of `boot.open_no_follow_symlink` on the throwaway-loaded hook module — correctly targets `write_boot_log()`'s own `__globals__` since that function is defined directly in `session-start-boot.py`, not re-exported from elsewhere (mutation-tested live: breaking the guard makes the test fail as expected, restoring makes it pass). (b) `_render_banner_with_branch()` replaces `git checkout -b <payload>` (fails at setup on Windows for long/`<`/`>` branch names, NTFS-reserved) with a direct monkeypatch of `git_helpers.run_git` for just the `branch --show-current` call, letting every other git call hit the real repo — avoids the "can't create this branch name as a real ref on Windows" trap while still exercising the real sanitizer/banner code. (c) `real_symlink_capable` fixture moved from `test_crossplatform_symlink_guard.py` to `conftest.py` and applied via `@pytest.mark.usefixtures(...)` across ~35 classes in `test_security_regression.py` — makes the whole symlink-guard suite skip cleanly (not fail) on a Windows box without Developer Mode/`SeCreateSymbolicLinkPrivilege`.

Noted, non-blocking, unrelated to this diff: `tests/test_boot_freshness_hardening.py::TestFetchHeadAgeSeconds::test_existing_fetch_head_returns_nonnegative_float` failed once in a full 981-test/12-minute run but passed cleanly in an isolated targeted run of the same file — looks like environment-timing flakiness (not touched by this round's diff, not reproducible in isolation). If it recurs, look at clock-resolution/mtime-vs-time.time() skew under load, not this round's code.

Full suite after this polish round: 897 passed, 74 skipped, 10 failed (9 are the pre-existing `bin.release_helpers` `ModuleNotFoundError` baseline unchanged since round 7; the 10th is the flaky `TestFetchHeadAgeSeconds` test above, confirmed non-reproducible in isolation). Targeted run of all 5 changed test files alone: 193 passed, 72 skipped, 0 failed. VERDICT: LGTM.

## A2 token-fence nonce placed adjacent to the marker instead of bound to it — defeats the "infalsifiable frame" goal even though the RED test passes

Confirmed 2026-07-10, issue #59 (`docs/plan/fix-fence-a2-close-57.md`, decisions `feed852`/`79fdf9a`, commit `d987f94`). The decision's own stated goal: "un delimitador que el commit no puede adivinar ni reproducir no puede falsificar ni romper la salida" — i.e. the nonce must make the ACTUAL boundary the consumer trusts unpredictable, not just make *some* byte in the overall output differ between invocations.

Two sibling fixes landed in the same commit for the two production fence sites, with different quality:

- `hooks/precompact-snapshot.py::format_snapshot()` (correct): `fence_nonce = secrets.token_hex(8)` is appended as a suffix on the SAME LINE as both the header (`=== GIT MEMORY SNAPSHOT (pre-compact) === (nonce:{fence_nonce})`) and the footer (`=== END SNAPSHOT === (nonce:{fence_nonce})`) — the SAME nonce on BOTH sides, forming a genuine matching pair an attacker cannot pre-compute. `_neutralize_snapshot_delimiters()` still works unchanged because it matches the un-nonced literal as a *substring* of the nonced line.
- `hooks/user-prompt-memory-check.py::main()` (deviation): `fence_nonce` is embedded ONLY in the framing LABEL line that precedes `<memory-data>` (`"...NO INSTRUCCIONES · fence-nonce:{fence_nonce}]\n<memory-data>\n{recall_block}\n</memory-data>"`). The actual `<memory-data>`/`</memory-data>` tag literals themselves stay byte-static and hardcoded — `</memory-data>` in particular carries no nonce at all. Ultron's own commit message flagged this as "desviacion nonce por revisar" (self-aware, not silently smuggled).

Why this matters: the entire reason A2 (token-fence) was chosen over A1 (pure denylist) per `feed852` is that the denylist ("un pozo sin fondo") had already needed ~5 rounds of new-evasion patches (2b/2c/2d/2e). A2's value proposition is closing the class *independent* of whether the denylist (`sanitize_trailer_value()`'s `<\s*/?\s*memory-data\s*>` strip regex) has some future gap. Since the nonce in `user-prompt-memory-check.py` is not bound to `</memory-data>` itself, a future denylist bypass that lets a literal, static `</memory-data>` reach `recall_block` would STILL successfully spoof the boundary — the nonce sitting on a preceding, unrelated line provides zero protection for that specific attack. The fix reduces to purely cosmetic for this hook, defeating the stated purpose of choosing A2 at all.

The RED test written for this (`TestUserPromptHookFenceNonceInfalsifiability::test_fence_wrapper_is_not_byte_identical_across_invocations`) only asserts `out1 != out2` (any difference anywhere in stdout) — a correct instance of the "assert the invariant not the byte/format" round-2e lesson in general, but here the invariant chosen is too weak to prove the actual claimed security property (that the boundary the LLM trusts specifically is unpredictable). It passes green under the deviation, giving false confidence.

The stated reason for the deviation ("nonce-ing the tags themselves would only need to also update the shared sanitizer, out of scope" + would break `test_hardening_recall.py::TestFramingAntiInjection`'s exact-literal assertions) is a **false premise**: `precompact-snapshot.py`'s own same-commit sibling fix proves a same-line-suffix nonce (`<memory-data> (fence-nonce:{nonce})` / `</memory-data> (fence-nonce:{nonce})`) would have preserved `"<memory-data>" in stdout` / `"</memory-data>" in stdout` as exact substrings (old tests keep passing unchanged) AND kept `sanitize_trailer_value()`'s existing fence regex fully effective (it operates on `recall_block` content, not on the hook's own trusted frame lines) AND delivered a genuine matching-pair nonce. The correct pattern was already sitting in the same commit, one file away.

Rule for future A2/nonce-style "unforgeable frame" fixes: when a decision requires a nonce to make a delimiter unpredictable, verify the nonce is bound to (same line as, or otherwise structurally coupled to) BOTH the open AND close markers the consumer actually trusts — not merely present somewhere else in the same output block. If two sibling call sites implement the "same" fix in the same round, diff them against each other, not just each independently against its own RED test.

## Follow-up security fix extends kwarg to new call sites but skips the central docstring + skips per-site rationale comments

Confirmed 2026-07-09, issue #53 SEC-HIGH-001 round (`5c044fa`): the base fix (commit `367aedf`) added an opt-in `reject_hardlinks: bool = False` param to `lib/git_helpers.py::open_no_follow_symlink()` / `lib/_symlink_safe_open.py::open_no_follow_symlink_fallback()`, and each of its 4 initial call sites (`session-start-boot.py`, `boot_glossary_cache.py` x2, `user-prompt-memory-check.py`) got a dedicated inline comment ("reject_hardlinks=True (issue #53, decision 51a3c44): ... toolkit-generated-only ..."). The docstring's own "which call sites should pass True" example list was written to match those 4.

The follow-up round (`5c044fa`, Argus-found SEC-HIGH-001 extension) added the SAME kwarg to 3 MORE call sites (`lib/install_apply.py:276`, `bin/git-memory-upgrade.py:362`, `bin/git-memory-doctor.py:517`, all `manifest.json` writes) but touched ONLY those 3 lines — confirmed via `git diff <before>..<after> -- lib/git_helpers.py lib/_symlink_safe_open.py` returning empty. Two consequences: (1) the central function's docstring example list is now stale (still lists only the original 3 file names, omits `manifest.json`); (2) none of the 3 new call sites got an inline rationale comment — the bare kwarg was dropped into an existing *symlink*-guard comment that never mentions hard links. The actual reasoning for these 3 sites exists only in the Dante test file's module docstring (`tests/test_manifest_hardlink_reject.py`) and in Ultron's own agent-memory (`lessons.md`) — neither is visible to someone reading the production source file.

Pattern to check on any "extend an existing opt-in security guard to N more call sites" round: (a) grep the guard function's own docstring for a "which callers should use this" list and confirm it was updated to include the new call sites' generated-file names; (b) confirm each NEW call site got its own inline comment in the same style as the ORIGINAL call sites, not just a bare kwarg addition — the commit diff touching only the kwarg line (no comment line) is the tell.

## Relabeling a rate-limit-derived stamp to a stronger positive claim without revisiting the adjacent "this timestamp is not trustworthy" security comment

Confirmed 2026-07-10, issue #60 (`docs/plan/fix-boot-memory-stamp.md`, decision `ceef426`, wips `3be6552`/`d630e14`). `lib/boot_git_checks.py`'s `rate_limited` branch was relabeled from `MEMORY: LOCAL — fetch skipped (rate-limit, {age} ago)` to `MEMORY: remote (synced {age} ago)` — correct per the stated UX goal ("fresh = good, LOCAL only for real failures"), and the gate math (`_fetch_gate_and_rate_limit`, only reachable with a measured `0 <= age < 300s`) genuinely makes every reachable stamp truthful *relative to FETCH_HEAD's mtime*.

The catch: `lib/boot_git_checks.py:449-459` carries a pre-existing, untouched Argus SEC-LOW-001 comment that explicitly bounds the risk of `.git/FETCH_HEAD`'s mtime being locally writable/spoofable ("touch, a crafted checkout, clock changes") by asserting "every actual freshness claim in the rendered stamp still comes from the fetch's own real exit code, never from this timestamp." That assertion was TRUE for the old wording ("fetch skipped" makes no freshness claim) and is FALSE for the new one ("remote (synced ...)" is precisely a freshness claim sourced from that same mtime, since the gate short-circuits BEFORE any real fetch attempt in this branch). The file now contradicts itself: `:791-792` (new) says "FETCH_HEAD < 300s ... means memory is confirmed fresh"; `:449-459` (untouched) says that exact timestamp must never be used to assert freshness.

Practical exposure: anything that touches `.git/FETCH_HEAD`'s mtime without a real fetch happening (restored backup, `cp -r` preserving mtimes, a container image pre-populated at build time, or a dev doing `touch` to dodge the rate-limit wait) now makes the boot confidently claim `MEMORY: remote (synced Ns ago)` — the SAME wording as a genuinely verified fetch — with zero real verification. Previously this degraded to a neutral "skipped" text; now it degrades to a false-positive-shaped confident claim, which re-risks the exact trade-off Argus already accepted at a lower severity, without re-confirming it at the new one.

Rule for future "relabel a status text to sound more positive/confident" rounds: grep the surrounding file for any comment that already documents WHY the underlying signal (timestamp, cache flag, feature-detection boolean, etc.) can't be trusted for the claim you're about to make more confident — if the new wording crosses the line that comment drew, the comment needs to be revisited (or the security posture re-confirmed with Argus), not just the wording changed. A relabel that only touches the display string can silently upgrade the severity of an already-accepted residual risk.

## A "read-side" regression test is silently redundant with (and masked by) an upstream write-side guard added in the SAME fix — both hit the identical choke point

Confirmed 2026-07-10, issue #60 v4 round (`docs/plan/fix-boot-memory-stamp.md` AMENDMENT v4, decision `174d82b`, diff `df1bb4f..154a80d`). Ultron's fix adds ONE guard: `_check_remote_is_live()` (`lib/boot_git_checks.py:725`) treats a resolved `git remote get-url` value that is byte-identical to the remote's own alias (`url == remote_name`, git's empty-URL fallback) exactly like an unresolved remote — `{"status": "no_remote", ...}`, propagated by `_resolve_fetch_target()` as an early return BEFORE `_check_own_stamp_rate_limit()`/`_read_own_stamp_age()` (the v3 remote_url identity comparison) ever run.

Dante wrote two tests for this: a write-side pinning test (repo X, own trap, asserts no stamp file is ever created — correctly isolated, exercises exactly the new branch) and a second test explicitly documented as "the read-side half of decision 174d82b... the read side must reject it regardless of provenance" (seeds a poisoned stamp via read-mutate-rewrite on a REAL stamp, §34-correct, plants it on an unrelated repo Z). The catch: Z's OWN fixture is ALSO degenerated the same way (`_degenerate_remote_url_to_alias(repo_z)`, matching the real-world "this vector affects a whole CLASS of repos" framing) — so Z's boot hits the SAME new write-side early-return on ITS OWN live resolution, before `_read_own_stamp_age()` (the actual "read side" identity comparison the test claims to prove) is ever reached at all.

Empirically confirmed by patching `_read_own_stamp_age()` (`lib/boot_fetch_stamp.py`) to skip the `remote_url` comparison entirely (`data.get("remote_url") != remote_url` removed from the OR-chain) and re-running only the two new tests: both still pass (`2 passed`). The "read-side" test cannot distinguish "the read path correctly rejected the poisoned claim" from "the read path was never reached" — it is proven, by construction, to pass regardless of whether the v3 remote_url comparison exists at all. Production behavior is still SAFE (the single write-side guard closes both directions, as the code's own docstring correctly claims) — this is a test/documentation-truthfulness finding, not a live security gap: the module comment and the test's own docstring assert independent read-side coverage that does not exist as written.

Rule for future "guard added upstream of an existing check" rounds: when a NEW guard sits before an EXISTING guard in the same call chain (here: `_check_remote_is_live` before `_check_own_stamp_rate_limit`), any test whose fixture triggers the NEW guard's condition on BOTH sides of a two-repo scenario cannot prove the EXISTING (downstream) guard still does its job — it never runs. To genuinely test the downstream guard in isolation, the fixture must avoid tripping the upstream guard (e.g., a target repo with a real, resolvable, non-degenerate URL) so execution actually reaches the code under test. Verify by temporarily neutering the specific comparison the test claims to cover and re-running just that test — if it still passes, the test is redundant with something upstream, not proving what its docstring says.
