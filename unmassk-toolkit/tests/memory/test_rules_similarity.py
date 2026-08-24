"""Contrato compartido de normalizacion (D-054 + regla nueva del
propietario, 2026-08-24) -- `lib/memory/rules_similarity.py::similar_existing()`.

Todo texto que se compare o se use como clave se normaliza a minusculas
Y SIN ACENTOS. `similar_existing()` hoy solo pasa el texto por
`_tokenize()` (`text.lower()`, sin quitar acentos) antes de comparar por
Jaccard -- dos remembers que solo difieren en acentos/caja pierden
solapamiento de vocabulario justo en las palabras que llevan tilde.

Ancla el comportamiento en el PUNTO DE ENTRADA real,
`rules.similar_existing()` -- la fachada que `bin/memory/rule.py` y el
comando `/remember` usan de verdad -- nunca en `rules_similarity.py`
importado a pelo: la funcion fisica de normalizacion compartida puede
vivir en cualquier sitio dentro de `lib/memory/` (frontera vigilada por
`tests/memory/test_boundary.py`, que sigue en verde), lo unico que este
fichero prueba es lo que el punto de entrada hace con el texto.

Mismo patron de siembra que `test_rules.py` (fila 5, ya en verde): un
repo git temporal real (`tmp_repo`), cwd movido dentro con `_cwd()`
(misma razon exacta -- la Superficie de `rules.py` no declara un
parametro de raiz), y `rules.add()` real (nunca un fichero de reglas
escrito a mano) para sembrar la regla existente antes de preguntar por
el parecido -- productor/consumidor real (unmassk-standards SS34).

Los tres tests fallan hoy (RED) o se quedan en verde a proposito segun
el punto del contrato que cubren -- ver el docstring de cada uno.
"""

import os
from contextlib import contextmanager

import pytest

from .conftest import import_lib_memory_module


@pytest.fixture
def rules():
    return import_lib_memory_module("rules")


@contextmanager
def _cwd(path):
    """Cambia el cwd del proceso a `path` durante el bloque, y lo restaura
    siempre -- mismo helper y misma razon que `test_rules.py::_cwd`."""
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def test_near_duplicate_rule_differing_only_in_accent_and_case_is_detected(
    rules, tmp_repo
):
    """Punto 3 del contrato: dos remembers que solo difieren en
    acentos/caja cuentan como el mismo texto (mas parecidos que antes).

    RED hoy: las cuatro palabras con tilde ('diseño'/'diseno',
    'página'/'pagina', 'botón'/'boton', 'exportación'/'exportacion') no
    casan bajo `_tokenize()` actual (solo `.lower()`) -- solo
    'mark_accent'/'de'/'con' coinciden. Jaccard = 3/11 =~ 0.27, por
    debajo de `vocabulary.SIMILARITY_THRESHOLD` (0.5). Tras normalizar
    tambien por acentos, las ocho palabras coinciden todas y Jaccard sube
    a 7/7 = 1.0.
    """
    original = "MARK_ACCENT diseño de página con botón de exportación"
    near_duplicate_accent_and_case_only = (
        "MARK_ACCENT DISENO DE PAGINA CON BOTON DE EXPORTACION"
    )

    with _cwd(tmp_repo):
        add_result = rules.add(original, "user")
        assert add_result.ok, f"add() fallo inesperadamente: {add_result.git_error}"

        hits = rules.similar_existing(near_duplicate_accent_and_case_only)

    assert hits, (
        "una regla casi identica, salvo acentos y caja, no se detecto como "
        "parecida"
    )
    assert ("user", original) in hits, (
        f"similar_existing() no devolvio la pareja (dueno, texto) de la regla "
        f"original: {hits!r}"
    )


def test_genuinely_different_rule_with_accented_words_is_not_detected(
    rules, tmp_repo
):
    """Punto 3 del contrato -- control negativo: dos remembers
    GENUINAMENTE distintos (no solo por acentos) no se vuelven parecidos
    al normalizar tambien por acentos. Se queda en verde antes y despues
    del cambio -- prueba que sobre-normalizar no dispara el detector de
    mas.
    """
    original = "MARK_ACCENT facturación mensual con IVA incluido siempre"
    unrelated = "MARK_ACCENT autenticación con clave temporal de un solo uso"

    with _cwd(tmp_repo):
        add_result = rules.add(original, "user")
        assert add_result.ok, f"add() fallo inesperadamente: {add_result.git_error}"

        hits = rules.similar_existing(unrelated)

    assert not hits, (
        f"dos reglas sin relacion real (mas alla de llevar acentos, cada una "
        f"en una palabra distinta) se marcaron como parecidas: {hits!r}"
    )


def test_regression_case_only_near_duplicate_rule_still_detected(rules, tmp_repo):
    """Punto 4 del contrato -- regresion: un remember casi identico solo
    por diferencia de CAJA (sin acentos de por medio) sigue
    detectandose tras anadir el paso de acentos. Ya funciona hoy
    (`.lower()` cubre la caja); este test se queda en verde antes y
    despues, como red de seguridad.
    """
    original = "MARK_CASE solo fallos reales del dia a dia"
    near_duplicate_case_only = "MARK_CASE SOLO FALLOS REALES DEL DIA A DIA"

    with _cwd(tmp_repo):
        add_result = rules.add(original, "user")
        assert add_result.ok, f"add() fallo inesperadamente: {add_result.git_error}"

        hits = rules.similar_existing(near_duplicate_case_only)

    assert hits
    assert ("user", original) in hits
