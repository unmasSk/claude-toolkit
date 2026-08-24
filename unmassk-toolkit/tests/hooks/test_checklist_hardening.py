"""Hardening extension of the casillas-por-programa contract
(docs/plan/casillas-por-programa.md, D-052) -- six scenarios the
coordinator asked for after Cerberus/Argus's review, RED against the code
as it stood at review time where applicable.

NOTA (2026-08-24): Ultron was fixing these IN PARALLEL while this file was
being written (same situation as `test_skill_checklist_inject.py`/
`test_checklist_gate.py`'s own first pass). By the time each test below
was run, several of Cerberus/Argus's findings were ALREADY fixed in
`hooks/checklist-gate.py` / `hooks/skill-checklist-inject.py` /
`lib/checklist_state.py` / `lib/git_helpers.py` (verified by reading the
live files immediately before writing each test, never from memory or from
the coordinator's description alone). Each test class states plainly
whether it found RED or GREEN the moment it was written -- the final
red/green split reported to the coordinator is whatever
`python3 -m pytest unmassk-toolkit/tests/hooks -q` says when this file is
done, not a prediction.

Scenario -> real mechanism verified in the code:

1. Persistence-failure-must-not-block: `checklist-gate.py::_apply_gate`
   now re-reads a FRESH registry under `checklist_state.locked()` and
   checks `save_registry()`'s return value before ever emitting a block --
   if the write fails, it warns on stderr and exits 0 instead of blocking
   with a counter that never advances on disk (the exact infinite-block
   Argus reproduced). Forced here with a real `chmod 555` on the registry
   directory (never on the fixture's tmp_path root -- only the specific
   `session-checklists/` dir), restored in `finally` before pytest's own
   tmp_path cleanup runs.
2. Non-dict-JSON-stdin: `checklist-gate.py::main()` now guards
   `isinstance(hook_input, dict)` right after `json.loads()`, resetting to
   `{}` on a miss -- `null`, `[1,2,3]`, `42` are all valid JSON that used
   to reach `hook_input.get(...)` directly and raise AttributeError.
   `skill-checklist-inject.py` already caught this generically (its
   `hook_input.get("tool_name")` call sits inside a broad `try/except`) --
   pinned here too, per the coordinator's "pina también el suyo".
3. Registry race: reproduced via the SAME technique
   `tests/test_file_lock.py` already established in this repo (asymmetric
   injected delay + a real cross-process exclusive lock, never a bare
   sleep-based race) -- but calling `lib/checklist_state.py`'s REAL
   `locked()`/`load_registry()`/`save_registry()` directly (the exact
   functions `skill-checklist-inject.py::_record_skill_load()` calls),
   with the delay injected INSIDE the locked critical section so the test
   also proves mutual exclusion is genuine, not just "usually fast enough
   to not collide".
4. Malformed `session_id`: `lib/checklist_state.py::is_safe_path_component()`
   (new) rejects any session_id containing "/", "\\", or ".." BEFORE it
   ever becomes a path component -- `registry_path()` raises `ValueError`
   for one, caught by `load_registry`/`save_registry` like any other
   unreadable/unwritable registry. Verified here that the traversal
   target (`.claude/.unmassk/bar.json` for `session_id="foo/../../bar"`)
   never gets created -- the registry can ONLY be born under
   `.claude/.unmassk/session-checklists/`.
5. Idempotency: `_record_skill_load()`'s `already_declared` set already
   short-circuits a repeat load of the same skill -- pinned by invoking
   the real inject hook twice in the same session and reading the
   registry once at the end.
6. Multi-skill: `checklist-gate.py::_expected_boxes()` already flattens
   every declared skill's boxes into one deduplicated list -- pinned with
   two skills (imitating flow + close-session) sharing one registry, and
   both skills' unmet boxes are required to show up in `reason` before the
   gate allows a clean close.

Round trip (unmassk-standards Sec.34): every "what must be true at the
end" assertion below reads the SAME registry/task-board files the test
itself seeded or the hook itself wrote -- never a hand-typed expected
string standing in for what the code actually produced.
"""

