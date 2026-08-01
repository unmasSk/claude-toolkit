"""incidents -- the toolkit's own failure channel.

WHY THIS EXISTS
---------------
When a toolkit hook breaks, it writes to stderr and exits 0. On `Stop`,
`PreToolUse` and `PreCompact` that stream goes to the debug log and is never
read (measured: 0 of 2506 on `Stop`). One hook stayed dead for ~4 months
because of exactly that. This module is the replacement: an incident is
written the moment it happens, and surfaced on the next `UserPromptSubmit`
-- the only channel proven to reach the model mid-session (1445/1445).

THE TOOLKIT IS INSTALLED IN EVERY PROJECT, SO THE LOG IS GLOBAL
---------------------------------------------------------------
The failure happens wherever the owner is working (some web app, some other
repo); the fix happens in the toolkit repo. A log written into the failing
project's `.claude/` would never be seen from the toolkit repo, so the log
lives under the USER's home (`~/.claude/.unmassk/`) and the alert is emitted
in whatever project is open at the time. Each record keeps the project it
came from -- the same fault appearing in several projects is a signal, not
noise -- but the fingerprint deliberately EXCLUDES the project, or the same
fault would be re-announced once per project the owner opens.

THE LOCATION MUST BE ACTIONABLE, WHICH MEANS NOT THE CACHE PATH
---------------------------------------------------------------
What actually executes is the plugin CACHE copy
(`~/.claude/plugins/cache/.../<version>/hooks/x.py`). Showing that path
invites editing the cache, which is discarded on the next upgrade and never
reaches git. Every location is therefore reported RELATIVE to the plugin
root (`hooks/x.py:214`) -- what the owner greps for in his own repo -- and
carries the plugin version, because a repo checked out at another version
may not have that line at all.

CONTRACT
--------
- Immediate. Never batched, never deferred to the next boot.
- No counters. An identical incident is announced ONCE per session and then
  stays quiet; it is never tallied ("this happened 7 times" is forbidden).
- Noise counts as an incident too: a repeated, non-actionable warning is
  reported through this same channel.
- FAIL-OPEN, ABSOLUTE. Nothing in this module may ever break a hook. Every
  public function swallows everything, including BaseException, and returns
  a neutral value. An error reporter that kills a session is worse than no
  reporter at all.

All `git_helpers` / `parsing` / `version` imports are DEFERRED into function
bodies on purpose: this is a stably-named module (cached in `sys.modules`
after its first import), and a module-level import evaluated inside a test's
stub window would freeze to the stub forever.
"""

import hashlib
import json
import os
from datetime import datetime, timezone

INCIDENTS_LOG_NAME = "incidents.jsonl"
INCIDENTS_STATE_NAME = "incidents-state.json"
ROTATED_SUFFIX = ".1"

# Bounded. On overflow the file is rotated to `.1` (never silently stopped):
# two files, ~1 MB total, worst case.
MAX_LOG_BYTES = 512 * 1024
# Per-session fingerprint memory. Far above any plausible number of distinct
# faults in one session; exists so a pathological session cannot grow the
# state file without bound.
MAX_SEEN_FINGERPRINTS = 200
MAX_FIELD_CHARS = 300
MAX_LINE_CHARS = 240
DEFAULT_SHOW_LIMIT = 3

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Escape hatch for a test that means to exercise this module for real.
FORCE_ENV_VAR = "UNMASSK_INCIDENTS_FORCE"


def _suppressed() -> bool:
    """True while running under pytest -- the channel stays inert.

    The suite drives the toolkit's failure paths ON PURPOSE (malformed
    stdin, simulated write errors, unwritable directories). Those are not
    incidents, and `tests/conftest.py::run_cmd` merges the whole os.environ
    into every hook subprocess, so `PYTEST_CURRENT_TEST` reaches the hook
    and this check works from inside a spawned hook too.

    Without this, every suite run injected fabricated failures into the
    owner's live channel and he would chase a "FALLO en
    hooks/pre-task-recall.py:170 — JSONDecodeError" that is a fixture doing
    its job. That is exactly the non-actionable NOISE this channel exists to
    eliminate, so producing it would defeat the whole point. Verified: 5
    such fake entries had already accumulated in ~/.claude/.unmassk/ before
    this guard existed.

    A test that genuinely needs the real behavior sets UNMASSK_INCIDENTS_FORCE.
    """
    if os.environ.get(FORCE_ENV_VAR):
        return False
    return "PYTEST_CURRENT_TEST" in os.environ


