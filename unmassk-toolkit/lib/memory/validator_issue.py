"""La comprobacion contra GitHub de que la issue del acta existe de
verdad -- partida fuera de validator.py por tamano [mismo techo, mismo
motivo que `validator_zones.py`: DEUDA.md punto 14, "552 lineas, techo
500"; con esta pieza dentro, `validator.py` habria pasado el mismo techo
otra vez].

Este fichero NO es una segunda pieza ni una segunda puerta de
validacion: sigue habiendo una sola implementacion de "esto es valido"
[PIEZAS.md Sec.7.5]. `validator.py` importa `validate_issue` de aqui de
forma PLANA [PIEZAS.md Sec.3.3bis] y lo reexpone bajo el mismo nombre,
asi que `validator.validate_issue` sigue funcionando exactamente igual
para cualquiera que lo llame (`bin/memory/note.py`).

QUE ES LO QUE SE PARTIO, Y POR QUE ESTE CORTE Y NO OTRO: la fila 8 de la
aduana [spec-sistema-memoria-v2.md Sec.6; TEXTOS.md Sec.1.9] es la UNICA
de las diez que exige llamar a algo externo distinto de git (``gh``) --
un asunto propio, que no comparte datos con el resto de `validator.py`
mas alla de la `Note` candidata (para el comando de relanzamiento) y el
numero de issue. Decision del propietario, 2026-08-02 [PIEZAS.md
Sec.10.1, punto 1]: *"Se construye en validator, no en el script -- el
script no valida nada. ... Copia ese trato"* (el de
``health.plans_unreflected``, que ya consulta ``gh`` y falla en alto si
no puede: *no se puede comprobar* nunca es *esta bien*).

QUE NO HACE. No decide el tipo de nota, las zonas, los campos, los
punteros, la sustitucion, la pregunta del dolor ni la destilacion --
todo eso sigue en `validator.py`. No abre ficheros ni llama a git -- la
UNICA llamada externa de todo el modulo `validator.py` (y de este
fichero) es a `gh`, nunca a `git` [PIEZAS.md Sec.7.5, misma restriccion
que el resto de la pieza, con esta unica excepcion declarada].

No importa nada fuera de la biblioteca estandar de Python y de sus
hermanos de `lib/memory/` [PIEZAS.md Sec.13], importados PLANOS
[PIEZAS.md Sec.3.3bis].
"""

import subprocess
from pathlib import Path

from model import Note, Rejection
import rejection as rejection_

# Segundos de espera para `gh issue view` -- mismo valor y misma fuente
# que `health._GH_TIMEOUT` ("consulta simple, 0,85s medidos"), no una
# segunda copia inventada: los dos son el mismo tipo de llamada (una
# consulta de lectura contra `gh`). No se importa de `health.py` para no
# crear una dependencia cruzada entre dos piezas que no comparten nada
# mas -- mismo tradeoff, ya aceptado en este sistema, que `rejection.py`
# asume para el emoji "⛔" en vez de importar `emojis.py` por un solo
# caracter [rejection.py, docstring del modulo].
_GH_TIMEOUT = 10

# Texto real y estable que `gh issue view` escribe en stderr cuando el
# numero no corresponde a ninguna issue/PR del repo -- verificado en vivo
# contra este mismo repositorio (`gh issue view 999999999`, 2026-08-02):
# `GraphQL: Could not resolve to an issue or pull request with the number
# of 999999999. (repository.issue)`, returncode 1. Cualquier OTRO fallo de
# `gh` (no instalado, sin red, timeout, auth) no lleva esta frase -- esa
# distincion es la que separa "la issue no existe" (rechazo real) de "no
# se pudo comprobar" (RuntimeError, nunca silencio).
_ISSUE_NOT_FOUND_MARKER = "Could not resolve to an issue or pull request"


def _issue_exists(issue: int) -> bool:
    """`True` si `gh` confirma que la issue existe, `False` si `gh`
    confirma que NO existe -- las dos son respuestas reales de `gh`
    funcionando. Cualquier otro resultado (no instalado, sin red, timeout,
    respuesta con otra forma) es un fallo real de la comprobacion, no un
    "no existe", y se propaga como `RuntimeError` con la causa -- mismo
    trato, mismo mensaje, que `health._last_activity_at` [PIEZAS.md
    Sec.10.1, punto 1: "*no se puede comprobar* nunca es *esta bien*"].
    """
    try:
        proc = subprocess.run(
            ["gh", "issue", "view", str(issue), "--json", "number"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"gh issue view #{issue} no termino dentro de {_GH_TIMEOUT}s"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"no se pudo ejecutar 'gh' para comprobar la issue #{issue} "
            f"(no esta instalado, o no es ejecutable): {exc}"
        ) from exc

    if proc.returncode == 0:
        return True
    if _ISSUE_NOT_FOUND_MARKER in proc.stderr:
        return False
    raise RuntimeError(
        f"gh issue view #{issue} fallo: {proc.stderr.strip() or proc.stdout.strip()}"
    )


def validate_issue(note: Note, issue: int | None) -> Rejection | None:
    """Fila 8 [TEXTOS.md Sec.1.9]. `issue` no es un campo que se derive de
    `note` -- igual que `stops`/`is_distillation` en `validator.py`, viaja
    aparte porque solo puede invocarse antes de que la `Note` este
    terminada [ver "ASUNCIONES DE FIRMA" en el docstring de
    `validator.py`]. `issue is None` (el flag `--issue` no se dio) no
    dispara ninguna llamada a `gh` -- no hay nada que comprobar, y esta es
    la UNICA vez que se comprueba [TEXTOS.md Sec.1.9: "Esta es la unica
    vez que se comprueba"].
    """
    if issue is None:
        return None
    if _issue_exists(issue):
        return None

    what = f"ACTA RECHAZADA — la issue #{issue} no existe en este repo"
    options = (
        "Esta es la única vez que se comprueba. Si el número está mal, el enlace",
        "decisión → plan queda roto para siempre y nadie lo va a notar.",
        "",
        "  gh issue list --limit 20          ver las abiertas",
        '  gh issue create --title "..."     crearla ahora',
    )
    command = (
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}" --description "..." --issue <numero real>',
    )
    return rejection_.build(
        kind="issue_not_found", what=what, options=options, command=command
    )
