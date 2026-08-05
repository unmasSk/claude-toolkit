# FASE 7 — lo que se ejecuta

**Este documento es la orden de trabajo de la fase 7.** Los 18 pasos, uno a uno, con lo que va dentro de cada uno, dónde se escribe y cómo se sabe que está hecho.

**Reglas de este documento:**

- **Si contradice a `docs/spec-sistema-memoria-v2.md`, manda la especificación.** Aquí no se decide nada nuevo: se ordena lo ya decidido.
- **Un hueco declarado no se rellena por criterio propio.** Donde pone *«sin decidir»*, se pregunta.
- Nada se construye sin que el propietario lo diga. Nada se commitea sin que él lo diga.

**Estado, 2026-08-05: 13 de 18 hechos. Suite de memoria en 388 verdes.**

Hechos: **7.1 · 7.2 · 7.2b · 7.3 · 7.4** (la skill de memoria, `skills/unmassk-memory/`, escrita, revisada dos veces por el revisor de skills, pasada por el consejo de cinco y **ejecutada comando a comando** contra proyectos nuevos) · **7.5** (ascender una pregunta: `--promotes`, con su fichero `lib/memory/notes_promote.py`) · **7.6** (los planes, en `skills/unmassk-flow/references/plan.md`) · **7.7** · **7.8** (el pie de House, revisado por él mismo) · **7.9** (el mapa de Bilbo con sus tres líneas de memoria) · **7.10** · **7.11** (la skill central, limpia) · **7.12** (el bloque del `CLAUDE.md`) · **7.13** (incidencias, en `skills/unmassk-flow/references/incident.md`, revisado por House dos veces).

**7.13b — la destilación: protocolo escrito y probado dos veces sobre historiales reales.** **7.13c — compactación de memoria de agente: protocolo escrito** (`skills/unmassk-memory/references/agent-memory-compaction.md`), juzgado por dos agentes opuestos —el del diario de 112 ficheros y el que ya estaba sano—, con sus hallazgos aplicados. **Nadie lo ha ejecutado todavía: eso es una pasada aparte, y va después de publicar.**

**Sobre la destilación:** El protocolo está escrito (`skills/unmassk-memory/references/distill.md`) y hay **dos pruebas en seco reales**, en la raíz: `PRUEBA-MEMORIA-V2.md` (este repositorio) y `PRUEBA-MEMORIA-V2-OMAWA.md` (el producto real). Lo que sale de ellas está más abajo, en el paso 7.13b.

**Queda: 7.14** *(y antes, el paso 2.8b: el script de publicar todavía usa el generador viejo).*

### 7.13d — escrito y probado `[2026-08-05]`

Lo escribe **un agente que lee la conversación en crudo**, no Claude acordándose. Y **solo cuando el propietario lo pide**: nada automático tras compactar — *«si hago uno, ¿para qué quiero dos?»*. Un hook no puede lanzar un agente de todos modos; lo único que llega tras compactar es el arranque, y se descartó usarlo.

**LA FORMA, Y SE HA HECHO MAL TRES VECES:** el **Next ES EL TITULAR** del commit — la primera línea, lo primero que se ve —, igual que en una decisión el titular es la decisión. **El contexto ES EL CUERPO.** No existe ningún campo `Next:` al pie: eso es la forma del sistema retirado, y arrastrarla es lo que hace que el Next acabe enterrado al final, que es justo donde no sirve.

**El cierre lleva tres cosas:** el **Next**, que es el titular · el **contexto en prosa**, unas 50 líneas de lo que se habló y no vive en ningún commit · y debajo del contexto, **el titular de TODOS los commits desde el último Next** `[decisión del propietario, 2026-08-05]` — *«sean WIP, sean commit, sean memoria, sea lo que coño sea»*, una línea cada uno. Si los checkpoints se fundieron en uno, git solo tiene el fundido y eso es lo que sale.

*(La prueba del 2026-08-05 salió con el Next al pie porque el encargo pedía el comando del sistema viejo. El fallo fue del encargo, no del agente — y es la tercera vez que pasa por la misma causa: la herramienta vieja empuja a esa forma.)*

**Los titulares se sacan de git, no de la conversación** — son exactos y no dependen del filtro. **Y el límite de "esta sesión" es el último Next**: git no sabe qué es una sesión, pero cada cierre deja esa marca. Si una sesión murió sin cerrar, la siguiente recoge las dos y no se pierde nada.

