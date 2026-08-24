"""Lectura de `zones.json` -- partido de `zones.py` por tamano (354
lineas, techo 300), mismo patron que `rules.py` -> `rules_commit.py`.

`load()` cruza a `zones.py` (que la reexpone bajo el mismo nombre) y a
`zones.add()`, que la usa para leer las zonas existentes antes de anadir
una nueva.

No importa nada del toolkit fuera de la biblioteca estandar de Python
[PIEZAS.md Sec.13]. Imports planos entre hermanos de `lib/memory/`
[PIEZAS.md Sec.3.3bis]. No importa nada de `zones.py` -- direccion
unica, para que no haya ciclo.
"""

import json
from pathlib import Path

from model import Zone
from zones_commit import normalize


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
    trocearia letra a letra en cinco alias falsos sin avisar a nadie.
    Por eso esta funcion tambien valida que el JSON top-level sea un
    objeto, que cada zona sea un objeto, que su ``description`` sea texto
    y que sus ``aliases`` sean una lista de texto -- y lanza ``ValueError``
    nombrando el fichero y la zona afectada si no.

    El nombre y los alias se normalizan a minuscula al releer
    [`normalize()`], no solo al escribir -- un `zones.json` escrito ANTES
    de esta regla tiene que seguir resolviendo igual. La descripcion
    viaja tal cual, sin normalizar.
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
