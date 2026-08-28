# Attack Patterns — What Worked

## Cómo leer este fichero
Compactado 2026-08-25: contrastado contra el código real, no contra lo
recordado. Está en 3 bloques: técnicas transferibles (sin fichero vivo o
muerto que las ate), sistema actual (código que existe hoy — verificado
`find`/`grep` línea a línea contra el repo), y un bloque final retirado
(el sistema de memoria v1, borrado entero en el commit `615f5cc` "borrado
el sistema de memoria anterior y retirada su documentacion de obra",
2026-08-05 — confirmado también por el propio docstring superviviente de
`lib/boot_health.py`: "the v1 boot chain... was deleted — v2's
boot_launcher.py replaced it"). El detalle completo de esa era (rondas,
PoCs, file:line originales) sigue intacto en `round-history.md` y en
`docs/deprecated/` — no se repite aquí, solo la lección transferible.
Donde verifiqué en vivo que un hallazgo de esta lista YA ESTÁ CERRADO en
el código actual, añadí una nota `[CERRADO ...]` con la prueba — el texto
original del hallazgo se queda intacto encima, nunca se acorta.

## Técnicas transferibles (no atadas a un fichero concreto)

### Un fix de doc committeado en el repo se contrasta contra el cache que de verdad se carga (2026-08-28)
Un commit puede arreglar `SKILL.md` en el checkout de git y no tocar nunca la
copia que Claude Code carga en la sesion real: `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`.
`diff` el fichero del repo contra el de la version mas alta en cache (`sort -V`)
detecta esto en un segundo. Caso real: commit `1c89325` "retire R-018" arreglo
67 ficheros en 7 plugins y NINGUNO se publico -- las 7 plugins seguian sirviendo
el `${CLAUDE_PLUGIN_ROOT}` roto que el commit decia haber retirado. Aplica a
cualquier commit de doc/skill en este repo: el commit no es el producto, el
cache lo es.

### Un directorio de version "unknown"/huerfano ya existe en este cache real -- no hace falta fabricarlo (2026-08-28)
`~/.claude/plugins/cache/claude-plugins-official/{context7,plugin-dev}/unknown/`
con `.orphaned_at` es un estado real que el propio mecanismo de cache de Claude
Code produce en esta maquina, hoy. Cualquier patron `find ... | sort -V | tail -1`
que descubra la version de una skill es vulnerable a elegirlo: `sort -V` pone
`unknown` DESPUES de cualquier semver. Reproducido con datos sembrados en
`scratchpad/fake-cache2`: una copia huerfana con `.orphaned_at` gana a la
version real y el script equivocado corre sin ningun error visible -- silent
wrong-target, no crash. Antes de aceptar un patron `sort -V | tail -1` para
resolver la version de un plugin, sembrar un directorio `unknown` junto a la
version real y repetir la busqueda.

### Un subcomando de terceros que un arreglo ACABA de recomendar, se ejecuta con reloj (2026-08-28)
Cuando la ronda anterior cierra un hallazgo anadiendo "abre una sesion con
`X sub start`", ese comando entra en el doc sin haberse corrido nunca. Correrlo
con un tope de tiempo (lanzar en background, `kill -0` en bucle, matar a los
30 s) separa tres desenlaces que la lectura confunde: sale con error de
validacion por flags que faltan, devuelve, o **no devuelve nunca porque es un
grabador en streaming**. El tercero es el caro: en una llamada Bash de agente
cuelga la sesion, y al matarlo deja estado abortado que contamina los informes
de la cuenta para siempre. Caso real: `kraken session start` (unmassk-trading,
ronda 5). Corolario: si el mismo fichero ya dice en otro sitio "una skill no
puede mantener un socket abierto entre turnos", el arreglo se contradice solo.

### Un exit code medido a traves de una tuberia es un exit code inventado (2026-08-28)
`cmd | head` devuelve el estado de `head`, no el de `cmd`. Asi entro un "Measured:
it exits 0" FALSO en un doc — lo medi yo en una ronda anterior y el arreglo lo
escribio como hecho, sustituyendo el dato correcto que ya estaba. Medir siempre
`cmd >/dev/null 2>&1; echo $?` sin tuberia, y probar las variantes (con y sin
`--yes`, con y sin nombre) antes de afirmar un codigo de salida. Caso real:
`kraken workspace promote` sale 1 en las cuatro variantes; solo la tuberia da 0.

### El estado del shell NO sobrevive entre llamadas de la herramienta Bash (2026-08-28)
Verificado en vivo: `export X=valor` en una llamada, `echo "[$X]"` en la
siguiente devuelve `[]`. Cwd sí persiste; variables de entorno, funciones y
`source` NO. Ataque estándar contra cualquier skill o doc que diga "set it once
per session": extraer todas las variables que un bloque define y comprobar si
otro bloque las lee en una llamada distinta. Sirve igual para `SKILL_DIR`, para
`export KRAKEN_WORKSPACE=...` (selección de cuenta → operación correcta contra
el destino equivocado) y para `source "$HOME/.cargo/env"`. **Corolario para
revisar arreglos: sustituir una variable vacía por otra variable no arregla
nada.**

### Orden declarado vs orden de definición (2026-08-28)
En una skill con pasos numerados, comprobar en qué línea se DEFINE cada
marcador (`<dir>`, `$VAR`) y en qué línea se USA por primera vez. Un paso 0 que
usa un valor acordado en el paso 2 obliga al agente a improvisarlo — y lo
improvisa en el cwd, que suele ser justo el sitio prohibido. `grep -n` del
marcador ordenado por línea lo enseña en un vistazo.

### Diffear las dos mitades de un arreglo que tocó dos ficheros (2026-08-28)
Cuando un arreglo edita SKILL.md y un reference a la vez, contrastar sus
afirmaciones entre sí, no solo cada una contra el código. Caso real: un flag que
SKILL.md prohíbe y el reference exige, con SKILL.md ordenando leer el reference.

### La limitación autoinfligida vendida como propiedad fija (2026-08-28)
Cuando un documento declara "esto nunca se rellena / nadie escribe eso", buscar
en el propio directorio del plugin la pieza que lo rellenaría (`ls scripts/`,
`--help` de cada script) y luego `grep` de su nombre en toda la documentación.
Un escritor que existe y no se nombra convierte un freno de seguridad en adorno,
y la doc lo presenta como si no hubiera alternativa.


### Un gate que consume el veredicto de otro POR RUTA, sin frescura ni calidad
- Cuando la pieza B decide leyendo un artefacto JSON que produce la pieza A, atacar SIEMPRE tres cosas antes que la lógica: (1) pasarle un artefacto viejo de A, (2) pasarle uno que A generó sobre datos vacíos/erróneos, (3) NO pasárselo (si la bandera es opcional).
- La prueba se monta en 4 comandos: correr A antes del hecho (artefacto benigno), provocar el hecho, correr A otra vez (artefacto que refuta), y correr B con cada uno. Si B da el mismo veredicto o uno indistinguible, está roto.
- El agravante que convierte esto en T1 no está en el código sino en la prosa: buscar la frase del doc que enseña a leer "faltan artefactos" como "no encontró nada malo". Ahí el bypass deja de ser un fallo y pasa a ser la instrucción.
- Segundo agravante a comprobar siempre: si el código de salida no distingue los casos (p.ej. una bandera `--fail-on-*` que devuelve lo mismo para "refusal" y para "input que no producimos") y stdout imprime solo el veredicto sin las razones, entonces NADA de lo que el doc manda leer separa los dos.

### Recorrer una skill como un Claude recién llegado, en un proyecto vacío
- El ataque más productivo contra una skill NO es leerla: es ejecutarla en orden en un scratch sin memoria, sin config y sin los binarios que da por instalados, y parar en la primera línea que no corre. Ronda `unmassk-trading` 2026-08-28: los 5 scripts aguantaron todo, y aun así el veredicto fue FALLA, entero por la capa de prosa ejecutable.
- Comprobaciones fijas, en este orden:
  1. **`${CLAUDE_PLUGIN_ROOT}` en un bloque `bash` siempre está vacío** en la shell de la Bash tool (verificado 2026-08-03 por Ultron y re-verificado 2026-08-28). `python3 ${CLAUDE_PLUGIN_ROOT}/skills/.../x.py` corre como `/skills/.../x.py`. Claude Code sí inyecta "Base directory for this skill: <ruta>" al cargar la skill, así que el modelo *puede* sustituir a mano — pero si la skill no se lo dice, es improvisación.
  2. **El instalador de terceros**: bajar el tarball de release y `tar tzf` para ver qué ficheros existen de verdad. Un doc que dice "el CLI trae `agents/x.json`" suele estar mirando el repo de fuentes, no el artefacto instalado.
  3. **`pip install` sin más** falla en macOS con Homebrew por partida doble: `pip` no está en PATH (sí `pip3`) y `pip3` responde `externally-managed-environment`.
  4. **Toda línea `find "$(dirname "$(command -v <bin>)")/.."`**: sin el binario, `dirname ''` -> `.`, o sea `find ./..` = el padre del proyecto del usuario; con el binario en `~/.cargo/bin`, `find $HOME`. Montar un fichero homónimo en un directorio hermano y demostrar que el chequeo de seguridad lee el del proyecto ajeno. La regla "si no se puede leer, trátalo como peligroso" no salta: sí se leyó, otro fichero.
  5. **Cada bloque de comando sin `--output-dir`/`--state-dir` explícito** escribe en el cwd, que es el repositorio del usuario. Correrlo y `ls` el scratch.
  6. **Contradicción entre la secuencia numerada y la tabla de modos**: la secuencia suele excluir pasos ("los pasos 8-11 son de órdenes reales") que la tabla declara aplicables en todos los modos. Rastrear si el fichero del modo afectado invoca alguna vez esos scripts — si no lo hace, la tabla miente.
  7. **El mismo flag con dos valores distintos en dos ficheros** que el modelo lee en la misma sesión (`--state-dir <dir>` vs `<dir>/theses`) es divergencia silenciosa: cada script mira un almacén distinto y ambos contestan "vacío".

