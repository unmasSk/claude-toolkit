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

## Texts that encode the pipeline (verified @7d23875e, 2026-10-18)

- **`unmassk-toolkit/checklists/{flow,audit,close-session,council}.json` are not in the skill dirs but
  encode them.** `hooks/skill-checklist-inject.py` forces those boxes verbatim when the skill loads and
  `hooks/checklist-gate.py` blocks Stop on them. A skill sweep that skips `checklists/` leaves them stale
  (flow.json still said Trivial/Standard/Big and "context commit" after the 10-18 sweep).
- **`lib/managed_blocks.py` has 4 blocks** (EXECUTED); `hooks/session-start-crew.py` docstring says 5.
  The block text in CLAUDE.md lives there, not in the skills. The CLAUDE.md injected at session start can
  be older than the file on disk: read the disk.
- **`hooks/pre-merge-gate.py` blocks every `git merge`/`git pull` and demands Cerberus + Alexandria
  (`# merge-reviewed` token)**; `hooks/customs.py` lets merge pass. Two hooks, opposite stance on merge.
- **`lib/skill_router.py`** holds the skill-trigger and `[orden]` reminder tables for the per-message hook.

## Checklist hooks (verified @ed307f0d, 2026-10-18)

- Boxes are NOT written to the app task board by any hook. Inject writes a registry file
  `<cwd>/.claude/.unmassk/session-checklists/<session_id>.json` (`lib/checklist_state.py`) and tells the model
  (additionalContext) to create the tasks; the Stop gate reads the model-made tasks from
  `~/.claude/tasks/<id>/N.json` and compares by normalized text (`normalize_box_text`). A box text must match
  exactly after normalization, so a box cannot carry a variable word (e.g. the chosen procedure).
- Manifest `checklists/*.json` only needs `boxes: [str]`; `flow.json` box [0] is read by a casefold test.
