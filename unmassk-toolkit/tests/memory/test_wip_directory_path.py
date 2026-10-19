"""Contrato de `gitmem wip "<msg>" --path <una carpeta>` -- issue #104,
punto 3 (test-first, Short).

Hoy (leido y ejecutado, 2026-10-19): `wip.py` hace `path.read_bytes()`
sobre cada `--path`; con una carpeta eso cae a `None`, y luego
`notes.write_work()` vuelve a leerla y revienta. La salida real es
`git fallo al commitear: [Errno 21] Is a directory: '<ruta>'`, codigo 1,
sin commit -- jerga de Python, y la persona no sabe que hacer.

Contrato (del orquestador, issue #104 punto 3):
- no guarda nada (ni commit nuevo, ni nada dejado en el indice);
- dice en llano que `--path` admite ficheros, no carpetas -- sin jerga
  (`Errno`, `Is a directory`, `IsADirectoryError`, traza de pila);
- lista los ficheros cambiados bajo esa carpeta, seguidos y sin seguir,
  y solo esos (ni los que no cambiaron, ni los de fuera de la carpeta);
- da el comando exacto para relanzar, con un `--path` por fichero;
- codigo de salida distinto de cero, sin traceback;
- pasar los ficheros uno a uno sigue funcionando como hoy.

Todo se ejecuta por la puerta del usuario: `bin/gitmem wip ...` como
proceso aparte, en un repositorio desechable (`tmp_repo`) y con un HOME
desechable. El comando de relanzamiento NO se compara contra un texto
tecleado aqui: se extrae de la salida real, se ejecuta de verdad con la
misma fachada y se mira que el commit resultante lleva exactamente los
ficheros que este test cambio en disco (las dos cosas, escritas por
separado: lo que el test toco y lo que el comando propuesto comitea).
"""

import os
import shlex

import pytest

from .conftest import run_git, run_gitmem_script, seed_config_json

_MESSAGE = "mid refactor snapshot of the src folder"

# Lo que este test cambia bajo `src/` -- la verdad independiente contra
# la que se mide el listado y el relanzamiento.
_CHANGED_TRACKED = "src/a.txt"
_CHANGED_UNTRACKED_NESTED = "src/sub/new.txt"
_UNCHANGED_TRACKED = "src/untouched.txt"
_CHANGED_OUTSIDE = "outside.txt"
_EXPECTED_LISTED = sorted([_CHANGED_TRACKED, _CHANGED_UNTRACKED_NESTED])

_JARGON = ("Traceback", "Errno", "Is a directory", "IsADirectoryError")


def _write(repo, rel, content):
    full = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)


def _git(repo, *args):
    rc, out, err = run_git(list(args), repo)
    assert rc == 0, f"git {args} fallo en el test: {err}"
    return out


@pytest.fixture
def dir_repo(tmp_repo, tmp_path):
    """Repositorio desechable con una carpeta `src/` que tiene: un fichero
    seguido modificado, un fichero nuevo sin seguir DENTRO de una
    subcarpeta nueva (git status lo plegaria a `src/sub/`), un fichero
    seguido sin tocar, y un cambio fuera de `src/`. `repo_type="trunk"`
    para que la proteccion de rama no rebote antes de llegar a `--path`.
    Devuelve (repo, env con HOME desechable).
    """
    seed_config_json(tmp_repo, repo_type="trunk")
    _write(tmp_repo, _CHANGED_TRACKED, "original\n")
    _write(tmp_repo, _UNCHANGED_TRACKED, "never touched\n")
    _write(tmp_repo, _CHANGED_OUTSIDE, "original outside\n")
    _git(tmp_repo, "add", "-A")
    _git(tmp_repo, "commit", "-m", "seed")

    _write(tmp_repo, _CHANGED_TRACKED, "original\nedited\n")
    _write(tmp_repo, _CHANGED_UNTRACKED_NESTED, "brand new\n")
    _write(tmp_repo, _CHANGED_OUTSIDE, "original outside\nedited\n")

    home = tmp_path / "throwaway-home"
    home.mkdir()
    return tmp_repo, {"HOME": str(home)}


