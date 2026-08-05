# Plan de construcción — Sistema de Memoria v2

**Versión:** 2.0 · **Fecha:** 2026-08-02 · **Estado:** propuesta, pendiente de autorización

## Los documentos

| Documento | Qué contiene |
|---|---|
| **este** | Los pasos, numerados, en orden, cada uno con su verificación |
| `TRAZABILIDAD.md` | Los 168 requisitos de la especificación → en qué paso se construye cada uno |
| `TEXTOS.md` | Los textos literales que el sistema escupe: rechazos, informe, arranque, índices, commits |
| `ARQUITECTURA.md` | El árbol de ficheros, las funciones de cada uno, y el grafo de dependencias |
| `DRIFT.md` | El barrido del repo entero: qué habla del sistema viejo y qué hay que tocar. Entrada de trabajo de la fase 7 |
| `TESTIGO.md` | Lo que el v1 construyó y **nadie llegó a usar**, medido función a función. Materia prima del documento siguiente |
| `PIEZAS.md` | **El contrato de cada fichero**, antes de escribir una línea: superficie, quién llama a cada función, sus tests, y qué del v1 no se trae. Alimenta la fase 1 y no la sustituye |

**Referencia:** `docs/spec-sistema-memoria-v2.md` (la especificación, cerrada).

---

## 0. Cómo se lee y cómo se cumple este plan

Cinco reglas, y son parte del plan:

1. **Los pasos van numerados y en orden.** Un paso no empieza hasta que el anterior pasa su verificación. Si un paso no se puede verificar, no es un paso: es una intención, y no entra.
2. **Ningún paso se salta.** Si un paso resulta innecesario al llegar a él, se dice y se tacha con su motivo — no se omite en silencio.
3. **Nada fuera del plan.** Si aparece trabajo que no está aquí, se para y se propone con la etiqueta *"esto no está en el plan"* por delante. No se cuela dentro de otro paso.
4. **Cada paso dice quién lo hace.** Ultron implementa, Dante prueba, Bilbo investiga, el orquestador escribe documentos y skills. Un paso sin dueño es un paso que rebota.
5. **La trazabilidad es la prueba.** `TRAZABILIDAD.md` demuestra que cada uno de los 168 requisitos tiene su paso. Si algo no está ahí, no se construye — y eso es exactamente lo que pasó con el v1.

---

## 1. Las siete decisiones, resueltas por el propietario

> **[Corrección del propietario, 2026-08-03]** Este título es falso, y es el origen de todo lo que se ha corregido hoy en los diez documentos de esta obra: el 3 de agosto se descubrió que estas siete filas **no las resolvió el propietario** — salieron de una sesión de Claude y se escribieron aquí como si lo fueran. `gitmem` no aparece ni una vez en la especificación cerrada. No se borra en silencio: queda anotado, y las filas de abajo se corrigen una a una donde de verdad chocan con lo que él ha decidido hoy. **Las decisiones reales de hoy, con su fecha y sus palabras, están en `DEUDA.md` PARTE 1** — esta tabla no las repite, las referencia.

Ya no bloquean nada. Quedan aquí porque cambian pasos concretos y hay que poder volver a leerlas.

