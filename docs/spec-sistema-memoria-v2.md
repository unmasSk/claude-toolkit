# Sistema de Memoria v2 — Especificación de Diseño
**Versión:** 1.0 · **Fecha:** 2026-08-01 · **Estado:** diseño cerrado, pendiente de construcción
**Propósito de este documento:** especificación completa para revisión adversarial (Council). Toda decisión lleva su justificación y, donde existe, su evidencia empírica. Los puntos abiertos están declarados explícitamente en §15; todo lo demás se considera cerrado.

---

## 1. Propósito y alcance

Sistema de memoria persistente para proyectos gestionados con Claude Code y la tripulación de agentes unmassk. Git es el sustrato: cada nota de memoria es un commit sin código de aplicación que transporta la nota **y la actualización de su línea de índice en el mismo commit** (un acto, un commit; los índices se versionan y se suben con el repo). El sistema reemplaza al actual (git-memory v1) que queda **congelado, sin arreglos adicionales**, como referencia y archivo muerto. No hay migración de historia: la memoria vieja se adapta una sola vez por destilación aditiva (§13).

Fuera del alcance de esta especificación: la skill bug-protocol (especificada en §11 pero se redacta aparte), los prompts de agentes afectados, y el plan de construcción.

---

## 2. Principios de diseño (invariantes)

Estos principios no son aspiraciones: son reglas de validación. Cualquier pieza que los viole está mal diseñada.

**P1 — Git es la fuente de verdad y es inmutable.** Nada se borra ni se reescribe jamás. Toda corrección es un commit nuevo (sustitución, cierre, alta). Los índices son proyecciones regenerables; si divergen de git, manda git.

**P2 — Un campo sin lector no existe.** Ningún campo, trailer o fichero entra al sistema sin que su lector se construya a la vez. Evidencia que motiva la regla: en el sistema v1 se escribieron 1.002 `Why:`, 605 `Touched:`, 79 `Risk:` y 63 `Issue:` que ningún script leyó jamás.

**P3 — La lista de campos y zonas válidos es la misma pieza que valida.** El contrato del que escribe y el vocabulario del que lee no pueden vivir en sitios distintos. Evidencia: el trailer `Sources:` era obligatorio por contrato del agente Gitto, se cumplió 25 veces, y los parsers lo descartaron en silencio porque no estaba en la lista de claves válidas.

**P4 — Mecanismo antes que disciplina; protocolo antes que automatismo.** Nada crítico depende de que el modelo "se acuerde". Lo que debe ocurrir siempre lo garantiza un gate (hook que valida) o un protocolo invocado por el usuario (skill). Los automatismos complejos con estado se evitan: cada pieza automática es superficie de fallo. Evidencia en ambos sentidos: las reglas de proceso guardadas como memoria produjeron 114 recordatorios duplicados sin efecto; las skills de protocolo invocadas explícitamente (close-session) se ejecutan correctamente de forma consistente.

**P5 — La aduana nunca pregunta en el aire.** Un hook solo puede permitir o rechazar. Toda "pregunta" del sistema es un rechazo cuyo mensaje contiene la pregunta y las opciones; responder es relanzar el comando con la respuesta como argumento (`--replaces D-030`, `--origin none`, `--incident new`). El ciclo es: intento → rechazo informativo → relanzamiento. Es síncrono, visible en el chat, y el canal de rechazo está medido como fiable (`decision:block` llega al modelo).
**Las respuestas se traen por adelantado:** el comando admite todos los flags en el primer intento (`--stops no --origin none`), y la aduana solo rechaza si FALTA información. El coste normal de guardar una nota es UN comando, cero rechazos; la skill de memoria enseña a traer los flags puestos. Los rechazos son la excepción, no el ciclo habitual.

**P6 — Toda pieza enseña un número al arrancar; el cero es alarma, no silencio.** Una zona sin notas devuelve "cero notas" en alto. Un contador que no aparece es un fallo, no una ausencia.

**P7 — Lo instalado se verifica contra lo escrito.** El sistema corre desde una caché de plugin que puede congelarse. Evidencia: seis hooks corrieron versiones viejas durante días mientras el repo contenía los arreglos; el vigilante existente no podía detectarlo porque viajaba dentro de la caché que vigilaba. El chequeo de sincronización debe operar desde fuera de la caché.

**P8 — Idioma por función: lo que se busca, en inglés; lo que se lee, en español.** Titulares y Keys (superficies de búsqueda) en inglés. Why, Description y Context (superficies de lectura) en español. Sin mezclas: una key en español es un agujero en la red de búsqueda.

**P9 — Cuantas menos piezas, mejor — pero cada una clarísima y fiable.** Se retira todo lo que no tenga caso de uso real demostrado. Los campos diseñados "por si acaso" nacen muertos (evidencia: `Conflict:`/`Resolution:` nacieron en el commit inicial sin decisión que los justificara; 1 uso en 5 meses).

**P10 — Presentación heredada.** Los emojis por tipo y la estructura visual jerárquica del formato v1 se conservan en todo (🧭 decisión, 📌 memo, 💾 context, etc.). El rediseño cambia tipos, zonas y campos, no la legibilidad.

**P11 — Todo timestamp en UTC**, y toda hora mostrada al usuario lleva la etiqueta "UTC" explícita.

