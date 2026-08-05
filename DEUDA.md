# Deuda — lo que está roto a propósito y hay que reparar antes de cerrar

**Abierto:** 2026-08-02 · **Rama:** `feat/memoria-v2` · **Última revisión completa:** 2026-08-03 (cada punto reejecutado, no fiado de lo reportado)

Durante la construcción del sistema de memoria v2 se han roto cosas **a sabiendas**, porque repararlas en el momento costaba más que dejarlas y arreglarlas en su fase. La regla que lo permite es del propietario: *«mientras todo se pueda arreglar, no hay problema»*. La condición es esta lista.

**Cómo se usa:** antes de fusionar la rama, se repasa entera. Nada se marca hecho sin comprobarlo — el comando de verificación está en cada punto para que no haya que fiarse de la memoria de nadie.

---

# PARTE 1 — LO QUE BEX HA DECIDIDO

**Esta parte existe porque casi todo el sistema se diseñó sin preguntarle.** El 3 de agosto se descubrió: los nombres de los diez comandos, los siete tipos de nota y que la nota vaya sin código salieron de una sesión de Claude y quedaron escritos en `PLAN-CONSTRUCCION.md` §1 bajo el título *«Las siete decisiones, resueltas por el propietario»* — **sin haberlo sido**. En la especificación, que sí está cerrada con él, la palabra `gitmem` no aparece ni una vez.

Aquí se anota **lo que decide él**, con su fecha y sus palabras. Nada se rellena por criterio propio.

> **Qué significa cada marca, porque no son lo mismo y confundirlas ya pasó** `[2026-08-03]`:
>
> | Marca | Significa |
> |---|---|
> | **`[x]`** | **Decidido Y construido.** Está en el código y hay tests que lo vigilan. **25 de las 34.** |
> | **`[~]`** | **Decidido, sin construir todavía.** La decisión es firme; el código no existe. **9 de las 34.** |
>
> **Las nueve que faltan por construir, contadas una a una el 2026-08-04.** Las seis primeras son de la fase 7; las tres últimas —**B32**, **B33** y **B34**— se decidieron el 2026-08-04 hablando y **añaden trabajo nuevo**: la skill de destilación y el prompt del cierre son fase 7 (pasos **7.13b**, **7.13c** y **7.13d**, nuevos), y la cascada de rondas es fase 8. **B2** (la aduana deduce sola si es nota o trabajo) · **B3** (el rechazo de `amend`/`rebase` tiene que dar la salida) · **B13** (el saludo tras el arranque, con emojis por sección) · **B15** (la doble confirmación de los comandos que borran trabajo) · **B18** (la cadena de montaje con workflows) · **B20** (los tres pasos de memoria en los prompts de los nueve agentes).
>
> **Ninguna está bloqueada por una pregunta pendiente.** La última que lo estaba —**B24**, el aviso de regla repetida— se desbloqueó el 2026-08-04 cuando el propietario delegó el texto, y está construida.
>
> Hasta hoy las diecinueve llevaban `[x]`, y una de ellas —la B2— tenía un `[x]` en el título y un *«falta construirlo»* tres líneas más abajo. **Un visto bueno que hay que leerse el párrafo entero para desmentir es exactamente el fallo que este sistema existe para impedir.**
>
> **Y el recuento estaba mal contado** `[corregido 2026-08-04]`: esta tabla decía «de las 19» cuando las entradas escritas eran **21** (B1 a B21, sin hueco). Con **B22**, añadida hoy, son **22**. El documento que dice cuánto falta no puede contar mal — es el mismo defecto que se corrige más abajo en la PARTE 2, donde el recuento hablaba de 27 puntos habiendo 28.
>
> Ojo, porque en la **PARTE 2** la misma marca significa otra cosa: allí `[x]` es **«roto y ya arreglado, con su comprobación ejecutada»**.

### [x] B1 · La nota y el código siguen separados — 2026-08-03

`note` guarda la nota, `work` guarda el código. **Se queda como está.**

Corrección al pasar: se dijo que el sistema viejo los guardaba juntos y **es falso**. Medido sobre los 1.818 commits: solo **6** llevan código y decisión a la vez, **0** llevan código y memo, y de los 1.013 `Why:` escritos solo **2** viajaban con código. El script lo permitía; nadie lo usó así.

### [~] B2 · La aduana deduce sola cuál de los dos es — 2026-08-03

> *«Si hay código modificado, pues es `work`. Y si no hay código modificado, si es una nota, pues `note`.»*

Se mira el diff. Nadie lo declara. **Falta construirlo.**

### [~] B3 · `amend` y `rebase`: el rechazo tiene que dar la salida — 2026-08-03

**Opción A para los dos.** Hoy rechaza diciendo *«esto reescribe historia»* y ahí te deja, incumpliendo la regla del propio sistema, que exige el comando exacto para relanzar `[PIEZAS §7.4]`. El rechazo debe decir qué hacer: mensaje equivocado → se sustituye con una nota nueva; fichero olvidado → otro commit encima; limpiar la rama → el squash al fusionar `[spec §10.4]`.

Los dos **cambian el mensaje Y el código**: `--amend` mete ficheros en un commit ya cerrado como si hubieran estado desde el principio; `rebase` reescribe los commits enteros y al resolver conflictos cambia el código.

### [x] B4 · Cuatro comandos cambian de nombre, uno se borra, uno nace — 2026-08-03

| Antes | Ahora |
|---|---|
| `close` | **`remove`** |
| `context` | **`next`** |
| `reindex` | **`rezones`** |
| `bench` | **borrado** — *«no lo he autorizado en la vida»* |
| *(no existía)* | **`wip`** — el checkpoint: `gitmem wip "mensaje"` |

**El checkpoint era un agujero:** el validador sabía reconocerlo y eximirlo de toda pregunta, pero **ningún comando lo escribía**. Puerta abierta sin llave. En el sistema viejo se usó **208** veces.

Y el arranque **deja de ser un subcomando**: *«ese comando no quiero que se use, tiene que ser automático, como se hacía antes»*. Se dispara solo al abrir sesión y **escribe un documento que Claude lee entero** — no una inyección, que tiene tope de tamaño.

**El sistema queda en nueve comandos:** `note` · `work` · `wip` · `remove` · `next` · `search` · `zones` · `rezones` · `rule`.

### [x] B5 · La forma del cierre de sesión — 2026-08-03

Corchete `[NEXT]` literal, su emoji, y el título de lo que toca mañana. Debajo, `Context:` con **un resumen en prosa de TODA la sesión** — lo que se habló, lo que se decidió, lo que se rompió, lo que quedó a medias, y los cabreos con su motivo. **No es un acta de lo construido** (para eso están los commits): es lo que se habló y no vive en ningún otro sitio.

El ejemplo que él aprobó queda como molde en `TEXTOS.md` §5.

### [x] B6 · El informe de una nota por su identificador — 2026-08-03

Molde dictado por él, escrito en `TEXTOS.md` §2.4. Cierra el punto **24**.

### [x] B7 · El repositorio anidado: no se arregla — 2026-08-03

> *«Nunca voy a trabajar en submódulos. Olvídalo ya.»*

Cierra el punto **25**. Los 3 tests se retiran. Comprobado además que `chatroom` **no es un submódulo**.

### [x] B8 · Tres capacidades del sistema viejo — 2026-08-03

| Capacidad | Decisión |
|---|---|
| Rescatar el contexto antes de que se comprima la conversación | **Fuera** — *«no se cumple nunca»* |
| La compactación periódica y las coronas | **Fuera** |
| La búsqueda difusa por texto libre | Se acepta la pérdida — *«que busque cuatro veces, ya está»* |

### [x] B9 · «Valla» pasa a llamarse «muro» — 2026-08-03

141 apariciones en 27 ficheros, con la concordancia rehecha frase a frase. **Hecho.** El criterio que deja: **si una palabra que sale a diario no se entiende, se cambia.**

Y su emoji pasa de `⚠` a **`⚠️`** — el mismo carácter con el selector de variante, porque el primero se pinta plano y no parece un emoji.

### [x] B10 · `rule` se queda con ese nombre — 2026-08-03

*«Hubiera preferido remember, pero como habría que cambiar muchas cosas, vale.»* Anotado por si se revierte.

### [x] B11 · Las etiquetas van en inglés — 2026-08-03

> *«Deja de poner cosas en español cuando son en inglés. No hablo del título ni de la descripción: hablo del resto — recuentos, avisos, restricciones.»*

`RECUENTOS`→`COUNTS` · `AVISOS`→`CHECKS` · `RESTRICCIONES`→`RESTRICTIONS` · `BLOQUEANTES`→`BLOCKERS` · `espera:`→`awaits:` · `MEMORIA`→`MEMORY`, y así en todo. **Solo el contenido explicativo sigue en castellano.**

### [x] B12 · El aviso de coherencia, con notas archivadas — 2026-08-03

Hoy imprime dos números que no cuadran y nadie explica. Pasa a desglosarse:

```
✓  indexes match git (68 lines / 68 notes)                    ← sin archivadas
✓  indexes match git (587 live + 25 archived / 612 notes)     ← cuando las hay
```

### [~] B13 · Cómo me comunico yo con él tras el arranque — 2026-08-03

> *«No me puede ser tan breve. Con seis preguntas abiertas, yo no me entero de nada. Esto es un fallo gordísimo.»*

El saludo de después del arranque **no es un resumen de tres líneas**: lleva el Next con lo que pasó ayer, los bloqueantes **con fecha si la tienen**, las preguntas abiertas **diciendo cuáles bloquean trabajo**, las incidencias, los planes con commits sin reflejar, y los muros que apliquen a lo de hoy. **Con emojis por sección** —los mismos del sistema— para distinguir las partes de un vistazo. El molde queda en `TEXTOS.md`.

### [x] B14 · Las reglas: `user` por defecto — 2026-08-03

> *«Las reglas son reglas, da igual quién las escriba.»* Si no se dice de quién es, se guarda como suya. **Sin rebote.**

### [~] B15 · Los comandos de git que borran trabajo — 2026-08-03

**La regla, y es una sola:** los comandos que pueden hacer desaparecer trabajo **no se bloquean — obligan a preguntarle a él**, enseñando exactamente qué desaparece. Son `reset`, `restore`, `checkout <fichero>`, `clean`, `stash`, `branch -D` y `push --force`.

**Y la confirmación es suya, no mía.** El rechazo que le llega a Claude dice literalmente *«no puedes confirmarlo tú: pregúntale al usuario y espera su respuesta»*, con el texto ya redactado. Claude se lo traslada, y **por duplicado**: tras el primer sí, se le repite en una línea lo que se va a perder antes de ejecutar. Dos síes, no uno.

Para subir y bajar cuando las dos copias han cambiado por separado, el aviso lleva además **cuántos commits hay a cada lado**, porque *«esos son los únicos que me preocupan»*.

### [x] B16 · El `merge` sigue con sus dos revisores — 2026-08-03

Pasa la aduana, pero antes tiene que pasar por el guardián que ya existe: **Cerberus** sobre el diff y **Alexandria** para el changelog. Y por la protección de rama: a `main` o `staging` no se fusiona directo.

Ese guardián es del sistema viejo y **sobrevive**. Arrastra un defecto que hay que arreglarle: **bloquea por leer la palabra «merge» dentro de un texto cualquiera** — frenó una nota de memoria que la llevaba en su descripción.

### [~] B18 · La cadena de montaje se orquesta con workflows — 2026-08-03, **a probar en la fase 7**

> *«Mételo en el punto 7, que hay que hacer las skills. Metes ahí en el flow lo del dynamic workflow y lo investigamos, hacemos pruebas y tal, cuando llegue ese punto.»*

**Qué gana la skill de flow con esto.** Hoy sus ocho pasos los ejecuta el orquestador a mano: lanza un agente, espera, lee, decide el siguiente. **El orquestador es el cuello de botella de su propio guion.** Escrito como workflow, la cadena se define una vez y corre sola:

- **Lo que hoy va en fila porque el orquestador solo mira una cosa a la vez, iría a la vez de verdad.** Y en cascada, no por etapas: en cuanto una pieza termina sus tests, **esa** empieza a implementarse sin esperar a las demás. Con cinco piezas y tres pasos, la diferencia entre esperar al más lento de cada etapa y esperar a la pieza más lenta de punta a punta es enorme.
- **La secuencia deja de depender de que alguien se acuerde.** `PIEZAS.md` §12bis existe precisamente porque *«se saltó la mitad de la tubería en la capa 1 y hubo que volver atrás»*. Un guion escrito no se salta pasos.
- **Y el que junta al final.** Hoy el orquestador lee cinco informes y algo se le escapa. Un agente cuyo único trabajo es cruzarlos ve lo que ninguno vio solo — que es donde han aparecido los fallos gordos de estos días.

**Lo que NO cambia:** dos agentes no pueden escribir el mismo fichero a la vez. Eso va en fila sí o sí, y ya está escrito en `CALENDARIO.md` porque costó un incidente.

**Vale igual para `unmassk-audit`** (14 pasos) y para el protocolo de cierre de sesión. **Se prueba en la fase 7, no antes.**

Y la regla que deja para el orquestador, anotada aparte porque es de conducta: **el coste en agentes no es criterio para decidir cómo se orquesta.** Se descartó usar workflows por caros sin preguntarle. *«¿A ti qué te importa? Si tengo la versión más bestia.»*

### [x] B17 · Los siete tipos de nota se quedan — 2026-08-03

Dados por buenos. Sus nombres van en inglés (`decision`, `memo`, `restriction`, `question`, `discarded`, `incident`, `blocker`), como todo lo mecánico.

### [~] B20 · La memoria no se inyecta: el agente la busca él — 2026-08-03

> **«Se supone que Claude le tiene que dar el contexto a la gente. ¿Por qué necesitamos inyectarle mierda de memoria? En su prompt le dices que lo primero que tiene que hacer es investigar en la memoria lo que tiene que ver con el campo que va a tocar. Si va a mirar el archivo X, que busque el historial: cuándo y por qué se ha modificado. Y dado que eso le va a decir la zona, que busque los muros de esas zonas.»**

**Sustituye a la fase 5 entera.** En vez de un vigilante que intercepta cada encargo, adivina la zona del texto y le pega memoria dentro, **cada agente lo hace él solo, en tres pasos, escritos en su prompt**:

1. **El historial del fichero que va a tocar** — cuándo se cambió y por qué.
2. **De ahí sale la zona**, sin adivinarla.
3. **Los muros de esa zona**, que son los que pueden pararle.

**Y es mejor que lo que había**, no solo más simple: el agente busca **el fichero que de verdad va a tocar**, no la zona que alguien dedujo de las palabras del encargo. La zona deducida era, además, el punto débil declarado del diseño viejo — tenía un texto entero para el caso de «no se pudo determinar».

**Qué se cae con esto:**

| Pieza | Qué pasa |
|---|---|
| `hooks/inject.py` | **se retira** — el vigilante que interceptaba los encargos |
| `lib/memory/dispatch.py` | **se retira o encoge mucho** — la tabla de qué ve cada oficio |
| Los pasos 5.1 a 5.7 del plan | **desaparecen**, incluida la semana de prueba |
| Los prompts de los nueve agentes | **ganan esos tres pasos** — es trabajo de la fase 7 |

**Y responde a una pregunta suya que merece quedar escrita:** *«¿por qué lo hacéis tan complicado?»*. Porque se diseñó maquinaria —un hook, una tabla por oficio, un molde de datos y una prueba de una semana— para lo que se resuelve con **tres líneas en el prompt de cada agente**.

### [x] B21 · Los identificadores duplicados: alarma, no mecanismo — 2026-08-03

> **«Mete un diagnóstico cuando hace el arranque, que diga que hay dos decisiones con el mismo número, y que lo arregle Claude, y a tomar por culo.»**

**Ya está construido**: el arranque comprueba los identificadores duplicados y lo dice en voz alta — `no duplicate IDs (5 notes)`. Si algún día dos notas comparten número, sale en el arranque y **lo arregla Claude en ese momento**.

Con eso, el hueco que Moriarty dejó anotado en la capa 2 —*«si alguien llama a la pieza de los índices por su cuenta, dos notas podrían coger el mismo número»*— **deja de ser un fallo que reparar**: es un caso que la alarma ya caza. Y encaja con lo que la especificación decía desde el principio: *«es alarma pasiva: detecta y lo enseña»*, porque repararlo solo significaría renumerar una nota ya escrita y todos los punteros que la citan.

### [x] B19 · Las cuatro que quedaban, cerradas por el orquestador — 2026-08-03

> **«Que las cierres ya. Me la suda lo que respondas ahí. Las cierres de una puta vez.»** `[el propietario delega el criterio, 2026-08-03]`

Quedan cerradas así, cada una con su motivo. **Revocables**: se decidieron con su delegación expresa, no con su respuesta.

**1 · Una decisión SÍ puede nacer de otra decisión.** Se añade `origin` a los campos permitidos del tipo `D`.

*Por qué:* el ejemplo del propio molde enseña `D-041 · nace de D-030`, y hoy **el sistema rechaza el ejemplo que lo ilustra**. Además el caso es real y corriente: decides el login con Google, y de esa decisión nace otra más pequeña —cuánto dura la sesión— que sin puntero queda suelta y nadie sabe de dónde salió. La alternativa era borrar el ejemplo, y eso sería tapar el hueco en vez de cerrarlo.

**2 · La aduana se enciende sola.** En cuanto el proyecto tiene memoria propia —existe `.claude/project-memory/` con al menos una nota—, la aduana queda encendida. **Sin botón.** La bandera `customs_enabled` se conserva para apagarla a mano si hace falta, no para encenderla.

*Por qué:* un interruptor que hay que acordarse de pulsar es un vigilante apagado, y este proyecto entero existe porque el silencio es su única amenaza. Y el motivo original de que naciera apagada —no bloquear al sistema viejo mientras siguiera en uso— **se cae solo con este criterio**: un proyecto sin memoria nueva no tiene notas, así que la aduana no se enciende y no molesta a nadie. El día que se escribe la primera nota es exactamente el día en que hay algo que proteger.

**3 · `git rebase --continue` y `--skip` pasan.** Solo se rechaza el `git rebase` que lo empieza. `--abort` pasa, como ya estaba.

*Por qué:* el bloqueo tiene que estar en la puerta de entrada, no a mitad del pasillo. Si alguien está dentro de un rebase —lo empezó en su terminal, o vino de un conflicto—, bloquear el `--continue` **lo deja atascado sin salida hacia delante**, y con un repositorio a medias, que es peor que el daño que se quería evitar. La decisión anterior la tomó un agente por su cuenta y nadie la revisó.

**4 · `awaits:` en todas partes, también en el informe de zona.** No hay excepción para el informe.

*Por qué:* la excepción venía de la regla vieja —«lo que se lee va en español»—, que es justo el eje que él cambió: ahora manda **etiqueta contra explicación**, y `awaits:` es una etiqueta en las dos superficies. Dos idiomas para el mismo campo según dónde salga es exactamente el tipo de detalle que nadie recuerda y acaba divergiendo.

### [x] B22 · Dos escrituras a la vez sobre el mismo fichero: **no se dan** — 2026-08-04

> **«No va a pasar nunca.»** `[propietario, 2026-08-04, respondiendo a la pregunta que bloqueaba las capas 2 y 3]`

Trabaja en una sola ventana. **No se construye nada para ese caso**, ni serializar ni negarse: no hay caso.

**Qué cierra, y son los tres hallazgos que llevaban la obra parada:**

| Punto | Qué medía | Estado |
|---|---|---|
| **27** | Dos `gitmem work` normales sobre el mismo fichero dan un commit con el mensaje de uno y el contenido del otro, **16 de 30**, respondiendo que todo fue bien | **cerrado — caso descartado** |
| **28** | Dos reparaciones a la vez duplican una nota y la commitean, **15 de 15** | **cerrado — caso descartado** |
| **13** (lo que quedaba vivo) | Un intruso que escribe en disco sin pasar por el sistema en absoluto | **cerrado — caso descartado** |

**Es la misma figura que B7** (el repositorio anidado): el hecho medido era real, el caso no se da, y por eso no se repara. Se cierra por decisión, no por arreglo — y queda escrito así para que nadie lo vuelva a levantar como hallazgo.

**Y cierra también por qué no se siguió tocando código:** el punto 27 llevaba **tres intentos** de reparación y **dos de ellos crearon un fallo nuevo en el arreglo anterior** — el 28 nació precisamente dentro del arreglo del 27. Seguir por ese eje era construir maquinaria contra una amenaza que este proyecto no tiene.

**Lo que NO cierra:** el candado de `gitcmd.file_lock()` **se queda donde está** —en `write`, `replace` y `close`—. Está escrito, probado (6 procesos × 60 iteraciones, sobrevive a un `kill -9`) y no cuesta nada mantenerlo. Esta decisión dice que no se construye **más**, no que se desmonte lo que ya aguanta.

### [x] B23 · Dar de alta una zona que ya existe **se rechaza y no toca nada** — 2026-08-04

> **«Lo puto lógico, que lo he dicho 40.000 veces.»**

No sobrescribe, no actualiza, no pregunta: **rebota diciendo que ya existe y no toca nada.**

**El fallo que cierra, reproducido ejecutándolo:** `gitmem zones add billing` sobre un `billing` que ya existía dejaba la zona con la descripción nueva y **sin los alias anteriores**. Como el alta de zonas **no pasa por git**, no había de dónde recuperarlos. Y el mensaje de éxito era **idéntico** al de una zona nueva: nada distinguía «he creado» de «he borrado lo que había». Lo encontró Argus el 2026-08-04.

**Construido y verificado el mismo día**, por donde entra el usuario:
```
add billing (alias: facturacion)  → ✅ billing añadida — zones.json tiene 1 zona
add billing (otra vez)            → ❌ "billing" ya es una zona — no se ha tocado zones.json
                                       fichero byte a byte igual · alias conservado
```

