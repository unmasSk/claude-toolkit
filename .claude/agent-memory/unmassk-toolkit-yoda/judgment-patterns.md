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
