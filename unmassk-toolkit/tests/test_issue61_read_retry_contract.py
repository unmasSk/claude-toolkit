"""
Contrato (test-first, Task 1) para issue #61 -- pérdida silenciosa de
memoria en fallo transitorio de `git` en el READ-PATH de producción.

Plan: docs/plan/fix-silent-memory-loss-61.md
Diagnóstico (House): un `git rc!=0` transitorio (ej. exit 128, carga del
runner de CI) colapsa hoy en "resultado vacío" en los lectores de
producción, indistinguible de "no hay memoria genuina" -- pérdida
silenciosa. El único retry que existe hoy vive en los WRAPPERS de test
(`_recall_with_retry` en test_recall.py, análogos en test_drift.py /
test_consolidation_trigger.py) -- nunca en el código de producción.

Decisión ya tomada (commit e9400db, Opción A): retry acotado en el
read-path + WARN visible que distinga fallo-de-git de vacío-genuino; NO
cambiar el tipo de retorno; fail-open (no bloquear arranque/turno).

Sitios cubiertos (los 4 del plan original -- ya en VERDE, ver clases
Test*ReadRetryContract de más abajo):
  1. lib/recall.py                _scan_commits()                (mayor blast radius)
  2. lib/boot_memory.py           extract_glossary()
  3. lib/boot_git_checks.py       get_timeline()
  4. lib/git_helpers.py           commits_since_last_consolidation()

Pasada de ENDURECIMIENTO (test-first, 2ª entrada de Dante -- Ultron ya
implementó, esto fija el comportamiento con tests, código de producción
NO se toca en esta pasada):
  5. lib/boot_memory.py           extract_memory()               (mayor blast radius de los 3 nuevos)
  6. hooks/precompact-snapshot.py extract_memory_from_log()       (fichero con guion, subprocess aislado)
  7. lib/boot_git_checks.py       get_last_context_time()
  8. lib/git_helpers.py           run_git_read_retrying()         (el helper compartido en sí -- SEC-HIGH-001,
                                                                    deadline de reloj + WARN-solo-tras-agotar)

Los tests de los sitios 5-7 siguen las mismas 3 clases A/B/C de arriba,
MÁS dos clases nuevas específicas de esta pasada de endurecimiento:
  D. WARN solo tras agotar (Cerberus, Verify round): un transitorio que
     SE RECUPERA en un intento posterior no debe dejar NINGÚN rastro en
     stderr (ni siquiera la traza del intento fallido) -- si dejara
     rastro, sería una falsa alarma para un fallo que ya se autocuró. Un
     fallo PERSISTENTE debe dejar el WARN EXACTAMENTE una vez (no una vez
     por intento fallido) -- cubierto en un sitio con
     `log_stderr_on_failure` explícito (get_last_context_time) y uno con
     print manual (extract_memory), como pidió el coordinador.
  E. Límite de reloj (SEC-HIGH-001): un intento que agota ~todo el
     presupuesto de READ_RETRY_DEADLINE_SECONDS (simulando un git
     COLGADO, no un rc=128 rápido) no debe disparar un 2º/3er intento --
     el peor caso por sitio debe quedar acotado a ~1x GIT_TIMEOUT, no
     READ_RETRY_ATTEMPTS x GIT_TIMEOUT. Probado tanto a nivel del helper
     compartido `run_git_read_retrying()` (unit, aislado -- ahí vive toda
     la lógica de reloj) como a nivel de sitio (extract_memory(), el de
     mayor blast radius, para probar el cableado real end-to-end).
     Reloj controlado: se reemplaza el NOMBRE `time` ligado en el
     namespace de git_helpers (nunca el módulo `time` real de stdlib) por
     un reloj falso que el run_git_fn de prueba avanza manualmente para
     simular el paso de tiempo que un cuelgue real causaría -- cero
     sleeps de 10s reales.

Cierre de completitud (4ª entrada de Dante, mismo fichero -- Ultron ya
envolvió el sitio, código de producción NO se toca en esta pasada):
  9. lib/bootstrap_commits.py     scan_recent_commits()           (2 llamadas internas -- log %h/%aI/%s/%b
                                                                    y log %h/%an, cada una envuelta por
                                                                    separado con run_git_read_retrying)
     Mismo mecanismo ya endurecido y probado a nivel de helper (sitio 8) --
     aquí solo falta el CABLEADO: que el retry realmente envuelve AMBAS
     llamadas de este sitio en concreto. No se re-testea deadline/WARN
     (ya cubierto genéricamente). `scan_recent_commits()` importa `run_git`
     a nivel de módulo (como recall.py) -> se parchea
     `bootstrap_commits.run_git`. Las dos llamadas comparten `args[0] ==
     "log"` -- se distinguen por el nº de separadores \x1f en su propio
     `--pretty=format:` literal (2 para la 1ª llamada -- %h\x1f%aI\x1f%s,
     1 para la 2ª -- %h\x1f%an), mismo criterio que
     `test_issue61_breadcrumbs.py::TestScanRecentCommitsBreadcrumb` ya usa
     para aislar estos mismos dos sitios.

Por sitio, 3 clases de test (acceptance granularity -- NO el barrido
exhaustivo de branches, ese es el pase de hardening posterior a la
implementación de Ultron):

  A. Retry recupera transitorio + round-trip §34: escribe una entrada de
     memoria REAL (commit real, "producer"), fuerza que la llamada git del
     read-path falle SOLO en el primer intento (rc=128 real, vía un
     directorio roto real -- nunca un rc inventado) y tenga éxito en el
     segundo, y afirma que el lector devuelve el DATO REAL escrito por
     este mismo test, no vacío. HOY debe fallar: no existe ningún bucle de
     reintento en producción, así que la primera (y única) llamada falla y
     el lector devuelve vacío inmediatamente.
     NOTA: esto mismo satisface el punto 4 del contrato ("round-trip") --
     separarlo en dos tests casi idénticos (uno con marcador único, otro
     sin él) sería duplicación sin valor añadido; aquí se fusionan
     deliberadamente en un solo test por sitio.
  B. Fallo persistente => WARN no silencioso: fuerza que TODAS las
     llamadas fallen (no solo la primera) y afirma (a) el valor de retorno
     sigue siendo el fail-safe existente (tipo sin cambios) y (b) aparece
     un WARN reconocible en stderr. Puede que ya esté en VERDE hoy en
     varios sitios -- un round anterior de la misma issue #61 (ver
     test_issue61_breadcrumbs.py) ya añadió breadcrumbs de
     `log_stderr_on_failure=True` / print manual en los 4 sitios. Se deja
     como test de contrato igualmente (candado de regresión explícito,
     documentado en el reporte cuál es cuál).
  C. Control anti-falso-positivo: una llamada que tiene éxito a la
     PRIMERA (rc=0) no debe disparar ningún reintento adicional ni ningún
     WARN -- nunca confundir "no hay memoria" / "éxito normal" con "git
     falló". Debe pasar HOY y seguir pasando después del fix (Ultron no
     puede reintentar en el camino feliz).

Canal de fallo (nunca un rc inventado, unmassk-standards §34): un
directorio real que existe pero no es un repo git en ningún ancestro
-- exactamente el mismo canal que test_issue61_breadcrumbs.py usa para
las 9 llamadas ya cubiertas ahí (rc=128 real de un `git log`/`git
rev-list` real).

Qué nombre parchear (module-level bound name vs. import local diferido,
ver unmassk-toolkit-python-test-conventions.md):
  - recall.py hace `from git_helpers import run_git` a nivel de módulo
    (bound name) -> se parchea `recall.run_git`.
  - boot_git_checks.py / boot_memory.py hacen `from git_helpers import
    run_git` DENTRO de la función (import diferido, resuelto de nuevo en
    cada llamada) -> se parchea `git_helpers.run_git`.
  - git_helpers.py's commits_since_last_consolidation() llama a `run_git`
    definida en el MISMO módulo -> también se parchea `git_helpers.run_git`.
"""

