"""Contrato de aceptacion, en ROJO -- `bin/memory/work.py --issue N` no
comprueba que esa issue exista de verdad (hallazgo de Argus).

Modo test-first, PASE DE CONTRATO: estos cuatro items son los que
definen "hecho" para este arreglo, a granularidad de aceptacion -- no el
barrido de ramas (ese llega en el pase de endurecimiento, tras la
implementacion real de Ultron). Ningun test de aqui toca produccion.

LA DECISION DE DISENO YA TOMADA, y que fija que assertion espera cada
clase (encargo del propietario, dos reglas):

1. Fallo de infraestructura de `gh` (no instalado, sin red, timeout, o
   cualquier respuesta que no sea el "no existe" real) -> el commit de
   trabajo SE HACE IGUAL, avisando por stderr. Perder un checkpoint por
   estar sin red es peor que el problema que arreglamos.
2. `gh` SI contesta y dice que la issue no existe -> se RECHAZA, cero
   commit nuevo.

QUE ES ROJO DE VERDAD HOY, y que NO (honestidad, mismo criterio que
`test_note_issue_field.py`; verificado CORRIENDO este fichero, no
supuesto): leido `bin/memory/work.py` antes de escribir esto -- hoy no
llama a `gh` en absoluto, para NINGUN valor de `--issue`. Consecuencia,
confirmada en vivo (3 rojos / 2 verdes de partida):

- Item 1 (numero inexistente -> rechazo): ROJO. Hoy `work.py` acepta y
  comitea cualquier numero, exista o no -- no hay ninguna comprobacion.
- Item 2 (numero existente -> pasa y el trailer entra): VERDE de
  partida -- ya pasa hoy, pero solo porque nada se comprueba, no porque
  el comportamiento correcto ya este implementado. Se deja como GUARDA
  de no-regresion para el caso positivo.
- Item 3 (fallo de infraestructura -> el commit se guarda igual, CON
  AVISO visible): el commit en si YA se guarda hoy (nada lo bloquea, no
  hay comprobacion), pero el AVISO no existe -- `work.py` hoy no imprime
  nada en stderr sobre `gh` en ningun caso. Las dos assertion de aviso
  son ROJAS de verdad hoy; las de "el commit se crea igual" son verdes
  de partida, dentro del MISMO test (no se separan: el encargo pide las
  dos cosas juntas, "se guarda... avisando").
- Item 4 (sin --issue no cambia nada): VERDE de partida -- hoy `work.py`
  jamas invoca `gh`, con o sin el flag. Se deja como GUARDA: el arreglo
  no puede meter una llamada externa donde antes no la habia.

No se fuerza a un test verde a parecer rojo para cumplir una instruccion
generica -- se reporta el estado real, confirmado corriendo la suite.

TECNICA REUTILIZADA de `test_note_issue_field.py` (unmassk-standards
Sec.34.5: mock solo cuando la dependencia no puede correr aqui -- una
consulta de red no determinista es exactamente ese caso). `work.py`
corre como proceso hijo separado (`run_memory_script`), asi que un
`monkeypatch.setattr(subprocess, "run", ...)` en el proceso de test no
lo alcanza -- un `gh` FALSO y ejecutable se escribe en un directorio
propio y se antepone al `PATH` del hijo via `env=` (que solo AÑADE al
entorno heredado, `conftest.py::run_memory_script`, nunca lo sustituye
entero salvo que el test fije la clave `PATH` explicitamente -- lo que
el caso "gh no esta instalado" usa a proposito, ver `_path_without_gh`).
El `gh` falso solo imita la FORMA de la herramienta real (codigo de
retorno + el marcador textual exacto que `validator_issue.py::
_ISSUE_NOT_FOUND_MARKER` ya declara y tiene verificado en vivo) -- nunca
replica su logica.

Ningun texto de este proyecto fija la REDACCION exacta del rechazo de
`work.py` (a diferencia de los de `note.py`, que TEXTOS.md repite
literalmente) -- mismo criterio que ya usa `test_work_script.py` para
el rechazo de rama protegida: se comprueba EFECTO (codigo de retorno,
cero commit nuevo, HEAD sin moverse, el numero de issue nombrado, la
salida no vacia), nunca un texto inventado a mano.
"""

