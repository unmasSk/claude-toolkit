"""Contrato de lib/memory/clusters.py -- PIEZAS.md Sec.9.1.

clusters.py NO EXISTE TODAVIA. Estos cuatro tests deben fallar al
importar, por diseno -- es el RED del modo test-first. Uno por fila de
la tabla "Sus tests" de Sec.9.1, ni uno mas:

  1. Una cadena de tres notas encadenadas se pliega en un racimo.
  2. Una nota huerfana da un racimo de una, sin excepcion y sin aviso
     de error.
  3. Con dos notas encadenadas, el titulo es el de la nueva.
  4. Mismo conjunto de notas -> mismos racimos, siempre.

El fixture `clusters` se pide PRIMERO en cada firma (mismo patron que
test_query.py/test_zones.py/test_format.py/test_similar.py): pytest
instancia los fixtures en el orden en que aparecen, asi que si
`clusters.py` no existe el fallo se reporta ahi -- nunca por
`model.py`, que ya existe y esta en verde.

clusters.py es puro (PIEZAS Sec.9.1, "Que NO hace": "No lee nada. No
ordena para presentar. No decide que esta archivado -- se lo dan"). No
hace falta `tmp_repo` ni git de ningun tipo: la superficie completa es
`group(notes: tuple[Note, ...], archived_ids: frozenset[str]) ->
tuple[Cluster, ...]`, y los cuatro tests la llaman directamente sobre
notas construidas en memoria con la factoria `_note` de abajo (mismo
patron que test_query.py::_note/test_format.py::_note).

LA REGLA, citada en Sec.9.1 y en spec Sec.8: se agrupa por PUNTEROS
(`Origin`, `Replaces`), nunca por parecido ni por keys. Un puntero que
apunta a algo ausente del conjunto no es un error -- deja a la nota
huerfana en un racimo de una, "y eso es la senal, no un fallo".

**Por que las aserciones leen atributos (`.id`, tuplas/frozensets de
ids) en vez de comparar objetos `Note`/`Cluster` completos con `==`:**
mismo hallazgo que zones-contract-notes.md/format-contract-notes.md/
query-contract-notes.md -- el `model` que este fichero carga via
`import_lib_memory_module` y el `model` que `clusters.py` importa por
dentro (`from model import Note, Cluster`, convencion plana de PIEZAS
Sec.3.3bis) pueden acabar siendo clases Python DISTINTAS aunque el
codigo fuente sea identico. Comparar `cluster.root == nota_esperada`
arriesgaria un falso rojo por identidad de clase, no por logica. Leer
`.id` (un `str`, sin ese problema) evita la trampa sin necesidad de un
`_assert_fields_match` como el de test_query.py, porque ningun test de
aqui construye un `Cluster`/`Note` "esperado" para comparar objeto a
objeto -- solo inspecciona lo que `clusters.group()` devolvio.

**Supuestos declarados, sin fuente literal en Sec.9.1 (mismo tipo de
hueco que en format-contract-notes.md/similar-contract-notes.md):**

1. **Fila 1 ("una cadena de tres notas encadenadas") se interpreta como
   una cadena de punteros `Origin` transitiva** (A <- B via
   `B.origin=(A.id,)` <- C via `C.origin=(B.id,)`), NO como una cadena
   de `Replaces`. Se elige `Origin` porque el "fallo real que previene"
   de esta fila ("la misma decision apareciendo tres veces como si
   fueran tres decisiones distintas") describe un problema de PLEGADO
   -- que el agrupado no colapse una cadena transitiva en un solo
   racimo -- mientras que la fila 3 ya aisla en exclusiva el mecanismo
   de `Replaces` (con el minimo de dos notas necesario para probarlo).
   Si el racimo de tres tambien debia construirse con `Replaces`, esta
   fila queda redundante con la 3 salvo por el conteo; ver PREGUNTA en
   el informe.
2. **`archived_ids` se pasa como segundo argumento posicional**, tal
   cual la firma declarada en Sec.9.1
   (`group(notes: tuple[Note, ...], archived_ids: frozenset[str])`) --
   ningun test depende del nombre exacto del kwarg.
3. **Ningun test inspecciona `Cluster.archived_ids` en la salida.**
   Sec.9.1 no dice si ese campo se propaga tal cual o se filtra por
   racimo, y ninguna de las cuatro filas de la tabla lo pide -- inventar
   esa asercion seria fabricar contrato no escrito. Fila 3 pasa un
   `archived_ids` no vacio solo porque la nota vieja de ese caso SI esta
   archivada en la realidad (fue sustituida), no porque el test lo
   verifique.
4. **El campo `type` de las notas de prueba es `"D"` (decision) por
   defecto**, sin que ningun test lo verifique: Sec.9.1 dice que el
   agrupado es "por punteros... nunca por parecido ni por keys", nada
   sugiere que dependa del campo `type`.

No se toca produccion: si `lib/memory/clusters.py` no existe, estos
tests se quedan en rojo tal cual estan -- eso es lo esperado. No se
toca ningun fichero de un companero (`conftest.py`, `model.py`, etc.).
"""

from datetime import datetime, timezone

import pytest

from .conftest import import_lib_memory_module


@pytest.fixture
def clusters():
    return import_lib_memory_module("clusters")


@pytest.fixture
def model():
    return import_lib_memory_module("model")


