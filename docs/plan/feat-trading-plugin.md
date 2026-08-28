# unmassk-trading — Planteamiento y plan

**Issue:** #85 · **Repo:** trunk (`main`) · **Creado:** 2026-08-27
**Estado:** **Fase 1 cerrada y publicada.** T1 a T7 hechas. Comparación línea por línea hecha; Cerberus, Argus, Dante, Moriarty y Yoda pasados y todos sus hallazgos corregidos. **Yoda: 87/110, aprobado con tres condiciones, las tres aplicadas.** **[2026-08-27] Consejo celebrado** (cinco asesores y cinco revisores): se publica la fase 1 y el freno se conecta a la cuenta de práctica en vez de borrarse — D-077, con X-086/X-087/X-088 descartadas. **Publicado v1.0.0 el 2026-08-27 y, tras cuatro paseos en frío, v1.0.1 y v1.0.2 el 2026-08-28.** La fase 2 es la #86; la #85 sigue abierta.

---

## 1 · Planteamiento

### El problema real

El propietario no sabe nada de trading y quiere aprender haciéndolo, sin arruinarse por
el camino. No quiere una herramienta de profesional, ni un robot que opere por él: quiere
**un sitio donde preguntar qué está pasando, entenderlo, y dar la orden él mismo**.

Ese usuario no está servido por nada de lo que existe. Está verificado, no supuesto: de
291 skills de trading publicadas en seis repositorios, **ninguna enseña a un principiante
ni evalúa lo que sabe**. Todas dan por sabido el vocabulario entero.

### Qué es esto, en una frase

Un plugin que **lee el mercado en vivo, lo explica al nivel de quien pregunta, calcula lo
que una persona hace mal de cabeza, y ejecuta en Kraken solo cuando el dueño lo ordena.**

### Qué NO es — y esto es la mitad del planteamiento

- **No adivina.** No hay señales de compra, ni objetivos de precio, ni puntuaciones de
  sentimiento. Un modelo no tiene ventaja informativa sobre a dónde va un precio, y
  fingirla es la forma más rápida de que esto haga daño.
- **No opera solo.** Ni en automático, ni programado, ni "mientras duermes" (X-083).
- **No toca una llave con permiso de retirada.** Nunca, ni temporalmente.
- **No es asesoramiento financiero**, y no va a fingir que lo es.

### En qué se apoya, y por qué no se escribe desde cero

Tres piezas ya escritas, todas MIT, todas vivas, todas leídas por dentro:

| Pieza | De dónde | Qué resuelve |
|---|---|---|
| `kraken-cli` | Kraken (oficial) | La cuenta de práctica local, el `--validate` antes de ejecutar, el apagado automático (`cancel-after`), y la lista legible por máquina de qué órdenes son peligrosas |
| `position_sizer.py` + sus tests | tradermonty | La aritmética de tamaño y riesgo, en `Decimal`, sin dependencias, con 647 líneas de test |
| `check_circuit_breaker.py`, `check_pre_trade_discipline.py` + tests | tradermonty | El freno tras un mal día y la puerta previa a la orden, con la semántica correcta: **un dato que falta nunca es un aprobado** |

**Lo que sí se escribe aquí, porque no existe en ningún sitio:** el modo principiante —
evaluar qué sabe, enseñárselo en el orden en que le hace falta, y una puerta medible para
pasar de dinero de mentira a dinero de verdad.

### Las tres reglas que no se doblan

1. **La dirección la decide él.** Lo que produce el plugin es aritmética y hechos.
2. **No se ejecuta nada sin una orden explícita suya en ese turno.** "Vale" no es orden.
3. **La llave nunca puede retirar fondos.**

### Cómo se sabe que está bien hecho

- Cada precio se entrega **con su edad y su fuente**, y contrastado contra un segundo
  mercado. Dos precios que discrepan **se reportan, no se promedian**.
- Cada orden pasa por `--validate` contra el mercado real antes de existir, y se
  **relee** después: nunca se informa de una ejecución desde la respuesta del comando que
  la mandó.
- El simulacro dice en voz alta en qué miente (rellena siempre entero y al instante).
- El registro vive en la memoria del proyecto, no en un segundo diario paralelo.

### Fases — y esta issue es la 1

1. **Leer, entender y practicar** — precios en vivo, modo principiante, cuenta de
   práctica, tamaño y riesgo. *(Esta.)*
2. **Ejecutar de verdad** — llaves recortadas, las cinco vueltas de la orden, promoción.
   **Puerta de entrada a esta fase, decidida el 2026-08-27 tras el veredicto de Yoda: el
   freno tiene que funcionar ANTES de que se mueva un euro.** Hoy el freno por pérdidas lee
   un almacén que este plugin nunca escribe, así que responde «puedes operar» sobre cero
   datos; y su día es el de Nueva York, así que una pérdida cerrada entre las 00:00 y las
   05:00 UTC se contabiliza al día anterior. Mientras no se arreglen esas dos cosas, la
   fase 2 no empieza. Con dinero de mentira no cuesta nada; con dinero de verdad lo cuesta
   todo.
