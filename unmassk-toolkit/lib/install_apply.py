"""
install_apply -- Phase 3 (execution) for bin/git-memory-install.py.

Split out of git-memory-install.py (600+ LOC, growing every round with
security guards) to keep the CLI entrypoint under the project's 500 LOC
limit. This module owns "actually change something on disk": cleaning up
old-style install remnants, removing stale hook entries, writing the
CLAUDE.md managed block, creating the manifest, installing the gitmem
PATH launcher, seeding the project-memory index files, and writing/
merging config.json's deduced repo_type.

Imports OLD_BIN_FILES/OLD_HOOK_FILES/OLD_LIB_FILES/OLD_SKILL_DIRS from
lib/install_inspect.py rather than duplicating them — inspect() and
_cleanup_old_install() must agree on exactly which files count as an
old-style install. One-way dependency: this module may import from
install_inspect.py, never the reverse.

The memory system's own modules (lib/memory/indexes.py, lib/memory/
config.py) live in a sibling directory not on sys.path by default — every
bin/memory/*.py script inserts lib/memory/ itself before importing them
(see bin/memory/work.py); the same insertion happens below, once, before
the `indexes` import.
"""

import json
import os
import subprocess
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from git_helpers import claude_md_lock_path, ensure_gitignore, file_lock, open_no_follow_symlink, verify_path_within_project
from managed_blocks import BLOCKS, upsert_managed_blocks
from version import VERSION

from install_inspect import OLD_BIN_FILES, OLD_HOOK_FILES, OLD_LIB_FILES, OLD_SKILL_DIRS

_LIB_MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

import indexes  # noqa: E402  (import after sys.path insert, same pattern as bin/memory/work.py)


def apply_plan(plan: dict[str, Any], source: str, target: str) -> list[str]:
    """Execute the installation plan.

    Args:
        plan: Output from create_plan().
        source: Plugin source root directory.
        target: Target repository root directory.

    Returns:
        List of error messages. Empty list means all actions succeeded.
    """
    errors = []

    for action, description in plan["actions"]:
        try:
            if action == "abort":
                return [description]
            elif action == "cleanup_old":
                _cleanup_old_install(target, source)
            elif action == "cleanup_stale_hooks":
                _cleanup_stale_settings_hooks(target)
            elif action == "update_claude_md":
                _update_claude_md(target)
            elif action == "install_gitmem_launcher":
                info = _install_gitmem_launcher(source, target)
                suffix = " (self-install: points at source tree, not the cache)" if info["is_self"] else ""
                print(f"  gitmem launcher: {info['path']}{suffix}")
                if not info["in_path"]:
                    print("  ⚠️  ~/.local/bin is not in your PATH. Add this line to your ~/.zshrc:")
                    print('      export PATH="$HOME/.local/bin:$PATH"')
            elif action == "seed_project_memory":
                _seed_project_memory(target)
            elif action == "write_config_json":
                print(f"  {_write_config_json(target, plan.get('repo_type', 'trunk'))}")
            elif action == "create_manifest":
                # Decision 2d56444 / Moriarty #63: create_manifest is always
                # the last action in plan["actions"] (see create_plan() in
                # bin/git-memory-install.py), so by the time we get here
                # `errors` already holds every failure from this same run.
                # The manifest is the producer side of the seam the boot
                # consumer gate trusts (upgrade_check.needs_upgrade, the
                # STATUS line) — stamping VERSION when an earlier action
                # failed would lie about install/upgrade success. Only write
                # it when nothing has failed so far; on failure, leave the
                # manifest exactly as it was (absent or stale) so the next
                # boot's consumer gate still sees the install/upgrade as
                # pending and retries it.
                if not errors:
                    _create_manifest(target, plan["mode"])
        except Exception as e:
            errors.append(f"{action}: {e}")

    if not errors:
        _commit_what_the_install_created(target)

    return errors


