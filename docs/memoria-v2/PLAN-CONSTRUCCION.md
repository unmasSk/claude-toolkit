# Plan de construcción — Sistema de Memoria v2

**Fecha:** 2026-08-01 · **Estado:** propuesta de plan, sin aprobar
**Especificación de referencia:** `docs/spec-sistema-memoria-v2.md` (cerrada, revisada por council)

Este documento es el plan. La especificación es el qué; esto es el en qué orden y con qué se verifica cada paso.

---

## 0. Las tres restricciones que mandan sobre el orden

Todo el orden de abajo sale de estas tres, no de gustos.

**A — El v1 sigue vivo y escribiendo durante toda la construcción.** No se congela el día uno: se congela el día del corte, proyecto a proyecto. Cualquier pieza que rompa al v1 antes de ese día está mal colocada en el plan.

**B — Los hooks se ejecutan desde la caché del plugin, no desde el repo.** Medido esta noche: la caché es una foto fijada por SHA y solo se mueve publicando versión + `claude plugin update` + reinicio. Consecuencia dura: **una pieza que sea hook no se puede desarrollar iterando**, porque cada cambio exige un ciclo de publicación. Todo lo que pueda ser script invocado por ruta se construye antes que lo que tenga que ser hook.

**C — Los prompts de los agentes van al final.** Un agente al que se le dice que consuma vallas cuando aún no hay vallas queda peor que como está. Los prompts se tocan en el corte de cada proyecto.

---

## 1. Dónde vive el código

**Plugin propio en el mismo repo**, hermano de los que ya existen (`unmassk-db`, `unmassk-ops`, `unmassk-design`…):

```
unmassk-memory/                    ← el v2, plugin nuevo
  .claude-plugin/plugin.json
  bin/            generador, búsqueda, regeneración de índices
  lib/            validador (una sola pieza, ver §3), formato, índices, informe
  hooks/          la aduana (última fase)
  skills/         la skill de memoria v2
  tests/
unmassk-toolkit/                   ← el v1, CONGELADO, no se toca
```

**Por qué plugin aparte y no una carpeta dentro del toolkit:** los dos sistemas tienen que poder correr a la vez y la caché sirve el plugin entero. Mezclados, no hay forma de saber cuál se ejecuta — que es exactamente el incidente del 2026-08-01 (seis hooks divergentes durante días). Separados, el v2 se instala, se prueba y se desinstala sin tocar al v1.

**Y los índices del proyecto** (`.claude/project-memory/`, los ocho ficheros) son del proyecto, no del plugin. Nacen vacíos en la fase 3.

---

## 2. Fase 0 — El bucle de desarrollo (bloqueante para todo lo demás)

**Problema:** ver restricción B. Si la primera pieza que construimos es un hook, cada iteración cuesta una publicación de versión y un reinicio.

**Solución, y es la que decide toda la arquitectura del plan:** el 90% del sistema **no necesita ser hook**. El generador, el validador, la búsqueda, el informe y los índices son scripts invocados por ruta. Se desarrollan y se prueban ejecutándolos directamente desde el repo, sin caché de por medio.

Solo hay **una** pieza que obligatoriamente es hook: la aduana (necesita interceptar y rechazar). Por eso va la última.

**Entregable de esta fase:** ninguno de código. Es una decisión de arquitectura del plan, y queda registrada aquí para que nadie la reabra a mitad.

**Verificación:** que el primer script de la fase 2 se pueda ejecutar con `python3 unmassk-memory/bin/<script>.py` desde el repo y funcione. Si eso no se cumple, el plan está mal montado.

---

## 3. Fase 1 — El validador, pieza única

**Qué:** una sola librería que sabe qué es válido: zonas, tipos, campos, keys marcadoras, formato del titular.

**Por qué primero y por qué UNA:** P3 dice que la lista de lo válido vive en la misma pieza que valida. Si la aduana valida por su cuenta y el generador valida por la suya, el día uno hay dos verdades — y ese es el fallo `Sources:` reproducido antes de empezar. **El generador y la aduana llaman a la misma función.**

**Contenido:**
- `zones.json` por proyecto, **sembrado**, no inventado: se destila del glossary cache del v1 más la estructura real de carpetas (materia prima ya preparada para monyma y omawa). Se acepta sucio y se limpia con el uso.
- Lista negra (`claude`, `user`, `session`, `project`, `workflow`) y palabra ilegal (`audit`).
- Alias.
- Los siete tipos y sus campos obligatorios.
- Las cuatro keys marcadoras con su normalización.

**Verificación:** tests que prueben que un titular bien formado pasa, que una zona inexistente no pasa, que un alias resuelve, que una zona de la lista negra devuelve el mensaje de rules, y que `audit` devuelve la disyuntiva. Sin tests de atacante: el modelo de amenaza es el sistema contra sí mismo.

