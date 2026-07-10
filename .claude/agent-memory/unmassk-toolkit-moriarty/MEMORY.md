# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
Target: issue #60 (boot MEMORY stamp relabel, decision ceef426, commit d630e14) Round-Trip
Sabotage (mandatory sect. 34). Real disposable repos in scratchpad (bare origin + bare unrelated
remote + real clones), real hardened-fetch subprocess via `git_helpers.run_git`, real
`hooks/session-start-boot.py` invoked twice in sequence as a subprocess, 2 independent read
channels (stdout banner + persisted `boot-log-latest.txt`), zero manual FETCH_HEAD tampering in
the winning PoCs. Verdict: FALLA (T1, Moriarty FALLA Rule -- round-trip check does not go red
under sabotage). The relabel's `rate_limited` -> `MEMORY: remote (synced {age} ago)`
(boot_git_checks.py:814-816) renders on bare FETCH_HEAD-mtime-age alone, no same-boot fetch exit
code required -- and TWO fully realistic, zero-attacker scenarios make it lie:
(1) origin unreachable from the start; boot #1 honestly says LOCAL/unverified, but its own
FAILED fetch attempt truncates+refreshes FETCH_HEAD as a side effect; boot #2 seconds later,
origin still dead, renders `MEMORY: remote (synced Ns ago)` -- no sync ever occurred.
(2) origin never fetched even once (alive, untouched); a real successful `git fetch` of a
totally unrelated second remote (simulating an IDE mirror/fork auto-fetch) touches FETCH_HEAD;
the next boot renders the same false "remote (synced)" claim.
Existing shipped test suite (96 tests, test_boot_freshness.py + _hardening.py) passes 100% green
with both live breaks present -- confirmed gap: every hardening test's "first boot" is a
genuinely SUCCESSFUL fetch before the remote breaks; none exercises a first boot whose OWN fetch
attempt fails, then a second boot in-window. Contrast (correctly HELD, not a break): real
successful fetch first, remote breaks after, second boot in-window -- "synced" is honest there,
matches the shipped `TestRateLimitedStampSurvivesRemoteBreakage` tests exactly. Clock skew
(future FETCH_HEAD mtime) and `history_related=False` short-circuit both verified unaffected/
still correct. See attack-patterns.md for full mechanism + PoC detail.

## Previous attack (older rounds, compact)
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
