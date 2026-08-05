---
name: memoria-v2-fase0-conftest-notes
description: unmassk-memory (sistema de memoria v2) FASE 0 paso 0.3 — tmp_repo fixture + esqueletos autorizados de register_note/assert_index_contains
metadata:
  type: project
---

`unmassk-memory-v2/tests/conftest.py` (rama `feat/memoria-v2`, paso 0.3 de
`docs/memoria-v2/PLAN-CONSTRUCCION.md`) es un conftest **nuevo**, no una
copia de `unmassk-toolkit/tests/conftest.py` — restricción A del plan
("desde cero, sin reutilizar nada del v1"). No trae la infraestructura de
identidad git de fallback (`_DEFAULT_GIT_IDENTITY_ENV`) ni el disable de
`gc.auto` del v1: la máquina de desarrollo tiene `user.name`/`user.email`
globales confirmados en `~/.gitconfig`, así que `git commit --allow-empty`
funciona sin inyección de entorno. Si algún día esto corre en un runner
sin identidad global, el fixture `tmp_repo` fallará ruidosamente (assert
en `rc_commit == 0`) — ese es el momento de portar el fallback del v1, no
antes.

**Patrón de esqueleto autorizado (no antipatrón de TODO abandonado):**
`register_note()` y `assert_index_contains()` en ese conftest.py lanzan
`NotImplementedError` a propósito. El propio plan (fila 0.3) dice
textualmente "los helpers de nota se completan en la fase 2" — cuando
existan `lib/notes.py` (paso 2.4) y `lib/indexes.py` (paso 2.2). Escribir
un cuerpo real ahora habría duplicado la lógica de validación/commit que
el plan exige que viva en una sola pieza (restricción D). Ningún test de
FASE 0 llama a estos dos helpers — el test tonto (`test_conftest_smoke.py`)
solo ejercita `tmp_repo` + `run_git()`.

Comando de verificación exacto (pyproject.toml raíz no recoge
`unmassk-memory-v2/tests` por defecto — `testpaths` sigue apuntando solo a
`unmassk-toolkit/tests`, no se tocó):
```
python3 -m pytest unmassk-memory-v2/tests/test_conftest_smoke.py -q
```

Cuando llegue la FASE 2 (paso 2.9, "tests de la transacción, los dos
casos del paso 2.4 contra un repo real"): reescribir estos dos helpers
para invocar `lib/notes.py`/`lib/indexes.py` de verdad, nunca fabricar a
mano el formato de línea de índice (eso vive en `lib/format.py`, paso
1.5 — mismo espíritu que la regla §34 de unmassk-standards, no fabricar
ground truth).