import json
import os
import subprocess
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import recall  # noqa: E402
import git_helpers  # noqa: E402
import boot_memory  # noqa: E402
import boot_git_checks  # noqa: E402
import bootstrap_commits  # noqa: E402

PRECOMPACT_SCRIPT = os.path.join(HOOKS_DIR, "precompact-snapshot.py")


# ── Repo helpers (misma forma que test_issue61_breadcrumbs.py / test_recall.py) ──

def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _commit(repo, subject, trailers=""):
    msg = subject
    if trailers:
        msg = subject + "\n\n" + trailers
    git_cmd(["commit", "--allow-empty", "-m", msg], repo)


def _make_broken_dir(tmp_path, name="not_a_repo"):
    """Directorio real que EXISTE pero no es un repo git en ningún ancestro."""
    broken = tmp_path / name
    broken.mkdir()
    return str(broken)


# ── Dobles de run_git (delegan SIEMPRE a la función real -- nunca reimplementan
#    el print/parseo, para que el breadcrumb/comportamiento asertado sea
#    código de producción ejecutando de verdad) ──────────────────────────────

def _make_flaky_run_git(real_run_git, fail_times, broken_dir, match=None):
    """Doble: las primeras `fail_times` llamadas que cumplan `match(args)`
    (por defecto, TODAS) se redirigen a `broken_dir` (fallo real, rc=128);
    el resto pasa a la función real sin tocar `cwd` (deja que el `cwd`
    ambiente/explícito que ya trae la llamada decida).
    """
    state = {"n": 0}
    _match = match or (lambda args: True)

    def _flaky(args, **kwargs):
        if _match(args):
            state["n"] += 1
            if state["n"] <= fail_times:
                kwargs["cwd"] = broken_dir
        return real_run_git(args, **kwargs)

    return _flaky, state


def _make_always_failing_run_git(real_run_git, broken_dir, match=None):
    _match = match or (lambda args: True)

    def _always_fail(args, **kwargs):
        if _match(args):
            kwargs["cwd"] = broken_dir
        return real_run_git(args, **kwargs)

    return _always_fail


def _make_counting_run_git(real_run_git):
    calls = {}

    def _counting(args, **kwargs):
        key = args[0] if args else ""
        calls[key] = calls.get(key, 0) + 1
        return real_run_git(args, **kwargs)

    return _counting, calls


class _FakeTimeModule:
    """Reemplazo del NOMBRE `time` ligado en el namespace de git_helpers
    (`import time` a nivel de módulo) -- NUNCA toca el módulo `time` real
    de stdlib globalmente. `run_git_read_retrying()` resuelve `time.
    monotonic()`/`time.sleep()` como nombres del namespace de git_helpers
    en el momento de la llamada, así que sustituir SOLO esa referencia
    (`monkeypatch.setattr(git_helpers, "time", fake)`) intercepta el reloj
    únicamente dentro de ese módulo, sin afectar a pytest ni a ningún otro
    código del proceso que use time.monotonic() de verdad.
    """

    def __init__(self, start=0.0):
        self._t = start
        self.sleep_calls = []

    def monotonic(self):
        return self._t

    def sleep(self, seconds):
        self.sleep_calls.append(seconds)  # nunca duerme de verdad

    def advance(self, dt):
        self._t += dt
        return self._t


# ── 1. lib/recall.py -- _scan_commits() (mayor blast radius) ───────────────

class TestScanCommitsReadRetryContract:
    """recall.py hace `from git_helpers import run_git` a nivel de módulo
    -- se parchea `recall.run_git` (bound name), no `git_helpers.run_git`.
    """

    def test_retry_recovers_transient_failure_returns_real_entry_round_trip(
        self, tmp_path, monkeypatch,
    ):
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "\U0001f9ed decision(issue61retry): use X",
            "Decision: use X over Y issue61retrymarker",
        )
        broken = _make_broken_dir(tmp_path)

        real_run_git = recall.run_git
        flaky, state = _make_flaky_run_git(real_run_git, fail_times=1, broken_dir=broken)
        monkeypatch.setattr(recall, "run_git", flaky)

        entries = recall._scan_commits(repo_dir=repo)

        assert any(
            e["kind"] == "Decision" and "issue61retrymarker" in e["text"] for e in entries
        ), (
            f"Un fallo transitorio en el 1er intento (rc=128 real) que se cura "
            f"en el 2o debe devolver la entrada REAL escrita por este mismo "
            f"test via retry acotado, no []. entries={entries!r}, "
            f"llamadas a run_git={state['n']}"
        )

    def test_persistent_failure_emits_warn_not_silent_empty(
        self, tmp_path, monkeypatch, capsys,
    ):
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f9ed decision(issue61retry): use X", "Decision: use X over Y")
        broken = _make_broken_dir(tmp_path)

        real_run_git = recall.run_git
        always_fail = _make_always_failing_run_git(real_run_git, broken)
        monkeypatch.setattr(recall, "run_git", always_fail)

        entries = recall._scan_commits(repo_dir=repo)

        assert entries == [], (
            f"Tras agotar los reintentos, el fail-safe sigue siendo [] "
            f"(tipo de retorno sin cambios) -- se obtuvo {entries!r}"
        )
        captured = capsys.readouterr()
        assert "[git_helpers] git 'log' exited 128" in captured.err, (
            f"Un fallo PERSISTENTE (todos los intentos agotados) debe dejar un "
            f"WARN visible en stderr que distinga 'git falló' de 'vacío "
            f"genuino' -- stderr obtenido: {captured.err!r}"
        )

    def test_genuine_empty_result_no_retry_no_extra_warn(
        self, tmp_path, monkeypatch, capsys,
    ):
        """Control anti-falso-positivo: repo real, sin NINGÚN commit de
        memoria -- rc=0, log_output vacío. No debe disparar reintento
        (una sola llamada a git) ni WARN.
        """
        repo = _make_repo(tmp_path)  # solo el commit "init", sin trailers de memoria

        real_run_git = recall.run_git
        counting, calls = _make_counting_run_git(real_run_git)
        monkeypatch.setattr(recall, "run_git", counting)

        entries = recall._scan_commits(repo_dir=repo)

        assert entries == [], f"Repo sin memoria debe devolver [], se obtuvo {entries!r}"
        assert calls.get("log", 0) == 1, (
            f"Un vacío GENUINO (rc=0, sin resultados) no debe disparar "
            f"reintentos -- se esperaba 1 llamada a 'git log', se hicieron "
            f"{calls.get('log', 0)}"
        )
        captured = capsys.readouterr()
        assert captured.err == "", (
            f"Éxito genuino (aunque vacío) no debe emitir ningún WARN -- "
            f"stderr obtenido: {captured.err!r}"
        )


