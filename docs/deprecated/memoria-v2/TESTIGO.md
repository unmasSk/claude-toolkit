# El testigo — qué construyó el v1 que nadie llegó a usar

**Fecha:** 2026-08-02 · **Medido contra:** commit `ecdfaa5` · **Método:** las 76 funciones de los 11 ficheros de memoria, cada nombre buscado contra los 55 ficheros de producción del toolkit y los 67 de test, más `hooks.json` entero para saber qué es punto de entrada real.

Este documento no propone nada. **Solo mide.** Existe porque el v2 se escribe desde cero y la única cosa que el v1 puede aportar es la lista de errores que ya pagó.

**Un dato que enmarca todo lo demás: cero clases en once ficheros.** El v1 entero son funciones sueltas. Así que las dataclasses del v2 no tenían precedente contra el que contrastarse — hubo que derivarlas una a una desde las salidas de `TEXTOS.md`, sin apoyo del testigo. Salieron **trece**, no las nueve que la arquitectura daba por buenas sin haberlas listado.

---

## 1. La grasa: ~590 líneas que no hacían nada

| Pieza | Líneas | Qué pasó |
|---|---|---|
| `recall.py::recall_relevant` | **79** | Un motor de relevancia completo —suelo de puntuación, fracción superior— con **cero consumidores en todo el repo**. Ni uno. Solo lo tocaban 8 tests. |
| `bin/git-memory-gc.py` | **414** | El fichero entero, sus siete funciones, inalcanzable. Solo se llegaba por un alias de shell que nunca se instala. |
| `parsing.py::extract_commit_message` | 22 | La única de las 76 sin **ni un solo** llamador, ni siquiera desde un test. |
| `parsing.py::parse_trailers` | 24 | Solo tests. Y su propia documentación miente: dice *«Used by validation hooks»* y ningún hook la importa. |
| `parsing.py::parse_commit_type` | 30 | Solo tests. |
| `boot_memory.py` — el bloque de re-export final | ~21 | Un puente de compatibilidad para un caso de carga que **no existe en ningún sitio del repo**. |

**Lo que esto enseña, y es la razón de la puerta 2 de `PIEZAS.md`:** ninguna de estas piezas se escribió por descuido. Todas se escribieron con intención, y ninguna llegó a tener quien la llamara. `recall_relevant` son 79 líneas de motor pensado, escrito y probado con ocho tests — y nadie lo enchufó jamás. Ocho tests en verde no demuestran que algo se use.

---

## 2. Los parámetros y retornos que nadie pasa ni lee

| Dónde | Qué |
|---|---|
| `recall(_repo_dir=None)` y `recall_relevant(_repo_dir=None)` | Ningún llamador real lo pasa nunca. Es una costura para tests, y su propia documentación lo admite. |
| `recall(scope=None)` | Solo uno de los dos llamadores reales lo usa. El hook de inyección nunca lo pasa. |
| `git-memory-gc.py::create_gc_commit() -> bool` | Devuelve un booleano que su único llamador **nunca lee**, en ninguna de sus dos ramas. |
| `boot_memory.py::_crown_replace(tombstones=None)` | Dos de los seis sitios que la llaman nunca lo pasan — documentado como intencional. |

---

## 3. Los duplicados, y el que importa de verdad

**Parsear el historial de git hacia memoria estructurada está implementado TRES veces:**

| Implementación | Líneas |
|---|---|
| `boot_memory.py::extract_memory` | 260 |
| `recall.py::_scan_commits` | 145 |
| `precompact-snapshot.py::extract_memory_from_log` | 157 |

**562 líneas haciendo lo mismo**, cada una por su cuenta: la separación de registros, el troceo de la cabecera, la extracción de trailers, la segunda pasada para las lápidas. Los comentarios se citan entre sí como *«mirrored from»* — o sea que era consciente, no un accidente. Y se sincronizaban **a mano**: ya había pasado tres veces que aparecía un caso nuevo y había que arreglarlo en los tres sitios.

Los otros cuatro duplicados son menores pero de la misma familia: dos funciones copiadas byte a byte entre dos hooks, la misma expresión de tokenizado en dos sitios, y la misma función de saneado envuelta bajo tres nombres distintos en tres ficheros.

**Esto el plan ya lo tenía anticipado**, y conviene decirlo: la arquitectura del v2 pone **un solo lector** (`query.py`) y prohíbe que nadie más toque los índices (`indexes.py`, *«Nadie más los toca»*). El testigo no descubre el problema — confirma con números por qué esa decisión estaba bien tomada.

---

## 4. Lo que este documento NO dice

No dice qué hacer con nada de esto. El v1 se retira siguiendo el plan, no siguiendo esta medición.

Y no cubre `lib/encoding_guard.py` ni `lib/colors.py` del toolkit, que son los precedentes de las dos primeras piezas del v2: quedaron fuera del encargo por ser ficheros del toolkit que sobreviven, no del sistema de memoria. Los apartados *«qué del v1 no se trae»* de `PIEZAS.md` §5.1 y §5.2 siguen pendientes por eso, y se rellenarán con una medición propia — no a ojo.
