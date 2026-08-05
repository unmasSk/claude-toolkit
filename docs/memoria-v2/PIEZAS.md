# Piezas — el contrato de cada fichero, antes de escribir una línea

**Versión:** 0.1 · **Fecha:** 2026-08-02 · **Estado:** en redacción, capa 0

Los otros documentos dicen **qué** se construye (`spec`), **en qué orden** (`PLAN-CONSTRUCCION`), **qué requisito cae dónde** (`TRAZABILIDAD`), **qué escupe el sistema** (`TEXTOS`) y **cómo se llaman las piezas** (`ARQUITECTURA`). Ninguno dice **qué lleva dentro cada fichero**. Este sí.

Es el documento que el v1 nunca tuvo, y es exactamente por eso que el v1 acabó con 1.002 `Why:` escritos y cero leídos, cinco scripts inalcanzables durante meses y una función que tres parsers descartaban en silencio.

---

## 0. La regla, y es una sola

> **Nada entra sin que se sepa quién lo llama.**

Cada función de este documento declara su llamador. Cada clase declara quién la instancia. Cada campo declara quién lo lee. Una pieza sin consumidor declarado **no se escribe** — no se escribe "por si acaso", no se escribe "para más adelante", no se escribe "porque el v1 lo tenía".

El corolario es incómodo y se acepta: si al llegar a la capa de arriba resulta que hace falta algo que aquí no está, **se vuelve a este documento y se declara antes de escribirlo**. Nunca al revés.

### 0.1 Cada afirmación lleva su fuente

Este documento no admite «asumí», «pensaba que» ni «no lo revisé». Toda afirmación va etiquetada, y la etiqueta dice de dónde sale:

| Etiqueta | Significa |
|---|---|
| `[TEXTOS §x]` `[spec §y]` `[plan §z]` | Citado de un documento. Se puede ir a leerlo. |
| `[medido]` | Verificado ejecutando algo o leyendo el código. Se dice qué se ejecutó. |
| `[pregunta]` | No hay fuente. **Se le pregunta al propietario.** No se resuelve por criterio propio. |

Una entrada con una `[pregunta]` dentro no está terminada y **su pieza no se construye**.

### 0.2 Un hueco puede ser deliberado — no se rellena, se pregunta

Regla dictada por el propietario y anterior a cualquier criterio de diseño:

> Los documentos los escribió alguien que lleva meses usando el sistema viejo. **Un hueco puede estar ahí a propósito** — porque decidió que esa parte no se automatiza, o porque sabe que Claude la resuelve solo sin necesidad de mecanismo.

Por eso está prohibido rellenar un hueco por iniciativa propia, y da igual lo evidente que parezca. Ver un hueco y pensar «esto falta por descuido» es exactamente el error que puede romper el sistema: se está construyendo maquinaria donde el diseño pedía que no la hubiera.

**Qué se hace en su lugar:** se anota como `[pregunta]`, se le cuenta al propietario en lenguaje llano y **con un ejemplo concreto** de qué pasaría en cada salida, y se espera. Un hueco pequeño también se pregunta; el tamaño no autoriza a decidirlo.

---

## 1. De dónde se deriva cada función: hacia atrás, desde la salida

No se inventa la lista de funciones y luego se mira a ver qué producen. Se hace al contrario, y es lo que distingue este intento del anterior.

**Las salidas ya están escritas, literales, en `TEXTOS.md`:** los diez rechazos de la aduana, el informe de zona en tres formas, el arranque en dos, los ocho formatos de línea de índice, y las siete plantillas de commit. Eso es el contrato de salida, palabra por palabra.

El método, por pieza:

1. Se coge una salida literal de `TEXTOS.md`.
2. Se pregunta qué hace falta para producir **exactamente** esos bytes.
3. Eso, y solo eso, entra en el contrato.
4. Lo que no sea alcanzable hacia atrás desde alguna salida, **no existe**.

Un ejemplo que ya cambió una decisión: el rechazo 1.6 («esto pisa a algo ya escrito») imprime las notas candidatas **con su `Why:` completo y sus keys**. De ahí sale que el detector de parecidas no puede devolver identificadores sueltos: tiene que devolver notas enteras. Eso no se dedujo de un diagrama, se dedujo del texto que hay que imprimir.

---

## 2. Las tres puertas contra el código muerto

No son promesas. Son mecanismos, y cada uno se pone rojo solo.

**Puerta 1 — test-first.** Toda función nace porque un test la pidió primero. Dante escribe el contrato en rojo desde las salidas literales; Ultron implementa hasta verde. Lo que ningún test pide, nadie lo escribe. Es la única defensa que no depende de que alguien se acuerde.

**Puerta 2 — el llamador declarado.** Este documento declara, por función, quién la llama. Un test recorre las declaraciones y falla si una función declarada no tiene llamador, o si el llamador declarado no la importa de verdad. Es la misma forma que el paso 1.10 del plan («un campo sin lector no existe»), aplicada al código en vez de a los campos.

**Puerta 3 — la frontera.** Un test recorre el grafo de imports real y se pone rojo con tres cosas:

- Algo de fuera de `lib/memory/` que importa de dentro.
- Algo de dentro que importa del toolkit fuera de una lista corta y declarada.
- Un módulo o una función exportada que nadie importa.

La tercera es la que mata la grasa el día que nace. Las dos primeras son las que impiden que se repita el enredo del v1: catorce ficheros donde memoria y toolkit convivían dentro del mismo fichero, sin costura posible.

**Por qué la frontera importa más de lo que parece:** es también la garantía de reversibilidad. Con la frontera verde, el v2 entero se borra con un solo comando y el toolkit no se entera. Sin ella, en seis meses volvemos a tener catorce ficheros que partir.

---

## 3. Lo que ya existe en esta rama, y qué se hace con ello

Este documento nace **después** de que se hiciera trabajo en la rama. Para que nadie lo dé por bueno sin mirarlo, aquí está el estado real y su veredicto.

### 3.1 El v1, retirado

| Qué | Estado |
|---|---|
| 3 hooks, 5 scripts de `bin/`, 3 módulos de `lib/`, la skill entera | **borrados** |
| 14 ficheros partidos (memoria fuera, toolkit dentro) | **operados**, sin verificación individual |
| `bin/git-memory` (el alias bash que nunca se instalaba) | borrado — con él caen los cinco scripts que solo él alcanzaba |
| Tests del v1 | 8 ficheros retirados en tres tandas; **7 quedan, todos mixtos** |
| `agents/gitto.md` | **retirado y conservado**: movido a `unmassk-toolkit/deprecated/`, fuera de `agents/` para que el harness no lo registre. La tripulación queda en nueve. Decisión del propietario, 2026-08-02 |

**Los 7 tests mixtos que quedan** son el residuo del enredo, no descuido: cada uno prueba a la vez maquinaria del v1 y código del toolkit que sobrevive. No se operan por dentro — se decidirán con el criterio de este documento: *sobrevive el test cuyo código siga corriendo el día que el v2 esté acabado*.

### 3.2 El v2, la fase 0

Existen 314 líneas escritas antes de que existiera este contrato:

| Fichero | Líneas | Veredicto |
|---|---|---|
| `lib/memory/utf8.py` | 49 | `[medido]` **CUMPLE — se quedó tal cual.** Ver §5.1. Sus 3 tests, en verde |
| `lib/memory/colors.py` | 36 | `[hecho]` **Reescrito como `emojis.py`** — tres mapeos, cero funciones, cero color. Sus 3 tests, en verde. El fichero viejo, borrado |
| `bin/gitmem` | 64 | se re-deriva en la capa de scripts |
| `tests/memory/conftest.py` | 127 | esqueleto con `NotImplementedError` a propósito; se rehace test-first |
| `tests/memory/test_conftest_smoke.py` | 38 | ídem |
| `tests/memory/__init__.py` | 0 | **se queda, y es necesario** — ver 3.3 |

Ninguno de estos ficheros tiene derecho adquirido. Se escribieron antes de la regla del §0, así que se miden contra su contrato como todo lo demás. Que ya estén escritos no es un argumento.

### 3.3bis Cómo se importan los módulos entre sí — convención fijada

`[decisión del contrato, 2026-08-02, tras un bloqueo real]` **`lib/memory/` entra en el camino de búsqueda y los módulos se importan planos entre sí**: `from model import Note`, nunca `from .model import Note` ni `from memory.model import Note`.

**Por qué, y no es gusto:** `tests/memory/` es un paquete (lo exige la trampa del §3.3) y `lib/memory/` se llama igual. Importar el segundo como paquete choca con el primero. Y cargarlo por ruta de fichero —que es como los tests lo hacen— **deja el módulo sin contexto de paquete**, así que un `from .model import ...` revienta con *«attempted relative import with no known parent package»* en vez de con el fallo real.

Se detectó antes de escribir una sola implementación, probándolo en vivo: bloqueaba el verde de los cuatro módulos de la capa 1 a la vez, porque **todos** importan los moldes de datos.

**Es además la convención que el toolkit ya usa**: sus módulos viven en `lib/` con esa carpeta en el camino de búsqueda y se importan planos (`from parsing import ...`). El v2 hace lo mismo un nivel más abajo. Cero mecanismo nuevo.

**Consecuencia para quien escriba tests:** el cargador del conftest tiene que meter `lib/memory/` en el camino de búsqueda **antes** de cargar el módulo, o los imports entre hermanos no resuelven.

### 3.3 Una trampa ya pagada, para que no se vuelva a pagar

`tests/memory/__init__.py` existe y **debe existir**. Sin él, Python registra `tests/conftest.py` y `tests/memory/conftest.py` con el mismo nombre de módulo (`conftest` a secas) y el segundo le roba el sitio al primero: medido en vivo, la suite pasó de 9 errores a 55 y de 768 tests colectados a 77.

Consecuencia que hereda todo test del v2: **dentro de `tests/memory/` los imports del conftest son relativos** (`from .conftest import ...`), nunca a pelo. Un import a pelo ahí resuelve al conftest del v1 y falla de una forma que no se parece en nada a su causa.

Es exactamente el tipo de fallo que este proyecto declara como su única amenaza: el sistema rompiéndose a sí mismo, en silencio, por un detalle que no se deduce leyendo el código.

---

## 4. Cómo se lee una entrada

Cada pieza tiene siempre las mismas siete secciones. Si a una le falta alguna, la entrada no está terminada.

| Sección | Qué contiene |
|---|---|
| **Para qué** | Una línea. Si no cabe en una línea, la pieza hace dos cosas y hay que partirla. |
| **De qué salida se deriva** | El texto literal de `TEXTOS.md`, o la línea de la especificación, que obliga a que esta pieza exista. Sin esto, la pieza no entra. |
| **Superficie** | Cada función y clase pública con su firma exacta: qué recibe, qué devuelve, **qué lanza cuando falla**. |
| **Qué NO hace** | Su frontera. Qué le toca al vecino. Es lo que evita que dos módulos acaben haciendo lo mismo. |
| **Quién la llama** | Por función. Sin llamador, no entra (puerta 2). |
| **Sus tests** | Qué prueba cada uno **y contra qué fallo real**. Un test que no nombra el fallo que previene, sobra. |
| **Qué del v1 NO se trae** | Con el dato medido delante. Es el valor del testigo. |

---

## 5. CAPA 0 — lo que no depende de nada

Tres piezas. No importan nada del sistema, así que se pueden escribir y probar sin que exista nada más.

---

### 5.1 `lib/memory/utf8.py`

**Para qué.** Garantizar que la salida con emojis no revienta en ninguna consola.

**De qué salida se deriva.** De todas. No hay ni un texto en `TEXTOS.md` sin caracteres fuera de ASCII: los siete emojis de tipo (`🧭 📌 ⚠️ ❓ 🚫 🔥 ⛔`), los de canal (`🚧` del wip, `🧠` de la regla, y el corchete literal `[NEXT]` que reutiliza `🧭`), el `✅` del aviso de key corregida, el `›` que marca la línea que casó, y las cajas (`═ ─ ├ └ ║ ╔ ╝`).

**Y el fallo concreto que previene, que no es cosmético:** la aduana emite su rechazo desde un hook. Si el flujo de salida no sabe codificar `⛔`, el hook no imprime un texto feo — **revienta**. Y un hook que revienta al bloquear un commit deja al usuario con un volcado de pila en vez de con la pregunta que tenía que contestar. La salida legible ES la función de la aduana; si se pierde, la aduana no sirve para nada.

**Superficie.**

```python
def force_utf8_streams() -> None
```

`[medido — leído en unmassk-toolkit/lib/memory/utf8.py, 49 líneas]` Reconfigura `stdout` y `stderr` a UTF-8 con `errors="replace"`. Idempotente. **No lanza nunca**: captura `AttributeError`, `ValueError`, `OSError` y `TypeError` y deja el flujo como estaba, porque *«el guard no se convierte en el crash que existe para evitar»* — el fichero ya lo declara como contrato de fallo abierto y lo argumenta caso por caso.

**Veredicto sobre el fichero que ya existe: cumple el contrato y se queda.** Es la única pieza de la fase 0 que sobrevive tal cual, y la razón está a la vista: nació con su contrato de fallo escrito, no con una implementación a ver qué sale. Es el listón del resto.

**Qué NO hace.** No sabe qué emojis existen (eso es `emojis.py`). No imprime.

**Quién la llama.** Primera sentencia de **todos** los puntos de entrada: los 10 scripts de `bin/memory/` (incluido `boot.py`, que sigue existiendo aunque ya no sea subcomando de `gitmem` — §10), los 2 hooks, y `bin/gitmem`. Trece llamadores `[medido tras retirar `hooks/inject.py` — decisión del propietario, 2026-08-03, B20; eran catorce]`. Ninguno más — un módulo de librería nunca la llama, porque quien manda sobre el flujo de salida es el proceso, no la librería.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Los 11 emojis y los 7 caracteres de caja se escriben en un flujo forzado a `cp1252` y vuelven byte a byte | El rechazo de la aduana revienta en una consola Windows y el usuario ve un volcado en vez de su pregunta |
| Llamarla dos veces no cambia el estado ni lanza | Dos puntos de entrada encadenados (un script llamado desde `gitmem`) se rompen entre sí |
| Con un `stdout` sin `reconfigure`, no lanza y el programa sigue | Un `gitmem` con la salida redirigida a una tubería deja de arrancar |

**Qué del v1 NO se trae.** *(pendiente del inventario del testigo — `lib/encoding_guard.py`)*

---

### 5.2 `lib/memory/emojis.py` (hoy se llama `colors.py`)

**Para qué.** El emoji de cada tipo, en un solo sitio.

**De qué salida se deriva.** De dos, y **solo dos** — esto es un hallazgo, no un detalle:

- El titular del commit: `[D-030][product][auth] 🧭 login with JWT + Google OAuth` (`TEXTOS` §5).
- La línea del archivo: `2026-06-02  [D-036][product][auth] 🧭 ...  →  replaced by D-041` (`TEXTOS` §4).

**El emoji va DESPUÉS de los corchetes** `[corrección del propietario, 2026-08-02 — TEXTOS §6.8]`. Esta sección lo tenía delante: era un resto de antes de la corrección, y es el tipo exacto de desfase que rompe el sistema en silencio — quien escribe pondría el emoji en un sitio y quien lee lo buscaría en otro.

**Y de dónde NO se deriva, que es lo que recorta la pieza:** `TEXTOS` §4 lo dice literal — *«la línea de índice es el titular literal, sin emoji»*, y *«el emoji solo aparece en el archivo, que es el único fichero que mezcla tipos»*. Los siete índices vigentes no llevan emoji. Así que el mapa de emojis tiene exactamente dos consumidores, no ocho.

**El informe y el arranque** usan emojis también (`⚠️ RESTRICTIONS`, `🔥 INCIDENTS` — etiquetas en inglés `[decisión del propietario, 2026-08-03]`), pero como **cabecera de sección**, no como emoji de una nota. Son dos usos distintos y por eso son dos constantes distintas.

**Superficie.**

```python
TYPE_EMOJI: Mapping[str, str]      # "D"→🧭  "M"→📌  "R"→⚠️  "Q"→❓  "X"→🚫  "I"→🔥  "B"→⛔
CHANNEL_EMOJI: Mapping[str, str]   # "next"→🧭 (con corchete [NEXT] delante)  ·  "rule"→🧠  ·  "wip"→🚧
SECTION_EMOJI: Mapping[str, str]   # cabeceras del informe y del arranque
```

Tres mapeos inmutables. **Cero funciones**: es datos, no lógica. Si en algún momento necesita una función, es señal de que la lógica se está colando en la capa de datos.

**El fichero que ya existe no cumple, y sus tres fallos son la demostración de para qué sirve este documento.** `[medido — leído en unmassk-toolkit/lib/memory/colors.py, 36 líneas]`

