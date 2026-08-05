"""Rechazos de la aduana, un texto con dos salidas -- contrato en
docs/memoria-v2/PIEZAS.md Sec.7.4.

De que salida se deriva: de los diez rechazos [TEXTOS.md Sec.1] (el
1.8, key marcadora mal escrita, no es rechazo -- TEXTOS.md lo titula
literalmente "aviso al guardar" y PIEZAS.md Sec.7.5 lo confirma: nueve
mas uno son diez rechazos de verdad). Los diez comparten la misma
anatomia -- que ha pasado, las opciones, el comando exacto para
relanzar -- y es eso lo que hace que esta pieza sea una sola en vez de
diez: no conoce el contenido real de ningun rechazo (eso lo decide
`validator.py`, capa 2, que todavia no existe), solo sabe dar forma a
esos tres elementos ya redactados por quien la llama.

Que NO hace: no decide si algo se rechaza -- eso es `validator.py`.
Esta pieza nunca ve una nota, una zona ni un id; solo el texto que otro
ya redacto.

Mismo objeto, dos renderizados: `render_terminal` (lo imprime el
generador cuando rechaza en proceso) y `render_hook_block` (lo emite
`hooks/customs.py` al bloquear) comparten un unico cuerpo de render.
Si fueran dos textos escritos por separado, se separarian con el
tiempo -- exactamente el fallo que el contrato quiere evitar ("que la
aduana diga una cosa y el generador otra").

Sin codigos de color (decision cerrada del propietario, PIEZAS.md
Sec.5.2, la misma que rige `emojis.py`): quien lee el bloque del hook
es Claude, no una terminal, y un codigo ANSI ahi es ruido en medio del
texto que hay que leer para contestar. El unico adorno visual es el
emoji "rechazado", el mismo que usan las diez plantillas literales de
TEXTOS.md Sec.1 (1.1 a 1.7 y 1.9 a 1.11, verificado uno por uno) y que
ya es `emojis.TYPE_EMOJI["B"]` -- consistente con el resto del sistema,
no inventado aqui. No se importa `emojis.py` solo por ese caracter
(evita una dependencia para un unico glifo fijo); si algun dia
`TYPE_EMOJI["B"]` cambia, este modulo tendria que actualizarse a mano
-- coste aceptado a cambio de no crear una dependencia de una linea.

El comando de relanzamiento viaja BYTE A BYTE: `build()` no le toca un
caracter (ni a `command`, ni a `what`, ni a `options`), y `render_*`
solo los concatena con separadores propios -- comillas simples, dobles
o escapadas incluidas. Copiar el comando del bloqueo y pegarlo en el
shell tiene que funcionar a la primera.
"""

from model import Rejection

_EXPECTED_PARTS = frozenset({"what", "options", "command"})


def build(kind: str, **parts) -> Rejection:
    """Empaqueta un rechazo ya redactado en un `Rejection`.

    `kind` es un identificador libre (PIEZAS.md Sec.7.4 no fija un
    enum) -- esta pieza no lo interpreta ni lo guarda, solo lo usa para
    nombrar el error si `parts` viene mal formado; quien decide que
    `kind` corresponde a que texto es `validator.py`.

    `parts` espera exactamente tres: `what` (que ha pasado, str),
    `options` (las opciones, tuple de str) y `command` (uno o dos
    comandos de relanzamiento, tuple de str -- el rechazo del cierre de
    incidencia, TEXTOS Sec.1.10, ofrece dos segun la respuesta). Un
    part que falta o que sobra revienta con `TypeError` nombrando cual
    -- rojo hablador, no un rechazo silenciosamente incompleto.
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
    """Cuerpo compartido de los dos renderizados -- ver docstring del modulo.

    Una sola funcion privada para las dos salidas publicas: la unica
    forma de que "mismo objeto, dos renderizados" sea una garantia
    estructural y no una promesa que dos implementaciones separadas
    pueden dejar de cumplir con el tiempo.
    """
    lines = [f"⛔ {r.title}", "", r.body]
    if r.relaunch:
        lines.append("")
        lines.append("Relanza:")
        for command in r.relaunch:
            lines.append(f"  {command}")
    return "\n".join(lines)


def render_terminal(r: Rejection) -> str:
    """El que imprime el generador cuando rechaza en proceso."""
    return _render(r)


def render_hook_block(r: Rejection) -> str:
    """El que devuelve `hooks/customs.py` al bloquear."""
    return _render(r)