**P12 — Banco de pruebas adversarial** con ejecución automática y resultado visible, que intente romper el sistema de forma continua.

---

## 3. El formato de nota

### 3.1 Titular

```
[TIPO-ID][zona1][zona2] resumen en inglés, ≤60 caracteres
```

- **TIPO-ID:** letra del tipo + contador simple por tipo (`D-030`, `R-007`). El contador lo asigna el script leyendo el índice. El choque multi-máquina no existe operativamente (el usuario trabaja en una sola máquina a la vez); como salvaguarda, el boot incluye un chequeo de IDs duplicados como alarma pasiva — detecta, no repara.
- **zona1 — el trabajo desde el que se habla:** product, testing, codeaudit, docs, deploy, database, api, ui, auth. Prácticamente común entre proyectos.
- **zona2 — la parte del producto de la que se habla:** propia de cada proyecto (p. ej. amianto, inventario, catastro).
- **Regla de desambiguación ("regla de dos segundos"):** si la palabra puede modificar a otra ("el testing DE amianto") es zona1; si solo puede ser objeto, es zona2.

### 3.2 Zonas: lista cerrada, sin comodines

- Las dos zonas son **obligatorias y reales**. No existen comodines (`core`, `producto`, `general`, `all`: todos rechazados). Una nota que "no tiene zona" es una nota mal clasificada o una zona que falta en la lista.
- Las zonas válidas viven en `zones.json`, lista cerrada por proyecto con **alias** para variantes (`front` → `frontend`).
- **El número de zonas es irrelevante; su calidad no.** Da igual 20 que 200: el objetivo es que no convivan sinónimos ni variantes de la misma cosa (una batería es una batería; una pantalla es una pantalla). El alta en dos pasos —buscar antes de crear; crear obligatoriamente si es genuinamente nuevo— **reduce** ese riesgo, no lo elimina: la búsqueda de equivalentes la hace el modelo, y puede no ver una equivalencia con vocabulario distinto. Decisión informada del propietario: se acepta el residuo a cambio de cero fricción, y la limpieza de sinónimos que se cuelen es tarea de mantenimiento humano puntual.
- **Alta de zona nueva, en dos pasos guiados por la aduana:** (1) rechazo con "esa zona no existe; busca en zones.json por si es otra con distinto nombre"; (2) si realmente falta, Claude la da de alta él mismo editando zones.json —sin pedir permiso; el usuario lo ve en el chat— y relanza. No es posible engañar al script: o la zona existe, o se crea a la vista antes de pasar.
- **Lista negra de zonas:** `claude`, `user`, `session`, `project`, `workflow` — rechazadas con el mensaje "esto no es memoria del proyecto; va al fichero de rules". Motivación: un tercio de la memoria v1 medida en tres proyectos era configuración de trabajo disfrazada de memoria.
- **Palabra ilegal `audit`:** ambigua entre el módulo de aplicación y las auditorías de agentes. El módulo entra como `registro` (zona2); las auditorías de agentes como `codeaudit` (zona1). Quien escriba `audit` recibe rechazo con la disyuntiva.

### 3.3 Campos del cuerpo

| Campo | Obligatorio | Idioma | Contenido |
|---|---|---|---|
| `Why:` | En D (y recomendado en R/X/I) | Español | El porqué. |
| `Keys:` | Recomendado | Inglés | Hasta 5 sinónimos que **no** estén en el titular. Red de búsqueda. |
| `Description:` | Sí | Español | Resumen destilado de la conversación o trabajo que dio lugar a la nota. |
| `Origin:` | Ver §3.4 | — | Puntero "de qué nota/incidencia nazco". |
| `Replaces:` | Al sustituir | — | Puntero "a qué nota reemplazo". |
| `Touched:` | Automático | — | Solo en commits de trabajo; lo escribe **exclusivamente el script** desde `git diff --name-only`. Prohibido a mano: del diff no se puede mentir. |

No existen más campos. `Council` y `Plan` no son campos de la nota: el veredicto de un council forma parte del Why o la Description; el plan es otro canal (§10). Retirados con evidencia: `Risk` (79 escritos, 0 leídos, enum jamás validado; la urgencia son labels de issue), `Conflict`/`Resolution` (1 uso, lector inalcanzable), `Sources` (duplicaba `Origin:`; su regla sobrevive en §6.5), `Crown`/`Retract-Crown` (sin función en el diseño nuevo), `Subsume`/`Triage` (nunca existieron como trailers).

### 3.4 Keys marcadoras

Cuatro keys tienen significado transversal y vocabulario controlado por la aduana, que las normaliza (`seguridad`→`security`, `perf`→`performance`, `anti-pattern`→`antipattern`): **`antipattern`, `security`, `performance`, `legal`**. El resto de keys son texto libre en inglés. La lista de marcadoras es viva como zones.json: se amplía cuando el uso lo pida, nunca en la mesa.

---

## 4. Los siete tipos

