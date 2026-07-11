# Mapa técnico — issue #63 (simplificación del boot)

Rama: `feat/issue-63-simplificacion-boot`. Alcance FIRMADO, 6 puntos (decisión 0f5af98). Este documento es
mapa puro (Bilbo) — no propone implementación, no audita seguridad.

Repo: `unmassk-toolkit/` (plugin fuente). Hook registry: `hooks/hooks.json`.

## 1. Bloques managed de CLAUDE.md — regenerados en CADA boot

**Cadena real:** `hooks/hooks.json` (SessionStart, 2º hook) → `hooks/session-start-crew.py:36-82` (`main()`)
→ `lib/managed_blocks.py:161` (`upsert_managed_blocks()`).

- `session-start-crew.py:61` llama `upsert_managed_blocks(content)` **incondicionalmente** en cada
  SessionStart — sin mirar versión antes. Lee CLAUDE.md, corre `upsert_managed_blocks()` (regex diff
  contra los 5 bloques definidos en `managed_blocks.py:31-139`), reescribe el archivo solo si cambió algo.
- **Confirmado (grep):** `session-start-crew.py` no menciona `manifest` en ningún punto — cero lectura de
  `.claude/.unmassk/manifest.json` antes de decidir si regenerar.
- **Marcador SÍ existe y es usable:** `manifest.json` tiene campo `"version"` (creado en
  `lib/install_apply.py:_create_manifest():243` y actualizado en `bin/git-memory-upgrade.py:~330`, ambos
  escriben `"version": VERSION`). `lib/version.py` expone `VERSION` leído de
  `.claude-plugin/plugin.json`. Comparar `manifest.version == VERSION` (string) ya es exactamente el
  patrón que usa `needs_upgrade()` (punto 2) vía `_parse_semver()` — mismo criterio, otro call site.
- **Otro consumidor de `check_skill_drift`/`check_version_mismatch`:** `lib/boot_render.py:146-174`
  (`render_status_section()`, invocado desde `session-start-boot.py:306`) YA lee manifest.json vía
  `lib/boot_health.py:check_version_mismatch():165-194` para el aviso "Plugin vX available" — es decir,
  el mecanismo de leer manifest.version ya existe en el codebase, solo no está conectado a
  `session-start-crew.py`.
- **Duplicación de la escritura de bloques:** `git-memory-install.py --auto` (invocado por el punto 2,
  cada UserPromptSubmit cuando hay upgrade) también reescribe CLAUDE.md vía
  `lib/install_apply.py:_update_claude_md():207-223` → mismo `upsert_managed_blocks()`. Dos rutas
  distintas (SessionStart sin gate + UserPromptSubmit con gate de versión) escriben el mismo archivo con
  la misma función. Riesgo de carrera / doble escritura en la misma sesión si el manifest está desfasado
  justo al bootear.

**Tests que cubren `upsert_managed_blocks()` / hook:** `tests/test_managed_blocks.py` (36 tests —
`TestBlocksDefinition`, `TestUpsertManagedBlocks`, `TestHelpers`, `TestInstallFiveBlocks`,
`TestCrewHookFiveBlocks` líneas 402-465, `TestUninstallFiveBlocks`), `tests/test_session_start_crew.py`
(5 tests, enfocados en encoding no-UTF8 del CLAUDE.md, no en gating por versión).
**Ninguno de estos tests ejercita un gate por manifest.version** porque ese gate no existe todavía —
cualquier test nuevo para "no regenerar si version no cambió" es 100% nuevo (RED).

**Dependencia con punto 2:** si se gatea `session-start-crew.py` por manifest.version, hay que decidir
qué pasa el primer boot tras un `/plugin update` a mitad de sesión (el manifest en disco todavía apunta
a la versión vieja hasta que corre `needs_upgrade()`/`--auto`) — orden de ejecución entre los dos hooks
importa.

## 2. Auto-upgrade del manifest — en CADA UserPromptSubmit

**Cadena real:** `hooks/hooks.json` (UserPromptSubmit, único hook) → `hooks/user-prompt-memory-check.py`
→ `needs_upgrade()` (líneas 87-142) llamado en `main()` línea 204, **sin gate de "ya se corrió esta
sesión"** — se evalúa en cada mensaje.

