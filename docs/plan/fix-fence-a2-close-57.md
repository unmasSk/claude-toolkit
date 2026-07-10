# Cierre #57 — A2 token-fence + costura de bytes + ReDoS + LOW-17

**Issue:** #59 (flecos destapados por la auditoría de #57, que está CERRADO)
**Branch:** main (repo trunk)
**Triage:** Big + costura productor→consumidor
**Build mode:** test-first
**Created:** 2026-07-10
**Decisiones:** `feed852` (A2 token-fence), `79fdf9a` (alcance del paquete)

## Goal
Cerrar la clase de forja/falsificación de la salida de memoria hacia el LLM: valla infalsificable (nonce) en los 2 sitios que hoy la enmarcan, transporte de bytes correcto en los 2 subprocess, tope anti-ReDoS y cierre de LOW-17 — con verify limpio y Yoda 110.

## Alcance (de `79fdf9a`)
DENTRO:
- **A2 nonce** en `hooks/user-prompt-memory-check.py:266-277` (única valla en producción) y en el delimitador hermano `=== SNAPSHOT ===` de `hooks/precompact-snapshot.py`.
- **Bytes-transport** en `lib/git_helpers.py:455-460` (`run_git`, `text=True` sin `newline`) y en el subprocess inline de `bin/git-memory-log.py:65-68` (mismo defecto, sitio independiente).
- **ReDoS** en `lib/bootstrap_commits.py:46` (`_GENERIC_TAG_RE`, `[^>]*` en bucle hasta 10x): tope de longitud.
- **LOW-17** en `lib/parsing.py:136-146` (`scan_trailers_memory` trunca en `\x1c/\x1d/\x1e` y descarta el `>` de cierre → marcador queda sin cerrar y el saneador no lo caza).

FUERA (candidato, NO en este paquete):
- Valla estructural nueva para `boot-log-latest.txt` / `lib/boot_render.py` (hoy no tiene ninguna; se apoya en saneo por campo). Rediseño separado.

## Cobertura de tests que YA existe (no duplicar)
`tests/test_control_byte_injection.py` (154 tests). Cubierto: forja/borrado por byte de control a nivel registro/campo, evasión de valla `\x1c/\x1d/\x1e/\x85/\x1f` (como bytes→espacio y como `\s`), bypass de strip de tags genéricos, unicidad del delimitador de precompact.
NO cubierto (lo que abre este paquete):
- (a) Traducción `\r`→`\n` en la capa de transporte real (subprocess), no en string in-memory.
- (b) ReDoS / tope de longitud en `_strip_generic_tags`.
- (c) LOW-17 (truncado antes del `>`).
- (d) Infalsificabilidad del nonce A2 (un trailer hostil no puede reproducir la valla).

## Tasks

### Task 1 — Dante: contrato RED completo (test-first)
**Files:** `tests/test_control_byte_injection.py` (+ posible `tests/test_run_git_transport.py`)
**Steps:**
- [ ] RED (a): payload con `\r` crudo en el body de un commit REAL, leído por `run_git` y por el subprocess de `git-memory-log.py` a través de subprocess real (no string Python); aserción: la línea no se forja/borra (round-trip de la costura, propiedad §34).
- [ ] RED (b): subject largo hostil (muchos `<letra` sin `>`) contra `_strip_generic_tags`; aserción de tope de longitud / tiempo acotado.
- [ ] RED (c): `</memory-data` con `\x1c` antes del `>`; aserción: la valla se neutraliza igualmente (no sobrevive sin cerrar).
- [ ] RED (d): trailer que intenta reproducir literal el marcador de valla; aserción: con nonce por invocación, el marcador inyectado NO coincide con la valla real → no rompe el marco.
- [ ] Verificar: los 4 en ROJO por la razón correcta.

### Task 2 — Ultron: implementación a VERDE
**Depends on:** Task 1
**Files:** `lib/git_helpers.py`, `bin/git-memory-log.py`, `hooks/user-prompt-memory-check.py`, `hooks/precompact-snapshot.py`, `lib/bootstrap_commits.py`, `lib/parsing.py`
**Steps:**
- [ ] Bytes: leer bytes en `run_git` (o `newline=""`/decodificación controlada) preservando `\r`; replicar en `git-memory-log.py`. Revisar los ~15 call-sites que consumen `run_git` para no romper decodificación.
- [ ] A2 nonce: generar nonce por invocación e insertarlo en la valla de `user-prompt-memory-check.py`; mismo patrón en el delimitador de `precompact-snapshot.py`.
- [ ] ReDoS: tope de longitud en la entrada de `_strip_generic_tags` / `_GENERIC_TAG_RE`.
- [ ] LOW-17: en `scan_trailers_memory`, no dejar marcador sin cerrar (sanear antes de truncar, o truncar sin partir el marcador).
- [ ] Verificar: contrato de Task 1 en VERDE + suite completa verde.

## Wave Map
- Wave 1: Task 1 (Dante, RED)
- Wave 2: Task 2 (Ultron, GREEN) — un solo agente, ficheros dispersos pero coordinados

## Verify (Step 5)
- Cerberus (goal-backward + sin literales hand-typed en el round-trip)
- Dante (hardening + cobertura ≥90% fn / ≥80% error paths)
- Argus (re-verifica SEC-CRIT-16, LOW-17, clase de valla)
- Moriarty (Round-Trip Sabotage contra el subprocess real antes de declarar AGUANTA)
- Yoda (Round-Trip Evidence Rule mecánica + veredicto 110)

## Close (Step 7)
Suite completa verde → Gitto squash de wips → push main (trunk) → cerrar #59 → context `#59 CLOSED` → candidato boot-log-fence apuntado.
