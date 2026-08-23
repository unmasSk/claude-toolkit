"""
Contract (RED, test-first) for Spanish-language support in the per-message
skill router, plus a new sibling function for non-skill owner orders.

BUILD MODE: test-first / contract pass. These are ACCEPTANCE-level tests
written BEFORE Ultron implements anything — they define "done", not the
exhaustive branch/unit suite (that hardening pass happens after Ultron's
real implementation exists to measure). No production code is touched here.

Background
──────────
`lib/skill_router.py::SKILL_TRIGGER_PHRASES` / `match_skills()` are
English-only today (see [skill-router-contract-notes] in Dante's agent
memory for the original English contract). The owner (Bex) writes Spanish,
dictated by voice — accents may or may not survive dictation. Two gaps:

  A) `match_skills()` must also route realistic Spanish phrasing to the same
     8 protocol skills, case- and accent-insensitively.

  B) A handful of owner orders are NOT skill invocations — they are direct
     behavioural corrections already written into CLAUDE.md's "broncas"
     section (silence, answer-first, delegate-to-Bilbo, literal-stop). These
     need a NEW public function `match_reminders(prompt_text) ->
     list[tuple[str, str]]` (key, Spanish reminder text) so the hook can
     nudge Claude to follow them, the same way `match_skills()` nudges
     toward a skill.

  C) The hook (`hooks/user-prompt-memory-check.py`) must wire BOTH: a
     "[skill-router]" line (already wired, English-only today) and a NEW
     "[orden]" line for matched reminders.

Contract decision (Dante, pre-implementation) — the "[orden]" marker
──────────────────────────────────────────────────────────────────────
Locking the new reminder line to "[orden]", following the same
bracket-label convention as every other line this hook emits
("[skill-router]", "[git-memory-boot]", "[memory-check]", ...). Tests below
assert marker PRESENCE plus the exact reminder substrings given in the task
(quoted below per key) — never full sentence wording, which is Ultron's
call.

`match_reminders()` is imported INSIDE each test that needs it (not at
module level) so that, until Ultron adds it, each of those tests fails with
its own clean ImportError instead of one collection-level error that would
also hide section A's (already-importable) assertion failures.

Not covered here (deliberately, per the task): performance, the full
EXHAUSTION PROTOCOL branch/edge sweep — that is the hardening pass after
Ultron implements (Flow Verify / Step 5), run against the real
implementation, not against imagined shape.
"""

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_cmd  # noqa: F401  (kept for parity with sibling file / future hook tests)
from skill_router import match_skills

from test_user_prompt_skill_router import (
    _make_installed_repo,
    _run_hook,
    SKILL_ROUTER_MARKER,
)

REMINDER_MARKER = "[orden]"


# ══════════════════════════════════════════════════════════════════════════
# A) Spanish phrases route to skills via match_skills()
# ══════════════════════════════════════════════════════════════════════════

SPANISH_FLOW_PROMPTS = [
    "arregla eso",
    "arreglalo ya",
    "construye",
    "implementa",
    "haz que funcione",
    "refactoriza",
]

SPANISH_GRILL_PROMPTS = [
    "vamos a pensarlo",
    "no tengo claro que quiero",
    "ayudame a definir",
]

SPANISH_CLOSE_SESSION_PROMPTS = [
    "cierra sesion",
    "cerramos",
    "hasta mañana",
    "cierre de sesion",
]

SPANISH_COUNCIL_PROMPTS = [
    "que opinas, A o B",
    "ayudame a decidir",
    "consejo",
]

SPANISH_LIFECYCLE_PROMPTS = [
    "continua",
    "donde estabamos",
    "seguimos",
]