def _plugin_version() -> str:
    """The version of the code that produced the incident ("?" if unknown)."""
    try:
        from version import VERSION

        return str(VERSION)
    except Exception:
        return "?"


def _clean(text: object, limit: int = MAX_FIELD_CHARS) -> str:
    """One safe, single-line, bounded field.

    Reuses the canonical sanitizer (control bytes, terminal escapes,
    memory-data fence markers) rather than growing a second one; falls back
    to a minimal strip only if `parsing` cannot be imported at all.
    """
    value = "" if text is None else str(text)
    try:
        from parsing import sanitize_trailer_value

        value = sanitize_trailer_value(value)
    except Exception:
        value = " ".join(value.split())
    return value[:limit]


def _relative_to_toolkit(path: str) -> str | None:
    """`hooks/x.py` for a file inside the running plugin, else None.

    Works identically whether the plugin runs from the cache or straight
    from the repo working tree, because the reference point is THIS file's
    own plugin root -- the failing file always lives in the same copy.
    """
    try:
        real = os.path.realpath(path)
        root = os.path.realpath(_PLUGIN_ROOT)
        if real == root or not real.startswith(root + os.sep):
            return None
        return os.path.relpath(real, root).replace(os.sep, "/")
    except Exception:
        return None


def _location(exc: BaseException) -> str | None:
    """`file:line` deduced from the traceback -- never hand-written.

    Picks the DEEPEST frame that belongs to the toolkit: the deepest frame
    overall is often stdlib (`json/decoder.py`), which is not where the fix
    goes. Falls back to the deepest frame's absolute path when the whole
    traceback is outside the plugin.
    """
    try:
        import traceback

        frames = traceback.extract_tb(exc.__traceback__)
        if not frames:
            return None
        chosen: tuple[str, int] | None = None
        for frame in frames:
            rel = _relative_to_toolkit(frame.filename)
            if rel is not None:
                chosen = (rel, frame.lineno or 0)
        if chosen is None:
            last = frames[-1]
            chosen = (_clean(last.filename, 160), last.lineno or 0)
        return f"{chosen[0]}:{chosen[1]}"
    except Exception:
        return None


def _session_key() -> str:
    """Identity of the current session, for the once-per-session rule.

    `CLAUDE_CODE_SESSION_ID` when the harness exports it. Otherwise the
    parent PID: every hook is a short-lived child of the one long-lived
    Claude Code process, so its ppid is stable for the whole session and
    differs between sessions -- good enough for a dedup key, and it degrades
    to "dedup within this process tree" in a plain shell.
    """
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if session and session.strip():
        return session.strip()[:120]
    return f"ppid:{os.getppid()}"


def _fingerprint(source: str, exc_type: str, location: str | None, message: str) -> str:
    """Short hash of source + exception type + location.

    The project is deliberately NOT part of it (see module docstring), and
    neither is the caller's message when an exception is present -- the same
    bug reached from two call sites with slightly different wording is one
    incident, not two.
    """
    material = "|".join([source, exc_type, location or "", message])
    return hashlib.sha1(material.encode("utf-8", "replace")).hexdigest()[:12]


def _global_runtime_dir() -> tuple[str, str]:
    """(~/.claude, ~/.claude/.unmassk) -- created if needed. Raises freely."""
    from git_helpers import verify_path_within_project

    claude_home = os.path.join(os.path.expanduser("~"), ".claude")
    runtime_dir = os.path.join(claude_home, ".unmassk")
    verify_path_within_project(runtime_dir, claude_home)
    os.makedirs(runtime_dir, exist_ok=True)
    return claude_home, runtime_dir


def _paths() -> tuple[str, str, str]:
    """(claude_home, log_path, state_path), all verified. Raises freely."""
    from git_helpers import verify_path_within_project

    claude_home, runtime_dir = _global_runtime_dir()
    log_path = os.path.join(runtime_dir, INCIDENTS_LOG_NAME)
    state_path = os.path.join(runtime_dir, INCIDENTS_STATE_NAME)
    verify_path_within_project(log_path, claude_home)
    verify_path_within_project(state_path, claude_home)
    return claude_home, log_path, state_path


