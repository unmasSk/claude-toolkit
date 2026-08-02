# Plan de construcción — Sistema de Memoria v2

**Versión:** 2.0 · **Fecha:** 2026-08-02 · **Estado:** propuesta, pendiente de autorización

## Los cuatro documentos

| Documento | Qué contiene |
|---|---|
| **este** | Los pasos, numerados, en orden, cada uno con su verificación |
| `TRAZABILIDAD.md` | Los 131 requisitos de la especificación → en qué paso se construye cada uno |
| `TEXTOS.md` | Los textos literales que el sistema escupe: rechazos, informe, arranque, índices, commits |
| `ARQUITECTURA.md` | El árbol de ficheros, las funciones de cada uno, y el grafo de dependencias |

**Referencia:** `docs/spec-sistema-memoria-v2.md` (la especificación, cerrada).

---

## 0. Cómo se lee y cómo se cumple este plan

Cinco reglas, y son parte del plan:

1. **Los pasos van numerados y en orden.** Un paso no empieza hasta que el anterior pasa su verificación. Si un paso no se puede verificar, no es un paso: es una intención, y no entra.
2. **Ningún paso se salta.** Si un paso resulta innecesario al llegar a él, se dice y se tacha con su motivo — no se omite en silencio.
3. **Nada fuera del plan.** Si aparece trabajo que no está aquí, se para y se propone con la etiqueta *"esto no está en el plan"* por delante. No se cuela dentro de otro paso.
4. **Cada paso dice quién lo hace.** Ultron implementa, Dante prueba, Bilbo investiga, el orquestador escribe documentos y skills. Un paso sin dueño es un paso que rebota.
5. **La trazabilidad es la prueba.** `TRAZABILIDAD.md` demuestra que cada uno de los 131 requisitos tiene su paso. Si algo no está ahí, no se construye — y eso es exactamente lo que pasó con el v1.

---

## 1. Las siete decisiones, resueltas por el propietario

Ya no bloquean nada. Quedan aquí porque cambian pasos concretos y hay que poder volver a leerlas.

| # | Decisión | Resolución | Afecta a |
|---|---|---|---|
| **1** | El campo de ficheros tocados | **SE RETIRA del v2 entero.** Era un duplicado de lo que git ya guarda, y en el v1 se escribió 605 veces sin que nadie lo leyera. La función se conserva sin él: la vista por fichero usa `git log -- <ruta>` y la capa se deduce del diff nativo | 2.7 · `ARQUITECTURA.md` §5 |
| **2** | El nombre del comando | **`gitmem`**, fachada única con subcomandos en inglés sobre los scripts: `note`, `close`, `context`, `work`, `search`, `boot`, `reindex`, `zones`, `rule`, `bench` | todo |
| **3** | Los emojis que faltaban | ❓ pregunta · 🚫 descarte · 🔥 incidencia. **No es una papelera**: la papelera sugiere que se puede borrar, y el descarte es permanente | 0.2 |
| **4** | El tercer hook para el arranque | **Sí.** Lanzador de ~20 líneas sin lógica: se escribe una vez y no se itera jamás, así que no paga el peaje de la caché | 3.6 |
| **5** | Los descartes automáticos | **Cada uno con su commit, su identificador y su línea de índice.** "Un acto, un commit" aplica a nota+índice, no al acto completo | 2.5 |
| **6** | El campo del bloqueante | **`Awaits:`** — campo propio, capitalizado y **en inglés**, como todos los que ve una máquina. Su lector es la sección de bloqueantes del arranque. En la presentación al usuario se lee «espera:», que es texto | 1.2 |
| **7** | Los ~504 tests del v1 | **Se borran al retirar cada pieza.** Git guarda la historia; tests contra código muerto son ruido | 9.3 |

### La regla transversal que manda sobre toda la arquitectura

**Todo nombre que ve una máquina va en inglés.** El principio P8 —"lo que se busca, en inglés"— se extiende a todo lo mecánico: nombres de scripts, módulos, funciones, campos, flags y subcomandos.

**Lo que se lee sigue en español:** los mensajes de rechazo, los informes, los textos del arranque. Solo cambia lo mecánico.

