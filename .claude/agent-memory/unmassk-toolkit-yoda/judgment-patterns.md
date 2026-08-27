# Judgment Patterns

## Nota de vigencia (compactación 2026-08-25) — lee esto antes de citar un file:line de abajo

Este fichero es un registro cronológico de veredictos reales. La mayoría de las entradas de
2026-06-09 a 2026-07-25, más las de 2026-08-06 y 2026-08-20, juzgan el sistema de memoria/boot
ANTERIOR (`hooks/session-start-boot.py`, `lib/boot_git_checks.py`, `lib/boot_memory.py`,
`lib/boot_glossary_cache.py`, `lib/boot_fetch_stamp.py`, `bin/git-memory-upgrade.py`,
`bin/git-memory-commit.py`, `bin/git-memory-gc.py`, `lib/bootstrap_commits.py`,
`hooks/pre-validate-commit-trailers.py`, `hooks/stop-dod-gate.py`) — **borrado del repositorio**:
el grueso el 2026-08-05 (commit `615f5cc`, "borrado el sistema de memoria anterior y retirada su
documentacion de obra", reescritura completa a memoria-v2/gitmem — ver `CLAUDE.md`: "El sistema
anterior está borrado del repositorio"), y `hooks/stop-dod-gate.py` aparte el 2026-08-23 (commit
`5f6b513`, "fuera los seis ficheros del guardian"). Verificado por mí mismo con `find`/`git log
--diff-filter=D` el 2026-08-25, no de memoria.

**Antes de reutilizar cualquier cita de file:line de una entrada anterior a 2026-08-06, comprobar
primero si el fichero sigue existiendo** (`find`/`ls`) — si no existe, el HECHO concreto que
describía ya no es verificable contra el código actual, pero la TÉCNICA de verificación (cómo
reproducir un sabotaje en vivo, cómo leer un canal de CI, cómo distinguir narración de evidencia)
sigue siendo válida y reutilizable contra el sistema actual (`bin/gitmem`, `lib/memory/`).
Ficheros confirmados que SÍ sobrevivieron ambas reescrituras y siguen siendo el código real hoy:
`lib/git_helpers.py`, `lib/install_apply.py`, `lib/parsing.py`, `lib/upgrade_check.py`,
`lib/boot_health.py`, `lib/managed_blocks.py`, `hooks/session-start-crew.py`, `hooks/customs.py`,
`hooks/user-prompt-memory-check.py`, `bin/git-memory-doctor.py` (creció a 714 líneas, era 518 en
2026-07-05), `bin/release.py`+helpers (repo root). Las entradas de 2026-08-22 en adelante (`--issue`
en los siete tipos de nota, I-003 rules.py split, textnorm.py) ya juzgan el sistema `lib/memory/`
actual — verificadas vigentes.

## 2026-06-09 — Release script (release.py + release_helpers.py)

**Pattern: verificar fixes de Moriarty directamente en código, no en tests.**
Los T1 de Moriarty (--allow-dirty stage leak; pre-release block) se verificaron:
1. Leyendo `_execute_stage`: `git reset -q` antes de `git add --` = limpieza real del índice.
2. Ejecutando `_semver_key` con valores reales: `(1,4,0,1)` > `(1,4,0,0,(1,'rc1'))` = semver 2.0.0 correcto.

**Pattern: orphaned helpers no son bugs si tienen uso interno.**
`_semver_key`, `_validate_semver`, `_validate_plugin_name` no se importan en release.py
pero sí se usan internamente en release_helpers.py. Son helpers de soporte, no código muerto.

**Pattern: comentario PENDIENTE estale es ruido, no bloqueante.**
El `PENDIENTE T2.1` en `_preflight_check_not_behind` refiere a una nota de iteración anterior.
El comportamiento actual (fetch falla → _die) es correcto y está cubierto por TestT21FetchFailClosed.

**Pattern: 346 LOC en helpers justificable cuando release.py es 298.**
La extracción forzó parte del presupuesto al módulo de soporte. 346 LOC con 71 blancos + 24 docstring markers
= ~238 LOC de código real. Justificable por la necesidad de mantener release.py bajo 300.

**Pattern: push failure -> ADVERTENCIA en stderr + _verify exit 2 (no exit 1).**
El push no hace sys.exit directamente. La función cae a _verify() que detecta HEAD adelantado
y sale con EXIT_VERIFY_FAIL=2. El contrato de exit codes (0/1/2) se mantiene.

## 2026-07-04 — Boot hook stdout truncation fix (session-start-boot.py)

**Pattern: un fix que arregla el caso diagnosticado puede dejar viva la misma clase de bug por otra puerta.**
El fix capa el stdout a banner solo si `len(full_text) > 6000 bytes`. Pero el bug real
era que el harness trunca el PREVIEW a ~2KB, y el offset de la línea `Next:` dentro del
stdout depende del contenido de secciones ANTERIORES (STATUS/BRANCH/SCOPES), no del total.
Repro propio: 25 scopes con descripciones realistas (sin ningún campo gigante, sin
tocar el trigger que Cerberus/Dante probaron) → total 3193 bytes (bajo el umbral de 6000,
modo inline) pero `Next:` aparece en el offset 2491 — ya truncado por el harness real.
Nadie en el pipeline probó esta zona intermedia: los tests de Dante y la nota de Ultron
solo miden "tamaño total vs 6000", nunca el offset de `Next:` dentro del prefijo real
que el harness previsualiza. SCOPES es la única sección del hook sin MAX_* (todas las
demás — decisions, memos, remembers, timeline — sí lo tienen).
**Regla aprendida**: cuando el contrato de un fix es "X nunca se pierde", verificar el
invariante en el punto exacto donde se re-crea el bug (offset de X dentro del prefijo
truncado), no solo el proxy que el fix usa como guardia (tamaño total). Un proxy más
permisivo que el límite real dejará ventanas sin cubrir.

**Pattern: round-trip evidence verificado a mano, no solo vía pytest.**
Repetí manualmalmente (no confié en el reporte de Ultron ni en el conteo de pytest):
(1) éxito: escritura + banner correcto, log íntegro (grep del marcador de 2100 chars).
(2) fallo real (chmod 500 en `.claude` antes de que exista `.unmassk`): stdout cae a
imprimir el contenido íntegro inline, sin mencionar un archivo que nunca se creó.
(3) `git-memory-commit.py` rechaza subject >100 chars con exit 1 y no crea commit.
Los 9 fallos de test_release.py se confirmaron pre-existentes reproduciendo el mismo
error en un `git worktree` del commit anterior al pipeline completo (7534247^) — mismos
9 nombres, mismo `ModuleNotFoundError: No module named 'bin.release_helpers'`.

**Pattern: cuidado con archivos ya modificados en el working tree que no son míos.**
Encontré `CHANGELOG.md` y `SKILL.md` con ediciones de documentación sin commitear,
escritas ~1 min antes de mi verificación (aparentemente Alexandria u otro proceso
adelantándose fuera de orden de pipeline — Alexandria debería correr DESPUÉS de mi
veredicto). Las dejé intactas (nunca las toqué con git checkout/reset), solo lo
reporté como observación de secuencia, no como bloqueante de mi juicio sobre el código.

## 2026-07-04 (ronda 2) — Boot hook: umbral eliminado, no ajustado

**Pattern: cuando el hallazgo Major es "el proxy no mide el punto real del bug",**
**la única corrección aceptable es borrar el proxy, no afinarlo.**
Bex decidió eliminar STDOUT_FULL_INLINE_BUDGET_BYTES por completo en vez de
bajar el umbral o medir el offset de `Next:` en vez del total. Verificado
en código (`session-start-boot.py:1340-1367`): el único camino que imprime
contenido completo en stdout es el fallback de escritura fallida
(`if not boot_log_path`) — el resto es un `else` incondicional. Repetí mi
propio repro de 25 scopes (3193 bytes) contra el código actual: banner de
700 bytes, sin "Next:" inline, contenido íntegro en el log file. El hallazgo
Major que yo mismo levanté ya no puede ocurrir porque no queda ninguna
condición que evaluar — no es que el umbral ahora sea más estricto, es que
no hay umbral.

**Pattern: verificar migración de tests "cosmética vs real" con grep dirigido.**
Cuando un agente reporta "migré N tests de stdout a archivo de log", no basta
con que pasen en verde — un test puede seguir aserting contra `output` (stdout)
y además leer el log sin que la aserción vieja se haya borrado. Grep dirigido:
`grep -n "assert.*output"` en los 5 archivos migrados, filtrado por los
strings que antes vivían solo en stdout (👑, CONSOLIDATE, tombstone) → cero
resultados, y confirmé por separado que sí llaman a `_read_boot_log`/leen
`boot-log-latest`. Las dos búsquedas juntas prueban migración real, ninguna
por sí sola lo hace.

## 2026-07-05 — Boot hook pipeline final judgment (14 rondas Cerberus/Argus, sin Moriarty)

**Pattern: verificar un fix de "record injection via control bytes" con un objeto git crafteado a mano, no con mocks.**
Para confirmar el crítico SEC-CRIT-NEW-01 (forjado de registro falso en el parseo de `git log`)
no basta con leer el código o correr el test suite existente. Repro propio en 3 pasos:
(1) Intenté embeber un byte NUL real (`\x00`) en el body de un commit vía `git commit` normal
y vía `git hash-object` — AMBOS lo rechazan (`fatal: refusing to create malformed object`,
incluso con `fsck.nulInCommit=ignore`). Pero además, aunque se fuerce el NUL escribiendo el
objeto suelto directamente en `.git/objects/` (bypaseando toda validación de git), `git log
--format=%b` TRUNCA el mensaje en el NUL — un hallazgo técnico nuevo: NUL nunca puede ser el
vector de esta clase de ataque porque git lo trunca en la capa de pretty-print, con o sin `-z`.
(2) El byte real explotable es `\x1e` (RS, el separador que el código VIEJO usaba) — SÍ
sobrevive intacto en un commit real y en la salida de `git log`. Escribí un objeto commit
crafteado a mano (loose object en `.git/objects/`, sha real vía sha1+zlib) con `\x1e` +
campos `\x1f` falsos (sha/subject/decision forjados) embebidos en el body de un commit
legítimo, actualicé `refs/heads/main` a ese commit, y corrí `boot_memory.extract_memory()`
tal cual vive en el repo. Resultado: el diccionario devuelto solo contiene la Decision
legítima; el sha/subject/decision forjados NUNCA aparecen — el fix (`git log -z` con NUL
real como separador de registro, `\x1f` solo como separador de campo con maxsplit fijo)
sostiene bajo ataque real, no solo bajo el test que Dante escribió.
(3) Symlink de `.claude/settings.json`: creé un repo real donde `.claude` es un symlink
real (no mock) a un directorio externo con un `settings.json` que simula el real (~/.claude)
con hooks de otro plugin. Llamé a `_cleanup_stale_settings_hooks()` tal cual vive en
`lib/install_apply.py` — `UnsafePathError` se lanza, el archivo externo queda intacto byte
a byte, y `apply_plan()` captura la excepción sin abortar el resto del install.

**Pattern: mutation testing en vivo sobre el fix reportado por Cerberus, no confiar en "confirmado con prueba de mutación real" del commit message.**
Neutraliza a mano el guard (`if root: verify_path_within_project(...)` → `if False: ...`)
en `lib/boot_glossary_cache.py`, corrí el test específico
(`TestBugAOEnsureRuntimeDirFallbackBranchSymlinkedParent`), confirmé que se pone ROJO
(el archivo SÍ se escribe fuera del repo con el guard neutralizado), `git checkout --` para
restaurar, confirmé verde de nuevo. La afirmación de la ronda de Cerberus se sostiene.

**Pattern: verificar "9 fallos preexistentes, sin relación" con un worktree, no de memoria.**
`git worktree add <scratch> <sha-pre-pipeline> --detach` al commit de release anterior al
inicio de la sesión (v1.15.0, `f1dcb8e`), correr solo `tests/test_release.py` ahí: mismos
9 nombres de test, mismo `ModuleNotFoundError: No module named 'bin.release_helpers'`.
Confirma que no son causados por el trabajo de esta noche. `git worktree remove --force`
al terminar para no dejar basura.

**Pattern: pipeline sin Moriarty no es automáticamente un blocker si Yoda hace la verificación adversarial él mismo.**
Esta sesión corrió Dante (contrato TDD) → Ultron → Cerberus/Argus en 14 rondas iterativas,
SIN una ronda separada de Moriarty. Dado que Dante ya escribía tests que explotaban
literalmente el bug real en cada ronda (no solo happy-path), y que Yo reproduje en vivo
los 2 ataques de mayor severidad histórica contra el código actual (no contra mocks),
consideré esto equivalente en sustancia a un pase de Moriarty sobre los vectores más
críticos — lo señalé como gap de proceso en el veredicto (Observación), no como bloqueante.

