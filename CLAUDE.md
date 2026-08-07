<!--
  ESTE BLOQUE VA FUERA DE TODOS LOS MARCADORES `BEGIN`/`END`, Y ES A PROPOSITO.
  El generador de bloques gestionados reescribe TODO lo que hay entre un BEGIN y
  su END. La primera version de este texto se escribio DENTRO del bloque
  `unmassk-toolkit` y el arranque de la sesion siguiente lo borro entero, sin
  aviso y sin dejar rastro (no estaba commiteado). No lo muevas ahi abajo.
-->

# claude-toolkit

**Esto es la herramienta personal del propietario: el suelo sobre el que corren todos sus proyectos.** No es un producto público. Que alguien más lo descargue da igual; lo único que cuenta es que a él le funcione perfectamente.

**El sistema de memoria está publicado, corriendo, y con la memoria vieja ya destilada.** La memoria de un proyecto son commits: nueve comandos bajo `gitmem`, notas con dos zonas, y un arranque y un cierre de sesión que la leen y la escriben. El sistema anterior está borrado del repositorio.

**Estado de la memoria de ESTE repositorio `[2026-08-07]`:** el historial entero —del primer commit al 6 de agosto— está destilado en **225 notas** repartidas en **24 zonas**, más **29 reglas** del propietario separadas en su propio canal. Lo que quedó abierto está abierto de verdad, y es una sola cosa: la issue #83.

**Las zonas van siempre en minúsculas**, en los tres puntos — al crear, al buscar y al guardar una nota. Su descripción y cualquier otro texto se guardan tal cual se escribieron.

**Cómo funciona la memoria hoy se lee en un solo sitio: `unmassk-toolkit/skills/unmassk-memory/`**, que es lo que se carga en cada sesión. No hay un segundo sitio.

**`/remember` es el único comando de barra del toolkit.** Solo lee: pone en contexto el fichero de reglas del proyecto (`.claude/project-memory/rules.md`) y a partir de ahí obligan. **Guardar una regla es trabajo de Claude**, en el momento en que el propietario la dice — nunca algo que él tenga que invocar.

**Lo que queda por hacer, y en este orden:**

1. **Compactar la memoria de cada agente.** Protocolo escrito, no ejecutado.
2. **Yoda, una sola vez**, con el sistema entero delante.

**Todo lo que sirvió para construirlo está retirado en `docs/deprecated/`** — la especificación, el plan, la deuda y los contratos de cada pieza. Cuenta por qué las cosas son como son y guarda las decisiones del propietario con su fecha, pero **no describe el presente y no se mantiene**. No lo leas para saber cómo funciona algo hoy: manda el código.

**Estado real, siempre:** `python3 -m pytest unmassk-toolkit/tests -q`. **Del resto de la suite no se informa salvo que falle.**

---

## Las broncas — lo que el propietario tuvo que repetir, y algunas varias veces

Escritas por orden de cuánto costó aprenderlas. **No son estilo: son las que hicieron perder horas.**

**Estas doce no son la lista completa.** Las reglas vivas están en el fichero de reglas del proyecto y hoy son 29 — se leen enteras con `/remember`, y crecen cada vez que él corrige algo. Estas doce siguen aquí porque son las caras, no porque sean las únicas.

**1 · No repitas lo que ya has dicho.** Un hallazgo se cuenta **una vez**. Explicarlo por segunda vez «para que se entienda» es gastar el contexto de la sesión, que es el recurso que se acaba. *«Creo que me lo has dicho ya diez veces, cómo te gusta gastar contexto.»*

**2 · No informes de lo que estás haciendo.** Eso se ve en los planes y en los ficheros. Solo **resultados** y **preguntas**. *«Lo que estás haciendo lo veo en los planes.»*

**3 · Una pregunta cada vez, y el mensaje ES la pregunta.** No sueltes cuatro dudas al final de un texto largo — no se leen. En llano, con un ejemplo concreto de qué pasaría en cada salida, y esperas la respuesta. *«Es que después de 700 líneas me pones "sigo esperando tu respuesta".»*

