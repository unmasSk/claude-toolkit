# Prueba en seco — destilación de memoria vieja (Bilbo, 2026-08-05)

Encargo: cosechar zonas candidatas y destilar los 100 commits de memoria más antiguos del repo `claude-toolkit`, de lo viejo a lo nuevo. No se ha commiteado nada, no se ha ejecutado ningún comando de escritura de memoria. Todo el resultado vive aquí.

Repo en `HEAD` = `a5042d4` (2026-08-05, rama `feat/memoria-v2`).

---

## 0. El universo de commits de memoria

Se contaron los cuatro tags del sistema viejo (`decision(`, `memo(`, `remember(`, `context(`) en el `%s` de cada commit del historial completo (1870 commits en total).

| Clase | Nº commits |
|---|---|
| `decision(` | 295 |
| `memo(` | 248 |
| `context(` | 200 |
| `remember(` | 160 |
| **Total memoria** | **903** |

De los 903, la ronda tratada aquí es **la más antigua**, del `2026-03-05` al `2026-03-14` (10 días, la primera semana y media de vida del repo).

`903 / 100 = 9.03` → **10 rondas** de tamaño 100 (nueve rondas completas + una última de 3 commits).

Nota aparte, no pedida pero observada: `CLAUDE.md` (cabecera de la rama) dice "el viejo lleva 1.818 commits". El recuento real ahora mismo es 1870 commits totales en el repo (903 de ellos de memoria). La cifra del CLAUDE.md está desactualizada — el repo ha seguido creciendo desde que se escribió esa nota. No es mi trabajo corregirlo (Alexandria/el propietario), solo lo dejo constatado porque afecta a cualquier cálculo de "cuántas rondas quedan".

---

## PASADA 0 — cosecha de zonas

El sistema viejo no tenía zona1+zona2: tenía `tipo(scope)`, un único scope. Para cosechar candidatos a **zona2** miré la frecuencia de cada scope en los 903 commits de memoria de todo el historial (no solo los 100). Excluí `claude`, `user` y `user/bex`: no son zonas — son el subtipo de `remember(claude)` / `remember(user)`, confirmado leyendo varios ejemplos (`remember(claude): filtrar los hallazgos...`, `remember(user): Bex prioriza...`).

### Candidatos a zona2, por frecuencia real (top, con ejemplo)

| Zona2 candidata | Apariciones | Ejemplo real |
|---|---:|---|
| `memoria-v2` | 85 | `decision(plugin/memoria-v2): la secuencia de §12bis no se abrevia` |
| `chatroom` (+ `chatroom/design`, `/frontend`, `/ux`, `/agents`, `/architecture`, `/bridge`) | 56 + 31 = 87 | `decision(plugin/chatroom): stack definitivo del chatroom: backend Bun + Elysia...` |
| `boot` | 42 | `decision(plugin/boot): boot v2 — SessionStart hace todo` |
| `memory` | 38 | `decision(plugin/memory): #3 CERRADO...` |
| `architecture` | 38 | `decision(plugin/architecture): multi-plugin en misma repo` |
| `recall` | 34 | (recall del orquestador, inyección de memoria relevante) |
| `pentesting` | 19 | `wip(plugin/pentesting): tools .py levantadas (12) a sus skills` |
| `log-parsing` | 17 | `wip(plugin/log-parsing): arreglo raiz #57...` |
| `roadmap` | 15 | — |
| `release` | 15 | — |
| `lifecycle` | 15 | — |
| `design` (unmassk-design) | 13 | `decision(plugin/design): 11 referencias + Pro Max scripts` |
| `gitmemory` | 12 | — |
| `hooks` | 11 | — |
| `skills` | 10 | — |
| `seo` | 9 | — |
| `flow` | 9 | — |
| `ci` | 9 | `memo(plugin/ci): antipattern - flakiness Ubuntu-CI RESUELTA (#61)` |
| `consolidation` | 9 | — |
| `toolkit` | 8 | — |
| `methodology` | 8 | — |
| `cad` | 8 | — |
| `agents` | 7 | — |
| `tests` | 10 (6+4) | — |
| `ops` | 6 | — |
| `electronics` | 6 | — |
| `vscode-extension` / `extension` | 9 (5+4) | — |
| `marketplace` | 5 | — |
| `marketing` | 5 | — |
| `direction` | 5 | — |
| `compliance` | 5 | — |
| `standards`, `lib`, `humanize`, `frontend`, `docs`, `db`, `backlog` | 4 cada uno | — |
| `f6`, `config` | 3 cada uno | — |
| `scout`, `prompt-improver`, `process`, `date-parsing`, `crew`, `close-session`, `audit`, `3d` | 2 cada uno | — |

