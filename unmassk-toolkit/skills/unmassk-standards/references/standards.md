# Quality Standards — Generic

> Executable reference for AI agents. Binary rules (IF/THEN).
> Quality test: if two AIs read the same rule, they reach the same action.
> Stack-agnostic: applies to any language, any project. Project-specific values live in the project profile (see "Project profile"), never hardcoded here.

## Threat model — the system against itself

This document defends against **internal failure, not an external attacker.** The thing that breaks a project is the project breaking *itself*: memory lost or corrupted, a write that lands in the wrong place, a failure that passes silently, code that works on one OS and not another, a re-run that duplicates state.

There is **no adversary** in this model. Rules about injection, exploitation, hostile input, or attacker access do **not** belong here — a project that needs them declares them in its own profile. Everything below is calibrated to: *did the system corrupt, lose, or silently mis-handle its own data/state?*

---

## Pilar 1 — Producer↔Consumer round-trip integrity  (also cited as §34)

> **Anchor:** this section is the canonical `§34` referenced by agent prompts. `§34.1` = seam classification, `§34.2` = data provenance, `§34.3` = round-trip completeness, `§34.4` = the closed checklist below. Renaming to "Pilar 1" does not remove the `§34` handle.

The single most important rule, and the reason this is Pilar 1: **no truth is asserted against itself.**

**§34.1 — Seam classification.** A producer↔consumer seam exists wherever data is written and later read back: a file written then reread, a network call, a DB read/write, IPC, a queue, a subprocess boundary. IF the changed code (or its callees) crosses such a seam THEN this pillar applies — assumed by default, fail-closed. "No seam" may be claimed ONLY with the mechanical grep/dependency check shown, never by unaided assertion.

**§34.2 — Data provenance.**
```
IF a value is used as "expected" in an assertion against real system behavior
  THEN it MUST be either:
    (a) a value THIS run just wrote, re-read through the real seam, or
    (b) derived from a contract/schema that neither the implementer nor the test author can edit to fit today's behavior
  ELSE the value is fabricated ground truth — T1.
```

**§34.3 — Round-trip completeness.** IF a test writes a payload with N fields THEN the re-read assertion checks all N fields, enumerated programmatically from the write payload's keys — a hand-picked subset does not satisfy this.

**§34.5 — Real dependency by default (wire it to reality).** Default to testing against **real code and a real, disposable instance of the infra** — real DB, real file, real subprocess — not a mock. Mock ONLY what genuinely cannot run in the test environment (a paid, external, or non-deterministic third party), and even then the mock must not replicate production logic. A seam that is **only ever mocked, never once run against the real dependency, is unverified** — a green suite of mocks proves nothing about whether the pieces are wired together. At least one test must exercise the real wiring end-to-end. Not everything needs the real dependency, but the core seam of the feature always does.

