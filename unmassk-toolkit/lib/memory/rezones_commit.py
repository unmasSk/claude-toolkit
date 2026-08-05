"""Aplica el plan de `health.rebuild_plan()` sobre los indices reales y lo
GUARDA de forma que sobreviva a un `git checkout` -- en un solo commit
que junta todos los ficheros tocados, o (ver mas abajo) sin necesidad de
commit si el resultado ya coincide con `HEAD`. Si algo falla de verdad,
ninguno de los ficheros tocados queda modificado. Mismo contrato de
transaccion que `notes.write()`/`replace()`/`close()` [notes.py,
docstring del modulo: "candado -> ... -> escribir el indice -> commit ...
-> si git falla: restaurar"], aplicado aqui a una REPARACION en vez de a
una nota nueva.

HALLAZGO REAL QUE ESTO CIERRA [encargo de esta tarea, demostrado por
Moriarty]: `bin/memory/rezones.py --rebuild` (el modo sin `--verify`)
aplicaba el plan llamando a `indexes.insert()`/`indexes.remove()`
directamente -- que escriben en disco pero NUNCA comitean [indexes.py,
docstring: "No commitea"] -- y no llamaba a git en ningun punto. La
reparacion quedaba solo en el arbol de trabajo: `git status` la enseñaba
como cambio sin guardar, y un `git checkout` sobre el indice reparado la
borraba sin ningun aviso -- de vuelta a la averia de partida. El chequeo
de salud (`health.coherence()`) no lo detectaba porque compara DISCO
contra GIT, nunca lo COMITEADO contra lo que hay en el arbol de trabajo.

Vive en un fichero propio, no dentro de `notes.py` ni de `notes_commit.py`
-- los dos estan contra su techo de 500 lineas [DEUDA.md puntos 12/14,
mismo limite: `notes.py` 444/500, `notes_commit.py` 498/500 antes de esta
pieza]. Reutiliza la mecanica YA PUBLICA de `notes_commit.py`
(`lock_resource`, `restore_snapshot_best_effort`) y de `gitcmd.py`
(`run`, `commit`) en vez de reescribirlas -- no es una segunda
transaccion, es la MISMA mecanica aplicada a un caso distinto. Toma el
mismo candado global (`lock_resource(root)`) que `write`/`replace`/
`close`/`write_work` [notes_commit.py, punto 1 de su docstring], para que
una reconstruccion y una escritura de nota nunca se intercalen sobre los
mismos ocho indices.

**Limite conocido, cerrado como caso DESCARTADO por decision del
propietario -- no reparado [DEUDA.md, PARTE 1, B22, y punto 28 de la
PARTE 2, 2026-08-04]:** el plan que esta funcion aplica se calcula FUERA
del candado (en `bin/memory/rezones.py`) y, una vez dentro, nunca se
vuelve a comprobar si sigue vigente -- se aplica a ciegas. Con dos
reparaciones casi a la vez sobre la misma divergencia, la medicion real
dio **15 de 15**: la segunda reinserta la misma nota y la COMITEA, sin
que un `git checkout` pueda deshacerlo despues. Ese hecho sigue siendo
cierto y no se borra. Lo que cambia es el estado: **"no va a pasar
nunca" [propietario, 2026-08-04, respondiendo a la pregunta que
bloqueaba las capas 2 y 3]** -- se trabaja en una sola ventana, y por
eso NO se construye ninguna reparacion para este caso, ni recomprobar
el plan dentro del candado ni ninguna otra. El candado que esta pieza ya
coge (parrafo de arriba) se queda tal cual: la decision cierra ese eje,
no desmonta lo que ya funciona.

Y algo que sigue siendo cierto aunque el caso se descarte, y que NO es
lo mismo que el parrafo anterior: **quien inserta una linea de indice no
comprueba si el identificador ya esta** -- `indexes.insert()` anade sin
mirar. Eso no es concurrencia, es una comprobacion que sencillamente no
existe, sea cual sea el numero de procesos que la llamen.

**Un caso que `stage_and_commit()` no cubre, y por eso no se reutiliza
tal cual aqui:** si la corrupcion que se repara nunca llego a
COMITEARSE (una edicion a mano en el arbol de trabajo, nunca un `git
commit`), reparar puede devolver el fichero exactamente a los mismos
bytes que YA tiene `HEAD` -- no hay nada nuevo que comitear, y eso NO es
un fallo: el arbol de trabajo ya es identico a lo comiteado, asi que un
`git checkout` sobre el ya no puede perder nada (no hay diferencia que
perder). `git commit` sobre un pathspec sin cambios staged devuelve
`returncode != 0` igual que un fallo real -- tratarlo como error
rechazaria exactamente la reparacion que mas rapido se resuelve sola. Por
eso esta pieza comprueba `git diff --cached --quiet` ANTES de comitear
(en vez de interpretar el texto de error de `git commit`, fragil): `0` =
nada quedo distinto de `HEAD`, exito sin commit; `1` = si hay algo que
guardar, se comitea de verdad.

No decide QUE cambia -- eso sigue siendo exclusivamente
`health.rebuild_plan()` [PIEZAS.md Sec.9.4, "Que NO hace": "No repara
nada. Detecta y enseña. Reparar los indices es un comando aparte,
explicito"]. Esta pieza recibe el plan ya decidido (la misma forma exacta
que `rebuild_plan()` devuelve) y solo lo APLICA y lo GUARDA -- "reparar"
sigue siendo el comando aparte (`rezones.py`), no este modulo ni
`health.py`.

No importa nada del toolkit fuera de la biblioteca estandar de Python
[PIEZAS.md Sec.13]. Imports planos entre hermanos de `lib/memory/`
[PIEZAS.md Sec.3.3bis]. No importa `notes.py` ni `health.py` -- evita
cualquier ciclo con `health.py`, que ya importa `notes.py`.
"""

