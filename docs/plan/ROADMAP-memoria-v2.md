# ROADMAP — Sistema de memoria v2

**Decidido:** 2026-07-29 · **Punto de retorno:** tag `pre-rebuild-memoria-2026-07-29` (en origin)
**Criterio:** la capa de ENTREGA se rehace de cero. El MOTOR de memoria no se toca. La limpieza va aparte.

---

## Por qué esta división y no "todo de cero"

| Capa | Estado | Decisión |
|---|---|---|
| **Motor** — escribir/leer memoria en git (`git-memory-commit.py`, `parsing.py`, `recall.py`, `boot_memory.py`) | Funciona. Nunca ha perdido una entrada. Lleva ~15 bugs reales ya pagados (pérdida silenciosa por git transitorio, tombstones que resucitaban, lost-update en CLAUDE.md, prosa del usuario borrada al regenerar, subject de 1297 bytes que reventaba el arranque) | **NO SE TOCA.** Reescribirlo = repetir esos 15 incidentes sin saber que existen |
| **Entrega** — hooks + qué muestra el arranque (`hooks/*.py`, `boot_render.py`) | Podrida. 1 hook muerto entero, 3 mudos, 1 con doble fallo. ~2.800 líneas | **DE CERO** |
| **Muerto** — huérfanos, shims, migraciones cumplidas | ~4.000 líneas que no ejecuta nadie | **BORRAR**, en el orden de dependencias de la Fase 4 |