**Pattern: line-count convention drift durante hardening de seguridad — revisar TODOS los bin/*.py, no solo los que el orquestador ya señaló.**
`bin/git-memory-doctor.py` (518 líneas) fue la única excepción documentada/aceptada por Bex.
Pero `bin/git-memory-upgrade.py` creció de 452 (en f1dcb8e, antes de esta sesión) a 537
líneas por los mismos guards de seguridad añadidos esta noche — nadie lo dividió ni lo
declaró como segunda excepción. Los guards SÍ están presentes (12 usos de
verify_path_within_project/open_no_follow_symlink) — no es un hueco de seguridad, es un
hueco de convención/mantenibilidad sin decisión explícita. Encontrado corriendo
`wc -l bin/*.py` y comparando contra el commit pre-sesión, no por lectura línea a línea.

## 2026-07-06 — Windows cross-platform fix (git_helpers.py / _symlink_safe_open.py)

**Pattern: cuando Moriarty no deja evidencia del Round-Trip Sabotage obligatorio (§34), hazlo tú mismo antes de aplicar la Round-Trip Evidence Rule.**
El plan declaraba el seam (fichero escrito y releído, encoding UTF-8) y Moriarty
reportó el modelo de amenaza DEFENDIDO, pero sus notas de memoria (attack-patterns.md,
resilience.md) solo registraban pruebas happy-path/mockeadas para el round-trip de
encoding — ninguna mostraba el paso 2 obligatorio de su propio protocolo ("sabotea la
dependencia real, no el test"). En vez de rechazar mecánicamente por falta de prueba
o de aceptar la palabra del agente, reproduje el sabotaje yo mismo: revertí el fix
(quité `encoding="utf-8"` de una copia de `run_git`), forcé `PYTHONUTF8=0` en un
subproceso real, e hice un commit real con acentos/emoji vía `git commit`. Confirmé
por un canal independiente (bytes crudos del stdout de git, decodificados a mano)
que el contenido real es UTF-8 válido, y que la versión sin el fix SÍ produce mojibake
real bajo esas condiciones (`ðŸ”§` en vez de 🔧) — probando que el
test de round-trip de Dante (`TestEncodingIndependentOfPythonUtf8Env`, que SÍ corrí yo
mismo y vi en verde contra el código actual) no es teatro: de verdad detectaría esta
clase de regresión si volviera a ocurrir.

**Pattern: un residual de seguridad recién descubierto por Moriarty fuera del modelo de
amenaza declarado no bloquea si es estructuralmente igual a un residual ya aceptado.**
El hard-link bypass (`os.link` sobre el path objetivo) que Moriarty encontró rompe
tanto `os.path.islink()` (Windows) como `O_NOFOLLOW` (POSIX) porque un hard link es
indistinguible del archivo original a nivel de sistema de ficheros — no es un bug de
ESTE parche, es una limitación arquitectónica del diseño completo del guard
"detección por identidad/symlink", presente desde antes de esta sesión. Lo reproduje
en vivo (`os.link` real + `open_no_follow_symlink` real): escribe sin OSError, sobre
el contenido de la víctima. Mismo patrón de aceptación que el residual F5 (O_CREAT
TOCTOU, decisión `75fdb2f`): requiere que el atacante YA tenga escritura local previa
— un modelo de amenaza materialmente más débil que el declarado (symlink vía git
checkout). Condición, no bloqueo: debe documentarse en el docstring con el mismo rigor
que F5 (hoy solo vive en la memoria de Moriarty, no en el código).

**Pattern: la lista de "ficheros a tocar" de un plan puede ser un superset obsoleto — verificar antes de marcar como hueco.**
El plan (`docs/plan/fix-windows-crossplatform.md`) listaba 4 ficheros
(`install_apply.py`, `install_inspect.py`, `bootstrap_deps.py`, `boot_git_checks.py`)
como pendientes de recibir `encoding="utf-8"` explícito, pero el diff real no los toca.
Grep confirmó que los 4 usan EXCLUSIVAMENTE `open_no_follow_symlink()` para I/O de
ficheros, cuya firma ya tiene `encoding: str = "utf-8"` por defecto desde antes de esta
sesión — no hay hueco, el diagnóstico original (House, pre-sesión) enumeró líneas de
una fase de diagnóstico anterior a la centralización del choke point. Verificado
leyendo cada línea citada, no asumido.

**Pattern: verificar "N fallos preexistentes" con `git stash` (no worktree) cuando el cambio vive en el working tree sin commitear.**
`git worktree add` requiere un commit; con cambios sin commitear se usa
`git stash push -u -- <ficheros del fix>` (stash SOLO los ficheros del parche, dejando
memoria de otros agentes intacta), correr la muestra de tests, `git stash pop`,
verificar `git diff --stat` idéntico al estado original. Reproduje 9/9 fallos de una
muestra con el mismo `WinError 1314` exacto en el código pre-patch.

## 2026-07-06 (ronda 2) — Re-evaluación del fix cross-platform (96 → 101/110), go/no-go v1.16.1

**Pattern: verificar "condición documentada" comparando las DOS gemelas línea a línea, no solo una.**
La condición 1 del veredicto anterior (documentar el residual hard-link con el mismo rigor que F5)
se verificó leyendo AMBOS docstrings (`git_helpers.py::open_no_follow_symlink` y
`_symlink_safe_open.py::open_no_follow_symlink_fallback`) con `git diff HEAD`, confirmando que el
texto F6 (hard-link bypass) aparece en los dos con el mismo nivel de detalle (por qué islink() y
O_NOFOLLOW no lo detectan, mismo modelo de amenaza que F5, git no puede commitear un hard-link).
No basta con que UNA de las gemelas tenga la nota — la asimetría original era exactamente eso.

**Pattern: una decisión de "no cerrar un hallazgo de seguridad" puede ser DEFENDIBLE si está escrita
como decisión formal con alternativa de diseño explícita, no solo "lo dejamos para después".**
Commit `51a3c44`: Argus diseñó el cierre de F6 (parámetro opt-in `reject_hardlinks` + `st_nlink>1`)
y ÉL MISMO destapó el riesgo de falsos positivos en ficheros de usuario con hard-links legítimos
(worktrees). La decisión de diferir es sólida porque (a) viene con el diseño alternativo ya pensado,
no una excusa, (b) el riesgo aceptado es exactamente el mismo modelo de amenaza que F5 (ya aceptado),
(c) low risk explícito, (d) issue de seguimiento dedicado, no silencio. Verifiqué con `grep
reject_hardlinks|st_nlink` que NO quedó código a medio implementar (solo la mención en docstring de
la opción descartada) — importante: una decisión de diferir debe dejar CERO código huérfano de la
opción no tomada.

**Pattern: verificar un fix de "test teatro" repitiendo el sabotaje YO MISMO, no confiando en el
reporte de Moriarty/Dante aunque esté bien escrito.**
Moriarty documentó (attack-patterns.md + resilience.md) que
`test_run_git_round_trips_utf8_accents_and_emoji_through_real_git` pasaba en verde incluso con
`encoding="utf-8"` borrado de `run_git()`, porque corría bajo el `PYTHONUTF8=1` ambiental de esta
máquina. Dante lo reescribió para forzar `PYTHONUTF8=0` en un subproceso hijo. En vez de aceptar el
reporte, repetí el sabotaje a mano: parcheé `git_helpers.py` real (borré `encoding="utf-8"` del
`subprocess.run`), corrí SOLO esa clase de test → 2 failed (incluyendo el round-trip, con mojibake
real `ðŸ”§ ... corazÃ³n`), restauré el fichero desde backup, confirmé 4 passed de nuevo y
`git diff --stat` idéntico al original. Esto es lo que exige la Round-Trip Evidence Rule: canal
que yo leo directamente, no narración de otro agente.

**Pattern: un hallazgo NUEVO (fd leak + destructive-truncate-before-check) que ningún agente incluyó
en el resumen de "qué cambió" puede aparecer solo leyendo el diff real — Dante sí lo documentó en su
propio archivo de memoria (edge-cases.md) aunque no estaba en la lista que el orquestador me dio.**
`_open_no_follow_symlink_windows()` truncaba con `os.ftruncate(fd,0)` ANTES de que el chequeo
lstat/fstat pudiera rechazar una carrera TOCTOU — un guard que rechaza correctamente con OSError
podía igual destruir el contenido real de la víctima. Fix: truncar solo DESPUÉS de que la
comparación de identidad pase, todo envuelto en `try/except BaseException: os.close(fd); raise`.
Verificado con `TestDeferredTruncateOnIdentityMismatch` y `TestFstatFailureFdLeak` (ya no
`xfail(strict=True)`, ahora un pin verde normal) — ambos en el run de 46 passed.

**Puntuación actualizada (96 → 101/110):**
- Security 8→9: asimetría de documentación resuelta + destructive-truncate cerrado + F6 diferido
  con decisión formal y sólida. No sube a 10: F6 sigue siendo un hueco real sin ningún check en
  tiempo de ejecución (ni siquiera opt-in), en ambas plataformas.
- Error Handling 9→9 (sin cambio): el hueco específico que sostenía el 9 (decode-fail
  indistinguible/silencioso) está cerrado y verificado (test de stderr), pero el `except
  (SubprocessError, OSError, ValueError)` genérico sigue sin ningún rastro a stderr para el resto
  de causas — deliberado y documentado, pero sigue siendo un hueco real articulable, así que no
  sube a 10.
- Architecture 9→9 (sin cambio): la decisión de diferir F6 sin bolt-on refuerza la disciplina de
  scope ya reconocida antes, no añade evidencia nueva para subir.
- Testing 9→10: Moriarty ejecutó y documentó el Round-Trip Sabotage formal él mismo esta ronda
  (no tuve que suplirlo como en la ronda 1), y el hallazgo de teatro que él mismo destapó fue
  arreglado por Dante y reverificado por mí de forma independiente. No encontré ningún hueco
  adicional articulable tras el barrido — primer 10/10 de esta sesión.
- Maintainability 9→9 (sin cambio): nada nuevo que mueva la aguja; sigue siendo "gusto sin
  defecto concreto", igual que antes.

**Veredicto:** READY WITH CONDITIONS (no bloqueante) para v1.16.1 — go de publicación. Única
condición: abrir issue dedicado para el diseño de cierre de F6 (`reject_hardlinks`/`st_nlink>1`),
sin bloquear el release. Los ~68-77 fallos de `test_security_regression.py` (WinError 1314, sin
privilegio de symlink en este host Windows) siguen siendo la misma clase preexistente, reconfirmada
en vivo esta ronda (no ficticia, no relacionada con este fix).

## 2026-07-06 — Boot memory freshness multi-machine (issue #49) final judgment, 100/110

**Pattern: §34 gate on a fetch/read seam — verify with a real bare remote + real subprocess, never trust the agent's narration of "tests pass".**
Ran `pytest test_boot_freshness.py test_boot_freshness_hardening.py test_boot_freshness_regression.py`
myself (107 passed, then full suite 979/979 passed, run twice — once via a background task that
returned late, once synchronously to get the number directly). Read `TestIncidentBehindShowsRemoteNext`
directly: expected values (`INCIDENT_NEXT_MARKER`, `COMMITS_BEHIND_INCIDENT`) are constants the test
itself uses to WRITE the producer's commits (`_push_commits_from_b`), then asserts the SAME constants
appear in the consumer's (real boot hook subprocess) combined stdout+log output — no hand-typed
literal anywhere in the assertion chain. This is the textbook §34.2 pass: expected value traces to
this run's write, not to a captured/memorized "what it usually says".

**Pattern: when Moriarty's own memory notes show more live sabotage than any single report claims, cross-read his topic files directly instead of trusting a one-line "AGUANTA" summary.**
`attack-patterns.md`/`resilience.md` for this feature show ~6 rounds of real bare-remote/2-clone
triangulation, a real hung TCP listener + `ps`-confirmed process-tree kill, a real corrupted
`.git/refs/remotes/origin/main` SHA, `touch -t` clock-skew on FETCH_HEAD, and a genuinely unrelated
second bare repo used to reproduce the repo-identity (merge-base) T2 — each with an explicit
independent-verification channel (ps, git cat-file, git log origin/main, merge-base exit code) never
just "the function's own claim". This is what makes the §34.4 checklist's "sabotage effect confirmed
through an independent channel" item genuinely satisfiable without me re-doing all of it myself — I
spot-checked 2 (the incident round-trip, the process-tree-kill class) directly and cross-referenced
the rest against code that visibly implements the described fix (e.g. `check_upstream_shares_history`
using `merge-base`, `_ASKPASS_FAILFAST` branching on `sys.platform`).

**Pattern: an honest "untestable here" beats a mocked-Windows test — do not penalize the disclosure.**
`TestPosixProcessTreeKillOnTimeout`/`TestAskpassFailfastResolvesViaPath` explicitly refuse to fake
Windows coverage with a `subprocess.run` mock, arguing (correctly) that it would only prove the mock
was configured right, not that a real Windows process tree dies. Three concrete Windows gaps found by
grep: `_win32_kill_tree` (taskkill /F /T /PID) has zero test coverage of any kind; `_ASKPASS_FAILFAST`
= `"cmd /c exit 1"` is never exercised on win32; the 3 hardened-fetch-env tests (`TestFetchHardening`,
`TestFetchGateSkipsWithoutToolkitMemory`, fake-git PATH-shadowing) are `skipif(WINDOWS)` entirely. All
three are logic-reviewed only, documented as such in the code/test docstrings themselves (not hidden).
Scored Security 9/10 (not 10) specifically because of this real, articulable, but non-blocking gap —
consistent with treating "no Windows machine available" as an environment constraint to disclose, not
a code defect to reject over.

**Pattern: a Moriarty T3 "dead code relative to its own justification" finding (multi-match `_crown_replace`) is a maintainability/precision nitpick, not a functional bug — verify the unit test still tests real (if currently unreachable) semantics before treating the finding as closed vs. open.** Read `TestCrownReplaceMultiMatch` directly: it calls `_crown_replace` with hand-built lists containing
a genuine same-scope duplicate (simulating what `_merge_diverged_memory`'s concatenation COULD
produce if a downstream renderer folds a glossary crown over an already-merged list) — the unit
contract is real and correctly asserts multi-match-drops-duplicate behavior, even though no
production call today happens to combine "glossary crown" + "duplicated scope from divergence" in
one call. Noted as Observation, not a blocking finding.

**Score breakdown (100/110): Security 9, Error Handling 9, Architecture 9, Testing 10, Maintainability 8.**
First 10/10 I've given on Testing for a security-sensitive network-facing feature — justified by: zero
fabricated fixtures, real bare-remote round-trip driving the §34 gate, real process-tree kill against a
real grandchild PID, real hung-TCP-listener timeout test, explicit refusal to fake Windows coverage
with mocks, and 979/979 green with 0 xfail on a suite I ran myself twice. Maintainability held at 8
(not 9+) for the same class of issue flagged before in this project (`git-memory-upgrade.py`, session
2026-07-05): `fetch_memory_ref` (109 lines), `check_upstream_shares_history` (53), `render_scopes_section`
(51), `render_memoria_stamp` (51) all exceed the project's own 50-LOC-per-function convention, densely
commented but real code, no explicit Bex exception recorded for this round the way there is for
`git-memory-doctor.py`/`git-memory-upgrade.py`.

**Verdict:** APPROVED WITH CONDITIONS (non-blocking) — ship now. Follow-ups: (1) run this suite on a
real Windows CI runner/machine before or shortly after the next boot-hook-touching change, to close
the 3 documented Windows gaps with real execution instead of logic review; (2) Bex decision needed on
whether the 4 functions over 50 LOC in `lib/boot_git_checks.py` are an accepted 3rd exception (after
`git-memory-doctor.py`/`git-memory-upgrade.py`) or should be split; (3) optional, low-priority — either
find/add the real call path that exercises `_crown_replace`'s multi-match branch, or explicitly retire
`TestCrownReplaceMultiMatch`'s premise if it's confirmed to stay permanently unreachable.

## 2026-07-07 — Boot freshness #49, polish round final judgment (100 -> 103/110)

**Pattern: a "10 LOC via comment relocation" trick is legitimate, not metric-gaming, IF the file already has an established convention of design-rationale-as-preceding-comment BEFORE this round.** `check_upstream_shares_history()`/`render_memoria_stamp()` shrank from 53/51 LOC to 19/22 LOC by moving their multi-paragraph rationale from the docstring to a `#` comment block directly above the `def` line — AST-measured LOC only counts from `def` to the function's `end_lineno`, so this is real on the metric. Verified it is NOT gaming by grepping `git show <parent-of-polish-commit>:lib/boot_git_checks.py | grep '^# '` — 48 lines of exactly this pattern (rationale-as-preceding-comment) already existed in the file before this round (e.g. the `# ── Boot memory freshness ...` block above `fetch_memory_ref` predates this polish commit). Consistent style applied more broadly, not a one-off dodge invented to hit 50 LOC.

**Pattern: cross-read all 4 other agents' own memory-note commits landed in the SAME commit as the code change, not just the code diff — they independently re-attacked the fix and found things the code diff alone wouldn't show.** Commit 108c6a3 (the "pulido hacia 110" round) carried its own Cerberus/Moriarty/Dante/Ultron memory updates alongside the code. Reading Moriarty's `attack-patterns.md`/`resilience.md` diff directly surfaced two real, non-blocking latent findings the orchestrator's summary never mentioned: (1) Windows Task Scheduler/schtasks detachment escapes `taskkill /F /T /PID` (confirmed live with a real scheduled-task-spawned grandchild + independent `tasklist` query) — NOT a new gap, already inside the declared threat-model boundary of `TestWin32ProcessTreeKillOnTimeout`'s own docstring ("full local compromise" scope), just newly proven with a working PoC; (2) `time_ago()`'s `except (ValueError, TypeError, OSError)` does not catch `OverflowError` from `datetime.fromtimestamp()` on a huge digit string — pre-existing (predates this round's diff), confirmed unreachable via any real call site today. Both scored as real-but-non-blocking (docked lightly, not zeroed) rather than either ignored or treated as new blockers.

**Pattern: a "907 tests / 0 fallos" claim handed down as "verified fact" by the orchestrator did not reconcile with the one channel I could read myself.** Cerberus's own memory note, committed in the SAME commit, self-reported "897 passed, 74 skipped, 10 failed" (897+74+10 = 981, matching my own local `pytest --collect-only` total of 981 tests). The 10 failures were explained (9 pre-existing `bin.release_helpers` ModuleNotFoundError baseline, already reproduced pre-session in multiple earlier rounds via `git worktree`/`git stash`; 1 flaky `TestFetchHeadAgeSeconds`, which I verified DOES have a real fix in the same commit — tolerance widened from `age >= 0` to `-1.0 <= age < 60.0` with a cited 20k-iteration empirical probe). I could not trace "907" to anything — not my own collected total, not Cerberus's self-report. Treated as "not verified" (Observation, non-blocking) rather than asserting the literal figure, per the evidence standard ("if I cannot provide evidence, I say not verified — never looks fine"). This is NOT a §34 round-trip gate (that's specifically the fetch/read producer-consumer seam, which I DID re-verify fresh myself by running `test_boot_freshness.py::TestIncidentBehindShowsRemoteNext` directly against HEAD, exit code read by me, 1 passed) — it's a separate, lower-stakes test-bookkeeping precision gap, scored as a minor Security-dimension caveat, not a blocker.

**Score breakdown (100 -> 103/110): Security 9 (unchanged), Error Handling 9->9->10 promised, landed 9 (Moriarty's OverflowError find keeps it off a clean 10), Architecture 9->10 (crown_replace ambiguity resolved with a traced real call path, not asserted), Testing 10 (unchanged, sustained rigor), Maintainability 8->9 (the 4 promised boot_git_checks.py functions verified via AST at 0/4 over 50 LOC now — but boot_memory.py's `extract_memory` (192 LOC) and `extract_glossary` (129 LOC), pre-existing debt that grew modestly this round, have no explicit Bex-approved exception the way `git-memory-doctor.py`/`git-memory-upgrade.py` do — same recurring convention-drift pattern as the 2026-07-05 session).**

**Verdict:** APPROVED (GO for squash+merge), 103/110. All 4 explicitly promised polish items verified directly in code (not narration): excepts narrowed (3 sites, AST+grep confirmed, 2 remaining broad `except Exception` are deliberate documented fail-open safety nets, not leftovers), `_crown_replace` docstring corrected with a traced real call path via `boot_render.py`, all 4 originally-flagged `boot_git_checks.py` functions now 0/4 over 50 LOC, 2 new real (non-mocked) Windows security tests added for taskkill/askpass. Ran 312 tests myself fresh against HEAD (0 failures, 2 skipped = win32-only, as expected on macOS) covering every touched file. Gap to literal 110: 3 (Security, Windows-execution-result trusted via narration not a channel I read + Task Scheduler residual) + 3 (Error Handling, time_ago OverflowError latent gap) + 1 (Maintainability, boot_memory.py LOC-over-50 debt without explicit exception) = 7.

## 2026-07-07 (re-veredicto) — Boot freshness #49 close-out, 103 -> 107/110

**Pattern: a human's direct, in-conversation "I watched it run green" resolves the "agent narration vs channel I read myself" concern differently than an agent's summary of an artifact — but does NOT retroactively close an independently-proven structural residual.** Bex confirmed directly (relayed by the coordinator, not an agent narrating a report) that he personally watched the Windows suite go green. This is qualitatively different from Moriarty/Cerberus narrating "the tests passed" — it's the accountable human's own eyewitness account of the actual event, and Bex is the named escalation authority in my own role definition. Credited this fully for the "907 tests" trust concern. It did NOT move Security to 10, though — the independent Task Scheduler/`schtasks` detachment residual (Moriarty, live-proven, zero runtime check) is a *different* fact than "did the suite pass" — a green run doesn't exercise a scenario nobody wrote a test for. Kept Security at 9/10 for this separate, structural reason, consistent with the established F5/F6 hard-link-bypass precedent (2026-07-06 ronda 2): an accepted, formally-documented residual with zero runtime check keeps a security dimension off a clean 10 even after a legitimate defer-decision, because the hole itself is still open, only the paperwork around it is closed.

**Pattern: re-verify a "fixed" claim by reproducing the ORIGINAL failure against the OLD code, not just running the new test against the new code.** For the `time_ago()` OverflowError fix (commit `6fc6386`), ran `time_ago("9"*30)` live against current HEAD (`'unknown'`, no crash) AND cross-checked Dante's test docstring's claim that the pre-fix tuple actually raised — confirmed via reading the diff (`except (ValueError, TypeError, OSError)` -> `+ OverflowError`) that the old tuple genuinely lacked the member that matters, not a cosmetic reformulation. Also independently re-verified Argus's claim ("time_ago()'s return is display-only, never feeds staleness decisions") via `grep -rn "time_ago(" lib/ hooks/ bin/` — both call sites (`boot_git_checks.py:121,142`) feed directly into an f-string / return value used only for the RESUME section's "Last:" display line, confirmed by reading `get_last_context_time()` directly, not trusting the audit summary.

**Pattern: a "decision commit" that grants a LOC exception should be empty on `git show --stat` (metadata-only, no code diff) — an exception decision with an accompanying code diff would mean something got silently changed alongside the "we're not changing it" decision, which is a contradiction worth catching.** Verified `7fa39e3 --stat` is empty (0 files changed) before accepting it as the closing evidence for the Maintainability gap — matches the project's own decision-commit convention (Decision + Why trailers, no payload).

**Score breakdown (103 -> 107/110): Security 9 (unchanged — Task Scheduler residual is structural, not closable without a different Windows containment mechanism like Job Objects; not achievable today without real engineering work, correctly deferred), Error Handling 9->10 (OverflowError fixed + tested + live-reproduced by me + confirmed display-only/no control-flow impact — nothing left to articulate as a deduction), Architecture 10 (unchanged), Testing 10 (unchanged), Maintainability 9->10 (formal Bex decision commit verified, matches doctor.py/upgrade.py precedent exactly, empty-diff decision commit as expected).**

**Verdict:** APPROVED (GO for squash+merge), 107/110. Gap to literal 110 is entirely in Security (x3 weight) and is a real, structural, non-trivial-to-close item (schtasks/Task Scheduler process detachment escaping taskkill /T's PID-tree walk) — not achievable today as a quick fix; would need a genuine design change (e.g. Windows Job Objects for true nested-process containment) to fully close, correctly scoped as a future improvement, not a blocker.

## 2026-07-08 — CI green Windows+Ubuntu fix (72805bc + 05b14c9), %at date fix + errors='replace' residual, 95/110

**Pattern: when a fix unifies N of M call sites onto a more robust pattern, grep for the SAME fragile pattern across the whole tree before accepting "fixed" — a targeted House root-cause (2 functions) does not imply someone swept for siblings.** `lib/boot_git_checks.py`'s `get_timeline()`/`get_last_context_time()` moved from `%aI`+`fromisoformat()` (proven fragile against the CI runner's git ~2.43) to `%at` epoch (robust, matches `extract_memory()`). Grepping `%aI|fromisoformat` across the whole repo found the IDENTICAL pattern still live and unfixed in `bin/git-memory-gc.py:73,88`, `bin/git-memory-doctor.py:91,187,220`, `lib/bootstrap_commits.py:28` — none touched by this session, none exercised by any test that asserts a real parsed-date value (all wrapped in `except (ValueError, IndexError): return None`, so they'd degrade silently, not crash, exactly like the original bug did before it was diagnosed). Scored Architecture 8/10 (not 9) specifically for this — real, non-blocking, correctly out of THIS diff's scope (these 3 files weren't among the 6+4 failures being closed), but a legitimate follow-up: House swept exhaustively for the ENCODING defect class (140 sites/16 files) but not for the DATE-PARSING fragility class in the same session — an asymmetry in diligence between the two defect classes fixed back-to-back.

**Pattern: a fix can make a DIFFERENT file's test docstring stale the same day, without anyone noticing — cross-reference every "unreachable in production" claim against the diff you're currently judging.** `tests/test_boot_freshness_regression.py:1021` (`TestTimeAgoOverflowFallsBackSafely`, written 2026-07-07) asserted the `isdigit()`/`OverflowError` branch of `time_ago()` was "currently unreachable from any real call site... dead in production today" (true THEN — both real callers fed `%aI` ISO strings into the `else` branch). This session's `%at` fix (72805bc, 2026-07-08) flipped both real callers (`get_timeline()` line 142, `get_last_context_time()` line 172) onto epoch digit strings — the `isdigit()` branch is now the ONLY live path in production, and the docstring's premise is now false. Not a functional bug (the `OverflowError` fallback was already correctly widened and pinned as defense-in-depth), but a genuine test-rationale staleness introduced as a same-day side effect of a fix to a different file — found by tracing `time_ago(` call sites with grep, not by reading either file in isolation.

**Pattern: verify a "cp1252-safe for real users" product claim character-by-character, not by trusting the note.** House's diagnostic-patterns.md claimed `bin/release.py`'s only non-cp1252 character (`─` U+2500) is comment-only, never printed. Verified independently: wrote a one-off script collecting every char >127 in the file and checking `.encode('cp1252')` — confirmed `á é í ó ú —` all cp1252-encodable (printed via `_die`/f-strings) and `─` (box-drawing) appears ONLY in `# ── section ──` comment headers (grep confirmed, never inside a `print`/`_die` call). Independently reproduces House's claim rather than accepting it. Also confirmed via `merge-base --is-ancestor` that `force_utf8_streams()` (present in `unmassk-toolkit/bin/*.py`, unrelated `bin/` dir) landed via an EARLIER ancestor commit (14339fa) — House's "ABSENT from all bin/hooks entry points" note refers specifically to the separate repo-root `bin/release.py`/`bump-version.py` (release tooling, never in scope of that sweep), not a contradiction with the plugin's own `unmassk-toolkit/bin/` guard.

**Pattern: `gh run view <id> --json headSha,conclusion` is a channel I can read myself for a CI-green claim — use it instead of trusting the orchestrator's run-id citation.** Confirmed run 28938133937 has `headSha` == current HEAD (05b14c9) and `conclusion: success` on both `windows-latest` and `ubuntu-latest` jobs, read directly via `gh`, not narrated.

**Pattern: a commit-message claim of "Cerberus revisó el diff conjunto" can be imprecise — check which commit actually carries Cerberus's memory-note diff.** `72805bc`'s commit message documents Cerberus's LGTM; `05b14c9` (the residual `errors='replace'` fix, landed AFTER Cerberus's review) carries only a House memory-note diff, no Cerberus one. Treated as "Cerberus reviewed commit 1 only" rather than accepting "revisó el diff conjunto" at face value — closed the gap myself by directly reviewing the `errors='replace'` scope (grepped all 23 occurrences, confirmed every one reads subprocess output of an external process — git or a bin script — never a test-controlled `write_text`/`read_text`/in-process return value) and by running `test_release.py` myself under `PYTHONUTF8=0` (62/62 passed, matching the claimed figure exactly, read myself not narrated).

**Score breakdown (95/110): Security 9 (no attack surface added — `log_stderr_on_failure`'s breadcrumb only fires on 2 call sites with static `HEAD`/int-`n` args, git's own stderr text, truncated to 300 chars; Argus/Moriarty did not run this round — judged acceptable for a CI/test-stability fix with no auth/input-validation surface, same reasoning precedent as 2026-07-05's "Yoda does the adversarial pass himself" pattern), Error Handling 9 (except tuples correctly scoped, 7 dedicated tests for the new kwarg verified green by me directly), Architecture 8 (the 3-file date-parsing fragility gap above), Testing 8 (the stale docstring above, though the actual test still passes and tests real defensive behavior), Maintainability 9 (dense but accurate rationale comments, matches established project convention; the 3-file gap is pre-existing debt, not new).**

**Verdict:** APPROVED, 95/110. Ship. Two non-blocking follow-ups recommended: (1) open a small issue to unify `bin/git-memory-gc.py`, `bin/git-memory-doctor.py`, `lib/bootstrap_commits.py`'s `parse_date()`/`%aI` reads onto `%at` for consistency (same class of fragility, currently silent-degrade not crash, never fixed here because out of scope); (2) one-line docstring update on `TestTimeAgoOverflowFallsBackSafely` (test_boot_freshness_regression.py:1021) noting the `isdigit()` branch is now the LIVE path (post-72805bc), not dead code.

## 2026-07-08 (ronda 2) — Issue #55 close-out (%at unification, 6/6 sites), 95 -> 106/110

**Pattern: a prior verdict's "3-file gap" fleco is closed correctly when the fix generalizes to a 6th site the original House diagnosis never named.** The 95/110 verdict flagged 3 files (`gc.py`, `doctor.py`, `bootstrap_commits.py`) sharing the `%aI`+`fromisoformat()` fragility. Dante's contract docstring independently enumerated 6 concrete call sites across those 3 files (2 `parse_date()` duplicates + 4 git-log format strings, one of which — `doctor.py:check_hook_execution()` — parses nothing and was migrated for format-string consistency only, explicitly undertested with a stated reason). All 6 verified migrated in the actual diff, not just the ones a summary happened to name.

**Pattern: reproduce "N tests genuinely RED before the fix" with a real `git worktree` at the pre-diff SHA, copying only the new test file + conftest addition — not by trusting "confirmed RED" in an agent's commit message.** Copied `test_date_parsing_epoch_contract.py`+`conftest.py` into a worktree at `0ff8bfe` (pre-diff), ran the whole file against the OLD `gc.py`/`doctor.py`/`bootstrap_commits.py`: 10/10 failed, clean `AssertionError`s (not fixture crashes). Then ran the same file against HEAD: 10/10 passed. This is the full RED→GREEN cycle read by me directly, on both ends — stronger evidence than a single green run against HEAD alone.

**Pattern: a "date" field's producer contract can change format (ISO → raw epoch string) safely if literally nothing in the codebase parses/displays it — verify by grepping every consumer of the dict key, not just trusting the test file's own claim of "no crash today."** `lib/bootstrap_commits.py:scan_recent_commits()`'s `"date"` key is stored raw, never parsed. Traced its only consumer (`bin/git-memory-bootstrap.py`'s `output["commits"]`, JSON-mode only) and confirmed no `.get("date")`/formatting call exists anywhere in that file — the format-string swap is genuinely a no-op for behavior, only a data-shape change for hypothetical future consumers, exactly as documented.

**Pattern: distinguish "fromisoformat() on git-log output" (the fragility class issue #55 targets) from "fromisoformat() on a field the toolkit writes to itself" (out of scope by construction) with a one-line grep of the write site.** `lib/boot_glossary_cache.py:119`'s `datetime.fromisoformat(generated)` parses `generated_at`, which is written 40 lines below via `datetime.now(timezone.utc).isoformat()` — self-produced, well-formed by construction, never touches git's `%aI` output. Confirmed via `grep -n "generated_at"` showing both the read and write sites in the same file. Same reasoning applies to `lib/boot_git_checks.py:81`'s ISO fallback branch inside `time_ago()` itself — that IS the canonical pattern this fix mirrors, not a residual instance of the bug.

**Pattern: a pre-existing flaky test (`test_doctor_after_install` under `-k` filtering) reported by Cerberus as "reproduced on base commit via git worktree" is worth re-reproducing yourself with the exact same `-k` string, not just trusting the methodology description.** Ran `pytest tests/ -k "gc or doctor or bootstrap_commits"` against a worktree at `0ff8bfe`: identical single failure, same assertion, same message (`'CLAUDE.md not found'`). Whole-file run (`test_lifecycle.py` alone, both at base and at HEAD): 10/10 green. Whole-suite run at HEAD: 0 failures (the ordering that triggers the flake never occurs in full-suite collection order). Three separate confirmations, all read directly, none narrated.

**Pattern: no dedicated Argus/Moriarty round for a pure internal date-parsing robustness fix is acceptable when verified structurally, not just asserted.** Checked `git log --all -i --grep argus\|moriarty` and `git status`/mtime on both agents' memory dirs — zero commits, zero uncommitted changes for this round. No new attack surface exists to audit (no user input, no auth boundary, no injection surface — `%at`/`%aI` are git's own format-string tokens, not attacker-controlled). Consistent with the identical judgment call made in the prior 95/110 round for the sibling `%at` fix in `boot_git_checks.py`. Performed my own adversarial-equivalent verification (RED-before-fix worktree reproduction, flake reproduction) in lieu of a dedicated round — kept Security at 9/10 (not 10) for the same reason as before: no independent security-focused pass occurred, even though nothing security-relevant was found to look for.

**Score breakdown (95 -> 106/110): Security 9 (unchanged reasoning — no new attack surface, no dedicated Argus/Moriarty pass this round, same precedent as the sibling `%at` fix), Error Handling 9->10 (all 6 sites migrated including the untested-but-migrated `check_hook_execution` format string, dead `IndexError` removed from both except tuples, naive/aware `now()` mismatch fixed at both call sites and verified not just via unit test but via the end-to-end old-git-simulation tests, ISO fallback branch given dedicated tz-aware coverage per Cerberus's own follow-up — nothing left to articulate as a gap), Architecture 8->9 (the 3-file fragility gap from the prior verdict is fully closed and consistent with the canonical `time_ago()` shape; held off 10 because `parse_date()` still lives as 2 near-identical copies in `gc.py`/`doctor.py` rather than being centralized into a shared `lib/` module the way `time_ago()` itself is — pre-existing duplication, not introduced by this diff, but also not resolved by it), Testing 8->10 (the stale-docstring fleco from the prior round is independently confirmed fixed by direct read + a fresh green run of that exact file; the new contract suite is textbook §34 — real git producer, real RED-before-fix reproduction by me via worktree, real fake-git PATH-shadowing end-to-end degradation tests, not mocks), Maintainability 9 (unchanged — dense accurate rationale comments matching established project convention, no new debt introduced).**

**Verdict:** APPROVED, 106/110. Both flecos from the 95/110 round fully closed and independently verified (not narrated): fleco 1 (stale docstring) was already fixed before this round started, confirmed by direct read + green test run; fleco 2 (issue #55, `%at` unification) closed across all 6 sites, DoD grep confirms zero remaining `fromisoformat()`/`%aI` on git-log output outside the documented, tested, canonical ISO fallback branch. Full suite run by me directly: 1005 passed, 2 skipped, 0 failed (238s, foreground). Gap to literal 110 is Security (x3, no dedicated audit pass — structural, same as prior round) + Architecture (x2, pre-existing `parse_date()` duplication, not new debt).

## 2026-07-08 — Issue #55 final close-out attempt, 106 -> 88/110 (NOT closed, sent back)

**Pattern: a Moriarty numbered finding can bundle two distinct manifestations of the same root cause — a fix that closes one manifestation and a claim of "N/N arreglados" can both be true-ish while the finding is only half-closed. Verify each manifestation separately, don't accept a single check-mark per finding number.** Moriarty's finding #1 (year-10000+ overflow author date) had two manifestations: (a) a `Blocker:` trailer on such a commit becomes permanently invisible to both `gc.py`'s H2 heuristic and `doctor.py`'s stale-blocker count, zero diagnostic trace; (b) if the overflow-dated commit IS the GC commit itself, `doctor.py` falsely reports "GC: never run". The orchestrator's fix (a `gc_date_unparseable` flag threaded through `check_gc_status()`'s new 4-tuple) closes ONLY (b). Confirmed (a) is still live by direct code read (`doctor.py:254`'s `if "Blocker" in body_trailers and date:` has no unparseable-date branch, `gc.py:213`'s `if not commit["date"]: continue` is unchanged) AND by a live reproduction I built myself (real repo, `git commit --allow-empty` with `GIT_AUTHOR_DATE="@253402300800 +0000"` + a real `Blocker:` trailer, `git fsck --full` clean, ran the real `doctor.py --json` and `gc.py --dry-run --days 1` binaries: "Stale blockers: none" / "Nothing to clean" — the blocker is genuinely invisible, no trace anywhere). No test covers manifestation (a) — grepped `test_date_parsing_epoch_contract.py`'s class list, only `TestDoctorGcNeverRunFalseOnUnparseableFutureDate` (manifestation b) exists.

**Pattern: when an orchestrator's task narration says "Moriarty verdict DÉBIL, 3 roturas, las 3 arregladas", treat "3 arregladas" as a claim to verify per-finding, not a fact — DÉBIL (not AGUANTA) is itself a signal the round didn't fully hold.** Cross-referencing DÉBIL against the Moriarty FALLA Rule (T2/T3 findings need an explicit written accepted-risk decision from the orchestrator to be APPROVED WITH CONDITIONS, not a silent "we fixed it") — no such decision commit exists for the residual found here (unlike the F6 hard-link-bypass precedent, `51a3c44`, which WAS a proper written defer-decision). Verdict: APPROVED WITH CONDITIONS anyway (not REJECTED) because the residual is genuinely T2/T3 (Moriarty's own words: "none catastrophic", no crash, no data loss, no security boundary crossed, requires local commit-write access already inside the trust boundary) and the rest of the round is exceptionally solid — but flagged as a concrete, named, reproducible gap requiring either a quick symmetric fix (mirror the `gc_date_unparseable` pattern into the Blocker-counting path in both files) or an explicit Bex risk-acceptance decision, not silently closed.

**Pattern: Argus's findings can be real and independently verifiable via code+tests even when Argus left zero memory-note artifact of his own for the round (only narrated in commit messages).** Checked: no `.claude/agent-memory/unmassk-toolkit-argus/` diff exists anywhere in `0ff8bfe..HEAD`, only commit-message narration ("Argus RESUELVE 2 LOW..."). Did not block on this — the claimed guards (isinstance/isascii/length-cap) are directly readable in the diff and covered by Dante's contract tests (`TestParseDateNonStringInputContract`, `TestParseDateNonAsciiDigitsContract`, `TestParseDateLengthGuardContract`), which is a stronger verification channel than an agent's own memory note would be anyway. Noted as a process/bookkeeping observation, not a blocking finding — consistent with the general principle that code + tests I read myself outrank any agent's self-report, narrated or written.

**Pattern: a stray internal crew-name citation in a NEW file's docstring, written the same round as an explicit "jerga purgada, barrido confirmado sin coincidencias" cleanup claim, is worth a targeted diff-only grep (added lines, not whole-file), because the wider codebase is saturated with legitimate pre-existing SEC-*/Cerberus/Argus/Moriarty tags that would drown a whole-file grep in noise.** `lib/date_parsing.py`'s new module docstring cites `.claude/agent-memory/unmassk-toolkit-ultron/lessons.md` as precedent — the literal string "ultron" leaks into production code. Found via `git diff ... | grep '^+' | grep -iE '(crew names)'`, not a whole-tree grep (which returns ~80 pre-existing, legitimate, out-of-scope matches in `boot_git_checks.py`/`boot_memory.py`/etc. from the unrelated issue #49 pipeline). Minor, not blocking — but it does make the round's own cleanup claim inaccurate as stated.

