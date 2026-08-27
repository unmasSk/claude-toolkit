# Resilience — Attacks That Held

## Cómo leer este fichero
Compactado 2026-08-25, mismo criterio que `attack-patterns.md`: sistema
actual primero (verificado contra el código real, no contra lo
recordado), sistema v1 retirado al final (borrado entero en `615f5cc`,
2026-08-05 — ver `lib/boot_health.py`'s propio docstring superviviente).
El detalle completo de la era retirada sigue en `round-history.md` y
`docs/deprecated/`.

## unmassk-trading (plugin nuevo, 2026-08-27) — lo que aguantó

### price_check.py — no encontré nada, y lo intenté por 5 vías
- Red real contra Kraken y Binance: OK, spread 0.42 bps, edades correctas.
- Cero venues (par inventado `ZZZ/EUR`): verdict `SINGLE_SOURCE`, salida 5, y el campo `reason` dice literalmente "no venue answered with a usable price" — la trampa que SKILL.md avisa está realmente cubierta.
- Contrato de códigos de salida 0/3/4/5 (+2 de argparse) exacto; el 2 reservado a argparse a propósito.
- `spread_bps` sale a precisión completa como string, nunca redondeado a 0; `_spread_bps` devuelve None (no 0) si falta un precio.
- Única prosa falsa: SKILL.md dice que `BTCUSDT` "se parte como BTCU/SDT y el venue lo rechaza por nombre" — no: partir y volver a concatenar es un no-op para la URL y los dos venues contestaron OK. Error inofensivo en dirección segura.

### Los dos gates — fail-loud donde importa
- Salida documentada = salida real: breaker sin `--account-size` y gate sin `--answers-file` salen 2 sin comprobar nada; `HALTED` y `NO_GO` salen 0 sin `--fail-on-non-go`. Los tres avisos de SKILL.md son exactos.
- YAML de tesis corrupto, `thesis_id` duplicado, `--state-dir` que es un fichero -> warnings + `PARTIAL` + `HALTED`. La ausencia NUNCA se convierte en pase en el breaker por esa vía.
- Sin `jsonschema` instalado (python3 del sistema): ambos gates dan su veredicto normal, y el fallo de enlace con la tesis aparece como razón explícita `Could not load trader-memory-core link_report`.
- Salida documentada del sizer (`0.00110692 shares / $74.74 / $5.00 (1.0%)`) reproducida byte a byte con la llamada exacta de SKILL.md.
- Estrés: 20.000 candidatos (7,7 MB) en 0,35 s; YAML anidado 5.000 niveles -> `Error: maximum recursion depth exceeded`, salida 1, sin traza. 645 tests en verde sin dejar ficheros sueltos.

## Sistema actual — memoria v2 (`lib/memory/*`, `hooks/customs.py`, `hooks/checklist-gate.py`, `hooks/skill-checklist-inject.py`, `bin/memory/*`)

### lib/memory/ 13-module round (memoria-v2, 2026-08-02) -- what held
- indexes.py: concurrent insert()-vs-insert() (20 real parallel OS processes, append-mode,
  no locking) -- 0 losses, 0 corrupted lines, POSIX O_APPEND small-write atomicity holds.
- format.py: 2M-char description with 500k embedded newlines (pathological _fold/_fold_raw
  stress) round-trips byte-identical in <0.1s; pathological escaped-comma/backslash Keys
  list (20k repeats) round-trips correctly via _encode_list/_decode_list in <5ms.
- format.py: archive-line headline containing the literal arrow separator AND a fake
  destination-vocabulary phrase inline ("rename x → closed: fake dest...") -- parse_archive_line
  correctly recovers the real headline and real trailing destination, not fooled by the decoy.
- format.py: parse_message on a genuinely hand-corrupted blank line mid-body -- correctly
  returns None (fail-safe), does not silently misparse.
- gitcmd.py: file_lock() reentrant same-thread/same-path correctly raises
  LockNotReentrantError instead of deadlocking; atomic_write() 8-way concurrent writers on the
  same path -- always exactly one writer's full payload, never interleaved/corrupted.
  commit() with empty paths tuple correctly raises ValueError instead of silently committing
  the whole index.
- config.py: customs_enabled=1 (int, not bool) correctly rejected as corrupt (fail-loud, no
  silent bool() coercion); partial config.json (customs_enabled only) still fails closed to
  repo_type="gitflow" by omission, exactly as documented.
- validator.py: validate_replacement() correctly ignores a cross-zone near-duplicate note
  passed in an unfiltered existing_in_zone tuple; empty existing_in_zone correctly yields no
  rejection (pure function trusts its input by design, not a bug).

Verdict this round: FALLA (indexes.py insert/remove lost-update race, T1, see
attack-patterns.md — status not re-verified since).

### notes.py write() held: real multiprocess concurrency, reader/writer overlap, scale
- 8 REAL separate OS processes (not threads) calling `notes.write()` concurrently
  on the same repo: 8/8 distinct ids, 8/8 index lines present, 8/8 new records in
  history, no hang, no lost update -- the `.git/memory-notes` global flock
  genuinely serializes across processes, not just in-process threads.
- Concurrent reader (`query.by_zone`, 40 polls) running throughout 6 concurrent
  real-process writers: monotonic, never torn, never an exception.
- 400 real sequential history entries: by_id/by_word/by_zone all under 30ms.
- Huge single note (headline WITH embedded newlines/blank lines + ~120KB
  description with 5000 embedded blank-line paragraph breaks) round-trips byte-
  exact through write()->query.by_id() in <50ms.
- `notes.write()` called with process cwd inside a nested subdirectory of the
  repo -- held.
- `discard_alternatives(decision, (), ctx)` (zero alternatives) -- held.
- Persistent (non-transient, 3/3 attempts) git-log failure in query.py -- held,
  raises RuntimeError with the real stderr, never silently returns empty/None.

### lib/memory/gitcmd.py -- file_lock() holds across case-insensitive-filesystem path aliasing (memoria-v2, 2026-08-02)
- Two threads locking the SAME real file via two DIFFERENT-case path strings on a
  real case-insensitive-preserving filesystem (default macOS APFS) -- 20-thread
  concurrent read-increment-write, half via each casing, final counter == n_writers
  exactly, 0 losses. Root cause it does NOT hit: `os.open(..., O_CREAT)` on a
  case-insensitive filesystem resolves the differently-cased lock-file name to the
  SAME inode, so the real OS-level exclusive lock ends up shared correctly
  regardless of case.

### lib/memory/gitcmd.py -- commit()'s own --cleanup=verbatim claim verified true
- Docstring claims default git cleanup (strip) would delete the single-space
  blank-continuation line format.py's folding scheme depends on, and that
  --cleanup=verbatim preserves it. Verified empirically against a real repo,
  real commit, real re-read: the single-space line survives byte-for-byte with
  --cleanup=verbatim -- DECEPTION-phase check came back SÓLIDO, not HUMO.

### lib/memory/gitcmd.py -- concurrent commit() calls on the SAME repo (real race, no artificial cwd interference)
- Two real threads, same repo, each calling commit() on its own distinct staged
  file simultaneously -- the loser gets a real, non-empty, full stderr from the
  underlying tool's own index.lock contention, the winner succeeds, the log
  shows exactly one commit, zero duplication/corruption. Confirms the
  "stderr never empty" contract generalizes beyond the single documented
  pathspec-missing test case for THIS failure shape (contrast: the ambient-cwd-
  race failure shape in attack-patterns.md does NOT generalize -- different
  shape, closed for production callers separately).

### capa 2/3 re-attack, closures confirmed live (2026-08-03)
- `gitcmd.commit()` ambient-cwd race (prior T1): CLOSED for production. Re-ran
  the same 2-thread ambient-`os.chdir()`-flip PoC with an explicit `cwd=`
  argument (the only way any real production caller invokes it now -- verified
  `notes_commit.py:195` is the sole production caller and always passes
  `cwd=root`) -- the victim commit lands in the correct repo every time.
- `rejection.build()` value-emptiness (prior T1): CLOSED. `build(kind='x',
  what='', options=(), command=())` now raises `ValueError`.
- SIGKILL between `indexes.insert()` (durable) and the commit step in
  `notes.write()` (prior T1): the underlying gap is structurally unavoidable
  (confirmed again via `os.fork()` + `os.kill(SIGKILL)`) -- BUT the silent-
  failure half is CLOSED: `health.coherence()` now independently detects the
  orphaned index line by name, surfaces it live in `boot.py`'s real AVISOS
  banner, and `bin/memory/reindex.py` (no `--verify`) repairs it cleanly.
- `notes.write()` under real 2-process near-simultaneous concurrency (via the
  real `bin/memory/note.py` CLI): 15/15 trials both land cleanly, zero loud
  failures, zero silent loss.

### rule+rule concurrency (I-003 fix, 2026-08-23) -- lock holds
- 8 real concurrent `bin/memory/rule.py` processes, same repo, same
  `.git/memory-rules` lock: exactly the right commits landed, no lost rule,
  correct near-duplicate rejections under real contention.
- `_TEXT_MAX_CHARS` boundary is byte-exact: 200 chars accepted, 201 rejected.
- Read-only `.git` (chmod -w) fails loud with a single clean `[Errno 13]` line
  to stderr, no traceback, no partial write.
- **`health.coherence_rules()`** — reconfirmed live 2026-08-25 (D-056 round)
  after a clean `rule.py --retract` call: `(1, 1, ())`. It WAS resurrected
  2026-08-06 and is live today, after being retired earlier — see
  round-history.md's I-003 rounds for the full back-and-forth. This function
  covers `rules.md` the same way `health.coherence()` covers `notes.py`'s
  index/git drift.
- SIGKILL gap for `rules.py::add()` (the write-then-commit gap, same shape
  as `notes.py`'s): CONFIRMED STILL ALIVE as of the 2026-08-23 I-003
  re-attack round -- the write itself is structurally uncatchable (same as
  `notes.py`'s), and unlike `notes.py`, no independent detector closes the
  silent half for `rules.md` (`health.coherence_rules()` above only catches
  drift it's asked to check, it does not make the underlying gap disappear).
  See `attack-patterns.md`'s "SIGKILL mid-transaction" entry.

### rules.py retract()/replace() atomic write+commit-or-restore (2026-08-25, D-056 round)
- A REAL failing `pre-commit` git hook (forces `git commit` to fail) installed
  in a disposable scratch repo, never the test code itself (round-trip
  sabotage on a copy, per unmassk-standards §34) — both `bin/memory/rule.py
  --retract` and `... --replaces` correctly restore `rules.md` to
  byte-identical prior content and leave `git status --porcelain` clean,
  verified through an independent channel (`cat`+`git log`+`git status`,
  never the writer's own return value) — no orphan commit, no partial line,
  no drift between file and HEAD.

### checklist-gate.py / skill-checklist-inject.py / checklist_state.py (2026-08-24)
- 4 real concurrent `checklist-gate.py` processes on the same session/registry
  → exactly `_MAX_BLOCKS_PER_SESSION` (2) blocked, the other 2 correctly saw
  the cap and allowed-with-warning, `block_count` landed at exactly 2 on disk
  — no lost update, no over-increment.
- Symlinked `.claude` pointing OUTSIDE the project root → rejected before any
  write; nothing landed outside or inside the symlinked dir; hook still
  fail-opened cleanly, exit 0.
- Hostile `CLAUDE_CODE_TASK_LIST_ID` (`"../../../../../../etc"`) → rejected by
  `is_safe_path_component`; board dir resolves to `None`; fails open.
- Stress: a 190MB syntactically-broken task JSON file, a 150MB syntactically-
  valid one, a 20,000-file task board, and a 200,000-box checklist manifest
  all processed in well under 1s each — no size cap needed at this scale.

## Sistema actual — infraestructura (`git_helpers.py`, `bin/release.py`+helpers)

### git_helpers.open_no_follow_symlink Windows guard (2026-07-06)
- Real Windows box, real git-checkout-style symlink threat (islink() mocked True): both twins raise OSError
  BEFORE os.open() is ever called -- 0 open_calls observed, file content untouched.
- TOCTOU lstat/fstat identity mismatch (mocked st_ino divergence): OSError raised, fd opened then closed
  before returning -- no leaked fd, no fd handed to caller.
- Twin parity: git_helpers._open_no_follow_symlink_windows and _symlink_safe_open's copy are byte-identical
  in logic -- no divergence found despite deliberate attempt to diff them.
- POSIX branch: git diff confirms the O_NOFOLLOW/O_CREAT/O_TRUNC/O_APPEND lines are 100% untouched by this
  patch.
- Directory planted at the target path: Windows os.open() in read mode raises PermissionError -- fails
  closed, no crash, no silent success.
- Nonexistent path in read mode: FileNotFoundError -- expected, no AttributeError.
- run_git(): mocked subprocess.run raising UnicodeDecodeError -> caught by except (..., ValueError) ->
  returns (1, "") as documented, no crash escapes.
- ensure_gitignore() idempotency: called twice on a fresh .gitignore -- entry appears exactly once.
- Concurrent writers (8 threads, same brand-new path): all 8 succeed, final file content is one writer's
  full payload with zero interleaving/corruption.
- Encoding round-trip (accents + commit emojis): payload written once, reread compared against the SAME
  variable -- genuine round-trip. On disk the bytes are CRLF-translated (not literally "byte for byte" as
  a test docstring once claimed), but the str-level round-trip the code actually needs holds correctly.
- 5.8M-character payload round-trips correctly in 0.06s -- no stress ceiling hit.
- PYTHONUTF8=0 subprocess round-trip: both twins still round-trip correctly.

### git_helpers.run_git() encoding="utf-8" kwarg -- formal Round-Trip Sabotage (2026-07-06)
- Real commit with accents+emoji subject, ground truth confirmed via an INDEPENDENT channel (raw bytes
  captured without text=/encoding=, manually decoded) -- git's own stdout bytes are valid, well-formed
  UTF-8; the failure mode lives entirely in Python's decode step, never in git itself.
- Sabotaged the REAL dependency (scratch replica with encoding="utf-8" removed, forced PYTHONUTF8=0) ->
  silent mojibake, returncode 0, NO exception raised.
- REAL production git_helpers.run_git under the IDENTICAL forced conditions round-trips the commit subject
  correctly byte-for-byte -- the guarantee genuinely comes from the explicit encoding="utf-8" kwarg.
- SEAM VERDICT: run_git()'s encoding="utf-8" kwarg itself AGUANTA the sabotage.
- Caveat (see attack-patterns.md): the round-trip TEST itself never forces PYTHONUTF8=0, so it's a false
  green on any PYTHONUTF8=1 environment -- the kwarg holds, the test proving it doesn't exercise the risk
  condition. Regression protection for a literal kwarg deletion still exists via the sibling mock test.

### F6 hard-link reject guard (issue #53) — held under real adversarial pressure (2026-07-09)
`open_no_follow_symlink(..., reject_hardlinks=True)` and its fallback twin — confirmed still present in
current `git_helpers.py` (`reject_hardlinks` param + `st_nlink` check, verified 2026-08-25). 8 real PoCs,
0 breaks, as of the original round:
- Monkeypatch-injected TOCTOU race (attacker's `os.link()` fired exactly inside the
  `os.path.exists()` → `os.open()` window on a brand-new path) still gets caught: the
  `os.fstat(fd).st_nlink > 1` check is unconditional post-open.
- Real 500-iteration multi-threaded race — 0 bypasses, victim content untouched.
- §34 end-to-end sabotage against all 3 real production call sites of that era (`write_boot_log()`,
  `_write_glossary_cache()`, `_read_glossary_cache()` -- NOTE: these 3 call sites belonged to the v1 boot
  chain and no longer exist; the guard mechanism itself in git_helpers.py is what's being reconfirmed
  current, not these specific callers).
- 2000-iteration hammering of the rejection path — handle count verified via independent PowerShell
  `Get-Process ... HandleCount` — delta 0.
- `mode="a"` + `reject_hardlinks=True` — correctly rejected on both twins.
- `st_nlink=3` (two extra links) — `>1` threshold generalizes, twin parity holds.
- Not re-attacked this compaction pass; mechanism confirmed present, behavior not re-verified live.

### Atomic write (git_helpers._AtomicWriteNoFollowSymlink, 2026-07-19)
- fsync() failure and os.replace() failure (mocked at that single call each) both correctly
  propagate OSError, clean up the temp file (zero orphan), and leave the original content
  byte-identical — verified via independent post-hoc read/listdir.
- Symlink planted at the destination path is correctly rejected pre-write (islink() check
  before any temp file is even created); the external symlink target is never touched.
- 8-way concurrent OS processes writing the same path simultaneously: never a torn/mixed/partial
  result — os.replace()'s atomicity holds under real concurrency.
- A reader polling the file continuously throughout an in-flight write never observes a
  partial/torn read — always a complete old-or-new snapshot.
- `close()` called directly after a normal `with`-block commit is a true no-op.
- Zero-byte write (caller writes nothing) legitimately empties the file — correct, not a bug.

### release.py path-safety, semver, CHANGELOG, and push-failure handling (2026-06-09)
- Path traversal `../evil` → rejected by PLUGIN_NAME_RE before any filesystem access.
- Uppercase/empty plugin name → rejected by PLUGIN_NAME_RE.
- `UNMASSK_REPO_ROOT` env set to external repo → release.py overrides it with the correct root; victim
  repo not mutated.
- Semver comparisons (1.9.0→1.10.0, 2.0.0>1.99.99, 1.4.0-rc1 vs 1.4.0) — correct.
- Working tree check without --allow-dirty → correctly aborts. No upstream configured → correctly aborts.
  CHANGELOG absent → correctly aborts. CHANGELOG whitespace-only [Unreleased] → correctly aborts.
- Push failure → exits code 2, not 0; local commit preserved; ADVERTENCIA printed.
- Second release same version → rejected as "not greater". Detached HEAD → correctly aborts.
- CRLF CHANGELOG → handled correctly. 10,000-line CHANGELOG → processed in <1s.
- Huge version 99999.99999.99999 → accepted (valid semver).
- Concurrent releases (same version, two threads) → one wins, other fails at git add (index lock);
  final state consistent.
- **Nota 2026-08-25**: el fichero se partió en `bin/release.py` +
  `bin/release_validators.py` + `bin/release_helpers.py`
  (`_semver_tuple`→`_semver_key`, ahora completo semver 2.0.0 §11, ver
  attack-patterns.md) y el backend de commit cambió de `git commit` plano
  a `lib/memory/notes.write_work()` (ver attack-patterns.md,
  "write_work() silent cross-writer content misattribution"). Los
  comportamientos de arriba (traversal, semver, CHANGELOG, push-failure)
  no dependen del backend de commit y siguen siendo plausibles hoy, pero
  NO re-atacados en vivo esta pasada — el mecanismo de concurrencia
  específicamente cambió de familia (de `git commit` con index.lock a
  `notes.write_work()`, que tiene su propio hallazgo de colisión sin
  lock documentado en attack-patterns.md) y merece una ronda fresca si se
  vuelve a tocar `release.py`.

### validate-memory-path.py — path traversal guard
- `../traversal` through agent-memory → normpath resolves it out, no trigger.
- `file_path` in another root's agent-memory → correctly blocked.
- **Nota 2026-08-25**: el fichero sigue existiendo hoy
  (`unmassk-toolkit/hooks/validate-memory-path.py`), con el mismo mecanismo
  de `os.path.normpath` (verificado línea 76). No re-atacado esta pasada.

## Retirado — sistema de memoria v1 (borrado 2026-08-05, commit `615f5cc`)

Dos casos especiales, mecanismo muerto aunque el FICHERO sobreviva
(verificado 2026-08-25, no son "file not found"): `hooks/user-prompt-
memory-check.py` ya no inyecta contenido de `recall()` en el prompt —
su `main()` de hoy solo hace `needs_install()`; toda la sección de
resiliencia "recall injection (2026-06-12)" (JSON malformado, stdin
binario, prompts gigantes, determinismo de empates, etc.) documentaba
esa vía muerta. `hooks/session-start-crew.py` sigue vivo pero con función
distinta (ver attack-patterns.md, ya tiene sus propios cierres
verificados) — su entrada en "hooks/bin — adversarial inputs" ("running in
empty repo → exit 0") no se re-verificó contra la versión de hoy, se
descarta sin sustituto explícito por ser de bajo valor. El resto de
`hooks/bin — adversarial inputs (2026-06-12)` (stop-dod-gate,
pre-task-recall, session-start-boot, precompact-snapshot,
git-memory-commit, git-memory-gc) es sobre ficheros borrados, cubierto
por la lista de abajo.

Todo lo que sigue documentaba código que ya no existe: `lib/recall.py`,
`lib/boot_git_checks.py`, `lib/boot_memory.py`, `lib/boot_render.py`,
`lib/bootstrap_commits.py`, `lib/date_parsing.py`,
`hooks/precompact-snapshot.py`, `hooks/session-start-boot.py`,
`hooks/pre-validate-commit-trailers.py`,
`hooks/post-validate-commit-trailers.py`,
`hooks/pre-memory-dedup-gate.py`, `hooks/pre-task-recall.py`,
`hooks/stop-dod-gate.py`, `hooks/stop-close-session.py`,
`bin/git-memory-gc.py`, `bin/git-memory-bootstrap.py`,
`bin/git-memory-commit.py`, `bin/git-memory-uninstall.py` (confirmado
`find`/`git log --diff-filter=D`, 2026-08-25; solo quedan `.pyc` sueltos
de algunos en `__pycache__`). No hay nada ahí que re-verificar. Detalle
completo (recall.py tokenizer/ReDoS resistance, release.py's older shape,
boot freshness issues #49/#57/#59/#60 — fetch timeout+killpg real,
resolución dinámica de remoto, defensa anti-inyección de opciones git,
`get_timeline()`/`get_last_context_time()` degradando a "unknown" en vez
de forjar fecha, issue #55's date-parsing edge cases, F6's 3 call sites
de la era v1) en `round-history.md` y `docs/deprecated/`. Lo único que
sobrevivió intacto a la purga v1→v2 y sigue siendo la misma pieza atacada
arriba: el diseño de `git_helpers.py` (symlink guard, atomic write,
hard-link reject, run_git encoding, win32 kill tree) — no hace falta
repetir esas pruebas, siguen contando.
