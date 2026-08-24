"""
checklist_state.py -- the one per-session file two hooks share without
ever talking to each other directly (docs/plan/casillas-por-programa.md).

`hooks/skill-checklist-inject.py` (PostToolUse on the Skill tool) WRITES
which process skill loaded and which checklist boxes it declares. Later,
`hooks/checklist-gate.py` (Stop) READS that same file to know what must
exist on the task board before the session is allowed to close, and
writes back only the block counter (protection 2, see module docstring
of checklist-gate.py). Neither hook imports the other; this module is
the only contract between them.

File: <project_root>/.claude/.unmassk/session-checklists/<session_id>.json
    {
        "session_id": "...",
        "skills": [{"skill": "unmassk-flow", "boxes": ["...", ...]}, ...],
        "block_count": 0
    }

Resets naturally on /clear: a new session_id means a new, absent file --
both hooks start from the same empty state together (docs/plan, "Riesgo
tecnico": "el registro de la pieza 2 se guarda POR SESION para que ambos
lados se reseteen juntos").

Concurrency: every read-modify-write of this file MUST happen inside
`locked()` -- without it, two concurrent Skill loads (flow + audit) each
read the same content, each appended their own entry, and whichever
save_registry() call landed last silently discarded the other's. Same
class of lost-update race that `git_helpers.file_lock()` closes
elsewhere in this codebase.
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

# Every dash glyph the model might type in place of the manifest's own
# em dash (U+2014) -- en dash (U+2013), hyphen (U+2010), minus sign
# (U+2212) -- folded to plain ASCII '-' before any box-vs-task-subject
# comparison. A byte-exact comparison rejects real, completed work the
# instant Claude types a different (but visually identical) dash.
_DASH_VARIANTS = "—–‐−"
_DASH_TRANSLATION = str.maketrans({ch: "-" for ch in _DASH_VARIANTS})
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_box_text(value) -> str:
    """Canonical form for comparing a checklist box's declared text
    against a task board subject -- the ONE shared function both hooks
    must run their text through. NFKD-decomposes then drops every
    combining diacritic ('Cafe'/'Café'/'CAFE' must all match), case-folds
    (not `lower()` -- correct for non-ASCII), folds every dash variant to
    ASCII '-', collapses repeated whitespace, strips. Better to accept a
    cosmetic difference than to block real, completed work over one.
    Non-string input normalizes to "" (never raises).

    Duplicates `lib/memory/textnorm.py::normalize_text` on purpose, NOT
    imported from there: this file lives outside `lib/memory/`, which
    imports nothing outside it and nothing outside it imports back in
    (`test_boundary.py`) -- do not "deduplicate" these two without
    re-reading that boundary first.
    """
    if not isinstance(value, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    folded_case = without_accents.casefold()
    folded_dashes = folded_case.translate(_DASH_TRANSLATION)
    return _WHITESPACE_RE.sub(" ", folded_dashes).strip()


def _default_registry(session_id: str) -> dict:
    return {"session_id": session_id, "skills": [], "block_count": 0}


def _registry_dir(project_root: str) -> str:
    return os.path.join(project_root, ".claude", ".unmassk", _SUBDIR)


def is_safe_path_component(value) -> bool:
    """True only when `value` is a non-empty string usable as a SINGLE
    path component with no risk of aliasing outside the layout this
    module declares: a session_id of `"foo/../../bar"` would resolve to
    a DIFFERENT file entirely, and both land INSIDE project_root, so
    `verify_path_within_project()`'s "don't escape the repo" guard never
    catches it.
    """
    return (
        isinstance(value, str)
        and value != ""
        and "/" not in value
        and "\\" not in value
        and ".." not in value
    )


def registry_path(project_root: str, session_id: str) -> str:
    """The registry file path for this session, verified to stay inside
    project_root. Safe to call before the file or its directory exists.
    Raises ValueError when session_id isn't a safe single path component
    -- callers already catch this as part of their broad
    "unreadable/unwritable" exception handling.
    """
    if not is_safe_path_component(session_id):
        raise ValueError(f"unsafe session_id for registry path: {session_id!r}")
    path = os.path.join(_registry_dir(project_root), f"{session_id}.json")
    return verify_path_within_project(path, project_root)


def ensure_registry_dir(project_root: str) -> str:
    """Create the registry directory (and its parent .claude/.unmassk/,
    via ensure_runtime_dir) if missing. Returns the verified directory
    path."""
    ensure_runtime_dir(project_root)
    sc_dir = _registry_dir(project_root)
    verify_path_within_project(sc_dir, project_root)
    os.makedirs(sc_dir, exist_ok=True)
    return sc_dir


@contextlib.contextmanager
def locked(project_root: str, session_id: str):
    """Exclusive cross-process lock around a read-modify-write of this
    session's registry. Callers must do their ENTIRE load_registry() ->
    mutate -> save_registry() cycle inside this context -- see the
    module docstring's "Concurrency" section for the race this closes.

    Every failure mode that can happen BEFORE the caller's body runs
    (unsafe/missing session_id, ensure_registry_dir()/registry_path()
    raising, or file_lock() itself failing to even acquire the lock --
    e.g. a read-only session-checklists dir) degrades to yielding
    UNLOCKED rather than raising, so save_registry() can still fail-open
    gracefully instead of losing the entire checklist message. Only a
    lock that WAS acquired guarantees its own release via try/finally;
    an exception raised by the caller's body is never swallowed here.
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
    """Return (data, corrupt).

    data is always a usable dict -- defaulted to empty ({"skills": [],
    "block_count": 0}) both when the file is simply absent (normal: no
    process skill has loaded yet this session) and when it exists but
    cannot be read as the expected shape, INCLUDING when session_id isn't
    a safe path component (registry_path() raises ValueError, caught
    below like any other unreadable-registry case). `corrupt` is what
    tells "absent, normal" apart from "present or malformed, must warn":
    False for absent/no-session_id (stay silent, nothing to check), True
    for anything caller must warn about instead of pretending was empty
    on purpose.
    """
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
    """Best-effort write. Returns True on success, False on any failure --
    callers must treat False as fail-open (a write failure can never turn
    into a block, only into "the counter didn't stick this time"). Callers
    doing a read-modify-write MUST already be inside locked() -- this
    function does not lock by itself, since load+mutate+save is the unit
    that needs to be atomic, not the save alone."""
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