**Fallo 1 — siete constantes que nadie llama, ya escritas.** El fichero declara `RESET`, `BOLD`, `RED`, `GREEN`, `YELLOW`, `BLUE` y `CYAN`. Ningún consumidor derivado de ninguna salida las usa. Es código muerto nacido muerto, en el segundo fichero del proyecto, escrito el mismo día que se declaró que no habría código muerto. No es un descuido de quien lo escribió: es lo que pasa cuando se escribe un fichero sin contrato delante.

**RESUELTO por el propietario el 2026-08-02: no hay color en ninguna salida.** `[decisión del propietario]`

Su razón, y es la que gobierna toda la capa de presentación: **quien lee esto es Claude, no una persona.** Un código ANSI para Claude no aporta absolutamente nada — es ruido dentro del texto. El emoji sí, porque viaja **dentro** del texto y sobrevive a cualquier canal: al bloque del hook, al mensaje del commit, al fichero de índice y a la terminal, sin depender de que algo lo interprete.

**Consecuencias, las tres:** las siete constantes ANSI no se escriben; no hay `supports_color()` ni nada que dependa de `isatty`; y **el módulo pasa a llamarse `emojis.py`**, porque un módulo llamado `colors` sin un solo color es una mentira en el nombre — exactamente el defecto que ya tenían tres ficheros del v1, cuyo nombre no decía lo que hacían.

**Fallo 2 — un mapeo que mezcla dos cosas.** `EMOJIS` mete en el mismo diccionario los siete tipos de nota **y** `CONTEXT` y `WIP`, que no son tipos: son canales exentos, sin identificador, sin zonas y sin línea de índice `[spec §9]`. Un consumidor que recorra «los siete tipos» sobre ese diccionario recibe nueve. Es el fallo silencioso de manual, y de hecho **hace fallar el propio test de esta pieza** («los siete tipos tienen emoji y no hay ninguno de más»). Por eso el contrato son tres mapeos y no uno.

**Fallo 3 — le faltan símbolos que las salidas exigen.** `[TEXTOS §emojis]` declara `🧠` para las reglas y el fichero no lo tiene. `[TEXTOS §1.8]` usa `✅` en el aviso de key corregida, y tampoco está. Las cabeceras de sección del informe y del arranque, tampoco.

**Conclusión: se reescribe.** No se parchea — un fichero de 36 líneas con tres fallos estructurales cuesta menos volver a escribirlo desde su contrato que remendarlo, y remendarlo dejaría la duda de qué más quedó dentro.

**Qué NO hace.** No formatea. No sabe qué es una nota. No conoce los índices. Nadie valida contra él.

**Quién lo lee.** `format.build_subject` (el emoji del titular) · `indexes.archive` (el de la línea de archivo) · `format.build_context_message` (el `[NEXT]`) · `report_render` y `boot` (las cabeceras de sección).

**Los tres canales ya tienen productor real — actualizado 2026-08-03, verificado en el código.** Esta sección llevaba tiempo describiendo dos de los tres como huecos pendientes; dejaron de serlo:

- **`"next"→🧭`.** El titular pasa de llevar `⏩` suelto a llevar el corchete literal `[NEXT]` seguido del emoji (`[NEXT] 🧭 <titular>`) `[decisión del propietario, 2026-08-03]`. Productor real: `context.write` vía `bin/memory/next.py` (§9.6).
- **`"rule"→🧠`.** **Ya no está pendiente.** Productor real: `rules.add()` (§9.7, capa 4), en producción — importa `CHANNEL_EMOJI` y lo usa en cada alta. Esta sección decía antes que el escritor «aún no existe»; dejó de ser cierto y quedó sin corregir durante un tiempo — exactamente el mecanismo que mató a `Sources:` en el v1: un dato descrito en presente que ya no lo era, y nadie volvió a mirar.
- **`"wip"→🚧`.** **Tampoco está pendiente, desde 2026-08-03** `[decisión del propietario, tras verificar un agujero real: `validator.is_wip()` sabía reconocer y eximir el marcador, pero ningún comando lo escribía]`. Esta sección decía «el 🚧 NO lo escribe este sistema» — era cierto hasta esa fecha. Productor real: `bin/memory/wip.py` (§10), que antepone el marcador al mensaje antes de llamar a `notes.write_work()`.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Los siete tipos del vocabulario tienen emoji, y no hay ninguno de más | Se añade un tipo y su commit sale sin emoji, o queda un emoji de un tipo que ya no existe |
| Los mapeos son inmutables | Un módulo los muta en caliente y otro lee algo distinto en el mismo proceso |
| Ningún emoji se repite entre tipos | Dos tipos indistinguibles de un vistazo en el archivo, que es el único fichero que los mezcla |

**Qué del v1 NO se trae.** *(pendiente del inventario del testigo — `lib/colors.py` del toolkit)*

---

### 5.3 `lib/memory/model.py`

**Para qué.** Declarar una sola vez qué forma tiene cada cosa que el sistema mueve.

**De qué salida se deriva.** De todas, y por eso se deriva una a una. Una misma decisión existe en tres formas a la vez: el commit entero con sus campos `[TEXTOS §5]`, la línea de una sola fila del índice `[TEXTOS §4]`, y el racimo del informe con sus descartes colgando `[TEXTOS §2.1]`. Cada forma distinta es una clase; una forma que no aparece en ninguna salida no es una clase.

**El fallo concreto que previene** `[medido — TESTIGO §3]`: en el v1, tres ficheros tenían cada uno su propia idea de qué era una entrada de memoria, 562 líneas reimplementando lo mismo y sincronizadas a mano. Ya había pasado tres veces que aparecía un caso nuevo y había que arreglarlo en los tres sitios.

**Cuántas clases hay: catorce, no trece** `[corregido 2026-08-04 — este documento decía «trece, no nueve» y volvió a quedarse corto: el mismo defecto que dice haber arreglado se repitió]`. `ARQUITECTURA.md` decía nueve sin haberlas derivado — era un número, no una lista. Derivadas desde las salidas salían trece: once en la tabla de abajo, más `WordChunk` (apareció al escribir la firma de `WordReport`) y `WriteResult` (la usaban seis firmas sin estar declarada — lo cazó la revisión). **Faltaba una: `NoteReport`**, el informe de una nota por su identificador `[TEXTOS.md §2.4]`, añadida al código el 2026-08-03 para cerrar `DEUDA.md` #24 y nunca propagada a esta tabla. Verificado: `grep -c "^class " lib/memory/model.py` → 14. Aquí está de qué salida sale cada una.

| Clase | Sale de | Por qué no es otra |
|---|---|---|
| `Note` | Las siete plantillas de commit `[TEXTOS §5]` | — |
| `ContextNote` | El commit `[NEXT]` `[TEXTOS §5]` | Sin identificador, sin zonas, sin línea de índice `[spec §9]`. Meterla en `Note` obligaría a que zonas e identificador fueran opcionales, y un campo que para un tipo nunca se rellena es por donde el v1 se llenó de campos sin lector |
| `Zone` | El rechazo de zona inexistente `[TEXTOS §1.1]`, que imprime nombre, recuento y descripción | — |
| `IndexLine` | La línea de los siete índices vigentes `[TEXTOS §4]` | No lleva fecha ni emoji: es una forma más corta, no una `Note` recortada |
| `ArchiveLine` | La línea del archivo `[TEXTOS §4]` | Lleva fecha, emoji y destino — tres campos que la línea de índice no tiene |
| `Rejection` | Los diez rechazos `[TEXTOS §1]` | — |
| `Cluster` | El racimo del informe `[TEXTOS §2.1]` | — |
| `NoteReport` `[añadida a esta tabla 2026-08-04 — ya estaba en el código desde el 2026-08-03]` | El informe de una nota por su identificador `[TEXTOS §2.4]` | Cierra `DEUDA.md` #24: una nota sola, con su estado (vigente/archivada) y lo que cuelga de ella si es una decisión, sin tener que abrir el informe de toda la zona |
| `ZoneReport` | El informe de una zona `[TEXTOS §2.1]`, y el de zona vacía `[TEXTOS §2.2]`, que es el mismo con todo a cero | — |
| `WordReport` | La búsqueda por palabra `[TEXTOS §2.3]` | **Esta es la que faltaba en el conteo de nueve.** Atraviesa varias zonas, lleva la palabra buscada, y marca con `›` qué línea concreta casó — tres cosas que un informe de zona no tiene |
| `BootSummary` | El menú del día `[TEXTOS §3.1]` y `[TEXTOS §3.2]` | — |
| `HealthReport` | El bloque `AVISOS` del arranque `[TEXTOS §3.1]` | — |

**Superficie.** Catorce dataclasses congeladas (`frozen=True`) `[corregido 2026-08-04, decía trece — faltaba `NoteReport`]`, **cero funciones, cero métodos**. Si a alguna le hace falta un método, es que la lógica se está colando en la capa de datos y va al módulo que corresponda.

```python
@dataclass(frozen=True)
class Note:
    type: str                      # una de: D M R Q X I B
    id: str                        # "D-030"
    zone1: str
    zone2: str
    headline: str                  # inglés, ≤80 caracteres
    description: str               # obligatorio en los siete tipos
    timestamp: datetime            # UTC, del autor del commit
    why: str | None = None         # obligatorio en D
    keys: tuple[str, ...] = ()     # hasta 5
    origin: tuple[str, ...] = ()   # punteros "de qué nazco"
    replaces: str | None = None
    awaits: str | None = None      # solo en B
    issue: int | None = None       # solo en el acta de plan
```

**Resuelto: una sola `Note` con esos tres campos opcionales.** `[el propietario delega el cómo, 2026-08-02]` Siete clases casi idénticas obligarían a cada consumidor a ramificar por tipo antes de leer un titular, y son siete sitios donde una se queda atrás. **Qué campo es obligatorio en qué tipo no es forma, es regla** — y su sitio es `validator.validate_fields`, que ya existe en la arquitectura y es la única pieza que valida. La diferencia con `ContextNote` se sostiene: ahí los campos estarían vacíos *siempre*, y un campo que nunca se rellena no es opcional, es mentira.

```python
@dataclass(frozen=True)
class ContextNote:                 # el [NEXT] del cierre de sesión
    headline: str
    context: str                   # resumen en prosa corrida, no una lista de puntos
    keys: tuple[str, ...]
    timestamp: datetime
```

`context_points: tuple[str, ...]` **era el molde equivocado, corregido aquí** `[decisión del propietario, 2026-08-03, TEXTOS §5]`: el cuerpo del cierre de sesión no es una lista de puntos — es un campo `Context:` único en **prosa corrida**, con el resumen de toda la sesión («lo que se habló, lo que se decidió, lo que se rompió, lo que quedó a medias, y los cabreos con su motivo»). Con una tupla de puntos no se puede escribir ni releer ese resumen tal cual el propietario lo dictó; de ahí que el cambio no sea de redacción, sino del molde que usan quien escribe (`context.write`), quien lee (`context.latest`) y la prueba de ida y vuelta de `format.build_context_message`/`parse_context_message`. **Y el titular del commit cambia con él**: pasa de llevar el emoji `⏩` suelto delante a llevar el corchete literal `[NEXT]` seguido del emoji `🧭` (`[NEXT] 🧭 <titular>`) — mismo glifo que `TYPE_EMOJI["D"]`, reutilizado a propósito.

```python
@dataclass(frozen=True)
class Zone:                        # una entrada de zones.json
    name: str
    description: str               # la línea que imprime el rechazo de zona
    aliases: tuple[str, ...]
    # el recuento de notas NO es campo: lo calcula quien lo imprime, leyendo el índice

@dataclass(frozen=True)
class IndexLine:                   # una línea de los siete índices vigentes
    id: str
    zone1: str
    zone2: str
    headline: str
    # sin fecha y sin emoji, a propósito [TEXTOS §6.6]

@dataclass(frozen=True)
class ArchiveLine:                 # una línea de ARCHIVED.md
    date: date
    type: str
    id: str
    zone1: str
    zone2: str
    headline: str
    destination: str               # "replaced" | "closed" | "promoted"
    destination_detail: str        # el ID nuevo, o el motivo del cierre

@dataclass(frozen=True)
class Rejection:                   # lo que produce la aduana al rechazar
    title: str                     # "la zona «facturacion» no existe"
    body: str
    relaunch: tuple[str, ...]      # los comandos exactos, aparte del cuerpo
    # separados para que el test "lleva el comando de relanzamiento" sea
    # mecánico y no una búsqueda de texto dentro del cuerpo

@dataclass(frozen=True)
class Cluster:                     # una decisión con lo que cuelga de ella
    root: Note
    children: tuple[Note, ...]     # por punteros Origin/Replaces, nunca por parecido
    archived_ids: frozenset[str]   # cuáles de los hijos están ya archivados
    # el estado de cada hijo (descartada/vigente/archivada) se deriva de su
    # tipo y de este conjunto: no es un campo suyo

# añadida a esta ficha 2026-08-04 -- ya estaba en el código desde el
# 2026-08-03, cierra DEUDA.md #24
@dataclass(frozen=True)
class NoteReport:                  # el informe de una nota por su id [TEXTOS §2.4]
    note: Note
    generated_at: datetime
    archived: bool                 # vigente/archivada -- cabecera, regla 1
    cluster: Cluster | None        # lo que cuelga de ella; None si no cuelga nada

@dataclass(frozen=True)
class ZoneReport:
    zone: Zone
    generated_at: datetime
    live_count: int
    archived_count: int
    restrictions: tuple[Note, ...]
    blockers: tuple[Note, ...]
    decisions: tuple[Cluster, ...]
    memos: tuple[Note, ...]
    incidents: tuple[Note, ...]
    questions: tuple[Note, ...]

@dataclass(frozen=True)
class WordChunk:                   # un trozo de la búsqueda por palabra: una pareja de zonas
    zone1: str
    zone2: str
    notes: tuple[Note, ...]
    matched_ids: frozenset[str]    # cuáles llevan el marcador ›

@dataclass(frozen=True)
class WordReport:
    word: str
    generated_at: datetime
    zone_count: int
    live_count: int
    chunks: tuple[WordChunk, ...]
    # NO reutiliza ZoneReport: sus recuentos son "notas que casaron", no
    # "notas de la zona". Mismo nombre, otro significado = trampa

@dataclass(frozen=True)
class WriteResult:                 # lo que devuelve toda escritura
    ok: bool
    note_id: str | None            # el identificador asignado, si la hubo
    rejections: tuple[Rejection, ...]   # vacío si salió bien
    git_error: str | None          # el mensaje REAL de git, entero, si falló

@dataclass(frozen=True)
class HealthReport:
    duplicate_ids: tuple[str, ...]
    index_lines: int               # los números de "indexes match git
    git_notes: int                 #   (68 lines / 68 notes)" — caso sin archivadas
    plans_unreflected: tuple[tuple[int, int], ...]   # (issue, commits sin reflejar)
    # cuántas de las `git_notes` de arriba están archivadas — sin este dato
    # no se puede desglosar "587 live + 25 archived / 612 notes"; con 0,
    # quien imprime usa la forma corta de arriba [decisión del propietario,
    # 2026-08-03, TEXTOS §3, "el aviso de coherencia, con notas archivadas"]
    archived_notes: int = 0

@dataclass(frozen=True)
class BootSummary:
    project: str
    generated_at: datetime
    context: ContextNote | None    # None el primer día: el arranque lo dice en alto
    blockers: tuple[Note, ...]
    restrictions: tuple[Note, ...]     # todas, sin tope [spec §8.3]
    open_questions: int
    open_issues: int
    open_incidents: int
    health: HealthReport
```

**Son catorce, no doce** `[corregido 2026-08-04 — esta frase decía «doce, no once» y ya iba por detrás del código antes de esta corrección: `WriteResult` había subido el bloque a trece sin que esta línea se actualizara, y luego `NoteReport` lo subió a catorce]`. `WordChunk` apareció al escribir la firma de `WordReport`: el informe por palabra se parte en trozos por pareja de zonas, y cada trozo lleva su propio conjunto de líneas que casaron. Intentar reutilizar `ZoneReport` para eso habría metido una trampa — sus recuentos significan «notas de la zona» y aquí significan «notas que casaron». `NoteReport` es la última en sumarse — ver la tabla y el «Cuántas clases hay» de arriba.

**Qué NO hace.** No valida (eso es `validator`). No formatea (eso es `format` y `report_render`). No lee ni escribe nada. Cero funciones y cero métodos: si a una clase le hace falta un método, la lógica se está colando en la capa de datos.

**Quién las usa.** Todas las capas de arriba. Es el único módulo que puede importar todo el sistema sin crear un ciclo, precisamente porque no importa nada él.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Las catorce son inmutables: intentar cambiar un campo lanza `[corregido 2026-08-04, decía «trece»]` | Un módulo muta una nota en caliente y otro lee algo distinto en el mismo proceso — el fallo que no revienta, solo da un dato mal |
| `model.py` no importa ningún otro módulo del sistema | Un ciclo de importación que aparece tres capas más arriba y obliga a rehacer el grafo |
| Ninguna clase declara un método | La lógica colándose en la capa de datos, que es como el v1 acabó con tres ideas distintas de qué era una entrada |

