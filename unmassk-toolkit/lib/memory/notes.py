"""Escribir una nota y su linea de indice, en el mismo commit, o ninguna
de las dos.

ES LA PIEZA DONDE EL SISTEMA SE PUEDE CORROMPER A SI MISMO. Si la nota se
commitea y el indice no, hay una nota que ninguna busqueda encuentra
jamas. Si el indice se actualiza y el commit falla, hay una linea que
apunta a una nota que no existe. Las dos son corrupcion silenciosa.

El orden de `write` es el contrato:

    candado -> identificador -> validar -> escribir el indice
            -> commit de nota + indice JUNTOS
            -> si git falla: restaurar el indice y propagar el error
               real de git

Validar ANTES de tocar el indice, restaurar DESPUES de que git falle.
Cualquier otro orden deja una ventana donde el indice y git dicen cosas
distintas.

La mecanica de git de la que este fichero tira -- el candado
(`lock_resource`), la raiz (`repo_root`/`pm_root`), el `git add`+`git
commit` (`stage_and_commit`) y las dos restauraciones de mejor esfuerzo --
vive en `notes_commit.py`, partido de aqui por tamano. `write_work`
tambien vive alli: es la unica de las cinco operaciones que no toca
ningun indice y no necesita candado ni restauracion. Se reexpone bajo el
mismo nombre, asi que `notes.pm_root`/`notes.write_work` siguen
alcanzables igual.

La mecanica de "retirar una linea existente y archivarla con un destino"
que `replace()` usa entera vive en `notes_promote.py`
(`swap_and_archive()`), porque `promote()` (ascenso de una Q) la necesita
igual y una segunda copia de esa transaccion es la unica amenaza que
este proyecto declara.

Decisiones que cierran huecos que el contrato no fija letra por letra:

1. `discard_alternatives` enlaza cada alternativa a la decision via
   `origin` -- sin ese enlace, las alternativas descartadas quedarian
   huerfanas para siempre en el racimo de su decision (`clusters.py`
   agrupa EXCLUSIVAMENTE por punteros Origin/Replaces). Como el id de la
   decision solo se conoce DESPUES de escribirla, se extiende
   `ctx.known_ids` con ese id antes de validar cada alternativa.

2. `replace()`/`close()` comparten el orden de `write()`, pero retiran
   una linea EXISTENTE en vez de anadir una nueva.

3. La restauracion del indice esta protegida por `try`/`except
   BaseException`, no solo por `git_result.returncode != 0`: una
   excepcion real a mitad (un Ctrl-C durante un commit lento) sin este
   `try` se saltaba la restauracion entera y dejaba el indice huerfano.
   Si la propia restauracion revienta, su excepcion se traga (mejor
   esfuerzo) en vez de sustituir el diagnostico real.

4. Retirar una linea existente, no anadir una nueva, tiene tres
   consecuencias: (a) el id nuevo de `replace()` se calcula con la
   lectura tomada ANTES de `indexes.remove()`, para que el numero que
   `replace()` esta a punto de liberar no se reutilice dentro del MISMO
   commit; (b) la restauracion no puede ser `indexes.insert()` (una
   linea existente puede estar en cualquier posicion, y anadirla al
   final la moveria) -- se restaura el contenido completo capturado
   antes de escribir; (c) mismo mecanismo para `ARCHIVED.md`.

5. `next_id()` recibe SIEMPRE el indice vivo mas los ids ya archivados --
   sin esto, un id se liberaba en cuanto su nota se archivaba y podia
   reasignarse a una nota totalmente distinta (`I-001` cerrada, luego
   reasignada a una segunda incidencia real: dos notas distintas, un
   mismo identificador permanente en las dos, corrupcion invisible para
   `search.py`/`reindex.py`). `ids.next_id()` en si no cambia; el
   arreglo va en quien le pasa el indice (`index_with_archived()`,
   `notes_promote.py`), en `write()` y en `swap_and_archive()`. `close()`
   no lo necesita: no calcula ningun id nuevo.

No importa nada del toolkit fuera de la biblioteca estandar de Python.
Imports planos entre hermanos de `lib/memory/`.
"""

import dataclasses
from datetime import datetime, timezone

import format
import gitcmd
import ids
import indexes
import rejection as rejection_
from model import ArchiveLine, IndexLine, Note, Rejection, WriteResult
from notes_commit import (
    lock_resource,
    pm_root,
    repo_root,
    restore_index_best_effort,
    restore_snapshot_best_effort,
    stage_and_commit,
    write_work,
)
# Reexpuestos bajo el mismo nombre: `notes.promote` sigue alcanzable
# igual para `bin/memory/note.py`.
from notes_promote import index_with_archived, promote, swap_and_archive  # noqa: F401
from validator import Context, validate_note
from vocabulary import INDEX_FILES, TYPE_INDEX_FILES

