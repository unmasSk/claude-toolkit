# Boot Simplification Implementation Plan

**Issue:** #63
**Branch:** feat/issue-63-simplificacion-boot
**Triage:** Standard
**Build mode:** test-first ligero (puntos 1-3: cambios de comportamiento sin cobertura actual); lineal (4, 6); docs-only (5)
**Created:** 2026-07-11
**Modo de sesión:** automático hasta acabar (Bex); merge del PR reservado a Bex. Tests solo donde el cambio lo pida.

## Goal

Reducir la superficie del arranque: menos trabajo por boot/mensaje, avisos solo donde sean accionables, migraciones jubiladas, docs alineadas con la realidad. Principio: el boot lee e informa, escribe lo mínimo.

## Decisions

- 0f5af98 (alcance de 6 puntos firmado por Bex) + matices del mapa de Bilbo (boot-simplification-63-map.md):
  - Punto 3 resulta ser BUG: `boot_health.py:52` `REPO_BASE_DIR = dirname³(__file__)` apunta en producción a la carpeta de cache de versiones → compara una versión cacheada contra otra. Fix: detectar de verdad si hay repo fuente (solo el dev-repo del toolkit); sin fuente → sin chequeo, sin aviso.
  - Punto 5 sin código que quitar (el self-healing solo existe como prosa en SKILL.md:491-505). Pasa a ser tarea de Alexandria: reescribir esa sección para describir la realidad (extracción en vivo desde git log = sanación pasiva; sin reconstrucción automática).
  - Punto 2: mover a SessionStart pierde detectar `/plugin update` a mitad de sesión — pérdida aceptada en el alcance firmado ("solo al arrancar la sesión").
  - Punto 6: conservar al menos un carácter no-ASCII en el texto acortado (test_encoding_contract.py:109-133 usa esta línea como escenario cp1252).

## Tasks

### Task 1: Dante — RED puntos 1-3 (proporcionado, granularidad aceptación)
**Files:** tests (nuevo o donde encaje por convención)
- [ ] P1: con manifest.version == versión del plugin, `session-start-crew.py` NO reescribe CLAUDE.md (mtime/contenido intacto); con versión distinta o sin manifest, SÍ regenera (fail-open)
- [ ] P2: `user-prompt-memory-check.py` ya no dispara needs_upgrade/instalador; el upgrade corre en SessionStart (mismo efecto tras un bump simulado de versión)
- [ ] P3: en un proyecto SIN repo fuente del toolkit (layout de cache simulado), cero avisos de drift; en el dev-repo real con drift genuino, el aviso sigue
- [ ] Verificar RED por la razón correcta; resto de suite intacta

### Task 2: Ultron — GREEN 1-4 + 6
**Depends on:** Task 1
**Files:** hooks/session-start-crew.py, hooks/user-prompt-memory-check.py, hooks/session-start-boot.py, lib/boot_health.py, lib/boot_migrations.py, bin/git-memory-upgrade.py
- [ ] P1: gate por manifest.version en session-start-crew (marcador ya existe; leerlo como boot_health.check_version_mismatch)
- [ ] P2: mover needs_upgrade + install --auto a SessionStart; UserPromptSubmit deja de evaluarlo
- [ ] P3: REPO_BASE_DIR honesto — chequeo solo si existe repo fuente real (marcador del dev-repo, p.ej. presencia de .git + estructura fuente); sin fuente → skip silencioso
- [ ] P4: jubilar `_migrate_runtime_to_unmassk` y `_migrate_untrack_generated_jsons` (pre-v1.0.0, 2026-03-17, cumplidas de sobra) del camino de boot; `_migrate_stale_context_writer_statusline` (2026-06-05) SE QUEDA un ciclo más (criterio conservador). Deduplicar la copia de `_migrate_runtime_to_unmassk` en git-memory-upgrade.py (una regla, un sitio: si el upgrade-path aún la necesita, vive solo allí). LISTA COMPLETA de lo jubilado → PR body para Bex.
- [ ] P6: acortar el texto [memory-check] (~577 chars → apuntar a ~1/3) conservando: la esencia (¿durable, no-derivable, no capturado ya? dedup/tombstone antes de añadir; silencio ante la duda) y ≥1 carácter no-ASCII (→). CALIBRATION.md ya lleva el matiz completo.
- [ ] GREEN: tests de Task 1 + suite completa verde

### Task 3: Verify (proporcionado)
**Depends on:** Task 2
- [ ] Cerberus: review del diff completo (focos: fail-open del gate P1 —manifest corrupto/ausente nunca rompe—, P2 no pierde el upgrade en sesiones largas ya abiertas, P3 no silencia el dev-repo, P4 no rompe upgrade-path)
- [ ] Argus acotado (añadido a petición de Bex): P1 parseo del manifest como input no confiable (JSON malicioso/gigante/symlink), P3 lógica de detección de rutas (traversal, symlinks, patrón verify_path_within_project donde aplique), P2 el subprocess movido conserva su hardening
- [ ] Moriarty acotado: solo P1-P3 (manifest basura, cache con N versiones, layouts raros) — sabotaje corto
- [ ] Yoda: veredicto final sobre la rama

### Task 4: Alexandria — docs
**Depends on:** Task 3
- [ ] SKILL.md:491-505: self-healing reescrito a la realidad (detección/aviso pasivo, sin reconstrucción automática)
- [ ] SKILL.md: actualizar lo que describa needs_upgrade por-mensaje (~:108) y el drift check
- [ ] CHANGELOG [Unreleased]
- [ ] CLAUDE.md managed: si algún bloque describe el comportamiento cambiado, tocar el GENERADOR (managed_blocks.py vía Ultron si es código), nunca el CLAUDE.md a mano

### Task 5: Close
**Depends on:** Task 4
- [ ] Suite completa verde; push de la rama; CI verde en la rama
- [ ] PR a main con: resumen, lista de migraciones jubiladas (para Bex), métricas antes/después (qué corre por boot y por mensaje)
- [ ] MERGE: lo hace Bex (parada única acordada). Release tras el merge.

## Wave Map
Wave 1: Task 1 → Wave 2: Task 2 → Wave 3: Task 3 (Cerberus ∥ Moriarty, luego Yoda) → Wave 4: Task 4 → Wave 5: Task 5

## Plan Checker
- 6 puntos firmados → P1-P3 (Task 1+2), P4+P6 (Task 2), P5 (Task 4 docs). ✔
- Pérdida aceptada P2 documentada. Bug P3 documentado. P5 sin código confirmado. ✔
- Tests proporcionados (directriz de Bex), suite completa como red. ✔

**Status: COMPLETED** — issue cerrado; marcado en la limpieza del 2026-07-29 (censo de deuda). El plan quedó sin marcar al cerrar el trabajo: el paso 7 de Flow depende de que el orquestador lo recuerde, y no lo hizo.
