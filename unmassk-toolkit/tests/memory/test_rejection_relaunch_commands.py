"""Contrato CRUZADO: los comandos `gitmem ...` que el CODIGO DE RECHAZO
ofrece para relanzar, contra el `argparse` REAL de quien los ejecuta --
PIEZAS.md Sec.7.4 ("el rechazo... el comando exacto para relanzar").

Encargo del propietario (2026-08-04): `lib/memory/validator.py:409`
ofrece `gitmem close <id> "..."`. `close` se borro hace dias -- ahora es
`remove` (bin/gitmem, constante `SUBCOMMANDS`), y `remove` exige ademas
`--restriction no|new` (`bin/memory/remove.py:53`, `required=True`), asi
que ni con el nombre corregido funciona.
# [corregido 2026-08-04: la premisa de arriba ("required=True") ya no es
# cierta -- ese mismo dia, DESPUES de escribirse este parrafo, el
# propietario decidio que cerrar una I sin `--restriction` no puede ser
# el error crudo de argparse (P5, TEXTOS.md Sec.1.10), asi que
# `bin/memory/remove.py:53` paso a `default=None` y la pregunta la hace
# `validator.py::validate_incident_close_question`, no argparse. `close`
# SI se corrigio a `remove` en `validator.py:409` ademas -- con los dos
# arreglos, el comando que el rechazo ofrece hoy funciona tal cual, sin
# editar. Se deja el parrafo original sin borrar porque documenta el
# encargo real que disparo este fichero, no el estado actual.]
Este fichero prueba que ESE es
el unico comando muerto entre los que el sistema ofrece hoy -- o que no
lo es, si aparece otro.

POR QUE ESTE TEST SE JUSTIFICA (regla de esta rama, CLAUDE.md: "un test
entra solo si compara dos cosas escritas por separado"): compara el
TEXTO de los rechazos -- escrito en `lib/memory/validator.py`,
`validator_zones.py`, `validator_pointers.py`, `validator_issue.py`,
`rejection.py` y `hooks/customs.py` -- contra el `argparse` REAL de
`bin/gitmem` (constante `SUBCOMMANDS`) y de cada `bin/memory/<sub>.py`
(el objeto `ArgumentParser` que su propia funcion `_parse_args`
construye). Ninguna de las dos listas se teclea a mano en este fichero:
la primera se EXTRAE del AST real de los seis ficheros; la segunda se
OBTIENE construyendo el parser real (ver `_real_parser_for_subcommand`
mas abajo) -- nunca replicada como una lista de flags escrita aqui.

COMO SE EXTRAEN LOS COMANDOS (AST, no una expresion regular sobre texto
suelto): cada rechazo pasa su comando de relanzamiento a
`rejection_.build(..., command=command)` -- SIEMPRE a traves de una
variable local llamada `command` o `relaunch` (comprobado leyendo los
seis ficheros antes de escribir esto: ningun call site pasa un literal
inline). `_extract_commands_from_file` recorre el AST buscando
asignaciones `command = (...)` / `relaunch = (...)` y, por separado,
CUALQUIER cadena suelta del fichero cuyo contenido (tras `.strip()`)
empiece literalmente por `"gitmem "` -- esto ultimo es necesario porque
`validator.py:409` y `validator_zones.py:93` ofrecen un SEGUNDO camino
de relanzamiento dentro de `options` (el texto explicativo), no dentro
del campo `command` -- y el usuario lo ve exactamente igual en pantalla.
Una mencion suelta sin forma de comando (p.ej. "usa `gitmem work`." en
prosa) NO cuenta: no empieza la cadena por "gitmem ", la precede texto
o una comilla invertida.

TRATAMIENTO DE MARCADORES DE HUECO (encargo explicito de la tarea: "lo
que se comprueba es la FORMA del comando, no su contenido"): un
`<TIPO>`, `<zona1>`, `"..."` o cualquier interpolacion real de f-string
(`{note.zone1}`, etc.) se trata como UN valor valido, sea cual sea su
contenido -- nunca se comprueba tipo (`int`) ni `choices`, solo que el
FLAG existe y que ocupa el hueco de un argumento obligatorio. La
notacion `[--flag ...]` (opcional, documental) se retira antes de
tokenizar -- no es sintaxis de shell real, es una convencion de la
propia documentacion del sistema para marcar "esto se puede repetir".

QUE NO COMPRUEBA (limite explicito, para no fabricar un rojo que no
corresponde a esta tarea): NO valida que el valor de un flag tipado
(`--issue`, `type=int`) sea un entero de verdad, ni que un valor con
`choices=` sea uno de ellos -- eso seria comprobar CONTENIDO, no FORMA,
y el encargo pide justo lo contrario. Dos rarezas de forma quedaron
FUERA de este test a proposito, anotadas para quien las quiera cerrar
despues: `validator_issue.py:124` ofrece `--issue <numero real>` --el
UNICO marcador de hueco de los 21 con un espacio interno-- que si se
copiara literal sin sustituir partiria en dos palabras de shell; y
`validator.py:439`/`validator_pointers.py` ofrecen `--origin
<hash1>,<hash2>,...` como un unico token separado por comas, mientras
que `note.py --origin` es `nargs="+"` (varios tokens separados por
espacios) -- ninguna de las dos rompe la comprobacion de "existe /
obligatorio" que pide esta tarea.

Nada de esto se arregla aqui -- Ultron corrige `validator.py` despues.
"""