### [x] B31 · Un nombre que ya es **alias** de otra zona también se rechaza — 2026-08-04

`[decisión del orquestador extendiendo la de B23; revocable por el propietario]`

**Era el mismo agujero un paso al lado, y lo destapó Ultron al implementar B23.** La comprobación miraba solo los nombres canónicos, así que dar de alta una zona con el nombre que ya era **alias** de otra **creaba una segunda zona**. Desde ese instante `zones.resolve()` llevaba ese nombre a la zona nueva y no a la de siempre: **el alias quedaba secuestrado sin un solo aviso**, y la memoria escrita con él se partía en dos.

**Y el rechazo tiene una exigencia que los demás no tienen:** aquí el usuario **no puede saber por qué le rechazan** —«facturacion» no sale como zona en ningún listado—, así que el texto **nombra al dueño del alias**. Un «no» sin salida no es un rechazo válido en este sistema.

```
add facturacion  → ❌ "facturacion" ya es alias de la zona "billing"
                      — no se ha tocado zones.json
```

**Y de paso, el mensaje de éxito quedó descolgado y se arregló:** decía *«dada de alta»* —el nombre del comando viejo, que ya no existe— y *«1 zonas»*. Ahora dice *«añadida»*, anclado a `add`, y concuerda el singular.

### [x] B24 · Una regla casi repetida **no se guarda** — 2026-08-04

> **«Si es casi repetida, dejar solo 1.»**

Cierra el hueco que el contrato dejaba abierto (`PIEZAS.md` §9.7 decía *«se dice y se decide»* sin decir quién decide): tras el aviso, **la nueva no se guarda**. Queda una.

**Construido y verificado el 2026-08-04.** El texto lo delegó el propietario («decídelo tú») y está en `TEXTOS.md` §1.11b, marcado como revocable. El rechazo enseña **las dos** reglas —la vieja con su dueño real y la que ibas a escribir— porque sin verlas juntas no se puede juzgar si son la misma.

**Y destapó un límite que había que escribir:** el detector compara **palabras, no significado**. Caza `sé escueto, nada de yapping` contra `sé escueto, not yapping`, pero **no** caza `no te enrolles, ve al grano`, que dice lo mismo sin compartir ni una palabra. Es un límite aceptado —la especificación §12 lo declara punto abierto porque excede a un script—, pero el ejemplo del propio documento ilustraba justo el caso que no funciona, y eso sí era un fallo: se corrigió.

### [x] B25 · Los 70 commits basura de la rama **se quedan** — 2026-08-04

> **«Me dan igual esos commits, son basura, me la pela.»**

**No se reescribe la rama** — y menos con toda la obra sin commitear. Cierra el punto **21**. Los 8 ficheros sueltos que dejó aquel test **ya no están en la raíz** (comprobado el 2026-08-04), y la causa se arregló con una red en el `conftest` que compara el `HEAD` real antes y después de cada test.

### [x] B26 · `bootstrap_commits.py` se retira — 2026-08-04

Cierra el punto **23**. Vivo sin un solo llamador de producción; solo lo usaban sus tests. **Con una condición:** `tests/test_read_retry_contract.py` no lo prueba a él, prueba `git_helpers.run_git_read_retrying()` —pieza viva— usándolo como segundo punto de entrada. Esa cobertura **no puede bajar**.

### [x] B27 · Los diez ataques **no se publican en ningún sitio** — 2026-08-04

> **«Lo que consideres. Yo lo borraría todo eso.»**

Cierra el punto **16** de «lo decidido que falta por construir». El catálogo **no se pierde**: sigue siendo el material de ataque de Moriarty dentro de §12bis, igual que en todas las capas cerradas hasta hoy. Lo que **no** hay es artefacto ni superficie de salida — y en concreto **no vuelve al arranque**, porque eso reintroduciría exactamente el automatismo recurrente que él borró con `bench`.

### [x] B28 · La prueba de una semana **está cancelada** — 2026-08-04

> **«Esa prueba se canceló, lo dije antes.»**

Los requisitos **160** y **161** de `TRAZABILIDAD.md` se retiran con su motivo, sin borrar la fila. Al quitar la inyección (**B20**) no queda nada que medir: medían si un muro inyectado cambiaba lo que iba a hacer quien implementa, y ya no se inyecta nada.

### [x] B29 · Los subcomandos de zonas pasan a inglés — 2026-08-04

> **«Exacto, en inglés YA.»**

| Antes | Ahora |
|---|---|
| `gitmem zones alta` | **`gitmem zones add`** |
| `gitmem zones listar` | **`gitmem zones list`** |
| `gitmem zones buscar` | **`gitmem zones find`** |

Eran **los últimos tres nombres en castellano que ve una máquina** en todo el sistema, y contradecían su propia regla **B11**. Los nombres viejos **dejan de existir**: nada externo depende de ellos y todo esto está sin publicar.

### [x] B30 · El vigilante de cada mensaje **habla siempre** — 2026-08-04

> **«Que escriba algo, como "no hay nada que decir".»** · **«Que tenga coherencia y que sea en inglés.»**

**Revoca la decisión que se tomó en su ausencia** el 2026-08-02 —que callar estaba bien— y cierra el punto **22**, que quedó anotado como revocable precisamente por eso. Hoy imprime:

```
[memory-check] No skill match this turn — nothing to report.
```

**Por qué importa y no es cosmético:** un vigilante que solo habla cuando falla **es indistinguible de uno que no se está ejecutando** (principio P6). Ya costó un incidente: seis hooks corrieron versiones viejas durante días sin que nada lo dijera.

### [~] B32 · El destilador: **Bilbo, en rondas en cascada, con cosecha de zonas antes** — 2026-08-04

**Cierra el «sin decidir» de los pasos 8.3, 8.4 y 8.5**, que llevaban ahí desde que se escribió el plan.

**Una skill nueva prepara el trabajo.** No se lanza a Bilbo a pelo: la skill **mide primero** —cuántos commits hay y de qué clases, con git— y de ahí sale cuántas rondas hacen falta. Mil commits no caben en una sesión.

**Pasada 0 — la cosecha de zonas.** No destila nada: solo saca los términos candidatos a zona y **se los presenta al propietario para que apruebe**. Sin esto, cada ronda muere en «esa zona no existe», porque la aduana rechaza zonas inventadas.

**Y luego las rondas, EN CASCADA — de lo viejo a lo nuevo, nunca en paralelo** `[refinamiento del propietario sobre la propuesta del orquestador, y es mejor]`:

```
ronda 1 → los primeros 100 commits            → produce N notas
ronda 2 → LEE esas N notas + sus 100 commits  → produce M notas
ronda 3 → LEE las N+M + sus 100 commits       → ...
```

**Por qué así y no en paralelo:** si las rondas son ciegas entre sí, **se destilan contradicciones como si todas fueran verdad** — una decisión de marzo sustituida en junio, y la ronda que ve marzo no sabe que murió. Leyendo **las notas ya destiladas** (no una lista de identificadores: las notas **con su porqué dentro**), cada ronda puede **sustituir con puntero**. Es exactamente lo que el v2 tiene y el v1 no tenía.

### [x] B33 · **Compactación de memoria de agente**, proyecto a proyecto — 2026-08-04 `[construida 2026-08-05: `skills/unmassk-memory/references/agent-memory-compaction.md`]`

Se invoca a cada agente para que **mire sus memorias, las contraste contra el código o la documentación, haga informe, las modifique, y le diga a Claude qué cambió y por qué.** Puede ser skill nueva o ir dentro de la misma del cambio del v1 al v2.

**Tres condiciones que añade el orquestador**, porque un agente auditando su propia memoria es **juez y parte** —esa memoria es lo que le enseñó qué es verdad—:
1. **Cada cambio con su prueba**: fichero y línea.
2. **Nada se borra.** Se marca superado, con puntero, igual que las notas. Si borra, se pierde por qué lo creyó.
3. **Además de contrastar, fundir el diario en temas.**

**Y ese tercero salió de medirlo, no de suponerlo** `[2026-08-04]`:

| Agente | Ficheros | Líneas |
|---|---|---|
| **Dante** | **112** | **15.557** |
| Ultron | 21 | 7.286 |
| Moriarty | 3 | 2.458 |

**66 de los 112 de Dante son notas de una tarea concreta.** Eso no es memoria: es **un diario**, crece sin techo y no lo relee nadie, ni él. Es la enfermedad del v1 —escrito y nunca leído— en un tercer sistema. **Moriarty es la forma sana:** tres ficheros temáticos que crecen por dentro.

### [x] B34 · El cierre de sesión lo hace un agente que lee la conversación — **Claude no lo escribe** — 2026-08-04 `[construido 2026-08-05: skills/unmassk-close-session/, con dos condiciones revocadas por B42]`

Un agente ejecuta un script que **saca el JSONL de la conversación y le quita la morralla**, se lee la conversación entera, escribe **un contexto de unas 50 líneas** y pone **el Next correcto**.

**Qué problema ataca, y está medido** `[2026-07-31]`: *«se guardó bien mientras hubo pausas de trabajo, y se dejó de guardar en cuanto la sesión pasó a ser conversación continua. La aduana no cubre eso: vigila lo que llega a la puerta, y en conversación continua nadie va a la puerta.»* Hoy el contexto lo escribe Claude acordándose — **y acordarse no es un mecanismo**.

**Qué agente: `general-purpose`, con el prompt DENTRO de la skill de cierre.** No lleva ficha propia: una ficha sirve para dar oficio estable y memoria que se acumula entre sesiones, y este no necesita ninguna de las dos — lee, escribe y se va.

> **Es la excepción declarada a una regla del propietario**, y se deja escrito para que nadie la «corrija» dentro de dos meses: *«delega con la tripulación puesta, nunca agentes genéricos»* salió de las cadenas de montaje, donde importa que cada oficio se quede en su carril. Esto es una tarea suelta, de una pasada, sin carril que invadir.

**Dos condiciones que no se negocian:**
- ~~**El filtro quita los volcados de herramientas, NO los comandos.**~~ **REVOCADA el 2026-08-05 — ver B42.** El filtro saca **solo la conversación**.
- **No puede ir en `SessionEnd`.** Ese evento dispara al cerrar de verdad, pero **ya no hay modelo**: nadie puede juzgar qué importó. Se invoca mientras Claude sigue vivo.
- **Y el prompt vive en la skill, no se improvisa.** Un encargo tecleado de memoria cada vez es la puerta por la que un día no se pide el Next.

### [~] B35 · Un plan nace **solo si él lo dice** — 2026-08-05

> *«Lo decido yo. Tú, si quieres, puedes ofertarlo, pero lo decido yo.»*

Claude puede **ofrecerlo en una línea** cuando algo se alarga o toca varias zonas; abrirlo por criterio propio, nunca. Un plan arrastra documento, incidencia y acta: es ceremonia, y la ceremonia la pide el dueño.

### [~] B36 · Si la decisión cambia a mitad de un plan, **se edita la incidencia abierta** — 2026-08-05

> *«Se edita lo que hay.»*

No se cierra una y se abre otra: **un plan, un hilo**, con la historia del cambio dentro. Coincide con lo que la especificación §10.3 ya decía, y lo cierra como decisión suya.

### [x] B37 · El bloque del `CLAUDE.md` lleva el arranque **y las cuatro reglas que no pueden fallar** — 2026-08-05

Aprobado sobre el texto literal. Además del arranque —leer el informe, cargar la skill central y la de memoria, contar el menú del día—, el bloque lleva cuatro reglas que valen **aunque no se cargue ninguna skill**: la memoria es un commit y no se escribe en ficheros · los índices y la lista de zonas los escriben los comandos · un muro se retira preguntando · los comandos los ejecuta Claude.

**El motivo:** el bloque se lee siempre; la skill, solo si alguien la carga.

### [x] B38 · Una incidencia es lo que se rompe **en lo ya entregado** — 2026-08-05

> *«Si Cerberus o Argus encuentran algo mientras se construye, eso no es una incidencia: se lo dicen a Claude y se manda reparar. Un módulo no es perfecto al principio, se va puliendo. Una incidencia es cuando han pasado diez meses y sale un error de ese módulo.»*

**La línea es la entrega.** Antes, los hallazgos son trabajo; después, son cicatriz. Escrito en la especificación (§4), en la skill de memoria, en la ficha de House —que ahora **no emite pie si el encargo no dice en cuál de los dos casos está**— y en la skill de auditoría.

**Y una cerrada es historia:** si vuelve a romperse, es una incidencia **nueva**. Ni se reabre ni se sustituye.

### [x] B39 · Lo archivado **no bloquea** — 2026-08-05

El detector de parecidas miraba todo el historial: una incidencia cerrada en marzo frenaba la de octubre y ofrecía `--replaces`, salida que el tipo incidencia **no admite**. Ahora solo mira lo vigente. Lo vivo sigue bloqueando, que ahí sí es duplicado. *(Reparado también en el mismo camino del muro, que tenía el fallo gemelo.)*

### [x] B40 · Cada ronda de destilación **arranca leyendo `zones.json`** — 2026-08-05

Sin zonas aprobadas no empieza: es la comprobación de que la cosecha existe. Y con la lista real delante, lo que no encaje se ve en el momento.

### [x] B42 · El cierre: **solo la conversación arriba, TODOS los commits abajo** — 2026-08-05

**Revoca dos cosas de B34**, y las dos por el mismo motivo: el contexto es un resumen de lo hablado, no un acta de lo hecho.

**1 · El filtro saca la conversación y nada más.**

> *«Solo tiene que sacar la conversación, porque lo que tiene que decir en el context es un resumen de la conversación. No tiene que sacar ni tools, ni diferencial de archivos, ni nada de nada.»*

Cae la condición de conservar los comandos («lo comprobé» contra «lo dije»): lo comprobado deja commits, y los commits van listados justo debajo del contexto. **Y al medirlo apareció que la condición vieja se estaba comiendo el fichero:** el 42% eran informes de subagentes —lo que él mismo descartó el mismo día— colados porque llegan con forma de mensaje suyo, no de salida de herramienta.

**2 · Debajo del contexto van TODOS los commits desde el último Next.**

> *«Todos. Sean WIP, sean commit, sean memoria, sean datos, sea lo que coño sea. Si los WIPs los han squasheado, pues entonces no: solamente el commit y el squash. Solamente hay que enumerar el titular, la primera línea.»*

Nada de filtrar por tipo. Si los checkpoints se fundieron, git solo tiene el fundido y eso es lo correcto, no una pérdida.

**Construido y probado ejecutándolo el mismo día**, en `skills/unmassk-close-session/`: 53 MB de conversación en crudo → 633 KB de solo lo dicho, sin un resto de herramienta ni de informe.

### [x] B41 · Una ronda **da de alta la zona que falte** — 2026-08-05

Como en el uso normal: a la vista y sin pedir permiso. Perder una nota por una zona que la cosecha no vio es peor que crearla. **Cada ronda declara en su informe las zonas que creó**, para revisarlas juntas.

**Y lo que NO hubo que decidir, porque ya estaba escrito** `[2026-08-05]`: el contenido de la incidencia de plan lo fija la especificación §10.2 — *«la issue enlaza al documento y aloja el roadmap/checklist tachable»*—, y el ciclo de la pregunta abierta lo fija §4. Se le preguntaron las dos igual. Queda anotado como antipatrón: **buscar en la documentación antes de plantearle una decisión.**

---

# LOS 80 PASOS — dónde está cada uno

> **Eran 83 y son ~~76~~ 80** `[corregido 2026-08-04, y otra vez el mismo día: 76 restaba los siete de la fase 5 pero no sumaba los cuatro pasos nuevos decididos ese día — 7.13b, 7.13c, 7.13d y 8.2b, B32/B33/B34 — que sí entran en la suma comprobada de más abajo (43+0+5+32=80 antes de sus propias correcciones)]`. La fase 5 se retiró entera por decisión del propietario (B20) y sus **siete** pasos dejaron de existir — pero el recuento seguía sumándolos, y encima con estados que ya eran falsos (daba por construido un fichero borrado). **Un paso retirado que sigue contando es un paso que nunca se va a poder marcar hecho**, y por eso la tabla de abajo no llegaba nunca al final por diseño.

**Medido el 2026-08-03, paso a paso, ejecutando lo que se podía ejecutar** (`python3 -m pytest unmassk-toolkit/tests/memory -q` → **275 verdes, 0 rojos**, confirmado en esta misma revisión) **y leyendo el código donde no se podía**. Los pasos son los de `PLAN-CONSTRUCCION.md`, del 0.1 al 9.4, sin saltarse ninguno — incluido el **7.2b**, que el plan tiene pero no estaba contado en el «catorce» de la fase 7 (con él son **quince**).

**Cuatro estados, y solo esos:** ✅ **hecho** · 🔨 **a medias** (construido pero le falta una pieza concreta) · ⬜ **sin empezar** · ⚠️ **hecho pero sin cerrar** (construido y con tests en verde, pero su revisión todavía no ha terminado — el caso de las fases 2 y 3, punto **13** de esta misma deuda).

**Añadido más tarde el mismo 2026-08-03, con lo cerrado en las horas siguientes a la medición de arriba:**

- **Suite reejecutada: `python3 -m pytest unmassk-toolkit/tests/memory -q` → ~~261~~ **320** verdes, 0 rojos** (no 275 — el número bajó por tests retirados junto con piezas que se retiraron, no por regresión; verificado ejecutando, no de memoria). `[recontado 2026-08-04: la suite subió a 320 con el trabajo posterior — capas 2/3, B23/B24/B31, etc. — verificado ejecutando de nuevo, no de memoria]`
- ~~**El punto 27 de la Parte 2 —el fallo más grave de la obra— está cerrado.** `write_work()` deja de mentir... verificado con dos procesos reales, 0 de 60 con contenido cruzado.~~ **Este párrafo era falso y hay que dejarlo escrito** `[corregido 2026-08-04]`: ese «0 de 60» **se midió llamando a la función por dentro**, con el contenido inventado en memoria y nunca escrito a disco. Medido por donde entra el usuario salió **16 de 30**. El punto 27 **sí está cerrado hoy**, pero por otro motivo — el propietario descartó el caso (**B22**). *Un arreglo se mide por el camino por el que entra el usuario, nunca por dentro.*
- **La Fase 5 (fila de la tabla de abajo) ya no existe como tal.** Por la decisión **B20** de la Parte 1, sus siete pasos (5.1 a 5.7) se sustituyen enteros: `hooks/inject.py` y `lib/memory/dispatch.py` **se borraron de verdad**, con sus tests, y los nueve prompts de agente ya llevan el paso nuevo (verificado leyendo los nueve ficheros de `agents/`). Lo que queda pendiente de esa sustitución son dos avisos menores de Cerberus, todavía sin cerrar: el flag `search.py --file` sigue vivo y siempre falla en silencio (nadie lo usa desde los nueve prompts, pero sigue sin marcarse como roto en ningún documento), y la línea «Memory consulted» de los informes no está comprobada por ningún gate real — un agente puede escribir «ninguna» sin haber buscado nada y nada se lo impide.
- **El punto 13 sigue abierto, pero por un solo motivo** `[al día 2026-08-04]`. La tercera pasada de Moriarty sobre las capas 2 y 3 encontró tres cosas: `rezones.py --rebuild` no guardaba su reparación (**arreglado**, comprobado con un `git checkout` real), y las otras dos eran del eje de la concurrencia — **descartadas enteras por el propietario** (*«no va a pasar nunca»*, **B22**). Lo único que falta es **la cuarta pasada de Moriarty**, que §12bis exige y nadie ha hecho. El detalle está en el propio punto 13.

## El recuento — **al día 2026-08-04**

**80 pasos vivos en total** (los 83 del plan · **menos** los 7 de la fase 5 retirada · **más** los 4 que añaden las decisiones del 2026-08-04: **7.13b** la skill de destilación, **7.13c** la auditoría de memoria de agente, **7.13d** el prompt del cierre de sesión, y **8.2b** la cosecha de zonas).

| Estado | Cuántos |
|---|---|
| ✅ hecho | ~~43~~ **44** |
| ⚠️ hecho, pero sin cerrar | **0** |
| 🔨 a medias | **5** |
| ⬜ sin empezar | ~~32~~ **31** |

`[corregido 2026-08-04: el paso 7.10 pasó a hecho — punto 3 de la PARTE 2, cerrado el mismo día — así que sube un hecho y baja un sin-empezar]`

**Por fase:** 0 → 4/4 hecho · 1 → 10/10 hecho · 2 → 8 hecho + 2 sin empezar (de 10) · 3 → 7 hecho + 2 a medias (de 9) · 4 → 9/9 hecho · **5 → retirada entera, 0 pasos** · 6 → 4 hecho + 2 a medias + 3 sin empezar (de 9) · 7 → ~~1 hecho + 17 sin empezar~~ **2 hecho + 16 sin empezar** (de 18) `[corregido 2026-08-04: 7.10]` · 8 → 0/7 · 9 → 1 a medias + 3 sin empezar (de 4).

**Suma comprobada:** ~~43 + 0 + 5 + 32~~ **44 + 0 + 5 + 31** = **80**. `[los cuatro recuentos anteriores de este documento no cuadraban con su propia tabla; este sí — sumar es la comprobación más barata que tiene esta lista y no se estaba haciendo. Recontado 2026-08-04 tras cerrar 7.10]`

**El ⚠️ desaparece de esta tabla el 2026-08-04, y esto es lo más grande que ha pasado hoy.** Las quince filas de las fases 2 y 3 llevaban esa marca desde el principio de la obra: construidas, con sus tests en verde, y **sin cerrar** porque les faltaba la pasada de Moriarty que §12bis exige. Ya la tienen — una por capa, el 2026-08-04. Las dos dieron hallazgo y los dos están reparados y verificados ejecutándolos (punto **13**). **Las capas 2 y 3 eran anteriores a todo lo construido encima**, y era la razón por la que `CALENDARIO.md` avisaba de que se estaba edificando sobre una capa abierta. Ya no.

