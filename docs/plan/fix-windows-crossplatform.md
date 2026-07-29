# Fix Windows / Cross-Platform Compatibility — Implementation Plan

**Issue:** (trunk repo, tracked here)
**Branch:** main (trunk — working branch)
**Triage:** Big (toca protección de symlinks + ~15 sitios de encoding; seam de fichero write→reread)
**Build mode:** test-first
**Seam:** SÍ — fichero escrito y releído (`boot-log-latest.txt`, `glossary-cache.json`) + round-trip de encoding UTF-8. Moriarty + Yoda obligatorios en Verify.
**Created:** 2026-07-06

## Goal
Hacer el toolkit ejecutable y seguro en Windows/macOS/Linux por igual, sin degradar la garantía anti-symlink de SEC-CRIT-001/SEC-MED-NEW-02 ni añadir dependencias fuera de la librería estándar.

## Decisions (git-memory)
- `013b064` decision(plugin/portability): cross-platform (Windows/macOS/Linux) es requisito duro.
- `75fdb2f` decision(plugin/security): guard anti-symlink opción C híbrida; residual TOCTOU de `O_CREAT` en Windows aceptado y documentado; `0o600` documentado como POSIX-only; sin pywin32/ctypes.

## Diagnóstico base (House)
- **F1 (T1, crash duro):** `os.O_NOFOLLOW` no existe en Windows → `AttributeError` (que NO es `OSError`, así que escapa a los `except OSError`). En `lib/git_helpers.py:127,130` y su gemela `lib/_symlink_safe_open.py:32,35`.
- **F2/F3 (T2, latente):** `subprocess(text=True)` y `open()`/`json` sin `encoding=` → en Windows por defecto (cp1252) rompen o dan mojibake; hoy enmascarado por `PYTHONUTF8=1`.
- **F4 (garantía falsa):** docstring afirma que `0o600` niega acceso group/other — falso en Windows.
- **F5 (postura):** no basta con borrar `O_NOFOLLOW`; hay que dar equivalente Windows.

## Tasks

### Task 1: Contrato de test (Dante) — test-first, va PRIMERO
**Files:** `unmassk-toolkit/tests/test_security_regression.py` (y/o nuevo `test_crossplatform.py`)
**Steps:**
- [ ] Guard POSIX sin cambios: symlink preexistente → `OSError` (ELOOP); fichero normal → abre bien.
- [ ] Guard Windows: `os.path.islink()==True` (mockeado, sin crear symlink real — este entorno no tiene privilegio) → lanza `OSError` sin abrir.
- [ ] Guard Windows: identidad pre/post distinta (`lstat` vs `fstat` con `st_ino`/`st_dev` inyectados) → `OSError`, cierra el fd, no lo devuelve.
- [ ] Ambas plataformas: excepción propagada es `OSError` (o subclase), NUNCA `AttributeError` ni `return None`.
- [ ] Test parametrizado sobre las DOS gemelas (`git_helpers` y `_symlink_safe_open`) — mismo escenario, mismo resultado.
- [ ] Round-trip encoding: escribir contenido con acentos + emoji (🔧📝👑) vía el writer guardado y releerlo → idéntico.
- [ ] Desenmascarar cp1252: al menos un test que corra con `PYTHONUTF8=0` para probar que el encoding explícito no depende de la variable de entorno.
- [ ] Verify: `pytest unmassk-toolkit/tests -k "crossplatform or symlink or encoding"` → RED (aún sin implementar).

### Task 2: Guard cross-platform + `run_git` encoding (Ultron) — dueño de `git_helpers.py` y su gemela
**Depends on:** Task 1 (contrato RED)
**Files:** `unmassk-toolkit/lib/git_helpers.py`, `unmassk-toolkit/lib/_symlink_safe_open.py`
**Steps:**
- [ ] Reescribir `open_no_follow_symlink` con rama `sys.platform == "win32"`:
  - POSIX: `os.O_RDONLY|os.O_NOFOLLOW` / `os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW` como hoy.
  - Windows: `os.path.islink()` pre-open → fallar cerrado; `os.lstat` pre / `os.fstat(fd)` post, comparar `(st_dev, st_ino)`, si difieren cerrar fd y `raise OSError`; abrir con `open()` normal.
