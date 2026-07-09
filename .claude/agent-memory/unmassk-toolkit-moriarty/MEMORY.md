# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
Target: issue #57 FINAL re-validation round -- structural parsing fix (decision 0682e75,
commit 566eb88: structured fields %h/%at first, %n real-newline subject/body split, replacing
the whack-a-mole per-field maxsplit reordering). Repo relocated to unmassk-toolkit/ subdir
this round (4-plugin split). Same 7 sites re-attacked: lib/recall.py, bin/git-memory-gc.py,
bin/git-memory-doctor.py (x2 functions), lib/bootstrap_commits.py, hooks/precompact-snapshot.py,
lib/boot_memory.py.extract_memory(). Real disposable repos in scratchpad, real hostile
`git commit -m $'...'` payloads with literal x1f/x1e/U+2028/U+2029/U+0085/CR bytes, real
production functions called directly, independent-channel verification via `git cat-file`/
`git log --pretty=format:...` queried separately from the code under test throughout.
Verdict: DEBIL. The subject-x1f field-displacement class this round explicitly set out to
close IS genuinely closed at all 7 sites -- confirmed live, 7/7 held, including the
bootstrap_commits.py dual-git-log-call sha/author correlation (x1f in %an), Unicode
line-separator bytes (U+2028/U+0085/U+2029/CR) in the subject, and a forced short-hash
collision scenario (core.abbrev=4, 1200 commits -- git self-heals %h length, unreachable).
lib/boot_git_checks.py's get_timeline()/get_last_context_time() were re-attacked too (never
migrated to the new pattern) but this is a pre-existing, ALREADY-KNOWN, ALREADY-TESTED
[GUARD] site (tests/test_control_byte_injection.py Sites 7-8) -- re-confirmed live it
degrades safely to "unknown", not a new gap. TWO NEW confirmed EXPLOITs found this round,
both in the canonical `sanitize_trailer_value()` used across all consumers: (1) U+0085 (NEL)
is missing from the stripped-byte set (which DOES cover U+2028/U+2029/x1c/x1d/x1e) -- splicing
it inside the literal `</memory-data>` fence tag defeats the fence-splice defense the PRIOR
round explicitly added for x1c/x1d/x1e, reproduced end-to-end via recall_relevant() +
hooks/user-prompt-memory-check.py's real wrapping logic, confirmed reachable through ordinary
usage (a short, innocent scope-prefix filter like "i"); (2) hooks/precompact-snapshot.py uses
its OWN plain-ASCII delimiter scheme ("=== END SNAPSHOT ===") that the shared sanitizer was
never hardened against -- a plain-text Blocker/Memo/Decision/Next/Remember value containing
that literal string (zero control bytes needed) spoofs a premature end-of-snapshot marker
followed by attacker text in the real context Claude receives right after PreCompact;
tests/test_drift.py's existing structural checks would not catch this (containment-only
assertions, not uniqueness). Also confirmed fixed: gc.py's previously-flagged evidence-field
ANSI-leak bug (SEC-MED-09-adjacent). DECEPTION (T1): decision commit 0682e75/45cba61's "closes
the whole class" / "no LLM-facing injection survives" framing is disproven by the 2 live
exploits above -- the SPECIFIC class named (subject-x1f field displacement) is genuinely
closed, but the broader DoD claim is not. See attack-patterns.md for the NEL/marker-spoof
patterns in full detail; resilience.md for the 7-site re-confirmation and the
boot_git_checks.py [GUARD] re-verification.

