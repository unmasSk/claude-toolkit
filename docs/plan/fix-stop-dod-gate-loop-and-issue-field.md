# En vuelo: el bucle del guardián de cierre + el campo issue en los siete tipos

**Estado:** EN CURSO — no publicado. Escrito para sobrevivir a un cambio de sesión.
**Branch:** main (repo_type: trunk) · **Creado:** 2026-08-22

## Por qué esto es urgente

Un proyecto del propietario (`moria-v3`, toolkit 1.36.0) reportó que el hook `Stop`
entra en bucle: con la suite en rojo ejecuta la suite **entera** al final de cada
turno, bloquea, obliga a otro turno, y vuelve a ejecutarla. Allí el comando de tests
lanzaba audio real: **704 procesos huérfanos y la máquina sin poder hacer `fork`**.
El informe completo, con pruebas, está en `~/Workspace/moria-v3/docs/informe-stop-dod-gate.md`
(proyecto ajeno: solo lectura).

**El propietario tiene otros proyectos parados por esto.** Publicar es la prioridad.

## Lo que ya está hecho (en el árbol, sin commitear)

### Guardián de cierre — `hooks/stop-dod-gate.py` · 74/74 en verde
- **No reejecuta la suite si el árbol no ha cambiado.** Huella = `HEAD` + `git status
  --porcelain` hasheados, guardada junto a la decisión en
  `.claude/.unmassk/stop-dod-gate-state.json`. Si coincide, se reutiliza la decisión
  exacta sin ejecutar nada. Si la huella no se puede calcular → se ejecuta (nunca se
  salta la comprobación por no saber). **Esto es lo que corta los 704 procesos.**
- **La firma del anti-goteo sobrevive al contenido volátil**: se normalizan direcciones
  `0x...`, UUIDs, rutas temporales y tiempos `in N.NNs` antes de hashear. Antes la firma
  cambiaba en cada corrida y el anti-goteo no se activó ni una vez.
  - *Desviación deliberada de Ultron, con motivo*: se mantuvieron las líneas `E   ` en la
    firma en vez de excluirlas. Excluirlas rompía un test verde preexistente, porque
    pytest trunca su propia línea `FAILED` a ancho fijo y dos fallos distintos con prefijo
    largo común producen la misma línea; solo la `E` los distinguía.
- **El contrato, escrito en el docstring**: `test_command` se ejecuta en cada parada, así
  que debe ser idempotente y **sin efectos colaterales** (audio, notificaciones, red).

### Campo `issue` en los siete tipos de nota — 513 en verde en `tests/memory`
Decisiones **D-043** (veredicto del consejo), **D-044**, **D-045**; descartes **X-065** a **X-070**.
- `--issue` aceptado por D/M/R/Q/X/I/B (antes solo M). Producción: `vocabulary.py`,
  `report_render_note.py`, `report_render.py`, `boot.py`, `model.py`.
- El número se ve por los **tres** caminos: `search --id`, `search <zona>`, `search <palabra>`.
  El tercero no lo enseñaba **nunca**, para ningún tipo — lo encontró Moriarty.
- Contador del arranque: `plans with a record` → **`issues with a live note`**. La etiqueta
  vieja mentía al abrirse el campo. Se conserva la invariante de Argus (2026-08-02): ese
  número **nunca consulta GitHub**, solo cuenta notas locales sin archivar.
- `work.py --issue N` ahora comprueba que la issue exista: rechaza si no existe; si `gh` no
  puede contestar, **el commit se hace igual** con aviso visible (nunca se bloquea guardar
  trabajo). Cerró un hueco que encontró Argus.
- Veredicto de Yoda: **104/110**, aprobado.

### El protocolo de issues, escrito y enlazado
`unmassk-memory/references/issues.md` (nuevo) es el único sitio donde vive. Apuntan a él:
el **core** (momento 2: la raya es de alcance, no de gravedad; se propone y se espera, nunca
se abre por cuenta propia), la **skill de memoria**, el **cierre de sesión** (la red que
recoge lo escrito sin el usuario delante), la **auditoría** (donde decía "crea una issue" —
contradicción arreglada) y el **plan** de Flow.

### Fichas de agente
Regla nueva contra el truncado del índice de memoria, en las cuatro fichas que llevan el
tope de 200 líneas: `dante`, `house`, `ultron`, `moriarty`.

## En vuelo ahora mismo

**El rojo declarado del test-first.** El propietario trabaja test-driven en todos sus
proyectos: el contrato se escribe en rojo antes que el código, y hoy la compuerta lo trata
como avería y bloquea en cada parada. Diseño ya decidido:

- **Declarado, nunca inferido.** El orquestador declara qué está en rojo a propósito.
- Solo lo declarado se perdona; **cualquier otro rojo sigue bloqueando** (esto impide que
  se convierta en un interruptor para apagar la compuerta).
- Se permite el cierre **diciéndolo en una línea**, nunca en silencio.
- **La declaración se borra sola** cuando su rojo se pone verde.
- Vive en el estado de la sesión y **es por sesión** — no sobrevive a una sesión nueva.
- Se declara con un camino ejecutable (un comando pequeño), no editando el JSON a mano.

Dante tiene el contrato en marcha en `tests/test_stop_dod_gate.py`. Falta que Ultron lo
implemente en `hooks/stop-dod-gate.py`.

## Lo que falta para cerrar, en orden

1. Ultron implementa el rojo declarado hasta verde.
2. **Prueba en directo, exigida por el propietario**: montar un proyecto real y recorrer el
   ciclo test-first entero (contrato en rojo → implementación → verde) comprobando con las
   manos que no bloquea cuando no debe, que sí bloquea cuando debe, y que **no ejecuta nada
   si no se ha tocado un fichero**. La suite no basta.
3. Suite completa del repositorio en verde (`python3 -m pytest unmassk-toolkit/tests -q`).
4. Commit por `gitmem work`, push, y **esperar CI verde en Ubuntu y Windows antes de publicar**
   (regla del propietario desde que salieron rotas la 1.32.0 y la 1.33.0).
5. `python3 bin/release.py unmassk-toolkit <versión>` — pasada en seco antes.
6. **Avisar al propietario para que reinicie Claude**, que lo pidió expresamente.

## Trampas que ya costaron tiempo hoy — no repetirlas

- **Las fichas de agente no surten efecto hasta publicar.** Los agentes las leen del plugin
  instalado, no del árbol de trabajo. Por eso la regla contra el truncado no frenó a Dante.
- **El índice de memoria de Dante se truncó tres veces** (~20 KB → ~17 KB, descripciones
  cortadas a mitad de palabra) porque un aviso de tamaño del propio Claude Code le empuja a
  "compactar". Restaurado tres veces desde `HEAD`. Si vuelve a pasar: restaurar con
  `git show HEAD:<ruta>` y reañadir solo las entradas nuevas.
- **No lanzar la suite entera del repo con agentes trabajando en paralelo**: hoy dio 378
  errores que no eran del código, sino falta de procesos en la máquina (`fork failed`).
- El punto 4 del informe de moria (documentar el contrato) **ya está hecho**; los puntos 1,
  2 y 3 son los de arriba.
