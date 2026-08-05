"""El ascenso de una pregunta (Q) abierta -- contrato en
docs/spec-sistema-memoria-v2.md Sec.4 y docs/memoria-v2/TEXTOS.md Sec.4.

**Nace el 2026-08-05, por el techo de 500 lineas de `notes.py`** [encargo
del propietario]: `notes.py` estaba en 495 lineas, y `promote()` mas sus
dos rechazos mas la mecanica que comparte con `replace()` no cabian dentro
sin pasarlo -- el mismo techo, y por el mismo motivo, que ya partio
`notes_commit.py` de `notes.py` [ver el docstring de ese fichero].

**Sigue EXACTAMENTE el mismo patron que esa partida**: `notes.py` importa
de aqui de forma PLANA y reexpone bajo el mismo nombre [PIEZAS.md
Sec.3.3bis], asi que `notes.promote` sigue alcanzable igual para quien lo
llame (`bin/memory/note.py`). Este fichero, a su vez, NO importa nada de
`notes.py` -- evita el ciclo; es `notes.py` quien depende de este, nunca
al reves.

QUE ES `promote()`: la Q asciende a memo (M) si la respuesta es un hecho,
o cae a descarte (X) si es que no [spec Sec.4]. Es la TERCERA forma en
que una nota sale de su indice a `ARCHIVED.md` -- junto a `replace()`/
`close()`, las dos en `notes.py` -- con destino `"promoted"`
[model.ArchiveLine.destination].

**`swap_and_archive()` es la mecanica que `replace()` (en `notes.py`) y
`promote()` (aqui) COMPARTEN**, en vez de cada una reimplementarla por su
lado: candado, id nuevo (fundiendo indice vivo + archivado via
`index_with_archived()`, punto 5 del docstring de `notes.py` -- el
hallazgo real de Moriarty sobre reuso de identificadores archivados),
retirada de la linea vieja, insercion de la nueva, archivado con un
destino, commit y restauracion por snapshot si algo falla. Dos
transacciones paralelas sobre los mismos indices es exactamente la unica
amenaza que este proyecto declara (memoria corrompida por el propio
sistema) -- por eso `notes.py` importa esta funcion en vez de copiar el
cuerpo de `replace()` una segunda vez. `link_replaces` es la unica
diferencia real de comportamiento entre las dos llamadoras: `replace()`
la pasa a `True` (la nota nueva sustituye, lleva `Note.replaces=old_id`);
`promote()` la pasa a `False` -- un ascenso no es una sustitucion, y
`validate_replacement` solo mira `note.replaces`: forzarlo aqui
dispararia una colision de similitud ajena al camino que este ascenso
quiere aislar (ver el docstring de `promote()`).

`pre_check`, si se da, corre DENTRO del mismo candado que `swap_and_archive`
ya abre, justo tras `indexes.seed(pm)` y ANTES de tocar ningun indice --
lo usa `promote()` para sus dos rechazos sobre `question_id` (no es una Q,
no existe) sin abrir una segunda ventana de candado. `replace()` no lo
necesita: su unico rechazo (`ValueError` de tipo desconocido) no depende
de nada que el candado resuelva, y se comprueba antes de llamar aqui.

Los dos rechazos de `question_id` (`_reject_bad_promotes_target`) **no
tienen molde en TEXTOS.md todavia** -- redactados con el mismo tono que el
resto via `rejection.build()`, nunca un texto impreso a mano; pendiente de
que el documento se ponga al dia [aviso del propietario, misma tarea].

No importa nada fuera de la biblioteca estandar de Python. Imports planos
entre hermanos de `lib/memory/` [PIEZAS.md Sec.3.3bis].
"""

import dataclasses
from datetime import datetime, timezone
from pathlib import Path

import format
import gitcmd
import ids
import indexes
import rejection as rejection_
from model import ArchiveLine, IndexLine, Note, Rejection, WriteResult
from notes_commit import lock_resource, pm_root, repo_root, restore_snapshot_best_effort, stage_and_commit
from validator import Context, validate_note
from vocabulary import INDEX_FILES, TYPE_INDEX_FILES

