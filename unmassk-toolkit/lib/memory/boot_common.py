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
from datetime import datetime, timezone
from pathlib import Path

import gitcmd
import timefmt

# La carpeta esta ignorada por git en todos los proyectos del toolkit: es
# estado de la sesion, no memoria.
_REPORT_DIR = (".claude", ".unmassk")
_REPORT_NAME = "boot-latest.txt"


def report_path(root: Path) -> Path:
    """Ruta del informe del arranque en el repositorio `root`. No crea nada."""
    return Path(root).joinpath(*_REPORT_DIR, _REPORT_NAME)


def write_failure_marker(root: Path, headline: str, body: str) -> Path:
    """Sustituye el informe de `root` por un aviso de fallo fechado y
    devuelve su ruta. Lanza si no se puede escribir: quien llama decide
    si eso se dice o se calla."""
    destination = report_path(root)
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
