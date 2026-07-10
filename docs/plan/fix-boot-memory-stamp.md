# Fix Boot MEMORY Stamp Relabel — Implementation Plan

**Issue:** #60
**Branch:** main (trunk repo)
**Triage:** Standard
**Build mode:** test-first
**Created:** 2026-07-10

## Goal

El stamp `MEMORY:` del boot comunica estado bueno cuando la memoria está fresca (rate-limit con FETCH_HEAD < 5 min), y reserva `LOCAL` exclusivamente para fallos reales (failed / no_remote / unverified / never synced). El mecanismo de fetch no se toca.

## Decisions

- `ceef426` decision(plugin/boot): relabel del stamp (fresco=bueno, LOCAL solo fallos reales) + no enmascarar estado más fresco. Mecanismo de fetch intacto.
- **Refinamiento de diseño (este plan):** el "no pisar estado más fresco" se satisface con el propio relabel — la rama `rate_limited` solo se alcanza con FETCH_HEAD < 300s (edad medida, gate en `_fetch_gate_and_rate_limit`), así que todo stamp que un boot posterior escriba pasa a ser veraz y bueno. No se añade maquinaria de comparación entre boots (menos código, misma garantía). Cerberus valida goal-backward este razonamiento.
- **Nuevo texto para `rate_limited`:** `MEMORY: remote (synced {age} ago)` — verbo `synced` (vs `fetched`) mantiene distinguibles las dos ramas para depuración; desaparecen `LOCAL` y `fetch skipped` de este estado. Caso `age=None` (defensivo, no alcanzable por el gate): `MEMORY: remote (synced ? ago)`.
- **omawaMapas:** verificado por Bilbo — el fetch funciona (rc=0, 0.77s, osxkeychain OK, upstream coherente). Era este mismo bug de rótulo. Sin trabajo adicional.

## Contrato actual (Bilbo)

- Render: `_render_confirmed_fetch_stamp` en `lib/boot_git_checks.py:799-810`; rama `rate_limited` en `:809` produce `MEMORY: LOCAL — fetch skipped (rate-limit, {age} ago)`.
- `render_memoria_stamp` `:813-834`: prioridad `history_related=False` > confirmed (fetched/rate_limited) > unverified fallbacks. Fallos reales (`failed`/`no_remote`/`skipped_gate`) NO cambian.
- Consumidores: banner stdout + boot-log-latest.txt (session-start-boot.py:368-381, 187-233). PULL DIRECTIVE independiente de fetch_state — no se toca.
- Nadie más parsea el texto literal salvo 2 tests.

## Tasks

### Task 1: Dante — contrato RED (nuevo etiquetado)
**Files:** tests/test_boot_freshness_hardening.py, tests/test_boot_freshness.py
**Steps:**
- [ ] Actualizar las 2 expectativas literales de `rate_limited` en `TestRenderMemoriaStamp::test_states_and_ages` (:400-401) al nuevo contrato: `MEMORY: remote (synced 45s ago)` / `MEMORY: remote (synced ? ago)` → deben quedar RED
- [ ] Reforzar `test_rate_limited_state_shows_stamp` (test_boot_freshness.py:362-375, canal subprocess real §34): asertar que la línea MEMORY del segundo boot empieza por `MEMORY: remote (synced` y NO contiene `LOCAL` ni `skipped` → RED
- [ ] Guardia de regresión: los estados de fallo real (`failed`, `no_remote`, age None) SIGUEN produciendo `LOCAL`/`unverified` (ya cubierto por tests existentes — confirmar que quedan verdes, no tocarlos)
- [ ] Verificar RED: `python3 -m pytest unmassk-toolkit/tests/test_boot_freshness_hardening.py unmassk-toolkit/tests/test_boot_freshness.py` con exit code real (sin pipe a tail/head) — los tests nuevos/modificados fallan, el resto verde

### Task 2: Ultron — GREEN (relabel)
**Depends on:** Task 1
**Files:** lib/boot_git_checks.py
**Steps:**
- [ ] Cambiar la rama `rate_limited` de `_render_confirmed_fetch_stamp` (:809) al nuevo texto `MEMORY: remote (synced {age_txt} ago)`
- [ ] Ajustar la prosa de comentarios/docstrings adyacentes (:799-802, :785-798) que asumen la semántica vieja ("LOCAL" para rate-limit)
- [ ] NO tocar: gate, fetch, PULL DIRECTIVE, session-start-boot.py, estados de fallo
- [ ] Verificar GREEN: los 3 ficheros de test del stamp completos, exit code real

### Task 3: Verify (Cerberus + Dante hardening + Moriarty + Yoda)
**Depends on:** Task 2
**Steps:**
- [ ] Cerberus: goal-backward — ¿el relabel cierra de verdad la percepción de fallo? ¿el razonamiento "relabel ⇒ no hace falta comparación entre boots" tiene agujeros? ¿algún literal esperado hand-typed en el round-trip? (§34)
- [ ] Dante hardening: EXHAUSTION sobre la costura boot→boot-log (subprocess real): doble boot rápido, boot con fallo de red tras boot bueno, clock skew ya cubierto
- [ ] Moriarty: sabotaje de la costura — ¿puede un estado malo renderizarse como bueno? (p.ej. FETCH_HEAD movido por git externo dentro de la ventana tras un fetch fallido)
- [ ] Yoda: veredicto 110 con regla de evidencia round-trip mecánica
- [ ] Si T1/T2 → volver a Task 2 con hallazgos

### Task 4: Alexandria — documentar (3 audiencias)
**Depends on:** Task 3
**Steps:**
- [ ] skills/unmassk-gitmemory/SKILL.md:64 — reagrupar `rate_limited` con `fetched` como estados "confirmado fresco"; catálogo con los textos nuevos
- [ ] skills/unmassk-gitmemory/SKILL.md:62 — corregir dato obsoleto independiente: timeout 3s → 10s (v1.19.2)
- [ ] CHANGELOG.md raíz `[Unreleased]` — entrada del fix
- [ ] Revisar README/docs por menciones del stamp (Bilbo no encontró más, confirmar)

### Task 5: Close — squash + release + CI
**Depends on:** Task 4
**Steps:**
- [ ] Suite completa verde (exit code real)
- [ ] Gitto: squash de los wips del pipeline en commit limpio con trailers + push
- [ ] Release: `python3 bin/release.py unmassk-toolkit 1.19.3` (dry-run primero)
- [ ] Verificar CI verde (`gh run list`/`gh run watch`)
- [ ] Cerrar #60, marcar plan COMPLETED, context()

## Wave Map

- Wave 1: Task 1
- Wave 2: Task 2
- Wave 3: Task 3 (Cerberus ∥ Moriarty ∥ Dante hardening, luego Yoda)
- Wave 4: Task 4
- Wave 5: Task 5

## Plan Checker

- Decisión ceef426 → Tasks 1-2 (relabel) + refinamiento documentado arriba (no-pisar vía relabel). ✔
- Cada task tiene verificación con comando y criterio. ✔
- Dependencias explícitas. ✔
- Costura §34: Dante posee el round-trip (Task 1/3), Moriarty sabotea (Task 3), Yoda evidencia mecánica (Task 3). ✔
