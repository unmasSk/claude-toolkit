"""Contrato en ROJO -- puerta NUEVA: mismas claves + misma zona -> rechaza
pidiendo `--replaces`, aunque los titulares no se parezcan.

EL HUECO, confirmado leyendo el codigo real (no supuesto), no ejecutando
antes de leer: `lib/memory/similar.py::_tokens`/`_jaccard` YA mete
titular + description + why + keys en UN SOLO numero Jaccard
(`similar.py`, funcion `_tokens`, ~linea 47-62), y la zona YA es un
pre-filtro duro (`find_similar`, ~linea 97-99: `if note.zone1 !=
candidate.zone1 or note.zone2 != candidate.zone2: continue`). Asi que lo
que falta NO es "anadir claves/zona a la comparacion" -- ya estan. Falta
una puerta DISTINTA, de coincidencia EXACTA: cuando dos notas comparten
el mismo conjunto de claves en la misma pareja de zonas, el titular
distinto diluye el Jaccard por debajo del umbral
(`vocabulary.SIMILARITY_THRESHOLD` = 0.5, verificado en
`vocabulary.py`) y `validate_replacement()` (`validator.py:372-427`) dice
que la nota es valida cuando en realidad pisa a otra que ya existe --
mismo asunto, dos entradas independientes en el indice, sin que
`--replaces` intervenga nunca. Verificado en vivo antes de escribir esto
(ver el bloque de calculo mas abajo, en el docstring de
`TestSameKeysSameZoneDistinctHeadlinesBounces`): el Jaccard real de la
pareja de textos que usa ese test es 0.227, por debajo del umbral.

DONDE ENTRA: `bin/memory/note.py::_build_context()` (linea 110-161) ya
filtra `existing_in_zone` contra `indexes.archived_ids(pm)` -- SOLO
notas vivas llegan a `Context.existing_in_zone`, y por tanto solo notas
vivas pueden entrar en cualquier comparacion nueva que se anada aqui, el
mismo invariante que ya fija
`note-archived-similarity-bypass-contract-notes` (no se rompe en este
fichero -- ver `TestArchivedNoteWithSameKeysDoesNotBlockANewSimilarNote`
mas abajo, que reusa el mismo patron: cerrar via `gitmem remove` antes
de la segunda alta).

SEGUNDO PUNTO DE LLAMADA: `bin/memory/remove.py::_build_fence_context()`
(linea 76-93) alimenta el MISMO `validator.Context` para el muro que
nace de `--restriction new`, y ese muro pasa por `validator.validate_note()`
en `_guard_restriction_new()` (linea 128-160) -- la misma funcion pura
que agrega `validate_replacement()`. Verificado leyendo
`_build_fence_candidate()` (linea 100-112): la `Note` del muro NUNCA
lleva `keys` -- no existe un flag `--keys` en `remove.py::_parse_args()`
(confirmado con `grep -n keys bin/memory/remove.py`, cero lineas). Por
tanto la puerta nueva no puede activarse HOY por ese segundo camino con
un positivo real (no hay forma de darle al muro un conjunto de claves no
vacio) -- lo que SI se puede fijar por ahi es el invariante contrario:
dos muros con claves vacias en la MISMA zona, con textos distintos, NO
tienen que bloquearse por "mismo conjunto de claves" (el conjunto vacio
no cuenta como coincidencia) -- ver
`TestFenceCandidatesWithNoKeysNeverCollideOnTheNewGate`. Esto es una
limitacion real de `remove.py`, reportada aqui, no arreglada -- arreglar
es trabajo de Ultron.

QUE SE FIJA, en ocho tests (siete RED, uno control aparte etiquetado
GREEN explicitamente en su propio docstring):

1. Titulares distintos + mismas claves (mismo orden) + misma zona -> la
   segunda nota se rechaza citando la primera y pidiendo `--replaces`.
2. Lo mismo, pero las claves en ORDEN DISTINTO -- la puerta compara un
   CONJUNTO, no una secuencia ["mismo conjunto de claves", correccion
   literal del encargo].
3. Control: misma zona, claves DISTINTAS -> no bloquea (la puerta es
   sobre claves, no solo sobre zona).
4. Control: mismas claves, zona DISTINTA -> no bloquea (la puerta exige
   las dos cosas a la vez).
5. La nota vieja esta ARCHIVADA (cerrada via `gitmem remove`) -> la
   nueva con las mismas claves entra limpia -- el invariante de
   `note-archived-similarity-bypass-contract-notes` se respeta tambien
   para esta puerta nueva.
6. Control GREEN, explicito: dos notas SIN claves (`keys=()`) en la
   misma zona no pueden bloquearse entre si por "mismo conjunto de
   claves" -- el conjunto vacio nunca cuenta como coincidencia. Sin este
   guarda, una implementacion ingenua rompe cualquier zona en la que la
   gente no use `--keys` (el caso mas comun).
7. Mismo invariante que 6, pero por el SEGUNDO camino de llamada
   (`remove.py --restriction new`): dos muros con claves vacias en la
   misma zona, textos distintos, tienen que nacer los dos sin rebote.
8. BREAK 2 de Moriarty, RED nuevo: la pareja de zonas se compara HOY
   POSICIONALMENTE, no como conjunto -- confirmado leyendo el codigo
   (no supuesto) en `similar.py::find_similar` (`if note.zone1 !=
   candidate.zone1 or note.zone2 != candidate.zone2: continue`, ~linea
   98) y `similar.py::_find_exact_key_match` (mismo patron, ~lineas
   133-135). Dos notas con las MISMAS claves y la MISMA pareja de zonas
   escrita AL REVES (`--zones gamma delta` vs `--zones delta gamma`)
   hoy entran las dos limpias -- reproducido en vivo antes de escribir
   este test (`bin/gitmem note M --zones gamma delta ... --zones delta
   gamma ...`, las dos con `rc==0`). El propietario decidio que la
   pareja de zonas se trata como CONJUNTO para esta puerta -- mismo
   principio que la fila 2 ya fijo para las claves, aplicado ahora a las
   zonas. No toca cómo se guardan/resuelven las zonas en ningun otro
   sitio del sistema -- solo la comparacion de esta puerta de
   duplicados. Ver `TestSameKeysZonesSwappedStillBounces`.

Ejecutado via `bin/gitmem` (la fachada, PIEZAS.md Sec.10 fila
`bin/gitmem`: "despacha sin logica propia") contra un `tmp_repo`
temporal -- nunca importando `note.py`/`remove.py`/`validator.py` en
proceso, y nunca el repositorio real (`conftest.py::
_guard_against_writing_to_the_real_repo` lo impediria de todas formas).

Cada test lee el resultado de fuentes escritas por separado: la salida
real de `gitmem` (¿rebota o no?, ¿nombra la candidata real?) contra los
indices REALES leidos con el lector real (`indexes.read`), nunca un
texto de rechazo tecleado a mano ni un id inventado.
"""

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_gitmem_script,
    seed_zones_json,
)

