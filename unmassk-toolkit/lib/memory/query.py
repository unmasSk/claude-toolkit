"""Leer desde git hacia objetos -- el unico lector del historial de todo
el sistema de memoria.

No reimplementa el parseo del texto de un commit: toda nota sale de
`format.parse_message(text)` sobre el mensaje real de un commit (`git
log`), nunca de una regex propia. `Note.timestamp` no viaja en el texto
del commit -- `format.parse_message` devuelve un marcador de posicion
(`datetime.now()`); este modulo lo sustituye por la fecha de autor real
que `git log` ya trae en el mismo registro.

`by_file` no necesita ningun campo guardado: `git log -- <ruta>` da esa
funcion directamente.

Las cuatro funciones publicas leen contra el cwd del proceso; ninguna
declara su propio `root`/`cwd`.

`gitcmd.run()` nunca reintenta por su cuenta un fallo de git -- el
reintento es responsabilidad de esta pieza. `run_git_log()` (unico punto
de entrada a `git log` de todo el sistema, tambien usado por
`context.latest()` y `health.py`) reintenta un `returncode != 0` hasta
`_MAX_ATTEMPTS` veces: un `git` que falla una vez por carga (un
`index.lock` en curso) no puede leerse como "este proyecto no tiene
memoria". Si el fallo persiste, es real y se propaga como `RuntimeError`
con el `stderr` de git -- tragarlo devolveria una memoria vacia que se
confunde con "no hay nada". `_git_log()` (privada) es un envoltorio
delgado sobre `run_git_log()` con el formato de `Note` ya fijado.

Separadores: cada commit se pide con `-z` (terminador NUL entre
registros) y, dentro de cada registro, los campos van separados por
`\\x1f`. El mensaje crudo (`%B`) es el ULTIMO campo, partido con
`maxsplit=2` -- un `\\x1f` dentro del propio mensaje nunca particiona de
mas.

Que NO hace: no agrupa en racimos, no decide que esta vigente y que
archivado (lo dice el indice), no formatea.

`lib/memory/` no importa nada fuera de la biblioteca estandar de Python.
Import plano entre hermanos.
"""

import dataclasses
import time
from pathlib import Path

import format
import gitcmd
import timefmt
from model import Note

_FIELD_SEP = "\x1f"
_MAX_ATTEMPTS = 3  # intento inicial + hasta 2 reintentos
_RETRY_DELAY_SECONDS = 0.05

# `%at` (segundos-epoch), no `%aI` (ISO-8601 con sufijo `Z` en huso cero,
# que `datetime.fromisoformat` de Python 3.10 no sabe leer) [decision del
# propietario, 2026-08-08 -- ver `timefmt.from_git_seconds` para el porque
# completo].
_LOG_FORMAT = f"--pretty=format:%H{_FIELD_SEP}%at{_FIELD_SEP}%B"

# El mensaje literal y estable que git escribe cuando `git log` se pide
# sobre una rama que todavia no tiene ni un commit -- un repo recien
# creado, estado NORMAL, no un fallo. Verificado en vivo: `git init` +
# `git log` da `returncode=128` con `stderr` conteniendo exactamente esta
# frase.
UNBORN_BRANCH_MARKER = "does not have any commits yet"


def _is_unborn_branch(stderr: str) -> bool:
    """`True` si `stderr` es el mensaje real de git para "esta rama
    todavia no tiene ningun commit". Nunca se reintenta este caso: es el
    estado real y permanente del repo hasta el primer commit.
    """
    return UNBORN_BRANCH_MARKER in stderr


