# Moriarty — Memory Index

## Topic files
- [attack-patterns.md](./attack-patterns.md) — Patterns that worked on this codebase
- [resilience.md](./resilience.md) — Attacks that held

## Last attack
Target: F6 hard-link bypass rejection, issue #53 -- lib/git_helpers.py:open_no_follow_symlink()
and lib/_symlink_safe_open.py:open_no_follow_symlink_fallback() (twins), new opt-in
`reject_hardlinks=True` param + st_nlink>1 post-open fstat(fd) check, wired into 3 real call
sites: boot_glossary_cache.py read+write, session-start-boot.py write_boot_log(),
user-prompt-memory-check.py booted_flag write. Real Windows machine (the branch that actually
runs in prod here), real os.link() hard links throughout, no mocking.
Verdict: AGUANTA -- 8 distinct real PoCs, 0 breaks. (1) TOCTOU race simulation (monkeypatched
os.path.exists to inject the attacker's os.link() at the exact production checkpoint, Windows
new-file branch) confirmed the nlink check is unconditional post-open regardless of the
documented-accepted F5 residual -- even a brand-new-path race cannot bypass F6, because
os.link() to an existing file always produces nlink>=2 and the check fires on the already-open
fd regardless of timing. (2) Real 500-iteration multi-threaded concurrent race (background
thread hammering os.link() against the main thread's open loop, not simulated) produced 0
bypasses. (3) End-to-end sabotage (§34, real hard link pre-planted at the exact runtime path,
independent-channel verification via `certutil -hashfile` subprocess, never python's own open())
against all 3 real production entry points -- write_boot_log(), _write_glossary_cache(),
_read_glossary_cache() -- confirmed deferred-truncate correctly preserves the shared inode's
content on rejection, on both read and write paths, with zero fallback-to-plain-open() anywhere
in the exception handling (`except OSError: pass` swallows cleanly, no unsafe fallback exists).
(4) 2000-iteration hammering of the rejection path, handle count verified via independent
PowerShell `Get-Process ... HandleCount` query (not python's own fd tracking) -- delta 0, no
leak. (5) mode="a" + reject_hardlinks=True (NOT covered by the existing contract test file,
which only parametrizes r/w) -- confirmed the if/elif flag-building order on the POSIX branch
does not skip the nlink check for append mode; rejected correctly on both twins, sibling content
unchanged. (6) nlink=3 (not just 2) -- '>1' threshold generalizes correctly, twin parity holds.
One notable non-bug observation: user-prompt-memory-check.py's booted_flag call site never even
reaches the reject_hardlinks-guarded open when a hard link is PRE-planted before first boot --
`os.path.isfile(booted_flag)` short-circuits `if not session_booted:` first, so the guard is
literally unreachable in that specific scenario -- but this is SAFER, not weaker (no open() call
happens on the attacker's link at all this session, confirmed via certutil hash unchanged).
Attacked 8/8 identified vectors across BREAK/REGRESSION/STRESS/RACE phases (EXPLOIT/ABUSE/
DECEPTION phases: no viable distinct vector beyond what BREAK/REGRESSION already covered for
this specific, narrow feature -- logged as N/A with reasoning, not skipped silently). See
attack-patterns.md is NOT updated this round (nothing broke); see resilience.md for the full
per-vector detail.

## Previous attack
Target: issue #55 date-parsing migration (%aI+fromisoformat -> %at epoch, lib/date_parsing.py
centralization) -- dedicated adversarial round requested by Yoda after 106/110, diff 0ff8bfe..HEAD
-- bin/git-memory-gc.py, bin/git-memory-doctor.py, lib/bootstrap_commits.py, lib/date_parsing.py.
Real disposable repos in scratchpad, real `git commit`/`hash-object --literally` object-level
corruption (never touched the project repo), real end-to-end binary runs (gc.py --dry-run/--auto,
doctor.py --json, bootstrap.py --json), independent-channel verification via `git cat-file`/`git
fsck --full` throughout.
Verdict: DEBIL -- the parse_date() core (isdigit/int/fromtimestamp + ISO fallback, all exception
paths) holds solidly: negative epoch is rejected by git's own CLI/fsck entirely (only reachable via
deliberate --literally object surgery, and even then %at renders empty -> clean None, no crash);
\x1f/\x1f field-separator injection into subject/body mathematically + empirically can NEVER
produce a wrong-but-valid date (always collapses safely to None); huge digit-string DoS is blocked
by Python 3.11+'s int_max_str_digits guard; concurrent gc/doctor runs (parallel real subprocesses)
never corrupted repo state (fsck-clean throughout); the old %aI+.split("+")[0] code's negative-UTC-
offset crash (TypeError: naive/aware subtraction) is CONFIRMED real and CONFIRMED fixed by this
diff (reproduced with the literal old function body). 3 confirmed real breaks, none catastrophic:
(1) a year-10000+ author date (plain fsck-clean `git commit`, no trickery -- git's CLI only rejects
NEGATIVE dates, not future overflow past datetime.MAXYEAR) makes a Blocker: PERMANENTLY invisible
to both gc.py's H2 heuristic and doctor.py's stale-blocker count, with zero diagnostic trace, and
if the overflow-dated commit IS the GC commit itself, doctor falsely reports "GC: never run" despite
one having genuinely happened; (2) a future-but-in-range author date (+365 days, fully valid/fsck-
clean) makes doctor print "last run -365 days ago" -- a negative day count marked OK, no clamping
on check_gc_status()'s `(now - last_gc).days`; (3) lib/bootstrap_commits.py's %aI->%at swap has NO
consumer-side format adaptation -- the "date" field silently changed from a human-readable ISO
string to a raw epoch string, directly re-exposed verbatim in `git-memory-bootstrap.py --json`'s
output (documented as "structured output for Claude to present to the user"), confirmed live; the
test suite's own justification ("no crash today because nothing parses it") is narrower than the
real external consumer surface (T2 deception, not a blocking claim but inaccurate as stated). Two
UNREACHABLE-today findings logged but not counted as breaks per proof standard: parse_date()'s
isdigit() accepts several non-ASCII Unicode digit scripts that int() also silently accepts (produces
a wrong-but-valid date), but neither of the two real production call sites can ever feed it anything
but plain ASCII %at output; a truncated mid-digit git-log output would silently misparse to a wrong
date, but real run_git()'s blocking `proc.communicate()` is atomic (full output or clean timeout),
so this isn't reachable through the actual subprocess pipeline today. See attack-patterns.md /
resilience.md for full detail and exact repro steps.

## Previous attack
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
