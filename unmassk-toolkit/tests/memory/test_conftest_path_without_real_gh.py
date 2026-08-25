"""Regresion permanente de `conftest.py::path_without_real_gh()` -- la
REAPARICION del incidente CI del 2026-08-22 (CI run 32895458657, commit
d9cec70, Yoda system pass M-126): el arreglo original filtraba el
DIRECTORIO entero que contuviera un `gh` real, correcto solo mientras
`gh` y `git` viven en sitios distintos. En `ubuntu-latest` ambos
conviven en `/usr/bin` -- quitar el directorio se llevaba `git` por
delante, y 37 tests caian con "git no encontrado". En local (macOS,
Homebrew `gh` separado de Xcode CLT `git`) nunca se reproducia.

El arreglo definitivo (ver `conftest.py::path_without_real_gh` y
`_dir_without_gh`) filtra por FICHERO: cuando un directorio del `PATH`
trae un `gh` real, se reconstruye en un directorio de scratch con un
symlink a cada entrada EXCEPTO `gh`/`gh.exe`/`gh.cmd`/`gh.bat`, y ese
directorio de scratch sustituye al original -- `git` (y cualquier otro
binario que comparta carpeta con `gh`) sigue siendo localizable.

Cada test de aqui monta su propio "`/usr/bin` sintetico" (un directorio
propio con `git` y `gh` -- y a veces un tercer binario -- escritos por
el propio test, NUNCA el PATH real de esta maquina, que ya separa
`git`/`gh` y enmascararia el bug que se quiere cubrir) y compara dos
cosas escritas por separado: el contenido que el test escribio al
fabricar el escenario, contra lo que se lee de vuelta a traves del PATH
que devuelve el filtro bajo prueba.

Demostracion en ROJO contra la logica vieja (ejecutada una vez, no
permanente en este fichero -- reimplementarla aqui duplicaria produccion
de test dentro del propio test): con `path_without_real_gh` sustituida
por la version pre-arreglo (`kept = [d for d in dirs if not any(...)]`,
que ELIMINA el directorio entero en vez de reconstruirlo sin `gh`),
`TestGitSurvivesWhenGitAndGhShareADirectory` y
`TestNoDirectoryInTheResultContainsARealGh`'s companion assertions sobre
localizar `git` fallan (`shutil.which('git', path=...) is None`) --
confirmado corriendo estos mismos cuerpos de test contra esa version
vieja via `pytest.MonkeyPatch` en un script ad hoc, nunca commiteado.
Contra la version actual, verde.

CORRECCION MULTIPLATAFORMA (CI run 32904954108, 2026-08-26): los
binarios sinteticos originales se escribian con el nombre PELADO ("git",
"gh", "some-other-tool") en las tres plataformas. En ubuntu-latest y
macOS eso es correcto (solo importa el bit +x); en windows-latest,
`shutil.which()` nunca considera un candidato exacto a un nombre sin
extension de `PATHEXT` -- 3 tests caian alli con el mismo sintoma que el
bug real ("git ya no es localizable"), aunque el fichero SI estuviera en
el PATH devuelto. `_binary_name()` (arriba) escribe y busca cada binario
con el nombre que CADA plataforma exige (`git.exe` en Windows, `git` en
POSIX) -- ni un skip de Windows, ni una aserción mas debil: el mismo
contrato, expresado en la forma que cada plataforma reconoce.
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

from .conftest import _GH_FAKE_NAMES, _SANITIZED_GH_FREE_DIRS, path_without_real_gh

# `shutil.which()` en Windows (leido en la fuente real de la libreria
# estandar antes de escribir esto, no supuesto) SOLO antepone el nombre
# PELADO a la lista de candidatos cuando ese nombre YA termina en una
# extension de PATHEXT (`git.exe`) -- para un nombre sin extension
# (`git`), which() nunca prueba el fichero exacto, solo `git`+cada
# extension de PATHEXT (`.COM`, `.EXE`, `.BAT`...). Un binario sintetico
# escrito literalmente como "git" (correcto en POSIX, donde solo importa
# el bit +x) es por tanto INVISIBLE para `shutil.which("git", ...)` en
# Windows, aunque el fichero exista y este en el PATH devuelto -- CI
# confirmado (run 32904954108): "git ya no es localizable tras filtrar"
# en windows-latest, verde en ubuntu-latest con el MISMO codigo. La
# extension no es cosmetica ahi: es lo que which() exige para considerar
# el fichero un candidato exacto. `sys.platform == "win32"`, no
# `os.name == "nt"` -- mismo criterio que el resto de la suite
# (`test_work_issue_field.py`/`test_note_issue_field.py`/
# `test_report_render_issue_field.py`/`gitcmd.py`, nunca `os.name`).
_EXE_SUFFIX = ".exe" if sys.platform == "win32" else ""


def _binary_name(base):
    """El nombre de fichero que ESTA plataforma resuelve como ejecutable
    real -- sufijo `.exe` en Windows, nada en POSIX. Mismo criterio que
    `conftest.py::_GH_FAKE_NAMES` ya usa para reconocer un `gh` real
    (`gh`/`gh.exe`/`gh.cmd`/`gh.bat`): un binario de test que se hace
    pasar por "el ejecutable real de esta plataforma" tiene que llevar
    la forma que esa plataforma exige, no una fija.
    """
    return base + _EXE_SUFFIX


@pytest.fixture(autouse=True)
def _cleanup_sanitized_dirs_created_by_this_test():
    """`_SANITIZED_GH_FREE_DIRS` es un cache a nivel de modulo, compartido
    con el resto de la suite (limpiado de verdad solo al salir del
    proceso, via `atexit` -- ver `conftest.py`). Cada test de aqui usa un
    `tmp_path` propio, asi que sus claves nunca colisionan con las de
    otro test, pero sin este borrado se acumularian directorios de
    scratch reales en disco en cada ejecucion local repetida.
    """
    keys_before = set(_SANITIZED_GH_FREE_DIRS)
    yield
    keys_after = set(_SANITIZED_GH_FREE_DIRS)
    for key in keys_after - keys_before:
        shutil.rmtree(_SANITIZED_GH_FREE_DIRS.pop(key), ignore_errors=True)


def _shared_bin_dir(tmp_path, dirname="usr-bin-like", extra_names=()):
    """Simula `/usr/bin` en `ubuntu-latest`: `git` y `gh` (y, si se pide,
    algun binario mas) viviendo en el MISMO directorio -- nunca el PATH
    real de esta maquina de desarrollo, que ya los mantiene separados.
    Cada nombre pasa por `_binary_name()`: en Windows los ficheros se
    llaman `git.exe`/`gh.exe`/etc (lo que `shutil.which()` y el propio
    `PATHEXT` del sistema esperan), en POSIX se quedan pelados.
    """
    shared_dir = tmp_path / dirname
    shared_dir.mkdir()
    for base_name in ("git", "gh", *extra_names):
        binary_path = shared_dir / _binary_name(base_name)
        binary_path.write_text(f"real {base_name} binary\n", encoding="utf-8")
        binary_path.chmod(0o755)
    return shared_dir


class TestGitSurvivesWhenGitAndGhShareADirectory:
    """El fallo real de CI: `git` desaparecia cuando compartia carpeta
    con un `gh` real. Estos tests son la garantia de que no vuelve.
    """

    def test_git_stays_locatable_after_filtering_a_shared_directory(
        self, tmp_path, monkeypatch
    ):
        shared_dir = _shared_bin_dir(tmp_path)
        monkeypatch.setenv("PATH", str(shared_dir))

        result_path = path_without_real_gh()

        git_hit = shutil.which(_binary_name("git"), path=result_path)
        assert git_hit is not None, (
            f"git ya no es localizable tras filtrar -- PATH resultante: {result_path!r}"
        )
        assert Path(git_hit).read_text(encoding="utf-8") == (
            shared_dir / _binary_name("git")
        ).read_text(encoding="utf-8")

    def test_shared_directory_itself_is_replaced_not_left_empty(
        self, tmp_path, monkeypatch
    ):
        shared_dir = _shared_bin_dir(tmp_path)
        monkeypatch.setenv("PATH", str(shared_dir))

        result_path = path_without_real_gh()
        result_dirs = result_path.split(os.pathsep)

        assert str(shared_dir) not in result_dirs
        assert len(result_dirs) == 1
        assert result_dirs[0] != ""

    def test_a_third_binary_sharing_the_directory_also_survives(
        self, tmp_path, monkeypatch
    ):
        shared_dir = _shared_bin_dir(tmp_path, extra_names=("some-other-tool",))
        monkeypatch.setenv("PATH", str(shared_dir))

        result_path = path_without_real_gh()

        tool_hit = shutil.which(_binary_name("some-other-tool"), path=result_path)
        assert tool_hit is not None
        assert Path(tool_hit).read_text(encoding="utf-8") == (
            shared_dir / _binary_name("some-other-tool")
        ).read_text(encoding="utf-8")


class TestNoDirectoryInTheResultContainsARealGh:
    """El otro lado del contrato: filtrar por fichero no puede dejar
    colar `gh` de vuelta en ningun directorio del PATH devuelto.
    """

    def test_no_directory_in_the_returned_path_contains_a_real_gh(
        self, tmp_path, monkeypatch
    ):
        shared_dir = _shared_bin_dir(tmp_path)
        monkeypatch.setenv("PATH", str(shared_dir))

        result_path = path_without_real_gh()

        for result_dir in result_path.split(os.pathsep):
            for gh_name in _GH_FAKE_NAMES:
                assert not os.path.isfile(os.path.join(result_dir, gh_name)), (
                    f"{gh_name} sigue localizable en {result_dir}"
                )

    def test_windows_style_gh_names_are_also_filtered(self, tmp_path, monkeypatch):
        shared_dir = tmp_path / "windows-like"
        shared_dir.mkdir()
        for name in ("git.exe", "gh.exe"):
            binary_path = shared_dir / name
            binary_path.write_text(f"real {name}\n", encoding="utf-8")
            binary_path.chmod(0o755)
        monkeypatch.setenv("PATH", str(shared_dir))

        result_path = path_without_real_gh()

        assert shutil.which("git.exe", path=result_path) is not None
        assert shutil.which("gh.exe", path=result_path) is None


class TestSanitizedCopyIsCachedPerRealDirectory:
    def test_calling_twice_for_the_same_shared_directory_reuses_the_sanitized_copy(
        self, tmp_path, monkeypatch
    ):
        shared_dir = _shared_bin_dir(tmp_path)
        monkeypatch.setenv("PATH", str(shared_dir))

        first_result = path_without_real_gh()
        second_result = path_without_real_gh()

        assert first_result == second_result


class TestSymlinkFallbackWhenSymlinksAreUnsupported:
    """`_dir_without_gh` prefiere symlinks (barato, incluso con cientos
    de entradas como `/usr/bin`) pero cae a una copia real ENTRADA A
    ENTRADA cuando `os.symlink` falla -- nunca a copiar el directorio
    completo ni a dejarlo fuera del PATH.
    """

    def test_symlink_unsupported_falls_back_to_a_real_copy_of_just_that_entry(
        self, tmp_path, monkeypatch
    ):
        shared_dir = _shared_bin_dir(tmp_path)
        monkeypatch.setenv("PATH", str(shared_dir))

        def _symlink_always_fails(src, dst):
            raise OSError("symlinks no soportados (simulado)")

        monkeypatch.setattr(os, "symlink", _symlink_always_fails)

        result_path = path_without_real_gh()

        git_hit = shutil.which(_binary_name("git"), path=result_path)
        assert git_hit is not None
        assert not os.path.islink(git_hit), (
            "deberia ser una copia real, no un symlink, cuando symlink() falla"
        )
        assert Path(git_hit).read_text(encoding="utf-8") == (
            shared_dir / _binary_name("git")
        ).read_text(encoding="utf-8")