def _note(model, **overrides):
    """Factoria de Note con valores por defecto neutros -- cada test
    override solo los campos que le importan. Mismo patron que
    test_query.py::_note/test_format.py::_note.
    """
    fields = dict(
        type="D",
        id="D-000",
        zone1="testing",
        zone2="clusters",
        headline="seeded note for clusters.py contract",
        description="placeholder description for the clusters.py grouping contract.",
        timestamp=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        why=None,
        keys=(),
        origin=(),
        replaces=None,
        awaits=None,
        issue=None,
    )
    fields.update(overrides)
    return model.Note(**fields)


def test_three_note_chain_folds_into_a_single_cluster(clusters, model):
    """Fila 1: una cadena de tres notas encadenadas se pliega en un
    racimo.

    Fallo real que previene: la misma decision apareciendo tres veces
    como si fueran tres decisiones distintas.
    """
    root_note = _note(model, id="D-500", headline="root decision of the chain")
    mid_note = _note(
        model,
        id="D-501",
        origin=("D-500",),
        headline="mid note, hangs off the root via Origin",
    )
    leaf_note = _note(
        model,
        id="D-502",
        origin=("D-501",),
        headline="leaf note, hangs off the mid note via Origin",
    )

    result = clusters.group((root_note, mid_note, leaf_note), frozenset())

    assert len(result) == 1, (
        "una cadena de tres notas encadenadas debe plegarse en un solo "
        f"racimo, se obtuvieron {len(result)}"
    )
    cluster = result[0]
    assert cluster.root.id == root_note.id, (
        f"el racimo de la cadena debe tener a {root_note.id!r} como raiz, "
        f"tiene a {cluster.root.id!r}"
    )
    child_ids = {child.id for child in cluster.children}
    assert child_ids == {mid_note.id, leaf_note.id}, (
        "el racimo debe incluir las tres notas encadenadas "
        f"({mid_note.id!r} y {leaf_note.id!r} como hijos), se obtuvo "
        f"{child_ids!r}"
    )


def test_orphan_pointer_yields_a_cluster_of_one_without_raising(clusters, model):
    """Fila 2: una nota huerfana da un racimo de una, sin excepcion y
    sin aviso de error.

    Fallo real que previene: que un puntero roto tumbe el informe
    entero en vez de enseñarse.
    """
    orphan_note = _note(
        model,
        id="D-600",
        origin=("D-999-does-not-exist",),
        headline="decision whose Origin points at a note absent from the set",
    )

    result = clusters.group((orphan_note,), frozenset())

    assert len(result) == 1, (
        "un puntero roto debe producir un racimo de una nota, se "
        f"obtuvieron {len(result)} racimos"
    )
    assert result[0].root.id == orphan_note.id, (
        "la nota huerfana debe ser la raiz de su propio racimo, la raiz "
        f"es {result[0].root.id!r}"
    )
    assert result[0].children == (), (
        "la nota huerfana no debe tener hijos inventados, tiene "
        f"{result[0].children!r}"
    )


def test_two_chained_notes_title_is_the_newer_one(clusters, model):
    """Fila 3: con dos notas encadenadas, el titulo es el de la nueva.

    Fallo real que previene: leer como vigente algo que ya se sustituyo.
    """
    old_note = _note(model, id="D-700", headline="old decision, later superseded")
    new_note = _note(
        model,
        id="D-701",
        replaces="D-700",
        headline="new decision that supersedes the old one",
    )

    result = clusters.group((old_note, new_note), frozenset({old_note.id}))

    assert len(result) == 1, (
        "dos notas encadenadas por Replaces deben plegarse en un solo "
        f"racimo, se obtuvieron {len(result)}"
    )
    assert result[0].root.id == new_note.id, (
        f"el titulo del racimo debe ser la nota nueva ({new_note.id!r}), "
        f"salio {result[0].root.id!r}"
    )
    child_ids = {child.id for child in result[0].children}
    assert child_ids == {old_note.id}, (
        f"la nota vieja debe quedar como hija del racimo, hijos: {child_ids!r}"
    )


def test_same_note_set_yields_the_same_clusters_regardless_of_input_order(
    clusters, model
):
    """Fila 4: mismo conjunto de notas -> mismos racimos, siempre.

    Fallo real que previene: un agrupado que cambia entre dos
    ejecuciones y no se puede auditar.

    Se llama a `clusters.group()` dos veces sobre el MISMO conjunto de
    notas, una con el orden de entrada tal cual y otra invertido -- un
    "conjunto" no tiene orden por definicion, asi que si el resultado
    depende de en que orden llegaron las notas, el agrupado no es
    auditable. Las dos llamadas son dos computos independientes
    (nunca una comparada consigo misma): se compara la salida de la
    invocacion A contra la salida, por separado, de la invocacion B.
    """
    root_note = _note(model, id="D-800", headline="root decision for the determinism check")
    child_a = _note(
        model,
        id="D-801",
        origin=("D-800",),
        headline="first child hanging off the root",
    )
    child_b = _note(
        model,
        id="D-802",
        replaces="D-801",
        headline="second child, replaces the first",
    )

    notes = (root_note, child_a, child_b)
    archived = frozenset({child_a.id})

    result_in_order = clusters.group(notes, archived)
    result_reversed = clusters.group(tuple(reversed(notes)), archived)

    def _snapshot(clusters_tuple):
        return tuple(
            (
                cluster.root.id,
                tuple(child.id for child in cluster.children),
            )
            for cluster in clusters_tuple
        )

    snapshot_in_order = _snapshot(result_in_order)
    snapshot_reversed = _snapshot(result_reversed)

    assert snapshot_in_order == snapshot_reversed, (
        "el mismo conjunto de notas produjo racimos distintos segun el "
        f"orden de entrada: {snapshot_in_order!r} != {snapshot_reversed!r}"
    )
