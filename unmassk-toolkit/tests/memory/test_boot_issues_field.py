"""Contrato de `BootSummary.issues` (`lib/memory/model.py`) y su render
en el bloque COUNTS (`lib/memory/boot.py::_recuentos_block`) -- campo
nuevo: las notas VIGENTES que llevan `issue` puesto, mismo filtro de
archivado que `questions`/`incidents` (D-060/D-064, la fila "Issues" del
menu de apertura necesita listarlas una por linea, no solo contarlas).

Fichero nuevo, no una ampliacion de `test_boot.py` -- mismo criterio que
`test_note_issue_field.py`/`test_work_issue_field.py`/
`test_report_render_issue_field.py`: cada campo/superficie nueva
alrededor de `issue` en este proyecto vive en su propio fichero
`test_*_issue(s)_field.py`, nunca mezclada dentro del contrato original
del modulo que ya cubria.

Los tres items del contrato, uno por clase:

  1. Varias notas con issue, incluidas dos con el MISMO numero -> cada
     una en su propia linea de COUNTS, ORDENADAS por (issue, id), y el
     contador de arriba cuenta issues DISTINTAS, nunca notas.
  2. Cero notas con issue -> COUNTS sale IDENTICO a como salia antes de
     este campo: cabecera, contador en 0, y nada mas antes de OPEN
     QUESTIONS -- ni una linea "      - issue #..." de mas.
  3. Una nota archivada con issue no aparece -- mismo filtro de vigentes
     (`indexes.archived_ids`) que ya usa el resto de `BootSummary`.

Fixtures y helpers DUPLICADOS a proposito de `test_boot.py` (mismo
criterio que el resto de la suite: `_cwd`/`make_note`/`make_context`
repetidos en cada fichero de contrato, ver p.ej.
`test_health_rules_coherence_contract.py`), nunca importados de otro
fichero de test.

SEMBRADO REAL, NUNCA FABRICADO [unmassk-standards Sec.34]: cada nota
entra por `notes.write(note, ctx)` contra un `tmp_repo` real. El orden
esperado de cada test se calcula en Python (`sorted(...)`) a partir de
los `note_id` REALES que `notes.write()` devolvio -- nunca tecleado a
mano -- y se compara contra lo que `boot.build()`/`boot.render()`
produjeron de verdad: dos cosas escritas por separado.
"""

import contextlib
import os
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from .conftest import import_lib_memory_module

_BASE_NOTE_FIELDS = dict(
    type="M",
    id="",
    zone1="product",
    zone2="boot-test",
    description="MARK_BOOT_ISSUES_DESCRIPTION not empty, not special",
    timestamp=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
)


@pytest.fixture
def boot():
    return import_lib_memory_module("boot")


@pytest.fixture
def model():
    return import_lib_memory_module("model")


@pytest.fixture
def config():
    return import_lib_memory_module("config")


@pytest.fixture
def validator():
    return import_lib_memory_module("validator")


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def notes():
    return import_lib_memory_module("notes")


@pytest.fixture
def make_note(model):
    """Fabrica de `Note`, mismos defaults neutros que `test_boot.py` --
    cada test override solo lo que le importa."""

    def _make(**overrides):
        fields = dict(_BASE_NOTE_FIELDS)
        fields.update(overrides)
        return model.Note(**fields)

    return _make


@pytest.fixture
def make_context(model, config, validator):
    """Un `Context` real, con las zonas de la nota ya dadas de alta EN
    MEMORIA -- mismo patron que `test_boot.py::make_context`."""

    def _make(zone_names=(), existing_in_zone=(), known_ids=frozenset(), cfg=None):
        zones = {
            name: model.Zone(name=name, description=f"MARK zone {name}", aliases=())
            for name in zone_names
        }
        return validator.Context(
            zones=zones,
            existing_in_zone=existing_in_zone,
            known_ids=known_ids,
            config=cfg if cfg is not None else config.Config(),
        )

    return _make


@contextlib.contextmanager
def _cwd(path):
    """Cambia el cwd del proceso a `path` durante el bloque, y lo
    restaura siempre -- mismo helper que `test_boot.py`/`test_report.py`."""
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _issue_lines(rendered):
    """Solo las lineas de issue del bloque COUNTS -- ningun otro bloque
    de `boot.render()` usa este prefijo literal."""
    return [line for line in rendered.splitlines() if line.startswith("      - issue #")]


