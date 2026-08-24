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
from pathlib import Path

import pytest

from .conftest import _REAL_REPO_ROOT, import_lib_memory_module


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


# ---------------------------------------------------------------------------
# Contrato compartido de normalizacion (D-054 + regla nueva del propietario,
# 2026-08-24): todo texto que se compare o se use como clave se normaliza a
# minusculas Y SIN ACENTOS. Hasta ahora `zones.normalize()` solo hacia
# `.lower()`. Estos tests anclan el comportamiento en el PUNTO DE ENTRADA
# real (`zones.normalize`, `zones.resolve`) -- nunca en un simbolo fisico
# compartido: la funcion que hace el trabajo puede vivir en cualquier sitio
# dentro de lib/memory/ (frontera vigilada por test_boundary.py, que sigue
# en verde), lo unico que este fichero prueba es lo que `zones.py` hace con
# la entrada.
# ---------------------------------------------------------------------------


def test_normalize_treats_case_and_accent_variants_as_the_same_form(zones):
    """Punto 1 del contrato: 'Diseño'/'DISEÑO'/'diseno' normalizan a la
    MISMA forma, igual que 'Cafe'/'cafe'.

    RED hoy: `normalize()` solo aplica `.lower()`, asi que
    'Diseño'.lower() == 'diseño' (la ñ no se toca) y 'diseno' se queda
    'diseno' -- dos cadenas distintas, este assert falla.
    """
    assert (
        zones.normalize("Diseño") == zones.normalize("DISEÑO") == zones.normalize("diseno")
    ), (
        f"'Diseño'/'DISEÑO'/'diseno' deberian normalizar a la misma forma: "
        f"{zones.normalize('Diseño')!r} / {zones.normalize('DISEÑO')!r} / "
        f"{zones.normalize('diseno')!r}"
    )
    assert zones.normalize("Café") == zones.normalize("cafe")


def test_normalize_non_string_input_returns_empty_string_without_raising(zones):
    """Punto 1 del contrato: entrada no-string no revienta -- devuelve
    cadena vacia.

    Fallo real que previene: un `zones.json` corrupto con un nombre de
    zona no-string tumbando `normalize()` con un `AttributeError` sin
    avisar de donde vino, en vez de dejar que `load()` (que SI valida
    tipos, ver test de regresion mas arriba en este fichero) sea quien
    decide que hacer con la corrupcion.

    RED hoy: `normalize()` hace `name.lower()` directo -- `None.lower()`
    lanza `AttributeError`, no devuelve `""`.
    """
    assert zones.normalize(None) == ""
    assert zones.normalize(123) == ""


def test_zone_created_with_accent_is_found_by_search_without_accent_and_different_case(
    zones, model, tmp_path
):
    """Punto 2 del contrato -- ZONAS: crear/buscar una zona con acento y
    encontrarla escrita sin acento y en otra caja.

    Fallo real que previene: dos sesiones nombrando la misma zona
    "Diseño" y "DISENO" acaban con dos zonas que nunca se cruzan entre
    si -- memoria partida en dos, sin un solo error (el mismo patron ya
    medido para 'Boot'/'boot' que motivo `normalize()` en primer lugar).

    RED hoy: `zones.add()` persiste el nombre como `normalize("Diseño")`
    == 'diseño' (acento intacto); buscar 'DISENO' normaliza a 'diseno'
    (sin ñ) -- no coincide con la clave real 'diseño', `resolve()`
    devuelve `None`.
    """
    path = tmp_path / "zones.json"
    zones.add(
        model.Zone(name="Diseño", description="diseño visual del producto", aliases=()),
        path,
    )
    loaded = zones.load(path)

    resolved = zones.resolve("DISENO", loaded)

    assert resolved is not None, (
        "una zona creada como 'Diseño' no se encontro buscando 'DISENO' "
        "(distinta caja, sin acento)"
    )
    assert resolved == zones.resolve("diseño", loaded), (
        "buscar con acento y buscar sin acento deberian resolver a la MISMA "
        "zona canonica"
    )


def test_real_project_zones_do_not_collide_after_accent_normalization(zones):
    """Punto 2 del contrato -- el guardian que importa: las 24 zonas
    reales de este proyecto, hoy todas sin acento y ya distintas entre
    si, siguen siendo distintas tras normalizar tambien por acentos.
    Ninguna se fusiona por el cambio.

    Metrica calculada contra las zonas REALES del proyecto (leidas de
    `.claude/project-memory/zones.json` del propio repositorio), nunca
    una lista de nombres perdonados escrita a mano -- si alguna vez dos
    zonas reales colisionaran al quitar acentos, este test lo dice sin
    que nadie tenga que mantener una lista de excepciones (mismo
    criterio que ya goberno el cambio de lista-de-perdonados a metrica
    calculada en `indexes.counts`).

    Se queda en verde antes Y despues del cambio -- es una red de
    seguridad, no el comportamiento nuevo que este contrato introduce.
    """
    real_zones_path = Path(_REAL_REPO_ROOT) / ".claude" / "project-memory" / "zones.json"
    with open(real_zones_path, "r", encoding="utf-8") as fh:
        real_zone_names = list(json.load(fh).keys())

    assert real_zone_names, "zones.json real esta vacio -- nada que proteger en este test"

    normalized = [zones.normalize(name) for name in real_zone_names]

    assert len(set(normalized)) == len(real_zone_names), (
        "dos o mas zonas reales se fusionaron al normalizar tambien por "
        f"acentos: {real_zone_names!r} -> {normalized!r}"
    )


def test_regression_case_only_zone_names_still_resolve(zones, model, tmp_path):
    """Punto 4 del contrato -- regresion: lo que hoy ya resuelve solo por
    minuscula (sin que un acento este de por medio) sigue resolviendo
    igual tras anadir el paso de acentos.
    """
    path = tmp_path / "zones.json"
    zones.add(
        model.Zone(name="Boot", description="arranque de sesion", aliases=("Startup",)),
        path,
    )
    loaded = zones.load(path)

    assert zones.resolve("BOOT", loaded) == "boot"
    assert zones.resolve("startup", loaded) == "boot"
