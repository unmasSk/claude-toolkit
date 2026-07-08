"""
UTF-8 stream guard (issue #52, T1).

House (round 2, CI run 28897259775) root-caused Windows CI failures to W1:
no entry point under unmassk-toolkit/bin/*.py or hooks/*.py forces UTF-8 on
stdout/stderr. Under a Windows console using a legacy codepage (e.g. cp1252,
the default for many non-English Windows locales), any print() of an
emoji/arrow (-> up-arrow compass pin box-drawing dash) raises
UnicodeEncodeError and the process exits 1. Reproducible on any OS via
PYTHONIOENCODING=cp1252. See tests/test_encoding_contract.py for the four
reproduced scenarios.

Call force_utf8_streams() as the FIRST executable statement in every
bin/*.py and hooks/*.py entry point, immediately after the sys.path
mutation that makes lib/ importable and before any other import that might
print or format Unicode text.

Fail-open contract: this guard must NEVER itself be a source of a crash —
that would defeat its own purpose and violate the boot fail-open contract
every hook in this project already follows. sys.stdout/sys.stderr may not
support reconfigure() at all (older Python), may already be detached,
redirected to something that isn't a TextIOWrapper, or replaced by a test
harness — any such failure is swallowed silently, never raised.
errors="replace" is the belt-and-braces half of the fix: even after forcing
UTF-8, if some remaining character truly cannot be represented, output
degrades visually (a U+FFFD replacement char) instead of raising.
"""

import sys


def force_utf8_streams() -> None:
    """Reconfigure stdout and stderr to UTF-8 with errors="replace".

    Safe to call multiple times, safe to call when stdout/stderr are None,
    closed, detached, or otherwise not reconfigurable. Never raises.
    """
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
            # AttributeError: stream doesn't actually support reconfigure
            #   despite exposing the attribute (unusual wrapper).
            # ValueError: stream already closed/detached.
            # OSError: underlying fd-level failure reconfiguring.
            # TypeError: `reconfigure` attribute exists but isn't callable
            #   (e.g. a stray monkey-patch replacing it with a non-callable
            #   value) — getattr() above only checks presence, not
            #   callability, so the call itself can raise TypeError.
            # Any of these means we leave the stream exactly as it was —
            # never let the guard itself become the crash it exists to
            # prevent.
            pass
