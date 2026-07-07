# Judgment Patterns

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
