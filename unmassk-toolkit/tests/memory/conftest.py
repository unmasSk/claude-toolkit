"""Fixtures y helpers compartidos para los tests de unmassk-memory (v2).

Paso 0.3 de FASE 0 (ver docs/memoria-v2/PLAN-CONSTRUCCION.md): "un repo
git temporal, helpers para dar de alta notas y aserciones de indice. De
momento solo lo que haga falta para que un test tonto pase; los helpers
de nota se completan en la fase 2."

Escrito desde cero -- no reutiliza ninguna linea de
unmassk-toolkit/tests/conftest.py (restriccion A del plan: "desde cero,
sin reutilizar nada del v1"). Del v1 se hereda la leccion medida (que
forma tiene un fixture de repo temporal que funciona), nunca el codigo.

Regla transversal del plan: los nombres que ve una maquina (funciones,
fixtures, ficheros) van en ingles; los comentarios y docstrings, en
espanol.
"""

import atexit
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Ruta a lib/memory/, derivada del propio fichero -- no depende del cwd
# desde el que se invoque pytest.
_TESTS_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_TESTS_MEMORY_DIR))
LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")

# Cache de modulos ya cargados, keyed por nombre -> (hash de contenido, modulo).
# Sin esto, cada llamada a import_lib_memory_module() para el MISMO fichero
# devolvia un objeto modulo (y por tanto unas clases) distinto -- una
# dataclass congelada compara __class__ antes que los campos, asi que
# `resultado == esperado` fallaba aunque la implementacion fuera correcta.
# Lo sufrieron dos compañeros por separado (test_format.py, test_indexes.py),
# cada uno apañandolo comparando campo a campo en vez de con `==`.
#
# Se cachea por HASH DE CONTENIDO, no por mtime: mtime tiene resolucion de
# segundo en algunos filesystems, y una reescritura rapida del mismo fichero
# dentro de esa ventana pasaria desapercibida -- exactamente el caso que la
# condicion 2 pide cubrir ("un test reescribe el modulo a mitad de sesion").
# Un hash no depende de temporizacion: mismo contenido -> mismo objeto
# (coherente), contenido distinto -> se recarga siempre, sin excepcion.
_MODULE_CACHE = {}


