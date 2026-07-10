# Changelog

## [Unreleased]

## [1.19.3] - 2026-07-11

### Fixed

- **Boot `MEMORY:` stamp no longer labels fresh memory as a failure** (issue #60): when the boot's background fetch was skipped because memory was already confirmed synced within the last 5 minutes, the banner read `MEMORY: LOCAL — fetch skipped (rate-limit, Ns ago)` — worded as a failure even though memory was genuinely fresh. That state now renders `MEMORY: remote (synced Ns ago)`, grouped with `remote (fetched Ns ago)` as a confirmed-fresh state; `LOCAL` is reserved for real failures (no fetch this boot, no remote, never synced).

### Changed

- **Boot fetch freshness signal moved off `.git/FETCH_HEAD`** (issue #60): the rate-limit gate and the `MEMORY:` stamp used to read `.git/FETCH_HEAD`'s mtime, which a *failed* fetch also refreshes (git truncates it to 0 bytes on failure) and which any unrelated `git fetch` (IDE, mirror) touches too — both could produce a false "synced" claim. The boot now writes its own success stamp (`lib/boot_fetch_stamp.py`, `.claude/.unmassk/boot-fetch-stamp.json`, gitignored, per-machine) immediately after ITS OWN fetch against the resolved memory upstream exits 0, keyed to the remote's real URL (not just its local alias) plus branch and a schema version — a stamp copied between unrelated repos sharing a common `origin`/`main` naming convention (template scaffolding, backups) is never trusted as evidence of a real sync.
- **Toolkit CI gained real Windows coverage for the boot fetch path**: a unified `Popen` interceptor (`tests/_git_intercept.py`) replaces the previous PATH-shim approach, which silently no-opped on Windows because `CreateProcess` only resolves `.exe` and ignores `PATHEXT`. The fetch-gate and freshness-stamp tests now exercise real subprocess behavior on all three CI platforms instead of being skipped on Windows.

## [1.19.2] - 2026-07-10

### Fixed

- **Boot memory fetch now reliably completes** (plugin/boot): `FETCH_TIMEOUT_SECONDS` (`lib/boot_git_checks.py`) raised from 3s to 10s. The old 3s bound let the SessionStart fetch time out under normal network latency, so `origin/<branch>` stayed stale, the boot never detected local was behind, and `resolve_boot_memory()` served a stale *local* briefing instead of reading the fresh one from origin (observed live: a boot showed a 19h-old `Next:` while local was actually 36 commits behind). 10s stays a bounded timeout (boot never hangs) with fail-open unchanged; the "LOCAL — unverified" freshness stamp still fires as the safety net if a fetch genuinely fails. Two hung-fetch tests that used an 8s stall calibrated to beat the old 3s bound were re-derived from the constant so they no longer break silently.

## [1.19.1] - 2026-07-10

### Fixed

- **Carriage-return transport forgery in the git-log→memory pipeline** (issue #59): `run_git()` (`lib/git_helpers.py`) and the independent inline `git log` subprocess in `bin/git-memory-log.py` both decoded with `text=True` universal-newline translation, collapsing any `\r` in a commit body to `\n` before the parser saw it — a raw carriage return in a trailer could forge or erase a memory line. Both now capture raw bytes and decode manually (no newline translation), preserving `\r` literally. Verified end-to-end through a real subprocess round-trip against `git cat-file`.
- **Unclosed `memory-data` marker after control-byte truncation** (issue #59, SEC-LOW-17): `scan_trailers_memory()` (`lib/parsing.py`) truncates a line at the first `\x1c`/`\x1d`/`\x1e`; when that byte fell inside a `</memory-data…>` marker it dropped the closing `>`, leaving a dangling marker the fence stripper could not match. A trailing-remnant sweep now neutralizes it.
- **Quadratic-time input bound on generic-tag stripping** (issue #59): `_strip_generic_tags()` (`lib/bootstrap_commits.py`) is capped to 4096 chars before the tag regex runs, bounding a crafted-long-subject O(n²) case.

### Changed

- **Best-effort framing nonce on the memory-injection markers** (issue #59): the `UserPromptSubmit` recall block and the pre-compact snapshot carry a per-invocation nonce alongside their delimiters. The injection-fence hardening in #59 is intentionally **partial** — the threat requires repo write access (a hostile commit), which is outside the single-user trust model this toolkit targets. The remaining hardening (nonce bound *inside* the delimiter, invisible-Unicode/Cf stripping, disguised-marker regex, and a length bound on the new unclosed-marker sweep) is documented and deferred as risk-accepted.

## [1.19.0] - 2026-07-09

### Security

- **Hard-link bypass of the symlink-safe write guard closed** (issue #53): the two symlink-safe open helpers, `open_no_follow_symlink()` (`lib/git_helpers.py`) and its Windows-path twin `open_no_follow_symlink_fallback()` (`lib/_symlink_safe_open.py`), gain an opt-in `reject_hardlinks=True` parameter. When set, both check `os.fstat(fd).st_nlink` on the already-open file descriptor (TOCTOU-safe — the check runs after the symlink guard has already resolved the real file, not before) and raise `OSError` (`errno.EMLINK`) if the file has more than one link, deferring truncation in write mode so a rejected file's shared inode is never destroyed before the reject fires. Applied to the 5 file categories the toolkit generates and writes to itself — `boot-log-latest.txt` (`hooks/session-start-boot.py`), `glossary-cache.json` read and write (`lib/boot_glossary_cache.py`), `.session-booted` (`hooks/user-prompt-memory-check.py`), `manifest.json` across install/doctor/upgrade (`lib/install_apply.py`, `bin/git-memory-doctor.py`, `bin/git-memory-upgrade.py`), and the upgrade backup (`bin/git-memory-upgrade.py`) — closing SEC-HIGH-001 plus a variant the first pass missed on the upgrade backup path. Deliberately NOT applied to user-owned files (`CLAUDE.md`, `settings.json`, `.gitignore`), where a legitimate hard link between worktrees is valid and should not be rejected. `git-memory-upgrade.py`'s backup caller now wraps `create_backup()` in try/except so a rejected hard link at the backup path fails the upgrade cleanly instead of crashing uncaught. New contract tests: `tests/test_hardlink_reject_guard.py`, `tests/test_manifest_hardlink_reject.py`. Originally deferred out of the v1.16.1 cross-platform fix pending its own dedicated review (decision `51a3c44`); closed here.

## [1.18.0] - 2026-07-09

### Added

- **Toolkit CI on GitHub Actions** (issue #51): `.github/workflows/toolkit-ci.yml` runs the full test suite on both `windows-latest` and `ubuntu-latest` (`fail-fast: false`, so a failure on one OS never hides the other) — there was previously no automated channel to verify Windows results at all. Getting the matrix green surfaced two more real bugs, fixed in the same push: `get_timeline()`/`get_last_context_time()` (`lib/boot_git_checks.py`) used the same fragile `%aI` + `datetime.fromisoformat()` date parsing described below and were unified onto `%at` (unix epoch); 140 sites across 16 test files were missing an explicit `encoding="utf-8"` on subprocess/file reads, which only worked by accident locally under `PYTHONUTF8=1`. A follow-up fix added `errors="replace"` to the subprocess reads that consume externally-produced, locale-dependent output (`git`, `bin/release.py`) — the strict `utf-8` decode from the first pass broke on Windows runners without `PYTHONUTF8` set, since their locale output real accented characters as cp1252 bytes.
- **Deterministic test suite on CI runners** (issue #50): `tests/conftest.py`'s `run_cmd()` now injects a fallback git author/committer identity into every subprocess it spawns, applied only to a repo that has no identity configured anywhere (system, global, or set explicitly by that specific test) — on a runner with no git identity at all (e.g. GitHub Actions with `useConfigOnly = true`), every `git commit` issued by the test helpers previously exited 128 silently (the return code went unchecked), leaving dozens of tests asserting against repos that silently had zero commits. `tests/test_release.py`'s import of `bin.release_helpers` was also made independent of the working directory — it previously only worked by the accident of `pytest` inserting the cwd on `sys.path`, breaking with `ModuleNotFoundError` under a different cwd on Windows/CI.

### Fixed

- **Fragile git-log date parsing unified** (issue #55): `bin/git-memory-gc.py` and `bin/git-memory-doctor.py` each carried a byte-for-byte duplicate of the same `%aI` + `datetime.fromisoformat()` parser, which could silently degrade to `None` (dropping `Last:`/timeline ages) depending on the runner's git version. Both now call a shared `lib/date_parsing.py:parse_date()`, switched to `%at` (unix epoch) for robustness. `lib/bootstrap_commits.py` deliberately keeps `%aI` — its date is only ever displayed, never parsed, so the readable format stays. Hardened through adversarial review (Argus/Moriarty): an explicit type guard for non-`str` input, a length cap ahead of `int()` conversion, and rejection of non-ASCII Unicode digit strings (accepted by `str.isdigit()`, but never emitted by a real `git log %at`). `lib/boot_git_checks.py:time_ago()` picked up the same `OverflowError` guard and Unicode-digit rejection for consistency with the new shared parser. A malformed-date edge case — a hand-crafted commit with an out-of-range (year 10000+) timestamp, invisible to `gc.py`'s and `doctor.py`'s stale-commit heuristics with no trace — is an accepted, documented low-risk residual rather than a fix: it requires repo write access already inside the trust boundary, and the failure direction is always safe (under-reports, never deletes). Suite: 1026 tests green.
- **Windows console encoding crashes** (issue #52): none of the toolkit's 25 entry points (`bin/`, `hooks/`, `scripts/skill-search.py`, the flow-stack scaffold script) forced UTF-8 on stdout/stderr, so any non-ASCII `print()` under a Windows cp1252 console raised an uncaught `UnicodeEncodeError` — a partial install, a memory hook crashing on every prompt, or a commit that reported failure despite succeeding. New `lib/encoding_guard.py`, fail-open, applied at all 25 entry points with `errors="replace"` so a broken console encoding can no longer block the operation itself.

## [1.17.0] - 2026-07-07

### Added

- **Multi-machine boot memory freshness** (issue #49): the `[git-memory-boot]` SessionStart hook now detects when local git-memory is behind another machine's and reacts instead of silently showing stale state.
  - The previous unconditional `git fetch --quiet` (5s timeout) is replaced by a hardened, gated, rate-limited fetch (`fetch_memory_ref()`, `unmassk-toolkit/lib/boot_git_checks.py`): skipped entirely on a repo with no unmassk-toolkit memory installed, skipped again if `.git/FETCH_HEAD` is younger than 5 minutes, bounded to a 3s timeout, and run with `GIT_TERMINAL_PROMPT=0`, a neutralized askpass (POSIX and Windows), `BatchMode=yes`, and every configured credential helper disabled so it can never hang on an interactive prompt. Fail-open on every branch — network down, a missing remote, or a bug in the fetch path never delays or crashes the boot.
  - A `MEMORY:` provenance/freshness stamp now renders near the top of both the short stdout banner and the full boot-log file (`render_memoria_stamp()`): `remote (fetched Ns ago)`, `LOCAL — fetch skipped (rate-limit, Ns ago)`, `LOCAL — last fetch Ns ago, unverified`, `LOCAL — unverified (never synced with origin)`, or `LOCAL — upstream unrelated (no shared history), not shown`.
  - When local is strictly behind its upstream, a `PULL DIRECTIVE:` line proposes `git pull` as the first action of the session — or, if the working tree is dirty, explicitly says not to pull so nothing gets clobbered (`_build_pull_directive_lines()`).
  - `resolve_boot_memory()` (`unmassk-toolkit/lib/boot_memory.py`) now reads Next/Decision/Memo/Remember/Blocker straight from `origin/<branch>` when local is strictly behind (each entry labeled ` [source: remote]`), and from both sides (remote side labeled) when the branches have diverged — never silently merged into one truth. The glossary cache (`boot_glossary_cache.py`) now keys its freshness on both local HEAD's sha and origin's, so a cache built before the remote moved is no longer served as fresh.
  - Repo-identity guards added during hardening: `check_upstream_shares_history()` confirms the resolved upstream actually shares commit ancestry with local HEAD (`git merge-base`) before any of its memory is read or labeled "remote" — an unrelated repo that happens to share a branch name can no longer leak its memory into this project's boot, and the PULL DIRECTIVE is suppressed in that case (git itself would refuse the merge). The live remote name is re-resolved (`git remote get-url`) instead of assuming `origin`, so a renamed remote (`git remote rename origin upstream`) still works. A negative `.git/FETCH_HEAD` age (clock skew across machines) is treated as "not fresh" instead of permanently suppressing future fetches.
  - `git-memory-commit.py` now prints a warn-only (never blocking) notice before a `decision`/`memo`/`remember`/`context` commit if local is behind its upstream, reading the existing `@{u}` tracking ref — no extra fetch is performed for this check.
  - Cross-platform hardening: `run_git()` (`unmassk-toolkit/lib/git_helpers.py`) now kills the whole descendant process tree on a timeout, not just the direct `git` child — POSIX via process groups (`os.killpg`), Windows via `taskkill /F /T /PID`. One residual is documented rather than silently present: a Windows descendant that re-parents itself via Task Scheduler (`schtasks`) or a Windows service escapes `taskkill /T`'s PID-tree walk — accepted as a known limitation (reproduced live by Moriarty), since a process that self-detaches to a system service already implies the invoked `git` binary is fully compromised.

### Fixed

- `time_ago()` (`unmassk-toolkit/lib/boot_git_checks.py`) could raise an uncaught `OverflowError` on an out-of-range or malformed timestamp instead of degrading to `"unknown"` like every other malformed-input case — added to the existing `except` clause alongside `ValueError`/`TypeError`/`OSError`.

## [1.16.1] - 2026-07-06

### Fixed

- **Windows startup crash**: `os.O_NOFOLLOW` is POSIX-only, so on Windows every call into `open_no_follow_symlink()` (the symlink-safe file guard used by the boot hook, `doctor`, and several per-message hooks) raised an `AttributeError` — not `OSError`, so it escaped every existing `except OSError` and crashed instead of failing safe. `open_no_follow_symlink()` and its twin `_symlink_safe_open.open_no_follow_symlink_fallback()` (`unmassk-toolkit/lib/git_helpers.py`, `unmassk-toolkit/lib/_symlink_safe_open.py`) now branch on platform: POSIX keeps the original atomic `O_NOFOLLOW` open; Windows uses a two-step guard instead (`os.path.islink()` pre-check, then an `lstat`/`fstat` identity comparison, with the truncate deferred until after that check passes) that raises `OSError` on the same symlink-escape attempts the POSIX path blocks, never `AttributeError`. Two Windows-only residuals are accepted and documented in the docstring rather than silently present: a brand-new path has no prior identity to compare against (accepted TOCTOU gap), and a hard link to a file outside the repo is undetectable on any platform by either guard (deferred to a dedicated change per decision `51a3c44`). The `0o600` mode-bits docstring claim was also corrected — it only denies group/other access on POSIX; on Windows the file inherits its containing directory's ACL instead.
- **Encoding**: git output, hook subprocess calls, and a JSON file read across `unmassk-toolkit/lib/git_helpers.py` (`run_git`), `version.py`, `boot_health.py`, and four hooks (`session-start-crew.py`, `stop-dod-gate.py`, `user-prompt-memory-check.py`, `validate-memory-path.py`) now pass `encoding="utf-8"` explicitly instead of relying on the OS default — Windows defaults to `cp1252`, which broke or mangled (mojibake) any accented character or emoji in a commit message, and previously only worked by accident under `PYTHONUTF8=1`. `scripts/skill-search.py`'s `SKILL_SEARCH_EXTRA_DIRS` env var now splits on `os.pathsep` instead of a hardcoded `:`, so it works on Windows (`;`-separated paths) as well as POSIX.
- `run_git()` now reports a `UnicodeDecodeError` to stderr with a diagnostic message instead of silently collapsing it into the same generic `(1, "")` result as every other git failure, so a genuine decode failure is distinguishable from "git itself failed" during troubleshooting.

## [1.16.0] - 2026-07-06

### Fixed

- The `[git-memory-boot]` SessionStart hook (`unmassk-toolkit/hooks/session-start-boot.py`) could lose its `Next:` instruction when the full boot briefing was large: the Claude Code harness only previews a small prefix of SessionStart's stdout, so an oversized briefing (commonly caused by one bloated `context()` commit subject) silently cut off exactly the part telling Claude what to do next. There is no safe size threshold, so stdout is now unconditionally a short banner (status, branch, and a pointer) for every repo, regardless of size, while the complete, nothing-shortened briefing is always written to the fixed path `.claude/.unmassk/boot-log-latest.txt` for Claude to read instead. If writing that file fails for any reason, the hook falls back to printing the full content inline rather than pointing at a file that doesn't exist.
- `git-memory-commit.py` now rejects (`exit 1`, no commit created) a `context()` commit whose full subject line (emoji + `type(scope): message`) exceeds 100 characters, telling the caller to shorten the message and move the rest into `--body` — closing off the root cause of the truncation bug above at the source, instead of only mitigating its symptom. Other commit types are unaffected.

### Security

- **Parent-directory symlink escape**: every existing symlink guard in this codebase (`open_no_follow_symlink()`) only protected the final path component being opened — none protected the parent directories. If `.claude` itself (or a subdirectory like `.unmassk`, `agent-memory`, `skills`, `bin`, `hooks`) were a symlink committed in a malicious repo, `os.makedirs()`/`open()` silently followed it, so file operations that looked scoped to the project could actually read or write anywhere on disk — including overwriting the user's real `~/.claude/settings.json` or deleting another plugin's hook registrations. Closed with a single new chokepoint, `verify_path_within_project()` (`unmassk-toolkit/lib/git_helpers.py`), which resolves the full path via `realpath` and rejects it unless it stays inside the project root — mirroring the pattern `hooks/validate-memory-path.py` already used for the same bug class. Applied across every read/write site in `bin/`, `hooks/`, and `lib/` that touches `.claude/` (9 files call it directly), found via a mechanical AST sweep cross-checked independently by Argus.
- **Untrusted commit-derived content reaching Claude's context unsanitized**: text sourced from git commits — controllable by anyone able to commit to the repo — flowed into the boot briefing without going through the existing sanitizer in several places (commit scope labels, branch names, timeline entries, crowned decision/memo text, manifest version strings, and more). Closed by applying `_sanitize_trailer_value()` consistently at every render site in `unmassk-toolkit/lib/boot_render.py` and `boot_memory.py`.
- **Fake log-entry injection via control bytes**: the boot hook parsed `git log` output using `\x1e`/`\x1f` as field/record separators, both forgeable from inside a commit body — a crafted commit could inject bytes that made the parser see fabricated decision/memo/remember entries that never existed. Fixed by switching to `git log -z` (`unmassk-toolkit/lib/boot_memory.py`), which uses a real NUL byte as the record separator — NUL cannot appear in a git commit message, so it can't be forged.

### Changed

- `hooks/session-start-boot.py` split from 1278 lines into a single 330-line entry point plus 6 cohesive modules under `unmassk-toolkit/lib/`: `boot_memory.py` (memory/glossary extraction, further split into `boot_glossary_cache.py`), `boot_render.py` (section rendering), `boot_checks.py` (thin compatibility shim), `boot_health.py` and `boot_git_checks.py` (health/git status checks), and `boot_migrations.py`. `bin/git-memory-bootstrap.py` (936→143 lines) and `bin/git-memory-install.py` (541→252 lines) were split the same way into `lib/bootstrap_*.py` and `lib/install_*.py` modules. `bin/git-memory-doctor.py` (518 lines) and `bin/git-memory-upgrade.py` (537 lines) remain above the usual 500-line convention — both accepted as documented exceptions rather than split further this round.

## [1.15.0] - 2026-07-04

### Added

- Project startup quality floor: `unmassk-project-lifecycle`'s START branch (`unmassk-toolkit/skills/unmassk-project-lifecycle/SKILL.md`) gains a new step, before the first feature commit on a brand-new project, that confirms the scaffold has a working test command (even trivial), a lint/format config, and — if the stack implies secrets — a `.env.example`. Any missing piece is no longer silently skipped: it must be captured as an explicit `decision()` (e.g. "deferred: no test runner yet"). A small, concrete slice of the larger "solid project startup guide" idea, which otherwise stays deliberately frozen in the roadmap pending the memory/consolidator system maturing — a validation council found this specific piece doesn't depend on that maturity, so it shipped now.

### Changed

- Gitto Mode C (Consolidator, `unmassk-toolkit/agents/gitto.md`) now automatically retires superseded `Memo`/`Remember` entries when it crowns a group, instead of relying on the orchestrator to notice a near-duplicate mid-conversation and tombstone it by hand. It reuses the existing, already-tested `Resolved-Memo:`/`Resolved-Remember:` trailer mechanism — still additive, since a tombstone is itself a new commit, nothing is edited or deleted. `Decision` entries remain untouchable, unchanged. A 5-advisor council review closed three real gaps before this shipped: each cited source is checked individually before being tombstoned (a crown can be right on average while one specific source still carries a caveat the crown didn't capture — that source is left alone); the very first time this new tombstoning behavior fires anywhere in the project now requires Bex's approval, separate from the existing first-crown-per-scope gate; and a narrow new rule lets a truly isolated Memo/Remember (one that never grouped with anything, so it could never be crowned) be retired on its own once it's gone 6+ months with zero references, capped at 1-2 per pass.

## [1.14.0] - 2026-07-04

### Added

- Per-message skill-router nudge: the `[memory-check]` hook (`unmassk-toolkit/hooks/user-prompt-memory-check.py`) now checks every user message — not just the first — against a lightweight trigger-phrase table (new `unmassk-toolkit/lib/skill_router.py`) covering all 9 protocol skills, sourced directly from each skill's own frontmatter `description`. On a match it appends an informational `[skill-router] Possibly relevant skill(s): ...` line — purely a nudge, it never blocks or denies. A permanent drift-guard test loads the live SKILL.md descriptions at test time and fails if the trigger table ever falls out of sync with them again.

### Changed

- Protocols menu generator (`unmassk-toolkit/lib/managed_blocks.py`) extended with `unmassk-flow`, `unmassk-audit`, and `unmassk-flow-stack` — previously excluded from the CLAUDE.md Protocols menu under an old "only list installed+referenced skills" policy that no longer applied now that all three are fully shipped and tested; a skill Claude can't see in the one menu it reads every session can't be routed to reliably.

### Fixed

- Frontmatter trigger-phrase collisions between protocol skills — the actual mechanism Claude Code uses to pick which skill to invoke — fixed after a 5-advisor validation council tested 12 adversarial phrases against an earlier pass: `unmassk-grill` vs `unmassk-council` still tied on "two valid interpretations" vs "which option" (`unmassk-grill` is now scoped to ambiguity about WHAT to build, `unmassk-council` to choosing between already-scoped approaches to an already-understood goal); `unmassk-council`'s own description contradicted itself (claimed "nothing decided" while also excluding undefined requirements) — clarified that its idea-generation compares approaches to a goal that's already understood, not defines the goal; `unmassk-project-lifecycle` now defers to `unmassk-grill` when scope is undecided and to `unmassk-flow-stack` when a concrete stack is already named (previously only `unmassk-flow-stack` knew to defer, not the reverse).
- CRLF line endings in `unmassk-audit/SKILL.md` — the only file in the repo affected, likely a leftover from an earlier Windows-compatibility fix — converted to LF; could have broken tooling parsing its frontmatter.
- `test_user_prompt_skill_router.py` took 4+ minutes because most cases spawned a real subprocess and git repo per test; refactored so the majority call the pure `match_skills()` function in-process, reserving subprocess tests for the 6 that genuinely exercise hook wiring — same 85 tests, same coverage, now runs in well under 1 second.

## [1.13.0] - 2026-07-04

### Changed

- `unmassk-grill` extended instead of building a new skill: after researching GitHub's `spec-kit` and running a full pressure-test, the proposed new skill's core mechanism turned out to be identical to what `unmassk-grill` already does. Added a "Vagueness preamble" that scans the request's own wording for unquantified qualifiers, missing actors, missing error states, and ambiguous scope before the interview starts; an "Independently testable slice" check in the interview rules to catch a request that's secretly 2-3 bundled features; and a "Bounded mode" for when grill is invoked automatically by `unmassk-project-lifecycle` or `unmassk-flow` (capped at 5 questions, instead of running unbounded, so it doesn't stall an automated pipeline step).
- `unmassk-flow` (Step 0 Triage, for Standard/Big scope) and `unmassk-project-lifecycle` (START branch, before the requirements cascade) now call `unmassk-grill` explicitly — previously neither skill invoked it at all, using the toolkit's established phrasing ("use the Skill tool with `skill=\"unmassk-grill\"`") instead of the looser "invoke" wording both had. Flow's Step 1 Brainstorm also picks up any open branches logged by grill's bounded pass instead of re-deriving them from scratch.
- Removed the orphaned `unmassk-project-lifecycle/references/prd-template.md` — it was never wired into any live skill; git-memory's decision/memo commits already cover what a static PRD file would.

## [1.12.0] - 2026-07-04

### Added

- Gitto Mode C (Consolidator) installed (`agents/gitto.md`): a periodic memory-consolidation mode that reads all of a project's decision/memo/remember history and writes additive "crown" entries for topics that drifted across many commits, so the canonical version surfaces instead of the reader having to reconcile scattered restatements. Ships with a retraction mechanism — a `Retract-Crown: <hash>` trailer (paired with a required `Why:`, enforced by both commit-trailer validation hooks) that revokes a crown without resurrecting an older, already-superseded one; at boot, `session-start-boot.py` excludes retracted crowns and falls back to the fully un-crowned entry set. `Retract-Crown` added to `VALID_KEYS`/`MEMORY_KEYS` in `lib/constants.py`. 17 new tests (`tests/test_crown_retraction.py`); the existing 21 Crown tests are unaffected.

### Changed

- Commit/push cadence clarified for multi-agent pipelines: the crew (Ultron, Dante, Cerberus, etc.) never commits its own work — each agent returns a summary and the orchestrator records a local `wip:` commit per sub-step without pushing. A pipeline isn't closed until Yoda's verdict and Alexandria's documentation pass are both done; only then does Gitto squash the wips into a clean commit (or a few, with real trailers) and push. Memory commits (`decision`/`memo`/`remember`/`context`) are unaffected and still push immediately. Documented in `unmassk-gitmemory` and `unmassk-flow` SKILL.md, including a repo-type-aware (trunk vs. gitflow) rewrite of Flow's Step 7 Close, which previously assumed gitflow (merge to `dev`) unconditionally.

### Fixed

- Gitto Mode C's own grep pattern for reading memory history (`git log --grep="^\(Decision\|Memo\|Remember\):"`) matched zero commits against this project's real commit format (`<emoji> decision(scope): text`, not `Decision: text`) — caught via a dry-run against the repo's own memory before the feature shipped as done.

## [1.11.1] - 2026-07-03

### Changed

- README "Standards" row corrected to say 34 sections (was still showing 33), matching the §34 Producer↔Consumer Data Integrity addition already shipped in v1.11.0.

### Fixed

- Hardcoded Spanish forced onto every toolkit installer regardless of their own language, across code shared by every install: `lib/managed_blocks.py` (the generic CLAUDE.md communication block literally instructed every installer's Claude to always respond in Spanish — now language-neutral, matches the user's own language instead), `skills/unmassk-standards/references/standards.md` §18 "Language in Code" (was forcing Spanish comments/logs/error messages into the actual code Ultron writes for any installer's project, previously enforced as a T3 finding by Cerberus/Yoda — now follows the project's existing convention, defaults to English if greenfield; "identifiers always English" unchanged), `hooks/pre-task-recall.py` (memory-injection header shown to every subagent), `hooks/session-start-boot.py` (consolidation warning), `skills/unmassk-project-lifecycle/references/prd-template.md` (currently orphaned/unwired, translated anyway), and `bin/git-memory-commit.py` (`--path` argparse help string) — all translated to English. Found via a full Bilbo sweep of the distributed toolkit surface (skills/agents/hooks/lib/bin/README/CHANGELOG) after the first instance surfaced. The maintainer's own Spanish-communication preference is preserved separately as a `remember(user)` entry in git-memory — not lost, just no longer embedded in code shipped to every installer.

## [1.11.0] - 2026-07-02

### Added

- `unmassk-standards` §34 "Producer↔Consumer Data Integrity (Anti-Fixture-Fabrication)": closes a real-world failure class where a downstream project shipped ~2 weeks of undetected bugs because every crew agent validated against the same hand-fabricated mock fixture instead of the real backend. Enforced at four independent checkpoints: Dante (never Ultron) owns building the round-trip check against the real producer; Cerberus flags hand-typed literals used as expected values; Moriarty sabotages the real dependency with realistic corruption (not just connection kill-switches), verified through an independent channel, before declaring a feature resilient; Yoda's new Round-Trip Evidence Rule is fail-closed by default and requires a mechanical artifact he reads himself — never narrated by another agent — before rendering a verdict, with no "approved with conditions" discretion for this gate. `unmassk-flow` Step 0 (Triage) now requires a mandatory seam declaration regardless of feature size. Alexandria gains a new duty: document the real producer↔consumer contract once Yoda approves it, never the fixture.

### Fixed

- Merge gate (`hooks/pre-merge-gate.py`) no longer blocks same-branch catch-up syncs (e.g. `git pull origin main` while on `main`) behind the Cerberus+Alexandria review requirement — that gate now only fires when merging or pulling a genuinely different branch. Fail-closed: any ambiguity in resolving the current branch or the merge/pull target still falls back to requiring review. 12 new tests (`tests/test_pre_merge_gate.py`).

## [1.10.0] - 2026-06-16

### Added

- Crown marker (`Crown: <kind>` trailer): any memory commit (`decision`/`memo`/`remember`) can carry `Crown: Decision|Memo|Remember` to designate itself as the canonical entry for its category. At boot, crowned entries appear first in their section (DECISIONS / MEMOS / REMEMBER) and are prefixed with 👑, outside the normal entry budget so they never displace regular entries. Crown wins tie-breaking by scope even when the entry originates in the glossary. Additive and presentational: the "a Decision is never tombstoned" rule is unchanged. `Crown` added to `VALID_KEYS` and `MEMORY_KEYS` in `lib/constants.py`. 21 tests (`tests/test_crown.py`). This is Phase 1 of the memory consolidator — infrastructure only; the auto-consolidation flow (Gitto writing crown entries) is not yet wired (see below).
- Consolidation trigger (`CONSOLIDATE:` block): at boot, if the number of commits since the last `context(consolidation)` reaches the threshold (default 50, overridable via `GIT_MEMORY_CONSOLIDATION_THRESHOLD`), the boot output emits a `CONSOLIDATE:` block telling the orchestrator to launch Gitto in consolidator mode. Helper `commits_since_last_consolidation()` added to `lib/git_helpers.py`; uses `rev-list --count` for robustness on long histories; returns a high sentinel (9999) when no `context(consolidation)` exists so the first-ever run always triggers; fail-safe to 0 on error. Only the scope `context(consolidation)` resets the counter — ordinary `context()` commits do not. 11 tests (`tests/test_consolidation_trigger.py`). Phase 2 of the consolidator — trigger infrastructure only. The Gitto consolidator prompt is a draft under review (`docs/gitto-consolidador-DRAFT.md`, Phase 4, pending external AI review); automatic consolidation is not yet active.

## [1.9.0] - 2026-06-12

### Fixed

- Boot glossary merge now respects GC tombstones (`hooks/session-start-boot.py`): retired memos/remembers (`Resolved-Memo`/`Resolved-Remember`) no longer reappear at session start. `extract_memory()` now exposes the collected tombstones, and the REMEMBER/MEMOS glossary-merge steps skip any entry whose normalized text is tombstoned (decisions are never tombstoned, by design). Re-applies the fix from stale PR #20 fresh on `main`, with a regression test, without dragging that branch's 3-month-old memory commits. Test-first; full suite green.

#### Multi-agent audit (Bilbo · Argus · Cerberus · Moriarty) — correctness & robustness sweep

- **Three hook crashes that broke the session (fail-open violations):** `post-validate-commit-trailers.py` crashed on a non-numeric `exit_code`; `session-start-crew.py` crashed on a non-UTF-8 `CLAUDE.md`; `pre-validate-commit-trailers.py` blocked legitimate commands (`cat git.log`, `git log-remote`) via an over-broad `git…log` pattern. All three now degrade safely.
- **Memory dedup gate** (`pre-memory-dedup-gate.py`) was silently skipped when trailers used single quotes or no quotes — pattern now matches all three forms.
- **Retired notes reappearing:** the boot glossary merge only honored tombstones within the recent scan window (retired notes older than ~30 commits came back); and the pre-compaction snapshot (`precompact-snapshot.py`) only checked 2 of the 4 tombstone kinds. Both now honor tombstones across the full range / all `TOMBSTONE_KEYS`.
- **Context-commit detection** unified to one predicate across `extract_memory()` and `get_last_context_time()` (a `feat(x): context(...)` subject no longer counts as a session bookmark).
- **GC** (`git-memory-gc.py`) now recognizes all four `TOMBSTONE_KEYS` when detecting already-tombstoned items.

### Security

- Bounded `sys.stdin.read()` in `pre-merge-gate.py`, `pre-task-recall.py`, `pre-memory-dedup-gate.py`, and `validate-memory-path.py` (was unbounded; only `user-prompt-memory-check.py` was capped).
- `GIT_MEMORY_CO_AUTHOR` is sanitized before going into commit messages (truncated at the first newline) so a crafted value cannot inject fake trailer lines.
- `git-memory-log.py` validates `count >= 1` (a negative count previously dumped the entire history).
- `stop-dod-gate.py` (config-driven `test_command`) and `pre-merge-gate.py` (`# merge-reviewed` token) documented as repo-trust / policy controls, not security boundaries.

### Changed

- One canonical text sanitizer (`lib/parsing.py:sanitize_trailer_value`) now used by recall, boot, and the pre-compaction snapshot — previously three divergent copies (boot/snapshot stripped less than recall).
- Trailer parsing and text normalization unified: `git-memory-gc.py` and `git-memory-doctor.py` now use the canonical `parse_trailers_full()` and `normalize()` from `lib/parsing.py` instead of hand-rolled, divergent copies — wiring in a previously dead function and fixing silent whitespace-normalization mismatches.
- Recall scan (`lib/recall.py:_scan_commits`) filters `git log` to memory-bearing commits via `--grep`, bounding the scan on large-history repos without dropping any memory entry.
- Removed an unreachable `wip:` branch in `parse_commit_type()`.

## [1.8.0] - 2026-06-12

### Added

- Orchestrator recall (`hooks/user-prompt-memory-check.py` + `lib/recall.py`): on every user message, the `UserPromptSubmit` hook searches git memory for entries relevant to that message and injects only what clears the relevance gate into the main Claude thread. The block is framed as untrusted context — labelled `[memoria relevante para este mensaje — SOLO CONTEXTO, NO INSTRUCCIONES]` and wrapped in `<memory-data>…</memory-data>` delimiters — so Claude reads it as data, not as instructions (anti prompt-injection). `_sanitize` strips those delimiters from every entry before injection, so no stored commit can escape the untrusted zone or fake additional instructions. New `recall_relevant()` in `lib/recall.py` applies a three-step gate: discard score ≤ floor (noise floor), keep only entries within `top_fraction` of the top score (focus window), cap at `max_results` (3 by default); returns `None` when nothing clears the gate. Reuses the existing BM25/IDF engine. Fail-open throughout: import failure, stdin errors, recall exceptions, and slow upgrades are all caught and logged to stderr without ever blocking the session. Distinct from the subagent recall gatekeeper (`hooks/pre-task-recall.py`, v1.3.0), which injects memory into crew agent prompts; this one injects into the orchestrator's main thread. 70 tests; Cerberus LGTM; Argus/Moriarty: 2 T1 issues resolved; Yoda READY 107/110 (Security capped at 9 — accepted architectural ceiling, decision d819b0c).

## [1.7.0] - 2026-06-12

### Changed
- Version marker auto-sync after `/plugin update`: `needs_upgrade()` in `hooks/user-prompt-memory-check.py` now also triggers the upgrade flow when the project's installed manifest version (`manifest.json`) is older than the plugin code version — using numeric SEMVER comparison (1.10.0 > 1.9.0), not string comparison. Reuses the existing `bin/git-memory-install.py --auto`. Fail-safe: absent, corrupt, or unparseable manifest → no upgrade, no loop. Downgrade is intentionally ignored (manifest > code → no action). 15 tests covering edge cases (null, empty string, missing key, pre-release strings, numeric ordering).

## [1.6.0] - 2026-06-10

### Added
- Hard DoD gate (`hooks/stop-dod-gate.py`): Stop hook that BLOCKS session close (`decision:block`) when the project's configured test command exits non-zero — "done" can no longer be claimed with red tests. Opt-in via `.claude/git-memory-config.json` `test_command`. `shell=False` + `shlex.split(posix=False)` + quote-strip (injection-safe, Windows-compatible); 60s internal timeout (hooks.json 90s). Fail-open on any infra error (missing/unreadable config, missing binary, timeout, shlex `ValueError`, unexpected exception) — a broken gate never traps the user. 23 tests; Cerberus LGTM (0 blocking), both suggestions closed. Foundation for a safe autonomous ("Ralph") mode. Closes roadmap items #2/#3.

### Changed
- `unmassk-core` SKILL.md hardened: removed the "trivial 1-line edit" carve-out that let the orchestrator touch production code/tests. The orchestrator now edits NO code or tests ever (not even one-liners) — production code → Ultron, tests → Dante; "do it yourself" never licenses touching code. Closes a real loophole the orchestrator had exploited (and the matching `remember(claude)` was retired as a duplicate — the rule belongs in the skill, not memory).

## [1.5.0] - 2026-06-10

### Added
- Memory dedup gate (`hooks/pre-memory-dedup-gate.py`): PreToolUse/Bash hook that WARNS (non-blocking, fail-open) when a `memo`/`remember` commit is a lexical near-duplicate of an existing entry of the same type — Jaccard ≥ 0.40 over recall's tokenizer with an extended dedup stoplist, naming the match in `permissionDecisionReason`. Decisions are never compared (sacred). Cheap pre-filter regex so the 99% of Bash commands that are not memory commits skip git entirely. 40 tests; validated against the real corpus (does not fire on the iterated "3 memory systems" memos — those are semantic restatements, not lexical dups). Documented in `unmassk-gitmemory` Active Hooks.

### Changed
- Memory capture reminder (`hooks/user-prompt-memory-check.py`): the per-message `[memory-check]` flipped from "contains memory? → save it" to restraint — save ONLY if durable, non-derivable, and not already captured; on a correction, RETIRE the old entry with a tombstone instead of stacking; systemic/process rules belong in the loaded skill, not memory. Lowers over-saving pressure at the source (the gate is the net; this is the belt).

## [1.4.0] - 2026-06-09

### Added
- Release script (`bin/release.py` + `bin/release_helpers.py`): single command to orchestrate a full plugin release — pre-flight checks (clean tree, semver order, non-empty changelog, upstream configured, not behind remote), version bump, changelog promotion, pathspec commit via `git-memory-commit.py`, push, and post-push verification. Supports `--dry-run` and `--allow-dirty`. Exit codes: 0 = ok, 1 = preflight/execution error, 2 = post-push verify failure.
- `git-memory-commit.py --path` flag: allows callers to commit only specific files by pathspec, used by the release script to stage exactly the three release files without touching the rest of the index.
- `docs/RELEASING.md`: human-readable how-to guide for the release workflow — preconditions, dry-run first, what each step does, flags, version rules, mid-release recovery, and a first-use checklist.
- Documentation coverage: `unmassk-seo` SKILL.md now documents both active hooks (`pre-commit-seo-check.sh` and `validate-schema.py`) with triggers, what they check, and how to interpret their output. `unmassk-ops/ops-observability` routing table corrected to reference `logql-regression-checks.sh` as the LogQL validator. `unmassk-ops/ops-cicd` documents the usage trigger for `azure-step-walker.py` (traversal library, not invoked directly) and `azure-test-regressions.py` (regression suite). `unmassk-media/media-image-edit` now references `.env.example` for `FAL_KEY` configuration.
- Documentation discipline (three-audience rule): every new capability must be documented for humans (`README`/`docs`), the team (roadmap/git-memory), and Claude at load (`SKILL.md`/`CLAUDE.md`) in the same change. Encoded in `unmassk-core`, Flow's Document step, `unmassk-close-session`, and Alexandria's mandate.
- Toolkit discoverability in skills: `unmassk-gitmemory` now documents the `--path` flag, the `git-memory-recall.py` search tool (with ranking internals), the `memo(stack)` category, the release process (`bin/release.py`), and an "Active Hooks" section (merge gate, recall gatekeeper, commit validation, etc.). `unmassk-core` gains a Protocol-skills menu and Gitto Mode B (git ops). `README` gains a Development section and a Protocols row.
- Config for domain plugins: `unmassk-seo/.env.example` (5 MCP credentials), `unmassk-compliance/.mcp.json` + `.env.example` (Better i18n MCP).

### Fixed
- Scope-map path in `unmassk-gitmemory` SKILL.md corrected (`unmassk-crew-bilbo` → `unmassk-toolkit-bilbo`) — was a silent failure whenever Claude looked up the scope map.
- Test isolation bug: `test_migrate_statusline.py` left a stub `git_helpers` (missing `GIT_TIMEOUT`) in `sys.modules` without restoring it, breaking `test_recall.py` in the full suite (58 failures). Now snapshots/restores `sys.modules`. Full suite: 315/315 green.

### Removed
- Dead weight: `!new_skills/` (already integrated in v1.3.0), empty `generated-images/`, and orphaned `.pyc` files under the root `tests/`.

## [1.3.0] - 2026-06-08

### Added
- Recall gatekeeper (`hooks/pre-task-recall.py`): PreToolUse/Task hook that injects relevant project memory (decisions, memos, remembers) into subagent prompts before they execute. Uses `lib/recall.py` for keyword-ranked retrieval. Fail-open: any error lets the spawn through unchanged. Whitelisted to the 8 crew agents (Ultron, Dante, Cerberus, Argus, Moriarty, House, Yoda, Alexandria); Bilbo and Gitto are excluded. 51 tests.
- Build mode (`skills/unmassk-flow/references/linear.md`, `references/test-first.md`): two coding modes selectable per task. Linear for straightforward work; test-first/ATDD for complex features (Dante enters twice — acceptance contract before implementation, exhaustive hardening after). Flow acts as router in Execute Step 4 and delegates to the chosen reference document. Ultron and Dante gain explicit build-mode awareness.
- CLAUDE.md block generator (`lib/managed_blocks.py`): single source of truth for all 5 managed blocks (toolkit, protocols, caveman, communication, build-mode). Idempotent upsert — install, upgrade, and uninstall all import from this module; the blocks can no longer diverge across lifecycle commands. 35 new tests, 0 regressions.
- Protocol skills installed: `close-session`, `grill`, `council`, `project-lifecycle` — all four built, tested, and registered in the CLAUDE.md menu. Previously listed as planned; now live.
- Close-session hook (`hooks/stop-close-session.py`): Stop hook that fires at end of session, prompts the orchestrator to run the close-session skill (decisions dump, versioning if applicable, cleanup). Suppressed when the session had no substantive work. Coexists with the existing `stop-dod-check` hook.
- PRD template saved to `skills/unmassk-project-lifecycle/references/prd-template.md` for use in the START branch of the lifecycle skill.
- Communication block added to CLAUDE.md: rules for how agents report to the orchestrator (results not process, confirm structural changes with exceptions for security/irreversible/unverifiable, one thing at a time).

### Changed
- Flow skill (`skills/unmassk-flow/SKILL.md`) updated: Execute phase now routes to `references/linear.md` or `references/test-first.md` instead of inlining the method. Follows the Standards pattern — one rule, one place.
- Memory calibration tightened (`skills/unmassk-gitmemory/CALIBRATION.md`, `SKILL.md`): three root-cause fixes for over-saving — scope test (project rules belong in project memory, not global remember), stable-done filter (only save what is finished and confirmed, not in-progress reasoning), and timing-not-volume (urgency of a commit is determined by when the signal fires, not how many signals accumulated). `"never commit to main"` rule reframed by repo type: gitflow repos keep the rule; trunk-based repos commit to main by design.
- `unmassk-audit` skill aligned with session decisions: steps 0 and 13 now inherit `repo_type` from `unmassk-gitmemory` (gitflow → branch from dev + merge; trunk → main directly) instead of always assuming `dev`. The 97% coverage gate is documented as a deliberate audit exception that supersedes the pipeline's "coverage does not block merge" override. Scoring/tiers/weights now reference `unmassk-standards` rather than duplicating them.
- Core skill clarified: Ultron = production code only (not skills, agent prompts, or docs). Orchestrator loads standards on-demand; it does not load them at boot.

### Fixed
- Boot hook (`hooks/session-start-boot.py`): removed redundant full-text dump of `unmassk-core`, `unmassk-gitmemory`, and `CALIBRATION.md` from the boot output. These were being injected twice (once by the hook, once by the explicit Skill calls in CLAUDE.md), inflating the session start to ~57 KB that the harness truncated. Explicit Skill calls remain; the duplicate inline dump is gone.
- Flow-stack scaffold path corrected: `scaffold.py` was referenced as `flow-stack-selection` (does not exist) — fixed to `unmassk-flow-stack/scripts/scaffold.py` in two places, unblocking the lifecycle START branch.

## [1.2.0] - 2026-06-05

### Added
- Memory recall engine: `lib/recall.py` + CLI `bin/git-memory-recall.py`. Searches all decision/memo/remember commits by keyword with IDF ranking (rare terms score high, common terms sink), 1.5x bonus for scope matches, alphanumeric tokenization (finds `BM25`, `v2`, `RS256`), deduplication, and full history scan with no commit cap. Robust against context-injection attempts (sanitizes Unicode terminators) and enforces a query length cap.

### Changed
- `git_helpers.run_git` now accepts a `cwd` parameter, making it usable from any working directory.
- `TOMBSTONE_KEYS` and `RECALL_KEYS` constants extracted to `lib/constants.py` — shared between the recall engine and the boot hook (eliminates duplication).

### Removed
- Context-tracking subsystem removed entirely: `bin/context-writer.py`, the statusline wrapper it installed, context percentage warnings in `hooks/user-prompt-memory-check.py`, and all associated install/uninstall/upgrade lifecycle code. The subsystem was designed for the 200k-token context window; with 1M tokens it was noise.

### Fixed
- Upgrade self-heal: if a user's existing Claude settings still pointed the statusline at the deleted `context-writer.py`, the boot hook now detects this and restores the original statusline value (or removes the key), preventing a broken statusline after upgrading from any older version.

### Security
- `shell=True` in `context-writer.py` (issue #48, T1) is eliminated as a side-effect of removing the file entirely.

## [1.1.2] - 2026-03-24

### Fixed
- Boot migration `_migrate_untrack_generated_jsons()`: added `-r` flag to `git rm --cached` for `.unmassk/` directory — was failing silently (exit 128) without it.
- Upgrade tests: replaced stale `"Git Memory Active"` string literals with `"unmassk-toolkit Active"` to match current managed block content.

## [1.1.1] - 2026-03-24

### Fixed
- All 10 agent prompts: replaced routing language (`flag to X`, `route to X`, `@mention`) with scope declarations (`X's scope`). Agents outside chatroom cannot invoke each other — they only report back to the orchestrator.
- Ultron: added missing "The Team" table, removed leftover v1-to-v2 meta sections ("Things Cut From v1", "Summary of Changes").
- Cerberus: completed "The Team" table (was missing House, Bilbo, Alexandria, Gitto).
- Removed chatroom V2 reference files (`chatroom/*-system-prompt-v2.md`) — V2 is now canonical only in plugin source (`unmassk-toolkit/agents/`).

## [1.1.0] - 2026-03-24

### Added
- `compliance-legal-docs` skill: SKILL.md created with 42-reference routing table organized by category (contract review, GDPR/privacy, risk assessment, litigation, French employment law, vendor due diligence, document processing, legal ops)
- V2 system prompts for all 10 agents (alexandria, argus, bilbo, cerberus, dante, gitto, house, moriarty, ultron, yoda): universal format with The Team table, EXHAUSTION PROTOCOL, plain agent names (no @mentions), and no chatroom references — prompts work in any Claude Code context. Each agent self-reviewed their V2 draft and restored load-bearing V1 content that the initial rewrite lost.
- 5-phase agent pipeline: `PIPELINE_GENERIC` and `AGENT_PIPELINE_POSITION` rewritten. Each agent has an explicit chain position entry covering role, when to act, and when to skip.

### Fixed
- Boot hook now skips tombstoned entries when merging glossary remembers and memos into the session summary — `Resolved-Remember:` and `Resolved-Memo:` tombstones are respected on the glossary merge path, not just on the recent-commits path.

## [1.6.0] - 2026-03-16 (unmassk-crew)

### Added
- Cerberus commit-review mode: diff-only review pass with three severity tiers — Issue (blocks merge), Suggestion (recommended, non-blocking), Nitpick (never blocks). Includes a nitpick checklist covering naming conventions, natural language, import type consistency, `as const` usage, magic numbers, stray `console.log`, and similar low-stakes hygiene items. Inspired by CodeRabbit's review model.
- Alexandria merge mode: fast pre-merge documentation gate. Reads only the branch commits vs target branch, updates CHANGELOG under `[Unreleased]`, and checks affected CLAUDE.md files for staleness. No new files created, no memory writes — designed for speed at the merge boundary.
- `pre-merge-gate.py` PreToolUse hook: blocks `git merge` and `git pull` (non-rebase) commands until Cerberus and Alexandria have both passed. Detects `git.exe` on Windows, uses case-insensitive command matching, guards against `eval`/`bash -c`/`sh -c` indirection, and normalizes null bytes. Bypass by adding `# merge-reviewed` comment after both agents pass.

### Changed
- Orchestrator rules in `session-start-crew.py` updated with merge gate awareness: orchestrator must not call merge commands without a prior Cerberus + Alexandria pass, and proactive agent launch guidance is now explicit in the managed block.
- Crew table descriptions updated: Cerberus now documents both enterprise-audit mode and commit-review mode; Alexandria now documents both standard mode and merge mode.

## [1.5.0] - 2026-03-16 (unmassk-crew)

### Added
- `validate-memory-path.py` PreToolUse hook blocks agent-memory writes outside the git root — prevents agents from creating `.claude/agent-memory/` directories in wrong locations after `cd` operations. Fail-closed design with Windows case-insensitive path handling and symlink resolution via `realpath`.
- Orchestrator rules added to the `session-start-crew.py` managed block: orchestrator must not write code (delegate to Ultron), must launch Cerberus+Argus after any new code lands, decides what and who — not how.

### Changed
- Agent boot prompts hardened in 6 agents (cerberus, dante, ultron, alexandria, bilbo, house): `GIT_ROOT` is now resolved once as an absolute path with `|| exit 1` fallback, and the memory section enforces absolute paths anchored to `GIT_ROOT`.
- `hooks.json` updated with PreToolUse matcher for `Write|Edit` pointing to `validate-memory-path.py`.

### Fixed
- `compliance-legal-docs` references: removed broken `/mnt/skills/public/docx/SKILL.md` paths in 3 GDPR files (gdpr-privacy-notice-eu, dpia-sentinel, gdpr-breach-sentinel) — now points to `legal-docx-processing-anthropic`
- `compliance-legal-docs` references: removed broken sub-file references in both assignation-en-référé files (workflow-informations.md, structure-assignation.md, workflow-collecte.md, variantes-cas-particuliers.md, conseils-strategie.md) — workflows now self-contained in the reference files
- `compliance-legal-docs` references: removed broken `assets/` template path in politique-confidentialite-malik-taiar
- `compliance-legal-docs` references: removed `scripts/office/unpack.py`, `scripts/comment.py`, `scripts/accept_changes.py`, `scripts/recalc.py` references — replaced with standard system commands (unzip, LibreOffice, zip)
- `compliance-legal-docs` references: removed `editing.md`, `pptxgenjs.md`, `scripts/thumbnail.py` references from pptx-processing — replaced with inline instructions
- `compliance-legal-docs` references: removed `REFERENCE.md`, `FORMS.md` references from pdf-processing
- `compliance-legal-docs` references: replaced `AskUserQuestion`/`Task` tool calls in tabular-review with plain prose instructions; updated pdf/docx/xlsx "skill" references to reference file names

- `unmassk-ops` plugin: 5 skills covering the full ops domain (iac, containers, cicd, observability, scripting)
- `ops-iac` skill: SKILL.md + 14 references rewritten (Terraform, Ansible, Helm, Pulumi, OpenTofu)
- `ops-containers` skill: SKILL.md + 19 references rewritten (Kubernetes, Docker, Helm, container security)
- `ops-observability` skill: SKILL.md + 9 references rewritten (Prometheus, Grafana, alerting, logging)
- `ops-scripting` skill: SKILL.md + 21 references rewritten (Bash, Makefile)
- `ops-cicd` skill: SKILL.md + 30 references rewritten (GitHub Actions, GitLab CI, Azure Pipelines, Jenkins)

## [3.7.0] - 2026-03-13

### Added
- Boot auto-detects missing `git-memory-scopes.json` and instructs Claude to generate it via Explore agent
- Next cleanup in boot: checks GitHub issue status for pending Next items — closed issues are filtered out, items older than 7 days without an issue ref are marked `[stale]`
- Cross-repo guard prevents false positives when Next items reference issues in other repositories
- GC tombstone support for `Resolved-Next:` trailers — resolved pending items are hidden from future boot output
- Context warnings now use debounce: same-level warnings suppressed for 5 messages (shows `[CTX: N%]` instead), severity escalation (warning to critical) bypasses debounce
- Advisory language for context warnings — informs the agent instead of commanding it
- Test coverage for `context-writer.py` statusline wrapper (7 tests)
- `CO_AUTHOR` is now configurable via `GIT_MEMORY_CO_AUTHOR` environment variable

### Changed
- Scout agent removed — scope scanning now handled by an Explore agent prompt during boot
- Context percentage is now always shown in the UserPromptSubmit hook output (previously only displayed at 60%+ usage)
- Removed `Refs:` trailer key from valid keys — was unused dead code
- Replaced remaining scout terminology in bootstrap script and tests

### Fixed
- Boot and commit script hardening from code review feedback
- Debounce oscillation bug: context bouncing between 59-61% caused stale debounce state to suppress warnings incorrectly — state now resets when context drops back to info level
- `.context-status.json` and `.context-warn-state.json` added to `.gitignore` (were being tracked as noise)

## [3.6.0] - 2026-03-13

### Added
- Boot briefing v2: SessionStart hook produces structured output with zero redundant bash calls
- Automatic conversion of `Next:` trailers to GitHub issues during boot

### Changed
- Version is now centralized in `lib/version.py` as single source of truth, read from `plugin.json`
- CLAUDE.md boot instructions corrected and simplified

## [3.5.1] - 2026-03-13

### Added
- Context warnings now fire mid-session via UserPromptSubmit hook, not just at boot
- Slim hook output after boot — flag file prevents repeated instructions

### Fixed
- Quote all paths in hook output to prevent Windows path mangling
- UserPromptSubmit hook now uses wrapper scripts consistently

## [3.4.0] - 2026-03-12

### Added
- New `git-memory-issues` skill — GitHub issues and milestones as shared team memory
- Safety improvements: confirmation protocol, `--no-ff` merges, pre-merge checklist, immediate back-merge
- Scout agent onboarding integration
- Alexandria documentation agent design

### Fixed
- Belt regex now catches `git -C` and other flags before `log`/`commit` interception
- Narrowed issue skill trigger to avoid false activations on generic words

## [3.3.0] - 2026-03-12

### Added
- `remember()` commit type for explicit long-term memory capture
- Hierarchical scopes with scope-scout agent for automatic scope grouping in glossary
- Mandatory rule: agents always launch in background
- Hardened stop hook — `context()` commit is now mandatory when closing a session

### Changed
- Skill refactored to consolidate all rules (CLAUDE.md managed block minimized)
- Scope-scout agent renamed to "scout"

## [3.2.0] - 2026-03-12

### Added
- Pretty ANSI output for commit and log wrapper scripts
- PreToolUse hook blocks direct `git commit`/`git log` — forces wrapper scripts
- Boot glossary: session start extracts all decisions and memos from full git history

## [3.1.0] - 2026-03-12

### Added
- Frictionless capture: auto-detect decisions, memos, and context from conversation — commit without asking

### Changed
- CLAUDE.md managed block reduced to minimal pointer; all rules moved into the skill file

## [3.0.0] - 2026-03-11

### Changed
- Complete plugin audit: dead code removed, skills merged into single coherent file
- Dashboard archived (superseded by CLI tools)
- Boot now fetches latest git history before building snapshot
- All version references synced across plugin.json, marketplace.json, and code

### Fixed
- Restored `.claude-plugin/` files accidentally deleted during cleanup
- Install script no longer deletes source files when running inside the plugin's own repository

## [2.2.0] - 2026-03-11

### Added
- Context-aware stop hook with statusline wrapper showing session summary
- Gitto memory oracle agent for querying project memory conversationally
- Silent WIP strategy — WIP commits happen without noisy output

### Fixed
- Stale hooks cleaned during zero-copy migration
- Statusline backup hardened against missing files
- Doctor command now detects stale hook configurations

## [2.1.0] - 2026-03-08

### Added
- Automatic context checkpoint commits at natural pause points
- Auto-upgrade of outdated CLAUDE.md managed blocks on session start

### Changed
- Zero-copy install model: plugin runs directly from Claude Code cache, no files copied to project root
- Upgrade script rewritten for zero-copy model with full test coverage

## [2.0.0] - 2026-03-07

### Added
- SessionStart and UserPromptSubmit hooks for automatic memory boot
- Circuit breaker in Stop hook to prevent infinite loops
- Bootstrap detection in UserPromptSubmit hook for first-run guidance
- Incomplete install detection when `lib/` or `bin/` is missing
- Comprehensive type hints with mypy strict mode
- Monorepo detection refined with Rush/Moon support and scope mapping

### Changed
- Extracted shared `lib/` module: constants, git_helpers, parsing, colors (DRY refactor)
- All CLI scripts migrated from ad-hoc argument parsing to argparse
- Migrated 5 test suites to pytest with shared fixtures (old test files removed)
- Plugin aligned with official Claude Code plugin spec
- All code translated to English (docstrings, comments, headers)
- Marketplace.json added for self-hosting distribution
- Skills updated to use local paths instead of `$CLAUDE_PLUGIN_ROOT`

### Fixed
- Security audit round 2: complete manifest, symlink safety, MEMO_CATEGORIES validation, exit codes, imports
- Security audit round 3: XSS in dashboard, atomic writes, shell injection prevention, tombstone normalization
- Hook settings.json format corrected (flatten nesting, string matchers)
- Dashboard date parsing fixed (all dates were null)
- Stop hook now ignores git-memory runtime files

## [1.1.0-gitmemory] - 2026-03-06

### Added
- Static HTML dashboard for visualizing git memory (`git memory dashboard`)
- Lifecycle scripts: doctor, install, repair, uninstall
- Bootstrap scout: detects project stack, monorepos, and commitlint configuration
- Safe upgrade system with backup, diff review, and migrations
- Integration test matrix covering 10 end-to-end scenarios

### Changed
- Restructured project as Claude Code plugin (v2 architecture)

### Fixed
- Security audit: symlink traversal, uninstall orphans, exit code handling, manifest validation

## [1.0.0] - 2026-03-05

### Added
- Core git-memory system: persistent memory via git commit trailers
- Commit types: `context()`, `decision()`, `memo()` with emoji prefixes
- Memory search protocol with `git fetch` + deep grep before asking the user
- Conversational memory detection from natural language triggers
- Contradiction detection for conflicting decisions and memos
- Drift test validating search relevance and dedup under stress (200 commits, 6 scopes)
- CLI for manual memory queries (`git memory search`, `git memory log`)
- Garbage collector for pruning stale memory entries (`git memory gc`)
- Git hooks: pre-validate and post-validate commit trailers, precompact snapshot

### Changed
- Hooks hardened with restored drift test coverage

### Fixed
- Post-hook safety for delimiter collisions and nested prefix handling
- Partial date validation in form components
