#!/usr/bin/env python3
"""bin/memory/rezones.py -- el que repara: con `--verify` solo diagnostica
y no toca nada; sin el, reconstruye desde git Y LO GUARDA.

Contrato: docs/memoria-v2/PIEZAS.md Sec.10 (fila `rezones.py`, renombrada desde `reindex.py` -- decision del propietario, 2026-08-03) y Sec.9.4
("Quien lo llama": "`bin/memory/rezones.py --verify` llama a
`health.coherence(root)` -- ya en produccion"). Admite `--verify`.
Imprime que diverge, o que se reconstruyo.

**Convencion asumida sobre el codigo de retorno de `--verify`** [ASUNCION,
ningun texto del proyecto la fija -- ver docstring de
`test_rezones_script.py`]: codigo de retorno distinto de cero si hay una
divergencia real, cero si todo esta coherente. Mismo idioma para
reconstruir: codigo de retorno distinto de cero si la reparacion no se
pudo guardar.

**Reconstruir (sin `--verify`)** llama a `health.rebuild_plan(root)`
[movido a la libreria el 2026-08-02, hallazgo real: este script
reimplementaba treinta lineas del mismo cruce que `health.coherence()`
ya calcula, la logica de decision que la regla de Sec.10 reserva a un
modulo -- "si un script crece, es que se le esta colando logica que
pertenece a un modulo"] -- el mismo cruce que `health.coherence()` usa
para diagnosticar, aqui devuelto como PLAN (que insertar, que retirar,
en que fichero).

**El plan se APLICA Y SE COMITEA en `rezones_commit.apply_rebuild_plan()`
-- arreglado 2026-08-03, hallazgo real de Moriarty (DEUDA.md, "el comando
que repara los indices no guarda la reparacion").** Antes de este
arreglo, este script llamaba a `indexes.insert()`/`indexes.remove()`
DIRECTAMENTE -- que escriben en disco pero nunca comitean [indexes.py,
docstring: "No commitea"] -- y nunca invocaba a git: la reparacion vivia
solo en el arbol de trabajo, `git status` la enseñaba como cambio sin
guardar, y un `git checkout` sobre el indice reparado la borraba sin
ningun aviso, de vuelta a la averia de partida. `health.coherence()` no
lo detectaba porque compara DISCO contra GIT, nunca lo comiteado contra
el arbol de trabajo. `rezones_commit.apply_rebuild_plan()` reutiliza la
MISMA mecanica de candado+commit+restauracion que `notes.write()` ya usa
[notes_commit.py] -- no una transaccion nueva -- para que una nota viva
(no archivada) que falta en su indice quede REINSERTADA
(`indexes.insert`, misma linea que `notes.write()` habria escrito) y una
linea sin ninguna nota real detras quede RETIRADA (`indexes.remove`), las
dos EN UN COMMIT: un indice sin ninguna de las dos cosas queda BYTE A
BYTE igual que estaba, la prueba de que reconstruir no inventa [encargo
de esta tarea], y ahora ademas sobrevive a un `git checkout` porque la
reparacion misma es un commit. Este script sigue siendo "recibe
argumentos, llama a una funcion, imprime" -- decidir QUE cambia sigue sin
ser cosa suya, y ahora tampoco decide COMO se guarda.

No toca `rules.md`/`coherence_rules()` -- fuera de la superficie que
Sec.9.4 declara para este script (solo cita `health.coherence(root)`).

**Dos reparaciones a la vez, fuera de este script: decision del
propietario, no descuido -- DEUDA.md PARTE 1, B22 (2026-08-04) y PARTE 2,
punto 28 (cerrado el mismo dia como "caso descartado").** Comprobado
leyendo el codigo, no de memoria: el plan se calcula en la linea de
`_rebuild()` que llama a `health.rebuild_plan(root)` -- FUERA de
cualquier candado. El candado solo aparece despues, dentro de
`rezones_commit.apply_rebuild_plan()` (`gitcmd.file_lock(...)`), y ese
candado protege la ESCRITURA del plan ya calculado, nunca vuelve a
comprobar si el plan sigue siendo valido. Si dos reparaciones arrancan
casi a la vez, las dos calculan el mismo plan (reinsertar la misma nota)
antes de que ninguna coja el candado, y la segunda en entrar lo aplica
igual: la nota queda duplicada en el indice Y COMITEADA. Medido por
Moriarty el 2026-08-03: 15 de 15 intentos.

El propietario trabaja en una sola ventana y respondio literalmente **"no
va a pasar nunca"** a la pregunta de si dos escrituras a la vez sobre el
mismo fichero deben funcionar o el sistema debe negarse. Por eso esto NO
se repara: ni se mueve el calculo del plan dentro del candado, ni se
vuelve a comprobar el plan al entrar. El hecho medido (15 de 15) se deja
escrito a proposito -- no se borra solo porque el caso que lo provoca no
se vaya a dar --, para que dentro de seis meses quien lea esto sepa que
es una decision firmada, no un hueco que nadie miro.
"""

import argparse
import os
import sys

_BIN_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_BIN_MEMORY_DIR))
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import tras sys.path)

force_utf8_streams()

import health  # noqa: E402
import indexes  # noqa: E402
import notes  # noqa: E402
import rezones_commit  # noqa: E402


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="rezones.py")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args(argv)


def _verify(root):
    lines, notes_count, discrepancies = health.coherence(root)
    if not discrepancies:
        return [f"✓ índices coherentes con git ({lines} líneas / {notes_count} notas)"], 0
    out = [f"⚠️ índices no coherentes con git ({lines} líneas / {notes_count} notas)"]
    out.extend(f"  - {text}" for text in discrepancies)
    return out, 1


def _rebuild(root, pm):
    indexes.seed(pm)
    # Calculado FUERA de cualquier candado -- decision del propietario,
    # no descuido: ver el docstring del modulo (DEUDA.md B22 / punto 28).
    to_insert, to_remove = health.rebuild_plan(root)

    if not to_insert and not to_remove:
        return ["✓ nada que reconstruir -- los índices ya coinciden con git"], 0

    result = rezones_commit.apply_rebuild_plan(to_insert, to_remove, pm, root)
    if not result.ok:
        # Los ficheros ya quedaron restaurados por apply_rebuild_plan()
        # (mejor esfuerzo) antes de devolver este resultado -- se imprime
        # el error REAL de git, nunca una traza de pila [Sec.10].
        return [f"⚠️ la reparación no se pudo guardar -- índices restaurados: {result.git_error}"], 1

    changes = [f"+ {note.id} reinsertada en {target}" for note, target in to_insert]
    changes += [f"- {note_id} retirada de {name} (no existe en git)" for note_id, name in to_remove]
    return changes, 0


def main(argv):
    args = _parse_args(argv)
    root = notes.repo_root()
    pm = notes.pm_root(root)

    if args.verify:
        lines, rc = _verify(root)
        print("\n".join(lines))
        return rc

    lines, rc = _rebuild(root, pm)
    print("\n".join(lines))
    return rc


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # nunca una traza de pila -- PIEZAS.md Sec.10
        print(f"rezones.py: {exc}", file=sys.stderr)
        sys.exit(1)