**Qué del v1 NO se trae.** `[medido — TESTIGO]` **Cero clases en once ficheros**: el v1 entero eran funciones sueltas pasándose diccionarios. De ahí que tres ficheros tuvieran cada uno su propia idea de qué campos tenía una entrada, y que sincronizarlos fuera trabajo manual que ya falló tres veces.

---

## 6. CAPA 1 — los datos cerrados y el formato

Cinco piezas. Solo importan de la capa 0.

---

### 6.1 `lib/memory/vocabulary.py`

**Para qué.** Los datos cerrados del sistema, en una sola copia.

**De qué salida se deriva.** Los rechazos citan estos datos **literalmente**, y esa es la razón de que vivan en un solo sitio:

- El árbol de los siete tipos, con su letra y su descripción de una línea `[TEXTOS §1.4]`.
- La pregunta del dolor, palabra por palabra: *«¿puede costar datos, horas o producción caída?»* `[TEXTOS §1.5]`.
- Las cuatro keys marcadoras con sus variantes: `antipattern (anti-pattern, antipatron, antipatrón)`, `security (seguridad, sec)`, `performance (perf, rendimiento)`, `legal (legales, compliance)` `[TEXTOS §1.8]`.
- La lista negra de zonas y su mensaje `[TEXTOS §1.2]`.
- La palabra ilegal `audit` y sus dos salidas `[TEXTOS §1.3]`.

**El fallo que previene:** en el v1, `Sources:` era obligatorio según la definición de un agente y no existía en la lista de claves que leían los parsers, así que **los tres parsers lo descartaban en silencio** — 25 commits escribieron un campo que nadie llegó a leer nunca `[medido — TESTIGO]`. La lista de lo válido tiene que ser la misma pieza que valida, o hay dos verdades el primer día.

**Superficie.** Solo datos. **Cero funciones.**

```python
HEADLINE_MAX = 80          # el resumen, no la línea entera [spec §3.1]
MAX_KEYS = 5

TYPES: Mapping[str, _TypeSpec]        # las 7 letras → descripción, campos obligatorios, campos permitidos
FIELDS: Mapping[str, _FieldSpec]      # cada campo → su LECTOR declarado (ruta de la función que lo lee)
MARKER_KEYS: Mapping[str, str]       # cada variante → su forma canónica
ZONE_BLACKLIST: frozenset[str]       # claude, user, session, project, workflow
ILLEGAL_WORDS: Mapping[str, tuple]   # "audit" → sus dos resoluciones
PAIN_QUESTION: str                   # la pregunta literal, UNA sola copia en todo el sistema
INDEX_FILES: tuple[str, ...]         # los ocho, y solo ocho [spec §7]
```

**Los nombres exactos, fijados aquí para que nadie los adivine** (los tests ya se escribieron contra ellos). **`FieldSpec` y `TypeSpec` pasaron a `_FieldSpec`/`_TypeSpec` — internas desde 2026-08-04** `[corregido 2026-08-04 — este documento las declaraba públicas]`: son los moldes con los que se arman `FIELDS` y `TYPES`, no el dato en sí. Lo público de este fichero sigue siendo `FIELDS`/`TYPES`, que cualquier módulo importa y lee; las dos clases no tienen consumidor fuera de `vocabulary.py` — comprobado por `grep`, cero ficheros las nombran salvo los tests que las tocan a través de `FIELDS`/`TYPES` ya construidos:

```python
@dataclass(frozen=True)
class _FieldSpec:
    reader: str            # "modulo.funcion", el módulo relativo a lib/memory/

@dataclass(frozen=True)
class _TypeSpec:
    description: str       # la línea que sale en el rechazo «no sé qué tipo es esto»
    required_fields: frozenset[str]
    allowed_fields: frozenset[str]
```

**`FIELDS` es la pieza clave del proyecto entero.** Cada campo declara la ruta de la función que lo lee (paso 1.3 del plan). Es el principio P2 convertido en algo que se cae solo, en vez de en algo que alguien tiene que recordar.

**La regla de los tres estados, y existe porque la primera versión de este test era inservible.** Se escribió exigiendo que **todos** los lectores fueran importables — pero seis de los ocho viven en módulos de las capas de arriba, que durante la construcción todavía no existen. Eso lo condenaba a estar rojo durante semanas, y un test permanentemente rojo es la peor clase de test: se ignora, y detrás se esconde un fallo de verdad.

Los tres estados de un lector declarado:

| Estado | Cuándo | Veredicto |
|---|---|---|
| **verificado** | su módulo existe **y** tiene la función | verde |
| **pendiente** | su módulo aún no se ha escrito | verde, **pero se cuenta y se enseña** |
| **roto** | su módulo existe y **no** tiene la función | **rojo, siempre** |

El test **imprime cuántos pendientes quedan** — el cero se enseña, no se calla (P6). Hoy dirá seis; mañana cinco. **Y la puerta de aceptación del §13.1 exige que ese número sea cero**: mientras quede uno, el sistema no está acabado.

Lo que sigue cazando desde el primer día: alguien añade un campo con un lector que no existe en un módulo que **sí** existe. Rojo inmediato, que es el caso que mató al v1.

**Qué NO hace.** **No valida nada.** Es datos, no lógica. Lo leen también el formato, el render y el arranque, pero solo para presentar: nadie valida contra él sin pasar por `validator`. Esa es la puerta única de la restricción D del plan.

**Quién lo lee.** `validator` (todas sus funciones) · `format` (para construir y parsear) · `ids` (los tipos) · `indexes` (los ocho ficheros) · `report_render` y `boot` (para presentar).

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| **Todo campo de `FIELDS` declara un lector, y ese lector existe de verdad — con la regla de los tres estados** | Los 1.002 `Why:` y 605 `Touched:` del v1: campos escritos miles de veces sin que nadie los leyera |
| La pregunta del dolor aparece **exactamente una vez** en todo el código | Dos copias que se separan, y la aduana pregunta una cosa mientras la skill enseña otra |
| Cada uno de los siete tipos declara sus campos obligatorios y permitidos | Un tipo nuevo que entra sin decir qué necesita, y el validador lo deja pasar vacío |
| Los ocho ficheros de índice son ocho, ni uno más | Alguien añade `PLANS.md`, que la especificación prohíbe expresamente |

**Qué del v1 NO se trae.** `[medido — TESTIGO §1]` `RISK_VALUES` — un enum de valores válidos que **nunca se importó desde ningún sitio**, mientras 79 commits escribían el campo que debía validar. Y `MEMO_CATEGORIES`/`REMEMBER_CATEGORIES`, que mueren con el memo del v1 `[spec §4]`.

---

### 6.2 `lib/memory/zones.py`

**Para qué.** Cargar y consultar las zonas del proyecto.

**De qué salida se deriva.** Del rechazo de zona inexistente `[TEXTOS §1.1]`, que imprime el recuento total, y luego las más parecidas **con su número de notas y su descripción**:

```
zones.json tiene 34 zonas. Antes de crear una nueva, mira si ya está
con otro nombre. Las más parecidas:

  billing     18 notas   "cobros, pasarela de pago, suscripciones"
  invoices     4 notas   "documentos de factura emitidos al cliente"
```

De ahí sale que buscar parecidas no puede devolver nombres sueltos: devuelve zonas enteras. Y que **el recuento no lo pone esta pieza** — lo pone quien lo imprime, leyendo el índice, porque `zones.json` no sabe cuántas notas hay.

**Superficie.**

```python
def load(path: Path) -> dict[str, Zone]
def resolve(name: str, zones: dict[str, Zone]) -> str | None      # aplica alias; None si no existe
def candidates(name: str, zones: dict[str, Zone], limit: int = 3) -> tuple[Zone, ...]
def add(zone: Zone, path: Path) -> None                            # el alta en dos pasos, paso 2
```

`add` escribe bajo candado y de forma atómica: es la única escritura de este fichero. **Quien la ejecuta es siempre el comando `gitmem zones`** — también en el alta en dos pasos, donde la aduana solo rechaza indicando qué hacer y es Claude quien da de alta la zona y relanza `[spec §3.2]`. Ni la aduana ni el validador escriben nunca.

**Qué NO hace.** **No decide si una zona es válida** — eso es `validator.validate_zones`. No conoce la lista negra ni la palabra ilegal, que son datos de `vocabulary`. No lee los índices.

**Quién lo llama.** `validator.validate_zones` llama a `load`, `resolve` y `candidates` — por dentro, para que no haya una segunda puerta. A `add` **solo** lo llama `bin/memory/zones.py`, porque el validador no escribe nada.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Un alias resuelve a su zona canónica | Conviven `front` y `frontend` como zonas distintas y la memoria se parte en dos |
| Una zona inexistente devuelve `None`, no una excepción ni una cadena vacía | Un fallo que se confunde con «zona sin notas» y pasa callado |
| `candidates` encuentra la zona que se escribió mal por poco | El rechazo llega sin candidatas y el usuario crea el sinónimo igualmente |
| Dos `add` concurrentes no se pisan | Una zona dada de alta desaparece porque otra escritura la sobrescribió — pérdida silenciosa |
| **Ida y vuelta:** una zona con tildes en su descripción y varios alias, escrita con `add` y releída con `load`, vuelve idéntica | Una descripción truncada o un alias mal guardado: el rechazo imprimiría algo distinto de lo que se escribió, y nadie lo notaría |

**Qué del v1 NO se trae.** `[medido — TESTIGO §1]` El caché del glosario: 249 líneas con caducidad de 24 horas, comprobación de HEAD, del origen remoto y del esquema, más guardas de enlaces simbólicos. `zones.json` es un fichero pequeño que se lee entero: un caché ahí es maquinaria con estado, y cada pieza automática con estado es superficie de fallo `[spec P4]`.

---

### 6.3 `lib/memory/config.py`

**Para qué.** Los tres ajustes del proyecto, que pone una persona.

**De qué salida se deriva.** No de un texto: de tres comportamientos. El interruptor de la aduana `[plan §1, decisión del council]`, y el tipo de repositorio y el comando de tests, que hoy viven en `.claude/git-memory-config.json` y varias skills escriben `[DRIFT §6]`.

**Superficie.**

```python
@dataclass(frozen=True)
class Config:
    customs_enabled: bool = False      # la aduana NACE APAGADA
    repo_type: str = "gitflow"         # fail-closed: main protegido si no se declara
    test_command: str | None = None

def load(path: Path) -> Config
```

**Qué NO hace.** No guarda zonas. **Fichero aparte a propósito** `[decisión del propietario]`: las zonas las escribe el sistema a menudo, esto lo pone una persona una vez. Juntarlos es cómo una escritura automática acaba pisando un ajuste hecho a mano.

**Quién lo llama.** `hooks/customs.py` lee `customs_enabled` · `bin/memory/work.py` y `bin/memory/wip.py` leen `repo_type` antes de commitear, para saber si `main` está protegido (`wip.py` añadido 2026-08-03, misma protección que `work.py`, compartida vía `repo_guard.py` — §10.1) · el protocolo de cierre de sesión lee `test_command`.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Sin fichero, la aduana queda **apagada** | El primer día de instalación la aduana bloquea al v1 que todavía está en uso |
| Sin fichero, el tipo de repositorio es el protegido | Un commit directo a `main` en un repo que despliega solo |
| Un fichero corrupto **falla en alto**, no devuelve valores por defecto en silencio | La aduana apagada sin que nadie sepa que lo está — un vigilante que no vigila y no lo dice |

---

### 6.4 `lib/memory/format.py`

**Para qué.** Construir y parsear. Es **la pareja productor↔consumidor** del sistema.

**De qué salida se deriva.** De las siete plantillas de commit `[TEXTOS §5]`, las ocho líneas de índice y de archivo `[TEXTOS §4]`, y el commit de contexto `[TEXTOS §5]`. El titular, con el emoji ya en su sitio:

```
[D-030][product][auth] 🧭 login with JWT + Google OAuth
```

**Superficie.** Cada constructor tiene su parser. **No hay ninguno suelto**, y esa simetría es el contrato — **matizado el 2026-08-04**, ver abajo qué nivel de esa simetría es el que llega a producción.

```python
def build_subject(note: Note) -> str
def parse_subject(line: str) -> _SubjectParts | None

def build_message(note: Note) -> str
def parse_message(text: str) -> Note | None

def build_index_line(note: Note) -> str
def parse_index_line(line: str) -> IndexLine | None

def build_archive_line(line: ArchiveLine) -> str        # ← CORREGIDO, ver abajo
def parse_archive_line(line: str) -> ArchiveLine | None

def build_context_message(ctx: ContextNote) -> str
def parse_context_message(text: str) -> ContextNote | None
```

**La clase que trae `parse_subject` pasó a `_SubjectParts` (interna) el 2026-08-04** `[corregido — este documento la declaraba pública]`, pero **`build_subject`/`parse_subject` siguen siendo funciones públicas** — solo cambió el molde de datos que la segunda devuelve, no la función. Lo que sí es cierto, y matiza «esa simetría es el contrato»: `build_message` llama a `build_subject` por dentro, y `parse_message` resuelve el titular por dentro también — **ese es el nivel que de verdad alcanza producción**. `build_subject`/`parse_subject` siguen siendo la pareja que construye y lee el titular, pero hoy **ningún módulo de producción los llama directamente**; los únicos llamadores medidos fuera de `format.py` son tests (`test_format.py::test_emoji_after_brackets_enforced`, verificado por `test_boundary.py`). La idea de fondo no cambia — el titular se construye y se lee con una pareja simétrica, nunca con un constructor suelto — solo el nivel al que un consumidor externo debería engancharse: `build_message`/`parse_message`, no `build_subject`/`parse_subject`.

Los parsers devuelven `None` ante una línea que no es de las suyas — **nunca lanzan y nunca adivinan**. Un `ARCHIVED.md` con una línea escrita a mano no puede tumbar el arranque entero.

**Qué NO hace.** **No valida.** Construye lo que le den y parsea lo que le pasen. Si el titular pasa de 80 caracteres, `build_subject` lo construye igual: quien lo rechaza es `validator`. Separarlo es lo que permite que el parser lea notas viejas sin que las reglas de hoy se lo impidan.

**Quién lo llama.** `notes` (al escribir) · `query` (al leer) · `indexes` (las dos líneas de fichero) · `context`.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| **Ida y vuelta para los siete tipos y para el `[NEXT]`**: construir → parsear → objeto idéntico al de partida | Que el sistema escriba algo que él mismo no sabe volver a leer. Es el fallo que mata una memoria, y se prueba con un objeto generado, nunca con una cadena escrita a mano |
| Ida y vuelta de la línea de índice y de las **tres** formas de línea de archivo | Un `→ promoted to X-030` que el parser no reconoce y desaparece del informe sin avisar |
| Una línea corrupta devuelve `None` y no lanza | Un fichero editado a mano tumba el arranque en vez de reportar una incoherencia |
| El emoji va **después** de los corchetes, y el parser lo exige ahí | Dos formatos conviviendo, que es como se pierde la mitad de la historia |

**Qué del v1 NO se trae.** `[medido — TESTIGO §3]` Las **tres** implementaciones separadas de «parsear el historial hacia memoria estructurada» — 562 líneas en tres ficheros, sincronizadas a mano, que ya habían fallado tres veces con el mismo patrón. Aquí hay una y solo una.

---

### 6.5 `lib/memory/similar.py`

**Para qué.** Detectar si una nota nueva pisa a otra que ya está escrita.

**De qué salida se deriva.** Del rechazo 1.6 `[TEXTOS §1.6]`, y el texto manda sobre la firma. El rechazo imprime las candidatas **con su fecha, sus keys y su porqué entero**:

```
  D-030   2026-04-11   login with JWT + Google OAuth
          keys: token, oauth, sso, signin
          Why: sesiones no escalan multi-tenant; Google evita gestionar
               passwords propios
```

De ahí sale que esta pieza **devuelve notas enteras, no identificadores**. Si devolviera identificadores, el rechazo tendría que ir a buscarlas otra vez — y ahí es donde aparece la segunda puerta de lectura que el diseño prohíbe.

**Superficie.**

```python
def find_similar(
    candidate: Note,
    existing: tuple[Note, ...],
    threshold: float,
) -> tuple[Note, ...]
```

**Recibe los datos ya cargados. No lee ficheros y no llama a git.** Quien la llama es el validador, que sí sabe de dónde sacarlos.

**Qué NO hace.** No decide qué pasa con el parecido — eso es `validator.validate_replacement`, que es quien rechaza pidiendo `--replaces`. No busca fuera de la zona: comparar entre zonas distintas es ruido por definición.

