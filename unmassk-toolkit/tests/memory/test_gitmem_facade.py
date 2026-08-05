"""Contrato ROJO de `bin/gitmem` -- PIEZAS.md Sec.10 (fila `bin/gitmem`,
"la fachada").

`bin/gitmem` NO EXISTE TODAVIA. Modo test-first, pase de CONTRATO:
aceptacion, no barrido exhaustivo.

`bin/gitmem` vive en `bin/`, no en `bin/memory/` -- se ejecuta con
`run_gitmem_script()` (`conftest.py`), no con `run_memory_script()`.

De donde sale cada cosa:

- PIEZAS.md Sec.10, fila `bin/gitmem`: "despacha al script del
  subcomando"; imprime "lo que devuelva el script; con `--version`, la
  version del toolkit".
- Los NUEVE subcomandos reales, tras el renombrado del propietario
  (2026-08-03, COLA.md Sec.4): `note` `work` `wip` `remove` `next`
  `search` `zones` `rezones` `rule`. `close`->`remove`,
  `context`->`next`, `reindex`->`rezones`; `bench` se borro entero;
  `boot` deja de ser subcomando; `wip` se anade (el checkpoint sin
  preguntas, agujero real destapado verificando `validator.is_wip()`).
- Regla propia de esta tarea: "que cada subcomando llega a su script, que
  uno desconocido falla diciendo cuales hay, y que NO añade logica propia
  -- solo reparte".
- `.claude-plugin/plugin.json` -- el `version` real del toolkit
  (`1.25.0` a fecha de escribir esto, pero el test lo LEE del propio
  fichero en vez de tecleario, para no fabricar el valor esperado).

Round trip real, sin fabricar el texto esperado (unmassk-standards
Sec.34): "llega a su script" se comprueba con el EFECTO real de un
subcomando que ya existe y esta en verde (`next`) -- un commit
genuinamente vacio, releido con `context.latest()` real (el modulo de
libreria sigue llamandose `context.py`; solo el script y el subcomando
se renombraron) -- nunca comparando la salida de `gitmem` contra un
texto tecleado a mano. Y "--version" se compara contra el JSON real de
`plugin.json`, leido en el mismo test, nunca contra el numero copiado a
mano.

Con el script inexistente, todos estos tests fallan hoy por la misma
causa real: `python3 <ruta inexistente>` -- ver docstring de
`test_note_script.py` para el detalle del mensaje.
"""

import contextlib
import json
import os

import pytest

from .conftest import (
    _TOOLKIT_ROOT,
    import_lib_memory_module,
    run_git,
    run_gitmem_script,
    run_memory_script,
    seed_config_json,
)

_NINE_SUBCOMMANDS = (
    "note", "work", "wip", "remove", "next", "search", "zones", "rezones", "rule",
)


@contextlib.contextmanager
def _cwd(path):
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _git_commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


