"""Second hardening round on the casillas-por-programa gate
(docs/plan/casillas-por-programa.md, D-052) -- Moriarty broke the
box<->task matching after Cerberus/Argus's first round; four repro
scenarios the coordinator asked for, RED against the code as it stood at
review time where applicable.

NOTA (2026-08-24, same day as the two prior rounds): Ultron was fixing
these IN PARALLEL. Verified by reading the live files (`hooks/
checklist-gate.py`, `hooks/skill-checklist-inject.py`,
`lib/checklist_state.py`) immediately before writing each test -- as of
that read, `_read_board_tasks()`/`_violations()` still did nothing but a
bare `.strip()` before the equality check (no unicode normalization, no
dash-form equivalence, no duplicate-subject tie-break), and
`skill-checklist-inject.py` still emitted the SAME enforcement-promise
sentence and the SAME (freshly-loaded-manifest) box text regardless of
whether the registry write actually succeeded or whether this was a
repeat load. Each test class states plainly whether it found RED or GREEN
the moment it was written; the final split reported to the coordinator is
whatever `python3 -m pytest unmassk-toolkit/tests -q` says when this file
is done, not a prediction.

Scenario -> what's being compared (unmassk-standards Sec.34 -- "a test
enters only if it compares two things written separately"):

1. NORMALIZATION -- a manifest box (written by `make_manifest()`, one
   independent path) is compared against a task's `subject` (written by
   `write_task()`, a SEPARATE independent path, deliberately spelled with
   a different dash form / Unicode normalization form / whitespace
   pattern than the manifest's box text) -- both derived from the SAME
   literal `_BOX_TEXT` constant in this file so the test can assert
   "these two independently-written spellings of the same box must
   match" without hand-typing a third "expected" value.
2. DUPLICATES -- two task files with the identical `subject`
   (`write_task(board, 9, ...)` and `write_task(board, 90, ...)`, two
   independent files) where the LOWER id is completed and the HIGHER id
   (which sorts after it alphabetically: `"9.json" < "90.json"`) is
   pending -- the gate's decision must not depend on which file
   `os.listdir()` happens to return last.
3. FALSE PROMISE -- the SAME hook invocation's stdout is compared against
   itself under two independently-real conditions (a normal write vs. a
   `chmod 555` registry directory) -- never a hand-typed "expected
   message" string, only the literal enforcement sentence already
   present in `hooks/skill-checklist-inject.py`'s own
   `_build_context_message()` source (quoted here as a substring check,
   not fabricated).
4. HOT-EDIT -- the SECOND invocation's additionalContext is compared
   against the REGISTRY file's content (read independently, the same
   round-trip technique `test_skill_checklist_inject.py` already uses)
   after the manifest file on disk was overwritten in between the two
   invocations -- never against the (now-stale) manifest content.
"""

import json
import os
import unicodedata
import uuid

import pytest

from .conftest import (
    GATE_HOOK,
    INJECT_HOOK,
    fake_home_env,
    make_skill_payload,
    make_stop_payload,
    registry_path,
    run_hook,
    task_board_dir,
    write_task,
)


def _new_session():
    return f"sess-{uuid.uuid4().hex[:8]}"


# ── 1. Normalization: dash form, NFC/NFD, whitespace ─────────────────────

_BOX_TEXT = "Verify — Moriarty entregó veredicto"  # em dash (U+2014), NFC "entregó"


def _dash_variant(text):
    """Same text, ASCII hyphen instead of the manifest's em dash."""
    return text.replace("—", "-")


def _nfd_variant(text):
    """Same text, NFD-decomposed accents (leaves the dash untouched --
    only the accented letters are affected by Unicode normalization)."""
    return unicodedata.normalize("NFD", text)


def _whitespace_variant(text):
    """Same text, irregular repeated/leading/trailing whitespace."""
    return "  " + text.replace(" — ", "  —   ").replace("Moriarty ", "Moriarty  ") + "  "