Ejemplos del renombrado, ya aplicado en `ARQUITECTURA.md`: `note.py`→`note.py` · `search.py`→`search.py` · `boot.py`→`boot.py` · `validador`→`validator` · `rechazo`→`rejection` · `racimos`→`clusters` · `informe`→`report` · `salud`→`health` · `reparto`→`dispatch` · `--verify`→`--verify`.

---

## 2. Las cuatro restricciones que mandan sobre el orden

**A — Desde cero, sin reutilizar nada del v1.** Carpeta propia, piezas propias. Del v1 se heredan las lecciones medidas, nunca las líneas. El v1 sigue instalado hasta el día del cambio; por eso la aduana nace apagada.

**B — Los hooks corren desde la caché del plugin.** Cada cambio en un hook exige publicar versión + `claude plugin update` + reinicio. **Un hook no se puede desarrollar iterando.** Todo lo que pueda ser script por ruta va antes.

**C — Los prompts de los agentes van al final.** Un agente al que se le dice que consuma vallas cuando aún no hay vallas queda peor que como está.

**D — El validador es una sola pieza.** La llaman el generador y la aduana. Si hay dos implementaciones de "esto es válido", hay dos verdades el primer día — que es exactamente cómo murió `Sources:` en el v1.

---

## 3. Tres contradicciones de la especificación, resueltas aquí

La auditoría encontró tres sitios donde este plan contradecía a la especificación **sin declararlo**. Se declaran y se resuelven:

**3.1 — El orden de la aduana.** La especificación (§16.8) dice *"generador y aduana primero"*. Este plan pone la aduana en la fase 6. **Se mantiene el plan y se anula esa línea de la especificación**, por la restricción B: la aduana es hook, y ponerla primero significa que cada iteración del validador cuesta una publicación de versión. El generador sí va primero, como pide la especificación.

**3.2 — El tubo de inyección.** La especificación (§8.2) dice *"cambia el contenido, no el mecanismo"*. Este plan lo escribe de cero. **Se mantiene el plan**, por la restricción A: el v2 no reutiliza código del v1. Lo que se hereda es la medición del canal, que ahorra descubrirlo pero no escribirlo.

**3.3 — El candado de concurrencia.** La especificación (§7) dice *"se conserva el candado del v1, ya probado"*. La restricción A dice que no se reutilizan líneas. **Se resuelve así: el v2 escribe su propio candado**, con el mismo mecanismo (bloqueo exclusivo de fichero, con su variante de Windows) porque el mecanismo es correcto y está probado en producción. Es la única pieza del v1 que se reescribe imitándola a propósito, y queda dicho.

---

## 4. Dónde vive el código

```
unmassk-memory/                     ← carpeta nueva, en main, sin rama larga
  .claude-plugin/plugin.json
  bin/       gitmem (fachada) + 10 scripts invocables por ruta
  lib/       27 módulos, ninguno de más de 500 líneas
  hooks/     3 hooks: aduana, inyección y el lanzador del arranque
  skills/    la skill de memoria y la de incidencias
  commands/  el comando de reglas
  tests/     incluido el banco adversarial
```

El detalle está en `ARQUITECTURA.md`. La reversibilidad la da que la carpeta es independiente: si el v2 no vale, se borra entera.

---

## 5. Inventario del v1: qué muere, qué sobrevive, qué hay que partir

Levantado función a función sobre el código real. **Clasificado por lo que hace, no por cómo se llama** — y eso importa, porque hay tres ficheros cuyo nombre miente:

- `pre-validate-commit-trailers.py` **no valida ningún trailer**: solo obliga a usar el wrapper.
- `stop-dod-gate.py` no es de memoria: corre los tests al cerrar.
- `stop-close-session.py` solo imprime un recordatorio; no abre un trailer.

Y `validate-memory-path.py` protege la memoria **de los agentes**, que es otro sistema y sobrevive intacto.

### 5.1 Se retiran enteros (11)

`hooks/pre-task-recall.py` · `hooks/pre-memory-dedup-gate.py` · `hooks/precompact-snapshot.py` · `bin/git-memory-recall.py` · `bin/git-memory-gc.py` · `lib/boot_memory.py` (657 L) · `lib/boot_glossary_cache.py` (249 L) · `lib/recall.py` (519 L) · `skills/unmassk-gitmemory/` completo · el bloque `unmassk-toolkit` de `lib/managed_blocks.py` · ~26 ficheros de test (~504 tests)