# Que fichero de indice le toca a cada tipo -- dato cerrado del sistema,
# vive en `vocabulary.TYPE_INDEX_FILES`. Reexpuesto bajo el nombre privado
# de siempre para no tocar el resto de este fichero.
_TYPE_TO_INDEX_FILE = TYPE_INDEX_FILES

# Destino comun de replace()/close() -- literal de TEXTOS.md Sec.4. Mismo
# fichero que indexes.py usa por dentro.
_ARCHIVE_FILE = "ARCHIVED.md"
assert _ARCHIVE_FILE in INDEX_FILES, (
    "notes.py: _ARCHIVE_FILE ha quedado desincronizado de vocabulary.INDEX_FILES"
)


def write(note: Note, ctx: Context) -> WriteResult:
    """Escribe `note` y su linea de indice en un solo commit, o ninguna
    de las dos cosas. Ver el orden del contrato en el docstring del
    modulo -- no es negociable.
    """
    root = repo_root()
    pm = pm_root(root)
    with gitcmd.file_lock(lock_resource(root)):
        index_name = _TYPE_TO_INDEX_FILE.get(note.type)

        if index_name is not None:
            # `seed()` es idempotente: crea los ocho ficheros (y `pm` si
            # falta) solo si faltan, nunca toca uno que ya tiene notas.
            indexes.seed(pm)
            current_index = indexes.read(index_name, pm)
            new_id = ids.next_id(note.type, index_with_archived(current_index, pm))
            candidate = dataclasses.replace(note, id=new_id)
        else:
            # Tipo fuera del vocabulario cerrado: `validate_note` lo
            # rechaza abajo; aqui solo se evita un KeyError antes de eso.
            candidate = note

        rejections = validate_note(candidate, ctx)
        if rejections:
            return WriteResult(ok=False, note_id=None, rejections=rejections, git_error=None)

        # A partir de aqui `index_name` nunca es None: `validate_note` ya
        # habria rechazado cualquier tipo fuera de `_TYPE_TO_INDEX_FILE`.
        index_line = IndexLine(
            id=candidate.id,
            zone1=candidate.zone1,
            zone2=candidate.zone2,
            headline=candidate.headline,
        )
        indexes.insert(index_line, index_name, pm)

        index_path = pm / index_name
        # Puede fallar de dos formas: un GitResult con returncode != 0,
        # o una excepcion real a mitad -- la restauracion tiene que
        # darse en los dos casos, o la linea de indice queda huerfana.
        try:
            message = format.build_message(candidate)
            git_result = stage_and_commit(message, [index_path], root)
        except BaseException:
            restore_index_best_effort(candidate.id, index_name, pm)
            raise

        if git_result.returncode != 0:
            restore_index_best_effort(candidate.id, index_name, pm)
            # La limpieza del staging area ya la hace `stage_and_commit()`
            # por su cuenta -- ver su docstring, 2026-08-23.
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        return WriteResult(ok=True, note_id=candidate.id, rejections=(), git_error=None)


def discard_alternatives(
    decision: Note, alternatives: tuple[Note, ...], ctx: Context
) -> tuple[WriteResult, ...]:
    """Escribe `decision` y cada una de `alternatives`, cada una en su
    propio commit -- "un acto, un commit" aplica a nota+indice, no al
    acto completo. Una decision con dos alternativas produce tres
    resultados, no dos.

    Cada alternativa se escribe con `origin` apuntando al id real de
    `decision` -- el enlace que `clusters.py` necesita para agruparlas.
    """
    decision_result = write(decision, ctx)
    if not decision_result.ok:
        return (decision_result,)

    extended_ctx = dataclasses.replace(
        ctx, known_ids=ctx.known_ids | {decision_result.note_id}
    )

    results = [decision_result]
    for alternative in alternatives:
        linked = dataclasses.replace(
            alternative, origin=(decision_result.note_id,) + alternative.origin
        )
        results.append(write(linked, extended_ctx))
    return tuple(results)


def replace(new: Note, old_id: str, ctx: Context) -> WriteResult:
    """Sustituye `old_id` por `new` en un solo commit: la nota nueva, su
    linea de indice, la vieja fuera de su indice, y su linea en
    ARCHIVED.md con destino "replaced by <new_id>". La mecanica (id
    nuevo antes de retirar la vieja, restauracion por snapshot) vive en
    `notes_promote.swap_and_archive()` -- `replace()` solo resuelve el
    fichero de `old_id` y delega, con `destination="replaced"` y
    `link_replaces=True` (la nota nueva lleva `Note.replaces=old_id`).
    """
    old_type = old_id.split("-", 1)[0]
    old_index_name = _TYPE_TO_INDEX_FILE.get(old_type)
    if old_index_name is None:
        raise ValueError(f"{old_id!r}: tipo desconocido, ningun indice le corresponde")
    return swap_and_archive(
        old_id, old_index_name, new, ctx, destination="replaced", link_replaces=True
    )


