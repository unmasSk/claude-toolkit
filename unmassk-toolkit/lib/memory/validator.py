"""The single implementation of note validation.

Every function is pure (data comes in `Context`) except `validate_issue`, which calls `gh`.
`validate_pain_question`, `validate_distillation`, `validate_incident_close_question` and
`validate_issue_gate` take an answer that is not a `Note` field, so `validate_note` does not call them.
"""

import re
from dataclasses import dataclass

from config import Config
import emojis
from model import Note, Rejection, Zone
import rejection as rejection_
import similar
from validator_issue import validate_issue, validate_issue_gate
from validator_pointers import carry_accepted_flags, carry_answer_flags, description_flag, takes, validate_pointers, why_flag
from validator_searched import (  # noqa: F401 -- re-exported
    SEARCHED_PLACEHOLDER,
    SEARCHED_QUESTION,
    carry_searched,
    searched_given,
    searched_suffix,
    validate_searched,
)
from validator_zones import validate_zones

from vocabulary import (
    HEADLINE_MAX,
    MARKER_KEYS,
    MAX_KEYS,
    PAIN_QUESTION,
    SIMILARITY_THRESHOLD,
    TYPES,
)

# Literal "yes" value of the --stops flag.
_STOPS_YES = "yes"

_WORD_RE = re.compile(r"\w+", re.UNICODE)

# Single source of the WIP glyph, shared with `bin/memory/wip.py`.
_WIP_MARKER = emojis.CHANNEL_EMOJI["wip"]
_WIP_PREFIX = "[WIP]"


@dataclass(frozen=True)
class Context:
    """Everything the validator needs to know; supplied by the caller."""

    zones: dict[str, Zone]
    existing_in_zone: tuple[Note, ...]
    known_ids: frozenset[str]
    config: Config


def validate_note(note: Note, ctx: Context) -> tuple[Rejection, ...]:
    """All rules derivable from `note` and `ctx`. Empty means valid."""
    checks = (
        _validate_type(note),
        validate_zones(note, ctx.zones),
        validate_headline(note.headline),
        validate_fields(note),
        validate_pointers(note, ctx.known_ids, ctx.existing_in_zone),
        validate_replacement(note, ctx.existing_in_zone),
    )
    return tuple(r for r in checks if r is not None)


def validate_headline(headline: str) -> Rejection | None:
    """Reject a headline longer than `HEADLINE_MAX`."""
    length = len(headline)
    if length <= HEADLINE_MAX:
        return None

    what = f"el titular tiene {length} caracteres y el tope son {HEADLINE_MAX}"
    options = (
        f'  "{headline}"',
        "",
        "El titular es lo unico que se ve en el indice y en el arranque: si no se",
        "lee de un vistazo, deja de cumplir su funcion. No se corta solo, porque",
        "cortarlo borraria justo la parte que suele importar.",
        "",
        "Dos salidas:",
        "",
        "  acortalo          quedate con la prohibicion; el detalle va a Description",
        "  parte en dos      si dice dos cosas, son dos notas",
    )
    command = (
        "gitmem note <TIPO> --zones <zona1> <zona2> "
        f'"<titular de hasta {HEADLINE_MAX} caracteres>" --description "..."',
    )
    return rejection_.build(
        kind="headline_too_long", what=what, options=options, command=command
    )


def _validate_type(note: Note) -> Rejection | None:
    """Reject a note whose type is not in the vocabulary."""
    if note.type in TYPES:
        return None

    what = "no se que tipo es esto"
    options = [
        f'"{note.headline}" no encaja limpiamente en ningun tipo.',
        "",
    ]
    for letter, spec in TYPES.items():
        options.append(f"  {letter}  {spec.description}")
    options.append("")
    options.append(
        "Partela en dos, o elige uno, y relanza. Que no encaje es informacion:"
    )
    options.append(
        "si de verdad no es ninguno de los siete, dilo en el chat antes de forzarlo."
    )
    command = (
        f'gitmem note <TIPO> --zones {note.zone1} {note.zone2} '
        f'"{note.headline}" --description "..."',
    )
    return rejection_.build(
        kind="type_not_recognized",
        what=what,
        options=tuple(options),
        command=command,
    )


