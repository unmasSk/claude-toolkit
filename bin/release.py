#!/usr/bin/env python3
"""
release.py — Orquesta el release de un plugin: preflight + bump + CHANGELOG + commit/push + verify.

Uso: python3 bin/release.py <plugin> <new-version> [--dry-run] [--allow-dirty]
Exit: 0=ok, 1=error preflight/ejecución, 2=error verificación post-push.
Helpers en release_helpers.py (mismo directorio).
"""

import argparse
import datetime
import os
import sys
from pathlib import Path

_BIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _BIN_DIR not in sys.path:
    sys.path.insert(0, _BIN_DIR)

_LIB_MEMORY_DIR = os.path.normpath(
    os.path.join(_BIN_DIR, "..", "unmassk-toolkit", "lib", "memory")
)


def _load_memory_lib() -> None:
    """Deja importable el sistema de memoria v2, y falla en voz alta si no
    está. Se resuelve desde este fichero, no desde el directorio de
    trabajo: publicar se ejecuta desde la raíz del repositorio que se
    publica, que no tiene por qué ser este.
    """
    if not os.path.isdir(_LIB_MEMORY_DIR):
        _die(
            f"no encuentro el sistema de memoria en {_LIB_MEMORY_DIR}. "
            "Sin él no hay con qué escribir el commit del release."
        )
    if _LIB_MEMORY_DIR not in sys.path:
        sys.path.insert(0, _LIB_MEMORY_DIR)

from release_helpers import (  # noqa: E402
    EXIT_OK,
    EXIT_VERIFY_FAIL,
    _check_unreleased_not_empty,
    _die,
    _git,
    _load_json,
    _preflight_check_not_behind,
    _preflight_check_plugin_exists,
    _preflight_check_tree_clean,
    _preflight_check_upstream,
    _preflight_check_version_order,
    _preflight_resolve_paths,
    _preflight_validate_inputs,
    _promote_changelog,
    _read_file,
    _resolve_repo_root,
    _run,
    _semver_key,
    _write_file,
)


# ── Pre-flight ────────────────────────────────────────────────────────────

def _preflight(plugin: str, new_ver: str, repo_root: str,
               allow_dirty: bool) -> tuple[str, str, str, str]:
    """
    Valida todos los pre-requisitos antes de mutar nada.
    Devuelve (plugin_json_path, marketplace_path, changelog_path, current_branch).
    Aborta con exit != 0 si cualquier check falla.
    """
    _preflight_validate_inputs(plugin, new_ver)

    plugin_json_path, marketplace_path, changelog_path = _preflight_resolve_paths(
        plugin, repo_root
    )

    current_ver = _preflight_check_plugin_exists(plugin, marketplace_path, plugin_json_path)
    _preflight_check_version_order(new_ver, current_ver)
    _preflight_check_tree_clean(repo_root, allow_dirty)
    _preflight_check_upstream(repo_root)
    _preflight_check_not_behind(repo_root)

    changelog_text = _read_file(changelog_path)
    _check_unreleased_not_empty(changelog_text, changelog_path)

    branch_result = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"

    return plugin_json_path, marketplace_path, changelog_path, current_branch


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
    print(f"  4. Commit + push vía el generador de memoria (notes.write_work)")
    print(f"  5. Verify: versiones en remoto origin/{current_branch}")
    print(f"[DRY-RUN] Sin cambios aplicados.")


# ── Execute ───────────────────────────────────────────────────────────────

def _execute_bump(plugin: str, new_ver: str, repo_root: str) -> None:
    """Invoca bump-version.py como subproceso con UNMASSK_REPO_ROOT inyectado."""
    bump_script = os.path.join(_BIN_DIR, "bump-version.py")
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
    """
    Stagea los 3 ficheros del release sin tocar el resto del índice.

    No hace git reset: cualquier fichero que el usuario tuviera staged antes
    sigue staged después (el commit usará pathspec explícito para incluir
    solo los 3 ficheros del release).
    """
    result = _git(["add", "--", plugin_json_path, marketplace_path, changelog_path], repo_root)
    if result.returncode != 0:
        _die(f"git add falló: {result.stderr.strip()}")


