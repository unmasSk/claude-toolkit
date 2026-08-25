# Plan — que activar la memoria en un proyecto sea automático

**Abierto:** 2026-08-06, a petición del propietario · **Estado:** COMPLETADO — issue #82 cerrada en dos tandas (1.29.0 publicada, comentario 1; los dos puntos restantes cerrados y verificados ejecutando, comentario 2). Los 14 puntos de este plan están hechos. D-002 documenta la decisión.

## Qué se busca, en una frase

Que el propietario **entre en cualquiera de sus proyectos, diga «buenos días», y el sistema le cuente lo que hay que hacer.** Sin instalar nada a mano, sin dar de alta zonas antes de poder guardar la primera nota, sin escribir ficheros de configuración, y sin descubrir a base de rechazos qué le falta.

Hoy no es así: son **nueve pasos**, dos de ellos rechazos y uno un fichero escrito a mano, y **ninguno lo pide el sistema**.

## Qué queda FUERA de este plan

Lo más importante de este documento, porque es lo que impide que el plan se lo trague todo:

- **La destilación de la memoria vieja** (fase 8). Es una pasada propia, con su protocolo escrito, y va después.
- **La compactación de la memoria de cada agente.** Igual: protocolo escrito, pasada aparte.
- **Yoda.** Descartado por el propietario para esta obra.
- **Los siete comandos de git que borran trabajo** (`reset`, `stash`, `checkout`…). Decidido el 2026-08-05: se quedan como están.
- **Las 70 notas basura** del test que se descontroló. Decidido: no se tocan.
- **La secuencia de revisores** (Cerberus, Argus, Moriarty) sobre este trabajo. Descartada expresamente por el propietario.
- **Reescribir el historial** de cualquier rama.

## De dónde sale

Un barrido del 2026-08-05 con tres agentes, cada uno ejecutando escenarios reales en repositorios de mentira: proyecto nuevo desde cero, proyecto con memoria del sistema anterior, clon limpio en otra máquina, y el camino real de un proyecto en marcha.

Dato que lo enmarca: de los **14 repositorios del propietario, solo uno tiene memoria**, y **ninguno tiene `config.json`**.

## El orden de trabajo

### Hecho y probado ejecutándolo

1. **El arranque obliga a cargar las dos skills antes de responder.** La orden va delante del enlace al informe. Antes solo lo decía el `CLAUDE.md`, y se ignoró en una sesión real.
2. **El vigilante de cada mensaje nombra las dos skills**, no solo el core.
3. **El candado de zonas deja de versionarse**, en todos los proyectos, vía el `.gitignore` del instalador.
4. **`gitmem work` sabe guardar un borrado** (`git add --all` acotado a las rutas dadas).
5. **Las reglas viajan en git.** `rules.md` iba dentro del commit de la regla; antes se quedaba fuera y se perdía al clonar.
6. **Las zonas viajan en git.** `zones.json` era el único fichero de memoria que el sistema escribía y no commiteaba jamás: al clonar en otra máquina desaparecían la descripción y los alias, y el arranque lo daba todo en verde.
7. **El instalador puede ejecutarse.** Su puerta preguntaba por una marca que otro hook escribe en cada arranque, así que la respuesta era siempre «ya está instalado»: **no podía dispararse nunca, en ningún proyecto.**
8. **`gitmem rule list` deja de guardar una regla que dice «list»** y de dejar su commit para siempre.
9. **El arranque deja de decir «manifest al día»** en un proyecto que no está instalado.

### Hecho (issue #82, comentario 1 — publicado en 1.29.0)

10. **La instalación deja el proyecto entero puesto**, respetando sus cinco fases:
    - `gitmem` en el PATH, con un lanzador que sobrevive a los cambios de versión. — **hecho**
    - Los ocho índices sembrados al instalar, no al primer rechazo. — **hecho**
    - `config.json` **deducido** del propio repositorio: una sola rama es `trunk`. Sin él, **11 de los 14 repositorios rechazan el primer commit del día**. — **hecho**
    - El médico del sistema pasa a auscultar la memoria, que hoy no mira. — **hecho**
11. **Un proyecto con memoria anterior se presenta como si estuviera vacío.** — **hecho**: el arranque avisa ahora de memoria sin montar y de memoria anterior sin destilar (los "dos avisos nuevos" del comentario de cierre de la 1.29.0).
12. **El arranque no distingue «sin memoria» de «memoria sana y vacía».** — **hecho**, mismo aviso que el punto 11.

### Hecho (issue #82, comentario 2 — cerrado y verificado ejecutando)

13. **La aduana decide si está encendida mirando el proyecto de la sesión**, no el directorio del comando. — **hecho**: `_find_commit_creating_statement` devuelve ahora la posición de la sentencia del commit y la resolución del directorio se recorta ahí; un `cd` posterior ya no pisa el directorio real del commit.
14. **El protocolo de proyecto nuevo no menciona las zonas.** — **hecho**: START las crea antes de la fase A, SCAN las nombra a partir del propio escaneo y las pasa por el usuario antes de sembrar.

De propina en el mismo cierre: un commit escrito con un separador pegado sin espacio (`;`, `&&`, `||`, `|`) no se reconocía y pasaba sin evaluación — cerrado con el mismo tokenizador para todo el fichero. 63 tests en el hook, todos verdes.

## Cómo se sabe que está terminado

En un proyecto nuevo, recién clonado y sin tocar: se abre sesión, se dice «buenos días», y el sistema responde con el menú del día **sin que el usuario ejecute un solo comando**. La primera nota se guarda sin un rechazo. **Confirmado: issue #82 cerrada.**
