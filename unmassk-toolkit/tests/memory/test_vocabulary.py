"""Contrato de lib/memory/vocabulary.py -- PIEZAS.md Sec.6.1.

vocabulary.py NO EXISTE TODAVIA. Estos cuatro tests deben fallar al
importar, por diseno -- es el RED del modo test-first. Uno por fila de
la tabla "Sus tests" de Sec.6.1, ni uno mas:

  1. Todo campo de FIELDS declara un lector, y ese lector existe de
     verdad -- con la regla de los tres estados (reescrita 2026-08-02,
     ver mas abajo).
  2. La pregunta del dolor aparece exactamente una vez en todo el codigo.
  3. Cada uno de los siete tipos declara sus campos obligatorios y
     permitidos.
  4. Los ocho ficheros de indice son ocho, ni uno mas.

El fixture `vocabulary` importa por ruta de fichero
(`import_lib_memory_module`, ver conftest.py) para que cada test falle
individualmente con la causa real (`FileNotFoundError`:
lib/memory/vocabulary.py no existe todavia), en vez de un unico error de
coleccion para todo el fichero -- mismo patron que test_emojis.py.

No se toca produccion: si `lib/memory/vocabulary.py` no existe, estos
tests se quedan en rojo tal cual estan -- eso es lo esperado.

Nombres de `FieldSpec`/`TypeSpec` -- ya NO son una asuncion: PIEZAS.md
Sec.6.1 los fijo literalmente el 2026-08-02 ("Los nombres exactos,
fijados aqui para que nadie los adivine"):

  class FieldSpec: reader: str            # "modulo.funcion"
  class TypeSpec:  description: str
                   required_fields: frozenset[str]
                   allowed_fields: frozenset[str]

REGLA DE LOS TRES ESTADOS (fila 1, reescrita tras el primer intento --
exigir que los OCHO lectores fueran importables de verdad condenaba el
test a rojo permanente durante semanas, porque seis viven en modulos de
capas que aun no existen; un test permanentemente rojo se ignora, y
detras se esconde un fallo real):

  verificado -- el modulo existe Y tiene la funcion       -> verde
  pendiente  -- el modulo aun no se ha escrito             -> verde,
                pero se cuenta y se IMPRIME (el cero se ensena, P6)
  roto       -- el modulo existe y NO tiene la funcion     -> rojo,
                siempre -- este es el caso que mato al v1

La frontera pendiente/roto se decide por `os.path.exists()` del fichero
del modulo, nunca por un `try/except` generico: mezclar "no existe" con
"existe pero le falta la funcion" en el mismo `except` borraria
justo la distincion que da valor al test.
"""

import os

import pytest

from .conftest import LIB_MEMORY_DIR, import_lib_memory_module

# Los siete tipos del vocabulario, tal como los cita PIEZAS.md Sec.6.1 y
# spec-sistema-memoria-v2.md §4: D decision, M memo, R restriction,
# Q question, X discarded, I incident, B blocker.
SEVEN_TYPES = ("D", "M", "R", "Q", "X", "I", "B")

# Los ocho ficheros de indice, citados literalmente en
# spec-sistema-memoria-v2.md §7 ("Contiene exactamente ocho ficheros y
# nada mas"). MEMORY.md y PLANS.md estan citados ahi mismo como
# rechazados expresamente -- son el caso negativo de la fila 4.
EIGHT_INDEX_FILES = frozenset(
    {
        "DECISIONS.md",
        "MEMOS.md",
        "RESTRICTIONS.md",
        "QUESTIONS.md",
        "INCIDENTS.md",
        "DISCARDED.md",
        "BLOCKED.md",
        "ARCHIVED.md",
    }
)

_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(LIB_MEMORY_DIR))


