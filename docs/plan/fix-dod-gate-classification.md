# stop-dod-gate: clasificar rojo intencionado vs rojo real

[2026-08-23] Superseded: the gate was retired by the owner; see D-046.

**Status: COMPLETED** (2026-08-20)

**Issue:** — (trunk, sin issue; una sesión)
**Branch:** main (repo_type: trunk)
**Triage:** Standard · **Seam:** SÍ (fichero de estado escrito y releído entre turnos)
**Build mode:** test-first
**Created:** 2026-08-20

## Goal
Que el hook de Stop distinga el rojo deliberado del test-first (contrato en disco, módulo por escribir; suite vacía) del rojo real, para dejar de facturar tokens en cada parada del orquestador — sin dejar pasar jamás un rojo de verdad al cierre.

## Decisiones (bloqueadas con el usuario)
- **D1** — exit 2 por import de primera parte: no bloquear SOLO si el fuente está ausente del disco **y** ausente de git HEAD (nunca se escribió). Presente en disco pero revienta al importar → bloquea (rotura real). Ausente del disco pero trackeado en HEAD → borrado → bloquea. (opción 1 + remache git)
- **D2** — ante duda de clasificación → **bloquea**. El fail-open se reserva para no poder *ejecutar* pytest, nunca para no saber *interpretar* un exit no-cero.
- **D3** — estado (firma + avisos) en `.claude/.unmassk/stop-dod-gate-state.json`, escritura atómica, **no fatal** si no se puede escribir (la dedup se degrada, nunca rompe).
- **D4** — primera parte = señal de filesystem (`<cwd>/<seg>/`, `<seg>.py`, `src/<seg>/`) + git, no metadata de pyproject.
- **D5** — firma del anti-goteo keyeada por `session_id` (del evento Stop): salida completa una vez por sesión y por firma; repetición dentro de la sesión → recordatorio de una línea.
- **D6** (decidida a mitad de obra, no estaba aquí al arrancar) — "primera parte" se reconoce por la identidad declarada del proyecto (`[project].name` en pyproject, poetry, `packages`/`find` de setuptools, `setup.cfg`) o, en su defecto, por el layout en disco/git — no por metadata de pyproject a secas como decía D4. Coste aceptado a propósito: un proyecto que no declara su nombre en ningún sitio de esos sigue bloqueando ante un módulo top-level nuevo hasta que el fichero exista (memoria: `D-042`, decisión `X-064` — seguir bloqueando ese caso en vez de ampliar la heurística).

## Árbol de decisión (exit code de test_command)
- **0** → permite (igual que hoy).
- **5** (suite vacía) → permite; aviso informativo una vez por sesión.
- **1** (tests ejecutan y fallan) → bloquea.
- **2** (error de colección):
  - Parsear `No module named '(X)'` de stdout+stderr. **Ninguna coincidencia** (sintaxis rota en el test, otra causa) → bloquea.
  - Por cada módulo faltante `X`, `seg = X.split('.')[0]`:
    - **¿primera parte?** dir `<cwd>/<seg>/` | `<cwd>/<seg>.py` | `<cwd>/src/<seg>/` en disco, **o** algo bajo esos paths trackeado en git HEAD.
    - **No primera parte** (tercero/desconocido) → bloquea.
    - **Primera parte** → localizar el fuente del `X` dotted concreto:
      - presente en disco → bloquea (rotura real: existe pero no importa).
      - ausente en disco **y** trackeado en HEAD → bloquea (borrado).
      - ausente en disco **y** no trackeado → **permite** (test-first en vuelo; aviso una vez por módulo/sesión).
  - Si TODOS los módulos faltantes son "permite", no bloquea; si al menos uno bloquea, bloquea.
- Cualquier otro exit no-cero → bloquea (comportamiento actual).

## Anti-goteo (dedup por firma)
- Al decidir **bloquear**: firma = sha256 del conjunto ordenado de líneas `FAILED…`/`ERROR…`/`E   …` + exit_code, keyeada por `session_id`.
- Firma == última bloqueada de esta sesión → razón de una línea (sin volcar la salida). Firma nueva → razón completa (como hoy) y se guarda.
- Se preserva el contrato: siempre exit 0, fail-open ante error de infra, `shell=False`, timeout 60s.

## Tareas

### Task 1 — Contrato de aceptación (Dante)
**Files:** `unmassk-toolkit/tests/test_stop_dod_gate.py` (nueva clase)
**Modo:** test-first — estos tests FALLAN contra el hook actual (que bloquea todo no-cero).
- [x] Casos con pytest REAL (no `python -c` simulando exit) contra fixtures en `tmp_path`:
  - exit 5 (suite vacía) → permite
  - exit 2 submódulo primera parte, paquete padre en disco, submódulo ausente + no trackeado → permite
  - exit 2 primera parte presente en disco pero import roto → bloquea
  - exit 2 primera parte ausente del disco pero trackeado en git → bloquea (fixture: git init + commit + borrar)
  - exit 2 tercero (import de paquete inexistente no-repo) → bloquea
  - exit 1 (fallo de aserción real) → bloquea
  - dedup: dos bloqueos misma firma/sesión → 2º es one-liner; firma cambiada → salida completa
- [x] Verificar: la clase nueva falla contra el hook actual.

### Task 2 — Implementación (Ultron)
**Files:** `unmassk-toolkit/hooks/stop-dod-gate.py`, `unmassk-toolkit/lib/dod_gate_classify.py` (nuevo), `unmassk-toolkit/lib/git_helpers.py` (helper `git_tracked_status`, tri-estado — no `is_tracked_in_head` como se sketcheó aquí: devuelve "tracked"/"untracked"/"unknown", nunca colapsa un fallo de git en "seguro para permitir")
**Depends on:** Task 1
- [x] Helper de git-tracked sobre `run_git`, nunca subprocess crudo; tri-estado, nunca lanza.
- [x] Parser del exit code + módulos faltantes; detección primera parte (disco+git); árbol D1/D2/D6.
- [x] Estado atómico en `.claude/.unmassk/` (D3), keyeado por `session_id` (D5), leyendo stdin.
- [x] Verificado: `test_stop_dod_gate.py` + `test_dod_gate_classify.py` — 69 tests en verde.

## Verify (Step 5)
Cerberus + Argus ∥ → Ultron fix → Dante hardening + round-trip del fichero de estado (seam) → Moriarty (sabotaje round-trip) → fixes → Yoda (regla de evidencia round-trip).

## Wave Map
- Wave 1: Task 1 (Dante)
- Wave 2: Task 2 (Ultron), tras contrato en rojo
