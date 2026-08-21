"""
Tests for lib/dod_gate_classify.py -- pure exit-2 (pytest collection error)
classification helpers extracted out of hooks/stop-dod-gate.py [2026-08-20,
Cerberus/Argus Verify pass, size/testability].

Build mode: hardening pass (Verify), after Ultron's fix. Real code exists
now, so this file targets it directly at the UNIT level -- no subprocess,
no real pytest run, just the pure functions against a real filesystem and
(where relevant) a real git repository. This is deliberately NOT going
through hooks/stop-dod-gate.py as a subprocess (that's test_stop_dod_gate.py's
job) -- these tests exist specifically because one branch
(`classify_missing_module` -> "block_present") has no real, portable repro
via genuine pytest ModuleNotFoundError text (see test_stop_dod_gate.py's
module docstring for the empirical reasoning), and because the T1
git-uncertainty regression Cerberus found lives inside `classify_missing_module`
itself, one level below anything a hook-level subprocess test can pin
precisely.

Real dependencies, never mocked: real git repos (via subprocess, same
pattern as the rest of this suite's `git_cmd`/direct subprocess fixtures),
real files on a real filesystem, a real corrupted `.git/index`. Nothing
here replicates git's own logic in a mock -- every git-uncertainty case is
a genuinely broken git repo, produced the same way Cerberus reproduced it
by hand (confirmed empirically before writing these assertions: corrupting
`.git/index` with garbage bytes makes `git rev-parse --is-inside-work-tree`
still succeed while `git ls-files` fails with exit 128 -- "unknown", not
"untracked").

Test surface: 2 public functions with observable branches worth pinning
independently of the hook (`classify_missing_module` five-way return,
`git_tracked_status`'s tri-state as consumed by it). `extract_missing_modules`,
`module_source_candidates`, and `classify_collection_error`'s aggregation
rule are already exercised indirectly via test_stop_dod_gate.py's
real-pytest end-to-end tests; not re-duplicated here except where a
git-real-failure or on-disk-but-reported-missing case needs the shortcut a
hook-level test can't reach.

Not tested: extract_missing_modules's regex parsing in isolation (fully
covered by the real pytest output already flowing through
test_stop_dod_gate.py's TestCollectionError* classes); module_source_candidates
in isolation (pure string/path building, exercised as a side effect of
every classify_missing_module call below).
"""

import os
import sys

from conftest import LIB_DIR, git_cmd

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import dod_gate_classify as dgc
import git_helpers as gh


# ── Helpers ──────────────────────────────────────────────────────────────────