**Quién lo llama.** `validator.validate_replacement`, por dentro. **Ningún script lo llama directamente**, para que no haya una segunda puerta.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Dos notas casi iguales de la misma zona se detectan | Se duplica una decisión y conviven dos verdades sin que nadie lo note |
| Dos notas distintas de la misma zona **no** se detectan | Un rechazo que salta siempre acaba ignorándose siempre |
| Una nota igual pero de **otra** zona no se detecta | Ruido en cada alta que enseña al usuario a saltarse la pregunta |
| Devuelve notas completas, con su porqué y sus keys | El rechazo se queda sin lo que tiene que imprimir y hay que ir a buscarlo por otra puerta |

**Qué del v1 NO se trae.** `[medido — TESTIGO §1]` `recall_relevant` — **79 líneas de motor de relevancia, con suelo de puntuación y fracción superior, y cero consumidores en todo el repo.** Estaba escrita, pensada y con ocho tests en verde. Nadie la enchufó nunca. Es la pieza que mejor explica por qué existe la puerta del llamador declarado.

---

## 7. CAPA 2 — git, los índices, y la pieza única

Cinco piezas. Aquí aparece el validador, que es la que sostiene todo el diseño.

---

### 7.1 `lib/memory/gitcmd.py`

**Para qué.** Hablar con git sin perder por el camino lo que git dice.

**De qué salida se deriva.** De la novena validación de la aduana `[spec §6]`: *propagación del error real de git*. Y del candado `[spec §7]`.

**El fallo concreto:** si el commit de una nota falla y el sistema devuelve una cadena vacía, el usuario ve «no se pudo guardar» sin más, y el índice puede quedar apuntando a una nota que no existe. El mensaje de git **es** el diagnóstico; tragárselo convierte un fallo con causa en un fallo sin causa.

**Superficie.**

```python
@dataclass(frozen=True)
class GitResult:
    returncode: int
    stdout: str
    stderr: str                    # el mensaje real, entero, nunca vacío ni recortado

def run(args: Sequence[str], cwd: Path, timeout: int) -> GitResult
def repo_root(cwd: Path) -> Path
def commit(message: str, paths: Sequence[Path], allow_empty: bool) -> GitResult
def file_lock(path: Path)              # context manager, bloqueo exclusivo, no reentrante
def atomic_write(path: Path, content: str) -> None
```

`commit` acepta **rutas explícitas** y solo commitea esas — lo exige la publicación del toolkit, que commitea tres ficheros concretos sin arrastrar el resto del índice `[plan §2.7]`.

`atomic_write` escribe a un temporal en el mismo directorio y solo reemplaza el original cuando el contenido está entero en disco. Un `open(path,"w")` corriente vacía el fichero en el instante en que se abre: si el proceso muere a mitad, **el índice se queda vacío o partido**.

**Qué NO hace.** No sabe qué es una nota, ni un índice, ni una zona. Es la capa de git y nada más.

**Quién lo llama.** `notes` · `indexes` · `query` · `context`.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Un git que falla devuelve **su mensaje entero**, nunca vacío | Un fallo sin causa: el usuario ve «no se pudo guardar» y no hay forma de saber por qué |
| Dos procesos escribiendo el mismo índice se serializan | Los dos leen, cada uno cambia su parte, y el último borra el cambio del otro sin avisar |
| Una escritura atómica interrumpida deja el fichero original **intacto** | Un índice a medias, que es memoria perdida |
| Anidar el candado sobre la misma ruta se detecta | Un bloqueo mutuo que cuelga el proceso para siempre, sin mensaje |

**Qué del v1 NO se trae.** El v2 escribe su propio candado, imitando a propósito el mecanismo del v1 porque está probado en producción — **es la única pieza que se reescribe copiando la idea**, y queda dicho `[plan §3.3]`.

---

### 7.2 `lib/memory/ids.py`

**Para qué.** Dar el siguiente identificador, y avisar si hay dos iguales.

**De qué salida se deriva.** Del formato del titular `[spec §3.1]`: contador simple por tipo, asignado por el script leyendo el índice. Y del aviso del arranque `[TEXTOS §3.1]`: `✓ no duplicate IDs (68 notes)` (etiqueta en inglés `[decisión del propietario, 2026-08-03]`).

**Superficie.**

```python
def next_id(type_: str, index: tuple[IndexLine, ...]) -> str      # "D-031" tras treinta
def find_duplicates(index: tuple[IndexLine, ...]) -> tuple[str, ...]
```

**Qué NO hace.** No repara un duplicado. **Es alarma pasiva: detecta y lo enseña** `[spec §3.1]`. Repararlo automáticamente significaría renumerar una nota ya escrita, y con ella todos los punteros que la citan.

**Quién lo llama.** `notes.write` (para el alta) · `health.duplicates` (para el aviso del arranque).

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| `D-001` en un índice vacío; `D-031` tras treinta | Empezar en cero cada sesión y pisar identificadores existentes |
| El contador es **por tipo**: treinta decisiones no mueven el contador de memos | Un hueco en la numeración que hace pensar que faltan notas |
| Dos notas con el mismo identificador se detectan | Dos notas distintas indistinguibles en los punteros — un racimo apuntando a la equivocada |

---

### 7.3 `lib/memory/indexes.py`

**Para qué.** Leer y escribir los ocho ficheros. **Nadie más los toca.**

**De qué salida se deriva.** De los ocho formatos `[TEXTOS §4]`, con su cabecera: *«Lo escribe el script. No editar. Si diverge, manda git.»*

**Superficie.**

```python
def seed(root: Path) -> None                       # crea los ocho vacíos con su cabecera; idempotente
def read(name: str, root: Path) -> tuple[IndexLine, ...]
def read_archive(root: Path) -> tuple[ArchiveLine, ...]
def insert(line: IndexLine, name: str, root: Path) -> None
def remove(note_id: str, name: str, root: Path) -> None
def archive(line: ArchiveLine, root: Path) -> None
def counts(root: Path) -> Mapping[str, int]        # al vuelo, nunca guardados
```

**Qué NO hace.** **No commitea.** Escribe el fichero; quien lo mete en el mismo commit que la nota es `notes`, y esa unión es la transacción del sistema `[spec §7]`. No decide qué va a qué índice: eso lo dice el tipo de la nota.

**Quién lo llama.** `notes` (las cuatro escrituras) · `query` y `report` (lectura) · `health` (para cotejar contra git). **`ids` NO**: recibe el índice ya cargado como parámetro, no lo lee él.

**`counts` no tiene llamador de producción, y no se retira por eso** `[añadido 2026-08-04, tras verificarlo]`. `boot.py` y `report.py::_by_type` calculan su propio desglose por tipo leyendo el historial de git directamente, no los índices — así que ningún módulo de `lib/memory/` ni `bin/` invoca `indexes.counts` hoy. Pero **tres tests de `test_health.py` sí la llaman**, como segunda opinión: derivan el número de líneas esperado con `sum(indexes.counts(root).values())` y lo comparan contra lo que devuelve `health.coherence()`, en vez de teclear el número a mano `[unmassk-standards §34: no fabricar el resultado esperado de un round-trip]`. La regla que decide si una función así se retira es **producción == 0 Y tests == 0**; aquí solo la primera mitad es cierta, así que `counts` se queda. Es el mismo criterio que ya evitó tratarla como caso especial: `test_boundary.py` había empezado una lista de excepciones escrita a mano solo para `counts`, y se sustituyó por esta regla genérica de dos ramas — «con dos números no hay nada que decidir» — que ahora protege a `counts` junto con otras ocho funciones en la misma situación (producción cero, algún test), sin necesitar una lista aparte para cada una.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| `seed` dos veces no duplica ni borra nada | Instalar en un proyecto que ya tiene notas y vaciarle los índices |
| Las **tres** formas de destino del archivo se parsean: `replaced by` · `closed:` · `promoted to` | Una nota retirada desaparece del informe sin dejar rastro de a dónde fue |
| Los recuentos se calculan leyendo, nunca se guardan | Un número guardado que se separa de la realidad y nadie lo nota |
| Insertar en un índice inexistente falla en alto | Un índice que se crea solo, medio vacío, y parece que no hay notas |
| **Ida y vuelta de fichero:** insertar tres líneas y releerlas con `read` devuelve las tres, en orden y en el índice correcto | Una nota que se guarda en el fichero equivocado, o que se pierde entre otras al reescribir |

---

### 7.4 `lib/memory/rejection.py`

**Para qué.** Un texto, dos salidas.

**De qué salida se deriva.** De los diez rechazos `[TEXTOS §1]`. Todos tienen la misma anatomía, y es lo que hace que la pieza sea una y no diez: **qué ha pasado**, **las opciones**, y **el comando exacto para relanzar**.

**El fallo que previene:** un rechazo que solo dice «no válido» obliga a adivinar. El del v1 no existía siquiera — la aduana nueva rechaza *informando*, y por eso el texto es parte del contrato y no del gusto de quien lo escriba.

**Superficie.**

```python
def build(kind: str, **parts) -> Rejection
def render_terminal(r: Rejection) -> str
def render_hook_block(r: Rejection) -> str      # el que devuelve el hook al bloquear
```

**Mismo objeto, dos renderizados.** El generador imprime el de terminal; la aduana emite el de bloqueo. Si fueran dos textos, se separarían.

**Qué NO hace.** No decide si algo se rechaza — eso es `validator`. Solo da forma a la decisión que otro tomó.

**Quién lo llama.** `notes` (cuando el generador rechaza en proceso) y `hooks/customs.py` (cuando rechaza la aduana). **Los mismos dos consumidores que el validador**, y no es casualidad: van siempre juntos.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Los diez rechazos llevan **los tres elementos**: qué pasa, opciones, comando de relanzamiento | Un rechazo que obliga a adivinar, y que se acaba esquivando en vez de contestando |
| El comando de relanzamiento es **ejecutable tal cual**, sin editar | Copiar, pegar, y que falle otra vez por una comilla |
| Los dos renderizados llevan el mismo contenido | Que la aduana diga una cosa y el comando otra |

---

### 7.5 `lib/memory/validator.py`

**Para qué.** **La única implementación de «esto es válido» en todo el sistema.**

**De qué salida se deriva.** De las nueve validaciones de la aduana `[spec §6]` y de los diez rechazos que las expresan `[TEXTOS §1]`.

**Por qué es una sola pieza, y es la restricción D del plan:** la llaman el generador y la aduana. Si hubiera dos implementaciones, habría **dos verdades el primer día** — que es exactamente cómo murió `Sources:` en el v1: obligatorio según un lado, inexistente según el otro, descartado en silencio por los tres parsers `[medido — TESTIGO]`.

**Superficie.**

```python
@dataclass(frozen=True)
class Context:
    """Todo lo que el validador necesita saber del mundo.
    Lo trae quien lo llama: el validador NI abre ficheros NI llama a git."""
    zones: dict[str, Zone]
    existing_in_zone: tuple[Note, ...]
    known_ids: frozenset[str]
    config: Config

def validate_note(note: Note, ctx: Context) -> tuple[Rejection, ...]   # vacío = válida

def validate_headline(...)      # longitud, formato, idioma
def validate_zones(...)         # existencia, alias, lista negra, palabra ilegal, alta en dos pasos
def _validate_type(...)         # el árbol; si no encaja limpio, rechaza preguntando qué es
def validate_fields(...)        # obligatorios por tipo · no permitidos · inexistentes
def normalize_keys(...)         # vocabulario controlado, tope de cinco, ninguna ya en el titular
def validate_pain_question(...) # la exige en M y R; si la respuesta contradice al tipo, lo dice
def validate_pointers(...)      # los identificadores citados existen de verdad
def validate_replacement(...)   # si hay parecidas y no se declara sustitución, rechaza con ellas dentro
def validate_distillation(...)  # toda destilación exige fuentes
def is_wip(...)                 # el commit exento de toda pregunta
```

**`validate_type` pasó a `_validate_type` (interna) el 2026-08-04** `[corregido — este documento la declaraba pública]`. No es el mismo motivo que las demás renombradas de hoy: no era un lector fantasma para engañar a `vocabulary.FIELDS` (eso no aplica aquí — `type` no es uno de los ocho campos con lector declarado). Es una de las seis funciones que agrega `validate_note`, la única puerta real del validador desde fuera; fuera de este fichero nadie la llama y no tiene test propio, así que no había razón para dejarla pública. **No se generaliza a las otras siete `validate_*`**: `validate_pain_question`, `validate_issue` y `normalize_keys` sí tienen llamador externo (`bin/memory/note.py`/`remove.py`); `validate_headline`, `validate_fields`, `validate_replacement` y `validate_distillation`, aunque tampoco tengan llamador externo, sí tienen test propio — esas se quedan públicas.

**`validate_zones` y `validate_pointers` no están definidas aquí** `[corregido 2026-08-04 — este documento las daba por escritas en este fichero]`. Se partieron de `validator.py` por el mismo techo de 500 líneas que ya partió `format.py` `[DEUDA.md punto 12]`: `validate_zones` vive en **`validator_zones.py`** y `validate_pointers` en **`validator_pointers.py`** (una tercera, `validate_issue`, se partió el mismo día a **`validator_issue.py`** — comprueba contra GitHub que la issue del acta existe de verdad, es la única de las diez que no es pura). `validator.py` las importa de forma plana y las reexpone bajo el mismo nombre, así que `validator.validate_zones`/`validator.validate_pointers`/`validator.validate_issue` siguen alcanzables exactamente igual para quien las llame — la Superficie de arriba sigue siendo la superficie real, solo cambia en qué fichero vive cada `def`. Verificado: `grep -n "^def validate_zones\|^def validate_pointers" lib/memory/*.py`.

**Que `Context` sea un dato pasado desde fuera es la decisión estructural de esta pieza.** El validador es puro: mismos datos, mismo veredicto, siempre. Por eso se puede probar entero **sin que exista un solo commit** (fase 1 del plan), y por eso el hook y el generador obtienen exactamente la misma respuesta — cada uno arma el `Context` a su manera, pero la regla es una.

**Qué NO hace.** **No escribe nada.** No repara. No normaliza en disco: `normalize_keys` devuelve la forma buena, y quien la guarda es el generador. Un hook no puede escribir `[TEXTOS §6.3]`, y por eso la key mal escrita **no es un rechazo, es un aviso al guardar bien**.

**Quién lo llama.** **Exactamente dos:** `notes` (y a través suyo los cuatro scripts que escriben) y `hooks/customs.py`. Ninguno más — `zones` y `similar` no los llaman los scripts, los llama el validador por dentro, para que no exista una segunda puerta.

**Consecuencia buscada:** como el generador valida en proceso con esta misma pieza, **la aduana casi nunca dispara**. Existe para lo que no pasa por el generador: un commit a mano y los subagentes.

**Sus tests.** Uno por regla, y todos **sin un solo commit**:

| Test | Fallo real que previene |
|---|---|
| Un titular de 81 caracteres rebota, y el rechazo dice el tope | Titulares que crecen hasta dejar de ser leíbles de un vistazo en el índice |
| Una M sin respuesta a la pregunta del dolor rebota **con la pregunta literal dentro** | Que el muro y el hecho se confundan, y una restricción que debía salir en todos los arranques quede enterrada como memo |
| Un «sí» a la pregunta del dolor en una M dice «entonces es una R» | Lo mismo, pero cuando el usuario ya contestó bien y solo se equivocó de letra |
| Una nota parecida sin `--replaces` rebota **con las candidatas completas dentro** | Dos decisiones contradictorias vigentes a la vez, y nadie sabe cuál manda |
| Un campo que no existe para ese tipo rebota | Los campos zombis del v1: escritos, nunca leídos, invisibles |
| Una destilación sin fuentes rebota | Un resumen del que no se puede volver al original ni comprobar si resume bien |
| El `wip` no recibe **ni una sola** pregunta | Fricción en el checkpoint silencioso, que es lo que hace que se deje de usar |
| Mismos datos → mismo veredicto, siempre | Un validador que depende del entorno: pasa en el generador y falla en el hook, o al revés |

---

## 8. CAPA 3 — la transacción y la lectura

Dos piezas, y la primera es donde el sistema se puede corromper a sí mismo.

---

### 8.1 `lib/memory/notes.py`

**Para qué.** Escribir una nota **y su línea de índice, en el mismo commit, o ninguna de las dos.**

**De qué salida se deriva.** De la regla de los índices `[spec §7]`: *«La actualización del índice viaja en el mismo commit que la nota»*. Y del aviso del arranque que comprueba que se cumplió `[TEXTOS §3.1]`: `✓ indexes match git (68 lines / 68 notes)` — o, si hay notas archivadas, `✓ indexes match git (587 live + 25 archived / 612 notes)` `[decisión del propietario, 2026-08-03]`.

**El fallo concreto, y es el peor del sistema:** si la nota se commitea y el índice no, hay una nota que ninguna búsqueda encuentra — memoria escrita e invisible. Si se actualiza el índice y el commit falla, hay una línea que apunta a una nota que no existe. Las dos son corrupción silenciosa: nada revienta, y el fallo se descubre semanas después.

**Superficie.**

