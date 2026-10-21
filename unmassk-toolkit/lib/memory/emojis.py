"""Emojis of the memory system: three immutable maps, data only.

TYPE_EMOJI per note type, CHANNEL_EMOJI per commit channel, SECTION_EMOJI per report section header.
"""

from types import MappingProxyType

TYPE_EMOJI = MappingProxyType(
    {
        "D": "🧭",  # decision
        "M": "📌",  # memo
        "R": "⚠️",  # restriction (wall)
        "Q": "❓",  # open question
        "X": "🚫",  # discard -- permanent
        "I": "🔥",  # incident
        "B": "⛔",  # blocker
    }
)

CHANNEL_EMOJI = MappingProxyType(
    {
        "next": "⏩️",  # [NEXT] headline; variation selector makes it render as emoji
        "rule": "🧠",  # remember -- rule saved as an empty commit
        "wip": "🚧",  # checkpoint without questions (bin/memory/wip.py)
    }
)

SECTION_EMOJI = MappingProxyType(
    {
        "restricciones": "⚠️",  # "RESTRICCIONES" header
        "bloqueantes": "⛔",  # "BLOQUEANTES" header
        "decisiones": "🧭",  # "DECISIONES" header
        "memos": "📌",  # "MEMOS" header
        "incidencias": "🔥",  # "INCIDENCIAS" header
        "preguntas": "❓",  # "LO QUE ESPERA DE TI" header
    }
)