| Tipo | Nombre | Qué es | Cómo muere |
|---|---|---|---|
| **D** | decision | Elección tomada, con su Why obligatorio | Nunca se borra; otra D la sustituye con `Replaces:` |
| **M** | memo | Hecho estable del proyecto ("Stripe manda webhooks en UTC") | `Replaces:` o `close` (§5) |
| **R** | restriction | La valla: hecho que puede **parar o romper** un desarrollo ("jamás tests contra producción") | `Replaces:` o `close` |
| **Q** | question | Pregunta abierta sin confirmar | Asciende a M o cae a X; caduca **por evento**, no por fecha |
| **X** | discarded | Lo estudiado y rechazado; existe para que nadie lo re-proponga | Permanente |
| **I** | incident | Postmortem: se rompió algo + causa + qué se hizo | Se cierra (dentro de bug-protocol, §11) |
| **B** | blocker | Pendiente **de fuera** que hace que cosas no funcionen o no sean verdad ("el dominio .es de staging no está comprado") | `close` al resolverse |

Notas por tipo:

- **D:** decidir y planificar son actos distintos (§10). Al guardarse una D tras una elección entre opciones, las opciones perdedoras nacen como **X automáticos enlazados** con `Origin: D-nnn` en el mismo acto.
- **M:** las cinco categorías del memo v1 (preference/requirement/antipattern/stack/deadend) **mueren**. El censo real de los 201 memos del repo del toolkit reveló cinco poblaciones distintas conviviendo, y cada una tiene ahora su destino: hechos → M; vallas → R; preferencias de trabajo → rules (§12); informes de investigación → se destilan (hechos a M, negativos a X, el informe completo a docs vía Alexandria si tiene valor de mapa); trabajo pendiente → Q. `antipattern` sobrevive como key marcadora.
- **R:** nace de la **pregunta obligatoria de la aduana** en todo alta de M/R: "¿puede costar datos, horas o producción caída? sí/no". Una sola vara, la estricta, y la pregunta de la aduana la usa literal — el contrato vive en una pieza (P3). Y la R tiene muerte por protocolo: close-session incluye la pregunta "¿alguna R del arranque ya no es verdad? ciérrala", de modo que la lista no crece sin poda. **Todas las R salen en cada arranque sin tope** (§8.3): son pocas por naturaleza, y si hay 47 el propio número delata que algo se está clasificando mal. En los informes de zona van arriba, literales. Al nacer una R, la aduana presenta **todas** las incidencias candidatas de la zona (nunca una sola preseleccionada) y Claude elige con calma —en su turno normal, pudiendo leer los commits candidatos o preguntar al usuario— una, varias o ninguna como `Origin:`.
- **Q:** caduca por evento: debe resolverse antes de construir sobre su módulo o cuando una decisión pisa su terreno; el informe de zona la planta delante. Puede **parir una issue de investigación** cuando el usuario decide atacarla (simetría con D→plan-issue): la Q sigue viva en memoria; la issue es el vehículo; al cerrarse la issue, la Q asciende a M o cae a X.
- **B:** criterio de calibración (irá en la skill de memoria): pendiente **de fuera** (del usuario, del cliente, de un proveedor) **y** convierte afirmaciones del proyecto en falsas o acciones en imposibles. Lleva campo `espera:` con el responsable. Nace en caliente (al chocar con el muro) o en el cierre de sesión (renglón del protocolo: "¿quedó algo parado esperando algo de alguien?").

---

## 5. Ciclo de vida y retiradas

Un solo mecanismo universal de retirada, con dos caminos. Los trailers-lápida v1 (`Resolved-Memo`, `Resolved-Remember`, `Resolved-Next`, `Stale-Blocker`) **desaparecen**.

**Camino 1 — la mata su reemplazo (el habitual).** Al guardar una nota, la aduana busca parecidas en la zona (keys compartidas y texto). Si encuentra, rechaza con las candidatas dentro: "¿la tuya sustituye a M-041, conviven, o es duplicado?". El relanzamiento con `--replaces M-041` escribe la nueva con su puntero; el script retira la línea vieja del índice hacia ARCHIVED.md ("replaced by M-062"). **La nota vieja no se caza por memoria ni por vigilancia: se caza cuando su reemplazo intenta entrar por la puerta.**

**Camino 2 — se cruza y chirría (sin reemplazo).** `close M-041 "motivo"` → commit vacío de cierre; la línea sale del índice y entra en ARCHIVED.md ("closed: motivo"). El disparador es cruzársela en un informe y ver que ya no es verdad — no la memoria de nadie.

Las notas que nadie se cruza jamás no necesitan caza: son inofensivas por definición. Los tipos peligrosos tienen visibilidad forzada propia (R y B completos en cada boot; Q por evento; I contadas en boot).

---

## 6. La aduana

Dos piezas con papeles distintos: **el generador** escribe los commits (formato, emojis, Touched desde el diff, propagación de errores de git) y **la aduana** valida antes de dejar pasar. La lista de zonas, campos y keys válidos vive en la aduana (P3). La aduana es un hook PreToolUse sobre el comando de commit. Intercepta a **todos** los que commitean —sesión principal y subagentes— porque el hook es del harness, no de la sesión (verificado: los hooks disparan también en despachos de subagentes). Validaciones:

1. **Zonas** contra zones.json, con alias y el alta en dos pasos (§3.2). Lista negra y palabra ilegal `audit`.
2. **Árbol de tipos que acaba en pregunta, nunca en cajón:** ¿elección? → D (con sus X automáticos). ¿Hecho? → M. ¿Valla? → R. ¿Pregunta abierta? → Q. ¿Pendiente de fuera? → B. Si la nota no encaja limpiamente en D/M/R/Q/X/I/B, la aduana rechaza y pregunta qué es. Que el sistema diga "no sé clasificar esto" es información de diseño; embutirlo en un saco es como se pudrió la memoria v1.
3. **Pregunta obligatoria M/R** ("¿puede costar datos, horas o producción caída?").
4. **Sustitución exigida:** decisión que pisa a otra sin `Replaces:` → rechazo pidiéndolo. Detector de parecidas con candidatas completas (§5).
5. **Regla de consolidación:** toda nota de consolidación/destilación (las de la adaptación, §13) exige `Origin:` con al menos una fuente — **por tipo de nota, no por firma del autor**: compactar sin fuentes es imposible por definición, lo escriba quien lo escriba. Así el contrato vive en la aduana (P3), no en la prosa de ningún agente.
6. **Keys marcadoras** normalizadas (§3.4).
7. **WIP sin fricción:** los commits `wip` no reciben ninguna pregunta. El wip es un punto de guardado sagrado; fricción al guardar = no se guarda. (Su diff queda registrado en git para siempre: commitear no es perder el diferencial.)
8. **Acta de plan:** verificación única contra GitHub de que la issue referenciada existe (§10.3). Los commits de trabajo con `Issue: #N` pasan sin consulta: medio segundo y una dependencia externa por commit para algo que casi nunca falla es peaje injustificado (medido: 0,44 s/consulta).
9. **Errores propagados:** el generador nuevo propaga el error real de git; jamás lo silencia (defecto reproducido en el wrapper v1: "Error: git commit failed:" vacío).

---

## 7. Los índices (`.claude/project-memory/`)

Carpeta hermana de `agent-memory/`. Contiene **exactamente ocho ficheros** y nada más:

```
DECISIONS.md  MEMOS.md  RESTRICTIONS.md  QUESTIONS.md
INCIDENTS.md  DISCARDED.md  BLOCKED.md  ARCHIVED.md
```

- **Son índices, no la memoria:** una línea por nota = ID + titular. El contenido vive solo en git.
- Los escribe **solo el script**; nadie los edita a mano; si divergen de git, manda git (P1) — y esa regla tiene ejecutor: el boot comprueba la coherencia índices↔git y la enseña (✓/⚠), y existe un comando de regeneración total desde git. La actualización del índice viaja **en el mismo commit** que la nota.
- **Concurrencia:** las notas de memoria las escribe solo el orquestador, de una en una — sin caso de choque. Los commits de CÓDIGO sí pueden coincidir (oleadas con varios implementadores en paralelo): para eso **se conserva el candado del v1**, ya probado en producción.
- **ARCHIVED.md es un fichero único cronológico** (no una carpeta): todo lo retirado, una línea por nota — fecha + titular + destino ("replaced by D-031" / "closed: motivo" / "promoted to M-062"). El tipo viaja en la propia línea; se pregunta al pasado por fecha.
- **No existe fichero índice general** (MEMORY.md rechazado): la lista de ficheros la documenta la skill; los números los calcula el boot al vuelo contando líneas; un fichero-portada sería un duplicado capaz de mentir.
- **No existe PLANS.md**: los planes no se indexan aquí (§10.2).

---

## 8. La lectura

### 8.1 El informe (único producto de búsqueda)

Buscar devuelve **el estado completo de una zona**, nunca una lista de commits: vigente por defecto; historia completa tras `--todo`; agrupación en racimos **por punteros** (`Origin`/`Replaces` — determinista, falla a gritos; nunca por similitud de IA ni por keys); restricciones ⚠ arriba, literales; preguntas Q vivas al final como "lo que espera del dueño". Cuatro entradas:

- **Por ID:** `D-030` → la nota y su racimo.
- **Por zona:** `auth` → estado completo de auth.
- **Por palabra:** `stripe` → estado completo de las zonas donde aparece, con las líneas que casaron señaladas.
- **Por fichero:** `auth.service.ts` → sus commits (titular, desplegable al cuerpo). Implementación: `git log -- <fichero>`; git ya es ese registro, la pieza nueva es solo la vista. **Bajo demanda exclusivamente** — el hook de pre-edición fue evaluado y rechazado: para editar, el pasado sobra (el agente lee el fichero como está); inyectar historia en cada edición es gasto de tokens sin valor. El radio de daño es oficio de Bilbo (zoom-out), no de quien edita.

Zona sin notas → "cero notas" en alto (P6).

### 8.2 Los tres momentos de lectura

1. **Al despachar un agente a una zona:** el informe de la zona viaja dentro del encargo. Usa el tubo de inyección ya existente y medido (llega a los nueve agentes); cambia el contenido, no el mecanismo. **El contenido se reparte por oficio** (veredicto del Council, aceptado): quien puede violar una valla es quien tiene que verla —
   - **Ultron** (implementa): las R de la zona + la D vigente que gobierna el módulo.
   - **Dante** (tests): las R + las I de la zona — cada cicatriz pasada se convierte en test de regresión sin que nadie lo pida.
   - **House** (diagnostica): las I de la zona — medio bug es el mismo bug de la otra vez.
   - **Argus/Cerberus** (revisan): las I abiertas + notas con keys `security`/`antipattern` — revisan contra lo que ya falló.
   - **Moriarty** (ataca): las R + las I de la zona — su oficio es intentar romper: que ataque directamente las vallas y repita los golpes que ya tumbaron el sistema antes.
   - **Yoda** (juzga): la D vigente + las R de la zona — se juzga contra el contrato escrito, no contra el gusto del juez.
   - **Bilbo** (explora): el informe completo de la zona.
   Con el reparto por oficio, la valla llega directa a quien puede romperla — sin depender del resumen de ningún intermediario.
