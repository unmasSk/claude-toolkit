---
name: ops-iac shell script patterns
description: Safe shell scripting patterns used across the ops-iac skill scripts
type: project
---

## Shell Script Safety Patterns (ops-iac)

All scripts use `set -euo pipefail` (not bare `set -e`).

### Array-based config args (avoids word-splitting)
```bash
YAMLLINT_ARGS=()
if [ -f "$SKILL_DIR/assets/.yamllint" ]; then
    YAMLLINT_ARGS=(-c "$SKILL_DIR/assets/.yamllint")
fi
"$YAMLLINT_CMD" "${YAMLLINT_ARGS[@]}" "$file"
```
Same pattern for ANSIBLE_LINT_ARGS.

### mapfile for find output (avoids word-splitting on filenames)
```bash
mapfile -t YAML_FILES < <(find "$DIR" -type f \( -name "*.yml" -o -name "*.yaml" \) ...)
for file in "${YAML_FILES[@]}"; do ...
```

### Trap with single quotes (prevents early expansion)
```bash
trap 'rm -rf "$TEMP_VENV"' EXIT INT TERM
```

### ANSI sanitization for grep output
```bash
clean_line=$(echo "$line" | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g')
echo "  $clean_line"
```

## Shell Path Traversal Validation (wrapper scripts)
```bash
# Validate that the target script is within SCRIPT_DIR before executing
if [[ "$(realpath "$PYTHON_SCRIPT")" != "$SCRIPT_DIR"/* ]]; then
    echo "ERROR: script must be within skill directory" >&2
    exit 1
fi
```
Apply in python wrapper scripts immediately after reading $1, before any execution.

## Array-based act/tool execution (replaces eval + string concat)
```bash
local cmd_args=("${tool_path}" --flag)
if [[ -n "${optional_flag}" ]]; then cmd_args+=(-W "${optional_flag#-W }"); fi
cmd_args+=("${extra_args[@]}")
output=$("${cmd_args[@]}" 2>&1)
```
Pattern for gha-validate-workflow.sh act --list and --dryrun commands.

## Python Path Traversal Pattern (ops-iac)
```python
import os
resolved = Path(args.directory).resolve()
cwd = Path(os.getcwd()).resolve()
if not str(resolved).startswith(str(cwd)):
    print(json.dumps({"error": "Path traversal detected: target must be within working directory"}))
    sys.exit(1)
```
Apply in `main()` after parsing args, before any file access.

## React StrictMode double-mount protection for WebSocket hooks

File: `chatroom/apps/frontend/src/hooks/useWebSocket.ts`

React dev mode (StrictMode) mounts, unmounts, and remounts every component immediately.
Without protection, the `useEffect` cleanup fires `disconnect()` while the WebSocket is
still opening, producing "WebSocket is closed before the connection is established".

Pattern: hold a pending-disconnect timer in a `useRef`. Delay `disconnect()` by 100ms in
the cleanup. Cancel the timer at the top of the next effect run if a remount arrives
within that window (StrictMode). On a real unmount no remount follows within 100ms so
the timer fires normally.

```typescript
const cleanupRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

useEffect(() => {
  if (cleanupRef.current !== undefined) {
    clearTimeout(cleanupRef.current);
    cleanupRef.current = undefined;
  }
  connect(roomId);
  return () => {
    cleanupRef.current = setTimeout(() => {
      cleanupRef.current = undefined;
      disconnect();
    }, 100);
  };
}, [roomId, connect, disconnect]);
```

Key constraints:
- `useRef` must be at component level, never inside the effect.
- The cleanup cannot return a function — React ignores return values from cleanups.
- Cancellation must happen at the top of the next effect run.
- 100ms is sufficient for StrictMode (synchronous in dev) without delaying real disconnects.

## Elysia WS query params pattern (chatroom)

To read `?name=foo` in a WS handler, add `query: t.Object({ name: t.Optional(t.String()) })` alongside `params:` in the `.ws()` config. Access via `(ws.data as WsData).query?.name`. Update the `WsData` type: `type WsData = { params: { roomId: string }; query: { name?: string } }`.

## WS per-connection state tracking pattern (chatroom)

Three module-level Maps for tracking WS connection state:
```typescript
const wsConnIds = new Map<any, string>();          // ws handle → connId
const connStates = new Map<string, ConnState>();   // connId → {name, roomId, connectedAt}
const roomConns = new Map<string, Set<string>>();  // roomId → Set<connId>
```
Populate in `open()`, clean up in `close()`. This allows per-connection author name without putting it in `ws.data`.

## AGENT_DIR glob resolution pattern (chatroom)

Use `globSync` from `node:fs` to find versioned toolkit directories:
```typescript
import { existsSync, globSync } from 'node:fs';
const matches = globSync(join(homedir(), '.claude/plugins/cache/.../*/agents'));
matches.sort().reverse(); // highest version first
return matches[0];
```

## BM25 Skill Search Pattern (unmassk-crew)

Reference implementation lives at `unmassk-design/skills/unmassk-design/scripts/core.py` lines 89-148.
Copy BM25 class verbatim — it is proven and stdlib-only (csv, re, math.log, collections.defaultdict).

Script: `unmassk-crew/scripts/skill-search.py`
- Scans `~/.claude/plugins/cache/`, `~/.claude/skills/`, `<git-root>/.claude/skills/` for `*.skillcat`
- `.skillcat` = CSV with columns: `name,plugin,triggers,domains,frameworks,tools`
- Search columns: `name + triggers + domains + frameworks + tools`
- SKILL.md is colocated with the `.skillcat` file (same directory)
- `SKILL_SEARCH_EXTRA_DIRS` env var (colon-separated) adds extra scan dirs for testing
- Low-confidence threshold: score < 1.5 → print WARNING
- Runs in ~45ms on stdlib only

IDF behavior: with only 3 docs, all scores are compressed (max ~4.7 for exact keyword match). This is expected — warning fires correctly. Rankings are still correct.

## Managed Block Injection Pattern (CLAUDE.md / markdown files)

For injecting auto-generated content between markers in an existing file:

```python
MARKER_START = "<!-- skill-map:start -->"
MARKER_END = "<!-- skill-map:end -->"

def inject_into_claude_md(path, block):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f: f.write(block + "\n")
        return "created"
    with open(path) as f: content = f.read()
    if MARKER_START in content and MARKER_END in content:
        pattern = re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END)
        new_content = re.sub(pattern, block, content, flags=re.DOTALL)
        # write back
        return "updated"
    else:
        sep = "\n" if content.endswith("\n") else "\n\n"
        # append sep + block
        return "appended"
```

Key: `re.DOTALL` required for the replace to span multiple lines.
Key: `os.makedirs(..., exist_ok=True)` on the create path — parent may not exist.
