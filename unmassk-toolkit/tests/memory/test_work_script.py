"""Contrato ROJO de `bin/memory/work.py` -- PIEZAS.md Sec.10 (fila `work.py`).

`bin/memory/work.py` NO EXISTE TODAVIA. Modo test-first, pase de
CONTRATO: aceptacion, no barrido exhaustivo.

De donde sale cada cosa:

- PIEZAS.md Sec.10, fila `work.py`: llama a `notes.write_work`; admite
  "mensaje, --path (repetible), --issue"; imprime "el commit hecho".
- Las cuatro filas de test comunes + las dos reglas de esta tarea
  (force_utf8_streams primera sentencia; repo resuelto por cwd del
  proceso).
- La firma real de `lib/memory/notes_commit.py::write_work(message,
  paths, issue) -> WriteResult` -- YA en produccion, leida antes de
  escribir este contrato: "acepta rutas concretas y no arrastra el
  resto del arbol" (su propio docstring); si `issue` no es `None`, viaja
  como `f"{message}\\n\\nIssue: #{issue}"` -- formato literal ya escrito
  en produccion, no inventado aqui. `stage_and_commit()` hace `git add`
  EXPLICITO antes de comitear (mismo modulo): una ruta que no existe
  falla con el `pathspec ... did not match any file(s) known to git`
  real de git -- ya verificado contra un repo real segun el propio
  docstring de esa funcion.

HUECO CERRADO 2026-08-02 [PIEZAS.md Sec.10.1, punto 3, "orquestador en
modo autonomo... el propietario puede revocarlos"]: "si el tipo es el
protegido y se esta en la rama principal, el script rechaza" -- no
commitea, no pregunta. `work.py` YA EXISTE (`git status`), pero ese
punto 3 NO esta implementado -- lo dice el propio docstring del fichero,
citando el motivo real: los cuatro tests de la clase de arriba no
sembraban `config.json` (caen en el default fail-closed, `repo_type`
protegido) y corren sobre la rama que `git init` crea por defecto en
esta maquina -- exactamente el caso que la regla, implementada, tendria
que rechazar. Implementarla sin tocar los tests habria puesto los cuatro
en rojo a la vez, sin forma legal de arreglarlo desde produccion.

Desbloqueo, no invencion de comportamiento nuevo: los cuatro tests de
arriba siembran ahora `config.json` con `repo_type="trunk"` (el caso en
el que un commit de trabajo directo a la rama principal es legitimo), y
`TestProtectedRepoRejectsDirectCommitToMainBranch` (mas abajo) añade la
fila que faltaba -- protegido + rama principal -> rechazo real, sin
commit. Ningun texto fija la REDACCION exacta de ese rechazo (a
diferencia de los de `note.py`, que TEXTOS.md repite literalmente) --
por eso esos dos tests comprueban EFECTO (codigo de retorno, cero
commits nuevos, cero traceback, salida no vacia), nunca un texto
inventado a mano.

Con el punto 3 sin implementar todavia, `TestProtectedRepoRejectsDirect
CommitToMainBranch` es el ROJO real de esta tarea: `work.py` comitea hoy
sin mirar `repo_type` en absoluto.

Con el script inexistente, todos estos tests fallan hoy por la misma
causa real: `python3 <ruta inexistente>` -- ver docstring de
`test_note_script.py` para el detalle del mensaje.
"""

import os

import pytest

from .conftest import run_git, run_memory_script, seed_config_json


def _git_commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


def _git_head_sha(repo):
    rc, out, err = run_git(["rev-parse", "HEAD"], repo)
    assert rc == 0, f"git rev-parse fallo en el test: {err}"
    return out


def _git_files_changed(repo, ref="HEAD"):
    rc, out, err = run_git(["show", "--name-only", "--pretty=format:", ref], repo)
    assert rc == 0, f"git show fallo en el test: {err}"
    return sorted(line for line in out.splitlines() if line.strip())


def _git_head_message(repo):
    rc, out, err = run_git(["log", "-1", "--pretty=%B", "HEAD"], repo)
    assert rc == 0, f"git log fallo en el test: {err}"
    return out