# ── 2. lib/boot_memory.py -- extract_glossary() ────────────────────────────

class TestExtractGlossaryReadRetryContract:
    """extract_glossary() hace `from git_helpers import run_git` DENTRO de
    la función (import diferido, cwd ambiente) -- se parchea
    `git_helpers.run_git`, y el repo objetivo se selecciona con
    `monkeypatch.chdir()`.
    """

    def test_retry_recovers_transient_failure_returns_real_entry_round_trip(
        self, tmp_path, monkeypatch,
    ):
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "\U0001f9ed decision(issue61retryglossary): use X",
            "Decision: use X over Y issue61glossarymarker",
        )
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        flaky, state = _make_flaky_run_git(real_run_git, fail_times=1, broken_dir=broken)
        monkeypatch.setattr(git_helpers, "run_git", flaky)

        result = boot_memory.extract_glossary()

        assert any("issue61glossarymarker" in text for _, text, _ in result["decisions"]), (
            f"Un fallo transitorio en el 1er intento debe recuperarse via "
            f"retry y devolver la entrada Decision REAL, no listas vacías. "
            f"result={result!r}, llamadas a run_git={state['n']}"
        )

    def test_persistent_failure_emits_warn_not_silent_empty(
        self, tmp_path, monkeypatch, capsys,
    ):
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f9ed decision(issue61retryglossary): use X", "Decision: use X over Y")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        always_fail = _make_always_failing_run_git(real_run_git, broken)
        monkeypatch.setattr(git_helpers, "run_git", always_fail)

        result = boot_memory.extract_glossary()

        assert result == {"decisions": [], "memos": [], "remembers": []}, (
            f"Fail-safe sin cambios de tipo tras agotar reintentos -- se "
            f"obtuvo {result!r}"
        )
        captured = capsys.readouterr()
        assert "[boot_memory] extract_glossary(): git log exited 128" in captured.err, (
            f"WARN visible esperado en stderr tras fallo persistente -- "
            f"stderr obtenido: {captured.err!r}"
        )

    def test_genuine_empty_result_no_retry_no_extra_warn(
        self, tmp_path, monkeypatch, capsys,
    ):
        repo = _make_repo(tmp_path)  # sin commits de memoria
        monkeypatch.chdir(repo)

        real_run_git = git_helpers.run_git
        counting, calls = _make_counting_run_git(real_run_git)
        monkeypatch.setattr(git_helpers, "run_git", counting)

        result = boot_memory.extract_glossary()

        # NOTA: a diferencia de _scan_commits() (que filtra con --grep de
        # memoria y por tanto obtiene log_output="" -> vía el early-return
        # fail-safe de 3 claves), extract_glossary() escanea TODOS los
        # commits sin filtrar -- con solo el commit "init" (sin trailers de
        # memoria) rc=0 y log_output NO está vacío, así que recorre el
        # camino de éxito completo y devuelve las 4 claves (incluye
        # "tombstones") con listas vacías. Se comprueban las listas
        # individualmente en vez de la igualdad de dict completo para no
        # acoplar este test a esa forma de implementación.
        assert result["decisions"] == [] and result["memos"] == [] and result["remembers"] == [], (
            f"Repo sin entradas de memoria debe devolver listas vacías, se "
            f"obtuvo {result!r}"
        )
        assert calls.get("log", 0) == 1, (
            f"Éxito genuino (rc=0) no debe disparar reintentos -- se hicieron "
            f"{calls.get('log', 0)} llamadas a 'git log'"
        )
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr debe quedar limpio, se obtuvo: {captured.err!r}"


# ── 3. lib/boot_git_checks.py -- get_timeline() ─────────────────────────────

class TestGetTimelineReadRetryContract:
    """get_timeline() también hace `from git_helpers import run_git` DENTRO
    de la función -- mismo patrón de parcheo que extract_glossary() arriba.
    A diferencia de _scan_commits()/extract_glossary() (filtran por grep de
    memoria), get_timeline() lista los últimos N commits SIN filtrar, así
    que un repo real siempre devuelve al menos el commit "init" -- el test
    de control aquí se centra en "éxito (rc=0) = exactamente 1 llamada, sin
    reintento", no en "resultado vacío", que no es un estado alcanzable de
    forma natural para esta función.
    """

    def test_retry_recovers_transient_failure_returns_real_entry_round_trip(
        self, tmp_path, monkeypatch,
    ):
        repo = _make_repo(tmp_path)
        _commit(repo, "chore: issue61timelinemarker")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        flaky, state = _make_flaky_run_git(real_run_git, fail_times=1, broken_dir=broken)
        monkeypatch.setattr(git_helpers, "run_git", flaky)

        entries = boot_git_checks.get_timeline(n=10)

        assert any("issue61timelinemarker" in e for e in entries), (
            f"Un fallo transitorio en el 1er intento debe recuperarse via "
            f"retry y devolver el timeline REAL (con el commit escrito por "
            f"este test), no []. entries={entries!r}, llamadas={state['n']}"
        )

    def test_persistent_failure_emits_warn_not_silent_empty(
        self, tmp_path, monkeypatch, capsys,
    ):
        repo = _make_repo(tmp_path)
        _commit(repo, "chore: issue61timelinemarker")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        always_fail = _make_always_failing_run_git(real_run_git, broken)
        monkeypatch.setattr(git_helpers, "run_git", always_fail)

        entries = boot_git_checks.get_timeline(n=10)

        assert entries == [], (
            f"Fail-safe sin cambios de tipo tras agotar reintentos -- se "
            f"obtuvo {entries!r}"
        )
        captured = capsys.readouterr()
        assert "[git_helpers] git 'log' exited 128" in captured.err, (
            f"WARN visible esperado en stderr tras fallo persistente -- "
            f"stderr obtenido: {captured.err!r}"
        )

    def test_successful_call_no_retry_no_warn(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path)
        monkeypatch.chdir(repo)

        real_run_git = git_helpers.run_git
        counting, calls = _make_counting_run_git(real_run_git)
        monkeypatch.setattr(git_helpers, "run_git", counting)

        entries = boot_git_checks.get_timeline(n=10)

        assert entries, "Un repo real (con el commit 'init') debe devolver al menos 1 entrada"
        assert calls.get("log", 0) == 1, (
            f"Éxito genuino (rc=0) no debe disparar reintentos -- se hicieron "
            f"{calls.get('log', 0)} llamadas a 'git log'"
        )
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr debe quedar limpio, se obtuvo: {captured.err!r}"