---

## 4. Fase 2 — El generador

**Qué:** el script que escribe una nota: titular con ID asignado leyendo el índice, cuerpo con sus campos, `Touched:` desde el diff en commits de trabajo, y **la línea del índice en el mismo commit**.

**Contenido:**
- Asignación de ID por tipo, leyendo el índice.
- Escritura del commit (emojis heredados, P10).
- Actualización de la línea de índice **en el mismo acto** (un acto, un commit).
- `close <ID> "motivo"` → commit de cierre + línea a ARCHIVED.md.
- `--replaces` → puntero + retirada de la línea vieja a ARCHIVED.md.
- **Propagación del error real de git**, nunca un mensaje vacío (defecto reproducido del v1).
- Todos los flags por adelantado (P5): `--stops`, `--origin`, `--replaces`.

**Depende de:** fase 1 (llama al validador).

**Verificación:** crear las siete clases de nota de verdad en una rama descartable, comprobar que el índice cuadra con git, y que `close` y `--replaces` mueven la línea a ARCHIVED.md. Al terminar, borrar la rama.

**Hito real:** aquí ya se pueden escribir notas v2 a mano. El sistema existe aunque no lo lea nadie todavía.

---

## 5. Fase 3 — Índices y arranque (primer entregable visible)

**Qué:** los ocho ficheros de `.claude/project-memory/`, el menú del día en el arranque, y el comando de regeneración total desde git.

**Contenido:**
- Los ocho índices, escritos solo por el script.
- Render del arranque: Next+Context, todos los B, todas las R, recuentos, avisos.
- Chequeo de coherencia índices↔git (✓/⚠) y comando de regeneración.
- Chequeo de IDs duplicados.
- **Todos los ceros visibles** (P6): "0 vallas", "0 bloqueantes". Un contador que no aparece es un fallo.

**Depende de:** fase 2.

**Verificación:** con la memoria vacía, el arranque enseña ceros explícitos. Con tres notas escritas a mano, enseña tres. Se corrompe un índice a propósito y el arranque lo dice.

**Hito real:** primer día en que se ve algo por pantalla. Y es el momento de enseñárselo al propietario antes de seguir.

---

## 6. Fase 4 — La lectura: el informe

**Qué:** el producto único de búsqueda — estado completo de una zona.

**Contenido:**
- Cuatro entradas: por ID, por zona, por palabra, por fichero.
- Agrupación en racimos por punteros (`Origin`/`Replaces`), determinista.
- Vigente por defecto, `--todo` para la historia.
- Restricciones arriba y literales; Q vivas al final.
- Zona sin notas → "cero notas" en alto.

**Depende de:** fases 2 y 3.

**Verificación:** montar a mano un racimo de tres notas encadenadas y comprobar que el informe las pliega en una. Una nota sin punteros sale como grupo de una — y eso es correcto, es la señal de que nadie está enlazando.

---

## 7. Fase 5 — El reparto por oficio y LA PRUEBA

**Qué:** cambiar lo que viaja por el tubo de inyección a subagentes. El tubo ya existe y ya llega a los nueve (verificado en `hooks/pre-task-recall.py`); solo cambia el contenido.

**Pero se hace en dos tiempos, y el primero es la prueba:**

**5a — Solo Ultron, una semana.** Se le inyectan las R de la zona. Y su prompt gana **una línea**: si una R le cambió lo que iba a hacer, lo dice en su informe ("R-007 me hizo apuntar los tests a staging"). Sin esa línea la prueba no concluye nada: una valla que funciona sería indistinguible de una ignorada.

**5b — El resto de roles**, solo si 5a da señal: Dante (R + I), House (I), Argus/Cerberus (I abiertas + keys), Moriarty (R + I), Yoda (D vigente + R), Bilbo (informe completo).

**Depende de:** fase 4, y de que existan unas cuantas R reales (escritas a mano con el generador; no hace falta esperar a la destilación).

**Verificación:** es la propia prueba. Si en una semana ninguna valla cambió nada observable, **no se abandona nada**: lo que dice es que antes de extender el reparto a los otros ocho hay que atacar por qué se ignora lo inyectado. Es mucho mejor saberlo en la fase 5 que con todo construido.

**Sobre el listón, dicho por el propietario y con razón:** el v1 no es un punto de partida neutro — está medido que no funciona (1 lectura por cada 20 escrituras; 11 de 23 sesiones sin leer nada). Casi cualquier cosa que se lea más ya gana, así que el diseño no tiene que demostrar excelencia para justificarse. El único escenario en que el v2 sería peor que el v1 es estrecho y hay que tenerlo a la vista: que tampoco se lea **y además** cobre la fricción de la aduana en cada guardado, que es un coste que el v1 no tiene. Mismo resultado, más peaje. Esa es la única forma de perder, y es lo que esta prueba vigila.

