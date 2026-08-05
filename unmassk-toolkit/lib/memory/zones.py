"""Carga y consulta de las zonas del proyecto -- contrato en docs/memoria-v2/PIEZAS.md Sec.6.2.

De donde sale. Del rechazo de zona inexistente [TEXTOS Sec.1.1], que
imprime el recuento total de zonas.json y luego las mas parecidas, CON su
descripcion. De ahi que `candidates()` no pueda devolver nombres sueltos:
devuelve zonas enteras (objetos `Zone`).

Que NO hace esta pieza, y es la mitad del contrato [PIEZAS.md Sec.6.2]:
no decide si una zona es valida -- eso es `validator.validate_zones`; no
conoce la lista negra ni la palabra ambigua -- eso son datos de
`vocabulary`; no lee los indices. El recuento de notas que sale en el
rechazo no lo pone esta pieza: lo pone quien lo imprime, leyendo el
indice, porque `zones.json` no sabe cuantas notas hay [PIEZAS.md Sec.5.3,
model.Zone].

`add()` es la unica escritura de este fichero, y es la parte delicada:
bajo candado exclusivo entre procesos (lectura-modificacion-escritura
completa dentro de la misma seccion critica, para que dos altas
concurrentes no se pisen) y de forma atomica (fichero temporal en el
mismo directorio + os.replace, nunca un truncado en el sitio). Ambos
mecanismos estan reescritos de cero en este modulo, sin importar nada del
resto del toolkit: `lib/memory/` no importa nada fuera de la biblioteca
estandar de Python [PIEZAS.md Sec.13]. El candado imita a proposito el
mecanismo ya probado en produccion del v1 (bloqueo exclusivo de fichero,
con su variante de Windows) sin reutilizar sus lineas
[PLAN-CONSTRUCCION.md Sec.3.3, restriccion A].

Este proyecto no defiende contra un atacante (un solo dueno, sin
adversario externo) -- lo que importa es que el sistema no se rompa a si
mismo: una escritura a medias, o una zona que desaparece porque otra
escritura concurrente la piso, es perdida silenciosa de memoria.

El formato de zones.json no esta fijado por ningun documento del
contrato -- solo su contenido semantico (zonas, alias, descripcion). Este
modulo fija el formato mas simple que lo representa: un objeto JSON
`{nombre_canonico: {"description": ..., "aliases": [...]}}`.
"""

import difflib
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from model import Zone


