"""Mecanica de git que `notes.py` usa por debajo -- candado global,
composicion de la ruta de los ocho indices, `git add`+`git commit` con
restauracion de mejor esfuerzo si falla, y el commit de trabajo que no
toca ningun indice. Partido de `notes.py` por tamano.

Este fichero NO es una segunda transaccion ni una segunda puerta de
escritura: sigue habiendo un solo lugar donde nota+indice se escriben
juntos o ninguno de los dos -- ese lugar sigue siendo
`notes.write()`/`replace()`/`close()`, que se quedan enteros en
`notes.py`. Lo que vive aqui es la mecanica de la que esas tres tiran
por debajo, sin saber nada de `Note` ni de `Context`.

`lock_resource`, `repo_root`, `pm_root`, `stage_and_commit` y las dos
restauraciones de mejor esfuerzo no conocen `Note` -- solo mueven rutas,
un candado y comandos de git. `write_work` encaja en el mismo grupo por
otro motivo: es la unica de las cinco operaciones de `notes.py` que NO
toca ningun indice, asi que nunca necesita ninguna restauracion. SI toma
el mismo candado global que sus hermanas -- sin el, escritores
concurrentes reales chocaban contra `.git/index.lock` sin reintento.

Este fichero NO importa nada de `notes.py` -- direccion unica, para que
no haya ciclo. `notes.py` importa los siete nombres de aqui de forma
plana y los reexpone bajo el mismo nombre, asi que
`notes.pm_root`/`notes.write_work` siguen alcanzables igual.

`lock_resource`, `repo_root`, `stage_and_commit`,
`restore_index_best_effort` y `restore_snapshot_best_effort` pierden su
guion bajo al cruzar de fichero: dejan de ser detalle interno de un solo
modulo para ser mecanica que `notes.py` importa desde fuera. No hay una
segunda implementacion en ningun sitio, y por tanto ninguna forma de que
diverjan entre si.

Decisiones que fijan esta mecanica:

1. **Candado GLOBAL, no por indice.** `gitcmd.file_lock()` no es
   reentrante -- si la transaccion tomara el candado sobre la ruta del
   propio indice y luego llamara a `indexes.insert()` (que toma ESE
   MISMO candado por dentro), la segunda toma revienta. La transaccion
   toma un candado DISTINTO (`<root>/.git/memory-notes.lock`) que
   envuelve la operacion completa, y evita ademas que dos escritores
   concurrentes se peleen por `.git/index.lock` de verdad.

2. **`git add` explicito antes de `git commit`.** `gitcmd.commit()`
   commitea exactamente las rutas dadas pero no hace `git add` por su
   cuenta -- la PRIMERA escritura a cada indice (creado por
   `indexes.seed()` pero nunca comiteado) necesita `git add` antes.

3. **Restaurar el indice tras un fallo de git es `indexes.remove()`, no
   una copia de bytes a mano** -- solo para `restore_index_best_effort`
   (la vuelta de `notes.write()`): insert+remove del mismo id es una
   vuelta exacta. `replace()`/`close()` usan
   `restore_snapshot_best_effort` (snapshot completo) porque una linea
   existente puede estar en cualquier posicion y anadirla al final la
   moveria.

4. **Las dos restauraciones son mejor esfuerzo, a proposito.** Si la
   propia restauracion revienta, su excepcion se traga en vez de
   sustituir el diagnostico real -- perder ese mensaje es perder la
   unica causa que el usuario tiene para arreglar el problema.

5. **Los ocho indices viven en `pm_root(root)`, no en `root` a secas.**
   `health.coherence()`/`duplicates()` necesitan la MISMA raiz para leer
   los mismos ocho ficheros que `notes.py` escribe. Lo que NO cambia: el
   candado, el `git add`/`git commit` y `repo_root()` siguen anclados a
   la raiz PELADA del repositorio -- `.git/` solo existe ahi.

No importa nada del toolkit fuera de la biblioteca estandar de Python.
Imports planos entre hermanos de `lib/memory/`. No importa nada de
`notes.py` -- direccion unica.
"""