**El filtro saca la conversación, y NADA más** `[decisión del propietario, 2026-08-05 — revoca la condición anterior]`. Ni herramientas, ni comandos, ni diffs, ni informes de agentes: *«solo tiene que sacar la conversación, porque lo que tiene que decir en el contexto es un resumen de la conversación»*. Lo demás ya está en los commits, que van listados justo debajo.

> **Esto revoca la condición que decía «quita los volcados pero NO los comandos», que venía de B34 y estaba escrita en tres sitios.** El motivo de aquella —distinguir «lo comprobé» de «lo dije»— se resuelve por otro lado: lo comprobado deja commits, y los commits están todos en la lista de abajo. Medido: con las herramientas dentro, el 42% del fichero eran informes de subagentes, que es exactamente lo que el contexto **no** debe contar.

**ESCRITO Y PROBADO EJECUTÁNDOLO — 2026-08-05.** Tres piezas dentro de `skills/unmassk-close-session/`: `scripts/session_transcript.py` (el filtro), `references/close-agent-prompt.md` (el encargo literal) y el `SKILL.md`, que ya no promete un disparo automático.

De la prueba en vivo salieron cuatro cosas y las cuatro están dentro:

1. ~~Los informes de los subagentes no llegan al cierre y habría que dárselos.~~ **DESCARTADO por el propietario** `[2026-08-05]`: *«esos informes eran la tierra para plantar»*. Y al medirlo se vio que además **llegaban solos**: eran el 42% del fichero. Ahora el filtro los tira con todo lo demás.
2. **El filtro es un script dentro de la skill**, no una instrucción en prosa. Descrito con palabras se reinventa cada vez y el resultado no es reproducible.
3. **El corte de sesión ya no hay que convertirlo a mano:** el script busca el último Next y saca de él las dos formas que hacen falta —el commit para git, la fecha para la conversación—. Y lo busca **solo en el título**: pedírselo a git lo buscaría también en el cuerpo, y entonces un memo que hable del cierre se hace pasar por el cierre.
4. **El titular ronda los 70 caracteres**, no 80: el `[NEXT]` y su emoji cuentan dentro de la línea.

**Y tres fallos reales, encontrados ejecutándolo, no leyéndolo:** el error decía *«he mirado en tal sitio»* cuando le habías dado tú la ruta y no había mirado ahí · el listado contaba el cierre anterior como si fuera algo guardado en esta sesión · y el cuerpo de cincuenta líneas viajaba entre comillas en la línea de comandos, donde una comilla del usuario lo estropea y se guarda estropeado sin avisar. Ahora el cuerpo va por fichero.

**Y las rutas valen en los tres sistemas:** la carpeta de conversaciones se resuelve desde el hogar del usuario y el nombre se normaliza carácter a carácter, así que da igual la barra de Windows, la de Mac o los dos puntos de la unidad.

### Y lo que queda después de la fase 7

**7.14 arrastra un paso de la fase 2 sin hacer:** `bin/release.py` sigue usando el generador viejo. Va **antes** de publicar o la publicación se cae.

**Y hay dos pasadas que solo se pueden correr cuando esto esté publicado:** la destilación de la memoria vieja (fase 8) y la compactación de memoria de cada agente. Las dos tienen su protocolo escrito y **ninguna se ha ejecutado todavía**.

---

## Cómo se ha trabajado hoy, y por qué esto funcionó `[2026-08-05]`

Esto no es estilo: es lo que hizo que salieran los fallos. Se sigue.

**1 · Al agente que va a ejecutar algo se le pregunta antes de escribirlo, y se le pregunta de más.** No «¿te parece bien?», sino: *¿es ejecutable tal cual? · ¿qué te obliga a inventar? · ¿choca con tu propia ficha? · ¿qué sabes tú por oficio que quien escribe esto no puede saber? · ¿qué frase le falta para que otro no cometa tu error?* Esa última es la que más ha dado.

**Lo que sacó, y ninguna se habría visto leyendo:** House tumbó dos de las cuatro líneas del pie que le habían puesto —una le obligaba a inventarse una causa que no tenía, otra le hacía juzgar un coste que no es suyo— · Bilbo se desdijo solo de fundir tres ficheros que no debían fundirse, al leer el umbral bien escrito · Moriarty demostró que la regla de las zonas **no le aplica**, porque su memoria es técnica y no territorio · Ultron encontró que el protocolo contradecía sus propias instrucciones de memoria y nadie había resuelto cuál mandaba.

