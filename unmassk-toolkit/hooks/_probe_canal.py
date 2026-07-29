#!/usr/bin/env python3
"""_probe_canal -- TEMPORARY diagnostic probe of the hook delivery channel.

WHAT THIS IS
------------
An instrument, not a feature. Phase 0 of docs/plan/fix-canal-de-entrega-memoria.md.
It measures two things and judges nothing:

  A) what each hook event actually DELIVERS to a hook on stdin (passive
     record: which top-level keys arrive, and presence/type of the fields
     that matter -- never their content), plus the three things without
     which the result table cannot be read: `stop_hook_active` (upstream
     issue #54360, the Stop-loop bug), the client identity of this machine
     (upstream issue #49063, additionalContext works in the CLI but not in
     the VSCode extension), and a per-event invocation tally;
  B) which hook OUTPUT channel actually REACHES the model's context, by
     emitting the same per-invocation nonce through every candidate channel
     under a distinct label. Whichever labels show up in the model's context
     next turn are the channels that work. Zero interpretation needed.

There is no business logic here, no detector, no gate, and no blocking
decision. It is deliberately short-lived: Task 5 of the plan removes it.

CHANNEL LABELS EMITTED (same nonce, one label per channel)
----------------------------------------------------------
  PROBE-STDERR-<nonce>   stderr, exit 0
  PROBE-STDOUT-<nonce>   raw stdout text (see the caveat below)
  PROBE-ADDCTX-<nonce>   hookSpecificOutput.additionalContext
  PROBE-SYSMSG-<nonce>   systemMessage

Caveat on PROBE-STDOUT (documented harness behavior, not a choice): when a
hook's stdout parses as JSON, Claude Code honors the structured fields and
DISCARDS the raw stdout text. So "plain text on stdout" and "a JSON object
on stdout" cannot both be exercised by the same invocation. Since unknown
top-level keys in hook JSON are silently ignored, the raw-stdout marker
rides along as the ignored key `probeRawStdout`: it is invisible when the
harness consumes the JSON structurally, and visible whenever the harness
surfaces the raw stdout text instead. Reading it therefore means "the raw
stdout text reached the context", never "additionalContext worked".
Measuring plain-text-only stdout (no JSON at all) needs a second, separate
pass -- it is NOT covered by this one.

NOT emitted on this pass, on purpose: `decision: "block"` and
`permissionDecision: "deny"`. The blocking channel interrupts the user's
turn and is probed later, under control.

FAIL-OPEN CONTRACT (absolute)
-----------------------------
Any failure at any point -- unreadable stdin, malformed JSON, a payload that
is not an object, a full disk, a permission error, a missing lib import --
results in a silent exit 0. A diagnostic instrument must never be the reason
a session breaks. Every stage is independently wrapped so that a failure to
write the log still lets the markers be emitted, and vice versa.

Exit codes:
  0: Always.
"""

import json
import os
import secrets
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
try:
    # Wrapped (unlike the other hooks, which import this bare): the fail-open
    # contract above starts at the very first import, not at main().
    from encoding_guard import force_utf8_streams

    force_utf8_streams()
except BaseException:  # fail-open, see module docstring
    pass


PROBE_LOG_NAME = "probe-canal.jsonl"
# Per-event invocation tally, kept in its own tiny file so it stays truthful
# even after the .jsonl hits its size cap and stops accepting lines. "Stop
# fired 40 times and no marker was ever seen" and "Stop never fired at all"
# are opposite conclusions; without this counter they look identical.
PROBE_COUNTS_NAME = "probe-canal-counts.json"
NO_EVENT_KEY = "<no-event>"
# Once the log reaches this size the probe stops appending. A sentinel file
# (PROBE_LOG_NAME + CAPPED_SUFFIX) marks that the final "log is full" line
# was already written, so the notice is written exactly once instead of on
# every subsequent invocation.
MAX_LOG_BYTES = 2 * 1024 * 1024
CAPPED_SUFFIX = ".capped"

NONCE_BYTES = 4  # 8 hex characters
RAW_STDOUT_KEY = "probeRawStdout"

# Fields whose presence/type answers "what does this event actually hand a
# hook?". Their CONTENT is never recorded: last_assistant_message and the
# transcript can be huge and can carry the user's own text.
INSPECTED_FIELDS = (
    "transcript_path",
    "last_assistant_message",
    "session_id",
    "cwd",
    "tool_name",
    # Upstream issue #54360 (open): stop_hook_active does not propagate
    # correctly when system messages are interleaved, and the Stop hook ends
    # up firing in a loop. Its VALUE is recorded (it is a bool, not content)
    # so "the channel never arrives" can be told apart from "the hook looped".
    "stop_hook_active",
)

# Environment identity. Upstream issue #49063: additionalContext is NOT
# injected in the VSCode extension but does work in the CLI -- so a result
# table is uninterpretable, and not comparable against another setup, unless
# each line says which client produced it. This machine is precisely the
# ambiguous case (CLAUDE_CODE_ENTRYPOINT=cli with TERM_PROGRAM=vscode).
# Values are recorded for the two identity variables; the bridge variables
# are recorded as presence only.
ENV_VALUE_VARS = ("CLAUDE_CODE_ENTRYPOINT", "TERM_PROGRAM")
ENV_PRESENCE_VARS = ("CLAUDE_CODE_SSE_PORT", "CLAUDE_CODE_BRIDGE_SESSION_ID")

