# Fix — escritura atómica de CLAUDE.md (bloques managed)

**Issue:** — (del veredicto del council; el "#1" original resultó obsoleto, esto es el fallo real)
**Branch:** — (trunk, main es la rama de trabajo)
**Triage:** BIG (T1, 4 escritores, helper compartido)
**Build mode:** test-first
**Seam:** SÍ — productor escribe CLAUDE.md, consumidor (boot) lo lee. §34 + atomicidad. Moriarty + Yoda.
**Created:** 2026-07-19

## Goal
Que ninguna escritura de los bloques managed de CLAUDE.md pueda dejar el fichero vacío o parcial ante un crash/kill/disco-lleno a mitad: escritura atómica (todo-o-nada).

## Diagnóstico (House, ya hecho)
- Bug real: todos los escritores usan `open(claude_md, "w")` = truncate-in-place, sin temp, sin `os.replace`, sin lock. En cuanto `open("w")` retorna, el fichero está a 0 bytes. Crash en esa ventana → CLAUDE.md vacío/parcial. T1 confirmado.
- El patrón atómico correcto YA existe en el repo: `lib/boot_fetch_stamp.py:256-303` (`tempfile.mkstemp` en el mismo dir + `os.replace`).
- (#3 migración duplicada: YA resuelto, una sola definición. Fuera de scope. Solo residuo: un `.pyc` rancio, limpieza opcional trivial.)

## Los 4 escritores a cubrir
- `hooks/session-start-crew.py:78,84-85`
- `lib/install_apply.py:242-243` (`_update_claude_md`, compartido por `git-memory-install.py`, `apply_upgrade()` de `git-memory-upgrade.py`, y `git-memory-repair.py`)
- `bin/git-memory-uninstall.py` (mismo helper, quita bloques)

## Tasks

### Task 1 (Dante — CONTRATO test-first, primero)
**Contrato a fijar (rojo hoy):**
- **Atomicidad:** si la escritura se interrumpe ANTES de completarse (simular fallo en la escritura del temp o antes del `os.replace`), CLAUDE.md conserva su contenido ORIGINAL — nunca vacío ni parcial.
- **Éxito:** una escritura normal deja el contenido nuevo correcto y completo.
- **Temp en el mismo directorio** que CLAUDE.md (si no, `os.replace` cruza dispositivos y no es atómico) — afirmarlo.
- **Sin regresión de seguridad de path:** preservar la semántica actual de rechazo de symlink / no escribir fuera del repo que ya tienen los escritores (no seguir un symlink de CLAUDE.md ni de su directorio padre). Verificar que el fix no la pierde.
- Cubrir el helper centralizado (ver Task 2) y al menos un escritor real end-to-end (round-trip §34: escribir bloques → leerlos de vuelta intactos).
**Verify:** los tests nuevos FALLAN contra el código actual (no atómico).

### Task 2 (Ultron — implementa hasta GREEN)
- Centralizar la escritura atómica en UN helper (en `lib/git_helpers.py`, junto a `open_no_follow_symlink`, reutilizando el patrón de `boot_fetch_stamp.py`): escribir a temp en el mismo dir + `os.replace` sobre CLAUDE.md.
- Preservar la semántica de rechazo de symlink / path-safety actual (verificar el destino antes del replace si hace falta; `os.replace` no debe seguir/reemplazar en silencio un symlink que hoy se rechazaría — si el destino es symlink, comportarse como hoy).
- Enrutar los 4 escritores por ese helper. No cambiar el CONTENIDO que escriben, solo CÓMO lo escriben.
- Cross-platform: `os.replace` es atómico en POSIX y Windows; confirmar que el patrón de temp+replace funciona en ambos (Windows no permite replace sobre fichero abierto — asegurar que no hay handle abierto al hacer replace).
**Verify:** contrato de Dante verde + suite completa verde.

## Wave Map
- Task 1 (Dante contrato) → Task 2 (Ultron GREEN).

## Verify (Step 5) — con seam §34
- Cerberus (calidad, ¿los 4 escritores enrutados? ¿alguno se quedó fuera?) + Argus (¿el temp filtra contenido a un fichero con permisos laxos? ¿race del propio temp?).
- Dante: endurece; el round-trip lo posee Dante.
- Moriarty: sabotaje de round-trip — forzar fallos en varios puntos de la escritura y probar que CLAUDE.md nunca queda vacío/parcial.
- Yoda: veredicto + Round-Trip Evidence Rule.
- Gate duro: suite completa verde + cross-platform CI (Windows+Linux).