---

## 8. Fase 6 — La aduana (la única pieza que es hook)

**Qué:** el hook PreToolUse que valida antes de dejar pasar, con el rechazo informativo.

**Va aquí y no antes por dos razones:** es la única pieza que obliga a ciclo de publicación (restricción B), y es la que rompería al v1 el día que se encienda (restricción A).

**Contenido:**
- Llama al validador de la fase 1. No duplica lógica.
- Las nueve validaciones de la especificación.
- **Interruptor: nace apagada.** Flag o variable de entorno; se enciende proyecto a proyecto en el corte.
- `wip` exento, a propósito.

**Verificación:** con la aduana apagada, el v1 sigue commiteando sin problema — se prueba en vivo. Con la aduana encendida en un proyecto de pruebas, un commit sin zonas rebota con el mensaje correcto y el relanzamiento con los flags pasa a la primera.

---

## 9. Fase 7 — Los agentes y las skills

**Qué:** lo que hay que reescribir, y solo ahora que hay algo que consumir.

- **Gitto:** pierde el modo consolidador periódico, gana el modo adaptador único.
- **House:** el pie estructurado de su informe (causa raíz + titular y zonas propuestos para la I).
- **Bilbo:** el zoom-out como paso obligatorio (mapa de módulos, llamantes, radio de daño).
- **Ultron:** la línea de la prueba (ya introducida en 5a).
- **close-session:** los cuatro renglones nuevos — escribir el Context/Next, actualizar la issue-plan, podar vallas, dar de alta bloqueantes.
- **La skill de memoria v2:** cómo se escribe una nota, con los flags por delante para que el coste normal sea un comando y cero rechazos.
- **`unmassk-bug-protocol`:** skill nueva. Va **después** del generador y la aduana porque commitea en formato nuevo. Sus cinco puntos internos se resuelven al redactarla.

**Verificación:** un ciclo real de cada protocolo, no una lectura del texto.

---

## 10. Fase 8 — La destilación, proyecto a proyecto

**Qué:** Gitto destila la memoria v1 a formato nuevo, una vez, de forma aditiva.

**Por proyecto, y con dos cosas decididas antes de empezar cada uno:**
- **La fecha de corte.** Lo que el v1 escribió hasta ese día entra en la destilación; desde ese día, solo formato nuevo. Sin fecha explícita, las notas de las semanas de construcción no las destila nadie.
- **El encendido de la aduana** en ese proyecto, el mismo día.

**Orden de proyectos:** primero `claude-toolkit` (es donde se construye y donde duele menos equivocarse), después uno real.

**Verificación:** por pasadas con tope, "en la duda, proponer al propietario", y `Origin:` obligatorio citando los hashes v1 de los que destila.

---

## 11. Fase 9 — Apagar el v1

Solo cuando un proyecto esté destilado y la aduana encendida. El v1 queda como archivo muerto consultable: **cero migración, cero reescritura**.

---

## 12. Resumen del orden y sus dependencias

| Fase | Pieza | Depende de | Se puede enseñar |
|---|---|---|---|
| 0 | Decisión de arquitectura: todo script salvo la aduana | — | no |
| 1 | Validador único + zones.json sembrado | 0 | no |
| 2 | Generador | 1 | notas reales en una rama |
| 3 | Índices + arranque | 2 | **sí — primer entregable visible** |
| 4 | El informe | 2, 3 | sí |
| 5a | Reparto a Ultron + **LA PRUEBA** | 4 | **sí — y es el gate del plan** |
| 5b | Reparto al resto | 5a con señal | sí |
| 6 | La aduana, apagada | 1, 5 | sí |
| 7 | Agentes y skills | 6 | sí |
| 8 | Destilación por proyecto | 7 | sí |
| 9 | Apagar el v1 | 8 | — |

**El único gate de verdad es 5a.** Todo lo anterior es construir; a partir de ahí, si la prueba no da señal, el diseño se replantea en vez de terminarse.

---

## 13. Lo que este plan NO resuelve

Declarado para que no aparezca luego como sorpresa:

1. Las listas de zonas definitivas de cada proyecto — tarea del propietario, con la materia prima ya preparada.
2. El dedup semántico de remembers — excede a un script, requiere agente.
3. El carril de "ensayo operativo" en la tripulación: ninguna definición de agente cubre "ejecuta una prueba y reporta". Esta noche esa tarea rebotó entre dos agentes y la acabó haciendo el orquestador. Va a volver a pasar en las fases 2, 5 y 6.
4. El papel de Alexandria en el flujo de documentación.
5. El banco de pruebas adversarial (P12): está en la especificación como principio y no tiene fase asignada aquí. Debería colgar de cada fase, no ser una fase.