2. **Pregunta del usuario que mira al pasado:** el disparador es **el usuario en lenguaje natural** ("busca en memoria qué decidimos del login") → Claude ejecuta el script de búsqueda. Sin disparadores léxicos, sin juicio espontáneo del modelo (medido como no fiable; council 4-1 en contra), sin inyección por mensaje (retirada en v1 por ruido). Pedir explícito no falla.
3. **Reglas de conducta:** canal aparte (§12).

### 8.3 El boot: el menú del día

El arranque de sesión (canal medido 100% fiable: 64/64) presenta, en este orden:

```
⏩ ÚLTIMO NEXT (con su Context debajo)                     ← §9
⛔ TODOS los B, con su "espera: quién"                     ← sin tope
⚠ TODAS las R                                             ← sin tope ni presupuesto
Recuentos: Q sin resolver · issues abiertas · I abiertas   ← solo números
Avisos: plan #N con commits sin reflejar (§10.4) · IDs duplicados (§3.1) · índices coherentes con git ✓/⚠
```

Claude comunica el menú al usuario en su primer mensaje y **el usuario decide el rumbo** (Next, preguntas, issues u otra cosa). El boot pone el mapa; no decide. **Criterio de visibilidad, explícito:** R y B salen enteras porque son seguridad — no se puede trabajar sin verlas; las Q e issues salen como recuento porque son el backlog del propietario — las elige él del menú. No es una inconsistencia: son dos naturalezas distintas. (Las Q vivas de una zona ya aparecen, además, al final del informe de esa zona cuando viaja a un agente.) Los presupuestos de renderizado del v1 (que ocultaban el 94-96% de la memoria) desaparecen para R y B: su valor es precisamente la visibilidad incondicional.

---

## 9. Context/Next: la compactación de la conversación

Redefinición completa respecto al v1. El context **no** es otro commit que narra trabajo (eso ya lo cuentan los commits de la sesión): es **la compactación de la conversación** — lo hablado que no vive en ningún commit y se perdería al cerrar.

```
⏩ implement discussed changes to close-session skill
Keys: close-session, checkpoint, plan
Context:
- Revisado el diseño del checkpoint: muere el automático, lo hace close-session
- Punto de inflexión: fuera comodines — toda nota lleva dos zonas reales
- Decidido de palabra: los planes viven en docs/ como plan-*.md
- Quedó en el aire el alcance de facturación; hablar antes de empezar
```

- **El titular ES el Next**, obligatorio, con el emoji de avance ⏩. Es la orden del día de la sesión siguiente.
- `Keys:` como cualquier commit (es su superficie de enlace), en inglés.
- El cuerpo es **`Context:`** (no Description): la conversación destilada en puntos — inflexiones, decisiones de palabra, hilos abiertos. Sin transcripción ("Jose dijo / yo dije"). En español.
- Lo escribe **close-session**. Cada cierre pisa al anterior: el boot enseña solo el último; los anteriores quedan en git como historia gratuita.
- **Renglones que close-session gana con este diseño (consolidado):** (1) escribir el context/Next; (2) actualizar la issue-plan trabajada — checkboxes + comentario resumen (§10.4); (3) poda de vallas — "¿alguna R del arranque ya no es verdad? ciérrala" (§4); (4) alta de bloqueantes — "¿quedó algo parado esperando algo de alguien? → commitea el B" (§4).
- **Sin zonas, sin índice, sin lápida:** es estado, no memoria del proyecto. No se busca; se lee entero al arrancar.
- Puede citar issues (`#47`) a mano. **La creación automática de issues desde el Next queda retirada** — evidencia concluyente: 416 trailers `Next:` en el proyecto más grande y **cero** issues creadas por el mecanismo automático en toda su vida; además los Next reales son párrafos con condiciones y gates, no títulos.

---

## 10. Decisiones y planes: los tres momentos

### 10.1 Momento 1 — decidir

Nota D con Why + Keys + Description, y los X de las alternativas perdedoras enlazados con `Origin:` en el mismo acto. Ejemplo canónico:

```
🧭 [D-030][product][auth] login with JWT + Google OAuth
Why: sesiones no escalan multi-tenant; Google evita gestionar passwords propios
Keys: token, oauth, sso, signin
Description: Brainstorm sobre el login. Se valoraron sesiones de servidor,
login propio y JWT...
```

### 10.2 Momento 2 — el plan

Decidir y planificar son actos distintos. El plan:

- **Se diseña en conversación** (usuario + Claude). La issue de GitHub la crea Claude ahí mismo con `gh` — nunca un script. Evidencia de la radiografía de la issue-plan real: la issue buena nació a mano, dentro de un milestone que ya era el plan macro; cuerpo con checklist de ficheros + workflow + DoD; cuerpo vivo que se va marcando; ciclo cierre→reapertura→cierre.
- **El documento del plan** vive en `docs/` con nombre propio (`plan-login.md`), como los planes que ya genera Claude Code. La issue enlaza al documento y aloja el **roadmap/checklist tachable**.
- **El acta en git** enlaza decisión → issue (`Origin: D-030`, referencia `#47`). La aduana verifica la existencia de la issue una única vez, aquí.

