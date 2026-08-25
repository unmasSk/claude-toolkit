"""El fichero de reglas -- los remembers. Fuera del sistema de memoria, a
proposito.

Fachada/api: `add()`/`retract()`/`replace()` (mas abajo) son las
operaciones reales de esta pieza; el resto se partio en tres hermanos
por concernencia:

  - `rules_validate.py` -- valida `kind`/`text`/`quote` ANTES de tocar
    git o el fichero.
  - `rules_similarity.py` -- reconoce una linea ya escrita, detecta
    casi-duplicados por texto, y localiza/quita la linea exacta que
    `retract()`/`replace()` necesitan.
  - `rules_commit.py` -- candado, ruta del fichero, lectura, y la
    transaccion completa de comitear (o deshacer) una regla.

Este fichero importa de los tres e importa SOLO de ellos. Reexporta
`read_all`/`rules_file_path`/`iter_rule_texts`/`similar_existing`/
`strip_quote_suffix` bajo el mismo nombre, sin guion bajo.

Un remember NO es memoria de proyecto: no lleva zonas, no pasa por la
aduana de zonas, no aparece en ninguna busqueda ni informe, y no lo lee
ningun agente.

FORMATO DEL COMMIT:

    [remember][user] 🧠 <texto>
    [remember][claude] 🧠 <texto>

Solo titular, en espanol, sin cuerpo, tope de 200 caracteres.

`add()` (I-003) comitea de verdad: escribe la linea en el fichero
(`gitcmd.atomic_write()`, atomico) y la comitea con
`notes_commit.stage_and_commit()` -- el mismo mecanismo compartido que
`gitmem work`/`gitmem wip`/`gitmem note`. Si el commit falla, el fichero
se restaura a su contenido anterior (`notes_commit.
restore_snapshot_best_effort()`) y `add()` devuelve `ok=False` con
`git_error` -- nunca `ok=True` sin un commit real detras.

`retract()`/`replace()` comparten el MISMO camino atomico fichero+git
(`commit_or_restore`, bajo el mismo `lock_resource()`) -- una regla
retirada por este camino nunca deja a `health.coherence_rules()`
gritando una discrepancia falsa de "edicion a mano", porque HEAD y el
arbol de trabajo se mueven juntos o no se mueven. `replace()` es un
UNICO `atomic_write()` + UNICO `commit_or_restore()` sobre el contenido
ya con la linea vieja quitada y la nueva anadida -- nunca dos commits
encadenados, que dejarian una ventana real donde el retiro entra y el
alta no.

Quien lo llama: `bin/memory/rule.py` y el comando `/remember`.

`lib/memory/` no importa nada fuera de la biblioteca estandar de Python.
Imports planos entre hermanos. Este proyecto no defiende contra un
atacante externo -- lo que importa es que el sistema no se rompa a si
mismo: el fallo real es que el fichero y el commit queden
desincronizados, nunca que uno reporte exito sin el otro.
"""

import gitcmd
from emojis import CHANNEL_EMOJI
from model import WriteResult
from rules_commit import (
    commit_or_restore,
    lock_resource,
    read_current_rules_content,
    repo_root,
    rules_file_path,
)
from rules_commit import read_all  # noqa: F401 -- reexportado, add() no lo usa
from rules_similarity import (  # noqa: F401 -- iter_rule_texts/strip_quote_suffix reexportados
    find_rule_line,
    iter_rule_texts,
    remove_rule_line,
    similar_existing,
    strip_quote_suffix,
)
from rules_validate import (
    QUOTE_NOT_GIVEN,
    TEXT_MAX_CHARS,
    reject_invalid_kind,
    reject_invalid_text,
    reject_rule_not_found,
    reject_too_long,
    validate_quote,
)