def _execute_commit_push(plugin: str, new_ver: str, repo_root: str,
                         plugin_json_path: str, marketplace_path: str,
                         changelog_path: str) -> None:
    """
    Commit vía el generador del sistema de memoria v2, y luego push por
    separado. El commit local queda aunque el push falle (recuperable con
    'git push').

    Llama a `notes.write_work()` — la pieza, no el script `bin/memory/work.py`
    — y esa distinción es deliberada, no un atajo:

    - `write_work()` se escribió PARA esto. Su propio docstring lo dice:
      "lo necesita la publicacion del toolkit, que commitea unos pocos
      ficheros sin llevarse cambios a medias de otros".
    - La protección de la rama principal vive en los SCRIPTS (`work.py`,
      `wip.py`), no en la pieza. Es una regla sobre el trabajo del día:
      el trabajo no aterriza en la rama principal por su cuenta. Publicar
      es justamente el acto que sí va ahí — someterlo a esa regla haría
      imposible publicar, que es lo contrario de lo que la regla protege.

    Ya no viaja el campo de ficheros tocados: el v2 lo retiró entero
    porque git guarda el diff y `git log -- <ruta>` ya responde eso
    [TEXTOS.md §6, punto 7].
    """
    _load_memory_lib()
    import notes  # noqa: E402  (import tras sys.path, resuelto en _load_memory_lib)

    paths = [Path(plugin_json_path), Path(marketplace_path), Path(changelog_path)]

    # Los bytes que este proceso acaba de escribir, leídos antes de tocar
    # git: es lo que `write_work()` compara para no commitear el contenido
    # de otro bajo este mensaje [DEUDA.md punto 27].
    known_content = []
    for path in paths:
        try:
            known_content.append(path.read_bytes())
        except OSError:
            known_content.append(None)

    result = notes.write_work(
        f"release {plugin} v{new_ver}",
        paths,
        None,
        known_content=known_content,
    )
    if not result.ok:
        _die(f"el generador de memoria falló al crear el commit: {result.git_error}")

    push_result = _git(["push"], repo_root)
    if push_result.returncode != 0:
        print(
            f"ADVERTENCIA: git push falló. El commit local existe; recupéralo con 'git push'.\n"
            f"  stderr: {push_result.stderr.strip()}",
            file=sys.stderr,
        )


# ── Post-push verify ──────────────────────────────────────────────────────

def _verify_remote_has_commit(repo_root: str, current_branch: str) -> None:
    """Verifica que el commit local llegó al remoto. Aborta con VERIFY_FAIL si no."""
    diverge_result = _git(
        ["rev-list", f"origin/{current_branch}..HEAD", "--count"],
        repo_root,
    )
    if diverge_result.returncode != 0:
        print(
            f"VERIFY ERROR: No se pudo verificar si el commit llegó al remoto: "
            f"{diverge_result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(EXIT_VERIFY_FAIL)

    ahead_count = int(diverge_result.stdout.strip() or "0")
    if ahead_count != 0:
        print(
            f"VERIFY ERROR: El commit local NO está en origin/{current_branch} "
            f"({ahead_count} commit(s) por delante). "
            "El push falló. Recupéralo con: git push",
            file=sys.stderr,
        )
        sys.exit(EXIT_VERIFY_FAIL)


def _verify_versions_match(
    plugin: str, new_ver: str, plugin_json_path: str, marketplace_path: str
) -> None:
    """Verifica que marketplace.json y plugin.json coinciden en new_ver."""
    marketplace = _load_json(marketplace_path)
    mp_entry = next(
        (p for p in marketplace.get("plugins", []) if p["name"] == plugin), None
    )
    if mp_entry is None:
        print(
            f"VERIFY ERROR: Plugin '{plugin}' no encontrado en marketplace.json post-bump.",
            file=sys.stderr,
        )
        sys.exit(EXIT_VERIFY_FAIL)

    mp_ver = mp_entry.get("version")
    pj_ver = _load_json(plugin_json_path).get("version")

    errors = []
    if mp_ver != new_ver:
        errors.append(f"marketplace.json tiene versión {mp_ver!r} en lugar de {new_ver!r}.")
    if pj_ver != new_ver:
        errors.append(f"plugin.json tiene versión {pj_ver!r} en lugar de {new_ver!r}.")
    if mp_ver != pj_ver:
        errors.append(
            f"Versiones no coinciden: marketplace.json={mp_ver!r}, plugin.json={pj_ver!r}."
        )
    if errors:
        for e in errors:
            print(f"VERIFY ERROR: {e}", file=sys.stderr)
        sys.exit(EXIT_VERIFY_FAIL)


def _verify(plugin: str, new_ver: str, repo_root: str,
            plugin_json_path: str, marketplace_path: str,
            current_branch: str) -> None:
    """Orquesta la verificación post-push: commit en remoto + versiones coherentes."""
    _verify_remote_has_commit(repo_root, current_branch)
    _verify_versions_match(plugin, new_ver, plugin_json_path, marketplace_path)
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

    _execute_bump(args.plugin, args.version, repo_root)
    _execute_changelog(changelog_path, args.version)
    _execute_stage(plugin_json_path, marketplace_path, changelog_path, repo_root)
    _execute_commit_push(
        args.plugin, args.version, repo_root,
        plugin_json_path, marketplace_path, changelog_path,
    )

    _verify(
        args.plugin, args.version, repo_root,
        plugin_json_path, marketplace_path, current_branch,
    )

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
