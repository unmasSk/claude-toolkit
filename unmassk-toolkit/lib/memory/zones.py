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

**Fachada/api desde 2026-08-24** [partido bajo el techo de 300 lineas por
fichero, este fichero llego a 354 -- mismo patron que ya aplico `rules.py`
-> `rules_commit.py`/`rules_similarity.py`/`rules_validate.py`]. `add()`
(mas abajo) es la operacion real de esta pieza, igual que `rules.add()`
lo es en su fachada; el resto se partio en tres hermanos por concernencia
real:

  - `zones_commit.py` -- `normalize()` (la normalizacion compartida por
    todo el modulo), el candado exclusivo entre procesos
    (`exclusive_lock()`) y la escritura atomica (`write_atomic()`).
  - `zones_load.py` -- `load()`, lectura y validacion de forma de
    `zones.json`.
  - `zones_query.py` -- `resolve()`, `candidates()`, `render_list()`:
    consulta y presentacion, sin escritura.

Este fichero importa de los tres e importa SOLO de ellos -- nunca al
reves [direccion unica, mismo principio que ya aplica `notes.py`/
`notes_commit.py`]. Reexporta `normalize`/`load`/`resolve`/`candidates`/
`render_list` bajo el MISMO nombre, sin guion bajo, asi que
`zones.normalize`/`zones.load`/`zones.resolve`/`zones.candidates`/
`zones.render_list` siguen siendo atributos validos de este modulo, exista
o no la funcion fisicamente aqui. Verificado antes de partir: ningun
llamador real (grep ejecutado sobre `lib/` y `bin/`) usa un nombre
PRIVADO de este fichero desde fuera.

`add()` es la unica escritura de este fichero, y es la parte delicada:
bajo candado exclusivo entre procesos (lectura-modificacion-escritura
completa dentro de la misma seccion critica, para que dos altas
concurrentes no se pisen) y de forma atomica (fichero temporal en el
mismo directorio + os.replace, nunca un truncado en el sitio). Ambos
mecanismos viven en `zones_commit.py` y no importan nada del resto del
toolkit: `lib/memory/` no importa nada fuera de la biblioteca estandar de
Python [PIEZAS.md Sec.13].

Este proyecto no defiende contra un atacante (un solo dueno, sin
adversario externo) -- lo que importa es que el sistema no se rompa a si
mismo: una escritura a medias, o una zona que desaparece porque otra
escritura concurrente la piso, es perdida silenciosa de memoria.

El formato de zones.json no esta fijado por ningun documento del
contrato -- solo su contenido semantico (zonas, alias, descripcion). Este
modulo fija el formato mas simple que lo representa: un objeto JSON
`{nombre_canonico: {"description": ..., "aliases": [...]}}`.
"""

from pathlib import Path

from model import Zone
from zones_commit import exclusive_lock, normalize, write_atomic  # noqa: F401
from zones_load import load
from zones_query import candidates, render_list, resolve  # noqa: F401


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
    llegar a escribir nada.

    `zone.name` y `zone.aliases` se normalizan a minuscula antes de
    persistir [`normalize()`] -- esta es la UNICA escritura de
    `zones.json`, asi que es el sitio correcto para garantizarlo pase lo
    que pase por donde entre `zone`. `zone.description` viaja tal cual,
    sin tocar.
    """
    canonical = Zone(
        name=normalize(zone.name),
        description=zone.description,
        aliases=tuple(normalize(a) for a in zone.aliases),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with exclusive_lock(lock_path):
        existing = load(path)
        existing[canonical.name] = canonical
        write_atomic(path, existing)
