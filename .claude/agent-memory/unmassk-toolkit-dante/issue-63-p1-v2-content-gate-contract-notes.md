---
name: issue-63-p1-v2-content-gate-contract-notes
description: issue #63 P1 v2 acceptance contract (decision 2d56444) — content-based CLAUDE.md gate replacing version-trust after Moriarty's 3 T1 PoCs; monkeypatch-in-subprocess producer sabotage (no chmod), same-file conflict with v1's test_crew_manifest_version_gate.py
metadata:
  type: project
---

New file: `unmassk-toolkit/tests/test_crew_content_gate_v2.py` (4 tests, all
RED confirmed for the right reason except the control). Contract: decision
2d56444 (git show 2d56444) — the P1 gate must verify CLAUDE.md CONTENT, not
manifest.json's version string. Moriarty's 3 T1 PoCs (issue #63 "Last attack"
in `.claude/agent-memory/unmassk-toolkit-moriarty/MEMORY.md`) map 1:1 to
tests 1-3; test 4 is the "don't lose the optimization" control.

**Reproduced RED, confirmed live**: 3/4 fail with the exact same literal
buggy string as the failure evidence — `"[crew] manifest.version matches
VERSION, skipping CLAUDE.md check"` appears in stdout while CLAUDE.md content
is still stale/poisoned/absent. Test 4 (canonical content + matching
manifest → skip) is GREEN today, as the contract explicitly allows ("puede
nacer verde o rojo según implementación") — v1's version-only check happens
to coincide with v2 in the non-adversarial case.

**Technique: monkeypatch-in-subprocess producer sabotage, NOT chmod.**
Test 1 (Moriarty PoC 1: producer write failure + manifest still stamped)
needed to make `lib/install_apply.py::apply_plan()` genuinely fail
`_update_claude_md()`'s write while `_create_manifest()` still succeeds —
without chmod (established project rule, see
`test_boot_output.py::_run_boot_with_failing_log_write()` and this project's
own conventions doc: chmod-based write-failure simulation only blocks the
OWNER's writes on POSIX and does nothing on Windows). Wrote
`_run_sabotaged_producer(repo)`: an inline `python3 -c` script, run as a REAL
subprocess (own process, own sys.modules — matches project convention for
"canal real"), that does a plain `import install_apply` (no hyphens, directly
importable), captures the real `install_apply.open_no_follow_symlink`, then
overwrites the module attribute with a wrapper that raises `PermissionError`
ONLY when `mode == "w"` and `os.path.basename(path) == "CLAUDE.md"` —
falling through to the real function for every other call (including
manifest.json's own `open_no_follow_symlink(..., reject_hardlinks=True)`
write, a different basename, untouched). Then calls `install_apply.apply_plan()`
directly with a hand-built 2-action plan (`update_claude_md`,
`create_manifest` — the two actions that always run regardless of repo
state, confirmed by reading `bin/git-memory-install.py::create_plan()`).
This reproduces Moriarty's exact PoC 1 using REAL production functions
(apply_plan/_update_claude_md/_create_manifest), not a fabricated stand-in —
`apply_plan()`'s per-action try/except appends to `errors[]` and does NOT
abort the loop, so `_create_manifest()` genuinely runs right after and
stamps `manifest.version == VERSION` even though the CLAUDE.md write failed.
Verified live via 3 sanity/anti-vacuity asserts before ever running the gate
under test: `errors` non-empty and attributed to `update_claude_md`, CLAUDE.md
content byte-identical to pre-sabotage (write genuinely failed), manifest
version genuinely == VERSION despite the failure.

**Anti-vacuity distinguishing "regenerated" from "silently skipped":** test 1's
final assertion branches on the OBSERVED outcome rather than asserting a single
fixed shape (the task brief explicitly allows either outcome — regenerate OR
report failure, never silent skip): `if STALE_MARKER not in content_after:`
assert the content is now genuinely canonical via `any_block_outdated()`
(proves "regenerated" means correctly regenerated, not just "marker
happened to vanish"); `else:` assert none of `"skip"/"up to date"/"matches"`
appear anywhere in stdout+stderr combined (proves silent-success language is
never used while content is still wrong). Test 4 (the happy-path control)
is the other half of this distinguishing pair — together they prove the
oracle isn't just always-failing or always-passing.

**Known same-suite conflict, flagged not silently fixed:** the EXISTING
`test_crew_manifest_version_gate.py::TestManifestVersionMatchSkipsRewrite`
asserts the OPPOSITE of this file's Test 2 for a near-identical fixture
shape (manifest version match + stale/altered first block → that file
expects SKIP, this file's poisoned-block test expects REGENERATE). This is
not a mistake in either file — it's the literal v1→v2 contract reversal
decision 2d56444 describes. Once Ultron implements the v2 content-based
gate, `test_crew_manifest_version_gate.py`'s `TestManifestVersionMatchSkipsRewrite`
will need to be retired or rewritten in the SAME PR, or the two test files
will permanently disagree post-fix. Left untouched deliberately (out of
this task's "SOLO tests para el contrato nuevo" scope; not my call to retire
another file's contract without the orchestrator's sign-off) — reported
explicitly to the requester instead of silently resolving it.

**Explicitly excluded from this file's scope (per task brief):** hardening
the PRODUCER itself (`apply_plan()` should arguably not stamp the manifest
when `update_claude_md` failed; `lib/upgrade_check.py::
trigger_auto_upgrade_if_needed()` discards the installer subprocess's
returncode/stdout/stderr entirely). Test 1 exercises this real bug as a
documented PRECONDITION to reach the divergent state, but asserts nothing
about fixing it — a second contract for that front was explicitly deferred
to a separate task.

Verification: file alone 3 failed / 1 passed (all for the exact expected
literal-string reason, shown in captured output); full suite run pending
at time of writing — see [issue-63-boot-simplification-contract-notes](issue-63-boot-simplification-contract-notes.md)
(same file's earlier P1 v1 acceptance contract this supersedes) and
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)
(monkeypatch-not-chmod convention this reuses, `_run_boot_with_failing_log_write()`
precedent).
