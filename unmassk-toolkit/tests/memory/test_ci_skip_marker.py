"""Contrato ROJO para D-070 -- `gitmem work` y `gitmem wip` anaden
`[skip ci]` al mensaje del commit que crean, en SU PROPIA linea, para que
GitHub Actions no dispare CI en los pasos intermedios de trabajo (lo
respeta de forma nativa, sin tocar el workflow). `bin/release.py` NUNCA
lo anade -- su commit es el unico que SI dispara y verifica CI, y ese es
justamente el punto que mas importa blindar (ver `test_release.py`,
clase `TestReleaseCommitNeverCarriesTheSkipCiMarker`, para el guardian).

Modo test-first, PASE DE CONTRATO: aceptacion, no barrido exhaustivo de
ramas -- eso llega en el pase de endurecimiento, tras la implementacion
real de Ultron. Ningun test de aqui toca produccion.

De donde sale cada cosa (leido en el codigo real, no de oidas, antes de
escribir esto):

- `bin/memory/work.py:151` -- `notes.write_work(args.message, paths,
  args.issue, known_content=known_content)`.
- `bin/memory/wip.py:121-122` -- construye `marked_message = f"{_WIP_PREFIX}
  {_WIP_MARKER} {args.message}"` y llama a `notes.write_work(marked_message,
  paths, None, ...)`.
- `lib/memory/notes_commit.py:507` -- `full_message = message if issue is
  None else f"{message}\\n\\nIssue: #{issue}"` -- el punto de ensamblado
  COMPARTIDO por el que pasan `work.py`, `wip.py` Y `bin/release.py`. Si
  el marcador de skip-ci se anadiera AQUI (en vez de en cada script que
  SI debe llevarlo), el release tambien se lo llevaria de regalo --
  exactamente el fallo silencioso que `test_release.py` esta puesto a
  cazar.
- `lib/memory/gitcmd.py:211-215` -- `git commit --cleanup=verbatim -m
  <mensaje>`, nada se recorta.
- `lib/memory/health_plans.py:68` -- `_ISSUE_TRAILER_RE =
  re.compile(r"^Issue: #(\\d+)$", re.MULTILINE)`, la red de seguridad del
  arranque que reporta "N commits citando la issue #X sin reflejar".
  Anclado por LINEA ENTERA: un marcador que aterrizara en la MISMA linea
  que el trailer lo mataria en silencio -- la regresion que mas importa
  de este contrato (punto 2 mas abajo).
- `lib/memory/validator.py::is_wip()` -- `subject.startswith((f"{_WIP_PREFIX}
  {_WIP_MARKER}", _WIP_MARKER))`, el consumidor real que reconoce un
  checkpoint por su TITULAR (primera linea del commit, `git log
  --format=%s`) -- una linea nueva en el CUERPO del mensaje no le afecta,
  pero se comprueba en vivo de todas formas (round trip real, nunca
  supuesto).

TECNICA REUTILIZADA de `test_work_issue_field.py`/`test_health.py`
(unmassk-standards Sec.34.5 -- mock solo cuando la dependencia no puede
correr aqui): `--issue N` en `work.py` llama a `gh` para comprobar que la
issue existe -- un `gh` FALSO se antepone al `PATH` del proceso hijo
(mismo helper que `test_work_issue_field.py`, no reimplementado desde
cero). `health_plans.plans_unreflected()` corre EN PROCESO (se importa
via `import_lib_memory_module`), asi que su propia llamada a `gh` se
intercepta con `monkeypatch.setattr(subprocess, "run", ...)`, igual que
`test_health.py::_patch_gh` -- nunca se finge git, solo `gh`.

Ningun texto de este proyecto fija que forma EXACTA usa GitHub Actions
para reconocer el marcador salvo la que la propia decision D-070 ya cita
literalmente (`gitmem search --id D-070`): `[skip ci]`. Los tests de
aqui comprueban esa forma exacta, en su propia linea, con
`re.IGNORECASE` solo para tolerar mayusculas -- nunca inventando una
variante (`skip-ci` sin corchetes, etc.) que ningun documento del
proyecto pide.
"""

import json
import os
import re
import subprocess
import sys

import pytest

from .conftest import (
    import_lib_memory_module,
    path_without_real_gh,
    run_git,
    run_memory_script,
    seed_config_json,
)