### El bloque de comando copiable manda sobre el párrafo que lo corrige
- Una skill puede decir en prosa "sin esta bandera el halt no bloquea nada" y, tres líneas antes o en otro fichero, imprimir el bloque `bash` sin esa bandera. Lo que se ejecuta es el bloque.
- Ataque: extraer TODOS los bloques de comando de la skill y sus referencias, ejecutarlos literalmente, y comparar el resultado con lo que la prosa promete. Contar cuántos sitios muestran el comando y en cuántos falta la bandera crítica.

### Calendario ajeno: reloj del mercado equivocado sobre datos 24/7
- Cuando código levantado de otro dominio agrega por "día" con un huso fijo (`America/New_York`, semanas de lunes) y el proyecto lo usa sobre un mercado 24/7, el fallo no es de frontera: es un número falso. Probar el MISMO hecho a dos horas del mismo día natural del usuario y comparar el veredicto.
- La ventana peligrosa es [00:00, |offset|) UTC: ahí el hecho se contabiliza al día anterior, el agregado del día sale 0.00 y la calidad del dato sigue diciendo OK.
- Comprobar si la suite de tests ya CODIFICA ese comportamiento: si hay un test que lo afirma como correcto, el hallazgo sigue siendo real pero hay que decir que está bendecido, no descubierto.

### Colisión de nombre de artefacto con marca de tiempo de segundos
- Cualquier `salida_%Y-%m-%d_%H%M%S.ext` escrita con truncado pierde artefactos sin concurrencia ninguna: dos ejecuciones seguidas en el mismo segundo bastan.
- Prueba barata y demoledora: N ejecuciones con veredictos distintos -> contar ficheros. Si el que sobrevive es el permisivo, es un hallazgo de dinero, no de higiene.
- Señal delatora en el registro: varias entradas de auditoría idénticas apuntando todas al mismo fichero.

### Re-running the ORIGINAL reproducing command verbatim after a claimed fix
- When a prior round left a live PoC (e.g. "delay function X via monkeypatch, race an external writer in during the delay"), re-run that EXACT command against the new code before trusting a docstring that says "closes this window"
- A fix can legitimately close a related-but-narrower window (e.g. between two internal reads) while leaving the original command's exact target (the gap right before the final write call) unchanged — the fix reads as if it closed "the" race but only closed one shape of it
- Distinguish the two by testing BOTH: the exact original PoC, and the specific narrower window the fix's own docstring claims to address — a "held" on the narrower one does not imply "held" on the original

### Monkeypatch-widen the real gap instead of racing on luck (crash-mid-multi-step-write)
- Pattern: any write-then-git-commit sequence where the write is atomic but the
  commit is a SEPARATE later step (e.g. `gitcmd.atomic_write()` then
  `notes_commit.stage_and_commit()` in `lib/memory/rules.py::add()`) has a real,
  non-zero gap between the two -- a process death (SIGKILL/OOM/host eviction) in
  that gap leaves the write on disk with no commit behind it, permanently.
- The gap is real in production but nanoseconds wide; don't rely on timing luck.
  In a throwaway scratch script (never edits the project), monkeypatch the
  function that starts the SECOND step (e.g. `notes_commit.stage_and_commit`) to
  `time.sleep(N)` before calling the real implementation, then self-SIGKILL
  (`os.system("(sleep 1; kill -9 <pid>) &")` from inside the same process, or a
  second thread) during that sleep. This only widens an already-real window to
  make it observable -- it does not fabricate a new code path.
- Same trick works for TOCTOU on a read-modify-write: delay the WRITE call
  (not the read) so a second thread's plain `open()/write()` on the same file
  lands in the middle, then check whether the delayed write clobbers it.
- Confirmed twice in one round (2026-08-23, `lib/memory/rules.py::add()`): the
  atomic_write-then-commit gap silently reproduces exactly the corruption I-003
  was filed for, and the read-modify-write of `previous_content` silently
  clobbers a concurrent external edit to the same file -- both `ok=True`.

### A new validation gate added to ONE real caller of a shared Note-building path — always check the others
- When a contract adds a new check function (e.g. `validator.validate_issue_gate`) and wires it into ONE script's `main()` (e.g. `bin/memory/note.py`), grep the whole tree for every OTHER place that also turns raw input into the SAME kind of object and validates it — here, `hooks/customs.py::_decide_note()` builds a `Note` via `format.parse_message()` from a raw `git commit -m` and calls `validator.validate_note()`, but never the new gate function. `validate_note()`'s own docstring even says the new gate is deliberately excluded (same reasoning as `validate_pain_question`) — that's correct for `note.py` (which calls it separately) but silently wrong for any OTHER caller of `validate_note()` that never adds the extra call. This is the SAME shape as D-056's BREAK 1 (archived-filter) — recognize the pattern instead of re-deriving it: "a Context/gate built once and reused correctly by caller A, but caller B constructs its own and forgets the newest addition".
- Same technique that worked here: build the exact commit MESSAGE the CLI would produce (`format.build_message()` on a hand-built `Note`, missing the new field/flag on purpose), feed it as a PreToolUse JSON payload directly to the hook script over stdin (`{"tool_name": "Bash", "tool_input": {"command": 'git commit -m "<msg with REAL embedded newlines, not shlex-escaped \\n>"'}, "cwd": ...}`), confirm `{"decision": "approve"}`, THEN actually run the real `git commit` (dynamic `$SUB` trick, see below) and read it back through an independent real CLI (`search.py --id`) — never trust the hook's own JSON decision as the only evidence, the commit has to actually land and be independently queryable.
- Gotcha: `_extract_dash_m_message` tokenizes the `command` STRING with `shlex.shlex(posix=True)`, which mimics real shell quoting — a Python `json.dumps()`-escaped `\n` (literal backslash-n, two chars) inside a double-quoted bash arg stays literal backslash-n after shlex too (POSIX double quotes don't expand `\n`), so a message built with `\n`-escaped embedding never round-trips as a real note and the hook falls through to the generic "not a note" rejection instead of exercising the gate at all. Use REAL embedded newline bytes in the Python string that becomes the `command` field (`'git commit -m "' + msg + '"'`, `msg` containing actual `\n` characters) — that's what a real multi-line `-m` argument looks like in an actual terminal/Claude-Code Bash call.

### Isolate a round-trip corruption's real trigger by testing pure size separately from the suspected special character
- When a large pathological payload (embedded `\r`, unicode, fake field labels, absurd length all mixed together) shows a round-trip mismatch, don't stop at "big pathological input breaks it" — split the variable. Re-run the SAME size with only the suspected character removed (e.g. same 200KB, all `y`, zero special chars) to prove size alone is clean, isolating the real trigger to the specific byte. This turned a vague "quote sometimes corrupts" into a precise, reproducible, single-character root cause (`\r` -> `\n` via `subprocess.run(text=True)`'s universal-newline translation on the READ side, colliding with the fold-continuation stripper's own single-space heuristic) instead of an unfalsifiable "large input is risky" claim.
- Also confirm WHERE in the round trip the corruption happens by checking the git object's OWN raw bytes (`git log --format=%B -1 | python3 -c "sys.stdin.buffer.read()..."`, reading binary, never through `text=True`) before blaming the writer — here the raw git object was byte-perfect (the `\r` survived storage), which proves the corruption is entirely on the READ side (`gitcmd.run()`'s own `subprocess.run(text=True, encoding="utf-8")`, missing `newline=""`), not on write.

## Sistema actual — memoria v2 (`lib/memory/*`, `hooks/customs.py`, `hooks/checklist-gate.py`, `hooks/skill-checklist-inject.py`, `bin/memory/*`)

### git error-message marker lists miss the "exists on disk, uncommitted" variant
- Pattern: any code that classifies a `git show`/`git log` failure by matching `stderr` against a fixed marker string list, to distinguish "state X is fine" from "real git error"
- Real git has MULTIPLE distinct messages for what looks like one conceptual case ("no committed version of this path") depending on whether the path currently exists on disk:
  - path never existed anywhere: `"fatal: path 'X' does not exist in 'HEAD'"`
  - path EXISTS on disk right now but was never committed: `"fatal: path 'X' exists on disk, but not in 'HEAD'"` (different string entirely)
  - zero commits in the repo at all: `"fatal: invalid object name 'HEAD'."`
- A marker list built from only ONE of these (often the one a happy-path test exercises) makes the uncovered variant raise instead of returning the documented empty/neutral value — reproduce by creating the file on disk without ever adding/committing it, then reading it at HEAD
- Especially dangerous when the very feature being tested is "detect a file that was written but never committed" (a SIGKILL/partial-write scenario) — that is EXACTLY the disk-exists-but-uncommitted case, so the crash lands on the first real use of the feature, not on an edge case
- Root location this round: `lib/memory/query.py::show_file_at_head()`, `_SHOW_PATH_MISSING_MARKER = "does not exist in"` only
- **[CERRADO — verificado 2026-08-25]**: `query.py:118` ahora tiene
  `_exists_at_head()`, que comprueba EXISTENCIA vía `git cat-file -e
  HEAD:<path>` (solo returncode, nunca prosa de stderr) antes de que
  `show_file_at_head()` (línea 145) llame a `git show`. Ya no clasifica por
  el texto del mensaje de git en ningún punto. Cerrado también en vivo en
  `round-history.md` ("I-003 re-attack, ronda 5", punto 1: MUERTO).

