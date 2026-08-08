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
                       boundary, in order, whatever kind it is: a note, a
                       checkpoint, saved code, anything. Taken from git
                       verbatim, because git is exact and the
                       conversation is not.
    3. CONVERSATION -- what the user and Claude said to each other, and
                       nothing else.

What comes out of the transcript, and this is the whole rule: **the
conversation, and only the conversation**. No tool calls, no tool output,
no diffs, no subagent reports, no injected reminders. The close is a
summary of what was said; everything else is already in the commits, and
on a real session the machinery is most of the file.

Usage:
    python3 session_transcript.py [--repo PATH] [--transcript PATH]
                                  [--since ISO-UTC] [--out PATH]

Every argument is optional; the defaults are the ordinary case. Works the
same on macOS, Linux and Windows: no path is ever assembled by hand.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

# A close is the only mark git carries for "a session ended here".
_NEXT_MARK = "[NEXT]"

# How recently another transcript must have been touched for a second
# open session to be worth naming.
_RECENT_SECONDS = 1800

# Machinery the harness injects: reminders, subagent reports,
# slash-command echoes. Only WELL-FORMED spans of these are removed, and
# nothing is ever dropped for merely starting with one of the names: in a
# project whose subject is its own machinery, a real message can open
# with "<system-reminder> why does this fire on every message". Whole
# entries the harness injected are caught upstream by their own flag.
_INJECTED = (
    "system-reminder",
    "task-notification",
    "local-command-caveat",
    "local-command-stdout",
    "local-command-stderr",
    "command-name",
    "command-message",
    "command-args",
    "user-prompt-submit-hook",
    "bash-input",
    "bash-stdout",
    "bash-stderr",
)

# The same machinery also arrives glued to the end of a real message.
_INLINE_TAGS = re.compile(
    r"<(" + "|".join(_INJECTED) + r")\b.*?</\1>",
    re.DOTALL,
)


# git says this, and only this, when a repository has no commits yet.
# Every other failure is a failure and must not be read as "nothing here".
_EMPTY_REPO = ("does not have any commits yet", "unknown revision")


def _run(args, cwd):
    proc = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return proc.returncode, proc.stdout, proc.stderr.strip()


def _git_log(args, cwd):
    """`git log` output, or "" for a repository with no commits.

    Anything else that git refuses is raised, never turned into an empty
    answer: "git could not tell me" and "there is nothing" look the same
    downstream, and reporting the second when the first happened writes a
    close that lies about the whole session.
    """
    code, out, err = _run(["git", "log"] + args, cwd)
    if code == 0:
        return out
    if any(mark in err for mark in _EMPTY_REPO):
        return ""
    raise RuntimeError(f"git log failed in {cwd}: {err or 'no reason given'}")


def _projects_root():
    """Claude Code keeps its transcripts under the user's home folder.
    `expanduser` resolves that on Windows, macOS and Linux alike -- the
    separators come from `os.path.join`, never typed in.
    """
    return os.path.join(os.path.expanduser("~"), ".claude", "projects")


def _slug(path):
    """One folder per project, named after its full path with every
    character that is not a letter or a digit turned into a dash. That
    covers `/` on macOS and Linux and both `\\` and the drive colon on
    Windows, without a branch per platform.
    """
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(path))


def _newest_transcript(repo):
    """Returns (path, note). The note is never empty when something is
    off: a wrong guess here silently closes the wrong session.
    """
    root = _projects_root()
    if not os.path.isdir(root):
        return None, f"{root} does not exist — is this Claude Code?"

    wanted = _slug(repo)
    folder = os.path.join(root, wanted)
    if not os.path.isdir(folder):
        others = sorted(os.listdir(root))
        return None, (
            f"no transcript folder for this project (expected {wanted} "
            f"inside {root}, which holds {len(others)} others such as "
            f"{others[:3]})"
        )

    files = [
        os.path.join(folder, name)
        for name in os.listdir(folder)
        if name.endswith(".jsonl")
    ]
    if not files:
        return None, f"{folder} holds no .jsonl transcript"

    files.sort(key=os.path.getmtime, reverse=True)
    newest = files[0]

    # Two windows open on the same project is ordinary, and this cannot
    # tell which one is asking: it only knows which file was written to
    # last. A session that spent a quarter of an hour thinking loses the
    # race to a busier window, and the close comes out about somebody
    # else's day with nothing saying so [Moriarty, 2026-08-05].
    #
    # So the comparison is against NOW, not against the winner: any other
    # transcript with recent activity is named, and so is the age of the
    # one chosen. A reader can then see it picked a file that has been
    # cold for twenty minutes.
    now = time.time()
    age = now - os.path.getmtime(newest)
    rivals = [
        other for other in files[1:] if now - os.path.getmtime(other) < _RECENT_SECONDS
    ]
    if rivals:
        return newest, (
            "MORE THAN ONE SESSION IS OPEN ON THIS PROJECT — "
            f"the one chosen was last written to {int(age // 60)} min ago; "
            f"{len(rivals)} other(s) active within the last "
            f"{_RECENT_SECONDS // 60} min: "
            + ", ".join(os.path.basename(r) for r in rivals)
            + ". Confirm this is the session being closed."
        )
    return newest, ""