import argparse
import ast
import importlib.machinery
import importlib.util
import os
import re
import shlex

import pytest

from .conftest import BIN_MEMORY_DIR, GITMEM_BIN, _TOOLKIT_ROOT

# Los seis ficheros cuyo texto de rechazo puede ofrecer un `gitmem ...`
# de relanzamiento -- literal del encargo, no una busqueda mas amplia.
_SOURCE_FILES = (
    os.path.join(_TOOLKIT_ROOT, "lib", "memory", "validator.py"),
    os.path.join(_TOOLKIT_ROOT, "lib", "memory", "validator_zones.py"),
    os.path.join(_TOOLKIT_ROOT, "lib", "memory", "validator_pointers.py"),
    os.path.join(_TOOLKIT_ROOT, "lib", "memory", "validator_issue.py"),
    os.path.join(_TOOLKIT_ROOT, "lib", "memory", "rejection.py"),
    os.path.join(_TOOLKIT_ROOT, "hooks", "customs.py"),
)


# ---------------------------------------------------------------------
# Extraccion: AST real de los seis ficheros, nunca una lista a mano.
# ---------------------------------------------------------------------


def _render_string_node(node):
    """Devuelve el texto literal de un `ast.Constant` (str) o de un
    `ast.JoinedStr` (f-string), sustituyendo cada `{expr}` interpolado
    por un token unico `PLACEHOLDERn` -- sin espacios ni comillas, para
    que la FORMA del shell (que va citado, que no) no cambie respecto a
    lo que produce el codigo real en produccion. Devuelve `None` si el
    nodo no es una cadena (nunca debería pasar dado como se filtra antes
    de llamar a esta funcion, pero es una salida explicita, no un mute).
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        counter = 0
        for value_node in node.values:
            if isinstance(value_node, ast.Constant):
                parts.append(value_node.value)
            elif isinstance(value_node, ast.FormattedValue):
                parts.append(f"PLACEHOLDER{counter}")
                counter += 1
            else:
                return None
        return "".join(parts)
    return None


def _isolate_and_normalize(raw_text):
    """A partir de una cadena que CONTIENE `"gitmem "`, devuelve solo el
    comando desde ahi en adelante (algunos rechazos son compuestos, p.ej.
    `hooks/customs.py`: "git merge --squash <rama> && gitmem work ..."),
    retira la notacion documental `[--flag opcional ...]` (no es sintaxis
    de shell, es una marca de "esto se puede repetir") y colapsa el
    espacio interno de un marcador `<...>` a un solo token (el UNICO caso
    real, `validator_issue.py:124`, "<numero real>" -- ver docstring del
    modulo, "QUE NO COMPRUEBA"). Devuelve `None` si `"gitmem "` no
    aparece en el texto.
    """
    idx = raw_text.find("gitmem ")
    if idx == -1:
        return None
    isolated = raw_text[idx:]
    isolated = re.sub(r"\[[^\[\]]*\]", "", isolated)
    isolated = re.sub(r"<[^<>]*>", lambda m: m.group(0).replace(" ", "_"), isolated)
    return isolated


class _LeafStringVisitor(ast.NodeVisitor):
    """Recorre el AST recogiendo cadenas (`Constant` str / `JoinedStr`)
    como HOJAS: al llegar a un `JoinedStr` NO desciende a sus fragmentos
    internos (`Constant`/`FormattedValue`), porque esos fragmentos son
    trozos parciales de la MISMA cadena (p.ej. solo la mitad de un
    comando, cortada justo antes de una interpolacion) y contarlos por
    separado duplicaria/corromperia la extraccion.
    """

    def __init__(self):
        self.found = []

    def visit_JoinedStr(self, node):  # noqa: N802 (nombre fijado por ast.NodeVisitor)
        self.found.append(node)

    def visit_Constant(self, node):  # noqa: N802
        if isinstance(node.value, str):
            self.found.append(node)


def _extract_commands_from_file(file_path):
    """Devuelve `[(lineno, comando_normalizado), ...]`, deduplicado, para
    un fichero -- combina dos pasadas sobre el MISMO AST:

    Pase A -- asignaciones `command = (...)` / `relaunch = (...)`: el
    campo que PIEZAS.md Sec.7.4 define como "el comando exacto de
    relanzamiento", el unico que todo call site de `rejection_.build`
    usa (verificado con `grep` antes de escribir este fichero: nueve
    `command=command`, dos `command=relaunch`, cero literales inline).
    Permite comandos COMPUESTOS ("X && gitmem Y").

    Pase B -- cualquier cadena suelta del fichero cuyo `.strip()` empiece
    literalmente por `"gitmem "`: cubre los comandos que viven dentro de
    `options` (el texto explicativo), como el propio
    `validator.py:409` ("gitmem close <id> ...") y
    `validator_zones.py:93` ("gitmem rule ..."). Una mencion en prosa
    ("usa `gitmem work`.") no empieza la cadena por "gitmem " -- queda
    fuera sola, sin necesidad de una lista negra de exclusiones.
    """
    with open(file_path, "r", encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=file_path)

    found = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = node.targets
        if len(targets) != 1 or not isinstance(targets[0], ast.Name):
            continue
        if targets[0].id not in ("command", "relaunch"):
            continue
        value = node.value
        elements = value.elts if isinstance(value, (ast.Tuple, ast.List)) else [value]
        for element in elements:
            rendered = _render_string_node(element)
            if rendered is None:
                continue
            normalized = _isolate_and_normalize(rendered)
            if normalized is not None:
                found[(element.lineno, normalized)] = True

    visitor = _LeafStringVisitor()
    visitor.visit(tree)
    for node in visitor.found:
        rendered = _render_string_node(node)
        if rendered is None:
            continue
        stripped = rendered.strip()
        if not stripped.startswith("gitmem "):
            continue
        normalized = _isolate_and_normalize(stripped)
        if normalized is not None:
            found[(node.lineno, normalized)] = True

    return sorted(found.keys())


def _collect_all_commands():
    """Extrae de los seis ficheros reales -- se ejecuta UNA vez, a nivel
    de modulo, para poder parametrizar los tests con un id legible
    (`fichero:linea`) que senale el comando muerto por su nombre, sin
    reextraer en cada test.
    """
    commands = []
    for file_path in _SOURCE_FILES:
        for lineno, command in _extract_commands_from_file(file_path):
            relpath = os.path.relpath(file_path, _TOOLKIT_ROOT)
            commands.append((relpath, lineno, command))
    return commands


ALL_COMMANDS = _collect_all_commands()


# ---------------------------------------------------------------------
# Realidad: el `argparse` real de `bin/gitmem` y de cada script.
# ---------------------------------------------------------------------


def _real_subcommands():
    """Lee `SUBCOMMANDS` de `bin/gitmem` DE VERDAD -- importando el
    fichero real (no tiene extension `.py`, hace falta un loader
    explicito), nunca copiando la tupla a mano en este test.
    """
    loader = importlib.machinery.SourceFileLoader("gitmem_cli_under_test", GITMEM_BIN)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module.SUBCOMMANDS


SUBCOMMANDS = _real_subcommands()


def _import_bin_memory_module(subcommand):
    """Carga `bin/memory/<subcommand>.py` por ruta de fichero -- mismo
    patron que `import_lib_memory_module` de `conftest.py` (nunca por
    `import` con nombre, para no colisionar con ningun paquete de
    test); nombre de modulo prefijado (`bin_memory_<sub>`) para no
    chocar con los hermanos de `lib/memory/` que ese mismo script
    importa de forma PLANA durante su propio `exec_module()` (p.ej.
    `bin/memory/remove.py` hace `import zones as zones_lib`, que registra
    `sys.modules['zones']` -- un nombre plano que SI colisionaria con
    `bin/memory/zones.py` si este loader usara el mismo nombre corto;
    prefijar evita la colision aunque este fichero no necesite cargar
    `bin/memory/zones.py`).
    """
    path = os.path.join(BIN_MEMORY_DIR, f"{subcommand}.py")
    spec = importlib.util.spec_from_file_location(f"bin_memory_{subcommand}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PARSER_CACHE = {}


def _real_parser_for_subcommand(subcommand):
    """Devuelve el `argparse.ArgumentParser` REAL que
    `bin/memory/<subcommand>.py::_parse_args` construye -- sin ejecutar
    `parse_args()` de verdad (que fallaria en alto, o interpretaria
    valores, para cualquier tokenizacion sintetica). Tecnica: parchea
    `ArgumentParser.parse_args` para que devuelva el propio parser en vez
    de parsear, llama a `_parse_args([])` (que construye el parser con
    TODOS sus `add_argument` reales y termina llamando a
    `parser.parse_args([])`, ahora interceptado), y restaura el metodo
    original en un `finally`. El resultado es el objeto `ArgumentParser`
    de produccion, intacto -- ningun flag de este fichero replicado a
    mano.

    Cacheado por subcomando: cada `bin/memory/<sub>.py` solo se importa y
    se construye una vez por sesion de test, aunque varios comandos
    extraidos usen el mismo subcomando.
    """
    if subcommand in _PARSER_CACHE:
        return _PARSER_CACHE[subcommand]

    module = _import_bin_memory_module(subcommand)
    captured = {}
    original_parse_args = argparse.ArgumentParser.parse_args

    def _spy_parse_args(self, args=None, namespace=None):
        captured["parser"] = self
        return argparse.Namespace()

    argparse.ArgumentParser.parse_args = _spy_parse_args
    try:
        module._parse_args([])
    finally:
        argparse.ArgumentParser.parse_args = original_parse_args

    parser = captured["parser"]
    _PARSER_CACHE[subcommand] = parser
    return parser


def _check_tokens_against_real_parser(tokens, parser):
    """Comprueba `tokens` (lo que sigue al subcomando) contra el
    `argparse.ArgumentParser` REAL: que flag exista, y que ningun
    argumento OBLIGATORIO (posicional o `--flag required=True`) falte.

    Nunca llama a `parser.parse_args()` de verdad -- eso comprobaria
    ademas TIPO (`type=int`) y `choices=`, es decir CONTENIDO, que esta
    fuera del alcance de esta tarea (ver docstring del modulo, "QUE NO
    COMPRUEBA"). El consumo de valores por flag SI respeta el `nargs`
    real de cada `Action` (`None` -> 1, entero -> ese numero, `"+"` ->
    todo lo que siga sin pinta de flag) -- leido del propio `Action`,
    nunca adivinado.

    Devuelve una lista de motivos de fallo (vacia si el comando es
    compatible con el parser real).
    """
    option_to_action = parser._option_string_actions
    positional_actions = [a for a in parser._actions if not a.option_strings]
    required_optional_actions = [
        a for a in parser._actions if a.option_strings and a.required
    ]

    reasons = []
    found_flags = set()
    remaining_positional_tokens = []

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            action = option_to_action.get(token)
            if action is None:
                reasons.append(
                    f"flag {token!r} no existe en el argparse real de "
                    f"{parser.prog}"
                )
                i += 1
                continue
            found_flags.add(token)
            nargs = action.nargs
            if nargs is None:
                consume = 1
            elif isinstance(nargs, int):
                consume = nargs
            elif nargs == "+":
                consume = 0
                j = i + 1
                while j < len(tokens) and not tokens[j].startswith("--"):
                    consume += 1
                    j += 1
            else:
                consume = 0
            i += 1 + consume
        else:
            remaining_positional_tokens.append(token)
            i += 1

    for action in required_optional_actions:
        if not any(opt in found_flags for opt in action.option_strings):
            reasons.append(
                f"falta el flag obligatorio {action.option_strings} en "
                f"{parser.prog}"
            )

    required_positional_count = sum(1 for a in positional_actions if a.required)
    if len(remaining_positional_tokens) < required_positional_count:
        required_names = [a.dest for a in positional_actions if a.required]
        reasons.append(
            f"{parser.prog} espera {required_positional_count} argumentos "
            f"posicionales obligatorios {required_names}, el comando trae "
            f"{len(remaining_positional_tokens)} ({remaining_positional_tokens!r})"
        )
    return reasons


def _tokenize(command):
    return shlex.split(command, comments=True)


# ---------------------------------------------------------------------
# Sanidad: el extractor no esta vacio (mutation-check estatico -- si
# ALL_COMMANDS estuviera vacio por un fallo del propio extractor, los
# tests de abajo pasarian en verde sin comprobar nada, un rojo mudo
# disfrazado de exito).
# ---------------------------------------------------------------------


def test_extraction_finds_a_realistic_number_of_relaunch_commands():
    """Guarda de no-vacuidad: a fecha de este test, los seis ficheros
    ofrecen 21 comandos `gitmem ...` de relanzamiento (8 en validator.py,
    5 en validator_zones.py, 2 en validator_pointers.py, 1 en
    validator_issue.py, 0 en rejection.py, 4 en hooks/customs.py -- 0 en
    rejection.py es correcto: es el generador generico, nunca escribe un
    "gitmem" literal). Si un cambio futuro en el extractor lo dejara
    devolviendo una lista vacia (o goteando a un puñado), este test lo
    dice por su nombre en vez de dejar pasar los de abajo en verde por
    no tener nada que comprobar.

    [corregido 2026-08-04: el recuento de arriba (21, con 8 en
    validator.py) ya no es el real -- contado de nuevo agrupando
    `ALL_COMMANDS` por fichero (no a mano: `Counter(relpath for relpath,
    _, _ in ALL_COMMANDS)`), hoy son 23 (11 en validator.py, 5 en
    validator_zones.py, 2 en validator_pointers.py, 1 en
    validator_issue.py, 0 en rejection.py, 4 en hooks/customs.py). La
    diferencia son los dos comandos nuevos que
    `validator.py::validate_incident_close_question` anadio el
    2026-08-04 (`gitmem remove ... --restriction no` / `--restriction
    new ...`, ver PIEZAS.md Sec.7.4 fila 10). El umbral `>= 15` de abajo
    sigue de sobra por debajo de cualquiera de los dos numeros, no hacia
    falta tocarlo.]
    """
    assert len(ALL_COMMANDS) >= 15, (
        f"el extractor solo encontro {len(ALL_COMMANDS)} comandos "
        f"'gitmem ...' en los seis ficheros -- revisa "
        f"_extract_commands_from_file antes de fiarte de los tests "
        f"parametrizados de este fichero"
    )


@pytest.mark.parametrize(
    "relpath, lineno, command",
    ALL_COMMANDS,
    ids=[f"{relpath}:{lineno}" for relpath, lineno, command in ALL_COMMANDS],
)
def test_relaunch_command_subcommand_exists_in_gitmem_dispatch(relpath, lineno, command):
    """Cada `gitmem <subcomando> ...` que un rechazo ofrece tiene que
    despachar a un subcomando REAL -- `bin/gitmem`, constante
    `SUBCOMMANDS`, nunca una lista copiada en este fichero.

    `lib/memory/validator.py:409` falla aqui hoy: ofrece
    `gitmem close <id> "..."`, y `close` no esta en `SUBCOMMANDS` (se
    renombro a `remove`).
    """
    tokens = _tokenize(command)
    subcommand = tokens[1]
    assert subcommand in SUBCOMMANDS, (
        f"{relpath}:{lineno} ofrece `{command}` -- el subcomando "
        f"{subcommand!r} no existe en bin/gitmem (SUBCOMMANDS={SUBCOMMANDS})"
    )


_COMMANDS_WITH_REAL_SUBCOMMAND = [
    (relpath, lineno, command)
    for relpath, lineno, command in ALL_COMMANDS
    if _tokenize(command)[1] in SUBCOMMANDS
]


@pytest.mark.parametrize(
    "relpath, lineno, command",
    _COMMANDS_WITH_REAL_SUBCOMMAND,
    ids=[
        f"{relpath}:{lineno}"
        for relpath, lineno, command in _COMMANDS_WITH_REAL_SUBCOMMAND
    ],
)
def test_relaunch_command_flags_and_required_args_match_real_argparse(
    relpath, lineno, command
):
    """Cada flag que un rechazo usa existe de verdad en el `argparse` del
    script que lo ejecuta, y ningun argumento que ese script declare
    OBLIGATORIO falta -- comprobado contra el `ArgumentParser` real
    (`_real_parser_for_subcommand`), nunca contra una lista de flags
    escrita en este fichero.

    Filtrado a los comandos cuyo subcomando SI existe (el caso contrario
    -- `close` -- ya lo cubre y lo nombra
    `test_relaunch_command_subcommand_exists_in_gitmem_dispatch` sin
    duplicar el fallo aqui con un motivo distinto).
    """
    tokens = _tokenize(command)
    subcommand = tokens[1]
    rest = tokens[2:]
    parser = _real_parser_for_subcommand(subcommand)
    reasons = _check_tokens_against_real_parser(rest, parser)
    assert reasons == [], (
        f"{relpath}:{lineno} ofrece `{command}`, incompatible con el "
        f"argparse real de {subcommand}.py: " + "; ".join(reasons)
    )


def test_close_command_at_validator_py_line_409_dispatches_via_real_gitmem_facade(
    tmp_path,
):
    """Prueba de extremo a extremo (subproceso real, `bin/gitmem` tal
    cual lo invoca un usuario) del comando que `validator.py:409` ofrece
    LITERAL -- extraido del AST real, no retecleado aqui --, para que el
    fallo se vea con la salida real de la fachada, no solo con la
    comprobacion estatica de arriba.

    Hoy `gitmem close ...` rebota con "subcomando desconocido: 'close'"
    (`bin/gitmem::_print_unknown_subcommand`) -- este test afirma que
    DEBERIA despachar (returncode de un subcomando real, nunca el de
    "subcomando desconocido"), y falla mostrando el stderr real de la
    fachada.
    """
    from .conftest import run_gitmem_script

    # Se busca por CONTENIDO, no por numero de linea: clavarlo a la 409
    # hacia que cualquier linea anadida mas arriba de `validator.py`
    # tumbara este test sin que nada del rechazo hubiera cambiado
    # [2026-08-05, tras corregirlo el prefijo `[WIP]`]. Lo que este test
    # vigila es que el rechazo del solapamiento ofrezca un subcomando que
    # exista, no en que renglon vive.
    matches = [
        (relpath, lineno, command)
        for relpath, lineno, command in ALL_COMMANDS
        if relpath.endswith("validator.py") and "--restriction" in command
    ]
    assert matches, (
        "no se extrajo de validator.py ningun comando de cierre de nota -- "
        "el extractor cambio de comportamiento o el rechazo del "
        "solapamiento dejo de ofrecer salida; este test depende de "
        "encontrarlo ahi de verdad, no de un texto fijo"
    )
    relpath, lineno, command = matches[0]
    tokens = _tokenize(command)
    subcommand = tokens[1]

    returncode, stdout, stderr = run_gitmem_script(tokens[1:], cwd=tmp_path)

    assert "subcomando desconocido" not in stderr, (
        f"validator.py:409 sigue ofreciendo un subcomando muerto: "
        f"`{command}` -- bin/gitmem lo rechaza con {stderr.strip()!r} "
        f"(subcomando extraido: {subcommand!r}, no esta en SUBCOMMANDS)"
    )


# RETIRADO 2026-08-04 -- aqui vivio
# `test_close_command_renamed_to_remove_is_still_missing_required_restriction_flag`.
# Cazaba, en rojo, que ni corrigiendo SOLO el nombre del subcomando
# (`close` -> `remove`) el comando de `validator.py:409` funcionaba --
# `remove.py` exige ademas `--restriction no|new`
# (`bin/memory/remove.py:53`, `required=True`), y el texto de entonces no
# lo traia. Fijaba la comparacion por su nombre ("se esperaba que
# validator.py:409 siguiera ofreciendo 'close'") a proposito, para
# caracterizar ESE fallo concreto -- y el propio mensaje de assert ya
# avisaba de su fecha de caducidad: "si esto cambio, Ultron ya corrigio
# el subcomando y este test de caracterizacion sobra".
#
# Ultron corrigio `validator.py:409` (2026-08-04): ahora ofrece
# `gitmem remove <id> "..." --restriction no`, verificado en vivo contra
# un repositorio de prueba real (returncode 0, "D-001 archivada"). Con
# el subcomando corregido, la primera asercion de este test
# (`tokens[1] == "close"`) pasa a fallar por una razon que ya no importa
# -- el texto real ya no dice "close", asi que seguir afirmando que
# DEBERIA decirlo es exactamente el "test academico" que se fija en un
# fallo ya reparado en vez de comparar dos cosas escritas por separado.
# Se retira en vez de arreglarse porque no hay nada que comparar: no
# queda ninguna asuncion de nombre que verificar, solo un hecho pasado.
#
# Lo que cazaba SIGUE cubierto por los dos tests generales de este
# fichero, sin fijar ningun nombre de subcomando ni ningun numero de
# linea (ambos parametrizados sobre `ALL_COMMANDS`, extraido en vivo del
# AST real en cada corrida):
#   - `test_relaunch_command_subcommand_exists_in_gitmem_dispatch` --
#     si alguien vuelve a poner un subcomando que no existe en
#     `SUBCOMMANDS` (en esta linea o en cualquier otra), salta.
#   - `test_relaunch_command_flags_and_required_args_match_real_argparse`
#     -- si a `validator.py:409` (o a cualquier otro comando extraido)
#     le falta `--restriction` u otro flag obligatorio, salta -- se
#     comprobo en vivo ANTES de retirar este test: `_check_tokens_against_real_parser`
#     sobre el texto real de hoy (`remove <id> "..." --restriction no`)
#     devuelve `[]`, y quitando a mano el token `--restriction no` de esa
#     misma comprobacion vuelve a devolver
#     `["falta el flag obligatorio ['--restriction'] en remove.py"]` --
#     el hueco que cazaba el test retirado no queda sin cubrir.
#
# [corregido 2026-08-04: DOS afirmaciones de este bloque describian un
# estado que ya cambio DESPUES de escribirse -- se dejan citadas, no se
# borran, porque narran el motivo real de la retirada:
#   (a) linea 558-559, "`remove.py` exige ademas `--restriction no|new`
#       (`required=True`)" -- ya no es cierto: `bin/memory/remove.py:53`
#       paso a `default=None` el mismo dia (ver correccion al inicio del
#       fichero); la pregunta la hace hoy
#       `validator.py::validate_incident_close_question`, no argparse.
#   (b) linea 589-591, el resultado de la ablacion -- re-ejecutado hoy
#       contra el `remove.py` real (`_check_tokens_against_real_parser`
#       sobre los tokens de `gitmem remove <id> "..."`, SIN
#       `--restriction`) devuelve `[]`, no el mensaje citado: como el
#       flag ya no es `required=True` en el argparse real,
#       `test_relaunch_command_flags_and_required_args_match_real_argparse`
#       NO detectaria hoy que ese flag falte -- esa cobertura concreta
#       (el flag ausente del todo) ya no la da ningun test de este
#       fichero. Lo que SI sigue detectando ese mismo test es un flag
#       INEXISTENTE o un obligatorio-de-verdad ausente (los positionales
#       `id`/`reason`); la pregunta de negocio "una I no se cierra sin
#       contestar" la cubre hoy `test_remove_incident_close_question.py`
#       (ver memoria del agente,
#       incident-close-question-contract-notes.md), no este fichero.]
