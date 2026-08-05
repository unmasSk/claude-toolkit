"""Contrato de lib/memory/ids.py -- PIEZAS.md Sec.7.2.

ids.py NO EXISTE TODAVIA (tampoco lib/memory/model.py, del que sale la
clase `IndexLine` que esta pieza recibe). Estos tres tests deben fallar al
importar, por diseno -- es el RED del modo test-first. Uno por fila de la
tabla "Sus tests" de Sec.7.2, ni una mas:

  1. `D-001` en un indice vacio; `D-031` tras treinta.
  2. El contador es POR TIPO: treinta decisiones no mueven el contador de
     memos.
  3. Dos notas con el mismo identificador se detectan.

El fixture `ids` importa por ruta de fichero (`import_lib_memory_module`,
ver conftest.py) para que cada test falle individualmente con la causa
real (`FileNotFoundError`: lib/memory/ids.py no existe todavia), en vez
de un unico error de coleccion para todo el fichero -- mismo patron que
test_zones.py y test_similar.py. Se lista antes que `make_index_line` en
la firma de cada test para que sea ESE fallo, y no el de `model.py`
(tambien inexistente, y al que `make_index_line` llega por dentro), el
que se reporte primero -- pytest instancia los fixtures de un test en el
orden en que aparecen como parametros.

Un detalle del contrato que gobierna lo que este fichero NO prueba:
Sec.7.2 dice literal que ids.py "no repara un duplicado. Es alarma
pasiva: detecta y lo ensena" -- reparar renumeraria una nota ya escrita
y arrastraria todos los punteros que la citan, y el diseno lo prohibe
explicitamente. `find_duplicates()` solo se prueba detectando: ningun
test de este fichero espera que mute `index`, renumere un id ni escriba
nada.

Y otro, de Sec.7.3 ("Quien la llama": "`ids` NO [lo llama]. Recibe el
indice ya cargado como parametro, no lo lee el"): por eso ningun test de
este fichero toca disco ni usa `tmp_repo` -- el indice siempre se
construye a mano con `model.IndexLine` y se pasa directamente a las dos
funciones.

No se toca produccion: si `lib/memory/ids.py` no existe, estos tests se
quedan en rojo tal cual estan -- eso es lo esperado.
"""

import pytest

from .conftest import import_lib_memory_module


@pytest.fixture
def ids():
    return import_lib_memory_module("ids")


@pytest.fixture
def make_index_line():
    """Factoria de `model.IndexLine` -- carga `model` por dentro (mismo
    patron que `make_note` en test_similar.py), nunca a traves de un
    fixture `model` propio, para que el orden de parametros del test siga
    determinando que fallo se reporta primero.
    """
    model = import_lib_memory_module("model")

    def _make(**overrides):
        fields = dict(
            id="D-001",
            zone1="product",
            zone2="auth",
            headline="placeholder headline",
        )
        fields.update(overrides)
        return model.IndexLine(**fields)

    return _make


def test_next_id_starts_at_one_on_empty_index_and_continues_after_thirty(
    ids, make_index_line
):
    """Fila 1: `D-001` en un indice vacio; `D-031` tras treinta.

    Fallo real que previene: empezar en cero cada sesion y pisar
    identificadores existentes.
    """
    assert ids.next_id("D", ()) == "D-001"

    thirty_decisions = tuple(
        make_index_line(id=f"D-{n:03d}") for n in range(1, 31)
    )

    assert ids.next_id("D", thirty_decisions) == "D-031"


def test_counter_is_per_type_not_global(ids, make_index_line):
    """Fila 2: el contador es POR TIPO -- treinta decisiones no mueven el
    contador de memos.

    Fallo real que previene: un hueco en la numeracion que hace pensar
    que faltan notas.
    """
    thirty_decisions = tuple(
        make_index_line(id=f"D-{n:03d}") for n in range(1, 31)
    )

    assert ids.next_id("M", thirty_decisions) == "M-001"


def test_find_duplicates_detects_two_notes_with_the_same_id(
    ids, make_index_line
):
    """Fila 3: dos notas con el mismo identificador se detectan.

    Fallo real que previene: dos notas distintas indistinguibles en los
    punteros -- un racimo apuntando a la equivocada.

    NOTA: esta pieza NO repara el duplicado, solo lo detecta y lo ensena
    (Sec.7.2, "Que NO hace" -- alarma pasiva a proposito). Este test no
    espera renumeracion ni mutacion de `index`: solo que el id repetido
    aparezca en lo que devuelve `find_duplicates`, y que un id sin
    conflicto no aparezca (control negativo, para que el assert no pase
    con una implementacion que devuelva "todos los ids" a ciegas).
    """
    index = (
        make_index_line(id="D-005", headline="version original"),
        make_index_line(
            id="D-005", headline="version distinta, mismo identificador"
        ),
        make_index_line(id="D-006", headline="nota sin conflicto"),
    )

    duplicates = ids.find_duplicates(index)

    assert "D-005" in duplicates
    assert "D-006" not in duplicates
