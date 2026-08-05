#!/usr/bin/env python3
"""dead-code.py -- detector de codigo muerto de dos ramas, suelto de
cualquier proyecto.

USO (manual, nunca enganchado a una suite ni a un hook -- se ejecuta
cuando tu quieras):

    python3 dead-code.py <ruta-de-codigo> [<ruta-de-codigo> ...] <carpeta-de-tests>

Una o mas rutas de codigo -- cada una una carpeta (recorrida entera) o
un fichero suelto (un hook, un script) -- y SIEMPRE, como ultimo
argumento, la carpeta de tests. Ejemplo real de este mismo proyecto,
que necesita cinco rutas de codigo porque su codigo vive repartido en
cinco sitios distintos (libreria, comandos, un script suelto, dos
hooks):

    python3 dead-code.py lib/memory bin/memory bin/gitmem \\
        hooks/customs.py hooks/boot_launcher.py tests/memory

DALE TODAS LAS RUTAS DONDE VIVE EL CODIGO. Dejarte una fuera no es un
resultado "un poco corto": es que esta herramienta va a ACUSAR DE
MUERTO ALGO QUE ESTA VIVO, en la direccion peligrosa -- porque solo ve
los ficheros que le diste, y un simbolo llamado unicamente desde una
ruta que no le pasaste le parece, desde donde mira, sin llamador. Caso
real, medido en este mismo proyecto: si solo se le pasa ``lib/memory``,
``repo_guard.current_branch`` sale con produccion 0 -- pero SI tiene un
llamador real, en ``bin/memory/wip.py``, y es la comprobacion que
impide que un checkpoint aterrice en la rama principal. Alguien que se
fiara de esa fila y la borrara se quedaria sin esa proteccion sin
notarlo hasta que algo se rompiera. Sale de la tabla en cuanto se le
pasa tambien la carpeta que lo llama.

Por cada simbolo publico de nivel superior (funcion o clase que no
empieza por "_") de cada fichero ``.py`` de las rutas de codigo, cuenta
dos numeros, SIEMPRE por separado -- un test nunca cuenta como
produccion, esa es la diferencia entera con un "grep de quien lo usa":

  produccion  cuantos ficheros que NO son tests usan el simbolo desde
              fuera de su propio fichero (import real, de verdad usado
              en el cuerpo -- no basta con importarlo).
  tests       cuantas FUNCIONES de test (nunca ficheros: un fichero
              puede tener veinte tests sobre la misma pieza) tocan el
              simbolo de verdad.

Como se lee la tabla -- va aqui porque es la unica pagina que alguien
lee antes de borrar algo:

  produccion == 0 Y tests == 0   -> codigo muerto. Nadie lo usa, nadie
                                     lo prueba. Candidato a borrar.
  produccion == 0 Y tests >= 1   -> NO es codigo muerto: es una
                                     herramienta de contraste, algo que
                                     solo usan los tests para comprobar
                                     OTRA pieza (el resultado de A se
                                     compara contra el de B calculado
                                     por otro camino). No se borra.
  produccion >= 1                -> tiene consumidor real. No sale
                                     como fila roja.

Extraido de un detector que vivia pegado a un proyecto concreto
(comparaba una lista fija de zonas del propio repo, escrita a mano en
su propio codigo). Aqui las zonas son exactamente las rutas que le
pases en la linea de comandos -- ninguna ruta viene supuesta ni
adivinada, para que funcione igual en cualquier proyecto y con
cualquier reparto de carpetas.

Metodo: AST, nunca grep/texto crudo -- un docstring que CITA una
llamada para explicar algo no es una llamada real, y un grep a lo
bruto no distingue las dos cosas.

Tres trampas resueltas aqui (ya pagadas una vez, en el detector del que
sale este fichero, contra un proyecto real):

  1. Modulo recibido con APODO. Un fichero de test puede recibir un
     modulo bajo un nombre distinto al suyo (choque con una palabra
     reservada de Python, o simplemente estilo). Si se buscara el
     nombre del fichero a pelo, sus tests serian invisibles. Se
     resuelve leyendo, en el propio AST del fichero de test, dos
     patrones literales: (a) una fixture de pytest cuyo cuerpo es
     ``return <llamada>(...)`` con un argumento de texto que coincide
     con el nombre de un modulo real, y (b) una variable de NIVEL DE
     MODULO con esa misma forma (``nombre = <llamada>("modulo")``,
     sin fixture, usada como cierre). NO se ata al nombre de ninguna
     funcion cargadora en concreto (`import_module`, un cargador
     casero...): cualquier llamada cuyo argumento de texto sea el
     nombre de un modulo real cuenta -- eso es lo que hace que esto
     no dependa de ningun proyecto en particular.
  2. Tests dentro de una CLASE (``class TestAlgo:`` con metodos
     ``def test_*(self, ...)``). Si solo se mirara el nivel superior
     del fichero, una parte de los tests -- a veces la mayoria --
     seria invisible entera.
  3. Modulo en una variable de fichero, SIN apodo ni fixture --
     mismo patron que (1)(b) pero sin decorador.

Y la cuarta, la que hace que esto valga la pena: un test JAMAS cuenta
como produccion, aunque llame al simbolo cien veces.

Limites declarados, no callados:

  - Import dinamico (``importlib.import_module(x)`` con ``x`` NO
    literal, ``__import__(x)``) no aparece en el arbol de sintaxis
    como un Import/ImportFrom -- este detector no lo ve.
  - Convencion de nombre PLANO: el simbolo "propietario" de un modulo
    se identifica por el nombre de fichero (sin ``.py``), no por su
    ruta completa. Si dos ficheros -- en la misma ruta de codigo, en
    subcarpetas distintas, o incluso en dos rutas de codigo distintas
    de las que le pasaste -- comparten nombre, este detector se niega
    a adivinar y sale con un error explicando cual par choca -- no
    mezcla sus simbolos en silencio.
  - Un fichero que no es valido Python (no analiza) se salta con un
    aviso por stderr; no aborta el resto del analisis.
  - No escribe nada. Solo imprime.
"""

