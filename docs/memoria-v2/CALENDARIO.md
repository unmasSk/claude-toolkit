# Calendario de construcción — qué va en paralelo y qué no

**Para qué:** que el orden de ejecución no se decida sobre la marcha. Cada tanda dice qué piezas van **a la vez** y qué tiene que estar cerrado antes. Se sigue sin preguntar.

**La regla que fija el orden:** dos piezas van en paralelo si **ninguna importa a la otra**. Todo lo demás es secuencial. Sale del grafo de `ARQUITECTURA.md` §4, no de una intuición.

**Y cada capa se cierra con la secuencia de `PIEZAS.md` §12bis** — Cerberus y Argus a la vez, Ultron arregla, Dante endurece, **Moriarty rompe, y ahi acaba la capa**.

**Yoda no entra por capa: juzga UNA sola vez, al final de todo**, con el sistema entero delante. Y la documentacion se sincroniza al cierre, no a cada tanda. (Decision del propietario, 2026-08-02.)

---

## Estado

| | Piezas | Estado |
|---|---|---|
| **Capa 0** | `utf8` · `emojis` · `model` | ✅ construidas |
| **Capa 1** | `vocabulary` · `zones` · `config` · `format` · `similar` | ✅ construidas · **revisión completa** (Cerberus, Argus y Moriarty) |
| **Capa 2** | `gitcmd` · `ids` · `indexes` · `rejection` · `validator` | ✅ **cerrada 2026-08-04 — secuencia completa.** Moriarty dio FALLA: un puntero `Origin` mal escrito (`d-030`) se colaba sin comprobar y la nota quedaba enlazada a nada. Reparado y verificado |
| **Capa 3** | `notes` · `query` | ✅ **cerrada 2026-08-04 — secuencia completa.** Moriarty dio DÉBIL: `write_work()` rechazaba un commit legítimo culpando a un proceso inexistente. Reparado y verificado |
| **Capa 4** | `clusters` · `report` · `report_render` · `health` · `context` · `rules` · `boot` | ✅ construidas · **revisión completa**. *(`dispatch` se retiró entera — decisión del propietario, 2026-08-03, B20.)* |
| **Capa 5** | 10 scripts + la fachada `gitmem` | ✅ **cerrada 2026-08-04 — secuencia completa con el reparto nuevo.** Cerberus y Argus sacaron dos cosas (el alta de zona que pisaba la anterior, el aviso de regla repetida que no existía) y **Moriarty encontró dos más que a ellos se les escaparon**: una nota guardada con el alias de una zona quedaba **invisible para siempre**, y el comando de relanzamiento de un rechazo no era ejecutable tal cual. Todo reparado y verificado |
| **Capa 6** | 2 hooks *(`inject.py` retirado entero — decisión del propietario, 2026-08-03, B20)* | ✅ construidos y con test **[comprobado 2026-08-03, tras B20: `customs.py` · `boot_launcher.py` existen en `unmassk-toolkit/hooks/`, `pytest unmassk-toolkit/tests/memory/test_customs_hook.py unmassk-toolkit/tests/memory/test_boot_launcher.py -q` → 29 passed]**. **Sin enchufar en `hooks.json` a propósito:** engancharlos mientras el sistema viejo sigue vivo dispararía dos arranques a la vez. Falta apuntarlos — `DEUDA.md` punto 26 |

**Actualizado el 2026-08-03.** La capa 5 cerró su secuencia entera: Cerberus y Argus sacaron seis cosas, y **Moriarty encontró una más que a los dos se les escapó** — el identificador de una nota cerrada se reasignaba a la siguiente, dejando dos notas distintas marcadas igual en git para siempre. Es el tercer cierre de capa seguido en que la última pasada encuentra algo que las dos anteriores dieron por bueno. **261 tests en verde.**