Categoría aparte, **no es zona de producto**: `deadend/doc-drift`, `deadend/toolkit-bin`, `deadend/toolkit-tests`, `deadend/toolkit-hooks`, `deadend/validation-hooks`, `deadend/gitmemory-trailers`, `deadend/memoria-v1-superficie`, `deadend/close-session` (1-2 cada uno). Son el propio mecanismo de dead-ends de Bilbo (memo(deadend/…)), no temas de producto — no deben entrar como candidatos a zona2.

También aparte: `forms`, `api`, `ui`, `db`, `global`, `capture` con conteos bajos (2-3) — **son en su mayoría los commits de demo/prueba del propio sistema** (ver hallazgo en Pasada 1, nota 1). No los propondría como zona2 real sin revisar cada uno a mano.

### Hallazgo que hay que decidir antes de aprobar zonas

Este repo **no es un producto, es un marketplace de ~15 productos** (plugins): memoria/gitmemory, chatroom, pentesting, seo, marketing, design, db, ops, compliance, cad, electronics, log-parsing... La spec de zona2 dice "la parte del producto de la que se habla, propia de cada proyecto" en singular. Aquí zona2 en la práctica ya funciona como "qué plugin/subsistema", que es correcto — pero hay casos de tres niveles (`chatroom/frontend`, `chatroom/design`, `plugin/f6`) que el modelo de dos zonas no cubre limpio: ¿"chatroom" es zona2 y "frontend" se pierde, o "ui" es zona1 y "chatroom" zona2? Sin decidir esto, cualquier nota sobre el chatroom pierde precisión. Lo dejo como pregunta para el propietario, no lo resuelvo yo.

### Las nueve zonas1 — cuáles se usan de verdad aquí

| Zona1 | ¿Se usa? | Evidencia |
|---|---|---|
| `product` | **Sí, mayoritaria** | Casi todas las decisiones de arquitectura de plugins, del sistema de memoria, del propio toolkit |
| `testing` | **Sí** | `tests` (10 apariciones), drift test, contrato test-first de Dante, fix de flakiness de CI (`plugin/ci`) |
| `codeaudit` | **Sí** | Auditorías de Cerberus/Argus/Moriarty, "10C 63W" en marketing, fixes de seguridad en código portado |
| `docs` | **Sí** | `docs` (4), changelog de Alexandria, READMEs reescritos |
| `deploy` | **Sí** | `release` (15), `marketplace` (5), version bumps, reinstalación de plugin, CI |
| `database` | **Débil / mayormente falso positivo** | Solo hay trabajo real de base de datos en el chatroom (bun:sqlite). El resto de hits con scope `db` es **construir un plugin de contenido sobre bases de datos** (`unmassk-db`) — eso es `product`, no `database`. Los 25 hits de "database/db" en subjects son mayoritariamente ese caso o commits demo |
| `api` | **Prácticamente sin uso real** | Los 2 hits de scope `api` son de los commits demo (ver nota 1); el resto de menciones de "api" son contenido de un skill de pentesting (`api-security` como categoría de vulnerabilidad a auditar en proyectos de terceros), no una API propia de este toolkit |
| `ui` | **Sí, pero no rotulada así** | Trabajo real de UI existe (chatroom frontend/ux/design, iconos de la extensión VS Code) pero nunca aparece con scope literal `ui` salvo en los commits demo |
| `auth` | **No usada / marginal** | Un solo hit real: circuit-breaker de auth failures en `chatroom/frontend`. El resto de menciones de "auth" son contenido del skill de pentesting (`authentication` como categoría a auditar EN OTROS proyectos), no auth propia de este toolkit |