class TestSeveralIssuesIncludingASharedNumberSortByIssueThenId:
    """Item (1) del contrato."""

    def test_issues_field_and_render_sort_by_issue_then_id_with_a_shared_number(
        self, boot, model, notes, tmp_repo, make_note, make_context
    ):
        root = Path(tmp_repo)
        zone = "bootissuesorderzone"
        ctx = make_context(zone_names=(zone,))

        # Orden de ESCRITURA elegido a proposito para que NO coincida con
        # el orden esperado tras ordenar por (issue, id) -- si el test
        # pasara conservando el orden de siembra, no distinguiria "ordena
        # de verdad" de "casualidad, el orden de escritura ya servia".
        seed_plan = (
            ("MARK_BOOTISSUES ninety written first", 90),
            ("MARK_BOOTISSUES three written second", 3),
            ("MARK_BOOTISSUES fortytwo a written third", 42),
            ("MARK_BOOTISSUES fortytwo b written fourth", 42),
        )
        seeded = []
        for headline, issue in seed_plan:
            note = make_note(
                type="M", zone1=zone, zone2=zone, headline=headline, issue=issue
            )
            with _cwd(root):
                write_result = notes.write(note, ctx)
            assert write_result.ok, (
                f"seed de {headline!r} fallo: "
                f"{write_result.git_error or write_result.rejections}"
            )
            seeded.append((issue, write_result.note_id, headline))

        with _cwd(root):
            summary = boot.build()
            rendered = boot.render(summary)

        # El orden esperado se calcula EN PYTHON, a partir de los
        # note_id REALES devueltos por notes.write() -- nunca tecleado.
        expected_order = sorted(seeded, key=lambda item: (item[0], item[1]))

        assert [
            (note.issue, note.id, note.headline) for note in summary.issues
        ] == expected_order, (
            f"BootSummary.issues no sale ordenada por (issue, id): "
            f"{summary.issues!r}, esperado {expected_order!r}"
        )

        distinct_issues = {issue for issue, _id, _headline in seeded}
        assert len(distinct_issues) == 3, (
            "comprobacion previa del propio escenario: 4 notas, 3 numeros "
            f"de issue distintos -- salio {distinct_issues!r}"
        )
        assert summary.open_issues == 3, (
            f"el contador debe contar issues DISTINTAS (3), no notas (4): "
            f"salio {summary.open_issues!r}"
        )

        expected_lines = [
            f"      - issue #{issue}: {headline}"
            for issue, _id, headline in expected_order
        ]
        assert _issue_lines(rendered) == expected_lines, (
            f"el render de COUNTS no lista las issues en el orden/formato "
            f"esperado:\n{rendered}"
        )

        # El contador de arriba, y el bloque de issues justo debajo, en
        # ese orden -- nunca despues de OPEN QUESTIONS/OPEN INCIDENTS.
        rendered_lines = rendered.splitlines()
        counts_index = rendered_lines.index("COUNTS")
        counter_index = rendered_lines.index(
            "   issues with a live note .  3"
        )
        first_issue_line_index = rendered_lines.index(expected_lines[0])
        questions_index = next(
            i for i, line in enumerate(rendered_lines) if line.startswith("❓ OPEN QUESTIONS")
        )
        assert counts_index < counter_index < first_issue_line_index < questions_index


