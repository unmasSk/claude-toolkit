"""
Regression tests for parsing/normalization consolidation.

Retirement note (memoria-v2 cleanup pass): normalize() and bin/git-memory-gc.py
were both retired with the v1 -> v2 memory surgery -- gc.py no longer exists
on disk at all, and normalize() has no successor in lib/parsing.py. Every
test that exercised either one directly (TestNormalizeCanonical,
TestGcTombstoneNormalization, TestDoctorCheckGcStatusFiltersValidKeys, and
the gc-importing half of TestGcScanCommitsFiltersValidKeys) has been removed
along with the two now-unused `_import_gc`/`_import_doctor` loader helpers
that only existed to reach that retired machinery.

What survives here protects functions that are still live in
lib/parsing.py and will keep running once the v2 memory system is done:
  1. parse_trailers_full() filters VALID_KEYS and supports multi-value
  2. Guard for the dead code block: parse_commit_type("wip: algo") -> "wip"
  3. sanitize_trailer_value()'s documented control-byte contract

Coverage:
  Tested 2/2 live functions in scope (parse_trailers_full, parse_commit_type),
  plus sanitize_trailer_value()'s control-byte contract.
  Branches: VALID_KEYS filter, multi-value, wip dead-code path.
  Edge cases: repeated key 3x, unknown key mid-body, empty body.

Added (#72 fix pass, Cerberus finding): TestSanitizeTrailerValueControlByteContract
pins sanitize_trailer_value()'s documented control-byte contract (lib/parsing.py
L194-236). It was left without its own unit test after the 4 attacker-framed
test files (test_control_byte_injection.py, test_security_regression.py,
test_hardlink_reject_guard.py, test_manifest_hardlink_reject.py) that exercised
it indirectly were retired -- integrity coverage, not attacker simulation.
"""

import os
import sys

import pytest

# ── Import lib/ modules ───────────────────────────────────────────────────────

SOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_DIR = os.path.join(SOURCE_ROOT, "lib")

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from parsing import parse_trailers_full, parse_commit_type, sanitize_trailer_value
from constants import VALID_KEYS


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 3 — parse_trailers_full() filtra VALID_KEYS
#
# Origen histórico: este contrato nació para verificar hacia dónde debía
# migrar el scan_commits() de bin/git-memory-gc.py (ya retirado del repo).
# Lo que sigue vivo y protege código real es el contrato de
# parse_trailers_full() en sí: una clave fuera de VALID_KEYS nunca llega al
# dict de trailers.
# ═════════════════════════════════════════════════════════════════════════════

class TestGcScanCommitsFiltersValidKeys:
    """
    parse_trailers_full() debe filtrar por VALID_KEYS.
    """

    def test_parse_trailers_full_rejects_note_key(self):
        """
        "Note" no está en VALID_KEYS → parse_trailers_full() lo ignora.
        """
        assert "Note" not in VALID_KEYS, "Precondición: Note no es clave válida"
        body = "Note: this is not a trailer\nNext: do something"
        trailers = parse_trailers_full(body)
        assert "Note" not in trailers
        assert "Next" in trailers

    def test_gc_commits_with_note_key_not_in_trailers(self):
        """
        Construimos commits con la forma que devolvería un scan de commits,
        usando el parseo canónico (parse_trailers_full) y verificamos que
        "Note" (clave inválida) nunca llega a los trailers del commit.

        Nota (retirada de gc.py): esta prueba antes cargaba
        bin/git-memory-gc.py vía _import_gc() para comparar contra su
        find_stale_items(), pero esa comparación nunca se usaba en el
        cuerpo del test -- solo importaba el módulo y lo descartaba. Con
        gc.py retirado del repo, se quita esa carga muerta; lo que este
        test protege de verdad es parse_trailers_full(), que sigue vivo.
        """
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
        """Varias claves válidas distintas → cada una en su entrada.

        ARREGLADO (PLAN-CONSTRUCCION.md paso 9.3): "Touched" fue retirada
        de VALID_KEYS (ver lib/constants.py) el 2026-08-02 junto con
        "Resolved-Next"/"Stale-Blocker" — sustituida aquí por "Blocker",
        que sigue siendo una clave válida.
        """
        body = "Why: fix broken auth\nBlocker: waiting on review\nNext: add tests"
        result = parse_trailers_full(body)
        assert result["Why"] == "fix broken auth"
        assert result["Blocker"] == "waiting on review"
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

    def test_tombstone_keys_no_longer_valid(self):
        """Resolved-Next y Stale-Blocker ya NO están en VALID_KEYS.

        ARREGLADO (PLAN-CONSTRUCCION.md paso 9.3): el propietario mandó
        retirar estas dos claves de trailer el 2026-08-02 (ver
        lib/constants.py::VALID_KEYS) junto con "Touched" — el test
        original afirmaba lo contrario ("están en VALID_KEYS y se
        parsean"), que era cierto para el sistema de tombstones v1 y ya no
        lo es. Invertido a regresión: si alguna de las dos vuelve a
        colarse en VALID_KEYS sin que sea una decisión deliberada, este
        test lo detecta.
        """
        assert "Resolved-Next" not in VALID_KEYS
        assert "Stale-Blocker" not in VALID_KEYS
        body = "Resolved-Next: implement auth\nStale-Blocker: old issue"
        result = parse_trailers_full(body)
        assert "Resolved-Next" not in result
        assert "Stale-Blocker" not in result


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


