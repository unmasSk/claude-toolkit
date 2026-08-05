# Prueba en seco #2 — destilación de memoria vieja, sobre un producto real (Bilbo, 2026-08-05)

## Aviso — esta es la v2 del fichero, y por qué

La primera versión de este documento se escribió **sin la skill de memoria delante** — solo con un resumen del formato dado en el encargo. Con `SKILL.md` y `references/distill.md` leídos enteros, esa versión tenía un fallo de fondo, no de detalle: de las 43 "notas de memoria" que produje, solo **6 eran memoria real del proyecto**. Las otras 37 eran reglas de cómo trabaja el equipo de agentes (protocolo de auditoría, prompts, orden de un checkpoint, convenciones de código) que la propia skill manda a un canal aparte — y las metí como notas de producto porque leían gramaticalmente igual que una decisión ("decidimos que la auditoría tiene 8 pasos" se lee igual que "decidimos usar Postgres"), sin aplicar la prueba que la skill ya tenía escrita: **¿esto seguiría siendo verdad si otro equipo construyera OmawaMapas?** Si no, es una regla, no memoria — por muy D o M que parezca.

Esta versión rehace la Pasada 1 con esa prueba aplicada a los 100 commits, commit a commit. La Pasada 0 (cosecha de zonas) no cambia — sigue siendo un hallazgo válido y, de hecho, ahora explica mejor por qué salió lo que salió.

Repo destilado en `HEAD` = `843dc08` (2026-07-31), 2506 commits totales, solo lectura. `claude-toolkit` en el momento de la prueba, `a5042d4`.

**Los identificadores `[D-N]` son provisionales**, solo para referenciar una nota desde otra dentro de este fichero en seco — el sistema real los asigna al guardar.

---

## El recuento honesto — el resultado de la prueba

**De los 100 commits de memoria más antiguos (2026-03-08 a 2026-03-14):**

| | Commits | Notas/reglas resultantes |
|---|---:|---:|
| **Memoria de proyecto genuina** | 7 commits fuente | **6 notas** (D-001…D-006) |
| **Reglas — canal aparte, no memoria** | 60 commits fuente | **39 reglas** |
| **Descartado — ni nota ni regla** | 35 commits | — |
| *(solapan: 2 commits alimentan a la vez una nota y una regla)* | | |

100 = 7 + 60 − 2 (solape) + 35. Cuadra exacto.

**6 de 100 — el 6%.** No 43. La ronda 1 de OmawaMapas es, casi entera, el montaje del propio proceso de auditoría con agentes — exactamente lo que `distill.md:66` dice que hay que esperar de un historial temprano: *"the first weeks of a project are usually about setting up how it will be worked on, not about the product itself"*.

---

## 1. Notas de memoria de proyecto (6)

Cada una pasa la prueba de los seis meses del `--why`, y la prueba del equipo distinto: seguirían siendo ciertas sobre OmawaMapas aunque lo construyera otro equipo con otras herramientas.

