# Project Conventions — unmassk-toolkit

## Release pipeline
- **Contrato de verdad**: `docs/plan/feat-release-script.md` (sección Contract + Resolutions + "Verify findings")
- **Build mode**: test-first (ATDD). Dante escribe tests en rojo → Ultron implementa hasta verde.
- **Commit de release**: vía `unmassk-toolkit/bin/git-memory-commit.py` sin `--push`; push separado con `git push` directo.

## Estándares de código
- Funciones ≤ 50 LOC (ninguna lo supera en release.py ni helpers)
- release.py ≤ 300 LOC (298 real)
- release_helpers.py: objetivo 300, actual 346 (aceptado por extracción forzada)
- shell=True: prohibido (verificado, no hay ninguno)
- subprocess: siempre lista de args + timeout de 60s

## Semver
- SEMVER_RE estricto: prohíbe leading zeros en major/minor/patch
- _semver_key: sin pre-release > con pre-release (semver 2.0.0 §11)
- Precedencia: `(major, minor, patch, (1,))` para final vs `(major, minor, patch, (0, ...ids))` para pre-release

## Path safety
- Path traversal: verificado en _preflight_resolve_paths y bump-version.safe_plugin_path
- REPO_ROOT: resuelto con git rev-parse --show-toplevel (no __file__) en release.py
- UNMASSK_REPO_ROOT: env var de override para tests (bump-version.py retrocompatible)

## Symlink safety architecture (boot hook hardening, 2026-07-05)
- Chokepoint: `lib/git_helpers.py::verify_path_within_project(path, project_root)` — realpath ambos, compara prefijo con os.sep, protege también componentes intermedios simlinkeados (no solo el componente final). Usado en `ensure_runtime_dir()` y en cualquier sitio que cree/toque `.claude/` o `.claude/.unmassk/` directamente.
- Guard de componente final: `open_no_follow_symlink(path, mode)` en `lib/git_helpers.py` (con fallback en `lib/_symlink_safe_open.py` para módulos que se cargan de forma standalone en tests) — O_NOFOLLOW simétrico en lectura y escritura.
- Regla de diseño: los dos guards son complementarios, NUNCA sustitutos uno del otro — un guard de componente final no protege si el directorio PADRE (ej. `.claude` mismo) es el symlink.
- `bin/git-memory-doctor.py` (518 líneas): única excepción de LOC documentada, aceptada explícitamente por Bex. Seguridad no comprometida (guards presentes).
- `bin/git-memory-upgrade.py` (537 líneas, creció desde 452 pre-sesión): gap de convención SIN decisión explícita — pendiente que Bex decida si se acepta como 2ª excepción o se divide.
- Parser de `git log` para memoria (`lib/boot_memory.py`): usa `git log -z` (NUL real de git como separador de REGISTRO) + `\x1f` (separador de CAMPO dentro de un registro, con maxsplit fijo). NUNCA usar un carácter embebible en el mensaje (`\x1e`, etc.) como separador de registro — un commit real SÍ puede contener `\x1e`/`\x1f`/etc, pero NUNCA un NUL crudo (git lo trunca/rechaza en toda capa: commit porcelain, hash-object con fsck, y pretty-print `%b`/`%B` trunca en el NUL incluso si el objeto se fuerza a nivel de loose object).