# Mismas dos constantes locales que ya tiene notes.py (y, por separado,
# health.py) -- alias de datos, no la transaccion; duplicar un literal de
# tres lineas no es el fallo que este fichero existe para evitar.
_TYPE_TO_INDEX_FILE = TYPE_INDEX_FILES
_ARCHIVE_FILE = "ARCHIVED.md"
assert _ARCHIVE_FILE in INDEX_FILES, (
    "notes_promote.py: _ARCHIVE_FILE ha quedado desincronizado de vocabulary.INDEX_FILES"
)


def index_with_archived(current_index: tuple[IndexLine, ...], pm: Path) -> tuple[IndexLine, ...]:
    """`current_index` mas un `IndexLine` hueco por cada id ya archivado en
    `pm` -- movida aqui desde `notes.py` el 2026-08-05 (mismo techo de
    500 lineas). `write()`/`close()` en `notes.py` y `swap_and_archive()`
    aqui abajo la usan igual, importada de forma plana. Ver el punto 5 del
    docstring de `notes.py` para el hallazgo real que la hizo necesaria.
    """
    archived = indexes.archived_ids(pm)
    return current_index + tuple(
        IndexLine(id=archived_id, zone1="", zone2="", headline="")
        for archived_id in archived
    )


def swap_and_archive(
    old_id: str,
    old_index_name: str,
    new: Note,
    ctx: Context,
    *,
    destination: str,
    link_replaces: bool,
    pre_check=None,
) -> WriteResult:
    """Retira `old_id` de `old_index_name`, escribe `new` con un id nuevo
    en su propio indice, y archiva la vieja con `destination` -- las tres
    cosas en un solo commit, o ninguna [PIEZAS.md Sec.8.1]. Ver el
    docstring del modulo para el porque de compartir esta mecanica entre
    `replace()` y `promote()` en vez de duplicarla.

    Precondicion del llamador (salvo lo que cubra `pre_check`): `old_id`
    ya tiene forma valida para `old_index_name` -- este helper no decide
    si el tipo es el correcto, solo mueve datos. Mismo orden que fija el
    docstring de `notes.py` (punto 4): id nuevo ANTES de retirar la vieja
    (para que `replace()`/`promote()` nunca reusen, dentro del mismo
    commit, el numero que estan a punto de liberar), restauracion por
    snapshot completo (nunca `indexes.insert()`: una linea existente
    puede estar en cualquier posicion del fichero).
    """
    root = repo_root()
    pm = pm_root(root)
    with gitcmd.file_lock(lock_resource(root)):
        indexes.seed(pm)

        if pre_check is not None:
            rejection = pre_check(pm)
            if rejection is not None:
                return WriteResult(ok=False, note_id=None, rejections=(rejection,), git_error=None)

        old_index_path = pm / old_index_name
        old_index_snapshot = old_index_path.read_text(encoding="utf-8")
        old_lines = indexes.read(old_index_name, pm)
        old_line = next((line for line in old_lines if line.id == old_id), None)
        indexes.remove(old_id, old_index_name, pm)
        if old_line is None:  # no deberia ocurrir: mismo candado desde la lectura
            raise RuntimeError(f"inconsistencia interna: {old_id!r} se retiro de {old_index_name}")

        index_name_new = _TYPE_TO_INDEX_FILE.get(new.type)
        if index_name_new is not None:
            same_file = index_name_new == old_index_name
            current_index = old_lines if same_file else indexes.read(index_name_new, pm)
            new_id = ids.next_id(new.type, index_with_archived(current_index, pm))
            candidate = dataclasses.replace(
                new, id=new_id, replaces=(old_id if link_replaces else new.replaces)
            )
        else:  # tipo fuera del vocabulario -- validate_type lo rechaza abajo
            candidate = dataclasses.replace(new, replaces=old_id) if link_replaces else new

        rejections = validate_note(candidate, ctx)
        if rejections:
            restore_snapshot_best_effort(old_index_path, old_index_snapshot)
            return WriteResult(ok=False, note_id=None, rejections=rejections, git_error=None)

        # index_name_new nunca es None aqui: validate_type ya lo habria rechazado.
        new_index_path = pm / index_name_new
        new_index_snapshot = (
            old_index_snapshot if same_file else new_index_path.read_text(encoding="utf-8")
        )
        new_line = IndexLine(
            id=candidate.id, zone1=candidate.zone1, zone2=candidate.zone2,
            headline=candidate.headline,
        )
        indexes.insert(new_line, index_name_new, pm)

        archive_path = pm / _ARCHIVE_FILE
        archive_snapshot = archive_path.read_text(encoding="utf-8")
        old_type = old_id.split("-", 1)[0]
        indexes.archive(
            ArchiveLine(
                date=datetime.now(timezone.utc).date(), type=old_type, id=old_id,
                zone1=old_line.zone1, zone2=old_line.zone2, headline=old_line.headline,
                destination=destination, destination_detail=candidate.id,
            ),
            pm,
        )

        touched = list({old_index_path, new_index_path, archive_path})

        def _restore_all() -> None:
            restore_snapshot_best_effort(old_index_path, old_index_snapshot)
            restore_snapshot_best_effort(new_index_path, new_index_snapshot)
            restore_snapshot_best_effort(archive_path, archive_snapshot)

        try:
            message = format.build_message(candidate)
            git_result = stage_and_commit(message, touched, root)
        except BaseException:
            _restore_all()
            raise

        if git_result.returncode != 0:
            _restore_all()
            for path in touched:
                gitcmd.run(["reset", "--", str(path)], cwd=root, timeout=gitcmd.GIT_TIMEOUT)
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        return WriteResult(ok=True, note_id=candidate.id, rejections=(), git_error=None)


