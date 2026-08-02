# Plan de construcción — Sistema de Memoria v2

**Fecha:** 2026-08-02 · **Estado:** propuesta de plan, sin aprobar
**Especificación de referencia:** `docs/spec-sistema-memoria-v2.md` (cerrada, revisada por council)
**Inventario de referencia:** §3 de este documento, levantado función a función sobre el código real (HEAD `09a0f2f`)

---

## 1. Las tres restricciones que mandan sobre el orden

**A — El v2 se construye DESDE CERO, sin reutilizar nada del v1.** Carpeta propia, piezas propias: su script de commits, su inyección a subagentes, su arranque, su validador. Del v1 se heredan las **lecciones medidas** (§14 de la especificación), nunca las líneas.

Lo que sí es cierto y no es lo mismo: **el v1 sigue siendo lo que está instalado y funcionando hasta el día del cambio.** No porque se quiera que trabajen juntos —no se quiere—, sino porque es lo que hay puesto hasta que se quita. Consecuencia práctica única: ninguna pieza del v2 debe romper al v1 antes de ese día, y por eso la aduana nace apagada.

**B — Los hooks se ejecutan desde la caché del plugin, no desde el repo.** Medido: la caché es una foto fijada por SHA y solo se mueve publicando versión + `claude plugin update` + reinicio. **Una pieza que sea hook no se puede desarrollar iterando.** Todo lo que pueda ser script invocado por ruta se construye antes que lo que tenga que ser hook.

**C — Los prompts de los agentes van al final.** Un agente al que se le dice que consuma vallas cuando aún no hay vallas queda peor que como está.

---

## 2. Dónde vive el código

```
unmassk-memory/                    ← el v2, carpeta nueva, todo desde cero
  .claude-plugin/plugin.json
  bin/            generador, búsqueda, regeneración de índices
  lib/            validador, formato, índices, informe
  hooks/          la aduana + la inyección (últimas fases)
  skills/         la skill de memoria v2
  tests/
unmassk-toolkit/                   ← el v1, CONGELADO
```

**Carpeta nueva en `main`, sin rama larga.** La reversibilidad la da que la carpeta es independiente: si el v2 no vale, se borra entera. Las fases 1 a 5 son scripts que se lanzan por ruta y se prueban sin instalar nada; la primera pieza que exige publicarse es la aduana (fase 6), y nace apagada.

**Los índices del proyecto** (`.claude/project-memory/`, los ocho ficheros) son del proyecto, no del plugin. Nacen vacíos en la fase 3.

---

## 3. INVENTARIO: qué del v1 muere, qué sobrevive, qué hay que partir

Levantado función a función sobre el código real, no por nombre de fichero. **Esa distinción importa: hay ficheros cuyo nombre miente.**

### 3.1 Correcciones que el inventario obliga a hacer

Tres piezas que parecían de memoria y **no lo son**:

- **`hooks/pre-validate-commit-trailers.py`** — se llama "validate-commit-trailers" y **no valida ningún trailer**. Lo único que hace es bloquear `git commit`/`git log` directos para forzar el uso del wrapper. La validación de contenido vive en `bin/git-memory-commit.py`.
- **`hooks/stop-dod-gate.py`** — corre el `test_command` al cerrar. Cero relación con memoria pese a compartir prefijo con los demás.
- **`hooks/stop-close-session.py`** — detecta actividad por tipo de commit e **imprime un recordatorio de texto**. No abre ni parsea un solo trailer.

Y una que parece de memoria del proyecto y es de otra cosa: **`hooks/validate-memory-path.py`** protege `.claude/agent-memory/` — la memoria **de los agentes**, que es un sistema distinto y sobrevive intacto.

### 3.2 Se retiran enteros (100% memoria)

