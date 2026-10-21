"""Read memory notes from git history into `Note` objects; the single reader of `git log`."""

import dataclasses
import time
from pathlib import Path

import format
import gitcmd
import timefmt
from model import Note

_FIELD_SEP = "\x1f"
_MAX_ATTEMPTS = 3  # first try + up to 2 retries
_RETRY_DELAY_SECONDS = 0.05

# `%at` (epoch seconds): Python 3.10 `fromisoformat` cannot read `%aI`'s `Z` suffix.
_LOG_FORMAT = f"--pretty=format:%H{_FIELD_SEP}%at{_FIELD_SEP}%B"

# git's stderr for `git log` on a branch with no commits yet: a valid state, not a failure.
UNBORN_BRANCH_MARKER = "does not have any commits yet"


def _is_unborn_branch(stderr: str) -> bool:
    """True if `stderr` is git's message for a branch with no commits yet."""
    return UNBORN_BRANCH_MARKER in stderr


def run_git_log(pretty_format: str, extra_args: tuple[str, ...] = ()) -> str:
    """Run `git log -z` in the cwd and return its stdout, retrying transient failures.

    A branch with no commits returns "". A failure that persists raises RuntimeError.
    """
    args = ["log", "-z", pretty_format, *extra_args]
    result = None
    for attempt in range(_MAX_ATTEMPTS):
        result = gitcmd.run(args, cwd=Path.cwd(), timeout=gitcmd.GIT_TIMEOUT)
        if result.returncode == 0:
            return result.stdout
        if _is_unborn_branch(result.stderr):
            return ""
        if attempt < _MAX_ATTEMPTS - 1:
            time.sleep(_RETRY_DELAY_SECONDS)
    raise RuntimeError(
        f"git log fallo tras {_MAX_ATTEMPTS} intentos: {result.stderr}"
    )


def _git_log(extra_args: tuple[str, ...]) -> str:
    """`run_git_log()` with the `Note` format."""
    return run_git_log(_LOG_FORMAT, extra_args)


def _exists_at_head(relpath: str, root: Path) -> bool:
    """True if `relpath` exists in HEAD (decided by return code, not stderr text)."""
    result = gitcmd.run(
        ["cat-file", "-e", f"HEAD:{relpath}"], cwd=root, timeout=gitcmd.GIT_TIMEOUT
    )
    return result.returncode == 0


def show_file_at_head(relpath: str, root: Path) -> str:
    """Committed content of `relpath` at HEAD; "" if absent, RuntimeError if `git show` fails."""
    if not _exists_at_head(relpath, root):
        return ""
    result = gitcmd.run(["show", f"HEAD:{relpath}"], cwd=root, timeout=gitcmd.GIT_TIMEOUT)
    if result.returncode == 0:
        return result.stdout
    raise RuntimeError(f"git show HEAD:{relpath} fallo en {root}: {result.stderr}")


def _parse_records(raw_stdout: str) -> tuple[tuple[Note, str], ...]:
    return tuple((note, text) for _sha, note, text in _parse_records_with_sha(raw_stdout))


def _parse_records_with_sha(raw_stdout: str) -> tuple[tuple[str, Note, str], ...]:
    """Parse `_git_log` output into `(sha, Note, text)`, skipping commits that are not notes."""
    parsed: list[tuple[str, Note, str]] = []
    for record in raw_stdout.split("\0"):
        if not record:
            continue
        commit_hash, author_date, raw_message = record.split(_FIELD_SEP, 2)
        text = raw_message.rstrip("\n")
        note = format.parse_message(text)
        if note is None:
            continue
        note = dataclasses.replace(note, timestamp=timefmt.from_git_seconds(author_date))
        parsed.append((commit_hash, note, text))
    return tuple(parsed)


def _all_notes() -> tuple[tuple[Note, str], ...]:
    return _parse_records(_git_log(()))


def by_id(note_id: str) -> Note | None:
    """The note whose id matches `note_id` case-insensitively, or None."""
    target = note_id.lower()
    for note, _text in _all_notes():
        if note.id.lower() == target:
            return note
    return None


def commits_by_id(note_id: str) -> tuple[tuple[str, Note], ...]:
    """`(sha, note)` for every commit carrying exactly `note_id`, newest first."""
    return tuple(
        (sha, note)
        for sha, note, _text in _parse_records_with_sha(_git_log(()))
        if note.id == note_id
    )


def by_zone(zone1: str | None, zone2: str | None) -> tuple[Note, ...]:
    """Notes matching `zone1` and `zone2`; a None argument does not filter."""
    return tuple(
        note
        for note, _text in _all_notes()
        if (zone1 is None or note.zone1 == zone1)
        and (zone2 is None or note.zone2 == zone2)
    )


def by_word(word: str) -> tuple[tuple[Note, tuple[str, ...]], ...]:
    """Notes whose text contains `word` (case-insensitive), with the matching lines."""
    needle = word.lower()
    results: list[tuple[Note, tuple[str, ...]]] = []
    for note, text in _all_notes():
        matched_lines = tuple(line for line in text.split("\n") if needle in line.lower())
        if matched_lines:
            results.append((note, matched_lines))
    return tuple(results)


def by_file(path: Path) -> tuple[Note, ...]:
    """Notes whose commit touched `path`."""
    raw_stdout = _git_log(("--", str(path)))
    return tuple(note for note, _text in _parse_records(raw_stdout))
