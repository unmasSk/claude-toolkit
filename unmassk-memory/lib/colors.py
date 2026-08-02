"""Colores ANSI y emojis del sistema de memoria v2.

Los mensajes que ve el usuario (rechazos de la aduana, informes, el menu
del arranque) usan estas constantes para dar formato en terminal.

EMOJIS mapea cada tipo de nota a su simbolo. La clave es el codigo de una
letra que ya usa la linea de comandos (``gitmem note D ...``), no el
nombre largo -- es un identificador mecanico, va en ingles/letra suelta
por la regla transversal del plan. Los valores estan fijados en
docs/memoria-v2/TEXTOS.md (decision resuelta #3 de PLAN-CONSTRUCCION.md
Seccion 1): el descarte es un simbolo permanente (no una papelera, que
sugeriria que se puede borrar).
"""

# Codigos de escape ANSI (SGR -- Select Graphic Rendition).
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

# Emoji por tipo de nota (los siete tipos), mas el de contexto y el de
# wip -- ver docs/memoria-v2/TEXTOS.md.
EMOJIS = {
    "D": "🧭",  # decision
    "M": "📌",  # memo
    "R": "⚠",  # restriction (valla)
    "Q": "❓",  # question
    "X": "🚫",  # discarded (descarte, permanente)
    "I": "🔥",  # incident
    "B": "⛔",  # blocker
    "CONTEXT": "⏩",  # contexto/avance del cierre de sesion
    "WIP": "🚧",  # commit de trabajo, exento de la aduana
}