def _relaunch_lines(text):
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("gitmem wip ")
    ]


def _relaunch_argv(text):
    lines = _relaunch_lines(text)
    assert len(lines) == 1, (
        f"tiene que haber exactamente una linea de relanzamiento "
        f"`gitmem wip ...`; encontradas {len(lines)} en:\n{text}"
    )
    return shlex.split(lines[0])


def _paths_of(argv):
    pairs = list(zip(argv, argv[1:]))
    return sorted(value for flag, value in pairs if flag == "--path")


@pytest.mark.parametrize("given", ["src", "src/"])
class TestWipWithADirectoryPath:
    def test_should_save_nothing_when_path_is_a_directory(self, dir_repo, given):
        repo, env = dir_repo
        head_before = _git(repo, "rev-parse", "HEAD")

        rc, out, err = run_gitmem_script(
            ["wip", _MESSAGE, "--path", given], cwd=repo, env=env
        )

        assert rc != 0, f"stdout={out!r} stderr={err!r}"
        assert _git(repo, "rev-parse", "HEAD") == head_before
        assert _git(repo, "diff", "--cached", "--name-only") == ""

    def test_should_answer_without_python_jargon_when_path_is_a_directory(
        self, dir_repo, given
    ):
        repo, env = dir_repo
        rc, out, err = run_gitmem_script(
            ["wip", _MESSAGE, "--path", given], cwd=repo, env=env
        )
        combined = out + err
        assert rc != 0
        leaked = [word for word in _JARGON if word in combined]
        assert leaked == [], f"jerga en la respuesta: {leaked} -- {combined!r}"

    def test_should_list_exactly_the_changed_files_under_the_directory(
        self, dir_repo, given
    ):
        repo, env = dir_repo
        rc, out, err = run_gitmem_script(
            ["wip", _MESSAGE, "--path", given], cwd=repo, env=env
        )
        combined = out + err
        assert rc != 0
        missing = [p for p in _EXPECTED_LISTED if p not in combined]
        assert missing == [], f"no lista {missing}: {combined!r}"
        intruders = [
            p for p in (_UNCHANGED_TRACKED, _CHANGED_OUTSIDE) if p in combined
        ]
        assert intruders == [], f"lista lo que no toca: {intruders}: {combined!r}"

    def test_should_give_a_relaunch_with_one_path_per_changed_file(
        self, dir_repo, given
    ):
        repo, env = dir_repo
        rc, out, err = run_gitmem_script(
            ["wip", _MESSAGE, "--path", given], cwd=repo, env=env
        )
        assert rc != 0
        argv = _relaunch_argv(out + err)
        assert argv[:3] == ["gitmem", "wip", _MESSAGE], argv
        assert _paths_of(argv) == _EXPECTED_LISTED, argv
        assert argv.count("--path") == len(_EXPECTED_LISTED), argv

    def test_should_commit_exactly_those_files_when_the_relaunch_is_run(
        self, dir_repo, given
    ):
        repo, env = dir_repo
        rc, out, err = run_gitmem_script(
            ["wip", _MESSAGE, "--path", given], cwd=repo, env=env
        )
        assert rc != 0
        argv = _relaunch_argv(out + err)
        head_before = _git(repo, "rev-parse", "HEAD")

        rc2, out2, err2 = run_gitmem_script(argv[1:], cwd=repo, env=env)

        assert rc2 == 0, f"el relanzamiento propuesto falla: {out2!r} {err2!r}"
        assert _git(repo, "rev-parse", "HEAD~1") == head_before
        committed = sorted(
            _git(repo, "show", "--name-only", "--pretty=format:", "HEAD").split()
        )
        assert committed == _EXPECTED_LISTED


