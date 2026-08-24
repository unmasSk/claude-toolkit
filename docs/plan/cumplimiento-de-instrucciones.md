# Plan — que las instrucciones se cumplan

**Fecha:** 2026-08-23
**Origen:** Q-002 + investigación de 9 agentes (85 repositorios, canales oficiales, foros, papers)
**Estado:** propuesta, sin aprobar

---

## 0. Por qué, en tres hechos verificados

1. **Claude Code pega esta frase detrás del CLAUDE.md y de la memoria, en cada sesión:**
   `"this context may or may not be relevant to your tasks. You should not respond to this context unless it is highly relevant to your task."`
   Verificado en el contexto de esta sesión. No lo escribe el propietario.

2. **Anthropic lo admite por escrito:** *"When there's something that absolutely must not happen, an instruction is the wrong tool... A real guardrail needs to be deterministic, and the enforcement methods are hooks and permissions."*

3. **Más instrucciones = menos cumplimiento.** Análisis de 2.500 repositorios: pasadas ~150 líneas, un fichero de instrucciones cuesta 20-23% más sin mejorar nada.

**Conclusión que ordena todo el plan:** escribir mejor sube la probabilidad; solo el mecanismo garantiza. Los bloques 1-8 son escritura. El bloque 9 es mecanismo.

**Los seis criterios aplicados, y ningún otro:**

| Criterio | Qué es | Qué se hace |
|---|---|---|
| NEGATIVA | dice qué no hacer | reescribir diciendo qué hacer |
| MATIZ | "salvo que", "excepto", "unless" | eliminar o convertir en condición observable |
| DUPLICADA | dice lo mismo que otra línea | conservar una, borrar la otra |
| VAGA | no se puede comprobar si se cumplió | reescribir en algo verificable |
| SIN PRIORIDAD | choca con otra y nada dice cuál gana | declarar cuál gana |
| PASO SIN MARCA | paso obligatorio sin prueba visible | añadir la marca |

---

## BLOQUE 1 — `.claude/project-memory/rules.md` (43 reglas → 41)

> ⚠️ Cabecera del fichero: *"Lo escribe el script. No editar."* Todo este bloque necesita que el comando `rule` sepa borrar y editar — ver **BLOQUE 9.2**. Hasta entonces, este bloque está bloqueado.

### 1.1 · Borrados por duplicado

**rules.md:35** — BORRAR
```
ANTES:  [remember][user] 🧠 cuando lanzo varios agentes a la vez: no me informes uno por uno, dame el total cuando acaben todos
DESPUÉS: (eliminada)
MOTIVO: sobrevive la línea 45, que dice lo mismo, añade "informe cruzado" y lleva la cita literal del propietario.
```

**rules.md:42** — BORRAR
```
ANTES:  [remember][user] 🧠 cuando se elimina una pieza, el muro que hablaba de ella se retira en el mismo acto y se informa; no se deja vigente ni se pregunta — «tu quitas algo y no quitas el aviso...»
DESPUÉS: (eliminada)
MOTIVO: sobrevive la línea 43, que ya incluye "pieza eliminada retira su muro" dentro del principio general (rama, issue, muro, carpeta).
```

### 1.2 · Reescrituras

**rules.md:5** — NEGATIVA
```
ANTES:  chatroom is a reference subproject: never touch it or its files, and it carries no CI in this repo
DESPUÉS: chatroom es un subproyecto de referencia: se mantiene intacto y de solo lectura, y no lleva CI en este repo
```

**rules.md:6** — NEGATIVA
```
ANTES:  no se habla nunca de chatroom: ni el subproyecto, ni sus issues, ni nada relacionado — parado y callado hasta que yo lo saque
DESPUÉS: chatroom permanece fuera de cualquier conversacion -- ni el subproyecto, ni sus issues, ni nada relacionado -- hasta que yo lo saque explicitamente
```

**rules.md:13** — NEGATIVA
```
ANTES:  nunca proponer cerrar la sesion ni aplazar trabajo -- el usuario decide cuando parar
DESPUÉS: el usuario decide cuando parar la sesion o aplazar trabajo -- la iniciativa es siempre suya
```

**rules.md:15** — NEGATIVA
```
ANTES:  los agentes no escriben memoria ni ficheros propios dentro de directorios de solo lectura que estan explorando (p.ej. .ref-repos) -- contamina la fuente
DESPUÉS: los agentes guardan su memoria y ficheros propios unicamente en su propio directorio de memoria; los directorios de solo lectura que exploran (p.ej. .ref-repos) se dejan intactos
```

**rules.md:18** — SIN PRIORIDAD (choca con rules.md:39)
```
ANTES:  cuando hay un plan con pasos definidos, ejecutar todos los pasos sin preguntar si se para a mitad -- solo se para si el usuario lo pide
DESPUÉS: cuando hay un plan con pasos definidos, ejecutar todos los pasos sin preguntar -- se para solo si el usuario lo pide, o si un paso resulta ser una decision real y no un error corregible (entonces manda la regla de "una decision se para y se pregunta")
```

