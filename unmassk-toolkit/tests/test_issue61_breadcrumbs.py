"""
Cierre de hallazgo de Cerberus sobre issue #61 (suggestion, no bloqueante
pero se repara -- estandar del repo): los 9 breadcrumbs de diagnostico
que Ultron anadio (fallos de `git` con rc!=0 que ahora escriben una traza
a stderr en vez de colapsar en silencio a un valor fail-safe) no tenian
NINGUN test que provocara el fallo en cada sitio real y verificara que la
traza aparece. El unico test existente del mecanismo
(test_boot_freshness_hardening.py::TestRunGitLogStderrOnFailure) cubre
run_git()'s propio kwarg de forma generica (7 escenarios con Popen
mockeado) -- nunca los 9 CALL SITES que realmente lo usan en produccion.

Los 9 sitios (2 mecanismos distintos):

  A) `log_stderr_on_failure=True` pasado a git_helpers.run_git() -- el
     breadcrumb lo imprime run_git() mismo. 7 sitios:
       1. lib/recall.py:194                 _scan_commits()
       2. lib/git_helpers.py:572             commits_since_last_consolidation() [log --grep]
       3. lib/git_helpers.py:611             commits_since_last_consolidation() [rev-list --count]
       4. lib/bootstrap_commits.py:139       scan_recent_commits() [log %h/%aI/%s/%b]
       5. lib/bootstrap_commits.py:156       scan_recent_commits() [log %h/%an]
       6. hooks/precompact-snapshot.py:113   extract_memory_from_log()
       7. hooks/precompact-snapshot.py:263   format_snapshot() [branch --show-current]

  B) print manual a stderr en el propio call site (NO usa el kwarg,
     porque varios dobles de test para run_git en este repo tienen firma
     fija `(args, cwd=None)` sin **kwargs, y pasar un kwarg nuevo ahi
     rompe esos tests con TypeError -- documentado en el propio codigo).
     2 sitios:
       8. lib/boot_memory.py:181             extract_memory()
       9. lib/boot_memory.py:403             extract_glossary()

Test surface (EXHAUSTION PROTOCOL paso 1): 7 funciones de produccion
cubren los 9 call sites (commits_since_last_consolidation y
scan_recent_commits tienen 2 call sites cada una, dentro de la MISMA
funcion). Para cada call site: 1 test de fallo real (verifica (a) el
valor de retorno fail-safe intacto y (b) el breadcrumb en stderr con
contenido diagnosticable). Ademas, 1 test de anti-vacuidad POR FUNCION
(7 en total, cubriendo ambos mecanismos A y B) que prueba que la MISMA
asercion de stderr distingue exito de fallo (caso feliz -> stderr
limpio), no que sea vacuamente verdadera. Total: 9 fallos + 7
anti-vacuidad = 16 tests. Excluido de este fichero: la logica interna de
run_git()'s propio kwarg (ya cubierta por TestRunGitLogStderrOnFailure) y
cualquier otro comportamiento de estas funciones no relacionado con el
breadcrumb (ya cubierto por sus propios tests dedicados en
test_boot_freshness_hardening.py / test_consolidation_trigger.py / etc.).

Canal de fallo usado (el mas realista disponible en cada caso, nunca un
valor inventado -- unmassk-standards SS34):
  - Sitios con parametro `repo_dir`/`cwd` explicito (1, 2/3 primera
    llamada): un directorio real que existe pero no es un repo git
    (`git log`/`git rev-list` fallan de verdad, rc=128 real).
  - Sitios sin parametro de cwd, dependientes del cwd ambiente del
    proceso (4/5, 8, 9): `monkeypatch.chdir()` (pytest lo restaura solo),
    mismo patron que test_boot_freshness_hardening.py.
  - Sitios donde SOLO la segunda de dos llamadas debe fallar (3, 5, 7):
    un doble de run_git que delega a la funcion REAL para toda llamada
    que no sea la que se quiere romper, y solo le cambia el `cwd` a un
    directorio roto para esa -- el print del breadcrumb sigue siendo el
    codigo real de produccion ejecutandose, no una reimplementacion.
  - Sitio 6/9 (hooks/precompact-snapshot.py, fichero con guion, no
    importable con `import`): subprocess real completo para el fallo
    simple (repo con `git init` sin commits -- pasa is_git_repo() pero
    `git log` falla de verdad); para el sitio 7 (branch, solo alcanzable
    cuando ya hay memoria real), un script inline ejecutado en un
    subprocess AISLADO que monkeypatchea git_helpers.run_git antes de
    cargar el hook via importlib (mismo patron ya usado en el repo para
    hooks hyphenated) -- nunca contamina el proceso de test principal.
"""

