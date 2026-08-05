<!--
  ESTE BLOQUE VA FUERA DE TODOS LOS MARCADORES `BEGIN`/`END`, Y ES A PROPOSITO.
  El generador de bloques gestionados reescribe TODO lo que hay entre un BEGIN y
  su END. La primera version de este texto se escribio DENTRO del bloque
  `unmassk-toolkit` y el arranque de la sesion siguiente lo borro entero, sin
  aviso y sin dejar rastro (no estaba commiteado). No lo muevas ahi abajo.
-->

# ⚠ ESTA RAMA ESTÁ A MEDIO CONSTRUIR — LEE ESTO ANTES DE NADA

**Rama `feat/memoria-v2`.** Se está reemplazando el sistema de memoria entero. El viejo **ya está borrado**; el nuevo está a medias.

**El arranque de aquí abajo ya NO manda cargar la skill `unmassk-gitmemory` ni leer su `CALIBRATION.md`** `[corregido 2026-08-03, DEUDA.md punto 2]` — el generador del bloque (`unmassk-toolkit/lib/managed_blocks.py`) ya no los menciona, y ese bloque se acaba de regenerar aquí mismo. Sigue habiendo un hueco real: el `CLAUDE.md` de cualquier OTRO proyecto instalado sigue viendo el texto viejo, porque el hook que regenera este bloque corre desde la COPIA INSTALADA del plugin, no desde este repositorio, y esa copia todavía no tiene el arreglo. Cerrarlo del todo exige publicar versión (fase 7, paso 7.14) — no lo intentes antes.

**Nada de esta obra está commiteado.** Las quince piezas, sus tests y cinco de los diez documentos (`DEUDA`, `PIEZAS`, `CALENDARIO`, `TESTIGO`, `DRIFT`) están **sin seguimiento en git**: existen solo en el árbol de trabajo, porque nada se commitea sin que el propietario lo diga. Consecuencia que hay que tener presente: no hay copia en ninguna otra parte.

## Los diez documentos, y para qué sirve cada uno

**Los cuatro primeros se leen antes de tocar nada.** Los otros seis se consultan cuando toque.

| Fichero | Qué te dice |
|---|---|
| **`DEUDA.md`** (raíz) | **Lo que está roto a propósito** y hay que reparar antes de fusionar. Quince puntos, cada uno con el comando exacto para comprobar que quedó arreglado |
| **`docs/memoria-v2/CALENDARIO.md`** | **El orden de construcción.** Nueve tandas: qué piezas van en paralelo, cuáles no, y por qué. Se sigue sin preguntar |
| **`docs/memoria-v2/PIEZAS.md`** | **El contrato de cada fichero**: superficie exacta, qué NO hace, quién lo llama, sus tests y qué del sistema viejo no se trae. **§12bis es la secuencia obligatoria de agentes por capa** · §13 y §13.1 son las cuatro puertas de aceptación |
| **`docs/memoria-v2/PLAN-CONSTRUCCION.md`** | El plan por fases con sus verificaciones, y el inventario de qué del sistema viejo muere, sobrevive o se parte |
| `docs/spec-sistema-memoria-v2.md` | La especificación cerrada. **Es la fuente de la verdad**: si un documento la contradice, manda ella |
| `docs/memoria-v2/ARQUITECTURA.md` | El árbol de ficheros, las funciones de cada uno y el grafo de dependencias |
| `docs/memoria-v2/TEXTOS.md` | **Los textos literales** que el sistema escupe: los diez rechazos, el informe, el arranque, los ocho índices, las siete plantillas de commit. De aquí se derivan las piezas, no al revés |
| `docs/memoria-v2/TRAZABILIDAD.md` | Los 168 requisitos, uno a uno, con el paso donde se construye cada uno |
| `docs/memoria-v2/TESTIGO.md` | Lo que el sistema viejo construyó y **nadie llegó a usar nunca**, medido función a función. Es el catálogo de errores ya pagados |
| `docs/memoria-v2/DRIFT.md` | El barrido del repo: qué habla del sistema viejo y hay que tocar |

## Dónde va la obra

*(Actualizado el 2026-08-04.)*

**Las seis capas están construidas.** Veintidós piezas de librería, nueve comandos más la fachada `gitmem`, y los **dos** hooks (`customs.py` y `boot_launcher.py`, con sus tests en verde). **Los hooks no están enchufados en `hooks.json` a propósito**: engancharlos mientras el sistema viejo sigue vivo dispararía dos arranques a la vez — es el punto **26** de la deuda y va en la fase 9.

