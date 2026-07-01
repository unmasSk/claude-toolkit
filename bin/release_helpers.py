#!/usr/bin/env python3
"""release_helpers.py — Funciones auxiliares para release.py.

Validadores de semver/plugin en release_validators.py (sin imports circulares).
"""

import json
import os
import re
import subprocess
import sys
from typing import NoReturn

# Garantiza que release_validators.py se encuentre tanto al ejecutar
# directamente (bin/ en sys.path) como al importar como módulo desde tests.
_BIN_DIR_RH = os.path.dirname(os.path.abspath(__file__))
if _BIN_DIR_RH not in sys.path:
    sys.path.insert(0, _BIN_DIR_RH)

from release_validators import (  # noqa: E402
    _semver_key,
    _validate_plugin_name,
    _validate_semver,
)

# ── Constantes ────────────────────────────────────────────────────────────

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_VERIFY_FAIL = 2

MARKETPLACE_REL = os.path.join(".claude-plugin", "marketplace.json")
CHANGELOG_REL = "CHANGELOG.md"
PLUGIN_JSON_REL = os.path.join(".claude-plugin", "plugin.json")

SUBPROCESS_TIMEOUT = 60


# ── Salida de error ───────────────────────────────────────────────────────

def _die(msg: str, code: int = EXIT_ERROR) -> NoReturn:
    """Imprime mensaje de error a stderr y termina con code != 0."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ── Helpers de subprocess ─────────────────────────────────────────────────

def _run(args: list[str], cwd: str, check: bool = False,
         env: dict | None = None, timeout: int = SUBPROCESS_TIMEOUT) -> subprocess.CompletedProcess:
    """Ejecuta un subproceso con lista de args (nunca shell=True)."""
    merged_env = {**os.environ, **(env or {})}
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            env=merged_env,
            timeout=timeout,
            check=check,
        )
    except subprocess.TimeoutExpired:
        _die(
            f"El subproceso {args[0]!r} superó el timeout de {timeout}s. "
            "Verifica conectividad y vuelve a intentarlo."
        )


def _git(args: list[str], cwd: str, check: bool = False) -> subprocess.CompletedProcess:
    return _run(["git"] + args, cwd=cwd, check=check)


# ── Resolución de root ────────────────────────────────────────────────────

def _resolve_repo_root() -> str:
    """Resuelve el root del repo con git sobre el CWD (no con __file__)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        _die(
            "git rev-parse --show-toplevel superó el timeout. "
            "Verifica que estás dentro de un repositorio git accesible."
        )
    if result.returncode != 0:
        _die("No se pudo resolver el root del repo. ¿Estás dentro de un repositorio git?")
    return result.stdout.strip()


# ── I/O de ficheros ───────────────────────────────────────────────────────

def _load_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        _die(f"Fichero no encontrado: {path}")
    except json.JSONDecodeError as exc:
        _die(f"JSON malformado en {path}: {exc}")


def _read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        _die(f"Fichero no encontrado: {path}")
    except OSError as exc:
        _die(f"Error leyendo {path}: {exc}")