import os
import subprocess
import sys

from conftest import (
    SOURCE_ROOT, HOOKS_DIR, PRECOMPACT_SCRIPT,
    run_cmd, git_cmd,
)

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import recall  # noqa: E402
import git_helpers  # noqa: E402
import bootstrap_commits  # noqa: E402
import boot_memory  # noqa: E402


# ── Repo helpers (convencion local del fichero, igual que test_crown.py) ───

def _make_repo(tmp_path, name="repo"):
    """Repo git minimo, con identidad configurada, sin install."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _commit(repo, subject, trailers=""):
    """Commit con bloque de trailers opcional (misma forma que test_crown.py)."""
    msg = subject
    if trailers:
        msg = subject + "\n\n" + trailers
    git_cmd(["commit", "--allow-empty", "-m", msg], repo)


def _make_broken_dir(tmp_path, name="not_a_repo"):
    """Directorio real que EXISTE pero no es un repo git en ningun ancestro."""
    broken = tmp_path / name
    broken.mkdir()
    return str(broken)


# ── 1. lib/recall.py:194 -- _scan_commits() ────────────────────────────────

class TestScanCommitsBreadcrumb:
    """_scan_commits(repo_dir=...) pasa el kwarg log_stderr_on_failure=True
    directamente a run_git() -- el breadcrumb lo imprime run_git() mismo.
    """

    def test_git_log_failure_leaves_breadcrumb_and_empty_list(self, tmp_path, capsys):
        broken = _make_broken_dir(tmp_path)

        entries = recall._scan_commits(repo_dir=broken)

        assert entries == [], (
            f"_scan_commits() debe fail-safe a [] en fallo de git, devolvio {entries!r}"
        )
        captured = capsys.readouterr()
        assert "[git_helpers] git 'log' exited 128" in captured.err, (
            f"Se esperaba breadcrumb con rc=128 en stderr, se obtuvo: {captured.err!r}"
        )

    def test_anti_vacuity_valid_repo_returns_entries_with_clean_stderr(self, tmp_path, capsys):
        """Anti-vacuidad (mecanismo A): prueba que la asercion de arriba
        realmente distingue exito de fallo -- un repo sano debe devolver
        entradas reales Y dejar stderr limpio.
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f9ed decision(issue61test): use X", "Decision: use X over Y")

        entries = recall._scan_commits(repo_dir=repo)

        assert any(
            e["kind"] == "Decision" and "use X over Y" in e["text"] for e in entries
        ), f"Se esperaba la entrada Decision real del commit, se obtuvo {entries!r}"
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr debe estar limpio en exito, se obtuvo: {captured.err!r}"


# ── 2/3. lib/git_helpers.py:572,611 -- commits_since_last_consolidation() ──