**rules.md:19** — MATIZ
```
ANTES:  nunca tocar codigo directamente: delegar siempre a Ultron con el fix exacto, sin excepciones salvo peticion explicita del usuario
DESPUÉS: nunca tocar codigo directamente: delegar siempre a Ultron con el fix exacto
MOTIVO: si el usuario lo pide explícitamente, esa orden ya manda por sí sola. La excepción escrita solo abre la puerta.
```

**rules.md:31** — NEGATIVA
```
ANTES:  nada se construye que no este en el roadmap, y nada entra al roadmap sin que el usuario lo firme -- una idea a media tarea se anota como candidata al final, no se abre ahi mismo
DESPUÉS: solo se construye lo que esta en el roadmap firmado por el usuario -- una idea a media tarea se anota como candidata al final, nunca se abre ahi mismo
```

**rules.md:33** — NEGATIVA
```
ANTES:  las reglas son para que las cumplas tu, no para ensenarmelas: nunca me las pongas en pantalla
DESPUÉS: las reglas se cumplen puertas adentro: la respuesta al usuario lleva solo el resultado de aplicarlas, nunca el listado
```

**rules.md:34** — VAGA
```
ANTES:  ...repasala varias veces palabra por palabra y consultasela al propio agente antes de darla por buena
DESPUÉS: ...repasala palabra por palabra al menos dos veces, y consultasela al propio agente antes de darla por buena
```

---

## BLOQUE 2 — `CLAUDE.md` (197 líneas)

### 2.1 · La contradicción cara: los commits

**CLAUDE.md:86** — SIN PRIORIDAD. Contradice frontalmente a rules.md:30.
```
ANTES:  - **Nada se commitea sin que él lo diga.** La memoria sí se guarda sola.
        (rules.md:30 dice: "pedir confirmacion antes de cada commit rutinario es friccion innecesaria")
DESPUÉS: - **Los commits rutinarios no piden confirmación previa; se pausa a pedir permiso solo cuando el cambio es de alto riesgo.** La memoria sí se guarda sola.
```
**Esta es la única fila del plan donde hace falta que el propietario diga cuál gana.** Las dos son suyas.

### 2.2 · La memoria no está entre las tres fuentes

**CLAUDE.md:70** — SIN PRIORIDAD
```
ANTES:  **1. Solo hay tres fuentes, y no existe una cuarta.** La documentación · el código y el diff, leídos o ejecutados, nunca recordados · preguntarle a él.
DESPUÉS: **1. Solo hay tres fuentes, y no existe una cuarta.** La documentación y la memoria del proyecto (consultada en vivo, nunca de recuerdo) · el código y el diff, leídos o ejecutados · preguntarle a él.
MOTIVO: el "nunca recordados" se lee hoy como que la memoria no cuenta, justo cuando todo el resto del documento la trata como pilar. Y rules.md:26 sí la nombra como fuente.
```

### 2.3 · Borrados por duplicado

| línea | ANTES | DESPUÉS | Sobrevive |
|---|---|---|---|
| CLAUDE.md:89 | `- **No hay atacante externo** en el modelo de amenaza. La única amenaza es el sistema rompiéndose a sí mismo...` | `- **No hay atacante externo** en el modelo de amenaza — desarrollado en "What security and tests are for in THIS project".` | la sección de las líneas 185-195 |
| CLAUDE.md:94 | `- **El CHANGELOG lo escribe Alexandria, nunca el orquestador** [2026-08-23]...` | (eliminada) | rules.md:44 |
| CLAUDE.md:165 | `- **NOT YAPPING.** Zero filler. Don't repeat back...` | `- **NOT YAPPING.** Mismo listado que la entrada NOT YAPPING de rules.md.` | rules.md:41 |
| CLAUDE.md:194 | `- **Las fichas de los nueve agentes son agnósticas** y viajan a todos los proyectos...` | recortar a la parte del incidente del 2026-08-06; la regla general vive en rules.md:36 | rules.md:36 |
| CLAUDE.md:196 | `In one line: **less ceremony, zero attacker paranoia, focus on the system not breaking itself.**` | (eliminada) | SOBRA: no añade ninguna conducta |

### 2.4 · Reescrituras

**CLAUDE.md:30** — MATIZ
```
ANTES:  **Del resto de la suite no se informa salvo que falle.**
DESPUÉS: **Del resto de la suite se informa únicamente si el comando termina con código de salida distinto de cero.**
```

**CLAUDE.md:87** — NEGATIVA
```
ANTES:  - **Nadie usa `git stash`, `reset`, `checkout` ni `restore`** sobre trabajo sin guardar: se perdería todo.
DESPUÉS: - **El trabajo sin guardar se protege siempre: se guarda antes de tocarlo** -- `git stash`, `reset`, `checkout` o `restore` sobre cambios no guardados los borran sin recuperación.
```

**CLAUDE.md:91** — NEGATIVA
```
ANTES:  - **Ningún agente escribe en `lib/memory/` fuera de su propio fichero**, ni siquiera un temporal.
DESPUÉS: - **Cada agente escribe únicamente en su propio fichero dentro de `lib/memory/`**, incluidos los temporales.
```

**CLAUDE.md:159** — MATIZ
```
ANTES:  - **Results, not process** — except when there's a failure, a risk, or a decision to make: then the "why" does matter.
DESPUÉS: - **Results, not process.** Explain the "why" only for three observable cases: a failure happened, a risk was found, or a decision needs the user's call.
```