def _write_file(repo, relative_path, content="MARK content\n"):
    full_path = os.path.join(repo, relative_path)
    os.makedirs(os.path.dirname(full_path) or repo, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return full_path


class TestAcceptsAllFlagsWithoutBouncingAndCommitsExactlyGivenPaths:
    """Filas 1 y 4: un comando, cero rechazos; y el efecto real -- el
    commit toca EXACTAMENTE las rutas dadas, nunca el resto del arbol
    [notes_commit.py::write_work, docstring]."""

    def test_two_paths_and_an_issue_trailer_in_one_call(self, tmp_repo):
        # repo_type="trunk": el caso en el que un commit de trabajo
        # directo a la rama principal es legitimo [PIEZAS.md Sec.10.1,
        # punto 3] -- sin esto, este test cae en el default fail-closed
        # (protegido) y rebotaria en cuanto ese punto se implemente.
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt", "MARK content A\n")
        _write_file(tmp_repo, "fileB.txt", "MARK content B\n")
        # Presente en el arbol de trabajo, pero NUNCA pasado por --path:
        # si aparece en el commit, el script arrastro mas de lo pedido.
        _write_file(tmp_repo, "fileC_untouched.txt", "MARK content C, must not be committed\n")

        before = _git_commit_count(tmp_repo)
        rc, out, err = run_memory_script(
            "work.py",
            [
                "wire the new login flow",
                "--path", "fileA.txt",
                "--path", "fileB.txt",
                "--issue", "42",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        after = _git_commit_count(tmp_repo)
        assert after == before + 1

        assert _git_files_changed(tmp_repo) == ["fileA.txt", "fileB.txt"], (
            "el commit de trabajo arrastro algo fuera de las rutas dadas, o le faltan"
        )
        message = _git_head_message(tmp_repo)
        assert message.startswith("wire the new login flow")
        assert "Issue: #42" in message


class TestFailureExitsNonzeroWithRealTextNoTraceback:
    def test_nonexistent_path_fails_with_the_real_git_pathspec_error(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        rc, out, err = run_memory_script(
            "work.py",
            ["commit a path that is not there", "--path", "does_not_exist.txt"],
            cwd=tmp_repo,
        )
        assert rc != 0, f"una ruta inexistente tiene que fallar: stdout={out!r}"
        combined = out + err
        assert "Traceback" not in combined
        assert "does_not_exist.txt" in combined, (
            f"el error real de git ('pathspec ... did not match') tiene que nombrar "
            f"la ruta: {combined!r}"
        )

        # Efecto real: no se creo ningun commit nuevo.
        rc2, count_out, err2 = run_git(["rev-list", "--count", "HEAD"], tmp_repo)
        assert rc2 == 0
        assert int(count_out) == 1, "una ruta inexistente no puede haber producido un commit"

    def test_real_git_index_lock_surfaces_the_real_git_error_not_a_traceback(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        lock_path = os.path.join(tmp_repo, ".git", "index.lock")
        with open(lock_path, "w", encoding="utf-8"):
            pass
        try:
            rc, out, err = run_memory_script(
                "work.py",
                ["should not commit, index is locked", "--path", "fileA.txt"],
                cwd=tmp_repo,
            )
        finally:
            os.remove(lock_path)

        assert rc != 0, f"con .git/index.lock puesto, el commit tiene que fallar: stdout={out!r}"
        combined = out + err
        assert "Traceback" not in combined
        assert "index.lock" in combined, (
            f"el error real de git tiene que llegar a la salida: {combined!r}"
        )


class TestForceUtf8StreamsFirstStatement:
    def test_accented_message_survives_a_restricted_console_encoding(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        rc, out, err = run_memory_script(
            "work.py",
            ["añadir soporte a café ☕ en el checkout", "--path", "fileA.txt"],
            cwd=tmp_repo,
            env={"PYTHONIOENCODING": "cp1252", "LANG": "C", "LC_ALL": "C"},
        )
        combined = out + err
        assert "UnicodeEncodeError" not in combined
        assert "UnicodeDecodeError" not in combined
        assert "Traceback" not in combined
        assert rc == 0, f"un commit de trabajo valido no deberia fallar bajo cp1252: {combined!r}"


class TestRepoResolvedByProcessCwd:
    def test_launched_from_a_nested_subdirectory_still_commits_to_that_same_repo(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        nested = os.path.join(tmp_repo, "src", "some", "nested", "place")
        os.makedirs(nested, exist_ok=True)
        file_path = _write_file(tmp_repo, "fileA.txt")
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "work.py",
            ["work committed from a nested cwd", "--path", file_path],
            cwd=nested,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, (
            "el commit no aparecio en tmp_repo aunque el script se lanzo desde "
            "una subcarpeta suya -- ¿resuelve el repositorio por una ruta fija?"
        )
        assert _git_files_changed(tmp_repo) == ["fileA.txt"]


class TestProtectedRepoRejectsDirectCommitToMainBranch:
    """PIEZAS.md Sec.10.1, punto 3 -- el hueco que este contrato dejaba
    abierto, ahora cerrado por el texto: "si el tipo es el protegido y se
    esta en la rama principal, el script rechaza" -- no commitea, no
    pregunta.

    ROJO real hoy: `bin/memory/work.py` no lee `repo_type` en absoluto
    (confirmado leyendo el fichero) -- comitea siempre, tambien sobre
    `main` con el default fail-closed. Los dos tests de abajo tienen que
    fallar por ESO, no por otra causa -- verificado corriendo la suite
    antes de cerrar esta tarea.

    "La rama principal": ningun texto de esta rama fija que nombre de
    rama cuenta -- ASUNCION documentada, igual que el propio docstring de
    `work.py` ya la deja escrita: es la rama que `git init` crea por
    defecto en esta maquina (verificado, es "main"), la misma que usan
    ya los cuatro tests de `TestAcceptsAllFlagsWithoutBouncingAndCommits
    ExactlyGivenPaths` y hermanas -- `tmp_repo` no la cambia nunca, asi
    que no hace falta fijarla a mano aqui.

    Ningun texto fija la REDACCION exacta de este rechazo (a diferencia
    de los de `note.py`, que TEXTOS.md repite literalmente seis veces) --
    por eso estos dos tests comprueban EFECTO, nunca un texto inventado a
    mano: codigo de retorno distinto de cero, CERO traceback, la salida
    no esta vacia ("dice que hacer"), y sobre todo -- el efecto que
    demuestra que el rechazo es de verdad y no solo un aviso -- ningun
    commit nuevo y el mismo SHA de HEAD antes y despues.
    """

    def test_gitflow_repo_type_on_main_branch_rejects_without_committing(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="gitflow")
        _write_file(tmp_repo, "fileA.txt")
        before_count = _git_commit_count(tmp_repo)
        before_sha = _git_head_sha(tmp_repo)

        rc, out, err = run_memory_script(
            "work.py",
            ["should not commit directly to a protected main", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc != 0, (
            f"repo_type=gitflow en la rama principal tiene que rebotar: "
            f"stdout={out!r} stderr={err!r}"
        )
        combined = out + err
        assert "Traceback" not in combined
        assert combined.strip() != "", "el rechazo tiene que decir algo, no salir en silencio"

        after_count = _git_commit_count(tmp_repo)
        after_sha = _git_head_sha(tmp_repo)
        assert after_count == before_count and after_sha == before_sha, (
            "un rechazo que ya ha escrito no es un rechazo -- HEAD no puede "
            f"haberse movido: antes={before_sha!r} despues={after_sha!r}"
        )

    def test_missing_config_defaults_to_protected_and_rejects_on_main(self, tmp_repo):
        # Sin config.json en absoluto: config.py cae en su default
        # fail-closed (repo_type="gitflow", "main protegido si no se
        # declara" -- su propio docstring). Es el caso mas peligroso: el
        # de un proyecto recien instalado, sin ningun ajuste todavia
        # [encargo del propietario -- "el que protege un proyecto recien
        # instalado"].
        _write_file(tmp_repo, "fileA.txt")
        before_count = _git_commit_count(tmp_repo)
        before_sha = _git_head_sha(tmp_repo)

        rc, out, err = run_memory_script(
            "work.py",
            ["should not commit, missing config defaults to protected", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc != 0, (
            f"sin config.json, el default protegido tiene que rebotar en la "
            f"rama principal: stdout={out!r} stderr={err!r}"
        )
        combined = out + err
        assert "Traceback" not in combined
        assert combined.strip() != "", "el rechazo tiene que decir algo, no salir en silencio"

        after_count = _git_commit_count(tmp_repo)
        after_sha = _git_head_sha(tmp_repo)
        assert after_count == before_count and after_sha == before_sha, (
            "un rechazo que ya ha escrito no es un rechazo -- HEAD no puede "
            f"haberse movido: antes={before_sha!r} despues={after_sha!r}"
        )


# ---------------------------------------------------------------------------
# Endurecimiento (paso 5, PIEZAS.md Sec.12bis) -- dos regresiones reales de
# `lib/memory/notes_commit.py`, ya arregladas por Ultron:
#
# 1. `stage_and_commit()` hacia `git add` anclado a `root`, pero llamaba a
#    `gitcmd.commit()` sin pasarle esa misma raiz -- heredaba el cwd
#    ambiental del proceso. Un commit de trabajo lanzado desde una
#    subcarpeta interpretaba el MISMO pathspec relativo desde dos sitios
#    distintos, y podia terminar tocando (o ensuciando el indice de) un
#    fichero de la raiz que el usuario ni siquiera queria tocar.
# 2. `write_work()` no limpiaba el area de staging cuando el commit
#    fallaba -- a diferencia de sus tres hermanas (`write`/`replace`/
#    `close`, en `notes.py`), que ya hacen `git reset -- <ruta>` si
#    `git commit` falla. Ahora resuelve las rutas a absolutas ANTES de
#    tocar git, y limpia el staging area si el commit falla.
# ---------------------------------------------------------------------------


class TestNestedCommitTargetsOnlyItsOwnPathLeavingTheRootFileAlone:
    """Escenario exacto del encargo: `app.py` en la raiz, modificado y
    SIN comitear; otro `app.py` distinto dentro de `sub/`, sin trackear
    todavia. Se commitea trabajo desde `sub/` apuntando a `sub/app.py`
    (con una ruta RELATIVA, tal como la teclearia una persona parada ahi).

    RED antes del arreglo: sin `root` explicito en la llamada a
    `gitcmd.commit()`, `git add -- app.py` (anclado a `root`) staba EL
    APP.PY DE LA RAIZ (la unica interpretacion posible de una ruta
    relativa anclada a `root`) en vez del de `sub/` -- el fichero
    equivocado quedaba staged, y el de verdad (`sub/app.py`) nunca se
    llegaba a tocar.
    """

    def test_commit_from_subdir_touches_only_its_own_app_py_root_stays_dirty_and_untouched(
        self, tmp_repo
    ):
        seed_config_json(tmp_repo, repo_type="trunk")

        # app.py de la raiz: trackeado, comiteado, y luego MODIFICADO sin
        # comitear -- tiene que seguir exactamente asi despues.
        root_app_path = _write_file(tmp_repo, "app.py", "root version, tracked at init\n")
        rc_add, _o, e_add = run_git(["add", "app.py"], tmp_repo)
        assert rc_add == 0, e_add
        rc_commit, _o, e_commit = run_git(["commit", "-m", "track root app.py"], tmp_repo)
        assert rc_commit == 0, e_commit
        with open(root_app_path, "w", encoding="utf-8") as fh:
            fh.write("root version, DIRTY, must survive the sub/ commit untouched\n")
        with open(root_app_path, encoding="utf-8") as fh:
            root_dirty_content = fh.read()

        # sub/app.py: contenido DISTINTO, todavia sin trackear.
        _write_file(tmp_repo, os.path.join("sub", "app.py"), "sub version, brand new\n")
        sub_dir = os.path.join(tmp_repo, "sub")

        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "work.py",
            ["wire the sub module", "--path", "app.py", "--issue", "7"],
            cwd=sub_dir,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, "el commit desde sub/ no se creo"

        # (a) el commit toca EXCLUSIVAMENTE sub/app.py.
        assert _git_files_changed(tmp_repo) == ["sub/app.py"], (
            "el commit de trabajo desde sub/ tenia que tocar solo sub/app.py, "
            f"toco: {_git_files_changed(tmp_repo)!r}"
        )
        rc_show, committed_content, e_show = run_git(["show", "HEAD:sub/app.py"], tmp_repo)
        assert rc_show == 0, e_show
        assert committed_content == "sub version, brand new"

        # (b) el app.py de la raiz sigue exactamente como estaba: mismo
        # contenido en disco, y sigue siendo un cambio SIN comitear.
        with open(root_app_path, encoding="utf-8") as fh:
            assert fh.read() == root_dirty_content, (
                "el app.py de la raiz cambio de contenido -- el commit de "
                "trabajo lanzado desde sub/ lo toco por error"
            )
        rc_status, status_out, e_status = run_git(
            ["status", "--porcelain", "--", "app.py"], tmp_repo
        )
        assert rc_status == 0, e_status
        assert status_out.strip() == "M app.py", (
            "el app.py de la raiz deberia seguir modificado y SIN STAGEAR "
            f"tras el commit lanzado desde sub/: git status dice {status_out!r}"
        )


class TestFailedCommitLeavesNoStagedLeftovers:
    """`write_work()` limpia el staging area si el commit falla -- mismo
    contrato que ya cumplen `notes.write()`/`replace()`/`close()`.

    Un `pre-commit` hook que rechaza SIEMPRE es la forma real de que
    `git add` complete pero `git commit` falle despues -- a diferencia de
    `.git/index.lock` (que bloquea `git add` tambien, y por tanto nunca
    llega a stagear nada), este es el escenario donde de verdad queda
    algo que limpiar.

    RED antes del arreglo: sin el `git reset -- <ruta>` que ahora sigue
    al commit fallido, `fileA.txt` se quedaba staged para siempre aunque
    el commit de trabajo nunca se llego a hacer -- el area de staging
    mentia sobre un cambio que el usuario no pidio.
    """

    def test_a_commit_rejected_by_a_precommit_hook_leaves_the_staging_area_clean(
        self, tmp_repo
    ):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt", "MARK content that should never end up committed\n")

        hooks_dir = os.path.join(tmp_repo, ".git", "hooks")
        os.makedirs(hooks_dir, exist_ok=True)
        hook_path = os.path.join(hooks_dir, "pre-commit")
        with open(hook_path, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\necho 'MARK_REJECT: no commits allowed by this hook' >&2\nexit 1\n")
        os.chmod(hook_path, 0o755)

        before_count = _git_commit_count(tmp_repo)
        before_sha = _git_head_sha(tmp_repo)

        rc, out, err = run_memory_script(
            "work.py",
            ["should be rejected by the pre-commit hook", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc != 0, (
            f"un commit rechazado por el hook tiene que fallar: stdout={out!r} stderr={err!r}"
        )
        combined = out + err
        assert "Traceback" not in combined

        after_count = _git_commit_count(tmp_repo)
        after_sha = _git_head_sha(tmp_repo)
        assert after_count == before_count and after_sha == before_sha, (
            "un commit rechazado por el hook no puede haber avanzado HEAD: "
            f"antes={before_sha!r} despues={after_sha!r}"
        )

        # El hallazgo real: `git add` SI llego a completarse (el hook
        # corre DESPUES de stagear) -- sin la limpieza, fileA.txt se queda
        # staged para siempre aunque el commit nunca se hizo.
        rc_diff, staged_out, e_diff = run_git(["diff", "--cached", "--name-only"], tmp_repo)
        assert rc_diff == 0, e_diff
        assert staged_out.strip() == "", (
            "el area de staging deberia quedar LIMPIA tras un commit fallido "
            f"-- sigue habiendo algo staged: {staged_out!r}"
        )
        rc_status, status_out, e_status = run_git(
            ["status", "--porcelain", "--", "fileA.txt"], tmp_repo
        )
        assert rc_status == 0, e_status
        assert status_out.strip() == "?? fileA.txt", (
            "fileA.txt deberia volver a aparecer como SIN TRACKEAR (nunca "
            f"llego a comitearse), no como staged: {status_out!r}"
        )