import argparse
import ast
import os
import sys
from pathlib import Path

NOISE_DIRS = {"__pycache__"}


# ---------------------------------------------------------------------------
# Lectura de ficheros -- nunca ejecucion. Un fichero que lee stdin o
# lanza un subproceso al importarse (visto en produccion real) colgaria
# el analisis si se intentara `import`; por eso todo aqui es AST puro.
# ---------------------------------------------------------------------------


def _parse_file(path):
    try:
        source = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"aviso: no se pudo leer {path}: {exc}", file=sys.stderr)
        return None
    try:
        return ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        print(f"aviso: no se pudo analizar {path}: {exc}", file=sys.stderr)
        return None


def _iter_py_files(root, *, name_filter):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in NOISE_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(".py") and name_filter(fn):
                yield os.path.join(dirpath, fn)


def _iter_code_files_from_one(code_path):
    """Los ficheros de UNA ruta de codigo, que puede ser una carpeta
    (recorrida entera, solo ``.py``, salvo lo que parece test propio --
    ``test_*.py`` / ``*_test.py``) o un fichero suelto -- un hook, o un
    script sin extension como ``bin/gitmem`` (tiene shebang de Python
    pero no termina en ``.py``). Un fichero dado EXPLICITAMENTE cuenta
    siempre, sin filtrar por nombre ni por extension -- quien lo puso
    en la lista lo puso a proposito, y exigirle ``.py`` dejaria fuera
    justo el caso real que esto existe para cubrir.
    """
    if os.path.isfile(code_path):
        yield code_path
        return
    yield from _iter_py_files(
        code_path, name_filter=lambda fn: not (fn.startswith("test_") or fn.endswith("_test.py"))
    )


def _iter_code_files(code_paths):
    """Todo ``.py`` de produccion de TODAS las rutas de codigo dadas --
    una o varias, carpetas o ficheros sueltos, sin duplicar si dos
    rutas se solapan.
    """
    seen = set()
    for code_path in code_paths:
        for path in _iter_code_files_from_one(code_path):
            if path not in seen:
                seen.add(path)
                yield path


