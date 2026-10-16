"""Regresion: el arranque no instala fuera de un repositorio git.

Comportamiento: con el cwd de la sesion FUERA de un arbol de trabajo git y
sin `.claude/.unmassk/manifest.json`, `hooks/boot_launcher.py` no lanza el
instalador, no imprime nada sobre instalacion y no crea nada en esa
carpeta. Contra-caso: un `git init` recien hecho, sin manifiesto, SI se
instala (el manifiesto aparece).

Se conduce como lo hace el arranque real: proceso aparte, payload JSON de
SessionStart por stdin con `cwd`. HOME/USERPROFILE van a un directorio
temporal: el instalador deja un lanzador en `~/.local/bin` y el test nunca
debe tocar el del usuario.
"""

import os

from .conftest import (
    make_session_start_payload,
    run_git,
    run_hook_with_payload,
)

HOOK_NAME = "boot_launcher.py"


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
    assert "instalaci" not in both, both
    assert "ha fallado" not in both, both
    assert not os.path.exists(_manifest(folder))
    assert os.listdir(str(folder)) == []
    # ni el lanzador PATH en el HOME aislado
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