**Score breakdown (88/110): Security 9 (dedicated Argus+Moriarty round finally happened, closing the prior 106/110 gap; guards verified via reproduction; docked for Argus's narration-only artifact + the length-guard asymmetry between the two mirror functions, both non-blocking), Error Handling 6 (the live, reproduced, misreported-as-fixed Blocker-invisibility gap above — real, on-target, silent, T2/T3 per Moriarty's own scale, but non-catastrophic), Architecture 9 (the prior verdict's explicit `parse_date()` duplication gap is genuinely closed via a clean, precedented extraction to `lib/date_parsing.py`; Ultron's documented, well-reasoned decision NOT to force-merge `time_ago()` into `parse_date()` — Python 3.10 Z-suffix behavior difference — is good judgment, not unresolved debt; docked lightly for the stray "ultron" docstring citation), Testing 8 (exceptional §34 rigor otherwise — real git fixtures, real `GIT_AUTHOR_DATE`/`git fsck --full` reproductions, self-contradiction caught and reconciled, RED->GREEN independently reproduced by me via worktree at `d78c136` -> HEAD; docked for the one concrete missing contract test, the mirror of the manifestation that WAS tested), Maintainability 9 (clean removal of duplicate functions, honest rationale comments, jargon cleanup mostly real — 6 jargon comments removed, 0 new SEC-tags added in touched-file diff hunks — docked lightly for the "ultron" residual).**

