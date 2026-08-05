"""Capa de git propia de la memoria -- contrato en docs/memoria-v2/PIEZAS.md Sec.7.1.

Para que: hablar con git sin perder por el camino lo que git dice. De
donde sale: de la novena validacion de la aduana [spec Sec.6]
(propagacion del error real de git) y del candado [spec Sec.7].

El fallo concreto que este modulo existe para prevenir: si el commit de
una nota falla y la capa devuelve una cadena vacia, el usuario ve "no se
pudo guardar" sin causa, y el indice puede quedar apuntando a una nota
que no existe. El mensaje de git ES el diagnostico -- tragarselo
convierte un fallo con causa en un fallo sin causa. Los otros dos fallos
que este modulo cubre son de la misma familia (perdida o corrupcion
silenciosa de memoria, el unico riesgo real de este proyecto -- CLAUDE.md:
"el sistema contra si mismo, no una persona contra el sistema"): una
carrera entre dos escritores del mismo indice que pierde el cambio del
que llego primero sin avisar, y una escritura interrumpida a mitad que
deja el indice vacio o partido.

Que NO hace: no sabe que es una nota, ni un indice, ni una zona -- es la
capa de git y nada mas [PIEZAS.md Sec.7.1].

`lib/memory/` no importa nada del toolkit fuera de la biblioteca estandar
de Python [PIEZAS.md Sec.13]. El candado (`file_lock`) imita a proposito
el mecanismo ya probado en produccion de
`unmassk-toolkit/lib/git_helpers.py::file_lock()` -- bloqueo exclusivo de
fichero con su variante de Windows -- sin reutilizar sus lineas ni
importarlo [PLAN-CONSTRUCCION.md Sec.3.3, restriccion A]. Es la unica
pieza del v1 que se reescribe copiando la idea, y queda dicho. Mismo
espiritu que ya aplico `zones.py` para su propio candado privado, aqui
como la pieza canonica de la capa git.

Este proyecto no defiende contra un atacante (un solo dueno, sin
adversario externo) -- lo que importa es que el sistema no se rompa a si
mismo.
"""

import errno
import os
import subprocess
import sys
import tempfile
import threading
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

GIT_TIMEOUT = 10  # segundos por defecto para repo_root()/commit(), que no exponen su propio parametro de timeout


@dataclass(frozen=True)
class GitResult:
    """Lo que devuelve toda llamada a git. `stderr` es el mensaje REAL,
    entero, nunca vacio ni recortado -- es el diagnostico, no un extra."""

    returncode: int
    stdout: str
    stderr: str


