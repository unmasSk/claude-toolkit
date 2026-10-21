"""Shared text normalisation for `lib/memory/`: lowercase, no accents."""

import unicodedata


def normalize_text(value: str) -> str:
    """Casefold `value` and strip its accents; non-`str` input returns ""."""
    if not isinstance(value, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return without_accents.casefold()