# ── 4. lib/git_helpers.py -- commits_since_last_consolidation() ────────────

class TestCommitsSinceLastConsolidationReadRetryContract:
    """commits_since_last_consolidation() hace dos llamadas a run_git
    DENTRO de la misma invocación (log --grep, luego rev-list --count) --
    se aísla el reintento a la PRIMERA ('log') con `match=lambda args:
    args[0] == "log"`, igual que test_issue61_breadcrumbs.py aísla sus
    sitios 2/3 con el mismo mecanismo de "doble selectivo".
    """

    _MATCH_LOG = staticmethod(lambda args: bool(args) and args[0] == "log")

    def test_retry_recovers_transient_failure_returns_real_count_round_trip(
        self, tmp_path, monkeypatch,
    ):
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f4be context(consolidation): issue61consolidationmarker")
        for i in range(2):
            _commit(repo, f"chore: after {i}")
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        flaky, state = _make_flaky_run_git(
            real_run_git, fail_times=1, broken_dir=broken, match=self._MATCH_LOG,
        )
        monkeypatch.setattr(git_helpers, "run_git", flaky)

        count = git_helpers.commits_since_last_consolidation(cwd=repo)

        assert count == 2, (
            f"Un fallo transitorio en el 1er intento de la llamada 'log --grep' "
            f"debe recuperarse via retry y devolver el conteo REAL (2 commits "
            f"tras el context(consolidation) escrito por este test), no 0/"
            f"sentinel. count={count!r}, llamadas 'log'={state['n']}"
        )

    def test_persistent_failure_emits_warn_not_silent_zero(
        self, tmp_path, monkeypatch, capsys,
    ):
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f4be context(consolidation): issue61consolidationmarker")
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        always_fail = _make_always_failing_run_git(
            real_run_git, broken, match=self._MATCH_LOG,
        )
        monkeypatch.setattr(git_helpers, "run_git", always_fail)

        count = git_helpers.commits_since_last_consolidation(cwd=repo)

        assert count == 0, (
            f"Fail-safe sin cambios de tipo tras agotar reintentos -- se "
            f"obtuvo {count!r}"
        )
        captured = capsys.readouterr()
        assert "[git_helpers] git 'log' exited 128" in captured.err, (
            f"WARN visible esperado en stderr tras fallo persistente -- "
            f"stderr obtenido: {captured.err!r}"
        )

    def test_genuine_success_no_retry_no_extra_warn(self, tmp_path, monkeypatch, capsys):
        """Control anti-falso-positivo: éxito genuino en AMBAS llamadas
        (log --grep encuentra el commit, rev-list --count funciona) --
        ninguna de las dos debe reintentarse.
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f4be context(consolidation): issue61consolidationmarker")
        for i in range(3):
            _commit(repo, f"chore: {i}")

        real_run_git = git_helpers.run_git
        counting, calls = _make_counting_run_git(real_run_git)
        monkeypatch.setattr(git_helpers, "run_git", counting)

        count = git_helpers.commits_since_last_consolidation(cwd=repo)

        assert count == 3, f"Se esperaban 3 commits tras la consolidación, se obtuvo {count!r}"
        assert calls.get("log", 0) == 1, (
            f"Éxito genuino no debe reintentar 'log --grep' -- se hicieron "
            f"{calls.get('log', 0)} llamadas"
        )
        assert calls.get("rev-list", 0) == 1, (
            f"Éxito genuino no debe reintentar 'rev-list --count' -- se "
            f"hicieron {calls.get('rev-list', 0)} llamadas"
        )
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr debe quedar limpio, se obtuvo: {captured.err!r}"


# ── 5. lib/boot_memory.py -- extract_memory() (mayor blast radius de los 3 nuevos) ─
#
# extract_memory() hace `from git_helpers import run_git, run_git_read_retrying`
# DENTRO de la función (import diferido, cwd ambiente) -- mismo patrón de
# parcheo que extract_glossary(): se parchea `git_helpers.run_git` y se
# selecciona el repo con `monkeypatch.chdir()`. Es un sitio de "print
# manual" (no pasa log_stderr_on_failure a run_git_read_retrying -- imprime
# su propio breadcrumb DESPUÉS de que el helper retorne), igual que
# extract_glossary().

class TestExtractMemoryReadRetryContract:
    def test_retry_recovers_transient_failure_returns_real_entry_round_trip(
        self, tmp_path, monkeypatch,
    ):
        repo = _make_repo(tmp_path)
        _commit(
            repo,
            "\U0001f9ed decision(issue61extractmemory): use X",
            "Decision: use X over Y issue61extractmemorymarker",
        )
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        flaky, state = _make_flaky_run_git(real_run_git, fail_times=1, broken_dir=broken)
        monkeypatch.setattr(git_helpers, "run_git", flaky)

        result = boot_memory.extract_memory()

        assert any(
            "issue61extractmemorymarker" in text for _, text, _ in result.get("decisions", [])
        ), (
            f"Un fallo transitorio en el 1er intento debe recuperarse via "
            f"retry y devolver la entrada Decision REAL escrita por este "
            f"mismo test, no listas vacías. result={result!r}, "
            f"llamadas={state['n']}"
        )

    def test_persistent_failure_emits_warn_not_silent_empty(
        self, tmp_path, monkeypatch, capsys,
    ):
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f9ed decision(issue61extractmemory): use X", "Decision: use X over Y")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        always_fail = _make_always_failing_run_git(real_run_git, broken)
        monkeypatch.setattr(git_helpers, "run_git", always_fail)

        result = boot_memory.extract_memory()

        assert result == {}, f"Fail-safe sin cambios de tipo -- se obtuvo {result!r}"
        captured = capsys.readouterr()
        assert "[boot_memory] extract_memory(): git log exited 128" in captured.err, (
            f"WARN visible esperado en stderr tras fallo persistente -- "
            f"stderr obtenido: {captured.err!r}"
        )

    def test_genuine_empty_result_no_retry_no_extra_warn(
        self, tmp_path, monkeypatch, capsys,
    ):
        repo = _make_repo(tmp_path)  # solo "init", sin trailers de memoria
        monkeypatch.chdir(repo)

        real_run_git = git_helpers.run_git
        counting, calls = _make_counting_run_git(real_run_git)
        monkeypatch.setattr(git_helpers, "run_git", counting)

        result = boot_memory.extract_memory()

        assert result.get("decisions", []) == [] and result.get("memos", []) == [], (
            f"Repo sin entradas de memoria debe devolver listas vacías, se "
            f"obtuvo {result!r}"
        )
        assert calls.get("log", 0) == 1, (
            f"Éxito genuino (rc=0) no debe disparar reintentos -- se "
            f"hicieron {calls.get('log', 0)} llamadas a 'git log'"
        )
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr debe quedar limpio, se obtuvo: {captured.err!r}"

    def test_transient_recovery_leaves_no_warn_trace(
        self, tmp_path, monkeypatch, capsys,
    ):
        """WARN solo tras agotar (Cerberus, Verify round): un transitorio
        que SE RECUPERA en el 2º intento no debe dejar NINGÚN rastro en
        stderr -- ni siquiera la traza del 1er intento fallido. Si dejara
        rastro, sería una falsa alarma para un fallo que ya se autocuró.
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f9ed decision(issue61extractmemory): use X", "Decision: use X over Y")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        flaky, state = _make_flaky_run_git(real_run_git, fail_times=1, broken_dir=broken)
        monkeypatch.setattr(git_helpers, "run_git", flaky)

        result = boot_memory.extract_memory()

        assert result.get("decisions"), "El retry debió recuperar la entrada real"
        captured = capsys.readouterr()
        assert captured.err == "", (
            f"Un fallo transitorio que SE RECUPERA no debe dejar ningún "
            f"WARN en stderr (ni siquiera la traza del 1er intento "
            f"fallido) -- se obtuvo: {captured.err!r}"
        )

    def test_persistent_failure_warns_exactly_once_not_per_attempt(
        self, tmp_path, monkeypatch, capsys,
    ):
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f9ed decision(issue61extractmemory): use X", "Decision: use X over Y")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        always_fail = _make_always_failing_run_git(real_run_git, broken)
        monkeypatch.setattr(git_helpers, "run_git", always_fail)

        boot_memory.extract_memory()

        captured = capsys.readouterr()
        occurrences = captured.err.count("[boot_memory] extract_memory(): git log exited 128")
        assert occurrences == 1, (
            f"El WARN debe aparecer EXACTAMENTE 1 vez tras agotar los "
            f"{git_helpers.READ_RETRY_ATTEMPTS} intentos (no una vez por "
            f"intento) -- apareció {occurrences} veces en: {captured.err!r}"
        )


