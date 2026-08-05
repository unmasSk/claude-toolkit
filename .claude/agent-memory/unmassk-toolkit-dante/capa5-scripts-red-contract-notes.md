---
name: capa5-scripts-red-contract-notes
description: bin/memory/{note,close,context,work}.py RED contract (PIEZAS.md Sec.10) -- run_memory_script() subprocess pattern, argparse-missing-arg vacuous-pass pitfall, CLI-grammar-by-literal-example technique
metadata:
  type: project
---

**2026-08-02, memoria-v2 capa 5 (los scripts), contrato en rojo antes de
Ultron.** Escribi los tests de `bin/memory/note.py` · `close.py` ·
`context.py` · `work.py` (ninguno existe todavia) en
`unmassk-toolkit/tests/memory/test_{note,close,context,work}_script.py`.
22 tests, todos ROJOS por la causa real (script inexistente); los 160 ya
verdes se quedaron verdes. Ver [[memoria-v2-fase0-conftest-notes]] y
[[notes-cwd-leak-fix-and-guard-fixture-notes]] para el resto del sistema
de memoria v2 -- esta nota es solo la CAPA DE SCRIPTS.

**Los scripts se prueban como procesos reales, nunca importados** --
regla explicita de PIEZAS.md Sec.10. Añadi `run_memory_script(name,
args, cwd, env=None)` a `tests/memory/conftest.py` (junto a `pm_path()` /
`seed_zones_json()`, ambas DRY entre los cuatro ficheros): invoca
`sys.executable <bin/memory/name> *args` con `cwd` explicito y un `env`
que EXTIENDE (no sustituye) el heredado -- necesario para el test de
`PYTHONIOENCODING=cp1252` sin romper `PATH`/`HOME` (git deja de
funcionar si se sustituye el entorno entero).

**Pitfall real, cazado ejecutando, no en teoria: un test de "falta un
argumento obligatorio" puede pasar EN VERDE hoy mismo, con el script
inexistente, si solo mira `returncode != 0` y `"Traceback" not in
salida`.** `python3 <ruta que no existe>` devuelve `returncode=2` y un
stderr de una sola linea ("can't open file ... No such file or
directory") -- exactamente la misma forma que un argparse real
rechazando un flag que falta. Sin un assert de CONTENIDO positivo (no
solo negativo), el test es tautologico con el fallo que se supone que
detecta. Lo cace en `test_context_script.py` (headline obligatorio):
verificado con `pytest -q` antes de cerrar la tarea, la suite dio 161
verdes en vez de los 160 esperados -- ese +1 vacuo era ese test. Lo quite
en vez de fabricar un assert de contenido (context.write() no tiene
NINGUNA aduana -- "sin candado, sin aduana, sin indice", su propio
docstring -- asi que no hay ninguna funcion real de la que derivar el
texto exacto de un rechazo de argparse sin inventarme la redaccion).
Regla para la proxima vez: **antes de dar un test de "fallo" por bueno
en un contrato rojo, correrlo aislado y confirmar que TODAVIA falla con
el script ausente** -- un `assert rc != 0` solo no basta nunca como
unico criterio de un test de fallo en un contrato test-first, porque
"el fichero no existe" es tambien, tecnicamente, un fallo.

**Tecnica: derivar la gramatica de CLI de los comandos de relanzamiento
LITERALES que TEXTOS.md repite, no inventarla.** `note.py` no tiene un
unico sitio que fije su interfaz de argumentos, pero TEXTOS.md Sec.1.1/
1.5/1.6/1.7/1.9/1.11 repiten la MISMA forma seis veces en los textos de
rechazo: `gitmem note <TIPO> --zones <z1> <z2> "<titular>" [--why ...]
[--description ...] [--replaces <ID>|none] [--origin ...] [--issue N]`.
Seis repeticiones independientes de la misma forma es evidencia real, no
una suposicion -- la use como el contrato de CLI del test, documentandolo
en el docstring del fichero como "GRAMATICA DE CLI ASUMIDA" con su cita.
Donde NO habia ninguna repeticion literal (la forma de `--point` en
`context.py`, que no tiene analogo en ningun texto), lo deje marcado
explicitamente como ASUNCION en el docstring en vez de fingir que era
contrato.

**Round trip real contra rechazos, sin fabricar el texto esperado**
(unmassk-standards Sec.34): para probar que `note.py` imprime el rechazo
real ante una zona inexistente o un `--stops` que falta, NO tecleo el
texto del rechazo a mano -- llamo en el mismo proceso de test a
`validator.validate_zones(note, zones)` / `validator.validate_pain_
question(note, stops)` (funciones REALES, ya en produccion) con los
MISMOS datos que le paso al script por CLI, renderizo con
`rejection.render_terminal(r)` ("el que imprime el generador cuando
rechaza en proceso" -- literal de su propio docstring, asi que es
exactamente la funcion que el script tiene que llamar tambien) y
comparo esa cadena calculada contra el stdout+stderr real del proceso
hijo. Productor (script) y patron de comparacion vienen de la MISMA
libreria real, nunca de un texto copiado de TEXTOS.md a mano.

**Huecos del contrato anotados en vez de inventados** (encargo
explicito del propietario: "si algo no cuadra, anotalo y sigue"):
1. `--issue` de `note.py` dispara una comprobacion contra `gh issue
   view` [TEXTOS.md Sec.1.9] que `validator.py` declara EXPLICITAMENTE
   fuera de su propia pieza ("la 8... no vive en esta pieza") -- ningun
   modulo de produccion la expone hoy. Cero tests usan `--issue` para no
   depender de `gh` real (red/auth) en un pase de aceptacion.
2. `close.py --restriction new` [TEXTOS.md Sec.1.10] implicaria crear una
   R nueva al cerrar una incidencia, pero `notes.close(note_id, reason,
   ctx)` no tiene NINGUNA capacidad de escribir una nota nueva (su
   propio docstring: "cerrar no crea ninguna nota nueva"). Solo probe
   `--restriction no`.
3. `config.py::load()` documenta que "`bin/memory/work.py` lee
   `repo_type` ... para saber si main esta protegido" pero ningun texto
   fija QUE hace con esa lectura -- ningun test de `work.py` ejercita
   rama protegida.

**Fixture de siembra para `close.py`:** como `note.py` tampoco existe
todavia, `test_close_script.py` siembra la nota real que va a cerrar
llamando a `notes.write()` EN PROCESO (produccion ya existente, mismo
patron que `test_notes.py`), envuelto en el mismo `_cwd(tmp_repo)`
context manager -- nunca a traves del script bajo contrato, que es
precisamente lo que se prueba.
