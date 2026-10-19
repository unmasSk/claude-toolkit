"""
skill_router — per-message protocol-skill trigger-phrase matcher.

Lightweight, cheap trigger-phrase table used by the UserPromptSubmit hook
(hooks/user-prompt-memory-check.py) to nudge Claude toward the right
protocol skill on EVERY message, not just the first. NOT a BM25/ranking
rebuild -- an 11-agent council explicitly rejected building anything
heavier than a static substring check for this. Purely informational:
never blocks, never denies.

Public interface:
    match_skills(prompt_text) -> list[str]
    match_reminders(prompt_text) -> list[tuple[str, str]]
    is_agent_notice(prompt_text) -> bool

Every phrase in SKILL_TRIGGER_PHRASES is sourced from the matching skill's
own SKILL.md frontmatter `description` field (see skills/<name>/SKILL.md).
Exception: unmassk-core's description has no quoted trigger phrases (it is
"Loaded on session boot", not phrase-triggered) -- its entries are the
closest equivalent, drawn from its own distinctive nouns/verbs instead.
SKILL_TRIGGER_PHRASES stays English-only and untouched by this: a
permanent drift guard (tests/test_user_prompt_skill_router.py,
TestSkillTriggerPhrasesMatchLiveDescriptions) asserts every one of its
phrases is a live substring of its skill's SKILL.md description, and no
SKILL.md carries Spanish text.

The owner (Bex) writes prompts in Spanish, voice-dictated -- accents may
or may not survive dictation ("sesion" and "sesión" are the same word to
him). SKILL_TRIGGER_PHRASES_ES adds his Spanish phrasing per skill,
matched case- and accent-insensitively (NFKD-normalize + drop combining
marks, then lower-case, on both the prompt and every phrase) alongside
the English table -- kept as a separate dict so the drift guard above
never sees it. match_skills() checks both tables together.

REMINDER_TRIGGERS / match_reminders() is a second, unrelated table for
owner orders that are NOT skill invocations -- direct behavioural
corrections from the owner's rules
(answer-first, delegate-research-to-Bilbo, literal-stop, automatic-mode).
Same matching discipline (normalized substring, never raises), separate
result shape: a list of (key, Spanish reminder text) pairs, since more
than one order can legitimately fire on the same message.
"""

import re
import unicodedata


def _normalize(text: str) -> str:
    """Lower-case and strip diacritics via NFKD decomposition.

    Voice dictation drops accents unpredictably ("sesión" vs "sesion"),
    so both the prompt and every stored phrase are run through this before
    the substring check -- makes accents optional on both sides instead of
    hardcoding every accented/unaccented pair by hand.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.lower()


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

# Owner's Spanish phrasing per skill (voice-dictated; accents optional --
# see _normalize()). Kept separate from SKILL_TRIGGER_PHRASES on purpose
# (see module docstring): the drift guard only ever reads the English dict.
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
    """Return the list of skill names whose trigger phrases appear in
    prompt_text, in SKILL_TRIGGER_PHRASES iteration order.

    Cheap accent- and case-insensitive substring check (via _normalize())
    against both SKILL_TRIGGER_PHRASES (English) and SKILL_TRIGGER_PHRASES_ES
    (Spanish) -- no stemming, no fuzzy matching, no scoring. Never raises:
    any unexpected input just yields no matches (fail-open, same discipline
    as the rest of the hook).
    """
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


# ── Owner orders that are not skill invocations ────────────────────────────
#
# Each key maps to the trigger phrases (Spanish, owner's own wording) and
# the reminder text to surface (Spanish, in the owner's own
# wording). Every phrase below is chosen to match ONLY the owner's actual
# phrasing -- e.g. "orden-literal" uses "para ya"/"no sigas", never bare
# "para"/"parar", so an unrelated "para que funcione" or a lone "parar"
# does not misfire (verified against the test file's explicit negative
# cases).
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

# A block the owner pasted: `<pasted_content id="x">...</pasted_content id="x">`.
# Non-greedy and tied to its own id, so owner words between two blocks survive.
_PASTED_BLOCK_RE = re.compile(
    r'<pasted_content id="([^"]*)">.*?</pasted_content id="\1">', re.DOTALL)


def _strip_pasted(text: str) -> str:
    """Drop every pasted block: its words were written by someone else."""
    return _PASTED_BLOCK_RE.sub(" ", text)


# Openings Claude Code uses when it delivers an agent's message as a user
# turn. Such a turn is not the owner speaking: its words (an agent quoting
# "modo automatico", "implementa", ...) must not fire owner orders or skill
# routing. Only the OPENING counts -- an owner prompt that mentions one of
# these strings mid-text is still the owner.
AGENT_NOTICE_PREFIXES: tuple[str, ...] = (
    "<task-notification>",
    "Another Claude session sent a message:",
    "<agent-message",
)


def is_agent_notice(prompt_text: str) -> bool:
    """True when prompt_text, after leading whitespace, opens with one of
    AGENT_NOTICE_PREFIXES. Never raises; non-str/empty input yields False."""
    if not isinstance(prompt_text, str):
        return False
    return prompt_text.lstrip().startswith(AGENT_NOTICE_PREFIXES)


def match_reminders(prompt_text: str) -> list[tuple[str, str]]:
    """Return the list of (key, reminder_text) pairs whose trigger phrases
    appear in prompt_text, in REMINDER_TRIGGERS iteration order.

    Same normalized-substring discipline as match_skills(): accent- and
    case-insensitive, never raises, empty/None input yields an empty list.
    More than one reminder can fire on the same message. An entry with
    "ignore_pasted" matches only the owner's own words, outside pasted blocks.
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
