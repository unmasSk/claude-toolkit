---
name: cicd-workflows
description: GitHub Actions workflow findings — .github/workflows/*.yml (toolkit-ci, plugin-tests, chatroom-ci), first CI/CD audit round 2026-08-06
metadata:
  type: project
---

## First CI/CD audit — 2026-08-06, three workflows, no actionlint/act available in this environment

`actionlint`/`act` are not installed in this environment (`which actionlint`/`which act` both empty). Validated all three `.github/workflows/*.yml` by hand (full read + cross-referencing every `run:`/`working-directory:` path against disk). No prior gitmem zone memory existed for any of these three files or "workflows"/"security"/"antipattern" generically — this entry is the baseline going forward.

**T1 — `chatroom-ci.yml` gives false green for the frontend.** Both jobs (`typecheck`, `test`) only touch `chatroom/apps/backend`. `chatroom/apps/frontend` has its own `build` (`tsc && vite build`), `test` (`vitest run`), `lint` scripts and real test files (`apps/frontend/src/test/**/*.test.{ts,tsx}`, confirmed 5+ files) — none run in CI. `chatroom/package.json`'s own `check-all` script documents the intended full set (`build && lint && format:check && test:backend && test:frontend`) — CI implements only `test:backend`-equivalent + a typecheck. A PR that breaks the frontend merges green. Check pattern: whenever reviewing a CI workflow for a JS/TS monorepo, diff the root `package.json`'s own aggregate script (e.g. `check-all`/`ci`) against what the workflow actually runs — the aggregate script is usually the intended contract, and the workflow silently implementing a subset is the classic false-green shape.

**T2 recurring across all three workflows found in this round:**
- No `permissions:` block anywhere (toolkit-ci, plugin-tests, chatroom-ci) — GITHUB_TOKEN inherits repo/org default instead of least-privilege `contents: read`. None of the three jobs need more than read.
- `chatroom-ci.yml` has no `timeout-minutes` on either job (toolkit-ci/plugin-tests do: 20/25 min). Default GH timeout is 360 min — a hang burns 6h silently.
- `oven-sh/setup-bun@v2` (third-party action) pinned to a mutable major tag, not SHA — higher supply-chain risk than official `actions/*` at a major tag (which the project's own skill reference calls "acceptable").
- `pip install pytest pyyaml` (toolkit-ci.yml:35) and `pip install pytest pyyaml numpy trimesh manifold3d pyserial cadquery` (plugin-tests.yml:33) — zero version pins. Under this project's own "system against itself" threat model (see project CLAUDE.md), this is a real self-harm risk: an upstream release can break CI with zero code change on this side.
- `bun install` (chatroom-ci.yml, both jobs) without `--frozen-lockfile` despite a committed `chatroom/bun.lock` — install can silently diverge from the committed lockfile.

**T3:** `actions/checkout@v5`/`actions/setup-python@v5` one major behind the skill's own recommended v6 (not deprecated, just outdated — no Dependabot config present to catch this automatically). `chatroom-ci.yml`'s `push: branches: ["**"]` + `pull_request: branches: [main]` combo double-runs CI for same-repo PRs with no `concurrency:` cancel-in-progress group (absent in all three files). No pip/bun caching anywhere (perf only).

Check pattern for future CI/CD reviews in this repo: (1) always cross-check a JS/TS monorepo workflow against the root package.json's own aggregate/check-all script for coverage gaps — this is where "verde en falso" actually lives, not in syntax errors; (2) always check whether third-party (non-`actions/*`, non-`docker/*`) actions are pinned to SHA vs a mutable tag, since the project profile's "no external attacker" stance is about the toolkit's own code, not about supply-chain integrity of third-party Actions pulled into CI runs with a token.