```python
def write(note: Note, ctx: Context) -> WriteResult
def replace(new: Note, old_id: str, ctx: Context) -> WriteResult
def close(note_id: str, reason: str, ctx: Context) -> WriteResult
def discard_alternatives(decision: Note, alternatives: tuple[Note, ...], ctx: Context) -> tuple[WriteResult, ...]
def write_work(message: str, paths: Sequence[Path], issue: int | None) -> WriteResult
```

**`write_work` no está definida aquí** `[corregido 2026-08-04 — este documento la daba por escrita en este fichero]`. Vive en **`notes_commit.py`** (`def write_work`, con un cuarto parámetro real que esta firma no reflejaba: `known_content: list[bytes | None] | None = None`, la huella de contenido con la que detecta si otro proceso tocó la misma ruta mientras la llamada seguía en curso). `notes_commit.py` es el fichero al que se partió, por el mismo techo de 500 líneas que ya partió `format.py`/`validator.py` `[DEUDA.md puntos 12/14]`, toda la mecánica de git de la que `notes.py` tira por debajo: el candado (`lock_resource`), la raíz (`repo_root`/`pm_root`), `git add`+`git commit` (`stage_and_commit`) y las dos restauraciones de mejor esfuerzo. `write_work` fue con ella porque es la única de las cinco operaciones de esta ficha que no toca ningún índice y por tanto no necesitaba, en un principio, ni candado ni restauración. `notes.py` importa los siete nombres de `notes_commit.py` de forma plana y los reexpone bajo el mismo nombre, así que `notes.pm_root`/`notes.write_work` siguen alcanzables exactamente igual para quien los llame hoy.

**Dato que no hay que repetir mal: `write_work` SÍ coge el candado.** Verificado — `grep -n "gitcmd.file_lock(lock_resource" lib/memory/notes.py lib/memory/notes_commit.py` da `notes.py:199` (`write`), `:314` (`replace`), `:401` (`close`) y **`notes_commit.py:452`**, dentro del cuerpo de `write_work` (línea 303). Arreglo del 2026-08-03, hallazgo de Moriarty en la capa 3: sin él, escritores concurrentes reales chocaban contra `.git/index.lock` sin reintento, 7-8 de cada 10. Cualquier texto que insinúe que `write_work` sigue sin candado está caducado.

**El orden de `write` es el contrato, y no es negociable:**

```
candado → identificador → validar → escribir el índice → commit de nota + índice JUNTOS
       → si git falla: restaurar el índice y propagar el error REAL de git
```

Validar **antes** de tocar el índice, y restaurar **después** de que git falle. Cualquier otro orden deja una ventana en la que el índice y git dicen cosas distintas.

`discard_alternatives` produce **un commit por descarte**, cada uno con su identificador y su línea `[plan §1, decisión 5]`: *«un acto, un commit» aplica a nota+índice, no al acto completo*. Una decisión con dos alternativas produce tres commits, y los tres índices cuadran.

`write_work` es el commit de trabajo: lleva su referencia a issue, **acepta rutas concretas** (lo necesita la publicación del toolkit), y **no lleva campo de ficheros tocados** — se retiró del v2 `[plan §1, decisión 1]`.

**Qué NO hace.** No valida (llama a `validator`). No formatea (llama a `format`). No decide qué índice toca (lo dice el tipo). **No pide permiso ni pregunta nada**: si el validador rechaza, devuelve el rechazo y punto.

**Quién lo llama.** Cuatro scripts: `note.py`, `remove.py` (renombrado desde `close.py`), `work.py` y `wip.py` `[wip.py añadido 2026-08-03, decisión del propietario — el checkpoint también pasa por notes.write_work, con la misma protección de rama que work.py, compartida vía repo_guard.py]`. **`next.py` (el script y el subcomando; el módulo interno sigue llamándose `context.py`) NO** — llama a `context.write`, porque el `[NEXT]` está exento de todo este aparato a propósito (§9.6).

**Sus tests.** Contra un repositorio de git de verdad, no simulado:

| Test | Fallo real que previene |
|---|---|
| `git show --stat` del commit contiene **la nota y la línea de índice** | Una nota que ninguna búsqueda encuentra jamás — memoria escrita e invisible |
| Si el commit falla, **el índice queda exactamente como estaba** | Una línea de índice apuntando a una nota que no existe |
| Si el commit falla, el error que sale es **el de git**, entero | Un fallo sin causa, imposible de diagnosticar |
| Una decisión con dos alternativas produce tres commits y tres índices que cuadran | Descartes que se pierden y una alternativa ya rechazada que se vuelve a proponer en seis meses |
| Un commit de trabajo con tres rutas **no arrastra** el resto del árbol | La publicación del toolkit se lleva por delante trabajo a medias |
| Dos escrituras a la vez se serializan | Las dos leen el índice, cada una añade lo suyo, y la última borra la línea de la otra |
| **`replace`: un solo commit lleva la nota nueva, su línea, la vieja fuera del índice y su línea en el archivo** | Que la sustitución quede a medias: dos notas vigentes diciendo lo contrario, y nadie sabe cuál manda |
| **`replace`: la línea archivada dice `→ replaced by <ID nuevo>`**, y se puede volver a leer | Una nota retirada que desaparece sin rastro de a dónde fue |
| **`close`: la línea sale del índice y entra en el archivo con `→ closed: <motivo>`** | Una nota cerrada que sigue saliendo en los informes como si fuera verdad |
| **Si el commit falla, en las dos, los índices quedan exactamente como estaban** | Un índice que apunta a una nota que no existe |
| **Cerrar o sustituir un identificador que no existe rebota**, sin tocar nada | Un archivo que se llena de líneas que no corresponden a ninguna nota |

**Las cinco filas de `replace` y `close` se añaden el 2026-08-02** `[orquestador en modo autónomo, derivadas de spec §5 y TEXTOS §4]`. El punto **10** de `DEUDA.md` las declaraba abiertas —*«su comportamiento real no lo fija ningún texto»*— y **eso ya no es cierto**: la especificación §5 describe los dos caminos («la mata su reemplazo» y «se cruza y chirría»), `TEXTOS.md` §4 fija las **tres** formas literales de la línea de archivo (`replaced by <ID>` · `closed: <motivo>` · `promoted to <ID>`), y la Superficie de esta misma ficha ya dice que cada una es **un solo commit**. Lo único que faltaba eran las filas, y son estas. Sin ellas, las dos funciones seguirían declaradas y lanzando un error de «no implementado», que es **la mitad del ciclo de vida de una nota**: sin ellas no se puede sustituir ni retirar nada.

---

### 8.2 `lib/memory/query.py`

**Para qué.** Leer desde git hacia objetos. **Es el único lector del historial.**

**De qué salida se deriva.** De las cuatro entradas de búsqueda `[spec §8]`: por identificador, por zona, por palabra y por fichero.

**Por qué es uno solo:** el v1 tenía **tres** implementaciones de esto, 562 líneas en tres ficheros, sincronizadas a mano, y ya había fallado tres veces `[medido — TESTIGO §3]`. Aquí hay una.

**Superficie.**

```python
def by_id(note_id: str) -> Note | None
def by_zone(zone1: str | None, zone2: str | None) -> tuple[Note, ...]
def by_word(word: str) -> tuple[tuple[Note, tuple[str, ...]], ...]   # nota + las líneas que casaron
def by_file(path: Path) -> tuple[Note, ...]                          # git log -- <ruta>
```

`by_word` devuelve **las líneas concretas que casaron**, no solo la nota: el informe las marca con `›` `[TEXTOS §2.3]`, y si esta función devolviera solo notas, el render tendría que volver a buscar dentro — segunda puerta de lectura.

`by_file` no necesita ningún campo guardado: **el campo de ficheros tocados no existe en el v2**, y su función la da `git log -- <ruta>` directamente `[plan §1, decisión 1]`. En el v1 ese campo se escribió 605 veces sin que nadie lo leyera nunca.

**Qué NO hace.** No agrupa en racimos (eso es `clusters`). No decide qué está vigente y qué archivado (eso lo dice el índice). No formatea.

**Quién lo llama.** `report` · `boot` · `health` · `bin/memory/search.py`. *(`dispatch` también la llamaba — retirada entera, `[decisión del propietario, 2026-08-03, B20]`, ver §9.8.)*

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Sembrar tres notas y recuperarlas por identificador, zona, palabra y fichero | Que se escriba bien y no se pueda leer — que es tener una memoria que no sirve |
| Un identificador inexistente devuelve `None`, no una excepción | Un fallo que se confunde con «no hay nada» y pasa callado |
| Una lectura de git que falla de forma transitoria **se reintenta** antes de rendirse | Un `git` que falla una vez por carga se lee como «este proyecto no tiene memoria», y la sesión arranca en blanco |
| `by_word` devuelve las líneas que casaron, no solo las notas | El informe no puede marcar la línea y hay que buscarla otra vez por otra puerta |

---

## 9. CAPA 4 — lo que se enseña

Ocho piezas. Todo lo que llega a los ojos de alguien.

---

### 9.1 `lib/memory/clusters.py`

**Para qué.** Agrupar una decisión con lo que cuelga de ella.

**De qué salida se deriva.** Del racimo del informe `[TEXTOS §2.1]`:

```
  D-030  login with JWT + Google OAuth                          2026-04-11
    ├─ X-012  server-side sessions                    descartada · Origin D-030
    ├─ D-041  session lifetime raised to 30 days      vigente   · Origin D-030
    └─ D-036  logout only clears the cookie           archivada · replaced by D-052
```

**La regla, y es innegociable** `[spec §8]`: se agrupa **por punteros** (`Origin`, `Replaces`), **nunca por parecido ni por keys**. Un racimo armado por similitud cambia según el algoritmo y no se puede auditar. Uno armado por punteros es el mismo siempre y **falla en alto**: si un puntero apunta a algo que no existe, la nota queda huérfana — un racimo de una — **y eso es la señal, no un fallo** `[plan §4.1]`.

**Superficie.**

```python
def group(notes: tuple[Note, ...], archived_ids: frozenset[str]) -> tuple[Cluster, ...]
```

**El título del racimo es la nota viva más reciente** `[spec §8]`: si una decisión sustituye a otra, manda la nueva.

**Qué NO hace.** No lee nada. No ordena para presentar. No decide qué está archivado — se lo dan.

**Quién lo llama.** `report.build`.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Una cadena de tres notas encadenadas se pliega en **un** racimo | La misma decisión apareciendo tres veces como si fueran tres decisiones distintas |
| Una nota huérfana da un racimo de una, **sin excepción y sin aviso de error** | Que un puntero roto tumbe el informe entero en vez de enseñarse |
| Con dos notas encadenadas, el título es el de la nueva | Leer como vigente algo que ya se sustituyó |
| Mismo conjunto de notas → mismos racimos, siempre | Un agrupado que cambia entre dos ejecuciones y no se puede auditar |

---

### 9.2 `lib/memory/report.py` y 9.3 `lib/memory/report_render.py`

**Para qué.** El primero decide **qué** se enseña y en qué orden; el segundo lo convierte en texto. Separados para que ninguno pase de 500 líneas.

**De qué salida se deriva.** Del informe de zona `[TEXTOS §2.1]`, del de zona vacía `[TEXTOS §2.2]` y del de búsqueda por palabra `[TEXTOS §2.3]`.

**El orden es contrato, no gusto** `[spec §8]`: restricciones arriba y literales, luego bloqueantes, luego los racimos de decisiones, luego memos e incidencias, y **las preguntas al final, bajo el título «LO QUE ESPERA DE TI»**. Vigente por defecto; la historia completa solo con `--todo`.

**Superficie.**

```python
# report.py
def build_zone(zone: str, include_archived: bool) -> ZoneReport
def build_word(word: str, include_archived: bool) -> WordReport

# report_render.py
def render_zone(r: ZoneReport) -> str
def render_word(r: WordReport) -> str
```

**Las restricciones salen con su porqué**, no solo con el titular `[TEXTOS §6.5]`: *un titular en inglés a secas no cambia la conducta de nadie a las tres de la mañana*.

**Qué NO hace.** `report` no formatea; `report_render` no decide nada ni lee de git. **Y ninguno de los dos devuelve nunca una lista de commits** `[spec §8]`: buscar devuelve el estado de una zona, siempre.

**Quién los llama.** `bin/memory/search.py`. *(`dispatch` también los llamaba, para que el explorador recibiera el informe completo — retirada entera, `[decisión del propietario, 2026-08-03, B20]`, ver §9.8.)*

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| El orden se cumple: restricciones primero, preguntas al final | Un muro enterrado bajo veinte memos, que es no tener muro |
| La historia solo aparece con la opción explícita | Un informe de cien líneas donde lo vigente se pierde entre lo retirado |
| Una zona vacía dice **CERO NOTAS en alto**, y es imposible confundirlo con un error | El silencio del v1: algo deja de funcionar y nadie se entera |
| Las restricciones llevan su porqué | Un titular que nadie obedece porque no dice qué pasa si se lo salta |
| La búsqueda por palabra marca **la línea** que casó | Saber que una nota casó pero no por qué, y tener que leerla entera |

---

### 9.4 `lib/memory/health.py`

**Para qué.** Comprobar que el sistema no se ha roto solo.

**De qué salida se deriva.** Del bloque `CHECKS` del arranque `[TEXTOS §3.1]` (`AVISOS`→`CHECKS`, etiqueta en inglés `[decisión del propietario, 2026-08-03]`):

```
⚠️  plan #47: 3 commits sin reflejar en la issue
✓  no duplicate IDs (68 notes)
✓  indexes match git (68 lines / 68 notes)
```

**Y cuando hay notas archivadas, el segundo aviso se desglosa** `[decisión del propietario, 2026-08-03, TEXTOS §3]` — dos números sueltos no explican por qué divergen:

```
✓  no duplicate IDs (612 notes)
✓  indexes match git (587 live + 25 archived / 612 notes)
```

**Los dos ✓ importan tanto como el ⚠️.** Enseñar el número cuando todo va bien es lo que hace que el día que falle se note. Un chequeo que solo habla cuando falla es indistinguible de uno que no se ejecuta — y eso ya pasó en el v1, donde seis hooks corrían versiones viejas durante días sin que nada lo dijera `[spec P6, P7]`.

**Superficie.**

```python
def coherence(root: Path) -> tuple[int, int, tuple[str, ...]]   # líneas, notas, discrepancias
def coherence_rules(root: Path) -> tuple[int, int, tuple[str, ...]]   # commits de regla, líneas, discrepancias
def duplicates(root: Path) -> tuple[str, ...]
def plans_unreflected() -> tuple[tuple[int, int], ...]
def rebuild_plan(root: Path) -> tuple[tuple[tuple[Note, str], ...], tuple[tuple[str, str], ...]]   # qué insertar, qué quitar
def build() -> HealthReport
```

**`rebuild_plan` se añade el 2026-08-02** `[cierre de los hallazgos de Cerberus y Argus sobre la capa 5]`. **No es una función nueva: es una que estaba escrita en el sitio equivocado.** `bin/memory/rezones.py` (entonces `reindex.py`, renombrado `[decisión del propietario, 2026-08-03]`) reimplementaba treinta líneas del mismo cruce índices-contra-git que `coherence()` ya hacía aquí — dos copias de la misma lógica, y solo una vigilada por los tests de esta ficha. La regla que lo manda ya estaba escrita: la lógica pertenece a un módulo, el script solo despacha. `rezones.py` ahora la llama en vez de repetirla. **Sigue sin reparar nada**: devuelve el plan —qué línea falta y qué línea sobra—, y es el script quien decide aplicarlo, que es justo lo que dice el «Qué NO hace» de abajo.

**`coherence_rules` se añade el 2026-08-02** `[decisión del orquestador en modo autónomo, derivada del hallazgo de Argus]`. Las reglas se guardan **en dos sitios a la vez** —un commit en git y una línea en el fichero— y hasta hoy **nada vigilaba que los dos dijeran lo mismo**, mientras que las notas sí tienen esa vigilancia desde el principio. El fallo que la motiva se demostró ejecutándolo: matando el proceso entre las dos escrituras, la regla quedaba en git e **invisible para siempre** para el comando que la entrega. El orden de escritura ya se corrigió —fichero primero, commit después, y si el commit falla se deshace—, pero eso protege del fallo **futuro**, no detecta el desfase **ya existente**. Sin este chequeo, una regla perdida no la descubre nadie: no hay reconstrucción posible, porque nadie sabe que falta.

**Qué NO hace.** **No repara nada.** Detecta y enseña. Reparar los índices es un comando aparte, explícito, con modo de solo-diagnóstico `[plan §3.7]`.

