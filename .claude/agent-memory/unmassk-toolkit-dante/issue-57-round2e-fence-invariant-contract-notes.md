---
name: issue-57-round2e-fence-invariant-contract-notes
description: Issue #57 round 2e (decision e861680, memo b49eb60) — structural closure of the sanitizer denylist class via whitespace-tolerant invariant regex, not byte enumeration; bootstrap fixed-point tag stripping; git-memory-log scope/emoji gap
metadata:
  type: feedback
---

Extends [issue-57-output-saneo-round2d-contract-notes](issue-57-output-saneo-round2d-contract-notes.md).
That round chased individual bytes one at a time (added \x85/NEL to a
byte-enumeration test). Memo b49eb60 found the actual root cause: this is
NOT a missing-byte problem, it's an ORDER-OF-OPERATIONS bug —
`sanitize_trailer_value()` converts control bytes to a literal SPACE
*before* trying to remove the exact (no-`\s`) `</?memory-data>` substring,
so its own space-insertion defeats its own tag-removal step, for EVERY
byte in the class, not just the ones nobody thought to test yet. Round 2e
is declared (in decision e861680) the LAST denylist-patching round — if
the same class reappears after this, escalate a redesign choice
(denylist-robust vs. allowlist/token-fence vs. full `<>` escaping) to Bex,
don't keep patching byte-by-byte at 1am.

## The key test-design lesson: assert the INVARIANT, not the byte

Added `_FENCE_SHAPE_RE = re.compile(r"<\s*/?\s*memory-data\s*>", re.IGNORECASE)`
to `tests/test_control_byte_injection.py` PART R, replacing the
byte-enumerated `_FENCE_BREAK_RE_NEL` approach from PART L for this
round's tests. This single whitespace-tolerant regex catches BOTH bypass
mechanisms with the same assertion:
1. bytes that ARE in the sanitizer's char class (get converted to a real
   space, which `\s*` then matches) — parametrized over all 12 bytes
   currently in the class (CR, LF, VT, FF, ESC, FS, GS, RS, DEL, NEL,
   U+2028, U+2029), confirmed RED for all 12, both open (`<memory-data>`)
   and closing (`</memory-data>`) tag shape.
2. `\x1f`, which is NOT in the sanitizer's char class at all and survives
   100% raw/unconverted — confirmed RED anyway, because Python's `\s` in
   `re` (Unicode-aware, no `re.ASCII`) directly matches `\x1c`-`\x1f`
   as whitespace on its own (confirmed empirically: `re.match(r"\s",
   "\x1f")` is truthy) — so the SAME invariant regex catches this
   completely different mechanism without any special-casing. This is
   exactly the point: an invariant assertion survives a future one-byte
   patch; a byte-enumerated assertion doesn't.

Verified end-to-end (not just the unit function) via `recall_relevant()`
(2 representative bytes: `\x1f` and `\x1b`, not all 12 — the unit-level
parametrize already covers the full class, e2e only needs to prove the
mechanism reaches the real pipeline) and via the real
`hooks/user-prompt-memory-check.py` subprocess (worst-case `\x1f` only).

## `_strip_generic_tags` needs a fixed point, not one `.sub()` call

`lib/bootstrap_commits.py`'s `_GENERIC_TAG_RE` (`</?[a-zA-Z][\w-]*\s*>`)
assumes a naked tag. Three constructions bypass it, confirmed live both at
the unit level and through the real `git memory bootstrap --json` CLI:
`<system role="root">` (attribute breaks the regex's bare-`>` assumption),
`<system/>` (the regex requires the tag name to be followed by `\s*>`
directly — the literal `/` before `>` isn't consumed by `[\w-]*` or `\s*`,
so the whole `<system/>` never matches and survives verbatim), and
`<sy<system>stem>` (nested — one `.sub()` pass strips only the innermost
`<system>`, leaving the outer `<system>...>` intact — needs to iterate to
a fixed point, not a single call).

**Guard confirmed both ways**: ordinary arithmetic `a < b and b > c`
survives completely untouched today (no tag-shape at all, never at risk).
A TypeScript-style generic `Foo<Bar>` is ALREADY neutralized by the
current regex (confirmed live) — per this round's decision, that's an
ACCEPTED trade-off for the bootstrap-json context (neutralizing
tag-shaped `<...>` there is fine), so the contract deliberately does not
assert on `Foo<Bar>` either way, only on true arithmetic usage.

## `git-memory-log.py` scope/emoji gap needs TWO different constructions

PART O (prior round) only covered `msg` (group 4). The `scope` (group 3)
and emoji/prefix (group 1) groups of `SUBJECT_RE`'s matched branch are
still printed raw. A single hostile subject can't hit both — an ANSI
sequence placed inside the scope parens (`decision(auth\x1b[31mFAKE):
...`, needs an emoji prefix present to reach the matched branch at all)
is a DIFFERENT construction than one placed in the emoji/prefix token
itself (`🧭\x1b[31mFAKE decision(auth): ...`) — confirmed live, both leak
raw ANSI independently.

## Verification discipline (2026-07-10)

Every RED/GUARD here was reproduced live in a scratch script against the
REAL current source (sanitize_trailer_value, _strip_generic_tags, the
real git-memory-log.py and git-memory-bootstrap.py --json subprocess
calls) before a single test was written, including confirming the
counter-intuitive fact that Python's `\s` regex class matches `\x1c`-`\x1f`
natively (load-bearing for why the invariant regex generalizes across
both bypass mechanisms without enumerating \x1f separately). PART R added
to the same file (`tests/test_control_byte_injection.py`, now ~3400
lines): 45 new tests (37 RED + 8 GUARD), confirmed via a scoped
`pytest -k` run matching exactly. Full file: 154 tests total (109
pre-existing + 45 new), `117 passed, 37 failed` on the scoped class,
zero regressions in the 109 pre-existing tests.
