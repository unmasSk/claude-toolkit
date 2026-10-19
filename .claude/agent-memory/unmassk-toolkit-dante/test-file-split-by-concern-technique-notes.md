---
name: test-file-split-by-concern-technique-notes
description: How to split an oversized test file (>500 LOC) by concern without losing or changing a test -- line-range splitter, id diff, byte-identical AST check; #95 step 2 layout
metadata:
  type: project
---

Project limit (standards default, no override in memory): 500 LOC per test file, 300 per source file.
Yoda flags any test file over 500 as T2 without a `Waiver:` line.

**Technique (2026-10-19, Yoda's #95 step 2 fix pass, 117 -> 117 tests):**
1. Copy the originals to the scratchpad FIRST (`orig_<name>.py`) -- the splitter reads them, never the live file.
2. Splitter script: compose each new file from 1-indexed LINE RANGES of the original plus a short new
   header/imports; `assert SRC[n].startswith("class X")` on every boundary so a shifted line fails loud.
   No test body is retyped.
3. Shared helpers/fixtures go to a module WITHOUT the `test_` prefix in the same package
   (pattern already used by `gh_graphql_fake.py`); fixtures are imported into each test file with
   `# noqa: F401 (fixture)`. Keep helper names unchanged (underscore names included) so other files'
   imports only change their module. Don't grow conftest.py (already 869 LOC).
4. Whole-file `pytestmark` skip -> `POSIX_ONLY = pytest.mark.skipif(...)` in the helper; each file sets
   `pytestmark = POSIX_ONLY` (same condition, same skips).
5. Prove nothing lost: collect `--collect-only -q` before/after, strip the file part, `diff` the sorted
   `Class::test[param]` lists. Then an AST script: every top-level def/class/assign of the originals must
   exist byte-identical (`ast.get_source_segment`, decorators included) in exactly one new file.
6. No pyflakes/ruff on this machine: a 40-line AST checker for undefined names / unused imports does it.
7. Keep the ORIGINAL filename for one of the parts (no file deletion needed; `rm` is off-limits anyway),
   and update prose that points at a moved test (e.g. "covered in test_X.py").

Layout after the split: boot deadline -> `boot_hook_harness.py` / `boot_hook_gh_stub.py` /
`boot_overrun_tools.py` + tests `_contract` (batched GraphQL), `_launcher`, `_overrun_marker`;
Moriarty step-2 -> `_fix_pass` (boot hook) + `_save_hints` (customs/report hints); presave contract ->
`presave_searched_contract_support.py` + `_contract` + `_customs`; presave fix pass ->
`presave_searched_fix_support.py` + `_fix_pass` (version skew) + `_fix_pass_relaunch`.

**Fence relaunch (remove.py) test technique:** to reach the "pre-check passed but the fence write failed"
path, install a real `commit-msg` hook in tmp_repo/.git/hooks that refuses only messages with
`^Origin: <incident id>` (marker file as setup proof), then remove the hook and obey the printed relaunch.
See `test_remove_fence_relaunch_searched.py`. Related: [[presave-searched-flag-contract-notes]],
[[boot-deadline-hook-timing-contract-notes]].
