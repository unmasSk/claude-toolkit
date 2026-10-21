# Recomendaciones: unmassk-toolkit frente a Gentle-AI

Fecha: 2026-10-01.

Comparación hecha leyendo el código de los dos proyectos, sin ejecutarlos:

- **unmassk-toolkit v1.43.0**, este repo.
- **Gentle-AI**, de Gentleman Programming (`github.com/Gentleman-Programming/gentle-ai`, commit `4740983`, línea v4).

Las cifras son aproximadas.

---

## 1. Qué es cada uno

| | unmassk-toolkit | Gentle-AI |
|---|---|---|
| Naturaleza | Marketplace de plugins para Claude Code (15 plugins) | Binario en Go que instala y configura agentes ya existentes |
| Distribución | Marketplace de Claude Code, `autoUpdate` | Homebrew (goreleaser) o `go install` |
| Agentes soportados | **Solo Claude Code** | **17**: Claude, Codex, Cursor, OpenCode, Gemini, Copilot, Windsurf, Kiro, Qwen… |
| Idioma interno | Español | Inglés |

No compiten exactamente en lo mismo: este toolkit es una **caja de herramientas muy amplia sobre Claude Code**, y Gentle-AI es un **instalador y orquestador que sirve para cualquier agente**.

---

## 2. Diferencias punto por punto

### Memoria persistente

| | unmassk | Gentle-AI |
|---|---|---|
| Dónde se guarda | Commits en el propio repo, con tipo por emoji y `Issue: #N`, más 8 ficheros índice | SQLite local de **Engram**, un binario aparte que se descarga de GitHub |
| Cómo accede el agente | CLI `gitmem` (note, search, rule, work, wip, next…) | Herramientas MCP (`mem_save`, `mem_search`, `mem_context`…) |
| Compartir con el equipo | Va con el repo (`git fetch`) | `engram sync` exporta a `.engram/`, y hay sincronización en la nube opcional |
| Qué obliga a guardar | Hooks: `customs.py` desvía `git commit` a `gitmem work` | Solo el prompt ("MANDATORY… call mem_save") |
| Coste | Ensucia el historial del proyecto, con commits vacíos incluidos. Requiere un repo git | Depende de un binario externo. El historial queda limpio |

**Gana unmassk** en auditabilidad, en que no depende de nada externo y en que los hooks obligan a guardar.
**Gana Gentle-AI** en que no ensucia el historial y funciona fuera de un repo git.

### Skills

| | unmassk | Gentle-AI |
|---|---|---|
| Número | **90** | **15** |
| Dominios | Pentesting (30), compliance (9), media (8), db (7), design (7), ops (7), electrónica (4), 3D, frontend, SEO, marketing, TS, humanizer | Casi todo proceso: PRs, commits, revisión, crear y mejorar skills. El único dominio técnico es `go-testing` |
| Material de apoyo | 1.206 ficheros de referencia y 257 scripts | Plantilla fija por skill (Activation Contract / Hard Rules / Decision Gates / Output Contract) |
| Profundidad | **Desigual.** `ops-iac` tiene 239 líneas y 20 scripts reales; `db-postgres` (82 líneas) y `pentesting-injection` (68) son índices hacia referencias de terceros | Corta pero homogénea, de 35 a 190 líneas |

**Gana unmassk** claramente en amplitud. **Gentle-AI** es más homogéneo de forma.

### Agentes

- **unmassk:** 9 agentes con un rol cada uno: bilbo, ultron, dante, cerberus, argus, moriarty, house, yoda y alexandria. El orden es fijo, según `checklists/flow.json`: Cerberus+Argus → Ultron → Dante → Moriarty → Yoda → Alexandria. Los orquesta la sesión principal siguiendo las skills; no hay un orquestador que se ejecute aparte.
- **Gentle-AI:** 4 lentes de revisión (risk, reliability, resilience, readability) más un refutador; "Judgment Day", con dos jueces que revisan a ciegas y un agente que arregla, en un máximo de 2 rondas; y un prompt de orquestador.

### Qué se impone de verdad y qué solo se describe

| | unmassk | Gentle-AI |
|---|---|---|
| Commits | **Bloqueado por hook:** `git commit` suelto, `--amend` y `rebase` | Solo skills |
| Merge | **Bloqueado por hook** hasta que hayan revisado Cerberus y Alexandria | — |
| Revisión pendiente al cerrar | Gate de checklist en `Stop`, que bloquea como máximo 2 veces | **Hook en `Stop`/`SessionStart` que bloquea si hay una revisión a medias**, con su estado guardado en el binario (`gentle-ai review`) |
| Ficheros sensibles | — | **Lista de bloqueo en permisos**: `.env`, `.ssh`, `secrets/`, `credentials.json`, Keychains |
| Metodología | Grill, council, lifecycle y la puntuación sobre 110: **solo prosa** | ODD/SDD: **solo prosa**. RDD sí lo controla el binario |
| Qué comprueba el gate | Que las casillas estén marcadas, no la calidad | Que los pasos de revisión se hayan completado |

### Calidad de ingeniería

