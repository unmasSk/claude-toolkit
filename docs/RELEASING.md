# How to release a plugin

This guide walks through publishing a new version of a plugin in this marketplace repo
using `bin/release.py`.

## Precondition: fill the CHANGELOG

The release script **aborts** if `## [Unreleased]` in the root `CHANGELOG.md` is empty
(only headers like `### Added` without entries count as empty). Fill it with the changes
that will ship in this release before running anything.

## Precondition: validate the plugin (mandatory for a new plugin)

Before releasing — and **always for a brand-new plugin** — run the
`plugin-dev:plugin-validator` agent on the plugin directory and get a **PASS**. Ask
Claude to "validate the plugin `<name>`" (it spawns the validator agent). It checks the
manifest JSON and required fields, kebab-case name, semver, auto-discovery wiring, each
`SKILL.md` frontmatter, that **every `references/*.md` cited in a skill actually exists**
(the classic new-plugin footgun is a dangling reference or a file that never got written),
README/LICENSE presence, no hardcoded secrets, and that `plugin.json`'s version matches the
root `marketplace.json` entry. Fix every critical issue before `bin/release.py`. For a new
plugin, also confirm the plugin is **registered** in the root `.claude-plugin/marketplace.json`
and listed in the root `README.md` install block + plugin table.

## Precondition: if the plugin ships scripts, three things the validator does not check

Learned the expensive way with `unmassk-trading` (two patch releases in one night, four cold walks of the skill by a Claude with an empty project). A `SKILL.md` whose bash blocks look right can still fail on every command the first time a real user runs it.

- **`${CLAUDE_PLUGIN_ROOT}` is empty in the Bash tool** — it is only substituted in `hooks.json` entries (R-019, which retired R-018 for prescribing exactly this). A bare relative path is just as broken: a skill runs with the working directory set to the *user's* project. What does arrive is the `Base directory for this skill:` line printed when the skill loads, so each block must resolve the skill directory itself.
- **A shell variable does not survive from one Bash call to the next** — every call is its own shell. Each block has to be self-contained: resolve the path in the same call that uses it, and say so, or someone will copy it line by line.
- **Scripts that default their output to the current directory will write into whatever repository the user is standing in.** Pass `--output-dir`/`--state-dir` explicitly in every documented block, and add the default names to the root `.gitignore` as a backstop.

And give the plugin **its own CI job** if its test suite has dependencies of its own: sharing a job means one plugin's broken pin hides another plugin's result. The `maker-plugins` job sat broken and unnoticed for three weeks that way, because a path filter also kept it from ever running (M-133).

## Step 1 — dry run

Always run `--dry-run` first. It prints the full plan without touching any file:

```bash
python3 bin/release.py <plugin> <new-version> --dry-run
```

Example:

```bash
python3 bin/release.py unmassk-seo 1.1.0 --dry-run
```

Expected output:

```
[DRY-RUN] Release plan para unmassk-seo v1.1.0
  1. Bump: bin/bump-version.py unmassk-seo 1.1.0
     - unmassk-seo/.claude-plugin/plugin.json
     - .claude-plugin/marketplace.json
  2. Promover CHANGELOG: ## [Unreleased] -> ## [1.1.0] - 2026-06-09
     - CHANGELOG.md
  3. Stage: solo los 3 ficheros anteriores
  4. Commit + push vía el generador de memoria (notes.write_work)
  5. Verify: versiones en remoto origin/main
[DRY-RUN] Sin cambios aplicados.
```

## Step 2 — real run

```bash
python3 bin/release.py <plugin> <new-version>
```

## What the script does (in order)

1. **Pre-flight** — validates all conditions before mutating anything:
   - Plugin name is valid (lowercase, alphanumeric, hyphens)
   - Version is valid semver (no leading zeros: `1.04.0` is rejected)
   - Version is strictly greater than the current version (`1.4.0` > `1.4.0-rc1`)
   - Working tree is clean (or `--allow-dirty` is passed)
   - Current branch has an upstream configured
   - Local branch is not behind the remote (`git fetch` + comparison)
   - Plugin exists in `marketplace.json` and its `plugin.json` is present
   - `## [Unreleased]` exists, is unique, is the first version section, and has real content