**§34.6 — Confirmation is an independent read-back, not the command's own echo.** When code asserts that an action on an external system took effect — a device moved, a deploy went live, a row was written, a measured quantity is X — the confirmation MUST come from **reading the resulting state back through a channel independent of the command that caused it**, not from the fact that the command was sent, nor from the command's own success/ACK. "I sent `forward()`, so it moved" and "the write returned 200, so the data is there" are the same fabrication: the command asserted against itself. IF the resulting state genuinely cannot be independently read (no sensor, no queryable side effect) THEN the outcome is reported as *commanded / unverified* — never upgraded to *confirmed*. Inventing the confirmation, or deriving it from the command, is silent failure. This is the runtime generalization of §34.2: 3d's "never invent a measurement — read it from the caliper" and electronics' "the device confirms, or it isn't done" are one rule. (Distinct from §34.3: §34.3's round-trip is a *test* obligation, not a mandatory production read-after-write on every write; §34.6 governs the runtime moment code *claims an action succeeded*.)

| Rule | Tier |
|------|------|
| Seam presence assumed by default (fail-closed); "no seam" claimed only with the mechanical grep/dependency check shown | T1 |
| Hand-typed literal used as an expected value across a real seam | T1 |
| Persisted/committed captured response reused across runs as a fixture | T1 |
| Core seam of the feature exercised only by mocks, never once against the real dependency | T2 (T1 if nothing wires it to reality) |
| An action on an external system reported as *confirmed* from the command/ACK alone, with no independent read-back — and no *commanded/unverified* honesty when none is possible (§34.6) | T1 |
| Round-trip assertion covers only a subset of the written fields (not enumerated programmatically from the write payload's keys) | T2 (T1 if the omitted field is what the feature is about) |

Origin: a real incident where independent review passes unanimously approved code carrying weeks of latent bugs, because every check validated against the same hand-typed fixture — the fixture and the bug agreed with each other, so agreement proved nothing. The round-trip is regenerated live every run; only the check's logic persists, never the captured values.

---

## 1. Tier system

| Tier | Scope | Blocks merge | Action |
|------|-------|--------------|--------|
| T1 | Data/memory integrity, crashes, silent failure of a load-bearing path | Yes, always | Immediate fix |
| T2 | Error handling, core testing, structure | Yes, unless a `Waiver:` line documents the justification (waiver mechanics below) | Fix before merge |
| T3 | Naming, cosmetics, extra coverage | No | Fix when convenient |

IF uncertain about tier THEN assign T2.

**Definition — "load-bearing path"** (decides T1 vs T2): a path is load-bearing IF its failure loses or corrupts persisted state, OR blocks the primary function of the module. Otherwise it is not load-bearing.

**Definition — "re-read verification across the seam"**: a §34 round-trip **test** that writes a payload and reads it back through the real seam — NOT a mandatory read-after-write in production runtime. The rule demands the test exists, not that every production write re-reads itself.

**Security exception to the uncertainty fallback:** the "IF uncertain THEN T2" rule does NOT apply to attack-surface findings (injection, auth bypass, exposed secret). Those are out of this document's threat model — classify them via the project profile or route to the security agent (Argus); NEVER let the T2 fallback silently downgrade one.

**T2 waiver mechanics.** A T2 blocks merge "unless written justification". "Written" = a `Waiver:` line in the commit/finding record stating the rule waived and the reason. The reviewer (Cerberus/Yoda) verifies the waiver **exists**, not that it is eloquent — an absent waiver blocks; a present one passes the gate. A T1 is **never** waivable.

**Conflict tie-breaker (two rules fire on the same code).** The higher tier wins. At equal tier, the more specific rule wins. Example: a 320-LOC file triggers "split (T2)", but a naive split yields a 25-LOC module which triggers "over-splitting" — same tier, so the more specific rule (don't create sub-30-LOC modules) wins: split by real responsibility, not to hit the number.

### Finding classification (generic rows only)

| Finding | Tier |
|---------|------|
| Unhandled error that crashes the process | T1 |
| Data/memory written without re-read verification across a real seam | T1 |
| Silent failure of a load-bearing path (swallowed error, masked exit code, fail-open without log) | T1 |
| Concurrent write can corrupt shared state | T1 |
| Non-portable code that fails on a supported OS | T2 |
| Generic untyped error where the project defines typed errors | T2 |
| Type/force-cast without a justification comment | T2 |
| File over the size limit without a split | T2 |
| Dead export (zero consumers in production code) | T3 |
| Debug print/log left in committed code | T2 |
| Coverage below the project's declared threshold | T3 |
| Naming inconsistent with the project's convention | T3 |

### Execution priority (integrity-first)

1. **Data/memory integrity** — nothing corrupts or loses persisted state
2. **Silent failure** — every failure is observable
3. **Critical happy paths** — main flows run without crashing
4. **Structure and testing** — typed errors, tests, size limits
5. **Cleanup** — naming, cosmetics, dead code

IF a module has a T1 integrity finding AND a T3 cosmetic finding THEN fix integrity first. NEVER touch cosmetics while a T1 is open.

---

## 2. Design principles (agnostic)

- **SOLID** — single responsibility; open/closed; Liskov; interface segregation; dependency inversion.
- **DRY** — extract after the 2nd duplication; abstraction mandatory at 3+.
- **KISS** — simplest thing that works. IF an abstraction needs 4+ config params THEN it is too generic — simplify.
- **YAGNI** — implement only what is needed now. No speculative "just in case" code.

### Size limits (concept-keyed defaults — override via project profile)

| Concept | Default hard limit | Sweet spot |
|---------|-------------------|------------|
| Source file | 300 LOC | 200-300 |
| Exported function/method | 50 LOC | 15-30 |
| Nesting level | 3 | 2 |
| Function parameters | 4 | 3 (use an object beyond that) |
| Test file | 500 LOC | 200-400 |
| Cyclomatic complexity | 10 | 5-8 |

```
IF file > limit                                                    THEN mandatory split (T2)
IF file <= limit AND file >= 2/3 of limit AND 2+ responsibilities  THEN recommended split
IF file <= limit AND (file < 2/3 of limit OR 1 responsibility)     THEN do NOT split
```
(When a `> limit` file has a single responsibility, it still splits — by extracting cohesive helpers — but the split MUST NOT create sub-30-LOC modules; see the over-splitting anti-pattern and the tie-breaker.)

"Responsibility" (binary): IF all functions in the file need the same test setup THEN 1 responsibility; different groups needing different setup THEN 2+.

The numbers above are **defaults**. IF the project profile declares a limit THEN use it (see Project-pointer rule).

### Decision trees (agnostic)

- **Split a file** — see size rule above.
- **Extract to shared/utils** — used in 1 place → keep it there; 2 → note, don't extract; 3+ → mandatory extraction.
- **Create an abstraction** — repeats 2× → note; 3+ → mandatory; needs 4+ config params → too generic; saves <5 LOC per use → the repeated code is clearer.
- **Refactor vs leave alone** — works + tested + under limits → do NOT touch for aesthetics; works but violates T1 → mandatory fix; touches data/persistence → STOP, confirm first.

### Dead code & casts

- Exported symbol with zero production consumers → dead (T3). Consumed only in tests is NOT dead. Grep the whole source tree before deleting.
- Every force/unchecked cast MUST have a one-line justification comment. Exceptions: compile-time-only casts, test-mock casts.

---

## 3. Memory / persistence integrity (T1 core)

Every write to persisted state (files, memory index, git-memory, caches, config) must survive a crash mid-write and must be readable back exactly as written.

```
IF writing a file that is read back later
  THEN write to a temp file, fsync, then atomic rename — never truncate-in-place a live file
IF updating an index that points at other files (e.g. a MEMORY.md index → topic files)
  THEN the index and its targets must stay consistent — no dangling pointer, no orphaned target
IF overwriting existing content
  THEN read the current version first; never blow away content you did not author or verify
```

| Rule | Tier |
|------|------|
| Write path with no re-read verification across the seam | T1 |
| In-place truncate of a file that could be read concurrently or mid-crash | T1 |
| An edit that deletes user/content it did not author (regression by over-eager cleanup) | T1 |
| Index ↔ target inconsistency (pointer to a missing file, or unlinked-but-present file) | T2 |
| A persisted record (decision/log) silently lost on a failed write | T1 |
| Ever-growing persisted state with no compaction/rotation policy | T2 |
| New format reads old persisted data and corrupts or silently drops it (no version/migration) | T1 |

Lived example distilled into this section: a cleanup that "fixed" an orphaned marker **deleted the user's notes underneath it** — a mechanical fix that destroyed real data. Conservative rule: an edit removes only what it can prove is safe to remove; when unsure, preserve.

---

## 4. Silent failure / fail-loud (T1)

Every failure must be **observable**. A failure that produces no error, no log, and no signal is worse than a crash, because nobody knows the system stopped working.

```
IF an operation can fail
  THEN its failure must surface — a raised error, a logged warning, or a non-zero exit — never nothing
IF you chain a command whose exit code matters (a build, a test, a validation)
  THEN NEVER pipe it through something that replaces the exit code (| tail, | head, || true)
IF a fallback runs on failure (fail-open)
  THEN it MUST log why it fell back — a silent fallback hides the real fault
IF a status/label is derived from state
  THEN it must not be able to lie — verify against the real state, not a cheap proxy
IF a guard enables/disables behavior by environment
  THEN use an allowlist (env == 'dev' or 'test'), never a denylist (env != 'production')
  — a denylist silently enables dev behavior in every env it forgot (staging, uat)
```

| Rule | Tier |
|------|------|
| Empty catch / swallowed error on a load-bearing path | T1 |
| Exit code of a pass/fail command masked by a pipe or `|| true` | T1 |
| Fail-open without a log line explaining the fallback | T2 (T1 if it hides data loss) |
| A shown status derived from an unsafe proxy that can diverge from reality in silence | T1 |
| Environment guard uses a denylist (`env != 'production'`) instead of an allowlist | T1 |

Lived examples: `pytest | tail` handed the shell the exit code of `tail`, masking real test failures; a boot showed stale state without any warning that the fetch had failed; a version gate compared a semver as a *string*, so the label lied while the content silently diverged.

---

## 5. Platform robustness — Windows / Linux / macOS (T2)

The toolkit runs on all three. Code must not assume one.

```
IF you build a filesystem path        THEN use the language's path join, never hardcode "/" or "\"
IF you read/write text                 THEN handle CRLF vs LF; normalize before comparing strings
IF you read/write bytes as text        THEN declare UTF-8 explicitly; tolerate/strip a BOM; handle a lone surrogate without crashing
IF you rely on an env var              THEN account for per-OS names (HOME vs USERPROFILE)
IF you shell out                       THEN the binary/flags must exist on all supported OSes, or branch on the detected OS
IF you set a startup/subprocess timeout THEN give real margin — a cold FS or slow disk is not a failure
IF you open a file another process may hold THEN handle the lock/permission difference across OSes
```

| Rule | Tier |
|------|------|
| Hardcoded path separator or absolute path assumption | T2 |
| String comparison that breaks on CRLF vs LF | T2 |
| Encoding not declared / crash on non-ASCII or lone surrogate | T2 |
| Env var read that ignores the per-OS name | T2 |
| Non-portable shell/binary with no platform branch | T2 |
| Startup timeout too tight to survive a cold/slow disk | T2 |

Lived examples: tests broke on Windows over CRLF and over `HOME` vs `USERPROFILE`; a boot fetch timeout was too short and failed intermittently until raised.

---

## 6. Internal idempotency

Hooks, scripts, and boot steps re-run. Re-running must not duplicate or corrupt state.

```
IF a hook/script can fire more than once on the same input
  THEN a second run must be a no-op on already-applied state, not a duplicate write
IF two agents/processes share a working tree or state
  THEN NEVER perform a global mutation (stash/reset/checkout across the whole tree) — operate only on your own paths (pathspec)
```

| Rule | Tier |
|------|------|
| Re-run duplicates or corrupts state (no idempotency guard) | T2 |
| Global tree mutation while another actor is working — destroys their uncommitted work | T1 |

Lived example: parallel agents on one working tree — a global `stash`/`reset` by one destroyed the other's uncommitted work.

### Concurrency — race on shared state

```
IF a resource can be modified by concurrent actors
  THEN never SELECT-then-UPDATE (or read-then-write) without a guard — that is a race
IF you update shared state
  THEN include a version/timestamp guard in the condition (WHERE version = $seen / compare-and-set)
IF 0 rows/records were affected by the guarded update
  THEN it is a conflict — raise it, NEVER treat it as silent success
```

| Rule | Tier |
|------|------|
| Read-then-write / SELECT-then-UPDATE without a guard (race) | T1 |
| Guarded update affects 0 records but reported as success (silent) | T1 |
| Persisted write auto-retried without an idempotency key (may duplicate) | T1 |
| Retry without a max-attempt cap, or with a fixed (non-backoff) delay | T2 |

Concept only — no SQL isolation levels or DB-specific locking here; those live in the project profile.

---

## 7. Async & error handling (agnostic)

| Rule | Tier |
|------|------|
| Fire-and-forget async work (no await, no error handler) | T1 |
| Error in a `.catch`/handler swallowed instead of re-thrown or logged | T1 |
| Independent async ops run sequentially instead of concurrently | T2 |
| Cleanup (close connections, release locks) not in a `finally`/equivalent | T2 |

Error-handling principle (concept, not a specific class): the project defines its error taxonomy; use the project's typed errors, re-throw without wrapping away context, and NEVER silently swallow a catch. IF the project declares no taxonomy THEN a raised, logged, contextual error is the minimum.

---

## 8. Anti-pattern catalog (generic method)

Detect these regardless of language; examples are pseudocode.

- **Duplicated `instanceof`/type-switch chain** → replace N identical blocks with a map of type→config + one handler.
- **Comment as decoration** → a doc comment longer than the function it documents, or restating the signature, is noise. Remove.
- **Over-splitting** → do not extract a one-caller function to its own file; split by real entity (>~30 LOC, a responsibility that can grow), not by dogma.
- **Unnecessary runtime freeze/guard** → do at compile time what you don't need at runtime.
- **Duplicated near-identical validators/handlers** → parameterize into one.
- **Magic numbers/strings** in config/timeouts/limits → named constant.

---

## 9. Scoring — /110 (reweighted to the threat model)

Five weighted dimensions, calibrated to "the system against itself". **11 weight-units → /110.** Score each dimension 0-10 on its checklist only.

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| Integrity (data + memory) | ×3 | Pilars 1 & 3 — no corruption, no loss, round-trip verified |
| Silent-failure / Error handling | ×3 | §4 & §7 — every failure observable, nothing swallowed |
| Structure | ×2 | §2 — size limits, SOLID, no duplication beyond the DRY threshold (3+ occurrences → extract) |
| Real verification / round-trip | ×2 | tests exist and exercise the real seam, not a fabricated fixture |
| Maintainability | ×1 | naming, no dead code, no debug prints, constants |

Platform robustness (§5) is scored as **checklist items inside Integrity and Structure** — it is NOT its own weighted dimension (that would make the total /130, not /110).

Scoring rules: 10 = all items pass; 9 = one minor miss; 8 = two misses; <8 = serious. Do NOT invent criteria outside the checklist. IF something works and violates no checklist item THEN it is NOT a finding.

**The score and the merge gate are separate machines — the number never overrides a tier.** The merge/stop gate = **full score AND zero open T1 AND zero un-waivered T2**. 110/110 is *necessary, never sufficient*: a single open T1 blocks merge even at a perfect score. The closed checklists are not exhaustive of all T1s (e.g. a denylist env-guard §4, a format-migration corruption §3 may be found outside the listed items); any T1 found anywhere in this document blocks, whether or not it maps to a checklist row. An autonomous loop must not stop at 110/110 while a T1 is open.

### Closed checklist per dimension (score 0-10 on these only)

**Integrity (×3):** round-trip verified on every real seam (§34); writes atomic (§3); index↔target consistent (§3); no concurrent-write race (§6); no persisted record lost.
**Silent-failure / Error handling (×3):** no empty/swallowed catch; no masked exit code (§4); fail-open logs its fallback; status not derived from an unsafe proxy; async errors re-thrown or logged (§7); cleanup in `finally`.
**Structure (×2):** files/functions within limits (§2); SOLID respected; no duplication beyond the DRY threshold in §2 (extract at 3+ occurrences); platform-portable (§5 — path/encoding/env/timeout).
**Real verification (×2):** tests exist for load-bearing logic; they exercise the real seam, not a fabricated fixture; **no tautological assertion** (`expect(true)`), **no test depends on execution order**, **no mock that replicates production logic**, mocks cleared between tests; happy path + error paths covered. Do NOT test: getters without logic, re-exports, external library behavior, every parameter combination.
**Maintainability (×1):** named constants (no magic numbers in config/limits/timeouts); no dead code / debug prints; comments and naming per §11.

### Anti-void rule (normative)

**For every concrete rule removed in favor of an abstract principle, one mechanical IF/THEN internal-failure rule must remain in that dimension.** A dimension carrying a weight but no mechanical checks is a phantom, and the /110 becomes decorative. A reviewer must be able to point at a concrete IF/THEN for every weighted dimension.

**Per-item evidence (normative).** A dimension's 0-10 is not a gut grade — it is derived from its checklist items, each pass/fail with evidence (a `file:line`, a test result, a grep). Report the failing items, not just the number. A dimension scored without naming which items passed/failed is an unverified assertion — exactly the §34 sin at the scoring layer.

---

## 10. Project profile & pointer rule

The generic standard defines the **what/why**. The concrete **which/how-much** lives in the project, in one of two homes:

1. **Agent memory** (`.claude/agent-memory/<agent>/MEMORY.md`) — operational overrides: this project's size limits, coverage threshold, build/test command, "mistakes I've made here before".
2. **Project profile** (declared in `CLAUDE.md` / git-memory, never a loose file) — contracts: response/data shape, soft-delete convention, schema, roles, stack conventions.

### Pointer rule (normative)

```
IF the project profile declares value X   THEN use X
ELSE                                       use the generic default
NEVER invent a value to fit today's behavior
IF a check depends on a profile that is MISSING
  THEN FAIL LOUD — surface a warning that the profile is absent
  NEVER silently resolve the check to a no-op (that is itself a silent failure — §4)
```

**Tailoring boundary (normative).** A project profile MAY tighten a value (stricter limit), add project-specific rules, or map a generic concept to a concrete command. A profile MUST NOT **downgrade or waive a generic T1** — no profile can declare "we don't do atomic writes here" or "silent failure is fine here". The pointer rule tunes the *which/how-much*, never the *whether* of a T1. A profile attempting to weaken a T1 is itself a T1 finding.

Examples of what standards must NOT hardcode (they point to the profile instead): the typecheck/build command (not `tsc`), the response/data contract (not an HTTP envelope), the soft-delete filter (not `AND active = true`), the DB columns, the roles, the coverage number.

---

## 11. Comments, naming & dependencies (maintainability)

```
Document an exported symbol only when its purpose is non-obvious; note what it throws.
NEVER restate the type signature in the doc comment (that is noise).
A doc comment longer than the code it documents is an anti-pattern — shorten or delete.
Identifiers are in the project's code language (default English); comments and user-facing
  messages follow the project's existing convention — check before writing.
Name constants for any magic number/string in config, security, limits or timeouts.
IF functionality is solvable in under ~30 LOC THEN implement it; never add a dependency for something trivial.
```

| Rule | Tier |
|------|------|
| Doc comment restates the signature, or is longer than the function | T3 |
| Magic number/string in config, limits or timeouts | T2 |
| Magic number/string in general logic | T3 |
| Dependency added for trivial (<30 LOC) functionality | T2 |
| Naming inconsistent with the project's declared convention | T3 |

---

## Severities

| Severity | Definition | Typical tier |
|----------|-----------|--------------|
| CRITICAL | Data loss/corruption, or a load-bearing path fails silently | T1 |
| HIGH | Violates a hard rule, likely bug | T1-T2 |
| MEDIUM | Reduces maintainability / violates a recommendation | T2 |
| LOW | Minor improvement | T3 |
| INFO | Observation, no required action | — |

IF HIGH and unclear T1 vs T2: affects data/memory integrity or silent failure → T1; affects structure/testing/patterns → T2.

---

## Acceptance gate for THIS document (round-trip on itself)

Before this standard replaces the current one, replay **real past internal failures** through it and confirm each still classifies correctly — proof the rewrite kept its teeth, not just its principles. One replay per new pillar, not a single fixture:

| Lived incident | Must classify | Under |
|----------------|---------------|-------|
| `pytest \| tail` masked the real exit code | T1 | §4 Silent failure |
| A cleanup deleted the user's notes under an orphaned marker | T1 | §3 Memory integrity |
| Tests broke on Windows over CRLF / `HOME` vs `USERPROFILE` | T2 | §5 Platform |
| A global `stash`/`reset` destroyed a parallel agent's uncommitted work | T1 | §6 Idempotency/concurrency |

IF any replay does not classify as shown THEN this document lost its bite for that pillar — fix before shipping.

**Determinism probe (the line-4 test, made executable).** The header claims "two AIs reading the same rule reach the same action." Prove it: hand the *same* finding to two independent agent instances and compare the tier they assign. IF they diverge THEN the rule that produced the split is ambiguous — pin it down before shipping. This is cheap with the existing multi-agent (Council) infrastructure and is the only mechanism that actually tests the document's own quality criterion.