**Verdict:** APPROVED WITH CONDITIONS (not literal 110, sent back for one targeted fix or an explicit Bex risk-acceptance decision). Gap: (1) Major — Blocker-invisibility-via-unparseable-date not fixed in either `gc.py`'s H2 or `doctor.py`'s stale-blocker count (only the sibling "GC: never run" manifestation was fixed); (2) Minor — "ultron" crew-name citation in `lib/date_parsing.py`'s new docstring contradicts the round's own "jerga purgada" claim; (3) Observation — Argus left no dedicated memory-note artifact this round (narration-only), Cerberus's 1 pending suggestion (time_ago length-guard asymmetry) correctly self-assessed as non-blocking and confirmed as such independently.

## 2026-07-09 — F6 hard-link reject (issue #53) + SEC-HIGH-001/VARIANT-01, 88/110

**Pattern: a task's own framing of a verification gap ("ran on CI Ubuntu") can be factually wrong — check the CI channel directly with `gh run view`/`gh run list`, never accept "it ran in CI" as given, even when it sounds like a reasonable disclosed limitation.** The task described the POSIX branch as "ran on CI Ubuntu, not on this machine" — implying it had run and passed elsewhere. `gh run list`/`gh run view` showed HEAD (`e9de236`) was never pushed (zero CI runs against that SHA) and the one commit that DID run on CI (`bd1880f`, one commit behind) FAILED on both ubuntu-latest and windows-latest — correctly RED on the not-yet-fixed VARIANT-01 test, which is expected/fine, but proves the POSIX branch of the *complete* fix has literally never executed anywhere, contradicting the framing. This is qualitatively different from an honestly-disclosed gap (e.g. the 2026-07-06/07 Windows-Task-Scheduler residual pattern) — it's an inaccurate claim about verification state that only surfaces by reading the channel directly instead of trusting the narration, exactly the discipline this role exists to apply. Did not trigger the mechanical §34 REJECT (that gate's own artifact — the write→read round-trip test — WAS real, fresh, green, and I personally sabotaged+restored it on the platform I could test), but materially dropped Security score and became the single named condition for reaching 110.

**Pattern: when an entire round has ZERO memory-note artifacts from 3 of 5 agents (Cerberus, Argus, Moriarty all narration-only, verified via `git show --stat` on every commit in the round), independently verify each agent's SPECIFIC claimed finding via code+tests+live sabotage rather than blanket-accepting or blanket-rejecting.** Argus's and Cerberus's specific claims (4 missing call-sites; 6 flecos = 4 comments + 2 tests) were both independently confirmed true via direct diff read + full-codebase grep sweep + running the tests myself. Moriarty's "8 PoCs reales, AGUANTA" had literally nothing to check against — performed a substitute adversarial pass myself (race-condition reasoning on the fstat-after-open window, symlink+hardlink interaction order, EXDEV cross-filesystem limit ruling out device-node hard-link DoS) and found nothing additional, but explicitly flagged this substitute as weaker evidence than a real documented Moriarty round, consistent with the 2026-07-05 precedent for "Yoda does the adversarial pass himself."

**Pattern: a fail-safe security rejection (OSError propagating uncaught) is not a security bug even when it crashes the caller — but IS a real, articulable Error Handling deduction when it's inconsistent with sibling call sites in the SAME commit.** `bin/git-memory-upgrade.py:505`'s `create_backup()` call has no try/except, unlike the other 3 manifest-write call sites in the same feature (all of which gracefully append to an `errors` list or swallow). The security property holds either way (write never happens on hard-link detection) — this is purely a UX/consistency gap, scored as Minor, not Major.

**Score breakdown (88/110): Security 7 (design/Windows-implementation verified end-to-end by me including live sabotage; POSIX branch of the FINAL commit never executed anywhere, and the task's own claim about this was checked and found false), Error Handling 8 (create_backup() unwrapped call site, real but non-security-compromising inconsistency), Architecture 9 (clean opt-in param, twin symmetry verified line-by-line identical, minor unreconciled doctor.py-vs-glossary-cache read-guard rationale), Testing 8 (exceptional §34 contract — differential controls, independent-channel sibling-hardlink verification, real RED→GREEN sabotage reproduced by me — docked for zero cross-platform execution of the complete suite and the Moriarty-substitute-not-equivalent gap), Maintainability 9 (very clean, well-commented, minor doc-reconciliation nit).**

**Verdict:** APPROVED WITH CONDITIONS, 88/110. Push `e9de236` + get real green CI (both runners) is the single condition blocking literal 110 (Security x3), plus one 1-line Error Handling fix (upgrade.py:505 try/except) and one cosmetic docstring cross-reference. None of these are §34 mechanical-REJECT triggers — that gate's own artifact was verified fresh/green/sabotaged by me directly.

## 2026-07-09 (re-veredicto) — Issue #53 close-out attempt tras condiciones 2+3, 88 -> 96/110 (CI cierra Security, pero 2 comentarios nuevos abren Maintainability)

**Pattern: cuando se añade un try/except NUEVO alrededor de una función existente, releer el comentario ADYACENTE dentro de esa función que describe qué excepciones "no se capturan" — puede quedar falso por construcción de clases, no solo por descuido.** `bin/git-memory-upgrade.py:166-167` (dentro de `create_backup()`, comentario reescrito en el MISMO commit `7c3624f` que añadió el try/except en `main()`) afirma "An UnsafePathError from this call still propagates as an uncaught exception (main() does not catch it)". Falso: `UnsafePathError(OSError)` (`lib/git_helpers.py:24`, subclaseado A PROPÓSITO "so every existing call site that already wraps ... except OSError ... fails closed automatically") y el nuevo `except OSError as e:` en `main()` envuelve la llamada COMPLETA a `create_backup()`, así que SÍ captura el `UnsafePathError` de `verify_path_within_project(backup_dir, target)` (línea 174, dentro de la misma función, antes del write). Verificado en vivo dos veces: (1) snippet Python aislado confirmando `except OSError` atrapa `UnsafePathError`; (2) sabotaje real completo — hard link real plantado en el `backup_path` predicho (datetime congelado + `sanitize_trailer_value` real, mismo algoritmo que el test VARIANT-01 existente), llamada real a `create_backup()` envuelta en la lógica exacta de `main()`: `OSError` (EMLINK) capturado, mensaje formateado impreso, exit code 1, contenido de la víctima intacto. El comportamiento real es CORRECTO (incluso mejor de lo que el comentario dice) — el defecto es puramente de precisión del comentario, introducido por el propio fix que se pidió verificar.

**Pattern: un cross-reference que cita literalmente la MISMA frase de justificación en ambos sentidos puede seguir sin resolver una asimetría de comportamiento real — verificar la conclusión aplicada, no solo la cita.** Condición 3 pedía verificar que el cross-ref `doctor.py:514 <-> boot_glossary_cache.py:114` existe en ambos sentidos y cita la misma justificación — mecánicamente SÍ (ambos citan textualmente "a read of a hard-linked file cannot corrupt the victim, only a write can"). Pero esa MISMA frase se usa para justificar DOS decisiones opuestas: `doctor.py`'s manifest read omite `reject_hardlinks` a propósito; `boot_glossary_cache.py`'s cache read SÍ pasa `reject_hardlinks=True`. El cross-ref nuevo hace ambos sitios más fáciles de encontrar pero no explica por qué el mismo criterio produce resultados distintos — la "unreconciled doctor.py-vs-glossary-cache read-guard rationale" ya anotada en el veredicto 88/110 sigue abierta, solo que ahora más visible/citable. No es nuevo de esta ronda (glossary-cache.json es uno de los 4 call sites ORIGINALES pre-issue-#53 según nota de Cerberus), pero el pedido explícito de Bex de "verificar que cita la misma justificación" pasa la vara mecánica sin cerrar la vara sustantiva.

**Pattern: código nuevo de manejo de errores (un try/except) puede quedar con cobertura de test cero incluso cuando la propiedad de seguridad subyacente SÍ está testeada — grep del nombre de la función en tests/ para confirmar quién la llama y cómo.** `tests/test_manifest_hardlink_reject.py::TestSecHigh001Variant01UpgradeBackupHardlinkWrite` llama a `create_backup()` DIRECTAMENTE (bypassa `main()`), verificando el guard de escritura pero nunca ejercitando el try/except de `main()` (mensaje formateado + `sys.exit(1)` en vez de traceback). `git show --stat 7c3624f` confirma cero archivos de test tocados en el commit que añadió el try/except. Suplí la verificación yo mismo (ver patrón anterior) en vez de bloquear, consistente con el precedente "Yoda hace el pase adversarial él mismo" — pero sigue siendo un hueco real de Testing, no cerrado por un test automatizado.

**Score breakdown (88 -> 96/110): Security 7->9 (la condición única que bloqueaba Security x3 — CI verde en ambos runners contra el HEAD exacto — verificada directamente vía `gh run view 29013655522` (headSha=7c3624f, conclusion=success en ubuntu-latest Y windows-latest); rama POSIX del fix final ahora SÍ ejecutada realmente, no solo revisada por lógica; no sube a 10 por el hallazgo UnsafePathError-comment-falso, recién probado en vivo, en el propio código de guarda de seguridad que se tocó para cerrar esta issue), Error Handling 8->9 (el hueco nombrado — create_backup() sin try/except — cerrado y verificado con sabotaje real; no sube a 10 por el mismo hallazgo de comentario falso, que es específicamente sobre semántica de captura de excepciones), Architecture 9 (sin cambio — la "unreconciled read-guard rationale" ya estaba priceada en el 9 anterior; el cross-ref nuevo la hace más visible sin resolverla, ni mejora ni empeora el número), Testing 8 (sin cambio — hueco de cobertura del try/except nuevo, suplido por verificación en vivo mía, no por un test pinneado), Maintainability 9->8 (dos hallazgos NUEVOS de precisión de comentario en el código específico entregado para cerrar esta issue: la afirmación falsa sobre UnsafePathError y el cross-ref que cita el mismo criterio para justificar decisiones opuestas sin reconciliar).**

**Verdict:** APPROVED (GO, ship), 96/110 — NO es 110/110 literal. Suite local corrida por mí mismo directamente (no narrada): 987 passed, 77 skipped, 0 failed, 723.99s, coincide exactamente con la cifra reclamada. Gap a 110 = 14 puntos en 3 hallazgos concretos, ninguno bloqueante: (1) Maintainability/Error-Handling — comentario falso en `git-memory-upgrade.py` ~166-167 sobre UnsafePathError no capturado; (2) Maintainability/Architecture — cross-ref doctor.py<->boot_glossary_cache.py cita el mismo criterio para decisiones opuestas sin reconciliar; (3) Testing — cero cobertura automatizada del try/except nuevo en main() (solo verificación en vivo mía). Los 3 son de precisión de comentario/test, no de comportamiento en producción — el comportamiento real verificado en los 3 casos es correcto o mejor de lo documentado.

## 2026-07-09 (re-veredicto final) — Issue #53 cierre real, 96 -> 110/110

**Pattern: cuando los 3 huecos que bloquean 110 son puramente de precision (comentario, cross-ref, cobertura) y no de comportamiento, cerrarlos con evidencia directa SI justifica 10/10 en las dimensiones que docaban — no hace falta reservar puntos "por si acaso".** Verifique los 3 directamente, sin narracion de otro agente: (1) `git-memory-upgrade.py:166-174` reescrito, grep confirma CERO referencias residuales a la frase falsa vieja ("main() does not catch") en todo el repo; `class UnsafePathError(OSError)` confirmada en `git_helpers.py:24` exacto. (2) cross-ref doctor.py:518-531 <-> boot_glossary_cache.py:113-124 ahora explican la razon REAL (read alimenta write ya guardado vs. read sin write pareado) y verifique leyendo el resto de `_read_glossary_cache()` que en efecto no hay ningun write en ese path. (3) test nuevo `TestSecHigh001Variant01MainBackupErrorHandling` verificado con MI PROPIO sabotaje en vivo: cambie `except OSError` a `except ValueError` en el except real de `main()`, confirme el test se rompe con un traceback real (prueba que el test depende genuinamente del except, no es tautologico), restaure y confirme verde de nuevo. CI (`gh run view 29015978470`) headSha=e6f8872 coincide exacto con el commit del fix; HEAD actual (b03db60) es memoria-only, `git diff e6f8872..b03db60 --stat` vacio. Suite local corrida por mi: 1063 passed, 2 skipped, 0 failed (256s). Workflow YAML corre `pytest unmassk-toolkit/tests -q` sin filtro, asi que el test nuevo SI fue parte del run verde de CI, no solo local.

**Score breakdown (96 -> 110/110): Security 10 (unico hallazgo que docaba Security en la ronda anterior era el comentario falso DENTRO del codigo de guarda de seguridad — ahora preciso, verificado sin residuos), Error Handling 10 (semantica de captura de excepciones ahora documentada con precision exacta, verificada linea por linea), Architecture 10 (cross-ref reconciliado con razon real distinta por sitio, no la misma frase repetida para decisiones opuestas), Testing 10 (cobertura automatizada real del try/except de main(), con mutation-test mio en vivo confirmando que el test no es tautologico), Maintainability 10 (los 2 hallazgos de precision que docaban esta dimension estan cerrados, sin residuos en el resto del repo).**

**Verdict:** APPROVED (GO, ship), 110/110 literal. Los 3 flecos: TODOS resueltos con evidencia directa (no narracion). Ningun hallazgo nuevo encontrado en esta ronda. Proximo paso fuera de mi scope: bump de version + cierre de issue #53 en GitHub (ya notado en contexto de sesion, no bloqueante para este veredicto).

## 2026-07-10 — Issue #60 boot MEMORY stamp v4 final judgment: REJECTED on CI-green gate despite exceptional local evidence

**Pattern: local pytest green (even with my own live sabotage/restore) is NOT a substitute for "it is green" in the Round-Trip Evidence Rule when the project's own CI matrix targets a platform I didn't/can't execute on.** Full local suite (macOS): 1246 passed, 2 skipped (Windows-only), exit 0 — real, run twice by me with a clean (non-tail-piped) exit code the second time after catching my own mistake of piping to `tail` the first time (own project memory warns against exactly this — `EXIT_CODE=$?` after `| tail` captures tail's exit code, not pytest's). The 3 required §34 gate classes (`TestOwnSuccessStampNotFetchHeadMtime`, `TestOwnStampIdentityIncludesRemoteURL`, `TestAliasFallbackURLIsNotResolvedIdentity`) all pass locally, and I personally reproduced RED→GREEN on the v4 guard (`url == remote_name` check in `_check_remote_is_live()`) by neutralizing it, confirming 2 tests fail with the exact predicted assertion, then restoring and confirming green again. All of this was genuine, first-hand evidence — and still insufficient, because `gh run view` (a channel I read myself) showed the REAL Windows CI runner has been consistently RED across the last 2 pushes (headSha 787b698 and 174d82b) on the exact test classes constituting this feature's core contract (`TestOwnSuccessStampNotFetchHeadMtime` vectors A/B/D + `TestOwnStampIdentityIncludesRemoteURL` both tests) — "N failed, no fetch call was observed at all" — and the actual final fix commits (`32379b7`, `154a80d`, the v4 RED/GREEN pair) have NEVER been pushed at all (`git status`: branch ahead of origin by exactly those 2 commits). Zero CI evidence exists for the code I was asked to approve.

**Pattern: a plausible root-cause hypothesis from code reading is not evidence — say so explicitly, don't let it soften the verdict.** Read `_make_fake_git()` (test_boot_freshness.py:261-274): writes an extensionless file named literally `git` (no `.exe`/`.cmd`/`.bat`) into a temp dir prepended to PATH, `chmod 0o755` (a POSIX-only no-op concept on Windows). Windows' `CreateProcess`/PATH resolution requires a PATHEXT-recognized extension for `subprocess.run(["git", ...])` to find a shim ahead of `git.exe` — this is very likely why the fake shim is silently bypassed on Windows CI (real git runs, but the test's OWN fetch-call-observation channel — the fake git's JSON log — never gets written, so the test's "no fetch call was observed" assertion fires even though real git may well have fetched correctly). This is a plausible, code-grounded, but UNCONFIRMED-by-execution hypothesis that the failure is test-harness-only, not a production bug — I stated it as exactly that (a hypothesis, not a finding) rather than either (a) treating it as proof the code is fine (would be an uninformed opinion) or (b) ignoring it and assuming the worst (would misdiagnose the fix direction). This matters for a Windows-targeting fake-git-on-PATH pattern anywhere else in this codebase — same shim technique, same latent Windows gap, and nobody in the pipeline (Cerberus, Dante, Ultron, Moriarty, House) flagged or diagnosed it despite CI being actively red for 2 consecutive pushes.

**Pattern: process hygiene gap — Moriarty's v4 final AGUANTA verdict exists ONLY as uncommitted working-tree changes.** `git status` showed `.claude/agent-memory/unmassk-toolkit-moriarty/{MEMORY.md,resilience.md}` as modified-not-committed, containing the entire "v4 round-4 FINAL check, AGUANTA, 0 breaks" narrative (evasion attempts against whitespace-URL, insteadOf rewrites, legit-rare name==url coincidence). `git diff ac3e805..HEAD` (the exact channel the task instructions pointed me to) does NOT surface this — I only found it via `git status` after noticing MEMORY.md content mismatched between my diff-read and a live grep of the working file. Also found: Cerberus never reviewed the v4 diff at all (`grep -rn "174d82b" .claude/agent-memory/unmassk-toolkit-cerberus/` = zero hits; only chatroom-standards.md's unrelated "actions/checkout v4" match) — the last code change to ship (the `url == remote_name` guard) has zero Cerberus review, compensated for by my own direct read (small, clean diff, one-line logic change + docstring) but worth naming explicitly as a real pipeline gap, not silently absorbed.

**Rule for future git-log-boundary tasks:** when told "check `git log X..HEAD`" as the evidence boundary, ALSO run `git status` unconditionally — committed-range diffs cannot show uncommitted memory-note evidence the orchestrator's own summary may be citing (e.g. "Moriarty AGUANTA 12/12" in this task's context turned out to be real but only readable via the working tree, not history).

**Score breakdown (83/110 nominal, but REJECTED overrides the numeric threshold per the Round-Trip Evidence Rule's explicit no-override clause): Security 8 (sound design, verified via extensive real sabotage — mine + Moriarty's documented v2/v3 rounds — but zero confirmed-working verification on the one non-macOS platform this "multi-machine" feature explicitly targets), Error Handling 9 (fail-open discipline excellent, atomic write correct, no concrete finding), Architecture 8 (clean split, good docstrings, minor completeness gaps: plan doc never updated past the v2 amendment despite v3/v4 decisions existing in git log, no Cerberus pass on the final diff), Testing 4 (the CI-green mechanical fact is false for current HEAD — no run exists — and false for the closest prior run — 5 real Windows failures, unaddressed across 2 pushes), Maintainability 8 (dense accurate comments matching established convention, LOC-over-50 functions are docstring-heavy not code-heavy per AST measurement, consistent with prior sessions' judgment on this exact pattern).**

**Verdict:** REJECTED (NOT READY). This is the first time in this project's history I've rejected on the §34/Round-Trip Evidence Rule's CI-green mechanical fact specifically (prior sessions always found a real, fresh, green `gh run view` match before approving — e.g. 2026-07-09's `headSha=7c3624f` match, 2026-07-06's Windows-watched-live account from Bex). The gap is fully actionable and likely small (push, get a fresh CI run, diagnose whether the fake-git shim needs a `.cmd`/`.bat` Windows twin) — not a design-level rejection, but the rule exists precisely to prevent "the logic is obviously fine, ship it" from substituting for real cross-platform execution evidence, especially on a feature whose entire purpose is multi-machine correctness.

## 2026-07-11 — Issue #60 re-veredicto tras cierre de bloqueantes: REJECTED (83) -> APPROVED (101/110)

**Patrón: cuando el bloqueante es evidenciario (no de diseño), el re-veredicto debe re-verificar el MISMO canal, no aceptar la narración de que se cerró.** Repetí exactamente los mismos pasos mecánicos de la ronda anterior: `git rev-list --left-right --count origin/main...HEAD` (0/0, confirma push real), `gh run view 29125050400` (leído yo mismo: ambos jobs success, headSha coincide con HEAD exacto), y `gh api .../attempts/{1,2}/jobs` para leer el HISTORIAL de reintentos (no solo el resultado final) — confirmando que windows-latest ya estaba verde en el intento 1 (matching la narrativa) y que ubuntu-latest falló 2 veces por una familia DISTINTA de test cada vez (`test_recall::test_entry_beyond_500_commits_is_found`, luego `test_drift::test_deep_search`), ninguno tocado por este diff (`git diff ac3e805..3e971fa --stat -- test_recall.py test_drift.py` vacío) y con issue #61 real, verificable, abierto con los 4 fallos documentados.

**Patrón: reproducir el sabotaje sobre el NUEVO mecanismo de test cuando el bloqueante anterior era justo sobre la fiabilidad del mecanismo de test.** No me bastó con leer `tests/_git_intercept.py` y confirmar que Dante documentó un mutation-kill — parcheé `_looks_like_git()` para devolver `False` siempre yo mismo, corrí `TestOwnSuccessStampNotFetchHeadMtime`, confirmé 3/4 tests caen con el `assert []` exacto predicho, restauré, confirmé verde de nuevo. Por separado, reproduje el mutation-kill de Cerberus sobre el hallazgo de test-redundancy (`_read_own_stamp_age()`'s `remote_url` comparison eliminada a mano → el test ARREGLADO cae correctamente ahora, cuando ANTES del fix habría pasado en verde de forma vacía). Ambos ciclos RED→GREEN míos, no narrados.

**Patrón: cuando el código de producción no cambió entre rondas (`git diff <verdict-anterior>..<HEAD-nuevo> -- lib/` vacío), la re-verificación de ese código NO necesita repetirse línea por línea — solo confirmar el hash es idéntico y reusar el análisis anterior.** `lib/boot_git_checks.py`/`lib/boot_fetch_stamp.py` son byte-idénticos entre `154a80d` (mi veredicto NOT READY) y `3e971fa` (HEAD final) — verificado con `git diff --stat`. Todo el cambio de esta ronda vive en test-infra (`tests/_git_intercept.py`, nuevo) y notas de agentes. Esto acota el alcance real de la re-verificación sin reducir su rigor.

**Hallazgo nuevo, nimio, cosmético: el plan doc quedó desactualizado DESPUÉS de escribir su propia sección de cierre.** `docs/plan/fix-boot-memory-stamp.md`'s CIERRE section (escrita en `e62ba37`) lista 4 items como `- [ ]` (sin marcar): 2 Blockers (CI Windows rojo, wips sin pushear), 1 Minor (Cerberus no revisó v4), 1 Obs (notas Moriarty sin commitear) — los 4 están genuinamente resueltos en los commits POSTERIORES (`4b10931`, `3e971fa`) pero el plan nunca se volvió a tocar tras `e62ba37` (`git log -1 -- docs/plan/...` confirma última edición = `e62ba37`) para marcar esas casillas. Comportamiento real correcto en los 4 casos — puramente un artefacto de checklist no actualizado, exactamente el tipo de hallazgo "nimio, cosmético" que el estándar de Bex (110 = cero hallazgos) pide nombrar aunque no bloquee.

**Score (83 rechazado -> 101/110 aprobado): Security 9 (sin cambio de diseño desde la ronda anterior, pero ahora con evidencia real de ejecución en Windows cerrando el hueco cross-platform que antes dejaba la dimensión en duda), Error Handling 9 (sin cambio, sin hallazgo nuevo), Architecture 9 (el interceptor de `subprocess.Popen` es un diseño genuinamente mejor que el shim de PATH que reemplaza — cross-platform by construction, sin rama POSIX/Windows — más el hallazgo de Cerberus sobre el guard v4 cerrado con evidencia), Testing 10 (primer 10/10 limpio de esta feature — CI verde en ambas plataformas verificado por mí vía `gh run view`, 2 sabotajes en vivo míos propios sobre 2 mecanismos distintos, mutation-kill de Dante Y de Cerberus ambos re-verificados por mí, cero skips de Windows restantes atados a este mecanismo), Maintainability 9 (el hallazgo cosmético del plan doc arriba es lo único que impide un 10 limpio).**

**Veredicto:** APPROVED (GO), 101/110. Los 3 bloqueantes de la ronda NOT READY anterior (CI sin evidencia para HEAD, Windows rojo sin diagnosticar, Cerberus sin pasar por v4) están cerrados con evidencia directa, no narración — verificado por mí en cada uno de los 3 casos mediante un canal que leí yo mismo (gh run view/api, sabotaje en vivo x2, lectura de diffs). Único hallazgo nuevo: cosmético (checkboxes del plan doc desactualizados), no bloqueante.

## 2026-07-11 — Issue #63 boot simplification final judgment, 93/110, READY WITH CONDITIONS

**Pattern: a Moriarty finding labeled "T1" in his own attack notes can be correctly reclassified as T2 by checking it against the project's OWN strict tier definition (Security/data-integrity/crashes), not against Moriarty's informal severity vocabulary.** boot_health.py's `check_version_mismatch()` uses raw string inequality (`installed != PLUGIN_VERSION`) instead of semver comparison, producing a backwards "update available" message when a newer manifest was later pinned to an older release. Moriarty called this "DECEPTION T1". Verified: (a) preexisting byte-for-byte on main (`git show main:...boot_health.py` has the identical line) — not introduced by this branch; (b) non-destructive — the REAL upgrade-trigger oracle (`upgrade_check.needs_upgrade()`) already uses correct semver `<` comparison and stays silent correctly; only the display STATUS line lies; (c) tracked in a real GitHub issue (`gh issue view 64`) explicitly labeled `[T2]` by the team with PoC, root cause, fix, and DoD — satisfies the Moriarty FALLA Rule's T2/T3 written-justification exception. Deferring this to a follow-up issue is defensible; treating it as a T1 mechanical-REJECT would have been over-applying Moriarty's own vocabulary instead of the project's tier table.

**Pattern: a Cerberus review commit range can be stale relative to current HEAD — always diff the review's OWN cited range against `main..HEAD` before crediting "Cerberus: LGTM/NOT MERGEABLE" as covering the branch.** Cerberus's only review of this branch was scoped `884bc2b..25ef9fa`, which sits right after the FIRST (later-discarded) implementation of the P1 gate — before Moriarty broke that v1 gate, before the v2 content-gate rewrite (decision 2d56444), before Argus's 2 T1 fixes, before producer hardening, and crucially before Moriarty round 3 found + this branch fixed a real data-loss regression. Cerberus's own last verdict ("NOT MERGEABLE as-is", dangling memory link) was never re-run against the final diff. Compensated by my own direct read of every production diff + 2 live RED→GREEN sabotage rounds (the orphaned-END data-loss fix, and Argus's `verify_path_within_project` guard in `upgrade_check.py`) — but named this explicitly as a pipeline-completeness gap rather than silently crediting a stale "Cerberus passed" narrative.

**Pattern: don't mechanically demand CI-green-on-push before rendering a verdict when the branch's OWN plan schedules push+CI as a task AFTER Yoda's verdict.** Unlike the 2026-07-10 issue #60 case (REJECTED — the task asked me to confirm CI already green on a SHA that was supposed to already be pushed), this branch's own plan (`docs/plan/refactor-boot-simplification.md`, Task 5) explicitly places "push de la rama; CI verde en la rama" AFTER Task 3 (Yoda's verdict) and Task 4 (Alexandria docs) — my pipeline position here is BEFORE push, by design. Verified via `git rev-list --left-right --count origin/main...HEAD` (branch 7 commits ahead of origin, including the entire headline data-loss-regression fix — zero CI evidence exists for current HEAD) and `git ls-remote` — real facts, not assumed. Rendered READY-to-proceed rather than NOT-READY-for-CI-absence, but named CI-green-on-final-SHA (both `ubuntu-latest`/`windows-latest` per `.github/workflows/toolkit-ci.yml`) as an explicit, mandatory pre-merge condition for whoever pushes/merges (Bex/Gitto), not a blocker of my own verdict at this pipeline stage.

**Pattern: a Cerberus-caught "dangling memory link" anti-pattern can RECUR and WORSEN within the SAME branch after being caught once — check `git status` for untracked agent-memory files even when a prior review already flagged and partially fixed one instance.** Cerberus's stale review caught 1 dangling file (`issue-63-boot-simplification-contract-notes.md`, later committed in 43b14eb). By current HEAD, 8 MORE issue-63 Dante topic files are linked from the committed `MEMORY.md` but sit untracked in the working tree (`git status --short` / `git ls-files` cross-check) — plus an uncommitted edit to `docs/plan/refactor-boot-simplification.md`. Named as a mandatory pre-push fix (trivial `git add`+commit), not a code-quality rejection.

**Score breakdown (93/110): Security 8 (2 real Argus T1 fixes + producer hardening + content-gate redesign, all verified live via my own sabotage; docked for the still-open STATUS bug, correctly-but-only-just-deferred, and for Cerberus's staleness on the actual security-relevant final code), Error Handling 9 (consistent fail-open discipline verified across every touched call site, matches established project convention), Architecture 9 (clean single-source-of-truth design, well-reasoned content-gate pivot, provably-safe-by-construction orphaned-END fix verified for first/middle/last block positions and above/below gaps; minor ding for 2 unrelated skill-doc commits bundled into the branch), Testing 8 (exceptional §34 rigor on the headline regression, personally reproduced RED→GREEN twice on two different mechanisms; docked for the process-completeness gaps above — stale Cerberus, no Moriarty round-4 re-confirmation after the fix landed, dangling memory links), Maintainability 8 (dense, decision-anchored comments throughout; docked for the dangling-memory-link/uncommitted-plan-edit hygiene gap and the accepted-but-real dead-text-duplication debt in #64).**

**Verdict:** READY WITH CONDITIONS (proceed to Alexandria → push → CI → PR; Bex retains merge). Conditions before push: commit the 8 dangling Dante memory files + the plan.md edit. Condition before merge: real green CI (both runners) on the final pushed SHA, verified via `gh run view` by whoever merges — not narrated. Neither condition is a code-quality defect; both are process/evidence gaps.

## 2026-07-18 — Issue #72 "adelgazamiento" (anti-attacker test thinning), 98/110

**Pattern: for a test-deletion-only round (no production behavior change), verify the deletion boundary itself, not just "does the suite stay green".** The real judgment work here was confirming EVERY removed test class was genuinely attacker-framed (external adversary, forged/injected payload, "compromised collaborator", planted symlink) and not integrity-framed (self-inflicted corruption, platform quirk, own-process failure). Read all 6 mixed-file diffs in full and cross-checked class-by-class against the plan's own conserve/remove list (`docs/plan/refactor-adelgazamiento-72.md` Task 2) — every single class matched exactly, including the fix-pass correction where Cerberus caught the plan's own "PARAR y reportar si es dudosa" rule being silently skipped for `TestScopesInjectionSanitization` (whose docstring named a non-attacker trigger, "corrupted Bilbo run", yet was pre-listed for deletion anyway).

**Pattern: "código vivo intacto" claims for a pure test round are verifiable in under a minute via `git diff --stat` — do it before reading anything else.** `git diff 9d43382 HEAD --stat -- unmassk-toolkit/` showed only 2 functional lines changed anywhere outside `tests/` (both static-list-literal removals of a filename), the rest pure test deletions/restorations + comment rewrites in `lib/`/`hooks/`. This single command answered both the §34 no-seam mechanical check (no producer↔consumer write/read path touched, gate does not fire, verified by me directly not narrated) and most of the Argus/Moriarty-omission defensibility question (zero new production code path = zero new attack surface to audit) before any deeper reading was needed.

**Pattern: a Cerberus review that self-reports "NOT MERGEABLE as-is" with concrete findings, landed as a real memory-note diff in the SAME commit as the fix pass, is strong evidence — but still requires independently re-reading the fix against each specific finding, not crediting "ya resueltos" from the orchestrator's summary.** Cerberus's own `anti-patterns.md` diff named 2 issues with file:line precision (sanitizer's control-byte class losing ALL direct unit coverage; the plan's own ambiguity-stop rule not honored for one class) and 3 lesser findings (9 stale by-name test-file references in production comments; a TOCTOU fd-leak concern Cerberus himself checked and found already covered elsewhere — a good example of a reviewer catching and closing his OWN near-false-positive before reporting it). Verified all 5 independently: read the new `TestSanitizeTrailerValueControlByteContract` (13 parametrized control bytes matching exactly what Cerberus said was uncovered, plus the `<memory-data>` fence regex, plus normal-text-preserved and whitespace-strip cases), read the restored `TestScopesRenderStaysSingleLine` (confirmed integrity-only framing, no attacker language), and read all 9 lib/hooks comment diffs individually (confirmed each stale by-name reference rewritten with an accurate, still-true remaining rationale, not just deleted).

**Pattern: an agent's own review sweep scope ("grep production dirs") can legitimately be narrower than the full repo — check the excluded zone yourself before accepting "0 remaining references".** Cerberus's stale-reference finding explicitly scoped itself to production files (`lib/`, `hooks/`, `bin/`), and the fix pass closed exactly those 9. A repo-wide grep for the same deleted filenames (`test_security_regression.py`, `test_control_byte_injection.py`) found 5 MORE comment-only references still alive in `tests/` (`conftest.py:267`, `test_pre_merge_gate.py:103`, `test_boot_freshness_hardening.py:46`, `test_boot_pending_next_cutoff.py:56-57,124`) — genuinely out of scope for what was fixed (nobody claimed to sweep tests/), non-functional (docstring-only, pytest doesn't care), but a real, nameable residual that neither Cerberus's sweep nor the fix pass's stated scope covered.

**Pattern: a static cleanup-list edit removing a filename that is "inexistente" in the CURRENT tree can still have existed historically — `git log --all --diff-filter=A -- <path>` before accepting "phantom reference" at face value.** `git-memory-dashboard.py` was added to `OLD_BIN_FILES` in the v1.0.0 merge commit (`037e0cb`) specifically to clean up a real pre-v1.0.0 artifact (added `48af246`, a genuine dashboard feature later retired). Removing it from the cleanup list is not incorrect, but "referencia fantasma (fichero inexistente)" mischaracterizes it — it existed, just not now, and the list's whole purpose is catching exactly this kind of historical leftover. Practically inert given the project's single-owner threat model (no real users with a stale pre-v1.0.0 install to miss-clean), scored as an Observation, not a deduction-worthy finding on its own — but worth naming precisely rather than accepting the commit message's framing.

**Pattern: a GitHub issue's own literal DoD can have more checkboxes than the work delivered — check `gh issue view` even when a signed decision commit narrows scope, and say explicitly that "ready to commit" and "ready to close the issue" are different questions.** Issue #72's DoD had 3 items: (1) remove anti-attacker tests — done; (2) keep only platform/integrity tests — done for the files touched; (3) "retirar código muerto/sobre-ingenierizado (gates de proceso, binarios de mantenimiento, fetch-stamp sobre-ingenierizado, motor de migraciones)" — NOT done, directly contradicted by decision `7e7f2c2`'s "no tocar código vivo". The numeric line-count DoD target (8-10k) was also formally abandoned via that same decision. The decision commit is a legitimate, well-reasoned scope narrowing (documented, with a concrete reason — "inalcanzable sin destripar integridad"), but the GitHub issue itself was never edited/commented to reflect it. Recommended: commit the reviewed work now (it's ready), but don't close #72 outright — either edit the issue to strike item 3 with a link to the decision, or leave it open/re-scope it, so the issue's own literal text doesn't misrepresent what shipped.

**Score breakdown (98/110): Integrity 9 (zero producer/consumer seam touched, real §34 no-seam mechanical check performed by me; docked lightly for the dashboard-list "phantom" mischaracterization), Error Handling 9 (nothing touched in this dimension by the diff itself; the one relevant fail-loud test — `TestBootLogWriteFailureLogsWarning` — verified still present and untouched), Structure 9 (clean class-by-class execution against the plan's own list, verified exactly), Real verification 9 (new tests are real/non-tautological against real production functions, suite run by me directly — 1078 passed, 2 skipped, exit 0, 253.89s, arithmetic cross-checked against all 4 phase commits' self-reported counts; docked for the 5 residual stale tests/ comments outside anyone's stated sweep scope and for Dante leaving no dedicated memory-note artifact this round, narration-only), Maintainability 8 (very clean comment rewrites in all 9 lib/hooks files; docked for the same two residuals above).**

**Verdict:** APPROVED (ready to commit), 98/110. NOT a recommendation to close GitHub issue #72 as fully resolved — its own DoD item 3 (dead-code removal) was explicitly descoped by decision, but the issue text itself doesn't reflect that; flagged as a closing-mechanics question for Bex/Gitto, not a code-quality blocker. Zero T1/T2 findings from Cerberus survive unaddressed (both verified closed by me directly); Argus/Moriarty omission defensible and verified structurally (zero commits, zero new production code path in the diff).

## 2026-07-18 — Issue #61 silent-memory-loss read-path retry, final judgment (92/110)

**Pattern: grep the codebase's OWN prior "breadcrumb"/pointer comments as a completeness cross-check, don't just trust the current pipeline's stated site list.**
House's diagnosis this session (memo `4500f81`) and the plan (`docs/plan/fix-silent-memory-loss-61.md`)
both named exactly 4 production read sites; Cerberus's Verify-round sweep added 3 more (7 total,
matching decision `e9400db` + the Verify-round expansion). But an EARLIER, separate House root-cause
pass (commit `07e194a`, `git log` shows it predates this session) had already added
`# breadcrumb #61: transient git failure here used to collapse to None with zero trace` comments to
`lib/bootstrap_commits.py:123` and `:148` (`scan_recent_commits()`, used by `git memory bootstrap`),
and Cerberus's OWN earlier follow-up (dated 2026-07-11, recorded in
`.claude/agent-memory/unmassk-toolkit-dante/issue-61-ci-flake-hardening-notes.md`) explicitly listed
these 2 sites among "9 real production call sites" needing the WARN breadcrumb (which they got,
`log_stderr_on_failure=True`, confirmed in `07e194a`'s diff). None of this session's House/Cerberus/
Ultron passes touched `bootstrap_commits.py` — a simple `grep -rn "run_git(" lib/ hooks/ bin/ | grep -v
run_git_read_retrying` cross-referenced against `grep -rn "breadcrumb #61\|issue #61"` surfaced the gap
immediately (2 call sites, lines 126/150 in current HEAD, still plain `run_git()`, no retry). Verdict:
APPROVED WITH CONDITIONS (92/110) — the boot-critical path (every-session recall/glossary/timeline,
the actual Ubuntu-CI flakiness root cause) is genuinely fixed and mutation-tested; `bootstrap_commits.py`
is a real but lower-blast-radius residual (manual `git memory bootstrap` command, output is
human-reviewed before any commit is made per its own docstring — never auto-consumed on every session)
classified as Minor/tracked follow-up, not a blocker for closing #61's diagnosed scope.

**Pattern: reproduce a reported mutation-kill myself, don't just read the agent's narration of it.**
Dante's memory notes described mutation-killing the SEC-HIGH-001 per-attempt timeout cap
(`call_kwargs["timeout"] = max(0.1, min(remaining, base_timeout))` in `lib/git_helpers.py`'s
`run_git_read_retrying()`) by reverting it to `base_timeout` and watching
`test_slow_then_would_be_hanging_second_attempt_gets_capped_timeout` fail. I repeated this myself
(edited the live file, ran the test class, saw the exact same failure — `received_timeouts[1] == 10`
not `< 9` — restored from a backup, confirmed `git diff --stat` empty). This is what the Round-Trip
Evidence Rule demands for a latency-bound claim: read the artifact myself, not the agent's transcription
of it.

**Score breakdown:** Integrity 8/3=24, Silent-failure 8/3=24, Structure 9/2=18, Real verification
9/2=18, Maintainability 8/1=8 → 92/110. Docked consistently across Integrity/Silent-failure/Real-
verification for the same root cause (the `bootstrap_commits.py` gap), not 3 independent issues.

## 2026-07-19 — Fix atómico CLAUDE.md (git_helpers._AtomicWriteNoFollowSymlink)

**Pattern: mutation-kill reproducido en vivo en vez de confiar en el reporte de Moriarty.**
Los dos mutation-checks documentados en tests/test_atomic_claude_md_write.py (chmod-preservation
y orphan-sweep) los reproduje yo mismo: comenté/parcheé la línea real en lib/git_helpers.py,
corrí SOLO esa clase de test, confirmé rojo con el mensaje exacto esperado (0o600 en vez de 0o644;
orphan sigue existiendo), restauré con `git checkout --` y confirmé `git status` limpio. Coste bajo
(2 ediciones puntuales), evidencia de primera mano en vez de narrada.

**Pattern: verificar el "no regresión" contando callers, no leyendo el diff de cada uno.**
`grep -rn "open_no_follow_symlink(" | wc -l` (71 sitios) vs `grep -rn "atomic=True"` (exactamente
4 call sites en 3 ficheros: session-start-crew.py x2, install_apply.py x1, git-memory-uninstall.py x1)
confirma mecánicamente que el resto de callers no cambiaron de comportamiento sin tener que
re-leer los 71 uno por uno.

**Pattern: memo de git-memory como evidencia de scope correcto para un hallazgo colateral.**
La carrera lost-update que Moriarty encontró (pre-existente, no introducida por el fix) estaba
documentada como memo `eae0880` con reproducción real (2 in-process + 8 procesos) y explícitamente
diferida a decisión de Bex — eso es lo que separa "hallazgo correctamente escopeado fuera" de
"hallazgo tapado". Confirmé el memo existe y dice eso antes de aceptar la afirmación del orquestador.

**Pattern: suite completa 1129/2 corrida por mí mismo vía nohup + polling con `until kill -0`,
nunca narrada.** El log crudo de pytest (dots + resumen final) es el canal directamente leído que
exige el Round-Trip Evidence Rule — no un resumen de otro agente.

## 2026-07-25 — Dead-end memory loop (deadend Memo category + Bilbo recall whitelist)

**Pattern: when Moriarty's own memory file wasn't updated for the round (stale mtime), don't accept the orchestrator's narration of "Moriarty found X" as the §34 sabotage artifact — reproduce the sabotage myself.**
Checked `.claude/agent-memory/unmassk-toolkit-moriarty/MEMORY.md` mtime: last touched 2026-07-19, six days before this session — Moriarty never persisted this round's BREAK1/BREAK2 findings to its own memory. The only trace was the orchestrator's memo commit (`3562561`) and the task-prompt paraphrase, neither of which counts as a channel I read myself per the Round-Trip Evidence Rule. Fix: edited `bin/git-memory-commit.py` in place to remove the `sanitize_trailer_value()` call (reverting to the pre-fix shape), ran `test_trailer_newline_regression.py` → confirmed RED with the exact silent-loss symptom described (orphan physical line, `NO_DEBE_PERDERSE` fragment split off), then `git checkout --` to restore and confirmed GREEN. This is a legitimate substitute for a missing Moriarty artifact — the gate cares about a mechanically-verified real corruption + independent-channel confirmation, not about which agent's hand did the sabotage.

**Pattern: a dead pre-commit validation layer is not automatically a T1 blocking the feature that happens to add a new value to the validated set.**
`pre-/post-validate-commit-trailers.py` don't fire on the real wrapper commit path (`extract_commit_message` looks for `-m`, the wrapper never uses it) — confirmed pre-existing, not touched by this diff. Distinguished this from BREAK2 (T1, active silent data loss on ALL trailers via embedded newline, fixed this round) by checking whether the feature's actual READ path depends on the dead layer: `scan_trailers_memory()`/`recall()` (what Bilbo/boot actually use) are independent of `parse_trailers()`/`validate_trailers()` (the dead hooks) — grep-verified via `git-memory-commit.py`'s import list (`from parsing import ... sanitize_trailer_value`, no `validate_trailers` import at all). A missing guardrail (defense-in-depth gap) that nothing currently exploits is T2/T3-class disclosed debt, not a T1 blocking THIS merge — verify the dependency graph before applying the FALLA/T1 auto-reject rule to a pre-existing finding.

## 2026-08-06 — Robustez memoria v2 + CI (customs.py rescate, stop-dod-gate aviso, doctor zonas #13)

**Pattern: mutation-kill en vivo sobre el fix de determinismo de Moriarty, con 5+ PYTHONHASHSEED reales, no solo confiar en el reporte "confirmado en 5 corridas".**
El fix reordena `_COMMIT_CREATING_SUBCOMMANDS` (un `set`, orden dependiente del hash seed del proceso) para
priorizar `rebase`/`merge`/`cherry-pick` en el fallback de `_find_commit_creating_statement` cuando
`shlex.split()` falla. Corri la clase de test real (`TestRescuePassthroughSurvivesShlexTokenizationFailure`)
bajo `PYTHONHASHSEED=0..4`: 5/5 verde con el fix. Luego muté una copia EN MEMORIA (no en disco de forma
permanente -- ver conventions.md, sección "Git-safety HARD RULE", incidente de esta misma sesión) quitando solo el reordenamiento
(dejando el resto del fix intacto) y corrí `PYTHONHASHSEED=0..7`: rojo en 6/8 seeds, con fallos distintos según
el seed (a veces `merge --abort`, a veces `rebase --continue`/`--skip`) -- exactamente el bug no-determinista
que el fix documenta haber cerrado. El fix es real, no cosmético.

**Pattern: verificar un "T1 de Moriarty arreglado" ejecutando el escenario exacto contra el binario real, no solo leyendo el test.**
Para el segundo T1 (`check_project_config()` da falso verde sobre `{"customs_enabled": "true"}`), corrí
`git-memory-doctor.py --json` de verdad contra un `config.json` con ese contenido exacto: `level: "error"`,
mensaje `"corrupt: 'customs_enabled' must be boolean, got str"`. Coincide exactamente con lo que Ultron/Cerberus
reportan, verificado por un canal independiente (stdout JSON real del proceso, no el reporte del agente).

**Pattern: "N fallos preexistentes, confirmado por Ultron revirtiendo sus ficheros" se re-verifica con
`git show HEAD:<path> > <path>` (lectura pura), NUNCA con `git stash`/`git checkout --` en este repo específico.**
Ver conventions.md, sección "Git-safety HARD RULE" -- este repo tiene una regla dura de git-safety escrita por Ultron (múltiples sesiones
concurrentes sin commitear en el mismo árbol). Repetí la comparación de los 3 fallos (`test_boundary.py` x2,
`test_rejection_relaunch_commands.py` x1) con el método correcto después del incidente: idénticos antes/después,
confirmado también que un 4to fallo que apareció en una corrida completa (`test_gitcmd.py::
test_concurrent_writers_to_same_index_serialize_via_file_lock`) es flaky bajo carga (rojo en la corrida
completa de 580s/966 tests concurrente con otro proceso, verde en aislamiento) -- no es un 4to fallo real.

**Pattern: una función helper que "resuelve un caso" puede dejar el otro caso (corrupción real, no solo
vacío) cayendo en el manejo de errores YA existente más arriba en la pila -- verificar el camino completo,
no solo la función nueva.** `health.zones_state()` colapsa corrupto→"empty" a propósito (documentado, mismo
criterio que `memory_mounted()` ya aplicaba). Verifiqué que esto NO deja `zones.py list` crasheando con una
traza cruda sobre zones.json corrupto: `_cmd_list()` cae al `zones_lib.load()` real después del check de
"absent", que SÍ lanza `ValueError`, pero el `except Exception` genérico de `main()` (línea 259, comentario
"nunca una traza de pila") lo convierte en stderr limpio + exit 1 -- confirmado ejecutando el escenario real
(rc=1, stderr con mensaje claro, sin traceback). Mismo comportamiento que existía ANTES de este diff
(`_cmd_list` ya llamaba `zones_lib.load()` sin try/except propio desde siempre) -- no es una regresión.

## 2026-08-20 — stop-dod-gate.py exit 5/1/2 classification + D-042 (declared identity) + git tri-state

**Pattern: never background a real pytest run with raw `nohup ... &` when the suite under test contains a
real-signal test (SIGHUP/SIGINT/etc.) -- it produces a reproducible FALSE failure, not a flaky one.**
`TestSignalKilledProcessBlocks::test_process_killed_by_sighup_blocks` failed 2/2 identically when I
backgrounded the full suite myself via `nohup python3 -m pytest ... &`, but passed 1/1 in isolation and
981/981 (0 failed) when I reran the exact same 78-file subset via the harness's own `run_in_background`
(no `nohup`). Root cause confirmed by a minimal repro: `nohup`'s whole purpose is to set `SIGHUP` to
`SIG_IGN` for its direct child, and POSIX `exec()` PRESERVES an ignored disposition across exec (only
CAUGHT dispositions reset to default) -- so every grandchild `subprocess.run()` spawns downstream (pytest's
own child, and that child's own child in the SIGHUP self-kill test) inherits the ignore, and
`os.kill(os.getpid(), SIGHUP)` becomes a silent no-op, changing the test's own precondition ("the child
really gets killed by a real signal") without changing anything in the code under test. Isolated repro:
`nohup python3 -c "subprocess.run([...self-SIGHUP...])" ` -> returncode 0 (ignored) vs the same command
run directly -> returncode -1 (really killed). **Rule going forward: for any test suite in this repo that
exercises real OS signals, use the Bash tool's own `run_in_background: true` to background a long pytest
run, never a manually-typed `nohup ... &`** -- confirmed one is safe, the other silently corrupts signal
tests' own preconditions. Do not report a signal-based test failure as a real regression before ruling
this out first (rerun in isolation AND rerun the background job without `nohup`).

**Pattern: a hook's `_run_test_command()`-style subprocess wrapper with `subprocess.run(...,
encoding="utf-8", ...)` (strict decode) inside a broad `except (..., ValueError)` fail-open clause silently
swallows a REAL failure whenever the child's stdout/stderr contains one invalid UTF-8 byte -- because
`UnicodeDecodeError` IS a `ValueError` subclass, so it lands in the SAME bucket as "could not run the
command at all," even though the command DID run and DID fail for real.** Live repro against the actual
hook (`hooks/stop-dod-gate.py::_run_test_command`, this exact idiom pre-dates this session's diff --
confirmed via `git diff`, lines unchanged): `test_command` prints `b"FAILED test_x - AssertionError: bad
byte \xff\xfe here"` and exits 1 (a completely real, unambiguous red) -- the hook produces ZERO output
(no JSON block, no stderr) and exits 0, silently allowing session close. This is exactly the project's own
named worst case ("un fallo que pasa callado"), live on the hot path of the one feature whose entire
stated purpose is "never let a real red pass silently" -- and missed by Cerberus, Argus, Dante, AND
Moriarty across a fairly deep multi-round pass on this same file. Reported as a Major (not blocking that
session's diff, since the buggy code pre-dates it and lives in an untouched function -- D1-D5's scope was
only the exit 5/1/2 tree), named as an urgent follow-up with the exact fix (`errors="replace"` on the
`subprocess.run` call, or split `UnicodeDecodeError` out of the generic fail-open except into its own
"real failure, non-UTF8 output" block-branch). **Check for this pattern in ANY hook that runs an
arbitrary, project-configured external command** (as opposed to this codebase's OWN git subprocess calls,
which are much more UTF-8-hardened already per many prior sessions) -- `test_command` is uniquely exposed
because it can be literally any test runner in any language, unlike the codebase's internal `git` calls.

**Pattern: a Cerberus "NOT MERGEABLE" T1 verdict can be legitimately, honestly closed WITHOUT literally
satisfying the reviewer's own repro, when the repro turns out to be provably unfixable from the available
signal, and the fix instead covers the REAL underlying risk class.** Cerberus's T1 repro for the
`is_tracked_in_head()` boolean-collapse bug used "commit a file, delete it, rename `.git` away" as the
demonstration. Ultron's fix (`git_tracked_status()`, tri-state) verifiably CANNOT make that exact literal
scenario block, because `git rev-parse --is-inside-work-tree` and `git ls-files` produce byte-identical
output/exit-code whether `.git` was renamed away after real commits existed or never existed at all --
confirmed by hand, no git-observable signal survives `.git`'s removal to distinguish the two. Ultron
documented this explicitly (docstring "Known, accepted limitation (verified by hand, not assumed)") and
shipped the fix for the actually-realistic, actually-repeatable transient-failure class instead (a LIVE
repo whose `ls-files` fails for some other reason -- corrupted index, permission error), which I
independently re-verified live (real repo, real `.git/index` corruption, hook correctly blocks) --
distinct from the ".git entirely gone" case, which I ALSO independently reproduced and confirmed resolves
to ALLOW, exactly as documented, not a new silent regression. No subsequent Cerberus re-pass exists
confirming this narrower closure (their memory's last recorded verdict is still literally "NOT
MERGEABLE") -- treated this as a stale-Cerberus-scope gap (same class as the 2026-07-18 pattern) and
closed it myself via direct live reproduction of BOTH sides of the fix, rather than either trusting an
unconfirmed narrative or mechanically rejecting on a stale verdict. Recommend the `.git`-fully-gone
residual get the same explicit owner sign-off D-042 got (Bex named it directly), since it's the same "D2
golden rule" territory -- named as a Minor, not blocking.

**Verdict: APPROVED WITH CONDITIONS, 85/110.** Full detail: D-042 (Moriarty's flagship T1+DECEPTION --
brand-new top-level test-first module always blocked) verified fixed live, both sides (declared identity
via pyproject.toml allows; no declared identity still blocks, exactly the accepted residual, both
independently reproduced against the real hook). Git tri-state T1 (Cerberus) verified fixed for the real
transient-failure class live. Argus's SIGHUP-vs-infra-sentinel LOW fix verified via direct code read +
isolated test + clean full-suite background run. §34 round-trip gate on the state file done personally
(real write→read, 2 sabotage variants). The one NEW Major finding above (UTF-8 strict-decode swallowing a
real failure) is the single named condition, urgent but not blocking THIS diff (pre-existing, untouched
function, out of D1-D5's stated scope).

## 2026-08-23 — Blind self-review of my own agent sheet (yoda.md diff)

**Pattern: check every new instruction for a term the doc never defines.**
The diff added "downgrade to the neutral register" (Emotional Register section) but no
register in the table is labeled "neutral" — the closest candidate ("Solid but unremarkable")
isn't named that. An instruction that tells me to fall back to an undefined thing is not
executable as written, even though it reads fine on a first pass. Worth this exact check
whenever a diff adds a fallback/default behavior: does the target of the fallback actually
exist elsewhere in the same document?

**Pattern: two structurally parallel rules, added in the same diff, that use different
anchoring mechanisms for the same underlying question are a coherence gap even with no
outright contradiction.** Noise Control's Cerberus re-review rule ("if the diff changed
after his review") and the adjacent Argus re-audit rule ("if code changed... after his
audit's commit") ask the same thing but only one names a mechanical anchor (a commit).
Same-shape rules should share the same anchor unless there's a stated reason not to.

## 2026-08-24 — I-003 rules.py split (rules_commit/rules_similarity/rules_validate) + resurrected coherence_rules + checklist-gate/skill-checklist-inject + textnorm.py unification

**Pattern: a centralized fix's mutation-kill can legitimately be green on one caller and red on another, and that split IS the evidence, not a contradiction.**
Sabotaged `notes_commit.py::stage_and_commit()`'s new post-commit-failure `git reset` (the "MM state" fix) live:
`test_rule_commit_contract.py::TestFailedCommitLeavesNoStagedLeftovers` went RED (real 'MM' in
`git status --porcelain`), but `test_notes.py::test_commit_rejected_by_pre_commit_hook_leaves_a_fully_clean_tree`
stayed GREEN under the same sabotage -- because `notes.write()` already carried its OWN local `git reset`
predating this centralization (documented explicitly in the same docstring: "los `git reset` que ya existian
en los llamadores de notes.py... no se tocan -- quedan redundantes pero inofensivos"). Restored via direct
`open()/write()` (never `git checkout --`/`stash`, per this repo's hard git-safety rule), confirmed both
green again, confirmed `git diff` byte-identical to pre-sabotage. Lesson: when a "single shared fix" docstring
names one caller as already-protected-by-something-else, a mutation-kill that only breaks the OTHER caller is
not a gap in the test suite -- it's the direct confirmation of exactly what the docstring claims.

**Pattern: `query.by_zone()` (called unconditionally right before `health.build()` in `boot.build()`) already
raises `RuntimeError` on a real, non-transient git failure -- this is Sec.8.2's own declared, pre-existing
architecture ("fail loud, never silent" for a real git failure, only retry+swallow a transient one). A new
function (`health.coherence_rules()` -> `query.show_file_at_head()`) that does the same is NOT a new
availability risk introduced by this diff -- it's following the established convention of the module it lives
in. Checked this before treating "coherence_rules can raise on real git corruption, uncaught in boot.build()"
as a finding.

**Verdict: APPROVED, 106/110.** Full suite run personally (`nohup`-free, via harness backgrounding):
1183 passed, 2 skipped (both pre-existing Windows-only skips, verified irrelevant to this diff), 0 failed.
Round-trip (§34) evidence: real subprocess git (`index.lock`, real `pre-commit` hook, real thread-race,
real repo state for "exists on disk but not in HEAD") across `test_rule_commit_contract.py` +
`test_health_rules_coherence_contract.py` (Moriarty's own two confirmed sabotage classes: pre-commit-hook
rejection after `git add`, and a never-committed first-ever rule crashing `coherence_rules()` -- both closed,
both independently reproduced by me for one of them). D-054 (checklist strips accents too) and the
external-hand-edit race window in `rules.add()` (both pre-accepted per CLAUDE.md's task briefing) correctly
NOT re-litigated -- confirmed present and correctly scoped as accepted, not silently dropped.
One stale note found and resolved: Dante's own contract-notes file for D-054 records a RED (non-string input
to `textnorm.normalize_text` raising instead of returning `""`) that Ultron fixed AFTER that note was written
-- confirmed by reading `textnorm.py`'s actual guard and re-running the exact named test
(`test_normalize_non_string_input_returns_empty_string_without_raising`) in isolation: PASSED. Not a live gap.

## 2026-08-27 — unmassk-trading fase 1 (SKILL.md + 5 refs + 5 scripts + 645 tests), 96/110

**Pattern: cuando una feature es sobre todo PROSA que un Claude ejecuta, el juicio se hace
verificando afirmación por afirmación contra el canal que la afirmación cita — no leyendo la
prosa.** SKILL.md/gate-input.md/risk-and-sizing.md afirman ~14 hechos comprobables con la
palabra "verified" al lado. Los corrí todos yo: `TRADING_ALLOWED`+`EMPTY_STATE` con state-dir
vacío (exit 0), `REVIEW_REQUIRED` sin el pipe con la lista de razones EXACTA
`['market_regime artifact not provided','circuit_breaker artifact not provided']`, `NO_GO`
con el pipe HALTED, `--fail-on-non-go` → exit 2, razones ausentes de stdout y presentes solo
en el JSON, sizer 500€/0,75% → posición > cuenta con exit 0 y sin aviso, sizer sin
`--fractional` → "0 shares / Risk: $0.00 (0.0%)" exit 0. Los 14 se sostuvieron. **Una skill
cuya seguridad vive en prosa se audita ejecutando la prosa, no leyéndola** — y aquí la prosa
resultó exacta hasta las cadenas literales.

**Pattern: la afirmación "levantado byte a byte" SE VERIFICA con el repo origen clonado, y es
barata.** `scratchpad/repos/tradermonty_claude-trading-skills` estaba ahí. Diff de los 10
artefactos levantados: 5 scripts/schema + 5 docs → **exactamente** la cabecera de atribución
(5 líneas `#` o 8 líneas `<!-- -->`) y **una sola** línea de lógica
(`check_pre_trade_discipline.py:434`, ruta del módulo hermano), justo lo que declara
`CREDITS.md`. El schema JSON: 0 líneas de diff. Nunca aceptar "byte-idéntico" narrado cuando
el origen se puede clonar.

**Pattern: 5 mutaciones en vivo sobre el fichero real (restauradas desde variable en memoria,
sha256 idéntico antes/después) valen más que 645 tests en verde.** S1 reloj muestreado antes
del fetch → 3 rojos; S2 spread 0 en vez de None cuando falta una fuente → 9 rojos; S4
`if missing or len(rows)<2` neutralizado → 17 rojos; S5 check de edad neutralizado → 10
rojos. **Y dos sabotajes del PRODUCTOR REAL sobre el round-trip vivo**: endpoint Kraken
cambiado a `/public/Assets` → el test live muere con `SINGLE_SOURCE`; campo `c` (último
precio) cambiado a `o` (apertura) → el test live muere con `DISAGREE` a 128 bps. El segundo
es la mejor evidencia posible de que el diseño de dos mercados hace lo que dice: una deriva
semántica silenciosa en una fuente la cazó la OTRA fuente, no un fixture.
**Nunca usé `git checkout`** — leer bytes a variable, escribir mutación, restaurar escribiendo
la variable, verificar sha256 (regla de conventions.md, incidente propio 2026-08-06).

**Pattern: "CI en rojo" no es "esta feature está en rojo" — abrir el run y leer QUÉ job murió.**
`gh run list` mostraba 5 fallos seguidos en los commits de trading. `gh run view <id>` mostró
que el job `unmassk-trading script tests (ubuntu)` estaba **verde** (643 passed, 2 deselected —
los dos `@pytest.mark.live`) y que el rojo era el job de los plugins maker (`numpy==2.4.6` no
existe para Python 3.10), preexistente y ajeno. Más aún: la decisión de darle a trading su
propio job (commit `83375b5`) quedó **validada por este mismo run** — sin ella el resultado de
trading habría quedado escondido tras el fallo de dependencias de otro plugin.

**Pattern: un hallazgo T1 de Moriarty que se cierra con documentación en vez de código es
aceptable SOLO mientras la fase no toque dinero — y hay que decir en qué fase deja de serlo.**
De los 6 BREAK de Moriarty, 5 se cerraron con prosa (el código levantado no se toca por
diseño). Para fase 1 (leer/practicar/dimensionar, cuenta de papel sin clave) eso basta: ningún
fallo puede costar dinero. Para fase 2 (ejecución real) no basta, y lo dije como condición
nombrada. **BREAK 6 (carrera lost-update en `thesis_store.link_report`, 4 de 8 entradas
perdidas y las 8 llamadas devolviendo éxito) es el único que no dejó rastro en NINGÚN sitio del
plugin** — ni código ni documento. Lo encontré grepeando los 6 BREAK contra los .md del plugin
uno por uno, no leyendo el informe. Un hallazgo de Moriarty sin rastro en el artefacto es un
hallazgo que se redescubre entero dentro de dos fases.

**Pattern: reproducir la cifra rara de un documento antes de llamarla falsa.**
`risk-and-sizing.md`/`SKILL.md` decían "500 € cuenta, stop 0,75% → posición de 661 €". Con la
receta documentada (`--share-precision 8`) sale 666,64 €. Fuerza bruta: sale **661,67 € exacto
con `--share-precision 4`**. No es una cifra inventada, es una cifra de una corrida con flags
distintas a las que el propio documento manda usar. Minor, no fabricación — pero en un fichero
cuyo lema es "los ejemplos que no sobreviven a ser ejecutados son cómo una skill le enseña algo
falso a su usuario", la asimetría se nombra.