class TestCommitsSinceLastConsolidationBreadcrumb:
    """Dos call sites independientes de log_stderr_on_failure=True dentro
    de la MISMA funcion: la primera llamada (log --grep=context(consolidation))
    y la segunda (rev-list --count), solo alcanzable si la primera SI
    encontro un commit de consolidacion.
    """

    def test_first_call_failure_breadcrumb_and_zero(self, tmp_path, capsys):
        broken = _make_broken_dir(tmp_path)

        count = git_helpers.commits_since_last_consolidation(cwd=broken)

        assert count == 0, f"Fallo total de git debe fail-safe a 0, devolvio {count!r}"
        captured = capsys.readouterr()
        assert "[git_helpers] git 'log' exited 128" in captured.err, (
            f"Se esperaba breadcrumb de la 1a llamada (log) en stderr, se obtuvo: {captured.err!r}"
        )

    def test_second_call_failure_breadcrumb_and_zero(self, tmp_path, monkeypatch, capsys):
        """Fuerza SOLO la 2a llamada (rev-list) a fallar, mientras la 1a
        (log --grep) corre de verdad contra un repo valido y encuentra el
        commit de consolidacion real -- prueba el 2o breadcrumb de forma
        independiente del primero, delegando siempre a la funcion run_git
        REAL (nunca una reimplementacion del print).
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f4be context(consolidation): memoria consolidada")
        _commit(repo, "chore: regular 1")

        broken = _make_broken_dir(tmp_path, "not_a_repo_2")
        real_run_git = git_helpers.run_git

        def _selective_fail(args, **kwargs):
            if args and args[0] == "rev-list":
                kwargs["cwd"] = broken
            return real_run_git(args, **kwargs)

        monkeypatch.setattr(git_helpers, "run_git", _selective_fail)

        count = git_helpers.commits_since_last_consolidation(cwd=repo)

        assert count == 0, (
            f"El fallo de rev-list debe fail-safe a 0 (no al sentinel, porque la "
            f"1a llamada SI encontro un commit de consolidacion), devolvio {count!r}"
        )
        captured = capsys.readouterr()
        assert "[git_helpers] git 'rev-list' exited 128" in captured.err, (
            f"Se esperaba breadcrumb de la 2a llamada (rev-list) en stderr, se obtuvo: {captured.err!r}"
        )

    def test_anti_vacuity_valid_repo_returns_real_count_with_clean_stderr(self, tmp_path, capsys):
        """Anti-vacuidad (mecanismo A, ambas llamadas): un repo sano con
        commit de consolidacion y N commits posteriores debe devolver
        exactamente N Y dejar stderr limpio.
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f4be context(consolidation): memoria consolidada")
        for i in range(3):
            _commit(repo, f"chore: regular {i}")

        count = git_helpers.commits_since_last_consolidation(cwd=repo)

        assert count == 3, f"Se esperaban 3 commits desde consolidacion, se obtuvo {count!r}"
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr debe estar limpio en exito, se obtuvo: {captured.err!r}"


# ── 4/5. lib/bootstrap_commits.py:139,156 -- scan_recent_commits() ─────────