import dataclasses
import hashlib
import os
import re
import tempfile
from pathlib import Path

import gitcmd
import indexes
from model import WriteResult


def lock_resource(root: Path) -> Path:
    """Ruta base del candado GLOBAL de escritura -- ver punto 1 del
    docstring del modulo. Vive dentro de `.git/`, no en el arbol de
    trabajo, para que nunca aparezca como cambio sin trackear en
    `git status`.
    """
    return Path(root) / ".git" / "memory-notes"


def repo_root() -> Path:
    return gitcmd.repo_root(Path.cwd())


def pm_root(root: Path) -> Path:
    """Raiz real de los ocho indices y de `ARCHIVED.md` --
    `.claude/project-memory/` del proyecto. `root` es la raiz pelada del
    repositorio git (`repo_root()`), hermana de `.git/` -- nunca el
    destino final por si sola.

    Publica (sin guion bajo): `health.coherence()`/`duplicates()`
    necesitan la MISMA raiz para leer los mismos ocho ficheros que
    `notes.py` escribe.
    """
    return Path(root) / ".claude" / "project-memory"


def _path_in_index(path: Path, root: Path) -> bool:
    """`True` si `path` sigue teniendo entrada en el indice de git ahora
    mismo. Usada por `stage_and_commit()` para distinguir un borrado SIN
    stagear (desaparece del arbol de trabajo pero sigue en el indice) de
    uno YA stageado con `git rm` (desaparece de los dos sitios a la vez).
    """
    result = gitcmd.run(
        ["ls-files", "--error-unmatch", "--", str(path)],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    return result.returncode == 0


def stage_and_commit(message: str, paths: list[Path], root: Path) -> gitcmd.GitResult:
    """`git add` explicito seguido de `gitcmd.commit()`. Devuelve el
    `GitResult` del primer paso que falle, o el del commit si ambos
    salen bien -- con `stderr` GARANTIZADO no vacio si
    `returncode != 0` (`_ensure_nonempty_stderr()`).

    Esta garantia vive AQUI, no en cada llamador: es el UNICO sitio
    donde un `GitResult` de un commit real de este sistema nace o se
    devuelve -- todos sus llamadores (`notes.write()`/`replace()`/
    `close()`, `write_work()`, `rules.add()`) la heredan sin tener que
    aplicarla cada uno por su cuenta.

    Si el `git add` entra pero el `git commit` que le sigue falla (un
    hook que rechaza, un `.git/index.lock` de otro escritor concurrente),
    el INDICE de git se queda con el contenido nuevo staged aunque el
    commit nunca llego a existir -- si quien llama ademas restaura el
    CONTENIDO del fichero, el resultado es un `git status` en "MM". Por
    eso, si el `add` entro pero el commit falla, esta funcion deshace su
    PROPIO staging con un `git reset` de mejor esfuerzo antes de
    devolver el `GitResult` del commit fallido.

    `root` viaja explicito a las dos llamadas: un commit lanzado desde
    una subcarpeta interpretaria el mismo pathspec relativo desde dos
    sitios distintos si `git add`/`gitcmd.commit()` no compartieran el
    mismo `cwd`.

    `paths` se filtra ANTES del `git add`, nunca del `git commit`: una
    ruta se incluye en el pathspec de `git add --all` solo si sigue
    existiendo en el arbol de trabajo o sigue teniendo entrada en el
    indice (`_path_in_index()`) -- un fichero ya `git rm`-eado (fuera de
    los dos sitios) hacia que `git add --all -- <path>` fallara con
    "pathspec did not match" antes de siquiera intentar el commit. Una
    ruta ausente de los dos sitios se salta del `add` pero sigue
    viajando integra al `git commit -- <paths>`: si de verdad no es
    nada, `git commit` fallara con su propio mensaje, en voz alta.
    """
    # `--all` (no el `add` pelado): sin el, un BORRADO era imposible de
    # guardar (un fichero recien ignorado por `.gitignore` falla `git add`
    # en cerrado, y `git commit` a pelo lo bloquea la aduana). `--all`
    # registra tambien la desaparicion de una ruta sin ensanchar lo que se
    # comitea: sigue acotado al mismo pathspec explicito de `paths`.
    addable_paths = [p for p in paths if os.path.exists(p) or _path_in_index(p, root)]
    if addable_paths:
        add_result = gitcmd.run(
            ["add", "--all", "--", *(str(p) for p in addable_paths)],
            cwd=root,
            timeout=gitcmd.GIT_TIMEOUT,
        )
        if add_result.returncode != 0:
            return _ensure_nonempty_stderr(add_result)
    commit_result = gitcmd.commit(message, paths, allow_empty=False, cwd=root)
    if commit_result.returncode != 0 and addable_paths:
        # Mejor esfuerzo: el `add` SI entro, asi que el indice quedo con
        # el contenido nuevo staged aunque el commit nunca existio --
        # deshacerlo aqui evita un `git status` en "MM". Se ignora el
        # resultado de este `reset`: el fallo que se reporta sigue siendo
        # `commit_result`.
        gitcmd.run(
            ["reset", "--", *(str(p) for p in addable_paths)],
            cwd=root,
            timeout=gitcmd.GIT_TIMEOUT,
        )
    return _ensure_nonempty_stderr(commit_result)


# Texto de respaldo -- costura compartida: un hook de `pre-commit` que
# hace `exit 1` sin imprimir nada deja `stdout` Y `stderr` los dos
# vacios. Devolver ese `stderr` vacio tal cual como `WriteResult.git_error`
# es un fallo silencioso: `ok=False` sin ninguna causa visible. Vive AQUI,
# el UNICO punto donde nace o se devuelve el `GitResult` de un commit
# real de este sistema, para que TODOS los llamadores (`notes.write()`/
# `replace()`/`close()`, `write_work()`, `rules.add()`) hereden la
# garantia sin una copia por llamador.
_GIT_FAILED_NO_MESSAGE = "git rechazo la operacion sin dar ningun mensaje (revisa hooks de pre-commit)"


def _ensure_nonempty_stderr(result: gitcmd.GitResult) -> gitcmd.GitResult:
    """Garantiza que un `GitResult` con fallo trae un `stderr` real,
    nunca vacio. Un resultado que salio bien, o que ya trae `stderr`
    real, se devuelve intacto -- esta funcion nunca sustituye un mensaje
    real de git, solo rellena el hueco cuando git no dejo ninguno.
    """
    if result.returncode == 0 or result.stderr:
        return result
    return dataclasses.replace(result, stderr=_GIT_FAILED_NO_MESSAGE)


def restore_index_best_effort(note_id: str, index_name: str, pm: Path) -> None:
    """Revierte la linea de `note_id` en `index_name` tras un commit que
    no llego a completarse -- `indexes.insert()` seguido de
    `indexes.remove()` del mismo id, la vuelta exacta. Restauracion de
    `notes.write()` exclusivamente -- `replace()`/`close()` usan
    `restore_snapshot_best_effort`, no esta.

    `pm` es `pm_root(root)`, no la raiz pelada del repositorio -- pasar
    la raiz pelada haria que `indexes.remove()` buscara el fichero en el
    sitio equivocado y la linea de indice quedaria huerfana sin que
    nadie lo note.

    Mejor esfuerzo, a proposito: si `indexes.remove()` revienta aqui, su
    excepcion no debe sustituir el motivo real por el que se esta
    restaurando.
    """
    try:
        indexes.remove(note_id, index_name, pm)
    except Exception:
        pass


def restore_snapshot_best_effort(path: Path, original_content: str) -> None:
    """Restaura `path` a `original_content` -- vuelta de `replace()`/
    `close()` para el indice viejo y ARCHIVED.md (una linea existente
    puede estar en cualquier posicion, y `indexes.insert()` la moveria al
    final). Mejor esfuerzo, mismo motivo que `restore_index_best_effort()`.
    """
    try:
        gitcmd.atomic_write(path, original_content)
    except Exception:
        pass


def _staged_as_new_before_us(path: Path, root: Path) -> bool:
    """`True` si `path` YA aparece en el indice de git como fichero NUEVO
    (sin version previa en HEAD) antes de que `write_work()` haga su
    propio `git add` -- la firma de que otro escritor lo `git add`-eo por
    su cuenta justo antes, fuera de este candado.

    `git diff --cached --name-status -- <path>` compara INDICE contra
    HEAD: una linea que empieza por `A` (anadido) significa que el
    indice ya tiene contenido para `path` que HEAD todavia no conoce.
    `M` (modificado) o salida vacia no cuentan -- un fichero YA trackeado
    preestageado antes de llamar a `write_work()` es un uso legitimo.
    """
    result = gitcmd.run(
        ["diff", "--cached", "--name-status", "--", str(path)],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    return result.stdout.startswith("A\t")


def _content_fingerprint(path: Path) -> str | None:
    """Huella del contenido de `path` en este instante exacto, o `None`
    si el fichero no existe -- DISTINTO de `_staged_as_new_before_us()`,
    que mira el INDICE de git; esto lee el ARBOL DE TRABAJO directamente.
    Para un fichero YA TRACKEADO que dos escritores pisan por turnos, el
    INDICE no distingue las dos situaciones, pero el CONTENIDO crudo si.

    sha256 sobre bytes crudos, no sobre texto interpretado: no depende de
    que la codificacion se adivine bien.
    """
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except FileNotFoundError:
        return None


def _relpath_posix(path: Path, root: Path) -> str:
    """`path` (absoluta) relativa a `root`, forzada a `/` (nunca `\\`) --
    git interpreta pathspecs y argumentos `--path` con `/`,
    independientemente del sistema de ficheros. Compartido entre
    `_git_blob_hash_of_bytes()` y `_committed_blob_hash()` para que las
    dos calculen exactamente la misma ruta relativa.
    """
    return Path(os.path.relpath(str(path), str(root))).as_posix()


def _git_blob_hash_of_bytes(content: bytes, path: Path, root: Path) -> str | None:
    """Hash del blob que git GUARDARIA DE VERDAD para `content` si se
    escribiera en `path` y se hiciera `git add` -- sin escribirlo al
    object store (`hash-object` sin `-w`) y sin tocar el arbol de trabajo
    real: `content` se vuelca a un fichero temporal fuera del repo
    (siempre borrado). `None` si `git hash-object` fallo -- nunca se
    trata como si coincidiera con nada.

    `--path <ruta relativa real>` es obligatorio, y `--no-filters` esta
    PROHIBIDO: `stage_and_commit()` comitea via `git add` normal, que SI
    aplica los filtros de la ruta real (en Windows, `core.autocrlf`
    normaliza `\\r\\n` a `\\n` al guardar). `--no-filters` hashea los
    bytes crudos, asi que en cualquier repo con autocrlf activo esta
    funcion compararia el hash CRLF contra el blob LF que git de verdad
    guardo -- siempre distinto, sin que nadie pisara nada (rompio
    `gitmem wip` en CI de Windows). `--path <ruta>` resuelve el mismo
    filtro de `.gitattributes` pero contra la ruta CORRECTA: la promesa
    de esta funcion es "el hash que estos bytes tendrian SI se
    guardaran en `path`", no "el hash de estos bytes exactos".
    """
    fd, tmp_path = tempfile.mkstemp(prefix=".write_work_verify.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        result = gitcmd.run(
            ["hash-object", "--path", _relpath_posix(path, root), tmp_path],
            cwd=root,
            timeout=gitcmd.GIT_TIMEOUT,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return result.stdout.strip() if result.returncode == 0 else None


def _committed_blob_hash(path: Path, root: Path) -> str | None:
    """Hash del blob que `HEAD` tiene DE VERDAD para `path` ahora mismo,
    o `None` si no se pudo determinar -- nunca se trata como si
    coincidiera con nada.
    """
    rel = _relpath_posix(path, root)
    result = gitcmd.run(["rev-parse", f"HEAD:{rel}"], cwd=root, timeout=gitcmd.GIT_TIMEOUT)
    return result.stdout.strip() if result.returncode == 0 else None


# `[<rama> <sha-corto>] <asunto>` o `[<rama> (root-commit) <sha-corto>]
# <asunto>` -- la linea de resumen que `git commit` imprime en su PROPIA
# `[<rama> <sha-corto>] <asunto>` -- la linea de resumen que `git commit`
# imprime en su PROPIA salida estandar salvo `--quiet`. `.+` es voraz a
# proposito: retrocede hasta el ULTIMO `<espacio><hex>]` de la primera
# linea, que es siempre el que cierra el resumen de git, sin importar
# cuantos espacios lleve el nombre de la rama.
_COMMIT_SUMMARY_SHA_RE = re.compile(r"^\[.+\s([0-9a-fA-F]{4,40})\]")


def _own_commit_sha_from_commit_output(commit_stdout: str, root: Path) -> str | None:
    """Identificador completo (40 caracteres) del commit que `git commit`
    acaba de crear, leido de la PRIMERA linea de SU PROPIA salida --
    nunca de un `git rev-parse HEAD` en un subproceso posterior: entre el
    commit y cualquier lectura posterior de `HEAD` como referencia, un
    proceso ajeno puede comitear encima y envenenar la referencia antes
    de que nada la compare.

    El sha corto se expande a los 40 caracteres con
    `git rev-parse <corto>^{commit}` -- busqueda por CONTENIDO (el objeto
    ya existe bajo ese hash), nunca por REFERENCIA: un commit ajeno que
    aterrice entre medias no cambia a que apunta un hash que ya existe.

    `None` si la primera linea no tiene la forma esperada o si la
    expansion falla.
    """
    first_line = commit_stdout.split("\n", 1)[0]
    match = _COMMIT_SUMMARY_SHA_RE.match(first_line)
    if match is None:
        return None
    short_sha = match.group(1)
    result = gitcmd.run(
        ["rev-parse", f"{short_sha}^{{commit}}"], cwd=root, timeout=gitcmd.GIT_TIMEOUT
    )
    return result.stdout.strip() if result.returncode == 0 else None


def write_work(
    message: str,
    paths: list[Path],
    issue: int | None,
    known_content: list[bytes | None] | None = None,
) -> WriteResult:
    """Commit de trabajo: acepta rutas concretas y no arrastra el resto
    del arbol -- lo necesita la publicacion del toolkit, que commitea
    unos pocos ficheros sin llevarse cambios a medias de otros. No lleva
    campo de ficheros tocados: `git log -- <ruta>` ya responde eso.

    `issue`, si se da, viaja como trailer `Issue: #N` al final del
    mensaje -- mismo formato literal que usa `format.py` para el campo
    `Issue` de una nota.

    No toca ningun indice de nota -- por eso vive en este fichero y no en
    `notes.py`, y por eso no necesita ninguna restauracion de las que sus
    hermanas si usan. SI toma el mismo candado global que ellas.

    Las rutas se resuelven a absolutas ANTES de tocar git, con
    `os.path.abspath()` (no `Path.resolve()`, que seguiria symlinks y
    reescribiria una ruta ya absoluta bajo un symlink, como `tmp_path` en
    macOS): `paths` llega relativo al cwd real desde el que se invoco el
    script, que puede ser una subcarpeta -- resolverlo aqui, contra
    `os.getcwd()`, antes de que `stage_and_commit()` lo ancle a `root`
    para las dos llamadas a git, deja de importar donde se interprete.

    Limpia el staging area si el commit falla, mismo mecanismo que sus
    tres hermanas (mejor esfuerzo).

    **Concurrencia -- por que existen el candado, `known_content` y la
    verificacion post-commit.** Esta funcion, a diferencia de
    `write()`/`replace()`/`close()`, no toca ningun indice propio del
    sistema, asi que su unica proteccion contra otro escritor real es lo
    que describe aqui:

    1. Candado global (`gitcmd.file_lock(lock_resource(root))`): sin el,
       escritores concurrentes reales chocaban contra
       `.git/index.lock` sin reintento.

    2. El candado NO basta: `gitcmd.commit()` usa la forma con pathspec
       (`git commit -- <rutas>`), que RELEE EL ARBOL DE TRABAJO en el
       instante del commit. Si otro proceso, ajeno a este candado, pisa
       una ruta con su propio `git add` antes de que esta funcion
       arranque, el commit se llevaria SU contenido bajo el mensaje de
       quien llamo aqui -- un commit permanente que miente sobre lo que
       guardo. `_staged_as_new_before_us()` detecta esa senal (la ruta ya
       aparece en el indice como fichero nuevo) y se niega a comitear en
       vez de mentir con `ok=True`.

    3. Eso no cubre un fichero YA TRACKEADO que dos escritores pisan por
       turnos sin ningun `git add` externo. Comparar una huella leida del
       disco (al entrar, y otra vez antes de comitear) tampoco basta: si
       la pisada ya ocurrio ANTES de que esta funcion arrancara, las dos
       lecturas coinciden entre si y el problema pasa desapercibido. La
       unica forma real de cerrarlo es que la huella de referencia no la
       lea esta funcion del disco, sino que la calcule el propio llamador
       a partir de los bytes que el mismo acaba de escribir en memoria, y
       se la pase aqui: `known_content`, opcional y en la misma
       posicion/orden que `paths` (una lista de `bytes`, o `None` por
       ruta sin contenido conocido de antemano).

       **Decision del propietario:** dos escrituras de verdad
       simultaneas al mismo fichero de trabajo (dos `gitmem work`
       reales, no solo dos llamadas a esta funcion) no tienen que
       funcionar las dos -- el caso se descarta, no se persigue mas
       alla de lo que el candado y `known_content` ya cierran.

    4. Incluso con huellas en memoria, queda una rendija: `stage_and_commit()`
       hace `git add --all` y LUEGO `gitcmd.commit()`, que relee el
       arbol de trabajo otra vez en el instante del commit. Si el otro
       escritor pisa el fichero justo ahi, el commit se lleva su
       contenido bajo nuestro mensaje. La unica forma de cerrarlo es
       comprobar DESPUES de comitear, contra lo que `HEAD` de verdad
       quedo llevando: para cada `path` con `known_content` conocido, el
       hash de blob que tendrian esos bytes (`_git_blob_hash_of_bytes`)
       tiene que coincidir exactamente con el blob que `HEAD` tiene para
       esa ruta (`_committed_blob_hash`). Si no coincide -- o si
       cualquiera de las dos consultas falla, tratado igual que un
       desajuste -- el commit reciente es sospechoso y se intenta
       deshacer. Sin `known_content` para una ruta, esa ruta no se
       verifica (mismo hueco aceptado en el punto 3).

    5. **Deshacer un commit sospechoso tiene que ser un solo acto
       atomico, nunca "comprobar y luego actuar"**: cualquier hueco entre
       mirar `HEAD` y mover `HEAD` es una ventana donde un commit ajeno
       legitimo se pierde igual. El mecanismo:

       a. `own_commit_sha` se PARSEA de la primera linea de la salida
          del propio `git commit` (`_own_commit_sha_from_commit_output()`),
          nunca de un `rev-parse HEAD` posterior -- la misma llamada que
          crea el commit, sin hueco en el que envenenarla.
       b. El padre se resuelve con `git rev-parse <own_commit_sha>~1` --
          por CONTENIDO (el padre de ESTE commit), nunca `HEAD~1` (una
          referencia que se mueve).
       c. Deshacer es UNA sola llamada: `git update-ref -m <razon> HEAD
          <padre> <own_commit_sha>` -- mueve `HEAD` al padre SOLO SI su
          valor actual es, exactamente, `own_commit_sha`; comprobacion y
          movimiento son la MISMA operacion atomica bajo el candado de
          referencias de git. Si `HEAD` ya no es `own_commit_sha`, el
          comando falla solo, sin tocar nada.
       d. Solo si eso tuvo exito se sincroniza el indice con
          `git reset --mixed HEAD` (higiene, mejor esfuerzo).
       e. Las tres ramas de fallo (commit propio no identificado; commit
          sin padre; `update-ref` fallo) nombran `own_commit_sha` siempre
          que el commit corrupto sigue vivo.

    Cualquier verificacion de contenido que se añada aqui en el futuro
    necesita las dos disciplinas a la vez: el acto decisivo tiene que ser
    atomico contra la referencia que puede moverse, y el calculo de hash
    tiene que reproducirse contra lo que git REALMENTE almacena en la
    plataforma real (`_git_blob_hash_of_bytes()` hasheaba bytes crudos
    con `--no-filters` hasta que eso rompio en Windows: `core.autocrlf`
    normaliza `\\r\\n` a `\\n` al guardar, asi que el hash crudo nunca
    coincidia con el blob LF que git de verdad guardaba -- `--path <ruta
    real>`, no `--no-filters`, es lo que reproduce el filtro correcto).
    """
    resolved_paths = [Path(os.path.abspath(str(p))) for p in paths]
    if known_content is not None and len(known_content) != len(paths):
        raise ValueError(
            f"known_content tiene {len(known_content)} elemento(s) pero paths "
            f"tiene {len(paths)} -- tienen que ir en el mismo orden, uno por ruta"
        )
    try:
        entry_fingerprints = {
            path: hashlib.sha256(content).hexdigest() if content is not None else _content_fingerprint(path)
            for path, content in zip(resolved_paths, known_content or [None] * len(paths))
        }
    except OSError as exc:
        return WriteResult(ok=False, note_id=None, rejections=(), git_error=str(exc))
    root = repo_root()
    full_message = message if issue is None else f"{message}\n\nIssue: #{issue}"

    with gitcmd.file_lock(lock_resource(root)):
        for path in resolved_paths:
            if _staged_as_new_before_us(path, root):
                return WriteResult(
                    ok=False,
                    note_id=None,
                    rejections=(),
                    git_error=(
                        f"{path} ya aparecia en el indice de git como fichero nuevo "
                        "antes de esta llamada a write_work() -- otro proceso lo "
                        "'git add'-eo por su cuenta, fuera de este candado; "
                        "'git commit -- <ruta>' relee el arbol de trabajo en el "
                        "instante del commit, asi que comitear ahora podria mentir "
                        "sobre el contenido que este escritor preparo. Se aborta con "
                        "causa en vez de comitear un contenido que no se puede verificar."
                    ),
                )

        changed_since_entry = [
            path
            for path in resolved_paths
            if _content_fingerprint(path) != entry_fingerprints[path]
        ]
        if changed_since_entry:
            changed_list = ", ".join(str(p) for p in changed_since_entry)
            return WriteResult(
                ok=False,
                note_id=None,
                rejections=(),
                git_error=(
                    f"el contenido de {changed_list} cambio en disco entre que esta "
                    "llamada a write_work() empezo y el instante de comitear -- otro "
                    "proceso lo escribio por su cuenta mientras esta llamada seguia en "
                    "curso. Se aborta con causa en vez de comitear un contenido que ya "
                    "no es el que este escritor tenia al arrancar."
                ),
            )

        git_result = stage_and_commit(full_message, resolved_paths, root)

        if git_result.returncode != 0:
            gitcmd.run(
                ["reset", "--", *(str(p) for p in resolved_paths)],
                cwd=root,
                timeout=gitcmd.GIT_TIMEOUT,
            )
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        # Leido de la salida del PROPIO `git commit` -- nunca de un
        # `rev-parse HEAD` posterior. Ver el docstring de la funcion de
        # arriba y el punto 9 mas abajo para el porque exacto (agujero 5).
        own_commit_sha = _own_commit_sha_from_commit_output(git_result.stdout, root)

        mismatched = []
        for path, content in zip(resolved_paths, known_content or [None] * len(resolved_paths)):
            if content is None:
                continue
            expected_hash = _git_blob_hash_of_bytes(content, path, root)
            actual_hash = _committed_blob_hash(path, root)
            if expected_hash is None or actual_hash is None or expected_hash != actual_hash:
                mismatched.append(path)

        if not mismatched:
            return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)

        mismatched_list = ", ".join(str(p) for p in mismatched)
        base_cause = (
            f"el commit se creo pero {mismatched_list} no lleva el contenido "
            "que este escritor tenia en la mano -- otro proceso lo piso justo "
            "en el instante de comitear ('git commit -- <rutas>' relee el "
            "arbol de trabajo, punto 8 del docstring de esta funcion)."
        )

        if own_commit_sha is None:
            return WriteResult(
                ok=False,
                note_id=None,
                rejections=(),
                git_error=(
                    base_cause + " Ademas, no se pudo identificar de forma "
                    "fiable el commit que esta llamada acaba de crear -- no "
                    "se intenta deshacer nada sin esa referencia. Hace falta "
                    "revision manual."
                ),
            )

        # `<sha>~1` es una busqueda por CONTENIDO (el padre de ESTE commit
        # concreto), no por referencia -- resuelve igual sin importar donde
        # este `HEAD` ahora mismo, asi que no tiene la ventana del punto 9.
        parent_result = gitcmd.run(
            ["rev-parse", f"{own_commit_sha}~1"], cwd=root, timeout=gitcmd.GIT_TIMEOUT
        )
        parent_sha = parent_result.stdout.strip() if parent_result.returncode == 0 else None

        if parent_sha is None:
            return WriteResult(
                ok=False,
                note_id=None,
                rejections=(),
                git_error=(
                    base_cause + f" El commit {own_commit_sha} es el primero "
                    "del repositorio -- no tiene padre al que volver, asi que "
                    f"no se puede deshacer. El commit corrupto {own_commit_sha} "
                    "SIGUE siendo HEAD de verdad. Hace falta arreglarlo a "
                    "mano: revisar y quitar ese commit."
                ),
            )

        # Punto 9: un unico acto atomico, no una comprobacion seguida de un
        # acto -- `git update-ref` mueve `HEAD` a `parent_sha` SOLO SI su
        # valor actual sigue siendo, exactamente, `own_commit_sha`; la
        # comparacion y el movimiento son la MISMA operacion, bajo el
        # candado de referencias del propio git, sin ningun hueco entre
        # "mirar" y "actuar" que un proceso ajeno pueda colarse por medio.
        cas_result = gitcmd.run(
            [
                "update-ref",
                "-m",
                f"write_work(): deshacer commit corrupto {own_commit_sha}",
                "HEAD",
                parent_sha,
                own_commit_sha,
            ],
            cwd=root,
            timeout=gitcmd.GIT_TIMEOUT,
        )

        if cas_result.returncode != 0:
            return WriteResult(
                ok=False,
                note_id=None,
                rejections=(),
                git_error=(
                    base_cause + " El intento de deshacerlo con 'git "
                    f"update-ref' fallo ({cas_result.stderr}) -- lo mas "
                    "probable es que el historial se moviera entre nuestro "
                    "commit y este intento (otro proceso ajeno ya comiteo "
                    "algo legitimo encima), y por eso NO se toca el "
                    f"historial en absoluto. El commit corrupto "
                    f"{own_commit_sha} sigue siendo alcanzable. Hace falta "
                    "revision manual."
                ),
            )

        # `HEAD` ya apunta, de forma segura y verificada, a `parent_sha` --
        # sincronizar el indice ahora es solo higiene (mejor esfuerzo, sin
        # comprobar el resultado, igual que el resto de restauraciones de
        # este fichero): no mueve ninguna referencia, asi que ninguna carrera
        # posterior puede volver a comerse un commit ajeno por esta via.
        gitcmd.run(["reset", "--mixed", "HEAD"], cwd=root, timeout=gitcmd.GIT_TIMEOUT)

        return WriteResult(
            ok=False,
            note_id=None,
            rejections=(),
            git_error=(
                base_cause + " Se deshizo el commit ('git update-ref', "
                "comparar-y-cambiar atomico sobre HEAD, sin tocar el arbol "
                "de trabajo) y se devuelve ok=False con causa en vez de "
                "mentir con ok=True."
            ),
        )
