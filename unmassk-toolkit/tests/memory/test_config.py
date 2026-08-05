"""Contrato de lib/memory/config.py -- PIEZAS.md Sec.6.3.

config.py NO EXISTE TODAVIA. Estos tres tests deben fallar al importar,
por diseno -- es el ROJO del modo test-first. Uno por fila de la tabla
"Sus tests" de Sec.6.3, ni una mas:

  1. Sin fichero, la aduana queda apagada.
  2. Sin fichero, el tipo de repositorio es el protegido.
  3. Un fichero corrupto falla en alto, no devuelve valores por defecto
     en silencio.

Un cuarto test se anadio despues (misma sesion, ya con `config.py`
implementado): Ultron introdujo una guarda de tipo que ninguna de las
tres filas de arriba pedia explicitamente -- `load()` no solo valida
que el fichero sea JSON valido, tambien que cada campo tenga el tipo
correcto. La declaro como desviacion, y al comprobarla resulto que
evita un fallo real: `{"customs_enabled": "false"}` (con comillas) es
JSON perfectamente valido, pero si nadie comprueba el tipo, un
consumidor Python evalua ese texto como verdadero (cadena no vacia),
encendiendo la aduana en silencio con el mismo ajuste que dice
apagarla. El propio docstring del modulo (lib/memory/config.py, lineas
25-30) ya lo deja escrito como parte del contrato de "fichero
corrupto" de la fila 3 -- este test es la prueba que faltaba para esa
frase.

El fixture `config` importa por ruta de fichero
(`import_lib_memory_module`, ver conftest.py) para que cada test falle
individualmente con la causa real (`FileNotFoundError`:
lib/memory/config.py no existe todavia), en vez de un unico error de
coleccion para todo el fichero -- mismo patron que test_emojis.py y
test_vocabulary.py.

No se toca produccion: si `lib/memory/config.py` no existe, estos tests
se quedan en rojo tal cual estan -- eso es lo esperado.

Por que estos tres valores no son comodidad, son seguridad (PIEZAS.md
Sec.6.3 + el encargo que acompana esta tarea): sin fichero de
configuracion la aduana nace APAGADA -- si naciera encendida, el primer
dia de instalacion bloquearia el sistema viejo que todavia esta en uso
-- y el tipo de repositorio cae del lado protegido (`gitflow`, main
protegido) para que un commit directo a un repo con auto-deploy no pase
inadvertido. Y un fichero corrupto tiene que fallar en alto: una aduana
apagada sin que nadie sepa que lo esta es un vigilante que no vigila y
encima no lo dice.

Fila 1 y fila 2 comparten el mismo escenario ("sin fichero") pero son
dos aserciones sobre dos campos distintos de `Config`, y la tabla de
Sec.6.3 las lista como dos filas separadas -- de ahi que sean dos tests,
no uno con dos asserts, siguiendo la regla de una aserta logica por
test.

Fila 3 es deliberadamente independiente de las dos anteriores: si
`load()` tratara "fichero corrupto" igual que "sin fichero" (devolviendo
`Config()` en silencio), esa `Config()` por defecto tambien tendria
`customs_enabled=False` -- la misma cifra que la fila 1 comprueba para
el caso correcto. Por eso la fila 3 no compara valores devueltos: exige
que `load()` LANCE ante contenido corrupto, que es la unica forma de
distinguir "silencio porque no hay fichero" (aceptado) de "silencio
porque el fichero esta roto" (el fallo que este test previene).
"""

import pytest

from .conftest import import_lib_memory_module


@pytest.fixture
def config():
    return import_lib_memory_module("config")


def test_missing_file_customs_has_no_explicit_setting(config, tmp_path):
    """Fila 1 -- REVISADA [DEUDA.md B19 punto 2, 2026-08-03]: sin fichero,
    ``customs_enabled`` no es ``False``, es ``None`` -- "sin ajuste
    explicito". Esta pieza ya no decide si la aduana queda encendida o
    apagada; solo carga (o no) un valor explicito del fichero. Quien
    resuelve el valor efectivo sin ajuste es ``hooks/customs.py``
    (``_customs_active`` / ``_project_has_notes``), que la enciende sola
    en cuanto el proyecto tiene su primera nota.

    Fallo real que este test sigue previniendo, con la lectura nueva: un
    ``load()`` que devolviera ``False`` en vez de ``None`` le mentiria a
    ese consumidor -- ``False`` es indistinguible de "el fichero dice
    explicitamente apagada", y le quitaria la posibilidad de encenderse
    sola sobre un proyecto con notas.
    """
    # "config.json" es el nombre del sistema NUEVO (ARQUITECTURA.md §6bis,
    # tabla `.claude/project-memory/`; PIEZAS.md Sec.6.3). No confundir
    # con "git-memory-config.json", el marcador del sistema viejo que
    # cita el propio texto de PIEZAS.md al derivar esta pieza ("hoy viven
    # en") -- ese es el origen historico del dato, no el fichero que
    # `config.load()` lee. El directorio es temporal (`tmp_path`), asi
    # que la ruta exacta (`.claude/project-memory/`) es indiferente aqui;
    # solo el nombre de fichero es parte del contrato que un test puede
    # confundir.
    missing_path = tmp_path / "config.json"
    assert not missing_path.exists()

    result = config.load(missing_path)

    assert result.customs_enabled is None