**La marca ⚠️ se queda definida en la leyenda de arriba** aunque hoy no la lleve ninguna fila: vuelve a hacer falta en cuanto se construya la próxima capa, porque toda capa nace así hasta que pasa su secuencia entera.

**Lo que no pude verificar ejecutando, y por qué:** los pasos que dependen de una sesión real con los hooks activos (3.6, ~~5.3, 5.4,~~ 6.1, 7.14 y toda la fase 9 `[corregido 2026-08-04: 5.3 y 5.4 eran de la fase 5, retirada entera por B20 — ya no existen]`) no se pueden probar disparando una sesión de verdad, porque **lo que corre en cada sesión es la copia instalada en la caché (versión 1.25.0), no este repositorio** — lo comprobé pidiendo un comando inocuo y viendo que el aviso de bloqueo citaba la ruta de la caché, no la del repo. Para esos pasos leí el código y sus tests en vez de ejecutar una sesión — está anotado en cada fila.

**Tres hallazgos que no esperaba, verificados los tres leyendo el código de hoy mismo, no un documento:**
1. **El candado que faltaba en `write_work()` (el hallazgo más grave que tiene anotado el punto 27 de esta deuda) ya está arreglado en el código.** El docstring de `notes_commit.py` lo fecha el 2026-08-03 y lo atribuye a Moriarty; `pytest tests/memory/test_notes.py` da 22 verdes. `[al día 2026-08-04: el punto 27 quedó cerrado, pero no por este arreglo — el propietario descartó el caso entero (B22). Este párrafo se conserva porque el arreglo del candado sigue en el código y sigue siendo cierto.]`
2. **Gitto ya está retirado** (paso 7.7): nueve agentes en `agents/`, y `deprecated/gitto.md` existe y está commiteado — no es un pendiente de la fase 7, está hecho, y de hecho más avanzado de lo que decía el encargo de esta tarea.
3. **`unmassk-toolkit/commands/` no existe como carpeta.** El comando de reglas (`/remember`, paso 3.3) no tiene su fichero — está la pieza que lee y escribe el fichero de reglas, pero no el comando que lo entrega.

---

## FASE 0 — Preparar el terreno (4/4 hecho)

| Paso | Qué es | Estado | Qué falta |
|---|---|---|---|
| **0.1** | Crear la carpeta del sistema con su fichero de versión | ✅ hecho | Nada — con un matiz: no nació como plugin aparte en versión 0.1.0 (lo que pedía el paso tal cual), porque una decisión posterior del propio plan (§4) cambió el destino: el sistema vive dentro del toolkit que ya existía (versión 1.25.0, comprobado en `plugin.json`), no en una carpeta nueva. Es lo que manda esa decisión posterior, no un incumplimiento |
| **0.2** | Que los emojis se puedan imprimir sin reventar en cualquier terminal, incluidos los antiguos de Windows | ✅ hecho | Nada — probado en vivo forzando la codificación antigua (`cp1252`), imprime sin error |
| **0.3** | Un cajón de pruebas compartido: un repositorio de git de mentira para probar sin tocar el de verdad | ✅ hecho | Nada — existe (`tests/memory/conftest.py`, 637 líneas) con el repositorio de mentira y los ayudantes de alta; su prueba mínima pasa (`test_conftest_smoke.py`, 2 verdes) |
| **0.4** | Dejar escrito que casi nada de esto es un hook — casi todo se invoca por ruta, para no depender de publicar versión en cada cambio | ✅ hecho | Nada — está escrito en `ARQUITECTURA.md`, aunque no con la cita que este punto llevaba: ~~«Declara TRES hooks y nada más»~~ **`ARQUITECTURA.md:19` dice literalmente «Declarará DOS hooks de memoria — HOY NO DECLARA NINGUNO»** `[corregido 2026-08-04: la cita no existe en el fichero]`. Son dos hooks nuevos (`customs.py` y `boot_launcher.py`), ninguno registrado en `hooks.json` todavía — el espíritu del paso (casi todo por ruta) se cumple igual |

## FASE 1 — El validador (10/10 hecho, secuencia de revisión completa)

| Paso | Qué es | Estado | Qué falta |
|---|---|---|---|
| **1.1** | Los tipos de datos base del sistema, sin ninguna lógica dentro | ✅ hecho | Nada — hoy son **14**, no 13 como dice el documento (se añadió uno más después de contarlos); cosmético, no afecta a nada |
| **1.2** | Los siete tipos de nota, sus campos y sus reglas fijas | ✅ hecho | Nada |
| **1.3** | Que cada campo declare quién lo lee, para no repetir el error del sistema viejo (605 campos escritos y nunca leídos) | ✅ hecho | Nada |
| **1.4** | Las zonas del proyecto: alias, zona inexistente, lista negra | ✅ hecho | Nada |
| **1.5** | Construir un texto y volver a leerlo tiene que dar exactamente lo mismo que se escribió | ✅ hecho | Nada |
| **1.6** | Detectar dos notas casi iguales dentro de la misma zona | ✅ hecho | Nada |
| **1.7** | Un solo texto de rechazo que sirve tanto en pantalla como dentro de un bloqueo automático | ✅ hecho | Nada |
| **1.8** | La pieza única que decide si una nota es válida | ✅ hecho | Nada |
| **1.9** | Una prueba por cada regla del validador | ✅ hecho | Nada |
| **1.10** | Una prueba que salta sola si alguien añade un campo sin decir quién lo lee | ✅ hecho | Nada — no es un fichero aparte como preveía el paso, está dentro de `test_vocabulary.py` (`test_every_field_declares_a_reader_that_resolves_by_the_three_state_rule`), mismo efecto |

## FASE 2 — El generador (8 ~~sin cerrar~~ **hecho** + 2 sin empezar, de 10) `[corregido 2026-08-04]`

**Por qué «sin cerrar» y no «hecho» — ya no aplica.** ~~Moriarty ya atacó esta capa dos veces y las dos dio **FALLA** — sus hallazgos siguen sin cerrar formalmente (punto **13** de más abajo), así que aunque el código y los tests estén completos, la revisión no ha terminado.~~ **El punto 13 se cerró el 2026-08-04**: la cuarta pasada de Moriarty completó la secuencia de `PIEZAS.md` §12bis sobre esta capa, encontró un hallazgo real (el puntero `Origin` mal escrito) y quedó reparado y verificado. El recuento de ⚠️ de más arriba ya está en 0. `[corregido 2026-08-04]`

| Paso | Qué es | Estado | Qué falta |
|---|---|---|---|
| **2.1** | Una capa de git propia: que un fallo diga su motivo real, con candado contra dos escrituras a la vez | ✅ hecho | Revisión de Moriarty. *(Antes había aquí un segundo pendiente —`commit_empty()` sin directorio de trabajo propio, punto **25**— y **ya no lo es**: el punto 25 quedó cerrado el 2026-08-03 por decisión del propietario, «nunca voy a trabajar en submódulos». `[al día 2026-08-04]`)* |
| **2.2** | Los ocho ficheros índice: sembrar, insertar, retirar, archivar, contar | ✅ hecho | Revisión de Moriarty |
| **2.3** | El contador de identificadores por tipo (`D-001`, `D-002`...) y el detector de duplicados | ✅ hecho | Revisión de Moriarty |
| **2.4** | La transacción: la nota y su línea de índice se guardan juntas o ninguna de las dos | ✅ hecho | Revisión de Moriarty. El punto **27** —el hallazgo más grave de toda la obra— **quedó cerrado el 2026-08-04, y no por un arreglo**: el propietario descartó el caso (*«no va a pasar nunca»*, B22). Lo que sí está en el código y se queda es el candado y el paso de `known_content`, con su fecha y su motivo en el propio fichero `[al día 2026-08-04]` |
| **2.5** | Cuando se descarta una alternativa de una decisión, cada una con su propio commit y su propia línea de índice | ✅ hecho | Revisión de Moriarty |
| **2.6** | Los scripts para dar de alta una nota, cerrarla y sustituirla, con todos los flags desde el primer intento | ✅ hecho | Revisión de Moriarty |
| **2.7** | El commit de trabajo, con su issue, y que se pueda commitear solo ciertos ficheros sin arrastrar el resto | ✅ hecho | Revisión de Moriarty |
| **2.8** | **MINA 1** — decirle al guardián de commits del sistema viejo que reconozca los scripts nuevos, para que no los bloquee | ⬜ sin empezar | El fichero que hace esa comprobación (`pre-validate-commit-trailers.py`) sigue reconociendo solo el script viejo; no se ha tocado. En la práctica esto no ha bloqueado nada todavía porque el bloqueo solo salta cuando el texto de un comando escribe «git» y «commit» juntos, y los scripts nuevos se invocan con python — pero el paso, tal como está escrito, no se ha hecho |
| **2.8b** | **MINA 4** — que el script de publicar versión use el generador nuevo en vez del viejo | ⬜ sin empezar | ~~`unmassk-toolkit/bin/release.py`~~ **`bin/release.py`** (está en la raíz del repositorio, no dentro de `unmassk-toolkit/` — `[corregido 2026-08-04]`) sigue apuntando a `git-memory-commit.py` (el script viejo) y sigue usando el campo `Touched=` que el v2 retiró. El día que se borre el sistema viejo, publicar una versión se rompe |
| **2.9** | Pruebas de la transacción contra un repositorio real | ✅ hecho | Revisión de Moriarty. Las pruebas están y pasan: ~~22~~ **25** verdes (`test_notes.py`) `[recontado 2026-08-04]` |

## FASE 3 — Índices, arranque y salud (7 ~~sin cerrar~~ **hecho** + 2 a medias, de 9) `[corregido 2026-08-04]`

**Mismo motivo que la fase 2, y ya no aplica.** ~~Moriarty ya atacó esta capa dos veces, **FALLA** las dos, hallazgos sin cerrar (punto **13**).~~ **El punto 13 se cerró el 2026-08-04**: la cuarta pasada de Moriarty completó la secuencia sobre esta capa, encontró un hallazgo real (`write_work()` culpando a un proceso inexistente) y quedó reparado y verificado. `[corregido 2026-08-04]`

| Paso | Qué es | Estado | Qué falta |
|---|---|---|---|
| **3.1** | Las cuatro formas de leer notas: por identificador, por zona, por palabra, por fichero | ✅ hecho | Revisión de Moriarty |
| **3.2** | El aviso de «esto es lo que estaba haciendo» que se guarda al cerrar la sesión | ✅ hecho | Revisión de Moriarty. Moriarty encontró aquí un fallo real y no arreglado todavía: si el aviso más reciente no lleva ningún punto de contexto, el sistema devuelve por error uno más antiguo en su lugar, en vez del último — sin ningún aviso de que eso pasó |
| **3.3** | El fichero de reglas del proyecto, su script, **y el comando que lo entrega** | 🔨 a medias | El fichero y el script existen y funcionan. **El comando no existe**: no hay ninguna carpeta `commands/` en el sistema todavía, así que no hay forma de pedir las reglas con una orden — solo llamando al script directamente |
| **3.4** | La salud del sistema: coherencia entre índices y git, identificadores duplicados, planes sin reflejar | ✅ hecho | Revisión de Moriarty |
| **3.5** | El menú del día completo, escrito desde cero | ✅ hecho | Revisión de Moriarty |
| **3.6** | El hook mínimo que dispara el menú del día al abrir sesión | 🔨 a medias | Construido y probado por separado (`hooks/boot_launcher.py`, con sus propios tests), pero **no está enganchado en `hooks.json`** — no se dispara todavía en ninguna sesión real. Es a propósito: engancharlo ahora, con el sistema viejo aún encendido, dispararía dos arranques a la vez. Se engancha en la fase 9 (punto **26** de esta deuda) |
| **3.7** | El script que reconstruye los índices desde git, con un modo de solo mirar sin tocar | ✅ hecho | Revisión de Moriarty |
| **3.8** | Los ocho ficheros nacen vacíos, cada uno con su cabecera de aviso | ✅ hecho | Revisión de Moriarty |
| **3.9** | Pruebas del arranque y de la salud | ✅ hecho | Revisión de Moriarty |

## FASE 4 — La lectura: el informe (9/9 hecho, secuencia de revisión completa)

| Paso | Qué es | Estado | Qué falta |
|---|---|---|---|
| **4.1** | Agrupar notas encadenadas en un solo racimo | ✅ hecho | Nada |
| **4.2** | El título del racimo es siempre el de la nota viva más reciente | ✅ hecho | Nada |
| **4.3** | El orden del informe: restricciones arriba, racimos en medio, preguntas al final | ✅ hecho | Nada |
| **4.4** | El texto final del informe | ✅ hecho | Nada |
| **4.5** | Un aviso bien visible cuando una zona no tiene ninguna nota | ✅ hecho | Nada |
| **4.6** | La búsqueda por palabra señala la línea exacta que hizo coincidir, no solo la nota | ✅ hecho | Nada |
| **4.7** | Ver qué notas tocan un fichero concreto | ✅ hecho | Nada |
| **4.8** | El script de búsqueda con sus cuatro formas de buscar | ✅ hecho | Nada |
| **4.9** | Pruebas del informe | ✅ hecho | Nada |

## FASE 5 — **RETIRADA ENTERA** por decisión del propietario (B20, 2026-08-03) — 0 pasos vivos

**Los siete pasos (5.1 a 5.7) ya no existen.** La tabla que había aquí quedó caducada el mismo día que se escribió, y decía cosas que hoy son falsas: daba `dispatch.py` por construido y `hooks/inject.py` por «a medias, pendiente de enganchar», **cuando los dos ficheros están borrados del repositorio junto con sus tests**. `[corregido 2026-08-04 — la tabla vieja contradecía al párrafo de arriba de este mismo documento, que ya decía que se borraron de verdad]`

**Qué la sustituye:** cada agente busca su propia memoria, en tres pasos escritos en su prompt — el historial del fichero que va a tocar, la zona que sale de ahí, y los muros de esa zona. Los nueve prompts ya los llevan (verificado leyendo los nueve ficheros de `agents/`).

**Lo único que sobrevive de esta fase, y no como paso sino como aviso pendiente:** dos hallazgos menores de Cerberus siguen sin cerrar — el flag `search.py --file` sigue vivo y falla siempre en silencio (nadie lo usa, pero nada lo marca como roto), y la línea «Memory consulted» de los informes de agente no la comprueba ningún control real: un agente puede escribir «ninguna» sin haber buscado nada.

## FASE 6 — La aduana (4 hecho + 2 a medias + 3 sin empezar, de 9)

> **El título de esta fase decía «La aduana y el banco adversarial» y el banco ya no es un comando** `[corregido 2026-08-04]`. `gitmem bench` se borró entero (B4) y con él su único punto de entrada. Los pasos **6.7** y **6.8** siguen abajo porque el catálogo de los diez ataques no se pierde —es material de Moriarty dentro de §12bis—, pero **dónde sale su resultado no está decidido** y es un hueco declarado, no un olvido.

| Paso | Qué es | Estado | Qué falta |
|---|---|---|---|
| **6.1** | El hook de la aduana, llamando al mismo validador de la fase 1 | 🔨 a medias | Construido, llama al validador único (no hay una segunda copia de «esto es válido» en ningún sitio, comprobado leyendo el código) y tiene 17 pruebas en verde. **No está enganchado en `hooks.json`** — mismo motivo que 3.6 ~~y 5.3~~ `[corregido 2026-08-04: 5.3 era de la fase 5, retirada por B20]`, se engancha en la fase 9 |
| **6.2** | El interruptor de la aduana | ✅ hecho | Nada — y mejor de lo que pedía el paso: ya no hace falta encenderla proyecto a proyecto a mano; se enciende ella sola en cuanto el proyecto tiene su primera nota, por una decisión posterior del propietario (B19, punto 2 de la Parte 1) que ya está implementada en el código |
| **6.3** | Que el `wip` y el aviso de cierre de sesión no reciban ninguna pregunta | ✅ hecho | Nada |
| **6.4** | Al cerrar una incidencia, preguntar si de ahí sale un muro | 🔨 a medias | El mecanismo existe (`gitmem remove` exige decir `--restriction no` o `--restriction new`), pero por un camino distinto al que describe el texto oficial: en vez del aviso «CIERRE RETENIDO» con las dos opciones explicadas, hoy es un flag obligatorio de la línea de comandos, con un mensaje de error genérico si se olvida. Además falta la prueba de que crear el muro con éxito funciona — solo está probado el camino en el que falla |
| **6.5** | Al nacer un muro desde una incidencia, mostrar todas las incidencias candidatas de la zona, nunca una ya elegida de antemano | ⬜ sin empezar | No encontré ningún código que haga esto — ni un texto que lo describa fuera del propio plan |
| **6.6** | Cuando una zona no existe, el sistema dice cómo darla de alta y relanzar | ✅ hecho | Nada — el aviso de rechazo da el texto exacto y el comando existe (`gitmem zones add`; se llamaba `alta` hasta B29, 2026-08-04). **El texto del rechazo no se ve afectado por ese renombrado**: comprobado, no cita ningún subcomando — remite al fichero `zones.json` directamente |
| **6.7** | El catálogo de ataques del banco de pruebas | ⬜ sin empezar | No hay ningún fichero de catálogo. El propio plan deja anotado que, al borrarse el comando `gitmem bench`, no está decidido dónde debe salir el resultado de este banco — es un hueco a propósito, no un olvido |
| **6.8** | Que el banco corra solo y enseñe su resultado | ⬜ sin empezar | Depende del 6.7 |
| **6.9** | Pruebas de la aduana | ✅ hecho | Nada — 17 verdes (`test_customs_hook.py`) |

> **Esta tabla va por detrás desde el 2026-08-05 y no se fía de ella nadie: el estado vivo de la fase 7 está en `FASE-7.md`, que es la orden de trabajo.** Ese día se cerraron once pasos más (7.1 a 7.6, 7.8, 7.9, 7.11 a 7.13d) y aquí solo se han marcado los dos que se tocaron. Se deja dicho en vez de repintar doce filas de memoria: **13 de 18 hechos, queda el 7.14** *(y antes, el 2.8b)*.

## FASE 7 — Skills, agentes y periferia (~~1~~ **2** hecho, de ~~15~~ **18** — la más grande y la que falta casi entera) `[corregido 2026-08-04: faltaban tres filas en esta tabla — 7.13b, 7.13c y 7.13d, decididas el mismo día (B32/B33/B34) — que el recuento de "80 pasos" de más arriba ya sumaba pero esta tabla no llevaba]`

| Paso | Qué es | Estado | Qué falta |
|---|---|---|---|
| **7.1** | La skill de memoria, que enseña a traer todos los datos puestos desde el primer intento | ⬜ sin empezar | No existe ninguna carpeta de skill de memoria nueva |
| **7.2** | Dentro de esa skill: la regla de los dos segundos, cuándo algo es bloqueante y cuándo es un muro, el árbol de los siete tipos | ⬜ sin empezar | Depende del 7.1 |
| **7.2b** | Dentro de esa skill: la explicación de «ver qué notas tocan un fichero», escrita una sola vez para que ningún agente la repita | ⬜ sin empezar | Depende del 7.1 |
| **7.3** | Dentro de esa skill: que solo el usuario, hablando normal, dispare una búsqueda — nunca una palabra clave ni un criterio propio de Claude | ⬜ sin empezar | Depende del 7.1 |
| **7.4** | Dentro de esa skill: enseñar el menú del día en el primer mensaje | ⬜ sin empezar | Depende del 7.1 |
| **7.5** | Cómo vive y muere una pregunta abierta: se resuelve antes de construir encima, puede generar una incidencia, y al cerrarse sube de nivel o se descarta | ⬜ sin empezar | No encontré ningún mecanismo ni documento que lo implemente todavía |
| **7.6** | Los planes: documento, incidencia creada a mano por Claude (nunca por un script), acta que enlaza la decisión con la incidencia | ⬜ sin empezar | No hay nada construido para esto todavía |
| **7.7** | Retirar a Gitto sin borrarlo — mover su ficha fuera de la lista de agentes activos | ✅ hecho | Nada — **este ya está hecho, y no lo decía el encargo de hoy**: hay nueve agentes en `agents/` (Gitto no es uno), su ficha vive en `deprecated/gitto.md`, y ese cambio ya está commiteado en el repositorio |
| **7.8** | Un pie fijo y ordenado al final del informe de House | ⬜ sin empezar | El informe de House sigue con su formato de siempre, sin ninguna sección nueva relacionada con memoria |
| **7.9** | Que Bilbo, antes de entrar en detalle, empiece siempre con el mapa general | ⬜ sin empezar | Bilbo ya tiene una instrucción de «zoom out» genérica, pero es de marzo de este año, de una restructuración sin relación con este proyecto — no hace referencia a zonas ni a muros. No es lo que pide este paso |
| **7.10** | Que el cierre de sesión recupere lo que perdió: el aviso final con su resumen, la incidencia-plan al día, la poda de muros viejos, el alta de bloqueantes | ~~⬜ sin empezar~~ **✅ hecho** `[corregido 2026-08-04, ver punto 3 de la PARTE 2]` | ~~La propia skill de cierre de sesión lo dice con todas las letras: «esto vuelve en el paso 7.10, y el reemplazo todavía no está construido»~~ **Nada — verificado 2026-08-04**: `SKILL.md` tiene 62 líneas con los cuatro pasos escritos (Next en prosa, issue del plan, poda de muros, alta de bloqueantes). No verificado con un cierre real de punta a punta, solo con la lectura del fichero |
| **7.11** | Los seis puntos de la skill central (`unmassk-core`) que hay que actualizar | ⬜ sin empezar | Esa skill sigue mencionando la skill de memoria vieja como si siguiera viva |
| **7.12** | Reescribir entero el bloque de `CLAUDE.md` que se instala en todos los proyectos | ⬜ sin empezar | El generador de ese bloque sigue con el patrón de borrado del sistema viejo, sin ningún contenido del nuevo |
| **7.13** | La skill de incidencias | ⬜ sin empezar | No existe ninguna carpeta para ella |
| **7.13b** *(añadida 2026-08-04)* | La skill de destilación: mide con git cuántos commits hay y de qué clases, decide cuántas rondas hacen falta y las encadena en cascada `[decisión B32]` | ⬜ sin empezar | No existe ninguna skill de destilación todavía |
| **7.13c** *(añadida 2026-08-04)* | La compactación de memoria de agente: cada agente contrasta sus memorias contra código/documentación, informa y las modifica `[decisión B33]` | ⬜ sin empezar | No existe ese encargo todavía, ni como skill nueva ni dentro de otra |
| **7.13d** *(añadida 2026-08-04)* | El prompt del cierre de sesión, dentro de `unmassk-close-session`, ejecutado por un `general-purpose`: filtra la conversación, la lee entera y escribe el Next, el contexto y la lista de commits `[decisiones B34 y B42]` | ✅ hecho `[2026-08-05]` | Nada — `scripts/session_transcript.py` + `references/close-agent-prompt.md` + `SKILL.md`, probado ejecutándolo contra la sesión real y contra un repositorio de prueba |
| **7.14** | Publicar el toolkit con el sistema nuevo dentro | ⬜ sin empezar | La versión instalada sigue siendo 1.25.0, sin el sistema nuevo activo — **es el paso que desbloquea todo lo demás**, como ya explica la sección de más abajo |

