# Project Conventions — unmassk-toolkit

## Release pipeline
- **Contrato de verdad**: `docs/plan/feat-release-script.md` (sección Contract + Resolutions + "Verify findings")
- **Build mode**: test-first (ATDD). Dante escribe tests en rojo → Ultron implementa hasta verde.
- **Commit de release**: `unmassk-toolkit/bin/git-memory-commit.py` (citado en 2026-06-09) ya no existe -- borrado 2026-08-05 junto al resto del sistema anterior. **No verificado** con qué mecanismo commitea `release.py` hoy (grep de `bin/release.py`/`release_helpers.py` para "commit"/"gitmem" no encontró nada obvio 2026-08-25) -- confirmar contra el código antes de reusar esta afirmación.

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
- `bin/git-memory-doctor.py`: única excepción de LOC documentada, aceptada explícitamente por Bex. Seguridad no comprometida (guards presentes). Verificado 2026-08-25: sigue vivo y ha seguido creciendo — 714 líneas actuales (era 518 en 2026-07-05), sin nueva decisión de Bex registrada sobre el nuevo tamaño. Mismo gap de convención que el de `git-memory-upgrade.py` de abajo, pendiente.
- `bin/git-memory-upgrade.py` (537 líneas en 2026-07-05, creció desde 452 pre-sesión): **[SUSTITUIDO 2026-08-25]** este fichero ya no existe -- borrado el 2026-08-05 (commit `615f5cc`, "borrado el sistema de memoria anterior") como parte de la reescritura completa a memoria-v2/gitmem (ver `CLAUDE.md`: "El sistema anterior está borrado del repositorio"). El gap de convención que documentaba quedó moot con el fichero. La disciplina de LOC-por-función y las excepciones documentadas por Bex siguen aplicando al sistema actual (`bin/gitmem`, `lib/memory/`) -- no verificado en esta pasada si tiene sus propias excepciones registradas.
- Parser de `git log` para memoria (`lib/boot_memory.py`): usa `git log -z` (NUL real de git como separador de REGISTRO) + `\x1f` (separador de CAMPO dentro de un registro, con maxsplit fijo). NUNCA usar un carácter embebible en el mensaje (`\x1e`, etc.) como separador de registro — un commit real SÍ puede contener `\x1e`/`\x1f`/etc, pero NUNCA un NUL crudo (git lo trunca/rechaza en toda capa: commit porcelain, hash-object con fsck, y pretty-print `%b`/`%B` trunca en el NUL incluso si el objeto se fuerza a nivel de loose object). **[fichero borrado 2026-08-25]** `lib/boot_memory.py` ya no existe (borrado 2026-08-05, sistema anterior). El HECHO técnico sobre cómo git trata NUL/`\x1e`/`\x1f` en `git log`/pretty-print sigue siendo verdad universal de git, no del proyecto -- reutilizable si el sistema actual (`lib/memory/gitcmd.py`, no auditado en esta pasada) parsea `git log` de forma parecida.

