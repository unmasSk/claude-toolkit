"""Fourth hardening round on the casillas-por-programa gate
(docs/plan/casillas-por-programa.md, D-052) -- case-folding, confirmed by
hand by the coordinator to be MISSING from `checklist_state.normalize_box_text()`
even though the third round's report claimed it was already there.

Why the third round's tests never caught this (coordinator's own ask: "que
el nuevo compare de verdad dos cajas distintas"): every normalization test
in `test_checklist_matching_and_promise_hardening.py`
(`TestBoxTaskMatchingIsNormalizationTolerant`) varies the DASH, the
Unicode composition form, or WHITESPACE between the manifest box and the
task subject -- but every one of those variants was built from
`_BOX_TEXT` via `str.replace()`/`unicodedata.normalize()`, neither of
which touches letter case. `_BOX_TEXT` and every one of its dash/NFD/
whitespace variants are therefore ALL still lowercase-vs-lowercase (or
whatever case `_BOX_TEXT` itself uses) on both sides -- none of them ever
put the manifest box in one case and the task subject in a DIFFERENT one,
so a missing `.casefold()` in the real function had no test that could
have exercised it. This file is the one that actually varies case.

Scenarios (unmassk-standards Sec.34 -- two independently-written strings,
never a hand-typed "expected" standing in for what the code produces):

1. A REAL production box (`checklists/flow.json`'s own text, read from
   that file so this isn't a fabricated string) vs. the SAME text
   all-lowercase, and vs. all-UPPERCASE, both as a task subject.
2. A non-ASCII accented letter in a different case ("Ó" in the manifest
   box, "ó" in the task subject) -- the coordinator's own requested
   example, to pin that whatever normalization exists is unicode-case-
   aware.
3. A bonus, STRICTLY casefold-vs-lower()-distinguishing pair: the German
   "ß" (eszett) in the manifest box vs. "SS" in the task subject --
   `"ß".casefold() == "ss"` but `"ß".lower() == "ß"` (unchanged) in
   Python, verified interactively before writing this test. A fix that
   used `.lower()` instead of `.casefold()` would pass scenarios 1-2
   (plain Latin accented letters happen to fold the same under both) but
   fail this one -- this is the one test that actually tells the two
   implementations apart, not just "some case-insensitivity exists".
4. Negative control: a task in a DIFFERENT case that is ALSO a
   genuinely different box (not a re-cased version of the same one) must
   still block -- case-folding must not get so loose it treats unrelated
   text as a match.

With the code as it stood when the coordinator's message arrived
(`normalize_box_text()` missing `.casefold()`), scenarios 1-3 are RED
(reported "Missing" instead of satisfied). Whether they're still red or
already green by the time this file runs is reported in the test run,
not assumed here -- see this task's final report.
"""

import json
import uuid

import pytest

from .conftest import (
    CHECKLISTS_DIR,
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


# The manifest's REAL text, read from the real file Ultron/the design
# already ships -- not fabricated here (Sec.34: the manifest is one
# independent producer; this test never invents its content by hand).
def _real_flow_first_box() -> str:
    data = json.loads((CHECKLISTS_DIR / "flow.json").read_text(encoding="utf-8"))
    return data["boxes"][0]


class TestCaseFoldingMatchesRealProductionBox:
    """Scenario 1: the coordinator's exact repro -- a real manifest box,
    same text in a task subject but a DIFFERENT letter case (all-lower or
    all-upper)."""

    def test_all_lowercase_task_subject_satisfies_the_real_flow_box(
        self, fake_home, project_dir
    ):
        box = _real_flow_first_box()
        assert box != box.lower(), "fixture guard: el box real ya tiene que tener mayusculas"
        session_id = _new_session()
        _seed_registry_with_box(project_dir, session_id, box)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, box.lower(), "completed")

        rc, parsed, stdout, stderr = _run_gate(fake_home, project_dir, session_id)

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"la misma casilla real en minusculas tiene que satisfacerla: "
            f"parsed={parsed!r}"
        )

    def test_all_uppercase_task_subject_satisfies_the_real_flow_box(
        self, fake_home, project_dir
    ):
        box = _real_flow_first_box()
        session_id = _new_session()
        _seed_registry_with_box(project_dir, session_id, box)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, box.upper(), "completed")

        rc, parsed, stdout, stderr = _run_gate(fake_home, project_dir, session_id)

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"la misma casilla real en MAYUSCULAS tiene que satisfacerla: "
            f"parsed={parsed!r}"
        )


class TestCaseFoldingIsUnicodeAware:
    """Scenario 2 (coordinator's explicit example): a non-ASCII accented
    letter, different case on each side -- pins that the fold is
    unicode-aware casefold(), not an ASCII-only trick."""

    def test_uppercase_accented_letter_in_manifest_satisfies_lowercase_in_task(
        self, fake_home, project_dir
    ):
        box = "Confirmar la opción Ó antes de continuar"
        task_subject = "confirmar la opción ó antes de continuar"
        assert box != task_subject  # dos cadenas distintas de verdad
        session_id = _new_session()
        _seed_registry_with_box(project_dir, session_id, box)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, task_subject, "completed")

        rc, parsed, stdout, stderr = _run_gate(fake_home, project_dir, session_id)

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"'Ó' (manifiesto) vs 'ó' (tarea) tiene que casar via "
            f"casefold unicode-aware: parsed={parsed!r}"
        )


class TestCaseFoldingIsRealCasefoldNotLower:
    """Scenario 3 (bonus, strictly distinguishing): 'ß'.casefold() ==
    'ss' but 'ß'.lower() == 'ß' unchanged -- verified interactively before
    writing this test (see module docstring). A `.lower()`-based fix
    would pass every other test in this file and still fail this one."""

    def test_eszett_manifest_box_satisfies_double_s_task_subject(
        self, fake_home, project_dir
    ):
        assert "ß".casefold() == "ss"
        assert "ß".lower() == "ß"  # confirms this pair actually distinguishes the two
        box = "Confirmar la calle Straße antes de enviar"
        task_subject = "confirmar la calle STRASSE antes de enviar"
        session_id = _new_session()
        _seed_registry_with_box(project_dir, session_id, box)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, task_subject, "completed")

        rc, parsed, stdout, stderr = _run_gate(fake_home, project_dir, session_id)

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"'ß' (manifiesto) vs 'SS' (tarea) solo casan bajo casefold "
            f"real, nunca bajo lower(): parsed={parsed!r}"
        )


class TestCaseFoldDoesNotSwallowARealMismatch:
    """Scenario 4 (negative control): a task in a DIFFERENT case that is
    ALSO a genuinely different box must still block -- casefold must not
    get so loose it treats unrelated text as a match."""

    def test_recased_but_different_box_still_blocks(self, fake_home, project_dir):
        box = "Casilla Real De Flow Que Si Importa"
        wrong_task_subject = "OTRA CASILLA QUE NO TIENE NADA QUE VER"
        session_id = _new_session()
        _seed_registry_with_box(project_dir, session_id, box)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, wrong_task_subject, "completed")

        rc, parsed, stdout, stderr = _run_gate(fake_home, project_dir, session_id)

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is not None and parsed.get("decision") == "block", (
            f"una tarea de otra casilla, aunque este en otra caja, no "
            f"puede satisfacer esta: parsed={parsed!r}"
        )
        assert box in parsed.get("reason", "")
