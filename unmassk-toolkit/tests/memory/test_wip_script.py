"""Contrato de `bin/memory/wip.py` -- PIEZAS.md Sec.10 (fila `wip.py`) +
Sec.10.1 punto 4.

`wip.py` YA EXISTE (nacio 2026-08-03) y NO ha pasado todavia por ningun
revisor -- este es su checkpoint. A diferencia de los otros nueve
scripts de `bin/memory/`, es el UNICO sin su propio fichero de tests:
solo lo ejercitaban dos tests de `test_gitmem_facade.py`, y los dos lo
lanzan a traves de la fachada `gitmem`, nunca al script solo. Estos
tests SI lo invocan directamente (`run_memory_script("wip.py", ...)`),
mismo patron que `test_work_script.py` (su hermano mas cercano: mismo
`lib/memory/repo_guard.py`, misma mecanica de `notes.write_work()`).

Estos tests NO nacen en rojo -- la pieza ya existe. Nacen en verde, o
destapan un fallo real en `bin/memory/wip.py` /
`lib/memory/repo_guard.py` / `lib/memory/notes_commit.py::write_work`.

De donde sale cada cosa (leido en el codigo real, no de oidas):

- `bin/memory/wip.py` (leido entero antes de escribir esto): antepone
  `emojis.CHANNEL_EMOJI["wip"]` al mensaje, llama a
  `notes.write_work(marked_message, paths, None, known_content=...)`,
  protege la rama principal con `lib/memory/repo_guard.py` (misma
  mecanica que `work.py`), lee cada `--path` con `path.read_bytes()`
  como primerisima accion (antes de `notes.repo_root()`,
  `config.load()` o el chequeo de rama), y NO admite `--issue` --
  `_parse_args()` solo declara `message` y `--path` (`action="append",
  required=True`).
- `docs/memoria-v2/PIEZAS.md` Sec.10.1 punto 4: la decision del
  propietario que gobierna la proteccion de rama de `wip.py` ("el
  checkpoint protege la rama principal, con la misma proteccion que
  work.py") -- dos controles DISTINTOS: la aduana (customs.py, ya
  exime al wip en `test_customs_hook.py`, fuera del alcance de este
  fichero) y la proteccion de rama (este fichero). Ningun test de aqui
  toca customs.py.
- `lib/memory/repo_guard.py` (leido entero): `PROTECTED_REPO_TYPE =
  "gitflow"`, `MAIN_BRANCH_NAMES = frozenset({"main", "master"})`,
  `protected_branch_rejection()` -- mismo texto que ya usaba `work.py`
  antes del traslado (2026-08-03).
- `lib/memory/config.py::load()`: sin `config.json`, `repo_type` cae en
  `"gitflow"` (fail-closed) -- el caso mas peligroso, un proyecto recien
  instalado sin ajuste todavia.
- `lib/memory/emojis.py::CHANNEL_EMOJI["wip"]` (`"🚧"`) y
  `lib/memory/validator.py::is_wip()` -- el marcador que `wip.py`
  escribe y el que un consumidor real (la aduana) reconoce vienen del
  MISMO valor (`validator._WIP_MARKER` lee `CHANNEL_EMOJI["wip"]`); los
  tests de aqui comparan contra esos DOS modulos reales, nunca contra
  un `"🚧"` tecleado a mano.

Round trip real, sin fabricar el texto esperado (unmassk-standards
Sec.34): el marcador del titular se deriva de `emojis.CHANNEL_EMOJI`
(productor real) y se verifica con `validator.is_wip()` (consumidor
real) -- nunca comparando contra un emoji copiado a mano. El contenido
comiteado se compara contra los BYTES escritos en disco por el propio
test antes de invocar el script (`git show HEAD:<ruta>` en crudo, nunca
contra lo que el script "dice" que hizo).

DEUDA.md PARTE 1 B22 (2026-08-04, decision del propietario): "dos
procesos a la vez no va a pasar nunca" -- ningun test de aqui prueba
concurrencia. La cobertura de esa carrera (el punto 27, `known_content`
pasado a `write_work()`) ya vive, y en profundidad, en
`test_notes.py::test_regression_two_real_processes_writing_same_file_
never_commit_crossed_content_under_ok_true` -- este fichero solo
comprueba el CABLEADO de `wip.py` (lee antes de tocar git, pasa los
bytes, no los vuelve a leer), no la seguridad bajo carrera.
"""

