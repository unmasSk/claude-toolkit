# CLAUDE.md — claude-git-memory

<!-- BEGIN claude-git-memory (managed block — do not edit) -->
## Git Memory Active

Este proyecto usa claude-git-memory v2.
Git es la memoria. Cada commit es resumible entre sesiones y máquinas.

### Al iniciar sesión
Lee el skill `git-memory` y ejecuta AUTO-BOOT automáticamente.

### Comandos conversacionales
- "instala/repara/desinstala memoria" → skill `git-memory-lifecycle`
- "estado de memoria" / "doctor" → skill `git-memory-lifecycle` (doctor)
- "qué recuerdas" → boot con resumen extendido
- Releases, conflictos, undo → skill `git-memory-protocol`
- Rebase, reset, self-healing → skill `git-memory-recovery`
<!-- END claude-git-memory -->

## ⚠️ Sistema en Alpha — Verificación Activa

Este sistema (claude-git-memory v2) está en **fase alpha**. Como operador, debes:

1. **Reportar cualquier fallo** que encuentres al usar hooks, skills, CLI, o lifecycle scripts — no lo ignores silenciosamente
2. **Verificar antes de confiar**: si un comando (`git memory doctor`, `install`, `repair`, etc.) produce output inesperado, investígalo y repórtalo al usuario
3. **Ejecutar `git memory doctor`** al inicio de cada sesión para confirmar que el sistema está sano
4. **Si algo se rompe**: usa `git memory repair --auto` antes de intentar arreglos manuales
5. **No asumir que todo funciona** — valida los resultados de cada operación del sistema de memoria
6. **Documentar bugs encontrados**: si encuentras un bug reproducible, explícalo al usuario con pasos para reproducir

El sistema se considera estable cuando todos los tests pasen (`drift-test.py` + `lifecycle-test.py`) y doctor reporte todo verde en repos instalados.
