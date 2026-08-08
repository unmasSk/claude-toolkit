"""lib/memory/timefmt.py -- las dos formas de escribir una fecha.

    utc_label(t)  ->  "2026-08-05 16:04 UTC"     cuando fue, exacto
    ago(t)        ->  "hace 2 h"                  cuanto hace, de un vistazo

Existe porque las dos estaban escritas mas de una vez. `utc_label` vivia
duplicada en `boot.py` y en `report_render.py`, y la segunda llevaba una
conversion defensiva que la primera no -- dos copias del mismo renglon
que ya habian empezado a separarse. Y `ago` iba a ser una tercera copia
de `time_ago()` del arranque del sistema anterior.

**De ese `time_ago()` se traen sus guardas, que salieron de fallos
reales, no de imaginacion** [`lib/boot_git_checks.py:117`]: una fecha que
no se puede leer NO revienta el arranque, se dice que no se sabe; y una
fecha sin zona horaria se trata como UTC en vez de estallar al restarla.
Un arranque que revienta por una fecha rara deja al usuario sin memoria
esa mañana, que es un precio absurdo por un dato de adorno.

Lo que NO se trae: leer cadenas ISO. Aqui casi todo el mundo maneja
`datetime` ya construido -- quien lo parsea es quien lo saca de git.

**Excepcion, desde 2026-08-08:** `from_git_seconds()`. Git escribe la
fecha de un commit hecho en offset +00:00 (un contenedor sin TZ, un merge
desde la web de GitHub, un bot) como `...T04:49:21Z` -- formato ISO-8601
estricto con sufijo `Z`. `datetime.fromisoformat` de Python 3.10 no sabe
leer esa `Z` (soporte anadido en 3.11), y el CI de este repo fija Python
3.10. Un solo commit en huso cero envenenaba la lectura ENTERA en cinco
sitios distintos (`query.py`, `context.py`, `health_plans.py`,
`remote.py`) -- cada uno pidiendole a git la fecha como texto ISO y
convirtiendola por su cuenta con `fromisoformat`, la misma implementacion
repetida cinco veces que este fichero existe para no permitir.

**La solucion no es normalizar la `Z`: es dejar de pedir texto.** Un
numero de segundos-epoch (`%at` en un `--pretty=format:`,
`%(committerdate:unix)` en un `for-each-ref`) no tiene formato, ni `Z`,
ni huso horario que una version de Python pueda leer distinto de otra --
mata la clase entera de fallo, no solo el sintoma. Ya se habia decidido
asi una vez en el sistema anterior por este mismo motivo y se perdio al
reescribirlo [`lib/boot_git_checks.py:117`]; esta vez el unico lector
vive aqui y los cinco sitios lo llaman -- los cuatro de lib/memory/ mas
el transcript del cierre de sesion, que vive en una skill y llega hasta
aqui por sys.path igual que el resto de scripts del toolkit --, ninguno
vuelve a convertir texto
por su cuenta.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

_UNKNOWN = "unknown"


def _as_utc(moment: datetime) -> datetime | None:
    if not isinstance(moment, datetime):
        return None
    if moment.tzinfo is None:
        # Sin zona horaria se asume UTC, igual que hacia `time_ago()`:
        # restarle una fecha con zona lanzaria, y perder el arranque por
        # eso no compensa.
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def utc_label(moment: datetime) -> str:
    """"2026-08-05 16:04 UTC". Siempre en UTC: se trabaja desde mas de un
    sitio y una hora local no dice lo mismo en los dos."""
    utc = _as_utc(moment)
    if utc is None:
        return _UNKNOWN
    return f"{utc:%Y-%m-%d %H:%M} UTC"


def from_git_seconds(raw: str) -> datetime:
    """El `datetime` UTC-aware de lo que git escribe en segundos-epoch --
    `%at` en un `--pretty=format:`, `%(committerdate:unix)` en un
    `for-each-ref`. Unico lector del historial de este tipo: `query.py`,
    `context.py`, `health_plans.py` y `remote.py` pasan su fecha de autor
    por aqui, ninguno convierte texto de git por su cuenta [ver el porque
    completo en el docstring del modulo].

    No atrapa nada: si `raw` no es un numero, `int()` lanza `ValueError`
    tal cual y se propaga. Una fecha que no se puede leer no puede volver
    a devolver `None` ni "seguir como si no hubiera pasado nada" -- eso es
    indistinguible de "no hay actividad", el mismo silencio que esta
    pieza existe para impedir [condicion del encargo, 2026-08-08].
    """
    return datetime.fromtimestamp(int(raw), tz=timezone.utc)


def ago(moment: datetime, now: datetime | None = None) -> str:
    """"2 h ago", "3 days ago", "2 weeks ago".

    En ingles: es una etiqueta de estado de la cabecera, no contenido
    explicativo [B11 -- "deja de poner cosas en español cuando son en
    ingles: hablo de recuentos, avisos, restricciones"]. Mismas palabras
    que usaba `time_ago()` del arranque anterior.
    """
    utc = _as_utc(moment)
    if utc is None:
        return _UNKNOWN
    reference = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    if reference is None:
        return _UNKNOWN

    delta = reference - utc
    if delta < timedelta(0):
        return "in the future"

    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    if seconds < 604800:
        days = seconds // 86400
        return "1 day ago" if days == 1 else f"{days} days ago"
    weeks = seconds // 604800
    return "1 week ago" if weeks == 1 else f"{weeks} weeks ago"
