# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
Target: issue #60 (boot MEMORY stamp) v2 re-attack (decision 90d096d, wip eb3e554) -- own-
fetch-success-stamp (.claude/.unmassk/boot-fetch-stamp.json) replacing FETCH_HEAD-mtime as the
freshness source. Real disposable repos (bare origins + real clones), real hook subprocess
(hooks/session-start-boot.py), 2 independent read channels (stdout + boot-log-latest.txt), 8-way
real concurrency, 20MB stress payload -- zero manual internal-function mocking. Verdict: FALLA
(T1, Moriarty FALLA Rule -- round-trip check does not go red). Live EXPLOIT: the stamp binds
identity by LOCAL ALIAS STRINGS ("origin"/"main"), never by remote URL or any repo-identity
signal -- a stamp `cp`'d verbatim from an unrelated repo (same, extremely common, alias names)
into a project whose own real origin is unreachable makes the boot claim `MEMORY: remote
(synced 0s ago)` on both channels and skip its own real fetch entirely, no git operation
required to plant it (unlike the v1 bug it replaced). Shipped suite (133 tests) stayed green
throughout. Contrast (correctly HELD): vectors A/B/D re-verified fixed; stamp
garbage/empty/wrong-fields/20MB-malformed content, symlink (file AND parent dir), hard link,
future-mtime skew, 8-way concurrent real boots, detached HEAD/no-upstream/dead-remote/removed-
remote, deleted-stamp-mid-window, and the legit happy-path round-trip all held correctly. See
attack-patterns.md / resilience.md for full detail.

## Previous attack (older rounds, compact)
- Issue #60 v1 relabel (decision ceef426, commit d630e14) -- FALLA, T1 Round-Trip Sabotage: bare FETCH_HEAD-mtime rate-limit rendered false `remote (synced)` both when the boot's OWN failed fetch refreshed FETCH_HEAD and when an unrelated remote's real successful fetch touched it; 96-test suite stayed green throughout. Led directly to v2 (own-stamp mechanism, see "Last attack" above for its own re-attack result).
- Issue #59 (A2 token-fence infalsifiability, decision feed852) -- FALLA, 2 live T1 EXPLOITs (Unicode Cf invisible-format-char fence bypass in both user-prompt-memory-check.py and precompact-snapshot.py) + 1 T1 structural DECEPTION (nonce placed outside the actual trust boundary). See attack-patterns.md for detail.
- Issue #57 round 2d FIRST pass (structural %h/%at/%n fix) -- DEBIL, 7/7 field-displacement
  sites held, 2 NEW exploits found then (NEL fence-splice, precompact plain-text delimiter
  spoof) -- both re-verified this round, see "Last attack" above for outcome.
- Issue #57 log-parsing fix round (post ff538f1) -- FALLA, subject-\x1f field displacement
  broke all 5 downstream sites (recall/gc/doctor x2/bootstrap/precompact); also found
  \x1c/\x1d/\x1e fence-splice gap (predecessor to the NEL gap above) + gc.py evidence-field
  ANSI leak.
- F6 hard-link bypass rejection (issue #53) -- AGUANTA, 8 real PoCs, 0 breaks.
- Issue #55 date-parsing migration -- DEBIL, 3 real breaks (year-10000+ overflow, negative
  "days ago", silent --json date-format change).
- Boot memory freshness multi-machine (issue #49, 3 rounds) -- round1 DEBIL (2 breaks) →
  round2 AGUANTA (0 T1) → round3 AGUANTA (1 new T2 via Round-Trip Sabotage: no shared-history
  check on the tracked ref).
- git_helpers.py encoding seam Round-Trip Sabotage and any rounds older than the above: see
  attack-patterns.md / resilience.md (not reproduced here).