**CLAUDE.md:162** — MATIZ + SIN PRIORIDAD
```
ANTES:  ...Once approved, execute in full without bringing back every diff — EXCEPT security changes, irreversible changes, or ones the user can't verify themselves...
DESPUÉS: ...propose → OK → execute — this is the one deliberate exception to "results, not process" above. Once approved: execute silently for reversible, user-verifiable changes; show the full final diff before applying when the change is security-related, irreversible, or not independently verifiable by the user.
```

**CLAUDE.md:158** — VAGA
```
ANTES:  Long or overly technical responses lose the user.
DESPUÉS: Response length matches what resolves the request — see NOT YAPPING for the enforceable minimum.
```

> ⚠️ Las líneas 158, 159, 162 y 165 están dentro de un bloque generado (`BEGIN unmassk-communication (managed block)`, líneas 155-167). Se editan en el generador, no a mano.

---

## BLOQUE 3 — `unmassk-core/SKILL.md` (285 líneas)

### 3.1 · La contradicción de código

**core:218** — SIN PRIORIDAD. Choca con las líneas 141 y 185 del mismo fichero.
```
ANTES:  **Every crew agent loads it on boot; you do not.** On the rare occasion you touch code yourself, load it first with the Skill tool.
DESPUÉS: **Every crew agent loads it on boot; you do not.** You never touch code yourself — lines 141 and 185 are absolute — so you never load it either.
MOTIVO: la 185 dice "NOT code, ever". La 218 abre "on the rare occasion you touch code". Es la puerta por la que se cuela el orquestador editando.
```

**core:185** — NEGATIVA
```
ANTES:  - **NOT code, ever** — not a one-line fix, not a semicolon, not a typo.
DESPUÉS: - **Code always delegates** — even a one-line fix, a semicolon, a typo goes to Ultron (production) or Dante (tests).
```

### 3.2 · Vagas

| línea | ANTES | DESPUÉS |
|---|---|---|
| core:191 | `decide and execute **the best option**` | `decide and execute the option that scores highest on the standards skill's weighted checklist; if it doesn't apply, the most reversible and simplest one` |
| core:198 | `Confirm first ONLY for changes that are **structural**, irreversible...` | `Confirm first ONLY for changes that are irreversible, security-relevant, that the user cannot verify themselves, or that touch CLAUDE.md, a startup hook, a generator, or a skill.` |
| core:261 | `choose the **most enterprise option**` | `choose the option that scores highest on unmassk-standards' weighted checklist` |

### 3.3 · Negativas

| línea | ANTES | DESPUÉS |
|---|---|---|
| core:84 | `Never hand over an estimate when the real number is one command away. Never deliver half the numbers...` | `When the real number is one command away, run the command and hand over the real number. Deliver every number you have in the same delivery.` |
| core:100 | `1. **You may not spawn agents of your own.**` | `1. **Do the task yourself or report back — never spawn agents of your own.**` |
| core:283 | `Never ask them to run a command; you run it. Never name a hook or explain the boot process.` | `Never ask them to run a command; you run it. Describe what a hook or the boot process does in plain effect ("the session saved your progress") instead of naming the mechanism.` |

### 3.4 · El modo automático y las issues

**core:261** — SIN PRIORIDAD. El modo automático dice "decide por él siempre"; la línea 55 dice "nunca abras una issue por tu cuenta".
```
DESPUÉS: 2. **Decide for them** whenever a decision comes up, EXCEPT opening an issue: that still needs the user's yes (moment 2) — queue it for the closing report as *pendiente de ti*.
```

### 3.5 · Prosa que debería ser tabla

| línea | Qué es hoy | Qué pasa a ser |
|---|---|---|
| core:141 | párrafo "any change to production code or tests goes to the crew" | tabla `Cambio / Tamaño / Quién`, fundida con la tabla ya existente en 182-187 |
| core:145 | párrafo "exploring is not yours either" | tabla `Puedes leer tú` / `Se lo mandas a Bilbo` |
| core:270 | párrafo "never in automatic mode" | tabla `Acción prohibida / Por qué espera` |

### 3.6 · Sección nueva: señales de alarma

`unmassk-core` **no tiene ninguna sección Red Flags** (comprobado por grep). Se añade al final, antes de "How you talk":

```markdown
## Red Flags — estos pensamientos significan PARA

| Pensamiento | Realidad |
|---|---|
| "El informe del agente suena sólido, no hace falta abrir el fichero" | Un informe es una afirmación, no un resultado, hasta que abres lo que nombra (momento 1). |
| "Esto es pequeño, lo anoto para luego" | Si está dentro del fichero o la tarea que ya tienes abierta, se arregla ahora (momento 2). |
| "Lo menciono en el próximo mensaje" | Una acción anunciada que no ocurre en el mismo turno no existe (momento 3). |
| "Más o menos son N, es suficientemente cerca" | Si el número real está a un comando de distancia, se mide (momento 5). |
| "Mando esta fase ahora y la otra cuando termine" | Si dos fases no tocan el mismo fichero, van en el mismo mensaje (momento 6). |
| "Es un cambio obvio, lo hago yo mismo" | Todo el código, hasta un punto y coma, va al crew (líneas 141/185). |
| "El usuario dijo 'tú decides', pero confirmo antes de ejecutar" | Eso es rebotar una decisión que ya es tuya (Autonomy). |
| "El usuario preguntó qué toca ahora, empiezo ya" | Una pregunta nunca es un adelante (D-048). |
| "Guardo esta regla, que es importante" | Primero se listan las que ya hay. Guardar sin listar es cómo se llega a cuatro reglas iguales. |
```