import os
import sys

import pytest

from .conftest import path_without_real_gh, run_git, run_memory_script, seed_config_json

# CI incident 2026-08-22 (conftest.py::path_without_real_gh): en Windows,
# `subprocess.run(["gh", ...])` sin `shell=True` (produccion, no tocada
# aqui) nunca resuelve un fichero sin extension `.exe` via CreateProcess
# -- estructural, no arreglable desde el lado del test. Se salta
# explicito, nunca en silencio, en los tests que dependen de que el `gh`
# falso GANE la resolucion de `PATH` (los que NO dependen de eso, como
# "gh ausente del PATH", no se saltan).
_WIN_GH_SKIP_REASON = (
    "tecnica de gh falso en PATH: en Windows, subprocess.run(['gh', ...]) "
    "sin shell=True nunca resuelve un fichero sin extension .exe -- "
    "estructural, no arreglable sin tocar validator_issue.py (fuera de "
    "alcance de Dante)"
)
_skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32", reason=_WIN_GH_SKIP_REASON
)


def _git_commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


def _git_head_sha(repo):
    rc, out, err = run_git(["rev-parse", "HEAD"], repo)
    assert rc == 0, f"git rev-parse fallo en el test: {err}"
    return out


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


def _fake_gh_dir(tmp_path, *, mode, issue_number, call_log=None, dirname="fake-gh-bin"):
    """Escribe un `gh` FALSO, ejecutable, en un directorio propio -- ver
    docstring del modulo para el porque (un proceso hijo no se puede
    parchear con `monkeypatch`). Entiende la UNICA forma real que
    `validator_issue.py::_issue_exists` invoca (`gh issue view <N>
    --json number`):

    - `mode="exists"`: returncode 0 (contenido de stdout irrelevante --
      `_issue_exists` solo mira `returncode == 0` para el caso positivo).
    - `mode="missing"`: returncode 1 con el marcador textual REAL en
      stderr, verificado en vivo contra `gh`
      (`validator_issue.py::_ISSUE_NOT_FOUND_MARKER`) -- "la issue no
      existe", rechazo real.
    - `mode="unrelated_error"`: returncode 1 con un stderr que NO lleva
      ese marcador (p.ej. un limite de peticiones) -- la otra forma real
      de fallo de infraestructura que el encargo pide simular, distinta
      de "gh no esta en el PATH".

    Si `call_log` se da, cada invocacion (con la forma que sea) añade una
    linea a ese fichero -- unico uso: probar que sin `--issue`, `gh`
    jamas se invoca (fichero ausente al final).

    Cualquier otra invocacion sale con returncode 97 y un stderr que la
    nombra -- ruidosa, no un cero inventado, si algun test la disparase
    sin querer.
    """
    gh_dir = tmp_path / dirname
    gh_dir.mkdir(exist_ok=True)
    gh_path = gh_dir / "gh"
    call_log_repr = repr(str(call_log)) if call_log is not None else "None"
    script = f'''#!/usr/bin/env python3
import sys

CALL_LOG = {call_log_repr}
MODE = {mode!r}
ISSUE = {str(issue_number)!r}

args = sys.argv[1:]
if CALL_LOG:
    with open(CALL_LOG, "a", encoding="utf-8") as fh:
        fh.write(" ".join(args) + "\\n")

if len(args) >= 3 and args[0] == "issue" and args[1] == "view" and args[2] == ISSUE:
    if MODE == "exists":
        sys.stdout.write('{{"number": ' + ISSUE + '}}')
        sys.exit(0)
    if MODE == "missing":
        sys.stderr.write(
            "GraphQL: Could not resolve to an issue or pull request with "
            "the number of " + ISSUE + ". (repository.issue)"
        )
        sys.exit(1)
    if MODE == "unrelated_error":
        sys.stderr.write(
            "error connecting to api.github.com: rate limit exceeded, try again later"
        )
        sys.exit(1)

sys.stderr.write("fake gh (dante test double): unexpected invocation " + repr(args))
sys.exit(97)
'''
    gh_path.write_text(script, encoding="utf-8")
    gh_path.chmod(0o755)
    return str(gh_dir)