**Quién lo llama.** `boot.build` y `bin/memory/rezones.py --verify`.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Borrar una línea de un índice a mano se reporta como «falta en índice» | Una nota que existe en git y no la encuentra ninguna búsqueda |
| Añadir una línea de más se reporta también — la divergencia se detecta **en los dos sentidos** | Una línea que apunta a una nota que no existe |
| Con todo correcto, salen **los números**, no el silencio | Un chequeo mudo, indistinguible de uno que no se ejecuta |
| Un commit de trabajo posterior al último movimiento de su issue sale como «sin reflejar», con su recuento | El aviso del arranque que existe para que un plan no se quede atrás calla justo cuando debía hablar |
| Un commit **anterior** al último movimiento de la issue **no** sale | Un aviso que salta siempre acaba ignorándose siempre |
| Sin ningún commit que cite una issue, devuelve vacío **sin consultar nada fuera** | Pagar una consulta externa en cada arranque para preguntar por algo que no existe |
| Si la consulta externa falla o no está disponible, **falla en alto** y nunca devuelve «todo correcto» | El peor fallo posible de esta pieza: decir que un plan está al día porque no se pudo mirar |

**Las cuatro filas de arriba son de `plans_unreflected`, y se añaden el 2026-08-02** `[orquestador, derivadas de spec §10.4]`. La tabla original solo cubría `coherence`, y la función se escribió después porque `vocabulary.FIELDS["issue"]` la declara como su lector — la regla de los tres estados (§6.1) la puso en rojo en cuanto el módulo existió sin ella. Nació, por tanto, **exportada y sin un solo test**, que es el patrón del punto 11 de `DEUDA.md`. La última fila es la que más importa: esta función depende de una herramienta externa (`gh`), y una pieza que informa «todo correcto» porque no pudo comprobarlo es exactamente el fallo silencioso que este sistema existe para impedir.

---

### 9.5 `lib/memory/boot.py`

**Para qué.** El menú del día.

**De qué salida se deriva.** De las dos formas del arranque `[TEXTOS §3.1]` y `[TEXTOS §3.2]`, y del orden exacto de sus cinco bloques `[spec §8.3]`: el `[NEXT]` con su contexto debajo (`⏩` era el marcador antiguo; pasó a `🧭` con su corchete literal `[decisión del propietario, 2026-08-03]`), los bloqueantes con a quién se espera, **todas** las restricciones sin tope, los recuentos (`COUNTS`), y los avisos (`CHECKS`) — las cuatro últimas etiquetas en inglés, mismo lote de decisión.

**La forma del proyecto recién instalado es tan contrato como la otra:**

```
⛔ BLOCKERS ......  C E R O
⚠️ RESTRICTIONS ....  C E R O
                      No hay ningún muro puesto. Nada te va a parar
                      porque nadie ha escrito todavía qué rompe qué.
```

**Superficie.**

```python
def build() -> BootSummary
def render(s: BootSummary) -> str
```

**Qué NO hace.** **Solo compone y renderiza.** No lee git directamente (llama a `query`), no calcula salud (llama a `health`), no escribe.

**Quién lo llama.** `bin/memory/boot.py`, y a través suyo el hook lanzador.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Memoria vacía → **ceros explícitos y ruidosos**, no secciones ausentes | Arrancar creyendo que no hay muros cuando lo que pasa es que el lector falló |
| Tres notas → tres, y las restricciones salen **todas**, sin tope | El presupuesto de renderizado del v1: 10 de 287 decisiones visibles, 96% invisible, y el modelo concluyendo que lo que no salió no existe |
| Un índice corrupto sale como aviso y **el arranque sigue** | Que un fichero a medias deje la sesión sin memoria entera |
| Las horas llevan su etiqueta UTC | Dos máquinas leyendo la misma hora como dos horas distintas |

---

### 9.6 `lib/memory/context.py`

**El módulo mantiene este nombre** `[decisión del propietario, 2026-08-03]`: solo cambiaron el script (`bin/memory/context.py` → `next.py`) y el subcomando (`gitmem context` → `gitmem next`), no la librería. Quien lea «context.py» de aquí en adelante en este documento se refiere siempre a este módulo interno, nunca al script — el que invoca al usuario es `next.py`.

**Para qué.** Leer y escribir el `[NEXT]` del cierre de sesión.

**De qué salida se deriva.** Del commit de contexto `[TEXTOS §5]` y de la primera línea del arranque `[TEXTOS §3.1]`. **El marcador cambió** `[decisión del propietario, 2026-08-03]`: el titular pasa de llevar `⏩` suelto a llevar el corchete literal `[NEXT]` seguido de `🧭` (`[NEXT] 🧭 <titular>`), y el cuerpo es un único campo `Context:` en prosa corrida — nunca una lista de puntos (ver §5.3, `ContextNote.context`).

**Superficie.**

```python
def write(ctx: ContextNote) -> WriteResult
def latest() -> ContextNote | None
```

**Sin zonas, sin identificador, sin línea de índice y sin lápida** `[spec §9]`. **Cada cierre pisa al anterior**: el arranque enseña solo el último. Y está **exento de la aduana** `[plan §6.3]`: es lo último que se escribe en una sesión, y una pregunta ahí es fricción en el peor momento.

**Qué NO hace.** No toca ningún índice. No se archiva.

**Quién lo llama.** `bin/memory/next.py` (lo invoca el protocolo de cierre; renombrado desde `context.py` `[decisión del propietario, 2026-08-03]` — el módulo que llama, este mismo, no cambió de nombre) y `boot.build`.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Se escribe y se lee de vuelta idéntico, con su `Context:` en prosa | Perder el hilo entre sesiones, que es para lo único que existe |
| El segundo cierre pisa al primero y el arranque enseña **solo el último** | Dos «siguiente paso» a la vez, sin saber cuál está vivo |
| La aduana no le hace **ni una** pregunta | Fricción justo al cerrar, que es cuando menos se tolera |

---

### 9.7 `lib/memory/rules.py`

**Para qué.** El fichero de reglas — los remembers. **Fuera del sistema, a propósito.**

**De qué salida se deriva.** Del mensaje de la lista negra `[TEXTOS §1.2]`, que manda ahí lo que no es memoria del proyecto, y de la especificación §12.

**El formato del commit** `[propietario, 2026-08-02]` — no estaba en `TEXTOS.md` y se fija aquí:

```
[remember][user] 🧠 solo fallos del día a día, nada de casos límite académicos

[remember][claude] 🧠 español llano, sin jerga ni metáforas inventadas
```

**Por qué la palabra `remember` va en el primer corchete:** es lo que la aduana usa para filtrarlo, y es un filtro que no puede fallar — el primer corchete de una nota es **siempre** letra + número (`[D-030]`, `[R-007]`), así que `[remember]` no colisiona con ninguna nota posible. La aduana lo reconoce, lo deja pasar sin ninguna pregunta de zona, y el script lo lleva al fichero.

**Nota de ubicación:** el bloque que sigue describe el commit `[NEXT]` (el del cierre de sesión), no el `remember` de esta misma pieza — quedó aquí, junto a `rules.py`, porque los dos comparten el mismo mecanismo de commit vacío. La ficha con autoridad sobre el `[NEXT]` es §9.6 (`context.py`) y §5.3 (`ContextNote`); aquí se deja al día solo lo que cambió, para que las dos no diverjan.

**El `[NEXT]` marca el avance, no el contexto** `[corrección del propietario, 2026-08-02]`. La lista de emojis lo etiquetaba como «contexto/avance» y de ahí salió mal nombrado; la especificación §9 es la precisa: *«el titular ES el Next, obligatorio, con su emoji»*. **Y el marcador mismo cambió después** `[decisión del propietario, 2026-08-03]`: pasa de `⏩` suelto a un corchete literal `[NEXT]` seguido de `🧭` (`[NEXT] 🧭 <titular>`), mismo glifo que `TYPE_EMOJI["D"]`.

Cómo se reparte ese commit, entonces:

| Parte | Qué lleva | Tope |
|---|---|---|
| **Titular** — `[NEXT] 🧭` | **El Next**: qué se está haciendo, qué hay que seguir haciendo, y su issue si la tiene | **80**, como cualquier titular `[propietario]` |
| **Cuerpo** — campo `Context:` | El resumen de **toda la sesión** en **prosa corrida** — lo que se habló, lo que se decidió, lo que se rompió, lo que quedó a medias, y los cabreos con su motivo. **Nunca una lista de puntos.** Sin emoji propio | sin tope fijo |

**Superado por la corrección del propietario, 2026-08-03 — conservado para que quede constancia de qué cambió:** esta sección decía *«Solo titular, en español, sin cuerpo, tope de 200 caracteres»*, razonado con la mediana de 125 caracteres de los 19 remembers reales del sistema anterior. Ese razonamiento valía para el `remember` (que sigue siendo solo-titular, ver arriba), pero el propietario decidió que el `[NEXT]` necesitaba más que un titular de 200 caracteres para no perder el hilo de una sesión entera — de ahí nace el campo `Context:` en prosa, sin el tope que tenía cuando era solo titular.

Sin zonas, sin identificador, sin línea de índice `[spec §12]`.

**Dónde vive el fichero de reglas** `[propietario + medido, 2026-08-02]` — faltaba en todos los documentos y se resuelve aquí:

> **El fichero de reglas es `.claude/project-memory/rules.md` del proyecto**, junto a los ocho índices y a `zones.json`/`config.json`. El comando `/remember` **no lo contiene: lo entrega.**

**El requisito que manda sobre esto, dictado por el propietario:** el comando es **uno solo y general** —vive en `commands/` del toolkit, como las skills viven en `skills/`, y no se instala uno por proyecto—, pero **las reglas que enseña son las del proyecto en el que estás**. Si el contenido viviera dentro del propio fichero del comando, las reglas de un proyecto pisarían las del otro.

**Cómo se resuelve, y está comprobado leyendo comandos reales ya instalados** `[medido — `commands/deploy.md` del plugin oficial de Vercel]`: el cuerpo de un fichero de comando **son instrucciones para Claude**, no un programa. Así que el comando no guarda nada: le dice a Claude que lea el fichero de reglas del proyecto y lo entregue entero. Como la ruta es relativa al proyecto, **es imposible que se mezclen dos proyectos**: no existe ningún sitio donde convivan.

**Una corrección declarada, para que no se repita:** este documento dijo antes que el fichero de reglas *era* el del comando, en `.claude/commands/remember.md`. Era una **deducción del orquestador, no un dato**, y el propietario la corrigió. Queda escrita porque es el error exacto que este documento existe para impedir — rellenar un hueco por criterio propio en vez de preguntar o medir (§0.1 y §0.2).

**Descartado y por qué:** existe una sintaxis (`` !`comando` ``) que ejecuta algo y mete su salida en lo que se le entrega a Claude. **No se usa**: ningún comando de los instalados la emplea, así que no está verificada en vivo. También se valoró escribir un comando dentro de cada proyecto y regenerarlo en cada arranque; se descarta porque depende de que ese mecanismo corra siempre, y el día que no corra las reglas dejan de llegar sin que nadie se entere.

**Para quien lo implemente:** la escritura va **atómica y bajo candado**, con las piezas que `gitcmd.py` ya tiene (`atomic_write`, `file_lock`), sin escribir unas nuevas. El fichero lleva la misma cabecera de aviso que los índices —*«lo escribe el script, no editar»*—, que es lo coherente con sus vecinos de carpeta.

**El flujo, que es de dos pasos y no de uno** `[spec §12]`:

```
commit vacío  [remember][user] 🧠 <el texto>    ← queda en git, como todo lo demás
        ↓  el script lo detecta por el primer corchete
fichero de remembers, organizado                 ← es de donde se lee con /remember
```

Se guarda en git **y** en el fichero. En git porque nada se pierde; en el fichero porque es lo que se entrega entero cuando lo pides.

**Superficie.**

```python
def add(text: str, kind: str) -> WriteResult   # kind: "user" | "claude"
def read_all() -> str                          # el fichero ENTERO, sin filtrar
def similar_existing(text: str) -> tuple[str, ...]   # los parecidos que ya están
```

`similar_existing` compara **por texto**, y su resultado se enseña antes de añadir: si ya hay uno casi igual, se dice y se decide. **El contraste por significado —dos frases distintas que dicen lo mismo— NO se construye**: la especificación lo declara punto abierto porque excede a un script y pide un agente `[spec §12]`.

**Qué NO hace, y son cuatro prohibiciones explícitas** `[spec §12]`: no lleva zonas, no pasa por la aduana de zonas, **no aparece en ninguna búsqueda ni informe**, y **no lo lee ningún agente**. El usuario lo invoca con `/remember`, que entrega el fichero entero a Claude.

**El fallo que previene:** un tercio de toda la memoria del v1, replicada en tres proyectos, era configuración de trabajo disfrazada de memoria de proyecto. Ensuciaba todas las búsquedas.

**Quién lo llama.** `bin/memory/rule.py` y el comando `/remember`.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Se añade una regla y `read_all` devuelve el fichero **entero** | Entregar la mitad de las reglas y que Claude trabaje con la otra mitad sin saberlo |
| Una regla **no aparece** en ninguna búsqueda de memoria | El ruido del v1: un tercio de la memoria era configuración disfrazada |
| Añadir dos a la vez no pierde ninguna | Una regla que se escribe y desaparece — pérdida silenciosa |
| **El commit y el fichero acaban con lo mismo**: se guarda un remember y aparece en los dos sitios | Que quede en git y no en el fichero, o al revés: `/remember` entregaría una lista incompleta sin decirlo |
| Un remember casi idéntico a uno existente se detecta y se avisa antes de añadirlo | La pila de 114 recordatorios duplicados que ya pasó en el sistema anterior |
| Un remember de 201 caracteres rebota | Reglas que crecen hasta mezclar tres cosas en una y dejan de aplicarse |
| El comando entrega el fichero **entero**, nunca una selección | Trabajar con la mitad de las reglas sin saber que falta la otra mitad |

---

### 9.8 `lib/memory/dispatch.py` — **retirada, 2026-08-03**

**Se retira entera** `[decisión del propietario, 2026-08-03, B20]`, junto con el hook que la llamaba (`hooks/inject.py`, antes §11). Motivo del propietario, literal: *«¿Por qué necesitamos inyectarle mierda de memoria a la gente? En su prompt le dices que lo primero que tiene que hacer es investigar en la memoria lo que tiene que ver con el fichero que va a tocar.»*

**Lo que hacía esta pieza** — adivinar la zona del encargo a partir de sus palabras y decidir qué nota le tocaba a cada oficio — **lo hace ahora cada agente él solo, en tres pasos escritos en su propio prompt**: (1) el historial del fichero que va a tocar, (2) de ahí sale la zona, sin adivinarla, (3) los muros de esa zona. Es mejor que lo que había: el agente busca el fichero que de verdad va a tocar, no la zona que alguien dedujo del texto del encargo — que era, además, el punto débil declarado del diseño de esta pieza (el bloque `_NO_ZONE_BLOCK` de más arriba existía solo para el caso en que esa adivinanza fallaba).

**Ningún módulo real dependía de ella** para nada que no fuera el reparto por oficio — comprobado antes de borrar: ni `report.py` ni `report_render.py` la importan en código, solo la nombraban en su docstring como llamador futuro (corregido también). Su único llamador real era `hooks/inject.py`, retirado con ella; y sus tests, `tests/memory/test_dispatch.py`, retirados también.

---

## 10. CAPA 5 — los scripts

**Van en tabla y no en ficha larga a propósito: son piezas finas.** Un script recibe argumentos, llama a **una** función de la librería e imprime lo que le devuelve. Toda la lógica está debajo. Si un script crece, es que se le está colando lógica que pertenece a un módulo.

**La regla común a los diez:** primera sentencia `force_utf8_streams()`; salen por código de retorno distinto de cero cuando fallan; **nunca imprimen una traza de pila** — imprimen el rechazo o el error real de git.

**La tabla cambia por decisión del propietario, 2026-08-03** (`COLA.md §4`): `close`→`remove`, `context`→`next`, `reindex`→`rezones` (renombrados); `bench` se borra entero — *«no lo he autorizado en la vida»*; `boot` **sale de esta tabla**, deja de ser subcomando de `gitmem` — se dispara solo al abrir sesión, como el arranque de siempre (la pieza que genera el documento sigue existiendo, `bin/memory/boot.py`/`lib/memory/boot.py`, solo deja de invocarse vía `gitmem boot`); y `wip` se añade — el checkpoint que el validador ya sabía eximir de toda pregunta pero que ningún comando escribía. **El sistema queda en nueve subcomandos**, más la fachada `bin/gitmem` que los reparte: diez scripts en total.