class TestZeroIssuesRendersLikeBeforeTheField:
    """Item (2) del contrato."""

    def test_zero_issues_counts_section_has_no_extra_lines(
        self, boot, model, notes, tmp_repo, make_note, make_context
    ):
        root = Path(tmp_repo)
        zone = "bootissueszerozone"
        ctx = make_context(zone_names=(zone,))

        # Una nota vigente SIN issue -- prueba que el filtro mira
        # `issue is not None`, no "hay alguna nota vigente".
        note = make_note(
            type="M",
            zone1=zone,
            zone2=zone,
            headline="MARK_BOOTISSUES no issue on this one at all",
            issue=None,
        )
        with _cwd(root):
            write_result = notes.write(note, ctx)
        assert write_result.ok, (
            f"seed fallo: {write_result.git_error or write_result.rejections}"
        )

        with _cwd(root):
            summary = boot.build()
            rendered = boot.render(summary)

        assert summary.issues == (), (
            f"sin ninguna nota con issue, el campo debe quedar vacio: "
            f"{summary.issues!r}"
        )
        assert summary.open_issues == 0

        rendered_lines = rendered.splitlines()
        counts_index = rendered_lines.index("COUNTS")
        counter_line = rendered_lines[counts_index + 1]
        assert counter_line == "   issues with a live note .  0"
        # `_named_block()` antepone SIEMPRE una linea en blanco antes de
        # cada titulo con nombre propio (existia ya antes de este campo,
        # ver `lib/memory/boot.py::_named_block`) -- lo que este item del
        # contrato prohibe es cualquier linea DE MAS entre el contador y
        # esa separacion habitual, no la separacion en si.
        separator_line = rendered_lines[counts_index + 2]
        assert separator_line == "", (
            "con cero issues, justo tras el contador solo debe venir la "
            "linea en blanco que ya separaba COUNTS de OPEN QUESTIONS antes "
            f"de este campo -- salio {separator_line!r} en su lugar:\n{rendered}"
        )
        next_line = rendered_lines[counts_index + 3]
        assert next_line.startswith("❓ OPEN QUESTIONS"), (
            "con cero issues, COUNTS debe pasar directo del contador a la "
            f"separacion habitual y de ahi a OPEN QUESTIONS, sin ninguna "
            f"linea de issue de mas -- salio {next_line!r} en su lugar:\n{rendered}"
        )
        assert _issue_lines(rendered) == [], (
            f"no deberia haber ninguna linea de issue con el contador en "
            f"cero:\n{rendered}"
        )


class TestArchivedNoteWithIssueIsExcluded:
    """Item (3) del contrato."""

    def test_archived_note_with_issue_disappears_from_field_and_render(
        self, boot, model, indexes, notes, tmp_repo, make_note, make_context
    ):
        root = Path(tmp_repo)
        zone = "bootissuesarchivedzone"
        ctx = make_context(zone_names=(zone,))

        note = make_note(
            type="M",
            zone1=zone,
            zone2=zone,
            headline="MARK_BOOTISSUES archived issue seventy seven",
            issue=77,
        )
        with _cwd(root):
            write_result = notes.write(note, ctx)
        assert write_result.ok, (
            f"seed fallo: {write_result.git_error or write_result.rejections}"
        )
        note_id = write_result.note_id

        with _cwd(root):
            summary_before = boot.build()
        assert summary_before.open_issues == 1, (
            "comprobacion previa: la nota vigente con issue debe contar "
            f"como 1 antes de archivar -- salio {summary_before.open_issues!r}"
        )
        assert [n.id for n in summary_before.issues] == [note_id], (
            "comprobacion previa: la nota debe aparecer en `issues` antes "
            f"de archivar -- salio {summary_before.issues!r}"
        )

        with _cwd(root):
            indexes.remove(note_id, "MEMOS.md", notes.pm_root(root))
            indexes.archive(
                model.ArchiveLine(
                    date=date(2026, 8, 2),
                    type="M",
                    id=note_id,
                    zone1=zone,
                    zone2=zone,
                    headline=note.headline,
                    destination="closed",
                    destination_detail=(
                        "MARK_BOOTISSUES_DETAIL archived, routine cleanup"
                    ),
                ),
                notes.pm_root(root),
            )
            summary_after = boot.build()
            rendered_after = boot.render(summary_after)

        assert summary_after.issues == (), (
            "la nota archivada con issue no deberia seguir en `issues` -- "
            f"mismo filtro de vigentes que `questions`/`incidents`: "
            f"{summary_after.issues!r}"
        )
        assert summary_after.open_issues == 0, (
            "el contador debe bajar a 0 tras archivar -- salio "
            f"{summary_after.open_issues!r}"
        )
        assert not any(
            line.startswith("      - issue #77") for line in rendered_after.splitlines()
        ), (
            "la issue de la nota archivada no deberia aparecer en el "
            f"render:\n{rendered_after}"
        )