| | unmassk | Gentle-AI |
|---|---|---|
| Tests | 107 ficheros, unos 1.038 tests, ~53.500 líneas de test en el núcleo | 767 ficheros `_test.go`, **~236.000 líneas de test** |
| CI | Python 3.10 en Ubuntu y Windows, más tests de plugins y design-gate | gofmt, `go test`, benchmarks, control para que el código muerto no crezca, test de Claude en Docker sin red, Windows y política de tamaño de PR |
| E2E | — | Docker en Ubuntu, Fedora y Arch |
| Instalación | `git-memory-install/doctor/repair` | **Copia de seguridad de la configuración antes de cada escritura**, `doctor` y desinstalación |
| Release | Semver por plugin, CHANGELOG, `docs/RELEASING.md` | goreleaser, release firmada y con origen verificable, promoción de versiones candidatas |
| Telemetría | — | **Activada por defecto** (`cmd/gentle-telemetry`) |

---

## 3. Lo que se debería mejorar en unmassk-toolkit

Ordenado por relación entre impacto y esfuerzo.

### Arreglos concretos (rápidos)

1. **La autoinstalación de memoria se lanza fuera de un repo git.**
   - `unmassk-toolkit/hooks/boot_launcher.py:71-100` ejecuta `git-memory-install.py --auto` en cualquier carpeta sin `manifest.json`.
   - El instalador sale con error ("not a git repository", `bin/git-memory-install.py:209`), así que cada sesión abierta en `~` imprime *"la instalación automática ha fallado"*.
   - **Arreglo:** comprobar `git rev-parse --show-toplevel` antes de lanzar el instalador. Si no hay repo, no decir nada.

2. **Bloquear los ficheros sensibles en permisos**, copiando a Gentle-AI: `.env`, `.ssh/`, `secrets/`, `credentials.json` y Keychains. Encaja con la filosofía de proteger el sistema de sí mismo que ya sigue `unmassk-standards`.

### Mejoras de diseño

3. **Gate de "revisión pendiente" con estado real.** El gate de checklist solo mira casillas. Gentle-AI guarda en su binario un estado de la revisión y bloquea `Stop` mientras falte un paso. Habría que guardar el estado del pipeline en `.claude/.unmassk/` y que `checklist-gate.py` lo lea, en vez de fiarse de lo que se ha marcado.

4. **Copia de seguridad antes de tocar configuración.** Antes de que el instalador o los hooks escriban en `settings.json`, `CLAUDE.md` o los hooks, guardar una copia, y añadir un `uninstall` que restaure.

5. **Que la memoria ensucie menos el historial.** Valorar una de estas opciones:
   - guardar las notas en una rama dedicada (`refs/memory/*`) o en `git notes`;
   - o, como mínimo, dejar de crear commits vacíos.
   
   Así los proyectos de terceros no cargan con el historial de la memoria.

6. **Memoria fuera de un repo git.** Hoy sin repo no hay memoria. Opción: una memoria global por usuario como respaldo, en `~/.claude/.unmassk/`. — Decidido no hacerlo (Bex, 2026-10-21): fuera de un proyecto no hay memoria.

### Contenido

7. **Igualar la profundidad de las skills de dominio.** Varias son índices finos hacia material de terceros, sin scripts (`db-postgres`, `pentesting-injection`). Hay que priorizar las más usadas y darles:
   - un flujo concreto;
   - un criterio de "hecho";
   - al menos un script de verificación, como en `ops-iac`.

8. **Plantilla común para SKILL.md**, como el contrato fijo de Gentle-AI: activación, reglas duras, puntos de decisión y formato de salida. Facilita revisar y mantener las 90 skills.

### Coste y alcance

9. **Pipeline de 9 agentes con un modo ligero.** Para cambios medianos, una vía corta (Cerberus → Ultron → Dante) que no gaste tokens en Moriarty, Yoda y Alexandria. En el plan Max se nota en el límite de uso.

10. **E2E de la instalación** en un contenedor limpio, con macOS por CI si se puede: instalar, comprobar con doctor, abrir una sesión y desinstalar. Ahora los tests son sobre todo unitarios.

### A largo plazo (opcional)

11. **Soporte para otros agentes.** Es lo que más diferencia a Gentle-AI. Sería un rediseño grande, con adaptadores por agente. Solo merece la pena si el toolkit se va a distribuir a otra gente.

12. **Documentación y código en inglés** si se busca que contribuyan otros. Si es de uso personal, no hace falta.

---

## 4. Qué NO copiar de Gentle-AI

- **Telemetría activada por defecto.**
- **La complejidad de su sistema de revisión:** la jerga de "consent/v3 envelope" y "lineage", y un fichero de baseline de 102 KB en la CI. Si se copia la idea del punto 3, mejor en versión simple.
- **Que la memoria dependa de un binario externo descargado.**

---

## 5. Veredicto

- **Para uso propio sobre Claude Code, unmassk-toolkit es mejor:** muchas más skills y más dominios, reglas impuestas por hooks y memoria auditable en git.
- **Como producto para distribuir, Gentle-AI está más maduro:** soporta muchos agentes, tiene una instalación más robusta y muchos más tests.

Los puntos 1–4 de la sección 3 son los que más acercan unmassk a esa madurez sin perder lo que ya hace mejor.