| Script | Llama a | Admite | Imprime |
|---|---|---|---|
| `bin/gitmem` | despacha al script del subcomando | los nueve subcomandos | lo que devuelva el script; con `--version`, la versión del toolkit |
| `note.py` | `notes.write` · `notes.replace` · `notes.discard_alternatives` | tipo, `--zones`, titular, `--why`, `--description`, `--keys`, `--stops`, `--origin`, `--replaces`, `--awaits`, `--issue`, `--discard "<titular>" "<porqué>"` (repetible) | confirmación con el identificador nuevo, o el rechazo |
| `remove.py` (renombrado desde `close.py`) | `notes.close` · `notes.write` (el muro, si `--restriction new`) | identificador, motivo, `--restriction {no,new}`, `--restriction-text`, `--why` | la línea movida al archivo; con `--restriction new`, también el muro nuevo |
| `next.py` (renombrado desde `context.py`; el módulo interno sigue llamándose `context.py`, §9.6) | `context.write` | titular, `--context "<prosa>"`, `--keys` | confirmación (`[NEXT] 🧭 <titular>`) |
| `work.py` | `notes.write_work` | mensaje, `--path` (repetible), `--issue` | el commit hecho |
| `wip.py` **(nuevo, 2026-08-03)** | `notes.write_work` (con el marcador `🚧` antepuesto) | mensaje, `--path` (repetible) | el commit hecho, o el rechazo de rama protegida |
| `search.py` | `report.build_zone` · `report.build_word` · `query.by_id` · `query.by_file` | identificador, zona, palabra o fichero, `--todo` | **siempre un informe, nunca una lista de commits** |
| `rezones.py` (renombrado desde `reindex.py`) | `indexes` + `health` (`rebuild_plan`) | `--verify` (solo diagnostica) | qué diverge, o qué se reconstruyó |
| `zones.py` | `zones.load` · `zones.candidates` · `zones.add` | `add` · `list` · `find` **(antes `alta`/`listar`/`buscar` — decisión del propietario, 2026-08-04, B29: los tres subcomandos pasan a inglés, sin alias ni periodo de gracia; los nombres en castellano dejan de existir)** | las zonas con su recuento y descripción |
| `rule.py` | `rules.add` · `rules.read_all` | el texto de la regla | confirmación, o el fichero entero |

**`bench.py` se borra entero** `[decisión del propietario, 2026-08-03]` — no tiene fila. Su catálogo de ataques no se pierde: ver el `[pregunta]` abierto en §14 sobre dónde sale ahora su resultado.

**`boot.py` sale de esta tabla** `[decisión del propietario, 2026-08-03]` — sigue existiendo como pieza (`bin/memory/boot.py`, §9.5), pero ya no es un subcomando de `gitmem`: lo dispara el hook de `SessionStart`, no un comando que alguien tenga que acordarse de teclear.

**`note.py` engancha `notes.replace` y `notes.discard_alternatives` desde hoy, 2026-08-04** `[verificado en el código]`. Esta tabla ya daba por hecha la llamada a las tres funciones; **hasta hoy no era cierto**: `note.py` solo llamaba a `notes.write`, y una sustitución con `--replaces` se guardaba como nota nueva sin archivar la vieja — las dos quedaban vigentes a la vez, justo la corrupción silenciosa que `notes.replace` existe para impedir. Hoy `--replaces <ID>` (con un ID real, no el centinela `"none"`) dispara `notes.replace`, y el flag nuevo `--discard "<titular>" "<porqué>"` (repetible, uno por alternativa) dispara `notes.discard_alternatives`. Los dos flujos son mutuamente excluyentes: si hay `--discard`, la nota se escribe solo por ahí, nunca por `write`/`replace`.

**`zones.py add` rechaza un nombre que ya existe, y también uno que ya es alias de otra zona — sin tocar el fichero** `[añadido 2026-08-04, decisión del propietario, tras un fallo real: dos altas seguidas sobre el mismo nombre borraban en silencio el alias y la descripción de la primera, y las dos imprimían el mismo «dada de alta»]`. **La comprobación vive en el script, no en `zones.add()`**: `zones.add()` en sí misma sigue sin comprobar nada — es `bin/memory/zones.py` quien lee `zones.load(path)` antes de construir la `Zone` candidata, y decide no llamar a `add()` en absoluto si el nombre ya es una zona canónica, dejando `zones.json` byte a byte igual. Un choque contra un **alias** de otra zona (no un nombre canónico) queda fuera de este rebote a propósito — ningún documento fija si también debería rebotar, y no se rellena ese hueco aquí `[pregunta pendiente, no de este barrido]`.

**Todos los flags en el primer intento** `[spec P5]`: el coste normal de guardar una nota tiene que ser **un comando y cero rechazos**. Un script que obliga a relanzar tres veces enseña a no usarlo.

### 10.1 Cuatro huecos del contrato, cerrados

`[orquestador en modo autónomo, 2026-08-02 — derivados de la especificación; el propietario puede revocarlos]` Los destapó Dante al escribir los contratos de los cuatro scripts que escriben: la tabla de arriba admite tres flags cuyo comportamiento **no fijaba ningún texto**. Se cierran aquí porque sin ellos los scripts no se pueden construir.

**1 · `note.py --issue` — la comprobación contra GitHub, cerrada** `[corregido 2026-08-04 — este punto decía «hoy no está escrita» y ya no es cierto]`. La especificación §6, validación 8, la declara: *«verificación única contra GitHub de que la issue referenciada existe»*. Está escrita: vive en `validator_issue.py` (`def validate_issue`, partida de `validator.py` por el techo de 500 líneas, §7.5), y `bin/memory/note.py:298` la llama directo — `validator.validate_issue(candidate, args.issue)` — sin pasar por `validate_note`, igual que ya fija §7.5. Su motivo sigue en el texto del rechazo `[TEXTOS §1.9]`: *«Esta es la única vez que se comprueba. Si el número está mal, el enlace decisión → plan queda roto para siempre y nadie lo va a notar.»*

Precedente que ya estaba en pie y sigue igual: `health.plans_unreflected` consulta `gh` y **falla en alto si no puede**, que es el trato correcto: *no se puede comprobar* nunca es *está bien*.

**2 · `remove.py --restriction new`** (entonces `close.py`, renombrado `[decisión del propietario, 2026-08-03]`) **— cierra la incidencia y crea el muro, en el mismo acto.** El texto del rechazo `[TEXTOS §1.10]` fija los flags exactos (`--restriction new --restriction-text "..." --why "..."`), pero ninguna ficha decía quién escribe el muro resultante. **Lo escribe el script, en el mismo acto que el cierre**, y son **dos commits**: uno por la nota cerrada y otro por el muro nuevo, con su `Origin:` apuntando a la incidencia.

No rompe la regla de «un script, una función»: es exactamente el mismo patrón que `notes.discard_alternatives`, donde *«un acto, un commit» aplica a nota+índice, no al acto completo* `[plan §1, decisión 5]`. Con `--restriction no`, el cierre va solo.

**3 · `work.py` y el tipo de repositorio — se protege la rama principal.** `PIEZAS.md` §6.3 dice que este script lee `repo_type` *«antes de commitear, para saber si `main` está protegido»*, pero no decía qué hacer con esa respuesta. **Si el tipo es el protegido y se está en la rama principal, el script rechaza** y dice qué hacer — no commitea y no pregunta.

Es coherente con cómo nace ese ajuste: `config.py` lo declara **fail-closed** (*«main protegido si no se declara»*), y ese valor por defecto solo tiene sentido si alguien lo obedece. Un ajuste que nadie lee es un campo zombi, que es lo que este sistema entero existe para impedir.

**4 · `wip.py` protege la rama principal igual que `work.py`, y no duplicando el control** `[decisión del propietario, 2026-08-03: «el checkpoint protege la rama principal, con la misma protección que work.py» — un checkpoint en la rama principal ES un commit en la rama principal, y da igual que sea rápido]`. La mecánica (qué nombres cuentan como rama principal, cómo se lee la rama actual, el texto del rechazo) vive en una pieza nueva de capa 2, **`lib/memory/repo_guard.py`** — trasladada desde dentro de `work.py`, sin cambiar ni una línea de comportamiento ni el texto del rechazo, para que `wip.py` pudiera pedir la misma protección sin copiarla: dos copias del mismo control es exactamente el patrón que este sistema existe para evitar.

`repo_guard.py` expone `current_branch(root)` (lanza si no puede leer la rama, nunca una cadena vacía), `protected_branch_rejection(branch)` (el texto del rechazo, idéntico al que `work.py` ya usaba) y las dos constantes que gobiernan la decisión: `PROTECTED_REPO_TYPE = "gitflow"` (mismo valor fail-closed que `config.Config.repo_type`) y `MAIN_BRANCH_NAMES = frozenset({"main", "master"})` — lista fija, sin preguntar al remoto. **No decide si se llama**: eso lo decide cada script que lo importa. `work.py` lo llama siempre; `wip.py` lo llama desde esta decisión, con la misma condición (`repo_type` protegido + rama actual en `MAIN_BRANCH_NAMES` → rechaza, no commitea, no pregunta). **Que `wip` no reciba preguntas de la aduana** (`validator.is_wip()` lo exime) **no es lo mismo que «sin protección de rama»**, que es un control distinto. No tiene ficha propia en la CAPA 2 (§7) todavía — queda anotado como hueco de este documento, no de construcción: la pieza ya existe y funciona, solo falta su entrada de siete secciones.

**Sus tests, comunes a los diez.**

| Test | Fallo real que previene |
|---|---|
| Cada script acepta **todos** sus flags de una vez, sin rebotar | La fricción que hace que se deje de usar el sistema, que es la única forma real de perderlo |
| Un fallo sale por código de retorno distinto de cero | Un script que falla en silencio y el llamador cree que guardó |
| Ninguno imprime una traza de pila ante una entrada mala | El usuario ve un volcado en vez de la pregunta que tiene que contestar |
| Las siete clases de nota se crean de verdad en una rama descartable | Que el camino completo no se pruebe nunca de punta a punta |

---

## 11. CAPA 6 — los dos hooks

**Solo hay dos** `[plan §0.4, recuento corregido — decisión del propietario, 2026-08-03, B20: se retira `inject.py`, que era el tercero]`. Todo lo demás se invoca por ruta. El motivo operativo sigue igual y está medido: **los hooks corren desde la caché del plugin**, así que cambiar uno exige publicar versión, actualizar y reiniciar. Un hook no se puede desarrollar iterando `[plan §2, restricción B]`.

| Hook | Evento | Qué hace | Regla que lo gobierna |
|---|---|---|---|
| `customs.py` | `PreToolUse` / `Bash` | Intercepta el commit, llama **al mismo validador**, y bloquea con la pregunta dentro | **Nace apagada.** Se enciende proyecto a proyecto, para no bloquear al v1 mientras siga en uso |
| `boot_launcher.py` | `SessionStart` | ~20 líneas sin lógica: llama a `bin/memory/boot.py` | Se escribe una vez y **no se itera jamás** — por eso no paga el peaje de la caché |

**`inject.py` se retiró entera** `[decisión del propietario, 2026-08-03, B20]` — junto con `lib/memory/dispatch.py` (§9.8), a la que llamaba. Sustituida por tres pasos en el prompt de cada agente: el historial del fichero que va a tocar, la zona que sale de ahí, y los muros de esa zona — ver §9.8 para el motivo completo. No toca esta obra escribir esos tres pasos en los prompts de los nueve agentes; es trabajo de otra fase.

**Sus tests.**

| Test | Fallo real que previene |
|---|---|
| Apagada, la aduana no bloquea nada — probado en vivo contra el v1 | Que el primer día de instalación se bloquee el sistema que todavía está en uso |
| Encendida, bloquea **con el texto exacto** del rechazo | Un bloqueo que no dice qué hacer, y que se acaba esquivando |
| El `wip` y el `[NEXT]` pasan sin **ni una** pregunta | Fricción en el checkpoint y en el cierre, los dos peores momentos para preguntar |

### 11.1 `[pregunta]` — **RESUELTA por el propietario, 2026-08-03**

> **«Siempre que se use git tiene que guardarse de una forma u otra en memoria. La memoria es el registro de cada cosa que hacemos, así que sí, se guarda siempre todo.»**
>
> **Gana la segunda salida: la aduana encendida rebota el commit corriente** y remite a `gitmem work`, para que quede registro de qué se tocó y a qué issue iba. La fricción se acepta a cambio del registro completo — es decisión del propietario, no una deducción.
>
> **Y no hay excepciones por camino** `[corrección del propietario, 2026-08-03: «la aduana tiene que ver pasar todo, ya se habló todo eso»]`. Este documento llegó a declarar `git merge`, `git rebase`, `git cherry-pick` y `git commit --amend` como agujero aceptado, porque crean commits **sin ejecutar `git commit -m`**. **Era una deducción del orquestador y está revocada.** La especificación §6 ya lo decía: *«La aduana es un hook PreToolUse sobre el comando de commit. Intercepta a **todos** los que commitean»*.
>
> Las exenciones son **dos, y solo dos**: el `wip` y el `[NEXT]` del cierre de sesión `[spec §6.7, plan §6.3]`. Ninguna más, y ninguna por forma del comando.
>
> **Y qué hace con cada uno de esos cuatro** `[decisión del propietario, 2026-08-03]`. **Ver pasar no es bloquear:** la aduana los ve todos y decide. El criterio sale de P1, no de una preferencia:
>
> | Comando | La aduana | Por qué |
> |---|---|---|
> | `git commit --amend` | **rechaza** | Reescribe. P1: *«nada se borra ni se reescribe jamás; toda corrección es un commit nuevo»* |
> | `git rebase` | **rechaza** | Reescribe en lote. Su uso legítimo —limpiar la rama— ya tiene mecanismo decidido: el squash al merge `[spec §10.4]` |
> | `git merge` | **pasa** | Añade. Git ya lo registra por existir, y el commit del squash **sí** entra por la aduana como commit de trabajo |
> | `git cherry-pick` | **pasa, a secas** | Añade. Sin confirmación: fricción en una operación rara. Su riesgo real —duplicar el identificador de una nota— ya tiene alarma: el chequeo de IDs duplicados del arranque `[spec §3.1]` |
>
> **El razonamiento de fondo, y es lo que evita leer la decisión al revés:** la regla no es *«todo commit lleva una nota de memoria»*. **Git es el sustrato** `[spec §1, P1]` — un commit de merge ya está registrado por el hecho de existir en la historia. Las notas son **un tipo** de commit, no un peaje que pague todo commit; y el registro del trabajo tiene sus canales propios ya diseñados: el contexto del cierre de sesión `[spec §9]` y la issue del plan `[spec §10.4]`.
>
> **`git pull` deja de ser un agujero** con esta tabla: crea un commit de merge, y merge pasa. Lo levantó Ultron al implementar y se cierra aquí.
>
> **Dos apoyos que se citaron y NO valen como fuente, dicho para que nadie los repita:** *«un rebase borra memoria silenciosamente»* y *«las operaciones git peligrosas siempre confirman»* salen de la auditoría del v1 y del contrato de su skill —**no de una medición ni de una regla heredable**, y la skill del v1 se retira entera. Las conclusiones se sostienen sin ellos: **P1 basta** para rechazar el rebase, y lo de `cherry-pick` es decisión nueva del propietario, no herencia.

<details><summary>El planteamiento original de la pregunta, conservado</summary>

#### `[pregunta]` abierta — bloqueaba `customs.py`, 2026-08-03

**Qué hace la aduana encendida con un commit que no es una nota de memoria** — un `git commit -m "fix: bug"` escrito a mano. **Ningún documento lo dice.**

La spec §6 enumera nueve validaciones y **las nueve son sobre notas**: zonas, árbol de tipos, pregunta del dolor, sustitución, consolidación, keys, wip, acta de plan, errores de git. Ninguna menciona el commit corriente. Y `TEXTOS.md` §1.4 —el rechazo *«no sé qué tipo es esto»*— **no lo cierra**: su texto empieza por `⛔ NOTA RECHAZADA` y su ejemplo es una nota que mezcla dos cosas, no un commit que no pretendía ser una nota.

Las dos salidas son opuestas y ninguna es obviamente la buena:

- **Pasa de largo.** La aduana solo mira lo que dice ser una nota; el commit de código no le concierne. Riesgo: se puede commitear trabajo saltándose `work.py`, y entonces `Touched`/`Issue:` no se registran.
- **Rebota pidiendo `gitmem work`.** La aduana obliga a que todo commit entre por su puerta. Riesgo: con la aduana encendida **no se puede commitear a mano**, ni siquiera un arreglo de una línea, y esa fricción es exactamente la que hace que un sistema se acabe esquivando.

**Hasta que el propietario elija, `customs.py` no se implementa.** El contrato en rojo (`tests/memory/test_customs_hook.py`, 8 tests) ya está escrito y **no cubre este caso a propósito**: rellenarlo con criterio propio sería decidirlo en silencio, que es justo lo que este documento existe para impedir.

</details>

---

## 12. Lo que falta para poder empezar a construir

