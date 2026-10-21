"""Force UTF-8 on stdout/stderr so printing emojis never crashes on a legacy codepage.

Call it first in every entry point, right after lib/ is put on sys.path.
"""

import sys


def force_utf8_streams() -> None:
    """Reconfigure stdout and stderr to UTF-8 with errors="replace"; never raises."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError, TypeError):
            # Closed, detached or replaced stream: leave it as it was.
            pass
