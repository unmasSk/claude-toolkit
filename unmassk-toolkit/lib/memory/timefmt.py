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

Lo que NO se trae: leer epoch y cadenas ISO. Aqui todo el mundo maneja
`datetime` ya construido -- quien lo parsea es quien lo saca de git.
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
