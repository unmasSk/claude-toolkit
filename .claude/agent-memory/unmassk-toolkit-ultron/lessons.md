# Lessons — mistakes I made here, and why they happened

The full chronicle (2026-03 to 2026-08) was distilled on 2026-10-16; the old text stays in the git history of this folder.

- Used `git stash` as a "before" snapshot and ate a concurrent agent's uncommitted work (twice) — the tree is shared; compare against a copy in my scratchpad instead.
- Ran the whole suite (`pytest unmassk-toolkit/tests -q`) after a rule against it, twice — scoped runs on the touched files were already enough, and the full run can collide with other sessions.
- Edited source while a background test run was in flight — the run mixed before/after states with no marker; a background run freezes the tree until it ends.
- Trusted "the contract is red" from the prompt without running it — it had gone green in another session; run the named test first.
- Trusted Dante's list of tests my change would break — two more broke; run the full scope of the contract files, not only the named tests.
- Blamed my change for failures that came from another agent mid-edit on the same file — check the baseline before blaming myself.
- Read `git diff` on a shared file as all mine — it mixed other agents' hunks; only lines I touched since my baseline are mine.
- Chased an Edit "string not found" for 15 calls as a tool bug — the name in the file was Spanish (`_discrepancias`), I typed English.
- Copied a neighbour's try/except and pushed the function over 50 lines without noticing — count lines after borrowing a pattern.
- Wrote a fail-open wrapper inside a helper and called it safe — the cache can hold an older copy that raises before the wrapper runs; guard at the caller.
- Wrote the memory index as paragraphs — every session paid for it; one short phrase per line.
- Ran `rm` in the same batch as a Write that a hook then blocked — the delete went through, the write did not; delete only after the new file is confirmed on disk.