### 5.2 Se quedan enteros (38)

**hooks:** `pre-merge-gate` · `pre-validate-commit-trailers` · `session-start-crew` · `stop-close-session` · `stop-dod-gate` · `validate-memory-path`
**bin:** `git-memory-install` · `git-memory-log` · `git-memory-repair` · `git-memory-uninstall` · `git-memory-bootstrap` · `design_gate` · `hooks_doc_sync`
**lib (17):** `colors` · `version` · `encoding_guard` · `date_parsing` · `boot_checks` · `skill_router` · `boot_migrations` · `_symlink_safe_open` · `install_inspect` · `cache_sync_check` · `upgrade_check` · `bootstrap_tree` · `bootstrap_report` · `bootstrap_deps` · `install_apply` · `hooks_doc` · `incidents`
**resto:** `unmassk-scaffolding` · siete agentes sin menciones a memoria · dos bloques de `CLAUDE.md` · ~42 ficheros de test

### 5.3 Hay que partirlos (15)

| Pieza | Se va | Se queda |
|---|---|---|
| `hooks/session-start-boot.py` (519 L) | el sello de memoria, el fetch, y toda la sección de memoria de `main()` | `write_boot_log`, status, drift, rama, upgrade |
| `hooks/stop-dod-check.py` (241 L) | `has_recent_memory_commits`, `get_last_commit_next`, checks 4-5 | detección de cambios y wips, checks 1-3 |
| `hooks/user-prompt-memory-check.py` (249 L) | solo el texto del banner | incidencias, instalación, enrutado, flag de sesión |
| `bin/git-memory-commit.py` (551 L) | issues desde `Next:`, longitud de `context()`, categorías, aviso de estar detrás | **toda la mecánica genérica de commit** |
| `bin/git-memory-doctor.py` (698 L) | `check_hook_execution`, `check_gc_status` | los otros 9 chequeos |
| `bin/git-memory-upgrade.py` (563 L) | media función de migración | el resto — ya muerto |
| `lib/boot_git_checks.py` (1118 L) | ~500 líneas de frescura + consolidación | rama, upstream, scopes, timeline |
| `lib/boot_render.py` (513 L) | resume, decisions, memos, remember, gc, timeline, coronas | cabecera, status, pie |
| `lib/boot_health.py` (400 L) | `check_issue_status`, `_issue_matches_next` | drift, versión, lanzadores |
| `lib/parsing.py` (285 L) | `scan_trailers_memory`, `normalize` | tipo, scope, mensaje, sugerencia |
| `lib/constants.py` (54 L) | claves de trailer y categorías | tipos de commit, co-autor |
| `lib/git_helpers.py` (1222 L) | `commits_since_last_consolidation` | todo lo demás |
| `skills/unmassk-close-session/SKILL.md` | pasos 1-4 | pasos 5-9 |
| `skills/unmassk-core/SKILL.md` | 6 puntos (líneas 3, 8-11, 24, 83, 126, 180) | los otros ~185 |
| `agents/gitto.md` (314 L) | **85-90% del agente** | la mecánica git del modo B |

### 5.4 Ya estaban muertos (5)

`bin/git-memory` (bash) · `git-memory-bootstrap.py` · `git-memory-gc.py` · `git-memory-uninstall.py` · `git-memory-upgrade.py`. Solo alcanzables por un alias de shell **que nunca se instala**. No hay que planificar su retirada.

### 5.5 Las tres minas

**Mina 1 — el gate que bloqueará al v2.** `pre-validate-commit-trailers.py:51` reconoce el commit legítimo comparando la ruta contra la cadena `git-memory-commit.py`. Como el generador del v2 se llama de otra forma, **bloqueará todos los commits del sistema nuevo**. Se desactiva en el paso **2.8**, no en la fase 9.

**Mina 2 — un saneador compartido.** `sanitize_trailer_value` nació en `parsing.py` para proteger la memoria y hoy la usan **cinco módulos que no son de memoria**. El v2 escribe el suyo y no la toca; se apunta para el día del reparto de `parsing.py`.

**Mina 3 — el arranque no tiene costura.** En `session-start-boot.py` la salud del toolkit y la memoria se escriben intercaladas en la misma lista. Por eso el arranque del v2 **se escribe de cero** (paso 3.5) en vez de amputar el viejo.