def _iter_test_files(tests_dir):
    return _iter_py_files(tests_dir, name_filter=lambda fn: fn.startswith("test_"))


def _stem_of(path):
    """Nombre "propietario" de un fichero: su nombre base sin ``.py`` --
    o el nombre base tal cual si no tiene esa extension (el caso de un
    fichero suelto sin extension como ``bin/gitmem``, que SI cuenta
    como modulo de produccion cuando se le da explicitamente).
    """
    base = os.path.basename(path)
    return base[:-3] if base.endswith(".py") else base


def _stems_from_files(files):
    """`{nombre_propietario: ruta}` -- la convencion plana, DENTRO de una
    sola ruta de codigo. Si dos ficheros de la MISMA ruta comparten
    nombre (dos subcarpetas suyas, p.ej.), se devuelven aparte como
    colision -- ahi no hay ninguna señal para desempatar, y este
    detector no decide por si solo cual de los dos es "el" modulo.
    """
    stem_to_path = {}
    collisions = {}
    for path in sorted(files):
        stem = _stem_of(path)
        if stem in stem_to_path:
            collisions.setdefault(stem, [stem_to_path[stem]]).append(path)
        else:
            stem_to_path[stem] = path
    return stem_to_path, collisions


def _resolve_stems_across_paths(code_paths):
    """Igual que `_stems_from_files`, pero a traves de VARIAS rutas de
    codigo dadas en la linea de comandos. Un choque DENTRO de una
    misma ruta sigue siendo fatal (sin señal para desempatar). Un
    choque ENTRE dos rutas distintas -- el patron real de este mismo
    proyecto, un script de `bin/memory/boot.py` que envuelve a
    `lib/memory/boot.py` y comparte su nombre -- SI tiene señal: la
    ruta listada ANTES en la linea de comandos gana como definidor
    canonico. La(s) ruta(s) perdedora(s) se siguen analizando como
    consumidoras (lo que importan cuenta), pero sus propios simbolos
    bajo ese nombre no se rastrean -- avisado por stderr, nunca en
    silencio.

    Devuelve `(stem_to_path, shadowed_files, fatal_collisions)`.
    `shadowed_files` es la lista de rutas de fichero que perdieron un
    choque entre rutas -- el llamador las sigue analizando como
    ficheros de produccion normales, solo que sin ser "dueñas" de
    ningun stem.
    """
    stem_to_path = {}
    shadowed_files = []
    fatal_collisions = {}
    for code_path in code_paths:
        local_files = list(_iter_code_files_from_one(code_path))
        local_stems, local_collisions = _stems_from_files(local_files)
        if local_collisions:
            fatal_collisions.update(local_collisions)
            continue
        for stem, path in local_stems.items():
            if stem in stem_to_path:
                print(
                    f"aviso: '{stem}' definido en mas de una ruta de codigo -- "
                    f"se usa {stem_to_path[stem]} como definidor canonico "
                    "(la primera ruta dada en la linea de comandos gana); "
                    f"{path} se trata como consumidor -- sus propios simbolos "
                    "bajo ese nombre no se rastrean.",
                    file=sys.stderr,
                )
                shadowed_files.append(path)
            else:
                stem_to_path[stem] = path
    return stem_to_path, shadowed_files, fatal_collisions


def _resolution_own_stem(path, stem_to_path):
    """El nombre que `path` "posee" a efectos de no contarse a si mismo
    como consumidor externo de sus propios simbolos: su stem real SI es
    el definidor canonico de ese stem; si no (perdio un choque entre
    rutas, ver `_resolve_stems_across_paths`), un valor que NUNCA
    coincide con un stem real -- la propia ruta completa, que siempre
    contiene un separador de carpetas y por tanto no puede ser igual a
    ningun nombre de modulo plano -- para que sus importaciones de
    verdad SI cuenten como uso externo.
    """
    stem = _stem_of(path)
    return stem if stem_to_path.get(stem) == path else path


# ---------------------------------------------------------------------------
# Analisis por fichero -- simbolos publicos declarados, imports que
# apuntan a un modulo hermano (por nombre) y lo que el propio codigo usa
# de verdad (Name/Attribute en contexto Load -- que algo se importe no
# basta, tiene que aparecer usado).
# ---------------------------------------------------------------------------


