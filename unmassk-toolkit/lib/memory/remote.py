"""lib/memory/remote.py -- lo que el arranque necesita saber del remoto.

Tres preguntas, y las tres tienen que responderse ANTES de leer memoria:

    1. traer          `git fetch --all`, nunca `pull`
    2. donde se dejo  la rama con el commit mas reciente de todas,
                      locales y remotas, y hace cuanto
    3. donde estas    la rama de ahora, y cuanto se separa de su remoto

**Por que el fetch va primero y no es opcional** [decision del
propietario, 2026-08-05]: se trabaja en mas de una maquina. Se cierra la
sesion en casa sobre `dev`, se sigue en otro sitio sobre una rama nueva,
y al volver a casa el repositorio local no sabe nada de eso. Sin traer
primero, el arranque lee el ultimo cierre de ESTA copia -- que es de
antes de ayer -- y lo presenta como el estado del proyecto. No avisa de
nada, porque desde dentro todo cuadra.

**Nunca `pull`.** Traer no toca el arbol de trabajo; fusionar si. El
arranque informa de que hay que traerse el trabajo; moverlo lo decide
quien esta delante.

**Un fallo de red nunca para el arranque** -- la memoria ayuda, no
bloquea. Pero tampoco se calla: si el fetch fallo, el arranque lo dice,
porque todo lo que venga despues puede estar mirando una foto vieja.

`bin/memory/boot.py` es su unico llamador.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import re
import sys

import gitcmd
import timefmt  # reexportado para boot.py, y usado aqui mismo abajo

# El fetch sale a la red: se le da mas margen que a una lectura local,
# pero acotado -- un arranque que se queda colgado es un arranque roto.
FETCH_TIMEOUT = 10

# ---------------------------------------------------------------------
# El entorno endurecido, traido tal cual del arranque del sistema
# anterior [`lib/boot_git_checks.py`, commit 3449fbe]. NO se reinventa:
# costo dos rondas de reparacion alli y cada linea tapa un agujero
# distinto por el que el arranque se quedaba colgado esperando a alguien
# que no estaba delante.
#
#   GIT_TERMINAL_PROMPT   git no pregunta por consola
#   GIT_ASKPASS/SSH_ASKPASS  ningun dialogo grafico de contraseña; el
#                         programa que se pone falla al instante. Tiene
#                         que ser un nombre suelto que se resuelva por
#                         PATH: git lo invoca como argv[0] literal, sin
#                         pasar por una shell, asi que una ruta absoluta
#                         o un comando con argumentos NO valen fuera de
#                         Windows
#   GIT_SSH_COMMAND       ssh en modo sin interaccion
#   GIT_CONFIG_*          desactiva TODOS los ayudantes de credenciales
#                         configurados -- llavero de macOS, libsecret,
#                         los de Windows. Los tres de arriba solo callan
#                         a git; un ayudante puede sacar su propia
#                         ventana igual. Se pasa por variables y no por
#                         `-c` para no cambiar los argumentos de git
# ---------------------------------------------------------------------
_ASKPASS_FAILFAST = "cmd /c exit 1" if sys.platform == "win32" else "false"

_HARDENED_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": _ASKPASS_FAILFAST,
    "SSH_ASKPASS": _ASKPASS_FAILFAST,
    "GIT_SSH_COMMAND": "ssh -oBatchMode=yes",
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "credential.helper",
    "GIT_CONFIG_VALUE_0": "",
}

# Separador de unidad: no puede ser el byte nulo, que es lo natural en
# git, porque un argumento de proceso no admite nulos dentro -- se ve al
# ejecutarlo, no leyendo.
_FIELD_SEP = "\x1f"
# `%(committerdate:unix)` (segundos-epoch), no `:iso8601-strict` (sufijo
# `Z` en huso cero, que `datetime.fromisoformat` de Python 3.10 no sabe
# leer) [decision del propietario, 2026-08-08 -- ver
# `timefmt.from_git_seconds`].
_REF_FORMAT = _FIELD_SEP.join(
    (
        "%(committerdate:unix)",
        "%(refname:short)",
        "%(objectname:short)",
        "%(symref)",
        "%(contents:subject)",
    )
)

# Cuantas referencias se piden antes de filtrar. Se piden varias y no una
# porque la primera puede ser una que hay que descartar.
_REF_CANDIDATES = 20


@dataclass(frozen=True)
class Activity:
    """Donde se toco el proyecto por ultima vez, mire uno la rama que
    mire."""

    branch: str
    sha: str
    when: datetime
    subject: str


@dataclass(frozen=True)
class RemoteState:
    """Lo que el arranque enseña en su cabecera."""

    fetched: bool
    fetch_error: str | None
    current_branch: str | None
    latest: Activity | None
    ahead: int | None
    behind: int | None
    # La rama tenia remoto y ya no existe alli: se fusiono y se borro.
    upstream_gone: bool = False
    # `True` cuando el remoto configurado NO comparte ni un commit con
    # este repositorio: apunta a otro proyecto.
    unrelated_remote: bool = False

    @property
    def elsewhere(self) -> bool:
        """El trabajo mas reciente no esta donde estas tu. Es el caso que
        justifica todo este fichero."""
        if self.latest is None or self.current_branch is None:
            return False
        return _bare(self.latest.branch) != self.current_branch


def _bare(ref: str) -> str:
    """`origin/feat/x` y `feat/x` son la misma rama para quien mira."""
    if "/" not in ref:
        return ref
    head, tail = ref.split("/", 1)
    return tail if head in ("origin", "upstream") else ref


def fetch_all(root: Path) -> tuple[bool, str | None]:
    """`git fetch --all --prune`. Devuelve (fue bien, motivo si no).

    `--prune` para que una rama borrada en el remoto deje de figurar aqui
    como sitio donde podria estar el trabajo.
    """
    result = gitcmd.run(
        ["fetch", "--all", "--prune", "--quiet"],
        cwd=root,
        timeout=FETCH_TIMEOUT,
        env=_HARDENED_ENV,
    )
    if result.returncode == 0:
        return True, None
    reason = (result.stderr or "").strip().split("\n")[-1]
    return False, reason or "git no dijo por que"


def latest_activity(root: Path, local_only: bool = False) -> Activity | None:
    """La rama con el commit mas reciente, locales y remotas incluidas.

    Se ordena por fecha del commit, no por la rama en la que estas: eso
    es justamente lo que el arranque no puede deducir solo.
    """
    result = gitcmd.run(
        [
            "for-each-ref",
            "--sort=-committerdate",
            f"--count={_REF_CANDIDATES}",
            f"--format={_REF_FORMAT}",
            "refs/heads",
            *(() if local_only else ("refs/remotes",)),
        ],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    if result.returncode != 0:
        return None

    for line in (result.stdout or "").split("\n"):
        if line.count(_FIELD_SEP) != 4:
            continue
        when, branch, sha, symref, subject = line.split(_FIELD_SEP)

        # `refs/remotes/origin/HEAD` es un puntero a la rama por defecto
        # del remoto, no una rama: su nombre corto se queda en "origin" a
        # secas y, empatado en fecha con la rama a la que apunta, gana por
        # orden alfabetico. El arranque acababa diciendo "Last worked on:
        # origin", que no existe -- y justo en el caso para el que se
        # escribio este fichero. Ya habia pasado una vez en el arranque
        # anterior [Cerberus, 2026-08-05; mismo fallo el 2026-07-15].
        if symref:
            continue

        # Sin red de seguridad a proposito: una fecha que `timefmt` no
        # pueda leer es un fallo real de git, no "esta referencia no
        # existe" -- devolver `None` ahi seria indistinguible de "no hay
        # actividad" [condicion del encargo, 2026-08-08]. Con
        # segundos-epoch (arriba) este caso no deberia darse nunca; si se
        # da, tiene que gritar, no callarse.
        moment = timefmt.from_git_seconds(when)
        return Activity(branch=branch, sha=sha, when=moment, subject=subject)
    return None


_TRACK_RE = re.compile(r"ahead (\d+)|behind (\d+)")
_GONE = "gone"


def divergence(root: Path, branch: str | None) -> tuple[int | None, int | None]:
    """Cuantos commits tienes de mas y de menos frente a tu remoto.

    `(None, None)` cuando esa rama no tiene remoto que seguir: no es un
    fallo, es un proyecto que todavia no ha subido nada.

    Se pregunta por la REFERENCIA, no por el historial: `git rev-list`
    contaria lo mismo, pero es un lector del historial y en este sistema
    solo hay uno, `query.py` [PIEZAS.md Sec.8.2 -- lo caza un test de
    frontera, no la buena voluntad de nadie]. `%(upstream:track)` da la
    cuenta ya hecha leyendo solo referencias.
    """
    if not branch:
        return None, None
    result = gitcmd.run(
        [
            "for-each-ref",
            "--format=%(upstream:track)",
            f"refs/heads/{branch}",
        ],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    track = (result.stdout or "").strip()
    if result.returncode != 0 or not track:
        return None, None
    # git contesta "[gone]" cuando la rama de la que colgabas ya no existe
    # en el remoto -- lo normal despues de fusionar y borrarla. Sin
    # reconocerlo, ni "ahead" ni "behind" casaban y las dos cuentas se
    # quedaban en cero, que es indistinguible de "estas al dia"
    # [Argus, 2026-08-05].
    if _GONE in track:
        return None, None
    ahead = behind = 0
    for match in _TRACK_RE.finditer(track):
        if match.group(1):
            ahead = int(match.group(1))
        if match.group(2):
            behind = int(match.group(2))
    return ahead, behind


def shares_history(root: Path, branch: str | None) -> bool:
    """¿El remoto de esa rama comparte historia con este repositorio?

    Traido del arranque anterior [`boot_git_checks.py::
    check_upstream_shares_history`], donde salio de un incidente real: un
    `origin` que apuntaba a OTRO proyecto del propietario hacia que el
    arranque dijera "vas 2 commits por detras" y listara ramas ajenas
    como si fueran de aqui. Los numeros eran ciertos y no significaban
    nada.

    `True` cuando NO HAY ninguna referencia del remoto que comparar: sin
    remoto no hay nada de que desconfiar, y tratarlo como sospechoso
    llenaria de avisos el arranque de cualquier proyecto local.

    **La comprobacion NO se apoya en el remoto declarado de la rama.** Esa
    era la version anterior y tenia el agujero por el que entraba todo:
    una rama que todavia no se ha subido no tiene remoto declarado, que
    es el estado normal de cualquier rama recien creada -- y entonces la
    funcion decia "es de los nuestros" sin comparar ni un commit. Con un
    `origin` apuntando a otro proyecto, el arranque llegaba a enseñar el
    Next de ESE proyecto como si fuera el tuyo, en la primera linea, sin
    un solo aviso [Moriarty, 2026-08-05: el guardian existia, su test
    estaba verde, y el caso corriente no pasaba por el].

    Ahora se compara contra las referencias del remoto DE VERDAD: si hay
    alguna y ninguna comparte un solo commit con lo que tienes, el remoto
    no es de este proyecto.
    """
    candidates = gitcmd.run(
        [
            "for-each-ref",
            f"--count={_REF_CANDIDATES}",
            "--format=%(refname:short)%(symref)",
            "refs/remotes",
        ],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    references = [
        line.strip()
        for line in (candidates.stdout or "").split("\n")
        # Una referencia simbolica (`origin/HEAD`) no es una rama: su
        # nombre viene pegado al destino y no se puede comparar.
        if line.strip() and "refs/remotes/" not in line
    ]
    if candidates.returncode != 0 or not references:
        return True

    for reference in references:
        # `--` separa opciones de referencias, igual que en el original.
        shared = gitcmd.run(
            ["merge-base", "--", "HEAD", reference],
            cwd=root,
            timeout=gitcmd.GIT_TIMEOUT,
        )
        if shared.returncode == 0:
            return True
    return False


def state(root: Path, current_branch: str | None) -> RemoteState:
    """Trae y responde las tres preguntas de una vez."""
    fetched, error = fetch_all(root)
    related = shares_history(root, current_branch)
    # Con un remoto ajeno, las cuentas de adelanto y retraso salen de
    # comparar dos historias que no tienen nada que ver: el numero es
    # real y no significa nada. Se callan, y se dice por que.
    ahead, behind = divergence(root, current_branch) if related else (None, None)
    gone = related and _upstream_gone(root, current_branch)
    return RemoteState(
        fetched=fetched,
        fetch_error=error,
        current_branch=current_branch,
        # Con un remoto ajeno NO se miran sus ramas: el commit mas
        # reciente de alli es de otro proyecto, y salia anunciado como
        # "aqui se dejo el trabajo" -- encima con el aviso de "esta en
        # otra rama", que era falso [Argus, 2026-08-05].
        latest=latest_activity(root, local_only=not related),
        ahead=ahead,
        behind=behind,
        unrelated_remote=not related,
        upstream_gone=bool(gone),
    )


def _upstream_gone(root: Path, branch: str | None) -> bool:
    if not branch:
        return False
    result = gitcmd.run(
        ["for-each-ref", "--format=%(upstream:track)", f"refs/heads/{branch}"],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    return _GONE in (result.stdout or "")