def run(
    args: Sequence[str], cwd: Path, timeout: int, env: Mapping[str, str] | None = None
) -> GitResult:
    """Ejecuta `git <args>` en `cwd` y devuelve el resultado real, siempre.

    Nunca lanza por un fallo DE GIT: un `returncode != 0` es un resultado
    normal de esta funcion, no una excepcion (fila 1 de Sec.7.1 -- el
    stderr de git es el diagnostico que el usuario necesita, y tragarlo
    convierte un fallo con causa en un fallo sin causa). Los dos fallos
    que si se convierten en un `GitResult` en vez de propagar una
    excepcion de `subprocess` son los que un vigilante no puede
    permitirse perder aunque no vengan de git respondiendo con un
    codigo de salida: el binario `git` ausente o no ejecutable
    (`OSError`) y un proceso que no termina dentro de `timeout`
    (`subprocess.TimeoutExpired`).
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            # `env` se SUPERPONE al entorno real, nunca lo sustituye:
            # reemplazarlo entero dejaria a git sin PATH ni HOME. Su unico
            # uso hoy es el endurecido del fetch (`remote.py`), que apaga
            # toda peticion de credenciales para que el arranque no se
            # quede colgado esperando a alguien.
            env={**os.environ, **env} if env else None,
        )
    except subprocess.TimeoutExpired:
        return GitResult(
            returncode=124,
            stdout="",
            stderr=f"git {list(args)!r} no termino dentro de {timeout}s (cwd={cwd})",
        )
    except OSError as e:
        return GitResult(
            returncode=127,
            stdout="",
            stderr=f"no se pudo ejecutar git {list(args)!r}: {e}",
        )
    stdout, stderr = proc.stdout, proc.stderr
    if proc.returncode != 0 and not stderr.strip() and stdout.strip():
        # Algunos fallos de git (p.ej. "nothing to commit, working tree
        # clean") escriben el motivo real por stdout y dejan stderr en
        # blanco -- confirmado contra git real, no supuesto (ver
        # test_failed_commit_with_reason_only_in_stdout_still_reaches_stderr).
        # `GitResult.stderr` promete ser "el mensaje real, entero, nunca
        # vacio" -- si stderr vino vacio pero stdout trae el motivo, ESE es
        # el diagnostico real y se copia tal cual (nunca un texto inventado
        # aqui). Cuando stderr SI trae contenido, se deja intacto: los dos
        # canales pueden coexistir y ninguno se descarta.
        stderr = stdout
    return GitResult(returncode=proc.returncode, stdout=stdout, stderr=stderr)


def repo_root(cwd: Path) -> Path:
    """Raiz del repositorio git que contiene `cwd`.

    Lanza `RuntimeError` con el stderr real de git si `cwd` no esta
    dentro de un repositorio -- devolver `None` o una cadena vacia aqui
    esconderia la causa exacta a quien lo llama.
    """
    result = run(["rev-parse", "--show-toplevel"], cwd=cwd, timeout=GIT_TIMEOUT)
    if result.returncode != 0:
        raise RuntimeError(f"git rev-parse --show-toplevel fallo en {cwd}: {result.stderr}")
    return Path(result.stdout.strip())


def commit(
    message: str, paths: Sequence[Path], allow_empty: bool, cwd: Path | None = None
) -> GitResult:
    """Commitea EXACTAMENTE `paths`, aunque el indice de git tenga mas
    cosas staged fuera de ellas -- lo necesita la publicacion del
    toolkit, que commitea tres ficheros concretos sin arrastrar el resto
    [PIEZAS.md Sec.7.1; plan Sec.2.7].

    `paths` es obligatorio y no vacio: un pathspec vacio no filtra nada
    -- haria `git commit` sobre el indice completo, el silencio contrario
    a lo que esta funcion promete.

    `cwd` es OPCIONAL (`None` por defecto): si se omite, hereda el cwd
    ambiental del proceso, igual que el mecanismo ya probado en
    produccion de `bin/git-memory-commit.py::_do_commit()` -- quien la
    llama ya esta corriendo dentro del repo [comportamiento historico,
    conservado para no romper `test_gitcmd.py`, que llama a esta funcion
    sin `cwd` apoyandose en `os.chdir()` antes de la llamada]. Quien SI
    conoce la raiz del repositorio de antemano debe pasarla explicita
    aqui -- hallazgo real: `notes_commit.py::stage_and_commit()` anclaba
    su `git add` a `root` pero dejaba que este `commit()` heredara el cwd
    ambiental sin declararlo; un commit de trabajo lanzado desde una
    subcarpeta interpretaba el MISMO pathspec relativo desde dos sitios
    distintos (`git add` desde `root`, `git commit` desde la subcarpeta),
    el commit fallaba, y el fichero de la raiz que `git add` habia tocado
    por error quedaba staged sin que nada lo deshiciera. Ver el docstring
    de `stage_and_commit()` para el arreglo completo.

    `--cleanup=verbatim`: sin esto, git aplica su modo de limpieza por
    defecto (`strip`) al mensaje, que borra el espacio final de cada
    linea. `format.py` (Sec.6.4) codifica una linea en blanco DENTRO de
    un campo plegado como una linea que contiene exactamente un espacio
    (`_fold_raw`) -- git la deja vacia, y al releer, esa linea vacia se
    interpreta como el fin de los campos del cuerpo:
    `format.parse_message` devuelve `None` para un mensaje que el propio
    sistema escribio, y `query` lo descarta en silencio. Verificado
    contra un commit real: `git commit --cleanup=verbatim` conserva el
    espacio, el modo por defecto no. El mensaje que llega aqui ya lo
    construyo `format.build_message()` -- no necesita que git lo retoque
    una segunda vez.
    """
    if not paths:
        raise ValueError(
            "commit() exige al menos una ruta explicita en `paths` -- un "
            "pathspec vacio commitearia el indice completo, justo lo que "
            "esta funcion existe para evitar"
        )
    args = ["commit", "--cleanup=verbatim"]
    if allow_empty:
        args.append("--allow-empty")
    args += ["-m", message, "--", *(str(p) for p in paths)]
    return run(args, cwd=cwd if cwd is not None else Path.cwd(), timeout=GIT_TIMEOUT)


def commit_empty(message: str) -> GitResult:
    """Commit GENUINAMENTE vacio -- ``git commit --allow-empty`` sin
    pathspec -- para los dos escritores del sistema que no tocan ningun
    fichero al comitear: ``rules.add()`` (el commit vacio del remember,
    PIEZAS.md Sec.9.7) y ``context.write()`` (el (arrow) del cierre de
    sesion, PIEZAS.md Sec.9.6). ``commit()`` de arriba exige ``paths`` no
    vacio [fila de arriba] y no encaja en ninguno de los dos: no hay
    ninguna nota ni indice que commitear.

    Antes de que existiera esta funcion, cada uno de los dos llamadores
    construia la misma invocacion de git a mano -- las dos con
    ``--cleanup=verbatim``, y el dia que a una se le olvidara ese flag el
    texto plegado se corrompe en silencio (ver el porque exacto en el
    docstring de ``commit()`` de arriba). Con una unica pieza de git que
    lo construye, ese olvido deja de ser posible.

    No declara su propio ``cwd``: hereda el cwd ambiental del proceso,
    igual que ``commit()``.
    """
    args = ["commit", "--cleanup=verbatim", "--allow-empty", "-m", message]
    return run(args, cwd=Path.cwd(), timeout=GIT_TIMEOUT)


# --- candado exclusivo entre procesos, con deteccion de anidamiento ---

# Registro EN PROCESO de que ruta absoluta tiene tomada cada hilo. Existe
# solo para detectar el anidamiento (fila 4 de Sec.7.1) ANTES de intentar
# el candado real: fcntl.flock()/msvcrt.locking() estan ligados a la
# "open file description" de cada os.open(), no al proceso ni al hilo --
# dos aperturas distintas del mismo hilo sobre el mismo fichero se
# bloquean entre si de verdad, indefinidamente, si se intentara el
# candado real dos veces sin este guardia. La exclusion mutua ENTRE
# hilos/procesos sigue siendo la del sistema operativo; este registro
# nunca la sustituye, solo evita pedirle al SO algo que ya se sabe que
# se colgaria para siempre.
_held_locks_guard = threading.Lock()
_held_locks: dict[str, int] = {}

# Windows: el unico errno que file_lock() reintenta por su cuenta (ver su
# docstring). Cualquier otro es un fallo real que no se arregla reintentando.
_MSVCRT_LOCK_CONTENDED_ERRNO = getattr(errno, "EDEADLOCK", None)


class _LockNotReentrantError(RuntimeError):
    """`file_lock()` se anido sobre la misma ruta desde el mismo hilo -- el
    candado subyacente no es reentrante, y esta excepcion es como lo dice
    en vez de colgar el proceso para siempre (fila 4 de Sec.7.1)."""


def _acquire_platform_lock(fd: int) -> None:
    """Toma el candado exclusivo real sobre `fd`, bloqueante. Ver el
    docstring de `file_lock()` para el porque de cada rama de plataforma."""
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                return
            except OSError as e:
                if (
                    _MSVCRT_LOCK_CONTENDED_ERRNO is not None
                    and e.errno == _MSVCRT_LOCK_CONTENDED_ERRNO
                ):
                    continue  # contencion en curso -- sigue intentando
                raise  # fallo real -- reintentar no lo va a arreglar
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX)


def _release_platform_lock(fd: int) -> None:
    """Suelta el candado tomado por `_acquire_platform_lock()` sobre `fd`."""
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


def _same_file(fd: int, path: str) -> bool:
    """True si el fichero abierto en `fd` sigue siendo, ahora mismo, el
    mismo inodo que `path` tiene en el directorio -- comparando
    `(st_dev, st_ino)`. Si `path` ya no existe (alguien lo borro), no
    son el mismo. Usado solo al ADQUIRIR (ver `_acquire_live_lock()`):
    es la comprobacion que cierra la carrera clasica `flock()` + borrado
    -- un `fd` abierto antes de que otro proceso borrara `path` sigue
    apuntando al inodo VIEJO aunque el nombre ya no exista o ya senale a
    un inodo nuevo."""
    try:
        path_stat = os.stat(path)
    except OSError:
        return False
    fd_stat = os.fstat(fd)
    return (fd_stat.st_dev, fd_stat.st_ino) == (path_stat.st_dev, path_stat.st_ino)


def _acquire_live_lock(lock_path: str) -> int:
    """Abre `lock_path`, toma el candado real sobre el, y solo lo da por
    bueno si el inodo que acaba de bloquear sigue siendo, en este mismo
    instante, el que esa ruta tiene en el directorio.

    La carrera que esto cierra (la razon de que estos `.lock` no se
    pudieran borrar hasta ahora sin peligro): un proceso B abre
    `lock_path` (inodo X) y se queda bloqueado en `flock()` porque A lo
    tiene tomado. A termina, borra `lock_path` (el nombre desaparece,
    pero el inodo X sigue vivo mientras A y B lo tengan abierto) y
    suelta su candado. El `flock()` de B, que seguia esperando sobre el
    inodo X, se desbloquea al instante -- B "consigue" el candado, pero
    sobre un inodo YA MUERTO (sin nombre) o, peor, un inodo que un
    tercer proceso C ya recreo y esta usando de verdad sin contencion
    real (dos procesos dentro a la vez). La comprobacion de abajo
    detecta exactamente ese caso: si `lock_path` ya no apunta al inodo
    que B acaba de bloquear, B suelta, cierra y reintenta desde cero --
    reabriendo `lock_path` consigue el fichero que este vivo AHORA
    (nuevo o recien creado), y vuelve a intentar el candado sobre ese.
    """
    while True:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            _acquire_platform_lock(fd)
        except BaseException:
            os.close(fd)
            raise
        if _same_file(fd, lock_path):
            return fd
        # Inodo fantasma: alguien borro (y quiza recreo) `lock_path`
        # mientras esperabamos -- lo que acabamos de bloquear no es la
        # entrada vigente. Soltar, cerrar, reintentar sobre la ruta real.
        _release_platform_lock(fd)
        os.close(fd)


def _release_live_lock(fd: int, lock_path: str) -> None:
    """Suelta el candado tomado por `_acquire_live_lock()` y borra
    `lock_path` -- el borrado es lo que permite que estos `.lock` no se
    acumulen sueltos en el directorio, y es seguro porque, mientras
    llegamos aqui, ningun otro proceso puede estar "dentro": la
    exclusion mutua de `flock()` garantiza que solo el tenedor actual
    del candado ejecuta esta funcion para este `lock_path`, y ningun
    otro llamador de `file_lock()` borra nunca esta ruta por su cuenta.

    Orden POSIX (`fcntl.flock`): se borra el fichero ANTES de soltar el
    candado, no despues. Si se soltara primero, un proceso B que ya
    estaba bloqueado en `flock()` sobre el mismo inodo se desbloquearia
    de inmediato y podria alcanzar a borrar el mismo nombre por su
    cuenta si tuviera su propia logica de limpieza -- borrando antes,
    cuando B se desbloquee ya no hay nombre que confundir con el suyo, y
    su propia comprobacion de inodo en `_acquire_live_lock()` (que ve
    `lock_path` inexistente) lo manda a reabrir y reintentar sobre el
    fichero real, nunca a entrar dos veces.

    Orden Windows (`msvcrt.locking`) AL REVES, y es una decision
    consciente, no un descuido: la CRT de Windows no concede permiso de
    borrado sobre un fichero que sigue abierto sin `FILE_SHARE_DELETE`
    (que `os.open()` no pide), asi que `os.unlink()` antes de cerrar el
    `fd` fallaria con `PermissionError` en la practica. Se suelta y se
    cierra primero, y SOLO DESPUES se intenta borrar. La seguridad de la
    exclusion mutua no depende de este orden -- la da la comprobacion de
    inodo en `_acquire_live_lock()`, que corre igual en las dos
    plataformas --; lo unico que cambia es que, bajo contencion real,
    en Windows el `.lock` puede sobrevivir mas veces que en POSIX antes
    de desaparecer. Hueco declarado, no escondido: no hay banco de
    pruebas de Windows en este proyecto para verificarlo en vivo.
    """
    if sys.platform == "win32":
        _release_platform_lock(fd)
        os.close(fd)
        try:
            os.unlink(lock_path)
        except OSError:
            pass  # otro proceso ya lo recreo, o ya no existe -- no es un fallo
    else:
        try:
            os.unlink(lock_path)
        except OSError:
            pass
        _release_platform_lock(fd)
        os.close(fd)


@contextmanager
def file_lock(path: Path):
    """Bloqueo exclusivo entre procesos sobre `path`, bloqueante hasta
    conseguirlo. Serializa cualquier lectura-modificacion-escritura sobre
    el fichero que protege (fila 2 de Sec.7.1).

    El fichero real de candado (`<path>.lock`) se BORRA al soltarse --
    no queda suelto en el directorio junto a los indices que protege.
    Ver los docstrings de `_acquire_live_lock()`/`_release_live_lock()`
    para la carrera exacta (`flock()` + borrado) que hace que esto no
    sea un simple `os.unlink()` de mas: sin la comprobacion de inodo de
    `_acquire_live_lock()`, un proceso que llega justo despues del
    borrado podria recrear la ruta y tomar el candado sin contencion
    real mientras otro sigue "dentro" -- dos procesos a la vez. Con
    ella, ese proceso detecta el inodo fantasma y reintenta, nunca entra
    en falso.

    NO REENTRANTE, y lo dice: anidar `file_lock()` sobre la MISMA ruta
    desde el MISMO hilo -- incluso a varios niveles de llamada -- lanza
    `_LockNotReentrantError` en vez de colgar el proceso (fila 4). Un hilo
    DISTINTO pidiendo la misma ruta si espera de verdad: esa espera es la
    serializacion real que la fila 2 exige, no un bug.

    POSIX: `fcntl.flock(fd, fcntl.LOCK_EX)` -- bloqueo nativo, indefinido,
    lo espera el kernel, sin bucle de reintento aqui (el reintento que SI
    existe, en `_acquire_live_lock()`, es por inodo fantasma, no por
    contencion).

    Windows: `msvcrt.locking()` no tiene un bloqueo indefinido propio --
    cada llamada reintenta unos 10s por su cuenta y lanza `OSError` si la
    region sigue ocupada. `_acquire_platform_lock()` reintenta por su
    cuenta alrededor de eso: solo mientras el error sea justo esa
    contencion en curso; cualquier otro error se relanza tal cual, porque
    reintentar no lo va a arreglar.

    `fcntl`/`msvcrt` se importan de forma perezosa, dentro de la rama de
    `sys.platform` que corresponde, para que importar este modulo nunca
    falle en la plataforma que no aplica.
    """
    abs_path = os.path.abspath(str(path))
    current_thread = threading.get_ident()

    with _held_locks_guard:
        if _held_locks.get(abs_path) == current_thread:
            raise _LockNotReentrantError(
                f"file_lock() ya esta tomado sobre {abs_path!r} por este "
                "mismo hilo -- no es reentrante (PIEZAS.md Sec.7.1, fila 4)"
            )

    lock_path = f"{abs_path}.lock"
    fd = _acquire_live_lock(lock_path)
    with _held_locks_guard:
        _held_locks[abs_path] = current_thread
    try:
        yield
    finally:
        with _held_locks_guard:
            _held_locks.pop(abs_path, None)
        _release_live_lock(fd, lock_path)


def atomic_write(path: Path, content: str) -> None:
    """Escribe `content` entero en `path` sin dejarlo nunca truncado a
    medias (fila 3 de Sec.7.1).

    Un `open(path, "w")` corriente vacia el fichero en el instante en que
    se abre -- si el proceso muere a mitad, el indice se queda vacio o
    partido. Aqui se escribe a un fichero temporal en el MISMO directorio
    que `path` (para que el reemplazo final quede en el mismo sistema de
    ficheros) y solo se reemplaza con `os.replace()` cuando el contenido
    esta entero en disco y `fsync()` confirma que llego a persistirse --
    `os.replace()` es atomico tanto en POSIX como en Windows desde Python
    3.3. Un fallo a mitad de escritura (proceso matado, disco lleno) deja
    `path` con su contenido ANTERIOR intacto, nunca a medias.
    """
    path_str = str(path)
    dest_dir = os.path.dirname(os.path.abspath(path_str)) or "."
    fd, tmp_path = tempfile.mkstemp(
        dir=dest_dir, prefix=f".{os.path.basename(path_str)}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path_str)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