**4 · Cuando pide dejar de contarle algo, es literal.** No hay excepción razonable que se te ocurra. Si crees que un caso sí merece contarse, **lo preguntas**.

**5 · Orquesta tú.** No le hagas decidir el reparto de agentes ni el orden. Si no está claro, **escríbelo** y ejecútalo. *«Solo tienes que orquestar, coño.»*

**6 · Delega, y no gastes tu contexto en lo que puede hacer otro.** Un barrido de trece ficheros a mano es contexto tirado.

**7 · En paralelo lo que no se toca; en fila lo que sí.** Ir pieza a pieza cuando cinco son independientes es perder la sesión. Y dos agentes sobre el mismo fichero es un incidente — ya costó uno.

**8 · No te pongas nervioso.** Ante un incidente menor, arreglar y seguir. No montar un operativo de cuatro mensajes por dos ficheros temporales.

**9 · Nada de casos de laboratorio.** Al entregar hallazgos, filtra tú antes: solo lo del día a día, ordenado por frecuencia real. Un listado con ocho puntos donde tres son rebuscados hace que no se lea ninguno de los cinco buenos.

**10 · Habla como a alguien que no programa, y con ejemplos.** Si algo no se entiende, no es que él no sepa: es que está mal explicado.

**11 · Lo que él dice manda sobre cualquier documento**, incluidos los que se presentan como decisiones suyas — buena parte los escribieron IAs bajo su nombre sin preguntarle. Citar un documento vale para avisar de que existe una versión anterior, en una línea. No vale como argumento ni como freno.

**12 · Un documento desactualizado no frena trabajo ya hecho.** Si la deuda dice que algo está abierto y el código dice que está cerrado, manda el código: se corrige el documento y se sigue. Ya costó una sesión entera.

---

## Cómo se trabaja aquí — y por qué, que es lo que se olvida

Estas cinco salieron de fallos reales, no de teoría.

**1. Solo hay tres fuentes, y no existe una cuarta.** La documentación · el código y el diff, leídos o ejecutados, nunca recordados · preguntarle a él. Lo que no salga de ahí **no se rellena con criterio propio**, por evidente que parezca: **un hueco puede ser deliberado.**

**2. Delegar es obligatorio, verificar también.** Sin delegar, la sesión se agota a media obra. Pero lo delegado llega **sin verificar**: cada informe de agente se contrasta contra el fichero real antes de darlo por bueno. Un agente borró dieciséis ficheros de una pasada; otro dio por buena una fila que su propio documento desmentía.

**3. Corregir una queja no autoriza a saltarse la tubería.** Al pedir más velocidad, se lanzaron parejas de tests e implementación en paralelo **y desaparecieron los revisores** sobre ocho ficheros nuevos.

**4. Se prueba ejecutando, no leyendo.** Todos los fallos graves de esta obra salieron de correr comandos; ninguno de revisar código. Y **un arreglo se mide por el camino por el que entra el usuario, nunca por dentro**: un «0 de 60» medido llamando a la función por dentro salió «16 de 30» medido como lo usa una persona.

**5. La secuencia de revisión no se abrevia.** Cerberus y Argus en paralelo, y **Moriarty el último, siempre**. Cuatro veces ha encontrado algo que los dos primeros dieron por bueno — entre ellas, pérdida silenciosa de notas con todos los tests en verde, y un arranque que inyectaba el Next de otro proyecto.

**6. Una ficha de agente o una skill se repasa palabra por palabra, y se le consulta al propio agente.** No es ceremonia: el 2026-08-06 se revisaron las nueve y cada agente encontró en la suya algo que quien la escribió no vio. House rechazó **tres** versiones seguidas de un mismo comando escrito por el orquestador —el primero no casaba ni una línea de las que buscaba, el segundo ignoraba los ficheros sin guardar en git, el tercero se rompía en silencio desde una subcarpeta—. Y al darle a Moriarty permiso de escritura se le quitó sin querer la barrera que le impedía tocar código: la regla se sostenía en que no tenía la herramienta, no en estar escrita.

---

## Reglas vivas