```
[D-001][database][config] Supabase SSL usa rejectUnauthorized=true en producción
Why: Supabase emite certificados de CA pública que validan correctamente con el CA store de
Node.js; dejarlo en false abría la conexión a MitM sin necesidad real
Description: cambio de configuración de conexión a BD en producción, auditoría de config/
Keys: mitm, certificados, produccion, nodejs
Discard: "rejectUnauthorized=false" — dejaba la conexión abierta a un ataque que no hacía falta
correr, dado que el certificado ya es de CA pública válida
Origin: dcd3ff7

[D-002][database][config] deepFreeze se mantiene en database/constants.ts pese a ser redundante
con 'as const' en teoría
Why: 'as const' solo da tipos en compile-time; el objeto usa valores de runtime (envConfig), y
los tests verifican Object.isFrozen en objetos anidados (POOL_CONFIG, ERROR_CODES) — quitarlo
permitiría mutación en runtime y rompería esos tests, por un overhead que se paga una sola vez
al arrancar
Keys: runtime, mutacion, pool-config, tests
Discard: "quitar deepFreeze y confiar solo en as const" — as const no protege nada en runtime,
solo en tipos; los tests de inmutabilidad dejarían de tener sentido
Origin: 83f2b0e

[D-003][api][swagger] swagger no expone devServer como alternativa en prod/staging, solo en
dev/test
Why: SEC-MED-001 — listar localhost:PORT en el swagger de producción exponía información de
infraestructura interna sin que el cliente la necesitara para nada
Keys: sec-med-001, infraestructura, entornos
Discard: "mostrar siempre devServer" — expone datos internos a cualquiera con acceso a la
documentación pública de la API
Origin: 129bd2d

[D-004][api][validation] .strict() es obligatorio en todos los schemas Zod de request
Why: confirmado en la auditoría de api/auth/ (score 34→110) — sin .strict(), Zod deja pasar
campos extra sin avisar, y el cliente cree que esos campos fueron validados cuando no lo fueron
Keys: schemas, payload, campos-extra
Discard: "schemas sin .strict()" — permite que payloads con datos no validados pasen en silencio
Origin: c7d21db

[D-005][api][inventario] la API usa PATCH, no PUT, para actualizaciones parciales
Why: PUT implica reemplazo completo del recurso; los endpoints reales solo tocan un subconjunto
de campos — usar PUT ahí rompe la semántica REST y obliga al cliente a reenviar el recurso
entero para cambiar uno solo
Description: decidido durante la auditoría de api/inventario/ (issue #11); se lee como una regla
general de la API, no solo de ese módulo
Keys: rest, semantica, actualizacion-parcial
Discard: "mantener PUT para updates parciales" — fuerza al cliente a mandar el recurso completo
por cada cambio pequeño
Origin: b4dc3c7

[D-006][api][auth] requestId se recibe como parámetro en toda la cadena de AuthService, nunca
se genera dentro
Why: la re-auditoría independiente de auth/ encontró que validateUser/authenticateUser/hasRole
generaban su propio requestId internamente — eso rompe la trazabilidad end-to-end de un mismo
request a través del servicio de autenticación
Keys: trazabilidad, end-to-end, authservice
Discard: "generar requestId dentro de cada método" — cada capa produce un ID distinto para el
mismo request real, imposible de correlacionar en logs
Origin: 620bedf, 5d6d669
```

---

## 2. Reglas — canal aparte, no memoria de proyecto (39)

`gitmem rule` no acepta `--origin` hoy — no hay dónde citar la fuente en el sistema real. Lo apunto igual aquí, porque es lo que permite decidir después si se pierde sin más o si el canal de reglas necesita ese campo.

