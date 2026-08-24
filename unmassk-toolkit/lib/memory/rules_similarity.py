"""Reconocimiento de una linea de regla ya escrita, y deteccion de
casi-duplicados por texto -- partido de `rules.py` por tamano.

`iter_rule_texts()`/`strip_quote_suffix()` cruzan a `health.py` ademas de
a `rules.py` -- se quedan publicos. `similar_existing()` llama a
`read_all()` (en `rules_commit.py`, no en `rules.py`) para que esta
llamada nunca tenga que importar DESDE la fachada.

Duplicacion deliberada frente a `similar.py`: ese modulo calcula
solapamiento de vocabulario pero esta atado a `Note` (headline +
description + why + keys); un remember no tiene ninguno de esos campos.
`_tokenize`/`_jaccard` son la version minima sin esa forma.

Que NO hace: no valida zonas, no pasa por `validator.py`, no decide
semantica ("dos frases distintas que dicen lo mismo") -- compara solo
por texto.
"""

import re
from typing import NamedTuple

import textnorm
from rules_commit import read_all
from vocabulary import SIMILARITY_THRESHOLD


_WORD_RE = re.compile(r"\w+", re.UNICODE)

# Reconoce una linea de regla ya escrita en el fichero: "[remember][kind]
# <emoji> <texto>". El emoji se casa con \S+ (no con el literal fijo) por
# el mismo motivo que format._SUBJECT_RE usa \S+ para el suyo: no atar el
# regex a un caracter exacto que vive en otro modulo.
_RULE_LINE_RE = re.compile(r"^\[remember\]\[(?P<kind>[^\]]+)\]\s+\S+\s+(?P<text>.+)$")


def _tokenize(text: str) -> frozenset[str]:
    """Minusculas y sin acentos (``textnorm.normalize_text``, compartida
    con `zones.py`/`similar.py` -- ver el docstring de `textnorm.py`)
    antes de partir en palabras."""
    return frozenset(_WORD_RE.findall(textnorm.normalize_text(text)))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Interseccion sobre union. Dos vocabularios vacios no son
    "identicos" -- son datos ausentes; 0.0, nunca division por cero."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def iter_rule_texts(content: str) -> tuple[str, ...]:
    """Los textos (sin prefijo `[remember][kind] emoji `) de cada linea de
    regla reconocida en `content`. Una linea que no case se salta en
    silencio -- el UNICO reconocimiento de "esto es una linea de regla"
    en todo el sistema.
    """
    texts = []
    for line in content.splitlines():
        match = _RULE_LINE_RE.match(line)
        if match is not None:
            texts.append(match.group("text"))
    return tuple(texts)


class _RuleMatch(NamedTuple):
    """Una candidata de `similar_existing()`: dueno (`kind`) + texto --
    detalle privado de este modulo, no una forma del sistema.
    """

    kind: str
    text: str


def _iter_rule_lines(content: str) -> tuple[tuple[str, str], ...]:
    """Como `iter_rule_texts()` pero conservando el `kind` (dueno) de
    cada linea -- uso exclusivo de `similar_existing()`. Reutiliza el
    mismo `_RULE_LINE_RE`, nunca una segunda copia del patron.
    """
    lines = []
    for line in content.splitlines():
        match = _RULE_LINE_RE.match(line)
        if match is not None:
            lines.append((match.group("kind"), match.group("text")))
    return tuple(lines)


# Separador de la cita dentro de la linea escrita -- em dash + guillemets,
# nunca comillas rectas (encargo 2026-08-23): "no te enrolles, tio" con
# comillas rectas se confunde con una comilla dentro del propio texto de
# la regla; el em dash + guillemets no aparece en ningun texto de regla
# real hasta ahora y separa visiblemente las dos partes al leer.
_QUOTE_SUFFIX_RE = re.compile(r"^(?P<text>.*) — «(?P<quote>.*)»$")


def strip_quote_suffix(text: str) -> str:
    """El texto de una linea ya escrita SIN la parte de cita (` — «...»`),
    si la lleva -- el parecido (Jaccard) y la candidata que se ensena en
    el rechazo se miden solo sobre el texto de la regla, nunca sobre la
    cita. Tambien la usa `health.coherence_rules()` para que una cita
    distinta no cuente como discrepancia de contenido.

    `iter_rule_texts()` NO usa esto y sigue devolviendo la linea con la
    cita incluida a proposito.
    """
    match = _QUOTE_SUFFIX_RE.match(text)
    if match is not None:
        return match.group("text")
    return text


def similar_existing(text: str) -> tuple[_RuleMatch, ...]:
    """Las reglas ya guardadas que se parecen a `text`, por texto -- se
    ensena antes de anadir. El contraste por significado no se
    construye, solo texto.

    Cada candidata es una pareja `(kind, text)`, nunca el texto solo:
    una regla `[user]` y una `[claude]` con el mismo texto no son la
    misma regla, y el rechazo necesita mostrar de quien es cada una.
    """
    candidate = _tokenize(text)
    matches = []
    for kind, existing_text in _iter_rule_lines(read_all()):
        # La cita nunca entra en el parecido ni en lo que se devuelve.
        stripped_text = strip_quote_suffix(existing_text)
        if _jaccard(candidate, _tokenize(stripped_text)) >= SIMILARITY_THRESHOLD:
            matches.append(_RuleMatch(kind, stripped_text))
    return tuple(matches)