def _public_top_level_symbols(tree):
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    }


def _analyze_file(tree, stems):
    defined = _public_top_level_symbols(tree)
    from_imports = {}
    module_aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module in stems:
                for alias in node.names:
                    local = alias.asname or alias.name
                    from_imports[local] = (node.module, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in stems:
                    module_aliases[alias.asname or top] = top
    used_names = set()
    used_attrs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            used_attrs.add((node.value.id, node.attr))
    return {
        "defined": defined,
        "from_imports": from_imports,
        "module_aliases": module_aliases,
        "used_names": used_names,
        "used_attrs": used_attrs,
    }


def _resolve_owner(stem, symbol, definer_info, depth=0):
    """Sigue una cadena de reexportacion (``from hermano import X``) hasta
    el modulo que DEFINE `symbol` de verdad, para que un simbolo
    reexportado no salga como huerfano en el modulo que solo lo
    reenvia. Tope de profundidad como salvaguarda ante un ciclo.
    """
    if depth > 8 or stem not in definer_info:
        return stem, symbol
    data = definer_info[stem]
    if symbol in data["defined"]:
        return stem, symbol
    if symbol in data["from_imports"]:
        src_stem, src_symbol = data["from_imports"][symbol]
        return _resolve_owner(src_stem, src_symbol, definer_info, depth + 1)
    return stem, symbol


# ---------------------------------------------------------------------------
# Trampa 1 -- modulo recibido con apodo o en variable de modulo, sin
# atarse al nombre de ninguna funcion cargadora en concreto: cualquier
# llamada con un argumento de texto que coincide con el nombre de un
# modulo real cuenta.
# ---------------------------------------------------------------------------


def _is_pytest_fixture_decorator(node):
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr == "fixture"
    if isinstance(target, ast.Name):
        return target.id == "fixture"
    return False


def _call_stem_arg(call, stems):
    """Si `call` tiene al menos un argumento (posicional o de palabra
    clave) que es una constante de texto igual al nombre de un modulo
    real, devuelve ese nombre. No importa como se llame la funcion --
    es justo lo que permite no depender del nombre de ningun cargador
    de un proyecto concreto.
    """
    literals = [a for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    literals += [
        kw.value
        for kw in call.keywords
        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str)
    ]
    for lit in literals:
        if lit.value in stems:
            return lit.value
    return None


def _fixture_stem_aliases(tree, stems):
    """`{nombre_de_fixture: modulo}` para cada fixture de pytest de NIVEL
    SUPERIOR cuyo cuerpo contiene ``return <llamada>(...)`` con un
    argumento de texto que nombra un modulo real.
    """
    aliases = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if not any(_is_pytest_fixture_decorator(d) for d in node.decorator_list):
            continue
        for sub in node.body:
            if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Call):
                stem = _call_stem_arg(sub.value, stems)
                if stem:
                    aliases[node.name] = stem
                    break
    return aliases


def _module_level_stem_aliases(tree, stems):
    """`{nombre_de_variable: modulo}` para cada asignacion de NIVEL DE
    MODULO con forma ``nombre = <llamada>(...)`` cuyo argumento de
    texto nombra un modulo real -- el mismo patron que la fixture, sin
    decorador, usado como cierre por los tests del fichero.
    """
    aliases = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        stem = _call_stem_arg(node.value, stems)
        if stem:
            aliases[node.targets[0].id] = stem
    return aliases


# ---------------------------------------------------------------------------
# Trampa 2 -- tests dentro de una clase. `_iter_test_functions` entra un
# nivel dentro de cada `ClassDef` de nivel superior y produce
# ("Clase::metodo", nodo) -- mismo formato de node-id que pytest.
# ---------------------------------------------------------------------------


def _iter_test_functions(tree):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name.startswith(
                    "test_"
                ):
                    yield f"{node.name}::{sub.name}", sub


# ---------------------------------------------------------------------------
# El arbol de dos ramas.
# ---------------------------------------------------------------------------


