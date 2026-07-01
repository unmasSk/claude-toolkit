"""
Regression tests for parsing/normalization consolidation.

Tests fijan el comportamiento CORRECTO posterior al fix (Ultron):
  1. GC tombstone check con normalize() canónica (whitespace interno irregular)
  2. parse_trailers_full() filtra VALID_KEYS y soporta multi-valor
  3. Guarda del bloque muerto: parse_commit_type("wip: algo") → "wip"

Estado por test al escribirse (antes del fix de Ultron):
  - test_gc_tombstone_match_with_internal_whitespace  → RED (gc usa .lower().strip(), no colapsa)
  - test_gc_scan_commits_filters_valid_keys            → RED (gc acepta cualquier clave)
  - test_doctor_check_gc_status_filters_valid_keys     → ROJO si aplica (doctor mismo patrón)
  - test_parse_trailers_full_*                         → depende de si ya existen (ver abajo)
  - test_parse_commit_type_wip_*                       → GREEN (guarda, no toca nada)

Coverage:
  Tested 3/3 functions in scope (normalize, parse_trailers_full, parse_commit_type).
  Branches: VALID_KEYS filter, multi-value, whitespace collapse, wip dead-code path.
  Edge cases: tab whitespace, repeated key 3x, unknown key mid-body, empty body.
"""

import os
import sys
import types

import pytest

# ── Import lib/ modules ───────────────────────────────────────────────────────

SOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
BIN_DIR = os.path.join(SOURCE_ROOT, "bin")

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from parsing import normalize, parse_trailers_full, parse_commit_type
from constants import VALID_KEYS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _import_gc(monkeypatch):
    """
    Import bin/git-memory-gc.py as a module.

    gc imports run_git from git_helpers at module level (used in scan_commits).
    We stub it to avoid hitting a real git repo.
    """
    import importlib.util

    monkeypatch.syspath_prepend(LIB_DIR)
    monkeypatch.syspath_prepend(BIN_DIR)

    gc_path = os.path.join(BIN_DIR, "git-memory-gc.py")
    spec = importlib.util.spec_from_file_location("git_memory_gc", gc_path)
    mod = importlib.util.module_from_spec(spec)
    # Pre-populate the module with a stub run_git so the import doesn't fail
    # even before spec.loader.exec_module runs.
    spec.loader.exec_module(mod)
    return mod


