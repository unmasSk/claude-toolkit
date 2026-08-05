---
name: config-contract-notes
description: unmassk-memory (v2) Capa 1 -- lib/memory/config.py contract tests from PIEZAS.md Sec.6.3, 3 rows RED + a 4th GREEN-phase test for Ultron's declared type-guard deviation; fail-loud-vs-missing-file anti-vacuity gotcha, scratchpad mutation-check technique
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_config.py` (3 tests, RED by
design) -- one test per row of the "Sus tests" table in
`docs/memoria-v2/PIEZAS.md` Sec.6.3, literally, no extra coverage added
(same test-first acceptance-granularity override as
[vocabulary-contract-notes](vocabulary-contract-notes.md) and
[memoria-v2-fase0-emojis-utf8-contract-notes](memoria-v2-fase0-emojis-utf8-contract-notes.md)).

**The three rows are not comfort, they're security** (the task framed
it this way and it shapes the assertions): no config file -> customs
must be born OFF (row 1) and repo_type must default to the protected
`"gitflow"` (row 2) -- if either defaulted the other way, day-one
install would either block the still-in-use v1 system or leave a
main-branch auto-deploy repo unprotected. Row 3 is the one that needed
care.

**Row 3 anti-vacuity gotcha, the one worth remembering:** `Config()`'s
own default is `customs_enabled=False` -- the SAME value row 1 asserts
for the correct "no file" case. If `load()` silently swallowed a
corrupt-file parse error and fell back to `Config()`, that fallback
would produce `customs_enabled=False` too, and a naive test asserting
just that value on a corrupt file would falsely pass on exactly the bug
the row exists to catch ("un vigilante que no vigila y encima no lo
dice" -- the silent failure has the same symptom as the correct
default). Fixed by asserting `pytest.raises(Exception)` around
`config.load(corrupt_path)` instead of comparing return values --
raising is the only signal that distinguishes "no file yet" (accepted,
quiet) from "file exists and is broken" (must fail loud). Any test on
`load()`'s no-file default vs corrupt-file behavior on this kind of
frozen dataclass with unfortunate matching defaults should check this
same trap first.

**`"gitflow"` literal, disclosed:** not importable (no module exports
it -- it's not one of vocabulary.py's five closed-data tables per
PIEZAS Sec.6.1, and config.py doesn't exist yet), so it's typed as a
literal sourced directly from PIEZAS Sec.6.3's own Superficie citation
(`repo_type: str = "gitflow"  # fail-closed`), same allowance as
[vocabulary-contract-notes](vocabulary-contract-notes.md)'s
`EIGHT_INDEX_FILES`/`SEVEN_TYPES` literals for a module that doesn't
exist yet.

**Corrupt-file fixture:** unparseable text (`"{ esto no es json valido
"`) written via `tmp_path`, not a real fixture file checked into the
repo -- config.py's file format (JSON) is inferred from `config.json`
(the real name, ARQUITECTURA.md §6bis + PIEZAS Sec.6.3; do NOT use
`git-memory-config.json`, that's the OLD v1 marker file PIEZAS cites
only as the historical source of the `repo_type`/`test_command` data,
not the file `config.load()` reads -- coordinator caught this exact mix-up
in round 1, see below).

**Round-1 coordinator correction, both fixed:**
1. **Filename** -- all three tests originally used
   `tmp_path / "git-memory-config.json"`. Wrong: that's the v1 file.
   Renamed to `tmp_path / "config.json"` everywhere (functionally inert
   since it's a tmp_path, but a stale name in a brand-new test is
   exactly the kind of residue that confuses someone in three months --
   coordinator's own words).
2. **Row 3 `pytest.raises(Exception)` too broad** -- passed even if
   `load()` raised for a WRONG reason (e.g. an internal `TypeError` bug
   unrelated to the corrupt file). Fixed by keeping the broad `Exception`
   type (PIEZAS Sec.6.3 doesn't name a concrete exception class, only
   "falla en alto" -- fixing a class not cited would invent an
   unstated rule) but ADDING `assert corrupt_path.name in
   str(exc_info.value)` -- the message must name the file that broke.
   Mutation-checked both directions: a naive `json.load()`-without-
   context fake raises `JSONDecodeError` with no filename in the
   message and correctly FAILS this assertion; wrapping it in `raise
   ValueError(f"config corrupto en {path}: {exc}")` correctly PASSES.
   This mirrors gitcmd.py's own contract (Sec.7.1: "el mensaje real,
   entero, nunca vacio ni recortado") applied one layer up.

**Verification technique used before reporting done:** same
mutation-check as
[vocabulary-contract-notes](vocabulary-contract-notes.md) -- wrote a
throwaway real `lib/memory/config.py` (dataclass + `load()` matching
the contract exactly) in one bash block, confirmed all 3 tests PASS
(not vacuous), deleted it and `__pycache__`, then reran to confirm RED
returned (`FileNotFoundError`, one per test, at fixture setup).

Verification command used (matches the task's exact ask):
`python3 -m pytest unmassk-toolkit/tests/memory/test_config.py -v` -> 3
errors, `FileNotFoundError: lib/memory/config.py` at fixture setup, one
per row -- RED for the right reason.

Scope note: `conftest.py` and other colleagues' in-progress files
(`lib/memory/vocabulary.py`, `tests/memory/test_zzz_probe_collision.py`,
etc., from parallel `zones.py`/`format.py`/`similar.py` test writers)
were present as uncommitted changes in the working tree before this
task started and were not touched.

**4th test, added after Ultron implemented (GREEN phase, same file):**
Ultron's real `load()` added a per-field `isinstance` guard that no row
above literally asked for. He declared it as a deviation and it turned
out to guard a real bug: `{"customs_enabled": "false"}` (quoted) is
valid JSON, so it never hits the JSONDecodeError path of row 3 -- but
`bool("false") is True` in Python, so an ungated `load()` would return
`Config(customs_enabled="false")` and any `if config.customs_enabled:`
consumer would silently turn the customs on. Added
`test_wrong_type_but_valid_json_fails_loud_and_names_file` (same
`pytest.raises(Exception)` + filename-in-message pattern as row 3 --
reused deliberately, don't invent a new assertion shape when an
existing contract test already proves the right thing).

**Verification technique for a GREEN-phase addition (different from
the RED-phase one above):** since `config.py` already exists for real,
mutation-checking it means editing a COPY, never the original. Copied
`lib/memory/config.py` into the scratchpad
(`/private/tmp/.../scratchpad/mutation_check/config_mutated.py`, NEVER
`lib/memory/` -- see
[mutation-check-collision-incident-ids](mutation-check-collision-incident-ids.md)
for why that folder is off-limits for throwaway files), stripped just
the `customs_enabled` isinstance guard, loaded the mutated file via
`importlib.util.spec_from_file_location` in a standalone script (not
through the `import_lib_memory_module` conftest helper, which is
hardcoded to `lib/memory/` and can't point at a scratch copy), and
called `.load()` on the same quoted-`"false"` fixture. Confirmed it
returns `Config(customs_enabled='false', ...)` with no exception --
proving the new test's `pytest.raises(Exception)` would fail (RED) on
the unguarded code, so the GREEN result against the real module is not
vacuous.

Reference: [vocabulary-contract-notes](vocabulary-contract-notes.md), [memoria-v2-fase0-emojis-utf8-contract-notes](memoria-v2-fase0-emojis-utf8-contract-notes.md), [mutation-check-collision-incident-ids](mutation-check-collision-incident-ids.md)