---

## PASADA 1 — destilación de los 100 commits más antiguos

Procesados de más antiguo (`92e0f0d`, 2026-03-05) a más reciente del lote (`74ee47b`, 2026-03-14). **30 notas** producidas a partir de 57 de los 100 commits (varios commits alimentan más de una nota); **43 commits se descartan sin nota** — el porqué de cada uno está en la tabla al final de esta sección.

### Notas destiladas

```
[M-001][product][memory] toolkit's own git history has synthetic demo commits, must be filtered
Description: commits 92e0f0d, 58a4a2f, b56aacb, 0d8a1f6, f9bb7f1, 689817d, ed90964, 0343b00,
da3e507 (2026-03-05, todos con Issue: CU-010, scopes forms/api/ui/db/global) son decisiones y
memos de una app demo (dayjs vs moment, paginación cursor, tailwind, índice compuesto, arrow
functions, filtros estilo Notion, no usar fs síncrono) usados para validar el propio sistema de
git-memory. Se mezclaron con el historial real del proyecto. Un memo contemporáneo (da91ea5) ya
lo señaló en su momento. Cualquier ronda de destilación futura debe saltarse estos commits.
Keys: synthetic, demo commits, CU-010, test fixtures, noise
Origin: 92e0f0d, 58a4a2f, b56aacb, 0d8a1f6, f9bb7f1, 689817d, ed90964, 0343b00, da3e507, da91ea5

[D-002][deploy][distribution] plugin de Claude Code es la distribución primaria, el instalador manual queda como fallback legacy
Why: Claude Code tiene sistema de plugins nativo (/plugin install, marketplace, autocarga de
skills/hooks, $CLAUDE_PLUGIN_ROOT) — no hay razón para mantener clone+install manual como vía
principal
Description: decisión fundacional de distribución, tomada a los dos días de nacer el repo
Keys: marketplace, plugin system, installer, legacy path
Origin: 9c86b44

[M-003][deploy][toolkit] el marketplace/producto se llama "unmassk-claude-toolkit"
Description: nombre confirmado vigente hoy (es la ruta base del propio skill que emite esta nota)
Keys: naming, marketplace name, rebrand
Origin: e8211de

[D-004][product][architecture] el toolkit se distribuye como varios plugins independientes y
complementarios en el mismo repo de marketplace
Why: modularidad (instalas solo lo que necesitas) sin perder integración real entre plugins
Description: sigue siendo cierto hoy con 10+ plugins (gitmemory/crew, flow, audit, seo,
marketing, design, db, ops, compliance, chatroom...). Los recuentos concretos que dan estas
mismas decisiones ("4 plugins", luego "8 plugins") ya están obsoletos — el marketplace los ha
superado ampliamente; se cita el hash por trazabilidad, no por la cifra
Keys: multi-plugin marketplace, modularidad, complementariedad
Origin: 66bb671, 03700d2, ad5a221

[D-005][product][architecture] los plugins de dominio nuevos son solo-skill: cero agentes nuevos,
los agentes del crew ejecutan vía carga de skill
Why: los agentes del crew (Bilbo, Ultron, Dante, Cerberus, Argus, Moriarty, House, Yoda,
Alexandria) deben hacer MÁS que los agentes externos portados, no menos — una sola capa de
ejecución, no un agente por plugin
Description: patrón confirmado en seo, marketing, design y, más tarde, db/ops/compliance
Keys: skill-only plugin, no new agents, crew execution
Origin: 0b7434c, 1c4152b, 03700d2

[M-006][product][architecture] al portar un repo externo a un plugin nuevo, se incorpora todo
(skills, referencias, MCPs, hooks, scripts), un plugin a la vez, completo antes de empezar el
siguiente
Origin: 1c4152b

[M-007][product][architecture] los scripts que usa una skill viven dentro del directorio de esa
skill, nunca huérfanos en la raíz del plugin (eso crea código muerto)
Origin: 5030fc3

[M-008][product][architecture] el SKILL.md debe mandatar el uso de sus scripts como paso
explícito del flujo ("ejecuta X para Y"), no solo listarlos como disponibles
Origin: 7f979f7

[M-009][product][architecture] las instrucciones de uso de herramientas MCP van en los ficheros
de referencia de la skill, nunca solo en las definiciones de agente
Origin: 468865a

[M-010][deploy][architecture] preferencia - los subagentes se lanzan en sonnet, opus se reserva
para orquestación y decisiones complejas
Origin: 6af76d6

[M-011][codeaudit][architecture] al portar código de terceros a un plugin que se distribuye,
se corrigen TODOS los hallazgos de seguridad de Moriarty antes de publicar — nunca se envía una
vulnerabilidad conocida a los usuarios finales del plugin
Description: este requisito habla de proteger a quien INSTALA un plugin publicado (código
portado de terceros con posible CVE real), un modelo de amenaza distinto al de este mismo repo
en la rama memoria-v2 (propietario único, sin atacante externo declarado en CLAUDE.md). No son
contradictorios: aplican a superficies distintas — no confundir uno con otro
Keys: ported code, third-party vulnerabilities, shipped plugin security
Origin: e1c935c

[M-012][product][architecture] antipatrón - Ultron implementa código, Alexandria escribe
documentación y referencias — no cruzar la frontera
Origin: 77c6a96

[Q-013][deploy][toolkit] "trabajar directo en main, las ramas feature causan desincronía de
marketplace" (2026-03-14) choca con la práctica actual: una rama de larga vida
(feat/memoria-v2) con la regla explícita de "nada se commitea a main hasta que el propietario
lo diga"
Description: ninguno de los 100 commits leídos resuelve si la regla de main-directo era solo
para plugins pequeños/aislados y las reescrituras grandes usan rama a propósito, o si la regla
quedó sin más superada. No lo decido yo
Keys: main vs feature branch, marketplace desync, long-lived branch
Origin: c54bfe0, 74ee47b

[M-014][deploy][toolkit] antipatrón - "/plugin update" no funciona; el camino real es /plugin
(menú) > marketplace > seleccionar update
Origin: bdb9132

[M-015][product][toolkit] preferencia/requisito - capturar memos y decisiones sin preguntar
"¿ok?": detectar señal, commitear directo, informar después con una línea breve
Origin: e7f200b, 65216491, 530faaba, 024930c

[M-016][product][toolkit] preferencia - capturar también investigaciones, ideas y hallazgos
técnicos como memo, no solo frases explícitas de "siempre X / nunca Y"
Origin: 65216491

[M-017][product][toolkit] antipatrón - nunca ejecutar un plan mientras quede una pregunta
abierta al usuario; esperar siempre la respuesta
Description: precursor directo de la bronca #3 actual de CLAUDE.md ("una pregunta cada vez... y
esperas la respuesta")
Origin: f27bbea, 4e0cb0b

[M-018][product][toolkit] antipatrón - al lanzar agentes, prompts cortos con el QUÉ, nunca
repetir el CÓMO que ya está en la ficha del agente
Origin: 12d9500

[M-019][product][toolkit] antipatrón - nunca afirmar que un fix funciona sin verificarlo de
punta a punta desde la sesión real del usuario, no solo desde tests o lectura de código
Description: esta misma sesión (2026-03-11) envió fixes sin verificar (stop hook seguía
bloqueando, dos skills nunca cargaban, README desactualizado) y el usuario los pilló todos.
Es la raíz de la regla actual "Verify before claiming done or exists"
Origin: 801bdf7, d2eaf62, e7b0680

[M-020][product][toolkit] antipatrón - nunca borrar/reinstalar la caché del plugin con una
sesión activa; produce deadlock porque los hooks bloquean todas las llamadas a Bash
Origin: e7b0680, 34275b5, aa469d7

[M-021][product][toolkit] antipatrón - un hook de auto-instalación disparado en cada
UserPromptSubmit tiene radio de explosión total: un bug real en el instalador llegó a borrar
los propios ficheros fuente del plugin
Origin: e7b0680

[M-022][product][vscode-extension] se diseñó por completo una extensión de VS Code para
visualizar git-memory en tiempo real (arquitectura WebviewView, iconos estilo glassmorphic,
distribución local .vsix primero) a lo largo de varias sesiones, y se aparcó como "roadmap
v5.0" — nunca se construyó
Origin: 92e2576, f239a5e, 4a7f835, 9bb86bf, 741eaf6, 2e1b23b, 1d9a5a1, d54d59c, c48a87e

[D-023][product][toolkit] el bloque gestionado de CLAUDE.md se mantiene mínimo (pocas líneas
apuntando al skill); toda la lógica operativa vive en el skill cargado, no se duplica en el
CLAUDE.md de cada proyecto
Why: evita repetir contenido del skill en cada proyecto y mantiene el CLAUDE.md limpio
Origin: ca1d2b6, a6104f9

[D-024][product][toolkit] los commits de memoria se producen con scripts wrapper de salida
formateada, y un hook de control bloquea `git commit`/`git log` en crudo — solo el wrapper
(Claude) puede escribir commits de memoria, no un humano a mano
Origin: b5edd19, a7fbbca

[Q-025][product][toolkit] "los hooks salen con exit 0 y avisos agresivos, nunca bloquean duro"
(decisión de 2026-03-14 para los hooks del plugin SEO) choca con la "aduana" que se está
construyendo ahora mismo en memoria-v2, diseñada explícitamente para BLOQUEAR (rechazo +
reintento obligatorio) antes de permitir un commit de memoria
Description: ninguno de los 100 commits de este lote resuelve si la filosofía "nunca bloquea
duro" era solo para hooks de plugins publicados (afectan a otros usuarios) y los hooks de
control interno del propio toolkit sí pueden bloquear, o si hay una contradicción real sin
resolver. No lo decido yo
Origin: 01e2a24

[M-026][product][memory] los commits `remember()` capturan personalidad y estilo de trabajo de
Claude/usuario, distinto de `memo()` que captura conocimiento del proyecto
Origin: a5a3eaed, a6104f9

[M-027][docs][changelog] requisito - la automatización de changelog de Alexandria debe filtrar
commits de scope agentes/agent-memory, deduplicar de forma idempotente por SHA, y quedarse
callada si no hay nada accionable de cara al usuario que reportar
Origin: f51932f

[M-028][product][toolkit] Alexandria se añadió como agente compartido del crew (no de un
proyecto concreto) para que cada proyecto instalado tenga documentación automática gratis
Origin: 46d8898

[M-029][product][toolkit] el usuario prefiere /clear a compactar la conversación porque confía
en que git-memory retoma perfecto en la siguiente sesión — indicador clave de confianza en el
sistema
Origin: 1f39145

[Q-030][product][toolkit] la línea de co-autor del commit debería ser una constante
configurable, no hardcodeada — el valor exacto nunca se decidió en estos 100 commits (se ve
después cambiar de "Claude" a "Claude Opus 4.6" a "Claude Opus 5" de forma orgánica, no por una
constante configurada)
Origin: ef32e2e
```

