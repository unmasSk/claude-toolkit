#!/usr/bin/env python3
"""bin/memory/wip.py -- el checkpoint sin preguntas: un commit de
trabajo marcado con el emoji de wip (🚧) delante del titular, para que
la aduana lo exima de toda pregunta [validator.is_wip, TEXTOS.md
cabecera de emojis: "🚧 wip"].

Contrato: nuevo subcomando `wip`, PIEZAS.md Sec.10 (fila `wip.py`) --
anadido 2026-08-03, decision del propietario, tras verificar un agujero
real: `validator.is_wip()` ya sabia reconocer y eximir el marcador, pero
ningun comando lo escribia -- una puerta abierta sin llave. En el
sistema v1 se uso 208 veces: es el guardado rapido de trabajo a medias,
sin preguntas, que luego se comprime al fusionar.

Grammar de CLI, misma forma que `work.py` (mismo tipo de commit --
codigo, no nota de memoria -- menos `--issue`, que un checkpoint no
referencia por diseño: es trabajo a medias, todavia sin acta):

    wip.py "<mensaje>" --path <ruta1> [--path <ruta2> ...]

Reutiliza `notes.write_work()` tal cual [PIEZAS.md Sec.8.1, ya en
produccion]: candado, staging atomico, restauracion si git falla --
nada de eso se reescribe aqui. Lo unico propio de este script es
anteponer el marcador de wip (`emojis.CHANNEL_EMOJI["wip"]`, "🚧") al
mensaje ANTES de llamar -- si se escribiera de otra forma,
`validator.is_wip()` no lo reconoceria y la aduana le haria las mismas
preguntas que a cualquier commit de trabajo corriente, justo lo
contrario de para que existe esta pieza.

**SI protege la rama principal, igual que `work.py`, desde
2026-08-03** [decision del propietario: "el checkpoint protege la rama
principal"] -- este docstring decia hasta esa fecha que no lo hacia,
por decision tomada aqui sin que se hubiera pedido; era un agujero real
(el checkpoint es un commit, y un commit en la rama principal lo es
tanto si es rapido como si no) y quedo cerrado explicitamente. **Que
`wip` no haga preguntas de aduana** [`validator.is_wip()` lo exime] **no
es lo mismo que "sin proteccion de rama"**, que es un control distinto,
gobernado por `config.repo_type` (fail-closed: protegido si no se
declara) -- un ajuste que nadie obedeciera seria un campo zombi. La
mecanica (nombre de rama principal, lectura de la rama actual, texto
del rechazo) vive en `lib/memory/repo_guard.py`, compartida con
`work.py` sin duplicarla -- ver el docstring de ese modulo. Y el
rechazo dice que hacer, como todos los de este sistema: crear una rama
de trabajo, o declarar el tipo de repositorio si el proyecto despliega
de verdad directo desde la principal.
"""

import argparse
import os
import sys
from pathlib import Path

_BIN_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_BIN_MEMORY_DIR))
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import tras sys.path)

force_utf8_streams()

import config  # noqa: E402
import emojis  # noqa: E402
import notes  # noqa: E402
import repo_guard  # noqa: E402

_WIP_MARKER = emojis.CHANNEL_EMOJI["wip"]

# El corchete literal delante, igual que el `[NEXT]` del cierre
# [decision del propietario, 2026-08-05]. Su lector es
# `validator.is_wip()`, que reconoce por este mismo prefijo.
_WIP_PREFIX = "[WIP]"


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="wip.py")
    parser.add_argument("message")
    parser.add_argument("--path", action="append", required=True, dest="paths")
    return parser.parse_args(argv)


def main(argv):
    args = _parse_args(argv)
    paths = [Path(p) for p in args.paths]

    # Misma razon y mismo orden que `work.py`: leido antes de cualquier
    # subproceso de git o E/S propia [DEUDA.md punto 27, docstring de
    # write_work() punto 7] -- es el cierre real, aunque no absoluto,
    # para el unico llamador que no genera sus propios bytes en memoria.
    # `None` si la ruta no se puede leer ahora mismo (no existe,
    # permiso) -- write_work() cae entonces a su propia lectura de
    # disco para esa ruta, mismo comportamiento que antes de este
    # arreglo, no una regresion.
    #
    # Estado a 2026-08-04 [DEUDA.md B22]: el propietario descarto el
    # caso que motivaba este cierre -- dos escrituras a la vez sobre el
    # mismo fichero -- con un "No va a pasar nunca": se trabaja en una
    # sola ventana. El punto 27 queda CERRADO por decision, no por mas
    # reparacion: esto ya NO es un pendiente. La decision dice que no se
    # construye MAS por ese eje (nada de serializar, nada de negarse) --
    # no que se retire lo que ya funciona, asi que esta lectura
    # anticipada se queda tal cual esta.
    known_content = []
    for path in paths:
        try:
            known_content.append(path.read_bytes())
        except OSError:
            known_content.append(None)

    root = notes.repo_root()
    pm = notes.pm_root(root)
    config_path = pm / "config.json"
    cfg = config.load(config_path)

    if cfg.repo_type == repo_guard.PROTECTED_REPO_TYPE:
        branch = repo_guard.current_branch(root)
        if branch in repo_guard.MAIN_BRANCH_NAMES:
            print(repo_guard.protected_branch_rejection(branch, config_path))
            return 1

    marked_message = f"{_WIP_PREFIX} {_WIP_MARKER} {args.message}"
    result = notes.write_work(marked_message, paths, None, known_content=known_content)
    if not result.ok:
        print(f"git fallo al commitear: {result.git_error}", file=sys.stderr)
        return 1

    print(marked_message)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # nunca una traza de pila -- PIEZAS.md Sec.10
        print(f"wip.py: {exc}", file=sys.stderr)
        sys.exit(1)