def _write(repo: str, relpath: str, content: str) -> None:
    path = os.path.join(repo, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _init_git_repo(workdir: str) -> None:
    rc, _, stderr = git_cmd(["init"], workdir)
    assert rc == 0, f"git init falló en el fixture: {stderr!r}"


def _git_add_all_commit(workdir: str, message: str) -> None:
    rc, _, stderr = git_cmd(["add", "-A"], workdir)
    assert rc == 0, f"git add falló en el fixture: {stderr!r}"
    rc, _, stderr = git_cmd(["commit", "-m", message], workdir)
    assert rc == 0, f"git commit falló en el fixture: {stderr!r}"


def _corrupt_git_index(workdir: str) -> None:
    """Sobreescribe .git/index con bytes de basura -- repro real (no
    simulada) de un índice corrupto. Confirmado a mano antes de escribir
    aserciones: `git rev-parse --is-inside-work-tree` sigue saliendo 0
    (el repo real SIGUE ahí) pero `git ls-files` sale 128 con "fatal:
    index file corrupt" -- exactamente el "unknown" tri-state que
    git_tracked_status() documenta, distinto de "untracked"."""
    index_path = os.path.join(workdir, ".git", "index")
    assert os.path.isfile(index_path), "fixture inválido: no hay .git/index que corromper"
    with open(index_path, "wb") as f:
        f.write(b"GARBAGE_NOT_A_REAL_INDEX" * 50)


# ── Item 1 (T1 regression, Cerberus) -- git uncertainty must BLOCK ───────────
#
# El agujero original: is_tracked_in_head() (booleano) devolvía False
# tanto para "confirmado no trackeado" como para "git no pudo responder",
# y el llamador trataba ese False como "seguro para permitir". Reproducido
# por Cerberus: commit de moria/foo.py, borrado del árbol, .git
# inutilizado -> el booleano decía False (igual que "nunca trackeado") y
# el hook dejaba cerrar la sesión sobre un módulo que SÍ había existido y
# se había borrado. git_tracked_status() ahora es tri-state
# ("tracked"/"untracked"/"unknown") precisamente para que esto no vuelva
# a pasar -- estos dos tests fijan los dos lados del corte de diseño.

class TestGitUncertaintyBlocksClassification:
    """seg existe, el módulo concreto está ausente en disco, y la
    consulta a git sobre si estuvo trackeado FALLA de verdad (no dice ni
    sí ni no) -- debe bloquear, nunca colapsar en "nunca escrito"."""

    def test_corrupt_git_index_during_classification_blocks(self, tmp_path):
        """Repo git real: moria/foo.py se commitea, se borra del árbol de
        trabajo, y el índice queda corrupto ANTES de clasificar -- la
        consulta git_tracked_status() no puede confirmar ni tracked ni
        untracked. classify_missing_module debe devolver un veredicto de
        bloqueo, no allow_neverwritten."""
        workdir = str(tmp_path / "repo")
        os.makedirs(workdir)
        _init_git_repo(workdir)
        _write(workdir, "moria/__init__.py", "")
        _write(workdir, "moria/foo.py", "X = 1\n")
        _git_add_all_commit(workdir, "add moria.foo -- fixture del test")
        os.remove(os.path.join(workdir, "moria", "foo.py"))

        # Repro real, confirmada a mano antes de escribir esta aserción:
        # rev-parse --is-inside-work-tree sigue en 0 (el repo real sigue
        # presente), pero ls-files sale 128 ("index file corrupt") --
        # tri-state "unknown", no "untracked".
        _corrupt_git_index(workdir)
        status = gh.git_tracked_status(workdir, ["moria/foo.py", "moria/foo/__init__.py"])
        assert status == "unknown", (
            f"Precondición del fixture: la consulta git debe fallar de "
            f"verdad (tri-state 'unknown'), no 'untracked' ni 'tracked'; "
            f"got={status!r}"
        )

        verdict = dgc.classify_missing_module(workdir, "moria.foo")
        assert verdict == "block_git_unknown", (
            f"Incertidumbre real de git (índice corrupto) debe bloquear "
            f"-- nunca colapsar en allow_neverwritten sobre una duda; "
            f"verdict={verdict!r}"
        )
        assert verdict.startswith("block_"), (
            f"Cualquier veredicto que no sea allow_neverwritten debe ser "
            f"un veredicto de bloqueo por construcción; verdict={verdict!r}"
        )

        # Confirmación de extremo a extremo de la agregación: el mismo
        # texto de salida que el hook vería de pytest, clasificado a
        # través de classify_collection_error(), también debe bloquear.
        fake_pytest_output = "ModuleNotFoundError: No module named 'moria.foo'"
        allow, never_written = dgc.classify_collection_error(workdir, fake_pytest_output)
        assert allow is False, (
            "Con git en duda real, classify_collection_error debe agregar "
            f"a bloqueo, no a permiso; allow={allow!r}"
        )
        assert never_written == []

    def test_no_git_repo_at_all_confirms_allow_neverwritten(self, tmp_path):
        """Frontera de diseño intencionada, el otro lado del corte: SIN
        repo git en absoluto (ni siquiera `.git`), un módulo local nunca
        escrito no puede tener historia que borrar -- confirmado
        "untracked" (no "unknown"), así que debe permitir."""
        workdir = str(tmp_path / "no_git_workdir")
        os.makedirs(workdir)
        _write(workdir, "moria/__init__.py", "")
        # moria.never_written_thing -- ni en disco ni puede estar en git,
        # porque no hay ningún git.

        status = gh.git_tracked_status(
            workdir, ["moria/never_written_thing.py", "moria/never_written_thing/__init__.py"]
        )
        assert status == "untracked", (
            f"Sin repo git, la consulta debe resolver CONFIRMADO ausente "
            f"('untracked'), no 'unknown' -- no hay historia que dude; "
            f"got={status!r}"
        )

        verdict = dgc.classify_missing_module(workdir, "moria.never_written_thing")
        assert verdict == "allow_neverwritten", (
            f"Sin repo git y con seg presente en disco, un módulo nunca "
            f"escrito debe permitir -- no hay borrado trackeado posible "
            f"sin historia; verdict={verdict!r}"
        )


# ── Item 3 -- block_present, la rama sin repro real vía pytest ────────────────
#
# test_stop_dod_gate.py documenta (2026-08-20) que esta rama no tiene un
# repro portable vía la salida REAL de pytest: si el fichero de X existe y
# es importable, CPython no levanta ModuleNotFoundError nombrando
# exactamente ese X. A nivel unitario, contra la función pura, sí es
# directamente alcanzable: basta con pedirle que clasifique un X cuyo
# fichero concreto SÍ existe en disco -- exactamente la precondición que
# dispara la rama defensiva, sin necesitar que pytest la produzca de
# verdad.

class TestBlockPresentBranch:
    def test_concrete_source_present_on_disk_blocks(self, tmp_path):
        workdir = str(tmp_path / "present_workdir")
        os.makedirs(workdir)
        _write(workdir, "moria/__init__.py", "")
        _write(workdir, "moria/foo.py", "X = 1\n")  # el fuente de X SÍ existe

        verdict = dgc.classify_missing_module(workdir, "moria.foo")

        assert verdict == "block_present", (
            f"El fuente concreto de X existe en disco -- rama defensiva "
            f"'existe pero se reportó como faltante', debe bloquear; "
            f"verdict={verdict!r}"
        )

    def test_concrete_source_present_as_package_dir_blocks(self, tmp_path):
        """Misma rama, pero el fuente concreto es un paquete
        (`__init__.py` bajo un directorio), no un módulo suelto --
        `module_source_candidates` genera ambas formas."""
        workdir = str(tmp_path / "present_pkg_workdir")
        os.makedirs(workdir)
        _write(workdir, "moria/__init__.py", "")
        _write(workdir, "moria/foo/__init__.py", "X = 1\n")

        verdict = dgc.classify_missing_module(workdir, "moria.foo")

        assert verdict == "block_present", (
            f"El fuente concreto de X existe como paquete en disco -- "
            f"misma rama defensiva, debe bloquear; verdict={verdict!r}"
        )


# ── D-042 (2026-08-20, Moriarty finding, coverage gap) -- declared identity ───
#
# Ultron implemented D-042 (first-party by declared project identity,
# checked BEFORE the disk/git layout signal) with zero tests -- he only
# called the helpers directly while writing them, never through a real
# TOML/cfg file on a real filesystem, and never through the real hook +
# real pytest end-to-end (that half lives in test_stop_dod_gate.py's
# TestDeclaredIdentityD042EndToEnd). These tests hit real files written to
# tmp_path and parsed by the REAL tomllib/configparser, nothing mocked.
#
# Bug found while writing this coverage, NOT fixed here (out of lane,
# reported instead): `_names_from_setup_cfg()`'s own docstring promises
# "never raises", but `configparser.ConfigParser.read()` raises a bare
# `UnicodeDecodeError` on a non-UTF-8 setup.cfg -- NOT a subclass of
# either `OSError` or `configparser.Error`, so the function's own
# `except (OSError, configparser.Error):` clause misses it. Confirmed by
# hand: `_names_from_setup_cfg()` and `_declared_first_party_names()`
# called DIRECTLY on a binary setup.cfg both raise UnicodeDecodeError
# uncaught. The bug is currently MASKED at the only boundary the hook
# actually calls -- `classify_missing_module()`'s own blanket
# `except Exception: return "block_thirdparty"` swallows it one layer up,
# so the observable hook behavior stays safe (block on doubt, D2 holds).
# `TestDeclaredIdentityFailsSafe` below tests the safe, masked boundary
# (`classify_missing_module`) with a binary setup.cfg, and separately
# tests `_names_from_setup_cfg()` directly with a syntactically-broken
# but valid-UTF8 cfg (the documented, already-safe degrade path) --
# deliberately NOT calling `_names_from_setup_cfg()` directly with binary
# content, which would just pin today's contract violation instead of
# testing real behavior. Once Ultron adds `UnicodeDecodeError` to that
# except clause, the regression test for the fix is exactly that direct
# call.

class TestDeclaredFirstPartyIdentity:
    """Cada fuente de identidad declarada, por separado, contra ficheros
    reales en tmp_path -- el módulo nunca existió en disco ni en git, así
    que SOLO la identidad declarada puede hacer que se permita."""

    def test_pyproject_project_name_declares_first_party(self, tmp_path):
        workdir = str(tmp_path / "proj_pep621")
        os.makedirs(workdir)
        _write(workdir, "pyproject.toml", '[project]\nname = "moria"\nversion = "0.1.0"\n')

        assert dgc.classify_missing_module(workdir, "moria") == "allow_neverwritten", (
            "[project].name declara 'moria' como propio -- un 'moria' "
            "nunca escrito debe permitir, no bloquear como third-party"
        )

    def test_pyproject_poetry_name_declares_first_party(self, tmp_path):
        workdir = str(tmp_path / "proj_poetry")
        os.makedirs(workdir)
        _write(workdir, "pyproject.toml", '[tool.poetry]\nname = "moria"\nversion = "0.1.0"\n')

        assert dgc.classify_missing_module(workdir, "moria") == "allow_neverwritten", (
            "[tool.poetry].name debe reconocerse igual que [project].name"
        )

    def test_pyproject_setuptools_packages_list_declares_first_party(self, tmp_path):
        workdir = str(tmp_path / "proj_setuptools_list")
        os.makedirs(workdir)
        _write(workdir, "pyproject.toml", '[tool.setuptools]\npackages = ["moria"]\n')

        assert dgc.classify_missing_module(workdir, "moria") == "allow_neverwritten", (
            "[tool.setuptools].packages (lista explícita) debe declarar "
            "'moria' como propio"
        )

    def test_pyproject_setuptools_packages_find_declares_first_party(self, tmp_path):
        """packages.find escanea el directorio real -- a diferencia de las
        otras fuentes, esta SOLO puede nombrar algo que ya existe en disco
        (mismo comentario del propio `_resolve_setuptools_find`), así que
        el propio paquete SÍ tiene que estar ahí para que el finder lo
        vea; lo que se prueba es que la clasificación de un SUBmódulo
        nunca escrito dentro de ese paquete pasa por la vía de identidad
        declarada, no por seg_exists() a secas."""
        workdir = str(tmp_path / "proj_setuptools_find")
        os.makedirs(workdir)
        _write(workdir, "moria/__init__.py", "")
        _write(workdir, "pyproject.toml", '[tool.setuptools.packages.find]\nwhere = ["."]\n')

        assert "moria" in dgc._names_from_pyproject(workdir), (
            "packages.find debe resolver 'moria' como nombre declarado a "
            "partir del escaneo real del directorio"
        )
        assert dgc.classify_missing_module(workdir, "moria.never_written_sub") == "allow_neverwritten", (
            "Un submódulo nunca escrito de un paquete resuelto vía "
            "packages.find debe permitir"
        )

    def test_setup_cfg_metadata_name_declares_first_party(self, tmp_path):
        workdir = str(tmp_path / "proj_setupcfg")
        os.makedirs(workdir)
        _write(workdir, "setup.cfg", "[metadata]\nname = moria\n")

        assert dgc.classify_missing_module(workdir, "moria") == "allow_neverwritten", (
            "setup.cfg [metadata] name debe declarar 'moria' como propio"
        )

    def test_declared_name_normalizes_dash_to_underscore(self, tmp_path):
        """Nombre declarado con guion ('mi-paquete'), módulo faltante con
        guion bajo ('mi_paquete') -- la normalización D-042 debe hacerlos
        coincidir."""
        workdir = str(tmp_path / "proj_normalize")
        os.makedirs(workdir)
        _write(workdir, "pyproject.toml", '[project]\nname = "mi-paquete"\n')

        assert "mi_paquete" in dgc._names_from_pyproject(workdir), (
            f"'mi-paquete' declarado debe normalizarse a 'mi_paquete'; "
            f"got={dgc._names_from_pyproject(workdir)!r}"
        )
        assert dgc.classify_missing_module(workdir, "mi_paquete") == "allow_neverwritten", (
            "Con la normalización, un 'mi_paquete' nunca escrito debe "
            "permitir"
        )


class TestDeclaredIdentityFailsSafe:
    """Fallo al parsear la identidad declarada nunca puede abrir la
    puerta -- degrada a la señal de layout de siempre, y si el seg no
    existe ahí tampoco, bloquea (D2: nunca permitir sobre una duda)."""

    def test_corrupt_pyproject_toml_never_allows_new_toplevel(self, tmp_path):
        workdir = str(tmp_path / "corrupt_toml")
        os.makedirs(workdir)
        _write(workdir, "pyproject.toml", "this is [ not valid toml at all ===")

        assert dgc._names_from_pyproject(workdir) == set(), (
            "TOML inválido debe degradar a un set vacío, nunca lanzar ni "
            "asumir identidad"
        )
        assert dgc.classify_missing_module(workdir, "brandnew_corrupt_toml") == "block_thirdparty", (
            "Con pyproject.toml corrupto y el módulo ausente del disco/git, "
            "debe bloquear -- un fallo de parseo nunca abre la puerta"
        )

    def test_malformed_but_valid_utf8_setup_cfg_degrades_to_empty_names(self, tmp_path):
        """setup.cfg sintácticamente roto (sección sin cerrar) pero en
        UTF-8 válido -- configparser.Error, ya capturado por el except
        documentado. Camino seguro ya cubierto por el propio código."""
        workdir = str(tmp_path / "badsyntax_cfg")
        os.makedirs(workdir)
        _write(workdir, "setup.cfg", "[metadata\nname = moria\n")  # falta el ]

        assert dgc._names_from_setup_cfg(workdir) == set(), (
            "setup.cfg con sintaxis rota (pero UTF-8 válido) debe degradar "
            "a un set vacío, nunca lanzar"
        )
        assert dgc.classify_missing_module(workdir, "brandnew_badsyntax_cfg") == "block_thirdparty", (
            "Con setup.cfg ilegible y el módulo ausente del disco/git, "
            "debe bloquear"
        )

    def test_unreadable_binary_setup_cfg_never_allows_at_classify_boundary(self, tmp_path):
        """setup.cfg binario (no UTF-8) -- en la frontera pública que
        realmente llama el hook (`classify_missing_module`), el resultado
        sigue siendo seguro: bloquea, nunca permite sobre la duda. (Ver
        nota de arriba: `_names_from_setup_cfg()` en sí mismo SÍ lanza sin
        capturar sobre esta entrada exacta -- bug real, reportado aparte,
        no tocado aquí -- pero queda enmascarado por el
        `except Exception` de `classify_missing_module`, que es la única
        frontera que el hook llama de verdad.)"""
        workdir = str(tmp_path / "binary_cfg")
        os.makedirs(workdir)
        with open(os.path.join(workdir, "setup.cfg"), "wb") as f:
            f.write(b"\x00\x01\xff\xfe not a cfg [[[ ===")

        assert dgc.classify_missing_module(workdir, "brandnew_binary_cfg") == "block_thirdparty", (
            "setup.cfg binario/no-UTF8 -- en la frontera que el hook "
            "realmente llama, debe seguir bloqueando, nunca permitir "
            "sobre la duda"
        )


class TestNoDeclaredIdentityStillBlocksNewTopLevel:
    """Sin pyproject.toml ni setup.cfg en absoluto -- comportamiento
    ANTERIOR a D-042 (solo layout), coste aceptado explícitamente por el
    propietario para un proyecto que no declara su propia identidad. Se
    fija como test para que nadie lo "arregle" sin decidirlo aparte."""

    def test_no_identity_files_new_toplevel_module_still_blocks(self, tmp_path):
        workdir = str(tmp_path / "no_identity")
        os.makedirs(workdir)
        # Ni pyproject.toml ni setup.cfg -- proyecto sin identidad declarada.

        assert dgc._declared_first_party_names(workdir) == set()
        assert dgc.classify_missing_module(workdir, "brandnew_no_identity") == "block_thirdparty", (
            "Sin identidad declarada, un módulo top-level nuevo sigue "
            "bloqueando -- coste aceptado a propósito por D-042, no un "
            "bug pendiente de arreglar"
        )


# ── Regression: UnicodeDecodeError fix, called DIRECTLY (2026-08-20) ─────────
#
# Follow-up to the bug flagged in TestDeclaredIdentityFailsSafe above:
# Ultron added `UnicodeDecodeError` to `_names_from_setup_cfg()`'s except
# clause, and confirmed `_names_from_pyproject()` already caught it via
# its existing `except (OSError, ValueError)` (UnicodeDecodeError is a
# ValueError subclass). These tests call the two helpers -- and
# `_declared_first_party_names()`, which has no `except` of its own --
# DIRECTLY, deliberately bypassing `classify_missing_module()`'s blanket
# `except Exception`. That umbrella is exactly what masked the original
# bug: a test that goes through it again would stay green whether or not
# the inner fix is real. Calling the inner functions with no umbrella is
# the only way to prove the fix, not just the outer safety net.

class TestUnicodeDecodeErrorFixDirectCalls:
    def _write_binary(self, workdir: str, filename: str) -> str:
        path = os.path.join(workdir, filename)
        with open(path, "wb") as f:
            f.write(b"\x00\x01\xff\xfe not valid utf-8 [[[ ===")
        return path

    def test_names_from_setup_cfg_binary_content_returns_empty_no_raise(self, tmp_path):
        workdir = str(tmp_path / "direct_binary_cfg")
        os.makedirs(workdir)
        self._write_binary(workdir, "setup.cfg")

        result = dgc._names_from_setup_cfg(workdir)

        assert result == set(), (
            f"setup.cfg no-UTF8, llamado directamente (sin el paraguas de "
            f"classify_missing_module) -- debe degradar a un set vacío, "
            f"nunca lanzar; got={result!r}"
        )

    def test_names_from_pyproject_binary_content_returns_empty_no_raise(self, tmp_path):
        """Simetría: el mismo repro pero para pyproject.toml -- Ultron
        confirmó que ya estaba cubierto vía `except (OSError, ValueError)`
        (UnicodeDecodeError es subclase de ValueError); esto lo fija como
        test, no solo como confirmación verbal."""
        workdir = str(tmp_path / "direct_binary_pyproject")
        os.makedirs(workdir)
        self._write_binary(workdir, "pyproject.toml")

        result = dgc._names_from_pyproject(workdir)

        assert result == set(), (
            f"pyproject.toml no-UTF8, llamado directamente -- debe "
            f"degradar a un set vacío, nunca lanzar; got={result!r}"
        )

    def test_declared_first_party_names_both_files_binary_returns_empty_no_raise(self, tmp_path):
        """`_declared_first_party_names()` no tiene su propio try/except
        -- depende enteramente de que las dos funciones que envuelve
        degraden limpio. Con AMBOS ficheros binarios a la vez, debe
        seguir devolviendo un set vacío sin lanzar."""
        workdir = str(tmp_path / "direct_binary_both")
        os.makedirs(workdir)
        self._write_binary(workdir, "pyproject.toml")
        self._write_binary(workdir, "setup.cfg")

        result = dgc._declared_first_party_names(workdir)

        assert result == set(), (
            f"pyproject.toml Y setup.cfg no-UTF8 a la vez, llamado "
            f"directamente sobre _declared_first_party_names (sin "
            f"paraguas propio) -- debe degradar a un set vacío, nunca "
            f"lanzar; got={result!r}"
        )
