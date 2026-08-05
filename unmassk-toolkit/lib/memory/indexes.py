"""Leer y escribir los ocho ficheros de indice -- contrato en
docs/memoria-v2/PIEZAS.md Sec.7.3.

Para que: "nadie mas los toca" [Sec.7.3]. Es la unica pieza que abre los
ocho ficheros de `vocabulary.INDEX_FILES` para leer o escribir sus lineas.
Cada fichero lleva la cabecera que TEXTOS.md Sec.4 fija como texto de
salida ("Lo escribe el script. No editar. Si diverge, manda git."), y esa
cabecera es la razon por la que esta pieza existe: si diverge de lo que
git guarda en el commit real, manda git, no este fichero.

**No commitea.** Escribe el fichero; quien lo mete en el mismo commit que
la nota es `notes` (fase 2, no existe todavia), y esa union es la
transaccion del sistema [Sec.7.3, "Que NO hace"]. Tampoco decide que va a
que indice: eso lo dice el tipo de la nota, y esa decision es de quien
llama, no de este modulo.

Construir y parsear la linea de texto exacta es cosa de `format.py`
(Sec.6.4) -- no se reimplementa el formato aqui, es exactamente el fallo
del v1 que Sec.6.4 documenta (562 lineas de parseo de historial
duplicadas en tres ficheros, sincronizadas a mano). `insert`/`read` usan
`format.build_index_line`/`format.parse_index_line` directamente sobre el
`IndexLine` que reciben o devuelven (misma forma de campos que `Note`:
id/zone1/zone2/headline, duck typing intencionado, no una coincidencia).
`read_archive` usa `format.parse_archive_line`. `archive` necesita
`format.build_archive_line`, que espera un `Note` con `timestamp:
datetime` -- pero `ArchiveLine.date` ya es un `datetime.date` sin hora, no
un `Note`. Se resuelve envolviendo los campos de la `ArchiveLine` en un
`Note` de usar-y-tirar (con `description=""`, campo que
`build_archive_line` no lee) y `timestamp` reconstruido con
`datetime.combine(line.date, time.min, tzinfo=timezone.utc)` -- la vuelta
exacta de `date` a `datetime` para que `note.timestamp.date()` devuelva el
mismo `date` de partida. Eso reutiliza la logica de formato entera (emoji,
espaciado, las tres frases de destino) sin escribirla una segunda vez
aqui.

Las lineas de cabecera y las lineas en blanco nunca casan con
`format.parse_index_line`/`format.parse_archive_line` (ambas regex exigen
que la linea empiece por `[` o por una fecha `AAAA-MM-DD`) -- por eso
`read`/`read_archive` las descartan solas, sin necesitar saber que es una
cabecera: cualquier linea que el parser no reconozca simplemente no entra
en el resultado.

`seed` es idempotente por construccion: solo escribe un fichero que
`Path.exists()` diga que falta. Nunca trunca ni sobreescribe uno que ya
tiene notas -- ese es el fallo que el test de esta fila existe para
atrapar (instalar sobre un proyecto que ya tiene notas y vaciarle los
indices).

`insert`/`archive`/`remove` fallan en alto (excepcion, nunca crean el
fichero) si el indice de destino no existe todavia -- `seed()` no corrio,
o el fichero se perdio. Un indice que se crea solo y vacio en ese momento
parece "no hay notas" en vez de gritar que algo esta mal [Sec.7.3, fila 4
de "Sus tests"].

`counts` no guarda nada: cuenta leyendo `read`/`read_archive` en cada
llamada, siempre. Un numero guardado se separaria de la realidad la
primera vez que alguien escriba un fichero de indice sin pasar por esta
pieza (a mano, o desde otro proceso) y nadie lo notaria [Sec.7.3, fila 3].
"""

from datetime import datetime, time, timezone
from pathlib import Path
from collections.abc import Mapping

import format
from gitcmd import atomic_write, file_lock
from model import ArchiveLine, IndexLine, Note
from vocabulary import INDEX_FILES

_ARCHIVE_NAME = "ARCHIVED.md"

# Cabecera literal de TEXTOS.md Sec.4 para los ficheros con texto propio,
# distinto de la regla comun de los siete indices vigentes. Estas dos
# constantes SI llevan tildes/em-dash: son texto de salida del sistema
# (lo que se escribe de verdad en el fichero), no comentarios de codigo --
# copiadas byte a byte de TEXTOS.md, no reescritas a mano.
_DISCARDED_HEADER = (
    "# Permanente: aquí nada se archiva. Existe para que nadie lo re-proponga.\n"
)
_ARCHIVE_HEADER = (
    "# Todo lo retirado, en orden cronológico. El tipo viaja en la línea; al\n"
    "# pasado se le pregunta por fecha. Lo escribe el script.\n"
)


