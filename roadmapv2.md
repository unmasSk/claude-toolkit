# Roadmap del toolkit

Qué está hecho, qué falta y cómo trabajamos. En cristiano.
El detalle técnico (commits, decisiones) vive en la memoria del proyecto; aquí va lo legible.

**Actualizado: 2026-06-10.**

---

## ✅ Ya hecho y funcionando

- **La memoria automática del proyecto.** El sistema recuerda entre sesiones lo que decidimos, lo que prefieres y cómo trabajar, y se lo pasa solo a los ayudantes (los que programan, revisan, prueban…) cuando los lanzo. Ya no empiezo de cero cada día.
- **Un freno al exceso de memoria guardada (hoy, en la 1.5.0).** El sistema guardaba de más: la misma idea apuntada una y otra vez con otras palabras. Ahora hay dos capas. Una: el recordatorio de cada mensaje pide guardar SOLO si vale de verdad y no existe ya (y si es una corrección, retirar la vieja en vez de apilar). Dos: salta un aviso cuando voy a guardar algo casi idéntico a lo que ya hay. El aviso avisa, no bloquea — para no perder nunca una nota legítima por error.
- **Publicar una versión es un solo comando.** Antes se hacía a mano y se podía olvidar un paso (de hecho pasó). Ahora un único comando sube el número de versión, apunta los cambios, lo guarda, lo manda a tus máquinas y verifica que llegó — y se niega a publicar si algo está a medias. Construido ayer y estrenado de verdad hoy al publicar la 1.5.0.
- **Documentación en tres sitios a la vez.** Todo lo nuevo queda escrito para quien visita el repo en GitHub, para nosotros, y para que el propio Claude lo sepa — con una norma para que se haga siempre.
- **Dos formas de programar:** una rápida para prototipos y otra "primero las pruebas" para cosas serias. Yo elijo cuál según la tarea.
- **Cuatro rutinas para situaciones concretas.** Se activan solas según el momento: arrancar, retomar o escanear un proyecto —si es ajeno, aprende leyéndolo, sin tocar su código ni su historial—; interrogarme a fondo antes de construir algo dudoso o con riesgo; un "consejo" de cinco voces con criterios opuestos para decisiones donde equivocarse duele (es caro, solo cuando toca de verdad); y cerrar la sesión ordenada, volcando lo decidido y dejando escrito por dónde seguir.
- **Limpieza y arreglos:** borré ficheros muertos, arreglé un fallo que reventaba las pruebas, y repasé todo el repo buscando cosas que existían pero que Claude no sabía usar — y las documenté.

## 👉 Lo siguiente (ya acordado)

- _Nada acordado pendiente ahora mismo._ La **1.5.0 ya está publicada** y llega a cada ordenador al hacer `/plugin update`. El consolidador de memoria y el prompt de Gitto están **parados a propósito** (necesitan juicio, otra liga); lo demás está en la lista de abajo.

## 🔧 Lo que queda por hacer

1. **Que la memoria automática también te llegue a TI.** Hoy se la paso a los ayudantes, pero a nuestra conversación principal todavía no. Falta engancharlo. Aparcado a propósito: antes hay que medir que no llene demasiado la conversación.
2. **Un freno que impida cantar "hecho" cuando no lo está.** Ahora mismo se puede dar algo por terminado sin haberlo integrado del todo. Queremos un control automático que no deje.
3. **Una lista de comprobación obligatoria para el que programa.** Antes de que el ayudante que escribe código diga "he acabado", que tenga que pasar sí o sí unas comprobaciones (que las pruebas pasen, etc.). Hoy es una lista que se puede saltar; queremos que no se pueda. **Esto es clave:** es el cimiento que haría posible y seguro el "modo trabajar solo" de abajo — sin este freno, un agente en bucle solo acumula basura; con él, se autocorrige.
4. **Obligar a apuntar la versión y los cambios al integrar.** Para que nunca se publique algo sin actualizar el número de versión y el historial, en vez de fiarlo a que alguien se acuerde.
5. **Cerrar un aviso viejo en GitHub.** Hay un aviso (el #48) que ya está resuelto —el código problemático se borró hace tiempo— pero quedó abierto. Solo falta cerrarlo con una nota.

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
- **Modo "déjalo trabajando solo" (estilo Ralph):** un agente que muele una tarea grande hasta terminarla sin ti, corrigiéndose con cada intento. Depende del freno duro del punto 3 — sin eso, no es seguro.

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
