"""lib/dod_gate_state.py -- shared read/write for stop-dod-gate's
per-session state file (`.claude/.unmassk/stop-dod-gate-state.json`).

Single-session snapshot: the file holds ONE session's dedup/cache/
declaration state at a time -- loading with a session_id that doesn't
match what's currently stored returns a fresh default (never merges two
sessions' data into one file). This is the SAME file the hook already
used for the anti-drip signature and the tree-fingerprint cache; it now
also carries `declared_tests` (Caso 17, 2026-08-22): the list of pytest
node ids the orchestrator has declared as an in-flight test-first
contract for that session, so a red written on purpose (Dante's contract,
before Ultron implements) doesn't get treated as a real regression.

Extracted out of `hooks/stop-dod-gate.py` so `bin/stop-dod-declare.py`
(the `declare`/`clear`/`status` command) can read and write the EXACT
same file without a second, drifting implementation of this I/O. The
hook re-exports these under its original private names (`_state_path`,
`_default_state`, `_load_state`, `_save_state`) for every existing call
site.

Best-effort throughout: any read/write failure degrades silently (a read
failure resets to `default_state()`, a write failure is simply skipped)
-- it can never change a gate decision on its own (D2), matching every
other piece of state this hook keeps.
"""

import json
import os

from git_helpers import open_no_follow_symlink, ensure_runtime_dir, UNMASSK_RUNTIME_DIR

STATE_FILENAME = "stop-dod-gate-state.json"


def state_path(cwd: str) -> str:
    return os.path.join(cwd, UNMASSK_RUNTIME_DIR, STATE_FILENAME)


def default_state(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "last_block_signature": None,
        "warned_empty_suite": False,
        "warned_modules": [],
        "tree_fingerprint": None,
        "cached_decision": None,
        "declared_tests": [],
    }


def load_state(cwd: str, session_id: str) -> dict:
    """Return this session's state, or a fresh one when the stored
    session_id doesn't match (new session) or the file is missing/corrupt.
    Never raises.
    """
    default = default_state(session_id)
    try:
        with open_no_follow_symlink(state_path(cwd), "r") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("session_id") != session_id:
            return default
        warned_modules = data.get("warned_modules")
        tree_fingerprint = data.get("tree_fingerprint")
        cached_decision = data.get("cached_decision")
        declared_tests = data.get("declared_tests")
        return {
            "session_id": session_id,
            "last_block_signature": data.get("last_block_signature"),
            "warned_empty_suite": bool(data.get("warned_empty_suite", False)),
            "warned_modules": list(warned_modules) if isinstance(warned_modules, list) else [],
            "tree_fingerprint": tree_fingerprint if isinstance(tree_fingerprint, str) else None,
            "cached_decision": cached_decision if isinstance(cached_decision, dict) else None,
            "declared_tests": list(declared_tests) if isinstance(declared_tests, list) else [],
        }
    except Exception:
        return default


def save_state(cwd: str, state: dict) -> None:
    """Best-effort persist. A failure here must never surface -- it only
    means the next call re-warns / re-dumps / re-declares instead of
    reusing what was already saved."""
    try:
        runtime_dir = ensure_runtime_dir(cwd)
        path = os.path.join(runtime_dir, STATE_FILENAME)
        with open_no_follow_symlink(path, "w", atomic=True) as f:
            json.dump(state, f)
    except Exception:
        pass