def validate_fields(note: Note) -> Rejection | None:
    """Reject missing required fields or fields the type does not allow."""
    type_spec = TYPES.get(note.type)
    if type_spec is None:
        return None  # unknown type: _validate_type rejects it

    present = _present_fields(note)
    missing_required = sorted(type_spec.required_fields - present)
    not_allowed = sorted(present - type_spec.allowed_fields)

    if not missing_required and not not_allowed:
        return None

    lines = []
    if missing_required:
        lines.append(
            f"Faltan campos obligatorios para el tipo {note.type}: "
            f"{', '.join(missing_required)}"
        )
    if not_allowed:
        lines.append(
            f"Estos campos no existen para el tipo {note.type}: "
            f"{', '.join(not_allowed)}"
        )
    what = f"el campo no encaja con el tipo {note.type}"
    # One placeholder per required field, so the relaunch command does not bounce again.
    required = "".join(
        f' --{field} "..."' for field in sorted(type_spec.required_fields - {"description"})
    )
    command = (
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{required} --description "..."',
    )
    return rejection_.build(
        kind="field_not_allowed", what=what, options=tuple(lines), command=command
    )


def _present_fields(note: Note) -> frozenset[str]:
    """Optional fields `note` really carries; blank free text does not count."""
    present = {"description"} if note.description and note.description.strip() else set()
    if note.why is not None and note.why.strip():
        present.add("why")
    if note.keys:
        present.add("keys")
    if note.origin:
        present.add("origin")
    if note.replaces is not None and note.replaces != "none":  # none = coexist, any type
        present.add("replaces")
    if note.awaits is not None and note.awaits.strip():
        present.add("awaits")
    if note.issue is not None:
        present.add("issue")
    if note.quote is not None and note.quote.strip():
        present.add("quote")
    return frozenset(present)


def normalize_keys(keys: tuple[str, ...], headline: str) -> tuple[str, ...]:
    """Canonical keys, at most `MAX_KEYS`, none already in the headline. Writes nothing."""
    headline_words = frozenset(_WORD_RE.findall(headline.lower()))
    normalized: list[str] = []
    seen: set[str] = set()
    for key in keys:
        canonical = MARKER_KEYS.get(key.lower(), key.lower())
        if canonical in seen or canonical in headline_words:
            continue
        seen.add(canonical)
        normalized.append(canonical)
        if len(normalized) >= MAX_KEYS:
            break
    return tuple(normalized)


def validate_pain_question(note: Note, stops: str | None) -> Rejection | None:
    """For M and R: require the pain answer `stops` and check it matches the type."""
    if note.type not in ("M", "R"):
        return None

    if stops is None:
        what = "falta una respuesta"
        options = (
            "Toda M y toda R contestan lo mismo antes de entrar:",
            "",
            f"  {PAIN_QUESTION}",
            "",
            "  si  ->  es un muro. Entra como R y sale en TODOS los arranques.",
            "  no  ->  es un hecho. Entra como M y se lee cuando se busca su zona.",
        )
        command = (  # carries origin/replaces/awaits already given
            f'gitmem note M --zones {note.zone1} {note.zone2} '
            f'"{note.headline}"{description_flag(note)}{carry_answer_flags(note, skip=frozenset({"--stops"}))} --stops no',
            f'gitmem note R --zones {note.zone1} {note.zone2} '
            f'"{note.headline}"{description_flag(note)}{carry_answer_flags(note, skip=frozenset({"--stops"}))}'
            f'{why_flag(note, "R")} --stops yes',
        )
        return rejection_.build(
            kind="missing_pain_answer", what=what, options=options, command=command
        )

    expected_type = "R" if stops == _STOPS_YES else "M"
    if note.type == expected_type:
        return None

    answer_word = "si" if expected_type == "R" else "no"
    kind_word = "muro" if expected_type == "R" else "hecho"
    what = (
        f'contestaste "{answer_word}" a "{PAIN_QUESTION}" -- entonces es un '
        f"{kind_word}, entra como {expected_type}, no {note.type}"
    )
    options = (
        f"{PAIN_QUESTION} -> {answer_word}",
        f"eso corresponde al tipo {expected_type}, no {note.type}.",
    )
    command = (  # carries origin/replaces/awaits already given
        f'gitmem note {expected_type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{description_flag(note)}{carry_answer_flags(note, skip=frozenset({"--stops"}))}'
        f'{why_flag(note, expected_type)} --stops {stops}',
    )
    return rejection_.build(
        kind="pain_answer_wrong_type", what=what, options=options, command=command
    )