**Regla que gobierna todo el roadmap:** ningún borrado ocurre antes de que la Fase 0 diga por qué canal se entrega. Construir el freno sin ese dato es repetir el error de 2026 (#69).

---

## FASE 0 — Medición del canal · EN CURSO

**Estado:** instrumento puesto y sincronizado al caché. Recoge datos desde la sesión siguiente al 2026-07-29.

| # | Acción | Fichero | Verificación |
|---|---|---|---|
| 0.1 | ✅ Probe construido | `hooks/_probe_canal.py` (nuevo, 301 líneas) | 5 payloads degradados → exit 0 siempre |
| 0.2 | ✅ Declarado en 5 eventos | `hooks/hooks.json` | 49 inserciones, 0 eliminaciones |
| 0.3 | ✅ Sincronizado al caché | `<cache>/1.24.0/hooks/` | probe ejecutado desde el caché → salida correcta |
| 0.4 | ⏳ **Leer la medición** | `.claude/.unmassk/probe-canal.jsonl` | cruzar nonce emitido vs nonce visto en contexto |
| 0.5 | ⏳ Persistir la tabla evento × canal | `memo(plugin/hooks)` | — |
| 0.6 | ⏳ Retirar el probe | repo **y** caché + restaurar `hooks.json.pre-probe.bak` | `grep -c _probe_canal` = 0 en ambos |

**Salida de la fase:** tabla que dice, para `Stop`, `PostToolUse`, `SessionStart`, `UserPromptSubmit`, `SubagentStop`: qué campo llega al modelo. **Esa tabla decide la Fase 1.**

Bifurcación ya prevista:
- Si `additionalContext` llega en `Stop` → los 3 hooks mudos se arreglan cambiando de canal, sin tocar su lógica.
- Si no llega nada en `Stop` → el freno no puede vivir ahí y se mueve a `PreToolUse`.

---

## FASE 1 — Capa de entrega, de cero

**Se borran y se reescriben**, no se parchean. Nada de esto sobrevive tal cual.

| # | Fichero | Qué pasa | Por qué |
|---|---|---|---|
| 1.1 | `hooks/stop-dod-check.py` (241 l.) | **Reescribir** | Emite 5 avisos por stderr+exit0 → 0/2506 llegan. La lógica es correcta; el canal no |
| 1.2 | `hooks/stop-close-session.py` (127 l.) | **Fusionar con 1.1** | Duplica el escaneo de `git log` y el checklist de cierre. Un mensaje, no tres |
| 1.3 | `hooks/precompact-snapshot.py` (371 l.) | **Reescribir** | 371 líneas, fence con nonce, anti-forja… todo por un canal que no entrega. `PreCompact` no admite `additionalContext`: hay que decidir entre `decision:block`+`reason` o mover el checkpoint a otro evento |
| 1.4 | `hooks/pre-memory-dedup-gate.py` (325 l.) | **Reescribir** | Doble fallo: regex `:157` exige espacio tras `.py` y falla con la ruta entrecomillada (la que el propio sistema instruye) → se le escapan ~2/3 de los memos; y avisa por `permissionDecisionReason` junto a `allow`, que no llega |
| 1.5 | `lib/boot_render.py` (471 l.) | **Reescribir la parte de presupuesto** | Debe declarar en la propia salida cuántas entradas muestra de cuántas hay (hoy calla el recorte). `render_gc_section` cuenta lo mostrado, no lo real → la alarma nunca salta |
| 1.6 | `lib/boot_memory.py` `SCAN_DEPTH`/`MAX_*` | **Recalibrar, no reescribir** | Es motor. Solo cambian los topes y el conteo real para la alarma |

**Verificación de la fase:** un turno real donde el aviso de cierre llegue al contexto. Prueba conductual, no test unitario: si sigue sin llegar, la fase ha fallado aunque los tests pasen.

---

## FASE 2 — Los gates que sí deben morder

| # | Acción | Fichero:línea | Nota |
|---|---|---|---|
| 2.1 | `CLAUDE_CODE` → `CLAUDECODE` | `hooks/pre-validate-commit-trailers.py:42` | Revive el bloqueo de commit/log directo tras 4 meses muerto |
| 2.2 | Arreglar la fixture que lo ocultaba | `tests/conftest.py:295` | Fabrica `CLAUDE_CODE=1`, un entorno que producción nunca da. **Dante**, no Ultron |
| 2.3 | Test que detecte esta clase de bug | nuevo | "¿este hook llega a dispararse?" — no existe ni uno. Es el bug que dominó el censo |
| 2.4 | `test_command` con subconjunto rápido | `.claude/git-memory-config.json` | Hoy desarmado a propósito: `Stop` dispara por turno y la suite tarda 280s contra un tope de 60s. Hace falta un subconjunto <20s |
| 2.5 | `EXPECTED_HOOKS` 5→12, `EXPECTED_SKILLS` 3→10 | `bin/git-memory-doctor.py:43-55` | Da verde sobre 7 hooks y 7 skills que no mira. Fallo silencioso puro |
| 2.6 | Doctor debe comparar repo **vs** caché | `bin/git-memory-doctor.py` | Hoy solo mira el caché → verde aunque tu edición no se ejecute |

---

## FASE 3 — Memoria en el mensaje

**Solo después de la Fase 0.** Se reinstaura la inyección por mensaje, por el canal medido, sin repetir el error de #69 (acertaba mal y metía ruido).

| # | Acción | Nota |
|---|---|---|
| 3.1 | Inyectar por `UserPromptSubmit` → `additionalContext` | Canal probado: 1445/1445 |
| 3.2 | Contenido: decisiones/memos del tema que toca el mensaje | Reusar `lib/recall.py` — es motor, funciona |
| 3.3 | Calibrar el umbral con datos, no a ojo | El fallo de #69 fue precisión, no mecanismo |
| 3.4 | Puerta de entrada: `remember(claude)` sin verificador → se rechaza | Del veredicto del council: sin cerrar el grifo, en 6 meses hay 134 otra vez |

---

## FASE 4 — Borrado, en orden de dependencias

**El orden NO es opcional** — cada punto desbloquea el siguiente.

### 4a. Huérfanos de `bin/` (~74 KB + 44 KB de lib)

| Orden | Fichero | Precondición |
|---|---|---|
| 1 | Quitar `check_cli()` de `bin/git-memory-doctor.py:128-138,426-429` | **Antes** de borrar el wrapper, o el doctor da error permanente |
| 2 | Decidir dónde vive la migración v3.7→v3.8 (`git-memory-upgrade.py:206-283`) | Es su único hogar hoy, por decisión explícita |
| 3 | `bin/git-memory` (bash, 152 l.) | Causa raíz: su alias `git memory` nunca se instala |
| 4 | `bin/git-memory-bootstrap.py` + `lib/bootstrap_{tree,deps,commits,report}.py` | O se cablea a `unmassk-project-lifecycle`, o se va. **Decisión de Bex** |
| 5 | `bin/git-memory-gc.py` (414 l.) | Nadie limpia `Next:`/`Blocker:` hoy. **Decisión de Bex** |
| 6 | `bin/git-memory-uninstall.py` (392 l.) | Única salida limpia del toolkit, pero nadie puede lanzarla |
| 7 | `bin/git-memory-upgrade.py` (563 l.) | Solapado con `install.py --auto`, que es el camino vivo |

### 4b. Muerto en `lib/`

| Fichero:símbolo | Líneas | Precondición |
|---|---|---|
| `parsing.extract_commit_message` | 21 | ninguna — 0 referencias en todo el repo |
| `parsing.parse_commit_type` | 28 | borrar antes `tests/test_parsing_consolidation.py` GROUP 6 |
| `parsing.parse_trailers` | 23 | borrar antes sus 3 ficheros de test |
| `constants.RISK_VALUES`, `CODE_TYPES` | 4 | ninguna |
| `colors.GREEN`, `BOLD` | 2 | ninguna |
| `managed_blocks._BEGIN_MARKERS` | 2 | ninguna |
| `boot_memory.py:637-657` (shim) | 21 | ninguna — nadie lo consume por esa vía |
| `boot_checks.py` (fichero entero) | 69 | reapuntar `boot_render.py:57` a `boot_health`/`boot_git_checks` |
| `recall.recall_relevant` | 79 | borrar antes `test_recall_gated.py` |
| `boot_migrations.py` (fichero entero) | 114 | migración cumplida, verificada en disco |
| `lib/_symlink_safe_open.py` | 165 | **arreglar antes `tests/test_migrate_statusline.py`** — es lo único que lo sostiene |

**Cadena crítica:** `boot_migrations.py` → `test_migrate_statusline.py` → el stub de `sys.modules` → 6 `try/except ImportError` en producción → `_symlink_safe_open.py`. Tirar del primer hilo cae toda: **~320 líneas de producción + 395 de test**.

### 4c. Tests (180-220 retirables de 1.147)

| Grupo | Tests | Nota |
|---|---|---|
| Anti-atacante | ~40 | `test_crossplatform_symlink_guard*.py` + `test_issue63_manifest_read_hardening.py` |
| Código muerto | ~7 | 5 en `test_user_prompt_recall.py` afirman la ausencia de algo ya borrado |
| Tautológicos | ~110 | 75 de 85 en `test_user_prompt_skill_router.py`: 586 líneas de test para un módulo de 74 que hace `if frase in texto` |
| Por shim | ~23 | `test_needs_upgrade_semver.py`, `test_migrate_statusline.py` |

**Hueco a cubrir, no a borrar:** `skills/unmassk-scaffolding/scripts/scaffold.py` — 3.541 líneas, el fichero más grande del repo, **cero tests**.

### 4d. Higiene
- Marcar `Status: COMPLETED` en los 6 planes de `docs/plan/` cuyos issues están cerrados (#49, #57, #60, #63, #72, #78)
- Borrar `.pyc` huérfanos de `bin/__pycache__/` (`context-writer` ya no existe)

---

## FASE 5 — Que la documentación no pueda volver a mentir

Esto es lo que impide que el censo haya que repetirlo en seis meses.

| # | Acción | Fichero |
|---|---|---|
| 5.1 | Generar la sección "Active Hooks" desde `hooks.json` + los ficheros reales | `skills/unmassk-gitmemory/SKILL.md` |
| 5.2 | El doctor **falla** si la doc y el código divergen | `bin/git-memory-doctor.py` |
| 5.3 | Corregir las 31 falsedades restantes | `managed_blocks.py:47`, `unmassk-core/SKILL.md:28,34-42,135-137`, `README:61,78,80,84,127,133`, `GC-PROMPT.md` (huérfano + comando roto) |
| 5.4 | Resolver el nudo `unmassk-audit` | O se hace agnóstico de verdad, o deja de afirmarlo (9 prompts con `npx vitest`/`prettier`/Zod/97%) |

---

## Orden de ejecución y por qué

1. **Fase 0** — bloquea todo lo demás. Sin la tabla del canal, la Fase 1 es fe.
2. **Fase 1** — es lo que Bex nota en la misma semana.
3. **Fase 2** — gates que muerden; barato y de efecto inmediato.
4. **Fase 5.1-5.2** — antes de la limpieza, para que la limpieza no vuelva a desincronizar la doc.
5. **Fase 3** — la pieza grande, ya con canal medido.
6. **Fase 4** — al final: es higiene, no conducta, y es la única irreversible.

**Nada de la Fase 4 se ejecuta hasta que 1, 2 y 3 estén verdes.** Borrar primero y arreglar después deja el sistema sin red durante el arreglo.

## Criterio de terminado del roadmap entero

No es "los tests pasan". Es: **una sesión real donde una regla guardada cambia lo que hago, sin que Bex la repita.** Si eso no ocurre, el roadmap ha fallado por muy verde que esté la suite.
