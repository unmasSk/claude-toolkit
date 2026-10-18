"""Regression: session start does not install outside a git repository.

Behavior: with the session cwd OUTSIDE a git working tree and without
`.claude/.unmassk/manifest.json`, `hooks/boot_launcher.py` does not launch
the installer, prints nothing about installation and creates nothing in that
folder. Counter-case: a freshly made `git init`, without a manifest, DOES
install (the manifest appears).

It is driven the way the real session start does it: a separate process,
SessionStart JSON payload on stdin with `cwd`. HOME/USERPROFILE point to a
temporary directory: the installer leaves a launcher in `~/.local/bin` and
the test must never touch the user's.
"""

import ast
import os

from .conftest import (
    HOOKS_DIR,
    make_session_start_payload,
    run_git,
    run_hook_with_payload,
)

HOOK_NAME = "boot_launcher.py"


def _memory_notice_first_lines(tree):
    """First line of every `[memory]` notice printed under `tree`, read from
    the hook's own source (AST of its `print(...)` calls), not hand-typed.

    A print argument is either a plain string or an f-string; the static
    text of its first line is what the hook emits verbatim in both cases.
    """
    lines = []
    for node in ast.walk(tree):
        is_print = (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
            and node.args
        )
        if not is_print:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            text = arg.value
        elif isinstance(arg, ast.JoinedStr) and isinstance(arg.values[0], ast.Constant):
            text = arg.values[0].value
        else:
            continue
        if text.startswith("[memory]"):
            lines.append(text.split("\n")[0].lower())
    return lines


def _hook_notices():
    """(every `[memory]` notice of the hook, the install notices alone).

    The install notices are the ones printed inside the `if` that tests
    for the missing manifest. Since D-130 the hook has a third notice, the
    boot-overrun one, which is not about installing: outside git none of
    the three may appear, but only the install pair proves the scan still
    finds what this test is about.
    """
    with open(os.path.join(HOOKS_DIR, HOOK_NAME), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    install = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and "manifest" in ast.unparse(node.test):
            install.extend(_memory_notice_first_lines(node))
    return _memory_notice_first_lines(tree), install


def _isolated_home_env(tmp_path):
    home = tmp_path / "fake_home"
    home.mkdir()
    return {"HOME": str(home), "USERPROFILE": str(home)}, home


def _manifest(folder):
    return os.path.join(str(folder), ".claude", ".unmassk", "manifest.json")


def test_should_not_install_nor_print_nor_create_when_cwd_is_outside_git(tmp_path):
    env, home = _isolated_home_env(tmp_path)
    folder = tmp_path / "not_a_repo"
    folder.mkdir()

    rc, out, err = run_hook_with_payload(
        HOOK_NAME, make_session_start_payload(str(folder)), cwd=str(folder), env=env
    )

    assert rc == 0, f"stdout={out!r} stderr={err!r}"
    both = (out + err).lower()
    notices, install_notices = _hook_notices()
    # anti-vacuity: both install notices (installed OK / install failed)
    # were found, and they are among the notices checked below
    assert len(install_notices) == 2, install_notices
    assert set(install_notices) <= set(notices), (install_notices, notices)
    for notice in notices:
        assert notice not in both, both
    assert not os.path.exists(_manifest(folder))
    assert os.listdir(str(folder)) == []
    # nor the PATH launcher in the isolated HOME
    assert not (home / ".local").exists()


def test_should_install_when_fresh_git_init_folder_has_no_manifest(tmp_path):
    env, home = _isolated_home_env(tmp_path)
    repo = tmp_path / "fresh_repo"
    repo.mkdir()
    rc_init, _o, err_init = run_git(["init"], str(repo))
    assert rc_init == 0, err_init

    rc, out, err = run_hook_with_payload(
        HOOK_NAME, make_session_start_payload(str(repo)), cwd=str(repo), env=env
    )

    assert rc == 0, f"stdout={out!r} stderr={err!r}"
    assert os.path.isfile(_manifest(repo)), f"stdout={out!r} stderr={err!r}"