# Mismo incidente de CI (2026-08-22) que ya documenta
# `test_work_issue_field.py` -- en Windows, `subprocess.run(["gh", ...])`
# sin `shell=True` nunca resuelve un fichero sin extension `.exe` via
# CreateProcess. Se salta explicito solo en los tests que dependen de que
# el `gh` falso GANE la resolucion de `PATH`.
_WIN_GH_SKIP_REASON = (
    "tecnica de gh falso en PATH: en Windows, subprocess.run(['gh', ...]) "
    "sin shell=True nunca resuelve un fichero sin extension .exe -- "
    "estructural, no arreglable sin tocar validator_issue.py (fuera de "
    "alcance de Dante)"
)
_skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason=_WIN_GH_SKIP_REASON)

# La forma EXACTA que D-070 cita literalmente, en su propia linea del
# mensaje de commit (permitiendo espacio en blanco alrededor, nunca texto
# adicional en la misma linea -- eso es justo lo que "propia linea"
# significa).
_SKIP_CI_OWN_LINE_RE = re.compile(r"^\s*\[skip ci\]\s*$", re.IGNORECASE | re.MULTILINE)


def _git_head_message(repo):
    rc, out, err = run_git(["log", "-1", "--pretty=%B", "HEAD"], repo)
    assert rc == 0, f"git log fallo en el test: {err}"
    return out


def _git_head_subject(repo):
    rc, out, err = run_git(["log", "-1", "--format=%s"], repo)
    assert rc == 0, f"git log fallo en el test: {err}"
    return out