3. **El registro y sus estadísticas** — qué funcionó, qué no, y contradecirle con su
   propio historial. Aquí se retira `thesis_store` y el registro pasa entero a la memoria
   del proyecto — pero la parte que alimenta al freno se adelanta a la fase 2 por la puerta
   de arriba.

Fuera de todas ellas por ahora: backtesting y la idea del juego.

**Acciones, y en concreto el sector de la IA — fase 2.** Es lo que al propietario le
interesa mirar (2026-08-27), y tiene una ventaja real ahí: trabaja en esto y entiende qué
hace cada empresa. Dos hechos que lo colocan en la fase 2 y no en la 1: el dato en vivo de
acciones cuesta unos 99 $/mes mientras que con 15 minutos de retraso es gratis —
suficiente para comprar y mantener, inútil para el minuto—, y **Kraken no lista acciones
tokenizadas** en su catálogo de pares (comprobado el 2026-08-27 contra `AssetPairs`: 1437
pares, ninguno de acciones), así que esa puerta no existe hoy.

---

## 2 · Orden de trabajo

Este es el orden que el propietario fijó el 2026-08-27, y no se abrevia:

```
investigación → plan → planteamiento
   → traer el código (no escribirlo) → comparar línea por línea
   → auditores → CONSEJO → cierre
```

- **Investigación:** hecha. Dos rondas de Bilbo, 291 skills barridas, seis repos leídos
  por dentro. Resultados en M-128 a M-132.
- **Plan y planteamiento:** este documento.
- **Consejo:** `unmassk-council` **al final, sobre el resultado terminado** — decisión
  del propietario el 2026-08-27 («Después»). Juzga algo construido, revisado y roto por
  Moriarty, no una intención.
- **Traer el código:** copiar las piezas MIT con su licencia y su atribución, adaptarlas
  a euros y a cripto 24/7. Nada de reescribir lo que ya está escrito y probado.
- **Comparar línea por línea:** lo nuestro contra las skills equivalentes descargadas.
  Qué dicen ellas que a nosotros nos falta, y qué decimos nosotros que sobra.
- **Auditores:** Cerberus y Argus en paralelo, Moriarty después, Yoda el último.

## 3 · Tareas

### T1 · Traer el código (Ultron + Dante) — **HECHA**
- [x] `position_sizer.py`, `check_circuit_breaker.py`, `check_pre_trade_discipline.py`,
      `thesis_store.py` y `schemas/thesis.schema.json`, byte a byte, con atribución MIT
- [x] Sus tests enteros: **371, todos en verde**, sin tocar una sola comprobación
- [x] Los cinco documentos de esas piezas, también copiados, en `references/lifted/`
- [x] Una única línea de lógica cambiada en todo el traslado (la ruta del módulo hermano),
      declarada en `CREDITS.md`
