"""Que linea de `gitmem` tecleada guarda una nota o una regla -- la
lectura que necesita la aduana (`hooks/customs.py`) para hacer la
pregunta de D-098 ANTES de que el comando corra.

Aqui viven tambien, una sola vez, las dos listas de palabras con las que
`bin/memory/rule.py` decide que `gitmem rule <palabra>` no guarda: si la
aduana y el comando las tuvieran cada uno por su lado, una palabra
anadida a una sola volveria a bloquear una lectura o a dejar pasar un
guardado [Moriarty ABUSE con `help`, 2026-10-19].

Pura: recibe las sentencias ya tokenizadas (el tokenizador de shell es
el de la aduana) y no abre ficheros ni llama a git.
"""

import re

from validator_searched import SEARCHED_FLAG, searched_given

# `gitmem rule list`/`ls` leen las reglas en vez de guardar una.
RULE_READ_WORDS = ("list", "ls")
# Palabras sueltas que `gitmem rule` rebota sin guardar: son subcomandos de
# otras familias y teclearlas aqui es la equivocacion natural [House,
# 2026-08-05: `gitmem rule list` guardaba una regla "list"].
RULE_NOT_A_RULE_WORDS = ("add", "find", "show", "read", "verify", "rebuild", "help")

_GITMEM_PROGRAM_TOKEN_RE = re.compile(r"(?:^|/)gitmem$")
_ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Los flags de `bin/memory/rule.py`, todos con un valor detras.
_RULE_VALUE_FLAGS = frozenset({"--kind", "--quote", "--retract", "--replaces", SEARCHED_FLAG})
# Pedir la ayuda de argparse no guarda nada [Moriarty ABUSE, 2026-10-19].
_HELP_FLAGS = ("-h", "--help")


def _flag_value(tokens, flag):
    """El valor de `flag` en `tokens` (`--flag X` o `--flag=X`), o `None`."""
    for i, tok in enumerate(tokens):
        if tok == flag:
            return tokens[i + 1] if i + 1 < len(tokens) else None
        if tok.startswith(flag + "="):
            return tok[len(flag) + 1:]
    return None


def _rule_saves(rest):
    """`gitmem rule ...` guarda (alta o `--replaces`) -- leer, `list`/`ls`,
    una palabra suelta que rule.py rebota y `--retract` no."""
    flags = {tok.split("=", 1)[0] for tok in rest if tok.startswith("--")}
    if "--retract" in flags:
        return False
    if "--replaces" in flags:
        return True
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok in _RULE_VALUE_FLAGS:
            i += 2
            continue
        if not tok.startswith("--"):
            word = tok.strip().lower()
            return word not in RULE_READ_WORDS and word not in RULE_NOT_A_RULE_WORDS
        i += 1
    return False


def find_unanswered_save(statements):
    """`(stmt_index, tokens)` de la primera sentencia que ES un `gitmem
    note`/`gitmem rule` que guarda sin `--searched` con contenido, o
    `None`. `statements` es la lista de sentencias tokenizadas del
    comando, o `None` si no se pudo tokenizar. Solo cuenta `gitmem` en
    posicion de programa: un `grep "gitmem note"` o un `echo gitmem note`
    solo lo mencionan."""
    if statements is None:
        return None
    for stmt_index, statement in enumerate(statements):
        # `\<salto>` (continuacion de linea) sale de shlex como un token
        # "\n" suelto: fuera, o el relanzamiento lleva un argumento que es
        # un salto de linea y obedecerlo rebota.
        tokens = [tok for tok in statement if tok != "\n"]
        while tokens and _ENV_ASSIGNMENT_RE.match(tokens[0]):
            tokens.pop(0)
        if len(tokens) < 2 or not _GITMEM_PROGRAM_TOKEN_RE.search(tokens[0]):
            continue
        sub, rest = tokens[1], tokens[2:]
        asks_help = any(tok in _HELP_FLAGS for tok in rest)
        saves = not asks_help and (sub == "note" or (sub == "rule" and _rule_saves(rest)))
        if saves and not searched_given(_flag_value(rest, SEARCHED_FLAG)):
            return stmt_index, tokens
    return None
