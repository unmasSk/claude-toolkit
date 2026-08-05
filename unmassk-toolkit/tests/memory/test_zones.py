"""Contrato de lib/memory/zones.py -- PIEZAS.md Sec.6.2.

zones.py NO EXISTE TODAVIA. Estos cinco tests deben fallar al importar,
por diseno -- es el RED del modo test-first. Uno por fila de la tabla
"Sus tests" de Sec.6.2, ni uno mas:

  1. Un alias resuelve a su zona canonica.
  2. Una zona inexistente devuelve None, no una excepcion ni una cadena
     vacia.
  3. `candidates` encuentra la zona que se escribio mal por poco.
  4. Dos `add` concurrentes no se pisan.
  5. Ida y vuelta: una zona con tildes en su descripcion y varios alias,
     escrita con `add` y releida con `load`, vuelve identica.

El fixture `zones` importa por ruta de fichero (`import_lib_memory_module`,
ver conftest.py) para que cada test falle individualmente con la causa
real (`FileNotFoundError`: lib/memory/zones.py no existe todavia), en vez
de un unico error de coleccion para todo el fichero -- mismo patron que
test_emojis.py y test_vocabulary.py.

Cada test pide el fixture `zones` ANTES que `model` en su firma: pytest
instancia los fixtures pedidos por un test en el orden en que aparecen,
asi que si `zones.py` no existe el fallo se reporta ahi -- nunca por
`model.py`, aunque tampoco exista todavia -- y la causa reportada sigue
senalando la pieza de este contrato, no una dependencia suya.

`model.py` (Sec.5.3, Capa 0) todavia no existe tampoco. Los tests de este
fichero construyen sus zonas de prueba con `model.Zone` en vez de escribir
un `zones.json` a mano: la forma exacta del fichero no esta fijada en
Sec.6.2 ("De que salida se deriva" solo cita el TEXTO del rechazo, no el
formato de disco), y adivinar un esquema seria fabricar un fixture que
`load()` tendria que casualmente aceptar -- exactamente lo que
unmassk-standards SS34 prohibe. En su lugar, cada test siembra datos
escribiendo con `zones.add()` y comprobando lo que devuelve `zones.load()`
sobre esa misma escritura: la pareja productor/consumidor real, nunca un
valor esperado inventado a mano.

No se toca produccion: si `lib/memory/zones.py` no existe, estos tests se
quedan en rojo tal cual estan -- eso es lo esperado.
"""

import json
import threading

import pytest

from .conftest import import_lib_memory_module


@pytest.fixture
def zones():
    return import_lib_memory_module("zones")


@pytest.fixture
def model():
    return import_lib_memory_module("model")


def test_alias_resolves_to_canonical_zone(zones, model, tmp_path):
    """Fila 1: un alias resuelve a su zona canonica.

    Fallo real que previene: conviven "front" y "frontend" como zonas
    distintas y la memoria se parte en dos.
    """
    path = tmp_path / "zones.json"
    canonical = model.Zone(
        name="frontend",
        description="interfaz de usuario",
        aliases=("front", "fe"),
    )
    zones.add(canonical, path)
    loaded = zones.load(path)

    assert zones.resolve("front", loaded) == "frontend"
    assert zones.resolve("fe", loaded) == "frontend"


def test_resolve_unknown_zone_returns_none_not_exception_or_empty_string(
    zones, model, tmp_path
):
    """Fila 2: una zona inexistente devuelve None, no una excepcion ni una
    cadena vacia.

    Fallo real que previene: un fallo que se confunde con "zona sin
    notas" y pasa callado.
    """
    path = tmp_path / "zones.json"
    zones.add(model.Zone(name="billing", description="cobros", aliases=()), path)
    loaded = zones.load(path)

    result = zones.resolve("nonexistent-zone-xyz", loaded)

    assert result is None


def test_candidates_finds_near_miss_typo(zones, model, tmp_path):
    """Fila 3: `candidates` encuentra la zona que se escribio mal por
    poco.

    Fallo real que previene: el rechazo llega sin candidatas y el
    usuario crea el sinonimo igualmente.
    """
    path = tmp_path / "zones.json"
    zones.add(
        model.Zone(
            name="billing",
            description="cobros, pasarela de pago, suscripciones",
            aliases=(),
        ),
        path,
    )
    zones.add(
        model.Zone(
            name="invoices",
            description="documentos de factura emitidos al cliente",
            aliases=(),
        ),
        path,
    )
    zones.add(model.Zone(name="auth", description="autenticacion", aliases=()), path)
    loaded = zones.load(path)

    result = zones.candidates("biling", loaded)  # typo: falta una "l"

    assert result, "candidates() no devolvio nada para un typo de un caracter"
    assert any(zone.name == "billing" for zone in result), (
        f"'billing' no aparece entre las candidatas para 'biling': {result}"
    )