class TestScanRecentCommitsBreadcrumb:
    """Dos call sites independientes de log_stderr_on_failure=True dentro
    de la MISMA funcion: la 1a llamada (log %h/%aI/%s/%b) y la 2a (log
    %h/%an, solo autores) -- distinguibles por el numero de separadores
    \\x1f en su propio --pretty=format literal (2 vs 1).
    """

    def test_first_call_failure_breadcrumb_and_none(self, tmp_path, monkeypatch, capsys):
        broken = _make_broken_dir(tmp_path)
        monkeypatch.chdir(broken)

        result = bootstrap_commits.scan_recent_commits(depth=20)

        assert result is None, f"Fallo total de git debe fail-safe a None, devolvio {result!r}"
        captured = capsys.readouterr()
        assert "[git_helpers] git 'log' exited 128" in captured.err, (
            f"Se esperaba breadcrumb de la 1a llamada (log) en stderr, se obtuvo: {captured.err!r}"
        )

    def test_second_call_failure_breadcrumb_and_degraded_authors(self, tmp_path, monkeypatch, capsys):
        """Fuerza SOLO la 2a llamada (autores) a fallar, mientras la 1a
        corre de verdad contra un repo valido -- prueba el 2o breadcrumb de
        forma independiente Y prueba la forma exacta de la degradacion:
        author='' por commit (no crash, no None -- el 'count' de la 1a
        llamada queda intacto).
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "chore: alpha")
        _commit(repo, "chore: beta")
        monkeypatch.chdir(repo)

        broken = _make_broken_dir(tmp_path, "not_a_repo_2")
        real_run_git = bootstrap_commits.run_git

        def _selective_fail(args, **kwargs):
            pretty = next((a for a in args if a.startswith("--pretty=format:")), "")
            if pretty.count("\x1f") == 1:  # 2a llamada: %h\x1f%an unicamente
                kwargs["cwd"] = broken
            return real_run_git(args, **kwargs)

        monkeypatch.setattr(bootstrap_commits, "run_git", _selective_fail)

        result = bootstrap_commits.scan_recent_commits(depth=20)

        assert result is not None, "La 1a llamada tuvo exito -- no debe devolver None"
        assert result["count"] == 3, (
            f"'count' viene de la 1a llamada (no afectada), incluye el commit 'init' de "
            f"_make_repo, se esperaban 3, se obtuvo {result['count']!r}"
        )
        assert result["authors"] == {"": 3}, (
            f"Con la llamada de autores rota, TODOS los commits deben degradar a "
            f"author='' (no crash, no None) -- se obtuvo {result['authors']!r}"
        )
        assert all(c["author"] == "" for c in result["recent"]), (
            f"Cada commit en 'recent' debe tener author='' -- se obtuvo {result['recent']!r}"
        )
        captured = capsys.readouterr()
        assert "[git_helpers] git 'log' exited 128" in captured.err, (
            f"Se esperaba breadcrumb de la 2a llamada en stderr, se obtuvo: {captured.err!r}"
        )

    def test_anti_vacuity_valid_repo_returns_real_authors_with_clean_stderr(self, tmp_path, monkeypatch, capsys):
        """Anti-vacuidad (mecanismo A, ambas llamadas): un repo sano debe
        devolver el autor REAL (no '') Y dejar stderr limpio.
        """
        repo = _make_repo(tmp_path)
        git_cmd(["config", "user.name", "Alice"], repo)
        git_cmd(["config", "user.email", "alice@test.com"], repo)
        _commit(repo, "chore: alpha")
        monkeypatch.chdir(repo)

        result = bootstrap_commits.scan_recent_commits(depth=20)

        assert result is not None
        assert result["count"] == 2
        assert result["authors"].get("Alice") == 1, (
            f"Se esperaba el autor real 'Alice', se obtuvo {result['authors']!r}"
        )
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr debe estar limpio en exito, se obtuvo: {captured.err!r}"


# ── 8. lib/boot_memory.py:181 -- extract_memory() (mecanismo B: print manual) ─

class TestExtractMemoryBreadcrumb:
    """extract_memory() NO usa el kwarg log_stderr_on_failure de run_git
    (varios dobles de test en este repo tienen firma fija sin **kwargs,
    documentado en el propio codigo) -- imprime el breadcrumb el mismo,
    manualmente, solo con el rc (sin texto de stderr de git). Sin
    parametro de cwd -- depende del cwd ambiente del proceso.
    """

    def test_git_log_failure_leaves_breadcrumb_and_empty_dict(self, tmp_path, monkeypatch, capsys):
        broken = _make_broken_dir(tmp_path)
        monkeypatch.chdir(broken)

        result = boot_memory.extract_memory()

        assert result == {}, f"extract_memory() debe fail-safe a {{}}, devolvio {result!r}"
        captured = capsys.readouterr()
        assert "[boot_memory] extract_memory(): git log exited 128" in captured.err, (
            f"Se esperaba breadcrumb manual en stderr, se obtuvo: {captured.err!r}"
        )

    def test_anti_vacuity_valid_repo_returns_real_memory_with_clean_stderr(self, tmp_path, monkeypatch, capsys):
        """Anti-vacuidad (mecanismo B): un repo sano debe devolver memoria
        real (no {}) Y dejar stderr limpio.
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f9ed decision(issue61test): use X", "Decision: use X over Y")
        monkeypatch.chdir(repo)

        result = boot_memory.extract_memory()

        assert result != {}, "Un repo con un commit Decision real no debe devolver {}"
        assert "decisions" in result
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr debe estar limpio en exito, se obtuvo: {captured.err!r}"


