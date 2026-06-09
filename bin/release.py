#!/usr/bin/env python3
"""
release.py — Orquesta el release completo de un plugin de punta a punta.

Uso:
  python3 bin/release.py <plugin> <new-version> [--dry-run] [--allow-dirty]

Pasos:
  1. Pre-flight fail-closed (valida estado antes de mutar nada).
  2. Execute: bump + promoción de CHANGELOG + stage + commit/push.
  3. Post-push verify: versiones coherentes, commit en remoto.

Exit codes:
  0: release completo y verificado
  1: error de pre-flight o ejecución
  2: error de verificación post-push
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

# ── Constantes ────────────────────────────────────────────────────────────

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_VERIFY_FAIL = 2

MARKETPLACE_REL = os.path.join(".claude-plugin", "marketplace.json")
CHANGELOG_REL = "CHANGELOG.md"
PLUGIN_JSON_REL = os.path.join(".claude-plugin", "plugin.json")

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")
PLUGIN_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
MAX_INPUT_LEN = 128

SUBPROCESS_TIMEOUT = 60


# ── Helpers de validación (reutiliza mismas reglas que bump-version.py) ───

def _validate_semver(version: str) -> bool:
    """Devuelve True si version tiene formato semver válido."""
    if len(version) > MAX_INPUT_LEN:
        return False
    return bool(SEMVER_RE.match(version))


def _validate_plugin_name(name: str) -> bool:
    """Devuelve True si el nombre de plugin es válido (lowercase alnum con guiones)."""
    if len(name) > MAX_INPUT_LEN:
        return False
    return bool(PLUGIN_NAME_RE.match(name))


def _semver_tuple(version: str) -> tuple[int, int, int]:
    """Convierte '1.3.0' en (1, 3, 0). Ignora pre-release suffix para comparación."""
    core = version.split("-")[0]
    parts = core.split(".")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


# ── Helpers de subprocess ─────────────────────────────────────────────────

def _run(args: list[str], cwd: str, check: bool = False,
         env: dict | None = None, timeout: int = SUBPROCESS_TIMEOUT) -> subprocess.CompletedProcess:
    """Ejecuta un subproceso con lista de args (nunca shell=True)."""
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=merged_env,
        timeout=timeout,
        check=check,
    )


def _git(args: list[str], cwd: str, check: bool = False) -> subprocess.CompletedProcess:
    return _run(["git"] + args, cwd=cwd, check=check)


# ── Resolución de root ────────────────────────────────────────────────────

def _resolve_repo_root() -> str:
    """Resuelve el root del repo con git sobre el CWD (no con __file__)."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        _die("No se pudo resolver el root del repo. ¿Estás dentro de un repositorio git?")
    return result.stdout.strip()


# ── Salida de error ───────────────────────────────────────────────────────

