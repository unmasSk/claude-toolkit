# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
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
