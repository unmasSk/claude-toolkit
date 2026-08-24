"""Normalizacion de texto compartida DENTRO de `lib/memory/` -- minusculas
y sin acentos, un unico punto para `zones.py::normalize`, `similar.py` y
`rules_similarity.py`.

`lib/memory/` no importa nada fuera de la biblioteca estandar, y nada de
fuera importa de aqui [test_boundary.py]. `lib/checklist_state.py`
necesita la misma cuenta pero, por esa frontera, NO importa esta pieza:
mantiene su propia copia en `normalize_box_text()` -- duplicacion
consciente, no descuido.
"""

import unicodedata


def normalize_text(value: str) -> str:
    """Minusculas + sin acentos: `casefold()` (no `lower()`) sobre el
    texto NFKD-descompuesto tras descartar los caracteres combinantes.
    Entrada no-`str` devuelve cadena vacia en vez de reventar.
    """
    if not isinstance(value, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return without_accents.casefold()