### 10.3 Momento 3 — el cambio de decisión

Nueva D con `Replaces: D-030`. Git no se toca; la issue del plan —que es mutable por diseño— se edita para reflejar el alcance nuevo. El puntero siempre lo pone lo nuevo hacia lo viejo.

### 10.4 Mantenimiento del plan

- Los commits de trabajo llevan `Issue: #47` (detección exacta verificada: `git log --grep="^Issue: #N"`, cero falsos positivos).
- **La issue la pone al día el protocolo close-session** (renglón nuevo en su paso de higiene de tracker): marcar checkboxes de lo completado + comentario resumen. El checkpoint automático en SessionEnd fue diseñado, ensayado y **retirado** en favor del protocolo; con él mueren sus tres complicaciones (frontera de sesión, marca de máquina en comentarios, coste por N planes).
- **Red de seguridad en el boot** (consulta simple, 0,85 s medidos): si hay commits `Issue: #N` posteriores al último comentario de la issue → aviso "plan #47: N commits sin reflejar".
- **Al merge: squash.** Los wips se comprimen; el Touched del commit final es la unión completa del diff contra la base de la rama (verificado empíricamente). La historia que importa es la de capítulos (un merge = un capítulo), no la de borradores.

---

## 11. Incidencias: protocolo, no maquinaria

La incidencia vive dentro de la **skill `unmassk-bug-protocol`** (hermana de close-session), invocada por skill-router o por el usuario. Especificación dictada:

1. **Investigación, tres vertientes:** (a) Bilbo examina la zona de conflicto (zoom-out inherente); (b) Claude lee los logs de producción y se los pasa a House; (c) Claude relata el fallo a House en lenguaje natural y House investiga logs y código.
2. **A la vuelta de House con veredicto de bug encontrado → Claude commitea la I en ese momento**, con el pie estructurado que House incorpora a su informe (causa raíz + titular y zonas propuestos). House no escribe git.
3. Rama del fix → pipeline completa (Ultron, tests, wips necesarios).
4. Al terminar: squash, cierre de rama, cierre de issue si la hubo.
5. **Cierre de la I** en el commit final; la aduana "ofrece" ahí la **R** con su única mecánica posible (P5): rechaza el commit de cierre con la pregunta dentro ("¿de esta cicatriz sale valla? --restriction new|no") — la cadena explosión → diagnóstico → postmortem → valla, sin depender de memoria.

La pregunta del dolor (¿esto costó datos/horas/producción?) vive **en el protocolo**, no en la aduana. Red de seguridad: recuento de I abiertas en cada boot. Puerta manual siempre abierta (incidencias sin House: aviso externo del cliente, etc.). Una I con trabajo largo puede parir issue, como D y Q.

**Agujero residual asumido explícitamente:** un bug que nadie encuadra como bug no carga la skill. Precio aceptado a cambio de retirar la maquinaria automática de detección (registro de despachos interrogante, tercer estado, SubagentStop, barrido de fantasmas), cuyo análisis de fallos superaba con creces al del protocolo. El conocimiento de la sonda queda archivado y verificado por si se necesita: el identificador de agente llega fiable en `tool_input.subagent_type` (normalización: tras el último `:`, minúsculas), la herramienta se llama **`Agent`** (no `Task`), y el payload regala `description`, `tool_use_id`, `prompt_id` y `effort.level`.

**Cinco puntos a definir al redactar la skill (declarados, no resueltos):** criterio de arranque entre las tres vertientes; desemboque de la vertiente (a) — Bilbo mapea, no diagnostica; caso House-no-encuentra; si la rama del fix lleva issue de GitHub; mecanismo exacto del cierre de la I.

---

## 12. Remembers / rules: fuera del sistema

Los remember (user/claude) son configuración de cómo trabajar, no memoria del proyecto. Medido: un tercio de toda la memoria v1, replicado en tres proyectos.

- Flujo: commit vacío (nomenclatura nueva posible) → el script lo detecta → lo añade a la lista de remembers, organizada, en su fichero propio.
- **No** aparecen en búsquedas, ni en informes, ni los lee ningún agente.
- El usuario los invoca con su comando (`/remember`), que entrega el fichero **entero** a Claude.
- Sin zonas, sin aduana de zonas, sin casilla — a propósito.
- Punto abierto declarado: el dedup de remembers (dos frases distintas con el mismo significado) excede a un script; requiere agente. Pendiente de revisar; no bloquea nada.

---

## 13. Instalación y adaptación de memoria v1

**Convivencia v1↔v2 durante la construcción (Council, aceptado):** el v1 sigue vivo y escribiendo mientras el v2 se construye, y la aduana nueva rechazaría todo lo que el v1 escribe (ninguna nota vieja lleva dos zonas ni pasa el árbol de tipos). Dos decisiones tomadas ANTES de construir:
- **Interruptor:** la aduana nace apagada por defecto (flag/env var) y se enciende proyecto a proyecto en el momento del corte.
- **Fecha de corte por proyecto:** lo que el v1 escriba hasta ese día entra en la destilación; desde ese día, solo formato nuevo. Sin fecha explícita, las notas de las semanas de construcción no las destila nadie.