class TestDispatchesToTheRealSubcommandScript:
    """El subcomando `next` llega a `bin/memory/next.py` de verdad --
    probado con el EFECTO real (un commit genuinamente vacio, releido con
    `context.latest()`, produccion), nunca con un texto inventado."""

    def test_gitmem_next_produces_the_same_real_effect_as_the_script_directly(
        self, tmp_repo
    ):
        context_lib = import_lib_memory_module("context")
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_gitmem_script(
            [
                "next", "dispatched through the gitmem facade",
                "--context", "prosa de contexto para el round trip",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, "el subcomando next tiene que producir un commit real"

        with _cwd(tmp_repo):
            latest = context_lib.latest()
        assert latest is not None
        assert latest.headline == "dispatched through the gitmem facade"

    def test_gitmem_wip_produces_a_real_commit_that_validator_is_wip_recognizes(
        self, tmp_repo
    ):
        """El subcomando `wip` llega a `bin/memory/wip.py` de verdad --
        probado con el EFECTO real: un commit real, cuyo titular
        `validator.is_wip()` (produccion) reconoce -- nunca comparando
        contra un texto tecleado a mano [unmassk-standards Sec.34].

        `repo_type="trunk"`: este test prueba el DESPACHO de la fachada
        y el reconocimiento del titular, no la proteccion de rama -- eso
        vive por separado en `TestWipRejectsDirectCommitToProtectedMain
        Branch`, mas abajo. Decision del propietario 2026-08-03: "el
        checkpoint protege la rama principal igual que el commit de
        trabajo" [DEUDA.md PARTE 1]. Sin sembrar `config.json`, este
        repositorio de prueba cae en el default fail-closed
        (`repo_type="gitflow"`) y `wip` rebotaria en `main` antes de
        llegar a comitear nada -- exactamente la misma tecnica que ya
        usa `test_work_script.py` para desbloquear sus commits legitimos
        en la rama principal."""
        seed_config_json(tmp_repo, repo_type="trunk")
        validator_lib = import_lib_memory_module("validator")
        before = _git_commit_count(tmp_repo)

        touched = os.path.join(tmp_repo, "MARK_wip_file.txt")
        with open(touched, "w", encoding="utf-8") as fh:
            fh.write("MARK wip checkpoint content\n")

        rc, out, err = run_gitmem_script(
            [
                "wip", "mid-refactor snapshot via the gitmem facade",
                "--path", "MARK_wip_file.txt",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, "el subcomando wip tiene que producir un commit real"

        _rc, subject, _err = run_git(["log", "-1", "--format=%s"], tmp_repo)
        assert validator_lib.is_wip(subject), (
            f"el titular del commit de wip tiene que empezar por el marcador "
            f"que validator.is_wip() reconoce -- titular real: {subject!r}"
        )


class TestWipRejectsDirectCommitToProtectedMainBranch:
    """Decision del propietario 2026-08-03 [DEUDA.md PARTE 1]: "el
    checkpoint protege la rama principal igual que el commit de
    trabajo". Sin `config.json` sembrado, `config.py` cae en su default
    fail-closed (`repo_type="gitflow"`, protegido) -- el caso mas
    peligroso, el de un proyecto recien instalado sin ajuste todavia, y
    exactamente el que `tmp_repo` reproduce sin tocar nada (rama
    "main", la que `git init` crea por defecto en esta maquina).

    Mismo montaje y misma tecnica de EFECTO que
    `test_work_script.py::TestProtectedRepoRejectsDirectCommitToMain
    Branch` (`work.py` sobre el mismo `lib/memory/repo_guard.py`):
    ningun texto fija la redaccion exacta del rechazo, asi que se
    comprueba EFECTO -- codigo de retorno distinto de cero, cero
    traceback, salida no vacia ("dice que hacer"), y sobre todo -- lo
    que demuestra que el rechazo es real y no un aviso a medias -- CERO
    commits nuevos y el mismo SHA de HEAD antes y despues. Un rechazo
    que deja el repositorio a medio comitear es peor que no rechazar."""

    def test_wip_bounces_on_main_without_config_and_leaves_history_untouched(
        self, tmp_repo
    ):
        touched = os.path.join(tmp_repo, "MARK_wip_file.txt")
        with open(touched, "w", encoding="utf-8") as fh:
            fh.write("MARK wip checkpoint content, must not be committed\n")

        before_count = _git_commit_count(tmp_repo)
        _rc, before_sha, _err = run_git(["rev-parse", "HEAD"], tmp_repo)

        rc, out, err = run_gitmem_script(
            [
                "wip", "should not commit directly to a protected main",
                "--path", "MARK_wip_file.txt",
            ],
            cwd=tmp_repo,
        )
        assert rc != 0, (
            f"sin config.json, el default protegido tiene que rebotar el "
            f"checkpoint en la rama principal: stdout={out!r} stderr={err!r}"
        )
        combined = out + err
        assert "Traceback" not in combined
        assert combined.strip() != "", "el rechazo tiene que decir que hacer, no salir en silencio"

        after_count = _git_commit_count(tmp_repo)
        _rc, after_sha, _err = run_git(["rev-parse", "HEAD"], tmp_repo)
        assert after_count == before_count and after_sha == before_sha, (
            "un rechazo que ya ha escrito no es un rechazo -- HEAD no puede "
            f"haberse movido: antes={before_sha!r} despues={after_sha!r}"
        )


class TestUnknownSubcommandFailsListingWhatExists:
    def test_unknown_subcommand_fails_and_names_the_nine_real_ones(self, tmp_repo):
        rc, out, err = run_gitmem_script(["frobnicate"], cwd=tmp_repo)
        assert rc != 0, f"un subcomando desconocido tiene que fallar: stdout={out!r}"
        combined = out + err
        assert "Traceback" not in combined
        for subcommand in _NINE_SUBCOMMANDS:
            assert subcommand in combined, (
                f"el fallo tiene que listar los nueve subcomandos reales -- "
                f"falta {subcommand!r}: {combined!r}"
            )


class TestVersionFlagPrintsTheRealToolkitVersion:
    def test_version_matches_plugin_json_for_real(self, tmp_repo):
        plugin_json_path = os.path.join(_TOOLKIT_ROOT, ".claude-plugin", "plugin.json")
        with open(plugin_json_path, "r", encoding="utf-8") as fh:
            real_version = json.load(fh)["version"]

        rc, out, err = run_gitmem_script(["--version"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err
        assert real_version in out, (
            f"--version tiene que imprimir la version REAL de plugin.json "
            f"({real_version!r}), no una inventada: {out!r}"
        )


class TestAddsNoLogicOfItsOwn:
    """"no añade logica propia -- solo reparte": una nota rechazada por el
    validador real via `gitmem note` tiene que dar EXACTAMENTE el mismo
    rechazo que `note.py` directamente -- si la fachada reimplementara
    algo, los dos caminos podrian divergir."""

    def test_gitmem_note_rejects_exactly_like_note_py_directly_for_the_same_bad_input(
        self, tmp_repo
    ):
        args = [
            "D", "--zones", "auth", "product", "login flow rewrite",
            "--why", "old flow did not scale",
        ]  # sin --description: falta un campo obligatorio de D

        rc_direct, out_direct, err_direct = run_memory_script("note.py", args, cwd=tmp_repo)
        rc_facade, out_facade, err_facade = run_gitmem_script(["note", *args], cwd=tmp_repo)

        assert rc_direct != 0, f"la llamada directa deberia rebotar: {out_direct!r}"
        assert rc_facade == rc_direct
        assert out_facade == out_direct, (
            "gitmem note tiene que dar EXACTAMENTE el mismo rechazo que note.py "
            f"directamente: directo={out_direct!r} fachada={out_facade!r}"
        )


class TestForceUtf8StreamsFirstStatement:
    def test_unknown_subcommand_message_survives_a_restricted_console_encoding(self, tmp_repo):
        rc, out, err = run_gitmem_script(
            ["frobnicate"], cwd=tmp_repo,
            env={"PYTHONIOENCODING": "cp1252", "LANG": "C", "LC_ALL": "C"},
        )
        combined = out + err
        assert "UnicodeEncodeError" not in combined
        assert "UnicodeDecodeError" not in combined
        assert "Traceback" not in combined