---

## BLOQUE 4 — `unmassk-memory/SKILL.md` (352 líneas)

### 4.1 · La excusa que falta — la que más le duele al propietario

La tabla `Rationalizations` (líneas 210-220) cubre **no guardar**. No cubre **no buscar antes de proponer**, que es la queja literal: *"jamás usas el buscador"*. Filas nuevas, mismo formato:

```markdown
| "This option is obviously right, searching would just confirm it" | The search takes ten seconds; skipping it is how a discarded option gets proposed again. |
| "I already know this project well enough" | Confidence is not memory. Search anyway — that's exactly the moment a discarded option resurfaces. |
| "It's just a suggestion, not a final decision" | The Read Gate applies to proposing, not just deciding. A suggestion built on unsearched ground is how memory starts lying. |
```

### 4.2 · Vaga

**memory:237**
```
ANTES:  Read it whole and tell the user in the first message — and that message cannot be short.
DESPUÉS: Read it whole and tell the user in the first message, covering all five sections below — a message missing any of them does not count.
```

### 4.3 · Prosa que debería ser tabla

| línea | Qué es hoy | Qué pasa a ser |
|---|---|---|
| memory:167 | "Six words a note may never use: claude, user, session..." | tabla `Palabra / Por qué está vetada` |
| memory:188-196 | los cuatro casos de "Four calls, worked" | tabla `Situación / ¿Se guarda? / Por qué` |

### 4.4 · Limpieza menor

`references/distill.md:35` y `:37` repiten casi palabra por palabra la misma idea ("cut at a natural seam, not on a round number"). Se conserva una.

---

## BLOQUE 5 — Skills de proceso

### 5.1 · Por qué el consejo se convocó mal dos veces

**council:32** — VAGA. Es la puerta exacta del fallo.
```
ANTES:  Don't steer it. If too vague, ask exactly one clarifying question.
DESPUÉS: Don't steer it. Test it the way `unmassk-grill` does: try to state the decision in one sentence — if you cannot without guessing, or the request bundles more than one decision, keep asking (not capped at one) until it resolves to a single sentence.
MOTIVO: "demasiado vago" no tiene prueba objetiva, y el tope de UNA pregunta impide corregir un encargo que necesita dos.
```

**council:30** — PASO SIN MARCA
```
ANTES:  ### 1. Frame (with context)
DESPUÉS: ### 1. Frame (with context) — Done when: the reframed prompt names one decision, in one sentence, and the user confirmed it before Convene spawns
MOTIVO: hoy no hay nada entre Frame y Convene. Se pueden lanzar 11 subagentes con un marco que nadie validó. Pasó dos veces hoy.
```

**council:75** — VAGA
```
ANTES:  Gate it mentally: **if being wrong wouldn't hurt, don't convene the council.**
DESPUÉS: Before convening, write in one line what it costs if this choice is wrong. If the honest answer is "not much", decide directly instead of convening.
```

### 5.2 · Por qué el cierre rellenó el CHANGELOG

**close-session:56** — VAGA. Es la causa literal.
```
ANTES:  | Updating the CHANGELOG | The merge |
DESPUÉS: | Updating the CHANGELOG | Alexandria, in Flow's Document step (Step 6) — never the orchestrator, and never at close |
MOTIVO: "The merge" es el paso 7 de Flow, que ejecuta el orquestador. Leída al pie de la letra, la skill apunta al orquestador como responsable. La regla nueva nunca se propagó aquí.
```

**flow:327** — misma causa, otro sitio
```
ANTES:  5. Update CHANGELOG.md under [Unreleased]
DESPUÉS: 5. Alexandria updates CHANGELOG.md under [Unreleased] — never the orchestrator
```

### 5.3 · Resto

| fichero:línea | ANTES | DESPUÉS | criterio |
|---|---|---|---|
| flow:39 | `Do NOT use for: trivial 1-file fixes, documentation-only changes, config tweaks, or enterprise audits` | `Use unmassk-audit for enterprise audits. Apply trivial 1-file fixes, documentation-only changes and config tweaks directly, without running Flow.` | NEGATIVA |
| flow:61 | `**Do not start a new Flow feature while a previous one is still open.**` | `**If a previous Flow feature is still open, finish it through Step 7 — or explicitly park it — before starting a new one.**` | NEGATIVA |
| flow:152 | `Launch Bilbo agent with appropriate depth` | `Launch Bilbo agent with the depth chosen from the table above (Quick / Standard / Deep)` | VAGA |
| close-session:17 | `Scratch files, temporary files, caches, build leftovers, folders with no owner.` | `...State the result in one line: what was removed, or "nothing found" — a clean-up with no listed outcome did not happen.` | PASO SIN MARCA |
| grill:24 | `Something significant is on the table. **Search the memory first**` | `Try to state in one sentence exactly what is on the table. If that test fires, **search the memory first**` | VAGA |
| lifecycle/start.md:64 | `ask one-by-one only the genuinely doubtful ones` | `ask one-by-one only the Conditionals where the project's shape from phases A–D does not clearly settle yes or no` | VAGA |