def import_lib_memory_module(module_name):
    """Carga un modulo de lib/memory/ por ruta de fichero, nunca por import.

    Medido en vivo (2026-08-02): `import memory.<x>` con lib/ en sys.path
    colisiona con este mismo directorio, `tests/memory/`, que es un
    paquete Python (tiene `__init__.py`, ver PIEZAS.md 3.3). pytest
    registra `sys.modules['memory']` apuntando a `tests/memory/` ANTES de
    que un test llegue a importar `lib/memory/<x>.py` -- que tambien se
    llamaria `memory.<x>` si `lib/` estuviera en sys.path. Confirmado:
    `import memory.utf8` revienta con
    `ModuleNotFoundError: No module named 'memory.utf8'` porque
    `sys.modules['memory']` ya es `tests/memory/`, que no tiene
    `utf8.py`. Cargar por ruta de fichero (spec_from_file_location)
    nunca pasa por el nombre `memory` en sys.modules, asi que el choque
    no puede ocurrir.

    Si `module_name` no existe todavia en `lib/memory/` (p.ej. `emojis.py`
    antes de que Ultron lo escriba), `spec_from_file_location` no lanza --
    el fallo llega despues, en `exec_module()`, como `FileNotFoundError`.
    Eso es exactamente lo que un test test-first quiere ver: rojo por
    fichero inexistente, no un error de import enmascarado.

    Convencion fijada en PIEZAS.md Sec.3.3bis (2026-08-02, tras un bloqueo
    real): los modulos de `lib/memory/` se importan PLANOS entre si
    (`from model import Note`), nunca relativos (`from .model import
    Note` -- revienta con "attempted relative import with no known
    parent package", porque el modulo cargado por ruta de fichero no
    tiene contexto de paquete) ni via el paquete `memory` (choca con
    `tests/memory/`, ver parrafo de arriba). Para que un import plano
    como ese resuelva, `lib/memory/` tiene que estar en `sys.path` ANTES
    de ejecutar el modulo -- exactamente lo que el toolkit ya hace un
    nivel mas arriba (`sys.path.insert(0, .../lib)` en cada script de
    `bin/`, seguido de imports planos como `from parsing import ...`).
    Se inserta una sola vez (comprobando que no este ya) para no hinchar
    `sys.path` cada vez que un test pide un modulo.

    Esto NO cambia el comportamiento de `FileNotFoundError` de arriba: el
    modulo principal se sigue cargando por ruta explicita, nunca por
    busqueda en `sys.path` -- lo unico que `sys.path` resuelve son los
    imports PLANOS que el propio modulo haga hacia sus hermanos durante
    `exec_module()`.

    Cacheado por hash de contenido (ver `_MODULE_CACHE` arriba): dos
    llamadas para el mismo `module_name` con el fichero sin cambios
    devuelven el MISMO objeto modulo (mismas clases, `==` entre dataclasses
    funciona con normalidad). Si el fichero cambia entre dos llamadas
    (p.ej. Ultron reescribe `zones.py` a mitad de sesion), el hash ya no
    coincide y se recarga desde cero -- ningun test recibe una version
    vieja del modulo. Un fichero que no existe se abre para hashear ANTES
    de tocar la cache, asi que `FileNotFoundError` sigue siendo el mismo
    error, con el mismo mensaje, que lanzaba `exec_module()` antes de este
    cambio -- no un error nuevo ni enmascarado.

    REGISTRO BAJO EL NOMBRE PLANO, no `lib_memory_<x>` (arreglado
    2026-08-02, ver memoria del agente: "doble registro del mismo
    model.py"). El sintoma real: `model.py` cargado dos veces con dos
    nombres -- este cargador lo registraba como `lib_memory_model`,
    mientras que cualquier modulo hermano cargado por AQUI que hiciera
    `from model import ZoneReport` (la convencion PLANA obligatoria de
    Sec.3.3bis) disparaba el mecanismo NORMAL de import de Python, que
    busca `model` en `sys.path`, no lo encuentra en `sys.modules`, lo
    carga el SOLO por su cuenta (sin pasar por esta funcion) y lo registra
    como `sys.modules['model']` -- un objeto de modulo DISTINTO, con sus
    propias clases. Una dataclass congelada compara `__class__ is
    other.__class__` antes que los campos, asi que
    `isinstance(build_zone(...), model.ZoneReport)` fallaba con un
    `AssertionError` que decia, literalmente, que un `ZoneReport` no era
    un `ZoneReport` -- dos clases identicas en todo menos en cual de los
    dos `sys.modules` las creo.

    El arreglo: cargar SIEMPRE bajo el nombre plano (`module_name`, no
    `f"lib_memory_{module_name}"`) y registrar `sys.modules[module_name]
    = mod` ANTES de `exec_module()` (patron estandar para que un import
    circular o un hermano que se cargue durante `exec_module()` encuentre
    la MISMA instancia via `sys.modules`, en vez de disparar una segunda
    carga por su cuenta). Con esto, si el test pide `model` ANTES que
    `zones`, el `from model import ZoneReport` de `zones.py` encuentra
    `sys.modules['model']` ya puesto por esta funcion y reutiliza esas
    mismas clases -- una sola identidad.

    Pero el orden inverso (pedir `zones` sin haber pedido `model` antes)
    sigue siendo posible -- ningun test esta obligado a pedir sus
    dependencias en un orden concreto. En ese caso, `zones.py` dispara el
    import PLANO natural de Python durante su propio `exec_module()`, que
    carga `model.py` "el solo" y lo registra en `sys.modules['model']`
    ANTES de que esta funcion llegue a pedirlo. Por eso, antes de crear
    una carga nueva, se comprueba si `sys.modules[module_name]` ya existe
    Y su `__file__` apunta al MISMO fichero de `lib/memory/` -- si es
    asi, se adopta ese objeto como el canonico (se guarda en
    `_MODULE_CACHE` tal cual) en vez de crear un segundo objeto con las
    mismas clases pero distinta identidad. Verificado en vivo en los dos
    ordenes (ver memoria del agente para el detalle).
    """
    if LIB_MEMORY_DIR not in sys.path:
        sys.path.insert(0, LIB_MEMORY_DIR)

    path = os.path.join(LIB_MEMORY_DIR, f"{module_name}.py")

    with open(path, "rb") as fh:
        content_hash = hashlib.sha256(fh.read()).hexdigest()

    cached = _MODULE_CACHE.get(module_name)
    if cached is not None and cached[0] == content_hash:
        return cached[1]

    # Ya cargado de forma NATURAL por el import plano de un hermano
    # (p.ej. `zones.py` haciendo `from model import ZoneReport` durante su
    # propio `exec_module()`, antes de que este test pidiera `model`
    # explicitamente) -- adoptarlo tal cual, nunca crear un segundo
    # objeto para el mismo fichero.
    existing = sys.modules.get(module_name)
    existing_path = getattr(existing, "__file__", None)
    if existing is not None and existing_path and os.path.abspath(existing_path) == path:
        _MODULE_CACHE[module_name] = (content_hash, existing)
        return existing

    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    # Registrar ANTES de ejecutar (patron estandar de importlib): si el
    # propio modulo, durante su exec, hace `from model import X` y ESE
    # import dispara a su vez la carga de otro hermano que importa este
    # mismo `module_name` (ciclo, o simplemente un hermano cargado
    # despues via esta misma funcion), encuentra ya esta instancia en
    # `sys.modules` en vez de crear una segunda.
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)

    _MODULE_CACHE[module_name] = (content_hash, mod)
    return mod