# Bounds on the recorded key list. The payload comes from the harness, not
# from an adversary -- this exists so one anomalous payload can never blow
# past the file size cap in a single line, nothing more.
MAX_KEYS = 100
MAX_KEY_LEN = 80


def _read_stdin() -> tuple[object, str]:
    """Read stdin and parse it without assuming any shape.

    Returns (payload, status) where status is one of: "object",
    "non-object", "invalid-json", "empty", "stdin-unreadable". `payload` is
    the parsed value only when the status is "object" or "non-object".
    """
    try:
        raw = sys.stdin.read()
    except BaseException:  # fail-open
        return None, "stdin-unreadable"
    if not raw or not raw.strip():
        return None, "empty"
    try:
        payload = json.loads(raw)
    except (ValueError, RecursionError):
        return None, "invalid-json"
    return payload, "object" if isinstance(payload, dict) else "non-object"


def _describe_field(payload: dict, key: str) -> dict:
    """Presence and type of one field -- never its value.

    `len` is recorded for strings because "present but empty" and "present
    with 40 KB in it" are different answers to the question this probe
    exists to settle, and a length reveals nothing about the content.
    """
    if key not in payload:
        return {"present": False}
    value = payload[key]
    info: dict = {"present": True, "type": type(value).__name__}
    if isinstance(value, bool):
        # A bool carries no user content -- record it outright. This is what
        # makes stop_hook_active (issue #54360) readable.
        info["value"] = value
    elif isinstance(value, str):
        info["len"] = len(value)
    return info


def _env_info() -> dict:
    """Which client produced this line (issue #49063) -- see ENV_VALUE_VARS."""
    info: dict = {v: os.environ.get(v) for v in ENV_VALUE_VARS}
    info.update({v: v in os.environ for v in ENV_PRESENCE_VARS})
    return info


def _transcript_info(payload: dict) -> dict | None:
    """Whether the transcript file exists and how big it is (metadata only)."""
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not path:
        return None
    info: dict = {"exists": False}
    try:
        info["exists"] = os.path.isfile(path)
        if info["exists"]:
            info["size_bytes"] = os.path.getsize(path)
    except OSError as e:
        info["stat_error"] = type(e).__name__
    return info


def _top_level_keys(payload: dict) -> dict:
    """Bounded list of the payload's first-level keys."""
    keys = [str(k)[:MAX_KEY_LEN] for k in list(payload.keys())[:MAX_KEYS]]
    result: dict = {"keys": keys}
    if len(payload) > MAX_KEYS:
        result["keys_omitted"] = len(payload) - MAX_KEYS
    return result


def _event_name(payload: object) -> str | None:
    """The event name as it actually arrives, or None if it does not."""
    if not isinstance(payload, dict):
        return None
    value = payload.get("hook_event_name")
    if isinstance(value, str) and value.strip():
        return value.strip()[:MAX_KEY_LEN]
    return None


def _plan_channels(event_name: str | None) -> list[str]:
    """Which channels this invocation emits the nonce through.

    additionalContext is only emitted when the event name is known, because
    hookSpecificOutput.hookEventName is required by the harness schema and
    there is nothing truthful to put in it otherwise.
    """
    channels = ["stderr", "stdout.raw_text", "systemMessage"]
    if event_name:
        channels.append("hookSpecificOutput.additionalContext")
    return channels


def _build_record(payload: object, status: str, event_name: str | None,
                  nonce: str, channels: list[str],
                  event_seq: int | None, counts: dict) -> dict:
    """Assemble the one JSON line describing this invocation."""
    record: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "stdin_status": status,
        "hook_event_name": event_name,
        "nonce": nonce,
        # "attempted": the record is written before the markers are emitted,
        # so a channel listed here is what the probe set out to emit.
        "channels_attempted": channels,
        # This invocation's ordinal for its own event, plus a snapshot of
        # every event's tally -- so the LAST line alone answers "how many
        # times did each event fire?" without reading the whole file.
        "event_seq": event_seq,
        "counts": counts,
        "env": _env_info(),
    }
    if isinstance(payload, dict):
        record.update(_top_level_keys(payload))
        record["fields"] = {k: _describe_field(payload, k) for k in INSPECTED_FIELDS}
        transcript = _transcript_info(payload)
        if transcript is not None:
            record["transcript"] = transcript
    else:
        record["keys"] = None
        if status == "non-object":
            record["payload_type"] = type(payload).__name__
    return record


def _runtime_paths() -> tuple[str, str] | None:
    """(project_root, .claude/.unmassk/) -- resolved ONCE per invocation.

    Deferred lib import (module-level would put a second import outside the
    guarded block at the top of this file). Both the counter and the log need
    these, and `run_git` spawns a subprocess -- on PostToolUse this hook runs
    on every single tool call, so resolving it twice would double that cost
    for nothing. Raises freely -- main() owns the fail-open wrapping.
    """
    from git_helpers import ensure_runtime_dir, run_git

    code, root = run_git(["rev-parse", "--show-toplevel"])
    if code != 0 or not root:
        return None
    return root, ensure_runtime_dir(root)