import json
import os
import subprocess
import sys
import time
import uuid

import pytest

from .conftest import (
    GATE_HOOK,
    INJECT_HOOK,
    LIB_DIR,
    fake_home_env,
    make_skill_payload,
    make_stop_payload,
    registry_path,
    run_hook,
    run_hook_raw,
    seed_registry,
    task_board_dir,
    write_task,
)


def _new_session():
    return f"sess-{uuid.uuid4().hex[:8]}"


# ── 1. Persistence failure must never block ─────────────────────────────


class TestPersistenceFailureNeverBlocks:
    """Coordinator item 1: a registry directory that can't be WRITTEN to
    (chmod 555) must make the gate warn and let the session close -- never
    block with a counter that can't advance (Argus's infinite-block
    repro)."""

    def test_readonly_registry_dir_fails_open_instead_of_blocking(
        self, fake_home, project_dir
    ):
        if os.name != "posix":
            pytest.skip("chmod-based permission test is POSIX-only")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            pytest.skip("running as root bypasses permission bits entirely")

        session_id = _new_session()
        items = ["Casilla que se queda pendiente"]
        seed_registry(project_dir, session_id, "unmassk-flow", items)
        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, items[0], "pending")  # open_items, not missing -> would block

        reg_path = registry_path(project_dir, session_id)
        sc_dir = reg_path.parent
        # Pre-create the lock file (normal perms) so file_lock() can still
        # OPEN it (no directory-write needed for opening an existing file)
        # -- isolating the failure to the registry WRITE itself, the exact
        # failure mode Argus reproduced, rather than lock acquisition.
        lock_path = f"{reg_path}.lock"
        open(lock_path, "a").close()

        original_mode = sc_dir.stat().st_mode
        os.chmod(sc_dir, 0o555)
        try:
            payload = make_stop_payload(project_dir, session_id)
            rc, parsed, stdout, stderr = run_hook(
                GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
            )

            assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
            assert parsed is None or parsed.get("decision") != "block", (
                "el contador no se pudo persistir -- bloquear de todas "
                f"formas repite el bucle infinito de Argus: parsed={parsed!r}"
            )
            assert stderr.strip() != "", (
                "un fallo de persistencia tiene que avisar por stderr, "
                "nunca fallar en silencio"
            )
            assert "Traceback" not in stdout and "Traceback" not in stderr
        finally:
            os.chmod(sc_dir, original_mode)


# ── 2. Non-dict valid JSON on stdin ──────────────────────────────────────

_NON_DICT_STDINS = ("null", "[1, 2, 3]", "42")


