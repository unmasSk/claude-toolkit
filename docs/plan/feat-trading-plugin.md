# unmassk-trading — Planteamiento y plan

**Issue:** #85 · **Repo:** trunk (`main`) · **Creado:** 2026-08-27
**Estado:** PLANTEAMIENTO — nada construido. El borrador improvisado del 2026-08-27 está
apartado fuera del repositorio (`scratchpad/draft-cero/`) y no cuenta como trabajo hecho:
entra, como mucho, como material de comparación.

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
3. **El registro y sus estadísticas** — qué funcionó, qué no, y contradecirle con su
   propio historial.

Fuera de todas ellas por ahora: acciones y ETFs (el dato en vivo cuesta dinero),
backtesting, y la idea del juego.

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

### T1 · Traer el código (Ultron + Dante) — sin dependencias
- [ ] Copiar `position_sizer.py` y sus tests, con cabecera de atribución MIT
- [ ] Copiar `check_circuit_breaker.py` y `check_pre_trade_discipline.py` con sus tests
- [ ] Adaptar: euros, cripto 24/7 (no hay "próximo día hábil"), y las comisiones de Kraken
- [ ] Verificación: la suite copiada pasa **antes** de tocar nada, y sigue pasando después

### T2 · El comprobador de precio (Dante contrato → Ultron)

**No hay nada que copiar: ninguna de las 291 skills contrasta dos fuentes ni sella la edad
del precio. Esta se escribe, y por eso lleva contrato en rojo antes que implementación.**
- [ ] Contrato en rojo: dos fuentes, edad de cada precio, discrepancia en puntos básicos,
      veredicto `OK` / `DISAGREE` / `STALE` / `SINGLE_SOURCE`, y **salida distinta de cero
      en los tres malos** para que quien lo llame no pueda ignorarlo
- [ ] Al menos un test contra los dos mercados reales (§34.5)
- [ ] Implementación hasta verde

### T3 · La capa que no existe: modo principiante (orquestador)
- [ ] Evaluación (qué sabe / qué puede permitirse), orden de enseñanza, primera semana,
      puerta de promoción

### T4 · Comparación línea por línea — depende de T1, T2, T3
- [ ] Lo escrito contra las skills equivalentes de los seis repos; huecos y sobras, con cita

### T5 · Auditores — depende de T4
- [ ] Cerberus ∥ Argus → arreglos → Moriarty → arreglos → Yoda, una vez

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