### Los 43 commits descartados, y por qué

| Commit | Por qué se descarta |
|---|---|
| `a0b9530` | Origen del git-memory v1 completo (memo(), búsqueda, drift test). El sistema entero que construyó está siendo reemplazado ahora mismo por memoria-v2 en esta misma rama — sin valor hacia delante |
| `dfb50e5`, `02c5ef9`, `fa7481e`, `6426f73`, `443bab4`, `bef8506` | Mecánica interna del "boot v2" de v1 (SessionStart, scout, skills issues/milestones) — todo ese subsistema se borra con memoria-v2 |
| `803e7d6` | Stop hook que obligaba `context()` antes de cerrar sesión — superado: en v2 el cierre de sesión lo hace un agente que lee la conversación, no un hook |
| `5fa5dbe6` | Memo "falta plugin de base de datos" — ya resuelto, `unmassk-db` se construyó después (visible en el propio historial: commits `plugin/db`) |
| `cd82c63` | Instrucción de sincronización puntual (renombrar `enterprise-audit`→`unmassk-audit` en agentes) — tarea de una vez, ya ejecutada |
| `7a2bb37` | Requisito de gitignore atado a `git-memory-scopes.json`, artefacto específico de v1; sin verificar si v2 tiene equivalente, no se traslada a ciegas |
| `30e9ac8` | Mecánica de integración del agente "scout" — ese agente se elimina en el mismo lote de commits, subsistema muerto |
| `37716ea` | Memo "ya se resolvió esto, no lo repitas" — puntero a algo ya cerrado, sin contenido propio |
| `a485743` | Brainstorm de sesión cuyos 5 puntos ya están recogidos individualmente en las notas 015/023/024/026 — duplicado |
| `bdd3895` | Decisiones de Safety + skill issues/milestones de v1 — mecánica de boot que muere con v2 |
| `cdcfa06` | Log de sesión puro ("pausa, el usuario va a reinstalar") — sin contenido duradero |
| `d7a8235` | Fix del instalador v1 para limpiar hooks obsoletos en migración "zero-copy" — mecánica específica de un instalador que ya no es el modelo de distribución actual |
| `967a196`, `0dcca438`, `59b05f1`, `a6fcba5`, `af8687a`, `cc4e02a`, `c95d421`, `87e15ca`, `d445903`, `21646f2`, `c97cc8d`, `117514e`, `0406ed7`, `b71dcaf`, `d92287f`, `94ee004`, `0235839`, `4342bec`, `37d65eb`, `703f7c6`, `9dcbc4a`, `b8b2bb4`, `4927aa8`, `6b775ab`, `d5f48e9`, `8c0a646` | Checkpoints de sesión ("Next:", "sesión productiva", % completado) o decisiones de contenido interno ya construido y estable de los plugins SEO/marketing/design (qué MCPs, cuántas referencias, qué paleta de iconos) — entregables completos y estáticos, no quedan decisiones abiertas que destilar |

