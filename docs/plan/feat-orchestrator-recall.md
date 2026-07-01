# Recall del orquestador — Implementation Plan

**Issue:** (trunk repo, sin issue de GitHub; tracking = este plan + git-memory)
**Branch:** main (repo trunk — se trabaja directo en main)
**Triage:** Big (toca el hook que dispara en cada mensaje; afecta contexto/prompt-cache de TODA interacción)
**Build mode:** test-first (comportamiento con reglas claras — umbral, fail-safe, sin ruido — y caro si se equivoca)
**Created:** 2026-06-12

## Goal

Que en cada mensaje del usuario, el hook `user-prompt-memory-check.py` busque en la memoria git lo más relevante a ese mensaje e inyecte **al contexto del Claude principal** solo lo que de verdad destaque — para que el orquestador no repita errores ya anotados.

## Decisiones (de la investigación de ayer + cierre de hoy)

- **Recall del orquestador = prioridad, fallo arquitectónico** (decision 4efed2d): los subagentes reciben recall fresco por spawn (`pre-task-recall.py`), pero el hilo principal solo tiene el volcado de boot. Hay que cerrarlo.
- **Buscar siempre, inyectar solo si destaca** (memo ee8cfb9, mecanismo 4): buscar es gratis; el coste es inyectar y contaminar contexto. Inyectar es una DECISIÓN, no un lookup ciego.
- **Umbral relativo + suelo, language-agnostic** (memos ab330ab + 9962be3): nada de umbral absoluto atado a vocabulario; pero el 2x-mediana puro es frágil (cuando todo es relevante, no inyecta). Híbrido elegido: **suelo mínimo absoluto pequeño** (descarta casi-cero) **+ fracción del mejor** (solo resultados al menos la mitad de fuertes que el top) **+ tope K**. Sobre scores IDF (no dependen del idioma).
- **En proceso, no subproceso** (memo del caso 20s de latencia): llamar a `lib/recall.py` importado, como hace `pre-task-recall.py`. Hook ligero.
- **Fail-open total** (patrón `pre-task-recall.py`): cualquier excepción → no inyectar bloque, el hook sigue con su comportamiento de hoy (`[git-memory] root`, `needs_upgrade`, `[memory-check]`). NUNCA romper el arranque ni el resto del hook.
- **Inyección como texto plano a stdout** antes del bloque `[memory-check]`, etiquetada claramente.

## Estado de partida (mapa de Bilbo)

- `unmassk-toolkit/hooks/user-prompt-memory-check.py`: hook `UserPromptSubmit`. Hoy NO lee stdin. Emite con `print("\n".join(lines))` (línea ~187). UserPromptSubmit recibe en stdin JSON con el campo `prompt`.
- `unmassk-toolkit/lib/recall.py`: `recall(query, *, limit=8, scope=None, _repo_dir=None) -> str` (texto formateado, sin scores). Internos reutilizables: `_scan_commits()`, `_build_df()`, `_idf_score()`, `_tokenize()`. Corpus = `git log --all` (toda la historia). Stopwords EN+ES, tokenizer con acentos.
- Tests plantilla: `tests/test_recall.py` (helpers `_make_repo`, `_commit`, `recall_in`) y `tests/test_pre_task_recall.py` (helper `_run_hook` = invoca el hook por subproceso con JSON en stdin).

## Tasks

### Task 1: API de recall con scores + puerta de relevancia (lib)
**Files:** modify `unmassk-toolkit/lib/recall.py` · test `unmassk-toolkit/tests/test_recall_gated.py`
**Steps:**
- [ ] Añadir función pública `recall_relevant(query, *, max_results=3, floor=<const>, top_fraction=0.5, scope=None, _repo_dir=None) -> str | None` que:
  - reusa `_scan_commits` + `_build_df` + `_idf_score` para puntuar todas las entradas
  - aplica la puerta: descarta score <= `floor`; del resto conserva los que cumplan `score >= top_fraction * top_score`; corta a `max_results`
  - si no sobrevive ninguno → devuelve `None` (no inyectar)
  - si sobreviven → devuelve el MISMO formato de bloque que `recall()` (reusar el formateador existente, no duplicarlo)
- [ ] Constantes nombradas a nivel de módulo (`RECALL_FLOOR`, `RECALL_TOP_FRACTION`, `RECALL_MAX_RESULTS`) para que el comportamiento sea tuneable y testeable.
- [ ] Language-agnostic: la puerta opera solo sobre scores numéricos IDF, cero keywords de idioma.
- [ ] Verify: `python -m pytest unmassk-toolkit/tests/test_recall_gated.py -q` → verde.

### Task 2: Inyección en el hook por mensaje (hook)
**Depends on:** Task 1
**Files:** modify `unmassk-toolkit/hooks/user-prompt-memory-check.py` · test `unmassk-toolkit/tests/test_user_prompt_recall.py`
**Steps:**
- [ ] Al inicio de `main()`: leer `sys.stdin` de forma defensiva, parsear JSON, extraer `prompt` (string). Si no hay stdin / no parsea / no hay `prompt` → seguir sin recall (no romper nada).
- [ ] Llamar `recall_relevant(prompt)` en proceso, envuelto en try/except que ante CUALQUIER error → no bloque.
- [ ] Si devuelve bloque, añadirlo a `lines` ANTES del bloque `[memory-check]`, con etiqueta clara (p.ej. `[memoria relevante — recuperada para esta consulta]`).
- [ ] Preservar intactos: `[git-memory] root`, la rama de `needs_upgrade`/install --auto, y el `[memory-check]`. El recall SUMA, no reemplaza.
- [ ] Verify: `python -m pytest unmassk-toolkit/tests/test_user_prompt_recall.py -q` → verde.

## Wave Map
- Wave 1: Task 1 (lib + su contrato)
- Wave 2: Task 2 (hook, depende de la API de Task 1)

(Test-first: en cada wave, Dante escribe el contrato que falla → Ultron implementa hasta verde.)

## Contrato de comportamiento (lo que los tests deben fijar)

1. Query claramente relevante a una memoria existente (comparte token distintivo) → el bloque se inyecta y contiene esa entrada.
2. Query irrelevante (sin solape real) → NO se inyecta bloque (`None`).
3. Query con un match débil por debajo de `top_fraction` del mejor → ese match débil queda fuera.
4. Tope: nunca más de `RECALL_MAX_RESULTS` entradas.
5. Hook sin stdin / stdin no-JSON / sin campo `prompt` → fail-safe: hook funciona como hoy, sin bloque, sin crash.
6. Excepción dentro del recall → fail-safe: hook sigue, resto de bloques intactos.
7. El `[memory-check]` y la lógica de upgrade preexistentes siguen funcionando con el recall activado (no regresión).
8. Language-agnostic: una query en otro idioma con token distintivo compartido también dispara.
