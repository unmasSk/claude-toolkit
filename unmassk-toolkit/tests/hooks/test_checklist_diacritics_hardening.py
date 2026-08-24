"""Fifth hardening round on the casillas-por-programa gate
(docs/plan/casillas-por-programa.md, D-052) -- diacritics.

Decision (coordinator, 2026-08-24): the box<->task matcher now ALSO
ignores diacritics (accents, tildes) -- not just dash form, Unicode
composition, whitespace, and letter case (rounds 3-4). Verified by
reading `lib/checklist_state.py::normalize_box_text()` immediately before
writing this file: it NFC-composes accented letters (so "ó" written as
"o" + combining acute and "ó" written as one precomposed codepoint
already match each other -- round 3's NFC/NFD test), but it does NOT
strip the accent itself -- "entregó" and "entrego" were still two
different strings after normalization. This file's tests are RED against
that code; whether Ultron's parallel fix has already landed by the time
they run is reported in the test run, not assumed here (see this task's
final report).

Scenarios (unmassk-standards Sec.34 -- two independently-written strings,
never a hand-typed "expected" standing in for what the code produces):

1. A manifest box with an accented word ("entregó") vs. a task subject
   with the same word, accent-free ("entrego") -- must be satisfied.
2. Negative control: two GENUINELY different boxes (different words, not
   just a missing accent) must still not be confused after diacritics are
   stripped.
3. The explicit "ñ" vs "n" case the coordinator called out BY NAME as a
   deliberate, accepted consequence of this decision -- not a bug to be
   caught, a contract to be pinned. Written as its own test so a future
   reader who only skims failures understands this one failing would mean
   the DECISION was reverted, not that a real bug reappeared.
"""

import json
import uuid

import pytest

from .conftest import (
    GATE_HOOK,
    fake_home_env,
    make_stop_payload,
    registry_path,
    run_hook,
    task_board_dir,
    write_task,
)


def _new_session():
    return f"sess-{uuid.uuid4().hex[:8]}"


def _seed_registry_with_box(project_dir_path, session_id, box_text):
    reg_path = registry_path(project_dir_path, session_id)
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(
        json.dumps(
            {
                "session_id": session_id,
                "skills": [{"skill": "unmassk-flow", "boxes": [box_text]}],
                "block_count": 0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _run_gate(fake_home_path, project_dir_path, session_id):
    payload = make_stop_payload(project_dir_path, session_id)
    return run_hook(GATE_HOOK, payload, cwd=project_dir_path, env=fake_home_env(fake_home_path))


class TestDiacriticsAreIgnoredWhenMatching:
    """Scenario 1: the coordinator's exact repro -- an accented manifest
    box vs. the same task subject with the accent dropped."""

    def test_accent_free_task_subject_satisfies_accented_manifest_box(
        self, fake_home, project_dir
    ):
        box = "Verify — Moriarty entregó veredicto"
        task_subject = "Verify — Moriarty entrego veredicto"  # sin tilde en la "o"
        assert box != task_subject  # dos cadenas distintas de verdad
        session_id = _new_session()
        _seed_registry_with_box(project_dir, session_id, box)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, task_subject, "completed")

        rc, parsed, stdout, stderr = _run_gate(fake_home, project_dir, session_id)

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"'entregó' (manifiesto) vs 'entrego' (tarea, sin tilde) "
            f"tiene que casar tras quitar diacriticos: parsed={parsed!r}"
        )


class TestDiacriticStrippingDoesNotSwallowARealMismatch:
    """Scenario 2 (negative control, de siempre): dos casillas
    REALMENTE distintas (no solo con/sin tilde de la MISMA palabra) no se
    pueden confundir tras quitar acentos."""

    def test_two_genuinely_different_boxes_still_do_not_match(
        self, fake_home, project_dir
    ):
        box = "Confirmar el diseño técnico antes de continuar"
        wrong_task_subject = "Revisar el presupuesto financiero del trimestre"
        session_id = _new_session()
        _seed_registry_with_box(project_dir, session_id, box)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, wrong_task_subject, "completed")

        rc, parsed, stdout, stderr = _run_gate(fake_home, project_dir, session_id)

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is not None and parsed.get("decision") == "block", (
            f"quitar diacriticos no puede hacer que dos casillas SIN "
            f"relacion cuenten como la misma: parsed={parsed!r}"
        )
        assert box in parsed.get("reason", "")


class TestEneVersusEneIsADeliberateAcceptedEffect:
    """Scenario 3: 'ñ' vs 'n' -- the coordinator named this explicitly.
    THIS IS NOT A BUG. If this test ever starts failing, it means
    diacritic-stripping was reverted or scoped down, not that a real
    mismatch-prevention regression reappeared -- do not 'fix' this by
    making the matcher stricter again without going back to the
    coordinator first, the decision that made it pass was deliberate."""

    def test_ene_with_tilde_and_plain_ene_count_as_the_same_box(
        self, fake_home, project_dir
    ):
        box = "Confirmar el diseño antes de continuar"
        task_subject = "Confirmar el diseno antes de continuar"  # "n", no "ñ"
        assert box != task_subject
        assert "ñ" in box and "ñ" not in task_subject
        session_id = _new_session()
        _seed_registry_with_box(project_dir, session_id, box)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, task_subject, "completed")

        rc, parsed, stdout, stderr = _run_gate(fake_home, project_dir, session_id)

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"'ñ' vs 'n' es el efecto ACEPTADO de quitar diacriticos "
            f"(decision del propietario, 2026-08-24), no un bug: "
            f"parsed={parsed!r}"
        )
