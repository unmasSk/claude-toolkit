# Release Script (`bin/release.py`) — Implementation Plan

**Tarea:** roadmap #9 (memo `2c28f49`)
**Branch:** main (repo trunk)
**Triage:** Standard+ (infra de release: muta versiones + git push; riesgo = release roto)
**Build mode:** test-first / ATDD
**Created:** 2026-06-09

## Goal
Un script que orqueste el release de un plugin de punta a punta — bump + CHANGELOG + commit + push + verificación post-push — de forma que `/plugin update` vea la nueva versión, y que se niegue a publicar en estado dudoso (lo que falló hoy: commit sin push).

## Decisions (git-memory)
- `90ee16a` — **CHANGELOG único** en la raíz para todo el marketplace; el script promociona el `## [Unreleased]` raíz a `## [x.y.z] - fecha`. NO por-plugin (anula `db81a89`). Se unificará a futuro.
- `b66f8e1` — **Pre-flight fail-closed**: aborta si tree sucio / `[Unreleased]` vacío / local por detrás del remoto. Flag `--dry-run` para ensayar.
- `e581717` / `377fbee` — push **manual** (el script lo hace como paso explícito); NO hay hook de push-automático.
- Release **por-plugin**: args = `<plugin> <version>`. Reusa `bin/bump-version.py` como autoridad del bump.
- El script **valida y promociona** el changelog, NO inventa contenido (eso lo deja Alexandria antes).

## Contract — `bin/release.py`

CLI: `python3 bin/release.py <plugin> <new-version> [--dry-run] [--allow-dirty]`

**Root del repo:** se resuelve con `git rev-parse --show-toplevel` sobre el CWD (NO con `__file__`), para que sea testeable contra un repo temporal y correcto en uso real.

### Pre-flight (fail-closed — aborta con mensaje claro + exit ≠ 0)
1. Validar `<plugin>` (regex de bump-version) y `<new-version>` (semver).
2. El plugin existe en `marketplace.json` y tiene su `plugin.json`.
3. `new-version` es **estrictamente mayor** que la versión actual (semver hacia delante). Igual o menor → aborta.
4. Working tree limpio → si sucio, aborta (salvo `--allow-dirty`, documentado).
5. La rama tiene upstream configurado → si no, aborta.
6. No estar por detrás del remoto: `git fetch` + `git rev-list HEAD..@{u}` == 0 → si detrás, aborta ("pull first").
7. `CHANGELOG.md` raíz tiene un `## [Unreleased]` con contenido no vacío → si vacío, aborta ("rellena [Unreleased] primero").

### Execute (se OMITE en `--dry-run`; dry-run imprime lo que haría)
1. **Bump:** invoca `bin/bump-version.py <plugin> <version>` (actualiza plugin.json + marketplace.json). Verifica exit 0. *(bump-version.py debe operar sobre el mismo root; ver Task 2b.)*
2. **Promociona CHANGELOG:** inserta `## [x.y.z] - YYYY-MM-DD` capturando el contenido actual de `[Unreleased]`, y deja un `## [Unreleased]` vacío nuevo arriba. Fecha = hoy (`datetime.date.today()`).
3. **Stage:** `plugin.json` del plugin, `marketplace.json`, `CHANGELOG.md` (solo esos tres).
4. **Commit + push:** invoca `git-memory-commit.py chore <plugin> "release v<version>" --trailer Why=... --push`.

### Post-push verify (fail-closed si algo no cuadra)
1. `git rev-list origin/<branch>..HEAD` == 0 (el commit está en el remoto).
2. `marketplace.json[plugin].version` == `plugin.json.version` == `new-version`.
3. Imprime resumen: "/plugin update verá ahora `<plugin>` v<version> en origin/<branch>".

Exit 0 solo si TODO verifica.

## Tasks