def _die(msg: str, code: int = EXIT_ERROR) -> None:
    """Imprime mensaje de error a stderr y termina con code != 0."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ── Lectura de ficheros ───────────────────────────────────────────────────

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


# ── Pre-flight ────────────────────────────────────────────────────────────

def _preflight(plugin: str, new_ver: str, repo_root: str,
               allow_dirty: bool) -> tuple[str, str, str, str]:
    """
    Valida todos los pre-requisitos antes de mutar nada.
    Devuelve (plugin_json_path, marketplace_path, changelog_path, current_branch).
    Aborta con exit != 0 si cualquier check falla.
    """

    # 1. Validar nombres
    if not _validate_plugin_name(plugin):
        _die(f"Nombre de plugin inválido: {plugin!r}. "
             "Debe ser lowercase alfanumérico con guiones.")
    if not _validate_semver(new_ver):
        _die(f"Versión inválida: {new_ver!r}. Formato esperado: MAJOR.MINOR.PATCH")

    marketplace_path = os.path.join(repo_root, MARKETPLACE_REL)
    changelog_path = os.path.join(repo_root, CHANGELOG_REL)
    plugin_json_path = os.path.join(repo_root, plugin, PLUGIN_JSON_REL)

    # Verificar que el path no sale del repo_root (path traversal)
    repo_real = os.path.realpath(repo_root)
    plugin_json_real = os.path.realpath(plugin_json_path)
    if not plugin_json_real.startswith(repo_real + os.sep):
        _die(f"Path traversal detectado para {plugin!r}. Rechazado.")

    # 2. Plugin existe en marketplace.json
    marketplace = _load_json(marketplace_path)
    if "plugins" not in marketplace or not isinstance(marketplace["plugins"], list):
        _die("marketplace.json no tiene un array 'plugins' válido.")

    mp_entry = next(
        (p for p in marketplace["plugins"] if p["name"] == plugin), None
    )
    if mp_entry is None:
        _die(f"Plugin '{plugin}' no encontrado en marketplace.json.")

    # Plugin.json existe
    if not os.path.exists(plugin_json_path):
        _die(f"plugin.json no encontrado: {plugin_json_path}")

    plugin_data = _load_json(plugin_json_path)
    current_ver = plugin_data.get("version") or mp_entry.get("version", "0.0.0")

    # 3. new-version es estrictamente mayor que la actual
    try:
        if _semver_tuple(new_ver) <= _semver_tuple(current_ver):
            _die(
                f"La nueva versión {new_ver!r} no es mayor que la actual {current_ver!r}. "
                "El release requiere avanzar la versión."
            )
    except (ValueError, IndexError):
        _die(f"No se pudo comparar versiones: {current_ver!r} vs {new_ver!r}")

    # 4. Working tree limpio
    if not allow_dirty:
        status_result = _git(["status", "--porcelain"], repo_root)
        if status_result.stdout.strip():
            _die(
                "Working tree sucio. Haz commit o stash de los cambios antes de hacer release, "
                "o usa --allow-dirty."
            )

    # 5. Upstream configurado
    upstream_result = _git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        repo_root,
    )
    if upstream_result.returncode != 0:
        _die(
            "La rama actual no tiene upstream configurado. "
            "Configura el upstream con: git push -u origin <branch>"
        )

    # 6. No estar por detrás del remoto
    # git fetch para actualizar refs remotas. Si falla (ej. remote inaccesible),
    # no podemos verificar el estado — lo dejamos pasar (el push fallará después).
    fetch_result = _git(["fetch"], repo_root)
    if fetch_result.returncode == 0:
        behind_result = _git(["rev-list", "HEAD..@{u}", "--count"], repo_root)
        if behind_result.returncode == 0:
            behind_count = int(behind_result.stdout.strip() or "0")
            if behind_count > 0:
                _die(
                    f"La rama local está {behind_count} commit(s) por detrás del remoto. "
                    "Ejecuta 'git pull' antes de hacer release."
                )

    # 7. [Unreleased] con contenido
    changelog_text = _read_file(changelog_path)
    _check_unreleased_not_empty(changelog_text, changelog_path)

    # Obtener rama actual
    branch_result = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"

    return plugin_json_path, marketplace_path, changelog_path, current_branch


def _check_unreleased_not_empty(changelog_text: str, changelog_path: str) -> None:
    """
    Verifica que ## [Unreleased] tenga contenido no vacío.
    Aborta si está vacío (solo líneas en blanco hasta el siguiente ##).
    """
    match = re.search(r"^## \[Unreleased\](.*?)(?=^## \[|\Z)", changelog_text,
                      re.MULTILINE | re.DOTALL)
    if not match:
        _die(f"No se encontró ## [Unreleased] en {changelog_path}.")

    section_body = match.group(1)
    # Eliminar líneas en blanco; si queda algo, hay contenido
    if not section_body.strip():
        _die(
            "La sección ## [Unreleased] está vacía. "
            "Rellena el CHANGELOG con las notas de release antes de publicar."
        )


# ── Promoción de CHANGELOG ────────────────────────────────────────────────

def _promote_changelog(changelog_text: str, new_ver: str, today: str) -> str:
    """
    Reemplaza ## [Unreleased] con:
      ## [Unreleased]
      <línea en blanco>
      ## [new_ver] - today
      <contenido anterior de [Unreleased]>

    Keep a Changelog canónico: una sola línea en blanco entre los dos headings.
    """
    pattern = re.compile(
        r"(## \[Unreleased\])(.*?)(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(changelog_text)
    if not match:
        _die("No se encontró ## [Unreleased] en el CHANGELOG al intentar promocionar.")

    unreleased_body = match.group(2)  # incluye el \n inicial

    # Nuevo bloque: [Unreleased] vacío + línea en blanco + nuevo heading + contenido
    new_block = f"## [Unreleased]\n\n## [{new_ver}] - {today}{unreleased_body}"

    promoted = changelog_text[:match.start()] + new_block + changelog_text[match.end():]
    return promoted


# ── Dry-run ───────────────────────────────────────────────────────────────

def _print_dry_run_plan(plugin: str, new_ver: str, repo_root: str,
                        plugin_json_path: str, marketplace_path: str,
                        changelog_path: str, current_branch: str) -> None:
    """Imprime a stdout el plan de lo que haría el release."""
    today = datetime.date.today().isoformat()
    print(f"[DRY-RUN] Release plan para {plugin} v{new_ver}")
    print(f"  1. Bump: bin/bump-version.py {plugin} {new_ver}")
    print(f"     - {plugin_json_path}")
    print(f"     - {marketplace_path}")
    print(f"  2. Promover CHANGELOG: ## [Unreleased] -> ## [{new_ver}] - {today}")
    print(f"     - {changelog_path}")
    print(f"  3. Stage: solo los 3 ficheros anteriores")
    print(f"  4. Commit + push vía git-memory-commit.py")
    print(f"  5. Verify: versiones en remoto origin/{current_branch}")
    print(f"[DRY-RUN] Sin cambios aplicados.")


# ── Execute ───────────────────────────────────────────────────────────────

def _execute_bump(plugin: str, new_ver: str, repo_root: str) -> None:
    """Invoca bump-version.py como subproceso con UNMASSK_REPO_ROOT inyectado."""
    # bump-version.py está junto a este script en el repo real (no en el repo temporal).
    bump_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bump-version.py")
    env_override = {"UNMASSK_REPO_ROOT": repo_root}

    result = _run(
        [sys.executable, bump_script, plugin, new_ver],
        cwd=repo_root,
        env=env_override,
    )
    if result.returncode != 0:
        _die(
            f"bump-version.py falló (exit {result.returncode}):\n"
            f"  stdout: {result.stdout.strip()}\n"
            f"  stderr: {result.stderr.strip()}"
        )


def _execute_changelog(changelog_path: str, new_ver: str) -> None:
    """Promociona [Unreleased] a [new_ver] - today en el CHANGELOG."""
    today = datetime.date.today().isoformat()
    original = _read_file(changelog_path)
    promoted = _promote_changelog(original, new_ver, today)
    _write_file(changelog_path, promoted)


def _execute_stage(plugin_json_path: str, marketplace_path: str,
                   changelog_path: str, repo_root: str) -> None:
    """Stagea exactamente los 3 ficheros del release. Nada más."""
    # Paths relativos al root para git add
    paths = [plugin_json_path, marketplace_path, changelog_path]
    result = _git(["add", "--"] + paths, repo_root)
    if result.returncode != 0:
        _die(f"git add falló: {result.stderr.strip()}")


def _execute_commit_push(plugin: str, new_ver: str, repo_root: str,
                         plugin_json_path: str, marketplace_path: str,
                         changelog_path: str) -> None:
    """
    Commit vía git-memory-commit.py (sin --push) y luego push por separado.
    Separar los dos pasos garantiza que el commit local quede aunque el push falle.
    """
    commit_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "unmassk-toolkit", "bin", "git-memory-commit.py",
    )
    commit_script = os.path.normpath(commit_script)

    touched_rel = ", ".join([
        os.path.relpath(p, repo_root)
        for p in [plugin_json_path, marketplace_path, changelog_path]
    ])

    # Paso 1: commit (sin --push)
    commit_args = [
        sys.executable, commit_script,
        "chore", plugin, f"release v{new_ver}",
        "--body", f"Release {plugin} v{new_ver}: bump versiones y promover CHANGELOG.",
        "--trailer", f"Why=release v{new_ver}",
        "--trailer", f"Touched={touched_rel}",
    ]
    commit_result = _run(commit_args, cwd=repo_root)
    if commit_result.returncode != 0:
        print(commit_result.stdout, end="")
        print(commit_result.stderr, file=sys.stderr, end="")
        _die(
            f"git-memory-commit.py falló al crear el commit (exit {commit_result.returncode}):\n"
            f"  stderr: {commit_result.stderr.strip()}"
        )

    # Paso 2: push (separado, para que el commit local quede aunque falle)
    push_result = _git(["push"], repo_root)
    if push_result.returncode != 0:
        print(
            f"ADVERTENCIA: git push falló. El commit local existe y puedes recuperarlo con 'git push'.\n"
            f"  stderr: {push_result.stderr.strip()}",
            file=sys.stderr,
        )
        # No abortamos aquí: el post-push verify detectará la divergencia y saldrá != 0.


# ── Post-push verify ──────────────────────────────────────────────────────

def _verify(plugin: str, new_ver: str, repo_root: str,
            plugin_json_path: str, marketplace_path: str,
            current_branch: str) -> None:
    """
    Verifica post-push:
    1. git rev-list origin/<branch>..HEAD == 0 (commit en remoto)
    2. marketplace.json[plugin].version == plugin.json.version == new_ver
    Aborta con exit VERIFY_FAIL si algo no cuadra.
    """

    def _verify_die(msg: str) -> None:
        print(f"VERIFY ERROR: {msg}", file=sys.stderr)
        sys.exit(EXIT_VERIFY_FAIL)

    # 1. Commit en remoto
    diverge_result = _git(
        ["rev-list", f"origin/{current_branch}..HEAD", "--count"],
        repo_root,
    )
    if diverge_result.returncode != 0:
        _verify_die(
            f"No se pudo verificar si el commit llegó al remoto: "
            f"{diverge_result.stderr.strip()}"
        )
    ahead_count = int(diverge_result.stdout.strip() or "0")
    if ahead_count != 0:
        _verify_die(
            f"El commit local NO está en origin/{current_branch} "
            f"({ahead_count} commit(s) por delante). "
            "El push falló o no llegó a ejecutarse. "
            "Puedes recuperarlo con: git push"
        )

    # 2. Versiones coherentes
    marketplace = _load_json(marketplace_path)
    mp_entry = next(
        (p for p in marketplace.get("plugins", []) if p["name"] == plugin), None
    )
    if mp_entry is None:
        _verify_die(f"Plugin '{plugin}' no encontrado en marketplace.json post-bump.")
    mp_ver = mp_entry.get("version")

    plugin_data = _load_json(plugin_json_path)
    pj_ver = plugin_data.get("version")

    if mp_ver != new_ver:
        _verify_die(
            f"marketplace.json tiene versión {mp_ver!r} en lugar de {new_ver!r}."
        )
    if pj_ver != new_ver:
        _verify_die(
            f"plugin.json tiene versión {pj_ver!r} en lugar de {new_ver!r}."
        )
    if mp_ver != pj_ver:
        _verify_die(
            f"Versiones no coinciden: marketplace.json={mp_ver!r}, plugin.json={pj_ver!r}."
        )

    print(
        f"Release verificado. '/plugin update' verá ahora "
        f"{plugin} v{new_ver} en origin/{current_branch}."
    )


# ── CLI ───────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Orquesta el release completo de un plugin: bump + CHANGELOG + commit + push + verify."
    )
    parser.add_argument("plugin", help="Nombre del plugin (ej: unmassk-toolkit)")
    parser.add_argument("version", help="Nueva versión semver (ej: 1.4.0)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Imprime el plan sin aplicar ningún cambio.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Continúa aunque el working tree tenga cambios no staged.",
    )
    args = parser.parse_args()

    repo_root = _resolve_repo_root()

    plugin_json_path, marketplace_path, changelog_path, current_branch = _preflight(
        args.plugin, args.version, repo_root, args.allow_dirty
    )

    if args.dry_run:
        _print_dry_run_plan(
            args.plugin, args.version, repo_root,
            plugin_json_path, marketplace_path, changelog_path, current_branch,
        )
        return EXIT_OK

    # Execute
    _execute_bump(args.plugin, args.version, repo_root)
    _execute_changelog(changelog_path, args.version)
    _execute_stage(plugin_json_path, marketplace_path, changelog_path, repo_root)
    _execute_commit_push(
        args.plugin, args.version, repo_root,
        plugin_json_path, marketplace_path, changelog_path,
    )

    # Post-push verify
    _verify(
        args.plugin, args.version, repo_root,
        plugin_json_path, marketplace_path, current_branch,
    )

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
