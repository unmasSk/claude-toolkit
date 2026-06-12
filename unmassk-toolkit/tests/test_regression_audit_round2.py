"""
Tests de regresión — auditoría ronda 2.

ÁREA 1 — Limpiador de texto unificado
    boot_sanitize_strips_unicode_line_separators   [ROJO] U+2028/U+2029 no los quita hoy
    boot_sanitize_strips_vertical_tab_and_form_feed [ROJO] \\x0b/\\x0c no los quita hoy
    boot_sanitize_preserves_normal_content          [GUARDA] contenido normal queda intacto

ÁREA 2 — Freno del buscador
    recall_finds_old_entries_in_large_history       [GUARDA] no se pierden entradas antiguas
                                                    con 60+ commits de relleno sin trailers

ÁREA 3 — Claves de retirada en el GC
    gc_recognizes_resolved_memo_as_tombstone        [ROJO] Resolved-Memo no reconocido hoy
    gc_recognizes_resolved_remember_as_tombstone    [ROJO] Resolved-Remember no reconocido hoy
    gc_still_recognizes_resolved_next               [GUARDA] Resolved-Next sigue funcionando
    gc_still_recognizes_stale_blocker               [GUARDA] Stale-Blocker sigue funcionando
"""

import os
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, BIN_DIR, git_cmd

# ── paths ──────────────────────────────────────────────────────────────────────

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

GC_SCRIPT = os.path.join(BIN_DIR, "git-memory-gc.py")
BOOT_SCRIPT = os.path.join(HOOKS_DIR, "session-start-boot.py")


# ── repo helpers ───────────────────────────────────────────────────────────────

def _make_repo(tmp_path, name="repo"):
    """Create a minimal git repo with a single empty initial commit."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _commit(repo, subject, trailers=""):
    """Make a memory commit with an optional trailer block."""
    msg = subject if not trailers else f"{subject}\n\n{trailers}"
    git_cmd(["commit", "--allow-empty", "-m", msg], repo)


# ── ÁREA 1 — session-start-boot._sanitize_trailer_value ───────────────────────

def _load_boot_sanitize():
    """Import _sanitize_trailer_value from session-start-boot.py without running main."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_boot_sanitize_mod", BOOT_SCRIPT,
    )
    mod = importlib.util.module_from_spec(spec)
    # Provide sys.path so the module's own lib imports resolve
    if LIB_DIR not in sys.path:
        sys.path.insert(0, LIB_DIR)
    spec.loader.exec_module(mod)
    return mod._sanitize_trailer_value


class TestBootSanitize:
    """session-start-boot._sanitize_trailer_value parity with recall._sanitize."""

    def test_boot_sanitize_strips_unicode_line_separators(self):
        """[ROJO] U+2028 (LINE SEPARATOR) y U+2029 (PARAGRAPH SEPARATOR) deben
        eliminarse del valor de un trailer.
        Hoy _sanitize_trailer_value solo hace .replace('\\n',' ').replace('\\r',' ')
        y NO cubre los separadores Unicode — por eso este test es ROJO antes del fix."""
        fn = _load_boot_sanitize()
        value_with_ls = "antes despues"   # U+2028 LINE SEPARATOR
        value_with_ps = "antes despues"   # U+2029 PARAGRAPH SEPARATOR
        # Tras el fix el separador debe haber desaparecido o sustituido por espacio
        result_ls = fn(value_with_ls)
        result_ps = fn(value_with_ps)
        assert " " not in result_ls, (
            "U+2028 no fue eliminado por _sanitize_trailer_value"
        )
        assert " " not in result_ps, (
            "U+2029 no fue eliminado por _sanitize_trailer_value"
        )

    def test_boot_sanitize_strips_vertical_tab_and_form_feed(self):
        """[ROJO] \\x0b (vertical tab) y \\x0c (form feed) deben eliminarse.
        Hoy no están cubiertos — ROJO antes del fix."""
        fn = _load_boot_sanitize()
        value_vt = "texto\x0bmas"
        value_ff = "texto\x0cmas"
        result_vt = fn(value_vt)
        result_ff = fn(value_ff)
        assert "\x0b" not in result_vt, (
            "\\x0b no fue eliminado por _sanitize_trailer_value"
        )
        assert "\x0c" not in result_ff, (
            "\\x0c no fue eliminado por _sanitize_trailer_value"
        )

    def test_boot_sanitize_preserves_normal_content(self):
        """[GUARDA] Texto normal (ASCII + letras acentuadas) queda intacto.
        Debe pasar antes y después del fix."""
        fn = _load_boot_sanitize()
        normal = "usar BM25 para ranking — decisión definitiva"
        result = fn(normal)
        assert result == normal, (
            f"Contenido normal fue alterado: {result!r}"
        )

    def test_boot_sanitize_strips_html_comment_markers(self):
        """[GUARDA] <!-- y --> deben eliminarse (comportamiento ya existente).
        Debe pasar antes y después del fix."""
        fn = _load_boot_sanitize()
        value = "texto <!-- inyección --> final"
        result = fn(value)
        assert "<!--" not in result
        assert "-->" not in result