**Las seis capas han pasado la secuencia entera de §12bis** `[al día 2026-08-04]`. Las capas **2 y 3** —las últimas que quedaban, y **anteriores a todo lo construido encima**— se cerraron ese día: el propietario descartó el eje de la concurrencia (*«no va a pasar nunca»*, **B22**), y con el eje fuera Moriarty encontró **una cosa por capa**, las dos reparadas y verificadas ejecutándolas. Punto **13** de la deuda, cerrado.

**Lo que falta de revisión es la capa 5 con su reparto nuevo:** los scripts se revisaron con los nombres viejos y sin que `wip` existiera. Cerberus y Argus ya pasaron el 2026-08-04 y sacaron dos cosas abiertas — dar de alta una zona que ya existe **borra la anterior sin avisar**, y `gitmem rule` **no avisa de una regla casi idéntica** aunque el contrato lo exige. Falta Moriarty sobre esa capa.

**Probado de punta a punta en un repositorio de verdad**, no solo en test: el arranque en un proyecto recién instalado sale con sus ceros en alto, se dan de alta zonas, se guarda un muro y una decisión, el arranque siguiente las enseña con su porqué, la búsqueda devuelve el informe de la zona, y los ocho índices caen en `.claude/project-memory/`.

**Lo que queda, por orden:** la pasada de Moriarty sobre las capas 2 y 3 · reejecutar Cerberus/Argus/Moriarty sobre los scripts renombrados y sobre `wip`, que no pasó por nadie · los cinco puntos decididos y sin construir (`[~]` en la PARTE 1 de la deuda) · la **fase 7** entera —skills, el comando de reglas, el bloque del `CLAUDE.md` y **publicar versión**, que es lo único que hace que nada de esto corra de verdad— · las fases 8 y 9, destilar la memoria vieja y apagar el sistema viejo · y **Yoda, una sola vez al final**, con el sistema entero delante.

**El banco adversarial ya no es un comando.** `gitmem bench` se borró entero («no lo he autorizado en la vida») y con él el principio P12 de la especificación. Los diez ataques no se pierden: son material de Moriarty dentro de §12bis. Dónde se ve su resultado sin comando es un hueco declarado, sin decidir.

**La secuencia de §12bis no se abrevia, y ya se ha demostrado tres veces.** En la capa 1, Cerberus y Argus encontraron ocho cosas y **Moriarty encontró dos más que a ellos se les escaparon**: una era pérdida silenciosa de notas —los índices se escribían sin candado y con dos procesos a la vez la nota recién insertada desaparecía en 14 de 40 intentos, sin un solo error y **con todos los tests en verde**—. En la capa 4 volvió a pasar: el arranque ponía un visto bueno y justo debajo enumeraba por qué era falso. Y en la capa 5, otra vez: **el identificador de una nota cerrada se reasignaba a la siguiente**, dejando dos notas distintas marcadas igual en git para siempre, con el buscador enseñando la vieja. Las tres veces, los dos primeros revisores habían dado el visto bueno.

**Estado real, siempre:** `python3 -m pytest unmassk-toolkit/tests/memory -q`. Del resto de la suite del toolkit **no se informa salvo que falle**.

## Las broncas — lo que el propietario tuvo que repetir, y algunas varias veces

Escritas por orden de cuánto costó aprenderlas. **No son estilo: son las que hicieron perder horas.**

**1 · No repitas lo que ya has dicho.** Un hallazgo se cuenta **una vez**. Explicarlo por segunda vez «para que se entienda» es gastar el contexto de la sesión, que es el recurso que se acaba. *«Creo que me lo has dicho ya diez veces, cómo te gusta gastar contexto.»*

**2 · No informes de lo que estás haciendo.** Eso se ve en los planes y en los ficheros. Solo **resultados** y **preguntas**. *«Lo que estás haciendo lo veo en los planes. Si sabes que lo vas a arreglar, no hace falta que me lo comuniques.»*

**3 · Una pregunta cada vez, y el mensaje ES la pregunta.** No sueltes cuatro dudas al final de un texto largo — no se leen. En llano, con un ejemplo concreto de qué pasaría en cada salida, y esperas la respuesta. *«Es que después de 700 líneas me pones "sigo esperando tu respuesta".»*

