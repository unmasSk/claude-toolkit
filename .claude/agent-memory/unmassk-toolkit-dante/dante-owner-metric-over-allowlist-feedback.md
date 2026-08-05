---
name: dante-owner-metric-over-allowlist-feedback
description: owner prefers a computed metric over a hand-maintained exception/allowlist for any gate — reversed a real in-progress allowlist 2026-08-04
metadata:
  type: feedback
---

When a detector/gate needs to tolerate a legitimate special case (e.g. a
function with zero production callers that a test still needs as a §34
second-opinion oracle), do not default to a hand-written exception list —
even a "safe" one with per-row justification and self-verification against
re-reading the real file. Propose a **computed metric with two independently
counted branches** first (e.g. production-caller count vs test-usage count),
and let a **fixed threshold rule** decide red/not-red. Only fall back to a
named-exception table if no metric can express the distinction.

**Why:** owner's own words, mid-task, reversing an allowlist I had already
built and partly tested for `indexes.counts` (`docs/memoria-v2/PIEZAS.md`
Sec.13 boundary gate, [[piezas-sec13-boundary-tests-notes]]): *"con dos
números no hay nada que decidir — 'producción 0, tests 3' es un HECHO, no un
veredicto. Se acabó la lista de perdonados — que era una puerta trasera
esperando a que alguien la ampliara hasta vaciar el detector de sentido."* An
allowlist, however well-guarded, is still a list someone has to remember to
add to and can be widened by anyone without re-deriving the justification. A
metric with a fixed threshold has no such surface — the same rule that
protects `indexes.counts` today protects the next legitimate case tomorrow
without a human writing a new row.

**How to apply:** before building any allowlist/exception mechanism for a
gate (dead-code detector, lint suppression, coverage carve-out), first ask
"can the distinction I'm trying to encode be expressed as a count or ratio
instead of a named list?" If yes, build that — the owner will pick it over an
allowlist every time, per this incident. Still keep the anti-vacuity fire
tests either way (prove the rule fires on a planted violation AND does not
suppress a real one) — that part of the discipline survived the pivot intact.

Also operationally: when an in-progress edit gets reversed mid-task and the
file was never committed (`git status` shows `??`, untracked), there is no
`git checkout`/`stash` to fall back to — revert by hand, re-applying the
exact prior text via Edit, then verify by rerunning the test suite before
building the replacement on top.
