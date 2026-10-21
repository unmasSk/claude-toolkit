"""Read and write the session-close context (the Next) as an empty git commit.

No lock, no validator, no index: it is a standalone empty commit.
"""

import dataclasses

import format
import gitcmd
import timefmt
from model import ContextNote, WriteResult
from query import run_git_log

# NUL between commits (`-z`), `\x1f` between fields; the raw message (`%B`) goes last.
_FIELD_SEP = "\x1f"
# `%at` (epoch seconds): Python 3.10 `fromisoformat` cannot read `%aI`'s `Z` suffix.
_LOG_FORMAT = f"--pretty=format:%at{_FIELD_SEP}%B"


def write(ctx: ContextNote) -> WriteResult:
    """Write `ctx` as an empty commit."""
    message = format.build_context_message(ctx)
    result = gitcmd.commit_empty(message)

    if result.returncode != 0:
        return WriteResult(ok=False, note_id=None, rejections=(), git_error=result.stderr)
    return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)


def latest(all_refs: bool = True) -> ContextNote | None:
    """The most recent session-close context with its real commit timestamp, or `None` if none exists.

    Raises `RuntimeError` on a real `git log` failure; a branch with no commits returns `None`.
    """
    # `--all` finds a close made on another branch or machine; `--date-order` puts the newest first.
    # `all_refs=False` when the remote is not this project's, so another project's close is not read.
    extra = ("--all", "--date-order") if all_refs else ("--date-order",)
    raw_stdout = run_git_log(_LOG_FORMAT, extra)

    for record in raw_stdout.split("\0"):
        if not record:
            continue
        author_date, raw_message = record.split(_FIELD_SEP, 1)
        parsed = format.parse_context_message(raw_message.rstrip("\n"))
        if parsed is not None:
            return dataclasses.replace(parsed, timestamp=timefmt.from_git_seconds(author_date))
    return None