def _header_for(name: str) -> str:
    """La cabecera de `name`, literal donde TEXTOS.md Sec.4 la fija
    distinta (DISCARDED.md, ARCHIVED.md), y derivada de la "regla comun"
    para los otros seis -- el mismo patron que DECISIONS.md muestra en
    Sec.4 ("# DECISIONS -- indice. Lo escribe el script. No editar. Si
    diverge, manda git."), con el nombre del propio fichero en el lugar
    de "DECISIONS".
    """
    if name == _ARCHIVE_NAME:
        return _ARCHIVE_HEADER
    if name == "DISCARDED.md":
        return _DISCARDED_HEADER
    stem = name[: -len(".md")] if name.endswith(".md") else name
    return f"# {stem} — índice. Lo escribe el script. No editar. Si diverge, manda git.\n"


def _index_path(name: str, root: Path) -> Path:
    return Path(root) / name


def _archive_path(root: Path) -> Path:
    return Path(root) / _ARCHIVE_NAME


def _require_index_file(name: str) -> None:
    """Falla en alto si `name` no es uno de los ocho ficheros de
    `vocabulary.INDEX_FILES` -- "nadie mas los toca" [Sec.7.3] incluye no
    escribir en un fichero ajeno del mismo directorio (p.ej. `zones.json`)
    por un `name` equivocado del llamador. Se llama ANTES de tocar disco,
    para que un destino invalido nunca llegue a abrir el fichero.
    """
    if name not in INDEX_FILES:
        raise ValueError(
            f"{name!r} no es uno de los ocho indices de vocabulary.INDEX_FILES"
        )