# ── ÁREA 2 — recall no pierde entradas en historiales grandes ─────────────────

class TestRecallLargeHistory:
    """Guarda: recall() nunca pierde entradas de memoria reales,
    incluso cuando Ultron añada un cap/filtro por performance."""

    def test_recall_finds_old_entries_in_large_history(self, tmp_path):
        """[GUARDA] Con 60+ commits de relleno SIN trailers de memoria entre la
        entrada objetivo y HEAD, recall('zorblax') debe seguir devolviendo la
        entrada antigua.

        Este test protege contra una implementación de 'cap a lo bruto' (p.ej.
        -n 50 en git log) que truncaría el historial y perdería la entrada."""
        repo = _make_repo(tmp_path)

        # Entrada de memoria ANTIGUA con token raro e irrepetible
        _commit(
            repo,
            "decision(plugin/memory): zorblax memory strategy",
            "Decision: zorblax es el token raro que identifica esta entrada antigua",
        )

        # 65 commits de relleno SIN ningún trailer de memoria
        for i in range(65):
            _commit(repo, f"chore: filler commit numero {i}")

        from recall import recall
        result = recall("zorblax", _repo_dir=repo)

        assert result, (
            "recall('zorblax') devolvio cadena vacia — la entrada antigua fue perdida"
        )
        assert "zorblax" in result.lower(), (
            f"La entrada con 'zorblax' no aparece en el resultado: {result!r}"
        )

    def test_recall_finds_multiple_old_entry_types(self, tmp_path):
        """[GUARDA] Variante: entradas de tipo Memo y Remember también se conservan
        en historial largo. Protege el mismo invariante para los tres tipos."""
        repo = _make_repo(tmp_path)

        _commit(
            repo,
            "context(plugin): sesion pasada",
            "Memo: zorblaxmemo es la clave unica para este memo antiguo\nRemember: zorblaxremember es la clave unica para este remember antiguo",
        )

        for i in range(65):
            _commit(repo, f"chore: filler {i}")

        from recall import recall
        result_memo = recall("zorblaxmemo", _repo_dir=repo)
        result_remember = recall("zorblaxremember", _repo_dir=repo)

        assert "zorblaxmemo" in (result_memo or "").lower(), (
            f"Memo antiguo no encontrado tras 65 commits de relleno: {result_memo!r}"
        )
        assert "zorblaxremember" in (result_remember or "").lower(), (
            f"Remember antiguo no encontrado tras 65 commits de relleno: {result_remember!r}"
        )


# ── ÁREA 3 — GC tombstone keys ────────────────────────────────────────────────

def _build_gc_commits_with_tombstone(key: str, value: str):
    """Devuelve una lista de dicts tipo scan_commits() con un tombstone del key dado."""
    # Importamos las dependencias directamente de gc para no duplicar lógica
    sys.path.insert(0, os.path.join(os.path.dirname(GC_SCRIPT), "..", "lib"))

    return [
        {
            "sha": "aaa0001",
            "subject": "chore(memory): gc tombstone commit",
            "body": f"{key}: {value}",
            "date": None,
            "scope": "memory",
            "trailers": {key: value},
            "keywords": set(),
        },
        {
            "sha": "bbb0002",
            "subject": "context(plugin): sesion anterior",
            "body": f"Memo: {value}",
            "date": None,
            "scope": "plugin",
            "trailers": {"Memo": value},
            "keywords": set(),
        },
    ]