class TestSanitizeTrailerValueControlByteContract:
    """
    Pin del contrato documentado en sanitize_trailer_value() (lib/parsing.py
    L194-236): qué bytes de control neutraliza y el regex de la marca
    memory-data.

    Justificación (integridad de render, NO defensa anti-atacante): un byte
    de control -- p.ej. un ANSI escape (\\x1b) pegado sin querer al copiar
    texto desde una terminal o un log -- dentro de un mensaje de commit
    legítimo puede corromper la propia terminal o el render del boot log si
    llega intacto hasta la salida. Este test fija que la función sigue
    neutralizando esos bytes; no simula ningún adversario ni collaborator
    comprometido.

    Restaurado en #72 (fix pass, hallazgo de Cerberus): los 4 ficheros de
    test puramente atacante retirados en el mismo issue cubrían este
    contrato solo indirectamente, dejándolo sin test propio tras su borrado.
    """

    @pytest.mark.parametrize("byte, name", [
        ("\r", "carriage-return"),
        ("\n", "newline"),
        ("\u2028", "line-separator U+2028"),
        ("\u2029", "paragraph-separator U+2029"),
        ("\x0b", "vertical-tab"),
        ("\x0c", "form-feed"),
        ("\x1b", "ANSI-escape"),
        ("\x1c", "file-separator"),
        ("\x1d", "group-separator"),
        ("\x1e", "record-separator"),
        ("\x1f", "unit-separator"),
        ("\x7f", "DEL"),
        ("\x85", "NEL"),
    ])
    def test_control_byte_is_neutralized(self, byte, name):
        """Cada byte de control documentado se reemplaza por espacio, nunca
        sobrevive intacto en el resultado."""
        text = f"before{byte}after"
        result = sanitize_trailer_value(text)
        assert byte not in result, (
            f"{name} ({byte!r}) debe ser neutralizado por "
            f"sanitize_trailer_value(); result={result!r}"
        )
        assert "before" in result and "after" in result, (
            f"el saneo debe preservar el texto legítimo alrededor, no solo "
            f"quitar el byte de control; result={result!r}"
        )

    def test_html_comment_markers_are_stripped(self):
        """'<!--' y '-->' se eliminan del valor."""
        result = sanitize_trailer_value("before<!--comment-->after")
        assert "<!--" not in result and "-->" not in result
        assert "before" in result and "after" in result

    def test_memory_data_fence_marker_open_and_close_are_stripped_case_insensitively(self):
        """La marca de zona memory-data (apertura o cierre) se elimina sin
        distinguir mayúsculas/minúsculas."""
        for marker in (
            "<memory-data>", "</memory-data>",
            "<MEMORY-DATA>", "</MEMORY-DATA>",
            "<Memory-Data>",
        ):
            result = sanitize_trailer_value(f"before{marker}after")
            assert "memory-data" not in result.lower(), (
                f"la marca {marker!r} sobrevivió a sanitize_trailer_value(); "
                f"result={result!r}"
            )

    def test_memory_data_fence_marker_with_interleaved_whitespace_is_stripped(self):
        """El regex de la marca (r"<\\s*/?\\s*memory-data\\s*>") tolera
        espacio en blanco alrededor del token y de la barra de cierre."""
        result = sanitize_trailer_value("before< / memory-data >after")
        assert "memory-data" not in result.lower(), (
            f"una marca con espacio en blanco intercalado sobrevivió; "
            f"result={result!r}"
        )

    def test_normal_text_with_unicode_is_preserved_unchanged(self):
        """Texto normal sin bytes de control ni marcas no se altera."""
        normal = "decision normal sin bytes de control, con unicode café 😀"
        assert sanitize_trailer_value(normal) == normal

    def test_leading_and_trailing_whitespace_is_stripped(self):
        """El resultado final pasa por .strip()."""
        assert sanitize_trailer_value("  padded value  ") == "padded value"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
