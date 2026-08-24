"""Contrato de lib/memory/similar.py -- PIEZAS.md Sec.6.5.

similar.py NO EXISTE TODAVIA (tampoco lib/memory/model.py, del que sale
la clase `Note` que esta pieza recibe y devuelve). Estos cuatro tests
deben fallar al importar, por diseno -- es el RED del modo test-first.
Uno por fila de la tabla "Sus tests" de Sec.6.5, ni uno mas:

  1. Dos notas casi iguales de la misma zona se detectan.
  2. Dos notas distintas de la misma zona NO se detectan.
  3. Una nota igual pero de OTRA zona no se detecta.
  4. Devuelve notas completas, con su porque y sus keys.

El fixture `similar` importa por ruta de fichero
(`import_lib_memory_module`, ver conftest.py) para que cada test falle
individualmente con la causa real (`FileNotFoundError`:
lib/memory/similar.py no existe todavia), en vez de un unico error de
coleccion para todo el fichero -- mismo patron que test_vocabulary.py y
test_emojis.py. Se lista antes que `make_note` en la firma de cada test
para que sea ESE fallo, y no el de `model.py` (tambien inexistente), el
que se reporte primero -- pytest instancia los fixtures independientes
de un test en el orden en que aparecen como parametros.

Esta pieza recibe los datos YA CARGADOS (PIEZAS.md Sec.6.5, "Superficie"):
no lee ficheros ni llama a git. Por eso `make_note` construye objetos
`Note` a mano en vez de tocar un repo -- no hace falta `tmp_repo` aqui.

No se toca produccion: si `lib/memory/similar.py` no existe, estos tests
se quedan en rojo tal cual estan -- eso es lo esperado.
"""

from datetime import datetime, timezone

import pytest

from .conftest import import_lib_memory_module

# El ejemplo del rechazo 1.6 (TEXTOS.md Sec.1.6): D-030, zona
# [product][auth], con sus keys y su Why literales. Se usa como base de
# "nota existente" en los cuatro tests para que la firma no invente datos
# sueltos por test.
_BASE_NOTE_FIELDS = dict(
    type="D",
    id="D-030",
    zone1="product",
    zone2="auth",
    headline="login with JWT + Google OAuth",
    description=(
        "usuarios autentican con email/password o con Google OAuth"
    ),
    timestamp=datetime(2026, 4, 11, tzinfo=timezone.utc),
    why=(
        "sesiones no escalan multi-tenant; Google evita gestionar "
        "passwords propios"
    ),
    keys=("token", "oauth", "sso", "signin"),
)

# Threshold deliberadamente generoso: las notas "casi iguales" de los
# tests 1 y 4 comparten prácticamente todo el texto y las keys (para
# quedar per encima de cualquier formula de similitud razonable), y las
# notas "distintas" del test 2 no comparten ni tema ni una sola key (para
# quedar por debajo). El valor exacto no acopla el test a un algoritmo
# concreto -- solo separa "obviamente igual" de "obviamente distinto".
_THRESHOLD = 0.5


@pytest.fixture
def similar():
    return import_lib_memory_module("similar")


@pytest.fixture
def make_note():
    model = import_lib_memory_module("model")

    def _make(**overrides):
        fields = dict(_BASE_NOTE_FIELDS)
        fields.update(overrides)
        return model.Note(**fields)

    return _make


def test_two_near_identical_notes_of_the_same_zone_are_detected(
    similar, make_note
):
    """Fila 1: dos notas casi iguales de la misma zona se detectan.

    Fallo real que previene: se duplica una decision y conviven dos
    verdades sin que nadie lo note.
    """
    existing_note = make_note()
    candidate = make_note(
        id="D-099",
        headline="login with JWT and Google OAuth",
    )

    result = similar.find_similar(
        candidate, (existing_note,), threshold=_THRESHOLD
    )

    assert existing_note in result


def test_two_distinct_notes_of_the_same_zone_are_not_detected(
    similar, make_note
):
    """Fila 2: dos notas distintas de la misma zona NO se detectan.

    Fallo real que previene: un rechazo que salta siempre acaba
    ignorandose siempre.
    """
    existing_note = make_note()
    candidate = make_note(
        id="D-099",
        headline="add dark mode toggle to the settings screen",
        description="permite alternar tema oscuro/claro desde ajustes",
        why=(
            "usuarios piden reducir la fatiga visual en el uso nocturno "
            "de la app"
        ),
        keys=("darkmode", "theme", "ui", "settings"),
    )

    result = similar.find_similar(
        candidate, (existing_note,), threshold=_THRESHOLD
    )

    assert result == ()


