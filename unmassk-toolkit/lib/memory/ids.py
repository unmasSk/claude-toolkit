"""Per-type note id counter and duplicate-id detection over an already loaded index.

Pure functions: no file or git access; duplicates are reported, never repaired.
"""

from model import ArchiveLine, IndexLine


def next_id(type_: str, index: tuple[IndexLine, ...]) -> str:
    """Next id of ``type_`` (e.g. "D-001" on an empty index), counting only that type's ids."""
    prefix = f"{type_}-"
    numbers = [
        int(line.id[len(prefix):])
        for line in index
        if line.id.startswith(prefix)
    ]
    next_number = max(numbers, default=0) + 1
    return f"{prefix}{next_number:03d}"


def find_duplicates(index: tuple[IndexLine | ArchiveLine, ...]) -> tuple[str, ...]:
    """Ids appearing more than once in ``index`` (case-insensitive), each as first spelled."""
    seen: dict[str, list] = {}
    for line in index:
        entry = seen.setdefault(line.id.lower(), [line.id, 0])
        entry[1] += 1
    return tuple(first for first, count in seen.values() if count > 1)