def add(text: str, kind: str, quote=QUOTE_NOT_GIVEN) -> WriteResult:
    """Anade una regla: una linea mas en el fichero de reglas, escrita de
    forma atomica, seguida de un commit real. `ok=True` implica que el
    commit existe de verdad, nunca solo que el fichero se escribio.

    `quote` -- las palabras literales de quien la dijo, obligatoria en la
    practica para cualquier `kind` (kind-agnostic: exigirla solo para
    `kind == "user"` dejaba un hueco). Si se pasa y viene en blanco,
    rebota, salvo el literal `"none"` (`--quote none`, la unica salida
    para "Claude se deja una nota a si mismo"). Un llamador que ni
    siquiera menciona `quote` (`add(text, kind)`) no activa esta
    validacion. Con cita real, la linea escrita lleva un sufijo
    ` — «<cita>»`; `iter_rule_texts()` sigue devolviendo la linea entera.

    Rebota SIN tocar el fichero si `text`/`kind`/`quote` fallan sus
    validaciones (`reject_invalid_text`/`reject_invalid_kind`/
    `validate_quote`) -- salto de linea, vacio, o sobre el tope de
    caracteres.

    Si el commit falla o revienta a mitad, el fichero se restaura a
    `previous_content` con `notes_commit.restore_snapshot_best_effort()`
    y `add()` devuelve `ok=False` con `git_error` puesto al mensaje real
    de git.

    **Frontera aceptada, no se reabre sin que el propietario lo pida:**
    `add()` lee `rules.md` dos veces bajo el candado -- una al empezar, y
    otra inmediatamente antes de `gitcmd.atomic_write()`, para recoger
    una escritura externa (edicion a mano) que aterrice entre medias. La
    ventana entre esa SEGUNDA lectura y la escritura misma sigue siendo
    fisica y no se cierra del todo: cerrarla exigiria un compare-and-swap
    a nivel de fichero que `gitcmd.atomic_write()` no implementa. Se
    acepta porque `add()`/`retract()`/`replace()` son los UNICOS
    escritores reales de `rules.md` en todo el sistema, y los tres pasan
    por el mismo `lock_resource()` -- se serializan entre si sin
    excepcion. Solo una edicion manual que ignore la cabecera del
    fichero ("no editar") podria caer justo en esa rendija.
    """
    if "\n" in kind or not kind.strip():
        return WriteResult(
            ok=False, note_id=None, rejections=(reject_invalid_kind(kind),), git_error=None
        )
    if "\n" in text or not text.strip():
        return WriteResult(
            ok=False, note_id=None, rejections=(reject_invalid_text(text),), git_error=None
        )
    if len(text) > TEXT_MAX_CHARS:
        return WriteResult(
            ok=False, note_id=None, rejections=(reject_too_long(text),), git_error=None
        )

    quote_has_content, quote_rejection = validate_quote(quote, text)
    if quote_rejection is not None:
        return WriteResult(ok=False, note_id=None, rejections=(quote_rejection,), git_error=None)

    root = repo_root()
    with gitcmd.file_lock(lock_resource(root)):
        emoji = CHANNEL_EMOJI["rule"]
        subject = f"[remember][{kind}] {emoji} {text}"
        if quote_has_content:
            subject += f" — «{quote}»"

        path = rules_file_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_existed_before, previous_content = read_current_rules_content(path)

        # Re-chequeo bajo el candado, lo mas cerca posible de la escritura
        # real: recoge una edicion externa a `rules.md` que haya aterrizado
        # entre la lectura de arriba y este punto.
        file_existed_before, previous_content = read_current_rules_content(path)

        gitcmd.atomic_write(path, previous_content + subject + "\n")

        # `file_existed_before` viaja para que, si el commit falla en el
        # primer remember del proyecto, se borre el fichero entero en vez
        # de restaurarlo a una cabecera huerfana.
        git_error = commit_or_restore(path, previous_content, subject, root, file_existed_before)
        if git_error is not None:
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_error)

        return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)


