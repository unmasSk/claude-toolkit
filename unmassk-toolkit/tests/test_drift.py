"""
Drift tests simulating 6 months of commit history.

Retirement note (memoria-v2 cleanup, docs/memoria-v2/PLAN-CONSTRUCCION.md
§9.3): test_gc_tombstones, test_dedup_integrity, test_snapshot_budget,
test_truncation and test_delimiter_collision were all removed — every one
of them depended on hooks/precompact-snapshot.py (via the run_snapshot()
helper), which no longer exists on disk.

RETIRADO 2026-08-26 (Bilbo finding, verified by reading the real code, not
assumed): test_deep_search (plus its exclusive generators build_history/
gen_code_commit/gen_decision/gen_memo/gen_context and the drift_repo
fixture) is retired too. It generated 200 commits using the v1 trailer
format (`Decision: ...`, `Memo: <cat> - <desc>`, bare `git commit --allow-
empty -m "<subject>\\n\\n<trailers>"`) and then asserted that
`git log --all --grep=Decision:` / `--grep=Memo:` found them — a real git
feature, zero project code involved. That format is not what this project
writes anymore: the real producer, `lib/memory/format.py:196`
(`build_subject`), emits `[D-030][zone1][zone2] <emoji> <headline>` as the
subject, and the real body-field vocabulary
(`lib/memory/format.py:244`, `_BODY_FIELD_ORDER`) is `Why, Awaits, Keys,
Description, Replaces, Origin, Issue` — there is no `Decision:`/`Memo:`/
`Next:`/`Blocker:`/`Touched:` body field anywhere in the current system.
The test never called `lib/memory/format.py`, `query.py`, or any other
project module — it only proved that stock `git log --grep` can find a
string the same test inserted, which fails this project's own rule for
what earns a test: "un test entra solo si compara dos cosas escritas por
separado; si solo se mira a sí mismo, sobra." No rewrite target exists
that wouldn't be a substantially new test (a real 200-note round trip
through `lib/memory/query.py`'s `by_zone`/`by_word`/`by_id` against the
real producer) — out of scope for a mechanical realignment pass; flagged
here rather than invented. Confirmed nothing else in this test suite
imports `gen_code_commit`, `gen_decision`, `gen_memo`, `gen_context`,
`build_history`, `drift_repo`, `_git_log_or_fail`, or the
`TOTAL_COMMITS`/`DECISION_COUNT`/`MEMO_COUNT`/`SCOPES`/`EMOJIS`/
`CODE_TYPES` constants (grepped across `unmassk-toolkit/tests/`) — no
coverage lost anywhere else by removing them.
"""

import sys

import pytest


# RETIRADO (PLAN-CONSTRUCCION.md paso 9.3): run_snapshot() invocaba
# hooks/precompact-snapshot.py, que ya no existe en disco (confirmado por
# FileNotFoundError en ejecucion real) — eliminado junto con el resto del
# sistema de memoria v1. Sus unicos cuatro llamadores (test_dedup_integrity,
# test_snapshot_budget, test_truncation, test_delimiter_collision, mas
# abajo) se retiraron con el.


# RETIRADO (PLAN-CONSTRUCCION.md paso 9.3): test_dedup_integrity,
# test_snapshot_budget y test_truncation llamaban a run_snapshot() (ver
# nota de retiro mas arriba) — 100% de su contenido probaba
# hooks/precompact-snapshot.py, eliminado.


# RETIRADO (memoria v2, 2026-08-05): test_hook_robustness y
# test_nested_prefixes llamaban a check_hook_msg() -> PRE_HOOK
# (hooks/pre-validate-commit-trailers.py), borrado entero junto con el
# resto del sistema de memoria v1 (confirmado: check_hook_msg() devuelve
# rc=2/"can't open file" para todo, no el resultado real que estos tests
# esperaban). Su sucesor, hooks/customs.py, no tiene el concepto de
# fixup!/squash!/amend!/Merge/Revert -- esos eran prefijos que el v1
# TOLERABA para no bloquear un rewrite de historia local legitimo;
# customs.py resuelve la misma familia de casos de otra forma (rebase con
# --continue/--skip/--abort pasa siempre, ver TestRebasePassthroughOnlyForInFlightOperations
# en tests/memory/test_customs_hook.py) -- no hay un equivalente 1:1 al
# que redirigir estos dos tests sin inventar cobertura no pedida.

# NOTE (2026-07-25): test_post_hook_exit_code was removed here — it invoked
# post-validate-commit-trailers.py, which was deleted outright (dead code in
# the wrapper's path; see test_memo_category_deadend_contract.py's
# retirement note for the full history). pre-validate-commit-trailers.py
# never inspected tool_output/exit_code at all — it only blocks the tool
# invocation BEFORE execution based on the command string — so there was no
# live pre-hook behavior to adapt this test toward, and now the hook itself
# is gone too.


# RETIRADO (PLAN-CONSTRUCCION.md paso 9.3): test_delimiter_collision
# llamaba a run_snapshot() (ver nota de retiro mas arriba) — probaba que
# los pipes no rompian el snapshot de hooks/precompact-snapshot.py,
# eliminado.


# RETIRADO 2026-08-26: test_deep_search (y sus generadores exclusivos) —
# ver la nota completa al principio de este fichero.


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