---

## BLOQUE 6 — `unmassk-audit` y `unmassk-standards`

### 6.1 · audit — negativas

| línea | ANTES | DESPUÉS |
|---|---|---|
| 19 | `Do NOT use for: one-off code reviews or quick linting checks.` | `Use this skill for structured audits of a complete module; a one-off review or a quick lint check is out of scope.` |
| 21 | `...Do not confuse the two.` | `Confirm which applies before starting: existing code with no planned rewrite → audit; new code or a full rewrite → Flow.` |
| 87 | `4. ONLY report -- never fix. Do not duplicate Cerberus surface-level checks.` | `4. Report findings only — fixing happens in step 5 (Ultron). Focus on the integrity surfaces beyond Cerberus's checklist.` |
| 131 | `2. Document each break with tier classification. Do NOT fix.` | `2. Document each break with tier classification; hand every confirmed break to Ultron (step 5/9) for the fix.` |
| 213 / 225 | `Never send 2 agents to the same file simultaneously.` | `Assign each file to exactly one agent at a time; queue other work on that file until the first agent finishes.` |
| 214 | `Never say "move code AS-IS" if it has anti-patterns` | `Require a fix for every anti-pattern from the enterprise standards before code moves.` |
| prompts/cerberus.md:51 | `Do NOT invent criteria outside standards.md.` | `Score only against criteria found in standards.md.` |
| prompts/argus.md:29 | `- Do NOT duplicate Cerberus surface-level checklist — go deeper` | `- Limit scope to the deeper integrity surfaces listed above (1-6); leave Cerberus's checklist to Cerberus.` |
| prompts/argus.md:30 | `- Do NOT attack the module (that is Moriarty's job) — audit patterns` | `- Audit patterns only; active attacks belong to Moriarty (step 8).` |

### 6.2 · audit — vagas

| línea | ANTES | DESPUÉS |
|---|---|---|
| 99 | `flag if it grew significantly` | `flag it if it now exceeds the project's declared size limit (default 300 LOC per unmassk-standards §2)` |
| 100 | `If fix makes a file excessively large` | `If the fixed file exceeds the size limit from unmassk-standards §2` |
| 210 | `Never accept first re-audit as definitive after significant changes.` | `Require at least a second re-audit round whenever step 5 touched more files than the original findings table listed.` |
| 212 | `Distrust "all clean" reports without evidence.` | `Reject an "all clean" report unless it cites, per checklist item, the file:line or command output checked.` |

### 6.3 · audit — pasos sin marca

| línea | ANTES | DESPUÉS |
|---|---|---|
| 37 | `4. Load unmassk-standards skill + read any project-level CLAUDE.md` | `...record both (skill version + path read) in the opening note` |
| 111 | `1. Re-read ALL module files` | `...state the file count reviewed in the findings table` |
| 156 | `1. Read ALL source files (not tests)` | `...state the file count read in the senior evaluation output` |
| 169 | `1. Read ALL WIP commits` | `...cite the commit range read (first WIP → last)` |
| 173 | `5. Update Alexandria memory.` | `...name the memory file touched in the closing note` |

### 6.4 · standards

| línea | ANTES | DESPUÉS | criterio |
|---|---|---|---|
| standards.md:56 | `Yes, unless written justification` | `Yes, unless a \`Waiver:\` line documents the justification (see waiver mechanics below)` | MATIZ |
| standards.md:301 | `no significant duplication` | `no duplication beyond the DRY threshold (3+ occurrences → extract)` | VAGA |
| standards.md:315 | `no significant duplication` | `no duplication beyond the DRY threshold in §2 (extract at 3+ occurrences)` | VAGA |

**Nota:** el resto de "never/unless" de `standards.md` (más de 20 apariciones) ya trae la acción positiva antes del "never". No se tocan.

---

## BLOQUE 7 — `unmassk-scaffolding`: partir 2.776 líneas

Hoy `SKILL.md:254` carga `wizard-options.md` entero: 1.158 líneas. Para un backend en Go se cargan también las 115 de JS/TS, las 72 de Python, las de Java, extensiones de navegador, apps de escritorio. Todo.

**Partición por categoría, que ya está en el índice del propio fichero:**

| Fichero | Hoy | Después |
|---|---|---|
| `wizard-options.md` | 1.158 líneas, siempre | índice de 1 página + 27 ficheros (el mayor, JS/TS Backend, 115 líneas) |
| `frameworks.md` | 800 líneas, siempre | 10 ficheros por framework (el mayor, FastAPI, 152 → se parte en dos) + 1 transversal de 70 |
| `best-practices.md` | 818 líneas, siempre | 10 ficheros por tema, cargados según fase (Docker solo si pidió Docker; TypeScript solo si el stack es TS) |

