"""Disposable repo, the real `gitmem next`, and the script run as the close agent runs it."""

import os
import re
import sys
import uuid
from collections import namedtuple

from conftest import BIN_DIR, SOURCE_ROOT, git_cmd, run_cmd
from session_transcript_records_helpers import (
    DAY, assistant, base_record, tool_answer, tool_call, write_transcript,
)

SCRIPT = os.path.join(
    SOURCE_ROOT, "skills", "unmassk-close-session", "scripts", "session_transcript.py"
)
CLOSE_PROMPT = os.path.join(
    SOURCE_ROOT, "skills", "unmassk-close-session", "references", "close-agent-prompt.md"
)
NEXT_SCRIPT = os.path.join(BIN_DIR, "memory", "next.py")


def _read_close_prompt(pattern):
    with open(CLOSE_PROMPT, encoding="utf-8") as handle:
        found = re.search(pattern, handle.read(), re.DOTALL)
    assert found, f"{pattern!r} not found in {CLOSE_PROMPT}"
    return found.group(1)


def close_prompt_stop_prefix():
    """The header prefix the close agent's prompt says to STOP on."""
    return _read_close_prompt(r"carries a `([^`]+)` line[^.]*STOP")


def close_agent_prompt():
    """The prompt the orchestrator hands the close agent, read from the skill."""
    return _read_close_prompt(r"## THE PROMPT\s*```\n(.*?)\n```")


# ── disposable git repo ─────────────────────────────────────────────────


def _dated(hhmmss):
    stamp = f"{DAY}T{hhmmss}Z"
    return {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git_cmd(["init", "-q", "-b", "main"], str(repo))
    return str(repo)


def commit(repo, subject, hhmmss):
    rc, _, err = git_cmd(["commit", "-q", "--allow-empty", "-m", subject], repo,
                         env=_dated(hhmmss))
    assert rc == 0, err
    rc, sha, err = git_cmd(["rev-parse", "HEAD"], repo)
    assert rc == 0, err
    return sha.strip()


# A close written by the real producer: its sha and subject read back from
# git, and exactly what the Bash call that ran it printed.
Close = namedtuple("Close", "sha subject headline command output")


def gitmem_next(repo, headline, hhmmss):
    """Writes a close with the real bin/memory/next.py, as `gitmem next` does."""
    context = "Resumen inventado de la sesion."
    rc, stdout, stderr = run_cmd([sys.executable, NEXT_SCRIPT, headline, "--context", context],
                                 cwd=repo, env=_dated(hhmmss))
    assert rc == 0, stderr
    rc, sha, err = git_cmd(["rev-parse", "HEAD"], repo)
    assert rc == 0, err
    rc, subject, err = git_cmd(["log", "-1", "--format=%s"], repo)
    assert rc == 0, err
    command = (f'python3 "/somewhere/bin/gitmem" next "{headline}" --context "{context}"; '
               'echo "EXIT=$?"')
    # run_cmd strips the output; the shell would print next.py's line, then the echo.
    output = stdout.rstrip("\n") + f"\nEXIT={rc}"
    return Close(sha.strip(), subject.strip(), headline, command, output)


def held_close(transcript_path, session_id, close, launched, done):
    """What a session holds when its close agent wrote `close`: the Agent call
    in the top-level transcript, and that agent's sidechain file
    (<session>/subagents/agent-*.jsonl) with the real `gitmem next` call and output.
    Writes the sidechain file; returns the top-level records."""
    agent_id = uuid.uuid4().hex[:17]
    tool_id = "toolu_" + uuid.uuid4().hex[:24]
    prompt = close_agent_prompt()
    launch = assistant("", launched)
    launch["sessionId"] = session_id
    launch["message"]["content"] = [{"type": "tool_use", "id": tool_id, "name": "Agent",
                                     "input": {"description": "Write the session close",
                                               "subagent_type": "general-purpose",
                                               "prompt": prompt}}]
    result = base_record("user", done)
    result.update({"sessionId": session_id, "sourceToolAssistantUUID": launch["uuid"],
                   "message": {"role": "user", "content": [
                       {"type": "tool_result", "tool_use_id": tool_id,
                        "content": [{"type": "text", "text": "Close written."}]}]},
                   "toolUseResult": {"status": "completed", "prompt": prompt,
                                     "agentId": agent_id, "agentType": "general-purpose",
                                     "content": [{"type": "text", "text": "Close written."}]}})

    bash_id = "toolu_" + uuid.uuid4().hex[:24]
    opening = base_record("user", launched)
    opening["message"] = {"role": "user", "content": prompt}
    side = [opening, tool_call(close.command, done, bash_id),
            tool_answer(close.output, done, bash_id)]
    for record in side:
        record.update({"isSidechain": True, "agentId": agent_id, "sessionId": session_id})
    folder = os.path.join(os.path.dirname(str(transcript_path)), session_id, "subagents")
    write_transcript(os.path.join(folder, f"agent-{agent_id}.jsonl"), side)
    return [launch, result]


def held_close_top_level(session_id, close, launched, done):
    """The orchestrator ran `gitmem next` itself: call and output in the top-level transcript."""
    bash_id = "toolu_" + uuid.uuid4().hex[:24]
    records = [tool_call(close.command, launched, bash_id),
               tool_answer(close.output, done, bash_id)]
    for record in records:
        record["sessionId"] = session_id
    return records


# ── running the script the way the close agent runs it ──────────────────


class Run:
    def __init__(self, rc, stdout, stderr, text):
        self.rc, self.stdout, self.stderr, self.text = rc, stdout, stderr, text
        head, _, rest = text.partition("# COMMITS SINCE THE BOUNDARY")
        commits_part, _, conversation = rest.partition("# CONVERSATION")
        self.header = head
        self.commits = [line for line in commits_part.split("\n")[1:]
                        if line and not line.startswith("#")]
        self.conversation = conversation.split("\n", 1)[1] if "\n" in conversation else ""
        self.turns = [chunk for chunk in re.split(r"^=== ", self.conversation, flags=re.M)
                      if chunk.strip()]

    def user_turns_with(self, phrase):
        return [t for t in self.turns if t.startswith("user ") and phrase in t]

    def anywhere_in_conversation(self, phrase):
        return phrase in self.conversation

    def header_lines(self, prefix):
        return [line for line in self.header.split("\n") if line.startswith(prefix)]

    def commit_notes(self):
        return [line for line in self.header_lines("note:") if "commit" in line.lower()]

    def stop_lines(self):
        """Header lines the close agent stops on (prefix read from its prompt)."""
        return self.header_lines(close_prompt_stop_prefix())


def run_raw(tmp_path, repo, transcript, *extra, out_name="close-input.txt"):
    """(rc, stderr, Run or None): the script's answer, success or not."""
    out = str(tmp_path / out_name)
    rc, stdout, stderr = run_cmd(
        [sys.executable, SCRIPT, "--repo", repo, "--transcript", transcript, "--out", out,
         *extra],
        cwd=repo,
    )
    if rc != 0 or not os.path.exists(out):
        return rc, stderr, None
    with open(out, encoding="utf-8") as handle:
        return rc, stderr, Run(rc, stdout, stderr, handle.read())


def run(tmp_path, repo, transcript, *extra, out_name="close-input.txt"):
    rc, stderr, result = run_raw(tmp_path, repo, transcript, *extra, out_name=out_name)
    assert rc == 0 and result is not None, f"script failed rc={rc}: {stderr}"
    return result
