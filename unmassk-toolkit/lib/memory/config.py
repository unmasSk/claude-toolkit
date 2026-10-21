"""The project's three settings, loaded from .claude/project-memory/config.json.

A missing file gives fail-closed defaults; a corrupt file or a wrong-typed value raises.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """The three settings with their fail-closed defaults."""

    customs_enabled: bool | None = None  # None = not set; hooks/customs.py decides
    repo_type: str = "gitflow"         # fail-closed: main is protected unless declared
    test_command: str | None = None


def load(path: Path) -> Config:
    """Load ``config.json``: defaults if missing, ValueError naming the file if corrupt."""
    if not path.exists():
        return Config()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"config.py: {path.name} esta corrupto y no se pudo interpretar "
            f"como JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"config.py: {path.name} esta corrupto -- se esperaba un objeto "
            f"JSON (diccionario) y llego {type(data).__name__}"
        )

    customs_enabled = data.get("customs_enabled")
    if customs_enabled is not None and not isinstance(customs_enabled, bool):
        raise ValueError(
            f"config.py: {path.name} esta corrupto -- 'customs_enabled' "
            f"debe ser booleano y llego {type(customs_enabled).__name__}"
        )

    repo_type = data.get("repo_type", "gitflow")
    if not isinstance(repo_type, str):
        raise ValueError(
            f"config.py: {path.name} esta corrupto -- 'repo_type' debe "
            f"ser texto y llego {type(repo_type).__name__}"
        )

    test_command = data.get("test_command")
    if test_command is not None and not isinstance(test_command, str):
        raise ValueError(
            f"config.py: {path.name} esta corrupto -- 'test_command' debe "
            f"ser texto o null y llego {type(test_command).__name__}"
        )

    return Config(
        customs_enabled=customs_enabled,
        repo_type=repo_type,
        test_command=test_command,
    )