| Pieza | Qué hacía |
|---|---|
| `hooks/pre-task-recall.py` | inyección de memoria a subagentes |
| `hooks/pre-memory-dedup-gate.py` | aviso de memos casi duplicados |
| `hooks/precompact-snapshot.py` | re-inyección antes de compactar (medido: 0 eventos reales) |
| `bin/git-memory-recall.py` | CLI de búsqueda |
| `bin/git-memory-gc.py` | recolector de `Next:`/`Blocker:` — **ya muerto**, sustituido por Gitto modo C |
| `lib/boot_memory.py` (657 L) | extracción de memoria de los commits |
| `lib/boot_glossary_cache.py` (249 L) | caché del glosario |
| `lib/recall.py` (519 L) | motor de búsqueda BM25 |
| `skills/unmassk-gitmemory/` completo | SKILL.md, CALIBRATION.md, GC-PROMPT.md, TEMPLATE.md |
| Bloque `unmassk-toolkit` de `lib/managed_blocks.py` (líneas 35-51) | el texto de arranque inyectado en el `CLAUDE.md` de **todos** los proyectos |
| ~26 ficheros de test (~504 tests) | la mitad de la suite |

### 3.3 Se quedan enteros (0% memoria)

`hooks/`: `pre-merge-gate.py`, `pre-validate-commit-trailers.py`, `session-start-crew.py`, `stop-close-session.py`, `stop-dod-gate.py`, `validate-memory-path.py`

`bin/`: `git-memory-install.py`, `git-memory-log.py`, `git-memory-repair.py`, `git-memory-uninstall.py`, `git-memory-bootstrap.py`, `design_gate.py`, `hooks_doc_sync.py`

`lib/` (17 módulos): `colors`, `version`, `encoding_guard`, `date_parsing`, `boot_checks`, `skill_router`, `boot_migrations`, `_symlink_safe_open`, `install_inspect`, `cache_sync_check`, `upgrade_check`, `bootstrap_tree`, `bootstrap_report`, `bootstrap_deps`, `install_apply`, `hooks_doc`, `incidents`, y ~99% de `git_helpers`

`skills/`: `unmassk-scaffolding` (cero acoplamiento). `agents/`: Argus, Cerberus, Dante, House, Moriarty, Ultron, Yoda (cero menciones a memoria). Bloques `unmassk-communication` y `unmassk-build-mode` de `CLAUDE.md`. ~42 ficheros de test (~533 tests).

### 3.4 HAY QUE PARTIRLOS — quince piezas

Ni se borran ni se conservan enteras. **Esta es la lista que decide el trabajo real.**

| Pieza | Se va (memoria) | Se queda |
|---|---|---|
| `hooks/session-start-boot.py` (519 L) | el `memoria_stamp`, el fetch de memoria, y toda la sección de memoria de `main()` (resume, glossary, remember, decisions, memos, gc, consolidación, timeline) | `write_boot_log`, status, drift de hooks/skills, rama, upstream, disparador de upgrade |
| `hooks/stop-dod-check.py` (241 L) | `has_recent_memory_commits`, `get_last_commit_next`, checks 4-5 | detección de cambios sin commitear y wips acumulados, checks 1-3 |
| `hooks/user-prompt-memory-check.py` (249 L) | solo el texto del banner | drenaje de incidencias, empuje de instalación, enrutado de skills, flag de sesión |
| `bin/git-memory-commit.py` (551 L) | alta/cierre de issue desde `Next:`, longitud de `context()`, validación de categorías de `Memo:`/`Remember:`, aviso de estar detrás | **toda la mecánica genérica de commit**: sujeto, mensaje, `--path`, commit, push, parser de argumentos |
| `bin/git-memory-doctor.py` (698 L) | `check_hook_execution`, `check_gc_status` | los otros 9 chequeos de salud del toolkit |
| `bin/git-memory-upgrade.py` (563 L) | media función de migración (glossary, scopes) | el resto — **ya muerto como punto de entrada** |
| `lib/boot_git_checks.py` (1118 L) | ~500 líneas del bloque de frescura de memoria + `render_consolidation_section` | rama, upstream, ramas remotas, scopes, timeline |
| `lib/boot_render.py` (513 L) | resume, decisions, memos, remember, gc, timeline, lógica de coronas | cabecera, status, línea de sincronización del plugin, pie |
| `lib/boot_health.py` (400 L) | `check_issue_status`, `_issue_matches_next` | drift de skills, versión, lanzadores de doctor/repair |
| `lib/parsing.py` (285 L) | `scan_trailers_memory`, `normalize` | tipo de commit, scope, extracción de mensaje, sugerencia de scope |
| `lib/constants.py` (54 L) | las claves de trailer y las categorías | tipos de commit, firma de co-autor |
| `lib/git_helpers.py` (1222 L) | `commits_since_last_consolidation` (líneas 1130-1210) | todo lo demás |
| `skills/unmassk-close-session/SKILL.md` | pasos 1-4 (flush, curador, resume point, lápidas) | pasos 5-9 (versionado, changelog, limpieza, ramas, doc) |
| `skills/unmassk-core/SKILL.md` | 6 puntos concretos (líneas 3, 8-11, 24, 83, 126, 180) | los otros ~185 (agentes, delegación, workflows) |
| `agents/gitto.md` (314 L) | **~85-90% del agente** — modos A y C enteros, y los trailers del modo B | la mecánica git genérica del modo B |