**2 · Se prueba ejecutando, no leyendo.** Los fallos de hoy salieron todos de correr comandos contra repositorios de prueba: el rechazo que ofrecía un comando muerto, la cadena de rechazos que no converge, la incidencia cerrada bloqueando a la nueva. Ninguno salía revisando código.

**3 · Se busca en la documentación antes de preguntarle al propietario.** Dos veces se le hizo decidir algo que ya estaba escrito en la especificación. Es antipatrón anotado.

**4 · Lo que se escribe en un documento permanente pasa dos preguntas:** ¿sería verdad dentro de un año sin saber nada de hoy? · ¿está ya dicho en otro sitio de este mismo fichero? Ahí mueren el «ayer», las menciones al sistema anterior y las duplicaciones.

**5 · Y una que costó tres broncas:** en la descripción de una skill va **solo cuándo cargarse** — sin rutas, sin ficheros, sin ejemplos, en inglés. El contenido va en el cuerpo.

---

## El orden — qué va antes y qué puede ir a la vez

**Tanda 1 — la skill de memoria (7.1 · 7.2 · 7.2b · 7.3 · 7.4).**
Va primera y sola. Es **una sola skill** con cinco encargos dentro, y el resto de la fase la referencia: el paso 7.2b dice expresamente que su contenido vive **una vez** y que los prompts de los agentes solo apuntan a él. Si se escribe después, todo lo que la referencia nace apuntando a nada.

**Tanda 2 — cuatro cosas que no se tocan entre ellas, a la vez (7.8 · 7.9 · 7.11 · las cinco skills).**
Son ficheros distintos: el informe de House, el de Bilbo, la skill central y las cinco skills que llaman al sistema borrado. Ninguna importa a otra.

**Tanda 3 — las tres skills nuevas (7.13 · 7.13b · 7.13c) y el prompt del cierre (7.13d).**
Van después de la tanda 1 porque las cuatro se apoyan en la skill de memoria.

**Tanda 4 — los dos de proceso (7.5 · 7.6).**
Pueden ir con la tanda 3; se separan porque no son skills: son reglas de cómo vive una pregunta abierta y cómo vive un plan.

**Tanda 5 — el bloque del `CLAUDE.md` (7.12).**
Va tarde a propósito: cambia el arranque de **todos** los proyectos instalados, así que se escribe cuando ya se sabe qué existe de verdad.

**Tanda 6 — publicar (7.14).** El último. Y antes hay que arreglar el script de publicar (ver el final de este documento).

---

# LOS 18 PASOS

## 7.1 · La skill de memoria

**Qué entrega.** El documento que enseña a guardar una nota **bien a la primera**, con todos los datos puestos, para que la aduana no tenga que rebotar.

**Qué va dentro.**
- Cada tipo de nota con su comando completo de ejemplo, con todos los datos, no un esqueleto.
- Qué es obligatorio en cada tipo y qué no *(el porqué es obligatorio en una decisión; la descripción, en todas)*.
- Que el coste normal de guardar es **un comando y cero rechazos**; el rechazo es la excepción.

**Dónde.** Carpeta nueva de skill dentro del toolkit. Hoy no existe ninguna.

**Hecho cuando.** Un alta completa se escribe sin rebotar ni una vez.

---

## 7.2 · Dentro de la skill: cómo se decide

**Qué entrega.** Las tres decisiones que hoy no están escritas en ningún sitio al que se pueda mandar a nadie.

**Qué va dentro.**
- **La regla de los dos segundos** para elegir las dos zonas: si la palabra puede modificar a otra («el *testing* DE amianto») es la primera casilla; si solo puede ser el objeto, es la segunda.
- **Cuándo algo es un muro y cuándo no:** la vara es una sola y estricta — *¿puede costar datos, horas o producción caída?*
- **Cuándo algo es un bloqueante:** es pendiente **de fuera** (de ti, de un cliente, de un proveedor) **y** convierte en falso algo del proyecto o en imposible una acción.
- **El árbol de los siete tipos**, que acaba siempre en pregunta, nunca en cajón de sastre.

**Hecho cuando.** Están escritas con ejemplos.

---

## 7.2b · Dentro de la skill: ver qué notas tocan un fichero

**Qué entrega.** La explicación de la vista por fichero, escrita **una sola vez** para que ningún agente la repita en su prompt.

**Qué va dentro.** Qué es, sus dos comandos, y cuándo la usa cada oficio.

**Hecho cuando.** Ningún prompt de agente duplica ese contenido: todos apuntan aquí.

---

## 7.3 · Dentro de la skill: quién dispara una búsqueda

