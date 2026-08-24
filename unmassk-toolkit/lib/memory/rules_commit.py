"""Mecanica de fichero+git de `rules.py` -- candado, ruta, lectura del
arbol de trabajo, y la transaccion completa de comitear una regla (o
deshacerla si el commit falla) -- partido de `rules.py` por tamano.

El fichero vivo es ``.claude/project-memory/rules.md`` del proyecto,
junto a los ocho indices y a ``zones.json``/``config.json``. Como la
ruta es relativa al proyecto, las reglas de un proyecto nunca se
enseñan en otro. `/remember` (general, en `commands/`) le dice a Claude
que lea este fichero y lo entregue entero -- no es un programa.

Nombres sin guion bajo (`lock_resource`, `repo_root`,
`read_current_rules_content`, `commit_or_restore`, `rules_file_path`,
`read_all`) cruzan a `rules.py`. Lo que solo se llama a si mismo dentro
de este fichero se queda privado.

`read_all()` vive AQUI, no en `rules.py` -- es la unica forma de que
`rules_similarity.py::similar_existing()` la llame sin crear un ciclo:
`rules.py` importa DE `rules_commit.py` y DE `rules_similarity.py`; si
`read_all()` viviera en la fachada, `rules_similarity.py` tendria que
importar desde ella. `rules.py` sigue reexportando `read_all` bajo el
mismo nombre.

Imports planos entre hermanos. `lib/memory/` no importa nada fuera de la
biblioteca estandar de Python.
"""

from pathlib import Path

import gitcmd
import notes_commit


# Cabecera literal del fichero de reglas -- mismo patron que
# ``indexes._header_for`` aplica a sus vecinos (DECISIONS.md, etc.):
# "Lo escribe el script. No editar. Si diverge, manda git." Coherente con
# que el fichero vive junto a los ocho indices y a zones.json/config.json
# [PIEZAS.md Sec.9.7, ARQUITECTURA.md Sec.207].
_RULES_HEADER = "# RULES — reglas de trabajo (remember). Lo escribe el script. No editar. Si diverge, manda git.\n"


def rules_file_path(root: Path) -> Path:
    """Ruta del fichero de reglas -- un unico punto de cambio."""
    return root / ".claude" / "project-memory" / "rules.md"


def lock_resource(root: Path) -> Path:
    """Candado GLOBAL propio de este modulo -- envuelve la operacion
    completa de `add()` (leer, anadir la linea, escribir, comitear) para
    que dos `add()` concurrentes no pierdan ninguna regla.

    Esta ruta (`.git/memory-rules`) SOLO serializa las llamadas a
    `add()` entre si -- es distinta de `notes_commit.lock_resource()`
    (`.git/memory-notes`). `add()` y un `gitmem work`/`wip`/`note`
    concurrente SI compiten por el mismo `.git/index.lock` real dentro de
    `stage_and_commit()`; ese choque falla en voz alta con el error real
    de git, nunca silencioso -- este candado no lo evita, solo garantiza
    que dos `add()` entre si nunca se pisan. Vive dentro de `.git/` para
    no aparecer en `git status`.
    """
    return root / ".git" / "memory-rules"


def repo_root() -> Path:
    return gitcmd.repo_root(Path.cwd())


def read_current_rules_content(path: Path) -> tuple[bool, str]:
    """El fichero de reglas TAL COMO ESTA en este instante -- `(existe,
    contenido)`. `existe=False` devuelve la cabecera (`_RULES_HEADER`)
    como contenido "de partida".

    `add()` la llama DOS VECES: una escritura ajena a `rules.md` (una
    edicion a mano, fuera de `lock_resource()`) entre la primera lectura
    y el `atomic_write()` final se perderia en silencio si `add()` solo
    leyera una vez.
    """
    exists = path.exists()
    content = path.read_text(encoding="utf-8") if exists else _RULES_HEADER + "\n"
    return exists, content


def _restore_or_delete_best_effort(
    path: Path, previous_content: str, file_existed_before: bool
) -> None:
    """Deshace la escritura de `add()` en el arbol de trabajo tras un
    commit que fallo -- mejor esfuerzo, nunca propaga su propia excepcion.
    Dos casos:

    - `file_existed_before` -- `rules.md` ya existia: se restaura a
      `previous_content` (`notes_commit.restore_snapshot_best_effort()`).
    - No existia -- este `add()` fue quien lo creo (el primer remember
      del proyecto): restaurar a `previous_content` dejaria un fichero
      huerfano con solo la cabecera. Se borra entero en su lugar.
    """
    if file_existed_before:
        notes_commit.restore_snapshot_best_effort(path, previous_content)
        return
    try:
        path.unlink()
    except OSError:
        pass  # ya no estaba, o alguien mas lo borro -- mejor esfuerzo


def commit_or_restore(
    path: Path, previous_content: str, message: str, root: Path, file_existed_before: bool
) -> str | None:
    """Comitea `path` (ya escrito con la linea nueva) con `message` via
    `notes_commit.stage_and_commit()` -- mismo mecanismo compartido que
    `notes.write()`/`write_work()`, nunca una copia local. Si el commit
    falla o revienta a mitad, deshace la escritura en el arbol de trabajo
    con `_restore_or_delete_best_effort()` antes de devolver el problema.

    Devuelve `None` si el commit salio bien, o un `stderr` SIEMPRE no
    vacio si fallo -- `stage_and_commit()` ya lo garantiza
    (`_ensure_nonempty_stderr()`), asi que esto no necesita su propio
    respaldo.
    """
    try:
        git_result = notes_commit.stage_and_commit(message, [path], root)
    except BaseException:
        _restore_or_delete_best_effort(path, previous_content, file_existed_before)
        raise
    if git_result.returncode != 0:
        _restore_or_delete_best_effort(path, previous_content, file_existed_before)
        return git_result.stderr
    return None


def read_all() -> str:
    """El fichero de reglas ENTERO, sin filtrar -- lo que ``/remember``
    entrega a Claude [Sec.9.7]. Cadena vacia si todavia no hay ninguna
    regla, nunca una excepcion.

    Bajo el mismo candado que ``add()``: sin esto, un lector podria caer
    justo en medio de la transaccion de un ``add()`` concurrente (fichero
    ya escrito, commit todavia en marcha) -- una inconsistencia real,
    aunque de una fraccion de segundo, entre lo que el fichero ya dice y
    lo que git todavia no sabe.
    """
    root = repo_root()
    with gitcmd.file_lock(lock_resource(root)):
        path = rules_file_path(root)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")
