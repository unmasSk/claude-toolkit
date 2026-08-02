# Arquitectura — ficheros, funciones y dependencias

Qué se escribe exactamente, y qué llama a qué. **28 módulos, 10 scripts, 2 hooks.** Ninguno pasa de 500 líneas por construcción.

---

## 1. El árbol

```
unmassk-memory/
├── .claude-plugin/plugin.json    Manifiesto del plugin nuevo.
│
├── hooks/
│   ├── hooks.json                Declara DOS hooks. El resto no aparece, a propósito.
│   ├── aduana.py                 Intercepta el commit, llama al validador, bloquea con la pregunta dentro. Nace apagada.
│   └── inyeccion.py              Mete el contenido por oficio en el encargo del subagente. Fallo abierto absoluto.
│
├── bin/
│   ├── nota.py                   Alta de nota de cualquiera de los 7 tipos; sustitución; descartes automáticos.
│   ├── cerrar.py                 Retirada sin reemplazo: saca la línea del índice y la archiva.
│   ├── contexto.py               Escribe el ⏩ del cierre de sesión.
│   ├── trabajo.py                Commit de TRABAJO: único escritor de los ficheros tocados y de la referencia a issue.
│   ├── buscar.py                 Las cuatro entradas. Siempre imprime un informe, nunca una lista.
│   ├── arrancar.py               El menú del día.
│   ├── regenerar-indices.py      Reconstruye los ocho desde git; con --verificar solo diagnostica.
│   ├── zonas.py                  Listar, buscar equivalentes, dar de alta.
│   ├── regla.py                  Alta y lectura de reglas (canal aparte).
│   └── banco.py                  Lanza el banco adversarial e imprime el resultado.
│
├── lib/                          28 módulos — detalle en §2
├── skills/
│   ├── unmassk-memoria/          Enseña a traer los flags puestos, el árbol de tipos, la calibración.
│   └── unmassk-bug-protocol/     El protocolo de incidencias.
├── commands/remember.md          Entrega el fichero de reglas entero.
└── tests/                        Incluido el banco adversarial.
```

---

## 2. Los módulos y sus responsabilidades

| Módulo | Responsabilidad |
|---|---|
| `utf8.py` | Fuerza UTF-8. Primera sentencia de todo punto de entrada (lección de Windows del v1). |
| `colores.py` | Constantes de color y los emojis de los siete tipos. |
| `modelo.py` | Nueve dataclasses puras, cero lógica. Rompe los ciclos de importación. |
| `gitcmd.py` | Capa git propia: ejecución con **stderr real**, raíz del repo, commit con rutas explícitas, candado de fichero, escritura atómica. |
| `vocabulario.py` | **Los datos cerrados**: 7 tipos, campos con su lector declarado, keys marcadoras, lista negra, palabra ilegal, la pregunta del dolor en una sola copia, los ocho índices. |
| `zonas.py` | Carga del fichero de zonas, alias, candidatas por parecido, alta, y el interruptor de la aduana. |
| `formato.py` | Construir y parsear: titular, cuerpo, mensaje, línea de índice, línea de archivo. **Pareja productor↔consumidor: lo que se escribe se puede volver a leer.** |
| `parecidas.py` | Detector léxico dentro de la zona. Recibe datos; no lee ficheros. |
| `validador.py` | **La pieza única.** La única implementación de "esto es válido". |
| `rechazo.py` | Un texto, dos renderizados: terminal y bloqueo de hook. |
| `ids.py` | Contador por tipo leyendo el índice; detector de duplicados. |
| `indices.py` | Lectura y escritura de los ocho ficheros. Nadie más los toca. |
| `notas.py` | **La transacción**: validar → índice → commit de nota+índice juntos → si git falla, restaurar y propagar el error real. |
| `consulta.py` | Lectura desde el historial hacia objetos: por identificador, zona, palabra y fichero. |
| `racimos.py` | Agrupación determinista por punteros. Nunca por similitud ni por keys. |
| `informe.py` | Construye el estado de una zona: vallas arriba, racimos, preguntas al final. |
| `informe_render.py` | Convierte ese estado en texto, con la presentación heredada. Separado para no pasar de 500 líneas. |
| `salud.py` | Coherencia índices↔git, identificadores duplicados, planes con commits sin reflejar. |
| `arranque.py` | Compone el menú del día. Solo renderiza. |
| `contexto.py` | Lector y escritor del ⏩. |
| `reglas.py` | El fichero de reglas: alta y entrega completa. Sin zonas, sin índice, a propósito. |
| `reparto.py` | La tabla de qué ve cada oficio, y de dónde sale la zona del encargo. |

---

## 3. Las funciones que importan

### `validador.py` — la pieza compartida

| Función | Qué hace |
|---|---|
| `validar_nota` | Entrada única. Corre todo lo de abajo y devuelve la nota normalizada o los fallos. |
| `validar_titular` | Longitud, formato, idioma. |
| `validar_zonas` | Existencia, alias, lista negra, palabra ilegal, alta en dos pasos. |
| `validar_tipo` | El árbol: si no encaja limpio en ninguno de los siete, rechaza preguntando qué es. |
| `validar_campos` | Obligatorios por tipo; no permitidos para ese tipo; inexistentes. |
| `normalizar_keys` | Vocabulario controlado; cinco como máximo; ninguna que ya esté en el titular. |
| `validar_pregunta_dolor` | Exige la respuesta en memo y valla; y si la respuesta contradice al tipo, lo dice. |
| `validar_punteros` | Los identificadores citados existen; una valla sin origen lista todas las incidencias de la zona. |
| `validar_sustitucion` | Si hay parecidas y no se declara sustitución, rechaza con las candidatas dentro. |
| `validar_consolidacion` | Toda destilación exige fuentes. Por tipo de nota, no por autor. |
| `es_wip` | Identifica el commit exento de toda pregunta. |
| `Contexto` | Todo lo que el validador necesita saber del mundo, pasado por el llamante. **Ni abre ficheros ni llama a git.** |

