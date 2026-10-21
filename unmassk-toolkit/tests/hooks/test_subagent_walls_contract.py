"""Test-first contract for hooks/subagent-walls.py (D-171, D-174, issue #91).

Every agent, at its start, gets the project's walls: the hook reads the
SubagentStart input on stdin, finds `.claude/project-memory/RESTRICTIONS.md`
walking up from the payload's `cwd`, and prints

    {"hookSpecificOutput": {"hookEventName": "SubagentStart",
                            "additionalContext": "<heading>\\n<wall>\\n..."}}

where the context is one heading line plus every line of that file that
starts with `[R-`, exactly as written, in file order. No project memory, or
an index with no walls: nothing on stdout, exit 0. Unreadable file or bad
input: nothing on stdout, one line on stderr, exit 0 -- an agent must never
be stopped from starting.

The hook is run as a separate process with a real payload on stdin, never
imported. One test runs it through the exact `command` string hooks.json
gives Claude Code.

Constraints this contract declares for the implementation:
  - the project is found from the payload's `cwd`, not the process cwd;
  - the nearest `.claude/project-memory/RESTRICTIONS.md` going up wins;
  - the stderr line for an unreadable index names the file (RESTRICTIONS.md).
"""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from .conftest import HOOKS_DIR, TOOLKIT_ROOT, run_cmd, run_hook, run_hook_raw

HOOK = "subagent-walls.py"
HOOKS_JSON = HOOKS_DIR / "hooks.json"
GITMEM_BIN = TOOLKIT_ROOT / "bin" / "gitmem"
EVENT = "SubagentStart"
WALL_PREFIX = "[R-"

_GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "unmassk-toolkit-tests",
    "GIT_AUTHOR_EMAIL": "tests@unmassk-toolkit.invalid",
    "GIT_COMMITTER_NAME": "unmassk-toolkit-tests",
    "GIT_COMMITTER_EMAIL": "tests@unmassk-toolkit.invalid",
}

_INDEX_HEADER = "# RESTRICTIONS — índice. Lo escribe el script. No editar. Si diverge, manda git."


# ── Builders ────────────────────────────────────────────────────────────

def make_payload(cwd, agent_type="unmassk-toolkit:dante"):
    """SubagentStart input: common fields + agent_id / agent_type."""
    return {
        "session_id": f"sess-{uuid.uuid4().hex[:8]}",
        "transcript_path": str(Path(cwd) / "transcript.jsonl"),
        "cwd": str(cwd),
        "permission_mode": "default",
        "hook_event_name": EVENT,
        "agent_id": f"agent-{uuid.uuid4().hex[:8]}",
        "agent_type": agent_type,
    }


def write_index(project, lines):
    """Hand-written RESTRICTIONS.md, for the filtering cases only (the
    byte-for-byte case uses the real writer, see the round-trip test)."""
    pm = Path(project) / ".claude" / "project-memory"
    pm.mkdir(parents=True, exist_ok=True)
    path = pm / "RESTRICTIONS.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def context_lines(parsed):
    """additionalContext split in lines, after checking the envelope."""
    assert parsed is not None, "stdout is not a JSON object"
    out = parsed["hookSpecificOutput"]
    assert out["hookEventName"] == EVENT
    return out["additionalContext"].split("\n")


def assert_heading_then(lines, walls):
    assert lines[0].strip(), "the first line must be a heading"
    assert not lines[0].startswith(WALL_PREFIX), "the heading must not be a wall"
    assert lines[1:] == walls


def assert_hook_exists():
    """Red for the right reason: the hook file is missing, not a test error."""
    assert (HOOKS_DIR / HOOK).is_file(), f"hooks/{HOOK} does not exist yet"


# ── Behaviours ──────────────────────────────────────────────────────────