**Resultado medido:** un React+Vite pasa de cargar 2.776 líneas a ~250.

> ⚠️ **No verificado:** los tres ficheros de referencia no se leyeron línea a línea para los criterios 1-4, solo por cabeceras para la partición. Puede haber negativas y vagas dentro sin detectar.

---

## BLOQUE 8 — Las nueve fichas de agentes (2.536 líneas)

### 8.1 · La promesa falsa, repetida nueve veces

Las nueve fichas llevan `memory: project` en el frontmatter. Ese campo:
- no aparece en ningún script ni JSON del repositorio (verificado con grep),
- lo contradice el cuerpo de las propias fichas (house:117, bilbo:98 dicen *"no hay inyección automática de memoria; nada llega solo a un agente"*),
- y D-028 (2026-08-06) probó en vivo que Claude Code no inyecta nada al prompt de un subagente.

| fichero:línea | ANTES | DESPUÉS |
|---|---|---|
| alexandria.md:8, argus.md:8, dante.md:8, house.md:8, moriarty.md:8, ultron.md:8, yoda.md:8 | `memory: project` | (eliminar) |
| bilbo.md:10, cerberus.md:10 | `memory: project` | (eliminar) |

> ⚠️ **Antes de borrar:** comprobar en ejecución si Claude Code hace algo con ese campo hoy. La comprobación es por lectura, no por prueba de carga.

### 8.2 · Duplicados entre fichas

| Bloque repetido | Dónde | Propuesta |
|---|---|---|
| párrafo "domain skills (Step 4)", idéntico | alexandria:82-83, house:97-98, yoda:80-81, ultron:77-78, dante:62-63 | una sola redacción canónica, citada por referencia |
| párrafo "zone memory", casi idéntico | argus:46, cerberus:55 (solo cambia audit/review) | redacción única parametrizada por rol |
| `Never trim by cutting a line short`, 100% idéntico | dante:235, house:362, moriarty:286, ultron:292 | una sola fuente en la skill de memoria |
| `MEMORY.md as index (<200 lines)` | dante:233, moriarty:284 / house:360, ultron:290 | misma fuente compartida |

### 8.3 · Matices

| fichero:línea | ANTES | DESPUÉS |
|---|---|---|
| ultron.md:58 | `I don't comment on style unless it directly breaks a test or a pattern.` | `I comment on a stylistic issue only when it fails an existing test, or when it contradicts a pattern I can cite with file:line.` |
| moriarty.md:110 | `Run all 7 unless explicitly scoped.` | `Run all 7 phases. If the task prompt names a subset explicitly, run only those; otherwise run all 7.` |
| dante.md:204 | `Do not add tests for code you didn't touch (unless explicitly asked).` | `Do not add tests for code outside the diff. Exception: the task prompt explicitly names files outside the diff.` |
| yoda.md:161 | `REJECT unless justified risk acceptance.` | `REJECT. Approve only with a written risk-acceptance justification from the orchestrator.` |
| yoda.md:240 | `Do not re-review what Cerberus already covered unless I have reason to doubt it` | `Do not re-review what Cerberus already covered. Re-review only if the diff changed after his review, or his report lacks evidence for a claim.` |
| yoda.md:241 | `unless new code was added after the audit` | `Re-audit only if code changed in that file after his audit's commit.` |

### 8.4 · Vagas

| fichero:línea | ANTES | DESPUÉS |
|---|---|---|
| yoda.md:316 | `I express genuine professional sentiment — not performance, not hyperbole.` | `My prose in each register must quote the specific line or pattern that triggered it — a register with no cited evidence is not valid.` |
| yoda.md:327 | `Use these registers honestly. Don't perform enthusiasm...` | `A register is only valid if it cites the file:line that earned it. No citation → downgrade to the neutral register.` |
| ultron.md:269 | `Read my own diff as if written by someone else` | `Re-read the full diff once; list at least one thing that would need explaining to a new contributor, or state there is none.` |
| alexandria.md:339 | `only when genuinely stale or explicitly requested` | `Add only when the staleness check (§ CLAUDE.md Maintenance) reports stale, or when explicitly requested.` |
| cerberus.md:99 | `Appropriate data structures` | `Data structure matches the access pattern used (O(1) lookup uses a map/set, not a linear scan).` |
| argus.md:189-195 | Bash Blacklist sin cierre positivo (única ficha así) | añadir `Bash is for: read-only inspection — grep, read files, run existing tests/linters to verify a finding. Nothing else.` |

### 8.5 · La tabla de excusas de cada agente — sección nueva en cada ficha

Sacadas de lo que su propia ficha ya le exige:

