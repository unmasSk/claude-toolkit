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