def load(path: Path) -> dict[str, Zone]:
    """Lee zones.json y devuelve las zonas indexadas por su nombre canonico.

    Un fichero ausente se trata como "todavia no hay ninguna zona"
    (proyecto recien instalado [TEXTOS Sec.3.2]), no como un error. Un
    fichero presente pero corrupto (JSON invalido) SI se deja propagar --
    tragarlo aqui y devolver {} silenciosamente dejaria que `add()`
    sobrescribiera zones.json entero con una unica zona, borrando todo lo
    demas sin avisar: exactamente la perdida silenciosa que este proyecto
    trata como su unica amenaza real.

    "Corrupto" no es solo JSON invalido -- mismo patron que
    ``config.py::load()`` [PIEZAS.md Sec.6.3]: un JSON sintacticamente
    valido con la forma equivocada (``"aliases": "front"`` en vez de una
    lista) pasaria ``json.load`` sin problema, y ``tuple("front")`` lo
    trocearia letra a letra en cinco alias falsos sin avisar a nadie --
    exactamente el fallo silencioso que este contrato prohibe. Por eso
    esta funcion tambien valida que el JSON top-level sea un objeto, que
    cada zona sea un objeto, que su ``description`` sea texto y que sus
    ``aliases`` sean una lista de texto -- y lanza ``ValueError``
    nombrando el fichero y la zona afectada si no.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        return {}

    if not isinstance(raw, dict):
        raise ValueError(
            f"zones.py: {path.name} esta corrupto -- se esperaba un objeto "
            f"JSON (diccionario) y llego {type(raw).__name__}"
        )

    zones: dict[str, Zone] = {}
    for name, fields in raw.items():
        if not isinstance(fields, dict):
            raise ValueError(
                f"zones.py: {path.name} esta corrupto -- la zona {name!r} "
                f"debe ser un objeto JSON y llego {type(fields).__name__}"
            )

        description = fields.get("description", "")
        if not isinstance(description, str):
            raise ValueError(
                f"zones.py: {path.name} esta corrupto -- 'description' de "
                f"la zona {name!r} debe ser texto y llego "
                f"{type(description).__name__}"
            )

        aliases = fields.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            raise ValueError(
                f"zones.py: {path.name} esta corrupto -- 'aliases' de la "
                f"zona {name!r} debe ser una lista de texto y llego "
                f"{aliases!r}"
            )

        zones[name] = Zone(name=name, description=description, aliases=tuple(aliases))
    return zones


def resolve(name: str, zones: dict[str, Zone]) -> str | None:
    """Aplica alias y devuelve el nombre canonico, o None si no existe.

    None, nunca una excepcion ni una cadena vacia: una cadena vacia se
    confundiria con "zona sin notas" y el fallo pasaria callado.
    """
    if name in zones:
        return name
    for zone in zones.values():
        if name in zone.aliases:
            return zone.name
    return None


def candidates(name: str, zones: dict[str, Zone], limit: int = 3) -> tuple[Zone, ...]:
    """Las zonas mas parecidas a `name`, para el rechazo de zona inexistente.

    Devuelve zonas enteras (con su descripcion), no nombres sueltos --
    asi es como sale el rechazo [TEXTOS Sec.1.1].
    """
    close_names = difflib.get_close_matches(name, list(zones.keys()), n=limit, cutoff=0.6)
    return tuple(zones[n] for n in close_names)


def add(zone: Zone, path: Path) -> None:
    """Da de alta `zone` en zones.json, bajo candado y de forma atomica.

    Lectura-modificacion-escritura completa dentro de una unica seccion
    critica: dos `add()` concurrentes sobre el mismo `path` se serializan
    en vez de pisarse. Si `path` no existe todavia, se crea desde cero
    (equivalente a partir de {} y anadir la primera zona).

    El directorio que contiene `path` (`.claude/project-memory/` en un
    proyecto real) se crea si falta, idempotente (`exist_ok=True`) --
    mismo patron que `indexes.seed()` aplica a su propio directorio. Un
    proyecto recien instalado no tiene todavia esa carpeta la primera vez
    que se da de alta una zona, y sin esto el candado de abajo (que abre
    un fichero JUNTO a `path`) revienta con `FileNotFoundError` antes de
    llegar a escribir nada [hallazgo real: el alta quedo parcheada en
    `bin/memory/zones.py` en vez de aqui, obligando a cada futuro llamador
    -- el script de zonas, y el alta en dos pasos de la aduana -- a
    acordarse de crear la carpeta por su cuenta].
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with _exclusive_lock(lock_path):
        existing = load(path)
        existing[zone.name] = zone
        _write_atomic(path, existing)


def _serialize(zones: dict[str, Zone]) -> dict:
    return {
        name: {"description": z.description, "aliases": list(z.aliases)}
        for name, z in zones.items()
    }


def _write_atomic(path: Path, zones: dict[str, Zone]) -> None:
    """Escribe zones.json entero sin dejarlo nunca truncado a medias.

    Fichero temporal creado en el MISMO directorio que `path` (para que
    el reemplazo final quede en el mismo sistema de ficheros) y
    `os.replace()` al terminar -- atomico tanto en POSIX como en Windows
    desde Python 3.3. Un fallo a mitad de escritura (proceso matado,
    disco lleno) deja `path` con su contenido ANTERIOR intacto, nunca a
    medias.
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
def _exclusive_lock(lock_path: Path):
    """Bloqueo exclusivo entre procesos sobre `lock_path`, bloqueante hasta
    conseguirlo. Serializa cualquier lectura-modificacion-escritura sobre
    el `zones.json` correspondiente.

    POSIX: `fcntl.flock(fd, fcntl.LOCK_EX)` -- bloqueo nativo, indefinido,
    lo espera el kernel, sin bucle de reintento aqui.

    Windows: `msvcrt.locking()` no tiene un bloqueo indefinido propio --
    cada llamada reintenta internamente unos 10 segundos y luego lanza
    OSError si la region sigue ocupada. El bucle de abajo es el
    reintento PROPIO de esta funcion alrededor de eso: solo reintenta
    mientras el error sea justo ese (contencion en curso); cualquier otro
    error se relanza tal cual, porque reintentar no lo va a resolver.

    fcntl/msvcrt se importan de forma perezosa, dentro de la rama de
    `sys.platform` que corresponde -- para que importar este modulo nunca
    falle en la plataforma que no aplica.
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
