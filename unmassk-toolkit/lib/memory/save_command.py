"""Detect a typed `gitmem` command that saves a note or a rule without `--searched`.

Pure: takes statements already tokenized by the caller; no file or git access.
"""

import re

from validator_searched import SEARCHED_FLAG, searched_given

# `gitmem rule list`/`ls` read rules instead of saving one.
RULE_READ_WORDS = ("list", "ls")
# Single words `gitmem rule` refuses to save (subcommands of other families).
RULE_NOT_A_RULE_WORDS = ("add", "find", "show", "read", "verify", "rebuild", "help")

_GITMEM_PROGRAM_TOKEN_RE = re.compile(r"(?:^|/)gitmem$")
_ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Flags of `bin/memory/rule.py` that take a value.
_RULE_VALUE_FLAGS = frozenset({"--kind", "--quote", "--retract", "--replaces", SEARCHED_FLAG})
# Asking argparse for help saves nothing.
_HELP_FLAGS = ("-h", "--help")


def _flag_value(tokens, flag):
    """Value of `flag` in `tokens` (`--flag X` or `--flag=X`), or `None`."""
    for i, tok in enumerate(tokens):
        if tok == flag:
            return tokens[i + 1] if i + 1 < len(tokens) else None
        if tok.startswith(flag + "="):
            return tok[len(flag) + 1:]
    return None


def _rule_saves(rest):
    """True when `gitmem rule ...` saves (new rule or `--replaces`), not reads or retracts."""
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
    """`(stmt_index, tokens)` of the first statement saving a note/rule without `--searched`, or `None`.

    `statements` is the tokenized command, or `None` if it could not be tokenized.
    Only `gitmem` in program position counts.
    """
    if statements is None:
        return None
    for stmt_index, statement in enumerate(statements):
        # A line continuation comes out of shlex as a lone "\n" token.
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
