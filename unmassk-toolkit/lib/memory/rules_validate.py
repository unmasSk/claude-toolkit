"""Validation of a rule's kind, text and quote for `rules.py`; builds rejections, never writes."""

import rejection
from model import Rejection


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
    """Rejection for a kind that is blank or holds a newline (it would split the rule line)."""
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


def _reject_missing_quote(text: str, kind: str | None, replaces: str | None) -> Rejection:
    """Rejection for a blank quote; the relaunch command keeps the given --replaces and --kind."""
    what = "la regla no lleva ni una cita literal ni --quote none explicito"
    options = (
        f'  "{text}"',
        "",
        "Toda regla se guarda con las palabras REALES de quien la dijo, o con",
        "--quote none si es Claude quien se la deja a si mismo y el",
        "propietario no dijo nada -- asi se colo una correccion real del",
        'propietario guardada como [claude] solo para saltarse la cita.',
    )
    base = f'gitmem rule "{text}"'
    if replaces is not None:
        base += f' --replaces "{replaces}"'
    if kind is not None:
        base += f" --kind {kind}"
    command = (
        f'{base} --quote "<sus palabras literales>"',
        f"{base} --quote none",
    )
    return rejection.build(
        kind="rule_missing_quote", what=what, options=options, command=command
    )


def reject_invalid_text(text: str) -> Rejection:
    """Rejection for a rule text that is blank or holds a newline."""
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


_QUOTE_MAX_CHARS = TEXT_MAX_CHARS


def _reject_quote_newline(quote: str) -> Rejection:
    """Rejection for a quote with a newline (the quote lives on the rule's line)."""
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
    """Rejection for a quote over `_QUOTE_MAX_CHARS`."""
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


def reject_rule_not_found(text: str, kind: str) -> Rejection:
    """Rejection when no `[kind]` rule has exactly `text` (quote excluded)."""
    what = f'no existe ninguna regla [{kind}] con ese texto exacto: "{text}"'
    options = (
        f'  "{text}"',
        "",
        f"No se encontro ninguna linea guardada bajo [{kind}] cuyo texto (sin la",
        "cita) case caracter a caracter con ese. Puede que el texto no sea",
        "identico, o que la regla exista bajo el otro --kind.",
    )
    command = ("gitmem rule",)
    return rejection.build(
        kind="rule_not_found", what=what, options=options, command=command
    )


def validate_quote(
    quote, text: str, kind: str | None = None, replaces: str | None = None
) -> tuple[bool, Rejection | None]:
    """Return `(quote_has_content, rejection)`; rejection is None when the quote is absent, "none" or valid.

    Applies to every kind alike.
    """
    quote_mentioned = quote is not QUOTE_NOT_GIVEN
    quote_blank = quote_mentioned and (quote is None or not quote.strip())
    quote_is_explicit_none = (
        quote_mentioned and not quote_blank and quote.strip().lower() == _QUOTE_NONE_LITERAL
    )
    if quote_mentioned and quote_blank and not quote_is_explicit_none:
        return False, _reject_missing_quote(text, kind, replaces)

    quote_has_content = quote_mentioned and not quote_blank and not quote_is_explicit_none
    if quote_has_content and "\n" in quote:
        return quote_has_content, _reject_quote_newline(quote)
    if quote_has_content and len(quote) > _QUOTE_MAX_CHARS:
        return quote_has_content, _reject_quote_too_long(quote)
    return quote_has_content, None