## Boot simplification (issue #63, 2026-07-11)
- CLAUDE.md managed-block gate (`hooks/session-start-crew.py` + `lib/install_apply.py::_update_claude_md()`): content-based, never version-based (decision 2d56444). Both ALWAYS read+diff `lib/managed_blocks.py`'s canonical `BLOCKS` via `upsert_managed_blocks()`; only the WRITE is skipped when content already matches. `manifest.json`'s "version" field is never trusted as a proxy for content correctness. Verificado 2026-08-25: los 3 ficheros (`session-start-crew.py`, `install_apply.py`, `managed_blocks.py`) siguen vivos hoy, este párrafo sigue vigente.
- Orphaned-END regeneration (a BEGIN marker with no matching END, e.g. from a merge-conflict resolution): fixed "safe by construction" — removes EXACTLY the dangling BEGIN's own line, reinserts the full canonical block in place. Never deletes anything else (verified for first/middle/last block position, above/below gaps). Known accepted residual: leaves the orphaned block's old body as inert duplicate dead text (issue #64, cosmetic, tracked, not destructive). **[cerrado 2026-08-25]** issue #64 verificado CLOSED vía `gh issue view 64` -- el "known accepted residual" ya no es una decisión pendiente, aunque no verifiqué el fix concreto.
- Upgrade-check (`lib/upgrade_check.py`, new module) moved from per-message (`hooks/user-prompt-memory-check.py`) to once-per-SessionStart (`hooks/session-start-boot.py`, called AFTER `render_status_section()` so the STATUS line still reports the mismatch it found before the manifest gets synced). **[fichero borrado 2026-08-25]** `hooks/session-start-boot.py` ya no existe (mismo borrado del sistema anterior, commit `615f5cc`, 2026-08-05) — `lib/upgrade_check.py` y `hooks/user-prompt-memory-check.py` SÍ siguen vivos hoy, pero no verifiqué desde dónde se llama ahora `needs_upgrade()` en el sistema actual.
- `lib/boot_health.py::check_version_mismatch()` (STATUS line source) still compares versions as raw strings, NOT semver — known preexisting bug (byte-identical on main), non-destructive (the real upgrade-trigger oracle `needs_upgrade()` already uses correct semver), tracked as GitHub issue #64 `[T2]` with explicit DoD. Do not treat as a new regression if seen again. **[verificar antes de reusar]** `lib/boot_health.py` sigue vivo (verificado 2026-08-25) e issue #64 está CLOSED — no confirmé si `check_version_mismatch()` recibió el fix semver o si el cierre fue por otra vía (p.ej. el propio fichero cambiando de responsabilidad tras memoria-v2).
- Single-home discipline ("una regla, un sitio"): `_migrate_runtime_to_unmassk` lives ONLY in `bin/git-memory-upgrade.py` now (the `lib/boot_migrations.py` copy was deleted, not just unwired). `_migrate_untrack_generated_jsons` deleted outright (no upgrade-path duplicate existed). **[fichero borrado 2026-08-25]** `bin/git-memory-upgrade.py` ya no existe (ver nota de arriba, borrado del sistema anterior) — este párrafo es histórico, la disciplina "una regla, un sitio" en sí sigue siendo el criterio a aplicar en el sistema actual.
- CI matrix for this repo: `.github/workflows/toolkit-ci.yml` runs `[ubuntu-latest, windows-latest]` — local-only pytest green (even macOS) has historically NOT been sufficient evidence for a release go/no-go in this project (see judgment-patterns.md 2026-07-10 issue #60); always confirm via `gh run view` on the exact final pushed SHA before treating a branch as release-ready. Verificado 2026-08-25: el workflow sigue existiendo tal cual, regla vigente.

## [HISTÓRICO — premisa ya no aplica] unmassk-toolkit git-memory: read path (recall/boot) is independent of the write-time validation hooks

`lib/parsing.py::scan_trailers_memory()` (recall/boot read path, feeds `recall()`) and `lib/parsing.py::parse_trailers_full()` do NOT call or depend on `hooks/pre-validate-commit-trailers.py::validate_trailers()` in any way — they are separate code paths reading the same commit trailers independently. Confirmed 2026-07-25 (dead-end memory loop judgment): even with the validation hooks structurally dead on the wrapper commit path, memory recall/boot correctness is unaffected. When judging whether a validation-layer gap blocks a feature, check whether the feature's actual read path imports/depends on the broken validator before treating it as blocking.

**[SUSTITUIDO 2026-08-25]** `hooks/pre-validate-commit-trailers.py` ya no existe -- borrado el 2026-08-05 (commit `615f5cc`, reescritura completa a memoria-v2/gitmem, ver `CLAUDE.md`). `lib/parsing.py` sigue vivo pero no verifiqué si `scan_trailers_memory()`/`parse_trailers_full()` siguen siendo las funciones reales del read path actual, o si el nuevo sistema `gitmem`/`lib/memory/` las reemplazó. El PATRÓN de juicio ("verificar si el read path real depende del validador roto antes de bloquear por eso") sigue siendo válido como técnica y se conserva por eso -- el hecho concreto que describía (este validador específico, muerto pero presente) ya no existe ni como código muerto.

## Git-safety HARD RULE en claude-git-memory (unmassk-toolkit/) -- vale para MI, no solo para Ultron

`.claude/agent-memory/unmassk-toolkit-ultron/MEMORY.md` (tope del fichero): NUNCA `git stash`, `git reset`,
`git checkout -- <path>`, `git restore`, ni ningún comando que mueva/mute el árbol de trabajo en este repo --
ni siquiera acotado a un path, ni siquiera "solo para mirar". Dos sesiones de trabajo sin commitear conviven
en el mismo árbol (varios agentes construyendo en paralelo a petición del propietario). Ya pasó dos veces
antes de esta sesión (ver lessons.md de Ultron) y una tercera vez conmigo -- las tres veces recuperadas por
suerte (fsck de commits colgantes, nunca garantizado). Lectura pura de git (`status`, `diff`, `log`, `show`)
siempre es segura -- la prohibición es sobre cualquier cosa que mueva el árbol. Para una comparación
antes/después de un fichero real: copiar a variable en memoria (Python `open().read()`), mutar/restaurar
por escritura directa, nunca por comando git que mute el índice o el árbol.

**Mi propio incidente (2026-08-06), fusionado aquí desde el antiguo lessons.md (fichero huérfano, nunca
enlazado en MEMORY.md -- rescatado en la compactación 2026-08-25):** verificando "N fallos preexistentes"
vía `git stash push -u -- <ficheros>` (patrón que documenté como válido para OTRO repo el 2026-07-06) y
después un `git checkout -- unmassk-toolkit/hooks/customs.py` para deshacer una mutación mía de prueba
(kill-test del reordenamiento determinista), destruí sin darme cuenta el diff real de producción de ese
fichero -- `git checkout --` restaura a HEAD entero, no solo deshace mi mutación, así que se llevó por
delante el trabajo real de Ultron también. Recuperación: `git stash pop` sí había funcionado limpio antes
(diff idéntico confirmado), pero el `checkout --` posterior no tenía stash que revertir -- se recuperó con
`git fsck --unreachable --no-reflog`, encontrando el SHA de commit del stash ya dropeado (`0acfb3c9...`,
todavía no recolectado por gc) y `git show <sha>:<path> > <path>` para restaurar el blob exacto (verificado
byte a byte: mismo hash de blob `61c2f02` que el diff original). Sin ese commit de stash todavía vivo en el
object store, la pérdida habría sido irreversible desde mi lado. **Regla que adopto para cualquier repo, no
solo este:** antes de cualquier prueba de mutación/kill-test o comparación antes/después sobre un fichero de
producción real (no una copia), buscar primero si existe una convención de seguridad de git documentada en
la memoria de otros agentes del mismo repo (`grep "HARD RULE"\|"git stash"\|"git checkout"` en
`.claude/agent-memory/*/MEMORY.md` y topic files). El patrón correcto para una mutación temporal es escribir
la versión mutada con Python (`open(path).write(...)`) tras guardar el contenido original en una variable en
memoria, y restaurar escribiendo esa misma variable de vuelta -- nunca `git checkout --`/`git stash`, ni
siquiera "solo para revertir mi propio cambio", porque en un árbol de trabajo compartido ese comando no
distingue "mi cambio" de "el cambio real que ya estaba ahí".

## lib/memory/vocabulary.py::FIELDS[x].reader es "el mas directo", no "el unico" -- por diseno

El propio docstring de `vocabulary.py` (parrafo "Tabla campo -> lector") dice explicitamente
que cuando ARQUITECTURA.md Sec.6 lista mas de un lector real para un campo, `FIELDS[x].reader`
copia solo el PRIMERO -- no es una afirmacion de que solo exista un lector, es una eleccion de
cual citar. Antes de marcar como "documentacion desfasada" que un campo tenga un segundo lector
real no listado (ej. `report_render.py` leyendo `note.issue` ademas de `health.plans_unreflected`),
comprobar este parrafo -- puede ser exactamente el caso previsto, no una deriva.

## Un hallazgo fuera del diff, en la misma working tree, no bloquea el veredicto de la feature -- pero se reporta aparte

2026-08-22 (--issue abierto a los siete tipos, D-044/D-045): mientras revisaba el diff de la
feature encontre que `.claude/agent-memory/unmassk-toolkit-dante/MEMORY.md` (fichero de otro
agente, tocado en la misma sesion para anadir 3 lineas nuevas legitimas) tenia sus ~102 lineas
PREEXISTENTES truncadas mecanicamente a mitad de palabra frente a HEAD (confirmado con
`git show HEAD:<ruta>` byte a byte, no una sospecha) -- perdida real de contenido en un indice
de memoria, justo el eje que este proyecto mas protege. No bloquee el veredicto de la feature
(codigo/tests de `lib/memory/vocabulary.py` etc. intactos y correctos, la corrupcion no la causo
esta logica) pero lo marque como condicion explicita a resolver antes de comitear el lote --
memory es un commit y no se reescribe, asi que si esto entra sin corregir queda para siempre.

## Round-trip real en customs.py / stop-dod-gate.py / zones.py list / doctor.py: subprocess real, no mock

Los 4 ficheros de test tocados en la tanda del 2026-08-06 (`test_customs_hook.py`, `test_stop_dod_gate.py`,
`test_zones_script.py`, `test_doctor_derived_expectations.py`) invocan el hook/script REAL como proceso aparte
(`subprocess.run([sys.executable, HOOK_PATH], ...)` o equivalente) contra ficheros REALES en un repo temporal
(`tmp_repo`/`tmp_path`), nunca contra un mock del parser de JSON o del filesystem. `zones.py`'s `_cmd_list` y
`git-memory-doctor.py`'s `check_project_zones`/`check_project_config` se prueban con `zones.json`/`config.json`
corruptos escritos byte a byte en disco (marcadores de conflicto de merge sin resolver, tipos JSON equivocados)
-- satisface la Regla de Evidencia de Round-Trip sin necesitar reconstruir el seam yo mismo, aunque lo repetí
de todas formas para los 2 hallazgos T1 de Moriarty (ver judgment-patterns.md).

**Estado 2026-08-25**: `hooks/stop-dod-gate.py` y su `test_stop_dod_gate.py` ya no existen (el hook se borró
`5f6b513`, 2026-08-23, "fuera los seis ficheros del guardian"). `test_customs_hook.py` y `test_zones_script.py`
siguen vivos pero se mudaron a `tests/memory/`. `test_doctor_derived_expectations.py` sigue en `tests/`. La
TÉCNICA (subprocess real contra ficheros reales, nunca mock del parser) sigue siendo el criterio a aplicar a
cualquier hook/script actual con round-trip -- se conserva por eso, no por el hook concreto que ya no existe.
