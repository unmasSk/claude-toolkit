#!/usr/bin/env python3
"""bin/stop-dod-declare.py -- declare, clear, or query the in-flight
test-first contracts that shield hooks/stop-dod-gate.py's Stop-close gate
(Caso 17, 2026-08-22).

Why this exists: this toolkit's own build method is test-first (Dante
writes the contract in red, Ultron implements until green), and the
Stop gate otherwise treats an on-purpose red exactly like a real
regression, blocking session close on every Stop while the
implementation is in flight. This command lets the orchestrator name,
explicitly, which currently-failing pytest node ids are a known
in-flight contract for the current session -- never inferred by the gate
itself.

Usage:
    stop-dod-declare.py declare <test_node_id> [<test_node_id> ...] --session <ID>
    stop-dod-declare.py clear --session <ID>
    stop-dod-declare.py status --session <ID>

`<test_node_id>` is a real pytest node id exactly as it appears in a
`FAILED` line (`<file>::<function>`) -- the gate already parses those
lines for the anti-drip signature, and reuses that same extraction to
compare against what's declared here.

`declare`/`clear` exit 0 on success. `status` prints JSON on stdout with
at least the key `"declared"` -- the list of node ids currently declared
for that session (empty list when none). All three operate on
`os.getcwd()`, the same convention as every other `bin/*.py` script.

State lives in `.claude/.unmassk/stop-dod-gate-state.json` -- the SAME
file the gate already uses for its anti-drip signature and tree-
fingerprint cache, read and written through lib/dod_gate_state.py so
there is exactly one implementation of this I/O, never a second one
drifting from the hook's own. Declarations are scoped per session_id:
declaring under one session and querying/closing under another behaves
as if nothing was ever declared (same single-session-snapshot shape the
state file already had before this command existed).
"""

import argparse
import json
import os
import sys

_BIN_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(_BIN_DIR)
_LIB_DIR = os.path.join(_TOOLKIT_ROOT, "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from encoding_guard import force_utf8_streams  # noqa: E402  (import after sys.path setup)

force_utf8_streams()

from dod_gate_state import load_state, save_state  # noqa: E402


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="stop-dod-declare.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    declare_parser = subparsers.add_parser(
        "declare", help="Declare one or more pytest node ids as an in-flight contract."
    )
    declare_parser.add_argument("test_node_ids", nargs="+", metavar="test_node_id")
    declare_parser.add_argument("--session", required=True)

    clear_parser = subparsers.add_parser(
        "clear", help="Remove every declared node id for this session."
    )
    clear_parser.add_argument("--session", required=True)

    status_parser = subparsers.add_parser(
        "status", help="Print the node ids currently declared for this session as JSON."
    )
    status_parser.add_argument("--session", required=True)

    return parser.parse_args(argv)


def _invalidate_tree_fingerprint_cache(state: dict) -> None:
    """Force the NEXT Stop to run test_command for real instead of
    replaying a cached decision.

    Why this is needed here: this state file lives under the gate's own
    runtime directory (.claude/.unmassk/), which the fingerprint
    computation deliberately EXCLUDES (writing the gate's own bookkeeping
    must never look like "the project changed"). That means declaring or
    clearing a contract, on its own, never changes the tree fingerprint --
    so without this, a Stop that already cached a BLOCK decision before
    `declare` ran would keep replaying that stale block forever, never
    re-evaluating it against the declaration that was just added. Any
    change to the declared set invalidates whatever decision was cached
    before it, since that decision was computed without knowing about it."""
    state["tree_fingerprint"] = None
    state["cached_decision"] = None


def _cmd_declare(cwd: str, session_id: str, node_ids: list) -> int:
    state = load_state(cwd, session_id)
    declared = state.get("declared_tests", [])
    for node_id in node_ids:
        if node_id not in declared:
            declared.append(node_id)
    state["declared_tests"] = declared
    _invalidate_tree_fingerprint_cache(state)
    save_state(cwd, state)
    return 0


def _cmd_clear(cwd: str, session_id: str) -> int:
    state = load_state(cwd, session_id)
    if state.get("declared_tests"):
        _invalidate_tree_fingerprint_cache(state)
    state["declared_tests"] = []
    save_state(cwd, state)
    return 0


def _cmd_status(cwd: str, session_id: str) -> int:
    state = load_state(cwd, session_id)
    json.dump({"declared": state.get("declared_tests", [])}, sys.stdout)
    sys.stdout.flush()
    return 0


def main(argv) -> int:
    args = _parse_args(argv)
    cwd = os.getcwd()

    if args.command == "declare":
        return _cmd_declare(cwd, args.session, args.test_node_ids)
    if args.command == "clear":
        return _cmd_clear(cwd, args.session)
    if args.command == "status":
        return _cmd_status(cwd, args.session)

    # argparse's `required=True` on the subparsers already rejects any
    # other value before main() is ever reached -- this is unreachable in
    # practice, kept only so the function has an explicit, documented exit.
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
