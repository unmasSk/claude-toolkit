"""Shared setup for the #105 fix-pass tests after Moriarty: two live notes
under one id, made the way it happens in real use (two clones each write
the next id with `gitmem note`, then a union merge), with commit dates
fixed so `git log` order never depends on two commits sharing a second.
Not a test module (no `test_` prefix).
"""

import re
import shutil
import subprocess

from .conftest import pm_path, run_git, run_gitmem_script, seed_zones_json, with_searched

SAVED_ID_RE = re.compile(r"\b([A-Z]-\d+)\s+guardada")
LIVE_INDEXES = (
    "DECISIONS.md", "MEMOS.md", "RESTRICTIONS.md", "QUESTIONS.md",
    "DISCARDED.md", "INCIDENTS.md", "BLOCKED.md",
)
INDEX_OF = {"D": "DECISIONS.md", "M": "MEMOS.md", "R": "RESTRICTIONS.md",
            "Q": "QUESTIONS.md", "X": "DISCARDED.md", "I": "INCIDENTS.md", "B": "BLOCKED.md"}

BASE_DATE = "2026-01-01T09:00:00+0000"
OLDER_DATE = "2026-01-02T09:00:00+0000"
NEWER_DATE = "2026-01-03T09:00:00+0000"

EXTRA = {
    "M": ["--description", "seeded memo for the fix pass", "--stops", "no"],
    "I": ["--description", "seeded incident for the fix pass", "--work", "no"],
    "R": ["--description", "seeded wall for the fix pass", "--why", "seeded why", "--stops", "yes",
          "--origin", "none"],
    "D": ["--description", "seeded decision for the fix pass", "--why", "seeded why"],
    "Q": ["--description", "seeded question for the fix pass", "--work", "no"],
}


def dated(date):
    return {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}


def gitmem(args, cwd, env):
    rc, out, err = run_gitmem_script(args, cwd=cwd, env=env)
    combined = out + err
    assert "Traceback" not in combined, combined
    return rc, out, combined


def git_ok(args, cwd):
    rc, out, err = run_git(args, cwd)
    assert rc == 0, f"git {args} failed in the test setup: {err}"
    return out


def seed(repo, env, note_type, zones, headline, extra=None, date=None):
    """Write one note through `gitmem note`; returns (id, sha)."""
    args = with_searched(["note", note_type, "--zones", *zones, headline,
                          *(EXTRA[note_type] if extra is None else extra)])
    rc, out, combined = gitmem(args, repo, {**env, **(dated(date) if date else {})})
    assert rc == 0, f"seeding {note_type} {headline!r} failed: {combined!r}"
    match = SAVED_ID_RE.search(out)
    assert match, f"no saved id in the seed output: {out!r}"
    return match.group(1), git_ok(["rev-parse", "HEAD"], repo)


def make_twins(repo, tmp_path, env, note_type, here, there, zones_known, extra=None):
    """Two live notes with one id. `here` and `there` are (zones, headline,
    date); `here` is written in `repo`, `there` in a clone. Returns
    (id, {"here": sha, "there": sha}).
    """
    seed_zones_json(repo, zones_known)
    seed(repo, env, note_type, here[0], f"base {note_type} entry so the index is tracked",
         extra, BASE_DATE)
    other = str(tmp_path / "other")  # a clone: gitmem does not run in a worktree
    git_ok(["clone", "-q", repo, other], str(tmp_path))
    seed_zones_json(other, zones_known)
    id_here, sha_here = seed(repo, env, note_type, here[0], here[1], extra, here[2])
    id_there, sha_there = seed(other, env, note_type, there[0], there[1], extra, there[2])
    assert id_here == id_there, f"setup did not produce a duplicate: {id_here} vs {id_there}"
    attributes = pm_path(repo).parent.parent / ".git" / "info" / "attributes"
    attributes.parent.mkdir(parents=True, exist_ok=True)
    attributes.write_text("*.md merge=union\n", encoding="utf-8")
    git_ok(["fetch", "-q", other, "HEAD"], repo)
    git_ok(["merge", "--no-edit", "FETCH_HEAD"], repo)
    return id_here, {"here": sha_here, "there": sha_there}


def live_lines(indexes, repo, note_type, note_id):
    return [line for line in indexes.read(INDEX_OF[note_type], pm_path(repo)) if line.id == note_id]


def archive_lines(indexes, repo, note_id):
    return [line for line in indexes.read_archive(pm_path(repo)) if line.id == note_id]


def snapshot(repo):
    files = {p.name: p.read_bytes() for p in sorted(pm_path(repo).glob("*.md"))}
    return files, git_ok(["rev-parse", "HEAD"], repo), git_ok(["status", "--porcelain"], repo)


def relaunch_commands(output):
    """Every command line of every `Relanza:` block in `output`."""
    commands, inside = [], False
    for line in output.splitlines():
        if line.strip() == "Relanza:":
            inside = True
            continue
        if inside and line.startswith("  "):
            commands.append(line.strip())
            continue
        inside = False
    return commands


def pasted_words(command):
    """The argv a real POSIX shell builds from `command` pasted as printed."""
    shell = shutil.which("sh") or shutil.which("bash")
    assert shell, "no POSIX shell on PATH: cannot paste a relaunch like a person does"
    proc = subprocess.run([shell, "-c", "printf '%s\\0' " + command], capture_output=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.decode("utf-8").split("\0")[:-1]


def flag_value(words, flag):
    assert words.count(flag) == 1, f"{flag} must appear exactly once: {words!r}"
    return words[words.index(flag) + 1]