- [ ] Aplicar el MISMO cambio a `open_no_follow_symlink_fallback` en la gemela (mismo commit, comportamiento idéntico).
- [ ] Corregir el docstring (F4): `0o600` es efectivo solo en POSIX; en Windows el fichero hereda la ACL del directorio contenedor. No prometer garantía que no se cumple.
- [ ] Documentar el residual (F5) en el docstring: el caso `O_CREAT` en Windows no cierra el TOCTOU atómicamente sin API nativa; aceptado deliberadamente.
- [ ] `run_git` (`~:188`): añadir `encoding="utf-8"` al `subprocess`; revisar el `except (SubprocessError, OSError, ValueError)` que traga `UnicodeDecodeError` como fallo genérico de git — que un error de decode no se disfrace de "git falló".
- [ ] `ensure_gitignore` y demás llamadas locales siguen funcionando.
- [ ] Verify: los tests de guard de Task 1 pasan a VERDE en este entorno.

### Task 3: Barrido de encoding en el resto (Ultron) — NO toca `git_helpers.py`
**Depends on:** Task 1
**Files (sin solape con Task 2):** `lib/version.py:21`, `lib/install_apply.py:191,201,277`, `lib/install_inspect.py:111,141,154`, `lib/bootstrap_deps.py:35,205,301`, `lib/boot_health.py:183,249,262`, `lib/boot_git_checks.py:212`, `hooks/session-start-crew.py:22`, `hooks/validate-memory-path.py:19`, `hooks/stop-dod-gate.py:105`, `hooks/user-prompt-memory-check.py:204`
**Steps:**
- [ ] Añadir `encoding="utf-8"` a cada `open()`/`json.load`/`json.dump` y `encoding="utf-8"` a cada `subprocess(text=True)`.
- [ ] Patrón de referencia ya correcto: `lib/boot_migrations.py:143,158,171` y el cache de glosario — imitarlos.
- [ ] F6 (bajo demanda, bajo): MOOT — `scripts/skill-search.py` fue retirado y archivado en el tag `bm25-skill-gate-1.19.9`; ya no existe en el árbol, nada que corregir.
- [ ] Verify: los round-trip de encoding de Task 1 pasan a VERDE, incluido el que corre con `PYTHONUTF8=0`.

## Wave Map
- **Wave 1:** Task 1 (Dante escribe el contrato; queda RED).
- **Wave 2:** Task 2 + Task 3 en paralelo (ficheros disjuntos — Task 2 es dueña de `git_helpers.py`/gemela; Task 3 el resto).
- **Wave 3:** suite completa verde → Verify (Task 5).

## Verify (Step 5)
- Cerberus: calidad + goal-backward + confirma que ningún valor esperado del round-trip es un literal a mano.
- Argus: audita que la garantía anti-symlink sobrevive en ambas plataformas y que el residual está documentado, no silenciado.
- Moriarty: Round-Trip Sabotage + intento de bypass del guard en Windows.
- Yoda: veredicto de producción + Round-Trip Evidence Rule sobre el seam.

## Non-goals (scope creep — issues aparte si se quieren)
- ACL real de Windows para `0o600` (F4 se documenta, no se implementa).
- Cerrar el residual `O_CREAT` con `pywin32`/`ctypes`.
- F7 (junctions NTFS en install/uninstall), F9 (templates scaffold Unix) — bajo demanda, fuera del runtime crítico.
- Lint/CI con `PYTHONUTF8=0` en Windows para desenmascarar la clase permanentemente (recomendación de House — candidata a issue futuro).

**Status: COMPLETED** — issue cerrado; marcado en la limpieza del 2026-07-29 (censo de deuda). El plan quedó sin marcar al cerrar el trabajo: el paso 7 de Flow depende de que el orquestador lo recuerde, y no lo hizo.
