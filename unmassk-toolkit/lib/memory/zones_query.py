"""Consulta y presentacion de zonas -- `resolve()` (alias -> nombre
canonico), `candidates()` (las mas parecidas, para el rechazo de zona
inexistente) y `render_list()` (el texto de la lista de zonas). Partido
de `zones.py` por tamano (354 lineas, techo 300), mismo patron que
`rules.py` -> `rules_similarity.py`.

Las tres cruzan a `zones.py`, que las reexpone bajo el mismo nombre.

No importa nada del toolkit fuera de la biblioteca estandar de Python
[PIEZAS.md Sec.13]. Imports planos entre hermanos de `lib/memory/`
[PIEZAS.md Sec.3.3bis]. No importa nada de `zones.py` -- direccion
unica, para que no haya ciclo.
"""

import difflib

from model import Zone
from zones_commit import normalize


def resolve(name: str, zones: dict[str, Zone]) -> str | None:
    """Aplica alias y devuelve el nombre canonico, o None si no existe.

    None, nunca una excepcion ni una cadena vacia: una cadena vacia se
    confundiria con "zona sin notas" y el fallo pasaria callado.

    `name` se normaliza [`normalize()`] antes de comparar -- `Boot`,
    `BOOT` y `boot` tienen que llegar los tres a la misma zona. La
    comparacion normaliza TAMBIEN cada clave y cada alias de `zones` (en
    vez de asumir que el diccionario ya llego normalizado) -- un `zones`
    construido a mano en otro sitio (p.ej. un `Context` de prueba armado
    directamente) tiene que seguir resolviendo igual. Devuelve la clave
    TAL CUAL esta en `zones`, no la version normalizada del argumento.
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

    `name` se normaliza antes de comparar, igual que en `resolve()`.
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
    cuenta, solo formatea lo que recibe ya cargado (`load()`).

    Extraida de `bin/memory/zones.py::_cmd_list` [encargo del
    propietario, 2026-08-09] para que un segundo llamador -- el aviso de
    cero resultados de `bin/memory/search.py` -- enseñe las zonas del
    proyecto con el mismo formato exacto, sin reimplementarlo.
    """
    lines = [f"zones.json tiene {len(zones_map)} zonas:"]
    for name in sorted(zones_map):
        zone = zones_map[name]
        line = f"  {name}   {zone.description}"
        if zone.aliases:
            line += f"   (alias: {', '.join(zone.aliases)})"
        lines.append(line)
    return "\n".join(lines)