import pytest


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


# Pareja de textos con MUY bajo solapamiento de vocabulario a proposito --
# calculado en vivo antes de escribir este fichero replicando
# `similar.py::_tokens`/`_jaccard` (headline+description+keys,
# `textnorm.normalize_text`, interseccion/union): Jaccard = 0.227,
# claramente por DEBAJO de `vocabulary.SIMILARITY_THRESHOLD` (0.5). Esto
# demuestra que el detector de parecido HOY (`similar.find_similar`) NO
# es lo que tiene que atrapar esta pareja -- si lo atrapara, esta puerta
# nueva no aportaria nada distinto y el test no probaria lo que dice
# probar.
_OLD_HEADLINE = "checkout retries a payment three times before failing silently"
_OLD_DESCRIPTION = (
    "the retry loop swallows the underlying gateway error and never "
    "surfaces it to the user"
)
_NEW_HEADLINE = (
    "support cannot tell why a customer's payment attempt disappeared "
    "without a trace"
)
_NEW_DESCRIPTION = (
    "the order never completes even though the bank statement shows the "
    "charge succeeded"
)
_SHARED_KEYS = ("idempotency-key", "gateway-timeout", "retry-loop")

# Segunda pareja de textos, para el control "claves distintas" -- tambien
# de bajo solapamiento con la primera, y con su PROPIO conjunto de claves
# que no comparte ni una palabra con `_SHARED_KEYS`.
_OTHER_HEADLINE = "the pdf invoice generator drops line items over fifty entries"
_OTHER_DESCRIPTION = (
    "large orders render an invoice missing several rows, and finance "
    "notices only after the customer complains"
)
_OTHER_KEYS = ("pdf-render", "invoice-overflow", "line-items")

