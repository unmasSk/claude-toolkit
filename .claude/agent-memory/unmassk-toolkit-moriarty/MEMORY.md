# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
Target: issue #60 (boot MEMORY stamp) v3 re-attack, round 3 (decision 787b698, wip df1bb4f) --
identity model gained remote URL (`git remote get-url`) + schema_version alongside alias/branch,
split into lib/boot_fetch_stamp.py. Real disposable repos, real hook subprocess
(hooks/session-start-boot.py), 2 independent channels (stdout + boot-log-latest.txt). Verdict:
FALLA (T1). Live EXPLOIT: `git remote get-url` falls back to the literal remote NAME
(e.g. "origin") when `remote.<name>.url` is unset/empty -- reachable via one ORDINARY command
(`git remote set-url origin ""`), no adversary needed. `_looks_like_git_option()` only rejects
empty/leading-dash, so this degenerate alias-as-URL passes as "resolved". Confirmed end-to-end:
repoX (real fetch success, url-unset + local `origin/` dir trick) writes a genuine stamp with
`remote_url: "origin"`; repoZ (totally unrelated content/history, ALSO url-unset via the SAME
ordinary command, no local trick needed on this side) + a copied stamp -> false
`MEMORY: remote (synced 0s ago)` on both channels, zero real fetch against repoZ's actual remote.
Reopens exactly the template/backup/dotfiles-sync threat model 787b698 named as v3's reason to
exist. Root: lib/boot_git_checks.py:704-709 `_check_remote_is_live()`. Contrast (HELD): the v2
PoC replayed (real distinct URLs) rejected correctly; URL-variant false positives (trailing
slash/.git dup/case/embedded creds) -- none, literal compare only ever causes harmless extra
fetches; `_read_stamp_age_by_alias_only()` traced live to its one call site, confirmed it can
never feed rate_limited/synced; schema_version v1-legacy/string/null/list -- 0 crashes, always
"absent stamp"; newline+NUL+ANSI crammed into remote_url round-trips safely via JSON escaping,
never reaches any subprocess argv or output surface; 6/6 quick regression re-checks after the
module split (symlink file/dir, 8-way concurrency, corrupt JSON, future mtime, 5MB stress) held.
See attack-patterns.md / resilience.md for full detail.

## Previous attack (v2 round, compact)
Issue #60 v2 re-attack (decision 90d096d, wip eb3e554) -- own-fetch-success-stamp
(.claude/.unmassk/boot-fetch-stamp.json) replacing FETCH_HEAD-mtime. FALLA (T1): stamp bound
identity by LOCAL ALIAS STRINGS only ("origin"/"main"), no URL/repo-identity signal -- a `cp`'d
stamp from an unrelated repo (same common alias) forged `MEMORY: remote (synced 0s ago)`. Led to
v3 (see "Last attack" above). Contrast (HELD): vectors A/B/D, garbage/corrupt/20MB content,
symlink/hard link, future-mtime, 8-way concurrency, dead/removed remote, deleted-stamp-mid-window.

## Previous attack (older rounds, compact)
- Issue #60 v1 relabel (decision ceef426, commit d630e14) -- FALLA, T1 Round-Trip Sabotage: bare FETCH_HEAD-mtime rate-limit rendered false `remote (synced)` both when the boot's OWN failed fetch refreshed FETCH_HEAD and when an unrelated remote's real successful fetch touched it; 96-test suite stayed green throughout. Led directly to v2 (own-stamp mechanism, see "Previous attack (v2 round, compact)" above for its own re-attack result).
- Issue #59 (A2 token-fence infalsifiability, decision feed852) -- FALLA, 2 live T1 EXPLOITs (Unicode Cf invisible-format-char fence bypass in both user-prompt-memory-check.py and precompact-snapshot.py) + 1 T1 structural DECEPTION (nonce placed outside the actual trust boundary). See attack-patterns.md for detail.
- Issue #57 round 2d FIRST pass (structural %h/%at/%n fix) -- DEBIL, 7/7 field-displacement
  sites held, 2 NEW exploits found then (NEL fence-splice, precompact plain-text delimiter
  spoof) -- both re-verified since, see resilience.md for outcome.
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