def _scan_production_usage(file_analysis, definer_info, report, stem_to_path):
    """Rama de produccion -- cualquier fichero de las rutas de codigo que
    no sea el propio dueno del simbolo, usandolo de verdad (por
    `from hermano import simbolo` con el nombre local realmente
    referenciado, o por `import hermano` con `hermano.simbolo` usado
    como atributo). Muta `report` in-place.
    """
    for path, analysis in file_analysis.items():
        own_stem = _resolution_own_stem(path, stem_to_path)
        for local, (src_stem, src_symbol) in analysis["from_imports"].items():
            owner_stem, owner_symbol = _resolve_owner(src_stem, src_symbol, definer_info)
            if owner_stem == own_stem:
                continue
            key = f"{owner_stem}.{owner_symbol}"
            if local in analysis["used_names"] and key in report:
                report[key]["production"].add(path)
        for alias, stem in analysis["module_aliases"].items():
            for obj, attr in analysis["used_attrs"]:
                if obj != alias:
                    continue
                owner_stem, owner_symbol = _resolve_owner(stem, attr, definer_info)
                if owner_stem == own_stem:
                    continue
                key = f"{owner_stem}.{owner_symbol}"
                if key in report:
                    report[key]["production"].add(path)


def _touched_symbols_in_test(node, name_to_stem, from_imports, definer_info):
    """Simbolos `(stem, simbolo)` que el CUERPO de un test concreto toca
    de verdad -- por atributo sobre un nombre aliasado (`param.simbolo`)
    o por uso directo de un nombre importado con `from hermano import
    simbolo`. Una funcion aparte solo para mantener el bucle que la
    llama por debajo del limite de tamano.
    """
    touched = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id in name_to_stem:
            touched.add(_resolve_owner(name_to_stem[sub.value.id], sub.attr, definer_info))
        elif isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load) and sub.id in from_imports:
            src_stem, src_symbol = from_imports[sub.id]
            touched.add(_resolve_owner(src_stem, src_symbol, definer_info))
    return touched


def _scan_test_file_usage(path, tests_dir, stems, definer_info, report):
    """Rama de tests para UN fichero -- por FUNCION/METODO test_*, nunca
    por fichero. Resuelve las tres trampas (apodo por fixture, variable
    de modulo, tests dentro de una clase) antes de mirar cada test.
    Muta `report` in-place.
    """
    tree = _parse_file(path)
    if tree is None:
        return
    test_analysis = _analyze_file(tree, stems)
    # Visibles en CUALQUIER test del fichero por cierre: imports
    # normales (`import modulo`) y variables de nivel de modulo con el
    # patron de la trampa 1.
    always_visible = dict(test_analysis["module_aliases"])
    always_visible.update(_module_level_stem_aliases(tree, stems))
    from_imports = test_analysis["from_imports"]
    fixture_aliases = _fixture_stem_aliases(tree, stems)

    for qualname, node in _iter_test_functions(tree):
        params = {a.arg for a in node.args.args if a.arg != "self"}
        name_to_stem = dict(always_visible)
        name_to_stem.update({p: fixture_aliases[p] for p in params if p in fixture_aliases})
        if not name_to_stem and not from_imports:
            continue
        touched = _touched_symbols_in_test(node, name_to_stem, from_imports, definer_info)
        for owner_stem, owner_symbol in touched:
            key = f"{owner_stem}.{owner_symbol}"
            if key in report:
                report[key]["tests"].append(f"{os.path.relpath(path, tests_dir)}::{qualname}")


def _build_file_analysis(stem_to_path, shadowed_files, consumer_paths, stems):
    """El AST-analisis de cada fichero de produccion relevante -- los
    definidores canonicos, los que perdieron un choque entre rutas, y
    los que solo consumen sin auditarse. Una funcion aparte solo para
    mantener `build_report` por debajo del limite de tamano.
    """
    consumer_files = list(_iter_code_files(consumer_paths)) if consumer_paths else []
    file_analysis = {}
    for path in list(stem_to_path.values()) + shadowed_files + consumer_files:
        if path in file_analysis:
            continue
        tree = _parse_file(path)
        if tree is None:
            continue
        file_analysis[path] = _analyze_file(tree, stems)
    return file_analysis