### 3.5 Ya estaban muertos antes de empezar

`bin/git-memory` (bash), `bin/git-memory-bootstrap.py`, `bin/git-memory-gc.py`, `bin/git-memory-uninstall.py`, `bin/git-memory-upgrade.py`. Ninguno se invoca desde ningún hook ni módulo: solo eran alcanzables por un alias de shell que **nunca se instala**. No hay que planificar su retirada — ya no hacen nada.

### 3.6 Las tres minas: lo que rompe el día uno si no se mira

**1. El gate que bloqueará al v2.** `hooks/pre-validate-commit-trailers.py` sobrevive (no es de memoria) y reconoce que el commit es legítimo **comparando la ruta contra la cadena `bin/git-memory-commit.py`**. Si el generador del v2 se llama de otra forma —y se va a llamar de otra forma—, este hook **bloqueará todos los commits del sistema nuevo**. Hay que tocarlo en la fase 2, no en la 9.

**2. Un saneador de texto compartido.** `sanitize_trailer_value` nació en `lib/parsing.py` para proteger la memoria, y hoy lo usan **cinco módulos que no son de memoria** (incidencias, bootstrap de commits, informe de bootstrap, salud del arranque, y el log). Si al partir `parsing.py` esa función se mueve o se renombra, rompe cosas que no tienen nada que ver con la memoria.

**3. El arranque no tiene costura.** En `session-start-boot.py`, la salud del toolkit y la memoria se van escribiendo **intercaladas en una única lista de líneas**. No hay frontera de función entre las dos: retirar la mitad de memoria exige reescribir `main()`, no borrar un bloque.

---

## 4. Fase 0 — La decisión que evita el bucle lento

Ver restricción B. **El 90% del sistema no necesita ser hook**: generador, validador, búsqueda, informe e índices son scripts invocados por ruta, y se desarrollan ejecutándolos desde el repo sin caché de por medio. Solo dos piezas son obligatoriamente hooks —la aduana y la inyección— y por eso van al final.

**Verificación:** que el primer script de la fase 2 se pueda ejecutar con `python3 unmassk-memory/bin/<script>.py` desde el repo. Si eso no se cumple, el plan está mal montado.

---

## 5. Fase 1 — El validador, pieza única

**Ficheros que nacen:** `unmassk-memory/lib/validador.py`, `unmassk-memory/lib/formato.py`, `zones.json` por proyecto.

**Por qué UNA sola pieza:** P3 — la lista de lo válido vive donde se valida. Si la aduana valida por su cuenta y el generador por la suya, hay dos verdades el primer día. **Generador y aduana llaman a la misma función.**

**Contenido:** zonas (con alias, lista negra, palabra ilegal `audit`), los siete tipos y sus campos obligatorios, las cuatro keys marcadoras con su normalización, y el formato del titular.

**`zones.json` se siembra, no se inventa:** se destila del glossary del v1 más la estructura real de carpetas. Se acepta sucio y se limpia con el uso.

**Verificación:** titular bien formado pasa; zona inexistente no pasa; alias resuelve; zona de la lista negra devuelve el mensaje de rules; `audit` devuelve la disyuntiva.

---

## 6. Fase 2 — El generador

**Ficheros que nacen:** `unmassk-memory/bin/nota.py` (o el nombre que se elija), `unmassk-memory/lib/indices.py`.

**Contenido:** asignación de ID por tipo leyendo el índice; escritura del commit con los emojis heredados; **la línea de índice en el mismo commit**; `close <ID> "motivo"`; `--replaces`; todos los flags por delante (P5); y **propagación del error real de git**, nunca un mensaje vacío.

