# Arquitectura — ficheros, funciones y dependencias

Qué se escribe exactamente, y qué llama a qué. **31 módulos, 10 scripts, 2 hooks.** `[decía «22 módulos» tras retirar `lib/memory/dispatch.py` y `hooks/inject.py` — decisión del propietario, 2026-08-03, B20. Corregido a 31 el 2026-08-04: `ls unmassk-toolkit/lib/memory/*.py | wc -l`. Faltaban nueve particiones por el techo de 500 líneas que nunca se añadieron ni al árbol ni a las tablas — ver §2]` Ninguno pasa de 500 líneas por construcción.

**Regla de nombres, innegociable:** todo nombre que ve una máquina va **en inglés** — scripts, módulos, funciones, campos, flags y subcomandos. Dentro de lo que **lee** una persona (mensajes de rechazo, informes, textos del arranque), el eje **no** es «se busca / se lee» — así lo planteaba el principio P8, y de ahí salió el castellano en sitios que no tocaba. El eje real es **etiqueta contra explicación**: las etiquetas estructurales (`COUNTS`, `CHECKS`, `RESTRICTIONS`, `BLOCKERS`, `MEMORY`, y el resto de cabeceras y campos fijos) van en inglés aunque vivan dentro de un informe en español; el contenido que explica —los porqués, las descripciones, los rechazos en sí— se queda en castellano [decisión del propietario, 2026-08-03].

**El comando es `gitmem`** — una fachada única con subcomandos sobre los scripts.

**Y todo esto vive dentro de `unmassk-toolkit/`, no en un plugin aparte.** La memoria es infraestructura del núcleo: un plugin suelto puede no estar instalado, y entonces desaparecen el arranque, la aduana y la skill mientras el resto de la tripulación los sigue llamando. El nombre `unmassk-gitmemory` queda libre porque el v1 se borra en la misma rama, así que la skill nueva lo hereda y **no hay enlaces que romper ni paso de absorción**. Los módulos van en la subcarpeta `lib/memory/` porque **es la frontera**: la especificación manda un test que compruebe en cada ejecución que nadie de fuera importa de dentro y que nadie de dentro importa del toolkit. `[esta línea ha cambiado DOS VECES el 2026-08-04, y las dos merecen quedar. Por la mañana decía, en presente, que el test ya corría — y era falso: no existía ninguno. Por la tarde **se construyó**: `tests/memory/test_boundary.py`, y **encontró un fallo real en su primera ejecución** —que `note.py --replaces` no archivaba la nota vieja, dejando dos decisiones vigentes contradiciéndose—. Así que hoy sí corre, y con la suite. Lo que sigue **sin construir** es el cuarto, el de §13.1: el que genera el mermaid del grafo real y lo compara contra §4. La corrección de la mañana quedó vieja en cuatro horas, que es precisamente la velocidad a la que este documento envejece]`. Ese es su motivo — no el choque de nombres, que desapareció al pasar `colors.py` a llamarse `emojis.py`.

---

## 1. El árbol

```
unmassk-toolkit/                  ← el sistema nace DENTRO del toolkit, no como plugin aparte
│
├── hooks/
│   ├── hooks.json                Declarará DOS hooks de memoria — HOY NO DECLARA NINGUNO.
│   ├── customs.py                Intercepta el commit, llama al validador, bloquea con la pregunta dentro. Nace apagada.
│   └── boot_launcher.py          ~20 líneas sin lógica: llama a bin/boot.py. Se escribe una vez y no se itera jamás.

> **`hooks.json` no registra ninguno de los dos, y eso es a propósito** `[corregido 2026-08-04]`. Esta línea decía *«Declara DOS hooks y nada más»*, en presente, y es falso por partida doble: hoy ese fichero declara **nueve** hooks y **los nueve son del sistema viejo** (`session-start-boot`, `session-start-crew`, `pre-validate-commit-trailers`, `pre-merge-gate`, `validate-memory-path`, `user-prompt-memory-check`, `stop-dod-gate`, `stop-dod-check`, `stop-close-session`). Ni `customs.py` ni `boot_launcher.py` aparecen.
>
> **Los dos existen como fichero y tienen sus tests en verde, pero no se disparan nunca: son código muerto hasta que se registren.** Es deliberado — engancharlos mientras el sistema viejo sigue vivo dispararía **dos arranques a la vez**. Se registran al retirar el v1 (fase 9), y está anotado como punto **26** de `DEUDA.md`.
>
> Se corrige porque este documento describe el destino, no el presente, y escribir el destino en presente es exactamente cómo se cree que algo vigila cuando no lo hace.
│   (`inject.py` se retiró entera [decisión del propietario, 2026-08-03, B20]: cada agente busca su propia
│    memoria de proyecto en tres pasos escritos en su prompt, en vez de que un hook se la reparta por oficio.)
│
├── bin/
│   ├── gitmem                    La fachada: despacha el subcomando al script que toca. **Nueve subcomandos** —
│   │                             `note` `work` `wip` `remove` `next` `search` `zones` `rezones` `rule`.
│   │                             `boot` NO es uno de ellos [decisión del propietario, 2026-08-03].
│   └── memory/                   Los diez scripts, todos invocables por ruta.
│   ├── note.py                   Alta de nota de cualquiera de los 7 tipos; sustitución; descartes automáticos.
│   ├── work.py                   Commit de trabajo: escribe la referencia a issue.
│   ├── wip.py                    El checkpoint: `gitmem wip "mensaje"`, exento de toda pregunta del validador.
│   │                             **Nuevo** — el hueco ya existía: `validator.is_wip` sabía reconocer el commit
│   │                             exento, pero ningún comando lo escribía. Puerta abierta sin llave
│   │                             [decisión del propietario, 2026-08-03].
│   ├── remove.py                 Retirada sin reemplazo: saca la línea del índice y la archiva.
│   │                             *(antes `close.py` [decisión del propietario, 2026-08-03])*
│   ├── next.py                   Escribe el ⏩ del cierre de sesión.
│   │                             *(antes `context.py` [decisión del propietario, 2026-08-03])*
│   ├── search.py                 Las cuatro entradas. Siempre imprime un informe, nunca una lista.
│   ├── zones.py                  Listar, buscar equivalentes, dar de alta.
│   ├── rezones.py                Reconstruye los ocho índices desde git; con --verify solo diagnostica.
│   │                             *(antes `reindex.py` [decisión del propietario, 2026-08-03])*
│   ├── rule.py                   Alta y lectura de reglas (canal aparte).
│   └── boot.py                   El menú del día. **Ya no es subcomando de `gitmem`**: se dispara solo al abrir
│                                 sesión — lo llama `hooks/boot_launcher.py`, sin pasar por la fachada — y escribe
│                                 un documento completo que Claude lee entero, no una inyección con tope de tamaño
│                                 [decisión del propietario, 2026-08-03].
│
│   `bench.py` se ha borrado entero, no renombrado — *«no lo he autorizado en la vida»*
│   [decisión del propietario, 2026-08-03]. Con él cae la obligación de correrlo como invariante que le imponía
│   el principio P12 de la especificación. **No confundir con `tests/memory/`:** el banco adversarial que vive
│   ahí abajo es la suite de pruebas de Moriarty, no este comando, y sigue existiendo aparte.
│
├── lib/memory/                   Los 31 módulos del sistema — §2. Subcarpeta propia: **es la frontera**, pensada
│                                 para que un test la vigile (nadie de fuera importa de dentro; nadie de dentro
│                                 importa del toolkit fuera de una lista corta). `[decía «22 módulos» y que el test
│                                 ya vigila — corregido 2026-08-04: 31 módulos en disco, y el test está
│                                 especificado (`PIEZAS.md` §13/§13.1) sin construir — ver §1 introducción]`.
│                                 Con eso, el v2 entero se borra con un solo comando.
├── skills/
│   ├── unmassk-gitmemory/        Enseña a traer los flags puestos, el árbol de tipos, la calibración,
│   │                             y la mini-sección de la vista por fichero (§5).
│   │                             Hereda el nombre del v1, que se borra en esta misma rama.
│   └── unmassk-bug-protocol/     El protocolo de incidencias.
├── commands/remember.md
└── tests/memory/                 Incluido el banco adversarial.
```

---

## 2. Los módulos

| Módulo | Responsabilidad |
|---|---|
| `utf8.py` | Fuerza UTF-8. Primera sentencia de todo punto de entrada. |
| `emojis.py` | Los emojis: los de los siete tipos, los de canal y los de cabecera de sección. **Sin color** — decisión del propietario (2026-08-02): quien lee esto es Claude, y un código ANSI no le aporta nada; el emoji sí, porque viaja dentro del texto y sobrevive a cualquier canal. |
| `model.py` | **Catorce** dataclasses puras e inmutables, cero lógica y cero métodos. Rompe los ciclos de importación. Eran «nueve» hasta que se derivaron una a una desde las salidas — ver `PIEZAS.md` §5.3. `[decía «trece» — corregido 2026-08-04: faltaba `NoteReport`, el informe de una nota por su identificador (`TEXTOS.md` §2.4); `grep -c "^class " model.py` → 14]` |
| `gitcmd.py` | Capa git propia: ejecución con **stderr real**, raíz del repo, commit con rutas explícitas, candado de fichero, escritura atómica. |
| `vocabulary.py` | **Los datos cerrados**: 7 tipos, campos con su lector declarado, keys marcadoras, lista negra, palabra ilegal, la pregunta del dolor en una sola copia, los ocho índices. |
| `zones.py` | Carga de `zones.json`: zonas, alias, candidatas por parecido y alta. |
| `config.py` | Carga de `config.json`: interruptor de la aduana, tipo de repositorio y comando de tests. **Fichero aparte del de zonas, a propósito** — decisión del propietario: cada cosa en su sitio, no un cajón. |
| `format.py` | Construir y parsear: titular, cuerpo, mensaje, línea de índice, línea de archivo. **Pareja productor↔consumidor.** |
| `format_lines.py` | **[añadido 2026-08-04, faltaba]** La línea de índice y la línea de archivo — partido de `format.py` por tamaño (519 líneas, techo 500). `format.py` importa estos cuatro nombres de aquí y los reexpone; sigue siendo una sola pareja productor↔consumidor, no dos. |
| `similar.py` | Detector léxico dentro de la zona. Recibe datos; no lee ficheros. |
| `validator.py` | **La pieza única.** El punto de entrada (`validate_note`) de "esto es válido". |
| `validator_zones.py` | **[añadido 2026-08-04, faltaba]** La legalidad del nombre de zona: existencia, alias, lista negra, palabra ilegal — partido de `validator.py` por tamaño (552 líneas, techo 500). Reexportado como `validator.validate_zones`; no es una segunda puerta de validación. |
| `validator_pointers.py` | **[añadido 2026-08-04, faltaba]** Los punteros (`Replaces`/`Origin`) apuntan a notas que existen; un muro no nace sin decir de qué incidencia sale — partido de `validator.py` por el mismo techo. Reexportado como `validator.validate_pointers`. |
| `validator_issue.py` | **[añadido 2026-08-04, faltaba]** Comprobación contra GitHub de que la issue del acta existe de verdad — partido de `validator.py` por el mismo techo. Reexportado como `validator.validate_issue`; lo llama directo `bin/memory/note.py`, no pasa por `validate_note`. |
| `rejection.py` | Un texto, dos renderizados: terminal y bloqueo de hook. |
| `ids.py` | Contador por tipo leyendo el índice; detector de duplicados. |
| `indexes.py` | Lectura y escritura de los ocho ficheros. Nadie más los toca. |
| `notes.py` | **La transacción**: validar → índice → commit de nota+índice juntos → si git falla, restaurar y propagar el error real. La mecánica de git que usa por debajo vive en `notes_commit.py`. |
| `notes_commit.py` | **[añadido 2026-08-04, faltaba]** La mecánica de git de `notes.py`: candado global, ruta de los ocho índices, `git add`+`git commit` con restauración de mejor esfuerzo si falla, y `write_work` — el commit de trabajo que no toca ningún índice. Partido de `notes.py` por tamaño (550 líneas, techo 500). |
| `query.py` | Lectura desde el historial hacia objetos: por identificador, zona, palabra y fichero. |
| `clusters.py` | Agrupación determinista por punteros. Nunca por similitud ni por keys. |
| `report.py` | Construye el estado de una zona: muros arriba, racimos, preguntas al final. |
| `report_render.py` | Convierte ese estado en texto, con la presentación heredada. Separado para no pasar de 500 líneas. |
| `report_render_note.py` | **[añadido 2026-08-04, faltaba]** Convierte el informe de una nota por su identificador (`NoteReport`) en texto — molde en `TEXTOS.md` §2.4. Fichero aparte de `report_render.py`, no una función más allí, por el mismo techo de 500 líneas. |
| `health.py` | Coherencia índices↔git, identificadores duplicados, planes con commits sin reflejar. Esto último vive en `health_plans.py`. |
| `health_plans.py` | **[añadido 2026-08-04, faltaba]** La red de seguridad de planes de acta sin reflejar en commits — partida de `health.py` por el mismo techo. Reexportado como `health.plans_unreflected`. |
| `boot.py` | Compone el menú del día. Solo renderiza. |
| `context.py` | Lector y escritor del ⏩. |
| `rules.py` | El fichero de reglas: alta y entrega completa. Sin zonas, sin índice, a propósito. |
| `rezones_commit.py` | **[añadido 2026-08-04, faltaba]** Aplica el plan de `health.rebuild_plan()` sobre los índices reales y lo guarda en un solo commit (o sin commit si ya coincide con `HEAD`); mismo contrato de transacción que `notes.write`/`replace`/`close`. Lo usa `bin/memory/rezones.py`. |
| `repo_guard.py` | **[añadido 2026-08-04, faltaba]** Rechaza un commit directo sobre la rama principal de un repositorio protegido. Compartido por `bin/memory/work.py` y `bin/memory/wip.py` — el checkpoint tiene la misma protección que el commit de trabajo. |

*(`dispatch.py` — la tabla de qué ve cada oficio — se retiró entera [decisión del propietario, 2026-08-03, B20]. Cada agente busca su propia memoria en tres pasos escritos en su prompt, en vez de que un hook se la reparta.)*

---

## 3. Las funciones que importan

### `validator.py` — la pieza compartida

**`[corregido 2026-08-04]`** Tres de las filas de abajo no viven en `validator.py`: se partieron por el techo de 500 líneas (`DEUDA.md` punto 14, 552 líneas) y `validator.py` las importa de forma plana y las reexpone bajo el mismo nombre — sigue habiendo una sola implementación de "esto es válido", nunca dos puertas. También faltaba `validate_issue` entera.

| Función | Vive en | Qué hace |
|---|---|---|
| `validate_note` | `validator.py` | Entrada única. Corre `validate_type`, `validate_zones`, `validate_headline`, `validate_fields`, `validate_pointers`, `validate_replacement` y devuelve los fallos (vacío = válida). No incluye `validate_pain_question`, `validate_issue` ni `validate_distillation`: necesitan un dato que no es campo de `Note` ni de `Context`. |
| `validate_headline` | `validator.py` | Longitud, formato, idioma. |
| `validate_zones` | **`validator_zones.py`** | Existencia, alias, lista negra, palabra ilegal, alta en dos pasos. |
| `validate_type` | `validator.py` | El árbol: si no encaja limpio en ninguno de los siete, rechaza preguntando qué es. |
| `validate_fields` | `validator.py` | Obligatorios por tipo; no permitidos para ese tipo; inexistentes. |
| `normalize_keys` | `validator.py` | Vocabulario controlado; cinco como máximo; ninguna que ya esté en el titular. |
| `validate_pain_question` | `validator.py` | Exige la respuesta en memo y muro; si contradice al tipo, lo dice. |
| `validate_pointers` | **`validator_pointers.py`** | Los identificadores citados existen; un muro sin origen lista todas las incidencias de la zona. |
| `validate_replacement` | `validator.py` | Si hay parecidas y no se declara sustitución, rechaza con las candidatas dentro. |
| `validate_distillation` | `validator.py` | Toda destilación exige fuentes. Por tipo de nota, no por autor. |
| `validate_issue` | **`validator_issue.py`** | **[añadido 2026-08-04, faltaba entera]** Verificación única contra GitHub de que la issue del acta existe de verdad. La llama directo `bin/memory/note.py`, no pasa por `validate_note`. |
| `is_wip` | `validator.py` | Identifica el commit exento de toda pregunta. |
| `Context` | `validator.py` | Todo lo que el validador necesita saber del mundo, pasado por el llamante. **Ni abre ficheros ni llama a git.** |

### `notes.py` y `notes_commit.py` — la transacción

**`[corregido 2026-08-04]`** `write_work` no vive en `notes.py`: vive en `notes_commit.py`, junto con la mecánica de git que las cuatro funciones de arriba usan por debajo (candado, `git add`+`git commit`, restauración de mejor esfuerzo).

| Función | Vive en | Qué hace |
|---|---|---|
| `write` | `notes.py` | Candado → identificador → validar → índice → commit de nota+índice **en un solo commit** → si git falla, restaura el índice y devuelve el error real. |
| `replace` | `notes.py` | Un commit con la nota nueva, su línea, la vieja retirada y su línea archivada. |
| `close` | `notes.py` | Un commit con la línea fuera del índice y dentro del archivo. |
| `discard_alternatives` | `notes.py` | Los descartes con su origen. **Cada uno con su propio commit, su identificador y su línea de índice** — "un acto, un commit" aplica a nota+índice, no al acto completo. |
| `write_work` | **`notes_commit.py`** | Commit de trabajo con la referencia a issue. **Sin campo de ficheros tocados: se retiró del v2.** |

---

## 4. El grafo

```
                    utf8   emojis   model
                      └───────┴────────┴──────────────┐
   vocabulary ──────┬──── format ──────┬──── indexes  │   gitcmd
       │            │        │         │        │     │      │
       │        zones        │         │        │     └──────┤
       └──► similar          │         │        │            │
                └──► ★ validator ◄─────┘        │            │
                          │  │                  │            │
                     rejection│     ids ────────┤            │
                          │  └──► ● notes ◄─────┴────────────┘
                          │            │
                          │         query ──┬── clusters ── report ── render
                          │            ├── health
                          │            ├── context
                          │            └──────────► boot
   ┌──────────────────────┴───────────────────────────────────────────────┐
▲ hooks/customs.py       bin/note.py  work.py  wip.py  remove.py  next.py
                          bin/search.py  zones.py  rezones.py  rule.py   ── gitmem (fachada, 9 subcomandos)
▲ hooks/boot_launcher.py ───────────────────────────────────► bin/boot.py   (automático, no por gitmem
                                                                             [decisión del propietario, 2026-08-03])
```

*(`hooks/inject.py` y `dispatch` desaparecen de este grafo — retirados enteros [decisión del propietario, 2026-08-03, B20].)*

**`[corregido 2026-08-04]` Nueve satélites que faltan en el dibujo de arriba**, verificados contra los `import` reales — el dibujo ASCII no se retocó a mano porque un redibujado sin verificación de alineado es peor que no redibujar; se listan aparte:

| Satélite | Cuelga de | Verificado |
|---|---|---|
| `format_lines.py` | `format.py` lo importa (`emojis`, `model` también entran en el satélite) | `grep "^from \|^import" format.py` |
| `validator_zones.py` | `validator.py` lo importa; el satélite importa `model`, `rejection`, `zones`, `vocabulary` | idem en `validator.py` / `validator_zones.py` |
| `validator_pointers.py` | `validator.py` lo importa; el satélite importa `model`, `rejection` | idem |
| `validator_issue.py` | `validator.py` lo importa; el satélite importa `model`, `rejection` | idem, y `bin/memory/note.py` lo usa directo vía `validator.validate_issue` |
| `notes_commit.py` | `notes.py` lo importa; el satélite importa `gitcmd`, `indexes`, `model` | idem |
| `health_plans.py` | `health.py` lo importa; el satélite importa `query` | idem |
| `report_render_note.py` | Ninguno del núcleo lo importa — lo importa `bin/memory/search.py` directo; el satélite importa `emojis`, `model`, `report_render`, `vocabulary` | `grep` en `bin/memory/search.py` |
| `rezones_commit.py` | `bin/memory/rezones.py` lo importa directo (no `health.py`); el satélite importa `gitcmd`, `indexes`, `model`, `notes_commit` | idem |
| `repo_guard.py` | `bin/memory/work.py` y `bin/memory/wip.py` lo importan directo; el satélite solo importa `gitcmd` | idem |

**El validador compartido, en concreto:**

- Hay **una sola** implementación de "esto es válido" — repartida en cuatro ficheros (`validator.py` como entrada, más los tres satélites de arriba), pero con un único punto de entrada, `validate_note`, y las piezas partidas reexportadas bajo el mismo nombre. `[corregido 2026-08-04, decía sin más «validator.py»]`
- El módulo `validator.py` lo importan directo **cuatro ficheros**, no dos: `notes.py`, `hooks/customs.py`, `bin/memory/note.py` y `bin/memory/remove.py`. Los dos últimos no pasan por `validate_note` — importan `validator.py` solo por lo que queda fuera de esa entrada única (`Context`, `normalize_keys`, `validate_pain_question`, `validate_issue`). `[corregido 2026-08-04, decía «exactamente dos consumidores»; verificado por grep]`
- `rejection.py` lo importan bastante más que esos dos: los tres satélites del validador, `rules.py` (y por tanto `bin/memory/rule.py`), y `bin/memory/note.py`/`remove.py` para los rechazos que generan por su cuenta. Sigue siendo **un solo texto con dos renderizados** — terminal y bloqueo de hook — nunca una segunda implementación de rechazo. `[corregido 2026-08-04, decía «lo comparten los mismos dos»; verificado por grep]`
- `vocabulary.py` es datos, no validación. Lo leen también el formato, el render y el arranque, pero solo para presentar. **Nadie valida contra él sin pasar por el validador.**
- `similar.py` sigue con un único importador, verificado: `validator.py`. `zones.py` sí lo llaman los scripts directamente (`bin/memory/zones.py`, `note.py`, `remove.py`, `search.py`, `hooks/customs.py`, `report.py`) para listar y dar de alta — lo que sigue siendo cierto es que ningún script repite la *validación* de legalidad de un nombre de zona por su cuenta; esa comprobación vive solo en `validator_zones.py`, llamada por el validador. `[corregido 2026-08-04, decía que ningún script llamaba a `zones.py`; verificado por grep]`
- Consecuencia buscada: como el generador valida en proceso con la misma pieza, **la aduana casi nunca dispara**. Existe para lo que no pasa por el generador — un commit a mano, y los subagentes.

---

## 5. La vista por fichero — sin campo propio

El campo de ficheros tocados **no existe en el v2**: era un duplicado de lo que git ya guarda, y en el v1 se escribió 605 veces sin que nadie lo leyera. La función se conserva entera sin él:

```
git log -- <fichero>              qué se ha hecho en este fichero y cuándo
git diff --name-only <base>       qué toca esta rama
```

**Se documenta como mini-sección propia dentro de la skill de memoria**, con los comandos y con cuándo la usa cada oficio:

| Oficio | Cuándo |
|---|---|
| Diagnóstico | Antes de diagnosticar: qué se tocó ahí y cuándo |
| Implementador | Al retomar una rama: qué llevaba ya tocado |
| Explorador | En su zoom-out: el radio de daño real |
| Tests | Al testear un arreglo: qué ficheros entraron en el fix |

**Los prompts de los agentes solo referencian esa sección.** El contenido vive una sola vez, en la skill — si se duplica en cinco prompts, en tres meses hay cinco versiones distintas.

---

## 6. Auditoría: ningún campo sin lector

**`[corregido 2026-08-04]`** Las filas `Why`/`Description`/`Awaits` citaban dos lectores que ya no son públicos, y uno de ellos **nunca existió de verdad** — es el caso más ilustrativo del barrido de hoy:

- `report_render.render` **no existe, y no es un renombrado: se borró entera.** Existía **solo para que este mismo chequeo (`vocabulary.FIELDS`) encontrara un símbolo con ese nombre** — un lector de mentira, escrito para engañar a la puerta que vigila que ningún campo se quede sin lector real. La pieza que vigila el código muerto se lo estaba haciendo a sí misma. El lector real, el que de verdad se invoca desde fuera de `report_render.py` y llega a los campos `why`/`description`, es **`report_render.render_zone`** — la función pública que ya declara §9.2/9.3 de `PIEZAS.md`.
- `boot.blockers_section` **pasó a `boot._blockers_section` (interna), mismo motivo exacto**: era pública solo para que este chequeo la encontrara, y fuera de `boot.py` no la llamaba nadie. Su lector real, el que sí es público y sí llega al campo `awaits`, es **`boot.render`** — la función que ya declara §9.5 de `PIEZAS.md` y que invoca a `_blockers_section` por dentro.

`vocabulary.py` ya declara los lectores corregidos en su propio código (`FIELDS["why"]`/`["description"]` → `"report_render.render_zone"`, `FIELDS["awaits"]` → `"boot.render"`), fechado el mismo 2026-08-04. Esta tabla solo estaba desfasada respecto a esa corrección.

| Se escribe | Lo escribe | **Lo lee** |
|---|---|---|
| `Why` | `format.build_message` | `report_render.render_zone` |
| `Keys` | idem | `query.by_word` *(`dispatch.content_for` también lo leía — retirado entero, B20)* |
| `Description` | idem | `report_render.render_zone` |
| `Origin` | idem | `clusters.group` |
| `Replaces` | idem | `clusters.group` · `notes.replace` |
| `Awaits` | idem (solo en bloqueantes) | `boot.render` (invoca a `_blockers_section` por dentro, interna desde 2026-08-04) |
| `Issue` | `notes_commit.write_work` `[corregido 2026-08-04, decía `notes.write_work`]` · y el acta de plan, que es una **M** con `Origin:` + `Issue:` (no existe tipo `PLAN`) | `health.plans_unreflected` · `validator.validate_issue` (verificación única contra GitHub) |
| `Context` | `context.write` | `context.latest` → `boot.next_section` |
| Los siete índices | `indexes.insert/remove` | `ids.next` · `report.build` · `health.coherence` — *(`indexes.counts` estaba en esta lista y **no tiene ningún llamador de producción**: `[corregido 2026-08-04]`. Ni el arranque ni el informe de zona la usan — los dos cuentan por su cuenta desde git. Se conserva porque tres tests de `health.py` la usan como **segunda opinión**, para comprobar que la coherencia no se inventa sus números; retirarla obligaría a teclear el valor esperado a mano)* |
| El archivo | `indexes.archive` | `indexes.read_archive` → informe con historia |
| `zones.json` | `zones.add` | `zones.load` → `validator.validate_zones` |
| `config.json` | a mano / la instalación | `config.load` → la aduana (interruptor) · el cierre de sesión (comando de tests) · el tipo de repositorio |
| El fichero de reglas | `rules.add` | `rules.read` → el comando |

**Ocho campos, ocho lectores.** Ninguno queda sin uno, y un test recorre los campos declarados, importa la función lectora de cada uno y falla si no existe (paso 1.10 del plan). Así el principio deja de depender de que alguien se acuerde.

---

## 6bis. Los dos ficheros de configuración del proyecto

Separados a propósito. Viven los dos en `.claude/project-memory/`, junto a los ocho índices:

| Fichero | Qué guarda | Quién lo escribe |
|---|---|---|
| `zones.json` | Las zonas válidas del proyecto y sus alias | `gitmem zones add` *(antes `alta` — decisión del propietario, 2026-08-04, B29: los tres subcomandos pasan a inglés)*, y el alta en dos pasos de la aduana |

**La forma de `zones.json`, fijada aquí** — ningún documento la decía, y se decidió al implementar (2026-08-02). Queda escrita para que no vuelva a depender de quien la escriba:

```json
{
  "billing":  { "description": "cobros, pasarela de pago, suscripciones",
                "aliases": ["cobros", "pagos"] },
  "invoices": { "description": "documentos de factura emitidos al cliente",
                "aliases": [] }
}
```

El nombre de la zona es la clave; dentro van su descripción de una línea —la que imprime el rechazo de zona inexistente— y sus alias. **El recuento de notas NO se guarda aquí**: lo calcula quien lo imprime, leyendo el índice. Un número guardado se separa de la realidad, y este fichero lo edita también una persona a mano.
| `config.json` | El interruptor de la aduana, el tipo de repositorio y el comando de tests | A mano o en la instalación |

**Por qué dos y no uno:** las zonas cambian a menudo y las escribe el sistema; la configuración cambia una vez y la pone una persona. Meterlas en el mismo fichero es cómo una escritura automática acaba pisando un ajuste que alguien puso a mano.

El segundo hereda lo que hoy vive en `.claude/git-memory-config.json` — `repo_type` y `test_command` — que el barrido del repo destapó como huérfanos: varias skills los escriben y ningún documento del plan los recogía.

---

## 7. La zona del encargo — resuelto

La especificación no decía cómo sabe la inyección en qué zona trabaja el agente. Se resuelve así:

1. **El despacho la declara**: una línea `Zone: z1/z2` en el encargo del subagente. Lo escribe el orquestador y lo enseña la skill.
2. **Respaldo**: si no está, casado por palabras del encargo contra el fichero de zonas.
3. **Y si aun así no se puede determinar, el hook NO se calla.** Inyecta un bloque que lo dice:

```
[PROJECT MEMORY]
No se pudo determinar la zona de este encargo, así que este agente
trabaja SIN memoria de proyecto: no ve los muros de ninguna zona.
Si el encargo tiene zona, declárala con una línea «Zone: z1/z2».
```

**Por qué importa el punto 3:** el silencio es el fallo del v1 — algo deja de pasar y nadie se entera. Con el aviso, un despacho sin zona sale en el informe del agente y se ve. Es el principio P6 aplicado al reparto: el cero se enseña, no se calla.

**La cabecera `[PROJECT MEMORY]` va en inglés y el resto del bloque en castellano, y no es un descuido.** [decisión del propietario, 2026-08-03]: las etiquetas estructurales —lo que enmarca, no lo que explica— van en inglés (`MEMORIA`→`MEMORY`, y así con el resto); el contenido explicativo se queda en castellano. El eje no es «lo que se busca / lo que se lee», que es como lo planteaba el principio P8 y de ahí salió el castellano de esta cabecera; el eje correcto es etiqueta contra explicación.
