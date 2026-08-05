"""Escribir una nota y su linea de indice, en el mismo commit, o ninguna
de las dos -- contrato en docs/memoria-v2/PIEZAS.md Sec.8.1.

ES LA PIEZA DONDE EL SISTEMA SE PUEDE CORROMPER A SI MISMO. Si la nota se
commitea y el indice no, hay una nota que ninguna busqueda encuentra
jamas -- memoria escrita e invisible. Si el indice se actualiza y el
commit falla, hay una linea que apunta a una nota que no existe. Las dos
son corrupcion silenciosa: nada revienta, y el fallo se descubre semanas
despues.

El orden de `write` es el contrato, y no es negociable [PIEZAS.md Sec.8.1]:

    candado -> identificador -> validar -> escribir el indice
            -> commit de nota + indice JUNTOS
            -> si git falla: restaurar el indice y propagar el error
               REAL de git

Validar ANTES de tocar el indice, restaurar DESPUES de que git falle.
Cualquier otro orden deja una ventana donde el indice y git dicen cosas
distintas.

LA MECANICA DE GIT DE LA QUE ESTE FICHERO TIRA -- EL CANDADO
(`lock_resource`), LA RAIZ (`repo_root`/`pm_root`), EL `git add`+`git
commit` (`stage_and_commit`) Y LAS DOS RESTAURACIONES DE MEJOR ESFUERZO
-- VIVE EN `notes_commit.py`, partido de aqui por tamano (550 lineas,
techo 500, mismo limite que ya se aplico a `format.py` [DEUDA.md punto
12] y `validator.py` [DEUDA.md punto 14]). El commit de trabajo
(`write_work`) va con ella, porque es la unica de las cinco operaciones
que no toca ningun indice y por tanto no necesita ni el candado ni
ninguna restauracion. Se importa de alli de forma PLANA [PIEZAS.md
Sec.3.3bis] y se reexpone bajo el mismo nombre, asi que
`notes.pm_root`/`notes.write_work` siguen alcanzables exactamente igual
para quien los llame hoy -- ver el docstring de `notes_commit.py` para
el porque de ese corte y no otro, y las decisiones (candado global,
`git add` explicito, que restauracion usa cada operacion) que fija esa
mecanica.

**2026-08-05, mismo techo, segundo corte:** la mecanica de "retirar una
linea existente y archivarla con un destino" (id nuevo, retirada,
insercion, archivado, commit+restauracion) que `replace()` usaba entera
se movio a `notes_promote.py` (`swap_and_archive()`), porque `promote()`
-- el ascenso de una Q, tercera forma de archivar tras `replace()`/
`close()` -- la necesita IGUAL y una segunda copia de esa transaccion es
la unica amenaza que este proyecto declara. `replace()` (mas abajo)
delega en ella; se importa de alli de forma PLANA, mismo patron que
`notes_commit.py`. Ver el docstring de `notes_promote.py` para el porque
completo.

DECISIONES TOMADAS PARA CERRAR HUECOS QUE EL CONTRATO NO FIJA LETRA POR
LETRA (ninguna estaba escrita en PIEZAS.md; derivadas del propio texto y
verificadas contra un repo git real antes de fijarlas):

1. **`discard_alternatives` enlaza cada alternativa a la decision via
   `origin`.** No lo exige ningun test de esta tarea, pero SI lo exige
   el resto del sistema ya escrito: `vocabulary.py` documenta que
   `origin` "aparece citado ... para X (los automaticos que nacen
   enlazados a su D, spec Sec.4)", y `clusters.py` (PIEZAS Sec.9.1)
   agrupa EXCLUSIVAMENTE por punteros Origin/Replaces, nunca por
   parecido. Sin este enlace, las alternativas descartadas quedarian
   huerfanas para siempre en el racimo de su decision. Como el
   identificador de la decision solo se conoce DESPUES de escribirla,
   `discard_alternatives` extiende `ctx.known_ids` con ese id recien
   asignado antes de validar cada alternativa (si no, `validate_pointers`
   rechazaria un puntero que en ese mismo instante ya es real).

2. **`replace()`/`close()` -- las cinco filas anadidas el 2026-08-02**
   (PIEZAS.md Sec.8.1): comparten el orden de `write()`, pero retiran una
   linea EXISTENTE en vez de anadir una nueva -- ver punto 4.

3. **La restauracion del indice esta protegida por `try`/`except
   BaseException`, no solo por el `if git_result.returncode != 0` de la
   letra del contrato.** Auditoria del 2026-08-02: entre escribir la
   linea de indice y comprobar el resultado de git no habia ningun
   `try`/`finally` -- una excepcion real a mitad (un Ctrl-C durante un
   commit lento, por ejemplo) se saltaba la restauracion entera y dejaba
   el indice huerfano. Las funciones de restauracion (`notes_commit.py`)
   son, ademas, el unico sitio que llama a `indexes.remove()`/escribe el
   snapshot en esta ruta: si la propia restauracion revienta, su
   excepcion se traga (mejor esfuerzo) en vez de sustituir el
   diagnostico real (el `GitResult.stderr` de git, o la excepcion que
   interrumpio el commit) -- perder ESE mensaje es perder la unica causa
   que el usuario tiene para arreglar el problema.

4. **Retirar una linea EXISTENTE, no anadir una nueva -- tres
   consecuencias.** (a) El id nuevo de `replace()` se calcula con la
   lectura tomada ANTES de `indexes.remove()`, nunca despues: evita que,
   DENTRO DEL MISMO commit, el numero que `replace()` esta a punto de
   liberar se reutilice para la nota nueva que ese mismo `replace()` esta
   creando. Esto protege solo ESE caso concreto (mismo commit, mismo
   tipo) -- NO protegia, hasta el punto 5 de aqui abajo, contra reusar el
   id de una nota archivada en un commit ANTERIOR (una M cerrada por
   `close()` ayer, o sustituida por un `replace()` de otro dia): ver el
   hallazgo real y el arreglo en el punto 5. (b) La restauracion no puede ser `indexes.insert()` (la
   vuelta exacta de `write()`, porque ahi la linea SIEMPRE es la
   ultima): una linea existente puede estar en cualquier posicion, y
   anadirla al final la moveria. Se restaura el contenido completo
   capturado antes de escribir (`restore_snapshot_best_effort()` en
   `notes_commit.py`, misma primitiva atomica que `indexes.py` ya usa
   por dentro). (c) Mismo mecanismo para `ARCHIVED.md` (sin funcion
   "quitar la ultima linea": `indexes.remove()` usa
   `format.parse_index_line`, que nunca casa con una linea de archivo).
   El asunto de `close()` no tiene plantilla propia ni encaja en
   `gitcmd.commit_empty()` (reservado a escritores que no tocan NINGUN
   fichero); usa el literal de TEXTOS.md Sec.4 ("closed: <motivo>").

5. **`next_id()` recibe SIEMPRE el indice vivo mas los ids ya archivados
   -- arreglado 2026-08-03, hallazgo real (Moriarty, capa 5, memoria
   corrompida de forma permanente).** Hasta este arreglo, `write()` y
   `replace()` llamaban a `ids.next_id()` con `current_index` a secas --
   solo las lineas VIVAS que `indexes.read()` devuelve. En cuanto una
   nota se archivaba (`close()`, o el lado "vieja" de un `replace()`), su
   numero desaparecia de ese indice y quedaba libre para la SIGUIENTE
   alta del mismo tipo: reproducido en un repositorio real, dar de alta
   `I-001`, cerrarla, y dar de alta una segunda incidencia distinta
   volvia a devolver `I-001` -- dos commits reales, dos notas distintas,
   el mismo identificador permanente en los dos. `search.py --id I-001`
   ensenaba solo la incidencia vieja (la nueva no aparecia por ese id) y
   `reindex.py` no lo detectaba ni lo reparaba.

   `ids.next_id()` en si NO cambia -- sigue sin abrir ficheros ni llamar
   a git [ids.py, docstring], su firma sigue siendo `next_id(type_,
   index)` letra por letra [PIEZAS.md Sec.7.2, "el identificador lo
   asigna el script leyendo el indice"] -- el arreglo va en QUIEN le pasa
   el indice, tal como pide el contrato. `index_with_archived()` (movida a
   `notes_promote.py` el 2026-08-05, importada plana de alli -- ver el
   corte de arriba) construye, antes de cada llamada a `next_id()`
   en `write()` y en `swap_and_archive()` (`replace()`/`promote()`), la union del indice vivo con un
   `IndexLine` hueco (solo `id`; `zone1`/`zone2`/`headline` vacios --
   `next_id()` nunca los lee) por cada id de `indexes.archived_ids(pm)`
   [ya existente, ya usado por `health.coherence()` para lo mismo]. Los
   DOS llamantes se corrigieron -- `write()` (alta normal) y `replace()`
   (el lado "nueva" de una sustitucion) -- aunque `replace()` ya tenia la
   proteccion parcial del punto 4(a) para el caso de un solo commit, esa
   proteccion nunca cubrio un id archivado en un commit ANTERIOR, que es
   exactamente el hallazgo real. `close()` no necesita este arreglo: no
   calcula ningun id nuevo, solo retira uno existente.

No importa nada del toolkit fuera de la biblioteca estandar de Python
[PIEZAS.md Sec.13]. Imports planos entre hermanos de `lib/memory/`
[PIEZAS.md Sec.3.3bis].
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
# `index_with_archived`/`promote`/`swap_and_archive` importados de forma
# plana de `notes_promote.py` [2026-08-05, segundo corte por el techo de
# 500 lineas -- ver el parrafo que arranca "2026-08-05, mismo techo,
# segundo corte" en el docstring de arriba]. Reexpuestos bajo el mismo
# nombre: `notes.promote` sigue alcanzable igual para `bin/memory/note.py`.
from notes_promote import index_with_archived, promote, swap_and_archive  # noqa: F401
from validator import Context, validate_note
from vocabulary import INDEX_FILES, TYPE_INDEX_FILES

# Que fichero de indice le toca a cada tipo -- dato cerrado del sistema,
# vive en `vocabulary.TYPE_INDEX_FILES` [correccion 2026-08-02: antes era
# una copia privada de este modulo; `vocabulary.py` ya es la casa de "los
# siete tipos" y "los ocho ficheros de indice" por separado, ver su
# propio docstring]. Reexpuesto bajo el nombre privado de siempre para no
# tocar el resto de este fichero: `write()`/`replace()`/`close()` siguen
# llamando a `_TYPE_TO_INDEX_FILE.get(...)` tal cual. La comprobacion de
# que ningun tipo se queda sin fichero de indice ya vive en
# `vocabulary.py` (revienta la carga de ESE modulo, antes de que este
# pueda siquiera importarlo) -- una segunda copia de esa asercion aqui
# seria codigo muerto.
_TYPE_TO_INDEX_FILE = TYPE_INDEX_FILES

# Destino comun de replace()/close() -- literal de TEXTOS.md Sec.4. Mismo
# fichero que indexes.py usa por dentro (su `_ARCHIVE_NAME` es privado de
# ese modulo, no se reexporta). La asercion evita el mismo desajuste
# silencioso que la de arriba, si algun dia cambia en vocabulary.INDEX_FILES.
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
            # `seed()` es idempotente (indexes.py Sec.7.3): crea los ocho
            # ficheros vacios con su cabecera solo si faltan, nunca toca
            # uno que ya tiene notas. `write()` es el punto de entrada
            # real de una escritura -- no puede asumir que algo mas ya
            # sembro los indices antes (un proyecto recien instalado, o
            # -- como en fila 3 de test_notes.py -- un caller que solo
            # quiere probar el fallo de git sin sembrar nada primero).
            # `seed()` tambien crea `pm` si falta (`root.mkdir(parents=True,
            # exist_ok=True)`, indexes.py) -- un proyecto recien instalado
            # no tiene todavia `.claude/project-memory/`.
            indexes.seed(pm)
            current_index = indexes.read(index_name, pm)
            new_id = ids.next_id(note.type, index_with_archived(current_index, pm))
            candidate = dataclasses.replace(note, id=new_id)
        else:
            # Tipo fuera del vocabulario cerrado: no hay indice del que
            # leer un contador. `validate_type` (dentro de
            # `validate_note`, mas abajo) es quien lo rechaza con el
            # texto correcto -- aqui solo se evita reventar con un
            # `KeyError` antes de llegar a esa validacion.
            candidate = note

        rejections = validate_note(candidate, ctx)
        if rejections:
            return WriteResult(ok=False, note_id=None, rejections=rejections, git_error=None)

        # A partir de aqui `index_name` nunca es None: `validate_type`
        # ya habria rechazado cualquier tipo fuera de `_TYPE_TO_INDEX_FILE`.
        index_line = IndexLine(
            id=candidate.id,
            zone1=candidate.zone1,
            zone2=candidate.zone2,
            headline=candidate.headline,
        )
        indexes.insert(index_line, index_name, pm)

        index_path = pm / index_name
        # Todo lo que sigue puede fallar de dos formas: un `GitResult`
        # con `returncode != 0` (git respondio, pero mal -- rama de
        # abajo), o una excepcion real a mitad (un Ctrl-C durante un
        # commit lento, por ejemplo -- `stage_and_commit` reventando). La
        # restauracion del indice tiene que darse en los dos casos, no
        # solo cuando git falla de forma ordenada: sin este `try`, una
        # excepcion aqui deja la linea de indice ya escrita en disco
        # apuntando a un commit que nunca se hizo, huerfana para siempre.
        try:
            message = format.build_message(candidate)
            git_result = stage_and_commit(message, [index_path], root)
        except BaseException:
            restore_index_best_effort(candidate.id, index_name, pm)
            raise

        if git_result.returncode != 0:
            restore_index_best_effort(candidate.id, index_name, pm)
            # Limpieza del staging area, mejor esfuerzo: si `git add`
            # llego a completarse pero `git commit` fallo por otra
            # razon, el indice ya se restauro en disco (la garantia que
            # el contrato exige) pero `.git/index` podria seguir
            # apuntando al contenido descartado. No se propaga un
            # fallo de este paso -- el invariante real (bytes del
            # indice identicos a los de antes) ya quedo protegido.
            gitcmd.run(["reset", "--", str(index_path)], cwd=root, timeout=gitcmd.GIT_TIMEOUT)
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        return WriteResult(ok=True, note_id=candidate.id, rejections=(), git_error=None)


def discard_alternatives(
    decision: Note, alternatives: tuple[Note, ...], ctx: Context
) -> tuple[WriteResult, ...]:
    """Escribe `decision` y cada una de `alternatives`, cada una en su
    propio commit -- "un acto, un commit" aplica a nota+indice, no al
    acto completo [PIEZAS.md Sec.8.1]. Una decision con dos alternativas
    produce tres resultados (tres commits), no dos.

    Cada alternativa se escribe con `origin` apuntando al identificador
    real de `decision` (ver punto 1 del docstring del modulo) -- el
    enlace que `clusters.py` necesita para agruparlas bajo su decision.
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
    ARCHIVED.md con destino "replaced by <new_id>" [spec Sec.5 camino 1;
    TEXTOS Sec.4; PIEZAS.md Sec.8.1]. La mecanica (id nuevo antes de
    retirar la vieja, restauracion por snapshot, `indexes.remove()`
    lanzando `ValueError` sola si `old_id` no esta en su indice --
    test_notes.py fila 11) vive en `notes_promote.swap_and_archive()`
    desde el 2026-08-05 [segundo corte por el techo de 500 lineas, ver el
    docstring del modulo] -- `replace()` solo resuelve el fichero de
    `old_id` y delega, con `destination="replaced"` y
    `link_replaces=True` (la nota nueva lleva `Note.replaces=old_id`).
    """
    old_type = old_id.split("-", 1)[0]
    old_index_name = _TYPE_TO_INDEX_FILE.get(old_type)
    if old_index_name is None:
        raise ValueError(f"{old_id!r}: tipo desconocido, ningun indice le corresponde")
    return swap_and_archive(
        old_id, old_index_name, new, ctx, destination="replaced", link_replaces=True
    )


# 2026-08-04, hallazgo real (Moriarty, capa 5): `close()` pasaba `reason`
# tal cual a `indexes.archive()` -> `format.build_archive_line()`, que lo
# interpola en lo que TEXTOS.md Sec.4 fija como UNA SOLA linea fisica de
# ARCHIVED.md -- sin pasar por el plegado que si protege headline/Why/
# Description en el camino de un commit normal. Un salto de linea real en
# el motivo partia la entrada en dos (o, si el resto encajaba con
# `_ARCHIVE_LINE_RE`, creaba una entrada fantasma que nunca existio), y el
# comando salia con "✅ archivada" y codigo 0 -- corrupcion silenciosa mas
# un visto bueno falso, justo la unica amenaza que este proyecto declara.
# Plegar aqui exigiria que `read_archive()`/`parse_archive_line()` supieran
# reconstruir una entrada partida en varias lineas fisicas -- ARCHIVED.md
# es, por contrato [TEXTOS.md Sec.4, spec Sec.7], exactamente una linea por
# nota, sin continuacion documentada en ningun sitio; inventar esa
# continuacion ahi contradice el propio molde que TEXTOS.md fija como
# fuente de la verdad. Se rechaza en su lugar, reusando el MISMO mecanismo
# de rechazo que ya usa el resto del sistema (`rejection.build`/
# `render_terminal`, PIEZAS.md Sec.7.4) -- nada nuevo inventado.
def _reject_close_reason_multiline(note_id: str, reason: str) -> Rejection | None:
    """`None` si `reason` cabe en una sola linea fisica; un `Rejection` si
    trae un salto de linea propio -- ver el porque en el comentario de
    arriba. `close()` no pasa por `validate_note()` [ver su docstring],
    asi que este es el unico punto donde `reason` se puede rechazar antes
    de escribir nada.
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
    indice y entra en ARCHIVED.md con destino "closed: <reason>" [spec
    Sec.5 camino 2; TEXTOS Sec.4; PIEZAS.md Sec.8.1]. `ctx` se recibe por
    simetria de Superficie con `write()`/`replace()` pero no se usa: cerrar
    no crea ninguna nota nueva que `validate_note()` tenga que ver.

    Reutiliza `indexes.remove()` para localizar y retirar la linea (mismo
    motivo que `replace()`, ver su docstring) -- si `note_id` no esta en
    su indice, lanza `ValueError` sola, sin tocar nada (test fila 11).

    **`reason` se rechaza ANTES de tocar nada si trae un salto de linea
    propio** [2026-08-04, ver `_reject_close_reason_multiline` arriba] --
    la unica validacion que `close()` hace, porque `reason` no es campo de
    `Note` y `validate_note()` nunca lo ve.
    """
    del ctx  # ver docstring: recibido por simetria de Superficie, sin uso
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
            for path in touched:
                gitcmd.run(["reset", "--", str(path)], cwd=root, timeout=gitcmd.GIT_TIMEOUT)
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        return WriteResult(ok=True, note_id=note_id, rejections=(), git_error=None)
