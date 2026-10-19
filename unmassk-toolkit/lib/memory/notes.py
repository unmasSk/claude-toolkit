"""Escribir una nota y su linea de indice, en el mismo commit, o ninguna
de las dos: una sin la otra es corrupcion silenciosa.

El orden de `write` es el contrato:

    candado -> identificador -> validar -> escribir el indice
            -> commit de nota + indice JUNTOS
            -> si git falla (o salta una excepcion): restaurar el indice
               y propagar el error real de git

`replace()`/`close()` siguen el mismo orden retirando una linea existente:
el id nuevo se calcula antes de retirar la vieja, y se restaura el texto
completo capturado antes de escribir. `next_id()` recibe siempre el indice
vivo mas los ids archivados (`index_with_archived`), o un id se reusa.

La mecanica de git vive en `notes_commit.py`; la de retirar y archivar, en
`notes_promote.swap_and_archive()`. Las dos se reexponen aqui.
"""

import dataclasses
import shlex
from collections.abc import Callable
from datetime import datetime, timezone

import format
import gitcmd
import ids
import indexes
import notes_duplicate
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

_TYPE_TO_INDEX_FILE = TYPE_INDEX_FILES

_ARCHIVE_FILE = "ARCHIVED.md"
assert _ARCHIVE_FILE in INDEX_FILES, (
    "notes.py: _ARCHIVE_FILE ha quedado desincronizado de vocabulary.INDEX_FILES"
)


def write(note: Note, ctx: Context) -> WriteResult:
    """Escribe `note` y su linea de indice en un solo commit, o nada."""
    root = repo_root()
    pm = pm_root(root)
    with gitcmd.file_lock(lock_resource(root)):
        index_name = _TYPE_TO_INDEX_FILE.get(note.type)

        if index_name is not None:
            indexes.seed(pm)
            current_index = indexes.read(index_name, pm)
            new_id = ids.next_id(note.type, index_with_archived(current_index, pm))
            candidate = dataclasses.replace(note, id=new_id)
        else:
            # Tipo fuera del vocabulario: `validate_note` lo rechaza abajo.
            candidate = note

        rejections = validate_note(candidate, ctx)
        if rejections:
            return WriteResult(ok=False, note_id=None, rejections=rejections, git_error=None)

        index_line = IndexLine(
            id=candidate.id,
            zone1=candidate.zone1,
            zone2=candidate.zone2,
            headline=candidate.headline,
        )
        indexes.insert(index_line, index_name, pm)

        index_path = pm / index_name
        try:
            message = format.build_message(candidate)
            git_result = stage_and_commit(message, [index_path], root)
        except BaseException:
            restore_index_best_effort(candidate.id, index_name, pm)
            raise

        if git_result.returncode != 0:
            restore_index_best_effort(candidate.id, index_name, pm)
            # `stage_and_commit()` ya limpia el staging area.
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        return WriteResult(ok=True, note_id=candidate.id, rejections=(), git_error=None)


def refused_alternatives(
    alternatives: tuple[Note, ...], ctx: Context
) -> tuple[tuple[Note, tuple[Rejection, ...]], ...]:
    """Cada alternativa que rebota, con sus rechazos. Cada una se compara
    tambien con las anteriores ya aceptadas: la misma alternativa dos veces
    rebota en la puerta de duplicados igual que si ya estuviera escrita."""
    refused = []
    accepted: tuple[Note, ...] = ()
    for alternative in alternatives:
        seen = dataclasses.replace(ctx, existing_in_zone=ctx.existing_in_zone + accepted)
        found = validate_note(alternative, seen)
        if found:
            refused.append((alternative, found))
        else:
            label = f"(--discard {len(accepted) + 1})"
            accepted += (dataclasses.replace(alternative, id=label),)
    return tuple(refused)


def discard_alternatives(
    decision: Note,
    alternatives: tuple[Note, ...],
    ctx: Context,
    write_decision: Callable[[Note, Context], WriteResult] = write,
) -> tuple[WriteResult, ...]:
    """Escribe `decision` y cada una de `alternatives`, cada una en su propio
    commit, con `origin` apuntando al id real de la decision.

    Todas las alternativas se validan antes de escribir nada: si alguna rebota,
    vuelve un solo resultado con todos sus rechazos. `write_decision(decision,
    ctx)` escribe la decision (`write`, o `replace`/`promote` envueltas).
    """
    rejections = tuple(r for _alt, found in refused_alternatives(alternatives, ctx) for r in found)
    if rejections:
        return (WriteResult(ok=False, note_id=None, rejections=rejections, git_error=None),)

    decision_result = write_decision(decision, ctx)
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
    """Sustituye `old_id` por `new` en un solo commit; la vieja se archiva
    como "replaced by <new_id>". Delega en `swap_and_archive()`.
    """
    old_type = old_id.split("-", 1)[0]
    old_index_name = _TYPE_TO_INDEX_FILE.get(old_type)
    if old_index_name is None:
        raise ValueError(f"{old_id!r}: tipo desconocido, ningun indice le corresponde")
    return swap_and_archive(
        old_id, old_index_name, new, ctx, destination="replaced", link_replaces=True
    )


def _reject_close_reason_multiline(note_id: str, reason: str) -> Rejection | None:
    """`None` si `reason` cabe en una linea; un `Rejection` si trae un salto
    de linea, que partiria su entrada de ARCHIVED.md.
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


def close(
    note_id: str,
    reason: str,
    ctx: Context,
    commit: str | None = None,
    relaunch_for: Callable[[str], str] | None = None,
) -> WriteResult:
    """Cierra `note_id` con `reason` en un solo commit: sale de su indice y
    entra en ARCHIVED.md como "closed: <reason>". `ctx` no se usa.

    Se rechaza antes de tocar nada si `reason` trae un salto de linea, o si
    varias lineas vivas llevan `note_id` y `commit` no elige una (D-145).
    `relaunch_for(sha)` da el comando de ese rechazo.
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
        if relaunch_for is None:
            relaunch_for = notes_duplicate.remove_relaunch(note_id, shlex.quote(reason))
        line, duplicate = notes_duplicate.pick(note_id, lines, commit, relaunch_for)
        if duplicate is not None:
            return WriteResult(ok=False, note_id=None, rejections=(duplicate,), git_error=None)
        indexes.remove(note_id, index_name, pm, only=line)
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

        try:  # asunto: literal de TEXTOS.md Sec.4
            git_result = stage_and_commit(f"closed: {reason}", touched, root)
        except BaseException:
            _restore_all()
            raise

        if git_result.returncode != 0:
            _restore_all()
            # `stage_and_commit()` ya limpia el staging area.
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        return WriteResult(ok=True, note_id=note_id, rejections=(), git_error=None)
