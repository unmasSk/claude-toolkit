"""Contrato de lib/memory/gitcmd.py -- PIEZAS.md Sec.7.1.

gitcmd.py existe -- los cuatro tests de contrato de abajo (uno por fila de
la tabla "Sus tests" de Sec.7.1) ya estan en verde:

  1. Un git que falla devuelve su mensaje entero, nunca vacio.
  2. Dos procesos escribiendo el mismo indice se serializan.
  3. Una escritura atomica interrumpida deja el fichero original intacto.
  4. Anidar el candado sobre la misma ruta se detecta.

Un QUINTO test, anadido despues como REGRESION (no una fila nueva de la
tabla de contrato -- ver su propio docstring,
`test_failed_commit_with_reason_only_in_stdout_still_reaches_stderr`),
cubre un agujero real que la fila 1 no cazaba: cuando el motivo del
fallo de git llega por STDOUT en vez de por stderr, se pierde. Ese test
esta en rojo por su causa real; los otros cuatro siguen en verde.

El fixture `gitcmd` importa por ruta de fichero (`import_lib_memory_module`,
ver conftest.py) para que cada test falle individualmente con la causa
real (`FileNotFoundError`: lib/memory/gitcmd.py no existe todavia), en vez
de un unico error de coleccion para todo el fichero -- mismo patron que
test_emojis.py, test_vocabulary.py, test_config.py y test_zones.py.

Cada test pide el fixture `gitcmd` ANTES que `tmp_repo` en su firma, igual
que test_zones.py pide `zones` antes que `model`: pytest instancia los
fixtures en el orden en que aparecen, asi que si `gitcmd.py` no existe el
fallo se reporta ahi, nunca por una fixture ajena.

Por que estos cuatro son "de los mas serios de todo el proyecto" (el
encargo que acompana esta tarea, y Sec.7.1 del propio documento): esta
pieza es DONDE el sistema se puede corromper a si mismo. Un fallo de git
tragado en silencio deja al usuario sin diagnostico. Una carrera entre dos
escritores del mismo indice pierde el cambio del que llego primero, sin
avisar. Una escritura no atomica interrumpida a mitad deja el indice vacio
o partido. Y un candado que se cuelga a si mismo cuelga el proceso para
siempre, sin mensaje. Los cuatro son perdida o corrupcion silenciosa de
memoria -- el unico riesgo real de este proyecto, segun CLAUDE.md
("el sistema contra si mismo, no una persona contra el sistema").

CONTRA GIT DE VERDAD, no simulado: los cuatro tests usan el repositorio
git temporal real del fixture `tmp_repo` de conftest.py, sin mockear
subprocess ni el modulo `git`.

La unica excepcion es la fila 3 (escritura atomica interrumpida), donde
provocar un fallo real a mitad de escritura exige matar un proceso real
en el instante justo. Como se monto, en detalle (para que quede
documentado, tal como pide el encargo):

  - Antes de escribir nada, se deja en `target` un contenido "original"
    conocido, escrito directamente (sin pasar por `atomic_write`).
  - Se lanza un SUBPROCESO PYTHON REAL (no un hilo -- un hilo no se puede
    matar con SIGKILL a mitad de una syscall de escritura) que carga
    `gitcmd.py` por ruta de fichero y llama a `atomic_write(target,
    contenido_grande)`, con un contenido de varios cientos de MB para que
    la escritura al temporal tarde un tiempo medible en disco, no
    instantaneo.
  - El proceso PADRE (el test) no duerme a ciegas: hace *poll* del
    directorio cada 0.5ms esperando a que aparezca CUALQUIER fichero
    nuevo que no sea `target` ni `.git` -- eso es la entrada de
    directorio del fichero temporal, que aparece en el instante del
    `open()`/`mkstemp()`, mucho antes de que el contenido este escrito
    entero. En cuanto aparece, manda `SIGKILL` inmediatamente.
  - Se comprueba que el proceso realmente murio por señal (no que
    termino solo antes de que le llegara el kill -- si terminara solo,
    el test no habria probado nada real, y se hace fallar explicito en
    ese caso en vez de pasar en falso).
  - Se relee `target` y se compara byte a byte contra el contenido
    original: si `atomic_write` es de verdad atomica, el `os.replace()`
    final nunca llego a ejecutarse, y `target` sigue siendo el fichero
    de antes, intacto.

  Misma tecnica de deteccion-por-aparicion-de-fichero (no por reloj) que
  ya se uso para la carrera del candado en el v1
  (`file-lock-lost-update-contract-notes.md`): preferir una señal real
  observable a una espera ciega, porque una espera ciega es exactamente
  la clase de test dependiente del tiempo que unmassk-standards prohibe.

No se toca produccion: si `lib/memory/gitcmd.py` no existe, estos tests se
quedan en rojo tal cual estan -- eso es lo esperado.
"""

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from .conftest import LIB_MEMORY_DIR, import_lib_memory_module, run_git