### A contract satisfied by ONE caller of a shared validator is not satisfied by the OTHER caller
- Pattern: a pure validator function (`validate_note`/`validate_replacement`) takes its world-state pre-filtered in a `Context` object, built separately by EACH of its consumers — never fetches anything itself
- One consumer's own docstring can explicitly document a filter it applies before building `Context` (e.g. `bin/memory/note.py::_build_context()`: "`existing_in_zone` se filtra contra `indexes.archived_ids(pm)` antes de entrar en `Context`") while a SECOND, independent consumer of the exact same validator (`hooks/customs.py::_decide_note()`, the PreToolUse hook that intercepts a raw `git commit`) builds its own `Context` from the unfiltered read (`query.by_zone()`, which deliberately returns the WHOLE history including archived, by design, for OTHER readers like the zone report) and never applies the same filter
- Net effect: the exact same "similar note, need --replaces" duplicate-gate rejection that the CLI (`note.py`) correctly suppresses for archived candidates still fires against those same archived candidates through the OTHER real entry point (a raw `git commit -m "..."` that an agent or the customs-gated Bash hook processes) — a contract clause ("NO dispara contra archivadas") that reads as globally true is actually only true for ONE of the two real callers
- Detect by finding every caller of the shared validator/Context builder, diffing what each one does BEFORE constructing `Context`, not just reading the validator's own docstring
- Root this round: `unmassk-toolkit/hooks/customs.py:666` (`existing_in_zone = query.by_zone(note.zone1, note.zone2)`, no archived filter) vs `unmassk-toolkit/bin/memory/note.py:154-156` (same read, then `if n.id not in archived`)
- **[CERRADO — verificado 2026-08-25]**: `hooks/customs.py::_decide_note()`
  filtra `archived = indexes.archived_ids(pm)` antes de construir
  `existing_in_zone`, mismo patrón que `note.py`. Re-atacado el mismo día
  (D-056 re-attack): repro original ahora aprueba; confirmado que NO
  sobre-filtra (candidato contra nota viva sigue bloqueando). `known_ids`
  sigue sin filtrar archivadas para `Origin:`/`Replaces:` — no es el mismo
  agujero, no reabierto.