from pathlib import Path

import gitcmd
import indexes
from model import IndexLine, Note, WriteResult
from notes_commit import lock_resource, restore_snapshot_best_effort


def _build_message(
    to_insert: tuple[tuple[Note, str], ...], to_remove: tuple[tuple[str, str], ...]
) -> str:
    """Mensaje del commit de reparacion -- ningun texto de TEXTOS.md fija
    uno para esta operacion (mismo hueco que ya declaran `work.py`/
    `wip.py` para su propio rechazo de rama protegida: "el texto exacto
    no esta fijado en ningun documento"). Cita cada identificador
    afectado, no solo un recuento, para que `git log` sea la explicacion
    completa de que reparo esta reconstruccion sin tener que abrir el
    diff.
    """
    parts = []
    if to_insert:
        parts.append("reinsertadas: " + ", ".join(note.id for note, _target in to_insert))
    if to_remove:
        parts.append("retiradas: " + ", ".join(note_id for note_id, _name in to_remove))
    return "rezones: reparación de índices (" + "; ".join(parts) + ")"


def apply_rebuild_plan(
    to_insert: tuple[tuple[Note, str], ...],
    to_remove: tuple[tuple[str, str], ...],
    pm: Path,
    root: Path,
) -> WriteResult:
    """Aplica `to_insert`/`to_remove` -- la forma exacta que devuelve
    `health.rebuild_plan()` -- sobre los indices de `pm`, y lo guarda: en
    un commit nuevo si el resultado difiere de `HEAD`, o sin commit si ya
    coincide (ver el parrafo del modulo sobre este caso). Si no hay nada
    que aplicar, no toma el candado ni llama a git.

    Si `git add` o el commit fallan de verdad -- `returncode` distinto de
    cero por una razon REAL, o una excepcion a mitad -- TODOS los
    ficheros tocados se restauran a su contenido EXACTO de antes
    (snapshot completo, misma tactica que `notes.replace()`/
    `notes.close()` usan para sus propios ficheros de varias lineas --
    una linea reconstruida puede caer en cualquier posicion del indice,
    `indexes.insert()` la moveria al final si se usara como reversa).
    Mejor esfuerzo, mismo motivo que `restore_snapshot_best_effort()` ya
    documenta: si la propia restauracion revienta, esa excepcion no debe
    tapar el diagnostico real que `git_error` lleva.
    """
    touched_names = {target for _note, target in to_insert} | {name for _note_id, name in to_remove}
    if not touched_names:
        return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)

    with gitcmd.file_lock(lock_resource(root)):
        touched_paths = {
            pm / name: (pm / name).read_text(encoding="utf-8") for name in touched_names
        }
        path_args = [str(p) for p in touched_paths]

        def _restore_all() -> None:
            for path, original in touched_paths.items():
                restore_snapshot_best_effort(path, original)

        def _reset_staged() -> None:
            gitcmd.run(["reset", "--", *path_args], cwd=root, timeout=gitcmd.GIT_TIMEOUT)

        try:
            for note, target in to_insert:
                indexes.insert(
                    IndexLine(
                        id=note.id, zone1=note.zone1, zone2=note.zone2, headline=note.headline
                    ),
                    target,
                    pm,
                )
            for note_id, name in to_remove:
                indexes.remove(note_id, name, pm)

            add_result = gitcmd.run(["add", "--", *path_args], cwd=root, timeout=gitcmd.GIT_TIMEOUT)
            if add_result.returncode != 0:
                _restore_all()
                return WriteResult(
                    ok=False, note_id=None, rejections=(), git_error=add_result.stderr
                )

            diff_result = gitcmd.run(
                ["diff", "--cached", "--quiet", "--", *path_args],
                cwd=root, timeout=gitcmd.GIT_TIMEOUT,
            )
            if diff_result.returncode == 0:
                # El arbol de trabajo ya coincide con HEAD tras aplicar
                # el plan -- ver el parrafo del modulo. Ya no hay nada
                # que un `git checkout` pueda perder.
                return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)
            if diff_result.returncode != 1:
                _restore_all()
                _reset_staged()
                return WriteResult(
                    ok=False, note_id=None, rejections=(), git_error=diff_result.stderr
                )

            message = _build_message(to_insert, to_remove)
            git_result = gitcmd.commit(message, list(touched_paths), allow_empty=False, cwd=root)
        except BaseException:
            _restore_all()
            _reset_staged()
            raise

        if git_result.returncode != 0:
            _restore_all()
            _reset_staged()
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)