@pytest.fixture
def gitcmd():
    return import_lib_memory_module("gitcmd")


def test_failed_git_command_returns_full_real_stderr_never_empty(gitcmd, tmp_repo):
    """Fila 1: un git que falla devuelve su mensaje entero, nunca vacio.

    Fallo real que previene: si el commit de una nota falla y la capa
    devuelve una cadena vacia, el usuario ve "no se pudo guardar" sin
    mas y no hay forma de saber por que. El mensaje de git ES el
    diagnostico -- tragarselo convierte un fallo con causa en un fallo
    sin causa.

    Se usa `run()` (la primitiva mas baja de la Superficie, con `cwd`
    explicito -- a diferencia de `commit()`, que no declara un parametro
    `cwd` propio) contra un pathspec que no existe: git responde con un
    "fatal: pathspec ... did not match any files" real, no fabricado.
    """
    missing_file = "no-existe-este-fichero.txt"
    result = gitcmd.run(
        ["commit", "-m", "intento de commit", "--", missing_file],
        cwd=tmp_repo,
        timeout=10,
    )

    assert result.returncode != 0, (
        "un pathspec inexistente deberia hacer fallar el commit"
    )
    assert result.stderr.strip() != "", (
        "gitcmd.run() devolvio un stderr vacio ante un fallo real de git -- "
        "el usuario se queda sin diagnostico"
    )
    assert missing_file in result.stderr, (
        "el mensaje de error no menciona el fichero real que fallo -- "
        f"parece recortado o generico: {result.stderr!r}"
    )