def test_should_keep_committing_files_given_one_by_one(dir_repo):
    """Golden: verde hoy a proposito -- el camino fichero a fichero no
    puede romperse al arreglar el de carpeta."""
    repo, env = dir_repo
    head_before = _git(repo, "rev-parse", "HEAD")

    rc, out, err = run_gitmem_script(
        [
            "wip", _MESSAGE,
            "--path", _CHANGED_TRACKED,
            "--path", _CHANGED_UNTRACKED_NESTED,
        ],
        cwd=repo,
        env=env,
    )

    assert rc == 0, f"stdout={out!r} stderr={err!r}"
    assert "Traceback" not in out + err
    assert _git(repo, "rev-parse", "HEAD~1") == head_before
    committed = sorted(
        _git(repo, "show", "--name-only", "--pretty=format:", "HEAD").split()
    )
    assert committed == _EXPECTED_LISTED


# ---------------------------------------------------------------------------
# Ronda de arreglo de #104.3 (Cerberus F1/F2 + los casos que Ultron declaro
# «Beyond the tests»). Mismo metodo: puerta del usuario, relanzamiento
# extraido de la salida real y ejecutado, commit comparado contra lo que el
# test cambio en disco.
# ---------------------------------------------------------------------------


def _reject_and_relaunch(repo, env, args, cwd=None):
    """Lanza `gitmem wip` con `args`, exige el rechazo, ejecuta el
    relanzamiento propuesto desde la MISMA carpeta y devuelve
    (salida del rechazo, argv del relanzamiento, `--name-status` del commit).
    """
    where = cwd or repo
    rc, out, err = run_gitmem_script(["wip", _MESSAGE, *args], cwd=where, env=env)
    assert rc != 0, f"stdout={out!r} stderr={err!r}"
    argv = _relaunch_argv(out + err)
    head_before = _git(repo, "rev-parse", "HEAD")
    rc2, out2, err2 = run_gitmem_script(argv[1:], cwd=where, env=env)
    assert rc2 == 0, f"el relanzamiento propuesto falla: {out2!r} {err2!r}"
    assert _git(repo, "rev-parse", "HEAD~1") == head_before
    status = _git(repo, "show", "--name-status", "--pretty=format:", "HEAD")
    return out + err, argv, sorted(status.splitlines())


class TestListedPathsArePosixStyle:
    """Cerberus #104.3 F1 (T2): en Windows `os.path.relpath` da `src\\a.txt`
    y el listado y el relanzamiento salen con barra invertida, mezclada con
    las barras normales que ensena git en todo lo demas. Contrato: barras
    normales en todas las plataformas. Rojo solo en Windows (la CI corre en
    windows-latest); en macOS/Linux no hay forma fiel de simularlo, porque
    el arreglo correcto (`Path(...).as_posix()`) depende del tipo de ruta
    del sistema que lo ejecuta."""

    def test_should_list_and_relaunch_with_forward_slashes_only(self, dir_repo):
        repo, env = dir_repo
        rc, out, err = run_gitmem_script(
            ["wip", _MESSAGE, "--path", "src"], cwd=repo, env=env
        )
        combined = out + err
        assert rc != 0
        assert _CHANGED_UNTRACKED_NESTED in combined, combined
        assert "\\" not in combined, f"barra invertida en: {combined!r}"
        assert _paths_of(_relaunch_argv(combined)) == _EXPECTED_LISTED

    def test_should_keep_a_given_file_with_forward_slashes_next_to_a_folder(
        self, dir_repo
    ):
        """El fichero dado a mano tambien vuelve con `/`: en Windows
        `str(Path("src/a.txt"))` es `src\\a.txt`."""
        repo, env = dir_repo
        _write(repo, "docs/notes/n.txt", "new\n")
        rc, out, err = run_gitmem_script(
            ["wip", _MESSAGE, "--path", "docs/notes/n.txt", "--path", "src"],
            cwd=repo,
            env=env,
        )
        assert rc != 0
        paths = _paths_of(_relaunch_argv(out + err))
        assert paths == sorted(["docs/notes/n.txt", *_EXPECTED_LISTED]), paths