# ── 9. lib/boot_memory.py:403 -- extract_glossary() (mecanismo B) ──────────

class TestExtractGlossaryBreadcrumb:
    """Mismo mecanismo de print manual que extract_memory() arriba, call
    site independiente.
    """

    def test_git_log_failure_leaves_breadcrumb_and_empty_lists(self, tmp_path, monkeypatch, capsys):
        broken = _make_broken_dir(tmp_path)
        monkeypatch.chdir(broken)

        result = boot_memory.extract_glossary()

        assert result == {"decisions": [], "memos": [], "remembers": []}, (
            f"extract_glossary() debe fail-safe a listas vacias, devolvio {result!r}"
        )
        captured = capsys.readouterr()
        assert "[boot_memory] extract_glossary(): git log exited 128" in captured.err, (
            f"Se esperaba breadcrumb manual en stderr, se obtuvo: {captured.err!r}"
        )

    def test_anti_vacuity_valid_repo_returns_real_glossary_with_clean_stderr(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path)
        _commit(repo, "\U0001f9ed decision(issue61test): use X", "Decision: use X over Y")
        monkeypatch.chdir(repo)

        result = boot_memory.extract_glossary()

        assert result["decisions"], f"Se esperaba la entrada Decision real, se obtuvo {result!r}"
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr debe estar limpio en exito, se obtuvo: {captured.err!r}"


# ── 6. hooks/precompact-snapshot.py:113 -- extract_memory_from_log() ───────

class TestPrecompactExtractMemoryFromLogBreadcrumb:
    """Fichero con guion, no importable directamente -- se ejecuta como
    subprocess real completo (mismo run_cmd()/PRECOMPACT_SCRIPT que el
    resto de la suite). Canal de fallo real: un repo con `git init` pero
    CERO commits -- pasa el guard is_git_repo() del propio hook (main():
    linea 327) pero `git log -n 30 ...` falla de verdad (rc=128, "does
    not have any commits yet"). Ningun mock: subprocess -> subprocess.
    """

    def test_no_commits_repo_leaves_breadcrumb_and_no_snapshot(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["config", "user.email", "test@test.com"], repo)
        git_cmd(["config", "user.name", "Test"], repo)

        rc, stdout, stderr = run_cmd([sys.executable, PRECOMPACT_SCRIPT], repo)

        assert rc == 0, f"El hook siempre sale 0 (non-blocking). stderr={stderr!r}"
        assert stdout == "", (
            f"Con cero commits, extract_memory_from_log() fail-safea a {{}} y main() "
            f"sale antes de imprimir ningun snapshot -- se obtuvo stdout={stdout!r}"
        )
        assert "[git_helpers] git 'log' exited 128" in stderr, (
            f"Se esperaba breadcrumb en stderr, se obtuvo: {stderr!r}"
        )

    def test_anti_vacuity_valid_repo_produces_snapshot_with_clean_stderr(self, tmp_path):
        repo = str(tmp_path / "repo2")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["config", "user.email", "test@test.com"], repo)
        git_cmd(["config", "user.name", "Test"], repo)
        git_cmd(
            ["commit", "--allow-empty", "-m",
             "\U0001f9ed decision(issue61test): use X\n\nDecision: use X over Y"],
            repo,
        )

        rc, stdout, stderr = run_cmd([sys.executable, PRECOMPACT_SCRIPT], repo)

        assert rc == 0
        assert "use X over Y" in stdout, f"Se esperaba contenido real del snapshot, se obtuvo: {stdout!r}"
        assert stderr == "", f"stderr debe estar limpio en exito, se obtuvo: {stderr!r}"


# ── 7. hooks/precompact-snapshot.py:263 -- format_snapshot() [branch] ──────

