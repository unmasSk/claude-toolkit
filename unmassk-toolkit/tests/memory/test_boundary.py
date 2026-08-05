"""tests/memory/test_boundary.py -- la puerta 3 de PIEZAS.md Sec.2/Sec.13:
la frontera entre `lib/memory/` y el resto del toolkit que lo aloja.

Contrato: `docs/memoria-v2/PIEZAS.md` Sec.2 ("Las tres puertas contra el
codigo muerto", puerta 3) y Sec.13 ("Los tres tests de frontera"). Los
tres, palabra por palabra de esa tabla:

  1. Nadie de fuera mira hacia dentro -- ningun fichero del toolkit fuera
     de `lib/memory/`, `bin/memory/`, `bin/gitmem`, los 2 hooks
     (`customs.py`, `boot_launcher.py` -- Sec.11: "solo hay dos") y
     `tests/memory/` importa nada de `lib/memory/`.
  2. Nadie de dentro mira hacia fuera -- ningun modulo de `lib/memory/`
     importa nada del toolkit. La lista permitida esta VACIA a proposito:
     solo biblioteca estandar.
  3. Nada exportado sin importador -- toda funcion publica y todo modulo
     de `lib/memory/` tiene al menos un importador real DENTRO DEL
     SISTEMA (produccion: los propios modulos hermanos, los scripts de
     `bin/memory/`, `bin/gitmem`, los 2 hooks -- `tests/memory/` NO
     cuenta: DEUDA.md ya describe el patron exacto que esto existe para
     cazar, "cero llamadores de produccion... lo unico que lo usaba eran
     sus propios tests").

NO escribe el cuarto test de Sec.13.1 (el grafo generado comparado
contra el mermaid de `ARQUITECTURA.md` Sec.4) -- va aparte, encargo
distinto, depende de un documento que este fichero no toca.

Estado real al escribir esto (2026-08-04), verificado ejecutando, no
supuesto: los tests 1 y 2 pasan contra el codigo de verdad -- la
separacion ya se respeta en la practica. **El test 3, en su mitad de
simbolos, NO pasa** -- encuentra codigo publico sin importador real.
Eso no es un fallo de este fichero: es el hallazgo que Sec.13 dice que
existe para sacar a la luz, y no se ajusta el criterio para que pase
[encargo explicito: "si sale rojo, no lo ajustes... dejalo rojo"].

Metodo, y por que -- deliberadamente AST, nunca grep/texto crudo (mismo
criterio que `test_query.py::_git_history_call_sites`, que ya evito una
trampa real: varios ficheros CITAN codigo en su propio docstring para
explicar un arreglo, y un grep a lo bruto lo confundiria con una llamada
real). Recorre el arbol de sintaxis de cada fichero -- nunca una lista de
nombres escrita a mano, que es justo lo que Sec.13 pide evitar ("una
lista a mano es otra cosa que mantener, y envejece igual que el
documento que veniamos de corrigiendo").

Limite conocido, declarado en vez de callado: un import dinamico
(`importlib.import_module("x")`, `__import__("x")`) no aparece en el
arbol de sintaxis como un `Import`/`ImportFrom` y este detector no lo ve.
Verificado antes de escribir esto: `grep -rln "importlib" lib/memory
bin/memory bin/gitmem hooks/customs.py hooks/boot_launcher.py` (y lo
mismo para `__import__`) no da nada -- hoy no hay ninguno en produccion.
Si aparece uno manana,
esta puerta no lo cazara; ese hueco no se tapa aqui por iniciativa
propia (iria contra la propia Sec.0.2 de PIEZAS.md, "un hueco puede ser
deliberado").

Cada uno de los tres detectores se demuestra roto a proposito antes de
confiar en el, contra una copia desechable en `tmp_path` (nunca contra
`lib/memory/` real -- regla del encargo, incidente ya pagado el
2026-08-02 con dos stubs THROWAWAY sueltos en produccion): si el
detector no se dispara ahi, tampoco protege nada de verdad.
"""

import ast
import os
import sys
from pathlib import Path

from .conftest import (
    BIN_MEMORY_DIR,
    GITMEM_BIN,
    HOOKS_DIR,
    LIB_MEMORY_DIR,
    _TOOLKIT_ROOT,
)

TESTS_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "tests", "memory")
MEMORY_HOOK_FILES = (
    os.path.join(HOOKS_DIR, "customs.py"),
    os.path.join(HOOKS_DIR, "boot_launcher.py"),
)


# ---------------------------------------------------------------------------
# Helpers compartidos por los tres detectores -- leen ficheros, nunca los
# ejecutan (evita el problema real medido en `hooks/boot_launcher.py`: lee
# stdin y lanza un subproceso en cuanto se importa, sin guarda de
# `__name__ == "__main__"` -- importarlo de verdad para inspeccionarlo
# colgaria el test esperando stdin).
# ---------------------------------------------------------------------------


def _lib_memory_stems(lib_memory_dir):
    """Los nombres planos de los modulos de `lib/memory/` -- "model",
    "notes", "zones"... -- derivados listando el directorio, nunca escritos
    a mano (Sec.13: "no una lista escrita a mano").
    """
    return sorted(f[:-3] for f in os.listdir(lib_memory_dir) if f.endswith(".py"))


def _parse_file(path):
    return ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))


def _top_level_import_targets(tree):
    """`(lineno, nombre_punteado)` de cada `import X` / `from X import ...`
    en cualquier profundidad del arbol (un import perezoso dentro de una
    funcion tambien cuenta -- `ast.walk` los encuentra igual que los de
    nivel de modulo). Ignora los relativos (`from . import x`, `level > 0`
    ): un import relativo solo puede alcanzar a un hermano dentro de SU
    PROPIO paquete, nunca puede cruzar hacia -- ni salir de -- `lib/memory/`
    desde un fichero que vive en otro sitio del disco. Verificado que hoy
    no hay ninguno en produccion (ver docstring del modulo).
    """
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                hits.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module:
                hits.append((node.lineno, node.module))
    return hits


def _iter_python_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git")]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


# ---------------------------------------------------------------------------
# Test 1 -- "nadie de fuera mira hacia dentro"
# ---------------------------------------------------------------------------


def _is_inside_allowed_zone(path, *, lib_memory_dir, bin_memory_dir, gitmem_bin, hook_files, tests_memory_dir):
    """La zona permitida de Sec.13, tal cual la tabla la enumera: `lib/memory/`,
    `bin/memory/`, `bin/gitmem`, los 2 hooks de memoria y `tests/memory/`.
    Todo lo demas del toolkit es "fuera".
    """
    ap = os.path.abspath(path)
    if ap.startswith(os.path.abspath(lib_memory_dir) + os.sep):
        return True
    if ap.startswith(os.path.abspath(bin_memory_dir) + os.sep):
        return True
    if gitmem_bin and ap == os.path.abspath(gitmem_bin):
        return True
    if ap in {os.path.abspath(h) for h in hook_files}:
        return True
    if ap.startswith(os.path.abspath(tests_memory_dir) + os.sep):
        return True
    return False


def _find_outside_imports_of_lib_memory(
    toolkit_root, *, lib_memory_dir, bin_memory_dir, gitmem_bin, hook_files, tests_memory_dir
):
    """Recorre TODO `.py` del arbol bajo `toolkit_root` que no viva dentro de
    la zona permitida, y marca cualquier import (en cualquier forma: plano
    -- `import model` -- o de paquete -- `import memory.model` / `from
    memory import model`, por si alguien rompe la convencion plana de
    PIEZAS.md Sec.3.3bis) que apunte a un modulo de `lib/memory/`.
    """
    stems = set(_lib_memory_stems(lib_memory_dir))
    violations = {}
    for path in _iter_python_files(toolkit_root):
        if _is_inside_allowed_zone(
            path,
            lib_memory_dir=lib_memory_dir,
            bin_memory_dir=bin_memory_dir,
            gitmem_bin=gitmem_bin,
            hook_files=hook_files,
            tests_memory_dir=tests_memory_dir,
        ):
            continue
        tree = _parse_file(path)
        hits = []
        for lineno, dotted in _top_level_import_targets(tree):
            top = dotted.split(".")[0]
            if top == "memory" or top in stems:
                hits.append(f"{os.path.relpath(path, toolkit_root)}:{lineno} -> import {dotted}")
        if hits:
            violations[os.path.relpath(path, toolkit_root)] = hits
    return violations


