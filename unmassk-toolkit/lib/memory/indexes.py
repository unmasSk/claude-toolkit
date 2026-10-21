"""Read and write the eight index files; the only module that opens them.

Writers fail loud when the file is missing and never create it empty."""

from datetime import datetime, time, timezone
from pathlib import Path
from collections.abc import Mapping

import format
from gitcmd import atomic_write, file_lock
from model import ArchiveLine, IndexLine, Note
from vocabulary import INDEX_FILES

_ARCHIVE_NAME = "ARCHIVED.md"

# Literal file headers (output text).
_DISCARDED_HEADER = (
    "# Permanente: aquí nada se archiva. Existe para que nadie lo re-proponga.\n"
)
_ARCHIVE_HEADER = (
    "# Todo lo retirado, en orden cronológico. El tipo viaja en la línea; al\n"
    "# pasado se le pregunta por fecha. Lo escribe el script.\n"
)


def _header_for(name: str) -> str:
    """Return the header line for index file `name`."""
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
    """Raise ValueError before touching disk if `name` is not one of the eight indexes."""
    if name not in INDEX_FILES:
        raise ValueError(
            f"{name!r} no es uno de los ocho indices de vocabulary.INDEX_FILES"
        )


def seed(root: Path) -> None:
    """Create the eight index files with their header; existing files are left untouched."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name in INDEX_FILES:
        path = _index_path(name, root)
        if not path.exists():
            path.write_text(_header_for(name) + "\n", encoding="utf-8")


def read(name: str, root: Path) -> tuple[IndexLine, ...]:
    """Return the note lines of `name` in file order; raise if the file is missing."""
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
    """Return the parseable lines of `ARCHIVED.md` in file order; raise if it is missing."""
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
    """Append `line` to `name` under its lock with an atomic write; raise if the file is missing."""
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
    """Remove every line of `note_id` from `name` (only the first equal to `only` if given); return the count.

    Raise if the file is missing or the id is not in it."""
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
    """Append `line` to `ARCHIVED.md` under its lock; raise if the file is missing."""
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
    """Return the ids in `ARCHIVED.md`; empty when the file is missing."""
    root = Path(root)
    if not (root / _ARCHIVE_NAME).exists():
        return frozenset()
    return frozenset(line.id for line in read_archive(root))


def counts(root: Path) -> Mapping[str, int]:
    """Return the note-line count of each of the eight files, read fresh every time."""
    result: dict[str, int] = {}
    for name in INDEX_FILES:
        if name == _ARCHIVE_NAME:
            result[name] = len(read_archive(root))
        else:
            result[name] = len(read(name, root))
    return result