def retract(text: str, kind: str) -> WriteResult:
    """Retira una regla: quita la linea `[kind]` cuyo texto BASE (sin
    cita) case exacto con `text`, escrita de forma atomica, seguida de
    un commit real -- mismo criterio que `add()`: `ok=True` implica que
    el commit existe de verdad, nunca solo que el fichero cambio.

    Identifica la linea por `find_rule_line()` (`rules_similarity.py`),
    que ya compara sobre el texto SIN cita -- quien retira una regla se
    refiere a lo que dijo, no a la cita que la acompana en el fichero.

    Rebota SIN tocar el fichero si `text`/`kind` fallan sus
    validaciones (mismas que `add()`: salto de linea, vacio) o si
    ninguna linea `[kind]` casa con `text` (`reject_rule_not_found()`)
    -- nunca un no-op silencioso que parezca exito. Un `kind` correcto
    pero un texto guardado bajo OTRO `kind` cae en el mismo rechazo:
    `find_rule_line()` filtra por `kind` antes de comparar texto.

    Si el commit falla o revienta a mitad, el fichero se restaura a
    `previous_content` (mismo mecanismo que `add()`) y `retract()`
    devuelve `ok=False` con `git_error` puesto al mensaje real de git.
    """
    if "\n" in kind or not kind.strip():
        return WriteResult(
            ok=False, note_id=None, rejections=(reject_invalid_kind(kind),), git_error=None
        )
    if "\n" in text or not text.strip():
        return WriteResult(
            ok=False, note_id=None, rejections=(reject_invalid_text(text),), git_error=None
        )

    root = repo_root()
    with gitcmd.file_lock(lock_resource(root)):
        path = rules_file_path(root)
        file_existed_before, previous_content = read_current_rules_content(path)
        # Re-chequeo bajo el candado, mismo motivo que en add(): recoge
        # una edicion externa a rules.md aterrizada entre medias.
        file_existed_before, previous_content = read_current_rules_content(path)

        matched_line = find_rule_line(previous_content, text, kind)
        if matched_line is None:
            return WriteResult(
                ok=False,
                note_id=None,
                rejections=(reject_rule_not_found(text, kind),),
                git_error=None,
            )

        new_content = remove_rule_line(previous_content, matched_line)
        emoji = CHANNEL_EMOJI["rule"]
        message = f"[remember][retract][{kind}] {emoji} {text}"

        gitcmd.atomic_write(path, new_content)

        git_error = commit_or_restore(path, previous_content, message, root, file_existed_before)
        if git_error is not None:
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_error)

        return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)


def replace(old_text: str, new_text: str, kind: str, quote=QUOTE_NOT_GIVEN) -> WriteResult:
    """Sustituye una regla: quita la linea `[kind]` cuyo texto BASE case
    exacto con `old_text` y anade `new_text` en su lugar, en UN SOLO
    `atomic_write()` seguido de UN SOLO `commit_or_restore()` -- nunca
    dos commits encadenados. Atomica de verdad: o el commit entra con
    las dos mitades (retiro + alta) dentro, o `commit_or_restore()`
    deshace la escritura entera y `old_text` sigue exactamente como
    estaba, sin que `new_text` haya aparecido en ningun sitio.

    Mismas validaciones que `add()` sobre `kind`/`new_text`/`quote`.
    Rebota SIN tocar el fichero si ninguna linea `[kind]` casa con
    `old_text` (`reject_rule_not_found()`), mismo criterio que
    `retract()` -- un `kind` equivocado para una regla que si existe
    cae en el mismo rechazo.
    """
    if "\n" in kind or not kind.strip():
        return WriteResult(
            ok=False, note_id=None, rejections=(reject_invalid_kind(kind),), git_error=None
        )
    if "\n" in new_text or not new_text.strip():
        return WriteResult(
            ok=False, note_id=None, rejections=(reject_invalid_text(new_text),), git_error=None
        )
    if len(new_text) > TEXT_MAX_CHARS:
        return WriteResult(
            ok=False, note_id=None, rejections=(reject_too_long(new_text),), git_error=None
        )

    quote_has_content, quote_rejection = validate_quote(quote, new_text)
    if quote_rejection is not None:
        return WriteResult(ok=False, note_id=None, rejections=(quote_rejection,), git_error=None)

    root = repo_root()
    with gitcmd.file_lock(lock_resource(root)):
        path = rules_file_path(root)
        file_existed_before, previous_content = read_current_rules_content(path)
        # Re-chequeo bajo el candado, mismo motivo que en add()/retract().
        file_existed_before, previous_content = read_current_rules_content(path)

        matched_line = find_rule_line(previous_content, old_text, kind)
        if matched_line is None:
            return WriteResult(
                ok=False,
                note_id=None,
                rejections=(reject_rule_not_found(old_text, kind),),
                git_error=None,
            )

        content_without_old = remove_rule_line(previous_content, matched_line)

        emoji = CHANNEL_EMOJI["rule"]
        new_subject = f"[remember][{kind}] {emoji} {new_text}"
        if quote_has_content:
            new_subject += f" — «{quote}»"

        new_content = content_without_old + new_subject + "\n"
        message = f"[remember][replace][{kind}] {emoji} {old_text} -> {new_text}"

        gitcmd.atomic_write(path, new_content)

        git_error = commit_or_restore(path, previous_content, message, root, file_existed_before)
        if git_error is not None:
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_error)

        return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)
