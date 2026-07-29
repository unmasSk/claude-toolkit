# Fase 0 — Prueba del canal de entrega (instrumento antes que obra)

**Issue:** (pendiente de crear)
**Branch:** main (repo trunk)
**Triage:** Standard
**Build mode:** linear
**Seam:** SÍ — el hook es el productor, el modelo el consumidor. Es exactamente el seam bajo investigación.
**Created:** 2026-07-29

## Goal

Determinar empíricamente **por qué canal, en qué evento, llega texto de un hook al contexto del modelo** — y si se puede devolver una respuesta ya generada antes de que llegue al usuario.

Sin este dato, todo el diseño del freno es fe. El censo ya probó lo que **no** llega (`content` vacío en Stop 0/2506, PreToolUse 0/4688, PreCompact 0 eventos). Falta probar lo que **sí** llega y por qué campo.

## Decisiones tomadas (orquestador, autonomía delegada)

1. **Dos mitades independientes.** (a) registro pasivo de lo que cada evento RECIBE; (b) emisión de marcadores únicos por canal para ver cuáles LLEGAN. La (b) es la que responde la pregunta.
2. **Marcadores con nonce por canal.** Cada canal candidato emite una cadena única e inconfundible. En el turno siguiente, el orquestador declara cuáles ve. Los que se ven, funcionan. Cero interpretación.
3. **Primero los canales no bloqueantes.** `stderr`+exit0, `stdout`+exit0, `hookSpecificOutput.additionalContext`, `systemMessage`. El canal bloqueante (`decision: "block"` + `reason`) se prueba en una segunda pasada controlada, porque interrumpe el turno.
4. **El probe no juzga nada.** No hay lógica de negocio, no hay detectores, no hay bloqueo. Solo registra y emite. Es un instrumento.
5. **Fail-open absoluto.** Cualquier excepción del probe → exit 0 silencioso. Un instrumento de diagnóstico jamás puede romper una sesión.
6. **Vida limitada.** El probe se retira cuando la fase 0 concluye. No se queda en el sistema.

## Tasks

### Task 1: Probe de registro pasivo
**Files:** create `unmassk-toolkit/hooks/_probe_canal.py`
**Steps:**
- [ ] Lee el JSON completo de stdin sin asumir forma
- [ ] Escribe una línea JSON por invocación a `.claude/.unmassk/probe-canal.jsonl`: timestamp, `hook_event_name`, lista de claves de nivel superior recibidas, y si vienen `transcript_path` / `last_assistant_message` / `session_id` (presencia y tipo, no contenido)
- [ ] Ruta resuelta con `verify_path_within_project()` antes de escribir
- [ ] Fail-open: cualquier excepción → exit 0 sin salida
- [ ] Verificar: `python3 _probe_canal.py < payload.json` escribe una línea válida y sale 0

### Task 2: Emisión de marcadores por canal
**Files:** modify `unmassk-toolkit/hooks/_probe_canal.py`
**Steps:**
- [ ] Generar un nonce corto por invocación
- [ ] Emitir el MISMO nonce por cada canal candidato, con etiqueta distinta por canal:
      `PROBE-STDERR-<nonce>`, `PROBE-STDOUT-<nonce>`,
      `PROBE-ADDCTX-<nonce>` (en `hookSpecificOutput.additionalContext`),
      `PROBE-SYSMSG-<nonce>` (en `systemMessage`)
- [ ] Registrar en el `.jsonl` qué nonce se emitió y por qué canales, para poder cruzarlo después
- [ ] Verificar: la salida es JSON válido y el fichero registra el nonce

### Task 3: Registro en hooks.json
**Files:** modify `unmassk-toolkit/hooks/hooks.json`
**Depends on:** Task 2
**Steps:**
- [ ] Declarar el probe en los eventos que hay que medir: `Stop`, `PostToolUse`, `SessionStart`, `UserPromptSubmit`, `SubagentStop`
- [ ] NO tocar ninguna entrada existente
- [ ] Verificar: `python3 -c "import json; json.load(open('hooks/hooks.json'))"` pasa, y el resto de hooks siguen declarados

### Task 4: Lectura del resultado (ORQUESTADOR, turno siguiente)
**Depends on:** Task 3
**Steps:**
- [ ] Tras un turno completo, leer `.claude/.unmassk/probe-canal.jsonl`
- [ ] Declarar qué etiquetas `PROBE-*` aparecen en el contexto del propio orquestador
- [ ] Cruzar: nonce emitido vs nonce visto → tabla evento × canal × llega/no llega
- [ ] Persistir la tabla como `memo(plugin/hooks)` — es el dato que gobierna todo el diseño posterior

### Task 5: Retirada
**Depends on:** Task 4
**Steps:**
- [ ] Quitar el probe de `hooks.json` y borrar el fichero
- [ ] El `.jsonl` queda como evidencia hasta que el memo esté escrito

## Wave Map

- Wave 1: Task 1 → Task 2 (mismo fichero, secuencial)
- Wave 2: Task 3
- Wave 3: Task 4 (requiere un turno real de por medio)
- Wave 4: Task 5

## Criterio de éxito

Una tabla con evidencia directa: para cada evento medido, qué campo de salida llega al contexto del modelo y cuál no. Con esa tabla, el freno de la Fase 3 deja de ser una suposición.
