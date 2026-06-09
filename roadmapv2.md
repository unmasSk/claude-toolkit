# Roadmap del toolkit

Qué está hecho, qué falta y cómo trabajamos. En cristiano.
El detalle técnico (commits, decisiones) vive en la memoria del proyecto; aquí va lo legible.

**Actualizado: 2026-06-09.**

---

## ✅ Ya hecho y funcionando

- **La memoria automática del proyecto.** El sistema recuerda entre sesiones lo que decidimos, lo que prefieres y cómo trabajar, y se lo pasa solo a los ayudantes (los que programan, revisan, prueban…) cuando los lanzo. Ya no empiezo de cero cada día.
- **Publicar una versión es un solo comando.** Antes se hacía a mano y se podía olvidar un paso (de hecho pasó). Ahora un único comando sube el número de versión, apunta los cambios, lo guarda, lo manda a tus máquinas y verifica que llegó — y se niega a publicar si algo está a medias. Construido y probado a fondo hoy.
- **Documentación en tres sitios a la vez.** Todo lo nuevo queda escrito para quien visita el repo en GitHub, para nosotros, y para que el propio Claude lo sepa — con una norma para que se haga siempre.
- **Dos formas de programar:** una rápida para prototipos y otra "primero las pruebas" para cosas serias. Yo elijo cuál según la tarea.
- **Limpieza y arreglos:** borré ficheros muertos, arreglé un fallo que reventaba las pruebas, y repasé todo el repo buscando cosas que existían pero que Claude no sabía usar — y las documenté.

## 👉 Lo siguiente (ya acordado)

- **Publicar la versión nueva.** Todo lo de hoy está guardado pero aún no ha llegado a tus 4 ordenadores. Hace falta reiniciar y lanzar el comando de publicar. Sería, además, la primera vez que usamos de verdad el comando que construimos hoy.

## 🔧 Lo que queda por hacer

1. **Que la memoria automática también te llegue a TI.** Hoy se la paso a los ayudantes, pero a nuestra conversación principal todavía no. Falta engancharlo. Aparcado a propósito: antes hay que medir que no llene demasiado la conversación.
2. **Un freno que impida cantar "hecho" cuando no lo está.** Ahora mismo se puede dar algo por terminado sin haberlo integrado del todo. Queremos un control automático que no deje.
3. **Una lista de comprobación obligatoria para el que programa.** Antes de que el ayudante que escribe código diga "he acabado", que tenga que pasar sí o sí unas comprobaciones (que las pruebas pasen, etc.). Hoy es una lista que se puede saltar; queremos que no se pueda. **Esto es clave:** es el cimiento que haría posible y seguro el "modo trabajar solo" de abajo — sin este freno, un agente en bucle solo acumula basura; con él, se autocorrige.
4. **Obligar a apuntar la versión y los cambios al integrar.** Para que nunca se publique algo sin actualizar el número de versión y el historial, en vez de fiarlo a que alguien se acuerde.
5. **Cerrar un aviso viejo en GitHub.** Hay un aviso (el #48) que ya está resuelto —el código problemático se borró hace tiempo— pero quedó abierto. Solo falta cerrarlo con una nota.

## 🧊 Ideas futuras (congeladas a propósito)

La visión grande. NO se toca hasta que la memoria automática lleve un tiempo rodando — no es desprecio, es no construirlo antes de tiempo y hacerlo mal.

- **El "cerebro" de la memoria:** que la memoria se organice sola, conecte ideas relacionadas, distinga lo maduro de lo que es un borrador, y se pueda ver como un mapa visual del proyecto.
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
