---
name: Anti-patterns found in ops scripts, hooks, and chatroom bridge plans
description: Recurring shell, Python, and TypeScript/Bun anti-patterns found in ops-containers, ops-scripting/ops-observability skills, unmassk-crew hooks (2026-03-14, 2026-03-16), chatroom bridge plan (2026-03-18), and chatroom @mention depth feature (2026-03-18)
type: project
---

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