def test_concurrent_writers_to_same_index_serialize_via_file_lock(gitcmd, tmp_repo):
    """Fila 2: dos procesos escribiendo el mismo indice se serializan.

    Fallo real que previene: dos escritores leen el mismo indice, cada
    uno cambia su parte, y el ultimo borra el cambio del otro sin
    avisar -- la actualizacion perdida.

    Se usan varios hilos reales (mismo patron que
    test_zones.py::test_two_concurrent_adds_do_not_clobber_each_other)
    haciendo cada uno un incremento leer-modificar-escribir de un
    contador compartido en disco, con una pausa deliberada entre la
    lectura y la escritura para ensanchar la ventana de carrera. Sin
    `file_lock()` sirviendo de exclusion mutua real, ese hueco hace casi
    seguro que algunos incrementos se pisen entre si. Si `file_lock()`
    serializa de verdad, el contador final es exactamente el numero de
    hilos -- ni uno menos.
    """
    index_path = os.path.join(tmp_repo, "index.txt")
    with open(index_path, "w", encoding="utf-8") as fh:
        fh.write("0")

    n_writers = 20
    errors = []

    def increment_under_lock():
        try:
            with gitcmd.file_lock(index_path):
                with open(index_path, encoding="utf-8") as fh:
                    current = int(fh.read().strip())
                time.sleep(0.01)  # ensancha la ventana de carrera a proposito
                with open(index_path, "w", encoding="utf-8") as fh:
                    fh.write(str(current + 1))
        except Exception as exc:  # se reporta, no se traga
            errors.append(exc)

    threads = [
        threading.Thread(target=increment_under_lock, daemon=True)
        for _ in range(n_writers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    still_alive = [t for t in threads if t.is_alive()]
    assert not still_alive, (
        f"{len(still_alive)} hilo(s) no terminaron dentro del plazo -- "
        "file_lock() parece haberse colgado bajo concurrencia"
    )
    assert not errors, f"file_lock() lanzo bajo escritura concurrente: {errors}"

    with open(index_path, encoding="utf-8") as fh:
        final_value = int(fh.read().strip())
    assert final_value == n_writers, (
        f"se perdieron actualizaciones bajo escritura concurrente: "
        f"esperado {n_writers}, quedo {final_value} -- la actualizacion "
        "perdida que este test existe para prevenir"
    )


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="SIGKILL/os.kill sobre un pid no aplica igual en Windows",
)
def test_atomic_write_interrupted_mid_write_leaves_original_file_intact(
    gitcmd, tmp_repo
):
    """Fila 3: una escritura atomica interrumpida deja el fichero
    original intacto.

    Fallo real que previene: un `open(path, "w")` corriente vacia el
    fichero en el instante en que se abre -- si el proceso muere a
    mitad, el indice se queda vacio o partido. La escritura atomica
    escribe a un temporal y solo reemplaza cuando esta entera.

    Como se provoca el corte a mitad, en detalle (ver tambien el
    docstring del modulo): un SUBPROCESO real escribe un contenido
    grande via `atomic_write()`; el proceso padre hace poll del
    directorio (no duerme a ciegas) esperando a que aparezca la entrada
    del fichero temporal, y en cuanto aparece manda SIGKILL. Se
    comprueba que el proceso murio realmente por señal (si termino solo
    antes del kill, el test no probo nada y falla explicito en vez de
    pasar en falso) y que el fichero original -- escrito ANTES de correr
    el subproceso, nunca tocado por `atomic_write()` -- sigue siendo
    byte a byte el mismo.
    """
    target = os.path.join(tmp_repo, "index.txt")
    original_content = "linea original -- contenido de antes del corte\n"
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(original_content)

    baseline_entries = set(os.listdir(tmp_repo))

    gitcmd_path = os.path.join(LIB_MEMORY_DIR, "gitcmd.py")
    # 300 MB: suficientemente grande para que la escritura al temporal
    # tarde un tiempo medible en disco, no instantaneo -- el contenido
    # se genera DENTRO del subproceso (no se incrusta como literal en el
    # comando) para no arrastrar un argumento de linea de comandos de
    # cientos de MB.
    write_size_bytes = 300 * 1024 * 1024
    script = (
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('gitcmd_subprocess', {gitcmd_path!r})\n"
        "gitcmd = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(gitcmd)\n"
        f"content = 'A' * {write_size_bytes}\n"
        f"gitcmd.atomic_write({target!r}, content)\n"
    )

    proc = subprocess.Popen([sys.executable, "-c", script], cwd=tmp_repo)
    try:
        deadline = time.time() + 20
        new_entry_seen = False
        while time.time() < deadline:
            current_entries = set(os.listdir(tmp_repo))
            if current_entries - baseline_entries:
                new_entry_seen = True
                break
            if proc.poll() is not None:
                break
            time.sleep(0.0005)

        os.kill(proc.pid, signal.SIGKILL)
        returncode = proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)

    assert new_entry_seen, (
        "nunca aparecio un fichero temporal antes del corte -- este test "
        "no llego a probar una interrupcion real a mitad de escritura"
    )
    assert returncode != 0, (
        "el subproceso termino por su cuenta (returncode="
        f"{returncode}) antes de que le llegara SIGKILL -- la interrupcion "
        "no fue real, este resultado no prueba nada"
    )

    with open(target, encoding="utf-8") as fh:
        survived_content = fh.read()
    assert survived_content == original_content, (
        "el fichero original quedo distinto tras una escritura interrumpida "
        "a mitad -- el indice se quedo vacio o partido, exactamente lo que "
        "atomic_write() existe para prevenir"
    )