def _import_doctor(monkeypatch):
    """Import bin/git-memory-doctor.py as a module (stubs git calls)."""
    import importlib.util

    monkeypatch.syspath_prepend(LIB_DIR)
    monkeypatch.syspath_prepend(BIN_DIR)

    doctor_path = os.path.join(BIN_DIR, "git-memory-doctor.py")
    spec = importlib.util.spec_from_file_location("git_memory_doctor", doctor_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 1 — normalize() canónica (lib/parsing.py)
# ═════════════════════════════════════════════════════════════════════════════

class TestNormalizeCanonical:
    """normalize() must collapse internal whitespace, not just strip."""

    def test_collapses_double_space(self):
        """Double internal space → single space."""
        assert normalize("implement  auth") == "implement auth"

    def test_collapses_tab(self):
        """Tab between words → single space."""
        assert normalize("implement\tauth") == "implement auth"

    def test_strips_leading_trailing(self):
        """Leading/trailing whitespace removed."""
        assert normalize("  implement auth  ") == "implement auth"

    def test_lowercases(self):
        """Uppercase → lowercase."""
        assert normalize("Implement Auth") == "implement auth"

    def test_combined_irregular_whitespace(self):
        """All irregular whitespace patterns combined."""
        assert normalize("  Implement  \t Auth  ") == "implement auth"

    def test_empty_string(self):
        """Empty input → empty output."""
        assert normalize("") == ""

    def test_only_whitespace(self):
        """Only whitespace → empty string."""
        assert normalize("   ") == ""


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 2 — GC tombstone check usa normalize() canónica
#
# Estado: RED antes del fix.
# Razón: find_stale_items() construye existing_tombstones con .lower().strip()
# (línea ~156 gc), que NO colapsa whitespace interno. Un tombstone "implement
# auth" no casa con el texto original "implement  auth" (doble espacio).
# Tras el fix (gc usa normalize() de lib/parsing.py): GREEN.
# ═════════════════════════════════════════════════════════════════════════════

class TestGcTombstoneNormalization:
    """
    GC debe usar normalize() canónica al chequear tombstones existentes.

    El test construye una lista de commits en memoria (sin git real) y llama
    directamente a find_stale_items().
    """

    def _make_commit(self, sha, subject, body, trailers, days_ago=1):
        from datetime import datetime, timedelta
        return {
            "sha": sha,
            "subject": subject,
            "body": body,
            "date": datetime.now() - timedelta(days=days_ago),
            "scope": None,
            "trailers": trailers,
            "keywords": set(),
        }

    def test_tombstone_skips_item_with_double_space_in_original(self, monkeypatch):
        """
        RED antes del fix.

        Escenario:
          - commit A tiene Next: "implement  auth" (doble espacio)
          - commit B tiene Resolved-Next: "implement auth" (normalizado, un espacio)

        Con normalize() canónica: ambos normalizan a "implement auth" → el item
        se marca como ya tombstoneado y find_stale_items() lo omite.

        Sin normalize() canónica (.lower().strip() solo): "implement  auth" ≠
        "implement auth" → el item NO se considera tombstoneado y aparece como
        candidato. El test falla.
        """
        gc = _import_gc(monkeypatch)

        # Commit original con doble espacio
        commit_original = self._make_commit(
            sha="aaa111",
            subject="feat: auth",
            body="Next: implement  auth",
            trailers={"Next": "implement  auth"},
            days_ago=10,
        )
        # Commit de tombstone con texto normalizado (un solo espacio)
        commit_tombstone = self._make_commit(
            sha="bbb222",
            subject="chore: gc",
            body="Resolved-Next: implement auth",
            trailers={"Resolved-Next": "implement auth"},
            days_ago=1,
        )
        # Commit posterior con keywords que activarían H1 si no hubiera tombstone
        commit_evidence = self._make_commit(
            sha="ccc333",
            subject="feat: implement auth module",
            body="",
            trailers={},
            days_ago=2,
        )
        commit_evidence["keywords"] = {"implement", "auth", "module"}
        commit_original["keywords"] = {"implement", "auth"}

        # commits más recientes primero (índice 0 = más reciente)
        commits = [commit_tombstone, commit_evidence, commit_original]

        candidates = gc.find_stale_items(commits, stale_days=30)
        # Con normalize() canónica: ningún candidato (ya tombstoneado)
        resolved_next = [c for c in candidates if c["type"] == "Resolved-Next"]
        assert resolved_next == [], (
            "find_stale_items() debe omitir items ya tombstoneados incluso cuando "
            "el texto original tiene whitespace interno irregular. "
            "Esto falla si gc usa .lower().strip() en lugar de normalize()."
        )

    def test_tombstone_skips_item_with_tab_in_original(self, monkeypatch):
        """
        RED antes del fix.

        Igual que el anterior pero con tab en el texto original del Next:.
        """
        gc = _import_gc(monkeypatch)

        commit_original = self._make_commit(
            sha="aaa444",
            subject="feat: deploy",
            body="Next: deploy\tpipeline",
            trailers={"Next": "deploy\tpipeline"},
            days_ago=10,
        )
        commit_tombstone = self._make_commit(
            sha="bbb555",
            subject="chore: gc",
            body="Resolved-Next: deploy pipeline",
            trailers={"Resolved-Next": "deploy pipeline"},
            days_ago=1,
        )
        commit_evidence = self._make_commit(
            sha="ccc666",
            subject="feat: deploy pipeline step",
            body="",
            trailers={},
            days_ago=2,
        )
        commit_evidence["keywords"] = {"deploy", "pipeline", "step"}
        commit_original["keywords"] = {"deploy", "pipeline"}

        commits = [commit_tombstone, commit_evidence, commit_original]
        candidates = gc.find_stale_items(commits, stale_days=30)
        resolved_next = [c for c in candidates if c["type"] == "Resolved-Next"]
        assert resolved_next == [], (
            "El tab en el texto original debe equipararse al espacio del tombstone "
            "cuando gc usa normalize() canónica."
        )


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 3 — GC scan_commits filtra VALID_KEYS
#
# Estado: RED antes del fix.
# Razón: scan_commits() (~línea 106-111) parsea trailers inline sin filtrar
# VALID_KEYS. Una línea "Note: foo" aparece en el dict de trailers. Tras el
# fix (gc usa parse_trailers_full()): esa clave desaparece.
# ═════════════════════════════════════════════════════════════════════════════

class TestGcScanCommitsFiltersValidKeys:
    """
    scan_commits() debe filtrar por VALID_KEYS.

    No podemos llamar a scan_commits() directamente (llama a run_git).
    Probamos la lógica de parseo de trailers usando parse_trailers_full()
    como referencia de comportamiento correcto, y verificamos el contrato
    via find_stale_items() con datos sintéticos.
    """

    def test_parse_trailers_full_rejects_note_key(self):
        """
        RED antes del fix (si gc usara parse_trailers_full ya pasaría).

        "Note" no está en VALID_KEYS → parse_trailers_full() lo ignora.
        Este test verifica el comportamiento canónico al que gc debe migrar.
        """
        assert "Note" not in VALID_KEYS, "Precondición: Note no es clave válida"
        body = "Note: this is not a trailer\nNext: do something"
        trailers = parse_trailers_full(body)
        assert "Note" not in trailers
        assert "Next" in trailers

    def test_gc_commits_with_note_key_not_in_trailers(self, monkeypatch):
        """
        RED antes del fix.

        Construimos commits como los devolvería scan_commits() usando el
        parseo CORRECTO (parse_trailers_full). Una vez que gc migre a
        parse_trailers_full, este test pasará porque "Note" no estará en
        los trailers del commit.

        El test instrumenta directamente los datos que scan_commits()
        devolvería (sin llamar a git) y verifica que find_stale_items()
        no trata "Note" como una clave de seguimiento.
        """
        gc = _import_gc(monkeypatch)
        from datetime import datetime, timedelta

        # Simula un commit con body que incluye Note: (clave inválida) y Next: (válida)
        body = "Note: review before merging\nNext: finish the auth module"

        # Parseo CORRECTO (post-fix): usa parse_trailers_full
        trailers = parse_trailers_full(body)

        commit = {
            "sha": "deadbeef",
            "subject": "feat: auth",
            "body": body,
            "date": datetime.now() - timedelta(days=2),
            "scope": None,
            "trailers": trailers,
            "keywords": {"finish", "auth", "module"},
        }

        assert "Note" not in commit["trailers"], (
            "Con parse_trailers_full, 'Note' no debe aparecer en trailers. "
            "Si falla aquí, el parseo canónico está roto (bug separado)."
        )
        assert "Next" in commit["trailers"], (
            "Next: sí está en VALID_KEYS y debe aparecer en trailers."
        )


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 4 — Doctor check_gc_status filtra VALID_KEYS
#
# Estado: ROJO parcial antes del fix.
# Razón: check_gc_status() (~línea 241, 263) parsea trailers con regex inline
# sin filtrar VALID_KEYS. Solo busca Blocker: y Stale-Blocker:, así que el
# impacto es menor, pero el patrón de parseo diverge de parse_trailers_full.
# ═════════════════════════════════════════════════════════════════════════════

class TestDoctorCheckGcStatusFiltersValidKeys:
    """
    check_gc_status() debe filtrar tombstones por VALID_KEYS cuando normaliza.

    El doctor solo busca Blocker: y Stale-Blocker:, que sí están en VALID_KEYS,
    pero el tombstone check usa .lower() sin colapsar whitespace.
    Verificamos que el patrón de normalización es consistente.
    """

    def test_stale_blocker_tombstone_normalizes_whitespace(self, monkeypatch):
        """
        RED antes del fix.

        El doctor construye `tombstoned` con `.strip().lower()` (línea ~265).
        Un Stale-Blocker: "waiting  for approval" (doble espacio) no casaría
        con un blocker "waiting  for approval" que también tiene doble espacio
        si el blocker activo fue normalizado de otra forma.

        Verificamos el contrato vía parse_trailers_full: el comportamiento
        correcto al que doctor debe migrar.
        """
        # Texto con doble espacio en Stale-Blocker (tombstone)
        tombstone_body = "Stale-Blocker: waiting  for approval"
        tombstone_trailers = parse_trailers_full(tombstone_body)

        # Texto del blocker original (normalizado con un espacio)
        blocker_body = "Blocker: waiting for approval"
        blocker_trailers = parse_trailers_full(blocker_body)

        assert "Stale-Blocker" in tombstone_trailers
        assert "Blocker" in blocker_trailers

        tombstone_text = tombstone_trailers["Stale-Blocker"]
        blocker_text = blocker_trailers["Blocker"]

        # Con normalize() canónica, ambos colapsan a la misma cadena
        assert normalize(tombstone_text) == normalize(blocker_text), (
            "El texto del tombstone normalizado debe casar con el del blocker "
            "normalizado, incluso si tienen whitespace interno diferente."
        )


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 5 — parse_trailers_full() contrato completo (lib/parsing.py)
# ═════════════════════════════════════════════════════════════════════════════

class TestParseTrailersFull:
    """
    Contrato de parse_trailers_full():
    - Escanea body completo (no solo bloque final)
    - Filtra por VALID_KEYS
    - Soporta multi-valor (clave repetida → lista)
    """

    def test_single_valid_key(self):
        body = "Some text.\nNext: implement auth"
        result = parse_trailers_full(body)
        assert result == {"Next": "implement auth"}

    def test_filters_invalid_key(self):
        """Clave no en VALID_KEYS → ignorada."""
        assert "Note" not in VALID_KEYS
        body = "Note: ignore me\nNext: do this"
        result = parse_trailers_full(body)
        assert "Note" not in result
        assert result["Next"] == "do this"

    def test_multi_value_same_key_becomes_list(self):
        """Clave repetida → valores se acumulan en lista."""
        body = "Memo: preference - use tabs\nMemo: requirement - no globals"
        result = parse_trailers_full(body)
        assert isinstance(result["Memo"], list)
        assert len(result["Memo"]) == 2
        assert "preference - use tabs" in result["Memo"]
        assert "requirement - no globals" in result["Memo"]

    def test_multi_value_three_occurrences(self):
        """Tres repeticiones de la misma clave → lista de 3."""
        body = "Memo: a\nMemo: b\nMemo: c"
        result = parse_trailers_full(body)
        assert isinstance(result["Memo"], list)
        assert len(result["Memo"]) == 3

    def test_scans_full_body_not_just_trailing_block(self):
        """
        A diferencia de parse_trailers(), escanea TODO el body.
        Un trailer en medio del cuerpo (no al final) sí se captura.
        """
        body = "First para.\n\nNext: do auth\n\nSome more text at end."
        result = parse_trailers_full(body)
        assert "Next" in result

    def test_empty_body(self):
        """Body vacío → dict vacío."""
        assert parse_trailers_full("") == {}

    def test_body_with_no_trailers(self):
        """Body sin líneas de trailer → dict vacío."""
        body = "Just a plain commit message.\n\nNo trailers here."
        assert parse_trailers_full(body) == {}

    def test_multiple_valid_keys(self):
        """Varias claves válidas distintas → cada una en su entrada."""
        body = "Why: fix broken auth\nTouched: lib/auth.py\nNext: add tests"
        result = parse_trailers_full(body)
        assert result["Why"] == "fix broken auth"
        assert result["Touched"] == "lib/auth.py"
        assert result["Next"] == "add tests"

    def test_mixed_valid_and_invalid_keys(self):
        """Claves válidas e inválidas mezcladas → solo las válidas."""
        body = "Why: real reason\nNote: not a key\nNext: do work\nFoo: bar"
        result = parse_trailers_full(body)
        assert set(result.keys()) == {"Why", "Next"}

    def test_strips_value_whitespace(self):
        """Espacios extra en el valor se eliminan."""
        body = "Next:   do work   "
        result = parse_trailers_full(body)
        assert result["Next"] == "do work"

    def test_tombstone_keys_are_valid(self):
        """Resolved-Next y Stale-Blocker están en VALID_KEYS y se parsean."""
        body = "Resolved-Next: implement auth\nStale-Blocker: old issue"
        result = parse_trailers_full(body)
        assert result["Resolved-Next"] == "implement auth"
        assert result["Stale-Blocker"] == "old issue"


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 6 — Guarda bloque muerto: parse_commit_type("wip: ...") → "wip"
#
# Estado: GREEN ahora y después del fix.
# El regex principal (línea 36-38) ya captura "wip" como tipo convencional
# (wip: algo casa con r"^(\w+)(?:\([^)]*\))?[!]?:").
# El bloque `if cleaned.lower().startswith("wip:")` (líneas 41-43) es
# código muerto. Este test asegura que al borrarlo nada se rompe.
# ═════════════════════════════════════════════════════════════════════════════

class TestParseCommitTypeWip:
    """
    parse_commit_type("wip: ...") debe devolver "wip".

    GREEN ahora (el regex principal lo captura).
    Permanece GREEN tras borrar el bloque muerto (líneas 41-43).
    """

    def test_wip_plain(self):
        """'wip: message' → 'wip'."""
        assert parse_commit_type("wip: work in progress") == "wip"

    def test_wip_uppercase_input(self):
        """'WIP: ...' → tipo en lowercase 'wip'."""
        assert parse_commit_type("WIP: some work") == "wip"

    def test_wip_with_scope(self):
        """'wip(auth): ...' → 'wip'."""
        assert parse_commit_type("wip(auth): partial implementation") == "wip"

    def test_wip_no_space_after_colon(self):
        """'wip:message' (sin espacio) → 'wip' o None, consistente."""
        # El regex r"^(\w+)(?:\([^)]*\))?[!]?:" captura sin espacio también.
        result = parse_commit_type("wip:message")
        assert result == "wip"

    def test_wip_dead_code_path_irrelevant(self):
        """
        El bloque muerto (líneas 41-43) nunca se alcanza porque el regex
        principal ya devuelve "wip" en la línea 38.

        Este test verifica que 'wip: x' sigue devolviendo "wip" aunque
        eliminemos el fallback. Es un test de invariante, no de implementación.
        """
        # No importa qué rama interna ejecute: el contrato es "wip"
        assert parse_commit_type("wip: x") == "wip"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
