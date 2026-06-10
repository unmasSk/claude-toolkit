# Investigación — Sistema de memoria del toolkit unmassk + el Consolidador (Gitto)

> Documento para una segunda IA colaboradora. Resume todo lo que llevamos investigado sobre el rediseño del sistema de memoria, y dónde queremos tu opinión — **sobre todo para afianzar el prompt de Gitto (el consolidador)**.
> Todo lo de aquí está sacado de investigación real (código del repo, repos externos citados, y un panel de 4 agentes internos). Donde algo no consta en una fuente, se marca como tal.
> Fecha: 2026-06-10.

---

## 0. Resumen de una frase

Queremos que la **memoria del proyecto** (que vive como commits de git) (1) le **llegue** al agente principal cuando es relevante, (2) que los comportamientos obligatorios **se cumplan** de verdad, y (3) que la memoria se **mantenga limpia y ordenada** sola. Este doc se centra en la pieza 3 (el **consolidador**, que ejecutará el agente **Gitto**).

---

## 1. El sistema actual (punto de partida)

- **git-memory**: la memoria son **commits de git** con *trailers*. Cuatro tipos: `decision()` (decisiones de arquitectura), `memo()` (hechos/estado del proyecto), `remember()` (cómo es el usuario / cómo debe comportarse Claude), `context()` (puntos de retomada).
- **Buscador BM25** (`unmassk-toolkit/lib/recall.py`): rankea recuerdos por relevancia (IDF: las palabras raras pesan más), con bonus 1.5× si la palabra coincide con el *scope* del commit, y dedup por texto normalizado.
- **"El portero"** (hook `PreToolUse/Task`, `hooks/pre-task-recall.py`): antes de lanzar un subagente del crew (Ultron, Cerberus, etc.) le **inyecta** la memoria relevante en su prompt. **FUNCIONA, verificado de extremo a extremo.**
- **El ORQUESTADOR** (el Claude principal que habla con el usuario y decide) **NO tiene recall automático**: solo recibe un **volcado de toda la memoria una vez, en el arranque**. → **Fallo arquitectónico**: el que más necesita continuidad de memoria es el que peor recall tiene.
- **Mecanismos de mantenimiento ya existentes** (importante, ver §5.2): "tombstones" que **retiran sin borrar**, un GC (recolector de basura), y un prompt de consolidación manual.

---

## 2. Las tres piezas del rediseño

1. **RECALL del orquestador** (leer) — §3.
2. **GATE / freno** (que lo obligatorio pase) — §4.
3. **CONSOLIDADOR** (mantener la memoria limpia y enlazada), ejecutado por **Gitto** — §5. ← **foco de este doc.**

Las tres se complementan: el consolidador mantiene limpio el corpus del que bebe el recall, y el gate fuerza lo que el recall (pasivo) no garantiza.

---

## 3. RECALL del orquestador

**Problema:** no queremos buscar/inyectar en *cada* mensaje del usuario (gasta demasiados tokens).

**Diseño propuesto:** **buscar siempre** (BM25 es gratis al ejecutarse; lo que gasta es *inyectar* texto al contexto) e **inyectar solo si algo destaca de verdad**.

**El gate de inyección — RELATIVO y language-agnostic** (clave: nada de umbral absoluto ni keywords de un idioma, para que funcione en es/en/zh):
- Normalizar las puntuaciones del buscador y **inyectar solo si el mejor recuerdo puntúa ≥ 2× la mediana** de los candidatos (hay un "ganador" claro).
- **Demo real** contra 300 memorias del proyecto: mensajes con chicha dan ratio ~4× (inyecta); *"ok gracias sigue"* da 1.1× (no inyecta nada).

**Fragilidad detectada por el panel** (a corregir): el ratio 2× **falla cuando TODO es relevante** (si hay 8 recuerdos de "auth" y preguntas por auth, la mediana sube y el ratio baja → no inyecta justo cuando más importa). **Fix propuesto:** combinar el ratio con un **suelo absoluto mínimo** + calcular la mediana sobre el **top-5** (no sobre todos) + exigir un **mínimo de corpus** antes de aplicar el ratio.

