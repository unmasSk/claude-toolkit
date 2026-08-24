"""Validacion de los tres campos de `add()` (`kind`/`text`/`quote`) --
partido de `rules.py` por tamano. Nunca toca git ni el fichero -- cada
funcion rebota sin escribir nada, siempre ANTES de que `add()` toque
disco.

Nombres sin guion bajo (`TEXT_MAX_CHARS`, `reject_too_long`,
`reject_invalid_kind`, `reject_invalid_text`, `validate_quote`,
`QUOTE_NOT_GIVEN`) cruzan a `rules.py`, que los llama desde `add()`. Los
que solo se llaman entre si aqui mismo se quedan privados.

Imports planos entre hermanos. `lib/memory/` no importa nada fuera de la
biblioteca estandar de Python.
"""

import rejection
from model import Rejection


# Tope de Sec.9.7 -- constante propia, no vocabulary.HEADLINE_MAX: ese
# tope (80) es del titular de una Note: dominio distinto, valor distinto,
# declarado explicitamente como "fuera del sistema" [Sec.9.7].
TEXT_MAX_CHARS = 200


def reject_too_long(text: str) -> Rejection:
    length = len(text)
    what = f"la regla tiene {length} caracteres y el tope son {TEXT_MAX_CHARS}"
    options = (
        f'  "{text}"',
        "",
        "Una regla es un titular sin cuerpo -- lo que no cabe en el tope no",
        "llega a leerse nunca. Si mezcla varias cosas, son varias reglas.",
    )
    command = (f'gitmem rule "<hasta {TEXT_MAX_CHARS} caracteres>"',)
    return rejection.build(
        kind="rule_too_long", what=what, options=options, command=command
    )


def reject_invalid_kind(kind: str) -> Rejection:
    """Rebota ANTES de tocar git o el fichero, mismo criterio que
    `reject_invalid_text` aplicado a `kind`: un salto de linea parte la
    linea escrita en dos al releer y ninguna vuelve a casar con
    `_RULE_LINE_RE` -- la regla entera queda invisible.
    """
    if "\n" in kind:
        what = "el tipo de la regla lleva un salto de linea"
        options = (
            f"  {kind!r}",
            "",
            "El fichero de reglas es una linea por regla. Un salto de linea en el",
            "tipo rompe ese formato igual que ya lo rompia en el texto: al",
            "releer, la linea se parte en dos y ninguna de las dos vuelve a",
            "reconocerse como regla -- la regla entera queda invisible.",
        )
    else:
        what = "el tipo de la regla esta vacio"
        options = (
            "Un tipo en blanco (o solo espacios) no identifica quien la escribio.",
        )
    command = ('gitmem rule "<texto>" --kind <user|claude>',)
    return rejection.build(
        kind="rule_invalid_kind", what=what, options=options, command=command
    )


QUOTE_NOT_GIVEN = object()


_QUOTE_NONE_LITERAL = "none"


def _reject_missing_quote(text: str) -> Rejection:
    """Rebota ANTES de tocar git o el fichero. Exige cita para AMBOS
    `kind` por igual -- `--quote none` explicito es la unica salida sin
    cita real (Claude se deja una nota a si mismo, el propietario no dijo
    nada). Dispara solo cuando quien llama SI menciono `quote` y viene en
    blanco y no es `"none"` -- nunca para un llamador que ni siquiera
    pasa el parametro (`add(text, kind)`).
    """
    what = "la regla no lleva ni una cita literal ni --quote none explicito"
    options = (
        f'  "{text}"',
        "",
        "Toda regla se guarda con las palabras REALES de quien la dijo, o con",
        "--quote none si es Claude quien se la deja a si mismo y el",
        "propietario no dijo nada -- asi se colo una correccion real del",
        'propietario guardada como [claude] solo para saltarse la cita.',
    )
    command = (
        f'gitmem rule "{text}" --quote "<sus palabras literales>"',
        f'gitmem rule "{text}" --quote none',
    )
    return rejection.build(
        kind="rule_missing_quote", what=what, options=options, command=command
    )


