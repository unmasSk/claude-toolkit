#!/usr/bin/env python3
"""
Stop hook -- the program-set checklist gate.

Compares this session's registry (written by `skill-checklist-inject.py`
when a process skill loaded, see lib/checklist_state.py) against the real
task board. Blocks "done" only when a box that program declared is
missing from the board, or present but still pending/in_progress.

Board location (docs/plan/casillas-por-programa.md, "Riesgo tecnico"):
`(CLAUDE_CONFIG_DIR or ~/.claude)/tasks/(CLAUDE_CODE_TASK_LIST_ID or
session_id)/<N>.json`, one file per task, each `{id, subject, status, ...}`.
Writes there are not atomic and the directory key can legitimately differ
from session_id (team setups) -- both are treated as ordinary, expected
conditions below, never as an internal error.

Four protections, all fail-open, none optional (each closes a documented
real failure -- see the module docstring of casillas-por-programa.md):
1. `stop_hook_active` is NEVER re-blocked -- issue #55754's loop burned
   50 minutes of a real session re-triggering its own Stop hook.
2. At most 2 blocks per session (counted in the same per-session
   registry); after that, warn and let the session close.
3. Read-only, always: no subprocess, no network, no git call of any kind.
   R-009 measured 704 orphaned processes and D-046 measured this gate's
   own predecessor eating half a million tokens of context by re-running
   a test command on every Stop.
4. Any error, corrupt registry, corrupt board JSON, or missing board
   directory: fail-open AND say so on stderr -- tdd-guard blocked every
   session in total silence the day its own model dependency vanished.
   A single unreadable task file never invalidates the others (House,
   2026-08-23: the board's writes are per-file, not atomic).

I/O:
  stdin:  Stop event JSON -- session_id, cwd, stop_hook_active.
  stdout: {"decision":"block","reason":"..."} when blocking; empty when
          allowing (silent when no process skill loaded this session, or
          everything is satisfied).
  exit:   always 0.
"""

import json
import os
import sys

