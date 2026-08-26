---
name: capa4-hardening-session-notes
description: 2026-08-02 capa-4 hardening pass (clusters/context/rules/health/dispatch) -- gitcmd.commit_empty verbatim-cleanup regression technique, and confirmed parallel-agent test drift unrelated to this task
metadata:
  type: project
---

Session covered two jobs from the orchestrator (PIEZAS.md Sec.12bis step
5, "endurecer con lo aprendido, antes de que Moriarty entre"), both
tests-only, both against already-shipped production code:

1. `health.coherence_rules()` -- brand-new function, zero tests (DEUDA.md
   point-11 pattern). 5 tests. See
   [health-contract-notes](health-contract-notes.md)'s Update section for
   the full design.
2. Nine review findings across `clusters`/`context`/`rules`/`health`/
   `dispatch`, of which 5 concrete items were asked to be pinned with
   tests. Landed as: 2 tests in `test_rules.py` (write-order/restore +
   invalid-text-bounces-before-git, see
   [rule-py-full-contract-notes](rule-py-full-contract-notes.md) Update), 1 regression
   in `test_health.py` (archived-note false positive, see
   [health-contract-notes](health-contract-notes.md) Update), 2 tests in
   `test_dispatch.py` (`DeclaredZoneNotFound`, see
   [dispatch-contract-notes](dispatch-contract-notes.md) Update), and 1
   test in `test_gitcmd.py` (below). No test added to `test_clusters.py`/
   `test_context.py` directly -- none of the 5 named items needed a test
   AT that layer specifically (the `gitcmd.commit_empty()` item is the
   shared dependency both `rules.py` and `context.py` lean on, and
   testing it once at the `gitcmd` level covers both without duplicating
   the same assertion in two files).

## `gitcmd.commit_empty()` — MOVED 2026-08-25

Relocated verbatim to [gitcmd-contract-notes.md](gitcmd-contract-notes.md)'s own Update section — this
was the one piece of this session's content not already duplicated elsewhere (the write-order/restore
regression is in `rule-py-full-contract-notes.md`'s Round 1 Update; the `coherence_rules()` hardening is in
`health-contract-notes.md`'s own Update; the `DeclaredZoneNotFound` hardening is in `dispatch-contract-notes.md`'s
own Update — all confirmed present by grep before this file was left retired). Nothing cut, only moved.

## Confirmed unrelated: parallel-agent drift observed in the full-suite run

Full-suite command run at the end of this task
(`python3 -m pytest unmassk-toolkit/tests/memory -q`) showed 6 failures
beyond this task's scope -- verified NOT caused by anything edited in
this session (only `test_health.py`/`test_rules.py`/`test_gitcmd.py`/
`test_dispatch.py` were touched, confirmed via `git status --porcelain`):

- **`test_notes.py`** (5 failures when run in isolation): `notes.replace()`
  and `notes.close()` still raise a deliberate
  `NotImplementedError("... esta descopado de esta tarea ...")` --
  another agent (Ultron, presumably) is mid-flight on those two
  functions' real contract. Confirmed by reading the actual
  `AssertionError` text: the test itself asserts the exception is NOT a
  `NotImplementedError`, and it still is one.
- **`test_report.py`** (2 failures, was 4 collection ERRORS at session
  start when `report.py` didn't exist yet): a colleague finished a first
  pass of `report.py` mid-session. Its `build_zone()` returns a
  `ZoneReport` that fails `isinstance()` against the test's own loaded
  `model` module -- the exact cross-module class-identity gotcha already
  documented project-wide (`clusters-contract-notes.md`,
  `context-py-contract-notes.md`, etc.) -- `test_report.py` just doesn't
  (yet) use the field-by-field comparator pattern the other contract
  files adopted to sidestep it. Not my file to touch (explicitly excluded
  by the orchestrator this session), and not something to silently patch
  around.

Reported here rather than acted on, per this project's explicit rule
("nada se rellena con criterio propio... un hueco puede ser deliberado")
and the task's own instruction to note anomalies and continue rather than
stop to ask.