---

## Cómo se mide

**1. Commits de memoria totales, por clase, y rondas de 100.**
903 en total: 295 `decision`, 248 `memo`, 200 `context`, 160 `remember`. Salen **10 rondas** (9 de 100 + 1 de 3).

**2. De los 100 tratados: cuántas notas, de qué tipos, cuántos commits quedan fuera y por qué.**
**30 notas** de 57 commits distintos (varios commits alimentan más de una nota); **43 commits sin nota** (tabla arriba). Reparto por tipo: **22 M**, **5 D**, **3 Q**, **0 X, 0 R, 0 I, 0 B**.

**3. Con qué me he peleado.**
- **No hay tipo para "se diseñó del todo y se aparcó indefinidamente".** La nota 022 (extensión VS Code) no es una decisión vigente (D), no es un hecho estable de "cómo es el proyecto ahora" (M en sentido estricto), y desde luego no es X ("se estudió y se rechazó") — nadie la rechazó, se despriorizó. La until forcé a M porque es lo más parecido, pero pierde matiz: un lector de la nota no sabe, sin abrir el body, que esto NO se va a construir salvo que alguien lo retome.
- **Zona1 no encaja bien con "construir un plugin de contenido sobre X".** Un commit con scope `db` casi siempre resultó ser "estamos construyendo el plugin unmassk-db" (trabajo de producto sobre un plugin que enseña bases de datos a terceros), no trabajo de base de datos de este propio toolkit. Etiquetarlo `database` sería falso; etiquetarlo `product` es correcto pero pierde la pista de "iba de bases de datos". Mismo problema con `api` y con `ui` (unmassk-design es un plugin sobre diseño, no diseño propio del toolkit). La zona1 fija de nueve valores no distingue "trabajo EN el dominio X" de "trabajo construyendo UN PRODUCTO SOBRE el dominio X para terceros".
- **Zona2 de tres niveles.** `chatroom/frontend`, `chatroom/design`, `chatroom/ux`, `chatroom/agents`, `chatroom/architecture`, `chatroom/bridge` — seis sub-áreas reales bajo un mismo zona2 candidato (`chatroom`). El modelo de dos zonas obliga a elegir: o se pierde la sub-área, o se inventa una zona2 distinta por cada combinación (`chatroom-frontend`, `chatroom-ux`...) que infla el catálogo de zonas sin que el propietario lo haya aprobado así.
- **Contradicciones genuinas entre decisiones viejas y el estado/las reglas actuales**, sin que ningún commit de este lote las resuelva: main-directo vs rama larga (Q-013), hooks-nunca-bloquean vs la aduana bloqueante de memoria-v2 (Q-025). No sé si son evoluciones deliberadas o deuda sin cerrar — las dejo como Q en vez de decidir.
- **El descarte de "checkpoint de sesión puro" es un juicio, no un hecho medible.** Decidir que 26 commits de "sesión productiva, X/Y completado" no merecen nota es una llamada de criterio mía; otro destilador podría rescatar alguno como "hecho estable" (p.ej. qué exactamente incluye unmassk-marketing v1.0.0). Lo dejo explícito en vez de ocultarlo bajo "no eran relevantes".

