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
