"""Leer y escribir los ocho ficheros de indice: la unica pieza que los abre.

No commitea (eso lo hace `notes`) ni decide a que indice va cada nota. El
formato de cada linea es de `format.py`. `insert`/`archive`/`remove` fallan
en alto si el fichero no existe: nunca lo crean vacio. `counts` lee cada
vez, nunca guarda un numero.
"""

from datetime import datetime, time, timezone
from pathlib import Path
from collections.abc import Mapping

import format
from gitcmd import atomic_write, file_lock
from model import ArchiveLine, IndexLine, Note
from vocabulary import INDEX_FILES

_ARCHIVE_NAME = "ARCHIVED.md"

# Cabeceras literales de TEXTOS.md Sec.4, byte a byte (texto de salida).
_DISCARDED_HEADER = (
    "# Permanente: aquí nada se archiva. Existe para que nadie lo re-proponga.\n"
)
_ARCHIVE_HEADER = (
    "# Todo lo retirado, en orden cronológico. El tipo viaja en la línea; al\n"
    "# pasado se le pregunta por fecha. Lo escribe el script.\n"
)


def _header_for(name: str) -> str:
    """La cabecera de `name`: literal para DISCARDED.md y ARCHIVED.md, la regla comun para el resto."""
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
    """Falla en alto, antes de tocar disco, si `name` no es uno de los ocho indices."""
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
    """Las lineas de `ARCHIVED.md`, en el orden del fichero; una linea que no
    encaja con ningun destino se descarta, como en `read`.
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
    `name` no existe. Lee y escribe bajo un mismo candado, con escritura atomica.
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


def remove(note_id: str, name: str, root: Path, only: IndexLine | None = None) -> int:
    """Retira la linea de `note_id` de `name` y devuelve cuantas retiro. Falla
    en alto si `name` no existe o `note_id` no esta en el.

    Sin `only` retira toda linea con ese id; con `only`, solo la primera
    linea igual a `only`. Mismo candado que `insert()`.
    """
    _require_index_file(name)
    path = _index_path(name, root)
    with file_lock(path):
        if not path.exists():
            raise FileNotFoundError(f"no se puede retirar de un indice inexistente: {path}")

        raw_lines = path.read_text(encoding="utf-8").split("\n")
        kept: list[str] = []
        removed = 0
        for raw_line in raw_lines:
            parsed = format.parse_index_line(raw_line)
            wanted = parsed is not None and parsed.id == note_id
            if wanted and only is not None:
                wanted = removed == 0 and parsed == only
            if wanted:
                removed += 1
                continue
            kept.append(raw_line)

        if not removed:
            raise ValueError(f"{note_id!r} no esta en {name}")

        text = "\n".join(kept)
        if not text.endswith("\n"):
            text += "\n"
        atomic_write(path, text)
        return removed


def archive(line: ArchiveLine, root: Path) -> None:
    """Anade `line` al final de `ARCHIVED.md`. Falla en alto sin escribir
    nada si el fichero no existe. Mismo candado que `insert()`.
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
    """Identificadores que estan en `ARCHIVED.md`; un fichero ausente son cero."""
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