def _write_file(repo, relative_path, content="MARK content\n"):
    full_path = os.path.join(repo, relative_path)
    os.makedirs(os.path.dirname(full_path) or repo, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return full_path


def _fake_gh_dir(tmp_path, *, mode, issue_number, dirname="fake-gh-bin"):
    """Mismo `gh` falso, minimo, que `test_work_issue_field.py::_fake_gh_dir`
    -- solo entiende `gh issue view <N> --json number`, imita la FORMA de
    la herramienta real (codigo de retorno), nunca su logica. Aqui solo
    hace falta `mode="exists"` (la issue es real segun el gh falso), asi
    que es un subconjunto deliberadamente mas pequeno que el original.
    """
    gh_dir = tmp_path / dirname
    gh_dir.mkdir(exist_ok=True)
    gh_path = gh_dir / "gh"
    script = f'''#!/usr/bin/env python3
import sys

MODE = {mode!r}
ISSUE = {str(issue_number)!r}

args = sys.argv[1:]
if len(args) >= 3 and args[0] == "issue" and args[1] == "view" and args[2] == ISSUE:
    if MODE == "exists":
        sys.stdout.write('{{"number": ' + ISSUE + '}}')
        sys.exit(0)

sys.stderr.write("fake gh (dante D-070 test double): unexpected invocation " + repr(args))
sys.exit(97)
'''
    gh_path.write_text(script, encoding="utf-8")
    gh_path.chmod(0o755)
    return str(gh_dir)


def _env_with_fake_gh(fake_gh_dir):
    return {"PATH": fake_gh_dir + os.pathsep + path_without_real_gh()}


class TestWorkCommitCarriesSkipCiOnItsOwnLine:
    """Punto 1 del encargo. ROJO real hoy: `work.py` llama a
    `notes.write_work(args.message, ...)` sin tocar `args.message` en
    absoluto -- ningun marcador se anade todavia."""

    def test_plain_work_commit_carries_the_skip_ci_marker_on_its_own_line(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")

        rc, out, err = run_memory_script(
            "work.py",
            ["checkpoint work that must skip ci", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        message = _git_head_message(tmp_repo)
        assert _SKIP_CI_OWN_LINE_RE.search(message), (
            "D-070: un commit de 'gitmem work' tiene que llevar el marcador "
            f"'[skip ci]' en su propia linea -- mensaje real:\n{message!r}"
        )


class TestWorkCommitWithIssueKeepsBothTrailersOnSeparateLines:
    """Punto 2 del encargo -- el que MAS importa: el marcador de skip-ci
    no puede aterrizar en la MISMA linea que el trailer `Issue: #N`,
    porque `health_plans.py` lo busca anclado por LINEA ENTERA
    (`^Issue: #(\\d+)$`). Se llama al regex REAL de produccion, nunca a
    una copia tecleada a mano en este fichero -- si algun dia ese regex
    cambia, este test cambia de significado con el, no se queda mintiendo
    contra una version vieja."""

    @_skip_on_windows
    def test_issue_trailer_still_matches_health_plans_real_regex_alongside_the_marker(
        self, tmp_repo, tmp_path
    ):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        issue_number = 4242
        fake_gh_dir = _fake_gh_dir(tmp_path, mode="exists", issue_number=issue_number)
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = run_memory_script(
            "work.py",
            ["wire the retry flow", "--path", "fileA.txt", "--issue", str(issue_number)],
            cwd=tmp_repo,
            env=env,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        message = _git_head_message(tmp_repo)
        assert _SKIP_CI_OWN_LINE_RE.search(message), (
            "el commit de trabajo con --issue tambien tiene que llevar el "
            f"marcador '[skip ci]' en su propia linea: {message!r}"
        )

        health_plans_mod = import_lib_memory_module("health_plans")
        match = health_plans_mod._ISSUE_TRAILER_RE.search(message)
        assert match is not None and int(match.group(1)) == issue_number, (
            "el trailer 'Issue: #N' tiene que seguir casando, ENTERO y SOLO "
            "en su propia linea, con el regex REAL y ANCLADO de "
            "health_plans.py -- si el marcador de skip-ci aterrizara en la "
            "MISMA linea que el trailer, este regex dejaria de encontrarlo "
            f"en silencio -- mensaje real:\n{message!r}"
        )


class TestBootSafetyNetStillCountsAWorkCommitCarryingSkipCi:
    """Punto 3 del encargo -- la red de seguridad del arranque
    (`health_plans.plans_unreflected()`, el consumidor REAL del regex de
    arriba) tiene que seguir contando un commit de `gitmem work --issue N`
    real, aunque ahora lleve el marcador de skip-ci de mas. Se ejercita el
    PUNTO DE ENTRADA real de produccion (no una regex copiada aparte): si
    el marcador rompiera el anclaje por linea del trailer, esta cuenta
    bajaria a cero SIN avisar -- exactamente el fallo silencioso que esta
    pieza existe para impedir."""

    @_skip_on_windows
    def test_work_issue_commit_with_skip_ci_marker_is_still_counted_as_unreflected(
        self, tmp_repo, tmp_path, monkeypatch
    ):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")
        issue_number = 4747
        fake_gh_dir = _fake_gh_dir(tmp_path, mode="exists", issue_number=issue_number)
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = run_memory_script(
            "work.py",
            [
                "citing an issue, must still be counted by the boot safety net",
                "--path", "fileA.txt",
                "--issue", str(issue_number),
            ],
            cwd=tmp_repo,
            env=env,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        health_plans_mod = import_lib_memory_module("health_plans")

        # `plans_unreflected()` corre EN PROCESO (a diferencia de work.py,
        # lanzado como subproceso arriba) -- se intercepta solo su propia
        # llamada a `gh`, nunca los `git log` reales que necesita para leer
        # el historial: mismo patron que `test_health.py::_patch_gh`, no
        # reimplementado a ciegas.
        real_run = subprocess.run
        gh_calls = []

        def _fake_run(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if cmd and cmd[0] == "gh":
                gh_calls.append(list(cmd))
                payload = json.dumps({"comments": [], "createdAt": "2020-01-01T00:00:00Z"})
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=payload, stderr="")
            return real_run(*args, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        previous_cwd = os.getcwd()
        os.chdir(tmp_repo)
        try:
            result = health_plans_mod.plans_unreflected()
        finally:
            os.chdir(previous_cwd)

        assert result == ((issue_number, 1),), (
            "el commit real de 'gitmem work --issue N' (ahora con el "
            "marcador de skip-ci anadido) tiene que seguir contando como "
            f"'sin reflejar' -- plans_unreflected() devolvio {result!r}"
        )
        assert len(gh_calls) == 1, (
            f"se esperaba UNA consulta a gh (una por issue) -- se observaron "
            f"{len(gh_calls)}: {gh_calls!r}"
        )


class TestWipCommitCarriesSkipCiAndStaysRecognizedAsWip:
    """Punto 4 del encargo. Round trip real (unmassk-standards Sec.34):
    `validator.is_wip()` es el consumidor de produccion, comparado contra
    el TITULAR real que `wip.py` acaba de comitear -- nunca un `"🚧"`
    tecleado a mano."""

    def test_wip_commit_carries_skip_ci_marker_and_validator_is_wip_still_true(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        _write_file(tmp_repo, "fileA.txt")

        rc, out, err = run_memory_script(
            "wip.py",
            ["mid-refactor checkpoint that must skip ci", "--path", "fileA.txt"],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        message = _git_head_message(tmp_repo)
        assert _SKIP_CI_OWN_LINE_RE.search(message), (
            f"un checkpoint de 'gitmem wip' tiene que llevar '[skip ci]' en "
            f"su propia linea: {message!r}"
        )

        validator_mod = import_lib_memory_module("validator")
        subject = _git_head_subject(tmp_repo)
        assert validator_mod.is_wip(subject), (
            "el marcador de skip-ci (anadido al CUERPO del mensaje) no puede "
            "romper el reconocimiento real de validator.is_wip() sobre el "
            f"TITULAR del commit -- titular real: {subject!r}"
        )