---

# LAS FASES

---

## FASE 0 — Preparar el terreno

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **0.1** | Crear `unmassk-memory/` con su estructura vacía y `plugin.json` en versión `0.1.0` | Ultron | El árbol existe y `python3 -c "import json;json.load(open('unmassk-memory/.claude-plugin/plugin.json'))"` no falla |
| **0.2** | Escribir `lib/utf8.py` y `lib/colors.py` (con los emojis de los siete tipos) | Ultron | Un emoji se imprime bajo `PYTHONIOENCODING=cp1252` sin reventar |
| **0.3** | Escribir `tests/conftest.py`: repo git temporal, helpers de alta, aserciones de índice | Dante | Un test tonto que crea el repo temporal pasa |
| **0.4** | Dejar constancia de que **solo la aduana y la inyección son hooks**; todo lo demás se invoca por ruta | Orquestador | Está escrito en `ARQUITECTURA.md` |

**Puerta de fase:** el primer script se puede ejecutar con `python3 unmassk-memory/bin/...` desde el repo, sin instalar nada.

---

## FASE 1 — El validador (sin git, sin ficheros: todo unitario)

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **1.1** | `lib/model.py` — las nueve dataclasses puras, sin lógica | Ultron | Importan y son inmutables |
| **1.2** | `lib/vocabulary.py` — los 7 tipos, sus campos, las 4 keys marcadoras, la lista negra, la palabra ilegal, la pregunta del dolor **en una sola copia**, y el tope de 60 caracteres | Ultron | Cada tipo declara sus campos obligatorios y permitidos |
| **1.3** | Declarar en `vocabulario.CAMPOS` el **lector** de cada campo (ruta de la función que lo lee) | Ultron | Un campo sin lector declarado hace fallar el módulo al importarse |
| **1.4** | `lib/zones.py` + sembrar `zones.json` del glossary del v1 más la estructura de carpetas | Ultron | Alias resuelve · zona inexistente rebota · lista negra da el mensaje de reglas · `audit` da la disyuntiva |
| **1.5** | `lib/format.py` — construir y parsear titular, cuerpo, línea de índice y línea de archivo | Ultron | **Round-trip: construir → parsear → objeto idéntico**, para los 7 tipos y para el ⏩ |
| **1.6** | `lib/similar.py` — detector léxico dentro de la zona | Ultron | Dos notas casi iguales se detectan; dos distintas, no |
| **1.7** | `lib/rejection.py` — un texto, dos renderizados (terminal y bloqueo de hook) | Ultron | El texto lleva **qué pasa, las opciones y el comando exacto de relanzamiento** |
| **1.8** | `lib/validator.py` — la pieza única: titular, zonas, tipo, campos, keys, pregunta del dolor, punteros, sustitución, consolidación, y la exención del `wip` | Ultron | Titular >60 rebota · M sin respuesta rebota con la pregunta literal · "sí" en una M dice "entonces es una R" · nota parecida sin `--replaces` rebota con las candidatas dentro |
| **1.9** | Tests del validador, uno por regla | Dante | Verde sin que exista un solo commit |
| **1.10** | `tests/test_p2_sin_zombis.py` — recorre los campos declarados, importa su lector y falla si no existe | Dante | **Rojo si alguien añade un campo sin lector.** Esta es la vacuna contra los 605 `Touched:` |

**Puerta de fase:** los tests del validador pasan y no hay una segunda implementación de "esto es válido" en ningún sitio.

---