# `reason` con un salto de linea propio partia la entrada de ARCHIVED.md
# en dos (o creaba una entrada fantasma) mientras el comando seguia
# saliendo "✅ archivada" -- corrupcion silenciosa mas un visto bueno
# falso. ARCHIVED.md es, por contrato, exactamente una linea por nota,
# sin plegado documentado -- se rechaza en su lugar.
def _reject_close_reason_multiline(note_id: str, reason: str) -> Rejection | None:
    """`None` si `reason` cabe en una sola linea fisica; un `Rejection` si
    trae un salto de linea propio. `close()` no pasa por `validate_note()`,
    asi que este es el unico punto donde `reason` se puede rechazar.
    """
    if "\n" not in reason:
        return None
    what = "el motivo de cierre trae un salto de linea propio"
    options = (
        f'  "{reason}"',
        "",
        "El motivo entra en ARCHIVED.md como una sola linea fisica -- un salto",
        "de linea ahi parte la entrada en dos, o la funde con la linea",
        "siguiente. No se puede guardar tal cual.",
        "",
        "Vuelve a intentarlo con el motivo en una sola linea.",
    )
    command = (f'gitmem remove {note_id} "<motivo sin saltos de linea>"',)
    return rejection_.build(
        kind="close_reason_multiline", what=what, options=options, command=command
    )


def close(note_id: str, reason: str, ctx: Context) -> WriteResult:
    """Cierra `note_id` con `reason` en un solo commit: la linea sale de su
    indice y entra en ARCHIVED.md con destino "closed: <reason>". `ctx`
    se recibe por simetria con `write()`/`replace()` pero no se usa:
    cerrar no crea ninguna nota nueva.

    Reutiliza `indexes.remove()` para localizar y retirar la linea -- si
    `note_id` no esta en su indice, lanza `ValueError` sola.

    `reason` se rechaza ANTES de tocar nada si trae un salto de linea
    propio (`_reject_close_reason_multiline`) -- la unica validacion que
    `close()` hace.
    """
    del ctx  # recibido por simetria de Superficie, sin uso
    rejection = _reject_close_reason_multiline(note_id, reason)
    if rejection is not None:
        return WriteResult(ok=False, note_id=None, rejections=(rejection,), git_error=None)
    root = repo_root()
    pm = pm_root(root)
    with gitcmd.file_lock(lock_resource(root)):
        indexes.seed(pm)
        note_type = note_id.split("-", 1)[0]
        index_name = _TYPE_TO_INDEX_FILE.get(note_type)
        if index_name is None:
            raise ValueError(f"{note_id!r}: tipo desconocido, ningun indice le corresponde")
        index_path = pm / index_name
        index_snapshot = index_path.read_text(encoding="utf-8")
        lines = indexes.read(index_name, pm)
        line = next((entry for entry in lines if entry.id == note_id), None)
        indexes.remove(note_id, index_name, pm)
        if line is None:  # no deberia ocurrir -- ver replace()
            raise RuntimeError(f"inconsistencia interna: {note_id!r} se retiro de {index_name}")

        archive_path = pm / _ARCHIVE_FILE
        archive_snapshot = archive_path.read_text(encoding="utf-8")
        indexes.archive(
            ArchiveLine(
                date=datetime.now(timezone.utc).date(), type=note_type, id=note_id,
                zone1=line.zone1, zone2=line.zone2, headline=line.headline,
                destination="closed", destination_detail=reason,
            ),
            pm,
        )

        touched = [index_path, archive_path]

        def _restore_all() -> None:
            restore_snapshot_best_effort(index_path, index_snapshot)
            restore_snapshot_best_effort(archive_path, archive_snapshot)

        try:  # asunto: literal de TEXTOS.md Sec.4, ver punto 4(c) del modulo
            git_result = stage_and_commit(f"closed: {reason}", touched, root)
        except BaseException:
            _restore_all()
            raise

        if git_result.returncode != 0:
            _restore_all()
            # La limpieza del staging area ya la hace `stage_and_commit()`
            # por su cuenta -- ver su docstring, 2026-08-23.
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        return WriteResult(ok=True, note_id=note_id, rejections=(), git_error=None)