class TestWallsReachTheAgent:

    def test_should_return_heading_plus_every_wall_in_file_order_when_index_has_walls(self, tmp_path):
        # Bug caught: walls dropped, reordered, the header or blank lines leaked in.
        project = tmp_path / "project"
        walls = [
            "[R-003][install][hooks] never delete the plugin cache during an active session",
            "[R-017][hooks][skills] agents never run git stash/reset/checkout/restore",
            "[R-012][memory][architecture] next_id must receive live index plus archived ids",
        ]
        write_index(project, [_INDEX_HEADER, "", *walls])
        assert_hook_exists()

        rc, parsed, stdout, stderr = run_hook(HOOK, make_payload(project), cwd=str(project))

        assert rc == 0, stderr
        assert_heading_then(context_lines(parsed), walls)

    def test_should_take_only_lines_that_start_with_the_wall_prefix(self, tmp_path):
        # Bug caught: a substring match lets a line that only mentions a wall through.
        project = tmp_path / "project"
        wall = "[R-005][db][docs] reference-heavy skills must cite verified sources"
        write_index(project, [
            _INDEX_HEADER,
            "see [R-005] below",
            " [R-099][x][y] indented, not a wall line",
            "[D-001][x][y] a decision line",
            wall,
        ])
        assert_hook_exists()

        rc, parsed, _out, stderr = run_hook(HOOK, make_payload(project), cwd=str(project))

        assert rc == 0, stderr
        assert_heading_then(context_lines(parsed), [wall])

    def test_should_find_the_index_walking_up_from_a_subfolder_cwd(self, tmp_path):
        # Bug caught: the hook only looks in cwd itself and agents in a subfolder get nothing.
        project = tmp_path / "project"
        wall = "[R-020][skills][install] skill discovery must filter .orphaned_at"
        write_index(project, [_INDEX_HEADER, "", wall])
        deep = project / "pkg" / "sub" / "deeper"
        deep.mkdir(parents=True)
        assert_hook_exists()

        rc, parsed, _out, stderr = run_hook(HOOK, make_payload(deep), cwd=str(deep))

        assert rc == 0, stderr
        assert_heading_then(context_lines(parsed), [wall])

    def test_should_resolve_from_the_payload_cwd_not_the_process_cwd(self, tmp_path):
        # Bug caught: os.getcwd() used instead of the payload's cwd field.
        project = tmp_path / "project"
        wall = "[R-021][skills][architecture] agent memory stays on the six builders"
        write_index(project, [_INDEX_HEADER, "", wall])
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        assert_hook_exists()

        rc, parsed, _out, stderr = run_hook(HOOK, make_payload(project), cwd=str(elsewhere))

        assert rc == 0, stderr
        assert_heading_then(context_lines(parsed), [wall])

    def test_should_use_the_nearest_project_when_projects_are_nested(self, tmp_path):
        # Bug caught: walking to the top and giving an agent another project's walls.
        outer = tmp_path / "outer"
        inner = outer / "vendor" / "inner"
        write_index(outer, [_INDEX_HEADER, "", "[R-001][a][b] outer wall"])
        write_index(inner, [_INDEX_HEADER, "", "[R-002][c][d] inner wall"])
        assert_hook_exists()

        rc, parsed, _out, stderr = run_hook(HOOK, make_payload(inner), cwd=str(inner))

        assert rc == 0, stderr
        assert_heading_then(context_lines(parsed), ["[R-002][c][d] inner wall"])


class TestSilentWhenThereIsNothingToSay:

    def test_should_print_nothing_and_exit_0_when_no_project_memory_exists(self, tmp_path):
        # Bug caught: an empty envelope, a heading with no walls, or a crash outside a project.
        bare = tmp_path / "no-memory-here"
        bare.mkdir()
        assert_hook_exists()

        rc, _parsed, stdout, stderr = run_hook(HOOK, make_payload(bare), cwd=str(bare))

        assert (rc, stdout) == (0, ""), stderr

    def test_should_print_nothing_and_exit_0_when_index_has_no_walls(self, tmp_path):
        # Bug caught: a lone heading injected into every agent of a project with no walls.
        project = tmp_path / "project"
        write_index(project, [_INDEX_HEADER, ""])
        assert_hook_exists()

        rc, _parsed, stdout, stderr = run_hook(HOOK, make_payload(project), cwd=str(project))

        assert (rc, stdout) == (0, ""), stderr


class TestNeverStopsAnAgent:

    @pytest.mark.parametrize(
        "raw_stdin",
        ["{not json at all", "", "[]", '"a string"'],
        ids=["broken-json", "empty", "json-array", "json-string"],
    )
    def test_should_print_nothing_one_stderr_line_and_exit_0_on_bad_input(self, tmp_path, raw_stdin):
        # Bug caught: a traceback (exit 1, many lines) or a silent swallow with no word on stderr.
        assert_hook_exists()

        rc, stdout, stderr = run_hook_raw(HOOK, raw_stdin, cwd=str(tmp_path))

        assert rc == 0
        assert stdout == ""
        assert len(stderr.strip().splitlines()) == 1, stderr

    def test_should_print_nothing_one_stderr_line_naming_the_file_and_exit_0_when_unreadable(self, tmp_path):
        # Bug caught: PermissionError crashes the hook, or is swallowed in silence.
        if sys.platform == "win32":
            pytest.skip("chmod-based permission test is POSIX-only")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            pytest.skip("root reads a chmod 000 file anyway")
        project = tmp_path / "project"
        path = write_index(project, [_INDEX_HEADER, "", "[R-001][a][b] wall"])
        assert_hook_exists()
        os.chmod(path, 0o000)
        try:
            rc, _parsed, stdout, stderr = run_hook(HOOK, make_payload(project), cwd=str(project))
        finally:
            os.chmod(path, 0o644)

        assert rc == 0
        assert stdout == ""
        lines = stderr.strip().splitlines()
        assert len(lines) == 1, stderr
        assert "RESTRICTIONS.md" in lines[0]


