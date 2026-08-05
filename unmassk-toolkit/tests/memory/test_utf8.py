"""Contrato de lib/memory/utf8.py -- PIEZAS.md Sec.5.1.

utf8.py YA EXISTE y el contrato dice que CUMPLE (veredicto en Sec.3.2 y
Sec.5.1: "cumple el contrato y se queda"). Estos tres tests no cambian
eso -- son la red que impide que alguien lo rompa despues. Uno por fila
de la tabla "Sus tests" de Sec.5.1, ni uno mas.

Carga el modulo real por ruta de fichero via `import_lib_memory_module`
(ver conftest.py) para evitar la colision de nombre `memory` documentada
ahi -- nunca `import memory.utf8` a pelo.
"""

import io
import sys

import pytest

from .conftest import import_lib_memory_module

utf8 = import_lib_memory_module("utf8")

# Los mismos caracteres que cita PIEZAS.md Sec.5.1 como "de que salida se
# deriva": los siete emojis de tipo, los tres de canal, y el aviso de key
# corregida -- fuente unica, no inventados en este fichero.
_TYPE_EMOJIS = ("🧭", "📌", "⚠️", "❓", "🚫", "🔥", "⛔")
_CHANNEL_EMOJIS = ("⏩", "🚧", "🧠")
_KEY_FIXED_MARK = ("✅",)
ELEVEN_EMOJIS = _TYPE_EMOJIS + _CHANNEL_EMOJIS + _KEY_FIXED_MARK
BOX_CHARS = ("═", "─", "├", "└", "║", "╔", "╝")

assert len(ELEVEN_EMOJIS) == 11, "la fila del contrato dice 11, no otro numero"
assert len(BOX_CHARS) == 7, "la fila del contrato dice 7, no otro numero"


def _make_cp1252_text_stream():
    """Un TextIOWrapper que arranca en cp1252 (el codepage heredado que
    revienta con estos caracteres), respaldado por un BytesIO legible."""
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
    return stream, buffer


class TestForceUtf8StreamsSurvivesCp1252Origin:
    """Fila 1: los 11 emojis y los 7 caracteres de caja se escriben en un
    flujo forzado a cp1252 y vuelven byte a byte.

    Fallo real que previene: la aduana emite su rechazo desde un hook: si
    el flujo de salida no sabe codificar (p.ej. '⛔' bajo cp1252), el hook
    no imprime un texto feo -- revienta, y el usuario ve un volcado de
    pila en vez de la pregunta que tenia que contestar.
    """

    def test_eleven_emojis_and_seven_box_chars_round_trip_from_cp1252(
        self, monkeypatch
    ):
        stream, buffer = _make_cp1252_text_stream()
        monkeypatch.setattr(sys, "stdout", stream)

        utf8.force_utf8_streams()

        payload = "".join(ELEVEN_EMOJIS + BOX_CHARS)
        sys.stdout.write(payload)
        sys.stdout.flush()

        assert buffer.getvalue().decode("utf-8") == payload


class TestForceUtf8StreamsIdempotent:
    """Fila 2: llamarla dos veces no cambia el estado ni lanza.

    Fallo real que previene: dos puntos de entrada encadenados (un script
    llamado desde `gitmem`) se rompen entre si si la segunda llamada
    reconfigura de una forma distinta o lanza.
    """

    def test_calling_twice_keeps_utf8_and_does_not_raise(self, monkeypatch):
        stdout_stream, _ = _make_cp1252_text_stream()
        stderr_stream, _ = _make_cp1252_text_stream()
        monkeypatch.setattr(sys, "stdout", stdout_stream)
        monkeypatch.setattr(sys, "stderr", stderr_stream)

        utf8.force_utf8_streams()
        encoding_after_first = (sys.stdout.encoding, sys.stderr.encoding)

        utf8.force_utf8_streams()  # no debe lanzar la segunda vez
        encoding_after_second = (sys.stdout.encoding, sys.stderr.encoding)

        assert encoding_after_first == ("utf-8", "utf-8")
        assert encoding_after_second == ("utf-8", "utf-8")


class TestForceUtf8StreamsWithoutReconfigure:
    """Fila 3: con un stdout sin reconfigure, no lanza y el programa sigue.

    Fallo real que previene: un `gitmem` con la salida redirigida a una
    tuberia (un objeto que no expone `reconfigure()`) deja de arrancar.
    """

    def test_stdout_without_reconfigure_does_not_raise_and_stream_stays_usable(
        self, monkeypatch
    ):
        class StreamWithoutReconfigure:
            def __init__(self):
                self.written = []

            def write(self, text):
                self.written.append(text)

            def flush(self):
                pass

        stream = StreamWithoutReconfigure()
        assert not hasattr(stream, "reconfigure")
        monkeypatch.setattr(sys, "stdout", stream)

        utf8.force_utf8_streams()  # no debe lanzar

        # "el programa sigue": el stream original sigue sirviendo para
        # escribir, tal cual estaba, sin que la funcion lo haya dejado
        # inutilizable.
        sys.stdout.write("still alive")
        assert stream.written == ["still alive"]