def _write_file(path: str, content: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        _die(f"Error escribiendo {path}: {exc}")


# ── Validaciones de CHANGELOG ─────────────────────────────────────────────

def _extract_unreleased_body(changelog_text: str) -> str:
    """Devuelve el cuerpo de ## [Unreleased] (todo hasta la siguiente sección)."""
    match = re.search(r"^## \[Unreleased\](.*?)(?=^## \[|\Z)", changelog_text,
                      re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def _check_unreleased_not_empty(changelog_text: str, changelog_path: str) -> None:
    """Verifica que ## [Unreleased] exista, sea único, sea la primera sección
    de versión, y tenga contenido real (cabeceras ### solas no cuentan)."""
    unreleased_positions = [
        m.start() for m in re.finditer(r"^## \[Unreleased\]", changelog_text, re.MULTILINE)
    ]
    if len(unreleased_positions) == 0:
        _die(f"No se encontró ## [Unreleased] en {changelog_path}.")
    if len(unreleased_positions) > 1:
        _die(
            f"CHANGELOG malformado: múltiples ## [Unreleased] en {changelog_path}. "
            "Debe haber exactamente uno."
        )

    unreleased_pos = unreleased_positions[0]
    first_version_match = re.search(r"^## \[", changelog_text, re.MULTILINE)
    if first_version_match and first_version_match.start() != unreleased_pos:
        _die(
            f"CHANGELOG malformado: ## [Unreleased] no es la primera sección de versión "
            f"en {changelog_path}. Debe aparecer antes de cualquier ## [x.y.z]."
        )

    real_lines = [
        line for line in _extract_unreleased_body(changelog_text).splitlines()
        if line.strip() and not line.strip().startswith("###")
    ]
    if not real_lines:
        _die(
            "La sección ## [Unreleased] está vacía (solo cabeceras o en blanco). "
            "Rellena el CHANGELOG con las notas de release antes de publicar."
        )


def _promote_changelog(changelog_text: str, new_ver: str, today: str) -> str:
    """Mueve el contenido de ## [Unreleased] bajo ## [new_ver] - today
    y deja un ## [Unreleased] vacío arriba (exactamente una línea en blanco
    de separación — Keep a Changelog canónico)."""
    pattern = re.compile(
        r"(## \[Unreleased\])(.*?)(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(changelog_text)
    if not match:
        _die("No se encontró ## [Unreleased] en el CHANGELOG al intentar promocionar.")

    unreleased_body = match.group(2)
    new_block = f"## [Unreleased]\n\n## [{new_ver}] - {today}{unreleased_body}"

    return changelog_text[:match.start()] + new_block + changelog_text[match.end():]


# ── Helpers de preflight ──────────────────────────────────────────────────

def _preflight_validate_inputs(plugin: str, new_ver: str) -> None:
    """Valida formato de plugin y version. Aborta si inválidos."""
    if not _validate_plugin_name(plugin):
        _die(f"Nombre de plugin inválido: {plugin!r}. "
             "Debe ser lowercase alfanumérico con guiones.")
    if not _validate_semver(new_ver):
        _die(f"Versión inválida: {new_ver!r}. Formato esperado: MAJOR.MINOR.PATCH")


def _preflight_resolve_paths(plugin: str, repo_root: str) -> tuple[str, str, str]:
    """
    Resuelve y valida los paths de los 3 ficheros del release.
    Devuelve (plugin_json_path, marketplace_path, changelog_path).
    Aborta si se detecta path traversal.
    """
    marketplace_path = os.path.join(repo_root, MARKETPLACE_REL)
    changelog_path = os.path.join(repo_root, CHANGELOG_REL)
    plugin_json_path = os.path.join(repo_root, plugin, PLUGIN_JSON_REL)

    repo_real = os.path.realpath(repo_root)

    def _assert_inside_repo(path: str, label: str) -> None:
        real = os.path.realpath(path)
        if not real.startswith(repo_real + os.sep):
            _die(f"Path traversal detectado para {label!r} ({path!r}). Rechazado.")

    _assert_inside_repo(plugin_json_path, plugin)
    _assert_inside_repo(marketplace_path, MARKETPLACE_REL)
    _assert_inside_repo(changelog_path, CHANGELOG_REL)

    return plugin_json_path, marketplace_path, changelog_path


def _preflight_check_plugin_exists(
    plugin: str,
    marketplace_path: str,
    plugin_json_path: str,
) -> str:
    """
    Verifica que el plugin existe en marketplace.json y que plugin.json existe.
    Devuelve la versión actual del plugin.
    """
    marketplace = _load_json(marketplace_path)
    if "plugins" not in marketplace or not isinstance(marketplace["plugins"], list):
        _die("marketplace.json no tiene un array 'plugins' válido.")

    mp_entry = next((p for p in marketplace["plugins"] if p["name"] == plugin), None)
    if mp_entry is None:
        _die(f"Plugin '{plugin}' no encontrado en marketplace.json.")

    if not os.path.exists(plugin_json_path):
        _die(f"plugin.json no encontrado: {plugin_json_path}")

    plugin_data = _load_json(plugin_json_path)
    return plugin_data.get("version") or mp_entry.get("version", "0.0.0")


def _preflight_check_version_order(new_ver: str, current_ver: str) -> None:
    """Aborta si new_ver no es estrictamente mayor que current_ver."""
    try:
        if _semver_key(new_ver) <= _semver_key(current_ver):
            _die(
                f"La nueva versión {new_ver!r} no es mayor que la actual {current_ver!r}. "
                "El release requiere avanzar la versión."
            )
    except (ValueError, IndexError):
        _die(f"No se pudo comparar versiones: {current_ver!r} vs {new_ver!r}")


def _preflight_check_tree_clean(repo_root: str, allow_dirty: bool) -> None:
    """Aborta si el working tree está sucio y allow_dirty no está activado."""
    if not allow_dirty:
        status_result = _git(["status", "--porcelain"], repo_root)
        if status_result.stdout.strip():
            _die(
                "Working tree sucio. Haz commit o stash de los cambios antes de hacer release, "
                "o usa --allow-dirty."
            )


def _preflight_check_upstream(repo_root: str) -> None:
    """Aborta si la rama actual no tiene upstream configurado."""
    upstream_result = _git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        repo_root,
    )
    if upstream_result.returncode != 0:
        _die(
            "La rama actual no tiene upstream configurado. "
            "Configura el upstream con: git push -u origin <branch>"
        )


def _preflight_check_not_behind(repo_root: str) -> None:
    """
    Hace git fetch y verifica que local no está por detrás del remoto.
    Aborta si el fetch falla (fail-closed) o si hay commits pendientes de pull.
    """
    fetch_result = _git(["fetch"], repo_root)
    if fetch_result.returncode != 0:
        _die(
            f"git fetch falló. Verifica conectividad con el remoto.\n"
            f"  stderr: {fetch_result.stderr.strip()}"
        )
    behind_result = _git(["rev-list", "HEAD..@{u}", "--count"], repo_root)
    if behind_result.returncode == 0:
        behind_count = int(behind_result.stdout.strip() or "0")
        if behind_count > 0:
            _die(
                f"La rama local está {behind_count} commit(s) por detrás del remoto. "
                "Ejecuta 'git pull' antes de hacer release."
            )
    else:
        _die("No se pudo comparar con el remoto (git rev-list falló).")