# Claves para la fila 8 (BREAK 2 de Moriarty, zonas al reves) -- las que
# el encargo pide literalmente. Jaccard verificado en vivo con estas
# claves y el mismo par de titulares OLD/NEW de arriba: 0.1395,
# claramente por debajo de `vocabulary.SIMILARITY_THRESHOLD` (0.5) --
# el detector de parecido de siempre (`similar.find_similar`) no es lo
# que tiene que atrapar esta pareja tampoco aqui.
_ZONE_ORDER_KEYS = ("ansible", "terraform")


def _write_note(repo, note_type, zone1, zone2, headline, description, *, keys=(), stops=None, replaces=None):
    args = ["note", note_type, "--zones", zone1, zone2, headline, "--description", description]
    if keys:
        args += ["--keys", *keys]
    if stops is not None:
        args += ["--stops", stops]
    if replaces is not None:
        args += ["--replaces", replaces]
    return run_gitmem_script(args, cwd=repo)


class TestSameKeysSameZoneDistinctHeadlinesBounces:
    """Fila 1 del contrato -- el caso central. Dos M, titulares y
    descripciones sin apenas solapamiento (Jaccard 0.227, verificado
    arriba en el docstring del modulo), mismas tres claves en el mismo
    orden, misma pareja de zonas. La segunda tiene que rebotar citando
    la primera y pidiendo `--replaces`."""

    def test_second_note_with_same_keys_and_zone_is_rejected_asking_for_replaces(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "payments"])

        rc_old, out_old, err_old = _write_note(
            tmp_repo, "M", "product", "payments",
            _OLD_HEADLINE, _OLD_DESCRIPTION, keys=_SHARED_KEYS, stops="no",
        )
        assert rc_old == 0, f"stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)

        rc_new, out_new, err_new = _write_note(
            tmp_repo, "M", "product", "payments",
            _NEW_HEADLINE, _NEW_DESCRIPTION, keys=_SHARED_KEYS, stops="no",
        )
        assert rc_new != 0, (
            "mismas claves + misma zona tiene que rebotar aunque los "
            f"titulares no se parezcan: stdout={out_new!r} stderr={err_new!r}"
        )
        combined = out_new + err_new
        assert "Traceback" not in combined
        assert old_id in combined, (
            f"el rechazo tiene que nombrar la candidata real ({old_id}): {combined!r}"
        )
        assert "--replaces" in combined, (
            f"el rechazo tiene que pedir --replaces como salida: {combined!r}"
        )

        pm = pm_path(tmp_repo)
        live_ids = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert live_ids == {old_id}, (
            f"la nota rechazada no puede haber entrado en el indice: {sorted(live_ids)!r}"
        )


class TestSameKeysDifferentOrderStillBounces:
    """Fila 2 -- la puerta compara un CONJUNTO de claves, no una
    secuencia ["mismo conjunto de claves", correccion literal del
    encargo]. Mismas tres claves que la fila 1, pero la segunda nota las
    da en un orden distinto."""

    def test_same_keys_shuffled_order_still_triggers_the_gate(self, tmp_repo, indexes):
        seed_zones_json(tmp_repo, ["product", "payments"])

        rc_old, out_old, err_old = _write_note(
            tmp_repo, "M", "product", "payments",
            _OLD_HEADLINE, _OLD_DESCRIPTION, keys=_SHARED_KEYS, stops="no",
        )
        assert rc_old == 0, f"stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)

        shuffled_keys = tuple(reversed(_SHARED_KEYS))
        assert shuffled_keys != _SHARED_KEYS, "precondicion: el orden tiene que ser de verdad distinto"

        rc_new, out_new, err_new = _write_note(
            tmp_repo, "M", "product", "payments",
            _NEW_HEADLINE, _NEW_DESCRIPTION, keys=shuffled_keys, stops="no",
        )
        assert rc_new != 0, (
            "el mismo CONJUNTO de claves en otro orden tiene que rebotar igual: "
            f"stdout={out_new!r} stderr={err_new!r}"
        )
        combined = out_new + err_new
        assert old_id in combined, f"tiene que nombrar la candidata real: {combined!r}"

        pm = pm_path(tmp_repo)
        live_ids = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert live_ids == {old_id}