def test_no_file_outside_the_allowed_zone_imports_lib_memory():
    """Puerta 3, fila 1 de Sec.13. Sin ella: un modulo del toolkit acaba
    dependiendo de la memoria, y el dia que se quiera borrar el v2 entero
    no se puede -- se lleva por delante el arranque o la instalacion.

    Verificado 2026-08-04 contra el codigo real: pasa. No es una promesa
    del documento, es el resultado de correr este detector sobre los
    ~90 ficheros `.py` del toolkit fuera de la zona permitida.
    """
    violations = _find_outside_imports_of_lib_memory(
        _TOOLKIT_ROOT,
        lib_memory_dir=LIB_MEMORY_DIR,
        bin_memory_dir=BIN_MEMORY_DIR,
        gitmem_bin=GITMEM_BIN,
        hook_files=MEMORY_HOOK_FILES,
        tests_memory_dir=TESTS_MEMORY_DIR,
    )
    assert not violations, (
        "fichero(s) fuera de la zona permitida (lib/memory/, bin/memory/, "
        "bin/gitmem, hooks/customs.py, hooks/boot_launcher.py, "
        f"tests/memory/) importando lib/memory/ directamente: {violations!r}"
    )


def test_outside_import_detector_catches_a_planted_violation(tmp_path):
    """Prueba de fuego de la puerta 1, contra una copia desechable en
    `tmp_path` -- nunca contra `lib/memory/` real (incidente del
    2026-08-02: dos stubs THROWAWAY quedaron sueltos en produccion por
    escribir la prueba de fuego en el sitio equivocado). Si esto no se
    dispara, `test_no_file_outside_the_allowed_zone_imports_lib_memory`
    tampoco protege nada -- solo pasaria porque nunca encuentra nada, no
    porque de verdad vigile.
    """
    fake_root = tmp_path / "toolkit"
    fake_lib_memory = fake_root / "lib" / "memory"
    fake_lib_memory.mkdir(parents=True)
    (fake_lib_memory / "model.py").write_text("class Note:\n    pass\n", encoding="utf-8")

    fake_bin_memory = fake_root / "bin" / "memory"
    fake_bin_memory.mkdir(parents=True)
    fake_gitmem = fake_root / "bin" / "gitmem"
    fake_hooks_dir = fake_root / "hooks"
    fake_hooks_dir.mkdir(parents=True)
    fake_tests_memory = fake_root / "tests" / "memory"
    fake_tests_memory.mkdir(parents=True)

    outsider_dir = fake_root / "skills"
    outsider_dir.mkdir()
    (outsider_dir / "unrelated_skill.py").write_text(
        "import sys\nsys.path.insert(0, '../lib/memory')\nfrom model import Note\n",
        encoding="utf-8",
    )

    violations = _find_outside_imports_of_lib_memory(
        str(fake_root),
        lib_memory_dir=str(fake_lib_memory),
        bin_memory_dir=str(fake_bin_memory),
        gitmem_bin=str(fake_gitmem),
        hook_files=(str(fake_hooks_dir / "customs.py"), str(fake_hooks_dir / "boot_launcher.py")),
        tests_memory_dir=str(fake_tests_memory),
    )
    assert violations, (
        "el detector de la puerta 1 no marco un `from model import Note` "
        "real, escrito a proposito fuera de la zona permitida"
    )


# ---------------------------------------------------------------------------
# Test 2 -- "nadie de dentro mira hacia fuera"
# ---------------------------------------------------------------------------


def _find_inside_imports_of_toolkit(lib_memory_dir):
    """Recorre cada `.py` de `lib/memory/` y marca cualquier import cuyo
    modulo de nivel superior NO sea (a) otro modulo hermano de
    `lib/memory/` -- el unico tipo de import entre hermanos que la
    convencion plana de PIEZAS.md Sec.3.3bis permite -- ni (b) biblioteca
    estandar de Python (`sys.stdlib_module_names`, Python 3.10+). Lo que
    quede es exactamente lo que Sec.13 prohibe: algo del toolkit, o un
    paquete de terceros.
    """
    stems = set(_lib_memory_stems(lib_memory_dir))
    stdlib = set(sys.stdlib_module_names)
    violations = {}
    for fn in sorted(os.listdir(lib_memory_dir)):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(lib_memory_dir, fn)
        tree = _parse_file(path)
        hits = []
        for lineno, dotted in _top_level_import_targets(tree):
            top = dotted.split(".")[0]
            if top in stems:
                continue
            if top in stdlib:
                continue
            hits.append(f"{fn}:{lineno} -> import {dotted}")
        if hits:
            violations[fn] = hits
    return violations


def test_no_lib_memory_module_imports_the_toolkit_or_third_party_code():
    """Puerta 3, fila 2 de Sec.13. La lista de lo que `lib/memory/` puede
    importar del toolkit esta VACIA, a proposito -- el v2 escribe su
    propia capa de git, su candado, su UTF-8 y sus emojis. Sin esta puerta
    vuelve el enredo del v1: una funcion nacida para la memoria acaba
    usandola cinco modulos que no son de memoria, y ya no se puede separar.

    Verificado 2026-08-04 contra el codigo real: pasa, sobre los 31
    ficheros de `lib/memory/`.
    """
    violations = _find_inside_imports_of_toolkit(LIB_MEMORY_DIR)
    assert not violations, (
        f"modulo(s) de lib/memory/ importando algo que no es ni un hermano "
        f"de lib/memory/ ni biblioteca estandar: {violations!r}"
    )


def test_inside_import_detector_catches_a_planted_violation(tmp_path):
    """Prueba de fuego de la puerta 2, contra una copia desechable."""
    fake_lib_memory = tmp_path / "lib_memory"
    fake_lib_memory.mkdir()
    (fake_lib_memory / "model.py").write_text("class Note:\n    pass\n", encoding="utf-8")
    (fake_lib_memory / "notes.py").write_text(
        "import os\nimport json\nfrom model import Note\nimport acme_toolkit_helper\n",
        encoding="utf-8",
    )

    violations = _find_inside_imports_of_toolkit(str(fake_lib_memory))
    assert violations, (
        "el detector de la puerta 2 no marco un `import acme_toolkit_helper` "
        "real, plantado a proposito -- ni stdlib ni hermano de lib/memory/"
    )
    assert "notes.py" in violations


# ---------------------------------------------------------------------------
# Test 3 -- "nada exportado sin importador"
# ---------------------------------------------------------------------------


def _public_top_level_symbols(tree):
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    }