### `notas.py` — la transacción

| Función | Qué hace |
|---|---|
| `escribir` | Candado → identificador → validar → índice → commit de nota+índice **en un solo commit** → si git falla, restaura el índice y devuelve el error real. |
| `sustituir` | Un commit con la nota nueva, su línea, la vieja retirada y su línea archivada. |
| `cerrar` | Un commit con la línea fuera del índice y dentro del archivo. |
| `descartar_alternativas` | Los descartes con su origen, en el mismo acto. |
| `escribir_trabajo` | Commit de trabajo con los ficheros tocados calculados del diff. |

### `reparto.py` — el mapa por oficio

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
                    utf8   colores   modelo
                      └───────┴────────┴──────────────┐
  vocabulario ──────┬──── formato ──────┬──── indices │   gitcmd
       │            │        │          │        │    │      │
       │        zonas        │          │        │    └──────┤
       └──► parecidas        │          │        │           │
                └──► ★ validador ◄──────┘        │           │
                          │  │                   │           │
                       rechazo│      ids ────────┤           │
                          │  └──► ● notas ◄──────┴───────────┘
                          │            │
                          │        consulta ──┬── racimos ── informe ── render
                          │            ├── salud                          │
                          │            ├── contexto                       │
                          │            ├── reparto ◄──────────────────────┘
                          │            └──────────► arranque
   ┌──────────────────────┴───────────────────────────────────────────────┐
▲ hooks/aduana.py     ● bin/nota.py  cerrar.py  contexto.py  trabajo.py
▲ hooks/inyeccion.py    bin/buscar.py  arrancar.py  regenerar-indices.py
                        bin/zonas.py  regla.py  banco.py
```

**El validador compartido, en concreto:**

- Hay **una sola** implementación de "esto es válido": `validador.py`.
- La importan **exactamente dos consumidores**: `notas.py` (y por su intermedio los cuatro scripts que escriben) y `hooks/aduana.py`.
- `rechazo.py` lo comparten los mismos dos: el generador imprime la versión de terminal, la aduana emite la de bloqueo. **Mismo texto, dos salidas.**
- `vocabulario.py` es datos, no validación. Lo leen también el formato, el render y el arranque, pero solo para presentar. **Nadie valida contra él sin pasar por el validador.**
- `zonas.py` y `parecidas.py` no los llaman los scripts: los llama el validador por dentro. Así no hay una segunda puerta.
- Consecuencia buscada: como el generador valida en proceso con la misma pieza, **la aduana casi nunca dispara**. Existe para lo que no pasa por el generador — un commit a mano, y los subagentes.

---

## 5. Auditoría: ningún campo sin lector

| Se escribe | Lo escribe | **Lo lee** |
|---|---|---|
| El porqué | `formato.construir_mensaje` | `informe_render.render` |
| Las keys | idem | `consulta.por_palabra` · `reparto.contenido_para` |
| La descripción | idem | `informe_render.render` |
| El origen | idem | `racimos.agrupar` |
| La sustitución | idem | `racimos.agrupar` · `notas.sustituir` |
| Los ficheros tocados | `notas.escribir_trabajo` | `informe_render.render_fichero` ⚠ **el más débil — ver §6** |
| Quién se espera | `formato.construir_mensaje` | `arranque.seccion_bloqueantes` |
| La issue | `notas.escribir_trabajo` | `salud.planes_sin_reflejar` |
| El contexto | `contexto.escribir` | `contexto.ultimo` → `arranque.seccion_next` |
| Los siete índices | `indices.insertar/retirar` | `ids.siguiente` · `indices.recuentos` · `informe.construir` · `salud.coherencia` |
| El archivo | `indices.archivar` | `indices.leer_archivo` → informe con historia |
| El fichero de zonas | `zonas.alta` | `zonas.cargar` → `validador.validar_zonas` |
| El fichero de reglas | `reglas.anadir` | `reglas.leer` → el comando |

**Un test recorre los campos declarados, importa la función lectora de cada uno y falla si no existe.** Así el principio deja de depender de que alguien se acuerde: es el paso 1.10 del plan.

---

## 6. Lo que hay que discutir antes de escribir una línea

1. **Los ficheros tocados siguen oliendo a zombi.** Su único lector posible es la vista por fichero, y esa vista ya se resuelve con `git log -- <ruta>` sin el campo. Dos salidas: aceptar esa vista como lector suficiente, o **retirar el campo del v2 entero**. En el v1 fueron 605 escrituras y cero lecturas. → **decisión 1 del plan.**
2. **El commit de trabajo no está en la especificación**, pero la especificación exige los ficheros tocados "escritos exclusivamente por el script" y la referencia a issue en commits de trabajo. O nace ese script, o esos commits siguen pasando por el wrapper del v1 para siempre.
3. **Cómo sabe la inyección la zona del encargo.** La especificación no lo dice. Propuesta: una línea en el encargo, con casado por palabras como respaldo y silencio si no decide. **Sin esto la fase 5 no arranca.**
4. **El hook del arranque.** "Solo dos hooks" choca con que el arranque es por definición un hook de inicio. Propuesta: un tercer fichero que es un lanzador puro sin lógica, sobre el que nunca se itera. → **decisión 4 del plan.**
5. **Los descartes producen varios commits en un acto.** Si se quiere literalmente un commit por acto, hay que meterlos dentro del commit de la decisión y renunciar a que cada uno tenga identificador propio. → **decisión 5 del plan.**