### Task 1: Acceptance contract (Dante) — test-first
**Files:** create `unmassk-toolkit/tests/test_release.py`
**Fixture:** repo git temporal con marketplace falso (marketplace.json con 1-2 plugins + dirs con plugin.json + CHANGELOG.md), `git init`, remoto **bare** local, commit inicial, upstream configurado. Reusa patrones de `conftest.py`.
**Casos (el contrato):**
- [ ] Happy path: bumpea, promociona changelog, commitea, pushea, verifica. Asserts: versiones cambiadas en ambos JSON, `[x.y.z]` en changelog + `[Unreleased]` vacío arriba, commit presente en el bare remoto.
- [ ] `--dry-run`: imprime el plan, **cero** cambios, sin commit, exit 0.
- [ ] Aborta (exit ≠ 0, sin mutar nada): tree sucio (sin `--allow-dirty`), versión no-mayor, `[Unreleased]` vacío, plugin inexistente, sin upstream, local por detrás del remoto.
- [ ] `--allow-dirty`: procede pese a tree sucio, pero **solo** stagea los 3 ficheros objetivo.
- [ ] Fallo de push: el commit queda local, exit ≠ 0, mensaje claro (no deja el release "a medias" en silencio).
- [ ] Verify atrapa mismatch: si tras el bump las versiones no coinciden, aborta antes de cantar éxito.

### Task 2: Implement `bin/release.py` (Ultron)
**Depends on:** Task 1 (tests en rojo)
**Files:** create `bin/release.py`; modify `bin/bump-version.py`
- [ ] 2a: Implementar `release.py` según el Contract hasta que TODOS los tests de Task 1 pasen.
- [ ] 2b: `bump-version.py` debe poder operar sobre un root inyectado (override de `REPO_ROOT` vía arg/env, **retrocompatible**: por defecto, comportamiento actual) para que el subproceso del bump golpee el repo temporal en los tests. Extraer helper compartido si queda más limpio (DRY).
- [ ] 2c: Validar reutilizando los validadores de bump-version (semver, plugin name, path-safety). Sin duplicar regex.
- [ ] Verify: `pytest unmassk-toolkit/tests/test_release.py` verde.

### Task 3: Verify (Cerberus + Dante hardening + Moriarty + Yoda)
**Depends on:** Task 2
- [ ] Cerberus: goal-backward — ¿entrega el goal, no solo pasa tests? Estándares (subprocess seguro, error handling, exit codes).
- [ ] Dante: hardening exhaustivo + cobertura (≥90% funciones / ≥80% rutas de error).
- [ ] Moriarty: romper estados parciales — push a medias, fetch que falla, changelog malformado, race con el remoto, `--allow-dirty` filtrando cambios ajenos.
- [ ] Yoda: veredicto production-ready.

### Task 4: Document (Alexandria)
**Depends on:** Task 3 verde
**Files:** create `docs/RELEASING.md`
- [ ] Cómo bumpear/liberar: precondiciones (rellenar `[Unreleased]`), comando, `--dry-run` primero, qué verifica, qué hacer si aborta. Documentado contra el comportamiento REAL del script.

## Resolutions (post-contract, antes de Ultron)
1. **Commit:** `release.py` usa el wrapper `git-memory-commit.py` con trailers válidos (`Why=release v<version>`, `Touched=<paths>`), `--push`. NO `git commit` directo.
2. **Root override:** env var `UNMASSK_REPO_ROOT`. `release.py` resuelve el root con `git rev-parse --show-toplevel` y exporta `UNMASSK_REPO_ROOT` al subproceso de `bump-version.py`. `bump-version.py` lee `os.environ.get("UNMASSK_REPO_ROOT")` y cae al comportamiento `__file__` actual si no está (retrocompatible).
3. **Formato changelog:** exactamente UNA línea en blanco entre `## [Unreleased]` y el nuevo `## [<version>] - <fecha>`. Keep a Changelog canónico.

## Wave Map
- Wave 1: Task 1 (Dante, contrato en rojo)
- Wave 2: Task 2 (Ultron, hasta verde)
- Wave 3: Task 3 (verificación; Cerberus+Dante+Moriarty+Yoda en paralelo)
- Wave 4: Task 4 (Alexandria)