# ── 6. hooks/precompact-snapshot.py -- extract_memory_from_log() ───────────
#
# Fichero con guion, no importable con `import` -- se ejecuta via un
# subprocess Python AISLADO que parchea git_helpers.run_git ANTES de
# cargar el hook via importlib (mismo patrón que
# _PRECOMPACT_BRANCH_FAILURE_PROBE de test_issue61_breadcrumbs.py), para
# que el parche nunca contamine el proceso de test principal. Sitio con
# `log_stderr_on_failure=True` EXPLÍCITO (mecanismo A, no el print manual
# de extract_memory()).

_PRECOMPACT_EXTRACT_MEMORY_PROBE = """
import sys, os, json, importlib.util

LIB_DIR = {lib_dir!r}
HOOKS_DIR = {hooks_dir!r}
BROKEN = {broken!r}
MODE = {mode!r}  # "flaky1" | "always" | "counting"

sys.path.insert(0, LIB_DIR)

import git_helpers
_real_run_git = git_helpers.run_git
_state = {{"n": 0}}


def _fake_run_git(args, **kwargs):
    _state["n"] += 1
    if MODE == "flaky1":
        if _state["n"] <= 1:
            kwargs["cwd"] = BROKEN
    elif MODE == "always":
        kwargs["cwd"] = BROKEN
    return _real_run_git(args, **kwargs)


git_helpers.run_git = _fake_run_git

spec = importlib.util.spec_from_file_location(
    "precompact_probe", os.path.join(HOOKS_DIR, "precompact-snapshot.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

result = mod.extract_memory_from_log()
print(json.dumps({{"result": result, "calls": _state["n"]}}))
"""


class TestExtractMemoryFromLogReadRetryContract:
    def _run_probe(self, repo, mode, broken=""):
        script = _PRECOMPACT_EXTRACT_MEMORY_PROBE.format(
            lib_dir=LIB_DIR, hooks_dir=HOOKS_DIR, broken=broken, mode=mode,
        )
        return subprocess.run(
            [sys.executable, "-c", script],
            cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )

    def test_retry_recovers_transient_failure_returns_real_entry_round_trip(self, tmp_path):
        repo = str(tmp_path / "repo1")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["config", "user.email", "test@test.com"], repo)
        git_cmd(["config", "user.name", "Test"], repo)
        git_cmd(
            ["commit", "--allow-empty", "-m",
             "\U0001f9ed decision(issue61precompact): use X\n\n"
             "Decision: use X over Y issue61precompactmarker"],
            repo,
        )
        broken = _make_broken_dir(tmp_path, "not_a_repo_probe1")

        proc = self._run_probe(repo, mode="flaky1", broken=broken)

        assert proc.returncode == 0, f"probe crasheó: stderr={proc.stderr!r}"
        payload = json.loads(proc.stdout)
        assert any(
            "issue61precompactmarker" in d.get("decision", "")
            for d in payload["result"].get("decisions", {}).values()
        ), (
            f"Un fallo transitorio en el 1er intento debe recuperarse via "
            f"retry y devolver la entrada Decision REAL, no {{}}. "
            f"payload={payload!r}"
        )
        assert payload["calls"] == 2, (
            f"Se esperaban exactamente 2 llamadas a run_git (1 fallo + 1 "
            f"éxito), se hicieron {payload['calls']}"
        )

    def test_persistent_failure_emits_warn_not_silent_empty(self, tmp_path):
        repo = str(tmp_path / "repo2")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["config", "user.email", "test@test.com"], repo)
        git_cmd(["config", "user.name", "Test"], repo)
        git_cmd(
            ["commit", "--allow-empty", "-m",
             "\U0001f9ed decision(issue61precompact): use X\n\nDecision: use X over Y"],
            repo,
        )
        broken = _make_broken_dir(tmp_path, "not_a_repo_probe2")

        proc = self._run_probe(repo, mode="always", broken=broken)

        assert proc.returncode == 0, f"probe crasheó: stderr={proc.stderr!r}"
        payload = json.loads(proc.stdout)
        assert payload["result"] == {}, f"Fail-safe sin cambios -- se obtuvo {payload!r}"
        assert "[git_helpers] git 'log' exited 128" in proc.stderr, (
            f"WARN visible esperado en stderr -- se obtuvo: {proc.stderr!r}"
        )

    def test_genuine_no_memory_trailers_no_retry_no_warn(self, tmp_path):
        repo = str(tmp_path / "repo3")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["config", "user.email", "test@test.com"], repo)
        git_cmd(["config", "user.name", "Test"], repo)
        git_cmd(["commit", "--allow-empty", "-m", "chore: sin trailers de memoria"], repo)

        proc = self._run_probe(repo, mode="counting")

        assert proc.returncode == 0, f"probe crasheó: stderr={proc.stderr!r}"
        payload = json.loads(proc.stdout)
        assert payload["result"].get("decisions", {}) == {}
        assert payload["result"].get("memos", {}) == {}
        assert payload["calls"] == 1, (
            f"Éxito genuino (rc=0) no debe disparar reintentos -- se "
            f"hicieron {payload['calls']} llamadas"
        )
        assert proc.stderr == "", f"stderr debe quedar limpio, se obtuvo: {proc.stderr!r}"


