# Adelgazamiento — recorte de tests anti-atacante (#72)

**Issue:** #72
**Branch:** — (trunk repo, main es la rama de trabajo)
**Triage:** BIG
**Build mode:** linear (borrado; verificación = suite verde + cero tests atacante)
**Created:** 2026-07-18

## Goal
Retirar los tests de defensa anti-atacante (~9.8k líneas) sin tocar código vivo, dejando la suite verde y solo tests de integridad/plataforma/round-trip.

## Decisions
- 7e7f2c2: recortar SOLO tests anti-atacante; código vivo intacto; objetivo numérico 8-10k abandonado (inalcanzable sin destripar integridad).
- Modelo de amenaza firmado (CLAUDE.md): "el sistema contra sí mismo", no un atacante externo.

## Baseline
1373 passed, 2 skipped (exit 0), ~5min. ~14.5k código / ~39k test.

## Tasks

### Task 1 (Dante): borrar 4 ficheros atacante puros
**Files (delete):**
- unmassk-toolkit/tests/test_control_byte_injection.py (3661)
- unmassk-toolkit/tests/test_security_regression.py (3902)
- unmassk-toolkit/tests/test_hardlink_reject_guard.py (440)
- unmassk-toolkit/tests/test_manifest_hardlink_reject.py (523)
**Verify:** `pytest unmassk-toolkit/tests -q` → verde (menos esos ~8.5k), sin errores de colección/import.

### Task 2 (Dante, continuación): excisar clases atacante de 6 mixtos
**Files (edit — conservar la parte integridad, quitar solo la atacante):**
- test_boot_output.py → quitar las 6 clases SEC (L1155-1963: TestSymlinkWriteProtection, TestControlByteRecordInjection, TestScopesInjectionSanitization, …). Conservar TestBootSections/TestBootLogFileFullContent/TestWriteBootLogSurrogateEscape.
- test_crossplatform_symlink_guard.py → quitar TestWindowsToctouIdentityMismatch (+ TestPosixGuardUnchanged si es solo parte del race). Conservar TestExceptionInvariantAcrossPlatforms/TestTwinParity/TestEncodingRoundTrip (fix crash Windows).
- test_crossplatform_symlink_guard_hardening.py → quitar TestToctouMismatchAllModes. Conservar el resto (data-loss/fd-leak/parity).
- test_issue63_manifest_read_hardening.py → quitar TestSecT1_002* (.claude dir symlink bypass). CONSERVAR TestSecT1_001* (RecursionError fail-safe = integridad).
- test_hardening_recall.py → quitar TestFramingAntiInjection + TestSanitizeBreakoutBlocked. Conservar fail-open/format robustness.
- test_stop_dod_gate.py → quitar TestMetacharacterSafety. Conservar TestCommandPasses/TestInfraErrorsFailOpen/TestAlwaysValidJson.
**Cuidado:** conservar imports/fixtures que usen las clases supervivientes. Si una clase es dudosa (integridad vs atacante), PARAR y reportar, no borrar.
**Verify:** `pytest unmassk-toolkit/tests -q` → verde; cero tests con framing de atacante externo.

### Task 3 (Ultron): limpiar referencia fantasma
**Files (edit):**
- lib/install_inspect.py:26 — quitar 'git-memory-dashboard.py' de OLD_BIN_FILES
- bin/git-memory-uninstall.py:48 — idem
**Verify:** `pytest unmassk-toolkit/tests -q` → verde.

## Wave Map
- Secuencial: Task 1 → Task 2 → Task 3 (todas tocan tests salvo T3; T2 depende de que T1 no rompa colección).

## Verify (Step 5)
- Cerberus: confirmar que SOLO se quitó atacante, integridad intacta, sin imports/fixtures colgando.
- Argus/Moriarty: N/A (borrado de tests, sin código/comportamiento nuevo ni superficie de ataque añadida). Se documenta el porqué.
- Yoda: veredicto ligero de cierre.
- Gate mecánico duro: suite completa verde (el suelo de 1373 menos los tests retirados a propósito).
