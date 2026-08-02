"""Test tonto que demuestra que el fixture `tmp_repo` (paso 0.3) funciona.

Es la verificacion de puerta que pide FASE 0 en
docs/memoria-v2/PLAN-CONSTRUCCION.md ("un test tonto que crea el repo
temporal pasa"). No prueba nada del sistema de memoria todavia -- eso
llega en las fases 1 y 2, cuando exista el validador y el generador.
"""

import os

from conftest import run_git


def test_tmp_repo_is_a_real_git_worktree(tmp_repo):
    """El directorio existe y `git` lo reconoce como worktree valido."""
    assert os.path.isdir(tmp_repo)
    assert os.path.isdir(os.path.join(tmp_repo, ".git"))

    returncode, stdout, stderr = run_git(
        ["rev-parse", "--is-inside-work-tree"], tmp_repo
    )
    assert returncode == 0, f"git rev-parse fallo: {stderr}"
    assert stdout == "true"


def test_tmp_repo_has_exactly_one_initial_commit(tmp_repo):
    """El repo temporal trae ya el commit inicial 'init' y solo ese."""
    returncode, stdout, stderr = run_git(
        ["log", "--format=%s", "-1"], tmp_repo
    )
    assert returncode == 0, f"git log fallo: {stderr}"
    assert stdout == "init"

    returncode_count, stdout_count, stderr_count = run_git(
        ["rev-list", "--count", "HEAD"], tmp_repo
    )
    assert returncode_count == 0, f"git rev-list fallo: {stderr_count}"
    assert stdout_count == "1"