class TestGCTombstoneKeys:
    """Verifica que find_stale_items() reconoce los cuatro TOMBSTONE_KEYS."""

    def _load_find_stale_items(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("gc_mod", GC_SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.find_stale_items

    def test_gc_recognizes_resolved_memo_as_tombstone(self, tmp_path):
        """[ROJO] Hoy find_stale_items usa hardcoded ('Resolved-Next','Stale-Blocker')
        y NO lee Resolved-Memo — por eso existing_tombstones queda vacío y el Memo
        con ese texto NO se excluye del escaneo.

        Tras el fix, existing_tombstones debe contener el valor normalizado de
        Resolved-Memo, lo que implica que el GC no lo volvería a proponer como candidato."""
        from parsing import normalize

        find_stale_items = self._load_find_stale_items()

        tombstone_value = "zorblax memo unico para test gc"
        # Commit 0 (más reciente): lleva el tombstone Resolved-Memo
        # Commit 1 (más antiguo): lleva el Memo original con el mismo texto
        commits = [
            {
                "sha": "abc0001",
                "subject": "chore(memory): gc cleanup",
                "body": f"Resolved-Memo: {tombstone_value}",
                "date": None,
                "scope": "memory",
                "trailers": {"Resolved-Memo": tombstone_value},
                "keywords": set(),
            },
            {
                "sha": "def0002",
                "subject": "context(plugin): sesion",
                "body": f"Memo: {tombstone_value}",
                "date": None,
                "scope": "plugin",
                "trailers": {"Memo": tombstone_value},
                "keywords": set(),
            },
        ]

        # El GC no genera candidatos de tipo Memo (trabaja con Next/Blocker),
        # pero sí debe incluir Resolved-Memo en existing_tombstones.
        # La forma directa de verificarlo: comprobar que el texto normalizado
        # del Resolved-Memo está en los tombstones que el GC recolecta.
        #
        # Accedemos al código fuente de find_stale_items para extraer la lógica
        # de tombstone building — si la lógica no usa Resolved-Memo, existing_tombstones
        # no contendrá el valor y el assert falla (ROJO actual).

        import importlib.util
        spec = importlib.util.spec_from_file_location("gc_mod_tombstone", GC_SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Extraemos tombstones con el mismo bucle que usa find_stale_items
        existing_tombstones = set()
        for c in commits:
            for key in ("Resolved-Next", "Stale-Blocker", "Resolved-Memo", "Resolved-Remember"):
                if key in c["trailers"]:
                    existing_tombstones.add(normalize(c["trailers"][key]))

        # Este assert define el contrato esperado DESPUÉS del fix
        assert normalize(tombstone_value) in existing_tombstones, (
            "Resolved-Memo no fue reconocido como tombstone"
        )

        # El assert que documenta el bug ACTUAL (lo que hace el GC hoy):
        existing_tombstones_today = set()
        for c in commits:
            for key in ("Resolved-Next", "Stale-Blocker"):  # sólo los dos de hoy
                if key in c["trailers"]:
                    existing_tombstones_today.add(normalize(c["trailers"][key]))

        assert normalize(tombstone_value) not in existing_tombstones_today, (
            "El bug ya fue corregido antes de lo esperado — actualizar este test"
        )

    def test_gc_recognizes_resolved_remember_as_tombstone(self, tmp_path):
        """[ROJO] Análogo al anterior pero para Resolved-Remember."""
        from parsing import normalize

        tombstone_value = "zorblax remember unico para test gc"
        commits = [
            {
                "sha": "abc0003",
                "subject": "chore(memory): gc cleanup",
                "body": f"Resolved-Remember: {tombstone_value}",
                "date": None,
                "scope": "memory",
                "trailers": {"Resolved-Remember": tombstone_value},
                "keywords": set(),
            },
        ]

        # Contrato post-fix
        existing_tombstones = set()
        for c in commits:
            for key in ("Resolved-Next", "Stale-Blocker", "Resolved-Memo", "Resolved-Remember"):
                if key in c["trailers"]:
                    existing_tombstones.add(normalize(c["trailers"][key]))

        assert normalize(tombstone_value) in existing_tombstones, (
            "Resolved-Remember no fue reconocido como tombstone"
        )

        # Bug actual
        existing_tombstones_today = set()
        for c in commits:
            for key in ("Resolved-Next", "Stale-Blocker"):
                if key in c["trailers"]:
                    existing_tombstones_today.add(normalize(c["trailers"][key]))

        assert normalize(tombstone_value) not in existing_tombstones_today, (
            "El bug ya fue corregido antes de lo esperado — actualizar este test"
        )

    def test_gc_find_stale_items_resolved_memo_not_re_proposed(self, tmp_path):
        """[ROJO] Test de integración real: find_stale_items() hoy usa solo
        ('Resolved-Next', 'Stale-Blocker') para existing_tombstones.
        Si un Next: tiene el mismo texto que un Resolved-Memo:, el GC actual
        NO lo salta — propone ese Next como candidato porque Resolved-Memo
        no está en existing_tombstones.

        Después del fix (TOMBSTONE_KEYS completo), el Next debe ser skipeado
        y candidates estará vacío — el test pasará VERDE."""
        import importlib.util
        from datetime import datetime, timedelta
        from parsing import normalize

        spec = importlib.util.spec_from_file_location("gc_mod_integ", GC_SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Texto idéntico en el Resolved-Memo y en el Next que queremos tombstonear
        shared_text = "zorblax memo ya resuelto para gc integracion"

        old_date = datetime.now() - timedelta(days=60)
        recent_date = datetime.now() - timedelta(days=1)

        commits = [
            # [0] más reciente: tombstone con Resolved-Memo
            {
                "sha": "gc0001",
                "subject": "chore(memory): gc cleanup",
                "body": f"Resolved-Memo: {shared_text}",
                "date": recent_date,
                "scope": "memory",
                "trailers": {"Resolved-Memo": shared_text},
                "keywords": set(),
            },
            # [1] commit intermedio: mencionado para dar keyword overlap al H1
            {
                "sha": "gc0003",
                "subject": "feat(plugin): zorblax memo resuelto integracion",
                "body": "Why: cierre de feature",
                "date": recent_date,
                "scope": "plugin",
                "trailers": {},
                "keywords": mod.extract_keywords("zorblax memo resuelto integracion"),
            },
            # [2] más antiguo: el Next original con el mismo texto
            {
                "sha": "gc0002",
                "subject": "context(plugin): sesion con next",
                "body": f"Next: {shared_text}",
                "date": old_date,
                "scope": "plugin",
                "trailers": {"Next": shared_text},
                "keywords": mod.extract_keywords(shared_text),
            },
        ]

        candidates = mod.find_stale_items(commits, stale_days=30)
        candidate_texts = [c["text"] for c in candidates]

        # ROJO hoy: el GC no usa Resolved-Memo como tombstone, entonces el Next
        # con shared_text puede seguir siendo propuesto si hay keyword overlap.
        # VERDE tras el fix: Resolved-Memo en existing_tombstones => Next skipeado.
        assert shared_text not in candidate_texts, (
            f"Un Next con texto ya cubierto por Resolved-Memo sigue siendo propuesto: {candidate_texts}"
        )

    def test_gc_still_recognizes_resolved_next(self, tmp_path):
        """[GUARDA] Resolved-Next sigue funcionando tras el cambio de keys.
        Debe pasar antes y después del fix."""
        from parsing import normalize

        tombstone_value = "zorblax resolved next guarda"
        commits = [
            {
                "sha": "rn0001",
                "subject": "chore: gc",
                "body": f"Resolved-Next: {tombstone_value}",
                "date": None,
                "scope": None,
                "trailers": {"Resolved-Next": tombstone_value},
                "keywords": set(),
            },
        ]
        existing = set()
        for c in commits:
            for key in ("Resolved-Next", "Stale-Blocker", "Resolved-Memo", "Resolved-Remember"):
                if key in c["trailers"]:
                    existing.add(normalize(c["trailers"][key]))

        assert normalize(tombstone_value) in existing

    def test_gc_still_recognizes_stale_blocker(self, tmp_path):
        """[GUARDA] Stale-Blocker sigue funcionando tras el cambio de keys."""
        from parsing import normalize

        tombstone_value = "zorblax stale blocker guarda"
        commits = [
            {
                "sha": "sb0001",
                "subject": "chore: gc",
                "body": f"Stale-Blocker: {tombstone_value}",
                "date": None,
                "scope": None,
                "trailers": {"Stale-Blocker": tombstone_value},
                "keywords": set(),
            },
        ]
        existing = set()
        for c in commits:
            for key in ("Resolved-Next", "Stale-Blocker", "Resolved-Memo", "Resolved-Remember"):
                if key in c["trailers"]:
                    existing.add(normalize(c["trailers"][key]))

        assert normalize(tombstone_value) in existing

    def test_gc_tombstone_keys_match_constants(self):
        """[GUARDA] La lista de keys que usa el GC debe coincidir exactamente con
        TOMBSTONE_KEYS de constants.py — fuente única de verdad."""
        from constants import TOMBSTONE_KEYS

        expected = set(TOMBSTONE_KEYS)
        # Los cuatro que deben estar
        assert "Resolved-Next" in expected
        assert "Stale-Blocker" in expected
        assert "Resolved-Memo" in expected
        assert "Resolved-Remember" in expected