def _analyze_module(tree, stems):
    """Extrae, de UN fichero, lo que hace falta para resolver quien importa
    a quien: sus simbolos publicos declarados, sus `from <hermano> import
    ...` (con su alias si lo hay), sus `import <hermano>` (con su alias) y
    el conjunto de nombres/atributos que el propio codigo USA de verdad
    (`ast.Name`/`ast.Attribute` en contexto `Load`) -- no basta con que algo
    se importe, tiene que aparecer usado (Sec.2, puerta 2: "si el llamador
    declarado no la importa DE VERDAD").
    """
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
    """Sigue la cadena de reexportacion hasta el modulo que DEFINE `symbol`
    de verdad -- sin esto, las cuatro funciones de `format_lines.py`
    saldrian como huerfanas: se reexportan por nombre dentro de `format.py`
    [PIEZAS.md Sec.6.4, docstring de ese fichero: "se importan de forma
    PLANA y se reexponen aqui bajo el mismo nombre... siguen alcanzables
    desde este modulo sin que cambie una firma"], y su unico consumidor
    real (`indexes.py`) las alcanza como `format.build_index_line(...)`,
    nunca `format_lines.build_index_line(...)` -- verificado leyendo
    `indexes.py` antes de escribir esta funcion. Un solo salto no bastaria
    en general (una cadena de reexportaciones podria tener mas de uno);
    `depth` pone un tope de seguridad para no entrar en bucle si dos
    modulos llegaran a reexportarse entre si por error.
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


def _production_files(lib_memory_dir, bin_memory_dir, gitmem_bin, hook_files):
    """Los ficheros que cuentan como "dentro del sistema" para la puerta 3:
    los propios hermanos de `lib/memory/`, los scripts de `bin/memory/`,
    `bin/gitmem` y los 2 hooks. `tests/memory/` NO entra aqui a proposito
    -- un simbolo que solo usan sus propios tests es exactamente el patron
    que Sec.13 existe para cazar (DEUDA.md: "cero llamadores de
    produccion... lo unico que lo usaba eran sus propios tests").
    """
    files = [
        os.path.join(lib_memory_dir, f) for f in sorted(os.listdir(lib_memory_dir)) if f.endswith(".py")
    ]
    if os.path.isdir(bin_memory_dir):
        files += [
            os.path.join(bin_memory_dir, f)
            for f in sorted(os.listdir(bin_memory_dir))
            if f.endswith(".py")
        ]
    if gitmem_bin and os.path.isfile(gitmem_bin):
        files.append(gitmem_bin)
    for h in hook_files:
        if os.path.isfile(h):
            files.append(h)
    return files


def _own_stem_of(path, lib_memory_dir):
    if os.path.dirname(os.path.abspath(path)) != os.path.abspath(lib_memory_dir):
        return None
    base = os.path.basename(path)
    return base[:-3] if base.endswith(".py") else None


def _find_modules_without_importer(lib_memory_dir, bin_memory_dir, gitmem_bin, hook_files):
    stems = _lib_memory_stems(lib_memory_dir)
    stem_set = set(stems)
    prod_files = _production_files(lib_memory_dir, bin_memory_dir, gitmem_bin, hook_files)

    importers = {stem: set() for stem in stems}
    for path in prod_files:
        own_stem = _own_stem_of(path, lib_memory_dir)
        analysis = _analyze_module(_parse_file(path), stem_set)
        referenced = set(analysis["module_aliases"].values()) | {
            src_stem for (src_stem, _sym) in analysis["from_imports"].values()
        }
        for stem in referenced:
            if stem != own_stem:
                importers[stem].add(path)

    return {stem: sorted(files) for stem, files in importers.items() if not files}


def _find_symbols_without_importer(lib_memory_dir, bin_memory_dir, gitmem_bin, hook_files):
    stems = _lib_memory_stems(lib_memory_dir)
    stem_set = set(stems)
    prod_files = _production_files(lib_memory_dir, bin_memory_dir, gitmem_bin, hook_files)
    file_analysis = {p: _analyze_module(_parse_file(p), stem_set) for p in prod_files}

    definer_info = {
        stem: file_analysis[os.path.join(lib_memory_dir, f"{stem}.py")]
        for stem in stems
        if os.path.join(lib_memory_dir, f"{stem}.py") in file_analysis
    }

    symbol_importers = {
        stem: {sym: set() for sym in definer_info[stem]["defined"]} for stem in definer_info
    }

    for path, analysis in file_analysis.items():
        own_stem = _own_stem_of(path, lib_memory_dir)

        for local, (src_stem, src_symbol) in analysis["from_imports"].items():
            owner_stem, owner_symbol = _resolve_owner(src_stem, src_symbol, definer_info)
            if owner_stem == own_stem:
                continue
            if local in analysis["used_names"] and owner_symbol in symbol_importers.get(owner_stem, {}):
                symbol_importers[owner_stem][owner_symbol].add(path)

        for alias, stem in analysis["module_aliases"].items():
            for obj, attr in analysis["used_attrs"]:
                if obj != alias:
                    continue
                owner_stem, owner_symbol = _resolve_owner(stem, attr, definer_info)
                if owner_stem == own_stem:
                    continue
                if owner_symbol in symbol_importers.get(owner_stem, {}):
                    symbol_importers[owner_stem][owner_symbol].add(path)

    return {
        f"{stem}.{sym}": sorted(files)
        for stem, syms in symbol_importers.items()
        for sym, files in syms.items()
        if not files
    }


# ---------------------------------------------------------------------------
# Arbol de dos ramas por simbolo -- reemplaza la lista de excepciones que
# se empezo a escribir para este encargo y el propietario tiro
# [2026-08-04]: "con dos numeros no hay nada que decidir -- 'produccion 0,
# tests 3' es un HECHO, no un veredicto". Nada de tabla de excepciones
# escritas a mano; el arbol se deriva del mismo AST que ya usa el resto
# de este fichero, para los mismos 31 modulos y sus simbolos publicos.
#
# Rama de PRODUCCION: cuantos ficheros -- de `lib/memory/`, `bin/memory/`,
# `bin/gitmem`, los 2 hooks -- importan/llaman el simbolo de verdad.
# Identica a la que ya usa `_find_symbols_without_importer`, pero aqui se
# guarda el conteo completo, no solo los que dan cero.
#
# Rama de TESTS: cuantos TESTS -- funciones `test_*`, nunca ficheros; un
# solo fichero puede tener veintidos tests que tocan la misma pieza, y esa
# diferencia es justo la que hace util la rama -- usan el simbolo de
# verdad. Los tests de este proyecto NUNCA hacen `import indexes` a secas:
# reciben cada modulo de `lib/memory/` como FIXTURE (`tests/memory/
# conftest.py` y cada fichero de test: `@pytest.fixture def indexes():
# return import_lib_memory_module("indexes")`, verificado leyendo
# `test_health.py` antes de escribir esto), y lo usan dentro del cuerpo
# como `indexes.counts(...)`.
#
# CORREGIDO 2026-08-04 [hallazgo del propietario, verificado ejecutando el
# detector contra el repo real: "0 tests" para format.build_subject/
# parse_subject/SubjectParts pese a que test_format.py:380,387,393 los
# llaman de verdad]: el NOMBRE DE LA FIXTURE no siempre es el stem --
# `format` choca con la funcion integrada de Python, asi que NINGUN
# fichero recibe ese modulo bajo su propio nombre (`fmt` en
# test_format.py/test_query.py, `format_mod` en test_customs_hook.py/
# test_notes.py, `format_lib` en test_search_script.py -- verificado
# leyendo los cinco ficheros antes de escribir esto). Comparar el
# PARAMETRO contra el `stem_set` directamente (como hacia esta rama antes)
# nunca podia encontrar `format`, para ningun simbolo suyo, en ningun
# fichero -- el punto ciego no era "faltan tres tests", era estructural:
# CUALQUIER modulo recibido bajo apodo queda invisible entero.
#
# El apodo esta ESCRITO en el propio fichero de test -- no hay que
# adivinarlo: la fixture declara de donde viene con
# `return import_lib_memory_module("<stem>")`. `_fixture_stem_aliases()`
# lee ese enlace por AST (nunca ejecuta el fichero) y devuelve
# `{nombre_de_fixture: stem}` para cada fixture de nivel superior del
# fichero. La rama de tests resuelve el PARAMETRO de cada `def test_*(...)`
# contra ese mapa -- nunca contra el nombre crudo -- y busca, dentro de
# ESE cuerpo, un atributo `parametro.simbolo`, resolviendo el stem real
# (no el alias) antes de consultar `definer_info`/`_resolve_owner`.
#
# CORREGIDO 2026-08-04, ronda 2 [este detector deja de ser exclusivo de
# esta rama -- pasa a `bin/dead-code.py`, herramienta que el propietario
# se lleva a TODOS sus proyectos; "no le voy a dar una herramienta que
# cuenta de menos"]. El orquestador confirmo un segundo punto ciego,
# estructuralmente identico al del apodo (un simbolo con uso real contado
# como cero) pero con dos causas distintas, verificadas leyendo el codigo
# real antes de escribir el arreglo, nunca adivinadas:
#
#  (a) TESTS DENTRO DE UNA CLASE -- `class TestAlgo:` con metodos
#      `def test_*(self, fixture, ...)`. Confirmado por el orquestador:
#      14 de los 36 ficheros de este directorio agrupan sus tests asi.
#      Antes de esto, la rama de tests solo miraba `tree.body` -- el
#      nivel superior del modulo -- y un metodo vive en `ClassDef.body`,
#      nunca ahi: invisible del todo. `_iter_test_functions(tree)` entra
#      un nivel dentro de cada `ClassDef` de `tree.body` y produce
#      `("Clase::metodo", nodo)` -- el mismo formato de node-id que
#      pytest, para que la fila de la tabla sea reconocible. El parametro
#      `self` se descarta explicitamente antes de resolver fixtures (no
#      es una fixture nunca, aunque no habria colisionado con ningun stem
#      real -- se descarta igual, por escrito, no por casualidad).
#
#  (b) VARIABLE DE NIVEL DE MODULO, SIN FIXTURE -- el patron real de
#      `test_utf8.py` linea 20: `utf8 = import_lib_memory_module("utf8")`
#      fuera de cualquier funcion, sin `@pytest.fixture`; los tests lo
#      usan como cierre (closure), nunca como parametro.
#      `_module_level_stem_aliases(tree, stem_set)` lee ese mismo patron
#      literal por AST (asignacion de nivel de modulo a un solo nombre,
#      valor `import_lib_memory_module("<stem>")`) y sus resultados se
#      mezclan con los de la fixture para CADA test del fichero (una
#      variable de modulo es visible en todos, un parametro solo en el
#      suyo -- si coinciden de nombre, el parametro local gana, igual que
#      en Python de verdad).
#
# Verificado que ninguno de los dos arreglos sobre-cuenta: por cada
# patron hay un par de pruebas de fuego en `tmp_path` -- una que plante
# un simbolo SI tocado (debe contar) y otra que plante un SEGUNDO simbolo
# del MISMO modulo/fichero que NINGUN test toca (debe seguir en cero) --
# y ademas, contra el repo real, se leyeron a mano (no solo por el
# detector) tres casos cuyo numero cambio con este arreglo:
# `utf8.force_utf8_streams` (`test_utf8.py::TestForceUtf8StreamsIdempotent
# ::test_calling_twice_keeps_utf8_and_does_not_raise`, linea 82: llamada
# real, no mencion), `report_render.render_zone`/`report.build_zone`
# (`test_search_script.py::TestZoneQueryMatchesTheRealProducerRoundTrip::
# test_zone_report_equals_report_render_render_zone_for_real`, linea 187:
# `report_render_lib.render_zone(report_lib.build_zone(...))`, llamada
# real) y `zones.load` (`test_zones_script.py::
# TestTwoConcurrentRegistrationsDoNotClobberEachOther::
# test_two_zones_py_processes_registering_different_zones_at_once`, linea
# 161: `zones_lib.load(zones_path)`, llamada real). Los tres son llamadas
# de verdad sobre el resultado, no una mencion de paso.
#
# Efecto sobre la tabla de simbolos con produccion == 0 (los 15 de mas
# abajo): NINGUNO -- verificado ejecutando, no supuesto. Los 14 ficheros
# con clases y el patron de `test_utf8.py` si añaden filas a `tests` para
# muchos simbolos CON produccion real (`zones.load`, `report_render.
# render_zone`, `utf8.force_utf8_streams`...), pero ninguno de esos
# simbolos estaba en la lista de produccion == 0 -- que hoy no cambie el
# veredicto es una casualidad de ESTE repositorio, no del diseño: en otro
# proyecto, un simbolo sin produccion cuyo unico test viva dentro de una
# clase habria seguido contando "0 tests" para siempre con la version
# anterior de este detector.
#
# Cada test cuenta UNA vez por simbolo aunque lo use varias veces en su
# cuerpo (`touched_this_test` mas abajo) -- si no, un test con tres
# aserciones sobre el mismo valor inflaria el numero sin aportar una
# segunda opinion mas.
#
# Regla de cuando esto grita, fijada por el propietario, no por este
# fichero: produccion == 0 Y tests == 0 -> rojo (codigo muerto del todo).
# produccion == 0 Y tests >= 1 -> no rojo, pero sale listado para mirarlo
# (es la situacion real medida hoy en `indexes.counts`: 0 produccion, 3
# tests de `test_health.py` que lo usan como segunda opinion de
# `health.coherence()`, unmassk-standards Sec.34). produccion >= 1 -> verde,
# no sale listado -- ya tiene un llamador real, mirarlo no aporta nada.


def _iter_test_files(tests_memory_dir):
    for fn in sorted(os.listdir(tests_memory_dir)):
        if fn.startswith("test_") and fn.endswith(".py"):
            yield os.path.join(tests_memory_dir, fn)


def _is_pytest_fixture_decorator(node):
    """`True` si `node` (un decorador) es `@pytest.fixture` o
    `@pytest.fixture(...)` -- las dos formas que usa `pytest`. Cubre
    tambien `@fixture`/`@fixture(...)` (import directo, `from pytest
    import fixture`) por si algun fichero futuro cambia de estilo --
    verificado que hoy los 25 ficheros de `tests/memory/` hacen `import
    pytest` y usan `@pytest.fixture` (ver docstring de la seccion), pero
    la comprobacion no depende de esa convencion para funcionar.
    """
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr == "fixture"
    if isinstance(target, ast.Name):
        return target.id == "fixture"
    return False


def _fixture_stem_aliases(tree, stem_set):
    """`{nombre_de_fixture: stem}` para cada fixture de NIVEL SUPERIOR de un
    fichero de test cuyo cuerpo es literalmente `return
    import_lib_memory_module("<stem>")` -- el enlace que declara, en el
    propio codigo (nunca adivinado), bajo que nombre llega cada modulo de
    `lib/memory/` a ESTE fichero de test en concreto.

    Existe porque el nombre de la fixture no siempre es el stem: `format`
    choca con la funcion integrada de Python, asi que se recibe como
    `fmt`/`format_mod`/`format_lib` segun el fichero (ver comentario de
    seccion, mas arriba, para los cinco ficheros reales verificados). Sin
    este mapa, la rama de tests solo encuentra un simbolo cuando el
    parametro se llama exactamente igual que el modulo -- y para
    `format.py` eso no ocurre jamas, en ningun fichero.
    """
    aliases = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if not any(_is_pytest_fixture_decorator(d) for d in node.decorator_list):
            continue
        for sub in node.body:
            if not isinstance(sub, ast.Return) or not isinstance(sub.value, ast.Call):
                continue
            call = sub.value
            if not (isinstance(call.func, ast.Name) and call.func.id == "import_lib_memory_module"):
                continue
            if not call.args or not isinstance(call.args[0], ast.Constant):
                continue
            stem = call.args[0].value
            if isinstance(stem, str) and stem in stem_set:
                aliases[node.name] = stem
    return aliases


def _module_level_stem_aliases(tree, stem_set):
    """`{nombre_de_variable: stem}` para cada asignacion de NIVEL DE MODULO
    con la forma literal `nombre = import_lib_memory_module("<stem>")` --
    el segundo patron real de este directorio, distinto del de fixture:
    `test_utf8.py` linea 20 hace exactamente esto (`utf8 =
    import_lib_memory_module("utf8")`, sin `@pytest.fixture`, fuera de
    cualquier funcion) y sus tests lo usan como cierre (closure) --
    `utf8.fuerza_algo(...)` -- nunca como parametro. Antes de esto, ese
    modulo era invisible para la rama de tests exactamente por la misma
    razon estructural que `format.py`: nada en `node.args.args` lo
    delataba, porque nunca llega como argumento.

    Mismo criterio que `_fixture_stem_aliases`: se lee el enlace literal
    del AST, nunca se ejecuta el fichero ni se adivina el nombre.
    """
    aliases = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not (isinstance(call.func, ast.Name) and call.func.id == "import_lib_memory_module"):
            continue
        if not call.args or not isinstance(call.args[0], ast.Constant):
            continue
        stem = call.args[0].value
        if isinstance(stem, str) and stem in stem_set:
            aliases[node.targets[0].id] = stem
    return aliases


def _iter_test_functions(tree):
    """`(qualname, nodo)` de cada funcion `test_*` de un fichero de test --
    de NIVEL DE MODULO (`qualname` = el nombre de la funcion tal cual) o
    de un METODO dentro de una `class Test...:` (`qualname` =
    "Clase::metodo", el mismo formato de node-id que usa pytest de
    verdad). Antes de esto, la rama de tests solo miraba `tree.body`
    -- el nivel superior del modulo -- asi que NINGUN metodo de NINGUNA
    de las catorce clases de prueba de este directorio (de 36 ficheros de
    test) aparecia jamas: mismo sintoma que el apodo de `format.py`
    (simbolo con uso real, contado como cero), causa distinta (la
    funcion vive en `ClassDef.body`, no en `tree.body`).

    Solo entra un nivel dentro de una clase -- no hay clases anidadas en
    ningun fichero de este directorio hoy (verificado antes de escribir
    esto); si aparece una, sus metodos quedarian fuera, mismo criterio de
    "declarar el limite" que el resto de este fichero.
    """
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if (
                    isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and sub.name.startswith("test_")
                ):
                    yield f"{node.name}::{sub.name}", sub


def _symbol_usage_report(lib_memory_dir, bin_memory_dir, gitmem_bin, hook_files, tests_memory_dir):
    """El arbol de dos ramas, por cada simbolo publico de nivel superior
    de `lib/memory/`: `{"stem.simbolo": {"production": [ficheros...],
    "tests": ["fichero.py::test_funcion", ...]}}`. Ninguna rama decide
    sola si el simbolo esta bien o mal -- eso lo hace quien lee el numero
    (o el test que aplica la regla de arriba).
    """
    stems = _lib_memory_stems(lib_memory_dir)
    stem_set = set(stems)
    prod_files = _production_files(lib_memory_dir, bin_memory_dir, gitmem_bin, hook_files)
    file_analysis = {p: _analyze_module(_parse_file(p), stem_set) for p in prod_files}

    definer_info = {
        stem: file_analysis[os.path.join(lib_memory_dir, f"{stem}.py")]
        for stem in stems
        if os.path.join(lib_memory_dir, f"{stem}.py") in file_analysis
    }

    report = {
        f"{stem}.{sym}": {"production": set(), "tests": []}
        for stem in definer_info
        for sym in definer_info[stem]["defined"]
    }

    # Rama de produccion -- misma resolucion de reexport de un salto
    # (_resolve_owner) que usa la mitad de simbolo del test 3 de arriba.
    for path, analysis in file_analysis.items():
        own_stem = _own_stem_of(path, lib_memory_dir)
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

    # Rama de tests -- por FUNCION/METODO test_*, nunca por fichero (ver
    # docstring de la seccion, mas arriba, para el porque del
    # parametro-como-fixture; `_fixture_stem_aliases` resuelve el apodo de
    # `format.py`; `_module_level_stem_aliases` resuelve el patron de
    # `test_utf8.py` -- variable de modulo, sin fixture;
    # `_iter_test_functions` entra en las clases de prueba, no solo en
    # `tree.body`).
    if os.path.isdir(tests_memory_dir):
        for path in _iter_test_files(tests_memory_dir):
            tree = _parse_file(path)
            alias_to_stem = _fixture_stem_aliases(tree, stem_set)
            module_var_to_stem = _module_level_stem_aliases(tree, stem_set)
            for qualname, node in _iter_test_functions(tree):
                # "self" nunca es una fixture -- se descarta explicitamente
                # antes de resolver, no porque coincidiera por accidente
                # (ninguna fixture real se llama "self"), sino para que la
                # regla quede escrita y no dependa de esa casualidad.
                params = {a.arg for a in node.args.args if a.arg != "self"}
                # Resuelve cada PARAMETRO al stem real via el enlace
                # declarado por la fixture -- nunca comparando el nombre
                # del parametro contra el stem directamente (eso es
                # justo lo que no encontraba `format`, aliasado como
                # `fmt`/`format_mod`/`format_lib` segun el fichero).
                param_to_stem = {p: alias_to_stem[p] for p in params if p in alias_to_stem}
                # Las variables de NIVEL DE MODULO (patron `test_utf8.py`)
                # son visibles en CUALQUIER test del fichero por cierre,
                # nunca por parametro -- se mezclan aqui, y un parametro
                # con el mismo nombre (sombra local) gana sobre la global,
                # igual que en Python de verdad.
                name_to_stem = dict(module_var_to_stem)
                name_to_stem.update(param_to_stem)
                if not name_to_stem:
                    continue
                touched_this_test = set()
                for sub in ast.walk(node):
                    if not (
                        isinstance(sub, ast.Attribute)
                        and isinstance(sub.value, ast.Name)
                        and sub.value.id in name_to_stem
                    ):
                        continue
                    owner_stem, owner_symbol = _resolve_owner(
                        name_to_stem[sub.value.id], sub.attr, definer_info
                    )
                    key = f"{owner_stem}.{owner_symbol}"
                    if key in report:
                        touched_this_test.add(key)
                for key in touched_this_test:
                    report[key]["tests"].append(
                        f"{os.path.relpath(path, tests_memory_dir)}::{qualname}"
                    )

    return {
        key: {"production": sorted(v["production"]), "tests": sorted(v["tests"])}
        for key, v in report.items()
    }


def test_every_lib_memory_module_has_a_real_importer():
    """Puerta 3, fila 3 de Sec.13, la mitad de MODULO: cada uno de los 31
    ficheros de `lib/memory/` tiene que aparecer importado -- entero, o
    por al menos uno de sus simbolos -- desde otro fichero de produccion.

    Verificado 2026-08-04: pasa. Los 31 modulos tienen importador real.
    """
    orphans = _find_modules_without_importer(
        LIB_MEMORY_DIR, BIN_MEMORY_DIR, GITMEM_BIN, MEMORY_HOOK_FILES
    )
    assert not orphans, f"modulo(s) de lib/memory/ sin ningun importador real de produccion: {orphans!r}"


def test_module_importer_detector_catches_a_planted_orphan_module(tmp_path):
    """Prueba de fuego de la mitad de modulo de la puerta 3."""
    lib_memory = tmp_path / "lib_memory"
    lib_memory.mkdir()
    (lib_memory / "used.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (lib_memory / "orphan.py").write_text("def g():\n    return 2\n", encoding="utf-8")

    bin_memory = tmp_path / "bin_memory"
    bin_memory.mkdir()
    (bin_memory / "consumer.py").write_text("import used\n\nused.f()\n", encoding="utf-8")

    orphans = _find_modules_without_importer(
        str(lib_memory), str(bin_memory), str(tmp_path / "gitmem"), ()
    )
    assert "orphan" in orphans, "un modulo plantado sin ningun importador no se marco"
    assert "used" not in orphans, "un modulo con importador real se marco por error"


def test_no_public_symbol_has_zero_production_and_zero_tests(capsys):
    """Puerta 3, fila 3 de Sec.13, la mitad de SIMBOLO -- rediseñada
    2026-08-04 [encargo directo del propietario, sustituye la lista de
    excepciones que se habia empezado a escribir para `indexes.counts`
    antes de esto: "con dos numeros no hay nada que decidir"]. Cada
    simbolo publico de nivel superior de `lib/memory/` es un arbol de DOS
    RAMAS -- produccion (ficheros que lo importan/llaman) y tests
    (funciones `test_*` que lo tocan) -- y la unica regla que hace gritar
    a este test es la que fijo el propietario: **produccion == 0 Y tests
    == 0**. Produccion 0 con al menos un test no es rojo -- sale listado
    para mirarlo, nunca oculto.

    Imprime la tabla completa de simbolos con produccion == 0 (rojos y no
    rojos) SIEMPRE, pase o falle el test -- `capsys.disabled()` escribe
    directo a la terminal real, sin pasar por la captura de pytest, para
    que la lista se vea tanto en un `-q` como en cualquier otro modo. Ya
    costo caro una vez en esta obra un chequeo que solo hablaba al fallar
    ("indistinguible de uno que no se ejecuta").

    **ESTADO REAL 2026-08-04, verificado ejecutando esta version tras el
    arreglo del apodo (`_fixture_stem_aliases`), no supuesto:** 15
    simbolos con produccion 0. De ellos, 9 tienen al menos un test y NO
    son rojo: `indexes.counts` (3, segunda opinion de `health.coherence()`
    en `test_health.py`, unmassk-standards Sec.34), `health.coherence_rules`
    (11, `test_boot.py` la llama por su cuenta para comparar contra
    `summary.health.rule_commits`/`rule_lines` de `boot.build()`),
    `health.duplicates` (1, mismo patron contra
    `summary.health.duplicate_ids`), los cuatro `validator.validate_*`
    (`validate_distillation` 1, `validate_fields` 3, `validate_headline` 2,
    `validate_replacement` 1 -- tests directos de su propio comportamiento,
    fixture `validator` sin apodo) y, **hallazgo de este mismo encargo**,
    `format.build_subject` y `format.parse_subject` (1 test cada uno --
    `test_format.py::test_emoji_after_brackets_enforced`, lineas 380 y
    387/393, llamando `fmt.build_subject(note)` / `fmt.parse_subject(...)`
    -- `fmt` es el APODO de `format.py` en ese fichero, `format` choca con
    la funcion integrada de Python). El detector VIEJO (comparar el
    parametro contra el stem, sin resolver la fixture) no podia ver estos
    dos jamas -- exactamente el hallazgo que reporto el propietario.

    **De los 15, quedan 6 con produccion 0 Y tests 0 -- estos SI son el
    hallazgo original, codigo sin llamador de produccion y sin ningun test
    que lo sostenga:** `format.SubjectParts` (el propio `test_format.py`
    lo documenta en su docstring, linea 20-23: "ningun test construye ni
    inspecciona un SubjectParts" -- confirmado, no es un falso negativo del
    detector, es un hueco real), `gitcmd.LockNotReentrantError`,
    `query.is_unborn_branch`, `validator.validate_type`,
    `vocabulary.FieldSpec`, `vocabulary.TypeSpec`. No se decide aqui si
    cada uno debe pasar a privado, ganar un llamador real, o quedarse asi
    -- eso es del propietario (Sec.0.2).

    (`boot.blockers_section`, que aparecia en la lista roja de la version
    anterior de este fichero, ya no sale en absoluto: paso a llamarse
    `_blockers_section` -- privada, ver `lib/memory/vocabulary.py` lineas
    121-128 -- y por tanto ya no es un simbolo PUBLICO que este test deba
    vigilar. No es un efecto de este cambio de aqui.)

    **Resumen para el informe: de las 15 filas de la tabla, 2 eran
    FALSAS antes de este arreglo** -- `format.build_subject` y
    `format.parse_subject` salian con "0 tests" cuando la realidad, escrita
    en el propio `test_format.py`, era "1 test" cada uno. Las otras 13
    filas ya eran correctas (produccion y tests coincidian con lo que el
    codigo hace de verdad). El veredicto de la puerta 3 no cambia --
    sigue habiendo codigo muerto de verdad (6 simbolos) -- pero dos de los
    que antes se contaban como parte de ese muerto no lo eran.
    """
    report = _symbol_usage_report(
        LIB_MEMORY_DIR, BIN_MEMORY_DIR, GITMEM_BIN, MEMORY_HOOK_FILES, TESTS_MEMORY_DIR
    )
    watch_list = {key: v for key, v in report.items() if not v["production"]}

    with capsys.disabled():
        print()
        print(
            "Puerta 3 / Sec.13 -- simbolos publicos de lib/memory/ con "
            "produccion == 0 (arbol de dos ramas, produccion >= 1 no sale "
            "listado porque ya tiene llamador real):"
        )
        print(f"  {'simbolo':<40}{'produccion':>11}{'tests':>8}")
        for key in sorted(watch_list):
            v = watch_list[key]
            print(f"  {key:<40}{len(v['production']):>11}{len(v['tests']):>8}")
        if not watch_list:
            print("  (ninguno -- todo simbolo publico tiene al menos un fichero de produccion)")

    dead = {key: v for key, v in watch_list.items() if not v["tests"]}
    assert not dead, (
        f"{len(dead)} simbolo(s) publico(s) de lib/memory/ con produccion == 0 Y "
        f"tests == 0 -- codigo muerto del todo, nadie lo usa y nadie lo prueba: "
        f"{sorted(dead)!r}"
    )


def test_two_branch_report_flags_a_symbol_with_zero_production_and_zero_tests(tmp_path):
    """Prueba de fuego -- la que de verdad importa de las tres de aqui
    abajo, y la que pidio el propietario explicitamente ("demuestramelo
    rompiendolo"): un simbolo plantado SIN llamador de produccion Y SIN
    ningun test que lo toque tiene que salir con las dos ramas vacias --
    el UNICO caso que la regla fija en rojo. Montado en `tmp_path`, fuera
    del repositorio real -- nunca escribiendo en `lib/memory/` (incidente
    ya pagado 2026-08-02, dos stubs THROWAWAY sueltos en produccion).
    """
    lib_memory = tmp_path / "lib_memory"
    lib_memory.mkdir()
    (lib_memory / "widget.py").write_text("def totally_dead():\n    return 1\n", encoding="utf-8")

    bin_memory = tmp_path / "bin_memory"
    bin_memory.mkdir()
    tests_memory = tmp_path / "tests_memory"
    tests_memory.mkdir()
    (tests_memory / "test_widget.py").write_text(
        "def test_unrelated():\n    assert 1 == 1\n", encoding="utf-8"
    )

    report = _symbol_usage_report(
        str(lib_memory), str(bin_memory), str(tmp_path / "gitmem"), (), str(tests_memory)
    )
    entry = report["widget.totally_dead"]
    assert not entry["production"] and not entry["tests"], (
        "una funcion plantada sin llamador de produccion NI test la marco con "
        f"alguna de las dos ramas no vacia -- el detector no vio el caso mas "
        f"grave que existe: {entry!r}"
    )


def test_two_branch_report_does_not_flag_zero_production_when_a_test_uses_it(tmp_path):
    """Segundo renglon de la tabla del encargo: produccion 0 pero tests
    >= 1 NO cuenta como "0 y 0" -- es la situacion real medida hoy en
    `indexes.counts`. Se reproduce aqui el patron minimo REAL: un
    `@pytest.fixture` que declara el enlace (`return
    import_lib_memory_module("widget")`, nunca `import widget` a secas --
    asi es como los 25 ficheros de test de este proyecto lo hacen,
    confirmado leyendo `test_health.py` antes de escribir el detector) y
    un test que lo recibe como parametro y usa `widget.oracle_fn(...)`
    dentro de su cuerpo.
    """
    lib_memory = tmp_path / "lib_memory"
    lib_memory.mkdir()
    (lib_memory / "widget.py").write_text("def oracle_fn():\n    return 1\n", encoding="utf-8")

    bin_memory = tmp_path / "bin_memory"
    bin_memory.mkdir()
    tests_memory = tmp_path / "tests_memory"
    tests_memory.mkdir()
    (tests_memory / "test_widget.py").write_text(
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def widget():\n"
        "    return import_lib_memory_module('widget')\n"
        "\n"
        "\n"
        "def test_something(widget):\n"
        "    expected = widget.oracle_fn()\n"
        "    expected_again = widget.oracle_fn()\n"  # segundo uso, mismo test: no debe duplicar el conteo
        "    assert expected == expected_again\n",
        encoding="utf-8",
    )

    report = _symbol_usage_report(
        str(lib_memory), str(bin_memory), str(tmp_path / "gitmem"), (), str(tests_memory)
    )
    entry = report["widget.oracle_fn"]
    assert not entry["production"], (
        f"produccion deberia seguir en 0 -- ningun fichero de produccion llama "
        f"widget.oracle_fn: {entry!r}"
    )
    assert entry["tests"] == ["test_widget.py::test_something"], (
        "la rama de tests deberia contar exactamente UN test tocando el "
        f"simbolo (dos usos dentro del MISMO test no duplican el conteo): {entry!r}"
    )


def test_two_branch_report_resolves_a_module_received_under_an_alias(tmp_path):
    """LA prueba que de verdad importa de este encargo -- pedida
    literalmente por el propietario ("demuestrame que la rama de tests
    cuenta bien un modulo que llega con apodo"), montada en `tmp_path`,
    fuera del repositorio real (regla del encargo).

    Reproduce el caso real que el propio propietario reporto, verificado
    ejecutando el detector viejo contra el repo: `format.py` NUNCA se
    recibe bajo su propio nombre en ningun fichero de test -- `format`
    choca con la funcion integrada de Python -- asi que llega bajo un
    apodo declarado por la fixture (`fmt` en test_format.py/test_query.py,
    `format_mod` en test_customs_hook.py/test_notes.py, `format_lib` en
    test_search_script.py). Aqui se reproduce el mismo nombre de modulo y
    el mismo patron exacto de fixture-con-apodo (`fmt`) que usa
    test_format.py de verdad, y se comprueba que la rama de tests
    resuelve el apodo hasta el simbolo real -- nunca por el nombre del
    parametro, que aqui NUNCA coincide con el stem.
    """
    lib_memory = tmp_path / "lib_memory"
    lib_memory.mkdir()
    (lib_memory / "format.py").write_text("def build_thing():\n    return 1\n", encoding="utf-8")

    bin_memory = tmp_path / "bin_memory"
    bin_memory.mkdir()
    tests_memory = tmp_path / "tests_memory"
    tests_memory.mkdir()
    (tests_memory / "test_format.py").write_text(
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def fmt():\n"  # apodo real: "format" no puede ser el nombre de la fixture
        "    return import_lib_memory_module('format')\n"
        "\n"
        "\n"
        "def test_uses_build_thing(fmt):\n"
        "    result = fmt.build_thing()\n"
        "    assert result == 1\n",
        encoding="utf-8",
    )

    report = _symbol_usage_report(
        str(lib_memory), str(bin_memory), str(tmp_path / "gitmem"), (), str(tests_memory)
    )
    entry = report["format.build_thing"]
    assert entry["tests"] == ["test_format.py::test_uses_build_thing"], (
        "un modulo recibido bajo apodo (fixture 'fmt' devolviendo "
        "import_lib_memory_module('format')) no se conto -- el mismo punto "
        f"ciego que el propietario reporto para format.py de verdad: {entry!r}"
    )


def test_two_branch_report_does_not_over_count_an_untouched_symbol_in_an_aliased_module(tmp_path):
    """La simetrica, pedida explicitamente por el propietario ("que un
    simbolo que de verdad no toca ningun test siga contando cero"): en el
    MISMO fichero aliasado de la prueba anterior, un SEGUNDO simbolo del
    mismo modulo que el test nunca toca tiene que seguir en cero. Sin
    esta prueba, un arreglo del apodo demasiado ancho (p.ej. "si la
    fixture aliasa el modulo, marca TODOS sus simbolos como tocados")
    pasaria la prueba de arriba y cambiaria un punto ciego por uno nuevo
    -- exactamente lo que el propietario pidio no hacer.
    """
    lib_memory = tmp_path / "lib_memory"
    lib_memory.mkdir()
    (lib_memory / "format.py").write_text(
        "def build_thing():\n    return 1\n\n\ndef never_touched():\n    return 2\n",
        encoding="utf-8",
    )

    bin_memory = tmp_path / "bin_memory"
    bin_memory.mkdir()
    tests_memory = tmp_path / "tests_memory"
    tests_memory.mkdir()
    (tests_memory / "test_format.py").write_text(
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def fmt():\n"
        "    return import_lib_memory_module('format')\n"
        "\n"
        "\n"
        "def test_uses_build_thing(fmt):\n"
        "    result = fmt.build_thing()\n"
        "    assert result == 1\n",
        encoding="utf-8",
    )

    report = _symbol_usage_report(
        str(lib_memory), str(bin_memory), str(tmp_path / "gitmem"), (), str(tests_memory)
    )
    assert report["format.build_thing"]["tests"] == ["test_format.py::test_uses_build_thing"]
    assert report["format.never_touched"]["tests"] == [], (
        "un simbolo del MISMO modulo aliasado que ningun test toca de verdad "
        f"salio marcado como probado: {report['format.never_touched']!r}"
    )
    assert not report["format.never_touched"]["production"], (
        f"ademas, ese simbolo tampoco tiene produccion en este montaje: "
        f"{report['format.never_touched']!r}"
    )


def test_two_branch_report_resolves_a_test_method_inside_a_class(tmp_path):
    """El primer patron pedido por el propietario para que este detector
    salga de esta rama sin contar de menos (`bin/dead-code.py`, va a
    todos sus proyectos): un test que vive DENTRO de una `class
    TestAlgo:`, exactamente como los catorce ficheros reales de este
    directorio (`test_search_script.py`, `test_boot_launcher.py`,
    `test_wip_script.py`... verificado por el orquestador: 14 de 36).
    Antes de este cambio la rama de tests solo miraba `tree.body` -- el
    metodo vive en `ClassDef.body`, invisible del todo, mismo sintoma que
    el apodo de `format.py` con otra causa.
    """
    lib_memory = tmp_path / "lib_memory"
    lib_memory.mkdir()
    (lib_memory / "widget.py").write_text("def build_thing():\n    return 1\n", encoding="utf-8")

    bin_memory = tmp_path / "bin_memory"
    bin_memory.mkdir()
    tests_memory = tmp_path / "tests_memory"
    tests_memory.mkdir()
    (tests_memory / "test_widget.py").write_text(
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def widget():\n"
        "    return import_lib_memory_module('widget')\n"
        "\n"
        "\n"
        "class TestBuildThing:\n"
        "    def test_uses_build_thing(self, widget):\n"
        "        result = widget.build_thing()\n"
        "        assert result == 1\n",
        encoding="utf-8",
    )

    report = _symbol_usage_report(
        str(lib_memory), str(bin_memory), str(tmp_path / "gitmem"), (), str(tests_memory)
    )
    entry = report["widget.build_thing"]
    assert entry["tests"] == ["test_widget.py::TestBuildThing::test_uses_build_thing"], (
        "un metodo test_* dentro de una clase, usando una fixture real por "
        f"parametro (mas 'self', que no es fixture), no se conto: {entry!r}"
    )


def test_two_branch_report_does_not_over_count_an_untouched_symbol_in_a_test_class(tmp_path):
    """La simetrica del patron de clase -- pedida explicitamente ("que un
    simbolo que ningun test toca, aunque el fichero tenga clases, siga
    contando cero"): en el MISMO fichero con clases de la prueba anterior,
    un SEGUNDO simbolo que ningun metodo toca (ni dentro ni fuera de la
    clase) tiene que seguir en cero. Sin esto, entrar en el cuerpo de la
    clase podria empezar a contar "de mas" -- ver cualquier atributo
    dentro del bloque entero de la clase en vez de solo dentro de CADA
    metodo -- que es exactamente la mentira que preocupa al propietario:
    dar por probado algo que solo se menciona de pasada.
    """
    lib_memory = tmp_path / "lib_memory"
    lib_memory.mkdir()
    (lib_memory / "widget.py").write_text(
        "def build_thing():\n    return 1\n\n\ndef never_touched():\n    return 2\n",
        encoding="utf-8",
    )

    bin_memory = tmp_path / "bin_memory"
    bin_memory.mkdir()
    tests_memory = tmp_path / "tests_memory"
    tests_memory.mkdir()
    (tests_memory / "test_widget.py").write_text(
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def widget():\n"
        "    return import_lib_memory_module('widget')\n"
        "\n"
        "\n"
        "class TestBuildThing:\n"
        "    def test_uses_build_thing(self, widget):\n"
        "        result = widget.build_thing()\n"
        "        assert result == 1\n"
        "\n"
        "    def test_unrelated(self):\n"
        "        assert 1 == 1\n",
        encoding="utf-8",
    )

    report = _symbol_usage_report(
        str(lib_memory), str(bin_memory), str(tmp_path / "gitmem"), (), str(tests_memory)
    )
    assert report["widget.build_thing"]["tests"] == [
        "test_widget.py::TestBuildThing::test_uses_build_thing"
    ]
    assert report["widget.never_touched"]["tests"] == [], (
        "un simbolo del MISMO modulo, en un fichero con clases, que ningun "
        f"metodo toca de verdad salio marcado como probado: "
        f"{report['widget.never_touched']!r}"
    )


def test_two_branch_report_resolves_a_module_level_variable_without_a_fixture(tmp_path):
    """El segundo patron pedido por el propietario: el modulo recibido en
    una VARIABLE DE NIVEL DE MODULO, sin fixture -- el patron real de
    `test_utf8.py` linea 20 (`utf8 = import_lib_memory_module("utf8")`,
    fuera de cualquier funcion, sin `@pytest.fixture`). Los tests lo
    referencian por cierre (closure), nunca como parametro -- antes de
    este cambio, la rama de tests no miraba mas que `node.args.args`, asi
    que este patron era invisible del todo, mismo sintoma que los otros
    dos, tercera causa distinta.
    """
    lib_memory = tmp_path / "lib_memory"
    lib_memory.mkdir()
    (lib_memory / "widget.py").write_text("def build_thing():\n    return 1\n", encoding="utf-8")

    bin_memory = tmp_path / "bin_memory"
    bin_memory.mkdir()
    tests_memory = tmp_path / "tests_memory"
    tests_memory.mkdir()
    (tests_memory / "test_widget.py").write_text(
        "widget = import_lib_memory_module('widget')\n"
        "\n"
        "\n"
        "def test_uses_build_thing():\n"
        "    result = widget.build_thing()\n"
        "    assert result == 1\n",
        encoding="utf-8",
    )

    report = _symbol_usage_report(
        str(lib_memory), str(bin_memory), str(tmp_path / "gitmem"), (), str(tests_memory)
    )
    entry = report["widget.build_thing"]
    assert entry["tests"] == ["test_widget.py::test_uses_build_thing"], (
        "una variable de NIVEL DE MODULO (sin fixture, patron real de "
        f"test_utf8.py) usada por cierre en un test no se conto: {entry!r}"
    )


def test_two_branch_report_does_not_over_count_an_untouched_symbol_via_module_level_variable(
    tmp_path,
):
    """La simetrica del patron de variable de modulo: un SEGUNDO simbolo
    del mismo modulo, en el mismo fichero, que NINGUN test toca tiene que
    seguir en cero -- la variable de modulo es visible en TODOS los tests
    del fichero por cierre, que es justo el riesgo de sobre-contar que
    preocupa al propietario si esto se hiciera mal (marcar el modulo
    entero como "tocado" en vez de cada simbolo por separado).
    """
    lib_memory = tmp_path / "lib_memory"
    lib_memory.mkdir()
    (lib_memory / "widget.py").write_text(
        "def build_thing():\n    return 1\n\n\ndef never_touched():\n    return 2\n",
        encoding="utf-8",
    )

    bin_memory = tmp_path / "bin_memory"
    bin_memory.mkdir()
    tests_memory = tmp_path / "tests_memory"
    tests_memory.mkdir()
    (tests_memory / "test_widget.py").write_text(
        "widget = import_lib_memory_module('widget')\n"
        "\n"
        "\n"
        "def test_uses_build_thing():\n"
        "    result = widget.build_thing()\n"
        "    assert result == 1\n"
        "\n"
        "\n"
        "def test_unrelated():\n"
        "    assert 1 == 1\n",
        encoding="utf-8",
    )

    report = _symbol_usage_report(
        str(lib_memory), str(bin_memory), str(tmp_path / "gitmem"), (), str(tests_memory)
    )
    assert report["widget.build_thing"]["tests"] == ["test_widget.py::test_uses_build_thing"]
    assert report["widget.never_touched"]["tests"] == [], (
        "un simbolo del MISMO modulo, expuesto por la MISMA variable de "
        f"nivel de modulo, que ningun test toca de verdad salio marcado "
        f"como probado: {report['widget.never_touched']!r}"
    )


def test_two_branch_report_counts_a_real_production_file(tmp_path):
    """Simetrico de los dos anteriores: produccion >= 1 se cuenta de
    verdad -- sin esto, las dos pruebas de fuego de arriba podrian pasar
    con una rama de produccion que nunca encuentra nada.
    """
    lib_memory = tmp_path / "lib_memory"
    lib_memory.mkdir()
    (lib_memory / "widget.py").write_text("def used():\n    return 1\n", encoding="utf-8")

    bin_memory = tmp_path / "bin_memory"
    bin_memory.mkdir()
    (bin_memory / "consumer.py").write_text("import widget\n\nwidget.used()\n", encoding="utf-8")
    tests_memory = tmp_path / "tests_memory"
    tests_memory.mkdir()

    report = _symbol_usage_report(
        str(lib_memory), str(bin_memory), str(tmp_path / "gitmem"), (), str(tests_memory)
    )
    entry = report["widget.used"]
    assert entry["production"] == [str(bin_memory / "consumer.py")], (
        f"un fichero de produccion real que llama widget.used() no se conto: {entry!r}"
    )


def test_symbol_importer_detector_catches_a_planted_orphan(tmp_path):
    """Prueba de fuego, caso positivo: una funcion publica que NINGUN
    consumidor de produccion importa tiene que marcarse.
    """
    lib_memory = tmp_path / "lib_memory"
    lib_memory.mkdir()
    (lib_memory / "widget.py").write_text(
        "def used_publicly():\n    return 1\n\n\ndef never_imported_anywhere():\n    return 2\n",
        encoding="utf-8",
    )
    bin_memory = tmp_path / "bin_memory"
    bin_memory.mkdir()
    (bin_memory / "consumer.py").write_text("import widget\n\nwidget.used_publicly()\n", encoding="utf-8")

    orphans = _find_symbols_without_importer(
        str(lib_memory), str(bin_memory), str(tmp_path / "gitmem"), ()
    )
    assert "widget.never_imported_anywhere" in orphans, (
        "una funcion publica plantada sin ningun importador de produccion no se marco"
    )
    assert "widget.used_publicly" not in orphans, "una funcion con importador real se marco por error"


def test_symbol_importer_detector_does_not_flag_a_legitimate_one_hop_reexport(tmp_path):
    """Prueba de fuego, caso negativo -- el que evita que la puerta 3 sea
    demasiado estricta y produzca ruido academico: el mismo patron
    documentado y REAL de `format.py` reexportando `format_lines.py`
    (`from format_lines import build_index_line, ...`, consumido despues
    como `format.build_index_line(...)`, nunca `format_lines.
    build_index_line(...)`) no tiene que marcarse como huerfano.
    """
    lib_memory = tmp_path / "lib_memory"
    lib_memory.mkdir()
    (lib_memory / "inner.py").write_text("def build_thing():\n    return 1\n", encoding="utf-8")
    (lib_memory / "outer.py").write_text("from inner import build_thing\n", encoding="utf-8")

    bin_memory = tmp_path / "bin_memory"
    bin_memory.mkdir()
    (bin_memory / "consumer.py").write_text(
        "import outer\n\nresult = outer.build_thing()\n", encoding="utf-8"
    )

    orphans = _find_symbols_without_importer(
        str(lib_memory), str(bin_memory), str(tmp_path / "gitmem"), ()
    )
    assert "inner.build_thing" not in orphans, (
        "un reexport plano de un solo salto, consumido a traves del modulo que "
        "reexporta -- exactamente el patron real de format.py/format_lines.py -- "
        "se marco como huerfano: falso positivo"
    )