def seed(root: Path) -> None:
    """Crea los ocho ficheros vacios con su cabecera. Idempotente: un
    fichero que ya existe no se toca, con notas o sin ellas.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name in INDEX_FILES:
        path = _index_path(name, root)
        if not path.exists():
            path.write_text(_header_for(name) + "\n", encoding="utf-8")


def read(name: str, root: Path) -> tuple[IndexLine, ...]:
    """Las lineas de nota de `name`, en el orden del fichero. Falla en
    alto si `name` no existe todavia -- un indice ausente es un fallo del
    sistema, no "cero notas".
    """
    path = _index_path(name, root)
    if not path.exists():
        raise FileNotFoundError(f"indice inexistente, seed() no corrio: {path}")

    lines: list[IndexLine] = []
    for raw_line in path.read_text(encoding="utf-8").split("\n"):
        parsed = format.parse_index_line(raw_line)
        if parsed is not None:
            lines.append(parsed)
    return tuple(lines)


def read_archive(root: Path) -> tuple[ArchiveLine, ...]:
    """Las lineas de `ARCHIVED.md`, en el orden del fichero. Reconoce las
    tres formas de destino (`replaced by` / `closed:` / `promoted to`) via
    `format.parse_archive_line` -- una linea que no encaje con ninguna
    (escrita a mano, o de un formato mas viejo) se descarta en silencio en
    vez de tumbar la lectura entera, mismo contrato que `read`.
    """
    path = _archive_path(root)
    if not path.exists():
        raise FileNotFoundError(f"ARCHIVED.md inexistente, seed() no corrio: {path}")

    lines: list[ArchiveLine] = []
    for raw_line in path.read_text(encoding="utf-8").split("\n"):
        parsed = format.parse_archive_line(raw_line)
        if parsed is not None:
            lines.append(parsed)
    return tuple(lines)


def insert(line: IndexLine, name: str, root: Path) -> None:
    """Anade `line` al final de `name`. Falla en alto sin escribir nada si
    `name` no existe todavia -- nunca lo crea a medias.

    Ciclo leer-modificar-escribir COMPLETO dentro de un unico `file_lock()`
    (gitcmd.py Sec.7.1), no solo la escritura: `remove()` reescribe el
    fichero entero leyendo su contenido primero, y sin este candado
    envolviendo tambien la lectura, un `insert()` que caiga justo entre la
    lectura y la escritura de un `remove()` concurrente (aunque sea sobre
    otra nota) desaparece en silencio -- el `remove()` sobreescribe con una
    version del fichero mas vieja que no lo vio. La escritura en si es
    atomica (`gitcmd.atomic_write`, temporal + `os.replace()`), para que un
    proceso muerto a mitad no deje el indice partido.
    """
    _require_index_file(name)
    path = _index_path(name, root)
    with file_lock(path):
        if not path.exists():
            raise FileNotFoundError(
                f"no se puede insertar en un indice inexistente: {path}. "
                "Ejecuta seed() primero."
            )
        existing = path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
        new_content = existing + format.build_index_line(line) + "\n"
        atomic_write(path, new_content)


def remove(note_id: str, name: str, root: Path) -> None:
    """Retira la linea de `note_id` de `name`, conservando el resto en su
    orden y su cabecera intacta. Falla en alto si `name` no existe todavia
    o si `note_id` no esta en el.

    Mismo candado y misma escritura atomica que `insert()` -- ver su
    docstring. Serializados sobre el mismo `path`, un `insert()` y un
    `remove()` concurrentes nunca se intercalan: uno termina su ciclo
    entero antes de que el otro empiece el suyo.
    """
    _require_index_file(name)
    path = _index_path(name, root)
    with file_lock(path):
        if not path.exists():
            raise FileNotFoundError(f"no se puede retirar de un indice inexistente: {path}")

        raw_lines = path.read_text(encoding="utf-8").split("\n")
        kept: list[str] = []
        removed = False
        for raw_line in raw_lines:
            parsed = format.parse_index_line(raw_line)
            if parsed is not None and parsed.id == note_id:
                removed = True
                continue
            kept.append(raw_line)

        if not removed:
            raise ValueError(f"{note_id!r} no esta en {name}")

        text = "\n".join(kept)
        if not text.endswith("\n"):
            text += "\n"
        atomic_write(path, text)


def archive(line: ArchiveLine, root: Path) -> None:
    """Anade `line` al final de `ARCHIVED.md`. Falla en alto sin escribir
    nada si el fichero no existe todavia.

    Mismo candado y misma escritura atomica que `insert()`/`remove()` --
    ver sus docstrings. `ARCHIVED.md` es un fichero de indice mas dentro
    de `INDEX_FILES`, sujeto al mismo riesgo de carrera si algo mas lo
    toca (hoy solo `archive()` escribe ahi, pero el candado no depende de
    quien mas exista).
    """
    path = _archive_path(root)
    with file_lock(path):
        if not path.exists():
            raise FileNotFoundError(f"ARCHIVED.md inexistente: {path}")

        placeholder = Note(
            type=line.type,
            id=line.id,
            zone1=line.zone1,
            zone2=line.zone2,
            headline=line.headline,
            description="",
            timestamp=datetime.combine(line.date, time.min, tzinfo=timezone.utc),
        )
        text = format.build_archive_line(placeholder, line.destination, line.destination_detail)
        existing = path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
        atomic_write(path, existing + text + "\n")


def archived_ids(root: Path) -> frozenset[str]:
    """Identificadores ya retirados, segun `ARCHIVED.md` -- fuente unica
    para "que esta archivado ahora mismo". Antes de esto, `boot.py` y
    `report.py` calculaban lo mismo cada uno con su propia copia privada
    (`frozenset(line.id for line in indexes.read_archive(...))`, letra
    por letra igual); ahora las dos llaman aqui [revision 2026-08-02].

    Un `ARCHIVED.md` que todavia no existe no es un fallo: es el estado
    real de un proyecto recien instalado, antes de que `seed()` haya
    corrido ni una vez -- cero archivados es un dato valido, no una
    excepcion [mismo criterio que `health.coherence_rules()` ya aplica a
    la ausencia del fichero de reglas]. Sin este descuento, `boot.build()`
    revienta con `FileNotFoundError` en la primerisima sesion de
    cualquier proyecto, antes de que exista una sola nota que mostrar.
    """
    root = Path(root)
    if not (root / _ARCHIVE_NAME).exists():
        return frozenset()
    return frozenset(line.id for line in read_archive(root))


def counts(root: Path) -> Mapping[str, int]:
    """Cuantas lineas de nota tiene cada uno de los ocho ficheros, leyendo
    cada vez -- nunca un numero guardado.
    """
    result: dict[str, int] = {}
    for name in INDEX_FILES:
        if name == _ARCHIVE_NAME:
            result[name] = len(read_archive(root))
        else:
            result[name] = len(read(name, root))
    return result