1. Tiers T1/T2/T3 como base de auditoría de calidad. — `dd8624e`
2. Auditoría manual no basta: verificación cruzada con agentes independientes antes de declarar "enterprise". — `f17572a`
3. Nunca `expect(true).toBe(true)` como cobertura; aserciones reales siempre. — `7039416`
4. Seguir el roadmap de auditoría en orden estricto de nivel, sin saltar. — `00cd481`
5. Test-first: golden tests capturados ANTES de tocar código, en cada auditoría de módulo. — `ebdc419`, `53c29f0`
6. Lectura obligatoria de ENTERPRISE-STANDARDS.md + AUDIT-PROCESS.md antes de auditar; comentarios/JSDoc/logs en español, identificadores en inglés. — `5f7492a`, `b6a7b34`
7. Nunca editar tests a mano en trabajo bulk — delegar siempre a un agente. — `35cf913`
8. Una auditoría nunca es suficiente: lanzar siempre un verificador independiente tras cada ronda de fixes; un agente que no ejecuta tests no puede reportar "all clean". — `a3cd843`, `c955921`
9. Pasar lint a los módulos ya auditados antes de cerrar su issue. — `9796ff8`
10. Nunca commitear, mergear o cerrar un issue sin confirmación explícita del usuario — mostrar `git status` y esperar. — `aef5c6a`, `b9a0ccf`, `e4f5750`
11. Split de archivos de producción al sweet spot 200-300 LOC (hard limit 500 solo aplica a tests). — `e4f5750`, `d89f589`, `b4dc3c7`
12. Las revisiones senior son evaluación en lenguaje natural, distinta de auditoría por tiers; solo se arregla lo bloqueante. — `a53a4787`
13. Protocolo de 8 pasos por módulo: inventario → auditoría → fix tests → golden → fixes por tier → adversarial → re-auditoría → cierre. — `fd1271f8`
14. Nunca descartar un error nuevo como "pre-existente" sin verificar su origen. — `87a0fc0`, `4cc255b`
15. Siempre `git push` al cerrar sesión, sin esperar a que se pida. — `9f073a8`
16. Planes de auditoría en `docs/plan/auditorias/`, en minúsculas, nunca se borran; cierre completo = merge + push + close issue + borrar rama local y remota; Moriarty/Yoda con anti-inflación y evidencia ejecutable obligatoria. — `c33b829`, `e76b40f`, `6b35395`, `c0f70ac`
17. Memoria persistente solo para Ultron/Cerberus/Dante/Alexandria; Moriarty/Yoda/Argus sin memoria a propósito, para evaluar limpio cada vez. — `8bddb89`
18. Prompts a agentes siempre en español; a Yoda solo se le dice el módulo, nunca checklist ni lista de archivos — nada de prompts largos, solo target y contexto mínimo. — `8bddb89`, `720c93e`, `d62cb2c`
19. Alexandria usa Diátaxis completo (4 tipos). — `1c169e9`
20. Bloques operativos (perímetro, evidencia, escalación) en 6 agentes para que no se solapen ni hablen de más. — `da416be`
21. Todo prompt a agente con memoria debe incluir leer-antes/escribir-después explícito; investigar y anotar, nunca modo automático descerebrado. — `82a7a1f`, `8ae45a9`
22. El checkpoint `wip` va DESPUÉS de que Cerberus revise el diff sin commitear, nunca antes — se corrigió dos veces el mismo día antes de asentarse en esta versión. — `a0a73c7`, `0564dec`, `50e48cf`
23. Nunca borrar agent-memory mal localizada sin leerla antes — fusionar en el destino correcto, luego borrar duplicados. — `d9680aa`
24. La skill enterprise-audit es de proyecto, no plugin distribuible — hardcodea paths/roles/stack de OmawaMapas a propósito; Argus en paralelo con Cerberus en el paso 4. — `01e0e7b`, `53c29f0`
25. Las skills se inyectan a los agentes por tarea, no se adjuntan de forma permanente. — `0e922f6`
26. Multi-Agent Adversarial Review solo para bugs críticos o decisiones de arquitectura, nunca fixes rutinarios. — `52f6ce5`
27. Preferencia de herramienta: claude-seo para SEO en Astro; marketing-skills descartado. — `1aafcef`
28. Patrones GSD adoptados en agentes ya existentes, no agentes nuevos; incident-responder descartado — House+Ultron siempre tienen tiempo. — `8640a01`, `8da8455`
29. Discuss y research van a git-memory como commits, nunca a archivos separados; solo el plan se escribe en docs/. — `4147f08`
30. Pipeline propio HeroClaude: primero 6 pasos, una review de Yoda lo lleva a 8 definitivos (TRIAGE→BRAINSTORM→RESEARCH→PLAN→EXECUTE→VERIFY→DOCUMENT→CLOSE) — la versión de 6 queda superada. — `61800c6`, `c4d1f4b`, `3cb0e6a`, `d6ceef7`, `d36524a`, `93f12ac`
31. Superpowers desinstalado — absorbido por HeroClaude y los agentes propios. — `68813d9`
32. Gate de suite completa de tests obligatorio antes de mergear, no solo el módulo auditado. — `ab8df6d`
33. Los tests de integración nunca mockean el middleware de validación. — `3c32e59`
34. Verificar siempre los claims de auth/routing contra el montaje real de rutas antes de reportarlos — nunca auditar en silo. — `0dbbca8`
35. Nunca lanzar a Alexandria en paralelo con Yoda — esperar aprobación explícita del usuario. — `489b758`
36. Agentes con memoria tienen boot/shutdown obligatorio; topic files enlazados en MEMORY.md o no se leen; tope de ~300 líneas, solo patrones reutilizables. — `be74af9`, `315cf54`
37. Imports sin usar se eliminan, nunca se prefijan con guion bajo. — `4b05f20`
38. Añadir un CLOSED CHECKLIST a AGENT-PROMPTS.md para prevenir drift en el cierre de auditorías. — `5d6d669`
39. Al instalar plugins nuevos o actualizados, comparar comportamiento con la versión anterior y reportar discrepancias al usuario. — `e3dc466`