def test_two_concurrent_adds_do_not_clobber_each_other(zones, model, tmp_path):
    """Fila 4: dos `add` concurrentes no se pisan.

    Fallo real que previene: una zona dada de alta desaparece porque otra
    escritura la sobrescribio -- perdida silenciosa.
    """
    path = tmp_path / "zones.json"
    zones.add(model.Zone(name="seed", description="zona inicial", aliases=()), path)

    barrier = threading.Barrier(2)
    errors = []

    def add_zone(zone):
        try:
            barrier.wait(timeout=5)
            zones.add(zone, path)
        except Exception as exc:  # se reporta, no se traga
            errors.append(exc)

    zone_a = model.Zone(name="billing", description="cobros", aliases=())
    zone_b = model.Zone(name="invoices", description="facturas", aliases=())

    thread_a = threading.Thread(target=add_zone, args=(zone_a,))
    thread_b = threading.Thread(target=add_zone, args=(zone_b,))
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)

    assert not errors, f"add() lanzo bajo escritura concurrente: {errors}"

    loaded = zones.load(path)
    assert set(loaded.keys()) >= {"seed", "billing", "invoices"}, (
        "una de las dos escrituras concurrentes se perdio: "
        f"quedaron {set(loaded.keys())}"
    )


def test_add_then_load_round_trips_accented_description_and_aliases_identically(
    zones, model, tmp_path
):
    """Fila 5: ida y vuelta -- una zona con tildes en su descripcion y
    varios alias, escrita con `add` y releida con `load`, vuelve
    identica.

    Fallo real que previene: una descripcion truncada o un alias mal
    guardado -- el rechazo imprimiria algo distinto de lo que se
    escribio, y nadie lo notaria.

    El valor esperado es el mismo objeto `original` que este test acaba
    de escribir, releido a traves del seam real (`load()`) -- nunca una
    cadena tecleada a mano (unmassk-standards SS34).
    """
    path = tmp_path / "zones.json"
    original = model.Zone(
        name="facturacion",
        description="cobros, pasarela de pago, suscripciones y anulaciones segun el pais",
        aliases=("billing", "cobros", "pagos"),
    )

    zones.add(original, path)
    loaded = zones.load(path)
    reloaded = loaded["facturacion"]

    # Comparacion campo a campo, no `==` de objeto: `zones` y `model` se
    # cargan por separado via `import_lib_memory_module` (dos modulos sin
    # paquete comun -- ver docstring del fichero), asi que aunque
    # `zones.load()` devuelva instancias de un `Zone` estructuralmente
    # identico, puede no ser la MISMA clase que `model.Zone` importada
    # aqui -- el `__eq__` generado por `@dataclass` compara
    # `self.__class__ is other.__class__` primero y devolveria
    # `NotImplemented` (falso) aunque los datos sean iguales byte a byte.
    # Comparar por campo evita ese falso negativo, que no es un fallo de
    # produccion sino un artefacto de como esta cargado el test.
    assert reloaded.name == original.name
    assert reloaded.description == original.description
    assert reloaded.aliases == original.aliases


def test_regression_aliases_as_string_fails_loud_naming_file_and_zone(zones, tmp_path):
    """REGRESION (arreglado 2026-08-02): un `zones.json` con
    `"aliases": "front"` (una cadena en vez de una lista) pasaba
    `json.load` sin problema, y `tuple("front")` la troceaba LETRA A
    LETRA en cinco alias falsos (`'f'`, `'r'`, `'o'`, `'n'`, `'t'`) sin
    avisar a nadie -- a partir de ahi, resolver la zona `'f'` acababa
    resolviendo (por error) a la zona corrupta. El arreglo valida que
    `aliases` sea una lista de texto y falla EN ALTO, nombrando el
    fichero y la zona afectada, en vez de aceptar la forma equivocada en
    silencio.

    Esta propiedad es distinta de la de los otros cuatro (`test_format.py`):
    aqui lo que se prueba no es "lo que entra vuelve identico" sino que
    falla en alto, con el fichero y la zona nombrados en el mensaje.

    Confirmado en vivo contra una copia con la validacion de forma
    deshecha (scratchpad de esta sesion,
    `mutcheck/bug5_aliases_string/`, vuelta a `tuple(aliases)` ciego):
    `load()` no lanzaba y devolvia `aliases == ('f', 'r', 'o', 'n', 't')`
    con ese arreglo desecho; con el codigo real, lanza `ValueError`
    nombrando fichero y zona.
    """
    path = tmp_path / "zones.json"
    path.write_text(
        json.dumps({"billing": {"description": "cobros", "aliases": "front"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        zones.load(path)

    message = str(exc_info.value)
    assert path.name in message, f"el error no nombra el fichero: {message}"
    assert "billing" in message, f"el error no nombra la zona: {message}"