class TestSameKeysZonesSwappedStillBounces:
    """Fila 8 -- BREAK 2 de Moriarty. Misma logica que la fila 2, pero
    sobre la PAREJA DE ZONAS en vez de sobre las claves: dos notas con
    el mismo conjunto de claves (mismo orden esta vez, para aislar la
    variable que se prueba aqui) escriben la misma pareja de zonas en
    orden CONTRARIO (`--zones gamma delta` la vieja, `--zones delta
    gamma` la nueva). La puerta tiene que tratar la pareja como
    CONJUNTO -- sin orden -- y rebotar igual que si las zonas hubieran
    llegado en el mismo orden.

    HOY no rebota: `similar.py::find_similar` (~linea 98) y
    `similar.py::_find_exact_key_match` (~lineas 133-135) comparan
    `note.zone1 != candidate.zone1 or note.zone2 != candidate.zone2`
    posicionalmente -- `zone1`/`zone2` intercambiados hace que las dos
    comparaciones den `True` (distintas) aunque la pareja sea la misma.
    Reproducido en vivo antes de escribir este test contra `bin/gitmem`
    real: las dos notas quedan con `rc==0`, dos ids vigentes en el
    indice -- el mismo hueco que fija esta fila, no una suposicion."""

    def test_same_keys_with_the_zone_pair_written_in_reverse_order_still_bounces(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["gamma", "delta"])

        rc_old, out_old, err_old = _write_note(
            tmp_repo, "M", "gamma", "delta",
            _OLD_HEADLINE, _OLD_DESCRIPTION, keys=_ZONE_ORDER_KEYS, stops="no",
        )
        assert rc_old == 0, f"stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)

        rc_new, out_new, err_new = _write_note(
            tmp_repo, "M", "delta", "gamma",
            _NEW_HEADLINE, _NEW_DESCRIPTION, keys=_ZONE_ORDER_KEYS, stops="no",
        )
        assert rc_new != 0, (
            "la misma pareja de zonas escrita al reves tiene que rebotar "
            f"igual que en el mismo orden: stdout={out_new!r} stderr={err_new!r}"
        )
        combined = out_new + err_new
        assert "Traceback" not in combined
        assert old_id in combined, (
            f"el rechazo tiene que nombrar la candidata real ({old_id}): {combined!r}"
        )
        assert "--replaces" in combined, (
            f"el rechazo tiene que pedir --replaces como salida: {combined!r}"
        )

        pm = pm_path(tmp_repo)
        live_ids = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert live_ids == {old_id}, (
            f"la nota rechazada no puede haber entrado en el indice: {sorted(live_ids)!r}"
        )


class TestDifferentKeysSameZoneDoesNotBounce:
    """Fila 3, control -- misma zona, pero claves que no comparten ni una
    palabra: la puerta es sobre las claves, no solo sobre la zona. Tiene
    que entrar limpia."""

    def test_distinct_keys_in_the_same_zone_pair_does_not_trigger_the_gate(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "payments"])

        rc_old, out_old, err_old = _write_note(
            tmp_repo, "M", "product", "payments",
            _OLD_HEADLINE, _OLD_DESCRIPTION, keys=_SHARED_KEYS, stops="no",
        )
        assert rc_old == 0, f"stdout={out_old!r} stderr={err_old!r}"

        rc_new, out_new, err_new = _write_note(
            tmp_repo, "M", "product", "payments",
            _OTHER_HEADLINE, _OTHER_DESCRIPTION, keys=_OTHER_KEYS, stops="no",
        )
        assert rc_new == 0, (
            "claves distintas en la misma zona no tienen que rebotar por la "
            f"puerta nueva: stdout={out_new!r} stderr={err_new!r}"
        )

        pm = pm_path(tmp_repo)
        live_ids = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert len(live_ids) == 2, f"las dos notas tienen que quedar vigentes: {sorted(live_ids)!r}"


