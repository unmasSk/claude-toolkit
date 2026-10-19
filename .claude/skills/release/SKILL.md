---
name: release
description: Publish a new version of a plugin of this repository (claude-toolkit) and install it on the owner's machine. Use at the session close of this repository, or when the owner says to publish, release or bump a plugin. Only this repository publishes; never use it in another project.
---

# Release — publish a plugin of claude-toolkit

This repository is the one that publishes. The session close of this repository publishes; the generic close-session skill does not, on purpose: there it would publish in every project.

## Before you start

1. **The CHANGELOG is written by Alexandria, never by you.** If `[Unreleased]` lacks what the release ships, send her (merge or close mode) before going on.
2. **The version moves only through `bin/release.py`**, which bumps it and syncs `marketplace.json` in the same commit: a bump without that sync leaves users without the update (R-004). Never edit the version by hand.
3. **You are on `main` with a clean tree.** CI runs only on a push to `main`, and an untracked file blocks the release; session files belong in `.claude/informes/`, outside git.

## Steps

1. Dry run: `python3 bin/release.py <plugin> <version> --dry-run`. Read its output; fix what it names.
2. Release: `python3 bin/release.py <plugin> <version>`. It writes the release commit and pushes it.
3. Find the release's CI run by its commit: `gh run list --commit <release sha>`, then `gh run view <id>` until it finishes.
   - Toolkit CI runs on Ubuntu and Windows when the release touches `unmassk-toolkit/`, `bin/` or `pyproject.toml`; Plugin Tests runs on Ubuntu for `unmassk-3d`, `unmassk-electronics` and `unmassk-trading`.
   - No run for that commit means the release touched no tested path: say so, never read an older run as this release's verdict.
4. Only with the run green, install it yourself — never ask the owner to run anything:
   - `claude plugin marketplace update unmassk-claude-toolkit`
   - `claude plugin update <plugin>@unmassk-claude-toolkit`
   - Check that `~/.claude/plugins/cache/unmassk-claude-toolkit/<plugin>/<version>/` exists. The new version applies from the next session.

## Verify

The release is finished only when its CI run is green on every OS that run covers (R-024).

## If it fails

- `release.py` exit 1: preflight or execution failed before the push. Fix what it names and run it again.
- `release.py` exit 2: the push happened but the post-push check failed. Read its message; do not release again on top. Fix the cause, and if the push itself did not land, `git push` it.
- A red CI run is an incident: open it, fix it, install nothing, and the next release proves the fix.