class TestBoxTaskMatchingIsNormalizationTolerant:
    """Coordinator item 1: three independently-real spellings of the SAME
    box must all be recognized as satisfied when the task is completed --
    a manifest box is one producer, a task's `subject` is a different one,
    and they don't have to be byte-identical to mean the same box."""

    def test_ascii_hyphen_task_satisfies_em_dash_manifest_box(
        self, fake_home, project_dir
    ):
        session_id = _new_session()
        self._seed_registry_with_box(project_dir, session_id, _BOX_TEXT)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, _dash_variant(_BOX_TEXT), "completed")

        rc, parsed, stdout, stderr = self._run_gate(fake_home, project_dir, session_id)

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"guion largo (manifiesto) vs guion ASCII (tarea) tiene que "
            f"contar como la MISMA casilla: parsed={parsed!r}"
        )

    def test_nfd_task_subject_satisfies_nfc_manifest_box(self, fake_home, project_dir):
        session_id = _new_session()
        self._seed_registry_with_box(project_dir, session_id, _BOX_TEXT)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, _nfd_variant(_BOX_TEXT), "completed")

        rc, parsed, stdout, stderr = self._run_gate(fake_home, project_dir, session_id)

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"NFC (manifiesto) vs NFD (tarea) de las mismas tildes tiene "
            f"que contar como la MISMA casilla: parsed={parsed!r}"
        )

    def test_repeated_whitespace_task_subject_satisfies_manifest_box(
        self, fake_home, project_dir
    ):
        session_id = _new_session()
        self._seed_registry_with_box(project_dir, session_id, _BOX_TEXT)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, _whitespace_variant(_BOX_TEXT), "completed")

        rc, parsed, stdout, stderr = self._run_gate(fake_home, project_dir, session_id)

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"espacios repetidos/sobrantes en la tarea tienen que seguir "
            f"casando con la misma casilla: parsed={parsed!r}"
        )

    def test_negative_control_a_genuinely_different_box_still_blocks(
        self, fake_home, project_dir
    ):
        """Guard against over-normalization: a task for a DIFFERENT box
        (not just a different spelling of the SAME box) must still count
        as missing -- otherwise the fix for 1-3 would be a fuzzy match
        loose enough to silently satisfy anything."""
        session_id = _new_session()
        self._seed_registry_with_box(project_dir, session_id, _BOX_TEXT)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, "Verify — Someone else entregó otra cosa", "completed")

        rc, parsed, stdout, stderr = self._run_gate(fake_home, project_dir, session_id)

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is not None and parsed.get("decision") == "block", (
            f"una tarea de una casilla DISTINTA no puede satisfacer esta: "
            f"parsed={parsed!r}"
        )
        assert _BOX_TEXT in parsed.get("reason", "")

    @staticmethod
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

    @staticmethod
    def _run_gate(fake_home_path, project_dir_path, session_id):
        payload = make_stop_payload(project_dir_path, session_id)
        return run_hook(
            GATE_HOOK, payload, cwd=project_dir_path, env=fake_home_env(fake_home_path)
        )


# ── 2. Duplicate subjects: a completed one must satisfy, regardless of listdir order ──


