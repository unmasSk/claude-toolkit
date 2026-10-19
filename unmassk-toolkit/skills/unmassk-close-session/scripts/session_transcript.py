#!/usr/bin/env python3
"""Prepare everything the close-session agent has to read, in one file.

Why this is a script and not a paragraph of instructions: described in
prose it gets reinvented every time, the result is not reproducible, and
the agent burns its context building the filter instead of reading the
session.

It writes ONE file with three parts, in this order:

    1. HEADER       -- which session boundary was used and how it was
                       found. Never silent: if the boundary could not be
                       established, it says so in capitals.
    2. COMMITS      -- the first line of EVERY commit since that
                       boundary, in order, whatever kind it is. Taken from
                       git verbatim, because git is exact and the
                       conversation is not.
    3. CONVERSATION -- what the user and Claude said to each other, and
                       nothing else, from every session of this project
                       since the boundary (D-144).

No tool calls, no tool output, no diffs, no subagent reports, no injected
reminders: everything else is already in the commits.

Usage:
    python3 session_transcript.py [--repo PATH] [--transcript PATH]
                                  [--since ISO-UTC] [--out PATH]

Every argument is optional; the defaults are the ordinary case. With
--transcript only that file is read. Works the same on macOS, Linux and
Windows: no path is ever assembled by hand.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import session_records  # noqa: E402  (sibling module, path set just above)

# A close is the only mark git carries for "a session ended here".
_NEXT_MARK = "[NEXT]"

# git says this, and only this, when a repository has no commits yet.
# Every other failure is a failure and must not be read as "nothing here".
_EMPTY_REPO = ("does not have any commits yet", "unknown revision")


def _run(args, cwd):
    proc = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return proc.returncode, proc.stdout, proc.stderr.strip()


def _git_log(args, cwd):
    """`git log` output, or "" for a repository with no commits. Any other
    refusal is raised: "git could not tell me" is not "there is nothing"."""
    code, out, err = _run(["git", "log"] + args, cwd)
    if code == 0:
        return out
    if any(mark in err for mark in _EMPTY_REPO):
        return ""
    raise RuntimeError(f"git log failed in {cwd}: {err or 'no reason given'}")


def _from_git_seconds(raw):
    """The UTC `datetime` of a git epoch-seconds field (`%at`).

    A deliberate copy of `lib/memory/timefmt.from_git_seconds`: importing it
    would cross the `lib/memory/` boundary (tests/memory/test_boundary.py).
    Change `timefmt.py` first and mirror it here. A non-number raises.
    """
    return datetime.fromtimestamp(int(raw), tz=timezone.utc)


def _last_close(repo, held=()):
    """The newest close in history that this session does not hold itself.

    Returns (sha, iso_utc, subject, skipped) — the first three None when
    none is found. A close whose sha starts with one in `held` is this
    session's own earlier close and is skipped, newest first in `skipped`
    as (sha, subject): a redo covers the whole session (D-143). A close
    another window wrote is a boundary like any other (D-144).

    The match is on the SUBJECT only: a note that merely mentions a close
    in its body is not one.
    """
    skipped = []
    for line in _git_log(["--format=%H%x00%at%x00%s"], repo).split("\n"):
        if line.count("\0") != 2:
            continue
        sha, raw_epoch, subject = line.split("\0")
        if not subject.startswith(_NEXT_MARK):
            continue
        if any(sha.startswith(prefix) for prefix in held):
            skipped.append((sha, subject))
            continue
        stamp = _from_git_seconds(raw_epoch).strftime("%Y-%m-%dT%H:%M:%S")
        return sha, stamp, subject, skipped
    return None, None, None, skipped


def _commits(repo, since_sha, since_iso=None):
    """The first line of every commit since the boundary, oldest first.

    With `since_iso` (from --since) the window is that time, not the sha.
    No filtering by kind: a checkpoint, saved code and a note all count.
    """
    if since_iso:
        out = _git_log(["--format=%at%x00%s", "--reverse", "HEAD"], repo)
        rows = (line.partition("\0") for line in out.split("\n") if "\0" in line)
        return [
            subject
            for raw_epoch, _, subject in rows
            if _from_git_seconds(raw_epoch).strftime("%Y-%m-%dT%H:%M:%S") >= since_iso
        ]
    out = _git_log(
        ["--format=%s", "--reverse", f"{since_sha}..HEAD" if since_sha else "HEAD"],
        repo,
    ).strip()
    return out.split("\n") if out else []


def _transcripts(args, repo):
    """Returns (session being closed, every transcript to read, warning), or
    exits non-zero. A wrong path handed over and nothing found where we
    looked are two different failures, and say so."""
    if args.transcript:
        if not os.path.exists(args.transcript):
            sys.exit(f"session_transcript.py: --transcript {args.transcript} does not exist.")
        return args.transcript, [args.transcript], ""
    files, warning = session_records.project_transcripts(repo)
    if not files:
        sys.exit(f"session_transcript.py: {warning}. "
                 "Pass --transcript with the path to the session's .jsonl.")
    return files[-1], files, warning


def _boundary_lines(args, sha, since, subject, skipped):
    lines = []
    if skipped:
        lines.append(
            "skipped:    this session's own earlier close(s), newest first: "
            + "; ".join(f"{close_sha[:12]} {close_subject}" for close_sha, close_subject in skipped)
        )
    if args.since:
        lines.append(f"boundary:   {args.since} (given with --since)")
    elif since:
        # The SHA is what anyone else needs to ask git about the same window.
        lines.append(f"boundary:   {since} — last close: {sha[:12]} {subject}")
    elif skipped:
        lines.append(
            "boundary:   none before this session — every close in this "
            "history is this session's own (skipped above), so everything "
            "below is the whole history and the whole transcript."
        )
    else:
        lines.append(
            "boundary:   NONE FOUND — no close is recorded in this history, so "
            "everything below is the whole history and the whole transcript. "
            "Say so in the context: it may cover more than one session."
        )
    return lines


def _notes(commits, conversation, undated, sessions, closing):
    lines = []
    if sessions and sessions != [session_records.session_id(closing)]:
        lines.append(f"sessions:   {len(sessions)} spoke since the boundary, turns labelled "
                     "by session: " + ", ".join(sessions))
    if not commits:
        lines.append("note:       not one commit since the boundary. Either nothing was "
                     "saved this session or the boundary is wrong — say so in the close.")
    if undated:
        lines.append(f"note:       {undated} entries carried no timestamp and were "
                     "kept regardless — they may predate the boundary")
    if not conversation:
        lines.append("warning:    NOT ONE TURN OF CONVERSATION CAME OUT. Either the "
                     "boundary is wrong or this is the wrong transcript. Do not write "
                     "a close from memory — report this instead.")
    return lines


def _render(header, commits, conversation):
    parts = ["\n".join(header), ""]
    parts.append(f"# COMMITS SINCE THE BOUNDARY — {len(commits)}, oldest first")
    parts.append(
        "# One line each, copied verbatim into the close, below the context. "
        "These come from git and are exact; nothing retyped from the "
        "conversation is."
    )
    parts.extend(commits or ["(none)"])
    parts.append("")
    parts.append(f"# CONVERSATION — {len(conversation)} turn(s), nothing but what was said")
    parts.append("")
    parts.append("\n\n".join(conversation))
    return "\n".join(parts)


def main(argv):
    parser = argparse.ArgumentParser(prog="session_transcript.py")
    parser.add_argument("--repo", default=os.getcwd())
    parser.add_argument("--transcript")
    parser.add_argument("--since", help="ISO UTC, no zone suffix. Overrides the last close.")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    repo = os.path.abspath(args.repo)
    closing, transcripts, warning = _transcripts(args, repo)
    header = [
        "# CLOSE-SESSION INPUT",
        f"repo:       {repo}",
        f"transcript: {closing} ({os.path.getsize(closing):,} bytes raw)",
    ]
    if warning:
        header.append(f"warning:    {warning}")

    sha, since, subject, skipped = _last_close(repo, session_records.held_closes(closing))
    header += _boundary_lines(args, sha, since, subject, skipped)
    commits = _commits(repo, sha, args.since)
    conversation, undated, sessions = session_records.conversation(
        transcripts, args.since or since)
    header += _notes(commits, conversation, undated, sessions, closing)

    # The pid in the name: two runs at once on a fixed path interleaved
    # both sessions in one file with no error [Moriarty, 2026-08-05].
    destination = args.out or os.path.join(
        tempfile.gettempdir(),
        f"close-session-{session_records.session_id(closing)}-{os.getpid()}.txt",
    )
    with open(destination, "w", encoding="utf-8") as handle:
        handle.write(_render(header, commits, conversation))

    print(destination)
    print(
        f"{os.path.getsize(destination):,} bytes · "
        f"{len(commits)} commits · {len(conversation)} turns"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # never a stack trace
        print(f"session_transcript.py: {exc}", file=sys.stderr)
        sys.exit(1)