---

## 3. Descartados (35 commits) — ni nota ni regla

| Categoría | Nº | Commits | Motivo |
|---|---:|---|---|
| Arranque de sesión puro (solo "empieza la auditoría de X, issue #N") | 9 | `6cecf5b` `9785026` `78b9cfd` `7bd3f40` `a5dbd67` `207903f` `9821bf4` `0e9b8ed` `02194c0` | Cero contenido más allá de anunciar que empieza |
| Checkpoint de progreso redundante con el cierre de la misma auditoría | 12 | `7c86f16` `4d92db5` `13a7e8c` `c37d55d` `e0a4e73` `80546011` `ba7917d` `87197f5` `9521d6c` `4a38b59` `aacfdc8` `004dff7` | Ya reafirma lo que su propio commit de cierre vuelve a decir |
| Hallazgos puntuales de un módulo, arreglados durante la construcción — trabajo ordinario, no se registra | 8 | `fe529d8` `f34cb80` `34ba949` `f63b200` `49ffc49` `f4c7937` `1424d06` `253a3e9` | Bugs de un fichero concreto ya resueltos en la misma sesión — la skill lo dice explícito: un defecto encontrado y arreglado mientras se construye es trabajo ordinario, no se anota |
| Resumen de sesión que reagrega notas/reglas ya capturadas por separado | 4 | `b8b8022` `ce8a7ca` `ff9c09a` `eedb9c4` | Los dos últimos son el mismo día, contenido casi idéntico — duplicado literal, no solo redundante |
| Contaminación cruzada de repos — habla del `claude-toolkit` externo, no de OmawaMapas | 2 | `d34fc12` `46bbce0` | Ni memoria de este proyecto ni regla de este equipo — es contenido de otro repositorio |

---

## PASADA 0 — cosecha de zonas (sin cambios respecto a la v1, y ahora se entiende mejor por qué)

### Candidatos a zona2, por frecuencia real (top, sobre los 825 commits de memoria de todo el historial)

| Zona2 candidata | Apariciones | Ejemplo real |
|---|---:|---|
| `claude` / `user` | 74 + 14 | subtipo de `remember()`, no zona |
| `frontend/diseno` (+ `frontend/design` 16, mismo concepto en dos idiomas) | 30 | `test(frontend/diseno): e2e layout-guard...` |
| `project/aws-staging` | 29 | `memo(project/aws-staging): config nginx VIVO de staging...` |
| `workflow` (+ subzonas) | 52 | `decision(workflow/creative-pipeline): pipeline final de 6 pasos...` — **con la skill delante, esto es justo la palabra prohibida (`SKILL.md:136`) y ahora sé por qué: casi todo lo que vive bajo `workflow` en este historial es regla de proceso, no zona2** |
| `backend/catastro` | 24 | `decision(backend/catastro): Widget enriquecimiento...` |
| `backend/import` | 20 | — |
| `backend/inventario` | 12 | — |
| `frontend/amianto` | 11 | — |
| `audit-municipios`, `audit-auth-core`, `middleware-audit` | 10+7+5 | contienen la palabra ambigua `audit` — mismo aviso |
| `backend/rbac` | 7 | `decision(backend/rbac): REGLA GENERAL DE ROLES...` |

### Las nueve zonas1 — uso literal sobre los 825 commits de memoria

| Zona1 | Apariciones literales |
|---|---:|
| `database` | 8 (las 8 reales: schema propio) |
| `testing` | 7 |
| `deploy` | 4 |
| `docs` | 2 |
| `product`, `codeaudit`, `api`, `ui`, `auth` | **0 cada una** |

Cinco de nueve nunca se usaron literalmente en 2506 commits. Con la skill delante esto lee distinto que en la v1: no es solo que el vocabulario del equipo difiera del catálogo — es que buena parte de lo que yo intentaba encajar en `codeaudit`/`api`/`ui`/`auth` en la ronda 1 **no era zona2 de nada, era regla**, y por eso nunca encontró una palabra de zona1 que le quedara bien.

---

## Cómo se mide

