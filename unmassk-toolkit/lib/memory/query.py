"""Leer desde git hacia objetos -- contrato en docs/memoria-v2/PIEZAS.md
Sec.8.2.

Para que: **el unico lector del historial**. El v1 tenia esto implementado
TRES veces, 562 lineas en tres ficheros sincronizadas a mano, y ya habia
fallado tres veces con el mismo patron [medido -- TESTIGO Sec.3]. Aqui hay
uno.

No reimplementa el parseo del texto de un commit -- eso es exactamente el
fallo del v1 que este modulo existe para no repetir. Toda nota sale de
`format.parse_message(text)` sobre el mensaje real de un commit (`git log`),
nunca de una regex propia. `Note.timestamp` no viaja en el texto del commit
[format.py, docstring]: `format.parse_message` devuelve un marcador de
posicion (`datetime.now()`); este modulo lo sustituye por la fecha de autor
real que `git log` ya trae en el mismo registro, con `dataclasses.replace`.

`by_file` no necesita ningun campo guardado: el campo de ficheros tocados
no existe en el v2, y su funcion la da `git log -- <ruta>` directamente
[Sec.8.2] -- en el v1 ese campo se escribio 605 veces sin que nadie lo
leyera nunca.

Las cuatro funciones leen contra el cwd del proceso (igual que
`gitcmd.commit()`, que "hereda el cwd ambiental... quien la llama ya esta
corriendo dentro del repo") -- ninguna declara su propio `root`/`cwd`
porque la superficie de Sec.8.2 no lo pide.

**El reintento (fila 3) es responsabilidad de esta pieza, no de
`gitcmd.run()`**: `gitcmd.py` Sec.7.1 declara explicitamente que `run()`
"nunca lanza por un fallo DE GIT... un returncode != 0 es un resultado
normal" -- no reintenta por su cuenta. `run_git_log()` (publica, unico
punto de entrada a `git log` de TODO el sistema de memoria, no solo de
este modulo -- ver el parrafo siguiente) reintenta un `returncode != 0`
hasta `_MAX_ATTEMPTS` veces antes de rendirse, con una pausa corta entre
intentos: un `git` que falla una vez por carga (p.ej. un `index.lock` en
curso) no puede leerse como "este proyecto no tiene memoria" [Sec.8.2, fila
3]. Si el fallo persiste tras agotar los reintentos, es un fallo real (no
transitorio) y se propaga en alto (`RuntimeError` con el `stderr` real de
git) -- tragarlo devolveria una memoria vacia que se confunde con "no hay
nada", exactamente lo que la fila 2 prohibe para un caso distinto
(identificador inexistente) y que aqui seria igual de silencioso.
`_git_log()` (privada) sigue siendo el unico punto de entrada DENTRO de
este modulo, fijando el formato de una `Note`; es un envoltorio delgado
sobre `run_git_log()`.

**`run_git_log()` se hizo publica el 2026-08-02** [encargo del
orquestador, incidencia real: "hay tres modulos leyendo el historial de
git por su cuenta, y el contrato dice que solo puede haber uno"].
`context.latest()` y las dos lecturas de `health.py`
(`_rule_commit_texts`, `_issue_commit_dates`) tenian cada una su PROPIO
`git log` directo, construido a mano, sin el reintento de este modulo --
exactamente el patron que Sec.8.2 declara prohibido ("el v1 tenia esto
implementado TRES veces... sincronizadas a mano"). El sintoma ya se
habia pagado: arreglar que una rama sin commits no reventara el arranque
se arreglo aqui y el arranque siguio reventando en los otros dos
lectores, cada uno con el mismo agujero por su lado -- hubo que
arreglarlo cuatro veces. `run_git_log(pretty_format, extra_args=())`
generaliza lo que antes solo sabia leer el formato de una `Note`: recibe
el `--pretty=format:...` y los argumentos extra que cada consumidor
necesita, y devuelve el `stdout` crudo (o RuntimeError si el fallo es
real) sin saber nada de que campos trae ese formato -- interpretar el
resultado sigue siendo trabajo de quien llama, nunca de esta funcion.

Separadores: cada commit se pide con `-z` (terminador NUL entre registros
completos) y, dentro de cada registro, los campos van separados por
`\\x1f` -- un commit nunca puede contener un NUL de verdad (git lo rechaza
a nivel de objeto), asi que el limite de REGISTRO nunca puede confundirse
con contenido real de una nota, sea el que sea. Dentro de un registro solo
el mensaje crudo (`%B`) puede traer casi cualquier caracter, y por eso es
el ULTIMO campo, partido con `maxsplit=2` -- un `\\x1f` que apareciera
dentro del propio mensaje nunca particiona de mas.

Que NO hace [Sec.8.2]: no agrupa en racimos (`clusters`), no decide que
esta vigente y que archivado (lo dice el indice), no formatea.

`lib/memory/` no importa nada del toolkit fuera de la biblioteca estandar
de Python [PIEZAS.md Sec.13]. Import plano entre hermanos (`import format`,
`import gitcmd`) [PIEZAS.md Sec.3.3bis].
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
# creado, estado NORMAL, no un fallo [hallazgo 2 de Moriarty, ronda 2,
# 2026-08-02]. Verificado en vivo: `git init` + `git log` da
# `returncode=128` con `stderr` conteniendo exactamente esta frase (varia
# el nombre de rama entre comillas, nunca esta frase). Antes de este
# arreglo, ese `returncode != 0` se trataba como el mismo fallo transitorio
# que un `index.lock` en curso: se reintentaba tres veces y, al agotar los
# intentos, se lanzaba -- nadie lo capturaba, y el arranque entero moria en
# el primerisimo `git log` de cualquier proyecto sin un solo commit todavia.
UNBORN_BRANCH_MARKER = "does not have any commits yet"


def _is_unborn_branch(stderr: str) -> bool:
    """`True` si `stderr` es el mensaje real de git para "esta rama
    todavia no tiene ningun commit" -- ver `UNBORN_BRANCH_MARKER`. Nunca
    reintenta este caso: no es una carga pasajera, es el estado real y
    permanente del repo hasta el primer commit.

    Privada (guion bajo) desde 2026-08-04 -- pero esta es la UNICA de un
    grupo de seis funciones revisadas ese dia que tuvo un motivo REAL para
    haber sido publica alguna vez, y ese motivo merece quedar escrito para
    que nadie lo lea como "esto no se toca".

    Se hizo publica el 2026-08-02 porque `context.py` y `health.py` tenian
    cada uno su propio `git log` directo y llamaban a esta funcion por
    separado (ver "`run_git_log()` se hizo publica" en el docstring del
    modulo). Ese mismo dia los dos se consolidaron para pasar por
    `run_git_log()` de aqui abajo en vez de invocar `git log` por su
    cuenta. Comprobado el 2026-08-04 con
    `grep -rn "is_unborn_branch" unmassk-toolkit/`: ningun fichero fuera
    de este modulo la nombra ya (los tres tests que la mencionan lo hacen
    en prosa/docstring, sin llamarla), y hoy el UNICO llamador es
    `run_git_log()`, mas abajo en este mismo fichero. El motivo por el que
    se hizo publica desaparecio ese mismo dia; nadie la volvio a bajar
    hasta ahora.

    Si manana otra pieza necesita saber si una rama esta recien nacida,
    volver a hacerla publica es LEGITIMO -- no fue un error ponerla
    publica en su momento, fue que su motivo se resolvio en otro sitio (la
    consolidacion en `run_git_log()`) y esta funcion se quedo sin el
    segundo llamador que justificaba el guion bajo fuera.
    """
    return UNBORN_BRANCH_MARKER in stderr


def run_git_log(pretty_format: str, extra_args: tuple[str, ...] = ()) -> str:
    """Ejecuta `git log -z {pretty_format} [extra_args]` contra el cwd del
    proceso, reintentando un `returncode != 0` transitorio hasta
    `_MAX_ATTEMPTS` veces antes de rendirse, y devuelve el `stdout` crudo.

    **Unico punto de entrada a `git log` de todo el sistema de memoria**
    -- no solo de este modulo. Ver "`run_git_log()` se hizo publica el
    2026-08-02" en el docstring de arriba para el porque exacto: antes de
    esta funcion, `query.py`, `context.py` y `health.py` tenian cada uno
    su propia invocacion de `git log` construida a mano, el mismo patron
    de tres implementaciones sincronizadas que Sec.8.2 existe para
    impedir. Esta funcion NO sabe que formato trae `pretty_format` ni que
    significan `extra_args` -- eso es trabajo de quien llama (`_git_log`
    de aqui abajo para una `Note`; `context.latest()` para un cierre de
    sesion; `health._rule_commit_texts()`/`health._issue_commit_dates()`
    para commits de regla y de trabajo).

    Una rama sin ningun commit todavia (`_is_unborn_branch`) es un estado
    VALIDO, no un fallo [hallazgo 2 de Moriarty, ronda 2, 2026-08-02]:
    devuelve cadena vacia de inmediato, sin reintentar y sin contarlo como
    el fallo real de la rama de abajo -- un repo recien creado, sin un
    solo commit, no es "git fallo", es "todavia no hay memoria".

    Un fallo que persiste tras agotar los reintentos SI es real, no
    transitorio: se propaga como `RuntimeError` con el `stderr` real de
    git -- devolver una cadena vacia aqui se confundiria con "no hay
    nada todavia", el mismo silencio que la fila 2 de Sec.8.2 prohibe
    para el caso de un identificador inexistente.
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
    excepcion ni una cadena vacia (fila 2 de Sec.8.2): un fallo que se
    confunde con "no hay nada" es un fallo que pasa callado.

    La comparacion se normaliza a minusculas [hallazgo en vivo
    2026-08-06: `--id r-001` no encontraba `R-001`, aunque `next_id()`
    siempre genera el prefijo en mayusculas -- un usuario tecleando en
    minuscula es el caso normal, no el raro]. El `Note` devuelto trae
    `note.id` tal cual esta escrito en el commit -- solo la comparacion
    se normaliza, nunca el dato.
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
    """Notas cuyo texto contiene `word`, junto con las lineas concretas que
    casaron (fila 4 de Sec.8.2) -- si esta funcion devolviera solo notas,
    el informe tendria que volver a buscar dentro para marcar la linea,
    una segunda puerta de lectura.

    La comparacion se normaliza a minusculas [hallazgo en vivo
    2026-08-06: `gitmem search ultron` y `gitmem search Ultron` daban
    resultados distintos -- una sustancial perdida de memoria real,
    porque la prosa de las notas escribe los nombres propios en
    mayuscula inicial (`Ultron`, `Moriarty`) y la mayoria de las
    busquedas reales se teclean en minuscula]. Las lineas devueltas
    llevan su texto ORIGINAL, tal cual esta en el commit -- solo la
    comparacion se normaliza, nunca lo que se enseña.
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