# ── Round-trip against the real writer ─────────────────────────────────

def _gitmem(args, cwd):
    return run_cmd([sys.executable, str(GITMEM_BIN), *args], cwd=cwd, env=_GIT_IDENTITY)


@pytest.fixture
def memory_repo(tmp_path):
    """Throwaway git repo with two zones, ready for `gitmem note R`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (["git", "init", "-q"], ["git", "commit", "-q", "--allow-empty", "-m", "init"]):
        rc, _o, err = run_cmd(args, cwd=str(repo), env=_GIT_IDENTITY)
        assert rc == 0, err
    pm = repo / ".claude" / "project-memory"
    pm.mkdir(parents=True)
    (pm / "zones.json").write_text(
        json.dumps({z: {"description": f"zone {z}", "aliases": []} for z in ("hooks", "memory")}),
        encoding="utf-8",
    )
    return repo


def _save_wall(repo, headline):
    rc, out, err = _gitmem(
        ["note", "R", "--zones", "hooks", "memory", headline,
         "--why", "un muro de prueba", "--description", "prueba «de ida y vuelta»",
         "--stops", "yes", "--searched", "nada escrito"],
        cwd=str(repo),
    )
    assert rc == 0, f"gitmem note R failed: {out}\n{err}"


class TestRoundTripWithRealGitmem:

    def test_should_pass_walls_with_accents_quotes_and_guillemets_byte_for_byte(self, memory_repo):
        # Bug caught: ascii-escaping, accent folding, quote mangling or re-encoding on the way out.
        headlines = [
            'nunca «tocar» el "índice" a mano — lo escribe el script',
            "la configuración del niño: ‘comillas’ y ñandú, sin pérdida",
        ]
        for h in headlines:
            _save_wall(memory_repo, h)
        index = memory_repo / ".claude" / "project-memory" / "RESTRICTIONS.md"
        written = [
            line for line in index.read_bytes().decode("utf-8").split("\n")
            if line.startswith(WALL_PREFIX)
        ]
        assert len(written) == 2 and all(h in w for h, w in zip(headlines, written)), written
        assert_hook_exists()

        rc, parsed, _out, stderr = run_hook(HOOK, make_payload(memory_repo), cwd=str(memory_repo))

        assert rc == 0, stderr
        assert_heading_then(context_lines(parsed), written)


# ── Registration: the door Claude Code uses ─────────────────────────────

def _load_hooks():
    return json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]


def _walls_groups():
    return [
        g for g in _load_hooks().get(EVENT, [])
        if any(HOOK in h.get("command", "") for h in g.get("hooks", []))
    ]


class TestRegistration:

    def test_should_register_the_hook_once_under_subagentstart_for_every_agent(self):
        # Bug caught: hook written but never wired, wired twice, or limited by a matcher.
        groups = _walls_groups()

        assert len(groups) == 1, f"{EVENT} entries running {HOOK}: {len(groups)}"
        assert groups[0].get("matcher") in (None, "", "*")

    def test_should_deliver_walls_when_run_through_the_hooks_json_command(self, tmp_path):
        # Bug caught: a command string that does not run the hook (wrong path, wrong interpreter).
        if sys.platform == "win32":
            pytest.skip("${CLAUDE_PLUGIN_ROOT} in the command is POSIX shell expansion")
        groups = _walls_groups()
        assert len(groups) == 1, f"{HOOK} is not registered under {EVENT}"
        command = next(h["command"] for h in groups[0]["hooks"] if HOOK in h["command"])
        project = tmp_path / "project"
        wall = "[R-023][install][hooks] installer removes only its own exact old hooks"
        write_index(project, [_INDEX_HEADER, "", wall])

        result = subprocess.run(
            command, shell=True, cwd=str(project),
            input=json.dumps(make_payload(project)),
            capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(TOOLKIT_ROOT)},
            timeout=20,
        )

        assert result.returncode == 0, result.stderr
        assert_heading_then(context_lines(json.loads(result.stdout)), [wall])