def _env_with_fake_gh(fake_gh_dir):
    return {"PATH": fake_gh_dir + os.pathsep + path_without_real_gh()}


def _path_without_gh():
    """El `PATH` real heredado, MENOS cualquier directorio que contenga
    un `gh` de verdad -- no un `PATH` vacio (eso tambien se llevaria
    `git`, que `write_work()` necesita para comitear de verdad). Ahora
    delega en `conftest.py::path_without_real_gh()` (mismo filtro,
    generalizado tras el incidente de CI 2026-08-22 a los tres ficheros
    que fabrican un `gh` falso -- este era el original que lo motivo)."""
    return path_without_real_gh()


@_skip_on_windows
class TestNonexistentIssueRejectsWithoutCommitting:
    """Item 1 del encargo -- el UNICO rojo real hoy: `work.py` no llama a
    `gh` en absoluto, asi que un numero inventado se comitea igual que
    uno real. `git log` real, no lo que el script reclame, decide si
    hubo commit."""

    def test_bogus_issue_number_is_rejected_and_no_commit_is_created(self, tmp_repo, tmp_path):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        bogus_issue = 999999999
        fake_gh_dir = _fake_gh_dir(tmp_path, mode="missing", issue_number=bogus_issue)
        env = _env_with_fake_gh(fake_gh_dir)

        before_count = _git_commit_count(tmp_repo)
        before_sha = _git_head_sha(tmp_repo)

        rc, out, err = run_memory_script(
            "work.py",
            ["fix the checkout timeout bug", "--path", "fileA.txt", "--issue", str(bogus_issue)],
            cwd=tmp_repo,
            env=env,
        )
        assert rc != 0, (
            f"--issue {bogus_issue} (el gh falso confirma que NO existe) tendria "
            f"que rebotar -- salio rc=0, stdout={out!r} stderr={err!r}"
        )
        combined = out + err
        assert "Traceback" not in combined
        assert str(bogus_issue) in combined, (
            f"el rechazo deberia nombrar la issue #{bogus_issue} y como "
            f"relanzar -- salida real: {combined!r}"
        )
        assert combined.strip() != "", "el rechazo tiene que decir algo, no salir en silencio"

        after_count = _git_commit_count(tmp_repo)
        after_sha = _git_head_sha(tmp_repo)
        assert after_count == before_count and after_sha == before_sha, (
            "un rechazo que ya ha escrito no es un rechazo -- HEAD no puede "
            f"haberse movido: antes={before_sha!r} despues={after_sha!r}"
        )


