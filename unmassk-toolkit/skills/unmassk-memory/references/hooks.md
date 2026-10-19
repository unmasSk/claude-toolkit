# The hooks that are live

Generated from `hooks/hooks.json`, never by hand: a hook documented here but not registered is this skill telling the user something untrue.

<!-- BEGIN unmassk-active-hooks (generated from hooks/hooks.json — do not edit by hand) -->
**10 hook invocations declared** in `hooks/hooks.json`. Event, matcher and timeout are read from that file; file presence is checked on disk; transient measurement probes are excluded. This table is generated — regenerate with `bin/hooks_doc_sync.py --write`, never by editing it here.

| Event | Matcher | Hook file | Timeout |
|---|---|---|---|
| `SessionStart` | — | `boot_launcher.py` | 30s |
| `SessionStart` | — | `session-start-crew.py` | 10s |
| `PreToolUse` | `Bash` | `customs.py` | 15s |
| `PreToolUse` | `Write\|Edit` | `validate-memory-path.py` | 5s |
| `PreToolUse` | `Bash` | `pre-merge-gate.py` | 10s |
| `PreToolUse` | `Agent\|Task` | `reviewer-prompt-gate.py` | 5s |
| `UserPromptSubmit` | — | `user-prompt-memory-check.py` | 10s |
| `PostToolUse` | `Skill` | `skill-checklist-inject.py` | 5s |
| `Notification` | `permission_prompt\|idle_prompt` | `owner-cue.py` | 5s |
| `Stop` | — | `checklist-gate.py` | 5s |
<!-- END unmassk-active-hooks -->