def can_be_replaced(note: Note) -> bool:
    """Only a D, M or R is replaced by id; an I, X, Q or B never is."""
    return takes(note.type, "replaces")


def validate_replacement(
    note: Note, existing_in_zone: tuple[Note, ...]
) -> Rejection | None:
    """Reject a note that overlaps existing ones in its zone when `--replaces` is missing."""
    if note.replaces is not None:
        return None

    candidates = similar.find_overlapping(
        note, existing_in_zone, threshold=SIMILARITY_THRESHOLD
    )
    if not candidates:
        return None

    what = f"esto pisa a algo que ya esta escrito en [{note.zone1}][{note.zone2}]"
    options = [
        f"Tu nota comparte terreno con estas de [{note.zone1}][{note.zone2}]. "
        "Di que pasa con ellas antes de entrar:",
        "",
    ]
    for candidate in candidates:
        options.append(
            f"  {candidate.id}   {candidate.timestamp.date().isoformat()}   "
            f"{candidate.headline}"
        )
        if candidate.keys:
            options.append(f"          keys: {', '.join(candidate.keys)}")
        if candidate.why:
            options.append(f"          Why: {candidate.why}")
        options.append("")
    # Only the exits and fields the type accepts.
    by_id = takes(note.type, "replaces")
    options.extend(
        [
            "Tres salidas, y solo tres:" if by_id else "Dos salidas, y solo dos:",
            "",
            *(["  la sustituye   --replaces <id>       la vieja sale del indice a ARCHIVED"] if by_id else []),
            "  conviven       --replaces none       las dos siguen vigentes",
            "  es duplicado   no la guardes; si hay que matizar, cierra la vieja:",
            '                 gitmem remove <id> "..." --restriction no',
        ]
    )
    replaceable = [c.id for c in candidates if can_be_replaced(c)]
    answer = replaceable[0] if by_id and replaceable else "none"
    command = (  # only what was given and the type takes: pasted as printed, it saves
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{carry_accepted_flags(note)}{description_flag(note)} --replaces {answer}',
    )
    return rejection_.build(
        kind="overlapping_note", what=what, options=tuple(options), command=command
    )


def validate_distillation(note: Note, is_distillation: bool) -> Rejection | None:
    """Reject a distillation without `origin` sources."""
    if not is_distillation or note.origin:
        return None

    what = "una destilacion sin fuentes no es una destilacion"
    options = (
        "Compactar es decir DE QUE. Sin Origin no hay forma de volver a lo que",
        "resumiste ni de comprobar si lo resumiste bien.",
        "",
        "Pon los hashes v1 de los que sale, separados por espacios.",
    )
    command = (
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}" --description "..." --origin <hash1> <hash2> ...',
    )
    return rejection_.build(
        kind="distillation_without_sources",
        what=what,
        options=options,
        command=command,
    )


def validate_incident_close_question(note: Note, restriction: str | None) -> Rejection | None:
    """Ask whether closing an incident (I) gives rise to a restriction."""
    if note.type != "I" or restriction is not None:
        return None

    what = f"{note.id} no se cierra sin contestar esto"
    options = (
        "¿de esta cicatriz sale muro?",
        "",
        f"  {note.id}  [{note.zone1}][{note.zone2}]  {note.headline}",
        f"         causa: {note.description}",
        "",
        "  sí  →  nace una R en esta misma zona y sale en todos los arranques",
        "  no  →  se cierra sin más; nadie vuelve a enterarse",
    )
    command = (
        f'gitmem remove {note.id} "..." --restriction no',
        f'gitmem remove {note.id} "..." --restriction new '
        f'--restriction-text "..." --why "..."',
    )
    return rejection_.build(
        kind="incident_close_question", what=what, options=options, command=command
    )


def is_wip(subject: str) -> bool:
    """True if `subject` is a WIP checkpoint (`[WIP] 🚧` or the older bare emoji)."""
    return subject.startswith((f"{_WIP_PREFIX} {_WIP_MARKER}", _WIP_MARKER))