def _read_state(state_path: str) -> dict:
    """Current dedup/display cursor state; {} when absent or unreadable."""
    from git_helpers import open_no_follow_symlink

    try:
        with open_no_follow_symlink(state_path, "r") as f:
            loaded = json.load(f)
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_state(state_path: str, state: dict) -> None:
    """Replace the state file atomically. Raises freely."""
    from git_helpers import open_no_follow_symlink

    with open_no_follow_symlink(state_path, "w", atomic=True) as f:
        f.write(json.dumps(state, sort_keys=True) + "\n")


def _rotate_if_needed(log_path: str, state: dict) -> None:
    """Keep the log bounded without ever going silent.

    At the cap the current file becomes `<log>.1` and a fresh one starts.
    The display cursor is reset in the same breath, since line numbers in
    the new file mean nothing to the old cursor. Called under the lock.
    """
    try:
        if os.path.getsize(log_path) < MAX_LOG_BYTES:
            return
    except OSError:
        return
    os.replace(log_path, log_path + ROTATED_SUFFIX)
    state["shown_lines"] = 0


def _current_project() -> str:
    """Absolute path of the project the incident happened in."""
    try:
        from git_helpers import run_git

        code, root = run_git(["rev-parse", "--show-toplevel"])
        if code == 0 and root:
            return os.path.realpath(root)
    except Exception:
        pass
    return os.path.realpath(os.getcwd())


def _build_record(source: str, message: str, exc: BaseException | None,
                  location: str | None, fingerprint: str, session: str) -> dict:
    """The one JSON line describing this incident."""
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "version": _plugin_version(),
        "source": _clean(source, 80),
        "message": _clean(message),
        "exc_type": type(exc).__name__ if exc is not None else "",
        "exc_message": _clean(exc) if exc is not None else "",
        "location": location or "",
        "fingerprint": fingerprint,
        "project": _current_project(),
        "session": session,
    }


def _report(source: str, message: str, exc: BaseException | None) -> None:
    """Append one incident unless this session already reported it.

    Raises freely -- report_incident() owns the fail-open wrapping. The lock
    covers the whole read-state -> dedup -> append -> write-state cycle:
    several hooks (and several subagents) can report at the same instant,
    which is the lost-update race `file_lock()` exists for.
    """
    from git_helpers import file_lock, open_no_follow_symlink

    _, log_path, state_path = _paths()
    location = _location(exc) if exc is not None else None
    exc_type = type(exc).__name__ if exc is not None else ""
    fingerprint = _fingerprint(source, exc_type, location,
                               "" if exc is not None else _clean(message))
    session = _session_key()

    with file_lock(log_path):
        state = _read_state(state_path)
        if state.get("session") != session:
            # New session: the once-per-session memory starts empty. The
            # display cursor is NOT reset -- an incident written after the
            # last message of a dead session must still get its one airing.
            state = {"session": session, "seen": [],
                     "shown_lines": state.get("shown_lines", 0)}
        seen = state.get("seen")
        if not isinstance(seen, list):
            seen = []
        if fingerprint in seen:
            return  # said once already this session; never repeated, never counted
        _rotate_if_needed(log_path, state)
        record = _build_record(source, message, exc, location, fingerprint, session)
        with open_no_follow_symlink(log_path, "a") as f:
            f.write(json.dumps(record) + "\n")
        state["seen"] = (seen + [fingerprint])[-MAX_SEEN_FINGERPRINTS:]
        _write_state(state_path, state)


def report_incident(source: str, message: str, *, exc: BaseException | None = None) -> None:
    """Record that the toolkit failed at `source`, once per session.

    `source` is the subsystem ("recall-subagente", "claude-md-write"), not a
    location: the location is deduced from `exc`'s traceback, so it can
    never drift out of date the way a hand-written one does. `message` is
    the human context ("memory injection for subagents lost"). Pass `exc`
    whenever there is one -- without it there is no file:line to show.

    Never raises, never returns anything, never blocks the caller.
    """
    try:
        if _suppressed():
            return
        _report(source, message, exc)
    except BaseException:  # fail-open, absolute -- see module docstring
        pass


def _shorten(text: object, limit: int) -> str:
    """Bound a field, cutting the MIDDLE rather than the tail.

    Exception messages are usually paths, and a path's tail (the filename
    that actually failed) carries more information than its middle. Cutting
    the end would throw away the useful half.
    """
    value = str(text or "")
    if len(value) <= limit:
        return value
    if limit <= 1:
        return value[:limit]
    keep = limit - 1
    head = keep // 2
    return value[:head] + "…" + value[len(value) - (keep - head):]


