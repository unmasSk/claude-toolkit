# Roadmap v2 — Upgrade del unmassk toolkit

> Síntesis de la sesión de diseño a tres bandas (Bex + dos IAs).
> La **lista completa de 42 ideas** está al final, para el archivo. La **parte de arriba** es para la semana que viene.
> Estado de partida: **el kit ya funciona muy bien.** Esto es pulir algo que entrega valor, no apagar un incendio. No hay urgencia → no se abren frentes en paralelo.

---

## Estado — 2026-06-08 (lunes, LEER PRIMERO)

**HECHO esta sesión (commiteado en `main`, aún SIN publicar — instalado sigue v1.1.0):**
- [x] **Portero de recall** (#1 + #2 + #4) — hook `PreToolUse/Task` que inyecta memoria al subagente, whitelist por `subagent_type`, live-read git. Yoda 110/110, 51 tests. **La otra mitad del recall, ya enganchada.**
- [x] **Build-mode** (NUEVO, no estaba en el roadmap) — dos modos de escritura: lineal vs test-first/ATDD; Flow es el router (Step 4) y delega a `references/linear.md` y `test-first.md`; el orquestador elige por tarea; Build Mode en Ultron/Dante.
- [x] **Generador de los 5 bloques del CLAUDE.md** (NUEVO) — `lib/managed_blocks.py` (fuente única); el generador escribe toolkit/protocols/caveman/communication/build-mode en cada proyecto, idempotente.
- [x] **Calibración anti-sobreguardado** (#20 aplicado) — scope test (reglas de proyecto NO van a `remember` global), filtro hecho-estable, timing≠volumen, `remember(claude)` gana "When it does NOT fire".
- [x] **Reencuadre "never commit to main" por tipo de repo** — trunk vs gitflow, marcador commiteado, fail-closed.
- [x] **Core** (#21 parcial, #38 parcial) — Ultron=código de producción (no docs/skills); standards on-demand en orquestador; quitado el volcado redundante del boot.

**PENDIENTE INMEDIATO (el thread abierto — ver lista de tareas visual):**
- [ ] Completar `close-session` (bump/changelog/limpieza) + su hook de disparo (Stop/PreCompact).
- [ ] Construir/instalar las 3 skills de protocolo (lifecycle, grill, council) — el CLAUDE.md las nombra pero son borradores.
- [ ] Definir el bloque `communication` (placeholder vacío).
- [ ] Publicar: bump 1.2.0→1.3.0 + CHANGELOG. **Nada de esto está vivo hasta publicar.**

**OJO (causa del lío de hoy):** metimos el MENÚ (protocols en el CLAUDE.md) ANTES de construir las skills. El CLAUDE.md nombra cosas que aún no existen.

---

## Estado — fin de sesión 2026-06-05 (sesión anterior)

**HECHO y publicado en `main` (v1.2.0, cada uno 110/110 de Yoda, pipeline completa):**
- ✅ **Buscador de recall** (Cubo 2, nivel i) — `unmassk-toolkit/lib/recall.py` + `bin/git-memory-recall.py`. Busca memoria por palabra con ranking idf, dedup, historia completa, tokeniza alfanuméricos (BM25/v2/RS256), sanitiza inyección. Probado en uso real. **Merged.**
- ✅ **Eliminado el subsistema de seguimiento de contexto** (pre-tarea, no estaba en el roadmap original): context-writer + avisos de % + statusline, con auto-cura del statusline al actualizar (no rompe instalaciones viejas). **Merged.** Efecto: cerró el `shell=True` (issue #48).
- ✅ CHANGELOG `[Unreleased]` (Alexandria) + bump **1.1.0 → 1.2.0** (plugin.json + marketplace.json).
- ✅ Decisiones de diseño persistidas en git-memory: plugin-no-MCP, recall-por-hook, vectores-diferidos, graphify (robar algoritmo/adoptar nativo), curador=Gitto.

**⏳ SIGUIENTE LADRILLO (empezar por aquí):** el **hook "portero"** — la OTRA mitad del recall. Un hook `PreToolUse/Task` que engancha `lib/recall.py` para **inyectar la memoria en el prompt del subagente automáticamente**. ⚠️ El buscador existe pero **NO está enganchado todavía** → el auto-recall aún no ocurre en el sistema. Esto es lo que lo hace útil de verdad.

**PENDIENTE (sin empezar):**
- #6 recall del orquestador (hook `UserPromptSubmit`, medir coste de inyección por turno antes).
- #19 gate "done-sin-merge"; #18 Exit Gate de seguridad de Ultron como **script real** (no checklist).
- El **bump no está gateado** en el merge → mejora de gate (igual que done-sin-merge).
- Cubo 3 entero: curador, madurez (draft/validated/core), grafo bicapa, MCP como superficie, higiene.
- **Bug:** ruta rota de `scaffold.py` en `unmassk-flow-stack/SKILL.md` (apunta a `flow-stack-selection`, no existe).
- **Huecos de protocolo** (#22/#23/#24): continuar/escanear proyecto existente (no hay), comunicación (mínimo), plantilla de prompt a agente, conexión scaffolding↔memoria.
- Evaluar 4 skills de **mattpocock** (triage/caveman/grill-me/handoff) para #42.
- Cerrar issue **#48** a mano (gh del bot sin permiso de cierre).

**Cómo retomar exactamente:** el boot lee git-memory y muestra RESUME con el último `context()` (`b0bc77f`) + todas las decisiones por scope (plugin/memory, /recall, /graph, /curator). Lee este roadmap. Empieza por el hook portero.

---

## 0. Principio rector (la lente que resuelve la mitad de las dudas)

**Proceso → gate. Información → memoria + recall.**

- Si algo *debe ocurrir siempre* (seguir la pipeline, revisar antes de cerrar) es **proceso**: se fuerza con un **gate** (hook que bloquea), nunca con una nota.
- Si algo *es un hecho* (este proyecto usa Next.js, decidimos Redis) es **información**: va en **memoria**, y un **recall forzado** la sirve cuando toca.
- Síntoma del error de categoría: un `remember` que empieza por un verbo de acción ("seguir", "llamar", "no saltarse") es proceso disfrazado de memoria. Acaba guardado 114 veces sin efecto.

**Verdad sobre todo:** lo voluntario dentro del agente no ocurre. Captura está forzada (hook), recall no existe (voluntario). Esa asimetría es la raíz de casi todos los fallos.

---

## 1. La jerarquía real (no son 42 tareas iguales)

- **Raíz:** el principio del §0. No es una tarea, es la lente.
- **Cimientos (todo lo demás cuelga de aquí):**
  1. **Recall** — sin esto el conocimiento no circula.
  2. **Curador** — sin esto no hay grafo que dibujar ni madurez que rankear.
  3. **Gates** — sin esto los procesos se siguen saltando.
- **Hoja (lo más seductor = la trampa):** el mapa/grafo, el plugin/MCP, los vectores. No pueden existir hasta que el curador teja aristas y los gates produzcan hechos verificables que pintar.

---

## 2. Decisiones ya cerradas en esta sesión

- ✅ **Sigue siendo plugin, NO se convierte a MCP.** El push de los hooks no se puede replicar en MCP (pull). Un MCP puede sumarse *dentro* del plugin como superficie de llamada limpia, pero **sin LLM dentro** y **sin sustituir los hooks**.
- ✅ **Se empieza por memoria/recall.** Es el cimiento y está diseñado y verificado contra la plataforma.
- ✅ **Recall = hook `PreToolUse/Task`** (único canal real que llega al subagente: reescribir su `prompt`). `SubagentStart` y `additionalContext` NO sirven (van a la sesión principal, verificado).
- ✅ **El curador puede ser Gitto** (subagente Claude) → usa el LLM del host, **sin API key propia** salvo que se quiera curado autónomo en CI.
- ✅ **Vectores: diferidos — por NO ser cimiento ni prioritarios, NO porque el grafo los sustituya.** Cuidado con esto: el grafo solo conecta lo que ya está enlazado explícitamente (`Supersedes`, `Touched`, refs). Los vectores hacen algo que el grafo **no puede**: encontrar relaciones que *nadie enlazó* (parafraseo, vocabulario cruzado, arranque en frío). Es un valor **distinto**, no "la mayoría" del grafo. Se difieren porque no son fundación — y **se reabren el día que el grafo se quede corto en búsqueda difusa.** Cuando lleguen, como índice derivado en sidecar.

---

## 3. Los tres cubos (cómo se ejecuta)

### 🟢 Cubo 1 — Quick wins (arreglos de una tarde, independientes, esta semana)
No dependen de nada, mejoran hoy, no se rompen entre sí. Se hacen sueltos, sin abrir un proyecto.

- [ ] **#21** Cargar `unmassk-standards` también en el **orquestador** (hoy solo lo cargan los agentes obreros; el boot solo inyecta core+gitmemory+CALIBRATION). → línea de config.
- [ ] **#7** Decidir el rol de **Gitto** (hoy listado en el roster, nunca invocado): lo reemplaza el hook de recall, o se formaliza.
- [ ] **#13** Que las `decision()` registren los **callejones descartados** (qué se rechazó y por qué), no solo la conclusión. → es hábito + ajuste de prompt, no subsistema.
- [ ] **#19** Cerrar la puerta de escape **"done sin merge"** para que el merge-gate que YA existe (Cerberus+Alexandria) sea inevitable. → pequeño, alto impacto.

### 🟡 Cubo 2 — El cimiento (UNO, en singular): el RECALL
Tu siguiente *proyecto*. No se empieza el curador hasta que esto funcione y se haya usado una semana.

**MVP (nivel i):**
- [x] **#1** Hook `PreToolUse/Task` que inyecta memoria en el prompt del subagente antes de trabajar. ✅ (portero, 110/110)
- [x] **#2** Whitelist por `subagent_type` (decide *si* dispara; no a Bilbo/Plan). ✅
- [ ] **#3** Ranking blando rol+scope (decide *qué* prioriza; nunca exclusión dura). ⏳ (el portero usa query=prompt; el ranking blando sigue pendiente)
- [x] **#4** Lectura de git **en vivo** en cada spawn (no caché). ✅ (recall hace live-read)

**Inmediatamente después (sobre el mismo cimiento):**
- [ ] **#5** Capa C: el orquestador pasa el scope exacto, gateado en `unmassk-flow`.
- [ ] **#14-16** El bucle auditor→memo→recall (commit inmediato del antipatrón + live-read; tipos de commit por agente para que el estado salga de un hecho verificable).

**Decisión aparte — NO es la misma tarea (medir coste antes de soltarla):**
- [ ] **#6** Recall del **orquestador** (gemelo `UserPromptSubmit` del `[memory-check]`). Es **otro hook, otro punto de inyección, otro perfil de coste**: el de subagentes es acotado (un spawn, un trabajo); este es **continuo en cada turno** y puede inflar tu contexto principal rápido. Se decide por separado tras medir cuánto pesa — **no pegado al MVP de subagentes.**

**DoD del cubo:** recall de subagentes funcionando + usado una semana antes de tocar el cubo 3.

### 🔴 Cubo 3 — Congelado (anotado, intocable, hasta que el cimiento exista)
No es degradarlo: es protegerlo de empezarlo antes de tiempo y hacerlo mal.

- **Curador pesado** (#8 madurez en sidecar, #9 dream/consolidación, #10-12 Gitto-curador de dos velocidades, agente write-only).
- **Gates avanzados** (#18 Exit Gate de seguridad como script real que bloquea).
- **Protocolo Enterprise / arranque** (#22 contrato Enterprise al crear proyecto, #23 protocolos empezar/continuar/escanear, #24 auto-uso fiable de skills): **originaron media conversación** ("Claude no hace bien el arranque, no lee la skill enterprise"). Son **subsistemas**, no quick wins, y dependen de que recall+memoria existan para sembrar el árbol. Aquí, intocables hasta su turno — **NO en tierra de nadie.** (#21, su hermano de una tarde, ya está en Cubo 1.)
- **Mapa / grafo** (#25-33): mapa neuronal autorrellenado, color=estado, dos grafos superpuestos (decisiones↔código vía `Touched:`), aristas de proceso, robar el algoritmo de graphify (nx.Graph genérico) para la capa git + adoptarlo nativo para la capa código.
- **Plugin / autonomía** (#34 MCP como superficie de llamada sin LLM, #35 lenguaje natural sin slash-commands, #36 roadmap+backlog como documentos).
- **Higiene** (#39 podar agentes, #40 adelgazar MDs, #41 auditar bin/+lib/, #42 incorporar skills nuevas que merezcan la pena).

### ⚪ Apartado (fuera de los cubos de "construir")
- **#37** Nota de **preferencias de colaboración** (no perfil psicológico; observable, **visible y editable**, nunca oculta). → pensarla despacio, no meterla en un sprint.
- **#38** Revisar el **boot** (sospecha de que entierra lo importante). → diagnóstico primero (leer el código), *luego* decidir si hay algo que hacer. No darlo por malo sin verlo.

---

## 4. Dependencias (qué bloquea a qué)

```
Principio §0 (lente)
   │
   ├── Recall (cimiento) ──────────► habilita el bucle de aprendizaje y el recall del orquestador
   ├── Gates (cimiento) ───────────► producen hechos verificables (color del mapa, estado del pipeline)
   └── Curador (cimiento) ─────────► teje el grafo de aristas + la madurez
                                          │
                                          ▼
                         Mapa/Grafo (hoja) ── necesita curador (aristas) + gates (hechos que pintar)
                                          │
                                          ▼
                         Vectores ── solo si léxico+grafo se quedan cortos (índice derivado)
```

---

## 5. Reglas de ejecución (la disciplina)

1. **Una cosa a la vez.** Terminarla, vivir con ella unas semanas, *luego* la siguiente.
2. **No mezclar escalas.** "Arreglo de una tarde" (#21) y "subsistema de un mes" (curador) no van en la misma lista de prioridad. Son listas distintas.
3. **No abrir frentes en paralelo.** El kit ya funciona → el lujo de no tener incendio no se desperdicia.
4. **La lista de 42 es para el archivo, no para la semana.**
5. **Color/estado siempre desde un hecho verificable en git**, jamás desde autodeclaración. Un mapa que miente es peor que no tener mapa.

---

## 6. Inventario completo (las 42, para no perder nada)

**Recall:** 1) hook PreToolUse/Task · 2) whitelist subagent_type · 3) ranking blando rol+scope · 4) live-read git · 5) capa C scope vía flow · 6) recall del orquestador · 7) rol de Gitto.

**Curador y madurez:** 8) madurez en sidecar fuera de git · 9) curador dream · 10) curador = Gitto (sin key) · 11) dos velocidades (colisión al escribir + lote al cerrar) · 12) curador write-only · 13) decisiones registran lo descartado.