**[decisión del propietario, 2026-08-03, posterior a ese cierre]** — el reparto de diez scripts que la capa 5 cerró esa mañana ya no es el vigente: `close`→`remove`, `context`→`next`, `reindex`→`rezones` (tres renombres), **`bench` se borra entero** («no lo he autorizado en la vida»), y nace `wip` (el checkpoint, que hoy ningún comando escribía). La cuenta sigue en diez —uno sale, uno entra— pero no son los mismos diez que pasaron Cerberus/Argus/Moriarty por su nombre viejo. Detalle y por qué en la Tanda 5, más abajo.

> **Las capas 2 y 3 quedaron cerradas el 2026-08-04. Este aviso llevaba abierto desde el principio de la obra y ya no aplica** `[cerrado 2026-08-04]`**.**
>
> Eran **anteriores a todo lo construido encima**, y por eso este documento avisaba de que se estaba edificando sobre una capa sin cerrar. Lo que las desbloqueó fueron dos cosas del mismo día:
>
> - **El eje de la concurrencia salió de en medio, y no por un arreglo.** El propietario respondió a la pregunta que llevaba esto parado desde el 2026-08-02 — **«no va a pasar nunca»** —, así que los puntos **27**, **28** y el hallazgo del intruso se cierran como **caso descartado**, igual que el repositorio anidado (B7/punto 25). Ver `DEUDA.md` PARTE 1, **B22**.
> - **Con ese eje fuera, Moriarty gastó la pasada entera en lo que sí puede pasar** — y encontró **una cosa por capa**, las dos reales, las dos que cuatro revisores anteriores habían dado por buenas. Reparadas y verificadas ejecutándolas. Detalle en `DEUDA.md` punto **13**.
>
> **Es la cuarta vez seguida que la última pasada encuentra algo que las dos anteriores aprobaron.** Capa 1, capa 4, capa 5, y ahora las capas 2 y 3. La secuencia de §12bis no se abrevia, y esta es la cuarta demostración.
>
> **Y hubo una quinta el mismo día**, al reejecutar la capa 5 con el reparto nuevo: Cerberus y Argus sacaron dos cosas, y Moriarty encontró **una nota que se guardaba con el alias de una zona y quedaba invisible para siempre** — confirmación de éxito, cero errores, y ninguna búsqueda por zona la encontraba jamás.
>
> **Y una sexta, que no salió de ningún agente:** el tercero de los tests de frontera (`PIEZAS.md` §13), nada más escribirse, destapó que **`note.py --replaces` no archivaba la nota vieja** — dos decisiones vigentes contradiciéndose, que es literalmente el fallo que `replace()` existe para impedir. Cuatro revisores habían dado esa capa por buena. **Un vigilante automático encontró en un minuto lo que la revisión humana no vio en dos días, y además no depende de que nadie se acuerde de mirarlo.**
>
> *(La versión anterior de este aviso decía que `write_work()` commiteaba **sin candado**. Dejó de ser cierto el 2026-08-03 —el candado está en el código— y el aviso se quedó sin corregir. Se anota porque es el mismo defecto que este documento existe para cazar: un dato escrito en presente que ya no lo era.)*

---

## Las tandas

### Tanda 2a — cuatro en paralelo *(cerrada)*
`gitcmd` · `ids` · `indexes` · `rejection`

Ninguna importa a otra. `indexes` usa `format`, ya construido.

### Tanda 2b — una sola
`validator`

**No puede ir con las anteriores:** importa `vocabulary`, `zones`, `similar`, `config` y `rejection`. Es la pieza que sostiene el diseño — la única implementación de «esto es válido» — y va sola a propósito.

→ **Cierre de capa 2:** la secuencia completa de §12bis sobre las cinco piezas.

### Tanda 3 — dos en paralelo
`notes` · `query`

`notes` es **la transacción**: nota e índice en el mismo commit, o ninguno de los dos. Es donde el sistema se puede corromper a sí mismo, y por eso su revisión es la más seria de todas.
`query` es **el único lector del historial**. En el sistema viejo esto estaba escrito tres veces.

→ **Cierre de capa 3:** secuencia completa.