| Qué | Estado |
|---|---|
| Las fichas de módulo `[recuento tras retirar `dispatch.py` — decisión del propietario, 2026-08-03, B20; eran 23]` — **22 fichas, no 22 ficheros** `[corregido 2026-08-04: en disco hay 31 ficheros en `lib/memory/`, no 22 — `ls lib/memory/*.py \| wc -l` → 31. Faltan nueve fichas, lista debajo de esta tabla]` | **22 escritas** — capas 0 a 4. **Nueve pendientes** |
| Los nueve scripts (más `bin/gitmem`) y los 2 hooks `[recuento tras retirar `inject.py` — B20; eran 3]` | **escritos** — capas 5 y 6 |
| Los tres tests de frontera (puerta 3) y la puerta de aceptación del §13.1 (el mermaid generado) | **especificados, sin construir** `[corregido 2026-08-04 — esta fila y §13/§13.1 los daban por escritos, en presente; verificación debajo de la tabla]` |
| El banco adversarial | **escrito** — §14, pero su único punto de entrada (`gitmem bench`) está borrado; dónde sale ahora su resultado es un `[pregunta]` abierto, ver §14 |
| `[pregunta]` abiertas que bloquean piezas | ninguna — §11.1 la resolvió el propietario el 2026-08-03. Queda una `[pregunta]` en §14 (dónde sale el resultado del banco sin `gitmem bench`), pero no bloquea ninguna pieza: el catálogo de ataques ya corre dentro de §12bis con o sin respuesta |

**Las nueve fichas de módulo que faltan** `[corregido 2026-08-04]`. En disco hay 31 ficheros en `lib/memory/` (verificado: `ls lib/memory/*.py | wc -l` → 31), y esta sección solo llevaba la cuenta de 22. Los nueve sin ficha:

- `format_lines.py` — partición de `format.py` por el techo de 500 líneas `[DEUDA.md punto 12]`; tiene las dos parejas build/parse de la línea de índice y de la línea de archivo. Ver §6.4.
- `health_plans.py` — partición de `health.py` por el mismo techo; tiene `plans_unreflected()`, la red de seguridad de planes sin reflejar. Ver §9.4.
- `notes_commit.py` — partición de `notes.py` por el mismo techo; tiene el candado, la raíz del repo y `write_work`. Ver §8.1 (ya corregida arriba).
- `report_render_note.py` — partición de `report_render.py` por el mismo techo; tiene `render_note()`, el molde del informe por identificador (`TEXTOS.md` §2.4, cierra `DEUDA.md` #24). Ver §9.2/9.3.
- `rezones_commit.py` — **no es una partición por tamaño**, es una pieza nueva: aplica y comitea el plan de `health.rebuild_plan()` sobre los índices reales, cerrando el hallazgo de Moriarty de que `rezones.py --rebuild` reparaba en disco sin comitear nunca (`DEUDA.md` punto 27/28). Ver §9.4.
- `validator_issue.py` — partición de `validator.py` por el mismo techo; tiene `validate_issue`, la única validación de las diez que llama a algo externo (`gh`). Ver §7.5 (ya corregida arriba).
- `validator_pointers.py` — partición de `validator.py` por el mismo techo; tiene `validate_pointers`. Ver §7.5 (ya corregida arriba).
- `validator_zones.py` — partición de `validator.py` por el mismo techo; tiene `validate_zones`. Ver §7.5 (ya corregida arriba).
- `repo_guard.py` — ya señalado como hueco en §10.1, punto 4 (no es una partición por tamaño: es la protección de rama principal, sacada de dentro de `work.py` para que `wip.py` la pudiera compartir sin copiarla).

Ocho de los nueve son particiones por el techo de 500 líneas de una ficha que sí existe — el trabajo es escribir su «por qué se partió» dentro de la ficha del fichero original, no siete fichas nuevas desde cero. `rezones_commit.py` y `repo_guard.py` son las dos excepciones: piezas de verdad sin ficha propia.

**Los tres tests de frontera y la puerta del §13.1, sin construir** `[corregido 2026-08-04]`. §13 y §13.1 los describen en presente, como si corrieran ya — §13.1 llega a decir *«Cuándo corre: con la suite normal, no en una pasada final»*. Verificado: `find unmassk-toolkit/tests -iname "*frontera*" -o -iname "*boundary*" -o -iname "*mermaid*" -o -iname "*graph*"` no devuelve nada, y ningún fichero de `tests/memory/` recorre el grafo de imports real de `lib/memory/` ni genera un mermaid. `DEUDA.md` punto 11 ya lo tenía anotado como no construido — este documento no, hasta ahora. Lo que sigue en §13 y §13.1 es el contrato de lo que hay que escribir, no una descripción de lo que ya vigila.

---

## 12bis. Cómo se construye una capa — la secuencia, y no se abrevia

`[corrección del propietario, 2026-08-02]` — se saltó la mitad de la tubería en la capa 1 y hubo que volver atrás. Queda escrita aquí para que no dependa de que el orquestador se acuerde.

**Una capa no está cerrada cuando sus tests están en verde.** Está cerrada cuando ha pasado esto entero, en este orden:

| # | Quién | Qué |
|---|---|---|
| 1 | **Dante** | Escribe los tests de cada pieza de la capa, **en rojo**, uno por fila del contrato. En paralelo, una pieza por agente |
| 2 | **Ultron** | Implementa hasta el verde. En paralelo, una pieza por agente |
| 3 | **Cerberus + Argus** | **A la vez**, sobre todo el código de la capa. Cerberus: contrato, código muerto, fronteras. Argus: integridad interna — datos perdidos, fallo silencioso, ida y vuelta, plataforma |
| 4 | **Ultron** | Arregla lo que los dos hayan sacado, **de una pasada**. No vuelven a revisar |
| 5 | **Dante** | Endurece los tests con lo aprendido |
| 6 | **Moriarty** | **Intenta romperlo.** Solo ahora, con el código ya revisado, auditado y probado. Ataca el código **y los tests**. **Aquí acaba la capa.** |
| 7 | **Ultron y Dante** | Reparan lo que Moriarty rompió — código él, tests ella |

**Yoda y Alexandria NO entran por capa** `[decisión del propietario, 2026-08-02]`. Yoda juzga **una sola vez, al final de todo**, con el sistema entero delante — no cinco veces sobre trozos. Y la documentación se sincroniza al cierre, no a cada tanda.

**Dos reglas que hacen que esto no se convierta en un bucle infinito:** cada revisor pasa **una vez** por capa; y a Moriarty se le da un encargo **corto**, sin lista de vectores — si se le pre-mastican los ataques, deja de encontrar el que nadie pensó, que es lo único para lo que existe.

**Y el modelo de amenaza no cambia en ningún paso:** no hay atacante externo. Ni Argus ni Moriarty buscan entrada hostil, inyección ni evasión. Buscan que el sistema se rompa **a sí mismo**: memoria perdida, escritura en el sitio equivocado, fallo que pasa callado.

---

## 13. Los tres tests de frontera

**Estado real, 2026-08-04: especificados, sin escribir.** `[corregido — este §13 y el §13.1 de abajo describían los cuatro tests en presente, como si ya corrieran. No es así: verificado `find unmassk-toolkit/tests -iname "*frontera*" -o -iname "*boundary*" -o -iname "*mermaid*" -o -iname "*graph*"` → nada, y ningún fichero de `tests/memory/` recorre el grafo de imports real. `DEUDA.md` punto 11 ya lo daba por no construido — aquí no se decía. Es grave porque el §13.1 es una de las cuatro puertas de aceptación del sistema (§0): dar por corriendo la puerta que cierra el proyecto hace creer que hay algo vigilando cuando no lo hay nadie]`. Lo que sigue es el contrato de lo que hay que escribir — no se borra la especificación, se deja dicho que es eso: contrato, no hecho.

Son la puerta 3 del §2, y no vigilan una pieza: vigilan **la separación entre el sistema de memoria y el toolkit que lo aloja**. Sin ellos, en seis meses volvemos a tener catorce ficheros donde memoria y toolkit conviven sin costura — que es exactamente el estado del que venimos.

**La lista de lo que `lib/memory/` puede importar del toolkit está VACÍA, y es a propósito.** El v2 escribe su propia capa de git, su propio candado, su propio forzado de UTF-8 y sus propios emojis. No importa nada de fuera salvo la biblioteca estándar de Python. Esa decisión ya estaba tomada `[plan §2, restricción A y §3.3]`; aquí solo se convierte en algo que se cae solo.

| Test | Qué comprueba | Qué se rompería sin él |
|---|---|---|
| **Nadie de fuera mira hacia dentro** | Ningún fichero del toolkit fuera de `lib/memory/`, `bin/memory/`, `bin/gitmem`, los 2 hooks y `tests/memory/` importa nada de `lib/memory/` | Un módulo del toolkit acaba dependiendo de la memoria, y el día que quieras borrar el v2 entero no puedes: se lleva por delante el arranque o la instalación |
| **Nadie de dentro mira hacia fuera** | Ningún módulo de `lib/memory/` importa nada del toolkit. Lista permitida: **vacía** | El enredo del v1 otra vez: `sanitize_trailer_value` nació para la memoria y acabó usándola cinco módulos que no eran de memoria, y ya no se puede separar |
| **Nada exportado sin importador** | Toda función pública y todo módulo de `lib/memory/` tiene al menos un importador real dentro del sistema | Las ~590 líneas del v1 que nunca sirvieron para nada — incluida una pieza de 79 líneas con ocho tests en verde que nadie enchufó jamás |

**Contrato: los tres se ejecutan con la suite normal, no aparte** `[siguen sin escribirse — ver el estado real al principio de esta sección]`. Un vigilante que hay que acordarse de lanzar es un vigilante muerto — eso ya pasó con el banco de pruebas del sistema anterior y con el chequeo de la caché.

**Y hay un premio concreto por tenerlos en verde:** con la frontera intacta, el v2 entero se borra con un solo comando y el toolkit ni se entera. Eso es la reversibilidad real del proyecto — no una promesa, una propiedad comprobable en cada ejecución de los tests.

### 13.1 La puerta de aceptación: el grafo se genera, no se dibuja

`[exigencia del propietario, 2026-08-02]` — *«comprueba que las funciones encajen unas con otras, que haya un mermaid o un flow entre ellas que funcione de verdad. Como otra vez haya código muerto, toda la sesión me la he hecho perder.»*

Un cuarto test, y es el que cierra el sistema:

**Recorre el grafo REAL de importaciones y llamadas de `lib/memory/`, dibuja el mermaid a partir de él, y lo compara contra el grafo declarado en `ARQUITECTURA.md` §4. Si no coinciden, falla.**

**Por qué generado y no dibujado:** un diagrama hecho a mano es una promesa — envejece en silencio y nadie lo nota hasta que engaña a alguien. Uno generado del código no puede mentir: o el código encaja como dice el documento, o el test se pone rojo. Es el mismo principio que gobierna todo lo demás aquí, aplicado a la documentación.

**Qué caza este test que los otros tres no:**

| Caso | Por qué se escapa a los otros |
|---|---|
| Dos módulos que se importan en círculo | Cada uno tiene su importador: la puerta del llamador los da por buenos |
| Una dependencia que el documento no declara | Nadie la mira, porque el código funciona igual |
| Una capa que salta a otra que no le toca — el arranque leyendo git directo en vez de pasar por su lector | Funciona, y por eso nadie lo ve, hasta que hay dos lectores del historial y vuelve el fallo del v1 |
| Un módulo declarado en la arquitectura que nunca se escribió | Sale como ausencia, no como error |

**Contrato: cuándo corre — con la suite normal, no en una pasada final** `[sin escribir todavía — ver el estado real al principio del §13]`. Una función exportada que nadie llama tiene que poner la suite en rojo **el día que se escribe**, no tres semanas después — para entonces ya hay código encima y quitarla cuesta diez veces más.

**Y el resultado se enseña**, como todo lo demás de este sistema: el mermaid generado se escribe en el repositorio, así que el diagrama que se lee es siempre el que el código produjo en la última ejecución.

---

---

## 14. El banco adversarial — los diez ataques

**Qué es:** diez intentos de colar una nota mala, lanzados contra la aduana para comprobar que de verdad rechaza lo que dice que rechaza. Corre **en proceso, contra el validador puro, sin escribir un solo commit**.

**Por qué existe:** un vigilante que nadie comprueba acaba sin vigilar. Ya pasó en el sistema anterior — el gate de duplicados corría, pero su aviso no llegaba a ningún sitio donde alguien lo leyera, así que se le escapaba dos de cada tres casos sin que nadie lo supiera durante meses.

| # | El ataque | Lo caza | Responde con | Se da por bueno si | Si NO se rechaza |
|---|---|---|---|---|---|
| 1 | Una nota casi igual a otra de la misma zona, sin declarar sustitución | `validate_replacement` | §1.6 | Las candidatas incluyen la nota vieja, y no hay commit nuevo | Dos notas dicen lo mismo y una búsqueda devuelve dos respuestas sin decir cuál manda |
| 2 | Un muro que nace sin decir de qué incidencia sale | `validate_pointers` | §1.6 (variante de origen) | El rechazo lista **todas** las incidencias candidatas de la zona, no una preseleccionada | Un muro sin cicatriz detrás: nadie puede comprobar si sigue siendo verdad |
| 3 | Una decisión que contradice a otra vigente de la misma zona | `validate_replacement` | §1.6 | Las candidatas incluyen la decisión que contradice | Dos decisiones vigentes se contradicen y nadie sabe cuál manda |
| 4 | Un titular de 96 caracteres | `validate_headline` | §1.11 | El rechazo dice la longitud real y el tope | Los titulares crecen hasta no leerse de un vistazo en el índice |
| 5 | Una zona que no existe | `validate_zones` | §1.1 | El rechazo nombra la zona mala y ofrece parecidas **leídas del fichero real**, no fijas | El fichero de zonas se llena de casi-duplicados y la memoria se parte en dos |
| 6 | Una key marcadora mal escrita (`seguridad`) | `normalize_keys` | §1.8 — **no es rechazo, es aviso** | La nota **SÍ se guarda**, con `security`, y la salida enseña la corrección | Buscar por `security` deja fuera en silencio todo lo guardado como `seguridad` |
| 7 | Una zona de la lista negra (`session`) | `validate_zones` | §1.2 | El rechazo remite a `gitmem rule` | La configuración de trabajo se cuela en la memoria del producto y ensucia toda búsqueda |
| 8 | La palabra ambigua `audit` | `validate_zones` | §1.3 | El rechazo ofrece **las dos** salidas: `registro` y `codeaudit` | Dos cosas sin relación comparten zona para siempre |
| 9 | Un memo que contesta «sí» a la pregunta del dolor | `validate_pain_question` | §1.5 | El rechazo dice que es una R, no una M | Un muro enterrado como memo: deja de salir en los arranques y deja de ser muro |
| 10 | Una destilación sin declarar sus fuentes | `validate_distillation` | §1.7 | El rechazo exige `--origin` | Un resumen del que no se puede volver al original ni comprobar si resume bien |

**Cuándo corre y dónde se ve — `[pregunta]` abierta, 2026-08-03, sin resolver.** Este documento decía *«`gitmem bench` — el subcomando ya estaba reservado»* y que el veredicto salía en la misma línea del arranque que los otros dos chequeos. **Los dos hechos en los que se apoyaba dejaron de ser ciertos:** `bench` se borró entero — *«no lo he autorizado en la vida»* — y con él su único punto de entrada.

**El catálogo de los diez ataques no se pierde.** Sigue siendo material de ataque de Moriarty dentro de la secuencia normal de §12bis (paso 6, «intenta romperlo»), igual que en las capas 1 a 4, que nunca tuvieron banco aparte. Lo que no está decidido es **dónde se ve su resultado**, ahora que no hay comando. No se decide aquí por criterio propio (§0.2) — tres salidas posibles, con lo que pasa en cada una:

- **Vive solo en el informe de la pasada de Moriarty de cada capa.** No deja rastro permanente: si dentro de seis meses alguien pregunta «¿este ataque sigue rechazándose?», hay que ir a buscar el informe de aquella sesión, si es que todavía existe.
- **Se guarda como una fila más del bloque `CHECKS` del arranque** — con su ✓/⚠️ en cada sesión, como `no duplicate IDs` o `indexes match git`. Pero eso reintroduce una ejecución automática y recurrente, que es exactamente lo que era `bench` y lo que el propietario acaba de borrar.
- **No se guarda en ningún sitio.** El catálogo queda como una lista que Moriarty conoce y aplica, sin ningún artefacto que demuestre, sesión a sesión, que se siguió ejecutando.

**Qué NO cubre, dicho explícitamente para que nadie lo lea como más de lo que da:**

- No prueba contra nadie malicioso. Los diez son fallos de uso normal — este proyecto no tiene ese modelo de amenaza.
- No cubre cuatro validaciones que tienen su prueba aparte: no encaja en ningún tipo (§1.4), la issue no existe (§1.9), el cierre de incidencia (§1.10) y la exención del `wip`.
- No prueba los dos hooks en vivo: eso es otro banco, el de §11.
- No comprueba que el generador y la aduana **armen bien** los datos que le pasan al validador. Solo que el validador rechaza cuando esos datos describen uno de estos diez casos.