class TestFolderMixedWithFiles:
    def test_should_keep_given_files_and_add_the_folder_files_when_mixed(
        self, dir_repo
    ):
        repo, env = dir_repo
        _out, argv, status = _reject_and_relaunch(
            repo, env, ["--path", _CHANGED_OUTSIDE, "--path", "src"]
        )
        expected = sorted([_CHANGED_OUTSIDE, *_EXPECTED_LISTED])
        assert _paths_of(argv) == expected, argv
        assert status == sorted(
            [f"M\t{_CHANGED_OUTSIDE}", f"M\t{_CHANGED_TRACKED}",
             f"A\t{_CHANGED_UNTRACKED_NESTED}"]
        ), status

    def test_should_not_duplicate_a_file_given_both_alone_and_inside_its_folder(
        self, dir_repo
    ):
        repo, env = dir_repo
        rc, out, err = run_gitmem_script(
            ["wip", _MESSAGE, "--path", _CHANGED_TRACKED, "--path", "src"],
            cwd=repo,
            env=env,
        )
        assert rc != 0
        argv = _relaunch_argv(out + err)
        assert _paths_of(argv) == _EXPECTED_LISTED, argv
        assert argv.count("--path") == len(_EXPECTED_LISTED), argv


def test_should_say_there_is_nothing_and_offer_no_relaunch_when_folder_is_clean(
    dir_repo,
):
    repo, env = dir_repo
    _write(repo, "clean/kept.txt", "committed\n")
    _git(repo, "add", "clean/kept.txt")
    _git(repo, "commit", "-m", "clean folder")
    head_before = _git(repo, "rev-parse", "HEAD")

    rc, out, err = run_gitmem_script(
        ["wip", _MESSAGE, "--path", "clean"], cwd=repo, env=env
    )
    combined = out + err

    assert rc != 0, combined
    assert _git(repo, "rev-parse", "HEAD") == head_before
    assert "clean" in combined, combined
    assert "clean/kept.txt" not in combined, combined
    assert _relaunch_lines(combined) == [], combined
    leaked = [word for word in _JARGON if word in combined]
    assert leaked == [], combined


def test_should_list_only_the_new_name_of_a_renamed_file(dir_repo):
    """Renombrado preparado (`git mv`): con `-z` git trae detras la ruta de
    origen; si se tomara como otra entrada saldria basura (`c/untouched.txt`)
    o el nombre viejo, que ya no existe y haria fallar el relanzamiento."""
    repo, env = dir_repo
    _git(repo, "mv", _UNCHANGED_TRACKED, "src/moved.txt")

    rc, out, err = run_gitmem_script(
        ["wip", _MESSAGE, "--path", "src"], cwd=repo, env=env
    )
    combined = out + err

    assert rc != 0
    paths = _paths_of(_relaunch_argv(combined))
    assert paths == sorted([*_EXPECTED_LISTED, "src/moved.txt"]), paths
    assert _UNCHANGED_TRACKED not in combined, combined
    assert "c/untouched.txt" not in combined, combined


def test_should_relaunch_relative_to_the_subfolder_it_was_run_from(dir_repo):
    """Cerberus #104.3 F2.1: lanzado desde `src/`, las rutas salen relativas
    a `src/` y el relanzamiento, ejecutado desde ahi mismo, comitea justo
    `src/sub/new.txt`."""
    repo, env = dir_repo
    out, argv, status = _reject_and_relaunch(
        repo, env, ["--path", "sub"], cwd=os.path.join(repo, "src")
    )
    assert _paths_of(argv) == ["sub/new.txt"], argv
    assert status == [f"A\t{_CHANGED_UNTRACKED_NESTED}"], status


def test_should_list_and_commit_a_deleted_file_inside_the_folder(dir_repo):
    """Cerberus #104.3 F2.2: un fichero seguido borrado dentro de la carpeta
    entra en el listado y el relanzamiento deja el borrado en el commit."""
    repo, env = dir_repo
    os.remove(os.path.join(repo, _UNCHANGED_TRACKED))

    out, argv, status = _reject_and_relaunch(repo, env, ["--path", "src"])

    assert _UNCHANGED_TRACKED in out, out
    assert _paths_of(argv) == sorted([*_EXPECTED_LISTED, _UNCHANGED_TRACKED])
    assert status == sorted(
        [f"M\t{_CHANGED_TRACKED}", f"A\t{_CHANGED_UNTRACKED_NESTED}",
         f"D\t{_UNCHANGED_TRACKED}"]
    ), status
