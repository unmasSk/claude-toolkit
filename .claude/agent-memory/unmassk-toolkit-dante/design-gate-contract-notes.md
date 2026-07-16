---
name: design-gate-contract-notes
description: bin/design_gate.py (skill frontmatter collision linter) test contract — 68 tests, hyphen-free bin/ script direct-import trick, JSON-string-as-YAML-value fixture technique, CI wiring
metadata:
  type: project
---

`unmassk-toolkit/bin/design_gate.py` (skill frontmatter collision linter — keyword/phrase
collisions, dangling "Use when NOT" skill references, mutual contradictions) got its first
test file: `unmassk-toolkit/tests/test_design_gate.py`, 68 tests, all synthetic fixtures under
`tmp_path` (never depends on the real repo's skill tree or its real
`design-gate-allowlist.json`). Wired into `.github/workflows/toolkit-ci.yml` as a step after
the pytest step: `python unmassk-toolkit/bin/design_gate.py` (default `--root`/`--allowlist`,
same invocation style as running it locally) — CI fails only on a genuinely NEW collision;
baseline collisions (gdpr/hipaa/mrr/pgvector/etc.) are already in the real allowlist so this
is green today (verified live: 87 skills scanned, `Result: CLEAN`, exit 0).

**`design_gate.py` is the ONE bin/ script with no hyphens in its filename** (every other
bin/ script — `git-memory-*.py` — is hyphenated and needs the
`importlib.util.spec_from_file_location` dance documented in
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)). Because
it's a plain valid module name, it's directly importable: add `BIN_DIR` (from `conftest`) to
`sys.path`, then `import design_gate` — normal, no importlib gymnastics. This made most of the
suite fast in-process calls (`design_gate.run_gate(root, allowlist_path=...)`,
`design_gate.extract_mention_terms(...)`, etc.) instead of subprocesses, reserving real
subprocess (`run_script`) only for CLI-wiring-sensitive assertions (exit codes, `--json` vs
human-mode output, `--root`/`--allowlist` argparse wiring, the utf-8 stdout encoding path via
`force_utf8_streams()`).

**Fixture technique: emit the SKILL.md description as a JSON string, not a YAML block
scalar.** `f'description: {json.dumps(description)}'` is a valid one-line YAML flow scalar
(JSON is a YAML subset) that safely embeds quotes, colons, and unicode with zero YAML-folding
indentation risk — much more robust than trying to hand-indent a `>`-folded block scalar in a
test fixture. Used for every well-formed synthetic skill in the suite. Malformed fixtures
(never-crash tests) are written as raw strings via a separate `_write_raw()` helper instead,
since those need literal control over the broken YAML/frontmatter shape.

**Always pass an explicit (usually empty) allowlist fixture — never rely on the real
`design-gate-allowlist.json` in these tests**, even though synthetic term names (`quantumwidget`,
`XQZ`, `wobblesprocket`, etc.) are chosen to never collide with real allowlisted keys anyway.
Keeps the suite decoupled from the real allowlist file's future contents.

**Gotcha found while writing extraction-function assertions: a skill's `wordbag` (built by
`build_skill_records()`) stores hyphenated compounds as ONE token** (`"prefers-reduced-motion"`),
not split into sub-parts — `_significant_words()` (used for the wordbag) keeps hyphens
mid-token by design. Only `_expand_wordset()`/`_expand_variants()` (used later, inside
`find_mutual_contradictions()`'s "is this ground claimed anywhere" check) splits a hyphenated
compound into its ≥4-char sub-parts. Asserting `"motion" in wordbag` for a
`"prefers-reduced-motion"` mention term is wrong — the correct assertion is the whole compound
string. Caught this live (first draft failed), not by re-reading the source ahead of time —
worth double-checking which of the two functions a given test path actually exercises before
asserting on token-splitting behavior anywhere in this module.

**Cerberus regression-fix tests (digit-led skill name dangling-ref, short ALL-CAPS acronym
collision) were verified non-vacuous with a live inline simulation of the OLD (pre-fix) regex
and filter logic** (reimplemented the old `_is_distinctive` without the `isupper()` carve-out,
and the old dangling-reference token regex with `[a-z]` instead of `[a-z0-9]` after the
hyphen) run against the SAME fixture inputs, in a throwaway `python -c` snippet outside the
test file — confirmed the old logic returns empty/False (would have missed the bug) while the
current code catches it. No production file was touched to do this check.

**Coverage**: 26/26 top-level functions in `design_gate.py` have at least one direct or
CLI-level test; 15/15 identified error paths covered (frontmatter never-crash branches ×8,
`load_allowlist` branches ×3, 0-skills-fail-loud, CLI `yaml is None` early exit, function-level
`yaml is None` guard, bad `--root` path, `_finding_key` unknown-category `ValueError`). Not
tested: `load_skill_frontmatter`'s real `OSError` (permission-denied) branch — only the
`UnicodeDecodeError` half of that combined except-clause was exercised (invalid UTF-8 bytes);
a genuinely unreadable-but-existing file isn't reliably simulable cross-platform without
root-owned-file tricks that don't fit a portable fixture suite, same reasoning as the
`os.chmod`-based Windows exclusions already documented in
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md).
