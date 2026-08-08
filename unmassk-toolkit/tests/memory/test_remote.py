"""Contrato de `lib/memory/remote.py` y `lib/memory/timefmt.py`.

Cada prueba compara DOS cosas escritas por separado -- lo que la pieza
dice contra lo que git responde por otro camino, o contra el entorno
endurecido del arranque anterior leido de su propio fichero. Ninguna se
mira a si misma.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from .conftest import import_lib_memory_module

# Al nivel del modulo, como `test_utf8.py`: es la forma que el guardian
# de frontera sabe leer para saber que estas piezas SI tienen quien las
# pruebe.
remote = import_lib_memory_module("remote")
timefmt = import_lib_memory_module("timefmt")
gitcmd = import_lib_memory_module("gitcmd")

_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, env=_ENV
    )
    return proc.stdout.strip()


def _commit(repo: Path, name: str, message: str) -> None:
    (repo / name).write_text(f"{name}\n")
    _git(repo, "add", name)
    _git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-qm", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main", ".")
    _commit(work, "a.txt", "seed")
    return work


class TestLatestActivityFindsTheBranchGitAlsoNames:
    """La pieza dice en que rama se toco el proyecto por ultima vez; git
    responde lo mismo por otro camino."""

    def test_the_newest_branch_wins_even_when_you_are_standing_on_another(
        self, repo: Path
    ) -> None:
        _git(repo, "checkout", "-q", "-b", "feat/tienda")
        _commit(repo, "b.txt", "trabajo de la tienda")
        _git(repo, "checkout", "-q", "main")

        found = remote.latest_activity(repo)

        # La otra fuente: la fecha de cada rama, preguntada aparte.
        newest_by_git = _git(
            repo,
            "for-each-ref",
            "--sort=-committerdate",
            "--count=1",
            "--format=%(refname:short)",
            "refs/heads",
        )
        assert isinstance(found, remote.Activity), (
            "lo que sale tiene que ser la pieza declarada, no una tupla suelta: "
            "quien lo lea se apoya en los nombres de sus campos"
        )
        assert found.branch == newest_by_git == "feat/tienda", (
            "la rama con el commit mas reciente tiene que ser la misma que "
            f"nombra git: pieza={found.branch!r} git={newest_by_git!r}"
        )
        assert found.subject == "trabajo de la tienda"
        assert remote.RemoteState(
            fetched=True,
            fetch_error=None,
            current_branch="main",
            latest=found,
            ahead=None,
            behind=None,
        ).elsewhere, "estando en main con el trabajo en feat/tienda, tiene que avisar"

    def test_standing_on_the_branch_that_was_worked_on_is_not_elsewhere(
        self, repo: Path
    ) -> None:
        found = remote.latest_activity(repo)
        state = remote.RemoteState(
            fetched=True,
            fetch_error=None,
            current_branch="main",
            latest=found,
            ahead=None,
            behind=None,
        )
        assert not state.elsewhere


def _commit_with_zero_offset_date(repo: Path, name: str, message: str) -> None:
    """Mismo patron que `_commit()` de arriba, pero fuerza
    `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` a un offset `+00:00` explicito.

    Verificado por House: con este gancho git escribe la fecha del commit
    con sufijo `Z` (formato ISO-8601 estricto que usa `%(committerdate:
    iso8601-strict)`, el mismo que `remote.py` pide) SEA CUAL SEA la zona
    horaria de la maquina que ejecuta el test -- sin el, el rojo de este
    fichero dependeria de en que huso este quien corre pytest, y en
    Madrid (o cualquier sitio que no sea offset cero) nunca reproduciria
    nada.
    """
    # Muy en el futuro a proposito, no "2026-01-01" a secas: `main` trae un
    # commit "seed" con la hora AMBIENTAL real (la del reloj de quien
    # ejecuta el test) -- una fecha forzada que quedase mas vieja que ese
    # seed haria que `main` ganase el orden por `-committerdate` de forma
    # legitima, sin que el bug de la `Z` tuviera nada que ver, y el rojo
    # de este test seria un rojo por la razon equivocada.
    env_with_zero_offset_date = {
        **_ENV,
        "GIT_AUTHOR_DATE": "2030-01-01T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2030-01-01T00:00:00+00:00",
    }
    (repo / name).write_text(f"{name}\n")
    subprocess.run(["git", "add", name], cwd=repo, env=env_with_zero_offset_date)
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "commit", "-qm", message],
        cwd=repo,
        env=env_with_zero_offset_date,
    )


class TestZeroOffsetCommitDateNeverSilentlyLosesTheLatestActivity:
    """T1 real (House + coordinador, 2026-08-08), lector 1 de 4 del mismo
    fallo: git escribe la fecha de un commit hecho en offset +00:00 (un
    contenedor sin TZ, un merge desde la web de GitHub, un bot) como
    `...T04:49:21Z`. `datetime.fromisoformat` de Python 3.10 no sabe leer
    esa `Z` (soporte anadido en 3.11), y `toolkit-ci.yml` fija Python
    3.10.

    `latest_activity()` (remote.py ~197-198) ya envuelve el parseo en un
    `try/except ValueError: continue` -- no revienta, pero el resultado es
    peor: se traga el error EN SILENCIO y sigue como si esa referencia no
    existiera. Con un solo commit en el repo, "seguir como si no
    existiera" es devolver `None` -- indistinguible de "este repositorio
    no tiene ninguna actividad todavia", que es un estado real y
    completamente distinto. El arranque no puede contar la diferencia
    entre las dos cosas si la pieza que lee tampoco puede.

    Este test SOLO reproduce el fallo en Python < 3.11 -- ver la entrega
    de esta tarea para la salida real bajo un interprete 3.10.
    """

    def test_a_zero_offset_branch_is_found_not_silently_dropped(
        self, repo: Path
    ) -> None:
        _git(repo, "checkout", "-q", "-b", "feat/huso-cero")
        _commit_with_zero_offset_date(repo, "b.txt", "trabajo en huso cero")
        _git(repo, "checkout", "-q", "main")

        # El montaje es invalido si git no escribio de verdad el huso cero
        # -- comprobado leyendo el historial por OTRO camino, nunca
        # asumido.
        newest_by_git = _git(
            repo,
            "for-each-ref",
            "--sort=-committerdate",
            "--count=1",
            "--format=%(committerdate:iso8601-strict)",
            "refs/heads/feat/huso-cero",
        )
        assert newest_by_git.endswith("Z"), (
            f"el montaje de la prueba es invalido: la rama nueva no quedo "
            f"con sufijo Z (huso cero) -- {newest_by_git!r}"
        )

        # Hoy esto no devuelve la Activity real de `feat/huso-cero` (la
        # unica rama con un commit de verdad aparte del seed): devuelve
        # `None`, indistinguible de "no hay actividad" -- la misma
        # perdida silenciosa que este proyecto existe para impedir.
        found = remote.latest_activity(repo, local_only=True)

        assert found is not None, (
            "latest_activity() devolvio None -- el commit en huso cero "
            "existe de verdad (confirmado por git arriba), pero la pieza "
            "lo trago en silencio y reporto 'no hay actividad'"
        )
        assert found.branch == "feat/huso-cero", (
            f"se esperaba la rama con el commit real mas reciente, salio {found.branch!r}"
        )


class TestDivergenceMatchesWhatGitCountsByAnotherRoute:
    """`divergence()` lee referencias; `git rev-list` cuenta commits. Las
    dos cuentas tienen que coincidir -- si no, el arranque dice un numero
    que no es."""

    def test_ahead_and_behind_agree_with_rev_list(self, tmp_path: Path) -> None:
        origin = tmp_path / "origin.git"
        subprocess.run(
            ["git", "init", "--bare", "-q", "-b", "main", str(origin)], check=True
        )
        work = tmp_path / "work"
        work.mkdir()
        _git(work, "init", "-q", "-b", "main", ".")
        _commit(work, "a.txt", "seed")
        _git(work, "remote", "add", "origin", str(origin))
        _git(work, "push", "-q", "-u", "origin", "main")

        # Dos commits sin subir.
        _commit(work, "b.txt", "uno")
        _commit(work, "c.txt", "dos")

        ahead, behind = remote.divergence(work, "main")

        counted = _git(
            work, "rev-list", "--left-right", "--count", "main...main@{upstream}"
        ).split()
        assert [str(ahead), str(behind)] == counted, (
            f"la cuenta por referencias ({ahead}, {behind}) no coincide con la "
            f"que da rev-list ({counted})"
        )

    def test_a_branch_with_no_upstream_says_nothing_instead_of_zero(
        self, repo: Path
    ) -> None:
        """Cero seria mentira: no es que estes al dia, es que no hay con
        que compararte."""
        assert remote.divergence(repo, "main") == (None, None)


class TestTheFetchIsHardenedTheSameWayTheOldBootWas:
    """El entorno endurecido no se reinventa: se comprueba contra el
    fichero del arranque anterior, que es de donde salio."""

    def test_git_itself_confirms_every_credential_helper_is_off(
        self, repo: Path
    ) -> None:
        """Lo dice GIT, no el diccionario mirandose a si mismo.

        Se configura un ayudante de credenciales en el repositorio y se
        le pregunta a git si lo ve, con el mismo entorno con el que sale
        el fetch. Si lo viera, ese ayudante podria sacar su propia
        ventana y dejar el arranque esperando a alguien que no esta
        delante -- el fallo que costo dos rondas en el arranque anterior.
        """
        _git(repo, "config", "credential.helper", "osxkeychain")

        sin_endurecer = gitcmd.run(
            ["config", "--get", "credential.helper"], cwd=repo, timeout=10
        )
        assert sin_endurecer.stdout.strip() == "osxkeychain", (
            "el ayudante no llego a configurarse: la prueba no demuestra nada"
        )

        endurecido = gitcmd.run(
            ["config", "--get", "credential.helper"],
            cwd=repo,
            timeout=10,
            env=remote._HARDENED_ENV,
        )
        assert endurecido.stdout.strip() == "", (
            "git sigue viendo un ayudante de credenciales pese al entorno "
            f"endurecido: {endurecido.stdout!r}"
        )

    def test_the_hardened_env_adds_to_the_real_one_instead_of_replacing_it(
        self, repo: Path
    ) -> None:
        """Sustituir el entorno entero dejaria a git sin PATH ni HOME. Si
        eso pasara, esta llamada no encontraria ni el binario."""
        result = gitcmd.run(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo,
            timeout=10,
            env=remote._HARDENED_ENV,
        )
        assert result.returncode == 0 and result.stdout.strip() == "main"

    def test_a_repo_with_no_remote_is_not_a_fetch_failure(self, repo: Path) -> None:
        """Sin remoto, `git fetch --all` no tiene nada que traer y sale
        bien. Tratarlo como fallo llenaria de avisos cualquier proyecto
        local."""
        ok, reason = remote.fetch_all(repo)
        assert ok, f"un repositorio sin remoto no es un fallo de fetch: {reason}"


class TestBareStripsTheRemoteName:
    def test_origin_and_local_are_the_same_branch(self) -> None:
        assert remote._bare("origin/feat/x") == "feat/x"
        assert remote._bare("feat/x") == "feat/x"
        assert remote._bare("main") == "main"


class TestTimeFormatting:
    def test_utc_label_matches_the_same_moment_formatted_apart(self) -> None:
        moment = datetime(2026, 8, 5, 16, 4, tzinfo=timezone.utc)
        assert timefmt.utc_label(moment) == "2026-08-05 16:04 UTC"

    def test_a_local_time_is_shown_in_utc_not_as_it_arrived(self) -> None:
        madrid = timezone(timedelta(hours=2))
        assert timefmt.utc_label(
            datetime(2026, 8, 5, 18, 4, tzinfo=madrid)
        ) == "2026-08-05 16:04 UTC"

    @pytest.mark.parametrize(
        "delta,expected",
        [
            (timedelta(seconds=10), "just now"),
            (timedelta(minutes=32), "32 min ago"),
            (timedelta(hours=2), "2 h ago"),
            (timedelta(days=1), "1 day ago"),
            (timedelta(days=3), "3 days ago"),
            (timedelta(days=8), "1 week ago"),
            (timedelta(days=30), "4 weeks ago"),
        ],
    )
    def test_elapsed_reads_the_way_a_person_says_it(
        self, delta: timedelta, expected: str
    ) -> None:
        now = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
        assert timefmt.ago(now - delta, now=now) == expected

    def test_a_date_it_cannot_read_never_takes_the_boot_down(self) -> None:
        """Perder el arranque de la mañana por una fecha rara no compensa
        [guarda traida de `time_ago()` del arranque anterior]."""
        assert timefmt.ago("no soy una fecha") == "unknown"
        assert timefmt.utc_label(None) == "unknown"

    def test_a_date_with_no_timezone_is_read_as_utc_instead_of_exploding(
        self,
    ) -> None:
        naive = datetime(2026, 8, 5, 12, 0)
        now = datetime(2026, 8, 5, 14, 0, tzinfo=timezone.utc)
        assert timefmt.ago(naive, now=now) == "2 h ago"


class TestAForeignRemoteIsNamedInsteadOfCounted:
    """Traido del arranque anterior, donde salio de un incidente real: un
    `origin` apuntando a otro proyecto hacia que el arranque dijera "vas
    2 commits por detras" de un sitio ajeno."""

    def test_a_remote_with_no_shared_history_is_reported_and_never_counted(
        self, tmp_path: Path
    ) -> None:
        foreign = tmp_path / "foreign"
        foreign.mkdir()
        _git(foreign, "init", "-q", "-b", "main", ".")
        _commit(foreign, "theirs.txt", "another project entirely")

        mine = tmp_path / "mine"
        mine.mkdir()
        _git(mine, "init", "-q", "-b", "main", ".")
        _commit(mine, "mine.txt", "my project")
        _git(mine, "remote", "add", "origin", str(foreign))
        _git(mine, "fetch", "-q", "origin")
        _git(mine, "branch", "--set-upstream-to=origin/main", "main")

        # git confirma por su cuenta que no comparten ni un commit
        shared = subprocess.run(
            ["git", "merge-base", "--", "HEAD", "origin/main"],
            cwd=mine,
            capture_output=True,
            text=True,
            env=_ENV,
        )
        assert shared.returncode != 0, (
            "el montaje de la prueba es invalido: los dos repositorios SI "
            "comparten historia"
        )

        assert remote.shares_history(mine, "main") is False

        state = remote.state(mine, "main")
        assert state.unrelated_remote is True
        assert (state.ahead, state.behind) == (None, None), (
            "con un remoto ajeno los numeros son reales y no significan nada: "
            f"no se pueden ensenar ({state.ahead}, {state.behind})"
        )

    def test_a_branch_never_pushed_still_catches_a_foreign_remote(
        self, tmp_path: Path
    ) -> None:
        """El agujero que dejaba entrar todo [Moriarty, 2026-08-05].

        La comprobacion se apoyaba en el remoto DECLARADO de la rama. Una
        rama recien creada y todavia sin subir no tiene ninguno -- el
        estado mas comun que hay -- y entonces se daba por buena sin
        comparar un solo commit. Con `origin` apuntando a otro proyecto,
        el arranque llegaba a enseñar el Next de ESE proyecto como si
        fuera el de este.

        El test anterior no lo cazaba porque configuraba el remoto de la
        rama antes de comprobar nada.
        """
        foreign = tmp_path / "foreign"
        foreign.mkdir()
        _git(foreign, "init", "-q", "-b", "main", ".")
        _commit(foreign, "theirs.txt", "another project entirely")

        mine = tmp_path / "mine"
        mine.mkdir()
        _git(mine, "init", "-q", "-b", "main", ".")
        _commit(mine, "mine.txt", "my project")
        _git(mine, "remote", "add", "origin", str(foreign))
        _git(mine, "fetch", "-q", "origin")
        # Rama nueva, nunca empujada: SIN remoto declarado.
        _git(mine, "checkout", "-q", "-b", "feat/never-pushed")

        upstream = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "feat/never-pushed@{upstream}"],
            cwd=mine,
            capture_output=True,
            text=True,
            env=_ENV,
        )
        assert upstream.returncode != 0, (
            "el montaje es invalido: esta rama SI tiene remoto declarado, que "
            "es justo el caso que el test viejo ya cubria"
        )

        assert remote.shares_history(mine, "feat/never-pushed") is False, (
            "una rama sin remoto declarado no puede dar por bueno un origin "
            "que no comparte ni un commit con este repositorio"
        )
        assert remote.state(mine, "feat/never-pushed").unrelated_remote is True

    def test_a_branch_with_no_remote_is_not_treated_as_foreign(
        self, repo: Path
    ) -> None:
        """Sin remoto no hay de que desconfiar; marcarlo llenaria de avisos
        cualquier proyecto local."""
        assert remote.shares_history(repo, "main") is True
        assert remote.state(repo, "main").unrelated_remote is False


