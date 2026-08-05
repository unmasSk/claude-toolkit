"""Contrato de lib/memory/emojis.py -- PIEZAS.md Sec.5.2.

emojis.py NO EXISTE TODAVIA (hoy hay un colors.py que el contrato declara
que NO cumple -- 7 constantes ANSI sin consumidor, un mapeo que mezcla
tipos con canales exentos, y le faltan simbolos que las salidas exigen;
se reescribe entero con otro nombre). Estos tres tests deben fallar al
importar, por diseno -- es el RED del modo test-first. Uno por fila de la
tabla "Sus tests" de Sec.5.2, ni uno mas.

El fixture `emojis` importa por ruta de fichero (`import_lib_memory_module`,
ver conftest.py) para que cada test falle individualmente con la causa
real (`FileNotFoundError`: lib/memory/emojis.py no existe todavia), en
vez de un unico error de coleccion para todo el fichero.

No se toca produccion: si `lib/memory/emojis.py` no existe, estos tests
se quedan en rojo tal cual estan -- eso es lo esperado.
"""

import pytest

from .conftest import import_lib_memory_module

# Los siete tipos del vocabulario, letra -> descripcion, tal como los cita
# PIEZAS.md Sec.5.2 "Superficie": "D" decision, "M" memo, "R" restriction,
# "Q" question, "X" discarded, "I" incident, "B" blocker.
SEVEN_TYPES = ("D", "M", "R", "Q", "X", "I", "B")


@pytest.fixture
def emojis():
    return import_lib_memory_module("emojis")


def test_seven_types_have_emoji_and_no_extra(emojis):
    """Fila 1: los siete tipos del vocabulario tienen emoji, y no hay
    ninguno de mas.

    Fallo real que previene: se anade un tipo y su commit sale sin
    emoji, o queda un emoji de un tipo que ya no existe -- exactamente el
    Fallo 2 que el contrato midio en el `colors.py` de hoy (su `EMOJIS`
    mezcla los siete tipos con "CONTEXT" y "WIP", que no son tipos).
    """
    assert set(emojis.TYPE_EMOJI.keys()) == set(SEVEN_TYPES)
    for type_letter in SEVEN_TYPES:
        assert emojis.TYPE_EMOJI[type_letter]


def test_mappings_are_immutable(emojis):
    """Fila 2: los mapeos son inmutables.

    Fallo real que previene: un modulo los muta en caliente y otro lee
    algo distinto en el mismo proceso.

    Cada intento de mutacion va precedido de un `assert ... in` sobre la
    clave real (no una inventada): `MappingProxyType` rechaza CUALQUIER
    asignacion con `TypeError` exista o no la clave, asi que probar contra
    una clave que no existe pasa en verde igual que contra una real -- no
    prueba nada concreto del contrato. El `in` ata el test a la clave que
    de verdad usa produccion (`emojis.py`): si algun dia se renombra, este
    assert es el que rompe, no el intento de mutacion.
    """
    assert "D" in emojis.TYPE_EMOJI
    with pytest.raises(TypeError):
        emojis.TYPE_EMOJI["D"] = "x"
    assert "next" in emojis.CHANNEL_EMOJI
    with pytest.raises(TypeError):
        emojis.CHANNEL_EMOJI["next"] = "x"
    assert "restricciones" in emojis.SECTION_EMOJI
    with pytest.raises(TypeError):
        emojis.SECTION_EMOJI["restricciones"] = "x"


def test_no_emoji_repeats_between_types(emojis):
    """Fila 3: ningun emoji se repite entre tipos.

    Fallo real que previene: dos tipos indistinguibles de un vistazo en
    el archivo, que es el unico fichero que los mezcla (ARCHIVED.md,
    PIEZAS.md Sec.5.2 "De que salida se deriva").
    """
    values = list(emojis.TYPE_EMOJI.values())
    assert len(set(values)) == len(values)
