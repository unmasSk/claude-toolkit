# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
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

## Previous attack
Target: `unmassk-toolkit/lib/git_helpers.py` + `unmassk-toolkit/lib/_symlink_safe_open.py` (Windows anti-symlink guard, fix-windows-crossplatform)
Date: 2026-07-06
Verdict: DEBIL — stated threat model (git-committed symlink) holds; hard-link bypass demonstrated (adjacent threat, not this fix's regression); 1 non-OSError escape (UnicodeEncodeError) confirmed pre-existing, not introduced by this patch.