## Previous attack
Target: issue #57 log-parsing fix re-validation round (post-remediation, commit ff538f1) --
lib/recall.py, bin/git-memory-gc.py, bin/git-memory-doctor.py, lib/bootstrap_commits.py, plus
hooks/precompact-snapshot.py (checked as the fix's own held-up "reference" site) and
lib/parsing.py:sanitize_trailer_value(). Real disposable repos in scratchpad, real hostile
`git commit -m $'...'` payloads with literal \x1f/\x1e/\x1b/\x7f/\x1c/\x1d bytes, real
production functions called directly (never mocked), independent-channel verification via
`git cat-file`/`git log --pretty=format:%at`/`%b` queried separately from the code under test.
Verdict: FALLA. All 5 originally-reported breaks (a stray \x1f in the commit BODY before a
real trailer) are CONFIRMED FIXED live: HOSTILE-MEMO-B, HOSTILE-BLOCKER-C (aged 90 days)
survive intact through recall.py/gc.py/doctor.py with correct date/scope/trailers; -z's NUL
record boundary holds even under a body saturated with 300x \x1e\x1f (no bleed into
neighboring commits); the empty-body/body-only-separators .strip() edge case is handled
correctly (no parts[] index corruption). BUT the reorder-%b-last fix only protects the LAST
field -- %s (subject) sits in a MIDDLE position in every format string, and a commit SUBJECT
carrying one stray \x1f (trivial: `git commit -m $'type(x): subject\x1fjunk'`) desyncs every
downstream field the identical way the original bug did: reproduced live across ALL FIVE sites
sharing this pattern -- recall.py._scan_commits (real Decision silently lost), gc.py.scan_commits
+find_stale_items (date->None, real aged Blocker invisible), doctor.py.check_hook_execution
(undercount, confirmed exact -2 over 12 commits), doctor.py.check_gc_status (a real,
fsck-clean, 100-day-old Blocker completely invisible), bootstrap_commits.py.scan_recent_commits
(date/author swapped + a phantom "author" entry -- literally a date string -- pollutes the
contributor-count stat fed to `git memory bootstrap --json`), AND hooks/precompact-snapshot.py
(the exact file decision commit 45cba61 calls "la referencia a calcar" is equally vulnerable).
Two more confirmed EXPLOITs: (1) sanitize_trailer_value() strips \x1b/\x7f/literal
`</memory-data>` but not \x1c/\x1d/\x1e -- splicing one of these invisible bytes INSIDE the
literal fence-tag text (`</memory-data\x1e>`) defeats the regex while leaving every
human-visible tag character intact, full end-to-end PoC reproduced via recall_relevant() +
the exact wrapping logic from hooks/user-prompt-memory-check.py, producing what visually reads
as a forged early `</memory-data>` close followed by attacker-controlled "SYSTEM:" text; (2)
gc.py's `find_stale_items()` sanitizes `c["text"]` but never `c["evidence"]` (built raw from
`sha + " " + subject`), so a hostile ANSI byte in a resolution commit's subject reaches
`print_candidates()`'s real stdout unescaped, confirmed via captured output. DECEPTION (T1):
decision commit 45cba61 explicitly frames the round as "closing the whole class, not just the
instance, so #55->#57 doesn't repeat" -- the live PoCs above prove the class was only partially
closed. RACE declared N/A (all audited functions are stateless read-only git-log scans, no
shared mutable state in scope). See attack-patterns.md for the field-displacement/fence-splice/
evidence-leak patterns in full detail.

## Previous attack (older rounds, compact)
- F6 hard-link bypass rejection (issue #53, git_helpers.py/_symlink_safe_open.py) --
  AGUANTA, 8 real PoCs (TOCTOU race, 500-iter thread race, real Windows hard-link
  sabotage w/ certutil independent verification, 2000-iter handle-leak check, append
  mode, nlink=3). 0 breaks.
- Issue #55 date-parsing migration (%aI->%at, date_parsing.py) -- DEBIL, 3 real breaks:
  year-10000+ overflow date makes a Blocker permanently invisible to gc/doctor with zero
  trace; future-dated commit produces a negative "days ago" in doctor; bootstrap_commits.py's
  %aI->%at swap silently changed the --json "date" field's format with no consumer-side
  adaptation (T2 deception on the test suite's own narrower justification).
- Boot memory freshness multi-machine, issue #49, 3 rounds -- round 1 DEBIL (2 real breaks:
  clock-skew suppresses fetch indefinitely while showing "hace 0s"; broken @{u} tracking
  makes MEMORIA: remoto claim verified freshness while silently falling back local-only) ->
  round 2 AGUANTA (0 T1, both breaks confirmed fixed; 4 lower-tier T2/T3 findings: hardcoded
  "origin" gate, still-Spanish label, dead-code dedup fix, no regression tests) -> round 3
  AGUANTA (all 4 round-2 findings confirmed closed; 1 NEW T2 found via formal Round-Trip
  Sabotage: resolve_boot_memory() never verifies the tracked ref shares real history with
  the project, confirmed via a totally unrelated bare repo producing a confidently-labeled
  but wrong "MEMORY: remote (fetched 0s ago)" banner).
- git_helpers.py encoding seam Round-Trip Sabotage (2026-07-06) and any rounds older than
  the above: see attack-patterns.md / resilience.md for full detail (not reproduced here).