def _from_git_seconds(raw):
    """The UTC `datetime` of a git epoch-seconds field (`%at`).

    This is a DELIBERATE, in-file copy of
    `lib/memory/timefmt.from_git_seconds` -- not a fifth chance to forget
    it exists. That function is the real owner of "how this toolkit reads
    a git date"; this script cannot import it because it lives outside
    `lib/memory/`, and `lib/memory/` is a declared zone with a boundary
    the toolkit enforces on purpose: the memory system has to be
    deletable whole without breaking anything else that depends on it,
    and a skill importing its internals would break that. The test that
    would catch an import here (and did, once) is
    `tests/memory/test_boundary.py::test_no_file_outside_the_allowed_zone_imports_lib_memory`.

    Do NOT "clean this up" by importing `timefmt` instead -- that crosses
    the boundary right back. If the conversion ever needs to change, change
    it in `timefmt.py` first (it is the source of truth) and mirror the
    change here by hand; the two are intentionally decoupled, not
    accidentally duplicated.

    Raises `ValueError` as-is if `raw` is not a number, same as
    `timefmt.from_git_seconds`: a date that cannot be read must not come
    back as `None` or silently "as if nothing happened" -- that is
    indistinguishable from "no activity", the exact silence this exists to
    avoid.
    """
    return datetime.fromtimestamp(int(raw), tz=timezone.utc)


def _last_close(repo):
    """The boundary of "this session" is the last close, because git has
    no idea what a session is and that mark is the only thing a close
    leaves behind. Returns (sha, iso_utc, subject) or three Nones.

    The match is on the SUBJECT and nowhere else. Asking git to search
    would also search the body, so a note that merely *mentions* the
    close would pass itself off as one and cut the session in the wrong
    place -- silently.

    A session that died without closing leaves no mark, so the next close
    picks up both and nothing is lost. That is intended, not a bug.
    """
    # `%at` (segundos-epoch), no `%aI` (ISO-8601 con sufijo `Z` en huso
    # cero, que `datetime.fromisoformat` de Python 3.10 no sabe leer)
    # [decision del propietario, 2026-08-08 -- ver `_from_git_seconds`
    # arriba para el porque esta conversion vive aqui duplicada en vez de
    # importada de `lib/memory/timefmt.from_git_seconds`].
    for line in _git_log(["--format=%H%x00%at%x00%s"], repo).split("\n"):
        if line.count("\0") != 2:
            continue
        sha, raw_epoch, subject = line.split("\0")
        if not subject.startswith(_NEXT_MARK):
            continue
        stamp = _from_git_seconds(raw_epoch)
        return sha, stamp.strftime("%Y-%m-%dT%H:%M:%S"), subject
    return None, None, None


def _commits(repo, since_sha):
    """The first line of every commit since the boundary, oldest first.

    No filtering by kind on purpose: a checkpoint, saved code and a note
    all count. If checkpoints were squashed, git only has the squash and
    that is what shows up -- which is the right answer, not a loss.
    """
    out = _git_log(
        ["--format=%s", "--reverse", f"{since_sha}..HEAD" if since_sha else "HEAD"],
        repo,
    ).strip()
    return out.split("\n") if out else []


def _said(entry):
    """What a person or Claude actually said in this entry, if anything."""
    message = entry.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    if not isinstance(content, list):
        return []

    out = []
    for chunk in content:
        # thinking, tool_use and tool_result all fall out here.
        if not isinstance(chunk, dict) or chunk.get("type") != "text":
            continue
        # Only well-formed injected spans are removed. Nothing is dropped
        # for merely *starting* with one of those names: in a project that
        # talks about its own machinery, a real message opening with
        # "<system-reminder> why does this fire on every message" is
        # ordinary prose, and dropping it deleted the user's complaint
        # whole [Moriarty, 2026-08-05]. Injected entries are already
        # caught upstream by their own flag; leaking a stray tag is noise
        # a reader can see, while deleting a message is loss nobody can.
        text = _INLINE_TAGS.sub("", chunk.get("text") or "").strip()
        if text:
            out.append(text)
    return out