# Ficheros que la instalacion crea y que TIENEN que viajar en git. No es
# una lista de "por si acaso": cada uno se pierde en un clon si no esta
# aqui, y su ausencia rompe algo concreto. Los ocho indices y `config.json`
# son la memoria del proyecto; `.gitignore` es lo que impide que el informe
# del arranque -- reescrito en cada sesion -- acabe commiteado; `CLAUDE.md`
# es lo que le dice a Claude que cargue las skills.
#
# `manifest.json` NO esta y es deliberado: vive bajo `.claude/.unmassk/`,
# que el propio `.gitignore` ignora, porque dice que version hay instalada
# EN ESTA MAQUINA. Versionarlo haria que un clon heredara la version de
# otro ordenador.
_LO_QUE_CREA_LA_INSTALACION = (
    ".gitignore",
    "CLAUDE.md",
    ".claude/project-memory/config.json",
    ".claude/project-memory/ARCHIVED.md",
    ".claude/project-memory/BLOCKED.md",
    ".claude/project-memory/DECISIONS.md",
    ".claude/project-memory/DISCARDED.md",
    ".claude/project-memory/INCIDENTS.md",
    ".claude/project-memory/MEMOS.md",
    ".claude/project-memory/QUESTIONS.md",
    ".claude/project-memory/RESTRICTIONS.md",
)