# ── Shared lib ────────────────────────────────────────────────────────────
_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(os.path.dirname(_HOOKS_DIR), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from encoding_guard import force_utf8_streams  # noqa: E402
force_utf8_streams()

from git_helpers import open_no_follow_symlink  # noqa: E402  (protection 3: file reads only, no git/subprocess helpers)
import checklist_state  # noqa: E402

_STDIN_READ_LIMIT = 1_048_576  # 1 MiB, same ceiling as this repo's other hooks.
_MAX_BLOCKS_PER_SESSION = 2
_SATISFIED_STATUS = "completed"


def _expected_boxes(registry: dict) -> list[str]:
    """Flatten every declared skill's boxes into one ordered, deduplicated
    list -- a session can load more than one process skill (e.g. Flow,
    then close-session), and both sets of boxes must hold."""
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in registry.get("skills", []):
        for box in entry.get("boxes", []):
            if isinstance(box, str) and box not in seen:
                seen.add(box)
                ordered.append(box)
    return ordered


def _board_dir(cwd: str, session_id: str) -> str | None:
    """The board directory path, or None when the task-list key (env
    override, or session_id as fallback) isn't a single safe path
    component -- never build a path from something that could alias
    outside the intended `tasks/<key>/` layout (Cerberus/Argus, 2026-08-24,
    same class of finding fixed in lib/checklist_state.py for session_id).
    Callers must treat None exactly like "directory does not exist"
    (fail-open, protection 4)."""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    task_list_id = os.environ.get("CLAUDE_CODE_TASK_LIST_ID") or session_id
    if not checklist_state.is_safe_path_component(task_list_id):
        return None
    return os.path.join(config_dir, "tasks", task_list_id)


def _read_board_tasks(board_dir: str) -> tuple[dict[str, list[str]], list[str]]:
    """Return (normalized_subject -> every status seen for it,
    unreadable_filenames). Multiple tasks can normalize to the same
    subject -- ALL of their statuses are kept, never collapsed to
    "whichever file sorted last alphabetically overwrote the dict entry"
    (Moriarty, 2026-08-24: reproduced -- an earlier duplicate file with
    status completed was silently shadowed by a later-sorting pending
    duplicate, and the box wrongly showed as open). A task file that
    can't be read or doesn't have the expected shape is skipped and named
    in the second list -- it never invalidates the other files (fail-open
    PER FILE, protection 4)."""
    tasks: dict[str, list[str]] = {}
    broken: list[str] = []
    try:
        names = sorted(n for n in os.listdir(board_dir) if n.endswith(".json"))
    except OSError:
        return tasks, broken

    for name in names:
        path = os.path.join(board_dir, name)
        try:
            with open_no_follow_symlink(path, "r") as f:
                data = json.load(f)
            subject = data.get("subject")
            status = data.get("status")
            if isinstance(subject, str) and isinstance(status, str):
                key = checklist_state.normalize_box_text(subject)
                tasks.setdefault(key, []).append(status)
            else:
                broken.append(name)
        except Exception:
            broken.append(name)
    return tasks, broken


def _violations(expected: list[str], tasks: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """Return (missing, open_items) among `expected`, comparing NORMALIZED
    text on both sides (Moriarty, 2026-08-24: a byte-exact comparison
    rejected real completed work over a different dash glyph or a
    differently-composed accent -- the normal path, not an edge case; see
    checklist_state.normalize_box_text). `missing` = no task on the board
    normalizes to this subject at all. `open_items` = at least one
    matching task exists, but NONE of them is completed -- a box is
    satisfied the moment ANY matching task is completed, regardless of
    how many other duplicates or their order."""
    missing, open_items = [], []
    for box in expected:
        statuses = tasks.get(checklist_state.normalize_box_text(box))
        if not statuses:
            missing.append(box)
        elif _SATISFIED_STATUS not in statuses:
            open_items.append(box)
    return missing, open_items


def _build_reason(missing: list[str], open_items: list[str]) -> str:
    lines = ["Program-set checklist boxes are not satisfied yet:"]
    if missing:
        lines.append("Missing from the task board (create them verbatim):")
        lines.extend(f"  - {b}" for b in missing)
    if open_items:
        lines.append("On the board but not completed (pending/in_progress):")
        lines.extend(f"  - {b}" for b in open_items)
    lines.append("Create/finish these before closing the session.")
    return "\n".join(lines)


def _emit_block(reason: str) -> None:
    json.dump({"decision": "block", "reason": reason}, sys.stdout, ensure_ascii=False)
    sys.stdout.flush()


def _block_or_allow(cwd: str, session_id: str, missing: list[str], open_items: list[str]) -> None:
    """Protection 2 (max 2 blocks/session) + protection 3 (race): reload
    the registry FRESH, INSIDE the lock, and persist the incremented
    counter before ever emitting a block -- `registry` as loaded at the
    top of main() may be stale by now, and reusing it here would silently
    clobber a concurrent write the same way two concurrent inject.py calls
    did (Cerberus/Argus, 2026-08-24; see lib/checklist_state.py docstring).
    Exits the process directly at every terminal point."""
    with checklist_state.locked(cwd, session_id):
        fresh_registry, _fresh_corrupt = checklist_state.load_registry(cwd, session_id)
        block_count = fresh_registry.get("block_count", 0)
        if block_count >= _MAX_BLOCKS_PER_SESSION:
            sys.stderr.write(
                "checklist-gate: already blocked this session the maximum "
                f"{_MAX_BLOCKS_PER_SESSION} time(s) -- allowing close with boxes still "
                f"open: {', '.join(missing + open_items)}\n"
            )
            sys.exit(0)

        fresh_registry["block_count"] = block_count + 1
        if not checklist_state.save_registry(cwd, session_id, fresh_registry):
            # The anti-loop counter (protection 2) only works if it's
            # durable -- blocking anyway here, with a counter that never
            # advances on disk, reproduces issue #55754's exact loop
            # (every future Stop re-blocks forever). A single skipped
            # block is the safer failure.
            sys.stderr.write(
                "checklist-gate: could not persist the block counter -- "
                "allowing close this turn (a blocks-forever loop is worse "
                "than one skipped block)\n"
            )
            sys.exit(0)

    _emit_block(_build_reason(missing, open_items))


def _apply_gate(cwd: str, session_id: str, registry: dict) -> None:
    """Everything from 'is there anything to check' through emitting a
    block. Exits the process directly at every terminal point, same
    control-flow style as main()."""
    expected = _expected_boxes(registry)
    if not expected:
        sys.exit(0)  # silence: no process skill loaded this session

    board_dir = _board_dir(cwd, session_id)
    if board_dir is None or not os.path.isdir(board_dir):
        sys.stderr.write(
            f"checklist-gate: task board directory not found or unresolvable "
            f"({board_dir!r}); the team's task-list key may differ from "
            "session_id, or be unsafe -- allowing close\n"
        )
        sys.exit(0)

    tasks, broken = _read_board_tasks(board_dir)
    if broken:
        sys.stderr.write(
            f"checklist-gate: {len(broken)} task file(s) on the board were "
            f"unreadable and skipped ({', '.join(broken)}); the rest were still checked\n"
        )

    missing, open_items = _violations(expected, tasks)
    if not missing and not open_items:
        sys.exit(0)  # clean pass, nothing to say

    _block_or_allow(cwd, session_id, missing, open_items)


def main() -> None:
    try:
        raw = sys.stdin.read(_STDIN_READ_LIMIT)
        hook_input = json.loads(raw) if raw.strip() else {}
        if not isinstance(hook_input, dict):
            # Valid JSON but not an object (null, a list, a bare number...)
            # -- every hook_input.get() below would raise AttributeError
            # and crash this process with a non-zero exit, violating this
            # hook's own "exit: always 0" contract (Cerberus/Argus,
            # 2026-08-24: reproduced with stdin `null`, `[1,2,3]`, `42`).
            hook_input = {}
    except Exception as e:
        sys.stderr.write(f"checklist-gate: unreadable stdin, allowing close ({e!r})\n")
        sys.exit(0)

    # Protection 1: never re-block a Stop that already blocked itself.
    if hook_input.get("stop_hook_active") is True:
        sys.exit(0)

    session_id = hook_input.get("session_id")
    cwd = hook_input.get("cwd") or os.getcwd()

    try:
        registry, corrupt = checklist_state.load_registry(cwd, session_id)
        if corrupt:
            sys.stderr.write(
                "checklist-gate: session-checklists registry was unreadable, "
                "allowing close (fail-open)\n"
            )
        _apply_gate(cwd, session_id, registry)

    except Exception as e:
        sys.stderr.write(f"checklist-gate: unexpected error, allowing close ({e!r})\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