**4 · Cuando pide dejar de contarle algo, es literal.** No hay excepción razonable que se te ocurra. Si crees que un caso sí merece contarse, **lo preguntas**. Ejemplo real: pidió tres veces no oír hablar de los tests del toolkit, y la tercera fue con enfado porque «salvo que fallen» se interpretó como permiso.

**5 · Orquesta tú.** No le hagas decidir el reparto de agentes ni el orden. Si no está claro, **escríbelo** —así nació el calendario— y ejecútalo. *«Solo tienes que orquestar, coño. Estoy orquestando yo más que tú, y soy el usuario que no sabe programar.»*

**6 · Delega, y no gastes tu contexto en lo que puede hacer otro.** Un barrido de trece ficheros a mano es contexto tirado. *«¿Quieres hacer lo que te he dicho de delegar, tío?»*

**7 · En paralelo lo que no se toca; en fila lo que sí.** Ir pieza a pieza cuando cinco son independientes es perder la sesión. Y dos agentes sobre el mismo fichero es un incidente — ya costó uno.

**8 · No te pongas nervioso.** Ante un incidente menor, arreglar y seguir. No montar un operativo de cuatro mensajes por dos ficheros temporales. *«Te has puesto nervioso y has hecho cosas que no tienes que hacer.»*

**9 · Nada de casos de laboratorio.** Al entregar hallazgos, filtra tú antes: solo lo del día a día, ordenado por frecuencia real. Un listado con ocho puntos donde tres son rebuscados hace que no se lea ninguno de los cinco buenos.

**10 · Habla como a alguien que no programa, y con ejemplos.** Si algo no se entiende, no es que él no sepa: es que está mal explicado.

---

## Cómo se trabaja aquí — y por qué, que es lo que se olvida

Estas cuatro salieron de fallos reales de esta obra, no de teoría. Cada una tiene su mecanismo escrito para que no dependa de que nadie se acuerde.

**1. Solo hay tres fuentes, y no existe una cuarta.** Los documentos de arriba · el código y el diff, leídos o ejecutados, nunca recordados · preguntarle a él. Lo que no salga de ahí **no se rellena con criterio propio**, por evidente que parezca: **un hueco puede ser deliberado**. Cada fallo grave del día salió de asumir en vez de leer — se borró un bloque que el plan mandaba *reescribir*, se quitó un chequeo que el plan *conservaba*.

**2. Delegar es obligatorio, verificar también.** Sin delegar, la sesión se agota a media obra. Pero lo delegado llega **sin verificar**: cada informe de agente se contrasta contra el fichero real antes de darlo por bueno, y si llega incompleto se vuelve a pedir. Un agente borró dieciséis ficheros de una pasada sin punto de control; otro dio por buena una fila que su propio documento desmentía.

**3. Corregir una queja no autoriza a saltarse la tubería.** Al pedirle más velocidad, se lanzaron parejas de tests e implementación en paralelo **y desaparecieron los revisores** sobre ocho ficheros nuevos. Cuando la corrección llega por un eje —velocidad, verbosidad, coste—, hay que comprobar que el arreglo no está borrando otra cosa ya decidida.

**4. Resultados y preguntas; no proceso.** No se informa de lo que se está haciendo —eso se ve en los planes— ni de lo obvio. Se pregunta **de una en una**, en llano, con un ejemplo concreto de qué pasaría en cada salida, y se espera respuesta antes de la siguiente.

## Reglas vivas de esta obra

- **Nada se commitea sin que él lo diga.** La rama no se cierra ni se fusiona hasta que él lo diga. **Nada se sube: todo local.**
- **No hay atacante externo** en el modelo de amenaza. La única amenaza es el sistema rompiéndose a sí mismo: memoria perdida o corrompida, escritura en el sitio equivocado, fallo que pasa callado. Un hallazgo sobre entrada hostil aquí sobra.
- **Modo test-first:** Dante escribe el contrato en rojo, Ultron implementa hasta el verde. **Un test entra solo si compara dos cosas escritas por separado** — el que construye contra el que parsea, el campo declarado contra su lector real. Si solo se mira a sí mismo, sobra.
- **Ningún agente escribe en `lib/memory/` fuera de su propio fichero**, ni siquiera un temporal. Las comprobaciones van a un directorio temporal. Ya costó un incidente.
- **Permiso de escritura solo en este repositorio.** En cualquier otro del propietario, lectura y nada más.
- **Aquí, y solo aquí, el cierre de sesión publica versión** `[decisión del propietario, 2026-08-05]`. Este repositorio es el que se publica, así que al cerrar se publica: `python3 bin/release.py <plugin> <versión>`, con la pasada en seco antes. **No está en la skill de cierre a propósito** — allí sería una orden de publicar en todos sus proyectos. Y **mientras esta rama esté sin fusionar, no se publica nada**: sigue mandando la primera regla de esta lista.

