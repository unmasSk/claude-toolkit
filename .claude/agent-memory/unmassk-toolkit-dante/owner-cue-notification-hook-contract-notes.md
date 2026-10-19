---
name: owner-cue-notification-hook-contract-notes
description: #95 2d owner-cue RED contract -- testing a sound hook without sound; Perl fake afplay with warm-up for sub-second timing
metadata:
  type: project
---

`unmassk-toolkit/tests/hooks/test_owner_cue_contract.py` (17 tests, 16 RED, 1 green guard).

**Never play sound:** hook PATH = scratch bin (python3 sh-wrapper + fake afplay) + `/bin`;
real afplay is `/usr/bin/afplay`, kept off PATH. Contract forbids a hard-coded
`/usr/bin/afplay` (it would bypass the fake AND play through speakers).

**Sub-second timing gotcha:** a Python fake recorded the first play ~0.15 s late
(gaps [0.17, 0.30]). Two causes: interpreter cold start and macOS's first-exec
check of a freshly written script. Fix: fake in Perl (`/usr/bin/perl`, Time::HiRes)
+ one warm-up exec in the fixture (`--owner-cue-test-warmup`, exits before logging).
Gap window 0.25-0.9 s with a 3 s fake play: kills no-sleep, 0.15 s and sequential.

**Harness validated** on a scratch copy with a reference impl: 17/17 green x3,
11/11 mutants killed (incl. `wait` at end, stdin crash, `.*`/absent matcher, Stop re-wire).
Absent matcher must be treated as match-all in the registration helper.

No test runs `compare_hooks_doc` on the real tree: SKILL.md hook-table drift is only
caught by doctor / `bin/hooks_doc_sync.py`.

**Fix pass (D-126 beyond-the-tests, 2026-10-19):** "afplay on PATH but cannot start" =
an executable file whose shebang names a nonexistent interpreter -- `shutil.which`
finds it (X_OK + isfile), `Popen` raises FileNotFoundError. Chmod 0o644 would NOT
work: `which` skips it, so it tests the "missing" branch instead. Test asserts rc 0,
no Traceback, fast, and "afplay" on stderr; kills both "no try/except" and
"except: pass" mutants. File now 18 tests.