class TestDuplicateSubjectSatisfiedIfAnyIsCompleted:
    """Coordinator item 2: `9.json` (completed) sorts alphabetically
    BEFORE `90.json` (pending) -- `_read_board_tasks()`'s dict keyed by
    subject lets whichever file is read LAST win, so today the pending
    one silently overwrites the completed one and the gate blocks. The
    box is satisfied if ANY task with that subject is completed, no
    matter the file processing order."""

    def test_completed_duplicate_satisfies_even_when_a_pending_duplicate_sorts_after_it(
        self, fake_home, project_dir
    ):
        session_id = _new_session()
        box = "Casilla duplicada"
        reg_path = registry_path(project_dir, session_id)
        reg_path.parent.mkdir(parents=True, exist_ok=True)
        reg_path.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "skills": [{"skill": "unmassk-flow", "boxes": [box]}],
                    "block_count": 0,
                }
            ),
            encoding="utf-8",
        )
        board = task_board_dir(fake_home, session_id)
        write_task(board, 9, box, "completed")
        write_task(board, 90, box, "pending")
        # "9.json" < "90.json" alfabeticamente -- la pending se procesa
        # DESPUES si el emparejamiento es "el ultimo fichero gana".
        assert sorted(os.listdir(board)) == ["9.json", "90.json"]

        payload = make_stop_payload(project_dir, session_id)
        rc, parsed, stdout, stderr = run_hook(
            GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is None or parsed.get("decision") != "block", (
            f"una tarea completed con ese subject ya satisface la "
            f"casilla, exista o no un duplicado pending: parsed={parsed!r}"
        )


# ── 3. False promise when the registry can't be persisted ───────────────

# Literal substring from `hooks/skill-checklist-inject.py::_build_context_message()`
# -- quoted from the real production source, never fabricated (Sec.34).
_ENFORCEMENT_PROMISE_SUBSTRING = "will block closing this session"


class TestNoFalseEnforcementPromiseWhenPersistenceFails:
    """Coordinator item 3: if the registry write fails, the gate will
    never even SEE this skill's boxes -- so inject must not tell Claude
    the gate "will block" over them. It should still say SOMETHING (a
    soft notice), just not that specific claim."""

    def test_successful_persistence_still_makes_the_enforcement_promise(
        self, fake_home, project_dir, make_manifest
    ):
        """Baseline: the promise IS present on a normal, successful run
        -- proves the negative assertion below is meaningful (the phrase
        exists in the hook's vocabulary at all), not vacuously true."""
        skill = f"skill-promise-{uuid.uuid4().hex[:8]}"
        make_manifest(skill, ["Unico paso"])
        session_id = _new_session()

        payload = make_skill_payload(project_dir, session_id, skill)
        rc, parsed, stdout, stderr = run_hook(
            INJECT_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert _ENFORCEMENT_PROMISE_SUBSTRING in stdout, (
            f"baseline sano: la promesa de enforcement tiene que estar "
            f"presente cuando el registro SI se pudo persistir: {stdout!r}"
        )

    def test_readonly_registry_dir_drops_the_enforcement_promise(
        self, fake_home, project_dir, make_manifest
    ):
        if os.name != "posix":
            pytest.skip("chmod-based permission test is POSIX-only")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            pytest.skip("running as root bypasses permission bits entirely")

        skill = f"skill-promise-{uuid.uuid4().hex[:8]}"
        make_manifest(skill, ["Unico paso"])
        session_id = _new_session()

        reg_path = registry_path(project_dir, session_id)
        sc_dir = reg_path.parent
        sc_dir.mkdir(parents=True, exist_ok=True)
        # Pre-create the lock file with normal perms so file_lock() can
        # still OPEN it (opening an EXISTING file needs no dir-write) --
        # isolates the failure to the registry WRITE itself, same
        # technique already used in test_checklist_hardening.py item 1.
        open(f"{reg_path}.lock", "a").close()

        original_mode = sc_dir.stat().st_mode
        os.chmod(sc_dir, 0o555)
        try:
            payload = make_skill_payload(project_dir, session_id, skill)
            rc, parsed, stdout, stderr = run_hook(
                INJECT_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
            )

            assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
            assert "Traceback" not in stdout and "Traceback" not in stderr
            assert stderr.strip() != "", (
                "un fallo de persistencia tiene que avisar por stderr"
            )
            assert _ENFORCEMENT_PROMISE_SUBSTRING not in stdout, (
                f"el registro no se pudo persistir -- el gate NUNCA va a "
                f"ver estas casillas, asi que prometer que las hara "
                f"cumplir es una mentira: stdout={stdout!r}"
            )
            assert stdout.strip() != "", (
                "sigue habiendo que avisar de algo (aviso suave), no "
                "silencio total -- solo se retira la promesa de "
                f"enforcement: stdout={stdout!r}"
            )
        finally:
            os.chmod(sc_dir, original_mode)


# ── 4. Hot-edit: registry text wins over a manifest edited afterward ────


class TestHotEditedManifestNeverOverridesTheCommittedRegistryText:
    """Coordinator item 4 ("si es barato"): once a skill's boxes are
    committed to the registry, a manifest edited afterward must not leak
    its new text into a REPEAT load's additionalContext -- the gate will
    only ever check the registry's (old) text, so that's the only text
    that may honestly be presented as enforced."""

    def test_second_load_after_manifest_hot_edit_emits_the_registry_text(
        self, fake_home, project_dir, make_manifest
    ):
        skill = f"skill-hotedit-{uuid.uuid4().hex[:8]}"
        original_box = "Box V1 -- texto original committeado"
        manifest_path = make_manifest(skill, [original_box])
        session_id = _new_session()
        env = fake_home_env(fake_home)

        payload = make_skill_payload(project_dir, session_id, skill)
        rc1, _parsed1, out1, err1 = run_hook(INJECT_HOOK, payload, cwd=project_dir, env=env)
        assert rc1 == 0, f"stderr={err1!r}"
        assert original_box in out1

        # Hot-edit: overwrite the SAME manifest file with different boxes
        # -- independent of anything the registry or the first call wrote.
        edited_box = "Box V2 -- texto nuevo que NUNCA se comprometio"
        manifest_path.write_text(
            json.dumps({"skill": skill, "boxes": [edited_box]}), encoding="utf-8"
        )

        rc2, _parsed2, out2, err2 = run_hook(INJECT_HOOK, payload, cwd=project_dir, env=env)
        assert rc2 == 0, f"stderr={err2!r}"

        registry = json.loads(registry_path(project_dir, session_id).read_text(encoding="utf-8"))
        entry = next(e for e in registry["skills"] if e.get("skill") == skill)
        assert entry.get("boxes") == [original_box], (
            "el registro no se toca en una recarga (idempotencia ya "
            f"probada) -- tiene que seguir teniendo el texto ORIGINAL: {entry!r}"
        )

        assert original_box in out2, (
            f"la segunda carga tiene que emitir el texto del REGISTRO "
            f"(lo que el gate de verdad va a exigir): stdout={out2!r}"
        )
        assert edited_box not in out2, (
            f"el texto nuevo del manifiesto hot-editado NUNCA debe "
            f"aparecer -- el gate no lo conoce, prometerlo seria mentir: "
            f"stdout={out2!r}"
        )