## FASE 8 — La destilación (0/~~6~~ **7**, sin empezar) `[corregido 2026-08-04: faltaba 8.2b, la cosecha de zonas, decidida el mismo día — B32]`

| Paso | Qué es | Estado | Qué falta |
|---|---|---|---|
| **8.1** | Fijar la fecha de corte de un proyecto | ⬜ sin empezar | No se ha hecho para ningún proyecto |
| **8.2** | Encender la aduana en ese proyecto | ⬜ sin empezar | Depende del 8.1 |
| **8.2b** *(añadida 2026-08-04)* | La cosecha de zonas: pasada previa que no destila nada, saca los términos candidatos a zona y los presenta al propietario para que apruebe `[decisión B32]` | ⬜ sin empezar | No existe todavía — es prerrequisito de 8.3, porque sin zonas aprobadas la aduana rechaza toda nota destilada |
| **8.3** | Destilar la memoria vieja del proyecto, citando de qué commits sale cada nota | ⬜ sin empezar | El propio plan deja sin decidir quién lo ejecuta — no es un olvido, es una decisión pendiente |
| **8.4** | Repartir lo destilado en sus cinco destinos (memo, muro, regla, documentación, pregunta) | ⬜ sin empezar | Depende del 8.3 |
| **8.5** | En caso de duda, preguntar al usuario en vez de decidir solo | ⬜ sin empezar | Depende del 8.3 |
| **8.6** | Orden: primero este mismo toolkit, después un proyecto real | ⬜ sin empezar | Depende de toda la fase |

## FASE 9 — Retirar el sistema viejo (1 a medias + 3 sin empezar, de 4)

| Paso | Qué es | Estado | Qué falta |
|---|---|---|---|
| **9.1** | Sacar del fichero de hooks los que ya no sirven, sin borrar ningún fichero | 🔨 a medias, y no como paso coordinado | Tres de esos hooks (`pre-task-recall.py`, `pre-memory-dedup-gate.py`, `precompact-snapshot.py`) **ya no están ni en disco ni en el fichero de hooks** — pero se fueron con el borrado general del sistema viejo al principio de esta rama, no como resultado de ejecutar este paso. Los hooks que hay que partir en dos (`session-start-boot.py` y el resto de la lista) **siguen enteros**, sin partir, en el fichero de hooks de hoy |
| **9.2** | Decidir qué hacer, fichero a fichero, con los catorce ficheros que hay que partir en dos | ⬜ sin empezar | Ninguno de los catorce tiene esa decisión tomada como parte de este paso — aunque varios ya se partieron sueltos, como trabajo de otros puntos de esta misma deuda (los puntos 1, 4 y 6, por ejemplo) |
| **9.3** | Borrar los tests de cada pieza que se retire, a la vez que la pieza | ⬜ sin empezar | No se ha borrado ningún test del sistema viejo todavía |
| **9.4** | Leer los resultados de la sonda pendiente del sistema viejo y cerrarla | ⬜ sin empezar | No se ha hecho — afecta solo al sistema ya congelado, así que no bloquea nada de lo demás |

## Lo que no cambia de la versión anterior de esta sección

**Fases 2 y 3 — ya no impide cerrarlas nada.** ~~Moriarty atacó las dos, **dio FALLA las dos veces**, y sus hallazgos siguen sin cerrar formalmente. Es el punto **13** de esta deuda, y es la deuda más antigua viva: **anterior a todo lo que se ha construido encima**, por eso el calendario dice que construir sobre una capa sin cerrar es justo lo que ese documento existe para impedir.~~ **El punto 13 se cerró el 2026-08-04** — cuarta pasada de Moriarty, un hallazgo por capa, los dos reparados y verificados ejecutándolos. Era la deuda más antigua viva; ya no está abierta. `[corregido 2026-08-04]`

**Fase 5 — la prueba que nadie ha hecho.** El plan no acaba en construir el reparto: sus pasos 5.5 a 5.7 son **una semana de uso real con la memoria llegando solo a quien implementa**, con el criterio de éxito escrito de antemano — que Ultron diga en su informe si un muro le cambió lo que iba a hacer. Y dice, con todas las letras, que el resto de oficios entra **«solo si 5a dio señal»**. El propio plan avisa de por qué importa: *«si en una semana ninguna valla cambió nada observable, el problema no es la selección del contenido sino que lo inyectado se ignora — conclusión más valiosa que descubrirlo con el sistema entero construido»*.

**Fase 7 — la que desbloquea todo lo demás.** Hasta que no se publique la versión (paso 7.14), lo que corre en cada sesión tuya **es la copia instalada, congelada**, no este repositorio — por eso varios pasos de esta tabla no se pudieron probar con una sesión real y hubo que leer el código en su lugar.

**Y el final de todo:** con las seis capas cerradas, **Yoda juzga una vez**, con el sistema entero delante. Después, la documentación al día.

---

## Lo decidido que falta por construir

**Actualizado el 2026-08-03, más tarde el mismo día. Suite: ~~261~~ **320** verdes, cero rojos** (el número bajó desde 275 por tests retirados junto con las piezas de la Fase 5 que se borraron por la decisión B20, no por una regresión). `[recontado 2026-08-04: 320 es la cifra actual, verificada ejecutando `python3 -m pytest unmassk-toolkit/tests/memory -q`]`

| # | Qué | Estado |
|---|---|---|
| 1 | El informe por identificador | ✅ **hecho** — enseña la nota, su estado y lo que cuelga de ella |
| 2 | Los renombrados y el borrado de `bench` | ✅ **hecho** — nueve comandos |
| 3 | El comando `wip` | ✅ **hecho**, y protege la rama principal igual que `work` |
| 4 | La forma del cierre de sesión: `[NEXT]` y contexto en prosa | ✅ **hecho** |
| 5 | Los `.lock` que se limpian solos | ✅ **hecho** — con comprobación de inodo, demostrado con seis procesos reales peleándose 240 veces |
| 6 | Retirar los 3 tests del repositorio anidado | ✅ **hecho** |
| 7 | Una decisión puede nacer de otra | ✅ **hecho** |
| 8 | La aduana se enciende sola con la primera nota | ✅ **hecho** |
| 9 | El `--continue` y el `--skip` de un rebase pasan | ✅ **hecho** |
| 10 | `awaits:` en todas partes | ✅ **hecho** |
| 11 | **El arranque automático, sin subcomando** | ⬜ **falta** — `boot` ya no es subcomando, pero **nada lo dispara solo**. Hay que enchufarlo, y eso es fase 7 |
| 12 | **La deducción `note`/`work` desde el diff** | ⬜ **falta** — la aduana todavía no mira si hay código tocado para saber cuál de los dos es |
| 13 | **El rechazo con salida para `amend` y `rebase`** | 🔨 **a medias** — el texto ya está escrito (`TEXTOS.md` §1.12 y §1.13); **falta que el hook lo use** |
| 14 | **La confirmación por duplicado** de los siete comandos que borran trabajo | 🔨 **a medias** — los dos textos ya están (`TEXTOS.md` §8); **falta el mecanismo que los intercepta** |
| 15 | **El guardián de fusiones bloquea por palabra suelta** | ⬜ **falta** — frenó una nota de memoria por llevar «merge» en su descripción. Cuatro bloqueos falsos medidos en una mañana |
| 16 | **Dónde sale el resultado de los diez ataques** | ✅ **decidido y cerrado 2026-08-04 — en ningún sitio** (B27). *«Lo que consideres. Yo lo borraría todo eso.»* El catálogo **no se pierde**: sigue siendo el material de ataque de Moriarty dentro de §12bis, igual que en todas las capas cerradas hasta hoy. Lo que no hay es artefacto — y **no vuelve al arranque**, porque eso reintroduciría el automatismo recurrente que él borró con `bench` |

---

## POR DECIDIR — **vacío. No queda ninguna.**

Las cuatro que quedaban las cerró el orquestador el 2026-08-03 con delegación expresa del propietario — ver **B19**. Son revocables, y su motivo está escrito para poder discutirlo.

<details><summary>Lo que había aquí antes de cerrarse</summary>

## POR DECIDIR — lo que sigue abierto

- **Si una decisión puede nacer de otra decisión.** Hoy el tipo `D` no admite `origin`, pero el ejemplo del propio documento enseña una decisión colgando de otra. **El ejemplo que ilustra el sistema no se puede escribir con el sistema.**
- **Cómo se enciende la aduana**: hoy nace apagada y hay que encenderla proyecto a proyecto. Su pregunta, sin responder: *«¿tenemos que darle a un botón, o en cuanto se empiece a crear memoria se despierta sola?»*
- **El `--continue` / `--skip`** de un rebase a medias: hoy se bloquean y `--abort` pasa. Lo decidió un agente.
- **[pregunta] Cómo se escribe el campo del bloqueante cuando se lo enseñas a él, no a una máquina.** Dos documentos dicen cosas distintas sobre lo mismo, y no lo puedo decidir yo:
  - `PLAN-CONSTRUCCION.md` (fila 6, corregida hoy) y tu propia cita en esta misma lista (punto B11 de arriba) dicen que se lee **siempre** `awaits:`, en inglés, sin matiz.
  - `TEXTOS.md` §6, punto 4, es más fino: dice que el **informe de una zona o de una nota** (cuando pides `search billing` o `search --id I-004`) sigue enseñando **«espera:», en español** — y que **solo el arranque** (el documento que se lee al abrir sesión) pasa a «awaits:», en inglés. Los dos moldes de texto ya escritos en `TEXTOS.md` (§2.1/§2.3, con «espera:» en español, y §3.1, con «awaits:» en inglés) están construidos siguiendo esta segunda lectura, no la primera.
  - **Las dos no pueden ser verdad a la vez.** Un ejemplo de cada salida, con la misma nota (`B-002`, esperando a Marta):
    - **Lectura A — siempre en inglés:** buscas `gitmem search billing` y ves `awaits: el cliente (Marta, IT de Omawa)` en la pantalla del informe, igual que en el arranque.
    - **Lectura B — depende de dónde se mira:** buscas `gitmem search billing` y ves `espera: el cliente (Marta, IT de Omawa)`, en español, tal como sale hoy. Pero al abrir sesión, el documento del arranque muestra la misma nota como `awaits: el cliente (Marta, IT de Omawa)`, en inglés.
  - **¿Cuál de las dos quieres?** → **Cerrada: gana la lectura A**, `awaits:` en todas partes. Ver **B19**, punto 4.

</details>

---

# PARTE 2 — LO QUE ESTÁ ROTO

## Rotas a propósito, con reparación asignada

### [x] 1 · El bloque gestionado del `CLAUDE.md` se borró en vez de reescribirse — **cerrado 2026-08-02**

**Es la más grave de la lista** y la única que sale de este repo: afecta a **cualquier proyecto** donde se instale el toolkit.

`lib/managed_blocks.py` ya no produce el bloque `unmassk-toolkit` — su lista quedó en tres (protocolos, comunicación, modo de construcción). Pero **seis sitios** siguen usando la cadena `BEGIN unmassk-toolkit` como semáforo de «esto está instalado»: `upgrade_check.py:96` · `install_inspect.py:92` · `bootstrap_deps.py:278` · `git-memory-repair.py:74` · `user-prompt-memory-check.py:76` · `git-memory-doctor.py:195`.

**Qué pasa en un proyecto nuevo:** se instala → el marcador no se escribe → el sistema mira, no lo encuentra, y dice «no está configurado, ejecuta la instalación» → se ejecuta → vuelve a fallar. Bucle en cada mensaje, sin una sola excepción visible. Y en paralelo, la detección de versión vieja queda muerta: siempre dirá que estás al día.

El plan (paso **7.12**) decía **reescribirlo**, no borrarlo. Esto fue extralimitación de la cirugía.

> **Reparación:** fase 7 · reponer el bloque en el generador **o** reescribir los seis consumidores. Uno de los dos.
> **Verificación:** `python3 -c "import sys;sys.path.insert(0,'unmassk-toolkit/lib');import managed_blocks as m;print([b['begin'] for b in m.BLOCKS])"` tiene que incluir `unmassk-toolkit`, **y** `pytest unmassk-toolkit/tests/test_lifecycle.py -q` en verde.
> **Verificado 2026-08-02:** la lista de `BLOCKS` incluye `<!-- BEGIN unmassk-toolkit (managed block — do not edit) -->`. `pytest unmassk-toolkit/tests/test_lifecycle.py unmassk-toolkit/tests/test_managed_blocks.py -q` → **46 passed** (los 4 que estaban en rojo el mismo día, `test_uninstall` / `test_uninstall_full_local` / `TestBlocksDefinition::test_toolkit_block_content` / `TestUninstallFourBlocks::test_uninstall_removes_all_four_blocks`, están todos en verde ahora). Reparado en el generador.

### [ ] 2 · El arranque del proyecto manda cargar tres cosas borradas — **y NO se cierra tocando código**

**Medido el 2026-08-02, y cambia la naturaleza del punto.** El generador del bloque **ya está arreglado en el repositorio**: su cuerpo no menciona la skill borrada ni su calibración. Pero el `CLAUDE.md` de este proyecto **sí las sigue mencionando**, en las líneas 102-103, porque **el generador que corre de verdad es el de la caché instalada**, no el del repositorio:

```
generador del repo   → menciona la skill borrada: False
generador de la caché → menciona la skill borrada: True
```

Y ese generador **se ejecuta en cada arranque de sesión**, así que **reescribe el bloque con el texto viejo cada vez**. Arreglarlo otra vez en el repositorio no sirve de nada.

**La consecuencia, y vale para más de un punto de esta lista:** hay arreglos que **solo se pueden verificar publicando versión** — el vigilante de commits arreglado hoy es el otro caso, y sigue bloqueando por falso positivo en esta sesión por el mismo motivo. Es exactamente el principio P7 de la especificación: *«lo instalado se verifica contra lo escrito»*.

El síntoma original sigue siendo el mismo: `CLAUDE.md` da tres órdenes en cada sesión nueva y las tres apuntan a algo que ya no existe — cargar la skill `unmassk-gitmemory`, leer su `CALIBRATION.md` y ejecutar `git-memory-recall.py`.

> **Reparación:** fase 7, paso **7.12**, con el bloque nuevo — **y publicar versión** (paso 7.14), que es lo que hace que el arreglo llegue a correr.
> **Verificación:** las tres rutas que cite el bloque tienen que existir en disco, **comprobado contra la copia instalada**, no contra el repositorio.

### [x] 3 · La skill de cierre de sesión no hacía lo que prometía — **CERRADO 2026-08-04 (paso 7.10)**

> **Recuperó sus cuatro renglones**, los que fija la especificación §218, y van **antes** que la limpieza del proyecto — porque la limpieza se puede rehacer mañana y **lo que se habló hoy no se recupera** cuando se cierra la ventana:
>
> 1. **Escribir el Next**, con su titular de 80 y su `--context` en prosa: *lo que se habló, lo que se decidió, lo que se rompió, lo que quedó a medias, y los cabreos con su motivo*. No es un acta de lo construido —para eso están los commits—: es lo que se dijo, que no vive en ningún otro sitio.
> 2. **La issue del plan al día** — es lo que hace que el aviso del arranque se calle por el motivo correcto.
> 3. **La poda de muros**, *preguntando*: «¿alguna de estas restricciones ya no es verdad?». Nunca se retira un muro por criterio propio: está ahí porque algo se rompió una vez. Y salen **todas** en cada arranque, así que una caducada cuesta atención todos los días.
> 4. **El alta de bloqueantes**, preguntando si algo quedó parado esperando a alguien. La diferencia con un pendiente importa: un pendiente es tuyo, **un bloqueante es de otro**, y sale en cada arranque con a quién se espera para que no se pudra callado.
>
> **Y la cabecera dejó de mentir en la otra dirección:** ya no dice *«el reemplazo no está construido»* — lo está. Los comandos se invocan por ruta hasta que se publique la versión (paso 7.14), y la skill lo dice para que nadie los dé por instalados.

**Corregido 2026-08-04: el diagnóstico de abajo ya no es verdad — se conserva plegado por lo que cuenta, no por lo que cuenta bien.** `unmassk-toolkit/skills/unmassk-close-session/SKILL.md` tiene hoy **62 líneas**, no 27, y los cuatro renglones sí están escritos: **1.** el Next con su `--context` en prosa (`next.py`), **2.** la issue del plan al día, **3.** la poda de muros (preguntando, no decidiendo solo), **4.** el alta de bloqueantes — verificado leyendo el fichero completo. La cabecera además ya no dice que el reemplazo no esté construido. **Verificación real ejecutada:** el contenido del fichero cubre los cuatro pasos; no se ha comprobado con un cierre de sesión real de punta a punta, solo con la lectura del fichero.

<details><summary>El diagnóstico del 2026-08-02, conservado — describía el fichero de entonces, no el de hoy</summary>

**Parcial — la mentira concreta ya se corrigió, la función sigue sin recuperarse.** `skills/unmassk-close-session/SKILL.md` sigue en 27 líneas, pero **la cabecera ya no promete lo que no hace**: dice explícitamente *«this skill today is housekeeping only... it does NOT consolidate decisions or write a resume point — the old memory system that did that was retired on `feat/memoria-v2` and the replacement isn't built yet»*. Verificado leyendo el fichero completo el 2026-08-02: cero menciones de guardar memoria en la descripción, y el aviso de alcance es honesto.

Lo que **no** ha pasado es la segunda mitad del punto: la skill no ha recuperado su función con la memoria nueva — eso sigue en fase 7, paso 7.10.

> **Reparación:** fase 7, paso **7.10** — se parten los pasos 1-4 y gana cuatro renglones: el avance de cierre, la issue-plan al día, la poda de muros y el alta de bloqueantes.
> **Verificación:** un cierre real ejecuta los cuatro. **No pasa todavía** — esos cuatro renglones no existen en el fichero (verificado, mismo `Read` de arriba).

</details>

### [x] 4 · `stop-dod-check.py` perdió un chequeo que el plan conservaba — **cerrado 2026-08-02**

El plan autorizaba quitar dos funciones de memoria y los chequeos 4 y 5, **conservando el 1 al 3**. La cirugía dejó solo el 1 y el 2: se llevó también el **chequeo 3**, que avisaba de un `Next:` sin resolver en el último commit — el que detecta trabajo de traspaso sin cerrar.

No rompe nada en ejecución, pero es una red de seguridad menos, y justo del tipo de pérdida silenciosa que este proyecto prioriza evitar.

> **Reparación:** reponerlo, reescrito sin `sanitize_trailer_value` (cuyo import se retiró del fichero).
> **Verificación:** `grep -c "# Check" unmassk-toolkit/hooks/stop-dod-check.py` da 3. **Verificado 2026-08-02: da 3** (`# Check 1: Uncommitted changes...`, `# Check 2: Wip accumulation...`, `# Check 3: Last commit has unresolved Next:...`), y el fichero ya no importa `sanitize_trailer_value`.

### [x] 5 · El vigilante de sincronización no entraba en subcarpetas — **CERRADO 2026-08-04**

> **Comprobado ejecutándolo:** tocar `lib/memory/notes.py` **ya se detecta**. La clave de la huella pasa de ser el nombre del fichero a la **ruta relativa** (`memory/notes.py`), que es lo que impide que dos ficheros del mismo nombre en subcarpetas distintas se pisen entre sí y den una comparación que miente.
>
> **Por qué era grave ahora y no antes:** el sistema de memoria nuevo vive **entero en subcarpetas** — 31 módulos en `lib/memory/` y 10 scripts en `bin/memory/`. Los 41 eran **invisibles** para el vigilante que avisa de que la copia instalada va por detrás: se cambiaba cualquiera y seguía diciendo que todo estaba al día. Un vigilante que mira donde no está lo que vigila **da un visto bueno falso**, que es peor que no tenerlo.
>
> Se conservaron los dos comportamientos que sí eran correctos: `__pycache__` se sigue ignorando **también en subcarpetas anidadas**, y un directorio que no existe sigue devolviendo «no hay con qué comparar» en vez de una alarma falsa. 7 tests nuevos.