**Qué entrega.** La regla de que buscar en memoria **lo pides tú, hablando normal**.

**Qué va dentro.** El disparador es el usuario en lenguaje natural, y las tres prohibiciones: sin palabras clave que disparen solas, sin que Claude decida por su cuenta que toca buscar, y sin meter memoria en cada mensaje.

**Por qué.** Las tres se midieron y fallaron en el sistema viejo. Pedirlo explícito no falla.

---

## 7.4 · Dentro de la skill: contarte el menú del día

**Qué entrega.** Cómo se te cuenta el arranque en el primer mensaje.

**Qué va dentro.** El molde ya está escrito y aprobado por ti en `docs/memoria-v2/TEXTOS.md` §7: el Next con lo que pasó, los bloqueantes **con fecha**, las preguntas abiertas **diciendo cuáles bloquean trabajo** (no un número suelto), las incidencias, los planes con commits sin reflejar, y los muros que apliquen — con un emoji por sección.

**La regla que lo justifica, en tus palabras:** *«con seis preguntas abiertas, yo no me entero de nada»*.

**Hecho cuando.** El primer mensaje de una sesión real sale con esa forma.

---

## 7.5 · Cómo vive y muere una pregunta abierta

**Qué entrega.** El ciclo completo de una pregunta sin resolver.

**Qué va dentro.**
- Se resuelve **antes** de construir sobre su módulo, o cuando una decisión pisa su terreno. No caduca por calendario: caduca por evento.
- Puede parir una incidencia de investigación cuando decides atacarla.
- Al cerrarse, **sube** a hecho o **cae** a descartada — y eso queda escrito en el archivo.

**Hecho cuando.** El destino («ascendida a…») aparece de verdad en el fichero de archivadas.

---

## 7.6 · Los planes

**Qué entrega.** Cómo se convierte una decisión en un plan con seguimiento.

**Qué va dentro.**
- El **documento** del plan vive en `docs/`.
- La **incidencia** en GitHub la crea Claude a mano, **nunca un script**, y **enlaza al documento y aloja la lista tachable** *(especificación §10.2)*.
- El **acta**: un commit que enlaza la decisión con la incidencia.
- **El plan lo abre él** — Claude puede ofrecerlo en una línea, nunca abrirlo *(decisión B35, 2026-08-05)*.
- Si la decisión cambia, **se edita la incidencia abierta**: un plan, un hilo *(decisión B36, 2026-08-05)*.
- Lo único que se trae de la plantilla vieja: el apartado de **qué queda fuera** del alcance. El resto era peso muerto.

**Hecho cuando.** Un ciclo completo, de verdad, de principio a fin.

---

## 7.7 · Retirar a Gitto — ✅ HECHO

Su ficha está fuera de la lista de agentes activos y **no se ha borrado**: vive en la carpeta de retirados. La tripulación queda en nueve.

---

## 7.8 · El pie del informe de House

**Qué entrega.** Que el diagnosticador termine siempre igual: causa raíz, más el titular y las zonas propuestos para guardar la incidencia.

**Por qué importa.** Él no escribe en git; quien guarda la nota es Claude. Sin ese pie, cada vez hay que inventarse el titular.

---

## 7.9 · Bilbo empieza por el mapa

**Qué entrega.** Que el explorador, antes de entrar en detalle, entregue siempre el mapa general: módulos, quién llama a qué, y hasta dónde llega el daño de tocar algo.

**Ojo.** Hoy tiene una instrucción parecida, pero es de marzo y de otra reestructuración: no habla de zonas ni de muros. No sirve.

---

## 7.10 · El cierre de sesión recupera sus cuatro renglones — ✅ HECHO

Escribir el Next con su resumen en prosa · poner al día la incidencia del plan · **podar muros preguntando** (nunca por criterio propio) · dar de alta bloqueantes.

**Falta una comprobación:** que un cierre real ejecute los cuatro. Está verificado leyendo el fichero, no ejecutándolo.

---

## 7.11 · La skill central

**Qué entrega.** Que la skill que se carga en cada sesión deje de nombrar la memoria vieja como si viviera.

**Hueco declarado.** *«Los seis puntos»* no están enumerados en ningún documento. **Primera tarea del paso: enumerarlos y enseñártelos** antes de tocar nada.

---

## 7.12 · El bloque del `CLAUDE.md`

**Qué entrega.** El texto que el toolkit instala en el `CLAUDE.md` de **todos** tus proyectos, reescrito entero.

