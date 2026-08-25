# Diseño — las casillas las pone el programa, no Claude

**Fecha:** 2026-08-23 · **Origen:** Q-002, aprobado por Bex en sesión (D-052)
**Estado:** COMPLETADO — implementado, probado en directo el 2026-08-24 (bloquea vacío, deja cerrar completo, re-bloquea una casilla abierta, respeta `stop_hook_active`) y publicado en **1.39.0** (M-125, CHANGELOG). Manifiestos, pieza 2 y pieza 3 existen en el árbol: `unmassk-toolkit/hooks/skill-checklist-inject.py`, `unmassk-toolkit/hooks/checklist-gate.py`, `unmassk-toolkit/checklists/{flow,close-session,audit,council}.json`.

## La idea en una frase

Cuando una skill de proceso se carga, un programa dicta sus casillas y las apunta en un registro propio; al cerrar, otro programa compara ese registro con el tablero visible y no deja decir «terminado» con casillas abiertas o ausentes.

## Por qué así y no de otra forma

- Si las casillas las escribe Claude, el cerrojo depende de que Claude sea obediente para vigilar si Claude es obediente. Agujero señalado por el revisor del plan.
- El dato medido (M-119): tablero encendido, cero usos en 8 sesiones. Hace falta que algo lo encienda por él.
- Anthropic, por escrito: una garantía real es determinista — hooks y permisos, no instrucciones.

## Las tres piezas

### 1 · Manifiestos de casillas (nuevos, propiedad del programa)
`unmassk-toolkit/checklists/<skill>.json` — la lista literal de casillas de cada skill de proceso:
- `unmassk-flow` → 15 · `unmassk-close-session` → 4 · `unmassk-audit` → 14 · `unmassk-council` → 1 (frame confirmado por el usuario ANTES de convocar)
- Doble uso: son también la plantilla MD legible (el plan B de Bex sale gratis del mismo fichero).

### 2 · Al cargar la skill (PostToolUse sobre la herramienta Skill)
- Detecta qué skill se cargó; si tiene manifiesto:
  a) escribe en `.claude/.unmassk/session-checklists.json` qué skill cargó y qué casillas se esperan (registro del PROGRAMA, no del modelo);
  b) inyecta como contexto la orden literal: «crea estas N casillas en el tablero, textualmente, ahora».
- Claude sigue siendo quien llama a la herramienta del tablero (un hook no puede llamar herramientas), pero ya no decide NI el contenido NI la existencia de las casillas: si no las crea, la pieza 3 lo pilla, porque el registro del programa dice que debían existir.

### 3 · El cerrojo (Stop hook, `checklist-gate.py`)
Compara el registro del programa con el estado real del tablero. Bloquea si hay casillas esperadas ausentes, `pending` o `in_progress`.

**Las cuatro protecciones, ninguna opcional** (cada una viene de un fallo real documentado en la investigación):
1. Respeta `stop_hook_active` — nunca bloquea dos veces seguidas (el bucle del issue #55754 se comió 50 min de sesión).
2. Máximo 2 bloqueos por sesión; después deja pasar avisando.
3. Solo LEE — no ejecuta tests, no lanza procesos, no llama a ningún modelo (R-009: 704 procesos huérfanos; D-046: el gate anterior se comía medio millón de contexto).
4. Ante error, JSON corrupto o tablero ilegible: DEJA PASAR y lo dice (tdd-guard bloqueó todo en silencio cuando su modelo desapareció).

**Lo que este cerrojo NO cubre, dicho honesto:** marcar una casilla sin hacer el trabajo. Eso lo mitiga el revisor ciego (ya en la skill jefe), no este mecanismo.

## Riesgo técnico — CERRADO (House, 2026-08-23, verificado en ejecución)
- El tablero persiste en `~/.claude/tasks/<clave>/<N>.json` — un JSON por tarea, con `{id, subject, status, ...}`. Legible por hook: readdir + parsear + ordenar.
- Todo hook recibe `session_id` en su stdin JSON (esquema verificado en el binario vivo). La clave del directorio es normalmente el session_id, pero puede ser otra (`CLAUDE_CODE_TASK_LIST_ID`, equipos) → si el directorio no existe, NUNCA bloquear.
- La escritura de cada JSON **no es atómica** → el fail-open (protección 4) se aplica POR FICHERO: un JSON ilegible no invalida los otros.
- Con `/clear` cambia el session_id y el tablero nace vacío → el registro de la pieza 2 se guarda POR SESIÓN para que ambos lados se reseteen juntos.
- Puerta extra disponible: eventos de hook `TaskCreated`/`TaskCompleted` (payload con task_id y subject) — fuente empujada para el registro, sin parsear ficheros.
- Corrección de premisa: M-119 medía la herramienta equivocada (TodoWrite); el tablero real (TaskCreate) sí se usa. Reemplazada por nota nueva.

## Prueba en directo (definición de hecho) — EJECUTADA, 2026-08-24 (M-125)
1. Cargar Flow en una sesión de prueba → las 15 casillas aparecen sin intervención manual. — hecho
2. Intentar cerrar con casillas abiertas → bloqueo con la lista, una sola vez. — hecho
3. Cerrar con todo marcado → pasa limpio. — hecho
4. Corromper el registro a mano → deja pasar avisando (nunca bloquea en silencio). — hecho
5. Sesión sin skill de proceso cargada → el cerrojo no dice nada. — hecho

## Orden de obra — completado
1. Verificar persistencia del tablero (House, en ejecución). — hecho
2. Manifiestos + pieza 2 (Ultron), test en rojo primero (Dante) para el registro. — hecho
3. Pieza 3 (Ultron) con sus cuatro protecciones testadas una a una (Dante). — hecho
4. Revisión: Cerberus+Argus en paralelo, Moriarty el último. — hecho
5. La prueba en directo de arriba, conmigo al mando, antes de darlo por hecho. — hecho, 2026-08-24

Nota posterior: D-054 (2026-08-24) afinó el emparejador de casillas para que también ignore tildes, no solo mayúsculas/guiones/espacios — evita bloquear una casilla completada por una diferencia de acento al recopiar el texto.