def build_report(code_paths, tests_dir, consumer_paths=()):
    """`{"modulo.simbolo": {"production": [...], "tests": [...]}}` para
    cada simbolo publico de las <rutas-de-codigo> AUDITADAS
    (`code_paths`). `consumer_paths` (opcional) solo cuenta como
    consumidora -- se escanea para ver que importa, pero sus propios
    simbolos no se rastrean (razon completa: `_EPILOG`, seccion
    `--consumidores`; existe para no marcar como "muerto" un script
    que se ejecuta como proceso y al que nadie importa jamas).

    Devuelve `(report, fatal_collisions)` -- `fatal_collisions` no
    vacio significa dos ficheros con el mismo nombre DENTRO de una
    misma ruta (entre rutas distintas se resuelve por orden, avisando,
    ver `_resolve_stems_across_paths`).
    """
    stem_to_path, shadowed_files, fatal_collisions = _resolve_stems_across_paths(code_paths)
    if fatal_collisions:
        return {}, fatal_collisions

    stems = set(stem_to_path)
    file_analysis = _build_file_analysis(stem_to_path, shadowed_files, consumer_paths, stems)

    definer_info = {
        stem: file_analysis[path] for stem, path in stem_to_path.items() if path in file_analysis
    }

    report = {
        f"{stem}.{sym}": {"production": set(), "tests": []}
        for stem in definer_info
        for sym in definer_info[stem]["defined"]
    }

    _scan_production_usage(file_analysis, definer_info, report, stem_to_path)

    if os.path.isdir(tests_dir):
        for path in _iter_test_files(tests_dir):
            _scan_test_file_usage(path, tests_dir, stems, definer_info, report)

    return (
        {
            key: {"production": sorted(v["production"]), "tests": sorted(v["tests"])}
            for key, v in report.items()
        },
        {},
    )


def _print_table(report):
    print(f"{'simbolo':<40}{'produccion':>11}{'tests':>8}")
    for key in sorted(report, key=lambda k: (len(report[k]["production"]), k)):
        v = report[key]
        print(f"  {key:<38}{len(v['production']):>11}{len(v['tests']):>8}")

    dead = sorted(k for k, v in report.items() if not v["production"] and not v["tests"])
    contrast = sorted(k for k, v in report.items() if not v["production"] and v["tests"])

    print()
    print(f"{len(report)} simbolos publicos en total.")
    print(
        f"{len(contrast)} con produccion 0 y al menos un test -- herramienta de "
        "contraste, NO se borra:"
    )
    for key in contrast:
        print(f"  {key}")
    print(f"{len(dead)} con produccion 0 Y tests 0 -- codigo muerto:")
    for key in dead:
        print(f"  {key}")


_USAGE = (
    "dead-code.py <ruta-de-codigo> [<ruta-de-codigo> ...] <carpeta-de-tests>\n"
    "                   [--consumidores <ruta> [<ruta> ...]]"
)

_DESCRIPTION = (
    "Por cada simbolo publico de las <rutas-de-codigo> AUDITADAS, cuenta "
    "cuantos ficheros de produccion (fuera de tests) lo usan y cuantas "
    "funciones de test lo tocan -- dos numeros por separado, un test "
    "nunca cuenta como produccion."
)