# ── 7. lib/boot_git_checks.py -- get_last_context_time() ───────────────────
#
# Mismo patrón de import diferido que get_timeline() -- se parchea
# `git_helpers.run_git`. Sitio con `log_stderr_on_failure=True` EXPLÍCITO
# (mecanismo A) -- complementa a extract_memory() (mecanismo B, print
# manual) para la cobertura de "WARN solo tras agotar" pedida por el
# coordinador.

class TestGetLastContextTimeReadRetryContract:
    def test_retry_recovers_transient_failure_returns_real_time_round_trip(
        self, tmp_path, monkeypatch,
    ):
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f4be context(issue61ctx): issue61ctxmarker")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        flaky, state = _make_flaky_run_git(real_run_git, fail_times=1, broken_dir=broken)
        monkeypatch.setattr(git_helpers, "run_git", flaky)

        result = boot_git_checks.get_last_context_time()

        assert result is not None, (
            f"Un fallo transitorio en el 1er intento debe recuperarse via "
            f"retry y devolver el time_ago REAL del commit context() "
            f"escrito por este test, no None. llamadas={state['n']}"
        )

    def test_persistent_failure_emits_warn_not_silent_none(
        self, tmp_path, monkeypatch, capsys,
    ):
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f4be context(issue61ctx): marker")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        always_fail = _make_always_failing_run_git(real_run_git, broken)
        monkeypatch.setattr(git_helpers, "run_git", always_fail)

        result = boot_git_checks.get_last_context_time()

        assert result is None, f"Fail-safe sin cambios de tipo -- se obtuvo {result!r}"
        captured = capsys.readouterr()
        assert "[git_helpers] git 'log' exited 128" in captured.err, (
            f"WARN visible esperado en stderr tras fallo persistente -- "
            f"stderr obtenido: {captured.err!r}"
        )

    def test_genuine_no_context_commit_no_retry_no_warn(
        self, tmp_path, monkeypatch, capsys,
    ):
        repo = _make_repo(tmp_path)  # solo "init", sin context()
        monkeypatch.chdir(repo)

        real_run_git = git_helpers.run_git
        counting, calls = _make_counting_run_git(real_run_git)
        monkeypatch.setattr(git_helpers, "run_git", counting)

        result = boot_git_checks.get_last_context_time()

        assert result is None, f"Sin commit context(), se esperaba None -- se obtuvo {result!r}"
        assert calls.get("log", 0) == 1, (
            f"Éxito genuino (rc=0) no debe disparar reintentos -- se "
            f"hicieron {calls.get('log', 0)} llamadas a 'git log'"
        )
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr debe quedar limpio, se obtuvo: {captured.err!r}"

    def test_transient_recovery_leaves_no_warn_trace(
        self, tmp_path, monkeypatch, capsys,
    ):
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f4be context(issue61ctx): marker")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        flaky, state = _make_flaky_run_git(real_run_git, fail_times=1, broken_dir=broken)
        monkeypatch.setattr(git_helpers, "run_git", flaky)

        result = boot_git_checks.get_last_context_time()

        assert result is not None, "El retry debió recuperar el time_ago real"
        captured = capsys.readouterr()
        assert captured.err == "", (
            f"Un fallo transitorio que SE RECUPERA no debe dejar ningún "
            f"WARN en stderr -- se obtuvo: {captured.err!r}"
        )

    def test_persistent_failure_warns_exactly_once_not_per_attempt(
        self, tmp_path, monkeypatch, capsys,
    ):
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f4be context(issue61ctx): marker")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        always_fail = _make_always_failing_run_git(real_run_git, broken)
        monkeypatch.setattr(git_helpers, "run_git", always_fail)

        boot_git_checks.get_last_context_time()

        captured = capsys.readouterr()
        occurrences = captured.err.count("[git_helpers] git 'log' exited 128")
        assert occurrences == 1, (
            f"El WARN debe aparecer EXACTAMENTE 1 vez tras agotar los "
            f"{git_helpers.READ_RETRY_ATTEMPTS} intentos (no una vez por "
            f"intento) -- apareció {occurrences} veces en: {captured.err!r}"
        )


# ── 8. lib/git_helpers.py -- run_git_read_retrying() (SEC-HIGH-001, límite de reloj) ─
#
# Prueba directa del helper compartido -- es donde vive TODA la lógica de
# deadline, aislada de cualquier sitio concreto (unit-level, no
# integration: el valor está en la lógica pura del bucle, no en el
# cableado). Reloj controlado via `_FakeTimeModule` (ver arriba) -- nunca
# un sleep real de 10s.

