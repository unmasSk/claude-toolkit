"""Zone persistence: name normalization, the cross-process lock and the atomic write of zones.json."""

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import textnorm
from model import Zone


def normalize(name: str) -> str:
    """Lowercase, accent-free zone name or alias; descriptions are not normalized."""
    return textnorm.normalize_text(name)


def _serialize(zones: dict[str, Zone]) -> dict:
    return {
        name: {"description": z.description, "aliases": list(z.aliases)}
        for name, z in zones.items()
    }


def write_atomic(path: Path, zones: dict[str, Zone]) -> None:
    """Write zones.json atomically; on failure `path` keeps its previous content."""
    dest_dir = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dest_dir, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(_serialize(zones), f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


@contextmanager
def exclusive_lock(lock_path: Path):
    """Blocking exclusive cross-process lock on `lock_path`.

    On Windows `msvcrt.locking` gives up after ~10 s, so the contention error is retried; any other error is raised.
    """
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if sys.platform == "win32":
            import errno
            import msvcrt

            contended_errno = getattr(errno, "EDEADLOCK", None)
            os.lseek(fd, 0, os.SEEK_SET)
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                    break
                except OSError as e:
                    if contended_errno is not None and e.errno == contended_errno:
                        # Still contended after msvcrt's own ~10 s retry.
                        continue
                    raise  # real failure: retrying will not fix it
            try:
                yield
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