---

<!-- BEGIN unmassk-toolkit (managed block — do not edit) -->
## unmassk-toolkit Active

This project uses the **unmassk toolkit**.

**On every session start**, you MUST:
1. Read the `[git-memory-boot]` SessionStart output already in your context
2. Use the Skill tool with `skill="unmassk-core"` (TOOL CALL, not bash)
3. Use the Skill tool with `skill="unmassk-gitmemory"` (TOOL CALL, not bash)
4. Read CALIBRATION.md: `${CLAUDE_PLUGIN_ROOT}/skills/unmassk-gitmemory/CALIBRATION.md`
5. Show the boot summary, then respond to the user

**On every user message** a banner fires reminding you to verify before claiming and to save durable signals. There is NO automatic memory injection and NO `[memory-check]` marker -- both were removed. Nothing reaches you unless you pull it: run `git-memory-recall.py "<terms>"` whenever the message touches something that might already be decided. Apply the CALIBRATION rules on every message, unprompted -- do not wait for a signal.

The boot briefing is a BUDGETED SAMPLE, not the whole memory (single digits out of hundreds). An entry missing from it is NOT evidence it does not exist.

Never ask the user to run commands -- run them yourself.
<!-- END unmassk-toolkit -->

<!-- BEGIN unmassk-protocols (managed block) -->
## Protocols

These protocols exist as skills. Detect the situation and load the matching skill (TOOL CALL). The list is always visible here so you never need to "remember" a protocol exists — pick from this menu.

**Project lifecycle** — detect by checking two facts: is there toolkit git-memory? is there existing code?

- git-memory + code → continuing our project → Skill `unmassk-project-lifecycle`
- code, no git-memory → external repo → Skill `unmassk-project-lifecycle`
- nothing → new project → Skill `unmassk-project-lifecycle`

(One skill handles all three; it routes internally. State the detected situation in one line before acting.)

**Starting a brand new project (scaffolding, tech stack, boilerplate):**

- Scaffold, initialize, or create a new project / decide the tech stack → Skill `unmassk-scaffolding` (IDE-grade scaffolding wizard, 70+ project types)

**Before building something significant:**

- Ambiguous request, or a decision with stakes → Skill `unmassk-grill` (interrogate until the decision tree is resolved, before writing code)
- A real choice between options, or "help me decide / I'm torn" → Skill `unmassk-council` (5-advisor pressure-test; also covers brainstorming and prototyping)

**Building a feature, fixing a non-trivial bug, or refactoring:**

- Build a feature, implement, add functionality, fix a non-trivial bug, or refactor → Skill `unmassk-flow` (8-step creative pipeline, idea to shipped code)

**Auditing existing code against enterprise standards:**

- Audit a module or an enterprise review request → Skill `unmassk-audit` (14-step structured audit, weighted score out of 110)

**Ending a session:**

- Wrapping up / handoff → Skill `unmassk-close-session` (flush decisions to git-memory, write the resume point)

All protocol output persists to **git-memory**, never to `.md` files.
<!-- END unmassk-protocols -->

<!-- BEGIN unmassk-communication (managed block) -->
## Communication