`lib/cache_sync_check.py::_dir_fingerprint` no es recursiva: descarta cualquier entrada que sea un directorio. Compara solo los ficheros sueltos de `hooks/`, `lib/`, `bin/` y `agents/`.

**Con el sistema nuevo esto pasa de límite conocido a agujero real**, porque sus módulos viven en `lib/memory/` y sus scripts en `bin/memory/`: tal como está, **el v2 entero será invisible** para el vigilante que debe avisar de que la versión instalada va por detrás.

No es nuevo ni lo introdujo el cambio que añadió `agents` a la lista.

> **Reparación:** antes de publicar la versión con el v2 dentro.
> **Verificación:** tocar un fichero de `lib/memory/` y comprobar que el conteo del arranque sube. ~~**Sigue sin pasar (verificado 2026-08-02):** `_dir_fingerprint()` sigue con `if not os.path.isfile(full): continue`, y `COMPARED_SUBDIRS = ("hooks", "lib", "bin", "agents")` sigue siendo plano — `lib/memory/` (23 ficheros) y `bin/memory/` siguen invisibles para el vigilante.~~ **Pasa (verificado 2026-08-04):** `unmassk-toolkit/lib/cache_sync_check.py::_dir_fingerprint()` ya no filtra directorios — recorre con `os.walk()` y usa la ruta relativa como clave, con su propio docstring citando este punto (#5) por nombre. Coincide con el callout de arriba, que ya lo daba por cerrado. `[corregido 2026-08-04: esta línea de verificación se había quedado sin actualizar cuando se cerró el punto]`

### [x] 6 · El arranque puede mandarte hacer `git pull` de un repo ajeno — **cerrado 2026-08-02**

Se retiró `check_upstream_shares_history()` con el bloque de frescura — pero **también protegía dos salidas que sobreviven**: la orden de `git pull` y la lista de ramas. Anulaba el remoto cuando no compartía historia con el repo.

**Reproducido en vivo** en un repo cuyo `origin` apunta a otro proyecto sin ancestro común: el arranque emite `PULL DIRECTIVE: local is 2 commit(s) behind` —contra un repo que `git` rechazaría con *refusing to merge unrelated histories*— y lista las ramas ajenas como si fueran de este proyecto, sin decir de dónde salen.

Es el patrón a vigilar en los trece ficheros de §5.3 que quedan por partir: **un guardián que nació para el subsistema amputado, pero que también protegía superficies vivas.**

> **Reparación:** restituir la comprobación de ancestro común para esas dos superficies.
> **Verificación:** en un repo con remoto sin historia común, el arranque no ordena `pull` ni lista ramas ajenas. **Verificado 2026-08-02**: `check_upstream_shares_history()` está de vuelta en `lib/boot_git_checks.py`, y `tests/test_boot_git_checks.py::TestBootSuppressesPullAndBranchesForUnrelatedUpstream::test_unrelated_upstream_shows_neither_pull_nor_branches` lo prueba **en vivo** (arranque real contra un repo temporal con `origin` sin ancestro común) — `pytest unmassk-toolkit/tests/test_boot_git_checks.py -q` → 41 passed, 1 skipped. Mismo test cierra el punto 18.

### [x] 7 · Dos funciones de la línea de tiempo quedaron huérfanas — **CERRADO 2026-08-04**

> **Su verificación exacta, ejecutada hoy, ya da vacío:**
> ```
> grep -rn "get_timeline\|get_last_context_time" unmassk-toolkit/lib unmassk-toolkit/hooks unmassk-toolkit/bin
> → (sin resultados)
> ```
> Lo que quedaba eran **dos comentarios** de `lib/git_helpers.py` que citaban esas funciones como ejemplo histórico de dos incidentes reales (el reintento de lectura del issue #61 y la falsificación de líneas por saltos de carro del #59). **No se han borrado: se han reescrito.** La lección que cuentan sigue valiendo y es cara; lo que sobraba era mandar a alguien a buscar dos funciones que ya no existen. Ahora lo dicen: *«se retiraron en `feat/memoria-v2` y ya no existen — la lección se mantiene, no vayas a buscarlas»*.

**La contradicción del inventario está resuelta** (2026-08-02): la especificación §8.3 y `TEXTOS.md` §3.1 fijan el arranque nuevo en **cinco bloques y ninguno es la línea de tiempo** — último avance con su contexto, bloqueantes enteros, restricciones enteras, recuentos y avisos. La fila del inventario que decía «se queda» estaba mal.

Y lo que se temía perder está cubierto y mejor: el bloque de **avisos habla siempre**, con sus visto bueno y su número (`✓ IDs sin duplicados (68 notas)`), aunque no pase nada. Demuestra que el arranque leyó de verdad, igual que hacía la línea de tiempo, y encima dice algo útil.

Queda solo la limpieza: `get_timeline()` y `get_last_context_time()` siguen en `boot_git_checks.py` con **cero llamadores** — cierto para las llamadas, pero `lib/boot_checks.py` sí las **importaba** por nombre (`from boot_git_checks import (..., get_timeline, get_last_context_time, ...)`, más su entrada en `__all__`) y las volvía a exportar sin que nadie las consumiera después. Retirarlas de `boot_git_checks.py` sin tocar también ese import habría reventado el `ImportError` en cadena `boot_checks.py` → `boot_health.py`/`boot_render.py` → `session-start-boot.py` — el arranque entero, no solo un test. 112 líneas muertas en total entre las dos.

> **Reparación:** retirar las dos funciones **y** su import/`__all__` en `lib/boot_checks.py`, en el mismo cambio.
> **Verificación:** `grep -rn "get_timeline\|get_last_context_time" unmassk-toolkit/lib unmassk-toolkit/hooks unmassk-toolkit/bin` vacío. **No pasa todavía (verificado 2026-08-02):** el `import boot_checks` ya no revienta (las dos funciones y su entrada en `__all__` sí se retiraron de `lib/boot_checks.py`), pero el grep **no da vacío** — quedan 2 coincidencias, las dos en `lib/git_helpers.py` (líneas ~852 y ~901), y las dos son **comentarios** que citan el nombre de las funciones como ejemplo histórico de un incidente (issue #61), no una llamada ni un import real. Funcionalmente cerrado; el grep literal, no.

### [x] 8 · `lib/boot_fetch_stamp.py` — 357 líneas huérfanas, en ninguna lista — **cerrado 2026-08-02**

Su único consumidor era el bloque de fetch recién amputado. Cero importadores en producción y en tests. **No aparece en ninguna de las cuatro listas del inventario del plan.**

> **Reparación:** decidir si se retira. Medido por Bilbo contra HEAD: ahí estaba vivo; quedó huérfano como consecuencia del plan, no por error del cirujano.
> **Verificación:** decisión tomada — el fichero se retiró. `ls unmassk-toolkit/lib/boot_fetch_stamp.py` → no existe (`git status` lo marca `D`, borrado en el árbol de trabajo, sin commitear todavía). `grep -rn "^import boot_fetch_stamp\|from boot_fetch_stamp"` vacío en todo el repo — lo que queda son 5 comentarios/docstrings que lo citan como referencia histórica de patrón (temp-file-then-replace), no imports.

### [x] 9 · Un test bloquea la cobertura del banner del arranque — **cerrado 2026-08-02**

`tests/test_boot_output.py:1052` llama a `render_boot_banner_lines()` con diez argumentos y la firma nueva admite nueve. Eso deja **sin cobertura** dos guardas que siguen vivas: el recorte de nombres de rama largos y el presupuesto de bytes de la salida.

> **Verificación:** `pytest unmassk-toolkit/tests/test_boot_output.py -q` en verde. **Verificado 2026-08-02: 30 passed.** El propio fichero documenta el arreglo citando este punto: *"ARREGLADO (PLAN-CONSTRUCCION.md paso 9.3 / DEUDA.md punto 9): el call... usaba un `""` de más antes de `pull_directive_lines`"* — el arreglo fue solo en el test, `render_boot_banner_lines()` no cambió.

---

## Del sistema nuevo — huecos declarados durante la construcción

### [x] 10 · Dos funciones declaradas y sin implementar — **cerrado 2026-08-02**

`lib/memory/notes.py` declara `replace()` y `close()` con su firma exacta, y las dos **lanzan un error de «no implementado»**. Se dejaron así a propósito: ninguno de los seis tests del contrato las cubre, y su comportamiento real —si la sustitución es una transacción o dos, qué forma exacta tiene la línea que se archiva— **no lo fija ningún texto**. La regla del proyecto dice que un hueco puede ser deliberado y no se rellena adivinando.

Pero son la mitad del ciclo de vida de una nota: sin ellas no se puede sustituir ni retirar nada.

> **Reparación:** cerrar su contrato en `PIEZAS.md` §8.1 —con sus filas de test— y luego implementarlas.
> **Verificación:** `grep -n NotImplementedError unmassk-toolkit/lib/memory/notes.py` vacío. **Verificado 2026-08-02: vacío.** `replace()`/`close()` están implementadas (decisión 5 del docstring del módulo); `pytest unmassk-toolkit/tests/memory/test_notes.py -q` → ~~15~~ **25** passed `[recontado 2026-08-04]`, incluidos los tests de `replace`/`close`.

### [x] 11 · Cuatro funciones exportadas sin un solo test — **CERRADO 2026-08-04**

> **Las cuatro están cubiertas.** `gitcmd.commit` tiene test directo; `indexes.remove` e `indexes.archive` tienen llamador real de producción (`notes.replace()`/`close()`) con su cobertura; y la última que quedaba, **`gitcmd.repo_root`**, tiene ya dos tests propios (2026-08-04) — `test_gitcmd.py` pasa de 7 a **9 en verde**.
>
> **Por qué esa última importaba más que las otras tres:** `repo_root()` es la que decide **en qué repositorio escribe el sistema**, y orientarse mal ahí ya costó **70 commits falsos** en esta rama. Una función que decide dónde se guarda la memoria y que nadie miraba de frente era el patrón exacto que este proyecto declara como su enfermedad.
>
> Los dos tests comparan contra `git rev-parse --show-toplevel` **ejecutado aparte**, nunca contra una ruta escrita a mano: desde una subcarpeta devuelve la raíz, y fuera de un repositorio lanza con el mensaje real de git dentro. **Ninguno nació en rojo** — la función ya era correcta, y no había desfase entre su código y su contrato.
>
> **Y lo que este punto pedía de fondo SE CONSTRUYÓ el mismo día** `[2026-08-04]`: los tres tests de frontera de `PIEZAS.md` §13 existen y corren con la suite. **Encontraron algo real en su primera ejecución** — que `note.py --replaces` no archivaba la nota vieja, dejando dos decisiones vigentes contradiciéndose. Cuatro revisores habían dado esa capa por buena.
>
> **Y el detector evolucionó el mismo día, por una idea del propietario:** en vez de una lista de huérfanos —que obligaba a mantener una lista de perdonados, puerta trasera esperando a que alguien la ampliara— da **dos números por símbolo**: cuántos ficheros de producción lo usan desde fuera, y cuántos tests lo tocan. *«Una función tiene que tener dos ramitas mínimo.»*
>
> **Grita solo con las dos ramas a cero.** Producción a cero con tests **no es grasa**: es una herramienta de contraste, algo que solo usan los tests para comprobar otra pieza. Esa distinción salvó hoy tres funciones que sostenían **quince** comprobaciones, y **dos retiradas ya estaban en marcha** cuando se descubrió.
>
> **El propio detector tenía dos puntos ciegos, encontrados en su primera hora:** no veía los tests que reciben un módulo con otro nombre —`format.py` llega siempre como `fmt`, porque choca con una palabra de Python—, ni los que viven dentro de una caja, que aquí son **14 ficheros de 36**. Los dos cerrados, cada uno con su prueba de que cuenta bien **y** de que no cuenta de más. **La herramienta que se construyó para no fiarse de nadie tampoco se comprueba sola.**

`gitcmd.commit` · `gitcmd.repo_root` · `indexes.remove` · `indexes.archive`.

Existen, se exportan, y **ninguna tabla de contrato pidió un test para ellas**. Es la definición exacta de lo que el sistema anterior acumuló hasta las 590 líneas inútiles — y `indexes.archive` es especialmente delicada porque toca el fichero donde va a parar todo lo retirado.

> **Reparación:** o se les escribe test, o se retiran si nadie las llama.
> **Verificación:** el test de frontera (§13) las caza solo — una función exportada sin importador pone la suite en rojo. **No pasa (verificado 2026-08-02):** ninguno de los tres tests de frontera de §13 ni la puerta §13.1 (grafo generado) existen todavía como código — `find unmassk-toolkit/tests -iname "*frontier*" -o -iname "*boundary*" -o -iname "*graph*"` vacío, sin `ARQUITECTURA.md` mermaid generado. Mejora parcial de las cuatro: `gitcmd.commit()` sí tiene test directo ahora (`tests/memory/test_gitcmd.py:403`); `indexes.remove`/`indexes.archive` ya tienen **llamador real de producción** (`notes.py::replace()`/`close()`, líneas 430/461/517/523) con cobertura transitiva vía `test_notes.py` (15/15 verde); `gitcmd.repo_root` sigue sin un test propio, solo se ejecuta de paso dentro de otras pruebas.

### [x] 12 · `format.py` pasa de su techo — **cerrado 2026-08-02**

519 líneas, y el contrato pone el límite en 500. No es la única — ver el punto 14, `validator.py` se pasa aún más. El límite existe para que ninguna acabe siendo la que nadie se atreve a abrir.

> **Verificación:** `wc -l unmassk-toolkit/lib/memory/format.py` por debajo de 500. **Verificado 2026-08-02: 423 líneas.** Se partió en `format.py` (423) + `format_lines.py` (154); `pytest unmassk-toolkit/tests/memory/test_format.py -q` en verde.

### [x] 13 · Las capas 2 y 3 — **CERRADO 2026-08-04: secuencia completa, con dos hallazgos reparados**

> **La cuarta pasada de Moriarty se hizo el 2026-08-04, una por capa, en paralelo, y las dos encontraron algo.** Con sus reparaciones verificadas por el orquestador ejecutándolas, la secuencia de `PIEZAS.md` §12bis queda completa en las dos capas y **este punto se cierra**. Era la deuda más antigua viva de este documento.
>
> **Capa 2 — veredicto FALLA.** `validator_pointers.py`: un puntero `Origin` con forma de identificador **pero mal escrito** —minúscula (`d-030`) o con un espacio de sobra— **no casaba el patrón**, y por eso se eximía de toda comprobación igual que un hash de commit del sistema viejo. La nota se guardaba **enlazada a nada**, sin un solo aviso, y el racimo del informe no la agruparía jamás con su origen. En un muro era doble: se saltaba también la exigencia de citar la incidencia. **Reparado** (Dante 4 tests en rojo → Ultron): la forma se reconoce ignorando mayúsculas y espacios, pero la existencia se comprueba **sin normalizar**, así que un identificador mal escrito rebota como puntero colgante. **El hash del v1 sigue eximido** — verificado, era la condición de no romperlo.
>
> **Capa 3 — veredicto DÉBIL.** `notes_commit.py::write_work()`: cuando `known_content` traía `None` para una ruta —lo que `work.py` y `wip.py` producen, **y documentan palabra por palabra**, cuando su lectura previa falla por permisos— la función no caía a leer el disco como prometía su propio contrato: rechazaba el commit **culpando a otro proceso que no existía**. Reproducido con **un solo actor**. Y con un directorio en vez de un fichero, escapaba una traza de pila cruda, contra la regla de §10 (*«nunca imprimen una traza de pila»*). **Reparado** (Dante 2 tests en rojo → Ultron): cae a leer el disco, y cualquier `OSError` sale como fallo limpio con su causa.
>
> **Ninguna de las dos capas perdió memoria ni dio un «todo bien» sobre una mentira** — las tres condiciones que este documento fija para un FALLA grave. Lo encontrado fue: una nota que se cree enlazada y no lo está, y un rechazo legítimo con un diagnóstico inventado.
>
> **Y el eje que llevaba esto parado desde el 2026-08-02 —la concurrencia— quedó fuera por decisión del propietario** (PARTE 1, **B22**): *«no va a pasar nunca»*. Sin él, Moriarty gastó la pasada entera en lo que sí puede pasar, y encontró dos cosas que cuatro revisores anteriores habían dado por buenas.

<details><summary>El estado anterior, conservado — tres pasadas de Moriarty y por qué no cerraban</summary>

#### Las capas 2 y 3 no han pasado la revisión completa

Solo la **capa 1** completó la secuencia entera de `PIEZAS.md` §12bis con sus tres pasadas. Y no fue simbólico: Cerberus y Argus sacaron ocho cosas, y **Moriarty encontró dos más que a ellos se les escaparon** — una de ellas, pérdida silenciosa de notas con los cincuenta y siete tests en verde.

Las capas 2 y 3 —once piezas, incluidos el validador y la transacción, que son las dos que más pueden corromper— **ya pasaron por Cerberus y Argus, con sus hallazgos cerrados**. Lo que queda pendiente es **Moriarty**, que de momento solo ha revisado la capa 1.

> **Verificación:** las tres pasadas hechas en las capas 2 y 3 (Cerberus, Argus y Moriarty), y sus hallazgos cerrados, con los fallos fijados como regresión. **No pasa (verificado 2026-08-02, memoria de Moriarty leída directamente):** Moriarty ya está atacando la capa 2 y la 3, pero **ningún ataque ha dado veredicto limpio todavía** y sus hallazgos siguen abiertos, no cerrados:
> - **Capa 2** (`gitcmd`+`ids`+`rejection`, ronda acotada — `validator.py` no estaba escrito cuando atacó): veredicto **FALLA**, 2 T1 confirmados en vivo. Uno sigue reproducible hoy mismo: `gitcmd.commit()` no declara su propio `cwd` («hereda el cwd ambiental del proceso», docstring sin cambios, línea ~135) — el PoC de dos hilos de Moriarty (un `chdir` a otro repo en la ventana de una llamada relativa) sigue aplicando tal cual está el código.
> - **Capa 3** (`notes`+`query`): veredicto **FALLA**, 3 T1 + 2 DECEPTION confirmados (SIGKILL entre `indexes.insert()` y el registro, un `write_work()` sin candado, más).
> Con la capa 1 costó ocho hallazgos de Cerberus/Argus y dos más de Moriarty (uno de ellos, pérdida silenciosa de notas con 57 tests en verde) — el precedente es que esta pasada normalmente encuentra algo real, y aquí ya lo ha encontrado dos veces.

**Segunda pasada de Moriarty sobre las dos capas, 2026-08-03. Veredicto: FALLA otra vez.** Tres de sus hallazgos anteriores **caen con prueba** y uno **empeora**:

| Hallazgo anterior | Estado hoy |
|---|---|
| `gitcmd.commit()` sin `cwd` propio | **CERRADO.** Repetida la carrera de dos hilos (uno commitea, otro cambia el directorio a mitad): con `cwd` explícito el commit aterriza siempre en el repositorio correcto, y `notes_commit.py:195` —su único llamador de producción— siempre lo pasa |
| `rejection.build()` construía rechazos mutilados en silencio | **CERRADO.** Con partes vacías ahora lanza; y `validator.py` —el productor real, que no existía cuando se encontró— nunca le pasa un valor vacío |
| Muerte del proceso entre escribir el índice y commitear | **Su mitad silenciosa, CERRADA por rebote.** El agujero sigue (un `SIGKILL` no lo atrapa ningún `except`), pero `health.coherence()` lo detecta con nombre y apellido y **sale en el arranque**: `⚠ índices no coherentes con git (1 líneas / 0 notas) — M-001: está en el índice pero no existe en git`. Y `reindex.py` lo repara. Ya no es memoria perdida en silencio: es memoria perdida, avisada y reparable |
| `ids.next_id()` — TOCTOU vía llamador directo | **Sin cambios.** Sigue abierto solo como advertencia: ningún llamador real lo dispara hoy |
| **`write_work()` sin candado** | **VIVO, y es peor de lo que se creía** — ver el punto **27** |

**Tercera pasada de Moriarty sobre las dos capas, 2026-08-03 — la que este mismo documento llamó «tercera y final».** Veredicto: **FALLA otra vez**, con tres hallazgos nuevos. **Corrección importante sobre este mismo punto: no es cierto que «el único que quedaba vivo era el punto 27» — la tercera pasada encontró tres cosas, no una, y solo dos de las tres están cerradas hoy.**

| Qué encontró Moriarty en la tercera pasada | Estado verificado hoy |
|---|---|
| **El candado de `gitcmd.file_lock()` (reescrito), puesto a prueba a fondo** | **AGUANTA.** 6 procesos reales × 60 iteraciones con la sección crítica ensanchada, cero violaciones de exclusión mutua, y sobrevive a un `SIGKILL` real de quien tiene el candado a mitad — el siguiente lo coge limpio, sin bloqueo muerto |
| **Hallazgo nuevo (bandera, con engaño):** dos llamadas normales a `write_work()`, sin ningún intruso, sobre el mismo fichero — **55% (11 de 20)** con contenido cruzado bajo `ok=True` | **CERRADO** — es exactamente el punto **27** de esta lista, con el arreglo de `known_content` y **0 de 60** verificado |
| **Hallazgo nuevo:** un intruso que nunca llama a `write_work()` (solo escribe en disco, sin `git add`) sigue colándose — la comprobación de «fichero nuevo en el índice» no mira el contenido del árbol de trabajo | **NO CERRADO.** El propio `notes_commit.py` lo admite en su docstring: la ventana se estrechó (ahora es entre que el script lee el fichero y llama a la función, no toda la vida del proceso), pero **«no eliminado»**. Afecta a los dos llamadores reales de hoy, `work.py` y `wip.py` |
| **Hallazgo nuevo, en una pieza distinta:** `bin/memory/rezones.py --rebuild` reparaba los índices en disco pero **nunca lo comiteaba** (`indexes.py` no comitea nada, por contrato) — un `git checkout` sobre el índice reparado borraba la reparación en silencio, sin ningún aviso, y `health.coherence()` no lo detectaba porque compara disco contra git, nunca lo comiteado contra el árbol de trabajo | **CERRADO** — nueva pieza `lib/memory/rezones_commit.py`, mismo candado y misma mecánica de transacción que el resto del sistema. **Verificado por mí en vivo, hoy**: repo de prueba, nota sembrada, índice corrompido a mano, `rezones.py` la repara y queda un commit nuevo (`git log` lo muestra), y tras un `git checkout --` sobre el fichero reparado **la reparación sigue ahí** — no se pierde |

**Por qué el punto 13 sigue abierto — de dos motivos queda uno** `[actualizado 2026-08-04]`**:**

1. ~~**El hallazgo del intruso puro (fila 3) sigue vivo**, admitido por el propio código, no solo estrechado.~~ **CERRADO el 2026-08-04 por decisión del propietario** (PARTE 1, **B22**): *«no va a pasar nunca»*. Exige dos escritores a la vez sobre el mismo fichero, y no los hay — el propietario trabaja en una sola ventana. Se cierra como caso descartado, igual que el punto 25 y por el mismo criterio, no con un arreglo. Con él caen los puntos **27** y **28**, que son la misma familia.
2. ~~**Nadie ha vuelto a atacar los dos arreglos del 2026-08-03 con una cuarta pasada de Moriarty.**~~ **HECHO el 2026-08-04**, una pasada por capa, en paralelo. Las dos encontraron algo real y las dos están reparadas — el detalle, arriba. Con eso, la secuencia de §12bis queda completa y el punto se cierra.

</details>

### [x] 14 · `validator.py` también pasa del techo — **cerrado 2026-08-02**

549 líneas, y el contrato pone el límite en 500. El punto 12 de esta lista solo cita `format.py` (519) — `validator.py` se pasa aún más y se quedó sin anotar.

> **Reparación:** partirlo o revisar el límite, igual que el 12.
> **Verificación:** `wc -l unmassk-toolkit/lib/memory/validator.py` por debajo de 500. **Verificado 2026-08-02: 465 líneas.** Se partió en `validator.py` (465) + `validator_zones.py` (130); `pytest unmassk-toolkit/tests/memory/test_validator.py -q` en verde.

### [x] 15 · El bloque de estado del `CLAUDE.md` se borró solo al arrancar — **CERRADO 2026-08-04**

> **Comprobado ejecutándolo**, con las dos mitades que decidían si el arreglo servía:
> - Con texto escrito a mano dentro de un bloque gestionado, el arranque **lo dice y lo devuelve entero**: *«previous content between the markers was overwritten, recovered verbatim here: …»*. **Se puede recuperar**, que era la condición — un aviso que dijera «había algo y lo he borrado» sin decir qué, no salva nada.
> - En un arranque normal **no dice nada**. Si el único cambio es de espacios, se calla. Un vigilante que grita cada día se ignora, y entonces no vigila.
>
> **La decisión, tomada por el orquestador** `[2026-08-04, revocable]`**: avisa y sobrescribe, no se niega.** De las dos salidas solo una es viable: negarse dejaría ese bloque **congelado para siempre**, y regenerarlo en cada arranque es justamente su función — un generador que se planta al primer texto ajeno rompe la instalación en todos los proyectos.
>
> El aviso viaja por el canal que ya existía, lo que devuelve la función, sin cambiar su forma ni tocar a sus llamadores.

Es el fallo más ilustrativo del día porque es exactamente el modelo de amenaza del proyecto —el sistema rompiéndose a sí mismo, en silencio— y ocurrió en el propio toolkit, no en el sistema nuevo. Los hechos, verificados: el bloque se escribió anclado en `## unmassk-toolkit Active`, que está **dentro** del bloque gestionado `unmassk-toolkit`; `lib/managed_blocks.py::upsert_managed_blocks` reescribe todo lo que hay entre un marcador `BEGIN` y su `END`; al arrancar la sesión siguiente el generador regeneró su bloque y se llevó por delante el texto, **sin aviso y sin dejar rastro** (no estaba commiteado). Se recuperó del transcript y se ha recolocado por encima del primer `BEGIN`, fuera de todos los marcadores, con un comentario que lo explica.

> **Reparación:** decidir si el generador debe **avisar** cuando va a sobrescribir contenido que no escribió él, en vez de tragárselo callando.
> **Verificación:** escribir una línea de prueba dentro de un bloque gestionado, disparar el generador, y comprobar que avisa en vez de borrarla en silencio. **Sigue sin pasar (verificado 2026-08-02):** `grep -n "warn\|unexpected\|ajeno\|foreign" unmassk-toolkit/lib/managed_blocks.py` vacío — `upsert_managed_blocks()` sigue sustituyendo todo lo que hay entre `BEGIN`/`END` sin comprobar si lo de dentro es suyo.

---

## Revisión línea por línea, seis pasadas (2026-08-02)

### [x] 16 · El wrapper de commits no validaba el contenido — **CERRADO 2026-08-04**

> **Comprobado ejecutándolo contra un repositorio de verdad**, contando los commits antes y después, no fiándose del código de salida:
> ```
> memo normal                → guardado    (los commits suben)
> Memo=deadend -  (vacío)    → rebota, código 2, NINGÚN commit creado
>   Error: empty Memo description: 'deadend -'.
>          Must be: 'category - description' with a non-empty description
> ```
>
> **Se repuso solo la mitad que el plan nunca autorizó a quitar.** La función original hacía dos cosas y se fue entera: validar la categoría *(autorizado, no vuelve)* y comprobar que la descripción no quedara vacía tras sanear *(no autorizado — es esto)*. **La lista de categorías no se repone**: `MEMO_CATEGORIES`/`REMEMBER_CATEGORIES` no existen ya en ningún sitio, y inventar una aquí sería rellenar un hueco por criterio propio.
>
> **Por qué corría prisa:** este wrapper **es la vía de escritura viva** hasta el día del corte — el que guarda la memoria en cada sesión. Y por lo mismo era el arreglo con más riesgo de todos: endurecerlo de más habría dejado de guardar memoria, callando, hasta que alguien lo notara días después. De ahí los dos controles en verde que exigen que una descripción de verdad **sí** se guarde.

`_validate_trailer_content()` se fue de `bin/git-memory-commit.py` en el mismo commit que retiró las categorías (`578177a`, sobre `e2dafbe`). El plan (`PLAN-CONSTRUCCION.md` §5.3, fila de `bin/git-memory-commit.py`) autorizaba quitar «categorías» — pero esa función hacía dos cosas en una: validar la categoría **y** comprobar que la descripción no quedara vacía tras `sanitize_trailer_value()` (el caso de una descripción hecha solo de control-bytes, hallazgo de Cerberus del 2026-07-25). Solo lo primero estaba en el plan.

Importa porque **el sistema viejo sigue siendo la vía de escritura viva** hasta el día del corte: hoy mismo se puede escribir una entrada de memoria con `Memo=categoriainventada - x` o con la descripción vacía y el commit se crea igual. Antes fallaba en cerrado — exit 2, sin commit —; ahora pasa. Su test (`test_wrapper_trailer_content_validation_contract.py`) se borró con la función, así que tampoco hay red.

> **Reparación:** reponer `_validate_trailer_content()` (o equivalente) mientras este wrapper siga siendo la vía de escritura viva.
> **Verificación:** un commit con `--trailer "Memo=categoriainventada - x"` es rechazado (código de salida distinto de 0, sin commit creado); una descripción vacía tras sanear también. **Sigue sin pasar (verificado 2026-08-02):** `grep -n "_validate_trailer_content\|def _validate" unmassk-toolkit/bin/git-memory-commit.py` no encuentra la función (solo `_validate_path_args`, que es otra cosa). Su test sigue borrado — solo queda el `.pyc` cacheado de `test_wrapper_trailer_content_validation_contract`, no el `.py` fuente.

### [x] 17 · El arranque calculaba «vas N por detrás» sin confirmar el remoto, y no lo decía — **CERRADO 2026-08-04**

> **Ahora lo dice, comprobado ejecutándolo:**
> ```
> PULL DIRECTIVE: local is 2 commit(s) behind (not confirmed against a fresh remote check) — ...
>
> BRANCHES (origin):
>   (not confirmed against a fresh remote check — reflects the last fetch)
> ```
>
> **El texto se eligió para que se entienda sin saber qué es un `fetch`:** dice que el dato no está comprobado contra el remoto, no habla de referencias caducadas. En inglés porque las dos etiquetas que acompaña —`PULL DIRECTIVE` y `BRANCHES`— lo están, según la regla **B11**.
>
> **No se ha vuelto a consultar la red.** Quitar el `fetch` del arranque fue una decisión del plan y no se revierte: lo que se arregla es que el texto **diga la verdad sobre lo que sabe**. Antes daba un número con la misma seguridad de siempre pudiendo ser de hace días — mentía por omisión, que es la única amenaza que este proyecto declara.
>
> **Un detalle que decidió la forma:** los tests ya en verde fijan que la directiva es **una sola línea**, así que el aviso entró dentro de ella. Y en la sección de ramas se puso deliberadamente con un formato que **no** parezca una rama más, porque el control que limita cuántas se enseñan cuenta como rama toda línea con esa forma — habría inflado ese recuento en silencio.

El `git fetch` del arranque se retiró — con autorización del plan (§5.3, fila de `hooks/session-start-boot.py`: «el fetch» se va) — y `run_preboot_migrations()` lo confirma en su propio docstring: *"this function no longer performs any network I/O"*. Pero las dos salidas que antes se apoyaban en un fetch reciente siguen calculándose igual: `get_ahead_behind()` (`lib/boot_git_checks.py:267`) solo hace `git rev-list HEAD...<upstream>` sobre refs locales, y `get_remote_branches()` (`:404`) lee `refs/remotes/<remote>/*` tal como quedaron del último fetch — que puede ser de días. Ni la línea `PULL DIRECTIVE` (`_build_pull_directive_lines()`, `:304`) ni la sección `BRANCHES` (`render_branches_section()`, `:474`) dicen en ningún sitio que ese dato no está confirmado contra el remoto real. No revienta: miente por omisión con la misma seguridad de siempre, que es justo la única amenaza que este proyecto declara.

Distinto del punto 6: el 6 es un remoto AJENO sin historia común — el arranque recomienda `pull` contra el repo equivocado. Este es el remoto CORRECTO, pero con datos que pueden llevar días sin refrescar y nada lo avisa.

> **Reparación:** o esas dos salidas avisan de que el dato no está confirmado contra el remoto, o se retiran mientras no haya fetch en el arranque.
> **Verificación:** el texto que emiten `_build_pull_directive_lines()` y `render_branches_section()` incluye un aviso de frescura no confirmada, o esas salidas se retiran mientras no haya fetch. **Sigue sin pasar (verificado 2026-08-02):** las dos funciones están sin cambios respecto a lo descrito — `_build_pull_directive_lines()` (línea 277) sigue sin ninguna mención de frescura, y las dos siguen calculando sobre refs locales sin fetch previo.

### [x] 18 · Se perdió la única prueba de que el arranque no recomiende `pull` contra un repositorio ajeno — **cerrado 2026-08-02**

`tests/test_boot_freshness_regression.py` se borró completo — de los trece ficheros de tests borrados es el único mixto. Casi todas sus clases probaban código ya muerto (`fetch_memory_ref()`, `render_memoria_stamp()`, el sello `REMOTE_PROVENANCE_LABEL`, todo lo que ya no existe), y ese código sí murió con ellas sin problema. Pero `TestCheckUpstreamSharesHistoryDirect` y `TestPullDirectiveGapForUnrelatedUpstream` probaban `check_upstream_shares_history()` directamente y el gap ya conocido (marcado `xfail`) de que el `PULL DIRECTIVE` no distingue un remoto sin historia común. El fichero de reemplazo, `tests/test_boot_git_checks.py`, lo dice en su propio docstring: solo salvó lo que sigue vivo — `get_ahead_behind()`, `_build_pull_directive_lines()`, `time_ago()`, y el `run_git()` genérico — y **no tiene ningún test para el caso de remoto sin historia común**. El fallo que ese caso vigilaba es exactamente el punto 6 de esta misma lista, ya reproducido en vivo; ahora está sin red.

> **Reparación:** junto con el punto 6 — el mismo arreglo debe traer de vuelta su test.
> **Verificación:** existe un test que se pone rojo si el arranque ordena `pull` o lista ramas de un remoto sin historia común. **Verificado 2026-08-02**: `tests/test_boot_git_checks.py::TestBootSuppressesPullAndBranchesForUnrelatedUpstream` (su propio docstring dice literalmente *"DEUDA.md #6/#18 regression"*) — corre un arranque real contra un repo temporal con `origin` sin ancestro común y comprueba que ni `git pull` ni la sección `BRANCHES` aparecen en la salida.

### [x] 19 · La tabla de tests de `health.py` cubre una de sus cuatro funciones — **cerrado 2026-08-02**

`PIEZAS.md` §9.4 declara la superficie de `lib/memory/health.py` en cuatro funciones — `coherence`, `duplicates`, `plans_unreflected`, `build` — pero su tabla «Sus tests» tiene tres filas y las tres describen el mismo chequeo: la divergencia de `coherence()` entre índice y git, en los dos sentidos, más el caso «todo correcto, salen los números». Ninguna fila menciona `duplicates()`, `plans_unreflected()` ni `build()`. Como `health.py` todavía no está implementado, nacería con tres de sus cuatro funciones exportadas y sin un solo test escrito para ellas — el mismo patrón que ya recoge el punto 11 de esta lista, una capa más arriba.

> **Reparación:** añadir a la tabla una fila de test por cada función que el contrato declara.
> **Verificación:** el contrato de §9.4 tiene fila de test para `coherence`, `duplicates`, `plans_unreflected` y `build`. **Mejoró, no cierra (verificado 2026-08-02):** `PIEZAS.md` §9.4 ya tiene fila de test para `coherence` (3 filas + una cuarta añadida para el caso de nota archivada legítima) y para `plans_unreflected` (4 filas, añadidas 2026-08-02) — y `pytest unmassk-toolkit/tests/memory/test_health.py -q` corrobora la implementación real: **13 passed**, cubriendo `coherence`, `coherence_rules` (función nueva, tampoco estaba en la lista original del punto) y `plans_unreflected`. ~~**`duplicates()` y `build()` siguen sin una sola fila en la tabla ni un solo test**~~ — **CERRADO al final del día:** `pytest unmassk-toolkit/tests/memory/test_health.py -q` da **15 tests**, y las cuatro funciones tienen cobertura: `build()` la ejercitan los cinco tests de `test_boot.py` (el arranque no existe sin ella) y `duplicates()` se escribió reutilizando `ids.find_duplicates`, cerrando de paso la huérfana que `ids.py` llevaba declarando desde su primer día. Lo que sigue abierto de esta familia es el punto 11 — `grep -n "def test_" tests/memory/test_health.py` no tiene ningún test con esos nombres.

---

## Del mismo día, encontradas en la revisión del 2026-08-02

### [x] 20 · Los ocho índices se escribían en la raíz del repositorio, y su restauración apuntaba al mismo sitio equivocado — **cerrado 2026-08-02**

`notes.py::write()`/`replace()`/`close()` pasaban la raíz PELADA del repositorio directamente a `indexes.seed()`/`insert()`/`remove()`/`archive()`, en vez de `.claude/project-memory/` — su sitio real, junto a `zones.json`. Los siete índices vigentes y `ARCHIVED.md` aparecían sueltos en la raíz. Y de paso, esto destapó un segundo fallo encadenado: la restauración tras un commit fallido (`_restore_index_best_effort()`) usaba la misma raíz equivocada, así que si el commit fallaba, `indexes.remove()` buscaba el fichero donde no estaba, reventaba con `FileNotFoundError`, y esa excepción se tragaba en silencio (mejor esfuerzo) — la línea de índice quedaba huérfana sin que nadie lo notara.

> **Reparación:** `pm_root(root)` (`notes.py`, junto a `zones.json`) en las cuatro llamadas de escritura y en la restauración, dejando el candado y el `git add`/`git commit` anclados a la raíz pelada (que es donde vive `.git/`).
> **Verificación:** `notes.py::pm_root()` devuelve `Path(root) / ".claude" / "project-memory"`, y `_restore_index_best_effort()` recibe `pm` (no `root`) explícitamente documentado en su propio docstring. **Verificado 2026-08-02:** los dos arreglos están en el código (líneas 218 y 240-246 de `notes.py`); `tests/memory/test_notes.py` usa `notes.pm_root(root)` en cada punto de lectura/escritura de índices (17 sitios) y pasa completo: `pytest unmassk-toolkit/tests/memory/test_notes.py -q` → ~~15~~ **25** passed `[recontado 2026-08-04]`.

### [x] 21 · Un test escribió 70 commits falsos y dejó 8 ficheros sueltos — **CERRADO 2026-08-04**

> **«Me dan igual esos commits, son basura, me la pela.»** `[propietario, 2026-08-04 — PARTE 1, B25]`
>
> **No se reescribe la rama.** Los 70 commits se quedan en el historial: son ruido, no estorban, y reescribir con toda la obra sin commitear es un riesgo desproporcionado para limpiar basura.
>
> **Los 8 ficheros sueltos ya no están** — comprobado el 2026-08-04 listando la raíz: solo quedan `CHANGELOG.md`, `CLAUDE.md`, `DEUDA.md`, `README.md`, `ROADMAP.md` y `TOOLKIT.md`. Desaparecieron en algún momento posterior a la medición del 2026-08-02, así que la mitad de este punto se cerró sola.
>
> **Lo que de verdad cerraba este punto ya estaba hecho: la causa.** Las llamadas que escribían contra el repositorio real van envueltas, y hay una red nueva —`tests/memory/conftest.py::_guard_against_writing_to_the_real_repo`— que compara el `HEAD` real antes y después de **cada** test y falla en el acto si cambió. Eso es lo que impide que vuelva a pasar; los 70 commits eran solo la cicatriz.

Cuatro filas de siembra en `test_notes.py` (antiguas filas 7-10, cinco llamadas a `notes.write()`) invocaban esa función **fuera** del `with _cwd(root):` que envuelve el resto del fichero. `notes.write()` resuelve el repositorio por el cwd del proceso — sin ese envoltorio, escribía contra este mismo repositorio. Resultado medido por el propio proyecto: **70 commits falsos** en la rama (uno por ejecución de la suite completa) y **8 ficheros de índice sueltos en la raíz**.

> **Verificación de la causa (arreglada):** `grep -n "notes.write(" unmassk-toolkit/tests/memory/test_notes.py` — todas las llamadas están envueltas en `with _cwd(root):`. **Verificado 2026-08-02: así es**, sin excepción. Además hay una red nueva: `tests/memory/conftest.py::_guard_against_writing_to_the_real_repo` (fixture `autouse=True`) compara el SHA de `HEAD` del repositorio real antes y después de **cada** test, y falla en el acto si cambió — su propio docstring cita este incidente por nombre y número (70 commits, 8 ficheros). `pytest unmassk-toolkit/tests/memory -q` corrido dos veces no movió `HEAD` del repositorio real ninguna de las dos.
> **Lo que NO está resuelto:** los 70 commits siguen en el historial de la rama (`git log --all --oneline | grep -iE "MARK_ROW|M-0[5-9][0-9]"` → **70** líneas, verificado 2026-08-02) y los 8 ficheros siguen sueltos en la raíz (`ARCHIVED.md` · `BLOCKED.md` · `DECISIONS.md` · `DISCARDED.md` · `INCIDENTS.md` · `MEMOS.md.lock` · `QUESTIONS.md` · `RESTRICTIONS.md` — confirmado por contenido: cada uno lleva la cabecera literal `_header_for()` de `indexes.py`, la prueba de que salieron de una ejecución real de la suite). **Decisión del propietario:** si se reescribe la rama para quitar los 70 commits, o se dejan y se limpian solo los 8 ficheros. Ninguna de las dos cosas se ha tocado — Alexandria no borra ficheros ni reescribe historial por su cuenta.

### [x] 22 · Dos tests en rojo exigiendo que el hook de cada mensaje imprima siempre algo — **CERRADO 2026-08-04: los tests tenían razón**

> **«Que escriba algo, como "no hay nada que decir".»** · **«Que tenga coherencia y que sea en inglés.»** `[propietario, 2026-08-04 — PARTE 1, B30]`
>
> **La decisión que se tomó en su ausencia queda revocada.** Se había decidido —sin él— que callar cuando no hay nada que decir era correcto, y quedó anotado aquí como **revocable** precisamente por eso. Acaba de revocarlo: **el hook habla siempre.**
>
> Hoy imprime, verificado ejecutándolo a mano:
> ```
> [memory-check] No skill match this turn — nothing to report.
> ```
> En inglés (regla **B11**) y con la misma etiqueta entre corchetes que sus otras líneas.
>
> **Y esto es lo que hay que retener de este punto, más allá del arreglo:** los dos tests llevaban días en rojo **y tenían razón**. Se dio por bueno que el código estaba bien y el test sobraba, cuando era al revés. Un test en rojo que se explica en vez de arreglarse es un test que se acaba ignorando — y detrás se esconde un fallo de verdad.
>
> *(Queda una aserción caduca en `test_encoding_contract.py` que exige que la salida cite `git-memory-recall.py`, un script del sistema viejo que ya no existe. Esa sí es del test, no del código, y se está corrigiendo.)*

`hooks/user-prompt-memory-check.py::main()`: cuando el repo ya arrancó (`session_booted=True`) y el mensaje no encaja con ninguna palabra clave del router de skills, `lines` queda `[]` y `if lines: print(...)` no dispara — el hook emite **stdout vacío**. Dos tests, mismo hallazgo, reportado una sola vez:

- `tests/test_user_prompt_recall.py::TestNoRegression::test_base_output_not_empty` — **verificado en rojo 2026-08-02**: `assert stdout.strip()` falla con cadena vacía.
- `tests/test_encoding_contract.py::TestUserPromptMemoryCheckCp1252::test_valid_stdin_json_exits_zero_with_useful_output` — **verificado en rojo 2026-08-02**, mismo síntoma (stdout vacío), y su expectativa de encontrar `git-memory-recall.py` en la salida ya no aplica en ningún sitio del hook.

Se decidió (sin el propietario presente) que **callar cuando no hay nada que decir es correcto** — pero es una decisión tomada en su ausencia, así que queda **anotada como revocable**, no como cierre.

> **Reparación:** o Ultron repone un `print` incondicional, o el propietario confirma que el silencio es la conducta correcta y los dos tests se reescriben para exigirlo (invertir la aserción, no borrarla).
> **Verificación:** `pytest unmassk-toolkit/tests/test_user_prompt_recall.py::TestNoRegression::test_base_output_not_empty unmassk-toolkit/tests/test_encoding_contract.py::TestUserPromptMemoryCheckCp1252::test_valid_stdin_json_exits_zero_with_useful_output -q` en verde, o los dos reescritos con la firma del propietario. **No pasa: 2 failed, verificado 2026-08-02.**

### [x] 23 · `bootstrap_commits.py` vivo sin un solo llamador — **CERRADO 2026-08-04: se retira**

> **«Se retira.»** `[propietario, 2026-08-04 — PARTE 1, B26]`
>
> Cero llamadores de producción: no lo importa ningún hook ni ningún script de `bin/`. Lo único que lo usaba eran sus propios tests — la definición exacta de lo que este proyecto declara como su enfermedad, y la razón por la que existe la puerta del llamador declarado (`PIEZAS.md` §2, puerta 2).
>
> **Con una condición que no es negociable, y era lo que llevaba días bloqueando este punto:** `tests/test_read_retry_contract.py` **no lo prueba a él** — prueba `lib/git_helpers.py::run_git_read_retrying()`, que es **pieza viva y compartida** (el contrato de reintento de lectura del issue #61), usando `bootstrap_commits.scan_recent_commits()` como **segundo punto de entrada independiente** al mismo mecanismo. Retirar el fichero llevándose ese test por delante quitaría cobertura de código que sigue en producción, y eso **no es lo que se ha decidido**. La cobertura de `run_git_read_retrying()` no baja.

`lib/bootstrap_commits.py` no lo importa ningún hook ni script de `bin/` (`grep -rln "bootstrap_commits" unmassk-toolkit/` solo da el propio fichero y dos tests). Borrarlo se lleva por delante la cobertura del contrato de reintento de lectura del issue #61: `tests/test_read_retry_contract.py` prueba `git_helpers.py::run_git_read_retrying()` (la pieza real, compartida) también a través de `bootstrap_commits.py::scan_recent_commits()` como segundo punto de prueba independiente del mismo mecanismo.

> **Reparación:** ninguna urgente — es una decisión de diseño (¿retirar el fichero y mover esa cobertura a un test que no dependa de código muerto de producción, o dejarlo vivo a propósito como fixture de contrato?), no un bug.
> **Verificación:** `grep -rln "bootstrap_commits" unmassk-toolkit/` — **verificado 2026-08-02**: solo `lib/bootstrap_commits.py`, `tests/test_bootstrap_commits_date_field_contract.py` y `tests/test_read_retry_contract.py`; cero en `hooks/` y `bin/`. `pytest unmassk-toolkit/tests/test_bootstrap_commits_date_field_contract.py unmassk-toolkit/tests/test_read_retry_contract.py -q` → 10 passed.

### [x] 24 · Buscar por identificador devuelve la zona entera — **el texto ya existe, cerrado 2026-08-03**

> **El propietario dictó el molde el 2026-08-03** y está escrito en `TEXTOS.md` **§2.4**, con sus cinco reglas: la cabecera es la nota (identificador, tipo y **estado**), todos los campos del commit con su nombre y sin imprimir los vacíos, las dos zonas con la fecha en que se escribió, debajo lo que cuelga de ella por punteros, y el pie ofreciendo la zona en vez de `--todo`.
>
> Lo que bloqueaba este punto era exactamente eso — *«en esta obra los textos se escriben primero y de ellos se derivan las piezas»* — y ya no falta. **La implementación entra por la cola** (`DEUDA.md` PARTE 1, «lo decidido que falta por construir», punto 1), con su contrato en rojo escribiéndose ahora.

<details><summary>El diagnóstico original, conservado</summary>

#### Buscar por identificador devuelve la zona entera, con lo archivado mezclado y sin marcar

`bin/memory/search.py::_render_by_id()` resuelve la nota con `query.by_id()` y acto seguido la tira: devuelve `report_render.render_zone(report.build_zone(note.zone1, True))`. Tres consecuencias, las tres vistas en pantalla ejecutándolo:

1. **Pides una nota y te dan una zona.** La spec §8.1 dice literalmente *«Por ID: `D-030` → la nota y su racimo»*. Lo que sale es el informe completo de la zona.
2. **Se ignora la segunda zona.** Una nota vive en dos (`zone1`, `zone2`); el informe se construye solo sobre la primera, sin decirlo.
3. **El archivado va forzado a `True` y sin marca.** La spec dice *«vigente por defecto; historia completa tras `--todo`»*. Aquí sale todo mezclado, la nota cerrada indistinguible de las vivas, **y el pie del informe sigue ofreciendo `--todo` «con lo archivado»** — que ya estaba arriba. El informe se contradice a sí mismo en la misma pantalla.

Reproducido en un repositorio limpio: alta de `I-001`, cierre de `I-001`, alta de `I-002`; `search.py --id I-001` responde `ZONA core · 1 vigentes · 1 archivadas` y lista **las dos** bajo `🔥 INCIDENCIAS (2)`.

**Por qué no se ha reparado ya:** `TEXTOS.md` §2 tiene el molde de la zona con contenido, el de la zona vacía y el de la búsqueda por palabra. **No tiene molde para el informe por identificador.** En esta obra los textos se escriben primero y de ellos se derivan las piezas, nunca al revés, así que arreglar esto sin ese molde sería inventarlo. Las piezas para construirlo ya existen (`query.by_id` para la nota, `clusters.build` para el racimo por punteros `Origin`/`Replaces`).

> **Reparación:** el propietario fija el molde del informe por identificador en `TEXTOS.md` §2; después `_render_by_id()` se deriva de él. El punto 3 (archivado forzado y pie contradictorio) se arregla con el molde, no antes: es la misma función.
> **Verificación:** con `I-001` cerrada e `I-002` viva, `python3 bin/memory/search.py --id I-001` enseña **esa** nota y su racimo, no el inventario de la zona, y ninguna nota archivada aparece sin marca mientras el pie siga ofreciendo `--todo`. **No pasa: verificado 2026-08-03.**

</details>

### [x] 25 · El repositorio anidado — **cerrado 2026-08-03: no se arregla, por decisión del propietario**

> **«Nunca voy a trabajar en submódulos. Nunca. Olvídalo ya, no vamos a arreglar nada de eso porque no se va a dar el caso.»** `[propietario, 2026-08-03]`
>
> Y comprobado además que el caso que le preocupaba **no existe**: `chatroom` no es un submódulo ni un repositorio anidado — no tiene `.git` propio, es una carpeta normal de este repositorio, así que trabajando ahí dentro la memoria **ya va a la general**, que es justo lo que quiere.
>
> **Los 3 tests que lo exigían se retiran, no se arreglan** (`test_context.py`, `test_gitcmd.py`, `test_rules.py`) — están en la cola de trabajo, punto 8. Son los tres rojos que llevan todo el día en la suite.

<details><summary>El diagnóstico, conservado — el hecho era real, el caso no se da</summary>

#### Dentro de un repositorio anidado, el sistema entero trabaja sobre el repositorio equivocado

> **Corregido el 2026-08-03, el mismo día.** La primera versión de este punto (conservada abajo) culpaba a `commit_empty()` y proponía anclarlo a la raíz del repositorio «igual que `commit()`». **Esa reparación no arregla nada, y el diagnóstico estaba mal enfocado.** Lo levantó el contrato al escribirse y está comprobado: `git rev-parse --show-toplevel` ejecutado con el directorio dentro de un repositorio B genuinamente anidado devuelve **la raíz de B**, no la de A. Es el comportamiento real de git, no un bug. Anclar «a la raíz del repositorio» da el mismo resultado.
>
> **Y el alcance es mucho mayor:** no son los dos escritores sin fichero, es **todo el sistema**. Guardando una nota normal con `bin/memory/note.py` desde dentro de B, en un proyecto A que ya tenía sus zonas dadas de alta:
>
> ```
> → la nota se RECHAZA: "esa zona no existe"        (busca zones.json en B)
> → y ademas deja creado:
>   <A>/vendor/otro/.claude/project-memory/MEMOS.md  (siembra la memoria DENTRO de B)
> ```
>
> No es solo que se pierda el `⏩`: el sistema **se instala en el repositorio equivocado** y desde ahí deja de ver las zonas del proyecto.
>
> **`[pregunta]` para el propietario, y por eso este punto no se repara todavía:** trabajando dentro de un submódulo o de un repositorio clonado dentro de otro, **¿la memoria es la del submódulo o la del proyecto que lo contiene?** Las dos respuestas son defendibles y **ningún documento la toma**. Si es la del submódulo, el comportamiento de hoy es correcto y lo que falta es **decirlo en voz alta** (hoy no avisa de nada). Si es la del proyecto, hace falta un ancla distinta de `git rev-parse`, y hay que definir cuál. Rellenarlo con criterio propio sería decidirlo en silencio.
>
> Los tests del contrato (`test_context.py`, `test_rules.py`, `test_gitcmd.py`, 5 en total) **se quedan en rojo a propósito** hasta que la pregunta se responda: reproducen el hecho y no presuponen el mecanismo del ancla, pero sí afirman una de las dos salidas.

<details><summary>Diagnóstico original, conservado — era correcto en el hecho, equivocado en la causa y en la reparación</summary>

#### El cierre de sesión y el `remember` se guardan en el repositorio equivocado si hay un repositorio anidado — **fallo silencioso, memoria perdida**

`lib/memory/gitcmd.py::commit_empty()` invoca git con `cwd=Path.cwd()` — **el directorio donde está el proceso, no la raíz del proyecto** — y su propio docstring lo declara: *«No declara su propio `cwd`: hereda el cwd ambiental del proceso, igual que `commit()`»*. Pero `commit()` **ya se arregló** el 2026-08-03 (acepta `cwd` y `notes_commit.stage_and_commit()` le pasa la raíz); `commit_empty()` se quedó fuera.

Sus dos llamantes son precisamente los que no tocan ningún fichero, así que no hay ninguna otra ancla que los salve: `context.write()` (el `⏩` del cierre de sesión) y `rules.add()` (el commit vacío del `remember`).

Reproducido: repositorio A con un repositorio B anidado dentro (`vendor/otro`, un submódulo, un proyecto clonado dentro de otro). Ejecutando el cierre de sesión **desde dentro de B**:

```
### commits en el repo A (el proyecto):
f074850 repo A: el proyecto de verdad          ← el ⏩ NO está aqui
### commits en el repo B (el anidado ajeno):
7906db2 ⏩ cierro la sesion de hoy              ← esta aqui
```

Y por pantalla sale `⏩ cierro la sesion de hoy`, sin un solo aviso. La sesión siguiente abre el proyecto y **no encuentra Next**: se perdió en silencio. Es la misma causa raíz que metió los 70 commits falsos en la rama —orientarse por el directorio en vez de por el repositorio— en el único sitio donde quedó sin corregir.

> **Reparación (la de la versión vieja, NO válida):** `commit_empty()` se ancla a la raíz del repositorio, igual que `commit()`; `context.write()` y `rules.add()` se la pasan.
> **Verificación:** con un repositorio B anidado dentro de A, ejecutar el cierre de sesión y el `remember` **desde dentro de B**. **No pasa: verificado 2026-08-03.**

</details>

> **Reparación real:** depende de la respuesta del propietario a la pregunta de arriba. En los dos caminos, el sistema **deja de callarse**: hoy escribe en otro repositorio y siembra su carpeta allí sin un solo aviso, y eso está mal en las dos lecturas.
> **Verificación:** con un repositorio B anidado dentro de A y las zonas dadas de alta en A, ejecutar desde dentro de B el cierre de sesión, el `remember` y un alta de nota; el resultado coincide con lo que el propietario haya decidido **y se dice por pantalla**. **No pasa: verificado 2026-08-03 — no avisa de nada.**

</details>

### [ ] 26 · El hook del arranque existe, funciona, y **no lo llamaría nadie**

**Corregido 2026-08-03: ya no son dos hooks, es uno solo.** `hooks/inject.py` —el segundo hook que este punto citaba— **se retiró por completo** junto con `lib/memory/dispatch.py` y sus tests, por decisión del propietario (**B20**, Parte 1 de este documento): la memoria deja de inyectarse por un vigilante y pasa a que cada agente la busque él mismo, en tres pasos escritos en su propio prompt. No es que el hook siga sin engancharse — **ya no existe**, y no va a engancharse nunca.

Lo que queda de este punto es solo `hooks/boot_launcher.py`: está escrito, con sus tests en verde, y probado a mano ejecutándolo. Pero **no está registrado en `unmassk-toolkit/hooks/hooks.json`**, que sigue apuntando solo a los hooks del sistema viejo. Un hook que no está en ese fichero no se dispara nunca: hoy es código muerto.

Es el mismo patrón que ya costó un hallazgo en la capa 4 —un vigilante escrito ese mismo día que no llegaba a ninguna pantalla porque el molde no tenía sitio para sus números—, y la razón por la que la especificación insiste en que un chequeo que no habla es indistinguible de uno que no se ejecuta.

**Se deja abierto a propósito, no es un olvido:** registrar un hook nuevo mientras el sistema viejo sigue vivo puede dejar dos arranques disparando a la vez, y el orden en que se retira el v1 es la fase 9 del plan. Va junto con la publicación de versión, no antes.

**Y hay un test en rojo por esto, que nadie había anotado** `[encontrado 2026-08-04]`**:**

```
unmassk-toolkit/tests/test_doctor_derived_expectations.py
  ::TestExpectedHooksDerivation::test_matches_the_hook_files_actually_shipped

  hooks.json and hooks/ disagree.
      shipped but not declared: ['boot_launcher.py', 'customs.py']
```

Es un vigilante **legítimo** —comprueba que lo que hay en `hooks/` y lo que declara `hooks.json` digan lo mismo— cazando exactamente la divergencia que este punto describe. **Lleva en rojo desde que los dos hooks se escribieron (2026-08-03) y no estaba escrito en ninguna parte.**

**Se anota, no se silencia.** Un test en rojo que nadie explica es un test que se acaba ignorando, y detrás se esconde un fallo de verdad — es la lección que acaba de dejar el punto **22**, donde dos tests llevaban días en rojo **teniendo razón**. Este la tiene también: lo que vigila es cierto, y se pondrá verde solo cuando la fase 9 registre los dos hooks. Hasta entonces, **es rojo esperado y está declarado aquí**.

> **Reparación:** al retirar el v1 (fase 9), `hooks.json` registra `boot_launcher.py` en `SessionStart`, y se quitan los del sistema viejo que quedan sustituidos. `customs.py` entra también — su `[pregunta]` bloqueante (`PIEZAS.md` §11.1) **la respondió el propietario el 2026-08-03**: *«siempre que se use git tiene que guardarse de una forma u otra en memoria»*.
> **Verificación:** `grep -c "boot_launcher" unmassk-toolkit/hooks/hooks.json` distinto de cero, y una sesión real arrancando con el hook nuevo. **No pasa: verificado 2026-08-03, cero coincidencias.**

### [x] 27 · El commit de trabajo se guarda con tu título y el contenido de otro — **CERRADO 2026-08-04 por decisión del propietario: el caso no se da**

> **«No va a pasar nunca.»** `[propietario, 2026-08-04 — PARTE 1, B22]`
>
> **No se cierra con un arreglo: se cierra descartando el caso.** El hecho medido sigue siendo cierto —16 de 30 con dos procesos a la vez—, pero **no hay dos procesos a la vez**: el propietario trabaja en una sola ventana. Es la misma figura que el punto **25**, el repositorio anidado, cerrado igual el 2026-08-03.
>
> **Y por eso no se sigue tocando código:** tres intentos de reparación, dos de los cuales crearon un fallo nuevo en el arreglo anterior — el punto **28** nació dentro del arreglo de este. El candado que ya existe (`write`, `replace`, `close`) **se queda**; lo que no se construye es más maquinaria por este eje.
>
> **Lo que sigue siendo verdad y no se borra, porque es la lección más cara del día:** el «0 de 60» con el que este punto se cerró por tercera vez **se midió llamando a la función por dentro**, con el contenido inventado en memoria y nunca escrito a disco. Medido por donde entra el usuario salió **16 de 30**. *Un arreglo se mide por el camino por el que entra el usuario, nunca por dentro.*

<details><summary>El diagnóstico completo, conservado — el hecho era real, el caso no se da</summary>

> **⚠️ Este punto se dio por cerrado tres veces y las tres veces era mentira.** La cuarta pasada de Moriarty lo reabrió con la medición que faltaba, y **el motivo de por qué el «0 de 60» era falso es la lección más importante del día**:
>
> **El «0 de 60» se midió llamando a la función directamente**, con el contenido inventado en memoria y nunca escrito a disco. Moriarty lo probó **como lo usa una persona** —dos `gitmem work` normales sobre el mismo fichero, sin nada raro— y salió **16 de 30 (53%)**. Antes del arreglo era el 55%. **El arreglo no cambió nada en el uso real.**
>
> **La causa, medida:** `work.py` lee el fichero «como primerísima acción», sí — pero **arrancar el proceso tarda entre 50 y 150 milisegundos** (Python y sus imports). Esa es la ventana real, no la que dice el código. Barrida de 0 a 200 ms: hasta los 40 ms se cuela **el 100 % de las veces**, y sigue colándose hasta los 100 ms. El docstring que la llama «mínima» **miente**.
>
> **Y deja sin sentido el hueco que este punto declaraba aparte** —«un intruso que nunca llama a la función»—: no hace falta ningún intruso. **Dos llamadas normales y cooperantes se pisan la mitad de las veces**, y eso es el uso más ordinario que tiene el sistema: dos ediciones al mismo fichero, cada una seguida de su commit.

> **Reparación: NO es más código encima.** Tres intentos y cada uno creó un fallo nuevo en el arreglo anterior. Lo que hay que decidir primero, y es del propietario porque cambia el diseño: **si dos escrituras a la vez sobre el mismo fichero tienen que funcionar, o si el sistema debe negarse a hacerlas.** Hoy intenta funcionar y miente. Negarse —*«ese fichero lo está guardando otro, espera»*— es más simple, más honesto, y probablemente suficiente para quien trabaja en una sola ventana.
> **Verificación:** dos procesos reales de `gitmem work` sobre el mismo fichero, treinta rondas, **cero commits con contenido cruzado** — o el rechazo explícito, con su causa. **No pasa: verificado 2026-08-03, 16 de 30.**

<details><summary>El cierre falso, conservado — es el ejemplo de cómo una medición mal montada da un verde que no existe</summary>

#### El commit de trabajo se guarda con tu título y el contenido de otro, y te dice que todo fue bien — «cerrado» 2026-08-03

**El fallo más grave de toda la obra, y el que más veces se dio por cerrado sin estarlo — tres.** `notes_commit.py:242` — `write_work()` **commitea sin candado**, mientras sus tres hermanas (`write`, `replace`, `close`, en `notes.py` líneas 199, 314 y 401) sí lo cogen.

Reproducido por dos agentes distintos y **por el orquestador con sus propias manos**:

```
write_work dice -> ok: True | git_error: None
--- titulo del commit ---            msgA
--- contenido que quedo dentro ---   content-B
```

Un commit **permanente** cuyo título dice una cosa y cuyo contenido es de otro proceso, y la función responde que todo salió bien. Medido sin forzar nada: **3 de cada 20** intentos con dos procesos reales sobre el mismo fichero. El mismo experimento contra `notes.write()` —que sí tiene candado— sale **15 de 15 limpio**.

**El mecanismo, y explica por qué el arreglo tiene dos mitades:** `git commit -- <ruta>` **no** commitea lo que dejaste preparado con `git add`; **relee el árbol de trabajo para esa ruta en el instante del commit**. Dos escenarios distintos salen de ahí:

- **La carrera entre escritores concurrentes** — diez hilos, cada uno con su ruta: sin candado, 7-8 de cada 10 mueren contra `.git/index.lock`, que git no reintenta. **Lo cierra el candado.** Es el caso del día a día: dos agentes commiteando a la vez.
- **El contenido cambiado** — si otro proceso pisa el fichero **antes** de que la función arranque, el contenido bueno ya no existe en ningún sitio y **ningún candado lo recupera**. Aquí la exigencia es otra: que la función **deje de mentir** y falle con causa en vez de responder `ok=True`.

> **Reparación:** `write_work()` coge el mismo candado que sus tres hermanas, **y** deja de declarar éxito sobre un commit cuyo contenido no es el que se pidió. El contrato de commitear **solo** las rutas dadas, sin arrastrar el resto del índice, no se toca: lo exige la publicación del toolkit `[plan §2.7]`.
> **Por qué costó tres intentos:** el candado (arreglo 1) cierra la pelea contra `.git/index.lock`, pero no evita que otro escritor pise el fichero en disco. Un segundo arreglo (comprobar si la ruta ya estaba en el índice de git como fichero nuevo) tampoco bastaba: solo caza al intruso que hace su propio `git add`. El caso real y corriente — dos llamadas normales a `write_work()`, cada una escribiendo su propio contenido en el mismo fichero, sin ningún intruso — seguía colándose. Verificado en vivo por Moriarty tras el segundo arreglo: **11 de 20 intentos (55%)** con el mensaje de un escritor sobre el contenido del otro.
> **El arreglo real:** la huella de referencia deja de leerse del disco dentro de la función — la calcula quien llama, a partir de los bytes que **ya tiene en la mano** (`known_content`), sin volver a leer el fichero. `work.py`/`wip.py` leen el fichero como primerísima acción del script, antes de cualquier otra cosa, y le pasan esos bytes.
> **Verificación ejecutada 2026-08-03:** `pytest unmassk-toolkit/tests/memory/test_notes.py -q` → verde (incluido en los **261 passed** de la suite completa de memoria). Con dos procesos de sistema operativo reales (no hilos) pasando `known_content`: **0 de 60** con contenido y mensaje cruzados, en dos tandas por separado (20 y 40). Y el arreglo se puso a prueba deshaciéndolo en una copia temporal fuera de este repositorio (nunca tocando el código de producción): con esa copia sin el arreglo, el mismo experimento salió en rojo **tres veces** — 9/20, 6/20 y 5/20 — confirmando que el cierre vive específicamente en pasar los bytes ya conocidos, no en el candado ni en la comprobación de fichero nuevo por sí solas.
> **Lo que sigue vivo, y no es este punto:** un intruso que pisa el fichero en disco **sin pasar por `write_work()` en absoluto** (nunca hace `git add`) todavía tiene una ventana — ahora mucho más estrecha (entre que el script lee el fichero y llama a la función), pero no cero. Está anotado en el punto **13**, no aquí: este punto cierra el caso que lo hacía grave — dos escritores normales, sin ningún intruso, mintiendo con `ok=True`.

</details>

</details>

*(Los dos `</details>` de arriba cierran el diagnóstico. El segundo faltaba desde el 2026-08-03 — sin él, todo el punto 28 quedaba plegado dentro del desplegable del 27 y no se veía al leer el documento. `[corregido 2026-08-04]`)*

### [x] 28 · Dos reparaciones a la vez duplican una nota — **CERRADO 2026-08-04 por decisión del propietario: el caso no se da**

> **«No va a pasar nunca.»** `[propietario, 2026-08-04 — PARTE 1, B22]` Mismo motivo que el punto 27: hace falta lanzar **dos reparaciones casi a la vez**, y no hay dos. El hecho medido —15 de 15— sigue siendo cierto; el caso, no se da.
>
> **Se conserva entero el diagnóstico de abajo** porque enseña dos cosas que sí siguen valiendo: que el arreglo de un fallo puede traer el suyo propio (este nació dentro del arreglo del 27), y que **un aviso y un visto bueno sobre el mismo hecho en la misma pantalla** es un defecto de presentación por sí mismo — el propietario ya lo señaló en la capa 4.

<details><summary>El diagnóstico, conservado — el hecho era real, el caso no se da</summary>

#### Dos reparaciones a la vez duplican una nota, y la duplican guardada para siempre

**Encontrado el 2026-08-03 en código escrito ese mismo día** — la pieza que arregló el punto anterior. Es el patrón que se ha repetido tres veces hoy: **el arreglo trae su propio fallo**.

`bin/memory/rezones.py` calcula qué hay que reparar **fuera del candado**, y `lib/memory/rezones_commit.py` coge el candado pero **nunca vuelve a comprobar si ese plan sigue valiendo** una vez dentro. Aplica a ciegas.

Reproducido **15 de 15 veces**: se borra a mano una línea de un índice —justo lo que ese comando existe para arreglar— y se lanzan **dos reparaciones casi a la vez**. La segunda reinserta la misma nota otra vez **y la commitea**.

**Y es peor que el fallo que esa pieza vino a cerrar**, por dos motivos:

- El fallo original se podía perder con un `git checkout`; **este ya está guardado**, así que no hay vuelta atrás.
- Y el arranque te enseña las dos cosas, **contradiciéndose en la misma pantalla**:

```
⚠️  duplicate IDs: D-001
✓  indexes match git (2 lines / 1 notes)
```

Un aviso y un visto bueno sobre el mismo hecho. Es exactamente el patrón que ya salió en la capa 4 y que el propietario señaló entonces.

**No es de laboratorio:** dos terminales, o una persona y un vigilante, reaccionando los dos al mismo aviso del arranque.

> **Reparación:** el plan se calcula **dentro** del candado, o se vuelve a comprobar al entrar. Y quien inserta una línea de índice debería negarse si el identificador ya está — hoy añade sin mirar.
> **Verificación:** dos reparaciones simultáneas sobre la misma divergencia dejan **una sola línea**, y el arranque no enseña un aviso y un visto bueno sobre lo mismo. **No pasa: verificado 2026-08-03, 15 de 15.**

</details>

---

---

## Sabidas y aceptadas — NO se reparan durante la construcción

Están aquí para que nadie las vuelva a levantar como hallazgo.

- **La versión instalada va por detrás del repo.** La caché está congelada en 1.25.0 y da igual que crea que hay diez agentes o que sus hooks sean viejos. Se resuelve al publicar, y las pruebas reales son **al fusionar**, no antes. *(Decisión del propietario, 2026-08-02.)*
- **Nada del sistema viejo puede colarse en la versión nueva.** Verificado: la caché guarda **una carpeta por versión**, cada una foto completa e independiente — medido, 183 ficheros en 1.24.0 y 191 en 1.25.0, cada una con sus propios agentes y hooks. La carpeta nueva contendrá solo lo que esa versión lleve.

---

## Cómo se cierra esta lista

Un punto se marca hecho **solo** tras ejecutar su verificación. Si al repasarla antes de fusionar queda alguno sin marcar, no se fusiona: o se repara, o se baja aquí abajo con el motivo escrito y la firma del propietario.

## Recuentos viejos — **ninguno vale ya**

**El recuento que manda es el de abajo del todo, fechado el 2026-08-04: 28 puntos, ~~15 cerrados, 13 abiertos~~ 26 cerrados, 2 abiertos.** `[recontado 2026-08-04: la sección de abajo tenía su propia cuenta mal — el detalle está anotado ahí mismo, no aquí]` Lo que sigue en este desplegable son cuatro recuentos anteriores que se contradicen entre sí (dijeron 23, 27 dos veces y 27 otra vez, con cuatro repartos distintos de cerrados y abiertos). **Se conservan plegados porque cuentan cómo se llegó aquí, no porque cuenten bien** — y plegados precisamente para que nadie lea una de estas cifras creyendo que es la vigente, que es lo que ya pasó una vez: se decidió si la rama se podía fusionar con un número falso. `[plegado 2026-08-04]`

<details><summary>Los cuatro recuentos anteriores, conservados</summary>

### Estado tras la revisión completa del 2026-08-02

> **Añadido el 2026-08-03:** los puntos **24** y **25** (capa 5), el **26** (capa 6) y el **27** (capa 3, el más grave de la obra). Total **27 puntos: 10 cerrados, 17 abiertos.** El resto de esta sección es del día anterior y no se ha reejecutado.
>
> **Y un defecto que ya no es de un hook, sino de dos:** el vigilante de commits bloquea por ver la palabra «commit» dentro de un texto cualquiera —ya estaba anotado—, y **el vigilante de fusiones tiene exactamente el mismo defecto con la palabra «merge»**, que no lo estaba. Medido el 2026-08-03: **cuatro bloqueos falsos en una mañana**, incluidos una nota de memoria que llevaba la palabra en su descripción y un script de prueba que la llevaba dentro de una lista. Ninguno de los dos comandos iba a fusionar ni a commitear nada.
>
> El punto **13** sigue abierto pero **encogió**: su primer hallazgo pendiente —`gitcmd.commit()` sin `cwd` propio— quedó cerrado el 2026-08-03, y el agujero gemelo que quedaba vivo en `commit_empty()` es ahora el punto 25, con su propia verificación.

> **RECUENTO BUENO, contado uno a uno el 2026-08-03 al cierre de la sesión:** **27 puntos rotos — 13 cerrados y 14 abiertos**, más **19 decisiones del propietario**, todas cerradas. Lo que sigue debajo es del día anterior y sus cifras ya no valen: llegó a decir 27 en una línea y 23 en la siguiente, y a decidir si la rama se podía fusionar con un número que era falso. Se conserva por lo que cuenta, no por lo que cuenta mal.

**23 puntos en total. 10 cerrados, 13 abiertos.** Cada uno con su comando de verificación reejecutado hoy, no fiado de lo que se creía cerrado.

**Cerrados (verificación ejecutada, en verde):** 1 · 4 · 6 · 8 · 9 · 10 · 12 · 14 · 18 · 20.

**Abiertos:**
- **Sin tocar, siguen igual que antes:** 2 (arranque manda cargar tres cosas borradas — deliberado, fase 7), 5 (vigilante de caché no ve `lib/memory/`), 15 (bloque gestionado sobreescribe sin avisar), 16 (wrapper de commits sin validar `Memo:`/`Remember:`), 17 (arranque sin aviso de frescura del remoto).
- **Mejoraron pero no cierran:** 3 (la cabecera de `close-session` ya dice la verdad; la función sigue sin recuperarse), 7 (las funciones e imports se retiraron; quedan 2 comentarios citándolas, el grep literal no da vacío), 11 (3 de 4 funciones ya tienen llamador o test real; el test de frontera que las cazaría automáticamente no existe), 19 (`coherence`/`plans_unreflected` ya tienen fila y test; `duplicates`/`build` siguen sin ninguno de los dos).
- **En curso activamente hoy, con hallazgos reales sin cerrar:** 13 (Moriarty ya atacó capas 2 y 3, veredicto FALLA las dos veces — un T1 de `gitcmd.commit()` sigue reproducible).
- **Nuevos de esta revisión:** 21 (la causa de los 70 commits falsos y los 8 ficheros sueltos está arreglada y con red nueva; la limpieza de lo ya ocurrido es decisión del propietario), 22 (2 tests en rojo por una decisión de silencio tomada sin el propietario, revocable), 23 (`bootstrap_commits.py` vivo por una decisión de cobertura pendiente, no un bug).

~~**Este número —13 abiertos— es el que decide si la rama se puede fusionar hoy.**~~ *(cifra del 2026-08-02, ya falsa — el recuento bueno está arriba: **14 abiertos**.)*

</details>

---

## RECUENTO BUENO — 2026-08-04. Este es el que vale; todos los de arriba quedan por lo que cuentan, no por lo que cuentan bien

> **Recontado el 2026-08-04, otra vez el mismo día — esta sección se contradecía a sí misma tres veces más** (19 cerrados aquí, 9 abiertos más abajo, «el número que cuenta es 7» más abajo todavía, una tabla de 13 después de eso, y «nueve» en la última línea). **Contando de verdad las cabeceras numeradas de este documento — 26 llevan `[x]` y solo 2 llevan `[ ]` (el 2 y el 26)** — el recuento correcto es **26 cerrados, 2 abiertos**. Nada de lo de abajo se borra: cada cifra que contradice esta se deja tachada en su sitio, con esta misma nota como explicación, siguiendo el patrón del resto del documento (líneas 385, 411, 1093).

**28 puntos rotos en total (1 a 28, sin huecos). ~~15 cerrados, 13 abiertos.~~ 26 cerrados, 2 abiertos.**

> **Dos errores de recuento corregidos hoy, y hay que decirlos porque este documento es el que decide si la rama se puede fusionar:**
>
> 1. **Los recuentos anteriores decían «27 puntos, sin huecos» y había 28.** El punto **28** estaba escrito, medido y con su reproducción — y no entraba en ninguna suma. Un punto roto invisible para el recuento es exactamente el fallo silencioso que este proyecto declara como su única amenaza, cometido por el propio documento que lo declara.
> 2. **El punto 27 aparecía cerrado en el recuento y reabierto en su propia ficha**, los dos textos del mismo día. Hoy queda cerrado de verdad, pero **por otro motivo**: no por el arreglo, sino porque el propietario descartó el caso (**B22**).

**Qué cambia hoy, 2026-08-04:** el propietario responde a la pregunta que llevaba la obra parada —*«no va a pasar nunca»*— y con esa sola respuesta caen **tres** cosas: el punto **27**, el **28**, y el único hallazgo que quedaba vivo del **13**. Ninguno se cierra con código: los tres se cierran como **caso descartado**, la misma figura que el punto 25.

~~**Cerrados (19):** 1 · 4 · 6 · 8 · 9 · 10 · 12 · **13** · 14 · 18 · 19 · 20 · **21** · **22** · **23** · 24 · 25 · **27** · **28**.~~

**Cerrados (26)** `[recontado 2026-08-04: la lista de 19 se dejaba fuera a 3, 5, 7, 11, 15, 16 y 17, que llevan su propia cabecera «CERRADO 2026-08-04» más arriba en este mismo documento]`: 1 · **3** · 4 · **5** · 6 · **7** · 8 · 9 · 10 · **11** · 12 · **13** · 14 · **15** · **16** · **17** · 18 · 19 · 20 · **21** · **22** · **23** · 24 · 25 · **27** · **28**.

**Abiertos (2)** `[recontado 2026-08-04: 1 y 3 no eran abiertos — el 1 ya estaba en la propia lista de "Cerrados" un párrafo más arriba, y el 3 se cerró ese mismo día (ver PARTE 2, punto 3) — y "2 · 2" repetía el mismo punto dos veces]`, **y los dos son la misma clase:**

<details><summary>La tabla del 2026-08-04 anterior, conservada — decía «Abiertos (9)» con dos filas que no sumaban 9</summary>

**Abiertos (9), y NO son todos lo mismo** `[corregido por el propietario, 2026-08-04: «eso no es roto, eso es en espera»]`**:**

| Estado | Cuáles | Qué significa |
|---|---|---|
| 🔧 **ROTO** — hay algo que reparar | **1** · 3 | Recuperar lo que hace el cierre de sesión. **Es construcción de la fase 7, no una reparación**, y ya está especificado (paso 7.10 + `TEXTOS.md` §5) |
| ⏳ **EN ESPERA** — ya está resuelto, falta publicarlo o encenderlo | **2** · 2 · 26 | **No hay nada que reparar.** El arreglo está escrito y verificado; lo que falta es que llegue a correr |

</details>

| Estado | Cuáles | Qué significa |
|---|---|---|
| ⏳ **EN ESPERA** — ya está resuelto, falta publicarlo o encenderlo | **2** · **26** | **No hay nada que reparar.** El arreglo está escrito y verificado; lo que falta es que llegue a correr |

> **Los otros seis se cerraron el 2026-08-04, en una tarde:** **5** (el vigilante no miraba en subcarpetas y todo el sistema nuevo le era invisible) · **7** (dos comentarios citaban funciones retiradas) · **11** (`repo_root`, la que decide en qué repositorio se escribe, sin un solo test propio) · **15** (el generador se tragaba texto ajeno sin dejar rastro) · **16** (el wrapper que guarda la memoria dejó de validar) · **17** (el arranque daba un número sin decir que podía ser de días atrás).
>
> **Ninguno era del sistema de memoria nuevo.** Los seis vivían en el toolkit viejo que sobrevive — que es lo que había que comprobar antes de decir que las capas 0 a 6 estaban limpias.

**Los dos en espera, y por qué no son deuda técnica:**
- **Punto 2** — el arranque manda cargar tres cosas borradas. **Arreglado en el repositorio hace días.** Sigue pasando porque lo que corre en cada sesión es la copia instalada, no este repositorio: se cierra solo al publicar versión (paso **7.14**), sin tocar una línea más.
- **Punto 26** — los dos hooks nuevos no están registrados en `hooks.json`. **Deliberado**: engancharlos con el sistema viejo aún vivo dispararía dos arranques a la vez. Se registran en la fase 9.

**Por qué importa la distinción, y no es semántica:** este documento decide si la rama se puede fusionar. Contar como «roto» algo que ya está arreglado **infla el número que toma esa decisión** — es el mismo defecto de los cuatro recuentos falsos que se corrigieron esta misma tarde, con otra cara. ~~**El número que cuenta para reparar es 7, no 9.**~~ **Recontado 2026-08-04: el número que cuenta para reparar con código es 0** — los dos abiertos que quedan (2 y 26) son EN ESPERA, no ROTO; ninguno se arregla tocando código, los dos se cierran solos al llegar su fase.

~~**De trece abiertos a nueve en una tarde, y no por arreglar código:**~~ **De trece abiertos a dos, en la misma tarde** `[recontado 2026-08-04: «nueve» no sumaba bien — ver la nota al principio de esta sección]`, y tampoco por arreglar código: el propietario respondió las siete decisiones que llevaban semanas esperándole (PARTE 1, **B22** a **B30**). Tres de las que cerró —los 70 commits, los dos tests en rojo, `bootstrap_commits.py`— **no eran fallos**: eran cosas que nadie podía decidir por él, y que por eso se quedaron ahí meses figurando como deuda técnica. Los demás —3, 5, 7, 11, 15, 16, 17— sí se cerraron con revisión y arreglo, el mismo día.

**El 13 se cierra el 2026-08-04 y es el que más pesaba:** era la deuda más antigua viva y bloqueaba las capas 2 y 3, que son **anteriores a todo lo construido encima**. Moriarty pasó una vez por capa, las dos dieron hallazgo, y los dos están reparados y verificados ejecutándolos — no leyendo un informe.

**Dos hallazgos, encontrados el 2026-08-04 en la capa 5** (Cerberus y Argus sobre los scripts renombrados, que se habían revisado con los nombres viejos y sin que `wip` existiera) — ~~abiertos~~ **los dos cerrados el mismo día, B23/B31 y B24** `[corregido 2026-08-04]`. No entraron nunca en la lista numerada de arriba; se dejan anotados aquí para que no se pierdan:

| Qué | Estado |
|---|---|
| **Dar de alta una zona que ya existe borra la anterior** — descripción y alias, sin aviso, con un mensaje de éxito idéntico al de una zona nueva, y sin pasar por git, así que **no hay de dónde recuperarlo**. Reproducido por el orquestador. Es plausible: no existe comando de editar, así que para añadir un alias se vuelve a hacer ~~`alta`~~ **`add`** `[corregido 2026-08-04: el subcomando se llama `add` desde B29]` | ~~**abierto — espera decisión del propietario:** ¿rebota, o actualiza conservando lo que no se menciona?~~ **cerrado el mismo 2026-08-04, decisión B23** — rebota y no toca nada, construido y verificado. Y el agujero gemelo del alias (**B31**) también quedó cerrado |
| **`gitmem rule` no avisa de una regla casi idéntica ya guardada.** El contrato lo exige (`PIEZAS.md` §9.7) y el script **nunca llama** a la pieza que lo detecta. Es el daño ya pagado: 114 recordatorios duplicados en el sistema viejo | ~~**abierto — contrato en rojo escrito**, pero `TEXTOS.md` **no tiene texto para ese aviso** y aquí los textos se escriben antes que las piezas~~ **cerrado el mismo 2026-08-04, decisión B24** — el texto se delegó al orquestador y está en `TEXTOS.md` §1.11b; `bin/memory/rule.py:100` ya llama a `rules_lib.similar_existing` |

**De los 2 abiertos, qué clase de cosa es cada uno** `[recontado 2026-08-04: 5, 3, 7, 11, 15, 16 y 17 ya están cerrados, cada uno con su cabecera propia en la PARTE 2 — la tabla vieja de «13 abiertos» queda plegada abajo por lo que cuenta, no por lo que cuenta bien]`:

| Clase | Cuáles | Qué hace falta |
|---|---|---|
| **Se cierra publicando versión** (paso 7.14) | 2 | Nada que arreglar en el repositorio: lo que corre es la copia instalada |
| **Se cierra en la fase 9** | 26 | Enganchar `boot_launcher.py` y `customs.py` en `hooks.json` |

<details><summary>La tabla del 2026-08-04 anterior, conservada — clasificaba 13 abiertos que ya no lo eran</summary>

**De los 13 abiertos, qué clase de cosa es cada uno** — importa porque no todos son reparaciones:

| Clase | Cuáles | Qué hace falta |
|---|---|---|
| **Se cierran publicando versión** (paso 7.14) | 2 · 5 | Nada que arreglar en el repositorio: lo que corre es la copia instalada |
| **Trabajo de la fase 7** | 3 · 15 · 16 · 26 | Skills, bloque del `CLAUDE.md`, enganchar los hooks |
| **Revisión pendiente** | 13 | Una pasada de Moriarty |
| **Limpieza declarada, sin urgencia** | 7 · 11 | Dos comentarios que citan funciones retiradas · los tests de frontera de §13, que no existen todavía |
| ~~**Esperan una decisión tuya**~~ | ~~21 · 22 · 23~~ | **Los tres, respondidos y cerrados el 2026-08-04** |
| **Aviso de frescura del remoto** | 17 | Reparación pequeña, sin dependencias |

**Ya no queda ni un punto esperando una decisión tuya.** Los nueve abiertos son trabajo: dos se cierran solos al publicar versión, cuatro son fase 7, y tres son limpieza.

</details>

**Ya no queda ni un punto esperando una decisión tuya, y ya solo quedan dos abiertos, no nueve** `[recontado 2026-08-04]`: el **2** y el **26**, y los dos se cierran solos — el 2 al publicar versión, el 26 al enganchar los hooks en la fase 9. Ninguno espera una decisión del propietario ni una reparación de código.