### Tanda 4a — cuatro en paralelo *(siguiente)*
`clusters` · `context` · `rules` · `health`

Ninguna importa a otra. `clusters` solo necesita `model`; `context` y `rules` solo `gitcmd` y `format`; `health` lee por `query`, ya construido.

*(`dispatch` iba en esta tanda — retirada entera, decisión del propietario, 2026-08-03, B20.)*

### Tanda 4b — dos, en fila
`report` → `report_render`

El segundo consume lo que produce el primero. **No pueden ir a la vez.**

### Tanda 4c — una
`boot`

Compone lo que producen `context`, `health` y `query`. Va cuando esos tres están.

→ **Cierre de capa 4:** secuencia completa.

### Tanda 5 — once en paralelo
Los diez scripts y la fachada.

**[decisión del propietario, 2026-08-03]** — el reparto de scripts que se construyó y revisó esa misma mañana cambia por la tarde: `close`→`remove`, `context`→`next`, `reindex`→`rezones`; **`bench` se borra entero**; nace `wip`. La cuenta de diez no se mueve (uno sale, uno entra), pero el conjunto no es el mismo: los renombres y el borrado de `bench` están **«en marcha»** (`DEUDA.md` PARTE 1, punto 2) y `wip` **todavía no existe** (mismo punto, entrada 3). El cierre de esta tanda no se da por bueno con los nombres viejos: hay que reejecutar Cerberus/Argus/Moriarty sobre los scripts renombrados y sobre `wip`, que no pasaron por nadie todavía.

Son piezas finas: reciben argumentos, llaman a **una** función de la librería e imprimen. Si uno crece, es que se le está colando lógica que pertenece a un módulo.

→ **Cierre:** secuencia completa de §12bis.

**Ya no incluye un banco adversarial aparte.** El `bench` que lo lanzaba está borrado, y con él el principio P12 de la especificación, que lo exigía como invariante automático con ejecución sola y resultado visible — el propietario nunca lo autorizó. El catálogo de los diez ataques que Dante escribió (duplicado, sin enlace, decisión que contradice, titular largo, zona inventada, key mal escrita, zona prohibida, `audit`, memo que era muro, destilación sin fuentes) no se pierde: sigue siendo el material de ataque de Moriarty dentro de la secuencia normal de §12bis, igual que en las capas 1 a 4, ninguna de las cuales tuvo nunca un banco aparte.

### Tanda 6 — dos en paralelo, y es la última
`customs` · `boot_launcher`

**Van al final por una razón operativa medida:** los hooks corren desde la copia instalada del plugin, así que cambiar uno exige publicar versión, actualizar y reiniciar. **No se pueden desarrollar iterando.** Todo lo que pueda ser script por ruta va antes — y por eso solo hay dos.

*(`inject` iba en esta tanda — retirada entera, decisión del propietario, 2026-08-03, B20: cada agente busca su propia memoria de proyecto, ya no hace falta un hook que se la reparta.)*

→ **Cierre:** secuencia completa + las cuatro puertas de aceptación (§13 y §13.1), incluido el grafo generado del código.

---

## Y solo entonces, el final de todo

Con las seis capas cerradas: **Yoda**, una vez, sobre el sistema entero. Después, la documentación al día.

---

## Lo que NO se paraleliza nunca

- **Dos piezas donde una importa a la otra.** Es toda la regla.
- **Revisar un fichero mientras alguien lo escribe.** El informe nace caducado. Revisar la capa 1 mientras se construye la 2 **sí vale** —son ficheros distintos y nadie escribe encima—, y es lo que se está haciendo ahora.
- **Dos agentes sobre el mismo fichero.** Ni siquiera para leerlo y escribirlo.

## Lo que sí, siempre

- **Los tests de una tanda se escriben todos a la vez**, antes de implementar ninguna.
- **Las implementaciones de una tanda, todas a la vez**, una pieza por agente.
- **Ningún agente escribe en `lib/memory/` fuera de su propio fichero**, ni siquiera un temporal — ya costó un incidente.