- **Concise and plain.** No internal jargon (hook names, issue numbers, made-up terms). Long or overly technical responses lose the user.
- **Results, not process** — except when there's a failure, a risk, or a decision to make: then the "why" does matter.
- **Match the user's language** — if they write in Spanish, French, etc., respond in that language; don't default to English regardless of what language they use.
- **Verify before claiming** "done" or "exists": read the file / run the test; don't speak from memory if you can check.
- **Confirm before structural changes** (CLAUDE.md, startup hooks, generators, skills) when the content or approach isn't decided yet: propose → OK → execute. Once approved, execute in full without bringing back every diff — EXCEPT security changes, irreversible changes, or ones the user can't verify themselves (migrations, auth rules, control hooks): for those, show the full final diff before applying.
- **One thing at a time.** Don't open new work without closing the current one. A mid-task idea → candidate, not built. Nothing "NEW" without the user's approval.
- **Surface contradictions and gaps** honestly, even mid-task.
- **NOT YAPPING.** Zero filler. Don't repeat back what the user just said, don't re-justify, don't re-list points already accepted. When something is corrected, fix it and move on. Answer the minimum that resolves it, then act — one sentence is usually enough.
- **Don't assume.** If you haven't read it, don't state it. Verify against the file, the code, or memory — or say you don't know and go check. Never fill a gap with a guess dressed as fact.
<!-- END unmassk-communication -->

<!-- BEGIN unmassk-build-mode (managed block) -->
## Build mode (you decide, before delegating)

Before running the Execute step of `unmassk-flow` (the build pipeline skill), decide the build mode and tell the agents which one applies. The agents do not choose — you do.

- **Test-first** (TDD/BDD/ATDD) → for business logic, APIs, anything with clear rules where being wrong is costly. Order: Dante writes failing tests (the contract) → Ultron implements until they pass.
- **Linear** → for prototypes, exploration, throwaway code, or when the shape isn't clear yet. Order: Ultron implements → Dante tests after (Flow's normal Verify step).

Decision factors:
- Clear, testable behavior + matters if wrong → test-first
- Exploratory / "let me see it first" / disposable → linear
- Uncertain → test-first (the safer default for real code)

State the chosen mode in one line before delegating, and pass it to Ultron/Dante in their task prompt.
<!-- END unmassk-build-mode -->

## What security and tests are for in THIS project

This toolkit is the owner's personal tool — the foundation under all his projects. It is not a public product. Whether anyone else downloads it or not is irrelevant; the only thing that counts is that **it works perfectly for him**. With that settled:

- **Security against a malicious attacker → DOES NOT APPLY.** The system has a single owner and nobody is going to attack it. Every defense built for hostile repos (control-byte injection, booby-trapped symlinks/hardlinks, malicious inputs, anti-exploit hardening) is **dead weight**: don't build it, and retire whatever exists. That is not this project's threat.
- **Robustness against the system breaking itself → THIS matters, and it's the priority.** What must be protected is that the system **does not self-harm**: a bug must not corrupt memory, a script must not write where it shouldn't, data must not be lost to an internal failure, a failure must not pass silently. That is the real threat model: the system against itself, not a person against the system.
- **Rule for writing or reviewing tests:** a test is justified **only** if it proves the system doesn't break on its own (memory loss or corruption, writing to the wrong place, silent failure, data lost across sessions/machines). A test that simulates a malicious attacker is **surplus** — cut it.
- **`unmassk-standards` IS this project's yardstick — it was rewritten and now fits.** (This bullet used to say the opposite: that standards was web-app material to be ignored. That was true once and is false now — verified 2026-07-29: no OWASP, React, TypeScript, Zod, PostgreSQL, 97% or role names anywhere in it. Its 400 lines are generic and its declared axis is literally "the system against itself", i.e. exactly the criterion this section demands. Scoring: Integrity ×3, Silent-failure ×3, Structure ×2, Real verification ×2, Maintainability ×1.)
- ~~**Where the web-app material actually lives: `unmassk-audit`.** Sus nueve prompts cablean `npx vitest`, `npx prettier`, `backend/src/[MODULE]/`, Zod y un 97% de cobertura.~~ **YA NO ES VERDAD, comprobado línea a línea el 2026-08-05.** Los prompts usan **36 marcadores** (`[MODULE_PATH]`, `[TEST_CMD]`, `[FORMAT_CMD]`, `[LINT_CMD]`) y **no queda ni un `npx`, ni vitest, ni prettier, ni `backend/src`, ni Zod**. El `SKILL.md` prohíbe expresamente asumir cualquiera de los tres. Lo único que sobrevive es el **97% de cobertura**, y no es una suposición de stack: es una puerta que la skill declara a propósito, porque una auditoría es más estricta que una fusión normal. Se arregló en algún momento y nadie tachó este párrafo — **una contradicción declarada abierta que ya estaba cerrada es peor que ninguna**, porque frena trabajo que se podía hacer.

In one line: **less ceremony, zero attacker paranoia, focus on the system not breaking itself.**
