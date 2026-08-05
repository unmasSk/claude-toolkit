#!/usr/bin/env python3
"""bin/memory/search.py -- el buscador: identificador, zona, palabra o
fichero, siempre un informe -- NUNCA una lista de commits [spec
Sec.8.1, contrato duro].

Contrato: docs/memoria-v2/PIEZAS.md Sec.10 (fila `search.py`). Grammar de
CLI [ASUNCION, sin evidencia posicional directa para `--id`/`--file` --
ver el docstring de test_search_script.py, que la fija antes de que este
fichero existiera]:

    search.py <ZONA-o-PALABRA> [--todo]
    search.py --id <ID> [--todo]
    search.py --file <RUTA> [--todo]

El positional resuelve a zona si `zones.resolve()` lo reconoce (nombre
canonico o alias); si no, se trata como busqueda por palabra -- misma
lectura que ya hace `zones.resolve()` en produccion [docstring del test].

`--id`: siempre enseña la nota y su racimo, nunca una lista de commits --
molde en docs/memoria-v2/TEXTOS.md Sec.2.4 (dictado por el propietario,
2026-08-03), cierra DEUDA.md #24. Se resuelve con `report.build_note()` +
`report_render_note.render_note()`: la cabecera es la NOTA (id, tipo en
castellano, estado vigente/archivada), nunca el inventario de una zona;
lleva sus dos zonas y la fecha real de escritura; el racimo por punteros
Origin/Replaces debajo, solo si algo cuelga de ella; y el pie ofrece la
zona, nunca `--todo` (lo archivado ya sale marcado en el racimo). ANTES
de este molde, `--id` resolvia como el informe COMPLETO de la zona
(`zone1`) con `include_archived=True` siempre -- el fallo que DEUDA.md #24
describe (zona entera, `zone2` ignorada, archivado forzado sin marca, pie
contradictorio ofreciendo `--todo` con lo que ya estaba arriba).

`--file`: mismo contrato duro -- nunca una lista de commits, aunque
`query.by_file` devuelva notas sueltas. Se resuelve como el informe
COMPLETO de cada zona (`zone1`) tocada por al menos una nota que toco esa
ruta, concatenados -- reutiliza `report.build_zone`, nunca reimplementa el
formato.

LIMITACION ESTRUCTURAL, no un caso vacio normal: `query.by_file` hace
`git log -- <ruta>` y solo reconoce como nota los commits de ESE log que
llevan trailers de `notes.write()`. Un commit de nota nunca toca el
fichero de codigo del que habla -- toca solo los indices de memoria
(`pm_root`) -- asi que pedir `--file` sobre un fichero de codigo real
siempre viene vacio, comprobado en vivo (commit real + nota real sobre
ese fichero, cero coincidencias). El aviso de "sin notas" de aqui abajo
lo dice explicito: no es "no hay memoria de este fichero" (dato), es
"esta entrada no puede encontrar memoria de un fichero de codigo"
(limitacion de la propia opcion) -- las dos lecturas no pueden verse
iguales. La alternativa real para preguntar por un fichero es la
busqueda por palabra (su basename o modulo), que es la que usan hoy los
nueve agentes.
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

import notes  # noqa: E402
import query  # noqa: E402
import report  # noqa: E402
import report_render  # noqa: E402
import report_render_note  # noqa: E402
import zones as zones_lib  # noqa: E402


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="search.py")
    parser.add_argument("query", nargs="?", default=None, help="zona o palabra")
    parser.add_argument("--id", default=None)
    parser.add_argument("--file", default=None)
    parser.add_argument("--todo", action="store_true")
    return parser.parse_args(argv)


def _render_by_id(note_id):
    note_report = report.build_note(note_id)
    if note_report is None:
        print(f"search.py: no existe la nota {note_id}", file=sys.stderr)
        return None
    return report_render_note.render_note(note_report)


def _render_by_file(path, include_archived):
    touched = query.by_file(path)
    if not touched:
        return (
            f"search.py: ninguna nota toco {path} -- limitacion conocida de "
            "--file: busca commits que tocan esa ruta exacta, y el commit de "
            "una nota nunca toca el fichero de codigo del que habla (toca "
            "solo los indices de memoria). Para preguntar por un fichero, "
            "usa la busqueda por palabra: search.py <basename o modulo>"
        )
    zones_touched = sorted({n.zone1 for n in touched})
    reports = [
        report_render.render_zone(report.build_zone(z, include_archived))
        for z in zones_touched
    ]
    return "\n\n".join(reports)


def _render_by_query(text, include_archived, pm):
    zones_map = zones_lib.load(pm / "zones.json")
    resolved = zones_lib.resolve(text, zones_map)
    if resolved is not None:
        return report_render.render_zone(report.build_zone(resolved, include_archived))
    return report_render.render_word(report.build_word(text, include_archived))


def main(argv):
    args = _parse_args(argv)

    if args.id is not None:
        text = _render_by_id(args.id)
        if text is None:
            return 1
        print(text)
        return 0

    root = notes.repo_root()
    pm = notes.pm_root(root)

    if args.file is not None:
        print(_render_by_file(args.file, args.todo))
        return 0

    if args.query is None:
        print("search.py: se necesita una zona, una palabra, --id o --file", file=sys.stderr)
        return 1

    print(_render_by_query(args.query, args.todo, pm))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # nunca una traza de pila -- PIEZAS.md Sec.10
        print(f"search.py: {exc}", file=sys.stderr)
        sys.exit(1)
