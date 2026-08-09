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


def normalize(name: str) -> str:
    """El NOMBRE de una zona -- su clave de comparacion y de persistencia
    -- va siempre en minuscula [orden del propietario, 2026-08-07: dos
    sesiones nombrando la misma zona distinto (`Boot` / `boot`) acababan
    con dos zonas que nunca se cruzaban entre si, memoria perdida sin un
    solo error]. Esto se aplica SOLO al nombre canonico y a los alias --
    son llaves de busqueda, no texto libre. La descripcion de la zona, y
    cualquier otro texto del sistema (titulares, why, keys, contexto de
    cierre, reglas), no pasa por aqui y se guarda tal cual se escribio
    [precision del propietario, 2026-08-07].

    Punto unico para esta regla -- `load()`, `resolve()`, `candidates()`
    y `add()` la llaman a traves de esta funcion en vez de repetir
    `.lower()` cada uno por su cuenta, para que un cambio futuro (p.ej.
    tambien recortar espacios) solo se toque aqui.
    """
    return name.lower()


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

    El nombre y los alias se normalizan a minuscula al releer
    [`normalize()`, arriba] -- no solo al escribir: un `zones.json`
    escrito ANTES de esta regla (una zona en mayuscula, de una sesion
    vieja) tiene que seguir resolviendo igual, nunca quedar huerfano
    porque el fichero en disco no se toco. La descripcion viaja tal cual
    esta en el fichero, sin normalizar.
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

        canonical_name = normalize(name)
        canonical_aliases = tuple(normalize(a) for a in aliases)
        zones[canonical_name] = Zone(
            name=canonical_name, description=description, aliases=canonical_aliases
        )
    return zones


def resolve(name: str, zones: dict[str, Zone]) -> str | None:
    """Aplica alias y devuelve el nombre canonico, o None si no existe.

    None, nunca una excepcion ni una cadena vacia: una cadena vacia se
    confundiria con "zona sin notas" y el fallo pasaria callado.

    `name` se normaliza [`normalize()`, arriba] antes de comparar --
    `Boot`, `BOOT` y `boot` tienen que llegar los tres a la misma zona.
    La comparacion normaliza TAMBIEN cada clave y cada alias de `zones`
    sobre la marcha, en vez de asumir que el diccionario ya llego
    normalizado -- en produccion siempre es asi (`load()`/`add()` lo
    garantizan), pero esta funcion no depende de quien la llama: un
    `zones` construido a mano en otro sitio (p.ej. un `Context` de
    prueba armado directamente, sin pasar por `load()`) tiene que seguir
    resolviendo igual. Devuelve la clave TAL CUAL esta en `zones` (no la
    version normalizada del argumento de busqueda) -- es el nombre
    canonico real de quien llamo, y coincide con la version normalizada
    solo porque en produccion `zones` ya viene asi.
    """
    target = normalize(name)
    for canonical, zone in zones.items():
        if normalize(canonical) == target:
            return canonical
        if target in (normalize(a) for a in zone.aliases):
            return canonical
    return None


def candidates(name: str, zones: dict[str, Zone], limit: int = 3) -> tuple[Zone, ...]:
    """Las zonas mas parecidas a `name`, para el rechazo de zona inexistente.

    Devuelve zonas enteras (con su descripcion), no nombres sueltos --
    asi es como sale el rechazo [TEXTOS Sec.1.1].

    `name` se normaliza antes de comparar, igual que en `resolve()` --
    para que "FACTURACION" mal escrito tambien encuentre "facturacion"
    como candidata, no solo su forma exacta.
    """
    close_names = difflib.get_close_matches(
        normalize(name), list(zones.keys()), n=limit, cutoff=0.6
    )
    return tuple(zones[n] for n in close_names)


def render_list(zones_map: dict[str, Zone]) -> str:
    """El texto de la lista de zonas -- cabecera con el recuento total,
    luego una linea por zona con su nombre, su descripcion y sus alias
    si tiene.

    Pura presentacion: no lee `zones.json` ni ningun otro fichero por su
    cuenta, solo formatea lo que recibe ya cargado (`load()`) -- mismo
    principio que declara el docstring de `report_render.py` para las
    piezas que "pintan" en vez de "decidir".

    Extraida de `bin/memory/zones.py::_cmd_list` [encargo del
    propietario, 2026-08-09] para que un segundo llamador -- el aviso de
    cero resultados de `bin/memory/search.py` cuando una busqueda por
    palabra no encuentra ninguna nota -- enseñe las zonas del proyecto
    con el mismo formato exacto, sin reimplementarlo.
    """
    lines = [f"zones.json tiene {len(zones_map)} zonas:"]
    for name in sorted(zones_map):
        zone = zones_map[name]
        line = f"  {name}   {zone.description}"
        if zone.aliases:
            line += f"   (alias: {', '.join(zone.aliases)})"
        lines.append(line)
    return "\n".join(lines)


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

    `zone.name` y `zone.aliases` se normalizan a minuscula antes de
    persistir [`normalize()`, arriba] -- esta es la UNICA escritura de
    `zones.json`, asi que es el sitio correcto para garantizarlo pase lo
    que pase por donde entre `zone` (hoy solo `bin/memory/zones.py`, pero
    no depende de que ese script se acuerde de normalizar por su cuenta).
    `zone.description` viaja tal cual, sin tocar.
    """
    canonical = Zone(
        name=normalize(zone.name),
        description=zone.description,
        aliases=tuple(normalize(a) for a in zone.aliases),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with _exclusive_lock(lock_path):
        existing = load(path)
        existing[canonical.name] = canonical
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