**Y aquí se desactiva la mina 1:** el gate superviviente reconoce el wrapper por su ruta. En esta fase se le añade la ruta del generador nuevo, o bloqueará todo commit del v2.

**Depende de:** fase 1.

**Verificación:** crear las siete clases de nota en una rama descartable, comprobar que el índice cuadra con git, y que `close` y `--replaces` mueven la línea a `ARCHIVED.md`. Borrar la rama al terminar.

---

## 7. Fase 3 — Índices y arranque (primer entregable visible)

**Ficheros que nacen:** los ocho de `.claude/project-memory/`, `unmassk-memory/lib/arranque.py`, `unmassk-memory/bin/regenerar-indices.py`.

**Contenido:** el menú del día (Next+Context, todos los B, todas las R, recuentos, avisos), el chequeo de coherencia índices↔git, el de IDs duplicados, y **todos los ceros visibles** (P6).

**Nota sobre la mina 3:** este arranque es **nuevo**, no una amputación del viejo. El del v1 sigue corriendo hasta el corte; el del v2 se prueba por ruta.

**Verificación:** con memoria vacía, ceros explícitos. Con tres notas, tres. Se corrompe un índice a propósito y el arranque lo dice.

---

## 8. Fase 4 — La lectura: el informe

**Ficheros que nacen:** `unmassk-memory/lib/informe.py`, `unmassk-memory/bin/buscar.py`.

**Contenido:** las cuatro entradas (ID, zona, palabra, fichero), racimos por punteros, vigente por defecto con `--todo` para la historia, restricciones arriba y literales, Q vivas al final, y "cero notas" en alto.

**Verificación:** montar un racimo de tres notas encadenadas y comprobar que el informe las pliega. Una nota sin punteros sale como grupo de una — y eso es correcto: es la señal de que nadie está enlazando.

---

## 9. Fase 5 — La inyección por oficio y LA PRUEBA

**Ficheros que nacen:** `unmassk-memory/hooks/inyeccion.py` — **escrito de cero**, no heredado.

**Lo que se hereda aquí es la medición, no el código:** está verificado que el evento dispara en **todos** los despachos, que la herramienta se llama `Agent` (no `Task`), y que el identificador llega en `tool_input.subagent_type` con prefijo de plugin, normalizable tras el último `:`. Eso ahorra descubrirlo, no escribirlo.

**5a — Solo Ultron, una semana.** Se le inyectan las R de la zona, y su prompt gana **una línea**: si una R le cambió lo que iba a hacer, lo dice en su informe. Sin esa línea la prueba no concluye nada.

**5b — El resto**, solo si 5a da señal: Dante (R + I), House (I), Argus/Cerberus (I abiertas + keys), Moriarty (R + I), Yoda (D vigente + R), Bilbo (informe completo).

**Qué mide y qué no:** las R de esta fase están escritas a mano y **sin que la aduana las haya validado** (llega en la fase 6). La prueba responde a "¿se leen las vallas?", no a "¿funciona el sistema completo?".

**Sobre el listón:** el v1 está medido como roto (1 lectura por cada 20 escrituras; 11 de 23 sesiones sin leer nada), así que casi cualquier cosa que se lea más ya gana y el diseño no tiene que demostrar excelencia. **La única forma de perder es que tampoco se lea Y ADEMÁS se pague la fricción de la aduana en cada guardado.** Si la prueba no da señal no se abandona nada: dice que antes de extender a los otros ocho hay que atacar por qué se ignora lo inyectado.

---

## 10. Fase 6 — La aduana (la otra pieza que es hook)

**Ficheros que nacen:** `unmassk-memory/hooks/aduana.py`, `unmassk-memory/tests/banco-adversarial/`.

**Va aquí** porque es la que obliga a ciclo de publicación (restricción B) y la que rompería al v1 el día que se encienda (restricción A).

**Contenido:** llama al validador de la fase 1 — no duplica lógica; las nueve validaciones de la especificación; `wip` exento a propósito; e **interruptor: nace apagada**, se enciende proyecto a proyecto en el corte.

