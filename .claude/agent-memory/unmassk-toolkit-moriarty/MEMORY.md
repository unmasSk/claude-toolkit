# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
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