def test_nesting_lock_on_same_path_is_detected_not_deadlocked(gitcmd, tmp_repo):
    """Fila 4: anidar el candado sobre la misma ruta se detecta.

    Fallo real que previene: un bloqueo mutuo que cuelga el proceso para
    siempre, sin mensaje.

    Se corre el intento de anidamiento en un hilo daemon con `join(timeout=...)`
    para que, si `file_lock()` realmente se colgara a si mismo, la
    suite de tests no se cuelgue con el -- el hilo sigue vivo en
    segundo plano y el test falla con un mensaje claro en vez de
    congelar pytest. Dos salidas incorrectas posibles, ambas cubiertas:
    (a) el hilo nunca termina (el bloqueo mutuo que este test existe
    para atrapar), o (b) el segundo `with` se completa "no-error" como
    si el candado fuera reentrante -- pero la Superficie de Sec.7.1 lo
    declara explicitamente "no reentrante", asi que un exito silencioso
    tambien es un fallo del contrato.
    """
    target = os.path.join(tmp_repo, "index.txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("contenido")

    outcome = {}

    def attempt_nested_lock():
        try:
            with gitcmd.file_lock(target):
                with gitcmd.file_lock(target):
                    pass
            outcome["result"] = "no-error"
        except Exception as exc:
            outcome["result"] = "raised"
            outcome["exception"] = exc

    thread = threading.Thread(target=attempt_nested_lock, daemon=True)
    thread.start()
    thread.join(timeout=10)

    assert not thread.is_alive(), (
        "anidar file_lock() sobre la misma ruta colgo el hilo indefinidamente -- "
        "el bloqueo mutuo sin deteccion ni mensaje que este test existe para prevenir"
    )
    assert outcome.get("result") == "raised", (
        "anidar el candado sobre la misma ruta deberia lanzar una excepcion "
        "detectable (Sec.7.1: 'no reentrante'), no completarse en silencio "
        f"(resultado real: {outcome.get('result')!r})"
    )


def test_failed_commit_with_reason_only_in_stdout_still_reaches_stderr(gitcmd, tmp_repo):
    """Regresion (confirmada 2026-08-02, no una de las cuatro filas de
    arriba): cuando `git commit` falla porque no hay nada que commitear,
    git escribe el motivo entero en STDOUT y deja stderr vacio.
    Confirmado ejecutandolo directo antes de escribir este test:

        git commit -m x   (sin nada staged)
        -> returncode=1
        -> stdout='On branch main\\nnothing to commit, working tree clean\\n'
        -> stderr=''

    `gitcmd.run()` (linea 61) solo copia `proc.stderr` al `GitResult` que
    devuelve -- el `proc.stdout` de esa misma llamada, aunque lleve el
    motivo real del fallo, no llega a ningun sitio. `commit()` (linea
    113) hereda ese mismo comportamiento sin arreglarlo: el resultado es
    un fallo real (`returncode != 0`) con el diagnostico en blanco.

    Esto rompe el contrato declarado en la propia dataclass (linea 53):
    `GitResult.stderr` es "el mensaje REAL, entero, nunca vacio ni
    recortado -- es el diagnostico, no un extra". Y es el defecto exacto
    que la especificacion (Sec.6, validacion 9) nombra por su nombre:
    "el generador nuevo propaga el error real de git; jamas lo silencia
    (defecto reproducido en el wrapper v1: 'Error: git commit failed:'
    vacio)".

    Row 1 de arriba (`test_failed_git_command_returns_full_real_stderr_never_empty`)
    ya declara probar esto, pero provoca el fallo con un pathspec
    inexistente -- ese caso SI llena stderr (git lo escribe ahi), asi
    que esa fila pasa en verde sin cazar el agujero real: la ruta donde
    el motivo llega por stdout, no por stderr, sigue sin cobertura. No
    se toca ni se borra esa fila; esta es una fila nueva para un caso
    distinto.

    El texto esperado NUNCA se teclea a mano: se captura primero
    ejecutando el MISMO commit fallido de forma directa (`run_git()`,
    la via cruda de conftest.py, sin pasar por `gitcmd`) contra un repo
    en el mismo estado exacto, y es ESO lo que se busca despues dentro
    de lo que devuelve `gitcmd.commit()`. Si el texto de git cambiara
    algun dia (version, locale), este test seguiria midiendo lo mismo en
    vez de comparar contra una cadena congelada.
    """
    tracked = os.path.join(tmp_repo, "tracked.txt")
    with open(tracked, "w", encoding="utf-8") as fh:
        fh.write("contenido inicial\n")
    rc_add, _out_add, err_add = run_git(["add", "tracked.txt"], tmp_repo)
    assert rc_add == 0, f"git add fallo en el setup del test: {err_add}"
    rc_seed, _out_seed, err_seed = run_git(
        ["commit", "-m", "seed tracked.txt"], tmp_repo
    )
    assert rc_seed == 0, f"commit de siembra fallo en el setup del test: {err_seed}"

    # Ground truth: el mismo commit fallido, ejecutado directo -- tracked.txt
    # ya esta committeado y sin cambios, asi que git no tiene nada que
    # commitear. Si esta aserto de aqui abajo fallara algun dia (p.ej. una
    # version de git que empiece a escribir el motivo tambien en stderr),
    # este test avisa de que dejo de medir lo que dice medir, en vez de
    # pasar en falso.
    rc_ground, out_ground, err_ground = run_git(
        ["commit", "-m", "intento de commit sin cambios"], tmp_repo
    )
    assert rc_ground != 0, "el commit de referencia deberia fallar (nada staged)"
    assert out_ground != "", (
        "el fixture de este test no reprodujo el caso -- git no escribio "
        "el motivo en stdout esta vez, este test no mide lo que dice medir"
    )
    assert err_ground == "", (
        "el fixture de este test no reprodujo el caso -- git escribio algo "
        "en stderr esta vez, este test no mide lo que dice medir"
    )

    prev_cwd = os.getcwd()
    os.chdir(tmp_repo)  # commit() no declara su propio cwd, hereda el ambiental
    try:
        result = gitcmd.commit(
            "intento de commit sin cambios", [Path("tracked.txt")], False
        )
    finally:
        os.chdir(prev_cwd)

    assert result.returncode != 0, "commitear sin cambios staged deberia fallar"
    assert result.stderr.strip() != "", (
        "gitcmd.commit() devolvio stderr vacio ante un fallo real de git -- "
        f"el motivo real ({out_ground!r}) quedo en stdout y se descarto "
        f"(stdout devuelto={result.stdout!r}, stderr devuelto={result.stderr!r})"
    )
    assert out_ground in result.stderr, (
        "el motivo real de git no llego integro al stderr que devuelve "
        f"gitcmd -- esperado que contuviera {out_ground!r}, stderr real: "
        f"{result.stderr!r}"
    )


def test_commit_empty_preserves_a_folded_blank_continuation_line(gitcmd, tmp_repo):
    """Regresion (item 5 del endurecimiento de capa 4, 2026-08-02):
    `commit_empty()` es ahora el UNICO sitio que construye un commit
    vacio para `rules.py` y `context.py` -- antes cada uno invocaba
    `git commit --allow-empty` a mano, y el dia que a uno se le olvidara
    `--cleanup=verbatim` el texto plegado (`format._fold_raw`) se
    corrompia en silencio.

    Por que importa exactamente: una linea de continuacion EN BLANCO
    dentro de un campo plegado se codifica como un UNICO espacio (nunca
    cero, nunca mas de uno -- `format._fold_raw`: prefijo + continuacion,
    y una continuacion vacia sigue llevando su espacio de prefijo). El
    modo de limpieza POR DEFECTO de git (`strip`) recorta ese espacio
    final de cada linea; sin `--cleanup=verbatim`, esa linea "en blanco"
    deja de empezar por espacio -- justo la señal que
    `format.parse_context_message` usa para saber que la continuacion
    sigue (ver su bucle: `elif line.startswith(" ") and current is not
    None`). Confirmado en vivo antes de escribir este test: el MISMO
    mensaje, commiteado con y sin `--cleanup=verbatim`, produce
    `[..., ' ', 'segunda linea plegada', ...]` en el primer caso y
    `[..., '', 'segunda linea plegada', ...]` en el segundo -- la linea
    de continuacion pierde su espacio y con el la señal de que sigue
    plegada.

    Prueba `commit_empty()` directamente (no `context.py`/`rules.py` por
    encima -- esta es la pieza unica que los dos comparten, y es donde
    el olvido dejo de ser posible): un mensaje con una linea de
    continuacion plegada de un solo espacio debe sobrevivir intacta en
    el commit real, releido con git de verdad (`git log -1
    --format=%B`), nunca comparado contra un texto tecleado a mano de
    vuelta.
    """
    folded_message = "MARK_FOLD_COMMIT_EMPTY headline\n \nsegunda linea plegada"

    prev_cwd = os.getcwd()
    os.chdir(tmp_repo)
    try:
        result = gitcmd.commit_empty(folded_message)
    finally:
        os.chdir(prev_cwd)

    assert result.returncode == 0, f"commit_empty() fallo: {result.stderr}"

    _rc, real_body, _err = run_git(["log", "-1", "--format=%B"], tmp_repo)
    real_lines = real_body.split("\n")

    assert " " in real_lines, (
        "la linea de continuacion plegada (un unico espacio) no sobrevivio "
        "intacta en el commit real -- probablemente se dejo de aplicar "
        f"--cleanup=verbatim en commit_empty(). Lineas reales: {real_lines!r}"
    )
    assert "segunda linea plegada" in real_lines, (
        f"la segunda linea del mensaje plegado no aparece intacta en el commit "
        f"real: {real_lines!r}"
    )


def test_lock_file_is_removed_on_release_and_never_lets_two_processes_in_at_once(
    gitcmd, tmp_repo
):
    """Nuevo requisito de este encargo (los ocho `.lock` sueltos en
    `.claude/project-memory/`, DEUDA.md punto 9): `file_lock()` debe
    borrar su fichero real de candado al soltarse, sin reabrir la
    carrera clasica `flock()` + `unlink()` -- un proceso que llega justo
    despues del borrado no debe poder tomar el candado sin contencion
    real mientras otro sigue dentro. El mecanismo exacto (comprobacion
    de inodo al adquirir en `_acquire_live_lock()`, borrado antes de
    soltar en POSIX dentro de `_release_live_lock()`) esta documentado
    en gitcmd.py; este test prueba el resultado observable, no la
    implementacion.

    PROBADO CONTRA PROCESOS REALES, no hilos -- la carrera es entre
    `open()`/`flock()` de DOS PROCESOS DISTINTOS disputando el mismo
    inodo/nombre; un hilo del mismo proceso no reproduce la parte donde
    el nombre desaparece del directorio mientras otro ya tiene un `fd`
    abierto sobre el inodo viejo. `n_processes` procesos python reales
    (subprocess.Popen, cada uno cargando gitcmd.py por ruta de fichero,
    igual que `test_atomic_write_interrupted_mid_write_leaves_original_file_intact`
    de arriba) corren cada uno `n_iterations` veces un bucle que:

      1. Toma `gitcmd.file_lock(target)`.
      2. Comprueba que un fichero "marcador de ocupado" (`busy_marker`)
         NO existe -- si existe, otro proceso esta dentro de la seccion
         critica AHORA MISMO: dos procesos a la vez, el fallo exacto que
         este test existe para cazar. Se imprime "MUTEX_BREACH" y el
         proceso sale con codigo distinto de cero en vez de continuar
         como si nada.
      3. Crea el marcador, duerme unos milisegundos (ensancha a
         proposito la ventana en la que otro proceso podria colarse), lo
         borra, y sale del `with` -- que suelta el candado real y borra
         su `.lock`.

    Con `n_processes * n_iterations` (240) entradas reales a la seccion
    critica repartidas entre procesos que constantemente abren, sueltan
    y vuelven a abrir el mismo `.lock`, la ventana exacta de la carrera
    (un proceso soltando y borrando justo cuando otro esta reabriendo)
    se cruza sola muchas veces, sin necesidad de forzar el timing a
    mano -- mismo espiritu que el test de la fila 2 de arriba
    (`test_concurrent_writers_to_same_index_serialize_via_file_lock`),
    aqui entre procesos en vez de entre hilos, y verificando ademas que
    no queda ningun `.lock` al final.
    """
    target = os.path.join(tmp_repo, "shared-resource.txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("contenido inicial\n")
    busy_marker = os.path.join(tmp_repo, "busy.marker")
    lock_path = f"{os.path.abspath(target)}.lock"

    gitcmd_path = os.path.join(LIB_MEMORY_DIR, "gitcmd.py")
    n_processes = 6
    n_iterations = 40

    script = (
        "import importlib.util\n"
        "import os\n"
        "import sys\n"
        "import time\n"
        "spec = importlib.util.spec_from_file_location("
        f"'gitcmd_subprocess', {gitcmd_path!r})\n"
        "gitcmd = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(gitcmd)\n"
        f"target = {target!r}\n"
        f"busy_marker = {busy_marker!r}\n"
        f"for _ in range({n_iterations}):\n"
        "    with gitcmd.file_lock(target):\n"
        "        if os.path.exists(busy_marker):\n"
        "            print('MUTEX_BREACH')\n"
        "            sys.exit(2)\n"
        "        with open(busy_marker, 'w', encoding='utf-8') as fh:\n"
        "            fh.write('busy')\n"
        "        time.sleep(0.005)\n"
        "        os.remove(busy_marker)\n"
        "sys.exit(0)\n"
    )

    procs = [
        subprocess.Popen(
            [sys.executable, "-c", script],
            cwd=tmp_repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(n_processes)
    ]

    outcomes = [(proc, *proc.communicate(timeout=120)) for proc in procs]

    breaches = [
        (proc.pid, out, err)
        for proc, out, err in outcomes
        if "MUTEX_BREACH" in out
    ]
    failures = [
        (proc.pid, proc.returncode, out, err)
        for proc, out, err in outcomes
        if proc.returncode != 0
    ]

    assert not breaches, (
        "al menos un proceso encontro el marcador de ocupado ya puesto por "
        "otro -- dos procesos dentro de la seccion critica a la vez, "
        f"exactamente la carrera que file_lock() existe para cerrar: {breaches!r}"
    )
    assert not failures, f"algun proceso fallo de forma inesperada: {failures!r}"

    assert not os.path.exists(lock_path), (
        f"quedo {lock_path!r} suelto tras soltarse todos los candados -- "
        "el fallo real de este encargo: un candado debe limpiarse al "
        "soltarse, no dejar su .lock tirado en el directorio"
    )


def test_repo_root_from_subdirectory_returns_repo_root_not_the_subdir(
    gitcmd, tmp_repo
):
    """DEUDA.md punto 11 (ultimo pendiente): `gitcmd.repo_root` no tenia
    ni un solo test que la mirara a ella directamente -- se ejecuta de
    paso dentro de otras pruebas, pero ninguna comprobaba su resultado.
    Importa porque es la funcion que decide EN QUE REPOSITORIO escribe
    el sistema -- ya hubo un incidente real por resolver el repositorio
    por el cwd del proceso en vez de por la raiz real (ver docstring de
    `_guard_against_writing_to_the_real_repo` en conftest.py: 70 commits
    falsos en esta rama).

    Desde una subcarpeta del repositorio, `repo_root()` debe devolver la
    RAIZ, no la subcarpeta. El valor esperado nunca se teclea a mano:
    se deriva ejecutando `git rev-parse --show-toplevel` aparte
    (`run_git`, la via cruda de conftest.py), contra la misma subcarpeta,
    y es ESO lo que se compara contra el resultado real de `gitcmd`.
    """
    subdir = os.path.join(tmp_repo, "notes", "zone1")
    os.makedirs(subdir)

    rc, expected_root, err = run_git(["rev-parse", "--show-toplevel"], subdir)
    assert rc == 0, f"el ground truth de git fallo en el setup del test: {err}"

    result = gitcmd.repo_root(Path(subdir))

    assert result == Path(expected_root), (
        f"repo_root() desde una subcarpeta devolvio {result!r}, distinto "
        f"de la raiz real reportada por git ({expected_root!r}) -- si "
        "devolviera la subcarpeta en vez de la raiz, el sistema escribiria "
        "memoria en el sitio equivocado"
    )
    assert result != Path(subdir), (
        "repo_root() devolvio la propia subcarpeta en vez de subir hasta "
        "la raiz del repositorio"
    )


def test_repo_root_outside_a_git_repository_raises_with_real_git_stderr(
    gitcmd, tmp_path
):
    """Complemento del test de arriba: fuera de un repositorio de git,
    el propio codigo de `repo_root()` (lib/memory/gitcmd.py, linea 112)
    declara en su docstring que lanza `RuntimeError` con el stderr real
    de git, en vez de devolver `None` o una cadena vacia -- "esconderia
    la causa exacta a quien lo llama". Este test fija ese comportamiento
    documentado, no lo inventa.

    El directorio usado (`tmp_path`, sin `git init`) no esta dentro de
    ningun repositorio -- pytest lo crea fuera del arbol de este proyecto.
    El texto esperado dentro del mensaje nunca se teclea a mano: se
    captura ejecutando el MISMO `git rev-parse --show-toplevel` aparte
    (`run_git`) contra el mismo directorio, y es su stderr real lo que se
    busca dentro de la excepcion.
    """
    outside_dir = str(tmp_path)

    rc, _out, expected_stderr = run_git(
        ["rev-parse", "--show-toplevel"], outside_dir
    )
    assert rc != 0, (
        "el ground truth de git deberia fallar fuera de un repositorio -- "
        f"si no fallo, este test no mide lo que dice medir (cwd={outside_dir!r})"
    )
    assert expected_stderr != "", (
        "el fixture de este test no reprodujo el caso -- git no escribio "
        "nada en stderr fuera de un repositorio esta vez"
    )

    with pytest.raises(RuntimeError) as exc_info:
        gitcmd.repo_root(Path(outside_dir))

    assert expected_stderr in str(exc_info.value), (
        "repo_root() fuera de un repositorio deberia propagar el stderr "
        f"real de git ({expected_stderr!r}) dentro del RuntimeError -- "
        f"mensaje real: {exc_info.value!s}"
    )