class TestSpanishSkillTriggers:
    @pytest.mark.parametrize("prompt", SPANISH_FLOW_PROMPTS)
    def test_spanish_prompt_routes_to_flow(self, prompt):
        matches = match_skills(prompt)
        assert "unmassk-flow" in matches, f"{prompt!r} -> {matches!r}"

    @pytest.mark.parametrize("prompt", SPANISH_GRILL_PROMPTS)
    def test_spanish_prompt_routes_to_grill(self, prompt):
        matches = match_skills(prompt)
        assert "unmassk-grill" in matches, f"{prompt!r} -> {matches!r}"

    @pytest.mark.parametrize("prompt", SPANISH_CLOSE_SESSION_PROMPTS)
    def test_spanish_prompt_routes_to_close_session(self, prompt):
        matches = match_skills(prompt)
        assert "unmassk-close-session" in matches, f"{prompt!r} -> {matches!r}"

    @pytest.mark.parametrize("prompt", SPANISH_COUNCIL_PROMPTS)
    def test_spanish_prompt_routes_to_council(self, prompt):
        matches = match_skills(prompt)
        assert "unmassk-council" in matches, f"{prompt!r} -> {matches!r}"

    @pytest.mark.parametrize("prompt", SPANISH_LIFECYCLE_PROMPTS)
    def test_spanish_prompt_routes_to_project_lifecycle(self, prompt):
        matches = match_skills(prompt)
        assert "unmassk-project-lifecycle" in matches, f"{prompt!r} -> {matches!r}"

    def test_accent_insensitive_close_session_both_forms_match(self):
        with_accent = match_skills("cierra sesión")
        without_accent = match_skills("cierra sesion")
        assert "unmassk-close-session" in with_accent, with_accent
        assert "unmassk-close-session" in without_accent, without_accent

    def test_case_insensitive_spanish_prompt(self):
        matches = match_skills("ARREGLA ESO")
        assert "unmassk-flow" in matches, matches

    def test_mixed_case_accented_prompt(self):
        matches = match_skills("Cierra Sesión, por favor")
        assert "unmassk-close-session" in matches, matches


# ══════════════════════════════════════════════════════════════════════════
# B) match_reminders() — owner orders that are not skills
# ══════════════════════════════════════════════════════════════════════════

SILENCIO_PROMPTS = ["silencio", "no digas nada", "callate", "silencio total"]
RESPUESTA_PRIMERO_PROMPTS = ["si o no", "sí o no", "contestame", "contéstame"]
BILBO_PROMPTS = ["manda a bilbo", "investiga", "lo que usa la gente"]
ORDEN_LITERAL_PROMPTS = ["quieto", "dejalo", "no sigas", "para ya"]


def _import_match_reminders():
    """Imported lazily (per-test) so an unimplemented match_reminders()
    fails each test individually with a clean ImportError, instead of one
    collection-level error hiding every other test in this file.
    """
    from skill_router import match_reminders
    return match_reminders


class TestMatchReminders:
    @pytest.mark.parametrize("prompt", SILENCIO_PROMPTS)
    def test_silencio_prompts_trigger_silencio_key(self, prompt):
        match_reminders = _import_match_reminders()
        reminders = match_reminders(prompt)
        keys = [k for k, _ in reminders]
        assert "silencio" in keys, f"{prompt!r} -> {reminders!r}"
        texts = [t for k, t in reminders if k == "silencio"]
        assert any("si escribes, es una pregunta" in t for t in texts), texts

    @pytest.mark.parametrize("prompt", RESPUESTA_PRIMERO_PROMPTS)
    def test_respuesta_prompts_trigger_respuesta_primero_key(self, prompt):
        match_reminders = _import_match_reminders()
        reminders = match_reminders(prompt)
        keys = [k for k, _ in reminders]
        assert "respuesta-primero" in keys, f"{prompt!r} -> {reminders!r}"
        texts = [t for k, t in reminders if k == "respuesta-primero"]
        assert any("primera linea" in t for t in texts), texts

    @pytest.mark.parametrize("prompt", BILBO_PROMPTS)
    def test_bilbo_prompts_trigger_bilbo_key(self, prompt):
        match_reminders = _import_match_reminders()
        reminders = match_reminders(prompt)
        keys = [k for k, _ in reminders]
        assert "bilbo" in keys, f"{prompt!r} -> {reminders!r}"
        texts = [t for k, t in reminders if k == "bilbo"]
        assert any("Bilbo" in t for t in texts), texts

    @pytest.mark.parametrize("prompt", ORDEN_LITERAL_PROMPTS)
    def test_orden_literal_prompts_trigger_orden_literal_key(self, prompt):
        match_reminders = _import_match_reminders()
        reminders = match_reminders(prompt)
        keys = [k for k, _ in reminders]
        assert "orden-literal" in keys, f"{prompt!r} -> {reminders!r}"
        texts = [t for k, t in reminders if k == "orden-literal"]
        assert any("literal" in t for t in texts), texts

    def test_para_que_funcione_does_not_trigger_orden_literal(self):
        match_reminders = _import_match_reminders()
        reminders = match_reminders("para que funcione")
        keys = [k for k, _ in reminders]
        assert "orden-literal" not in keys, reminders

    def test_parar_alone_does_not_trigger_orden_literal(self):
        match_reminders = _import_match_reminders()
        reminders = match_reminders("parar")
        keys = [k for k, _ in reminders]
        assert "orden-literal" not in keys, reminders

    def test_empty_string_returns_empty_list(self):
        match_reminders = _import_match_reminders()
        assert match_reminders("") == []

    def test_none_returns_empty_list(self):
        match_reminders = _import_match_reminders()
        assert match_reminders(None) == []


