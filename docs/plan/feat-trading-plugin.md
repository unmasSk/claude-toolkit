# unmassk-trading — Planteamiento y plan

**Issue:** #85 · **Repo:** trunk (`main`) · **Creado:** 2026-08-27
**Estado:** T1 a T5 cerradas. Comparación línea por línea hecha; Cerberus, Argus, Dante,
Moriarty y Yoda pasados y todos sus hallazgos corregidos. **Yoda: 87/110, aprobado con tres
condiciones, las tres aplicadas.** Quedan el Consejo (T6) y el cierre (T7).

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
- [ ] **Pendiente de la pasada de adaptación:** etiquetas en dólares y "shares", calendario
      de mercado estadounidense, y rutas de salida relativas al directorio actual

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

### T6 · Consejo — depende de T5
- [ ] `unmassk-council` sobre el plugin terminado: cinco asesores, y lo que salga se aplica

### T7 · Documentación y cierre — depende de T6
- [ ] Alexandria: tres superficies + CHANGELOG
- [ ] Suite entera en verde, commit y push en `main`
- [ ] #85 sigue abierta: esto cierra la fase 1, no la issue

## 4 · Lo que está sin decidir — lo decide el orquestador ahora, y el consejo lo revisa al final

1. **¿`kraken-cli` como base, o REST directo?** El binario da gratis el simulacro, el
   `--validate` y el apagado automático; a cambio, una dependencia en Rust y un contrato
   ajeno que se mueve.
2. **¿Qué es "en directo"?** Precio fresco al preguntar (barato, suficiente) o una cinta
   grabada en continuo (más piezas, más que puede fallar en silencio).
3. **¿El modo se pregunta o se deduce?** Preguntarlo es honesto; deducirlo de lo que sabe
   contestar evita una pregunta de burocracia el primer día.