| # | Decisión | Resolución | Afecta a |
|---|---|---|---|
| **1** | El campo de ficheros tocados | **SE RETIRA del v2 entero.** Era un duplicado de lo que git ya guarda, y en el v1 se escribió 605 veces sin que nadie lo leyera. La función se conserva sin él: la vista por fichero usa `git log -- <ruta>` y la capa se deduce del diff nativo | 2.7 · `ARQUITECTURA.md` §5 |
| **2** | El nombre del comando | **`gitmem`**, fachada única sobre los scripts. [**Corrección del propietario, 2026-08-03** — `DEUDA.md` PARTE 1, B4]: la lista de subcomandos de esta fila estaba mal en cuatro puntos y el sistema queda en **nueve**: `note`, `work`, `wip`, `remove`, `next`, `search`, `zones`, `rezones`, `rule`. `close`→`remove`, `context`→`next` y `reindex`→`rezones` se renombran; `bench` **se borra entero** («no lo he autorizado en la vida») — y con él cae el principio P12 de la especificación, que lo exigía como invariante (ver FASE 6, nota tras el paso 6.9); `wip` nace nuevo, el checkpoint que el validador ya sabía eximir de preguntas pero que ningún comando llegaba a escribir. Y `boot` **deja de ser subcomando**: no se invoca vía `gitmem`, se dispara solo al abrir sesión (paso 3.6) y escribe un documento que Claude lee entero — no una inyección, que tiene tope de tamaño | todo |
| **3** | Los emojis que faltaban | ❓ pregunta · 🚫 descarte · 🔥 incidencia. **No es una papelera**: la papelera sugiere que se puede borrar, y el descarte es permanente | 0.2 |
| **4** | El tercer hook para el arranque | **Sí.** Lanzador de ~20 líneas sin lógica: se escribe una vez y no se itera jamás, así que no paga el peaje de la caché | 3.6 |
| **5** | Los descartes automáticos | **Cada uno con su commit, su identificador y su línea de índice.** "Un acto, un commit" aplica a nota+índice, no al acto completo | 2.5 |
| **6** | El campo del bloqueante | **`Awaits:`** — campo propio, capitalizado y **en inglés**, como todos los que ve una máquina. Su lector es la sección de bloqueantes del arranque. [**Corrección del propietario, 2026-08-03**]: en la presentación al usuario también se lee «awaits:», **no** «espera:» — esta fila arrastraba el eje viejo (ver más abajo), ya invalidado | 1.2 |
| **7** | Los ~504 tests del v1 | **Se borran al retirar cada pieza.** Git guarda la historia; tests contra código muerto son ruido | 9.3 |

### La regla transversal que manda sobre toda la arquitectura

**Todo nombre que ve una máquina va en inglés.** El principio P8 —"lo que se busca, en inglés"— se extiende a todo lo mecánico: nombres de scripts, módulos, funciones, campos, flags y subcomandos.

> **[Corrección del propietario, 2026-08-03]** La frase que seguía aquí —«lo que se lee sigue en español: los mensajes de rechazo, los informes, los textos del arranque»— queda invalidada tal como estaba escrita: *«Deja de poner cosas en español cuando son en inglés. No hablo del título ni de la descripción: hablo del resto — recuentos, avisos, restricciones.»* El eje **no** es dónde vive el texto (si se busca o si se lee) — así lo decía el principio P8 de la especificación, y de ahí salió mal esta frase —; el eje es **etiqueta estructural contra contenido explicativo**. Las etiquetas van en inglés aunque vivan dentro de un informe o de un texto de arranque que el usuario lee: `RECUENTOS`→`COUNTS`, `AVISOS`→`CHECKS`, `RESTRICCIONES`→`RESTRICTIONS`, `BLOQUEANTES`→`BLOCKERS`, `MEMORIA`→`MEMORY`, `awaits:` (fila 6, arriba), y el resto de cabeceras de sección del informe y del arranque. **Solo el contenido explicativo** —los porqués, las descripciones, los textos de rechazo en prosa— sigue en castellano.

Ejemplos del renombrado, ya aplicado en `ARQUITECTURA.md`: `note.py`→`note.py` · `search.py`→`search.py` · `boot.py`→`boot.py` · `validador`→`validator` · `rechazo`→`rejection` · `racimos`→`clusters` · `informe`→`report` · `salud`→`health` · `reparto`→`dispatch` · `--verify`→`--verify`.

---

## 2. Las cuatro restricciones que mandan sobre el orden

**A — Desde cero, sin reutilizar nada del v1.** Carpeta propia, piezas propias. Del v1 se heredan las lecciones medidas, nunca las líneas. El v1 sigue instalado hasta el día del cambio; por eso la aduana nace apagada.

**B — Los hooks corren desde la caché del plugin.** Cada cambio en un hook exige publicar versión + `claude plugin update` + reinicio. **Un hook no se puede desarrollar iterando.** Todo lo que pueda ser script por ruta va antes.

