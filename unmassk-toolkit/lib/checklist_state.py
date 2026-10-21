"""Per-session checklist registry shared by `skill-checklist-inject.py` (writer) and `checklist-gate.py` (reader).

File: <project_root>/.claude/.unmassk/session-checklists/<session_id>.json; every read-modify-write runs inside `locked()`.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import unicodedata

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from git_helpers import (  # noqa: E402  (import after sys.path mutation)
    ensure_runtime_dir,
    file_lock,
    open_no_follow_symlink,
    verify_path_within_project,
)

_SUBDIR = "session-checklists"

# Dash variants folded to ASCII '-' before comparing box text with task subjects.
_DASH_VARIANTS = "—–‐−"
_DASH_TRANSLATION = str.maketrans({ch: "-" for ch in _DASH_VARIANTS})
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_box_text(value) -> str:
    """Lowercase, accent-free, dash- and whitespace-folded form of a box text; "" for non-strings.

    Kept separate from `lib/memory/textnorm.py` on purpose: `lib/memory/` has an import boundary.
    """
    if not isinstance(value, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    folded_case = without_accents.casefold()
    folded_dashes = folded_case.translate(_DASH_TRANSLATION)
    return _WHITESPACE_RE.sub(" ", folded_dashes).strip()


def is_valid_procedures(value) -> bool:
    """True when `value` is a valid `procedures` map: name -> {"selector": str, optional "boxes": list[str]}."""
    if not isinstance(value, dict) or not value:
        return False
    for name, spec in value.items():
        if not isinstance(name, str) or not isinstance(spec, dict):
            return False
        selector = spec.get("selector")
        if not isinstance(selector, str) or not selector.strip():
            return False
        if "boxes" in spec:
            boxes = spec["boxes"]
            if not isinstance(boxes, list) or not all(isinstance(b, str) for b in boxes):
                return False
    return True


def resolve_project_root(cwd: str) -> str:
    """Nearest ancestor of `cwd` holding `.git` (filesystem walk, no process), or `cwd`; never raises."""
    try:
        current = os.path.realpath(cwd)
        while True:
            if os.path.exists(os.path.join(current, ".git")):
                return current
            parent = os.path.dirname(current)
            if parent == current:
                return cwd
            current = parent
    except Exception:
        return cwd


def _default_registry(session_id: str) -> dict:
    return {"session_id": session_id, "skills": [], "block_count": 0}


def _registry_dir(project_root: str) -> str:
    return os.path.join(project_root, ".claude", ".unmassk", _SUBDIR)


def is_safe_path_component(value) -> bool:
    """True when `value` is a non-empty single path component (no separators, no `..`)."""
    return (
        isinstance(value, str)
        and value != ""
        and "/" not in value
        and "\\" not in value
        and ".." not in value
    )


def registry_path(project_root: str, session_id: str) -> str:
    """Registry file path for this session, verified inside project_root; ValueError on an unsafe session_id."""
    if not is_safe_path_component(session_id):
        raise ValueError(f"unsafe session_id for registry path: {session_id!r}")
    path = os.path.join(_registry_dir(project_root), f"{session_id}.json")
    return verify_path_within_project(path, project_root)


def ensure_registry_dir(project_root: str) -> str:
    """Create the registry directory if missing and return its verified path."""
    ensure_runtime_dir(project_root)
    sc_dir = _registry_dir(project_root)
    verify_path_within_project(sc_dir, project_root)
    os.makedirs(sc_dir, exist_ok=True)
    return sc_dir


@contextlib.contextmanager
def locked(project_root: str, session_id: str):
    """Exclusive lock around a load -> mutate -> save cycle of this session's registry.

    Any failure before the body runs yields unlocked instead of raising.
    """
    if not is_safe_path_component(session_id):
        yield
        return
    lock_cm = None
    try:
        ensure_registry_dir(project_root)
        path = registry_path(project_root, session_id)
        lock_cm = file_lock(path)
        lock_cm.__enter__()
    except Exception:
        yield
        return
    try:
        yield
    finally:
        lock_cm.__exit__(None, None, None)


def load_registry(project_root: str, session_id: str) -> tuple[dict, bool]:
    """Return (data, corrupt): data is always usable; corrupt is True when the file exists but is unreadable or malformed."""
    if not session_id:
        return _default_registry(session_id), False
    try:
        path = registry_path(project_root, session_id)
    except Exception:
        return _default_registry(session_id), True
    try:
        with open_no_follow_symlink(path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return _default_registry(session_id), False
    except Exception:
        return _default_registry(session_id), True

    if not isinstance(data, dict) or not isinstance(data.get("skills"), list):
        return _default_registry(session_id), True

    data.setdefault("block_count", 0)
    if not isinstance(data.get("block_count"), int):
        data["block_count"] = 0
    data.setdefault("session_id", session_id)
    return data, False


def save_registry(project_root: str, session_id: str, data: dict) -> bool:
    """Best-effort write; False on any failure. Callers must hold `locked()`."""
    if not session_id:
        return False
    try:
        ensure_registry_dir(project_root)
        path = registry_path(project_root, session_id)
        with open_no_follow_symlink(
            path, "w", reject_hardlinks=True, atomic=True
        ) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