_PRECOMPACT_BRANCH_FAILURE_PROBE = """
import sys, os, importlib.util

LIB_DIR = {lib_dir!r}
HOOKS_DIR = {hooks_dir!r}
BROKEN = {broken!r}

sys.path.insert(0, LIB_DIR)

import git_helpers
_real_run_git = git_helpers.run_git


def _fake_run_git(args, **kwargs):
    if args and args[0] == "branch":
        kwargs["cwd"] = BROKEN
    return _real_run_git(args, **kwargs)


git_helpers.run_git = _fake_run_git

spec = importlib.util.spec_from_file_location(
    "precompact_probe", os.path.join(HOOKS_DIR, "precompact-snapshot.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

try:
    mod.main()
except SystemExit:
    pass
"""


class TestPrecompactFormatSnapshotBranchBreadcrumb:
    """format_snapshot()'s propio call site de log_stderr_on_failure=True
    para `git branch --show-current` -- independiente del de
    extract_memory_from_log() arriba, y SOLO alcanzable cuando ya se
    encontro memoria real (has_content True), ya que un fallo del log
    inicial (repo vacio) nunca llega hasta aqui. Repo real + subprocesos
    git reales para todo excepto 'branch', que se redirige a un
    directorio roto via un git_helpers.run_git parcheado ANTES de cargar
    el hook via importlib -- corre en un subprocess Python aislado para
    que el parche jamas contamine el proceso de test principal (mismo
    patron ya usado en este repo para hooks con guion en el nombre).
    """

    def test_branch_call_failure_leaves_breadcrumb_and_omits_branch_line(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["config", "user.email", "test@test.com"], repo)
        git_cmd(["config", "user.name", "Test"], repo)
        git_cmd(
            ["commit", "--allow-empty", "-m",
             "\U0001f9ed decision(issue61test): use X\n\nDecision: use X over Y"],
            repo,
        )

        broken = _make_broken_dir(tmp_path, "not_a_repo")

        script = _PRECOMPACT_BRANCH_FAILURE_PROBE.format(
            lib_dir=LIB_DIR, hooks_dir=HOOKS_DIR, broken=broken,
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )

        assert "use X over Y" in result.stdout, (
            f"El snapshot debe seguir imprimiendo el contenido Decision real "
            f"(solo se omite Branch:) -- se obtuvo stdout={result.stdout!r}"
        )
        assert "Branch:" not in result.stdout, (
            f"Con la llamada de branch fallando, format_snapshot() debe fail-safe "
            f"omitiendo la linea 'Branch:' por completo -- se obtuvo stdout={result.stdout!r}"
        )
        assert "[git_helpers] git 'branch' exited 128" in result.stderr, (
            f"Se esperaba breadcrumb en stderr, se obtuvo: {result.stderr!r}"
        )

    def test_anti_vacuity_branch_call_succeeds_includes_branch_line_clean_stderr(self, tmp_path):
        """Anti-vacuidad (mecanismo A, sitio 'branch'): un repo sano donde
        TAMBIEN 'git branch --show-current' funciona debe incluir la
        linea 'Branch:' real Y dejar stderr limpio -- prueba que la
        asercion "Branch: not in stdout" de arriba realmente distingue
        fallo de exito, no que sea vacua.
        """
        repo = str(tmp_path / "repo2")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["config", "user.email", "test@test.com"], repo)
        git_cmd(["config", "user.name", "Test"], repo)
        git_cmd(
            ["commit", "--allow-empty", "-m",
             "\U0001f9ed decision(issue61test): use X\n\nDecision: use X over Y"],
            repo,
        )

        rc, stdout, stderr = run_cmd([sys.executable, PRECOMPACT_SCRIPT], repo)

        assert rc == 0
        assert "Branch:" in stdout, f"Se esperaba la linea Branch: real, se obtuvo: {stdout!r}"
        assert stderr == "", f"stderr debe estar limpio en exito, se obtuvo: {stderr!r}"