**Por qué es delicado.** Es el que le dice a Claude qué hacer al arrancar. Hoy manda cargar cosas que ya no existen — es el punto 2 de la deuda, y **no se cierra tocando código**: se cierra publicando.

**Qué lleva, decidido el 2026-08-05** *(aprobado sobre el texto literal)*: el arranque —leer el informe de sesión, cargar la skill central y la de memoria, y contarle el menú del día— **más las cuatro reglas que tienen que valer aunque no se cargue ninguna skill**: la memoria es un commit y no se escribe en ficheros · los índices y la lista de zonas los escriben los comandos, nunca una persona · un muro se retira preguntando, nunca por criterio propio · y los comandos los ejecuta Claude, nunca el usuario.

**El motivo de que esas cuatro vivan aquí y no solo en la skill:** el bloque se lee siempre; la skill, solo si alguien la carga.

**Y de paso, una frase del bloque de protocolos** (`unmassk-protocols`) nombra skills que aún llaman al sistema retirado — se repasa en el mismo paso.

---

## 7.13 · La skill de incidencias

**Qué entrega.** El protocolo de cuando algo se rompe.

**Qué va dentro.**
- **Tres formas de investigar:** Bilbo mira la zona · Claude le pasa los logs de producción a House · Claude le cuenta el fallo a House en lenguaje normal.
- Cuando House vuelve con el diagnóstico, **Claude guarda la incidencia en ese momento**.
- Rama del arreglo, con su tubería completa.
- Al cerrar la incidencia, el sistema **ofrece el muro** con la pregunta dentro del rechazo — que es lo que se construyó hoy.

**Cinco cosas sin decidir, declaradas en la especificación** *(se deciden al redactarla, contigo)*: con cuál de las tres vertientes se arranca · dónde desemboca la de Bilbo, que mapea pero no diagnostica · qué pasa si House no encuentra nada · si la rama del arreglo lleva incidencia de GitHub · el mecanismo exacto del cierre.

---

## 7.13b · La skill que prepara la destilación

**Qué entrega.** Lo que hay que saber **antes** de destilar la memoria vieja: cuántos commits hay, de qué clases, y cuántas rondas hacen falta.

**Por qué.** Mil commits no caben en una sesión, y el reparto no se improvisa.

**Y las rondas van en cascada**, de lo viejo a lo nuevo, nunca a la vez: cada ronda **lee las notas que produjo la anterior**. Si van ciegas entre sí, se destilan contradicciones como si todas fueran verdad.

### Lo medido en las dos pruebas en seco `[2026-08-05]`

| | Este repositorio | Omawa |
|---|---|---|
| Commits de memoria | 903 | 825 *(+455 puntos de guardado sin contar)* |
| De 100 commits | **30 notas** (22 M, 5 D, 3 Q) | **43 notas** (22 M, 19 D, 2 Q) |
| Se descarta | 43% | 25% |
| Coste de una ronda | 130.000 tokens | 143.000 |

**Un producto destila mucho mejor que una fábrica de herramientas**, y con eso cae la duda de las zonas: la ambigüedad *«trabajar en una base de datos» contra «escribir el plugin de bases de datos»* **no existe en Omawa — cero de 825 commits**. Era un caso propio de este repositorio.

**El tamaño de ronda: 100 se queda corto.** A ~1.300 tokens por commit, en una ronda caben 500. La regla no es un número fijo: **la ronda se llena hasta la mitad del contexto y la otra mitad se reserva para lo que arrastra la cascada** — y se corta en el cierre de sesión más cercano, que es el corte natural del historial. Con eso, este repositorio pasa de 10 rondas a 2 y Omawa a 5.

### Los tres huecos que dejaron las pruebas, y hay que cerrar

1. **La destilación reintroduciría la enfermedad del sistema anterior.** De las 43 notas de Omawa, **31 tienen como segunda zona `process`, `agents`, `standards`, `skill`, `toolkit`…** — o sea, **cómo se trabaja, no el producto**. Ocho usan `workflow`, que está **en la lista negra** y las haría rebotar todas. Falta la regla en el protocolo: **antes de asignar zonas, decidir si eso es memoria del proyecto o es una regla de trabajo**, que va a otro canal sin zonas.
1b. ~~**Un hueco del sistema:** el canal de reglas no puede citar de qué commits sale cada una.~~ **CERRADO — no es un hueco** `[decisión del propietario, 2026-08-05]`: *«una regla es una regla, me da igual de dónde salga; lo que importa es que estén colocadas en la temporalidad correcta»*. La ley de citar fuentes se queda para las notas del proyecto. Lo único que las reglas necesitan es **destilarse en el mismo orden de la cascada**, para que la posterior pise a la anterior cuando digan cosas distintas.

