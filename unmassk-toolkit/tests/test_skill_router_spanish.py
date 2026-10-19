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
     section (answer-first, delegate-to-Bilbo, literal-stop, automatic-mode;
     the silence reminder was retired by the owner on 2026-10-18). These
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

import os
import re

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
    # The owner retired the silence rule on 2026-10-18. His new rule:
    # «mientras se trabaja, ni parrafadas ni silencio: una linea numerada por
    # cada agente o paso que termina, tachandolo en la lista, con emojis; sin
    # aviso de voz». So the old silence prompts must no longer inject any
    # reminder at all: none of these prompts carries any other order, so the
    # contract is "nothing fires" -- not merely "the old key/wording is gone"
    # (a silence order back under another key or other words must go red).
    @pytest.mark.parametrize("prompt", SILENCIO_PROMPTS)
    def test_should_emit_no_reminder_when_prompt_asks_for_silence(self, prompt):
        match_reminders = _import_match_reminders()
        assert match_reminders(prompt) == [], prompt

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

    def test_should_describe_numbered_line_per_finished_step_when_automatico_fires(self):
        # Expected wording comes from the owner's current rule, not from the
        # code: «una linea numerada por agente o paso que acaba».
        # The old text allowed only 'silencio' or 'agente N de M' on screen;
        # that restriction must be gone.
        match_reminders = _import_match_reminders()
        reminders = match_reminders("modo automatico")
        texts = [t.lower() for k, t in reminders if k == "automatico"]
        assert texts, reminders
        text = texts[0]
        assert not re.search(r"solo\W+silencio", text), text
        assert "agente n de m" not in text, text
        assert "linea numerada" in text, text
        assert "agente" in text and "paso" in text, text

    def test_should_carry_the_current_owner_rule_when_automatico_fires(self):
        # Source: the owner's CURRENT rule (`gitmem rule`, rules.md), which
        # replaced the 2026-10-18 wording -- «al trabajar: una linea numerada
        # por agente o paso que acaba, solo «nombre, terminado»; si cambia el
        # orden (revisores hallan algo y vuelven Ultron y Dante), se dice; el
        # resto, al final». The reminder must say: name-only "terminado"
        # lines, and that an order change IS stated.
        match_reminders = _import_match_reminders()
        reminders = match_reminders("modo automatico")
        texts = [t.lower() for k, t in reminders if k == "automatico"]
        assert texts, reminders
        text = texts[0]
        assert "terminado" in text, text
        assert "nombre" in text, text
        assert re.search(r"cambia\w*\s+el\s+orden", text), text

    def test_should_no_longer_say_cross_it_off_the_list_when_automatico_fires(self):
        # The old rule's «tachandolo en la lista» is not in the owner's
        # current rule; a reminder still carrying it orders the old behaviour.
        match_reminders = _import_match_reminders()
        reminders = match_reminders("modo automatico")
        texts = [t.lower() for k, t in reminders if k == "automatico"]
        assert texts, reminders
        assert "tachando" not in texts[0], texts[0]

    def test_automaticamente_alone_does_not_trigger_automatico(self):
        match_reminders = _import_match_reminders()
        reminders = match_reminders("automaticamente")
        keys = [k for k, _ in reminders]
        assert "automatico" not in keys, reminders


# ══════════════════════════════════════════════════════════════════════════
# C) The hook wires both match_skills() and match_reminders() into stdout
# ══════════════════════════════════════════════════════════════════════════

class TestHookEmitsSpanishRoutingAndReminders:
    def test_should_print_no_orden_line_when_prompt_is_silencio_total(self, tmp_path):
        # Silence rule retired by the owner on 2026-10-18 (see TestMatchReminders):
        # through the real hook, no reminder line of any kind may appear.
        repo = _make_installed_repo(tmp_path)
        rc, stdout, stderr = _run_hook(repo, "silencio total, hostias")
        assert rc == 0, (rc, stdout, stderr)
        orden_lines = [line for line in stdout.splitlines() if line.startswith(REMINDER_MARKER)]
        assert not orden_lines, stdout

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
# C1b) #89 step 5.2 -- the automatic-mode reminder points to its reference
# ══════════════════════════════════════════════════════════════════════════
#
# The "Modo automatico" section leaves the boot-read core SKILL.md for a
# reference loaded on demand (D-094: nothing leaves without a pointer). The
# reminder must name that file, and the file it names must exist.

AUTOMATIC_MODE_REF = "unmassk-toolkit/skills/unmassk-core/references/automatic-mode.md"


