---
name: patterns
description: Recurring architecture/stack patterns in claude-toolkit that change how a vector applies here
metadata:
  type: project
---

**No external attacker in this repo's model.** CLAUDE.md states this explicitly and it is load-bearing for every audit here: this toolkit is the owner's single-user tool, not a public product. OWASP-style hostile-input findings (injection from an untrusted network caller, auth bypass, CORS, etc.) are dead weight unless the finding is really about the system corrupting/losing its own state. The real threat model is **the system harming itself**: memory loss/corruption, writing outside the project root, a failure that passes silently, a badly-built command that self-executes on internal data.

**`git_helpers.py` is a mature, already-hardened shared library.** Functions like `run_git` (always `shell=False`, `Popen(["git"] + args, ...)`, process-group kill on timeout), `open_no_follow_symlink` (O_NOFOLLOW / Windows TOCTOU identity check / optional hard-link rejection / atomic replace variant), `verify_path_within_project` + `ensure_runtime_dir` (resolves every intermediate symlinked component, not just the final one) already carry inline `SEC-*`/`ROB-*` comments documenting prior Argus/Moriarty rounds that fixed them. When a new hook reuses these helpers, the read/write-safety half of the audit is usually already closed — verify the *call site* passes the right mode/flags, don't re-derive the primitive's own safety from scratch every time.

**Git argument construction convention**: every `run_git([...])` call that takes caller-influenced path-like strings in this codebase puts a literal `"--"` before them (e.g. `git_helpers.py:1178`, `is_tracked_in_head`). This is the project's established pattern for "this string can never be reinterpreted as a git option" — check for it explicitly when reviewing a new `run_git` call site; its absence would be a real finding.

**gitmem word search on a brand-new file returns nothing found and that's normal**, not a red flag — see [[false-positives]] if this file gains history later. First audit of `unmassk-toolkit/hooks/stop-dod-gate.py` and `lib/git_helpers.py:is_tracked_in_head` was 2026-08-20; no prior notes existed.