def _bump_event_count(paths: tuple[str, str], event_name: str | None) -> tuple[int, dict]:
    """Increment this event's tally and return (this invocation's ordinal, all tallies).

    Serialized with the repo's existing `file_lock()` rather than a
    hand-rolled guard: this is a read-modify-write, and SubagentStop can
    genuinely fire concurrently for several subagents at once, which is
    exactly the lost-update race that helper exists for. The lock is held
    only for a sub-millisecond read + atomic replace of a file well under
    1 KB, and POSIX flock is released by the kernel if the process dies
    holding it, so a crashed probe cannot wedge later hooks.
    """
    from git_helpers import file_lock, open_no_follow_symlink, verify_path_within_project

    root, runtime_dir = paths
    counts_path = os.path.join(runtime_dir, PROBE_COUNTS_NAME)
    verify_path_within_project(counts_path, root)
    key = event_name or NO_EVENT_KEY

    with file_lock(counts_path):
        counts: dict = {}
        try:
            with open_no_follow_symlink(counts_path, "r") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                # Drop anything that is not a plain int: a corrupted or
                # hand-edited file must not propagate a bad type into the
                # arithmetic below (and bool is an int subclass, so exclude it).
                counts = {
                    k: v for k, v in loaded.items()
                    if isinstance(v, int) and not isinstance(v, bool)
                }
        except (OSError, ValueError):
            counts = {}  # absent or unreadable: start the tally fresh
        counts[key] = counts.get(key, 0) + 1
        with open_no_follow_symlink(counts_path, "w", atomic=True) as f:
            f.write(json.dumps(counts, sort_keys=True) + "\n")
        return counts[key], counts


def _append_record(paths: tuple[str, str], record: dict) -> None:
    """Append one JSON line to .claude/.unmassk/probe-canal.jsonl.

    Raises freely -- main() owns the fail-open wrapping.
    """
    from git_helpers import open_no_follow_symlink, verify_path_within_project

    root, runtime_dir = paths
    log_path = os.path.join(runtime_dir, PROBE_LOG_NAME)
    verify_path_within_project(log_path, root)
    capped_path = log_path + CAPPED_SUFFIX

    try:
        size = os.path.getsize(log_path)
    except OSError:
        size = 0

    at_cap = size >= MAX_LOG_BYTES
    if at_cap:
        if os.path.exists(capped_path):
            return  # notice already written; stop growing the file
        record = {
            "ts": record["ts"],
            "probe_log_full": True,
            "max_bytes": MAX_LOG_BYTES,
            "note": "size cap reached -- no further lines will be written",
        }

    with open_no_follow_symlink(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")

    if at_cap:
        verify_path_within_project(capped_path, root)
        with open_no_follow_symlink(capped_path, "w") as f:
            f.write(f"{PROBE_LOG_NAME} reached {MAX_LOG_BYTES} bytes; probe stopped appending.\n")


def _emit_markers(nonce: str, event_name: str | None) -> None:
    """Emit the same nonce through every candidate channel, one label each."""
    print(f"PROBE-STDERR-{nonce}", file=sys.stderr)
    out: dict = {
        "systemMessage": f"PROBE-SYSMSG-{nonce}",
        # Ignored by the harness whenever the JSON is consumed structurally;
        # visible only if the raw stdout text itself reaches the context.
        RAW_STDOUT_KEY: f"PROBE-STDOUT-{nonce}",
    }
    if event_name:
        out["hookSpecificOutput"] = {
            "hookEventName": event_name,
            "additionalContext": f"PROBE-ADDCTX-{nonce}",
        }
    print(json.dumps(out))


def main() -> None:
    """Record what arrived, then emit the nonce through every channel.

    Every stage is wrapped independently: a counter that cannot be bumped
    must not cost us the log line, a log that cannot be written must not
    cost us the markers, and markers that cannot be emitted must not cost
    us the record. The markers are the half that answers the question, so
    they are emitted last and are never gated on anything above them.
    """
    payload, status = _read_stdin()
    event_name = _event_name(payload)
    nonce = secrets.token_hex(NONCE_BYTES)
    channels = _plan_channels(event_name)

    paths = None
    try:
        paths = _runtime_paths()
    except BaseException:  # fail-open
        paths = None

    event_seq: int | None = None
    counts: dict = {}
    if paths is not None:
        try:
            event_seq, counts = _bump_event_count(paths, event_name)
        except BaseException:  # fail-open
            event_seq, counts = None, {}

    if paths is not None:
        try:
            _append_record(paths, _build_record(
                payload, status, event_name, nonce, channels, event_seq, counts))
        except BaseException:  # fail-open
            pass
    try:
        _emit_markers(nonce, event_name)
    except BaseException:  # fail-open
        pass


if __name__ == "__main__":
    try:
        main()
    except BaseException:  # fail-open, see module docstring
        pass
    sys.exit(0)