**C — Los prompts de los agentes van al final.** Un agente al que se le dice que consuma muros cuando aún no hay muros queda peor que como está.

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
unmassk-toolkit/                     ← carpeta nueva, en main, sin rama larga
  .claude-plugin/plugin.json
  bin/       gitmem (fachada, 9 subcomandos) + bin/memory/ con 10 scripts:
             los 9 subcomandos más boot.py, que ya no se invoca vía gitmem
             — se dispara solo al abrir sesión [decisión del propietario,
             2026-08-03; ver §1, fila 2]
  lib/memory/  31 módulos, ninguno de más de 500 líneas
  hooks/     2 hooks: la aduana (`customs.py`) y el lanzador del arranque (`boot_launcher.py`)
  skills/    la skill de memoria y la de incidencias
  commands/  el comando de reglas
  tests/     incluido el banco adversarial
```

> **[corregido 2026-08-04]** Esta sección se contradecía con la propia **FASE 5** de este mismo documento, más abajo, que retira `hooks/inject.py` entero por decisión del propietario (B20) — y esa fase ya estaba escrita cuando esta línea seguía diciendo «3 hooks: aduana, inyección y el lanzador del arranque». Verificado en disco: ni `hooks/inject.py` ni `lib/memory/dispatch.py` existen; los hooks reales de memoria son `unmassk-toolkit/hooks/customs.py` y `unmassk-toolkit/hooks/boot_launcher.py`, dos. Y `lib/memory/` no tiene 23 módulos: tiene **31** (contados en disco). Un documento que se desmiente a sí mismo dentro del mismo fichero es peor que uno incompleto — quien lo lea creerá el trozo que abra primero.

El detalle está en `ARQUITECTURA.md`. La reversibilidad la da que la carpeta es independiente: si el v2 no vale, se borra entera.

**El sistema nace ya dentro de `unmassk-toolkit/`.** No hay carpeta aparte ni paso de absorción: el v1 se borra en esta misma rama, así que el nombre `unmassk-gitmemory` queda libre y la skill nueva lo hereda. Cero enlaces que romper.

Por qué dentro y no como plugin aparte: **la memoria no es un plugin opcional** como el de bases de datos o el de diseño. Es infraestructura del núcleo. Si se queda como plugin suelto, puede no estar instalado — y entonces desaparecen el arranque, la aduana y la skill que enseña a usarla, mientras el resto de la tripulación (que la referencia desde `unmassk-core`, `unmassk-flow` y el cierre de sesión) apunta a algo que no está.

La reversibilidad la da la rama: si el v2 no vale, se borra la rama y `main` no se entera.

---

## 5. Inventario del v1: qué muere, qué sobrevive, qué hay que partir

Levantado función a función sobre el código real. **Clasificado por lo que hace, no por cómo se llama** — y eso importa, porque hay tres ficheros cuyo nombre miente:

- `pre-validate-commit-trailers.py` **no valida ningún trailer**: solo obliga a usar el wrapper.
- `stop-dod-gate.py` no es de memoria: corre los tests al cerrar.
- `stop-close-session.py` solo imprime un recordatorio; no abre un trailer.

Y `validate-memory-path.py` protege la memoria **de los agentes**, que es otro sistema y sobrevive intacto.

### 5.1 Se retiran enteros (12)

`hooks/pre-task-recall.py` · `hooks/pre-memory-dedup-gate.py` · `hooks/precompact-snapshot.py` · `bin/git-memory-recall.py` · `bin/git-memory-gc.py` · `lib/boot_memory.py` (657 L) · `lib/boot_glossary_cache.py` (249 L) · `lib/recall.py` (519 L) · `skills/unmassk-gitmemory/` completo · el bloque `unmassk-toolkit` de `lib/managed_blocks.py` · `agents/gitto.md` (314 L — **no se borra**, a diferencia del resto de esta lista: se conserva en `unmassk-toolkit/deprecated/gitto.md`, fuera de `agents/` para que el harness no lo registre) · ~26 ficheros de test (~504 tests)

### 5.2 Se quedan enteros (38)

**hooks:** `pre-merge-gate` · `pre-validate-commit-trailers` · `session-start-crew` · `stop-close-session` · `stop-dod-gate` · `validate-memory-path`
**bin:** `git-memory-install` · `git-memory-log` · `git-memory-repair` · `git-memory-uninstall` · `git-memory-bootstrap` · `design_gate` · `hooks_doc_sync`
**lib (17):** `colors` · `version` · `encoding_guard` · `date_parsing` · `boot_checks` · `skill_router` · `boot_migrations` · `_symlink_safe_open` · `install_inspect` · `cache_sync_check` · `upgrade_check` · `bootstrap_tree` · `bootstrap_report` · `bootstrap_deps` · `install_apply` · `hooks_doc` · `incidents`
**resto:** `unmassk-scaffolding` · siete agentes sin menciones a memoria · dos bloques de `CLAUDE.md` · ~42 ficheros de test

### 5.3 Hay que partirlos (14)

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

### 5.4 Ya estaban muertos (5)

`bin/git-memory` (bash) · `git-memory-bootstrap.py` · `git-memory-gc.py` · `git-memory-uninstall.py` · `git-memory-upgrade.py`. Solo alcanzables por un alias de shell **que nunca se instala**. No hay que planificar su retirada.

### 5.5 Las tres minas

**Mina 1 — el gate que bloqueará al v2.** `pre-validate-commit-trailers.py:51` reconoce el commit legítimo comparando la ruta contra la cadena `git-memory-commit.py`. Como el generador del v2 se llama de otra forma, **bloqueará todos los commits del sistema nuevo**. Se desactiva en el paso **2.8**, no en la fase 9.

**Mina 2 — un saneador compartido.** `sanitize_trailer_value` nació en `parsing.py` para proteger la memoria y hoy la usan **cinco módulos que no son de memoria**. El v2 escribe el suyo y no la toca; se apunta para el día del reparto de `parsing.py`.

**Mina 4 — `bin/release.py` INVOCA el motor viejo.** Es el único sitio de todo el repo donde el v1 no se describe sino que **se ejecuta**: ruta fija a `git-memory-commit.py` (línea 141) y `--trailer Touched=` (línea 159), un campo retirado. **Pero no guarda memoria**: hace un commit de tipo `chore` con tres ficheros concretos y pasa por el wrapper solo porque el gate prohíbe `git commit` directo. La traducción es `gitmem work`. Hoy no falla, pero el día que se retire el v1 el pipeline de publicación se cae con un código de error. Se desactiva en el paso **2.8b**, no en la fase 9.

**Mina 3 — el arranque no tiene costura.** En `session-start-boot.py` la salud del toolkit y la memoria se escriben intercaladas en la misma lista. Por eso el arranque del v2 **se escribe de cero** (paso 3.5) en vez de amputar el viejo.

---

# LAS FASES

---

## FASE 0 — Preparar el terreno

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **0.1** | Crear `unmassk-toolkit/` con su estructura vacía y `plugin.json` en versión `0.1.0` | Ultron | El árbol existe y `python3 -c "import json;json.load(open('unmassk-toolkit/.claude-plugin/plugin.json'))"` no falla |
| **0.2** | Escribir `lib/utf8.py` y `lib/colors.py` (con los emojis de los siete tipos) | Ultron | Un emoji se imprime bajo `PYTHONIOENCODING=cp1252` sin reventar |
| **0.3** | Escribir `tests/conftest.py`: repo git temporal, helpers de alta, aserciones de índice | Dante | Un test tonto que crea el repo temporal pasa |
| **0.4** | Dejar constancia de que **solo la aduana y la inyección son hooks**; todo lo demás se invoca por ruta [**corregido 2026-08-04**: la inyección se retiró entera por decisión del propietario (B20, ver FASE 5); los dos hooks reales hoy son la aduana (`customs.py`) y el lanzador del arranque (`boot_launcher.py`)] | Orquestador | Está escrito en `ARQUITECTURA.md` |

**Puerta de fase:** el primer script se puede ejecutar con `python3 unmassk-toolkit/bin/...` desde el repo, sin instalar nada.

---

## FASE 1 — El validador (sin git, sin ficheros: todo unitario)

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **1.1** | `lib/model.py` — las **catorce** dataclasses puras, sin lógica (eran «nueve» hasta derivarlas una a una: ver `PIEZAS.md` §5.3) [**corregido 2026-08-04**: decía «trece»; falta `NoteReport` (el informe de una nota por su identificador, decisión B6), añadida después de este recuento — `grep -c "^class " lib/memory/model.py` da 14. El mismo paso que presumía de haber corregido el número «de nueve a trece» volvió a quedarse corto] | Ultron | Importan y son inmutables |
| **1.2** | `lib/vocabulary.py` — los 7 tipos, sus campos, las 4 keys marcadoras, la lista negra, la palabra ilegal, la pregunta del dolor **en una sola copia**, y el tope de 80 caracteres | Ultron | Cada tipo declara sus campos obligatorios y permitidos |
| **1.3** | Declarar en `vocabulario.CAMPOS` el **lector** de cada campo (ruta de la función que lo lee) | Ultron | Un campo sin lector declarado hace fallar el módulo al importarse |
| **1.4** | `lib/zones.py` + sembrar `zones.json` del glossary del v1 más la estructura de carpetas | Ultron | Alias resuelve · zona inexistente rebota · lista negra da el mensaje de reglas · `audit` da la disyuntiva |
| **1.5** | `lib/format.py` — construir y parsear titular, cuerpo, línea de índice y línea de archivo | Ultron | **Round-trip: construir → parsear → objeto idéntico**, para los 7 tipos y para el Next (antes `⏩`, hoy `[NEXT]` + `🧭` — [corrección del propietario, 2026-08-03], ver `TEXTOS.md` §0 y §5) |
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
| **2.7** | El commit de trabajo, con la referencia a la issue. **Sin campo de ficheros tocados: retirado del v2.** Y admite commitear **solo ciertas rutas**, sin arrastrar el resto del índice — lo necesita la publicación, que commitea tres ficheros concretos | Ultron | El commit lleva su referencia · commitear tres rutas deja el resto del árbol intacto · la vista por fichero funciona con `git log -- <ruta>` |
| **2.8** | **MINA 1:** añadir las rutas del v2 a la lista de wrappers reconocidos en `unmassk-toolkit/hooks/pre-validate-commit-trailers.py:51` | Ultron | Un commit del v2 pasa el gate del v1. **Sin este paso, nada del v2 puede commitear** |
| **2.8b** | **MINA 4:** apuntar `bin/release.py` a `gitmem work` y quitarle el campo retirado | Ultron | Una publicación en seco funciona contra `gitmem` y commitea solo sus tres ficheros |
| **2.9** | Tests de la transacción | Dante | Los dos casos del paso 2.4, contra un repo real |

**Puerta de fase:** se pueden escribir notas de verdad y el índice nunca queda desincronizado del commit.

---

## FASE 3 — Índices, arranque y salud (primer entregable visible)

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **3.1** | `lib/query.py` — las cuatro lecturas desde git hacia objetos | Ultron | Sembrar tres notas y recuperarlas por ID, zona, palabra y fichero |
| **3.2** | `lib/context.py` + su script — el Next con su cuerpo, **sin zonas, sin índice, sin lápida** (el módulo sigue llamándose `context.py`; el subcomando expuesto es `next` — `bin/memory/next.py` [decisión del propietario, 2026-08-03]) | Ultron | Se escribe y se lee de vuelta · **y la aduana lo eximirá** (paso 6.3) |
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

## FASE 5 — retirada entera, 2026-08-03

`[decisión del propietario, 2026-08-03, B20]` **Sustituye a esta fase entera**, pasos 5.1 a 5.7 incluidos, con la semana de prueba (5.6). Motivo, literal del propietario: *«¿Por qué necesitamos inyectarle mierda de memoria a la gente? En su prompt le dices que lo primero que tiene que hacer es investigar en la memoria lo que tiene que ver con el fichero que va a tocar.»*

En vez de un vigilante que interceptaba cada encargo, adivinaba la zona por las palabras del texto y le pegaba memoria dentro (`lib/dispatch.py` del paso 5.2, y el hook de inyección del paso 5.3), **cada agente lo hace él solo, en tres pasos escritos en su propio prompt**: el historial del fichero que va a tocar, la zona que sale de ahí sin adivinarla, y los muros de esa zona. Escribir esos tres pasos en los nueve prompts es trabajo de otra fase, no de esta obra.

Las dos piezas que sostenían esta fase, `lib/memory/dispatch.py` y `hooks/inject.py`, junto con sus tests (`tests/memory/test_dispatch.py`, `tests/memory/test_inject_hook.py`), están retiradas — ver `PIEZAS.md` §9.8 y §11, `ARQUITECTURA.md` y `CALENDARIO.md`.

---

## FASE 6 — La aduana y el banco adversarial

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **6.1** | El hook de la aduana, llamando al **mismo validador** de la fase 1 | Ultron | No hay una segunda implementación de nada |
| **6.2** | El interruptor: **nace apagada**, se enciende proyecto a proyecto | Ultron | Apagada, el v1 sigue commiteando — se prueba en vivo |
| **6.3** | Las exenciones: el `wip` y el Next del cierre de sesión | Ultron | Ninguno de los dos recibe una sola pregunta |
| **6.4** | La décima validación: al cerrar una incidencia, se retiene el cierre preguntando si de esa cicatriz sale muro | Ultron | El cierre rebota con las dos opciones y el comando de relanzamiento |
| **6.5** | La undécima: al nacer un muro, se presentan **todas** las incidencias candidatas de la zona, nunca una preseleccionada | Ultron | Se listan todas; elegir ninguna es una respuesta válida |
| **6.6** | Alta de zona, paso 2: el sistema la da de alta a la vista y relanza | Ultron | La zona aparece en el fichero y el commit pasa a la segunda |
| **6.7** | El catálogo de ataques del banco adversarial | Dante | Duplicado, sin enlace, decisión que contradice, titular largo, zona inventada, key mal escrita, zona prohibida, `audit`, memo que era muro, destilación sin fuentes |
| **6.8** | El banco corre solo y **enseña su resultado** | Ultron | Un banco que nadie ejecuta es otro vigilante muerto |
| **6.9** | Tests de la aduana | Dante | Apagada no bloquea · encendida bloquea con el texto exacto · el `wip` pasa |

> **Nota [decisión del propietario, 2026-08-03]:** el subcomando `gitmem bench` se borra entero — «no lo he autorizado en la vida» (`DEUDA.md` PARTE 1, B4) — y con él cae el principio P12 de la especificación tal como estaba escrito, que lo exigía como invariante: ejecución automática **y** resultado visible por ese subcomando concreto (`docs/spec-sistema-memoria-v2.md` P12; `PIEZAS.md` §10, fila `gitmem bench`, dice literalmente que su veredicto sale «en la misma línea del arranque»). Los pasos 6.7 y 6.8 —el catálogo de ataques y «el banco corre solo y enseña su resultado»— siguen en pie como banco de pruebas: nada en la decisión de hoy dice que se retire el banco adversarial en sí. **Lo que queda sin decidir es su superficie de salida**, porque ya no puede ser `gitmem bench`: ¿se integra en el arranque junto a los otros avisos, o se queda solo en la suite de tests que corre Dante? No se rellena aquí por criterio propio — es un hueco para resolver antes de construir el paso 6.8.

---

## FASE 7 — Skills, agentes y periferia

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **7.1** | La skill de memoria: enseña a traer **todos los flags puestos** para que el coste normal sea un comando y cero rechazos | Orquestador | Un alta completa se escribe sin rebotar |
| **7.2** | En esa skill: la regla de los dos segundos, la calibración del bloqueante y del muro, y el árbol de tipos | Orquestador | Están escritas, con ejemplos |
| **7.2b** | En esa skill: la **mini-sección de la vista por fichero** — qué es, sus dos comandos, y cuándo la usa cada oficio. Los prompts de los agentes solo la referencian; el contenido vive una sola vez | Orquestador | Ningún prompt duplica el contenido |
| **7.3** | En esa skill: el disparador de búsqueda es **el usuario en lenguaje natural**, y las tres prohibiciones (sin disparadores léxicos, sin juicio espontáneo, sin inyección por mensaje) | Orquestador | Escrito |
| **7.4** | En esa skill: comunicar el menú del día en el primer mensaje y dejar que el usuario decida el rumbo | Orquestador | Escrito |
| **7.5** | El ciclo de vida de la pregunta abierta: se resuelve antes de construir sobre su módulo; puede parir una issue; al cerrarse asciende o cae | Orquestador + Ultron | El destino "ascendida a" aparece en el archivo |
| **7.6** | Los planes: documento en `docs/`, issue creada por Claude con `gh` **nunca por un script**, acta que enlaza decisión e issue, y edición de la issue al cambiar la decisión | Orquestador | Un ciclo completo de plan, real |
| **7.7** | **Gitto se RETIRA, no se reescribe — y NO se borra.** El 85-90% de su definición era el sistema viejo; lo que le quedaba ya no necesita un agente — consultar la memoria es un comando (`gitmem search`) y las operaciones de git las hace quien commitea. La tripulación pasa de diez a nueve. **Su definición se mueve a `unmassk-toolkit/deprecated/`** (decisión del propietario, 2026-08-02): fuera de `agents/` para que el harness no la registre, pero conservada | Orquestador | `agents/` tiene nueve · `deprecated/gitto.md` existe · ningún prompt ni skill lo sigue nombrando |
| **7.8** | House: el pie estructurado de su informe | Orquestador | — |
| **7.9** | Bilbo: el zoom-out obligatorio | Orquestador | — |
| **7.10** | `unmassk-close-session`: se parten los pasos 1-4 y gana cuatro renglones — el Next (con su resumen en prosa, no un acta de lo construido — [decisión del propietario, 2026-08-03]), la issue-plan al día, la poda de muros y el alta de bloqueantes | Orquestador | Un cierre real ejecuta los cuatro |
| **7.11** | `unmassk-core`: los seis puntos concretos | Orquestador | — |
| **7.12** | El bloque de `CLAUDE.md`: se reescribe entero. **Cambia el arranque de todos los proyectos instalados** | Orquestador | — |
| **7.13** | La skill de incidencias, con sus tres vertientes y sus cinco puntos internos resueltos al redactarla | Orquestador | Un ciclo completo de incidencia |
| **7.13b** | **La skill de destilación** — prepara el trabajo de la fase 8: mide con git cuántos commits hay y de qué clases, decide cuántas rondas, y define cómo se encadenan en cascada `[decisión del propietario, 2026-08-04, DEUDA.md B32]` | Orquestador | Sobre un historial real, la skill dice cuántas rondas salen y en qué orden — sin que nadie lo calcule a mano |
| **7.13c** | **La compactación de memoria de agente** — cada agente mira sus memorias, las contrasta contra el código o la documentación, informa, las modifica y dice qué cambió y por qué. Skill nueva **o** dentro de la del cambio del v1 al v2 `[decisión del propietario, 2026-08-04, DEUDA.md B33]` | Orquestador | Un agente real audita su memoria y entrega el informe con la prueba de cada cambio: fichero y línea |
| **7.13d** | **El prompt del cierre de sesión** — vive **dentro de `unmassk-close-session`**, y lo ejecuta un `general-purpose`: filtra el JSONL de la conversación, la lee entera, escribe el contexto en prosa y pone el Next `[decisión del propietario, 2026-08-04, DEUDA.md B34]`. **El filtro quita los volcados, nunca los comandos**; **no puede ir en `SessionEnd`**, donde ya no hay modelo que juzgue | Orquestador | Un cierre real produce contexto y Next sin que Claude los escriba de memoria |
| **7.14** | Publicar el toolkit con el sistema nuevo dentro | Orquestador | Se instala en un proyecto limpio y el arranque funciona |

---

## FASE 8 — La destilación, proyecto a proyecto

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **8.1** | Fijar la **fecha de corte** del proyecto | Orquestador + usuario | Escrita antes de empezar |
| **8.2** | Encender la aduana en ese proyecto | Orquestador | El primer commit del día ya pasa por ella |
| **8.2b** | **La cosecha de zonas** — pasada previa que **no destila nada**: saca los términos candidatos a zona del historial y se los presenta al propietario para que apruebe | Bilbo | Las zonas aprobadas están en `zones.json` **antes** de que empiece a destilar nadie |
| **8.3** | Se destila, **en rondas en cascada**, citando los hashes de origen | **Bilbo** `[decisión del propietario, 2026-08-04 — DEUDA.md B32]` | Cada nota destilada declara de qué sale |
| **8.4** | Los cinco destinos: hechos a memo, muros a restricción, preferencias a reglas, informes a documentación, pendiente a pregunta | Bilbo (misma decisión) | Ninguna cae en el saco equivocado |
| **8.5** | En la duda, se propone al usuario | Bilbo (misma decisión) | — |

> **Cómo se prepara y se trocea — `[decisión del propietario, 2026-08-04, B32]`. Sustituye al «sin decidir» que tenían estos tres pasos.**
>
> **Una skill nueva prepara el trabajo** (fase 7): mide con git **cuántos commits hay y de qué clases**, y de ahí sale cuántas rondas. Mil commits no caben en una sesión, y el reparto no se improvisa.
>
> **La pasada 0 es la cosecha de zonas** (paso 8.2b). Sin ella, cada ronda muere en «esa zona no existe» — la aduana rechaza zonas inventadas, y Bilbo no puede darlas de alta por su cuenta.
>
> **Y las rondas van EN CASCADA, de lo viejo a lo nuevo, nunca en paralelo:**
> ```
> ronda 1 → los primeros 100 commits             → produce N notas
> ronda 2 → LEE esas N notas + sus 100 commits   → produce M notas
> ronda 3 → LEE las N+M + sus 100 commits        → ...
> ```
> **El motivo es el que decide el diseño:** si las rondas son ciegas entre sí, **se destilan contradicciones como si todas fueran verdad** — una decisión de marzo sustituida en junio, y la ronda que ve marzo no sabe que murió. Leyendo **las notas ya destiladas** —no una lista de identificadores: las notas **con su porqué dentro**— cada ronda puede **sustituir con puntero**, que es justo lo que el v2 tiene y el v1 no.
| **8.6** | Orden: primero el toolkit, después un proyecto real | Orquestador | — |

---

## FASE 9 — Retirar el v1

| # | Paso | Quién | Verificación |
|---|---|---|---|
| **9.1** | Sacar de `hooks.json` los hooks de §5.1. **No se borran ficheros** | Ultron | Los hooks retirados no se ejecutan; el código queda de archivo muerto |
| **9.2** | Decidir fichero a fichero qué hacer con los catorce partidos | Orquestador | Lo más limpio es dejarlos y que el v2 no los use |
| **9.3** | Borrar los tests de cada pieza retirada, a la vez que la pieza | Dante | La suite queda verde y sin tests contra código muerto |
| **9.4** | Leer los resultados de la sonda pendiente del v1 y cerrarla | Orquestador | Afecta solo al sistema congelado |

---

## 6. Lo que este plan sigue sin resolver

1. **El carril de "ensayo operativo".** Ninguna definición de agente cubre "ejecuta una prueba y reporta". Esa tarea ya rebotó entre dos agentes en la sesión del diseño y la acabó haciendo el orquestador. **Va a volver a pasar en los pasos 2.6, 5.6 y 6.8.**
2. **El papel de Alexandria** en el flujo de documentación.
3. **La lista de zonas definitiva** de cada proyecto — es tarea tuya, con la materia prima preparada.
4. **El dedup semántico de reglas** — excede a un script.
5. *(resuelto — la zona del encargo se declara en el despacho y la ausencia se hace visible; ver paso 5.1)*
