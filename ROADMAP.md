# Roadmap del toolkit

Qué falta y cómo trabajamos. En cristiano.
Lo ya hecho vive en `CHANGELOG.md` y en la memoria del proyecto (git-memory) — este documento no lo repite.

**Creado: 2026-07-04.**

---

## 👉 Lo siguiente (ya acordado)

**Frente: diseño (`unmassk-design` multi-rama)** (2026-07-14): ✅ **cerrado** — v1.2.1 en remoto. Core + 6 ramas (motion, 3d, scroll, animation-formats, taste, flutter); incluye animación (Three.js/CSS/Flutter/UI) y taste/Emil Kowalski/impeccable. Council 5/5.

**Frente: maker / mundo físico** (acordado 2026-07-14): ✅ **cerrado** (2026-07-14). Dos plugins hermanos en remoto:
  - `unmassk-3d` v1.0.0 — CAD reality-first para impresión (CadQuery/OpenSCAD + Blender MCP, gates escala+watertight, iPhone LiDAR + calibre). Cerberus+Yoda+validator+council.
  - `unmassk-electronics` v1.0.0 — multi-rama (micro ESP32/platformio + Raspberry Pi + robótica), gate "el dispositivo confirma o no está hecho". Cerberus+validator+council.
  - _Follow-ups en memoria (candidatos abajo)._

**Frente: plugin `unmassk-humanizer`** (2026-07-14): ✅ **cerrado** — v1.0.0 en remoto. EN+ES, 3 modos, protect-list y corpus vacíos a propósito. Council 5/5.
  - _Candidato diferido:_ que el corpus vivo escriba a git-memory (auto-ingest fechado, sincroniza entre máquinas).

**Frente: plugin de pentesting** (issue #19): ✅ **cerrado** (2026-07-13). unmassk-pentesting v1.0.0 en remoto.

**Frente: deuda técnica del toolkit** (2026-07-07): ✅ **cerrado completo** (2026-07-09).

_Cerrados: higiene de tests Windows (#50), CI Windows (#51), UnicodeEncodeError cp1252 (#52), unificación de fechas a %at (#55) y cierre del bypass por hard-link (#53, Yoda 110/110, v1.19.0). Viven en CHANGELOG + git-memory._

## 🔧 Lo que queda por hacer

- **Contención real de procesos en Windows (Job Objects)** — el camino al 110 de Security del boot-freshness; es rediseño de ingeniería, no un fleco. _Candidato, sin visto bueno aún._

_Los flecos T3 (#54, #56, #57, #58) que aquí figuraban se cerraron como COMPLETED el 9–13 jul (antes de esta lista): #54/#57/#58 eran defensa contra input malformado/hostil = peso muerto fuera del threat model; #56 (timeline mermaid en grill) hecho. El listado era stale — corregido 2026-07-14._

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

- **Ampliar la skill de vídeo con OpenMontage** — `unmassk-media` ya tiene vídeo (Remotion+ffmpeg), añadir OpenMontage y más herramientas que Bex vaya diciendo. _En investigación._
- **AgentBrowser en vez de Playwright** — ver si aporta algo sobre lo que ya usamos. _En investigación._
- **"Fine skills"** — ver qué es exactamente y si vale para algo. _En investigación._
- **olmOCR 2** — herramienta de OCR, ver si encaja en algún plugin existente. _En investigación._
- **MoneyPrinterTurbo** — sumar a la ampliación de la skill de vídeo (junto a OpenMontage). _En investigación._
- **Castigos por asunción** (#77) — sistema de castigos en memoria fresca: cada asunción cazada por Bex se registra como un check concreto imposible de saltar, encoge al mejorar y gradúa a gate mecánico si reincide. Ataca el banner-blindness del `NO ASUMAS` estático. _En diseño, a afinar antes de construir._
- **`design-gate` / linter de colisiones de frontmatter** — salió del council al cerrar design v1.2.1. Parsear el frontmatter de cada skill, construir el mapa token→dueño, y flaggear en CI cualquier keyword reclamada por dos skills o cualquier `Use when NOT` que nombre a un hermano. Reutilizable en los plugins multi-skill (pentesting 30, compliance 9, media, db). Convierte la desambiguación manual en verificación automática. _Candidato, sin visto bueno aún._
- **Gate "confirmación = read-back por vía independiente" en `unmassk-standards`** — salió del council de electronics. Elevar a criterio de silent-failure de primera clase el patrón que ya convergen 3d ("nunca inventar una medida") y electronics ("el dispositivo confirma o no está hecho"): la confirmación es una lectura por una vía distinta al comando enviado. Con el `serial_verify` de electronics como referencia. _Candidato._
- **Patrón "perfil-por-objetivo" reutilizable** — generalizar el "per-device profile" de electronics (fichero persistido, re-leído cada sesión con las restricciones inmovibles del sistema externo) a deploy targets, APIs inestables, quirks de prod de un cliente. _Candidato._
- **Enganchar tests de `unmassk-3d` y `unmassk-electronics` al CI** — hoy sus suites (validate_mesh, serial_verify) corren a mano; son pip-only (cadquery/trimesh/pyserial), corren en Linux CI. Yoda/council lo marcaron. _Candidato, barato._
- **Sensor-gate helper para la rama `electronics-robotics`** — hoy la rama es solo prosa (capa de comportamiento); un helper con test que asista el read-back de sensor la igualaría a micro. _Candidato, no bloqueante._

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
