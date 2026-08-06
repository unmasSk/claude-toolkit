# Robustez de memoria + endurecimiento de CI — Plan

**Issue:** — (trunk, sin issue de GitHub)
**Branch:** main (trunk)
**Triage:** Big
**Build mode:** test-first para hooks/comandos de memoria; linear para CI y docs
**Created:** 2026-08-06

## Goal
Cerrar los huecos de robustez del sistema de memoria v2 y el verde-en-falso de la CI, dejando el conocimiento escrito donde el siguiente Claude lo lea solo.

## Seam declaration
Sí hay seam productor↔consumidor: los hooks leen ficheros de memoria (`config.json`, `zones.json`) escritos por los comandos gitmem. Verify tira de Moriarty + Yoda.

## Decisions
- **Aduana ante fichero de memoria ilegible:** bloquear con salida clara — sigue frenando commits normales, pero deja pasar los comandos de rescate (`git merge/rebase --abort/--continue`) y el mensaje explica cómo reparar. (Usuario, 2026-08-06.)
- **chatroom NO se toca** — es un subproyecto de referencia. Se le QUITA el workflow de CI (`chatroom-ci.yml` se elimina); no se testea ni se mantiene en este repo. (Usuario, 2026-08-06.)

## Tasks

### Task 1 — CI: eliminar chatroom-ci.yml [linear · Ultron]
**Files:** `.github/workflows/chatroom-ci.yml` (borrar)
- [ ] Eliminar el workflow por completo; no tocar nada dentro de `chatroom/`
- Resuelve el T1 (verde en falso del frontend) por eliminación: sin CI, no hay check engañoso.

### Task 2 — CI: endurecer los dos workflows del toolkit (T2/T3) [linear · Ultron]
**Files:** `.github/workflows/toolkit-ci.yml`, `.github/workflows/plugin-tests.yml`
- [ ] `permissions: contents: read` a nivel raíz en ambos
- [ ] Pinear dependencias (pytest/pyyaml; numpy/trimesh/manifold3d/pyserial/cadquery)
- [ ] checkout/setup-python a @v6; `concurrency: cancel-in-progress`; cache de pip

### Task 3 — Memoria: aduana no debe atascar (GRAVE, control hook) [test-first · Dante→Ultron]
**Files:** `hooks/customs.py`; test `tests/memory/test_customs_hook.py`
- [ ] Dante: contrato rojo — config/zones ilegible ⇒ (a) commit normal sigue bloqueado con mensaje que explica la salida; (b) `git merge/rebase --abort/--continue` PASAN
- [ ] Ultron: implementar hasta verde. **Diff mostrado antes de commit (control hook).**

### Task 4 — Memoria: gate de cierre no debe fallar callado (GRAVE, control hook) [test-first]
**Files:** `hooks/stop-dod-gate.py`; docstring `lib/memory/config.py`
- [ ] Dante: contrato rojo — config corrupto ⇒ el gate AVISA (no calla), distinto de "no configurado"
- [ ] Ultron: implementar + corregir el docstring de config.py que promete "nunca en silencio". **Diff antes de commit.**

### Task 5 — Memoria: zones list / doctor no deben enmascarar ausencia [test-first]
**Files:** `bin/memory/zones.py`, `bin/git-memory-doctor.py`
- [ ] Dante: contrato rojo — `zones list` distingue "no existe" de "existe vacío"; doctor comprueba zonas
- [ ] Ultron: implementar reutilizando la distinción de `health.memory_mounted()`

### Task 6 — Doc: la regla de las zonas donde se lea siempre [linear · Orquestador + Ultron]
**Files:** `unmassk-toolkit/skills/unmassk-memory/SKILL.md` (HECHO), texto del aviso en `lib/memory/health.py`/`boot.py` (Ultron)
- [x] Orquestador: principio "una zona es un acto de juicio, no un default de script" añadido al cuerpo de "The two zones" (inglés).
- [ ] Ultron: que el aviso de arranque (legacy sin destilar) nombre `references/distill.md`

## Wave Map
- Wave 1: Task 1+2 (Ultron, CI) ‖ Task 3 contrato (Dante, aduana)  ← EN CURSO
- Wave 2: Task 4+5 contratos (Dante) ‖ Task 3 impl (Ultron)
- Wave 3: Task 4+5 impl (Ultron) ‖ Task 6 aviso boot (Ultron)
- Wave 4: Verify (Cerberus+Argus → Moriarty → Yoda) sobre hooks/comandos
- Wave 5: Alexandria docs (3 audiencias) → Close (suite: `python3 -m pytest unmassk-toolkit/tests -q`)

## Notas de hallazgos colaterales (para el feedback, no tareas de código)
- **Deuda de tamaño:** `customs.py` en 580 líneas (>500, el techo que el repo aplica). Decisión del usuario (2026-08-06): NO partir aún — no crear `customs_rejections.py`. Cortar cuando él lo diga.
- **Residuos en `.claude/` (Bilbo, NO borrados — decisión del usuario):** `.unmassk/{boot-fetch-stamp.json, glossary-cache.json, context-status.json, context-warn-state.json, .message-counter}` + `agent-memory/…-bilbo/scopes.json` son residuos del sistema v1 (código generador ya borrado). Deuda `.gitignore`: 6 líneas a rutas viejas + 1 duplicada. Limpieza pendiente de autorización.
- El marcador `Status: COMPLETED` no se aplica a los planes → el gate "one feature in flight" de Flow siempre da falso positivo.
- `git-memory-repair.py` no conoce `config.json`/`zones.json` (no puede reparar el atasco de la aduana).
- No hay `.github/dependabot.yml` para actions.