## FASE 2 — El generador

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **2.1** | `lib/gitcmd.py` — git con el **stderr real**, candado de fichero propio, escritura atómica | Ultron | Un git que falla devuelve su mensaje entero, nunca vacío · dos procesos se serializan |
| **2.2** | `lib/indexes.py` — los ocho ficheros: sembrar, insertar, retirar, archivar, recuentos | Ultron | `sembrar` es idempotente · las tres formas de destino de archivo se parsean |
| **2.3** | `lib/ids.py` — contador por tipo y detector de duplicados | Ultron | `D-001` en índice vacío · `D-031` tras treinta |
| **2.4** | `lib/notes.py` — **la transacción**: validar → índice → commit de nota+índice **juntos** → si git falla, restaurar el índice y propagar el error | Ultron | `git show --stat` del commit contiene la nota **y** la línea de índice · si el commit falla, el índice queda como estaba |
| **2.5** | Los descartes de una decisión, enlazados con su origen — **cada uno con su commit, su identificador y su línea de índice** | Ultron | Una decisión con dos alternativas produce tres commits; los tres índices cuadran |
| **2.6** | `bin/` — el alta de nota, el cierre y la sustitución, con todos los flags admitidos en el primer intento | Ultron | Las siete clases de nota se crean en una rama descartable · el cierre y la sustitución mueven la línea al archivo |
| **2.7** | El commit de trabajo, con la referencia a la issue. **Sin campo de ficheros tocados: retirado del v2** | Ultron | El commit lleva su referencia · la vista por fichero funciona con `git log -- <ruta>`, sin campo |
| **2.8** | **MINA 1:** añadir las rutas del v2 a la lista de wrappers reconocidos en `unmassk-toolkit/hooks/pre-validate-commit-trailers.py:51` | Ultron | Un commit del v2 pasa el gate del v1. **Sin este paso, nada del v2 puede commitear** |
| **2.9** | Tests de la transacción | Dante | Los dos casos del paso 2.4, contra un repo real |

**Puerta de fase:** se pueden escribir notas de verdad y el índice nunca queda desincronizado del commit.

---

## FASE 3 — Índices, arranque y salud (primer entregable visible)

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **3.1** | `lib/query.py` — las cuatro lecturas desde git hacia objetos | Ultron | Sembrar tres notas y recuperarlas por ID, zona, palabra y fichero |
| **3.2** | `lib/context.py` + su script — el ⏩ con su cuerpo, **sin zonas, sin índice, sin lápida** | Ultron | Se escribe y se lee de vuelta · **y la aduana lo eximirá** (paso 6.3) |
| **3.3** | `lib/rules.py` + su script + el comando — el fichero de reglas, fuera del sistema | Ultron | Se añade una regla y se lee el fichero **entero** · no aparece en ninguna búsqueda |
| **3.4** | `lib/health.py` — coherencia índices↔git, IDs duplicados, planes con commits sin reflejar | Ultron | Borrar una línea de un índice a mano se reporta como "falta en índice" |
| **3.5** | `lib/boot.py` + su script — el menú del día completo, **escrito de cero** (mina 3) | Ultron | Memoria vacía → **ceros explícitos y ruidosos** · tres notas → tres · índice corrupto → aviso |
| **3.6** | El hook lanzador del arranque: ~20 líneas sin lógica que llaman al script | Ultron | Dispara en una sesión real · no se vuelve a tocar nunca |
| **3.7** | El script de regeneración de índices desde git, con modo solo-diagnóstico | Ultron | Corromper un índice: el diagnóstico lo dice, la regeneración lo arregla, el resultado es byte a byte el mismo |
| **3.8** | Los ocho ficheros nacen vacíos con su cabecera | Ultron | Existen y su cabecera dice quién los escribe |
| **3.9** | Tests de arranque y salud | Dante | Los ceros salen; la divergencia se detecta en los dos sentidos |

**Puerta de fase:** **esto se te enseña.** Es el primer día que hay algo por pantalla.

---

## FASE 4 — La lectura: el informe

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **4.1** | `lib/clusters.py` — agrupación por punteros, determinista | Ultron | Cadena de tres notas se pliega en un racimo · nota huérfana = racimo de una, **y eso es la señal, no un fallo** |
| **4.2** | El título del racimo es la nota viva más reciente | Ultron | Con dos notas encadenadas, el título es el de la nueva |
| **4.3** | `lib/report.py` — restricciones arriba, racimos en medio, preguntas al final; vigente por defecto | Ultron | El orden se cumple · la historia solo aparece con la opción explícita |
| **4.4** | `lib/report_render.py` — el texto, con la presentación heredada | Ultron | Calca los bloques de `TEXTOS.md` |
| **4.5** | "Cero notas" en alto para una zona vacía | Ultron | El texto es imposible de confundir con un error |
| **4.6** | La búsqueda por palabra **señala las líneas que casaron** | Ultron | Se ve qué línea concreta hizo match, no solo qué nota |
| **4.7** | La vista por fichero | Ultron | Devuelve los commits de ese fichero, desplegables |
| **4.8** | El script de búsqueda con sus cuatro entradas | Ultron | Las cuatro funcionan y todas imprimen un informe, **nunca una lista de commits** |
| **4.9** | Tests del informe | Dante | Los cinco puntos de 4.3 a 4.6 |