**Aquí se monta el banco adversarial (P12), y aquí tiene su dueño.** Cada fase anterior lleva sus tests en su verificación, pero el banco que intenta romper el sistema cuelga de esta fase, porque la aduana es la pieza que más merece ataque: guardar un duplicado, guardar sin enlace, una decisión que contradice a otra, un titular demasiado largo, una zona inventada, una key mal escrita. Cada uno rebota, el banco corre solo y **enseña su resultado** — un banco que nadie ejecuta es otro vigilante muerto.

**Verificación:** con la aduana apagada, el v1 sigue commiteando — se prueba en vivo. Encendida en un proyecto de pruebas, un commit sin zonas rebota con el mensaje correcto y el relanzamiento con flags pasa a la primera.

---

## 11. Fase 7 — Agentes y skills

Ahora que hay algo que consumir:

- **Gitto** — es el 85-90% memoria: se reescribe casi entero. Pierde el modo consolidador, gana el modo adaptador único.
- **House** — el pie estructurado de su informe (causa raíz + titular y zonas propuestos).
- **Bilbo** — el zoom-out obligatorio (mapa de módulos, llamantes, radio de daño).
- **Ultron** — la línea de la prueba (ya introducida en 5a).
- **`unmassk-close-session`** — se parte: los pasos 1-4 se reescriben para el v2, los 5-9 se quedan como están. Y gana los renglones nuevos: escribir el Context/Next, actualizar la issue-plan, podar vallas, dar de alta bloqueantes.
- **`unmassk-core`** — seis puntos concretos, no el skill entero.
- **El bloque `unmassk-toolkit` de `managed_blocks.py`** — se reescribe entero. Ojo: **cambia el `CLAUDE.md` de todos los proyectos instalados**.
- **`unmassk-bug-protocol`** — skill nueva; va después del generador y la aduana porque commitea en formato nuevo.

---

## 12. Fase 8 — La destilación, proyecto a proyecto

Gitto destila la memoria v1 a formato nuevo, una vez, de forma aditiva. **Con dos cosas decididas antes de empezar cada proyecto:**

- **La fecha de corte.** Lo escrito hasta ese día entra en la destilación; desde ese día, solo formato nuevo. Sin fecha explícita, las notas de las semanas de construcción no las destila nadie.
- **El encendido de la aduana** en ese proyecto, el mismo día.

**Orden:** primero `claude-toolkit` (es donde se construye y donde menos duele equivocarse), después uno real.

---

## 13. Fase 9 — Retirar el v1

**No se borran ficheros: se sacan de `hooks.json`.** Un hook no declarado no se ejecuta, y el código queda como archivo muerto sin molestar — coherente con P1 (nada se borra).

Se retira lo de §3.2 y la mitad de memoria de lo de §3.4. Se queda todo §3.3. Y se decide fichero a fichero qué hacer con los partidos: lo más limpio es dejarlos como están y que el v2 no los use, en vez de amputarlos.

---

## 14. Resumen del orden

| Fase | Pieza | Depende de | ¿Se puede enseñar? |
|---|---|---|---|
| 0 | Decisión: todo script salvo aduana e inyección | — | no |
| 1 | Validador único + `zones.json` sembrado | 0 | no |
| 2 | Generador + desactivar la mina del gate | 1 | notas reales |
| 3 | Índices + arranque | 2 | **sí — primer entregable visible** |
| 4 | El informe | 2, 3 | sí |
| 5a | Inyección a Ultron + **LA PRUEBA** | 4 | **sí — y es donde se aprende algo** |
| 5b | Inyección al resto | 5a con señal | sí |
| 6 | Aduana apagada + banco adversarial | 1, 5 | sí |
| 7 | Agentes y skills | 6 | sí |
| 8 | Destilación por proyecto | 7 | sí |
| 9 | Retirar el v1 | 8 | — |

---

## 15. Lo que este plan NO resuelve

1. Las listas de zonas definitivas de cada proyecto — tarea del propietario, con la materia prima preparada.
2. El dedup semántico de remembers — excede a un script.
3. **El carril de "ensayo operativo" en la tripulación:** ninguna definición de agente cubre "ejecuta una prueba y reporta". Esta noche esa tarea rebotó entre dos agentes y la acabó haciendo el orquestador. Va a volver a pasar en las fases 2, 5 y 6.
4. El papel de Alexandria en el flujo de documentación.
5. Qué hacer con los ~504 tests del v1 cuando se retire: ¿se borran, se marcan, se quedan corriendo contra código muerto?