- **La consolidación periódica muere.** Era la medicina del sistema enfermo (puerta abierta → bibliotecario a posteriori). La sustituyen: aduana en la entrada + muerte por diseño de cada tipo + lectura de solo-vigente. No queda trabajo para un compactador recurrente.
- **La adaptación es una fase única de instalación:** en un proyecto con memoria v1, Gitto la destila **una vez** a notas de formato nuevo. Aditivo (los commits viejos no se tocan jamás — P1), por partes con tope por pasada, "en la duda, proponer al usuario", y `Origin:` obligatorio citando los hashes v1 de los que destila (§6.5).
- Gitto pierde su modo consolidador periódico (coronas), gana el modo adaptador único, y conserva sus modos oráculo y ejecutor.
- **Cero migración de historia. Cero reescritura.** Lo no destilado queda como archivo muerto consultable.

---

## 14. Evidencia empírica que sustenta el diseño

Resumen de mediciones y ensayos realizados sobre los repos reales (claude-toolkit, omawa), citados a lo largo del documento:

1. **Auditoría de trailers en código:** 11 trailers vivos; 5 zombis de solo-escritura (Why 1.002, Touched 605, Risk 79, Issue 63, Conflict 1); `Sources:` obligatorio-e-invisible (25 usos); `Resolution` con lector inalcanzable; el parser documentado como "usado por hooks" solo lo usaban los tests.
2. **Canales de entrega medidos (8.700 ejecuciones, 23 sesiones):** SessionStart 64/64; UserPromptSubmit 1445/1445; Stop stderr 0/2506; PreToolUse stderr 0/4688 (pero `decision:block` sí llega); PreCompact 0. `Stop` dispara por turno (~109/sesión), no por sesión. `SessionEnd` existe en Claude Code y el toolkit no lo usaba.
3. **close-session es prosa en su totalidad** (9 pasos, ninguno ejecutado por el harness) — y aun así se ejecuta correctamente al ser invocado: base empírica de P4.
4. **Radiografía de la issue-plan real (#2 de omawa):** nacida a mano dentro de un milestone-plan; el único commit de memoria que la cita llegó 45 días después y de pasada.
5. **Mecanismo automático de issues:** 416 `Next:` en omawa, 0 issues con el label del wrapper, de 94 totales.
6. **Ensayo operativo del ciclo del plan** (issue de prueba real): ciclo completo funcional; tiempos gh 0,44–1,58 s; cruce de arranque 0,85 s; grep del trailer exacto; 10 agujeros documentados que alimentaron §10.
7. **Sonda del payload de despachos:** `tool_name == "Agent"`, `subagent_type` con prefijo de plugin, normalización verificada contra ambas formas.
8. **Incidente de la caché del plugin:** 6 hooks divergentes repo↔caché durante días; causa raíz en dos eslabones manuales; resuelto con release 1.25.0; motiva P7.
9. **Censo de memoria:** omawa 580 notas / 201 zonas en ramas vivas (el censo previo con `--all` estaba inflado un 40% por un tag de archivo); 57% de zonas de un solo uso — refuerza la lista cerrada. 201 memos del toolkit = 5 poblaciones distintas — motiva la partición M/R y los destinos de §4.
10. **Glossary cache v1:** diccionario a posteriori; 94 zonas, 36 de un solo uso, `frontend`/`front`/`next` conviviendo — "documenta el caos, no lo evita"; se recicla como cantera para destilar zones.json.

---

## 15. Validación del sistema

**Primera prueba de la construcción (Council + criterio del propietario):** antes de repartir el tubo a los nueve roles, una semana con UN solo cambio — las R de la zona inyectadas a Ultron. Criterio de éxito decidido de antemano para que el resultado sea un sí/no y no una impresión: el prompt de Ultron exige una línea en su informe si una R le cambió lo que iba a hacer ("R-007 me hizo apuntar los tests a staging en vez de a prod"). Si en una semana ninguna valla cambió nada observable, el problema no es la selección del contenido sino que lo inyectado se ignora — conclusión más valiosa que descubrirlo con el sistema entero construido.

**Aviso estructural asumido (Council):** el `wip` está exento de toda pregunta de la aduana (correcto: fricción al guardar = no se guarda), y por tanto es el desagüe natural cuando la aduana moleste — el escape no produce notas malas, produce CERO notas. Se vigila con el uso, no con maquinaria.

**El juicio final sobre si el sistema funciona es del propietario** — él conserva la continuidad entre sesiones que los modelos no tienen. Lo que sea testeable mecánicamente, se testea (banco de pruebas adversarial de P12, con ejecución automática y resultado visible); lo que no, lo dictamina el propietario con el uso. No se fijan métricas de éxito numéricas: los contadores del sistema (P6) informan, no juzgan.

Nota de revisión: se evaluó y descartó un contador de "notas con puntero". El detector de parecidas de la aduana es léxico y puede no ver equivalencias con vocabulario distinto — no es garantía total. El descarte es decisión del propietario: los contadores informan, el juicio es suyo.

---

## 16. Puntos abiertos declarados

Ninguno bloquea la construcción del núcleo. Se listan para que la revisión no los descubra como omisiones:

1. Los cinco puntos internos de la skill bug-protocol (§11), a definir al redactarla.
2. Prompts por reescribir: Gitto (§13), House (pie de informe, §11), Bilbo (zoom-out como paso obligatorio: mapa de módulos, llamantes y radio de daño en todo informe).
3. Papel de Alexandria en el sistema nuevo (destino "docs" de §4 ya decidido; el flujo de documentación, por hablar).
4. Listas de zonas definitivas por proyecto (tarea del usuario; materia prima preparada para monyma y omawa).
5. Dedup semántico de remembers (§12).
6. Carril de "ensayo operativo" en la tripulación (ninguna definición de agente lo cubre; las tareas de ensayo rebotan).
7. Resultados de la sonda `additionalContext` sobre los hooks Stop del v1 (sin leer; afecta solo al sistema congelado).
8. **El plan de construcción es fase aparte:** releer esta especificación completa, montar plan y roadmap. Orden ya decidido: generador y aduana primero; la skill bug-protocol después de ambos (commitea en formato nuevo). Primera prueba: la de Ultron (§15).

---

## 17. Puntos muertos (no reabrir sin evidencia nueva)

- Cambiar el almacén a SQLite/JSONL/embeddings → git se queda (decisión explícita del propietario).
- La capa (frontend/backend) como tercera casilla → se deduce de Touched en los commits de trabajo (las notas de memoria no tocan ficheros y no lo llevan).
- La actividad (auditoría, migración) como eje/casilla → va en el titular.
- Comodines de zona (`core`, `producto`, `general`, `all`) → dos zonas reales siempre.
- Deducción de zona desde ficheros (mapa zona↔rutas) → innecesaria: el fichero es el fichero.
- Hook de historial pre-edición → el pasado sobra para editar; vista por fichero bajo demanda.
- Buscar casilla a los remembers → no la tienen a propósito.
- Agrupar informes por similitud de IA o por keys → punteros.
- Índice general MEMORY.md / índice de planes PLANS.md → rechazados.
- Índices en `docs/` → sustituidos por `.claude/project-memory/`.
- Inyección de memoria por mensaje → retirada; council 4-1 en contra de reactivarla.
- Reescritura/migración de notas v1 → adaptación aditiva única.
- Caducidad de Q por calendario → por evento.
- Creación automática de issues (desde Next o planes) → retirada con evidencia 416/0.
- Checkpoint automático de planes en SessionEnd → sustituido por close-session.
- Consolidación periódica / coronas → retiradas.
- Registro de despachos como interrogador de la aduana → archivado; sustituido por bug-protocol.
- Trailers retirados: Risk, Conflict, Resolution, Sources (nombre), Crown, Retract-Crown, Resolved-*, Stale-Blocker.
- `Supersedes`/`Source` como nombres de puntero → `Replaces`/`Origin`.
- Tipo P / [PLAN] con ID propio → el plan es documento + issue + acta.
- Base común de 7 zonas → con dos casillas, la base común es la casilla 1 completa.

---

## 18. Glosario

| Término | Definición |
|---|---|
| **Nota** | Entrada de memoria: commit sin código de aplicación (lleva la nota + su línea de índice) de tipo D, M, R, Q, X, I o B |
| **Titular** | Primera línea: `[TIPO-ID][zona1][zona2] resumen` en inglés, ≤60 chars |
| **Zona** | Palabra válida de casilla; vive en zones.json (lista cerrada con alias) |
| **Aduana** | Hook PreToolUse que valida todo commit de memoria; único enforcement (P5) |
| **Rechazo informativo** | Mecánica universal de la aduana: bloqueo cuyo mensaje contiene pregunta y opciones; se responde relanzando con flags |
| **Keys** | ≤5 sinónimos de búsqueda en inglés, ausentes del titular |
| **Key marcadora** | Key de vocabulario controlado: antipattern, security, performance, legal |
| **Origin / Replaces** | Punteros: "de qué nazco" / "a qué reemplazo". Costuras del informe |
| **Racimo** | Grupo de notas unidas por punteros; su título es la nota viva más reciente |
| **close** | Comando de retirada sin reemplazo → ARCHIVED.md |
| **ARCHIVED.md** | Fichero cronológico único de todo lo retirado: fecha + titular + destino |
| **Índice** | Fichero de una línea por nota (ID + titular); solo lo escribe el script |
| **Informe** | Producto de toda búsqueda: estado completo de una zona, vigente por defecto |
| **Menú del día** | El boot: ⏩ Next+Context, todos los B y R, recuentos, avisos. El usuario decide el rumbo |
| **Context/Next** | Compactación de la conversación al cierre; titular = ⏩ Next |
| **Acta de plan** | Commit que enlaza D → issue del plan; única verificación GitHub de la aduana |
| **Adaptación** | Destilación única y aditiva de memoria v1 a formato nuevo (Gitto) |
| **rules / remembers** | Configuración de trabajo, fuera del sistema; se entrega entera con `/remember` |
| **zones.json** | Lista cerrada de zonas del proyecto; altas en dos pasos, a la vista |
| **Zombi** | Campo que se escribe y nadie lee; prohibido por P2 |
