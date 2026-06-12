# Roadmap del toolkit

Qué está hecho, qué falta y cómo trabajamos. En cristiano.
El detalle técnico (commits, decisiones) vive en la memoria del proyecto; aquí va lo legible.

**Actualizado: 2026-06-12.**

---

## ✅ Ya hecho y funcionando

- **La memoria automática del proyecto.** El sistema recuerda entre sesiones lo que decidimos, lo que prefieres y cómo trabajar, y se lo pasa solo a los ayudantes (los que programan, revisan, prueban…) cuando los lanzo. Ya no empiezo de cero cada día.
- **Un freno al exceso de memoria guardada (hoy, en la 1.5.0).** El sistema guardaba de más: la misma idea apuntada una y otra vez con otras palabras. Ahora hay dos capas. Una: el recordatorio de cada mensaje pide guardar SOLO si vale de verdad y no existe ya (y si es una corrección, retirar la vieja en vez de apilar). Dos: salta un aviso cuando voy a guardar algo casi idéntico a lo que ya hay. El aviso avisa, no bloquea — para no perder nunca una nota legítima por error.
- **Publicar una versión es un solo comando.** Antes se hacía a mano y se podía olvidar un paso (de hecho pasó). Ahora un único comando sube el número de versión, apunta los cambios, lo guarda, lo manda a tus máquinas y verifica que llegó — y se niega a publicar si algo está a medias. Construido ayer y estrenado de verdad hoy al publicar la 1.5.0.
- **Documentación en tres sitios a la vez.** Todo lo nuevo queda escrito para quien visita el repo en GitHub, para nosotros, y para que el propio Claude lo sepa — con una norma para que se haga siempre.
- **Dos formas de programar:** una rápida para prototipos y otra "primero las pruebas" para cosas serias. Yo elijo cuál según la tarea.
- **Cuatro rutinas para situaciones concretas.** Se activan solas según el momento: arrancar, retomar o escanear un proyecto —si es ajeno, aprende leyéndolo, sin tocar su código ni su historial—; interrogarme a fondo antes de construir algo dudoso o con riesgo; un "consejo" de cinco voces con criterios opuestos para decisiones donde equivocarse duele (es caro, solo cuando toca de verdad); y cerrar la sesión ordenada, volcando lo decidido y dejando escrito por dónde seguir.
- **Limpieza y arreglos:** borré ficheros muertos, arreglé un fallo que reventaba las pruebas, y repasé todo el repo buscando cosas que existían pero que Claude no sabía usar — y las documenté.
- **El freno duro: no se puede cantar "hecho" con las pruebas en rojo (hoy).** Antes, al cerrar, había un aviso que se podía ignorar. Ahora, si configuras qué pruebas correr, el sistema las corre al cerrar y, si fallan, **bloquea** el cierre — no deja dar nada por terminado hasta que estén en verde. Si el propio freno peta, te deja pasar (no te atrapa). Es el cimiento que hará seguro el modo "déjalo trabajando solo".
- **El número de versión se pone al día solo (hoy).** Cuando actualizas el plugin en una máquina, el marcador de versión de tu proyecto se sincroniza solo a la nueva versión — antes se podía quedar desfasado y no se arreglaba por sí mismo. Compara versiones de verdad (entiende que la 1.10 es más nueva que la 1.9, donde un texto a secas se equivocaría), nunca rebaja la versión, y si el marcador falta o está corrupto no hace nada raro (no se mete en un bucle).

## 👉 Lo siguiente (ya acordado)

- _Nada acordado pendiente ahora mismo._ La **1.5.0 ya está publicada** y llega a cada ordenador al hacer `/plugin update`. El consolidador de memoria y el prompt de Gitto están **parados a propósito** (necesitan juicio, otra liga); lo demás está en la lista de abajo.

## 🔧 Lo que queda por hacer

1. **Que la memoria relevante me llegue a MÍ (Claude) en cada mensaje.** Hoy solo tengo el volcado completo al arrancar la sesión; los ayudantes sí reciben memoria fresca al lanzarlos, pero la conversación principal no. Lo que falta: que cuando escribas algo (por ejemplo "pipeline"), lo más relevante de la memoria sobre eso me aparezca **a mí** automáticamente, para no repetir errores que ya están anotados. Es el recall del orquestador, ya marcado como prioridad. Único cuidado al construirlo: que no llene demasiado la conversación (buscar siempre, mostrarme solo lo que de verdad destaca).

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
- **Arranque de proyecto más sólido:** una guía formal de calidad al empezar un proyecto nuevo, y que Claude elija la herramienta correcta de forma fiable.
- **Modo "déjalo trabajando solo" (estilo Ralph):** un agente que muele una tarea grande hasta terminarla sin ti, corrigiéndose con cada intento. Se apoya en el freno duro de cierre (no cantar "hecho" con las pruebas en rojo), que ya está hecho.

## 🟡 Candidatos (necesitan tu visto bueno)

- **Mirar "Spec Kit"** (la herramienta nueva que quieres ver) y decidir si sustituye o complementa la plantilla de PRD que ya tenemos.
- **Una norma para que yo siga el roadmap en orden**, punto por punto, en vez de ir saltando.

## 📐 Cómo trabajamos

- **Una cosa a la vez.** Terminarla, vivir con ella, luego la siguiente. Nada nuevo a medias.
- **Nada se construye sin que tú lo metas aquí.** Una idea a media tarea se anota como candidata, no se abre.
- **Documentar todo en los tres sitios** (GitHub, nosotros, Claude) en el mismo momento.
- **El estado sale de hechos reales** (lo que está en el repo), nunca de lo que yo diga de memoria.

## Decisiones de fondo ya tomadas

- Seguimos siendo un plugin; no lo convertimos en otra cosa.
- Empezamos por la memoria porque es el cimiento de todo lo demás.
- La búsqueda "por significado" (no por palabra exacta) queda para más adelante, cuando haga falta de verdad.
