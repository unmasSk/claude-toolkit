---
name: memory-injection-2026-08-09
description: Estado real (2026-08-09) de la inyección de memoria en unmassk-toolkit — hooks vivos, el motor de recall muerto, boot.py no inyecta.
metadata:
  type: project
---

Mapa fresco tras el rediseño `memoria-v2` (docs ahora en `docs/deprecated/memoria-v2/`,
movidos 2026-08-05). Sustituye para efectos prácticos a [[boot-simplification-63-map]], que
describe el árbol de hooks anterior a este rediseño.

**Hooks vivos hoy (`unmassk-toolkit/hooks/hooks.json`):** SessionStart = `boot_launcher.py` +
`session-start-crew.py`; PreToolUse = `customs.py` (Bash, aduana de commits), `pre-merge-gate.py`
(Bash), `validate-memory-path.py` (Write|Edit); UserPromptSubmit = `user-prompt-memory-check.py`;
Stop = `stop-dod-gate.py`. Ocho ficheros en `hooks/`, ni uno más — confirmado por `ls`.

**El informe de arranque NO se inyecta, por decisión explícita del propietario (B4).**
`bin/memory/boot.py:main()` escribe el informe completo en
`.claude/.unmassk/boot-latest.txt` (`gitcmd.atomic_write`) y por stdout solo imprime la orden
de cargar las dos skills + la ruta del fichero + "Léelo entero... No está resumido". Razón
dada en el propio docstring: un hook tiene tope de tamaño de contexto, y un informe con veinte
muros se recorta por el final — justo los avisos de salud.

**El motor de recall (`recall_relevant()`, ~79 líneas, v1) está confirmado MUERTO, no solo
desenganchado:** no existe `lib/recall.py` ni `bin/git-memory-recall.py` en el árbol actual
(`find` sin resultados). `lib/memory/similar.py:27-34` lo dice explícito: "Que del v1 NO se
trae [medido — TESTIGO Sec.1]: `recall_relevant`... escrita, probada con ocho tests en verde,
y CERO consumidores en todo el repo". Todo lo que queda de "recall" en el código vivo son
menciones en comentarios/docstrings de otras piezas (`lib/parsing.py`, `lib/git_helpers.py`,
`lib/incidents.py`) que hablan de hooks YA RETIRADOS (`hooks/pre-task-recall.py`,
`hooks/session-start-boot.py`, `hooks/precompact-snapshot.py`) como llamadores históricos —
ninguno existe hoy en `hooks/`.

**No hay ningún hook `PreToolUse` sobre `Task`/`Agent` en el repo.** `hooks.json` (toolkit y
seo) solo tienen matchers `Bash` y `Write|Edit`. Grep de `modifiedInput`/`hookSpecificOutput`
en `hooks/`+`lib/`+`bin/` → cero resultados. Ningún subagente recibe memoria reescrita en su
prompt por un hook — coherente con la regla del propio CLAUDE.md ("nada llega solo a un
agente").

**`user-prompt-memory-check.py` ya NO imprime el texto largo de `[memory-check]`** (los 3
criterios "durable/non-derivable/not already captured", ~577 caracteres) documentado en el
mapa viejo — eso se retiró (issue #69, decisión `1e94975`: "recall push→pull"). Hoy
`"[memory-check]"` solo aparece como línea de relleno
`"[memory-check] No skill match this turn — nothing to report."` cuando no hay nada más que
decir ese turno (fallback para que el hook nunca imprima vacío). El resto del output de este
hook es: banner de instalación si falta `manifest.json`, bloque de "carga las skills ahora"
solo en el primer mensaje de la sesión (gateado por `.claude/.unmassk/.session-booted`), y el
router de skills por frase-disparadora (`lib/skill_router.py`).

**Residuo sin limpiar (no ficheros muertos, pero prosa/callers desactualizados):**
`lib/parsing.py:sanitize_trailer_value()` sigue documentando como llamadores "recall,
session-start-boot, precompact-snapshot" en su docstring — los tres retirados. Llamadores
reales hoy: `lib/incidents.py`, `bin/git-memory-log.py`, `bin/git-memory-doctor.py` (grep
confirmado). Es hallazgo para Alexandria (doc stale), no código muerto — la función sigue
usándose, solo el docstring miente sobre quién la usa.

Ver [[boot-simplification-63-map]] para el detalle histórico de issue #63 (managed blocks,
migraciones, self-healing en prosa) — esas partes de ese mapa siguen siendo válidas en lo que
no toca hooks de memoria per se (p.ej. las 3 migraciones de `boot_migrations.py` no se
reverificaron en esta pasada).
