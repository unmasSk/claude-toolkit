#!/usr/bin/env python3
"""bin/memory/boot.py -- el menu del dia: lo primero que se ve al abrir
una sesion.

Contrato: docs/memoria-v2/PIEZAS.md Sec.10 (fila `boot.py`): llama a
`boot.build` + `boot.render`, no admite argumentos, imprime el menu del
dia. Toda la logica (que se enseña, en que orden, que pasa en un proyecto
recien instalado o con una rama sin ningun commit todavia) vive en
`lib/memory/boot.py` -- ya en produccion, con las dos formas de reventar
en un proyecto recien instalado ya arregladas ahi (indices/`ARCHIVED.md`
ausentes cuentan como cero, una rama sin commits es un estado valido, no
un fallo) [ver `lib/memory/boot.py`, `lib/memory/indexes.py`,
`lib/memory/query.py`, docstrings "Revision 2026-08-02"].

`boot.build()` resuelve su `root` con `notes.repo_root()` (`git
rev-parse --show-toplevel`) [correccion 2026-08-02, `lib/memory/boot.py`,
docstring del modulo] -- ya no con `Path.cwd()` a secas, asi que este
guion no necesita ningun apano propio: lanzado desde una subcarpeta
anidada, `boot_lib.build()` encuentra la raiz real por si solo. El apano
que vivia aqui antes (`os.chdir(notes.repo_root())` antes de llamar a
`boot_lib.build()`) se retira -- quedaba fuera de la pieza, y obligaba a
que cada futuro llamador (el hook del arranque, que aun no existe) se
acordara de repetirlo.
"""

import os
import sys

_BIN_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_BIN_MEMORY_DIR))
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import tras sys.path)

force_utf8_streams()

import boot as boot_lib  # noqa: E402
import gitcmd  # noqa: E402
import notes  # noqa: E402


# Donde se deja el informe. La carpeta esta ignorada por git en todos
# los proyectos del toolkit: es estado de la sesion, no memoria.
_REPORT_DIR = (".claude", ".unmassk")
_REPORT_NAME = "boot-latest.txt"


def main(argv):
    """Escribe el informe en un fichero y deja por pantalla SOLO donde
    esta.

    **No se inyecta** [decision del propietario, B4]: lo que un hook
    imprime al arrancar entra en el contexto con un tope de tamaño, y un
    arranque con veinte muros y diez bloqueantes lo pasa. Recortado por
    ese tope, lo que desaparece es el final -- justo los avisos de salud,
    que son los que dicen si la memoria esta rota. Se escribe entero y se
    lee entero.
    """
    report = boot_lib.render(boot_lib.build())

    root = notes.repo_root()
    folder = root.joinpath(*_REPORT_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / _REPORT_NAME

    # `gitcmd.atomic_write()`, no un temporal a mano: un arranque
    # interrumpido a mitad no puede dejar medio informe que el siguiente
    # leeria como si fuera entero, y esa pieza ya resuelve exactamente
    # eso para los indices [Cerberus, 2026-08-05: no se reimplementa lo
    # que ya existe en el mismo sys.path].
    gitcmd.atomic_write(destination, report)

    print(f"[memory] el informe del arranque esta en {destination}")
    print("Léelo entero antes de hacer nada. No está resumido.")
    return 0


def _leave_a_failure_marker(exc: Exception) -> None:
    """Si el arranque revienta, el informe de AYER se queda en disco y no
    hay forma de distinguirlo del de hoy salvo mirando su fecha. Y quien
    lo lanza se traga el codigo de salida a proposito -- la memoria no
    bloquea la sesion. Asi que el fallo se escribe donde se lee
    [Argus, 2026-08-05].
    """
    try:
        from datetime import datetime, timezone

        root = notes.repo_root()
        folder = root.joinpath(*_REPORT_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        stamp = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC"
        gitcmd.atomic_write(
            folder / _REPORT_NAME,
            f"⚠️  EL ARRANQUE FALLÓ — {stamp}\n\n{exc}\n\n"
            "No hay informe de esta sesión. Lo que había aquí antes era de\n"
            "una sesión anterior y se ha sustituido por este aviso para que\n"
            "nadie lo lea como si fuera de hoy.\n",
        )
    except Exception:
        # Si ni siquiera esto se puede escribir, queda el stderr de abajo.
        pass


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # nunca una traza de pila -- PIEZAS.md Sec.10
        _leave_a_failure_marker(exc)
        print(f"boot.py: {exc}", file=sys.stderr)
        sys.exit(1)
