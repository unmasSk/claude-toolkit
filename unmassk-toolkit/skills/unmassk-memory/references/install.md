# When `gitmem` is not found

**If the bare command is not found, that is not a reason to reach for a long path — it is the signal that this project was never set up.** Run the installer once — discovered fresh in the same breath it runs, never a path pasted once and kept, since a kept path carries a version number and goes stale the day the toolkit updates:

```bash
SKILL_DIR=$(find ~/.claude/plugins/cache -maxdepth 5 -type d -path '*/unmassk-toolkit/*/skills/unmassk-memory' 2>/dev/null | while read -r d; do [ -e "${d%/skills/*}/.orphaned_at" ] || echo "$d"; done | sort -V | tail -1)
python3 "$SKILL_DIR/../../bin/git-memory-install.py" --auto
```

If that discovery comes back empty, the toolkit is running from a checkout rather than an
install: use the absolute path from the `Base directory for this skill:` line printed when this
skill loaded, and write it into the command literally.

Then use `gitmem`. It puts the launcher on the PATH and, in the same pass, seeds the eight indexes and writes the project's config — the things whose absence makes the first note bounce.

Reaching for the cache path instead leaves the project half-set-up forever: the command appears to work, so nobody notices there is no config and no indexes, and the next session pays for it again.
