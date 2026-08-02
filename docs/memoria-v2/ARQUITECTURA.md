# Arquitectura — ficheros, funciones y dependencias

Qué se escribe exactamente, y qué llama a qué. **27 módulos, 10 scripts, 3 hooks.** Ninguno pasa de 500 líneas por construcción.

**Regla de nombres, innegociable:** todo nombre que ve una máquina va **en inglés** — scripts, módulos, funciones, campos, flags y subcomandos. Lo que se **lee** (mensajes de rechazo, informes, textos del arranque) va en español. Es el principio P8 extendido a todo lo mecánico.

**El comando es `gitmem`** — una fachada única con subcomandos sobre los scripts.

---

## 1. El árbol

```
unmassk-memory/
├── .claude-plugin/plugin.json
│
├── hooks/
│   ├── hooks.json                Declara TRES hooks y nada más.
│   ├── customs.py                Intercepta el commit, llama al validador, bloquea con la pregunta dentro. Nace apagada.
│   ├── inject.py                 Mete el contenido por oficio en el encargo del subagente. Fallo abierto absoluto.
│   └── boot_launcher.py          ~20 líneas sin lógica: llama a bin/boot.py. Se escribe una vez y no se itera jamás.
│
├── bin/                          (todos invocables por ruta; gitmem es la fachada)
│   ├── gitmem                    La fachada: despacha el subcomando al script que toca.
│   ├── note.py                   Alta de nota de cualquiera de los 7 tipos; sustitución; descartes automáticos.
│   ├── close.py                  Retirada sin reemplazo: saca la línea del índice y la archiva.
│   ├── context.py                Escribe el ⏩ del cierre de sesión.
│   ├── work.py                   Commit de trabajo: escribe la referencia a issue.
│   ├── search.py                 Las cuatro entradas. Siempre imprime un informe, nunca una lista.
│   ├── boot.py                   El menú del día.
│   ├── reindex.py                Reconstruye los ocho índices desde git; con --verify solo diagnostica.
│   ├── zones.py                  Listar, buscar equivalentes, dar de alta.
│   ├── rule.py                   Alta y lectura de reglas (canal aparte).
│   └── bench.py                  Lanza el banco adversarial e imprime el resultado.
│
├── lib/                          27 módulos — §2
├── skills/
│   ├── unmassk-memory/           Enseña a traer los flags puestos, el árbol de tipos, la calibración,
│   │                             y la mini-sección de la vista por fichero (§5).
│   └── unmassk-bug-protocol/     El protocolo de incidencias.
├── commands/remember.md
└── tests/                        Incluido el banco adversarial.
```

---

## 2. Los módulos

| Módulo | Responsabilidad |
|---|---|
| `utf8.py` | Fuerza UTF-8. Primera sentencia de todo punto de entrada. |
| `colors.py` | Constantes de color y los emojis de los siete tipos. |
| `model.py` | Nueve dataclasses puras, cero lógica. Rompe los ciclos de importación. |
| `gitcmd.py` | Capa git propia: ejecución con **stderr real**, raíz del repo, commit con rutas explícitas, candado de fichero, escritura atómica. |
| `vocabulary.py` | **Los datos cerrados**: 7 tipos, campos con su lector declarado, keys marcadoras, lista negra, palabra ilegal, la pregunta del dolor en una sola copia, los ocho índices. |
| `zones.py` | Carga del fichero de zonas, alias, candidatas por parecido, alta, y el interruptor de la aduana. |
| `format.py` | Construir y parsear: titular, cuerpo, mensaje, línea de índice, línea de archivo. **Pareja productor↔consumidor.** |
| `similar.py` | Detector léxico dentro de la zona. Recibe datos; no lee ficheros. |
| `validator.py` | **La pieza única.** La única implementación de "esto es válido". |
| `rejection.py` | Un texto, dos renderizados: terminal y bloqueo de hook. |
| `ids.py` | Contador por tipo leyendo el índice; detector de duplicados. |
| `indexes.py` | Lectura y escritura de los ocho ficheros. Nadie más los toca. |
| `notes.py` | **La transacción**: validar → índice → commit de nota+índice juntos → si git falla, restaurar y propagar el error real. |
| `query.py` | Lectura desde el historial hacia objetos: por identificador, zona, palabra y fichero. |
| `clusters.py` | Agrupación determinista por punteros. Nunca por similitud ni por keys. |
| `report.py` | Construye el estado de una zona: vallas arriba, racimos, preguntas al final. |
| `report_render.py` | Convierte ese estado en texto, con la presentación heredada. Separado para no pasar de 500 líneas. |
| `health.py` | Coherencia índices↔git, identificadores duplicados, planes con commits sin reflejar. |
| `boot.py` | Compone el menú del día. Solo renderiza. |
| `context.py` | Lector y escritor del ⏩. |
| `rules.py` | El fichero de reglas: alta y entrega completa. Sin zonas, sin índice, a propósito. |
| `dispatch.py` | La tabla de qué ve cada oficio, y de dónde sale la zona del encargo. |

---

## 3. Las funciones que importan

### `validator.py` — la pieza compartida

