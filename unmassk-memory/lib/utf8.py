"""Fuerza UTF-8 en stdout/stderr.

Sin esto, un print() de un emoji (los que usa colors.EMOJIS) revienta con
UnicodeEncodeError bajo una consola con codepage heredado (p.ej. cp1252,
el que trae por defecto un Windows en varios idiomas no ingleses).
Reproducible en cualquier sistema operativo forzando
PYTHONIOENCODING=cp1252.

Se llama como PRIMERA sentencia ejecutable de cada punto de entrada
(bin/*.py, hooks/*.py), justo despues de la insercion de lib/ en
sys.path y antes de cualquier otro import que pueda imprimir texto.

Contrato de fallo abierto: esta funcion nunca puede ser ella misma el
origen de un crash -- eso traicionaria su proposito. Si el stream no
admite reconfigure() (stream ya cerrado, sustituido por un test, o
version de Python que no lo soporta), el fallo se traga en silencio y
el programa sigue con el stream tal cual estaba.
"""

import sys


def force_utf8_streams() -> None:
    """Reconfigura stdout y stderr a UTF-8, sustituyendo por un caracter
    de reemplazo lo que no se pueda representar en vez de reventar.

    Segura de llamar varias veces. Segura si stdout/stderr son None, ya
    estan cerrados, desacoplados, o no exponen reconfigure(). Nunca
    lanza una excepcion.
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
            # AttributeError: el stream expone el atributo pero no
            #   soporta reconfigure() de verdad (wrapper atipico).
            # ValueError: el stream ya esta cerrado o desacoplado.
            # OSError: fallo a nivel de descriptor de fichero.
            # TypeError: reconfigure fue sustituido por un valor no
            #   invocable (monkeypatch de un test, por ejemplo).
            # Cualquiera de estos deja el stream tal cual estaba -- el
            # guard no se convierte en el crash que existe para evitar.
            pass
