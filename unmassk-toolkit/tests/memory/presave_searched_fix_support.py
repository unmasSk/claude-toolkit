"""Shared values and helpers of the #95 part 2c fix pass (D-133 and the
relaunch fixes): `test_presave_searched_fix_pass.py` and
`test_presave_searched_fix_pass_relaunch.py`. Not a test module. Split
2026-10-19 (Yoda's size finding).
"""

import json
import os
from contextlib import contextmanager

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_git,
    run_gitmem_script,
    run_hook_with_payload,
)

_ZONE1 = "fixzone"
_ZONE2 = "fixzonetwo"

# An apostrophe and a colon on purpose (shell quoting, field lookalike).
_SEARCHED = 'busqué "compat" y \'1.47\': nada escrito sobre esto'


@contextmanager
def _cwd(path):
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


@pytest.fixture
def query_mod():
    return import_lib_memory_module("query")


@pytest.fixture
def format_mod():
    return import_lib_memory_module("format")


def _message_of(repo, rev="HEAD"):
    rc, message, err = run_git(["log", "-1", "--format=%B", rev], repo)
    assert rc == 0, err
    return message


def _read_back(repo, query_mod, note_id):
    with _cwd(repo):
        note = query_mod.by_id(note_id)
    assert note is not None, f"the new reader lost {note_id}"
    return note


def _save(repo, args):
    rc, out, err = run_gitmem_script(args, cwd=repo)
    assert rc == 0, f"save failed: stdout={out!r} stderr={err!r}"
    return extract_note_id(out)


def _relaunch_lines(output, prefix):
    lines = output.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == "Relanza:"]
    assert starts, f"no 'Relanza:' block -- {output!r}"
    return [line.strip() for line in lines[starts[-1] + 1:] if line.strip().startswith(prefix)]


def _fill_holes(tokens, values):
    """Obey a relaunch: fill each `"..."` hole with the value this test
    chose for the flag right before it."""
    filled = list(tokens)
    for i, token in enumerate(filled):
        if token == "...":
            flag = filled[i - 1]
            assert flag in values, f"unexpected hole after {flag!r} in {tokens!r}"
            filled[i] = values[flag]
    return filled


def _rules_lines(repo):
    path = pm_path(repo) / "rules.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return [line for line in text.splitlines() if line.startswith("[remember]")]


def _run_customs(repo, command):
    rc, out, err = run_hook_with_payload(
        "customs.py", {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": repo},
        cwd=repo,
    )
    assert rc == 0, f"customs.py always exits 0 -- rc={rc} stderr={err!r}"
    return json.loads(out)
