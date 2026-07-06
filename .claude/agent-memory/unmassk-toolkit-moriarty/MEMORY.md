# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
Target: boot memory freshness multi-machine re-attack round 3/FINAL (issue #49, fix commit d409805 +
regression tests 45ecfd6, diff 82c5ecb..HEAD) -- lib/boot_git_checks.py, lib/boot_memory.py,
lib/git_helpers.py. Real bare-remote + up to 14 clone triangulation in scratchpad (renamed remotes,
two-remote decoys, weird remote names, hand-crafted leading-dash refs, a fully UNRELATED bare repo
for formal Round-Trip Sabotage), real boot hook invocations end-to-end, real hung TCP server, real
concurrent/racing fetches, real `.git/config` hand-editing, real `fsck`/`merge-base`
independent-channel verification throughout.
Verdict: AGUANTA overall on this round's own scope -- all 4 previously-reported lower-tier findings
CONFIRMED CLOSED live: (1) REMOTE_PROVENANCE_LABEL and the MEMORY stamp are now genuinely English
(" [source: remote]"), verified through a real divergence/behind reproduction, no Spanish literal
found anywhere in the feature's code path; (2) the renamed-remote gate now resolves the live remote
name from `@{u}` instead of hardcoded "origin" -- confirmed fetching successfully across simple
rename, two-remotes-with-a-broken-"origin"-decoy, and a remote name containing dots/underscore/
hyphen, and the leading-dash-injection guard (_looks_like_git_option) still blocks a hand-crafted
`-evilremote` AND a hand-crafted leading-dash remote_BRANCH at the new `remote get-url --` call site
(no FETCH_HEAD created, argv-safe against shell-metacharacter remote names too); (3) _crown_replace's
multi-match branch confirmed still dead code with NO live behavior change (true divergence with both
sides crowning the same scope still shows both entries correctly, un-deduped, per design); (4) new
tests/test_boot_freshness_regression.py (11 cases) genuinely exercises all 4 closed findings with
real repos, no mocking, no fabricated fixtures -- not theater. Both ORIGINAL round-1 breaks
(clock-skew, decoupled stamp) re-confirmed fixed live under this round's code. POSIX killpg process-
tree kill re-confirmed under the refactored Windows/POSIX popen_kwargs split. `false`-by-PATH askpass
portability fix confirmed real (old `/bin/false` genuinely absent on this macOS box) but its safety
margin was already fully covered by GIT_TERMINAL_PROMPT=0 either way (no live hang existed before or
after). Windows taskkill /F /T /PID: logic-reviewed only (str(pid) argv-list, no shell=True, no
injection surface) -- untestable, no Windows machine available, explicitly declared as a gap rather
than a trivial-pass claim.
NEW finding (not a regression of this round -- pre-existing since the original issue #49 Task 4
design, discovered only now via a formal Round-Trip Sabotage pass applied to the final state):
resolve_boot_memory()/fetch_memory_ref() never verify that the ref `@{u}` resolves to is
actually a continuation of the SAME project's history -- only that it's a coherent, fetchable
branch-shaped ref. See attack-patterns.md for the full live reproduction (completely unrelated bare
repo, zero shared history confirmed independently, real boot hook output showing a crowned Decision
from a totally different project confidently labeled "MEMORY: remote (fetched 0s ago)" / "[source:
remote]"). Bounded severity (T2): requires local config-level tracking misconfiguration to
trigger (not remotely content-injectable), and the underlying VCS's own default refusal to combine
unrelated histories blocks the worst-case destructive-pull outcome -- but the DISPLAYED info itself
is already wrong and confidently mislabeled as verified. Flagged for Yoda; does not block this
round's own 4-finding closure. See attack-patterns.md / resilience.md for detail.


## Previous attack
Target: boot memory freshness multi-machine re-attack round 2 (issue #49, commit 2fb3663, diff
9990410..HEAD) -- lib/boot_git_checks.py, lib/boot_memory.py, lib/git_helpers.py,
hooks/session-start-boot.py. Real bare-remote + multi-clone triangulation in scratchpad, real boot
hook invocations, real hung TCP server (not mocked), real `.git/config` hand-editing.
Verdict: AGUANTA overall (0 T1 breaks) with 4 lower-tier findings. Both originally-reported breaks
CONFIRMED FIXED under live re-reproduction: (1) clock-skew (future-dated FETCH_HEAD mtime) now
correctly forces a fetch across every boundary tested; (2) decoupled MEMORIA/MEMORY stamp (fetch by
branch name vs read by @{u}) now correctly resolves the SAME upstream ref for both and tells the
truth ("LOCAL -- unverified") when no coherent upstream exists. killpg process-tree kill confirmed
via real 3-level-deep hung process tree + independent `ps` verification. New findings (none T1):
hardcoded "origin" liveness gate silently disables the whole feature for renamed remotes (T2,
pre-existing not introduced this round); REMOTE_PROVENANCE_LABEL is still Spanish contradicting the
docstring's explicit "whole banner is English now" claim (T2, disprovable, demonstrated live);
_crown_replace's multi-match dedup fix is dead code relative to its own stated justification (T3,
_merge_diverged_memory never calls it); zero regression-test coverage exists for either of the 2
fixes this round claims to have made (T2). See attack-patterns.md / resilience.md for detail.

## Previous attack
Target: boot memory freshness multi-machine (issue #49) -- lib/boot_git_checks.py, lib/boot_memory.py,
lib/boot_glossary_cache.py, hooks/session-start-boot.py, bin/git-memory-commit.py (git diff
ca1f6a2..HEAD). Real bare-remote+clone triangulation in scratchpad, real boot hook invocations
(no mocks/fake-git for the confirmed breaks).
Verdict: DEBIL -- 2 confirmed breaks (T1-adjacent, both realistic multi-machine states): (1) future-
dated FETCH_HEAD mtime (clock skew) suppresses the fetch indefinitely while displaying a healthy-
looking "hace 0s" message; (2) broken/stale upstream tracking config (@{u}) makes MEMORIA: remoto
claim remote-verified freshness while resolve_boot_memory() silently falls back to local-only content
-- reproduces the exact issue #49 incident through a path the fix didn't close. Everything else
(hung remote real timeout, huge behind count, true divergence with contradictory content, shallow
clone, detached HEAD, concurrent boots, stress, write-path warn-only, cache backward-compat) held
under real (non-mocked) adversarial conditions. See attack-patterns.md / resilience.md for detail.

## Previous attack
Target: `unmassk-toolkit/lib/git_helpers.py` run_git() encoding="utf-8" seam — formal Round-Trip Sabotage (§34)
Branch: main (working tree, uncommitted)
Date: 2026-07-06
Verdict: seam AGUANTA the sabotage (encoding="utf-8" kwarg genuinely prevents mojibake under forced
PYTHONUTF8=0) but the "real round-trip" test claiming to prove it is a false green on this env (see
attack-patterns.md) — regression protection today survives only via a sibling mock test, T1 test-coverage
deception, does not affect the seam's own verdict.