class TestAutomaticoPointsToReference:
    def _text(self):
        match_reminders = _import_match_reminders()
        texts = [t for k, t in match_reminders("modo automatico") if k == "automatico"]
        assert texts, "automatico did not fire"
        return texts[0]

    def test_should_name_the_automatic_mode_reference_when_automatico_fires(self):
        # Bug caught: the reminder still sends Claude to the old core section.
        assert AUTOMATIC_MODE_REF in self._text()

    def test_should_no_longer_point_to_core_section_when_automatico_fires(self):
        # Bug caught: two pointers, one to a section that no longer exists.
        assert not re.search(r"secci[oó]n\s+modo\s+autom[aá]tico", self._text().lower())

    def test_named_reference_exists_in_the_shipped_plugin(self):
        # Bug caught: a pointer to a file nobody created.
        rel = AUTOMATIC_MODE_REF.split("/", 1)[1]
        assert os.path.isfile(os.path.join(SOURCE_ROOT, rel)), rel

    def test_hook_orden_line_carries_the_reference_for_owner_prompt(self, tmp_path):
        # Same through the user's door: the [orden] line the owner's own
        # words produce names the reference.
        repo = _make_installed_repo(tmp_path)
        rc, stdout, stderr = _run_hook(repo, "ponte en modo automático, me voy a dormir")
        assert rc == 0, (rc, stdout, stderr)
        orden = [l for l in stdout.splitlines() if l.startswith(REMINDER_MARKER)]
        assert any(AUTOMATIC_MODE_REF in l for l in orden), stdout


# ══════════════════════════════════════════════════════════════════════════
# C2) Agent completion notices are not owner prompts
# ══════════════════════════════════════════════════════════════════════════
#
# Claude Code delivers a finished background agent, and a message from another
# Claude session, as a UserPromptSubmit prompt. Drill evidence (raw log of the
# pre-release drill): 569 such notices went through the router; 527 fired
# [skill-router], 76 an "[orden] silencio" line, 34 "[orden] investigacion" --
# a Moriarty report that merely QUOTED "modo automatico" injected the
# automatic-mode order. Contract: a prompt that IS one of these notices gets
# no "[orden]" line and no "[skill-router]" line, whatever words it carries.
# The owner's own prompts keep firing (see the modo-automatico hook test above
# and the control below).

# Text an agent report realistically quotes: every reminder/skill trigger the
# owner's orders use.
_NOTICE_BODY = (
    "Moriarty: el router inyecta el recordatorio de modo automatico en cada "
    "informe; manda a bilbo, investiga; silencio; arregla eso e implementa. "
    "Verdict: FALLA"
)

AGENT_NOTICE_PROMPTS = {
    "task-notification": (
        "<task-notification>\n<task-id>a1</task-id>\n<status>completed</status>\n"
        f"<result>{_NOTICE_BODY}</result>\n</task-notification>"
    ),
    "another-session": (
        "Another Claude session sent a message:\n" + _NOTICE_BODY
    ),
    "agent-message": (
        '<agent-message from="dante">\n' + _NOTICE_BODY + "\n</agent-message>"
    ),
}


class TestHookIgnoresAgentNotices:
    def test_notice_body_alone_fires_both_lines_when_owner_types_it(self, tmp_path):
        # Control: the SAME words typed by the owner do fire, so the notice
        # tests below go red for the wrapper, not because the words are inert.
        repo = _make_installed_repo(tmp_path)
        rc, stdout, stderr = _run_hook(repo, _NOTICE_BODY)
        assert rc == 0, (rc, stdout, stderr)
        assert any(l.startswith(REMINDER_MARKER) for l in stdout.splitlines()), stdout
        assert SKILL_ROUTER_MARKER in stdout, stdout

    @pytest.mark.parametrize("kind", sorted(AGENT_NOTICE_PROMPTS))
    def test_should_emit_no_orden_line_when_prompt_is_agent_notice(self, tmp_path, kind):
        repo = _make_installed_repo(tmp_path)
        rc, stdout, stderr = _run_hook(repo, AGENT_NOTICE_PROMPTS[kind])
        assert rc == 0, (rc, stdout, stderr)
        orden_lines = [l for l in stdout.splitlines() if l.startswith(REMINDER_MARKER)]
        assert not orden_lines, stdout

    @pytest.mark.parametrize("kind", sorted(AGENT_NOTICE_PROMPTS))
    def test_should_emit_no_skill_routing_when_prompt_is_agent_notice(self, tmp_path, kind):
        repo = _make_installed_repo(tmp_path)
        rc, stdout, stderr = _run_hook(repo, AGENT_NOTICE_PROMPTS[kind])
        assert rc == 0, (rc, stdout, stderr)
        assert SKILL_ROUTER_MARKER not in stdout, stdout

    def test_should_still_route_owner_prompt_that_mentions_task_notification(self, tmp_path):
        # The owner talking ABOUT notices is still the owner: only a prompt
        # that IS a notice is skipped, not one that names the tag mid-text.
        repo = _make_installed_repo(tmp_path)
        rc, stdout, stderr = _run_hook(
            repo, "modo automático y arregla el <task-notification> del router"
        )
        assert rc == 0, (rc, stdout, stderr)
        orden_lines = [l for l in stdout.splitlines() if l.startswith(REMINDER_MARKER)]
        assert any("modo automatico" in l for l in orden_lines), stdout
        assert "unmassk-flow" in stdout, stdout


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