def _commit_what_the_install_created(target: str) -> None:
    """Guarda en git lo que la instalacion acaba de crear.

    Sin esto, un proyecto recien instalado termina el dia con DIEZ ficheros
    sin guardar [medido 2026-08-06, simulacion de un dia entero de punta a
    punta]. Tres consecuencias, y ninguna es cosmetica:

    1. **Ruido permanente en `git status`.** Diez lineas que no son trabajo
       del usuario y que no desaparecen nunca por si solas.
    2. **Publicar se bloquea.** `bin/release.py` se niega a correr con el
       arbol sucio, asi que instalar la memoria impedia publicar.
    3. **Al clonar en otra maquina no hay ni configuracion ni indices.** Es
       el mismo agujero que ya se cerro en `rules.py` (el fichero de reglas
       se quedaba fuera de git) y en `zones.py` (las zonas se perdian
       enteras al clonar) -- este era el tercer sitio, y el mas grande.

    Pathspec EXPLICITO, nunca `git add -A`: el usuario puede tener trabajo
    suyo a medias en el indice cuando esto corre, y arrastrarlo dentro de un
    commit de instalacion seria robarle su commit. Mismo contrato que
    `gitcmd.commit()` ya cumple para la publicacion del toolkit.

    Falla en silencio a proposito: un repositorio sin un solo commit
    todavia, un `user.email` sin configurar o un `pre-commit` ajeno que
    rechaza son casos normales, y **ninguno justifica reventar una
    instalacion que por lo demas ha ido bien**. Lo que queda entonces son
    unos ficheros sin commitear, que es exactamente el estado de antes de
    este arreglo -- nunca algo peor.
    """
    existentes = [
        rel for rel in _LO_QUE_CREA_LA_INSTALACION
        if os.path.isfile(os.path.join(target, rel))
    ]
    if not existentes:
        return
    try:
        add = subprocess.run(
            ["git", "add", "--"] + existentes,
            cwd=target, capture_output=True, text=True, timeout=15,
        )
        if add.returncode != 0:
            return
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--"] + existentes,
            cwd=target, capture_output=True, text=True, timeout=15,
        )
        # Nada que guardar: la instalacion no cambio ninguno de estos
        # ficheros (segunda pasada sobre un proyecto ya instalado). Sin esta
        # comprobacion, `git commit` fallaria por "nothing to commit" y
        # dejaria un error donde no hay ninguno.
        if staged.returncode != 0 or not staged.stdout.strip():
            return
        subprocess.run(
            ["git", "commit", "-m",
             "install: memoria del proyecto (indices, config y gitignore)",
             "--"] + existentes,
            cwd=target, capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return


def _cleanup_old_install(target: str, source: str) -> None:
    """Remove files from old-style installs that copied to project root.

    Only removes files we recognize as git-memory managed files.
    Never removes user files or directories that contain non-managed files.
    """
    is_self = os.path.realpath(source) == os.path.realpath(target)
    if is_self:
        return

    removed = []

    # Remove individual managed files
    for f in OLD_BIN_FILES + OLD_HOOK_FILES + OLD_LIB_FILES:
        path = os.path.join(target, f)
        if os.path.isfile(path) or os.path.islink(path):
            # BUG AH / SEC-CRIT-002 sibling: "bin"/"hooks"/"lib" at the
            # project root may themselves be a symlink to an external,
            # pre-existing directory that happens to contain a real file
            # matching one of these fixed names — verify the resolved path
            # stays inside target before unlinking, mirroring the guard the
            # ".claude/hooks"/".claude/skills" rmtree section below already has.
            try:
                verify_path_within_project(path, target)
            except OSError:
                continue
            os.unlink(path)
            removed.append(f)

    # Remove old skill directories
    for d in OLD_SKILL_DIRS:
        path = os.path.join(target, d)
        if os.path.isdir(path) and not os.path.islink(path):
            # Same guard class as the fixed-name file loop above: an
            # intermediate component of `d` (e.g. "skills") may itself be a
            # symlink to an external, pre-existing directory — verify the
            # resolved path stays inside target before rmtree.
            try:
                verify_path_within_project(path, target)
            except OSError:
                continue
            shutil.rmtree(path)
            removed.append(d + "/")
        elif os.path.islink(path):
            # SEC-LOW-001: sibling of the rmtree branch above — an
            # intermediate component of `d` can equally be a symlink when
            # `path` itself resolves to a symlink; same guard, same reason.
            try:
                verify_path_within_project(path, target)
            except OSError:
                continue
            os.unlink(path)
            removed.append(d)

    # Remove old-style plugin.json at repo root (NOT .claude-plugin/ which may contain marketplace.json)
    old_plugin_json = os.path.join(target, "plugin.json")
    if os.path.isfile(old_plugin_json):
        os.remove(old_plugin_json)
        removed.append("plugin.json")

    # Remove old .claude/hooks and .claude/skills symlink directories
    for subdir in ["hooks", "skills"]:
        path = os.path.join(target, ".claude", subdir)
        if os.path.isdir(path):
            # SEC-CRIT-002: .claude may be a symlink to an external,
            # pre-existing directory (old-install shape reproduced there by
            # coincidence) — verify the resolved path stays inside target
            # before rmtree, or this destroys an unrelated directory outside
            # the project.
            try:
                verify_path_within_project(path, target)
            except OSError:
                continue
            # Only remove if it contains symlinks (our old install pattern)
            entries = os.listdir(path)
            all_symlinks = all(os.path.islink(os.path.join(path, e)) for e in entries) if entries else True
            if all_symlinks:
                shutil.rmtree(path)
                removed.append(f".claude/{subdir}/")

    # Clean up __pycache__ left by our old scripts, then try to remove empty dirs
    for d in ["bin", "hooks", "skills", "lib"]:
        path = os.path.join(target, d)
        if os.path.isdir(path):
            # BUG AI: same symlinked-parent risk as the fixed-name unlink
            # loop above, but larger blast radius — shutil.rmtree() on
            # __pycache__ deletes a whole external subtree, not one file.
            try:
                verify_path_within_project(path, target)
            except OSError:
                continue
            pycache = os.path.join(path, "__pycache__")
            if os.path.isdir(pycache):
                shutil.rmtree(pycache)
            try:
                os.rmdir(path)  # Only succeeds if empty
            except OSError:
                pass

    if removed:
        print(f"  Cleaned {len(removed)} old-style install files/directories")


def _cleanup_stale_settings_hooks(target: str) -> None:
    """Remove stale hook entries from the project's .claude/settings.json.

    When migrating from old-style installs, the project settings may contain
    hook commands that reference local paths (e.g. python3 hooks/...) instead
    of using ${CLAUDE_PLUGIN_ROOT}. Since the plugin now provides hooks via
    hooks.json, these entries are stale and should be removed.
    """
    settings_path = os.path.join(target, ".claude", "settings.json")

    # BUG Y / SEC-CRIT-NEW: if .claude itself is a symlink pointing outside
    # the repo (not just settings.json — the parent directory), this must
    # be treated as "settings.json is unsafe to touch", never silently
    # read/modified through the symlinked directory. Raises UnsafePathError
    # (subclass of OSError), caught by apply_plan()'s existing
    # `except Exception` around this action — fails the install action
    # instead of touching anything outside the repo.
    verify_path_within_project(settings_path, target)

    if not os.path.isfile(settings_path):
        return

    try:
        # SEC-MED-NEW-13: never follow a symlink planted at settings.json —
        # neither the read nor the write-back should trust/touch whatever
        # external file it points at.
        with open_no_follow_symlink(settings_path, "r") as f:
            settings = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    if "hooks" not in settings:
        return

    del settings["hooks"]

    with open_no_follow_symlink(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    print("  Removed stale hook entries from .claude/settings.json")


def _update_claude_md(target: str) -> None:
    """Add or update all 5 managed blocks in CLAUDE.md."""
    claude_md = os.path.join(target, "CLAUDE.md")

    # file_lock (issue: lost-update race, memo eae0880): shared by install,
    # upgrade, and repair (all three call this same function) -- the lock
    # must span the ENTIRE read -> upsert -> write cycle, not just the
    # write, so a concurrent writer (another one of these three entry
    # points, or session-start-crew.py's boot-time hook) never silently
    # discards this call's change with a stale-read overwrite.
    # claude_md_lock_path() (Cerberus anti-pollution finding): all 3
    # CLAUDE.md writers in this codebase must pass the exact same lock path
    # so they genuinely serialize against each other, and it lives under
    # .claude/.unmassk/ (already gitignored) instead of next to CLAUDE.md
    # itself. Any OSError here (lock acquisition or the write itself) is
    # already caught by this function's own caller, apply_plan(), which
    # records it in `errors` and keeps running the rest of the plan.
    lock_path = claude_md_lock_path(target)
    with file_lock(claude_md, lock_path=lock_path):
        if os.path.isfile(claude_md):
            try:
                # 7th audit round (BUG U): never follow a symlink planted at
                # CLAUDE.md for this read either — the write below is already
                # guarded, but the read must fail closed to "file absent" too.
                with open_no_follow_symlink(claude_md, "r") as f:
                    content = f.read()
            except OSError:
                content = "# CLAUDE.md\n\n"
        else:
            content = "# CLAUDE.md\n\n"

        new_content, _ = upsert_managed_blocks(content)

        # SEC-CRIT-NEW-09: never follow a symlink planted at CLAUDE.md — refuse
        # to write through to whatever external file it points at. The caller
        # (apply_plan) already wraps this action in try/except, so raising here
        # is reported as an error rather than crashing the whole install.
        # atomic=True (docs/plan/fix-atomic-claude-md-write.md, T1): writes to a
        # temp file in the same directory + os.replace(), so a crash/kill mid-
        # write can never leave CLAUDE.md empty or partial — see
        # git_helpers._AtomicWriteNoFollowSymlink's docstring.
        with open_no_follow_symlink(claude_md, "w", atomic=True) as f:
            f.write(new_content)


def _create_manifest(target: str, mode: str) -> None:
    """Create .claude/.unmassk/manifest.json with install metadata."""
    claude_dir = os.path.join(target, ".claude")
    # BUG Y / SEC-CRIT-NEW: os.makedirs() silently follows a directory
    # symlink at .claude (or .claude/.unmassk) that resolves to a real,
    # existing directory outside the repo — every file-level
    # open_no_follow_symlink() guard below is moot if the write lands
    # inside that external directory instead. Verify BEFORE creating
    # anything. Raises UnsafePathError (OSError subclass); apply_plan()'s
    # `except Exception` around this action (and repair.py's per-issue
    # try/except) already fail the calling action closed on this.
    verify_path_within_project(claude_dir, target)
    os.makedirs(claude_dir, exist_ok=True)

    manifest = {
        "version": VERSION,
        "installed_at": datetime.now().isoformat(),
        "runtime_mode": mode,
        "managed_blocks": [
            {
                "file": "CLAUDE.md",
                "begin": b["begin"].replace("<!-- ", "").split(" (")[0].split(" -->")[0],
                "end": b["end"].replace("<!-- ", "").replace(" -->", ""),
            }
            for b in BLOCKS
        ],
        "hook_registrations": [
            "PreToolUse", "PostToolUse", "Stop",
            "PreCompact", "SessionStart", "UserPromptSubmit",
        ],
        "last_healthcheck_at": datetime.now().isoformat(),
    }

    unmassk_dir = os.path.join(claude_dir, ".unmassk")
    # Defense in depth: .unmassk itself could independently be a symlink
    # escaping the repo even when .claude (just verified above) is not.
    verify_path_within_project(unmassk_dir, target)
    os.makedirs(unmassk_dir, exist_ok=True)
    manifest_path = os.path.join(unmassk_dir, "manifest.json")
    # SEC-HIGH-NEW-03 (Argus): symlink-safe write, matching
    # lib/boot_memory.py's existing open_no_follow_symlink() pattern — a
    # pre-planted symlink at this fixed path must not be silently followed
    # and used to overwrite an arbitrary file outside the repo.
    # reject_hardlinks=True (issue #53, decision 51a3c44): manifest.json is
    # toolkit-generated-only, never a legitimate user file, so a hard link
    # here can only be an attack.
    with open_no_follow_symlink(manifest_path, "w", reject_hardlinks=True) as f:
        json.dump(manifest, f, indent=2)

    ensure_gitignore(target)


# ── gitmem PATH launcher ─────────────────────────────────────────────────

def _gitmem_launcher_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".local", "bin")


def _gitmem_launcher_self_content(source: str) -> str:
    """Launcher content for the dogfooding case (source == target): the
    plugin's own source tree is never versioned into the cache, so there
    is nothing to resolve on every run — the launcher points straight at
    bin/gitmem inside the source tree, fixed at install time.
    """
    gitmem_path = os.path.join(source, "bin", "gitmem")
    return (
        "#!/usr/bin/env python3\n"
        "import subprocess, sys\n"
        f"sys.exit(subprocess.run([sys.executable, {gitmem_path!r}, *sys.argv[1:]]).returncode)\n"
    )


def _gitmem_launcher_cache_content() -> str:
    """Launcher content for a real project: resolves the newest plugin
    cache version on EVERY run, so the launcher survives a plugin
    upgrade without being reinstalled.

    Does not reimplement the semver-picking algorithm [encargo: "la
    pieza que ya sabe encontrarla existe y se reutiliza, no se
    reescribe: lib/boot_health.py::_latest_version_dir() y
    CACHE_BASE_DIR"] — it bootstraps into whichever cache version it
    finds first purely to import the real function/constant, then asks
    THAT function for the true latest version and dispatches there. The
    bootstrap version is never itself trusted as "the latest" — only
    used to reach the code that decides that.
    """
    return (
        "#!/usr/bin/env python3\n"
        "import glob, os, subprocess, sys\n"
        "_toolkit_versions = os.path.join(os.path.expanduser('~'), '.claude', 'plugins',\n"
        "    'cache', 'unmassk-claude-toolkit', 'unmassk-toolkit')\n"
        "_bootstrap_lib = next(iter(sorted(glob.glob(os.path.join(_toolkit_versions, '*', 'lib')))), None)\n"
        "if _bootstrap_lib:\n"
        "    sys.path.insert(0, _bootstrap_lib)\n"
        "try:\n"
        "    from boot_health import CACHE_BASE_DIR, _latest_version_dir\n"
        "    _latest = _latest_version_dir(os.path.join(CACHE_BASE_DIR, 'unmassk-toolkit'))\n"
        "except Exception:\n"
        "    _latest = None\n"
        "if not _latest:\n"
        "    print('gitmem: no unmassk-toolkit version found in the plugin cache "
        "-- run the installer again.', file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "sys.exit(subprocess.run([sys.executable, os.path.join(_latest, 'bin', 'gitmem'), "
        "*sys.argv[1:]]).returncode)\n"
    )


def _install_gitmem_launcher(source: str, target: str) -> dict[str, Any]:
    """Install/replace the ~/.local/bin/gitmem launcher [encargo: "gitmem
    en el PATH -- y que sobreviva a las actualizaciones"]. A direct
    symlink to the cache's version-numbered gitmem would go dead on the
    next plugin upgrade; this launcher re-resolves the version on every
    invocation instead (self-install case excepted, see
    _gitmem_launcher_self_content).

    Always overwritten unconditionally, no prior-launcher check: the
    generated content is a pure function of (source, target), so there is
    nothing meaningful to compare before replacing an old one.

    Not project-scoped (~/.local/bin lives outside `target`), so
    verify_path_within_project doesn't apply here — that guard exists for
    attacker-planted symlinks inside a hostile repo, and this project's
    threat model has no external attacker [CLAUDE.md, "que security y
    tests son para"]. The atomic temp-file + os.replace() write is kept
    anyway: it protects against THIS process crashing mid-write, which is
    the real, in-scope risk (system harming itself), not against a
    hostile third party.

    Returns {"path", "is_self", "in_path"} for the caller to report.
    """
    is_self = os.path.realpath(source) == os.path.realpath(target)
    launcher_dir = _gitmem_launcher_dir()
    os.makedirs(launcher_dir, exist_ok=True)
    launcher_path = os.path.join(launcher_dir, "gitmem")

    content = _gitmem_launcher_self_content(source) if is_self else _gitmem_launcher_cache_content()

    fd, tmp_path = tempfile.mkstemp(dir=launcher_dir, prefix=".gitmem-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(tmp_path, 0o755)
        os.replace(tmp_path, launcher_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    path_dirs = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    in_path = any(os.path.realpath(p) == os.path.realpath(launcher_dir) for p in path_dirs)

    return {"path": launcher_path, "is_self": is_self, "in_path": in_path}


# ── Project-memory seeding ───────────────────────────────────────────────

def _seed_project_memory(target: str) -> None:
    """Seed `.claude/project-memory/`'s eight index files with their
    headers [encargo: "no inventes el sembrado: la funcion existe y es
    lib/memory/indexes.py::seed(pm). Llamala."]. Reuses the real seeding
    function the rest of the memory system already writes through —
    idempotent by construction (seed() only creates a file that is
    missing, never touches one that already has notes).
    """
    pm_dir = os.path.join(target, ".claude", "project-memory")
    verify_path_within_project(pm_dir, target)
    indexes.seed(Path(pm_dir))


# ── config.json: deduced repo_type ───────────────────────────────────────

def _write_config_json(target: str, deduced_repo_type: str) -> str:
    """Write or merge `.claude/project-memory/config.json` with the
    deduced repo_type [encargo: "Nunca sobrescribas un config.json que ya
    exista, ni una clave que ya tenga... Si ya existe con repo_type, se
    respeta y se anuncia como respetado"]. config.py's own Config
    dataclass models exactly three keys (customs_enabled, repo_type,
    test_command) — those are the only keys this file can ever hold, so
    merging means: keep every key already present untouched, add
    repo_type only if it is missing.

    A corrupt existing file is never silently treated as empty and
    overwritten — same fail-loud contract as config.py::load()'s own
    docstring ("un fichero corrupto FALLA EN ALTO, nunca devuelve los
    valores por defecto en silencio"): overwriting a corrupt file here
    would risk discarding a repo_type a human already set that just
    happens to sit next to a JSON syntax error. Raises ValueError, caught
    by apply_plan()'s existing per-action try/except and reported as an
    install error instead.

    Returns a one-line message for the Phase 3/5 report.
    """
    pm_dir = os.path.join(target, ".claude", "project-memory")
    verify_path_within_project(pm_dir, target)
    os.makedirs(pm_dir, exist_ok=True)
    config_path = os.path.join(pm_dir, "config.json")

    data: dict[str, Any] = {}
    if os.path.isfile(config_path):
        try:
            with open_no_follow_symlink(config_path, "r") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(
                f"install_apply.py: {config_path} existe y esta corrupto -- "
                f"no se toca sin saber que clave conserva: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise ValueError(
                f"install_apply.py: {config_path} existe pero no es un "
                f"objeto JSON (diccionario) -- no se toca"
            )
        data = raw

    if "repo_type" in data:
        return f"config.json: repo_type={data['repo_type']!r} ya existente, respetado ({config_path})"

    data["repo_type"] = deduced_repo_type
    with open_no_follow_symlink(config_path, "w", atomic=True) as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return f"config.json: repo_type={deduced_repo_type!r} deducido y escrito ({config_path})"