def reject_invalid_text(text: str) -> Rejection:
    """Rebota ANTES de tocar git o el fichero. Dos casos: un salto de
    linea rompe el formato de una-linea-por-regla (al releer solo se
    recupera el trozo anterior al salto); vacio o solo espacios no dice
    nada.
    """
    if "\n" in text:
        what = "la regla lleva un salto de linea"
        options = (
            f"  {text!r}",
            "",
            "El fichero de reglas es una linea por regla. Un salto de linea rompe",
            "ese formato: al releer, solo se recupera el trozo anterior al salto y",
            "el resto queda huerfano e invisible -- el mismo fallo ya arreglado en",
            "el formato de las notas, aqui sin forma de plegarlo.",
        )
    else:
        what = "la regla esta vacia"
        options = (
            "Una regla en blanco (o solo espacios) no dice nada.",
        )
    command = (f'gitmem rule "<hasta {TEXT_MAX_CHARS} caracteres, una sola linea>"',)
    return rejection.build(
        kind="rule_invalid_text", what=what, options=options, command=command
    )


# Reusa el mismo numero que `TEXT_MAX_CHARS`: la cita vive en la MISMA
# linea fisica que el texto y es, como el, una frase citada, no un
# parrafo -- no hay motivo para un segundo tope distinto.
_QUOTE_MAX_CHARS = TEXT_MAX_CHARS


def _reject_quote_newline(quote: str) -> Rejection:
    """Rebota ANTES de tocar git o el fichero: la cita se escribe DENTRO
    de la misma linea fisica que el texto (sufijo ` — «<cita>»`), y un
    salto de linea en ella partiria la linea entera al releer.
    """
    what = "la cita lleva un salto de linea"
    options = (
        f"  {quote!r}",
        "",
        "El fichero de reglas es una linea por regla, y la cita viaja dentro de",
        "esa misma linea. Un salto de linea en la cita rompe el formato igual",
        "que ya lo rompia en el texto -- la regla ENTERA queda invisible al",
        "releer, no solo la cita.",
    )
    command = (
        f'gitmem rule "<texto>" --quote "<cita, hasta {_QUOTE_MAX_CHARS} caracteres, una sola linea>"',
    )
    return rejection.build(
        kind="rule_quote_newline", what=what, options=options, command=command
    )


def _reject_quote_too_long(quote: str) -> Rejection:
    """Rebota ANTES de tocar git o el fichero, mismo criterio que
    `reject_too_long` aplicado a la cita.
    """
    length = len(quote)
    what = f"la cita tiene {length} caracteres y el tope son {_QUOTE_MAX_CHARS}"
    options = (
        f'  "{quote}"',
        "",
        "La cita viaja en la misma linea fisica que el texto de la regla -- lo",
        "que no cabe en el tope no llega a leerse nunca.",
    )
    command = (f'gitmem rule "<texto>" --quote "<hasta {_QUOTE_MAX_CHARS} caracteres>"',)
    return rejection.build(
        kind="rule_quote_too_long", what=what, options=options, command=command
    )


def validate_quote(quote, text: str) -> tuple[bool, Rejection | None]:
    """Toda la logica de `quote` que `add()` necesita antes de tocar git
    o el fichero. Devuelve `(quote_has_content, rejection)` -- `rejection`
    es `None` si la cita pasa (ausente, `--quote none` explicito, o una
    cita real dentro de los limites). Unico llamador real: `add()`.

    Kind-agnostic: exigir la cita solo para `kind == "user"` dejaria un
    hueco (una regla del propietario guardada como `[claude]` se
    saltaria la cita).
    """
    quote_mentioned = quote is not QUOTE_NOT_GIVEN
    quote_blank = quote_mentioned and (quote is None or not quote.strip())
    quote_is_explicit_none = (
        quote_mentioned and not quote_blank and quote.strip().lower() == _QUOTE_NONE_LITERAL
    )
    if quote_mentioned and quote_blank and not quote_is_explicit_none:
        return False, _reject_missing_quote(text)

    quote_has_content = quote_mentioned and not quote_blank and not quote_is_explicit_none
    if quote_has_content and "\n" in quote:
        return quote_has_content, _reject_quote_newline(quote)
    if quote_has_content and len(quote) > _QUOTE_MAX_CHARS:
        return quote_has_content, _reject_quote_too_long(quote)
    return quote_has_content, None