# "automatico" reminder — owner puts Claude into unattended/automatic mode
# and expects a report when he's back. Same accent/case-insensitive
# discipline as every other reminder key (see _normalize() in
# lib/skill_router.py). "automaticamente" alone (e.g. "hazlo automaticamente")
# is a different word in a different sentence shape and must NOT misfire —
# same discipline as "orden-literal"'s "para ya" vs bare "parar" guard above.
AUTOMATICO_PROMPTS = [
    "modo automatico",
    "modo automático",
    "ponte en automatico",
    "automatico hasta que vuelva",
]


class TestMatchRemindersAutomatico:
    @pytest.mark.parametrize("prompt", AUTOMATICO_PROMPTS)
    def test_automatico_prompts_trigger_automatico_key(self, prompt):
        match_reminders = _import_match_reminders()
        reminders = match_reminders(prompt)
        keys = [k for k, _ in reminders]
        assert "automatico" in keys, f"{prompt!r} -> {reminders!r}"
        texts = [t for k, t in reminders if k == "automatico"]
        assert any("modo automatico" in t for t in texts), texts
        assert any("informe" in t for t in texts), texts

    def test_automaticamente_alone_does_not_trigger_automatico(self):
        match_reminders = _import_match_reminders()
        reminders = match_reminders("automaticamente")
        keys = [k for k, _ in reminders]
        assert "automatico" not in keys, reminders


# ══════════════════════════════════════════════════════════════════════════
# C) The hook wires both match_skills() and match_reminders() into stdout
# ══════════════════════════════════════════════════════════════════════════

class TestHookEmitsSpanishRoutingAndReminders:
    def test_silencio_total_prompt_emits_orden_marker_with_reminder_text(self, tmp_path):
        repo = _make_installed_repo(tmp_path)
        rc, stdout, stderr = _run_hook(repo, "silencio total, hostias")
        assert rc == 0, (rc, stdout, stderr)
        orden_lines = [line for line in stdout.splitlines() if line.startswith(REMINDER_MARKER)]
        assert orden_lines, f"Expected a line starting with {REMINDER_MARKER!r}; got stdout: {stdout!r}"
        assert any("si escribes, es una pregunta" in line for line in orden_lines), orden_lines

    def test_arregla_los_tres_de_argus_prompt_routes_to_flow(self, tmp_path):
        repo = _make_installed_repo(tmp_path)
        rc, stdout, stderr = _run_hook(repo, "arregla los tres de Argus")
        assert rc == 0, (rc, stdout, stderr)
        assert SKILL_ROUTER_MARKER in stdout, stdout
        assert "unmassk-flow" in stdout, stdout

    def test_modo_automatico_prompt_emits_orden_marker_with_reminder_text(self, tmp_path):
        repo = _make_installed_repo(tmp_path)
        rc, stdout, stderr = _run_hook(repo, "ponte en modo automático, me voy a dormir")
        assert rc == 0, (rc, stdout, stderr)
        orden_lines = [line for line in stdout.splitlines() if line.startswith(REMINDER_MARKER)]
        assert orden_lines, f"Expected a line starting with {REMINDER_MARKER!r}; got stdout: {stdout!r}"
        assert any("modo automatico" in line for line in orden_lines), orden_lines


# ══════════════════════════════════════════════════════════════════════════
# D) English triggers keep working (no regression from the Spanish addition)
# ══════════════════════════════════════════════════════════════════════════

class TestEnglishTriggersStillWork:
    def test_implement_routes_to_flow(self):
        matches = match_skills("I need to implement this feature")
        assert "unmassk-flow" in matches, matches

    def test_lets_wrap_up_routes_to_close_session(self):
        matches = match_skills("let's wrap up for today")
        assert "unmassk-close-session" in matches, matches
