"""Contrato ROJO (pase de aceptacion, modo test-first): cerrar una
incidencia con ``--restriction new`` son DOS actos dentro del MISMO
comando -- (1) cerrar la incidencia (irreversible, ya en git) y (2)
escribir el muro nuevo, que pasa por el validador como cualquier otra
nota. Hoy, si el paso 2 rebota, la incidencia queda cerrada y SIN muro:
el aviso da el comando de reintento, pero si nadie lo ejecuta la
cicatriz se queda sin su leccion -- "si quiere apuntar un muro, tiene
que apuntarse ese muro" [encargo del propietario, 2026-08-05].

LA CONDUCTA QUE TIENE QUE QUEDAR: o las dos cosas, o ninguna. Antes de
cerrar nada, se comprueba que el muro va a poder nacer; si no va a
poder, NO se cierra la incidencia.

ESTADO REAL HOY (verificado leyendo `bin/memory/remove.py`, no
supuesto): `_guard_restriction_new()` (linea ~88) solo comprueba que
`args.id` empiece por ``I-``, que `--restriction-text` no venga vacio, y
que la incidencia exista en el historial de git -- NUNCA pasa el texto
del muro por `validator.validate_note()` antes de tocar nada. `main()`
(linea ~258) llama a `notes.close()` incondicionalmente y solo DESPUES,
si el cierre salio bien, intenta `_create_fence()` (linea ~267). Un
titular de muro de mas de 80 caracteres (`vocabulary.HEADLINE_MAX`) hoy
CIERRA la incidencia igual y solo rebota el muro -- exactamente el fallo
que este contrato prueba que ya no puede pasar. Los tests de este
fichero fallan hoy por esa causa real: la incidencia SI aparece cerrada
(``"archivada"`` en la salida, fuera de su indice, dentro de
``ARCHIVED.md``) cuando el contrato exige que NO lo este.

AVISO PARA QUIEN LEA `test_remove_script.py` A LA VEZ: su clase
``TestRestrictionNewWarnsThePermanentCloseAndGivesAWorkingRetryCommand``
afirma exactamente el comportamiento contrario al que este fichero exige
(que el cierre YA es permanente cuando el muro rebota) -- es el propio
fallo que el propietario pide cerrar, documentado ahi como si fuera la
conducta correcta antes de esta tarea. No se toca ese fichero (no es el
mio), pero quien implemente el arreglo va a tener que reconciliar los
dos: una vez este contrato este en verde, esa clase deja de describir la
realidad y hay que reescribirla -- eso es tarea de Ultron/Cerberus, no
de este fichero.

DOS COSAS ESCRITAS POR SEPARADO, COMPARADAS (regla del proyecto): lo que
``remove.py`` IMPRIME (``"archivada"``, el rechazo, el codigo de salida)
contra lo que los lectores reales dicen que paso de verdad --
``indexes.read``/``indexes.read_archive`` sobre ``INCIDENTS.md``/
``ARCHIVED.md``, y una comparacion BYTE A BYTE del contenido de esos dos
ficheros antes/despues. Nunca se confia solo en el texto impreso.

NO HAY ATACANTE EXTERNO (CLAUDE.md): lo que se vigila es que el sistema
no se rompa a si mismo -- una incidencia que queda cerrada sin su
leccion escrita al lado, silenciosamente, aunque el codigo de salida
avise.

Ejecutado contra ``bin/gitmem`` de verdad sobre un repositorio de prueba
temporal (``tmp_repo``), nunca contra este repositorio.
"""

import os

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_gitmem_script,
    seed_note_via_script,
    seed_zones_json,
)


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def vocabulary():
    return import_lib_memory_module("vocabulary")


@pytest.fixture
def query():
    return import_lib_memory_module("query")


def _seed_incident(tmp_repo, zone1, zone2, headline):
    seed_zones_json(tmp_repo, [zone1, zone2])
    # work="no" [2026-08-26, D-065/D-066]: la aduana de issues rebota una
    # I sin --issue/--work antes de llegar a la atomicidad del muro que
    # este fichero prueba -- ajeno al escenario bajo prueba aqui.
    rc, out, err = seed_note_via_script(
        tmp_repo, "I", zone1, zone2, headline,
        description="MARK_ROOTCAUSE a stray retry loop hammered the payments API",
        work="no",
    )
    assert rc == 0, (
        f"la siembra real de la incidencia fallo, no es parte de lo que "
        f"este contrato prueba: stdout={out!r} stderr={err!r}"
    )
    return extract_note_id(out)