import json
import os

import pytest

from .conftest import (
    import_lib_memory_module,
    run_git,
    run_memory_script,
    seed_config_json,
)


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


def _git_head_subject(repo):
    rc, out, err = run_git(["log", "-1", "--format=%s"], repo)
    assert rc == 0, f"git log fallo en el test: {err}"
    return out


def _git_head_message(repo):
    rc, out, err = run_git(["log", "-1", "--pretty=%B", "HEAD"], repo)
    assert rc == 0, f"git log fallo en el test: {err}"
    return out


def _git_show_bytes(repo, ref):
    """Contenido REAL del blob comiteado, en crudo -- nunca a traves de
    lo que el script imprime. `subprocess` en binario (no `run_git`, que
    fuerza texto/utf-8) para no mangler bytes no-UTF8 en el round trip
    de contenido binario.
    """
    import subprocess

    result = subprocess.run(
        ["git", "show", ref], cwd=repo, capture_output=True
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _write_file(repo, relative_path, content="MARK content\n"):
    full_path = os.path.join(repo, relative_path)
    os.makedirs(os.path.dirname(full_path) or repo, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return full_path


def _write_bytes(repo, relative_path, content_bytes):
    full_path = os.path.join(repo, relative_path)
    os.makedirs(os.path.dirname(full_path) or repo, exist_ok=True)
    with open(full_path, "wb") as fh:
        fh.write(content_bytes)
    return full_path


@pytest.fixture
def emojis_mod():
    return import_lib_memory_module("emojis")


@pytest.fixture
def validator_mod():
    return import_lib_memory_module("validator")


class TestPrependsWipMarkerAndCommitsViaWriteWork:
    """Punto 1 del encargo: antepone `emojis.CHANNEL_EMOJI["wip"]` al
    mensaje y comitea de verdad via `notes.write_work()`. Round trip real
    contra los DOS modulos reales (productor del emoji + consumidor que
    lo reconoce), nunca un `"🚧"` tecleado a mano."""

    def test_commit_subject_carries_the_real_wip_marker_that_validator_is_wip_recognizes(
        self, tmp_repo, emojis_mod, validator_mod
    ):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt", "MARK checkpoint content\n")
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "wip.py",
            ["mid-refactor snapshot, not final yet", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, "el checkpoint tiene que producir un commit real"

        subject = _git_head_subject(tmp_repo)
        marker = emojis_mod.CHANNEL_EMOJI["wip"]
        assert subject == f"[WIP] {marker} mid-refactor snapshot, not final yet", (
            f"el titular tiene que ser el marcador real + el mensaje tal cual: {subject!r}"
        )
        assert validator_mod.is_wip(subject), (
            f"validator.is_wip() (produccion) tiene que reconocer el titular real "
            f"que wip.py acaba de comitear: {subject!r}"
        )

    def test_stdout_prints_the_exact_marked_message_it_committed(self, tmp_repo, emojis_mod):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")

        rc, out, err = run_memory_script(
            "wip.py",
            ["confirm stdout echoes the marked message", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        marker = emojis_mod.CHANNEL_EMOJI["wip"]
        assert out.strip() == f"[WIP] {marker} confirm stdout echoes the marked message", (
            f"la confirmacion en pantalla tiene que ser el mismo titular que se comiteo: {out!r}"
        )


class TestNoIssueTrailerByDesign:
    """El propio docstring de `wip.py`: mismo grammar que `work.py` "menos
    `--issue`, que un checkpoint no referencia por diseño". Dos cosas
    distintas que probar: (a) `--issue` NO es un flag valido -- si se le
    diera silenciosamente la vuelta, la CLI habria dejado de seguir el
    contrato documentado; (b) un checkpoint sin `--issue` no lleva
    trailer `Issue:` en el cuerpo del commit (a diferencia de
    `work.py`)."""

    def test_issue_flag_is_rejected_by_the_real_argparse_grammar(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "wip.py",
            [
                "should not accept --issue", "--path", "fileA.txt",
                "--issue", "42",
            ],
            cwd=tmp_repo,
        )
        assert rc != 0, f"--issue no es un flag de wip.py, tiene que rebotar: stdout={out!r}"
        combined = out + err
        assert "Traceback" not in combined
        assert "--issue" in combined or "unrecognized" in combined.lower(), (
            f"el rechazo de argparse tiene que nombrar el flag no reconocido: {combined!r}"
        )
        after = _git_commit_count(tmp_repo)
        assert after == before, "un flag no reconocido no puede haber producido un commit"

    def test_commit_body_carries_no_issue_trailer(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")

        rc, out, err = run_memory_script(
            "wip.py",
            ["plain checkpoint, no issue reference", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        message = _git_head_message(tmp_repo)
        assert "Issue:" not in message, (
            f"un checkpoint no referencia una issue por diseño -- el mensaje no puede "
            f"llevar el trailer 'Issue:': {message!r}"
        )


class TestCommitsExactlyGivenPathsWithTheRealBytesOnDisk:
    """Filas 1 y 4 combinadas con el punto 4 del encargo: el commit toca
    EXACTAMENTE las rutas dadas (nunca el resto del arbol) y el contenido
    comiteado es, byte a byte, el que estaba en disco al invocar el
    script -- verificado contra `git show` en crudo, nunca contra lo que
    el script dice."""

    def test_two_paths_in_one_call_touch_only_those_two_files(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt", "MARK content A\n")
        _write_file(tmp_repo, "fileB.txt", "MARK content B\n")
        _write_file(tmp_repo, "fileC_untouched.txt", "MARK content C, must not be committed\n")

        before = _git_commit_count(tmp_repo)
        rc, out, err = run_memory_script(
            "wip.py",
            [
                "checkpoint two files",
                "--path", "fileA.txt",
                "--path", "fileB.txt",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        after = _git_commit_count(tmp_repo)
        assert after == before + 1

        assert _git_files_changed(tmp_repo) == ["fileA.txt", "fileB.txt"], (
            "el checkpoint arrastro algo fuera de las rutas dadas, o le faltan"
        )

    def test_committed_content_matches_the_real_bytes_written_before_invocation(self, tmp_repo):
        # Contenido no-UTF8 a proposito: si wip.py leyera en modo texto
        # (en vez de path.read_bytes(), como documenta su propio
        # comentario "leido como la PRIMERISIMA accion"), esto fallaria
        # al decodificar o mangleria los bytes antes de llegar a git.
        seed_config_json(tmp_repo, repo_type="trunk")
        raw_bytes = b"MARK binary payload \xe9\xff\x00 not valid utf-8\n"
        _write_bytes(tmp_repo, "binary.dat", raw_bytes)

        rc, out, err = run_memory_script(
            "wip.py",
            ["checkpoint with raw non-utf8 bytes on disk", "--path", "binary.dat"],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        committed = _git_show_bytes(tmp_repo, "HEAD:binary.dat")
        assert committed == raw_bytes, (
            f"el contenido comiteado tiene que ser EXACTAMENTE el que estaba en disco "
            f"al invocar el script: esperado={raw_bytes!r} comiteado={committed!r}"
        )


class TestKnownContentFallsBackToDiskWhenPathIsUnreadable:
    """Punto 4 del encargo, la otra mitad: si la ruta no se puede leer
    ANTES de tocar git (`OSError` en `path.read_bytes()`), `wip.py` no
    revienta -- pasa `None` para esa ruta y deja que `write_work()` (y
    por debajo, `git add`) trate el fallo de la forma real: el error de
    `git add` sobre un pathspec inexistente, no un traceback de Python."""

    def test_nonexistent_path_fails_with_the_real_git_pathspec_error_not_a_crash(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "wip.py",
            ["checkpoint a path that is not there", "--path", "does_not_exist.txt"],
            cwd=tmp_repo,
        )
        assert rc != 0, f"una ruta inexistente tiene que fallar: stdout={out!r}"
        combined = out + err
        assert "Traceback" not in combined
        assert "does_not_exist.txt" in combined, (
            f"el error real de git ('pathspec ... did not match') tiene que nombrar "
            f"la ruta: {combined!r}"
        )

        after = _git_commit_count(tmp_repo)
        assert after == before, "una ruta inexistente no puede haber producido un commit"


class TestWriteWorkGitFailurePassesThroughVerbatim:
    """`main()` de `wip.py`: `if not result.ok: print(f"git fallo al
    commitear: {result.git_error}", ...); return 1` -- una rama propia de
    este script, distinta de la de `does_not_exist.txt` de arriba (esa
    falla dentro de `stage_and_commit`/`git add`; esta prueba que un
    fallo de `git commit` en si -- con el `add` ya completado -- tambien
    sale por esta rama, sin traceback y sin dejar HEAD movido."""

    def test_real_git_index_lock_surfaces_the_real_git_error_not_a_traceback(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        lock_path = os.path.join(tmp_repo, ".git", "index.lock")
        with open(lock_path, "w", encoding="utf-8"):
            pass
        try:
            rc, out, err = run_memory_script(
                "wip.py",
                ["should not commit, index is locked", "--path", "fileA.txt"],
                cwd=tmp_repo,
            )
        finally:
            os.remove(lock_path)

        assert rc != 0, f"con .git/index.lock puesto, el checkpoint tiene que fallar: stdout={out!r}"
        combined = out + err
        assert "Traceback" not in combined
        assert "index.lock" in combined, (
            f"el error real de git tiene que llegar a la salida: {combined!r}"
        )


class TestProtectedRepoRejectsDirectCheckpointToMainBranch:
    """Sec.10.1 punto 4: "wip.py protege la rama principal igual que
    work.py, y no duplicando el control" -- decision del propietario
    2026-08-03. Mismo montaje y misma tecnica de EFECTO que
    `test_work_script.py::TestProtectedRepoRejectsDirectCommitToMain
    Branch`: ningun texto fija la redaccion exacta del rechazo (lo
    imprime `repo_guard.protected_branch_rejection()`, sin plantilla en
    TEXTOS.md), asi que se comprueba EFECTO -- codigo de retorno
    distinto de cero, cero traceback, salida no vacia ("dice que
    hacer"), y sobre todo -- lo que demuestra que el rechazo es real y
    no un aviso a medias -- CERO commits nuevos y el mismo SHA de HEAD
    antes y despues.

    Esta clase prueba la PROTECCION DE RAMA -- un control distinto de
    la exencion de la aduana (que `wip` no reciba preguntas de
    `hooks/customs.py`, ya cubierto en `test_customs_hook.py`). Ningun
    test de aqui toca customs.py -- confundir los dos controles esta
    explicitamente descartado por el encargo."""

    def test_gitflow_repo_type_on_main_branch_rejects_without_committing(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="gitflow")
        _write_file(tmp_repo, "fileA.txt")
        before_count = _git_commit_count(tmp_repo)
        before_sha = _git_head_sha(tmp_repo)

        rc, out, err = run_memory_script(
            "wip.py",
            ["should not checkpoint directly to a protected main", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc != 0, (
            f"repo_type=gitflow en la rama principal tiene que rebotar el checkpoint: "
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

    def test_missing_config_defaults_to_protected_and_rejects_checkpoint_on_main(self, tmp_repo):
        # Sin config.json en absoluto: config.py cae en su default
        # fail-closed (repo_type="gitflow", "main protegido si no se
        # declara"). El caso mas peligroso -- un proyecto recien
        # instalado, sin ningun ajuste todavia.
        _write_file(tmp_repo, "fileA.txt")
        before_count = _git_commit_count(tmp_repo)
        before_sha = _git_head_sha(tmp_repo)

        rc, out, err = run_memory_script(
            "wip.py",
            ["should not checkpoint, missing config defaults to protected", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc != 0, (
            f"sin config.json, el default protegido tiene que rebotar el checkpoint "
            f"en la rama principal: stdout={out!r} stderr={err!r}"
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

    def test_rejection_text_matches_the_real_repo_guard_output_verbatim(
        self, tmp_repo
    ):
        """Round trip real (unmassk-standards Sec.34): el texto del
        rechazo se compara contra `repo_guard.protected_branch_rejection()`
        (produccion, la MISMA funcion que `wip.py` llama por dentro),
        nunca contra una cadena tecleada a mano en el test."""
        repo_guard_mod = import_lib_memory_module("repo_guard")
        seed_config_json(tmp_repo, repo_type="gitflow")
        _write_file(tmp_repo, "fileA.txt")

        rc, out, err = run_memory_script(
            "wip.py",
            ["checkpoint that must echo the real rejection text", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc != 0

        rc_branch, branch_name, err_branch = run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], tmp_repo
        )
        assert rc_branch == 0, err_branch
        expected_text = repo_guard_mod.protected_branch_rejection(branch_name)
        combined = out + err
        assert expected_text in combined, (
            f"el rechazo real tiene que ser el que produce repo_guard.py, no un texto "
            f"distinto -- esperado:\n{expected_text}\n\nsalida real:\n{combined}"
        )


class TestTrunkRepoTypeAllowsDirectCheckpointToMainBranch:
    """El otro lado de la misma regla: `repo_type="trunk"` (declarado
    explicitamente) es el caso en el que un checkpoint directo a la rama
    principal es legitimo -- no puede rebotar."""

    def test_trunk_repo_type_on_main_branch_commits_the_checkpoint(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "wip.py",
            ["trunk repo allows a direct checkpoint on main", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        after = _git_commit_count(tmp_repo)
        assert after == before + 1, "repo_type=trunk en main tiene que permitir el checkpoint"


class TestCorruptConfigFailsLoudNeverATraceback:
    """`config.load()` "un fichero corrupto FALLA EN ALTO" (su propio
    docstring): `repo_type` no-texto lanza `ValueError`. `wip.py` no
    envuelve esa llamada en ningun try propio -- el `except Exception`
    de nivel superior (`if __name__ == "__main__":`) es la unica red, y
    tiene que imprimir `"wip.py: <mensaje>"` por stderr, nunca una traza
    de pila. Rama distinta de las de rechazo de rama/git ya cubiertas
    arriba -- esta es la del manejador de excepcion generico."""

    def test_repo_type_not_a_string_fails_loud_via_the_generic_handler(self, tmp_repo):
        pm = os.path.join(tmp_repo, ".claude", "project-memory")
        os.makedirs(pm, exist_ok=True)
        with open(os.path.join(pm, "config.json"), "w", encoding="utf-8") as fh:
            json.dump({"repo_type": 42}, fh)
        _write_file(tmp_repo, "fileA.txt")
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "wip.py",
            ["should fail loud on a corrupt config.json", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc != 0, f"config.json corrupto tiene que fallar: stdout={out!r}"
        combined = out + err
        assert "Traceback" not in combined, (
            f"el manejador generico de wip.py tiene que imprimir el mensaje, "
            f"nunca dejar pasar una traza de pila: {combined!r}"
        )
        assert combined.strip() != "", "el fallo tiene que decir algo, no salir en silencio"
        assert "wip.py:" in combined, (
            f"el prefijo del manejador generico ('wip.py: <mensaje>') tiene que "
            f"aparecer en la salida: {combined!r}"
        )

        after = _git_commit_count(tmp_repo)
        assert after == before, "un config.json corrupto no puede haber producido un commit"


class TestForceUtf8StreamsFirstStatement:
    def test_accented_message_survives_a_restricted_console_encoding(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        rc, out, err = run_memory_script(
            "wip.py",
            ["añadir soporte a café ☕ en el checkout", "--path", "fileA.txt"],
            cwd=tmp_repo,
            env={"PYTHONIOENCODING": "cp1252", "LANG": "C", "LC_ALL": "C"},
        )
        combined = out + err
        assert "UnicodeEncodeError" not in combined
        assert "UnicodeDecodeError" not in combined
        assert "Traceback" not in combined
        assert rc == 0, f"un checkpoint valido no deberia fallar bajo cp1252: {combined!r}"


class TestRepoResolvedByProcessCwd:
    def test_launched_from_a_nested_subdirectory_still_commits_to_that_same_repo(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        nested = os.path.join(tmp_repo, "src", "some", "nested", "place")
        os.makedirs(nested, exist_ok=True)
        file_path = _write_file(tmp_repo, "fileA.txt")
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "wip.py",
            ["checkpoint committed from a nested cwd", "--path", file_path],
            cwd=nested,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, (
            "el checkpoint no aparecio en tmp_repo aunque el script se lanzo desde "
            "una subcarpeta suya -- ¿resuelve el repositorio por una ruta fija?"
        )
        assert _git_files_changed(tmp_repo) == ["fileA.txt"]
