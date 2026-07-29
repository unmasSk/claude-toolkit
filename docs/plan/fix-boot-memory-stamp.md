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

## AMENDMENT v2 (tras Verify — Moriarty FALLA T1)

**Hallazgo (Moriarty, canal real):** el relabel v1 miente al revés. (A) Un fetch FALLIDO trunca `.git/FETCH_HEAD` a 0 bytes y refresca su mtime (efecto real de git, verificado) → boot siguiente dentro de la ventana muestra `remote (synced 0s ago)` sin haber sincronizado jamás. (B) Un fetch exitoso a un remote NO relacionado (IDE/mirror) produce el mismo falso "synced". Cerberus además señaló que el comentario SEC-LOW-001 (`boot_git_checks.py:449-459`, "el mtime nunca alimenta un freshness claim") quedó contradicho por la rama nueva.

**Decisión v2 (90d096d):** la fuente de la señal de frescura deja de ser el mtime de FETCH_HEAD. El boot escribe un **stamp propio de éxito** SOLO cuando SU fetch al upstream de memoria termina con exit 0; el rate-limit del gate y el rótulo `remote (synced Ns ago)` leen ese stamp. Sin stamp o stamp viejo → se intenta el fetch (fail-open hacia fetchear). El fetch en sí sigue intacto.

### Task 6: Dante — contrato RED v2 (stamp de éxito propio)
**Files:** tests/test_boot_freshness*.py
- [ ] Vector A en rojo: fetch fallido → segundo boot < 300s NO dice `remote (synced` (dice LOCAL/unverified) y SÍ reintenta el fetch (el fallo no rate-limita)
- [ ] Vector B en rojo: fetch real exitoso a remote secundario (FETCH_HEAD tocado) → boot NO dice `remote (synced` sin haber fetcheado su upstream; fetchea de verdad
- [ ] Round-trip del stamp propio: boot con fetch OK escribe el registro; boot siguiente < 300s lee `rate_limited` y rotula `remote (synced Ns ago)` (canal subprocess real, valores derivados del contrato)
- [ ] Migración: repo sin stamp (primer boot tras upgrade) → fetchea
- [ ] Verificar RED por la razón correcta; el contrato v1 que siga siendo válido (relabel del texto, estados de fallo) no se toca

### Task 7: Ultron — GREEN v2
**Depends on:** Task 6
**Files:** lib/boot_git_checks.py (gate + escritura del stamp), posiblemente hooks/session-start-boot.py
- [ ] Escritura del stamp de éxito (ubicación: `.claude/.unmassk/`, vía `verify_path_within_project()` + patrón symlink-safe; stdlib-only; Windows-aware desde el diseño)
- [ ] `_fetch_gate_and_rate_limit` lee el stamp propio (edad 0<=age<300s → rate_limited con esa edad); FETCH_HEAD mtime deja de alimentar gate y rótulo
- [ ] Actualizar el comentario SEC-LOW-001 (:449-459) — hallazgo de Cerberus — para reflejar la nueva fuente
- [ ] Fail-open intacto: error leyendo/escribiendo el stamp nunca rompe el boot
- [ ] GREEN en los 3 ficheros del contrato + suite completa

### Re-Verify (dentro de Task 3)
- [ ] Moriarty re-ataca los vectores A y B contra el stamp propio + intenta corromper el stamp mismo (contenido basura, symlink, borrado)
- [ ] Cerberus re-revisa el diff v2
- [ ] Yoda veredicto final 110

## AMENDMENT v3 (Moriarty ronda 2 — FALLA T1 identidad por alias)

Copiar el stamp entre repos con alias comunes (origin/main) producía falso 'synced' (plantillas, backups). Decisión 787b698: identidad del stamp = alias + branch + **URL real** (`git remote get-url`) + `schema_version` (1→2, mismatch → ausente). Misma ronda: los 6 hallazgos de Cerberus v2 (S1 fidelidad de edad en no_remote vía `_read_stamp_age_by_alias_only` confinada a esa rama; S2 split a `lib/boot_fetch_stamp.py`; S3 pinning unitario del stamp; S4 assert de siembra; N1 comentario chmod Windows; N2 validación schema_version). Cerberus re-review v3: LGTM 0/0/0.

## AMENDMENT v4 (Moriarty ronda 3 — FALLA T1 fallback de get-url)

Con `remote.<alias>.url` VACÍA, `git remote get-url` devuelve el alias literal ("origin"), que pasaba como URL resuelta → stamp copiado entre repos degenerados volvía a colar. Decisión 174d82b: `url == remote_name` → identidad NO resuelta (rama no_remote, sin confianza y sin escritura de stamp; guard en `_check_remote_is_live`, único call site de get-url). Escalada de Ultron resuelta: el guard cierra también la escritura, así que el fixture del test cross-repo se re-sembró vía read-mutate-rewrite de un stamp sano (Dante). Moriarty check final v4: **AGUANTA** 12/12 (PoC ronda 3 muere, sin esquivas, caso legítimo name==url degrada honesto a LOCAL, regresión 4/4).

**Modelo de amenaza residual documentado (aceptado, juicio de Yoda: línea defendible):** (a) escritura local directa en `.claude/.unmassk/` = acceso local total, fuera de alcance como el resto de cachés; (b) manipulación de git config local más allá de los casos degenerados cerrados; (c) name==url genuino degrada a LOCAL permanente (honesto, nunca miente).

## CIERRE — hallazgos de Yoda ronda 1 (NOT READY, evidencia no diseño)

- [x] Blocker: CI de Windows ROJO → RESUELTO en 2 iteraciones: el fix `.cmd` de Dante falló (House ronda 2: CreateProcess solo busca `.exe`, PATHEXT es de cmd.exe); fix definitivo = interceptor de Popen en capa Python (`tests/_git_intercept.py`, sitecustomize + monkeypatch, mecanismo único en 3 plataformas, shims de PATH eliminados, 3 skips de Windows retirados, mutation-killed). Windows verde en run 29125050400.
- [x] Blocker: wips pusheados (HEAD 3e971fa = origin/main); CI verde en ambas plataformas (run 29125050400; Ubuntu necesitó 2 reruns por la familia flaky preexistente → issue #61). Leído por Yoda directamente.
- [x] Minor: Cerberus pasó por el guard v4 — LGTM producción + 1 hallazgo en test (read-side redundante, verde por razón equivocada, cazado por mutación) corregido por Dante con mutation-check verificado.
- [x] Minor: este plan actualizado con v3/v4.
- [x] Obs: notas de Moriarty v4 commiteadas (e62ba37).

**VEREDICTO FINAL (Yoda, re-render): READY — GO. 101/110** (Security 9, Error handling 9, Architecture 9, Testing 10, Maintainability 9). Los 9 responden al modelo de amenaza residual risk-accepted (decisiones de Bex) y no a hallazgos accionables; el único hallazgo cosmético (estas casillas) queda corregido en esta edición.
- Nota de proceso (antipatrón re-pisado, ya memorizado): los push de decisiones arrastraron los wips intermedios a origin/main → el squash limpio de cierre ya no es posible sin force-push (prohibido). El cierre squashea solo lo no pusheado o cierra con commit final normal; la historia carga los wips esta vez.

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

**Status: COMPLETED** — issue cerrado; marcado en la limpieza del 2026-07-29 (censo de deuda). El plan quedó sin marcar al cerrar el trabajo: el paso 7 de Flow depende de que el orquestador lo recuerde, y no lo hizo.
