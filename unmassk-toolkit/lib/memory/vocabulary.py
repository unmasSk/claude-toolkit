"""Closed data of the memory system: the single copy of everything the validator checks and rejections quote.

Data only, no functions. Every field names its real reader in FIELDS; the asserts below fail the import if a type lacks its index file or name."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class _FieldSpec:
    """A note body field and the function that really reads it."""

    reader: str  # "module.function", module relative to lib/memory/


@dataclass(frozen=True)
class _TypeSpec:
    """One of the seven note types: its description and fields."""

    description: str  # the line shown in the "unknown type" rejection
    required_fields: frozenset
    allowed_fields: frozenset


# Max headline length (the headline text, not the whole line).
HEADLINE_MAX = 80

# Max synonyms in Keys.
MAX_KEYS = 5

# Field -> its reader: a public function really called from outside its module.
FIELDS = MappingProxyType(
    {
        "why": _FieldSpec(reader="report_render.render_zone"),
        "keys": _FieldSpec(reader="query.by_word"),
        "description": _FieldSpec(reader="report_render.render_zone"),
        "origin": _FieldSpec(reader="clusters.group"),
        "replaces": _FieldSpec(reader="clusters.group"),
        "awaits": _FieldSpec(reader="boot.render"),
        "issue": _FieldSpec(reader="health.plans_unreflected"),
        "quote": _FieldSpec(reader="report_render_note.render_note"),
        "context": _FieldSpec(reader="context.latest"),
    }
)

# The seven note types with their required and allowed fields.
TYPES = MappingProxyType(
    {
        "D": _TypeSpec(
            description="se eligió entre opciones",
            required_fields=frozenset({"description", "why"}),
            allowed_fields=frozenset(
                {"description", "why", "keys", "replaces", "origin", "issue"}
            ),
        ),
        "M": _TypeSpec(
            description="un hecho estable del proyecto",
            required_fields=frozenset({"description"}),
            allowed_fields=frozenset(
                {"description", "keys", "origin", "replaces", "issue"}
            ),
        ),
        "R": _TypeSpec(
            description="un muro: saltarlo rompe algo",
            required_fields=frozenset({"description"}),
            allowed_fields=frozenset(
                {"description", "why", "keys", "origin", "replaces", "issue"}
            ),
        ),
        "Q": _TypeSpec(
            description="pregunta abierta, sin respuesta todavía",
            required_fields=frozenset({"description"}),
            allowed_fields=frozenset({"description", "keys", "issue", "quote"}),
        ),
        "X": _TypeSpec(
            description="se estudió y se descartó",
            required_fields=frozenset({"description"}),
            allowed_fields=frozenset(
                {"description", "why", "keys", "origin", "issue"}
            ),
        ),
        "I": _TypeSpec(
            description="se rompió algo: causa y qué se hizo",
            required_fields=frozenset({"description"}),
            allowed_fields=frozenset({"description", "why", "keys", "issue", "quote"}),
        ),
        "B": _TypeSpec(
            description="pendiente de fuera; bloquea",
            required_fields=frozenset({"description", "awaits"}),
            allowed_fields=frozenset({"description", "awaits", "keys", "issue"}),
        ),
    }
)

# Marker variant -> canonical form; canonical forms map to themselves so normalising is idempotent.
MARKER_KEYS = MappingProxyType(
    {
        "antipattern": "antipattern",
        "anti-pattern": "antipattern",
        "antipatron": "antipattern",
        "antipatrón": "antipattern",
        "security": "security",
        "seguridad": "security",
        "sec": "security",
        "performance": "performance",
        "perf": "performance",
        "rendimiento": "performance",
        "legal": "legal",
        "legales": "legal",
        "compliance": "legal",
    }
)

# Zones that describe how we work, not the product.
ZONE_BLACKLIST = frozenset({"claude", "user", "session", "project", "workflow"})

# Ambiguous zone word -> its two resolutions.
ILLEGAL_WORDS = MappingProxyType({"audit": ("registro", "codeaudit")})

# The pain question, the single copy in the system.
PAIN_QUESTION = "¿puede costar datos, horas o producción caída?"

# Similarity above which two notes count as the same; shared by validator.py and rules.py.
SIMILARITY_THRESHOLD = 0.5

# The eight index files, and only these.
INDEX_FILES = (
    "DECISIONS.md",
    "MEMOS.md",
    "RESTRICTIONS.md",
    "QUESTIONS.md",
    "INCIDENTS.md",
    "DISCARDED.md",
    "BLOCKED.md",
    "ARCHIVED.md",
)

# Note type -> its index file; ARCHIVED.md is written only by replace()/close().
TYPE_INDEX_FILES = MappingProxyType(
    {
        "D": "DECISIONS.md",
        "M": "MEMOS.md",
        "R": "RESTRICTIONS.md",
        "Q": "QUESTIONS.md",
        "I": "INCIDENTS.md",
        "X": "DISCARDED.md",
        "B": "BLOCKED.md",
    }
)

assert set(TYPE_INDEX_FILES) == set(TYPES), (
    "vocabulary.py: TYPE_INDEX_FILES ha quedado desincronizado de TYPES -- "
    "todo tipo del vocabulario cerrado necesita su fichero de indice "
    "declarado aqui"
)

# Spanish name of each type, for the by-id report header ("D-030 · decisión · vigente").
TYPE_SPANISH_NAME = MappingProxyType(
    {
        "D": "decisión",
        "M": "memo",
        "R": "restricción",  # not confirmed by any text or test
        "Q": "pregunta",
        "X": "descarte",
        "I": "incidencia",
        "B": "bloqueante",
    }
)

assert set(TYPE_SPANISH_NAME) == set(TYPES), (
    "vocabulary.py: TYPE_SPANISH_NAME ha quedado desincronizado de TYPES -- "
    "todo tipo del vocabulario cerrado necesita su nombre en castellano "
    "declarado aqui"
)
