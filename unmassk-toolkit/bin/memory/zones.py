#!/usr/bin/env python3
"""bin/memory/zones.py -- list, find equivalentes y dar de alta las
zonas del proyecto.

Contrato: docs/memoria-v2/PIEZAS.md Sec.10 (fila `zones.py`). Llama a UNA
funcion de la libreria por subcomando (`zones.load`, `zones.candidates`,
`zones.add`) e imprime lo que devuelve -- toda la logica vive en
`lib/memory/zones.py`, nunca aqui [PIEZAS.md Sec.10, regla comun a los
once scripts: "si un script crece, es que se le esta colando logica que
pertenece a un modulo"].

Grammar de CLI [decision del propietario, 2026-08-04: los subcomandos
pasan a ingles, sin alias ni periodo de gracia -- `alta`/`listar`/
`buscar` DEJAN de existir, los unicos validos pasan a ser
`add`/`list`/`find` (DEUDA.md B11, PLAN-CONSTRUCCION.md Sec.1: "todo
nombre que ve una maquina va en ingles"). `ARQUITECTURA.md` Sec.6bis y
`DEUDA.md` linea 365 siguen citando `gitmem zones alta` -- quedan
desactualizados por esta decision, corregirlos es trabajo de Alexandria,
no de este fichero]:

    zones.py add <nombre> --description "..." [--aliases a1 a2 ...]
    zones.py list
    zones.py find <nombre>

`zones.add()` ya escribe bajo candado exclusivo entre procesos y de
forma atomica [lib/memory/zones.py, docstring del modulo] -- este script
no anade ningun mecanismo propio de concurrencia: construye la `Zone`
candidata y llama a `zones.add()` una sola vez, tal cual.

**Dar de alta un nombre que YA es una zona rebota, no pisa** [decision
del propietario, 2026-08-04, reproduciendo el fallo real de ese dia: dos
altas seguidas sobre el mismo nombre borraban en silencio el alias y la
descripcion de la primera, y las dos imprimian el MISMO "dada de alta"].
El rebote vive AQUI, en el script -- `zones_lib.add()` en si mismo sigue
sin comprobar nada (no es responsabilidad de esta tarea): es el script
quien lee `zones_lib.load(path)` ANTES de construir la `Zone` candidata
y decide no llamar a `add()` en absoluto si el nombre ya es una zona
canonica, dejando `zones.json` intacto byte a byte. Ningun documento
fija un texto para este rechazo (`TEXTOS.md` Sec.1.1 es el rechazo
OPUESTO, zona que NO existe) -- el mensaje de aqui abajo es redaccion
propia, mismo tono que el resto de mensajes de este script.

Choque contra un ALIAS de otra zona (no un nombre canonico) TAMBIEN
rebota [decision del orquestador, 2026-08-04, extendiendo la del
propietario sobre el nombre existente; revocable por el]. Sin ese
rebote se creaba una SEGUNDA zona con ese nombre y, desde ese
instante, `zones.resolve()` lo llevaba a la nueva en vez de a la de
siempre: el alias de la vieja quedaba secuestrado sin un solo aviso.
Y el rechazo NOMBRA al dueno del alias, porque el nombre tecleado no
sale en ningun listado y un "ya existe" sin decir a quien seria un no
sin salida.

[corregido 2026-08-04] Este parrafo decia que ese choque quedaba
FUERA "a proposito", y el codigo de mas abajo ya lo rechazaba desde
esa misma tarde: se escribio antes de implementarlo y no se actualizo
al hacerlo. Se anota en vez de sustituirlo sin mas porque es el
defecto exacto que este sistema existe para cazar -- un comentario
que contradice al codigo que acompana, con dos horas de diferencia.

El "recuento" que PIEZAS.md Sec.10 promete en la salida es el numero
TOTAL de zonas en zones.json (mismo dato que ya imprime el rechazo de
zona inexistente, TEXTOS.md Sec.1.1: "zones.json tiene 34 zonas") -- NO
el numero de notas por zona: `model.Zone` declara explicitamente que ese
recuento "NO es campo: lo calcula quien lo imprime, leyendo el indice"
[model.py, comentario de la clase Zone], y esa lectura de indice
pertenece a `report.py`/`search.py`, no a este script (que solo llama a
`zones.load`/`zones.candidates`/`zones.add`).
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
import notes  # noqa: E402
import zones as zones_lib  # noqa: E402
from model import Zone  # noqa: E402


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="zones.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("name")
    add_parser.add_argument("--description", required=True)
    add_parser.add_argument("--aliases", nargs="+", default=())

    subparsers.add_parser("list")

    find_parser = subparsers.add_parser("find")
    find_parser.add_argument("name")

    return parser.parse_args(argv)


def _zones_path():
    root = notes.repo_root()
    pm = notes.pm_root(root)
    return pm / "zones.json"


def _cmd_add(args, path):
    # El NOMBRE de la zona y sus alias van siempre en minuscula [orden
    # del propietario, 2026-08-07: "Boot" y "boot" tecleados en sesiones
    # distintas acababan siendo dos zonas que nunca se cruzaban -- memoria
    # perdida sin un solo error]. `zones_lib.add()` normaliza igual antes
    # de escribir [lib/memory/zones.py::add, docstring] -- normalizar
    # TAMBIEN aqui, antes del rebote, es lo que permite que el propio
    # rebote de mas abajo compare contra el nombre normalizado (si no, un
    # "Boot" tecleado nunca chocaria contra el "boot" ya existente). La
    # descripcion NO se normaliza -- solo el nombre y los alias, que son
    # llaves de busqueda, nunca texto libre [precision del propietario].
    name = zones_lib.normalize(args.name)
    aliases = tuple(zones_lib.normalize(a) for a in args.aliases)

    # El script conoce el estado previo -- `zones_lib.add()` en si mismo
    # no comprueba nada [docstring del modulo, arriba]. Se lee
    # `zones_lib.load(path)` UNA vez, antes de tocar nada: si el nombre
    # ya es una zona canonica, se rebota sin llamar a `add()`, dejando
    # `zones.json` intacto byte a byte -- el fallo real que motiva esto
    # era la segunda alta pisando el alias/descripcion de la primera en
    # silencio.
    existing = zones_lib.load(path)
    if name in existing:
        print(
            f"❌ \"{name}\" ya es una zona -- no se ha tocado zones.json. "
            "Si quieres cambiar su descripcion o sus alias, edita el fichero "
            "a mano (todavia no hay comando de edicion)."
        )
        return 1

    # Mismo rebote, agujero al lado: `name` no es un nombre canonico
    # pero SI es el alias de OTRA zona -- `zones_lib.resolve()` ya sabe
    # aplicar alias [lib/memory/zones.py::resolve], asi que se reusa en
    # vez de recorrer `existing` a mano por segunda vez. Si resuelve a
    # algo (solo puede ser via alias, el caso canonico ya salio arriba),
    # se rebota igual, dejando `zones.json` intacto -- y el mensaje dice
    # DE QUIEN es el alias, porque el nombre tecleado no aparece en
    # ningun listado y un "ya existe" sin decir a quien no le da salida
    # al usuario.
    owner = zones_lib.resolve(name, existing)
    if owner is not None:
        print(
            f"❌ \"{name}\" ya es alias de la zona \"{owner}\" -- no se ha "
            "tocado zones.json. Si quieres cambiar sus alias, edita el "
            "fichero a mano (todavia no hay comando de edicion)."
        )
        return 1

    # `zones.add()` crea el directorio que contiene `path` si falta
    # [lib/memory/zones.py::add, docstring] -- este script no anade
    # ningun mecanismo propio, mismo patron que `indexes.seed()` aplica a
    # su propio directorio.
    zone = Zone(name=name, description=args.description, aliases=aliases)
    zones_lib.add(zone, path)
    total = len(zones_lib.load(path))
    unit = "zona" if total == 1 else "zonas"

    # La normalizacion NO es silenciosa [orden del propietario,
    # 2026-08-07: "se le dice al usuario que se ha normalizado, no en
    # silencio. Lo mismo con los alias"] -- se compara lo tecleado contra
    # lo que de verdad se guardo y, si algo cambio, se enseña.
    changed = []
    if name != args.name:
        changed.append(f"\"{args.name}\" → \"{name}\"")
    for raw, normalized in zip(args.aliases, aliases):
        if raw != normalized:
            changed.append(f"alias \"{raw}\" → \"{normalized}\"")
    notice = f" (normalizado a minuscula: {', '.join(changed)})" if changed else ""

    # El alta YA NO se comitea a si misma [orden del propietario,
    # 2026-08-06: 23 altas de zona en una sola tarde metieron 23 commits
    # propios en el historial -- `zones.json` es fichero de configuracion,
    # no una nota de memoria, y no le corresponde un commit por linea,
    # igual que a `rules.md` (ver `lib/memory/rules.py`)].
    #
    # [corregido 2026-08-06] Este bloque decia hasta hoy que el alta SI se
    # comiteaba a si misma [2026-08-05, hallazgo de Argus reproducido con
    # un `git clone` real] -- lo que sigue vigente de ese hallazgo es el
    # REQUISITO, no el mecanismo de entonces: `zones.json` tiene que
    # acabar versionado en git, porque su DESCRIPCION y sus ALIAS no viven
    # en ningun otro sitio y `rezones` declara expresamente que no los
    # reconstruye [docstring de `rezones.py`]. Sin eso, un clon en otra
    # maquina pierde la zona en silencio -- la unica amenaza que este
    # proyecto declara. Lo que cambia es COMO se cumple ese requisito:
    # antes, un commit propio por cada alta; ahora, `zones.json` se queda
    # modificado en el arbol de trabajo (`zones_lib.add()` ya lo escribe)
    # y viaja dentro del PROXIMO commit real que se haga por otra via
    # (`gitmem work`, `gitmem wip`, `gitmem note`, el cierre de sesion) --
    # las cuatro comitean con `git add --all` sobre las rutas que reciben
    # [`notes_commit.stage_and_commit()`], asi que `zones.json` entra
    # igual que cualquier otro fichero modificado, con solo pasarlo como
    # ruta. No hace falta ningun mecanismo propio aqui para eso.
    print(f"✅ {name} añadida — zones.json tiene {total} {unit}{notice}")
    return 0


def _cmd_list(path):
    # "zones.json no existe" y "zones.json existe pero esta vacio" son dos
    # hechos distintos [encargo del orquestador, 2026-08-06] -- antes de
    # esta linea `zones_lib.load(path)` los devolvia como el mismo `{}`
    # ["Un fichero ausente se trata como 'todavia no hay ninguna zona'",
    # lib/memory/zones.py::load, docstring], y `_cmd_list()` imprimia el
    # mismo "zones.json tiene 0 zonas:" para los dos. La distincion ya
    # existe en produccion, en `health.memory_mounted()` (Aviso B) -- se
    # reutiliza aqui via `health.zones_state()` en vez de anadir una
    # segunda lectura silenciosa del fichero.
    state, _ = health.zones_state(path)
    if state == "absent":
        print("zones.json (no existe) -- todavia no se ha dado de alta ninguna zona.")
        return 0

    zones_map = zones_lib.load(path)
    print(f"zones.json tiene {len(zones_map)} zonas:")
    for name in sorted(zones_map):
        zone = zones_map[name]
        line = f"  {name}   {zone.description}"
        if zone.aliases:
            line += f"   (alias: {', '.join(zone.aliases)})"
        print(line)
    return 0


def _cmd_find(args, path):
    zones_map = zones_lib.load(path)
    matches = zones_lib.candidates(args.name, zones_map)
    if not matches:
        print(f"ninguna zona parecida a «{args.name}» (zones.json tiene {len(zones_map)} zonas)")
        return 0
    print(f"zonas parecidas a «{args.name}»:")
    for zone in matches:
        print(f"  {zone.name}   {zone.description}")
    return 0


def main(argv):
    args = _parse_args(argv)
    path = _zones_path()

    if args.command == "add":
        return _cmd_add(args, path)
    if args.command == "list":
        return _cmd_list(path)
    return _cmd_find(args, path)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # nunca una traza de pila -- PIEZAS.md Sec.10
        print(f"zones.py: {exc}", file=sys.stderr)
        sys.exit(1)