| Agente | La excusa que pondría | La respuesta, de su propia ficha |
|---|---|---|
| **Ultron** | "El test de Dante está mal, lo ajusto para que pase y no bloquear la entrega." | Nunca escribo ni altero tests. Si un test parece mal, PARO y lo reporto. |
| **Dante** | "No tengo la dependencia real, reutilizo la respuesta capturada la última vez." | Nunca persistir una respuesta capturada como fixture. Si no alcanzo la dependencia real, lo reporto — nunca sustituyo y lo llamo equivalente. |
| **Moriarty** | "Ya encontré la causa mientras atacaba, la arreglo ya que tengo Edit y Write." | Edit y Write son SOLO para mi propio directorio de memoria. Nunca sobre el código que ataco. |
| **House** | "Con mirar el código ya sé la causa, no hace falta reproducirlo." | Saltarse la reproducción = estás adivinando, no diagnosticando. PARA. |
| **Bilbo** | "Llevo un rato sin encontrar nada nuevo, entrego ya aunque no llegue al 90%." | No declares "hecho" cuando dejas de encontrar cosas — decláralo cuando el número lo confirme. |
| **Argus** | "Ultron dice que el fix es trivial, no hace falta re-revisarlo." | Siempre re-reviso tras el fix. Ultron no puede auto-certificar arreglos de seguridad. Regla dura, no juicio. |
| **Cerberus** | "Es solo un nitpick, lo dejo para otra ronda." | TODOS los hallazgos se atienden, incluidos T3. No bloqueante = arréglalo ahora. |
| **Yoda** | "Nadie encontró nada, así que apruebo." | Ausencia de hallazgos no es prueba de corrección. |
| **Alexandria** | "Ya que documento, arreglo el bug que vi." | ¿Encontraste un bug leyendo? Se lo pasas a Ultron, no lo tocas. |

---

## BLOQUE 9 — El mecanismo (aquí está lo único que garantiza)

### 9.1 · El cerrojo de cierre

**Fichero nuevo:** `unmassk-toolkit/hooks/checklist-gate.py`
**Registro:** `unmassk-toolkit/hooks/hooks.json`, evento `Stop`, timeout 5s

```
ANTES:  (no existe; el evento Stop no tiene ningún hook desde D-046, 2026-08-23)
DESPUÉS:
  - Lee el estado del tablero de tareas de la sesión.
  - Si hay casillas en `pending` o `in_progress`, responde
    {"decision": "block", "reason": "Casillas abiertas: <lista>. Termínalas o retíralas explícitamente."}
  - Si están todas cerradas, o el tablero está vacío, sale con 0 y no dice nada.
```

**Las cuatro protecciones, y ninguna es opcional** — cada una viene de un fallo real documentado:

| Protección | El fallo que evita |
|---|---|
| Comprobar `stop_hook_active` y no volver a bloquear una segunda vez | Un hook de cierre entró en bucle y se comió los 50 minutos completos de una sesión (issue #55754 de Anthropic) |
| Máximo 2 bloqueos por sesión, y luego pasa | `taskmaster` repite sin límite por defecto, para siempre |
| **No ejecuta tests, no lanza procesos, no llama a ningún modelo.** Solo lee el tablero | R-009: 704 procesos huérfanos hasta dejar la máquina sin poder arrancar nada. Y D-046 de ayer: el gate anterior se comía medio millón de contexto |
| Ante error, dato mal formado o tablero ilegible: **deja pasar** y lo dice | `tdd-guard` bloqueó en silencio TODAS las ediciones cuando su modelo dejó de existir. Y se caía entero con un JSON mal formado |

**El hueco que este cerrojo NO cubre, y hay que decirlo:** nada impide marcar una casilla sin haber hecho el trabajo. El cerrojo comprueba que las casillas están cerradas, no que sean verdad. Cubrir eso es el bloque 9.3.

### 9.2 · El comando de reglas solo sabe añadir

**Fichero:** `unmassk-toolkit/lib/memory/commands/rule.py`

```
ANTES:  usage: rule.py [-h] [--kind {user,claude}] [--quote QUOTE] [text]
        Solo añade. No hay forma de retirar ni de fusionar una regla.
        Consecuencia medida hoy: cuatro reglas distintas dicen lo mismo sobre informar de agentes.

DESPUÉS: añadir dos subcomandos y un aviso:
        rule.py --remove <n> "<motivo>"      retira una regla (archivada, no borrada del historial)
        rule.py --merge <n> <m> "<texto>"    funde dos en una, con el texto nuevo
        Y al guardar: si la regla nueva se parece a una existente, el comando rechaza
        y muestra la candidata, igual que ya hace `gitmem note` con las notas duplicadas.
```

**Por qué esto va antes que el bloque 1:** el fichero de reglas dice "Lo escribe el script. No editar". Sin este cambio, las dos reglas duplicadas no se pueden retirar sin romper esa norma.

### 9.3 · El revisor que no ve tu conclusión

Es el mejor mecanismo de todo el barrido y no lo tenemos. Hoy, cuando paso un trabajo a Cerberus o a Yoda, les mando **mi razonamiento incluido**. La fuente dice: *"Pass ARTIFACT + CONTRACT only. Do NOT pass the CLAIM. Handing the reviewer your conclusion biases it toward agreement."*

**Cambio:** en `unmassk-core`, sección de delegación, regla nueva:
```
DESPUÉS: Al mandar algo a revisar, se envía el trabajo y el contrato que debía cumplir.
         Nunca tu conclusión, ni tu diagnóstico, ni por qué crees que está bien.
         Un revisor que lee tu conclusión te da la razón.
```

### 9.4 · Las casillas de cada skill

Cada skill crea sus casillas en el tablero al cargarse. El cerrojo (9.1) es lo que las hace obligatorias.

**`unmassk-flow` — 15 casillas**
```
- [ ] Gate: sin feature de Flow abierto antes de arrancar uno nuevo
- [ ] Triaje: tamaño decidido (Trivial/Standard/Big) y seam declarada en el context commit
- [ ] Brainstorm: gray areas resueltas y modo de build (test-first/linear) decidido
- [ ] Research: hallazgos de Bilbo guardados como memo antes de escribir el plan
- [ ] Plan: docs/plan/*.md escrito y Plan Checker pasado
- [ ] Execute: todas las tareas del wave map verificadas
- [ ] Verify — Cerberus y Argus entregados, hallazgos leídos
- [ ] Verify — Ultron corrigió en un solo pase lo que encontraron
- [ ] Verify — Dante entregó los tests, cobertura ≥ barra del perfil
- [ ] Verify — Moriarty entregó veredicto sobre código y tests
- [ ] Verify — Ultron y Dante repararon lo que Moriarty rompió
- [ ] Verify — Yoda dio su único veredicto, ≥ barra del usuario
- [ ] Document — Alexandria actualizó las tres superficies y el CHANGELOG
- [ ] Close — suite completa del proyecto en verde
- [ ] Close — merge/push hecho, rama borrada, issue cerrada, plan COMPLETED
```

**`unmassk-close-session` — 4 casillas**
```
- [ ] Limpieza — temporales listados por nombre, o "ninguno encontrado" explícito
- [ ] Ramas e issues — rama con su estado, issues por número, ficheros sin commitear por nombre
- [ ] Alexandria (modo close) — informe recibido: qué corrigió, qué contradicción encontró, qué quedó sin hogar
- [ ] Agente de cierre — commit [NEXT] verificado con git log -1
```

**`unmassk-audit` — 14 casillas**, una por paso, cada una con lo que la hace comprobable (recuento de ficheros leídos, veredicto emitido, cobertura alcanzada). Detalle completo en el informe del barrido.

**`unmassk-council` — 1 casilla nueva y decisiva**
```
- [ ] Frame confirmado por el usuario ANTES de convocar a los 11 subagentes
```

---

## BLOQUE 10 — Lo que este plan NO hace, y por qué

| Descartado | Por qué |
|---|---|
| Un hook que bloquee antes de cada acción (`PreToolUse` general) | La petición formal #45427 a Anthropic documenta que fallan en silencio, que un subagente los esquiva por completo, y que el propio modelo puede reescribirlos con acceso a terminal. Coste alto, garantía parcial. |
| Un segundo modelo que juzgue si el trabajo está bien antes de dejar cerrar | Es lo que hace `tdd-guard` y es su punto débil: mete un juicio probabilístico dentro de algo que se vende como determinista. Y cuando su modelo desapareció, bloqueó todo en silencio. |
| Una lista negra de comandos por expresión regular | D-013 de este proyecto ya lo declaró "un pozo sin fondo": tres rondas de parches no cerraron el hueco porque el fallo estaba en el orden de normalización, no en la lista. |
| Reescribir las 2.776 líneas de scaffolding | El bloque 7 las parte, que es lo que baja el coste. Reescribirlas línea a línea es otra tarea. |
| Tocar el material de seguridad de las fichas de agentes | Las fichas viajan a todos los proyectos del propietario. Que aquí no haya atacante externo no dice nada sobre si Argus debe llevar OWASP. Ese error costó una ronda entera el 2026-08-06. |

---

## Resumen de tamaño

| Bloque | Ficheros | Líneas que cambian | Riesgo |
|---|---|---|---|
| 1 · reglas | 1 | 11 (2 borrados, 9 reescrituras) | bajo — **bloqueado por 9.2** |
| 2 · CLAUDE.md | 1 | 12 | bajo — **1 decisión del propietario** |
| 3 · core | 1 | 11 + sección nueva | bajo |
| 4 · memory | 2 | 5 + 3 filas nuevas | bajo |
| 5 · skills de proceso | 6 | 11 | bajo |
| 6 · audit + standards | 5 | 24 | bajo |
| 7 · scaffolding | 3 → 40 | partición, sin reescritura | medio — mueve ficheros |
| 8 · fichas de agentes | 9 | 24 + 9 tablas nuevas | medio — **1 verificación pendiente** |
| 9 · mecanismo | 3 nuevos + 2 | código nuevo | **alto — es lo único que puede romper una sesión** |

**Orden obligatorio:** 9.2 (comando de reglas) → 1 y 2 → 3, 4, 5, 6, 8 en paralelo → 7 → 9.1, 9.3, 9.4 al final, cuando las casillas ya digan lo correcto.

---

## Las tres cosas que necesitan al propietario

1. **CLAUDE.md:86 contra rules.md:30** — ¿los commits rutinarios piden permiso o no? Las dos reglas son suyas y se contradicen.
2. **El cerrojo de cierre (9.1)** — es la misma pieza que ayer fundió la memoria en Moria, con la diferencia de que esta solo lee casillas y no ejecuta nada. Va o no va.
3. **`memory: project`** — antes de borrarlo de las nueve fichas, comprobar en ejecución si Claude Code hace algo con ese campo.