class TestSameKeysDifferentZoneDoesNotBounce:
    """Fila 4, control -- mismas claves, pero `zone2` distinto (misma
    tecnica que la fila 3 de `similar-contract-notes`: variar SOLO
    `zone2`, mantener `zone1` igual, para atrapar una implementacion que
    solo mirara `zone1`). Tiene que entrar limpia -- la puerta exige
    mismas claves Y misma pareja de zonas a la vez, no una sola cosa."""

    def test_same_keys_in_a_different_zone_pair_does_not_trigger_the_gate(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "payments", "invoicing"])

        rc_old, out_old, err_old = _write_note(
            tmp_repo, "M", "product", "payments",
            _OLD_HEADLINE, _OLD_DESCRIPTION, keys=_SHARED_KEYS, stops="no",
        )
        assert rc_old == 0, f"stdout={out_old!r} stderr={err_old!r}"

        rc_new, out_new, err_new = _write_note(
            tmp_repo, "M", "product", "invoicing",
            _NEW_HEADLINE, _NEW_DESCRIPTION, keys=_SHARED_KEYS, stops="no",
        )
        assert rc_new == 0, (
            "las mismas claves en OTRA pareja de zonas no tienen que rebotar: "
            f"stdout={out_new!r} stderr={err_new!r}"
        )

        pm = pm_path(tmp_repo)
        live_ids = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert len(live_ids) == 2, f"las dos notas tienen que quedar vigentes: {sorted(live_ids)!r}"


class TestArchivedNoteWithSameKeysDoesNotBlockANewSimilarNote:
    """Fila 5 -- el invariante de
    `note-archived-similarity-bypass-contract-notes` tiene que valer
    tambien para esta puerta nueva: una nota CERRADA no puede bloquear el
    alta de otra con las mismas claves en la misma zona. Mismo mecanismo
    (`gitmem remove` antes de la segunda alta), aplicado a la puerta de
    claves en vez de a la de Jaccard."""

    def test_closing_the_old_note_first_lets_the_new_one_in_despite_same_keys(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "payments"])

        rc_old, out_old, err_old = _write_note(
            tmp_repo, "M", "product", "payments",
            _OLD_HEADLINE, _OLD_DESCRIPTION, keys=_SHARED_KEYS, stops="no",
        )
        assert rc_old == 0, f"stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)

        rc_close, out_close, err_close = run_gitmem_script(
            ["remove", old_id, "fixed by making the gateway call idempotent"],
            cwd=tmp_repo,
        )
        assert rc_close == 0, f"stdout={out_close!r} stderr={err_close!r}"

        pm = pm_path(tmp_repo)
        archived_before = indexes.read_archive(pm)
        assert any(line.id == old_id for line in archived_before), (
            f"precondicion: {old_id} tiene que estar ya archivada: {archived_before!r}"
        )

        rc_new, out_new, err_new = _write_note(
            tmp_repo, "M", "product", "payments",
            _NEW_HEADLINE, _NEW_DESCRIPTION, keys=_SHARED_KEYS, stops="no",
        )
        assert rc_new == 0, (
            "una nota ARCHIVADA no puede bloquear el alta de otra con las "
            f"mismas claves: stdout={out_new!r} stderr={err_new!r}"
        )
        new_id = extract_note_id(out_new)

        live_ids = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert live_ids == {new_id}, f"solo la nueva tiene que quedar vigente: {sorted(live_ids)!r}"