**Detalles técnicos:**
- Inyectar **después** del mensaje del usuario (no en el system prompt) para no romper el prompt-cache (issue anthropics/claude-code #19909). Moriarty avisa: esto es un trade-off coste-vs-calidad (el recuerdo llega después de que el modelo ya formó intención); nombrarlo como tal.
- **Agujero concreto:** la tokenización del buscador (`recall.py`, regex `[a-zA-Z…]{2,}`) **no parte el chino** (no tiene espacios). Verificar antes de prometer multi-idioma.

---

## 4. GATE / comportamiento (resumen — no es el foco, pero es contexto)

**Hallazgo duro (confirmado por el panel y por nuestro propio código):** las **normas pasivas en contexto NO fuerzan comportamiento**. Prueba: nuestro hook `stop-dod-check.py` lleva un `[MANDATORY] ... NOT optional` y aun así se ignoró (no se revisó el CI). No es desobediencia: es **dilución de atención** — la norma compite con el contexto de la tarea y pierde.

**Conclusión:** para comportamiento obligatorio → **gate que bloquea** o **hacerlo imposible por construcción**. Más texto pasivo no sirve.

**Eje correcto de clasificación:** no "hecho vs comportamiento", sino **COSTE DE FALLO**: fallo barato/recuperable → recall pasivo basta; fallo caro/irreversible (no pushear, no revisar CI, saltarse un paso) → gate.

**Ideas del panel:** *impossible-by-construction* (commit+push atómico → "olvidar pushear" imposible); gates que verifican el **resultado** no solo la llamada; el **CI es asíncrono** → solo un hook de cierre de sesión puede comprobarlo (bloquear el cierre si está rojo); *enrichment hook* (inyectar el estado real para no poder inventarlo); máquina de estados sobre tool-calls con flag persistido entre hooks. Ya existe `hooks/pre-merge-gate.py` como molde (bloquea, falla-cerrado).

---

## 5. EL CONSOLIDADOR (Gitto) — FOCO

### 5.1 La idea (de Bex)

A medida que se escriben memorias (de cualquier tipo), un **contador** sube. Al llegar a un umbral (~30), un **hook avisa al orquestador**; el orquestador dice al usuario *"voy a reordenar mis pensamientos"*, **lanza a Gitto**, Gitto **consolida**, y al volver el orquestador solo **acusa recibo** (sin resumen al usuario).

**Restricción de diseño (Bex):** el disparo va **vía orquestador, NO autónomo** — un hook no puede lanzar un agente y dejarlo trabajando solo en background (eso no existe en la plataforma). El hook avisa; Claude lanza.

**Qué hace Gitto en la pasada:** dedup de remembers duplicados, ordenar/colocar, retirar lo obsoleto, reparar inconsistencias, y (v2) **enlazar** recuerdos relacionados.

### 5.2 Lo que YA tenemos (no partimos de cero)

| Mecanismo | Qué hace | Dónde |
|---|---|---|
| Tombstones (`Resolved-Memo:`, `Resolved-Remember:`, `Resolved-Next:`, `Stale-Blocker:`) | **Retiran** una memoria del recall **sin borrarla** | `lib/constants.py`; aplicado en `lib/recall.py`, `hooks/session-start-boot.py` |
| Dedup por texto normalizado | La primera ocurrencia gana; duplicados exactos se descartan | `lib/recall.py`, `lib/parsing.py` (`normalize`) |
| `git-memory-gc.py` (GC) | Heurísticas (solapamiento de keywords, TTL 30 días, trailer `Resolution:`) — **pero solo para `Next:` y `Blocker:`** | `bin/git-memory-gc.py` |
| **`GC-PROMPT.md`** | Plantilla de consolidación manual que **hoy invoca a YODA** (clasifica KEEP/TOMBSTONE/CONDENSE; aditivo: commit nuevo fusionado + tombstone de los originales) | `skills/unmassk-gitmemory/GC-PROMPT.md` |
| Avisos de boot | Emite `⚠️ GC:` cuando memos > 10, remember(user) > 8, remember(claude) > 8 | `hooks/session-start-boot.py` |
| Regla de oro | **`Decision:` NUNCA se tombstonea** (contrato explícito) | `lib/recall.py` |

### 5.3 Lo que FALTA

1. **Dedup semántica** (hoy solo texto exacto: dos remembers con el mismo significado pero distinta redacción no se fusionan).
2. **GC automático de `Memo:` y `Remember:`** (hoy solo Next/Blocker; para memos/remembers solo existe el flujo manual del GC-PROMPT).
3. **Trailer `Supersedes:`** o encadenamiento "esta memoria reemplaza a aquella".
4. **Score de importancia** (todos los remembers pesan igual; no hay "crítico, nunca expira").

### 5.4 Cómo lo hacen FUERA (con fuentes)

- **Engram** (`github.com/tstockham96/engram`): `engram_consolidate` es **aditivo, no destructivo** (produce conocimiento nuevo a partir de episodios: `consolidated`, `entitiesDiscovered`, `contradictions`, `connectionsFormed`). Detecta contradicciones pero **no las resuelve solo** (las superficia para revisión). El algoritmo exacto de merge **NO CONSTA** en la doc pública.
- **Hindsight / Vectorize** ([blog](https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation)): principio **"recency-wins con invalidación explícita"** — ante dos hechos contradictorios, gana el más reciente pero el viejo **se marca inválido, no se borra** (preserva auditoría). Cuatro mecanismos: Importance, Merge, Decay, Eviction (borrado duro solo por compliance/GDPR).
- **Mem0** ([blog](https://mem0.ai/blog/long-term-memory-ai-agents)): scan periódico; similitud vectorial > 0.85 → merge (promedio de vectores + LLM de resolución de conflictos), **no destructivo**. ~60% menos almacenamiento, +22% precisión.
- **Writer-Critic** ([Medium](https://medium.com/@tejpal.abhyuday/a-framework-agnostic-reference-for-designing-memory-in-any-ai-agent-not-just-travel-bots-0554fe803f59)): un LLM "writer" propone la memoria consolidada; un LLM "critic" valida tres cosas — ¿se perdió info vital?, ¿se inventó algo?, ¿la resolución del conflicto es correcta? Conflicto por fecha (gana el reciente = correcto, no es pérdida de datos). Importancia 5 = nunca expira; baja = caduca en meses.

### 5.5 El consolidador ACOTADO (propuesta a afianzar)

**V1 — SEGURO, determinista, SIN LLM** (Python puro sobre el historial de git, sin riesgo de pérdida):
1. Tombstonear `Remember:` **exactamente duplicados** (`normalize(A)==normalize(B)`), dejando el más reciente.
2. Igual para `Memo:` duplicados del mismo scope.
3. Retirar `Remember:`/`Memo:` **superados por una `Decision:` posterior** que los contradice (heurística de keyword overlap; con confirmación).
4. TTL configurable para `Memo:`/`Remember:` (igual que el TTL de Blocker, extendido).
5. **`--dry-run` obligatorio**: toda pasada devuelve la tabla KEEP/TOMBSTONE/CONDENSE **antes** de tocar nada; se confirma y luego se ejecuta.

**V2 — Avanzado, con LLM o grafo** (más potente, más riesgo de falsos positivos):
1. Dedup por **similitud semántica** (embeddings, umbral ~0.85).
2. **Grafo de entidades** y enlaces ("esto con esto").
3. Patrón **Writer-Critic** para los CONDENSE.
4. **Decay** por score de confianza.

**Reglas de oro (innegociables, v1 y v2):**
- **Nunca borrar** — solo tombstone (retirar marcando).
- **`Decision:` intocable.**
- En conflicto, **gana el más reciente**.

### 5.6 Decisiones ya tomadas (por Bex)

- El consolidador (y todo lo de git/github/memoria) va a **GITTO**, no a Yoda → migrar el GC-PROMPT y **reescribir el prompt de Gitto** (scope muy acotado + ejemplos).
- Disparo **vía orquestador** (contador → hook avisa → Claude lanza Gitto → acuse mínimo, sin resumen al usuario).
- Plan: **1º investigación** (este doc) → **2º reordenar y aplicar** → **3º revisar y revisar**.

---

## 6. Las 3 referencias de memoria que estudiamos

- **Engram** = `github.com/tstockham96/engram` (`engram-sdk`): servidor MCP de memoria para Claude Code; SQLite local, knowledge graph, consolidación, *spreading activation*; tools `engram_recall` (semántico), `engram_surface` (**proactivo**: empuja lo relevante sin que preguntes), `engram_consolidate`, `engram_audit` (cruza CLAUDE.md vs vault). LOCOMO 80% / 776 tokens.
- **Mem0** = `github.com/mem0ai/mem0`: recall por turno (caro), hechos atómicos en system prompt.
- **ByteRover** (antes **Cipher**) = `github.com/campfirein/byterover-cli`: "git para la memoria de IA", *context-tree* versionado con presupuesto fijo de tokens inyectado en el arranque.

---

## 7. Dónde queremos TU opinión (la otra IA)

1. **El prompt de Gitto para el consolidador**: cómo acotarlo bien, qué operaciones exactas debe ejecutar, qué ejemplos meterle para que no se pase de listo ni borre de más. (Gitto es nuestro agente de git/memoria; su prompt actual está en `unmassk-toolkit/agents/gitto.md`.)
2. ¿El V1 determinista (dedup exacto + retirar superados + TTL + dry-run) es **realmente seguro**? ¿Qué se nos escapa?
3. ¿El gate del recall (ratio 2× + suelo + top-5) es robusto, o hay una forma mejor de decidir "inyectar / no inyectar"?
4. La tokenización **ZH** del buscador — ¿cómo lo resolverías?
5. El **flujo del disparador** (contador → orquestador → Gitto) — ¿alguna pega o mejora?
6. ¿Algo grande que no estemos viendo?

---

## 8. Punteros al código (para que puedas leerlo)

- **Prompt actual de Gitto**: `unmassk-toolkit/agents/gitto.md`
- **Consolidación manual actual (a migrar)**: `unmassk-toolkit/skills/unmassk-gitmemory/GC-PROMPT.md`
- **Buscador / recall**: `unmassk-toolkit/lib/recall.py`
- **Tombstones y tipos**: `unmassk-toolkit/lib/constants.py`
- **GC**: `unmassk-toolkit/bin/git-memory-gc.py`
- **Canal de inyección al orquestador** (donde iría el recall): `unmassk-toolkit/hooks/user-prompt-memory-check.py`
- **Molde de gate que bloquea**: `unmassk-toolkit/hooks/pre-merge-gate.py`
- **Boot / volcado de memoria**: `unmassk-toolkit/hooks/session-start-boot.py`

---

## Fuentes externas
- Engram: https://github.com/tstockham96/engram
- Mem0: https://github.com/mem0ai/mem0 · https://mem0.ai/blog/long-term-memory-ai-agents
- ByteRover/Cipher: https://github.com/campfirein/byterover-cli · https://www.byterover.dev/
- Consolidación (Hindsight): https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation
- Writer-Critic / memoria de agentes: https://medium.com/@tejpal.abhyuday/a-framework-agnostic-reference-for-designing-memory-in-any-ai-agent-not-just-travel-bots-0554fe803f59
- Inyección y prompt-cache (placement): https://github.com/anthropics/claude-code/issues/19909