**4. ¿Es 100 un tamaño de ronda razonable?**
Con lo medido, **no para este primer tramo**: los 100 primeros commits cubren **10 días** de un proyecto que en su arranque mezcló pruebas del propio sistema (nota 001), un experimento aparcado de tres sesiones completas (VS Code extension, 9 commits), y dos sesiones de auditoría/parcheo del instalador (13 commits) — es decir, dentro de un solo corte de 100 conviven fases con nada que ver entre sí, y el ratio nota/commit salió 30/100 (0.3) muy influido por eso. Un corte natural mejor, medido sobre este mismo lote: **por sesión/tema**, no por cantidad fija — el propio historial ya viene segmentado por commits `context()` que marcan cierre de sesión (aquí hay 200 en todo el repo) y por scope (`vscode-extension` completo son 9 commits consecutivos, `install-safety` son 6, la primera racha "seo/marketing/design" del final de este lote son ~45 commits de una sola mega-sesión de construcción de plugins). Cortar por scope+context() habría dado lotes de 6-45 commits en vez de un corte ciego de 100 que parte "seo/marketing/design" a la mitad (esta ronda termina en pleno medio de la sesión de plugins, commit 100 de 100 es `74ee47b`, y la siguiente ronda seguiría el mismo hilo). No tengo medición sobre rondas posteriores (esta es la primera de diez) para saber si el problema se repite o si sesiones más maduras y estables producen lotes de 100 más homogéneos — dato que solo sale de destilar más rondas.

---

## Handoffs

No hay hallazgo de seguridad, de mantenibilidad de código, ni gap de documentación pública que reportar — este ejercicio es interno al proceso de destilación, no toca código de producto. Dos preguntas (Q-013, Q-025) y una ambigüedad de taxonomía (chatroom multinivel, zona1 vs "producto sobre X") quedan para el propietario/Yoda, no para otro agente del crew.

## DEAD-ENDS

DEAD-ENDS (subsystem: memoria-v2-distillation) — question: cómo se comporta Bilbo destilando 100 commits reales de este repo, para diseñar su nueva función
- found in: la ronda 1 completa (commits `92e0f0d`..`74ee47b`, 2026-03-05 a 2026-03-14) queda destilada en las 30 notas de este fichero; no hace falta re-caminarla
- found in: el hallazgo "demo commits polucionando el historial" (nota M-001) ya estaba semi-documentado en `da91ea5` desde 2026-03-07 — no re-descubrir, solo re-verificar si sigue habiendo commits demo sin marcar en rondas posteriores
@a5042d4
