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

## Boot simplification (issue #63, 2026-07-11)
- CLAUDE.md managed-block gate (`hooks/session-start-crew.py` + `lib/install_apply.py::_update_claude_md()`): content-based, never version-based (decision 2d56444). Both ALWAYS read+diff `lib/managed_blocks.py`'s canonical `BLOCKS` via `upsert_managed_blocks()`; only the WRITE is skipped when content already matches. `manifest.json`'s "version" field is never trusted as a proxy for content correctness.
- Orphaned-END regeneration (a BEGIN marker with no matching END, e.g. from a merge-conflict resolution): fixed "safe by construction" — removes EXACTLY the dangling BEGIN's own line, reinserts the full canonical block in place. Never deletes anything else (verified for first/middle/last block position, above/below gaps). Known accepted residual: leaves the orphaned block's old body as inert duplicate dead text (issue #64, cosmetic, tracked, not destructive).
- Upgrade-check (`lib/upgrade_check.py`, new module) moved from per-message (`hooks/user-prompt-memory-check.py`) to once-per-SessionStart (`hooks/session-start-boot.py`, called AFTER `render_status_section()` so the STATUS line still reports the mismatch it found before the manifest gets synced). Accepted loss: mid-session `/plugin update` no longer detected until next session start.
- `lib/boot_health.py::check_version_mismatch()` (STATUS line source) still compares versions as raw strings, NOT semver — known preexisting bug (byte-identical on main), non-destructive (the real upgrade-trigger oracle `needs_upgrade()` already uses correct semver), tracked as GitHub issue #64 `[T2]` with explicit DoD. Do not treat as a new regression if seen again.
- Single-home discipline ("una regla, un sitio"): `_migrate_runtime_to_unmassk` lives ONLY in `bin/git-memory-upgrade.py` now (the `lib/boot_migrations.py` copy was deleted, not just unwired). `_migrate_untrack_generated_jsons` deleted outright (no upgrade-path duplicate existed).
- CI matrix for this repo: `.github/workflows/toolkit-ci.yml` runs `[ubuntu-latest, windows-latest]` — local-only pytest green (even macOS) has historically NOT been sufficient evidence for a release go/no-go in this project (see judgment-patterns.md 2026-07-10 issue #60); always confirm via `gh run view` on the exact final pushed SHA before treating a branch as release-ready.

## unmassk-toolkit git-memory: read path (recall/boot) is independent of the write-time validation hooks

`lib/parsing.py::scan_trailers_memory()` (recall/boot read path, feeds `recall()`) and `lib/parsing.py::parse_trailers_full()` do NOT call or depend on `hooks/pre-validate-commit-trailers.py::validate_trailers()` in any way — they are separate code paths reading the same commit trailers independently. Confirmed 2026-07-25 (dead-end memory loop judgment): even with the validation hooks structurally dead on the wrapper commit path, memory recall/boot correctness is unaffected. When judging whether a validation-layer gap blocks a feature, check whether the feature's actual read path imports/depends on the broken validator before treating it as blocking.