2. **Bump** — calls `bin/bump-version.py` to write the new version into
   `<plugin>/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.

3. **Promote changelog** — renames `## [Unreleased]` to `## [<version>] - <date>` and
   inserts a fresh empty `## [Unreleased]` above it.

4. **Stage** — runs `git add` on exactly the three files: `plugin.json`, `marketplace.json`,
   `CHANGELOG.md`. No other staged or unstaged changes are touched.

5. **Commit + push** — creates the commit by calling `notes.write_work()`
   (`unmassk-toolkit/lib/memory/notes_commit.py`) directly in-process, not through the
   `gitmem` CLI: it scopes the commit to exactly the three release files via a git
   pathspec (`git commit -- <paths>`), then runs `git push`. This is deliberate, not a
   shortcut — `write_work()` exists specifically so publishing can commit a handful of
   files without dragging in unrelated half-finished changes elsewhere in the tree.

   > **This is the one commit in the whole session that is allowed to trigger CI**
   > (D-070, 2026-08-26). `gitmem work` and `gitmem wip` add `[skip ci]` on its own
   > line to every commit they create — GitHub Actions honors that marker natively —
   > so intermediate work never fires a run. This release commit never carries it,
   > by design: the release is the one point that verifies everything accumulated
   > since the last one. The marker lives in `unmassk-toolkit/lib/memory/ci.py`, with
   > a regression test guarding that it can never migrate into `write_work()` itself.

   > **The release commit carries no business trailers.** Its message is just the
   > headline (`release <plugin> v<version>`) — no `Why:`, `Description:`, `Keys:`,
   > or `Co-Authored-By:`. If you ever hand-write a *memory note* commit elsewhere in
   > this repo (not a release), remember `parse_trailers()` (`unmassk-toolkit/lib/parsing.py`)
   > reads trailers bottom-up and stops at the first blank or non-trailer line — a
   > trailing `Co-Authored-By:` after the business trailers hides all of them. That
   > footgun doesn't apply here: there's nothing to reorder in a release commit.

6. **Verify** — checks two things:
   - The local commit is on `origin/<branch>` (push succeeded)
   - `marketplace.json` and `plugin.json` both show the new version and agree with each other

   On success: `Release verificado. '/plugin update' verá ahora <plugin> v<version> en origin/<branch>.`

## Flags

| Flag | Effect |
|---|---|
| `--dry-run` | Print the plan, make no changes. Always use first. |
| `--allow-dirty` | Skip the clean-tree check. Only the 3 release files enter the commit regardless; other dirty files stay in the working tree. |

## Version rules

- Semver strict: `MAJOR.MINOR.PATCH` — no leading zeros (`1.04.0` is invalid)
- New version must be strictly greater than the current one
- A final release is greater than its pre-release: `1.4.0` > `1.4.0-rc1`

## If something fails mid-release

The script is fail-closed at pre-flight: no files are touched until all checks pass.

If the script fails **after** bumping the version and promoting the changelog but
**before** the commit: all three release files are already modified on disk (the bump
touches `<plugin>/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
before the changelog is even promoted), so revert all three, not just the changelog:

```bash
git checkout -- <plugin>/.claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md
```

If the commit was created locally but `git push` failed, the commit exists and is
recoverable. Run:

```bash
git push
```

The verify step will then confirm the commit reached the remote.

## First-use checklist

- [ ] `## [Unreleased]` has real entries (not just headers)
- [ ] `plugin-dev:plugin-validator` returns **PASS** on the plugin (mandatory for a new plugin)
- [ ] New plugin only: registered in root `marketplace.json` + listed in root `README.md`
- [ ] Working tree is clean (`git status` shows nothing, or `--allow-dirty` is intentional)
- [ ] Branch has upstream (`git push -u origin <branch>` if needed)
- [ ] Branch is up to date with remote (`git pull` if needed)
- [ ] Version is strictly greater than current (`python3 bin/release.py <plugin> <new-version> --dry-run` to confirm)
- [ ] Dry run output looks correct
- [ ] Run for real, confirm `Release verificado.` message