class TestNonDictStdinFailsOpenOnGate:
    """Coordinator item 2: `null`/`[1,2,3]`/`42` are all valid JSON that
    used to crash `checklist-gate.py` with an uncaught AttributeError
    (`hook_input.get(...)` on a non-dict) -- exit 1, never `exit 0`."""

    @pytest.mark.parametrize("raw_stdin", _NON_DICT_STDINS)
    def test_valid_non_dict_json_never_crashes_the_gate(
        self, fake_home, project_dir, raw_stdin
    ):
        rc, stdout, stderr = run_hook_raw(
            GATE_HOOK, raw_stdin, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, (
            f"stdin={raw_stdin!r} must not crash the gate (exit 0 always); "
            f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        )
        assert "Traceback" not in stdout and "Traceback" not in stderr
        parsed = None
        if stdout.strip():
            try:
                parsed = json.loads(stdout)
            except ValueError:
                parsed = None
        assert parsed is None or parsed.get("decision") != "block", (
            f"a non-dict stdin never has enough information to justify a "
            f"block: parsed={parsed!r}"
        )


class TestNonDictStdinFailsOpenOnInject:
    """Coordinator item 2 (pin, already correct on the other hook):
    `skill-checklist-inject.py`'s second `try/except Exception` already
    wraps `hook_input.get("tool_name")`, so the same non-dict stdin values
    already fail open. Pinned so a future refactor can't silently drop
    that generic except and reopen the same crash on this hook too."""

    @pytest.mark.parametrize("raw_stdin", _NON_DICT_STDINS)
    def test_valid_non_dict_json_never_crashes_inject(
        self, fake_home, project_dir, raw_stdin
    ):
        rc, stdout, stderr = run_hook_raw(
            INJECT_HOOK, raw_stdin, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert "Traceback" not in stdout and "Traceback" not in stderr
        assert stdout.strip() == "", (
            f"nada que declarar sin un tool_name/tool_input real: {stdout!r}"
        )


# ── 3. Registry race: two skills registering concurrently ───────────────


def _popen_py(code):
    return subprocess.Popen(
        [sys.executable, "-c", code],
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _wait(proc, timeout=20):
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        raise AssertionError(
            f"subprocess did not finish within {timeout}s -- likely a "
            f"deadlock. partial stdout={out!r} partial stderr={err!r}"
        ) from None
    return proc.returncode, out, err


def _wait_for_files(paths, procs, timeout=15):
    deadline = time.time() + timeout
    while not all(os.path.exists(p) for p in paths):
        if time.time() > deadline:
            errs = []
            for p in procs:
                p.kill()
                try:
                    _, err = p.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    err = "<did not exit even after kill()>"
                errs.append(err)
            raise AssertionError(
                f"subprocess(es) never signaled ready within {timeout}s: "
                f"{paths!r}. stderr so far: {errs!r}"
            )
        time.sleep(0.01)


def _writer_code(*, project_root, session_id, skill, boxes, ready_path, go_path, sleep_inside_lock):
    """Calls the REAL `lib/checklist_state.py` functions -- the exact ones
    `skill-checklist-inject.py::_record_skill_load()` calls -- with the
    delay injected INSIDE the locked critical section (same
    `race_delay`-inside-the-lock technique `test_file_lock.py` uses for
    its own without-vs-with-lock pair, adapted here since this module's
    lock is exercised directly rather than through a full hook process)."""
    return f"""
import sys, time
sys.path.insert(0, {str(LIB_DIR)!r})
import checklist_state

open({ready_path!r}, "w").close()

deadline = time.time() + 15
while not __import__("os").path.exists({go_path!r}):
    if time.time() > deadline:
        raise RuntimeError("GO signal never arrived within 15s")
    time.sleep(0.01)

with checklist_state.locked({project_root!r}, {session_id!r}):
    registry, corrupt = checklist_state.load_registry({project_root!r}, {session_id!r})
    time.sleep({sleep_inside_lock!r})
    registry["skills"].append({{"skill": {skill!r}, "boxes": {boxes!r}}})
    saved = checklist_state.save_registry({project_root!r}, {session_id!r}, registry)
    assert saved, "save_registry() reported failure inside the race test"
"""


class TestConcurrentSkillRegistrationsDoNotLoseAnEntry:
    """Coordinator item 3: two concurrent registrations of DIFFERENT
    skills (flow-like + audit-like) must both survive. Verified against
    the real `lib/checklist_state.py` (already carrying `locked()` at the
    time this was written -- see module docstring)."""

    def test_both_skills_present_after_concurrent_registration(self, tmp_path):
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)
        session_id = _new_session()

        ready_a = str(tmp_path / "ready_a")
        ready_b = str(tmp_path / "ready_b")
        go_path = str(tmp_path / "go")

        # B sleeps WHILE HOLDING THE LOCK -- A can only start its own read
        # once B's entire locked() block (including this sleep) has
        # released, proving genuine mutual exclusion, not lucky scheduling.
        code_b = _writer_code(
            project_root=project_root, session_id=session_id,
            skill="unmassk-audit", boxes=["box-audit-1"],
            ready_path=ready_b, go_path=go_path, sleep_inside_lock=0.5,
        )
        code_a = _writer_code(
            project_root=project_root, session_id=session_id,
            skill="unmassk-flow", boxes=["box-flow-1"],
            ready_path=ready_a, go_path=go_path, sleep_inside_lock=0.0,
        )

        proc_b = _popen_py(code_b)
        proc_a = _popen_py(code_a)
        _wait_for_files([ready_a, ready_b], [proc_a, proc_b])
        open(go_path, "w").close()

        rc_a, out_a, err_a = _wait(proc_a)
        rc_b, out_b, err_b = _wait(proc_b)

        assert rc_a == 0, f"writer A (flow) failed: stdout={out_a!r} stderr={err_a!r}"
        assert rc_b == 0, f"writer B (audit) failed: stdout={out_b!r} stderr={err_b!r}"

        reg_path = registry_path(project_root, session_id)
        final = json.loads(open(reg_path, encoding="utf-8").read())
        skills = {entry.get("skill") for entry in final.get("skills", [])}
        assert skills == {"unmassk-flow", "unmassk-audit"}, (
            f"las DOS entradas tienen que sobrevivir a la carrera; "
            f"encontrado={skills!r} registro completo={final!r}"
        )


# ── 4. Malformed session_id ──────────────────────────────────────────────


class TestMalformedSessionIdNeverEscapesSessionChecklistsDir:
    """Coordinator item 4: the registry can ONLY be born under
    `.claude/.unmassk/session-checklists/` -- a traversal-bearing
    session_id must never create a file anywhere else, and must fail open
    with a warning rather than silently landing wherever the traversal
    resolves to."""

    def test_traversal_session_id_is_rejected_not_followed(
        self, fake_home, project_dir, make_manifest
    ):
        skill = f"skill-race-{uuid.uuid4().hex[:8]}"
        make_manifest(skill, ["Unico paso"])
        malicious_session_id = "foo/../../bar"

        payload = make_skill_payload(project_dir, malicious_session_id, skill)
        rc, parsed, stdout, stderr = run_hook(
            INJECT_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        escaped_path = project_dir / ".claude" / ".unmassk" / "bar.json"
        assert not escaped_path.exists(), (
            f"un session_id con travesia de directorios no puede escribir "
            f"fuera de session-checklists/: aparecio {escaped_path}"
        )
        sc_dir = project_dir / ".claude" / ".unmassk" / "session-checklists"
        if sc_dir.exists():
            stray = [p for p in sc_dir.rglob("*") if p.is_file() and p.parent != sc_dir]
            assert not stray, f"no debe haber ficheros anidados bajo session-checklists/: {stray!r}"
        assert stderr.strip() != "", (
            "un session_id malformado tiene que avisar por stderr, no "
            "resolverse en silencio"
        )

    def test_session_id_with_plain_slash_is_rejected_not_nested(
        self, fake_home, project_dir, make_manifest
    ):
        skill = f"skill-race-{uuid.uuid4().hex[:8]}"
        make_manifest(skill, ["Unico paso"])
        malicious_session_id = "abc/def"

        payload = make_skill_payload(project_dir, malicious_session_id, skill)
        rc, parsed, stdout, stderr = run_hook(
            INJECT_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        nested_dir = project_dir / ".claude" / ".unmassk" / "session-checklists" / "abc"
        assert not nested_dir.exists(), (
            f"un '/' suelto en session_id no puede crear un subdirectorio "
            f"anidado bajo session-checklists/: aparecio {nested_dir}"
        )
        assert stderr.strip() != "", "tiene que avisar por stderr al rechazar el session_id"


# ── 5. Idempotency ────────────────────────────────────────────────────────


class TestSameSkillLoadedTwiceIsOneEntry:
    """Coordinator item 5: the docstring already promises this
    ("idempotent -- reloading the same skill twice does not duplicate the
    expectation") but nothing exercised it before now."""

    def test_second_load_of_the_same_skill_does_not_duplicate(
        self, fake_home, project_dir, make_manifest
    ):
        skill = f"skill-idem-{uuid.uuid4().hex[:8]}"
        items = ["Unico paso"]
        make_manifest(skill, items)
        session_id = _new_session()
        env = fake_home_env(fake_home)

        payload = make_skill_payload(project_dir, session_id, skill)
        rc1, _parsed1, _out1, err1 = run_hook(INJECT_HOOK, payload, cwd=project_dir, env=env)
        rc2, _parsed2, _out2, err2 = run_hook(INJECT_HOOK, payload, cwd=project_dir, env=env)

        assert rc1 == 0 and rc2 == 0, f"stderr1={err1!r} stderr2={err2!r}"

        reg_path = registry_path(project_dir, session_id)
        registry = json.loads(reg_path.read_text(encoding="utf-8"))
        matching = [e for e in registry.get("skills", []) if e.get("skill") == skill]
        assert len(matching) == 1, (
            f"cargar la MISMA skill dos veces en una sesion tiene que dejar "
            f"UNA sola entrada, no {len(matching)}: registro={registry!r}"
        )
        assert matching[0].get("boxes") == items


# ── 6. Multi-skill: both skills' boxes required ──────────────────────────


class TestMultiSkillRegistryRequiresBothSkillsBoxes:
    """Coordinator item 6: the design names this scenario explicitly
    (Flow, then close-session, in the same session) and nothing exercised
    it before now -- `_expected_boxes()` already flattens across every
    declared skill, this pins that it actually holds both skills'
    boxes accountable."""

    def test_incomplete_board_blocks_on_boxes_from_either_skill(
        self, fake_home, project_dir
    ):
        session_id = _new_session()
        flow_items = ["Flow paso A", "Flow paso B"]
        close_items = ["Close paso A"]
        reg_path = registry_path(project_dir, session_id)
        reg_path.parent.mkdir(parents=True, exist_ok=True)
        reg_path.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "skills": [
                        {"skill": "unmassk-flow", "boxes": flow_items},
                        {"skill": "unmassk-close-session", "boxes": close_items},
                    ],
                    "block_count": 0,
                }
            ),
            encoding="utf-8",
        )

        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, flow_items[0], "completed")
        write_task(board, 2, flow_items[1], "completed")
        # close_items[0] never created -> ausente, de la SEGUNDA skill

        payload = make_stop_payload(project_dir, session_id)
        rc, parsed, stdout, stderr = run_hook(
            GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert parsed is not None and parsed.get("decision") == "block", (
            f"una casilla ausente de la SEGUNDA skill tiene que bloquear "
            f"igual que si fuera de la primera: parsed={parsed!r}"
        )
        assert close_items[0] in parsed.get("reason", ""), (
            f"la casilla de close-session tiene que aparecer en la razon: "
            f"{parsed.get('reason')!r}"
        )

    def test_all_boxes_from_both_skills_completed_is_mute(self, fake_home, project_dir):
        session_id = _new_session()
        flow_items = ["Flow paso A"]
        close_items = ["Close paso A", "Close paso B"]
        reg_path = registry_path(project_dir, session_id)
        reg_path.parent.mkdir(parents=True, exist_ok=True)
        reg_path.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "skills": [
                        {"skill": "unmassk-flow", "boxes": flow_items},
                        {"skill": "unmassk-close-session", "boxes": close_items},
                    ],
                    "block_count": 0,
                }
            ),
            encoding="utf-8",
        )

        board = task_board_dir(fake_home, session_id)
        write_task(board, 1, flow_items[0], "completed")
        write_task(board, 2, close_items[0], "completed")
        write_task(board, 3, close_items[1], "completed")

        payload = make_stop_payload(project_dir, session_id)
        rc, parsed, stdout, stderr = run_hook(
            GATE_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert stdout.strip() == "", (
            f"con TODAS las casillas de las DOS skills completas, el gate "
            f"tiene que quedarse mudo: stdout={stdout!r}"
        )
