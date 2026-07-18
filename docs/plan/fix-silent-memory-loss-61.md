# Fix — pérdida silenciosa de memoria en fallo transitorio de git (#61)

**Issue:** #61
**Branch:** — (trunk repo, main es la rama de trabajo)
**Triage:** BIG (T1)
**Build mode:** test-first
**Seam:** SÍ — seam de lectura git (productor: commits de memoria; consumidor: lectores). §34 aplica (Moriarty round-trip + Yoda evidence rule).
**Created:** 2026-07-18

## Goal
Que los lectores de memoria en producción sobrevivan a un `git rc≠0` transitorio sin devolver vacío en silencio: retry acotado + aviso ruidoso que distinga "git falló / memoria degradada" de "no hay memoria".

## Decisions
- e9400db (Opción A): retry acotado en el read-path + WARN visible distinguiendo fallo de vacío; NO cambiar el contrato de retorno de los lectores; fail-open, no bloquea arranque/turno.
- Modelo de amenaza firmado: "el sistema contra sí mismo" (fallo silencioso + pérdida de memoria) = exactamente este bug.

## Diagnóstico (House, research ya hecho)
- Síntoma: `git log --all --grep ... exit 128` transitorio SOLO en Ubuntu-CI (carga del runner). No reproduce en local.
- Bug real: lectores de producción colapsan rc≠0 en vacío, indistinguible de "no hay memoria". Retry solo existe en el wrapper de los tests, NO en producción.
- Sitios de producción afectados:
  - `lib/recall.py:180-194` `_scan_commits()` (mayor blast radius: alimenta el recall inyectado en contexto)
  - `lib/boot_memory.py:431-441` `extract_glossary()`
  - `lib/boot_git_checks.py:207-210` `get_timeline()`
  - `lib/git_helpers.py:593-599` `commits_since_last_consolidation()`
  - Ejecutor compartido: `lib/git_helpers.py:455-513` `run_git` (timeout=rc1, contrato)

## Tasks

### Task 1 (Dante — CONTRATO test-first, va PRIMERO)
**Files (test):** tests nuevos/ampliados para los 4 lectores.
**Contrato a fijar (tests que fallan hoy):** simular `git rc≠0` transitorio (p.ej. exit 128) en la llamada del read-path y afirmar:
- El lector REINTENTA de forma acotada (N intentos con backoff corto) — un fallo que se cura al 2º intento devuelve el dato real, no vacío.
- Si tras el retry sigue fallando: emite un WARN visible/distinguible (no silencioso) y el resultado degradado NO se presenta como vacío autoritativo.
- Caso de control: un vacío GENUINO (rc 0, sin resultados) NO dispara retry ni warn (no confundir vacío-real con fallo).
- Round-trip §34: escribir memoria real → forzar fallo transitorio en la lectura → el lector recupera o avisa, nunca pierde la entrada en silencio.
**Verify:** los tests nuevos FALLAN contra el código actual (rojo = contrato válido).

### Task 2 (Ultron — implementa hasta GREEN)
**Files (prod):** recall.py, boot_memory.py, boot_git_checks.py, git_helpers.py.
**Steps:**
- Retry acotado (con backoff corto) en las llamadas git del READ-PATH de los 4 lectores. NO un cambio ciego en todo `run_git` (no meter retry en el path de escritura). Helper compartido de retry-de-lectura si reduce duplicación.
- Al agotar el retry: distinguir rc≠0 de vacío y emitir WARN visible; devolver vacío SIN pretender que es autoritativo. No cambiar el tipo de retorno.
- No bloquear arranque/turno (fail-open).
**Verify:** contrato de Dante en verde + suite completa verde.

### Task 3 (opcional, baja prioridad, SOLO si sobra margen): adelgazar magnitudes de fixture
- test_drift 200 commits y test_consolidation ~50: reducibles sin perder la garantía (House). NO toca la flakiness. Fuera del core del fix; candidato aparte.
- `test_recall horizonte 500+`: NO tocar (garantiza recall sin tope de profundidad).

## Wave Map
- Secuencial: Task 1 (Dante contrato) → Task 2 (Ultron GREEN). Task 3 aparte, opcional.

## Verify (Step 5) — con seam §34
- Cerberus (calidad, goal-backward) + Argus (¿el retry introduce algún riesgo? p.ej. amplificación de latencia/loop) en paralelo.
- Dante: endurece; el round-trip lo posee Dante, no Ultron.
- Moriarty: Round-Trip Sabotage contra la dependencia real — forzar git a fallar de varias formas y probar que ningún lector pierde memoria en silencio.
- Yoda: veredicto único + Round-Trip Evidence Rule.
- Gate duro: suite completa verde.