_EPILOG = (
    "DALE TODAS LAS RUTAS DONDE VIVE EL CODIGO -- el tuyo y el de lo\n"
    "que lo consume (libreria, comandos, hooks...). Dejarte una fuera\n"
    "no es un resultado neutro: hace que esta herramienta ACUSE DE\n"
    "MUERTO ALGO QUE ESTA VIVO. Ejemplo real, medido en este mismo\n"
    "proyecto: si solo se le pasa 'lib/memory' y se le calla que\n"
    "'bin/memory' existe, 'repo_guard.current_branch' sale con\n"
    "produccion 0 -- pero SI tiene un llamador real, en\n"
    "bin/memory/wip.py, y es la comprobacion que impide que un\n"
    "checkpoint aterrice en la rama principal. Sale de la tabla en\n"
    "cuanto se le pasa tambien esa ruta, como <ruta-de-codigo> o como\n"
    "--consumidores.\n\n"
    "--consumidores es para rutas que SOLO usan tu codigo, pero que tu\n"
    "NO quieres auditar por dead code -- el caso tipico es un script\n"
    "que se ejecuta como proceso (`python3 bin/nota.py`) o un hook: a\n"
    "esos nadie los 'importa' nunca, asi que si se auditaran saldrian\n"
    "SIEMPRE como muertos aunque sean justo el comando que usas cada\n"
    "dia. Se escanean igual para contar lo que consumen, pero sus\n"
    "propios simbolos no entran en la tabla. Cada ruta -- auditada o\n"
    "consumidora -- puede ser una carpeta (recorrida entera) o un\n"
    "fichero suelto (un hook, un script sin extension como un\n"
    "'bin/miherramienta').\n\n"
    "Como se lee la tabla:\n"
    "  produccion==0 y tests==0  -> codigo muerto de verdad, nadie lo\n"
    "                               usa y nadie lo prueba.\n"
    "  produccion==0 y tests>=1  -> NO es codigo muerto: es una\n"
    "                               herramienta de contraste, algo\n"
    "                               que solo usan los tests para\n"
    "                               comprobar OTRA pieza -- hoy eso\n"
    "                               salvo tres funciones que\n"
    "                               sostenian quince comprobaciones.\n"
    "  produccion>=1             -> tiene consumidor real.\n\n"
    "Manual, sin gancho: se ejecuta cuando tu quieras, nunca desde una\n"
    "suite ni un hook automatico."
)


def _build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="dead-code.py",
        usage=_USAGE,
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="ruta",
        help=(
            "una o mas rutas de codigo AUDITADO (carpeta o fichero .py), "
            "seguidas SIEMPRE de la carpeta de tests como ultimo argumento"
        ),
    )
    parser.add_argument(
        "--consumidores",
        nargs="+",
        metavar="ruta",
        default=[],
        help=(
            "rutas adicionales que SOLO consumen el codigo auditado -- "
            "scripts de comandos, hooks -- y no se auditan ellas mismas "
            "(ver el porque en la ayuda de arriba)"
        ),
    )
    return parser


def _print_collision_error(collisions):
    print(
        "error: dos (o mas) ficheros con el mismo nombre en subcarpetas "
        "distintas de la carpeta de codigo -- este detector asume nombre "
        "de fichero plano y unico, y se niega a adivinar cual es el "
        "modulo real:",
        file=sys.stderr,
    )
    for stem, paths in sorted(collisions.items()):
        print(f"  {stem}:", file=sys.stderr)
        for p in paths:
            print(f"    {p}", file=sys.stderr)


def _validate_code_path(code_path):
    if os.path.isdir(code_path) or os.path.isfile(code_path):
        return None
    return f"error: no existe (ni como carpeta ni como fichero): {code_path}"


def main(argv=None):
    args = _build_arg_parser().parse_args(argv)
    if len(args.paths) < 2:
        print(
            "error: hacen falta al menos dos rutas -- una de codigo y, la "
            "ultima siempre, la carpeta de tests",
            file=sys.stderr,
        )
        return 1

    *code_arg_paths, tests_arg_dir = args.paths
    code_paths = [os.path.abspath(p) for p in code_arg_paths]
    consumer_paths = [os.path.abspath(p) for p in args.consumidores]
    tests_dir = os.path.abspath(tests_arg_dir)

    for code_path in code_paths + consumer_paths:
        error = _validate_code_path(code_path)
        if error:
            print(error, file=sys.stderr)
            return 1
    if not os.path.isdir(tests_dir):
        print(f"error: no existe la carpeta de tests: {tests_dir}", file=sys.stderr)
        return 1
    if not any(_iter_code_files(code_paths)):
        print(f"error: ni un fichero .py de produccion bajo {code_paths}", file=sys.stderr)
        return 1

    report, collisions = build_report(code_paths, tests_dir, consumer_paths=consumer_paths)
    if collisions:
        _print_collision_error(collisions)
        return 2

    _print_table(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