def _real_repo_root():
    """Resuelve la raiz del repositorio git REAL (nunca un `tmp_repo` de
    test), fijando el cwd de esta llamada a `_TESTS_MEMORY_DIR` -- un
    directorio que ningun test cambia jamas, a diferencia del cwd del
    proceso, que si puede moverse durante un test (`_cwd()`,
    `monkeypatch.chdir()`).
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=_TESTS_MEMORY_DIR,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


_REAL_REPO_ROOT = _real_repo_root()


def _real_repo_head():
    """SHA de HEAD del repositorio real -- se compara antes/despues de
    cada test como red de seguridad (ver
    `_guard_against_writing_to_the_real_repo` mas abajo).
    """
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_REAL_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture(autouse=True)
def _guard_against_writing_to_the_real_repo(request):
    """Red de seguridad, no un envoltorio que hay que recordar poner:
    ningun test de `tests/memory/` puede terminar habiendo movido HEAD
    del repositorio git REAL (la raiz del proyecto -- nunca el
    `tmp_repo` temporal de cada test). Compara el SHA de HEAD del repo
    real antes y despues de CADA test (autouse, se aplica a todos sin
    que ningun fichero de test tenga que pedirla); si cambio, el test
    falla en el acto, con el nodeid y un recordatorio de la causa mas
    probable.

    Incidente real que motiva esto (2026-08-02): cuatro filas de siembra
    en `test_notes.py` (filas 7-10, cinco llamadas a `notes.write()` en
    total) invocaban esa funcion FUERA del `with _cwd(root):` que
    envuelve el resto del fichero. `notes.write()` resuelve el
    repositorio por el cwd del PROCESO -- sin ese envoltorio, escribia
    contra el repositorio real de este proyecto. Resultado medido: 70
    commits falsos en la rama y 8 ficheros de indice sueltos en la raiz
    del proyecto, uno por cada ejecucion de la suite completa.

    Se compara el SHA de HEAD, no el numero de commits (`rev-list
    --count`): detecta tambien un commit --amend o un cambio de rama, no
    solo un commit nuevo al final.
    """
    before = _real_repo_head()
    yield
    after = _real_repo_head()
    if before and after and before != after:
        pytest.fail(
            f"{request.node.nodeid!r} movio HEAD del repositorio git REAL "
            f"({_REAL_REPO_ROOT!r}): {before!r} -> {after!r}. Alguna "
            "llamada de escritura (notes.write/replace/close/write_work, "
            "gitcmd.commit/commit_empty, context.write, rules.add...) se "
            "invoco sin `with _cwd(tmp_repo):` / `monkeypatch.chdir"
            "(tmp_repo)' por delante -- toda escritura real de un test "
            "tiene que ir contra `tmp_repo`, nunca contra este repositorio.",
            pytrace=False,
        )


# Los cuatro scripts de escritura (capa 5, PIEZAS.md Sec.10) viven en
# bin/memory/, hermana de tests/memory/ bajo la raiz del toolkit --
# ninguno existe todavia (2026-08-02, contrato en rojo).
BIN_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "bin", "memory")


def run_memory_script(script_name, args, cwd, env=None):
    """Ejecuta `bin/memory/<script_name>` como PROCESO SEPARADO (nunca
    importando sus funciones -- PIEZAS.md Sec.10, "Como se prueban": "un
    script se prueba como lo usa una persona"), con `cwd` fijado a un
    repositorio real (normalmente `tmp_repo`, a veces una subcarpeta
    suya -- ver `test_repo_resolved_by_process_cwd*` en cada fichero de
    contrato).

    Devuelve `(returncode, stdout, stderr)`. `env` son variables que se
    AÑADEN al entorno heredado del proceso de test (nunca lo sustituyen
    entero): el caso de uso real es forzar una consola de codepage
    restringido (`PYTHONIOENCODING=cp1252`) para probar que la primera
    sentencia de cada script (`force_utf8_streams()`, ya en produccion
    en `lib/memory/utf8.py`) protege el rechazo con emojis sin heredar
    un `PATH`/`HOME` roto que impida a git funcionar dentro del proceso
    hijo.

    Con el script todavia sin existir, esta llamada falla con el
    `returncode` que Python le da a "no se pudo abrir el fichero"
    (stderr tipo `can't open file '...': [Errno 2] No such file or
    directory`) -- el ROJO real de este contrato, no un rechazo de la
    aduana ni un error de git.
    """
    script_path = os.path.join(BIN_MEMORY_DIR, script_name)
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    result = subprocess.run(
        [sys.executable, script_path, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full_env,
    )
    return result.returncode, result.stdout, result.stderr


# CI incident (2026-08-22): tres ficheros de esta carpeta escribian un
# `gh` FALSO en un directorio propio y lo ANTEPONIAN al `PATH` heredado
# (`fake_dir + os.pathsep + os.environ["PATH"]`), asumiendo que "primero
# en el PATH" basta para ganar siempre. En local (`gh` autenticado) esto
# funciona; en ubuntu-latest/windows-latest (gh real presente, SIN
# credenciales) el `gh` de verdad se ejecuto en su lugar y fallo con su
# propio mensaje de autenticacion -- confirmado reproduciendo la caida
# en vivo: si el `gh` falso no es ejecutable por CUALQUIER motivo,
# `execvp`/`posix_spawnp` (POSIX) NO lanza un error -- sigue buscando en
# el resto del `PATH` y ejecuta silenciosamente el siguiente candidato
# real (comportamiento POSIX documentado, reproducido aqui con un
# `chmod(0o644)` deliberado sobre el falso: el resultado fue la MISMA
# forma de fallo que did el runner). Anteponer no es suficiente cuando
# el candidato real sigue estando en el `PATH` como red de reserva
# silenciosa.
#
# Arreglo (solo en tests, nunca en produccion): construir el `PATH` del
# proceso hijo SIN ningun directorio que contenga un `gh` real -- asi,
# si el falso alguna vez no se pudiera ejecutar, la busqueda no tiene a
# donde caer y `validator_issue.py::issue_exists()` lo convierte en un
# `RuntimeError` claro ("no se pudo ejecutar 'gh'"), nunca en el `gh`
# real ejecutandose sin avisar. Generaliza el patron que ya existia,
# aislado, en `test_work_issue_field.py::_path_without_gh` (solo lo
# usaba el caso "gh no esta instalado") a los tres ficheros que fabrican
# un `gh` falso.
#
# REAPARICION del mismo incidente (CI run 32895458657, commit d9cec70,
# 2026-08-25): el arreglo de arriba filtraba el DIRECTORIO entero que
# contuviera un `gh` real -- correcto mientras `gh` y `git` viven en
# sitios distintos (macOS local, Homebrew), pero en `ubuntu-latest`
# ambos conviven en `/usr/bin`, asi que quitar el directorio se llevo
# `git` por delante y 37 tests cayeron con "git no encontrado". En local
# no se reproducia porque nunca coinciden en el mismo directorio.
#
# Arreglo definitivo: filtrar por FICHERO, no por directorio. Cuando un
# directorio del `PATH` contiene un `gh` real, no se descarta entero --
# se reconstruye en un directorio de scratch con un symlink a cada
# entrada EXCEPTO `gh`/`gh.exe`/`gh.cmd`/`gh.bat`, y ese directorio de
# scratch sustituye al original en el `PATH` devuelto. `git` (y
# cualquier otro binario que comparta carpeta con `gh`) sigue siendo
# localizable; solo `gh` desaparece. Symlinks, nunca copias -- barato
# incluso cuando el directorio real tiene cientos de entradas
# (`/usr/bin`), y si el sistema no soporta symlinks (`OSError`) cae a
# una copia real de esa entrada concreta, nunca del directorio completo.
_GH_FAKE_NAMES = ("gh", "gh.exe", "gh.cmd", "gh.bat")

# Cache por directorio real -- si el mismo directorio (p.ej. `/usr/bin`)
# aparece varias veces en el PATH o se pide en varias llamadas dentro de
# la misma sesion de test, se reconstruye una sola vez. Limpiado al
# salir del proceso, nunca dentro del test (el PATH devuelto puede seguir
# vivo en un `subprocess.run` en marcha).
_SANITIZED_GH_FREE_DIRS = {}


def _cleanup_sanitized_gh_free_dirs():
    for sanitized_dir in _SANITIZED_GH_FREE_DIRS.values():
        shutil.rmtree(sanitized_dir, ignore_errors=True)


atexit.register(_cleanup_sanitized_gh_free_dirs)


def _dir_without_gh(real_dir):
    """Devuelve un directorio equivalente a `real_dir` pero sin ningun
    `gh` real -- cada entrada que NO sea `gh` se enlaza (symlink) tal
    cual, asi que `git` u otro binario que viva en el mismo sitio que
    `gh` (caso `/usr/bin` en ubuntu-latest) sigue siendo localizable.
    """
    if real_dir in _SANITIZED_GH_FREE_DIRS:
        return _SANITIZED_GH_FREE_DIRS[real_dir]
    sanitized_dir = tempfile.mkdtemp(prefix="path-without-gh-")
    try:
        entries = os.listdir(real_dir)
    except OSError:
        entries = []
    for entry in entries:
        if entry in _GH_FAKE_NAMES:
            continue
        src = os.path.join(real_dir, entry)
        dst = os.path.join(sanitized_dir, entry)
        try:
            os.symlink(src, dst)
        except OSError:
            # Sistema sin soporte de symlinks (raro) -- copia real de
            # ESTA entrada concreta, nunca del directorio completo.
            try:
                shutil.copy2(src, dst)
            except OSError:
                continue
    _SANITIZED_GH_FREE_DIRS[real_dir] = sanitized_dir
    return sanitized_dir


def path_without_real_gh():
    """El `PATH` heredado por el proceso de test, con cada directorio
    que contenga un `gh` real SUSTITUIDO por una copia sin `gh` (nunca
    eliminado entero) -- nunca un `PATH` vacio ni un `PATH` que pierda
    `git`/`python3`/cualquier otro binario que los scripts bajo prueba
    necesiten de verdad, aunque ese binario comparta carpeta con `gh`
    (ubuntu-latest: `git` y `gh` conviven en `/usr/bin`). Filtra por
    CONTENIDO real de cada directorio (`gh` en POSIX, `gh.exe`/`gh.cmd`/
    `gh.bat` en Windows), nunca por una ruta fija -- portable a
    cualquier maquina donde `gh` viva en otro sitio.
    """
    dirs = os.environ.get("PATH", "").split(os.pathsep)
    kept = []
    for d in dirs:
        has_real_gh = any(
            os.path.isfile(os.path.join(d, name)) for name in _GH_FAKE_NAMES
        )
        kept.append(_dir_without_gh(d) if has_real_gh else d)
    return os.pathsep.join(kept)


GITMEM_BIN = os.path.join(_TOOLKIT_ROOT, "bin", "gitmem")


def run_gitmem_script(args, cwd, env=None):
    """Ejecuta `bin/gitmem` (la fachada -- vive un nivel mas arriba que
    los diez scripts que despacha, NO dentro de `bin/memory/`) como
    PROCESO SEPARADO -- mismo contrato exacto que `run_memory_script()`
    de aqui arriba: nunca se importa, `cwd` fijado a un repositorio real,
    `env` AÑADE al entorno heredado sin sustituirlo.

    `bin/gitmem` todavia no existe (2026-08-02, contrato en rojo,
    PIEZAS.md Sec.10, fila `bin/gitmem`) -- con el fichero ausente esta
    llamada falla con el mismo `returncode`/stderr de "no se pudo abrir
    el fichero" que ya documenta `run_memory_script()` para los cuatro
    scripts de escritura.
    """
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    result = subprocess.run(
        [sys.executable, GITMEM_BIN, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full_env,
    )
    return result.returncode, result.stdout, result.stderr


# Los tres hooks (capa 6, PIEZAS.md Sec.11) viven en hooks/, hermana de
# bin/ bajo la raiz del toolkit. boot_launcher.py todavia no existe
# (2026-08-02, contrato en rojo).
HOOKS_DIR = os.path.join(_TOOLKIT_ROOT, "hooks")


def run_hook_with_payload(hook_name, payload, cwd, env=None):
    """Ejecuta `hooks/<hook_name>` como PROCESO SEPARADO -- asi es como lo
    invoca Claude Code de verdad: el evento le llega por la ENTRADA
    ESTANDAR como JSON, nunca importando sus funciones. `payload` es un
    dict que se serializa con `json.dumps` y se manda por stdin.

    `cwd` fija el directorio de trabajo del proceso hijo -- el mismo que
    Claude Code establece de verdad al lanzar un hook. Los tests de este
    fichero fijan `cwd` y `payload["cwd"]` al MISMO valor a proposito: cual
    de los dos usa el lanzador para resolver el repositorio no esta escrito
    en ningun documento, y afirmar uno concreto seria fijar una decision
    que vive dentro del propio hook (justo lo que el contrato prohibe). Con
    los dos iguales, el resultado no depende de cual gane.

    Devuelve `(returncode, stdout, stderr)`. `env` son variables que se
    AÑADEN al entorno heredado del proceso de test (nunca lo sustituyen
    entero) -- mismo contrato que `run_memory_script`.

    Con el hook todavia sin existir, esta llamada falla con el
    `returncode` que Python le da a "no se pudo abrir el fichero" -- el
    ROJO real de este contrato.
    """
    return run_hook_raw_stdin(hook_name, json.dumps(payload), cwd, env=env)


def run_hook_raw_stdin(hook_name, raw_stdin, cwd, env=None):
    """Igual que `run_hook_with_payload`, pero manda `raw_stdin` (una
    cadena) tal cual por la entrada estandar, sin pasar por
    `json.dumps` -- para probar stdin vacio o JSON mal formado, casos
    donde el payload real no aplica.
    """
    hook_path = os.path.join(HOOKS_DIR, hook_name)
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    result = subprocess.run(
        [sys.executable, hook_path],
        input=raw_stdin,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full_env,
    )
    return result.returncode, result.stdout, result.stderr


def make_session_start_payload(cwd, source="startup"):
    """El payload REAL que Claude Code manda a un hook `SessionStart`,
    medido contra la referencia oficial (no inventado): campos comunes a
    todo hook -- `session_id`, `transcript_path`, `cwd`, `permission_mode`,
    `hook_event_name` -- mas los propios de `SessionStart` -- `source`
    (`startup`/`resume`/`clear`/`compact`), `model` [fuente:
    `hook-development/references/hook-input-schemas.md`, skill oficial de
    `plugin-dev`, seccion "Common Fields (All Hooks)" + "SessionStart"].
    `hooks/session-start-boot.py` (el SessionStart del sistema viejo, vivo
    en esta rama) no sirve como fuente de la forma del payload -- no lee
    stdin en absoluto, resuelve todo por `git` contra el cwd del proceso.
    """
    return {
        "session_id": "test-session-abc123",
        "transcript_path": "/tmp/fake-transcript.jsonl",
        "cwd": cwd,
        "permission_mode": "default",
        "hook_event_name": "SessionStart",
        "source": source,
        "model": "claude-test-model",
    }


_NOTE_ID_FROM_SUCCESS_RE = re.compile(r"[✅]\s*([A-Z]-\d+)\s+guardada")


def extract_note_id(stdout):
    """El identificador real que `note.py` acaba de asignar, leido de SU
    PROPIA confirmacion (`"✅ {id} guardada..."`, `bin/memory/note.py::
    _print_success`) -- nunca inventado ni derivado contando notas: el
    contador real de `ids.next_id()` es la unica fuente de verdad de que
    numero le tocaba, y este helper solo lo LEE de vuelta.
    """
    match = _NOTE_ID_FROM_SUCCESS_RE.search(stdout)
    assert match is not None, (
        f"no se encontro un identificador de nota en la salida de note.py: {stdout!r}"
    )
    return match.group(1)


def seed_note_via_script(
    repo,
    note_type,
    zone1,
    zone2,
    headline,
    *,
    why=None,
    description=None,
    stops=None,
    keys=None,
    origin=None,
    replaces=None,
    awaits=None,
    issue=None,
):
    """Da de alta una nota REAL invocando `bin/memory/note.py` como
    PROCESO -- no `notes.write()` en proceso. `note.py` ya existe y su
    contrato esta en verde (capa 5, tanda anterior): sembrar a traves de
    el ejercita la ruta completa (validador real incluido, mismo camino
    que usaria una persona) en vez de saltarsela -- mismo criterio que ya
    elige `test_close_script.py` para `notes.write()` en proceso cuando
    su escritor todavia no existia como script, aplicado aqui al reves
    (el escritor SI existe ya).

    No siembra `zones.json` por su cuenta -- un test puede querer varias
    notas en la MISMA pareja de zonas sin repetir el alta; llama a
    `seed_zones_json(repo, [zone1, zone2])` ANTES si hace falta.

    Devuelve `(returncode, stdout, stderr)` tal cual, sin revenir por su
    cuenta: quien llama decide si una siembra fallida tiene que tumbar el
    test (una siembra que falla en silencio dejaria el resto del test
    construido sobre una nota que nunca llego a escribirse).
    """
    args = [note_type, "--zones", zone1, zone2, headline]
    if why is not None:
        args += ["--why", why]
    if description is not None:
        args += ["--description", description]
    if stops is not None:
        args += ["--stops", stops]
    if keys:
        args += ["--keys", *keys]
    if origin:
        args += ["--origin", *origin]
    if replaces is not None:
        args += ["--replaces", replaces]
    if awaits is not None:
        args += ["--awaits", awaits]
    if issue is not None:
        args += ["--issue", str(issue)]
    return run_memory_script("note.py", args, cwd=repo)


def pm_path(repo):
    """`.claude/project-memory/` de `repo` -- la misma ruta que
    `notes_commit.pm_root()` documenta (ya en produccion): raiz pelada
    del repo, hermana de `.git/`. Se reconstruye aqui como ruta literal
    (no importando `notes_commit`) porque los cuatro ficheros de
    contrato de esta tarea necesitan sembrar `zones.json`/`config.json`
    ANTES de que el script (que si importa `notes_commit` por dentro)
    llegue a ejecutarse -- son dos necesidades distintas del mismo
    valor, no una duplicacion de logica.
    """
    return Path(repo) / ".claude" / "project-memory"


def seed_zones_json(repo, zone_names):
    """Escribe `zones.json` en el formato canonico que `zones.py`
    documenta y ya construye en produccion (`load()`/`_serialize()`):
    `{nombre_canonico: {"description": ..., "aliases": [...]}}`. Se
    escribe como JSON literal, sin invocar `zones.add()`, porque estos
    tests no ejercitan la mecanica de candado de esa pieza -- solo
    necesitan que la zona EXISTA antes de invocar el script bajo
    contrato.
    """
    pm = pm_path(repo)
    pm.mkdir(parents=True, exist_ok=True)
    data = {
        name: {"description": f"MARK zone description for {name}", "aliases": []}
        for name in zone_names
    }
    (pm / "zones.json").write_text(json.dumps(data), encoding="utf-8")


def seed_config_json(repo, **fields):
    """Escribe `config.json` en el formato que `config.py::load()` espera
    -- un objeto JSON plano con las claves `customs_enabled`/`repo_type`/
    `test_command`, cualquier subconjunto de ellas -- para que un test
    declare EXPLICITAMENTE el ajuste del repositorio, en vez de depender
    del default fail-closed (`Config()`, sin fichero).

    Uso real: `seed_config_json(repo, repo_type="trunk")` para el
    repositorio de prueba donde un commit de trabajo directo a la rama
    principal es legitimo -- lo contrario del default fail-closed
    (`repo_type="gitflow"`, el protegido), que es justo el caso que
    `bin/memory/work.py` tiene que rechazar [PIEZAS.md Sec.10.1, punto 3].

    Mismo patron que `seed_zones_json`: JSON literal, sin invocar ninguna
    funcion de `config.py`, porque estos tests no ejercitan su mecanica de
    carga -- solo necesitan que el fichero exista con el valor que el test
    quiere probar.
    """
    pm = pm_path(repo)
    pm.mkdir(parents=True, exist_ok=True)
    (pm / "config.json").write_text(json.dumps(fields), encoding="utf-8")


# Identidad git deterministica -- ese dia llego (House, 2026-08-08).
# Reproducido real, sin tocar ningun test: un runner limpio, sin
# ~/.gitconfig ni --system, no tiene NADIE que resuelva user.name/
# user.email:
#   printf '[user]\n\tuseConfigOnly = true\n' > /tmp/fakegitconfig
#   GIT_CONFIG_GLOBAL=/tmp/fakegitconfig GIT_CONFIG_SYSTEM=/dev/null \
#       python3 -m pytest <fichero> -q
# -> 284 fallos "Author identity unknown" -- todo lo que pasa por
# `tmp_repo` (que es casi todo este fichero) monta un commit inicial via
# `run_git(["commit", ...])` sin identidad propia, confiando en la de la
# maquina del propietario (unico sitio donde SI corria, y por eso nunca
# se vio en local).
#
# Reincidencia, no un fallo nuevo: `unmassk-toolkit/tests/conftest.py`
# (el conftest del v1, hermano de este, sigue vivo hoy) ya resolvio EXACTO
# este problema (issue #50/#51) con `_DEFAULT_GIT_IDENTITY_ENV` -- la
# reescritura de este fichero para v2 partio de cero (regla del plan,
# "sin reutilizar ninguna linea") y con el codigo se perdio tambien la
# leccion. El docstring de esta funcion decia literalmente "si algun dia
# esto corre en un runner sin identidad global, fallara ruidosamente --
# ese es el momento de anadir un fallback". Ese dia fue ayer.
#
# Por que AQUI y no en el workflow de CI: un `git config --global` en el
# runner tapa el sintoma en ESTA maquina concreta y vuelve a morder en la
# siguiente (otro runner limpio, un contribuidor nuevo, un contenedor de
# verificacion) -- exactamente el ciclo que ya paso una vez. Puesto en el
# entorno del PROCESO de test, en cambio, viaja con el repositorio, nunca
# depende de quien ni donde se ejecuta.
#
# Por que basta con tocar `run_git`: las variables de entorno de git
# (`GIT_AUTHOR_NAME`/`EMAIL`, `GIT_COMMITTER_NAME`/`EMAIL`) SIEMPRE ganan
# a cualquier fichero de configuracion (repo, global o system) -- regla
# propia de git, no de este proyecto. Escribirlas UNA vez en el
# `os.environ` real del proceso de pytest (no en un diccionario local)
# hace que las herede cualquier subproceso lanzado desde aqui en
# adelante: `run_git` mismo (no pasa `env=`, hereda por defecto), y
# tambien `run_memory_script`/`run_gitmem_script`/`run_hook_with_payload`/
# `run_hook_raw_stdin` de mas arriba, que construyen su propio entorno
# copiando `os.environ` en el momento de la llamada -- ninguno de ellos
# necesita tocarse. `tmp_repo` invoca `run_git` en su propio setup, antes
# de que el cuerpo de ningun test lance un script, asi que para cuando
# eso ocurre el entorno ya lleva la identidad.
#
# Incondicional, no `setdefault`: hay un unico sitio en esta suite que fija
# identidad PROPIA por repositorio (`test_customs_hook.py::_init_repo`, que
# hace `git config user.name/user.email` local para que un test de
# expansion de `~` no dependa de la identidad global de la maquina). Un
# `git config` de repositorio NUNCA gana a una variable de entorno --
# `setdefault` no cambiaria eso. Verificado que ese test no comprueba en
# ningun sitio el VALOR del autor/committer (solo que el commit tiene
# exito), asi que esta prioridad no le cambia nada -- sus llamadas a
# `git config` quedan inertes para identidad, no rotas.
#
# Mismos NOMBRE/EMAIL que `unmassk-toolkit/tests/conftest.py` (el hermano
# v1, `_DEFAULT_GIT_IDENTITY_ENV`) a proposito, no por casualidad: un `pytest
# unmassk-toolkit/tests -q` (el comando real de CI) importa los dos
# conftest.py del arbol en el mismo proceso, y `os.environ` es una unica
# tabla compartida -- si llevaran valores distintos, el que se importe
# despues pisaria al otro para TODA la suite, no solo para este
# subdirectorio, y un commit de un test ajeno a memoria apareceria firmado
# "memory". Ningun test de ningun lado comprueba el literal, asi que la
# unica forma limpia de que el orden de import nunca importe es que los dos
# escriban la misma cosa.
os.environ["GIT_AUTHOR_NAME"] = "unmassk-toolkit-tests"
os.environ["GIT_AUTHOR_EMAIL"] = "tests@unmassk-toolkit.invalid"
os.environ["GIT_COMMITTER_NAME"] = "unmassk-toolkit-tests"
os.environ["GIT_COMMITTER_EMAIL"] = "tests@unmassk-toolkit.invalid"


def run_git(args, cwd):
    """Ejecuta un comando git en `cwd` y devuelve (returncode, stdout, stderr).

    No pasa `env=` explicito -- hereda `os.environ` del proceso de pytest
    por defecto, que ya lleva la identidad deterministica inyectada arriba
    (`GIT_AUTHOR_NAME`/`EMAIL`, `GIT_COMMITTER_NAME`/`EMAIL`). `git commit`
    ya no depende de que la maquina que ejecuta los tests tenga
    `~/.gitconfig` -- funciona igual en el portatil del propietario, en un
    runner de CI limpio o en un contenedor de verificacion.
    """
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


@pytest.fixture
def tmp_repo(tmp_path):
    """Crea un repo git temporal con un commit inicial vacio y devuelve su ruta.

    Usa `tmp_path` (fixture nativa de pytest, un directorio unico por
    test que pytest limpia solo) en vez de gestionar un directorio
    temporal a mano.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    repo_path = str(repo)

    rc_init, _out_init, err_init = run_git(["init"], repo_path)
    assert rc_init == 0, f"git init fallo en el fixture tmp_repo: {err_init}"

    rc_commit, _out_commit, err_commit = run_git(
        ["commit", "--allow-empty", "-m", "init"], repo_path
    )
    assert rc_commit == 0, (
        f"git commit inicial fallo en el fixture tmp_repo: {err_commit}"
    )

    return repo_path


def register_note(repo, note_type, **fields):
    """Da de alta una nota de memoria (tipo + campos) en `repo`.

    ESQUELETO INTENCIONADO -- no una implementacion a medias ni un TODO
    abandonado. El propio plan (paso 0.3) dice textualmente: "los
    helpers de nota se completan en la fase 2". Ahora mismo no existen
    `lib/notes.py` (paso 2.4 -- la transaccion validar -> indice ->
    commit) ni `lib/ids.py` (paso 2.3 -- el contador de IDs por tipo),
    asi que cualquier cuerpo real aqui inventaria esa logica en vez de
    reutilizarla, justo lo que la restriccion D del plan prohibe ("el
    validador/generador es una sola pieza").

    Ningun test de la FASE 0 debe llamar a esta funcion todavia -- por
    eso lanza NotImplementedError en vez de simular un commit: un
    esqueleto que devuelve silenciosamente un resultado inventado seria
    peor que uno que grita que aun no existe.

    Cuando llegue la fase 2, este cuerpo pasa a invocar la funcion real
    de `lib/notes.py` (el nombre exacto lo fija el paso 2.4) y devuelve
    lo que esa funcion devuelva -- sin reimplementar aqui validacion,
    generacion de indice ni commit.
    """
    raise NotImplementedError(
        "register_note() se completa en la fase 2 (paso 2.4, lib/notes.py, "
        "y paso 2.3, lib/ids.py -- ver PLAN-CONSTRUCCION.md). Ningun test "
        "de la fase 0 debe depender de este helper todavia."
    )


def assert_index_contains(repo, index_name, note_id):
    """Comprueba que el fichero de indice `index_name` de `repo` contiene la linea de `note_id`.

    ESQUELETO INTENCIONADO, misma razon que `register_note()` arriba:
    `lib/indexes.py` (paso 2.2 -- sembrar, insertar, retirar, archivar,
    recuentos de los ocho ficheros de indice) todavia no existe. El
    formato de la linea de indice tampoco (`lib/format.py`, paso 1.5) --
    reimplementarlo aqui a mano duplicaria una verdad que el plan exige
    que viva en una sola pieza.

    Lanza NotImplementedError en vez de leer el fichero a ciegas y
    comparar contra una linea inventada a mano: eso seria fabricar el
    resultado esperado en vez de derivarlo del formato real (la misma
    regla que rige los round-trips de §34 en unmassk-standards).

    Cuando llegue la fase 2, este cuerpo pasa a leer el fichero de
    indice real (via `lib/indexes.py`) y comprobar la presencia de la
    linea que `lib/format.py` genero para `note_id`.
    """
    raise NotImplementedError(
        "assert_index_contains() se completa en la fase 2 (paso 2.2, "
        "lib/indexes.py, y paso 1.5, lib/format.py -- ver "
        "PLAN-CONSTRUCCION.md). Ningun test de la fase 0 debe depender de "
        "este helper todavia."
    )
