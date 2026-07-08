"""
Contract tests (test-first) para el disparador por contador de commits
del consolidador de memoria.

ESTADO ESPERADO: todos los tests de CONTRATO deben FALLAR en rojo
porque ni el helper commits_since_last_consolidation() ni el bloque
CONSOLIDATE: en session-start-boot.py existen todavía.

Ultron implementa; Dante verifica en el pase de hardening.

Casos:
  01  ≥50 commits desde última consolidación → CONSOLIDATE: aparece en boot
  02  <50 commits desde consolidación previa → NO aparece CONSOLIDATE:
  03  context(consolidation) reciente resetea el contador (<umbral → sin aviso)
  04  context(OTRO_SCOPE) NO resetea el contador (no es consolidación)
  05  Override GIT_MEMORY_CONSOLIDATION_THRESHOLD=5 → dispara a los 5 commits
  06  Override inválido (no numérico) → cae al default 50, sin crashear
  07  Historial largo (300 commits, consolidación al principio) → cuenta de verdad
  08  Primer aviso: repo sin ningún context(consolidation) → aviso SÍ aparece
  09  Helper directo: commits_since_last_consolidation() devuelve conteo correcto
"""

import os
import sys

import pytest

from conftest import (
    SOURCE_ROOT, HOOKS_DIR, INSTALL,
    run_cmd, git_cmd, write_file, run_script,
)

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
BOOT_HOOK = os.path.join(HOOKS_DIR, "session-start-boot.py")

# ── Helpers de repo ────────────────────────────────────────────────────────

