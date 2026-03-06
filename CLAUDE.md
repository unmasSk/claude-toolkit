# CLAUDE.md — claude-git-memory

<!-- BEGIN claude-git-memory (managed block — do not edit) -->
## Git Memory Active

Este proyecto usa claude-git-memory v2.
Git es la memoria. Cada commit es resumible entre sesiones y máquinas.

### Instrucciones para Claude (no para el usuario)
1. Al iniciar sesión: lee el skill `git-memory` y ejecuta AUTO-BOOT + doctor automáticamente
2. Ejecuta `python3 bin/git-memory-doctor.py --json` al arrancar. Si hay errores, repara con `python3 bin/git-memory-repair.py --auto`
3. Nunca le pidas al usuario que ejecute comandos del sistema de memoria — ejecútalos tú
4. Si el usuario dice "instala/repara/desinstala/doctor/estado" → lee skill `git-memory-lifecycle` y actúa
5. Si el usuario dice "qué recuerdas" → ejecuta boot extendido
6. Sistema en alpha: verifica todo, reporta fallos al usuario, no asumas que funciona
<!-- END claude-git-memory -->

## Sistema en Alpha — Claude verifica todo

Este sistema está en **fase alpha**. Tú (Claude) eres responsable de verificar que funciona:

- Al arrancar sesión: ejecuta `python3 bin/git-memory-doctor.py --json` silenciosamente. Si hay errores, díselo al usuario y ejecuta repair tú mismo.
- Si algo falla: ejecuta `python3 bin/git-memory-repair.py --auto` antes de intentar arreglos manuales.
- Nunca le pidas al usuario que ejecute comandos del sistema de memoria. Ejecútalos tú.
- Si encuentras un bug reproducible, explícalo al usuario con pasos para reproducir.
- No asumas que todo funciona — valida resultados de cada operación.