---

## FASE 5 — La inyección por oficio y LA PRUEBA

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **5.1** | La zona del encargo: una línea `Zone: z1/z2` en el despacho, con casado por palabras contra el fichero de zonas como respaldo. **Y si no se puede determinar, NO se calla: inyecta un bloque que dice que ese agente sale sin memoria de proyecto y por qué** | Orquestador | Un despacho sin zona produce una línea visible en el encargo, nunca un silencio |
| **5.2** | `lib/dispatch.py` — la tabla de qué ve cada oficio | Ultron | Cada agente recibe exactamente lo suyo · sin zona, cadena vacía |
| **5.3** | El hook de inyección, **escrito de cero**, con fallo abierto absoluto | Ultron | Contrato con payload real · una excepción en cualquier punto deja pasar el despacho sin tocarlo |
| **5.4** | Primera publicación de versión y actualización del plugin | Orquestador | El hook dispara de verdad en un despacho real |
| **5.5** | **5a: solo Ultron**, y su prompt gana una línea: si una valla le cambió lo que iba a hacer, lo dice en su informe | Orquestador | Sin esa línea la prueba no concluye nada |
| **5.6** | **Una semana de uso normal** | — | Se cuentan los informes de Ultron que mencionan una valla |
| **5.7** | 5b: el resto de oficios | Ultron | Solo si 5a dio señal |

**Qué mide esta prueba y qué no:** las vallas de esta fase están escritas a mano y **sin que la aduana las haya validado**. Responde a *"¿se leen las vallas?"*, no a *"¿funciona el sistema completo?"*.

**Sobre el listón:** el v1 está medido como roto (1 lectura por cada 20 escrituras; 11 de 23 sesiones sin leer nada). Casi cualquier cosa que se lea más ya gana. **La única forma de perder es que tampoco se lea y encima se pague la fricción de la aduana.** Si no hay señal no se abandona nada: se ataca por qué se ignora lo inyectado antes de extender.

---

## FASE 6 — La aduana y el banco adversarial

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **6.1** | El hook de la aduana, llamando al **mismo validador** de la fase 1 | Ultron | No hay una segunda implementación de nada |
| **6.2** | El interruptor: **nace apagada**, se enciende proyecto a proyecto | Ultron | Apagada, el v1 sigue commiteando — se prueba en vivo |
| **6.3** | Las exenciones: el `wip` y el ⏩ del cierre de sesión | Ultron | Ninguno de los dos recibe una sola pregunta |
| **6.4** | La décima validación: al cerrar una incidencia, se retiene el cierre preguntando si de esa cicatriz sale valla | Ultron | El cierre rebota con las dos opciones y el comando de relanzamiento |
| **6.5** | La undécima: al nacer una valla, se presentan **todas** las incidencias candidatas de la zona, nunca una preseleccionada | Ultron | Se listan todas; elegir ninguna es una respuesta válida |
| **6.6** | Alta de zona, paso 2: el sistema la da de alta a la vista y relanza | Ultron | La zona aparece en el fichero y el commit pasa a la segunda |
| **6.7** | El catálogo de ataques del banco adversarial | Dante | Duplicado, sin enlace, decisión que contradice, titular largo, zona inventada, key mal escrita, zona prohibida, `audit`, memo que era valla, destilación sin fuentes |
| **6.8** | El banco corre solo y **enseña su resultado** | Ultron | Un banco que nadie ejecuta es otro vigilante muerto |
| **6.9** | Tests de la aduana | Dante | Apagada no bloquea · encendida bloquea con el texto exacto · el `wip` pasa |

---