class TestARemotesSymbolicHeadIsNeverMistakenForABranch:
    """`refs/remotes/origin/HEAD` apunta a la rama por defecto del remoto
    y NO es una rama: su nombre corto se queda en "origin" a secas.
    Empatado en fecha con la rama a la que apunta, ganaba por orden
    alfabetico y el arranque decia "Last worked on: origin" -- un nombre
    que no existe. Mismo fallo que ya salio en el arranque anterior el
    2026-07-15."""

    def test_the_symref_never_wins_against_the_branch_it_points_at(
        self, tmp_path: Path
    ) -> None:
        origin = tmp_path / "origin.git"
        subprocess.run(
            ["git", "init", "--bare", "-q", "-b", "main", str(origin)], check=True
        )
        work = tmp_path / "work"
        work.mkdir()
        _git(work, "init", "-q", "-b", "main", ".")
        _commit(work, "a.txt", "the newest work")
        _git(work, "remote", "add", "origin", str(origin))
        _git(work, "push", "-q", "-u", "origin", "main")
        # Lo que crea cualquier clone normal, y lo que faltaba en las
        # pruebas: el puntero simbolico del remoto.
        _git(work, "remote", "set-head", "origin", "main")

        listed = _git(
            work,
            "for-each-ref",
            "--sort=-committerdate",
            "--format=%(refname:short) %(symref)",
            "refs/heads",
            "refs/remotes",
        )
        assert "origin refs/remotes/origin/main" in listed, (
            "el montaje no reproduce el caso: git no esta listando la HEAD "
            f"simbolica del remoto\n{listed}"
        )

        found = remote.latest_activity(work)
        assert found is not None
        assert found.branch != "origin", (
            "la HEAD simbolica del remoto se esta colando como si fuera una "
            "rama: 'origin' no es un sitio al que nadie pueda ir"
        )
        assert found.branch in ("main", "origin/main")