class TestRunGitReadRetryingDeadline:
    def test_hanging_first_attempt_never_starts_a_second_attempt(self, monkeypatch):
        fake_time = _FakeTimeModule(start=1000.0)
        monkeypatch.setattr(git_helpers, "time", fake_time)

        call_count = {"n": 0}

        def _hanging_run_git(args, **kwargs):
            call_count["n"] += 1
            # Simula un cuelgue real: la propia llamada consume ~todo el
            # presupuesto de GIT_TIMEOUT antes de devolver (run_git() real
            # devuelve (1, "") tras su propio timeout interno -- mismo
            # shape aquí, sin sleep real de por medio).
            fake_time.advance(git_helpers.GIT_TIMEOUT)
            return 1, ""

        code, output = git_helpers.run_git_read_retrying(_hanging_run_git, ["log", "--all"])

        assert call_count["n"] == 1, (
            f"Un intento que agota el presupuesto de reloj no debe "
            f"disparar un 2º intento -- se hicieron {call_count['n']} "
            f"llamadas a run_git_fn (peor caso esperado: ~1x GIT_TIMEOUT, "
            f"no {git_helpers.READ_RETRY_ATTEMPTS}x)"
        )
        assert (code, output) == (1, ""), f"Fail-safe sin cambios -- se obtuvo {(code, output)!r}"

    def test_anti_vacuity_fast_failures_still_get_full_retry_budget(self, monkeypatch):
        """Prueba que la aserción de arriba realmente distingue "cuelgue"
        de "fallo rápido": si cada intento consume solo una fracción
        mínima del presupuesto, el helper SÍ debe llegar a los
        READ_RETRY_ATTEMPTS intentos completos -- no se corta siempre de
        forma vacía en 1, solo cuando el presupuesto se agota de verdad.
        """
        fake_time = _FakeTimeModule(start=1000.0)
        monkeypatch.setattr(git_helpers, "time", fake_time)

        call_count = {"n": 0}

        def _fast_failing_run_git(args, **kwargs):
            call_count["n"] += 1
            fake_time.advance(0.01)  # fallo rápido, no un cuelgue
            return 1, ""

        code, output = git_helpers.run_git_read_retrying(_fast_failing_run_git, ["log", "--all"])

        assert call_count["n"] == git_helpers.READ_RETRY_ATTEMPTS, (
            f"Fallos rápidos (sin agotar el presupuesto de reloj) deben "
            f"agotar los {git_helpers.READ_RETRY_ATTEMPTS} intentos "
            f"normales -- se hicieron {call_count['n']}"
        )
        assert (code, output) == (1, "")

    def test_hanging_read_bounded_to_one_attempt_at_site_level(self, tmp_path, monkeypatch):
        """Integración (no solo el helper aislado): el sitio de mayor
        blast radius (extract_memory()) también debe quedar acotado a 1
        intento cuando el propio run_git simulado "cuelga" -- prueba el
        cableado real end-to-end, no solo la lógica pura del helper.
        """
        repo = _make_repo(tmp_path)
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        fake_time = _FakeTimeModule(start=1000.0)
        monkeypatch.setattr(git_helpers, "time", fake_time)

        real_run_git = git_helpers.run_git
        call_count = {"n": 0}

        def _hanging(args, **kwargs):
            call_count["n"] += 1
            fake_time.advance(git_helpers.GIT_TIMEOUT)
            kwargs["cwd"] = broken
            return real_run_git(args, **kwargs)

        monkeypatch.setattr(git_helpers, "run_git", _hanging)

        result = boot_memory.extract_memory()

        assert result == {}, f"Fail-safe sin cambios -- se obtuvo {result!r}"
        assert call_count["n"] == 1, (
            f"extract_memory() (mayor blast radius) no debe reintentar "
            f"tras un cuelgue simulado que agota el presupuesto -- se "
            f"hicieron {call_count['n']} llamadas"
        )

    def test_slow_then_would_be_hanging_second_attempt_gets_capped_timeout(
        self, monkeypatch,
    ):
        """Repair pass tras Moriarty: el test de deadline anterior
        (`test_hanging_first_attempt_never_starts_a_second_attempt`) solo
        cubría "el 1er intento cuelga" -- bloqueado por el gate de "no
        arrancar un intento nuevo si queda menos de
        READ_RETRY_MIN_ATTEMPT_SECONDS de presupuesto". El agujero real
        que Moriarty demostró: intento 1 LENTO-PERO-REAL (falla tras
        consumir CASI todo el presupuesto, p.ej. 9.3s de los 10s) deja
        ~0.7s de presupuesto -- suficiente para que el gate SÍ deje
        arrancar un 2º intento (0.7s > READ_RETRY_MIN_ATTEMPT_SECONDS =
        0.5s). Sin un cap POR INTENTO, ese 2º intento podría colgarse
        otro GIT_TIMEOUT completo (total ~2x, exactamente el escenario
        que SEC-HIGH-001 quería cerrar). El fix real de Ultron: cada
        intento recibe `timeout=max(0.1, min(presupuesto_restante,
        GIT_TIMEOUT))` -- el 2º intento aquí debe recibir ~0.7s, NO 10s,
        así que aunque "cuelgue" (un run_git() real lo mataría a su
        propio timeout interno, vía subprocess.communicate(timeout=...))
        queda acotado a esos ~0.7s, no a otro GIT_TIMEOUT completo.

        Reloj controlado (mismo `_FakeTimeModule` que el resto de esta
        clase): el run_git_fn falso REGISTRA el `timeout` que recibió en
        cada llamada (la aserción central) y avanza el reloj simulado
        exactamente ese valor en la 2ª llamada -- simula lo que un
        run_git() real haría si esa llamada colgase hasta su propio
        límite capado, sin ningún sleep real de por medio.
        """
        fake_time = _FakeTimeModule(start=1000.0)
        monkeypatch.setattr(git_helpers, "time", fake_time)

        received_timeouts = []

        def _slow_then_hanging_run_git(args, **kwargs):
            received_timeouts.append(kwargs.get("timeout"))
            if len(received_timeouts) == 1:
                # Intento 1: lento pero real -- consume ~9.3s de los 10s
                # de presupuesto antes de fallar (no un cuelgue puro).
                fake_time.advance(9.3)
                return 1, ""
            # Intento 2 (y cualquier posterior, si el gate fallara y
            # llegara a arrancar): simula que SE COLGARÍA -- un run_git()
            # real lo mataría a su propio timeout (el valor capado que
            # recibió en kwargs), así que el reloj avanza EXACTAMENTE ese
            # timeout, nunca GIT_TIMEOUT completo.
            fake_time.advance(kwargs.get("timeout") or git_helpers.GIT_TIMEOUT)
            return 1, ""

        start = fake_time.monotonic()
        code, output = git_helpers.run_git_read_retrying(_slow_then_hanging_run_git, ["log", "--all"])
        total_elapsed = fake_time.monotonic() - start

        assert len(received_timeouts) == 2, (
            f"Se esperaban EXACTAMENTE 2 intentos -- el 1º (lento, agota "
            f"~9.3s) y el 2º (arranca con ~0.7s restantes, se "
            f"'cuelga' hasta agotar ese resto -- el 3º ya no tiene "
            f"presupuesto para arrancar). Se hicieron "
            f"{len(received_timeouts)}, timeouts recibidos="
            f"{received_timeouts!r}"
        )
        assert received_timeouts[0] == pytest.approx(git_helpers.GIT_TIMEOUT, abs=0.01), (
            f"El 1er intento arranca con el presupuesto completo -- se "
            f"esperaba timeout≈{git_helpers.GIT_TIMEOUT}, se recibió "
            f"{received_timeouts[0]!r}"
        )
        assert received_timeouts[1] is not None and received_timeouts[1] < git_helpers.GIT_TIMEOUT * 0.9, (
            f"EL PUNTO CENTRAL DE ESTE TEST: el 2º intento debe recibir "
            f"un timeout CAPADO al presupuesto RESTANTE (~0.7s), NO el "
            f"GIT_TIMEOUT completo ({git_helpers.GIT_TIMEOUT}s) -- si "
            f"recibiera el GIT_TIMEOUT completo, un cuelgue real en el "
            f"2º intento podría costar otro GIT_TIMEOUT entero (~2x "
            f"total), exactamente el agujero que Moriarty demostró. Se "
            f"recibió {received_timeouts[1]!r}"
        )
        assert total_elapsed <= git_helpers.GIT_TIMEOUT * 1.1, (
            f"El reloj simulado total no debe superar ~1x GIT_TIMEOUT "
            f"({git_helpers.GIT_TIMEOUT}s) -- se obtuvo {total_elapsed!r}s. "
            f"Un total cercano a 2x GIT_TIMEOUT indicaría que el 2º "
            f"intento se dejó colgar sin el cap por intento (el bug que "
            f"Moriarty demostró antes de este fix)."
        )
        assert (code, output) == (1, ""), f"Fail-safe sin cambios -- se obtuvo {(code, output)!r}"