| Función | Qué hace |
|---|---|
| `validate_note` | Entrada única. Corre todo lo de abajo y devuelve la nota normalizada o los fallos. |
| `validate_headline` | Longitud, formato, idioma. |
| `validate_zones` | Existencia, alias, lista negra, palabra ilegal, alta en dos pasos. |
| `validate_type` | El árbol: si no encaja limpio en ninguno de los siete, rechaza preguntando qué es. |
| `validate_fields` | Obligatorios por tipo; no permitidos para ese tipo; inexistentes. |
| `normalize_keys` | Vocabulario controlado; cinco como máximo; ninguna que ya esté en el titular. |
| `validate_pain_question` | Exige la respuesta en memo y valla; si contradice al tipo, lo dice. |
| `validate_pointers` | Los identificadores citados existen; una valla sin origen lista todas las incidencias de la zona. |
| `validate_replacement` | Si hay parecidas y no se declara sustitución, rechaza con las candidatas dentro. |
| `validate_distillation` | Toda destilación exige fuentes. Por tipo de nota, no por autor. |
| `is_wip` | Identifica el commit exento de toda pregunta. |
| `Context` | Todo lo que el validador necesita saber del mundo, pasado por el llamante. **Ni abre ficheros ni llama a git.** |

### `notes.py` — la transacción

| Función | Qué hace |
|---|---|
| `write` | Candado → identificador → validar → índice → commit de nota+índice **en un solo commit** → si git falla, restaura el índice y devuelve el error real. |
| `replace` | Un commit con la nota nueva, su línea, la vieja retirada y su línea archivada. |
| `close` | Un commit con la línea fuera del índice y dentro del archivo. |
| `discard_alternatives` | Los descartes con su origen. **Cada uno con su propio commit, su identificador y su línea de índice** — "un acto, un commit" aplica a nota+índice, no al acto completo. |
| `write_work` | Commit de trabajo con la referencia a issue. **Sin campo de ficheros tocados: se retiró del v2.** |

### `dispatch.py` — el mapa por oficio

| Oficio | Qué recibe |
|---|---|
| Implementador | Las vallas de la zona + la decisión vigente que gobierna el módulo |
| Tests | Las vallas + las incidencias |
| Diagnóstico | Las incidencias |
| Revisores | Incidencias abiertas + notas marcadas de seguridad o antipatrón |
| Adversario | Las vallas + las incidencias |
| Juez | La decisión vigente + las vallas |
| Explorador | El informe completo de la zona |

---

## 4. El grafo

```
                    utf8   colors   model
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
                          │            ├── health                       │
                          │            ├── context                      │
                          │            ├── dispatch ◄───────────────────┘
                          │            └──────────► boot
   ┌──────────────────────┴───────────────────────────────────────────────┐
▲ hooks/customs.py    ● bin/note.py  close.py  context.py  work.py
▲ hooks/inject.py       bin/search.py  boot.py  reindex.py
▲ hooks/boot_launcher.py  bin/zones.py  rule.py  bench.py     ── gitmem (fachada)
```

**El validador compartido, en concreto:**

- Hay **una sola** implementación de "esto es válido": `validator.py`.
- La importan **exactamente dos consumidores**: `notes.py` (y por su intermedio los cuatro scripts que escriben) y `hooks/customs.py`.
- `rejection.py` lo comparten los mismos dos: el generador imprime la versión de terminal, la aduana emite la de bloqueo. **Mismo texto, dos salidas.**
- `vocabulary.py` es datos, no validación. Lo leen también el formato, el render y el arranque, pero solo para presentar. **Nadie valida contra él sin pasar por el validador.**
- `zones.py` y `similar.py` no los llaman los scripts: los llama el validador por dentro. Así no hay una segunda puerta.
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

| Se escribe | Lo escribe | **Lo lee** |
|---|---|---|
| `Why` | `format.build_message` | `report_render.render` |
| `Keys` | idem | `query.by_word` · `dispatch.content_for` |
| `Description` | idem | `report_render.render` |
| `Origin` | idem | `clusters.group` |
| `Replaces` | idem | `clusters.group` · `notes.replace` |
| `Awaits` | idem (solo en bloqueantes) | `boot.blockers_section` |
| `Issue` | `notes.write_work` | `health.plans_unreflected` |
| `Context` | `context.write` | `context.latest` → `boot.next_section` |
| Los siete índices | `indexes.insert/remove` | `ids.next` · `indexes.counts` · `report.build` · `health.coherence` |
| El archivo | `indexes.archive` | `indexes.read_archive` → informe con historia |
| El fichero de zonas | `zones.add` | `zones.load` → `validator.validate_zones` |
| El fichero de reglas | `rules.add` | `rules.read` → el comando |

**Ocho campos, ocho lectores.** Ninguno queda sin uno, y un test recorre los campos declarados, importa la función lectora de cada uno y falla si no existe (paso 1.10 del plan). Así el principio deja de depender de que alguien se acuerde.

---

## 7. La zona del encargo — resuelto

La especificación no decía cómo sabe la inyección en qué zona trabaja el agente. Se resuelve así:

1. **El despacho la declara**: una línea `Zone: z1/z2` en el encargo del subagente. Lo escribe el orquestador y lo enseña la skill.
2. **Respaldo**: si no está, casado por palabras del encargo contra el fichero de zonas.
3. **Y si aun así no se puede determinar, el hook NO se calla.** Inyecta un bloque que lo dice:

```
[MEMORIA DE PROYECTO]
No se pudo determinar la zona de este encargo, así que este agente
trabaja SIN memoria de proyecto: no ve las vallas de ninguna zona.
Si el encargo tiene zona, declárala con una línea «Zone: z1/z2».
```

**Por qué importa el punto 3:** el silencio es el fallo del v1 — algo deja de pasar y nadie se entera. Con el aviso, un despacho sin zona sale en el informe del agente y se ve. Es el principio P6 aplicado al reparto: el cero se enseña, no se calla.
