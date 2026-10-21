"""Shapes an already-written customs rejection (what, options, relaunch command) into text.

One renderer serves the terminal and the hook block; the parts are passed through byte for byte.
"""

from model import Rejection

_EXPECTED_PARTS = frozenset({"what", "options", "command"})


def build(kind: str, **parts) -> Rejection:
    """Pack a written rejection into a `Rejection`.

    `parts` must be exactly `what` (str), `options` (tuple of str) and `command`
    (tuple of str); a missing or extra part raises TypeError, an empty one ValueError.
    `kind` only names the error.
    """
    unknown = sorted(set(parts) - _EXPECTED_PARTS)
    if unknown:
        raise TypeError(f"build({kind!r}) recibio parts que no reconoce: {unknown}")

    missing = sorted(_EXPECTED_PARTS - set(parts))
    if missing:
        raise TypeError(
            f"build({kind!r}) necesita estos parts y no los recibio: {missing}"
        )

    empty = sorted(name for name in _EXPECTED_PARTS if not parts[name])
    if empty:
        raise ValueError(
            f"build({kind!r}) recibio estos parts sin valor real: {empty} -- "
            "un rechazo sin ellos sale mutilado en silencio (titular vacio, "
            "seccion de opciones o de relanzamiento desaparecida)"
        )

    return Rejection(
        title=parts["what"],
        body="\n".join(parts["options"]),
        relaunch=tuple(parts["command"]),
    )


def _render(r: Rejection) -> str:
    """Shared body of both public renderers."""
    lines = [f"⛔ {r.title}", "", r.body]
    if r.relaunch:
        lines.append("")
        lines.append("Relanza:")
        for command in r.relaunch:
            lines.append(f"  {command}")
    return "\n".join(lines)


def render_terminal(r: Rejection) -> str:
    """Text printed by the note writer when it rejects in process."""
    return _render(r)


def render_hook_block(r: Rejection) -> str:
    """Text returned by `hooks/customs.py` when it blocks."""
    return _render(r)