# ── 9. lib/bootstrap_commits.py -- scan_recent_commits() (cierre de completitud) ─
#
# scan_recent_commits() hace `from git_helpers import run_git,
# run_git_read_retrying` a NIVEL DE MÓDULO (bound name, como recall.py) --
# se parchea `bootstrap_commits.run_git`, nunca `git_helpers.run_git`. Dos
# llamadas internas envueltas cada una por su cuenta con
# run_git_read_retrying(): la 1ª (%h\x1f%aI\x1f%s%n%b, commits/fechas/
# scopes) y la 2ª (%h\x1f%an, autores) -- se distinguen contando los
# separadores \x1f en su propio literal --pretty=format:, igual que
# test_issue61_breadcrumbs.py::TestScanRecentCommitsBreadcrumb ya hace
# para aislar estos mismos dos sitios. Sin cwd param -- depende del cwd
# ambiente del proceso (monkeypatch.chdir()).
#
# No se re-testea deadline/WARN aquí (ya cubierto genéricamente por el
# sitio 8, TestRunGitReadRetryingDeadline, y por el mecanismo A de WARN ya
# probado en otros sitios con log_stderr_on_failure=True) -- solo el
# CABLEADO: que el retry envuelve de verdad ambas llamadas de ESTE sitio.

def _match_scan_recent_call1(args):
    """1ª llamada de scan_recent_commits(): %h\x1f%aI\x1f%s (2 separadores)."""
    pretty = next((a for a in args if a.startswith("--pretty=format:")), "")
    return pretty.count("\x1f") == 2


def _match_scan_recent_call2(args):
    """2ª llamada de scan_recent_commits(): %h\x1f%an (1 separador)."""
    pretty = next((a for a in args if a.startswith("--pretty=format:")), "")
    return pretty.count("\x1f") == 1


class TestScanRecentCommitsReadRetryContract:
    def test_retry_recovers_transient_failure_in_first_call_returns_real_commits_round_trip(
        self, tmp_path, monkeypatch,
    ):
        """1ª llamada (commits/fechas/subjects): un fallo transitorio en el
        1er intento debe recuperarse via retry y devolver los commits
        REALES escritos por este mismo test (round-trip §34), no None.
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "chore: issue61scanrecentmarker")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = bootstrap_commits.run_git
        flaky, state = _make_flaky_run_git(
            real_run_git, fail_times=1, broken_dir=broken, match=_match_scan_recent_call1,
        )
        monkeypatch.setattr(bootstrap_commits, "run_git", flaky)

        result = bootstrap_commits.scan_recent_commits(depth=20)

        assert result is not None, (
            f"Un fallo transitorio en el 1er intento de la 1ª llamada debe "
            f"recuperarse via retry, no devolver None. llamadas={state['n']}"
        )
        assert any(
            "issue61scanrecentmarker" in c.get("subject", "") for c in result.get("recent", [])
        ), (
            f"Se esperaba el commit REAL escrito por este test entre los "
            f"'recent', no una lista vacía/degradada -- result={result!r}"
        )

    def test_retry_recovers_transient_failure_in_second_call_returns_real_authors_round_trip(
        self, tmp_path, monkeypatch,
    ):
        """2ª llamada (autores): un fallo transitorio en el 1er intento
        debe recuperarse via retry y devolver el autor REAL, no degradar
        a author='' (que es lo que pasa hoy cuando esta llamada falla
        SIN retry, ver test_issue61_breadcrumbs.py's
        test_second_call_failure_breadcrumb_and_degraded_authors).
        """
        repo = _make_repo(tmp_path)
        git_cmd(["config", "user.name", "Issue61ScanRecentAuthor"], repo)
        git_cmd(["config", "user.email", "issue61@test.com"], repo)
        _commit(repo, "chore: alpha")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = bootstrap_commits.run_git
        flaky, state = _make_flaky_run_git(
            real_run_git, fail_times=1, broken_dir=broken, match=_match_scan_recent_call2,
        )
        monkeypatch.setattr(bootstrap_commits, "run_git", flaky)

        result = bootstrap_commits.scan_recent_commits(depth=20)

        assert result is not None
        assert result["authors"].get("Issue61ScanRecentAuthor") == 1, (
            f"Un fallo transitorio en el 1er intento de la 2ª llamada debe "
            f"recuperarse via retry y devolver el autor REAL, no degradar "
            f"a author='' -- authors={result['authors']!r}, "
            f"llamadas={state['n']}"
        )
        # NOTA: _make_repo() ya deja un commit "init" con autor "Test"
        # (configurado ANTES de que este test reconfigure user.name) --
        # el repo tiene 2 commits con autores distintos a propósito, así
        # que se comprueba el autor del commit "alpha" en concreto (no
        # "todos los recent"), evitando una aserción vacuamente falsa por
        # el propio "init".
        alpha_entry = next(c for c in result["recent"] if c["subject"] == "chore: alpha")
        assert alpha_entry["author"] == "Issue61ScanRecentAuthor", (
            f"El commit 'alpha' debe llevar el autor REAL tras la "
            f"recuperación, no degradar a '' -- se obtuvo {alpha_entry!r}"
        )

    def test_genuine_success_no_retry_no_warn(self, tmp_path, monkeypatch, capsys):
        """Control anti-falso-positivo: scan_recent_commits() siempre ve
        al menos el commit 'init' de _make_repo() -- nunca produce un
        resultado genuinamente vacío (a diferencia de _scan_commits(),
        que sí filtra por grep de memoria) -- así que el control aquí es
        "éxito (rc=0) = exactamente 1 llamada por sitio, sin reintento",
        mismo criterio ya usado para get_timeline()/
        commits_since_last_consolidation() en este mismo fichero.
        """
        repo = _make_repo(tmp_path)
        git_cmd(["config", "user.name", "Issue61ScanRecentControl"], repo)
        git_cmd(["config", "user.email", "issue61control@test.com"], repo)
        _commit(repo, "chore: alpha")
        _commit(repo, "chore: beta")
        monkeypatch.chdir(repo)

        real_run_git = bootstrap_commits.run_git
        calls = {"call1": 0, "call2": 0}

        def _counting(args, **kwargs):
            if _match_scan_recent_call1(args):
                calls["call1"] += 1
            elif _match_scan_recent_call2(args):
                calls["call2"] += 1
            return real_run_git(args, **kwargs)

        monkeypatch.setattr(bootstrap_commits, "run_git", _counting)

        result = bootstrap_commits.scan_recent_commits(depth=20)

        assert result is not None
        assert result["count"] == 3, f"Se esperaban 3 commits (init + alpha + beta), se obtuvo {result!r}"
        assert result["authors"].get("Issue61ScanRecentControl") == 2, (
            f"2 de los 3 commits (alpha/beta) llevan el autor real configurado -- "
            f"se obtuvo {result['authors']!r}"
        )
        assert calls["call1"] == 1, (
            f"Éxito genuino (rc=0) no debe reintentar la 1ª llamada -- se "
            f"hicieron {calls['call1']} llamadas"
        )
        assert calls["call2"] == 1, (
            f"Éxito genuino (rc=0) no debe reintentar la 2ª llamada -- se "
            f"hicieron {calls['call2']} llamadas"
        )
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr debe quedar limpio, se obtuvo: {captured.err!r}"