def format_incident_line(record: dict, same_project: bool = True) -> str:
    """The single actionable line the owner reads mid-session.

    `[toolkit v1.24.0] FALLO en hooks/pre-merge-gate.py:214 — KeyError: 'tool_input'`

    The project is appended only when the incident came from a DIFFERENT
    project than the one currently open -- otherwise it is noise, and when
    it differs, omitting it would be actively misleading.

    Budgeting is explicit and ordered, because a naive final-line truncation
    silently ate exactly the two fields that must never be lost: the version,
    the location and the project marker are laid down FIRST and always
    survive; only the exception text and the caller's context are squeezed
    to whatever room is left.
    """
    version = record.get("version") or "?"
    where = _shorten(record.get("location") or record.get("source") or "?", 90)
    prefix = f"[toolkit v{version}] FALLO en {where} — "

    suffix = ""
    if not same_project:
        project = str(record.get("project") or "").rstrip(os.sep)
        if project:
            suffix = f" (en {_shorten(os.path.basename(project), 40)})"

    exc_type = record.get("exc_type") or ""
    context = str(record.get("message") or "")
    if exc_type:
        detail = f"{exc_type}: {_shorten(record.get('exc_message'), 110)}".strip()
        if context:
            detail = f"{detail} ({_shorten(context, 70)})"
    else:
        detail = _shorten(context, 180) or "sin detalle"

    budget = max(40, MAX_LINE_CHARS - len(prefix) - len(suffix))
    return prefix + _shorten(detail, budget) + suffix


def _same_project(record: dict, current_path: str | None) -> bool:
    """Whether this incident came from the project that is open right now."""
    project = record.get("project")
    if not project or not current_path:
        return True
    try:
        here = os.path.realpath(current_path)
        there = os.path.realpath(project)
        return here == there or here.startswith(there + os.sep)
    except Exception:
        return True


def _drain(current_path: str | None, limit: int) -> list[str]:
    """Read the unshown incidents and advance the cursor. Raises freely."""
    from git_helpers import file_lock, open_no_follow_symlink

    _, log_path, state_path = _paths()
    with file_lock(log_path):
        state = _read_state(state_path)
        with open_no_follow_symlink(log_path, "r") as f:
            raw_lines = [ln for ln in f.read().splitlines() if ln.strip()]
        shown = state.get("shown_lines")
        if not isinstance(shown, int) or shown < 0 or shown > len(raw_lines):
            shown = 0  # rotated, truncated or corrupted cursor -- start over
        pending = raw_lines[shown:]
        if not pending:
            return []

        out: list[str] = []
        for raw in pending[:limit]:
            try:
                record = json.loads(raw)
            except ValueError:
                continue
            if isinstance(record, dict):
                out.append(format_incident_line(record, _same_project(record, current_path)))
        remaining = len(pending) - len(pending[:limit])
        if remaining > 0:
            out.append(f"[toolkit] y {remaining} incidencia(s) más sin mostrar — {log_path}")

        state["shown_lines"] = shown + len(pending[:limit])
        _write_state(state_path, state)
        return out


def drain_incidents(current_path: str | None = None,
                    limit: int = DEFAULT_SHOW_LIMIT) -> list[str]:
    """Formatted lines for every incident not yet shown; marks them shown.

    At most `limit` incidents are detailed per call; any surplus is stated
    in one line and detailed on the NEXT call, so nothing is ever lost and
    nothing is ever repeated. Returns [] on any failure -- the emitting hook
    must behave identically whether this works or not.
    """
    try:
        if _suppressed():
            return []  # never consume/advance the owner's real cursor from a test
        # Cheap existence probe FIRST, with no directory creation and no
        # lock: the normal case is "the toolkit has never failed", and that
        # case must cost one stat() on every single user message, nothing
        # more. The verified paths are re-derived inside _drain().
        probe = os.path.join(os.path.expanduser("~"), ".claude", ".unmassk",
                             INCIDENTS_LOG_NAME)
        if not os.path.exists(probe):
            return []
        return _drain(current_path, max(1, limit))
    except BaseException:  # fail-open, absolute -- see module docstring
        return []