# 2026-08-05, encargo del propietario: los dos rechazos de --promotes no
# tienen molde en TEXTOS.md -- redactados aqui con el mismo tono que el
# resto via rejection.build(), nunca impresos a mano. Pendiente de que
# TEXTOS.md Sec.1 se ponga al dia con estas dos formas.
def _reject_bad_promotes_target(new: Note, question_id: str, pm: Path) -> Rejection | None:
    """`None` si `question_id` es una Q abierta de verdad; un `Rejection`
    si no tiene forma de Q o si no esta vigente en QUESTIONS.md. Se llama
    ANTES de tocar ningun indice (via `pre_check` de `swap_and_archive`) --
    mismo criterio que `validator_pointers.validate_pointers` aplica a
    Replaces/Origin: rebota citando el id, nada se escribe.
    """
    relaunch = (
        f'gitmem note {new.type} --zones {new.zone1} {new.zone2} '
        f'"{new.headline}" --description "..." --promotes <ID de una Q real>',
    )
    if question_id.split("-", 1)[0] != "Q":
        what = f"--promotes apunta a {question_id!r}, que no es una pregunta (Q)"
        options = (
            "Solo una pregunta (Q) abierta asciende con --promotes -- a memo si la "
            "respuesta es un hecho, a descarte si es que no [spec Sec.4]. Cita el "
            "identificador de esa Q, nunca el de otro tipo.",
        )
        return rejection_.build(
            kind="promotes_not_a_question", what=what, options=options, command=relaunch
        )

    live_questions = {line.id for line in indexes.read(_TYPE_TO_INDEX_FILE["Q"], pm)}
    if question_id not in live_questions:
        what = f"--promotes cita un identificador que no existe: {question_id}"
        options = (
            "El puntero de --promotes tiene que apuntar a una pregunta (Q) abierta "
            "de verdad, igual que ya exige Replaces/Origin.",
        )
        return rejection_.build(
            kind="promotes_dangling", what=what, options=options, command=relaunch
        )

    return None


def promote(new: Note, question_id: str, ctx: Context) -> WriteResult:
    """Asciende `question_id` (una Q vigente) a `new`: sube a memo si la
    respuesta es un hecho, cae a descarte si es que no [spec Sec.4;
    TEXTOS Sec.4]. Delega en `swap_and_archive()` con
    `destination="promoted"` y `link_replaces=False` -- un ascenso no es
    una sustitucion, ver el docstring del modulo.
    """
    return swap_and_archive(
        question_id,
        _TYPE_TO_INDEX_FILE["Q"],
        new,
        ctx,
        destination="promoted",
        link_replaces=False,
        pre_check=lambda pm: _reject_bad_promotes_target(new, question_id, pm),
    )