- **Nada se commitea sin que él lo diga.** La memoria sí se guarda sola.
- **Nadie usa `git stash`, `reset`, `checkout` ni `restore`** sobre trabajo sin guardar: se perdería todo.
- **Permiso de escritura solo en este repositorio.** En cualquier otro del propietario, lectura y nada más.
- **No hay atacante externo** en el modelo de amenaza. La única amenaza es el sistema rompiéndose a sí mismo: memoria perdida o corrompida, escritura en el sitio equivocado, fallo que pasa callado. Un hallazgo sobre entrada hostil aquí sobra.
- **Modo test-first:** Dante escribe el contrato en rojo, Ultron implementa hasta el verde. **Un test entra solo si compara dos cosas escritas por separado.** Si solo se mira a sí mismo, sobra.
- **Ningún agente escribe en `lib/memory/` fuera de su propio fichero**, ni siquiera un temporal. Ya costó un incidente.
- **Nada llega solo a un agente.** No hay inyección automática de memoria ni de skills: un agente solo recibe lo que el orquestador le escribe en el prompt, más las skills que él le pegue en un bloque `[DOMAIN SKILL]`. Si una ficha promete recibir algo por su cuenta, esa ficha miente — pasó con Bilbo, que por creerlo nunca buscaba lo que le hacía falta.
- **Aquí, y solo aquí, el cierre de sesión publica versión** `[2026-08-05]`. Este repositorio es el que se publica: `python3 bin/release.py <plugin> <versión>`, con la pasada en seco antes. **No está en la skill de cierre a propósito** — allí sería una orden de publicar en todos sus proyectos.

---

<!-- BEGIN unmassk-toolkit (managed block — do not edit) -->
## unmassk-toolkit Active

This project uses the **unmassk toolkit**. Its memory lives in git, and it is
what you know about this project -- not a log you may consult.

**On every session start**, you MUST:
1. Read the session-start briefing already in your context: the last Next,
   every blocker, every restriction, the counts and the checks
2. Use the Skill tool with `skill="unmassk-core"` (TOOL CALL, not bash)
3. Use the Skill tool with `skill="unmassk-memory"` (TOOL CALL, not bash)
4. Tell the user the menu of the day, then respond

**Four rules that hold even when no skill is loaded:**
- Memory is a commit. Never write it into a file.
- The indexes and the zone list are written by the commands. Never by hand.
- A restriction is retired by asking the user, never on your own judgement.
- Never ask the user to run a command -- you run it.
<!-- END unmassk-toolkit -->

<!-- BEGIN unmassk-protocols (managed block) -->
## Protocols

These protocols exist as skills. Detect the situation and load the matching skill (TOOL CALL). The list is always visible here so you never need to "remember" a protocol exists — pick from this menu.

**Project lifecycle** — detect by checking two facts: does this project have memory? is there existing code?

- memory + code → continuing our project → Skill `unmassk-project-lifecycle`
- code, no memory → external repo → Skill `unmassk-project-lifecycle`
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

- Wrapping up / handoff → Skill `unmassk-close-session` (write the Next, update the plan, prune walls, register blockers)

All protocol output persists to **memory**, never to `.md` files.
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
- **`unmassk-audit` también está limpia** — comprobado línea a línea el 2026-08-05. Sus prompts usan 36 marcadores (`[MODULE_PATH]`, `[TEST_CMD]`, `[FORMAT_CMD]`, `[LINT_CMD]`) y no queda ni un `npx`, ni vitest, ni prettier, ni `backend/src`, ni Zod. Lo único fijo es el 97% de cobertura, y eso no es una suposición de stack: es una puerta que la skill declara a propósito, porque una auditoría es más estricta que una fusión normal.
- **Las fichas de los nueve agentes son agnósticas** y viajan a todos los proyectos del propietario. **Nunca se juzgan contra el proyecto en el que estás:** que aquí no haya atacante externo no dice nada sobre si el material de OWASP de Argus debe existir — lo pone el proyecto anfitrión. Ese error costó una ronda entera de revisiones el 2026-08-06.

In one line: **less ceremony, zero attacker paranoia, focus on the system not breaking itself.**