**1. Commits de memoria y rondas.** 825 en total (291 context, 266 memo, 182 decision, 86 remember) → 9 rondas de 100 (8 de 100 + 1 de 25). Sin cambios respecto a la v1.

**2. De los 100 tratados.** **6 notas de proyecto** (de 7 commits fuente), **39 reglas** (de 60 commits fuente, 2 compartidos con las notas), **35 commits descartados**. Frente a la v1 (43 "notas"): el número no bajó porque haya menos contenido real — bajó porque ahora se separa correctamente lo que es producto de lo que es proceso.

**3. Con qué me he peleado esta vez.** Separar, dentro de un mismo commit, la parte que es nota de la que es regla: `5d6d669` cierra la auditoría de auth/ con el contrato de `requestId` (nota D-006) Y con la introducción del "CLOSED CHECKLIST" en AGENT-PROMPTS.md (regla 38) — un solo commit alimentando ambos canales. Y decidir el borde entre "descarte por trabajo ordinario ya arreglado" y "regla": un bug puntual arreglado en el momento no se anota (`f34cb80`, 10 hallazgos T1 ya resueltos), pero la instrucción que ese mismo episodio deja para el futuro sí (regla 8, "lanzar siempre un verificador independiente").

**4. ¿Es 100 un tamaño de ronda razonable?** Con el número real (6 notas de producto), la respuesta cambia respecto a la v1: no es que 100 sea mucho o poco — es que **la primera ronda de un proyecto construido con auditoría asistida por agentes va a rendir casi toda su ronda en reglas, no en memoria de producto**, y eso no lo arregla ni agrandar ni achicar el corte. La `distill.md:66` ya lo avisa como propiedad general de los historiales tempranos; esta ronda lo confirma con un número concreto: 6%.

---

## Comparación con la prueba #1 (toolkit) — con la salvedad puesta por delante

**La prueba #1 no se ha vuelto a auditar con esta misma prueba de los seis meses / equipo distinto.** Es muy probable que buena parte de sus 30 "notas" (antipatrones de prompts, de checkpoints, de cuándo lanzar qué agente) tenga la misma contaminación que aquí bajó de 43 a 6 — el toolkit tiene el agravante de que su producto ES el propio sistema de agentes, así que la línea entre "cómo construimos" y "qué es el producto" es más fina que en OmawaMapas. No lo he recalculado; lo señalo para que el número de la prueba #1 no se tome como comparable sin más.

Con esa salvedad, lo que sigue en pie de la v1 y no depende del recuento de notas:

- **La ambigüedad "trabajar en X" vs "vender un producto sobre X" no aparece aquí** — 0 de 825 commits `database` la sufren, y siguen siendo los 8 del propio schema. Esto es un hecho de zona2/dominio, no de proceso, y no cambia con la corrección.
- **Cinco de nueve zonas1 nunca se usan literalmente** — dato de grep, tampoco cambia.
- **`catastro`/`amianto`/`municipios`/`rbac` emergen solos como zona2** en el historial completo — siguen siendo los mejores candidatos, aunque ninguno aparece en la ronda 1 porque esa parte del dominio se construye después.

---

## Handoffs

Ninguno sobre código de OmawaMapas. Sí uno interno: `gitmem rule` no tiene `--origin` (`SKILL.md:279-281`), así que las 39 reglas de esta ronda, si se guardan de verdad, pierden su cita — decisión pendiente del propietario, no mía.

## DEAD-ENDS

DEAD-ENDS (subsystem: memoria-v2-distillation-omawa) — question: cuánta de la ronda 1 es memoria de proyecto real una vez aplicada la prueba de la skill
- found in: 6 de 100 commits son memoria de proyecto genuina; el resto es proceso (39 reglas) o descarte (35) — recuento hecho commit a commit, no estimado
- ruled out: NOT la ambigüedad "producto sobre X" del toolkit — sigue sin reproducirse en omawaMapas, esto no cambió al aplicar la corrección
- found in: la v1 de este mismo fichero (`git log` de `claude-toolkit` para el commit que la introdujo) es el ejemplo vivo del error que la skill ahora nombra explícitamente — no hace falta repetir el análisis, está en el "Aviso" de arriba
@a5042d4 (claude-toolkit) / omawaMapas leído en 843dc08, solo lectura