2. **Los 455 puntos de guardado de Omawa no los ha mirado nadie.** Quedaron fuera por fidelidad al método. Puede haber trabajo real que no esté en ningún otro sitio, o ser ruido. **Sin decidir.**
3. **Las nueve zonas de trabajo no usan las palabras del propietario.** `product`, `codeaudit`, `api`, `ui` y `auth` aparecen **cero veces** en los 825 commits de Omawa: allí se escribe `project`, `backend`, `frontend`, `audit-…`. Los conceptos encajan, los nombres no — se resuelve con alias en la cosecha, pero hay que saberlo antes de empezar.

**Y una lección de método, que vale para todo lo que venga:** la primera prueba se lanzó **sin darle a Bilbo la skill de memoria**, solo un resumen del formato en el encargo. De ahí salieron los fallos de zona. Lo que se está midiendo ahora no es si él sabe destilar, sino **si el documento enseña a hacerlo**.

---

## 7.13c · Compactación de memoria de agente

**Qué entrega.** Que cada agente mire sus memorias, las contraste contra el código, informe y las corrija.

**Tres condiciones**, porque un agente auditándose a sí mismo es juez y parte: cada cambio con su prueba (fichero y línea) · **nada se borra**, se marca superado · y además de contrastar, **fundir el diario en temas**.

**Medido:** Dante tiene 112 ficheros y 15.557 líneas, y 66 de esos ficheros son notas de una tarea concreta. Eso no es memoria, es un diario. Moriarty, con 3 ficheros temáticos, es la forma sana.

---

## 7.13d · El prompt del cierre de sesión

**Qué entrega.** Que el cierre lo escriba **un agente que se lee la conversación**, no Claude acordándose.

**Qué va dentro.** Un script saca **la conversación y nada más**, el agente la lee entera, escribe un contexto de unas 50 líneas, pone el Next arriba y la lista de commits abajo.

**Tres condiciones:** el filtro deja **solo lo que se dijo** —ni herramientas, ni diffs, ni informes de agentes; lo demás ya está en los commits de abajo `[decisión del propietario, 2026-08-05]`— · no puede ir al cerrar del todo, porque ahí ya no hay nadie que juzgue · y el prompt vive **dentro de la skill**, no se teclea de memoria cada vez.

**Medido el 2026-08-05, ejecutándolo contra la sesión real:** 53 MB de conversación en crudo → **633 KB** de lo que se dijo, dos días enteros. Ni un resto de herramienta, informe ni recordatorio en la salida (comprobado buscándolos).

---

## 7.14 · Publicar la versión

**Qué entrega.** Que todo lo anterior **corra de verdad** en tus sesiones. Hoy lo que corre es la copia instalada, congelada en la 1.25.0.

**Hecho cuando.** Se instala en un proyecto limpio y el arranque funciona.

---

# LO QUE HACE FALTA Y NO ESTÁ EN LOS 18

**1 · Las cinco skills que llaman al sistema borrado.** `flow` · `project-lifecycle` · `council` · `grill` · `audit`. Ninguna aparece en los 18 pasos, y las cinco te dirán de guardar cosas con comandos que ya no existen. El barrido del repo las tenía apuntadas; el plan no las recogió.

**2 · El script de publicar sigue usando el generador viejo.** `bin/release.py` llama al script del sistema muerto y usa un campo retirado. Es el paso **2.8b**, de la fase 2, sin empezar. **Va antes del 7.14** o la publicación se cae con un error.

**3 · El comando de reglas no existe.** La pieza que lee y escribe el fichero de reglas está; el comando que te lo entrega, no — no hay carpeta de comandos en el toolkit. Es el paso **3.3**, a medias.

---

# HUECOS DECLARADOS — no se rellenan solos

- **Los seis puntos de la skill central** (7.11): sin enumerar en ningún documento.
- **Las cinco cuestiones internas de la skill de incidencias** (7.13): declaradas sin resolver en la especificación.
- **Qué enciende exactamente publicar.** Los dos hooks nuevos —el arranque y la aduana— **no están registrados a propósito**: engancharlos con el sistema viejo aún vivo dispararía dos arranques a la vez. Se registran en la fase 9. Conviene decidir, antes de publicar, qué queda encendido y qué no.