def _iter_py_files(root):
    """Recorre .py bajo `root`, saltando __pycache__ (nunca .git: fuera de root)."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in filenames:
            if filename.endswith(".py"):
                yield os.path.join(dirpath, filename)


@pytest.fixture
def vocabulary():
    return import_lib_memory_module("vocabulary")


def test_every_field_declares_a_reader_that_resolves_by_the_three_state_rule(
    vocabulary,
):
    """Fila 1 (reescrita 2026-08-02): todo campo de FIELDS declara un
    lector, y ese lector existe de verdad -- con la regla de los tres
    estados (verificado / pendiente / roto, ver docstring del fichero).

    Es la fila mas importante de las cuatro: recorre los campos
    declarados y clasifica cada lector. Solo "roto" pone el test en
    rojo; "pendiente" se cuenta y se imprime, nunca falla -- el sistema
    se construye por capas y seis lectores de capas de arriba
    legitimamente no existen todavia.

    La clasificacion mira el disco (`os.path.exists`) antes de intentar
    importar, para que "el modulo no existe" (pendiente) y "el modulo
    existe pero le falta la funcion" (roto) nunca se confundan dentro
    de un mismo except generico -- esa distincion es todo el valor del
    test.

    Fallo real que previene: los 1.002 `Why:` y 605 `Touched:` del v1 --
    campos escritos miles de veces sin que nadie los leyera nunca. Y en
    concreto el que tumbo al v1: un lector inventado en un modulo que
    SI existe, tragado en silencio por los tres parsers.
    """
    assert vocabulary.FIELDS, "FIELDS no puede estar vacio"

    verified = []
    pending = []
    broken = []

    for field_name, field_spec in vocabulary.FIELDS.items():
        reader_path = getattr(field_spec, "reader", None)
        assert reader_path, f"el campo '{field_name}' no declara lector"

        module_name, separator, function_name = reader_path.rpartition(".")
        assert separator and module_name and function_name, (
            f"el campo '{field_name}' declara un lector con forma "
            f"invalida: '{reader_path}' (se esperaba 'modulo.funcion')"
        )

        module_path = os.path.join(LIB_MEMORY_DIR, f"{module_name}.py")

        if not os.path.exists(module_path):
            pending.append((field_name, reader_path))
            continue

        reader_module = import_lib_memory_module(module_name)
        if callable(getattr(reader_module, function_name, None)):
            verified.append((field_name, reader_path))
        else:
            broken.append((field_name, reader_path))

    print(
        f"\n[FIELDS lectores] verificados={len(verified)} "
        f"pendientes={len(pending)} rotos={len(broken)}"
    )
    if pending:
        print(
            "  pendientes: "
            + ", ".join(f"{field}->{reader}" for field, reader in pending)
        )

    assert not broken, (
        "lector ROTO -- el modulo existe pero la funcion declarada no: "
        + ", ".join(f"{field}: {reader}" for field, reader in broken)
    )


def test_pain_question_appears_exactly_once_in_the_codebase(vocabulary):
    """Fila 2: la pregunta del dolor aparece exactamente una vez en todo
    el codigo.

    Fallo real que previene: dos copias que se separan, y la aduana
    pregunta una cosa mientras la skill ensena otra.
    """
    question = vocabulary.PAIN_QUESTION
    assert question, "PAIN_QUESTION no puede estar vacia"

    occurrences = []
    for path in _iter_py_files(_TOOLKIT_ROOT):
        with open(path, encoding="utf-8") as source_file:
            count = source_file.read().count(question)
        occurrences.extend([path] * count)

    assert occurrences == [os.path.join(LIB_MEMORY_DIR, "vocabulary.py")], (
        "la pregunta del dolor debe vivir en una sola copia, dentro de "
        f"lib/memory/vocabulary.py; se encontro en: {occurrences}"
    )


def test_each_of_the_seven_types_declares_required_and_allowed_fields(
    vocabulary,
):
    """Fila 3: cada uno de los siete tipos declara sus campos
    obligatorios y permitidos.

    Fallo real que previene: un tipo nuevo que entra sin decir que
    necesita, y el validador lo deja pasar vacio.
    """
    assert set(vocabulary.TYPES.keys()) == set(SEVEN_TYPES)

    for type_letter in SEVEN_TYPES:
        type_spec = vocabulary.TYPES[type_letter]
        required = getattr(type_spec, "required_fields", None)
        allowed = getattr(type_spec, "allowed_fields", None)

        assert required is not None, (
            f"el tipo '{type_letter}' no declara required_fields"
        )
        assert allowed is not None, (
            f"el tipo '{type_letter}' no declara allowed_fields"
        )
        assert set(required) <= set(allowed), (
            f"el tipo '{type_letter}' obliga un campo que no permite: "
            f"{set(required) - set(allowed)}"
        )
        # model.py (PIEZAS.md Sec.5.3): "description: str  # obligatorio
        # en los siete tipos".
        assert "description" in required, (
            f"el tipo '{type_letter}' no obliga 'description'"
        )

    # spec-sistema-memoria-v2.md §4: "D | decision | ... con su Why
    # obligatorio" -- el unico tipo que lo exige.
    assert "why" in vocabulary.TYPES["D"].required_fields
    for type_letter in SEVEN_TYPES:
        if type_letter == "D":
            continue
        assert "why" not in vocabulary.TYPES[type_letter].required_fields, (
            f"'why' solo es obligatorio en D, no en '{type_letter}'"
        )


def test_index_files_are_exactly_eight(vocabulary):
    """Fila 4: los ocho ficheros de indice son ocho, ni uno mas.

    Fallo real que previene: alguien anade `PLANS.md`, que la
    especificacion prohibe expresamente (spec-sistema-memoria-v2.md §7:
    "Indice general MEMORY.md / indice de planes PLANS.md -> rechazados").
    """
    assert len(vocabulary.INDEX_FILES) == 8
    assert set(vocabulary.INDEX_FILES) == EIGHT_INDEX_FILES
    assert "PLANS.md" not in vocabulary.INDEX_FILES
    assert "MEMORY.md" not in vocabulary.INDEX_FILES
