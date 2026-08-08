"""Mecanica de git que `notes.py` usa por debajo -- candado global,
composicion de la ruta de los ocho indices, `git add`+`git commit` con
restauracion de mejor esfuerzo si falla, y el commit de trabajo que no
toca ningun indice. Partido de `notes.py` por tamano (550 lineas, techo
500 -- mismo limite que ya se aplico a `format.py` [DEUDA.md punto 12]
y `validator.py` [DEUDA.md punto 14]).

Este fichero NO es una segunda transaccion ni una segunda puerta de
escritura: sigue habiendo un solo lugar donde nota+indice se escriben
juntos o ninguno de los dos [PIEZAS.md Sec.8.1] -- ese lugar sigue
siendo `notes.write()`/`replace()`/`close()`, que se quedan enteros en
`notes.py`. Lo que vive aqui es la mecanica de la que esas tres tiran
por debajo, sin saber nada de `Note`, de `Context` ni de que indice le
corresponde a que tipo -- eso sigue siendo terreno exclusivo de
`notes.py`.

QUE ES LO QUE SE PARTIO, Y POR QUE ESTE CORTE Y NO OTRO: `lock_resource`,
`repo_root`, `pm_root`, `stage_and_commit` y las dos restauraciones de
mejor esfuerzo (`restore_index_best_effort`/`restore_snapshot_best_effort`)
no conocen `Note` -- solo mueven rutas, un candado y comandos de git.
`write_work` encaja en el mismo grupo por un motivo distinto: es la
unica de las cinco operaciones de `notes.py` que NO toca ningun indice
[Superficie de PIEZAS.md Sec.8.1: "no lleva campo de ficheros
tocados"], asi que nunca necesita ninguna restauracion -- no hay indice
que proteger. **SI toma el mismo candado global que sus hermanas**
(arreglo 2026-08-03, ver el docstring de `write_work` puntos 5, 6 y 7):
sin el, escritores concurrentes reales chocaban contra `.git/index.lock`
sin reintento, y el candado por si solo tampoco bastaba -- se niega a
comitear en vez de mentir cuando detecta que otro proceso, fuera de este
candado, ya toco la misma ruta antes de tiempo (punto 6, por el indice de
git) o cambio su contenido en disco mientras esta llamada seguia en curso
(punto 7, por huella de contenido -- cierra la carrera a nivel de esta
funcion: reproducido con dos escritores reales sin ningun `git add`
externo, 11 de 20 intentos con mensaje y contenido cruzados antes de
este punto, 0 de 20 despues [DEUDA.md punto 27 se cerro 2026-08-04 por
decision del propietario, B22 -- no solo por este arreglo; ver el punto
7 de `write_work()` mas abajo]). Sacarla junto a
la mecanica que si usa deja en `notes.py` las tres
operaciones que si son la transaccion central (`write`/`replace`/
`close`) mas `discard_alternatives`, que no es mas que una envoltura de
`write()`.

ESTE FICHERO NO IMPORTA NADA DE `notes.py` -- direccion unica, para que
no haya ciclo [mismo principio que `format_lines.py`/`validator_zones.py`
ya aplican hoy mismo]. `notes.py` importa los siete nombres de aqui de
forma PLANA [PIEZAS.md Sec.3.3bis] y los reexpone bajo el mismo nombre,
asi que `notes.pm_root`/`notes.write_work` siguen alcanzables
exactamente igual para quien los llame hoy -- se verifico antes de
partir que ninguno de sus llamadores reales (`health.py`, `boot.py`,
`report.py`, `tests/memory/test_notes.py`) importa este fichero
directamente, y que ningun test referencia los nombres privados
anteriores (`_lock_resource`, `_repo_root`, `_stage_and_commit`,
`_restore_index_best_effort`, `_restore_snapshot_best_effort`) fuera de
prosa de comentario.

`lock_resource`, `repo_root`, `stage_and_commit`,
`restore_index_best_effort` y `restore_snapshot_best_effort` pierden su
guion bajo al cruzar de fichero -- mismo motivo que ya hizo publica a
`pm_root` (ver el punto 5 mas abajo, "correccion 2026-08-02"): dejan de
ser un detalle interno de un solo modulo para ser mecanica que
`notes.py` importa desde fuera. `write()`/`replace()`/`close()`, en
`notes.py`, siguen siendo los unicos llamadores reales de las dos
restauraciones -- no hay una segunda implementacion en ningun sitio, y
por tanto ninguna forma de que diverjan entre si, que es justo lo que
este corte tiene que evitar [el propio encargo: "el aparato compartido
no se parte... si acaba en dos sitios, se desincroniza"].

DECISIONES QUE FIJAN ESTA MECANICA (derivadas del contrato de
`notes.py` y verificadas contra un repo git real antes de fijarlas --
la historia completa de la transaccion vive en el docstring de
`notes.py` Sec.8.1; aqui solo las que describen el CODIGO que vive en
este fichero):

1. **Candado GLOBAL, no por indice.** `gitcmd.file_lock()` no es
   reentrante (gitcmd.py Sec.7.1) -- si la transaccion tomara el
   candado sobre la RUTA del propio indice y luego llamara a
   `indexes.insert()` (que toma ESE MISMO candado por dentro), la
   segunda toma revienta con `LockNotReentrantError` de inmediato. Para
   poder seguir usando `indexes.insert()`/`indexes.remove()` "tal
   cual", la transaccion toma un candado DISTINTO --
   `<root>/.git/memory-notes.lock` -- que envuelve la operacion
   COMPLETA (identificador -> validar -> insertar -> git add -> git
   commit). `indexes.insert()`/`remove()` siguen tomando su propio
   candado por RUTA DE FICHERO por dentro, sin chocar nunca con este
   (son rutas distintas). Ademas evita una carrera real con `git`
   mismo: sin este candado envolviendo tambien `git add`/`git commit`,
   dos escritores concurrentes podrian pelearse por `.git/index.lock`
   de verdad, no solo por el indice propio del sistema de memoria.

2. **`git add` explicito antes de `git commit`.** `gitcmd.commit()`
   commitea EXACTAMENTE las rutas dadas [gitcmd.py Sec.7.1] pero no
   hace `git add` por su cuenta. Verificado contra un repo git real (no
   supuesto): `git commit -m msg -- fichero-nuevo-sin-trackear` falla
   con `pathspec 'fichero' did not match any file(s) known to git` --
   la PRIMERA escritura a cada uno de los ocho indices (creados por
   `indexes.seed()` pero nunca comiteados) necesita `git add` antes.
   Para ficheros ya trackeados y modificados, `git add` es inocuo -- por
   eso se anade siempre, sin ramificar por si es la primera escritura o
   no.

3. **Restaurar el indice tras un fallo de git es `indexes.remove()`, no
   una copia de bytes a mano** -- solo aplica a
   `restore_index_best_effort`, la vuelta de `notes.write()`.
   `indexes.insert()` seguido de `indexes.remove()` del mismo id es una
   vuelta exacta (append + split/join con newline final son inversos
   exactos) -- reutiliza la pieza ya escrita en vez de guardar el
   contenido previo aparte. `replace()`/`close()` no pueden usar esta
   misma tactica -- su restauracion es `restore_snapshot_best_effort`,
   snapshot completo capturado antes de escribir, porque una linea
   existente puede estar en cualquier posicion del indice y anadirla al
   final (lo que haria `indexes.insert()`) la moveria [razon completa
   en el docstring de `notes.py`, punto 4 de su lista].

4. **Las dos restauraciones son mejor esfuerzo, a proposito.** Si la
   propia restauracion revienta, su excepcion se traga en vez de
   sustituir el diagnostico real (el `GitResult.stderr` de git, o la
   excepcion que interrumpio el commit) -- perder ESE mensaje es perder
   la unica causa que el usuario tiene para arreglar el problema. Quien
   llama (`notes.py`) decide que hacer con el diagnostico original;
   esta mecanica nunca lo tapa con uno propio.

5. **Los ocho indices viven en `pm_root(root)`, no en `root` a secas --
   correccion 2026-08-02.** `pm_root()` es publica (sin guion bajo) por
   el mismo motivo que las otras cuatro lo son al cruzar a este
   fichero: `notes.py` la reexpone porque `health.coherence()`/
   `health.duplicates()` (Sec.9.4) necesitan la MISMA raiz para leer
   los mismos ocho ficheros que `notes.py` escribe -- una sola
   decision, importada por quien la necesita. `report.py` ya compone
   la misma ruta con su propia funcion privada (`_pm_root`, fuera de
   este alcance) -- coincide byte a byte, no se toca aqui. **Lo que NO
   cambia:** el candado (`lock_resource`), el `git add`/`git commit`
   (`stage_and_commit`) y `repo_root()` siguen anclados a la raiz
   PELADA del repositorio -- son mecanismo de git, no ubicacion de
   indices, y `.git/` solo existe ahi.

No importa nada del toolkit fuera de la biblioteca estandar de Python
[PIEZAS.md Sec.13]. Imports planos entre hermanos de `lib/memory/`
[PIEZAS.md Sec.3.3bis]. No importa nada de `notes.py` -- direccion
unica, ver mas arriba.
"""

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
    docstring del modulo. `gitcmd.file_lock()` anade su propio sufijo
    `.lock`; el fichero real en disco es `<root>/.git/memory-notes.lock`.
    Vive dentro de `.git/`, no en el arbol de trabajo, para que nunca
    aparezca como cambio sin trackear en `git status`.
    """
    return Path(root) / ".git" / "memory-notes"


def repo_root() -> Path:
    return gitcmd.repo_root(Path.cwd())


def pm_root(root: Path) -> Path:
    """Raiz real de los ocho indices y de `ARCHIVED.md` --
    `.claude/project-memory/` del proyecto, junto a `zones.json`/
    `config.json` [spec Sec.7 en su propio titulo; ARQUITECTURA.md
    Sec.6bis; PIEZAS.md Sec.9.7, "junto a los ocho indices"]. `root` es
    la raiz PELADA del repositorio git (`repo_root()`), hermana de
    `.git/` -- nunca el destino final por si sola. Ver punto 5 del
    docstring del modulo para el incidente que esta funcion cierra.

    Publica (sin guion bajo), mismo motivo y misma fecha que
    `rules.rules_file_path()` [rules.py Sec.9.7]: `health.coherence()` /
    `health.duplicates()` (Sec.9.4) necesitan la MISMA raiz para leer los
    mismos ocho ficheros que `notes.py` escribe -- una sola decision,
    importada por quien la necesita (`import notes`, hermano plano), en
    vez de una copia local por modulo. `report.py` ya compone la misma
    ruta con su propia funcion privada (`_pm_root`, fuera del alcance de
    este arreglo) -- coincide byte a byte, no se toca aqui.
    """
    return Path(root) / ".claude" / "project-memory"


def stage_and_commit(message: str, paths: list[Path], root: Path) -> gitcmd.GitResult:
    """`git add` explicito (punto 2 del docstring del modulo) seguido de
    `gitcmd.commit()`. Devuelve el `GitResult` del primer paso que falle,
    o el del commit si ambos salen bien.

    `root` viaja explicito a LAS DOS llamadas -- corregido 2026-08-02,
    hallazgo real: `git add` ya usaba `cwd=root` pero `gitcmd.commit()`
    (antes de este arreglo) no aceptaba `cwd` y heredaba el ambiental del
    proceso. Un commit de trabajo lanzado desde una subcarpeta interpretaba
    el MISMO pathspec relativo desde dos sitios distintos: `git add`
    resolvia contra `root`, `git commit` contra la subcarpeta -- el commit
    fallaba (el pathspec no casaba con nada staged desde ese cwd) pero el
    `git add` ya habia dejado staged, en `root`, un fichero que ni siquiera
    era el que el usuario queria tocar. Con `root` explicito en las dos, un
    pathspec ya absoluto (ver `write_work()`) se resuelve identico sin
    importar desde donde se invoque el script.
    """
    # `--all` (no el `add` pelado): sin el, un BORRADO era imposible de
    # guardar con el sistema puesto, y se descubrio ejecutandolo
    # [2026-08-05]. `git add -- <ruta>` de un fichero que acaba de entrar
    # en el `.gitignore` falla en cerrado ("paths are ignored by one of
    # your .gitignore files"), y `git commit` a pelo lo bloquea la aduana:
    # dejar de versionar un fichero se quedaba sin ninguna salida. No es
    # un caso raro -- ocurre cada vez que algo pasa a ignorarse.
    #
    # `--all` es el modo que registra tambien la desaparicion de una ruta.
    # NO ensancha lo que se comitea: sigue acotado al mismo pathspec
    # explicito de `paths`, nunca al arbol entero, asi que el contrato de
    # "commitea SOLO estas rutas, sin arrastrar el resto del indice" --
    # el que exige la publicacion del toolkit [plan Sec.2.7] -- se
    # mantiene intacto.
    add_result = gitcmd.run(
        ["add", "--all", "--", *(str(p) for p in paths)],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    if add_result.returncode != 0:
        return add_result
    return gitcmd.commit(message, paths, allow_empty=False, cwd=root)


def restore_index_best_effort(note_id: str, index_name: str, pm: Path) -> None:
    """Revierte la linea de `note_id` en `index_name` tras un commit que
    no llego a completarse -- la vuelta exacta que el punto 3 del
    docstring del modulo describe (`indexes.insert()` seguido de
    `indexes.remove()` del mismo id). Restauracion de `notes.write()`
    exclusivamente -- `replace()`/`close()` usan
    `restore_snapshot_best_effort`, no esta.

    `pm` es `pm_root(root)`, no la raiz pelada del repositorio -- ahi es
    donde vive `index_name` de verdad (punto 5 del docstring del
    modulo). Pasar la raiz pelada aqui haria que `indexes.remove()`
    buscara el fichero en el sitio equivocado, fallara con
    `FileNotFoundError`, y esa excepcion se tragaria en silencio (mejor
    esfuerzo, ver mas abajo) -- la linea de indice quedaria huerfana sin
    que nadie lo note, exactamente el fallo que esta funcion existe para
    reparar.

    Mejor esfuerzo, a proposito (punto 4 del docstring del modulo): si
    `indexes.remove()` revienta aqui, su excepcion NO debe sustituir el
    motivo real por el que se esta restaurando (el fallo de git, o la
    excepcion que interrumpio el commit). Quien llama decide que hacer
    con el diagnostico original; esta funcion nunca lo tapa con uno
    propio.
    """
    try:
        indexes.remove(note_id, index_name, pm)
    except Exception:
        pass


def restore_snapshot_best_effort(path: Path, original_content: str) -> None:
    """Restaura `path` a `original_content` -- vuelta de `replace()`/
    `close()` para el indice viejo y ARCHIVED.md [razon completa en el
    docstring de `notes.py`, punto 4 de su lista: una linea existente
    puede estar en cualquier posicion, y `indexes.insert()` la moveria
    al final]. Mejor esfuerzo, mismo motivo que
    `restore_index_best_effort()`.
    """
    try:
        gitcmd.atomic_write(path, original_content)
    except Exception:
        pass


def _staged_as_new_before_us(path: Path, root: Path) -> bool:
    """`True` si `path` YA aparece en el indice de git como fichero NUEVO
    (sin version previa en HEAD) antes de que `write_work()` haga su
    propio `git add` -- la firma de que otro escritor lo `git add`-eo por
    su cuenta justo antes, fuera de este candado (ver el punto 6 del
    docstring del modulo para el porque exacto de esta senal).

    `git diff --cached --name-status -- <path>` compara INDICE contra
    HEAD para esa ruta exacta: una linea que empieza por `A` (anadido)
    significa que el indice ya tiene contenido para `path` que HEAD
    todavia no conoce. `M` (modificado) o salida vacia no cuentan --
    fila 5 de `test_notes.py` (`test_write_work_with_explicit_paths_
    does_not_drag_rest_of_tree`) preestagea a proposito tres ficheros YA
    trackeados antes de llamar a `write_work()`, y ese uso es legitimo
    [verificado contra el test real antes de fijar esta condicion: usar
    `--name-status` sin filtrar por `A` habria rechazado ese test].
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
    que mira el INDICE de git; esto lee el ARBOL DE TRABAJO directamente,
    con `open()`/`read()`, sin pasar por ningun comando de git ni por su
    latencia de subproceso. Es la pieza que cierra el hueco declarado en
    el punto 6 del docstring de `write_work()`: para un fichero YA
    TRACKEADO que dos escritores pisan por turnos, el INDICE no distingue
    las dos situaciones (ver el porque exacto ahi), pero el CONTENIDO
    crudo si -- sha256 de los bytes es identico solo si los bytes lo son.

    sha256 sobre bytes crudos, no sobre texto interpretado: sirve igual
    para cualquier fichero de trabajo (codigo fuente arbitrario), no solo
    para las notas del propio sistema, y no depende de que la codificacion
    se adivine bien.
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
    escribiera en `path` y se hiciera `git add` -- SIN escribirlo al
    object store (`hash-object` sin `-w`) y sin tocar el arbol de trabajo
    real: `content` se vuelca a un fichero temporal fuera del repo
    (siempre borrado, salga bien o mal la consulta) solo porque
    `gitcmd.run()` no expone stdin. `None` si `git hash-object` fallo --
    nunca se trata como si coincidiera con nada [punto 8 de
    `write_work()`].

    **`--path <ruta relativa real>` es obligatorio, y `--no-filters` esta
    PROHIBIDO -- arreglo 2026-08-08, corrigiendo un hallazgo previo mal
    resuelto.** La primera version de esta funcion usaba `--no-filters`
    para blindarse contra un filtro de `.gitattributes` resuelto por la
    ruta INCORRECTA (la del temporal) -- razonamiento correcto, arreglo
    equivocado: `--no-filters` hashea los BYTES CRUDOS, pero
    `stage_and_commit()` comitea pasando por el `git add` normal, que SI
    aplica los filtros de la ruta real -- en Windows, por defecto,
    `core.autocrlf` normaliza `\\r\\n` a `\\n` al guardar. El resultado:
    en cualquier repo con autocrlf activo, esta funcion comparaba el hash
    de los bytes CRLF crudos contra el blob LF que git de verdad guardo
    -- SIEMPRE distinto, para CUALQUIER escritura, sin que nadie pisara
    nada. Rompio `gitmem wip` en CI de Windows: cada commit valido salia
    "corrupto" y se deshacia. Reproducido y confirmado antes de tocar
    nada: en un repo con `core.autocrlf=true`, `git hash-object
    --no-filters` sobre bytes CRLF NO coincide con el blob real
    (`rev-parse HEAD:<ruta>`); `git hash-object --path <ruta>` (sin
    `--no-filters`) SI coincide, byte a byte con lo que git de verdad
    almacena. `--path` resuelve el mismo problema que `--no-filters`
    intentaba resolver -- que filtro de `.gitattributes` aplica -- pero
    contra la ruta CORRECTA (la real, no la del temporal), en vez de
    desactivar los filtros por completo. La promesa de esta funcion ya no
    es "el hash de estos bytes exactos" -- es "el hash que estos bytes
    tendrian SI se guardaran en `path`", que es lo unico que puede
    coincidir con lo que `stage_and_commit()` de verdad comitea.
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
    o `None` si no se pudo determinar (ruta ausente en `HEAD`, fallo de
    git) -- nunca se trata como si coincidiera con nada [punto 8 de
    `write_work()`].
    """
    rel = _relpath_posix(path, root)
    result = gitcmd.run(["rev-parse", f"HEAD:{rel}"], cwd=root, timeout=gitcmd.GIT_TIMEOUT)
    return result.stdout.strip() if result.returncode == 0 else None


# `[<rama> <sha-corto>] <asunto>` o `[<rama> (root-commit) <sha-corto>]
# <asunto>` -- la linea de resumen que `git commit` imprime en su PROPIA
# salida estandar salvo que se le pida `--quiet` (esta funcion no lo
# hace). `.+` es voraz a proposito: si el asunto del mensaje contiene un
# `]` mas temprano, el motor de regex retrocede hasta encontrar el
# ULTIMO `<espacio><hex>]` de la primera linea -- que es siempre el que
# cierra el resumen de git, sin importar cuantos espacios lleve el
# nombre de la rama (p.ej. HEAD separado: `[detached HEAD abcdef1]`).
_COMMIT_SUMMARY_SHA_RE = re.compile(r"^\[.+\s([0-9a-fA-F]{4,40})\]")


def _own_commit_sha_from_commit_output(commit_stdout: str, root: Path) -> str | None:
    """Identificador COMPLETO (40 caracteres) del commit que `git commit`
    ACABA de crear, leido de la PRIMERA linea de SU PROPIA salida --
    nunca de un `git rev-parse HEAD` en un subproceso posterior [agujero
    5, hallado por Cerberus en vivo, 2026-08-08]. Entre el `git commit`
    que crea nuestro commit y CUALQUIER subproceso siguiente que relea
    `HEAD` como referencia (una rama que se mueve), un proceso ajeno
    puede comitear encima -- `HEAD` para entonces ya no es nuestro
    commit, y esa lectura envenenaria la referencia desde el origen,
    antes incluso de que nada la compare con nada. La linea de resumen
    de `git commit` no tiene ese hueco: es la MISMA llamada que crea el
    commit, nunca una posterior.

    El sha corto de esa linea se expande a los 40 caracteres completos
    con `git rev-parse <corto>^{commit}` -- una busqueda por CONTENIDO
    (el objeto ya existe en la base de datos de git bajo ese hash), NUNCA
    por REFERENCIA (`HEAD`/una rama, que puede moverse). Un commit ajeno
    que aterrice entre medias no cambia a que apunta un hash de
    contenido que ya existe, asi que esta segunda llamada, aunque es un
    subproceso separado, no tiene la misma ventana que un `rev-parse
    HEAD` -- solo depende de que el objeto exista, nunca de que ref
    apunte a donde en este instante.

    `None` si la primera linea no tiene la forma esperada o si la
    expansion falla -- nunca se trata como si hubiera un identificador
    valido.
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
    del arbol [PIEZAS.md Sec.8.1] -- lo necesita la publicacion del
    toolkit, que commitea unos pocos ficheros sin llevarse cambios a
    medias de otros. No lleva campo de ficheros tocados (se retiro del
    v2 [plan Sec.1, decision 1]): `git log -- <ruta>` ya responde eso.

    `issue`, si se da, viaja como trailer `Issue: #N` al final del
    mensaje -- mismo formato literal que ya usa `format.py` para el
    campo `Issue` de una nota (`f"Issue: #{note.issue}"`), reutilizado
    aqui porque ningun texto de TEXTOS.md fija un formato distinto para
    un commit de trabajo.

    No toca ningun indice de nota -- por eso vive en este fichero y no en
    `notes.py`, y por eso no necesita ninguna restauracion de las que sus
    hermanas si usan. **Si toma el mismo candado global** que ellas
    (`gitcmd.file_lock(lock_resource(root))`) -- arreglo 2026-08-03, punto
    5/6 mas abajo.

    **Las rutas se resuelven a absolutas ANTES de tocar git** -- corregido
    2026-08-02, mismo hallazgo real que el docstring de `stage_and_commit()`
    explica: `paths` llega tal como el usuario lo escribio (relativo al cwd
    REAL desde el que invoco el script, que puede ser una subcarpeta del
    repositorio). Resolverlo aqui, contra `os.getcwd()` -- el mismo cwd
    ambiental con el que el usuario lo tecleo, nunca `root` -- antes de que
    `stage_and_commit()` lo ancle a `root` para las dos llamadas a git,
    deja de importar que la ruta se interprete en un sitio o en otro: ya es
    la misma cadena absoluta en las dos. `os.path.abspath()` y no
    `Path.resolve()`: normaliza (cwd + `..`/`.`) sin seguir symlinks, para
    no cambiar por debajo una ruta que un llamador ya paso absoluta (los
    tests de este modulo construyen sus rutas desde `tmp_path`, que en
    macOS vive bajo un symlink -- `resolve()` la reescribiria).

    **Limpia el staging area si el commit falla** -- corregido 2026-08-02,
    agravante del mismo hallazgo: a diferencia de `write()`/`replace()`/
    `close()` (`notes.py`), que ya deshacen el `git add` con `git reset --
    <ruta>` cuando `git commit` falla, esta funcion no lo hacia -- un
    commit fallido dejaba en `.git/index` lo que `git add` alcanzo a
    stagear, staged todavia, para que el proximo `git status` lo enseñara
    como un cambio pendiente que nadie pidio. Mismo mecanismo que sus tres
    hermanas, mejor esfuerzo (no se comprueba el resultado del `reset`: si
    el commit ya fallo, ese es el diagnostico real que hay que devolver).

    **5. Candado global -- arreglo 2026-08-03, capa 3, hallazgo de
    Moriarty.** Esta funcion comiteaba SIN el candado que sus tres
    hermanas si toman -- bajo escritores concurrentes reales (cada uno con
    su PROPIA ruta), 7-8 de cada 10 morian con `fatal: Unable to create
    '.git/index.lock': File exists` (git no reintenta por su cuenta).
    Envolver el cuerpo entero en `gitcmd.file_lock(lock_resource(root))`
    -- MISMO candado que `write`/`replace`/`close`, mismo motivo del punto
    1 del docstring del modulo (serializar tambien `git add`/`git commit`,
    no solo el estado propio del sistema) -- lo cierra: los N escritores
    ahora esperan su turno en vez de chocar contra git.

    **6. La mentira silenciosa -- misma fecha, la otra mitad del mismo
    hallazgo.** El candado NO basta: `gitcmd.commit()` usa la forma con
    pathspec (`git commit -- <rutas>`), que RELEE EL ARBOL DE TRABAJO en
    el instante del commit en vez de usar lo que un `git add` anterior
    dejo preparado [docstring de `gitcmd.commit()`, verificado contra git
    real]. Si otro proceso, AJENO a este candado (nunca llama a
    `write_work()`, asi que el candado no lo ve), pisa una ruta con
    `git add` propio ANTES de que esta funcion arranque, el commit se
    lleva SU contenido bajo el mensaje de quien llamo aqui, y sin
    deteccion habria devuelto `ok=True` -- un commit permanente que miente
    sobre lo que guardo. Reproducido en vivo: 3 de cada 20 intentos.

    Recuperar el contenido bueno es imposible en ese momento -- ya no
    existe en ningun sitio (ni en el arbol de trabajo, ni en el indice) --
    asi que esta funcion NO lo intenta. En su lugar, antes de tocar nada,
    comprueba con `_staged_as_new_before_us()` si alguna `path` ya
    aparece en el indice como fichero NUEVO (senal de que otro `git add`,
    fuera de este candado, ya la toco): si es asi, se niega a comitear y
    devuelve `ok=False` con la causa real en `git_error` -- fallar con
    causa en vez de mentir con `ok=True` [encargo explicito: "fallar con
    causa es una salida correcta; responder ok=True sin serlo, no"].

    **7. El hueco de arriba, cerrado a nivel de esta funcion -- arreglo
    2026-08-03, tercera vuelta, DEUDA.md punto 27.** Los dos arreglos
    anteriores (candado + `_staged_as_new_before_us()`) no bastaban:
    reproducido con DOS escritores reales, cada uno escribiendo su
    PROPIO contenido en el MISMO fichero por su cuenta (sin ningun `git
    add` externo) y llamando cada uno a `write_work()`, **11 de 20
    intentos (55%)** salian con `ok=True` y el mensaje de un escritor
    sobre el contenido del otro -- el fichero YA TRACKEADO, pisado dos
    veces, que el punto 6 dejaba sin cubrir.

    Un primer intento (huella capturada AL ENTRAR, comparada otra vez
    justo antes de `stage_and_commit()`, ambas leyendo el DISCO) solo
    bajo el mismo experimento a 8 de 20 (40%) -- medido en vivo, no
    asumido [las dos veces anteriores que este punto se dio por cerrado,
    no lo estaba]. Diagnostico: en esas 8 rondas `result.ok` era `True`
    porque las dos lecturas SI coincidian entre si -- la pisada ya habia
    ocurrido ANTES de la primera linea de esta funcion, asi que la propia
    huella de entrada partia ya del contenido equivocado. Ninguna
    comparacion hecha leyendo el disco DESDE DENTRO puede detectar eso.

    **La unica forma real de cerrarlo:** que la huella de referencia no
    la lea esta funcion del disco, sino que la calcule el propio llamador
    a partir de los BYTES que el mismo acaba de escribir, en memoria, sin
    volver a leer el fichero -- y se la pase aqui [el mismo limite que el
    punto 6 ya dejaba escrito]. `known_content` es ese parametro,
    opcional y en la MISMA posicion/orden que `paths`: una lista de
    `bytes` (o `None` por ruta sin contenido conocido de antemano). Con
    el, la huella de entrada nunca toca el disco -- es `sha256()` de los
    bytes que el llamador ya tenia en la mano.

    Verificado en vivo (dos procesos de SO reales, no hilos), pasando
    `known_content` con bytes generados en memoria y nunca releidos:
    **0 de 60 con contenido y mensaje cruzados**, en dos tandas por
    separado (20 y 40) contra este mismo codigo. Script temporal, fuera
    de este repositorio (regla de esta obra); reproducir exige dos
    procesos escribiendo cada uno su contenido al mismo fichero y
    llamando a `write_work()` con `known_content=[su_bytes_en_memoria]`.

    **Cerrado el 2026-08-04, no por este arreglo -- decision del
    propietario, DEUDA.md B22.** El "0 de 60" de arriba se midio
    llamando a la funcion por dentro, con `known_content` ya inventado
    en memoria: prueba el mecanismo, no el sistema completo. Por donde
    entra el usuario de verdad (dos `gitmem work` normales) salio **16
    de 30**: `work.py`/`wip.py` arrancan un proceso Python (50-150ms de
    imports) antes de leer el fichero, y esa ventana, mas ancha que la
    de esta funcion, es la que se cuela. A la pregunta de si dos
    escrituras a la vez tienen que funcionar o negarse, respondio **"no
    va a pasar nunca"**: el caso se descarta, no se repara -misma figura
    que el punto 25-. **El candado y `known_content` se quedan tal cual
    estan** -cierran lo que ya cerraban-, no porque tapen esta ventana,
    que ya no se persigue.

    **8. La ventana DENTRO de esta funcion, la que el punto 7 daba por
    cerrada y no lo estaba -- arreglo 2026-08-08, CI la cazo con el test
    de dos procesos reales (rojo intermitente: la carrera anterior con
    el mismo codigo paso).** Los puntos 6/7 comparan huellas leidas del
    DISCO antes de comitear, pero `stage_and_commit()` hace `git add
    --all` y LUEGO `gitcmd.commit()`, que usa la forma con pathspec y
    RELEE EL ARBOL DE TRABAJO otra vez en el instante del commit (su
    propio docstring, verificado contra git real). Entre la ultima
    comprobacion de huella (arriba) y esa relectura final hay una
    rendija -- pequeña, pero real: si el otro escritor pisa el fichero
    justo ahi, el commit se lleva su contenido bajo nuestro mensaje y
    esta funcion, sin verificar nada mas, devolvia `ok=True` mintiendo.

    Ampliar el candado no sirve -- el otro proceso escribe el fichero
    sin pedirlo, fuera de este candado, por diseño (es la escritura de
    trabajo del llamador, no una operacion de este modulo). La unica
    forma de cerrarlo es comprobar DESPUES de comitear, contra lo que
    `HEAD` de verdad quedo llevando -- no contra lo que la funcion CREE
    que comiteo: para cada `path` con `known_content` conocido, el hash
    de blob que tendrian esos bytes (`_git_blob_hash_of_bytes`, via
    `git hash-object` sobre un fichero temporal, nunca sobre el arbol de
    trabajo) tiene que coincidir exactamente con el blob que `HEAD`
    tiene para esa ruta (`_committed_blob_hash`, via `git rev-parse
    HEAD:<ruta>`). Si no coincide -- o si cualquiera de las dos consultas
    falla, que se trata igual que un desajuste, nunca como una
    coincidencia -- el commit que se acaba de crear es sospechoso: se
    intenta deshacer con `git reset --mixed HEAD~1` (mueve `HEAD` e
    indice al padre, nunca toca el arbol de trabajo -- el otro escritor
    puede seguir escribiendolo) **bajo las dos condiciones que el punto 9
    de mas abajo anade** -- deshacer a ciegas aqui resulto ser, el mismo
    dia, un segundo fallo.

    Recuperar el contenido bueno sigue siendo imposible (mismo limite
    que el punto 6 ya dejaba escrito) -- esto no lo intenta; solo
    garantiza que `ok=True` nunca vuelva a mentir. Sin `known_content`
    para una ruta (`None`), no hay bytes contra los que comparar -- esa
    ruta no se verifica, mismo hueco ya aceptado que el punto 7 documenta
    para ese caso.

    **9. El propio "deshacer" del punto 8 -- TRES rondas de agujeros en
    el mismo dia, las dos primeras cazadas por Cerberus con tests
    deterministas, la tercera por Cerberus reproduciendola EN VIVO contra
    codigo ya en produccion. Van CUATRO veces que este punto se da por
    cerrado y no lo esta. La leccion de las rondas 1 y 2 no bastaba
    -- esta es la de la ronda 3, y es la que de verdad cierra el patron:
    NINGUN NUMERO DE COMPROBACIONES ANTES DE UN ACTO QUE APUNTA A UNA
    REFERENCIA VIVA lo cierra. No es "comprobar mejor" -- es no separar
    "mirar" de "actuar": tienen que ser el MISMO acto, uno que solo
    puede fallar, nunca mentir.**

    - **Ronda 1:** el `reset` no comprobaba su propio resultado. Si
      fallaba (sin `HEAD~1`, o el indice ocupado), el commit corrupto
      seguia siendo `HEAD` y la funcion decia igualmente "se deshizo".
    - **Ronda 2:** `HEAD~1` se resolvia EN EL MOMENTO del reset, no
      fijado al commit propio -- la razon que lo justificaba entonces
      ("el candado global sigue tomado") solo vale para quien toma ese
      candado, y `bin/release.py` no lo toma. Arreglo de la ronda 2:
      fijar `own_commit_sha` con un `rev-parse HEAD` justo despues del
      commit, y comprobar que `HEAD` seguia siendo ese valor ANTES de
      resetear.
    - **Ronda 3, la que de verdad importa:** ese arreglo de la ronda 2
      segui­a siendo "comprobar, LUEGO actuar" -- dos actos separados, con
      un hueco real entre medias, por pequeño que fuera. Cerberus
      reproduzco EN VIVO, contra el codigo de la ronda 2, TRES agujeros
      en ese hueco:
        - El `reset --mixed HEAD~1` en si mismo resuelve `HEAD~1` cuando
          el subproceso ARRANCA -- un commit ajeno que aterriza DESPUES
          de que la comprobacion ya diera bien, pero ANTES de que el
          propio subproceso de `git reset` se ejecute, se lo come
          igual: la comprobacion anterior no protege el acto que viene
          despues.
        - `own_commit_sha` en si mismo se capturaba con un `git
          rev-parse HEAD` en un SUBPROCESO SEPARADO del propio `git
          commit`. Un commit ajeno que aterriza en ESE hueco (antes de
          esa lectura, no despues) envenena la referencia desde el
          origen -- el recheck posterior compara el veneno consigo
          mismo, coincide por construccion, y no detecta nada.
        - La rama de "el historial se movio" no nombraba el commit
          corrupto (a diferencia de su rama hermana, "el reset fallo",
          que si lo hacia) -- justo donde mas hace falta, porque ahi el
          commit corrupto sigue siendo `HEAD`, enterrandose bajo mas
          historial con cada commit legitimo que llega despues.

    **El arreglo de la ronda 3 -- un solo acto atomico, no una
    comprobacion seguida de un acto [primitiva propuesta por Cerberus]:**

    1. `own_commit_sha` ya NO se lee con un `rev-parse HEAD` posterior --
       se PARSEA de la primera linea de la salida del propio `git
       commit` (`_own_commit_sha_from_commit_output()`, arriba): la
       MISMA llamada que crea el commit, nunca una posterior, asi que no
       hay hueco en el que envenenarla. El sha corto de esa linea se
       expande a los 40 caracteres con `git rev-parse
       <corto>^{commit}` -- busqueda por CONTENIDO, no por referencia:
       un commit ajeno no cambia a que apunta un hash que ya existe, asi
       que esta segunda llamada, aunque es un subproceso aparte, no
       tiene la misma ventana.
    2. El padre se resuelve con `git rev-parse <own_commit_sha>~1` --
       tambien por CONTENIDO (el padre de ESTE commit concreto), nunca
       "`HEAD~1`" (una referencia que se mueve).
    3. Deshacer es UNA sola llamada: `git update-ref -m <razon> HEAD
       <padre> <own_commit_sha>` -- mueve `HEAD` a `<padre>` SOLO SI su
       valor actual es, exactamente, `own_commit_sha`; la comprobacion y
       el movimiento son la MISMA operacion atomica, bajo el candado de
       referencias del propio git, sin ningun subproceso independiente
       entre "mirar" y "actuar". Si `HEAD` ya no es `own_commit_sha`
       (un commit ajeno aterrizo en CUALQUIER momento anterior, sin
       importar cuando), este comando FALLA solo, sin tocar nada -- ni
       siquiera hace falta saber cuando aterrizo el commit ajeno para
       estar a salvo.
    4. Solo si el paso 3 tuvo exito se sincroniza el indice con `git
       reset --mixed HEAD` (sin `~1`: en este punto `HEAD` YA es el
       padre, de forma verificada, asi que este ultimo paso no mueve
       ninguna referencia -- es higiene, mejor esfuerzo, nunca el acto
       que decide si algo se pierde).
    5. Las tres ramas de fallo (no se identifico el commit propio; el
       commit es el primero del repositorio, sin padre; el
       `update-ref` fallo) nombran `own_commit_sha` SIEMPRE que el
       commit corrupto sigue vivo -- nunca solo en una de las tres.

    **Ademas, `_git_blob_hash_of_bytes()` -- otro hallazgo en vivo de
    Cerberus, el mismo dia, en produccion real:** la version de la ronda
    3 le paso `--no-filters` a `git hash-object`, razonando (rondas
    atras) que asi se evitaba un filtro de `.gitattributes` resuelto por
    la ruta INCORRECTA (la del temporal). El razonamiento sobre el
    riesgo era correcto; el arreglo apuntaba al lado equivocado:
    `--no-filters` hashea los BYTES CRUDOS, pero `stage_and_commit()`
    comitea con `git add` normal, que SI aplica los filtros de la ruta
    real -- en Windows, por defecto, `core.autocrlf` normaliza `\r\n` a
    `\n` al guardar. Resultado en produccion: en CUALQUIER repositorio
    con autocrlf activo, esta funcion comparaba el hash de los bytes
    CRLF crudos contra el blob LF que git de verdad guardo -- rojo
    SIEMPRE, para cualquier escritura, sin que nadie pisara nada.
    `gitmem wip` dejo de guardar nada en Windows: cada commit valido
    salia "corrupto" y se deshacia. Confirmado antes de tocar nada,
    reproducido con `core.autocrlf=true`: `hash-object --no-filters`
    sobre bytes CRLF NO coincide con el blob real; `hash-object --path
    <ruta>` (sin `--no-filters`) SI coincide, byte a byte, con lo que
    git de verdad almaceno. El arreglo: `--path <ruta relativa real>`
    -- resuelve el MISMO problema que `--no-filters` queria resolver
    (que filtro aplica) pero contra la ruta CORRECTA, en vez de apagar
    los filtros por completo. Ver el docstring de la funcion, arriba,
    para el detalle completo y la reproduccion.

    **Para la quinta vuelta, si la hay:** la ronda 3 demostro que
    "comprobar antes de actuar" nunca cierra una carrera contra una
    referencia que otro proceso puede mover -- hace falta que la
    comprobacion y el acto sean la MISMA operacion atomica (aqui,
    `update-ref` con `<oldvalue>`). La ronda 4 (el filtro) demostro algo
    distinto: un arreglo de concurrencia puede introducir su PROPIO
    falso positivo si asume una plataforma en vez de comprobarla --
    "arreglar sin reproducir en la plataforma real" cuesta tan caro como
    "comprobar en vez de actuar atomicamente". Cualquier verificacion de
    contenido que se añada aqui en el futuro necesita las dos disciplinas
    a la vez: el acto decisivo tiene que ser atomico contra la
    referencia que puede moverse, y el calculo de hash tiene que
    reproducirse contra lo que git REALMENTE almacena en la plataforma
    real (o, como minimo, contra un `core.autocrlf`/`.gitattributes`
    simulado), nunca contra una suposicion de que "aqui no hace falta".
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
