#!/usr/bin/env python3
"""
release_validators.py — Validadores puros para release.py y release_helpers.py.

Funciones de validación de semver, nombres de plugin y path-safety.
Sin imports circulares: este módulo no importa release_helpers.
"""

import re

# ── Constantes ────────────────────────────────────────────────────────────

# Semver estricto: prohíbe ceros a la izquierda en major/minor/patch (semver 2.0.0 §2)
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[a-zA-Z0-9.]+)?$")
PLUGIN_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
MAX_INPUT_LEN = 128


# ── Validación de formato ─────────────────────────────────────────────────

def _validate_semver(version: str) -> bool:
    """Devuelve True si version tiene formato semver estricto válido."""
    if len(version) > MAX_INPUT_LEN:
        return False
    return bool(SEMVER_RE.match(version))


def _validate_plugin_name(name: str) -> bool:
    """Devuelve True si el nombre de plugin es válido (lowercase alnum con guiones)."""
    if len(name) > MAX_INPUT_LEN:
        return False
    return bool(PLUGIN_NAME_RE.match(name))


# ── Comparación semver ────────────────────────────────────────────────────

def _semver_key(version: str) -> tuple:
    """
    Clave de comparación semver 2.0.0 (§11).

    - Compara major.minor.patch numéricamente.
    - Sin pre-release > con pre-release del mismo core (1.4.0 > 1.4.0-rc1).
    - Entre pre-releases: identificadores numéricos por valor, alfanuméricos por ASCII,
      numérico < alfanumérico.
    """
    parts = version.split("-", 1)
    core = parts[0]
    pre = parts[1] if len(parts) > 1 else None

    major, minor, patch = (int(x) for x in core.split("."))

    if pre is None:
        # (1,) > cualquier tupla de identificadores de pre-release
        pre_key = (1,)
    else:
        ids = pre.split(".")
        pre_key = (0,) + tuple(
            (0, int(ident)) if ident.isdigit() else (1, ident)
            for ident in ids
        )

    return (major, minor, patch) + pre_key