**Bucle de aprendizaje:** 14) auditor→memo→recall · 15) live-read + commit inmediato · 16) tipos de commit por agente · 17) verificación de cierre (Argus→Ultron→Argus).

**Gates:** 18) Exit Gate de seguridad como script real · 19) cerrar atajo done-sin-merge · 20) principio proceso→gate / info→memoria.

**Protocolo Enterprise / arranque:** 21) standards al orquestador · 22) contrato Enterprise al crear proyecto · 23) protocolos empezar/continuar/escanear · 24) auto-uso de skills.

**Mapa / grafo:** 25) mapa neuronal autorrellenado · 26) color=estado (verde/naranja/rojo) · 27) dos grafos superpuestos (decisiones↔código) · 28) puente = trailer `Touched:` · 29) aristas de proceso por agente · 30) orden capa 1 = madurez+importancia+recencia+centralidad · 31) robar algoritmo graphify (git) + adoptar nativo (código) · 32) vectores como índice derivado diferido · 33) índice semántico del codebase para Ultron.

**Plugin / autonomía:** 34) MCP como superficie de llamada sin LLM · 35) plugin en lenguaje natural sin slash-commands · 36) roadmap+backlog como documentos.

**Memoria de colaboración:** 37) nota de preferencias de colaboración (visible, editable, no perfil psicológico).

**Higiene / complejidad:** 38) revisar el boot · 39) podar agentes · 40) adelgazar MDs · 41) auditar bin/+lib/ · 42) incorporar skills nuevas.

---

*Siguiente acción concreta: afinar el Cubo 1 (quick wins sueltos) o arrancar el diseño fino del MVP de recall (Cubo 2). Una, no las dos.*
