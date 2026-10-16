"""Contrato ROJO: `gitmem --help` / `-h` / `help` / sin argumentos imprimen
cada subcomando con UNA linea de descripcion y salen con 0.

La lista esperada NO se teclea: se lee del propio `SUBCOMMANDS` de
`bin/gitmem` (AST, sin ejecutar el modulo). Un subcomando nuevo sin linea
de ayuda pone este test en rojo. Se ejecuta el punto de entrada del repo
como proceso, con HOME aislado.
"""

import ast
import os
import re
import subprocess
import sys

import pytest

_TOOLKIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GITMEM = os.path.join(_TOOLKIT, "bin", "gitmem")


def _dispatch_table():
    with open(_GITMEM, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "SUBCOMMANDS" for t in node.targets
        ):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("SUBCOMMANDS not found in bin/gitmem")


SUBCOMMANDS = _dispatch_table()


def _run(args, tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    return subprocess.run(
        [sys.executable, _GITMEM, *args],
        cwd=str(tmp_path), env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=60,
    )


def _help_line(stdout, name):
    for line in stdout.splitlines():
        m = re.match(rf"^\s*(?:gitmem\s+)?{re.escape(name)}\b(.*)$", line)
        if m:
            return m.group(1)
    return None


HELP_INVOCATIONS = [["--help"], ["-h"], ["help"], []]


@pytest.mark.parametrize("args", HELP_INVOCATIONS, ids=lambda a: " ".join(a) or "bare")
def test_should_exit_zero_when_help_requested(args, tmp_path):
    assert _run(args, tmp_path).returncode == 0


@pytest.mark.parametrize("args", HELP_INVOCATIONS, ids=lambda a: " ".join(a) or "bare")
@pytest.mark.parametrize("name", SUBCOMMANDS)
def test_should_describe_every_subcommand_when_help_requested(args, name, tmp_path):
    out = _run(args, tmp_path).stdout
    rest = _help_line(out, name)
    assert rest is not None, f"{name} missing from stdout:\n{out}"
    description = re.sub(r"^[\s:\-–—]+", "", rest)
    assert len(description.split()) >= 2, (
        f"{name} has no description line: {rest!r}"
    )


def test_should_fail_naming_valid_subcommands_when_unknown(tmp_path):
    r = _run(["zzz-not-a-subcommand"], tmp_path)
    assert r.returncode != 0
    for name in SUBCOMMANDS:
        assert name in r.stderr