class TestEmptyKeysNeverTriggersTheExactMatchGate:
    """Fila 6 -- CONTROL, GREEN hoy y tiene que seguir siendolo despues
    del arreglo. Dos notas SIN claves (`keys=()`, el caso mas comun --
    nadie pone `--keys` la mayoria de las veces) en la misma zona,
    titulares y descripciones distintos: no pueden rebotar por "mismo
    conjunto de claves". El conjunto vacio no es una coincidencia, es
    ausencia de dato -- mismo principio que ya fija
    `similar.py::_jaccard` para el vocabulario vacio (devuelve 0.0, nunca
    "identico"). Sin esta guarda, una implementacion ingenua de la puerta
    nueva (comparar `note.keys == existing.keys` sin mirar si esta
    vacio) rompe el alta de la SEGUNDA nota en cualquier zona donde nadie
    use `--keys` -- el caso de uso mas comun del sistema, no un borde
    raro."""

    def test_two_keyless_notes_in_the_same_zone_do_not_collide_on_the_new_gate(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "payments"])

        rc_old, out_old, err_old = _write_note(
            tmp_repo, "M", "product", "payments",
            _OLD_HEADLINE, _OLD_DESCRIPTION, keys=(), stops="no",
        )
        assert rc_old == 0, f"stdout={out_old!r} stderr={err_old!r}"

        rc_new, out_new, err_new = _write_note(
            tmp_repo, "M", "product", "payments",
            _NEW_HEADLINE, _NEW_DESCRIPTION, keys=(), stops="no",
        )
        assert rc_new == 0, (
            "dos notas sin claves no pueden rebotar entre si por 'mismo "
            f"conjunto de claves' vacio: stdout={out_new!r} stderr={err_new!r}"
        )

        pm = pm_path(tmp_repo)
        live_ids = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert len(live_ids) == 2, f"las dos notas tienen que quedar vigentes: {sorted(live_ids)!r}"


class TestFenceCandidatesWithNoKeysNeverCollideOnTheNewGate:
    """Fila 7 -- el SEGUNDO punto de llamada (`remove.py --restriction
    new`, via `_build_fence_context()`/`_guard_restriction_new()`, las
    dos vias que llegan a `validate_replacement()` con el mismo
    `Context`). `_build_fence_candidate()` (`remove.py:100-112`) NUNCA
    pone `keys` en la `Note` del muro -- no hay flag `--keys` en
    `remove.py::_parse_args()` (verificado, cero coincidencias) -- asi
    que un positivo real de la puerta nueva es estructuralmente
    imposible por este camino hoy. Lo que SI se puede fijar: dos muros en
    la MISMA zona, con textos distintos (para no chocar con el Jaccard
    de siempre), tienen que nacer los dos SIN rebote -- el conjunto vacio
    de claves no puede ser tratado como coincidencia tampoco aqui. CONTROL,
    GREEN hoy y tiene que seguir siendolo."""

    def test_two_keyless_fences_in_the_same_zone_both_land_without_bouncing(self, tmp_repo, indexes):
        seed_zones_json(tmp_repo, ["product", "payments"])

        rc_i1, out_i1, err_i1 = _write_note(
            tmp_repo, "I", "product", "payments",
            "checkout gateway call times out under peak load",
            "load tests show the gateway call exceeding its own timeout during peak traffic",
        )
        assert rc_i1 == 0, f"stdout={out_i1!r} stderr={err_i1!r}"
        incident1_id = extract_note_id(out_i1)

        rc_fence1, out_fence1, err_fence1 = run_gitmem_script(
            [
                "remove", incident1_id, "raised the gateway timeout budget",
                "--restriction", "new",
                "--restriction-text", "never lower the gateway timeout below its documented floor",
                "--why", "a shorter timeout reproduces the outage under the same load",
            ],
            cwd=tmp_repo,
        )
        assert rc_fence1 == 0, f"stdout={out_fence1!r} stderr={err_fence1!r}"

        rc_i2, out_i2, err_i2 = _write_note(
            tmp_repo, "I", "product", "payments",
            "refund webhook silently drops events during a deploy",
            "events fired while the pod restarts never reach the queue and nobody is told",
        )
        assert rc_i2 == 0, f"stdout={out_i2!r} stderr={err_i2!r}"
        incident2_id = extract_note_id(out_i2)

        rc_fence2, out_fence2, err_fence2 = run_gitmem_script(
            [
                "remove", incident2_id, "queued webhook retries during deploys",
                "--restriction", "new",
                "--restriction-text", "never deploy the webhook consumer without a retry queue in front of it",
                "--why", "a deploy without the queue reproduces the dropped events",
            ],
            cwd=tmp_repo,
        )
        assert rc_fence2 == 0, (
            "dos muros SIN claves en la misma zona no pueden rebotar entre "
            f"si: stdout={out_fence2!r} stderr={err_fence2!r}"
        )

        pm = pm_path(tmp_repo)
        live_restrictions = {line.id for line in indexes.read("RESTRICTIONS.md", pm)}
        assert len(live_restrictions) == 2, (
            f"los dos muros tienen que quedar vigentes: {sorted(live_restrictions)!r}"
        )
