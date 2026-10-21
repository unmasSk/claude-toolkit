"""Refuse a direct commit on the main branch of a protected repository.

Shared by `bin/memory/work.py` and `bin/memory/wip.py`; each caller decides whether to call it.
"""

from pathlib import Path

import config
import gitcmd
import notes

# Protected repo_type; same value as config.Config's fail-closed default.
PROTECTED_REPO_TYPE = "gitflow"

# Branch names that count as the main branch.
MAIN_BRANCH_NAMES = frozenset({"main", "master"})

# Written by lib/install_apply.py: install files left uncommitted on a protected branch, one path per line.
_INSTALL_UNCOMMITTED_MARKER = (".claude", ".unmassk", "install-uncommitted.txt")


def current_branch(root):
    """Current branch of the repository at `root`; raises `RuntimeError` with git's stderr on failure."""
    result = gitcmd.run(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=root, timeout=gitcmd.GIT_TIMEOUT
    )
    if result.returncode != 0:
        raise RuntimeError(f"no se pudo leer la rama actual: {result.stderr}")
    return result.stdout.strip()


def protected_branch_rejection(branch, config_path=None):
    """Rejection text: what happened and what to do.

    With `config_path`, append its exact path and whether to create or edit it;
    the text without it stays a literal prefix of the text with it.
    """
    text = (
        f"❌ commit de trabajo rechazado: repo_type=\"{PROTECTED_REPO_TYPE}\" "
        f"(protegido) y la rama actual (\"{branch}\") es la rama principal.\n"
        "Que hacer: crea una rama de trabajo y commitea ahi "
        "(`git checkout -b <rama>`); o si este repositorio de verdad "
        "despliega directo desde su rama principal, declaralo en "
        "config.json con \"repo_type\": \"trunk\" (o el que corresponda "
        "distinto de \"gitflow\")."
    )
    if config_path is None:
        return text

    if config_path.exists():
        detail = (
            f"\nLa ruta exacta de ese fichero en este repositorio: "
            f"{config_path}\nYa existe -- anade (o cambia) ahi la clave "
            "\"repo_type\": \"trunk\" sin tocar el resto de sus ajustes "
            "(por ejemplo \"customs_enabled\" o \"test_command\", si ya "
            "los tiene)."
        )
    else:
        detail = (
            f"\nLa ruta exacta de ese fichero en este repositorio: "
            f"{config_path}\nNo existe todavia -- crealo con este "
            "contenido:\n"
            "  {\"repo_type\": \"trunk\"}"
        )
    return text + detail


def protected_main_branch(root, cfg):
    """The current branch name when repo_type is protected and it is the main branch, else None."""
    if cfg.repo_type != PROTECTED_REPO_TYPE:
        return None
    branch = current_branch(root)
    return branch if branch in MAIN_BRANCH_NAMES else None


def _branch_is_protected(root):
    """`protected_main_branch` for a by-path caller with no config loaded."""
    cfg = config.load(notes.pm_root(root) / "config.json")
    return protected_main_branch(root, cfg) is not None


def install_left_uncommitted(root):
    """Files the install left uncommitted on a protected branch that still
    carry changes. A failed `git status` lists them all: warn, never hide."""
    try:
        text = Path(root, *_INSTALL_UNCOMMITTED_MARKER).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ()
    listed = [line for line in text.splitlines() if line.strip()]
    if not listed:
        return ()
    result = gitcmd.run(
        ["status", "--porcelain", "--untracked-files=all", "--", *listed],
        cwd=root, timeout=gitcmd.GIT_TIMEOUT,
    )
    if result.returncode != 0:
        return tuple(listed)
    return tuple(line[3:] for line in result.stdout.splitlines() if line.strip())


if __name__ == "__main__":
    # By-path entry for lib/install_apply.py, which may not import lib/memory/.
    print("protected" if _branch_is_protected(notes.repo_root()) else "open")