def test_missing_file_repo_type_is_the_protected_one(config, tmp_path):
    """Fila 2: sin fichero, el tipo de repositorio es el protegido.

    Fallo real que previene: un commit directo a `main` en un repo que
    despliega solo (gitflow, fail-closed: PIEZAS.md Sec.6.3 -- "sin
    fichero, el tipo de repositorio es el protegido").
    """
    missing_path = tmp_path / "config.json"
    assert not missing_path.exists()

    result = config.load(missing_path)

    # "gitflow" es el valor fail-closed citado literalmente en la
    # Superficie de PIEZAS.md Sec.6.3:
    # `repo_type: str = "gitflow"  # fail-closed: main protegido si no
    # se declara`. vocabulary.py no expone este dato -- no es una de sus
    # cinco tablas de datos cerrados (Sec.6.1) -- asi que no hay modulo
    # del que importarlo; el literal viene del propio contrato citado.
    assert result.repo_type == "gitflow"


def test_corrupt_file_fails_loud_instead_of_silent_defaults(config, tmp_path):
    """Fila 3: un fichero corrupto falla en alto, no devuelve valores
    por defecto en silencio.

    Fallo real que previene: la aduana apagada sin que nadie sepa que
    lo esta -- un vigilante que no vigila y encima no lo dice. Si
    `load()` se tragara el error de parseo y devolviera `Config()` por
    defecto, el sintoma seria identico al caso correcto de la fila 1
    (`customs_enabled=False`) y nadie distinguiria "no hay fichero
    todavia" de "hay un fichero roto que nadie esta leyendo".

    `pytest.raises(Exception)` a secas no basta: pasaria igual si
    `load()` revienta por un motivo AJENO al fichero corrupto (un bug
    interno que lanza `TypeError` en otra linea, por ejemplo), y ese
    verde no probaria lo que este test dice probar. Por eso, ademas de
    exigir que lance, se comprueba que el mensaje de la excepcion nombra
    el fichero que fallo -- la unica forma de confirmar que el fallo en
    alto senala SU causa real (PIEZAS.md Sec.7.1 fija el mismo principio
    para `gitcmd.run`: "el mensaje real, entero, nunca vacio ni
    recortado"). No se fija un tipo de excepcion concreto porque
    PIEZAS.md Sec.6.3 no lo declara -- solo dice "falla en alto" -- y
    fijar un tipo no citado seria inventar una regla que no esta en el
    contrato.
    """
    corrupt_path = tmp_path / "config.json"
    corrupt_path.write_text("{ esto no es json valido ", encoding="utf-8")

    with pytest.raises(Exception) as exc_info:
        config.load(corrupt_path)

    assert corrupt_path.name in str(exc_info.value), (
        "el fallo en alto debe nombrar el fichero que fallo -- "
        f"mensaje real: {exc_info.value!r}"
    )


def test_wrong_type_but_valid_json_fails_loud_and_names_file(config, tmp_path):
    """Guarda de tipo (desviacion declarada por Ultron, verificada en vivo).

    Fallo real que previene: `"customs_enabled": "false"` -- CON
    COMILLAS -- es JSON sintacticamente valido, así que no cae en la
    fila 3 por la vía del parseo. Pero el valor que llega no es el
    booleano `False`, es la cadena de texto `"false"`, y una cadena no
    vacia es verdadera en Python (`bool("false") is True`). Sin esta
    guarda, `load()` devolveria `Config(customs_enabled="false")`, un
    objeto donde el campo declarado `bool` en realidad guarda texto; el
    primer `if config.customs_enabled:` en cualquier consumidor
    encenderia la aduana -- exactamente lo que fila 1 dice que no debe
    pasar sin fichero, ahora colandose CON fichero, porque el contenido
    "parece bueno" (JSON valido) en vez de romperse solo como el
    fichero corrupto de la fila 3.

    Se reusa el mismo criterio de la fila 3: no basta con que lance,
    tiene que nombrar el fichero -- si no, un `ValueError` generico de
    otra parte del codigo haria pasar este test en verde sin haber
    probado la guarda de tipo.
    """
    bad_type_path = tmp_path / "config.json"
    bad_type_path.write_text(
        '{"customs_enabled": "false"}', encoding="utf-8"
    )

    with pytest.raises(Exception) as exc_info:
        config.load(bad_type_path)

    assert bad_type_path.name in str(exc_info.value), (
        "el fallo en alto debe nombrar el fichero que fallo -- "
        f"mensaje real: {exc_info.value!r}"
    )
