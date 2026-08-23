"""Contrato en ROJO -- `gitmem work` no puede commitear un borrado que
YA esta staged con `git rm`.

EL FALLO, reproducido en vivo por el orquestador en un repo de scratch y
confirmado leyendo el codigo real (no supuesto): `gitmem work "<msg>"
--path <fichero>` sobre un fichero trackeado cuyo borrado ya se stageo a
mano con `git rm` (entrada de indice fuera, fichero fuera del arbol de
trabajo) revienta con

    git fallo al commitear: fatal: pathspec '<ruta absoluta>' did not
    match any files

`lib/memory/notes_commit.py::stage_and_commit()` (linea 188 en
adelante) hace `git add --all -- <paths>` ANTES de `git commit --
<paths>`, y devuelve el resultado del primer paso que falle. Con el
fichero ausente A LA VEZ del indice y del arbol de trabajo, ese pathspec
no casa con nada que `git add` pueda ver (no es un borrado sin stagear
-- eso si lo cubre `--all`, segun el propio docstring de la funcion,
arreglo del 2026-08-05 -- es un borrado que YA NO EXISTE en ningun sitio
que `add` mire), asi que `git add --all -- <paths>` sale con codigo 128
y `stage_and_commit()` devuelve ESE fallo sin llegar nunca a intentar el
commit. Verificado aparte, contra un repo real: `git commit --
<misma ruta>` SOLO (sin el `git add` delante) sale con codigo 0 y
registra el borrado sin problema -- el `git add` previo es el paso que
sobra en este caso concreto, no el commit.

Un borrado SIN stagear (`rm fichero` a pelo, sin `git rm`) hoy funciona
-- lo cubre `--all` y no toca este contrato; este fichero no lo repite.

Ejecutado con `bin/gitmem` (la fachada, PIEZAS.md Sec.10 fila
`bin/gitmem`) contra un `tmp_repo` temporal, nunca importando
`notes_commit.py` en proceso -- `gitmem work` despacha por ruta a
`bin/memory/work.py` sin anadir logica propia [docstring de
`bin/gitmem`], asi que ejercitar la fachada es ejercitar el camino real
que tecleo el propietario.

`seed_config_json(tmp_repo, repo_type="trunk")`: el borrado se commitea
sobre la rama principal que crea `tmp_repo` (`main`) -- sin esto,
`work.py` rebota primero por PIEZAS.md Sec.10.1 punto 3 (rama protegida)
y el test nunca llegaria a ejercitar el fallo real de `stage_and_commit`.
"""

import os

import pytest

from .conftest import run_git, run_gitmem_script, seed_config_json


class TestWorkCommitsADeletionAlreadyStagedWithGitRm:
    def test_work_commits_a_deletion_already_staged_with_git_rm(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")

        # Fichero trackeado y comiteado.
        target_path = os.path.join(tmp_repo, "to_delete.txt")
        with open(target_path, "w", encoding="utf-8") as fh:
            fh.write("MARK content, about to be deleted\n")
        rc_add, _out_add, err_add = run_git(["add", "to_delete.txt"], tmp_repo)
        assert rc_add == 0, err_add
        rc_commit, _out_commit, err_commit = run_git(
            ["commit", "-m", "track to_delete.txt"], tmp_repo
        )
        assert rc_commit == 0, err_commit

        # Su borrado se staga a mano ANTES de invocar el comando bajo
        # prueba: fuera del indice y fuera del arbol de trabajo -- el
        # caso exacto que el fallo real reproduce, distinto de un `rm`
        # sin stagear.
        rc_rm, _out_rm, err_rm = run_git(["rm", "to_delete.txt"], tmp_repo)
        assert rc_rm == 0, err_rm
        assert not os.path.exists(target_path)

        rc, out, err = run_gitmem_script(
            ["work", "borrado", "--path", "to_delete.txt"],
            cwd=tmp_repo,
        )
        combined = out + err
        assert "Traceback" not in combined
        assert rc == 0, (
            "un borrado ya staged con `git rm` tiene que poder commitearse: "
            f"stdout={out!r} stderr={err!r}"
        )

        rc_ls, ls_out, err_ls = run_git(
            ["ls-tree", "HEAD", "--", "to_delete.txt"], tmp_repo
        )
        assert rc_ls == 0, err_ls
        assert ls_out.strip() == "", (
            "to_delete.txt sigue apareciendo en HEAD tras el commit de "
            f"trabajo: {ls_out!r}"
        )

        rc_msg, message, err_msg = run_git(["log", "-1", "--pretty=%B", "HEAD"], tmp_repo)
        assert rc_msg == 0, err_msg
        assert message.startswith("borrado"), (
            f"el commit HEAD no es el commit de trabajo esperado: {message!r}"
        )