- `needs_upgrade()` hace 2 checks (unión, cualquiera dispara upgrade):
  1. Lee CLAUDE.md (`open_no_follow_symlink`, línea 108) buscando markers viejos (`"python3 bin/"` o
     falta `"Context Checkpoint Commits"`).
  2. Lee `.claude/.unmassk/manifest.json` (línea 129), parsea `manifest.version` con `_parse_semver()`
     (líneas 68-84, exige exactamente X.Y.Z, sin prerelease) y compara `< PLUGIN_VERSION`.
  - Fail-safe a `False` en cualquier error/manifest ausente/versión no parseable (líneas 96-99,
    111, 136, 139, 142) — nunca produce loop infinito.
- Si `True` (línea 203-213): `subprocess.run([sys.executable, git-memory-install.py, "--auto"], timeout=15,
  cwd=root)` — todo envuelto en `try/except Exception` (fail-open, línea 211-213).
- **Costo real por mensaje:** 2 lecturas de archivo (CLAUDE.md + manifest.json) SIEMPRE, más un
  subprocess de hasta 15s SOLO cuando hay upgrade pendiente (no en cada mensaje una vez sincronizado).
- **Mover a SessionStart:** ya existe `session-start-boot.py` (hook SessionStart #1) y
  `session-start-crew.py` (hook SessionStart #2) — el chequeo cabría en cualquiera de los dos. El caso
  a no perder ("plugin actualizado a mitad de sesión") es EXACTAMENTE lo que el comentario en
  `skills/unmassk-gitmemory/SKILL.md:108` describe como comportamiento actual esperado: "Version marker
  auto-sync (UserPromptSubmit): on every message... If the manifest is older,
  bin/git-memory-install.py --auto runs transparently". Si se mueve a SessionStart, un
  `/plugin update` a mitad de sesión NO se detecta hasta el próximo `SessionStart` (nueva sesión) —
  cambio de comportamiento real, no solo de timing, que el plan debe decidir explícitamente.

**Tests:** `tests/test_needs_upgrade_semver.py` (18 tests — comparación semver, fail-safe, no-loop,
razones preexistentes que deben seguir gatillando) es el contrato completo de `needs_upgrade()`.
`tests/test_upgrade.py` (7 tests, cubre `git-memory-upgrade.py` CLI, no el hook).
`tests/test_hardening_recall.py` cubre que el `try/except` alrededor de `needs_upgrade()` +
`subprocess.run()` no rompe el hook (líneas 8, 101, 167). `tests/test_security_regression.py` tiene 2
regresiones de seguridad sobre `needs_upgrade()` (símlink en manifest.json línea ~1672-1719, símlink en
CLAUDE.md línea ~2137-2159) — mover esta lógica a otro hook implica mover también estas protecciones.
`tests/test_user_prompt_recall.py:46,69-90` y `tests/test_user_prompt_skill_router.py:110,137` fijan
manifest con versión actual precisamente para EVITAR que needs_upgrade() dispare durante esos tests —
si se mueve el gate, estos fixtures dejan de ser necesarios ahí y pasarían a necesitarse en los tests
del hook de destino.

## 3. Drift check de skills — por qué salta en proyectos SIN código fuente del toolkit

**Ubicación:** `lib/boot_health.py:110-162` (`check_skill_drift()`), invocado desde
`lib/boot_render.py:165` dentro de `render_status_section()`, llamado desde `session-start-boot.py:306`
— corre en **cada SessionStart**, sin relación con si el repo tiene o no el código fuente del toolkit.

**Causa raíz confirmada (bug de cálculo de ruta, no diseño intencional):**

```python
CACHE_BASE_DIR = ~/.claude/plugins/cache/unmassk-claude-toolkit          # boot_health.py:51
REPO_BASE_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # :52
```

`REPO_BASE_DIR` se calcula subiendo 3 niveles desde la ubicación del propio archivo. Esto es correcto
SOLO cuando el módulo corre desde un checkout del repo dev (estructura `<GIT_ROOT>/unmassk-toolkit/lib/
boot_health.py` → 3 `dirname()` = `<GIT_ROOT>`, que sí contiene subcarpetas `<plugin>/skills/`).

Pero en producción (cualquier proyecto que instaló el plugin, incluyendo antonio-alsara y omawaMapas),
el módulo corre desde el **cache**: `~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-toolkit/
<version>/lib/boot_health.py`. Ahí 3 `dirname()` aterrizan en
`~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-toolkit` — es decir, la carpeta de cache DE ESE
MISMO PLUGIN (que contiene subcarpetas de VERSIÓN, no de plugin). Este directorio:

1. **Siempre existe** en producción (es la propia ubicación del plugin corriendo), así que el guard
   `if not os.path.isdir(REPO_BASE_DIR): return None` (línea 121) nunca se activa para el caso
   "no hay código fuente" — el bug está exactamente en que la ruta mal calculada SIEMPRE resuelve a
   *algo* real.
2. `_build_repo_skill_index()` (líneas 84-107) hace `os.listdir(REPO_BASE_DIR)` esperando nombres de
   plugin — pero recibe nombres de VERSIÓN (`1.19.0`, `1.19.1`, `1.19.2`, ...). Para cada "entry" (una
   versión), construye `skills_dir = REPO_BASE_DIR/entry/skills` — que SÍ existe (es la carpeta skills
   de esa versión cacheada). El índice resultante mapea `skill_name -> SKILL.md de CUALQUIER versión
   cacheada de unmassk-toolkit que `os.listdir()` devuelva (orden no determinista, sin sort por semver).
3. `check_skill_drift()` compara el SKILL.md de la última versión cacheada de cada plugin (línea 150)
   contra esa "repo_index" mal construida (línea 153-158) — en la práctica, compara la versión más
   reciente de `unmassk-toolkit` contra OTRA versión cacheada de sí mismo (no contra el repo real). Si
   hay ≥2 versiones de `unmassk-toolkit` en cache (normal tras cualquier `/plugin update` que no borra
   la versión anterior) y el contenido de algún SKILL.md cambió entre versiones, el MD5 difiere y
   **dispara "drift" en un proyecto que nunca tuvo el código fuente del toolkit checkout-eado.**

**Veredicto: bug de scope, no comportamiento diseñado.** El check fue pensado para "¿el cache está
sincronizado con MI checkout del repo dev?" (útil solo en `claude-toolkit` mismo, donde SÍ hay curro
activo editando skills sin republicar) — pero la aritmética de rutas lo hace "accionable" en cualquier
repo con ≥2 versiones cacheadas, que es la mayoría de proyectos usuarios.

**Origen:** función existe sin cambios desde `037e0cb` (2026-03-17, v1.0.0 — el merge de 4 plugins).
~4 meses corriendo con este bug.

**Tests: CERO.** `grep -rn "check_skill_drift\|boot_health" tests/` no devuelve nada.
`grep -rn "CACHE_BASE_DIR\|REPO_BASE_DIR\|_build_repo_skill_index" tests/` tampoco. `tests/test_drift.py`
existe pero es sobre OTRA cosa completamente (drift de historial de commits / snapshot budget de
precompact, no drift de skills — nombre engañoso, no confundir). Esto explica por qué el bug de rutas
nunca fue detectado por la suite.

## 4. Migraciones que corren en cada boot — inventario completo

Grep `def.*migrat\|_migrate_` en `hooks/` + `lib/` + `bin/` → **3 migraciones activas en el hook de
boot** (todas en `lib/boot_migrations.py`, importadas y ejecutadas por
`hooks/session-start-boot.py:run_preboot_migrations():236-284`, sin ningún try/except que las salte —
solo su propio contenido decide si hacen algo):

| # | Función | Qué hace | Scope | Desde | Test |
|---|---|---|---|---|---|
| 0 | limpieza flag `.session-booted` (inline, no es función `_migrate_*`) | `os.remove()` del flag al iniciar sesión nueva | por proyecto | — (no es migración histórica, es reset de sesión) | sin test dedicado encontrado |
| 1 | `_migrate_runtime_to_unmassk()` (`boot_migrations.py:24-92`) | mueve `.glossary-cache.json`, `git-memory-manifest.json`, `.session-booted`, `git-memory-scopes.json` de `.claude/` raíz a `.claude/.unmassk/` (esquema v3.7→v3.8, era PRE-1.0) | por proyecto | confirmado presente ya en `037e0cb` (2026-03-17, v1.0.0) — anterior al merge de 4 plugins | `tests/test_security_regression.py` (símlink guard) |
| 2 | `_migrate_untrack_generated_jsons()` (`boot_migrations.py:95-113`) | `git rm --cached` de JSONs generados que instalaciones viejas commitearon por error + `ensure_gitignore()` | por proyecto | confirmado presente ya en `037e0cb` (v1.0.0) | `tests/test_migrate_statusline.py` |
| 3 | `_migrate_stale_context_writer_statusline()` (`boot_migrations.py:116-192`) | repara/quita `statusLine.command` que apuntaba a `context-writer.py` (borrado) en `~/.claude/settings.json` GLOBAL (no por proyecto) | global (no depende de `project_root`, corre siempre) | introducida en `df0a4a1` (2026-06-05, commit "fix: auto-curar statusline obsoleto al actualizar") — ~5 semanas antes de hoy | `tests/test_migrate_statusline.py` (`test_restores_from_backup`, `test_removes_key_without_backup`, `test_unrelated_statusline_untouched`, `test_idempotent_no_settings_file`, `test_backup_deleted_after_restore`) |

**Duplicación cruzada confirmada:** `bin/git-memory-upgrade.py:206` define **otra** función
`_migrate_runtime_to_unmassk()` — implementación separada (no importa de `boot_migrations.py`), invocada
desde el flujo de `git memory upgrade` (línea 302). Dos fuentes de verdad para la misma migración v3.7→
v3.8, mismo patrón de riesgo que el ya documentado en scan-history.md para BANNED_TOOLS/
RESERVED_AGENT_NAMES en el proyecto chatroom.

**Criterio de "ya cumplida" hoy:** ninguna de las 3 tiene marcador de "ya se ejecutó" — cada una decide
por sí sola en cada boot si hay algo que hacer, mirando el estado actual del filesystem (archivo viejo
presente / statusLine con string "context-writer" / JSONs trackeados). Esto es barato en el caso normal
(early-return si no hay nada que migrar) pero significa que jubilar una migración requiere confirmar que
NINGÚN usuario activo puede seguir teniendo el estado viejo — señal más fuerte para #1 y #2 (pre-1.0,
~4 meses) que para #3 (5 semanas, todavía relativamente reciente respecto a cuántos boots han pasado
desde entonces para instalaciones que no actualizan seguido).

## 5. Self-healing ante rebase/amnesia — SOLO existe como prosa, no como código

**Ubicación:** `skills/unmassk-gitmemory/SKILL.md:491-505`, sección `## Recovery` /
`### Self-Healing (rebase/reset detection)`:

> "On boot, compare known commit hashes with current tree. If amnesia detected (memory commits
> missing): 'Seems like a rebase happened. I've rebuilt memory from current state, but prior design
> context may be missing.' [...] Rebuild conservatively, be honest about gaps."

**Confirmado por grep exhaustivo (`rebase`, `amnesia`, `self-heal`, `reconstruct`, `heal`, `orphan`,
`_gap`) en `hooks/` + `lib/` + `bin/`:** no existe NINGÚN código que (a) persista una lista de "known
commit hashes" para comparar contra el árbol actual, (b) detecte explícitamente que hashes conocidos
desaparecieron, ni (c) "reconstruya" nada. Lo único tangencialmente relacionado es
`check_upstream_shares_history()` (`lib/boot_git_checks.py:605`), que compara la historia del upstream
remoto contra la local para detectar remotos NO relacionados (protección de identidad de repo, issue
#49) — es una comprobación distinta, no detección de rebase local.

**Lo que realmente pasa en cada boot:** `boot_memory.py`/`git_helpers.py`
(`commits_since_last_consolidation()`, línea 554) extraen memoria haciendo `git log --grep=...` en vivo
contra el árbol ACTUAL, sin comparar contra un índice persistido de commits ya vistos. Esto da
"auto-sanación" pasiva de facto (si un commit desaparece por rebase, simplemente deja de aparecer en el
próximo `git log`, sin crash) pero **sin ningún aviso explícito** de que algo desapareció — exactamente
el hueco que el punto 5 del issue pide resolver ("detectar + avisar honesto").

**Conclusión: no hay reconstrucción automática que quitar (no existe código de reconstrucción).** Lo que
existe es texto en SKILL.md que le pide al agente IA que "reconstruya conservadoramente" — instrucción a
razonamiento, no mecanismo determinista (mismo patrón de "gate no automatizado" que Bilbo documentó en
spec-kit, sesión 2026-07-04, scan-history.md). El trabajo real de este punto es: (a) decidir si construir
detección real (comparar SHAs conocidos, hoy no existen en ningún archivo persistido) o (b) simplemente
reescribir la prosa de SKILL.md para dejar de prometer "rebuilt memory" cuando ningún código lo hace.

**Tests: CERO** (`grep -rln "Self-Healing\|rebuilt memory\|amnesia" tests/` vacío).

## 6. Texto de `[memory-check]` en UserPromptSubmit

**Ubicación exacta:** `hooks/user-prompt-memory-check.py:304-314`, última línea que se agrega SIEMPRE a
`lines` antes de `print("\n".join(lines))` (línea 316) — se emite en TODOS los casos (booted o no,
con o sin recall injection).

**Texto literal (líneas 305-313):**
```
"[memory-check] Before saving: is this memory-worthy? Save ONLY if it clears ALL of: "
"(1) durable — still true next session, not a one-off; "
"(2) non-derivable — not already in the code or git-log; "
"(3) not already captured. "
"FIRST check existing memory: if a memo/remember already covers this, do NOT add another — "
"if it's a correction, RETIRE the old one with a Resolved-Memo/Resolved-Remember tombstone "
"instead of stacking a new entry. "
"Systemic/process rules belong in the loaded skill, NOT in memory. "
"If in doubt, or it's just thinking out loud → do nothing. Silence beats noise."
```

**Longitud medida:** 577 caracteres, 95 palabras, ≈144 tokens (estimación chars/4).

**Redundancia confirmada con `CALIBRATION.md`** (300 líneas / 3399 palabras / 20274 bytes, cargada en
boot paso 4 según `CLAUDE.md` del proyecto y el propio texto de `session-start-boot.py`/
`user-prompt-memory-check.py`):

| Fragmento de `[memory-check]` | Ya cubierto en CALIBRATION.md |
|---|---|
| "durable — still true next session, not a one-off" | línea 23: "*What* qualifies is still governed by 'write little, read often'... only durable, non-derivable, correctly-scoped signals" |
| "FIRST check existing memory... do NOT add another" | línea 56: "Before saving: deduplicate. Check if a similar memo/remember already exists. If it does, update it instead of creating a new one." |
| "Systemic/process rules belong in the loaded skill, NOT in memory" | línea 195, casi palabra por palabra: "It's a systemic process rule the loaded skill already states... These are NOT memory — they belong in the loaded skill" |
| "if it's a correction, RETIRE the old one with a Resolved-Memo/Resolved-Remember tombstone" | no está tan explícito en CALIBRATION.md pero el concepto de tombstone se cubre en otras partes del SKILL.md (`Resolved-Memo`/`Resolved-Remember`, mencionado en SKILL.md:104 dentro de la sección de hooks automáticos) |

**Casi todo el contenido sustantivo del recordatorio ya está, de forma más completa, en CALIBRATION.md**
— coherente con el matiz explícito de Bex: "acortar (aligerar, NO quitar)". El texto puede reducirse a
un nudge corto que apunte a CALIBRATION.md como fuente de la regla completa, sin repetir los 3 criterios
íntegros cada vez.

**Riesgo de cambiarlo — tests:** ningún test en el repo assertea el CUERPO completo del texto, solo el
prefijo literal `"[memory-check]"` como substring (`tests/test_user_prompt_recall.py` — 10+ asserts,
`tests/test_hardening_recall.py` — 6 asserts, `tests/test_encoding_contract.py:130`,
`tests/test_control_byte_injection.py:2367`, `tests/test_user_prompt_skill_router.py:33`). Achicar el
texto es seguro en términos de estos tests SIEMPRE que se conserve el prefijo `"[memory-check]"` literal.

**Único riesgo real:** `tests/test_encoding_contract.py:109-133`
(`TestUserPromptMemoryCheckCp1252::test_valid_stdin_json_exits_zero_with_useful_output`) documenta en su
docstring que el bug histórico que motivó el test era el carácter `→` (U+2192) dentro de ESTA MISMA
línea, no codificable en cp1252. Si el nuevo texto acortado elimina todo carácter no-ASCII, ese test
seguiría pasando (solo assertea `"[memory-check]" in out` y `rc==0`) pero dejaría de ejercitar realmente
el escenario cp1252 vía esta línea específica — sigue existiendo indirectamente porque
`"[memoria relevante...]"` (línea 291, cuando hay recall injection) también tiene caracteres no-ASCII,
pero ese bloque solo aparece condicionalmente. Vale la pena que Dante lo tenga presente al tocar el texto.

## Resumen de dependencias entre puntos

- **1 ↔ 2**: ambos escriben CLAUDE.md vía la misma `upsert_managed_blocks()`; ambos podrían compartir
  el mismo gate de manifest.version si se diseña un único punto de verdad "¿la versión instalada ya es
  la actual?" en vez de dos checks independientes.
- **1 ↔ 4**: `session-start-crew.py` y `run_preboot_migrations()` corren en el mismo SessionStart pero
  en hooks distintos (`session-start-crew.py` vs `session-start-boot.py`) — cualquier gate por versión
  en el punto 1 no afecta directamente al punto 4 (las migraciones no dependen de manifest.version hoy).
- **3 ↔ 1**: `check_skill_drift()` corre dentro de `render_status_section()`, llamada desde
  `session-start-boot.py` (NO desde `session-start-crew.py` del punto 1) — son hooks SessionStart
  distintos, no comparten código, pero ambos podrían beneficiarse de una noción común de "¿estoy
  corriendo desde el repo dev o desde cache?" si se decide condicionar el drift check a esa distinción.
- **5**: no tiene dependencias de código con los otros puntos — es puro trabajo de SKILL.md.
- **6**: no tiene dependencias de código — es puro texto en `user-prompt-memory-check.py`, en la misma
  función `main()` que gatea el punto 2 (`needs_upgrade()`), pero en una rama de código independiente
  (se imprime siempre, al final, sin relación con el resultado del check de upgrade).

## No examinado (fuera del subgrafo relevante a los 6 puntos)

De los ~99 archivos del scope amplio (`hooks/`=13, `lib/`=24, `bin/`=10, `tests/`=48,
`skills/unmassk-gitmemory/`=4): se leyeron completos 8 (session-start-boot.py, user-prompt-memory-check.py,
managed_blocks.py, session-start-crew.py, boot_health.py, boot_migrations.py, pre-merge-gate.py,
version.py) y se inspeccionaron con grep dirigido ~20 más (boot_render.py, boot_git_checks.py,
git_helpers.py, install_apply.py, git-memory-install.py, git-memory-upgrade.py, git-memory-repair.py,
git-memory-doctor.py, SKILL.md, CALIBRATION.md, y los tests listados arriba). Los 9 hooks restantes
(`post-validate-commit-trailers.py`, `pre-memory-dedup-gate.py`, `pre-task-recall.py`,
`pre-validate-commit-trailers.py`, `precompact-snapshot.py`, `stop-close-session.py`,
`stop-dod-check.py`, `stop-dod-gate.py`, `validate-memory-path.py`) y la mayoría de `bootstrap_*.py`,
`colors.py`, `constants.py`, `date_parsing.py`, `encoding_guard.py`, `parsing.py`, `recall.py`,
`skill_router.py` no se leyeron — ninguno aparece en los greps de los 6 términos clave
(`managed_blocks`, `needs_upgrade`, `drift`, `migrat`, `rebase`/`amnesia`, `memory-check`) y no tienen
relación de import directa con las funciones mapeadas arriba. Confirmado por grep global de cada término
sobre `hooks/`+`lib/`+`bin/` antes de descartarlos.
