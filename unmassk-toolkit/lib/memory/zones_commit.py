"""Mecanica de persistencia de `zones.py` -- la normalizacion de nombre
compartida por todo el modulo, el candado exclusivo entre procesos y la
escritura atomica de `zones.json`. Partido de `zones.py` por tamano
(354 lineas, techo 300), mismo patron que ya aplica `rules.py` ->
`rules_commit.py`/`rules_similarity.py`/`rules_validate.py`.

`normalize()`, `write_atomic()` y `exclusive_lock()` pierden su guion
bajo al cruzar de fichero -- mismo precedente que ya fijo
`notes_commit.py` para `lock_resource`/`repo_root`/`stage_and_commit`:
dejan de ser detalle interno de un solo modulo para ser mecanica que
`zones.py`, `zones_load.py` y `zones_query.py` importan desde fuera.
`_serialize()` se queda privada -- solo la usa `write_atomic()` aqui
mismo.

No importa nada del toolkit fuera de la biblioteca estandar de Python
[PIEZAS.md Sec.13]. Imports planos entre hermanos de `lib/memory/`
[PIEZAS.md Sec.3.3bis]. No importa nada de `zones.py`, `zones_load.py`
ni `zones_query.py` -- direccion unica, para que no haya ciclo.
"""

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import textnorm
from model import Zone


def normalize(name: str) -> str:
    """El nombre de una zona -- clave de comparacion y persistencia --
    siempre en minuscula y sin acentos. Se aplica SOLO al nombre
    canonico y a los alias; la descripcion no pasa por aqui.
    `load()`/`resolve()`/`candidates()`/`add()` la llaman a traves de
    esta funcion, nunca repiten la cuenta cada uno.
    """
    return textnorm.normalize_text(name)


def _serialize(zones: dict[str, Zone]) -> dict:
    return {
        name: {"description": z.description, "aliases": list(z.aliases)}
        for name, z in zones.items()
    }


def write_atomic(path: Path, zones: dict[str, Zone]) -> None:
    """Escribe zones.json entero sin dejarlo nunca truncado a medias.

    Fichero temporal en el MISMO directorio que `path` + `os.replace()`
    al terminar -- atomico en POSIX y en Windows desde Python 3.3. Un
    fallo a mitad deja `path` con su contenido ANTERIOR intacto.
    """
    dest_dir = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dest_dir, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(_serialize(zones), f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


@contextmanager
def exclusive_lock(lock_path: Path):
    """Bloqueo exclusivo entre procesos sobre `lock_path`, bloqueante hasta
    conseguirlo. Serializa cualquier lectura-modificacion-escritura sobre
    el `zones.json` correspondiente.

    POSIX: `fcntl.flock(fd, fcntl.LOCK_EX)` -- bloqueo nativo, indefinido.

    Windows: `msvcrt.locking()` no tiene bloqueo indefinido propio -- cada
    llamada reintenta internamente unos 10 segundos y luego lanza OSError
    si la region sigue ocupada. El bucle de abajo reintenta SOLO mientras
    el error sea justo ese; cualquier otro error se relanza tal cual.

    fcntl/msvcrt se importan de forma perezosa, dentro de la rama de
    `sys.platform` que corresponde.
    """
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if sys.platform == "win32":
            import errno
            import msvcrt

            contended_errno = getattr(errno, "EDEADLOCK", None)
            os.lseek(fd, 0, os.SEEK_SET)
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                    break
                except OSError as e:
                    if contended_errno is not None and e.errno == contended_errno:
                        # msvcrt.locking() ya agoto su propio intento de
                        # ~10s y la region sigue ocupada -- sigue siendo
                        # contencion genuina, no un fallo permanente.
                        continue
                    raise  # fallo real -- reintentar no lo va a arreglar
            try:
                yield
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
