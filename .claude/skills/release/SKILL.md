---
name: release
description: Publish a new version of a plugin of this repository (claude-toolkit) and install it on the owner's machine. Use at the session close of this repository, or when the owner says to publish, release or bump a plugin. Only this repository publishes; never use it in another project.
---

# Release — publish a plugin of claude-toolkit

This repository is the one that publishes. The session close of this repository publishes; the generic close-session skill does not, on purpose: there it would publish in every project.

## Before you start

1. **The CHANGELOG is written by Alexandria, never by you.** If `[Unreleased]` lacks what the release ships, send her (merge or close mode) before going on.
2. **Every change bumps the version and syncs `marketplace.json`** (R-004). `bin/release.py` does both; never edit the version by hand.
3. **The working tree is clean.** An untracked file blocks the release; session files belong in `.claude/informes/`, outside git.

## Steps

1. Dry run: `python3 bin/release.py <plugin> <version> --dry-run`. Read its output; fix what it names.
2. Release: `python3 bin/release.py <plugin> <version>`. It writes the release commit and pushes. It is the only commit that runs CI: `gitmem work` and `gitmem wip` add `[skip ci]` to every working commit (D-070).
3. Install it yourself — never ask the owner to run anything:
   - `claude plugin marketplace update unmassk-claude-toolkit`
   - `claude plugin update unmassk-toolkit@unmassk-claude-toolkit` (the plugin you released)
   - Check that `~/.claude/plugins/cache/unmassk-claude-toolkit/<plugin>/<version>/` exists. The new version applies from the next session.
4. Wait for the release CI: `gh run list --limit 1`, then `gh run view <id>`.

## Verify

The release is finished only when its CI run is green on every OS (R-024). A red run is an incident: open it, fix it, and the next release proves the fix.