def run_git_log(pretty_format: str, extra_args: tuple[str, ...] = ()) -> str:
    """Ejecuta `git log -z {pretty_format} [extra_args]` contra el cwd del
    proceso, reintentando un `returncode != 0` transitorio hasta
    `_MAX_ATTEMPTS` veces antes de rendirse, y devuelve el `stdout` crudo.

    Unico punto de entrada a `git log` de todo el sistema de memoria --
    tambien lo usan `context.latest()` y `health.py`. No sabe que formato
    trae `pretty_format` ni que significan `extra_args`; eso es trabajo
    de quien llama.

    Una rama sin ningun commit todavia (`_is_unborn_branch`) es un estado
    VALIDO, no un fallo: devuelve cadena vacia de inmediato, sin
    reintentar.

    Un fallo que persiste tras agotar los reintentos SI es real: se
    propaga como `RuntimeError` con el `stderr` de git -- una cadena
    vacia aqui se confundiria con "no hay nada todavia".
    """
    args = ["log", "-z", pretty_format, *extra_args]
    result = None
    for attempt in range(_MAX_ATTEMPTS):
        result = gitcmd.run(args, cwd=Path.cwd(), timeout=gitcmd.GIT_TIMEOUT)
        if result.returncode == 0:
            return result.stdout
        if _is_unborn_branch(result.stderr):
            return ""
        if attempt < _MAX_ATTEMPTS - 1:
            time.sleep(_RETRY_DELAY_SECONDS)
    raise RuntimeError(
        f"git log fallo tras {_MAX_ATTEMPTS} intentos: {result.stderr}"
    )


def _git_log(extra_args: tuple[str, ...]) -> str:
    """Envoltorio privado sobre `run_git_log()` con el formato de `Note`
    ya fijado (`_LOG_FORMAT`) -- lo usan las cuatro funciones publicas de
    esta pieza (`by_id`/`by_zone`/`by_word`/`by_file`, via `_all_notes()`
    y `by_file()`). Ver `run_git_log()` para el mecanismo real (reintento,
    rama sin commits, fallo real)."""
    return run_git_log(_LOG_FORMAT, extra_args)


def _exists_at_head(relpath: str, root: Path) -> bool:
    """`True` si `relpath` tiene version comiteada en HEAD ahora mismo --
    `git cat-file -e HEAD:{relpath}`, que solo comprueba EXISTENCIA
    (`-e`) sin traer contenido, y sale con `returncode == 0` si existe,
    distinto de cero si no -- para CUALQUIER motivo de "no": el path
    nunca se comiteo, el path existe en el arbol de trabajo pero no en
    HEAD, o el repositorio no tiene NINGUN commit todavia.

    Existencia se decide por `returncode`, nunca parseando el texto de
    `stderr` de `git show`: git tiene varias redacciones distintas segun
    el caso ("does not exist in", "invalid object name 'HEAD'", "exists
    on disk, but not in 'HEAD'"), y depender de esa prosa es una carrera
    que nunca se cierra del todo. `cat-file -e` es un chequeo de
    existencia puro.

    Un fallo de `cat-file` que NO sea "no existe" (repo corrupto) es
    indistinguible, por `returncode`, de "no existe" -- ese hueco lo
    cierra `show_file_at_head()`: si esta funcion dice `True`, el `git
    show` que sigue tiene que salir limpio si o si; si falla de todos
    modos, es un fallo real de git y se propaga en alto.
    """
    result = gitcmd.run(
        ["cat-file", "-e", f"HEAD:{relpath}"], cwd=root, timeout=gitcmd.GIT_TIMEOUT
    )
    return result.returncode == 0


def show_file_at_head(relpath: str, root: Path) -> str:
    """El contenido COMITEADO de `relpath` tal como HEAD lo tiene AHORA
    MISMO, nunca el arbol de trabajo (eso lo lee quien llama, con
    `path.read_text()`, si lo necesita para comparar).

    Segundo punto de entrada a un lector de historial de git de este
    modulo, junto a `run_git_log()`. `git show`/`git cat-file` solo se
    invocan AQUI en todo `lib/memory/`. A diferencia de `run_git_log()`,
    SI recibe `root` explicito -- su unico llamador
    (`health.coherence_rules()`) ya recibe un `root` que puede no
    coincidir con el cwd del proceso.

    Primero pregunta EXISTENCIA (`_exists_at_head()`); solo si existe,
    pide el CONTENIDO con `git show`. Cadena vacia -- estado valido, no
    un fallo -- cuando `_exists_at_head()` dice que no. Si dice que si
    existe pero el `git show` que sigue falla de todos modos, es un
    fallo real de git y revienta con `RuntimeError` y el `stderr` real,
    nunca una cadena vacia que lo enmascare.
    """
    if not _exists_at_head(relpath, root):
        return ""
    result = gitcmd.run(["show", f"HEAD:{relpath}"], cwd=root, timeout=gitcmd.GIT_TIMEOUT)
    if result.returncode == 0:
        return result.stdout
    raise RuntimeError(f"git show HEAD:{relpath} fallo en {root}: {result.stderr}")