def test_identical_note_of_another_zone_is_not_detected(similar, make_note):
    """Fila 3: una nota igual pero de OTRA zona no se detecta.

    Solo cambia `zone2` (product/auth vs product/billing): si la
    implementacion solo filtrase por `zone1`, este par seguiria
    casando por error y el test lo cazaria.

    Fallo real que previene: ruido en cada alta que ensena al usuario a
    saltarse la pregunta.
    """
    existing_note = make_note(id="D-030", zone1="product", zone2="billing")
    candidate = make_note(id="D-099", zone1="product", zone2="auth")

    result = similar.find_similar(
        candidate, (existing_note,), threshold=_THRESHOLD
    )

    assert result == ()


def test_returns_full_notes_with_why_and_keys(similar, make_note):
    """Fila 4: devuelve notas completas, con su porque y sus keys.

    Fallo real que previene: el rechazo se queda sin lo que tiene que
    imprimir (fecha, keys, porque entero) y hay que ir a buscarlo por
    otra puerta -- exactamente la segunda puerta de lectura que el
    diseno prohibe.
    """
    existing_note = make_note()
    candidate = make_note(
        id="D-099",
        headline="login with JWT and Google OAuth",
    )

    result = similar.find_similar(
        candidate, (existing_note,), threshold=_THRESHOLD
    )

    assert len(result) == 1
    returned = result[0]

    assert not isinstance(returned, str), (
        "find_similar debe devolver notas completas, no identificadores"
    )
    assert returned == existing_note
    assert returned.why == existing_note.why
    assert returned.keys == existing_note.keys
    assert returned.id == existing_note.id
    assert returned.timestamp == existing_note.timestamp


# ---------------------------------------------------------------------------
# Contrato compartido de normalizacion (D-054 + regla nueva del propietario,
# 2026-08-24): todo texto que se compare o se use como clave se normaliza a
# minusculas Y SIN ACENTOS. `similar.py::_tokens()` hoy solo hace
# `.lower()` sobre el texto conjunto. Estos tests anclan el comportamiento
# en el punto de entrada real (`similar.find_similar`) -- nunca en un
# simbolo fisico compartido: la funcion de normalizacion puede vivir en
# cualquier sitio dentro de lib/memory/ (frontera de test_boundary.py, que
# sigue en verde), lo unico que importa es lo que `find_similar` hace con
# el texto.
# ---------------------------------------------------------------------------


def test_two_notes_differing_only_in_accent_and_case_are_detected_as_similar(
    similar, make_note
):
    """Punto 3 del contrato: dos textos que solo difieren en acentos/caja
    cuentan como el mismo token (mas parecidos que antes).

    Disenado para NO casar bajo la tokenizacion actual (solo minuscula):
    las cuatro palabras del vocabulario difieren TODAS por un acento
    ('diseno'/'diseño', 'pagina'/'página', 'boton'/'botón',
    'exportacion'/'exportación'), asi que el Jaccard de hoy es 0/8 = 0.0
    (interseccion vacia), muy por debajo del umbral 0.5 de este fichero.
    Tras normalizar tambien por acentos, las cuatro palabras coinciden
    exactas y el Jaccard sube a 4/4 = 1.0.
    """
    existing_note = make_note(
        id="D-030",
        headline="DISENO PAGINA BOTON EXPORTACION",
        description="",
        why=None,
        keys=(),
    )
    candidate = make_note(
        id="D-099",
        headline="diseño página botón exportación",
        description="",
        why=None,
        keys=(),
    )

    result = similar.find_similar(candidate, (existing_note,), threshold=_THRESHOLD)

    assert existing_note in result, (
        "dos notas con el mismo vocabulario, salvo acentos y caja, no se "
        "detectaron como parecidas"
    )


def test_two_notes_with_different_accented_words_are_not_detected_as_similar(
    similar, make_note
):
    """Punto 3 del contrato -- control negativo: dos textos GENUINAMENTE
    distintos (no solo por acentos) no se vuelven iguales al normalizar
    tambien por acentos. Sobre-normalizar no es gratis.
    """
    existing_note = make_note(
        id="D-030",
        headline="facturación mensual con IVA incluido siempre",
        description="",
        why=None,
        keys=(),
    )
    candidate = make_note(
        id="D-099",
        headline="autenticación con clave temporal de un solo uso",
        description="",
        why=None,
        keys=(),
    )

    result = similar.find_similar(candidate, (existing_note,), threshold=_THRESHOLD)

    assert result == (), (
        "dos notas sin vocabulario compartido real (mas alla de llevar "
        f"acentos cada una en una palabra distinta) se marcaron como "
        f"parecidas: {result!r}"
    )


def test_regression_case_only_difference_still_detected_as_similar(
    similar, make_note
):
    """Punto 4 del contrato -- regresion: dos notas que hoy ya se
    detectan como parecidas solo por diferencia de CAJA (sin acentos de
    por medio) siguen detectandose tras anadir el paso de acentos.
    """
    existing_note = make_note(id="D-030", headline="LOGIN WITH JWT AND GOOGLE OAUTH")
    candidate = make_note(id="D-099", headline="login with jwt and google oauth")

    result = similar.find_similar(candidate, (existing_note,), threshold=_THRESHOLD)

    assert existing_note in result
