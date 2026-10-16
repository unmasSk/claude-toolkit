---
name: toolkit-code-tricks
description: Code tricks for exploring claude-toolkit — where the real entry points are, which names or greps mislead. Each entry carries its commit and date; re-check anything touching its area after that commit.
metadata:
  type: project
---

All entries verified against the live tree at commit `39d29c8c`, 2026-10-16, unless the entry says otherwise.
Task histories do NOT live here (they are project memory, in `gitmem`).

## Skills and plugins

- **Skill frontmatter is flat** (`name:`, `version:`, `description:`), no `metadata:` wrapper
  (grep count 0 on council, core, memory-doctor; first lines of memory and flow read).
  **Trap:** `description` is either one line (memory) or a folded block `description: >` with the text on
  the next indented lines (flow). A one-line `grep '^description:'` on a folded one returns just `>` — do
  not conclude "empty description". Read `sed -n 1,12p` instead.
- **Two plugin shapes, do not assume one.** Multi-skill: one dir per skill (`unmassk-toolkit/skills/`
  has 12, `unmassk-ops/skills/` has 7). Single aggregate skill: ONE skill dir with a `references/*.md`
  fan-out (`unmassk-seo/skills/unmassk-seo/`, `unmassk-marketing/skills/unmassk-marketing/`).
- **`.ref-repos/` rotates.** On 2026-10-16: `communitytools`, `harness-review`, `lote-a`..`lote-d`,
  `spec-kit`, `.claude`. Repos named in older notes (marketingskills, cc-devops-skills, the design repos)
  are gone. `ls .ref-repos/` first; never trust a remembered name.
- **Agent fichas live in the repo at `unmassk-toolkit/agents/<name>.md`.** The installed plugin cache
  copy is older until `/plugin update` (told by the orchestrator 2026-10-16, not checked). Read the repo
  path.
- **`chatroom/` is inside the repo but is its own project** (own `CLAUDE.md`, `README.md`,
  `CHANGELOG.md`). Do not map it as part of the toolkit.

## Boot, hooks, memory code

- **The full boot report is a file, not injected:** `bin/memory/boot.py:main` writes it to
  `.claude/.unmassk/boot-latest.txt` (`_REPORT_NAME`). The SessionStart hook only prints the order to
  read it. The hook output alone is not the report.
- **The "PLUGIN: N ficheros desincronizados (repo vs cache)" line** comes from the directory-fingerprint
  diff in `lib/cache_sync_check.py` (`check_repo_cache_sync`, `count_repo_cache_drift`), called from
  `hooks/session-start-crew.py` and `bin/git-memory-doctor.py`. Which of them prints the exact text was
  not grepped.
- **`recall_relevant` (v1 recall) has no production consumer.** Only `tests/test_user_prompt_recall.py`,
  `tests/test_hardening_recall.py` and a docstring in `lib/memory/similar.py` mention it. Do not trace a
  runtime path through it.
- **`hooks/validate-memory-path.py` (PreToolUse, Write|Edit) guards only agent-memory paths.** It acts on
  paths containing `.claude/agent-memory/` (must resolve under the CURRENT git root's
  `.claude/agent-memory/`, else block) and approves every other path. It does not stop an agent with
  Write/Edit from touching project files. From a worktree it also blocks writing another checkout's
  notebook (EXECUTED 2026-10-16: it blocked this very cleanup). Read from the repo copy; the installed
  copy was not compared.