### An ordered-pair zone comparison silently misses the same pair typed in reverse
- Pattern: any duplicate/overlap gate that compares `note.zone1 != candidate.zone1 or note.zone2 != candidate.zone2` when the CLI has no canonical order for a "pair" of zones (`--zones z1 z2` accepts any order, nothing sorts or normalizes it before storage)
- Two notes about the same topic, same exact non-empty key SET, one filed `--zones A B` and the other `--zones B A` — semantically the same "par de zonas" the contract promises to gate on — are NOT caught, because the comparison is positional (zone1-to-zone1, zone2-to-zone2), not set-based
- Realistic, not manufactured: nobody remembers or is told to preserve zone argument order between two notes on the same subject written weeks apart
- Root this round: `unmassk-toolkit/lib/memory/similar.py:133-135` (`_find_exact_key_match`'s zone-pair guard, same shape of bug in `find_similar` at line 98)
- Estado 2026-08-25: dejado abierto A PROPÓSITO por decisión del dueño
  (BREAK 2 del round D-056, "orden de zonas, se deja como decision de
  diseno" — no volver a resenalar sin que el dueño lo pida).

### A --chain/lineage view built only from "notes touching the queried zone" loses a thread whose HEAD moved zones
- Pattern: a lineage/chain report resolves its candidate set via a single-zone axis match (`zone1 == q or zone2 == q`), then builds each thread by walking BACKWARD from a head found in that same candidate set — never forward, never independent of the axis
- If a note's REPLACEMENT (the new head, still fully valid content) was filed under a completely different zone pair (a realistic "this got reclassified/broadened, refiled under different zones" edit — no zone-consistency rule ties a replacement to its predecessor's zones), the archived predecessor still matches the OLD zone's query (so `_chain_is_superseded()` correctly excludes it as a head) — but the new head never enters `matched` for that zone, so no thread ever walks back to it. The entire lineage (predecessor AND, implicitly, the query never learning where it went) disappears from the chain view of the zone it used to belong to
- Worse than not having the feature: the OLDER, unstructured `--todo` listing for the exact same zone still shows the full archived chain with its `(↺ old_id)` markers — the NEWER `--chain` view (built specifically to fix "el enlace de sustitucion se ve por un solo lado") loses MORE information than the view it was meant to improve on, for this one input shape
- Root this round: `unmassk-toolkit/lib/memory/report.py::build_chain()`/`_chain_threads()` (matched-set built once via `_notes_touching_zone`, threads only walk backward within it) — reproduced live: M-001→M-002→M-003 chain filed [alpha][beta], M-004 (replaces M-003) filed [gamma][delta]; `search alpha --chain` shows 0 memos (only unrelated I/R threads), `search alpha --todo` (no --chain) still shows all 3 archived memos correctly
- **[CERRADO — verificado 2026-08-25]**: `_chain_is_superseded()` ahora
  recibe `by_id` y solo trata una nota como sustituida si el id de la
  sustituta real está DENTRO de ese conjunto; si no, pasa a ser cabeza de
  su propio hilo. Repro original resuelto en vivo (M-001→M-002→M-003 ya
  aparece en `--chain`). **Pero el arreglo abrió un agujero nuevo,
  distinto**: una nota con sucesora real y viva pero archivada en OTRA
  zona (M-003→M-004) se pinta `cerrada` en el propio texto del `--chain`,
  aunque `ChainThread.closed` está documentado en `model.py:191` como
  "True = cierre legítimo sin sucesora" — falso para este caso. `--todo`
  para la misma nota es más honesto (`archivada (↺ M-002)`, sin afirmar
  "cerrada"). T2/T3 (información engañosa, no pérdida de datos), no
  bloqueante, no re-señalado por indicación del coordinador.

### lib/memory/indexes.py -- insert()/remove() lost-update race, no lock/atomic_write wired in despite the sibling module existing for exactly this (memoria-v2, 2026-08-02)
- gitcmd.py (same package) ships `file_lock()` + `atomic_write()` specifically because its own
  docstring names "una carrera entre dos escritores del mismo indice que pierde el cambio del
  que llego primero sin avisar" as one of only 3 named risks that whole layer exists to prevent.
  zones.py (also same package) correctly wires its OWN private lock+atomic pair around `add()`.
  indexes.py -- the ONE module that actually reads/writes the 8 index files -- imports neither
  gitcmd nor any lock/atomic mechanism at all: `insert()` appends via plain `path.open("a")`,
  `remove()` does `path.read_text()` -> filter -> plain `path.write_text()` with zero locking.
- Live PoC (real OS processes, ZERO mocking): pad an index with 3000 real lines (via real
  `insert()` calls, widens the window), then launch two real `python3` subprocesses
  simultaneously: one calls `indexes.insert(NEW_NOTE, ...)`, the other calls
  `indexes.remove(UNRELATED_EXISTING_ID, ...)`. Both exit rc=0 (success, no exception anywhere).
  14/40 trials (35%): the just-inserted note is PERMANENTLY GONE from the file afterward --
  confirmed via an independent plain-pathlib read AND via `indexes.read()` itself. Root cause:
  `remove()`'s read-filter-write is not atomic as a UNIT -- if `insert()`'s append lands between
  `remove()`'s read and its write, `remove()`'s write (computed from the stale pre-insert
  snapshot) clobbers the whole file, including the concurrently-appended note remove() never
  even saw.
- Also confirmed via a fully deterministic version (real threads + a `Path.write_text` timing
  patch used ONLY to force the worst-case interleave, not to alter semantics): same result,
  100% reproducible.
- Concurrent insert()-vs-insert() (both append-mode) HELD across 20 real parallel subprocesses --
  0 losses, 0 corruption, interleaved-but-complete lines (POSIX O_APPEND + small writes below
  PIPE_BUF). The break is specifically insert-vs-remove (or presumably remove-vs-remove), not
  concurrent appends.
- Caveat on current reachability: `notes.py` (the layer-2/3 orchestrator that would actually
  call `insert()`/`remove()` from real CLI commands) does not exist yet in this codebase (grep
  confirmed, phase 2/3 per ids.py's own docstring) -- so there is no real *caller* wiring two
  concurrent index writes together TODAY. The bug is 100% live in the module actually in scope
  (`lib/memory/indexes.py`, one of the 13 target modules) and will be reachable the moment any
  caller writes/replaces two notes to the same index around the same time (two sessions, or one
  `--replaces` transaction touching insert+archive/remove close together) -- an entirely
  ordinary usage pattern for this system, not a crafted edge case.
- Root: lib/memory/indexes.py:157 (`insert`), :172 (`remove`) -- no `file_lock`/atomic
  read-modify-write anywhere in this module; contrast lib/memory/gitcmd.py:204 (`file_lock`),
  :256 (`atomic_write`) and lib/memory/zones.py:136 (`add`, correctly locked+atomic).
- Nota 2026-08-25: `notes.py` ya existe hoy (capa 5 completa) — la reserva
  de "no hay caller real todavía" ya no aplica; el caller real es
  `bin/memory/note.py`/`bin/memory/rezones.py`. No re-atacado esta pasada,
  pendiente de una ronda de concurrencia dedicada si se vuelve a tocar
  `indexes.py`.

### lib/memory/format.py -- Keys/Origin/Replaces body fields bypass the folding mechanism, silent unparseable note on embedded newline
- `_body_field_line()` (format.py:242) wraps Why/Awaits/Description in `_fold()` (the
  continuation-line mechanism that survives embedded `\n` losslessly, per the module's own
  extensive docstring section on folding) but Keys/Origin/Replaces use plain f-strings
  (`f"Keys: {_encode_list(note.keys)}"`, `f"Replaces: {note.replaces}"`) with NO folding.
- Live PoC: `Note(..., keys=("normalkey", "weird\nkey"))` -> `format.build_message(note)`
  produces text containing a raw, un-prefixed `key` line with no leading continuation space ->
  `format.parse_message()` on that exact output returns `None` (not an exception) -- the note
  becomes completely unparseable by the module's own paired consumer, with zero error raised
  anywhere in the round trip.
- Reachability narrower than the indexes.py race: requires a literal `\n` inside a Keys/Origin/
  Replaces value, which normal CLI-typed short synonym words are unlikely to contain -- but
  nothing in validator.py (`normalize_keys`, `validate_fields`) rejects or strips embedded
  newlines from these fields before they reach `build_message`, so it is not blocked upstream
  either. Not a broken promise (format.py's docstring explicitly scopes the fold guarantee to
  Why/Description/Awaits/headline/context-points only, never claims it for Keys/Origin/Replaces)
  -- it's an unflagged gap in an otherwise very deliberately hardened round-trip contract.
- Root: lib/memory/format.py:250-262 (`_body_field_line`, the Keys/Replaces/Origin branches).

### Index-file `name` parameter accepted unchecked, corrupts any co-located file
- Pattern: a module that owns "the only N legitimate filenames it touches" (its own
  docstring says so) takes that filename as a bare `str` from the caller and does
  `if path.exists(): <read-modify-append-write>` with zero membership check against
  its own closed vocabulary of legitimate names (`vocabulary.INDEX_FILES`).
- Any OTHER real file that already exists in the same directory (a JSON config, a
  sibling module's own data file) is a silent target: `insert(line, "zones.json", root)`
  appends a memory-index text line to valid JSON, no exception, breaks `json.loads()`
  on next read. `path.exists()` is satisfied by ANY file, not just the intended 8/N.
- Live PoC: lib/memory/indexes.py:158-183 `insert()` — see
  unmassk-toolkit/lib/memory/indexes.py, target zones.json (co-located, written by
  the sibling `zones.py::add()`).
- Caveat worth checking before reporting: does the CURRENT real caller ever pass an
  unconstrained name? If it always passes from a closed dict (as `notes.py::write()`'s
  `_TYPE_TO_INDEX_FILE` does today), the bug is real but not end-to-end reachable
  yet — disclose that nuance, don't overstate severity, but still report: it's a
  structural gap in the target module's own public contract, and the next caller
  (or a maintenance one-off script under the single-operator threat model) may not
  have that same discipline.

### `_present_fields`-style optional-field detection: identity check vs truthiness
- Pattern: a function builds a "which optional fields are present" set to compare
  against a required/allowed-fields table. If ONE field uses `if x is not None`
  (identity) while a NEIGHBORING field on the same line uses `if x:` (truthiness),
  an empty string/empty collection sneaks past the identity-checked field as
  "present" even though it carries zero content.
- Concretely: lib/memory/validator.py:332-347 `_present_fields()` — `description`
  correctly requires truthy (`{"description"} if note.description else set()`), but
  `why` only checks `is not None` — `note.why = ""` registers as present, so a
  type where `why` is REQUIRED (e.g. `D`) accepts an empty-string why with zero
  rejection. Exactly the "zombie field" failure class the module's own test
  docstring names as the reason this check exists (v1's 1002 unread `Why:` lines).
- Reachable end-to-end today (validate_fields is called directly inside
  validate_note/write(), no closed-dict caller gate protects it like the indexes.py
  finding above).

### SIGKILL mid-transaction: `except BaseException` cannot cover process kills
- Pattern: a module's own docstring/decision log claims "try/except BaseException
  around the index-write→commit gap fixes ANY mid-flight interruption (Ctrl-C
  included)". True for KeyboardInterrupt/exceptions, structurally FALSE for
  SIGKILL/OOM-kill/power-loss — no userspace try/except can ever run after those.
- Concretely: lib/memory/notes.py `write()` — `indexes.insert()` (durable,
  atomic_write+fsync) runs BEFORE the `try/except BaseException` block that guards
  the commit step. Live PoC: real subprocess, monkeypatch `notes.gitcmd.commit` to
  `os.kill(getpid(), SIGKILL)` right when invoked, confirm child died by signal
  (returncode -9), then read the index file from a FRESH, independent process:
  the inserted line survives forever, `query.by_id()` (the sole history reader)
  returns `None` for that id — a permanent, silent index→nothing dangling
  reference. This class of gap generalizes to `rules.py::add()` too (2026-08-23
  round) — see `rules.py`'s own SIGKILL-gap entry below.
- General lesson: any "we now catch BaseException" claim needs the caveat "except
  signals that kill the process outright" spelled out, or the claim is a
  DECEPTION (T1 when the gap it's hiding is itself corruption/silent-failure).
- Estado 2026-08-25: para `notes.py` la mitad silenciosa está CERRADA —
  `health.coherence()` detecta el índice huérfano y lo muestra en el
  AVISOS de `boot.py`, `reindex.py` (sin `--verify`) lo repara. La ventana
  del SIGKILL en sí sigue siendo estructuralmente imposible de evitar (no
  es un bug, es la naturaleza de un `kill -9`). Para `rules.py` el mismo
  gap SÍ sigue abierto y SIN red de seguridad — ver la entrada de
  `rules.py` más abajo.

### Uncoordinated sibling writer on the same file: locked producer + unlocked committer
- Pattern: module A (`notes.write()`) protects a file with a lock + insert-then-
  commit-then-restore-on-failure transaction. A SIBLING function in the SAME
  module (`notes.write_work()`) can commit that exact same file path with ZERO
  lock, because its contract is "commit arbitrary explicit paths" and nothing
  stops an index-file path from being one of them.
- Concretely: paused A (real process, monkeypatched `format.build_message` as the
  pause point — right after `indexes.insert()` already durably wrote+released its
  own per-file lock, before A's own git add/record step) while a second, real,
  already-shipped function (`write_work()`) commits the SAME path with an
  unrelated message. Result, all confirmed live: (1) B's commit silently absorbs
  A's uncommitted index line under a commit message that has nothing to do with
  it — permanently unparseable/undiscoverable via `query.by_id` (format doesn't
  recognize B's subject line as a note) — a data fragment leaked into unrelated
  history forever; (2) A's own subsequent record attempt then fails because there
  is nothing left to record for that path (`returncode=1`), and CRITICALLY git
  puts the "nothing to record, tree clean" diagnostic on STDOUT, not stderr —
  confirmed via a raw subprocess probe — so `WriteResult.git_error` (which only
  ever surfaces `.stderr`) comes back as an EMPTY STRING, exactly the "fallo sin
  causa" gitcmd.py's own docstring exists to prevent, on a REAL git failure that
  the existing 6-row test suite never exercises (its two failure-injection tests
  both use `.git/index.lock`, which DOES populate stderr).
- General lesson: when auditing a "transaction is safe because of lock X", check
  every OTHER function in the same module/file that can touch the same resource
  without taking lock X — a sibling with a looser contract is a real, live seam.
- Ver también "write_work() silent cross-writer content misattribution" más abajo
  — mismo mecanismo, medido en vivo con tasa de colisión real.

### lib/memory/gitcmd.py -- commit() trusts ambient process-wide os.chdir(), silently commits into (or loses a note against) the WRONG repo under in-process thread concurrency (memoria-v2, 2026-08-02)
- `commit()`'s own docstring discloses it takes no `cwd` param and "hereda el cwd ambiental del proceso... quien la llama ya esta corriendo dentro del repo" -- an assumption that only holds if exactly one logical caller ever uses the ambient cwd at a time. `os.chdir()` in CPython is PROCESS-global, not thread-local: any two threads in the same process sharing this module (this codebase's OWN test suite proves multi-threaded usage is normal here -- test_gitcmd.py's row-2 test alone spins 20 threads) racing `os.chdir(repo) -> ...work... -> gitcmd.commit(msg, [relative_path])` can have thread A's `Path.cwd()` read (inside `commit()`) return thread B's repo instead of A's own, if B's chdir lands in the gap between A's chdir and A's `commit()` call -- a gap any real caller has (building the message via `format.build_message()`, per commit()'s own docstring naming `notes.write` as the real caller-to-be).
- Live PoC (real threads, 2 real repos, zero mocking): repo1/repo2, each with its own `note.txt` staged. Thread A: `os.chdir(repo1)`; realistic gap (work before calling commit); `gitcmd.commit("desde A...", [Path("note.txt")], allow_empty=False)`. Thread B: brief head start, `os.chdir(repo2)`; `gitcmd.commit("desde B...", [Path("note.txt")], allow_empty=False)`. 100% reproducible across 3 independent runs: B lands correctly in repo2. A's commit executes with the ambient cwd already flipped to repo2 by B -- A's own note (repo1) is NEVER committed (repo1 ends with an empty history, `git log` on repo1 says `fatal: invalid object name 'HEAD'` -- the note is real on disk but permanently unversioned) while A's call returns `GitResult(returncode=1, stdout='On branch main\\nnothing to commit, working tree clean\\n', stderr='')`.
- SECOND, independent break riding on the first: that `returncode=1` failure has `stderr=''` -- EMPTY -- which directly violates gitcmd.py's own row-1 contract, the exact one test_gitcmd.py's quoted row-1 test (named after "failed" + "git" + "command" + "returns" + "full_real_stderr_never_empty") exists to guarantee ("un git que falla devuelve su mensaje entero, nunca vacio"). The existing test only exercises ONE git-failure shape (missing pathspec, whose message IS on stderr); "nothing to commit" is a real, common git failure whose message lands on STDOUT, and `run()`/`commit()` only ever inspect/return `stderr` -- so this whole class of git failure silently produces an empty-diagnostic `GitResult` on `returncode != 0`, invisible to any caller that (correctly, per the module's own contract) trusts "stderr non-empty on failure".
- Root: lib/memory/gitcmd.py:113 `commit()` (no cwd param, `cwd=Path.cwd()` implicit), :61 `run()` (only captures/returns `stderr`, never `stdout`, even though some real git failure diagnostics land on stdout).
- **[CERRADO para producción — verificado en la ronda capa 2/3 re-attack]**:
  `notes_commit.py:195` (el único caller real hoy) siempre pasa
  `cwd=root`. La carrera de `os.chdir()` ambiental solo se reproduce
  omitiendo `cwd` a propósito, cosa que hoy solo hace el propio
  `test_gitcmd.py` (compat retro documentada, no un caller de producción).

### lib/memory/rejection.py -- build() validates kwarg PRESENCE, never VALUE, silently drops one of its 3 mandatory declared elements on empty tuple/string (memoria-v2, 2026-08-02)
- Module's own docstring states the whole reason it exists as ONE piece instead of ten: "los diez rechazos... comparten la misma anatomia -- que ha pasado, las opciones, el comando exacto para relanzar". `build()`'s only validation is `set(parts) == _EXPECTED_PARTS` (key presence) via `TypeError` -- it never checks that `options` or `command` (tuples) are non-empty, or that `what` (str) is non-empty.
- Live PoC (no mocking, pure module calls): `build("k", what="ALGO PASO", options=("opcion A",), command=())` -- zero exception. `render_terminal()` output: `'❮ ALGO PASO\\n\\nopcion A'` -- the "Relanza:" section, and the relaunch command itself, is completely absent (because `_render()` gates it on `if r.relaunch:`, and an empty tuple is falsy) -- no error, no warning, nothing distinguishes this from a legitimately-relaunch-less rejection.
- Root: lib/memory/rejection.py:64-72 (`build()`'s validation only checks key membership, never value truthiness) and :90 (`_render()`'s `if r.relaunch:` silently omits the section instead of asserting/failing loud on an empty tuple).
- **[CERRADO — verificado en la ronda capa 2/3 re-attack]**: `build()`
  ahora lanza `ValueError` en valor vacío. `validator.py` (el productor
  real, no existía cuando se encontró el hallazgo) nunca construye una
  tupla vacía de todas formas.

### lib/memory/ids.py next_id() + notes.close() -- closing the last live note of a type PERMANENTLY reuses its ID for the next unrelated note of that type (memoria-v2 capa 5, scripts round, 2026-08-03)
- `ids.next_id(type_, index)` (ids.py:30-45) computes the next number purely from
  the LIVE index it's handed -- `max(numbers in index) + 1`. `notes.close()`
  (notes.py:335-392) REMOVES the closed note's line from its live index (moved to
  `ARCHIVED.md`) as its whole point. `notes.write()` (notes.py:140-215) always
  calls `ids.next_id(note.type, current_index)` with `current_index =
  indexes.read(index_name, pm)` -- the live index AT THAT MOMENT, no awareness of
  `ARCHIVED.md`.
- Live PoC through the REAL capa-5 scripts end to end (`note.py` + `close.py`),
  the intended everyday "open incident, close incident" workflow: create `I-001`
  (only incident in the repo), close it -- INCIDENTS.md's live index goes back to
  empty. Create a brand-new, UNRELATED incident -- `ids.next_id()` returns `I-001`
  again. TWO real, permanent git commits now share the literal identifier `I-001`
  forever in git history. Repeated 4 more times on `I-002` in the same session.
- Downstream, all confirmed live: `search.py --id I-001` resolves to the OLD/
  archived note, hiding the real live note that shares its ID. `health.
  duplicates()`/`ids.find_duplicates()` NEVER catches this (only one "I-001"
  line ever sits in the live index at a time). `health.coherence()`/`reindex.py
  --verify` compares ID SETS not counts -- prints `✓ índices coherentes con git
  (5 líneas / 6 notas)` -- a visible, unexplained number mismatch, live in
  `boot.py`'s own daily AVISOS banner. `reindex.py` (no `--verify`) also can't
  repair it.
- T1 (identity/memory corruption) + tied T1 DECEPTION (the two ✓ lines are
  demonstrably lying about the exact thing they exist to guarantee, on the
  ordinary open-incident/close-incident cycle, not a lab case).
- General lesson: a "the next id computation only sees the live index" fix that's
  correctly reasoned about for ONE writer path (`replace()`, same-transaction
  snapshot) doesn't automatically hold for a DIFFERENT writer path (`close()`
  then a later independent `write()`) that shares the exact same blind spot but
  has no snapshot to protect it.
- Estado 2026-08-25: no reportado como cerrado en ninguna ronda posterior
  leída — sigue abierto salvo que se re-verifique.

### write_work() silent cross-writer content misattribution (capa 2/3 re-attack, 2026-08-03)
- Root cause, two parts that only bite TOGETHER: (1) `gitcmd.commit(message, paths,
  cwd=...)` with an explicit pathspec does NOT commit "whatever `git add` staged" --
  git's own well-documented behavior for `git commit -- <pathspec>` is to re-read the
  CURRENT WORKING TREE for those exact paths at commit time, overriding whatever was
  staged earlier for that path. (2) `notes_commit.py::write_work()` (used by
  `bin/memory/work.py`, its only real caller) takes NO lock at all -- unlike
  `write()`/`replace()`/`close()` (`notes.py:199,314,401`), which wrap their entire
  add+commit sequence in `gitcmd.file_lock(lock_resource(root))`.
- Live PoC (100% deterministic, not luck): 2 real OS processes both target the SAME
  path. A: writes content-A, `git add` (stages A), PAUSES. B: writes content-B,
  `git add` (re-stages B), PAUSES. A resumes: `git commit -m "msgA" -- path` --
  re-reads the worktree (now content-B) and commits it under A's OWN message. Net
  result: a permanent git commit titled "msgA-..." whose content is B's. `WriteResult`
  for A returns `ok=True, git_error=None` -- looks like a clean success.
  Un-synchronized: ~15% hit rate (3/20). Same shape against `notes.write()` (which
  HAS the lock): 15/15 both land, zero failures.
- General lesson: "commits exactly these paths" is a claim about WHICH files change,
  not about WHOSE version of them lands -- a pathspec-limited commit is not a
  snapshot of what you `git add`ed, it's a snapshot of the worktree at commit time.
  Any writer that skips the shared serialization lock is still vulnerable if two
  such writers ever target the same real path.
- Estado 2026-08-25: `bin/memory/work.py` y `bin/memory/wip.py` (que reusa
  `write_work()`) siguen existiendo hoy — no re-verificado si se le añadió
  lock desde entonces; tratar como abierto salvo re-confirmación.
  `bin/release.py`'s `_execute_commit_push()` también delega en
  `notes.write_work()` desde entonces (verificado 2026-08-25, ver bloque de
  infraestructura más abajo) — mismo mecanismo, nuevo consumidor a tener en
  cuenta si se re-ataca esta pieza.

### close-session round (session_transcript.py, compact)
New pattern: **destination-file naming with no session identity is a double
vulnerability, not one.** `_newest_transcript()` picks the mtime-newest
`.jsonl` under `~/.claude/projects/<slug>/` with NO way to confirm it's the
invoking session's own transcript, and `_RIVAL_WINDOW_SECONDS=600` only
flags a SECOND file within 10 min of the one it picked -- it never checks
whether the PICK ITSELF is stale relative to "now". Live PoC: session A idle
870s (reading/thinking) while session B (another window, same project) kept
writing -> script silently picks B's transcript, zero `warning:` line, close
written entirely from the wrong session. Reproduces the exact win condition
"produce a close about the wrong session, without anything saying so."
Second, independent pattern in the SAME function family: a tag-stripping
filter matched "BY NAME" (`_TAG_START`, exact strings like `<system-
reminder>`) still nukes a real user message whenever the project's own
domain is the tag mechanism itself -- users say `<system-reminder>` in real
prose about hooks, and the whole message vanishes, no warning. General
lesson: when a filter's exclusion list is drawn from the SAME domain the
users legitimately talk about, name-exact matching is not safe against real
content.
Third: `open(destination, "w")` with a DETERMINISTIC path (based on
transcript basename only, no pid/uuid, no lock, no atomic tmp+rename) lets
two genuinely concurrent invocations interleave into ONE corrupted file --
10/15 (67%) live trials mixed both sessions' content with zero error.
- Ubicación actual (2026-08-25, verificado): el script vive hoy en
  `unmassk-toolkit/skills/unmassk-close-session/scripts/session_transcript.py`
  (movido desde su ubicación original, mismo fichero, no borrado). No
  re-verificado si estos 3 hallazgos siguen abiertos tras el movimiento.

### A field opened to all note types can have a SECOND, undiscovered renderer gap besides the one everyone found
- Pattern: when a field (e.g. `Note.issue`) goes from "only type M" to "all seven
  types", the obvious production gates to check are the vocabulary/type allowlist
  and the by-id renderer (`report_render_note.py`). Both were correctly found and
  fixed here (D-044/D-045, `lib/memory/vocabulary.py` + `report_render_note.py`).
- But a SIBLING renderer (`lib/memory/report_render.py`, used by `gitmem search
  <zone>` and `gitmem search <word>` -- the two most ordinary "browse/find"
  commands) can independently never have supported the field AT ALL, for ANY
  type, including the one type (M) that already had the field before this task.
  Grep every per-type block-render function for the field name -- a field with a
  real value that's genuinely stored and correctly shown by ONE renderer can be
  silently absent from a SECOND renderer of the exact same note, with zero test
  anywhere catching it, because the two renderers were built/reviewed at
  different times and nobody diffed them against each other for field parity.
- The module's own "single declared reader" self-check (`vocabulary.py::FIELDS`)
  does NOT catch this: the declared reader (`health.plans_unreflected`, a totally
  different subsystem reading the git-log trailer) is real and does read the
  field -- so the self-check is satisfied even while the field is invisible
  through the routine browsing path a user would actually use.
- Estado 2026-08-25: no reportado cerrado en ninguna ronda posterior leída
  — tratar como abierto salvo re-verificación.

### Byte-exact checklist-text matching breaks on invisible, everyday variance (checklist-gate.py)
- Pattern: a gate compares two human-authored strings for EXACT equality (`.strip()` only, no Unicode normalization, no dash/dedup tie-break) where one side is model-generated text and the other is a config file the model is told to reproduce "verbatim"
- Three independent triggers, same root cause, all reproduced against the real hook: NFC vs NFD Unicode normalization, em-dash "—" typed/rendered as a plain hyphen (12 of 19 real checklist boxes use "—"), and a duplicate-subject task pair whose "last write wins" outcome depends on lexicographic (not numeric) filename sort.
- Root: `hooks/checklist-gate.py::_read_board_tasks()` (line ~111) and `_violations()` (line ~125)
- Status 2026-08-24: all 3 triggers above are DEAD -- `lib/checklist_state.py::normalize_box_text()` (NFC + dash-fold + whitespace-collapse) plus `_read_board_tasks()` collecting every status per normalized subject in a list (no dict-overwrite) close all three, re-verified live with the exact same recipes. One axis the fix still misses, found the SAME round: it does NOT casefold, so a completed task whose subject differs from the box only by letter case is still reported "missing" — same failure shape, one variance axis short, still OPEN as of 2026-08-24 (⚠️ DÉBIL verdict, not blocking). Re-check for MORE missed variance axes (NBSP, ZWJ, smart quotes) if this surface gets attacked again.

### Message emitted is decoupled from what actually got persisted (skill-checklist-inject.py)
- Pattern: a hook computes an outbound instruction/promise from a FRESH read of its own inputs, but the persistence step that's supposed to back that promise can silently no-op (write failure, or idempotency short-circuit on a second call) — and the instruction is still emitted unconditionally regardless
- Two real triggers: (1) `session-checklists/` dir unwritable → `_record_skill_load` warns and returns, but `main()` still emits the "will block" promise unconditionally — the Stop hook then genuinely stays silent forever for that box. (2) same skill reloaded with an EDITED manifest → idempotency guard keeps the OLD boxes in the registry, but the emitted message still shows the NEW text — the Stop gate only ever checks for the stale box no longer shown to the model.
- Both T2 (fail-open is intentional, no crash, no infinite block) but both defeat the ONE thing this feature exists to guarantee (M-119: don't depend on the model's obedience).
- Status 2026-08-24: both DEAD -- re-verified live with the exact recipes. `_record_skill_load()` now returns an `enforced` bool threaded into `_build_context_message()`, which emits the softer "will NOT be able to enforce" NOTE instead of the block promise when the write failed; the hot-edit case now emits the FIRST-loaded box list verbatim on a second same-session load, never the fresh manifest text.
- Root: `hooks/skill-checklist-inject.py::main()`, `_record_skill_load()`.

## Sistema actual — infraestructura (`git_helpers.py`, `bin/release.py`+helpers, `managed_blocks.py`, `upgrade_check.py`, `session-start-crew.py`, `git-memory-log.py`, `pre-merge-gate.py`)

### Hard link defeats "anti-symlink" guards on both Windows and POSIX (git_helpers.open_no_follow_symlink)
- Pattern: os.path.islink() (Windows) and O_NOFOLLOW (POSIX) only detect symbolic links -- a hard link
  (os.link(target, victim_path)) is indistinguishable from an ordinary file to both mechanisms, since it
  is not a reparse point and shares the same inode/file-record as the target.
- Demonstrated live (real filesystem, no mocking) on Windows: os.link(sensitive, 'boot-log-latest.txt')
  then git_helpers.open_no_follow_symlink(path, 'w') succeeds with NO OSError, and the write lands on the
  hard-linked sensitive file's shared data -- confirmed content overwritten.
- Read-side (SEC-MED-02) equally bypassed: hard-linking glossary-cache.json to attacker-controlled
  JSON, open_no_follow_symlink(path, 'r') returns the attacker's content with no rejection.
- Threat-model caveat (do not overclaim): git checkout cannot materialize a hard link (only blob content or
  a symlink-target string), so this bypass is NOT reachable via "clone a malicious repo, do nothing else".
  It requires the attacker to already have local write access to the runtime dir before the guarded write
  runs -- a different, adjacent threat model. Also true of the original pre-Windows-fix POSIX O_NOFOLLOW
  code -- not a regression introduced by this patch.
- Root: lib/git_helpers.py:167 (`_open_no_follow_symlink_windows`, current file has it at line 510) and its
  twin lib/_symlink_safe_open.py -- neither os.path.islink() nor the lstat/fstat (st_dev, st_ino)
  TOCTOU comparison can ever flag a hard link, because a hard link's identity IS the target's identity by
  design.
- Vigente 2026-08-25 (verificado): `git_helpers.py` sigue teniendo
  `_AtomicWriteNoFollowSymlink`, `open_no_follow_symlink`,
  `_open_no_follow_symlink_windows`, todo el mismo diseño. No re-atacado
  esta pasada, coordenadas de línea aproximadas (el fichero ha crecido a
  1154 líneas).

### UnicodeEncodeError (non-OSError) escapes open_no_follow_symlink and truncates pre-existing content first
- Pattern: write mode opens with O_TRUNC at os.open() time (truncation happens immediately, before any
  write() call). If the payload contains a lone UTF-16 surrogate code point (invalid for strict UTF-8
  encoding), f.write(payload) raises UnicodeEncodeError -- a ValueError subclass, NOT OSError.
- Confirmed live: pre-existing file content is destroyed (0 bytes on disk) by the time the exception
  propagates, since truncation already happened at open().
- Callers throughout the codebase wrap these calls in except OSError expecting ALL guard failures to
  surface that way. UnicodeEncodeError violates that contract and would surface as an unhandled crash at
  any call site that only catches OSError.
- Caveat: no current caller in this codebase feeds attacker-controlled content likely to contain lone
  surrogates -- not demonstrated as reachable from an external input today.

### run_git()'s "real round-trip" test is a false green on this machine (and per its own docstring, most CI) -- vigente, no reverificado
- Formal Round-Trip Sabotage (unmassk-standards §34) executed against `lib/git_helpers.py`'s `run_git()`
  `encoding="utf-8"` kwarg: sabotaged a scratch replica (kwarg removed) under a forced `PYTHONUTF8=0`
  child process -> silent mojibake, returncode 0, NO exception. The REAL production `run_git()` under the
  IDENTICAL forced conditions round-trips correctly -- the guarantee genuinely comes from the explicit
  kwarg, not the ambient env var.
- The TEST that is supposed to prove this ("real round-trip through real git") never forces `PYTHONUTF8=0`
  itself, so it is a false green on any `PYTHONUTF8=1` environment (this dev box; per the sibling test's
  own docstring, "most CI" too) -- it provides ZERO incremental regression protection beyond the sibling
  mock test (`test_run_git_passes_encoding_utf8_and_text_true_to_subprocess`), which IS env-independent.
- Vigente 2026-08-25: `git_helpers.py::run_git()` sigue existiendo (línea
  833 hoy). Nombres exactos de test no re-verificados tras la reescritura
  del módulo — si se re-ataca, confirmar primero que el test sigue
  llamándose igual antes de citarlo.

### Windows Task Scheduler detachment escapes taskkill /T process-tree kill
- Pattern: `taskkill /F /T /PID <pid>` (and any PID-tree-walk kill mechanism) only
  recurses through processes whose stored ParentProcessId chains back to the target
  PID. A grandchild that instead gets its process created via
  `schtasks /Create ... & schtasks /Run` has its own ParentProcessId rooted at the Task
  Scheduler service, NEVER the spawning process — structurally outside any PID-based
  tree.
- Confirmed live on `git_helpers.py`'s `_win32_kill_tree()` (invoked from `run_git()`'s
  TimeoutExpired branch): a fake "git.exe" that registers+runs a one-shot scheduled task
  spawning a real grandchild process, then itself hangs — `run_git(timeout=1)` times out,
  `_win32_kill_tree` fires `taskkill /F /T /PID` against the fake git.exe's own pid, and
  the scheduled-task-spawned grandchild is CONFIRMED STILL ALIVE 5s later via an
  independent `tasklist` query. No exception is raised anywhere.
- Reusable requirement: current user must be able to run `schtasks /Create ... /IT` +
  `/Run` without admin rights or a stored password (confirmed works out of the box on a
  standard Windows 11 user account).
- Vigente 2026-08-25 (verificado): `_win32_kill_tree` sigue en
  `git_helpers.py:770`. No re-atacado esta pasada.

### sanitize_trailer_value() (lib/parsing.py) — historia de saneado de bytes de control, consumidor original retirado
- `lib/parsing.py:126 sanitize_trailer_value()` sigue viva hoy y su propio
  docstring documenta en vivo la historia de blindaje incremental (x1c/x1d/
  x1e → NEL x85 → x1b → x1f → el invariante estructural `\s*` alrededor del
  tag) — verificado 2026-08-25: la clase de bytes de control ASCII/
  line-boundary está completa en el regex actual
  (`r"[\r\n \x0b\x0c\x1b\x1c\x1d\x1e\x1f\x7f\x85]"`).
- **Pero el consumidor que motivó todo ese blindaje ya no existe**: el
  fence `<memory-data>...</memory-data>` que envolvía contenido de recall
  para que el LLM lo tratara como confiable vivía en
  `hooks/user-prompt-memory-check.py`, y ese hook fue reescrito por
  completo (verificado: ya no tiene `recall_relevant`, ni fence, ni
  `token_hex` — hoy solo hace `needs_install()`). Ningún fichero del
  repo actual envuelve contenido en `<memory-data>` (grep confirmado,
  solo aparece dentro de `lib/parsing.py` mismo y de `lib/incidents.py`,
  que llama al saneador genérico sin usar el fence).
- Todos los hallazgos de "falsificación del fence" (bytes Cf invisibles,
  el "decoy" del espacio de sustitución, el nonce A2 fuera del límite de
  confianza) quedan retirados abajo — la lección transferible ya está
  condensada ahí. Lo que SIGUE vigente hoy: `sanitize_trailer_value()`
  como saneador de salida de terminal, usado por `bin/git-memory-log.py`
  (emoji+scope+msg, los tres grupos, verificado línea 130 — antes emoji/
  scope no se saneaban, ver cierre abajo) y `lib/incidents.py`. Un ataque
  fresco a esta pieza hoy debería apuntar a inyección ANSI/terminal, no a
  falsificación de fence — no atacado con ese enfoque esta pasada.

### bin/git-memory-log.py SUBJECT_RE emoji/scope capture groups never sanitized
- Only `sanitize_trailer_value(msg)` used to be applied; the `emoji` and `scope`
  captures from `SUBJECT_RE` were printed RAW via f-string.
- Live PoC 1 (scope): subject with an ANSI escape sequence in the scope capture
  group reached raw stdout, verified via direct byte inspection.
- Live PoC 2 (emoji): a full terminal screen-clear + color sequence reached raw
  stdout untouched.
- **[CERRADO — verificado 2026-08-25]**: `bin/git-memory-log.py:130` hoy
  llama `sanitize_trailer_value()` sobre los TRES grupos (`emoji`, `scope`,
  `msg`), no solo `msg`. El fichero fue reescrito (143 líneas hoy,
  `SUBJECT_RE` distinto — incluye `remember` como tipo). Comentario en el
  propio fichero (línea 129) referencia explícitamente que emoji/scope no
  son texto controlado por atacante ahora — consistente con el cierre.

### Atomic write (mkstemp+os.replace) — silent chmod-preservation failure (2026-07-19)
- Pattern: any "atomic write" that preserves the ORIGINAL file's mode by chmod'ing the temp
  file before `os.replace()`, wrapped in `try: os.chmod(...) except OSError: pass` (best-effort).
- Mock ONLY `os.chmod` to raise for the tmp path (simulates a real FAT32/exFAT/some-NFS mount
  that silently rejects chmod) — the write still succeeds, no exception reaches the caller,
  ZERO output on stdout/stderr, and the file's mode permanently narrows to mkstemp's 0600
  default. Verified independently via a plain `stat` after the fact.
- Root: `lib/git_helpers.py` (`_AtomicWriteNoFollowSymlink.__exit__`, currently around line 166).
- Generalizes: any "best-effort, never block the write" chmod/permission-preservation step is a
  silent-downgrade vector unless it logs on failure.

### Atomic write — lost-update race via concurrent legitimate writer (2026-07-19)
- Pattern: read-diff-write flow (read old content → compute new content → atomic replace) has
  NO lock. Atomicity of the WRITE ITSELF (no partial bytes) does not protect against a
  concurrent writer's content landing AFTER the read but BEFORE the replace — `os.replace()`
  silently discards it, no error, no merge, no warning.
- Repro technique: monkeypatch the wrapper around `open_no_follow_symlink(..., atomic=True)`
  to inject a second, independent `open(path,"w").write()` right after the real open() succeeds
  but before the atomic writer commits.
- Also reproducible trivially in-process: opening TWO `_AtomicWriteNoFollowSymlink` instances on
  the same path before either commits — last `__exit__()` wins, first writer's content vanishes.
- Generalizes: "atomic write" only guarantees no torn bytes for ITS OWN write — never
  linearizability across independent writers of the same file. Any multi-writer file needs this
  named as an accepted risk or closed with a lock, not silently assumed away by the word "atomic".

### Atomic write via os.replace() silently severs hardlinks (2026-07-19)
- Pattern: `os.replace(tmp, path)` swaps `path`'s directory entry to the temp file's OWN inode.
  If `path` was hardlinked to another file, the replace makes `path` point to a NEW, independent
  inode — the sibling hardlink is NOT updated, silently diverges forever, `st_nlink` drops from
  2 to 1 on both sides.
- Repro: `ln fileA fileB` (real hardlink, not symlink) → run the atomic writer on fileA → `stat`
  both files independently → different inode, nlink=1 each, fileB frozen at old content forever.
- Notable because the target codebase's OWN docstring explicitly names a hard-linked-worktrees
  use case it does not intend to break — the framing ("sibling unaffected by construction") is
  true only for content-preservation, not for the sharing relationship itself.

### Orphaned .tmp accumulation on real SIGKILL, no cleanup GC anywhere (2026-07-19)
- A crash mid-write via a real `kill -9` leaves the CLAUDE.md-safe guarantee intact but always
  leaves the `tempfile.mkstemp()` temp file behind. What is NOT disclosed/covered: no stale-tmp
  sweep/GC existed anywhere at the time — 3 repeated real SIGKILLs against the same directory
  left 3 distinct, permanently-accumulating orphan files in the PROJECT ROOT (not gitignored,
  user-visible). 20x normal sequential writes leave zero leak — strictly a crash-only artifact.
- Nota 2026-08-25: `git_helpers.py:126` hoy tiene
  `_sweep_orphaned_atomic_temp_files()` — sugiere que esto pudo cerrarse
  desde entonces. No re-verificado con un SIGKILL real esta pasada; si se
  re-ataca, confirmar en vivo antes de reportar como abierto o cerrado.

### git add does not clear pre-staged index entries (release.py / --allow-dirty)
- Pattern: script uses `git add -- [specific files]` to stage only release files. If the user has
  pre-staged unrelated files before running with --allow-dirty, those files REMAIN in the git
  index and could be included in the commit.
- **[MOOT — verificado 2026-08-25]**: `bin/release.py::_execute_stage()`
  sigue haciendo el mismo `git add -- <3 ficheros>` (sin `git reset`) y su
  propio docstring hoy lo llama a propósito ("No hace git reset: cualquier
  fichero que el usuario tuviera staged antes sigue staged después"), PERO
  el commit ya no es un `git commit` plano: `_execute_commit_push()` ahora
  delega en `lib/memory/notes.write_work()` (el mismo mecanismo de
  pathspec-limitado documentado arriba en "write_work() silent
  cross-writer content misattribution"), que commitea EXACTAMENTE los 3
  paths pasados — ficheros pre-staged de otro tema no entran en el commit
  de release aunque sigan en el índice. El riesgo original ya no aplica
  con este backend; el riesgo relevante hoy es el de `write_work()`
  mismo (sin lock), no el `git add` pre-staged.

### SEMVER_RE / _semver_tuple — leading zeros, pre-release ratchet
- Original findings: `SEMVER_RE` used to accept leading zeros (`1.04.0`), and
  `_semver_tuple` stripped the pre-release suffix before comparison, creating a
  one-way ratchet where a single `X.Y.Z-rc1` release permanently blocked the
  final `X.Y.Z` release.
- **[CERRADO — verificado 2026-08-25]**: hoy vive en
  `bin/release_validators.py`. `SEMVER_RE` es ahora
  `r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[a-zA-Z0-9.]+)?$"` —
  ceros a la izquierda ya rechazados por diseño (semver 2.0.0 §2, según
  su propio comentario). `_semver_key()` implementa la precedencia
  completa de semver 2.0.0 §11 (sin pre-release > con pre-release del
  mismo core, comparación de identificadores numérica vs ASCII) — el
  ratchet ya no existe, `1.4.0 > 1.4.0-rc1` correctamente. Bonus: ya
  incluye una defensa NUEVA no presente en el hallazgo original (issue
  #58: dígitos Unicode no-ASCII como '１２３' ya no toman la rama
  numérica).

### CHANGELOG structural validation — multi-[Unreleased], subsection-only body, wrong order
- Original findings: the promote regex only found the FIRST `[Unreleased]` (a
  second one was silently ignored); a body with only `### Added`/`### Changed`
  subsection headers and no real entries passed the "not empty" check; no
  validation that `[Unreleased]` was the topmost version section.
- **[CERRADO — verificado 2026-08-25]**: hoy vive en
  `bin/release_helpers.py::_check_unreleased_not_empty()`. Comprueba
  explícitamente: (a) exactamente un `[Unreleased]`, muere si hay 0 o 2+;
  (b) que sea la PRIMERA sección de versión (`first_version_match.start()
  != unreleased_pos` → muere); (c) filtra líneas que empiezan por `###`
  antes de decidir si el cuerpo está vacío. Los 3 hallazgos originales
  están cubiertos por checks explícitos y nombrados en el código actual.

### subprocess.TimeoutExpired uncaught in upgrade path
- Original finding: `hooks/user-prompt-memory-check.py`'s `needs_upgrade()`
  install-script subprocess call (timeout=15) had NO try/except, breaking the
  session-level fail-open guarantee if the install ran long.
- **[MOOT/CERRADO — verificado 2026-08-25]**: esa lógica ya no vive en
  `user-prompt-memory-check.py` (su `main()` de hoy no llama a
  `needs_upgrade`/`trigger_auto_upgrade_if_needed` en absoluto, per el
  propio docstring de `lib/upgrade_check.py`). El subprocess vive ahora en
  `lib/upgrade_check.py::trigger_auto_upgrade_if_needed()`, envuelto
  ENTERO en `try: ... except Exception as e: print(..., file=sys.stderr)`
  — un `TimeoutExpired` real quedaría capturado ahí. Cerrado.

### session-start-crew.py: UnicodeDecodeError on non-UTF-8 CLAUDE.md
- Original finding: `claude_md.read_text(encoding='utf-8')` with no try/except —
  a CLAUDE.md with invalid UTF-8 bytes crashed the SessionStart hook.
- **[CERRADO — verificado 2026-08-25]**: `hooks/session-start-crew.py`'s
  `_read_claude_md()` now wraps the read in `except (OSError,
  UnicodeDecodeError):`.

### Content-gate regex assumes "begin present" implies "end present too" / "Trustworthy boundary" splice destroys genuine content between it and the corruption (managed_blocks.py)
- Original findings (issue #63): `upsert_managed_blocks()`'s begin...end regex
  had nothing to match when only the END marker was deleted (a real, ordinary
  edit) — the block silently swallowed into the following block's body,
  reported "up to date" forever. The orphaned-BEGIN repair that followed
  treated EVERYTHING between a dangling BEGIN and the next canonical BEGIN as
  disposable, silently destroying real user content that happened to live in
  that gap (a normal place to write free-text notes).
- **[CERRADO — verificado 2026-08-25]**: `lib/managed_blocks.py`'s current
  `upsert_managed_blocks()` (line 154) has extensive inline comments citing
  "issue #63, Moriarty T1-1 regression on T1-A's own fix" and fixes BOTH
  halves: (a) when a block IS present but stale, the previous body between
  the markers is captured BEFORE being overwritten and, if it differs from
  canonical, embedded VERBATIM in the log line ("recovered verbatim here:
  ..."), never silently discarded; (b) the orphaned-BEGIN repair now removes
  EXACTLY the single dangling BEGIN line (`content.find("\n", start)`),
  never a range up to the next block — provably safe regardless of what sits
  before/after it, by construction, not just "in this case".

### needs_upgrade() Check 1 ("Context Checkpoint Commits" in block) permanently, unconditionally True — dead conditional gate
- Original finding: the literal string never existed in real production
  content (only test fixtures faked it), so a genuinely canonical, fresh
  install still tripped the upgrade subprocess on every session.
- **[CERRADO — verificado 2026-08-25]**: `lib/upgrade_check.py::
  needs_upgrade()`'s own docstring cites "Decision 1d623da / Moriarty T1-B
  (issue #63)" by name and confirms the fix: Check 1 now reuses
  `managed_blocks.any_block_outdated()` (a real comparison against canonical
  render), never a hand-typed magic string.

### Two "is this current" oracles that use different comparison semantics silently disagree
- Original finding: `boot_health.py::check_version_mismatch()` used raw string
  inequality (`!=`) while `upgrade_check.py::needs_upgrade()` used numeric
  semver `<` on the SAME manifest field — a downgrade/rollback scenario made
  the string-inequality oracle print a false "update available" message the
  authoritative oracle already knew was wrong.
- **[MOOT — verificado 2026-08-25]**: `check_version_mismatch()` ya no
  existe. `lib/boot_health.py`'s own surviving docstring: "2026-08-05: the v1
  boot chain... was deleted... check_version_mismatch()... had zero
  remaining callers once the v1 chain was gone, so it was removed." Solo
  queda UN oráculo hoy (`needs_upgrade()`), no hay con qué discrepar.

### pre-merge-gate.py: # merge-reviewed string bypasses gate unconditionally
- Original finding: `if '# merge-reviewed' in command:` — any command
  containing that literal substring (in a comment, in a string) bypassed the
  review gate unconditionally.
- **[MECANISMO RETIRADO — verificado 2026-08-25]**: el fichero fue
  reescrito por completo. Hoy no existe ningún `'# merge-reviewed'`
  literal (grep confirmado) — el mecanismo es ahora
  `_normalize()`/`_extract_positional_args()`/`_current_branch()`/
  `_upstream_branch()`/`_is_same_branch_exempt()`, una comprobación real
  de si el merge/pull objetivo es la MISMA rama actual, no un string
  mágico. El hallazgo original no aplica al código de hoy — hace falta
  una ronda nueva contra el mecanismo actual si se quiere atacar esta
  pieza, no re-verificado esta pasada.

## Retirado — sistema de memoria v1 (borrado 2026-08-05, commit `615f5cc`)

Los siguientes ficheros ya no existen en el repo (confirmado con `find` +
`git log --diff-filter=D`, 2026-08-25): `lib/boot_git_checks.py`,
`lib/boot_memory.py`, `lib/boot_render.py`, `lib/bootstrap_commits.py`,
`lib/recall.py`, `lib/date_parsing.py`, `hooks/precompact-snapshot.py`,
`hooks/session-start-boot.py`, `hooks/pre-validate-commit-trailers.py`,
`hooks/post-validate-commit-trailers.py`, `hooks/pre-memory-dedup-gate.py`,
`hooks/pre-task-recall.py`, `hooks/stop-dod-gate.py` +
`lib/dod_gate_classify.py`, `bin/git-memory-gc.py`,
`bin/git-memory-bootstrap.py`, `bin/git-memory-commit.py`,
`bin/git-memory-uninstall.py`. No volver a atacarlos — no hay nada ahí que
atacar. Detalle completo (rondas issue #49/#55/#57/#59/#60/#63, PoCs,
file:line originales) en `round-history.md` y `docs/deprecated/`. Lo único
que sobrevive de esa era, condensado a la lección transferible:

- **Una etiqueta de estado ("fresh"/"synced") no vale más que la evidencia
  que la sostiene**: subir la fuerza epistémica de una palabra sin añadir
  evidencia nueva es en sí mismo la superficie de ataque — pasó tres veces
  seguidas en el saga de boot freshness (mtime de FETCH_HEAD, luego un
  sello identificado solo por alias local, luego `get-url` cayendo al
  alias cuando la URL está vacía).
- **Enumerar una clase de bytes de control nunca se cierra incrementando
  uno a uno**: x1c/x1d/x1e → NEL → x1b → x1f, y aun así quedó fuera toda
  la categoría Unicode Cf (zero-width/invisible-format) — una familia
  semántica distinta que ninguna lista incremental de bytes ASCII cubre.
  Comprobar la familia completa de una vez, no bug a bug (lección que SÍ
  se aplicó al cerrar `sanitize_trailer_value()`, ver arriba).
- **Sustituir un byte de control por un ESPACIO deja un delimitador
  casi-idéntico ("decoy")** en vez de eliminarlo — la estrategia de
  reemplazo en sí era el fallo, no la lista de bytes.
- **Un nonce/entropía puesto junto al límite de confianza pero no DENTRO
  de él** no aporta ninguna defensa real contra la falsificación del
  límite mismo (A2 token-fence, issue #59).
- **Una puerta de confianza que mira "¿el sello dice que está al día?"
  antes de comprobar "¿existe siquiera lo que el sello promete?"** se
  puede saltar fabricando solo el sello.
- **`OverflowError` no es `ValueError`/`OSError`**: un except acotado que
  parece exhaustivo puede dejar fuera una excepción real de una librería
  estándar (`datetime.fromtimestamp` en fechas fuera de rango).
- **Un separador de campo/registro inyectado en un campo NO-final de una
  plantilla `git log --pretty=format:...`** desplaza los campos
  siguientes aunque el diseño solo proteja explícitamente "el último
  campo" — cualquier otro campo igual de controlable necesita el mismo
  tratamiento.
