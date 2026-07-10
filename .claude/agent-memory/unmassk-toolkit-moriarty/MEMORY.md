# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
Target: issue #59 (A2 token-fence infalsifiability, decision feed852) validation. Real
disposable repos in scratchpad, real `git commit -F <bytes-file>` hostile payloads, real
production functions called directly (sanitize_trailer_value, scan_trailers_memory,
recall_relevant, extract_memory_from_log/format_snapshot), real hooks/user-prompt-memory-check.py
AND hooks/precompact-snapshot.py invoked as subprocesses with raw stdout byte inspection,
independent-channel verification via `git cat-file -p`/`git log --pretty=%B` throughout.
Verdict: FALLA. 2 live T1 EXPLOITs + 1 T1 structural DECEPTION, all in the code this issue
shipped:
(1) A brand-new class (not another missing byte): Unicode invisible "format" characters
(Cf category -- ZWSP U+200B, ZWJ U+200D, WORD JOINER U+2060, BOM U+FEFF, SOFT HYPHEN U+00AD,
+10 more, 15 tested, ALL survive) defeat sanitize_trailer_value()'s fence regex AND its `\s*`
structural invariant entirely (neither the char-class substitution nor `\s` covers Cf).
`</memory-data` + U+200B + `>` survives 100% byte-intact through the real
recall_relevant() -> hooks/user-prompt-memory-check.py pipeline, renders visually identical to
the real closing tag, `stdout.count("</memory-data>") == 1` stays true throughout.
(2) SAME root cause, second live consumer: hooks/precompact-snapshot.py's
`_neutralize_snapshot_delimiters()` (naive str.replace, even more brittle) -- confirmed live via
its own real subprocess with a U+200B-spliced `=== END SNAPSHOT ===`.
(3) DECEPTION (T1, structural): the A2 token-fence nonce (`secrets.token_hex(8)`) is placed in
the LABEL text OUTSIDE the actual `<memory-data>`/`</memory-data>` tags and `=== ... ===`
delimiters (Ultron's own commit flagged this as "desviacion nonce por revisar") -- the real
trust boundary stays 100% static/predictable across invocations (proven: isolating just the
`<memory-data>...</memory-data>` substring across 3 real runs shows it byte-identical despite
full stdout differing), directly contradicting decision feed852's stated purpose ("a delimiter
the commit cannot guess or reproduce cannot forge the output"). The existing regression test
passes only because it checks the WHOLE stdout, not the isolated fence.
Confirmed HELD: CR/\r round-trip transport fix (SEC-CRIT-16) in both git_helpers.run_git() and
bin/git-memory-log.py, verified via real `git cat-file -p` ground truth; ReDoS caps (4096 in
_strip_generic_tags, LOW-17's `[^>]*$`, sanitize_trailer_value) all sub-second on multi-million-
char pathological input; LOW-17's own designed \x1c/\x1d/\x1e scenario genuinely closed;
10-way concurrency on the real hook, no corruption. Also found (T3/collateral, not security):
legitimate Decision/Memo text documenting the fence's own literal tag names gets silently
corrupted/neutralized by the same defenses, in both consumers.
See attack-patterns.md for full PoC detail, resilience.md for the held cases.

## Previous attack (older rounds, compact)
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