def _parse_records(raw_stdout: str) -> tuple[tuple[Note, str], ...]:
    """Convierte el `stdout` crudo de `_git_log` en pares `(Note, texto)`,
    saltando en silencio los registros que `format.parse_message` no
    reconoce como nota (p.ej. el commit inicial `init` del repo, o
    cualquier commit que no sea una nota de memoria) -- `parse_message`
    nunca lanza [format.py], y un commit ajeno no es un fallo de este
    modulo, es simplemente historial que no le pertenece.

    El texto crudo devuelto junto a cada `Note` es el que `by_word`
    necesita para marcar las lineas que casaron (fila 4): buscar dentro
    de `note.description`/`note.why` por separado perderia el titular y
    cualquier campo no modelado como texto libre.
    """
    parsed: list[tuple[Note, str]] = []
    for record in raw_stdout.split("\0"):
        if not record:
            continue
        _commit_hash, author_date, raw_message = record.split(_FIELD_SEP, 2)
        text = raw_message.rstrip("\n")
        note = format.parse_message(text)
        if note is None:
            continue
        note = dataclasses.replace(note, timestamp=timefmt.from_git_seconds(author_date))
        parsed.append((note, text))
    return tuple(parsed)


def _all_notes() -> tuple[tuple[Note, str], ...]:
    return _parse_records(_git_log(()))


def by_id(note_id: str) -> Note | None:
    """La nota con `id == note_id`, o `None` si no existe -- nunca una
    excepcion ni una cadena vacia.

    La comparacion se normaliza a minusculas (`--id r-001` tiene que
    encontrar `R-001`); el `Note` devuelto trae `note.id` tal cual esta
    escrito en el commit.
    """
    target = note_id.lower()
    for note, _text in _all_notes():
        if note.id.lower() == target:
            return note
    return None


def by_zone(zone1: str | None, zone2: str | None) -> tuple[Note, ...]:
    """Notas cuya `zone1` (y `zone2`, si se pide) coinciden. Un parametro
    en `None` no filtra por ese eje.
    """
    return tuple(
        note
        for note, _text in _all_notes()
        if (zone1 is None or note.zone1 == zone1)
        and (zone2 is None or note.zone2 == zone2)
    )


def by_word(word: str) -> tuple[tuple[Note, tuple[str, ...]], ...]:
    """Notas cuyo texto contiene `word`, junto con las lineas concretas
    que casaron -- si esta funcion devolviera solo notas, el informe
    tendria que volver a buscar dentro para marcar la linea.

    La comparacion se normaliza a minusculas (la prosa de las notas
    escribe nombres propios en mayuscula inicial, y la mayoria de las
    busquedas se teclean en minuscula); las lineas devueltas llevan su
    texto original.
    """
    needle = word.lower()
    results: list[tuple[Note, tuple[str, ...]]] = []
    for note, text in _all_notes():
        matched_lines = tuple(line for line in text.split("\n") if needle in line.lower())
        if matched_lines:
            results.append((note, matched_lines))
    return tuple(results)


def by_file(path: Path) -> tuple[Note, ...]:
    """Notas cuyo commit toco `path`, via `git log -- <ruta>` directamente
    -- no hace falta ningun campo guardado de ficheros tocados: ese campo
    no existe en el v2 [Sec.8.2].
    """
    raw_stdout = _git_log(("--", str(path)))
    return tuple(note for note, _text in _parse_records(raw_stdout))