- [x] Línea trazada: no se sigue tirando del hilo de dependencias (`thesis_review` fuera)
- [x] **La pasada de adaptación NO se hizo, y esa es la decisión:** el traslado se queda byte a byte, así que las etiquetas en dólares y "shares", el calendario de mercado estadounidense y las rutas de salida relativas al directorio actual **se documentan en vez de tocarse** — `SKILL.md` las declara una por una, los bloques pasan siempre `--output-dir`/`--state-dir` explícitos, y `.gitignore` protege la raíz del repositorio por si alguien los omite. El límite del día en Nueva York es lo único que sigue vivo, y es parte de la puerta de la fase 2 (#86)

### T2 · El comprobador de precio — **HECHA**

**Corregido el 2026-08-27 tras la comparación línea por línea:** la afirmación original
—«nada de las 291 contrasta dos fuentes»— era medio falsa. `agiprolabs/ohlcv-processing/
scripts/merge_sources.py` (491 líneas) sí reconcilia dos fuentes, y su propia
documentación fija el dato útil: **dos fuentes pueden discrepar legítimamente entre 0,1% y
2%** en cripto. Lo que no existe en ninguna es **sellar la edad del precio**, y su enfoque
es el contrario al nuestro: ellos *eligen ganador* (prefieren la fuente con más volumen),
que es justo lo que `honest-advice.md` prohíbe. El nuestro se escribe igualmente, y se
escribió.
- [x] Contrato en rojo: 62 tests, con los cuatro veredictos y salida distinta de cero en
      los tres malos
- [x] Dos tests contra los dos mercados reales (§34.5) — y uno de ellos cazó un fallo real
      (el reloj se muestreaba antes de las respuestas y el programa declaraba viejo su
      propio dato fresco)
- [x] Implementación hasta verde: **433 tests**

### T3 · La capa que no existe: modo principiante — **HECHA**
- [x] Evaluación (qué sabe / qué puede permitirse — esta usa el cuestionario levantado),
      orden de enseñanza, primera semana y puerta de promoción

### T4 · Comparación línea por línea — **HECHA**
- [x] Hecha: cazó cinco cosas que habrían roto una sesión (invocaciones de los frenos que
      no arrancaban, un «fallan a gritos» falso, una salida «verificada» inventada, la zona
      inexistente de las notas, y la skill buscándose a sí misma con un guión de más)

### T5 · Auditores — **HECHA**
- [x] Cerberus (7 issues) ∥ Argus (10 hallazgos) → arreglos → Dante (645 tests, 100% de
      cobertura medida) → Moriarty (FALLA: 6 roturas, 5 engaños) → arreglos → Yoda: 87/110

### T6 · Consejo — **HECHA**
- [x] `unmassk-council` sobre el plugin terminado. Los cinco asesores coincidieron en
      publicar quitando el freno roto; los cinco revisores, por separado, encontraron el
      mismo agujero en esa unanimidad y la presidencia la rechazó: **se publica la fase 1 y
      el freno se conecta a la cuenta de práctica, que ES el dato de pérdidas** (D-077).
      Descartadas: borrarlo y dejar un aviso impreso (X-086), retener la publicación hasta
      que funcione (X-087), y dejarlo tal cual recogiendo datos (X-088)
- [ ] **Lo que el Consejo deja abierto:** el wrapper que conecta freno y cuenta de práctica —y el límite del día en UTC— no está construido. Es la fase 2, y desde el 2026-08-27 tiene issue propia: **#86**. Verificado el 2026-08-28 que sigue abierto: `thesis_store.py` publica `open-position`, `trim`, `close` y `terminate`, pero **no un comando que cree una ficha**, así que no hay camino de «el usuario compró algo» a «el freno lo sabe»

### T7 · Documentación y cierre — **HECHA**
- [x] Alexandria: tres superficies + CHANGELOG (tres entradas: 1.0.0, 1.0.1 y 1.0.2)
- [x] Suites en verde: **689 del plugin y 1.285 del toolkit, vueltas a correr el 2026-08-28**; CI verde en los dos trabajos de `plugin-tests.yml`. `unmassk-trading` estrena trabajo propio para que la dependencia pesada de otro plugin no pueda esconder su resultado, y el trabajo de los plugins maker llevaba roto desde el 2026-08-06 **sin que nadie lo viera**, porque un filtro de rutas impedía que llegara a ejecutarse: fijaba Python 3.10 y dos de sus propias dependencias piden 3.11+ (M-133)
- [x] Validadores de plugin-dev pasados: cazaron que **ninguno de los comandos habría funcionado instalado** (rutas relativas) y el punto muerto de la puerta
- [x] **Cuatro paseos en frío** —un Claude leyendo la skill en un proyecto vacío, sin memoria, sin configuración y sin el binario `kraken`, sacando cada bloque y ejecutándolo— encontraron por orden: todas las invocaciones rotas por las rutas, el directorio de práctica apuntando a donde no era, la lista de órdenes peligrosas leyendo el fichero de otro proyecto, las puertas sin usarse nunca en modo principiante, y una instrucción de `session start` que no devuelve el control. Corregidos en 1.0.1 y 1.0.2
- [x] **R-018 quedó retirada y sustituida por R-019:** el arreglo de la 1.0.1 —invocar los scripts con `${CLAUDE_PLUGIN_ROOT}`— era falso, porque esa variable está vacía en la herramienta Bash y solo se sustituye en las entradas de `hooks.json`. Hoy cada bloque resuelve la ruta de la skill en la misma llamada que la usa, y se copia entero
- [x] Publicado v1.0.0 el 2026-08-27, y con los arreglos v1.0.1 y v1.0.2 el 2026-08-28
- [x] #85 sigue abierta: esto cierra la fase 1, no la issue

**Status: COMPLETED** (fase 1; la fase 2 es la #86)

## 4 · Lo que estaba sin decidir — **[2026-08-27] las tres decididas**

1. **¿`kraken-cli` como base, o REST directo?** El binario da gratis el simulacro, el
   `--validate` y el apagado automático; a cambio, una dependencia en Rust y un contrato
   ajeno que se mueve. → **`kraken-cli`** (D-076).
2. **¿Qué es "en directo"?** Precio fresco al preguntar (barato, suficiente) o una cinta
   grabada en continuo (más piezas, más que puede fallar en silencio). → **fresco al
   preguntar, sin demonio propio** (D-076): un demonio nuestro escribiendo a un fichero es
   justo la pieza que falla en silencio cuando nadie mira.
3. **¿El modo se pregunta o se deduce?** Preguntarlo es honesto; deducirlo de lo que sabe
   contestar evita una pregunta de burocracia el primer día. → **se pregunta una vez y se
   guarda** (D-075).
