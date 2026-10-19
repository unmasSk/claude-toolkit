"""lib/memory/boot_common.py -- lo que comparten `bin/memory/boot.py` y
`hooks/boot_launcher.py`: donde queda el informe del arranque, como se
deja en su sitio un aviso de fallo, y como se lee un tope en segundos.

Vive en un solo sitio porque el aviso de fallo existe para que nadie lea
el informe de una sesion anterior como el de hoy: si el lanzador lo
escribiera en una ruta y `boot.py` en otra, el informe viejo seguiria
pareciendo de hoy sin que nada lo dijera [Cerberus F3, 2026-10-19].
"""

import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import gitcmd
import timefmt

# La carpeta esta ignorada por git en todos los proyectos del toolkit: es
# estado de la sesion, no memoria.
_REPORT_DIR = (".claude", ".unmassk")
_REPORT_NAME = "boot-latest.txt"

# Hora (segundos epoch) a la que el lanzador corta `boot.py`. La pone el
# lanzador solo en el entorno de `boot.py`; sin ella (boot a mano) los
# pasos de red usan su tope propio.
BOOT_ENDS_AT_ENV = "UNMASSK_BOOT_ENDS_AT"
# Lo que se guarda tras los pasos de red para leer la memoria y escribir
# el informe: el fetch y `gh` comparten lo que quede del tope del
# lanzador, sin comerse este tramo, para que el informe (con sus avisos)
# llegue siempre antes del corte [Moriarty T2, 2026-10-19: 10 s + 15 s
# se comian los 25 s enteros y la sesion se quedaba sin informe].
_AFTER_NETWORK_RESERVE = 3.0


def report_path(root: Path) -> Path:
    """Ruta del informe del arranque en el repositorio `root`. No crea nada."""
    return Path(root).joinpath(*_REPORT_DIR, _REPORT_NAME)


def write_failure_marker(
    root: Path, headline: str, body: str, started: float | None = None
) -> Path | None:
    """Sustituye el informe de `root` por un aviso de fallo fechado y
    devuelve su ruta. Lanza si no se puede escribir: quien llama decide
    si eso se dice o se calla.

    Con `started` (segundos epoch del arranque que fallo), un informe
    escrito despues de esa hora no se toca y se devuelve `None`: es de
    otra sesion que arranco a la vez sobre el mismo repositorio y le fue
    bien, y es el de hoy [Moriarty RACE, 2026-10-19]."""
    destination = report_path(root)
    if started is not None:
        try:
            if destination.stat().st_mtime >= started:
                return None
        except FileNotFoundError:
            pass
    destination.parent.mkdir(parents=True, exist_ok=True)
    stamp = timefmt.utc_label(datetime.now(timezone.utc))
    gitcmd.atomic_write(destination, f"⚠️  {headline} — {stamp}\n\n{body}")
    return destination


def env_seconds(name: str, default: float) -> float:
    """Segundos leidos de la variable `name` en cada llamada; un valor que
    no es un numero positivo y finito vuelve a `default`, nunca revienta
    el arranque por una errata."""
    try:
        value = float(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if math.isfinite(value) and value > 0 else default


def network_budget(cap: float) -> float:
    """Segundos para un paso de red del arranque: `cap`, recortado a lo
    que queda hasta el corte del lanzador menos la reserva final. `<= 0`
    quiere decir que no queda tiempo: el paso se salta y se dice."""
    try:
        ends_at = float(os.environ.get(BOOT_ENDS_AT_ENV, ""))
    except ValueError:
        return cap
    if not math.isfinite(ends_at):
        return cap
    return min(cap, ends_at - time.time() - _AFTER_NETWORK_RESERVE)