## FASE 7 — Skills, agentes y periferia

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **7.1** | La skill de memoria: enseña a traer **todos los flags puestos** para que el coste normal sea un comando y cero rechazos | Orquestador | Un alta completa se escribe sin rebotar |
| **7.2** | En esa skill: la regla de los dos segundos, la calibración del bloqueante y de la valla, y el árbol de tipos | Orquestador | Están escritas, con ejemplos |
| **7.2b** | En esa skill: la **mini-sección de la vista por fichero** — qué es, sus dos comandos, y cuándo la usa cada oficio. Los prompts de los agentes solo la referencian; el contenido vive una sola vez | Orquestador | Ningún prompt duplica el contenido |
| **7.3** | En esa skill: el disparador de búsqueda es **el usuario en lenguaje natural**, y las tres prohibiciones (sin disparadores léxicos, sin juicio espontáneo, sin inyección por mensaje) | Orquestador | Escrito |
| **7.4** | En esa skill: comunicar el menú del día en el primer mensaje y dejar que el usuario decida el rumbo | Orquestador | Escrito |
| **7.5** | El ciclo de vida de la pregunta abierta: se resuelve antes de construir sobre su módulo; puede parir una issue; al cerrarse asciende o cae | Orquestador + Ultron | El destino "ascendida a" aparece en el archivo |
| **7.6** | Los planes: documento en `docs/`, issue creada por Claude con `gh` **nunca por un script**, acta que enlaza decisión e issue, y edición de la issue al cambiar la decisión | Orquestador | Un ciclo completo de plan, real |
| **7.7** | Gitto: se reescribe casi entero (pierde el consolidador, gana el adaptador) | Orquestador | — |
| **7.8** | House: el pie estructurado de su informe | Orquestador | — |
| **7.9** | Bilbo: el zoom-out obligatorio | Orquestador | — |
| **7.10** | `unmassk-close-session`: se parten los pasos 1-4 y gana cuatro renglones — el ⏩, la issue-plan al día, la poda de vallas y el alta de bloqueantes | Orquestador | Un cierre real ejecuta los cuatro |
| **7.11** | `unmassk-core`: los seis puntos concretos | Orquestador | — |
| **7.12** | El bloque de `CLAUDE.md`: se reescribe entero. **Cambia el arranque de todos los proyectos instalados** | Orquestador | — |
| **7.13** | La skill de incidencias, con sus tres vertientes y sus cinco puntos internos resueltos al redactarla | Orquestador | Un ciclo completo de incidencia |
| **7.14** | Registrar `unmassk-memory` en el marketplace y publicar | Orquestador | Se instala en un proyecto limpio |

---

## FASE 8 — La destilación, proyecto a proyecto

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **8.1** | Fijar la **fecha de corte** del proyecto | Orquestador + usuario | Escrita antes de empezar |
| **8.2** | Encender la aduana en ese proyecto | Orquestador | El primer commit del día ya pasa por ella |
| **8.3** | Gitto destila, por pasadas con tope, citando los hashes de origen | Gitto | Cada nota destilada declara de qué sale |
| **8.4** | Los cinco destinos: hechos a memo, vallas a restricción, preferencias a reglas, informes a documentación, pendiente a pregunta | Gitto | Ninguna cae en el saco equivocado |
| **8.5** | En la duda, se propone al usuario | Gitto | — |
| **8.6** | Orden: primero el toolkit, después un proyecto real | Orquestador | — |

---

## FASE 9 — Retirar el v1

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **9.1** | Sacar de `hooks.json` los hooks de §5.1. **No se borran ficheros** | Ultron | Los hooks retirados no se ejecutan; el código queda de archivo muerto |
| **9.2** | Decidir fichero a fichero qué hacer con los quince partidos | Orquestador | Lo más limpio es dejarlos y que el v2 no los use |
| **9.3** | Borrar los tests de cada pieza retirada, a la vez que la pieza | Dante | La suite queda verde y sin tests contra código muerto |
| **9.4** | Leer los resultados de la sonda pendiente del v1 y cerrarla | Orquestador | Afecta solo al sistema congelado |

---

## 6. Lo que este plan sigue sin resolver

1. **El carril de "ensayo operativo".** Ninguna definición de agente cubre "ejecuta una prueba y reporta". Esa tarea ya rebotó entre dos agentes en la sesión del diseño y la acabó haciendo el orquestador. **Va a volver a pasar en los pasos 2.6, 5.6 y 6.8.**
2. **El papel de Alexandria** en el flujo de documentación.
3. **La lista de zonas definitiva** de cada proyecto — es tarea tuya, con la materia prima preparada.
4. **El dedup semántico de reglas** — excede a un script.
5. *(resuelto — la zona del encargo se declara en el despacho y la ausencia se hace visible; ver paso 5.1)*