class TestFenceThatCannotBeBornClosesNothing:
    """Punto 1 y 4 del encargo: un muro que el validador va a rechazar
    (titular de mas de 80 caracteres -- "el caso mas limpio") no puede
    dejar la incidencia cerrada. Ni la incidencia ni el muro se mueven."""

    def test_headline_too_long_leaves_the_incident_open_and_archive_untouched(
        self, tmp_repo, indexes, vocabulary,
    ):
        zone1, zone2 = "payments", "retries"
        incident_id = _seed_incident(
            tmp_repo, zone1, zone2, "MARK a real incident, fence must not be born",
        )
        pm = pm_path(tmp_repo)
        incidents_before = (pm / "INCIDENTS.md").read_bytes()
        archived_before = (pm / "ARCHIVED.md").read_bytes()
        restrictions_before = (pm / "RESTRICTIONS.md").read_bytes()

        too_long_headline = "F" * 96
        assert len(too_long_headline) > vocabulary.HEADLINE_MAX, (
            "fixture de test roto: el titular tiene que superar el tope real"
        )

        rc, out, err = run_gitmem_script(
            [
                "remove", incident_id, "fixed by capping the retry loop",
                "--restriction", "new",
                "--restriction-text", too_long_headline,
                "--why", "MARK_WHY retries without a cap keep taking the API down",
            ],
            cwd=tmp_repo,
        )

        assert rc != 0, (
            f"un muro con titular de 96 caracteres tiene que rebotar el "
            f"comando ENTERO: stdout={out!r} stderr={err!r}"
        )
        combined = out + err
        assert "Traceback" not in combined

        # LA CONDUCTA QUE TIENE QUE QUEDAR: el cierre NO se confirmo. Si
        # esto aparece, el bug sigue vivo -- hoy SI aparece.
        assert "archivada" not in combined.lower(), (
            f"la incidencia no puede haberse dado por cerrada si el muro "
            f"que la cierra no pudo nacer: {combined!r}"
        )
        # El rechazo tiene que nombrar el problema real del muro (mismo
        # texto que `validator.validate_headline` construye en
        # produccion), no un aviso generico.
        assert "titular" in combined.lower() and str(vocabulary.HEADLINE_MAX) in combined, (
            f"el rechazo tiene que explicar que falla en el muro, con el "
            f"tope real citado: {combined!r}"
        )

        # Lo que el sistema dice que paso (nada) contra lo que los
        # lectores reales y los ficheros en disco, byte a byte, confirman.
        assert any(line.id == incident_id for line in indexes.read("INCIDENTS.md", pm)), (
            f"{incident_id} deberia seguir vigente en su indice -- el "
            f"cierre tiene que haberse retenido"
        )
        archived = [a for a in indexes.read_archive(pm) if a.id == incident_id]
        assert archived == [], (
            f"{incident_id} NO deberia estar en ARCHIVED.md: {archived!r}"
        )
        assert (pm / "INCIDENTS.md").read_bytes() == incidents_before, (
            "INCIDENTS.md no deberia haber cambiado ni un byte"
        )
        assert (pm / "ARCHIVED.md").read_bytes() == archived_before, (
            "ARCHIVED.md no deberia haber cambiado ni un byte -- el cierre "
            "no puede haber pasado a medias"
        )
        assert (pm / "RESTRICTIONS.md").read_bytes() == restrictions_before, (
            "RESTRICTIONS.md no deberia haber cambiado ni un byte -- ningun "
            "muro a medias"
        )


class TestFenceThatCanBeBornClosesBoth:
    """Punto 2 del encargo: con un texto de muro valido, las dos cosas
    pasan -- la incidencia sale de su indice y entra en el archivo, Y el
    muro existe, en la misma pareja de zonas, apuntando a su incidencia."""

    def test_valid_fence_text_closes_the_incident_and_births_the_fence(
        self, tmp_repo, indexes, query, vocabulary,
    ):
        zone1, zone2 = "payments", "retries2"
        incident_id = _seed_incident(
            tmp_repo, zone1, zone2, "MARK a second real incident, fence must be born",
        )
        pm = pm_path(tmp_repo)

        restriction_text = "MARK_FENCE retry loops must always carry a hard cap"
        assert len(restriction_text) <= vocabulary.HEADLINE_MAX

        rc, out, err = run_gitmem_script(
            [
                "remove", incident_id, "fixed by capping the retry loop",
                "--restriction", "new",
                "--restriction-text", restriction_text,
                "--why", "MARK_WHY retries without a cap keep taking the API down",
            ],
            cwd=tmp_repo,
        )

        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        combined = out + err
        assert "Traceback" not in combined
        assert "archivada" in combined.lower(), (
            f"el cierre real tiene que confirmarse: {combined!r}"
        )

        assert not any(line.id == incident_id for line in indexes.read("INCIDENTS.md", pm)), (
            f"{incident_id} deberia haber salido de INCIDENTS.md"
        )
        archived = [a for a in indexes.read_archive(pm) if a.id == incident_id]
        assert len(archived) == 1, f"{incident_id} deberia estar en ARCHIVED.md: {archived!r}"

        restriction_lines = [
            line for line in indexes.read("RESTRICTIONS.md", pm)
            if line.headline == restriction_text
        ]
        assert len(restriction_lines) == 1, (
            f"el muro deberia estar en RESTRICTIONS.md exactamente una vez: "
            f"{restriction_lines!r}"
        )
        fence_id = restriction_lines[0].id

        previous_cwd = os.getcwd()
        os.chdir(str(tmp_repo))
        try:
            fence_note = query.by_id(fence_id)
        finally:
            os.chdir(previous_cwd)
        assert fence_note is not None, f"{fence_id} no se encuentra en el historial real de git"
        assert fence_note.origin == (incident_id,), (
            f"el muro deberia apuntar a la incidencia original con Origin: "
            f"salio origin={fence_note.origin!r}"
        )
        assert fence_note.zone1 == zone1 and fence_note.zone2 == zone2, (
            f"el muro deberia nacer en la MISMA pareja de zonas que la "
            f"incidencia: salio ({fence_note.zone1}, {fence_note.zone2})"
        )
