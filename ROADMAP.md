# Roadmap del toolkit

Qué falta y cómo trabajamos. En cristiano.
Lo ya hecho vive en `CHANGELOG.md` y en la memoria del proyecto (git-memory) — este documento no lo repite.

**Creado: 2026-07-04.**

---

## 👉 Lo siguiente (ya acordado)

- _Nada acordado pendiente ahora mismo._

## 🔧 Lo que queda por hacer

- _Nada pendiente acordado._ Quedan las ideas congeladas de abajo y los candidatos, que necesitan tu visto bueno antes de tocarse.

## 🧊 Ideas futuras (congeladas a propósito)

La visión grande. NO se toca hasta que la memoria automática lleve un tiempo rodando — no es desprecio, es no construirlo antes de tiempo y hacerlo mal.

- **Mapa neuronal del proyecto (visión grande, congelado hasta que memoria + curador rueden):**
  - Mapa visual que se autorrellena desde la git-memory. Nodos = piezas del proyecto; al pasar el ratón, se expanden en subdecisiones.
  - **Dos dimensiones por nodo:** (1) arquitectura — ¿está decidido/construido?; (2) proceso — ¿está testeado/auditado/seguro? Un nodo puede estar verde en construcción y rojo en seguridad.
  - **Color = estado:** verde (decidido/hecho) · naranja (falta algo) · rojo (sin empezar). El naranja hace visible el protocolo enterprise: lo que falta se ve.
  - **Aristas de proceso:** cada agente pinta su capa (Dante=tests, Argus=seguridad, Cerberus=review, Moriarty=adversarial). El mapa es el tablero de control del crew.
  - **Grafo bicapa:** capa 1 (decisiones/git) sobre capa 2 (código), unidas por nodos-concepto. Puente entre capas = el trailer `Touched:` (que hay que escribir forzado, no voluntario, o el puente tiene agujeros).
  - **Motor:** robar el algoritmo de graphify (cluster/analyze/export sobre nx.Graph genérico) para la capa git; adoptarlo nativo para la capa código. Un motor, dos extractores. God-nodes ponderados por madurez/importancia, no solo por grado.
  - **REGLA DE ORO, innegociable:** el color de cada nodo/arista sale SIEMPRE de un hecho verificable en git (un commit de Argus, un test que pasa), JAMÁS de una autodeclaración. Un mapa que miente es peor que no tener mapa.
  - **Orden de construcción:** recall → curador (teje el grafo en git) → graphify renderiza. No construir la vista antes de que haya grafo que ver.
- **Modo "déjalo trabajando solo" (estilo Ralph):** un agente que muele una tarea grande hasta terminarla sin ti, corrigiéndose con cada intento. Se apoya en el freno duro de cierre (no cantar "hecho" con las pruebas en rojo), que ya está hecho.

## 🟡 Candidatos (necesitan tu visto bueno)

- _Ninguno pendiente ahora mismo._

## 📐 Cómo trabajamos

- **Una cosa a la vez.** Terminarla, vivir con ella, luego la siguiente. Nada nuevo a medias.
- **El roadmap se trabaja en el orden en que está escrito.** Lo siguiente es el primer ítem sin marcar de "Lo siguiente (ya acordado)" o, si está vacío, el primer candidato con tu visto bueno — nunca el que me parezca más interesante en el momento. Si yo quiero saltarme el orden, te lo digo explícito y esperas tu confirmación antes de actuar; si tú quieres saltarlo, lo dices y ya está.
- **Nada se construye sin que tú lo metas aquí.** Una idea a media tarea se anota como candidata, no se abre.
- **Documentar todo en los tres sitios** (GitHub, nosotros, Claude) en el mismo momento.
- **El estado sale de hechos reales** (lo que está en el repo), nunca de lo que yo diga de memoria.
- **Este documento se mantiene ligero.** Lo ya hecho no se repite aquí — vive en `CHANGELOG.md` y en git-memory. Si una sección de "hecho" empieza a crecer, es señal de que hay que limpiarla, no de que hay que seguir apilando.

## Decisiones de fondo ya tomadas

- Seguimos siendo un plugin; no lo convertimos en otra cosa.
- Empezamos por la memoria porque es el cimiento de todo lo demás.
- La búsqueda "por significado" (no por palabra exacta) queda para más adelante, cuando haga falta de verdad.