def _make_bare_repo(tmp_path, name="repo"):
    """Repo mínimo con git user configurado (sin install)."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _commit_empty(repo, msg):
    """Commit vacío con el mensaje dado."""
    git_cmd(["commit", "--allow-empty", "-m", msg], repo)


def _add_regular_commits(repo, n):
    """Añade n commits ordinarios (no-memoria, no-consolidación)."""
    for i in range(n):
        _commit_empty(repo, f"chore: regular commit {i}")


def _add_consolidation_commit(repo):
    """Añade un commit context(consolidation) que debe contar como marca."""
    _commit_empty(repo, "💾 context(consolidation): memoria consolidada")


def _run_boot(repo, extra_env=None):
    """Ejecuta session-start-boot.py y devuelve stdout.

    NOTA (corrección de contrato, Bex 2026-07-04): stdout ahora es siempre
    un banner corto (STATUS/BRANCH/puntero/BOOT COMPLETE). El bloque
    CONSOLIDATE: que estos tests verifican vive solo en el archivo de log
    completo — usar _read_boot_log(repo) tras esta llamada.
    """
    env = {**os.environ, **(extra_env or {})}
    rc, stdout, stderr = run_cmd(
        [sys.executable, BOOT_HOOK],
        repo,
        env=extra_env,
    )
    return stdout


# ── Boot-log file helpers (mismo patrón que test_boot_output.py) ──────────

BOOT_LOG_REL_PARTS = (".claude", ".unmassk", "boot-log-latest.txt")


def _boot_log_path(repo):
    return os.path.join(repo, *BOOT_LOG_REL_PARTS)


def _read_boot_log(repo):
    with open(_boot_log_path(repo), encoding="utf-8") as f:
        return f.read()


# ── Caso 01 — ≥50 commits desde consolidación → CONSOLIDATE: aparece ──────

class TestConsolidateTriggerAboveThreshold:

    def test_01_consolidate_block_appears_when_50_commits_since_last(self, tmp_path):
        """≥50 commits desde el último context(consolidation) → boot emite CONSOLIDATE:."""
        repo = _make_bare_repo(tmp_path)
        # Consolidación previa
        _add_consolidation_commit(repo)
        # 50 commits normales desde entonces
        _add_regular_commits(repo, 50)
        _run_boot(repo)
        content = _read_boot_log(repo)
        assert "CONSOLIDATE:" in content, (
            f"Se esperaba bloque CONSOLIDATE: con 50 commits desde la consolidación.\n"
            f"Boot log:\n{content}"
        )


# ── Caso 02 — <50 commits → NO aparece CONSOLIDATE: ──────────────────────

class TestConsolidateTriggerBelowThreshold:

    def test_02_no_consolidate_block_when_below_threshold(self, tmp_path):
        """<50 commits desde context(consolidation) → NO debe aparecer CONSOLIDATE:.

        El test verifica DOS contratos encadenados:
          a) el helper reporta el conteo correcto (<50)
          b) el boot NO emite CONSOLIDATE: cuando el conteo es < umbral

        Ambos contratos son rojos ahora: el helper no existe.
        """
        repo = _make_bare_repo(tmp_path)
        _add_consolidation_commit(repo)
        # 10 commits normales (< 50)
        _add_regular_commits(repo, 10)

        # Verificación precondición: el helper debe reportar 10
        # (esto falla en rojo porque el helper no existe)
        import importlib.util
        import subprocess as _sp
        spec = importlib.util.spec_from_file_location(
            "_gh_t02", os.path.join(LIB_DIR, "git_helpers.py"))
        mod = importlib.util.module_from_spec(spec)

        def _rg(args, timeout=10, cwd=None):
            env = {**os.environ, "GIT_DIR": os.path.join(repo, ".git"),
                   "GIT_WORK_TREE": repo}
            r = _sp.run(["git"] + args, capture_output=True, text=True, encoding='utf-8',
                        cwd=repo, env=env, timeout=timeout)
            return r.returncode, r.stdout.strip()

        spec.loader.exec_module(mod)
        mod.run_git = _rg
        count = mod.commits_since_last_consolidation()
        assert count == 10, f"Helper debería devolver 10, devolvió {count!r}"

        # Si el helper existe y devuelve 10, el boot NO debe emitir CONSOLIDATE:
        _run_boot(repo)
        content = _read_boot_log(repo)
        assert "CONSOLIDATE:" not in content, (
            f"NO se esperaba bloque CONSOLIDATE: con solo 10 commits desde la consolidación.\n"
            f"Boot log:\n{content}"
        )


# ── Caso 03 — context(consolidation) reciente resetea el contador ─────────

class TestConsolidateCounterResets:

    def test_03_recent_consolidation_resets_counter(self, tmp_path):
        """Tras context(consolidation) reciente, commits posteriores <50 → sin aviso.

        Verifica encadenado:
          a) el helper reporta 5 (solo cuenta desde la SEGUNDA consolidación)
          b) el boot NO emite CONSOLIDATE: cuando el conteo es < umbral
        """
        repo = _make_bare_repo(tmp_path)
        # Consolidación antigua + muchos commits
        _add_consolidation_commit(repo)
        _add_regular_commits(repo, 60)
        # Segunda consolidación (reciente) — debe ser la que cuenta
        _add_consolidation_commit(repo)
        # 5 commits después de la consolidación reciente
        _add_regular_commits(repo, 5)

        # Precondición: helper reporta 5 (desde la segunda consolidación)
        import importlib.util
        import subprocess as _sp
        spec = importlib.util.spec_from_file_location(
            "_gh_t03", os.path.join(LIB_DIR, "git_helpers.py"))
        mod = importlib.util.module_from_spec(spec)

        def _rg(args, timeout=10, cwd=None):
            env = {**os.environ, "GIT_DIR": os.path.join(repo, ".git"),
                   "GIT_WORK_TREE": repo}
            r = _sp.run(["git"] + args, capture_output=True, text=True, encoding='utf-8',
                        cwd=repo, env=env, timeout=timeout)
            return r.returncode, r.stdout.strip()

        spec.loader.exec_module(mod)
        mod.run_git = _rg
        count = mod.commits_since_last_consolidation()
        assert count == 5, (
            f"El helper debe contar solo desde la ÚLTIMA consolidación (5 commits), "
            f"devolvió {count!r}"
        )

        # Si el helper existe y devuelve 5, el boot NO debe emitir CONSOLIDATE:
        _run_boot(repo)
        content = _read_boot_log(repo)
        assert "CONSOLIDATE:" not in content, (
            f"La consolidación reciente debe resetear el contador. "
            f"Con solo 5 commits después no debe aparecer CONSOLIDATE:.\n"
            f"Boot log:\n{content}"
        )


# ── Caso 04 — context(OTRO_SCOPE) NO cuenta como consolidación ────────────

class TestNonConsolidationContextIgnored:

    def test_04_context_other_scope_does_not_reset_counter(self, tmp_path):
        """context(plugin) u otro scope NO resetea el contador de consolidación."""
        repo = _make_bare_repo(tmp_path)
        # Consolidación genuina
        _add_consolidation_commit(repo)
        # 30 commits normales
        _add_regular_commits(repo, 30)
        # context() con scope DISTINTO (no es consolidación)
        _commit_empty(repo, "💾 context(plugin): cierre de sesión")
        # 20 commits más (total desde consolidación = 30 + 1 + 20 = 51 > 50)
        _add_regular_commits(repo, 20)
        _run_boot(repo)
        content = _read_boot_log(repo)
        assert "CONSOLIDATE:" in content, (
            f"context(plugin) NO debe resetear el contador. "
            f"Con 51 commits desde la consolidación real debe aparecer CONSOLIDATE:.\n"
            f"Boot log:\n{content}"
        )


# ── Caso 05 — Override de umbral mediante variable de entorno ──────────────

class TestConsolidateThresholdOverride:

    def test_05_env_override_lowers_threshold(self, tmp_path):
        """GIT_MEMORY_CONSOLIDATION_THRESHOLD=5 dispara el aviso a los 5 commits."""
        repo = _make_bare_repo(tmp_path)
        _add_consolidation_commit(repo)
        _add_regular_commits(repo, 5)  # exactamente el override
        env = {**os.environ, "GIT_MEMORY_CONSOLIDATION_THRESHOLD": "5"}
        rc, stdout, stderr = run_cmd([sys.executable, BOOT_HOOK], repo, env=env)
        content = _read_boot_log(repo)
        assert "CONSOLIDATE:" in content, (
            f"Con threshold=5 y 5 commits desde consolidación debe aparecer CONSOLIDATE:.\n"
            f"Boot log:\n{content}"
        )


# ── Caso 06 — Override inválido → cae al default 50, sin crashear ─────────

class TestConsolidateInvalidOverride:

    def test_06_invalid_env_override_falls_back_to_default(self, tmp_path):
        """Override no numérico → default 50; boot no crashea.

        Verifica encadenado:
          a) el helper existe y devuelve 10 para 10 commits desde consolidación
          b) el boot con override inválido NO emite CONSOLIDATE: (usa default=50)
          c) no hay excepción no manejada (sin Traceback en stderr)
        """
        repo = _make_bare_repo(tmp_path)
        _add_consolidation_commit(repo)
        # 10 commits: por debajo del default 50
        _add_regular_commits(repo, 10)

        # Precondición: helper existe y devuelve 10
        import importlib.util
        import subprocess as _sp
        spec = importlib.util.spec_from_file_location(
            "_gh_t06", os.path.join(LIB_DIR, "git_helpers.py"))
        mod = importlib.util.module_from_spec(spec)

        def _rg(args, timeout=10, cwd=None):
            env_inner = {**os.environ, "GIT_DIR": os.path.join(repo, ".git"),
                         "GIT_WORK_TREE": repo}
            r = _sp.run(["git"] + args, capture_output=True, text=True, encoding='utf-8',
                        cwd=repo, env=env_inner, timeout=timeout)
            return r.returncode, r.stdout.strip()

        spec.loader.exec_module(mod)
        mod.run_git = _rg
        count = mod.commits_since_last_consolidation()
        assert count == 10, f"Helper debería devolver 10, devolvió {count!r}"

        env = {**os.environ, "GIT_MEMORY_CONSOLIDATION_THRESHOLD": "not-a-number"}
        rc, stdout, stderr = run_cmd([sys.executable, BOOT_HOOK], repo, env=env)
        content = _read_boot_log(repo)
        # No debe crashear
        assert "CONSOLIDATE:" not in content, (
            f"Con override inválido y 10 commits (< default 50) NO debe aparecer CONSOLIDATE:.\n"
            f"Boot log:\n{content}"
        )
        assert "Traceback" not in stderr, (
            f"Override inválido no debe generar excepción no manejada.\n"
            f"Stderr:\n{stderr}"
        )

    def test_06b_invalid_override_triggers_at_default_threshold(self, tmp_path):
        """Override no numérico con ≥50 commits → sí aparece CONSOLIDATE: (usa default)."""
        repo = _make_bare_repo(tmp_path)
        _add_consolidation_commit(repo)
        _add_regular_commits(repo, 50)
        env = {**os.environ, "GIT_MEMORY_CONSOLIDATION_THRESHOLD": "abc"}
        rc, stdout, stderr = run_cmd([sys.executable, BOOT_HOOK], repo, env=env)
        content = _read_boot_log(repo)
        assert "CONSOLIDATE:" in content, (
            f"Con override inválido y ≥50 commits debe usar default 50 → CONSOLIDATE: aparece.\n"
            f"Boot log:\n{content}"
        )
        assert "Traceback" not in stderr


# ── Caso 07 — Historial largo: la consolidación al principio cuenta ────────

class TestConsolidateLongHistory:

    def test_07_long_history_counts_correctly(self, tmp_path):
        """300 commits con consolidación al inicio → el conteo no se trunca, aviso aparece."""
        repo = _make_bare_repo(tmp_path)
        # Consolidación al inicio del historial
        _add_consolidation_commit(repo)
        # 300 commits normales después
        _add_regular_commits(repo, 300)
        _run_boot(repo)
        content = _read_boot_log(repo)
        assert "CONSOLIDATE:" in content, (
            f"Con 300 commits desde la consolidación (historial largo) debe aparecer CONSOLIDATE:.\n"
            f"El helper no debe truncarse en una ventana corta.\n"
            f"Boot log:\n{content}"
        )


# ── Caso 08 — Sin ningún context(consolidation) → sentinel → aviso ────────

class TestConsolidateFirstTimeNoHistory:

    def test_08_no_consolidation_ever_triggers_first_warning(self, tmp_path):
        """Repo sin ningún context(consolidation) → sentinel alto → CONSOLIDATE: aparece."""
        repo = _make_bare_repo(tmp_path)
        # Solo commits ordinarios, NUNCA un context(consolidation)
        _commit_empty(repo, "🧭 decision(auth): use JWT\n\nDecision: JWT\nWhy: stateless")
        _commit_empty(repo, "📌 memo(api): prefer async\n\nMemo: async/await everywhere")
        _add_regular_commits(repo, 5)
        _run_boot(repo)
        content = _read_boot_log(repo)
        assert "CONSOLIDATE:" in content, (
            f"Sin ningún context(consolidation) en el historial, el sentinel debe forzar "
            f"el primer aviso de consolidación.\n"
            f"Boot log:\n{content}"
        )


# ── Caso 09 — Helper directo: devuelve conteo correcto ────────────────────

class TestCommitsSinceLastConsolidationHelper:

    def test_09_helper_returns_correct_count(self, tmp_path):
        """commits_since_last_consolidation() cuenta correctamente en un repo montado."""
        repo = _make_bare_repo(tmp_path)
        _add_consolidation_commit(repo)
        # 7 commits ordinarios
        _add_regular_commits(repo, 7)

        # Importar el helper desde lib/git_helpers.py con CWD apuntando al repo de test
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_git_helpers_test",
            os.path.join(LIB_DIR, "git_helpers.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        # Parchear run_git dentro del módulo para que opere en el repo de test
        import subprocess as _sp

        def _patched_run_git(args, timeout=10, cwd=None):
            env = {**os.environ, "GIT_DIR": os.path.join(repo, ".git"), "GIT_WORK_TREE": repo}
            result = _sp.run(
                ["git"] + args,
                capture_output=True, text=True, encoding='utf-8',
                cwd=repo, env=env, timeout=timeout,
            )
            return result.returncode, result.stdout.strip()

        spec.loader.exec_module(mod)
        mod.run_git = _patched_run_git  # monkeypatch en la instancia importada

        count = mod.commits_since_last_consolidation()
        assert count == 7, (
            f"commits_since_last_consolidation() debería devolver 7, devolvió {count!r}.\n"
            f"(El commit de consolidación no cuenta; solo los 7 posteriores.)"
        )

    def test_09b_helper_returns_sentinel_when_no_consolidation(self, tmp_path):
        """Sin context(consolidation) en el historial, el helper devuelve un sentinel alto."""
        repo = _make_bare_repo(tmp_path)
        _add_regular_commits(repo, 5)

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_git_helpers_test2",
            os.path.join(LIB_DIR, "git_helpers.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        import subprocess as _sp

        def _patched_run_git(args, timeout=10, cwd=None):
            env = {**os.environ, "GIT_DIR": os.path.join(repo, ".git"), "GIT_WORK_TREE": repo}
            result = _sp.run(
                ["git"] + args,
                capture_output=True, text=True, encoding='utf-8',
                cwd=repo, env=env, timeout=timeout,
            )
            return result.returncode, result.stdout.strip()

        spec.loader.exec_module(mod)
        mod.run_git = _patched_run_git

        count = mod.commits_since_last_consolidation()
        # Sentinel: debe ser ≥ 50 para forzar el primer aviso
        assert count >= 50, (
            f"Sin context(consolidation) el helper debe devolver un sentinel ≥50, devolvió {count!r}."
        )
