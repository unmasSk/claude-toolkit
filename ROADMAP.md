# Roadmap del toolkit

Qué falta y cómo trabajamos. En cristiano.
Lo ya hecho vive en `CHANGELOG.md` y en la memoria del proyecto (git-memory) — este documento no lo repite.

**Creado: 2026-07-04.**

---

## 👉 Lo siguiente (ya acordado)

**Frente: plugin `unmassk-humanizer`** (acordado 2026-07-14): ✅ **v1.0.0 construido** (2026-07-14). Skill para que el texto escrito no suene a IA, EN+ES, con 3 modos (rewrite/detect/ingest), método de 3 pasadas, voces, protect-list y corpus vivo. Fusión de blader/humanizer + lguz/humanize-writing + kjmagnan1s/anti-slop (MIT) + capa español propia. Validado por council (5/5). protect-list y corpus se dejan vacíos a propósito: se llenan con el uso. Pendiente de cierre formal: bump/release.
  - _Candidato diferido:_ que el corpus vivo escriba a git-memory (auto-ingest fechado, sincroniza entre máquinas, aprende de la voz del dueño). Idea del council; se construye cuando sea menester.

**Frente: plugin de pentesting** (issue #19): ✅ **cerrado** (2026-07-13). unmassk-pentesting v1.0.0 construido, validado y en remoto. Follow-ups menores en memoria.

**Frente: deuda técnica del toolkit** (acordado 2026-07-07): ✅ **cerrado completo** (2026-07-09).

_Cerrados: higiene de tests Windows (#50), CI Windows (#51), UnicodeEncodeError cp1252 (#52), unificación de fechas a %at (#55) y cierre del bypass por hard-link (#53, Yoda 110/110, v1.19.0). Viven en CHANGELOG + git-memory._

## 🔧 Lo que queda por hacer

- **Frente después del de diseño (ya acordado, 2026-07-14):** plugins para el mundo físico/maker — modelado, impresión 3D y electrónica/robótica. Objetivo: diseñar piezas, sacarlas por impresora 3D, y montar electrónica tipo Raspberry/ESP32 para trastear ("hacer cositas"). Se arranca al cerrar el frente de diseño.

  _Investigación (2026-07-14, contrastada — corrige a una IA previa que iba desactualizada):_
  - **Piezas funcionales → CAD por código, NO Blender.** Blender es modelado de mallas (arte); para cajas/piezas funcionales imprimibles quieres **CAD paramétrico**: **OpenSCAD / CadQuery / build123d** son código puro → deterministas, diffables, testeables → encajan con nuestra filosofía de loop+gates. Mejor candidato a skill propia (`unmassk-cad`) que BlenderMCP. La otra IA ni lo mencionó.
  - **Electrónica → `platformio-mcp` es la incorporación más sólida.** Capa de ejecución hardware agent-first: descubrimiento de placas, build, flash, monitor serie, diagnóstico estructurado, auditorías de GPIO, y **verificación flash+monitor con aserciones runtime** (ej: `agent-flash-monitor-verify --expect-all BOOT_OK --reject-patterns "Guru Meditation,Brownout,WDT reset"`). Es LITERALMENTE nuestro patrón de gates (Cerberus/Argus) pero contra hardware físico: el agente no dice "done" hasta que el firmware bootea y el serial lo confirma. ~1000 placas, 30+ plataformas (ESP32-S3, RP2040, STM32, nRF52840). npm, instalación trivial. Complementos: bridge MCP a Cortex-Debug (breakpoints, leer/escribir registros ARM en vivo) y skills de debug ESP32 (Guru Meditation, stack overflows FreeRTOS, I2C/SPI/UART) — pero el ecosistema de skills embedded es escaso (~docena).
  - **Blender MCP** (ahora hay uno OFICIAL del equipo Blender + "Claude for Creative Work" de Anthropic, 9 conectores) → válido solo si se quiere **3D visual**, no para piezas funcionales. Cuidado: `execute_blender_code` ejecuta Python arbitrario + telemetría anónima por defecto; el de ahujasid sin guardas contra borrado/exfiltración → usar en VM.
  - **Sigue siendo cierto:** nadie conecta los cables por ti y "dispositivo autónomo completo" no existe. Pero el loop **código → flash → verificación serie → corrección SÍ es cerrable hoy**.
  - _Prioridad de incorporación:_ (1) platformio-mcp; (2) CAD por código (`unmassk-cad`); (3) Blender MCP oficial (opcional, 3D visual, con guardas).
- Candidatos con visto bueno.
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
- **Ampliar `unmassk-design` con skills de animación** — Three.js, "animation designer", Flutter animations, CSS animations, UI-animations. _En investigación._
- **AgentBrowser en vez de Playwright** — ver si aporta algo sobre lo que ya usamos. _En investigación._
- **"Fine skills"** — ver qué es exactamente y si vale para algo. _En investigación._
- **olmOCR 2** — herramienta de OCR, ver si encaja en algún plugin existente. _En investigación._
- **MoneyPrinterTurbo** — sumar a la ampliación de la skill de vídeo (junto a OpenMontage). _En investigación._
- **Sumar a `unmassk-design`: Emil Kowalski, "impeccable", "taste-skill"** — _En investigación._
- **Castigos por asunción** (#77) — sistema de castigos en memoria fresca: cada asunción cazada por Bex se registra como un check concreto imposible de saltar, encoge al mejorar y gradúa a gate mecánico si reincide. Ataca el banner-blindness del `NO ASUMAS` estático. _En diseño, a afinar antes de construir._

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
