#!/usr/bin/env python3
"""bin/memory/work.py -- el commit de trabajo (codigo): acepta rutas
concretas y no arrastra el resto del arbol [notes_commit.py::write_work,
docstring].

Contrato: docs/memoria-v2/PIEZAS.md Sec.10 (fila `work.py`). Grammar de
CLI [misma fila -- "mensaje, --path (repetible), --issue"]:

    work.py "<mensaje>" --path <ruta1> [--path <ruta2> ...] [--issue N]

Sec.10.1, punto 3 (proteccion de la rama principal) -- IMPLEMENTADO
2026-08-02. `config.py` deja leible `repo_type` (fail-closed: protegido
si no hay `config.json`) "antes de commitear, para saber si `main` esta
protegido" [config.py::load, docstring de quien lo llama]. Ese ajuste
solo tiene sentido si alguien lo obedece: si `repo_type` es el protegido
(`"gitflow"`, tambien el default fail-closed) Y la rama actual es la
principal, este script rechaza -- no commitea, no pregunta -- antes de
tocar el arbol de trabajo.

**La mecanica (nombre de rama principal, lectura de la rama actual,
texto del rechazo) vive en `lib/memory/repo_guard.py` desde
2026-08-03** -- trasladada de aqui sin cambiar ni una linea de
comportamiento, para que `bin/memory/wip.py` pudiera pedir la MISMA
proteccion [decision del propietario, "el checkpoint protege la rama
principal"] sin copiarla. Ver el docstring de ese modulo para la
asuncion de nombres de rama y el porque del traslado.

El texto exacto del rechazo no esta fijado en ningun documento (a
diferencia de los de `note.py`, que TEXTOS.md repite literalmente) --
la anatomia es la que Sec.7.4 exige para todo rechazo de este sistema:
que ha pasado y que hacer.
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
import notes  # noqa: E402
import rejection as rejection_  # noqa: E402
import repo_guard  # noqa: E402
import validator_issue  # noqa: E402


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="work.py")
    parser.add_argument("message")
    parser.add_argument("--path", action="append", required=True, dest="paths")
    parser.add_argument("--issue", type=int, default=None)
    return parser.parse_args(argv)


def _issue_rejection(message, paths, issue):
    """Rechazo real para `--issue N` cuando `gh` CONFIRMA que la issue no
    existe -- el UNICO caso que bloquea (encargo del propietario, regla
    2). Reusa `rejection.build`/`render_terminal`, la misma forma que
    `note.py` ya usa para su propio rechazo de issue -- ningun texto
    inventado a mano [Sec.7.4]. El comando de relanzamiento es el de
    `gitmem work`, no el de `gitmem note` (`validator_issue.validate_issue`
    no aplica aqui: exige una `Note` terminada que este script no
    construye)."""
    what = f"COMMIT DE TRABAJO RECHAZADO — la issue #{issue} no existe en este repo"
    options = (
        "Esta es la unica vez que se comprueba. Un numero mal tecleado aqui",
        "queda en el historial para siempre -- un commit no se reescribe.",
        "",
        "  gh issue list --limit 20          ver las abiertas",
        '  gh issue create --title "..."     crearla ahora',
    )
    path_flags = " ".join(f"--path {p}" for p in paths)
    command = (f'gitmem work "{message}" {path_flags} --issue <numero real>',)
    return rejection_.build(kind="issue_not_found", what=what, options=options, command=command)


def main(argv):
    args = _parse_args(argv)
    paths = [Path(p) for p in args.paths]

    # Leido como la PRIMERISIMA accion, antes de cualquier subproceso de
    # git (repo_root(), current_branch()) o E/S propia (config.load()) --
    # cada uno de esos ensancha la ventana entre "el contenido real que
    # este proceso vio" y "lo que write_work() acaba comiteando" si el
    # contenido se leyera despues [DEUDA.md punto 27, docstring de
    # write_work() punto 7: es el cierre real, aunque no absoluto, para
    # el unico llamador que no genera sus propios bytes en memoria].
    # `None` si la ruta no se puede leer ahora mismo (no existe, permiso)
    # -- write_work() cae entonces a su propia lectura de disco para esa
    # ruta, mismo comportamiento que antes de este arreglo, no una
    # regresion.
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

    # `--issue N` [encargo del propietario, dos reglas ya decididas]:
    # 1) `gh` CONFIRMANDO que la issue no existe es el UNICO caso que
    #    bloquea -- se rechaza, cero commit nuevo.
    # 2) Cualquier fallo de INFRAESTRUCTURA de `gh` (no instalado, sin
    #    red, timeout, una respuesta que no sea el "no existe" real --
    #    `validator_issue.issue_exists` ya distingue las dos, no se
    #    reimplementa aqui) NUNCA bloquea el commit de trabajo -- perder
    #    un checkpoint por estar sin red es peor que el problema. Solo se
    #    avisa, de forma visible, por stderr.
    if args.issue is not None:
        try:
            exists = validator_issue.issue_exists(args.issue)
        except RuntimeError as exc:
            print(
                f"aviso: no se pudo comprobar la issue #{args.issue} ({exc}) -- "
                "el commit de trabajo se guarda igual",
                file=sys.stderr,
            )
        else:
            if not exists:
                print(rejection_.render_terminal(_issue_rejection(args.message, paths, args.issue)))
                return 1

    result = notes.write_work(args.message, paths, args.issue, known_content=known_content)
    if not result.ok:
        print(f"git fallo al commitear: {result.git_error}", file=sys.stderr)
        return 1

    print(f"✅ commit de trabajo: {args.message}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # nunca una traza de pila -- PIEZAS.md Sec.10
        print(f"work.py: {exc}", file=sys.stderr)
        sys.exit(1)
