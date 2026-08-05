---
name: capa5-read-scripts-and-facade-contract-notes
description: bin/memory/{search,boot,reindex,zones,rule,bench}.py + bin/gitmem RED contract (PIEZAS.md Sec.10) -- gitmem already exists as a phase-0 stub, UTC-label round-trip normalization, vocabulary.TYPES required_fields gotcha
metadata:
  type: project
---

**2026-08-02, memoria-v2 capa 5 (los scripts que LEEN + la fachada),
contrato en rojo antes de Ultron.** Escribi los tests de `search.py` ·
`boot.py` · `reindex.py` · `zones.py` · `rule.py` · `bench.py`
(`tests/memory/test_{search,boot,reindex,zones,rule,bench}_script.py`) y
de `bin/gitmem` (`tests/memory/test_gitmem_facade.py`) -- 33 tests
nuevos, 31 rojos por causa real, 2 verdes legitimos. Ver
[[capa5-scripts-red-contract-notes]] para los cuatro scripts que
ESCRIBEN (misma tanda anterior) -- esta nota es solo la mitad que lee.
184 tests previos siguen en verde (0 regresiones); total 217 (186
verdes/31 rojos).

**HALLAZGO: `bin/gitmem` YA EXISTE, no es un hueco vacio.** El encargo
decia "ninguno existe todavia" para los siete, pero `unmassk-toolkit/
bin/gitmem` esta commiteado desde antes (un commit de "sin color en
ninguna salida") como un STUB de "fase 0": lee `plugin.json` y responde
`--version`/lista de subcomandos previstos, pero `main()` NO PARSEA
`sys.argv` en absoluto -- cualquier subcomando (real o inventado) da el
mismo listado y `rc=0`. Antes de dar por sentado que un fichero de la
tabla de PIEZAS.md Sec.10 no existe, comprobar `bin/` ademas de
`bin/memory/` -- el chequeo rutinario (`find bin/memory -maxdepth 1`) no
lo habria detectado porque vive un nivel mas arriba. Los 3 tests de
`test_gitmem_facade.py` que exigen despacho real fallan por la causa
correcta (el stub ignora argv), no por fichero ausente; los otros 2
(`--version`, `force_utf8_streams`) pasan hoy porque esa parte SI esta
implementada ya -- no es un falso verde, es comportamiento real que no
hay que romper.

**Helper nuevo en conftest.py: `run_gitmem_script(args, cwd, env=None)`.**
Mismo contrato que `run_memory_script()` pero apuntando a
`_TOOLKIT_ROOT/bin/gitmem` (un nivel mas arriba que `bin/memory/`, la
fachada vive fuera de esa subcarpeta). Reutilizar este, no crear un
tercero.

**Helpers nuevos: `seed_note_via_script()` + `extract_note_id()`.** Ahora
que `note.py` existe y esta en verde (tanda anterior), sembrar datos para
`search.py`/`boot.py`/`reindex.py` a traves de el (proceso real, camino
completo con validador) es mejor que `notes.write()` en proceso -- mismo
principio que ya uso `test_close_script.py` cuando `note.py` todavia no
existia (ahi si tocaba `notes.write()` directo). `extract_note_id(stdout)`
lee el ID real de la confirmacion `"✅ {id} guardada"` con regex, nunca lo
deriva contando notas ni asumiendo un contador.

**Round trip con timestamp: normalizar antes de comparar, nunca fijar
el minuto exacto.** `search.py`/`boot.py` tienen que reproducir BYTE A
BYTE lo que `report_render.render_zone/word()` / `boot.render(boot.
build())` construyen en el MISMO proceso de test contra el mismo repo --
pero cada llamada (la del script, la del test) usa `datetime.now()` por
separado, y las dos pueden caer a los dos lados de un cruce de minuto (la
etiqueta UTC trunca a `%H:%M`). Arreglo: `_UTC_LABEL_RE =
re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")`, sustituir por un token
fijo en AMBOS lados antes de comparar -- nunca comparar el timestamp
literal. Sin esto el test seria intermitente (prohibido por las reglas
de Dante: "No timing-dependent assertions").

**Gotcha real de `vocabulary.TYPES`: el tipo `D` exige `description` Y
`why`, no solo `why`.** Sembrar una nota D con solo `--why` (sin
`--description`) rebota con "Faltan campos obligatorios para el tipo D:
description" -- cazado ejecutando al sembrar para `test_search_script.py`/
`test_boot_script.py`. `M`/`R`/`Q`/`X`/`I` solo exigen `description`; `B`
exige `description` + `awaits`. Revisar `vocabulary.py::TYPES[letra].
required_fields` antes de escribir una siembra nueva, no asumir por
analogia con otro tipo.

**Bench.py: como probar un script cuya UNICA dependencia (PIEZAS.md
Sec.14, "el banco adversarial") tampoco existe todavia.** El encargo
decia explicitamente "sin inventarte su contenido" -- ni un modulo, ni
una funcion agregadora del banco existe hoy en `lib/memory/`. Contrato
reducido a lo que SI esta fijado por texto: corre (`rc==0`, sin
Traceback), enseña "el resultado, siempre" (stdout no vacio, sin exigir
forma), y el invariante literal de Sec.14 ("corre en proceso, contra el
validador puro, sin escribir un solo commit") -- este ultimo SI es
verificable sin inventar nada: comparar SHA de HEAD antes/despues (mismo
patron que la red autouse de `conftest.py`).

**Vacuous-pass real cazado dos veces esta sesion, mismo patron que
[[capa5-scripts-red-contract-notes]] ya documento para `note.py`/
`context.py`:** un test de "fallo real" que solo mira `rc!=0` + "sin
Traceback" pasa en VERDE hoy mismo con el script AUSENTE (`can't open
file` tambien da `rc!=0` y cero Traceback). Cazado en
`test_search_script.py` (ID inexistente -- arreglado exigiendo que el
propio ID aparezca en el mensaje) y evitado de raiz en
`test_zones_script.py` (sin ningun dato real del que derivar contenido
positivo para "falta el nombre" -- se elimino el test, con nota explicita
en el docstring del fichero, en vez de fabricar texto). Regla para la
proxima vez: correr AISLADO cualquier test de "debe fallar" antes de
darlo por bueno en un contrato rojo -- `rc!=0` + "sin Traceback" nunca
basta solo, necesita SIEMPRE un dato positivo real (el ID, el numero, el
nombre) que el mensaje de "fichero ausente" no puede contener por
casualidad.