@_skip_on_windows
class TestExistingIssuePassesAndTrailerEnters:
    """Item 2 del encargo. GUARDA, no rojo hoy (ver docstring del
    modulo): `work.py` ya comitea con el trailer para cualquier numero,
    porque no comprueba nada todavia -- esto tiene que seguir siendo
    cierto una vez que la comprobacion real este puesta, para el caso
    positivo."""

    def test_existing_issue_number_commits_with_real_trailer(self, tmp_repo, tmp_path):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        issue_number = 4242
        fake_gh_dir = _fake_gh_dir(tmp_path, mode="exists", issue_number=issue_number)
        env = _env_with_fake_gh(fake_gh_dir)

        before = _git_commit_count(tmp_repo)
        rc, out, err = run_memory_script(
            "work.py",
            ["wire the checkout retry flow", "--path", "fileA.txt", "--issue", str(issue_number)],
            cwd=tmp_repo,
            env=env,
        )
        assert rc == 0, (
            f"--issue {issue_number} (issue real, segun el gh falso) tendria que "
            f"comitear sin rebotar -- stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, "el commit no se creo"

        message = _git_head_message(tmp_repo)
        assert message.startswith("wire the checkout retry flow")
        assert f"Issue: #{issue_number}" in message, (
            f"el trailer real no lleva 'Issue: #{issue_number}' -- mensaje "
            f"real:\n{message!r}"
        )


class TestGhInfrastructureFailureNeverBlocksTheCommit:
    """Item 3 del encargo, las dos formas reales de fallo de
    infraestructura que el encargo nombra explicitamente: `gh` ausente
    del `PATH`, y `gh` presente pero respondiendo algo que no es "la
    issue no existe" (limite de peticiones, aqui).

    ROJO real hoy, para las dos: `work.py` hoy no llama a `gh` en
    absoluto, asi que el commit YA se crea (nada lo bloquea) pero el
    AVISO por stderr no existe -- `work.py` nunca imprime nada sobre
    `gh`. La assertion de "el commit se crea igual" es verde de partida;
    la de "avisa de forma visible" es la que falla hoy (confirmado
    corriendo la suite, ver docstring del modulo)."""

    def test_gh_not_on_path_still_commits_with_a_visible_warning(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        issue_number = 4242
        env = {"PATH": _path_without_gh()}

        before = _git_commit_count(tmp_repo)
        rc, out, err = run_memory_script(
            "work.py",
            [
                "checkpoint while gh is not installed",
                "--path", "fileA.txt",
                "--issue", str(issue_number),
            ],
            cwd=tmp_repo,
            env=env,
        )
        assert rc == 0, (
            f"gh ausente del PATH es un fallo de infraestructura -- no puede "
            f"bloquear el commit de trabajo: stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, "el commit tenia que crearse igual aunque gh no se pueda comprobar"

        message = _git_head_message(tmp_repo)
        assert f"Issue: #{issue_number}" in message

        assert err.strip() != "", (
            "un fallo de infraestructura tiene que avisar de forma visible "
            f"(stderr), no en silencio -- stderr real: {err!r}"
        )

    @_skip_on_windows
    def test_gh_answers_an_unrelated_error_still_commits_with_a_visible_warning(
        self, tmp_repo, tmp_path
    ):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        issue_number = 4242
        fake_gh_dir = _fake_gh_dir(tmp_path, mode="unrelated_error", issue_number=issue_number)
        env = _env_with_fake_gh(fake_gh_dir)

        before = _git_commit_count(tmp_repo)
        rc, out, err = run_memory_script(
            "work.py",
            [
                "checkpoint while gh answers something unrelated",
                "--path", "fileA.txt",
                "--issue", str(issue_number),
            ],
            cwd=tmp_repo,
            env=env,
        )
        assert rc == 0, (
            f"una respuesta de gh que no es 'no existe' es un fallo de "
            f"infraestructura -- no puede bloquear el commit: stdout={out!r} "
            f"stderr={err!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, "el commit tenia que crearse igual"

        message = _git_head_message(tmp_repo)
        assert f"Issue: #{issue_number}" in message

        assert err.strip() != "", (
            "un fallo de infraestructura tiene que avisar de forma visible "
            f"(stderr), no en silencio -- stderr real: {err!r}"
        )


@_skip_on_windows
class TestNoIssueFlagNeverCallsGh:
    """Item 4 del encargo. GUARDA hoy (ver docstring del modulo) --
    tiene que seguir siendo cierto tras la implementacion real: el
    arreglo no puede meter una llamada externa a `gh` donde antes no la
    habia, para el camino sin `--issue`."""

    def test_without_issue_flag_gh_is_never_invoked_and_commit_succeeds_normally(
        self, tmp_repo, tmp_path
    ):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        call_log = tmp_path / "gh-calls.log"
        fake_gh_dir = _fake_gh_dir(
            tmp_path, mode="exists", issue_number=1, call_log=str(call_log)
        )
        env = _env_with_fake_gh(fake_gh_dir)

        before = _git_commit_count(tmp_repo)
        rc, out, err = run_memory_script(
            "work.py",
            ["plain checkpoint without an issue flag", "--path", "fileA.txt"],
            cwd=tmp_repo,
            env=env,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        after = _git_commit_count(tmp_repo)
        assert after == before + 1

        message = _git_head_message(tmp_repo)
        assert "Issue:" not in message, (
            f"sin --issue no deberia aparecer ningun trailer 'Issue:' -- "
            f"mensaje real:\n{message!r}"
        )

        assert not call_log.exists(), (
            "sin --issue, gh no se deberia invocar en absoluto -- el fichero "
            "de llamadas del gh falso existe, algo lo invoco sin que se le "
            f"pidiera: {call_log.read_text(encoding='utf-8') if call_log.exists() else ''!r}"
        )
