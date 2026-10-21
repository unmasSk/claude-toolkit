"""Trigger-phrase matcher for the UserPromptSubmit hook: suggests protocol skills and owner reminders.

Informational only; matching is an accent- and case-insensitive substring check that never raises.
"""

import re
import unicodedata


def _normalize(text: str) -> str:
    """Lower-case and strip diacritics via NFKD decomposition."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.lower()


# Each phrase must be a substring of its skill's SKILL.md description (checked by a test).
SKILL_TRIGGER_PHRASES: dict[str, list[str]] = {
    "unmassk-core": [
        "agents", "delegate", "invoke workflows", "domain plugins", "standards",
    ],
    "unmassk-flow": [
        "build a feature", "requires writing code", "implement",
        "add functionality", "non-trivial bug", "refactor",
    ],
    "unmassk-grill": [
        "grill me", "help me define this", "let's think this through",
    ],
    "unmassk-council": [
        "should i", "which option", "council this", "pressure-test this",
        "i'm torn", "help me decide", "open-ended idea generation", "prototype this",
    ],
    "unmassk-project-lifecycle": [
        "new project", "let's start", "continue", "where were we",
        "pick up where we left off", "scan this repo", "i inherited this codebase",
    ],
    "unmassk-audit": [
        "audit a module", "enterprise review", "launch audit",
    ],
    "unmassk-close-session": [
        "let's wrap up", "close the session", "we're done for today", "hand off",
    ],
    "unmassk-scaffolding": [
        "scaffold project", "which stack", "tech stack", "what framework",
    ],
}

# Owner's Spanish phrasing per skill; kept apart so the description check reads only the English dict.
SKILL_TRIGGER_PHRASES_ES: dict[str, list[str]] = {
    "unmassk-flow": [
        "arregla", "arreglalo", "construye", "implementa",
        "haz que funcione", "refactoriza",
    ],
    "unmassk-grill": [
        "vamos a pensarlo", "no tengo claro que quiero", "ayudame a definir",
    ],
    "unmassk-council": [
        "que opinas", "a o b", "ayudame a decidir", "consejo",
    ],
    "unmassk-project-lifecycle": [
        "continua", "donde estabamos", "seguimos",
    ],
    "unmassk-close-session": [
        "cierra sesion", "cerramos", "hasta mañana", "cierre de sesion",
    ],
}


def match_skills(prompt_text: str) -> list[str]:
    """Skill names whose English or Spanish trigger phrases appear in prompt_text; [] on bad input."""
    try:
        haystack = _normalize(prompt_text)
    except Exception:
        return []
    matched = []
    for skill, phrases in SKILL_TRIGGER_PHRASES.items():
        all_phrases = phrases + SKILL_TRIGGER_PHRASES_ES.get(skill, [])
        for phrase in all_phrases:
            if _normalize(phrase) in haystack:
                matched.append(skill)
                break
    return matched


# Owner orders that are not skill invocations: trigger phrases and the reminder to surface.
REMINDER_TRIGGERS: dict[str, dict[str, object]] = {
    "respuesta-primero": {
        "phrases": ["si o no", "contestame"],
        "text": (
            "la primera linea es la respuesta a lo que ha preguntado; lo "
            "demas, despues"
        ),
    },
    "bilbo": {
        "phrases": ["manda a bilbo", "investiga", "lo que usa la gente"],
        "text": "investigacion = Bilbo, uno solo, con prohibicion de lanzar agentes",
    },
    "orden-literal": {
        "phrases": ["quieto", "dejalo", "no sigas", "para ya"],
        "text": (
            "orden literal, sin excepcion que se te ocurra: si crees que un "
            "caso merece otra cosa, lo preguntas"
        ),
    },
    "automatico": {
        "phrases": [
            "modo automatico", "ponte en automatico", "automatico hasta que vuelva",
        ],
        "text": (
            "modo automatico: ejecuta todo el tablero, decide por el (la "
            "opcion mas enterprise); al trabajar: una linea numerada por "
            "agente o paso que acaba, solo «nombre, terminado»; si cambia "
            "el orden (revisores hallan algo y vuelven Ultron y Dante), se "
            "dice; el resto, al final, en UN informe: bien / probado / "
            "decisiones tomadas por el / errores "
            "(references/automatic-mode.md de la skill unmassk-core)"
        ),
        "ignore_pasted": True,
    },
}

# A pasted block, `<pasted_content id="x">...</pasted_content id="x">`, matched per id.
_PASTED_BLOCK_RE = re.compile(
    r'<pasted_content id="([^"]*)">.*?</pasted_content id="\1">', re.DOTALL)


def _strip_pasted(text: str) -> str:
    """Drop every pasted block: its words were written by someone else."""
    return _PASTED_BLOCK_RE.sub(" ", text)


# Openings of a user turn that carries an agent's message rather than the owner's words.
AGENT_NOTICE_PREFIXES: tuple[str, ...] = (
    "<task-notification>",
    "Another Claude session sent a message:",
    "<agent-message",
)


def is_agent_notice(prompt_text: str) -> bool:
    """True when prompt_text opens (after whitespace) with an AGENT_NOTICE_PREFIXES entry."""
    if not isinstance(prompt_text, str):
        return False
    return prompt_text.lstrip().startswith(AGENT_NOTICE_PREFIXES)


def match_reminders(prompt_text: str) -> list[tuple[str, str]]:
    """(key, reminder_text) pairs whose phrases appear in prompt_text; [] on empty or bad input.

    An entry with "ignore_pasted" matches only text outside pasted blocks.
    """
    if not prompt_text:
        return []
    try:
        haystack = _normalize(prompt_text)
        owner_haystack = _normalize(_strip_pasted(prompt_text))
    except Exception:
        return []
    matched: list[tuple[str, str]] = []
    for key, entry in REMINDER_TRIGGERS.items():
        text = owner_haystack if entry.get("ignore_pasted") else haystack
        for phrase in entry["phrases"]:
            if _normalize(phrase) in text:
                matched.append((key, entry["text"]))
                break
    return matched