def _conversation(transcript, since_iso):
    """Returns (turns, undated) — the second is how many entries carried no
    timestamp. They are kept: an empty timestamp sorts below every
    boundary, so dropping them by comparison would delete real words from
    a session that has no way of noticing.
    """
    out = []
    undated = 0
    with open(transcript, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") not in ("user", "assistant"):
                continue
            # A subagent's own conversation is not this conversation.
            if entry.get("isSidechain"):
                continue
            # The harness flags everything it injects. Measured on a real
            # session: 47 such entries carried no tag at all -- whole skill
            # files, hook feedback -- and went in looking like something the
            # user had typed, 365k characters of it. The flag catches them
            # all; the tag names below catch only the ones that announce
            # themselves.
            if entry.get("isMeta"):
                continue
            stamp = entry.get("timestamp") or ""
            if since_iso and stamp and stamp < since_iso:
                continue
            said = _said(entry)
            if not said:
                continue
            if not stamp:
                undated += 1
                stamp = "(no timestamp)"
            who = (entry.get("message") or {}).get("role", entry["type"])
            out.append(f"=== {who} {stamp}\n" + "\n".join(said))
    return out, undated


def main(argv):
    parser = argparse.ArgumentParser(prog="session_transcript.py")
    parser.add_argument("--repo", default=os.getcwd())
    parser.add_argument("--transcript")
    parser.add_argument("--since", help="ISO UTC, no zone suffix. Overrides the last close.")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    repo = os.path.abspath(args.repo)

    # Two different failures, and they must not share one message: a path
    # that was handed over and is wrong is not the same as nothing found
    # where we looked. Blaming the wrong cause sends people hunting in
    # the wrong place.
    warning = ""
    if args.transcript:
        transcript = args.transcript
        if not os.path.exists(transcript):
            print(
                f"session_transcript.py: --transcript {transcript} does not exist.",
                file=sys.stderr,
            )
            return 1
    else:
        transcript, warning = _newest_transcript(repo)
        if not transcript:
            print(
                f"session_transcript.py: {warning}. "
                "Pass --transcript with the path to the session's .jsonl.",
                file=sys.stderr,
            )
            return 1

    header = [
        "# CLOSE-SESSION INPUT",
        f"repo:       {repo}",
        f"transcript: {transcript} ({os.path.getsize(transcript):,} bytes raw)",
    ]
    if warning:
        header.append(f"warning:    {warning}")

    sha, since, subject = _last_close(repo)
    if args.since:
        since = args.since
        header.append(f"boundary:   {since} (given with --since)")
    elif since:
        # The SHA is printed as well as the date: it is what anyone else
        # needs to ask git the same question about the same window.
        header.append(f"boundary:   {since} — last close: {sha[:12]} {subject}")
    else:
        header.append(
            "boundary:   NONE FOUND — no close is recorded in this history, so "
            "everything below is the whole history and the whole transcript. "
            "Say so in the context: it may cover more than one session."
        )

    commits = _commits(repo, sha)
    conversation, undated = _conversation(transcript, since)

    if undated:
        header.append(
            f"note:       {undated} entries carried no timestamp and were "
            "kept regardless — they may predate the boundary"
        )
    if not conversation:
        header.append(
            "warning:    NOT ONE TURN OF CONVERSATION CAME OUT. Either the "
            "boundary is wrong or this is the wrong transcript. Do not write "
            "a close from memory — report this instead."
        )

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

    # El nombre lleva el pid: con un destino fijo, dos pasadas a la vez
    # escribian sobre el mismo fichero y lo dejaban con las dos sesiones
    # entremezcladas, sin error por ninguna parte -- 10 de 15 veces
    # [Moriarty, 2026-08-05].
    destination = args.out or os.path.join(
        tempfile.gettempdir(),
        "close-session-"
        + os.path.basename(transcript).replace(".jsonl", "")
        + f"-{os.getpid()}.txt",
    )
    with open(destination, "w", encoding="utf-8") as handle:
        handle.write("\n".join(parts))

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
